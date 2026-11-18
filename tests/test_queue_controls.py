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
    queue_paused, set_queue_paused,
)
from transcription_worker import run_transcription


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
        for selected, expected_size in [('all', 250), ('errors', 2), ('done', 250)]:
            with redirect_stdout(io.StringIO()) as output:
                result = service.main(['--state-dir', str(self.state), '--model-data', str(self.root / 'models'),
                                       'status', '--limit', '250', '--filter', selected])
            self.assertEqual(result, 0)
            snapshot = json.loads(output.getvalue())
            self.assertEqual(snapshot['history_counts'], dict(all=255, errors=2, done=251))
            self.assertEqual(len(snapshot['jobs']), expected_size)
            if selected == 'errors':
                self.assertEqual({job['id'] for job in snapshot['jobs']}, set(identifiers[:2]))

    def test_cancel_all_pauses_and_cancels_automatic_retries_without_readding(self):
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
        self.assertEqual(self.row(one)['state'],'cancelled')
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

    @unittest.skipUnless(WINDOWS,'Native Windows writable-handle probe')
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
