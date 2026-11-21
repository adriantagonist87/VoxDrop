"""Profile-scoped app ownership, cooperative stop and bounded process cleanup."""
from contextlib import closing,contextmanager
from pathlib import Path
import os,sqlite3,time

import psutil
from platform_io import lock_service


def initialise_lifecycle(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS app_control (
        id INTEGER PRIMARY KEY CHECK(id=1), stop_requested INTEGER NOT NULL DEFAULT 0,
        owner_pid INTEGER, owner_created REAL);
        INSERT OR IGNORE INTO app_control(id) VALUES (1);''')


def stopping(db):
    row=db.execute('SELECT stop_requested FROM app_control WHERE id=1').fetchone()
    return bool(row and row[0])


def owner_alive(db):
    row=db.execute('SELECT owner_pid,owner_created FROM app_control WHERE id=1').fetchone()
    if not row or row[0] is None:
        return True  # Explicit standalone CLI runs have no GUI owner.
    try:
        process=psutil.Process(row[0])
        return process.is_running() and process.create_time()==row[1] and process.status()!=psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def register_owner(db,pid=None,created=None):
    if pid is not None:
        try:
            process=psutil.Process(pid)
            if created is None or process.create_time()!=created or not process.is_running():
                raise ValueError('Die startende VoxDrop-App läuft nicht mehr.')
        except psutil.Error as error:
            raise ValueError('Die startende VoxDrop-App läuft nicht mehr.') from error
    with db:
        db.execute('UPDATE app_control SET stop_requested=0,owner_pid=?,owner_created=? WHERE id=1',(pid,created))


def request_stop(db):
    with db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE app_control SET stop_requested=1 WHERE id=1')
        current=db.execute("SELECT id FROM jobs WHERE state IN ('copying','transcribing') AND publication_started=0").fetchall()
        for row in current:
            identifier=row[0]
            if not db.execute('SELECT 1 FROM cancel_requests WHERE job_id=?',(identifier,)).fetchone():
                db.execute('INSERT OR IGNORE INTO preemptions VALUES (?,?)',(identifier,time.time()))
                db.execute('INSERT INTO cancel_requests VALUES (?,?)',(identifier,time.time()))


@contextmanager
def lifecycle_lock(state):
    with (state/'app-control.lock').open('a') as lock:
        try:lock_service(lock)
        except BlockingIOError as error:
            raise RuntimeError('VoxDrop wird bereits gestartet oder beendet. Bitte kurz warten.') from error
        yield


def watch_owner(state,stop):
    owner = None
    while not stop.is_set():
        lost = False
        if owner is not None:
            try:
                process = psutil.Process(owner[0])
                lost = not _alive(process, owner[1])
            except psutil.Error:
                lost = True
        if lost:
            stop.set()
        try:
            with closing(sqlite3.connect(state/'jobs.sqlite3',timeout=2)) as db:
                if owner is None:
                    row = db.execute('SELECT owner_pid,owner_created FROM app_control WHERE id=1').fetchone()
                    if row and row[0] is not None:
                        owner = tuple(row)
                if stopping(db) or not owner_alive(db):
                    stop.set()
                    request_stop(db)
                    return
        except sqlite3.Error:
            pass  # The normal worker reports persistent DB failures.
        stop.wait(.25)


def service_processes(state,engine):
    state=os.path.normcase(os.path.abspath(state))
    engine=os.path.normcase(os.path.abspath(engine))
    found=[]
    for process in psutil.process_iter(['cmdline','create_time']):
        try:
            args=process.info['cmdline'] or []
            if not any(os.path.normcase(os.path.abspath(arg))==engine for arg in args if not arg.startswith('-')):
                continue
            if '--state-dir' not in args or not any(action in args for action in ('run','supervise')):
                continue
            position=args.index('--state-dir')+1
            if position>=len(args) or os.path.normcase(os.path.abspath(args[position]))!=state:
                continue
            found.append((process,process.info['create_time'],'supervise' in args))
        except (psutil.Error,OSError,ValueError):
            pass
    return found


def _alive(process,created):
    try:return process.is_running() and process.create_time()==created and process.status()!=psutil.STATUS_ZOMBIE
    except psutil.Error:return False


def stop_service(db,state,engine,*,grace_seconds=8):
    """Stop only this profile; never match a shared Python runtime by name."""
    with lifecycle_lock(state):
        recorded=True
        try:request_stop(db)
        except sqlite3.Error:
            db.rollback()
            recorded=False
            grace_seconds=0
        tracked={}
        deadline=time.monotonic()+grace_seconds
        while True:
            services=service_processes(state,engine)
            for process,created,_ in services:
                tracked[process.pid]=(process,created)
                try:
                    for child in process.children(recursive=True):
                        tracked[child.pid]=(child,child.create_time())
                except psutil.Error:pass
            if not any(_alive(process,created) for process,created in tracked.values()):
                break
            if time.monotonic()>=deadline:
                # Freeze roots first, then terminate all captured descendants, checking PID identity.
                for process,created,_ in sorted(services,key=lambda item:not item[2]):
                    if _alive(process,created):
                        try:process.suspend()
                        except psutil.Error:pass
                for process,created,_ in services:
                    try:
                        for child in process.children(recursive=True):tracked[child.pid]=(child,child.create_time())
                    except psutil.Error:pass
                for process,created in reversed(list(tracked.values())):
                    if _alive(process,created):
                        try:process.kill()
                        except psutil.NoSuchProcess:pass
                _,alive=psutil.wait_procs([process for process,created in tracked.values() if _alive(process,created)],timeout=5)
                if alive or service_processes(state,engine):
                    raise RuntimeError('VoxDrop konnte seine Hintergrundprozesse noch nicht vollständig beenden.')
                break
            time.sleep(.05)
        if not recorded:
            try:request_stop(db);recorded=True
            except sqlite3.Error:db.rollback()
    return dict(stopped=True,tracked_processes=len(tracked),database_stop_recorded=recorded)
