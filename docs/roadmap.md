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

Abarbeitung: [#77](https://github.com/BirneAusdruck/retro-manager/issues/77).

- Export: CHD zurückwandeln mit chdman
- Übertragung an die echte PS3
- PS3-Entschlüsselung mit einer echten ISO
- Download der Redump-Disc-Keys
- chdman mit echten Redump-Dumps der Sammlung
- Archive: echte RAR-Archive
- RomM: automatische Anmeldung der Oberfläche (erster Start, gespeicherte Sitzung) und Verhalten nach Abmelden
- Igir: Abbrechen während Prüfung bzw. „DATs aktualisieren“
- FTP-Reiter selbst (Durchsuchen, Hoch- und Herunterladen, Löschen)

## Themen

- **Bibliothek aufräumen:** über RomM hochgeladene Dateien prüfen, nach DAT benennen und ins Zielformat bringen, gesteuert aus dem Reiter „Einstellungen“ ([#55](https://github.com/BirneAusdruck/retro-manager/issues/55)).
- **Nach DAT benennen:** in den Reitern chdman und Igir ([#56](https://github.com/BirneAusdruck/retro-manager/issues/56)).
- **Werkzeug-Downloads:** Igir, chdman und 7-Zip per Knopf laden ([ADR 0005](adr/0005-external-tools-not-bundled.md), [#57](https://github.com/BirneAusdruck/retro-manager/issues/57)).
- **Weitere Zielformate:** RVZ (GameCube/Wii) und NSZ (Switch) ([#58](https://github.com/BirneAusdruck/retro-manager/issues/58)).
- **chdman:** parallele Jobs wie im Archive-Reiter ([#65](https://github.com/BirneAusdruck/retro-manager/issues/65)).
- **Archive:** weitere Quellen außer der Bibliothek, CHDs aus Archiven an chdman weitergeben, nach dem Zurückwandeln packen ([#66](https://github.com/BirneAusdruck/retro-manager/issues/66), [#67](https://github.com/BirneAusdruck/retro-manager/issues/67), [#68](https://github.com/BirneAusdruck/retro-manager/issues/68)).
- **Bibliothek:** `.bin` ohne CUE, zentrale Plattformzuordnung, Platzhalter `core/jobs.py` / `JobController` klären ([#69](https://github.com/BirneAusdruck/retro-manager/issues/69), [#78](https://github.com/BirneAusdruck/retro-manager/issues/78), [#79](https://github.com/BirneAusdruck/retro-manager/issues/79)).
- **Export und Übertragung:** weitere Zielgeräte (PS2, Xbox 360), angeschlossene Laufwerke, Aufbereiten und Senden parallel (jede fertig geprüfte Disc einzeln sendbar) ([#59](https://github.com/BirneAusdruck/retro-manager/issues/59), [#60](https://github.com/BirneAusdruck/retro-manager/issues/60), [#61](https://github.com/BirneAusdruck/retro-manager/issues/61), [#34](https://github.com/BirneAusdruck/retro-manager/issues/34), [#70](https://github.com/BirneAusdruck/retro-manager/issues/70)).
- **Einstellungen:** Metadaten-Zugänge, Werkzeug-Downloads und parallele Jobs an einem Ort ([#62](https://github.com/BirneAusdruck/retro-manager/issues/62), [#71](https://github.com/BirneAusdruck/retro-manager/issues/71)).
- **Packaging und Plattformen:** PyInstaller/AppImage, Windows-Port, später Podman ([ADR 0004](adr/0004-docker-for-romm.md), [#72](https://github.com/BirneAusdruck/retro-manager/issues/72), [#73](https://github.com/BirneAusdruck/retro-manager/issues/73), [#74](https://github.com/BirneAusdruck/retro-manager/issues/74), [#63](https://github.com/BirneAusdruck/retro-manager/issues/63), [#64](https://github.com/BirneAusdruck/retro-manager/issues/64), [#75](https://github.com/BirneAusdruck/retro-manager/issues/75)).

## Bekannte Probleme

Einzelne Fehler stehen als GitHub-Issues (Label `bug`); hier nur Übergreifendes.

- Große Uploads über die RomM-Oberfläche kommen nur teilweise an ([specs/romm-api.md](specs/romm-api.md#hinweise), [#81](https://github.com/BirneAusdruck/retro-manager/issues/81)).
- Der Export entpackt PS3-Archive außerhalb des Arbeitsordners ([architecture.md](architecture.md#dateien-und-bibliothek), [#80](https://github.com/BirneAusdruck/retro-manager/issues/80)).
- Projektbeschreibung in `pyproject.toml` und `README.md` fehlen noch ([#76](https://github.com/BirneAusdruck/retro-manager/issues/76)).
