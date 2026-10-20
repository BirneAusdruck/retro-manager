# Aktivitätsanzeige (Banner oben rechts)

Sobald irgendein Hintergrundvorgang läuft, erscheint oben rechts im Banner ein Feld mit dem ersten Vorgang. Beim Überfahren rollt eine Liste aller Vorgänge bis zum unteren Fensterrand aus; ein Klick auf einen Vorgang wechselt in den zuständigen Reiter.

## Quellen

`ActivityController` sammelt die Signale aller Controller:

| Quelle | Signale | Einträge | Reiter |
|---|---|---|---|
| Igir-Prüfung | `running_changed`, `output_line` | einer, Detail = letzte Ausgabezeile | igir |
| DATs aktualisieren | `running_changed`, `status`, `progress` | einer | igir |
| chdman | `queue_changed`, `phase`, `progress` | laufende Disc + je wartende Disc einer | chdman |
| Archive | `jobs_changed` | je laufender und je wartender Job einer | archive |
| Aufbereiten | `queue_changed`, `status`, `progress` | laufende Disc + je wartende Disc einer | export |
| FTP-Warteschlange | `job_added`, `job_changed`, `job_finished` | je Auftrag einer | ftp |

- Reihenfolge: laufende Vorgänge zuerst (in Startreihenfolge), dann wartende; Wartende behalten ihren Platz.
- Neue, beendete und von „wartet“ zu „läuft“ wechselnde Einträge werden sofort gemeldet, reiner Fortschritt gebündelt (höchstens ~10 Meldungen/s).

## Anzeige

- `ActivityIndicator` im Banner: Drehsymbol, Titel und Detail des ersten Vorgangs, Fortschrittsbalken (unbestimmt, wenn kein Fortschritt bekannt), „+N“ für weitere. Unsichtbar ohne Vorgänge.
- `ActivityPanel` schwebt über der Arbeitsfläche (nicht im Layout), rechtsbündig unter dem Feld, mindestens 380 px breit. Es rollt per `QPropertyAnimation` (~180 ms) bis zur Fensterunterkante aus und schließt ~300 ms, nachdem die Maus Feld und Liste verlassen hat. Bei Größenänderung des Fensters passt es sich an.
- Zeilen werden bei reinem Fortschritt an Ort und Stelle aktualisiert (kein Flackern, Klicks gehen nicht verloren).
- Klick → Signal `activity_clicked(tab)` → `MainWindow` wechselt in den Reiter (`Activity.tab`: igir, chdman, archive, export, ftp).

## Erweitern

Ein neuer Hintergrundvorgang bietet im Controller passende Signale an (laufend/wartend, Detail, Fortschritt) und wird in `ActivityController` angeschlossen; der Reiter bekommt einen `TAB_*`-Schlüssel und einen Eintrag in `MainWindow._tab_index`.
