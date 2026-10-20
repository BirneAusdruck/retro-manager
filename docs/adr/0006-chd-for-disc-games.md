# ADR 0006: CHD als Archivformat für Disc-Spiele

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Disc-Spiele liegen als BIN/CUE, GDI oder ISO vor, oft zusätzlich in 7z/ZIP. Das ist groß, besteht aus mehreren Dateien und Emulatoren können Archive meist nicht direkt lesen. Echte Hardware (webMAN, OPL, ODEs) braucht dagegen die Rohformate.

## Entscheidung

- Im Archiv werden Disc-Spiele als **CHD** abgelegt, wo Emulatoren es lesen (PS1, PS2, PSP, Dreamcast, Saturn und weitere CD-Systeme). GameCube/Wii bekommen RVZ, Switch NSZ, Cartridge-Systeme ZIP (`formats.target_format`).
- CHD ist verlustfrei: Zurückwandeln ergibt bitgenau die ursprünglichen Daten (Redump-Namen für Einzelspur-Discs werden wiederhergestellt).
- Für echte Hardware wandelt „Export vorbereiten“ automatisch zurück, in einen getrennten, löschbaren Ordner ([ADR 0009](0009-exports-as-derived-copies.md)).
- Umgewandelt wird über chdman ([ADR 0005](0005-external-tools-not-bundled.md)); die neue CHD wird vor dem Löschen des Originals mit `chdman verify` geprüft.

## Folgen

- RomM erkennt Discs in CHD über den eingebetteten SHA1.
- Die Prüfung gegen Redump-DATs (über Igir) passt zu BIN/CUE, nicht zur CHD – deshalb vor dem Umwandeln prüfen bzw. benennen.
