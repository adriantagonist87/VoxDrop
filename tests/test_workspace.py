"""Exercise the shared workspace with real QML events and isolated configuration."""
import json
import unittest
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
            self.assertTrue(self.controller.state['processingStopping'])
            self.assertTrue(self.controller.busy)
            pending[0][1](dict(current_id=1,export_finishes=False), None)
        self.assertTrue(self.controller.busy)
        self.assertFalse(self.controller.stop_command_pending)
        self.assertTrue(self.controller.state['busy'])

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

