"""Tests für retro_manager.core.dat_update."""

import io
import json
import zipfile
from datetime import date

import pytest

from retro_manager.core import dat_update as du


def dat(name: str) -> bytes:
    return (
        f'<?xml version="1.0"?><datafile><header><name>{name}</name></header></datafile>'.encode()
    )


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


PLATFORMS = [
    du.RommPlatform("gb", "Game Boy", "Portable Console"),
    du.RommPlatform("gba", "Game Boy Advance", "Portable Console"),
    du.RommPlatform("mac", "Mac", "Computer"),
    du.RommPlatform("zeebo", "Zeebo", "Console"),
    du.RommPlatform("switch", "Nintendo Switch", "Console"),
]
TOKENS = json.dumps(
    {
        "consoles": [
            {
                "datNameRegex": "/\\\\bGB\\\\b|Game ?Boy/i",
                "extensions": [],
                "tokens": {"romm": "gb"},
            },
            {"datNameRegex": "/Game ?Boy Advance/i", "extensions": [], "tokens": {"romm": "gba"}},
            {"datNameRegex": "/Gundam/i", "extensions": [], "tokens": {"es": "x"}},
        ]
    }
)


def test_parse_redump_systems_with_bios_and_entities():
    page = """<table><tr><th>System</th></tr>
    <tr><td>Sony PlayStation 3</td><td><a href="/datfile/ps3/">Datfile</a></td>
        <td><a href="/keys/ps3/">HEX</a></td></tr>
    <tr><td>Sony PlayStation</td><td><a href="/cues/psx/">Cuesheets</a></td>
        <td><a href="/datfile/psx/">Datfile</a></td>
        <td><a href="/datfile/psx-bios/">BIOS Datfile</a></td></tr>
    <tr><td>NEC PC-FX &amp; PC-FXGA</td><td><a href="/datfile/pc-fx/">Datfile</a></td></tr>
    <tr><td>Konami Twinkle</td><td></td></tr></table>"""
    assert du.parse_redump_systems(page) == [
        du.RedumpSystem("ps3", "Sony PlayStation 3", has_keys=True),
        du.RedumpSystem("psx", "Sony PlayStation", has_cues=True),
        du.RedumpSystem("psx-bios", "Sony PlayStation (BIOS)"),
        du.RedumpSystem("pc-fx", "NEC PC-FX & PC-FXGA"),
    ]


def test_parse_daily_submit_name():
    page = '<input type="submit" name="daily_dl_2026-05-30" value="Request" />'
    assert du.parse_daily_submit_name(page) == "daily_dl_2026-05-30"
    assert du.parse_daily_submit_name("<html>") is None


def test_daily_form_fields_request_parent_clone():
    fields = du.daily_form_fields("daily_dl_x")
    assert ("dat_type", "pc") in fields
    assert ("set[1]", "Ok") in fields
    assert fields[-1] == ("daily_dl_x", "Request")


def test_parse_download_button_skips_hidden_trap():
    page = (
        '<input type="submit" name="' + "a" * 32 + '" value="Download!!" style="display:none;">'
        '<input type="submit" name="' + "b" * 32 + '" value="Download!!">'
    )
    assert du.parse_download_button(page) == "b" * 32
    assert (
        du.parse_download_button(
            '<input type="submit" name="' + "a" * 32 + '" value="Download!!" style="display: none">'
        )
        is None
    )


def test_filename_from_disposition_strips_paths():
    header = 'attachment; filename="No-Intro Love Pack (PC) (2026-10-13).zip"'
    assert du.filename_from_disposition(header) == "No-Intro Love Pack (PC) (2026-10-13).zip"
    assert du.filename_from_disposition('attachment; filename="../../etc/x.dat"') == "x.dat"
    assert du.filename_from_disposition("inline") is None


def test_dat_header_name_unescapes():
    assert du.dat_header_name(dat("NEC - PC-FX &amp; PC-FXGA")) == "NEC - PC-FX & PC-FXGA"
    assert du.dat_header_name(b"<datafile/>") == ""


def test_extract_nointro_keeps_game_sets_only():
    pack = zip_bytes(
        {
            "No-Intro/Nintendo - Game Boy (Parent-Clone) (1).dat": dat("Nintendo - Game Boy"),
            "Non-Redump/Non-Redump - Sony - PlayStation (2).dat": dat(
                "Non-Redump - Sony - PlayStation"
            ),
            "Source Code/Source - x.dat": dat("x"),
            "No-Intro/readme.txt": b"hi",
        }
    )
    result = {(d.group, d.filename, d.name) for d in du.extract_nointro(pack)}
    assert result == {
        ("no-intro", "Nintendo - Game Boy (Parent-Clone) (1).dat", "Nintendo - Game Boy"),
        (
            "no-intro/Non-Redump",
            "Non-Redump - Sony - PlayStation (2).dat",
            "Non-Redump - Sony - PlayStation",
        ),
    }


def test_extract_redump_zip_and_plain():
    zipped = du.extract_redump(
        "x.zip", zip_bytes({"Sony - PlayStation (1).dat": dat("Sony - PlayStation")})
    )
    plain = du.extract_redump("Sony - PlayStation - BIOS.dat", dat("Sony - PlayStation - BIOS"))
    assert [(d.group, d.filename) for d in zipped] == [("redump", "Sony - PlayStation (1).dat")]
    assert [(d.group, d.name) for d in plain] == [("redump", "Sony - PlayStation - BIOS")]


def test_parse_console_tokens():
    rules = du.parse_console_tokens(TOKENS)
    assert rules[0].pattern.search("nintendo - game boy")
    assert rules[1].romm == "gba"
    assert rules[2].romm is None


