"""RomM-Endpunkte, Request-/Response-Datenklassen, Auth-Logik (RomM 5.4)."""

import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

HEARTBEAT_PATH = "/api/heartbeat"
TOKEN_PATH = "/api/token"
USERS_PATH = "/api/users"
SUPPORTED_PLATFORMS_PATH = "/api/platforms/supported"

CSRF_COOKIE = "romm_csrftoken"
CSRF_HEADER = "x-csrftoken"

ADMIN_ROLE = "admin"

# Von RomM erzwungene Mindestlänge für Passwörter.
MIN_PASSWORD_LENGTH = 6

# Wird von RomM auf die Rechte des Benutzers begrenzt.
TOKEN_SCOPES = (
    "me.read",
    "me.write",
    "roms.read",
    "roms.write",
    "roms.user.read",
    "roms.user.write",
    "platforms.read",
    "platforms.write",
    "collections.read",
    "collections.write",
    "assets.read",
    "assets.write",
    "firmware.read",
    "firmware.write",
    "users.read",
    "users.write",
    "tasks.run",
)


@dataclass(frozen=True)
class Heartbeat:
    version: str
    show_setup_wizard: bool


@dataclass(frozen=True)
class Token:
    access_token: str
    refresh_token: str
    expires_in: int


def base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def parse_heartbeat(data: dict[str, Any]) -> Heartbeat:
    system = data.get("SYSTEM", {})
    return Heartbeat(
        version=str(system.get("VERSION", "")),
        show_setup_wizard=bool(system.get("SHOW_SETUP_WIZARD", False)),
    )


def parse_token(data: dict[str, Any]) -> Token:
    return Token(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        expires_in=int(data.get("expires", 0)),
    )


def token_form(username: str, password: str) -> bytes:
    """Formular für den OAuth2-Password-Grant an /api/token."""
    return urlencode(
        {
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": " ".join(TOKEN_SCOPES),
        }
    ).encode()


def refresh_form(refresh_token: str) -> bytes:
    """Formular, um mit dem Refresh-Token ein neues Zugangstoken zu holen."""
    return urlencode({"grant_type": "refresh_token", "refresh_token": refresh_token}).encode()


def create_admin_body(username: str, password: str) -> bytes:
    """JSON für POST /api/users; nur ohne Anmeldung erlaubt, solange kein Admin existiert."""
    return json.dumps(
        {"username": username, "email": "", "password": password, "role": ADMIN_ROLE}
    ).encode()


def error_detail(body: bytes) -> str:
    """Fehlertext aus einer RomM-Fehlerantwort ({"detail": ...}); leer, wenn keiner lesbar ist."""
    try:
        detail = json.loads(body).get("detail", "")
    except ValueError, AttributeError:
        return ""
    if isinstance(detail, list):  # Validierungsfehler von FastAPI
        return "; ".join(str(item.get("msg", item)) for item in detail if item)
    return str(detail)


def basic_auth_header(username: str, password: str) -> str:
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {credentials}"


def web_login_script(auth_header: str) -> str:
    """JavaScript, das die eingebettete RomM-Oberfläche per Session anmeldet.

    Ist bereits eine Sitzung aktiv, passiert nichts. Sonst wird /api/login mit
    HTTP-Basic und CSRF-Token aufgerufen und die Seite neu geladen.
    """
    return f"""
(async () => {{
  const me = await fetch("/api/users/me", {{ credentials: "same-origin" }});
  if (me.ok) return;
  const csrf = document.cookie.split("; ")
    .find((c) => c.startsWith({json.dumps(CSRF_COOKIE + "=")}))?.split("=")[1] ?? "";
  const res = await fetch("/api/login", {{
    method: "POST",
    credentials: "same-origin",
    headers: {{ Authorization: {json.dumps(auth_header)}, {json.dumps(CSRF_HEADER)}: csrf }},
  }});
  if (res.ok) location.reload();
}})();
"""
