"""Tests für retro_manager.core.tools."""

import sys
from datetime import datetime
from pathlib import Path

from retro_manager.core import tools


def test_igir_executable_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    assert tools.igir_executable(tmp_path) == tmp_path / "igir" / "igir"


def test_igir_executable_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    assert tools.igir_executable(tmp_path) == tmp_path / "igir" / "igir.exe"


def test_igir_verify_args_do_not_write():
    args = tools.igir_verify_args(Path("/roms"), Path("/dats"), Path("/r/report.csv"))
    assert args == [
        "test",
        "report",
        "--dat",
        "/dats",
        "--input",
        "/roms",
        "--report-output",
        "/r/report.csv",
    ]
    for writing in ("copy", "move", "link", "extract", "zip", "clean", "--output"):
        assert writing not in args


def test_report_path_has_timestamp_without_percent(tmp_path):
    path = tools.report_path(tmp_path, datetime(2026, 10, 14, 9, 5, 7))
    assert path == tmp_path / "igir_report_2026-10-14_09-05-07.csv"
    assert "%" not in path.name


def test_clean_output_strips_ansi_and_splits_carriage_returns():
    text = "\x1b[32mScanning\x1b[0m 1/3\r Scanning 2/3\r\nDone\n\n"
    assert tools.clean_output(text) == ["Scanning 1/3", " Scanning 2/3", "Done"]


def test_clean_output_empty():
    assert tools.clean_output("\r\n  \n") == []


def test_igir_verify_args_with_extra_inputs():
    args = tools.igir_verify_args(Path("/roms"), Path("/dats"), Path("/r.csv"), [Path("/c/psx")])
    assert args == [
        "test",
        "report",
        "--dat",
        "/dats",
        "--input",
        "/roms",
        "--input",
        "/c/psx",
        "--report-output",
        "/r.csv",
    ]


def test_cue_inputs_prefers_platform_folder(tmp_path):
    (tmp_path / "psx").mkdir()
    (tmp_path / "saturn").mkdir()
    assert tools.cue_inputs(Path("/hdd/roms/psx"), tmp_path) == [tmp_path / "psx"]
    assert tools.cue_inputs(Path("/hdd/roms"), tmp_path) == [tmp_path / "psx", tmp_path / "saturn"]


def test_cue_inputs_without_cues(tmp_path):
    assert tools.cue_inputs(Path("/hdd/roms/psx"), None) == []
    assert tools.cue_inputs(Path("/hdd/roms/psx"), tmp_path / "fehlt") == []


def test_chdman_prefers_tools_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    local = tmp_path / "chdman" / "chdman"
    local.parent.mkdir()
    local.write_text("")
    assert tools.chdman_executable(tmp_path) == local


def test_chdman_falls_back_to_path(tmp_path, monkeypatch):
    monkeypatch.setattr(tools.shutil, "which", lambda name: "/usr/bin/chdman")
    assert tools.chdman_executable(tmp_path) == Path("/usr/bin/chdman")
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    assert tools.chdman_executable(tmp_path) is None


def test_chdman_extract_args():
    cd = tools.chdman_extract_args("cd", Path("/a/x.chd"), Path("/out"), "Spiel")
    assert cd == ["extractcd", "-i", "/a/x.chd", "-o", "/out/Spiel.cue", "--splitbin", "-f"]
    dvd = tools.chdman_extract_args("dvd", Path("/a/x.chd"), Path("/out"), "Spiel")
    assert dvd == ["extractdvd", "-i", "/a/x.chd", "-o", "/out/Spiel.iso", "-f"]


def test_chdman_extract_args_gdrom():
    gd = tools.chdman_extract_args("gd", Path("/a/x.chd"), Path("/out"), "Spiel")
    assert gd == ["extractcd", "-i", "/a/x.chd", "-o", "/out/Spiel.gdi", "-f"]


def test_chdman_create_args():
    cd = tools.chdman_create_args("cd", Path("/r/Spiel.cue"), Path("/t/Spiel.chd.part"))
    assert cd == ["createcd", "-i", "/r/Spiel.cue", "-o", "/t/Spiel.chd.part", "-f"]
    dvd = tools.chdman_create_args("dvd", Path("/r/Spiel.iso"), Path("/t/Spiel.chd.part"))
    assert dvd[0] == "createdvd"


def test_chdman_verify_and_info_args():
    assert tools.chdman_verify_args(Path("/a/x.chd")) == ["verify", "-i", "/a/x.chd"]
    assert tools.chdman_info_args(Path("/a/x.chd")) == ["info", "-i", "/a/x.chd"]


def test_sevenzip_prefers_tools_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tools.sys, "platform", "linux")
    local = tmp_path / "7zip" / "7zz"
    local.parent.mkdir()
    local.write_bytes(b"")
    assert tools.sevenzip_executable(tmp_path) == local


def test_sevenzip_falls_back_to_path(tmp_path, monkeypatch):
    monkeypatch.setattr(tools.shutil, "which", lambda name: "/usr/bin/7z" if name == "7z" else None)
    assert tools.sevenzip_executable(tmp_path) == Path("/usr/bin/7z")
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    assert tools.sevenzip_executable(tmp_path) is None


def test_sevenzip_args():
    assert tools.sevenzip_extract_args(Path("/a/x.7z"), Path("/w/out")) == [
        "x",
        "/a/x.7z",
        "-o/w/out",
        "-y",
        "-bsp1",
        "-bso0",
        "-bse2",
    ]
    assert tools.sevenzip_test_args(Path("/a/x.rar"))[:2] == ["t", "/a/x.rar"]
    pack = tools.sevenzip_pack_args("zip", 9, Path("/w/S.zip.part"), ["-seltsam.gb", "b.bin"])
    assert pack[:4] == ["a", "-tzip", "-mx=9", "-mmt=on"]
    # Dateinamen stehen hinter `--`, damit „-seltsam.gb“ kein Schalter wird.
    assert pack[-4:] == ["/w/S.zip.part", "--", "-seltsam.gb", "b.bin"]
