"""Zugriff auf keyring (Passwörter, API-Schlüssel, Geheimnisse für Docker)."""

import keyring
from keyring.errors import KeyringError

SERVICE = "retro-manager"

ROMM_PASSWORD = "romm_password"
DB_PASSWORD = "db_password"
DB_ROOT_PASSWORD = "db_root_password"
AUTH_SECRET_KEY = "romm_auth_secret_key"


class CredentialsError(Exception):
    """Der Systemschlüsselbund ist nicht verfügbar oder verweigert den Zugriff."""


def get_secret(key: str) -> str | None:
    """Liest ein Geheimnis aus dem Systemschlüsselbund; None, wenn es fehlt."""
    try:
        return keyring.get_password(SERVICE, key)
    except KeyringError as error:
        raise CredentialsError(str(error)) from error


def set_secret(key: str, value: str) -> None:
    """Speichert ein Geheimnis im Systemschlüsselbund."""
    try:
        keyring.set_password(SERVICE, key, value)
    except KeyringError as error:
        raise CredentialsError(str(error)) from error
