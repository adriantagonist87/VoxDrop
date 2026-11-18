"""Bring the existing window forward without discarding its display mode."""

import sys

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QWindow


class WindowPresenter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.last_state = Qt.WindowState.WindowNoState
        self.normal_state_timer = QTimer(self)
        self.normal_state_timer.setSingleShot(True)
        self.normal_state_timer.timeout.connect(self.remember_normal)
        self.remember(window.visibility())
        window.visibilityChanged.connect(self.remember)

    def remember(self, visibility):
        if sys.platform == "win32" and visibility == QWindow.Visibility.Windowed:
            # Windows emits Windowed briefly while minimizing fullscreen.
            # Wait for the completed transition before remembering a user
            # change to normal mode.
            self.normal_state_timer.start(0)
            return
        states = {
            QWindow.Visibility.Windowed: Qt.WindowState.WindowNoState,
            QWindow.Visibility.Maximized: Qt.WindowState.WindowMaximized,
            QWindow.Visibility.FullScreen: Qt.WindowState.WindowFullScreen,
        }
        if visibility in states:
            self.last_state = states[visibility]

    def remember_normal(self):
        if self.window.windowStates() == Qt.WindowState.WindowNoState:
            self.last_state = Qt.WindowState.WindowNoState

    def show(self):
        minimized = bool(self.window.windowStates() & Qt.WindowState.WindowMinimized)
        target = self.last_state
        if minimized:
            if sys.platform == "win32" and target == Qt.WindowState.WindowFullScreen:
                # Clear the native iconic state before re-entering fullscreen.
                # Otherwise Windows activation later restores the QML window
                # to normal, after Qt has already reported fullscreen again.
                self.window.showNormal()
                self.window.showFullScreen()
            else:
                self.window.setWindowStates(target)
        # QWindow.show() chooses the platform's default mode and calls
        # showNormal() on desktop systems, even for an already maximized window.
        self.window.setVisible(True)
        self.window.raise_()
        self.window.requestActivate()
