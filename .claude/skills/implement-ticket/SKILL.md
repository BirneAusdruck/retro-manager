---
name: implement-ticket
description: Setzt ein GitHub-Issue kontrolliert um. Sub-Issues eines Features laufen über einen Feature-Branch (feature/<nr>-<name>) mit eigenem Ticket-Branch und PR dorthin; eigenständige Issues (Bugs) direkt gegen main. Mit der Nummer eines Feature-Issues zeigt er den Stand und schließt fertige Features ab. Aufruf: /implement-ticket 42
disable-model-invocation: true
argument-hint: "<issue-nummer>"
---

# Ticket umsetzen

Eingabe: $ARGUMENTS (Issue-Nummer). Fehlt sie, nachfragen.

Grundsätze:

- **Ein Aufruf = ein Issue = ein Ticket-Branch = ein PR.** Alles außerhalb des Issues wird notiert, nicht umgesetzt.
- **Freigaben:** Plan, Commit/Push/PR und Merge jeweils erst nach ausdrücklicher Zustimmung des Nutzers.
- Auf geteilten Branches (`main`, `feature/…`) wird nie rebased oder force-gepusht.

## Namensregel

Slug aus dem Issue-Titel: Kleinbuchstaben, ä→ae, ö→oe, ü→ue, ß→ss, nur `a-z`, `0-9` und `-`, höchstens fünf Wörter.

- Feature-Branch: `feature/<feature-nr>-<slug>`
- Ticket-Branch: `<nr>-<slug>`

## 1. Issue einordnen

```bash
git status                                             # Uncommittetes? → nachfragen, nicht weitermachen
gh issue view <nr> --comments
gh issue view <nr> --json labels,state --jq '{labels:[.labels[].name],state}'
gh api "repos/{owner}/{repo}/issues/<nr>/sub_issues" --jq '.[] | {number,title,state}'
gh api "repos/{owner}/{repo}/issues/<nr>/parent" --jq .number 2>/dev/null   # Feature-Issue, falls Sub-Issue
```

Liefert der Parent-Aufruf nichts, nach „Teil von #…“ im Issue-Text suchen.

| Fall | Erkennung | Weiter mit |
|---|---|---|
| **A – Feature-Issue** | Label `feature` oder hat Sub-Issues | Abschnitt A |
| **B – Sub-Issue** | hat ein Feature-Issue als Eltern | Abschnitt B |
| **C – eigenständig** | weder noch (Bug, Refactor, Einzelaufgabe) | Abschnitt C |

Ist das Issue geschlossen, nur melden und abbrechen.

## A – Feature-Issue: Stand zeigen, nichts umsetzen

1. **Aufräumen:** Offene Sub-Issues, deren Ticket-PR schon in den Feature-Branch gemergt ist, schließen:
   ```bash
   gh pr list --base feature/<feature-nr>-<slug> --state merged --json number,headRefName
   gh issue close <nr> --comment "Erledigt mit #<pr> im Feature-Branch."
   ```
2. **Übersicht:** Sub-Issues mit Status und Abhängigkeiten in Reihenfolge auflisten.
3. Sind noch Sub-Issues offen: das nächste vorschlagen, dessen Abhängigkeiten erledigt sind (`/implement-ticket <nr>` in neuer Session). Ende.
4. Sind alle erledigt: weiter mit **„Feature abschließen“**.

## B – Sub-Issue (über den Feature-Branch)

### B1. Vorbereiten

- Abhängigkeiten aus „Hinweise“ prüfen (`gh issue view <dep> --json state`). Ist eine offen: abbrechen und melden.
- Issue-Kontext lesen: alle unter „Kontext“ genannten Docs, `docs/features/<bereich>.md`, bei neuen Modulen `docs/architekture.md`.
- Feature-Branch suchen: `git fetch origin && git branch -r --list "origin/feature/<feature-nr>-*"`.
- Prüfen, ob `main` Neues enthält, das im Feature-Branch fehlt: `git log --oneline origin/feature/<…>..origin/main`.

### B2. Plan zur Freigabe

Kurz vorlegen und **auf Freigabe warten**:

- **Git:** Feature-Branch neu anlegen oder vorhandenen nutzen; `main` einmergen, falls B1 neue Commits zeigt; Name des Ticket-Branches.
- **Code:** neue bzw. geänderte Dateien je Schicht, neue Tests.
- **Nachweis** je Akzeptanzkriterium.
- Unklarheiten oder Widersprüche zwischen Issue, Spec und Code.

Ist die Aufgabe deutlich größer als ~5 Dateien: Aufteilung vorschlagen statt anzufangen.

