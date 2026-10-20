# DAT-Quellen

Adressen in `core/dat_update.py`, Abläufe in `controllers/dat_controller.py` (Zeitlimit 120 s je Download).

## No-Intro (DAT-o-MATIC)

- Daily-Paket Parent/Clone: `https://datomatic.no-intro.org/index.php?page=download&s=64&op=daily`.
- Ablauf:
  1. Daily-Seite laden.
  2. Formular senden → Antwort 302 auf die Download-Seite.
  3. Den **sichtbaren** Knopf „Download!!“ senden. Ein versteckter Knopf daneben ist eine Bot-Falle und darf nicht benutzt werden.
- Aus dem ZIP übernimmt die App die Sets „No-Intro“ (nach `dats/no-intro/`), „Non-Redump“ und „Unofficial“ (nach `dats/no-intro/Non-Redump/` bzw. `Unofficial/`).
- Ändert No-Intro die Seite, ist hier zuerst nachzusehen.

## Redump

- **Nur über HTTP** erreichbar (`http://redump.org/…`).
- Liste der Systeme: `http://redump.org/downloads/`.
- DAT je System: `http://redump.org/datfile/<code>/` (ZIP), einschließlich BIOS-DATs.
- CUEs je System: `http://redump.org/cues/<code>/` (ZIP mit einer CUE je Spiel).
- Disc-Keys: `http://redump.org/keys/<code>/` (z. B. `ps3`; ZIP mit `.key`-Dateien, 16 Byte je Spiel).
- Zwischen den Anfragen 1 s Pause.

## Igir

- `consoleTokens.json` passend zur Igir-Version: `https://raw.githubusercontent.com/emmercm/igir/v<version>/…` – Grundlage der Zuordnung DAT → RomM-Plattform ([specs/igir.md](igir.md)).

## Entpacken der Pakete

Die ZIP-Pakete werden im Speicher gelesen (`zipfile` über `BytesIO`). Beim Auspacken von CUE- und Key-Paketen übernimmt die App nur Einträge mit sicheren relativen Pfaden (`manifest.is_safe_relative`, also kein `..` und kein absoluter Pfad). HTML-Entities in System- und DAT-Namen werden aufgelöst.
