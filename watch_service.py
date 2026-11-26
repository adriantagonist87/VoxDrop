"""Persistent, single-job background worker for the EINGANG/FERTIGGESTELLT workflow."""

import argparse
import ctypes
import errno
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing, contextmanager, suppress, redirect_stdout, redirect_stderr
from functools import lru_cache
from pathlib import Path, PureWindowsPath

import login_agent
from platform_io import (
    WINDOWS,
    child_process,
    is_reparse_point,
    lock_service,
    open_regular,
    process_options,
    file_is_being_written,
    graphics_timeout_since,
)
from smb_paths import (
    on_network_volume,
    resolve_folder,
    smb_mounts,
    validate_folder_path,
)
from transcription_worker import GraphicsTimeout, run_transcription
from runtime_logs import RollingLog
from gpu_budget import validate_percent
from queue_control import (
    JobCancelled, initialise_queue, queue_jobs, queue_paused, set_queue_paused, start_queue, stop_queue,
    move_queue_item, cancel_job, cancel_queue, cancellation_requested, poll_cancellation,
    prioritise_jobs, restore_preempted,
    immediate_count, prune_immediate,
    move_queue_relative,
    WATCHED_JOB, WATCH_PATH,
)
from media_history import MediaBusy, initialise_media_history, remember_result, previously_transcribed
from history_store import HISTORY_FILTERS, media_path_key, search_storage_lock, storage_generation
from app_lifecycle import initialise_lifecycle, stopping, register_owner, lifecycle_lock, watch_owner, stop_service
from voxdrop import (
    DEFAULT_DATA,
    DEFAULT_HARDWARE,
    DEFAULT_MODEL,
    HARDWARE,
    MEDIA_EXTENSIONS,
    MODELS,
    WHISPER_MODEL,
    configure_runtime,
    publish_text,
    setup_models,
)

STARTUP_RETRY_DELAYS = (10, 30, 60)
SMB_PROBE_TIMEOUT = 8
RECURSIVE_SCAN_TIMEOUT = 120

JOBS_TABLE = """
CREATE TABLE {name} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    completed_dir TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    settings TEXT NOT NULL,
    detected REAL NOT NULL,
    updated REAL NOT NULL,
    started REAL,
    finished REAL,
    state TEXT NOT NULL DEFAULT 'seen',
    attempt INTEGER NOT NULL DEFAULT 0,
    phase TEXT,
    progress REAL,
    error TEXT,
    media_hash TEXT,
    text_hash TEXT,
    publication_started INTEGER NOT NULL DEFAULT 0,
    origin_job_id INTEGER REFERENCES jobs(id)
)
"""
KNOWN_FILES_INDEX = """CREATE UNIQUE INDEX IF NOT EXISTS known_file_versions
    ON jobs(source,size,mtime_ns) WHERE origin_job_id IS NULL"""
SCHEMA = (
    JOBS_TABLE.format(name="IF NOT EXISTS jobs")
    + ";\n"
    + KNOWN_FILES_INDEX
    + """;
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    recorded REAL NOT NULL,
    state TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS job_history_order ON jobs(updated,id);
CREATE INDEX IF NOT EXISTS job_queue_order ON jobs(state,detected,id);
CREATE INDEX IF NOT EXISTS event_job_state ON events(job_id,state);
CREATE TABLE IF NOT EXISTS transcription_measurements (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    speech_seconds REAL,
    speaker_seconds REAL,
    peak_memory_bytes INTEGER
);
CREATE TABLE IF NOT EXISTS audio_durations (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    seconds REAL NOT NULL CHECK(seconds > 0)
);
CREATE TABLE IF NOT EXISTS speaker_diarization (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    speaker_method TEXT NOT NULL,
    speaker_passes INTEGER NOT NULL,
    speaker_note TEXT
);
CREATE TRIGGER IF NOT EXISTS new_job AFTER INSERT ON jobs BEGIN
    INSERT INTO events(job_id, recorded, state, attempt)
    VALUES (new.id, new.updated, new.state, new.attempt);
END;
CREATE TRIGGER IF NOT EXISTS job_state AFTER UPDATE OF state ON jobs
WHEN new.state != old.state BEGIN
    INSERT INTO events(job_id, recorded, state, attempt, error)
    VALUES (new.id, new.updated, new.state, new.attempt, new.error);
END;
CREATE TABLE IF NOT EXISTS service (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    updated REAL NOT NULL,
    state TEXT NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS connection (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    updated REAL NOT NULL,
    available INTEGER NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS folder_status (
    path TEXT PRIMARY KEY,
    updated REAL NOT NULL,
    available INTEGER NOT NULL,
    error TEXT,
    incident TEXT
);
CREATE TABLE IF NOT EXISTS folder_refresh (
    path TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS copy_exports (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    retirement_dir TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS copy_claims (
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    path TEXT NOT NULL,
    identity TEXT NOT NULL,
    PRIMARY KEY(job_id, path)
);
CREATE TABLE IF NOT EXISTS job_retries (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    retry_at REAL NOT NULL,
    delay REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS storage_state (
    id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO storage_state VALUES (1,0);
CREATE TABLE IF NOT EXISTS retained_media (
    source TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL
);
"""
)


class SourceChanged(OSError):
    pass


def read_settings(path):
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise TypeError("Die Konfiguration muss ein JSON-Objekt sein.")
    defaults = {
        "interval_seconds": 30,
        "language": "auto",
        "speaker_count": None,
        "speakers": True,
        "dover_lap": False,
        "monitoring": False,
        "require_smb": False,
        "hardware": DEFAULT_HARDWARE,
        "model": DEFAULT_MODEL,
        "skip_silence": False,
        "gpu_budget_percent": 100,
        "windows_cpu_only": WINDOWS,
    }
    settings = {name: values.get(name, default) for name, default in defaults.items()}
    if "folders" in values:
        folders = values["folders"]
        if not isinstance(folders, list) or any(
            not isinstance(p, str) for p in folders
        ):
            raise ValueError("Die Ordnerliste muss aus Pfaden bestehen.")
        paths = [path.strip() for path in folders]
        if len(set(paths)) != len(paths):
            raise ValueError("Ein Ordnerpfad ist mehrfach eingetragen.")
        for folder in paths:
            validate_folder_path(folder)
        recursive = values.get("include_subfolders", False)
        if type(recursive) is not bool:
            raise ValueError(
                "Unterordner einbeziehen muss ein- oder ausgeschaltet sein."
            )
        create = values.get("create_output_subfolder", False)
        if type(create) is not bool:
            raise ValueError("Unterordner erstellen muss ein- oder ausgeschaltet sein.")
        create = create and not recursive
        name = values.get("output_subfolder", "_FERTIGGESTELLT")
        if create:
            validate_subfolder(name)
        elif not isinstance(name, str):
            name = "_FERTIGGESTELLT"
        options = values.get("folder_options", {})
        if not isinstance(options, dict):
            raise ValueError("Ordneroptionen müssen nach Pfad zugeordnet sein.")
        folder_options = {}
        for folder in paths:
            choice = options.get(folder, {})
            if not isinstance(choice, dict):
                raise ValueError("Ungültige Ordneroptionen.")
            paused = choice.get("paused", False)
            mode = choice.get("output", "global")
            if type(paused) is not bool or mode not in ("global", "beside", "subfolder"):
                raise ValueError("Ungültige Pause oder Ausgabeoption für einen Ordner.")
            if mode == "subfolder":
                validate_subfolder(name)
            if paused or mode != "global":
                folder_options[folder] = {"paused": paused, "output": mode}
        settings.update(
            folders=paths,
            folder_options=folder_options,
            include_subfolders=recursive,
            create_output_subfolder=create,
            output_subfolder=name,
        )
    else:
        for name in ("input_dir", "completed_dir"):
            value = values.get(name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Ein Ordnerpfad für {name} ist erforderlich.")
            settings[name] = value
    scope = values.get("scope_dir")
    if scope is not None and (
        not isinstance(scope, str) or not Path(scope).is_absolute()
    ):
        raise ValueError("scope_dir muss ein absoluter lokaler Pfad sein.")
    settings["scope_dir"] = scope
    for name in ("monitoring", "speakers", "require_smb", "skip_silence", "dover_lap", "windows_cpu_only"):
        if type(settings[name]) is not bool:
            raise ValueError(f"{name} muss true oder false sein.")
    interval = settings["interval_seconds"]
    if type(interval) is not int or interval < 1:
        raise ValueError(
            "Das Scanintervall muss eine positive ganze Sekundenzahl sein."
        )
    if settings["language"] not in ("auto", "de", "en"):
        raise ValueError("Erlaubte Sprachen sind auto, de und en.")
    if settings["hardware"] not in HARDWARE:
        raise ValueError(f"Erlaubte Rechengeräte sind {', '.join(HARDWARE)}.")
    if settings["model"] not in MODELS:
        raise ValueError("Erlaubte Transkriptionsmodelle sind Qwen und Whisper.")
    validate_percent(settings['gpu_budget_percent'])
    count = settings["speaker_count"]
    if count is not None and (type(count) is not int or count not in range(1, 9)):
        raise ValueError(
            "Die Sprecherzahl muss zwischen 1 und 8 liegen oder null sein."
        )
    return settings


def validate_subfolder(name):
    if (
        not isinstance(name, str)
        or name != name.strip()
        or name in {"", ".", ".."}
        or any(character in name for character in ("/", "\\", "\0"))
        or (
            WINDOWS
            and (
                PureWindowsPath(name).is_reserved()
                or name.endswith(".")
                or any(c in ':*?"<>|' or ord(c) < 32 for c in name)
            )
        )
    ):
        raise ValueError(
            "Für den Unterordner ist ein einzelner Ordnername erforderlich."
        )


def folder_profile(settings, path):
    profile = {key: value for key, value in settings.items() if key not in ("folders", "folder_options")}
    mode = settings.get("folder_options", {}).get(path, {}).get("output", "global")
    if mode == "beside":
        profile["create_output_subfolder"] = False
    elif mode == "subfolder":
        profile.update(include_subfolders=False, create_output_subfolder=True)
    return {**profile, "watch_path": path, "require_smb": False, "scope_dir": None}


def enabled_watch_paths(settings):
    if "folders" not in settings:
        return [settings["input_dir"]]
    options = settings.get("folder_options", {})
    return [path for path in settings["folders"] if not options.get(path, {}).get("paused")]


def reconcile_watched_jobs(db, settings):
    """Withdraw pending work whose configured watcher was paused or removed."""
    enabled = json.dumps(enabled_watch_paths(settings))
    with db:
        db.execute("BEGIN IMMEDIATE")
        inactive = f"{WATCHED_JOB} AND {WATCH_PATH} NOT IN (SELECT value FROM json_each(?))"
        parked = db.execute(f"""UPDATE jobs SET state='watch_deferred',updated=?
            WHERE state IN ('seen','ready') AND {inactive} RETURNING id""",
            (time.time(), enabled)).fetchall()
        db.executemany("DELETE FROM immediate_jobs WHERE job_id=?", parked)
        # A failed retry remains visible as a failure in history.
        db.execute(f"""DELETE FROM job_retries WHERE job_id IN
            (SELECT id FROM jobs WHERE state='failed' AND {inactive})""", (enabled,))
        db.execute(f"""DELETE FROM immediate_jobs WHERE job_id IN
            (SELECT id FROM jobs WHERE state='failed' AND {inactive})""", (enabled,))
        db.execute("DELETE FROM folder_status WHERE path NOT IN (SELECT value FROM json_each(?))", (enabled,))
        return len(parked)


def request_watched_rescan(db, settings):
    paths = enabled_watch_paths(settings)
    if not settings["monitoring"] or not paths:
        raise ValueError("Schalte die Ordnerüberwachung für mindestens einen Ordner ein.")
    with db:
        db.execute("BEGIN IMMEDIATE")
        # Also recover untouched files hidden by older versions of Clear Queue.
        db.execute(f"""UPDATE jobs SET state='watch_deferred',updated=?
            WHERE state='cancelled' AND attempt=0 AND started IS NULL AND text_hash IS NULL
            AND NOT publication_started AND {WATCHED_JOB}
            AND {WATCH_PATH} IN (SELECT value FROM json_each(?))""", (time.time(), json.dumps(paths)))
        db.executemany("INSERT OR IGNORE INTO folder_refresh VALUES (?)", ((path,) for path in paths))


def output_folder(source, settings):
    if settings.get("include_subfolders") or not settings["create_output_subfolder"]:
        return source
    name = settings["output_subfolder"]
    validate_subfolder(name)
    output = source / name
    try:
        metadata = output.lstat()
    except FileNotFoundError:
        return output
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or is_reparse_point(metadata)
        or metadata.st_dev != source.stat().st_dev
    ):
        raise ValueError("Der Unterordner muss ein regulärer Ordner am Quellpfad sein.")
    return output


