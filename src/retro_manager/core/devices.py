"""Zielgeräte für Exporte: unterstützte Plattformen, Ordner im Ziel und Pfade auf dem Gerät."""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from retro_manager.core.library import LibraryGame

PLATFORM_LABELS = {"psx": "PS1", "ps2": "PS2", "ps3": "PS3", "psp": "PSP", "xbox360": "Xbox 360"}


@dataclass(frozen=True)
class DeviceProfile:
    """Beschreibt ein Zielgerät; `available=False` heißt: noch nicht umgesetzt."""

    id: str
    label: str
    available: bool
    platforms: dict[str, str] = field(default_factory=dict)  # RomM-Slug -> Ordner im Ziel
    remote_root: PurePosixPath = PurePosixPath("/")
    folder_per_game: frozenset[str] = frozenset()  # Plattformen mit einem Ordner je Spiel
    decrypts_ps3: bool = False  # PS3-ISOs mit Redump-Key entschlüsseln
    default_protocol: str = "ftp"
    default_port: int = 21


PS3_WEBMAN = DeviceProfile(
    id="ps3",
    label="PS3 (CFW + webMAN MOD)",
    available=True,
    platforms={"psx": "PSXISO", "ps2": "PS2ISO", "ps3": "PS3ISO", "psp": "PSPISO"},
    remote_root=PurePosixPath("/dev_hdd0"),
    # PS1-Spiele bestehen aus CUE + BIN(s).
    folder_per_game=frozenset({"psx"}),
    decrypts_ps3=True,
)
PS2_OPL = DeviceProfile(id="ps2-opl", label="PS2 (Open PS2 Loader)", available=False)
XBOX360 = DeviceProfile(id="xbox360", label="Xbox 360", available=False)

PROFILES: tuple[DeviceProfile, ...] = (PS3_WEBMAN, PS2_OPL, XBOX360)
DEFAULT_PROFILE = PS3_WEBMAN


def get_profile(profile_id: str) -> DeviceProfile:
    """Profil zu einer ID; unbekannte oder nicht verfügbare IDs ergeben das Standardprofil."""
    for profile in PROFILES:
        if profile.id == profile_id and profile.available:
            return profile
    return DEFAULT_PROFILE


def export_root(exports_dir: Path, profile: DeviceProfile) -> Path:
    return exports_dir / profile.id


def target_dir(root: Path, profile: DeviceProfile, game: LibraryGame) -> Path:
    """Ordner im Export, in den die Dateien dieser Disc kommen."""
    base = root / profile.platforms[game.slug]
    if game.slug in profile.folder_per_game:
        return base / (game.game_dir or game.name)
    return base


def remote_path(root: Path, profile: DeviceProfile, local_file: Path) -> PurePosixPath:
    """Pfad auf dem Gerät, z. B. `/dev_hdd0/PSXISO/Spiel/Spiel.cue`."""
    return profile.remote_root / PurePosixPath(local_file.relative_to(root).as_posix())
