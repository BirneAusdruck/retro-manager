---
name: document-feature
description: Dokumentiert ein umgesetztes oder geändertes Feature (Reiter, Funktion, Ablauf) in docs/features/<name>.md inklusive Mermaid-Klassen- und Sequenzdiagramm und zieht die übrigen Docs (specs, Architektur, Roadmap, ADRs) nach. Verwenden, sobald ein Feature oder Ticket fertig umgesetzt ist, wenn sich Verhalten, Module oder Abläufe geändert haben, wenn die Doku eines Features fehlt oder veraltet ist, oder wenn der Nutzer ein Feature erklärt, visualisiert oder dokumentiert haben möchte – auch wenn er nicht ausdrücklich „Doku“ sagt.
---

# Feature dokumentieren

Ziel: Die Doku beschreibt den **Ist-Zustand des Codes**, kurz und überprüfbar. Sie dient Menschen zum Verstehen und Claude als Kontext für spätere Änderungen. Veraltete Doku ist schlimmer als fehlende, deshalb wird immer gegen den Code geprüft.

## Ablauf

1. **Umfang klären.** Welches Feature? Was hat sich geändert? Bei Unklarheit `git diff` bzw. `git log` der letzten Änderungen ansehen. Feature-Namen wie in der Tabelle in `docs/README.md` verwenden (z. B. `chdman`, `export`, `ftp`).
2. **Bestehende Doku lesen:** `docs/features/<name>.md`, falls vorhanden, und die zugehörige Spec in `docs/specs/`.
3. **Code lesen, nicht erinnern.** Die beteiligten Dateien in `core/`, `controllers/`, `widgets/` und `widgets/models/` öffnen. Klassen-, Methoden- und Signalnamen nur übernehmen, wenn sie im Code so existieren.
4. **Feature-Doku schreiben oder aktualisieren** nach `assets/template.md`. Bestehende Doku gezielt anpassen statt neu schreiben; Abschnitte, die nicht zutreffen, weglassen.
5. **Übrige Docs nachziehen** (nur, was betroffen ist):
   - Regeln, Formate, Dateiablage, externe Schnittstellen → `docs/specs/…`
   - neue oder umbenannte Module, neue Code-Regeln → `docs/architecture.md`
   - Erledigtes, noch nicht real Getestetes, neue Themen oder bekannte Probleme → `docs/roadmap.md`, je ein Satz; Umsetzungsdetails gehören ins GitHub-Issue
   - neue Grundsatzentscheidung (betrifft mehr als ein Feature, schwer umkehrbar) → neuer ADR in `docs/adr/` mit nächster freier Nummer
   - neues Feature → Eintrag in der Tabelle „Wo steht was?“ in `docs/README.md` (Dateiname englisch, kebab-case)
6. **Prüfen:** Stimmen alle genannten Pfade, Klassen und INI-Schlüssel? Rendern die Mermaid-Blöcke (siehe unten)?
7. **Kurz berichten**, welche Dateien angepasst wurden. **Nicht committen**, außer der Nutzer verlangt es.

## Schreibregeln

- Deutsch, sachlich, im Stil der vorhandenen Docs.
- Auf Dateien und Klassen **verweisen** statt Code zu kopieren. Code-Schnipsel nur, wenn sie ein Format zeigen (z. B. Argumentliste, INI-Abschnitt).
- Keine Doppelungen: Jede Information steht an genau einer Stelle (Zuordnung in `docs/README.md`, Abschnitt „Docs pflegen“). Was in `specs/`, `architecture.md` oder `development.md` steht, wird verlinkt, nicht wiederholt.
- Geplantes und Offenes gehört grob in `roadmap.md` und ausführlich ins GitHub-Issue, nicht in die Feature-Doku; sie verlinkt dorthin. Der Abschnitt „Status“ nennt nur, was real getestet ist.
- Länge: so kurz wie möglich, Richtwert unter 150 Zeilen pro Feature.

## Diagramme (Mermaid)

Standard pro Feature: **ein Klassendiagramm** (Struktur und Pattern) und **ein Sequenzdiagramm** (Hauptablauf). Weitere nur bei Bedarf:

- `stateDiagram-v2` – wenn das Feature Zustände hat (z. B. wartend → läuft → geprüft → fertig)
- `flowchart` – für verzweigte Logik innerhalb einer Funktion
- Datenfluss – als `flowchart LR` mit Quellen, Verarbeitung und Zielen (HDD-Ordner, Gerät)

Regeln:

- **Schichten sichtbar machen:** Im Klassendiagramm die Klassen mit `<<View>>`, `<<Controller>>`, `<<Model>>` bzw. `<<ItemModel>>` kennzeichnen. Abhängigkeiten nur in erlaubter Richtung (View → Controller → Model).
- **Pattern benennen:** Erkennbare Pattern (Factory, Template Method über `GameTableModel`, Strategy über `DeviceProfile`, Observer über Qt-Signale …) im Diagramm per `note` und im Abschnitt „Aufbau“ in einem Satz benennen. Kein Pattern hineininterpretieren, das nicht da ist.
- **Sequenzdiagramm** zeigt den Hauptablauf von der Nutzeraktion bis zum Ergebnis, inklusive Signale zurück an die View. Asynchrone Schritte (`QProcess`, `BackgroundTask`) mit `-)` kennzeichnen. Fehler- und Abbruchpfad als `alt`-Block, wenn er sich wesentlich unterscheidet.
- Nur die für das Feature relevanten Klassen und Methoden, keine vollständigen Klassenlisten. Richtwert: höchstens ~10 Klassen bzw. ~15 Nachrichten pro Diagramm; sonst aufteilen.
- **Syntax-Fallen:** Beschriftungen mit Klammern, Doppelpunkten oder Pfeilen in Anführungszeichen setzen. Generics als `list~LibraryGame~` schreiben. Keine Leerzeichen in Klassennamen.
