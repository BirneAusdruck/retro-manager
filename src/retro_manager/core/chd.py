"""CHD-Umwandlung mit chdman: Quellen einer Disc, Ziele in der Bibliothek, CHD-Kopf lesen.

Ablauf einer Umwandlung (ausgeführt vom Controller):
Archiv ggf. in den Arbeitsordner entpacken → chdman create in eine Zwischendatei →
chdman verify → Zwischendatei an ihren Platz in `roms/<plattform>/` verschieben →
Originale löschen (abschaltbar).
"""

import re
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

from retro_manager.core.library import (  # noqa: F401 – auch für Aufrufer
    LibraryGame,
    cue_files,
    gdi_files,
    image_files,
)

# RomM-Plattformen mit Disc-Spielen, die chdman verarbeiten kann.
# GameCube/Wii (RVZ) und Switch (NSZ) gehören nicht dazu, PS3 ebenfalls nicht.
CHD_PLATFORMS = {
    "psx": "PS1",
    "ps2": "PS2",
    "psp": "PSP",
    "dc": "Dreamcast",
    "saturn": "Saturn",
    "segacd": "Sega CD",
    "turbografx-cd": "PC Engine CD",
    "neo-geo-cd": "Neo Geo CD",
    "3do": "3DO",
    "pc-fx": "PC-FX",
    "philips-cd-i": "CD-i",
    "amiga-cd32": "Amiga CD32",
    "atari-jaguar-cd": "Jaguar CD",
}
# Plattformen, deren ISOs DVDs (bzw. UMDs) sind: createdvd statt createcd.
DVD_PLATFORMS = frozenset({"ps2", "psp"})

MEDIA_CD = "cd"
MEDIA_GD = "gd"  # GD-ROM (Dreamcast)
MEDIA_DVD = "dvd"

IMAGE_SUFFIXES = (".cue", ".gdi", ".iso")
CHD_SUFFIX = ".chd"
PART_SUFFIX = ".part"
CHDMAN_WORK_DIRNAME = "chdman"

_CHD_MAGIC = b"MComprHD"
# Metadaten-Tags im CHD-Kopf -> Medienart.
_MEDIA_TAGS = {
    b"CHT2": MEDIA_CD,
    b"CHTR": MEDIA_CD,
    b"CHCD": MEDIA_CD,
    b"CHGD": MEDIA_GD,
    b"CHGT": MEDIA_GD,
    b"DVD ": MEDIA_DVD,
}
_PROGRESS = re.compile(r"(\d+(?:\.\d+)?)% complete")


class ChdError(Exception):
    """Eine Disc kann nicht umgewandelt werden (Meldung für den Nutzer)."""


@dataclass(frozen=True)
class ChdHeader:
    version: int
    logical_size: int  # Größe des Inhalts (unkomprimiert)
    media: str | None  # cd, gd, dvd oder None (andere CHD-Arten, z. B. Festplatte)


@dataclass(frozen=True)
class Conversion:
    """Ein Disc-Image, das zu genau einer CHD wird."""

    image: Path  # CUE, GDI oder ISO
    media: str  # cd (createcd) oder dvd (createdvd)
    part: Path  # Zwischendatei im Arbeitsordner
    target: Path  # endgültige CHD in der Bibliothek


def is_convertible(game: LibraryGame) -> bool:
    return game.kind != "chd"


def media_for_image(slug: str, image: Path) -> str:
    """createdvd nur für ISOs von DVD-Systemen; CUE/GDI (auch PS2-CDs) sind immer CDs."""
    if image.suffix.lower() == ".iso" and slug in DVD_PLATFORMS:
        return MEDIA_DVD
    return MEDIA_CD


def source_files(game: LibraryGame) -> list[Path]:
    """Alle Dateien, die nach der Umwandlung entfallen (Archiv bzw. Image samt Tracks)."""
    if game.kind == "archive":
        return [game.path]
    return image_files(game.path)


