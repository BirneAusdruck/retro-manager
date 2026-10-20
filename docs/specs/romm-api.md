# RomM-Schnittstelle (RomM 5.4.0)

Aufbau der Anfragen und Auswertung der Antworten in `core/romm_api.py`, Ausführung in `controllers/romm_controller.py` (`QNetworkAccessManager`, Zeitlimit 10 s je Anfrage).

## Endpunkte

| Endpunkt | Zweck |
|---|---|
| `GET /api/heartbeat` | Bereitschaft abfragen (Takt und Zeitlimit: [features/start.md](../features/start.md#konfiguration)). `SYSTEM.SHOW_SETUP_WIZARD = true` heißt: es gibt noch keinen Admin. |
| `POST /api/users` | Ersten Admin anlegen (Rolle `admin`). Leere E-Mail wird akzeptiert; Passwort mindestens 6 Zeichen (`MIN_PASSWORD_LENGTH`), sonst HTTP 400. |
| `POST /api/token` | Anmeldung der App per OAuth2-Password-Grant (Formular mit `scope`, siehe unten); Antwort enthält Access- und Refresh-Token. Erneuern per Refresh-Grant. |
| `GET /api/platforms/supported` | Alle von RomM unterstützten Plattformen (Slug, Name, Kategorie) für „DATs aktualisieren“. Bei HTTP 401 wird das Token erneuert und die Anfrage wiederholt. |
| `POST /api/login` | Anmeldung der **Weboberfläche** per HTTP-Basic mit CSRF-Header `x-csrftoken` aus dem Cookie `romm_csrftoken`; läuft als Skript in der eingebetteten Seite (`web_login_script`), nur wenn noch keine Sitzung aktiv ist. |

Fehlertexte von RomM (`detail`) werden ausgewertet (`romm_api.error_detail`) und dem Nutzer angezeigt, z. B. wenn das Anlegen des Admins abgelehnt wird.

## Token-Scopes

Je Lese- und Schreibrecht für `me`, `roms`, `roms.user`, `platforms`, `collections`, `assets`, `firmware`, `users` sowie `tasks.run` (`romm_api.TOKEN_SCOPES`).

## Hinweise

- Größere Uploads über die Weboberfläche kamen im Test nur teilweise an (von einer ganzen PS1-Sammlung nur 15 Spiele) – Ursache noch nicht untersucht.
