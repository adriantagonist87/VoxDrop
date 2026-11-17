import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.window_state import WindowPresenter

DESKTOP = Path(__file__).resolve().parents[1] / "desktop"


class DesktopWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        QQuickStyle.setStyle("Basic")
        sys.path.insert(0, str(DESKTOP))
        import controller
        cls.controller_module = controller

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(patch.object(self.controller_module, "PROFILE", Path(directory.name)))
        self.enterContext(patch.object(self.controller_module, "MODEL_DATA", Path(directory.name) / "data"))
        self.controller = self.controller_module.Controller(preview=True)
        self.engine = QQmlApplicationEngine()
        self.engine.setInitialProperties({"api": self.controller})
        self.engine.load(QUrl.fromLocalFile(str(DESKTOP / "qml/Main.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]
        self.presenter = WindowPresenter(self.window)
        self.addCleanup(self.window.close)

    def test_full_qml_fullscreen_survives_minimization_and_native_activation(self):
        self.presenter.show()
        QTest.qWait(300)
        self.window.showFullScreen()
        QTest.qWait(300)
        self.window.showMinimized()
        QTest.qWait(300)
        self.presenter.show()
        QTest.qWait(300)
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowFullScreen)
        self.assertTrue(self.window.isVisible())

    def test_network_wait_offers_cancel_and_recursive_mode_locks_archive_option(self):
        self.presenter.show()
        self.controller.downloading = True
        self.controller.network_permission_changed(True)
        self.controller.setSetting("include_subfolders", True)
        QTest.qWait(50)
        cancel = self.window.findChild(QObject, "cancelNetworkWait")
        self.assertTrue(cancel.property("visible"))
        self.assertTrue(cancel.property("enabled"))
        self.assertFalse(self.window.findChild(QObject, "createOutputSubfolder").property("enabled"))
        self.controller.cancelNetworkWait()
        self.assertTrue(self.controller.network_cancel.is_set())
        self.controller.network_permission_changed(False)
        QTest.qWait(50)
        self.assertFalse(cancel.property("visible"))
