"""Tests für retro_manager.core.archives und retro_manager.core.formats."""

import subprocess
from pathlib import Path

import pytest

from retro_manager.core import archives, config, formats, tools
from retro_manager.core.library import LibraryGame


def touch(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def entry(path, slug="gb", kind="file", game_dir=""):
    return LibraryGame(slug, archives.archive_stem(path), path, kind, 0, game_dir)


# --- Erkennen ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "suffix", "stem", "label"),
    [
        ("Spiel (USA).7z", ".7z", "Spiel (USA)", "7Z"),
        ("Spiel.ZIP", ".zip", "Spiel", "ZIP"),
        ("Spiel.tar.gz", ".tar.gz", "Spiel", "TAR.GZ"),
        ("Spiel.tgz", ".tgz", "Spiel", "TGZ"),
        ("Spiel.tar", ".tar", "Spiel", "TAR"),
        ("Spiel.part1.rar", ".part1.rar", "Spiel", "RAR"),
        ("Spiel.part01.rar", ".part01.rar", "Spiel", "RAR"),
        ("Spiel.rar", ".rar", "Spiel", "RAR"),
        ("Spiel.7z.001", ".7z.001", "Spiel", "7Z"),
        ("Spiel.nes.gz", ".gz", "Spiel.nes", "GZ"),
    ],
)
def test_archive_suffix_stem_label(name, suffix, stem, label):
    path = Path("/roms/gb") / name
    assert archives.archive_suffix(path) == suffix
    assert archives.archive_stem(path) == stem
    assert archives.archive_label(path) == label


@pytest.mark.parametrize(
    "name", ["Spiel.part2.rar", "Spiel.r00", "Spiel.7z.002", "Spiel.z01", "Spiel.gb", "a.bin"]
)
def test_not_a_first_archive_volume(name):
    assert not archives.is_archive(Path(name))


def test_secondary_volumes():
    assert archives.is_secondary_volume(Path("S.part3.rar"))
    assert archives.is_secondary_volume(Path("S.r12"))
    assert not archives.is_secondary_volume(Path("S.part1.rar"))
    assert not archives.is_secondary_volume(Path("S.7z.001"))


def test_compressed_tar():
    assert archives.is_compressed_tar(Path("S.tar.xz"))
    assert archives.is_compressed_tar(Path("S.txz"))
    assert not archives.is_compressed_tar(Path("S.tar"))
    assert not archives.is_compressed_tar(Path("S.nes.gz"))


@pytest.mark.parametrize(
    ("first", "others"),
    [
        ("S.part1.rar", ["S.part2.rar", "S.part3.rar"]),
        ("S.rar", ["S.r00", "S.r01"]),
        ("S.7z.001", ["S.7z.002"]),
        ("S.zip", ["S.z01"]),
    ],
)
def test_volumes(tmp_path, first, others):
    for name in [first, *others, "Anderes.part2.rar", "Anderes.r00"]:
        touch(tmp_path / name)
    assert [p.name for p in archives.volumes(tmp_path / first)] == [first, *others]


def test_volumes_single(tmp_path):
    archive = touch(tmp_path / "S.7z")
    assert archives.volumes(archive) == [archive]


# --- Bibliothek --------------------------------------------------------------------------------


def test_original_files(tmp_path):
    touch(tmp_path / "S.part1.rar")
    touch(tmp_path / "S.part2.rar")
    rar = entry(tmp_path / "S.part1.rar", kind="archive")
    assert [p.name for p in archives.original_files(rar)] == ["S.part1.rar", "S.part2.rar"]
    touch(tmp_path / "D.bin")
    (tmp_path / "D.cue").write_text('FILE "D.bin" BINARY\n')
    cue = LibraryGame("psx", "D", tmp_path / "D.cue", "cue", 0)
    assert [p.name for p in archives.original_files(cue)] == ["D.cue", "D.bin"]


def test_work_dir_unique_per_entry(tmp_path):
    a = entry(tmp_path / "S.7z", kind="archive")
    b = entry(tmp_path / "S.zip", kind="archive")
    assert archives.work_dir(tmp_path, a) != archives.work_dir(tmp_path, b)
    assert archives.work_dir(tmp_path, a).parent == tmp_path / "archive"


# --- Entpacken einsortieren --------------------------------------------------------------------


def test_layout_single_file_next_to_archive(tmp_path):
    staging = tmp_path / "w"
    touch(staging / "Tetris.gb")
    moves = archives.extracted_layout(staging, tmp_path / "roms" / "gb", "Tetris")
    assert moves == [(staging / "Tetris.gb", tmp_path / "roms" / "gb" / "Tetris.gb")]


def test_layout_single_folder_kept(tmp_path):
    staging = tmp_path / "w"
    touch(staging / "Spiel" / "a.bin")
    touch(staging / "Spiel" / "a.cue")
    moves = archives.extracted_layout(staging, tmp_path / "dest", "Archivname")
    assert moves == [(staging / "Spiel", tmp_path / "dest" / "Spiel")]


def test_layout_many_files_become_game_folder(tmp_path):
    staging = tmp_path / "w"
    touch(staging / "a.cue")
    touch(staging / "a.bin")
    moves = archives.extracted_layout(staging, tmp_path / "dest", "Spiel (USA)")
    assert moves == [(staging, tmp_path / "dest" / "Spiel (USA)")]
    [target] = archives.move_into_place(moves)
    assert sorted(p.name for p in target.iterdir()) == ["a.bin", "a.cue"]


