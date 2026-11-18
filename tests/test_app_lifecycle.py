from contextlib import closing
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from threading import Thread
from unittest.mock import Mock

import psutil
import watch_service as service
from app_lifecycle import register_owner,owner_alive,request_stop,stopping,stop_service
from desktop.command_process import CommandProcesses
from platform_io import process_options


class AppLifecycleTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name).resolve();self.state=self.root/'state'
        service.initialise(self.state);self.db=service.database(self.state);self.addCleanup(self.db.close)

    def test_owner_identity_and_explicit_new_start_reset_only_stop_intent(self):
        register_owner(self.db,os.getpid(),psutil.Process().create_time())
        self.assertTrue(owner_alive(self.db));request_stop(self.db);self.assertTrue(stopping(self.db))
        register_owner(self.db,os.getpid(),psutil.Process().create_time())
        self.assertFalse(stopping(self.db))
        with self.db:self.db.execute('UPDATE app_control SET owner_created=0')
        self.assertFalse(owner_alive(self.db))
        with self.assertRaises(ValueError):register_owner(self.db,os.getpid(),0)

    def add(self,name,state,publication=0):
        source=self.root/name;source.write_bytes(b'synthetic media')
        with self.db:
            identifier=self.db.execute('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated,state,attempt,started,publication_started) VALUES (?,?,15,1,?,1,1,?,1,1,?)',
                (str(source),str(self.root),json.dumps(dict(model='qwen3-asr-1.7b',speakers=False)),state,publication)).lastrowid
        return identifier

    def test_stop_restores_active_job_and_never_claims_waiting_jobs(self):
        active=self.add('Active.wav','transcribing');waiting=self.add('Waiting.wav','ready')
        request_stop(self.db)
        self.assertIsNotNone(self.db.execute('SELECT 1 FROM preemptions WHERE job_id=?',(active,)).fetchone())
        service.recover(self.db,self.state,verify_exports=False)
        self.assertEqual(self.db.execute('SELECT state FROM jobs WHERE id=?',(active,)).fetchone()[0],'ready')
        engine=Mock();self.assertFalse(service.next_job(self.db,self.state,engine));engine.assert_not_called()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)
        self.assertFalse(service.queue_paused(self.db))

    def test_stop_does_not_override_explicit_cancel_or_interrupt_started_publication(self):
        active=self.add('Cancelled.wav','copying');export=self.add('Export.wav','exporting',1)
        service.cancel_job(self.db,active);request_stop(self.db)
        self.assertFalse(self.db.execute('SELECT 1 FROM preemptions WHERE job_id=?',(active,)).fetchone())
        self.assertFalse(self.db.execute('SELECT 1 FROM cancel_requests WHERE job_id=?',(export,)).fetchone())
        service.recover(self.db,self.state,verify_exports=False)
        self.assertEqual(self.db.execute('SELECT state FROM jobs WHERE id=?',(active,)).fetchone()[0],'cancelled')

    def test_bounded_stop_kills_only_matching_profile_and_its_descendants(self):
        engine=self.root/'watch_service.py'
        engine.write_text("import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)")
        other=self.root/'other';service.initialise(other)
        processes=[]
        try:
            for state in (self.state,other):
                process=subprocess.Popen([sys.executable,'-B',str(engine),'--state-dir',str(state),'run'],stdout=subprocess.PIPE,text=True,**process_options(background=True))
                processes.append((process,psutil.Process(int(process.stdout.readline().strip()))))
            result=stop_service(self.db,self.state,engine,grace_seconds=.1)
            self.assertTrue(result['stopped'])
            self.assertIsNotNone(processes[0][0].poll())
            self.assertFalse(processes[0][1].is_running())
            self.assertIsNone(processes[1][0].poll())
            self.assertTrue(processes[1][1].is_running())
        finally:
            for process,child in processes:
                try:child.kill();child.wait(timeout=3)
                except psutil.Error:pass
                if process.poll() is None:process.kill()
                process.wait(timeout=3);process.stdout.close()

    def test_foreground_command_cancel_cleans_download_descendants(self):
        registry=CommandProcesses();ready=self.root/'command.json'
        script="import subprocess,sys,time,json; p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); open(sys.argv[1],'w').write(json.dumps([__import__('os').getpid(),p.pid])); time.sleep(60)"
        outcome=[]
        worker=Thread(target=lambda:outcome.append(registry.run([sys.executable,'-c',script,str(ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)))
        worker.start()
        deadline=time.monotonic()+10
        while not ready.exists() and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue(ready.exists())
        pids=json.loads(ready.read_text());children=[psutil.Process(pid) for pid in pids]
        registry.cancel();worker.join(8)
        self.assertFalse(worker.is_alive());self.assertEqual(len(outcome),1)
        _,alive=psutil.wait_procs(children,timeout=3);self.assertFalse(alive)
        with self.assertRaisesRegex(RuntimeError,'beendet'):registry.run([sys.executable,'-c','pass'])
