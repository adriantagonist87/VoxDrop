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
        # Cold process enumeration on a busy native Windows desktop can exceed
        # a minute. Keep the unrelated profile alive throughout that check.
        engine.write_text("import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(180)']); print(p.pid,flush=True); time.sleep(180)")
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

    @unittest.skipIf(sys.platform=='win32','Unix detached service handoff')
    def test_start_command_dies_with_owner_before_daemon_handoff(self):
        ready=self.root/'starter.pid'
        leaf="import os,sys,time; open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(60)"
        owner=("from desktop.command_process import CommandProcesses; import sys; "
               "CommandProcesses().run([sys.executable,'-BEs','-c',"+repr(leaf)+",sys.argv[1]],detached_start=True)")
        process=subprocess.Popen([sys.executable,'-BEs','-c',owner,str(ready)])
        child=None
        try:
            deadline=time.monotonic()+10
            while not ready.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(ready.exists())
            child=psutil.Process(int(ready.read_text()))
            process.kill();process.wait(5)
            _,alive=psutil.wait_procs([child],timeout=5)
            self.assertFalse(alive,'Blocked start survived its GUI owner')
        finally:
            if process.poll() is None:process.kill();process.wait(5)
            if child:
                try:child.kill();child.wait(5)
                except psutil.Error:pass

    @unittest.skipIf(sys.platform=='win32','Unix detached service handoff')
    def test_successful_start_handoff_keeps_new_daemon_session_alive(self):
        ready=self.root/'daemon.pid'
        leaf="import os,sys,time; open(sys.argv[1],'w').write(str(os.getpid())); time.sleep(60)"
        starter="import subprocess,sys; subprocess.Popen([sys.executable,'-BEs','-c',"+repr(leaf)+",sys.argv[1]],start_new_session=True)"
        child=None
        try:
            registry=CommandProcesses()
            result=registry.run([sys.executable,'-BEs','-c',starter,str(ready)],detached_start=True)
            self.assertEqual(result.returncode,0)
            deadline=time.monotonic()+10
            while not ready.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(ready.exists())
            child=psutil.Process(int(ready.read_text()));self.assertTrue(child.is_running())
        finally:
            if child:
                try:child.kill();child.wait(5)
                except psutil.Error:pass
