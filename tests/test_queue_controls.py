import hashlib
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import watch_service as service
from platform_io import WINDOWS, file_is_being_written
from queue_control import (
    JobCancelled, cancel_job, cancel_queue, move_queue_item, queue_jobs,
    queue_paused, set_queue_paused, start_queue, stop_queue,
)
from transcription_worker import GraphicsTimeout, run_transcription


class QueueTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve();self.incoming=self.root/'incoming';self.incoming.mkdir()
        self.state=self.root/'state';service.initialise(self.state)
        self.db=service.database(self.state);self.addCleanup(self.db.close)
        self.config=self.root/'config.json'
        self.config.write_text(json.dumps(dict(folders=[str(self.incoming)],include_subfolders=True,monitoring=True,interval_seconds=1,hardware='cpu',speakers=False)))
        self.settings=service.folder_profile(service.read_settings(self.config),str(self.incoming))
        self.engine=Mock(return_value='Synthetic transcript\n')

    def add(self,name='one.wav',content=b'synthetic media',now=100):
        source=self.incoming/name;source.write_bytes(content)
        service.scan(self.db,self.settings,now);service.scan(self.db,self.settings,now+1)
        return source,self.db.execute('select id from jobs where source=? order by id desc',(str(source),)).fetchone()[0]

    def row(self,identifier):
        return self.db.execute('select * from jobs where id=?',(identifier,)).fetchone()

    @unittest.skipUnless(WINDOWS, "Windows CPU-Schutz")
    def test_graphics_timeout_pauses_queue_and_cpu_mode_retries_queued_cuda_job(self):
        config = json.loads(self.config.read_text())
        config["hardware"] = "cuda"
        self.config.write_text(json.dumps(config))
        self.settings = service.folder_profile(service.read_settings(self.config), str(self.incoming))
        source, one = self.add()
        _, two = self.add("second.wav", b"second recording")
        failing = Mock(side_effect=GraphicsTimeout("Test-Timeout"))
        self.assertTrue(service.next_job(self.db, self.state, failing, config=self.config))
        self.assertEqual(failing.call_args.kwargs["hardware"], "cuda")
        self.assertTrue(queue_paused(self.db))
        self.assertEqual([row["id"] for row in queue_jobs(self.db)], [one, two])
        self.assertFalse(source.with_suffix(".txt").exists())
        self.assertIn("Test-Timeout", self.db.execute("select reason from queue_graphics_hold").fetchone()[0])
        self.assertFalse(service.next_job(self.db, self.state, self.engine, config=self.config))
        config["windows_cpu_only"] = True
        self.config.write_text(json.dumps(config))
        start_queue(self.db)
        self.assertTrue(service.next_job(self.db, self.state, self.engine, config=self.config))
        self.assertEqual(self.engine.call_args.kwargs["hardware"], "cpu")
        saved = json.loads(self.row(one)["settings"])
        self.assertEqual((saved["hardware"], saved["execution_hardware"]), ("cuda", "cpu"))
        self.assertIsNone(self.db.execute("select reason from queue_graphics_hold").fetchone())
        self.assertEqual(source.read_bytes(), b"synthetic media")
        self.assertTrue(source.with_suffix(".txt").is_file())

    @unittest.skipUnless(WINDOWS, "Windows GPU-Timeout")
    def test_crash_recovery_with_display_event_prevents_cuda_restart(self):
        _, identifier = self.add()
        with self.db:
            self.db.execute("""UPDATE jobs SET state='transcribing',started=?,
                settings=json_set(settings,'$.hardware','cuda') WHERE id=?""", (time.time()-5, identifier))
        with patch.object(service, "graphics_timeout_since", return_value="GPU-Timeout"):
            service.recover(self.db, self.state)
        self.assertEqual(self.row(identifier)["state"], "ready")
        self.assertTrue(queue_paused(self.db))
        self.assertFalse(service.next_job(self.db, self.state, self.engine, config=self.config))

    def test_stop_interrupts_current_and_preserves_queue_then_play_restarts_in_order(self):
        source, one=self.add();_,two=self.add('Second.wav',b'second')
        before={row['id']:row['settings'] for row in queue_jobs(self.db)}
        def engine(*args,**options):
            with closing(service.database(self.state)) as other:
                result=stop_queue(other)
                self.assertEqual(result['current_id'],one)
                self.assertFalse(result['export_finishes'])
                stop_queue(other)  # repeated Stop must preserve resumability
                with self.assertRaisesRegex(ValueError,'noch gestoppt'):
                    start_queue(other)
            self.assertTrue(options['cancelled']())
            return 'Unfinished text must not be published'
        self.assertTrue(service.next_job(self.db,self.state,engine))
        self.assertEqual(self.row(one)['state'],'ready')
        self.assertTrue(queue_paused(self.db))
        self.assertEqual([row['id'] for row in queue_jobs(self.db)],[one,two])
        self.assertEqual({row['id']:row['settings'] for row in queue_jobs(self.db)},before)
        self.assertFalse(source.with_suffix('.txt').exists())
        self.assertFalse(service.next_job(self.db,self.state,self.engine))
        start_queue(self.db)
        self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(one)['state'],'done')
        self.assertEqual(self.row(two)['state'],'ready')
        self.assertEqual(source.read_bytes(),b'synthetic media')

    def test_stopped_queue_recovers_without_auto_resuming_and_can_play_with_monitoring_off(self):
        _,one=self.add();_,two=self.add('Second.wav',b'second')
        with self.db:self.db.execute("update jobs set state='transcribing' where id=?",(one,))
        stop_queue(self.db);service.recover(self.db,self.state);service.recover(self.db,self.state)
        self.assertTrue(queue_paused(self.db))
        self.assertEqual([row['id'] for row in queue_jobs(self.db)],[one,two])
        self.assertFalse(service.next_job(self.db,self.state,self.engine,allow_automatic=False))
        start_queue(self.db)
        self.assertTrue(service.next_job(self.db,self.state,self.engine,allow_automatic=False))
        self.assertEqual(self.row(one)['state'],'done')

    def test_stop_finishes_completed_export_and_keeps_following_jobs_waiting(self):
        source,one=self.add();_,two=self.add('Second.wav',b'second')
        publish=service.publish_transcript_only
        def save_completed(db,job,*args,**kwargs):
            result=stop_queue(db)
            self.assertTrue(result['export_finishes'])
            self.assertEqual(result['current_id'],one)
            self.assertFalse(service.cancellation_requested(db,one))
            return publish(db,job,*args,**kwargs)
        with patch.object(service,'publish_transcript_only',side_effect=save_completed):
            self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(one)['state'],'done')
        self.assertTrue(source.with_suffix('.txt').exists())
        self.assertFalse(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(two)['state'],'ready')

    def test_stop_does_not_restore_an_explicitly_removed_active_job(self):
        _,one=self.add();_,two=self.add('Second.wav',b'second')
        with self.db:self.db.execute("update jobs set state='transcribing' where id=?",(one,))
        cancel_job(self.db,one);stop_queue(self.db);service.recover(self.db,self.state)
        self.assertEqual(self.row(one)['state'],'cancelled')
        self.assertTrue(queue_paused(self.db))
        self.assertEqual([row['id'] for row in queue_jobs(self.db)],[two])

    def test_existing_queued_job_uses_live_budget_config_without_overwriting_job_options(self):
        source, identifier = self.add()
        before = self.row(identifier)['settings']
        saved = json.loads(self.config.read_text())
        saved['gpu_budget_percent'] = 50
        self.config.write_text(json.dumps(saved))
        self.assertTrue(service.next_job(self.db, self.state, self.engine, config=self.config))
        self.assertEqual(self.engine.call_args.kwargs['gpu_budget_config'], self.config)
        self.assertEqual(self.row(identifier)['settings'], before)
        self.assertEqual(service.read_settings(self.config)['gpu_budget_percent'], 50)

    def test_explicit_start_processes_queue_with_monitoring_off_without_reviving_cancelled(self):
        first,one=self.add();second,two=self.add('cancelled.wav',b'cancelled media')
        settings=json.loads(self.config.read_text());settings['monitoring']=False
        self.config.write_text(json.dumps(settings))
        before=self.config.read_bytes()
        cancel_job(self.db,two);set_queue_paused(self.db,True)
        order=[row['id'] for row in queue_jobs(self.db)]
        self.assertEqual(service.start_queue(self.db),1)
        self.assertEqual(service.start_queue(self.db),1)  # Repeated clicks remain idempotent.
        self.assertFalse(queue_paused(self.db))
        self.assertEqual([row['id'] for row in queue_jobs(self.db)],order)
        self.assertTrue(service.next_job(self.db,self.state,self.engine,available_only=True,allow_automatic=False,config=self.config))
        self.assertEqual(self.row(one)['state'],'done')
        self.assertEqual(self.row(two)['state'],'cancelled')
        self.engine.assert_called_once()
        self.assertEqual(self.config.read_bytes(),before)
        self.assertEqual(first.read_bytes(),b'synthetic media')
        self.assertEqual(second.read_bytes(),b'cancelled media')

    @unittest.skipUnless(WINDOWS or sys.platform == 'darwin','Native writable-handle probe')
    def test_explicit_start_does_not_bypass_open_writer_or_wait_for_scan_interval(self):
        source,identifier=self.add()
        with self.db:self.db.execute("UPDATE jobs SET state='seen' WHERE id=?",(identifier,))
        service.start_queue(self.db)
        self.assertEqual(self.row(identifier)['state'],'ready')
        with source.open('ab'):
            service.next_job(self.db,self.state,self.engine,available_only=True,allow_automatic=False)
        self.engine.assert_not_called()
        self.assertIn('Aufnahme wird noch geschrieben',self.row(identifier)['error'])
        with self.db:self.db.execute('UPDATE job_retries SET retry_at=0')
        service.next_job(self.db,self.state,self.engine,available_only=True,allow_automatic=False)
        self.assertEqual(self.row(identifier)['state'],'done')

    def test_cleanup_error_cannot_replace_app_quit_preemption_or_user_cancel(self):
        from app_lifecycle import request_stop, register_owner
        for app_quit in (True, False):
            register_owner(self.db)
            source, identifier = self.add(f'cleanup-{app_quit}.wav',str(app_quit).encode())
            def interrupted(*args, **kwargs):
                if app_quit:
                    request_stop(self.db)
                else:
                    cancel_job(self.db,identifier)
                raise PermissionError('Mapped audio still closing')
            service.next_job(self.db,self.state,interrupted)
            self.assertEqual(self.row(identifier)['state'], 'ready' if app_quit else 'cancelled')
            self.assertIsNone(self.row(identifier)['error'])
            self.assertFalse((self.state/'jobs'/str(identifier)).exists())
            self.assertEqual(source.read_bytes(),str(app_quit).encode())
            if app_quit:
                cancel_job(self.db,identifier)

    def test_queue_contains_every_item_beyond_history_limit_and_order_survives_restart(self):
        for index in range(301):(self.incoming/f'item-{index:03}.wav').write_bytes(str(index).encode())
        service.scan(self.db,self.settings,100);service.scan(self.db,self.settings,101)
        rows=queue_jobs(self.db);self.assertEqual(len(rows),301)
        identifiers=[row['id'] for row in rows];detected={row['id']:row['detected'] for row in rows}
        move_queue_item(self.db,identifiers[-1],identifiers[0])
        with closing(service.database(self.state)) as reopened:
            self.assertEqual([row['id'] for row in queue_jobs(reopened)],[identifiers[-1],*identifiers[:-1]])
            self.assertEqual({row['id']:row['detected'] for row in queue_jobs(reopened)},detected)
        self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(identifiers[-1])['state'],'done')

    def test_remove_persists_across_scans_and_explicit_restore_appends(self):
        first,one=self.add();_,two=self.add('two.wav',b'other')
        cancel_job(self.db,one)
        service.scan(self.db,self.settings,200)
        service.recover(self.db,self.state)
        self.assertEqual(self.row(one)['state'],'cancelled')
        self.assertEqual([row['id'] for row in queue_jobs(self.db)],[two])
        service.retry(self.db,one)
        self.assertEqual([row['id'] for row in queue_jobs(self.db)],[two,one])
        self.assertEqual(first.read_bytes(),b'synthetic media')

    def test_history_counts_and_error_filter_include_rows_beyond_display_limit(self):
        for index in range(260):
            (self.incoming / f'item-{index:03}.wav').write_bytes(str(index).encode())
        service.scan(self.db, self.settings, 100)
        service.scan(self.db, self.settings, 101)
        identifiers = [row[0] for row in self.db.execute('SELECT id FROM jobs ORDER BY id')]
        states = ('failed', 'blocked', 'existing', 'duplicate', 'cancelled', 'superseded',
                  'ready', 'seen', 'copying', 'exporting', 'transcribing')
        with self.db:
            self.db.execute("UPDATE jobs SET state='done', updated=100")
            self.db.executemany('UPDATE jobs SET state=?, updated=? WHERE id=?',
                                [(state, index + 1, identifiers[index])
                                 for index, state in enumerate(states)])
        self.assertNotIn(identifiers[0], [job['id'] for job in service.history_jobs(
            self.db, 'desc', 250, terminal_only=True)])
        for selected, expected_size in [('all',250),('errors',2),('done',249),('existing',2),('cancelled',0)]:
            with redirect_stdout(io.StringIO()) as output:
                result = service.main(['--state-dir', str(self.state), '--model-data', str(self.root / 'models'),
                                       'status', '--limit', '250', '--filter', selected])
            self.assertEqual(result, 0)
            snapshot = json.loads(output.getvalue())
            self.assertEqual(snapshot['history_counts'],dict(all=251,errors=2,done=249,cancelled=0,existing=2))
            self.assertEqual(len(snapshot['jobs']), expected_size)
            if selected == 'errors':
                self.assertEqual({job['id'] for job in snapshot['jobs']}, set(identifiers[:2]))

    def test_relative_queue_moves_use_all_rows_and_preserve_detection_times(self):
        identifiers=[self.add(f'Item-{index}.wav',str(index).encode())[1] for index in range(5)]
        detected={row['id']:row['detected'] for row in queue_jobs(self.db)}
        selected=identifiers[3]
        cases=[('up',[0,1,3,2,4]),('down',[0,1,2,3,4]),('first',[3,0,1,2,4]),('last',[0,1,2,4,3])]
        for direction,order in cases:
            service.move_queue_relative(self.db,selected,direction)
            self.assertEqual([row['id'] for row in queue_jobs(self.db)],[identifiers[index] for index in order])
        self.assertEqual({row['id']:row['detected'] for row in queue_jobs(self.db)},detected)
        with self.db:
            self.db.execute("update jobs set state='transcribing' where id=?",(selected,))
        with self.assertRaises(ValueError):
            service.move_queue_relative(self.db,selected,'first')

    def test_drop_after_anchor_keeps_hidden_following_rows_in_place(self):
        identifiers=[self.add(f'Item-{index}.wav',str(index).encode())[1] for index in range(5)]
        service.move_queue_item(self.db,identifiers[0],identifiers[2],after=True)
        expected=[identifiers[index] for index in (1,2,0,3,4)]
        with closing(service.database(self.state)) as reopened:
            self.assertEqual([row['id'] for row in queue_jobs(reopened)],expected)
        service.move_queue_item(self.db,identifiers[0],identifiers[1])
        self.assertEqual([row['id'] for row in queue_jobs(self.db)],identifiers)

    def plan_drop(self, paths):
        with patch.object(service, 'inspect_folders_with_deadline', side_effect=service.inspect_folders):
            return service.prepare_drop(self.db, self.settings, [str(path) for path in paths])

    def test_mixed_drop_preflight_is_read_only_deduplicated_and_ignore_is_idempotent(self):
        done, one = self.add('Done.wav', b'finished')
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        queued, two = self.add('Queued.wav', b'waiting')
        new = self.incoming / 'New.wav'; new.write_bytes(b'new')
        subfolder = self.incoming / 'Sub'; subfolder.mkdir()
        nested = subfolder / 'Nested.wav'; nested.write_bytes(b'nested')
        plan = self.plan_drop([self.incoming, queued, subfolder, done])
        self.assertTrue(plan['has_conflicts'])
        self.assertEqual((plan['counts']['new'], plan['counts']['queued'], plan['counts']['done']), (2, 1, 1))
        self.assertEqual(self.db.execute('select count(*) from jobs').fetchone()[0], 2)
        result = service.resolve_drop(self.db, plan['token'], 'ignore')
        self.assertEqual((result['queued'], result['ignored']), (2, 2))
        self.assertEqual(service.resolve_drop(self.db, plan['token'], 'immediate'), result)
        self.assertEqual(self.db.execute('select count(*) from jobs').fetchone()[0], 4)
        self.assertEqual(self.row(two)['state'], 'ready')
        self.assertEqual(done.read_bytes(), b'finished')

    def test_drop_of_completed_file_explicitly_retranscribes_to_separate_txt(self):
        source, one = self.add()
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        old = source.with_suffix('.txt').read_bytes()
        plan = self.plan_drop([source])
        result = service.resolve_drop(self.db, plan['token'], 'retranscribe')
        self.assertEqual(result['queued'], 1)
        new = queue_jobs(self.db)[0]
        self.assertEqual(new['origin_job_id'], one)
        self.assertTrue(json.loads(new['settings'])['folder_drop'])
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        self.assertEqual(source.with_suffix('.txt').read_bytes(), old)
        self.assertTrue(service.targets(self.row(new['id']))[1].is_file())

    def test_immediate_drop_preempts_and_restores_current_job_after_selected_batch(self):
        source, one = self.add(); priority, two = self.add('Priority.wav', b'other')
        def engine(*args, **options):
            with closing(service.database(self.state)) as other:
                plan = service.prepare_drop(other, self.settings, [str(priority)])
                result = service.resolve_drop(other, plan['token'], 'immediate')
                self.assertEqual(result['interrupted'], one)
            self.assertTrue(options['cancelled']())
            return 'Interrupted result must not publish.'
        self.assertTrue(service.next_job(self.db, self.state, engine))
        self.assertEqual(self.row(one)['state'], 'ready')
        self.assertFalse(source.with_suffix('.txt').exists())
        self.assertFalse((self.state / 'jobs' / str(one)).exists())
        self.assertEqual([job['id'] for job in queue_jobs(self.db)], [two, one])
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        self.assertEqual(self.row(two)['state'], 'done')
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        self.assertEqual(self.row(one)['state'], 'done')
        self.assertEqual(source.read_bytes(), b'synthetic media')

    def test_preemption_survives_recovery_and_explicit_cancel_overrides_resume(self):
        _, one = self.add(); priority, two = self.add('Priority.wav', b'other')
        with self.db:
            self.db.execute("update jobs set state='transcribing' where id=?", (one,))
        plan = self.plan_drop([priority])
        service.resolve_drop(self.db, plan['token'], 'immediate')
        service.recover(self.db, self.state)
        self.assertEqual([job['id'] for job in queue_jobs(self.db)], [two, one])
        with self.db:
            self.db.execute("update jobs set state='transcribing' where id=?", (one,))
        plan = self.plan_drop([priority])
        service.resolve_drop(self.db, plan['token'], 'immediate')
        cancel_queue(self.db)
        service.recover(self.db, self.state)
        self.assertEqual(self.row(one)['state'], 'cancelled')
        self.assertTrue(queue_paused(self.db))
        self.assertEqual(len(queue_jobs(self.db)), 0)

    def test_immediate_selection_does_not_resume_the_rest_of_a_paused_queue(self):
        _, one = self.add(); selected, two = self.add('Selected.wav', b'other')
        set_queue_paused(self.db, True)
        plan = self.plan_drop([selected])
        result = service.resolve_drop(self.db, plan['token'], 'immediate')
        self.assertTrue(result['queue_remains_paused'])
        self.assertTrue(queue_paused(self.db))
        self.assertEqual(service.immediate_count(self.db), 1)
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        self.assertEqual(self.row(two)['state'], 'done')
        self.assertFalse(service.next_job(self.db, self.state, self.engine))
        self.assertEqual(self.row(one)['state'], 'ready')
        self.assertTrue(queue_paused(self.db))

    def test_manual_pause_stops_future_immediate_work_and_preempted_current_can_finish(self):
        _, one = self.add(); selected, two = self.add('Selected.wav', b'other')
        _, three = self.add('Rest.wav', b'rest')
        def engine(*args, **options):
            with closing(service.database(self.state)) as other:
                set_queue_paused(other, True)
                plan = service.prepare_drop(other, self.settings, [str(selected)])
                service.resolve_drop(other, plan['token'], 'immediate')
            return 'Do not publish this interrupted attempt'
        self.assertTrue(service.next_job(self.db, self.state, engine))
        self.assertTrue(queue_paused(self.db))
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        self.assertTrue(service.next_job(self.db, self.state, self.engine))
        self.assertEqual(self.row(two)['state'], 'done')
        self.assertEqual(self.row(one)['state'], 'done')
        self.assertFalse(service.next_job(self.db, self.state, self.engine))
        self.assertEqual(self.row(three)['state'], 'ready')
        plan = self.plan_drop([self.incoming / 'Rest.wav'])
        service.resolve_drop(self.db, plan['token'], 'immediate')
        set_queue_paused(self.db, True)
        self.assertFalse(service.next_job(self.db, self.state, self.engine))

    def test_immediate_drop_waits_for_export_and_does_not_cancel_selected_active_job(self):
        current, one = self.add(); priority, two = self.add('Priority.wav', b'other')
        with self.db:
            self.db.execute("update jobs set state='exporting',publication_started=1 where id=?", (one,))
        plan = self.plan_drop([priority])
        result = service.resolve_drop(self.db, plan['token'], 'immediate')
        self.assertIsNone(result['interrupted'])
        self.assertTrue(result['export_finishes'])
        with self.db:
            self.db.execute("update jobs set state='transcribing',publication_started=0 where id=?", (one,))
        plan = self.plan_drop([current, priority])
        result = service.resolve_drop(self.db, plan['token'], 'immediate')
        self.assertEqual(result['active'], 1)
        self.assertIsNone(result['interrupted'])
        self.assertFalse(service.cancellation_requested(self.db, one))

    def test_drop_reports_changed_and_unsupported_files_without_losing_valid_items(self):
        changed = self.incoming / 'Changed.wav'; changed.write_bytes(b'original')
        valid = self.incoming / 'Valid.wav'; valid.write_bytes(b'valid')
        unsupported = self.incoming / 'Notes.txt'; unsupported.write_text('Not media')
        plan = self.plan_drop([changed, valid, unsupported])
        self.assertEqual(len(plan['warnings']), 1)
        changed.write_bytes(b'changed version')
        result = service.resolve_drop(self.db, plan['token'], 'front')
        self.assertEqual(result['queued'], 1)
        self.assertEqual(len(result['warnings']), 2)
        self.assertEqual([job['source'] for job in queue_jobs(self.db)], [str(valid)])

    @unittest.skipUnless(WINDOWS, 'Windows path case')
    def test_drop_path_case_and_dot_segments_do_not_duplicate_a_waiting_file(self):
        source, one = self.add()
        plan = self.plan_drop([str(source).upper(), self.incoming / 'Sub' / '..' / source.name])
        self.assertEqual(len(plan['items']), 1)
        self.assertEqual(plan['counts']['queued'], 1)
        service.resolve_drop(self.db, plan['token'], 'front')
        self.assertEqual([job['id'] for job in queue_jobs(self.db)], [one])

    def test_clear_refills_from_watch_scan_but_keeps_processing_paused_and_errors(self):
        source,one=self.add();_,two=self.add('two.wav',b'other')
        with self.db:
            self.db.execute("update jobs set state='failed' where id=?",(two,))
            self.db.execute('insert into job_retries values (?,?,?)',(two,0,10))
        self.assertEqual(cancel_queue(self.db),2)
        self.assertTrue(queue_paused(self.db))
        self.assertEqual(len(queue_jobs(self.db)),0)
        self.add('new.wav',b'new',now=300)
        self.assertFalse(service.next_job(self.db,self.state,self.engine))
        set_queue_paused(self.db,False)
        self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(one)['state'],'done')
        self.assertEqual(self.row(two)['state'],'failed')
        self.assertEqual(source.read_bytes(),b'synthetic media')

    def test_active_cancel_stops_before_export_and_crash_recovery_keeps_intent(self):
        source,one=self.add()
        def engine(*args,**kwargs):
            with closing(service.database(self.state)) as other:
                self.assertEqual(cancel_job(other,one),'requested')
            self.assertTrue(kwargs['cancelled']())
            return 'This result must never be published.'
        self.assertTrue(service.next_job(self.db,self.state,engine))
        self.assertEqual(self.row(one)['state'],'cancelled')
        self.assertFalse(source.with_suffix('.txt').exists())
        self.assertFalse((self.state/'jobs'/str(one)).exists())
        service.retry(self.db,one)
        with self.db:self.db.execute("update jobs set state='transcribing' where id=?",(one,))
        cancel_job(self.db,one);service.recover(self.db,self.state)
        self.assertEqual(self.row(one)['state'],'cancelled')

    def test_export_barrier_rejects_cancellation_and_reorder_revalidates_claim(self):
        _,one=self.add();_,two=self.add('two.wav',b'other')
        original=service.keep_transcript_beside_source
        def reorder(db,job,settings,config):
            move_queue_item(db,one,0)
            return original(db,job,settings,config)
        with patch.object(service,'keep_transcript_beside_source',side_effect=reorder):
            self.assertFalse(service.next_job(self.db,self.state,self.engine))
        self.engine.assert_not_called()
        with self.db:self.db.execute("update jobs set state='exporting',publication_started=1 where id=?",(two,))
        with self.assertRaises(ValueError):cancel_job(self.db,two)

    def test_existing_txt_is_not_automatically_transcribed_and_manual_rerun_is_separate(self):
        source,one=self.add();txt=source.with_suffix('.txt');txt.write_text('Earlier result',encoding='utf-8')
        self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.engine.assert_not_called();self.assertEqual(self.row(one)['state'],'existing')
        new=service.retranscribe(self.db,one,self.settings)
        self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(new)['state'],'done')
        self.assertEqual(txt.read_text(),'Earlier result')
        self.assertTrue(service.targets(self.row(new))[1].is_file())

    def test_existing_result_is_labelled_during_scan_before_waiting_for_other_jobs(self):
        (self.incoming/'one.txt').write_text('Earlier result',encoding='utf-8')
        source,one=self.add()
        self.assertEqual(self.row(one)['state'],'existing')
        self.assertEqual(len(queue_jobs(self.db)),0)
        self.engine.assert_not_called()
        self.assertTrue(source.exists())

    def test_rename_uses_content_hash_and_does_not_run_inference_twice(self):
        source,one=self.add();self.assertTrue(service.next_job(self.db,self.state,self.engine))
        renamed=source.with_name('renamed.wav');source.rename(renamed)
        service.scan(self.db,self.settings,200);service.scan(self.db,self.settings,201)
        new=self.db.execute('select max(id) from jobs').fetchone()[0]
        self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(new)['state'],'done');self.assertEqual(self.engine.call_count,1)
        self.assertTrue(renamed.with_suffix('.txt').is_file())
        row=service.history_jobs(self.db,'desc',1)[0]
        self.assertEqual(row['prior_job_id'],one)
        self.assertEqual(row['result_kind'],'reused')
        self.assertEqual(hashlib.sha256(renamed.read_bytes()).hexdigest(),self.row(one)['media_hash'])

    @unittest.skipUnless(WINDOWS or sys.platform == 'darwin','Native writable-handle probe')
    def test_open_obs_style_writer_is_deferred_even_without_growth_then_processed_once(self):
        source,one=self.add()
        with source.open('ab'):
            self.assertTrue(file_is_being_written(source))
            self.assertTrue(service.next_job(self.db,self.state,self.engine))
            self.engine.assert_not_called();self.assertEqual(self.row(one)['state'],'failed')
            self.assertIn('Aufnahme wird noch geschrieben',self.row(one)['error'])
        self.assertFalse(file_is_being_written(source))
        with self.db:self.db.execute('update job_retries set retry_at=0')
        self.assertTrue(service.next_job(self.db,self.state,self.engine))
        self.assertEqual(self.row(one)['state'],'done');self.engine.assert_called_once()

    def test_real_cancel_kills_inference_descendants_and_cleans_temporary_audio(self):
        source,_=self.add()
        script=self.root/'fake-inference.py';pids=self.root/'pids.json'
        script.write_text("import json,os,subprocess,sys,tempfile,time\nfrom pathlib import Path\n"
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
            f"Path({str(pids)!r}).write_text(json.dumps([os.getpid(),child.pid]))\n"
            "Path(tempfile.gettempdir(),'cancel-audio.tmp').write_bytes(b'synthetic')\n"
            "time.sleep(60)\n",encoding='utf-8')
        with patch('transcription_worker.__file__',str(script)):
            started=time.monotonic()
            with self.assertRaises(JobCancelled):
                run_transcription(source,report=Mock(),measurements={},cancelled=pids.exists)
        self.assertLess(time.monotonic()-started,15)
        for pid in json.loads(pids.read_text()):
            self.assertFalse(psutil.pid_exists(pid),f'Orphan process {pid}')
        self.assertFalse(list(self.incoming.glob('transcription-*')))


if __name__=='__main__':unittest.main()
