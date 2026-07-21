"""Datenmodelle der Karten (siehe docs/SPECIFICATION.md §5.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # nur für Typannotation; Modul wird erst später gebaut
    from qslcards.lookup.base import LookupResult


@dataclass
class CardRow:
    """Eine Tabellenzeile der Rückseite. Datum in Reihenfolge D M Y."""

    date_d: str
    date_m: str
    date_y: str
    utc: str  # "HH:MM"
    freq_mhz: str
    mode: str
    rst_sent: str


@dataclass
class Card:
    recipient_call: str
    via_text: str  # Feld "Via:" (aus qsl_via oder leer)
    via_code: str  # B/D/E/M (für Export/Sortierung)
    rows: list[CardRow]  # 1..N (per_station kann mehrere haben)
    qsl_mark: str = "none"  # global aus config: "pse" | "tnx" | "none"
    portable_mark: str = "none"  # global aus config: "none" | "p" | "m"
    # Empfängeradresse nur bei Bedarf gefüllt (Export), NICHT auf der Karte:
    recipient: LookupResult | None = None
