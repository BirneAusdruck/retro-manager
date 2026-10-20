# Igir (5.7.2)

Mit Igir 5.7.2 verifiziertes Verhalten, auf das sich die App verlässt. Version: `tools.IGIR_VERSION`.

## Programmdatei

Standalone-Binary von [github.com/emmercm/igir/releases](https://github.com/emmercm/igir/releases) (ohne Node.js), Lizenz GPL-3.0, unter `tools/igir/igir` bzw. `igir.exe` (`tools.igir_executable`). Es gibt keine Option `--version`; die Version steht im Banner der Ausgabe.

## Prüfen mit Report

```
igir test report --dat <DAT-Ordner> --input <ROM-Ordner> [--input <CUE-Ordner> …] --report-output <reports/igir_report_YYYY-MM-DD_HH-MM-SS.csv>
```

- `tools.igir_verify_args` baut die Argumente; `test` verändert keine Dateien.
- `--dat <Ordner>` liest DATs auch aus Unterordnern.
- Zusätzliche `--input` mit korrekten Redump-CUEs ergänzen Disc-Dumps mit abweichender CUE (`tools.cue_inputs`).
- Der Report-Dateiname enthält kein `%`, damit Igir darin keine Tokens ersetzt.
- Ohne Terminal gibt Igir je Arbeitsschritt nur eine Abschlusszeile aus (keine Fortschrittsflut). ANSI-Steuerzeichen und `\r`-Überschreibungen entfernt `tools.clean_output`.

## Report-CSV

Spalten: `DAT Name, Game Name, Status, ROM Files, Patched, BIOS, Retail Release, Unlicensed, Debug, Demo, Beta, Sample, Prototype, Program, Aftermarket, Homebrew, Bad`.

| Status | Anzeige in der App |
|---|---|
| `FOUND` | Gefunden |
| `MISSING` | Fehlend |
| `DUPLICATE` | Doppelt |
| `UNUSED` | Unbekannt (Datei passt zu keinem DAT-Eintrag) |
| `DELETED` | Gelöscht |

`igir_report.without_unused_under` entfernt `UNUSED`-Zeilen, deren Datei unter den CUE-Hilfsordnern liegt.

## Erkennung

- Abgleich per Hash (CRC32 und Größe). Bei 7z/ZIP liest Igir die CRC32 aus dem Archivkopf, ohne zu entpacken. Dateinamen spielen für das Finden keine Rolle.
- Ein Spiel gilt nur als gefunden, wenn alle seine Dateien laut DAT stimmen (bei Disc-Spielen also auch die CUE).
- Dateien innerhalb eines Archivs werden nicht mit Dateien außerhalb kombiniert.

## Plattform-Tokens

- `consoleTokens.json` im Igir-Repository (Tag `v<version>`) ordnet DAT-Namen über `datNameRegex` Plattformen zu; das Token `{romm}` liefert RomMs Plattformordnernamen.
- Igir nimmt den **letzten** passenden Eintrag (`findLast`); die App macht es genauso.

## Grenzen

Igir erzeugt ZIP, aber kein CHD, RVZ oder NSZ.
