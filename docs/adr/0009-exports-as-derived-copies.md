# ADR 0009: Exporte für Hardware als abgeleitete, löschbare Kopien

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Echte Hardware (zuerst PS3 mit webMAN MOD, später PS2/OPL und Xbox 360) braucht andere Formate und Ordner als das Archiv. Würde man die Bibliothek dafür anpassen, ginge die eine saubere Quelle verloren.

## Entscheidung

- Die Bibliothek unter `roms/` bleibt die einzige Quelle. Für ein Zielgerät leitet die App Kopien im passenden Format ab (entpacken, aus CHD zurückwandeln, PS3-ISOs entschlüsseln) und legt sie in `<HDD>/exports/<profil>/` in der Ordnerstruktur des Geräts ab.
- Ein Manifest hält fest, welche Dateien die App geschrieben hat und ob sie übertragen sind; „Export löschen“ entfernt nur diese.
- Zielgeräte sind Profile (`DeviceProfile`) in `core/devices.py`; ein neues Gerät ist ein neues Profil.
- Übertragen wird getrennt über den FTP-Reiter, an den der Export Aufträge schickt.

## Folgen

- Der Export braucht zusätzlichen Platz auf der HDD, ist aber jederzeit löschbar und neu erzeugbar.
- Aufbereiten und Senden sind zwei Schritte (eine Pipeline „aufbereiten und senden“ ist denkbar).
