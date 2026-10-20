"""DATs von No-Intro und Redump laden, RomM-Plattformen zuordnen und nach <HDD>/dats schreiben."""

import html
import io
import json
import re
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from retro_manager.core import manifest

USER_AGENT = "Mozilla/5.0 (compatible; retro-manager/0.1; DAT-Aktualisierung)"

REDUMP_DOWNLOADS_URL = "http://redump.org/downloads/"
REDUMP_DATFILE_URL = "http://redump.org/datfile/{code}/"
REDUMP_CUES_URL = "http://redump.org/cues/{code}/"
REDUMP_KEYS_URL = "http://redump.org/keys/{code}/"
# Pause zwischen zwei Redump-Downloads, um den Server zu schonen.
REDUMP_DELAY_MS = 1000

DATOMATIC_BASE_URL = "https://datomatic.no-intro.org/"
DATOMATIC_DAILY_URL = DATOMATIC_BASE_URL + "index.php?page=download&s=64&op=daily"
DATOMATIC_DAILY_POST_URL = DATOMATIC_BASE_URL + "index.php?page=download&op=daily&s=64"

IGIR_CONSOLE_TOKENS_URL = (
    "https://raw.githubusercontent.com/emmercm/igir/v{version}"
    "/src/modules/candidates/utils/consoleTokens.json"
)

NOINTRO_DIRNAME = "no-intro"
REDUMP_DIRNAME = "redump"
# Korrekte CUE-Dateien je RomM-Plattform; der Ordner gehört komplett der App.
CUES_DIRNAME = "redump-cues"
# Disc-Keys zum Entschlüsseln (z. B. PS3) je RomM-Plattform; gehört ebenfalls der App.
KEYS_DIRNAME = "redump-keys"
REPORT_FILENAME = "ABGLEICH.md"
MANIFEST_FILENAME = ".retro-manager-dats.json"

# Sets aus dem No-Intro-Paket, die Spiele-ROMs enthalten (Ordnername im ZIP).
NOINTRO_STANDARD_SET = "No-Intro"
NOINTRO_EXTRA_SETS = ("Non-Redump", "Unofficial")

# Eindeutige Zuordnungen für Systeme, für die Igir keinen RomM-Ordner kennt.
MANUAL_MAPPINGS: tuple[tuple[str, str], ...] = (
    (r"^APF - ", "apf"),
    (r"^Apple - Macintosh", "mac"),
    (r"^Benesse - Pocket Challenge V2", "pocket-challenge-v2"),
    (r"^Benesse - Pocket Challenge W", "pocket-challenge-w"),
    (r"^Casio - Loopy", "casio-loopy"),
    (r"^Hitachi - S1", "hitachi-s1"),
    (r"^LeapFrog - Explorer", "leapfrog-explorer"),
    (r"^Palm\b", "palm-os"),
    (r"^Sega - Beena", "beena"),
    (r"^Sega - PICO", "sega-pico"),
)
# Namensabgleiche, die nachweislich falsch sind.
WRONG_NAME_MATCHES: tuple[str, ...] = (r"Capcom - Play System III", r"Naomi Satellite Terminal")

_DAT_SUFFIX_NOISE = re.compile(r"\b(parent clone|bios|datfile)\b")


@dataclass(frozen=True)
class RedumpSystem:
    code: str
    name: str
    has_cues: bool = False
    has_keys: bool = False


@dataclass(frozen=True)
class RommPlatform:
    slug: str  # Ordnername unter roms/
    name: str
    category: str


@dataclass(frozen=True)
class ConsoleRule:
    """Eine Zeile aus Igirs consoleTokens.json (nur der RomM-Ordner wird gebraucht)."""

    pattern: re.Pattern[str]
    romm: str | None


@dataclass(frozen=True)
class DatFile:
    group: str  # Zielordner relativ zu dats/, z. B. "no-intro/Non-Redump"
    filename: str
    data: bytes = field(repr=False)
    name: str  # <header><name> der DAT
    source: str = ""  # Redump-Systemkürzel, z. B. "psx"


