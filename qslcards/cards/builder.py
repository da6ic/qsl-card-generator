"""Karten-Erzeugung: QSOs umformen und gruppieren (siehe SPECIFICATION.md §5.2).

**Kein Via-Filter**: es entstehen Karten für *alle* QSOs. Die Versandart (Via),
der QSL-Manager und die Adresse kommen aus dem Lookup (Map `CALL -> LookupResult`,
optional); ohne Treffer gilt `default_via`. Welche Karten am Ende gedruckt werden,
entscheidet die GUI anhand des Via-Filters — nicht dieses Modul.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from qslcards.adif.models import QSO
from qslcards.config import AppConfig
from qslcards.lookup import derive_via
from qslcards.pdf.geometry import MAX_ROWS

from .models import Card, CardRow

if TYPE_CHECKING:
    from qslcards.lookup.base import LookupResult

# Map CALL (Großbuchstaben) -> Lookup-Ergebnis; None-Werte sind erlaubt.
Lookups = dict[str, "LookupResult | None"]

# Optionale Tabelle Band -> repräsentative Frequenz (MHz), falls FREQ im Log fehlt.
# Untere Bandkante als Näherung; nur zur Anzeige auf der Karte.
BAND_TO_MHZ: dict[str, str] = {
    "160m": "1.8",
    "80m": "3.5",
    "60m": "5.3",
    "40m": "7.0",
    "30m": "10.1",
    "20m": "14.0",
    "17m": "18.068",
    "15m": "21.0",
    "12m": "24.89",
    "10m": "28.0",
    "6m": "50.0",
    "4m": "70.0",
    "2m": "144.0",
    "1.25m": "222.0",
    "70cm": "432.0",
    "23cm": "1296.0",
}


def _split_date(qso_date: str) -> tuple[str, str, str]:
    """ "YYYYMMDD" -> (date_d, date_m, date_y) mit 2-stelligem Jahr (Reihenfolge D M Y)."""
    date = (qso_date or "").strip()
    if len(date) >= 8:
        return date[6:8], date[4:6], date[2:4]
    return "", "", ""


def _format_utc(time_on: str) -> str:
    """ "HHMM"/"HHMMSS" -> "HH:MM" (Sekunden abschneiden)."""
    time = (time_on or "").strip()
    if len(time) >= 4:
        return f"{time[0:2]}:{time[2:4]}"
    return ""


def _freq_mhz(qso: QSO) -> str:
    """Frequenz in MHz aus FREQ; fehlt es, aus BAND ableiten."""
    if qso.freq:
        return qso.freq.strip()
    if qso.band:
        return BAND_TO_MHZ.get(qso.band.strip().lower(), "")
    return ""


def _make_row(qso: QSO) -> CardRow:
    date_d, date_m, date_y = _split_date(qso.qso_date)
    return CardRow(
        date_d=date_d,
        date_m=date_m,
        date_y=date_y,
        utc=_format_utc(qso.time_on),
        freq_mhz=_freq_mhz(qso),
        mode=(qso.mode or "").strip(),
        rst_sent=(qso.rst_sent or "").strip(),
    )


def _resolve_via(
    call: str, lookups: Lookups | None, default_via: str
) -> tuple[str, str, LookupResult | None]:
    """Ermittelt (via_code, via_text, recipient) für ein Rufzeichen aus dem Lookup.

    - `via_code` via `derive_via` (Priorität M>B>D>E, Fallback `default_via`).
    - `via_text` = QSL-Manager (oder leer) → Feld „Via:" auf der Karte.
    - `recipient` = das volle Lookup-Ergebnis (Adresse) für den Export, oder None.
    """
    result = lookups.get((call or "").strip().upper()) if lookups else None
    via_code = derive_via(result, default_via)
    via_text = (result.manager or "").strip() if result and result.manager else ""
    return via_code, via_text, result


def build_cards(qsos: list[QSO], config: AppConfig, lookups: Lookups | None = None) -> list[Card]:
    """Wandelt **alle** QSOs in Karten um (Umformung, Gruppierung, Sortierung).

    `lookups` liefert je Rufzeichen Via/Manager/Adresse; ohne Eintrag gilt
    `default_via` und ein leeres „Via:"-Feld. Es wird **nicht** nach Via gefiltert.
    """
    gen = config.generation

    if gen.card_mode == "per_station":
        cards = _group_per_station(qsos, lookups, gen.default_via)
    else:  # "per_qso" (Default)
        cards = _group_per_qso(qsos, lookups, gen.default_via)

    # Globale, manuelle Markierungen aus der Config je Karte übernehmen.
    for card in cards:
        card.qsl_mark = gen.qsl_mark
        card.portable_mark = gen.portable_mark

    # Deterministische Sortierung: Call, dann Datum/Zeit, dann Via.
    cards.sort(key=_card_sort_key)
    return cards


def _group_per_qso(qsos: list[QSO], lookups: Lookups | None, default_via: str) -> list[Card]:
    cards: list[Card] = []
    for qso in qsos:
        via_code, via_text, recipient = _resolve_via(qso.call, lookups, default_via)
        cards.append(
            Card(
                recipient_call=qso.call,
                via_text=via_text,
                via_code=via_code,
                rows=[_make_row(qso)],
                recipient=recipient,
            )
        )
    return cards


def _group_per_station(qsos: list[QSO], lookups: Lookups | None, default_via: str) -> list[Card]:
    # Gruppieren nach (Call, Via). Da die Via je Rufzeichen aus dem Lookup kommt,
    # ist sie für denselben Call konstant; der Schlüssel bleibt zur Sicherheit
    # (Call, Via). OrderedDict wahrt die Ersteinfüge-Reihenfolge.
    groups: OrderedDict[tuple[str, str], dict] = OrderedDict()
    for qso in qsos:
        via_code, via_text, recipient = _resolve_via(qso.call, lookups, default_via)
        key = (qso.call, via_code)
        entry = groups.setdefault(key, {"qsos": [], "via_text": via_text, "recipient": recipient})
        entry["qsos"].append(qso)

    cards: list[Card] = []
    for (call, via_code), entry in groups.items():
        group: list[QSO] = entry["qsos"]
        # innerhalb der Station nach Datum/Zeit sortieren
        group.sort(key=lambda q: (q.qso_date, q.time_on))
        rows = [_make_row(q) for q in group]
        # MAX_ROWS-Überlauf: Folge-Karten mit demselben Call/Via anlegen.
        for start in range(0, len(rows), MAX_ROWS):
            cards.append(
                Card(
                    recipient_call=call,
                    via_text=entry["via_text"],
                    via_code=via_code,
                    rows=rows[start : start + MAX_ROWS],
                    recipient=entry["recipient"],
                )
            )
    return cards


def _card_sort_key(card: Card) -> tuple[str, str, str, str, str, str]:
    first = card.rows[0]
    return (
        card.recipient_call,
        first.date_y,
        first.date_m,
        first.date_d,
        first.utc,
        card.via_code,
    )
