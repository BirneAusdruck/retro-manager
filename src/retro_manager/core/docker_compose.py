""".env schreiben, compose-Befehle als Argumentlisten bauen."""

import os
import secrets
import shutil
from pathlib import Path

COMPOSE_FILENAME = "docker-compose.yml"
ENV_FILENAME = ".env"


def docker_executable() -> str | None:
    """Pfad zum docker-Programm oder None, wenn Docker nicht installiert ist."""
    return shutil.which("docker")


def generate_secret() -> str:
    """Erzeugt ein zufälliges Geheimnis (64 Hex-Zeichen)."""
    return secrets.token_hex(32)


def env_values(
    library_path: Path,
    port: int,
    db_password: str,
    db_root_password: str,
    auth_secret_key: str,
) -> dict[str, str]:
    """Variablen für docker/.env."""
    return {
        "ROMM_LIBRARY_PATH": str(library_path),
        "ROMM_PORT": str(port),
        "DB_PASSWORD": db_password,
        "DB_ROOT_PASSWORD": db_root_password,
        "ROMM_AUTH_SECRET_KEY": auth_secret_key,
    }


def render_env(values: dict[str, str]) -> str:
    """Formatiert Variablen als .env-Inhalt; Werte in Anführungszeichen."""
    lines = []
    for key, value in values.items():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')
    return "\n".join(lines) + "\n"


def write_env(path: Path, values: dict[str, str]) -> None:
    """Schreibt die .env-Datei, nur für den Besitzer lesbar."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(render_env(values))
    os.chmod(path, 0o600)


def docker_info_args() -> list[str]:
    """Argumente, um zu prüfen, ob der Docker-Dienst läuft und erreichbar ist."""
    return ["info", "--format", "{{.ServerVersion}}"]


def compose_args(compose_dir: Path, *args: str) -> list[str]:
    """Argumente für `docker compose` mit festem Projektordner."""
    return [
        "compose",
        "--project-directory",
        str(compose_dir),
        "-f",
        str(compose_dir / COMPOSE_FILENAME),
        *args,
    ]


def up_args(compose_dir: Path) -> list[str]:
    return compose_args(compose_dir, "up", "-d")


def stop_args(compose_dir: Path) -> list[str]:
    # `stop` statt `down`: Container und Netzwerke bleiben erhalten, Start geht schneller.
    return compose_args(compose_dir, "stop")
