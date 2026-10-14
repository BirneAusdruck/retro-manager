"""Igir-Report (CSV) einlesen und auswerten."""

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

STATUS_COLUMN = "Status"
FILES_COLUMN = "ROM Files"
UNUSED_STATUS = "UNUSED"


@dataclass
class IgirReport:
    """Inhalt eines Igir-Reports; Spalten werden aus der Kopfzeile übernommen."""

    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    @property
    def status_index(self) -> int | None:
        """Index der Status-Spalte (FOUND, MISSING, …) oder None."""
        return self._column_index(STATUS_COLUMN)

    @property
    def files_index(self) -> int | None:
        """Index der Spalte mit den gefundenen Dateien oder None."""
        return self._column_index(FILES_COLUMN)

    def _column_index(self, wanted: str) -> int | None:
        for index, name in enumerate(self.columns):
            if name.strip().lower() == wanted.lower():
                return index
        return None


def parse_report(path: Path) -> IgirReport:
    """Liest einen Igir-Report; zu kurze Zeilen werden mit leeren Werten aufgefüllt."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        columns = next(reader, [])
        rows = [row + [""] * (len(columns) - len(row)) for row in reader if row]
    return IgirReport(columns=columns, rows=rows)


def status_counts(report: IgirReport) -> dict[str, int]:
    """Anzahl der Einträge je Status, z. B. {"FOUND": 120, "MISSING": 3}."""
    index = report.status_index
    if index is None:
        return {}
    return dict(Counter(row[index] for row in report.rows if row[index]))


def without_unused_under(report: IgirReport, roots: list[Path]) -> IgirReport:
    """Entfernt UNUSED-Einträge für Dateien unterhalb von `roots` (z. B. Hilfs-CUEs)."""
    status, files = report.status_index, report.files_index
    if status is None or files is None or not roots:
        return report
    prefixes = tuple(f"{root}/" for root in roots)
    rows = [
        row
        for row in report.rows
        if not (row[status] == UNUSED_STATUS and row[files].startswith(prefixes))
    ]
    return IgirReport(columns=report.columns, rows=rows)
