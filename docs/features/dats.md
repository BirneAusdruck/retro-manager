# DATs aktualisieren (Igir-Reiter)

Der Knopf **DATs aktualisieren** im Igir-Reiter lädt die DATs, die zu den Plattformen von RomM passen, und legt sie in `<HDD>/dats/` ab. Dazu korrekte Redump-CUEs (für die Prüfung von Disc-Spielen) und Redump-Disc-Keys (für PS3-Exporte).

## Ablauf

1. RomM-Plattformen holen: `GET /api/platforms/supported` (Token wird bei HTTP 401 per Refresh erneuert).
2. Igirs `consoleTokens.json` passend zu `tools.IGIR_VERSION` von GitHub laden – daraus kommt die Zuordnung DAT → RomM-Plattform.
3. No-Intro-Daily-Paket (Parent/Clone) von DAT-o-MATIC laden, Sets „No-Intro“, „Non-Redump“, „Unofficial“.
4. Alle Redump-DATs einschließlich BIOS laden.
5. Für passende Redump-Systeme mit Cuesheets: `redump.org/cues/<system>/` → `dats/redump-cues/<plattform>/`.
6. Für PS3: Disc-Keys `redump.org/keys/ps3/` → `dats/redump-keys/ps3/`.
7. Zuordnen und schreiben (im Thread-Pool), `ABGLEICH.md` erzeugen.

Adressen und Besonderheiten der Quellen: [specs/dat-sources.md](../specs/dat-sources.md).

## Zuordnung DAT → RomM-Plattform

1. Wie Igir: `findLast` über die `datNameRegex` aus `consoleTokens.json` – der **letzte** Treffer gewinnt (der erste führt zu Fehlzuordnungen).
2. Feste Zuordnungen in `dat_update.MANUAL_MAPPINGS`.
3. Namensabgleich mit den RomM-Plattformnamen; bekannte Fehltreffer stehen in `dat_update.WRONG_NAME_MATCHES` (z. B. „Capcom Play System III“, „Naomi Satellite Terminal“).

## Was geschrieben wird

```
<HDD>/dats/
├── no-intro/                  # inkl. Unterordner Non-Redump/, Unofficial/
├── redump/                    # inkl. BIOS-DATs
├── redump-cues/<plattform>/   # gehört komplett der App, wird je Lauf ersetzt
├── redump-keys/<plattform>/   # gehört komplett der App, wird je Lauf ersetzt
├── ABGLEICH.md                # welche RomM-Plattform welche DATs hat, welche fehlen
└── .retro-manager-dats.json   # Manifest der von der App geschriebenen Dateien
```

- Nur DATs, die zu einer RomM-Plattform passen, werden geschrieben.
- Beim nächsten Lauf ersetzt die App nur Dateien aus ihrem Manifest; **eigene DATs des Nutzers bleiben unberührt**.
- `ABGLEICH.md` hat drei Teile: je RomM-Plattform (`roms/<slug>`) die zugeordneten DATs mit Quelle und Art der Zuordnung; DATs ohne RomM-Plattform (nicht kopiert); RomM-Plattformen ohne DAT, gruppiert nach Kategorie.

## Status

- **Real getestet:** 265 DATs und 26 425 CUEs geladen und zugeordnet.
- **Noch offen:** siehe [Roadmap](../roadmap.md#noch-nicht-real-getestet).
