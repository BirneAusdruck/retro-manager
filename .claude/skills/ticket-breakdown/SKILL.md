---
name: ticket-breakdown
description: Zerlegt eine Feature-Spec aus docs/specs/ in kleine GitHub-Issues (Feature-Issue mit Aufgaben als Sub-Issues) nach den Vorlagen in .github/ISSUE_TEMPLATE/. Aufruf mit dem Pfad der Spec, z. B. /ticket-breakdown docs/specs/bibliothek-aufraeumen.md
disable-model-invocation: true
argument-hint: "<pfad-zur-spec> [milestone]"
---

# Spec in Tickets zerlegen

Eingabe: $ARGUMENTS (Pfad zur Spec, optional ein Milestone). Fehlt der Pfad, nachfragen.

Grundsatz: **Erst vorschlagen, dann anlegen.** Kein Issue wird erstellt, bevor der Nutzer die Liste freigegeben hat.

## Ablauf

1. **Spec lesen.** Enthält sie offene Fragen, die die Zerlegung beeinflussen, diese zuerst stellen und abbrechen, bis sie geklärt sind.
2. **Kontext lesen:** die betroffenen `docs/features/…`, bei neuen Modulen `docs/architekture.md`, und den vorhandenen Code der betroffenen Bereiche. Ziel: realistisch einschätzen, welche Dateien sich ändern.
3. **Bestehende Issues prüfen:** `gh issue list --search "<stichworte>" --state all` – gibt es das Feature-Issue oder Teile davon schon?
4. **Zerlegen** nach den Regeln unten.
5. **Vorschlag zeigen** als nummerierte Liste: Titel, Ziel in einem Satz, Schichten, wichtigste Akzeptanzkriterien, Abhängigkeiten. Auf Freigabe oder Änderungswünsche warten.
6. **Anlegen** (siehe „Issues anlegen“).
7. **Abschluss:** Die Nummer des Feature-Issues oben in der Spec eintragen (`Feature-Issue: #<nr>`) und die angelegten Issues mit Nummer und Titel auflisten.

## Regeln für die Zerlegung

- **Eine Aufgabe = eine Claude-Session.** Faustregel: ein klares Ziel, höchstens ~5 geänderte Dateien, höchstens ~6 Akzeptanzkriterien. Sonst aufteilen.
- **Jede Aufgabe ist für sich prüfbar** und hinterlässt den Code lauffähig mit grünen Tests.
- **Reihenfolge entlang der Schichten:** zuerst Model-Logik in `core/` mit Unit-Tests, dann Controller, dann View. Kleine Controller- und View-Änderungen dürfen in einer Aufgabe zusammengefasst werden; `core/`-Logik mit nennenswertem Umfang bekommt eine eigene Aufgabe.
- **Abhängigkeiten ausdrücklich nennen** („Abhängig von #…“), möglichst lineare Kette statt Geflecht.
- **„Nicht Teil dieser Aufgabe“ immer ausfüllen**, damit die Grenzen zu den Nachbaraufgaben klar sind.
- Akzeptanzkriterien prüfbar formulieren (Ja/Nein). Die Standardkriterien aus der Vorlage (Tests, Ruff, `document-feature`) immer übernehmen; `document-feature` nur bei der letzten Aufgabe eines Features, sofern sich davor kein dokumentiertes Verhalten ändert.
- Spekulative Aufgaben („könnte man später …“) nicht anlegen, sondern in der Spec bzw. `docs/roadmap.md` vormerken.

## Issues anlegen

Maßgeblich für den Aufbau sind die Vorlagen `.github/ISSUE_TEMPLATE/1-feature.yml` und `2-aufgabe.yml`; vor dem Anlegen lesen. Der Text verwendet deren Feldnamen als `###`-Überschriften (so rendert GitHub auch die Formulare), z. B. für eine Aufgabe:

```markdown
### Ziel
…
### Kontext
- Spec: docs/specs/<name>.md
- Feature-Doku: docs/features/<name>.md
### Betroffene Schichten
Model (core/), Controller (controllers/)
### Akzeptanzkriterien
- [ ] …
### Nicht Teil dieser Aufgabe
…
### Hinweise
Abhängig von #…
```

Befehle (Text jeweils als Datei im Arbeitsordner schreiben, nicht inline quoten):

```bash
# Feature-Issue, falls noch nicht vorhanden
gh issue create --title "Feature: <name>" --label feature --label "bereich:<x>" --body-file /tmp/feature.md [--milestone "<m>"]

# Aufgabe
gh issue create --title "<titel>" --label aufgabe --label "bereich:<x>" --body-file /tmp/aufgabe-1.md [--milestone "<m>"]

# Als Sub-Issue an das Feature hängen (REST braucht die numerische id, nicht die Nummer)
child_id=$(gh api "repos/{owner}/{repo}/issues/<aufgabe-nr>" --jq .id)
gh api -X POST "repos/{owner}/{repo}/issues/<feature-nr>/sub_issues" -F sub_issue_id="$child_id"
```

Schlägt das Verknüpfen fehl, stattdessen „Teil von #<feature-nr>“ unter „Hinweise“ eintragen und im Feature-Issue eine Aufgabenliste `- [ ] #<nr>` ergänzen. Fehlt ein Label, `bash .github/labels.sh` vorschlagen statt Labels eigenmächtig anzulegen.

Titel: kurz, im Imperativ, ohne Präfix, z. B. „Igir-Lauf über roms/ im Model planen“.
