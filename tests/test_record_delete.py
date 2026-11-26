from contextlib import closing
import hashlib
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

import record_delete as deletion
import watch_service as service
from desktop.transcript_search import search_transcripts


class RecordDeleteTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.state=self.root/'service';self.bin=self.root/'fake-bin';self.bin.mkdir()
        service.initialise(self.state);self.db=service.database(self.state);self.addCleanup(self.db.close)
        self.settings=dict(watch_path=str(self.root),monitoring=True,include_subfolders=True)
        self.calls=[]

    def add(self,name='Original Ä.wav',*,origin=None,state='done',data=b'synthetic media'):
        path=self.root/name;path.write_bytes(data);meta=path.stat()
        with self.db:
            identifier=self.db.execute('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated,state,origin_job_id,media_hash) VALUES (?,?,?,?,?,1,1,?,?,?)',
                (str(path),str(self.root),meta.st_size,meta.st_mtime_ns,json.dumps(self.settings),state,origin,hashlib.sha256(data).hexdigest())).lastrowid
        text=deletion.text_path(dict(self.db.execute('SELECT * FROM jobs WHERE id=?',(identifier,)).fetchone()))
        text.write_text('Künstlicher Suchinhalt '+name,encoding='utf-8')
        return identifier,path,text

    def trash(self,path):
        self.calls.append(path)
        destination=self.bin/(str(len(self.calls))+'-'+path.name)
        path.rename(destination)
        return str(destination)

    def test_confirmation_is_read_only_and_cancel_discards_only_the_plan(self):
        identifier,source,text=self.add();plan=deletion.prepare(self.db,self.state,identifier)
        self.assertTrue(source.exists() and text.exists());self.assertEqual(plan['recordCount'],1)
        self.assertEqual(len(plan['files']),2)
        deletion.discard(self.state,plan['token'])
        self.assertTrue(source.exists() and text.exists())
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)

    def test_trash_then_remove_all_selected_sql_and_search_records_only(self):
        identifier,source,text=self.add();other,untouched,other_text=self.add('Andere.wav',data=b'other')
        service.remember_result(self.db,other,'reused',other_text,prior_job_id=identifier);self.db.commit()
        result=search_transcripts(self.state/'jobs.sqlite3',self.state/'transcript-search.sqlite3',self.state/'content-search-result.json',
            'Suchinhalt',lambda job:deletion.text_path(job),Event())
        self.assertEqual(result['matches'],2)
        cache=self.state/'jobs'/str(identifier);cache.mkdir(parents=True);(cache/'transcript.txt').write_text('local cache')
        before_pause=service.queue_paused(self.db)
        plan=deletion.prepare(self.db,self.state,identifier)
        deleted=deletion.execute(self.db,self.state,plan['token'],trash=self.trash)
        self.assertEqual(deleted['deletedIds'],[identifier]);self.assertEqual(deleted['trashed'],3)
        self.assertFalse(source.exists() or text.exists() or cache.exists())
        self.assertTrue(untouched.exists() and other_text.exists())
        self.assertEqual(self.db.execute('SELECT prior_job_id FROM known_results WHERE job_id=?',(other,)).fetchone()[0],None)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events WHERE job_id=?',(identifier,)).fetchone()[0],0)
        self.assertFalse(self.db.execute('PRAGMA foreign_key_check').fetchall())
        self.assertEqual(service.queue_paused(self.db),before_pause)
        with closing(__import__('sqlite3').connect(self.state/'transcript-search.sqlite3')) as index:
            self.assertEqual(index.execute('SELECT job_id FROM job_files').fetchall(),[(other,)])

    def test_shared_transcript_and_retranscriptions_are_listed_and_deleted_together(self):
        root,source,text=self.add()
        child,_,child_text=self.add(origin=root)
        alternate,alt,_=self.add('Original Ä.flv')
        plan=deletion.prepare(self.db,self.state,child)
        self.assertEqual(plan['recordCount'],3)
        self.assertEqual(len([file for file in plan['files'] if file['role']=='original']),2)
        deletion.execute(self.db,self.state,plan['token'],trash=self.trash)
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
        self.assertFalse(any(path.exists() for path in (source,text,child_text,alt)))

    def test_keep_original_trashes_transcripts_and_cache_only(self):
        root,source,text=self.add()
        _,_,child_text=self.add(origin=root)
        _,second_source,_=self.add('Original Ä.flv')
        cache=self.state/'jobs'/str(root);cache.mkdir(parents=True)
        (cache/'copy.wav').write_bytes(b'synthetic copy')
        plan=deletion.prepare(self.db,self.state,root)
        self.assertTrue(plan['keepOriginal'])
        self.assertFalse(plan['lockedMode'])
        with patch.object(deletion,'check_delete_access') as preflight:
            result=deletion.execute(self.db,self.state,plan['token'],keep_original=True,trash=self.trash)
        self.assertCountEqual(self.calls,[text,child_text,cache])
        self.assertCountEqual([call.args[0] for call in preflight.call_args_list],self.calls)
        self.assertEqual(result['trashed'],3)
        for original in (source,second_source):
            self.assertEqual(original.read_bytes(),b'synthetic media')
        self.assertFalse(self.db.execute('SELECT 1 FROM jobs').fetchone())
        self.assertFalse(self.db.execute('PRAGMA foreign_key_check').fetchall())

    def test_delete_twenty_selected_records_keeps_originals_and_unselected_results(self):
        selected=[self.add(f'Aufnahme {index}.wav') for index in range(20)]
        other,source,text=self.add('Unbeteiligt.wav')
        identifiers=[identifier for identifier,_,_ in selected]
        plan=deletion.prepare(self.db,self.state,*identifiers)
        self.assertEqual(plan['selectedCount'],20)
        self.assertEqual(len(plan['files']),40)
        result=deletion.execute(self.db,self.state,plan['token'],keep_original=True,trash=self.trash)
        self.assertEqual(result['deletedIds'],identifiers)
        self.assertEqual(result['trashed'],20)
        self.assertCountEqual(self.calls,[transcript for _,_,transcript in selected])
        self.assertTrue(all(path.read_bytes()==b'synthetic media' for _,path,_ in selected))
        self.assertTrue(source.exists() and text.exists())
        self.assertEqual(self.db.execute('SELECT id FROM jobs').fetchone()[0],other)
        self.assertEqual(self.db.execute('SELECT count(*) FROM retained_media').fetchone()[0],20)

    def test_batch_groups_shared_transcript_and_refuses_replaced_original_in_another_group(self):
        first,source,text=self.add()
        shared,alternate,_=self.add('Original Ä.flv')
        third,changed,_=self.add('Geändert.wav')
        changed.write_bytes(b'different original')
        with self.assertRaisesRegex(ValueError,'andere oder geänderte Originaldatei'):
            deletion.prepare(self.db,self.state,first,shared,third)
        self.assertTrue(source.exists() and alternate.exists() and text.exists())
        plan=deletion.prepare(self.db,self.state,first,shared)
        self.assertEqual(plan['selectedCount'],2)
        self.assertEqual(plan['recordCount'],2)
        self.assertEqual(len(plan['files']),3)
        deletion.execute(self.db,self.state,plan['token'],trash=self.trash)
        self.assertEqual(self.calls.count(text),1)
        self.assertFalse(source.exists() or alternate.exists())
        self.assertTrue(changed.exists())

    def test_partial_batch_resumes_from_member_without_merging_unrelated_record(self):
        first,source,text=self.add()
        second,second_source,second_text=self.add('Zweite.wav')
        third,third_source,third_text=self.add('Dritte.wav')
        other_plan=deletion.prepare(self.db,self.state,second,third)
        plan=deletion.prepare(self.db,self.state,first,second)

        def fail_second(path):
            if path==second_text:
                raise OSError('synthetic recycle error')
            return self.trash(path)

        with self.assertRaisesRegex(RuntimeError,'Datenbankeinträge bleiben'):
            deletion.execute(self.db,self.state,plan['token'],keep_original=True,trash=fail_second)
        with self.assertRaisesRegex(ValueError,'begonnenen Löschung'):
            deletion.prepare(self.db,self.state,first,third)
        with self.assertRaisesRegex(ValueError,'begonnenen Löschung'):
            deletion.execute(self.db,self.state,other_plan['token'],trash=self.trash)
        resumed=deletion.prepare(self.db,self.state,second)
        self.assertEqual(resumed['token'],plan['token'])
        self.assertEqual(resumed['selectedCount'],2)
        self.assertTrue(resumed['keepOriginal'] and resumed['lockedMode'])
        deletion.execute(self.db,self.state,resumed['token'],keep_original=True,trash=self.trash)
        self.assertEqual(self.calls,[text,second_text])
        self.assertTrue(source.exists() and second_source.exists() and third_source.exists() and third_text.exists())

    def test_keep_original_survives_rescan_and_accepts_explicit_drop_or_changed_file(self):
        first,source,_=self.add()
        second,changed,_=self.add('Zweite.wav')
        for identifier in (first,second):
            plan=deletion.prepare(self.db,self.state,identifier)
            deletion.execute(self.db,self.state,plan['token'],keep_original=True,trash=self.trash)
        service.initialise(self.state)
        settings={**self.settings,'folders':[str(self.root)],'interval_seconds':1,'require_smb':False}

        def inspect(settings):
            versions=[(str(path),path.stat().st_size,path.stat().st_mtime_ns) for path in (source,changed)]
            return str(self.root),str(self.root),versions,''

        with closing(service.database(self.state)) as reopened:
            service.scan(reopened,settings,inspect=inspect)
            self.assertFalse(reopened.execute('SELECT 1 FROM jobs').fetchone())
            changed.write_bytes(b'different media version')
            service.scan(reopened,settings,inspect=inspect)
            self.assertEqual([row['source'] for row in reopened.execute('SELECT source FROM jobs')],[str(changed)])
            batch=service.prepare_drop(reopened,settings,[str(source)])
            self.assertEqual(service.resolve_drop(reopened,batch['token'],'queue')['queued'],1)
            row=reopened.execute('SELECT state,settings FROM jobs WHERE source=?',(str(source),)).fetchone()
            self.assertEqual(row['state'],'ready')
            self.assertTrue(json.loads(row['settings'])['folder_drop'])

    def test_partial_keep_original_resumes_without_allowing_a_mode_change(self):
        root,source,text=self.add()
        _,_,child_text=self.add(origin=root)
        plan=deletion.prepare(self.db,self.state,root)

        def fail_last(path):
            if path==child_text:
                raise OSError('synthetic trash failure')
            return self.trash(path)

        with self.assertRaisesRegex(RuntimeError,'Datenbankeinträge bleiben'):
            deletion.execute(self.db,self.state,plan['token'],keep_original=True,trash=fail_last)
        self.assertFalse(self.db.execute('SELECT 1 FROM retained_media').fetchone())
        resumed=deletion.prepare(self.db,self.state,root)
        self.assertTrue(resumed['lockedMode'] and resumed['keepOriginal'] and resumed['partial'])
        self.assertEqual(resumed['token'],plan['token'])
        with self.assertRaisesRegex(RuntimeError,'bereits bestätigte Auswahl'):
            deletion.execute(self.db,self.state,resumed['token'],keep_original=False,trash=self.trash)
        deletion.execute(self.db,self.state,resumed['token'],keep_original=True,trash=self.trash)
        self.assertEqual(self.calls,[text,child_text])
        self.assertTrue(source.exists())

    def test_network_paths_are_refused_before_any_mutation(self):
        identifier,source,text=self.add()
        with patch.object(deletion,'on_network_volume',return_value=True):
            with self.assertRaisesRegex(ValueError,'Netzlaufwerken'):deletion.prepare(self.db,self.state,identifier)
        self.assertTrue(source.exists() and text.exists())

    def test_changed_media_or_confirmation_snapshot_is_never_deleted(self):
        identifier,source,text=self.add();plan=deletion.prepare(self.db,self.state,identifier)
        source.write_bytes(b'replacement recording')
        with self.assertRaisesRegex(ValueError,'geändert'):deletion.execute(self.db,self.state,plan['token'],trash=self.trash)
        self.assertEqual(self.calls,[])
        with self.assertRaisesRegex(ValueError,'andere oder geänderte'):deletion.prepare(self.db,self.state,identifier)
        self.assertTrue(source.exists() and text.exists())

    def test_partial_trash_failure_keeps_sql_and_resumes_without_retrashing(self):
        identifier,source,text=self.add();plan=deletion.prepare(self.db,self.state,identifier)
        def fail_second(path):
            if path==text:raise OSError('synthetic trash failure')
            return self.trash(path)
        with self.assertRaisesRegex(RuntimeError,'Datenbankeinträge bleiben'):
            deletion.execute(self.db,self.state,plan['token'],trash=fail_second)
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
        self.assertFalse(source.exists());self.assertTrue(text.exists())
        again=deletion.prepare(self.db,self.state,identifier)
        self.assertTrue(again['partial']);self.assertEqual(again['token'],plan['token'])
        self.assertTrue(again['lockedMode']);self.assertFalse(again['keepOriginal'])
        deletion.execute(self.db,self.state,again['token'],trash=self.trash)
        self.assertEqual(self.calls.count(source),1)
        self.assertFalse(self.db.execute('SELECT 1 FROM jobs').fetchone())

    def test_active_related_job_blocks_the_entire_batch(self):
        identifier,source,text=self.add();self.add(origin=identifier,state='transcribing')
        with self.assertRaisesRegex(ValueError,'Verarbeitung'):deletion.prepare(self.db,self.state,identifier)
        self.assertTrue(source.exists() and text.exists())

    def test_changed_sql_snapshot_requires_a_new_confirmation(self):
        identifier,source,text=self.add();plan=deletion.prepare(self.db,self.state,identifier)
        with self.db:self.db.execute('UPDATE jobs SET attempt=attempt+1 WHERE id=?',(identifier,))
        with self.assertRaisesRegex(ValueError,'Datensatz hat sich geändert'):
            deletion.execute(self.db,self.state,plan['token'],trash=self.trash)
        self.assertEqual(self.calls,[]);self.assertTrue(source.exists() and text.exists())

    def test_native_trash_failure_never_falls_back_to_permanent_deletion(self):
        from PySide6 import QtCore
        identifier,source,text=self.add();plan=deletion.prepare(self.db,self.state,identifier)
        with patch.object(QtCore,'QFile') as native:
            native.supportsMoveToTrash.return_value=True
            native.return_value.moveToTrash.return_value=False
            native.return_value.errorString.return_value='synthetic unsupported trash'
            with self.assertRaisesRegex(OSError,'Nicht in den Papierkorb'):
                deletion.execute(self.db,self.state,plan['token'])
        self.assertTrue(source.exists() and text.exists())
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)

    def test_missing_files_can_be_cleaned_from_history(self):
        identifier,source,text=self.add();source.unlink();text.unlink()
        plan=deletion.prepare(self.db,self.state,identifier)
        result=deletion.execute(self.db,self.state,plan['token'],trash=self.trash)
        self.assertEqual(result['trashed'],0);self.assertEqual(self.calls,[])

    def test_replaced_file_at_old_source_is_protected_when_archive_is_valid(self):
        identifier,source,text=self.add();archive=self.root/'archive';archive.mkdir()
        archived=archive/source.name;source.rename(archived)
        source.write_bytes(b'new unrelated media')
        with self.db:self.db.execute('UPDATE jobs SET completed_dir=?,settings=? WHERE id=?',
            (str(archive),json.dumps(dict(watch_path=str(self.root),move_media=True)),identifier))
        plan=deletion.prepare(self.db,self.state,identifier)
        self.assertTrue(any(file['protected'] for file in plan['files']))
        deletion.execute(self.db,self.state,plan['token'],trash=self.trash)
        self.assertEqual(source.read_bytes(),b'new unrelated media');self.assertFalse(archived.exists())

    def test_symlink_cannot_turn_deletion_into_another_file(self):
        identifier,source,text=self.add();victim=self.root/'unrelated.txt';victim.write_text('keep')
        text.unlink()
        try:text.symlink_to(victim)
        except OSError:self.skipTest('Symlink creation unavailable')
        with self.assertRaisesRegex(ValueError,'reguläre'):deletion.prepare(self.db,self.state,identifier)
        self.assertEqual(victim.read_text(),'keep')
