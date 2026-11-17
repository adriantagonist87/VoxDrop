"""Windows fault injection using an isolated profile and synthetic audio.

Usage: python check-windows-recovery.py APP NEW_LOCAL_TEST_DIRECTORY SYNTHETIC_WAV [MODEL]
MODEL is large-v3-turbo (default) or qwen3-asr-1.7b. Qwen also checks decoded
audio confinement and cleanup after a hard worker interruption.
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
if len(sys.argv) not in (4,5):
    raise SystemExit(__doc__)
app,root,audio=[Path(p).resolve() for p in sys.argv[1:4]]
model=sys.argv[4] if len(sys.argv)==5 else 'large-v3-turbo'
if model not in ('large-v3-turbo','qwen3-asr-1.7b'):raise SystemExit('Unknown model')
root.mkdir(parents=True,exist_ok=False)
profile=root/'profile';profile.mkdir()
incoming=root/'incoming';incoming.mkdir()
config=profile/'config.json'
config.write_text(json.dumps(dict(folders=[str(incoming)],monitoring=True,
    interval_seconds=1,model=model,hardware='cuda',speakers=False)),encoding='utf-8')
env={**os.environ,'VOXDROP_PROFILE':str(profile)}
subprocess.Popen([str(app/'VoxDrop.exe'),'--background'],env=env)
state=profile/'service';dbfile=state/'jobs.sqlite3'
lock_hash=hashlib.sha256((app/'windows/uv.lock').read_bytes()).hexdigest()[:12]
python=app/f'Laufzeit/runtime-{lock_hash}/Scripts/python.exe'
engine=app/'Engine/watch_service.py'

def service_candidates():
    result=[]
    for p in psutil.process_iter(['name','cmdline']):
        try:
            args=p.info['cmdline'] or []
            if p.info['name']=='python.exe' and str(state) in args and 'run' in args:
                result.append(p)
        except psutil.Error:pass
    return result


def service_process():
    candidates=service_candidates()
    ids={p.pid for p in candidates}
    for p in candidates:
        try:
            if not any(c.pid in ids for c in p.children()):return p
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
temporary_audio=None
try:
    service=wait_for(service_process,15)
    assert service,'background EXE did not start worker'
    report['background_exe_started_service']=True
    previous={p.pid for p in service_candidates()}
    service.kill();service.wait(5)
    recovered=wait_for(lambda: (p if (p:=service_process()) and p.pid not in previous else None),20)
    report['supervisor_restarted_dead_service']=bool(recovered)
    service=recovered or start_service()
    target=incoming/'Synthetic.wav';shutil.copyfile(audio,target)
    original=hashlib.sha256(target.read_bytes()).hexdigest()
    active=wait_for(lambda: (r if (r:=job()) and r['state']=='transcribing' else None),30)
    assert active,'job did not begin'
    if model=='qwen3-asr-1.7b':
        temporary_audio=wait_for(lambda: next(state.glob('jobs/*/transcription-*/smb-qwen-*/audio.npy'),None),45)
        assert temporary_audio, 'Qwen did not allocate decoded audio inside recoverable job storage'
        report['temporary_audio_inside_job']=temporary_audio.is_relative_to(state/'jobs')
        report['temporary_audio_bytes']=temporary_audio.stat().st_size
    service=service_process()
    assert service, "worker disappeared before fault injection"
    descendants=service.children(recursive=True)
    service.kill();service.wait(5)
    time.sleep(.5)
    orphans=[p for p in descendants if p.is_running()]
    report['orphan_inference_processes_after_service_kill']=len(orphans)
    for p in reversed(orphans):
        try:p.kill()
        except psutil.Error:pass
    # Wait for the supervisor, or explicitly restart the baseline worker.
    recovered=wait_for(service_process,12) or start_service()
    finished=wait_for(lambda: (r if (r:=job()) and r['state'] in ('done','failed','blocked') else None),90)
    report['interrupted_job_final_state']=finished['state'] if finished else (job() or {}).get('state')
    report['original_unchanged']=hashlib.sha256(target.read_bytes()).hexdigest()==original
    report['txt_published']=target.with_suffix('.txt').exists()
    if temporary_audio is not None:
        report['interrupted_temporary_audio_removed']=not temporary_audio.exists()
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

raise SystemExit(not (report.get('background_exe_started_service') and
    report.get('supervisor_restarted_dead_service') and
    report.get('orphan_inference_processes_after_service_kill') == 0 and
    report.get('interrupted_job_final_state') == 'done' and
    report.get('original_unchanged') and report.get('txt_published') and
    (model!='qwen3-asr-1.7b' or (report.get('temporary_audio_inside_job') and
     report.get('interrupted_temporary_audio_removed')))))
