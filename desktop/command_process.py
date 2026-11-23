"""Own short GUI command subprocesses, including download/probe descendants."""
from contextlib import contextmanager
from collections import deque
import subprocess
from threading import Lock, Thread
import time

from platform_io import WINDOWS, child_process


class CommandProcesses:
    def __init__(self):
        self.lock=Lock();self.active={};self.stopping=False

    def reset(self):
        with self.lock:
            if not self.active:self.stopping=False

    def run(self,arguments,*,detached_start=False,allow_stop=False,timeout=None,on_stdout=None,cancel=None,**options):
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
            stdout,stderr=(process.communicate(timeout=timeout) if on_stdout is None else
                           self._stream(process,on_stdout,cancel,timeout))
            return subprocess.CompletedProcess(arguments,process.returncode,stdout,stderr)
        finally:
            with self.lock:self.active.pop(process.pid,None)
            getattr(process,'cancel_tree',lambda:None)()
            context.__exit__(None,None,None)

    @staticmethod
    def _stream(process,callback,cancel,timeout):
        """Drain both pipes while forwarding progress before the command exits."""
        buffers=[deque(),deque()]
        sizes=[0,0]
        errors=[]
        def drain(pipe,index):
            try:
                while line:=pipe.readline(65536):
                    if index==0:callback(line)
                    buffers[index].append(line)
                    sizes[index]+=len(line)
                    while sizes[index]>65536 and len(buffers[index])>1:
                        sizes[index]-=len(buffers[index].popleft())
            except Exception as error:errors.append(error)
        readers=[Thread(target=drain,args=(pipe,index),daemon=True)
                 for index,pipe in enumerate((process.stdout,process.stderr))]
        for reader in readers:reader.start()
        deadline=time.monotonic()+timeout if timeout is not None else None
        cancelled=False
        try:
            while process.poll() is None:
                if errors or (cancel is not None and cancel.is_set()):
                    cancelled=True
                    getattr(process,'cancel_tree',process.terminate)()
                    break
                if deadline is not None and time.monotonic()>=deadline:
                    raise subprocess.TimeoutExpired(process.args,timeout)
                time.sleep(.05)
            process.wait(timeout=5)
        finally:
            # A child retaining a pipe cannot keep the GUI worker alive after its owner exits.
            getattr(process,'cancel_tree',lambda:None)()
            for reader in readers:reader.join(5)
        if errors:raise errors[0]
        if any(reader.is_alive() for reader in readers):
            raise RuntimeError('Die Modellausgabe konnte noch nicht vollständig beendet werden.')
        if cancelled:raise RuntimeError('Modelleinrichtung abgebrochen. Sie kann später fortgesetzt werden.')
        return tuple(''.join(buffer)[-65536:] for buffer in buffers)

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
