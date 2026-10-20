# ADR 0008: uv für Abhängigkeiten und Befehle

**Status:** angenommen · **Entschieden:** Oktober 2026 · **Festgehalten:** 2026-10-20

## Kontext

Python-Projekte haben oft mehrere Quellen für Abhängigkeiten (requirements.txt, setup.py, manuell aktivierte venvs), die auseinanderlaufen.

## Entscheidung

Abhängigkeiten, Python-Version und Befehle werden ausschließlich mit [uv](https://docs.astral.sh/uv/) verwaltet; `pyproject.toml` und `uv.lock` sind die einzige Quelle. Befehle und Regeln im Einzelnen: [development.md](../development.md).

## Folgen

Reproduzierbare Umgebungen auf jedem Rechner mit `uv sync`.
