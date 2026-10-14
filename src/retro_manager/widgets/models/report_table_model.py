"""Tabellenmodell für einen Igir-Report."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt

from retro_manager.core.igir_report import IgirReport, status_counts

ModelIndex = QModelIndex | QPersistentModelIndex


class ReportTableModel(QAbstractTableModel):
    """Zeigt die Zeilen eines IgirReport; Spalten kommen aus der CSV-Kopfzeile."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._report = IgirReport()

    @property
    def status_column(self) -> int | None:
        return self._report.status_index

    def status_counts(self) -> dict[str, int]:
        """Anzahl der Einträge je Status im aktuellen Report."""
        return status_counts(self._report)

    def set_report(self, report: IgirReport) -> None:
        self.beginResetModel()
        self._report = report
        self.endResetModel()

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._report.rows)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._report.columns)

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> str | None:
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        ):
            return None
        return self._report.rows[index.row()][index.column()]

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._report.columns[section]
        return str(section + 1)
