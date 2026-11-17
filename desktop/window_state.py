"""Bring the existing window forward without discarding its display mode."""

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QWindow


class WindowPresenter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.last_state = Qt.WindowState.WindowNoState
        self.remember(window.visibility())
        window.visibilityChanged.connect(self.remember)

    def remember(self, visibility):
        states = {
            QWindow.Visibility.Windowed: Qt.WindowState.WindowNoState,
            QWindow.Visibility.Maximized: Qt.WindowState.WindowMaximized,
            QWindow.Visibility.FullScreen: Qt.WindowState.WindowFullScreen,
        }
        if visibility in states:
            self.last_state = states[visibility]

    def show(self):
        if self.window.windowStates() & Qt.WindowState.WindowMinimized:
            self.window.setWindowStates(self.last_state)
        # QWindow.show() chooses the platform's default mode and calls
        # showNormal() on desktop systems, even for an already maximized window.
        self.window.setVisible(True)
        self.window.raise_()
        self.window.requestActivate()
