"""Own one Unix process group until its command or its parent's pipe ends."""
import os
import select
import signal
import subprocess
import sys


def main():
    owner, ready = map(int, sys.argv[1:3])
    os.set_inheritable(owner, False)
    os.set_inheritable(ready, False)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    child = subprocess.Popen(sys.argv[3:], start_new_session=True)
    try:
        os.write(ready, str(child.pid).encode() + b'\n')
        os.close(ready)
        while child.poll() is None and not stopping:
            readable, _, _ = select.select([owner], [], [], .1)
            if readable and not os.read(owner, 1):
                stopping = True
    finally:
        # The group remains ours even when the command has exited but its
        # grandchildren still hold pipes or model/audio resources open.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        code = child.wait()
        os.close(owner)
    return code if code >= 0 else 128 - code


if __name__ == '__main__':
    raise SystemExit(main())
