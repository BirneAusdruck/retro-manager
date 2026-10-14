"""Tests für retro_manager.core.igir_report."""

from pathlib import Path

from retro_manager.core.igir_report import (
    IgirReport,
    parse_report,
    status_counts,
    without_unused_under,
)


def write(tmp_path, text: str):
    path = tmp_path / "report.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_report_reads_header_and_rows(tmp_path):
    path = write(
        tmp_path, 'DAT Name,Game Name,Status\nGB,"Tetris (World)",FOUND\nGB,Zelda,MISSING\n'
    )
    report = parse_report(path)
    assert report.columns == ["DAT Name", "Game Name", "Status"]
    assert report.rows == [["GB", "Tetris (World)", "FOUND"], ["GB", "Zelda", "MISSING"]]
    assert report.status_index == 2


def test_parse_report_pads_short_rows_and_skips_empty_lines(tmp_path):
    report = parse_report(write(tmp_path, "A,B,Status\n1\n\n"))
    assert report.rows == [["1", "", ""]]


def test_parse_report_handles_bom(tmp_path):
    report = parse_report(write(tmp_path, "﻿Status\nFOUND\n"))
    assert report.columns == ["Status"]


def test_status_counts():
    report = IgirReport(["Name", "Status"], [["a", "FOUND"], ["b", "FOUND"], ["c", "UNUSED"]])
    assert status_counts(report) == {"FOUND": 2, "UNUSED": 1}


def test_status_counts_without_status_column():
    assert status_counts(IgirReport(["Name"], [["a"]])) == {}


def test_empty_file_gives_empty_report(tmp_path):
    report = parse_report(write(tmp_path, ""))
    assert report.columns == [] and report.rows == []


def test_without_unused_under_drops_helper_files_only():
    report = IgirReport(
        ["Game Name", "Status", "ROM Files"],
        [
            ["Spiel", "FOUND", "/roms/a.bin|/dats/redump-cues/psx/Spiel.cue"],
            ["", "UNUSED", "/dats/redump-cues/psx/Anderes.cue"],
            ["", "UNUSED", "/roms/mod.7z"],
            ["Fehlt", "MISSING", ""],
        ],
    )
    filtered = without_unused_under(report, [Path("/dats/redump-cues/psx")])
    assert [row[0] or row[2] for row in filtered.rows] == ["Spiel", "/roms/mod.7z", "Fehlt"]


def test_without_unused_under_without_roots_returns_same():
    report = IgirReport(["Status"], [["UNUSED"]])
    assert without_unused_under(report, []) is report