def disc_images(directory: Path) -> list[Path]:
    """CUE/GDI/ISO in einem (entpackten) Ordner; ISOs, die eine CUE einbindet, zählen nicht."""
    found = sorted(
        (path for path in directory.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda path: str(path).lower(),
    )
    referenced = {
        file for image in found if image.suffix.lower() != ".iso" for file in image_files(image)[1:]
    }
    return [image for image in found if image not in referenced]


def plan_conversions(game: LibraryGame, images: list[Path], work_dir: Path) -> list[Conversion]:
    """CHD-Ziele neben dem Original (Struktur A: `roms/<plattform>/[<Spiel>/]`).

    Eine einzelne Disc heißt wie das Original in der Bibliothek, mehrere Discs aus einem
    Archiv heißen wie ihr jeweiliges Image. Wirft ChdError, wenn ein Ziel schon existiert.
    """
    if not images:
        raise ChdError(f"Kein Disc-Image (CUE, GDI, ISO) in {game.path.name} gefunden.")
    folder = game.path.parent
    conversions = []
    for image in images:
        name = game.name if len(images) == 1 else image.stem
        target = folder / f"{name}{CHD_SUFFIX}"
        if target.exists():
            raise ChdError(f"{target.name} existiert bereits.")
        part = work_dir / f"{name}{CHD_SUFFIX}{PART_SUFFIX}"
        conversions.append(Conversion(image, media_for_image(game.slug, image), part, target))
    if len({conversion.target for conversion in conversions}) < len(conversions):
        raise ChdError(f"{game.path.name} enthält mehrere Discs mit gleichem Namen.")
    return conversions


def game_work_dir(work_root: Path, game: LibraryGame) -> Path:
    """Eigener Arbeitsordner je Disc unter `<HDD>/.retro-manager-tmp/chdman/`."""
    safe = re.sub(r"[^\w.() -]+", "_", game.key)
    return work_root / CHDMAN_WORK_DIRNAME / safe


def required_space(game: LibraryGame, unpacked_size: int | None = None) -> int:
    """Platzbedarf im Arbeitsordner: entpacktes Archiv plus CHD (höchstens so groß wie roh)."""
    if game.kind == "archive":
        return 2 * (unpacked_size or game.size * 3)
    return sum(path.stat().st_size for path in image_files(game.path))


def finish_conversion(conversions: list[Conversion]) -> list[Path]:
    """Verschiebt geprüfte Zwischendateien an ihr Ziel; liefert die neuen CHDs."""
    done = []
    for conversion in conversions:
        conversion.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(conversion.part, conversion.target)
        done.append(conversion.target)
    return done


def remove_files(files: list[Path]) -> int:
    removed = 0
    for path in files:
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def target_key(game: LibraryGame, chd: Path) -> str:
    """Bibliotheksschlüssel einer erzeugten CHD (gleiches Schema wie `LibraryGame.key`)."""
    parts = [game.slug, game.game_dir, chd.name] if game.game_dir else [game.slug, chd.name]
    return "/".join(parts)


# --- Zurückwandeln -------------------------------------------------------------------------------


def extract_target(target_root: Path, game: LibraryGame, media: str) -> Path:
    """Ordner für die zurückgewandelte Disc: CDs/GD-ROMs (mehrere Tracks) bekommen einen
    eigenen Ordner, DVDs landen als einzelne ISO direkt im Zielordner."""
    return target_root if media == MEDIA_DVD else target_root / game.name


def extract_outputs_exist(target_dir: Path, name: str, media: str) -> bool:
    suffix = {MEDIA_DVD: ".iso", MEDIA_GD: ".gdi"}.get(media, ".cue")
    return (target_dir / f"{name}{suffix}").exists()


# --- CHD-Kopf ------------------------------------------------------------------------------------


def read_header(path: Path) -> ChdHeader | None:
    """Liest Version, Inhaltsgröße und Medienart aus dem Kopf einer CHD (v5); sonst None."""
    try:
        with path.open("rb") as file:
            head = file.read(64)
            if len(head) < 56 or head[:8] != _CHD_MAGIC:
                return None
            version = struct.unpack(">I", head[12:16])[0]
            if version != 5:
                return ChdHeader(version, 0, None)
            logical_size = struct.unpack(">Q", head[32:40])[0]
            offset = struct.unpack(">Q", head[48:56])[0]
            media = None
            seen = set()
            while offset and offset not in seen and media is None:
                seen.add(offset)
                file.seek(offset)
                entry = file.read(16)
                if len(entry) < 16:
                    break
                media = _MEDIA_TAGS.get(entry[:4])
                offset = struct.unpack(">Q", entry[8:16])[0]
            return ChdHeader(version, logical_size, media)
    except OSError:
        return None


def parse_progress(line: str) -> float | None:
    """`Compressing, 54.1% complete... (ratio=89.1%)` → 0.541."""
    match = _PROGRESS.search(line)
    return min(1.0, float(match.group(1)) / 100) if match else None
