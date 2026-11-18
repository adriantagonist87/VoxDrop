"""Shared controller for the VoxDrop desktop interface."""

import json
import os
import subprocess
import sys
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Event
from time import time

from model_storage import data_directory
from file_actions import reveal_in_explorer
from transcript_search import path_matches, run_content_search, transcript_path, history_category
from network_wait import NetworkPermissionError, retry_network_permission
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
    "cancelled": "Abgebrochen",
    "existing": "TXT bereits vorhanden",
    "duplicate": "Bereits transkribiert (gleicher Inhalt)",
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
        traceback = "Traceback (most recent call last):" in details
        if traceback or arguments[0] == "setup-models":
            with suppress(OSError):
                DESKTOP_LOG.parent.mkdir(parents=True, exist_ok=True)
                with DESKTOP_LOG.open("a", encoding="utf-8") as log:
                    log.write(
                        f"\n{datetime.now().isoformat(timespec='seconds')} · {arguments[0]}\n{details}\n"
                    )
        if arguments[0] == "setup-models" and "WinError 10013" in details:
            raise NetworkPermissionError(
                "Für den Modell-Download wurde die Netzwerkverbindung verweigert (Windows-Fehler 10013)."
            )
        if traceback:
            if arguments[0] == "setup-models":
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
        file.flush()
        os.fsync(file.fileno())
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
    if transcript:
        return transcript_path(job)
    source = Path(job["source"])
    archived = Path(job["completed_dir"]) / source.name
    settings = job_settings(job)
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
    queueChanged = Signal()
    contentSearchProgress = Signal(int, str)
    dropConflictOpened = Signal()
    dropResolved = Signal()
    detailsOpened = Signal()
    windowRequested = Signal()
    networkPermissionChanged = Signal(bool)
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
        self.queue = []
        self.queue_all = []
        self.queue_query = ''
        self.history_query = ''
        self.content_token = ''
        self.content_running = False
        self.content_status = ''
        self.content_cancel = Event()
        self.content_done = Event()
        self.content_done.set()
        self.clearing = False
        self.reset_generation = 0
        self.content_generation = 0
        self.contentSearchProgress.connect(self.content_search_progress)
        QApplication.instance().aboutToQuit.connect(self.content_cancel.set)
        self.queue_dragging = False
        self.queue_compact = self.preferences.value("queueCompact", True, type=bool)
        self.order = self.preferences.value("historyOrder", "desc")
        self.filter = "all"
        self.ready = preview
        self.busy = False
        self.downloading = False
        self.waiting_for_network = False
        self.network_cancel = Event()
        self.networkPermissionChanged.connect(self.network_permission_changed)
        QApplication.instance().aboutToQuit.connect(self.network_cancel.set)
        self.message = ""
        self.message_error = False
        self.drop_message = ""
        self.drop_error = False
        self.drop_plan = {}
        self.drop_backlog = []
        self.drop_timer = QTimer(self, interval=250)
        self.drop_timer.timeout.connect(self.drain_drops)
        self.refreshing = False
        self.checking = False
        self.next_probe = 0
        self.tray = None
        self.timer = QTimer(self, interval=2000)
        self.timer.timeout.connect(self.refresh)
        self.history_search_timer = QTimer(self, interval=180, singleShot=True)
        self.history_search_timer.timeout.connect(self.refresh)

    settings = Property("QVariantMap", lambda self: self.draft, notify=changed)
    folderPaths = Property(
        "QStringList", lambda self: self.paths, notify=foldersChanged
    )
    historyItems = Property(
        "QVariantList", lambda self: self.history, notify=historyChanged
    )
    queueItems = Property('QVariantList',lambda self:self.queue,notify=queueChanged)
    dropPlan = Property('QVariantMap', lambda self: self.drop_plan, notify=changed)

    @Property("QVariantMap", notify=changed)
    def state(self):
        running = self.snapshot.get("running", False)
        service = self.snapshot.get("service") or {}
        job = self.snapshot.get("current")
        current = {}
        if job:
            settings = job_settings(job)
            current = {
                "id": job['id'],
                "name": Path(job["source"]).name,
                "phase": 'Wird abgebrochen …' if job.get('cancel_requested') else job.get("phase") or STATES.get(job["state"], job["state"]),
                "progress": job.get("progress"),
                "elapsed": duration(time() - job["started"])
                if job.get("started")
                else "",
                "model": MODELS.get(settings.get("model"), MODELS["large-v3-turbo"]),
                "hardware": GPU_NAME.get(settings.get("hardware"), "CPU"),
                "canCancel": job['state'] in ('copying','transcribing') and not job.get('publication_started') and not job.get('cancel_requested'),
            }
        checked = {path: self.folder_status(path) for path in self.paths}
        return {
            "ready": self.ready,
            "busy": self.busy,
            "downloading": self.downloading,
            "waitingForNetwork": self.waiting_for_network,
            "running": running,
            "service": STATES.get(service.get("state"), "Aktiv")
            if running
            else "Dienst aus",
            "serviceError": service.get("error") or "",
            "current": current,
            "waiting": self.snapshot.get("waiting", 0),
            "queueCount": len(self.snapshot.get('queue',[])),
            "queuePaused": self.snapshot.get('queue_paused',False),
            "queueImmediateCount": self.snapshot.get('immediate_count', 0),
            "queueCompact": self.queue_compact,
            "queueSearch": self.queue_query,
            "historySearch": self.history_query,
            "contentSearchRunning": self.content_running,
            "contentSearchStopping": self.content_running and self.content_cancel.is_set(),
            "contentSearchActive": bool(self.content_token),
            "contentSearchStatus": self.content_status,
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
            "historyCounts": self.history_counts(),
            "order": self.order,
            "canClear": bool(self.snapshot.get('has_stored_data',self.snapshot.get('stored_jobs',0)
                or self.snapshot.get('jobs') or self.snapshot.get('queue') or self.history_counts()['all'])) and not job and not self.busy,
        }

    @Property("QVariantMap", notify=changed)
    def detail(self):
        if self.selected is None:
            return {}
        job = self.selected
        settings = job_settings(job)
        speakers = settings.get("speakers", True)
        known_result = job.get('result_kind') in ('existing','reused','duplicate')
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
            "note": ({'existing':'Vorhandene TXT-Datei erkannt. Inhalt und Aufnahme wurden nicht durch VoxDrop gegengeprüft.',
                      'reused':f"Identischer Dateiinhalt: Ergebnis aus Auftrag {job.get('prior_job_id')} übernommen; keine erneute KI-Verarbeitung.",
                      'duplicate':f"Identischer Dateiinhalt wurde bereits in Auftrag {job.get('prior_job_id')} verarbeitet. Das frühere TXT ist nicht mehr unverändert verfügbar; bei Bedarf neu transkribieren."}.get(job.get('result_kind')) or job.get("speaker_note") or ""),
            "retry": job["state"] in {"blocked", "failed", "cancelled"},
            "repeat": job["state"] in {"done", "blocked", "failed", "cancelled", "existing", "duplicate"},
            "reveal": job["state"] in {'done','existing'} or bool(job.get('known_transcript_path')),
            "openTranscript": job['state'] in {'done','existing'} or bool(job.get('known_transcript_path')),
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
                        ('Nicht bekannt (Bestandsdatei)' if job.get('result_kind')=='existing'
                         else 'Siehe Ursprungsauftrag') if known_result
                        else MODELS.get(settings.get("model"), MODELS["large-v3-turbo"]),
                    ),
                    (
                        "RAM-Auslastung verursacht",
                        f"{memory / 2**30:.2f} GiB Spitze".replace(".", ",")
                        if memory
                        else "—",
                    ),
                    ("Dauer Spracherkennung", 'Nicht erneut ausgeführt' if known_result else duration(job.get("speech_seconds"))),
                    (
                        "Verfahren der Sprecherzuordnung",
                        'Nicht neu bestimmt' if known_result else method if speakers else "Deaktiviert",
                    ),
                    (
                        "Dauer Sprecherzuordnung",
                        'Nicht erneut ausgeführt' if known_result else duration(job.get("speaker_seconds"))
                        if speakers
                        else "Deaktiviert",
                    ),
                    ("Dauer gesamt", duration(total_duration(job))),
                    ("Rechengerät", 'Keine neue Inferenz' if known_result else GPU_NAME.get(settings.get("hardware"), "CPU")),
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

    @Slot(bool)
    def network_permission_changed(self, waiting):
        self.waiting_for_network = waiting
        if self.downloading:
            self.notify(
                "Netzwerkzugriff verweigert (Windows 10013). Falls eine Freigabeanfrage erscheint, "
                "bestätige sie selbst. Ohne sichtbare Anfrage prüfe das Protokoll. "
                "VoxDrop versucht den Download alle fünf Sekunden erneut."
                if waiting else "Modelle werden heruntergeladen und geprüft …"
            )

    @Slot()
    def cancelNetworkWait(self):
        self.network_cancel.set()

    def action(self, operation, success, *, downloading=False):
        if self.busy or not self.ready:
            return
        self.busy = True
        self.downloading = downloading
        if downloading:
            self.network_cancel.clear()
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
            if (background or resume or (sys.platform == "win32" and settings.get("monitoring"))) and CONFIG.is_file():
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
        if not self.ready:
            return
        if self.busy or self.drop_plan:
            self.drop_backlog.extend(urls)
            self.drop_timer.start()
            self.drop_message = 'Weitere abgelegte Dateien/Ordner werden anschließend gemeinsam geprüft.'
            if self.drop_plan:
                self.drop_plan = {**self.drop_plan, 'notice': self.drop_message}
            self.changed.emit()
            return
        files = [url if isinstance(url, QUrl) else QUrl(url) for url in urls]
        paths = [url.toLocalFile() for url in files if url.isLocalFile()]
        if not paths or not self.models_present():
            self.drop_message = (
                "Lade zuerst die Modelle für die gewählte Konfiguration herunter."
                if paths
                else "Lege Dateien oder Ordner aus dem Dateimanager ab."
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
        self.drop_message = "Dateien und Ordner werden auf bestehende Aufträge geprüft …"
        self.drop_error = False
        self.changed.emit()

        def queue():
            plan = with_settings(
                settings, lambda file: json.loads(command("prepare-drop", file))
            )
            if not plan['has_conflicts']:
                plan['result'] = json.loads(command('resolve-drop', plan['token'], 'queue'))
                self.ensure_drop_service(plan['result'])
            return plan

        def queued(result, error):
            self.busy = False
            if error:
                self.drop_message, self.drop_error = error, True
            else:
                if 'result' in result:
                    self.show_drop_result(result['result'])
                else:
                    self.drop_plan = result
                    self.drop_message = 'Bereits bekannte Aufnahmen oder Probleme gefunden. Bitte im Dialog entscheiden.'
                    self.drop_error = bool(result['warnings'])
                    self.changed.emit()
                    self.dropConflictOpened.emit()
            self.changed.emit()
            self.refresh()

        self.submit(queue, queued)

    def ensure_drop_service(self, result):
        if result['pending']:
            if not CONFIG.exists():
                save_settings(DEFAULTS)
            command('start', CONFIG)

    def drain_drops(self):
        if not self.drop_backlog:
            self.drop_timer.stop()
        elif self.ready and not self.busy and not self.drop_plan:
            urls, self.drop_backlog = self.drop_backlog, []
            self.drop_timer.stop()
            self.enqueueFolders(urls)

    def show_drop_result(self, result):
        self.drop_message = (f"Neu eingereiht: {result['queued']}. Auswahl berücksichtigt: {result['selected']}. "
                             f"Ignoriert: {result['ignored']}. Bereits laufend: {result['active']}.")
        if result.get('interrupted'):
            self.drop_message += ' Der unterbrochene Auftrag wird anschließend erneut verarbeitet.'
        if result.get('export_finishes'):
            self.drop_message += ' Der begonnene Export wird zuerst sicher abgeschlossen.'
        if result.get('queue_remains_paused'):
            self.drop_message += ' Die übrige Warteschlange bleibt pausiert.'
        self.drop_error = bool(result['warnings'])
        if result['warnings']:
            self.drop_plan = dict(resolved=True, items=[], counts={}, warnings=result['warnings'], message=self.drop_message)
            self.changed.emit()
            self.dropConflictOpened.emit()
        else:
            self.drop_plan = {}
            self.dropResolved.emit()

    @Slot(str)
    def resolveDrop(self, action):
        if self.busy or not self.drop_plan or self.drop_plan.get('resolved'):
            return
        token = self.drop_plan['token']
        self.busy = True
        self.changed.emit()
        def apply():
            result = json.loads(command('resolve-drop', token, action))
            self.ensure_drop_service(result)
            return result
        def finished(result, error):
            self.busy = False
            if error:
                self.drop_plan = {**self.drop_plan, 'error': error}
                self.drop_error = True
            else:
                self.show_drop_result(result)
            self.changed.emit()
            self.refresh()
        self.submit(apply, finished)

    @Slot()
    def dismissDrop(self):
        if self.busy:
            return
        if not self.drop_plan.get('resolved'):
            self.drop_message = 'Drop verworfen. Bestehende Aufträge bleiben unverändert.'
            self.drop_error = False
        self.drop_plan = {}
        self.changed.emit()
        self.dropResolved.emit()

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
            return retry_network_permission(
                lambda: command("setup-models", "--model", selected, *flags),
                self.network_cancel,
                self.networkPermissionChanged.emit,
            )

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
        if self.preview or self.refreshing or not self.ready or self.clearing:
            return
        self.refreshing = True
        order = self.order
        history_filter = self.filter
        query, token = self.history_query, self.content_token
        reset_generation=self.reset_generation

        def finished(result, error):
            self.refreshing = False
            if self.clearing or reset_generation!=self.reset_generation:
                self.refresh()
                return
            if error:
                self.notify(error, True)
                return
            if (order, history_filter, query, token) != (self.order, self.filter, self.history_query, self.content_token):
                self.refresh()
                return
            self.snapshot = result
            if not result.get("running") and time() >= self.next_probe:
                self.next_probe = time() + self.draft["interval_seconds"]
                if self.paths:
                    self.check_folders(automatic=True)
            self.update_status()
            self.update_history()
            self.update_queue()
        def status():
            arguments = ['status', '--limit', '250', '--order', order, '--filter', history_filter,
                         '--search', query]
            if token:
                arguments += ['--content-results', str(PROFILE / 'service/content-search-result.json'),
                              '--content-token', token]
            return json.loads(command(*arguments))
        self.submit(status, finished)

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
        self.refresh()

    @Slot(str)
    def setOrder(self, value):
        self.order = value
        self.preferences.setValue("historyOrder", value)
        self.changed.emit()
        self.update_history()
        self.refresh()

    def history_counts(self):
        counts = self.snapshot.get("history_counts")
        if counts is not None:
            return counts
        jobs = self.snapshot.get("jobs", [])
        counts={key:0 for key in ('all','errors','done','cancelled','existing')}
        for job in jobs:
            category=history_category(job)
            if category:
                counts[category]+=1
                counts['all']+=category!='existing'
        return counts

    def update_history(self):
        jobs = self.snapshot.get("jobs", [])
        jobs=[job for job in jobs if history_category(job) in (
            {'done','errors','cancelled'} if self.filter=='all' else {self.filter})]
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
                    "status": 'Ergebnis übernommen' if job.get('result_kind')=='reused' else STATES.get(job["state"], job["state"]),
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

    def update_queue(self):
        if self.queue_dragging:
            return
        queue=[]
        for position, job in enumerate(self.snapshot.get('queue',[]), 1):
            settings=job_settings(job)
            size=job['size']
            queue.append(dict(
                id=job['id'],position=position,name=Path(job['source']).name,path=job['source'],
                status=('Aufnahme läuft / Datei gesperrt' if (job.get('error') or '').startswith('Aufnahme wird noch geschrieben') else 'Wartet auf Wiederholung') if job['state']=='failed' else STATES.get(job['state'],job['state']),
                size=f'{size/2**30:.2f} GiB' if size>=2**30 else f'{size/2**20:.1f} MiB',
                model=MODELS.get(settings.get('model'),settings.get('model','—')),
                language={'auto':'Automatisch','de':'Deutsch','en':'Englisch'}.get(settings.get('language'),'—'),
                hardware=GPU_NAME.get(settings.get('hardware'),'CPU'),
                audio=duration(job.get('audio_seconds')),added=clock(job['detected'],'%d.%m. %H:%M'),
                retryAt=clock(job.get('retry_at')) if job.get('retry_at') else '',
                options=' · '.join(name for name,key in [('Stille','skip_silence'),('Sprecher','speakers'),('DOVER','dover_lap')] if settings.get(key)),
            ))
        self.queue_all = queue
        self.apply_queue_search()

    def apply_queue_search(self):
        queue = [job for job in self.queue_all if path_matches(job['path'], self.queue_query)] if self.queue_query else self.queue_all
        if queue != self.queue:
            self.queue = queue
            self.queueChanged.emit()

    @Slot(str)
    def setQueueSearch(self, query):
        self.queue_query = query
        self.apply_queue_search()
        self.changed.emit()

    @Slot(str)
    def setHistorySearch(self, query):
        if query == self.history_query:
            return
        self.history_query = query
        self.content_token = ''
        if self.content_running:
            self.content_cancel.set()
            self.content_status = 'Detailsuche wird beendet …'
        else:
            self.content_status = ''
        self.changed.emit()
        self.history_search_timer.start()

    @Slot(int, str)
    def content_search_progress(self, generation, text):
        if generation == self.content_generation and self.content_running and not self.content_cancel.is_set():
            self.content_status = text
            self.changed.emit()

    @Slot()
    def startContentSearch(self):
        if self.content_running or self.busy or not self.history_query.strip():
            return
        self.content_generation += 1
        generation, query = self.content_generation, self.history_query
        self.content_cancel.clear()
        self.content_done.clear()
        self.content_token = ''
        self.content_running = True
        self.content_status = 'Detailsuche wird vorbereitet …'
        self.changed.emit()

        def search():
            if str(ENGINE) not in sys.path:
                sys.path.append(str(ENGINE))
            from platform_io import child_process
            try:
                return run_content_search(PROFILE / 'service/jobs.sqlite3', PROFILE / 'service/transcript-search.sqlite3',
                    PROFILE / 'service/content-search-result.json', query, self.content_cancel,
                    lambda text: self.contentSearchProgress.emit(generation, text),
                    lambda arguments, **options: child_process(arguments, cancellable=True, **options))
            finally:
                self.content_done.set()

        def finished(result, error):
            if generation != self.content_generation:
                return
            self.content_running = False
            if self.content_cancel.is_set() or query != self.history_query:
                self.content_status = 'Detailsuche gestoppt. Dateiname/Pfad wird weiter gefiltert.'
            elif error:
                self.content_status = error
            else:
                self.content_token = result['token']
                self.content_status = (f"Detailsuche: {result['matches']} Inhaltstreffer · "
                    f"{result['files']} Dateien geprüft · {result['skipped']} übersprungen")
            self.changed.emit()
            self.refresh()
        self.submit(search, finished)

    @Slot()
    def stopContentSearch(self):
        self.content_cancel.set()
        self.content_token = ''
        self.content_status = 'Detailsuche wird beendet …' if self.content_running else ''
        self.changed.emit()
        self.refresh()

    @Slot(bool)
    def setQueueCompact(self, compact):
        self.queue_compact = compact
        self.preferences.setValue("queueCompact", compact)
        self.preferences.sync()
        self.changed.emit()

    @Slot(bool)
    def setQueueDragging(self, active):
        self.queue_dragging=active
        if not active:
            self.update_queue()

    @Slot(int,int)
    def moveQueueItem(self, identifier, before):
        self.action(lambda:command('move-queue',identifier,before),'Reihenfolge gespeichert.')

    @Slot(int,str)
    def moveQueueRelative(self, identifier, direction):
        self.action(lambda:command('move-queue-relative',identifier,direction),'Reihenfolge gespeichert.')

    @Slot(int,int,bool)
    def moveQueueDrop(self, identifier, anchor, after):
        arguments = ['move-queue',identifier,anchor] + (['--after'] if after else [])
        self.action(lambda:command(*arguments),'Reihenfolge gespeichert.')

    @Slot(int)
    def cancelJob(self, identifier):
        self.action(lambda:command('cancel-job',identifier),'Auftrag wird abgebrochen; Originaldatei bleibt erhalten.')

    @Slot()
    def cancelQueue(self):
        self.action(lambda:command('cancel-queue'),'Warteschlange abgebrochen und pausiert.')

    @Slot(bool)
    def pauseQueue(self, paused):
        self.action(lambda:command('queue-pause','on' if paused else 'off'),
                    'Warteschlange pausiert; aktueller Auftrag läuft weiter.' if paused else 'Warteschlange fortgesetzt.')

    @Slot(int)
    def showDetails(self, identifier):
        selected = next(
            (job for job in [*self.snapshot.get("jobs", []),*self.snapshot.get('queue',[]),*([self.snapshot['current']] if self.snapshot.get('current') else [])] if job["id"] == identifier),
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
    def openTranscript(self):
        if self.selected is None or self.selected['state'] not in ('done','existing','duplicate'):
            return
        path=output_path(self.selected,transcript=True)

        def checked(result,error):
            if error:
                self.notify(error,True)
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(result))):
                self.notify('Das Transkript konnte mit der Standardanwendung nicht geöffnet werden.',True)

        def locate():
            if not path.is_file():
                raise FileNotFoundError('Die TXT-Datei ist nicht mehr am gespeicherten Ausgabeort vorhanden.')
            return path

        self.submit(locate,checked)

    @Slot()
    def revealOutput(self):
        if self.selected is not None:
            path = output_path(self.selected, transcript=True)
            if sys.platform == "win32":
                def revealed(result, error):
                    if error:
                        self.notify(error, True)
                self.submit(lambda: reveal_in_explorer(path), revealed)
            elif sys.platform == "darwin":
                subprocess.Popen(["/usr/bin/open", "-R", str(path)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    @Slot()
    def clearHistory(self):
        if self.busy or not self.ready or self.snapshot.get('current'):
            return
        self.busy=True
        self.clearing=True
        self.reset_generation+=1
        self.history_search_timer.stop()
        self.content_cancel.set()
        self.content_token=''
        self.history_query=''
        self.notify('Auftragsdaten und Suchindex werden bereinigt …')

        def clear():
            if not self.content_done.wait(10):
                raise RuntimeError('Die Detailsuche konnte noch nicht beendet werden. Bitte erneut versuchen.')
            return command('clear-history')

        def cleared(result,error):
            self.clearing=False
            self.busy=False
            if not error:
                self.filter='all'
                self.selected=None
                self.drop_plan={}
                self.drop_backlog=[]
                self.dropResolved.emit()
                self.content_status=''
                self.snapshot.update(jobs=[],queue=[],stored_jobs=0,has_stored_data=False,
                    history_counts={key:0 for key in ('all','errors','done','cancelled','existing')})
                self.update_history()
                self.update_queue()
            self.notify(error or 'Auftragsdaten und Suchindex geleert. Aktive Ordnerüberwachung liest beim nächsten Intervall neu ein.',bool(error))
            self.refresh()
        self.submit(clear,cleared)

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