def active_folders(settings):
    if path := settings.get("watch_path"):
        mounts = smb_mounts() if path.lower().startswith("smb://") else []
        source = resolve_folder(path, mounts, require_smb=False)
        return source, output_folder(source, settings)

    names = (settings["input_dir"], settings["completed_dir"])
    require_smb = settings["require_smb"]
    mounts = (
        smb_mounts()
        if require_smb or any(n.lower().startswith("smb://") for n in names)
        else []
    )
    incoming, completed = (
        resolve_folder(name, mounts, require_smb=require_smb) for name in names
    )
    if scope := settings.get("scope_dir"):
        root = Path(scope).resolve(strict=True)
        if any(
            folder == root or not folder.is_relative_to(root)
            for folder in (incoming, completed)
        ):
            raise ValueError(
                "Beide Ordner müssen innerhalb des konfigurierten Arbeitsbereichs liegen."
            )
    if incoming == completed or incoming.stat().st_dev != completed.stat().st_dev:
        raise ValueError(
            "Eingang und Fertiggestellt müssen getrennte Ordner desselben Volumes sein."
        )
    return incoming, completed


def database(state):
    connection = sqlite3.connect(state / "jobs.sqlite3", timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialise(state):
    if on_network_volume(state, smb_mounts()):
        raise ValueError(
            "Datenbank und temporäre Medienkopie benötigen einen lokalen Pfad."
        )
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with closing(database(state)) as db:
        db.execute("PRAGMA journal_mode = WAL")
        upgrade_jobs(db)
        db.executescript(SCHEMA)
        initialise_queue(db)
        initialise_media_history(db)
        initialise_lifecycle(db)


def upgrade_jobs(db):
    columns = [row["name"] for row in db.execute("PRAGMA table_info(jobs)")]
    if not columns or "origin_job_id" in columns:
        return
    db.execute("PRAGMA foreign_keys = OFF")
    try:
        db.execute("BEGIN IMMEDIATE")
        if "origin_job_id" not in {
            row["name"] for row in db.execute("PRAGMA table_info(jobs)")
        }:
            names = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
            db.execute(JOBS_TABLE.format(name="jobs_migrating"))
            db.execute(f"INSERT INTO jobs_migrating ({names}) SELECT {names} FROM jobs")
            db.execute("DROP TABLE jobs")
            db.execute("ALTER TABLE jobs_migrating RENAME TO jobs")
            db.execute(KNOWN_FILES_INDEX)
            if db.execute("PRAGMA foreign_key_check").fetchone():
                raise sqlite3.IntegrityError(
                    "Die Verlaufsdatenbank konnte nicht aktualisiert werden."
                )
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.execute("PRAGMA foreign_keys = ON")


def service_state(db, state, error=None):
    with db:
        db.execute(
            """INSERT INTO service VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated=excluded.updated, state=excluded.state,
                error=excluded.error""",
            (time.time(), state, error),
        )


def connection_state(db, available, error=None):
    with db:
        db.execute(
            """INSERT INTO connection VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET updated=excluded.updated,
                available=excluded.available, error=excluded.error""",
            (time.time(), available, error),
        )


def verify_writable(folder):
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".voxdrop-write-") as probe:
            probe.write(b"1")
            probe.flush()
    except OSError as error:
        raise OSError(
            f"Ordner nicht beschreibbar: {folder} ({error.strerror or error})"
        ) from error


def is_scan_directory(metadata, device):
    return (
        stat.S_ISDIR(metadata.st_mode)
        and not is_reparse_point(metadata)
        and metadata.st_dev == device
    )


def verify_source_directory(root, parent, *, source_root=None):
    anchor = root
    if not parent.is_relative_to(anchor):
        # A Windows drive letter may resolve to UNC. Keep the job's path
        # spelling, but validate every descendant through the resolved root.
        # Resolving the whole parent would hide a replaced child symlink.
        if source_root is None or str(source_root).lower().startswith("smb://"):
            raise OSError(f"Ordner liegt außerhalb des überwachten Pfads: {parent}")
        anchor = Path(os.path.abspath(Path(source_root).expanduser()))
        if not parent.is_relative_to(anchor) or anchor.resolve(strict=True) != root:
            raise OSError(f"Ordner liegt außerhalb des überwachten Pfads: {parent}")
    device = root.stat().st_dev
    for name in parent.relative_to(anchor).parts:
        root /= name
        if name.startswith(".") or not is_scan_directory(root.lstat(), device):
            raise OSError(f"Unterordner ist kein regulärer Ordner am Quellpfad: {root}")


def media_versions(incoming, recursive):
    versions = []
    warnings = []
    pending = [incoming]
    device = incoming.stat().st_dev if recursive else None
    while pending:
        folder = pending.pop()
        try:
            if folder != incoming and not is_scan_directory(folder.lstat(), device):
                continue
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    try:
                        if recursive and entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        elif Path(entry.name).suffix.lower() in MEDIA_EXTENSIONS:
                            metadata = entry.stat(follow_symlinks=False)
                            if (
                                stat.S_ISREG(metadata.st_mode)
                                and not is_reparse_point(metadata)
                                and metadata.st_size
                            ):
                                versions.append(
                                    (entry.path, metadata.st_size, metadata.st_mtime_ns)
                                )
                    except FileNotFoundError:
                        continue
                    except OSError as error:
                        if not recursive:
                            raise
                        warnings.append(str(error))
        except OSError as error:
            if folder == incoming:
                raise
            if not isinstance(error, FileNotFoundError):
                warnings.append(str(error))
    warning = None
    if warnings:
        warning = f"Ein Teil der Unterordner konnte nicht geprüft werden: {warnings[0]}"
        if len(warnings) > 1:
            warning += f" (+{len(warnings) - 1} weitere Fehler)"
    return versions, warning


def inspect_folders(settings):
    incoming, completed = active_folders(settings)
    recursive = bool(settings.get("include_subfolders") and settings.get("watch_path"))
    if recursive and (parent := settings.get("source_parent")):
        parent = Path(parent)
        verify_source_directory(incoming, parent, source_root=settings.get("watch_path"))
        incoming = completed = parent
    if settings.get("watch_path") and settings.get("probe_write", True):
        verify_writable(incoming)
        if completed != incoming and completed.is_dir():
            verify_writable(completed)
    if not settings["monitoring"]:
        for folder in {incoming, completed}:
            if folder.is_dir():
                with os.scandir(folder) as entries:
                    next(entries, None)
        return str(incoming), str(completed), [], None
    versions, warning = media_versions(incoming, recursive)
    return str(incoming), str(completed), versions, warning


def inspect_folders_with_deadline(settings):
    # A directory open on an SMB mount can block in the kernel. Isolate it from the watcher.
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-BEs",
                "-Xutf8",
                str(Path(__file__).resolve()),
                "inspect-folders",
            ],
            input=json.dumps(settings),
            capture_output=True,
            encoding="utf-8",
            timeout=RECURSIVE_SCAN_TIMEOUT
            if settings.get("include_subfolders") and settings["monitoring"]
            else SMB_PROBE_TIMEOUT,
            check=True,
            **process_options(),
        )
    except subprocess.TimeoutExpired as error:
        raise OSError("Zeitlimit bei der Ordnerprüfung erreicht.") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip().removeprefix("Fehler: ")
        raise OSError(detail or "SMB-Ordnerprüfung fehlgeschlagen.") from error
    return json.loads(result.stdout)


def scan(db, settings, now=None, *, inspect=inspect_folders, generation=None, config=None):
    if stopping(db):
        return
    generation=storage_generation(db) if generation is None else generation
    _, completed, versions, warning = inspect(settings)
    if not settings["monitoring"]:
        service_state(db, "paused")
        return
    now = time.time() if now is None else now
    snapshot = json.dumps(
        {**settings, "model": settings.get("model", DEFAULT_MODEL)},
        ensure_ascii=False,
        sort_keys=True,
    )
    with db:
        db.execute('BEGIN IMMEDIATE')
        if generation!=storage_generation(db) or stopping(db):
            return
        if config is not None:
            latest = read_settings(config)
            path = settings["watch_path"]
            if path not in enabled_watch_paths(latest) or folder_profile(latest, path) != settings:
                return
        for candidate in versions:
            if db.execute(
                'SELECT 1 FROM retained_media WHERE source=? AND size=? AND mtime_ns=?',
                (media_path_key(candidate[0]), *candidate[1:]),
            ).fetchone():
                continue
            destination = (
                str(Path(candidate[0]).parent)
                if settings.get("include_subfolders")
                else completed
            )
            db.execute(
                """UPDATE jobs SET state='superseded', updated=?
                WHERE source=? AND origin_job_id IS NULL AND state IN ('seen','ready') AND attempt=0
                AND (size != ? OR mtime_ns != ?)""",
                (now, *candidate),
            )
            db.execute(
                """INSERT INTO jobs(source,size,mtime_ns,completed_dir,settings,detected,updated)
                SELECT ?,?,?,?,?,?,? WHERE NOT EXISTS (
                    SELECT 1 FROM jobs WHERE source=? AND size=? AND mtime_ns=? AND origin_job_id IS NULL
                )""",
                (*candidate, destination, snapshot, now, now, *candidate),
            )
            db.execute(
                """UPDATE jobs SET state='seen', detected=?, updated=?
                WHERE source=? AND size=? AND mtime_ns=? AND origin_job_id IS NULL AND state='superseded'""",
                (now, now, *candidate),
            )
            db.execute(
                f"""UPDATE jobs SET state='seen', detected=?, updated=?,
                finished=NULL, error=NULL, phase=NULL, progress=NULL,
                settings=CASE WHEN text_hash IS NULL AND NOT publication_started THEN ? ELSE settings END,
                completed_dir=CASE WHEN text_hash IS NULL AND NOT publication_started THEN ? ELSE completed_dir END
                WHERE source=? AND size=? AND mtime_ns=? AND state='watch_deferred'
                AND {WATCHED_JOB} AND ({WATCH_PATH}=? OR (text_hash IS NULL AND NOT publication_started))""",
                (now, now, snapshot, destination, *candidate, settings.get("watch_path", settings.get("input_dir"))),
            )
            # Keep transcription choices on existing jobs. Output routing follows
            # the current watcher until processing starts.
            db.execute(
                f"""UPDATE jobs SET completed_dir=?, settings=json_set(settings,
                '$.include_subfolders',json(?), '$.create_output_subfolder',json(?),
                '$.output_subfolder',?, '$.move_media',json('false'))
                WHERE source=? AND size=? AND mtime_ns=? AND {WATCHED_JOB} AND {WATCH_PATH}=?
                AND state IN ('seen','ready') AND attempt=0 AND text_hash IS NULL
                AND NOT publication_started AND (completed_dir!=?
                OR COALESCE(json_extract(settings,'$.include_subfolders'),0)!=?
                OR COALESCE(json_extract(settings,'$.create_output_subfolder'),0)!=?)""",
                (destination, json.dumps(bool(settings.get("include_subfolders"))),
                 json.dumps(bool(settings.get("create_output_subfolder"))), settings.get("output_subfolder", "_FERTIGGESTELLT"),
                 *candidate, settings.get("watch_path", settings.get("input_dir")), destination,
                 bool(settings.get("include_subfolders")), bool(settings.get("create_output_subfolder"))),
            )
            db.execute(
                """UPDATE jobs SET state='ready', updated=? WHERE source=? AND size=? AND mtime_ns=?
                AND origin_job_id IS NULL AND state='seen' AND detected<=?""",
                (now, *candidate, now - settings["interval_seconds"]),
            )
    recognise_existing_results(db)
    service_state(db, "active")
    return warning


