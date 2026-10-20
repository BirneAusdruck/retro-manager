# PS3-ISOs entschlüsseln

Redump-Dumps von PS3-Discs sind verschlüsselt; webMAN braucht entschlüsselte ISOs. `core/ps3_iso.py` entschlüsselt sie wie PS3Dec, in reinem Python mit `cryptography` (~260 MB/s).

## Disc-Key

- Quelle: Redump-Keys (`dats/redump-keys/ps3/`, von „DATs aktualisieren“ geladen).
- Zuordnung über den Dateinamen: `<Spielname>.key` bzw. `.dkey` passend zum Namen der ISO (`find_key`) – die ISO muss also nach Redump benannt sein.
- Formate: 16 Byte binär oder Text mit 32 Hex-Zeichen (`read_key`).

## Aufbau

- Sektorgröße 2048 Byte.
- Sektor 0 enthält die Regionstabelle: Anzahl der unverschlüsselten Bereiche (4 Byte Big Endian), dann ab Byte 8 je Bereich erster und letzter Sektor (je 4 Byte). Die **Lücken** zwischen den unverschlüsselten Bereichen sind verschlüsselt (`parse_encrypted_regions`).
- Eine leere oder unplausible Tabelle (Anzahl 0, zu viele Bereiche, überlappend) ergibt einen Fehler – meist ist die Datei keine PS3-ISO.

## Verfahren

- AES-128-CBC je Sektor; der IV ist die Sektornummer als 16-Byte-Big-Endian-Zahl.
- Umsetzung: AES-ECB über alle Blöcke eines Sektorbereichs, danach XOR mit dem vorherigen Chiffreblock bzw. dem IV – so lassen sich viele Sektoren in einem Aufruf entschlüsseln.
- Reine Null-Sektoren waren nie verschlüsselt und bleiben unverändert.
- Gelesen und geschrieben wird in Blöcken von 1 MiB (512 Sektoren); Fortschritt und Abbruch je Block.

## Einschränkungen

- Nicht geprüft wird, ob eine ISO bereits entschlüsselt ist. Nur Redump-benannte Original-Dumps mit Key entschlüsseln lassen; ohne passenden Key übernimmt der Export die ISO unverändert.
- Mit einer echten PS3-ISO noch nicht getestet (nur mit selbst erzeugten Testabbildern).
