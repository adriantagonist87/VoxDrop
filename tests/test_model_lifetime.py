import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

import voxdrop


class ModelLifetimeTests(unittest.TestCase):
    def run_whisper(self, transcriber, speaker_stage):
        with (
            patch("voxdrop.require_models", return_value={voxdrop.WHISPER_MODEL: Path("model")}),
            patch("voxdrop.decode_media", return_value=(np.zeros(16_000), 1.0)),
            patch("voxdrop.load_whisper", return_value=transcriber),
            patch("voxdrop.assign_speakers", side_effect=speaker_stage) as assign,
        ):
            result = voxdrop.transcribe(
                Path("synthetic.wav"), model=voxdrop.WHISPER_MODEL,
                hardware="cuda", language="de", speakers=True,
                speaker_count=2, report=lambda *_: None,
            )
        return result, assign

    def transcriber(self):
        return Mock(backend="faster-whisper", transcribe=Mock(return_value={
            "segments": [{"start": 0, "end": 1, "text": " Test"}],
        }))

    def test_whisper_is_unloaded_before_the_speaker_model_can_load(self):
        transcriber = self.transcriber()

        def speakers(*args, **kwargs):
            transcriber.close.assert_called_once_with()
            self.assertEqual(args[2], "faster-whisper")
            return "speaker result"

        result, assign = self.run_whisper(transcriber, speakers)
        self.assertEqual(result, "speaker result")
        transcriber.close.assert_called_once_with()
        assign.assert_called_once()

    def test_failed_speech_recognition_still_unloads_whisper(self):
        transcriber = self.transcriber()
        transcriber.transcribe.side_effect = RuntimeError("ASR failed")
        speakers = Mock()
        with self.assertRaisesRegex(RuntimeError, "ASR failed"):
            self.run_whisper(transcriber, speakers)
        transcriber.close.assert_called_once_with()
        speakers.assert_not_called()

    def test_speaker_failure_occurs_after_whisper_has_been_unloaded(self):
        transcriber = self.transcriber()

        def speakers(*args, **kwargs):
            transcriber.close.assert_called_once_with()
            raise RuntimeError("speaker failed")

        with self.assertRaisesRegex(RuntimeError, "speaker failed"):
            self.run_whisper(transcriber, speakers)
        transcriber.close.assert_called_once_with()
