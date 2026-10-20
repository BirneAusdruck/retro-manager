# Roadmap

Stand: 2026-10-20

Grobe Übersicht: was steht, was noch real getestet werden muss und welche Themen anstehen – ein Satz je Punkt. Wie ein Thema umgesetzt wird (Aufgaben, Varianten, Akzeptanzkriterien), steht in GitHub-Issues und Sub-Issues, nicht hier.

## Umgesetzt

- **Start:** Einrichtung, Docker- und HDD-Prüfung, Start und Anmeldung bei RomM → [features/start.md](features/start.md)
- **RomM** in Docker mit eingebetteter Weboberfläche → [features/romm.md](features/romm.md)
- **Igir:** Prüfen mit Report → [features/igir.md](features/igir.md)
- **DATs aktualisieren:** No-Intro, Redump, CUEs, PS3-Keys → [features/dats.md](features/dats.md)
- **chdman:** umwandeln, zurückwandeln, prüfen → [features/chdman.md](features/chdman.md)
- **Archive:** entpacken, packen, prüfen, parallele Jobs → [features/archive.md](features/archive.md)
- **Export vorbereiten:** Profil PS3 (CFW + webMAN MOD) → [features/export.md](features/export.md)
- **FTP:** Dateimanager und Warteschlange (FTP/FTPS/SFTP) → [features/ftp.md](features/ftp.md)
- **Aktivitätsanzeige** im Banner → [features/activity.md](features/activity.md)
- **Einstellungen:** nur Platzhalter → [features/settings.md](features/settings.md)

## Noch nicht real getestet

- Export: CHD zurückwandeln mit chdman
- Übertragung an die echte PS3
- PS3-Entschlüsselung mit einer echten ISO
- Download der Redump-Disc-Keys
- chdman mit echten Redump-Dumps der Sammlung
- Archive: echte RAR-Archive

## Themen

- **Bibliothek aufräumen:** über RomM hochgeladene Dateien prüfen, nach DAT benennen und ins Zielformat bringen, gesteuert aus dem Reiter „Einstellungen“.
- **Nach DAT benennen:** in den Reitern chdman und Igir.
- **Werkzeug-Downloads:** Igir, chdman und 7-Zip per Knopf laden ([ADR 0005](adr/0005-external-tools-not-bundled.md)).
- **Weitere Zielformate:** RVZ (GameCube/Wii) und NSZ (Switch).
- **chdman:** parallele Jobs wie im Archive-Reiter.
- **Archive:** weitere Quellen außer der Bibliothek.
- **Bibliothek:** `.bin` ohne CUE, zentrale Plattformzuordnung, Platzhalter `core/jobs.py` / `JobController` klären.
- **Export und Übertragung:** weitere Zielgeräte (PS2, Xbox 360), angeschlossene Laufwerke, Aufbereiten und Senden in einem Schritt.
- **Einstellungen:** Metadaten-Zugänge, Werkzeug-Downloads und parallele Jobs an einem Ort.
- **Packaging und Plattformen:** PyInstaller/AppImage, Windows-Port, später Podman ([ADR 0004](adr/0004-docker-for-romm.md)).

## Bekannte Probleme

- Große Uploads über die RomM-Oberfläche kommen nur teilweise an ([specs/romm-api.md](specs/romm-api.md#hinweise)).
- Der Export entpackt PS3-Archive außerhalb des Arbeitsordners ([architecture.md](architecture.md#dateien-und-bibliothek)).
- Projektbeschreibung in `pyproject.toml` und `README.md` fehlen noch.
