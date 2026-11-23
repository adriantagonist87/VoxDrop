import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, QUrl, QPoint, QPointF, QMetaObject
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

    @unittest.skipUnless(sys.platform == 'darwin', 'Cocoa full-screen Space transition')
    def test_cocoa_fullscreen_minimization_after_maximizing_keeps_the_fullscreen_mode(self):
        if self.app.platformName() != 'cocoa':
            self.skipTest('Requires native Cocoa window transitions')
        self.presenter.show()
        self.window.showMaximized(); QTest.qWait(350)
        self.window.showFullScreen(); QTest.qWait(1200)
        self.window.showMinimized(); QTest.qWait(1200)
        self.presenter.show(); QTest.qWait(1600)
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowFullScreen)
        self.assertEqual(self.presenter.last_state, Qt.WindowState.WindowFullScreen)
        # Leaving a native full-screen Space restores the preceding zoomed
        # window first. A second normal request then leaves that zoomed mode.
        self.window.showNormal(); QTest.qWait(1200)
        self.window.showNormal(); QTest.qWait(350)
        self.window.hide(); self.presenter.show(); QTest.qWait(300)
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowNoState)

    def test_network_wait_offers_cancel_and_folder_modes_are_symmetric(self):
        self.presenter.show()
        self.controller.downloading = True
        self.controller.network_permission_changed(True)
        self.controller.setSetting("include_subfolders", True)
        QTest.qWait(50)
        cancel = self.window.findChild(QObject, "cancelNetworkWait")
        self.assertTrue(cancel.property("visible"))
        self.assertTrue(cancel.property("enabled"))
        self.assertTrue(self.window.findChild(QObject, "createOutputSubfolder").property("enabled"))
        self.controller.setSetting('create_output_subfolder', True)
        self.assertFalse(self.controller.draft['include_subfolders'])
        self.assertTrue(self.controller.draft['create_output_subfolder'])
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

    def test_gpu_slider_keyboard_saves_live_budget_without_saving_other_draft_edits(self):
        self.queue_fixture()
        self.controller.draft['hardware'] = self.controller_module.GPU
        self.controller.draft['language'] = 'en'
        self.controller.changed.emit()
        slider = self.visual('gpuBudgetSlider')
        with patch.object(self.controller_module, 'read_settings', return_value={**self.controller_module.DEFAULTS, 'language': 'de'}) , \
             patch.object(self.controller_module, 'save_settings') as save, \
             patch.object(self.controller, 'action', side_effect=lambda operation, message: operation()):
            self.controller.changed.emit()
            QTest.qWait(30)
            slider.forceActiveFocus()
            for _ in range(10):
                QTest.keyClick(self.window, Qt.Key.Key_Left)
            self.controller.notify('Status wurde während des Ziehens aktualisiert.')
            QTest.qWait(350)
        self.assertEqual(save.call_args.args[0]['gpu_budget_percent'], 50)
        self.assertEqual(save.call_args.args[0]['language'], 'de')
        self.assertEqual(self.controller.draft['language'], 'en')
        self.assertEqual(self.controller.draft['gpu_budget_percent'], 50)

    def test_gpu_slider_waits_for_busy_action_without_losing_pending_value(self):
        self.queue_fixture()
        self.controller.draft['hardware'] = self.controller_module.GPU
        self.controller.changed.emit()
        with patch.object(self.controller_module, 'save_settings') as save, \
             patch.object(self.controller_module, 'read_settings', return_value=self.controller_module.DEFAULTS.copy()), \
             patch.object(self.controller, 'action', side_effect=lambda operation, message: operation()):
            self.controller.changed.emit()
            slider = self.visual('gpuBudgetSlider')
            slider.forceActiveFocus()
            QTest.keyClick(self.window, Qt.Key.Key_Left)
            self.controller.busy = True
            self.controller.changed.emit()
            QTest.qWait(350)
            save.assert_not_called()
            self.controller.busy = False
            self.controller.changed.emit()
            QTest.qWait(350)
            self.assertEqual(save.call_args.args[0]['gpu_budget_percent'], 95)

    def test_gpu_slider_is_disabled_for_cpu(self):
        self.queue_fixture()
        self.controller.setSetting('hardware', 'cpu')
        QTest.qWait(30)
        self.assertFalse(self.visual('gpuBudgetSlider').property('enabled'))

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
        command.assert_called_once_with('move-queue',1,2,'--after')
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
        # Geometry is polished on a later Qt frame under load.
        for _ in range(50):
            if row.height() == compact_height:
                break
            QTest.qWait(20)
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

    def test_failed_details_keep_all_six_file_actions_visible(self):
        from desktop.detail_files import locate_files
        job = self.queue_fixture(1)[0]
        job.update(state='failed', error='Die Stille-Erkennung hat keine Sprache gefunden.')
        source = Path(job['source'])
        source.write_bytes(b'synthetic original')
        actions = ('revealOriginalButton', 'playOriginalButton', 'revealTranscriptButton',
                   'openTranscriptButton', 'retranscribeButton', 'closeJobDialog')
        callbacks = []
        with patch.object(self.controller, 'submit', side_effect=lambda operation, callback: callbacks.append((operation, callback))):
            self.controller.showDetails(job['id'])
        callbacks.pop()[1](locate_files(job), None)
        QTest.qWait(80)
        for name in actions:
            self.assertTrue(self.visual(name).property('visible'), name)
        self.assertTrue(self.visual('playOriginalButton').property('enabled'))
        self.assertTrue(self.visual('revealOriginalButton').property('enabled'))
        self.assertFalse(self.visual('openTranscriptButton').property('enabled'))
        self.assertFalse(self.visual('revealTranscriptButton').property('enabled'))
        self.assertIsNone(self.controller.audio_preview._player)
        self.assertFalse(self.window.findChild(QObject,'audioPreviewPopup').property('visible'))
        source.with_suffix('.txt').write_text('protected existing result')
        with patch.object(self.controller, 'submit', side_effect=lambda operation, callback: callbacks.append((operation, callback))):
            self.controller.showDetails(job['id'])
        callbacks.pop()[1](locate_files(job), None)
        QTest.qWait(40)
        self.assertTrue(self.visual('openTranscriptButton').property('enabled'))
        self.assertTrue(self.visual('revealTranscriptButton').property('enabled'))

    def test_original_playback_and_reveal_do_not_start_transcription(self):
        from desktop.detail_files import locate_files
        job = self.queue_fixture(1)[0]
        job['state'] = 'failed'
        Path(job['source']).write_bytes(b'media')
        self.controller.selected = job
        def immediate(operation, callback):
            try:
                result = operation()
            except Exception as error:
                callback(None, str(error))
            else:
                callback(result, None)
        with patch.object(self.controller_module, 'probe_detail_files', return_value=locate_files(job)), \
             patch.object(self.controller, 'submit', side_effect=immediate), \
             patch.object(self.controller_module, 'command') as command, \
             patch.object(self.controller.audio_preview, 'play_file') as played, \
             patch.object(self.controller_module, 'reveal_in_explorer') as reveal, \
             patch.object(self.controller_module.sys, 'platform', 'win32'):
            self.controller.playOriginal()
            played.assert_called_once_with(job['source'])
            self.controller.revealOriginal()
            reveal.assert_called_once_with(Path(job['source']))
            command.assert_not_called()

    def test_late_file_probe_cannot_reopen_a_closed_detail_player(self):
        job = self.queue_fixture(1)[0]
        callbacks = []
        with patch.object(self.controller, 'submit', side_effect=lambda operation, callback: callbacks.append(callback)):
            self.controller.showDetails(job['id'])
            self.controller.playOriginal()
        self.controller.closeDetails()
        with patch.object(self.controller.audio_preview, 'play_file') as played:
            for callback in callbacks:
                callback(dict(original=job['source'], originalAvailable=True), None)
            played.assert_not_called()
        self.assertEqual(self.controller.detail_files, {})

    def test_player_popup_outside_close_keeps_details_and_ignores_late_play_reply(self):
        job=self.queue_fixture(1)[0]
        files=dict(original=job['source'],originalAvailable=True,transcriptAvailable=False)
        callbacks=[]
        with patch.object(self.controller,'submit',side_effect=lambda operation,callback:callbacks.append(callback)):
            self.controller.showDetails(job['id'])
            callbacks.pop()(files,None)
            self.controller.playOriginal()
        popup=self.window.findChild(QObject,'audioPreviewPopup')
        QTest.qWait(30);self.assertTrue(popup.property('visible'))
        QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(4,4))
        QTest.qWait(40)
        self.assertFalse(popup.property('visible'))
        self.assertTrue(self.window.findChild(QObject,'jobDialog').property('visible'))
        with patch.object(self.controller.audio_preview,'play_file') as played:
            callbacks.pop()(files,None)
            played.assert_not_called()
            with patch.object(self.controller,'submit',side_effect=lambda operation,callback:callback(files,None)):
                self.controller.playOriginal()
            self.assertTrue(popup.property('visible'))
            played.assert_called_once_with(job['source'])
        self.controller.closeDetails()
        self.assertFalse(popup.property('visible'))

    def test_player_popup_escape_closes_without_closing_details(self):
        job=self.queue_fixture(1)[0]
        with patch.object(self.controller,'submit'):
            self.controller.showDetails(job['id'])
            self.controller.playOriginal()
        popup=self.window.findChild(QObject,'audioPreviewPopup')
        QTest.qWait(30)
        QTest.keyClick(self.window,Qt.Key.Key_Escape);QTest.qWait(30)
        self.assertFalse(popup.property('visible'))
        self.assertTrue(self.window.findChild(QObject,'jobDialog').property('visible'))
        self.assertFalse(self.controller.audio_requested)

    def test_player_sliders_also_apply_accessibility_value_changes(self):
        self.queue_fixture(1)
        with patch.object(self.controller, 'submit'):
            self.controller.showDetails(1)
        preview = self.controller.audio_preview
        backend = Mock()
        backend.duration.return_value = 12_000
        backend.position.return_value = 7000
        backend.isPlaying.return_value = False
        backend.isSeekable.return_value = True
        preview._player = backend
        preview._path = 'synthetic.wav'
        self.controller.audioPreviewOpened.emit()
        preview.changed.emit()
        QTest.qWait(30)
        self.visual('previewSeekSlider').setProperty('value', 3500)
        QTest.qWait(30)
        backend.setPosition.assert_called_with(3500)
        self.visual('previewVolumeSlider').setProperty('value', 30)
        QTest.qWait(30)
        self.assertEqual(preview.state['volume'], 30)
        self.controller.closeDetails()
        self.assertFalse(preview.state['available'])

    def test_player_scrubbing_previews_position_and_seeks_only_on_release(self):
        self.queue_fixture(1)
        with patch.object(self.controller,'submit'):
            self.controller.showDetails(1)
        preview=self.controller.audio_preview
        backend=Mock(duration=Mock(return_value=12_000),position=Mock(return_value=7000),
            isPlaying=Mock(return_value=False),isSeekable=Mock(return_value=True))
        preview._player=backend;preview._path='synthetic.wav'
        self.controller.audioPreviewOpened.emit();preview.changed.emit();QTest.qWait(40)
        slider=self.visual('previewSeekSlider')
        start=slider.mapToScene(QPointF(slider.width()*.3,slider.height()/2)).toPoint()
        end=slider.mapToScene(QPointF(slider.width()*.7,slider.height()/2)).toPoint()
        backend.setPosition.reset_mock()
        QTest.mousePress(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
        QTest.mouseMove(self.window,end,40)
        before=slider.property('value')
        self.assertTrue(slider.property('scrubbing'))
        backend.position.return_value=8000;preview.changed.emit();QTest.qWait(30)
        self.assertAlmostEqual(slider.property('value'),before)
        backend.setPosition.assert_not_called()
        QTest.mouseRelease(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
        QTest.qWait(30)
        backend.setPosition.assert_called_once()
        self.assertAlmostEqual(backend.setPosition.call_args.args[0],before,delta=10)
        self.assertFalse(slider.property('scrubbing'))

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
        with patch.object(self.controller_module.sys, 'platform', 'win32'), \
             patch.object(self.controller_module, 'windows_login_item', return_value=False), \
             patch.object(self.controller, 'submit', side_effect=immediately):
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
        self.assertTrue(self.visual('queueDragHandle2').property('enabled'))
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
        jobs=self.queue_fixture(3)
        self.controller.snapshot.update(queue_paused=True, immediate_count=2,
            current={**jobs[0],'state':'transcribing','started':100})
        self.controller.changed.emit()
        QTest.qWait(25)
        button = self.visual('pauseQueueButton')
        self.assertEqual(button.property('text'), 'Nach diesem Auftrag pausieren')
        point = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
        with patch.object(self.controller_module, 'command', return_value='') as command, patch.object(self.controller, 'action', side_effect=lambda operation, message: operation()):
            QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
            QTest.qWait(20)
        command.assert_called_once_with('queue-pause', 'on')

    def test_explicit_start_is_visible_and_resumes_processing_without_saving_monitor_settings(self):
        self.queue_fixture(3)
        self.controller.ready=True
        self.controller.snapshot.update(queue_paused=True,running=True)
        self.controller.changed.emit();QTest.qWait(30)
        button=self.visual('queuePlaybackButton')
        self.assertTrue(button.property('visible'));self.assertTrue(button.property('enabled'))
        self.assertEqual(button.property('text'),'STARTEN')
        self.assertEqual((button.width(),button.height()),(44,44))
        self.assertFalse(self.visual('pauseQueueButton').property('enabled'))
        self.assertIn('Gestoppt',self.visual('processingStatus').property('text'))
        point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
        with patch.object(self.controller_module,'command',return_value='') as command,patch.object(self.controller,'action',side_effect=lambda operation,message:operation()):
            QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
        self.assertEqual([call.args[0] for call in command.call_args_list],['start','start-queue'])

    def test_running_job_has_large_red_stop_and_secondary_finish_then_pause(self):
        jobs=self.queue_fixture(2)
        self.controller.ready=True
        current={**jobs[0], 'state':'transcribing','started':100,'phase':'Qwen-Modell laden','progress':None}
        self.controller.snapshot.update(current=current,running=True,queue_paused=False)
        self.controller.changed.emit();QTest.qWait(30)
        self.assertIn('Verarbeitung läuft',self.visual('processingStatus').property('text'))
        button=self.visual('queuePlaybackButton')
        self.assertTrue(button.property('enabled'))
        self.assertEqual(button.property('text'),'STOPP')
        self.assertEqual(button.property('background').property('color').name(),'#b5303a')
        self.assertTrue(self.visual('pauseQueueButton').property('enabled'))

    def test_playback_control_keeps_normal_square_size_in_fullscreen(self):
        self.queue_fixture(2)
        button=self.visual('queuePlaybackButton')
        for mode in ('normal','maximized','fullscreen'):
            if mode=='normal':self.window.showNormal();self.window.resize(1010,630)
            elif mode=='maximized':self.window.showMaximized()
            else:self.window.showFullScreen()
            QTest.qWait(60)
            self.assertEqual((button.width(),button.height()),(44,44),mode)

    def test_real_stop_click_waits_for_worker_then_switches_to_green_play(self):
        jobs=self.queue_fixture(2);self.controller.ready=True
        current={**jobs[0],'state':'transcribing','started':100,'cancel_requested':False}
        status=dict(current=current,queue=[jobs[1]],jobs=[],running=True,queue_paused=False)
        self.controller.snapshot=status.copy();self.controller.changed.emit();QTest.qWait(30)
        def command(*args):
            if args[0]=='stop-queue':
                status.update(queue_paused=True,current={**current,'cancel_requested':True})
                return json.dumps(dict(current_id=current['id'],export_finishes=False))
            if args[0]=='status':return json.dumps(status)
            if args[0] in ('start','start-queue'):return '{}'
            raise AssertionError(args)
        self.controller.preview=False
        with patch.object(self.controller_module,'command',side_effect=command) as sent, \
             patch.object(self.controller,'submit',side_effect=lambda operation,finished:finished(operation(),None)), \
             patch.object(self.controller_module,'save_settings') as save:
            button=self.visual('queuePlaybackButton')
            point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
            QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
            QTest.qWait(30)
            self.assertTrue(self.controller.state['processingStopping'])
            self.assertFalse(button.property('enabled'))
            self.controller.startProcessing()
            self.assertNotIn('start-queue',[call.args[0] for call in sent.call_args_list])
            status.update(current=None,queue=jobs)
            self.controller.refresh();QTest.qWait(30)
            self.assertEqual(button.property('text'),'STARTEN')
            self.assertEqual(button.property('background').property('color').name(),'#8ac6a5')
            self.assertTrue(button.property('enabled'))
            point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
            QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
            self.assertIn('start-queue',[call.args[0] for call in sent.call_args_list])
            save.assert_not_called()
        self.controller.preview=True

    def test_filtered_queue_menu_enables_moves_against_global_positions(self):
        self.queue_fixture(4)
        self.controller.setQueueSearch('* 3 mit*')
        QTest.qWait(30)
        self.assertEqual([job['id'] for job in self.controller.queue],[3])
        actions=self.visual('queueActions3')
        point=actions.mapToScene(QPointF(actions.width()/2,actions.height()/2)).toPoint()
        QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
        QTest.qWait(40)
        row=self.visual('queueRow3')
        menu=row.findChild(QObject,'queueMoveMenu3')
        self.assertTrue(menu.property('visible'))
        for action in ('First','Up','Down','Last'):
            self.assertTrue(menu.findChild(QObject,'queueMove'+action+'3').property('enabled'))
        up=menu.findChild(QObject,'queueMoveUp3')
        point=up.mapToScene(QPointF(up.width()/2,up.height()/2)).toPoint()
        with patch.object(self.controller_module,'command',return_value='') as command, patch.object(self.controller,'action',side_effect=lambda operation,message:operation()):
            QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
            QTest.qWait(30)
        command.assert_called_once_with('move-queue-relative',3,'up')

    def test_real_filtered_drag_targets_actual_neighbor_instead_of_filtered_end(self):
        jobs=self.queue_fixture(4)
        for index in (0,2):
            jobs[index]['source']=str(self.controller_module.PROFILE/f'Treffer {jobs[index]["id"]}.wav')
        self.controller.update_queue()
        self.controller.setQueueSearch('Treffer')
        QTest.qWait(40)
        self.assertEqual([job['id'] for job in self.controller.queue],[1,3])
        handle=self.visual('queueDragHandle1');target=self.visual('queueRow3')
        start=handle.mapToScene(QPointF(14,15)).toPoint()
        end=target.mapToScene(QPointF(20,target.height()-8)).toPoint()
        with patch.object(self.controller_module,'command',return_value='') as command, patch.object(self.controller,'action',side_effect=lambda operation,message:operation()):
            QTest.mousePress(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
            for step in range(1,13):
                point=QPoint(start.x(),round(start.y()+(end.y()-start.y())*step/12))
                QTest.mouseMove(self.window,point,30)
            QTest.mouseRelease(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
            QTest.qWait(40)
        command.assert_called_once_with('move-queue',1,3,'--after')

    def test_history_separates_unstarted_cancel_started_cancel_and_transcript_inventory(self):
        jobs=self.queue_fixture(3)
        jobs[0].update(state='cancelled',attempt=0)
        jobs[1].update(state='cancelled',attempt=1,started=100)
        jobs[2].update(state='existing',result_kind='existing')
        self.controller.snapshot.update(jobs=jobs,queue=[],stored_jobs=3,has_stored_data=True)
        self.controller.update_history();self.controller.update_queue();self.controller.changed.emit();QTest.qWait(40)
        self.assertEqual([job['id'] for job in self.controller.history],[2])
        self.assertEqual(self.controller.history_counts(),dict(all=1,errors=0,done=0,cancelled=1,existing=1))
        button=self.visual('historyFilter_existing')
        point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
        QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point);QTest.qWait(30)
        self.assertEqual([job['id'] for job in self.controller.history],[3])
        self.assertEqual(button.property('text'),'Bestand (1)')

    def test_clear_is_available_for_hidden_records_and_search_and_requires_dialog_acceptance(self):
        self.controller.snapshot.update(jobs=[],queue=[],stored_jobs=8000,has_stored_data=True)
        self.controller.setHistorySearch('Kein Treffer')
        self.presenter.show();self.controller.changed.emit();QTest.qWait(50)
        self.window.setProperty('settingsOpen', True)
        self.window.setProperty('settingsTab', 2)
        QTest.qWait(50)
        button=self.visual('clearHistoryButton')
        self.assertTrue(button.property('enabled'))
        point=button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint()
        with patch.object(self.controller_module,'command',return_value='') as command,patch.object(self.controller,'submit',side_effect=lambda operation,finished:finished(operation(),None)):
            QTest.mouseClick(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point);QTest.qWait(30)
            dialog=self.window.findChild(QObject,'confirmClear')
            self.assertTrue(dialog.property('visible'));command.assert_not_called()
            QMetaObject.invokeMethod(dialog,'accept');QTest.qWait(30)
            command.assert_called_once_with('clear-history')
        self.assertFalse(self.controller.history_query)
        self.assertFalse(self.controller.state['canClear'])
        self.assertFalse(self.controller.history)

    def test_metadata_reply_from_before_clear_cannot_restore_old_history(self):
        jobs=self.queue_fixture(1);jobs[0]['state']='done'
        callbacks=[]
        def capture(operation,finished):callbacks.append(finished)
        with patch.object(self.controller,'submit',side_effect=capture):
            self.controller.preview=False;self.controller.ready=True;self.controller.refresh()
            self.controller.preview=True
            self.controller.clearHistory()
            self.assertEqual(len(callbacks),2)
            callbacks[1](None,None)
            callbacks[0](dict(jobs=jobs,queue=[],history_counts=dict(all=1,done=1,errors=0)),None)
        self.assertFalse(self.controller.history)
        self.assertFalse(self.controller.queue)

    def delete_fixture(self):
        jobs=self.queue_fixture(3)
        for job in jobs:job.update(state='done',attempt=1,finished=101)
        self.controller.snapshot.update(jobs=jobs,queue=[],queue_paused=True)
        self.controller.update_history();self.controller.update_queue()
        self.controller.showDetails(1);QTest.qWait(30)
        return dict(token='a'*32,name=Path(jobs[0]['source']).name,recordCount=2,
            files=[dict(path=jobs[0]['source'],role='original')])

    def test_record_delete_popup_is_explicit_red_green_and_cancel_preserves_history(self):
        plan=self.delete_fixture()
        def command(*args):return json.dumps(plan) if args[0]=='prepare-delete-record' else '{}'
        with patch.object(self.controller_module,'command',side_effect=command) as sent, \
             patch.object(self.controller,'submit',side_effect=lambda operation,finished:finished(operation(),None)):
            button=self.visual('deleteRecordButton')
            self.assertTrue(button.property('visible'));self.assertTrue(button.property('enabled'))
            self.assertEqual(button.property('background').property('color').name(),'#b5303a')
            QMetaObject.invokeMethod(button,'clicked');QTest.qWait(30)
            popup=self.window.findChild(QObject,'deleteRecordDialog')
            self.assertTrue(popup.property('visible'))
            confirm=popup.findChild(QObject,'confirmDeleteRecordButton');cancel=popup.findChild(QObject,'cancelDeleteRecordButton')
            self.assertTrue(confirm.property('enabled'))
            self.assertEqual(confirm.property('background').property('color').name(),'#b5303a')
            self.assertEqual(cancel.property('background').property('color').name(),'#8ac6a5')
            self.assertEqual([call.args[0] for call in sent.call_args_list],['prepare-delete-record'])
            QMetaObject.invokeMethod(cancel,'clicked');QTest.qWait(30)
            self.assertFalse(popup.property('visible'))
            self.assertEqual([call.args[0] for call in sent.call_args_list],['prepare-delete-record','discard-delete-record'])
        self.assertEqual(len(self.controller.history),3)
        self.assertTrue(self.controller.snapshot['queue_paused'])
        self.assertEqual(self.controller.selected['id'],1)

    def test_record_delete_cancelled_probe_cannot_restore_confirmation(self):
        plan=self.delete_fixture();pending=[]
        with patch.object(self.controller,'submit',side_effect=lambda operation,finished:pending.append((operation,finished))):
            self.controller.requestRecordDeletion();self.controller.cancelRecordDeletion()
            pending[0][1](plan,None)
            self.assertFalse(self.controller.delete_plan)
            self.assertFalse(self.controller.busy)
            self.assertFalse(self.window.findChild(QObject,'deleteRecordDialog').property('visible'))
            self.assertEqual(len(pending),2)

    def test_record_delete_failure_keeps_details_then_success_removes_only_selected_ids(self):
        plan=self.delete_fixture()
        self.controller.delete_plan=plan;self.controller.recordDeletionOpened.emit()
        pending=[]
        with patch.object(self.controller,'submit',side_effect=lambda operation,finished:pending.append((operation,finished))):
            self.controller.confirmRecordDeletion()
            self.assertTrue(self.controller.deleting_record)
            self.controller.cancelRecordDeletion();self.assertTrue(self.controller.delete_plan)
            pending[0][1](None,'Die Datei ist gesperrt.')
            self.assertEqual(self.controller.selected['id'],1)
            self.assertEqual(len(self.controller.history),3)
            self.assertTrue(self.controller.delete_plan)
            self.assertIn('gesperrt',self.controller.delete_error)
            self.controller.confirmRecordDeletion()
            pending[1][1](dict(deletedIds=[1,2],trashed=3),None)
        self.assertEqual([job['id'] for job in self.controller.history],[3])
        self.assertIsNone(self.controller.selected)
        self.assertTrue(self.controller.snapshot['queue_paused'])
        self.assertFalse(self.controller.busy or self.controller.deleting_record)
        self.assertFalse(self.window.findChild(QObject,'deleteRecordDialog').property('visible'))

    def test_window_x_hides_to_tray_without_stopping_app_or_work(self):
        self.presenter.show();QTest.qWait(30)
        with patch.object(self.controller,'hasTray',return_value=True),patch.object(self.controller,'requestQuit') as quit_app:
            self.assertFalse(self.window.close());QTest.qWait(30)
            self.assertFalse(self.window.isVisible());quit_app.assert_not_called()
        self.assertFalse(self.controller.quitting)
        self.assertFalse(self.controller.content_cancel.is_set())
        self.assertFalse(self.controller.network_cancel.is_set())
        self.presenter.show();QTest.qWait(30)
        self.assertTrue(self.window.isVisible())

    def test_minimize_keeps_taskbar_window_and_x_without_tray_stays_reachable(self):
        self.presenter.show();QTest.qWait(30)
        self.window.showMinimized();QTest.qWait(30)
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.window.windowState(),Qt.WindowState.WindowMinimized)
        self.presenter.show();QTest.qWait(30)
        with patch.object(self.controller,'hasTray',return_value=False),patch.object(self.controller,'requestQuit') as quit_app:
            self.window.close();QTest.qWait(30)
            self.assertTrue(self.window.isVisible())
            self.assertEqual(self.window.windowState(),Qt.WindowState.WindowMinimized)
            quit_app.assert_not_called()

    def test_completed_full_shutdown_allows_window_to_close(self):
        self.presenter.show();QTest.qWait(30)
        self.controller.shutdown_complete=True;self.controller.changed.emit()
        with patch.object(self.controller,'hasTray',return_value=True):
            self.assertTrue(self.window.close());QTest.qWait(30)
        self.assertFalse(self.window.isVisible())

    def test_tray_quit_action_calls_full_app_shutdown(self):
        with patch.object(self.controller_module.QSystemTrayIcon,'isSystemTrayAvailable',return_value=True),patch.object(self.controller,'requestQuit') as quit_app:
            self.controller.preview=False
            self.controller.init_tray()
            self.controller.preview=True
            action=self.controller.menu.actions()[-1]
            self.assertEqual(action.text(),'VoxDrop beenden')
            action.trigger();quit_app.assert_called_once()
        self.controller.tray.hide()
