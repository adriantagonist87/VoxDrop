import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from smb_paths import resolve_folder, smb_address


class WindowsSMBTests(unittest.TestCase):
    def test_smb_url_uses_unc_and_preserves_unicode_subfolders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            folder = root / "Prüfungen"
            folder.mkdir()
            with patch("smb_paths.WINDOWS", True), patch("smb_paths.Path", return_value=root) as path:
                self.assertEqual(
                    resolve_folder("smb://nas.example/share/Pr%C3%BCfungen", [], require_smb=True),
                    folder,
                )
            path.assert_called_once_with("\\\\nas.example\\share\\")

    def test_invalid_windows_paths_are_rejected_before_network_access(self):
        for value in ("smb://nas.example/share/a:b", "smb://nas.example/share/a%5Cb",
                      "smb://nas.example/share/%2e%2e", "smb://user@nas.example/share"):
            with self.subTest(value=value), patch("smb_paths.WINDOWS", True), patch("smb_paths.Path") as path:
                with self.assertRaises(ValueError):
                    resolve_folder(value, [], require_smb=True)
                path.assert_not_called()

    def test_credentials_and_encoded_traversal_are_rejected(self):
        for value in ("smb://user:secret@nas.example/share", "smb://nas.example/share/%2e%2e"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                smb_address(value)
