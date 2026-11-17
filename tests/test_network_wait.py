import unittest
import sys
import tempfile
from pathlib import Path
from subprocess import CompletedProcess
from threading import Event
from unittest.mock import Mock, patch

from desktop.network_wait import NetworkPermissionError, retry_network_permission


class NetworkWaitTests(unittest.TestCase):
    def test_actual_controller_command_handles_denial_without_traceback(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
        import controller

        with tempfile.TemporaryDirectory() as temporary, patch(
            "controller.DESKTOP_LOG", Path(temporary) / "desktop.log"
        ), patch("controller.subprocess.run", side_effect=[
            CompletedProcess([], 1, "", "Fehler: [WinError 10013] Socket access denied"),
            CompletedProcess([], 0, "verified", ""),
        ]) as process:
            self.assertEqual(controller.retry_network_permission(
                lambda: controller.command("setup-models"), Event(), Mock(), interval=0
            ), "verified")
        self.assertEqual(process.call_count, 2)

    def test_denied_download_is_retried_until_access_is_granted(self):
        operation = Mock(side_effect=[NetworkPermissionError("10013"),
                                      NetworkPermissionError("10013"), "verified"])
        waiting = Mock()
        self.assertEqual(retry_network_permission(operation, Event(), waiting, interval=0), "verified")
        self.assertEqual(operation.call_count, 3)
        self.assertEqual([c.args[0] for c in waiting.call_args_list], [True, True, False])

    def test_cancel_stops_retries_and_preserves_a_resumable_state(self):
        cancel = Event()
        operation = Mock(side_effect=NetworkPermissionError("10013"))
        waiting = Mock(side_effect=lambda value: cancel.set() if value else None)
        with self.assertRaisesRegex(RuntimeError, "abgebrochen"):
            retry_network_permission(operation, cancel, waiting, interval=0)
        operation.assert_called_once()
        self.assertEqual(waiting.call_args.args, (False,))

    def test_other_failures_are_not_misreported_as_firewall_waits(self):
        operation = Mock(side_effect=ValueError("checksum mismatch"))
        waiting = Mock()
        with self.assertRaisesRegex(ValueError, "checksum"):
            retry_network_permission(operation, Event(), waiting, interval=0)
        operation.assert_called_once()
        waiting.assert_called_once_with(False)
