"""Zuordnung System → Archivformat (ZIP/CHD/RVZ/NSZ)."""

from retro_manager.core.chd import CHD_PLATFORMS

FORMAT_ZIP = "zip"
FORMAT_CHD = "chd"
FORMAT_RVZ = "rvz"
FORMAT_NSZ = "nsz"

_RVZ_PLATFORMS = frozenset({"ngc", "wii"})
_NSZ_PLATFORMS = frozenset({"switch"})
# Ohne feste Vorgabe (z. B. PS3: ISO bzw. Ordner, je nach Zielgerät).
_NO_RULE = frozenset({"ps3", "xbox360"})


def target_format(slug: str) -> str | None:
    """Archivformat, in dem die Bibliothek Spiele dieses Systems ablegt; None = keine Regel.

    Disc-Systeme mit CHD-Unterstützung → CHD, GameCube/Wii → RVZ, Switch → NSZ,
    alles andere (Cartridge-Systeme) → ZIP.
    """
    slug = slug.lower()
    if slug in CHD_PLATFORMS:
        return FORMAT_CHD
    if slug in _RVZ_PLATFORMS:
        return FORMAT_RVZ
    if slug in _NSZ_PLATFORMS:
        return FORMAT_NSZ
    if slug in _NO_RULE:
        return None
    return FORMAT_ZIP
