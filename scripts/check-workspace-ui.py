"""Render/test the real shared QML with isolated synthetic lists, never live media.

Run with the pinned Qt runtime. --native selects the real Windows/macOS Qt plugin;
this does not certify physical mouse, shell, tray, or OS display scaling.
Reports and screenshots may contain paths to the chosen output directory.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from contextlib import closing
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter, time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--scale', choices=('1','1.25','1.5'), default='1')
    parser.add_argument('--queue', type=int, default=8000)
    parser.add_argument('--history', type=int, default=20000)
    parser.add_argument('--content', action='store_true', help='Also write/search synthetic TXT files')
    args = parser.parse_args()
    if args.queue < 20 or args.history < 20:
        parser.error('At least 20 queue/history rows are required')
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ['QT_SCALE_FACTOR'] = args.scale
    os.environ['QT_QUICK_BACKEND'] = 'software'
    if not args.native:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    root = args.app.resolve()
    sys.path[:0] = [str(root/'Desktop' if (root/'Desktop').exists() else root/'desktop'),
                   str(root/'Engine' if (root/'Engine').exists() else root),
                   str(root/'.runtime/ci/VoxDrop/Engine')]
    with TemporaryDirectory(prefix='voxdrop-workspace-') as temporary:
        profile = Path(temporary)
        os.environ['VOXDROP_PROFILE'] = str(profile)
        import desktop
        import controller as module
        import watch_service as backend
        from transcript_search import search_transcripts
        from PySide6.QtCore import QObject, QPointF, QMetaObject, Qt, QCoreApplication, QEvent, qInstallMessageHandler
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtTest import QTest
        import psutil

        report = dict(passed=False, scale=args.scale, native=args.native,
                      queue=args.queue, history=args.history, timings={}, captures=[])
        warnings = []
        def qt_message(kind, context, message):
            warnings.append(message)
            print('Qt: '+message, file=sys.stderr, flush=True)
        qInstallMessageHandler(qt_message)
        app = desktop.create_app(['workspace-check'])
        report['qt_platform'] = app.platformName()
        state = profile/'service'
        backend.initialise(state)
        db = backend.database(state)
        now = time()
        options = {**module.DEFAULTS,'monitoring':True,'include_subfolders':True,
                   'language':'de','gpu_budget_percent':75,'dover_lap':True,
                   'folders':[r'D:\Beispiel\Besprechungen',r'Z:\Meetings']}
        start = perf_counter()
        with db:
            db.executemany('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated,state,started,finished) '
                           'VALUES(?,?,1,1,?,?,?, ?,?,?)',
                ((str(profile/f'Meeting {i:05} – Planung.wav'),str(profile),json.dumps(options),now-600,
                  now-i,'ready' if i<args.queue else ('failed' if i%50==0 else 'done'),
                  None if i<args.queue else now-600,None if i<args.queue else now-200)
                 for i in range(args.queue+args.history)))
        report['timings']['sqlite_seed_seconds'] = perf_counter()-start
        start = perf_counter()
        page = backend.history_jobs(db,'desc',250,terminal_only=True)
        counts = backend.history_counts(db)
        last = backend.history_jobs(db,'desc',250,terminal_only=True,offset=((args.history-1)//250)*250)
        matches = backend.history_jobs(db,'desc',250,terminal_only=True,search='*Meeting*9*')
        report['timings']['sqlite_pages_counts_wildcard_seconds'] = perf_counter()-start
        assert len(page)==min(250,args.history) and last and matches
        assert counts['all']==args.history
        if args.content:
            start = perf_counter()
            for i in range(args.queue,args.queue+args.history):
                (profile/f'Meeting {i:05} – Planung.txt').write_text(
                    ('Projektfortschritt und nächste Aufgaben.\n'*10)+('Abnahmebeispiel' if i%97==0 else ''),encoding='utf-8')
            result = search_transcripts(state/'jobs.sqlite3',state/'search.sqlite3',state/'matches.json',
                'Abnahmebeispiel',lambda job:backend.targets(job)[1],Event(),lambda text:None)
            report['content_result'] = result
            report['timings']['write_and_search_txt_seconds'] = perf_counter()-start
            cancelled = Event();cancelled.set()
            from transcript_search import SearchCancelled
            try:
                search_transcripts(state/'jobs.sqlite3',state/'search.sqlite3',state/'matches.json',
                    'Aufgaben',lambda job:backend.targets(job)[1],cancelled,lambda text:None)
                raise AssertionError('Detailsuche did not cancel')
            except SearchCancelled:
                report['content_cancelled'] = True
        db.close()
        api = module.Controller(preview=True)
        module.MODEL_DATA = Path(r'D:\VoxDrop\Modelle')
        api.draft = dict(options);api.saved_config=dict(options);api.paths=list(options['folders'])
        def public_job(job):
            return {**dict(job),'source':rf'D:\Beispiel\Besprechungen\{Path(job["source"]).name}',
                    'completed_dir':r'D:\Beispiel\Besprechungen'}
        with closing(backend.database(state)) as db:
            queue = [public_job(job) for job in db.execute("SELECT * FROM jobs WHERE state='ready' ORDER BY id")]
        current = {**queue[0],'id':999999,'state':'transcribing','started':now-240,
                   'progress':.6,'phase':'Spracherkennung (Qwen)','cancel_requested':False}
        api.snapshot = dict(running=True,service=dict(state='active'),
            folders=[dict(path=p,available=True,error=None,updated=now) for p in api.paths],
            queue=queue,jobs=[public_job(job) for job in page],current=current,waiting=len(queue),
            queue_paused=False,history_counts=counts,global_history_counts=counts)
        start = perf_counter();api.update_history();api.update_queue();api.setQueueCompact(True)
        engine = QQmlApplicationEngine();api.setParent(engine);window = desktop.load_window(engine,api)
        assert window is not None
        window.resize(1500,1000);window.show();QTest.qWait(350)
        report['timings']['initial_native_qml_seconds'] = perf_counter()-start
        def item(name):
            def visit(parent):
                if parent.objectName()==name:return parent
                for child in parent.childItems():
                    found=visit(child)
                    if found is not None:return found
            return visit(window.contentItem())
        def click(name):
            target=item(name)
            assert target is not None and target.isVisible() and target.isEnabled(),name
            position=target.mapToScene(QPointF(target.width()/2,target.height()/2))
            assert 0<=position.x()<=window.width() and 0<=position.y()<=window.height(),name
            QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,position.toPoint())
            QTest.qWait(80)
        def capture(name):
            QTest.qWait(100)
            assert window.grabWindow().save(str(args.output/(name+'.png'))),name
            button=item('queuePlaybackButton')
            assert button.width()==44 and button.height()==44
            report['captures'].append(name)
        capture('workspace-wide')
        start = perf_counter()
        api.setQueueSearch('*Meeting*123*');QTest.qWait(30)
        assert api.queue and len(api.queue)<len(queue)
        report['timings']['queue_wildcard_and_render_seconds'] = perf_counter()-start
        api.setQueueSearch('');window.resize(1010,630);QTest.qWait(120)
        capture('workspace-minimum')
        view=item('queueList');assert view.height()>=330
        click('historyTab');capture('history-minimum')
        window.setProperty('workTab',0)
        for tab,name in enumerate(('transcription','folders','app','import-export')):
            window.setProperty('settingsOpen',True);window.setProperty('settingsTab',tab)
            capture('settings-'+name+'-minimum')
            scroll=window.findChild(QObject,'settingsScroll').property('contentItem')
            scroll.setProperty('contentY',max(0,scroll.property('contentHeight')-scroll.property('height')))
            capture('settings-'+name+'-minimum-bottom')
            scroll.setProperty('contentY',0)
            window.resize(1280,820);capture('settings-'+name)
            window.resize(1010,630)
        window.setProperty('settingsOpen',False);QTest.qWait(80)
        click('queueActionsButton');capture('queue-actions')
        QTest.keyClick(window,Qt.Key.Key_Escape);QTest.qWait(40)
        api.showDetails(queue[0]['id']);capture('job-details')
        click('closeJobDialog')
        api.drop_plan=dict(counts=dict(new=2,queued=100,done=20,existing=5,problem=1),items=[
            dict(source=queue[i]['source'],kind='queued',status='Bereits in der Warteschlange') for i in range(100)])
        api.changed.emit();api.dropConflictOpened.emit();capture('drop-conflicts')
        QMetaObject.invokeMethod(window.findChild(QObject,'dropConflictDialog'),'close')
        for name in ('aboutDialog','feedbackDialog','confirmClear','confirmImport'):
            if name=='feedbackDialog':api.notify('Beispiel einer vollständigen Rückmeldung.\n'*100,True)
            dialog=window.findChild(QObject,name)
            assert dialog is not None and QMetaObject.invokeMethod(dialog,'open'),name
            capture(name)
            assert dialog.property('height')<=window.height()-35,name
            QMetaObject.invokeMethod(dialog,'close')
        report['rss_mib'] = round(psutil.Process().memory_info().rss/2**20,1)
        report['qml_messages'] = warnings
        assert not any('Error:' in s or 'ReferenceError' in s or 'TypeError' in s or 'Binding loop' in s for s in warnings),warnings
        report['passed']=True
        window.hide();engine.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        app.processEvents()
        (args.output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
