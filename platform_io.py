"""Operating-system primitives used by the shared transcription service."""

import errno
import os
import re
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

WINDOWS = sys.platform == "win32"
EVENT_NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"
WER_PROVIDER = "Provider[@Name='Windows Error Reporting'] and EventID=1001"


def _windows_events(channel, query, *, oldest=False, one=False):
    wevtutil = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/wevtutil.exe"
    args = [str(wevtutil), "qe", channel, f"/q:{query}", "/f:xml", "/e:Events", "/uni:true",
            "/rd:false" if oldest else "/rd:true"]
    if one:
        args.append("/c:1")
    result = subprocess.run(args, capture_output=True, timeout=2, check=True, **process_options())
    return ET.fromstring(result.stdout.decode("utf-16")).findall(f"{EVENT_NS}Event")


@lru_cache(maxsize=256)
def _first_wer_time(report_id):
    # ReportId stays the same when Windows resubmits a queued report.
    query = f"*[System[{WER_PROVIDER}] and EventData[Data[@Name='ReportId']='{report_id}']]"
    events = _windows_events("Application", query, oldest=True, one=True)
    if not events:
        raise ValueError("WER report is no longer in the event log")
    stamp = events[0].find(f"{EVENT_NS}System/{EVENT_NS}TimeCreated")
    if stamp is None:
        raise ValueError("WER event lacks creation time")
    return datetime.fromisoformat(stamp.get("SystemTime", "")).timestamp()


def _current_wer_report(event, started):
    data = {field.get("Name"): field.text or ""
            for field in event.findall(f"{EVENT_NS}EventData/{EVENT_NS}Data")}
    # Dump names carry local time to the minute, even when WER first submits
    # a report days later. Do not access paths supplied by event payloads.
    dump = re.search(r"\bWATCHDOG-(\d{8}-\d{4})\.dmp\b", data.get("AttachedFiles", ""), re.I)
    if dump:
        dt = datetime.strptime(dump[1], "%Y%m%d-%H%M")
        # A repeated local hour at the end of daylight saving time has two instants.
        if max(dt.timestamp(), dt.replace(fold=1).timestamp()) + 60 <= started:
            return False
    report_id = data.get("ReportId", "")
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", report_id):
        return False
    return _first_wer_time(report_id) >= started


def graphics_timeout_since(started):
    """Look for display recovery, a GPU timeout or graphics live dump during CUDA."""
    if not WINDOWS or not started:
        return None
    now = time.time()
    if started > now:
        return None
    # Keep the existing bounded lookup even for a worker running over two days.
    since = max(started, now - 48 * 60 * 60)
    stamp = datetime.fromtimestamp(since, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    date = f"TimeCreated[@SystemTime >= '{stamp}']"
    system_query = (f"*[System[{date} and ((Provider[@Name='Display'] and EventID=4101)"
                    " or (Provider[@Name='nvlddmkm'] and EventID=153))]]")
    unavailable = (OSError, subprocess.SubprocessError, ValueError, ET.ParseError)
    try:
        for event in _windows_events("System", system_query, one=True):
            event_id = event.findtext(f"{EVENT_NS}System/{EVENT_NS}EventID")
            return ("NVIDIA-Treiberfehler (153)" if event_id == "153"
                    else "Wiederherstellung des Grafiktreibers (4101)")
    except unavailable:
        pass
    query = (f"*[System[{date} and {WER_PROVIDER}]"
             " and EventData[Data[@Name='EventName']='LiveKernelEvent'"
             " and (Data[@Name='P1']='141' or Data[@Name='P1']='117' or Data[@Name='P1']='193')]]")
    try:
        reports = _windows_events("Application", query)
    except unavailable:
        return None
    for report in reports:
        try:
            if _current_wer_report(report, since):
                if report.findtext(f"{EVENT_NS}EventData/{EVENT_NS}Data[@Name='P1']")=='193':
                    return "Grafik-Watchdog (Windows-Fehlerbericht 193)"
                return "GPU-Timeout (Windows-Fehlerbericht 141/117)"
        except unavailable:
            continue
    return None


def inference_cpu_threads():
    return min(6, max(1, (os.cpu_count() or 2) // 3))


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
    """Popen with platform-specific descendant cleanup, including owner crashes."""
    import subprocess

    if not WINDOWS:
        with posix_child_process(*args, **kwargs) as child:
            yield child
        return

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


@contextmanager
def posix_child_process(arguments, **kwargs):
    """A pipe-owned guardian also cleans detached groups after owner SIGKILL."""
    import subprocess
    from pathlib import Path

    owner_read, owner_write = os.pipe()
    ready_read, ready_write = os.pipe()
    child = None
    try:
        inherited = tuple(kwargs.pop('pass_fds', ()))
        child = subprocess.Popen(
            [sys.executable, '-BEs', str(Path(__file__).with_name('posix_guard.py')),
             str(owner_read), str(ready_write), *map(str, arguments)],
            pass_fds=(*inherited, owner_read, ready_write), **kwargs)
        os.close(owner_read); owner_read = None
        os.close(ready_write); ready_write = None
        with os.fdopen(ready_read, 'rb') as ready:
            ready_read = None
            line = ready.readline()
        if not line:
            child.wait()
            raise RuntimeError('Der VoxDrop-Prozesswächter konnte nicht gestartet werden.')
        group = int(line)
        import threading
        lock = threading.Lock()

        def cancel_tree():
            nonlocal owner_write
            with lock:
                if owner_write is not None:
                    os.close(owner_write)
                    owner_write = None
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    import signal
                    try: os.killpg(group, signal.SIGKILL)
                    except ProcessLookupError: pass
                    child.kill()
                    child.wait(timeout=5)

        child.cancel_tree = cancel_tree
        try:
            yield child
        finally:
            cancel_tree()
    finally:
        for descriptor in (owner_read, owner_write, ready_read, ready_write):
            if descriptor is not None:
                os.close(descriptor)
        if child is not None:
            if child.poll() is None:
                child.terminate()
            child.wait()
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()


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
    """Defer local writable handles; never hold the media locked during inference."""
    if sys.platform == 'darwin':
        import subprocess
        result = subprocess.run(
            ['/usr/sbin/lsof', '-nP', '-Ffa', '--', str(path)],
            capture_output=True, text=True, timeout=3)
        if result.returncode not in (0, 1) or (result.returncode == 1 and result.stderr.strip()):
            raise OSError('Offene Aufnahme konnte nicht geprüft werden: ' + result.stderr.strip())
        # Inspect writable descriptors, including a paused local recorder.
        return any(line in ('aw', 'au') for line in result.stdout.splitlines())
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
