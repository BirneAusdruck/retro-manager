"""Tabellenmodell der Übertragungs-Warteschlange."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt

from retro_manager.controllers.transfer_controller import (
    STATE_CANCELLED,
    STATE_DONE,
    STATE_FAILED,
    STATE_RUNNING,
    STATE_WAITING,
    TransferJob,
)
from retro_manager.widgets.models.game_table_model import format_size

ModelIndex = QModelIndex | QPersistentModelIndex

COLUMN_LABEL, COLUMN_DIRECTION, COLUMN_PROGRESS, COLUMN_STATE = range(4)
# Fortschritt in Promille für die Balken-Darstellung.
PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 2


class TransferModel(QAbstractTableModel):
    """Aufträge der Warteschlange in der Reihenfolge, in der sie eingestellt wurden."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._jobs: list[TransferJob] = []

    def add(self, job: TransferJob) -> None:
        self.beginInsertRows(QModelIndex(), len(self._jobs), len(self._jobs))
        self._jobs.append(job)
        self.endInsertRows()

    def update(self, job: TransferJob) -> None:
        if job in self._jobs:
            row = self._jobs.index(job)
            self.dataChanged.emit(self.index(row, 0), self.index(row, COLUMN_STATE))

    def set_jobs(self, jobs: list[TransferJob]) -> None:
        self.beginResetModel()
        self._jobs = list(jobs)
        self.endResetModel()

    def job(self, row: int) -> TransferJob:
        return self._jobs[row]

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._jobs)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else 4

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        job = self._jobs[index.row()]
        column = index.column()
        if role == PROGRESS_ROLE:
            return (
                int(job.done * 1000 / job.total)
                if job.total
                else (1000 if job.state == STATE_DONE else 0)
            )
        if role == Qt.ItemDataRole.ToolTipRole:
            return job.message or None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if column == COLUMN_LABEL:
            return job.label
        if column == COLUMN_DIRECTION:
            return (
                self.tr("↑ Hochladen") if job.direction == "upload" else self.tr("↓ Herunterladen")
            )
        if column == COLUMN_PROGRESS:
            if not job.total:
                return ""
            return f"{format_size(job.done)} / {format_size(job.total)}"
        if column == COLUMN_STATE:
            return {
                STATE_WAITING: self.tr("wartet"),
                STATE_RUNNING: self.tr("läuft"),
                STATE_DONE: self.tr("fertig"),
                STATE_FAILED: self.tr("Fehler: {0}").format(job.message),
                STATE_CANCELLED: self.tr("abgebrochen"),
            }.get(job.state, job.state)
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return [self.tr("Auftrag"), self.tr("Richtung"), self.tr("Fortschritt"), self.tr("Status")][
            section
        ]
