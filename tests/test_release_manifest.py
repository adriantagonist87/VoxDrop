import hashlib
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.verify_windows_release import verify


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.root=Path(folder.name);self.archive=self.root/'release.zip'
        self.app=self.root/'app';self.app.mkdir()
        (self.app/'program.py').write_bytes(b'verified program')
        with ZipFile(self.archive,'w') as zipped:zipped.writestr('VoxDrop/program.py',b'verified program')
        self.manifest=dict(code_commit='verified-source',archive_sha256=self.hash(self.archive),files=[
            dict(path='program.py',size=16,sha256=self.hash(self.app/'program.py'))])

    def hash(self,path):return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_matches_program_and_preserves_additional_local_data(self):
        (self.app/'config.json').write_text('local settings')
        self.assertTrue(verify(self.manifest,self.archive,self.app)['passed'])
        self.assertEqual((self.app/'config.json').read_text(),'local settings')

    def test_rejects_changed_installation(self):
        (self.app/'program.py').write_bytes(b'changed program!')
        with self.assertRaisesRegex(ValueError,'Installed file mismatch'):
            verify(self.manifest,installation=self.app)

    def test_file_hash_detects_repacked_payload_even_if_archive_digest_is_updated(self):
        with ZipFile(self.archive,'w') as zipped:zipped.writestr('VoxDrop/program.py',b'changed program!')
        self.manifest['archive_sha256']=self.hash(self.archive)
        with self.assertRaisesRegex(ValueError,'Packaged file mismatch'):
            verify(self.manifest,self.archive)

    def test_rejects_archive_traversal_before_reading_payload(self):
        with ZipFile(self.archive,'a') as zipped:zipped.writestr('VoxDrop/../escape',b'bad')
        self.manifest['archive_sha256']=self.hash(self.archive)
        with self.assertRaisesRegex(ValueError,'Unsafe archive member'):
            verify(self.manifest,self.archive)