def recognise_existing_results(db):
    """Import adjacent TXT metadata before queued media reaches inference."""
    rows=db.execute("""SELECT * FROM jobs WHERE state IN ('seen','ready')
        AND origin_job_id IS NULL AND text_hash IS NULL""").fetchall()
    for job in rows:
        source=Path(job['source'])
        _, text=targets(job)
        if text.parent!=source.parent:
            continue
        try:
            if not text.is_file() or file_is_being_written(source) or file_is_being_written(text):
                continue
            text_hash=digest(text)
        except OSError:
            continue
        with db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT state FROM jobs WHERE id=?',(job['id'],)).fetchone()
            if current is None or current['state'] not in ('seen','ready'):
                continue
            remember_result(db,job['id'],'existing',text,text_hash)
            error_state(db,job['id'],'existing',None)


def inspect_drop_path(settings, path):
    candidate = Path(os.path.abspath(path))
    metadata = candidate.lstat()
    if stat.S_ISREG(metadata.st_mode):
        if candidate.suffix.lower() not in MEDIA_EXTENSIONS:
            raise ValueError('Diese Datei hat kein unterstütztes Audio-/Videoformat.')
        return str(candidate.parent), None, [(str(candidate), metadata.st_size, metadata.st_mtime_ns)], ''
    if not stat.S_ISDIR(metadata.st_mode) or candidate.is_symlink():
        raise ValueError('Bitte reguläre Aufnahmen oder Ordner ablegen; Verknüpfungen werden nicht verfolgt.')
    profile = {**folder_profile(settings, str(candidate)), 'monitoring': True,
               'include_subfolders': True, 'create_output_subfolder': False, 'probe_write': False}
    validate_folder_path(str(candidate))
    return inspect_folders_with_deadline(profile)


def drop_previous(db, candidate):
    comparison = 'source COLLATE NOCASE' if WINDOWS else 'source'
    return db.execute(f"""SELECT * FROM jobs WHERE {comparison}=? AND size=? AND mtime_ns=?
        ORDER BY CASE WHEN state IN ('copying','transcribing','exporting') THEN 0
            WHEN state IN ('seen','ready') THEN 1 ELSE 2 END, id DESC LIMIT 1""", candidate).fetchone()


def prepare_drop(db, settings, paths):
    """Inspect the entire drop without altering an existing job or starting new work."""
    candidates, warnings = {}, []
    for path in dict.fromkeys(paths):
        try:
            root, _, versions, warning = inspect_drop_path(settings, path)
            if warning:
                warnings.append(f'{path}: {warning}')
            for version in versions:
                candidates[os.path.normcase(version[0])] = (version, root)
        except (OSError, ValueError) as error:
            warnings.append(f'{path}: {error}')
    items = []
    labels = dict(new='Neue Aufnahme', queued='Bereits in der Warteschlange', active='Wird gerade verarbeitet',
                  done='Bereits transkribiert', existing='TXT bereits vorhanden', problem='Fehlgeschlagen oder abgebrochen')
    for version, root in candidates.values():
        previous = drop_previous(db, version)
        if previous:
            state = previous['state']
            kind = ('new' if state == 'watch_deferred' and not previous['text_hash'] and not previous['publication_started']
                    else 'queued' if state in ('seen','ready') else 'active' if state in ('copying','transcribing','exporting')
                    else 'existing' if state == 'existing' else 'done' if state in ('done','duplicate','superseded') else 'problem')
        else:
            kind = 'existing' if Path(version[0]).with_suffix('.txt').is_file() else 'new'
        profile = {**folder_profile(settings, root), 'watch_path': root, 'folder_drop': True,
                   'include_subfolders': True, 'create_output_subfolder': False, 'move_media': False}
        items.append(dict(source=version[0], size=version[1], mtime_ns=version[2], profile=profile,
                          job_id=previous['id'] if previous else None, kind=kind, status=labels[kind]))
    token = uuid.uuid4().hex
    with db:
        db.execute('INSERT INTO drop_batches VALUES (?,?,?,NULL)',
                   (token, time.time(), json.dumps(dict(items=items, warnings=warnings), ensure_ascii=False)))
        db.execute('DELETE FROM drop_batches WHERE created<?', (time.time()-7*86400,))
    counts = {kind: sum(item['kind'] == kind for item in items) for kind in labels}
    return dict(token=token, items=[{key:value for key,value in item.items() if key != 'profile'} for item in items],
                counts=counts, warnings=warnings, has_conflicts=bool(warnings) or any(item['kind'] != 'new' for item in items))


def resolve_drop(db, token, action):
    if action not in ('queue','front','retranscribe','immediate','ignore'):
        raise ValueError('Unbekannte Drop-Aktion.')
    batch = db.execute('SELECT * FROM drop_batches WHERE token=?', (token,)).fetchone()
    if batch is None:
        raise ValueError('Dieser Drop ist nicht mehr verfügbar. Bitte erneut ablegen.')
    if batch['result']:
        return json.loads(batch['result'])
    plan = json.loads(batch['items'])
    warnings = list(plan['warnings'])
    valid = []
    # Network I/O happens before the short write transaction.
    for item in plan['items']:
        try:
            metadata = Path(item['source']).lstat()
            if not stat.S_ISREG(metadata.st_mode) or (metadata.st_size,metadata.st_mtime_ns) != (item['size'],item['mtime_ns']):
                raise OSError('Datei wurde inzwischen verändert. Bitte erneut ablegen.')
            item['text_exists'] = Path(item['source']).with_suffix('.txt').is_file()
            valid.append(item)
        except OSError as error:
            warnings.append(f"{item['source']}: {error}")
    identifiers, queued, ignored, active = [], 0, 0, 0
    with db:
        db.execute('BEGIN IMMEDIATE')
        current_batch = db.execute('SELECT result FROM drop_batches WHERE token=?', (token,)).fetchone()
        if current_batch is None:
            raise ValueError('Dieser Drop ist nicht mehr verfügbar. Bitte erneut ablegen.')
        if current_batch['result']:
            return json.loads(current_batch['result'])
        for item in valid:
            source = item['source']
            version = (source, item['size'], item['mtime_ns'])
            previous = drop_previous(db, version)
            state = previous['state'] if previous else None
            deferred = state == 'watch_deferred' and not previous['text_hash'] and not previous['publication_started']
            if action == 'ignore' and ((previous is not None and not deferred) or item['kind'] != 'new'):
                ignored += 1
                continue
            if state in ('copying','transcribing','exporting'):
                identifiers.append(previous['id'])
                active += 1
                continue
            profile = item['profile']
            now = time.time()
            if (state in ('seen','ready') or deferred) and item['text_exists'] and action in ('retranscribe','immediate'):
                db.execute("UPDATE jobs SET state='existing',updated=? WHERE id=?", (now, previous['id']))
                remember_result(db, previous['id'], 'existing', Path(source).with_suffix('.txt'))
                previous = db.execute('SELECT * FROM jobs WHERE id=?', (previous['id'],)).fetchone()
                state = 'existing'
                deferred = False
            if deferred or state in ('seen','ready') or (state in ('failed','blocked','cancelled') and action in ('front','queue','immediate') and not (item['text_exists'] and action == 'immediate')):
                identifier = previous['id']
                db.execute("UPDATE jobs SET state='ready',completed_dir=?,settings=?,updated=?,error=NULL WHERE id=?",
                    (str(Path(source).parent), json.dumps(profile, ensure_ascii=False), now, identifier))
                db.execute('DELETE FROM job_retries WHERE job_id=?', (identifier,))
                db.execute('DELETE FROM cancel_requests WHERE job_id=?', (identifier,))
            elif previous is not None or item['kind'] == 'existing':
                if action not in ('retranscribe','immediate'):
                    ignored += 1
                    continue
                if previous is None:
                    base = db.execute("INSERT INTO jobs(source,size,mtime_ns,completed_dir,settings,detected,updated,state) VALUES (?,?,?,?,?,?,?,'existing')",
                        (*version, str(Path(source).parent), json.dumps(profile, ensure_ascii=False), now, now))
                    remember_result(db, base.lastrowid, 'existing', Path(source).with_suffix('.txt'))
                    previous = db.execute('SELECT * FROM jobs WHERE id=?', (base.lastrowid,)).fetchone()
                origin = previous['origin_job_id'] or previous['id']
                planned = db.execute("SELECT id FROM jobs WHERE origin_job_id=? AND state IN ('seen','ready','copying','transcribing','exporting') ORDER BY id LIMIT 1", (origin,)).fetchone()
                if planned:
                    identifier = planned['id']
                else:
                    profile = {**profile, 'original_media_hash': previous['media_hash']}
                    inserted = db.execute("INSERT INTO jobs(source,size,mtime_ns,completed_dir,settings,detected,updated,state,origin_job_id) VALUES (?,?,?,?,?,?,?,'ready',?)",
                        (*version, str(Path(source).parent), json.dumps(profile, ensure_ascii=False), now, now, origin))
                    identifier = inserted.lastrowid
                    queued += 1
            else:
                inserted = db.execute("INSERT INTO jobs(source,size,mtime_ns,completed_dir,settings,detected,updated,state) VALUES (?,?,?,?,?,?,?,'ready')",
                    (*version, str(Path(source).parent), json.dumps(profile, ensure_ascii=False), now, now))
                identifier = inserted.lastrowid
                queued += 1
            identifiers.append(identifier)
        interrupted = prioritise_jobs(db, identifiers, interrupt=action == 'immediate') if action in ('front','immediate') else None
        result = dict(queued=queued, selected=len(set(identifiers)), ignored=ignored, active=active,
                      interrupted=interrupted, pending=bool(identifiers), warnings=warnings,
                      queue_remains_paused=queue_paused(db),
                      export_finishes=action == 'immediate' and bool(db.execute("SELECT 1 FROM jobs WHERE state='exporting' OR (state IN ('copying','transcribing') AND publication_started=1)").fetchone()))
        db.execute('UPDATE drop_batches SET result=? WHERE token=?', (json.dumps(result, ensure_ascii=False), token))
    return result


def enqueue_folders(db, settings, folders):
    """Queue fixed file versions without subscribing to their directories."""
    queued = skipped = 0
    pending = False
    warnings = []
    for folder in dict.fromkeys(folders):
        source_settings = {
            **folder_profile(settings, folder),
            "monitoring": True,
            "include_subfolders": True,
            "create_output_subfolder": False,
            "probe_write": False,
        }
        try:
            root, _, versions, warning = inspect_drop_path(settings, folder)
        except (OSError, ValueError) as error:
            warnings.append(f"{folder}: {error}")
            continue
        if warning:
            warnings.append(f"{folder}: {warning}")

        now = time.time()
        with db:
            db.execute("BEGIN IMMEDIATE")
            for candidate in versions:
                source = candidate[0]
                parent = str(Path(source).parent)
                previous = db.execute(
                    """SELECT * FROM jobs WHERE origin_job_id IS NULL
                    AND source=? AND size=? AND mtime_ns=?""",
                    candidate,
                ).fetchone()
                if previous and previous["state"] == "done":
                    skipped += 1
                    continue

                original = json.loads(previous["settings"]) if previous else {}
                profile = folder_profile(settings, root)
                active = previous and previous["state"] in (
                    "copying", "transcribing", "exporting"
                )
                if previous and (active or previous["text_hash"]):
                    profile = original
                if previous and previous["publication_started"] and moves_media(original):
                    warnings.append(f"Archivexport bereits begonnen: {source}")
                    continue
                if previous and original.get("folder_drop") and (
                    active or previous["state"] == "ready"
                ):
                    skipped += 1
                    pending = True
                    continue
                profile.update(
                    watch_path=root,
                    folder_drop=True,
                    include_subfolders=True,
                    create_output_subfolder=False,
                    move_media=False,
                )
                snapshot = json.dumps(profile, ensure_ascii=False)
                if previous:
                    db.execute(
                        """UPDATE jobs SET completed_dir=?,settings=?,updated=?,
                        state=?,error=NULL WHERE id=?""",
                        (
                            parent, snapshot, now,
                            previous["state"] if active else "ready", previous["id"],
                        ),
                    )
                else:
                    db.execute(
                        """INSERT INTO jobs(source,size,mtime_ns,completed_dir,settings,
                        detected,updated,state) VALUES (?,?,?,?,?,?,?,'ready')""",
                        (*candidate, parent, snapshot, now, now),
                    )
                queued += 1
    return {"queued": queued, "skipped": skipped, "pending": pending, "warnings": warnings}


