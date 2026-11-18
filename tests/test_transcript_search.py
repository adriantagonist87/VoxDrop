from contextlib import closing, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

import watch_service as service
from desktop.transcript_search import SearchCancelled, path_matches, search_transcripts


class TranscriptSearchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.state = self.root / 'service'
        service.initialise(self.state)
        self.db = service.database(self.state)
        self.addCleanup(self.db.close)
        self.index = self.state / 'transcript-search.sqlite3'
        self.results = self.state / 'content-search-result.json'
        self.cancelled = Event()

    def add(self, name, text, state='done'):
        path = self.root / name
        path.with_suffix('.txt').write_text(text, encoding='utf-8')
        with self.db:
            cursor = self.db.execute('INSERT INTO jobs(source,completed_dir,size,mtime_ns,settings,detected,updated,state) '
                'VALUES (?,?,1,1,?,1,1,?)', (str(path), str(path.parent), '{}', state))
        return cursor.lastrowid, path

    def search(self, query, progress=lambda text: None):
        return search_transcripts(self.state / 'jobs.sqlite3', self.index, self.results, query,
            lambda job: service.targets(job)[1], self.cancelled, progress)

    def test_wildcards_unicode_and_literal_sql_metacharacters(self):
        identifier, path = self.add('Ärzte 100%_[Plan] .wav', 'Content')
        self.add('Other.wav', 'Other')
        for query in ('ÄRZ*100?', '100%_[Plan]', str(path.parent) + r'\Ärz*', '*.txt'):
            with self.subTest(query=query):
                rows = service.history_jobs(self.db, 'desc', 250, terminal_only=True, search=query)
                if query != '*.txt':
                    self.assertTrue(path_matches(path, query))
                    self.assertEqual([row['id'] for row in rows], [identifier])
                    self.assertEqual(service.history_counts(self.db, search=query)['all'], 1)
                else:
                    self.assertEqual(len(rows), 2)
        self.assertEqual(service.history_counts(self.db, search="' OR 1=1 --")['all'], 0)
        self.assertFalse(self.index.exists())

    def test_incremental_content_index_refreshes_changed_and_missing_files(self):
        one, source = self.add('First.wav', 'Die Besprechung behandelt Überprüfung und Sonderplanung.')
        self.add('Second.wav', 'Anderes Thema.')
        first = self.search('ÜBERPRÜF* Sonderplanung')
        self.assertEqual((first['matches'], first['changed']), (1, 2))
        self.assertEqual(json.loads(self.results.read_text())['job_ids'], [one])
        self.assertEqual(self.search('Sonderplanung')['changed'], 0)
        source.with_suffix('.txt').write_text('Das Thema wurde vollständig geändert.', encoding='utf-8')
        self.assertEqual(self.search('Sonderplanung')['matches'], 0)
        self.assertEqual(self.search('geändert')['matches'], 1)
        source.with_suffix('.txt').unlink()
        missing = self.search('geändert')
        self.assertEqual((missing['matches'], missing['skipped']), (0, 1))
        with closing(sqlite3.connect(self.index)) as index:
            self.assertEqual(index.execute('pragma integrity_check').fetchone()[0], 'ok')

    def test_cancel_keeps_previous_result_and_can_resume_with_consistent_index(self):
        for index in range(70):
            self.add(f'{index}.wav', 'Abbruchtest und Wiederaufnahme')
        original = self.search('Abbruchtest')
        saved = self.results.read_bytes()
        def cancel(text):
            if text.startswith('Suchindex:'):
                self.cancelled.set()
        with self.assertRaises(SearchCancelled):
            self.search('Wiederaufnahme', cancel)
        self.assertEqual(self.results.read_bytes(), saved)
        self.cancelled.clear()
        self.assertEqual(self.search('Wiederaufnahme')['matches'], original['matches'])
        self.assertEqual(self.db.execute("select count(*) from jobs where state='done'").fetchone()[0], 70)

    def test_explicit_content_results_extend_path_search_and_reject_stale_token(self):
        content_id, _ = self.add('Unnamed.wav', 'Einzigartiger Inhaltstreffer')
        path_id, _ = self.add('Inhaltstreffer Dateiname.wav', 'Anderer Text')
        indexed = self.search('Inhaltstreffer')
        arguments = ['--state-dir', str(self.state), '--model-data', str(self.root / 'models'),
                     'status', '--search', 'Inhaltstreffer', '--content-results', str(self.results),
                     '--content-token', indexed['token']]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(service.main(arguments), 0)
        snapshot = json.loads(output.getvalue())
        self.assertEqual({job['id'] for job in snapshot['jobs']}, {content_id, path_id})
        self.assertEqual(snapshot['history_counts']['all'], 2)
        with redirect_stdout(io.StringIO()), patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(service.main(arguments[:-1] + ['stale']), 1)
