# chdman (Reiter „chdman“)

CHD fasst die Dateien einer Disc verlustfrei in einer komprimierten Datei zusammen; RomM und Emulatoren wie DuckStation, PCSX2, Flycast oder PPSSPP lesen sie direkt ([ADR 0006](../adr/0006-chd-for-disc-games.md)). Echte Hardware (webMAN, OPL, XStation …) braucht dagegen BIN/CUE bzw. ISO – dafür wandelt „Export vorbereiten“ automatisch zurück.

## Liste

- Alle Disc-Spiele aus `roms/<slug>/` der Systeme in `chd.CHD_PLATFORMS`: PS1, PS2, PSP, Dreamcast, Saturn, Sega CD, PC Engine CD, Neo Geo CD, 3DO, PC-FX, CD-i, Amiga CD32, Jaguar CD. Nicht dabei: GameCube/Wii (RVZ), Switch (NSZ), PS3.
- Quelle ist `library.scan_platform`: Disc-Images (CHD, ISO, CUE, GDI) und 7z/ZIP-Archive. Größe = alle Tracks bzw. das Archiv.
- Filter nach System; Spalte **Prüfung** zeigt „in Ordnung“ / „fehlerhaft“ (nur für die laufende Sitzung).

## Aktionen

**In CHD umwandeln** (BIN/CUE, GDI, ISO, 7z/ZIP):

1. Archive werden zuerst in `<HDD>/.retro-manager-tmp/chdman/<schlüssel>/` entpackt (Platzprüfung vorher). Enthält ein Archiv mehrere Discs, entsteht je Image eine CHD mit dessen Namen; sonst heißt die CHD wie der Eintrag in der Bibliothek.
2. `createcd` für CUE/GDI und CD-ISOs, `createdvd` für ISOs von PS2 und PSP – in `<name>.chd.part` im Arbeitsordner.
3. `chdman verify` auf die neue Datei.
4. Verschieben neben das Original (Struktur A).
5. Original löschen (Archiv bzw. CUE/GDI samt aller Tracks bzw. ISO), wenn **„Originale nach erfolgreicher Prüfung löschen“** angehakt ist (Standard an, INI `[chdman] delete_originals`; Rückfrage vor dem Start).

Existiert die Ziel-CHD schon, wird die Disc übersprungen. Abbruch oder Fehler: Arbeitsordner wird gelöscht, das Original bleibt unberührt.

**Zurückwandeln …** in einen wählbaren Ordner. Die Medienart kommt aus dem CHD-Kopf ([specs/chdman.md](../specs/chdman.md)):

| Medium | Ergebnis |
|---|---|
| CD (PS1, Saturn, PS2-Spiele auf CD …) | BIN/CUE, ein BIN je Track (`--splitbin`; Einzelspur-Discs siehe [specs/chdman.md](../specs/chdman.md)) |
| GD-ROM (Dreamcast) | GDI mit einer Datei je Track |
| DVD (PS2, PSP) | eine ISO |

CDs und GD-ROMs bekommen einen Ordner je Spiel, DVDs nicht. Vorhandene Ausgaben werden nicht überschrieben. Mit gesetztem Haken wird die CHD nach erfolgreichem Zurückwandeln gelöscht (Rückfrage vorher). War das Original eine CD als ISO, kommt sie als BIN/CUE zurück – für chdman ist es eine CD. Ergebnis sind lose Dateien, kein 7z.

**Prüfen:** `chdman verify` rechnet die gespeicherten SHA1-Prüfsummen nach.
**Infos:** Ausgabe von `chdman info` (Tracks, Kompression, SHA1) im Protokoll.

## Verhalten

- Discs laufen nacheinander; chdman nutzt beim Komprimieren selbst alle Kerne. Fortschritt aus der „xx% complete“-Ausgabe, Arbeitsschritt („Entpacken …“, „Komprimieren …“, „CHD prüfen …“) in der Aktivitätsanzeige.
- Am Ende weist die App darauf hin, die Plattform in RomM neu einzulesen (Scan).
- Fehlt chdman, sind alle Aktionen gesperrt und ein Hinweis erscheint (Suchreihenfolge: [specs/chdman.md](../specs/chdman.md)).
- CHDs lassen sich nicht im Archive-Reiter entpacken – 7-Zip liest kein CHD.

## Status

- **Real getestet** mit chdman 0.289 und Testdaten: PS1-7z mit zwei Tracks, PS2-ISO, Dreamcast-GDI → CHD → zurück bitgenau; beschädigte CHD wird erkannt; Abbruch während des Komprimierens; Löschen der CHD beim Zurückwandeln.
- **Noch offen:** siehe [Roadmap](../roadmap.md#noch-nicht-real-getestet).
