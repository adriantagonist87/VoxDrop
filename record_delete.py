"""Confirmed history deletion: native trash first, SQL last; never unlink media."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import time
import uuid

from history_store import history_category, media_path_key, search_storage_lock
from platform_io import is_reparse_point, open_regular
from smb_paths import on_network_volume

ACTIVE={'copying','transcribing','exporting'}


def media_paths(job):
    source=Path(job['source']);archived=Path(job['completed_dir'])/source.name
    settings=json.loads(job['settings'])
    moved=not settings.get('watch_path') or settings.get('move_media')
    return list(dict.fromkeys((archived,source) if moved and job['state']=='done' and not job['origin_job_id'] else (source,archived)))


def text_path(job):
    if job.get('known_transcript_path'):return Path(job['known_transcript_path'])
    if job.get('result_kind') in ('existing','duplicate'):return Path(job['source']).with_suffix('.txt')
    media=Path(job['completed_dir'])/Path(job['source']).name
    if not job['origin_job_id']:return media.with_suffix('.txt')
    name=f"{media.stem} (Neu {job['id']}).txt"
    return media.with_name(name if len(name.encode('utf-8'))<=255 else f"Neutranskription {job['id']}.txt")


def rows(db):
    return [dict(row) for row in db.execute('SELECT j.*,k.kind AS result_kind,k.transcript_path AS known_transcript_path '
        'FROM jobs j LEFT JOIN known_results k ON k.job_id=j.id ORDER BY j.id')]


def connected_jobs(by_id,job_paths,identifier):
    if identifier not in by_id:raise ValueError('Der Datensatz ist nicht mehr vorhanden.')
    selected=by_id[identifier]
    if history_category(selected) is None:raise ValueError('Nur abgeschlossene Verlaufseinträge können gelöscht werden.')
    root=selected;seen=set()
    while root['origin_job_id'] in by_id:
        if root['id'] in seen:raise ValueError('Die Verknüpfungen dieser Aufnahme sind ungültig.')
        seen.add(root['id']);root=by_id[root['origin_job_id']]
    identifiers={root['id'],identifier}
    paths=job_paths[root['id']][0] | job_paths[identifier][0]
    texts={job_paths[root['id']][1],job_paths[identifier][1]}
    # Include aliases of this root, without probing every unrelated library path.
    for path in media_paths(selected):
        paths.add(media_path_key(path.resolve(strict=False)))
    while True:
        previous=set(identifiers)
        for job_id,row in by_id.items():
            media,text=job_paths[job_id]
            if job_id not in identifiers and (row['origin_job_id'] in identifiers or text in texts or paths & media):
                identifiers.add(job_id)
                paths.update(media)
                texts.add(text)
        if previous==identifiers:break
    return identifiers


def selected_groups(all_rows,selection):
    by_id={row['id']:row for row in all_rows}
    job_paths={
        row['id']:({media_path_key(path) for path in media_paths(row)},media_path_key(text_path(row)))
        for row in all_rows
    }
    groups=[]
    for identifier in selection:
        connected=connected_jobs(by_id,job_paths,identifier)
        for known in groups[:]:
            if connected & known:
                connected.update(known)
                groups.remove(known)
        groups.append(connected)
    for group in groups:
        for job_id in group:
            job=by_id[job_id]
            if job['state'] in ACTIVE:
                raise ValueError(f'Für „{Path(job["source"]).name}“ läuft noch eine Verarbeitung. Bitte zuerst fertigstellen oder stoppen.')
    return [[by_id[job_id] for job_id in sorted(group)] for group in groups]


def selected_rows(groups):
    return sorted((row for group in groups for row in group),key=lambda row:row['id'])


def fingerprint(path,*,directory=False):
    metadata=path.lstat()
    if path.is_symlink() or is_reparse_point(metadata) or not (stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)):
        raise ValueError(f'Keine zulässige reguläre Datei bzw. Arbeitskopie: {path}')
    value=[metadata.st_dev,metadata.st_ino,metadata.st_size,metadata.st_mtime_ns]
    if directory:
        value.append([[str(p.relative_to(path)),fingerprint(p,directory=p.is_dir())] for p in sorted(path.iterdir())])
    return value


def check_network(path):
    if on_network_volume(path) or on_network_volume(path.resolve(strict=False)):
        raise ValueError('Löschen auf Netzlaufwerken ist deaktiviert: Dort steht kein verlässlich nutzbarer Betriebssystem-Papierkorb bereit. Dateien und Datensätze bleiben erhalten.\n'+str(path))


def snapshot_file(path,role):
    path=path.absolute()
    check_network(path)
    if not Path(path.anchor).is_dir():raise OSError(f'Das Laufwerk ist nicht erreichbar: {path.anchor}')
    try:identity=fingerprint(path,directory=role=='cache')
    except FileNotFoundError:return dict(path=str(path),role=role,identity=None,canonical=str(path.resolve(strict=False)),status='missing')
    return dict(path=str(path),role=role,identity=identity,canonical=str(path.resolve(strict=True)),status='pending')


def hash_file(path):
    descriptor=open_regular(path,os.O_RDONLY)
    with os.fdopen(descriptor,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def journal_path(state,token):
    if not re.fullmatch('[0-9a-f]{32}',token):raise ValueError('Ungültige Löschbestätigung.')
    folder=state/'record-delete'
    if folder.exists() and (folder.is_symlink() or is_reparse_point(folder.lstat())):raise ValueError('Ungültiger lokaler Löschspeicher.')
    folder.mkdir(exist_ok=True,mode=0o700)
    return folder/(token+'.json')


def save(state,plan):
    target=journal_path(state,plan['token'])
    fd,name=tempfile.mkstemp(prefix='.plan-',dir=target.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as file:
            json.dump(plan,file,ensure_ascii=True);file.flush();os.fsync(file.fileno())
        os.replace(name,target)
    finally:Path(name).unlink(missing_ok=True)


def load(state,token):
    path=journal_path(state,token)
    if path.is_symlink() or is_reparse_point(path.lstat()):raise ValueError('Ungültige Löschbestätigung.')
    plan=json.loads(path.read_text(encoding='utf-8'))
    if plan.get('token')!=token or plan.get('schema')!=1:raise ValueError('Ungültige Löschbestätigung.')
    return plan


def public(plan):
    return dict(token=plan['token'],jobId=plan['selected'],name=plan['name'],
        selectedCount=len(selection_for(plan)),recordCount=len(plan['rows']),
        files=[dict(path=f['path'],role=f['role'],missing=f['status']=='missing',trashed=f['status']=='trashed',protected=f['status']=='protected') for f in plan['files']],
        lockedMode=plan['confirmed'],keepOriginal=plan.get('keepOriginal',not plan['confirmed']),
        partial=any(f['status']=='trashed' for f in plan['files']))


def selection_for(plan):
    return plan.get('selection',[plan['selected']])


def overlapping_plan(state,identifiers,*,skip=None):
    folder=state/'record-delete'
    if folder.is_dir() and not folder.is_symlink() and not is_reparse_point(folder.lstat()):
        for candidate in folder.glob('*.json'):
            if candidate.stem==skip:
                continue
            try:
                plan=load(state,candidate.stem)
            except FileNotFoundError:
                continue
            if plan['confirmed'] and any(row['id'] in identifiers for row in plan['rows']):
                return plan
    return None


def prepare(db,state,identifier,*additional):
    state=state.resolve()
    selection=sorted({identifier,*additional})
    all_rows=rows(db)
    by_id={row['id']:row for row in all_rows}
    for job_id in selection:
        if job_id not in by_id:
            raise ValueError('Ein ausgewählter Datensatz ist nicht mehr vorhanden. Bitte die Auswahl aktualisieren.')
        initial=by_id[job_id]
        for path in [*media_paths(initial),text_path(initial)]:
            check_network(path)
    groups=selected_groups(all_rows,selection)
    selected=selected_rows(groups)
    identifiers={row['id'] for row in selected}
    old=overlapping_plan(state,identifiers)
    if old:
        if not identifiers.issubset(row['id'] for row in old['rows']):
            raise ValueError('Ein Teil der Auswahl gehört zu einer begonnenen Löschung. Öffne einen dieser Einträge einzeln, um die Löschung fortzusetzen.')
        if old['rows']!=selected_rows(selected_groups(all_rows,selection_for(old))):
            raise ValueError('Die Datensätze haben sich seit dem begonnenen Löschen geändert. Bitte die bereits verschobenen Dateien im Papierkorb prüfen.')
        for file in old['files']:
            if file['status']=='pending' and not Path(file['path']).exists():
                file['status']='missing'
        return public(old)
    files={}
    for group in groups:
        for path,file in group_files(state,group).items():
            prior=files.setdefault(path,file)
            if prior is not file and file['role']=='original':
                if file['status']=='protected':
                    prior['status']='protected'
                if file.get('paths') and prior.get('paths'):
                    prior['paths']=list(dict.fromkeys([*prior['paths'],*file['paths']]))
    name=Path(by_id[identifier]['source']).name if len(selection)==1 else f'{len(selection)} ausgewählte Einträge'
    plan=dict(schema=1,token=uuid.uuid4().hex,created=time.time(),selected=identifier,
        selection=selection,name=name,rows=selected,
        files=sorted(files.values(),key=lambda file:{'original':0,'transcript':1,'cache':2}[file['role']]),confirmed=False)
    save(state,plan)
    return public(plan)


def group_files(state,selected):
    from voxdrop import MEDIA_EXTENSIONS

    files={};originals={};owners={}
    for job in selected:
        if Path(job['source']).suffix.casefold() not in MEDIA_EXTENSIONS:
            raise ValueError('Die gespeicherte Originaldatei ist keine unterstützte Mediendatei.')
        for path in media_paths(job):
            file=snapshot_file(path,'original')
            if file['identity'] is None:continue
            if Path(file['canonical']).is_relative_to(state):raise ValueError('Die Originaldatei verweist auf interne Arbeitsdaten.')
            filekey=media_path_key(file['canonical'])
            original=originals.setdefault(filekey,file)
            if original is file:
                original['paths']=[file['canonical']]
            if file['path'] not in original['paths']:
                original['paths'].append(file['path'])
            owners.setdefault(filekey,[]).append(job)
        text=text_path(job)
        if text.suffix.casefold()!='.txt':raise ValueError('Der gespeicherte Transkriptpfad ist keine TXT-Datei.')
        file=snapshot_file(text,'transcript');files.setdefault(media_path_key(file['canonical']),file)
        cache=state/'jobs'/str(job['id'])
        if cache.exists() or cache.is_symlink():
            file=snapshot_file(cache,'cache');files.setdefault(media_path_key(file['canonical']),file)
    valid_original=False
    for filekey,file in originals.items():
        candidates=owners[filekey];path=Path(file['path'])
        digest=hash_file(path) if any(job['media_hash'] for job in candidates) else None
        matches=any((digest==job['media_hash'] if job['media_hash'] else file['identity'][2:4]==[job['size'],job['mtime_ns']]) for job in candidates)
        if fingerprint(path)!=file['identity']:raise ValueError('Die Originaldatei hat sich während der Prüfung geändert.')
        if not matches:file['status']='protected'
        else:valid_original=True
        files[filekey]=file
    if originals and not valid_original:
        raise ValueError(f'Am gespeicherten Ort liegt inzwischen eine andere oder geänderte Originaldatei: {next(iter(originals.values()))["path"]}')
    if not originals:
        for job in selected:
            file=snapshot_file(media_paths(job)[0],'original');files.setdefault(media_path_key(file['canonical']),file)
    return files


def discard(state,token):
    plan=load(state,token)
    if not plan.get('confirmed'):journal_path(state,token).unlink()


def native_trash(path):
    # Qt 6.10's Windows implementation uses IFileOperation + FOFX_RECYCLEONDELETE.
    # There is deliberately no remove/unlink fallback for user media or transcripts.
    from PySide6.QtCore import QFile
    check_network(path)
    file=QFile(path.as_posix())
    if not QFile.supportsMoveToTrash() or not file.moveToTrash():
        raise OSError(f'Nicht in den Papierkorb verschoben: {path}. {file.errorString()}')
    receipt=file.fileName()
    if os.name=='nt' and not receipt:raise OSError('Der Papierkorb hat keinen Wiederherstellungsort bestätigt.')
    if path.exists():raise OSError(f'Die Datei liegt weiterhin am ursprünglichen Ort: {path}')
    return receipt


def check_delete_access(path):
    if os.name!='nt':return
    import ctypes
    from ctypes import wintypes
    create=ctypes.windll.kernel32.CreateFileW
    create.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE)
    create.restype=wintypes.HANDLE
    # Open only to test delete sharing/ACL; no DELETE_ON_CLOSE or data writes.
    handle=create(str(path),0x10000,7,None,3,0x02000000|0x00200000,None)
    if handle==ctypes.c_void_p(-1).value:
        raise OSError(f'Die Datei ist gesperrt oder nicht zum Löschen freigegeben: {path}')
    close=ctypes.windll.kernel32.CloseHandle;close.argtypes=(wintypes.HANDLE,);close.restype=wintypes.BOOL
    close(handle)


def clean_search_index(state,identifiers):
    index=state/'transcript-search.sqlite3'
    if index.exists():
        fingerprint(index)
        with closing(sqlite3.connect(index)) as search:
            marks=','.join('?' for _ in identifiers)
            paths=[row[0] for row in search.execute(f'SELECT path FROM job_files WHERE job_id IN ({marks})',identifiers)]
            with search:
                search.execute(f'DELETE FROM job_files WHERE job_id IN ({marks})',identifiers)
                for path in paths:
                    search.execute('DELETE FROM transcript_fts WHERE rowid IN (SELECT id FROM files WHERE path=? AND NOT EXISTS(SELECT 1 FROM job_files WHERE job_files.path=files.path))',(path,))
                    search.execute('DELETE FROM files WHERE path=? AND NOT EXISTS(SELECT 1 FROM job_files WHERE job_files.path=files.path)',(path,))
    for path in [state/'content-search-result.json',*state.glob('.search-*')]:
        if path.exists():
            fingerprint(path)
            if path.resolve().parent!=state:raise ValueError('Ungültiger lokaler Suchpfad.')
            path.unlink()


def execute(db,state,token,*,keep_original=False,trash=native_trash):
    state=state.resolve()
    with search_storage_lock(state):
        db.execute('BEGIN IMMEDIATE')
        try:
            plan=load(state,token)
            if plan['confirmed'] and keep_original!=plan.get('keepOriginal',False):
                raise ValueError('Beim Fortsetzen gilt die bereits bestätigte Auswahl für die Originaldatei.')
            current=selected_rows(selected_groups(rows(db),selection_for(plan)))
            if current!=plan['rows']:raise ValueError('Der Datensatz hat sich geändert. Bitte Löschbestätigung erneut öffnen.')
            identifiers=[row['id'] for row in current]
            if overlapping_plan(state,set(identifiers),skip=token):
                raise ValueError('Ein Teil der Auswahl gehört zu einer begonnenen Löschung. Bitte die Löschbestätigung erneut öffnen.')
            if keep_original:
                for file in plan['files']:
                    if file['role']=='original' and file['status']=='pending':
                        file['status']='retained'
            # Validate the entire batch before the first OS operation.
            for file in plan['files']:
                path=Path(file['path']);check_network(path)
                if file['status']=='protected':continue
                if str(path.resolve(strict=False))!=file['canonical']:raise ValueError('Ein Dateipfad hat sich geändert.')
                if plan['confirmed'] and file['status']=='pending' and not path.exists():
                    file['status']='missing'
                if file['status'] in ('missing','trashed'):
                    if path.exists():raise ValueError(f'Am früheren Ort liegt eine neue Datei; sie wird nicht gelöscht: {path}')
                elif fingerprint(path,directory=file['role']=='cache')!=file['identity']:
                    raise ValueError(f'Die Datei hat sich seit der Bestätigung geändert: {path}')
                elif file['status']=='pending':check_delete_access(path)
            plan.update(confirmed=True,keepOriginal=keep_original)
            save(state,plan)
            for file in plan['files']:
                if file['status']!='pending':continue
                path=Path(file['path'])
                if fingerprint(path,directory=file['role']=='cache')!=file['identity']:raise ValueError('Eine Datei wurde während des Löschens verändert.')
                file['receipt']=trash(path);file['status']='trashed';save(state,plan)
            marks=','.join('?' for _ in identifiers)
            clean_search_index(state,identifiers)
            db.execute(f'UPDATE known_results SET prior_job_id=NULL WHERE prior_job_id IN ({marks}) AND job_id NOT IN ({marks})',identifiers+identifiers)
            for table in ('events','transcription_measurements','audio_durations','speaker_diarization','copy_exports',
                          'copy_claims','job_retries','queue_positions','cancel_requests','preemptions','immediate_jobs','known_results'):
                db.execute(f'DELETE FROM {table} WHERE job_id IN ({marks})',identifiers)
            db.execute('DELETE FROM drop_batches')
            db.execute(f'DELETE FROM jobs WHERE id IN ({marks})',identifiers)
            db.executemany(
                'INSERT OR REPLACE INTO retained_media(source,size,mtime_ns) VALUES (?,?,?)',
                (
                    (media_path_key(path), *file['identity'][2:4])
                    for file in plan['files'] if file['status']=='retained'
                    for path in file.get('paths',(file['path'],file['canonical']))
                ),
            )
            db.execute('UPDATE storage_state SET generation=generation+1 WHERE id=1')
            db.commit()
        except BaseException as error:
            db.rollback()
            if 'plan' in locals() and any(f['status']=='trashed' for f in plan['files']):
                raise RuntimeError('Löschen noch nicht vollständig abgeschlossen. Bereits verschobene Dateien liegen im Papierkorb; die Datenbankeinträge bleiben erhalten. Erneut „Datensatz löschen“ wählen, um fortzusetzen. '+str(error)) from error
            raise
    journal_path(state,token).unlink(missing_ok=True)
    return dict(deletedIds=identifiers,trashed=sum(f['status']=='trashed' for f in plan['files']))
