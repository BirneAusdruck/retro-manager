"""Tests für retro_manager.core.remote gegen lokale FTP-, FTPS- und SFTP-Server."""

import asyncio
import datetime as dt
import threading
from datetime import datetime
from pathlib import PurePosixPath

import asyncssh
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler, TLS_FTPHandler
from pyftpdlib.ioloop import IOLoop
from pyftpdlib.servers import FTPServer

from retro_manager.core import remote
from retro_manager.core.progress import ExportCancelled

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")

USER, PASSWORD = "deck", "geheim"


# --- LIST-Parser ------------------------------------------------------------------------------

NOW = datetime(2026, 10, 19, 12, 0)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            "drwxr-xr-x  2 root root     4096 Jan 05 2025 PS3ISO",
            ("PS3ISO", True, 4096, datetime(2025, 1, 5)),
        ),
        (
            "-rw-r--r--  1 0 0  736651104 Oct 19 10:15 Spiel (USA).bin",
            ("Spiel (USA).bin", False, 736651104, datetime(2026, 10, 19, 10, 15)),
        ),
        (
            "-rw-r--r--  1 u g 10 Dec 31 23:59 alt.txt",
            ("alt.txt", False, 10, datetime(2025, 12, 31, 23, 59)),
        ),  # Vorjahr
        ("lrwxrwxrwx  1 u g 7 Jan 01 2020 link -> ziel", ("link", False, 7, datetime(2020, 1, 1))),
        (
            "10-19-26  03:56PM       <DIR>          Spiele",
            ("Spiele", True, 0, datetime(2026, 10, 19, 15, 56)),
        ),
        (
            "10-19-26  03:56PM            1234 a.iso",
            ("a.iso", False, 1234, datetime(2026, 10, 19, 15, 56)),
        ),
    ],
)
def test_parse_list_line(line, expected):
    entry = remote.parse_list_line(line, NOW)
    assert (entry.name, entry.is_dir, entry.size, entry.modified) == expected


@pytest.mark.parametrize("line", ["total 12", "", "Unsinn ohne Format"])
def test_parse_list_line_ignores_other_lines(line):
    assert remote.parse_list_line(line, NOW) is None


# --- Testserver -------------------------------------------------------------------------------


