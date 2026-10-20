"""Spiele der Bibliothek lesen (RomM-Struktur A: roms/<plattform>/[<Spiel>/]).

`scan_entries` findet alle Einträge einer Plattform – Archive, Disc-Images, einzelne ROMs –
und ist die einzige Stelle, die Plattformordner durchsucht. Die Reiter wählen daraus, was
sie verarbeiten können (z. B. `scan_platform` für Disc-Spiele).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from retro_manager.core.archive_names import (
    archive_stem,
    archive_suffix,
    is_archive,
    is_secondary_volume,
    volumes,
)

# Disc-Images: Dateiendung -> Art. BIN-Dateien zählen nur über ihre CUE bzw. GDI.
DISC_KINDS = {
    ".chd": "chd",
    ".iso": "iso",
    ".cue": "cue",
    ".gdi": "gdi",  # Dreamcast (GD-ROM)
}
KIND_ARCHIVE = "archive"  # jedes von 7-Zip lesbare Archiv (`archive_names.is_archive`)
KIND_FILE = "file"  # alles andere, z. B. eine ROM-Datei `Spiel.gb`
# Archive, die chdman- und Export-Reiter selbst entpacken (zipfile, py7zr).
DISC_ARCHIVE_SUFFIXES = (".7z", ".zip")


@dataclass(frozen=True)
class LibraryGame:
    """Ein Eintrag der Bibliothek, z. B. `roms/psx/Spiel (Disc 1).chd` oder `roms/gb/Tetris.zip`."""

    slug: str  # RomM-Plattform
    name: str  # Dateiname ohne Endung
    path: Path
    kind: str  # chd, iso, cue, gdi, archive, file
    size: int
    game_dir: str = ""  # Spielordner bei Spielen aus mehreren Dateien, sonst leer

    @property
    def key(self) -> str:
        """Eindeutiger Schlüssel relativ zur Plattform, z. B. `psx/FF8/FF8 (Disc 1).chd`."""
        parts = (
            [self.slug, self.game_dir, self.path.name]
            if self.game_dir
            else [self.slug, self.path.name]
        )
        return "/".join(parts)


def scan_entries(roms_dir: Path, slug: str) -> list[LibraryGame]:
    """Alle Einträge einer Plattform: Archive, Disc-Images und einzelne ROM-Dateien.

    Eine Ebene in Spielordner hinein (RomM-Unterordner wie `dlc/` bleiben außen vor).
    BINs/Tracks, die eine CUE oder GDI einbindet, und weitere Teile mehrteiliger Archive
    erscheinen nicht einzeln; die Größe umfasst alle Tracks bzw. Teile.
    """
    platform_dir = roms_dir / slug
    if not platform_dir.is_dir():
        return []
    entries = sorted(platform_dir.iterdir(), key=lambda path: path.name.lower())
    # Dateien eines Ordners gemeinsam betrachten, damit eingebundene Tracks wegfallen.
    loose = [entry for entry in entries if entry.is_file()]
    games = _entries_in(loose, slug, "")
    for folder in entries:
        if folder.is_dir() and not folder.name.startswith("."):
            files = sorted(
                (f for f in folder.iterdir() if f.is_file()), key=lambda p: p.name.lower()
            )
            games += _entries_in(files, slug, folder.name)
    return sorted(games, key=lambda game: (game.game_dir or game.name).lower())


def _entries_in(files: list[Path], slug: str, game_dir: str) -> list[LibraryGame]:
    files = [file for file in files if not file.name.startswith(".")]
    referenced: set[Path] = set()
    for file in files:
        if file.suffix.lower() in (".cue", ".gdi"):
            referenced.update(image_files(file)[1:])
    entries = []
    for file in files:
        if file in referenced or is_secondary_volume(file):
            continue
        if is_archive(file):
            # Nachbarn mitgeben: sonst liest jedes Archiv den Ordner erneut.
            size = sum(part.stat().st_size for part in volumes(file, files))
            name = archive_stem(file)
            entries.append(LibraryGame(slug, name, file, KIND_ARCHIVE, size, game_dir))
            continue
        kind = DISC_KINDS.get(file.suffix.lower(), KIND_FILE)
        size = sum(source.stat().st_size for source in image_files(file))
        entries.append(LibraryGame(slug, file.stem, file, kind, size, game_dir))
    return entries


def scan_platform(roms_dir: Path, slug: str) -> list[LibraryGame]:
    """Disc-Spiele einer Plattform für chdman und Export: Images und 7z/ZIP-Archive."""
    return [game for game in scan_entries(roms_dir, slug) if is_disc_source(game)]


def is_disc_source(game: LibraryGame) -> bool:
    """Disc-Image (CHD, ISO, CUE, GDI) oder ein Archiv, das die App selbst entpacken kann."""
    if game.kind in DISC_KINDS.values():
        return True
    return game.kind == KIND_ARCHIVE and archive_suffix(game.path) in DISC_ARCHIVE_SUFFIXES


def platforms(roms_dir: Path) -> list[str]:
    """Plattformordner unter `roms/` (sichtbare Ordner, alphabetisch)."""
    if not roms_dir.is_dir():
        return []
    return sorted(
        (p.name for p in roms_dir.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=str.lower,
    )


# --- Disc-Images und ihre Tracks ----------------------------------------------------------------


def cue_files(cue: Path) -> list[Path]:
    """Die von einer CUE referenzierten Dateien (BINs) im selben Ordner."""
    files = []
    for line in cue.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("FILE "):
            continue
        rest = stripped[5:].strip()
        name = (
            rest.split('"')[1] if rest.startswith('"') and rest.count('"') >= 2 else rest.split()[0]
        )
        candidate = cue.parent / Path(name).name
        if candidate.is_file() and candidate not in files:
            files.append(candidate)
    return files


def gdi_files(gdi: Path) -> list[Path]:
    """Die Track-Dateien einer GDI (`1 0 4 2352 "track 01.bin" 0`) im selben Ordner."""
    files = []
    lines = gdi.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[1:]:
        match = re.match(r'\s*\d+\s+\d+\s+\d+\s+\d+\s+(?:"([^"]+)"|(\S+))', line)
        if not match:
            continue
        candidate = gdi.parent / Path(match.group(1) or match.group(2)).name
        if candidate.is_file() and candidate not in files:
            files.append(candidate)
    return files


def image_files(image: Path) -> list[Path]:
    """Das Image selbst und alle Dateien, auf die es verweist."""
    suffix = image.suffix.lower()
    if suffix == ".cue":
        return [image, *cue_files(image)]
    if suffix == ".gdi":
        return [image, *gdi_files(image)]
    return [image]