@lru_cache(maxsize=1)
def rename_function():
    native = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True).renamex_np
    native.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    native.restype = ctypes.c_int
    return native


def rename_exclusive(source, target):
    if WINDOWS:
        # MoveFileEx without MOVEFILE_REPLACE_EXISTING also works on UNC paths.
        os.rename(source, target)
        return
    # RENAME_EXCL from the macOS SDK. The filesystem must provide the guarantee.
    if rename_function()(os.fsencode(source), os.fsencode(target), 0x00000004) == -1:
        code = ctypes.get_errno()
        if code in {errno.ENOTSUP, errno.ENOSYS}:
            raise OSError(
                code, "Das Volume unterstützt kein exklusives Umbenennen.", str(target)
            )
        raise OSError(code, os.strerror(code), str(target))


@contextmanager
def regular_reader(path):
    descriptor = open_regular(path, os.O_RDONLY)
    with os.fdopen(descriptor, "rb") as reader:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(f"Kein reguläres Medium: {path}")
        yield reader


def digest(path):
    with regular_reader(path) as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def version(metadata):
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def stage(job, target, *, cancelled=None):
    source = Path(job["source"])
    if shutil.disk_usage(target.parent).free < job["size"]:
        raise OSError(
            "Zu wenig freier Speicherplatz für die vollständige lokale Kopie."
        )
    sha = hashlib.sha256()
    written = 0
    partial = target.with_suffix(".partial")
    try:
        with regular_reader(source) as reader, partial.open("xb") as writer:
            initial = version(os.fstat(reader.fileno()))
            if initial[2:] != (job["size"], job["mtime_ns"]):
                raise SourceChanged("Die Quelle hat sich seit der Erkennung geändert.")
            while chunk := reader.read(1024 * 1024):
                if cancelled is not None and cancelled():
                    raise JobCancelled('Auftrag abgebrochen.')
                writer.write(chunk)
                sha.update(chunk)
                written += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
            if (
                written != job["size"]
                or version(os.fstat(reader.fileno())) != initial
                or version(source.lstat()) != initial
            ):
                raise SourceChanged(
                    "Die Quelle hat sich während der Übernahme geändert."
                )
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return sha.hexdigest()


def targets(job):
    media = Path(job["completed_dir"]) / Path(job["source"]).name
    if job["origin_job_id"] is None:
        return media, media.with_suffix(".txt")
    name = f"{media.stem} (Neu {job['id']}).txt"
    if len(name.encode("utf-8")) > 255:
        name = f"Neutranskription {job['id']}.txt"
    return media, media.with_name(name)


def moves_media(settings):
    return not settings.get("include_subfolders") and (
        not settings.get("watch_path") or settings.get("move_media", False)
    )


def matches(path, expected):
    try:
        return digest(path) == expected
    except FileNotFoundError:
        return False


def error_state(db, job_id, state, error):
    with db:
        db.execute(
            """UPDATE jobs SET state=?, error=?, updated=?, finished=?, phase=NULL, progress=NULL
            WHERE id=?""",
            (state, error, time.time(), time.time(), job_id),
        )


def hold_after_graphics_timeout(db, job_id, evidence):
    reason = f"Windows-Grafikfehler: {evidence}. Die Warteschlange wurde angehalten."
    with db:
        db.execute("BEGIN IMMEDIATE")
        if cancellation_requested(db, job_id):
            return False
        db.execute("UPDATE queue_state SET paused=1 WHERE id=1")
        db.execute("DELETE FROM immediate_jobs")
        db.execute("INSERT OR REPLACE INTO queue_graphics_hold VALUES (1,?)", (reason,))
        db.execute("DELETE FROM job_retries WHERE job_id=?", (job_id,))
        db.execute("""UPDATE jobs SET state='ready',error=?,updated=?,
            started=NULL,finished=NULL,phase=NULL,progress=NULL WHERE id=?""", (reason, time.time(), job_id))
    return True


def copy_identity(metadata):
    return f"{metadata.st_ino}:{metadata.st_birthtime.hex()}"


def copy_verified(db, job_id, source, target, expected):
    flags = os.O_RDWR
    try:
        descriptor = open_regular(target, flags | os.O_CREAT | os.O_EXCL)
        created = True
    except FileExistsError:
        if matches(target, expected):
            return
        descriptor = open_regular(target, flags)
        created = False

    with os.fdopen(descriptor, "r+b") as writer, regular_reader(source) as reader:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise FileExistsError(f"Am Ziel liegt keine reguläre Datei: {target.name}")
        identity = copy_identity(metadata)
        if created:
            with db:
                db.execute(
                    "INSERT OR REPLACE INTO copy_claims VALUES (?, ?, ?)",
                    (job_id, str(target), identity),
                )
        else:
            previous = db.execute(
                "SELECT identity FROM copy_claims WHERE job_id=? AND path=?",
                (job_id, str(target)),
            ).fetchone()
            if (
                not metadata.st_ino
                or not metadata.st_birthtime
                or previous is None
                or previous[0] != identity
            ):
                raise FileExistsError(
                    f"Eine andere Datei existiert bereits: {target.name}"
                )
            while prefix := writer.read(1024 * 1024):
                if reader.read(len(prefix)) != prefix:
                    raise FileExistsError(
                        f"Die Zielkopie wurde verändert: {target.name}"
                    )
        shutil.copyfileobj(reader, writer, length=1024 * 1024)
        writer.flush()
        os.fsync(descriptor)
    if not matches(target, expected):
        raise OSError(f"Die Zielkopie konnte nicht verifiziert werden: {target.name}")


def retirement_dir(db, job):
    row = db.execute(
        "SELECT retirement_dir FROM copy_exports WHERE job_id=?", (job["id"],)
    ).fetchone()
    return Path(row[0]) if row else None


def finish_retirement(directory, source, expected):
    if directory is None or not os.path.lexists(directory):
        return
    if directory.parent != source.parent or not stat.S_ISDIR(directory.lstat().st_mode):
        raise OSError("Der Sicherungsordner im Eingang kann nicht geprüft werden.")
    retired = directory / source.name
    if os.path.lexists(retired):
        if not matches(retired, expected):
            raise OSError(
                f"Datei im Sicherungsordner erhalten, da sie sich geändert hat: {retired}"
            )
        retired.unlink()
    directory.rmdir()


def publish_copies(db, job, transcript, initial, directory, staged):
    source = Path(job["source"])
    media, text = targets(job)
    if not matches(transcript, job["text_hash"]):
        raise OSError("Die lokal aufbewahrte TXT konnte nicht verifiziert werden.")
    media_to_copy = staged if staged.is_file() else source
    copy_verified(db, job["id"], media_to_copy, media, job["media_hash"])
    copy_verified(db, job["id"], transcript, text, job["text_hash"])
    if not matches(media, job["media_hash"]):
        raise OSError("Die Zielkopie wurde während des TXT-Exports verändert.")
    if version(source.lstat()) != initial:
        raise OSError("Die Quelle hat sich vor Abschluss des Exports geändert.")
    directory.mkdir(mode=0o700, exist_ok=True)
    retired = directory / source.name
    if not stat.S_ISDIR(directory.lstat().st_mode) or os.path.lexists(retired):
        raise OSError(f"Der Sicherungsordner ist nicht frei: {directory}")
    source.rename(retired)
    finish_retirement(directory, source, job["media_hash"])


def publish_text_exclusive(transcript, text, expected):
    if os.path.lexists(text):
        if not matches(text, expected):
            raise FileExistsError(f"Eine andere TXT existiert bereits: {text.name}")
        return
    if not matches(transcript, expected):
        raise OSError("Die lokal aufbewahrte TXT konnte nicht verifiziert werden.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=text.parent, prefix=".transcript-", suffix=".partial", delete=False
        ) as handle:
            temporary = Path(handle.name)
            with regular_reader(transcript) as reader:
                shutil.copyfileobj(reader, handle)
            handle.flush()
            os.fsync(handle.fileno())
        rename_exclusive(temporary, text)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def reserve_archive_export(db, job):
    if job["publication_started"]:
        return job
    media, text = targets(job)
    occupied = os.path.lexists(media) or os.path.lexists(text)
    with db:
        db.execute("BEGIN IMMEDIATE")
        latest = db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if json.loads(latest["settings"]).get("folder_drop"):
            return latest
        if occupied:
            raise FileExistsError("Medium oder TXT existiert bereits im Zielordner.")
        db.execute("UPDATE jobs SET publication_started=1 WHERE id=?", (job["id"],))
    return db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()


def publish_job(db, job, transcript, staged, *, text_first=False):
    source = Path(job["source"])
    media, text = targets(job)
    directory = retirement_dir(db, job)
    if not os.path.lexists(source):
        if matches(media, job["media_hash"]) and matches(text, job["text_hash"]):
            finish_retirement(directory, source, job["media_hash"])
            return
        raise FileNotFoundError(
            "Die Quelle fehlt, und das Zielpaar kann nicht bestätigt werden."
        )
    initial = version(source.lstat())
    if initial[2:] != (job["size"], job["mtime_ns"]) or not matches(
        source, job["media_hash"]
    ):
        if text_first:
            raise SourceChanged(
                "Die Originalaufnahme hat sich seit der Transkription verändert."
            )
        raise OSError("Die Quelle hat sich seit der Transkription geändert.")
    if directory is None and os.path.lexists(media):
        raise FileExistsError(f"Das Zielmedium existiert bereits: {media.name}")
    if text_first:
        publish_verified_text(db, job, transcript, text)
    if directory is None:
        try:
            if not text_first:
                publish_text_exclusive(transcript, text, job["text_hash"])
            if version(source.lstat()) != initial:
                raise OSError("Die Quelle hat sich vor dem Verschieben geändert.")
            rename_exclusive(source, media)
            return
        except OSError as error:
            if error.errno not in {errno.ENOTSUP, errno.ENOSYS}:
                raise
        directory = source.parent / f".transcriber-{uuid.uuid4().hex}"
        with db:
            db.execute(
                "INSERT INTO copy_exports VALUES (?, ?)", (job["id"], str(directory))
            )
    publish_copies(db, job, transcript, initial, directory, staged)


def publish_verified_text(db, job, transcript, text):
    try:
        publish_text_exclusive(transcript, text, job["text_hash"])
    except OSError as error:
        if error.errno not in {errno.ENOTSUP, errno.ENOSYS}:
            raise
        copy_verified(db, job["id"], transcript, text, job["text_hash"])
    if not matches(text, job["text_hash"]):
        raise OSError("Die exportierte TXT konnte nicht verifiziert werden.")


def publish_transcript_only(db, job, transcript):
    source, text = Path(job["source"]), targets(job)[1]
    initial = version(source.lstat())
    if initial[2:] != (job["size"], job["mtime_ns"]) or not matches(
        source, job["media_hash"]
    ):
        raise SourceChanged(
            "Die Originalaufnahme hat sich seit der Transkription verändert."
        )
    if job["origin_job_id"] is None and source.parent != text.parent:
        raise OSError("Der Ausgabeordner hat sich verändert.")
    if not job["publication_started"]:
        if os.path.lexists(text):
            raise FileExistsError(f"Eine TXT existiert bereits: {text.name}")
        with db:
            db.execute("UPDATE jobs SET publication_started=1 WHERE id=?", (job["id"],))
    publish_verified_text(db, job, transcript, text)


def job_folders(job, settings):
    parent = Path(job["source"]).parent
    if job["origin_job_id"] is not None:
        completed = Path(job["completed_dir"])
        if parent == completed:
            return probe_job_paths(
                {"watch_path": str(parent), "create_output_subfolder": False,
                 "include_subfolders": True}, parent=parent
            )
        incoming, output, _, _ = inspect_folders_with_deadline(
            {
                "input_dir": str(parent),
                "completed_dir": str(completed),
                "monitoring": False,
                "require_smb": False,
                "scope_dir": None,
            }
        )
        return Path(incoming), Path(output)
    return (
        probe_job_paths(settings, parent=parent)
        if settings.get("watch_path")
        else active_folders(settings)
    )


