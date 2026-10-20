"""Tests für retro_manager.core.chd."""

import shutil
import struct
import subprocess

import pytest

from retro_manager.core import chd
from retro_manager.core.library import LibraryGame


def touch(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def game(path, slug="psx", kind=None, game_dir=""):
    kind = kind or {".7z": "archive", ".zip": "archive"}.get(path.suffix, path.suffix[1:])
    return LibraryGame(slug, path.stem, path, kind, path.stat().st_size, game_dir)


def fake_chd(path, tags, logical_size=1000, version=5):
    """CHD-v5-Kopf mit einer Kette von Metadaten-Einträgen."""
    meta_start = 124
    header = bytearray(meta_start)
    header[:8] = b"MComprHD"
    header[12:16] = struct.pack(">I", version)
    header[32:40] = struct.pack(">Q", logical_size)
    header[48:56] = struct.pack(">Q", meta_start if tags else 0)
    body = bytearray()
    for index, tag in enumerate(tags):
        payload = b"TRACK:1"
        offset = meta_start + len(body)
        following = offset + 16 + len(payload) if index < len(tags) - 1 else 0
        body += tag + b"\0" + len(payload).to_bytes(3, "big") + struct.pack(">Q", following)
        body += payload
    path.write_bytes(bytes(header) + bytes(body))
    return path


# --- Medienart und Quellen ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slug", "name", "media"),
    [
        ("ps2", "Spiel.iso", "dvd"),
        ("psp", "Spiel.ISO", "dvd"),
        ("ps2", "Spiel.cue", "cd"),  # PS2-Spiele auf CD
        ("psx", "Spiel.iso", "cd"),
        ("dc", "Spiel.gdi", "cd"),
    ],
)
def test_media_for_image(tmp_path, slug, name, media):
    assert chd.media_for_image(slug, tmp_path / name) == media


def test_gdi_files_quoted_and_plain(tmp_path):
    for name in ("track01.bin", "track 02.raw", "track03.bin"):
        touch(tmp_path / name)
    gdi = tmp_path / "Spiel.gdi"
    gdi.write_text(
        '3\n1 0 4 2352 track01.bin 0\n2 600 0 2352 "track 02.raw" 0\n'
        "3 45000 4 2352 track03.bin 0\n4 50000 4 2352 fehlt.bin 0\n"
    )
    assert [p.name for p in chd.gdi_files(gdi)] == ["track01.bin", "track 02.raw", "track03.bin"]


def test_source_files_cue_with_bins(tmp_path):
    touch(tmp_path / "S (Track 1).bin")
    touch(tmp_path / "S (Track 2).bin")
    cue = tmp_path / "S.cue"
    cue.write_text('FILE "S (Track 1).bin" BINARY\nFILE "S (Track 2).bin" BINARY\n')
    assert [p.name for p in chd.source_files(game(cue))] == [
        "S.cue",
        "S (Track 1).bin",
        "S (Track 2).bin",
    ]


def test_source_files_archive_and_iso(tmp_path):
    archive = touch(tmp_path / "S.7z")
    iso = touch(tmp_path / "S.iso")
    assert chd.source_files(game(archive)) == [archive]
    assert chd.source_files(game(iso, "ps2")) == [iso]


def test_is_convertible(tmp_path):
    assert not chd.is_convertible(game(touch(tmp_path / "S.chd")))
    assert chd.is_convertible(game(touch(tmp_path / "S.7z")))


def test_disc_images_skips_referenced_and_other_files(tmp_path):
    touch(tmp_path / "Disc 1" / "A.bin")
    (tmp_path / "Disc 1" / "A.cue").write_text('FILE "A.bin" BINARY\n')
    touch(tmp_path / "B.iso")
    touch(tmp_path / "liesmich.txt")
    # Sortiert nach Pfad: „B.iso“ vor „Disc 1/A.cue“; BIN und TXT zählen nicht.
    assert [p.name for p in chd.disc_images(tmp_path)] == ["B.iso", "A.cue"]


def test_disc_images_ignores_iso_referenced_by_cue(tmp_path):
    touch(tmp_path / "A.iso")
    (tmp_path / "A.cue").write_text('FILE "A.iso" BINARY\n')
    assert [p.name for p in chd.disc_images(tmp_path)] == ["A.cue"]


# --- Planung -----------------------------------------------------------------------------------


def test_plan_single_disc_uses_library_name(tmp_path):
    archive = touch(tmp_path / "roms" / "psx" / "Spiel (USA).7z")
    work = tmp_path / "work"
    image = touch(work / "entpackt" / "anders.cue")
    [conversion] = chd.plan_conversions(game(archive), [image], work)
    assert conversion.target == tmp_path / "roms" / "psx" / "Spiel (USA).chd"
    assert conversion.part == work / "Spiel (USA).chd.part"
    assert conversion.media == "cd"


def test_plan_multi_disc_archive_uses_image_names(tmp_path):
    archive = touch(tmp_path / "roms" / "psx" / "FF8" / "FF8.7z")
    images = [tmp_path / "w" / "FF8 (Disc 1).cue", tmp_path / "w" / "FF8 (Disc 2).cue"]
    conversions = chd.plan_conversions(game(archive, game_dir="FF8"), images, tmp_path / "w")
    assert [c.target.name for c in conversions] == ["FF8 (Disc 1).chd", "FF8 (Disc 2).chd"]
    assert all(c.target.parent == archive.parent for c in conversions)


