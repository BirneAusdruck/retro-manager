#!/usr/bin/env bash
# Legt die Labels für Issue-Vorlagen und Skills an bzw. aktualisiert sie und
# schreibt die Bereichs-Auswahl in die Issue-Vorlagen.
# Bereiche werden aus docs/features/*.md abgeleitet (Dateiname = Bereich).
# Beliebig oft ausführbar: bash .github/labels.sh
set -euo pipefail
shopt -s nullglob

cd "$(git rev-parse --show-toplevel)"

templates=(.github/ISSUE_TEMPLATE/1-feature.yml .github/ISSUE_TEMPLATE/3-bug.yml)

create() { gh label create "$1" --color "$2" --description "$3" --force; }

# --- Bereiche einlesen -------------------------------------------------------
bereiche=()
for f in docs/features/*.md; do
  name=$(basename "$f" .md)
  [[ "${name,,}" == "readme" ]] && continue
  bereiche+=("$name")
done

# --- Labels ------------------------------------------------------------------
create feature  "1d76db" "Übergeordnetes Feature mit Spec"
create aufgabe  "0e8a16" "Konkreter Umsetzungsschritt"
create bug      "d73a4a" "Fehler"
create refactor "c5def5" "Umbau ohne Verhaltensänderung"
create docs     "fef2c0" "Nur Dokumentation"

if (( ${#bereiche[@]} == 0 )); then
  echo "Keine Feature-Docs in docs/features/ gefunden – Bereiche bleiben unverändert." >&2
  exit 0
fi

for name in "${bereiche[@]}"; do
  create "bereich:$name" "ededed" "Reiter/Bereich $name"
done

# --- Vorlagen ----------------------------------------------------------------
# Ersetzt die Zeilen zwischen "# bereiche:start" und "# bereiche:end"
# durch die aktuelle Liste; die Einrückung wird von der Start-Markierung übernommen.
liste=$(printf '%s\n' "${bereiche[@]}")
for t in "${templates[@]}"; do
  if ! grep -q '# bereiche:start' "$t" || ! grep -q '# bereiche:end' "$t"; then
    echo "Markierungen fehlen in $t – übersprungen." >&2
    continue
  fi
  awk -v liste="$liste" '
    /# bereiche:start/ {
      print
      match($0, /^ */); indent = substr($0, 1, RLENGTH)
      n = split(liste, b, "\n")
      for (i = 1; i <= n; i++) print indent "- " b[i]
      skip = 1; next
    }
    /# bereiche:end/ { skip = 0 }
    !skip { print }
  ' "$t" > "$t.tmp" && mv "$t.tmp" "$t"
done

echo
if git diff --quiet -- "${templates[@]}"; then
  echo "Vorlagen sind aktuell."
else
  echo "Vorlagen geändert – zum Übernehmen auf GitHub committen und pushen:"
  git --no-pager diff --stat -- "${templates[@]}"
fi
