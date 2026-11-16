"""Operating-system primitives used by the shared transcription service."""

import errno
import os
import stat
import sys

WINDOWS = sys.platform == "win32"


def lock_service(handle):
    if WINDOWS:
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EDEADLK):
                raise BlockingIOError(error.errno, error.strerror) from error
            raise
    else:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def is_reparse_point(metadata):
    return bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def open_regular(path, flags, mode=0o600):
    if WINDOWS and not flags & os.O_EXCL:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or is_reparse_point(before):
            raise OSError(f"Keine reguläre Datei: {path}")
    descriptor = os.open(
        path,
        flags
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0),
        mode,
    )
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or is_reparse_point(opened):
            raise OSError(f"Keine reguläre Datei: {path}")
        if WINDOWS:
            current = path.lstat()
            if is_reparse_point(current) or not os.path.samestat(current, opened):
                raise OSError(f"Die Datei hat sich beim Öffnen geändert: {path}")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def process_options(*, background=False):
    if WINDOWS:
        import subprocess

        if background:
            return {
                "creationflags": subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
            }
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True} if background else {}
