"""Tests für retro_manager.core.credentials (keyring gemockt)."""

import pytest

from retro_manager.core import credentials


@pytest.fixture
def fake_keyring(monkeypatch):
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(credentials.keyring, "get_password", lambda s, k: store.get((s, k)))
    monkeypatch.setattr(
        credentials.keyring, "set_password", lambda s, k, v: store.__setitem__((s, k), v)
    )
    return store


def test_missing_secret_is_none(fake_keyring):
    assert credentials.get_secret(credentials.ROMM_PASSWORD) is None


def test_set_then_get_secret(fake_keyring):
    credentials.set_secret(credentials.DB_PASSWORD, "geheim")
    assert credentials.get_secret(credentials.DB_PASSWORD) == "geheim"
    assert fake_keyring == {(credentials.SERVICE, credentials.DB_PASSWORD): "geheim"}


def test_keyring_errors_become_credentials_error(monkeypatch):
    def broken(*args):
        raise credentials.KeyringError("kein Backend")

    monkeypatch.setattr(credentials.keyring, "get_password", broken)
    monkeypatch.setattr(credentials.keyring, "set_password", broken)
    with pytest.raises(credentials.CredentialsError):
        credentials.get_secret(credentials.ROMM_PASSWORD)
    with pytest.raises(credentials.CredentialsError):
        credentials.set_secret(credentials.ROMM_PASSWORD, "x")
