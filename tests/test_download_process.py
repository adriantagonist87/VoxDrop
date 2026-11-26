import subprocess
import sys
from threading import Event,Thread
import unittest

from desktop.command_process import CommandProcesses


class DownloadProcessTests(unittest.TestCase):
    def test_progress_arrives_before_exit_and_both_output_pipes_are_bounded(self):
        registry=CommandProcesses()
        received=Event();done=Event();results=[]
        script="import sys,time; print('progress',flush=True);sys.stderr.write('x'*200000);sys.stderr.flush();time.sleep(.8);print('done',flush=True)"
        def run():
            try:
                results.append(registry.run([sys.executable,'-BEs','-c',script],on_stdout=lambda line:received.set(),
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8'))
            finally:done.set()
        thread=Thread(target=run);thread.start()
        self.assertTrue(received.wait(8))
        self.assertFalse(done.is_set())
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0].returncode,0)
        self.assertLessEqual(len(results[0].stderr),65536)
        self.assertIn('done',results[0].stdout)
        registry.wait_idle(.1)

    def test_cancel_stops_an_active_download_without_poisoning_other_commands(self):
        registry=CommandProcesses();cancel=Event();received=Event();errors=[]
        def run():
            try:
                registry.run([sys.executable,'-BEs','-c',"import time;print('ready',flush=True);time.sleep(60)"],
                    on_stdout=lambda line:received.set(),cancel=cancel,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            except Exception as error:errors.append(str(error))
        thread=Thread(target=run);thread.start()
        self.assertTrue(received.wait(8))
        cancel.set();thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors and 'abgebrochen' in errors[0])
        registry.wait_idle(.1)
        self.assertEqual(registry.run([sys.executable,'-c','pass']).returncode,0)