def keep_transcript_beside_source(db, job, settings, config):
    parent = str(Path(job["source"]).parent)
    if config is None or parent == job["completed_dir"]:
        return job
    current = read_settings(config)
    path = settings.get("watch_path", settings.get("input_dir"))
    if path in current.get("folders", ()):
        current = folder_profile(current, path)
    if not current.get("include_subfolders"):
        return job
    if job["publication_started"]:
        raise FileExistsError(
            "Ein früherer Export wurde bereits begonnen. Wähle „Neu transkribieren“."
        )
    settings.update(
        include_subfolders=True, create_output_subfolder=False, move_media=False
    )
    if job["origin_job_id"] is None and not settings.get("watch_path"):
        settings["watch_path"] = settings["input_dir"]
    with db:
        db.execute(
            """UPDATE jobs SET completed_dir=?, settings=?
            WHERE id=? AND settings=? AND publication_started=0""",
            (parent, json.dumps(settings, ensure_ascii=False), job["id"], job["settings"]),
        )
    return db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()


def finish_cancelled_job(db, state, work, job_id):
    if work.resolve().parent == (state/'jobs').resolve() and not work.is_symlink():
        with suppress(OSError):
            shutil.rmtree(work)
    if not restore_preempted(db, job_id):
        error_state(db, job_id, 'cancelled', None)
        with db:
            db.execute('DELETE FROM cancel_requests WHERE job_id=?',(job_id,))
            db.execute('DELETE FROM job_retries WHERE job_id=?',(job_id,))


def next_job(
    db,
    state,
    engine=run_transcription,
    *,
    available_only=False,
    allow_automatic=True,
    config=None,
):
    if stopping(db):
        return False
    prune_immediate(db)
    if queue_paused(db) and not immediate_count(db):
        return False
    with db:
        db.execute(
            """UPDATE jobs SET state='ready',error=NULL,finished=NULL,updated=?
            WHERE state='failed' AND id IN
            (SELECT job_id FROM job_retries WHERE retry_at<=?)""",
            (time.time(), time.time()),
        )
    manual_selection = """(origin_job_id IS NOT NULL OR json_extract(settings,'$.folder_drop')=1
        OR json_extract(settings,'$.manual_retry')=1 OR id IN (SELECT job_id FROM immediate_jobs))"""
    selection = (
        f"""AND ({manual_selection} OR {WATCH_PATH}
        IN (SELECT path FROM folder_status WHERE available=1))"""
        if available_only
        else ""
    )
    if not allow_automatic:
        selection = f"AND {manual_selection}"
    selection += " AND (NOT EXISTS(SELECT 1 FROM queue_state WHERE paused=1) OR id IN (SELECT job_id FROM immediate_jobs))"
    job = db.execute(
        f"""SELECT jobs.* FROM jobs JOIN queue_positions q ON q.job_id=jobs.id
        WHERE state='ready' {selection} ORDER BY q.position,jobs.id LIMIT 1"""
    ).fetchone()
    if job is None:
        return False
    settings = json.loads(job["settings"])
    watched = (job["origin_job_id"] is None and not settings.get("folder_drop") and not settings.get("manual_retry")
               and (settings.get("watch_path") or settings.get("input_dir")))
    if config is not None and watched:
        current = read_settings(config)
        if watched not in enabled_watch_paths(current):
            reconcile_watched_jobs(db, current)
            return True
    try:
        job = keep_transcript_beside_source(db, job, settings, config)
    except FileExistsError as error:
        error_state(db, job["id"], "blocked", str(error))
        return True
    settings = json.loads(job["settings"])
    watch_path = settings.get("watch_path")
    manual = job["origin_job_id"] is not None
    if (
        watch_path
        and settings["create_output_subfolder"]
        and not settings.get("include_subfolders")
    ):
        settings["move_media"] = True
    if manual:
        incoming, completed = Path(job["source"]).parent, Path(job["completed_dir"])
    elif available_only or watch_path:
        try:
            incoming, completed = probe_job_paths(
                settings, parent=Path(job["source"]).parent
            )
        except (OSError, ValueError) as error:
            if settings.get("include_subfolders"):
                error_state(db, job["id"], "failed", str(error))
            else:
                record_folder(db, watch_path or settings["input_dir"], str(error))
            return True
    else:
        incoming, completed = active_folders(settings)
    if (
        Path(job["source"]).parent != incoming
        or Path(job["completed_dir"]) != completed
    ):
        error = "Die Ordner stimmen nicht mehr mit dem Auftrag überein."
        if available_only:
            error_state(db, job["id"], "failed", error)
            return True
        raise OSError(error)

    job_id = job["id"]
    work = state / "jobs" / str(job_id)
    local = work / ("media" + Path(job["source"]).suffix.lower())
    transcript = work / "transcript.txt"
    phase = "exporting" if job["text_hash"] else "copying"
    now = time.time()
    with db:
        db.execute("BEGIN IMMEDIATE")
        current = read_settings(config) if config is not None else {}
        if watched and current and watched not in enabled_watch_paths(current):
            return False
        if phase == "copying":
            settings.pop("execution_hardware", None)
            if WINDOWS and current.get("windows_cpu_only") and settings.get("hardware") == "cuda":
                settings["execution_hardware"] = "cpu"
            if (WINDOWS and settings.get("execution_hardware", settings.get("hardware")) == "cuda"
                    and db.execute("SELECT 1 FROM queue_graphics_hold").fetchone()):
                return False
        claimed = db.execute(
            f"""UPDATE jobs SET state=?, attempt=attempt+1, started=?, updated=?, finished=NULL,
            error=NULL, settings=? WHERE id=? AND state='ready' AND settings=?
            AND (NOT EXISTS(SELECT 1 FROM queue_state WHERE paused=1) OR id IN (SELECT job_id FROM immediate_jobs))
            AND NOT EXISTS(SELECT 1 FROM app_control WHERE stop_requested=1)
            AND id=(SELECT j.id FROM jobs j JOIN queue_positions q ON q.job_id=j.id
                WHERE j.state='ready' {selection} ORDER BY q.position,j.id LIMIT 1)""",
            (phase, now, now, json.dumps(settings, ensure_ascii=False), job_id, job["settings"]),
        ).rowcount
    if not claimed:
        return False

    def check_cancel():
        if cancellation_requested(db, job_id):
            raise JobCancelled('Auftrag abgebrochen.')

    def schedule_retry(delay):
        with db:
            db.execute("BEGIN IMMEDIATE")
            if config is not None and watched:
                try:
                    still_enabled = watched in enabled_watch_paths(read_settings(config))
                except (OSError, TypeError, ValueError):
                    still_enabled = False
                if not still_enabled:
                    db.execute("DELETE FROM job_retries WHERE job_id=?", (job_id,))
                    return
            db.execute("INSERT OR REPLACE INTO job_retries VALUES (?,?,?)",
                       (job_id, time.time() + delay, delay))

    try:
        check_cancel()
        work.mkdir(parents=True, exist_ok=True, mode=0o700)
        if manual and job_folders(job, settings) != (incoming, completed):
            raise OSError(
                "Die Auftragsordner stimmen nicht mehr mit dem Verlauf überein."
            )
        if not job["text_hash"]:
            if file_is_being_written(Path(job['source'])):
                raise MediaBusy('Aufnahme wird noch geschrieben oder ist gesperrt. Warte auf Dateifreigabe.')
            if not manual:
                _, existing_text=targets(job)
                if existing_text.parent == Path(job['source']).parent and existing_text.is_file():
                    existing_hash=digest(existing_text)
                    with db:
                        db.execute('BEGIN IMMEDIATE')
                        check_cancel()
                        remember_result(db,job_id,'existing',existing_text,existing_hash)
                        error_state(db,job_id,'existing',None)
                    return True
            local.with_suffix(".partial").unlink(missing_ok=True)
            media_hash = stage(job, local, cancelled=lambda: cancellation_requested(db,job_id))
            check_cancel()
            previous=None if manual else previously_transcribed(db,media_hash,job_id)
            cached_result=None
            if previous is not None:
                _, previous_text=targets(previous)
                previous_bytes=None
                if previous_text.is_file():
                    with regular_reader(previous_text) as reader:
                        previous_bytes=reader.read()
                text_valid=previous_bytes is not None and hashlib.sha256(previous_bytes).hexdigest()==previous['text_hash']
                if text_valid:
                    cached_result=previous_bytes.decode('utf-8')
                    with db:
                        remember_result(db,job_id,'reused',None,previous['text_hash'],previous['id'])
                else:
                    with db:
                        db.execute('BEGIN IMMEDIATE')
                        check_cancel()
                        remember_result(db,job_id,'duplicate',None,previous['text_hash'],previous['id'])
                        db.execute('UPDATE jobs SET media_hash=? WHERE id=?',(media_hash,job_id))
                        error_state(db,job_id,'duplicate',None)
                    return True
            if manual and settings.get("original_media_hash") not in (None, media_hash):
                raise SourceChanged(
                    "Die Aufnahme stimmt nicht mehr mit der Datei aus dem Verlauf überein."
                )
            with db:
                db.execute(
                    "UPDATE jobs SET state='transcribing',updated=? WHERE id=?",
                    (time.time(), job_id),
                )

            def report(phase, fraction):
                with db:
                    db.execute(
                        "UPDATE jobs SET phase=?, progress=?, updated=? WHERE id=?",
                        (phase, fraction, time.time(), job_id),
                    )

            language = (
                "auto-detect"
                if settings["language"] == "auto"
                else settings["language"]
            )
            measurements = {}
            result = cached_result if cached_result is not None else engine(
                local,
                language=language,
                speakers=settings["speakers"],
                speaker_count=settings["speaker_count"],
                hardware=settings.get("execution_hardware", settings.get("hardware", "cpu")),
                model=settings.get("model", WHISPER_MODEL),
                skip_silence=settings.get("skip_silence", False),
                dover_lap=settings.get("dover_lap", False),
                report=report,
                measurements=measurements,
                cancelled=lambda: poll_cancellation(state, job_id),
                gpu_budget_config=config,
            )
            check_cancel()
            transcript.unlink(missing_ok=True)
            publish_text(transcript, result)
            with db:
                db.execute('BEGIN IMMEDIATE')
                check_cancel()
                db.execute(
                    """UPDATE jobs SET state='exporting',media_hash=?,text_hash=?,updated=?,
                    phase=NULL,progress=NULL WHERE id=?""",
                    (media_hash, digest(transcript), time.time(), job_id),
                )
                if (audio_seconds := measurements.get("audio_seconds")) is not None:
                    db.execute(
                        """INSERT INTO audio_durations VALUES (?,?)
                        ON CONFLICT(job_id) DO UPDATE SET seconds=excluded.seconds""",
                        (job_id, audio_seconds),
                    )
                if details := measurements.get("speaker_details"):
                    db.execute(
                        """INSERT INTO speaker_diarization VALUES (?,?,?,?)
                        ON CONFLICT(job_id) DO UPDATE SET speaker_method=excluded.speaker_method,
                            speaker_passes=excluded.speaker_passes,speaker_note=excluded.speaker_note""",
                        (
                            job_id,
                            details["method"],
                            details["passes"],
                            details.get("note"),
                        ),
                    )
                if measurements:
                    db.execute(
                        """INSERT INTO transcription_measurements
                        (job_id,speech_seconds,speaker_seconds,peak_memory_bytes) VALUES (?,?,?,?)
                        ON CONFLICT(job_id) DO UPDATE SET speech_seconds=excluded.speech_seconds,
                            speaker_seconds=excluded.speaker_seconds,
                            peak_memory_bytes=excluded.peak_memory_bytes""",
                        (
                            job_id,
                            *(
                                measurements.get(key)
                                for key in (
                                    "speech_seconds",
                                    "speaker_seconds",
                                    "peak_memory_bytes",
                                )
                            ),
                        ),
                    )
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        settings = json.loads(job["settings"])
        job = keep_transcript_beside_source(db, job, settings, config)
        settings = json.loads(job["settings"])
        completed = Path(job["completed_dir"])
        if job_folders(job, settings) != (incoming, completed):
            raise OSError(
                "Die Auftragsordner haben sich während der Verarbeitung geändert."
            )
        if not manual and moves_media(settings):
            job = reserve_archive_export(db, job)
            settings = json.loads(job["settings"])
            completed = Path(job["completed_dir"])
            if settings.get("folder_drop") and job_folders(job, settings) != (
                incoming, completed
            ):
                raise OSError("Der Quellordner des abgelegten Auftrags hat sich geändert.")
        if not manual and moves_media(settings):
            if watch_path:
                completed.mkdir(exist_ok=True)
                if output_folder(incoming, settings) != completed:
                    raise OSError("Der Ausgabeordner hat sich verändert.")
            publish_job(db, job, transcript, local, text_first=bool(watch_path))
        else:
            publish_transcript_only(db, job, transcript)
        error_state(db, job_id, "done", None)
        with db:
            db.execute("DELETE FROM job_retries WHERE job_id=?", (job_id,))
        with suppress(OSError):
            transcript.unlink(missing_ok=True)
    except JobCancelled:
        finish_cancelled_job(db, state, work, job_id)
    except GraphicsTimeout as error:
        if not hold_after_graphics_timeout(db, job_id, str(error)):
            finish_cancelled_job(db, state, work, job_id)
    except MediaBusy as error:
        error_state(db,job_id,'failed',str(error))
        schedule_retry(5)
    except SourceChanged as error:
        error_state(db, job_id, "superseded", str(error))
    except FileExistsError as error:
        error_state(db, job_id, "blocked", str(error))
    except Exception as error:  # noqa: BLE001 - job boundary, retains cached export for manual retry
        # Cleanup errors must never replace a recorded cancellation/preemption.
        publication=db.execute('SELECT publication_started FROM jobs WHERE id=?',(job_id,)).fetchone()
        if cancellation_requested(db,job_id) and publication and not publication[0]:
            finish_cancelled_job(db, state, work, job_id)
            return True
        error_state(db, job_id, "failed", str(error) or type(error).__name__)
        if transient_file_error(error):
            previous = db.execute("SELECT delay FROM job_retries WHERE job_id=?", (job_id,)).fetchone()
            delay = min(900, previous[0] * 2) if previous else 10
            schedule_retry(delay)
        else:
            with db:
                db.execute("DELETE FROM job_retries WHERE job_id=?", (job_id,))
    finally:
        with suppress(OSError):
            local.unlink(missing_ok=True)
        with suppress(OSError):
            work.rmdir()  # Only an empty work directory; cached failures stay intact.
    return True


