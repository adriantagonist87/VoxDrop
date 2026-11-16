"""Persistent, single-job background worker for the EINGANG/FERTIGGESTELLT workflow."""

import argparse
import ctypes
import errno
import fcntl
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
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing, contextmanager, suppress
from functools import lru_cache
from pathlib import Path

import login_agent
from smb_paths import resolve_folder, smb_mounts, validate_folder_path
from smb_transcriber import (
    DEFAULT_DATA,
    DEFAULT_MODEL,
    HARDWARE,
    MEDIA_EXTENSIONS,
    MODELS,
    WHISPER_MODEL,
    configure_runtime,
    publish_text,
    setup_models,
)
from transcription_worker import run_transcription

STARTUP_RETRY_DELAYS = (10, 30, 60)
SMB_PROBE_TIMEOUT = 8

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
        "hardware": "metal",
        "model": DEFAULT_MODEL,
        "skip_silence": False,
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
        create = values.get("create_output_subfolder", False)
        if type(create) is not bool:
            raise ValueError("Unterordner erstellen muss ein- oder ausgeschaltet sein.")
        name = values.get("output_subfolder", "_FERTIGGESTELLT")
        if create:
            validate_subfolder(name)
        elif not isinstance(name, str):
            name = "_FERTIGGESTELLT"
        settings.update(
            folders=paths, create_output_subfolder=create, output_subfolder=name
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
    for name in ("monitoring", "speakers", "require_smb", "skip_silence", "dover_lap"):
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
        raise ValueError("Erlaubte Rechengeräte sind metal und cpu.")
    if settings["model"] not in MODELS:
        raise ValueError("Erlaubte Transkriptionsmodelle sind Qwen und Whisper.")
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
    ):
        raise ValueError(
            "Für den Unterordner ist ein einzelner Ordnername erforderlich."
        )


def folder_profile(settings, path):
    profile = {key: value for key, value in settings.items() if key != "folders"}
    return {**profile, "watch_path": path, "require_smb": False, "scope_dir": None}


def output_folder(source, settings):
    if not settings["create_output_subfolder"]:
        return source
    name = settings["output_subfolder"]
    validate_subfolder(name)
    output = source / name
    try:
        metadata = output.lstat()
    except FileNotFoundError:
        return output
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_dev != source.stat().st_dev:
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
    if any(state.is_relative_to(root) for _, _, root in smb_mounts()):
        raise ValueError(
            "Datenbank und temporäre Medienkopie benötigen einen lokalen Pfad."
        )
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with closing(database(state)) as db:
        db.execute("PRAGMA journal_mode = WAL")
        upgrade_jobs(db)
        db.executescript(SCHEMA)


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
        with tempfile.NamedTemporaryFile(
            dir=folder, prefix=".smb-transcriber-write-"
        ) as probe:
            probe.write(b"1")
            probe.flush()
    except OSError as error:
        raise OSError(
            f"Ordner nicht beschreibbar: {folder} ({error.strerror or error})"
        ) from error


def inspect_folders(settings):
    incoming, completed = active_folders(settings)
    if settings.get("watch_path") and settings.get("probe_write", True):
        verify_writable(incoming)
        if completed != incoming and completed.is_dir():
            verify_writable(completed)
    if not settings["monitoring"]:
        for folder in {incoming, completed}:
            if folder.is_dir():
                with os.scandir(folder) as entries:
                    next(entries, None)
        return str(incoming), str(completed), []
    versions = []
    with os.scandir(incoming) as entries:
        for entry in entries:
            path = Path(entry.path)
            if path.name.startswith(".") or path.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            try:
                metadata = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(metadata.st_mode) or not metadata.st_size:
                continue
            versions.append((entry.path, metadata.st_size, metadata.st_mtime_ns))
    return str(incoming), str(completed), versions


