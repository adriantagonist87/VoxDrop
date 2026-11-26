from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import Mock

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer

from desktop.audio_preview import AudioPreview, clock


class AudioPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.media = self.root / "Prüfton Ä.wav"
        with wave.open(str(self.media), "wb") as output:
            output.setparams((1, 2, 16_000, 0, "NONE", "not compressed"))
            output.writeframes(b"\x00\x00" * 16_000 * 4)
        self.player = AudioPreview(volume=0)
        self.addCleanup(self.dispose)

    def dispose(self):
        self.player.close()
        self.player.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def wait_for(self, predicate):
        for _ in range(200):
            if predicate():
                return
            QTest.qWait(25)
        self.fail(f"Audio condition timed out: {self.player.state}")

    def test_preview_is_lazy_and_does_not_open_a_file_on_construction(self):
        self.assertIsNone(self.player._player)
        self.assertFalse(self.player.state["available"])
        self.player.setVolume(42)
        self.assertEqual(self.player.state["volume"], 42)
        self.assertIsNone(self.player._player)

    def test_long_recording_clock_keeps_hours(self):
        self.assertEqual(clock(3_661_999), "1:01:01")
        self.assertEqual(clock(59_000), "00:59")

    def test_real_wav_play_pause_seek_volume_and_close(self):
        import faulthandler
        faulthandler.dump_traceback_later(10, exit=True)
        self.addCleanup(faulthandler.cancel_dump_traceback_later)
        if QMediaDevices.defaultAudioOutput().isNull():
            self.skipTest("No audio output device in this test session")
        self.player.play_file(self.media)
        self.wait_for(lambda: self.player.state["duration"] == 4000 and self.player.state["position"] > 80)
        self.assertEqual(self.player.state["error"], "")
        self.assertTrue(self.player.state["playing"])
        self.assertEqual(self.player._player.activeVideoTrack(), -1)
        self.player.toggle()
        self.wait_for(lambda: not self.player.state["playing"])
        position = self.player.state["position"]
        QTest.qWait(180)
        self.assertLessEqual(abs(self.player.state["position"] - position), 30)
        self.player.seek(2200)
        self.wait_for(lambda: abs(self.player.state["position"] - 2200) < 80)
        self.player.setVolume(27)
        self.assertAlmostEqual(self.player._output.volume(), .27, places=3)
        self.player.close()
        self.assertFalse(self.player.state["available"])
        self.assertTrue(self.player._player.source().isEmpty())
        self.assertEqual(self.player._player.playbackState(), QMediaPlayer.PlaybackState.StoppedState)
        QTest.qWait(150)
        self.media.rename(self.root / "Freigegeben.wav")

    def test_corrupt_media_reports_an_error_and_close_clears_it(self):
        broken = self.root / "Defekt.wav"
        broken.write_bytes(b"not an audio file")
        self.player.play_file(broken)
        self.wait_for(lambda: bool(self.player.state["error"]))
        self.assertFalse(self.player.state["loading"])
        self.player.close()
        self.assertEqual(self.player.state["error"], "")
        self.assertFalse(self.player.state["available"])

    def test_real_speed_control_enables_pitch_compensation_and_limits_rate(self):
        if QMediaDevices.defaultAudioOutput().isNull():
            self.skipTest('No audio output device in this test session')
        self.player.play_file(self.media)
        self.wait_for(lambda:self.player.state['duration']==4000)
        if not self.player.state['rateAvailable']:
            self.skipTest('Backend cannot preserve pitch at different playback rates')
        self.player.setRate(1.5)
        self.assertTrue(self.player._player.pitchCompensation())
        self.assertEqual(self.player._player.playbackRate(),1.5)
        self.player.changeRate(1);self.assertEqual(self.player.state['rate'],1.75)
        self.player.changeRate(-1);self.assertEqual(self.player.state['rate'],1.5)
        self.player.setRate(99);self.assertEqual(self.player.state['rate'],3.)
        self.player.setRate(-1);self.assertEqual(self.player.state['rate'],.5)
        self.player.setRate(float('nan'));self.assertEqual(self.player.state['rate'],.5)

    def test_unavailable_pitch_backend_keeps_normal_speed(self):
        backend=Mock()
        backend.pitchCompensationAvailability.return_value=QMediaPlayer.PitchCompensationAvailability.Unavailable
        self.player._player=backend
        self.assertFalse(self.player.state['rateAvailable'])
        self.player.setRate(2)
        backend.setPlaybackRate.assert_called_once_with(1.)
        backend.setPitchCompensation.assert_not_called()

    def test_mute_preserves_volume_and_volume_change_restores_sound(self):
        self.player.setVolume(35)
        self.player.toggleMute()
        self.assertTrue(self.player.state['muted'])
        self.assertEqual(self.player.state['volume'],35)
        self.assertIsNone(self.player._player)
        self.player._ensure_player()
        self.assertTrue(self.player._output.isMuted())
        self.player.toggleMute();self.assertFalse(self.player._output.isMuted())
        self.player.toggleMute();self.player.setVolume(40)
        self.assertFalse(self.player._output.isMuted())