@dataclass(frozen=True)
class DatMatch:
    dat: DatFile
    platform: RommPlatform | None
    how: str  # "igir", "manuell", "name" oder ""


@dataclass
class DatUpdateResult:
    written: list[Path]
    covered_platforms: int
    missing_platforms: int
    unmapped_dats: int
    report_path: Path
    cue_files: int = 0
    key_files: int = 0


# --- Webseiten auslesen -----------------------------------------------------------------------


def parse_redump_systems(page: str) -> list[RedumpSystem]:
    """Systeme mit DAT-Link von redump.org/downloads, inklusive BIOS-DATs."""
    systems: list[RedumpSystem] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if not cells:
            continue
        name = html.unescape(re.sub(r"<[^>]+>", "", cells[0])).strip()
        cue_codes = set(re.findall(r'href="/cues/([^"/]+)/"', row))
        key_codes = set(re.findall(r'href="/keys/([^"/]+)/"', row))
        for code in re.findall(r'href="/datfile/([^"/]+)/"', row):
            label = f"{name} (BIOS)" if code.endswith("-bios") else name
            systems.append(
                RedumpSystem(code, label, has_cues=code in cue_codes, has_keys=code in key_codes)
            )
    return systems


def parse_daily_submit_name(page: str) -> str | None:
    """Name des „Request“-Knopfs im Daily-Formular von DAT-o-MATIC."""
    match = re.search(r'name="(daily_dl_[^"]+)"', page)
    return match.group(1) if match else None


def daily_form_fields(submit_name: str) -> list[tuple[str, str]]:
    """Formularfelder für das Daily-Paket: Parent/Clone, alle Sets (Filter beim Entpacken)."""
    fields = [("dat_type", "pc")]
    fields += [(f"set[{index}]", "Ok") for index in range(1, 6)]
    fields += [("set_redump_custom", "Ok"), ("set_redump_bios", "Ok")]
    fields += [("include_standard", "Ok"), (submit_name, "Request")]
    return fields


def parse_download_button(page: str) -> str | None:
    """Name des sichtbaren „Download!!“-Knopfs; versteckte Knöpfe sind Fallen für Bots."""
    for name, rest in re.findall(
        r'<input type="submit" name="([0-9a-f]{32})" value="Download!!"([^>]*)>', page
    ):
        if "display:none" not in rest.replace(" ", ""):
            return name
    return None


def filename_from_disposition(header: str) -> str | None:
    """Dateiname aus einem Content-Disposition-Header."""
    match = re.search(r'filename="?([^";]+)"?', header)
    return PurePosixPath(match.group(1).strip()).name if match else None


# --- DATs entpacken ---------------------------------------------------------------------------


def dat_header_name(data: bytes) -> str:
    """Systemname aus dem <header><name> einer Logiqx-DAT."""
    match = re.search(rb"<header>.*?<name>(.*?)</name>", data, re.S)
    if not match:
        return ""
    return html.unescape(match.group(1).decode("utf-8", "replace")).strip()


def extract_nointro(pack: bytes) -> list[DatFile]:
    """DATs der Spiele-Sets aus dem No-Intro-Daily-Paket."""
    dats = []
    with zipfile.ZipFile(io.BytesIO(pack)) as archive:
        for member in archive.namelist():
            path = PurePosixPath(member)
            set_name = path.parts[0] if len(path.parts) > 1 else ""
            if path.suffix != ".dat":
                continue
            if set_name == NOINTRO_STANDARD_SET:
                group = NOINTRO_DIRNAME
            elif set_name in NOINTRO_EXTRA_SETS:
                group = f"{NOINTRO_DIRNAME}/{set_name}"
            else:
                continue
            data = archive.read(member)
            dats.append(DatFile(group, path.name, data, dat_header_name(data)))
    return dats


def extract_redump(filename: str, payload: bytes, code: str = "") -> list[DatFile]:
    """Redump liefert DATs einzeln oder als ZIP mit einer DAT."""
    if payload[:2] != b"PK":
        return [DatFile(REDUMP_DIRNAME, filename, payload, dat_header_name(payload), code)]
    dats = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.namelist():
            if member.endswith(".dat"):
                data = archive.read(member)
                name = PurePosixPath(member).name
                dats.append(DatFile(REDUMP_DIRNAME, name, data, dat_header_name(data), code))
    return dats


