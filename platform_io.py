"""Operating-system primitives used by the shared transcription service."""

import errno
import os
import stat
import sys
from contextlib import contextmanager

WINDOWS = sys.platform == "win32"


def windows_process_job(child):
    """Keep a Windows child tree inside a kill-on-owner-exit job object."""
    import ctypes
    from ctypes import wintypes

    class Limits(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                    ("max_working_set", ctypes.c_size_t), ("active_processes", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                    ("scheduling", wintypes.DWORD)]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("basic", Limits), ("io_counters", ctypes.c_uint64 * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                               ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                 ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(handle, int(child._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    import threading
    close_lock = threading.Lock()

    def close():
        nonlocal handle
        with close_lock:
            if handle is not None:
                # Closing a kill-on-close job requests asynchronous termination.
                # Wait for every member, including venv redirector grandchildren,
                # before TemporaryDirectory tries to remove their mapped audio.
                import time
                processes = []
                try:
                    capacity = 32
                    while True:
                        members = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
                        success = kernel.QueryInformationJobObject(handle, 3, members, ctypes.sizeof(members), None)
                        assigned, count = (wintypes.DWORD * 2).from_buffer(members)
                        if success and count >= assigned:
                            break
                        if not success and ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
                            raise ctypes.WinError(ctypes.get_last_error())
                        capacity = max(capacity * 2, assigned)
                    for pid in (ctypes.c_size_t * count).from_buffer(members, 8):
                        process = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                        if process:
                            processes.append(process)
                        elif ctypes.get_last_error() != 87:  # Already exited.
                            raise ctypes.WinError(ctypes.get_last_error())
                    if not kernel.TerminateJobObject(handle, 1):
                        raise ctypes.WinError(ctypes.get_last_error())
                    deadline = time.monotonic() + 5
                    for process in processes:
                        result = kernel.WaitForSingleObject(process, max(0, int((deadline-time.monotonic())*1000)))
                        if result == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        if result != 0:
                            raise RuntimeError("Ein VoxDrop-Unterprozess wurde noch nicht vollständig entladen.")
                finally:
                    for process in processes:
                        kernel.CloseHandle(process)
                    kernel.CloseHandle(handle)
                    handle = None
    return close


def resume_windows_child(child):
    """Resume the primary thread after assigning the still-suspended process."""
    import ctypes
    from ctypes import wintypes

    class ThreadEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("thread_id", wintypes.DWORD), ("owner_pid", wintypes.DWORD),
                    ("base_priority", wintypes.LONG), ("delta_priority", wintypes.LONG),
                    ("flags", wintypes.DWORD)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ThreadEntry()
        entry.size = ctypes.sizeof(entry)
        found = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.owner_pid == child.pid:
                thread = kernel.OpenThread(2, False, entry.thread_id)  # THREAD_SUSPEND_RESUME
                if not thread:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if kernel.ResumeThread(thread) == 0xFFFFFFFF:
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    kernel.CloseHandle(thread)
                return
            found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        raise OSError("Der neue Windows-Prozess hat keinen fortsetzbaren Hauptthread.")
    finally:
        kernel.CloseHandle(snapshot)


@contextmanager
def child_process(*args, cancellable=False, **kwargs):
    """Popen with Windows descendant cleanup, including owner crashes."""
    import subprocess

    if WINDOWS:
        # Assignment must precede execution, including uv's Python redirector.
        # Otherwise a fast child can spawn descendants outside the job.
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 4  # CREATE_SUSPENDED
    elif cancellable:
        kwargs['start_new_session'] = True
    with subprocess.Popen(*args, **kwargs) as child:
        close_job = None
        try:
            close_job = windows_process_job(child) if WINDOWS else None
            if WINDOWS:
                resume_windows_child(child)
            if cancellable:
                if WINDOWS:
                    child.cancel_tree = close_job
                else:
                    def cancel_tree():
                        import signal
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    child.cancel_tree = cancel_tree
        except BaseException:
            if close_job is not None:
                close_job()
            child.kill()
            child.wait()
            raise
        try:
            yield child
        finally:
            if close_job is not None:
                close_job()


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


def file_is_being_written(path):
    """Probe Windows sharing compatibility; do not lock the file during inference."""
    if not WINDOWS:
        return False
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                                ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    # Exclude FILE_SHARE_WRITE: any existing writable handle makes this fail,
    # even when OBS has temporarily stopped growing the file.
    handle=kernel.CreateFileW(str(path),0x80000000,0x1|0x4,None,3,0x80,None)
    if handle==ctypes.c_void_p(-1).value:
        code=ctypes.get_last_error()
        if code in (32,33):
            return True
        raise ctypes.WinError(code)
    kernel.CloseHandle(handle)
    return False


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
                # DETACHED_PROCESS makes this venv redirector allocate a new
                # console in its real Python child. Keep the service windowless.
                "creationflags": subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
            }
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True} if background else {}
