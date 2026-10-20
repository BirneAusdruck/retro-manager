# ADR 0004: RomM in Docker, zunächst nur Docker Engine

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

RomM wird als Container-Stack (RomM + MariaDB) ausgeliefert. Zur Wahl standen Docker und Podman; die Entwicklung läuft unter SteamOS in einer Distrobox.

## Entscheidung

- RomM läuft über `docker compose` mit `docker/docker-compose.yml`; die App startet (`up -d`) und stoppt (`stop`, nicht `down`) den Stack selbst.
- Unterstützt wird zunächst nur **Docker Engine** (Linux, ohne `sudo` nutzbar: Gruppe `docker` oder rootless); unter Windows später Docker Desktop mit WSL2.
- Podman ist für später vorgemerkt.
- Docker wird nicht mitgeliefert, sondern beim Start geprüft.
- Keine Dockerfile für die Qt-App selbst – Docker nur für RomM.
- Der Docker-Aufruf ist an einer Stelle gekapselt (`core/docker_compose.py`, `controllers/docker_controller.py`).

## Folgen

Nutzer müssen Docker selbst installieren. Eine zweite Laufzeit (Podman) wäre an genau einer Stelle zu ergänzen.
