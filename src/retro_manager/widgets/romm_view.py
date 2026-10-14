"""Eingebettete RomM-Weboberfläche."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget

PROFILE_NAME = "retro-manager"


class RommView(QWebEngineView):
    """Zeigt RomM an; Cookies und Cache bleiben zwischen Programmstarts erhalten."""

    def __init__(self, storage_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._login_script = ""
        self._build_ui(storage_dir)
        self._connect_signals()

    def _build_ui(self, storage_dir: Path) -> None:
        self.setObjectName("rommView")
        # Das Profil muss die Seite überleben, daher hängt es an der Anwendung.
        profile = QWebEngineProfile(PROFILE_NAME, QCoreApplication.instance())
        profile.setPersistentStoragePath(str(storage_dir / "storage"))
        profile.setCachePath(str(storage_dir / "cache"))
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.setPage(QWebEnginePage(profile, self))

    def _connect_signals(self) -> None:
        self.loadFinished.connect(self._on_load_finished)

    def open(self, url: str, login_script: str) -> None:
        """Lädt RomM und meldet die Oberfläche nach dem Laden einmalig an."""
        self._login_script = login_script
        self.setUrl(QUrl(url))

    def _on_load_finished(self, ok: bool) -> None:
        if ok and self._login_script:
            script, self._login_script = self._login_script, ""
            self.page().runJavaScript(script)