@pytest.mark.parametrize(
    ("dat_name", "slug", "how"),
    [
        ("Nintendo - Game Boy (Parent-Clone)", "gb", "igir"),
        (
            "Nintendo - Game Boy Advance (Parent-Clone)",
            "gba",
            "igir",
        ),  # letzte passende Regel gewinnt
        ("Apple - Macintosh (DC42)", "mac", "manuell"),
        ("Zeebo - Zeebo (Parent-Clone)", "zeebo", "name"),
        ("Capcom - Play System III", None, ""),  # bekannter Fehltreffer
        ("Bandai - Gundam RX-78", None, ""),  # Igir-Regel ohne RomM-Ordner
        ("Nintendo - amiibo", None, ""),
    ],
)
def test_match_dats(dat_name, slug, how):
    [match] = du.match_dats(
        [du.DatFile("no-intro", "x.dat", b"", dat_name)], du.parse_console_tokens(TOKENS), PLATFORMS
    )
    assert (match.platform.slug if match.platform else None, match.how) == (slug, how)


def matches_for(*names: str) -> list[du.DatMatch]:
    dats = [du.DatFile("no-intro", f"{n}.dat", dat(n), n) for n in names]
    return du.match_dats(dats, du.parse_console_tokens(TOKENS), PLATFORMS)


def test_write_dats_writes_mapped_and_report(tmp_path):
    result = du.write_dats(
        tmp_path,
        matches_for("Nintendo - Game Boy", "Nintendo - amiibo"),
        PLATFORMS,
        "Quelle",
        date(2026, 10, 14),
    )
    assert [p.name for p in result.written] == ["Nintendo - Game Boy.dat"]
    assert (tmp_path / "no-intro" / "Nintendo - Game Boy.dat").read_bytes() == dat(
        "Nintendo - Game Boy"
    )
    assert not (tmp_path / "no-intro" / "Nintendo - amiibo.dat").exists()
    assert (result.covered_platforms, result.missing_platforms, result.unmapped_dats) == (1, 4, 1)
    report = result.report_path.read_text()
    assert (
        "Stand 14.10.2026" in report
        and "Nintendo Switch (`switch`)" in report
        and "- Nintendo - amiibo" in report
    )


def test_write_dats_replaces_only_own_files(tmp_path):
    du.write_dats(tmp_path, matches_for("Nintendo - Game Boy"), PLATFORMS, "", date.today())
    own = tmp_path / "eigene.dat"
    own.write_text("meins")
    du.write_dats(tmp_path, matches_for("Nintendo - Game Boy Advance"), PLATFORMS, "", date.today())
    assert not (tmp_path / "no-intro" / "Nintendo - Game Boy.dat").exists()
    assert (tmp_path / "no-intro" / "Nintendo - Game Boy Advance.dat").exists()
    assert own.read_text() == "meins"


def test_manifest_cannot_escape_dats_dir(tmp_path):
    outside = tmp_path / "wichtig.txt"
    outside.write_text("x")
    dats_dir = tmp_path / "dats"
    dats_dir.mkdir()
    (dats_dir / du.MANIFEST_FILENAME).write_text(json.dumps(["../wichtig.txt", "/etc/passwd"]))
    du.write_dats(dats_dir, [], PLATFORMS, "", date.today())
    assert outside.exists()


def test_extract_redump_keeps_source_code():
    [d] = du.extract_redump("x.dat", dat("Sony - PlayStation"), code="psx")
    assert d.source == "psx"


def test_extract_cues_only_cue_files():
    pack = zip_bytes({"A (USA).cue": b"FILE", "sub/B (Europe).cue": b"FILE2", "readme.txt": b"x"})
    assert du.extract_cues(pack) == {"A (USA).cue": b"FILE", "B (Europe).cue": b"FILE2"}


def test_write_dats_writes_cues_per_platform_and_replaces_folder(tmp_path):
    gb = du.DatFile("redump", "gb.dat", dat("Nintendo - Game Boy"), "Nintendo - Game Boy", "gbx")
    amiibo = du.DatFile("redump", "a.dat", dat("Nintendo - amiibo"), "Nintendo - amiibo", "ami")
    matches = du.match_dats([gb, amiibo], du.parse_console_tokens(TOKENS), PLATFORMS)
    stale = tmp_path / du.CUES_DIRNAME / "alt" / "x.cue"
    stale.parent.mkdir(parents=True)
    stale.write_text("alt")
    result = du.write_dats(
        tmp_path,
        matches,
        PLATFORMS,
        "",
        date.today(),
        cue_packs={"gbx": {"Spiel (USA).cue": b"FILE"}, "ami": {"Nein.cue": b"x"}},
    )
    assert result.cue_files == 1
    assert (tmp_path / du.CUES_DIRNAME / "gb" / "Spiel (USA).cue").read_bytes() == b"FILE"
    assert not stale.exists()
    assert not (tmp_path / du.CUES_DIRNAME / "ami").exists()


def test_extract_keys():
    pack = zip_bytes({"Spiel (Europe).key": bytes(16), "liesmich.txt": b"x"})
    assert du.extract_keys(pack) == {"Spiel (Europe).key": bytes(16)}


def test_write_dats_writes_key_packs(tmp_path):
    gb = du.DatFile("redump", "gb.dat", dat("Nintendo - Game Boy"), "Nintendo - Game Boy", "gbx")
    matches = du.match_dats([gb], du.parse_console_tokens(TOKENS), PLATFORMS)
    result = du.write_dats(
        tmp_path, matches, PLATFORMS, "", date.today(), key_packs={"gbx": {"S.key": bytes(16)}}
    )
    assert result.key_files == 1
    assert (tmp_path / du.KEYS_DIRNAME / "gb" / "S.key").read_bytes() == bytes(16)
