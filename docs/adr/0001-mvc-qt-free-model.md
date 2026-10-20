# ADR 0001: MVC mit Qt-freiem Model

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Die App verbindet viele Dinge: eine Weboberfläche (RomM), externe Programme, Netzwerk, Dateioperationen auf einer HDD. Diese Logik soll ohne laufende Oberfläche testbar sein, und die Oberfläche soll sich ändern lassen, ohne die Logik anzufassen.

## Entscheidung

Strikte Trennung in drei Schichten mit Abhängigkeiten in nur eine Richtung: `widgets/` (View) → `controllers/` → `core/` (Model). Das Model ist frei von Qt; alles Asynchrone liegt in den Controllern. Die geltenden Regeln im Einzelnen: [architecture.md](../architecture.md#schichten-model--view--controller).

## Folgen

- Die Logik (Befehlsaufbau, Planung, Dateiregeln) ist mit über 250 Unit-Tests abgedeckt, ohne Qt.
- Etwas mehr Code: Regeln, die eine View braucht (z. B. Zielformat eines Systems), gehen über eine Controller-Methode.
- `controllers/` und `widgets/models/` ergänzen die ursprünglich geplante Ordnerstruktur.