def transient_file_error(error):
    """Retry bounded-frequency I/O failures; never retry result collisions or ASR errors."""
    return isinstance(error, OSError) and (
        error.errno in {errno.EBUSY, errno.ETIMEDOUT, errno.ENOSPC,
                        errno.ENETDOWN, errno.ENETUNREACH, errno.ECONNRESET}
        # The Windows CRT reports an exclusive sharing lock as errno 13
        # without preserving WinError 32. Retry without changing any rights.
        or (WINDOWS and error.errno == errno.EACCES)
        or getattr(error, "winerror", None) in {32, 33, 53, 54, 55, 59, 64, 67, 121, 1231, 1232}
    )


def recover(db, state, *, verify_exports=True):
    jobs = db.execute(
        "SELECT * FROM jobs WHERE state IN ('copying','transcribing','exporting')"
    ).fetchall()
    for job in jobs:
        work = state / "jobs" / str(job["id"])
        if cancellation_requested(db, job['id']) and not job['publication_started']:
            if work.resolve().parent == (state/'jobs').resolve() and not work.is_symlink():
                with suppress(OSError):
                    shutil.rmtree(work)
            if not restore_preempted(db, job['id']):
                error_state(db,job['id'],'cancelled',None)
                with db:
                    db.execute('DELETE FROM cancel_requests WHERE job_id=?',(job['id'],))
                    db.execute('DELETE FROM job_retries WHERE job_id=?',(job['id'],))
            continue
        for leftover in work.glob("media.*"):
            leftover.unlink(missing_ok=True)
        for leftover in work.glob("transcription-*"):
            if leftover.is_dir() and not leftover.is_symlink():
                shutil.rmtree(leftover)
        if WINDOWS and job["state"] == "transcribing":
            settings = json.loads(job["settings"])
            if settings.get("execution_hardware", settings.get("hardware")) == "cuda":
                if evidence := graphics_timeout_since(job["started"]):
                    if hold_after_graphics_timeout(db, job["id"], evidence):
                        continue
        if verify_exports and job["publication_started"] and job["text_hash"]:
            try:
                settings = json.loads(job["settings"])
                moving = job["origin_job_id"] is None and moves_media(settings)
                incoming, completed = job_folders(job, settings)
                source = Path(job["source"])
                media, text = targets(job)
                if (
                    source.parent == incoming
                    and media.parent == completed
                    and (not moving or not os.path.lexists(source))
                    and matches(media if moving else source, job["media_hash"])
                    and matches(text, job["text_hash"])
                ):
                    if moving:
                        finish_retirement(
                            retirement_dir(db, job), source, job["media_hash"]
                        )
                    error_state(db, job["id"], "done", None)
                    (work / "transcript.txt").unlink(missing_ok=True)
                    continue
            except (OSError, ValueError):
                pass
        error_state(
            db,
            job["id"],
            "ready",
            "Auftrag unterbrochen. Automatische Wiederaufnahme nach Dienststart.",
        )
        with db:
            db.execute("UPDATE jobs SET finished=NULL WHERE id=?", (job["id"],))


def retry(db, job_id):
    with db:
        changed = db.execute(
            """UPDATE jobs SET state='ready', updated=?,error=NULL,settings=json_set(settings,'$.manual_retry',json('true'))
            WHERE id=? AND state IN ('failed','blocked','cancelled')""",
            (time.time(), job_id),
        ).rowcount
        if changed:
            db.execute("DELETE FROM job_retries WHERE job_id=?", (job_id,))
    if not changed:
        raise ValueError("Dieser Auftrag befindet sich nicht im Fehlerzustand.")


def retranscribe(db, job_id, settings):
    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if job is None or job["state"] not in ("done", "failed", "blocked", "cancelled", "existing", "duplicate"):
        raise ValueError("Wähle einen abgeschlossenen oder fehlgeschlagenen Auftrag.")
    recorded = Path(job["source"])
    archived, _ = targets(job)
    moving = job["origin_job_id"] is None and moves_media(json.loads(job["settings"]))
    candidates = (archived, recorded) if moving else (recorded, archived)
    available = []
    for media in dict.fromkeys(candidates if job["media_hash"] else (recorded,)):
        try:
            metadata = media.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_size == job["size"]
            and (job["media_hash"] or metadata.st_mtime_ns == job["mtime_ns"])
        ):
            available.append((media, metadata))
    if len(available) > 1:
        available = [item for item in available if matches(item[0], job["media_hash"])]
    if not available:
        raise FileNotFoundError(
            "Die Aufnahme aus dem Verlauf wurde am Quell- und Zielpfad nicht gefunden."
        )
    media, metadata = available[0]

    destination = Path(job["completed_dir"])
    if settings.get("include_subfolders") or not destination.is_dir():
        destination = media.parent
    profile = {**settings, "original_media_hash": job["media_hash"]}
    origin = job["origin_job_id"] or job_id
    now = time.time()
    with db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute(
            "SELECT 1 FROM jobs WHERE id=? AND state IN ('done','failed','blocked','cancelled','existing','duplicate')",
            (job_id,),
        ).fetchone():
            raise ValueError(
                "Der Auftrag ist inzwischen nicht mehr im Verlauf verfügbar."
            )
        if db.execute(
            """SELECT 1 FROM jobs WHERE origin_job_id=?
            AND state IN ('ready','copying','transcribing','exporting')""",
            (origin,),
        ).fetchone():
            raise ValueError(
                "Für diese Aufnahme ist bereits eine neue Transkription eingeplant."
            )
        cursor = db.execute(
            """INSERT INTO jobs(source,size,mtime_ns,completed_dir,settings,detected,updated,state,origin_job_id)
            VALUES (?,?,?,?,?,?,?,'ready',?)""",
            (
                str(media),
                metadata.st_size,
                metadata.st_mtime_ns,
                str(destination),
                json.dumps(profile, ensure_ascii=False),
                now,
                now,
                origin,
            ),
        )
        return cursor.lastrowid


