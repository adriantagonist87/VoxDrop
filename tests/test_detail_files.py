import json
from pathlib import Path
import tempfile
import unittest

from desktop.detail_files import locate_files


class DetailFileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "Original Ä, + Test.flv"
        self.archive = self.root / "Archiv"
        self.archive.mkdir()
        self.job = dict(id=42, source=str(self.source), completed_dir=str(self.source.parent),
                        state="failed", origin_job_id=None,
                        settings=json.dumps(dict(watch_path=str(self.root), move_media=False)))

    def test_original_is_available_for_every_history_state_without_a_transcript(self):
        self.source.write_bytes(b"synthetic original")
        for state in ("failed", "blocked", "cancelled", "superseded", "done", "existing", "duplicate"):
            with self.subTest(state=state):
                files = locate_files({**self.job, "state": state})
                self.assertTrue(files["originalAvailable"])
                self.assertEqual(files["original"], str(self.source.absolute()))
                self.assertFalse(files["transcriptAvailable"])

    def test_failed_job_can_still_open_an_existing_transcript(self):
        self.source.write_bytes(b"media")
        text = self.source.with_suffix(".txt")
        text.write_text("existing protected result")
        files = locate_files(self.job)
        self.assertTrue(files["transcriptAvailable"])
        self.assertEqual(files["transcript"], str(text.absolute()))

    def test_moved_media_is_preferred_after_success(self):
        self.source.write_bytes(b"different new file at original path")
        archived = self.archive / self.source.name
        archived.write_bytes(b"archived original")
        archived.with_suffix(".txt").write_text("result")
        job = {**self.job, "state": "done", "completed_dir": str(self.archive),
               "settings": json.dumps(dict(watch_path=str(self.root), move_media=True))}
        files = locate_files(job)
        self.assertEqual(files["original"], str(archived.absolute()))
        self.assertTrue(files["transcriptAvailable"])

    def test_retranscription_uses_its_own_text_and_archived_media_fallback(self):
        archived = self.archive / self.source.name
        archived.write_bytes(b"media")
        text = self.archive / f"{self.source.stem} (Neu 42).txt"
        text.write_text("new result")
        files = locate_files({**self.job, "origin_job_id": 1, "completed_dir": str(self.archive)})
        self.assertEqual(files["original"], str(archived.absolute()))
        self.assertEqual(files["transcript"], str(text.absolute()))
        self.assertTrue(files["transcriptAvailable"])

    def test_known_transcript_path_is_used_independently_of_job_state(self):
        known = self.root / "Vorhanden Ä.txt"
        known.write_text("existing result")
        files = locate_files({**self.job, "known_transcript_path": str(known)})
        self.assertEqual(files["transcript"], str(known.absolute()))
        self.assertTrue(files["transcriptAvailable"])

    def test_missing_files_and_directories_are_not_offered_as_files(self):
        self.source.mkdir()
        files = locate_files(self.job)
        self.assertFalse(files["originalAvailable"])
        self.assertFalse(files["transcriptAvailable"])