### B3. Branches anlegen

```bash
# Feature-Branch, nur wenn noch nicht vorhanden (verknüpft ihn mit dem Feature-Issue)
git switch main && git pull
gh issue develop <feature-nr> --name feature/<feature-nr>-<slug> --base main --checkout

# Feature-Branch aktualisieren, falls vorhanden
git switch feature/<feature-nr>-<slug> && git pull
git merge origin/main        # nur wenn freigegeben; bei Konflikten abbrechen und melden

# Ticket-Branch vom Feature-Branch (verknüpft ihn mit dem Sub-Issue)
gh issue develop <nr> --name <nr>-<slug> --base feature/<feature-nr>-<slug> --checkout
```

Setzt man ein Ticket fort, stattdessen `git switch <nr>-<slug>`.

Weiter mit **Umsetzen und prüfen**, danach B4.

### B4. Abschluss (jeweils nach Freigabe)

```bash
git commit                                  # Nachricht: "<Imperativ-Beschreibung> (#<nr>)"
git push -u origin <nr>-<slug>
gh pr create --base feature/<feature-nr>-<slug> --title "<titel> (#<nr>)" --body-file <datei>
```

PR-Text nach `.github/pull_request_template.md`, aber erste Zeile **„Erledigt #<nr> · Teil von #<feature-nr>“** statt „Closes“ – Schlüsselwörter schließen Issues nur bei Merge in `main`.

Nach Freigabe zum Mergen:

```bash
gh pr merge <pr> --squash --delete-branch
gh issue close <nr> --comment "Erledigt mit #<pr> im Feature-Branch."
git switch feature/<feature-nr>-<slug> && git pull
```

War es das letzte offene Sub-Issue: **„Feature abschließen“** vorschlagen.

## C – Eigenständiges Issue (direkt gegen main)

1. Kontext und Abhängigkeiten wie B1, Plan zur Freigabe wie B2 (ohne Feature-Branch).
2. Branch:
   ```bash
   git switch main && git pull
   gh issue develop <nr> --name <nr>-<slug> --base main --checkout
   ```
3. **Umsetzen und prüfen.**
4. Nach Freigabe: Commit, `git push -u origin <nr>-<slug>`, `gh pr create --base main …` mit **„Closes #<nr>“**. Nach Freigabe zum Mergen: `gh pr merge <pr> --squash --delete-branch`, dann `git switch main && git pull`.

## Umsetzen und prüfen (B und C)

- Reihenfolge: `core/` mit Unit-Tests, dann Controller, dann View.
- Regeln aus der CLAUDE.md und ggf. `widgets/CLAUDE.md` bzw. `controllers/CLAUDE.md`; bestehende Muster und im Issue genannte Vorbilder nachahmen.
- „Nicht Teil dieser Aufgabe“ strikt einhalten; Auffälligkeiten notieren.
- Prüfen:
  ```bash
  uv run pytest
  uv run ruff check src tests
  uv run ruff format src tests
  ```
  Bei Abläufen mit externen Werkzeugen zusätzlich real mit Testdaten, Oberfläche mit `QT_QPA_PLATFORM=offscreen`.
- **Jedes Akzeptanzkriterium einzeln:** erfüllt ja/nein mit Nachweis. Nicht Erfülltes offen melden.
- Steht `document-feature` in den Kriterien: Skill `document-feature` ausführen.
- Zusammenfassung: geänderte Dateien, Ergebnis je Kriterium, Vorschläge für Folge-Issues (nicht selbst anlegen), Vorschlag für Commit-Nachricht und PR-Text. Dann auf Freigabe warten.

## Feature abschließen

Wenn alle Sub-Issues erledigt sind (aus A oder nach dem letzten B4):

1. ```bash
   git switch feature/<feature-nr>-<slug> && git pull
   git merge origin/main      # nach Freigabe, falls main Neues enthält
   uv run pytest && uv run ruff check src tests
   ```
2. Prüfen, ob die Feature-Doku aktuell ist (sonst `document-feature`) und die Spec auf Status `Umgesetzt` setzen.
3. Nach Freigabe den Feature-PR anlegen:
   ```bash
   gh pr create --base main --title "Feature: <name> (#<feature-nr>)" --body-file <datei>
   ```
   Text: „Closes #<feature-nr>“, Liste der Sub-Issues mit ihren PRs, Hinweis auf Spec und Feature-Doku.
4. Nach Freigabe zum Mergen – **Merge-Commit statt Squash**, damit die Commits je Ticket in `main` erhalten bleiben:
   ```bash
   gh pr merge <pr> --merge --delete-branch
   git switch main && git pull
   ```