def test_plan_ps2_iso_is_dvd(tmp_path):
    iso = touch(tmp_path / "roms" / "ps2" / "Spiel.iso")
    [conversion] = chd.plan_conversions(game(iso, "ps2"), [iso], tmp_path / "w")
    assert conversion.media == "dvd"


def test_plan_refuses_existing_target(tmp_path):
    iso = touch(tmp_path / "Spiel.iso")
    touch(tmp_path / "Spiel.chd")
    with pytest.raises(chd.ChdError, match="existiert bereits"):
        chd.plan_conversions(game(iso, "ps2"), [iso], tmp_path / "w")


def test_plan_without_images(tmp_path):
    with pytest.raises(chd.ChdError, match="Kein Disc-Image"):
        chd.plan_conversions(game(touch(tmp_path / "S.7z")), [], tmp_path / "w")


def test_game_work_dir_is_unique_and_safe(tmp_path):
    a = game(touch(tmp_path / "roms" / "psx" / "FF8" / "Disc 1.cue"), game_dir="FF8")
    b = game(touch(tmp_path / "roms" / "psx" / "Disc 1.cue"))
    work_a, work_b = chd.game_work_dir(tmp_path, a), chd.game_work_dir(tmp_path, b)
    assert work_a != work_b
    assert work_a.parent == work_b.parent == tmp_path / "chdman"


def test_required_space(tmp_path):
    iso = touch(tmp_path / "S.iso", b"x" * 100)
    assert chd.required_space(game(iso, "ps2")) == 100
    archive = touch(tmp_path / "S.7z", b"x" * 10)
    assert chd.required_space(game(archive), unpacked_size=50) == 100


def test_finish_moves_parts_and_remove_files(tmp_path):
    part = touch(tmp_path / "work" / "S.chd.part", b"chd")
    target = tmp_path / "roms" / "psx" / "S.chd"
    conversion = chd.Conversion(tmp_path / "S.cue", "cd", part, target)
    assert chd.finish_conversion([conversion]) == [target]
    assert target.read_bytes() == b"chd" and not part.exists()
    other = touch(tmp_path / "a.bin")
    assert chd.remove_files([other, tmp_path / "fehlt.bin"]) == 1


def test_target_key_matches_library_key(tmp_path):
    folder_game = game(touch(tmp_path / "FF8" / "FF8.7z"), game_dir="FF8")
    assert chd.target_key(folder_game, tmp_path / "FF8" / "FF8.chd") == "psx/FF8/FF8.chd"
    plain = game(touch(tmp_path / "S.cue"))
    assert chd.target_key(plain, tmp_path / "S.chd") == "psx/S.chd"


# --- Zurückwandeln -----------------------------------------------------------------------------


def test_extract_target_folder_for_cd_not_for_dvd(tmp_path):
    g = game(touch(tmp_path / "Spiel.chd"))
    assert chd.extract_target(tmp_path / "out", g, "cd") == tmp_path / "out" / "Spiel"
    assert chd.extract_target(tmp_path / "out", g, "gd") == tmp_path / "out" / "Spiel"
    assert chd.extract_target(tmp_path / "out", g, "dvd") == tmp_path / "out"


def test_extract_outputs_exist(tmp_path):
    touch(tmp_path / "Spiel.cue")
    assert chd.extract_outputs_exist(tmp_path, "Spiel", "cd")
    assert not chd.extract_outputs_exist(tmp_path, "Spiel", "dvd")


# --- CHD-Kopf und Fortschritt ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tags", "media"),
    [
        ([b"CHT2", b"CHT2"], "cd"),
        ([b"CHGD"], "gd"),
        ([b"DVD "], "dvd"),
        ([b"GDDD"], None),  # Festplatten-CHD
        ([], None),
    ],
)
def test_read_header_media(tmp_path, tags, media):
    header = chd.read_header(fake_chd(tmp_path / "x.chd", tags, logical_size=5_000_000_000))
    assert header == chd.ChdHeader(5, 5_000_000_000, media)


def test_read_header_rejects_other_files(tmp_path):
    assert chd.read_header(touch(tmp_path / "x.chd", b"kein chd")) is None
    assert chd.read_header(tmp_path / "fehlt.chd") is None


def test_read_header_old_version(tmp_path):
    header = chd.read_header(fake_chd(tmp_path / "x.chd", [], version=4))
    assert header is not None and header.version == 4 and header.media is None


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Compressing, 54.1% complete... (ratio=89.1%)", 0.541),
        ("Verifying, 0.0% complete...", 0.0),
        ("Extracting, 100% complete...", 1.0),
        ("Compression complete ... final ratio = 94.0%", None),
        ("Raw SHA1 verification successful!", None),
    ],
)
def test_parse_progress(line, expected):
    assert chd.parse_progress(line) == expected


@pytest.mark.skipif(shutil.which("chdman") is None, reason="chdman nicht installiert")
def test_read_header_of_real_chdman_output(tmp_path):
    """Gegenprobe mit echtem chdman: Medienart aus selbst erzeugten CHDs."""
    touch(tmp_path / "S.bin", bytes(2352 * 20))
    cue = tmp_path / "S.cue"
    cue.write_text('FILE "S.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
    iso = touch(tmp_path / "D.iso", bytes(2048 * 20))
    for source, command, media in ((cue, "createcd", "cd"), (iso, "createdvd", "dvd")):
        output = tmp_path / f"{source.stem}.chd.part"
        subprocess.run(
            ["chdman", command, "-i", str(source), "-o", str(output), "-f"],
            check=True,
            capture_output=True,
        )
        header = chd.read_header(output)
        assert header is not None and header.media == media
