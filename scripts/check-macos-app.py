"""Native Cocoa/QML play-stop, real inference, queue and app-lifetime acceptance.

Uses a new private profile and copies only the supplied synthetic WAV. Run with
the bundle's Python. It never alters the native user profile or login item.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--models',type=Path,required=True)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    root=args.output.resolve(); profile=root/'profile';profile.mkdir()
    resources=args.app.resolve()/'Contents/Resources'
    sys.path[:0]=[str(resources/'Desktop'),str(resources/'Engine')]
    os.environ.update(VOXDROP_PROFILE=str(profile),VOXDROP_MODEL_DATA=str(args.models.resolve()))
    import desktop
    import controller as module
    import psutil
    from PySide6.QtCore import QCoreApplication,QEvent,QPointF,Qt,QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from window_state import WindowPresenter

    settings={**module.DEFAULTS,'folders':[],'monitoring':False,'language':'de',
              'gpu_budget_percent':10,'speakers':True,'skip_silence':True,'dover_lap':True}
    module.save_settings(settings)
    incoming=root/'Aufnahmen + Prüfung, Test';(incoming/'Unterordner').mkdir(parents=True)
    media=[incoming/'Besprechung Ä.wav',incoming/'Unterordner/Weitere Aufnahme.wav']
    for path in media:shutil.copyfile(args.fixture,path)
    hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in media}
    app=desktop.create_app(['native-mac-acceptance'])
    api=module.Controller();engine=QQmlApplicationEngine();api.setParent(engine);api.init_tray()
    window=desktop.load_window(engine,api);assert window is not None
    presenter=WindowPresenter(window);api.windowRequested.connect(presenter.show)
    gate=desktop.QuitInterceptor(api,app);app.installEventFilter(gate)
    report=dict(passed=False,qt_platform=app.platformName())
    def wait(predicate,label,timeout=90):
        print('Waiting: '+label,flush=True)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            QTest.qWait(30)
            if predicate():
                print('Passed: '+label,flush=True)
                return
        raise AssertionError(label+': '+api.message+'; '+str(api.content_status))
    def click_playback():
        def find(item):
            if item.objectName()=='queuePlaybackButton':return item
            for child in item.childItems():
                value=find(child)
                if value is not None:return value
        button=find(window.contentItem());assert button is not None and button.isEnabled()
        assert (button.width(),button.height())==(44,44)
        point=button.mapToScene(QPointF(22,22)).toPoint()
        QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
    try:
        presenter.show();api.start();wait(lambda:api.ready and not api.busy,'prepare')
        for mode in (Qt.WindowState.WindowMaximized,Qt.WindowState.WindowFullScreen):
            window.setWindowState(mode);QTest.qWait(1200)
            for _ in range(3):presenter.show();QTest.qWait(40);assert window.windowState()==mode
            window.hide();presenter.show();QTest.qWait(80);assert window.windowState()==mode
            window.showMinimized();QTest.qWait(1200);presenter.show();QTest.qWait(1500)
            assert window.windowState()==mode,(mode,window.windowState(),presenter.last_state)
        window.showNormal();window.resize(1280,820);QTest.qWait(300)
        report['native_window_modes']=True
        api.enqueueFolders([QUrl.fromLocalFile(str(incoming))])
        wait(lambda:(api.snapshot.get('current') or {}).get('state')=='transcribing'
             and (api.snapshot.get('current') or {}).get('phase')=='Transkribieren (Qwen)',
             'loaded Qwen inference')
        before=[row['id'] for row in api.snapshot.get('queue',[])]
        active_id=api.snapshot['current']['id']
        if active_id not in before:
            before.insert(0,active_id)
        started=time.monotonic();click_playback()
        wait(lambda:api.snapshot.get('queue_paused') and not api.snapshot.get('current') and not api.state['processingStopping'],'stop')
        report['stop_seconds']=round(time.monotonic()-started,3)
        assert [row['id'] for row in api.snapshot['queue']]==before
        assert not list((profile/'service/jobs').glob('*/transcription-*'))
        report['queue_preserved_on_stop']=True
        api.setGpuBudget(50);wait(lambda:not api.busy,'save budget')
        click_playback()
        wait(lambda:api.snapshot.get('current') is not None,'resumed inference')
        assert not module.read_settings()['monitoring']
        wait(lambda:all(path.with_suffix('.txt').is_file() for path in media)
             and not api.snapshot.get('current') and not api.snapshot.get('waiting'), 'real export and content reuse',90)
        for path in media:
            assert path.with_suffix('.txt').is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[str(path)]
        report['recursive_drop_metal_export_and_content_reuse']=True
        if api.hasTray():
            window.close();QTest.qWait(250);assert not window.isVisible()
            api.windowRequested.emit();QTest.qWait(100);assert window.isVisible()
            report['x_hides_and_tray_reopens']=True
        jobs=api.snapshot['jobs'];api.showDetails(jobs[0]['id'])
        api.setHistorySearch('Sonnenschein');wait(lambda:not api.busy,'search ready')
        api.startContentSearch();wait(lambda:bool(api.content_token) and not api.content_running,'content search')
        report['real_transcript_search']=True
        import sqlite3
        with sqlite3.connect(profile/'service/jobs.sqlite3') as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
            speakers=db.execute('SELECT speaker_method,speaker_passes FROM speaker_diarization').fetchall()
            assert speakers and all(method=='dover-lap' and passes==3 for method,passes in speakers),speakers
            report['speaker_fusion']=speakers
        tracked=[]
        for process in psutil.process_iter(['cmdline']):
            if any(str(profile) in arg for arg in process.info['cmdline'] or []):
                tracked.append(process)
                tracked.extend(process.children(recursive=True))
        QCoreApplication.sendEvent(app,QEvent(QEvent.Type.Quit))
        wait(lambda:api.shutdown_complete,'native quit')
        _,alive=psutil.wait_procs(tracked,timeout=10)
        assert not alive,[(p.pid,p.cmdline()) for p in alive]
        report['native_quit_stopped_profile_tree']=True
        report['passed']=True
    finally:
        if not api.shutdown_complete:
            api.ensureStopped()
        window.hide();api.timer.stop();api.drop_timer.stop()
        (root/'summary.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
