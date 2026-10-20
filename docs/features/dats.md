# DATs aktualisieren (Knopf im Reiter „Igir“)

Der Knopf **DATs aktualisieren** lädt die aktuellen DATs von No-Intro und Redump, behält nur die, die zu einer von RomM unterstützten Plattform passen, und legt sie in `<HDD>/dats/` ab. Dazu kommen korrekte Redump-CUEs (für die Prüfung von Disc-Spielen im [Igir-Reiter](igir.md)) und Redump-Disc-Keys (für PS3-Exporte, [features/export.md](export.md)).

Verwandte Docs: [specs/dat-sources.md](../specs/dat-sources.md) · [specs/igir.md](../specs/igir.md#plattform-tokens) · [specs/romm-api.md](../specs/romm-api.md) · [features/igir.md](igir.md)

## Bedienung

- **DATs aktualisieren** startet den Lauf. Voraussetzung: ein eingerichteter HDD-Ordner (sonst Meldung „Es ist noch kein HDD-Ordner eingerichtet.“) und eine Anmeldung der App bei RomM.
- Beim Start wird das Protokoll geleert; jeder Schritt erscheint dort als Zeile (z. B. „RomM kennt 120 Plattformen.“, „Redump: 3 Disc-Keys für …“).
- Der Balken zeigt beim Laden der Redump-DATs „erledigt / gesamt“, beim Zuordnen und Schreiben läuft er ohne Prozentangabe.
- Danach steht über der Tabelle eine Zusammenfassung: Anzahl geschriebener DATs, abgedeckte RomM-Plattformen, CUE-Dateien, Disc-Keys, RomM-Plattformen ohne DAT, DATs ohne Plattform und der Pfad zu `ABGLEICH.md`. Ist das Feld **DAT-Ordner** leer, wird `<HDD>/dats` eingetragen.
- **Abbrechen** (gemeinsamer Knopf mit der Igir-Prüfung) bricht die Downloads ab. Sperren der Knöpfe während des Laufs: [features/igir.md](igir.md#bedienung).
- Der Lauf erscheint in der [Aktivitätsanzeige](activity.md) („DATs aktualisieren“, Detail = letzte Protokollzeile).

## Aufbau

`DatController` arbeitet die Downloads als Kette von Antwort-Handlern nacheinander ab und meldet Zustand, Protokoll, Fortschritt und Ergebnis per Qt-Signal an `IgirPanel` und `ActivityController` (Observer). Auslesen, Zuordnen und Schreiben sind reine Funktionen in `core/dat_update.py`; das Schreiben läuft in `_WriteTask` (eigenes `QRunnable`) im globalen `QThreadPool`.

| Schicht | Datei | Rolle |
|---|---|---|
| View | `widgets/igir_panel.py` | `IgirPanel`: Knopf, Protokoll, Balken, Zusammenfassung (`_start_dat_update`, `_on_dats_updated`) |
| Controller | `controllers/dat_controller.py` | `DatController`: Ablauf, Downloads per `QNetworkAccessManager`, 1 s Pause per `QTimer`; `_WriteTask` im Thread-Pool |
| Controller | `controllers/romm_controller.py` | `RommController.fetch_supported_platforms` → `supported_platforms_ready` / `request_failed` |
| Controller | `controllers/settings_controller.py` | `dats_dir()` aus `[archive] hdd_path` |
| Model | `core/dat_update.py` | Adressen, Seiten auslesen, Pakete entpacken, `match_dats`, `write_dats`, `render_report`, Datenklassen |
| Model | `core/manifest.py` | `read_json`, `is_safe_relative` |

```mermaid
classDiagram
    class IgirPanel {
        <<View>>
        -_start_dat_update()
        -_on_dat_progress(done, total)
        -_on_dats_updated(result)
    }
    class SettingsController {
        <<Controller>>
        +dats_dir() Path
    }
    class DatController {
        <<Controller>>
        +update(dats_dir)
        +cancel()
        +is_running() bool
        running_changed(bool)
        status(str)
        progress(int, int)
        finished(object)
        failed(str)
    }
    class RommController {
        <<Controller>>
        +fetch_supported_platforms()
        supported_platforms_ready(object)
        request_failed(str)
    }
    class _WriteTask {
        <<Controller>>
        +run()
    }
    class dat_update {
        <<Model>>
        +parse_romm_platforms(data) list~RommPlatform~
        +parse_console_tokens(text) list~ConsoleRule~
        +parse_redump_systems(page) list~RedumpSystem~
        +extract_nointro(pack) list~DatFile~
        +extract_redump(filename, payload, code) list~DatFile~
        +match_dats(dats, rules, platforms) list~DatMatch~
        +write_dats(dats_dir, matches, platforms, sources, today) DatUpdateResult
    }
    class manifest {
        <<Model>>
        +read_json(path, default)
        +is_safe_relative(entry) bool
    }
    class DatUpdateResult {
        <<Model>>
        +list~Path~ written
        +int covered_platforms
        +int missing_platforms
        +int unmapped_dats
        +Path report_path
        +int cue_files
        +int key_files
    }
    IgirPanel --> DatController : ruft auf
    IgirPanel --> SettingsController : ruft auf
    DatController ..> IgirPanel : Signale
    DatController --> RommController : ruft auf
    RommController ..> DatController : Signale
    DatController --> _WriteTask : startet
    DatController --> dat_update : nutzt
    _WriteTask --> dat_update : nutzt
    dat_update --> manifest : nutzt
    dat_update --> DatUpdateResult : erzeugt
    note for DatController "Observer: Signale an IgirPanel und ActivityController"
```

## Ablauf

```mermaid
sequenceDiagram
    actor Nutzer
    participant V as IgirPanel
    participant C as DatController
    participant R as RommController
    participant N as QNetworkAccessManager
    participant T as _WriteTask
    participant M as core.dat_update

    Nutzer->>V: DATs aktualisieren
    V->>C: update(dats_dir)
    C--)V: running_changed(True)
    C->>R: fetch_supported_platforms()
    R--)C: supported_platforms_ready(data)
    C-)N: GET consoleTokens.json (Igir-Version)
    C-)N: DAT-o-MATIC (Seite, Formular, Download-Knopf)
    N--)C: No-Intro-Paket (ZIP)
    C-)N: GET redump.org/downloads/
    loop je Redump-System, 1 s Pause
        C-)N: GET datfile
        C--)V: progress(erledigt, gesamt)
        opt System passt zu RomM und hat CUEs bzw. Keys
            C-)N: GET cues bzw. keys
        end
    end
    C-)T: start (Thread-Pool)
    T->>M: extract_nointro, match_dats, write_dats
    alt Erfolg
        T--)C: done(DatUpdateResult)
        C--)V: running_changed(False), finished(result)
    else Abbruch, Netzwerk- oder Schreibfehler
        C--)V: running_changed(False), failed(meldung)
    end
```

Alle Zwischenstationen melden sich zusätzlich per `status(text)` im Protokoll. Adressen, Formular-Ablauf bei DAT-o-MATIC, Zeitlimit und Pause: [specs/dat-sources.md](../specs/dat-sources.md). RomM-Anfrage samt Token-Erneuerung: [specs/romm-api.md](../specs/romm-api.md).

Heruntergeladenes bleibt bis zum Schreiben im Speicher; vorher wird nichts unter `dats/` verändert. CUEs und Keys werden nur für Redump-Systeme geladen, deren DAT einer RomM-Plattform zugeordnet wurde.

## Zuordnung DAT → RomM-Plattform

`dat_update.match_dats` prüft je DAT (über den `<header><name>` der DAT) in dieser Reihenfolge; der erste Treffer gilt, die Art steht in `ABGLEICH.md`:

1. **`igir`:** Igirs Regeln aus `consoleTokens.json` – wie Igir gewinnt der **letzte** passende `datNameRegex` ([specs/igir.md](../specs/igir.md#plattform-tokens)). Nur wenn dessen `{romm}`-Token ein Slug ist, den RomM liefert.
2. **`manuell`:** feste Zuordnungen in `dat_update.MANUAL_MAPPINGS` für Systeme, für die Igir keinen RomM-Ordner kennt.
3. **`name`:** RomM-Plattformname im Systemteil des DAT-Namens (Text nach dem ersten „ - “, ohne „Parent Clone“, „BIOS“, „Datfile“); längere Namen zuerst, nur Namen ab 4 Zeichen. Bekannte Fehltreffer stehen in `dat_update.WRONG_NAME_MATCHES` („Capcom - Play System III“, „Naomi Satellite Terminal“).

DATs ohne Treffer werden nicht geschrieben.

## Dateien und Ablage

```
<HDD>/dats/
├── no-intro/                  # inkl. Unterordner Non-Redump/, Unofficial/
├── redump/                    # inkl. BIOS-DATs
├── redump-cues/<plattform>/   # gehört komplett der App, wird je Lauf ersetzt
├── redump-keys/<plattform>/   # gehört komplett der App, wird je Lauf ersetzt
├── ABGLEICH.md                # Abgleich mit RomM, wird je Lauf neu geschrieben
└── .retro-manager-dats.json   # Manifest der von der App geschriebenen DATs
```

- `<plattform>` ist der RomM-Slug (`fs_slug`), also der Ordnername unter `roms/` ([specs/library.md](../specs/library.md)). Die PS3-Keys liegen damit in `redump-keys/ps3/`.
- **Manifest:** JSON-Liste der relativen Pfade aller geschriebenen DATs. Zu Beginn des Schreibens löscht die App nur die darin aufgeführten Dateien (unsichere Einträge werden übergangen, `manifest.is_safe_relative`); **eigene DATs des Nutzers bleiben unberührt**. CUEs und Keys stehen nicht im Manifest, ihre Ordner werden vollständig gelöscht und neu angelegt.
- `ABGLEICH.md` hat drei Teile: je RomM-Plattform (`roms/<slug>`) die zugeordneten DATs mit Ordner und Art der Zuordnung; DATs ohne RomM-Plattform (nicht kopiert); RomM-Plattformen ohne DAT, gruppiert nach Kategorie. Kopf mit Datum und Quellenhinweis (`dat_controller.SOURCES_TEXT`, u. a. dass es für Nintendo Switch keine DAT gibt).
- Kein Arbeitsordner: Die Pakete werden im Speicher entpackt ([specs/dat-sources.md](../specs/dat-sources.md#entpacken-der-pakete)) und direkt nach `dats/` geschrieben.

## Konfiguration

Keine eigenen INI-Schlüssel. Zielordner ist `<[archive] hdd_path>/dats` (`config.dats_dir`, [specs/configuration.md](../specs/configuration.md)); die Version von `consoleTokens.json` folgt `tools.IGIR_VERSION`.

## Fehler und Abbruch

- **Abbruch des ganzen Laufs** mit Meldung unter den Knöpfen, wenn RomM nicht antwortet bzw. die App nicht angemeldet ist, wenn `consoleTokens.json`, eine DAT-o-MATIC-Seite oder die Redump-Systemliste nicht mit HTTP 200 kommt oder nicht auswertbar ist, wenn das No-Intro-Paket kein ZIP ist, bei Netzwerkfehlern (kein HTTP-Status) und wenn Redump keine Systeme liefert. `dats/` bleibt dann unverändert.
- **Einzelne Redump-DATs, CUE- oder Key-Pakete**, die fehlen oder beschädigt sind, werden nur im Protokoll vermerkt; der Lauf geht weiter.
- **Abbrechen** stoppt Pause-Timer und laufenden Download (`DatController.cancel`) und beendet den Lauf mit einer Meldung. Hat das Schreiben schon begonnen, wird es nicht mehr abgebrochen und läuft zu Ende.
- **Schreibfehler** (`OSError`, beschädigtes ZIP) melden „Schreiben fehlgeschlagen: …“; was bis dahin geschrieben bzw. gelöscht wurde, bleibt so.

## Status

- **Real getestet:** 265 DATs und 26 425 CUEs geladen und zugeordnet.
- **Noch offen:** siehe [Roadmap](../roadmap.md#noch-nicht-real-getestet).
