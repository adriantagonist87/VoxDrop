"""Own short GUI command subprocesses, including download/probe descendants."""
from contextlib import contextmanager
import subprocess
from threading import Lock
import time

from platform_io import WINDOWS, child_process


class CommandProcesses:
    def __init__(self):
        self.lock=Lock();self.active={};self.stopping=False

    def reset(self):
        with self.lock:
            if not self.active:self.stopping=False

    def run(self,arguments,*,detached_start=False,allow_stop=False,timeout=None,**options):
        @contextmanager
        def unmanaged():
            with subprocess.Popen(arguments,**options) as process:yield process
        # Unix daemons explicitly create a new session during handoff. The
        # short start command still needs pipe ownership while SQLite can block.
        context=unmanaged() if detached_start and WINDOWS else child_process(arguments,cancellable=True,**options)
        with self.lock:
            if self.stopping and not allow_stop:
                raise RuntimeError('VoxDrop wird beendet.')
            process=context.__enter__()
            self.active[process.pid]=process
        try:
            stdout,stderr=process.communicate(timeout=timeout)
            return subprocess.CompletedProcess(arguments,process.returncode,stdout,stderr)
        finally:
            with self.lock:self.active.pop(process.pid,None)
            getattr(process,'cancel_tree',lambda:None)()
            context.__exit__(None,None,None)

    def cancel(self):
        with self.lock:
            self.stopping=True
            for process in list(self.active.values()):
                try:
                    cancel=getattr(process,'cancel_tree',None)
                    if cancel:cancel()
                    elif process.poll() is None:process.terminate()
                except ProcessLookupError:pass

    def wait_idle(self, timeout=15):
        deadline=time.monotonic()+timeout
        while True:
            with self.lock:
                if not self.active:return
            if time.monotonic()>=deadline:
                raise RuntimeError('Eine vorherige Aktion läuft noch. Bitte kurz warten und erneut versuchen.')
            time.sleep(.05)
