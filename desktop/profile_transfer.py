"""Portable, checked profile archives. No pickle, executable payloads or extractall.

SQLite's backup API snapshots WAL databases even while transcription continues.
Restore is staged, paused and journalled; the caller stops owned processes first.
"""
from contextlib import closing, contextmanager, ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import sqlite3
import tempfile
import uuid
import zipfile

FORMAT = 'VoxDrop backup'
VERSION = 1
COMPONENTS = ('settings', 'databases', 'models', 'media')
DEFAULT_OPTIONS = dict(settings=True, databases=True, models=False, media=False)
MEDIA_SUFFIXES = {'.wav', '.mp3', '.m4a', '.mp4', '.mkv', '.mov', '.aac', '.flac', '.ogg', '.opus', '.wma', '.webm', '.avi', '.flv', '.m4v', '.aiff', '.aif', '.txt'}
JOURNAL = '.migration-journal.json'


class TransferCancelled(RuntimeError):
    pass


def check(cancel):
    if cancel is not None and cancel.is_set():
        raise TransferCancelled('Übertragung abgebrochen. Der vorherige Stand bleibt erhalten.')


def digest(path, cancel=None):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            check(cancel)
            result.update(block)
    return result.hexdigest()


def write_json(path, data):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name != 'nt':
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Ungültiger Dateipfad in der Sicherung.')
    path = PurePosixPath(value)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    if path.is_absolute() or str(path) != value or any(
            part in ('.', '..') or part.rstrip(' .') != part or part.split('.')[0].upper() in reserved
            or any(ord(c) < 32 for c in part) for part in path.parts):
        raise ValueError('Unsicherer Dateipfad in der Sicherung.')
    return path


def portable_path(value):
    return PureWindowsPath(value) if '\\' in value or PureWindowsPath(value).drive else PurePosixPath(value)


def remap_path(value, mappings):
    if not value:
        return value
    original = portable_path(value)
    for old, new in sorted(mappings.items(), key=lambda item: len(item[0]), reverse=True):
        if not new or old == new:
            continue
        root = portable_path(old)
        if type(root) is not type(original):
            continue
        try:
            relative = original.relative_to(root)
        except ValueError:
            continue
        return str(Path(new).joinpath(*relative.parts))
    return value


def remap_settings(settings, mappings, hardware):
    result = dict(settings)
    for key in ('input_dir', 'completed_dir', 'watch_path', 'scope_dir', 'source_parent'):
        if result.get(key):
            result[key] = remap_path(result[key], mappings)
    if 'folders' in result:
        result['folders'] = [remap_path(p, mappings) for p in result['folders']]
    if 'folder_options' in result:
        result['folder_options'] = {remap_path(p, mappings): choice for p, choice in result['folder_options'].items()}
    if result.get('hardware') in ('metal', 'cuda'):
        result['hardware'] = hardware
    return result


def read_database(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)


