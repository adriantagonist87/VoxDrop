import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from model_inventory import LABELS, SPEAKERS, WHISPER, catalog, inventory, model_use, remove_model


class ModelInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.store = self.root / "Modelle"
        self.database = self.root / "jobs.sqlite3"

    def write(self, path, data=b"model fixture"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def model(self, key):
        for name in catalog()[key][1]:
            self.write(self.store / "models" / key / name)
        return self.store / "models" / key

    def entry(self, key):
        return next(row for row in inventory(self.store) if row["id"] == key)

    def test_removes_only_selected_model_and_its_cache(self):
        self.assertEqual({row["status"] for row in inventory(self.store)}, {"Nicht installiert"})
        self.assertFalse(self.store.exists())
        model = self.model(WHISPER)
        speaker = self.model(SPEAKERS)
        repo = catalog()[WHISPER][0].replace("/", "--")
        cache = self.write(self.store / "huggingface" / "hub" / ("models--" + repo) / "blobs" / "model")
        shared = self.write(self.store / "huggingface" / "xet" / "chunk")
        self.assertEqual({row["id"] for row in inventory(self.store)}, set(LABELS))
        entry = self.entry(WHISPER)
        self.assertEqual(entry["status"], "Installiert")
        self.assertEqual(entry["cacheBytes"], cache.stat().st_size)
        remove_model(self.store, self.database, WHISPER, entry["token"])
        self.assertFalse(model.exists())
        self.assertFalse(cache.exists())
        self.assertTrue(speaker.is_dir())
        self.assertTrue(shared.is_file())
        self.assertEqual(self.entry(WHISPER)["status"], "Nicht installiert")

    def test_changed_incomplete_model_requires_fresh_confirmation(self):
        partial = self.write(self.store / "models" / WHISPER / ".cache" / "weights.incomplete")
        entry = self.entry(WHISPER)
        self.assertEqual(entry["status"], "Unvollständig")
        self.write(partial, b"new bytes written after review")
        with self.assertRaisesRegex(ValueError, "Modellbestand hat sich geändert"):
            remove_model(self.store, self.database, WHISPER, entry["token"])
        self.assertTrue(partial.is_file())

    def test_active_access_and_claimed_jobs_stop_deletion(self):
        model = self.model(WHISPER)
        token = self.entry(WHISPER)["token"]
        with model_use(self.store), model_use(self.store), self.assertRaisesRegex(ValueError, "gerade verwendet"):
            remove_model(self.store, self.database, WHISPER, token)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executescript("""CREATE TABLE jobs(state TEXT);
                CREATE TABLE immediate_jobs(job_id INTEGER);
                INSERT INTO jobs VALUES ('transcribing');
            """)
        with self.assertRaisesRegex(ValueError, "Pausiere"):
            remove_model(self.store, self.database, WHISPER, token)
        self.assertTrue(model.is_dir())

    def test_redirected_model_path_is_rejected(self):
        outside = self.write(self.root / "fremde Daten" / "model.bin")
        models = self.store / "models"
        models.mkdir(parents=True)
        try:
            (models / WHISPER).symlink_to(outside.parent, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Directory symlinks are unavailable: {error}")
        with self.assertRaises(ValueError):
            remove_model(self.store, self.database, WHISPER, "")
        self.assertEqual(outside.read_bytes(), b"model fixture")
