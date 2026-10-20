# FTP, FTPS und SFTP

`core/remote.py` kapselt alle Protokolle hinter der Schnittstelle `RemoteFs`; Fehler beider Implementierungen werden zu `RemoteError`. Wie der FTP-Reiter sie nutzt: [features/ftp.md](../features/ftp.md).

## FTP und FTPS (`FtpFs`, ftplib)

- FTPS ist explizites TLS (`FTP_TLS`) mit verschlüsseltem Datenkanal (`prot_p`).
- Ohne Benutzer wird `anonymous` verwendet.
- Listing per `MLSD`; lehnt der Server das ab, per `LIST` (Unix- und DOS-Format, `parse_list_line`).
- Fortsetzen über den Startpunkt (`REST`) bei `STOR` bzw. `RETR`.
- **Achtung:** Nach einem Listing steht ftplib auf `TYPE A`; viele Server verweigern `SIZE` im Textmodus. Deshalb setzt `FtpFs.size` vor `SIZE` wieder `TYPE I`.

## SFTP (`SftpFs`, paramiko)

- Nur Passwort-Anmeldung (kein SSH-Agent, keine Schlüsseldateien).
- Host-Keys „trust on first use“: beim ersten Verbinden in `known_hosts` gemerkt ([specs/configuration.md](configuration.md#ablageorte)); ein geänderter Key ergibt einen Fehler mit dem Hinweis, den Eintrag aus `known_hosts` zu entfernen, wenn der Wechsel gewollt ist.

## Gemeinsam

- Zeitlimit für Verbindung und Befehle 30 s (`TIMEOUT_SECONDS`), Blockgröße 1 MiB.
