import errno
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from watch_service import (
    database,
    initialise,
    inspect_folders,
    next_job,
    probe_pending_folders,
    read_settings,
    recover,
    rename_exclusive,
    retry,
)


class MultiFolderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.first = self.root / "Telefon"
        self.second = self.root / "Video"
        self.missing = self.root / "Unterbrochen"
        for folder in (self.first, self.second):
            folder.mkdir()
        self.state = self.root / "state"
        initialise(self.state)
        self.db = self.enterContext(closing(database(self.state)))
        self.engine = Mock(return_value="Testtranskript\n")
        self.deadlines = {}
        self.retries = {}

    def settings(self, *, subfolder=False):
        config = self.root / "config.json"
        config.write_text(
            json.dumps(
                {
                    "folders": [str(self.missing), str(self.first), str(self.second)],
                    "create_output_subfolder": subfolder,
                    "output_subfolder": "_FERTIGGESTELLT",
                    "monitoring": True,
                }
            )
        )
        return read_settings(config)

    def scan(self, settings, now, *, force=True):
        if force:
            self.deadlines.clear()
        with (
            patch(
                "watch_service.inspect_folders_with_deadline",
                side_effect=inspect_folders,
            ),
            patch("watch_service.time.time", return_value=now),
        ):
            return probe_pending_folders(
                self.db, settings, self.deadlines, self.retries
            )

    def test_folder_outage_leaves_other_jobs_running_and_each_pair_stays_in_its_own_archive(
        self,
    ):
        settings = self.settings(subfolder=True)
        for folder in (self.first, self.second):
            (folder / "Test.wav").write_bytes(b"media")
        self.assertTrue(self.scan(settings, 100))
        self.assertTrue(self.scan(settings, 130))
        self.assertFalse((self.first / "_FERTIGGESTELLT").exists())
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ):
            for _ in range(2):
                self.assertTrue(
                    next_job(self.db, self.state, self.engine, available_only=True)
                )
            self.assertFalse(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
        for folder in (self.first, self.second):
            self.assertFalse((folder / "Test.wav").exists())
            self.assertEqual(
                (folder / "_FERTIGGESTELLT/Test.wav").read_bytes(), b"media"
            )
            self.assertEqual(
                (folder / "_FERTIGGESTELLT/Test.txt").read_text(), "Testtranskript\n"
            )
        self.assertTrue(self.scan(settings, 160))
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM jobs WHERE state='done'").fetchone()[
                0
            ],
            2,
        )
        self.assertEqual(
            self.db.execute("SELECT available FROM connection").fetchone()[0], 0
        )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 2)

    def test_subfolder_conflict_preserves_recording_and_allows_export_retry(self):
        settings = self.settings(subfolder=True)
        source = self.first / "Test.wav"
        source.write_bytes(b"media")
        target = self.first / "_FERTIGGESTELLT"
        target.mkdir()
        media, text = target / source.name, target / "Test.txt"
        media.write_bytes(b"existing")
        self.scan(settings, 100)
        self.scan(settings, 130)
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ):
            self.assertTrue(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
            job = self.db.execute("SELECT id,state FROM jobs").fetchone()
            self.assertEqual(job["state"], "blocked")
            self.assertEqual(source.read_bytes(), b"media")
            self.assertEqual(media.read_bytes(), b"existing")
            self.assertFalse(text.exists())
            media.unlink()
            retry(self.db, job["id"])
            self.assertTrue(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
        self.engine.assert_called_once()
        self.assertFalse(source.exists())
        self.assertEqual(media.read_bytes(), b"media")
        self.assertEqual(text.read_text(), "Testtranskript\n")

    def test_subfolder_move_waits_for_verified_text_and_can_be_recovered(self):
        settings = self.settings(subfolder=True)
        source = self.first / "Test.wav"
        source.write_bytes(b"media")
        target = self.first / "_FERTIGGESTELLT"
        media, text = target / source.name, target / "Test.txt"
        self.scan(settings, 100)
        self.scan(settings, 130)

        def assert_text_and_move(origin, destination):
            if origin == source:
                self.assertEqual(text.read_text(), "Testtranskript\n")
            rename_exclusive(origin, destination)
            if origin == source:
                raise KeyboardInterrupt()

        with (
            patch(
                "watch_service.inspect_folders_with_deadline",
                side_effect=inspect_folders,
            ),
            patch("watch_service.rename_exclusive", side_effect=assert_text_and_move),
        ):
            with self.assertRaises(KeyboardInterrupt):
                next_job(self.db, self.state, self.engine, available_only=True)
            self.assertEqual(
                self.db.execute("SELECT state FROM jobs").fetchone()[0], "exporting"
            )
            recover(self.db, self.state)
        self.assertEqual(
            self.db.execute("SELECT state FROM jobs").fetchone()[0], "done"
        )
        self.assertFalse(source.exists())
        self.assertEqual(media.read_bytes(), b"media")
        self.engine.assert_called_once()

    def test_subfolder_fallback_leaves_source_in_place_if_txt_cannot_be_copied(self):
        settings = self.settings(subfolder=True)
        source = self.first / "Test.wav"
        source.write_bytes(b"media")
        target = self.first / "_FERTIGGESTELLT"
        self.scan(settings, 100)
        self.scan(settings, 130)
        with (
            patch(
                "watch_service.inspect_folders_with_deadline",
                side_effect=inspect_folders,
            ),
            patch(
                "watch_service.rename_exclusive",
                side_effect=OSError(errno.ENOTSUP, "unsupported"),
            ),
        ):
            with patch(
                "watch_service.copy_verified",
                side_effect=OSError(errno.EIO, "TXT nicht kopierbar"),
            ):
                self.assertTrue(
                    next_job(self.db, self.state, self.engine, available_only=True)
                )
            job = self.db.execute("SELECT id,state FROM jobs").fetchone()
            self.assertEqual(job["state"], "failed")
            self.assertEqual(source.read_bytes(), b"media")
            self.assertFalse((target / source.name).exists())
            retry(self.db, job["id"])
            self.assertTrue(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
        self.assertEqual(
            self.db.execute("SELECT state FROM jobs").fetchone()[0], "done"
        )
        self.assertFalse(source.exists())
        self.assertEqual((target / source.name).read_bytes(), b"media")
        self.assertEqual((target / "Test.txt").read_text(), "Testtranskript\n")
        self.engine.assert_called_once()

    def test_write_error_persists_as_one_incident_and_refresh_rechecks_only_the_requested_path(
        self,
    ):
        settings = self.settings()
        self.missing.mkdir()
        wav = self.first / "Test.wav"
        wav.write_bytes(b"media")

        def check(profile):
            if profile["watch_path"] == str(self.missing):
                raise OSError("Ordner nicht beschreibbar")
            return inspect_folders(profile)

        with patch("watch_service.inspect_folders_with_deadline", side_effect=check):
            probe_pending_folders(self.db, settings, {}, {})
            before = self.db.execute(
                "SELECT incident FROM folder_status WHERE path=?", (str(self.missing),)
            ).fetchone()[0]
            self.assertTrue(before)
            probe_pending_folders(self.db, settings, {}, {})
            self.assertEqual(
                self.db.execute(
                    "SELECT incident FROM folder_status WHERE path=?",
                    (str(self.missing),),
                ).fetchone()[0],
                before,
            )
        with self.db:
            self.db.execute(
                "INSERT INTO folder_refresh VALUES (?)", (str(self.missing),)
            )
        deadlines = dict.fromkeys(settings["folders"], float("inf"))
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ) as probe:
            probe_pending_folders(self.db, settings, deadlines, {})
            self.assertEqual(probe.call_count, 1)
            self.assertEqual(probe.call_args.args[0]["watch_path"], str(self.missing))
        recovered = self.db.execute(
            "SELECT available,incident FROM folder_status WHERE path=?",
            (str(self.missing),),
        ).fetchone()
        self.assertEqual(tuple(recovered), (1, None))

    def test_export_beside_source_does_not_recognize_the_same_version_again(self):
        settings = self.settings()
        (self.first / "Test.wav").write_bytes(b"media")
        self.scan(settings, 100)
        self.scan(settings, 130)
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ):
            self.assertTrue(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
            self.assertTrue((self.first / "Test.wav").is_file())
            self.assertTrue((self.first / "Test.txt").is_file())
            self.scan(settings, 160)
            self.assertFalse(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
        self.engine.assert_called_once()
