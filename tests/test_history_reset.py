from contextlib import closing,redirect_stdout
import hashlib,io,json,sqlite3,tempfile,unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

import watch_service as service
from desktop.transcript_search import search_transcripts
from history_store import history_category,search_storage_lock,storage_generation


class HistoryResetTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name).resolve();self.state=self.root/'service'
        service.initialise(self.state);self.db=service.database(self.state);self.addCleanup(self.db.close)
        self.index=self.state/'transcript-search.sqlite3';self.results=self.state/'content-search-result.json'
        self.settings=dict(service.read_settings(self.config()))
        self.settings=service.folder_profile(self.settings,str(self.root))

    def config(self):
        path=self.root/'config.json'
        path.write_text(json.dumps(dict(folders=[str(self.root)],monitoring=True,include_subfolders=True,interval_seconds=1)))
        return path

    def add(self,name,state='ready',attempt=0,started=None):
        path=self.root/name;path.write_bytes(name.encode())
        metadata=path.stat()
        with self.db:
            cursor=self.db.execute('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated,state,attempt,started) VALUES (?,?,?,?,?,1,1,?,?,?)',
                (str(path),str(self.root),metadata.st_size,metadata.st_mtime_ns,json.dumps(self.settings),state,attempt,started))
        return cursor.lastrowid,path

    def test_8000_never_started_cancellations_stay_internal_until_explicit_clear(self):
        with self.db:
            self.db.executemany('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated,state) VALUES (?,?,1,1,?,1,1,\'ready\')',
                ((str(self.root/f'Queued {i}.wav'),str(self.root),json.dumps(self.settings)) for i in range(8000)))
        service.cancel_queue(self.db)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],8000)
        self.assertEqual(service.history_jobs(self.db,'desc',250,terminal_only=True),[])
        self.assertEqual(service.history_counts(self.db),dict(all=0,errors=0,done=0,cancelled=0,existing=0))
        with self.db:self.db.execute("UPDATE jobs SET attempt=1,started=1 WHERE id=1")
        self.assertEqual(service.history_counts(self.db)['cancelled'],1)
        self.assertEqual([job['id'] for job in service.history_jobs(self.db,'desc',250,terminal_only=True)],[1])
        with closing(service.database(self.state)) as reopened:
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],8000)
        service.clear_history(self.db,self.state)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)

    def test_history_categories_keep_existing_and_reused_results_out_of_done(self):
        fixtures=[('done',0,None,None),('done',1,1,'reused'),('existing',0,None,'existing'),
                  ('duplicate',1,1,'duplicate'),('failed',1,1,None),('blocked',0,None,None),
                  ('cancelled',0,None,None),('cancelled',1,1,None),('superseded',0,None,None)]
        expected=dict(all=4,errors=2,done=1,cancelled=1,existing=3)
        for number,(state,attempt,started,kind) in enumerate(fixtures):
            identifier,path=self.add(f'{number}.wav',state,attempt,started)
            if kind:
                with self.db:service.remember_result(self.db,identifier,kind,path.with_suffix('.txt'))
        self.assertEqual(service.history_counts(self.db),expected)
        for category,size in expected.items():
            rows=service.history_jobs(self.db,'desc',250,terminal_only=True,history_filter=category)
            self.assertEqual(len(rows),size)
            self.assertTrue(all(history_category(dict(job)) in ({'done','errors','cancelled'} if category=='all' else {category}) for job in rows))

    def search(self,query):
        return search_transcripts(self.state/'jobs.sqlite3',self.index,self.results,query,
            lambda job:service.targets(job)[1],Event())

    def test_full_reset_removes_search_and_drop_data_then_scan_reimports_real_txt(self):
        known,source=self.add('Existing.wav','existing')
        transcript=source.with_suffix('.txt');transcript.write_text('Reimportierbarer Testinhalt',encoding='utf-8')
        other,media=self.add('Unprocessed.wav')
        originals={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in (source,transcript,media)}
        with self.db:
            service.remember_result(self.db,known,'existing',transcript)
            self.db.execute("INSERT INTO drop_batches VALUES ('old-plan',1,'[]','{}')")
            self.db.execute('INSERT INTO folder_refresh VALUES (?)',(str(self.root),))
        service.cancel_queue(self.db)
        first=self.search('Testinhalt');stale=self.results.read_bytes()
        work=self.state/'jobs'/str(other);work.mkdir(parents=True);(work/'cache').write_bytes(b'private cache')
        (self.state/'.search-interrupted').write_bytes(b'old result')
        generation=storage_generation(self.db)
        service.clear_history(self.db,self.state)
        for table in ('jobs','events','known_results','drop_batches','queue_positions','cancel_requests','preemptions','immediate_jobs','folder_status','folder_refresh'):
            self.assertEqual(self.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0,table)
        self.assertEqual(storage_generation(self.db),generation+1)
        self.assertTrue(service.queue_paused(self.db))
        for path in (self.index,self.results,self.state/'jobs',self.state/'.search-interrupted'):
            self.assertFalse(path.exists(),str(path))
        self.assertTrue(all(hashlib.sha256(path.read_bytes()).hexdigest()==digest for path,digest in originals.items()))
        service.scan(self.db,self.settings,100)
        imported=self.db.execute('SELECT * FROM jobs WHERE source=?',(str(source),)).fetchone()
        self.assertGreater(imported['id'],other)
        self.assertEqual(imported['state'],'existing')
        self.assertEqual(service.history_counts(self.db),dict(all=0,errors=0,done=0,cancelled=0,existing=1))
        # Even a copied-back old result token cannot address new records after a reset.
        self.results.write_bytes(stale)
        arguments=['--state-dir',str(self.state),'--model-data',str(self.root/'models'),'status','--filter','existing','--search','Testinhalt','--content-results',str(self.results),'--content-token',first['token']]
        with redirect_stdout(io.StringIO()),patch('sys.stderr',new_callable=io.StringIO):
            self.assertEqual(service.main(arguments),1)
        second=self.search('Testinhalt')
        arguments[-1]=second['token']
        with redirect_stdout(io.StringIO()) as output:self.assertEqual(service.main(arguments),0)
        self.assertEqual([job['id'] for job in json.loads(output.getvalue())['jobs']],[imported['id']])

    def test_clear_during_search_is_refused_without_changing_rows_or_index(self):
        _,source=self.add('Protected.wav','done');source.with_suffix('.txt').write_text('Protected content')
        self.search('Protected');saved=self.index.read_bytes()
        with search_storage_lock(self.state):
            with self.assertRaisesRegex(RuntimeError,'Detailsuche'):service.clear_history(self.db,self.state)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)
        self.assertEqual(self.index.read_bytes(),saved)
        service.clear_history(self.db,self.state)
        self.assertFalse(self.index.exists())

    def test_scan_started_before_reset_cannot_restore_its_old_file_list(self):
        _,source=self.add('Before.wav');self.db.execute('DELETE FROM events');self.db.execute('DELETE FROM jobs');self.db.commit()
        metadata=source.stat()
        def inspect(settings):
            with closing(service.database(self.state)) as other:service.clear_history(other,self.state)
            return str(self.root),str(self.root),[(str(source),metadata.st_size,metadata.st_mtime_ns)],None
        service.scan(self.db,self.settings,100,inspect=inspect)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
        service.scan(self.db,self.settings,101)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)

    def test_failed_cache_cleanup_is_reported_and_can_be_retried_without_old_jobs(self):
        _,source=self.add('Cleanup.wav','done');source.with_suffix('.txt').write_text('Cleanup content')
        self.search('Cleanup')
        with patch.object(service.shutil,'rmtree',side_effect=PermissionError('synthetic sharing lock')):
            with self.assertRaisesRegex(RuntimeError,'Bereinigung erneut'):service.clear_history(self.db,self.state)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(service.main(['--state-dir',str(self.state),'status']),0)
        self.assertTrue(json.loads(output.getvalue())['has_stored_data'])
        service.clear_history(self.db,self.state)
        self.assertFalse(list(self.state.glob('.history-clear-*')))
        self.assertTrue(source.exists())