def test_layout_refuses_existing_target_and_empty(tmp_path):
    staging = tmp_path / "w"
    touch(staging / "Tetris.gb")
    touch(tmp_path / "dest" / "Tetris.gb", b"vorhanden")
    with pytest.raises(archives.ArchiveError, match="existiert bereits"):
        archives.extracted_layout(staging, tmp_path / "dest", "Tetris")
    empty = tmp_path / "leer"
    empty.mkdir()
    with pytest.raises(archives.ArchiveError, match="leer"):
        archives.extracted_layout(empty, tmp_path / "dest", "X")


def test_find_inner_tar(tmp_path):
    tar = touch(tmp_path / "Spiel.tar")
    assert archives.find_inner_tar(tmp_path) == tar
    touch(tmp_path / "Zweite.tar")
    with pytest.raises(archives.ArchiveError):
        archives.find_inner_tar(tmp_path)


# --- Packen ------------------------------------------------------------------------------------


def test_plan_pack_rom_and_cue(tmp_path):
    rom = touch(tmp_path / "roms" / "gb" / "Tetris.gb")
    plan = archives.plan_pack(entry(rom), "zip", tmp_path / "w")
    assert plan.names == ("Tetris.gb",)
    assert plan.target == rom.parent / "Tetris.zip"
    assert plan.part == tmp_path / "w" / "Tetris.zip.part"
    touch(tmp_path / "D (Track 1).bin")
    (tmp_path / "D.cue").write_text('FILE "D (Track 1).bin" BINARY\n')
    cue = LibraryGame("psx", "D", tmp_path / "D.cue", "cue", 0)
    assert archives.plan_pack(cue, "7z", tmp_path / "w").names == ("D.cue", "D (Track 1).bin")


def test_plan_pack_repack_archive_uses_contents(tmp_path):
    archive = touch(tmp_path / "Spiel.7z")
    game = entry(archive, kind="archive")
    with pytest.raises(archives.ArchiveError, match="entpackt"):
        archives.plan_pack(game, "zip", tmp_path / "w")
    plan = archives.plan_pack(game, "zip", tmp_path / "w", ["Spiel.gb"])
    assert plan.names == ("Spiel.gb",) and plan.target == tmp_path / "Spiel.zip"


def test_pack_target_conflicts(tmp_path):
    zipped = touch(tmp_path / "Spiel.zip")
    with pytest.raises(archives.ArchiveError, match="bereits als ZIP"):
        archives.check_pack_target(entry(zipped, kind="archive"), "zip")
    rom = touch(tmp_path / "Spiel.gb")
    with pytest.raises(archives.ArchiveError, match="existiert bereits"):
        archives.check_pack_target(entry(rom), "zip")
    with pytest.raises(archives.ArchiveError, match="Unbekannt"):
        archives.check_pack_target(entry(rom), "rar")


def test_remove_files(tmp_path):
    a = touch(tmp_path / "a")
    assert archives.remove_files([a, tmp_path / "fehlt"]) == 1 and not a.exists()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  0M Scan\b\b\b\b\b\b\b\b\b         \b\b\b\b\b\b\b\b\b  0%\b\b\b\b    \b\b\b\b", 0.0),
        (" 48% 1 + big.bin\b\b\b\b\b\b\b\b 97% 2 + big.bin", 0.97),
        ("100% Orange Juice.zip", 1.0),  # Prozent im Dateinamen zählt nicht doppelt
        (" 12% 3 + 100% Orange Juice.bin", 0.12),
        ("  0M Scan", None),
    ],
)
def test_parse_progress(text, expected):
    assert archives.parse_progress(text) == expected


# --- Zielformat je System ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slug", "target"),
    [
        ("gb", "zip"),
        ("n64", "zip"),
        ("psx", "chd"),
        ("PS2", "chd"),
        ("dc", "chd"),
        ("ngc", "rvz"),
        ("wii", "rvz"),
        ("switch", "nsz"),
        ("ps3", None),
    ],
)
def test_target_format(slug, target):
    assert formats.target_format(slug) == target


# --- Gegenprobe mit echtem 7-Zip ---------------------------------------------------------------

SEVENZIP = tools.sevenzip_executable(config.tools_dir(config.app_dir()))


@pytest.mark.skipif(SEVENZIP is None, reason="7-Zip nicht vorhanden")
def test_real_7zip_pack_test_extract(tmp_path):
    source = tmp_path / "src"
    touch(source / "-seltsam.gb", b"rom" * 1000)
    part = tmp_path / "S.zip.part"
    pack = tools.sevenzip_pack_args("zip", 5, part, ["-seltsam.gb"])
    subprocess.run([str(SEVENZIP), *pack], cwd=source, check=True, capture_output=True)
    subprocess.run(
        [str(SEVENZIP), *tools.sevenzip_test_args(part)], check=True, capture_output=True
    )
    out = tmp_path / "out"
    extract = tools.sevenzip_extract_args(part, out)
    subprocess.run([str(SEVENZIP), *extract], check=True, capture_output=True)
    assert (out / "-seltsam.gb").read_bytes() == b"rom" * 1000
