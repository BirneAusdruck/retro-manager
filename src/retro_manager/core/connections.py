"""Gespeicherte Verbindungen zu Geräten (FTP/FTPS/SFTP); Passwörter liegen im Schlüsselbund."""

import configparser
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from retro_manager.core import remote

SECTION_PREFIX = "connection:"
KNOWN_HOSTS_FILENAME = "known_hosts"


@dataclass(frozen=True)
class Connection:
    id: str
    name: str
    protocol: str = "ftp"
    host: str = ""
    port: int = 21
    user: str = ""  # leer = anonym (nur FTP/FTPS)
    start_dir: str = "/"

    @property
    def secret_key(self) -> str:
        """Schlüssel des Passworts im Systemschlüsselbund."""
        return f"{SECTION_PREFIX}{self.id}"


def new_connection(name: str, protocol: str = "ftp", host: str = "") -> Connection:
    return Connection(
        id=uuid.uuid4().hex[:8],
        name=name,
        protocol=protocol,
        host=host,
        port=remote.DEFAULT_PORTS.get(protocol, 21),
    )


def known_hosts_path(base: Path) -> Path:
    """Gemerkte SSH-Host-Keys (SFTP) neben der App."""
    return base / KNOWN_HOSTS_FILENAME


def load_connections(path: Path) -> list[Connection]:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    connections = []
    for section in parser.sections():
        if not section.startswith(SECTION_PREFIX):
            continue
        values = parser[section]
        protocol = values.get("protocol", "ftp")
        if protocol not in remote.PROTOCOLS:
            continue
        connections.append(
            Connection(
                id=section.removeprefix(SECTION_PREFIX),
                name=values.get("name", "") or values.get("host", ""),
                protocol=protocol,
                host=values.get("host", ""),
                port=values.getint("port", fallback=remote.DEFAULT_PORTS[protocol]),
                user=values.get("user", ""),
                start_dir=values.get("start_dir", "/") or "/",
            )
        )
    return sorted(connections, key=lambda connection: connection.name.lower())


def save_connections(path: Path, connections: list[Connection]) -> None:
    """Ersetzt alle Verbindungsabschnitte, andere Abschnitte der INI bleiben erhalten."""
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    for section in [s for s in parser.sections() if s.startswith(SECTION_PREFIX)]:
        parser.remove_section(section)
    for connection in connections:
        parser[f"{SECTION_PREFIX}{connection.id}"] = {
            "name": connection.name,
            "protocol": connection.protocol,
            "host": connection.host,
            "port": str(connection.port),
            "user": connection.user,
            "start_dir": connection.start_dir,
        }
    with path.open("w", encoding="utf-8") as file:
        parser.write(file)


def migrate_ps3_target(connections: list[Connection], host: str, port: int) -> list[Connection]:
    """Übernimmt die frühere PS3-Adresse einmalig als Verbindung „PS3“."""
    if not host or any(c.host == host and c.port == port for c in connections):
        return connections
    ps3 = replace(new_connection("PS3", "ftp", host), port=port, start_dir="/dev_hdd0")
    return [*connections, ps3]
