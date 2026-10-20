# chdman (0.289)

chdman gehört zu MAME (GPL). Gesucht unter `tools/chdman/chdman` bzw. `chdman.exe`, sonst im PATH (`tools.chdman_executable`; Linux z. B. Paket `mame-tools`). Argumente in `core/tools.py`.

## Befehle

| Zweck | Aufruf |
|---|---|
| CD/GD-ROM erzeugen | `chdman createcd -i <bild.cue/.gdi/.iso> -o <ausgabe> -f` |
| DVD erzeugen | `chdman createdvd -i <bild.iso> -o <ausgabe> -f` |
| CD zurückwandeln | `chdman extractcd -i <x.chd> -o <ziel>/<name>.cue --splitbin -f` |
| GD-ROM zurückwandeln | `chdman extractcd -i <x.chd> -o <ziel>/<name>.gdi -f` |
| DVD zurückwandeln | `chdman extractdvd -i <x.chd> -o <ziel>/<name>.iso -f` |
| Prüfen | `chdman verify -i <x.chd>` (Rückgabewert 0 = in Ordnung) |
| Infos | `chdman info -i <x.chd>` |

- `createdvd` nur für ISOs von DVD-Systemen (PS2, PSP); CUE/GDI und CD-ISOs mit `createcd` (`chd.media_for_image`).
- Der Ausgabename darf eine beliebige Endung haben; die App schreibt zuerst `<name>.chd.part`.
- `--splitbin` schreibt `Name (Track N).bin` je Track. Bei nur einem Track benennt die App die Datei auf den Redump-Namen `Name.bin` um und passt die CUE an (`export.normalize_single_track`).
- Beim Zurückwandeln einer GD-ROM als GDI heißen die Tracks `<name>01.bin`, `<name>02.raw` …
- Eine nackte `.bin` ohne CUE ist kein gültiger Eingang für `createcd` (im Test hing der Aufruf).
- chdman komprimiert mit allen Kernen (Begrenzung mit `-np`).

## Ausgabe

- Fortschritt auf der Standardausgabe, mit `\r` überschrieben: `Compressing, 54.1% complete... (ratio=89.1%)`, `Verifying, 0.0% complete...`, `Extracting, …% complete...`. `chd.parse_progress` liest die Prozentzahl.
- Erfolg beim Prüfen: `Raw SHA1 verification successful!` / `Overall SHA1 verification successful!`.
- Fehler: eine aussagekräftige Zeile (z. B. `Error reading CHD file (…): Decompression error`), danach `Fatal error occurred: 1` – die App zeigt die Zeile davor.

## CHD-Kopf (Version 5)

`chd.read_header` liest ohne chdman:

| Byte | Inhalt |
|---|---|
| 0–7 | Kennung `MComprHD` |
| 12–15 | Version (Big Endian); bei Version ≠ 5 liest `read_header` keine Medienart |
| 32–39 | Inhaltsgröße unkomprimiert (`logical size`) |
| 48–55 | Versatz des ersten Metadaten-Eintrags |

Metadaten-Eintrag: 4 Byte Tag, 1 Byte Flags, 3 Byte Länge, 8 Byte Versatz des nächsten Eintrags, danach die Daten. Die Medienart ergibt sich aus dem Tag:

| Tag | Medium |
|---|---|
| `CHT2`, `CHTR`, `CHCD` | CD |
| `CHGD`, `CHGT` | GD-ROM |
| `DVD ` | DVD |
| andere (z. B. `GDDD`) | keine Disc (z. B. Festplatte) |
