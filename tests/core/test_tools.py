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
