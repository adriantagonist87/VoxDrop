import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from silence import select_speech
from smb_transcriber import transcribe

RATE = 16000


def segment(start, end, word):
    return {
        "start": start,
        "end": end,
        "text": word.strip(),
        "words": [{"start": start, "end": end, "word": word}],
    }


class SilenceTests(unittest.TestCase):
    def test_speech_is_compacted_and_speakers_receive_original_timeline(self):
        original = np.zeros(20 * RATE, dtype=np.float32)
        spans = [
            {"start": 4 * RATE, "end": 6 * RATE},
            {"start": 15 * RATE, "end": 17 * RATE},
        ]
        result = {
            "segments": [segment(1.5, 2.0, " Abend"), segment(2.0, 2.8, " Morgen")]
        }
        data = {}
        with (
            patch("smb_transcriber.require_models", return_value={}),
            patch("smb_transcriber.decode_media", return_value=(original, 20)),
            patch("faster_whisper.vad.get_speech_timestamps", return_value=spans),
            patch(
                "smb_transcriber.qwen_backend.transcribe", return_value=result
            ) as model,
            patch(
                "smb_transcriber.assign_speakers", return_value="Resultat"
            ) as diarization,
        ):
            self.assertEqual(
                transcribe(
                    Path("audio.wav"),
                    language="de",
                    speakers=True,
                    speaker_count=None,
                    skip_silence=True,
                    measurements=data,
                    report=lambda *_: None,
                ),
                "Resultat",
            )
        self.assertEqual(len(model.call_args.args[0]), 4 * RATE)
        self.assertIs(diarization.call_args.args[0], original)
        self.assertEqual(data["audio_seconds"], 20)
        for word, start, end in zip(result["segments"], (5.5, 15.0), (6.0, 15.8)):
            self.assertEqual((word["start"], word["end"]), (start, end))
            self.assertEqual(
                (word["words"][0]["start"], word["words"][0]["end"]), (start, end)
            )

    def test_short_silence_at_the_edges_is_retained(self):
        audio = np.zeros(10 * RATE, dtype=np.float32)
        with patch(
            "faster_whisper.vad.get_speech_timestamps",
            return_value=[{"start": RATE, "end": 9 * RATE}],
        ):
            speech, mapping = select_speech(audio)
        self.assertIs(speech, audio)
        self.assertIsNone(mapping)

    def test_empty_detection_is_an_explicit_error(self):
        audio = np.zeros(10 * RATE, dtype=np.float32)
        with (
            patch("faster_whisper.vad.get_speech_timestamps", return_value=[]),
            self.assertRaisesRegex(ValueError, "keine Sprache"),
        ):
            select_speech(audio)
