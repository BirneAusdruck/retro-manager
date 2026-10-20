# Architektur

## Schichten: Model – View – Controller

Die App folgt strikt MVC. Abhängigkeiten zeigen nur in eine Richtung ([ADR 0001](adr/0001-mvc-qt-free-model.md)):

```
View (widgets/)       ──►  Controller (controllers/)  ──►  Model (core/)
        ▲                          │
        └──── Qt-Signale ──────────┘
```

| Schicht | Ordner | Qt? | Verantwortung |
|---|---|---|---|
| Model | `core/` | **nein** | Domänenlogik, Datenklassen, Konfiguration, Befehlsaufbau für externe Tools, Validierung. Mit reinem `pytest` ohne `QApplication` testbar. |
| Controller | `controllers/` | ja | Verbindet View und Model, führt asynchrone Arbeit aus (`QProcess`, `QThreadPool`, `QTimer`, `QNetworkAccessManager`) und meldet Ergebnisse per Signal. Kein Layout, keine Widgets. |
| View | `widgets/` | ja | Darstellung und Eingaben, keine Geschäftslogik. UI vollständig im Code ([ADR 0002](adr/0002-ui-in-code.md)). |
| Item-Models | `widgets/models/` | ja | Qt-Tabellenmodelle als Darstellungsadapter über `core/`-Datenklassen. |

- `core/` importiert niemals PySide6.
- Views rufen Controller-Methoden auf und reagieren auf deren Signale; sie importieren aus `core/` höchstens Datenklassen (z. B. `LibraryGame`) als Typen. Regeln wie „welches Zielformat hat ein System“ fragen sie über den Controller ab.
- Models kennen weder Controller noch Views; sie geben Werte zurück oder werfen Exceptions.
- Controller enthalten keine Layout- oder Widget-Logik, Views keine Geschäftslogik.
- Alle Objekte werden in `app.py` erzeugt und per Konstruktor übergeben – keine globalen Singletons.

### Ablauf am Beispiel einer Tabelle

```
Reiter wird sichtbar → Panel.refresh()                 (View)
  → ChdmanController.library(hdd)                      (Controller)
  → library.scan_platform(roms, slug)                  (Model, liest die HDD)
  ← list[LibraryGame]
  → ChdTableModel.set_games(...)                       (Item-Model)
  → QTableView fragt rowCount()/data() ab
```

Teilaktualisierungen (z. B. Prüfergebnisse) kommen per Signal und lösen nur `dataChanged` für die betroffene Spalte aus.

## Module

### `core/` – Model

| Modul | Aufgabe |
|---|---|
| `config.py` | `AppConfig` (INI-Schema), Pfade relativ zur Programmdatei (`app_dir`, `tools_dir`, `reports_dir`, `webdata_dir`, `compose_dir`) und auf der HDD (`dats_dir`, `exports_dir`, `work_dir`), `is_dev_build` |
| `credentials.py` | Zugriff auf `keyring` (Schlüssel siehe [specs/configuration.md](specs/configuration.md)) |
| `mount_check.py` | Liegt der HDD-Ordner auf einem eingehängten Laufwerk? (`os.path.ismount` bis zur Wurzel) |
| `docker_compose.py` | `.env` schreiben, compose-Befehle als Argumentlisten, Geheimnisse erzeugen |
| `romm_api.py` | Endpunkte, Anfrage-/Antwort-Daten, Anmeldung ([specs/romm-api.md](specs/romm-api.md)) |
| `tools.py` | Pfade und Argumentlisten für Igir, chdman, 7-Zip; `clean_output` für Prozessausgabe |
| `igir_report.py` | Igir-Report (CSV) einlesen und auswerten |
| `dat_update.py` | DAT-Quellen auslesen, RomM-Plattformen zuordnen, nach `<HDD>/dats` schreiben |
| `manifest.py` | JSON-Manifeste (was die App selbst geschrieben hat) und Pfadschutz |
| `progress.py` | Gemeinsame Typen: Fortschritts-Callback, Abbruchprüfung, `ExportError`, `ExportCancelled` |
| `library.py` | **Einzige Ordnersuche** in `roms/<plattform>/` (`scan_entries`, `scan_platform`, `platforms`), Auflösen der Tracks von CUE/GDI ([specs/library.md](specs/library.md)) |
| `archive_names.py` | Archive am Namen erkennen (Endungen, mehrteilige Archive, Formatanzeige) |
| `archives.py` | Entpacken/Packen planen, Entpacktes einsortieren, Originale bestimmen |
| `chd.py` | CHD-Plattformen, Umwandlung planen, CHD-Kopf lesen, chdman-Fortschritt |
| `formats.py` | Zielformat je System (`target_format`) |
| `export.py` | Exportplan (Entpacken, chdman, Kopieren, PS3 entschlüsseln) und Export-Manifest |
| `devices.py` | Zielgeräte-Profile: Plattform → Ordner im Ziel, Pfade auf dem Gerät |
| `ps3_iso.py` | PS3-ISOs mit Redump-Disc-Key entschlüsseln ([specs/ps3-iso.md](specs/ps3-iso.md)) |
| `remote.py` | FTP/FTPS/SFTP hinter der Schnittstelle `RemoteFs`, Up-/Download mit Fortsetzen |
| `connections.py` | Gespeicherte Verbindungen (INI), Passwörter im Schlüsselbund |
| `platforms.py`, `jobs.py` | Platzhalter, noch leer (siehe [roadmap.md](roadmap.md)) |

