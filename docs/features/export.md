# Export vorbereiten (Reiter „Export vorbereiten“)

Das Archiv bleibt die eine saubere Quelle; für echte Hardware leitet die App daraus **Exporte im Format des Zielgeräts** ab. Sie liegen in einem eigenen, jederzeit löschbaren Ordner `<HDD>/exports/<profil>/` (von RomM ignoriert) und gehen per FTP auf das Gerät.

## Zielgeräte

- Auswahl per Dropdown; Profile in `core/devices.py` (`DeviceProfile`: Plattformen → Ordner im Ziel, `remote_root`, Plattformen mit einem Ordner je Spiel, PS3-Entschlüsselung, Standardprotokoll und -port).
- Noch nicht umgesetzte Geräte (PS2 mit Open PS2 Loader, Xbox 360) stehen mit `available=False` ausgegraut im Dropdown („kommt später“).
- Gewähltes Gerät und die Verbindung für „An Gerät senden“ stehen in der INI (`[export]`).
- Ein neues Gerät = ein neues `DeviceProfile`, ggf. eigene Schritte in `core/export.py`.

## Ablauf

1. Die Liste zeigt alle Disc-Spiele der Plattformen des Profils (`library.scan_platform`) mit Status „aufbereitet“ / „übertragen“.
2. **Aufbereiten** arbeitet die ausgewählten Discs nacheinander ab; Fehler einzelner Discs brechen den Rest nicht ab. Vorher wird der Platz im Export-Ordner geprüft.
3. **Export löschen** entfernt nur die Dateien, die laut Manifest von der App geschrieben wurden; eigene Dateien im Export-Ordner bleiben.
4. **An Gerät senden** stellt die aufbereiteten Dateien mit den Zielpfaden des Profils als Auftrag in die Warteschlange des [FTP-Reiters](ftp.md) (`ExportController.send` → `TransferController.enqueue_upload`) und wechselt dorthin. Nach erfolgreichem Auftrag wird der Status „übertragen“. Noch nicht aufbereitete Spiele werden übersprungen.

Aufbereiten und Senden sind zwei getrennte Schritte.

Das Manifest `exports/<profil>/.retro-manager-export.json` führt je Disc die geschriebenen Dateien und den Status. Abbruch oder Fehler räumen halbfertige Dateien sofort weg.

## Quellen

| Quelle | Schritt |
|---|---|
| 7z / ZIP | entpacken (7z über `py7zr` mit eigener `WriterFactory`, damit „Abbrechen“ im Entpack-Thread greift; unsichere Pfade im Archiv → Fehler) |
| ISO | kopieren |
| BIN/CUE | CUE samt aller BINs kopieren |
| CHD | chdman `extractcd --splitbin` bzw. `extractdvd`; schlägt `extractdvd` bei einer PS2-CHD fehl, folgt `extractcd`. Einzelspur-Discs wie in [specs/chdman.md](../specs/chdman.md). Ohne chdman sind CHD-Einträge gesperrt. |

## Profil PS3 (CFW + webMAN MOD)

- Plattformen: PS1, PS2, PS3, PSP aus `roms/{psx,ps2,ps3,psp}`.
- Ordner im Export und auf dem Gerät (unter `/dev_hdd0/`) wie webMAN sie erwartet:

| Plattform | Ordner | Inhalt |
|---|---|---|
| PS1 | `PSXISO/<Spiel>/` | BIN/CUE, ein Ordner je Spiel |
| PS2 | `PS2ISO/` | ISO |
| PS3 | `PS3ISO/` | ISO (entschlüsselt) |
| PSP | `PSPISO/` | ISO |

- Übertragung über das FTP von webMAN (Port 21, anonym).
- **PS3-ISOs:** Redump-Dumps sind verschlüsselt. Mit dem Disc-Key aus `dats/redump-keys/ps3/` (Zuordnung über den Redump-Namen, also die Datei nach Redump benennen) wird die ISO beim Aufbereiten entschlüsselt ([specs/ps3-iso.md](../specs/ps3-iso.md)); Archive werden dafür zuerst in `PS3ISO/.entpacken/` entpackt. Ohne Key wird die ISO unverändert übernommen, mit Hinweis im Protokoll (Einschränkungen: [specs/ps3-iso.md](../specs/ps3-iso.md#einschränkungen)).

## Status

- **Real getestet:** PS1 (7z → BIN/CUE) und PS2 (7z → ISO) bitgenau gegen Redump, Abbrechen, Export löschen, Senden an einen lokalen FTP-Testserver mit Status „übertragen“.
- **Noch offen:** siehe [Roadmap](../roadmap.md#noch-nicht-real-getestet).
