import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import login_agent


class LoginAgentTests(unittest.TestCase):
    def test_configuration_roundtrips_and_disables_without_touching_foreign_plist(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "LaunchAgents" / (login_agent.LABEL + ".plist")
            config = login_agent.definition(
                root / "worker.py",
                root / "config.json",
                root / "state",
                root / "models",
            )
            with patch("login_agent.agent_path", return_value=path):
                login_agent.update(True, config)
                self.assertEqual(plistlib.loads(path.read_bytes()), config)
                self.assertTrue(config["RunAtLoad"])
                self.assertEqual(
                    config["AssociatedBundleIdentifiers"], ["local.smb-transcriber"]
                )
                login_agent.update(False, config)
                self.assertFalse(path.exists())
                legacy = {
                    key: value
                    for key, value in config.items()
                    if key != "AssociatedBundleIdentifiers"
                }
                path.write_bytes(plistlib.dumps(legacy))
                login_agent.update(False, config)
                self.assertFalse(path.exists())
                path.write_bytes(plistlib.dumps({"Label": "foreign"}))
                with self.assertRaises(ValueError):
                    login_agent.update(False, config)
                self.assertEqual(
                    plistlib.loads(path.read_bytes()), {"Label": "foreign"}
                )