def clear_history(db, state):
    state=state.resolve()
    removed=state/f'.history-clear-{uuid.uuid4().hex}'
    assert removed.parent==state and not removed.exists()
    with search_storage_lock(state):
        moved=[]
        db.execute('PRAGMA secure_delete=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute("SELECT 1 FROM jobs WHERE state IN ('copying','transcribing','exporting')").fetchone():
                raise ValueError('Der Verlauf kann nach Abschluss des aktiven Auftrags geleert werden.')
            names=['jobs','record-delete','transcript-search.sqlite3','transcript-search.sqlite3-wal',
                   'transcript-search.sqlite3-shm','content-search-result.json']
            artifacts=[state/name for name in names]+list(state.glob('.search-*'))
            for artifact in artifacts:
                if artifact.exists() or artifact.is_symlink():
                    if is_reparse_point(artifact.lstat()) or artifact.is_symlink():
                        raise ValueError('Die lokalen Cachepfade dürfen keine Verknüpfungen sein.')
                    removed.mkdir(exist_ok=True,mode=0o700)
                    artifact.rename(removed/artifact.name)
                    moved.append(artifact)
            for table in ('job_retries','events','transcription_measurements','speaker_diarization',
                          'audio_durations','copy_claims','copy_exports','known_results','queue_positions',
                          'cancel_requests','preemptions','immediate_jobs','drop_batches','folder_status',
                          'folder_refresh','connection','service','queue_graphics_hold','retained_media','jobs'):
                db.execute(f'DELETE FROM {table}')
            # Retain monotonic job IDs and the user's pause, never old file/search records.
            db.execute('UPDATE storage_state SET generation=generation+1 WHERE id=1')
            db.commit()
        except BaseException:
            try:
                for artifact in reversed(moved):
                    (removed/artifact.name).rename(artifact)
                if removed.exists():
                    removed.rmdir()
            finally:
                db.rollback()
            raise
        for cached in state.glob('.history-clear-*'):
            if is_reparse_point(cached.lstat()) or cached.is_symlink():
                raise ValueError('Ein lokaler Bereinigungsrest ist eine Verknüpfung und wurde nicht gelöscht.')
            assert cached.resolve().is_relative_to(state) and cached.name.startswith('.history-clear-')
            try:
                shutil.rmtree(cached)
            except OSError as error:
                raise RuntimeError('Auftragsdaten zurückgesetzt; ein lokaler Cache konnte noch nicht entfernt werden. Bitte Bereinigung erneut ausführen.') from error
        db.execute('VACUUM')
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')


def scan_once(db, settings):
    generation=storage_generation(db)
    try:
        scan(db, settings, inspect=inspect_folders_with_deadline,generation=generation)
    except (OSError, ValueError) as error:
        service_state(
            db, "unavailable" if settings["monitoring"] else "paused", str(error)
        )
        connection_state(db, False, str(error))
        return False
    if generation!=storage_generation(db):
        return False
    connection_state(db, True)
    return True


def record_folder(db, path, error=None, *, partial=False):
    incident = uuid.uuid4().hex if error is not None else None
    with db:
        db.execute(
            """INSERT INTO folder_status VALUES (?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET updated=excluded.updated,available=excluded.available,
                error=excluded.error,
                incident=CASE WHEN excluded.available THEN NULL
                              ELSE COALESCE(folder_status.incident,excluded.incident) END""",
            (path, time.time(), error is None or partial, error, incident),
        )


def probe_job_paths(settings, *, parent=None):
    incoming, completed, _, _ = inspect_folders_with_deadline(
        {
            **settings,
            "monitoring": False,
            "probe_write": False,
            "source_parent": str(parent) if parent is not None else None,
        }
    )
    return Path(incoming), Path(completed)


def probe_folder(settings, path):
    return inspect_folders_with_deadline(folder_profile(settings, path))


def probe_pending_folders(db, settings, deadlines, retries, *, config=None):
    generation=storage_generation(db)
    paths = enabled_watch_paths(settings)
    requested = set()
    if db.execute("SELECT 1 FROM folder_refresh LIMIT 1").fetchone():
        with db:
            requested = {
                row[0]
                for row in db.execute("DELETE FROM folder_refresh RETURNING path")
            }
    due = [
        path
        for path in paths
        if path in requested or time.monotonic() >= deadlines.get(path, 0)
    ]
    if due:
        with ThreadPoolExecutor(max_workers=min(len(due), 8)) as pool:
            checking = {pool.submit(probe_folder, settings, path): path for path in due}
            for task in as_completed(checking):
                path = checking[task]
                delay = settings["interval_seconds"]
                try:
                    warning = scan(
                        db,
                        folder_profile(settings, path),
                        inspect=lambda _, result=task: result.result(),
                        generation=generation,
                        config=config,
                    )
                except (OSError, ValueError) as error:
                    if generation!=storage_generation(db):
                        continue
                    record_folder(db, path, str(error))
                    delay = next(
                        retries.setdefault(path, iter(STARTUP_RETRY_DELAYS)), delay
                    )
                else:
                    if generation!=storage_generation(db):
                        continue
                    record_folder(db, path, warning, partial=warning is not None)
                    retries[path] = iter(())
                deadlines[path] = time.monotonic() + delay
    if generation!=storage_generation(db):
        return False
    active = set(paths)
    available = sum(
        row[0] in active
        for row in db.execute("SELECT path FROM folder_status WHERE available=1")
    )
    connected = available == len(paths) and bool(paths)
    state = (
        ("active" if available else "unavailable")
        if paths and settings["monitoring"]
        else "paused"
    )
    latest_connection = db.execute("SELECT available FROM connection").fetchone()
    latest_service = db.execute("SELECT state,error FROM service").fetchone()
    if due or latest_connection is None or latest_connection[0] != connected:
        connection_state(db, connected)
    if due or latest_service is None or tuple(latest_service) != (state, None):
        service_state(db, state)
    return available > 0


def poll_config(db, config, stop, connected, multiple=None):
    generation=storage_generation(db)
    previous = None
    deadline = 0
    retries = iter(STARTUP_RETRY_DELAYS)
    folder_deadlines, folder_retries = {}, {}
    while not stop.is_set():
        try:
            current = read_settings(config)
        except (OSError, TypeError, ValueError) as error:
            service_state(db, "unavailable", str(error))
            connection_state(db, False, str(error))
            connected.clear()
            previous = None
            stop.wait(1)
            continue
        revision=storage_generation(db)
        if revision!=generation:
            generation=revision
            connected.clear()
            previous=current
            deadline=time.monotonic()+current['interval_seconds']
            folder_deadlines={path:deadline for path in current.get('folders',[])}
            folder_retries.clear()
            retries=iter(STARTUP_RETRY_DELAYS)
        if "folders" in current:
            if multiple is not None:
                multiple.set()
            if current != previous:
                connected.clear()
                updated_paths = set(enabled_watch_paths(current))
                reconcile_watched_jobs(db, current)
                with db:
                    for row in db.execute("SELECT path FROM folder_status").fetchall():
                        if row["path"] not in updated_paths:
                            db.execute(
                                "DELETE FROM folder_status WHERE path=?", (row["path"],)
                            )
                        else:
                            # Recheck changed settings before accepting new jobs.
                            db.execute(
                                "UPDATE folder_status SET available=0 WHERE path=?",
                                (row["path"],),
                            )
                folder_deadlines.clear()
                folder_retries = {
                    path: remaining
                    for path, remaining in folder_retries.items()
                    if path in updated_paths
                }
                previous = current
            if (
                probe_pending_folders(db, current, folder_deadlines, folder_retries, config=config)
                and current["monitoring"]
            ):
                connected.set()
            else:
                connected.clear()
            stop.wait(1)
            continue
        if multiple is not None:
            multiple.clear()
        if previous is not None and "folders" in previous:
            with db:
                db.execute("DELETE FROM folder_status")
        if current != previous or time.monotonic() >= deadline:
            interval = current["interval_seconds"]
            if scan_once(db, current):
                connected.set()
                retries = iter(())
                delay = interval
            else:
                connected.clear()
                delay = next(retries, interval)
            previous = current
            deadline = time.monotonic() + delay
        stop.wait(1)


def run(state, config, *, once):
    settings = read_settings(config)
    stop = threading.Event()
    connected = threading.Event()
    multiple = threading.Event()
    if "folders" in settings:
        multiple.set()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())

    def poll():
        while not stop.is_set():
            try:
                with closing(database(state)) as db:
                    poll_config(db, config, stop, connected, multiple)
                return
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                connected.clear()
                traceback.print_exc()
                stop.wait(5)

    with (state / "service.lock").open("a") as lock, closing(database(state)) as db:
        try:
            lock_service(lock)
        except BlockingIOError as error:
            raise RuntimeError(
                "Der Dienst läuft bereits für diese Auftragsdatenbank."
            ) from error
        with db:
            db.execute("DELETE FROM connection")
        recover(db, state)
        lifetime=threading.Thread(target=watch_owner,args=(state,stop),name='app-owner',daemon=True)
        if not once:
            lifetime.start()
        if once:
            if multiple.is_set():
                reconcile_watched_jobs(db, settings)
            available = (
                probe_pending_folders(db, settings, {}, {}, config=config) and settings["monitoring"]
                if multiple.is_set()
                else scan_once(db, settings)
            )
            try:
                next_job(
                    db,
                    state,
                    available_only=multiple.is_set(),
                    allow_automatic=available,
                    config=config,
                )
            except (OSError, ValueError) as error:
                service_state(db, "unavailable", str(error))
            return
        scanner = threading.Thread(target=poll, name="scanner")
        scanner.start()
        try:
            while not stop.is_set():
                try:
                    if next_job(
                        db,
                        state,
                        available_only=multiple.is_set(),
                        allow_automatic=connected.is_set(),
                        config=config,
                    ):
                        continue
                except (OSError, ValueError) as error:
                    service_state(db, "unavailable", str(error))
                    stop.wait(settings["interval_seconds"])
                stop.wait(1)
        finally:
            stop.set()
            scanner.join()
            service_state(db, "stopped")


def is_running(state):
    return lock_held(state / "service.lock") or lock_held(state / "supervisor.lock")


def lock_held(path):
    with path.open("a") as lock:
        try:
            lock_service(lock)
        except BlockingIOError:
            return True
    return False


def supervise(state, model_data, config):
    with closing(RollingLog(state / "service.log")) as log:
        with redirect_stdout(log), redirect_stderr(log):
            supervise_worker(state, model_data, config, log)


def supervise_worker(state, model_data, config, log):
    """Restart an unexpectedly exited service without requiring an open GUI."""
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    with (state / "supervisor.lock").open("a") as lock:
        try:
            lock_service(lock)
        except BlockingIOError:
            return
        delay = 2
        lifetime=threading.Thread(target=watch_owner,args=(state,stop),name='app-owner',daemon=True)
        lifetime.start()
        while not stop.is_set():
            started = time.monotonic()
            try:
                with child_process(
                    [sys.executable, "-BEs", "-Xutf8", str(Path(__file__).resolve()),
                     "--state-dir", str(state), "--model-data", str(model_data),
                     "run", str(config)],
                    cancellable=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    **process_options(),
                ) as child:
                    def copy_output(stream=child.stdout):
                        try:
                            while line := stream.readline(64_000):
                                log.write(line)
                        except (OSError, ValueError):
                            pass  # The process context closes the pipe during shutdown.

                    reader = threading.Thread(target=copy_output, daemon=True)
                    reader.start()
                    while child.poll() is None and not stop.wait(0.5):
                        pass
                    if stop.is_set() and child.poll() is None:
                        try:
                            child.wait(timeout=6)
                        except subprocess.TimeoutExpired:
                            child.cancel_tree()
                    code = child.wait()
                reader.join(timeout=10)
                if stop.is_set():
                    return
                print(f"Hintergrunddienst beendet (Code {code}); Neustart in {delay} s.",
                      file=sys.stderr, flush=True)
            except (OSError, ValueError, RuntimeError):
                traceback.print_exc()
            if time.monotonic() - started >= 60:
                delay = 2
            stop.wait(delay)
            delay = min(300, delay * 2)


def start_in_background(state, model_data, config, *, owner_pid=None, owner_created=None):
    read_settings(config)
    with lifecycle_lock(state),closing(database(state)) as db:
        register_owner(db,owner_pid,owner_created)
        _start_in_background(state,model_data,config)


def _start_in_background(state,model_data,config):
    if is_running(state):
        return
    with (state / ("bootstrap.log" if WINDOWS else "service.log")).open("ab") as log:
        subprocess.Popen(
            [
                sys.executable,
                "-BEs",
                "-Xutf8",
                str(Path(__file__).resolve()),
                "--state-dir",
                str(state),
                "--model-data",
                str(model_data.resolve()),
                "supervise",
                str(config.resolve()),
            ],
            **process_options(background=True),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )


def history_search_scope(db, query, content_matches=False):
    query = query.strip()
    if not query:
        return '', ()
    def paths(source, completed, origin, identifier, known):
        media = os.path.join(completed, os.path.basename(source))
        stem = os.path.splitext(os.path.basename(source))[0]
        transcript = os.path.splitext(media)[0] + '.txt'
        if origin:
            name = f'{stem} (Neu {identifier}).txt'
            transcript = os.path.join(completed, name if len(name.encode('utf-8')) <= 255 else f'Neutranskription {identifier}.txt')
        return '\n'.join((source, media, transcript, known or '')).replace('\\', '/').casefold()
    db.create_function('history_search_paths', 5, paths, deterministic=True)
    pattern = query.replace('\\', '/').casefold().replace('!', '!!').replace('%', '!%').replace('_', '!_')
    pattern = '%' + pattern.replace('*', '%').replace('?', '_') + '%'
    clause = "history_search_paths(j.source,j.completed_dir,j.origin_job_id,j.id,k.transcript_path) LIKE ? ESCAPE '!'"
    if content_matches:
        clause += ' OR j.id IN (SELECT job_id FROM temp.content_matches)'
    return ' AND (' + clause + ')', (pattern,)


def history_counts(db, *, search='', content_matches=False):
    clause, arguments = history_search_scope(db, search, content_matches)
    keys=list(HISTORY_FILTERS)
    aggregates=','.join(f'COALESCE(SUM({HISTORY_FILTERS[key]}),0)' for key in keys)
    counts=db.execute('SELECT '+aggregates+' FROM jobs j LEFT JOIN known_results k ON k.job_id=j.id WHERE 1'+clause,arguments).fetchone()
    return dict(zip(keys,counts))


