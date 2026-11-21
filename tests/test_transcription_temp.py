import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import transcription_worker
from platform_io import WINDOWS


class TranscriptionTemporaryTests(unittest.TestCase):
    @unittest.skipUnless(WINDOWS, "Windows-Grafiküberwachung")
    def test_display_timeout_terminates_windowless_worker_and_cleans_temporary_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            media = root / "example.wav"
            media.write_bytes(b"synthetic media")
            ready = root / "inference-started"
            worker = root / "sleeping_worker.py"
            worker.write_text(
                "from pathlib import Path\nimport sys,tempfile,time\n"
                "Path(tempfile.mkdtemp(), 'test-audio.npy').write_bytes(b'audio')\n"
                "Path(sys.argv[2]).with_name('inference-started').touch()\n"
                "time.sleep(12)\n",
                encoding="utf-8",
            )
            with (
                patch.object(transcription_worker, "__file__", str(worker)),
                patch.object(transcription_worker, "GRAPHICS_POLL_INTERVAL", .05),
                patch.object(transcription_worker, "graphics_timeout_since",
                             side_effect=lambda _: "Test-Timeout" if ready.is_file() else None),
                self.assertRaisesRegex(transcription_worker.GraphicsTimeout, "Test-Timeout"),
            ):
                transcription_worker.run_transcription(media, report=lambda *_: None, measurements={}, hardware="cuda")
            self.assertTrue(ready.is_file())
            self.assertEqual(list(root.glob("transcription-*")), [])

    def test_crashed_worker_cannot_leave_audio_outside_its_job_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            job = root / "job"
            fallback = root / "system-temp"
            job.mkdir()
            fallback.mkdir()
            media = job / "media.wav"
            media.write_bytes(b"synthetic media")
            worker = root / "fault_worker.py"
            worker.write_text(
                "import json,os,sys,tempfile\n"
                "from pathlib import Path\n"
                "folder=Path(tempfile.mkdtemp(prefix='qwen-fault-'))\n"
                "(folder/'audio.npy').write_bytes(b'synthetic decoded audio')\n"
                "Path(sys.argv[2]).with_name('observed.json').write_text(json.dumps(str(folder)))\n"
                "os._exit(19)\n",
                encoding="utf-8",
            )
            with (
                patch.dict(os.environ, {name: str(fallback) for name in ("TMPDIR", "TEMP", "TMP")}),
                patch.object(transcription_worker, "__file__", str(worker)),
                self.assertRaisesRegex(RuntimeError, "Transkriptionsprozess"),
            ):
                transcription_worker.run_transcription(
                    media, report=lambda *_: None, measurements={}
                )
            allocated = Path(json.loads((job / "observed.json").read_text()))
            self.assertTrue(allocated.is_relative_to(job), "decoded audio escaped job storage")
            self.assertFalse(allocated.exists(), "crashed worker left temporary audio behind")
            self.assertEqual(list(fallback.iterdir()), [])
