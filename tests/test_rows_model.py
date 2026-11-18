"""Exercise incremental snapshots rather than recreating thousands of delegates."""
import random
import unittest

from PySide6.QtTest import QAbstractItemModelTester
from desktop.rows_model import StableRows


class StableRowsTests(unittest.TestCase):
    def test_incremental_refresh_does_not_reset_unchanged_delegates(self):
        model = StableRows()
        tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Warning)
        resets, changes = [], []
        model.modelReset.connect(lambda: resets.append(True))
        model.dataChanged.connect(lambda *args: changes.append(args))
        rows = [dict(id=i, status='ready') for i in range(8000)]
        model.update(rows)
        anchor = model.index(4000)
        from PySide6.QtCore import QPersistentModelIndex
        anchor = QPersistentModelIndex(anchor)
        model.update(rows[1:] + [dict(id=8000, status='ready')])
        self.assertEqual(len(resets), 1)
        self.assertEqual(anchor.row(), 3999)
        self.assertEqual(anchor.data(model.ROW)['id'], 4000)
        model.update([{**r, 'status':'changed'} if r['id']==4000 else r for r in model.rows])
        self.assertEqual(len(changes), 1)
        self.assertEqual(anchor.data(model.ROW)['status'], 'changed')
        self.assertIsNotNone(tester)

    def test_random_reorders_insertions_and_removals_keep_exact_snapshot(self):
        model = StableRows()
        tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Warning)
        rng = random.Random(47)
        for _ in range(80):
            rows = [dict(id=i, name=str(i)) for i in rng.sample(range(90), rng.randrange(90))]
            model.update(rows)
            self.assertEqual(model.rows, rows)
            self.assertEqual(model.rowCount(), len(rows))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            model.update([dict(id=1),dict(id=1)])
        self.assertIsNotNone(tester)

