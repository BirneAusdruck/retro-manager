# ADR 0003: RomM als Herzstück, Bibliotheksstruktur A für alle Werkzeuge

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Die Sammlung braucht eine Verwaltung mit Metadaten, Covern und Weboberfläche. Eine eigene zu bauen wäre aufwendig; RomM leistet das bereits. RomM erkennt Plattformen allerdings nur über Ordnernamen und unterstützt zwei Ordnerstrukturen.

## Entscheidung

- RomM ist das Herzstück; seine Weboberfläche wird im Hauptfenster eingebettet, eigene Funktionen kommen als zusätzliche Reiter.
- Verbindlich ist **RomM-Struktur A**: `<HDD>/roms/<plattform>/[<Spiel>/]`, daneben `bios/`, `dats/`, `exports/`. Struktur B (`<plattform>/roms/`) wird nicht verwendet.
- **Jedes** integrierte Werkzeug (Igir, chdman, 7-Zip, Export) liest und schreibt nach dieser Struktur. Plattformordner sind RomM-Slugs; Igirs Token `{romm}` liefert sie.
- Metadaten-Dienste (IGDB, ScreenScraper …) richtet der Nutzer in RomM ein; beim Start der App sind sie nicht nötig.
- Die Version ist fest eingetragen (`rommapp/romm:5.4.0`); Updates nur durch bewusstes Ändern des Tags.

## Folgen

- Alles, was die App ablegt, erscheint nach einem Scan direkt in RomM.
- Dateien, die über RomM hochgeladen werden, sind zunächst weder geprüft noch richtig benannt – dafür ist „Bibliothek aufräumen“ vorgemerkt.
- Hilfsdaten der App (`dats/`, `exports/`, `.retro-manager-tmp/`) liegen außerhalb von `roms/`, damit RomM sie ignoriert.
