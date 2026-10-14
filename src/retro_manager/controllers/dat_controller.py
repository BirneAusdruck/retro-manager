"""DATs aktualisieren: RomM-Plattformen, Igir-Tabelle, No-Intro und Redump laden, schreiben."""

import logging
import zipfile
from collections.abc import Callable
from datetime import date
from pathlib import Path

import shiboken6
from PySide6.QtCore import QByteArray, QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from retro_manager.controllers.romm_controller import RommController
from retro_manager.core import dat_update
from retro_manager.core.dat_update import ConsoleRule, DatFile, RommPlatform

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_MS = 120_000
SOURCES_TEXT = (
    "Quellen: No-Intro Daily-Paket (Parent/Clone; Sets No-Intro, Non-Redump, Unofficial) und "
    "Redump (alle Systeme und BIOS-DATs). Zugeordnete DATs liegen in `no-intro/` (Unterordner "
    "`Non-Redump/`, `Unofficial/`) und `redump/`. Nintendo Switch: weder No-Intro noch Redump "
    "bieten eine DAT an."
)

# (HTTP-Status, Antwort-Header in Kleinbuchstaben, Inhalt)
ResponseHandler = Callable[[int, dict[str, str], bytes], None]


class _WriteSignals(QObject):
    done = Signal(object)  # DatUpdateResult
    error = Signal(str)


class _WriteTask(QRunnable):
    """Entpacken, Zuordnen und Schreiben im Hintergrund (über 100 MB Dateien)."""

    def __init__(
        self,
        dats_dir: Path,
        nointro_pack: bytes,
        redump_dats: list[DatFile],
        rules: list[ConsoleRule],
        platforms: list[RommPlatform],
        cue_packs: dict[str, dict[str, bytes]],
    ) -> None:
        super().__init__()
        self.signals = _WriteSignals()
        self._dats_dir = dats_dir
        self._nointro_pack = nointro_pack
        self._redump_dats = redump_dats
        self._rules = rules
        self._platforms = platforms
        self._cue_packs = cue_packs

    def run(self) -> None:
        try:
            dats = dat_update.extract_nointro(self._nointro_pack) + self._redump_dats
            matches = dat_update.match_dats(dats, self._rules, self._platforms)
            result = dat_update.write_dats(
                self._dats_dir,
                matches,
                self._platforms,
                SOURCES_TEXT,
                date.today(),
                cue_packs=self._cue_packs,
            )
        except (OSError, zipfile.BadZipFile) as error:
            self.signals.error.emit(str(error))
            return
        self.signals.done.emit(result)


