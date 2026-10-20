"""Tests für retro_manager.core.export."""

import struct
import zipfile

import py7zr
import pytest

from retro_manager.core import devices, export
from retro_manager.core.library import LibraryGame

PS3 = devices.PS3_WEBMAN


def noop(*args):
    pass


def never():
    return False


def game(tmp_path, slug, kind, name="Spiel (USA)", suffix=None, game_dir=""):
    path = tmp_path / "roms" / slug / f"{name}{suffix or '.' + kind}"
    return LibraryGame(slug, name, path, kind, 0, game_dir)


@pytest.mark.parametrize(
    ("slug", "kind", "suffix", "expected"),
    [
        ("psx", "chd", None, export.ChdExtract),
        ("ps2", "archive", ".7z", export.ExtractArchive),
        ("psp", "iso", None, export.CopyFiles),
    ],
)
def test_plan_step_types(tmp_path, slug, kind, suffix, expected):
    [step] = export.plan_disc_export(
        game(tmp_path, slug, kind, suffix=suffix), tmp_path / "out", PS3
    )
    assert isinstance(step, expected)


def test_plan_chd_media_by_platform(tmp_path):
    [ps1] = export.plan_disc_export(game(tmp_path, "psx", "chd"), tmp_path / "out", PS3)
    [ps2] = export.plan_disc_export(game(tmp_path, "ps2", "chd"), tmp_path / "out", PS3)
    assert (ps1.media, ps2.media) == ("cd", "dvd")
    assert ps1.target == tmp_path / "out" / "PSXISO" / "Spiel (USA)"
    assert ps1.name == "Spiel (USA)"


def test_plan_cue_copies_referenced_bins(tmp_path):
    folder = tmp_path / "roms" / "psx"
    folder.mkdir(parents=True)
    (folder / "S (Track 1).bin").write_bytes(b"a")
    (folder / "S (Track 2).bin").write_bytes(b"b")
    cue = folder / "S.cue"
    cue.write_text(
        'FILE "S (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\nFILE "S (Track 2).bin" BINARY\n'
    )
    [step] = export.plan_disc_export(LibraryGame("psx", "S", cue, "cue", 1), tmp_path / "out", PS3)
    assert [p.name for p in step.sources] == ["S.cue", "S (Track 1).bin", "S (Track 2).bin"]


def test_plan_unsupported_platform(tmp_path):
    with pytest.raises(export.ExportError):
        export.plan_disc_export(game(tmp_path, "gb", "iso"), tmp_path, PS3)


def test_cue_files_unquoted_and_missing(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"")
    cue = tmp_path / "x.cue"
    cue.write_text('FILE a.bin BINARY\nFILE "fehlt.bin" BINARY\nREM FILE x\n')
    assert export.cue_files(cue) == [tmp_path / "a.bin"]


def test_normalize_single_track(tmp_path):
    (tmp_path / "Spiel (Track 1).bin").write_bytes(b"data")
    cue = tmp_path / "Spiel.cue"
    cue.write_text('FILE "Spiel (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\n')
    export.normalize_single_track(cue)
    assert (tmp_path / "Spiel.bin").read_bytes() == b"data"
    assert cue.read_text().startswith('FILE "Spiel.bin" BINARY')


def test_normalize_keeps_multi_track(tmp_path):
    for n in (1, 2):
        (tmp_path / f"S (Track {n}).bin").write_bytes(b"")
    cue = tmp_path / "S.cue"
    cue.write_text('FILE "S (Track 1).bin" BINARY\nFILE "S (Track 2).bin" BINARY\n')
    export.normalize_single_track(cue)
    assert (tmp_path / "S (Track 1).bin").exists()


def test_chd_logical_size(tmp_path):
    chd = tmp_path / "x.chd"
    chd.write_bytes(b"MComprHD" + b"\0" * 24 + struct.pack(">Q", 700_000_000))
    assert export.chd_logical_size(chd) == 700_000_000
    other = tmp_path / "y.chd"
    other.write_bytes(b"kein chd")
    assert export.chd_logical_size(other) is None


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def make_7z(path, files, tmp_path):
    with py7zr.SevenZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(data, name)


@pytest.mark.parametrize("suffix", [".zip", ".7z"])
def test_extract_archive_with_progress(tmp_path, suffix):
    source = tmp_path / f"Spiel{suffix}"
    files = {"Spiel.cue": b"FILE", "Spiel.bin": b"x" * 5000}
    (make_zip if suffix == ".zip" else lambda p, f: make_7z(p, f, tmp_path))(source, files)
    seen = []
    step = export.ExtractArchive(source, tmp_path / "out")
    assert export.estimated_size(step) == 5004
    written = export.extract_archive(step, lambda d, t: seen.append((d, t)), never)
    assert sorted(p.name for p in written) == ["Spiel.bin", "Spiel.cue"]
    assert (tmp_path / "out" / "Spiel.bin").read_bytes() == b"x" * 5000
    assert seen and seen[-1] == (5004, 5004)


