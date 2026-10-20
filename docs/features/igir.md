# Igir (Reiter „Igir“)

[Igir](https://github.com/emmercm/igir) gleicht ROM-Dateien per Hash mit DATs ab. In der ersten Ausbaustufe nutzt die App es nur zum **Prüfen mit Report** – es werden keine Dateien verändert.

## Bedienung

- **ROM-Ordner** und **DAT-Ordner** wählen (zuletzt verwendete Ordner in der INI, `[igir]`). Als DAT-Ordner passt `<HDD>/dats` – Igir liest DATs auch aus Unterordnern.
- **Prüfen** startet `igir test report` ([specs/igir.md](../specs/igir.md)); die Ausgabe erscheint zeilenweise im Protokoll, **Abbrechen** beendet Igir.
- Danach zeigt die Tabelle den Report (Spalten wie in Igirs CSV), darüber eine Zusammenfassung „Gefunden · Fehlend · Doppelt · Unbekannt · Gelöscht“ und ein Filter nach Status. Die CSV liegt in `reports/igir_report_<Datum>_<Zeit>.csv` neben der App.
- **DATs aktualisieren** lädt die DATs für alle RomM-Plattformen ([features/dats.md](dats.md)).
- Fehlt die Igir-Programmdatei, zeigt der Reiter einen Hinweis mit dem erwarteten Pfad.

## Disc-Spiele mit abweichender CUE

Viele Disc-Dumps sind bitgenau korrekt, haben aber eine neu erzeugte oder umbenannte CUE. Igir zählt ein Spiel nur als gefunden, wenn **alle** Dateien laut DAT stimmen – also auch die CUE. Deshalb:

- Die App gibt die korrekten Redump-CUEs aus `dats/redump-cues/` als zusätzliches `--input` mit (`tools.cue_inputs`: heißt der ROM-Ordner wie eine Plattform, z. B. `roms/psx`, nur deren CUEs, sonst alle).
- Unbenutzte Hilfs-CUEs werden danach aus dem Report gefiltert (`igir_report.without_unused_under`), damit sie nicht als „Unbekannt“ erscheinen.
- **Grenze:** Igir kombiniert keine Dateien aus einem Archiv (7z/ZIP) mit Dateien außerhalb. BIN/CUE-Spiele *im Archiv* mit abweichender CUE bleiben „Unbekannt“, bis sie entpackt sind (z. B. im [Archive-Reiter](archive.md)).

Dateinamen spielen für das Finden keine Rolle, nur der Inhalt. Bei Disc-Spielen hängt es indirekt doch am Namen, weil die CUE die Dateinamen der BINs enthält.

## Programmdatei

Herkunft, Pfad und Version: [specs/igir.md](../specs/igir.md#programmdatei). Bezug der Programmdatei: [ADR 0005](../adr/0005-external-tools-not-bundled.md).

## Geplant

Benennen und Einsortieren nach DAT: siehe „Nach DAT benennen“ und „Bibliothek aufräumen“ in der [Roadmap](../roadmap.md).
