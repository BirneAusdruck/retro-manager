# Einstellungen (Reiter „Einstellungen“)

Platzhalter: Der Reiter hat noch keine Funktion und zeigt nur einen Erklärungstext, was hier künftig entstehen soll. Name und Funktion des Reiters stehen noch nicht fest.

## Bedienung

- Überschrift „Bibliothek prüfen und reparieren“.
- Erklärungstext: Der Reiter sei noch in Arbeit; künftig soll die App die Bibliothek mit einem Klick prüfen und die nötigen Aufgaben der einzelnen Werkzeuge automatisch auswählen.
- Hinweis, dass die Werkzeuge bis dahin einzeln in ihren Reitern zur Verfügung stehen.
- Keine Eingaben, Knöpfe oder Aktionen.

## Aufbau

| Schicht | Datei | Rolle |
|---|---|---|
| View | `widgets/settings_panel.py` | `SettingsPanel`: drei `QLabel` (`#settingsTitle`, `#settingsPlaceholder`, `#settingsHint`), ohne Controller |
| View | `widgets/main_window.py` | Legt den Reiter „Einstellungen“ als letzten Reiter an und fügt `SettingsPanel()` in den `QStackedWidget` ein |

Der Reiter nutzt keinen Controller. Insbesondere hat er nichts mit `controllers/settings_controller.py` zu tun: `SettingsController` lädt und speichert die Konfiguration der ganzen App und wird von Einrichtungsdialog und den übrigen Reitern genutzt (INI-Schema: [specs/configuration.md](../specs/configuration.md)).

## Status

- **Real getestet:** entfällt, der Reiter hat keine Funktion.
- **Geplant:** Themen „Bibliothek aufräumen“ und „Einstellungen“ in der [Roadmap](../roadmap.md#themen).
