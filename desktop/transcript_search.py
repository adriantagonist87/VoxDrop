"""On-demand, cancellable local transcript indexing. No files are read at startup."""

from contextlib import closing
import fnmatch
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
from queue import Empty, Queue
from threading import Event, Thread
import time
import uuid

_engine=Path(__file__).resolve().parents[1]/'Engine'
sys.path.append(str(_engine if _engine.is_dir() else _engine.parent))
from history_store import TRANSCRIPT_SCOPE, history_category, search_storage_lock, storage_generation

MAX_FILE_BYTES = 32 * 1024 * 1024


class SearchCancelled(Exception):
    pass


def transcript_path(job):
    source = Path(job['source'])
    if job.get('result_kind') in ('existing', 'duplicate'):
        return Path(job['known_transcript_path']) if job.get('known_transcript_path') else source.with_suffix('.txt')
    media = Path(job['completed_dir']) / source.name
    if job.get('origin_job_id'):
        name = f"{media.stem} (Neu {job['id']}).txt"
        return media.with_name(name if len(name.encode('utf-8')) <= 255 else f"Neutranskription {job['id']}.txt")
    return media.with_suffix('.txt')


def path_matches(path, query):
    # Escape everything except the two documented wildcards. A plain term is a substring.
    pattern = query.strip().replace('\\', '/').casefold().replace('[', '[[]')
    return fnmatch.fnmatchcase(str(path).replace('\\', '/').casefold(), '*' + pattern + '*')


def content_expression(query):
    words = re.findall(r'[^\W_]+\*?', query.casefold())
    if not words:
        raise ValueError('Für die Detailsuche bitte mindestens ein Wort eingeben.')
    return ' AND '.join('"' + word.rstrip('*') + '"' + ('*' if word.endswith('*') else '')
                        for word in words)


def search_transcripts(job_database, index_database, result_file, query, path_for_job,
                       cancelled, progress=lambda text: None):
    with search_storage_lock(Path(job_database).parent):
        return _search_transcripts(job_database,index_database,result_file,query,path_for_job,cancelled,progress)


