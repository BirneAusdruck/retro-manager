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
EXPORTS_DIRNAME = "exports"
# Arbeitsordner für Zwischenstände (Entpacken, halbfertige CHDs); von RomM ignoriert.
WORK_DIRNAME = ".retro-manager-tmp"

_SECTION_ARCHIVE = "archive"
_SECTION_ROMM = "romm"
_SECTION_JOBS = "jobs"
_SECTION_IGIR = "igir"
_SECTION_PS3 = "ps3"
_SECTION_EXPORT = "export"
_SECTION_CHDMAN = "chdman"
_SECTION_ARCHIVES = "archives"


@dataclass
class AppConfig:
    """Nicht geheime Einstellungen aus der INI-Datei."""

    hdd_path: Path | None = None
    romm_user: str = ""
    romm_port: int = 8080
    max_parallel_jobs: int = 2
    igir_input_dir: Path | None = None
    igir_dat_dir: Path | None = None
    ps3_host: str = ""
    ps3_port: int = 21
    export_device: str = "ps3"
    export_connection: str = ""
    # Originale nach erfolgreich geprüfter CHD-Umwandlung löschen.
    chd_delete_originals: bool = True
    # Reiter „Archive“: Packformat (7z/zip), Stufe (fast/normal/max), Originale löschen.
    archive_format: str = "zip"
    archive_level: str = "normal"
    archive_delete_originals: bool = False

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


def exports_dir(hdd_path: Path) -> Path:
    """Ordner für aufbereitete Spiele für echte Hardware (neben roms/, von RomM ignoriert)."""
    return hdd_path / EXPORTS_DIRNAME


def work_dir(hdd_path: Path) -> Path:
    """Arbeitsordner auf der Archiv-HDD; gleiches Laufwerk, damit fertige Dateien nur umbenannt
    werden müssen."""
    return hdd_path / WORK_DIRNAME


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
        ps3_host=parser.get(_SECTION_PS3, "host", fallback=defaults.ps3_host),
        ps3_port=parser.getint(_SECTION_PS3, "port", fallback=defaults.ps3_port),
        export_device=parser.get(_SECTION_EXPORT, "device", fallback=defaults.export_device),
        export_connection=parser.get(_SECTION_EXPORT, "connection", fallback=""),
        chd_delete_originals=parser.getboolean(
            _SECTION_CHDMAN, "delete_originals", fallback=defaults.chd_delete_originals
        ),
        archive_format=parser.get(_SECTION_ARCHIVES, "format", fallback=defaults.archive_format),
        archive_level=parser.get(_SECTION_ARCHIVES, "level", fallback=defaults.archive_level),
        archive_delete_originals=parser.getboolean(
            _SECTION_ARCHIVES, "delete_originals", fallback=defaults.archive_delete_originals
        ),
    )


def save_config(path: Path, config: AppConfig) -> None:
    """Schreibt die Konfiguration in die INI-Datei (ohne Geheimnisse).

    Andere Abschnitte (z. B. gespeicherte Verbindungen) bleiben erhalten.
    """
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    parser[_SECTION_ARCHIVE] = {"hdd_path": _path_text(config.hdd_path)}
    parser[_SECTION_ROMM] = {"user": config.romm_user, "port": str(config.romm_port)}
    parser[_SECTION_JOBS] = {"max_parallel": str(config.max_parallel_jobs)}
    parser[_SECTION_IGIR] = {
        "input_dir": _path_text(config.igir_input_dir),
        "dat_dir": _path_text(config.igir_dat_dir),
    }
    parser[_SECTION_PS3] = {"host": config.ps3_host, "port": str(config.ps3_port)}
    parser[_SECTION_EXPORT] = {
        "device": config.export_device,
        "connection": config.export_connection,
    }
    parser[_SECTION_CHDMAN] = {"delete_originals": str(config.chd_delete_originals).lower()}
    parser[_SECTION_ARCHIVES] = {
        "format": config.archive_format,
        "level": config.archive_level,
        "delete_originals": str(config.archive_delete_originals).lower(),
    }
    with path.open("w", encoding="utf-8") as file:
        parser.write(file)