def history_jobs(db, order, limit, *, terminal_only=False, history_filter="all", search='', content_matches=False, offset=0):
    direction = "ASC" if order == "asc" else "DESC"
    clause, arguments = history_search_scope(db, search, content_matches)
    scope = HISTORY_FILTERS[history_filter] if terminal_only or history_filter != 'all' else '1'
    return db.execute(
        f"""SELECT j.*, m.speech_seconds, m.speaker_seconds, m.peak_memory_bytes,
        d.speaker_method, d.speaker_passes, d.speaker_note,
        a.seconds AS audio_seconds,
        k.transcript_path AS known_transcript_path,k.prior_job_id,k.kind AS result_kind,
        (SELECT recorded FROM events
         WHERE job_id=j.id AND state='transcribing'
         ORDER BY id DESC LIMIT 1) AS transcription_started
        FROM jobs AS j LEFT JOIN transcription_measurements AS m ON m.job_id=j.id
        LEFT JOIN speaker_diarization AS d ON d.job_id=j.id
        LEFT JOIN audio_durations AS a ON a.job_id=j.id
        LEFT JOIN known_results k ON k.job_id=j.id
        WHERE {scope}{clause}
        ORDER BY j.updated {direction}, j.id {direction} LIMIT ? OFFSET ?""",
        (*arguments, limit, max(0, offset)),
    ).fetchall()


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--state-dir", type=Path, default=DEFAULT_DATA.parent / "service")
    cli.add_argument("--model-data", type=Path, default=DEFAULT_DATA)
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect-folders", help=argparse.SUPPRESS)
    commands.add_parser("prepare-app-data", help=argparse.SUPPRESS)
    for name in ("check", "run", "start", "supervise"):
        command = commands.add_parser(name)
        command.add_argument("config", type=Path)
        if name == "run":
            command.add_argument("--once", action="store_true")
        if name == 'start':
            command.add_argument('--owner-pid',type=int)
            command.add_argument('--owner-created',type=float)
        if name == "check":
            command.add_argument("--folder")
    commands.add_parser("validate-settings").add_argument("config", type=Path)
    setup = commands.add_parser("setup-models")
    setup.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    setup.add_argument("--no-speakers", action="store_true")
    refresh_command = commands.add_parser("refresh-folder")
    refresh_command.add_argument("config", type=Path)
    refresh_command.add_argument("folder")
    commands.add_parser("rescan-folders").add_argument("config", type=Path)
    commands.add_parser("reconcile-folders").add_argument("config", type=Path)
    status_command = commands.add_parser("status")
    status_command.add_argument("--limit", type=int, default=-1)
    status_command.add_argument("--offset", type=int, default=0)
    status_command.add_argument("--order", choices=("asc", "desc"), default="desc")
    status_command.add_argument("--filter", dest="history_filter", choices=HISTORY_FILTERS, default="all")
    status_command.add_argument('--search', default='')
    status_command.add_argument('--content-results', type=Path)
    status_command.add_argument('--content-token')
    autostart = commands.add_parser("autostart")
    autostart.add_argument("mode", choices=("on", "off", "preview"))
    autostart.add_argument("config", type=Path)
    commands.add_parser("retry").add_argument("job_id", type=int)
    commands.add_parser('cancel-job').add_argument('job_id',type=int)
    commands.add_parser('cancel-queue')
    commands.add_parser('start-queue')
    commands.add_parser('stop-queue')
    commands.add_parser('queue-pause').add_argument('mode',choices=('on','off'))
    move=commands.add_parser('move-queue')
    move.add_argument('job_id',type=int)
    move.add_argument('before_id',type=int)
    move.add_argument('--after',action='store_true')
    relative = commands.add_parser('move-queue-relative')
    relative.add_argument('job_id',type=int)
    relative.add_argument('direction',choices=('first','up','down','last'))
    rerun = commands.add_parser("retranscribe")
    rerun.add_argument("job_id", type=int)
    rerun.add_argument("config", type=Path)
    commands.add_parser("clear-history")
    commands.add_parser('prepare-delete-record').add_argument('job_ids',type=int,nargs='+')
    delete_record = commands.add_parser('delete-record')
    delete_record.add_argument('token')
    delete_record.add_argument('--keep-original',action='store_true')
    commands.add_parser('discard-delete-record').add_argument('token')
    commands.add_parser('stop')
    commands.add_parser("enqueue-folders").add_argument("config", type=Path)
    commands.add_parser('prepare-drop').add_argument('config', type=Path)
    drop_command = commands.add_parser('resolve-drop')
    drop_command.add_argument('token')
    drop_command.add_argument('action', choices=('queue','front','retranscribe','immediate','ignore'))
    args = cli.parse_args(argv)
    try:
        if args.command == "prepare-app-data":
            if WINDOWS:
                return 0
            import app_upgrade

            if app_upgrade.migrate(
                args.state_dir.parent, Path(__file__).resolve().parents[3]
            ):
                print("resume")
            return 0
        if args.command == "validate-settings":
            read_settings(args.config)
            return 0
        if args.command == "setup-models":
            configure_runtime(args.model_data, setup=True)
            setup_models(
                args.model_data.resolve(), args.model, speakers=not args.no_speakers
            )
            return 0
        if args.command == "check":
            settings = {**read_settings(args.config), "monitoring": False}
            if "folders" in settings:
                paths = settings["folders"]
                if args.folder is not None:
                    if args.folder not in paths:
                        raise ValueError("Der Ordner ist nicht in der Liste.")
                    paths = [args.folder]
                checks = []
                if paths:
                    with ThreadPoolExecutor(max_workers=min(len(paths), 8)) as pool:
                        tasks = {
                            pool.submit(probe_folder, settings, p): p for p in paths
                        }
                        for task in as_completed(tasks):
                            error = None
                            try:
                                task.result()
                            except (OSError, ValueError) as failure:
                                error = str(failure)
                            checks.append(
                                {
                                    "path": tasks[task],
                                    "available": error is None,
                                    "error": error,
                                }
                            )
                print(json.dumps(checks, ensure_ascii=False))
                return 0
            incoming, completed, _, _ = inspect_folders_with_deadline(settings)
            print(f"Eingang: {incoming}\nFertiggestellt: {completed}")
            return 0
        if args.command == "inspect-folders":
            print(json.dumps(inspect_folders(json.load(sys.stdin)), ensure_ascii=True))
            return 0
        state = args.state_dir.resolve()
        if args.command=='stop' and (state/'jobs.sqlite3').is_file():
            with closing(database(state)) as db:
                result=stop_service(db,state,Path(__file__).resolve())
                if result['database_stop_recorded']:
                    try:
                        recover(db,state,verify_exports=False)
                        service_state(db,'stopped')
                    except (OSError,sqlite3.Error):
                        result['recovery_deferred']=True
            print(json.dumps(result))
            return 0
        initialise(state)
        if args.command in ("run", "supervise"):
            configure_runtime(args.model_data)
            if args.command == "supervise":
                supervise(state, args.model_data.resolve(), args.config.resolve())
            else:
                run(state, args.config, once=args.once)
            return 0
        if args.command == "start":
            start_in_background(state,args.model_data,args.config,owner_pid=args.owner_pid,owner_created=args.owner_created)
            return 0
        if args.command=='stop':
            with closing(database(state)) as db:
                result=stop_service(db,state,Path(__file__).resolve())
                recover(db,state,verify_exports=False)
                service_state(db,'stopped')
            print(json.dumps(result))
            return 0
        if args.command == "autostart":
            if WINDOWS:
                raise ValueError(
                    "Der Windows-Anmeldestart wird über die VoxDrop-Oberfläche verwaltet."
                )
            import plistlib

            config = args.config.resolve()
            definition = login_agent.definition(
                Path(__file__).resolve(), config, state, args.model_data.resolve()
            )
            if args.mode == "preview":
                sys.stdout.buffer.write(plistlib.dumps(definition))
            else:
                if args.mode == "on":
                    read_settings(config)
                login_agent.update(args.mode == "on", definition)
            return 0
        with closing(database(state)) as db:
            if args.command in ('enqueue-folders', 'prepare-drop'):
                settings = read_settings(args.config)
                folders = json.loads(args.config.read_text(encoding="utf-8")).get(
                    "dropped_folders"
                )
                if not isinstance(folders, list) or not all(
                    isinstance(folder, str) for folder in folders
                ):
                    raise ValueError("Eine Liste abgelegter Dateien und Ordner ist erforderlich.")
                operation = prepare_drop if args.command == 'prepare-drop' else enqueue_folders
                print(json.dumps(operation(db, settings, folders), ensure_ascii=True))
            elif args.command == 'resolve-drop':
                print(json.dumps(resolve_drop(db, args.token, args.action), ensure_ascii=True))
            elif args.command == "retry":
                retry(db, args.job_id)
            elif args.command == 'cancel-job':
                print(cancel_job(db,args.job_id))
            elif args.command == 'cancel-queue':
                print(cancel_queue(db))
            elif args.command == 'queue-pause':
                set_queue_paused(db,args.mode=='on')
            elif args.command == 'start-queue':
                print(json.dumps(dict(started=start_queue(db))))
            elif args.command == 'stop-queue':
                print(json.dumps(stop_queue(db)))
            elif args.command == 'move-queue':
                move_queue_item(db,args.job_id,args.before_id,after=args.after)
            elif args.command == 'move-queue-relative':
                move_queue_relative(db,args.job_id,args.direction)
            elif args.command == "retranscribe":
                print(retranscribe(db, args.job_id, read_settings(args.config)))
            elif args.command == "clear-history":
                clear_history(db, state)
            elif args.command in ('prepare-delete-record','delete-record','discard-delete-record'):
                import record_delete
                if args.command=='prepare-delete-record':result=record_delete.prepare(db,state,*args.job_ids)
                elif args.command=='delete-record':result=record_delete.execute(db,state,args.token,keep_original=args.keep_original)
                else:record_delete.discard(state,args.token);result={}
                print(json.dumps(result,ensure_ascii=True))
            elif args.command == "reconcile-folders":
                print(reconcile_watched_jobs(db, read_settings(args.config)))
            elif args.command == "rescan-folders":
                request_watched_rescan(db, read_settings(args.config))
            elif args.command == "refresh-folder":
                if args.folder not in read_settings(args.config).get("folders", ()):
                    raise ValueError("Der Ordner ist nicht in der gespeicherten Liste.")
                with db:
                    db.execute(
                        "INSERT OR IGNORE INTO folder_refresh VALUES (?)",
                        (args.folder,),
                    )
            else:
                status = db.execute(
                    "SELECT updated,state,error FROM service"
                ).fetchone()
                connection = db.execute(
                    "SELECT available,error FROM connection"
                ).fetchone()
                graphics_hold = db.execute("SELECT reason FROM queue_graphics_hold WHERE id=1").fetchone()
                content_matches = False
                if args.content_results:
                    content = json.loads(args.content_results.read_text(encoding='utf-8'))
                    if (not args.content_token or content.get('token') != args.content_token
                            or content.get('query') != args.search or content.get('generation')!=storage_generation(db)):
                        raise ValueError('Die Detailsuche ist nicht mehr aktuell. Bitte erneut starten.')
                    identifiers = content.get('job_ids', [])
                    if not isinstance(identifiers, list) or any(type(identifier) is not int for identifier in identifiers):
                        raise ValueError('Ungültiges Detailsuchergebnis. Bitte erneut starten.')
                    db.execute('CREATE TEMP TABLE content_matches(job_id INTEGER PRIMARY KEY)')
                    db.executemany('INSERT OR IGNORE INTO content_matches VALUES (?)', ((identifier,) for identifier in identifiers))
                    content_matches = True
                jobs = history_jobs(db, args.order, args.limit, terminal_only=True,
                                    history_filter=args.history_filter, search=args.search, content_matches=content_matches, offset=args.offset)
                current = db.execute(
                    """SELECT j.*, EXISTS(SELECT 1 FROM cancel_requests c WHERE c.job_id=j.id)
                    AS cancel_requested FROM jobs j WHERE state IN ('copying','transcribing','exporting')"""
                ).fetchone()
                waiting = db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE state IN ('seen','ready')"
                ).fetchone()[0]
                print(
                    json.dumps(
                        {
                            "service": dict(status) if status else None,
                            "folders": [
                                {**dict(folder), "available": bool(folder["available"])}
                                for folder in db.execute(
                                    "SELECT * FROM folder_status ORDER BY path"
                                )
                            ],
                            "connection": {
                                "available": bool(connection["available"]),
                                "error": connection["error"],
                            }
                            if connection
                            else None,
                            "startup_retry_delays": STARTUP_RETRY_DELAYS,
                            "running": is_running(state),
                            "autostart": login_agent.agent_path().is_file(),
                            "waiting": waiting,
                            "queue_paused": queue_paused(db),
                            "graphics_hold": graphics_hold[0] if graphics_hold else "",
                            "immediate_count": immediate_count(db),
                            "queue": [dict(row) for row in queue_jobs(db)],
                            "current": dict(current) if current else None,
                            "jobs": [dict(job) for job in jobs],
                            "history_counts": history_counts(db, search=args.search, content_matches=content_matches),
                            "global_history_counts": history_counts(db),
                            "stored_jobs": db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
                            "has_stored_data": bool(db.execute('SELECT 1 FROM jobs UNION ALL SELECT 1 FROM drop_batches LIMIT 1').fetchone()
                                or (state/'transcript-search.sqlite3').exists() or (state/'content-search-result.json').exists()
                                or next(state.glob('.history-clear-*'),None) is not None),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        return 0
    except (OSError, TypeError, ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
