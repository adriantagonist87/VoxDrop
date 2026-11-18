import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, QUrl, QPoint, QPointF
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.window_state import WindowPresenter

DESKTOP = Path(__file__).resolve().parents[1] / "desktop"


class DesktopWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        QQuickStyle.setStyle("Basic")
        sys.path.insert(0, str(DESKTOP))
        import controller
        cls.controller_module = controller

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(patch.object(self.controller_module, "PROFILE", Path(directory.name)))
        self.enterContext(patch.object(self.controller_module, "MODEL_DATA", Path(directory.name) / "data"))
        self.controller = self.controller_module.Controller(preview=True)
        self.engine = QQmlApplicationEngine()
        self.controller.setParent(self.engine)
        self.engine.setInitialProperties({"api": self.controller})
        self.engine.load(QUrl.fromLocalFile(str(DESKTOP / "qml/Main.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]
        self.presenter = WindowPresenter(self.window)
        self.addCleanup(self.dispose_window)

    def dispose_window(self):
        self.controller.content_cancel.set()
        self.window.hide()
        self.engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def test_full_qml_fullscreen_survives_minimization_and_native_activation(self):
        self.presenter.show()
        QTest.qWait(300)
        self.window.showFullScreen()
        QTest.qWait(300)
        self.window.showMinimized()
        QTest.qWait(300)
        self.presenter.show()
        QTest.qWait(300)
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowFullScreen)
        self.assertTrue(self.window.isVisible())

    def test_network_wait_offers_cancel_and_recursive_mode_locks_archive_option(self):
        self.presenter.show()
        self.controller.downloading = True
        self.controller.network_permission_changed(True)
        self.controller.setSetting("include_subfolders", True)
        QTest.qWait(50)
        cancel = self.window.findChild(QObject, "cancelNetworkWait")
        self.assertTrue(cancel.property("visible"))
        self.assertTrue(cancel.property("enabled"))
        self.assertFalse(self.window.findChild(QObject, "createOutputSubfolder").property("enabled"))
        self.controller.cancelNetworkWait()
        self.assertTrue(self.controller.network_cancel.is_set())
        self.controller.network_permission_changed(False)
        QTest.qWait(50)
        self.assertFalse(cancel.property("visible"))

    def queue_fixture(self,count=3):
        jobs=[dict(id=i,source=str(self.controller_module.PROFILE/f'Aufnahme {i} mit langem Namen.wav'),
            completed_dir=str(self.controller_module.PROFILE),size=123456,mtime_ns=1,
            state='ready',detected=100,updated=100,started=None,finished=None,error=None,
            origin_job_id=None,settings=json.dumps(self.controller_module.DEFAULTS)) for i in range(1,count+1)]
        self.controller.snapshot=dict(queue=jobs,jobs=[],waiting=count,current=None,queue_paused=False)
        self.controller.update_queue();self.controller.changed.emit()
        self.presenter.show();QTest.qWait(200)
        return jobs

    def visual(self,name):
        def visit(item):
            if item.objectName()==name:return item
            for child in item.childItems():
                found=visit(child)
                if found:return found
            return None
        return visit(self.window.contentItem())

    def test_queue_is_visible_and_not_limited_to_250_history_rows(self):
        jobs=self.queue_fixture(301)
        view=self.window.findChild(QObject,'queueList')
        self.assertEqual(view.property('count'),301)
        self.assertEqual(len(self.controller.queue),301)
        self.assertTrue(view.property('visible'))
        self.assertIsNotNone(self.visual('removeQueue1'))
        self.controller.showDetails(jobs[-1]['id'])
        self.assertEqual(self.controller.selected['id'],301)

    def test_real_qml_drag_emits_persistent_move_command(self):
        self.queue_fixture(3)
        handle=self.visual('queueDragHandle1');target=self.visual('queueRow2')
        self.assertIsNotNone(handle);self.assertIsNotNone(target)
        start=handle.mapToScene(QPointF(14,15)).toPoint()
        end=target.mapToScene(QPointF(20,target.height()-8)).toPoint()
        with patch.object(self.controller_module,'command',return_value='') as command, patch.object(self.controller,'action',side_effect=lambda operation,message:operation()):
            QTest.mousePress(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
            for step in range(1,13):
                point=QPoint(start.x(),round(start.y()+(end.y()-start.y())*step/12))
                QTest.mouseMove(self.window,point,30)
            QTest.mouseRelease(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
            QTest.qWait(50)
        command.assert_called_once_with('move-queue',1,3)
        self.assertFalse(self.controller.queue_dragging)

    def test_history_buttons_show_global_counts_and_highlight_errors_until_zero(self):
        self.controller.snapshot = dict(jobs=[], history_counts=dict(all=600, errors=3, done=595))
        self.controller.changed.emit()
        self.presenter.show()
        self.window.resize(1010, 630)
        QTest.qWait(100)
        buttons = {value: self.visual('historyFilter_' + value) for value in ('all', 'errors', 'done')}
        self.assertEqual([buttons[value].property('text') for value in buttons],
                         ['Alle (600)', 'Fehler (3)', 'Fertig (595)'])
        errors = buttons['errors']
        self.assertEqual(errors.property('background').property('color').name(), '#b5303a')
        self.controller.setFilter('errors')
        QTest.qWait(20)
        self.assertTrue(errors.property('checked'))
        self.assertEqual(errors.property('background').property('color').name(), '#b5303a')
        self.controller.snapshot['history_counts'] = dict(all=597, errors=0, done=595)
        self.controller.changed.emit()
        self.controller.setFilter('all')
        QTest.qWait(20)
        self.assertEqual(errors.property('text'), 'Fehler (0)')
        self.assertFalse(errors.property('errorAlert'))
        self.assertEqual(errors.property('background').property('color').name(), '#292929')

    def test_compact_queue_expands_globally_and_per_row_and_saves_preference(self):
        self.queue_fixture(12)
        row = self.visual('queueRow1')
        self.assertFalse(row.property('expanded'))
        compact_height = row.height()
        self.assertLess(compact_height, 80)
        expand = self.visual('expandQueue1')
        point = expand.mapToScene(QPointF(expand.width() / 2, expand.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        QTest.qWait(30)
        self.assertTrue(row.property('expanded'))
        self.assertGreater(row.height(), compact_height + 60)
        toggle = self.visual('queueDetailsToggle')
        point = toggle.mapToScene(QPointF(toggle.width() / 2, toggle.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        QTest.qWait(30)
        self.assertFalse(self.controller.state['queueCompact'])
        self.assertTrue(self.visual('queueRow2').property('expanded'))
        self.assertFalse(self.controller.preferences.value('queueCompact', True, type=bool))
        self.controller.setQueueCompact(True)
        QTest.qWait(30)
        self.assertFalse(row.property('expanded'))
        self.assertFalse(self.visual('queueRow2').property('expanded'))
        self.assertEqual(row.height(), compact_height)

    def test_programmatic_folder_edit_updates_saved_draft(self):
        self.controller.paths=[str(self.controller_module.PROFILE/'old')]
        self.controller.foldersChanged.emit();QTest.qWait(50)
        field=self.visual('folderField0')
        self.assertIsNotNone(field)
        new=str(self.controller_module.PROFILE/'new')
        field.setProperty('text',new)
        QTest.qWait(20)
        self.assertEqual(self.controller.config()['folders'],[new])

    def test_open_transcript_uses_local_file_url_with_os_default_application(self):
        jobs=self.queue_fixture(1);job=jobs[0];job['state']='done'
        path=Path(job['source']).with_suffix('.txt');path.write_text('Synthetic transcript',encoding='utf-8')
        self.controller.selected=job
        with patch.object(self.controller_module.QDesktopServices,'openUrl',return_value=True) as opened, patch.object(self.controller,'submit',side_effect=lambda operation,callback:callback(operation(),None)):
            self.controller.openTranscript()
        opened.assert_called_once_with(QUrl.fromLocalFile(str(path)))
        self.assertTrue(self.controller.detail['openTranscript'])

    def test_imported_results_do_not_claim_a_model_or_new_inference(self):
        job=self.queue_fixture(1)[0]
        job.update(state='existing',result_kind='existing')
        self.controller.selected=job
        rows={row['label']:row['value'] for row in self.controller.detail['rows']}
        self.assertEqual(rows['Modell verwendet'],'Nicht bekannt (Bestandsdatei)')
        self.assertEqual(rows['Dauer Spracherkennung'],'Nicht erneut ausgeführt')
        self.assertEqual(rows['Verfahren der Sprecherzuordnung'],'Nicht neu bestimmt')
        self.assertEqual(rows['Rechengerät'],'Keine neue Inferenz')
        for kind in ('reused','duplicate'):
            job['result_kind']=kind
            rows={row['label']:row['value'] for row in self.controller.detail['rows']}
            self.assertEqual(rows['Modell verwendet'],'Siehe Ursprungsauftrag')

    def test_reveal_uses_known_transcript_path_and_reports_shell_failure(self):
        job = self.queue_fixture(1)[0]
        transcript = self.controller_module.PROFILE / 'Bestands TXT, Prüfung + Test.txt'
        transcript.write_text('Synthetic transcript', encoding='utf-8')
        job.update(state='existing', result_kind='existing', known_transcript_path=str(transcript))
        self.controller.selected = job
        def immediately(operation, finished):
            try:
                result = operation()
            except Exception as error:
                finished(None, str(error))
            else:
                finished(result, None)
        with patch.object(self.controller_module.sys, 'platform', 'win32'), patch.object(self.controller, 'submit', side_effect=immediately):
            with patch.object(self.controller_module, 'reveal_in_explorer') as reveal:
                self.controller.revealOutput()
            reveal.assert_called_once_with(transcript)
            with patch.object(self.controller_module, 'reveal_in_explorer', side_effect=OSError('Shell selection failed')):
                self.controller.revealOutput()
            self.assertTrue(self.controller.message_error)
            self.assertEqual(self.controller.message, 'Shell selection failed')

    def test_search_fields_toggle_filter_queue_and_content_search_requires_start(self):
        self.queue_fixture(12)
        def click(name):
            item = self.visual(name)
            point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
            QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
            QTest.qWait(25)
        self.assertFalse(self.visual('queueSearchField').property('visible'))
        click('queueSearchToggle')
        self.assertTrue(self.visual('queueSearchField').property('visible'))
        self.visual('queueSearchField').setProperty('text', '* 2 mit*')
        QTest.qWait(25)
        self.assertEqual([job['id'] for job in self.controller.queue], [2])
        self.assertEqual(self.controller.queue[0]['position'], 2)
        self.assertFalse(self.visual('queueDragHandle2').property('enabled'))
        click('queueSearchToggle')
        self.assertEqual(len(self.controller.queue), 12)
        self.assertEqual(self.controller.queue_query, '')
        click('historySearchToggle')
        self.visual('historySearchField').setProperty('text', 'Suchbegriff')
        QTest.qWait(25)
        self.assertFalse(self.controller.content_running)
        self.assertFalse((self.controller_module.PROFILE / 'service/transcript-search.sqlite3').exists())
        pending = []
        with patch.object(self.controller, 'submit', side_effect=lambda operation, finished: pending.append((operation, finished))):
            click('contentSearchButton')
            self.assertTrue(self.controller.content_running)
            self.assertEqual(len(pending), 1)
            click('contentSearchButton')
            self.assertTrue(self.controller.content_cancel.is_set())
            self.assertFalse(self.visual('contentSearchButton').property('enabled'))
            pending[0][1](None, 'Detailsuche gestoppt.')
        self.assertFalse(self.controller.content_running)
        self.assertFalse(self.controller.content_token)

    def test_drop_conflict_dialog_shows_batch_and_prioritises_only_after_click(self):
        self.presenter.show()
        self.controller.drop_plan = dict(token='synthetic-batch', counts=dict(new=1, queued=1, active=0, done=1, existing=0, problem=0),
            warnings=[], items=[dict(source=str(self.controller_module.PROFILE / 'Queued.wav'), kind='queued', status='Bereits in der Warteschlange')])
        self.controller.changed.emit()
        self.controller.dropConflictOpened.emit()
        QTest.qWait(50)
        dialog = self.window.findChild(QObject, 'dropConflictDialog')
        self.addCleanup(self.controller.dismissDrop)
        self.assertTrue(dialog.property('visible'))
        self.assertEqual(dialog.findChild(QObject, 'dropConflictList').property('count'), 1)
        result = dict(queued=1, selected=2, ignored=1, active=0, interrupted=None, pending=True, warnings=[])
        config = self.controller_module.PROFILE / 'config.json'; config.write_text('{}')
        def command(*arguments):
            return json.dumps(result) if arguments[0] == 'resolve-drop' else ''
        with patch.object(self.controller_module, 'CONFIG', config), patch.object(self.controller_module, 'command', side_effect=command) as sent, patch.object(self.controller, 'submit', side_effect=lambda operation, finished: finished(operation(), None)):
            sent.assert_not_called()
            button = dialog.findChild(QObject, 'dropFrontButton')
            point = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
            QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
            QTest.qWait(30)
            self.assertEqual(sent.call_args_list[0].args, ('resolve-drop', 'synthetic-batch', 'front'))
            self.assertFalse(dialog.property('visible'))
        self.assertFalse(self.controller.drop_plan)

    def test_pause_button_can_stop_future_immediate_selection_without_resuming_all(self):
        self.queue_fixture(3)
        self.controller.snapshot.update(queue_paused=True, immediate_count=2)
        self.controller.changed.emit()
        QTest.qWait(25)
        button = self.visual('pauseQueueButton')
        self.assertEqual(button.property('text'), 'Auswahl pausieren')
        point = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
        with patch.object(self.controller_module, 'command', return_value='') as command, patch.object(self.controller, 'action', side_effect=lambda operation, message: operation()):
            QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
            QTest.qWait(20)
        command.assert_called_once_with('queue-pause', 'on')
