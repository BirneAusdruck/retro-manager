"""Archivdateien am Namen erkennen: Endungen, mehrteilige Archive, Anzeige des Formats.

Reine Namenslogik ohne Dateizugriffe (außer `volumes` ohne mitgegebene Nachbarn), damit
`library` und `archives` sie gemeinsam nutzen können.
"""

import re
from pathlib import Path

# Einfache Endungen, die 7-Zip entpacken kann.
_SIMPLE_SUFFIXES = (
    ".7z",
    ".zip",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".tgz",
    ".tbz",
    ".tbz2",
    ".txz",
)
# Gepackte TARs: 7-Zip entpackt sie in zwei Schritten (erst zur .tar, dann deren Inhalt).
_TAR_COMPRESSED = (".tar.gz", ".tar.bz2", ".tar.xz")
_TAR_SHORT = (".tgz", ".tbz", ".tbz2", ".txz")

_RAR_PART = re.compile(r"\.part(\d+)\.rar$", re.IGNORECASE)
_RAR_OLD_VOLUME = re.compile(r"\.r\d\d$", re.IGNORECASE)
_SPLIT_VOLUME = re.compile(r"\.(7z|zip|rar)\.(\d{3})$", re.IGNORECASE)
_ZIP_SPLIT = re.compile(r"\.z\d\d$", re.IGNORECASE)


def archive_suffix(path: Path) -> str | None:
    """Archivendung in Kleinbuchstaben (`.7z`, `.tar.gz`, `.part1.rar`, `.7z.001`) oder None.

    Weitere Teile eines mehrteiligen Archivs (`.part2.rar`, `.r00`, `.7z.002`, `.z01`) ergeben
    None; sie gehören zum ersten Teil.
    """
    name = path.name.lower()
    if is_secondary_volume(path):
        return None
    split = _SPLIT_VOLUME.search(name)
    if split:
        return split.group(0)
    rar_part = _RAR_PART.search(name)
    if rar_part:
        return rar_part.group(0)
    for suffix in _TAR_COMPRESSED:
        if name.endswith(suffix):
            return suffix
    for suffix in _SIMPLE_SUFFIXES:
        if name.endswith(suffix):
            return suffix
    return None


def is_archive(path: Path) -> bool:
    return archive_suffix(path) is not None


def is_secondary_volume(path: Path) -> bool:
    name = path.name.lower()
    rar_part = _RAR_PART.search(name)
    if rar_part:
        return int(rar_part.group(1)) > 1
    split = _SPLIT_VOLUME.search(name)
    if split:
        return int(split.group(2)) > 1
    return bool(_RAR_OLD_VOLUME.search(name) or _ZIP_SPLIT.search(name))


def is_compressed_tar(path: Path) -> bool:
    suffix = archive_suffix(path) or ""
    return suffix in _TAR_COMPRESSED or suffix in _TAR_SHORT


def archive_stem(path: Path) -> str:
    """Name ohne Archivendung: `Spiel (USA).tar.gz` → `Spiel (USA)`."""
    suffix = archive_suffix(path)
    return path.name[: -len(suffix)] if suffix else path.stem


def archive_label(path: Path) -> str:
    """Anzeige des Formats, z. B. `7Z`, `TAR.GZ`, `RAR` (auch bei `.part1.rar`)."""
    suffix = archive_suffix(path) or path.suffix
    if _RAR_PART.search(suffix):
        return "RAR"
    split = _SPLIT_VOLUME.search(suffix)
    if split:
        return split.group(1).upper()
    return suffix.lstrip(".").upper()


def volumes(path: Path, siblings: list[Path] | None = None) -> list[Path]:
    """Alle Dateien eines (ggf. mehrteiligen) Archivs, erster Teil zuerst.

    `siblings` sind die Dateien im selben Ordner; ohne Angabe wird der Ordner gelesen.
    """
    name = path.name
    rar_part = _RAR_PART.search(name)
    split = _SPLIT_VOLUME.search(name)
    if rar_part:
        prefix = name[: rar_part.start()]
        pattern = re.compile(re.escape(prefix) + r"\.part\d+\.rar$", re.IGNORECASE)
    elif split:
        prefix = name[: split.start(2)]
        pattern = re.compile(re.escape(prefix) + r"\d{3}$", re.IGNORECASE)
    elif name.lower().endswith(".rar"):
        pattern = re.compile(re.escape(path.stem) + r"\.r\d\d$", re.IGNORECASE)
    elif name.lower().endswith(".zip"):
        pattern = re.compile(re.escape(path.stem) + r"\.z\d\d$", re.IGNORECASE)
    else:
        return [path]
    candidates = siblings if siblings is not None else list(path.parent.iterdir())
    others = sorted(p for p in candidates if p != path and pattern.fullmatch(p.name))
    return [path, *others]