@pytest.mark.parametrize("suffix", [".zip", ".7z"])
def test_extract_archive_cancel(tmp_path, suffix):
    source = tmp_path / f"S{suffix}"
    (make_zip if suffix == ".zip" else lambda p, f: make_7z(p, f, tmp_path))(
        source, {"a.bin": b"x" * 100}
    )
    with pytest.raises(export.ExportCancelled):
        export.extract_archive(export.ExtractArchive(source, tmp_path / "out"), noop, lambda: True)


def test_extract_archive_rejects_unsafe_paths(tmp_path):
    source = tmp_path / "boese.zip"
    make_zip(source, {"../ausserhalb.txt": b"x"})
    with pytest.raises(export.ExportError):
        export.extract_archive(export.ExtractArchive(source, tmp_path / "out"), noop, never)
    assert not (tmp_path / "ausserhalb.txt").exists()


def test_extract_broken_archive(tmp_path):
    source = tmp_path / "kaputt.7z"
    source.write_bytes(b"kein archiv")
    with pytest.raises(export.ExportError):
        export.extract_archive(export.ExtractArchive(source, tmp_path / "out"), noop, never)


def test_copy_files(tmp_path):
    src = tmp_path / "Spiel.iso"
    src.write_bytes(b"iso" * 10)
    step = export.CopyFiles((src,), tmp_path / "out" / "PS2ISO")
    assert export.copy_files(step, noop, never) == [tmp_path / "out" / "PS2ISO" / "Spiel.iso"]
    with pytest.raises(export.ExportCancelled):
        export.copy_files(step, noop, lambda: True)


def test_free_space_for_missing_dir(tmp_path):
    assert export.free_space(tmp_path / "gibt" / "es" / "nicht") > 0


def test_manifest_record_status_delete(tmp_path):
    root = tmp_path / "ps3"
    folder = root / "PSXISO" / "Spiel"
    folder.mkdir(parents=True)
    files = [folder / "Spiel.cue", folder / "Spiel.bin"]
    for f in files:
        f.write_bytes(b"x")
    own = root / "PSXISO" / "eigen.bin"
    own.write_bytes(b"meins")
    export.record_export(root, "psx/Spiel.7z", files)
    assert export.export_status(root) == {"psx/Spiel.7z": export.STATUS_PREPARED}
    export.set_status(root, "psx/Spiel.7z", export.STATUS_TRANSFERRED)
    assert export.export_status(root)["psx/Spiel.7z"] == export.STATUS_TRANSFERRED
    assert export.delete_export(root, "psx/Spiel.7z") == 2
    assert not folder.exists()  # leerer Spielordner entfernt
    assert own.read_bytes() == b"meins"
    assert export.export_status(root) == {}


def test_manifest_ignores_unsafe_entries(tmp_path):
    root = tmp_path / "ps3"
    root.mkdir()
    outside = tmp_path / "wichtig.txt"
    outside.write_text("x")
    (root / export.MANIFEST_FILENAME).write_text('{"games": {"k": {"files": ["../wichtig.txt"]}}}')
    export.delete_export(root, "k")
    assert outside.exists()


def ps3_game(tmp_path, kind="iso", name="Spiel (Europe)"):
    suffix = ".iso" if kind == "iso" else ".zip"
    path = tmp_path / "roms" / "ps3" / f"{name}{suffix}"
    return LibraryGame("ps3", name, path, kind, 0)


def test_plan_ps3_with_key_decrypts(tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / "Spiel (Europe).key").write_bytes(bytes(16))
    [step] = export.plan_disc_export(ps3_game(tmp_path), tmp_path / "out", PS3, keys)
    assert isinstance(step, export.DecryptPs3)
    assert step.target == tmp_path / "out" / "PS3ISO"
    extract, decrypt = export.plan_disc_export(
        ps3_game(tmp_path, "archive"), tmp_path / "out", PS3, keys
    )
    assert isinstance(extract, export.ExtractArchive) and isinstance(decrypt, export.DecryptPs3)
    assert (
        extract.target
        == decrypt.source
        == tmp_path / "out" / "PS3ISO" / ".entpacken" / "Spiel (Europe)"
    )


def test_plan_ps3_without_key_copies(tmp_path):
    [step] = export.plan_disc_export(ps3_game(tmp_path), tmp_path / "out", PS3, tmp_path / "keys")
    assert isinstance(step, export.CopyFiles)


def test_decrypt_ps3_from_unpack_dir_removes_it(tmp_path):
    from tests.core.test_ps3_iso import KEY, make_iso

    unpack = tmp_path / "out" / "PS3ISO" / ".entpacken" / "Spiel"
    unpack.mkdir(parents=True)
    iso, clear = make_iso(unpack)
    key = tmp_path / "Spiel.key"
    key.write_bytes(KEY)
    step = export.DecryptPs3(unpack, tmp_path / "out" / "PS3ISO", key)
    assert export.estimated_size(step) == len(clear)
    [written] = export.decrypt_ps3(step, noop, never)
    assert written.read_bytes() == clear
    assert not (tmp_path / "out" / "PS3ISO" / ".entpacken").exists()
