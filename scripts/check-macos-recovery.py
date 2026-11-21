"""Fault-inject only a new Mac profile with supplied synthetic speech/model data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
import wave

import psutil


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('app','models','fixture','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    root=args.output.resolve();profile=root/'profile';profile.mkdir();incoming=root/'incoming';incoming.mkdir()
    state=profile/'service';config=profile/'config.json';dbfile=state/'jobs.sqlite3'
    resources=args.app.resolve()/'Contents/Resources';python=resources/'Python/bin/python3.12';engine=resources/'Engine/watch_service.py'
    config.write_text(json.dumps(dict(folders=[str(incoming)],monitoring=True,interval_seconds=1,
        model='qwen3-asr-1.7b',hardware='metal',language='de',speakers=False,gpu_budget_percent=50)))
    env={**os.environ,'VOXDROP_PROFILE':str(profile),'VOXDROP_MODEL_DATA':str(args.models.resolve())}
    guis=[];report=dict(passed=False)
    def wait(predicate,label,timeout=30):
        print('Waiting: '+label,flush=True);deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            result=predicate()
            if result:print('Passed: '+label,flush=True);return result
            time.sleep(.1)
        raise AssertionError(label)
    def start():
        with (root/'app.log').open('ab') as log:
            process=subprocess.Popen([str(args.app.resolve()/'Contents/MacOS/VoxDrop'),'--background'],
                env=env,stdout=log,stderr=log,start_new_session=True)
        guis.append(process);return process
    def services():
        found=[]
        for p in psutil.process_iter(['cmdline']):
            try:
                arguments=p.info['cmdline'] or []
                if len(arguments)>3 and arguments[3]==str(engine) and str(state) in arguments and 'run' in arguments:found.append(p)
            except psutil.Error:pass
        return found
    def gone(process):
        try:return not process.is_running() or process.status()==psutil.STATUS_ZOMBIE
        except psutil.Error:return True
    def job(path):
        if not dbfile.is_file():return None
        try:
            with sqlite3.connect(dbfile,timeout=.2) as db:
                db.row_factory=sqlite3.Row
                row=db.execute('SELECT * FROM jobs WHERE source=? ORDER BY id DESC LIMIT 1',(str(path),)).fetchone()
                return dict(row) if row else None
        except sqlite3.Error:return None
    def command(*arguments):
        return subprocess.run([str(python),'-BEs','-Xutf8',str(engine),'--state-dir',str(state),
            '--model-data',str(args.models.resolve()),*map(str,arguments)],capture_output=True,text=True,timeout=30,check=True)
    try:
        gui=start();service=wait(lambda:next(iter(services()),None),'native background entry')
        old=service.pid;service.kill()
        service=wait(lambda:next((p for p in services() if p.pid!=old),None),'dead service restarted')
        report['native_entry_and_supervisor_recovery']=True
        first=incoming/'Interrupted.wav';shutil.copyfile(args.fixture,first)
        digest=hashlib.sha256(first.read_bytes()).hexdigest()
        wait(lambda:(job(first) or {}).get('state')=='transcribing','first inference')
        temporary=wait(lambda:next(state.glob('jobs/*/transcription-*/smb-qwen-*/audio.npy'),None),'recoverable decoded audio')
        wait(lambda:(job(first) or {}).get('phase')=='Transkribieren (Qwen)','loaded model before service loss')
        service=services()[0];descendants=service.children(recursive=True);old=service.pid
        service.kill()
        wait(lambda:all(gone(p) for p in descendants),'no orphan inference after service SIGKILL',10)
        wait(lambda:(job(first) or {}).get('state')=='done','interrupted job automatically completed',120)
        assert not temporary.exists() and first.with_suffix('.txt').is_file()
        assert hashlib.sha256(first.read_bytes()).hexdigest()==digest
        report['service_crash_cleaned_audio_and_resumed_job']=True
        second=incoming/'Owner loss.wav'
        with wave.open(str(args.fixture),'rb') as source:
            parameters=source.getparams();frames=source.readframes(source.getnframes())
        with wave.open(str(second),'wb') as target:
            target.setparams(parameters);target.writeframes(frames+b'\0'*(parameters.nchannels*parameters.sampwidth*16000))
        wait(lambda:(job(second) or {}).get('state')=='transcribing','second inference')
        wait(lambda:next(state.glob('jobs/*/transcription-*/smb-qwen-*/audio.npy'),None),'loaded Qwen for GUI loss')
        wait(lambda:(job(second) or {}).get('phase')=='Transkribieren (Qwen)','loaded model before GUI loss')
        tracked=[]
        for p in psutil.process_iter(['cmdline']):
            try:
                if str(state) in (p.info['cmdline'] or []):tracked.extend([p,*p.children(recursive=True)])
            except psutil.Error:pass
        # A held write transaction prevents cooperative cancel writes. The
        # supervisor/pipe ownership must still release inference independently.
        with sqlite3.connect(dbfile) as blocked:
            blocked.execute('BEGIN IMMEDIATE');started=time.monotonic();gui.kill();gui.wait(5)
            try:
                wait(lambda:all(gone(p) for p in tracked),'GUI loss cleans tree despite SQLite writer lock',15)
            except AssertionError:
                report['alive_after_owner_loss']=[dict(pid=p.pid,args=p.cmdline()) for p in tracked if not gone(p)]
                raise
            report['owner_loss_stop_seconds']=round(time.monotonic()-started,3)
            blocked.rollback()
        report['gui_loss_with_locked_database_left_no_orphans']=True
        fresh=incoming/'Must wait for app.wav';shutil.copyfile(args.fixture,fresh)
        time.sleep(3);assert job(fresh) is None
        start();wait(lambda:(job(second) or {}).get('state')=='done','restart resumes owner-interrupted job',120)
        assert second.with_suffix('.txt').is_file()
        report['app_restart_resumed_queue']=True
        report['passed']=True
    finally:
        if dbfile.is_file():
            try:command('stop')
            except Exception:pass
        for process in guis:
            if process.poll() is None:process.terminate();process.wait(10)
        (root/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