def extract_cues(payload: bytes) -> dict[str, bytes]:
    """CUE-Dateien aus einem Redump-Cuesheet-Paket (Dateiname -> Inhalt)."""
    return _extract_suffix(payload, ".cue")


def extract_keys(payload: bytes) -> dict[str, bytes]:
    """Disc-Keys (`.key`, je 16 Byte) aus einem Redump-Key-Paket."""
    return _extract_suffix(payload, ".key")


def _extract_suffix(payload: bytes, suffix: str) -> dict[str, bytes]:
    files = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.namelist():
            name = PurePosixPath(member).name
            if name.lower().endswith(suffix) and manifest.is_safe_relative(name):
                files[name] = archive.read(member)
    return files


# --- Zuordnung zu RomM ------------------------------------------------------------------------


def parse_console_tokens(text: str) -> list[ConsoleRule]:
    """Liest Igirs consoleTokens.json; Regex im JavaScript-Format /muster/flags."""
    rules = []
    for console in json.loads(text)["consoles"]:
        regex = console["datNameRegex"]
        last_slash = regex.rfind("/")
        flags = re.IGNORECASE if "i" in regex[last_slash + 1 :] else 0
        rules.append(
            ConsoleRule(re.compile(regex[1:last_slash], flags), console["tokens"].get("romm"))
        )
    return rules


def parse_romm_platforms(data: list[dict[str, Any]]) -> list[RommPlatform]:
    """Plattformen aus RomMs /api/platforms/supported."""
    return [
        RommPlatform(slug=item["fs_slug"], name=item["name"], category=item.get("category") or "")
        for item in data
    ]


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def match_dats(
    dats: list[DatFile], rules: list[ConsoleRule], platforms: list[RommPlatform]
) -> list[DatMatch]:
    """Ordnet jede DAT einer RomM-Plattform zu.

    Reihenfolge: Igirs Regel (wie Igir: die letzte passende gewinnt), feste Zuordnungen,
    zuletzt der Plattformname von RomM im Systemnamen der DAT.
    """
    by_slug = {platform.slug.lower(): platform for platform in platforms}
    by_name = sorted(
        ((_normalize(p.name), p) for p in platforms if len(_normalize(p.name)) >= 4),
        key=lambda item: -len(item[0]),
    )
    matches = []
    for dat in dats:
        matches.append(_match_one(dat, rules, by_slug, by_name))
    return matches


def _match_one(
    dat: DatFile,
    rules: list[ConsoleRule],
    by_slug: dict[str, RommPlatform],
    by_name: list[tuple[str, RommPlatform]],
) -> DatMatch:
    name = dat.name
    rule = next((rule for rule in reversed(rules) if rule.pattern.search(name)), None)
    if rule is not None and rule.romm and rule.romm.lower() in by_slug:
        return DatMatch(dat, by_slug[rule.romm.lower()], "igir")

    for pattern, slug in MANUAL_MAPPINGS:
        if re.search(pattern, name) and slug in by_slug:
            return DatMatch(dat, by_slug[slug], "manuell")

    if any(re.search(pattern, name) for pattern in WRONG_NAME_MATCHES):
        return DatMatch(dat, None, "")
    system = name.split(" - ", 1)[1] if " - " in name else name
    system = _DAT_SUFFIX_NOISE.sub("", _normalize(system)).strip()
    for platform_name, platform in by_name:
        if system == platform_name or re.search(rf"\b{re.escape(platform_name)}\b", system):
            return DatMatch(dat, platform, "name")
    return DatMatch(dat, None, "")


# --- Schreiben --------------------------------------------------------------------------------


