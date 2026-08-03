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
    via_text: str  # Feld "Via:" (Manager-Callsign aus dem Lookup, oder leer)
    via_routes: tuple[str, ...]  # akzeptierte Zustellwege der Station (B/D/Q/L)
    rows: list[CardRow]  # 1..N (per_station kann mehrere haben)
    qsl_mark: str = "none"  # global aus config: "pse" | "tnx" | "none"
    portable_mark: str = "none"  # global aus config: "none" | "p" | "m" | "t" | "r"
    confirm_mark: str = "none"  # global aus config: "qso" | "swl" | "none"
    remarks: str = ""  # REMARKS-Text der Karte; leer -> kein Kasten (dynamisch).
    #   Default = globaler Config-Wert; in der Vorschau je Karte überschreibbar.
    # True, sobald der Remarks-Text in der Vorschau manuell gesetzt wurde (≠ globaler
    # Wert). Schützt die Karte, wenn die globale Bemerkung geändert/gelöscht wird.
    remarks_manual: bool = False
    # Manueller Via-Override aus der Vorschau: erzwingt einen Weg (B/D/Q/L) und
    # überschreibt die automatische Auflösung aus via_routes + Prioritätsliste.
    via_override: str | None = None
    # Empfängeradresse nur bei Bedarf gefüllt (Export), NICHT auf der Karte:
    recipient: LookupResult | None = None