def inspect_folders_with_deadline(settings):
    # A directory open on an SMB mount can block in the kernel. Isolate it from the watcher.
    try:
        result = subprocess.run(
            [sys.executable, "-BEs", str(Path(__file__).resolve()), "inspect-folders"],
            input=json.dumps(settings),
            capture_output=True,
            text=True,
            timeout=SMB_PROBE_TIMEOUT,
            check=True,
        )
    except subprocess.TimeoutExpired as error:
        raise OSError("Zeitlimit beim Zugriff auf die SMB-Ordner erreicht.") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip().removeprefix("Fehler: ")
        raise OSError(detail or "SMB-Ordnerprüfung fehlgeschlagen.") from error
    return json.loads(result.stdout)


def scan(db, settings, now=None, *, inspect=inspect_folders):
    _, completed, versions = inspect(settings)
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
        for candidate in versions:
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
                (*candidate, str(completed), snapshot, now, now, *candidate),
            )
            db.execute(
                """UPDATE jobs SET state='seen', detected=?, updated=?
                WHERE source=? AND size=? AND mtime_ns=? AND origin_job_id IS NULL AND state='superseded'""",
                (now, now, *candidate),
            )
            db.execute(
                """UPDATE jobs SET state='ready', updated=? WHERE source=? AND size=? AND mtime_ns=?
                AND origin_job_id IS NULL AND state='seen' AND detected<=?""",
                (now, *candidate, now - settings["interval_seconds"]),
            )
    service_state(db, "active")


@lru_cache(maxsize=1)
def rename_function():
    native = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True).renamex_np
    native.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    native.restype = ctypes.c_int
    return native


def rename_exclusive(source, target):
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
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as reader:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(f"Kein reguläres Medium: {path}")
        yield reader


def digest(path):
    with regular_reader(path) as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def version(metadata):
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def stage(job, target):
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
        partial.rename(target)
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
    return not settings.get("watch_path") or settings.get("move_media", False)


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


def copy_identity(metadata):
    return f"{metadata.st_ino}:{metadata.st_birthtime.hex()}"


