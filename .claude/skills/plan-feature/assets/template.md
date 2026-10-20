# Spec: <Feature-Name>

Status: Entwurf · Feature-Issue: – · Bereich: <bereich>

## Ziel

<Was kann der Nutzer danach, und warum ist das nützlich? Zwei bis vier Sätze.>

**Fertig, wenn:**
- <prüfbares Kriterium aus Nutzersicht>

## Nicht-Ziele

- <ausdrücklich nicht Teil dieses Features>
- <später denkbar → roadmap.md>

## Bedienung

- **Ort:** <Reiter / Dialog>
- **Anzeige:** <Liste, Spalten, Filter, Status>
- **Aktionen:** <Schaltflächen und was sie auslösen>

## Ablauf

1. <Schritt aus Nutzersicht>
2. …

<Optional bei komplexem Ablauf: Mermaid-Flussdiagramm auf fachlicher Ebene, ohne Klassennamen.>

## Daten und Ablage

- **Liest:** <Ordner, Dateien, API>
- **Schreibt:** <Ziel, Benennung; Verweis auf specs/bibliothek.md>
- **Arbeitsordner:** `<HDD>/.retro-manager-tmp/<name>/`
- **Löscht/verschiebt:** <nur was, wann, mit welcher Bestätigung>

## Fehler, Abbruch, Grenzfälle

| Fall | Verhalten |
|---|---|
| Abbruch durch Nutzer | … |
| Zieldatei existiert | … |
| HDD nicht eingehängt | … |

## Konfiguration

| INI | Bedeutung | Standard |
|---|---|---|
| `[<abschnitt>] <schlüssel>` | … | … |

Geheimnisse: <keine / Schlüsselbund-Eintrag …>

## Technischer Ansatz

| Schicht | Neu / geändert | Rolle |
|---|---|---|
| Model | `core/<modul>.py` | … |
| Controller | `controllers/<modul>.py` | … |
| View | `widgets/<panel>.py` | … |
| Item-Model | `widgets/models/<modell>.py` | … |

- **Vorbild / Pattern:** <z. B. Unterklasse von GameTableModel; Warteschlange wie ChdmanController>
- **Nebenläufigkeit:** <QProcess / BackgroundTask / parallel bis max_parallel_jobs>
- **Externe Werkzeuge:** <Argumente über core/tools.py>
- **Windows-Port:** <zu beachten / nichts>

## Tests

- **Unit (core/):** <was wird getestet>
- **Real:** <mit welchen Werkzeugen und Testdaten>

## Entscheidungen

- <getroffene Entscheidung> – <Begründung> <(ADR NNNN, falls grundsätzlich)>

## Offene Fragen

- <noch zu klären, bevor die betroffene Aufgabe umgesetzt wird>
