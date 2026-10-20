# FTP (Reiter „FTP“)

Zweiteiliger Dateimanager (links lokal, rechts das Gerät) mit Übertragungs-Warteschlange. Nutzbar für alle Geräte mit FTP/FTPS/SFTP – Konsolen ebenso wie NAS oder PC. Der Reiter „Export vorbereiten“ schickt seine Aufträge hierher.

## Verbindungen

- Gespeicherte Verbindungen: Name, Protokoll (FTP, FTPS, SFTP), Adresse, Port, Benutzer, Startordner. Anlegen, Bearbeiten, Testen und Löschen über „Verwalten …“ (`ConnectionDialog`).
- In der INI als `[connection:<id>]`; das **Passwort** im Schlüsselbund unter `connection:<id>` ([specs/configuration.md](../specs/configuration.md)).
- Eine früher gespeicherte PS3-Adresse (`[ps3]`) wird einmalig als Verbindung „PS3“ übernommen.
- SFTP-Host-Keys: beim ersten Verbinden gemerkt (`known_hosts` neben der App, „trust on first use“); ein geänderter Key ergibt einen Fehler mit Hinweis.

## Bedienung

- Links lokaler Ordnerbaum (Start: `<HDD>/exports`), rechts der Ordner auf dem Gerät.
- Hochladen, Herunterladen, Ordner anlegen, Umbenennen, Löschen (rekursiv), Aktualisieren.
- Unten die Warteschlange mit Fortschritt je Auftrag; einzelne Aufträge abbrechen, erledigte entfernen.

## Übertragung

- `TransferController`: Durchsuchen und Warteschlange haben **je eine eigene Verbindung und einen eigenen Thread-Pool mit einem Thread**, damit eine laufende Übertragung das Durchsuchen nicht blockiert.
- Aufträge: Hochladen (fertige Liste von Datei → Zielpfad, z. B. vom Export, oder Dateien/Ordner rekursiv) und Herunterladen (rekursiv).
- Gleich große Ziele werden übersprungen, kleinere fortgesetzt; danach wird die Größe geprüft.
- Auftragszustände: wartet, läuft, fertig, fehlgeschlagen, abgebrochen. Jeder Auftrag erscheint in der [Aktivitätsanzeige](activity.md).

## Technik

- `core/remote.py`: gemeinsame Schnittstelle `RemoteFs` für `FtpFs` (ftplib, mit `FTP_TLS` und `prot_p` für explizites FTPS) und `SftpFs` (paramiko).
- FTP-Listing per `MLSD`, sonst `LIST` (Unix- und DOS-Format, `parse_list_line`).
- Achtung: Nach einem Listing steht ftplib auf `TYPE A`; vor `SIZE` wird wieder `TYPE I` gesetzt.

## Tests

Gegen echte lokale Server: pyftpdlib für FTP/FTPS (mit selbst erzeugtem Zertifikat) und asyncssh für SFTP. Für pyftpdlib je Test ein `FTPServer` mit eigener `IOLoop` – `ThreadedFTPServer` bzw. eine gemeinsame `IOLoop` führten zu sporadischen Abbrüchen.
