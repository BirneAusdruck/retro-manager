"""Archive (7z, ZIP, RAR, TAR …) der Bibliothek: erkennen, Ziele planen, Entpacktes einsortieren.

Ausgeführt wird mit 7-Zip (Argumente in `core/tools.py`); hier steht nur die reine Logik.
Entpackt und gepackt wird immer zuerst in einen Arbeitsordner; erst fertige und geprüfte
Ergebnisse kommen in die Bibliothek (Struktur A: `roms/<plattform>/[<Spiel>/]`).
"""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from retro_manager.core.archive_names import (  # noqa: F401 – auch für Aufrufer
    archive_label,
    archive_stem,
    archive_suffix,
    is_archive,
    is_compressed_tar,
    is_secondary_volume,
    volumes,
)
from retro_manager.core.library import LibraryGame, image_files

ARCHIVE_WORK_DIRNAME = "archive"
PART_SUFFIX = ".part"

_PROGRESS = re.compile(r"^(\d{1,3})%")

# Packformat -> (7-Zip-Typ, Dateiendung)
PACK_FORMATS = {"zip": ("zip", ".zip"), "7z": ("7z", ".7z")}
# Kompressionsstufe -> 7-Zip `-mx`
PACK_LEVELS = {"fast": 1, "normal": 5, "max": 9}


class ArchiveError(Exception):
    """Ein Archiv kann nicht verarbeitet werden (Meldung für den Nutzer)."""


@dataclass(frozen=True)
class PackPlan:
    """Was beim Packen einer Bibliothekseintrags entsteht."""

    names: tuple[str, ...]  # Dateien relativ zu `source_dir` (bei Archiven: Arbeitsordner)
    part: Path  # Zwischendatei im Arbeitsordner
    target: Path  # endgültiges Archiv in der Bibliothek


# --- Bibliothek ----------------------------------------------------------------------------------


def original_files(game: LibraryGame) -> list[Path]:
    """Dateien, die nach erfolgreichem Packen/Entpacken als „Original“ entfallen."""
    if game.kind == "archive":
        return volumes(game.path)
    if game.kind in ("cue", "gdi"):
        return image_files(game.path)
    return [game.path]


def work_dir(work_root: Path, game: LibraryGame) -> Path:
    """Eigener Arbeitsordner je Eintrag unter `<HDD>/.retro-manager-tmp/archive/`."""
    safe = re.sub(r"[^\w.() -]+", "_", game.key)
    return work_root / ARCHIVE_WORK_DIRNAME / safe


# --- Entpacken -----------------------------------------------------------------------------------


def find_inner_tar(directory: Path) -> Path:
    """Die eine `.tar`, die beim ersten Schritt aus `.tar.gz` & Co. entsteht."""
    tars = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".tar"]
    if len(tars) != 1:
        raise ArchiveError("Im gepackten TAR wurde keine einzelne .tar-Datei gefunden.")
    return tars[0]


def extracted_layout(staging: Path, destination: Path, stem: str) -> list[tuple[Path, Path]]:
    """Wohin der Inhalt von `staging` kommt: (Quelle, Ziel)-Paare.

    - genau eine Datei → direkt nach `destination/` (z. B. `Spiel.gb` neben das Archiv)
    - genau ein Ordner → dieser Ordner nach `destination/`
    - mehrere Einträge → als Spielordner `destination/<stem>/` (Struktur A)

    Wirft ArchiveError, wenn ein Ziel schon existiert oder das Archiv leer war.
    """
    entries = sorted(staging.iterdir(), key=lambda p: p.name.lower())
    if not entries:
        raise ArchiveError("Das Archiv ist leer.")
    if len(entries) == 1:
        moves = [(entries[0], destination / entries[0].name)]
    else:
        moves = [(staging, destination / stem)]
    for _, target in moves:
        if target.exists():
            raise ArchiveError(f"{target.name} existiert bereits in {destination}.")
    return moves


def move_into_place(moves: list[tuple[Path, Path]]) -> list[Path]:
    """Verschiebt Entpacktes an sein Ziel (gleiches Laufwerk: nur Umbenennen)."""
    done = []
    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, target)
        done.append(target)
    return done


# --- Packen --------------------------------------------------------------------------------------


def pack_target(game: LibraryGame, archive_format: str) -> Path:
    _, suffix = PACK_FORMATS[archive_format]
    return game.path.parent / f"{game.name}{suffix}"


def check_pack_target(game: LibraryGame, archive_format: str) -> Path:
    """Ziel des Packens; ArchiveError, wenn es schon existiert (vor dem Entpacken prüfbar)."""
    if archive_format not in PACK_FORMATS:
        raise ArchiveError(f"Unbekanntes Packformat: {archive_format}")
    target = pack_target(game, archive_format)
    if target == game.path:
        raise ArchiveError(f"{game.path.name} liegt bereits als {archive_label(target)} vor.")
    if target.exists():
        raise ArchiveError(f"{target.name} existiert bereits.")
    return target


def plan_pack(
    game: LibraryGame, archive_format: str, work: Path, contents: list[str] | None = None
) -> PackPlan:
    """Plan für ein Archiv je Spiel neben dem Original.

    Bei Dateien werden das Image samt Tracks bzw. die ROM-Datei gepackt; bei Archiven
    (`contents`) der entpackte Inhalt aus dem Arbeitsordner (Umpacken, z. B. 7z → ZIP).
    """
    target = check_pack_target(game, archive_format)
    if contents is not None:
        names = tuple(contents)
    elif game.kind == "archive":
        raise ArchiveError("Archive müssen vor dem Umpacken entpackt werden.")
    else:
        names = tuple(path.name for path in original_files(game))
    if not names:
        raise ArchiveError(f"{game.path.name}: nichts zu packen.")
    return PackPlan(names, work / f"{target.name}{PART_SUFFIX}", target)


def remove_files(files: list[Path]) -> int:
    removed = 0
    for path in files:
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def parse_progress(text: str) -> float | None:
    """Letzte Prozentangabe aus 7-Zips Fortschrittsausgabe (mit `\\b` überschrieben)."""
    # Jede Fassung der Zeile steht zwischen Rückschritt-Zeichen und beginnt mit „NN%“;
    # Prozentzeichen im Dateinamen dahinter zählen nicht.
    value = None
    for segment in re.split(r"[\b\r\n]+", text):
        match = _PROGRESS.match(segment.strip())
        if match:
            value = min(1.0, int(match.group(1)) / 100)
    return value
