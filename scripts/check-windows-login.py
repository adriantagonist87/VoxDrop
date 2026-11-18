"""One-shot native login observer. Run with a PRIVATE JSON configuration.

The observer never launches VoxDrop. It waits for the registered background GUI,
supervisor and service after a new boot, then adds only its synthetic fixture.
Configuration/report contain local paths and must stay outside public Git.
"""
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import psutil
import winreg

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
app, profile, fixture, incoming, output = [Path(config[key]) for key in ('app','profile','fixture','incoming','report')]
report = dict(started=time.time(), boot_time=psutil.boot_time(), observer_started_app=False)
new_boot = report['boot_time'] > config['prepared_boot_time'] + 1

def roles():
    matches = {'gui': [], 'supervisor': [], 'service': []}
    for process in psutil.process_iter(['exe','cmdline']):
        try:
            args = process.info['cmdline'] or []
            normalized = [str(arg).replace('\\','/').casefold() for arg in args]
            if not (process.info['exe'] or '').casefold().startswith(str(app).casefold()+'\\'):
                continue
            if any(arg.endswith('/desktop/desktop.py') for arg in normalized) and '--background' in args:
                matches['gui'].append(process)
            elif str(profile/'service') in args:
                if 'supervise' in args: matches['supervisor'].append(process)
                elif 'run' in args: matches['service'].append(process)
        except psutil.Error:
            pass
    result = {}
    for role, candidates in matches.items():
        pids = {process.pid for process in candidates}
        leaf = []
        for process in candidates:
            try:
                if not any(child.pid in pids for child in process.children()):
                    leaf.append(process.pid)
            except psutil.Error:
                pass
        result[role] = leaf
    return result

try:
    if not new_boot:
        raise RuntimeError('No new Windows boot since preparation; do not count this as login acceptance')
    report['code_commit'] = json.loads((app/'build-info.json').read_text())['code_commit']
    if report['code_commit'] != config['code_commit']:
        raise RuntimeError('Installed code changed after observer preparation')
    until = time.monotonic() + 120
    while time.monotonic() < until:
        current = roles()
        if all(len(pids) == 1 for pids in current.values()):
            break
        time.sleep(1)
    report['automatically_started_processes'] = current
    if not all(len(pids) == 1 for pids in current.values()):
        raise RuntimeError('Expected one background GUI, supervisor and worker without manually launching the app')
    report['app_seen_before_fixture'] = True
    target = incoming / ('VoxDrop-Anmeldetest-'+str(int(time.time()))+'.wav')
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    shutil.copyfile(fixture, target)
    report['fixture'] = str(target)
    until = time.monotonic() + 1800
    job = None
    dbpath = profile/'service/jobs.sqlite3'
    while time.monotonic() < until:
        try:
            with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True,timeout=3) as db:
                db.row_factory = sqlite3.Row
                row = db.execute('select * from jobs where source=? order by id desc limit 1',(str(target),)).fetchone()
                job = dict(row) if row else None
        except sqlite3.Error:
            pass
        if job and job['state'] in ('done','failed','blocked'):
            break
        time.sleep(2)
    report['job'] = job
    report['original_unchanged'] = hashlib.sha256(target.read_bytes()).hexdigest() == digest
    report['txt_published'] = target.with_suffix('.txt').is_file()
    report['passed'] = bool(job and job['state']=='done' and report['original_unchanged'] and report['txt_published'])
except Exception as error:
    report['passed'] = False
    report['error'] = str(error)
finally:
    report['finished'] = time.time()
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    if new_boot:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run',0,winreg.KEY_READ|winreg.KEY_SET_VALUE) as key:
            try:
                value,_ = winreg.QueryValueEx(key,'VoxDropAcceptanceObserver')
                if value == config['observer_run_value']:
                    winreg.DeleteValue(key,'VoxDropAcceptanceObserver')
            except FileNotFoundError:
                pass
