---
name: plan-feature
description: Plant ein neues oder geändertes Feature im Interview mit dem Nutzer und schreibt daraus eine Spec in docs/specs/<name>.md, bereit für /ticket-breakdown. Legt bei einem neuen Bereich auch Platzhalter-Doku und Labels an. Aufruf mit Feature-Name und optional kurzer Idee, z. B. /plan-feature bibliothek-aufraeumen „Doppelte Spiele finden und bereinigen“
disable-model-invocation: true
argument-hint: "<feature-name> [kurze Idee]"
---

# Feature planen

Eingabe: $ARGUMENTS (Feature-Name, optional eine kurze Idee). Fehlt der Name, nachfragen.

Grundsätze:

- **Nur planen, nichts umsetzen.** In diesem Skill wird kein Code geändert. Geschrieben werden nur Dateien in `docs/` (und ggf. `.github/` über `labels.sh`).
- **Der Nutzer entscheidet.** Claude fragt, schlägt vor und zeigt Folgen auf, trifft aber keine fachlichen Entscheidungen still.
- **Am Code geerdet.** Vorschläge passen zu Architektur und bestehenden Mustern; was nicht geht oder teuer wird, wird offen gesagt.

## 1. Kontext sammeln (vor der ersten Frage)

- `docs/roadmap.md` – steht die Idee schon dort? Mit welchen Notizen?
- Vorhandene Spec `docs/specs/<name>.md` – dann wird sie überarbeitet statt neu geschrieben.
- Betroffene `docs/features/*.md` und Specs (z. B. `specs/bibliothek.md`, `specs/konfiguration.md`).
- Bei neuen Modulen oder schichtübergreifenden Änderungen `docs/architecture.md`.
- Den Code der betroffenen Bereiche, soweit nötig, um Machbarkeit und passende Vorbilder zu erkennen.
- Offene Issues zum Thema: `gh issue list --search "<stichworte>"`.

Dann in zwei, drei Sätzen zusammenfassen, was schon existiert und woran das Feature anknüpft.

## 2. Interview

In **Runden mit höchstens 3–4 Fragen**, nicht alles auf einmal. Zu jeder Frage einen begründeten Vorschlag machen, den der Nutzer nur bestätigen muss. Antworten, die neue Fragen aufwerfen, in der nächsten Runde aufgreifen.

Themen (nur die relevanten, ungefähr in dieser Reihenfolge):

1. **Ziel und Nutzen** – Was soll der Nutzer danach können? Woran merkt er, dass es funktioniert?
2. **Abgrenzung** – Was gehört ausdrücklich nicht dazu? Was kommt vielleicht später?
3. **Bedienung** – Welcher Reiter, welche Anzeigen und Aktionen? Neuer Reiter oder Erweiterung?
4. **Ablauf** – Schritte aus Nutzersicht; was läuft im Hintergrund, was ist parallel?
5. **Daten und Ablage** – Was wird gelesen, geschrieben, verschoben, gelöscht? Passt es zu Struktur A und zur Regel „Originale nie ohne ausdrücklichen Wunsch löschen“?
6. **Fehler, Abbruch, Grenzfälle** – Was passiert bei Abbruch, fehlender HDD, vorhandenen Zieldateien, defekten Dateien?
7. **Konfiguration** – Neue INI-Einstellungen? Geheimnisse (→ Schlüsselbund)?
8. **Externe Werkzeuge und Plattform** – Welche Tools? Was ist beim späteren Windows-Port zu beachten?
9. **Test** – Wie lässt sich das mit Testdaten real prüfen?

Das Interview endet, wenn Ziel, Abgrenzung, Bedienung, Ablauf und Fehlerverhalten geklärt sind. Nicht Geklärtes wandert in „Offene Fragen“.

## 3. Technischer Ansatz

Auf Basis der Antworten einen Ansatz vorschlagen und bestätigen lassen:

- neue und geänderte Module je Schicht (`core/`, `controllers/`, `widgets/`, `widgets/models/`)
- passendes Pattern und Vorbild im Code (z. B. Tabelle als Unterklasse von `GameTableModel`, Warteschlange wie im chdman-Controller)
- Nebenläufigkeit: `QProcess`, `BackgroundTask`, Warteschlange, `max_parallel_jobs`
- **Grundsatzentscheidungen** (betreffen mehr als dieses Feature, schwer umkehrbar) als ADR-Kandidaten markieren

Bei mehreren sinnvollen Varianten: zwei Optionen mit Vor- und Nachteilen nennen und eine empfehlen.

## 4. Spec schreiben

Nach `assets/template.md` als `docs/specs/<name>.md`. Kurz und konkret, Richtwert unter 150 Zeilen. Auf bestehende Docs verweisen statt zu wiederholen. Status `Entwurf`.

Spec dem Nutzer zur Durchsicht geben und Änderungswünsche einarbeiten. Erst auf ausdrückliche Freigabe Status auf `Freigegeben` setzen.

## 5. Docs nachziehen (nach Freigabe)

- `docs/roadmap.md`: Eintrag ergänzen bzw. auf die Spec verweisen.
- Freigegebene Grundsatzentscheidungen als ADR in `docs/adr/` (nächste freie Nummer).
- **Neuer Bereich** (neuer Reiter oder eigenständiges Feature ohne Feature-Doku):
  1. Platzhalter `docs/features/<name>.md` anlegen: Titel und „In Planung, siehe [Spec](../specs/<name>.md)“.
  2. `bash .github/labels.sh` ausführen (legt `bereich:<name>` an und aktualisiert die Vorlagen-Dropdowns).
  3. Zeile in der Tabelle „Wo steht was?“ in `docs/README.md` ergänzen.

## 6. Abschluss

Geänderte Dateien auflisten, offene Fragen nennen und als nächsten Schritt vorschlagen:

```
/clear
/ticket-breakdown docs/specs/<name>.md
```

**Nicht committen**, außer der Nutzer verlangt es. Bei neuem Bereich darauf hinweisen, dass die Vorlagen erst nach Commit und Push auf GitHub wirken.
