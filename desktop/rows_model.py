"""Keep QML delegates and scroll anchors when background job snapshots change."""
from difflib import SequenceMatcher

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class StableRows(QAbstractListModel):
    ROW = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def roleNames(self):
        return {self.ROW: b'modelData'}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == self.ROW and 0 <= index.row() < len(self.rows):
            return self.rows[index.row()]
        return None

    def update(self, rows, *, reset=False):
        ids = [row['id'] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate job identifiers in desktop model')
        old_ids = [row['id'] for row in self.rows]
        if reset or not old_ids:
            self.beginResetModel()
            self.rows = list(rows)
            self.endResetModel()
            return
        if old_ids != ids:
            # Apply backwards so earlier edit indices remain valid. Typical
            # updates remove the completed first item or append newly found jobs.
            changes = SequenceMatcher(a=old_ids, b=ids, autojunk=False).get_opcodes()
            for kind, first, last, new_first, new_last in reversed(changes):
                if kind == 'equal':
                    continue
                if last > first:
                    self.beginRemoveRows(QModelIndex(), first, last - 1)
                    del self.rows[first:last]
                    self.endRemoveRows()
                if new_last > new_first:
                    self.beginInsertRows(QModelIndex(), first, first + new_last - new_first - 1)
                    self.rows[first:first] = rows[new_first:new_last]
                    self.endInsertRows()
        first_changed = None
        for index, row in enumerate(rows):
            if row != self.rows[index]:
                self.rows[index] = row
                if first_changed is None:
                    first_changed = index
            elif first_changed is not None:
                self.dataChanged.emit(self.index(first_changed), self.index(index - 1), [self.ROW])
                first_changed = None
        if first_changed is not None:
            self.dataChanged.emit(self.index(first_changed), self.index(len(rows) - 1), [self.ROW])
