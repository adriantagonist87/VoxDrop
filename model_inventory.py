"""Inspect and remove only VoxDrop's known local model directories."""

from contextlib import closing, contextmanager
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
import shutil
import sqlite3
import stat

import qwen_backend
from platform_io import WINDOWS, is_reparse_point


WHISPER = "large-v3-turbo"
SPEAKERS = "speaker-detection"
LABELS = {
    qwen_backend.ASR: "Qwen3-ASR 1.7B",
    qwen_backend.ALIGNER: "Qwen3 Forced Aligner 0.6B",
    WHISPER: "Whisper Large v3 Turbo",
    SPEAKERS: "Sprechererkennung (pyannote)",
}


@lru_cache(maxsize=1)
def catalog():
    atrain = json.loads(
        files("aTrain_core.data").joinpath("models.json").read_text(encoding="utf-8")
    )
    return {
        **{key: (spec["repo"], tuple(spec["files"]))
           for key, spec in qwen_backend.model_manifest().items()},
        **{key: (atrain[key]["repo_id"], tuple(atrain[key]["files"]))
           for key in (WHISPER, SPEAKERS)},
    }


def directory(path, *, optional=False):
    try:
        info = path.lstat()
    except FileNotFoundError:
        if optional:
            return False
        raise
    if not stat.S_ISDIR(info.st_mode) or is_reparse_point(info):
        raise ValueError(f"VoxDrop verwaltet hier nur reguläre Modellordner: {path}")
    return True


def lock_access(handle, exclusive):
    if not WINDOWS:
        import fcntl

        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(handle, mode | fcntl.LOCK_NB)
        return

    import ctypes
    import msvcrt
    from ctypes import wintypes

    class Overlapped(ctypes.Structure):
        _fields_ = [
            ("internal", ctypes.c_size_t), ("internal_high", ctypes.c_size_t),
            ("offset", wintypes.DWORD), ("offset_high", wintypes.DWORD),
            ("event", wintypes.HANDLE),
        ]

    function = ctypes.WinDLL("kernel32", use_last_error=True).LockFileEx
    function.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped),
    )
    function.restype = wintypes.BOOL
    # Lock the first byte, even in an empty coordination file.
    flags = 0x1 | (0x2 if exclusive else 0)  # FAIL_IMMEDIATELY | EXCLUSIVE_LOCK
    if not function(msvcrt.get_osfhandle(handle.fileno()), flags, 0, 1, 0, ctypes.byref(Overlapped())):
        code = ctypes.get_last_error()
        if code == 33:  # ERROR_LOCK_VIOLATION
            raise BlockingIOError("Model store is in use")
        raise ctypes.WinError(code)


@contextmanager
def model_use(data_dir, *, exclusive=False):
    """Coordinate access across VoxDrop profiles using the same model store."""
    root = Path(data_dir).resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    # The import can replace the store itself, so its lock lives beside it.
    lock = root.with_name(f".{root.name}.models.lock")
    with lock.open("a+b") as handle:
        try:
            lock_access(handle, exclusive)
        except BlockingIOError as error:
            raise ValueError("Der Modellspeicher wird gerade verwendet. Bitte warte, bis der Vorgang abgeschlossen ist.") from error
        yield


def model_paths(root, key, repo):
    repo_dir = "models--" + repo.replace("/", "--")
    paths = []
    for relative, kind in (
        (Path("models") / key, "model"),
        (Path("huggingface", "hub", repo_dir), "cache"),
    ):
        candidate = root
        for part in relative.parts:
            candidate = candidate / part
            if not directory(candidate, optional=True):
                break
        else:
            # Reject redirected ancestors, including junctions.
            if candidate.resolve(strict=True) != root / relative:
                raise ValueError("Der Modellpfad verweist auf einen anderen Ordner.")
            paths.append((candidate, kind))
    return paths


def describe(root, key, *, spec=None):
    repo, expected = spec if spec is not None else catalog()[key]
    totals = {"model": 0, "cache": 0}
    stamp = sha256()
    installed_files = set()
    paths = model_paths(root, key, repo) if directory(root, optional=True) else []

    def inspect(folder, kind, top):
        for entry in sorted(folder.iterdir()):
            info = entry.lstat()
            relative = entry.relative_to(top).as_posix()
            stamp.update(repr((kind, relative, info.st_mode, info.st_dev,
                               info.st_ino, info.st_size, info.st_mtime_ns,
                               info.st_ctime_ns)).encode("utf-8", errors="surrogatepass"))
            if kind == "cache" and relative.startswith("snapshots/") and entry.is_symlink():
                # Standard HF snapshots use links to blobs. Never read or follow them.
                continue
            if is_reparse_point(info):
                raise ValueError("Verknüpfte Modellordner können hier nicht gelöscht werden.")
            if stat.S_ISDIR(info.st_mode):
                inspect(entry, kind, top)
            elif stat.S_ISREG(info.st_mode):
                totals[kind] += info.st_size
                if kind == "model" and info.st_size:
                    installed_files.add(relative)
            else:
                raise ValueError("Der Modellordner enthält eine nicht unterstützte Dateiverknüpfung.")

    for path, kind in paths:
        info = path.lstat()
        stamp.update(repr((kind, info.st_dev, info.st_ino, info.st_ctime_ns)).encode())
        inspect(path, kind, path)
    have_model = any(kind == "model" for _, kind in paths)
    status = (
        "Installiert" if have_model and set(expected) <= installed_files else
        "Unvollständig" if have_model else
        "Nur Download-Cache" if paths else "Nicht installiert"
    )
    return {
        "id": key, "name": LABELS[key], "status": status, "present": bool(paths),
        "modelBytes": totals["model"], "cacheBytes": totals["cache"],
        "token": stamp.hexdigest(),
    }, paths


def inventory(data_dir):
    root = Path(data_dir).absolute()
    if directory(root, optional=True):
        root = root.resolve(strict=True)
    specs = catalog()
    rows = []
    for key, name in LABELS.items():
        try:
            item, _ = describe(root, key, spec=specs[key])
        except (OSError, ValueError) as error:
            item = {"id": key, "name": name, "status": str(error), "present": False,
                    "modelBytes": 0, "cacheBytes": 0, "token": ""}
        rows.append(item)
    return rows


@contextmanager
def idle_queue(database):
    if not database.is_file():
        yield
        return
    # Serialize with a job claim in this profile, even if the displayed status is stale.
    with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        job = db.execute(
            "SELECT 1 FROM jobs WHERE state IN ('copying','transcribing','exporting') LIMIT 1"
        ).fetchone()
        immediate = db.execute("SELECT 1 FROM immediate_jobs LIMIT 1").fetchone()
        if job or immediate:
            raise ValueError("Pausiere die Verarbeitung und warte, bis der aktive Auftrag beendet ist.")
        yield


def remove_model(data_dir, database, key, token):
    if key not in LABELS:
        raise ValueError("Unbekanntes VoxDrop-Modell.")
    root = Path(data_dir).absolute()
    directory(root)
    root = root.resolve(strict=True)
    with model_use(root, exclusive=True), idle_queue(Path(database).absolute()):
        item, paths = describe(root, key)
        if not paths or item["token"] != token:
            raise ValueError("Der Modellbestand hat sich geändert. Bitte prüfe die aktuelle Liste.")
        for path, _ in paths:
            directory(path)
            if path.resolve(strict=True) != path or not path.is_relative_to(root):
                raise ValueError("Unsicherer Modellpfad.")
            shutil.rmtree(path)
