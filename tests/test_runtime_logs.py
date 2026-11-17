import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch
from pathlib import Path

from runtime_logs import RollingLog


class RuntimeLogTests(unittest.TestCase):
    def test_continuous_unicode_output_is_bounded_and_keeps_latest_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "service.log"
            log = RollingLog(path, max_bytes=1024, backups=2)
            try:
                for number in range(500):
                    log.write(f"{number}: künstliches Ereignis ÄÖÜ\n")
                log.write("Letztes Ereignis\n")
                log.flush()
            finally:
                log.close()
            files = list(path.parent.glob("service.log*"))
            self.assertLessEqual(len(files), 3)
            self.assertLessEqual(sum(p.stat().st_size for p in files), 3072)
            self.assertIn("Letztes Ereignis", path.read_text(encoding="utf-8"))

    def test_huge_single_message_cannot_grow_the_log_without_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "service.log"
            log = RollingLog(path, max_bytes=1024)
            try:
                log.write("ä" * 100_000)
            finally:
                log.close()
            self.assertLess(path.stat().st_size, 1024)
            self.assertIn("gekürzt", path.read_text(encoding="utf-8"))

    def test_log_write_failure_does_not_recurse_through_redirected_stderr(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = RollingLog(Path(temporary) / "service.log", max_bytes=1024)
            try:
                with redirect_stderr(log), patch.object(log.handler, "shouldRollover", side_effect=OSError("disk full")):
                    self.assertEqual(log.write("diagnostic"), 10)
            finally:
                log.close()