### `controllers/`

| Modul | Aufgabe |
|---|---|
| `startup_controller.py` | Gesamter Startablauf ([features/start.md](features/start.md)) |
| `docker_controller.py` | `docker compose up -d` / `stop` per `QProcess` |
| `romm_controller.py` | Heartbeat-Abfrage, Admin anlegen, Anmeldung, Token-Erneuerung, unterstützte Plattformen |
| `settings_controller.py` | Laden/Speichern über `core.config` und `core.credentials`; Signal `changed` |
| `igir_controller.py` | Igir per `QProcess`, Ausgabe zeilenweise, Report |
| `dat_controller.py` | „DATs aktualisieren“: Downloads per `QNetworkAccessManager`, Schreiben im Thread-Pool |
| `chdman_controller.py` | chdman-Reiter: Warteschlange, ein Vorgang nach dem anderen |
| `archive_controller.py` | Archive-Reiter: Warteschlange mit bis zu `max_parallel_jobs` gleichzeitigen Jobs |
| `export_controller.py` | Aufbereiten für ein Zielgerät, Senden an die FTP-Warteschlange |
| `transfer_controller.py` | Verbindungen, Durchsuchen, Übertragungs-Warteschlange |
| `activity_controller.py` | Sammelt alle Hintergrundvorgänge für die Aktivitätsanzeige |
| `background_task.py` | `BackgroundTask`: `QRunnable` mit Fortschritt, Abbruch und Ergebnis per Signal |
| `job_controller.py` | Platzhalter (`QThreadPool` mit einstellbarer Größe), noch ungenutzt |

### `widgets/`

`main_window.py` (Kopfzeile: Logo links, Reiter `#toolTabs`, Aktivitätsanzeige rechts; darunter ein `QStackedWidget` mit den Arbeitsflächen), je Reiter ein Panel (`igir_panel`, `chdman_panel`, `archive_panel`, `export_panel`, `ftp_panel`, `settings_panel`, `romm_view`), Dialoge (`setup_dialog`, `connection_dialog`, `error_dialog`), Startbilder (`splash_screen`, `loading_screen`), wiederverwendbare Bausteine (`path_picker`, `info_label`, `activity_indicator`, `images`).

Reiter in dieser Reihenfolge: **RomM · Igir · chdman · Archive · Export vorbereiten · FTP · Einstellungen**.

`widgets/models/`: `game_table_model.GameTableModel` ist die gemeinsame Basis für alle Spielelisten (Auswahlkästchen, System, Spiel, Format, Größe, Status). Unterklassen passen Statusspalte, Formattext, gesperrte Zeilen und über `columns()` zusätzliche Spalten an: `export_table_model`, `chd_table_model`, `archive_table_model`. Daneben `report_table_model` (Igir), `remote_model` und `transfer_model` (FTP).

## Nebenläufigkeit

- **Nichts Blockierendes im UI-Thread:** kein `QProcess.execute()`, kein `subprocess.run()`, kein `time.sleep()`.
- **Externe Programme** (Igir, chdman, 7-Zip, Docker) laufen als `QProcess`; die Argumentlisten kommen aus `core/tools.py` bzw. `core/docker_compose.py`. Ausgabe wird stückweise gelesen, Fortschritt geparst (`chd.parse_progress`, `archives.parse_progress`).
- **Python-Arbeit** (Entpacken mit py7zr/zipfile, Kopieren, Entschlüsseln, Dateien verschieben) läuft als `BackgroundTask` im globalen `QThreadPool` und ruft reine Funktionen aus `core/` auf. Abbruch über ein `threading.Event`, das die Funktionen regelmäßig prüfen.
- **Warteschlangen:** chdman und Export arbeiten eine Liste nacheinander ab. Der Archive-Reiter startet je Eintrag einen eigenen Job (eigener 7-Zip-Prozess, eigener Arbeitsordner) und hält bis zu `max_parallel_jobs` (INI `[jobs] max_parallel`) gleichzeitig. Der nächste Schritt wird über `QTimer.singleShot(0, …)` angestoßen, damit viele schnell scheiternde Einträge keine Rekursion erzeugen.
- Signale für große Zahlen (Bytes über 2 GB) nutzen `Signal(object, object)` statt `int`.
- `shiboken6.isValid` schützt vor Rückrufen auf bereits gelöschte `QProcess`-Objekte beim Beenden.

