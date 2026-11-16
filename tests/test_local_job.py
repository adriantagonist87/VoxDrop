import io
import os
import tempfile
import unittest
import wave
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from voxdrop import (
    DEFAULT_MODEL,
    decode_media,
    format_transcript,
    main,
    publish_text,
)


class LocalJobTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = self.directory / "Prüfaufnahme Ä.wav"
        with wave.open(str(self.source), "wb") as handle:
            handle.setparams((1, 2, 16_000, 0, "NONE", "not compressed"))
            handle.writeframes(b"\x01\x00" * 16_000)

    def test_pyav_decodes_a_unicode_path(self):
        audio, duration = decode_media(self.source)
        self.assertEqual(audio.shape, (16_000,))
        self.assertEqual(duration, 1.0)

    def test_format_stable_speakers_and_times(self):
        cues = [
            {"start": 0.2, "text": " Hallo!", "speaker": "SPEAKER_04"},
            {"start": 72, "text": "Grüße!", "speaker": "SPEAKER_02"},
            {"start": 9000.7, "text": "Tschüss!", "speaker": "SPEAKER_04"},
        ]
        self.assertEqual(
            format_transcript(cues, speakers=True),
            "[00:00:00] Sprecher 1: Hallo!\n\n"
            "[00:01:12] Sprecher 2: Grüße!\n\n"
            "[02:30:00] Sprecher 1: Tschüss!\n",
        )

    def test_publish_refuses_to_replace_existing_text(self):
        target = self.source.with_suffix(".txt")
        publish_text(target, "Grüße\n")
        with self.assertRaises(FileExistsError):
            publish_text(target, "Andere Fassung\n")
        self.assertEqual(target.read_bytes(), "Grüße\n".encode())
        self.assertEqual(list(self.directory.glob("*.partial")), [])

    def test_cli_exports_only_txt_and_preserves_source(self):
        target = self.source.with_suffix(".txt")
        original = self.source.read_bytes()
        result = "[00:00:00] Sprecher 1: Grüße!\n"
        arguments = [
            "--data-dir",
            str(self.directory / "state"),
            "transcribe",
            str(self.source),
            "--output-dir",
            str(self.directory),
            "--language",
            "de",
            "--speaker-count",
            "2",
        ]
        with (
            patch.dict(os.environ),
            patch("voxdrop.transcribe", return_value=result) as engine,
        ):
            with (
                redirect_stdout(io.StringIO()) as stdout,
                redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(main(arguments), 0)
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
        engine.assert_called_once_with(
            self.source,
            language="de",
            speakers=True,
            speaker_count=2,
            hardware="metal",
            model=DEFAULT_MODEL,
            skip_silence=False,
            dover_lap=False,
        )
        self.assertEqual(stdout.getvalue().strip(), str(target))
        self.assertEqual(target.read_text(encoding="utf-8"), result)
        self.assertEqual(self.source.read_bytes(), original)

    def test_empty_tonspur_is_a_clear_failure(self):
        empty = self.directory / "leer.wav"
        with wave.open(str(empty), "wb") as handle:
            handle.setparams((1, 2, 16_000, 0, "NONE", "not compressed"))
        with self.assertRaisesRegex(ValueError, "keine Audiodaten|nicht dekodiert"):
            decode_media(empty)


if __name__ == "__main__":
    unittest.main()