def _search_transcripts(job_database, index_database, result_file, query, path_for_job,
                        cancelled, progress):
    expression = content_expression(query)
    started = time.monotonic()

    def check():
        if cancelled.is_set():
            raise SearchCancelled('Detailsuche gestoppt.')

    check()
    candidates = {}
    with closing(sqlite3.connect(Path(job_database).as_uri() + '?mode=ro', uri=True)) as jobs:
        jobs.row_factory = sqlite3.Row
        generation=storage_generation(jobs)
        rows = jobs.execute("""SELECT j.*, k.kind AS result_kind,
            k.transcript_path AS known_transcript_path FROM jobs j
            LEFT JOIN known_results k ON k.job_id=j.id
            WHERE """+TRANSCRIPT_SCOPE)
        for row in rows:
            check()
            path = Path(path_for_job(dict(row))).absolute()
            key = os.path.normcase(str(path))
            if key not in candidates:
                candidates[key] = (path, [])
            candidates[key][1].append(row['id'])

    index_database = Path(index_database)
    index_database.parent.mkdir(parents=True, exist_ok=True)
    changed = skipped = 0
    with closing(sqlite3.connect(index_database, timeout=2)) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA cache_size=-8192')  # 8 MiB page cache, independent of library size.
        db.executescript("""CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, size INTEGER, mtime_ns INTEGER);
            CREATE TABLE IF NOT EXISTS job_files (job_id INTEGER PRIMARY KEY, path TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS job_file_path ON job_files(path);""")
        try:
            db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
                body, content='', contentless_delete=1, detail=none,
                tokenize='unicode61 remove_diacritics 2')""")
        except sqlite3.OperationalError as error:
            if 'unrecognized option' not in str(error):
                raise RuntimeError('Die lokale SQLite-Laufzeit unterstützt den Suchindex nicht.') from error
            # Older Mac SQLite builds can use the same queries with an ordinary FTS5 table.
            db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
                body, detail=none, tokenize='unicode61 remove_diacritics 2')""")
        with db:
            db.execute('DELETE FROM job_files')
            db.executemany('INSERT INTO job_files VALUES (?,?)',
                           ((identifier, key) for key, (_, ids) in candidates.items() for identifier in ids))
        last_progress = 0
        progress(f'Suchindex wird geprüft: 0 / {len(candidates):,} Dateien'.replace(',', '.'))
        for number, (key, (path, _)) in enumerate(candidates.items(), 1):
            check()
            cached = db.execute('SELECT id,size,mtime_ns FROM files WHERE path=?', (key,)).fetchone()
            try:
                before = path.stat()
                if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
                    raise OSError('Kein unterstütztes Transkript oder größer als 32 MiB.')
                if not cached or (cached[1], cached[2]) != (before.st_size, before.st_mtime_ns):
                    chunks = []
                    size = 0
                    with path.open('rb') as file:
                        while chunk := file.read(64 * 1024):
                            check()
                            size += len(chunk)
                            if size > MAX_FILE_BYTES:
                                raise OSError('Transkript größer als 32 MiB.')
                            chunks.append(chunk)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise OSError('Transkript wurde während der Indexierung geändert.')
                    data = b''.join(chunks)
                    try:
                        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
                    except UnicodeDecodeError:
                        text = data.decode('cp1252', errors='replace')
                    check()
                    db.execute('INSERT INTO files(path,size,mtime_ns) VALUES (?,?,?) '
                               'ON CONFLICT(path) DO UPDATE SET size=excluded.size,mtime_ns=excluded.mtime_ns',
                               (key, after.st_size, after.st_mtime_ns))
                    identifier = db.execute('SELECT id FROM files WHERE path=?', (key,)).fetchone()[0]
                    db.execute('INSERT OR REPLACE INTO transcript_fts(rowid,body) VALUES (?,?)',
                               (identifier, text.casefold()))
                    changed += 1
            except OSError:
                skipped += 1
                if cached:
                    db.execute('DELETE FROM transcript_fts WHERE rowid=?', (cached[0],))
                    db.execute('DELETE FROM files WHERE id=?', (cached[0],))
            if number % 64 == 0:
                db.commit()
            now = time.monotonic()
            if now - last_progress >= .2 or number == len(candidates):
                progress(f'Suchindex: {number:,} / {len(candidates):,} Dateien · {skipped:,} übersprungen'.replace(',', '.'))
                last_progress = now
        check()
        with db:
            db.execute('DELETE FROM transcript_fts WHERE rowid IN (SELECT id FROM files '
                       'WHERE path NOT IN (SELECT path FROM job_files))')
            db.execute('DELETE FROM files WHERE path NOT IN (SELECT path FROM job_files)')
        db.set_progress_handler(lambda: int(cancelled.is_set()), 1000)
        progress('Transkriptinhalt wird durchsucht …')
        try:
            matches = [row[0] for row in db.execute('SELECT job_id FROM job_files JOIN files USING(path) '
                'WHERE files.id IN (SELECT rowid FROM transcript_fts WHERE transcript_fts MATCH ?)', (expression,))]
        except sqlite3.OperationalError:
            check()
            raise
        check()
    token = uuid.uuid4().hex
    result = dict(token=token, query=query, job_ids=matches,generation=generation)
    result_file = Path(result_file)
    fd, name = tempfile.mkstemp(prefix='.search-', dir=result_file.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(result, file)
            file.flush()
            os.fsync(file.fileno())
        check()
        os.replace(name, result_file)
    finally:
        Path(name).unlink(missing_ok=True)
    return dict(token=token, matches=len(matches), files=len(candidates), changed=changed,
                skipped=skipped, seconds=time.monotonic()-started)


def run_content_search(job_database, index_database, result_file, query, cancelled,
                       progress=lambda text: None, process_context=subprocess.Popen):
    """Keep even blocking network reads outside the GUI; cancellation owns one worker."""
    arguments = [sys.executable, '-BEs', '-Xutf8', str(Path(__file__).resolve()),
                 '--jobs', str(job_database), '--index', str(index_database),
                 '--results', str(result_file), '--query', query]
    options = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
    if sys.platform == 'win32':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    messages = Queue()
    result = None
    errors = []
    with process_context(arguments, **options) as child:
        def read():
            for line in child.stdout:
                messages.put(line)
        reader = Thread(target=read, daemon=True)
        reader.start()
        try:
            while True:
                if cancelled.is_set():
                    raise SearchCancelled('Detailsuche gestoppt.')
                try:
                    line = messages.get(timeout=.05)
                except Empty:
                    if child.poll() is not None and not reader.is_alive() and messages.empty():
                        break
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    errors.append(line.strip())
                    errors = errors[-5:]
                    continue
                if message.get('type') == 'progress':
                    progress(message['text'])
                elif message.get('type') == 'result':
                    result = message['result']
                elif message.get('type') == 'error':
                    errors.append(message['text'])
            if child.wait() != 0 or result is None:
                raise RuntimeError('\n'.join(errors) or 'Die Detailsuche konnte nicht abgeschlossen werden.')
            return {**result, 'worker_pid': child.pid}
        finally:
            if child.poll() is None:
                cancel_tree = getattr(child, 'cancel_tree', child.terminate)
                cancel_tree()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=3)
            reader.join(timeout=2)
            child.stdout.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Local transcript index worker')
    parser.add_argument('--jobs', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--query', required=True)
    args = parser.parse_args()
    def emit(kind, **values):
        print(json.dumps(dict(type=kind, **values), ensure_ascii=False), flush=True)
    try:
        found = search_transcripts(args.jobs, args.index, args.results, args.query, transcript_path,
                                   Event(), lambda text: emit('progress', text=text))
    except Exception as error:
        emit('error', text=str(error))
        raise SystemExit(1)
    emit('result', result=found)
