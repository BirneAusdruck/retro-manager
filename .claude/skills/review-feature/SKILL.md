---
name: review-feature
description: Prüft ein Feature read-only durch den Subagenten feature-reviewer gegen Spec, Doku, Projektregeln und Code und macht aus ausgewählten Befunden GitHub-Issues. Ohne Argument das Feature des aktuellen Branches. Aufruf: /review-feature oder /review-feature chdman
disable-model-invocation: true
argument-hint: "[feature]"
---

# Feature prüfen

Eingabe: $ARGUMENTS – Feature-Name, optional.

Grundsatz: **Es wird kein Code und keine Doku geändert.** Ergebnis sind Befunde und – nach Freigabe – Issues.

## 1. Feature bestimmen

- Mit Argument: dieses Feature (`docs/features/<name>.md` muss existieren, sonst nachfragen).
- Ohne Argument aus dem aktuellen Branch:
  - `feature/<nr>-…` oder Ticket-Branch eines Sub-Issues → Feature-Issue `<nr>` → Label `bereich:<name>`.
  - Auf `main` oder nicht ableitbar: nachfragen.

Bei einem Feature-Branch zusätzlich das Feature-Issue und seine Sub-Issues merken (für Akzeptanzkriterien und spätere Zuordnung).

## 2. Material sammeln (Hauptsession)

```bash
git fetch origin
git diff --stat origin/main...HEAD          # nur bei Feature-/Ticket-Branch
uv run pytest -q tests/ 2>&1 | tail -20
uv run ruff check src tests 2>&1 | tail -20
gh api "repos/{owner}/{repo}/issues/<feature-nr>/sub_issues" --jq '.[] | {number,title,state}'
gh issue list --label "bereich:<name>" --state open --json number,title
```

Die Akzeptanzkriterien der Sub-Issues mit `gh issue view <nr>` lesen.

## 3. Review durch den Subagenten

Subagent **`feature-reviewer`** aufrufen (nur Lesezugriff) mit: Feature-Name, Liste der relevanten Dateien bzw. Diff-Übersicht, Ausgabe von pytest und ruff, Akzeptanzkriterien der Sub-Issues.

## 4. Befunde aufbereiten

- Befunde, die schon als offenes Issue existieren, markieren („bereits #57“).
- Als Tabelle vorlegen, sortiert nach Schwere: Nr, Titel, Schwere, Kategorie, Konfidenz, Vorschlag **Bug / Aufgabe / Doku / ignorieren**.
- Danach die Details der Befunde.
- Den Nutzer auswählen lassen, z. B. „B1, B3 als Bug, B4 als Aufgabe, Rest ignorieren“. Befunde mit Konfidenz „vermutlich“ auf Wunsch vorher genauer prüfen lassen (erneut read-only).

## 5. Issues anlegen (nach Freigabe)

- **Bug** → Aufbau nach `.github/ISSUE_TEMPLATE/3-bug.yml`, Label `bug` + `bereich:<name>`.
- **Aufgabe / Doku** → Aufbau nach `.github/ISSUE_TEMPLATE/2-aufgabe.yml`, Label `aufgabe` bzw. `docs` + `bereich:<name>`.
- Text: Felder der Vorlage als `###`-Überschriften; Fundstelle, Beleg und Vorschlag aus dem Befund übernehmen; Hinweis „Gefunden mit /review-feature“.
- **Zuordnung:** Ist das Feature noch offen (Feature-Branch aktiv), fragen, ob die Issues Sub-Issues des Feature-Issues werden sollen – dann sind sie Teil des Features und werden vor „Feature abschließen“ erledigt. Sonst eigenständige Issues gegen `main`.

```bash
gh issue create --title "<titel>" --label bug --label "bereich:<name>" --body-file /tmp/befund-1.md
# als Sub-Issue anhängen
child_id=$(gh api "repos/{owner}/{repo}/issues/<nr>" --jq .id)
gh api -X POST "repos/{owner}/{repo}/issues/<feature-nr>/sub_issues" -F sub_issue_id="$child_id"
```

## 6. Abschluss

Angelegte Issues mit Nummer auflisten und den nächsten Schritt nennen (`/implement-ticket <nr>`).
