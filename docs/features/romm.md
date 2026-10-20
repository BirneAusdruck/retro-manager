# RomM (Reiter „RomM“)

RomM ist das Herzstück der App ([ADR 0003](../adr/0003-romm-as-core.md)): Es verwaltet die Bibliothek, holt Metadaten und Cover und bietet die Weboberfläche. Alle Werkzeuge der App richten sich nach der Ordnerstruktur, die RomM erwartet ([specs/library.md](../specs/library.md)).

## Betrieb

- RomM läuft in Docker ([ADR 0004](../adr/0004-docker-for-romm.md)), gestartet und gestoppt von der App über `docker/docker-compose.yml`.
- Versionen fest eingetragen: `rommapp/romm:5.4.0` und `mariadb:11.4` (mit Healthcheck). Updates bewusst durch Ändern des Tags.
- Port nur lokal: `127.0.0.1:${ROMM_PORT}:8080` (Standard 8080, INI `[romm] port`).
- Einbindung der HDD: `${ROMM_LIBRARY_PATH}:/romm/library`. Daten von RomM (Datenbank, Ressourcen, Redis, Assets, Konfiguration) liegen in benannten Docker-Volumes.
- Hasheous ist eingeschaltet (`HASHEOUS_API_ENABLED`); IGDB, ScreenScraper, SteamGridDB und RetroAchievements sind optional über `.env`-Variablen vorbereitet.
- Der Compose-Projektname ist `retro-manager`.

## Eingebettete Oberfläche

- `widgets/romm_view.py` bettet die Weboberfläche per `QWebEngineView` ein. Cookies und Cache liegen in einem dauerhaften Profil unter `webdata/` neben der App.
- Die App meldet die Oberfläche selbst an (`romm_api.web_login_script`: `POST /api/login` mit HTTP-Basic und CSRF-Header) – der Nutzer sieht keine Anmeldeseite.
- Eigene Funktionen der App kommen als zusätzliche Reiter hinzu, nicht als Eingriff in RomM.

## Hinweise für die Nutzung

- Über die RomM-Oberfläche hochgeladene Dateien landen in `roms/<plattform>/`, werden aber weder gegen DATs geprüft noch umbenannt oder umgepackt (siehe „Bibliothek aufräumen“ in der [Roadmap](../roadmap.md)).
- Nach Änderungen durch die App (z. B. CHD-Umwandlung) muss RomM die Plattform neu einlesen (Scan).
- Metadaten-Anbieter (IGDB, ScreenScraper, …) lassen sich direkt in RomM auswählen und einrichten.

Schnittstellen und Anmeldung im Detail: [specs/romm-api.md](../specs/romm-api.md).
