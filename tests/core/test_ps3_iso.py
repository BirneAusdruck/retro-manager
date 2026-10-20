"""Tests für retro_manager.core.ps3_iso mit einer selbst verschlüsselten Test-ISO."""

import os
import struct

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from retro_manager.core import ps3_iso
from retro_manager.core.export import ExportCancelled, ExportError

S = ps3_iso.SECTOR_SIZE
KEY = bytes(range(16))


def region_table(plain_regions):
    table = struct.pack(">II", len(plain_regions), 0)
    for start, end in plain_regions:
        table += struct.pack(">II", start, end)
    return table.ljust(S, b"\0")


def encrypt_sector(sector_no, data):
    iv = bytes(12) + struct.pack(">I", sector_no)
    encryptor = Cipher(algorithms.AES(KEY), modes.CBC(iv)).encryptor()
    return encryptor.update(data) + encryptor.finalize()


def make_iso(tmp_path, sectors=1500):
    """Unverschlüsselt: 0–1 und 1200–1499; verschlüsselt: 2–1199 (über Blockgrenzen hinweg)."""
    plain_regions = [(0, 1), (1200, sectors - 1)]
    clear = [region_table(plain_regions)] + [os.urandom(S) for _ in range(sectors - 1)]
    clear[700] = bytes(S)  # Null-Sektor im verschlüsselten Bereich bleibt unverändert
    encrypted = [
        encrypt_sector(n, data) if 2 <= n < 1200 and data != bytes(S) else data
        for n, data in enumerate(clear)
    ]
    iso = tmp_path / "Spiel (Europe).iso"
    iso.write_bytes(b"".join(encrypted))
    return iso, b"".join(clear)


def test_parse_encrypted_regions():
    assert ps3_iso.parse_encrypted_regions(region_table([(0, 1), (10, 19), (50, 99)])) == [
        (2, 10),
        (20, 50),
    ]


@pytest.mark.parametrize("sector0", [bytes(S), region_table([(10, 5)]), b"kurz"])
def test_parse_invalid_tables(sector0):
    with pytest.raises(ExportError):
        ps3_iso.parse_encrypted_regions(sector0)


def test_decrypt_sectors_matches_cbc():
    data = os.urandom(3 * S)
    encrypted = b"".join(encrypt_sector(40 + i, data[i * S : (i + 1) * S]) for i in range(3))
    assert ps3_iso.decrypt_sectors(KEY, 40, encrypted) == data


def test_decrypt_iso_roundtrip(tmp_path):
    iso, clear = make_iso(tmp_path)
    target = tmp_path / "out" / iso.name
    seen = []
    ps3_iso.decrypt_iso(iso, target, KEY, lambda d, t: seen.append((d, t)), lambda: False)
    assert target.read_bytes() == clear
    assert seen[-1] == (len(clear), len(clear))


def test_decrypt_iso_cancel(tmp_path):
    iso, _ = make_iso(tmp_path)
    with pytest.raises(ExportCancelled):
        ps3_iso.decrypt_iso(iso, tmp_path / "x.iso", KEY, lambda d, t: None, lambda: True)


def test_decrypt_rejects_odd_size(tmp_path):
    bad = tmp_path / "x.iso"
    bad.write_bytes(b"x" * 3000)
    with pytest.raises(ExportError):
        ps3_iso.decrypt_iso(bad, tmp_path / "y.iso", KEY, lambda d, t: None, lambda: False)


def test_read_key_binary_and_hex(tmp_path):
    binary = tmp_path / "a.key"
    binary.write_bytes(KEY)
    text = tmp_path / "b.dkey"
    text.write_text(KEY.hex().upper() + "\n")
    assert ps3_iso.read_key(binary) == KEY
    assert ps3_iso.read_key(text) == KEY
    broken = tmp_path / "c.key"
    broken.write_text("zu kurz")
    with pytest.raises(ExportError):
        ps3_iso.read_key(broken)


def test_find_key_by_name(tmp_path):
    (tmp_path / "Spiel (Europe).key").write_bytes(KEY)
    assert (
        ps3_iso.find_key(tmp_path, tmp_path / "x" / "Spiel (Europe).iso")
        == tmp_path / "Spiel (Europe).key"
    )
    assert ps3_iso.find_key(tmp_path, tmp_path / "Anderes.iso") is None
    assert ps3_iso.find_key(None, tmp_path / "Spiel (Europe).iso") is None
