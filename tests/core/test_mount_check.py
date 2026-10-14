"""Tests für retro_manager.core.mount_check (Mounts gemockt)."""

from pathlib import Path

from retro_manager.core import mount_check


def fake_mounts(monkeypatch, mounts: set[Path]) -> None:
    monkeypatch.setattr(mount_check.os.path, "ismount", lambda p: Path(p) in mounts)


def test_mount_point_walks_up_to_mount(tmp_path, monkeypatch):
    folder = tmp_path / "roms" / "ps2"
    folder.mkdir(parents=True)
    fake_mounts(monkeypatch, {Path("/"), tmp_path.resolve()})
    assert mount_check.mount_point(folder) == tmp_path.resolve()


def test_folder_on_mounted_drive(tmp_path, monkeypatch):
    fake_mounts(monkeypatch, {Path("/"), tmp_path.resolve()})
    assert mount_check.is_on_mounted_drive(tmp_path)


def test_empty_mount_folder_on_root_is_rejected(tmp_path, monkeypatch):
    fake_mounts(monkeypatch, {Path("/")})
    assert not mount_check.is_on_mounted_drive(tmp_path)


def test_missing_folder_is_rejected(tmp_path, monkeypatch):
    fake_mounts(monkeypatch, {Path("/"), tmp_path.resolve()})
    assert not mount_check.is_on_mounted_drive(tmp_path / "fehlt")
