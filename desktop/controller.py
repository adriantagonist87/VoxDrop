"""Shared controller for the VoxDrop desktop interface."""

import json
import os
import subprocess
import sys
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import time

from model_storage import data_directory
from PySide6.QtCore import (
    Property,
    QObject,
    QRunnable,
    QSettings,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = ROOT / "Engine" if (ROOT / "Engine").is_dir() else ROOT
LOGO = (
    ROOT / "VoxDropLogo.png"
    if sys.platform == "darwin" and (ROOT / "VoxDropLogo.png").is_file()
    else ROOT / "assets/VoxDropLogo.png"
)
if not LOGO.is_file():
    LOGO = ROOT / "macos/VoxDropLogo.png"
NATIVE_PROFILE = (
    Path.home() / "Library/Application Support"
    if sys.platform == "darwin"
    else Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
) / "VoxDrop"
PROFILE = Path(os.environ.get("VOXDROP_PROFILE", NATIVE_PROFILE))
MODEL_DATA = data_directory(PROFILE, ROOT)
CONFIG = PROFILE / "config.json"
DESKTOP_LOG = PROFILE / "service/desktop.log"
GPU = "metal" if sys.platform == "darwin" else "cuda"
GPU_NAME = {"metal": "Apple-GPU (Metal)", "cuda": "NVIDIA-GPU (CUDA)"}
TRAY_CONNECTED = "#199d61"
TRAY_DISCONNECTED = "#e14945"

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
    "include_subfolders": False,
    "create_output_subfolder": False,
    "output_subfolder": "_FERTIGGESTELLT",
    "interval_seconds": 30,
    "model": "qwen3-asr-1.7b",
    "language": "auto",
    "hardware": GPU,
    "speakers": True,
    "speaker_count": None,
    "dover_lap": False,
    "skip_silence": False,
    "monitoring": False,
}


def read_settings():
    if not CONFIG.is_file():
        return DEFAULTS.copy()
    saved = json.loads(CONFIG.read_text(encoding="utf-8"))
    if "folders" not in saved and (path := saved.get("input_dir")):
        saved["folders"] = [path]
    if saved.get("include_subfolders"):
        saved["create_output_subfolder"] = False
    return {**DEFAULTS, **saved}


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
            str(MODEL_DATA),
            *(str(value) for value in arguments),
        ],
        cwd=ENGINE,
        check=False,
        capture_output=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip()
        if "Traceback (most recent call last):" in details:
            with suppress(OSError):
                DESKTOP_LOG.parent.mkdir(parents=True, exist_ok=True)
                with DESKTOP_LOG.open("a", encoding="utf-8") as log:
                    log.write(
                        f"\n{datetime.now().isoformat(timespec='seconds')} · {arguments[0]}\n{details}\n"
                    )
            if arguments[0] == "setup-models":
                if "WinError 10013" in details:
                    raise RuntimeError(
                        "Für den Modell-Download wurde die Netzwerkverbindung verweigert (Windows-Fehler 10013)."
                    )
                raise RuntimeError("Die Modelle konnten nicht heruntergeladen werden.")
            raise RuntimeError(
                "Der VoxDrop-Dienst konnte die Aktion nicht abschließen."
            )
        raise RuntimeError(details or "VoxDrop-Dienst nicht verfügbar.")
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


def windows_login_item(enabled=None):
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
        except Exception as error:  # noqa: BLE001 - send failures to the GUI thread
            self.signals.finished.emit(None, str(error))
        else:
            self.signals.finished.emit(result, None)


