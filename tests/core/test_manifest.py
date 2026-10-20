"""Tests für retro_manager.core.manifest."""

import pytest

from retro_manager.core import manifest


@pytest.mark.parametrize(
    ("entry", "safe"),
    [
        ("no-intro/a.dat", True),
        ("PSXISO/Spiel (USA)/Spiel.cue", True),
        ("../x", False),
        ("a/../../x", False),
        ("/etc/passwd", False),
        ("a\\..\\x", False),
        ("", False),
        (42, False),
    ],
)
def test_is_safe_relative(entry, safe):
    assert manifest.is_safe_relative(entry) is safe


def test_read_write_roundtrip(tmp_path):
    path = tmp_path / "sub" / "m.json"
    manifest.write_json(path, {"games": {"ä": [1]}})
    assert manifest.read_json(path, None) == {"games": {"ä": [1]}}


def test_read_missing_or_broken_gives_default(tmp_path):
    assert manifest.read_json(tmp_path / "fehlt.json", []) == []
    broken = tmp_path / "kaputt.json"
    broken.write_text("{")
    assert manifest.read_json(broken, {}) == {}
