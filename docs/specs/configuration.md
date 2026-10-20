# Konfiguration und Geheimnisse

Grundsatz: Nicht Geheimes in der INI, Geheimes nur im Systemschlüsselbund ([architecture.md](../architecture.md#konfiguration-und-geheimnisse)).

## Ablageorte

| Was | Wo | Eingecheckt? |
|---|---|---|
| Einstellungen | `retro-manager.ini` neben der Programmdatei (`config.ini_path`) | nein |
| Geheimnisse | Systemschlüsselbund über `keyring` (Linux: Secret Service), Dienst `retro-manager` | – |
| RomM-Umgebung | `docker/.env`, bei jedem Start neu geschrieben, Rechte 0600 | nein |
| SFTP-Host-Keys | `known_hosts` neben der App | nein |
| Weboberfläche (Cookies, Cache) | `webdata/` | nein |
| Externe Programme | `tools/igir/`, `tools/7zip/`, ggf. `tools/chdman/` | nein |
| Igir-Reports | `reports/` | nein |

Neben der Programmdatei heißt: im gepackten Programm der Ordner der Programmdatei, beim Start aus dem Quellcode die Projektwurzel (`config.app_dir`). Auf einem neuen Rechner wandert die INI mit, die Geheimnisse nicht – dann erscheint der Einrichtungsdialog.

## INI-Abschnitte

| Abschnitt | Schlüssel | Standard | Bedeutung |
|---|---|---|---|
| `[archive]` | `hdd_path` | – | Wurzel der Bibliothek auf der Archiv-HDD |
| `[romm]` | `user`, `port` | –, `8080` | RomM-Benutzer, lokaler Port |
| `[jobs]` | `max_parallel` | `2` | gleichzeitige Jobs (Archive-Reiter), im Code `AppConfig.max_parallel_jobs` |
| `[igir]` | `input_dir`, `dat_dir` | – | zuletzt verwendete Ordner im Igir-Reiter |
| `[export]` | `device`, `connection` | `ps3`, – | Zielgerät und Verbindung für „An Gerät senden“ |
| `[chdman]` | `delete_originals` | `true` | Originale nach geprüfter Umwandlung löschen |
| `[archives]` | `format`, `level`, `delete_originals` | `zip`, `normal`, `false` | Packformat (`zip`/`7z`), Stufe (`fast`/`normal`/`max`), Originale löschen |
| `[connection:<id>]` | `name`, `protocol`, `host`, `port`, `user`, `start_dir` | – | gespeicherte FTP/FTPS/SFTP-Verbindung |
| `[ps3]` | `host`, `port` | –, `21` | alt; wird einmalig als Verbindung „PS3“ übernommen |

`save_config` und `save_connections` lesen die Datei vorher ein und behalten die Abschnitte des jeweils anderen.

## Schlüsselbund-Einträge (Dienst `retro-manager`)

| Eintrag | Inhalt |
|---|---|
| `romm_password` | Passwort des RomM-Benutzers |
| `db_password`, `db_root_password` | MariaDB-Passwörter, von der App einmalig erzeugt |
| `romm_auth_secret_key` | `ROMM_AUTH_SECRET_KEY`, von der App einmalig erzeugt |
| `connection:<id>` | Passwort einer gespeicherten Verbindung |

Ist der Schlüsselbund nicht erreichbar, bricht der Start mit einer Meldung ab.

## `docker/.env`

Wird bei jedem Start aus INI und Schlüsselbund erzeugt und steht in `.gitignore`:

| Variable | Quelle |
|---|---|
| `ROMM_LIBRARY_PATH` | `[archive] hdd_path` |
| `ROMM_PORT` | `[romm] port` |
| `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `ROMM_AUTH_SECRET_KEY` | Schlüsselbund |
| `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET`, `SCREENSCRAPER_USER`, `SCREENSCRAPER_PASSWORD`, `STEAMGRIDDB_API_KEY`, `RETROACHIEVEMENTS_API_KEY` | optional, in `docker-compose.yml` vorbereitet; Eingabe in der App ist vorgemerkt |
