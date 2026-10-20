# ADR 0010: Eine gemeinsame Suche über die Bibliothek

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Zunächst hatten chdman/Export (`library.scan_platform`) und der Archive-Reiter (`archives.scan_entries`) je eine eigene Ordnersuche. Sie liefen auseinander: Die Größe von BIN/CUE-Spielen zählte nur in einer der beiden die Tracks mit, und jedes Archiv las für mehrteilige Archive den Ordner erneut.

## Entscheidung

- `library.scan_entries` ist die **einzige** Stelle, die `roms/<plattform>/` durchsucht. Sie fasst Tracks (CUE/GDI) und Teile mehrteiliger Archive zusammen und berechnet die Größe.
- Die Erkennung von Archivnamen liegt in `core/archive_names.py`, damit `library` sie nutzen kann, ohne `archives` zu importieren.
- Die Reiter filtern: chdman und Export über `scan_platform` (`is_disc_source`), der Archive-Reiter nimmt alle Einträge.
- Neue Dateiarten werden nur dort ergänzt.

## Folgen

Einheitliches Verhalten in allen Reitern. Eine `.bin` ohne CUE ist eine eigene Frage, die künftig an genau dieser Stelle entschieden wird.
