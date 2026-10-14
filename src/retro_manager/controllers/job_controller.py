"""QThreadPool + QRunnable, Fortschritt per Signal."""

from PySide6.QtCore import QObject, QThreadPool


class JobController(QObject):
    """Führt Entpack- und Hash-Jobs parallel im Thread-Pool aus."""

    def __init__(self, max_parallel_jobs: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self.set_max_parallel_jobs(max_parallel_jobs)

    def set_max_parallel_jobs(self, count: int) -> None:
        """Legt fest, wie viele Jobs gleichzeitig laufen dürfen."""
        self._pool.setMaxThreadCount(max(1, count))
