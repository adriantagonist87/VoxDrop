import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import transcription_worker
from platform_io import WINDOWS


@unittest.skipUnless(WINDOWS, "Windows transcription temporary storage")
class TranscriptionTemporaryTests(unittest.TestCase):
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
