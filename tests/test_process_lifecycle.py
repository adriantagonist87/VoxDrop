import json
import subprocess
import sys
import time
import unittest

import psutil

from platform_io import WINDOWS, child_process, process_options


class ProcessLifecycleTests(unittest.TestCase):
    @unittest.skipUnless(WINDOWS, "Windows background console regression")
    def test_background_runtime_has_no_console_and_keeps_captured_streams(self):
        program = (
            "import ctypes,json,sys; "
            "print(json.dumps({'console':int(ctypes.windll.kernel32.GetConsoleWindow())}),flush=True); "
            "print('diagnostic output',file=sys.stderr,flush=True)"
        )
        result = subprocess.run(
            [sys.executable, "-BEs", "-Xutf8", "-c", program],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            timeout=10,
            **process_options(background=True),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["console"], 0)
        self.assertEqual(result.stderr.strip(), "diagnostic output")

    def test_child_output_and_exit_status_survive_managed_launch(self):
        with child_process([sys.executable, "-c", "print('ready'); raise SystemExit(7)"],
                           stdout=subprocess.PIPE, text=True, **process_options()) as child:
            self.assertEqual(child.communicate(timeout=10)[0].strip(), "ready")
            self.assertEqual(child.returncode, 7)

    @unittest.skipUnless(WINDOWS, "Windows kill-on-owner-exit job objects")
    def test_owner_crash_kills_child_and_grandchild(self):
        leaf = "import time; time.sleep(60)"
        branch = ("import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c',"
                  + repr(leaf) + "],creationflags=0x08000000); print(p.pid,flush=True); time.sleep(60)")
        owner = ("import sys,subprocess,time; from platform_io import child_process; "
                 "child=child_process([sys.executable,'-c'," + repr(branch) +
                 "],stdout=subprocess.PIPE,text=True,creationflags=0x08000000); p=child.__enter__(); "
                 "print(str(p.pid)+','+p.stdout.readline().strip(),flush=True); time.sleep(60)")
        with subprocess.Popen([sys.executable, "-B", "-c", owner], stdout=subprocess.PIPE,
                              text=True, **process_options()) as parent:
            processes = []
            try:
                # communicate timeout prevents a failed launch from hanging the suite.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    line = pool.submit(parent.stdout.readline).result(timeout=10)
                self.assertTrue(line.strip(), "owner exited before reporting children")
                processes = [psutil.Process(int(pid)) for pid in line.strip().split(",")]
                parent.kill()
                parent.wait(timeout=5)
                _, alive = psutil.wait_procs(processes, timeout=5)
                self.assertEqual(alive, [])
            finally:
                for process in reversed(processes):
                    if process.is_running():
                        process.kill()
                if parent.poll() is None:
                    parent.kill()