class Controller(QObject):
    changed = Signal()
    foldersChanged = Signal()
    historyChanged = Signal()
    detailsOpened = Signal()
    windowRequested = Signal()
    logo = Property(QUrl, lambda self: QUrl.fromLocalFile(str(LOGO)), constant=True)
    modelLocation = Property(str, lambda self: str(MODEL_DATA), constant=True)
    gpuName = Property(str, lambda self: GPU_NAME[GPU], constant=True)
    gpuValue = Property(str, lambda self: GPU, constant=True)

    def __init__(self, *, preview=False):
        super().__init__()
        self.preferences = QSettings(
            str(PROFILE / "layout.ini"), QSettings.Format.IniFormat
        )
        self.preview = preview
        self.draft = DEFAULTS.copy()
        self.paths = []
        self.snapshot = {}
        self.direct = {}
        self.pending = set()
        self.selected = None
        self.history = []
        self.order = self.preferences.value("historyOrder", "desc")
        self.filter = "all"
        self.ready = preview
        self.busy = False
        self.downloading = False
        self.message = ""
        self.message_error = False
        self.drop_message = ""
        self.drop_error = False
        self.refreshing = False
        self.checking = False
        self.next_probe = 0
        self.tray = None
        self.timer = QTimer(self, interval=2000)
        self.timer.timeout.connect(self.refresh)

    settings = Property("QVariantMap", lambda self: self.draft, notify=changed)
    folderPaths = Property(
        "QStringList", lambda self: self.paths, notify=foldersChanged
    )
    historyItems = Property(
        "QVariantList", lambda self: self.history, notify=historyChanged
    )

    @Property("QVariantMap", notify=changed)
    def state(self):
        running = self.snapshot.get("running", False)
        service = self.snapshot.get("service") or {}
        job = self.snapshot.get("current")
        current = {}
        if job:
            settings = job_settings(job)
            current = {
                "name": Path(job["source"]).name,
                "phase": job.get("phase") or STATES.get(job["state"], job["state"]),
                "progress": job.get("progress"),
                "elapsed": duration(time() - job["started"])
                if job.get("started")
                else "",
                "model": MODELS.get(settings.get("model"), MODELS["large-v3-turbo"]),
                "hardware": GPU_NAME.get(settings.get("hardware"), "CPU"),
            }
        checked = {path: self.folder_status(path) for path in self.paths}
        return {
            "ready": self.ready,
            "busy": self.busy,
            "downloading": self.downloading,
            "running": running,
            "service": STATES.get(service.get("state"), "Aktiv")
            if running
            else "Dienst aus",
            "serviceError": service.get("error") or "",
            "current": current,
            "waiting": self.snapshot.get("waiting", 0),
            "dropMessage": self.drop_message,
            "dropError": self.drop_error,
            "checked": checked,
            "warnings": [
                checked[path]
                for path in dict.fromkeys(self.paths)
                if checked[path].get("error")
            ],
            "autostart": windows_login_item()
            if sys.platform == "win32"
            else self.snapshot.get("autostart", False),
            "modelsReady": self.models_present(),
            "message": self.message,
            "messageError": self.message_error,
            "logAvailable": self.message_error and DESKTOP_LOG.is_file(),
            "filter": self.filter,
            "order": self.order,
            "canClear": bool(self.snapshot.get("jobs")) and not job and not self.busy,
        }

    @Property("QVariantMap", notify=changed)
    def detail(self):
        if self.selected is None:
            return {}
        job = self.selected
        settings = job_settings(job)
        speakers = settings.get("speakers", True)
        memory = job.get("peak_memory_bytes")
        method = {
            "dover-lap": f"DOVER-Lap ({job.get('speaker_passes') or 3} Durchgänge)",
            "single-fallback": "Einzellauf nach DOVER-Lap-Prüfung",
        }.get(job.get("speaker_method"), "Einzellauf")
        return {
            "name": Path(job["source"]).name,
            "path": str(output_path(job)),
            "status": STATES.get(job["state"], job["state"]),
            "error": job.get("error") or "",
            "note": job.get("speaker_note") or "",
            "retry": job["state"] in {"blocked", "failed"},
            "repeat": job["state"] in {"done", "blocked", "failed"},
            "reveal": job["state"] == "done",
            "rows": [
                {"label": label, "value": str(value)}
                for label, value in (
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
                        MODELS.get(settings.get("model"), MODELS["large-v3-turbo"]),
                    ),
                    (
                        "RAM-Auslastung verursacht",
                        f"{memory / 2**30:.2f} GiB Spitze".replace(".", ",")
                        if memory
                        else "—",
                    ),
                    ("Dauer Spracherkennung", duration(job.get("speech_seconds"))),
                    (
                        "Verfahren der Sprecherzuordnung",
                        method if speakers else "Deaktiviert",
                    ),
                    (
                        "Dauer Sprecherzuordnung",
                        duration(job.get("speaker_seconds"))
                        if speakers
                        else "Deaktiviert",
                    ),
                    ("Dauer gesamt", duration(total_duration(job))),
                    ("Rechengerät", GPU_NAME.get(settings.get("hardware"), "CPU")),
                )
            ],
        }

    def submit(self, operation, callback):
        task = Worker(operation)
        self.pending.add(task)

        def finish(result, error):
            self.pending.discard(task)
            callback(result, error)

        task.signals.finished.connect(finish, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(task)

    def notify(self, text="", error=False):
        self.message = text
        self.message_error = error
        self.changed.emit()

    def action(self, operation, success, *, downloading=False):
        if self.busy or not self.ready:
            return
        self.busy = True
        self.downloading = downloading
        self.notify(
            "Modelle werden heruntergeladen und geprüft …" if downloading else ""
        )

        def finished(result, error):
            self.busy = False
            self.downloading = False
            self.notify(error or success, bool(error))
            self.refresh()

        self.submit(operation, finished)

    def start(self, background=False):
        if self.preview or self.busy or self.ready:
            return
        self.busy = True
        self.changed.emit()

        def prepare():
            resume = (
                sys.platform == "darwin"
                and PROFILE == NATIVE_PROFILE
                and command("prepare-app-data").strip() == "resume"
            )
            settings = read_settings()
            if (background or resume) and CONFIG.is_file():
                command("start", CONFIG)
            return settings

        def prepared(settings, error):
            self.busy = False
            if error:
                self.notify(error, True)
                return
            self.draft = settings
            self.paths = list(settings.get("folders", []))
            self.ready = True
            self.foldersChanged.emit()
            self.notify()
            self.timer.start()
            self.refresh()

        self.submit(prepare, prepared)

    @Slot()
    def retryPreparation(self):
        self.start()

    @Slot(str, "QVariant")
    def setSetting(self, key, value):
        if key in DEFAULTS and key != "folders":
            if key == "create_output_subfolder" and self.draft["include_subfolders"]:
                return
            self.draft[key] = value
            if key == "include_subfolders" and value:
                self.draft["create_output_subfolder"] = False
            self.changed.emit()

    @Slot()
    def addFolder(self):
        self.paths.append("")
        self.foldersChanged.emit()
        self.changed.emit()

    @Slot(int)
    def removeFolder(self, index):
        if 0 <= index < len(self.paths):
            self.paths.pop(index)
            self.foldersChanged.emit()
            self.update_status()

    @Slot(int, str)
    def editFolder(self, index, text):
        if 0 <= index < len(self.paths) and self.paths[index] != text:
            self.paths[index] = text
            self.update_status()

    @Slot(int)
    def pickFolder(self, index):
        if 0 <= index < len(self.paths):
            folder = QFileDialog.getExistingDirectory(
                None, "Ordner auswählen", self.paths[index]
            )
            if folder:
                self.editFolder(index, os.path.normpath(folder))
                self.foldersChanged.emit()

    def config(self):
        return {
            **self.draft,
            "folders": [path.strip() for path in self.paths if path.strip()],
            "output_subfolder": self.draft["output_subfolder"].strip(),
        }

    @Slot("QVariantList")
    def enqueueFolders(self, urls):
        if not self.ready or self.busy:
            return
        files = [url if isinstance(url, QUrl) else QUrl(url) for url in urls]
        paths = [url.toLocalFile() for url in files if url.isLocalFile()]
        if not paths or not self.models_present():
            self.drop_message = (
                "Lade zuerst die Modelle für die gewählte Konfiguration herunter."
                if paths
                else "Lege einen Ordner aus dem Dateimanager ab."
            )
            self.drop_error = True
            self.changed.emit()
            return

        settings = {
            **self.draft,
            "folders": [],
            "monitoring": False,
            "include_subfolders": True,
            "create_output_subfolder": False,
            "dropped_folders": paths,
        }
        self.busy = True
        self.drop_message = "Ordner werden für die Warteschlange durchsucht …"
        self.drop_error = False
        self.changed.emit()

        def queue():
            result = with_settings(
                settings, lambda file: json.loads(command("enqueue-folders", file))
            )
            if result["queued"] or result["pending"]:
                if not CONFIG.exists():
                    save_settings(DEFAULTS)
                command("start", CONFIG)
            return result

        def queued(result, error):
            self.busy = False
            if error:
                self.drop_message, self.drop_error = error, True
            else:
                count, skipped = result["queued"], result["skipped"]
                parts = []
                if count:
                    parts.append(
                        "1 Aufnahme eingereiht."
                        if count == 1 else f"{count} Aufnahmen eingereiht."
                    )
                if skipped:
                    parts.append(
                        "1 Aufnahme war bereits erfasst."
                        if skipped == 1 else f"{skipped} Aufnahmen waren bereits erfasst."
                    )
                warnings = result["warnings"]
                if warnings:
                    parts.append(warnings[0])
                    if len(warnings) > 1:
                        parts.append(f"Weitere Meldungen: {len(warnings) - 1}.")
                self.drop_message = "\n".join(parts) or "Keine Mediendateien gefunden."
                self.drop_error = bool(warnings)
            self.changed.emit()
            self.refresh()

        self.submit(queue, queued)

    @Slot(bool)
    def save(self, start):
        if start and not self.models_present():
            self.notify(
                "Lade zuerst die Modelle für die gewählte Konfiguration herunter.", True
            )
            return
        settings = self.config()

        def save_and_start():
            save_settings(settings)
            if start:
                command("start", CONFIG)

        self.direct.clear()
        self.next_probe = 0
        self.action(
            save_and_start,
            "Hintergrunddienst wird gestartet."
            if start
            else "Einstellungen gespeichert.",
        )

    @Slot(bool)
    def setAutostart(self, enabled):
        settings = self.config()

        def register():
            if enabled:
                save_settings(settings)
            if sys.platform == "win32":
                windows_login_item(enabled)
            else:
                command("autostart", "on" if enabled else "off", CONFIG)

        self.action(
            register,
            "Start bei der Anmeldung aktiviert."
            if enabled
            else "Start bei der Anmeldung deaktiviert.",
        )

    @Slot()
    def toggleMonitor(self):
        if not self.snapshot.get("running"):
            self.save(True)
            return
        settings = read_settings()
        settings["monitoring"] = not settings["monitoring"]
        self.draft["monitoring"] = settings["monitoring"]
        self.action(lambda: save_settings(settings), "Ordnerüberwachung aktualisiert.")

    def models_present(self):
        if self.preview:
            return True
        model_root = MODEL_DATA / "models"
        selected = self.draft["model"]
        if selected == "large-v3-turbo":
            present = (model_root / selected / "model.bin").is_file()
        else:
            filename = (
                "qwen-windows-models.json"
                if sys.platform == "win32"
                else "qwen-models.json"
            )
            manifest = json.loads((ENGINE / filename).read_text(encoding="utf-8"))
            present = all(
                (model_root / name / file).is_file()
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
            not self.draft["speakers"]
            or all(
                (model_root / "speaker-detection" / file).is_file()
                for file in speaker_files
            )
        )

    @Slot()
    def downloadModels(self):
        selected = self.draft["model"]
        flags = [] if self.draft["speakers"] else ["--no-speakers"]

        def download():
            app = ROOT.parent.parent
            if (
                sys.platform == "darwin"
                and PROFILE == NATIVE_PROFILE
                and app.suffix == ".app"
                and app.parent.name != "VoxDrop"
            ):
                raise RuntimeError(
                    "Ziehe den gesamten Ordner „VoxDrop“ aus der DMG in den Programme-Ordner "
                    "und öffne darin VoxDrop.app. Dort werden auch die Modelle gespeichert."
                )
            try:
                MODEL_DATA.mkdir(parents=True, exist_ok=True)
                with NamedTemporaryFile(dir=MODEL_DATA, prefix=".write-check-"):
                    pass
            except OSError as error:
                raise RuntimeError(
                    f"Der Modellspeicher ist nicht beschreibbar: {MODEL_DATA}. "
                    "Installiere den VoxDrop-Ordner in einem beschreibbaren Programme-Ordner."
                ) from error
            return command("setup-models", "--model", selected, *flags)

        self.action(
            download,
            "Modelle sind einsatzbereit.",
            downloading=True,
        )

    @Slot()
    def openLog(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DESKTOP_LOG)))

    @Slot(str)
    def checkFolders(self, path):
        self.check_folders(path)

    def check_folders(self, path="", *, automatic=False):
        if self.checking:
            return
        self.checking = True
        settings = self.config()
        if path:
            settings["folders"] = [path]
        if not automatic:
            self.notify("Ordner werden geprüft …")

        def finished(result, error):
            self.checking = False
            if error:
                if not automatic:
                    self.notify(error, True)
                return
            for item in result:
                self.direct[item["path"]] = {**item, "updated": time()}
            if not automatic:
                self.notify("Ordnerprüfung abgeschlossen.")
            self.update_status()

        self.submit(
            lambda: with_settings(
                settings, lambda file: json.loads(command("check", file))
            ),
            finished,
        )

    def refresh(self):
        if self.preview or self.refreshing or not self.ready:
            return
        self.refreshing = True
        order = self.order

        def finished(result, error):
            self.refreshing = False
            if error:
                self.notify(error, True)
                return
            self.snapshot = result
            if not result.get("running") and time() >= self.next_probe:
                self.next_probe = time() + self.draft["interval_seconds"]
                if self.paths:
                    self.check_folders(automatic=True)
            self.update_status()
            self.update_history()
            if order != self.order:
                self.refresh()

        self.submit(
            lambda: json.loads(command("status", "--limit", "250", "--order", order)),
            finished,
        )

    def folder_status(self, path):
        path = path.strip()
        status = next(
            (row for row in self.snapshot.get("folders", []) if row["path"] == path), {}
        )
        direct = self.direct.get(path, {})
        if direct and (status.get("updated") or 0) <= direct["updated"]:
            return direct
        return status or direct

    def init_tray(self):
        if self.preview or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(waveform(TRAY_DISCONNECTED), self)
        self.menu = QMenu()
        self.status_action = self.menu.addAction("VoxDrop")
        self.status_action.setEnabled(False)
        self.menu.addAction("Hauptfenster öffnen", self.windowRequested.emit)
        self.monitor_action = self.menu.addAction("Dienst starten", self.toggleMonitor)
        self.menu.addSeparator()
        self.menu.addAction("Oberfläche beenden", QApplication.instance().quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()
        self.update_status()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.windowRequested.emit()

    @Slot(result=bool)
    def hasTray(self):
        return self.tray is not None and self.tray.isVisible()

    def update_status(self):
        if self.tray:
            paths = [self.folder_status(path) for path in self.paths if path.strip()]
            available = bool(paths) and all(
                path.get("available") and not path.get("error") for path in paths
            )
            label = (
                "Alle Ordner verfügbar"
                if available
                else ("Ordner prüfen" if paths else "Keine Ordner eingerichtet")
            )
            self.status_action.setText(label)
            self.tray.setToolTip(f"VoxDrop – {label}")
            self.tray.setIcon(waveform(TRAY_CONNECTED if available else TRAY_DISCONNECTED))
            running = self.snapshot.get("running")
            self.monitor_action.setText(
                (
                    "Ordnerüberwachung pausieren"
                    if self.draft["monitoring"]
                    else "Ordnerüberwachung fortsetzen"
                )
                if running
                else "Dienst starten"
            )
            self.monitor_action.setEnabled(self.ready and not self.busy)
            if running:
                for path in paths:
                    if path.get("error") and (incident := path.get("incident")):
                        key = "incidents/" + path["path"]
                        if self.preferences.value(key) != incident:
                            self.tray.showMessage(
                                "VoxDrop – Ordner nicht verfügbar",
                                f"{path['path']}\n{path['error']}",
                                QSystemTrayIcon.MessageIcon.Warning,
                            )
                            self.preferences.setValue(key, incident)
        self.changed.emit()

    @Slot(str)
    def setFilter(self, value):
        self.filter = value
        self.changed.emit()
        self.update_history()

    @Slot(str)
    def setOrder(self, value):
        self.order = value
        self.preferences.setValue("historyOrder", value)
        self.changed.emit()
        self.update_history()
        self.refresh()

    def update_history(self):
        jobs = self.snapshot.get("jobs", [])
        if self.filter != "all":
            states = {"done"} if self.filter == "done" else {"blocked", "failed"}
            jobs = [job for job in jobs if job["state"] in states]
        jobs = sorted(
            jobs,
            key=lambda job: (job["updated"], job["id"]),
            reverse=self.order == "desc",
        )
        history = []
        for job in jobs:
            finished = job.get("finished") if job["state"] == "done" else None
            history.append(
                {
                    "id": job["id"],
                    "name": Path(job["source"]).name,
                    "path": str(output_path(job)),
                    "status": STATES.get(job["state"], job["state"]),
                    "updated": clock(job["updated"], "%d.%m.%Y"),
                    "audio": duration(job.get("audio_seconds"), all_units=True),
                    "start": clock(job.get("transcription_started")),
                    "elapsed": duration(total_duration(job)),
                    "end": clock(finished),
                    "finished": finished,
                    "repeat": bool(job.get("origin_job_id")),
                    "error": job["state"] in {"blocked", "failed"},
                }
            )
        if history != self.history:
            self.history = history
            self.historyChanged.emit()

    @Slot(int)
    def showDetails(self, identifier):
        selected = next(
            (job for job in self.snapshot.get("jobs", []) if job["id"] == identifier),
            None,
        )
        if selected:
            self.selected = selected
            self.changed.emit()
            self.detailsOpened.emit()

    @Slot(bool)
    def retryJob(self, repeat):
        if self.selected is None:
            return
        identifier = self.selected["id"]
        if repeat:
            draft = self.config()
            self.action(
                lambda: with_settings(
                    draft, lambda file: command("retranscribe", identifier, file)
                ),
                "Neutranskription eingereiht.",
            )
        else:
            self.action(
                lambda: command("retry", identifier), "Auftrag erneut eingereiht."
            )

    @Slot()
    def revealOutput(self):
        if self.selected is not None:
            path = output_path(self.selected, transcript=True)
            if sys.platform == "win32":
                subprocess.Popen(["explorer.exe", f"/select,{path}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["/usr/bin/open", "-R", str(path)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    @Slot()
    def clearHistory(self):
        self.action(lambda: command("clear-history"), "Verlauf geleert.")

    @Slot(result="QVariantMap")
    def columnWidths(self):
        return {
            "left": self.preferences.value("columns/left", 340, type=int),
            "right": self.preferences.value("columns/right", 424, type=int),
        }

    @Slot(int, int)
    def saveColumnWidths(self, left, right):
        self.preferences.setValue("columns/left", left)
        self.preferences.setValue("columns/right", right)
        self.preferences.sync()