## Dateien und Bibliothek

- Bibliotheksstruktur ist RomM-Struktur A für alle Werkzeuge ([ADR 0003](adr/0003-romm-as-core.md)); gelesen wird die Bibliothek nur über `library.scan_entries` ([ADR 0010](adr/0010-single-library-scan.md), Einzelheiten in [specs/library.md](specs/library.md)).
- **Arbeitsordner:** Zwischenstände (entpackte Archive, halbfertige CHDs/Archive als `*.part`) liegen in `<HDD>/.retro-manager-tmp/` – auf demselben Laufwerk wie die Bibliothek, damit fertige Dateien nur umbenannt werden. Ausnahme bisher (bekanntes Problem): Der Export entpackt PS3-Archive nach `exports/<profil>/PS3ISO/.entpacken/` (`export.PS3_UNPACK_DIRNAME`).
- Erst geprüfte Ergebnisse kommen in die Bibliothek; bei Abbruch oder Fehler wird der Arbeitsordner gelöscht, das Original bleibt.
- Vorhandene Dateien werden nie überschrieben. Originale werden nur nach Erfolg und nur auf ausdrücklichen Wunsch gelöscht.

## Konfiguration und Geheimnisse

- **Passwörter und API-Schlüssel nur im Systemschlüsselbund**, nie in INI, Logs oder dem Repo. `docker/.env` ist erzeugt und ignoriert. INI-Abschnitte, Schlüsselbund-Einträge und `.env`: [specs/configuration.md](specs/configuration.md).
- Plattformabhängiges (Programmnamen, Docker-Aufruf) ist an genau einer Stelle gekapselt (`core/tools.py`, `core/docker_compose.py`), damit der Windows-Port lokal bleibt.

## Oberfläche

Vollständig im Code ([ADR 0002](adr/0002-ui-in-code.md)):

- Keine `.ui`-Dateien, kein Qt Designer, kein `pyside6-uic`.
- Jedes Widget baut sich in `_build_ui()` im Konstruktor auf und verbindet Signale in `_connect_signals()`. Layouts statt fester Positionen.
- Wiederverwendbare Bausteine als eigene Klassen statt Duplikaten (`PathPicker`, `InfoLabel`, `GameTableModel` …).
- Styling nur in `resources/style.qss`, Ansprache per `setObjectName` / `#objektname`; keine verstreuten `setStyleSheet()`.
- Sichtbare Texte in `self.tr()`. Qt-eigene Texte (Dateidialoge, Ja/Nein) kommen aus `qtbase_<sprache>.qm` von PySide6 (`app.load_qt_translations`).
- Ressourcen (`resources/style.qss`, `resources/icons/` mit App-Symbol, Logo, Startbild als SVG) über `importlib.resources`, damit sie auch im PyInstaller-Build gefunden werden.
- Info-Symbole (`InfoLabel`) stehen links vor der Beschriftung.

## Code-Konventionen

- Typannotationen überall, `@dataclass` für Domänenobjekte, `pathlib.Path` statt Zeichenketten für Pfade, `logging` statt `print`.
- Code, Kommentare und UI-Texte auf Deutsch, im Stil des umgebenden Codes.

## Packaging (geplant)

Offene Schritte: Thema „Packaging und Plattformen“ in der [Roadmap](roadmap.md#themen) bzw. in GitHub-Issues; hier die Grundsätze:

- PyInstaller `--onedir` über `uv run pyinstaller <spec-datei>` (schnellerer Start als `--onefile`, LGPL-Einhaltung für PySide6 einfacher); Linux als AppImage, Windows als Ordner/ZIP. Alternative: Nuitka.
- INI, `tools/`, `reports/` und `webdata/` liegen neben der Programmdatei (`config.app_dir()`; im AppImage der Ordner der `.AppImage`-Datei).
- Externe Tools werden weder ins Repo noch ins Paket aufgenommen, sondern bei Bedarf heruntergeladen ([ADR 0005](adr/0005-external-tools-not-bundled.md)). Docker wird nicht mitgeliefert; keine Dockerfile für die Qt-App ([ADR 0004](adr/0004-docker-for-romm.md)).
- Lizenztexte aller Komponenten beilegen: PySide6 (LGPL), Igir und chdman/MAME (GPL), 7-Zip (LGPL mit unRAR-Einschränkung, `tools/7zip/License.txt`), RomM (Lizenz der Version prüfen).
