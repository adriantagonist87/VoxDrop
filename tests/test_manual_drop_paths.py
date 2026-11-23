"""Manual drops keep their own source/output scope, including drive aliases."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import watch_service as service
from queue_control import queue_paused, set_queue_paused


class ManualDropPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.canonical = self.root / 'ResolvedShare'
        (self.canonical / 'Sub').mkdir(parents=True)
        self.alias = self.root / 'MappedDrive'
        self.watched = self.root / 'Watched'
        self.watched.mkdir()
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps(dict(folders=[str(self.watched)], monitoring=False,
            create_output_subfolder=True, include_subfolders=False, output_subfolder='_ARCHIVE',
            folder_options={str(self.watched):dict(paused=True,output='subfolder')},
            require_smb=True, scope_dir=str(self.watched), hardware='cpu', speakers=False)))
        self.settings = service.read_settings(self.config)
        self.state = self.root / 'state'
        service.initialise(self.state)
        self.db = service.database(self.state)
        self.addCleanup(self.db.close)

    def alias_probe(self, parent, *, resolved=None):
        resolve = Path.resolve
        def aliased(path, *args, **kwargs):
            return (resolved or self.canonical) if path == self.alias else resolve(path, *args, **kwargs)
        with patch.object(service, 'resolve_folder', return_value=self.canonical), \
             patch.object(Path, 'resolve', autospec=True, side_effect=aliased):
            return service.inspect_folders(dict(watch_path=str(self.alias), source_parent=str(parent),
                include_subfolders=True, create_output_subfolder=False, monitoring=False, probe_write=False))

    def test_drive_alias_retains_job_paths_after_checking_resolved_root(self):
        parent = self.alias / 'Sub'
        incoming, completed, files, _ = self.alias_probe(parent)
        self.assertEqual((incoming, completed, files), (str(parent), str(parent), []))

    def test_same_directory_alias_is_valid_for_retranscription(self):
        incoming, completed, _, _ = self.alias_probe(self.alias)
        self.assertEqual((incoming, completed), (str(self.alias), str(self.alias)))

    def test_alias_does_not_admit_a_directory_outside_selected_root(self):
        with self.assertRaisesRegex(OSError, 'außerhalb des überwachten Pfads'):
            self.alias_probe(self.root / 'Outside')

    def test_alias_must_still_resolve_to_the_selected_directory(self):
        with self.assertRaisesRegex(OSError, 'außerhalb des überwachten Pfads'):
            self.alias_probe(self.alias / 'Sub', resolved=self.root / 'DifferentShare')

    def test_alias_does_not_skip_descendant_reparse_and_device_checks(self):
        with patch.object(service, 'is_scan_directory', return_value=False) as checked:
            with self.assertRaisesRegex(OSError, 'kein regulärer Ordner'):
                self.alias_probe(self.alias / 'Sub')
        checked.assert_called_once_with((self.canonical / 'Sub').lstat(), self.canonical.stat().st_dev)

    def test_single_file_drops_ignore_watch_roots_and_output_options(self):
        before = self.config.read_bytes()
        outside = self.root / 'Outside'
        outside.mkdir()
        for parent in (self.watched, outside):
            with self.subTest(parent=parent.name):
                source = parent / 'Recording.wav'
                source.write_bytes(b'synthetic original')
                plan = service.prepare_drop(self.db, self.settings, [str(source)])
                self.assertFalse(plan['warnings'])
                result = service.resolve_drop(self.db, plan['token'], 'immediate')
                self.assertEqual(result['queued'], 1)
                engine = Mock(return_value='Manual transcript\n')
                with patch.object(service, 'inspect_folders_with_deadline', side_effect=service.inspect_folders):
                    self.assertTrue(service.next_job(self.db, self.state, engine,
                        available_only=True, allow_automatic=False, config=self.config))
                self.assertEqual(source.with_suffix('.txt').read_text(), 'Manual transcript\n')
                self.assertEqual(source.read_bytes(), b'synthetic original')
                self.assertFalse((parent / '_ARCHIVE').exists())
                row = self.db.execute('select * from jobs where source=?', (str(source),)).fetchone()
                self.assertEqual(row['state'], 'done')
                options = json.loads(row['settings'])
                self.assertTrue(options['folder_drop'])
                self.assertFalse(options['move_media'])
                self.assertFalse(options['require_smb'])
                self.assertIsNone(options['scope_dir'])
        self.assertEqual(self.config.read_bytes(), before)

    def test_legacy_folder_settings_do_not_restrict_single_file_drop(self):
        source = self.root / 'Anywhere.wav'
        source.write_bytes(b'synthetic media')
        settings = {**self.settings, 'input_dir': str(self.watched),
                    'completed_dir': str(self.watched / 'Archive')}
        settings.pop('folders')
        settings.pop('folder_options')
        plan = service.prepare_drop(self.db, settings, [str(source)])
        set_queue_paused(self.db, True)
        service.resolve_drop(self.db, plan['token'], 'immediate')
        with patch.object(service, 'inspect_folders_with_deadline', side_effect=service.inspect_folders):
            self.assertTrue(service.next_job(self.db, self.state, Mock(return_value='Result'),
                available_only=True, allow_automatic=False))
        self.assertEqual(source.with_suffix('.txt').read_text(), 'Result')
        self.assertTrue(queue_paused(self.db))
