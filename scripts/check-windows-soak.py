"""Native Windows 30-minute acceptance using a fresh isolated profile.

Usage: python check-windows-soak.py APP NEW_LOCAL_TEST_DIRECTORY SYNTHETIC_WAV [SECONDS]
SECONDS must be at least 1800 (default). Uses installed models and CUDA, closes only
its own test GUI, injects process/folder failures, and restores its own test files.
Never reboots or changes autostart, firewall, or productive settings. Keep reports
private because they contain local paths. Use synthetic audio of about 15 seconds.
"""
import ctypes
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import psutil

if sys.platform != 'win32' or len(sys.argv) not in (4, 5):
    raise SystemExit(__doc__)
app, root, audio = [Path(v).resolve() for v in sys.argv[1:4]]
duration = int(sys.argv[4]) if len(sys.argv) > 4 else 1800
if duration < 1800:
    raise SystemExit('The scheduled acceptance scenarios require at least 1800 seconds.')
if not audio.is_file() or not (app/'VoxDrop.exe').is_file():
    raise SystemExit('Installed app and synthetic audio file are required.')
lock_hash = hashlib.sha256((app/'windows/uv.lock').read_bytes()).hexdigest()[:12]
python = app/f'Laufzeit/runtime-{lock_hash}/Scripts/python.exe'
if not python.is_file():
    raise SystemExit('Prepare the installed app runtime before running this check.')
root.mkdir(parents=True, exist_ok=False)
profile = root / 'profile'; profile.mkdir()
state = profile / 'service'
folders = [root / 'A', root / 'B']
for p in folders: p.mkdir()
offline = root / 'B-offline'
config = profile / 'config.json'
settings = dict(folders=[str(p) for p in folders], monitoring=True, interval_seconds=1,
                model='large-v3-turbo', hardware='cuda', speakers=False)
env = {**os.environ, 'VOXDROP_PROFILE': str(profile)}
payload = audio.read_bytes()
original_hash = hashlib.sha256(payload).hexdigest()
expected = {}
events = []
samples = []
errors = []
started = time.monotonic()
fired = set()
locked = None
growing = None
growing_chunks = []

def stamp(): return round(time.monotonic() - started, 2)

def event(name, **values):
    item = dict(seconds=stamp(), event=name, **values)
    events.append(item)
    print(json.dumps(item), flush=True)

def save_config():
    temp = config.with_suffix('.new')
    with temp.open('w', encoding='utf-8') as out:
        json.dump(settings, out); out.flush(); os.fsync(out.fileno())
    temp.replace(config)

def launch():
    subprocess.Popen([str(app/'VoxDrop.exe'), '--background'], env=env,
                     creationflags=subprocess.CREATE_NO_WINDOW)

def roots():
    result = []
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            args = p.info['cmdline'] or []
            if p.info['name'] not in ('python.exe', 'pythonw.exe'): continue
            if str(state) in args or (str(app/'Desktop/desktop.py') in args and
                p.environ().get('VOXDROP_PROFILE') == str(profile)):
                result.append(p)
        except psutil.Error: pass
    return result

def logical(mode):
    candidates = []
    for p in roots():
        try:
            if mode in p.cmdline(): candidates.append(p)
        except psutil.Error: pass
    ids = {p.pid for p in candidates}
    result=[]
    for p in candidates:
        try:
            if not any(c.pid in ids for c in p.children()): result.append(p)
        except psutil.Error: pass
    return result

def jobs():
    path=state/'jobs.sqlite3'
    if not path.exists(): return []
    with sqlite3.connect(path, timeout=2) as db:
        db.row_factory=sqlite3.Row
        return [dict(r) for r in db.execute('SELECT id,source,state,attempt FROM jobs')]

def add(name, folder=0):
    path=folders[folder]/name
    path.write_bytes(payload)
    expected[str(path)]=original_hash
    event('new_audio',file=name)
    return path

def owned_tree():
    found={}
    for p in roots():
        try:
            for child in [p,*p.children(recursive=True)]: found[child.pid]=child
        except psutil.Error: pass
    return list(found.values())

