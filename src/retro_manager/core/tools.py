"""Befehlsaufbau für Igir und chdman."""

import re
import sys
from datetime import datetime
from pathlib import Path

IGIR_DIRNAME = "igir"
# Igir-Version, auf die die App abgestimmt ist (Argumente, consoleTokens.json).
IGIR_VERSION = "5.7.2"

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def igir_executable(tools_dir: Path) -> Path:
    """Erwarteter Pfad der Igir-Programmdatei (einzige plattformabhängige Stelle)."""
    name = "igir.exe" if sys.platform == "win32" else "igir"
    return tools_dir / IGIR_DIRNAME / name


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
