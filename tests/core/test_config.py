"""Tests für retro_manager.core.config."""

import sys
from pathlib import Path

from retro_manager.core import config
from retro_manager.core.config import AppConfig


def test_default_config_is_incomplete():
    assert not AppConfig().is_complete


def test_config_without_user_is_incomplete():
    assert not AppConfig(hdd_path=Path("/mnt/archiv")).is_complete


def test_config_with_path_and_user_is_complete():
    assert AppConfig(hdd_path=Path("/mnt/archiv"), romm_user="admin").is_complete


def test_ini_path_is_inside_base(tmp_path):
    assert config.ini_path(tmp_path) == tmp_path / "retro-manager.ini"


def test_compose_dir_is_inside_base(tmp_path):
    assert config.compose_dir(tmp_path) == tmp_path / "docker"


def test_app_dir_in_development_is_project_root():
    assert (config.app_dir() / "pyproject.toml").is_file()


def test_app_dir_when_frozen_is_executable_dir(tmp_path, monkeypatch):
    executable = tmp_path / "retro-manager"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert config.app_dir() == tmp_path


def test_webdata_dir_is_inside_base(tmp_path):
    assert config.webdata_dir(tmp_path) == tmp_path / "webdata"


def test_load_missing_file_gives_defaults(tmp_path):
    assert config.load_config(tmp_path / "fehlt.ini") == AppConfig()


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "retro-manager.ini"
    original = AppConfig(
        hdd_path=Path("/mnt/archiv"),
        romm_user="admin",
        romm_port=9000,
        max_parallel_jobs=4,
        igir_input_dir=Path("/mnt/archiv/neu"),
        igir_dat_dir=Path("/mnt/archiv/dats"),
    )
    config.save_config(path, original)
    assert config.load_config(path) == original


def test_saved_ini_contains_no_password_section(tmp_path):
    path = tmp_path / "retro-manager.ini"
    config.save_config(path, AppConfig(romm_user="admin"))
    assert "password" not in path.read_text().lower()


def test_is_dev_build_from_source():
    assert config.is_dev_build()


def test_is_not_dev_build_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert not config.is_dev_build()


def test_tools_and_reports_dir_are_inside_base(tmp_path):
    assert config.tools_dir(tmp_path) == tmp_path / "tools"
    assert config.reports_dir(tmp_path) == tmp_path / "reports"


def test_dats_dir_is_on_hdd(tmp_path):
    assert config.dats_dir(tmp_path) == tmp_path / "dats"
