# Bibliothek auf der Archiv-HDD

## Ordnerstruktur (RomM-Struktur A)

RomM ist das Herzstück; **jedes Werkzeug der App liest und schreibt nach dieser Struktur** ([ADR 0003](../adr/0003-romm-as-core.md)). Der HDD-Ordner ist im Container `/romm/library`.

```
<HDD>/
├── roms/<plattform>/          # ein Spiel = eine Datei oder ein eigener Ordner
│   ├── <Spiel>.zip
│   └── <Spiel>/               # bei mehreren Dateien (Discs, Updates, DLC)
│       ├── <Spiel> (Disc 1).chd
│       ├── <Spiel> (Disc 2).chd
│       └── dlc/ | update/ | patch/ | hack/ | translation/ | manual/ …   # von RomM erkannte Unterordner
├── bios/<plattform>/          # Firmware, nur wo nötig
├── dats/                      # DATs, CUEs, Keys (von RomM ignoriert) – siehe features/dats.md
├── exports/<profil>/          # aufbereitete Spiele für echte Hardware (von RomM ignoriert), löschbar
└── .retro-manager-tmp/        # Arbeitsordner der App (Entpacken, halbfertige Dateien)
    ├── chdman/<schlüssel>/
    └── archive/<schlüssel>/
```

- Struktur B (`<plattform>/roms/`) wird **nicht** verwendet.
- Der Arbeitsordner liegt bewusst auf der HDD: fertige Dateien werden nur umbenannt (kein Kopieren), und RomM sieht keine halbfertigen Dateien.

## Plattformordner

- RomM erkennt Plattformen **nur über den Ordnernamen**, nach seiner Liste unterstützter Plattformen (Slugs wie `gb`, `psx`, `ps2`, `dc`, `ngc`, `switch`). Groß-/Kleinschreibung ist egal; auch Batocera-, RetroBat- und ES-DE-Namen werden erkannt.
- Igirs Token `{romm}` liefert genau diese Ordnernamen ([specs/igir.md](igir.md#plattform-tokens)).
- Anzeigenamen der Plattformen stehen bisher an mehreren Stellen (`chd.CHD_PLATFORMS`, `devices.PLATFORM_LABELS`); die zentrale Zuordnung in `core/platforms.py` ist vorgemerkt ([Roadmap](../roadmap.md#themen)).

Wichtige Slugs: `psx` (PS1), `ps2`, `ps3`, `psp`, `dc` (Dreamcast), `saturn`, `segacd`, `turbografx-cd` (PC Engine CD), `neo-geo-cd`, `3do`, `pc-fx`, `philips-cd-i`, `amiga-cd32`, `atari-jaguar-cd`, `ngc` (GameCube), `wii`, `switch`.

## Archivformat je System

Nicht pauschal ZIP, sondern je System das Format, das Emulatoren und RomM am besten lesen (`formats.target_format`):

| Format | Systeme |
|---|---|
| ZIP | Cartridge-Systeme (Game Boy bis N64) und alle übrigen, nicht unten genannten Systeme |
| CHD | Disc-Systeme mit CHD-Unterstützung: PS1, PS2, PSP, Dreamcast, Saturn, Sega CD, PC Engine CD, Neo Geo CD, 3DO, PC-FX, CD-i, CD32, Jaguar CD |
| RVZ | GameCube, Wii |
| NSZ | Switch |
| keine Regel | PS3, Xbox 360 |

CHD ist nur sinnvoll, solange die Dumps nicht auf echter Hardware gebraucht werden (ODE wie XStation, OPL); dafür erzeugt „Export vorbereiten“ BIN/CUE bzw. ISO.

## Spiele-IDs und Namen

- Spiele-IDs (z. B. SLUS/SLES bei PS2) und korrekte Namen stammen aus den **Redump- bzw. No-Intro-DATs**, abgeglichen per Hash über Igir. Die App pflegt **keine eigene ID-Datenbank**.
- Switch-Dumps: Die DAT-Abdeckung ist lückenhaft; Title-IDs ggf. aus NSP/XCI auslesen.

## Einträge lesen (`core/library.py`)

`library.scan_entries(roms, slug)` ist die **einzige Stelle**, die Plattformordner durchsucht. Alle Reiter wählen daraus, was sie verarbeiten können; neue Dateiarten werden dort ergänzt, nicht in eigenen Suchfunktionen.

- Durchsucht `roms/<slug>/` und eine Ebene in Spielordner hinein; RomM-Unterordner (`dlc/`, `manual/` …) und versteckte Dateien bleiben außen vor.
- Ein Eintrag ist ein `LibraryGame`: `slug`, `name` (ohne Endung), `path`, `kind`, `size`, `game_dir` (Spielordner oder leer). Schlüssel `key` = `<slug>/[<game_dir>/]<dateiname>`.
- Arten (`kind`):

| Art | Dateien |
|---|---|
| `chd`, `iso`, `cue`, `gdi` | Disc-Images (`library.DISC_KINDS`) |
| `archive` | alles, was `archive_names.is_archive` erkennt (7z, ZIP, RAR, TAR …, auch mehrteilig) |
| `file` | alles andere, z. B. eine ROM-Datei `Tetris.gb` |

- BINs bzw. Tracks, die eine CUE oder GDI einbindet, und weitere Teile mehrteiliger Archive erscheinen **nicht einzeln**. `size` umfasst alle Tracks bzw. alle Teile.
- Eine `.bin` ohne CUE ist ein `file`. Als Disc-Image gilt `.bin` bewusst nicht: chdman bräuchte die CUE für Spuren und Modus.
- `library.scan_platform` = Filter `is_disc_source`: Disc-Images plus 7z/ZIP-Archive (die chdman- und Export-Reiter selbst über py7zr/zipfile entpacken). Der Archive-Reiter nimmt alle Einträge.
- Tracks auflösen: `cue_files` (Zeilen `FILE "…" BINARY`, mit und ohne Anführungszeichen), `gdi_files` (`<nr> <lba> <typ> <sektorgröße> <datei> <offset>`, Datei ggf. in Anführungszeichen), `image_files` (Image plus Tracks). Fehlende Dateien werden übergangen.
