"""Gemeinsame Typen für lange Vorgänge (Aufbereiten, Entschlüsseln, Übertragen)."""

from collections.abc import Callable

ProgressCallback = Callable[[int, int], None]  # erledigte Bytes, gesamt
CancelCheck = Callable[[], bool]


class ExportCancelled(Exception):
    """Der Nutzer hat den Vorgang abgebrochen."""


class ExportError(Exception):
    """Eine Quelle lässt sich nicht verarbeiten (z. B. kaputtes Archiv)."""
