"""Befehlsaufbau für Igir und chdman."""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

IGIR_DIRNAME = "igir"
CHDMAN_DIRNAME = "chdman"
SEVENZIP_DIRNAME = "7zip"
# Igir-Version, auf die die App abgestimmt ist (Argumente, consoleTokens.json).
IGIR_VERSION = "5.7.2"

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def igir_executable(tools_dir: Path) -> Path:
    """Erwarteter Pfad der Igir-Programmdatei (einzige plattformabhängige Stelle)."""
    name = "igir.exe" if sys.platform == "win32" else "igir"
    return tools_dir / IGIR_DIRNAME / name


def chdman_executable(tools_dir: Path) -> Path | None:
    """chdman aus `tools/chdman/`, sonst aus dem PATH (z. B. Paket mame-tools); None, wenn keins."""
    name = "chdman.exe" if sys.platform == "win32" else "chdman"
    local = tools_dir / CHDMAN_DIRNAME / name
    if local.is_file():
        return local
    found = shutil.which("chdman")
    return Path(found) if found else None


def sevenzip_executable(tools_dir: Path) -> Path | None:
    """7-Zip aus `tools/7zip/` (offizieller Build `7zz` bzw. `7za.exe`), sonst aus dem PATH."""
    name = "7za.exe" if sys.platform == "win32" else "7zz"
    local = tools_dir / SEVENZIP_DIRNAME / name
    if local.is_file():
        return local
    for candidate in ("7zz", "7z"):
        found = shutil.which(candidate)
        if found:
            return Path(found)
    return None


# Fortschritt auf die Standardausgabe, normale Meldungen aus, Fehler auf die Fehlerausgabe.
_SEVENZIP_OUTPUT = ["-bsp1", "-bso0", "-bse2"]


def sevenzip_extract_args(archive: Path, target_dir: Path) -> list[str]:
    """Entpackt mit Ordnerstruktur; `-y` beantwortet Rückfragen (Zielordner ist neu und leer)."""
    return ["x", str(archive), f"-o{target_dir}", "-y", *_SEVENZIP_OUTPUT]


def sevenzip_test_args(archive: Path) -> list[str]:
    """Prüft alle Einträge gegen ihre gespeicherten CRCs; Rückgabewert 0 = in Ordnung."""
    return ["t", str(archive), *_SEVENZIP_OUTPUT]


def sevenzip_pack_args(archive_type: str, level: int, output: Path, names: list[str]) -> list[str]:
    """Packt `names` (relativ zum Arbeitsordner des Prozesses) nach `output`.

    `--` beendet die Optionen, damit Dateinamen mit führendem `-` keine Schalter werden.
    """
    return [
        "a",
        f"-t{archive_type}",
        f"-mx={level}",
        "-mmt=on",
        *_SEVENZIP_OUTPUT,
        str(output),
        "--",
        *names,
    ]


def chdman_extract_args(media: str, chd: Path, target_dir: Path, name: str) -> list[str]:
    """chdman-Argumente, um eine CHD zurückzuwandeln.

    CDs werden mit `--splitbin` je Track geschrieben (`Name (Track 1).bin` wie bei Redump),
    GD-ROMs (Dreamcast) als GDI mit einer Datei je Track, DVDs als ISO.
    `-f` überschreibt vorhandene Dateien.
    """
    if media == "dvd":
        return ["extractdvd", "-i", str(chd), "-o", str(target_dir / f"{name}.iso"), "-f"]
    if media == "gd":
        return ["extractcd", "-i", str(chd), "-o", str(target_dir / f"{name}.gdi"), "-f"]
    return ["extractcd", "-i", str(chd), "-o", str(target_dir / f"{name}.cue"), "--splitbin", "-f"]


def chdman_create_args(media: str, image: Path, output: Path) -> list[str]:
    """chdman-Argumente, um aus CUE/GDI (`cd`) bzw. ISO (`dvd`) eine CHD zu erzeugen."""
    command = "createdvd" if media == "dvd" else "createcd"
    return [command, "-i", str(image), "-o", str(output), "-f"]


def chdman_verify_args(chd: Path) -> list[str]:
    """Prüft die in der CHD gespeicherten SHA1-Prüfsummen; Rückgabewert 0 = in Ordnung."""
    return ["verify", "-i", str(chd)]


def chdman_info_args(chd: Path) -> list[str]:
    return ["info", "-i", str(chd)]


def igir_verify_args(
    input_dir: Path, dat_dir: Path, report_path: Path, extra_inputs: list[Path] | None = None
) -> list[str]:
    """Argumente für `igir test report`: prüft Eingabedateien gegen DATs, ohne zu schreiben.

    `extra_inputs` (z. B. korrekte Redump-CUEs) ergänzen unvollständige Disc-Dumps.
    """
    args = ["test", "report", "--dat", str(dat_dir), "--input", str(input_dir)]
    for extra in extra_inputs or []:
        args += ["--input", str(extra)]
    return args + ["--report-output", str(report_path)]


def cue_inputs(input_dir: Path, cues_root: Path | None) -> list[Path]:
    """CUE-Ordner, die zur Prüfung von `input_dir` passen.

    Heißt der Eingabeordner wie eine RomM-Plattform (z. B. `roms/psx`), nur deren CUEs,
    sonst alle vorhandenen.
    """
    if cues_root is None or not cues_root.is_dir():
        return []
    matching = cues_root / input_dir.name
    if matching.is_dir():
        return [matching]
    return sorted(path for path in cues_root.iterdir() if path.is_dir())


def report_path(reports_dir: Path, now: datetime) -> Path:
    """Dateiname für einen Igir-Report; ohne `%`, damit Igir keine Tokens ersetzt."""
    return reports_dir / f"igir_report_{now:%Y-%m-%d_%H-%M-%S}.csv"


def clean_output(text: str) -> list[str]:
    """Teilt Programmausgabe in Zeilen, entfernt ANSI-Farbcodes und leere Zeilen.

    Fortschrittsanzeigen überschreiben ihre Zeile mit `\\r`; jede Fassung wird hier
    zu einer eigenen Zeile.
    """
    lines = re.split(r"\r\n|\r|\n", _ANSI_ESCAPE.sub("", text))
    return [line.rstrip() for line in lines if line.strip()]
