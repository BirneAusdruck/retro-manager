# 7-Zip (25.01)

Offizieller Build von Igor Pavlov: [github.com/ip7z/7zip/releases](https://github.com/ip7z/7zip/releases) bzw. 7-zip.org, z. B. `7z2501-linux-x64.tar.xz` mit `7zz` (dynamisch gelinkt) und `7zzs` (statisch). Lizenz: LGPL mit unRAR-Einschränkung (`License.txt`).

Gesucht unter `tools/7zip/7zz` (Linux) bzw. `tools/7zip/7za.exe` (Windows), sonst `7zz` oder `7z` im PATH (`tools.sevenzip_executable`).

## Befehle

Argumente in `core/tools.py`; alle mit `-bsp1 -bso0 -bse2` (Fortschritt auf die Standardausgabe, normale Meldungen aus, Fehler auf die Fehlerausgabe):

| Zweck | Aufruf |
|---|---|
| Entpacken | `7zz x <archiv> -o<zielordner> -y …` |
| Prüfen | `7zz t <archiv> …` |
| Packen | `7zz a -t<zip/7z> -mx=<1/5/9> -mmt=on … <ausgabe> -- <namen …>` |

- `x` entpackt mit Ordnerstruktur; `-y` ist unbedenklich, weil das Ziel ein neuer, leerer Arbeitsordner ist.
- Beim Packen läuft der Prozess im Quellordner; die Namen stehen hinter `--`, damit ein Dateiname wie `-seltsam.gb` nicht als Schalter gilt. `-t` legt das Format fest, deshalb darf die Ausgabe `<name>.zip.part` heißen.
- Gepackte TARs (`.tar.gz`, `.tgz` …) entpackt 7-Zip nur eine Ebene tief, also zur `.tar`; die App entpackt diese in einem zweiten Schritt.
- RAR kann 7-Zip nur entpacken, nicht erzeugen.

## Rückgabewerte

| Wert | Bedeutung |
|---|---|
| 0 | in Ordnung |
| 1 | Warnung (z. B. Dateien übersprungen) – die App wertet das als Fehler |
| 2 | schwerer Fehler (z. B. `Is not archive`) |
| 7 | falsche Argumente |
| 8 | zu wenig Speicher |
| 255 | vom Nutzer abgebrochen |
| −1 | kein Rückgabewert von 7-Zip: Der Prozess ist abgestürzt (von der App gesetzt) |

## Fortschrittsausgabe

Ohne Terminal überschreibt 7-Zip die Zeile mit Rückschritt-Zeichen (`\b`), z. B. `␈␈␈␈ 48% 1 + big.bin␈␈␈␈…`. `archives.parse_progress` nimmt die Prozentzahl am **Anfang** jedes Abschnitts – Prozentzeichen in Dateinamen (`100% Orange Juice`) zählen nicht. Da Ausgabe stückweise ankommt, behält der Job die letzten Zeichen für den nächsten Block.

Fehlermeldungen (Fehlerausgabe) sehen etwa so aus: `ERROR: <datei>` / `Open ERROR: Cannot open the file as [7z] archive` / `ERRORS:` / `Is not archive`; die App zeigt die letzten beiden aussagekräftigen Zeilen.

## Archivnamen (`core/archive_names.py`)

| Endung | Bedeutung |
|---|---|
| `.7z`, `.zip`, `.rar`, `.tar`, `.gz`, `.bz2`, `.xz` | einfache Archive |
| `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tgz`, `.tbz`, `.tbz2`, `.txz` | gepackte TARs (zwei Schritte) |
| `.part1.rar` (auch `.part01.rar`) | erster Teil eines mehrteiligen RAR; `.part2.rar` … gehören dazu |
| `.rar` + `.r00`, `.r01` … | RAR im alten Mehrteil-Schema |
| `.7z.001`, `.zip.001`, `.rar.001` | erster Teil eines aufgeteilten Archivs; `.002` … gehören dazu |
| `.zip` + `.z01` … | aufgeteiltes ZIP |

Weitere Teile erscheinen nicht als eigene Einträge; `volumes` liefert alle Teile, erster Teil zuerst. Der Spielname ist der Dateiname ohne Archivendung (`Spiel (USA).tar.gz` → `Spiel (USA)`).
