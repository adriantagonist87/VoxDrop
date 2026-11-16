"""Start the shared QML window and register an instance for this profile."""

import ctypes
import sys
from hashlib import sha256
from pathlib import Path

from controller import LOGO, PROFILE, Controller
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox

HERE = Path(__file__).resolve().parent


def create_app(argv):
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VoxDrop.Desktop")
    app = QApplication(argv)
    app.setApplicationName("VoxDrop")
    app.setOrganizationName("VoxDrop")
    app.setWindowIcon(QIcon(str(LOGO)))
    app.setQuitOnLastWindowClosed(False)
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    QQuickStyle.setStyle("Basic")
    font = QFontDatabase.addApplicationFont(str(HERE / "assets/InterVariable.ttf"))
    families = QFontDatabase.applicationFontFamilies(font)
    if families:
        app.setFont(QFont(families[0]))
    return app


def load_window(engine, controller):
    engine.setInitialProperties({"api": controller})
    engine.load(QUrl.fromLocalFile(str(HERE / "qml/Main.qml")))
    return next(iter(engine.rootObjects()), None)


def main():
    background = "--background" in sys.argv
    app = create_app(sys.argv)
    instance = "VoxDrop-" + sha256(str(PROFILE).casefold().encode()).hexdigest()[:16]
    client = QLocalSocket(app)
    client.connectToServer(instance)
    if client.waitForConnected(150):
        if not background:
            client.write(b"open")
            client.waitForBytesWritten(500)
        return 0
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(instance):
        QMessageBox.critical(None, "VoxDrop", server.errorString())
        return 1

    controller = Controller()
    engine = QQmlApplicationEngine()
    controller.init_tray()
    window = load_window(engine, controller)
    if window is None:
        QMessageBox.critical(
            None, "VoxDrop", "Das Hauptfenster konnte nicht geladen werden."
        )
        return 1

    def show():
        window.showNormal()
        window.raise_()
        window.requestActivate()

    def activate_existing():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.disconnected.connect(connection.deleteLater)

            def read(socket=connection):
                if bytes(socket.readAll()) == b"open":
                    show()

            connection.readyRead.connect(read)
            if connection.bytesAvailable():
                read()

    server.newConnection.connect(activate_existing)
    controller.windowRequested.connect(show)
    if not background or not controller.hasTray():
        window.show()
    controller.start(background)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
