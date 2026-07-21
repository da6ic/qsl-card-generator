"""Karten-Erzeugung: QSOs filtern, umformen, gruppieren (siehe SPECIFICATION.md §5.2)."""

from __future__ import annotations

from collections import OrderedDict

from qslcards.adif.models import QSO
from qslcards.config import AppConfig
from qslcards.pdf.geometry import MAX_ROWS

from .models import Card, CardRow

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


def _effective_via(qso: QSO, config: AppConfig) -> str | None:
    """Liefert den wirksamen Via-Code für ein QSO oder None (= verwerfen).

    Schritt 1: QSO behalten, wenn qsl_sent_via im via_filter liegt. QSOs ohne Via
    nur, wenn include_missing_via gesetzt ist (dann default_via verwenden).
    """
    gen = config.generation
    via = qso.qsl_sent_via
    if via is None:
        if gen.include_missing_via:
            return gen.default_via
        return None
    if via in gen.via_filter:
        return via
    return None


def build_cards(qsos: list[QSO], config: AppConfig) -> list[Card]:
    """Wandelt QSOs in Karten um (Filter, Umformung, Gruppierung, Sortierung)."""
    gen = config.generation

    # 1. Filtern + wirksamen Via-Code bestimmen.
    kept: list[tuple[QSO, str]] = []
    for qso in qsos:
        via = _effective_via(qso, config)
        if via is not None:
            kept.append((qso, via))

    if gen.card_mode == "per_station":
        cards = _group_per_station(kept)
    else:  # "per_qso" (Default)
        cards = _group_per_qso(kept)

    # 7. Globale, manuelle Markierungen aus der Config je Karte übernehmen.
    for card in cards:
        card.qsl_mark = gen.qsl_mark
        card.portable_mark = gen.portable_mark

    # 6. Deterministische Sortierung: Call, dann Datum/Zeit, dann Via.
    cards.sort(key=_card_sort_key)
    return cards


def _group_per_qso(kept: list[tuple[QSO, str]]) -> list[Card]:
    cards: list[Card] = []
    for qso, via in kept:
        cards.append(
            Card(
                recipient_call=qso.call,
                via_text=(qso.qsl_via or "").strip(),
                via_code=via,
                rows=[_make_row(qso)],
            )
        )
    return cards


def _group_per_station(kept: list[tuple[QSO, str]]) -> list[Card]:
    # Gruppieren nach (Call, Via). OrderedDict wahrt Ersteinfüge-Reihenfolge
    # (die endgültige Sortierung erfolgt ohnehin am Ende).
    groups: OrderedDict[tuple[str, str], list[QSO]] = OrderedDict()
    for qso, via in kept:
        groups.setdefault((qso.call, via), []).append(qso)

    cards: list[Card] = []
    for (call, via), group in groups.items():
        # innerhalb der Station nach Datum/Zeit sortieren
        group.sort(key=lambda q: (q.qso_date, q.time_on))
        via_text = next((q.qsl_via.strip() for q in group if q.qsl_via), "")
        rows = [_make_row(q) for q in group]
        # MAX_ROWS-Überlauf: Folge-Karten mit demselben Call/Via anlegen.
        for start in range(0, len(rows), MAX_ROWS):
            cards.append(
                Card(
                    recipient_call=call,
                    via_text=via_text,
                    via_code=via,
                    rows=rows[start : start + MAX_ROWS],
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
