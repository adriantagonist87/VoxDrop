import ctypes
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from desktop.file_actions import reveal_in_explorer


@unittest.skipUnless(sys.platform == 'win32', 'Windows Shell adapter')
class ExplorerActionTests(unittest.TestCase):
    def test_unicode_spaces_commas_and_plus_are_passed_as_literal_shell_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'Aufnahme + Prüfung, final.txt'
            path.write_text('Synthetic transcript', encoding='utf-8')
            shell, ole = Mock(), Mock()
            ole.CoInitializeEx.return_value = 0
            def parse(name, context, item, flags, attributes):
                self.assertEqual(name, str(path.absolute()))
                ctypes.cast(item, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(1234)
                return 0
            shell.SHParseDisplayName.side_effect = parse
            shell.SHOpenFolderAndSelectItems.return_value = 0
            with patch('ctypes.WinDLL', side_effect=[shell, ole]):
                reveal_in_explorer(path)
            args = shell.SHOpenFolderAndSelectItems.call_args.args
            self.assertEqual((args[0].value, *args[1:]), (1234, 0, None, 0))
            ole.CoTaskMemFree.assert_called_once()
            ole.CoUninitialize.assert_called_once_with()

    def test_missing_files_and_shell_failures_do_not_fall_back_to_default_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'result.txt'
            with patch('ctypes.WinDLL') as library:
                with self.assertRaises(FileNotFoundError):
                    reveal_in_explorer(path)
                library.assert_not_called()
            path.write_text('Synthetic transcript', encoding='utf-8')
            for phase in ('initialise', 'parse', 'select'):
                with self.subTest(phase=phase):
                    shell, ole = Mock(), Mock()
                    ole.CoInitializeEx.return_value = -1 if phase == 'initialise' else 0
                    def parse(name, context, item, flags, attributes):
                        if phase == 'parse':
                            return -1
                        ctypes.cast(item, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(1234)
                        return 0
                    shell.SHParseDisplayName.side_effect = parse
                    shell.SHOpenFolderAndSelectItems.return_value = -1
                    with patch('ctypes.WinDLL', side_effect=[shell, ole]):
                        with self.assertRaisesRegex(OSError, 'HRESULT'):
                            reveal_in_explorer(path)
                    self.assertEqual(ole.CoUninitialize.call_count, phase != 'initialise')
                    self.assertEqual(ole.CoTaskMemFree.call_count, phase == 'select')
