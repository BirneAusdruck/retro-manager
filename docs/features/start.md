# Start und Einrichtung

## Startablauf

Gesteuert vom `StartupController`; jeder Schritt meldet Erfolg oder Fehler per Signal.

1. Startbild zeigen (mindestens 1,5 s, `SPLASH_MIN_DURATION_MS`), dann beginnt der Ablauf in der laufenden Event-Loop.
2. Konfiguration laden: HDD-Pfad und RomM-Benutzer aus der INI, Passwort aus dem Schlüsselbund. Ist der Schlüsselbund nicht erreichbar → Fehlerdialog.
3. Fehlen Angaben → **Einrichtungsdialog**.
4. Prüfen, ob Docker installiert ist und läuft.
5. Prüfen, ob die HDD wirklich eingehängt ist – nicht nur, ob der Ordner existiert. Ein leerer Mount-Ordner existiert auch ohne Platte; `mount_check.is_on_mounted_drive` erkennt, dass er dann auf dem Wurzeldateisystem liegt.
6. `docker/.env` schreiben: HDD-Pfad, Port, DB-Passwörter und Auth-Schlüssel aus dem Schlüsselbund (beim ersten Start einmalig erzeugt). Zugänge zu Metadaten-Diensten schreibt die App noch nicht ([specs/configuration.md](../specs/configuration.md#dockerenv)).
7. `docker compose up -d` asynchron starten, Ladebildschirm zeigen.
8. Heartbeat `GET /api/heartbeat` alle 2 s abfragen, Zeitlimit 30 Minuten (der erste Start braucht wegen Datenbank-Migrationen 15–20 Minuten).
9. Gibt es noch keinen Admin, legt die App ihn mit den Angaben aus dem Einrichtungsdialog an; dann Anmeldung. Wird der Admin abgelehnt oder schlägt die Anmeldung fehl → zurück zum Einrichtungsdialog mit Hinweistext.
10. Hauptfenster zeigen und die RomM-Oberfläche laden (automatische Anmeldung per Skript).

Beim Beenden (`aboutToQuit`): `docker compose stop` (nicht `down`, damit Container und Daten bleiben), laufende Igir-, chdman-, Archiv- und Export-Vorgänge abbrechen, Übertragungen beenden.

Die App beendet sich nicht automatisch, wenn kurz kein Fenster offen ist (`setQuitOnLastWindowClosed(False)`), sondern nur, wenn der Nutzer Hauptfenster, Ladebildschirm oder Einrichtungsdialog schließt.

## Einrichtungsdialog

Drei Angaben, jeweils mit Info-Symbol (Tooltip) links vor der Beschriftung:

- **HDD-Ordner** – Wurzel der Bibliothek, wird in RomM als `/romm/library` eingebunden
- **RomM-Benutzer** und **RomM-Passwort** – bei einer neuen RomM-Installation wird damit der erste Admin angelegt; das Passwort braucht mindestens 6 Zeichen

Zugänge zu Metadaten-Diensten (IGDB, ScreenScraper, Cover-Quellen) werden beim Start nicht abgefragt; sie lassen sich direkt in RomM einrichten (später auch in den Einstellungen der App).

Im Entwicklungsbetrieb (Start aus dem Quellcode, `config.is_dev_build()`) zeigt der Dialog oben rechts einen Knopf **Dev**, der Testwerte einträgt (Konstanten `DEV_*` in `widgets/setup_dialog.py`).

## Fehler beim Start

Scheitert ein Schritt (kein Docker, HDD nicht eingehängt, `.env` nicht schreibbar, Zeitlimit …), schließt der Ladebildschirm und der **Startfehler-Dialog** zeigt die Meldung mit den Knöpfen „Erneut versuchen“ und „Beenden“. Er öffnet sich verzögert (`QTimer.singleShot(0, …)`), damit er nicht innerhalb eines anderen Dialogs aufgeht. Fehler werden zusätzlich geloggt.
