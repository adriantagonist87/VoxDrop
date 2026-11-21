import errno
import json
import os
import subprocess
import tempfile
import unittest
from platform_io import WINDOWS
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from smb_paths import resolve_folder
from voxdrop import DEFAULT_MODEL, WHISPER_MODEL
from watch_service import (
    active_folders,
    clear_history,
    copy_verified,
    database,
    history_jobs,
    initialise,
    next_job,
    poll_config,
    read_settings,
    recover,
    retranscribe,
    retry,
    scan,
    scan_once,
    targets,
)

TRANSCRIPT = "[00:00:00] Sprecher 1: Grüße!\n"


class WatchServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.state = self.root / "state"
        self.incoming = self.root / "EINGANG"
        self.completed = self.root / "FERTIGGESTELLT"
        self.incoming.mkdir()
        self.completed.mkdir()
        initialise(self.state)
        self.db = database(self.state)
        self.addCleanup(self.db.close)
        config = self.root / "test.json"
        config.write_text(
            json.dumps(
                {
                    "input_dir": str(self.incoming),
                    "completed_dir": str(self.completed),
                    "monitoring": True,
                    "language": "de",
                    "speaker_count": 2,
                }
            )
        )
        self.settings = read_settings(config)
        self.engine = Mock(return_value=TRANSCRIPT)
        self.source = self.incoming / "Grüße Ä.mp4"
        self.source.write_bytes(b"synthetic media bytes")
        self.media = self.completed / self.source.name
        self.text = self.media.with_suffix(".txt")

    def job(self):
        return self.db.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 1").fetchone()

    def scan(self, now):
        scan(self.db, self.settings, now)

    def queue(self):
        self.scan(100)
        self.scan(130)

    def test_waits_full_interval_and_moves_media_once(self):
        self.scan(100)
        self.scan(129)
        self.assertFalse(next_job(self.db, self.state, self.engine))
        self.assertEqual(self.job()["state"], "seen")
        self.scan(130)
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertFalse(self.source.exists())
        self.assertEqual(self.media.read_bytes(), b"synthetic media bytes")
        self.assertEqual(self.text.read_text(encoding="utf-8"), TRANSCRIPT)
        call = self.engine.call_args
        self.assertTrue(call.args[0].is_relative_to(self.state / "jobs"))
        self.assertFalse(call.args[0].exists())
        self.assertEqual(call.kwargs["language"], "de")
        self.assertEqual(call.kwargs["model"], DEFAULT_MODEL)
        self.assertFalse(call.kwargs["skip_silence"])
        self.assertEqual(call.kwargs["speaker_count"], 2)
        with closing(database(self.state)) as reopened:
            recover(reopened, self.state)
            scan(reopened, self.settings, 200)
            self.assertFalse(next_job(reopened, self.state, self.engine))
        self.engine.assert_called_once()
        self.assertEqual(self.job()["state"], "done")
        states = [r[0] for r in self.db.execute("SELECT state FROM events ORDER BY id")]
        self.assertEqual(
            states, ["seen", "ready", "copying", "transcribing", "exporting", "done"]
        )

    def test_model_choice_is_preserved_per_discovered_file(self):
        self.scan(100)
        self.settings["model"] = WHISPER_MODEL
        self.settings["skip_silence"] = True
        second = self.incoming / "Weiterer Test.wav"
        second.write_bytes(b"synthetic next media")
        self.scan(130)
        self.scan(160)
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(
            [call.kwargs["model"] for call in self.engine.call_args_list],
            [DEFAULT_MODEL, WHISPER_MODEL],
        )
        self.assertEqual(
            [call.kwargs["skip_silence"] for call in self.engine.call_args_list],
            [False, True],
        )

    def test_legacy_job_without_stored_model_uses_whisper(self):
        self.queue()
        stored = json.loads(self.job()["settings"])
        stored.pop("model")
        with self.db:
            self.db.execute("UPDATE jobs SET settings=?", (json.dumps(stored),))
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(self.engine.call_args.kwargs["model"], WHISPER_MODEL)

    def test_retranscription_uses_current_settings_and_keeps_the_archived_original(
        self,
    ):
        self.queue()
        self.assertTrue(next_job(self.db, self.state, self.engine))
        first = self.job()["id"]
        current = {
            **self.settings,
            "model": WHISPER_MODEL,
            "speaker_count": 3,
            "dover_lap": True,
        }
        second = retranscribe(self.db, first, current)
        self.assertGreater(second, first)
        with self.assertRaisesRegex(ValueError, "bereits"):
            retranscribe(self.db, first, current)

        engine = Mock(return_value="Neues Transkript\n")
        self.assertTrue(
            next_job(
                self.db, self.state, engine, available_only=True, allow_automatic=False
            )
        )
        self.assertEqual(self.job()["origin_job_id"], first)
        self.assertEqual(self.job()["state"], "done")
        self.assertEqual(engine.call_args.kwargs["model"], WHISPER_MODEL)
        self.assertEqual(engine.call_args.kwargs["speaker_count"], 3)
        self.assertTrue(engine.call_args.kwargs["dover_lap"])
        self.assertEqual(self.text.read_text(), TRANSCRIPT)
        self.assertEqual(targets(self.job())[1].read_text(), "Neues Transkript\n")
        self.assertEqual(self.media.read_bytes(), b"synthetic media bytes")
        self.assertEqual(
            self.db.execute("SELECT state FROM jobs WHERE id=?", (first,)).fetchone()[
                0
            ],
            "done",
        )

    def test_clear_history_resets_known_versions_and_preserves_media_and_exports(self):
        self.queue()
        first = self.job()["id"]
        with self.db:
            self.db.execute("UPDATE jobs SET state='copying' WHERE id=?", (first,))
        with self.assertRaisesRegex(ValueError, "aktiven Auftrags"):
            clear_history(self.db, self.state)
        self.assertIsNotNone(self.job())
        with self.db:
            self.db.execute("UPDATE jobs SET state='ready' WHERE id=?", (first,))

        previous_export = self.completed / "Vorhanden.txt"
        previous_export.write_text("Unabhängiges Transkript")
        local_cache = self.state / "jobs" / str(first)
        local_cache.mkdir(parents=True)
        (local_cache / "transcript.txt").write_text("Cache")
        clear_history(self.db, self.state)
        self.assertIsNone(self.job())
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0
        )
        self.assertFalse(local_cache.exists())
        self.assertEqual(previous_export.read_text(), "Unabhängiges Transkript")
        self.assertEqual(self.source.read_bytes(), b"synthetic media bytes")
        self.scan(200)
        self.assertGreater(self.job()["id"], first)
        self.assertEqual(self.job()["state"], "seen")

    def test_dover_mode_with_a_fixed_count_and_result_visible_in_history(self):
        self.settings["dover_lap"] = True
        self.queue()

        def engine(_media, *, measurements, dover_lap, speaker_count, **_):
            self.assertTrue(dover_lap)
            self.assertEqual(speaker_count, 2)
            measurements["speaker_details"] = {
                "method": "single-fallback",
                "passes": 3,
                "note": "Fusion ergab 3 Sprecher.",
            }
            return TRANSCRIPT

        self.assertTrue(next_job(self.db, self.state, engine))
        job = history_jobs(self.db, "desc", 1)[0]
        self.assertEqual(job["speaker_method"], "single-fallback")
        self.assertEqual(job["speaker_passes"], 3)
        self.assertEqual(job["speaker_note"], "Fusion ergab 3 Sprecher.")

    def test_changed_source_restarts_stability_window(self):
        self.scan(100)
        self.source.write_bytes(b"modified and longer")
        self.scan(130)
        self.assertEqual(self.job()["state"], "seen")
        self.assertFalse(next_job(self.db, self.state, self.engine))
        self.scan(160)
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.engine.assert_called_once()
        self.assertEqual(self.media.read_bytes(), b"modified and longer")

    def test_source_changed_after_ready_is_scanned_as_a_new_version(self):
        self.queue()
        self.source.write_bytes(b"new version before staging")
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(self.job()["state"], "superseded")
        self.engine.assert_not_called()

        self.scan(131)
        self.assertEqual(self.job()["state"], "seen")
        self.assertFalse(next_job(self.db, self.state, self.engine))
        self.scan(161)
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.engine.assert_called_once()
        self.assertEqual(self.media.read_bytes(), b"new version before staging")

    def test_collision_leaves_source_and_cached_transcript_for_manual_retry(self):
        self.text.write_text("Existing text", encoding="utf-8")
        self.queue()
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(self.job()["state"], "blocked")
        self.assertTrue(self.source.exists())
        self.assertFalse(self.media.exists())
        self.assertEqual(self.text.read_text(), "Existing text")
        self.scan(200)
        self.assertFalse(next_job(self.db, self.state, self.engine))
        self.text.unlink()
        retry(self.db, self.job()["id"])
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(self.job()["state"], "done")
        self.assertEqual(self.job()["attempt"], 2)
        self.engine.assert_called_once()

    def test_failed_media_rename_can_resume_without_another_transcription(self):
        from watch_service import rename_exclusive

        def denied(source, target):
            if source == self.source:
                raise OSError(errno.EIO, "disconnected")
            rename_exclusive(source, target)

        self.queue()
        with patch("watch_service.rename_exclusive", side_effect=denied):
            next_job(self.db, self.state, self.engine)
        self.assertTrue(self.source.exists())
        self.assertEqual(self.text.read_text(), TRANSCRIPT)
        self.assertEqual(self.job()["state"], "failed")
        retry(self.db, self.job()["id"])
        next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "done")
        self.engine.assert_called_once()

    def test_history_uses_actual_transcription_event_and_keeps_export_retry_metrics(
        self,
    ):
        def measured_engine(_media, *, measurements, **_):
            measurements.update(
                speech_seconds=2.0,
                speaker_seconds=1.0,
                peak_memory_bytes=4096,
                audio_seconds=9.5,
            )
            return TRANSCRIPT

        self.text.write_text("Vorhandenes Ziel", encoding="utf-8")
        self.queue()
        self.assertTrue(next_job(self.db, self.state, measured_engine))
        first = history_jobs(self.db, "desc", 1)[0]
        self.assertEqual(first["state"], "blocked")
        self.assertGreaterEqual(first["transcription_started"], first["started"])
        self.assertEqual(first["speech_seconds"], 2.0)

        self.text.unlink()
        retry(self.db, first["id"])
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.engine.assert_not_called()
        final = history_jobs(self.db, "desc", 1)[0]
        self.assertEqual(final["state"], "done")
        self.assertEqual(final["transcription_started"], first["transcription_started"])
        self.assertEqual(final["speaker_seconds"], 1.0)
        self.assertEqual(final["peak_memory_bytes"], 4096)
        self.assertEqual(final["audio_seconds"], 9.5)

    def test_history_sorts_before_the_limit_and_keeps_legacy_measurements_empty(self):
        self.scan(100)
        one = self.job()["id"]
        second = self.incoming / "Spätere Datei.wav"
        second.write_bytes(b"new test media")
        self.scan(101)
        two = self.job()["id"]
        self.assertEqual(history_jobs(self.db, "asc", 1)[0]["id"], one)
        self.assertEqual(history_jobs(self.db, "desc", 1)[0]["id"], two)
        legacy = history_jobs(self.db, "asc", 1)[0]
        self.assertIsNone(legacy["peak_memory_bytes"])
        self.assertIsNone(legacy["speech_seconds"])
        self.assertIsNone(legacy["audio_seconds"])

    def test_recovery_recognises_verified_pair_after_completed_move(self):
        self.queue()
        next_job(self.db, self.state, self.engine)
        with self.db:
            self.db.execute(
                "UPDATE jobs SET state='exporting' WHERE id=?", (self.job()["id"],)
            )
        recover(self.db, self.state)
        self.assertEqual(self.job()["state"], "done")
        self.assertFalse(next_job(self.db, self.state, self.engine))

    def test_recovery_automatically_resumes_interrupted_transcription(self):
        self.queue()
        with self.db:
            self.db.execute("UPDATE jobs SET state='transcribing',attempt=1")
        recover(self.db, self.state)
        self.assertEqual(self.job()["state"], "ready")
        self.assertIsNone(self.job()["finished"])
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(self.job()["state"], "done")
        self.assertEqual(self.media.read_bytes(), b"synthetic media bytes")
        self.engine.assert_called_once()

    def test_recovery_resumes_cached_export_without_recognizing_again(self):
        self.queue()
        with patch("watch_service.publish_job", side_effect=OSError("interrupted export")):
            next_job(self.db, self.state, self.engine)
        with self.db:
            self.db.execute("UPDATE jobs SET state='exporting'")
        recover(self.db, self.state)
        self.assertEqual(self.job()["state"], "ready")
        next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "done")
        self.engine.assert_called_once()

    def test_transient_io_failure_retries_automatically_after_backoff(self):
        self.queue()
        self.engine.side_effect = [OSError(errno.EBUSY, "file temporarily locked"), TRANSCRIPT]
        next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "failed")
        self.assertFalse(next_job(self.db, self.state, self.engine))
        with self.db:
            self.db.execute("UPDATE job_retries SET retry_at=0")
        self.assertTrue(next_job(self.db, self.state, self.engine))
        self.assertEqual(self.job()["state"], "done")
        self.assertFalse(self.db.execute("SELECT 1 FROM job_retries").fetchone())
        self.assertEqual(self.engine.call_count, 2)

    def test_transient_export_retry_keeps_cached_text(self):
        self.queue()
        with patch("watch_service.publish_job", side_effect=OSError(errno.ETIMEDOUT, "SMB timeout")):
            next_job(self.db, self.state, self.engine)
        with self.db:
            self.db.execute("UPDATE job_retries SET retry_at=0")
        next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "done")
        self.engine.assert_called_once()

    def test_permanent_asr_error_does_not_enter_automatic_retry_loop(self):
        self.queue()
        self.engine.side_effect = RuntimeError("invalid recording")
        next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "failed")
        self.assertFalse(self.db.execute("SELECT 1 FROM job_retries").fetchone())

    @unittest.skipUnless(WINDOWS, "Windows CRT sharing lock")
    def test_windows_crt_lock_without_winerror_is_retried(self):
        self.queue()
        self.engine.side_effect = [PermissionError(errno.EACCES, "sharing lock"), TRANSCRIPT]
        next_job(self.db, self.state, self.engine)
        self.assertTrue(self.db.execute("SELECT 1 FROM job_retries").fetchone())
        with self.db:
            self.db.execute("UPDATE job_retries SET retry_at=0")
        next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "done")

    def test_unavailable_folder_is_a_service_status_then_recovers(self):
        moved = self.root / "offline"
        self.completed.rename(moved)
        self.assertFalse(scan_once(self.db, self.settings))
        self.assertEqual(
            self.db.execute("SELECT state FROM service").fetchone()[0], "unavailable"
        )
        self.assertIsNone(self.job())
        moved.rename(self.completed)
        self.assertTrue(scan_once(self.db, self.settings))
        self.assertEqual(
            self.db.execute("SELECT state FROM service").fetchone()[0], "active"
        )
        self.assertEqual(self.job()["state"], "seen")

    def test_connection_is_checked_while_monitoring_is_paused(self):
        settings = {**self.settings, "monitoring": False}
        self.assertTrue(scan_once(self.db, settings))
        self.assertEqual(
            self.db.execute("SELECT available FROM connection").fetchone()[0], 1
        )
        self.completed.rmdir()
        self.assertFalse(scan_once(self.db, settings))
        self.assertEqual(
            self.db.execute("SELECT available FROM connection").fetchone()[0], 0
        )
        self.assertEqual(
            self.db.execute("SELECT state FROM service").fetchone()[0], "paused"
        )
        self.assertIsNone(self.job())

    def test_blocked_folder_probe_marks_connection_unavailable(self):
        with patch(
            "watch_service.subprocess.run",
            side_effect=subprocess.TimeoutExpired("inspect-folders", 8),
        ):
            self.assertFalse(scan_once(self.db, self.settings))
        available, error = self.db.execute(
            "SELECT available,error FROM connection"
        ).fetchone()
        self.assertEqual(available, 0)
        self.assertIn("Zeitlimit", error)
        self.assertIsNone(self.job())

    def test_startup_checks_follow_10_30_60_then_normal_interval(self):
        def startup_checks(first_success):
            elapsed = 0
            attempts = []

            def wait(seconds):
                nonlocal elapsed
                elapsed += seconds

            def check(*_):
                attempts.append(elapsed)
                return elapsed == first_success

            stop = Mock()
            stop.is_set.side_effect = lambda: elapsed > 130
            stop.wait.side_effect = wait
            with (
                patch("watch_service.read_settings", return_value=self.settings),
                patch("watch_service.scan_once", side_effect=check),
                patch("watch_service.time.monotonic", side_effect=lambda: elapsed),
            ):
                poll_config(self.db, self.root / "test.json", stop, Mock())
            return attempts

        self.assertEqual(startup_checks(None), [0, 10, 40, 100, 130])
        self.assertEqual(startup_checks(10), [0, 10, 40, 70, 100, 130])

    def test_scan_ignores_symlinks_hidden_partials_and_txt(self):
        (self.incoming / ".temp.wav").write_bytes(b"partial")
        (self.incoming / "recording.wav.partial").write_bytes(b"partial")
        (self.incoming / "recording.txt").write_text("transcript")
        self.queue()
        self.assertEqual(
            self.db.execute("SELECT source FROM jobs").fetchall()[0][0],
            str(self.source),
        )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)

    def test_scan_ignores_symlinks(self):
        try:
            os.symlink(self.source, self.incoming / "link.mp4")
        except OSError as error:
            if getattr(error, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege is unavailable (WinError 1314)")
            raise
        self.queue()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)

    def test_unsupported_exclusive_rename_copies_and_verifies_before_removing_input(
        self,
    ):
        self.queue()
        with patch(
            "watch_service.rename_exclusive",
            side_effect=OSError(errno.ENOTSUP, "unsupported"),
        ):
            next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "done")
        self.assertEqual(self.media.read_bytes(), b"synthetic media bytes")
        self.assertEqual(self.text.read_text(), TRANSCRIPT)
        self.assertEqual(list(self.incoming.iterdir()), [])

    def test_changed_destination_during_text_export_keeps_original(self):
        def copy_with_concurrent_change(db, job_id, source, target, expected):
            copy_verified(db, job_id, source, target, expected)
            if target == self.text:
                self.media.write_bytes(b"changed by another SMB client")

        self.queue()
        with (
            patch(
                "watch_service.rename_exclusive",
                side_effect=OSError(errno.ENOTSUP, "unsupported"),
            ),
            patch(
                "watch_service.copy_verified", side_effect=copy_with_concurrent_change
            ),
        ):
            self.assertTrue(next_job(self.db, self.state, self.engine))

        self.assertEqual(self.job()["state"], "failed")
        self.assertIn(
            "Zielkopie wurde während des TXT-Exports verändert", self.job()["error"]
        )
        self.assertEqual(self.source.read_bytes(), b"synthetic media bytes")
        self.assertEqual(self.media.read_bytes(), b"changed by another SMB client")

    def test_interrupted_copy_resumes_own_prefix_without_another_transcription(self):
        def write_prefix(reader, writer, length):
            writer.write(reader.read(7))
            raise OSError(errno.EIO, "test interruption")

        def copy_with_interrupt(db, job_id, source, target, expected):
            if target == self.media:
                with patch(
                    "watch_service.shutil.copyfileobj", side_effect=write_prefix
                ):
                    return copy_verified(db, job_id, source, target, expected)
            return copy_verified(db, job_id, source, target, expected)

        self.queue()
        with (
            patch(
                "watch_service.rename_exclusive",
                side_effect=OSError(errno.ENOTSUP, "unsupported"),
            ),
            patch("watch_service.copy_verified", side_effect=copy_with_interrupt),
        ):
            next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "failed")
        self.assertTrue(self.source.exists())
        self.assertEqual(self.media.read_bytes(), b"synthet")
        self.assertFalse(self.text.exists())
        retry(self.db, self.job()["id"])
        next_job(self.db, self.state, self.engine)
        self.assertEqual(self.job()["state"], "done")
        self.assertEqual(self.media.read_bytes(), b"synthetic media bytes")
        self.assertEqual(self.text.read_text(), TRANSCRIPT)
        self.engine.assert_called_once()

    def test_custom_scope_rejects_a_directory_outside_it(self):
        with self.assertRaisesRegex(ValueError, "Arbeitsbereichs"):
            active_folders({**self.settings, "scope_dir": str(self.completed)})

    @patch("smb_paths.WINDOWS", False)
    def test_smb_uri_resolves_mount_without_accepting_credentials_or_traversal(self):
        mounts = [("nas.example", "share", self.root)]
        self.assertEqual(
            resolve_folder("smb://nas.example/share/EINGANG", mounts, require_smb=True),
            self.incoming,
        )
        with self.assertRaises(ValueError):
            resolve_folder(
                "smb://account@nas.example/share/EINGANG", mounts, require_smb=True
            )
        with self.assertRaises(ValueError):
            resolve_folder("smb://nas.example/share/%2e%2e", mounts, require_smb=True)


if __name__ == "__main__":
    unittest.main()
