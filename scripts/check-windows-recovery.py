"""Windows fault injection using an isolated profile and synthetic audio.

Usage: python check-windows-recovery.py APP NEW_LOCAL_TEST_DIRECTORY SYNTHETIC_WAV
Stops only processes belonging to its newly created test profile. Never reboots.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import psutil

if sys.platform != 'win32':
    raise SystemExit('This native acceptance check requires Windows.')
if len(sys.argv) != 4:
    raise SystemExit(__doc__)
app,root,audio=[Path(p).resolve() for p in sys.argv[1:]]
root.mkdir(parents=True,exist_ok=False)
profile=root/'profile';profile.mkdir()
incoming=root/'incoming';incoming.mkdir()
config=profile/'config.json'
config.write_text(json.dumps(dict(folders=[str(incoming)],monitoring=True,
    interval_seconds=1,model='large-v3-turbo',hardware='cuda',speakers=False)),encoding='utf-8')
env={**os.environ,'VOXDROP_PROFILE':str(profile)}
subprocess.Popen([str(app/'VoxDrop.exe'),'--background'],env=env)
state=profile/'service';dbfile=state/'jobs.sqlite3'
python=app/'Laufzeit/runtime-fc8909c264e4/Scripts/python.exe'
engine=app/'Engine/watch_service.py'

def service_process():
    for p in psutil.process_iter(['name','cmdline']):
        try:
            args=p.info['cmdline'] or []
            if p.info['name']=='python.exe' and str(state) in args and 'run' in args:
                # uv's redirector and the actual interpreter have the same command.
                children=p.children()
                return next((c for c in children if c.name()=='python.exe'),p)
        except psutil.Error:pass
    return None

def wait_for(predicate,seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        value=predicate()
        if value:return value
        time.sleep(.2)
    return None

def job():
    if not dbfile.exists():return None
    with sqlite3.connect(dbfile) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 1').fetchone()
        return dict(row) if row else None

def start_service():
    subprocess.run([str(python),'-BEs','-Xutf8',str(engine),'--state-dir',str(state),
        '--model-data',str(app/'Modelle'),'start',str(config)],check=True,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return wait_for(service_process,10)

report={}
try:
    service=wait_for(service_process,15)
    assert service,'background EXE did not start worker'
    report['background_exe_started_service']=True
    service.kill();service.wait(5)
    recovered=wait_for(service_process,20)
    report['gui_restarted_dead_service']=bool(recovered)
    service=recovered or start_service()
    target=incoming/'Synthetic.wav';shutil.copyfile(audio,target)
    original=hashlib.sha256(target.read_bytes()).hexdigest()
    active=wait_for(lambda: (r if (r:=job()) and r['state']=='transcribing' else None),30)
    assert active,'job did not begin'
    descendants=service.children(recursive=True)
    service.kill();service.wait(5)
    time.sleep(.5)
    orphans=[p for p in descendants if p.is_running()]
    report['orphan_inference_processes_after_service_kill']=len(orphans)
    for p in reversed(orphans):
        try:p.kill()
        except psutil.Error:pass
    # Wait for the GUI watchdog, or explicitly restart the baseline worker.
    recovered=wait_for(service_process,12) or start_service()
    finished=wait_for(lambda: (r if (r:=job()) and r['state'] in ('done','failed','blocked') else None),45)
    report['interrupted_job_final_state']=finished['state'] if finished else (job() or {}).get('state')
    report['original_unchanged']=hashlib.sha256(target.read_bytes()).hexdigest()==original
    report['txt_published']=target.with_suffix('.txt').exists()
finally:
    for p in psutil.process_iter(['name','cmdline']):
        try:
            args=p.info['cmdline'] or []
            owned=str(state) in args or (p.info['name']=='pythonw.exe' and
                  str(app/'Desktop/desktop.py') in args and
                  p.environ().get('VOXDROP_PROFILE')==str(profile))
            if owned:
                for child in p.children(recursive=True):
                    try:child.kill()
                    except psutil.Error:pass
                p.kill()
        except psutil.Error:pass
    (root/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
