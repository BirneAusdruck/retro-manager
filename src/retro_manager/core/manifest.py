"""Manifest-Dateien: welche Dateien die App selbst angelegt hat (nur diese darf sie löschen)."""

import json
from pathlib import Path, PurePosixPath
from typing import Any


def is_safe_relative(entry: object) -> bool:
    """True für relative Pfade ohne `..`, damit ein Manifest nicht aus seinem Ordner greift."""
    if not isinstance(entry, str) or not entry:
        return False
    path = PurePosixPath(entry)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in entry


def read_json(path: Path, default: Any) -> Any:
    """Liest ein Manifest; fehlt es oder ist es kaputt, gilt `default`."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
