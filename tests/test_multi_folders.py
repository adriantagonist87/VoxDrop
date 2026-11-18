import errno
import json
import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from watch_service import (
    database,
    enqueue_folders,
    initialise,
    inspect_folders,
    next_job,
    probe_pending_folders,
    read_settings,
    recover,
    rename_exclusive,
    reserve_archive_export,
    retry,
)


class MultiFolderTests(unittest.TestCase):
    def test_opus_folder_drop_is_processed_beside_unchanged_original(self):
        source = self.first / "Besprechung.OPUS"
        source.write_bytes(b"media-discovery-fixture")
        (self.first / "Notiz.json").write_text("{}")
        settings = self.settings(subfolder=True)
        queued = enqueue_folders(self.db, settings, [str(self.first)])
        self.assertEqual(queued["queued"], 1)
        with patch("watch_service.inspect_folders_with_deadline", side_effect=inspect_folders):
            self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(source.read_bytes(), b"media-discovery-fixture")
        self.assertEqual(source.with_suffix(".txt").read_text(), "Testtranskript\n")
        self.assertFalse((self.first / "_FERTIGGESTELLT").exists())

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

    def settings(self, *, subfolder=False, recursive=False):
        config = self.root / "config.json"
        config.write_text(
            json.dumps(
                {
                    "folders": [str(self.missing), str(self.first), str(self.second)],
                    "include_subfolders": recursive,
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

    def test_recursive_scan_exports_each_transcript_beside_its_media(self):
        lesson = self.first / "Schulung" / "Modul"
        lesson.mkdir(parents=True)
        outside = self.root / "Extern"
        outside.mkdir()
        (outside / "Extern.wav").write_bytes(b"outside")
        sources = {
            self.first / "Video.wav": b"root",
            lesson / "Video.wav": b"lesson",
            self.second / "Video.wav": b"other",
        }
        for source, content in sources.items():
            source.write_bytes(content)

        self.scan(self.settings(), 100)
        self.assertIsNone(
            self.db.execute(
                "SELECT 1 FROM jobs WHERE source=?", (str(lesson / "Video.wav"),)
            ).fetchone()
        )
        settings = self.settings(subfolder=True, recursive=True)
        self.assertFalse(settings["create_output_subfolder"])
        self.scan(settings, 130)
        self.scan(settings, 160)
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ):
            for _ in sources:
                self.assertTrue(
                    next_job(self.db, self.state, self.engine, available_only=True)
                )
            self.scan(settings, 190)
            self.assertFalse(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
        for source, content in sources.items():
            self.assertEqual(source.read_bytes(), content)
            self.assertEqual(source.with_suffix(".txt").read_text(), "Testtranskript\n")
            self.assertFalse((source.parent / "_FERTIGGESTELLT").exists())
        self.assertFalse((outside / "Extern.txt").exists())
        self.assertFalse((lesson / "Link.txt").exists())
        self.assertEqual(self.engine.call_count, len(sources))

    def test_recursive_scan_ignores_symlinked_files_and_directories(self):
        outside = self.root / "Extern"
        outside.mkdir()
        (outside / "Extern.wav").write_bytes(b"outside")
        try:
            (self.first / "Verweis").symlink_to(outside, target_is_directory=True)
            (self.first / "Link.wav").symlink_to(outside / "Extern.wav")
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege is unavailable (WinError 1314)")
            raise
        settings = self.settings(recursive=True)
        self.scan(settings, 100)
        self.scan(settings, 130)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_unreadable_subfolder_leaves_readable_siblings_eligible(self):
        inaccessible = self.first / "Gesperrt"
        readable = self.first / "Erreichbar"
        for folder in (inaccessible, readable):
            folder.mkdir()
            (folder / "Modul.wav").write_bytes(b"media")
        scandir = os.scandir

        def check_access(path):
            if path == inaccessible:
                raise PermissionError(errno.EACCES, "Zugriff verweigert", str(path))
            return scandir(path)

        settings = self.settings(recursive=True)
        with patch("watch_service.os.scandir", side_effect=check_access):
            self.scan(settings, 100)
            self.scan(settings, 130)
        row = self.db.execute(
            "SELECT available,error FROM folder_status WHERE path=?", (str(self.first),)
        ).fetchone()
        self.assertEqual(row["available"], 1)
        self.assertIn(repr(str(inaccessible)), row["error"])
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ):
            self.assertTrue(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
        self.assertTrue((readable / "Modul.txt").is_file())
        self.assertFalse((inaccessible / "Modul.txt").exists())

    def test_enabling_recursive_mode_retargets_active_and_queued_archive_jobs(self):
        sources = [self.first / "Teil 1.wav", self.first / "Teil 2.wav"]
        for source in sources:
            source.write_bytes(b"media")
        settings = self.settings(subfolder=True)
        self.scan(settings, 100)
        self.scan(settings, 130)

        def enable_recursion(*args, **kwargs):
            self.settings(subfolder=True, recursive=True)
            return self.engine(*args, **kwargs)

        config = self.root / "config.json"
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ):
            self.assertTrue(
                next_job(
                    self.db, self.state, enable_recursion, available_only=True, config=config
                )
            )
            self.assertTrue(
                next_job(
                    self.db, self.state, self.engine, available_only=True, config=config
                )
            )
        for source in sources:
            self.assertEqual(source.read_bytes(), b"media")
            self.assertEqual(source.with_suffix(".txt").read_text(), "Testtranskript\n")
        self.assertFalse((self.first / "_FERTIGGESTELLT").exists())
        self.assertEqual(self.engine.call_count, 2)

    def test_dropped_folders_run_once_when_monitoring_is_paused(self):
        dropped = self.root / "Schulungen"
        nested = dropped / "Kurs" / "Modul"
        nested.mkdir(parents=True)
        source = nested / "Lektion.wav"
        source.write_bytes(b"media")
        settings = self.settings(subfolder=True)
        settings["monitoring"] = False
        config = self.root / "config.json"
        before = config.read_bytes()
        with patch(
            "watch_service.inspect_folders_with_deadline", side_effect=inspect_folders
        ):
            result = enqueue_folders(self.db, settings, [str(dropped), str(nested)])
            self.assertEqual((result["queued"], result["skipped"]), (1, 1))
            self.assertTrue(result["pending"])
            self.assertFalse(result["warnings"])
            self.assertTrue(
                next_job(
                    self.db, self.state, self.engine,
                    available_only=True, allow_automatic=False,
                )
            )
            (nested / "Später.wav").write_bytes(b"later")
            self.scan(settings, 160)
            self.assertFalse(
                next_job(
                    self.db, self.state, self.engine,
                    available_only=True, allow_automatic=False,
                )
            )
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(source.read_bytes(), b"media")
        self.assertEqual(source.with_suffix(".txt").read_text(), "Testtranskript\n")
        self.assertFalse((nested / "Später.txt").exists())
        self.assertFalse((nested / "_FERTIGGESTELLT").exists())

    def test_folder_drop_preempts_archive_before_publication(self):
        archive = self.settings(subfolder=True)
        queued = self.first / "Wartend.wav"
        active = self.first / "Aktiv.wav"
        for source in (queued, active):
            source.write_bytes(b"media")
        self.scan(archive, 100)
        self.scan(archive, 130)

        def drop_before_export(db, job):
            report = enqueue_folders(db, archive, [str(self.first)])
            self.assertEqual(report["queued"], 2)
            return reserve_archive_export(db, job)

        with (
            patch("watch_service.inspect_folders_with_deadline", side_effect=inspect_folders),
            patch("watch_service.reserve_archive_export", side_effect=drop_before_export) as reserve,
        ):
            self.assertTrue(
                next_job(self.db, self.state, self.engine, available_only=True)
            )
            self.assertTrue(
                next_job(
                    self.db, self.state, self.engine,
                    available_only=True, allow_automatic=False,
                )
            )
            reserve.assert_called_once()
        for source in (queued, active):
            self.assertEqual(source.read_bytes(), b"media")
            self.assertEqual(source.with_suffix(".txt").read_text(), "Testtranskript\n")
        self.assertFalse((self.first / "_FERTIGGESTELLT").exists())
        self.assertEqual(self.db.execute("SELECT count(*) FROM jobs").fetchone()[0], 2)
