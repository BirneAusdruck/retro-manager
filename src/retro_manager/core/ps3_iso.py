"""PS3-Disc-Abbilder (Redump) mit dem Disc-Key entschlüsseln – wie PS3Dec.

Aufbau: Sektor 0 enthält eine Tabelle der *unverschlüsselten* Regionen (Big Endian:
Anzahl als u32 bei Byte 0, ab Byte 8 je 8 Byte Start- und Endsektor, Ende inklusive).
Die Lücken dazwischen sind verschlüsselt: jeder 2048-Byte-Sektor einzeln mit
AES-128-CBC, Schlüssel = Disc-Key, IV = 12 Nullbytes + Sektornummer (u32 BE).
Sektoren, die nur aus Nullbytes bestehen, sind nicht verschlüsselt.
"""

import struct
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from retro_manager.core.progress import CancelCheck, ExportCancelled, ExportError, ProgressCallback

SECTOR_SIZE = 2048
KEY_SIZE = 16
_SECTORS_PER_CHUNK = 512  # 1 MiB je Lese-/Schreibvorgang
_ZERO_SECTOR = bytes(SECTOR_SIZE)
_MAX_REGIONS = (SECTOR_SIZE - 8) // 8


def parse_encrypted_regions(sector0: bytes) -> list[tuple[int, int]]:
    """Verschlüsselte Bereiche als (erster Sektor, Ende exklusiv)."""
    if len(sector0) < SECTOR_SIZE:
        raise ExportError("Das Abbild ist zu kurz für eine PS3-Disc.")
    count = struct.unpack(">I", sector0[:4])[0]
    if count == 0 or count > _MAX_REGIONS:
        raise ExportError("Keine gültige PS3-Regionstabelle (ist das eine PS3-ISO?).")
    plain = []
    for index in range(count):
        start, end = struct.unpack(">II", sector0[8 + index * 8 : 16 + index * 8])
        if end < start or (plain and start < plain[-1][1]):
            raise ExportError("PS3-Regionstabelle ist beschädigt.")
        plain.append((start, end + 1))
    return [(previous[1], current[0]) for previous, current in zip(plain, plain[1:], strict=False)]


def read_key(path: Path) -> bytes:
    """Disc-Key aus einer Redump-`.key` (16 Byte) oder einer Text-Datei mit 32 Hex-Zeichen."""
    data = path.read_bytes()
    if len(data) == KEY_SIZE:
        return data
    try:
        key = bytes.fromhex(data.decode("ascii").strip())
    except (UnicodeDecodeError, ValueError) as error:
        raise ExportError(f"Ungültiger Disc-Key: {path.name}") from error
    if len(key) != KEY_SIZE:
        raise ExportError(f"Ungültiger Disc-Key: {path.name}")
    return key


def find_key(keys_dir: Path | None, iso: Path) -> Path | None:
    """Passender Redump-Key über den Spielnamen (Dateiname wie bei Redump/Igir)."""
    if keys_dir is None:
        return None
    for suffix in (".key", ".dkey"):
        candidate = keys_dir / f"{iso.stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def decrypt_sectors(key: bytes, first_sector: int, data: bytes) -> bytes:
    """Entschlüsselt zusammenhängende Sektoren (CBC je Sektor, IV = Sektornummer)."""
    count = len(data) // SECTOR_SIZE
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    raw = decryptor.update(data) + decryptor.finalize()
    # CBC: Klartext = AES⁻¹(C_i) XOR C_(i-1); vor dem ersten Block eines Sektors steht der IV.
    chain = bytearray(len(data))
    for index in range(count):
        offset = index * SECTOR_SIZE
        chain[offset + 12 : offset + 16] = struct.pack(">I", first_sector + index)
        chain[offset + 16 : offset + SECTOR_SIZE] = data[offset : offset + SECTOR_SIZE - 16]
    plain = (int.from_bytes(raw, "big") ^ int.from_bytes(chain, "big")).to_bytes(len(data), "big")
    # Reine Null-Sektoren waren nie verschlüsselt.
    result = bytearray(plain)
    for index in range(count):
        offset = index * SECTOR_SIZE
        if data[offset : offset + SECTOR_SIZE] == _ZERO_SECTOR:
            result[offset : offset + SECTOR_SIZE] = _ZERO_SECTOR
    return bytes(result)


def decrypt_iso(
    source: Path,
    target: Path,
    key: bytes,
    on_progress: ProgressCallback,
    is_cancelled: CancelCheck,
) -> None:
    """Schreibt eine entschlüsselte Kopie von `source` nach `target`."""
    total = source.stat().st_size
    if total % SECTOR_SIZE:
        raise ExportError("Die Größe ist kein Vielfaches von 2048 Byte – keine PS3-ISO.")
    with source.open("rb") as src:
        regions = parse_encrypted_regions(src.read(SECTOR_SIZE))
        src.seek(0)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as dst:
            sector = 0
            while chunk := src.read(_SECTORS_PER_CHUNK * SECTOR_SIZE):
                if is_cancelled():
                    raise ExportCancelled
                dst.write(_decrypt_chunk(key, sector, chunk, regions))
                sector += len(chunk) // SECTOR_SIZE
                on_progress(sector * SECTOR_SIZE, total)


def _decrypt_chunk(key: bytes, first: int, chunk: bytes, regions: list[tuple[int, int]]) -> bytes:
    last = first + len(chunk) // SECTOR_SIZE
    out = bytearray(chunk)
    for start, end in regions:
        lo, hi = max(start, first), min(end, last)
        if lo >= hi:
            continue
        begin, finish = (lo - first) * SECTOR_SIZE, (hi - first) * SECTOR_SIZE
        out[begin:finish] = decrypt_sectors(key, lo, chunk[begin:finish])
    return bytes(out)
