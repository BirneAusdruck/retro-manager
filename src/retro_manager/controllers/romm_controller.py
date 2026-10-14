"""QNetworkAccessManager: Heartbeat, Erst-Admin, Login, Token."""

import json
import logging
from collections.abc import Callable

from PySide6.QtCore import QByteArray, QDeadlineTimer, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from retro_manager.core import romm_api
from retro_manager.core.romm_api import Heartbeat, Token

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_MS = 2000
REQUEST_TIMEOUT_MS = 10000

ReplyHandler = Callable[[int, bytes], None]


class RommController(QObject):
    """Kommuniziert mit der RomM-REST-API."""

    ready = Signal(object)  # Heartbeat
    admin_created = Signal()
    admin_rejected = Signal(str)  # RomM lehnt Benutzername/Passwort ab
    logged_in = Signal()
    login_failed = Signal(str)
    failed = Signal(str)
    # Abfragen nach dem Start (z. B. Plattformliste); getrennt von `failed` des Startablaufs.
    supported_platforms_ready = Signal(object)  # list[dict]
    request_failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._network = QNetworkAccessManager(self)
        self._base_url = ""
        self._token: Token | None = None
        self._deadline = QDeadlineTimer()
        self._poll_timer = QTimer(self)
        self._poll_timer.setSingleShot(True)
        self._poll_timer.setInterval(HEARTBEAT_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_heartbeat)

    @property
    def token(self) -> Token | None:
        return self._token

    def wait_until_ready(self, base_url: str, timeout_ms: int) -> None:
        """Fragt den Heartbeat ab, bis RomM antwortet oder das Zeitlimit abläuft."""
        self._base_url = base_url
        self._deadline = QDeadlineTimer(timeout_ms)
        self._poll_heartbeat()

    def create_admin(self, username: str, password: str) -> None:
        """Legt den ersten Admin an (nur möglich, solange RomM noch keinen hat)."""
        request = self._request(romm_api.USERS_PATH)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        csrf = self._csrf_token()
        if csrf:
            request.setRawHeader(romm_api.CSRF_HEADER.encode(), csrf)
        reply = self._network.post(
            request, QByteArray(romm_api.create_admin_body(username, password))
        )
        self._handle(reply, self._on_admin_reply)

    def login(self, username: str, password: str) -> None:
        """Meldet sich per OAuth2-Password-Grant an und merkt sich das Token."""
        request = self._request(romm_api.TOKEN_PATH)
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/x-www-form-urlencoded"
        )
        reply = self._network.post(request, QByteArray(romm_api.token_form(username, password)))
        self._handle(reply, self._on_token_reply)

    def fetch_supported_platforms(self) -> None:
        """Fragt alle Plattformen ab, die RomM unterstützt."""
        self._authorized_get(
            romm_api.SUPPORTED_PLATFORMS_PATH, self.supported_platforms_ready.emit, retry=True
        )

    def _authorized_get(self, path: str, on_success: Callable[[object], None], retry: bool) -> None:
        if self._token is None:
            self.request_failed.emit(self.tr("Die App ist nicht bei RomM angemeldet."))
            return
        request = self._request(path)
        request.setRawHeader(b"Authorization", f"Bearer {self._token.access_token}".encode())
        reply = self._network.get(request)
        self._handle(
            reply,
            lambda status, body: self._on_authorized_reply(status, body, path, on_success, retry),
        )

    def _on_authorized_reply(
        self,
        status: int,
        body: bytes,
        path: str,
        on_success: Callable[[object], None],
        retry: bool,
    ) -> None:
        if status == 401 and retry:
            # Zugangstoken abgelaufen: einmal erneuern und die Anfrage wiederholen.
            self._refresh_token(lambda: self._authorized_get(path, on_success, retry=False))
            return
        if status != 200:
            self.request_failed.emit(
                self.tr("RomM-Anfrage fehlgeschlagen (HTTP {0}).").format(status)
            )
            return
        try:
            data = json.loads(body)
        except ValueError:
            self.request_failed.emit(self.tr("Ungültige Antwort von RomM."))
            return
        on_success(data)

    def _refresh_token(self, then: Callable[[], None]) -> None:
        token = self._token
        if token is None or not token.refresh_token:
            self.request_failed.emit(self.tr("Die Anmeldung bei RomM ist abgelaufen."))
            return
        request = self._request(romm_api.TOKEN_PATH)
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/x-www-form-urlencoded"
        )
        reply = self._network.post(request, QByteArray(romm_api.refresh_form(token.refresh_token)))
        self._handle(reply, lambda status, body: self._on_refresh_reply(status, body, then))

    def _on_refresh_reply(self, status: int, body: bytes, then: Callable[[], None]) -> None:
        old = self._token
        try:
            new = romm_api.parse_token(json.loads(body)) if status == 200 else None
        except ValueError, KeyError:
            new = None
        if new is None or old is None:
            self.request_failed.emit(
                self.tr("Die Anmeldung bei RomM ist abgelaufen. Bitte die App neu starten.")
            )
            return
        # RomM schickt beim Erneuern nicht immer ein neues Refresh-Token mit.
        self._token = Token(
            new.access_token, new.refresh_token or old.refresh_token, new.expires_in
        )
        logger.info("RomM-Zugangstoken erneuert")
        then()

    def _request(self, path: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(self._base_url + path))
        request.setTransferTimeout(REQUEST_TIMEOUT_MS)
        return request

    def _csrf_token(self) -> QByteArray | None:
        for cookie in self._network.cookieJar().cookiesForUrl(QUrl(self._base_url)):
            if bytes(cookie.name().data()).decode() == romm_api.CSRF_COOKIE:
                return cookie.value()
        return None

    def _handle(self, reply: QNetworkReply, handler: ReplyHandler) -> None:
        def on_finished() -> None:
            reply.deleteLater()
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0
            handler(int(status), bytes(reply.readAll().data()))

        reply.finished.connect(on_finished)

    def _poll_heartbeat(self) -> None:
        reply = self._network.get(self._request(romm_api.HEARTBEAT_PATH))
        self._handle(reply, self._on_heartbeat_reply)

    def _on_heartbeat_reply(self, status: int, body: bytes) -> None:
        if status == 200:
            try:
                heartbeat: Heartbeat = romm_api.parse_heartbeat(json.loads(body))
            except ValueError:
                logger.warning("Ungültige Heartbeat-Antwort")
            else:
                logger.info("RomM %s bereit", heartbeat.version)
                self.ready.emit(heartbeat)
                return
        if self._deadline.hasExpired():
            self.failed.emit(self.tr("RomM hat nicht rechtzeitig geantwortet."))
            return
        self._poll_timer.start()

    def _on_admin_reply(self, status: int, body: bytes) -> None:
        if status in (200, 201):
            logger.info("RomM-Admin angelegt")
            self.admin_created.emit()
            return
        detail = romm_api.error_detail(body)
        logger.error("Admin anlegen fehlgeschlagen (%s): %s", status, detail or body[:500])
        if status in (400, 422) and detail:
            self.admin_rejected.emit(self.tr("RomM hat das Konto abgelehnt: {0}").format(detail))
            return
        message = self.tr("Der RomM-Admin konnte nicht angelegt werden (HTTP {0}).").format(status)
        self.failed.emit(f"{message}\n\n{detail}" if detail else message)

    def _on_token_reply(self, status: int, body: bytes) -> None:
        if status == 200:
            try:
                self._token = romm_api.parse_token(json.loads(body))
            except ValueError, KeyError:
                self.failed.emit(self.tr("Ungültige Antwort von RomM beim Anmelden."))
                return
            logger.info("Bei RomM angemeldet")
            self.logged_in.emit()
            return
        if status in (400, 401, 403):
            self.login_failed.emit(self.tr("Benutzername oder Passwort ist falsch."))
            return
        self.failed.emit(self.tr("Anmeldung bei RomM fehlgeschlagen (HTTP {0}).").format(status))
