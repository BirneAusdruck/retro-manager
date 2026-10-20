"""Tests für retro_manager.core.library."""

from retro_manager.core import library
from retro_manager.core.library import scan_platform


def touch(path, size=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_scan_platform_files_and_game_folders(tmp_path):
    roms = tmp_path / "roms"
    touch(roms / "psx" / "Spiel A (USA).7z", 10)
    touch(roms / "psx" / "Spiel B (USA).cue")
    touch(roms / "psx" / "Spiel B (USA).bin")  # zählt nur über die CUE
    touch(roms / "psx" / "Final Fantasy VIII" / "FF8 (Disc 1).chd")
    touch(roms / "psx" / "Final Fantasy VIII" / "FF8 (Disc 2).chd")
    touch(roms / "psx" / "Final Fantasy VIII" / "manual" / "Handbuch.chd")  # RomM-Unterordner
    touch(roms / "psx" / ".versteckt.iso")
    touch(roms / "psx" / "liesmich.txt")
    games = scan_platform(roms, "psx")
    assert [(g.name, g.kind, g.game_dir) for g in games] == [
        ("FF8 (Disc 1)", "chd", "Final Fantasy VIII"),
        ("FF8 (Disc 2)", "chd", "Final Fantasy VIII"),
        ("Spiel A (USA)", "archive", ""),
        ("Spiel B (USA)", "cue", ""),
    ]
    assert games[2].size == 10
    assert games[0].key == "psx/Final Fantasy VIII/FF8 (Disc 1).chd"
    assert games[2].key == "psx/Spiel A (USA).7z"


def test_scan_missing_platform(tmp_path):
    assert scan_platform(tmp_path, "ps3") == []


def test_scan_platform_gdi(tmp_path):
    roms = tmp_path / "roms"
    touch(roms / "dc" / "Spiel (Europe)" / "Spiel (Europe).gdi")
    touch(roms / "dc" / "Spiel (Europe)" / "track01.bin")
    [game] = scan_platform(roms, "dc")
    assert (game.kind, game.game_dir) == ("gdi", "Spiel (Europe)")


def test_size_of_cue_and_gdi_includes_tracks(tmp_path):
    roms = tmp_path / "roms"
    touch(roms / "psx" / "S (Track 1).bin", 1000)
    touch(roms / "psx" / "S (Track 2).bin", 500)
    cue = roms / "psx" / "S.cue"
    cue.write_text('FILE "S (Track 1).bin" BINARY\nFILE "S (Track 2).bin" BINARY\n')
    touch(roms / "dc" / "G" / "track01.bin", 300)
    gdi = roms / "dc" / "G" / "G.gdi"
    gdi.write_text("1\n1 0 4 2352 track01.bin 0\n")
    [psx] = scan_platform(roms, "psx")
    [dc] = scan_platform(roms, "dc")
    assert psx.size == 1500 + cue.stat().st_size
    assert dc.size == 300 + gdi.stat().st_size


def test_scan_entries(tmp_path):
    roms = tmp_path / "roms"
    touch(roms / "gb" / "Tetris (World).gb", 10)
    touch(roms / "gb" / "Zelda (USA).7z")
    touch(roms / "psx" / "Spiel (USA).bin", 100)
    (roms / "psx" / "Spiel (USA).cue").write_text('FILE "Spiel (USA).bin" BINARY\n')
    touch(roms / "psx" / "Gross.part1.rar", 5)
    touch(roms / "psx" / "Gross.part2.rar", 7)
    touch(roms / "psx" / "FF8" / "FF8 (Disc 1).chd")
    touch(roms / "psx" / "FF8" / "manual" / "Handbuch.pdf")
    touch(roms / "psx" / ".versteckt.7z")
    gb = library.scan_entries(roms, "gb")
    assert [(g.name, g.kind, g.size) for g in gb] == [
        ("Tetris (World)", "file", 10),
        ("Zelda (USA)", "archive", 1),
    ]
    psx = library.scan_entries(roms, "psx")
    assert [(g.name, g.kind, g.game_dir) for g in psx] == [
        ("FF8 (Disc 1)", "chd", "FF8"),
        ("Gross", "archive", ""),
        ("Spiel (USA)", "cue", ""),
    ]
    assert psx[1].size == 12  # alle Teile
    assert psx[2].size == 100 + len('FILE "Spiel (USA).bin" BINARY\n')  # CUE samt BIN


def test_platforms(tmp_path):
    for name in ("snes", "GB", ".versteckt"):
        (tmp_path / "roms" / name).mkdir(parents=True)
    touch(tmp_path / "roms" / "liesmich.txt")
    assert library.platforms(tmp_path / "roms") == ["GB", "snes"]
    assert library.platforms(tmp_path / "fehlt") == []


def test_scan_platform_only_disc_sources(tmp_path):
    """chdman und Export bekommen nur, was sie selbst verarbeiten können."""
    roms = tmp_path / "roms"
    for name in ("A.7z", "B.zip", "C.rar", "D.tar.gz", "E.7z.001", "F.chd", "G.gb"):
        touch(roms / "psx" / name)
    assert [g.path.name for g in scan_platform(roms, "psx")] == ["A.7z", "B.zip", "F.chd"]
    assert len(library.scan_entries(roms, "psx")) == 7
