"""VoxDrop desktop interface for Windows 11."""

import json
import os
import subprocess
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import time

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "Engine" if (ROOT / "Engine").is_dir() else ROOT
LOGO = (
    ROOT / "assets/VoxDropLogo.png"
    if (ROOT / "assets").is_dir()
    else ROOT / "macos/VoxDropLogo.png"
)
PROFILE = (
    Path(os.environ.get("LOCALAPPDATA", ROOT / ".runtime/windows-preview")) / "VoxDrop"
)
CONFIG = PROFILE / "config.json"
MODELS = {
    "qwen3-asr-1.7b": "Qwen3-ASR 1.7B",
    "large-v3-turbo": "Whisper Large v3 Turbo",
}
STATES = {
    "active": "Aktiv",
    "paused": "Pausiert",
    "unavailable": "Ordner prüfen",
    "stopped": "Dienst aus",
    "seen": "Erkannt",
    "ready": "Wartet",
    "copying": "Kopiert",
    "transcribing": "Transkribiert",
    "exporting": "Export läuft",
    "done": "Erfolgreich",
    "failed": "Fehler",
    "blocked": "Blockiert",
    "superseded": "Neue Dateiversion",
}
DEFAULTS = {
    "folders": [],
    "create_output_subfolder": False,
    "output_subfolder": "_FERTIGGESTELLT",
    "interval_seconds": 30,
    "model": "qwen3-asr-1.7b",
    "language": "auto",
    "hardware": "cuda",
    "speakers": True,
    "speaker_count": None,
    "dover_lap": False,
    "skip_silence": False,
    "monitoring": False,
}
STYLE = """
QMainWindow, QDialog, QWidget#historyBody, QWidget#content { background: #ffffff; color: #19231f; }
QWidget#header { background: #e9f5ed; border-bottom: 1px solid #d8e4dc; }
QWidget#settingsBody { background: #f3f7f4; }
QWidget#warning { background: #fff1f1; border: 1px solid #edb6b6; border-radius: 7px; }
QLabel#warningText { color: #a52323; }
QLabel#brand { color: #0c5635; font-size: 31px; font-weight: 700; }
QLabel#section { font-size: 17px; font-weight: 700; }
QLabel#filename, QPushButton#filename { font-size: 15px; font-weight: 700; text-align: left; }
QLabel#minor { color: #56615b; }
QScrollArea { border: 0; background: transparent; }
QSplitter::handle { background: #e1e7e3; }
QPushButton { background: #e7efe9; color: #174e34; border: 1px solid #dce8df;
    border-radius: 5px; padding: 5px 8px; }
QPushButton:hover { background: #d6e9db; }
QPushButton:disabled { color: #86968d; }
QPushButton#primary { background: #0c5635; color: white; }
QPushButton#primary:disabled { background: #85978b; }
QPushButton#filename { background: white; color: #19231f; border: 0; padding: 1px 0; }
QPushButton#filename:hover { color: #0c5635; text-decoration: underline; }
QLineEdit, QComboBox { background: white; padding: 4px 6px; border: 1px solid #d1ddd4; border-radius: 4px; }
QProgressBar { border: 0; background: #e5eee8; border-radius: 4px; height: 8px; }
QProgressBar::chunk { border-radius: 4px; background: #0c5635; }
"""


def read_settings():
    if not CONFIG.is_file():
        return DEFAULTS.copy()
    return {**DEFAULTS, **json.loads(CONFIG.read_text(encoding="utf-8"))}


def command(*arguments):
    python = Path(sys.executable)
    if python.name.casefold() == "pythonw.exe":
        python = python.with_name("python.exe")
    result = subprocess.run(
        [
            str(python),
            "-BEs",
            "-Xutf8",
            str(ENGINE / "watch_service.py"),
            "--state-dir",
            str(PROFILE / "service"),
            "--model-data",
            str(PROFILE / "data"),
            *(str(value) for value in arguments),
        ],
        cwd=ENGINE,
        check=False,
        capture_output=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or "VoxDrop-Dienst nicht verfügbar."
        )
    return result.stdout


