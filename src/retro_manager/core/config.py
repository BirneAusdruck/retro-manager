"""Konfigurationsschema, INI-Pfad relativ zur Programmdatei."""

import configparser
import sys
from dataclasses import dataclass
from pathlib import Path

INI_FILENAME = "retro-manager.ini"
COMPOSE_DIRNAME = "docker"
WEBDATA_DIRNAME = "webdata"
TOOLS_DIRNAME = "tools"
REPORTS_DIRNAME = "reports"
DATS_DIRNAME = "dats"

_SECTION_ARCHIVE = "archive"
_SECTION_ROMM = "romm"
_SECTION_JOBS = "jobs"
_SECTION_IGIR = "igir"


@dataclass
class AppConfig:
    """Nicht geheime Einstellungen aus der INI-Datei."""

    hdd_path: Path | None = None
    romm_user: str = ""
    romm_port: int = 8080
    max_parallel_jobs: int = 2
    igir_input_dir: Path | None = None
    igir_dat_dir: Path | None = None

    @property
    def is_complete(self) -> bool:
        """True, wenn alle für den Start nötigen Angaben vorhanden sind."""
        return self.hdd_path is not None and bool(self.romm_user)


def is_dev_build() -> bool:
    """True beim Start aus dem Quellcode, False im gepackten Programm (PyInstaller)."""
    return not getattr(sys, "frozen", False)


def app_dir() -> Path:
    """Basisordner der Anwendung: neben der Programmdatei bzw. die Projektwurzel."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def ini_path(base: Path) -> Path:
    """Pfad der INI-Datei im Basisordner."""
    return base / INI_FILENAME


def compose_dir(base: Path) -> Path:
    """Ordner mit docker-compose.yml und .env im Basisordner."""
    return base / COMPOSE_DIRNAME


def webdata_dir(base: Path) -> Path:
    """Ordner für Cookies und Cache der eingebetteten RomM-Oberfläche."""
    return base / WEBDATA_DIRNAME


def tools_dir(base: Path) -> Path:
    """Ordner für mitgelieferte externe Programme (Igir, chdman)."""
    return base / TOOLS_DIRNAME


def reports_dir(base: Path) -> Path:
    """Ordner für Reports der externen Programme."""
    return base / REPORTS_DIRNAME


def dats_dir(hdd_path: Path) -> Path:
    """Ordner für DAT-Dateien auf der Archiv-HDD (neben roms/ und bios/)."""
    return hdd_path / DATS_DIRNAME


def _optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def _path_text(path: Path | None) -> str:
    return str(path) if path else ""


def load_config(path: Path) -> AppConfig:
    """Liest die INI-Datei; fehlende Datei oder Werte ergeben Standardwerte."""
    defaults = AppConfig()
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    return AppConfig(
        hdd_path=_optional_path(parser.get(_SECTION_ARCHIVE, "hdd_path", fallback="")),
        romm_user=parser.get(_SECTION_ROMM, "user", fallback=defaults.romm_user),
        romm_port=parser.getint(_SECTION_ROMM, "port", fallback=defaults.romm_port),
        max_parallel_jobs=parser.getint(
            _SECTION_JOBS, "max_parallel", fallback=defaults.max_parallel_jobs
        ),
        igir_input_dir=_optional_path(parser.get(_SECTION_IGIR, "input_dir", fallback="")),
        igir_dat_dir=_optional_path(parser.get(_SECTION_IGIR, "dat_dir", fallback="")),
    )


def save_config(path: Path, config: AppConfig) -> None:
    """Schreibt die Konfiguration in die INI-Datei (ohne Geheimnisse)."""
    parser = configparser.ConfigParser()
    parser[_SECTION_ARCHIVE] = {"hdd_path": _path_text(config.hdd_path)}
    parser[_SECTION_ROMM] = {"user": config.romm_user, "port": str(config.romm_port)}
    parser[_SECTION_JOBS] = {"max_parallel": str(config.max_parallel_jobs)}
    parser[_SECTION_IGIR] = {
        "input_dir": _path_text(config.igir_input_dir),
        "dat_dir": _path_text(config.igir_dat_dir),
    }
    with path.open("w", encoding="utf-8") as file:
        parser.write(file)
