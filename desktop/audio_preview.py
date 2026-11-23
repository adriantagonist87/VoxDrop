"""On-demand audio-only preview of a local original, independent of inference."""
import os
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot


def clock(milliseconds):
    seconds = max(0, int(milliseconds) // 1000)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


class AudioPreview(QObject):
    changed = Signal()
    volumeChanged = Signal(float)

    def __init__(self, parent=None, *, volume=70):
        super().__init__(parent)
        self._player = None
        self._output = None
        self._path = ""
        self._error = ""
        self._loading = False
        self._volume = max(0., min(100., float(volume)))

    @Property("QVariantMap", notify=changed)
    def state(self):
        player = self._player
        position = player.position() if player and self._path else 0
        duration = player.duration() if player and self._path else 0
        return dict(available=bool(self._path), name=Path(self._path).name if self._path else "",
                    playing=bool(player and player.isPlaying()), loading=self._loading,
                    seekable=bool(player and player.isSeekable() and duration > 0),
                    position=position, duration=duration, positionText=clock(position),
                    durationText=clock(duration), volume=self._volume, error=self._error)

    def _ensure_player(self):
        if self._player is not None:
            return
        # This preview needs no video or hardware decoder. Inference keeps its
        # own CUDA/Metal configuration and is never started by the player.
        os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", ",")
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        self._player = QMediaPlayer(self)
        self._output = QAudioOutput(self)
        self._output.setVolume(self._volume / 100.)
        self._player.setAudioOutput(self._output)
        for signal in (self._player.positionChanged, self._player.durationChanged,
                       self._player.playbackStateChanged, self._player.seekableChanged):
            signal.connect(self.changed)
        self._player.tracksChanged.connect(self._disable_video)
        self._player.mediaStatusChanged.connect(self._media_status)
        self._player.errorOccurred.connect(self._media_error)

    def _disable_video(self):
        self._player.setActiveVideoTrack(-1)
        self._player.setActiveSubtitleTrack(-1)

    def _media_status(self, status):
        from PySide6.QtMultimedia import QMediaPlayer
        self._loading = status in (QMediaPlayer.MediaStatus.LoadingMedia,
                                   QMediaPlayer.MediaStatus.BufferingMedia,
                                   QMediaPlayer.MediaStatus.StalledMedia)
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self._disable_video()
            if not self._player.hasAudio():
                self._error = "Die Originaldatei enthält keine abspielbare Tonspur."
                self._player.setSource(QUrl())
        self.changed.emit()

    def _media_error(self, error, message):
        self._loading = False
        self._error = "Audio konnte nicht abgespielt werden: " + (message or "Format oder Datei nicht verfügbar.")
        self.changed.emit()

    def play_file(self, path):
        try:
            self._ensure_player()
        except (ImportError, RuntimeError) as error:
            self._error = f"Der Audioplayer konnte nicht geladen werden: {error}"
            self.changed.emit()
            return
        path = str(path)
        if path != self._path or self._error:
            self.close()
            self._path = path
            self._loading = True
            self._player.setSource(QUrl.fromLocalFile(path))
        self.toggle()

    @Slot()
    def toggle(self):
        if self._player is None or not self._path:
            return
        if self._error:
            self.play_file(self._path)
            return
        if self._player.isPlaying():
            self._player.pause()
        else:
            if self._player.duration() and self._player.position() >= self._player.duration():
                self._player.setPosition(0)
            self._player.play()
        self.changed.emit()

    @Slot(float)
    def seek(self, milliseconds):
        if self._player and self._player.isSeekable():
            self._player.setPosition(max(0, min(int(milliseconds), self._player.duration())))

    @Slot(float)
    def setVolume(self, percent):
        self._volume = max(0., min(100., float(percent)))
        if self._output:
            self._output.setVolume(self._volume / 100.)
        self.volumeChanged.emit(self._volume)
        self.changed.emit()

    @Slot()
    def close(self):
        self._path = ""
        self._loading = False
        self._error = ""
        if self._player:
            # Clearing the source also stops playback and releases the file.
            self._player.setSource(QUrl())
        self.changed.emit()