def validate_database(path):
    with closing(read_database(path)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Die gesicherte Datenbank ist beschädigt oder unvollständig.')
        if path.name == 'jobs.sqlite3':
            columns = {r[1] for r in db.execute('PRAGMA table_info(jobs)')}
            if not {'id', 'source', 'completed_dir', 'state', 'settings', 'publication_started', 'mtime_ns'}.issubset(columns):
                raise ValueError('Die Auftragsdatenbank passt nicht zu dieser VoxDrop-Version.')


def snapshot_database(source, target, cancel):
    with closing(read_database(source)) as source_db, closing(sqlite3.connect(target)) as target_db:
        source_db.backup(target_db, pages=256, progress=lambda *_: check(cancel), sleep=.05)
    validate_database(target)


def profile_files(profile):
    return [(name, profile / name) for name in ('config.json', 'layout.ini') if (profile / name).is_file()]


def media_inventory(config, database):
    """Walk only explicitly selected watch roots; history adds exact referenced files."""
    roots = list(config.get('folders', []))
    exact = set()
    if database.is_file():
        with closing(read_database(database)) as db:
            db.row_factory = sqlite3.Row
            for job in db.execute('SELECT * FROM jobs'):
                source = Path(job['source'])
                output = Path(job['completed_dir']) / source.name
                exact.update((source, output))
                transcript = output.with_suffix('.txt')
                if job['origin_job_id']:
                    name = f'{output.stem} (Neu {job["id"]}).txt'
                    transcript = output.with_name(name if len(name.encode('utf-8')) <= 255 else f'Neutranskription {job["id"]}.txt')
                exact.add(transcript)
            for row in db.execute('SELECT transcript_path FROM known_results WHERE transcript_path IS NOT NULL'):
                exact.add(Path(row[0]))
    roots += [str(p.parent) for p in exact]
    unique = []
    for root in sorted(set(roots), key=len):
        if not any(Path(root).is_relative_to(Path(p)) for p in unique):
            unique.append(root)
    records = [dict(source=p, directory=f'{i + 1:04d}-' + (re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', portable_path(p).name).rstrip(' .') or 'Dateien'))
               for i, p in enumerate(unique)]
    return records, exact


def tree_files(root, cancel):
    if not root.is_dir():
        return
    for folder, dirs, files in os.walk(root, followlinks=False):
        check(cancel)
        dirs[:] = [name for name in dirs if not name.startswith('.') and not (Path(folder) / name).is_symlink()]
        for name in sorted(files):
            path = Path(folder) / name
            if not name.startswith('.') and path.is_file():
                yield path


def export_backup(profile, models, destination, options=None, *, cancel=None, progress=lambda text: None):
    options = {**DEFAULT_OPTIONS, **(options or {})}
    if not any(options.get(key) for key in COMPONENTS):
        raise ValueError('Bitte mindestens einen Bestandteil auswählen.')
    profile, models, destination = map(Path, (profile, models, destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.voxdrop-export-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        entries = []
        config = json.loads((profile / 'config.json').read_text(encoding='utf-8')) if (profile / 'config.json').is_file() else {}
        if options['settings']:
            entries.extend(('settings', name, path) for name, path in profile_files(profile))
        job_snapshot = stage / 'jobs.sqlite3'
        if options['databases'] or options['media']:
            for source in sorted((profile / 'service').glob('*.sqlite3')):
                if source.name.startswith('.'):
                    continue
                check(cancel)
                progress('Datenbank wird konsistent gesichert: ' + source.name)
                target = stage / source.name
                snapshot_database(source, target, cancel)
                if options['databases']:
                    entries.append(('databases', 'service/' + source.name, target))
        roots, exact = media_inventory(config, job_snapshot)
        missing = []
        if options['media']:
            files = set(exact)
            for root in config.get('folders', []):
                if not Path(root).is_dir():
                    missing.append(root)
                files.update(p for p in tree_files(Path(root), cancel) if p.suffix.lower() in MEDIA_SUFFIXES)
            for source in sorted(files):
                if not source.is_file():
                    # A historical original can have been moved to its output folder.
                    continue
                for root in roots:
                    if source.is_relative_to(Path(root['source'])):
                        entries.append(('media', root['directory'] + '/' + source.relative_to(root['source']).as_posix(), source))
                        break
        if options['models']:
            if models == profile or profile.is_relative_to(models):
                raise ValueError('Modellspeicher und Benutzerprofil müssen getrennte Ordner sein.')
            if not models.is_dir():
                raise ValueError('Der Modellspeicher ist noch nicht vorhanden.')
            for source in tree_files(models, cancel):
                relative = source.relative_to(models)
                if relative.parts[0] not in ('models', 'huggingface') or 'logs' in relative.parts or 'xet' in relative.parts or source.name in ('token', 'stored_tokens'):
                    continue
                if not source.resolve().is_relative_to(models.resolve()):
                    raise ValueError('Eine Modellverknüpfung liegt außerhalb des Modellspeichers.')
                entries.append(('models', relative.as_posix(), source))
        manifest = dict(format=FORMAT, version=VERSION, created=datetime.now(timezone.utc).isoformat(),
                        platform=os.sys.platform, options=options, media_roots=roots, missing_folders=missing,
                        folders=config.get('folders', []), files=[], jobs=0)
        if job_snapshot.is_file():
            with closing(read_database(job_snapshot)) as db:
                manifest['jobs'] = db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        output = stage / 'archive.zip'
        blobs = set()
        with zipfile.ZipFile(output, 'w', allowZip64=True) as archive:
            for number, (area, name, source) in enumerate(entries, 1):
                check(cancel)
                safe_relative(name)
                if source.is_symlink() and area != 'models':
                    raise ValueError('Verknüpfte Mediendateien bitte über ihren Originalordner sichern.')
                if area == 'media':
                    from platform_io import file_is_being_written
                    if file_is_being_written(source):
                        raise ValueError('Eine Aufnahme wird noch geschrieben. Bitte die Sicherung nach Abschluss wiederholen.')
                progress(f'Sicherung: {number} / {len(entries)} Dateien · {source.name}')
                before = source.stat()
                sha = digest(source, cancel)
                blob = 'blobs/' + sha
                if sha not in blobs:
                    copied = hashlib.sha256()
                    with source.open('rb') as reader, archive.open(blob, 'w', force_zip64=True) as writer:
                        while block := reader.read(1024 * 1024):
                            check(cancel)
                            writer.write(block); copied.update(block)
                    if copied.hexdigest() != sha:
                        raise ValueError('Eine Datei wurde während der Sicherung verändert. Bitte erneut sichern.')
                    blobs.add(sha)
                after = source.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('Eine Datei wurde während der Sicherung verändert. Bitte erneut sichern.')
                manifest['files'].append(dict(area=area, path=name, size=before.st_size, mtime_ns=before.st_mtime_ns, sha256=sha))
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        check(cancel)
        with output.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(output, destination)
    return manifest


def inspect_backup(path):
    try:
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist()) > 250000 or archive.getinfo('manifest.json').file_size > 32 * 1024 * 1024:
                raise ValueError('Die Sicherung enthält zu viele Einträge.')
            data = json.loads(archive.read('manifest.json'))
            if data.get('format') != FORMAT or data.get('version') != VERSION:
                raise ValueError('Diese Datei ist keine unterstützte VoxDrop-Sicherung.')
            if len({i.filename for i in archive.infolist()}) != len(archive.infolist()):
                raise ValueError('Die Sicherung enthält doppelte ZIP-Einträge.')
            targets = set()
            for item in data['files']:
                safe_relative(item['path'])
                key = (item['area'], item['path'].casefold())
                sha = item['sha256']
                if item['area'] not in COMPONENTS or key in targets or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
                    raise ValueError('Ungültige oder doppelte Einträge in der Sicherung.')
                targets.add(key)
                if item['area'] == 'settings' and item['path'] not in ('config.json', 'layout.ini'):
                    raise ValueError('Unbekannte Einstellungsdatei in der Sicherung.')
                if item['area'] == 'databases' and (len(PurePosixPath(item['path']).parts) != 2 or not item['path'].startswith('service/') or not item['path'].endswith('.sqlite3')):
                    raise ValueError('Ungültiger Datenbankpfad in der Sicherung.')
                if item['area'] == 'models' and PurePosixPath(item['path']).name in ('token', 'stored_tokens'):
                    raise ValueError('Anmeldedaten gehören nicht in ein Modellarchiv.')
                if archive.getinfo('blobs/' + sha).file_size != item['size'] or item['size'] < 0:
                    raise ValueError('Die Sicherung ist unvollständig.')
            if len({r['directory'] for r in data['media_roots']}) != len(data['media_roots']):
                raise ValueError('Doppelte Medienordner in der Sicherung.')
            for root in data['media_roots']:
                if len(safe_relative(root['directory']).parts) != 1 or not isinstance(root['source'], str):
                    raise ValueError('Ungültige Medienzuordnung.')
            allowed = {'manifest.json', *('blobs/' + item['sha256'] for item in data['files'])}
            if set(archive.namelist()) != allowed:
                raise ValueError('Die Sicherung enthält unbekannte Dateien.')
            data['bytes'] = sum(i['size'] for i in data['files'])
            data['available'] = {key: any(i['area'] == key for i in data['files']) for key in COMPONENTS}
            return data
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Die Datei ist keine vollständige VoxDrop-Sicherung.') from error


def prepare_database(path, mappings, hardware, media_versions=None):
    if path.name != 'jobs.sqlite3':
        # The index keeps FTS content. Remap its path keys as well.
        with closing(sqlite3.connect(path)) as db, db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('files', 'job_files'):
                if table in tables:
                    for rowid, value in db.execute(f'SELECT rowid,path FROM {table}').fetchall():
                        db.execute(f'UPDATE {table} SET path=? WHERE rowid=?', (remap_path(value, mappings), rowid))
        return
    with closing(sqlite3.connect(path)) as db, db:
        for identifier, source, completed, settings in db.execute('SELECT id,source,completed_dir,settings FROM jobs').fetchall():
            source = remap_path(source, mappings)
            db.execute('UPDATE jobs SET source=?,completed_dir=?,settings=? WHERE id=?',
                       (source, remap_path(completed, mappings),
                        json.dumps(remap_settings(json.loads(settings), mappings, hardware), ensure_ascii=False), identifier))
            if source in (media_versions or {}):
                old_size, old_mtime, new_size, new_mtime = media_versions[source]
                db.execute('UPDATE jobs SET size=?,mtime_ns=? WHERE id=? AND size=? AND mtime_ns=?',
                           (new_size, new_mtime, identifier, old_size, old_mtime))
        for table, column in (('known_results', 'transcript_path'), ('copy_exports', 'retirement_dir'), ('copy_claims', 'path')):
            for rowid, value in db.execute(f'SELECT rowid,{column} FROM {table}').fetchall():
                db.execute(f'UPDATE {table} SET {column}=? WHERE rowid=?', (remap_path(value, mappings), rowid))
        db.execute('UPDATE queue_state SET paused=1')
        db.execute('UPDATE app_control SET stop_requested=0,owner_pid=NULL,owner_created=NULL')
        db.execute("UPDATE jobs SET state=CASE WHEN publication_started THEN 'blocked' ELSE 'ready' END,"
                   "phase=NULL,progress=NULL,finished=NULL,error='Import: unterbrochener Auftrag; Ausgabe vor Wiederholung prüfen.' "
                   "WHERE state IN ('copying','transcribing','exporting')")
        for table in ('immediate_jobs', 'drop_batches', 'folder_status', 'folder_refresh', 'connection', 'service', 'preemptions', 'cancel_requests'):
            db.execute(f'DELETE FROM {table}')
        db.execute('UPDATE storage_state SET generation=generation+1')
    validate_database(path)


def remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def recover_interrupted(profile):
    """A journal is written before the first replacement, never after it."""
    journal = Path(profile) / JOURNAL
    if not journal.is_file():
        return
    data = json.loads(journal.read_text(encoding='utf-8'))
    if data['status'] != 'committed':
        for op in reversed(data['operations']):
            target, backup = Path(op['target']), Path(op['backup'])
            staged = Path(op['staged']) if op['staged'] else None
            if backup.exists():
                remove(target)
                os.replace(backup, target)
            elif not op['existed'] and staged and not staged.exists():
                remove(target)
    journal.unlink()


@contextmanager
def stopped_profile(profile):
    from platform_io import lock_service
    state = profile / 'service'
    state.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for name in ('app-control.lock', 'supervisor.lock', 'service.lock', 'transcript-search.lock'):
            stream = stack.enter_context((state / name).open('a'))
            try:
                lock_service(stream)
            except BlockingIOError as error:
                raise RuntimeError('Überwachung oder Detailsuche läuft noch. Bitte erst beenden.') from error
        yield


def restore_backup(profile, models, archive_path, options, *, media_destination=None, mappings=None,
                   hardware='cpu', cancel=None, progress=lambda text: None):
    profile, models = Path(profile).resolve(), Path(models).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    data = inspect_backup(archive_path)
    options = {key: bool(options.get(key) and data['available'][key]) for key in COMPONENTS}
    if not any(options.values()):
        raise ValueError('Bitte mindestens einen vorhandenen Bestandteil auswählen.')
    mappings = dict(mappings or {})
    if len({str(Path(p).absolute()).casefold() for p in mappings.values() if p}) != len([p for p in mappings.values() if p]):
        raise ValueError('Bitte unterschiedliche Zielordner für die Pfadzuordnung verwenden.')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    transaction = profile.parent / ('VoxDrop-vor-Import-' + stamp)
    transaction.mkdir(mode=0o700)
    stage = transaction / 'staged'; stage.mkdir()
    extra_stages = []
    operations = []
    def operation(target, staged=None):
        target = Path(target)
        if target.is_symlink():
            raise ValueError('Der Import ersetzt keine verknüpften Zielpfade.')
        backup = target.parent / ('.voxdrop-vor-import-' + stamp + '-' + target.name)
        if target.is_relative_to(profile) and target != models:
            backup = transaction / 'previous' / target.relative_to(profile)
            backup.parent.mkdir(parents=True, exist_ok=True)
        operations.append(dict(target=str(target), staged=str(staged) if staged else None,
                               backup=str(backup), existed=target.exists()))
    try:
        selected = [item for item in data['files'] if options[item['area']]]
        model_stage = None
        if options['models']:
            if models == profile or profile.is_relative_to(models):
                raise ValueError('Modellspeicher und Benutzerprofil müssen getrennte Ordner sein.')
            models.parent.mkdir(parents=True, exist_ok=True)
            model_stage = Path(tempfile.mkdtemp(prefix='.voxdrop-model-import-', dir=models.parent)); extra_stages.append(model_stage)
        media_stage = media_target = None
        if options['media']:
            if not media_destination:
                raise ValueError('Bitte einen Zielordner für Aufnahmen und TXT auswählen.')
            media_destination = Path(media_destination).expanduser().resolve()
            media_destination.mkdir(parents=True, exist_ok=True)
            media_target = media_destination / ('VoxDrop-Import-' + stamp)
            if media_target.exists():
                raise FileExistsError('Der neue Importordner ist bereits vorhanden.')
            media_stage = Path(tempfile.mkdtemp(prefix='.voxdrop-media-import-', dir=media_destination)); extra_stages.append(media_stage)
            automatic = {root['source']: str(media_target / root['directory']) for root in data['media_roots']}
            mappings = {old: remap_path(old, automatic) for old in mappings}
            mappings.update(automatic)
        if options['settings'] or options['databases']:
            for old, new in mappings.items():
                if not new or not Path(new).is_absolute():
                    raise ValueError('Bitte die bisherigen Ordner zuerst absoluten Zielpfaden auf diesem Gerät zuordnen.')
        if options['models'] and data['platform'] != os.sys.platform:
            raise ValueError('Modelle dieser Plattform sind nicht kompatibel. Bitte Modelle auf dem Zielgerät neu einrichten.')
        required = sum(item['size'] for item in selected)
        if shutil.disk_usage(stage).free < sum(i['size'] for i in selected if i['area'] in ('settings', 'databases')) + 1024 * 1024:
            raise OSError('Zu wenig freier Speicher für den App-Datenimport.')
        for area, folder in (('models', model_stage), ('media', media_stage)):
            if folder and shutil.disk_usage(folder).free < sum(i['size'] for i in selected if i['area'] == area) + 1024 * 1024:
                raise OSError('Zu wenig freier Speicher für ' + area + '.')
        media_versions = {}
        model_blobs = {}
        with zipfile.ZipFile(archive_path) as archive:
            for number, item in enumerate(selected, 1):
                check(cancel)
                progress(f'Prüfen und vorbereiten: {number} / {len(selected)} Dateien')
                base = model_stage if item['area'] == 'models' else media_stage if item['area'] == 'media' else stage
                target = base / item['path']; target.parent.mkdir(parents=True, exist_ok=True)
                if item['area'] == 'models' and item['sha256'] in model_blobs:
                    try:
                        os.link(model_blobs[item['sha256']], target)
                        continue
                    except OSError:
                        pass  # Filesystems without hard links receive ordinary copies.
                hasher = hashlib.sha256()
                with archive.open('blobs/' + item['sha256']) as reader, target.open('xb') as writer:
                    while block := reader.read(1024 * 1024):
                        check(cancel); writer.write(block); hasher.update(block)
                    writer.flush(); os.fsync(writer.fileno())
                if hasher.hexdigest() != item['sha256']:
                    raise ValueError('Prüfsumme stimmt nicht. Der bisherige Stand bleibt erhalten.')
                os.utime(target, ns=(item['mtime_ns'], item['mtime_ns']))
                if item['area'] == 'media':
                    metadata = target.stat()
                    media_versions[str(media_target / item['path'])] = (item['size'], item['mtime_ns'], metadata.st_size, metadata.st_mtime_ns)
                if item['area'] == 'databases':
                    validate_database(target)
                if item['area'] == 'models':
                    model_blobs[item['sha256']] = target
        config = stage / 'config.json'
        if not config.is_file() and (profile / 'config.json').is_file():
            shutil.copy2(profile / 'config.json', config)
        if config.is_file():
            settings = remap_settings(json.loads(config.read_text(encoding='utf-8')), mappings if options['settings'] else {}, hardware)
            settings['monitoring'] = False
            write_json(config, settings)
            operation(profile / 'config.json', config)
        if (stage / 'layout.ini').is_file():
            operation(profile / 'layout.ini', stage / 'layout.ini')
        if options['databases']:
            new_databases = {p.name for p in (stage / 'service').glob('*.sqlite3')}
            for path in sorted((stage / 'service').glob('*.sqlite3')):
                prepare_database(path, mappings, hardware, media_versions)
                operation(profile / 'service' / path.name, path)
            # Never leave an old index/SQLite WAL against an imported database.
            for old in (profile / 'service').glob('*.sqlite3*'):
                if not old.name.startswith('.') and old.name not in new_databases:
                    operation(old)
            for name in ('jobs', 'content-search-result.json'):
                if (profile / 'service' / name).exists():
                    operation(profile / 'service' / name)
        else:
            # Even a settings/model-only import must not restart an existing queue.
            current = profile / 'service/jobs.sqlite3'
            if current.is_file():
                paused = stage / 'paused/jobs.sqlite3'; paused.parent.mkdir()
                snapshot_database(current, paused, cancel)
                with closing(sqlite3.connect(paused)) as db, db:
                    db.execute('UPDATE queue_state SET paused=1')
                    db.execute('DELETE FROM immediate_jobs')
                    db.execute('UPDATE app_control SET stop_requested=0,owner_pid=NULL,owner_created=NULL')
                operation(current, paused)
                for suffix in ('-wal', '-shm'):
                    if current.with_name(current.name + suffix).exists():
                        operation(current.with_name(current.name + suffix))
        if config.is_file():
            from watch_service import read_settings
            read_settings(config)
        if model_stage:
            # Keep this device's credentials; source-machine tokens are excluded.
            for name in ('token', 'stored_tokens'):
                existing = models / 'huggingface' / name
                if existing.is_file() and not existing.is_symlink():
                    target = model_stage / 'huggingface' / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(existing, target)
            operation(models, model_stage)
        if media_stage:
            operation(media_target, media_stage)
        with stopped_profile(profile):
            # Backups contain fresh app data even when only models/media are imported.
            progress('Vorherige Einstellungen und Datenbanken werden gesichert …')
            export_backup(profile, models, transaction / 'Vor-dem-Import.voxdrop.zip',
                          dict(settings=True, databases=True, models=False, media=False), cancel=cancel)
            check(cancel)
            journal = profile / JOURNAL
            if journal.exists():
                raise RuntimeError('Ein vorheriger Import muss zuerst wiederhergestellt werden.')
            journal_data = dict(status='applying', operations=operations)
            write_json(transaction / 'Wiederherstellung.json', dict(operations=operations, media_directory=str(media_target) if media_target else None))
            write_json(journal, journal_data)
            try:
                for op in operations:
                    target = Path(op['target']); target.parent.mkdir(parents=True, exist_ok=True)
                    if op['existed']:
                        os.replace(target, op['backup'])
                    if op['staged']:
                        os.replace(op['staged'], target)
                journal_data['status'] = 'committed'; write_json(journal, journal_data)
            except BaseException:
                recover_interrupted(profile)
                raise
            recover_interrupted(profile)
        model_backup = next((op['backup'] for op in operations if op['target'] == str(models) and op['existed']), None)
        return dict(backup=str(transaction / 'Vor-dem-Import.voxdrop.zip'), media_directory=str(media_target) if media_target else None, model_backup=model_backup,
                    mappings=mappings, files=len(selected), bytes=required)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        for folder in extra_stages:
            shutil.rmtree(folder, ignore_errors=True)
