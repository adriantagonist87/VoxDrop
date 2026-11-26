"""Exercise the shared workspace with real QML events and isolated configuration."""
import json
import unittest
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from PySide6.QtCore import QObject, QPointF, QMetaObject, Qt
from PySide6.QtTest import QTest
import test_desktop_window as harness


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        harness.DesktopWindowTests.setUpClass.__func__(cls)

    dispose_window = harness.DesktopWindowTests.dispose_window
    visual = harness.DesktopWindowTests.visual
    queue_fixture = harness.DesktopWindowTests.queue_fixture

    def setUp(self):
        harness.DesktopWindowTests.setUp(self)
        self.config_file = self.controller_module.PROFILE / 'config.json'
        self.enterContext(patch.object(self.controller_module, 'CONFIG', self.config_file))
        self.enterContext(patch.object(self.controller_module, 'DESKTOP_LOG', self.controller_module.PROFILE / 'service/desktop.log'))

    def click(self, name):
        item = self.visual(name) or self.window.findChild(QObject, name)
        self.assertIsNotNone(item, name)
        self.assertTrue(item.property('visible'), name)
        self.assertTrue(item.property('enabled'), name)
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
        QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        QTest.qWait(45)
        return item

    def seed_config(self):
        settings = {**self.controller_module.DEFAULTS, 'language': 'de', 'gpu_budget_percent': 75}
        self.config_file.write_text(json.dumps(settings), encoding='utf-8')
        self.controller.saved_config = dict(settings)
        self.controller.draft = dict(settings)
        self.controller.paths = []
        self.controller.changed.emit()
        return settings

    def test_import_export_page_has_independent_checkboxes_and_confirmation(self):
        self.queue_fixture(); self.seed_config()
        self.window.resize(1010, 630)
        QTest.qWait(80)
        self.click('settingsButton'); self.click('transferSettingsTab')
        self.assertEqual(self.window.property('settingsTab'), 3)
        self.assertFalse(self.controller.export_options['models'])
        self.click('exportOption_models')
        self.assertTrue(self.controller.export_options['models'])
        from PySide6.QtGui import QAccessible, QAccessibleActionInterface
        accessible=QAccessible.queryAccessibleInterface(self.visual('exportOption_models'))
        self.assertIsNotNone(accessible)
        accessible.actionInterface().doAction(QAccessibleActionInterface.toggleAction())
        QTest.qWait(30)
        self.assertFalse(self.controller.export_options['models'])
        self.assertFalse(self.controller.export_options['media'])
        self.controller.import_preview = dict(fileCount=3, jobs=4, bytes=1024,
            created='2026-11-21', platform=self.controller_module.sys.platform,
            available=dict(settings=True, databases=True, media=False, models=False))
        self.controller.changed.emit(); QTest.qWait(50)
        scroll=self.window.findChild(QObject, 'settingsScroll').property('contentItem')
        scroll.setProperty('contentY', max(0, scroll.property('contentHeight')-scroll.property('height')))
        QTest.qWait(60)
        self.click('importBackupButton')
        dialog=self.window.findChild(QObject,'confirmImport')
        self.assertTrue(dialog.property('visible'))
        self.assertLessEqual(dialog.property('height'),self.window.height()-35)
        QMetaObject.invokeMethod(dialog,'close')

    def test_model_tab_confirms_deletion_and_keeps_other_settings(self):
        from model_inventory import WHISPER, catalog

        self.queue_fixture()
        self.seed_config()
        self.window.resize(1010, 630)
        root = self.controller_module.MODEL_DATA / 'models' / WHISPER
        for name in catalog()[WHISPER][1]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic model')
        self.controller.setSetting('language', 'en')

        def wait_for_inventory():
            deadline = monotonic() + 8
            while (self.controller.model_inventory_loading or self.controller.busy) and monotonic() < deadline:
                QTest.qWait(20)
            self.assertFalse(self.controller.model_inventory_loading or self.controller.busy)
            self.assertFalse(self.controller.model_inventory_error, self.controller.model_inventory_error)

        self.click('settingsButton')
        self.click('modelSettingsTab')
        wait_for_inventory()
        self.assertLess(self.visual('modelSettingsTab').x(), self.visual('transferSettingsTab').x())
        self.click('deleteModel-' + WHISPER)
        self.click('cancelModelDelete')
        self.assertTrue(root.is_dir())
        self.click('deleteModel-' + WHISPER)
        self.click('acceptModelDelete')
        wait_for_inventory()
        self.assertFalse(root.exists())
        self.assertFalse(self.controller.message_error, self.controller.message)
        self.assertEqual(self.controller.draft['language'], 'en')
        self.assertTrue(self.controller.state['settingsDirty'])

    def test_folder_checkboxes_allow_switching_directly_in_both_directions(self):
        self.queue_fixture();self.seed_config()
        self.click('settingsButton');self.click('folderSettingsTab')
        for name, selected, other in (
            ('createOutputSubfolder','create_output_subfolder','include_subfolders'),
            ('includeSubfolders','include_subfolders','create_output_subfolder'),
            ('createOutputSubfolder','create_output_subfolder','include_subfolders')):
            self.click(name)
            self.assertTrue(self.controller.draft[selected])
            self.assertFalse(self.controller.draft[other])
        self.assertEqual(self.visual('createOutputSubfolder').property('text'),'Unterordner für fertige Transkripte erstellen')
        self.click('createOutputSubfolder')
        self.assertFalse(self.controller.draft['create_output_subfolder'])
        self.assertFalse(self.controller.draft['include_subfolders'])
        from PySide6.QtGui import QAccessible, QAccessibleActionInterface
        for name, selected, other in (('includeSubfolders','include_subfolders','create_output_subfolder'),
                                      ('createOutputSubfolder','create_output_subfolder','include_subfolders')):
            interface=QAccessible.queryAccessibleInterface(self.visual(name))
            interface.actionInterface().doAction(QAccessibleActionInterface.toggleAction())
            QTest.qWait(30)
            self.assertTrue(self.controller.draft[selected]);self.assertFalse(self.controller.draft[other])

    def test_gui_export_preview_and_reimport_real_isolated_database(self):
        import watch_service as backend
        profile=self.controller_module.PROFILE/'profile';profile.mkdir()
        self.enterContext(patch.object(self.controller_module,'PROFILE',profile))
        self.config_file=profile/'config.json'
        self.enterContext(patch.object(self.controller_module,'CONFIG',self.config_file))
        self.seed_config()
        backend.initialise(profile/'service')
        archive=profile/'Roundtrip.voxdrop.zip'
        def wait():
            deadline=monotonic()+30
            while self.controller.busy and monotonic()<deadline:QTest.qWait(20)
            self.assertFalse(self.controller.busy, self.controller.transfer_status)
            self.assertFalse(self.controller.message_error,self.controller.message)
        with patch.object(self.controller_module.QFileDialog,'getSaveFileName',return_value=(str(archive),'')):
            self.controller.exportBackup(); wait()
        self.assertTrue(archive.is_file())
        settings=self.seed_config();settings['language']='en'
        self.config_file.write_text(json.dumps(settings),encoding='utf-8')
        self.controller.draft=dict(settings);self.controller.saved_config=dict(settings)
        with patch.object(self.controller_module.QFileDialog,'getOpenFileName',return_value=(str(archive),'')):
            self.controller.chooseImportBackup(); wait()
        self.assertTrue(self.controller.import_preview['available']['databases'])
        self.controller.importBackup(); wait()
        self.assertEqual(self.controller.draft['language'],'de')
        self.assertFalse(self.controller.draft['monitoring'])
        self.assertIn('Import abgeschlossen',self.controller.transfer_status)
        # Keep the test's automatically created rollback outside the native profile.
        self.assertIn(str(profile.parent.resolve()),self.controller.transfer_status)

    def test_minimum_window_keeps_five_whole_queue_rows_and_switches_to_wide_history(self):
        self.queue_fixture(60)
        self.window.resize(1010, 630)
        QTest.qWait(100)
        self.assertTrue(self.window.property('focusView'))
        view = self.visual('queueList')
        row = self.visual('queueRow5')
        self.assertIsNotNone(row)
        bottom = row.mapToScene(QPointF(0, row.height())).y()
        self.assertLessEqual(bottom, view.mapToScene(QPointF(0, view.height())).y())
        self.click('historyTab')
        self.assertTrue(self.visual('historyList').property('visible'))
        self.assertFalse(view.property('visible'))
        for name in ('queuePlaybackButton', 'settingsButton', 'gpuBudgetSlider'):
            self.assertTrue(self.visual(name).property('visible'), name)
        self.click('queueTab')
        self.assertTrue(view.property('visible'))
        self.window.resize(1500, 900)
        QTest.qWait(60)
        self.assertFalse(self.window.property('focusView'))
        self.assertTrue(self.visual('historyList').property('visible'))
        self.assertTrue(view.property('visible'))

    def test_settings_groups_keep_dirty_edits_until_explicit_discard(self):
        self.queue_fixture()
        self.seed_config()
        self.controller.setSetting('language', 'en')
        self.assertTrue(self.controller.state['settingsDirty'])
        self.click('settingsButton')
        self.click('folderSettingsTab')
        self.assertEqual(self.window.property('settingsTab'), 1)
        self.click('appSettingsTab')
        self.assertEqual(self.controller.draft['language'], 'en')
        self.assertTrue(self.controller.state['settingsDirty'])
        self.click('discardSettingsButton')
        self.assertEqual(self.controller.draft['language'], 'de')
        self.assertEqual(self.controller.draft['gpu_budget_percent'], 75)
        self.assertFalse(self.controller.state['settingsDirty'])

    def test_pause_button_and_rescan_menu_use_saved_folders_without_saving_draft(self):
        self.queue_fixture()
        settings = self.seed_config()
        folder = str(self.config_file.parent / 'Watch')
        settings.update(folders=[folder], monitoring=True)
        self.config_file.write_text(json.dumps(settings), encoding='utf-8')
        self.controller.saved_config = dict(settings)
        self.controller.discardSettings()
        self.controller.setFolderOutput(folder, 'subfolder')
        self.controller.setSetting('language', 'en')
        self.controller.preview = False
        self.click('settingsButton')
        self.click('folderSettingsTab')
        with patch.object(self.controller_module, 'command', return_value='') as command, \
             patch.object(self.controller, 'refresh'), \
             patch.object(self.controller, 'submit', side_effect=lambda operation, finished: finished(operation(), None)):
            self.click('folderPause0')
            saved = json.loads(self.config_file.read_text())
            self.assertEqual(saved['folder_options'][folder], {'paused': True, 'output': 'global'})
            self.assertEqual(saved['language'], 'de')
            self.assertEqual(self.controller.draft['folder_options'][folder]['output'], 'subfolder')
            self.assertFalse(self.controller.state['canRescanFolders'])
            self.click('folderPause0')
            self.click('queueTab')
            self.click('queueActionsButton')
            self.click('rescanFoldersButton')
            self.assertEqual(command.call_args.args, ('rescan-folders', self.config_file))

    def test_save_button_persists_edits_and_does_not_reconfigure_existing_jobs(self):
        jobs = self.queue_fixture()
        self.seed_config()
        before = [job['settings'] for job in jobs]
        self.controller.setSetting('language', 'en')
        self.click('settingsButton')
        self.controller.preview = False
        with patch.object(self.controller_module, 'command', return_value='') as command, \
             patch.object(self.controller, 'refresh'), \
             patch.object(self.controller, 'submit', side_effect=lambda operation, finished: finished(operation(), None)):
            self.click('saveButton')
        self.assertEqual(json.loads(self.config_file.read_text())['language'], 'en')
        self.assertEqual(command.call_args.args[0], 'validate-settings')
        self.assertFalse(self.controller.state['settingsDirty'])
        self.assertEqual([job['settings'] for job in jobs], before)

    def test_live_monitor_toggle_does_not_commit_other_draft_fields(self):
        self.queue_fixture()
        self.seed_config()
        self.controller.setSetting('language', 'en')
        self.controller.preview = False
        with patch.object(self.controller_module, 'command', return_value='') as command, \
             patch.object(self.controller, 'refresh'), \
             patch.object(self.controller, 'submit', side_effect=lambda operation, finished: finished(operation(), None)):
            self.controller.setMonitoring(True)
        saved = json.loads(self.config_file.read_text())
        self.assertTrue(saved['monitoring'])
        self.assertEqual(saved['language'], 'de')
        self.assertEqual(self.controller.draft['language'], 'en')
        self.assertTrue(self.controller.state['settingsDirty'])
        self.assertTrue(self.controller.state['monitoringEnabled'])
        self.assertIn('start', [call.args[0] for call in command.call_args_list])

    @unittest.skipUnless(__import__('sys').platform == 'win32', 'Windows registration adapter')
    def test_autostart_uses_saved_configuration_without_saving_unrelated_edits(self):
        self.queue_fixture()
        baseline = self.seed_config()
        self.controller.setSetting('language', 'en')
        with patch.object(self.controller_module, 'windows_login_item') as register, \
             patch.object(self.controller, 'submit', side_effect=lambda operation, finished: finished(operation(), None)):
            self.controller.setAutostart(True)
        register.assert_any_call(True)
        self.assertEqual(json.loads(self.config_file.read_text()), baseline)

    def test_committed_watch_status_is_independent_from_queue_and_unsaved_paths(self):
        self.queue_fixture()
        saved = self.seed_config()
        saved.update(folders=['Saved folder'], monitoring=False)
        self.controller.saved_config = saved
        self.controller.paths = ['Unsaved folder']
        self.controller.snapshot.update(running=True, current={**self.controller.snapshot['queue'][0], 'state':'transcribing','started':100},
            folders=[dict(path='Saved folder', available=True, error=None)])
        self.controller.changed.emit()
        state = self.controller.state
        self.assertFalse(state['monitoringEnabled'])
        self.assertTrue(state['processingActive'])
        self.assertEqual((state['folderCount'], state['availableFolderCount']), (1, 1))
        self.assertIn('Überwachung aus', self.visual('folderStatusButton').property('text'))

    def test_cancel_confirmation_keeps_original_job_when_worker_advances(self):
        jobs = self.queue_fixture()
        self.controller.snapshot.update(current={**jobs[0], 'state':'transcribing', 'started':100}, running=True)
        self.controller.changed.emit()
        QTest.qWait(30)
        self.click('currentActionsButton')
        self.click('cancelCurrentButton')
        dialog = self.window.findChild(QObject, 'confirmCurrent')
        self.assertTrue(dialog.property('visible'))
        self.assertEqual(dialog.property('jobId'), 1)
        self.controller.snapshot['current'] = {**jobs[1], 'state':'transcribing', 'started':100}
        self.controller.changed.emit()
        with patch.object(self.controller, 'cancelJob') as cancel:
            QMetaObject.invokeMethod(dialog, 'accept')
            QTest.qWait(20)
        cancel.assert_called_once_with(1)

    def test_queue_clear_is_separate_from_stop_and_requires_confirmation(self):
        self.queue_fixture()
        self.click('queueActionsButton')
        with patch.object(self.controller, 'cancelQueue') as cancel:
            self.click('cancelQueueButton')
            dialog = self.window.findChild(QObject, 'confirmCancelQueue')
            self.assertTrue(dialog.property('visible'))
            cancel.assert_not_called()
            QMetaObject.invokeMethod(dialog, 'accept')
            QTest.qWait(20)
        cancel.assert_called_once_with()

    def test_result_actions_wrap_inside_minimum_window(self):
        jobs = self.queue_fixture()
        self.window.resize(1010, 630)
        job = {**jobs[0], 'state':'failed', 'known_transcript_path':str(self.controller_module.PROFILE/'Known result.txt')}
        self.controller.snapshot['jobs'] = [job]
        self.controller.showDetails(job['id'])
        QTest.qWait(60)
        for name in ('openTranscriptButton', 'revealTranscriptButton', 'closeJobDialog'):
            item = self.visual(name)
            self.assertIsNotNone(item, name)
            point = item.mapToScene(QPointF(item.width(), item.height()))
            self.assertLessEqual(point.x(), self.window.width(), name)
            self.assertLessEqual(point.y(), self.window.height(), name)

    def test_one_off_pickers_route_multiple_paths_without_changing_watched_folders(self):
        self.queue_fixture()
        paths = [(self.controller_module.PROFILE / name).as_posix() for name in ('One.wav', 'Two.mp4')]
        before = list(self.controller.paths)
        with patch.object(self.controller_module.QFileDialog, 'getOpenFileNames', return_value=(paths, '')), \
             patch.object(self.controller, 'enqueueFolders') as enqueue:
            self.controller.pickMedia()
        self.assertEqual([url.toLocalFile().replace('\\','/') for url in enqueue.call_args.args[0]], paths)
        with patch.object(self.controller_module.QFileDialog, 'getExistingDirectory', return_value=str(self.controller_module.PROFILE / 'Folder')), \
             patch.object(self.controller, 'enqueueFolders') as enqueue:
            self.controller.pickDropFolder()
        self.assertEqual(len(enqueue.call_args.args[0]), 1)
        self.assertEqual(self.controller.paths, before)

    def test_page_change_discards_inflight_reply_and_requests_correct_offset(self):
        jobs = self.queue_fixture()
        self.controller.snapshot.update(history_counts=dict(all=1000,done=1000,errors=0,cancelled=0,existing=0))
        self.controller.preview = False
        self.controller.next_probe = float('inf')
        callbacks = []
        with patch.object(self.controller, 'submit', side_effect=lambda operation, finished: callbacks.append((operation,finished))):
            self.controller.setHistoryPage(1)
            self.controller.setHistoryPage(2)
            stale = {**self.controller.snapshot, 'jobs':[{**jobs[0], 'id':251, 'state':'done'}]}
            callbacks[0][1](stale, None)
            self.assertFalse(self.controller.history)
            self.assertEqual(len(callbacks), 2)
            result = {**stale, 'jobs':[{**jobs[0], 'id':501, 'state':'done'}]}
            with patch.object(self.controller_module, 'command', return_value=json.dumps(result)) as command:
                callbacks[1][0]()
            args = command.call_args.args
            self.assertEqual(args[args.index('--offset') + 1], '500')
            callbacks[1][1](result, None)
        self.assertEqual([job['id'] for job in self.controller.history], [501])
        self.assertEqual(self.controller.state['historyOffset'], 500)
        self.controller.preview = True

    def test_filter_search_and_order_restart_pagination(self):
        self.queue_fixture()
        for operation in (lambda:self.controller.setFilter('done'), lambda:self.controller.setOrder('asc'),
                          lambda:self.controller.setHistorySearch('Changed query')):
            self.controller.history_page = 7
            operation()
            self.assertEqual(self.controller.history_page, 0)

    def test_workspace_preference_roundtrip_and_width_constraints(self):
        self.controller.setWorkspaceView('focus')
        self.assertEqual(self.controller.workspaceView, 'focus')
        self.controller.setWorkspaceView('invalid')
        self.assertEqual(self.controller.workspaceView, 'focus')
        self.controller.saveWorkspaceHistoryWidth(500)
        self.assertEqual(self.controller.workspaceHistoryWidth, 500)
        self.controller.saveWorkspaceHistoryWidth(2)
        self.assertEqual(self.controller.workspaceHistoryWidth, 340)

    def test_latest_drop_feedback_is_not_hidden_by_an_old_settings_message(self):
        self.queue_fixture()
        self.controller.notify('Alte Einstellungsbestätigung')
        self.controller.drop_message = 'Einige Dateien sind bereits in der Warteschlange.'
        self.controller.drop_error = True
        self.controller.changed.emit()
        self.assertEqual(self.visual('feedback').property('text'), self.controller.drop_message)
        self.assertTrue(self.controller.state['feedbackError'])
        self.controller.notify('Neue Aktion erfolgreich')
        self.assertEqual(self.visual('feedback').property('text'), 'Neue Aktion erfolgreich')
        self.assertFalse(self.controller.state['feedbackError'])
        self.assertIn(self.controller.drop_message, self.controller.state['feedbackDetails'])

    def test_global_error_shortcut_exposes_all_errors_despite_an_active_search(self):
        self.queue_fixture()
        self.controller.snapshot.update(history_counts=dict(all=1,errors=0,done=1),
            global_history_counts=dict(all=800,errors=4,done=796))
        self.controller.setHistorySearch('Only matching successes')
        self.controller.changed.emit()
        self.assertEqual(self.visual('globalErrorsButton').property('text'), 'Fehler (4)')
        self.click('globalErrorsButton')
        self.assertEqual(self.controller.history_query, '')
        self.assertEqual(self.controller.filter, 'errors')

    def test_stop_remains_available_during_other_work_without_releasing_its_busy_state(self):
        jobs = self.queue_fixture()
        self.controller.snapshot.update(current={**jobs[0], 'state':'transcribing', 'started':100}, running=True)
        self.controller.busy = True
        self.controller.changed.emit()
        pending = []
        with patch.object(self.controller, 'submit', side_effect=lambda operation, finished: pending.append((operation,finished))):
            self.click('queuePlaybackButton')
            self.assertFalse(pending)
            self.assertFalse(self.visual('finishCurrentThenPauseButton').property('enabled'))
            self.click('stopProcessingNowButton')
            self.assertTrue(self.controller.state['processingStopping'])
            self.assertTrue(self.controller.busy)
            pending[0][1](dict(current_id=1,export_finishes=False), None)
        self.assertTrue(self.controller.busy)
        self.assertFalse(self.controller.stop_command_pending)
        self.assertTrue(self.controller.state['busy'])

    def test_header_switch_saves_only_monitoring_and_tracks_both_controls(self):
        jobs=self.queue_fixture();self.seed_config()
        self.controller.setSetting('language','en')
        self.controller.snapshot.update(running=True,current={**jobs[0],'state':'transcribing','started':100},queue_paused=False)
        before=json.dumps(self.controller.snapshot,sort_keys=True)
        self.controller.preview=False
        self.addCleanup(setattr,self.controller,'preview',True)
        with patch.object(self.controller_module,'command') as command, \
             patch.object(self.controller,'refresh'), \
             patch.object(self.controller,'submit',side_effect=lambda operation,finished:finished(operation(),None)):
            switch=self.click('headerMonitoringSwitch')
            self.assertTrue(switch.property('checked'))
            self.assertTrue(json.loads(self.config_file.read_text())['monitoring'])
            self.assertEqual(json.loads(self.config_file.read_text())['language'],'de')
            self.assertEqual(self.controller.draft['language'],'en')
            status=self.visual('folderStatusButton')
            self.assertLess(switch.mapToScene(QPointF(switch.width(),0)).x(),status.mapToScene(QPointF(0,0)).x())
            self.click('headerMonitoringSwitch')
            self.assertFalse(switch.property('checked'))
            self.assertFalse(json.loads(self.config_file.read_text())['monitoring'])
            self.controller.setMonitoring(True);QTest.qWait(30)
            self.assertTrue(switch.property('checked'))
            self.assertTrue(all(call.args[0]=='validate-settings' for call in command.call_args_list))
        self.assertEqual(before,json.dumps(self.controller.snapshot,sort_keys=True))

    def test_stop_dialog_cancel_and_escape_leave_processing_unchanged(self):
        jobs=self.queue_fixture();self.seed_config()
        self.controller.snapshot.update(running=True,current={**jobs[0],'state':'transcribing','started':100},queue_paused=False)
        self.controller.changed.emit()
        before=json.dumps(self.controller.snapshot,sort_keys=True)
        with patch.object(self.controller,'submit') as submit:
            self.click('queuePlaybackButton')
            dialog=self.window.findChild(QObject,'stopProcessingDialog')
            self.assertTrue(dialog.property('visible'))
            self.click('cancelStopProcessingButton')
            self.assertFalse(dialog.property('visible'))
            self.click('queuePlaybackButton')
            QTest.keyClick(self.window,Qt.Key.Key_Escape);QTest.qWait(30)
            self.assertFalse(dialog.property('visible'))
            submit.assert_not_called()
        self.assertEqual(before,json.dumps(self.controller.snapshot,sort_keys=True))

    def test_stop_dialog_graceful_choice_pauses_queue_without_requesting_abort(self):
        jobs=self.queue_fixture();self.seed_config()
        self.controller.snapshot.update(running=True,current={**jobs[0],'state':'transcribing','started':100},queue_paused=False)
        self.controller.changed.emit()
        with patch.object(self.controller_module,'command',return_value='') as command, \
             patch.object(self.controller,'action',side_effect=lambda operation,message:operation()):
            self.click('queuePlaybackButton')
            command.assert_not_called()
            self.click('finishCurrentThenPauseButton')
            command.assert_called_once_with('queue-pause','on')
        self.assertFalse(self.window.findChild(QObject,'stopProcessingDialog').property('visible'))
        self.assertFalse(self.controller.playback_stopping)

    def test_stop_dialog_choices_wrap_inside_minimum_window(self):
        jobs=self.queue_fixture()
        self.controller.snapshot.update(running=True,current={**jobs[0],'state':'transcribing','started':100},queue_paused=False)
        self.controller.changed.emit();self.window.resize(1010,630)
        self.click('queuePlaybackButton')
        dialog=self.window.findChild(QObject,'stopProcessingDialog')
        self.assertLessEqual(dialog.property('width'),self.window.width()-32)
        self.assertLessEqual(dialog.property('height'),self.window.height()-32)
        for name in ('stopProcessingNowButton','finishCurrentThenPauseButton','cancelStopProcessingButton'):
            choice=self.visual(name)
            point=choice.mapToScene(QPointF(choice.width(),choice.height()))
            self.assertLessEqual(point.x(),self.window.width(),name)
            self.assertLessEqual(point.y(),self.window.height(),name)
        self.assertEqual(self.visual('finishCurrentThenPauseButton').property('text'),
            'Transkription geregelt fertigstellen und Warteschlange pausieren')

    def test_feedback_dialog_contains_complete_long_message_inside_window(self):
        self.queue_fixture()
        self.window.resize(1010,630)
        text='\n'.join('D:/Example/Very long source path '+str(i) for i in range(600))
        self.controller.notify(text, True)
        dialog = self.window.findChild(QObject,'feedbackDialog')
        QMetaObject.invokeMethod(dialog,'open')
        QTest.qWait(50)
        self.assertLessEqual(dialog.property('height'), self.window.height()-48)
        self.assertEqual(self.visual('feedbackText').property('text'), text)

    def test_pending_job_details_distinguish_planned_settings_from_measured_results(self):
        jobs = self.queue_fixture()
        jobs[0]['settings'] = json.dumps({**self.controller_module.DEFAULTS,'dover_lap':True})
        self.controller.showDetails(1)
        values = {row['label']:row['value'] for row in self.controller.detail['rows']}
        self.assertIn('Modell für diesen Auftrag', values)
        self.assertEqual(values['Verfahren der Sprecherzuordnung'], 'DOVER-Lap geplant')

    def test_live_removal_preserves_visible_scroll_anchor_and_expanded_row(self):
        jobs = self.queue_fixture(400)
        self.controller.setQueueCompact(True)
        view = self.visual('queueList')
        view.setProperty('contentY', 11000)
        QTest.qWait(70)
        visible = [self.visual('queueRow'+str(i)) for i in range(100,180)]
        visible = [r for r in visible if r is not None and 0 < r.y()-view.property('contentY') < view.height()-90]
        self.assertTrue(visible)
        row = visible[0]
        identifier = row.property('modelData')['id']
        self.click('expandQueue'+str(identifier))
        before = row.mapToScene(QPointF(0,0)).y()
        self.controller.snapshot['queue'] = jobs[1:]
        self.controller.update_queue()
        QTest.qWait(90)
        same = self.visual('queueRow'+str(identifier))
        self.assertTrue(same.property('expanded'))
        self.assertAlmostEqual(same.mapToScene(QPointF(0,0)).y(), before, delta=2)
        self.controller.setQueueSearch('*'+str(identifier)+'*')
        QTest.qWait(50)
        self.assertTrue(self.visual('queueRow'+str(identifier)).property('expanded'))
        self.controller.setQueueSearch('')

    def test_equal_history_with_new_search_context_resets_scope(self):
        self.controller.update_history()
        original = self.controller.history_model_scope
        self.controller.history_query = 'no matches'
        self.controller.update_history()
        self.assertNotEqual(self.controller.history_model_scope, original)