def write_dats(
    dats_dir: Path,
    matches: list[DatMatch],
    platforms: list[RommPlatform],
    sources: str,
    today: date,
    cue_packs: dict[str, dict[str, bytes]] | None = None,
    key_packs: dict[str, dict[str, bytes]] | None = None,
) -> DatUpdateResult:
    """Schreibt zugeordnete DATs und den Abgleich; ersetzt nur früher von der App geschriebene.

    `cue_packs`/`key_packs` (Redump-Kürzel -> Dateien) landen je RomM-Plattform in
    `redump-cues/` bzw. `redump-keys/`.
    """
    dats_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = dats_dir / MANIFEST_FILENAME
    for relative in _read_manifest(manifest_path):
        old = dats_dir / relative
        if old.is_file():
            old.unlink()

    written: list[Path] = []
    for match in matches:
        if match.platform is None:
            continue
        target = dats_dir / match.dat.group / match.dat.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(match.dat.data)
        written.append(target)
    manifest_path.write_text(
        json.dumps(sorted(str(path.relative_to(dats_dir)) for path in written), indent=1),
        encoding="utf-8",
    )

    cue_files = _write_packs(dats_dir / CUES_DIRNAME, matches, cue_packs or {})
    key_files = _write_packs(dats_dir / KEYS_DIRNAME, matches, key_packs or {})

    report = dats_dir / REPORT_FILENAME
    report.write_text(render_report(matches, platforms, sources, today), encoding="utf-8")
    covered = {match.platform.slug for match in matches if match.platform}
    return DatUpdateResult(
        written=written,
        covered_platforms=len(covered),
        missing_platforms=len([p for p in platforms if p.slug not in covered]),
        unmapped_dats=len([match for match in matches if match.platform is None]),
        report_path=report,
        cue_files=cue_files,
        key_files=key_files,
    )


def _write_packs(
    packs_dir: Path, matches: list[DatMatch], packs: dict[str, dict[str, bytes]]
) -> int:
    if packs_dir.is_dir():
        shutil.rmtree(packs_dir)
    count = 0
    for match in matches:
        pack = packs.get(match.dat.source) if match.platform else None
        if not pack:
            continue
        target = packs_dir / match.platform.slug
        target.mkdir(parents=True, exist_ok=True)
        for name, data in pack.items():
            (target / name).write_bytes(data)
        count += len(pack)
    return count


def _read_manifest(path: Path) -> list[str]:
    entries = manifest.read_json(path, [])
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if manifest.is_safe_relative(entry)]


def render_report(
    matches: list[DatMatch], platforms: list[RommPlatform], sources: str, today: date
) -> str:
    """Abgleich als Markdown: Zuordnungen, DATs ohne RomM-Plattform, RomM-Plattformen ohne DAT."""
    lines = [
        f"# DAT-Abgleich mit RomM – Stand {today:%d.%m.%Y}",
        "",
        sources,
        "",
        "## Zugeordnet (RomM-Ordner ← DATs)",
        "",
        "`igir` = Igirs `{romm}`-Token sortiert automatisch richtig; `manuell`/`name` = RomM "
        "unterstützt das System, Igir kennt aber keinen RomM-Ordner.",
        "",
    ]
    grouped: dict[RommPlatform, list[str]] = defaultdict(list)
    for match in matches:
        if match.platform:
            grouped[match.platform].append(f"{match.dat.name} [{match.dat.group}, {match.how}]")
    for platform in sorted(grouped, key=lambda p: p.slug):
        lines.append(f"- **{platform.name}** (`roms/{platform.slug}`)")
        lines += [f"  - {entry}" for entry in sorted(grouped[platform])]

    unmapped = sorted({match.dat.name for match in matches if match.platform is None})
    lines += ["", f"## DATs ohne RomM-Plattform ({len(unmapped)})", "", "Nicht kopiert.", ""]
    lines += [f"- {name}" for name in unmapped]

    missing: dict[str, list[str]] = defaultdict(list)
    for platform in platforms:
        if platform not in grouped:
            missing[platform.category or "Ohne Kategorie"].append(
                f"{platform.name} (`{platform.slug}`)"
            )
    lines += ["", f"## RomM-Plattformen ohne DAT ({sum(map(len, missing.values()))})", ""]
    for category in sorted(missing):
        lines.append(f"### {category} ({len(missing[category])})")
        lines += [f"- {entry}" for entry in sorted(missing[category])]
        lines.append("")
    return "\n".join(lines)
