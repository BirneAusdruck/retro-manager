# Dokumentation

Retro Manager ist eine Desktop-App (Python, PySide6) zur Verwaltung einer Retro- und Konsolenspielesammlung auf einer externen Archiv-HDD. RomM ist das Herzstück; Igir, chdman und 7-Zip sind als Werkzeuge in eigenen Reitern eingebunden.

**Ziel:** Das Archiv (`<HDD>/roms`) speichert jedes Spiel einmal, sauber benannt und platzsparend (Disc-Spiele als CHD, wo Emulatoren es lesen). Für echte Hardware leitet die App daraus Exporte im Format des Zielgeräts ab und überträgt sie per FTP. Erstes Zielgerät ist die PS3 mit CFW + webMAN MOD.

## Wo steht was?

| Datei | Inhalt |
|---|---|
| [architecture.md](architecture.md) | MVC-Schichten, Module, Nebenläufigkeit, Dateien, Geheimnisse, Oberfläche, Code-Konventionen, Packaging |
| [development.md](development.md) | Befehle, Tests, Voraussetzungen, Entwicklungsumgebung |
| [roadmap.md](roadmap.md) | Grobe Übersicht: Umgesetztes, noch nicht real Getestetes, anstehende Themen, bekannte Probleme |
| **features/** | Ein Dokument je Reiter bzw. Funktion – was sie tut und wie sie abläuft |
| [features/start.md](features/start.md) | Startablauf, Einrichtungsdialog, Fehlerdialog |
| [features/romm.md](features/romm.md) | RomM in Docker, eingebettete Weboberfläche |
| [features/igir.md](features/igir.md) | ROMs gegen DATs prüfen, Report |
| [features/dats.md](features/dats.md) | „DATs aktualisieren“: No-Intro, Redump, CUEs, PS3-Keys |
| [features/chdman.md](features/chdman.md) | Discs in CHD umwandeln, zurückwandeln, prüfen |
| [features/archive.md](features/archive.md) | Archive entpacken, packen, prüfen (7-Zip), parallele Jobs |
| [features/export.md](features/export.md) | „Export vorbereiten“ für echte Hardware, Profil PS3 |
| [features/ftp.md](features/ftp.md) | Dateimanager und Übertragungs-Warteschlange (FTP/FTPS/SFTP) |
| [features/activity.md](features/activity.md) | Aktivitätsanzeige im Banner |
| [features/settings.md](features/settings.md) | Reiter „Einstellungen“ (Platzhalter) |
| **specs/** | Regeln und Schnittstellen, an die sich der Code hält |
| [specs/library.md](specs/library.md) | Ordnerstruktur auf der HDD (RomM-Struktur A), Archivformat je System, Einträge lesen |
| [specs/configuration.md](specs/configuration.md) | INI-Abschnitte, Schlüsselbund-Einträge, `docker/.env` |
| [specs/romm-api.md](specs/romm-api.md) | Genutzte RomM-Endpunkte und Anmeldung |
| [specs/igir.md](specs/igir.md) | Igir-Aufrufe, Report-Format, Plattform-Tokens |
| [specs/chdman.md](specs/chdman.md) | chdman-Befehle, CHD-Kopf, Fortschrittsausgabe |
| [specs/7zip.md](specs/7zip.md) | 7-Zip-Befehle, Archivnamen, Fortschrittsausgabe |
| [specs/dat-sources.md](specs/dat-sources.md) | DAT-o-MATIC, Redump: Adressen und Abläufe |
| [specs/ps3-iso.md](specs/ps3-iso.md) | Entschlüsseln von PS3-ISOs mit Redump-Disc-Key |
| **adr/** | Architekturentscheidungen mit Begründung ([Übersicht](adr/README.md)) |

## Docs pflegen

Jede Information steht genau an einer Stelle; andere Dateien verlinken dorthin.

| Was | Wohin |
|---|---|
| Verhalten eines Reiters bzw. einer Funktion | `features/<name>.md` |
| Regeln, Formate, Schnittstellen externer Programme und Dienste | `specs/<name>.md` |
| Code-Regeln, neue Module | `architecture.md` |
| Befehle, Tests, Voraussetzungen | `development.md` |
| Erledigtes, noch nicht real Getestetes, anstehende Themen, bekannte Probleme – je ein Satz | `roadmap.md` |
| Wie ein Thema umgesetzt wird (Aufgaben, Varianten, Akzeptanzkriterien) | GitHub-Issues und Sub-Issues |
| Neue Grundsatzentscheidung | neue ADR in `adr/` |

Datei- und Ordnernamen englisch (kebab-case), Inhalte deutsch.
