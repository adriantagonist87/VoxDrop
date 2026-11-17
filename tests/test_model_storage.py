import os
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop.model_storage import data_directory


class ModelStorageTests(unittest.TestCase):
    def test_installed_mac_downloads_beside_the_signed_bundle(self):
        profile = Path("/Users/test/Library/Application Support/VoxDrop")
        resources = Path("/Applications/VoxDrop/VoxDrop.app/Contents/Resources")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(data_directory(profile, resources), Path("/Applications/VoxDrop/Modelle"))

    def test_isolated_profile_and_explicit_store_remain_independent(self):
        profile = Path(tempfile.gettempdir()) / "voxdrop-trial"
        resources = Path("/Applications/VoxDrop/VoxDrop.app/Contents/Resources")
        with patch.dict(os.environ, {"VOXDROP_PROFILE": str(profile)}, clear=True):
            self.assertEqual(data_directory(profile, resources), profile / "data")
            target = profile / "installation/Modelle"
            with patch.dict(os.environ, {"VOXDROP_MODEL_DATA": str(target)}):
                self.assertEqual(data_directory(profile, resources), target)

    def test_source_and_windows_keep_the_profile_store(self):
        profile = Path(tempfile.gettempdir()) / "voxdrop-user"
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(data_directory(profile, Path("source")), profile / "data")

    def test_windows_package_keeps_models_and_cache_beside_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "VoxDrop"
            (app / "windows").mkdir(parents=True)
            (app / "VoxDrop.exe").touch()
            (app / "windows/uv.lock").touch()
            profile = Path(temporary) / "profile"
            with patch("desktop.model_storage.sys.platform", "win32"), patch.dict(
                os.environ, {"VOXDROP_PROFILE": str(profile)}, clear=True
            ):
                self.assertEqual(data_directory(profile, app), app / "Modelle")
                explicit = Path(temporary) / "explicit-model-test"
                with patch.dict(os.environ, {"VOXDROP_MODEL_DATA": str(explicit)}):
                    self.assertEqual(data_directory(profile, app), explicit)


@unittest.skipUnless(sys.platform == "darwin", "macOS installation")
class ModelMigrationTests(unittest.TestCase):
    def test_failed_bundle_replacement_restores_app_and_models(self):
        from macos.install import install

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Source/VoxDrop.app"
            applications = root / "Applications"
            legacy = applications / "VoxDrop.app"
            profile = root / "profile"
            for bundle, marker in ((source, "new"), (legacy, "old")):
                (bundle / "Contents").mkdir(parents=True)
                (bundle / "Contents/Info.plist").write_bytes(
                    plistlib.dumps({"CFBundleIdentifier": "local.voxdrop"})
                )
                (bundle / "Contents/marker").write_text(marker)
            models = profile / "data"
            models.mkdir(parents=True)
            (models / "weights").write_bytes(b"model")

            def run(*args):
                if str(args[0]) == "/usr/bin/ditto":
                    import shutil
                    shutil.copytree(args[1], args[2])
                return ""

            rename = Path.rename

            def fail_new_bundle(path, target):
                if path.name == "VoxDrop.app" and path.parent.name.startswith(".voxdrop-install-"):
                    raise OSError("simulated replacement failure")
                return rename(path, target)

            with (
                patch("macos.install.execute", side_effect=run),
                patch("macos.install.processes", return_value={}),
                patch.object(Path, "rename", fail_new_bundle),
            ):
                with self.assertRaisesRegex(OSError, "simulated replacement"):
                    install(source, applications, profile)
            self.assertEqual((legacy / "Contents/marker").read_text(), "old")
            self.assertFalse(models.is_symlink())
            self.assertEqual((models / "weights").read_bytes(), b"model")

    def test_migration_leaves_model_bytes_only_in_application_folder(self):
        from macos.install import migrate_models

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile"
            previous = profile / "data"
            previous.mkdir(parents=True)
            (previous / "weights").write_bytes(b"model")
            target = root / "VoxDrop/Modelle"
            target.parent.mkdir()
            self.assertTrue(migrate_models(profile, target))
            self.assertTrue(previous.is_symlink())
            self.assertEqual((target / "weights").read_bytes(), b"model")
            self.assertFalse(migrate_models(profile, target))
            (target / "weights").unlink()
            target.rmdir()
            self.assertFalse((previous / "weights").exists())

    def test_conflicting_model_store_preserves_both_sources(self):
        from macos.install import migrate_models

        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile"
            old = profile / "data"
            target = Path(directory) / "VoxDrop/Modelle"
            for folder, content in ((old, b"old"), (target, b"new")):
                folder.mkdir(parents=True)
                (folder / "weights").write_bytes(content)
            with self.assertRaises(ValueError):
                migrate_models(profile, target)
            self.assertEqual((old / "weights").read_bytes(), b"old")
            self.assertEqual((target / "weights").read_bytes(), b"new")
