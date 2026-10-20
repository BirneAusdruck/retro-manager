# Archive (Reiter „Archive“)

Entpacken, Packen und Prüfen von Archiven mit 7-Zip ([ADR 0007](../adr/0007-7zip-as-archive-tool.md)), mehrere Einträge gleichzeitig. CHD-Dateien erzeugt und entpackt der [chdman-Reiter](chdman.md).

## Liste

- Vorerst nur die Bibliothek: alle Einträge aller Plattformordner unter `roms/` (`library.scan_entries`) – Archive, BIN/CUE, GDI, ISO, CHD und einzelne ROM-Dateien. Von CUE/GDI eingebundene Tracks und weitere Teile mehrteiliger Archive erscheinen nicht einzeln. Beliebige andere Ordner (z. B. Downloads) sind für später vorgemerkt.
- Filter nach System und **Anzeigen**: „Alle Einträge“, „Nur Archive“ (zum Entpacken/Prüfen), „Nur ungepackte“ (zum Packen).
- Spalten (Unterklasse `ArchiveTableModel` des gemeinsamen Tabellenmodells):

| Auswahl | System | Spiel | Format | Größe | Zielformat | Prüfung |
|---|---|---|---|---|---|---|
| | Plattform | Name | Archivart (`7Z`, `TAR.GZ`, `RAR (3 Teile)`) bzw. Dateiart | alle Teile bzw. Tracks | laut [Archivregeln](../specs/library.md#archivformat-je-system) | in Ordnung / fehlerhaft |

## Aktionen

**Entpacken** – 7z, ZIP, RAR (auch `.partN.rar`, `.rNN`), `.7z.001`/`.zip.001`, TAR, TAR.GZ/BZ2/XZ, GZ/BZ2/XZ:

1. Entpacken in `<HDD>/.retro-manager-tmp/archive/<schlüssel>/`; 7-Zip prüft dabei alle CRCs. Gepackte TARs in zwei Schritten (erst zur `.tar`, dann deren Inhalt).
2. Einsortieren (`archives.extracted_layout`):
   - genau eine Datei → direkt neben das Archiv (z. B. `Tetris.gb`)
   - genau ein Ordner → dieser Ordner
   - mehrere Einträge → Spielordner `<Archivname>/` (Struktur A)
3. Vorhandene Ziele werden nicht überschrieben (Fehler für diesen Eintrag).

**Entpacken nach …** – wie oben, aber in einen wählbaren Ordner.

**Packen** – als ZIP oder 7z, Stufe Schnell / Normal / Maximal (`-mx` 1 / 5 / 9), je Spiel ein Archiv neben dem Original:

- Gepackt wird die ROM-Datei, die CUE/GDI samt aller Tracks oder die ISO.
- Ausgewählte Archive werden **umgepackt** (entpacken → packen), z. B. 7z → ZIP.
- Ablauf: `<name>.<ext>.part` im Arbeitsordner → `7zz t` → an den Platz verschieben.
- Weicht das Format vom Zielformat des Systems ab (z. B. PS1, wo CHD vorgesehen ist), fragt die App nach.
- Liegt der Eintrag bereits im gewählten Format vor oder existiert das Ziel schon → Fehler für diesen Eintrag.

**Prüfen** – `7zz t` rechnet alle Prüfsummen eines Archivs nach.

**Originale nach Erfolg löschen** (Standard aus; Rückfrage vor dem Start) – nach erfolgreichem Entpacken bzw. Packen; bei mehrteiligen Archiven alle Teile. Packformat, Stufe und dieser Haken stehen in der INI (`[archives]`, [specs/configuration.md](../specs/configuration.md)).

Abbruch oder Fehler: Der Arbeitsordner des Eintrags wird gelöscht, das Original bleibt.

## Parallele Jobs

- **Gleichzeitig** (1–8, INI `[jobs] max_parallel`) legt fest, wie viele Einträge gleichzeitig laufen; die Änderung gilt sofort.
- Jeder Eintrag ist ein eigener Job mit eigenem 7-Zip-Prozess und Arbeitsordner; die Warteschlange füllt frei werdende Plätze.
- Auf einer HDD ist mehr nicht immer schneller (Kopfspringen zwischen den Dateien); 1–2 ist meist ein guter Wert.
- Jeder laufende Job erscheint als eigene Zeile in der [Aktivitätsanzeige](activity.md); Klick führt in diesen Reiter.

## Programmdatei

Fehlt 7-Zip, sind die Aktionen gesperrt. Suchreihenfolge, Befehle und Ausgabe: [specs/7zip.md](../specs/7zip.md).

## Status

- **Real getestet** mit 7-Zip 25.01 und Testdaten: 7z, ZIP mit mehreren Dateien, TAR.GZ, dreiteiliges `.7z.001` entpackt; ROMs und BIN/CUE als ZIP gepackt (bitgenau), 7z → ZIP umgepackt; zwei Jobs gleichzeitig; Zielkonflikte, beschädigtes Archiv, Abbruch mitten im Entpacken.
- **Noch offen:** siehe [Roadmap](../roadmap.md#noch-nicht-real-getestet).