def with_settings(settings, callback):
    PROFILE.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=PROFILE,
        prefix="settings-",
        suffix=".json",
        encoding="utf-8",
        mode="w",
        delete=False,
    ) as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)
        temporary = Path(file.name)
    try:
        return callback(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def save_settings(settings):
    def apply(path):
        command("validate-settings", path)
        path.replace(CONFIG)

    with_settings(settings, apply)


def login_item(enabled=None):
    if sys.platform != "win32":
        return False
    import winreg

    launcher = os.environ.get("VOXDROP_LAUNCHER")
    startup = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "VoxDrop"
    expected = subprocess.list2cmdline([launcher, "--background"]) if launcher else None
    if enabled is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup) as key:
                value, _ = winreg.QueryValueEx(key, name)
                # Keep the toggle on when VoxDrop is moved to a different folder.
                return bool(value)
        except FileNotFoundError:
            return False
    if enabled and expected is None:
        raise RuntimeError("Öffne VoxDrop.exe, um den Anmeldestart einzurichten.")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, startup) as key:
        if enabled:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, expected)
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass


def duration(value, all_units=False):
    if value is None:
        return "—"
    hours, remainder = divmod(max(0, int(value)), 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours or all_units:
        parts.append(f"{hours} Std.")
    if minutes or all_units or hours:
        parts.append(f"{minutes} Min.")
    parts.append(f"{seconds} Sek.")
    return " ".join(parts)


def clock(value, format="%H:%M Uhr"):
    return datetime.fromtimestamp(value).strftime(format) if value is not None else "—"


def total_duration(job):
    start = job.get("transcription_started")
    end = job.get("finished")
    return (
        end - start
        if job["state"] == "done" and start is not None and end is not None
        else None
    )


def job_settings(job):
    return json.loads(job["settings"])


def output_path(job, *, transcript=False):
    source = Path(job["source"])
    archived = Path(job["completed_dir"]) / source.name
    settings = job_settings(job)
    if transcript:
        if job.get("origin_job_id"):
            name = f"{archived.stem} (Neu {job['id']}).txt"
            return archived.with_name(
                name
                if len(name.encode("utf-8")) <= 255
                else f"Neutranskription {job['id']}.txt"
            )
        return archived.with_suffix(".txt")
    moved = not settings.get("watch_path") or settings.get("move_media")
    return (
        archived
        if moved and job["state"] == "done" and not job.get("origin_job_id")
        else source
    )


def text_label(text, role=None, *, wrap=False):
    label = QLabel(str(text))
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    if role:
        label.setObjectName(role)
    return label


def button(text, action, *, primary=False, hint=None):
    result = QPushButton(text)
    result.clicked.connect(action)
    if primary:
        result.setObjectName("primary")
    if hint:
        result.setToolTip(hint)
        result.setAccessibleName(hint)
    return result


def checkbox(text, checked):
    widget = QCheckBox(text)
    widget.setChecked(checked)
    return widget


def picker(choices, value):
    widget = QComboBox()
    widget.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    widget.setMinimumContentsLength(9)
    for key, title in choices:
        widget.addItem(title, key)
    widget.setCurrentIndex(max(0, widget.findData(value)))
    return widget


def pane(role):
    area = QScrollArea()
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidgetResizable(True)
    body = QWidget()
    body.setObjectName(role)
    column = QVBoxLayout(body)
    column.setContentsMargins(20, 18, 20, 18)
    column.setSpacing(9)
    column.setAlignment(Qt.AlignmentFlag.AlignTop)
    area.setWidget(body)
    return area, column


def remove_children(layout):
    while layout.count():
        entry = layout.takeAt(0)
        if entry.widget():
            entry.widget().hide()
            entry.widget().deleteLater()


def waveform(color):
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for index, height in enumerate((7, 15, 23, 15, 7)):
        x = 6 + 5 * index
        painter.drawLine(x, 16 - height // 2, x, 16 + height // 2)
    painter.end()
    return QIcon(image)


class HistoryName(QPushButton):
    def __init__(self, name, action):
        super().__init__()
        self.setObjectName("filename")
        self.setAccessibleName(name)
        self.setToolTip(name)
        self.clicked.connect(action)
        self.label = text_label(name, "filename", wrap=True)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.addWidget(self.label)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def sizeHint(self):
        return QSize(0, self.label.sizeHint().height() + 4)

    minimumSizeHint = sizeHint

    def heightForWidth(self, width):
        return self.label.heightForWidth(width) + 4


class Signals(QObject):
    finished = Signal(object, object)


class Worker(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = Signals()

    def run(self):
        try:
            result = self.operation()
        except Exception as error:  # noqa: BLE001 - report worker failures in the UI
            self.signals.finished.emit(None, str(error))
        else:
            self.signals.finished.emit(result, None)


class Dashboard(QMainWindow):
    def __init__(self, settings, *, preview=False):
        super().__init__()
        self.preview = preview
        self.snapshot = {}
        self.folder_checks = {}
        self.folder_rows = []
        self.pending = set()
        self.refreshing = False
        self.checking = False
        self.busy = False
        self.blink = True
        self.history_key = None
        self.next_probe = 0
        self.notifications = QSettings("VoxDrop", "VoxDrop")
        self.setWindowTitle("VoxDrop")
        self.setWindowIcon(QIcon(str(LOGO)))
        self.resize(1280, 830)
        self.setMinimumSize(990, 620)

        content = QWidget(objectName="content")
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self.header())
        splitter = QSplitter()
        settings_pane, settings_column = pane("settingsBody")
        center_pane, self.center = pane("content")
        history_pane, self.history = pane("historyBody")
        settings_pane.setMinimumWidth(325)
        history_pane.setMinimumWidth(340)
        for part in (settings_pane, center_pane, history_pane):
            splitter.addWidget(part)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([354, 440, 486])
        outer.addWidget(splitter, 1)
        self.setCentralWidget(content)
        self.fill_settings(settings_column, settings)
        self.fill_history_header()
        self.tray = self.create_tray()
        self.update_dashboard()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.blink_warnings)
        if not preview:
            self.timer.start(2000)
            self.blink_timer.start(700)
            self.refresh()

    def header(self):
        header = QWidget(objectName="header")
        row = QHBoxLayout(header)
        row.setContentsMargins(23, 14, 23, 14)
        row.setSpacing(15)
        logo = QLabel()
        logo.setPixmap(
            QPixmap(str(LOGO)).scaled(
                56,
                56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        row.addWidget(logo)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(text_label("VoxDrop", "brand"))
        brand.addWidget(text_label("Automatic Media Transcription", "minor"))
        row.addLayout(brand)
        row.addStretch()
        return header

    def fill_settings(self, column, initial):
        column.addWidget(text_label("Transkriptionsdienst", "section"))
        self.service_label = text_label("◯  Dienst aus", "minor")
        column.addWidget(self.service_label)
        self.autostart = checkbox("Automatisch bei Anmeldung starten", login_item())
        self.autostart.toggled.connect(self.set_autostart)
        column.addWidget(self.autostart)
        self.monitor = checkbox("Ordnerüberwachung aktiv", initial["monitoring"])
        column.addWidget(self.monitor)
        column.addWidget(text_label("Überwachte Ordner", "filename"))
        self.folder_list = QVBoxLayout()
        column.addLayout(self.folder_list)
        for path in initial["folders"]:
            self.add_folder(path)
        actions = QHBoxLayout()
        actions.addWidget(button("＋ Pfad hinzufügen", lambda: self.add_folder()))
        actions.addWidget(button("Alle Ordner prüfen", lambda: self.check_folders()))
        column.addLayout(actions)

        self.subfolder = checkbox(
            "Unterordner für fertige\nTranskripte erstellen?",
            initial["create_output_subfolder"],
        )
        column.addWidget(self.subfolder)
        self.output_name = QLineEdit(initial["output_subfolder"])
        self.output_name.setPlaceholderText("_FERTIGGESTELLT")
        column.addWidget(self.output_name)
        self.output_name.setVisible(self.subfolder.isChecked())
        self.subfolder.toggled.connect(self.output_name.setVisible)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        intervals = sorted({10, 30, 60, 300, initial["interval_seconds"]})
        self.interval = picker(
            [(seconds, f"{seconds} Sekunden") for seconds in intervals],
            initial["interval_seconds"],
        )
        self.model = picker(MODELS.items(), initial["model"])
        self.language = picker(
            [("auto", "Automatisch"), ("de", "Deutsch"), ("en", "Englisch")],
            initial["language"],
        )
        self.hardware = picker(
            [("cuda", "NVIDIA-GPU (CUDA)"), ("cpu", "CPU")], initial["hardware"]
        )
        form.addRow("Intervall Ordnerüberwachung", self.interval)
        form.addRow("Modell", self.model)
        column.addLayout(form)
        self.model_info = text_label("", "minor", wrap=True)
        column.addWidget(self.model_info)
        self.download = button("Modelle herunterladen", self.download_models)
        column.addWidget(self.download)
        remaining = QFormLayout()
        remaining.addRow("Sprache", self.language)
        remaining.addRow("Rechengerät", self.hardware)
        column.addLayout(remaining)
        self.silence = checkbox("Lange Stille überspringen", initial["skip_silence"])
        self.speakers = checkbox("Sprechererkennung", initial["speakers"])
        self.dover = checkbox(
            "Mehrere Prüfdurchgänge (DOVER-Lap)", initial["dover_lap"]
        )
        for item in (self.silence, self.speakers, self.dover):
            column.addWidget(item)
        self.speaker_count = picker(
            [(None, "Automatisch")] + [(i, str(i)) for i in range(1, 9)],
            initial["speaker_count"],
        )
        speaker_form = QFormLayout()
        speaker_form.addRow("Sprecherzahl", self.speaker_count)
        column.addLayout(speaker_form)
        self.speakers.toggled.connect(self.model_ready)
        self.model.currentIndexChanged.connect(self.model_ready)
        self.model_ready()
        controls = QHBoxLayout()
        self.save_button = button("Speichern", lambda: self.save(), primary=True)
        self.start_button = button("Dienst starten", lambda: self.save(start=True))
        controls.addWidget(self.save_button)
        controls.addWidget(self.start_button)
        column.addLayout(controls)
        self.message = text_label("", "minor", wrap=True)
        column.addWidget(self.message)

    def add_folder(self, path=""):
        item = QWidget()
        box = QVBoxLayout(item)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        row = QHBoxLayout()
        edit = QLineEdit(path)
        edit.setPlaceholderText(r"Ordner, \\Server\Freigabe oder smb://")
        warning = text_label("⚠", "warningText")
        warning.hide()
        row.addWidget(warning)
        row.addWidget(edit, 1)
        row.addWidget(
            button(
                "↻",
                lambda: self.check_folders(edit.text().strip()),
                hint="Ordner jetzt prüfen",
            )
        )
        row.addWidget(
            button("…", lambda: self.select_folder(edit), hint="Ordner auswählen")
        )
        row.addWidget(
            button("−", lambda: self.remove_folder(item), hint="Pfad entfernen")
        )
        edit.textChanged.connect(self.update_folders)
        box.addLayout(row)
        status = text_label("", "minor", wrap=True)
        box.addWidget(status)
        self.folder_rows.append((item, edit, warning, status))
        self.folder_list.addWidget(item)

    def select_folder(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "Ordner auswählen", edit.text())
        if folder:
            edit.setText(os.path.normpath(folder))

    def remove_folder(self, item):
        self.folder_rows = [row for row in self.folder_rows if row[0] is not item]
        item.deleteLater()
        self.update_folders()

    def settings(self):
        return {
            "folders": [edit.text().strip() for _, edit, _, _ in self.folder_rows],
            "monitoring": self.monitor.isChecked(),
            "create_output_subfolder": self.subfolder.isChecked(),
            "output_subfolder": self.output_name.text().strip(),
            "interval_seconds": self.interval.currentData(),
            "model": self.model.currentData(),
            "language": self.language.currentData(),
            "hardware": self.hardware.currentData(),
            "skip_silence": self.silence.isChecked(),
            "speakers": self.speakers.isChecked(),
            "speaker_count": self.speaker_count.currentData(),
            "dover_lap": self.dover.isChecked(),
        }

    def fill_history_header(self):
        title = QHBoxLayout()
        title.addWidget(text_label("Verlauf", "section"))
        title.addStretch()
        self.clear_button = button("Verlauf leeren …", self.clear_history)
        title.addWidget(self.clear_button)
        self.history.addLayout(title)
        filters = QFormLayout()
        self.filter = picker(
            [("all", "Alle"), ("errors", "Fehler"), ("done", "Fertig")], "all"
        )
        self.order = picker(
            [
                ("desc", "Chronologisch absteigend"),
                ("asc", "Chronologisch aufsteigend"),
            ],
            self.notifications.value("historyOrder", "desc"),
        )
        filters.addRow("Filter", self.filter)
        filters.addRow("Sortierung", self.order)
        self.history.addLayout(filters)
        self.history_rows = QVBoxLayout()
        self.history.addLayout(self.history_rows)
        self.filter.currentIndexChanged.connect(self.update_history)
        self.order.currentIndexChanged.connect(self.change_order)

    def create_tray(self):
        tray = QSystemTrayIcon(waveform("#ad2828"), self)
        tray.setToolTip("VoxDrop")
        menu = QMenu(self)
        self.tray_status = menu.addAction("VoxDrop")
        self.tray_status.setEnabled(False)
        menu.addAction("Hauptfenster öffnen", self.show_window)
        self.tray_monitor = menu.addAction(
            "Ordnerüberwachung pausieren", self.toggle_monitor
        )
        menu.addSeparator()
        menu.addAction("Oberfläche beenden", QApplication.instance().quit)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: (
                self.show_window()
                if reason == QSystemTrayIcon.ActivationReason.Trigger
                else None
            )
        )
        if not self.preview and QSystemTrayIcon.isSystemTrayAvailable():
            tray.show()
        return tray

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.tray.isVisible():
            event.ignore()
            self.hide()
        else:
            QApplication.instance().quit()
            event.accept()

    def submit(self, operation, callback):
        task = Worker(operation)
        self.pending.add(task)

        def finish(result, error):
            self.pending.discard(task)
            callback(result, error)

        task.signals.finished.connect(finish, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    def action(self, operation, success, *, refresh=True):
        if self.busy:
            return
        self.busy = True
        self.update_controls()

        def finished(result, error):
            self.busy = False
            self.message.setText(error if error else success)
            self.update_controls()
            if refresh:
                self.refresh()

        self.submit(operation, finished)

    def models_present(self):
        root = PROFILE / "data/models"
        model = self.model.currentData()
        if self.preview:
            return True
        if model == "large-v3-turbo":
            present = (root / model / "model.bin").is_file()
        else:
            manifest = json.loads(
                (ENGINE / "qwen-windows-models.json").read_text(encoding="utf-8")
            )
            present = all(
                (root / name / file).is_file()
                for name, entry in manifest.items()
                for file in entry["files"]
            )
        speaker_files = (
            "config.yaml",
            "embedding/pytorch_model.bin",
            "segmentation/pytorch_model.bin",
            "plda/plda.npz",
            "plda/xvec_transform.npz",
        )
        return present and (
            not self.speakers.isChecked()
            or all(
                (root / "speaker-detection" / path).is_file() for path in speaker_files
            )
        )

    def model_ready(self):
        ready = self.models_present()
        self.model_info.setText(
            "Modelle installiert" if ready else "Modell-Setup erforderlich"
        )
        self.download.setVisible(not ready)
        self.dover.setEnabled(self.speakers.isChecked())
        self.speaker_count.setEnabled(self.speakers.isChecked())
        return ready

    def update_controls(self):
        self.save_button.setEnabled(not self.busy)
        self.start_button.setEnabled(not self.busy)
        self.start_button.setVisible(not self.snapshot.get("running"))
        self.download.setEnabled(not self.busy)
        self.autostart.setEnabled(not self.busy)
        with_signals = self.autostart.blockSignals(True)
        self.autostart.setChecked(login_item())
        self.autostart.blockSignals(with_signals)
        self.clear_button.setEnabled(
            not self.busy
            and not self.snapshot.get("current")
            and bool(self.snapshot.get("jobs"))
        )
        self.model_ready()

    def download_models(self):
        selected = self.model.currentData()
        speaker_flags = [] if self.speakers.isChecked() else ["--no-speakers"]
        self.action(
            lambda: command("setup-models", "--model", selected, *speaker_flags),
            "Modelle sind einsatzbereit.",
        )
        self.message.setText("Modelle werden heruntergeladen und geprüft …")

    def save(self, *, start=False):
        if start and not self.model_ready():
            self.message.setText(
                "Lade zuerst die Modelle für die gewählte Konfiguration herunter."
            )
            return
        settings = self.settings()

        def save_and_start():
            save_settings(settings)
            if start:
                command("start", CONFIG)

        self.next_probe = 0
        self.folder_checks.clear()
        self.action(
            save_and_start,
            "Hintergrunddienst wird gestartet."
            if start
            else "Einstellungen gespeichert.",
        )

    def set_autostart(self, enabled):
        settings = self.settings()

        def register():
            if enabled:
                save_settings(settings)
            login_item(enabled)

        self.action(
            register,
            "Start bei der Anmeldung aktiviert."
            if enabled
            else "Start bei der Anmeldung deaktiviert.",
        )

    def toggle_monitor(self):
        if not self.snapshot.get("running"):
            self.save(start=True)
            return
        saved = read_settings()
        saved["monitoring"] = not saved["monitoring"]
        self.monitor.setChecked(saved["monitoring"])
        self.action(lambda: save_settings(saved), "Ordnerüberwachung aktualisiert.")

    def check_folders(self, path=None, *, automatic=False):
        if self.checking or path == "":
            return
        self.checking = True
        settings = self.settings()
        settings["folders"] = [folder for folder in settings["folders"] if folder]
        if path:
            settings["folders"] = [path]
        if not automatic:
            self.message.setText("Ordner werden geprüft …")

        def finished(result, error):
            self.checking = False
            if error:
                if not automatic:
                    self.message.setText(error)
                return
            for item in result:
                self.folder_checks[item["path"]] = {**item, "updated": time()}
            if not automatic:
                self.message.setText("Ordnerprüfung abgeschlossen.")
            self.update_dashboard()

        self.submit(
            lambda: with_settings(
                settings, lambda file: json.loads(command("check", file))
            ),
            finished,
        )

    def change_order(self):
        self.notifications.setValue("historyOrder", self.order.currentData())
        self.update_history()
        self.refresh()

    def refresh(self):
        if self.preview or self.refreshing:
            return
        self.refreshing = True
        order = self.order.currentData()

        def refreshed(result, error):
            self.refreshing = False
            if error:
                self.message.setText(error)
                return
            self.snapshot = result
            if not result.get("running") and time() >= self.next_probe:
                self.next_probe = time() + self.interval.currentData()
                self.check_folders(automatic=True)
            self.update_dashboard()

        self.submit(
            lambda: json.loads(command("status", "--limit", "250", "--order", order)),
            refreshed,
        )

    def update_dashboard(self):
        running = self.snapshot.get("running", False)
        service = self.snapshot.get("service") or {}
        label = STATES.get(service.get("state"), "Aktiv") if running else "Dienst aus"
        self.service_label.setText(f"{'◉' if running else '◯'}  {label}")
        self.tray_monitor.setEnabled(not self.busy)
        self.tray_monitor.setText(
            (
                "Ordnerüberwachung pausieren"
                if self.monitor.isChecked()
                else "Ordnerüberwachung fortsetzen"
            )
            if running
            else "Dienst starten"
        )
        self.update_folders()
        self.update_center()
        self.update_history()
        self.update_controls()

    def folder_status(self, path):
        status = next(
            (row for row in self.snapshot.get("folders", []) if row["path"] == path), {}
        )
        direct = self.folder_checks.get(path, {})
        if direct and status.get("updated", 0) <= direct.get("updated", 0):
            return direct
        return status or direct

    def failures(self):
        results = [
            self.folder_status(edit.text().strip())
            for _, edit, _, _ in self.folder_rows
        ]
        return [item for item in results if item.get("error")]

    def update_folders(self):
        if not hasattr(self, "tray"):
            return
        known = []
        for _, edit, warning, label in self.folder_rows:
            path = edit.text().strip()
            status = self.folder_status(path)
            if path:
                known.append(bool(status.get("available")))
            error = status.get("error")
            warning.setVisible(bool(error) and self.blink)
            label.setText(
                error
                or ("Erreichbar und beschreibbar" if status.get("available") else "")
            )
        self.tray.setIcon(waveform("#13904f" if known and all(known) else "#ad2828"))
        summary = (
            "Alle Ordner verfügbar"
            if known and all(known)
            else ("Ordner prüfen" if known else "Keine Ordner eingerichtet")
        )
        self.tray_status.setText(summary)
        self.tray.setToolTip(f"VoxDrop – {summary}")
        for status in self.failures():
            incident = status.get("incident")
            if self.tray.isVisible() and self.snapshot.get("running") and incident:
                key = "incidents/" + status["path"]
                if self.notifications.value(key) != incident:
                    self.tray.showMessage(
                        "VoxDrop – Ordner nicht verfügbar",
                        f"{status['path']}\n{status['error']}",
                        QSystemTrayIcon.MessageIcon.Warning,
                    )
                    self.notifications.setValue(key, incident)

    def blink_warnings(self):
        self.blink = not self.blink
        for _, edit, warning, _ in self.folder_rows:
            warning.setVisible(
                self.blink
                and bool(self.folder_status(edit.text().strip()).get("error"))
            )

    def update_center(self):
        remove_children(self.center)
        failures = self.failures()
        if failures:
            panel = QWidget(objectName="warning")
            column = QVBoxLayout(panel)
            heading = (
                "Ein Ordner ist nicht verfügbar"
                if len(failures) == 1
                else f"{len(failures)} Ordner sind nicht verfügbar"
            )
            column.addWidget(text_label("⚠  " + heading, "warningText", wrap=True))
            for item in failures:
                column.addWidget(
                    text_label(
                        f"{item['path']}\n{item['error']}", "warningText", wrap=True
                    )
                )
            self.center.addWidget(panel)
        self.center.addWidget(text_label("Aktueller Auftrag", "section"))
        job = self.snapshot.get("current")
        if job:
            self.center.addWidget(
                text_label(Path(job["source"]).name, "filename", wrap=True)
            )
            self.center.addWidget(
                text_label(
                    job.get("phase") or STATES.get(job["state"], job["state"]),
                    wrap=True,
                )
            )
            progress = QProgressBar()
            progress.setTextVisible(False)
            fraction = job.get("progress")
            progress.setRange(0, 0 if fraction is None else 100)
            if fraction is not None:
                progress.setValue(round(fraction * 100))
            self.center.addWidget(progress)
            if fraction is not None:
                self.center.addWidget(text_label(f"{fraction:.0%}", "minor"))
            if job.get("started"):
                self.center.addWidget(
                    text_label(
                        "Laufzeit  " + duration(time() - job["started"]), "minor"
                    )
                )
            settings = job_settings(job)
            self.center.addWidget(
                text_label(
                    "Modell  "
                    + MODELS.get(settings.get("model"), "Whisper Large v3 Turbo")
                )
            )
            self.center.addWidget(
                text_label("Rechengerät  " + self.accelerator(settings))
            )
        else:
            self.center.addWidget(text_label("Kein Auftrag in Bearbeitung", "minor"))
        self.center.addWidget(
            text_label(f"Warteschlange  {self.snapshot.get('waiting', 0)}")
        )

    @staticmethod
    def accelerator(settings):
        return {"cuda": "NVIDIA-GPU (CUDA)", "metal": "Apple-GPU (Metal)"}.get(
            settings.get("hardware"), "CPU"
        )

    def update_history(self):
        jobs = list(self.snapshot.get("jobs", []))
        order = self.order.currentData()
        filter_mode = self.filter.currentData()
        if filter_mode == "done":
            jobs = [job for job in jobs if job["state"] == "done"]
        elif filter_mode == "errors":
            jobs = [job for job in jobs if job["state"] in {"blocked", "failed"}]
        jobs.sort(key=lambda job: (job["updated"], job["id"]), reverse=order == "desc")
        now = time()
        key = [
            (job["id"], job["updated"], self.relative_time(job, now)) for job in jobs
        ]
        if key == self.history_key:
            return
        self.history_key = key
        remove_children(self.history_rows)
        if not jobs:
            self.history_rows.addWidget(text_label("Keine Aufträge", "minor"))
        for job in jobs:
            name = Path(job["source"]).name
            entry = HistoryName(name, lambda _=False, item=job: self.details(item))
            self.history_rows.addWidget(entry)
            if job.get("origin_job_id"):
                self.history_rows.addWidget(text_label("Neutranskription", "minor"))
            self.history_rows.addWidget(
                text_label(output_path(job), "minor", wrap=True)
            )
            finished = job.get("finished") if job["state"] == "done" else None
            end = clock(finished)
            if delta := self.relative_time(job, now):
                end += f" (vor {delta})"
            lines = [
                "Gesamtdauer der Audiodatei: "
                + duration(job.get("audio_seconds"), all_units=True),
                "Transkriptionsbeginn: " + clock(job.get("transcription_started")),
                "Transkriptionsdauer (gesamt): " + duration(total_duration(job)),
                "Transkription fertiggestellt: " + end,
                f"{STATES.get(job['state'], job['state'])}  ·  {clock(job['updated'], '%d.%m.%Y')}",
            ]
            self.history_rows.addWidget(text_label("\n".join(lines), wrap=True))
            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            self.history_rows.addWidget(divider)

    @staticmethod
    def relative_time(job, now):
        finished = job.get("finished")
        if (
            job["state"] == "done"
            and finished is not None
            and 0 <= now - finished < 3600
        ):
            elapsed = int(now - finished)
            return f"{elapsed} Sek." if elapsed < 60 else f"{elapsed // 60} Min."
        return ""

    def details(self, job):
        dialog = QDialog(self)
        dialog.setWindowTitle("Auftragsdetails")
        dialog.setMinimumWidth(540)
        column = QVBoxLayout(dialog)
        column.addWidget(text_label(Path(job["source"]).name, "section", wrap=True))
        column.addWidget(text_label(STATES.get(job["state"], job["state"]), "filename"))
        form = QFormLayout()
        settings = job_settings(job)
        memory = job.get("peak_memory_bytes")
        speakers = settings.get("speakers", True)
        method = {
            "dover-lap": f"DOVER-Lap ({job.get('speaker_passes') or 3} Durchgänge)",
            "single-fallback": "Einzellauf nach DOVER-Lap-Prüfung",
        }.get(job.get("speaker_method"), "Einzellauf")
        values = [
            (
                "Gesamtdauer der Audiodatei",
                duration(job.get("audio_seconds"), all_units=True),
            ),
            ("Erkannt", clock(job.get("detected"), "%d.%m.%Y %H:%M")),
            ("Beginn", clock(job.get("started"), "%d.%m.%Y %H:%M")),
            ("Ende", clock(job.get("finished"), "%d.%m.%Y %H:%M")),
            ("Versuche", job.get("attempt", 0)),
            (
                "Modell verwendet",
                MODELS.get(settings.get("model"), "Whisper Large v3 Turbo"),
            ),
            (
                "RAM-Auslastung verursacht",
                f"{memory / (1024**3):.2f} GiB Spitze".replace(".", ",")
                if memory
                else "—",
            ),
            ("Dauer Spracherkennung", duration(job.get("speech_seconds"))),
            ("Verfahren der Sprecherzuordnung", method if speakers else "Deaktiviert"),
            (
                "Dauer Sprecherzuordnung",
                duration(job.get("speaker_seconds")) if speakers else "Deaktiviert",
            ),
            ("Dauer gesamt", duration(total_duration(job))),
            ("Rechengerät", self.accelerator(settings)),
        ]
        for name, value in values:
            form.addRow(name, text_label(value, wrap=True))
        column.addLayout(form)
        path = text_label(output_path(job), "minor", wrap=True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        column.addWidget(path)
        for note in (job.get("error"), job.get("speaker_note")):
            if note:
                column.addWidget(text_label(note, "minor", wrap=True))
        controls = QHBoxLayout()
        if job["state"] in {"blocked", "failed"}:
            controls.addWidget(
                button(
                    "Erneut versuchen",
                    lambda: self.details_action(dialog, job, "retry"),
                )
            )
        if job["state"] in {"done", "blocked", "failed"}:
            controls.addWidget(
                button(
                    "Neu transkribieren",
                    lambda: self.details_action(dialog, job, "retranscribe"),
                )
            )
        if job["state"] == "done":
            controls.addWidget(
                button(
                    "Im Explorer zeigen",
                    lambda: self.reveal(output_path(job, transcript=True)),
                )
            )
        controls.addStretch()
        controls.addWidget(button("Schließen", dialog.accept))
        column.addLayout(controls)
        dialog.exec()

    def details_action(self, dialog, job, operation):
        if operation == "retranscribe":
            settings = self.settings()
            self.action(
                lambda: with_settings(
                    settings, lambda file: command(operation, job["id"], file)
                ),
                "Neutranskription eingereiht.",
            )
        else:
            self.action(
                lambda: command(operation, job["id"]), "Auftrag erneut eingereiht."
            )
        dialog.accept()

    @staticmethod
    def reveal(path):
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def clear_history(self):
        answer = QMessageBox.question(
            self,
            "Verlauf und bekannte Dateien leeren?",
            "Auftragsdaten werden zurückgesetzt. Aufnahmen und Transkripte bleiben erhalten.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.action(lambda: command("clear-history"), "Verlauf geleert.")


def main():
    background = "--background" in sys.argv
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VoxDrop.Desktop")
    app = QApplication(sys.argv)
    app.setApplicationName("VoxDrop")
    app.setOrganizationName("VoxDrop")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    instance = (
        "VoxDrop-" + sha256(str(PROFILE).casefold().encode("utf-8")).hexdigest()[:16]
    )
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
    try:
        window = Dashboard(read_settings())
    except (OSError, ValueError) as error:
        QMessageBox.critical(
            None, "VoxDrop", f"Einstellungen konnten nicht geladen werden.\n{error}"
        )
        return 1

    def activate_existing():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.disconnected.connect(connection.deleteLater)

            def read(socket=connection):
                if bytes(socket.readAll()) == b"open":
                    window.show_window()

            connection.readyRead.connect(read)
            if connection.bytesAvailable():
                read()

    server.newConnection.connect(activate_existing)
    if background and CONFIG.is_file():
        window.action(
            lambda: command("start", CONFIG), "Hintergrunddienst wird gestartet."
        )
    if not background or not window.tray.isVisible():
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
