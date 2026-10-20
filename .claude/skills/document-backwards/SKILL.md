---
name: document-backwards
description: Zieht die Doku bereits umgesetzter Features vollständig nach – für alle Features oder gezielt für einzelne. Nutzt dafür den Skill document-feature, prüft alles gegen den Code und sammelt Unklarheiten und Auffälligkeiten als Fragen an den Nutzer. Aufruf: /document-backwards (alle) oder /document-backwards chdman export
disable-model-invocation: true
argument-hint: "[feature …]"
---

# Doku rückwirkend nachziehen

Eingabe: $ARGUMENTS – ein oder mehrere Feature-Namen. Leer = alle Features.

Auftrag für jedes Feature: **vollständig nachziehen, alles gegen den Code prüfen, Unklarheiten und Auffälligkeiten als Fragen an den Nutzer.** Grundlage ist `.claude/skills/document-feature/SKILL.md` mit seinem Template.

## 1. Umfang bestimmen

- Mit Argumenten: genau diese Features. Unbekannte Namen melden.
- Ohne Argumente: alle `docs/features/*.md` (außer README) **und** Bereiche im Code ohne eigene Doku – Panels in `widgets/` und Controller in `controllers/`, zu denen keine Feature-Doku passt. Diese als Vorschlag für neue Feature-Docs aufführen.
- Liste mit kurzer Einschätzung je Feature (Doku fehlt / lückenhaft / vermutlich aktuell) vorlegen und **auf Freigabe warten**. Der Nutzer kann Features streichen oder die Reihenfolge ändern.

## 2. Branch

Doku-Änderungen laufen über einen eigenen Branch, nicht direkt auf `main`:

```bash
git switch main && git pull
git switch -c docs-nachziehen-<jjjj-mm-tt>
```

## 3. Features bearbeiten (je ein Subagent)

Jedes Feature in einem eigenen Subagenten bearbeiten, damit der Hauptkontext sauber bleibt; höchstens drei gleichzeitig. Auftrag an den Subagenten:

> Lies `.claude/skills/document-feature/SKILL.md` und befolge ihn für das Feature „<name>“: vollständig nachziehen, alles gegen den Code prüfen. Schreibe **nur** `docs/features/<name>.md`. Ändere keine anderen Dateien, sondern liefere zurück:
> 1. kurze Zusammenfassung der Änderungen,
> 2. vorgeschlagene Änderungen an anderen Docs (specs, `architecture.md`, `development.md`, `roadmap.md`, ADRs, Tabelle in `docs/README.md`) mit Datei und Inhalt,
> 3. Fragen an den Nutzer: Unklarheiten (Absicht hinter Verhalten, fehlende Begründungen, „Real getestet“-Angaben),
> 4. Auffälligkeiten: mögliches Fehlverhalten, Widersprüche zwischen Doku und Code, toter Code. Nichts davon als gewollt dokumentieren und nichts am Code ändern.

Fortschritt nach jedem Feature kurz melden.

## 4. Fragen klären

Alle Fragen gesammelt und **nach Feature gruppiert** stellen, nummeriert, damit der Nutzer kurz antworten kann („3: ja, gewollt“). Bei vielen Fragen in Runden zu höchstens zehn. Antworten in die jeweiligen Feature-Docs einarbeiten.

## 5. Übergreifende Docs

Die Vorschläge der Subagenten zusammenführen, Doppelungen und Widersprüche auflösen und **einmal zentral** anwenden: specs, Modultabellen in `docs/architecture.md`, `docs/roadmap.md`, Tabelle „Wo steht was?“ in `docs/README.md`. Neue ADRs nur, wenn der Nutzer die Begründung bestätigt hat.

Wurden neue Feature-Docs angelegt: `bash .github/labels.sh` ausführen.

## 6. Auffälligkeiten

Als Liste vorlegen mit Vorschlag je Punkt: Bug-Issue, Aufgabe oder ignorieren. Issues erst nach Freigabe anlegen (Aufbau nach `.github/ISSUE_TEMPLATE/3-bug.yml` bzw. `2-aufgabe.yml`, Label `bereich:<name>`).

## 7. Abschluss

- Übersicht: je Feature, was ergänzt bzw. korrigiert wurde; offene Fragen; angelegte Issues.
- Hinweis, die Diagramme in der Markdown-Vorschau (Strg+Umschalt+V) zu prüfen.
- Nach Freigabe: Commit „Doku nachgezogen: <features>“, Push, PR nach `main`, nach Freigabe mergen (`gh pr merge --squash --delete-branch`).