def copy_verified(db, job_id, source, target, expected):
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(target, flags | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
    except FileExistsError:
        if matches(target, expected):
            return
        descriptor = os.open(target, flags)
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


def publish_job(db, job, transcript, staged, *, text_first=False):
    source = Path(job["source"])
    media, text = targets(job)
    directory = retirement_dir(db, job)
    if not job["publication_started"]:
        if os.path.lexists(media) or os.path.lexists(text):
            raise FileExistsError("Medium oder TXT existiert bereits im Zielordner.")
        with db:
            db.execute("UPDATE jobs SET publication_started=1 WHERE id=?", (job["id"],))
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
    if job["origin_job_id"] is not None:
        parent = Path(job["source"]).parent
        completed = Path(job["completed_dir"])
        if parent == completed:
            return probe_job_paths(
                {"watch_path": str(parent), "create_output_subfolder": False}
            )
        incoming, output, _ = inspect_folders_with_deadline(
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
        probe_job_paths(settings)
        if settings.get("watch_path")
        else active_folders(settings)
    )


def next_job(
    db, state, engine=run_transcription, *, available_only=False, allow_automatic=True
):
    selection = (
        """AND (origin_job_id IS NOT NULL OR
        COALESCE(json_extract(settings,'$.watch_path'),json_extract(settings,'$.input_dir'))
        IN (SELECT path FROM folder_status WHERE available=1))"""
        if available_only
        else ""
    )
    if not allow_automatic:
        selection = "AND origin_job_id IS NOT NULL"
    job = db.execute(
        f"SELECT * FROM jobs WHERE state='ready' {selection} ORDER BY detected, id LIMIT 1"
    ).fetchone()
    if job is None:
        return False
    settings = json.loads(job["settings"])
    watch_path = settings.get("watch_path")
    manual = job["origin_job_id"] is not None
    if watch_path and settings["create_output_subfolder"]:
        settings["move_media"] = True
    if manual:
        incoming, completed = Path(job["source"]).parent, Path(job["completed_dir"])
    elif available_only or watch_path:
        try:
            incoming, completed = probe_job_paths(settings)
        except (OSError, ValueError) as error:
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
        claimed = db.execute(
            """UPDATE jobs SET state=?, attempt=attempt+1, started=?, updated=?, finished=NULL,
            error=NULL, settings=? WHERE id=? AND state='ready'""",
            (phase, now, now, json.dumps(settings, ensure_ascii=False), job_id),
        ).rowcount
    if not claimed:
        return False
    try:
        work.mkdir(parents=True, exist_ok=True, mode=0o700)
        if manual and job_folders(job, settings) != (incoming, completed):
            raise OSError(
                "Die Auftragsordner stimmen nicht mehr mit dem Verlauf überein."
            )
        if not job["text_hash"]:
            local.with_suffix(".partial").unlink(missing_ok=True)
            media_hash = stage(job, local)
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
            result = engine(
                local,
                language=language,
                speakers=settings["speakers"],
                speaker_count=settings["speaker_count"],
                hardware=settings.get("hardware", "cpu"),
                model=settings.get("model", WHISPER_MODEL),
                skip_silence=settings.get("skip_silence", False),
                dover_lap=settings.get("dover_lap", False),
                report=report,
                measurements=measurements,
            )
            transcript.unlink(missing_ok=True)
            publish_text(transcript, result)
            with db:
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
        resolved = job_folders(job, settings)
        if resolved != (incoming, completed):
            raise OSError(
                "Die Auftragsordner haben sich während der Verarbeitung geändert."
            )
        if not manual and moves_media(settings):
            if watch_path:
                completed.mkdir(exist_ok=True)
                if output_folder(incoming, settings) != completed:
                    raise OSError("Der Ausgabeordner hat sich verändert.")
            publish_job(db, job, transcript, local, text_first=bool(watch_path))
        else:
            publish_transcript_only(db, job, transcript)
        error_state(db, job_id, "done", None)
        with suppress(OSError):
            transcript.unlink(missing_ok=True)
    except SourceChanged as error:
        error_state(db, job_id, "superseded", str(error))
    except FileExistsError as error:
        error_state(db, job_id, "blocked", str(error))
    except Exception as error:  # noqa: BLE001 - job boundary, retains cached export for manual retry
        error_state(db, job_id, "failed", str(error) or type(error).__name__)
    finally:
        with suppress(OSError):
            local.unlink(missing_ok=True)
    return True


def recover(db, state):
    jobs = db.execute(
        "SELECT * FROM jobs WHERE state IN ('copying','transcribing','exporting')"
    ).fetchall()
    for job in jobs:
        work = state / "jobs" / str(job["id"])
        for leftover in work.glob("media.*"):
            leftover.unlink(missing_ok=True)
        for leftover in work.glob("transcription-*"):
            if leftover.is_dir() and not leftover.is_symlink():
                shutil.rmtree(leftover)
        if job["publication_started"] and job["text_hash"]:
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
            "failed",
            "Auftrag unterbrochen. Manuelle Wiederholung möglich.",
        )


def retry(db, job_id):
    with db:
        changed = db.execute(
            """UPDATE jobs SET state='ready', updated=?,error=NULL
            WHERE id=? AND state IN ('failed','blocked')""",
            (time.time(), job_id),
        ).rowcount
    if not changed:
        raise ValueError("Dieser Auftrag befindet sich nicht im Fehlerzustand.")


