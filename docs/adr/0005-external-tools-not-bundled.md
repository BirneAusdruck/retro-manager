# ADR 0005: Externe Werkzeuge nicht mitliefern, sondern bei Bedarf laden

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Igir und chdman (MAME) stehen unter GPL, 7-Zip unter LGPL mit unRAR-Einschränkung. Das Repository ist öffentlich; die App soll portabel ausgeliefert werden (AppImage, Windows-Ordner). Werkzeuge ins Paket zu bündeln, würde Lizenzpflichten und Paketgröße mit sich bringen und Updates an App-Releases koppeln.

## Entscheidung

- Externe Werkzeuge laufen als eigene Prozesse (`QProcess`), ihre Argumentlisten entstehen in `core/tools.py`.
- Sie werden **nicht** ins Paket gepackt. Die fertige App lädt sie bei Bedarf per Knopf (z. B. „Igir herunterladen“) von den offiziellen Releases nach `tools/<werkzeug>/` – mit fest eingetragener Version und Prüfsumme.
- Rückfallebene ohne Internet: Der Nutzer legt die Programmdatei selbst nach `tools/<werkzeug>/`. Während der Entwicklung geschieht das von Hand.
- chdman und 7-Zip werden zusätzlich im PATH gesucht.
- Fehlt ein Werkzeug, sperrt der zuständige Reiter seine Aktionen und zeigt einen Hinweis.

## Folgen

- Die Download-Knöpfe sind noch nicht umgesetzt (siehe Roadmap).
- Lizenztexte der Komponenten werden trotzdem beigelegt; vor einer Veröffentlichung sind die Lizenzen genau zu prüfen.
