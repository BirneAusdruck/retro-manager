"""Tests für retro_manager.core.connections."""

from retro_manager.core import connections as conns


def test_new_connection_uses_protocol_default_port():
    assert conns.new_connection("NAS", "sftp", "nas.local").port == 22
    assert conns.new_connection("PS3").port == 21


def test_save_and_load_roundtrip_keeps_other_sections(tmp_path):
    path = tmp_path / "retro-manager.ini"
    path.write_text("[romm]\nuser = admin\n", encoding="utf-8")
    a = conns.Connection("a1", "PS3 Wohnzimmer", "ftp", "192.168.1.50", 21, "", "/dev_hdd0")
    b = conns.Connection("b2", "NAS", "sftp", "nas.local", 2222, "deck", "/volume1")
    conns.save_connections(path, [b, a])
    assert conns.load_connections(path) == [b, a]  # nach Name sortiert
    assert "[romm]" in path.read_text(encoding="utf-8")
    conns.save_connections(path, [a])  # gelöschte Verbindung verschwindet
    assert conns.load_connections(path) == [a]


def test_load_skips_unknown_protocols(tmp_path):
    path = tmp_path / "x.ini"
    path.write_text("[connection:z]\nname = Alt\nprotocol = gopher\n", encoding="utf-8")
    assert conns.load_connections(path) == []


def test_secret_key_and_known_hosts(tmp_path):
    assert conns.Connection("ab", "X").secret_key == "connection:ab"
    assert conns.known_hosts_path(tmp_path) == tmp_path / "known_hosts"


def test_migrate_ps3_target_once():
    migrated = conns.migrate_ps3_target([], "192.168.1.50", 21)
    assert [(c.name, c.host, c.port, c.start_dir) for c in migrated] == [
        ("PS3", "192.168.1.50", 21, "/dev_hdd0")
    ]
    assert conns.migrate_ps3_target(migrated, "192.168.1.50", 21) == migrated
    assert conns.migrate_ps3_target([], "", 21) == []
