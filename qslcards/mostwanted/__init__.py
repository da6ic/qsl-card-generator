"""Most-Wanted-Filter: nur Karten an gesuchte DXCC-Gebiete drucken.

Rangliste: German DX Foundation (GDXF), https://gdxf.de/mostwanted/ — die
gesuchtesten DXCC-Gebiete aus Sicht Mitteleuropas, je Jahr und getrennt nach
Mixed/CW/Phone/Digital. Schlüssel ist die ADIF-DXCC-Nummer; die der Karten
kommt aus dem Log (Feld `DXCC`) oder aus dem Lookup (HamQTH `adif`, QRZ `dxcc`).

Öffentliche API:
  - `MostWantedList`, `RankedEntity`, `MostWantedFilter` (models)
  - `category_for_mode(mode)`, `normalize_category(value)`, `clamp_top(value)`
  - `refresh(path, force=False)` — gespeicherte Liste, bei Bedarf neu abgerufen
  - `load(path)` / `is_stale(ranking)` — ohne Netzzugriff
  - `parse_html(text)` / `fetch_html()` — die GDXF-Seite selbst
"""

from __future__ import annotations

from qslcards.mostwanted.gdxf import MostWantedFormatError, fetch_html, parse_html
from qslcards.mostwanted.models import (
    CATEGORIES,
    CATEGORY_AUTO,
    CATEGORY_CHOICES,
    DEFAULT_CATEGORY,
    DEFAULT_TOP,
    TOP_MAX,
    TOP_MIN,
    MostWantedFilter,
    MostWantedList,
    RankedEntity,
    category_for_mode,
    clamp_top,
    normalize_category,
)
from qslcards.mostwanted.store import MAX_AGE_DAYS, RefreshResult, is_stale, load, refresh

__all__ = [
    "CATEGORIES",
    "CATEGORY_AUTO",
    "CATEGORY_CHOICES",
    "CATEGORY_LABELS",
    "DEFAULT_CATEGORY",
    "DEFAULT_TOP",
    "MAX_AGE_DAYS",
    "TOP_MAX",
    "TOP_MIN",
    "MostWantedFilter",
    "MostWantedFormatError",
    "MostWantedList",
    "RankedEntity",
    "RefreshResult",
    "category_for_mode",
    "clamp_top",
    "fetch_html",
    "is_stale",
    "load",
    "normalize_category",
    "parse_html",
    "refresh",
]

# Anzeigenamen der Kategorien (GUI-Abschnitt 7) — die Ranglisten heißen auf der
# GDXF-Seite so, deshalb bleiben sie englisch.
CATEGORY_LABELS: dict[str, str] = {
    CATEGORY_AUTO: "Automatisch (nach Mode)",
    "mixed": "Mixed",
    "cw": "CW",
    "phone": "Phone",
    "digital": "Digital",
}
