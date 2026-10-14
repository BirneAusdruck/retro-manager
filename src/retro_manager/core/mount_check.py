"""Prüft, ob ein Ordner auf einem eingehängten Laufwerk liegt (nicht nur, ob er existiert)."""

import os
from pathlib import Path


def mount_point(path: Path) -> Path:
    """Liefert den Einhängepunkt, auf dem der Pfad liegt."""
    current = path.resolve()
    while not os.path.ismount(current):
        current = current.parent
    return current


def is_on_mounted_drive(path: Path) -> bool:
    """True, wenn der Ordner existiert und auf einem eigenen Laufwerk liegt.

    Ein leerer Mount-Ordner existiert auch ohne eingehängte Platte, liegt dann aber
    auf dem Wurzeldateisystem – genau das wird hier erkannt.
    """
    if not path.is_dir():
        return False
    return mount_point(path) != Path(path.anchor or "/")
