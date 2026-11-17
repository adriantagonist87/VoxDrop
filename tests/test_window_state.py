import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QWindow

from desktop.window_state import WindowPresenter


class WindowStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.window = QWindow()
        self.window.resize(1100, 700)
        self.presenter = WindowPresenter(self.window)
        self.addCleanup(self.window.close)

    def test_repeated_open_keeps_a_visible_maximized_window(self):
        self.window.showMaximized()
        self.app.processEvents()
        size = self.window.size()
        for _ in range(3):
            self.presenter.show()
            self.app.processEvents()
            self.assertEqual(self.window.windowState(), Qt.WindowState.WindowMaximized)
            self.assertEqual(self.window.size(), size)

    def test_repeated_open_keeps_a_visible_fullscreen_window(self):
        self.window.showFullScreen()
        self.presenter.show()
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowFullScreen)

    def test_hidden_window_keeps_its_maximized_mode(self):
        self.window.showMaximized()
        self.window.hide()
        self.presenter.show()
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowMaximized)

    def test_minimized_window_returns_to_its_previous_display_mode(self):
        for mode in (Qt.WindowState.WindowMaximized, Qt.WindowState.WindowFullScreen):
            with self.subTest(mode=mode):
                self.window.setWindowState(mode)
                self.window.setVisible(True)
                self.window.showMinimized()
                self.presenter.show()
                self.assertEqual(self.window.windowState(), mode)

    def test_normal_window_keeps_user_size_and_returns_from_minimization(self):
        self.presenter.show()
        self.window.resize(1130, 730)
        self.presenter.show()
        self.assertEqual((self.window.width(), self.window.height()), (1130, 730))
        self.window.showMinimized()
        self.presenter.show()
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowNoState)

    def test_leaving_maximized_mode_is_respected_on_the_next_open(self):
        self.window.showMaximized()
        self.window.showNormal()
        self.window.resize(1130, 730)
        self.window.hide()
        self.presenter.show()
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowNoState)
        self.assertEqual((self.window.width(), self.window.height()), (1130, 730))


if __name__ == "__main__":
    unittest.main()