def terminate_mode(mode):
    for p in logical(mode):
        try: p.kill()
        except psutil.Error: pass
    event('killed_test_process',mode=mode)

save_config(); launch(); event('started',code=json.loads((app/'build-info.json').read_text())['code_commit'])
next_sample=0
next_periodic=40
corrupt_restore=None
try:
    while stamp() < duration:
        elapsed=stamp()
        if elapsed >= next_periodic and elapsed < duration-180:
            add(f'Periodic-{int(next_periodic):04d}.wav')
            next_periodic += 120
        if elapsed >= 100 and 100 not in fired:
            fired.add(100)
            path=add('Temporarily-locked.wav')
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,
                                        ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
            kernel.CreateFileW.restype=ctypes.c_void_p
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            locked=kernel.CreateFileW(str(path),0x80000000,0,None,3,0x80,None)
            if locked == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
            event('exclusive_file_lock')
        if elapsed >= 130 and 130 not in fired:
            fired.add(130); kernel.CloseHandle(locked); locked=None; event('file_lock_released')
        if elapsed >= 200 and 200 not in fired:
            fired.add(200); (folders[0]/'Invalid.wav').write_bytes(b'not an audio file'); event('invalid_media')
        if elapsed >= 240 and 240 not in fired:
            fired.add(240)
            for p in roots():
                try:
                    if p.name()=='pythonw.exe': p.kill()
                except psutil.Error: pass
            event('closed_test_gui_worker_keeps_running')
        if elapsed >= 360 and 360 not in fired:
            fired.add(360); terminate_mode('run')
        if elapsed >= 480 and 480 not in fired:
            fired.add(480); folders[1].rename(offline); event('folder_B_offline')
        if elapsed >= 490 and 490 not in fired:
            fired.add(490); add('Other-folder-during-outage.wav')
        if elapsed >= 520 and 520 not in fired:
            fired.add(520); offline.rename(folders[1]); add('Returned-folder.wav',1); event('folder_B_returned')
        if elapsed >= 600 and 600 not in fired:
            fired.add(600); settings['monitoring']=False; save_config(); event('monitoring_paused')
        if elapsed >= 610 and 610 not in fired:
            fired.add(610); add('Wait-for-resume.wav')
        if elapsed >= 650 and 650 not in fired:
            fired.add(650)
            paused_ok=not (folders[0]/'Wait-for-resume.txt').exists()
            if not paused_ok: errors.append('paused monitoring processed a new file')
            event('pause_checked',ok=paused_ok)
        if elapsed >= 660 and 660 not in fired:
            fired.add(660); settings['monitoring']=True; save_config(); event('monitoring_resumed')
        if elapsed >= 720 and 720 not in fired:
            fired.add(720); growing=(folders[0]/'Still-copying.wav').open('wb')
            growing_chunks=[payload[i:i+len(payload)//24+1] for i in range(0,len(payload),len(payload)//24+1)]
            expected[str(folders[0]/'Still-copying.wav')]=original_hash
            event('slow_copy_started')
        if growing is not None:
            if growing_chunks:
                growing.write(growing_chunks.pop(0)); growing.flush()
                if (folders[0]/'Still-copying.txt').exists(): errors.append('published during changing file')
            else:
                growing.close(); growing=None; event('slow_copy_finished')
        if elapsed >= 840 and 840 not in fired:
            fired.add(840)
            py=python
            for _ in range(3):
                subprocess.run([str(py),'-BEs','-Xutf8',str(app/'Engine/watch_service.py'),
                    '--state-dir',str(state),'--model-data',str(app/'Modelle'),'start',str(config)],
                    check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            event('duplicate_start_checked',supervisors=len(logical('supervise')),workers=len(logical('run')))
            if len(logical('supervise'))!=1 or len(logical('run'))!=1: errors.append('duplicate background service')
        if elapsed >= 900 and 900 not in fired:
            fired.add(900); terminate_mode('supervise'); time.sleep(1); launch(); event('login_entry_equivalent_relaunch')
        if elapsed >= 1060 and 1060 not in fired:
            fired.add(1060); path=add('Existing-result.wav'); path.with_suffix('.txt').write_text('KEEP EXISTING RESULT\n'); event('output_collision')
        if elapsed >= 1200 and 1200 not in fired:
            fired.add(1200); folders[1].rename(offline); event('second_folder_outage')
        if elapsed >= 1260 and 1260 not in fired:
            fired.add(1260); offline.rename(folders[1]); add('After-second-outage.wav',1); event('second_folder_recovery')
        if elapsed >= 1350 and 1350 not in fired:
            fired.add(1350); corrupt_restore=config.read_bytes(); config.write_text('{incomplete'); event('temporary_invalid_config')
        if elapsed >= 1360 and 1360 not in fired:
            fired.add(1360); save_config(); corrupt_restore=None; add('After-config-recovery.wav'); event('config_restored')
        if elapsed >= 1620 and 1620 not in fired:
            fired.add(1620); settings['model']='qwen3-asr-1.7b'; save_config(); add('Qwen-final.wav'); event('qwen_model_selected')
        if elapsed >= next_sample:
            next_sample += 5
            processes=owned_tree(); rss=handles=0
            for p in processes:
                try: rss+=p.memory_info().rss; handles+=p.num_handles()
                except psutil.Error: pass
            rows=jobs(); counts={s:sum(r['state']==s for r in rows) for s in ('done','failed','blocked','seen','ready','copying','transcribing','exporting')}
            item=dict(seconds=elapsed,rss=rss,handles=handles,processes=len(processes),states=counts)
            samples.append(item)
            if int(elapsed//30)!=int((elapsed-5)//30): event('heartbeat',**counts,rss_mib=round(rss/2**20,1),processes=len(processes))
        time.sleep(.25)
    rows=jobs()
    for path,sha in expected.items():
        target=Path(path)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=sha: errors.append('synthetic original hash changed')
        if target.name!='Existing-result.wav' and not target.with_suffix('.txt').exists(): errors.append('expected TXT missing: '+target.name)
    if (folders[0]/'Existing-result.txt').read_text()!='KEEP EXISTING RESULT\n': errors.append('existing result overwritten')
    if not any(Path(r['source']).name=='Invalid.wav' and r['state']=='failed' for r in rows): errors.append('invalid media did not remain failed')
    if not any(Path(r['source']).name=='Existing-result.wav' and r['state']=='blocked' for r in rows): errors.append('collision did not remain blocked')
    if not logical('run') or len(logical('supervise'))!=1: errors.append('service not healthy at end')
except BaseException as error:
    errors.append('harness exception: '+type(error).__name__+': '+str(error))
    raise
finally:
    if locked is not None: kernel.CloseHandle(locked)
    if growing is not None: growing.close()
    if corrupt_restore is not None: save_config()
    if offline.exists() and not folders[1].exists(): offline.rename(folders[1])
    idle=[s for s in samples if not any(s['states'][k] for k in ('copying','transcribing','exporting'))]
    report=dict(duration_seconds=stamp(),events=events,errors=errors,expected_audio_count=len(expected),
                code_commit=json.loads((app/'build-info.json').read_text())['code_commit'],
                final_jobs=jobs(),peak_rss_bytes=max((s['rss'] for s in samples),default=0),
                idle_rss_first=idle[0]['rss'] if idle else None,idle_rss_last=idle[-1]['rss'] if idle else None,
                idle_handles_first=idle[0]['handles'] if idle else None,idle_handles_last=idle[-1]['handles'] if idle else None,
                log_bytes=sum(p.stat().st_size for p in state.glob('*.log*')),
                actual_windows_reboot=False)
    (root/'samples.json').write_text(json.dumps(samples),encoding='utf-8')
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for p in owned_tree()[::-1]:
        try: p.kill()
        except psutil.Error: pass
    print(json.dumps({k:v for k,v in report.items() if k not in ('events','final_jobs')},indent=2),flush=True)
raise SystemExit(bool(errors))
