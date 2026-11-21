"""Real ZIP/SQLite round trips and interrupted publication, only synthetic data."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
import profile_transfer as transfer
import watch_service as service


class ProfileTransferTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.profile = self.root / 'source'; self.models = self.root / 'source-models'
        self.target = self.root / 'target'; self.target_models = self.root / 'target-models'
        self.media = self.root / 'recordings'; self.media.mkdir()
        self.config = dict(folders=[str(self.media)], folder_options={str(self.media):dict(paused=True,output='beside')},
                           monitoring=True, interval_seconds=60, hardware=service.DEFAULT_HARDWARE, language='de', dover_lap=True)
        for profile in (self.profile, self.target):
            service.initialise(profile / 'service')
            (profile / 'config.json').write_text(json.dumps(self.config), encoding='utf-8')
            (profile / 'layout.ini').write_text('[General]\nhistoryOrder=asc\nqueueCompact=false\n', encoding='utf-8')
        self.archive = self.root / 'backup.voxdrop.zip'
        self.db = service.database(self.profile / 'service'); self.addCleanup(self.db.close)
        self.settings = service.folder_profile(service.read_settings(self.profile / 'config.json'), str(self.media))
        self.recording = self.media / 'Unterordner' / 'Gespräch + ü.wav'
        self.recording.parent.mkdir(); self.recording.write_bytes(b'synthetic recording')
        self.transcript = self.recording.with_suffix('.txt'); self.transcript.write_text('Synthetisches Transkript', encoding='utf-8')
        for number, state in enumerate(('done', 'ready', 'cancelled', 'transcribing', 'exporting'), 1):
            path = self.recording if number == 1 else self.media / f'{number}.wav'
            if not path.exists(): path.write_bytes(b'synthetic ' + str(number).encode())
            metadata = path.stat()
            with self.db:
                self.db.execute('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated,state,attempt,publication_started) VALUES(?,?,?,?,?,1,1,?,1,?)',
                    (str(path), str(path.parent), metadata.st_size, metadata.st_mtime_ns, json.dumps(self.settings), state, state == 'exporting'))
        with self.db:
            service.remember_result(self.db, 1, 'existing', self.transcript)
            self.db.execute('UPDATE queue_positions SET position=99-job_id')
        (self.models / 'models/qwen').mkdir(parents=True)
        (self.models / 'models/qwen/weights.safetensors').write_bytes(b'synthetic weights')
        (self.models / 'huggingface').mkdir()
        (self.models / 'huggingface/token').write_text('synthetic-secret-not-exported')
        (self.profile / 'service/desktop.log').write_text('private runtime log')

    def export(self, **options):
        return transfer.export_backup(self.profile, self.models, self.archive, options)

    def restore(self, **options):
        return transfer.restore_backup(self.target, self.target_models, self.archive,
            {**transfer.DEFAULT_OPTIONS, **options}, hardware='cpu', media_destination=self.root / 'migrated-media')

    def test_wal_snapshot_round_trip_preserves_all_rows_queue_and_safe_pause(self):
        self.export()
        report = self.restore()
        self.assertTrue(Path(report['backup']).is_file())
        with closing(service.database(self.target / 'service')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 5)
            self.assertEqual(db.execute('SELECT position FROM queue_positions ORDER BY job_id').fetchall(),
                             self.db.execute('SELECT position FROM queue_positions ORDER BY job_id').fetchall())
            self.assertTrue(service.queue_paused(db))
            self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=3').fetchone()[0], 'cancelled')
            self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=4').fetchone()[0], 'ready')
            self.assertEqual(db.execute('SELECT state FROM jobs WHERE id=5').fetchone()[0], 'blocked')
            self.assertIsNone(db.execute('SELECT owner_pid FROM app_control').fetchone()[0])
        config = json.loads((self.target / 'config.json').read_text())
        self.assertFalse(config['monitoring']); self.assertEqual(config['hardware'], 'cpu')
        self.assertTrue(config['folder_options'][str(self.media)]['paused'])
        self.assertEqual((self.target / 'layout.ini').read_bytes(), (self.profile / 'layout.ini').read_bytes())
        self.assertFalse(any('log' in f['path'] for f in transfer.inspect_backup(self.archive)['files']))

    def test_full_media_and_models_reimport_remaps_history_preserves_original_and_mtime(self):
        before = self.recording.read_bytes(); metadata = self.recording.stat()
        manifest = self.export(models=True, media=True)
        self.assertFalse(any('token' in item['path'] for item in manifest['files']))
        self.target_models.mkdir(); (self.target_models / 'old-model').write_bytes(b'old weights')
        (self.target_models/'huggingface').mkdir()
        (self.target_models/'huggingface/token').write_text('synthetic-target-token')
        report = self.restore(models=True, media=True)
        self.assertEqual(self.recording.read_bytes(), before)
        with closing(service.database(self.target / 'service')) as db:
            job = db.execute('SELECT * FROM jobs WHERE id=1').fetchone()
            self.assertTrue(Path(job['source']).is_relative_to(Path(report['media_directory'])))
            self.assertEqual(Path(job['source']).read_bytes(), before)
            self.assertEqual(Path(job['source']).stat().st_mtime_ns, metadata.st_mtime_ns)
            path = db.execute('SELECT transcript_path FROM known_results WHERE job_id=1').fetchone()[0]
            self.assertEqual(Path(path).read_bytes(), self.transcript.read_bytes())
        self.assertEqual((self.target_models / 'models/qwen/weights.safetensors').read_bytes(), b'synthetic weights')
        self.assertEqual((self.target_models/'huggingface/token').read_text(),'synthetic-target-token')
        self.assertTrue(list(self.root.glob('.voxdrop-vor-import-*-target-models/old-model')))
        # Reimport chooses a fresh directory and preserves the first import's media.
        repeated = self.restore(models=False, media=True)
        self.assertNotEqual(report['media_directory'], repeated['media_directory'])
        self.assertTrue(Path(report['media_directory']).is_dir())

    def test_settings_only_keeps_history_but_pauses_existing_queue(self):
        self.export(databases=False)
        with closing(service.database(self.target / 'service')) as db, db:
            db.execute('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated) VALUES(?,?,1,1,?,1,1)',
                       (str(self.root / 'existing.wav'), str(self.root), json.dumps(self.settings)))
        self.restore(databases=False)
        with closing(service.database(self.target / 'service')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 1)
            self.assertTrue(service.queue_paused(db))

    def test_all_databases_and_fts_content_survive_path_relocation(self):
        index=self.profile/'service/transcript-search.sqlite3'
        with closing(sqlite3.connect(index)) as db, db:
            db.executescript('CREATE TABLE files(id INTEGER PRIMARY KEY,path TEXT UNIQUE,size INTEGER,mtime_ns INTEGER);'
                             'CREATE TABLE job_files(job_id INTEGER PRIMARY KEY,path TEXT);'
                             'CREATE VIRTUAL TABLE transcript_fts USING fts5(body);')
            db.execute('INSERT INTO files VALUES(1,?,1,1)',(str(self.transcript),))
            db.execute('INSERT INTO job_files VALUES(1,?)',(str(self.transcript),))
            db.execute("INSERT INTO transcript_fts(rowid,body) VALUES(1,'Migrationstest')")
        notes=self.profile/'service/extra.sqlite3'
        with closing(sqlite3.connect(notes)) as db, db:
            db.execute('CREATE TABLE notes(value TEXT)');db.execute("INSERT INTO notes VALUES('Zusatzdatenbank')")
        self.export()
        relocated=self.root/'new-recordings'
        transfer.restore_backup(self.target,self.target_models,self.archive,transfer.DEFAULT_OPTIONS,
                                hardware='cpu',mappings={str(self.media):str(relocated)})
        with closing(sqlite3.connect(self.target/'service/transcript-search.sqlite3')) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM transcript_fts WHERE transcript_fts MATCH 'Migrationstest'").fetchone()[0],1)
            self.assertTrue(Path(db.execute('SELECT path FROM files').fetchone()[0]).is_relative_to(relocated))
        with closing(sqlite3.connect(self.target/'service/extra.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT value FROM notes').fetchone()[0],'Zusatzdatenbank')

    def test_media_only_import_does_not_redirect_unselected_settings_or_history(self):
        self.export(media=True)
        report=self.restore(settings=False,databases=False,models=False,media=True)
        self.assertTrue(Path(report['media_directory']).is_dir())
        current=json.loads((self.target/'config.json').read_text())
        self.assertEqual(current['folders'],self.config['folders'])
        with closing(service.database(self.target/'service')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)

    def test_corruption_and_unsafe_manifest_leave_existing_profile_unchanged(self):
        manifest = self.export()
        original = (self.target / 'config.json').read_bytes()
        with zipfile.ZipFile(self.archive) as archive:
            content = {name: archive.read(name) for name in archive.namelist()}
        blob = 'blobs/' + manifest['files'][0]['sha256']
        content[blob] = b'x' * len(content[blob])
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, value in content.items(): archive.writestr(name, value)
        with self.assertRaisesRegex(ValueError, 'Prüfsumme'): self.restore()
        self.assertEqual((self.target / 'config.json').read_bytes(), original)
        self.assertFalse((self.target / transfer.JOURNAL).exists())
        for path in ('../escape', '/absolute', 'C:/escape', 'service\\escape', 'CON', 'foo./test'):
            with self.subTest(path=path), self.assertRaises(ValueError): transfer.safe_relative(path)

    def test_failed_publication_rolls_back_every_already_replaced_file(self):
        self.export(models=True)
        old = (self.target / 'config.json').read_bytes()
        real_replace = os.replace
        def replace(source, destination):
            if Path(destination) == self.target_models:
                raise OSError('synthetic disk failure')
            return real_replace(source, destination)
        with patch.object(transfer.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'synthetic disk'): self.restore(models=True)
        self.assertEqual((self.target / 'config.json').read_bytes(), old)
        self.assertFalse((self.target / transfer.JOURNAL).exists())
        with closing(service.database(self.target / 'service')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)

    def test_next_start_recovers_interrupted_multi_file_commit(self):
        config = self.target / 'config.json'; before = config.read_bytes()
        old = self.target / '.old'; config.rename(old); config.write_bytes(b'partial new profile')
        staged = self.root / 'already-moved'; self.assertFalse(staged.exists())
        transfer.write_json(self.target / transfer.JOURNAL, dict(status='applying', operations=[dict(
            target=str(config), backup=str(old), staged=str(staged), existed=True)]))
        transfer.recover_interrupted(self.target)
        self.assertEqual(config.read_bytes(), before)

    def test_export_cancel_is_atomic_and_import_refuses_running_service_lock(self):
        self.archive.write_bytes(b'previous archive')
        cancel = Event(); cancel.set()
        with self.assertRaises(transfer.TransferCancelled):
            transfer.export_backup(self.profile, self.models, self.archive, cancel=cancel)
        self.assertEqual(self.archive.read_bytes(), b'previous archive')
        self.export()
        with transfer.stopped_profile(self.target):
            with self.assertRaisesRegex(RuntimeError, 'läuft noch'): self.restore()

    def test_windows_to_mac_prefix_mapping_is_component_based_and_handles_unc(self):
        mappings = {r'D:\Meetings': '/Volumes/Meetings', r'\\server\share': '/Volumes/share'}
        self.assertEqual(transfer.remap_path(r'd:\MEETINGS\Unterordner\Ü.wav', mappings), str(Path('/Volumes/Meetings') / 'Unterordner/Ü.wav'))
        self.assertEqual(transfer.remap_path(r'D:\Meetings-Alt\file.wav', mappings), r'D:\Meetings-Alt\file.wav')
        self.assertEqual(transfer.remap_path(r'\\server\share\Aufnahmen\A.wav', mappings), str(Path('/Volumes/share') / 'Aufnahmen/A.wav'))

    def test_internal_model_links_are_materialized_without_link_permissions(self):
        original = self.models / 'models/qwen/weights.safetensors'
        linked = original.with_name('linked.safetensors')
        try: linked.symlink_to(original.name)
        except OSError as error: self.skipTest(str(error))
        self.export(models=True)
        self.restore(models=True)
        self.assertFalse((self.target_models / 'models/qwen/linked.safetensors').is_symlink())
        self.assertEqual((self.target_models / 'models/qwen/linked.safetensors').read_bytes(), original.read_bytes())


if __name__ == '__main__': unittest.main()
