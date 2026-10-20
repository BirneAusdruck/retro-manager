"""Tests für retro_manager.core.devices."""

from pathlib import Path, PurePosixPath

from retro_manager.core import devices
from retro_manager.core.library import LibraryGame

PS3 = devices.PS3_WEBMAN


def game(slug, name="Spiel (USA)", game_dir=""):
    return LibraryGame(slug, name, Path(f"/roms/{slug}/{name}.chd"), "chd", 1, game_dir)


def test_target_dir_ps1_gets_folder_per_game(tmp_path):
    assert devices.target_dir(tmp_path, PS3, game("psx")) == tmp_path / "PSXISO" / "Spiel (USA)"
    multi = game("psx", "FF8 (Disc 1)", "Final Fantasy VIII")
    assert devices.target_dir(tmp_path, PS3, multi) == tmp_path / "PSXISO" / "Final Fantasy VIII"


def test_target_dir_iso_platforms(tmp_path):
    assert devices.target_dir(tmp_path, PS3, game("ps2")) == tmp_path / "PS2ISO"
    assert devices.target_dir(tmp_path, PS3, game("psp")) == tmp_path / "PSPISO"
    assert devices.target_dir(tmp_path, PS3, game("ps3")) == tmp_path / "PS3ISO"


def test_remote_path(tmp_path):
    local = tmp_path / "PSXISO" / "Spiel" / "Spiel.cue"
    assert devices.remote_path(tmp_path, PS3, local) == PurePosixPath(
        "/dev_hdd0/PSXISO/Spiel/Spiel.cue"
    )


def test_export_root_per_profile(tmp_path):
    assert devices.export_root(tmp_path, PS3) == tmp_path / "ps3"


def test_get_profile_falls_back_for_unknown_or_unavailable():
    assert devices.get_profile("ps3") is PS3
    assert devices.get_profile("xbox360") is devices.DEFAULT_PROFILE  # noch nicht verfügbar
    assert devices.get_profile("gibts-nicht") is devices.DEFAULT_PROFILE


def test_future_profiles_are_listed_but_unavailable():
    labels = {p.id: p.available for p in devices.PROFILES}
    assert labels == {"ps3": True, "ps2-opl": False, "xbox360": False}
