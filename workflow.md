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

Skills nach `.claude/skills/`, Subagent `feature-reviewer.md` nach `.claude/agents/`.

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

Vorher prüfen lassen (read-only): `/review-feature` → aus Befunden Issues machen → erledigen.

Nach dem letzten Sub-Issue (oder per `/implement-ticket <feature-nr>`): Claude holt `main` in den Feature-Branch, prüft Tests und Doku, setzt die Spec auf `Umgesetzt` und legt nach Freigabe den PR nach `main` an (`Closes #<feature-nr>`). Gemergt wird mit **Merge-Commit**, damit die Commits je Ticket erhalten bleiben.

## Bestehendes Feature erweitern

Offene Doku-PRs (z. B. von `document-backwards`) vorher mergen, damit Claude auf der aktuellen Doku arbeitet.

**Klein (eine Session):** einzelnes Issue, läuft direkt gegen `main`.

```bash
gh issue create --template 2-aufgabe.yml   # oder Claude: „Leg ein Issue nach 2-aufgabe.yml mit bereich:<name> an: …“
```

```
/implement-ticket <nr>
```

**Größer (mehrere Schritte):** eigener Name für die Erweiterung, Ablauf wie bei einem neuen Feature, aber ohne neuen Bereich.

```
/plan-feature <bereich>-<erweiterung> "kurze Idee"
/ticket-breakdown docs/specs/<bereich>-<erweiterung>.md
/implement-ticket <feature-nr>             # Stand + nächstes Sub-Issue
```

Bestehende Feature-Doku wird am Ende per `document-feature` erweitert.

**Unklar, was fehlt:** erst `/review-feature <name>`, Befunde zu Issues machen, dann wie oben.

## Doku von Hand nachziehen

```
/document-feature chdman        # ein Feature nach einer Änderung ohne Ticket
/document-backwards             # alle fertigen Features vollständig nachziehen
/document-backwards chdman ftp  # nur bestimmte
```

`document-backwards` prüft alles gegen den Code, stellt Unklarheiten gesammelt als Fragen, schlägt für Auffälligkeiten Issues vor und arbeitet auf eigenem Branch mit PR. Diagramme danach in der Vorschau prüfen (Strg+Umschalt+V, braucht die Extension „Markdown Preview Mermaid Support“).

## Feature prüfen

```
/review-feature           # Feature des aktuellen Branches
/review-feature chdman    # bestimmtes Feature
```

Ein read-only Subagent prüft Code gegen Spec, Doku, Akzeptanzkriterien und Projektregeln. Du bekommst eine Befundliste, wählst aus, was zum Ticket wird (Bug/Aufgabe/Doku), und entscheidest, ob es Sub-Issue des laufenden Features wird.

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
| `/document-feature <name>` | Feature-Doku aktualisieren |
| `/review-feature [name]` | Feature read-only prüfen → Issues |
| `/document-backwards [name …]` | Doku fertiger Features vollständig nachziehen |

## git-Spickzettel

### Stand Anzeigen
```bash
git status                     # aktueller Branch, geänderte und neue Dateien
git diff                       # Änderungen, die noch nicht vorgemerkt sind
git diff --staged              # vorgemerkte Änderungen (nach add)
git diff main                  # alles, was sich gegenüber main unterscheidet
git log --oneline -10          # letzte 10 Commits kurz
git log --oneline --graph --all  # alle Branches als Baum
git show <commit>              # Inhalt eines Commits
```

### Branches
```bash
git branch                     # lokale Branches, * = aktueller
git branch -a                  # inkl. Branches auf GitHub
git switch <branch>            # wechseln
git switch -c <neuer-branch>   # neu anlegen und wechseln
git branch -d <branch>         # lokalen Branch löschen (nur wenn gemergt)
```

### Änderungen speichern
```bash
git add <datei>                # Datei für den Commit vormerken
git add .                      # alle Änderungen im Ordner vormerken
git commit -m "Nachricht"      # Commit erstellen
```

### Hoch- und runterladen
```bash
git pull                       # neuesten Stand von GitHub holen
git push                       # eigene Commits hochladen
git push -u origin <branch>    # neuen Branch zum ersten Mal hochladen
git fetch                      # nur nachsehen, was es Neues gibt, ohne einzuarbeiten
```

### Zwischenparken
```bash
git stash                      # Änderungen beiseitelegen, Arbeitsstand sauber
git stash pop                  # wieder zurückholen
```

### Rückgängig machen
```bash
git restore <datei>            # Änderungen an einer Datei verwerfen ⚠️
git restore --staged <datei>   # Vormerkung aufheben, Änderung bleibt
git commit --amend             # letzten Commit korrigieren (nur vor dem Push!)
git revert <commit>            # Commit durch einen Gegen-Commit rückgängig machen
```

### Typischer Ablauf von Hand
```bash
git switch main && git pull     # aktuellen Stand holen
git switch -c 58-kleiner-fix    # Branch anlegen
# … ändern …
git status && git diff          # prüfen
git add . && git commit -m "Kleinen Fix umsetzen (#58)"
git push -u origin 58-kleiner-fix
gh pr create --fill             # PR anlegen
```
