import plistlib
import sqlite3
import sys
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch

if sys.platform == "darwin":
    import app_upgrade
import login_agent


@unittest.skipUnless(sys.platform == "darwin", "macOS profile migration")
class AppUpgradeTest(unittest.TestCase):
    def test_moves_support_and_updates_existing_login_registration(self):
        with (
            TemporaryDirectory() as directory,
            patch("pathlib.Path.home", return_value=Path(directory)) as home,
        ):
            support = home.return_value / "Library/Application Support/VoxDrop"
            previous = support.with_name(app_upgrade.PREVIOUS_NAME)
            app = home.return_value / "Applications/VoxDrop.app"
            config = previous / "config.json"
            state = previous / "service"
            state.mkdir(parents=True)
            config.write_text('{"folders":[]}')
            db = state / "jobs.sqlite3"
            with sqlite3.connect(db) as connection:
                connection.execute("CREATE TABLE jobs (id INTEGER)")
                connection.execute("INSERT INTO jobs VALUES (42)")
            agent = login_agent.agent_path().with_name(
                app_upgrade.PREVIOUS_LABEL + ".plist"
            )
            agent.parent.mkdir()
            agent.write_bytes(
                plistlib.dumps(
                    {
                        "Label": app_upgrade.PREVIOUS_LABEL,
                        "ProgramArguments": app_upgrade.worker_commands(app, previous)[
                            0
                        ],
                    }
                )
            )
            with patch("app_upgrade.launchctl", return_value=CompletedProcess([], 1)):
                self.assertFalse(app_upgrade.migrate(support, app))
                self.assertFalse(app_upgrade.migrate(support, app))
            self.assertEqual((support / config.name).read_text(), '{"folders":[]}')
            with sqlite3.connect(support / db.relative_to(previous)) as connection:
                self.assertEqual(
                    connection.execute("SELECT id FROM jobs").fetchall(), [(42,)]
                )
            registration = plistlib.loads(login_agent.agent_path().read_bytes())
            self.assertEqual(
                registration["ProgramArguments"],
                app_upgrade.worker_commands(app, support)[0],
            )
            self.assertEqual(
                registration["AssociatedBundleIdentifiers"],
                [login_agent.BUNDLE_IDENTIFIER],
            )
            self.assertFalse(previous.exists())
            self.assertFalse(agent.exists())

    def test_conflicting_data_is_not_replaced(self):
        with (
            TemporaryDirectory() as directory,
            patch("pathlib.Path.home", return_value=Path(directory)),
        ):
            support = Path(directory) / "VoxDrop"
            previous = support.with_name(app_upgrade.PREVIOUS_NAME)
            for path in (support, previous):
                path.mkdir()
                (path / "config.json").write_text(path.name)
            with self.assertRaisesRegex(ValueError, "zwei Ordner"):
                app_upgrade.migrate(support, Path(directory) / "VoxDrop.app")
            self.assertEqual((support / "config.json").read_text(), support.name)
            self.assertEqual((previous / "config.json").read_text(), previous.name)
