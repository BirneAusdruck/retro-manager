# Architekturentscheidungen (ADR)

Jede Datei hält eine Grundsatzentscheidung mit Kontext und Folgen fest. Neue Entscheidungen bekommen die nächste Nummer; eine überholte Entscheidung wird nicht gelöscht, sondern auf „ersetzt durch ADR NNNN“ gesetzt.

| Nr. | Entscheidung |
|---|---|
| [0001](0001-mvc-qt-free-model.md) | MVC mit Qt-freiem Model |
| [0002](0002-ui-in-code.md) | Oberfläche im Code statt Qt Designer |
| [0003](0003-romm-as-core.md) | RomM als Herzstück, Bibliotheksstruktur A für alle Werkzeuge |
| [0004](0004-docker-for-romm.md) | RomM in Docker, zunächst nur Docker Engine |
| [0005](0005-external-tools-not-bundled.md) | Externe Werkzeuge nicht mitliefern, sondern bei Bedarf laden |
| [0006](0006-chd-for-disc-games.md) | CHD als Archivformat für Disc-Spiele |
| [0007](0007-7zip-as-archive-tool.md) | 7-Zip als Archivwerkzeug |
| [0008](0008-uv-for-dependencies.md) | uv für Abhängigkeiten und Befehle |
| [0009](0009-exports-as-derived-copies.md) | Exporte für Hardware als abgeleitete, löschbare Kopien |
| [0010](0010-single-library-scan.md) | Eine gemeinsame Suche über die Bibliothek |

## Vorlage

```markdown
# ADR NNNN: <Titel>

**Status:** vorgeschlagen | angenommen | ersetzt durch ADR NNNN · **Entschieden:** JJJJ-MM-TT · **Festgehalten:** JJJJ-MM-TT

## Kontext

## Entscheidung

## Folgen
```