def retranscribe(db, job_id, settings):
    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if job is None or job["state"] not in ("done", "failed", "blocked"):
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
    if not destination.is_dir():
        destination = media.parent
    profile = {**settings, "original_media_hash": job["media_hash"]}
    origin = job["origin_job_id"] or job_id
    now = time.time()
    with db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute(
            "SELECT 1 FROM jobs WHERE id=? AND state IN ('done','failed','blocked')",
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
    work = state / "jobs"
    removed = state / f".history-clear-{uuid.uuid4().hex}"
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute(
            "SELECT 1 FROM jobs WHERE state IN ('copying','transcribing','exporting')"
        ).fetchone():
            raise ValueError(
                "Der Verlauf kann nach Abschluss des aktiven Auftrags geleert werden."
            )
        for table in (
            "events",
            "transcription_measurements",
            "speaker_diarization",
            "audio_durations",
            "copy_claims",
            "copy_exports",
            "jobs",
        ):
            db.execute(f"DELETE FROM {table}")
        if work.is_dir() and not work.is_symlink():
            work.rename(removed)
        db.commit()
    except BaseException:
        try:
            if removed.exists():
                removed.rename(work)
        finally:
            db.rollback()
        raise
    if removed.exists():
        with suppress(OSError):
            shutil.rmtree(removed)


def scan_once(db, settings):
    try:
        scan(db, settings, inspect=inspect_folders_with_deadline)
    except (OSError, ValueError) as error:
        service_state(
            db, "unavailable" if settings["monitoring"] else "paused", str(error)
        )
        connection_state(db, False, str(error))
        return False
    connection_state(db, True)
    return True


def record_folder(db, path, error=None):
    incident = uuid.uuid4().hex if error is not None else None
    with db:
        db.execute(
            """INSERT INTO folder_status VALUES (?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET updated=excluded.updated,available=excluded.available,
                error=excluded.error,
                incident=CASE WHEN excluded.available THEN NULL
                              ELSE COALESCE(folder_status.incident,excluded.incident) END""",
            (path, time.time(), error is None, error, incident),
        )


def probe_job_paths(settings):
    incoming, completed, _ = inspect_folders_with_deadline(
        {
            **settings,
            "monitoring": False,
            "probe_write": False,
        }
    )
    return Path(incoming), Path(completed)


def probe_folder(settings, path):
    return inspect_folders_with_deadline(folder_profile(settings, path))


def probe_pending_folders(db, settings, deadlines, retries):
    paths = settings["folders"]
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
                    scan(
                        db,
                        folder_profile(settings, path),
                        inspect=lambda _, result=task: result.result(),
                    )
                except (OSError, ValueError) as error:
                    record_folder(db, path, str(error))
                    delay = next(
                        retries.setdefault(path, iter(STARTUP_RETRY_DELAYS)), delay
                    )
                else:
                    record_folder(db, path)
                    retries[path] = iter(())
                deadlines[path] = time.monotonic() + delay
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
        if "folders" in current:
            if multiple is not None:
                multiple.set()
            if current != previous:
                connected.clear()
                updated_paths = set(current["folders"])
                with db:
                    for row in db.execute("SELECT path FROM folder_status").fetchall():
                        if row["path"] not in updated_paths:
                            db.execute(
                                "DELETE FROM folder_status WHERE path=?", (row["path"],)
                            )
                        else:
                            # Recheck changed settings before accepting new jobs.
                            db.execute(
                                "UPDATE folder_status SET available=0 WHERE path=? AND error IS NULL",
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
                probe_pending_folders(db, current, folder_deadlines, folder_retries)
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
        with closing(database(state)) as db:
            poll_config(db, config, stop, connected, multiple)

    with (state / "service.lock").open("a") as lock, closing(database(state)) as db:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                "Der Dienst läuft bereits für diese Auftragsdatenbank."
            ) from error
        with db:
            db.execute("DELETE FROM connection")
        recover(db, state)
        if once:
            if multiple.is_set():
                with db:
                    db.execute(
                        "DELETE FROM folder_status WHERE path NOT IN (SELECT value FROM json_each(?))",
                        (json.dumps(settings["folders"]),),
                    )
            available = (
                probe_pending_folders(db, settings, {}, {}) and settings["monitoring"]
                if multiple.is_set()
                else scan_once(db, settings)
            )
            try:
                next_job(
                    db,
                    state,
                    available_only=multiple.is_set(),
                    allow_automatic=available,
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
    with (state / "service.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def start_in_background(state, model_data, config):
    read_settings(config)
    if is_running(state):
        return
    with (state / "service.log").open("ab") as log:
        subprocess.Popen(
            [
                sys.executable,
                "-BEs",
                str(Path(__file__).resolve()),
                "--state-dir",
                str(state),
                "--model-data",
                str(model_data.resolve()),
                "run",
                str(config.resolve()),
            ],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )


def history_jobs(db, order, limit):
    direction = "ASC" if order == "asc" else "DESC"
    return db.execute(
        f"""SELECT j.*, m.speech_seconds, m.speaker_seconds, m.peak_memory_bytes,
        d.speaker_method, d.speaker_passes, d.speaker_note,
        a.seconds AS audio_seconds,
        (SELECT recorded FROM events
         WHERE job_id=j.id AND state='transcribing'
         ORDER BY id DESC LIMIT 1) AS transcription_started
        FROM jobs AS j LEFT JOIN transcription_measurements AS m ON m.job_id=j.id
        LEFT JOIN speaker_diarization AS d ON d.job_id=j.id
        LEFT JOIN audio_durations AS a ON a.job_id=j.id
        ORDER BY j.updated {direction}, j.id {direction} LIMIT ?""",
        (limit,),
    ).fetchall()


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--state-dir", type=Path, default=DEFAULT_DATA.parent / "service")
    cli.add_argument("--model-data", type=Path, default=DEFAULT_DATA)
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect-folders", help=argparse.SUPPRESS)
    for name in ("check", "run", "start"):
        command = commands.add_parser(name)
        command.add_argument("config", type=Path)
        if name == "run":
            command.add_argument("--once", action="store_true")
        if name == "check":
            command.add_argument("--folder")
    commands.add_parser("validate-settings").add_argument("config", type=Path)
    setup = commands.add_parser("setup-models")
    setup.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    setup.add_argument("--no-speakers", action="store_true")
    refresh_command = commands.add_parser("refresh-folder")
    refresh_command.add_argument("config", type=Path)
    refresh_command.add_argument("folder")
    status_command = commands.add_parser("status")
    status_command.add_argument("--limit", type=int, default=-1)
    status_command.add_argument("--order", choices=("asc", "desc"), default="desc")
    autostart = commands.add_parser("autostart")
    autostart.add_argument("mode", choices=("on", "off", "preview"))
    autostart.add_argument("config", type=Path)
    commands.add_parser("retry").add_argument("job_id", type=int)
    rerun = commands.add_parser("retranscribe")
    rerun.add_argument("job_id", type=int)
    rerun.add_argument("config", type=Path)
    commands.add_parser("clear-history")
    args = cli.parse_args(argv)
    try:
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
            incoming, completed, _ = inspect_folders_with_deadline(settings)
            print(f"Eingang: {incoming}\nFertiggestellt: {completed}")
            return 0
        if args.command == "inspect-folders":
            print(json.dumps(inspect_folders(json.load(sys.stdin)), ensure_ascii=True))
            return 0
        state = args.state_dir.resolve()
        initialise(state)
        if args.command == "run":
            configure_runtime(args.model_data)
            run(state, args.config, once=args.once)
            return 0
        if args.command == "start":
            start_in_background(state, args.model_data, args.config)
            return 0
        if args.command == "autostart":
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
            if args.command == "retry":
                retry(db, args.job_id)
            elif args.command == "retranscribe":
                print(retranscribe(db, args.job_id, read_settings(args.config)))
            elif args.command == "clear-history":
                clear_history(db, state)
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
                jobs = history_jobs(db, args.order, args.limit)
                current = db.execute(
                    "SELECT * FROM jobs WHERE state IN ('copying','transcribing','exporting')"
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
                            "current": dict(current) if current else None,
                            "jobs": [dict(job) for job in jobs],
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