def _self_signed_cert(path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(
        cert.public_bytes(serialization.Encoding.PEM)
        + key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


def _ftp_server(root, tls, tmp_path):
    authorizer = DummyAuthorizer()
    authorizer.add_user(USER, PASSWORD, str(root), perm="elradfmwMT")
    attrs = {"authorizer": authorizer}
    base = FTPHandler
    if tls:
        cert = tmp_path / "cert.pem"
        _self_signed_cert(cert)
        base = TLS_FTPHandler
        attrs.update(certfile=str(cert), tls_control_required=True, tls_data_required=True)
    server = FTPServer(("127.0.0.1", 0), type("H", (base,), attrs), ioloop=IOLoop())
    threading.Thread(target=server.serve_forever, kwargs={"timeout": 0.1}, daemon=True).start()
    return server, server.address[1]


class _PasswordServer(asyncssh.SSHServer):
    def begin_auth(self, username):
        return True

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        return username == USER and password == PASSWORD


def _sftp_server(root):
    loop = asyncio.new_event_loop()
    key = asyncssh.generate_private_key("ssh-ed25519")
    started = threading.Event()
    holder = {}

    async def start():
        holder["server"] = await asyncssh.listen(
            "127.0.0.1",
            0,
            server_factory=_PasswordServer,
            server_host_keys=[key],
            sftp_factory=lambda chan: asyncssh.SFTPServer(chan, chroot=str(root)),
        )
        started.set()

    threading.Thread(
        target=lambda: (loop.run_until_complete(start()), loop.run_forever()), daemon=True
    ).start()
    started.wait(10)
    port = holder["server"].sockets[0].getsockname()[1]
    return loop, holder["server"], port


@pytest.fixture(params=["ftp", "ftps", "sftp"])
def fs(request, tmp_path):
    root = tmp_path / "geraet"
    root.mkdir()
    known_hosts = tmp_path / "known_hosts"
    if request.param == "sftp":
        loop, server, port = _sftp_server(root)
        connection = remote.open_remote("sftp", "127.0.0.1", port, USER, PASSWORD, known_hosts)
        yield connection, root, PurePosixPath("/")
        connection.close()
        loop.call_soon_threadsafe(server.close)
        loop.call_soon_threadsafe(loop.stop)
    else:
        server, port = _ftp_server(root, request.param == "ftps", tmp_path)
        connection = remote.open_remote(
            request.param, "127.0.0.1", port, USER, PASSWORD, known_hosts
        )
        yield connection, root, PurePosixPath("/")
        connection.close()
        server.close_all()


def never():
    return False


# --- Dateioperationen -------------------------------------------------------------------------


def test_list_mkdir_rename_remove(fs):
    connection, root, top = fs
    assert connection.welcome()
    (root / "a.bin").write_bytes(b"x" * 10)
    connection.mkdir(top / "PS3ISO")
    entries = {e.name: e for e in connection.list_dir(top)}
    assert entries["PS3ISO"].is_dir and not entries["a.bin"].is_dir and entries["a.bin"].size == 10
    connection.rename(top / "a.bin", top / "PS3ISO" / "b.bin")
    assert (root / "PS3ISO" / "b.bin").exists()
    assert connection.size(top / "PS3ISO" / "b.bin") == 10
    assert connection.size(top / "fehlt.bin") is None
    remote.remove_tree(connection, top / "PS3ISO")
    assert not (root / "PS3ISO").exists()


def test_upload_items_creates_dirs_resumes_and_skips(fs, tmp_path):
    connection, root, top = fs
    local = tmp_path / "lokal"
    (local / "Spiel").mkdir(parents=True)
    data = bytes(range(256)) * 12_000
    (local / "Spiel" / "s.bin").write_bytes(data)
    (local / "Spiel" / "s.cue").write_bytes(b"FILE")
    items = remote.expand_upload([local / "Spiel"], top / "dev_hdd0" / "PSXISO")
    assert sorted(i.remote.as_posix() for i in items) == [
        "/dev_hdd0/PSXISO/Spiel/s.bin",
        "/dev_hdd0/PSXISO/Spiel/s.cue",
    ]
    target = root / "dev_hdd0" / "PSXISO" / "Spiel" / "s.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(data[:1_000_000])  # abgebrochene Übertragung
    seen, done_files = [], []
    remote.upload_items(connection, items, lambda d, t: seen.append(d), never, done_files.append)
    assert target.read_bytes() == data
    assert seen[0] == 1_000_000 and seen[-1] == len(data) + 4
    assert len(done_files) == 2
    remote.upload_items(connection, items, lambda d, t: None, never)  # zweiter Lauf: nichts zu tun


def test_download_items_recursive_with_resume(fs, tmp_path):
    connection, root, top = fs
    (root / "Ordner" / "Unter").mkdir(parents=True)
    data = b"y" * 3_000_000
    (root / "Ordner" / "Unter" / "groß.iso").write_bytes(data)
    (root / "Ordner" / "klein.txt").write_bytes(b"hi")
    local = tmp_path / "ziel"
    items = remote.expand_download(connection, [(top / "Ordner", True)], local)
    assert sorted((i.local.relative_to(local).as_posix(), size) for i, size in items) == [
        ("Ordner/Unter/groß.iso", 3_000_000),
        ("Ordner/klein.txt", 2),
    ]
    (local / "Ordner" / "Unter").mkdir(parents=True)
    (local / "Ordner" / "Unter" / "groß.iso").write_bytes(data[:500_000])
    seen = []
    remote.download_items(connection, items, lambda d, t: seen.append(d), never)
    assert (local / "Ordner" / "Unter" / "groß.iso").read_bytes() == data
    assert seen[0] in (0, 500_000)


def test_upload_cancel(fs, tmp_path):
    connection, _, top = fs
    file = tmp_path / "g.iso"
    file.write_bytes(b"x" * 5_000_000)
    with pytest.raises(ExportCancelled):
        remote.upload_items(
            connection, [remote.TransferItem(file, top / "g.iso")], lambda d, t: None, lambda: True
        )


def test_wrong_password(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    server, port = _ftp_server(root, False, tmp_path)
    try:
        with pytest.raises(remote.RemoteError):
            remote.open_remote("ftp", "127.0.0.1", port, USER, "falsch", tmp_path / "kh")
    finally:
        server.close_all()


def test_sftp_changed_host_key_is_rejected(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    known_hosts = tmp_path / "known_hosts"
    loop, server, port = _sftp_server(root)
    remote.open_remote("sftp", "127.0.0.1", port, USER, PASSWORD, known_hosts).close()
    loop.call_soon_threadsafe(server.close)
    assert known_hosts.read_text()
    loop2, server2, port2 = _sftp_server(root)  # neuer Server, neuer Schlüssel
    known_hosts.write_text(
        known_hosts.read_text().replace(f"[127.0.0.1]:{port}", f"[127.0.0.1]:{port2}")
    )
    with pytest.raises(remote.RemoteError, match="geändert"):
        remote.open_remote("sftp", "127.0.0.1", port2, USER, PASSWORD, known_hosts)
    loop2.call_soon_threadsafe(server2.close)


def test_unknown_protocol(tmp_path):
    with pytest.raises(remote.RemoteError):
        remote.open_remote("gopher", "h", 1, "", "", tmp_path)
