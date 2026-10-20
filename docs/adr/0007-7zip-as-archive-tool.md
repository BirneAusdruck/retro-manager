# ADR 0007: 7-Zip als Archivwerkzeug

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Für den Archive-Reiter sollten alle gängigen Formate (7z, ZIP, RAR, TAR …) entpackt und ZIP/7z erzeugt werden können, mehrere gleichzeitig. Python-Bibliotheken (zipfile, tarfile, py7zr) decken RAR nicht ab und py7zr ist langsam und kann nicht jede 7z-Variante.

## Entscheidung

- Der Archive-Reiter nutzt die **7-Zip-Kommandozeile** (offizieller Build `7zz`, ab Version 21 auch für Linux), als externes Werkzeug unter `tools/7zip/` ([ADR 0005](0005-external-tools-not-bundled.md)).
- chdman- und Export-Reiter entpacken 7z/ZIP weiterhin selbst über py7zr/zipfile (mit Abbruch im Thread); sie bekommen daher nur diese beiden Archivarten (`library.is_disc_source`).

## Folgen

- Entpacken: praktisch alle Formate einschließlich RAR5 und mehrteiliger Archive; Packen: ZIP und 7z. RAR kann nicht erzeugt werden.
- Schnell und mehrkernig; Fortschritt wird aus der Prozentausgabe gelesen.
- Ein weiteres externes Programm, das installiert bzw. heruntergeladen werden muss.
