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

from history_store import history_category, search_storage_lock
from platform_io import is_reparse_point, open_regular
from smb_paths import on_network_volume

ACTIVE={'copying','transcribing','exporting'}


def key(path):return os.path.normcase(os.path.abspath(path))


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


def group(all_rows,identifier):
    by_id={row['id']:row for row in all_rows}
    if identifier not in by_id:raise ValueError('Der Datensatz ist nicht mehr vorhanden.')
    selected=by_id[identifier]
    if history_category(selected) is None:raise ValueError('Nur abgeschlossene Verlaufseinträge können gelöscht werden.')
    root=selected;seen=set()
    while root['origin_job_id'] in by_id:
        if root['id'] in seen:raise ValueError('Die Verknüpfungen dieser Aufnahme sind ungültig.')
        seen.add(root['id']);root=by_id[root['origin_job_id']]
    identifiers={root['id'],identifier}
    paths={key(path) for job in (root,selected) for path in media_paths(job)}
    texts={key(text_path(job)) for job in (root,selected)}
    # Include aliases of this root, without probing every unrelated library path.
    for path in media_paths(selected):
        try:paths.add(key(path.resolve(strict=True)))
        except FileNotFoundError:pass
    while True:
        previous=set(identifiers)
        for row in all_rows:
            if row['origin_job_id'] in identifiers or key(text_path(row)) in texts or any(key(p) in paths for p in media_paths(row)):
                identifiers.add(row['id'])
                paths.update(key(p) for p in media_paths(row));texts.add(key(text_path(row)))
        if previous==identifiers:break
    found=[row for row in all_rows if row['id'] in identifiers]
    if any(row['state'] in ACTIVE for row in found):
        raise ValueError('Für diese Originaldatei läuft noch eine Verarbeitung. Bitte zuerst fertigstellen oder stoppen.')
    return found


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
        raise ValueError('Löschen auf Netzlaufwerken ist deaktiviert: Dort steht kein verlässlich nutzbarer Betriebssystem-Papierkorb bereit. Dateien und Datensatz bleiben erhalten.')


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
    return dict(token=plan['token'],jobId=plan['selected'],name=plan['name'],recordCount=len(plan['rows']),
        files=[dict(path=f['path'],role=f['role'],missing=f['status']=='missing',trashed=f['status']=='trashed',protected=f['status']=='protected') for f in plan['files']],
        partial=any(f['status']=='trashed' for f in plan['files']))


def prepare(db,state,identifier):
    state=state.resolve();all_rows=rows(db)
    initial=next((row for row in all_rows if row['id']==identifier),None)
    if initial is None:raise ValueError('Der Datensatz ist nicht mehr vorhanden.')
    for path in [*media_paths(initial),text_path(initial)]:check_network(path)
    selected=group(all_rows,identifier)
    # A failed multi-file operation keeps its receipts and can be resumed explicitly.
    folder=state/'record-delete'
    if folder.is_dir() and not folder.is_symlink() and not is_reparse_point(folder.lstat()):
        for candidate in folder.glob('*.json'):
            old=load(state,candidate.stem)
            if old['selected']==identifier and old.get('confirmed'):
                if old['rows']!=selected:raise ValueError('Der Datensatz hat sich seit dem begonnenen Löschen geändert. Bitte die bereits verschobenen Dateien im Papierkorb prüfen.')
                for file in old['files']:
                    if file['status']=='pending' and not Path(file['path']).exists():
                        file['status']='missing'
                save(state,old)
                return public(old)
    files={};originals={};owners={}
    for job in selected:
        from voxdrop import MEDIA_EXTENSIONS
        if Path(job['source']).suffix.casefold() not in MEDIA_EXTENSIONS:
            raise ValueError('Die gespeicherte Originaldatei ist keine unterstützte Mediendatei.')
        for path in media_paths(job):
            file=snapshot_file(path,'original')
            if file['identity'] is None:continue
            if Path(file['canonical']).is_relative_to(state):raise ValueError('Die Originaldatei verweist auf interne Arbeitsdaten.')
            filekey=key(file['canonical']);originals[filekey]=file;owners.setdefault(filekey,[]).append(job)
        text=text_path(job)
        if text.suffix.casefold()!='.txt':raise ValueError('Der gespeicherte Transkriptpfad ist keine TXT-Datei.')
        file=snapshot_file(text,'transcript');files.setdefault(key(file['canonical']),file)
        cache=state/'jobs'/str(job['id'])
        if cache.exists() or cache.is_symlink():
            file=snapshot_file(cache,'cache');files.setdefault(key(file['canonical']),file)
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
        raise ValueError('Am gespeicherten Ort liegt inzwischen eine andere oder geänderte Originaldatei. Es wurde nichts gelöscht.')
    if not originals:
        for job in selected:
            file=snapshot_file(media_paths(job)[0],'original');files.setdefault(key(file['canonical']),file)
    plan=dict(schema=1,token=uuid.uuid4().hex,created=time.time(),selected=identifier,
        name=Path(next(row for row in selected if row['id']==identifier)['source']).name,rows=selected,
        files=sorted(files.values(),key=lambda file:{'original':0,'transcript':1,'cache':2}[file['role']]),confirmed=False)
    save(state,plan)
    return public(plan)


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


