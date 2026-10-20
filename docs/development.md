# Entwicklung

## Befehle

```bash
uv sync                          # venv anlegen und Abhängigkeiten installieren
uv run python -m retro_manager   # App starten
uv run pytest                    # Tests
uv run ruff check src tests      # Linter (Zeilenlänge 100)
uv run ruff format src tests     # Formatierung
uv add <paket> / uv add --dev <paket> / uv remove <paket>
```

- Abhängigkeiten nur über uv ([ADR 0008](adr/0008-uv-for-dependencies.md)): kein `pip install`, keine `requirements.txt`; `pyproject.toml` ist die einzige Quelle, `uv.lock` wird eingecheckt.
- Befehle immer über `uv run`, nie über ein manuell aktiviertes venv.
- Entwicklungswerkzeuge (pytest, ruff, Testserver, später PyInstaller) in die Dev-Gruppe.

## Tests

- Jede Funktion in `core/` bekommt Unit-Tests in `tests/core/`, ohne Qt.
- Externe Prozesse und Netzwerk mocken; Tests setzen weder Docker noch die HDD voraus. Tests mit echtem chdman/7-Zip nur mit `skipif`, wenn das Programm fehlt.
- Controller-Tests (falls nötig) mit `pytest-qt`.
- Änderungen an Abläufen zusätzlich mit echten Werkzeugen und Testdaten in einem temporären Ordner gegenprüfen, Oberfläche offscreen (`QT_QPA_PLATFORM=offscreen`).

## Voraussetzungen

- Python laut `.python-version` (derzeit 3.14), uv.
- Docker Engine, ohne `sudo` nutzbar (Gruppe `docker` oder rootless) – nur für RomM ([ADR 0004](adr/0004-docker-for-romm.md)).
- Externe Werkzeuge liegen nicht im Repo (`tools/` ist ignoriert, [ADR 0005](adr/0005-external-tools-not-bundled.md)): Igir unter `tools/igir/`, 7-Zip unter `tools/7zip/`, chdman unter `tools/chdman/` oder aus dem PATH. Wo genau gesucht wird: [specs/igir.md](specs/igir.md), [specs/7zip.md](specs/7zip.md), [specs/chdman.md](specs/chdman.md).

## Umgebung des Entwicklers

SteamOS, Entwicklung in einer Distrobox (Arch, mit `--nvidia`); Docker Engine rootless. chdman aus dem Paket `mame-tools`, Igir und 7-Zip von Hand unter `tools/`.
