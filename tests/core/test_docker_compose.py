"""Tests für retro_manager.core.docker_compose."""

import stat
from pathlib import Path

from retro_manager.core import docker_compose


def test_docker_executable_uses_path_lookup(monkeypatch):
    monkeypatch.setattr(docker_compose.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert docker_compose.docker_executable() == "/usr/bin/docker"


def test_docker_executable_missing(monkeypatch):
    monkeypatch.setattr(docker_compose.shutil, "which", lambda name: None)
    assert docker_compose.docker_executable() is None


def test_generate_secret_is_random_hex():
    first, second = docker_compose.generate_secret(), docker_compose.generate_secret()
    assert first != second
    assert len(first) == 64
    int(first, 16)


def test_env_values():
    values = docker_compose.env_values(Path("/mnt/archiv"), 8080, "db", "root", "key")
    assert values == {
        "ROMM_LIBRARY_PATH": "/mnt/archiv",
        "ROMM_PORT": "8080",
        "DB_PASSWORD": "db",
        "DB_ROOT_PASSWORD": "root",
        "ROMM_AUTH_SECRET_KEY": "key",
    }


def test_render_env_quotes_and_escapes():
    assert docker_compose.render_env({"A": 'x"y', "B": "/pfad mit leer"}) == (
        'A="x\\"y"\nB="/pfad mit leer"\n'
    )


def test_write_env_is_private(tmp_path):
    path = tmp_path / ".env"
    docker_compose.write_env(path, {"A": "1"})
    assert path.read_text() == 'A="1"\n'
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_up_and_stop_args(tmp_path):
    prefix = ["compose", "--project-directory", str(tmp_path), "-f"]
    compose_file = str(tmp_path / "docker-compose.yml")
    assert docker_compose.up_args(tmp_path) == [*prefix, compose_file, "up", "-d"]
    assert docker_compose.stop_args(tmp_path) == [*prefix, compose_file, "stop"]


def test_docker_info_args():
    assert docker_compose.docker_info_args()[0] == "info"
