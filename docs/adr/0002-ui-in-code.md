# ADR 0002: Oberfläche im Code statt Qt Designer

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Qt-Oberflächen lassen sich mit dem Qt Designer (`.ui`-Dateien, daraus generierter Code) oder direkt im Python-Code bauen. Die Projektvorgabe von Beginn an ist der zweite Weg.

## Entscheidung

Keine `.ui`-Dateien, kein Qt Designer, kein `pyside6-uic`: Die Oberfläche wird vollständig in Python-Code gebaut, Styling zentral in einer QSS-Datei. Die geltenden Regeln im Einzelnen: [architecture.md](../architecture.md#oberfläche).

## Folgen

- Die gesamte Oberfläche ist normaler, durchsuchbarer Python-Code ohne generierte Dateien; Layout und die Logik, die es befüllt, stehen beieinander.
- Visuelles Zusammenklicken entfällt.