class DatController(QObject):
    """Lädt die aktuellen DATs und schreibt die zu RomM passenden nach <HDD>/dats."""

    running_changed = Signal(bool)
    status = Signal(str)
    progress = Signal(int, int)  # erledigt, gesamt
    finished = Signal(object)  # DatUpdateResult
    failed = Signal(str)

    def __init__(
        self, romm: RommController, igir_version: str, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._romm = romm
        self._igir_version = igir_version
        self._network = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next_redump)
        self._running = False
        self._task: _WriteTask | None = None
        self._reset()

        romm.supported_platforms_ready.connect(self._on_platforms)
        romm.request_failed.connect(self._on_romm_failed)

    def is_running(self) -> bool:
        return self._running

    def update(self, dats_dir: Path) -> None:
        """Startet die Aktualisierung."""
        if self._running:
            return
        self._reset()
        self._dats_dir = dats_dir
        self._set_running(True)
        self.status.emit(self.tr("RomM-Plattformen werden abgefragt …"))
        self._romm.fetch_supported_platforms()

    def cancel(self) -> None:
        """Bricht laufende Downloads ab; das Schreiben im Hintergrund läuft zu Ende."""
        if not self._running or self._task is not None:
            return
        self._timer.stop()
        if self._reply is not None:
            self._reply.abort()
        self._fail(self.tr("Die Aktualisierung wurde abgebrochen."))

    # --- Ablauf ---------------------------------------------------------------------------

    def _reset(self) -> None:
        self._dats_dir = Path()
        self._platforms: list[RommPlatform] = []
        self._rules: list[ConsoleRule] = []
        self._nointro_pack = b""
        self._manager_url = ""
        self._redump_queue: list[dat_update.RedumpSystem] = []
        self._redump_total = 0
        self._redump_dats: list[DatFile] = []
        self._cue_packs: dict[str, dict[str, bytes]] = {}

    def _on_platforms(self, data: object) -> None:
        if not self._running:
            return
        try:
            self._platforms = dat_update.parse_romm_platforms(data)  # type: ignore[arg-type]
        except (KeyError, TypeError) as error:
            self._fail(self.tr("Unerwartete Plattformliste von RomM: {0}").format(error))
            return
        self.status.emit(self.tr("RomM kennt {0} Plattformen.").format(len(self._platforms)))
        self.status.emit(self.tr("Igir-Zuordnungstabelle wird geladen …"))
        url = dat_update.IGIR_CONSOLE_TOKENS_URL.format(version=self._igir_version)
        self._get(url, self._on_console_tokens)

    def _on_romm_failed(self, message: str) -> None:
        if self._running and not self._platforms:
            self._fail(message)

    def _on_console_tokens(self, status: int, headers: dict[str, str], body: bytes) -> None:
        if not self._check(status, body, self.tr("Igir-Zuordnungstabelle")):
            return
        try:
            self._rules = dat_update.parse_console_tokens(body.decode("utf-8"))
        except (ValueError, KeyError) as error:
            self._fail(self.tr("Igir-Zuordnungstabelle ist ungültig: {0}").format(error))
            return
        self.status.emit(self.tr("No-Intro: Daily-Paket wird angefordert …"))
        self._get(dat_update.DATOMATIC_DAILY_URL, self._on_daily_page)

    def _on_daily_page(self, status: int, headers: dict[str, str], body: bytes) -> None:
        if not self._check(status, body, "DAT-o-MATIC"):
            return
        submit = dat_update.parse_daily_submit_name(body.decode("utf-8", "replace"))
        if submit is None:
            self._fail(self.tr("DAT-o-MATIC: Download-Formular nicht gefunden."))
            return
        self._post(
            dat_update.DATOMATIC_DAILY_POST_URL,
            dat_update.daily_form_fields(submit),
            self._on_daily_requested,
            referer=dat_update.DATOMATIC_DAILY_URL,
        )

    def _on_daily_requested(self, status: int, headers: dict[str, str], body: bytes) -> None:
        location = headers.get("location", "")
        if status not in (301, 302, 303) or not location:
            self._fail(self.tr("DAT-o-MATIC: Paket konnte nicht angefordert werden."))
            return
        self._manager_url = QUrl(dat_update.DATOMATIC_BASE_URL).resolved(QUrl(location)).toString()
        self._get(self._manager_url, self._on_manager_page)

    def _on_manager_page(self, status: int, headers: dict[str, str], body: bytes) -> None:
        if not self._check(status, body, "DAT-o-MATIC"):
            return
        button = dat_update.parse_download_button(body.decode("utf-8", "replace"))
        if button is None:
            self._fail(self.tr("DAT-o-MATIC: Download-Knopf nicht gefunden."))
            return
        self.status.emit(self.tr("No-Intro: Paket wird heruntergeladen …"))
        self._post(
            self._manager_url, [(button, "Download!!")], self._on_nointro_pack, self._manager_url
        )

    def _on_nointro_pack(self, status: int, headers: dict[str, str], body: bytes) -> None:
        if not self._check(status, body, "No-Intro"):
            return
        if body[:2] != b"PK":
            self._fail(self.tr("No-Intro: Die Antwort ist kein ZIP-Archiv."))
            return
        self._nointro_pack = body
        name = dat_update.filename_from_disposition(headers.get("content-disposition", ""))
        self.status.emit(self.tr("No-Intro: {0} geladen.").format(name or "Paket"))
        self.status.emit(self.tr("Redump: Systemliste wird geladen …"))
        self._get(dat_update.REDUMP_DOWNLOADS_URL, self._on_redump_page)

    def _on_redump_page(self, status: int, headers: dict[str, str], body: bytes) -> None:
        if not self._check(status, body, "Redump"):
            return
        self._redump_queue = dat_update.parse_redump_systems(body.decode("utf-8", "replace"))
        self._redump_total = len(self._redump_queue)
        if not self._redump_queue:
            self._fail(self.tr("Redump: keine Systeme gefunden."))
            return
        self.status.emit(self.tr("Redump: {0} DATs werden geladen …").format(self._redump_total))
        self._next_redump()

    def _next_redump(self) -> None:
        if not self._running:
            return
        if not self._redump_queue:
            self._write()
            return
        system = self._redump_queue.pop(0)
        self.progress.emit(self._redump_total - len(self._redump_queue), self._redump_total)
        url = dat_update.REDUMP_DATFILE_URL.format(code=system.code)
        self._get(url, lambda s, h, b: self._on_redump_dat(system, s, h, b))

    def _on_redump_dat(
        self,
        system: dat_update.RedumpSystem,
        status: int,
        headers: dict[str, str],
        body: bytes,
    ) -> None:
        filename = dat_update.filename_from_disposition(headers.get("content-disposition", ""))
        dats: list[DatFile] = []
        if status == 200 and filename:
            try:
                dats = dat_update.extract_redump(filename, body, system.code)
            except zipfile.BadZipFile:
                self.status.emit(self.tr("Redump: {0} ist beschädigt.").format(system.name))
        else:
            self.status.emit(
                self.tr("Redump: {0} nicht verfügbar (HTTP {1}).").format(system.name, status)
            )
        self._redump_dats += dats
        matches = dat_update.match_dats(dats, self._rules, self._platforms)
        if system.has_cues and any(match.platform for match in matches):
            # Korrekte CUE-Dateien nur für Systeme laden, die RomM auch kennt.
            QTimer.singleShot(dat_update.REDUMP_DELAY_MS, lambda: self._fetch_cues(system))
            return
        self._timer.start(dat_update.REDUMP_DELAY_MS)

    def _fetch_cues(self, system: dat_update.RedumpSystem) -> None:
        if not self._running:
            return
        url = dat_update.REDUMP_CUES_URL.format(code=system.code)
        self._get(url, lambda s, h, b: self._on_redump_cues(system, s, b))

    def _on_redump_cues(self, system: dat_update.RedumpSystem, status: int, body: bytes) -> None:
        if status == 200 and body[:2] == b"PK":
            try:
                cues = dat_update.extract_cues(body)
            except zipfile.BadZipFile:
                cues = {}
            self._cue_packs[system.code] = cues
            self.status.emit(
                self.tr("Redump: {0} CUE-Dateien für {1}.").format(len(cues), system.name)
            )
        else:
            self.status.emit(
                self.tr("Redump: CUE-Dateien für {0} nicht verfügbar.").format(system.name)
            )
        self._timer.start(dat_update.REDUMP_DELAY_MS)

    def _write(self) -> None:
        self.progress.emit(0, 0)
        self.status.emit(self.tr("DATs werden zugeordnet und geschrieben …"))
        task = _WriteTask(
            self._dats_dir,
            self._nointro_pack,
            self._redump_dats,
            self._rules,
            self._platforms,
            self._cue_packs,
        )
        task.signals.done.connect(self._on_written)
        task.signals.error.connect(
            lambda message: self._fail(self.tr("Schreiben fehlgeschlagen: {0}").format(message))
        )
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _on_written(self, result: dat_update.DatUpdateResult) -> None:
        self._task = None
        logger.info("DATs aktualisiert: %d Dateien nach %s", len(result.written), self._dats_dir)
        self._set_running(False)
        self.finished.emit(result)

    # --- Hilfen ---------------------------------------------------------------------------

    def _check(self, status: int, body: bytes, source: str) -> bool:
        if not self._running:
            return False
        if status != 200:
            self._fail(self.tr("{0} ist nicht erreichbar (HTTP {1}).").format(source, status))
            return False
        return True

    def _fail(self, message: str) -> None:
        self._task = None
        self._timer.stop()
        if self._running:
            logger.error("DAT-Aktualisierung fehlgeschlagen: %s", message)
            self._set_running(False)
            self.failed.emit(message)

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.running_changed.emit(running)

    def _request(self, url: str, referer: str | None = None) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(DOWNLOAD_TIMEOUT_MS)
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, dat_update.USER_AGENT)
        if referer:
            request.setRawHeader(b"Referer", referer.encode())
        return request

    def _get(self, url: str, handler: ResponseHandler) -> None:
        self._send(self._network.get(self._request(url)), handler)

    def _post(
        self,
        url: str,
        fields: list[tuple[str, str]],
        handler: ResponseHandler,
        referer: str | None = None,
    ) -> None:
        request = self._request(url, referer)
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/x-www-form-urlencoded"
        )
        # Weiterleitungen selbst verfolgen, um die Download-Seite zu erfahren.
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        query = "&".join(
            f"{QUrl.toPercentEncoding(key).data().decode()}="
            f"{QUrl.toPercentEncoding(value).data().decode()}"
            for key, value in fields
        )
        self._send(self._network.post(request, QByteArray(query.encode())), handler)

    def _send(self, reply: QNetworkReply, handler: ResponseHandler) -> None:
        self._reply = reply

        def on_finished() -> None:
            if not shiboken6.isValid(reply):
                return
            reply.deleteLater()
            if self._reply is reply:
                self._reply = None
            if not self._running:
                return
            status = int(reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0)
            if status == 0:
                self._fail(self.tr("Netzwerkfehler: {0}").format(reply.errorString()))
                return
            headers = {
                bytes(name.data()).decode("latin-1").lower(): bytes(value.data()).decode("latin-1")
                for name, value in reply.rawHeaderPairs()
            }
            handler(status, headers, bytes(reply.readAll().data()))

        reply.finished.connect(on_finished)
