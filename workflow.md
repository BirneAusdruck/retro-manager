# Workflow

Grundregel: **eine Aufgabe = eine Session = ein Branch = ein PR.** Jede Aufgabe hinterlässt lauffähigen Code mit grünen Tests. Git, PRs und Issues verwaltet Claude über die Skills; du gibst an den Haltepunkten frei.

```
Idee → roadmap.md → /plan-feature → /ticket-breakdown → /implement-ticket (je Sub-Issue) → Feature-PR → main
```

Branches:

```
main
├── feature/40-bibliothek-aufraeumen    ← ein Branch pro Feature-Issue
│   ├── 41-duplikate-im-model-finden    ← je Sub-Issue, PR in den Feature-Branch
│   └── 42-duplikate-im-reiter-anzeigen
└── 57-crash-bei-leerem-ordner          ← Bugs/Einzel-Issues direkt gegen main
```

## Einmalig

```bash
sudo pacman -S github-cli   # in der Distrobox
gh auth login               # GitHub.com → HTTPS → Web-Browser
bash .github/labels.sh      # Labels + Vorlagen-Dropdowns (aus docs/features/*.md)
```

## 1. Idee

Grob in `docs/roadmap.md` eintragen.

## 2. Planen (Spec)

```bash
git switch main && git pull
claude
```

```
/plan-feature <name> "kurze Idee"
```

Claude sammelt Kontext, interviewt dich in Runden, schlägt den technischen Ansatz vor und schreibt `docs/specs/<name>.md`. Spec prüfen → freigeben. Bei neuem Bereich legt der Skill Platzhalter-Doku und Label gleich mit an.

## 3. Tickets

```
/clear
/ticket-breakdown docs/specs/<name>.md "Milestone"
```

Vorschlag prüfen → freigeben → Issues werden angelegt.

## 4. Umsetzen (pro Sub-Issue, immer neue Session)

```
claude
/implement-ticket 41
```

1. Claude ordnet das Issue ein, legt beim ersten Sub-Issue den Feature-Branch an (sonst holt er `main` hinein) und zweigt den Ticket-Branch ab. **Plan freigeben.**
2. Claude setzt um, testet, prüft jedes Akzeptanzkriterium, aktualisiert ggf. die Doku über `document-feature`.
3. Diff prüfen: `git diff feature/<…>` (inkl. `docs/`)
4. **Commit, Push und PR freigeben** → PR geht in den Feature-Branch.
5. **Merge freigeben** → Claude mergt und schließt das Sub-Issue (automatisch geht das nur bei Merges in `main`).

Wo stehe ich im Feature, was ist als Nächstes dran?

```
/implement-ticket 40      # Nummer des Feature-Issues: zeigt Stand, setzt nichts um
```

## 5. Feature abschließen

Nach dem letzten Sub-Issue (oder per `/implement-ticket <feature-nr>`): Claude holt `main` in den Feature-Branch, prüft Tests und Doku, setzt die Spec auf `Umgesetzt` und legt nach Freigabe den PR nach `main` an (`Closes #<feature-nr>`). Gemergt wird mit **Merge-Commit**, damit die Commits je Ticket erhalten bleiben.

## Doku von Hand nachziehen

```
/document-feature chdman
```

Wenn sich etwas ohne Ticket geändert hat, die Doku veraltet ist oder ein Feature erklärt bzw. visualisiert werden soll. Ergebnis: `docs/features/<name>.md` mit Klassen- und Sequenzdiagramm, dazu angepasste specs, Architektur, Roadmap und ADRs.

## Fehler melden

```bash
gh issue create --template 3-bug.yml
```

Umsetzen mit `/implement-ticket <nr>`. Bugs ohne Feature laufen direkt gegen `main` (Branch von `main`, PR mit `Closes #<nr>`); der nächste Sub-Issue-Lauf holt den Fix in den Feature-Branch.

## Neuer Bereich (neuer Reiter / neues Feature)

Erledigt `/plan-feature` nach Freigabe der Spec: Platzhalter `docs/features/<name>.md`, `bash .github/labels.sh` (Label + Vorlagen-Dropdowns), Zeile in der `CLAUDE.md`. Danach committen und pushen, damit die Vorlagen auf GitHub wirken:

```bash
git add .github docs CLAUDE.md && git commit -m "Spec <name>" && git push
```

## Prüfen (macht Claude, geht auch von Hand)

```bash
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

## gh-Spickzettel

```bash
gh issue list                          # offene Issues
gh issue list --label bereich:chdman   # nach Bereich
gh issue list --milestone "Name"       # nach Etappe
gh issue view 42                       # Details
gh pr status                           # eigene PRs
gh pr list --base feature/<…>          # PRs in einen Feature-Branch
gh pr view --web                       # PR im Browser
```

## Claude-Spickzettel

| Befehl | Wofür |
|---|---|
| Shift+Tab | Plan Mode an/aus |
| `/clear` | Kontext leeren, neue Aufgabe |
| `/compact` | Kontext zusammenfassen bei langen Aufgaben |
| `/plan-feature <name>` | Feature planen → Spec |
| `/ticket-breakdown <spec>` | Spec → Issues |
| `/implement-ticket <nr>` | Sub-Issue/Bug umsetzen |
| `/implement-ticket <feature-nr>` | Stand des Features, ggf. abschließen |
| `/document-feature` | Feature-Doku manuell aktualisieren |
