"""Domänenmodell für ein QSO (siehe CLAUDE.md §6 / SPECIFICATION.md §4.3)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QSO:
    call: str
    qso_date: str  # "YYYYMMDD" (roh, wie im Log)
    time_on: str  # "HHMM" oder "HHMMSS"
    band: str | None = None
    freq: str | None = None  # MHz als String, z.B. "14.074"
    mode: str | None = None
    rst_sent: str | None = None
    rst_rcvd: str | None = None
    qsl_sent_via: str | None = None  # Rohwert aus dem Log, nur informativ
    qsl_via: str | None = None  # Manager/Route-Text
    name: str | None = None  # falls im Log vorhanden
    gridsquare: str | None = None
    # Empfängerbezogene Zusatzfelder aus dem Log (falls vorhanden). Sie dienen als
    # Ausgangsdaten für den optionalen Adress-Export; was fehlt, füllt der
    # HamQTH-Lookup. Absenderdaten kommen dagegen immer aus der Config (§5.3).
    qth: str | None = None  # Ort der Gegenstation
    country: str | None = None  # Land der Gegenstation
    # ADIF-DXCC-Nummer der Gegenstation (Feld `DXCC`), falls der Logger sie
    # schreibt. Roh als String; gewinnt vor dem Lookup (Most-Wanted-Filter).
    dxcc: str | None = None
    raw: dict[str, str] = field(default_factory=dict)  # alle Felder roh, kleingeschrieben
