"""Datenmodell der Most-Wanted-Rangliste und die Filterregel (§ Most Wanted).

Schlüssel ist überall die **ADIF-DXCC-Nummer** (GDXF verlinkt jede Zeile mit
`entity.php?entity=N`). Die Präfix-Spalte taugt dafür nicht: sie enthält
Angaben wie `9M6,8`, `FT-J,E` oder `3D2-C`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# Ranglisten der GDXF in Seitenreihenfolge: Code -> HTML-`id` der Tabelle.
CATEGORY_TABLE_IDS: dict[str, str] = {
    "mixed": "Mixed",
    "cw": "CW",
    "phone": "Phone",
    "digital": "Digital",
}
CATEGORIES = tuple(CATEGORY_TABLE_IDS)
# „Automatisch": jedes QSO wird an der Rangliste seines Modes gemessen.
CATEGORY_AUTO = "auto"
CATEGORY_CHOICES = (CATEGORY_AUTO, *CATEGORIES)
DEFAULT_CATEGORY = CATEGORY_AUTO

# Top N: so viele aktuelle DXCC-Gebiete gibt es (= Länge jeder GDXF-Liste).
TOP_MIN = 1
TOP_MAX = 340
DEFAULT_TOP = 100

# Modes, die als Phone zählen. Alles außer CW und diesen ist Digital. `PH` ist
# der Cabrillo-Code (der Parser übersetzt ihn zwar nach SSB, sicher ist sicher);
# DIGITALVOICE/DV (D-STAR, DMR, C4FM …) ist Sprache und zählt deshalb als Phone.
PHONE_MODES = frozenset({"SSB", "USB", "LSB", "AM", "FM", "PH", "DIGITALVOICE", "DV"})
CW_MODES = frozenset({"CW"})


def normalize_category(value: str | None) -> str:
    """Bringt einen Config-Wert auf einen gültigen Kategorie-Code (sonst Default)."""
    code = (value or "").strip().lower()
    return code if code in CATEGORY_CHOICES else DEFAULT_CATEGORY


def clamp_top(value: object) -> int:
    """Top N auf 1..340 begrenzen; Unlesbares wird zum Default."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_TOP
    return max(TOP_MIN, min(TOP_MAX, number))


def category_for_mode(mode: str | None) -> str:
    """Rangliste, an der ein QSO mit diesem Mode gemessen wird.

    CW -> `cw`, Sprache -> `phone`, alles andere (FT8, RTTY, PSK …) ->
    `digital`. Ohne Mode gibt es keinen Anhaltspunkt: dann gilt `mixed`.
    """
    code = (mode or "").strip().upper()
    if not code:
        return "mixed"
    if code in CW_MODES:
        return "cw"
    if code in PHONE_MODES:
        return "phone"
    return "digital"


@dataclass(frozen=True)
class RankedEntity:
    """Eine Zeile einer GDXF-Rangliste."""

    dxcc: int
    rank: int
    prefix: str
    name: str
    needed_pct: float | None = None  # „needed by" in Prozent


@dataclass
class MostWantedList:
    """Die vier Ranglisten eines Jahrgangs, wie sie von der GDXF kommen.

    `rankings[kategorie][dxcc]` -> `RankedEntity`. `fetched_at` ist der
    Abrufzeitpunkt (ISO-8601, UTC) und entscheidet über das Neuladen;
    `updated` ist der Stand-Vermerk der Seite („May 3, 2026"), nur zur Anzeige.
    """

    year: int | None
    rankings: dict[str, dict[int, RankedEntity]] = field(default_factory=dict)
    updated: str | None = None
    fetched_at: str | None = None

    def rank(self, dxcc: int | None, category: str) -> int | None:
        """Rang eines Gebiets in einer Kategorie; `None` = nicht gelistet."""
        if dxcc is None:
            return None
        entry = self.rankings.get(category, {}).get(dxcc)
        return entry.rank if entry is not None else None

    def is_empty(self) -> bool:
        return not any(self.rankings.values())


@dataclass(frozen=True)
class MostWantedFilter:
    """Die Druckregel „nur die Top N" — eingestellt in GUI-Abschnitt 7.

    `ranking=None` heißt: es liegt keine Liste vor (Netzfehler, nie geladen).
    Dann besteht **keine** Karte den Filter — so mit dem Nutzer entschieden;
    die Statuszeile von Abschnitt 7 sagt, warum.
    """

    ranking: MostWantedList | None
    top: int = DEFAULT_TOP
    category: str = DEFAULT_CATEGORY

    def rank(self, dxcc: int | None, modes: Iterable[str | None]) -> int | None:
        """Bester (kleinster) Rang über alle Modes einer Karte.

        - „Automatisch": jedes QSO an der Liste seines Modes; eine Karte „pro
          Station" mit gemischten Modes nimmt den besten Rang, der darauf vorkommt.
        - „Mixed": alle QSOs an der Mixed-Liste.
        - CW/Phone/Digital: **nur** QSOs in dieser Betriebsart zählen (wie im
          DXCC-Filter des Kollegen). Ein SSB-QSO an der CW-Liste zu messen
          ergäbe keinen Sinn — es bestätigt kein CW-Gebiet.
        """
        if self.ranking is None or dxcc is None:
            return None
        modes = list(modes)
        if self.category == CATEGORY_AUTO:
            categories = {category_for_mode(mode) for mode in modes} or {"mixed"}
        elif self.category == "mixed":
            categories = {"mixed"}
        elif any(category_for_mode(mode) == self.category for mode in modes):
            categories = {self.category}
        else:
            return None
        ranks = [r for c in categories if (r := self.ranking.rank(dxcc, c)) is not None]
        return min(ranks) if ranks else None

    def accepts(self, dxcc: int | None, modes: Iterable[str | None]) -> bool:
        """True, wenn das Gebiet unter den ersten `top` liegt. Unbekanntes
        Gebiet oder fehlende Liste -> False (Karte wird nicht gedruckt)."""
        rank = self.rank(dxcc, modes)
        return rank is not None and rank <= self.top
