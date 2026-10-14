"""Tests für retro_manager.core.romm_api."""

import base64
import json
from urllib.parse import parse_qs

import pytest

from retro_manager.core import romm_api


def test_base_url_is_local():
    assert romm_api.base_url(8080) == "http://127.0.0.1:8080"


def test_parse_heartbeat():
    data = {"SYSTEM": {"VERSION": "5.4.0", "SHOW_SETUP_WIZARD": True}, "OIDC": {}}
    assert romm_api.parse_heartbeat(data) == romm_api.Heartbeat("5.4.0", True)


def test_parse_heartbeat_tolerates_missing_fields():
    assert romm_api.parse_heartbeat({}) == romm_api.Heartbeat("", False)


def test_parse_token():
    data = {"access_token": "a", "refresh_token": "r", "token_type": "bearer", "expires": 900}
    assert romm_api.parse_token(data) == romm_api.Token("a", "r", 900)


def test_parse_token_without_access_token_fails():
    with pytest.raises(KeyError):
        romm_api.parse_token({})


def test_token_form():
    form = parse_qs(romm_api.token_form("admin", "p&w=1").decode())
    assert form["grant_type"] == ["password"]
    assert form["username"] == ["admin"]
    assert form["password"] == ["p&w=1"]
    assert "roms.read" in form["scope"][0].split()


def test_create_admin_body():
    body = json.loads(romm_api.create_admin_body("admin", "pw"))
    assert body == {"username": "admin", "email": "", "password": "pw", "role": "admin"}


def test_basic_auth_header_handles_umlauts():
    header = romm_api.basic_auth_header("jürgen", "pässwort")
    scheme, encoded = header.split(" ")
    assert scheme == "Basic"
    assert base64.b64decode(encoded).decode() == "jürgen:pässwort"


def test_web_login_script_embeds_header_safely():
    script = romm_api.web_login_script('Basic "x"')
    assert json.dumps('Basic "x"') in script
    assert "/api/login" in script
    assert romm_api.CSRF_HEADER in script


def test_error_detail_from_string():
    body = b'{"detail":"Password must be at least 6 characters long"}'
    assert romm_api.error_detail(body) == "Password must be at least 6 characters long"


def test_error_detail_from_validation_list():
    body = json.dumps({"detail": [{"msg": "field required"}, {"msg": "too short"}]}).encode()
    assert romm_api.error_detail(body) == "field required; too short"


@pytest.mark.parametrize("body", [b"", b"<html>", b"[]", b'{"other": 1}'])
def test_error_detail_unreadable_is_empty(body):
    assert romm_api.error_detail(body) == ""


def test_refresh_form():
    form = parse_qs(romm_api.refresh_form("r&1").decode())
    assert form == {"grant_type": ["refresh_token"], "refresh_token": ["r&1"]}