def execute(db,state,token,*,trash=native_trash):
    state=state.resolve()
    with search_storage_lock(state):
        db.execute('BEGIN IMMEDIATE')
        try:
            plan=load(state,token)
            current=group(rows(db),plan['selected'])
            if current!=plan['rows']:raise ValueError('Der Datensatz hat sich geändert. Bitte Löschbestätigung erneut öffnen.')
            # Validate the entire batch before the first OS operation.
            for file in plan['files']:
                path=Path(file['path']);check_network(path)
                if file['status']=='protected':continue
                if str(path.resolve(strict=False))!=file['canonical']:raise ValueError('Ein Dateipfad hat sich geändert.')
                if file['status'] in ('missing','trashed'):
                    if path.exists():raise ValueError(f'Am früheren Ort liegt eine neue Datei; sie wird nicht gelöscht: {path}')
                elif fingerprint(path,directory=file['role']=='cache')!=file['identity']:
                    raise ValueError(f'Die Datei hat sich seit der Bestätigung geändert: {path}')
                else:check_delete_access(path)
            plan['confirmed']=True;save(state,plan)
            for file in plan['files']:
                if file['status']!='pending':continue
                path=Path(file['path'])
                if fingerprint(path,directory=file['role']=='cache')!=file['identity']:raise ValueError('Eine Datei wurde während des Löschens verändert.')
                file['receipt']=trash(path);file['status']='trashed';save(state,plan)
            identifiers=[row['id'] for row in current];marks=','.join('?' for _ in identifiers)
            clean_search_index(state,identifiers)
            db.execute(f'UPDATE known_results SET prior_job_id=NULL WHERE prior_job_id IN ({marks}) AND job_id NOT IN ({marks})',identifiers+identifiers)
            for table in ('events','transcription_measurements','audio_durations','speaker_diarization','copy_exports',
                          'copy_claims','job_retries','queue_positions','cancel_requests','preemptions','immediate_jobs','known_results'):
                db.execute(f'DELETE FROM {table} WHERE job_id IN ({marks})',identifiers)
            db.execute('DELETE FROM drop_batches')
            db.execute(f'DELETE FROM jobs WHERE id IN ({marks})',identifiers)
            db.execute('UPDATE storage_state SET generation=generation+1 WHERE id=1')
            db.commit()
        except BaseException as error:
            db.rollback()
            if 'plan' in locals() and any(f['status']=='trashed' for f in plan['files']):
                raise RuntimeError('Löschen noch nicht vollständig abgeschlossen. Bereits verschobene Dateien liegen im Papierkorb; die Datenbankeinträge bleiben erhalten. Erneut „Datensatz löschen“ wählen, um fortzusetzen. '+str(error)) from error
            raise
    journal_path(state,token).unlink(missing_ok=True)
    return dict(deletedIds=identifiers,trashed=sum(f['status']=='trashed' for f in plan['files']))
