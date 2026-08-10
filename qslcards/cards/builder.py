"""Karten-Erzeugung: QSOs umformen und gruppieren (siehe SPECIFICATION.md §5.2).

**Kein Via-Filter**: es entstehen Karten für *alle* QSOs. Die akzeptierten
Zustellwege, der QSL-Manager und die Adresse kommen aus dem Lookup (Map
`CALL -> LookupResult`, optional); ohne Treffer gilt `default_via`. Welcher Weg
tatsächlich gedruckt wird — und ob überhaupt — entscheidet die Prioritätsliste
der GUI (`effective_via`), nicht dieses Modul.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from qslcards.config import AppConfig
from qslcards.logbook import QSO
from qslcards.lookup import accepted_routes, extract_manager_callsign, resolve_route
from qslcards.pdf.geometry import MAX_ROWS_PLAIN, MAX_ROWS_WITH_REMARKS

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
    """Frequenz in MHz aus FREQ; fehlt es, aus BAND ableiten. Immer 3 Nachkommastellen."""
    raw = qso.freq.strip() if qso.freq else ""
    if not raw and qso.band:
        raw = BAND_TO_MHZ.get(qso.band.strip().lower(), "")
    return _format_freq(raw)


def _format_freq(raw: str) -> str:
    if not raw:
        return ""
    try:
        return f"{float(raw):.3f}"
    except ValueError:
        return raw


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
) -> tuple[tuple[str, ...], str, LookupResult | None]:
    """Ermittelt (via_routes, via_text, recipient) für ein Rufzeichen aus dem Lookup.

    - `via_routes` = akzeptierte Zustellwege (B/D/Q/L) via `accepted_routes`;
      ohne verwertbaren Treffer `(default_via,)`.
    - `via_text` = gesäubertes Manager-Rufzeichen (oder leer) → Feld „Via:" auf
      der Karte; der rohe Manager-Freitext wird verworfen (siehe
      `extract_manager_callsign`).
    - `recipient` = das volle Lookup-Ergebnis (Adresse) für den Export, oder None.
    """
    result = lookups.get((call or "").strip().upper()) if lookups else None
    via_routes = accepted_routes(result, default_via)
    via_text = extract_manager_callsign(result.manager) if result else ""
    return via_routes, via_text, result


def effective_via(card: Card, active_priority: Sequence[str]) -> str | None:
    """Der tatsächlich zu druckende Weg einer Karte (oder `None` = nicht drucken).

    Ein manueller Override (`card.via_override`) erzwingt den *Weg*, respektiert
    aber weiterhin die Trennlinie: liegt der Weg unter der Linie (nicht in
    `active_priority`), wird die Karte **nicht** gedruckt. Ohne Override wird der
    höchstpriorisierte aktive Weg aus `card.via_routes` gewählt (`resolve_route`).
    Einzige Quelle der Wahrheit für Vorschau **und** Export.
    """
    via = card.via_override or resolve_route(card.via_routes, active_priority)
    return via if via in active_priority else None


def build_cards(qsos: list[QSO], config: AppConfig, lookups: Lookups | None = None) -> list[Card]:
    """Wandelt **alle** QSOs in Karten um (Umformung, Gruppierung, Sortierung).

    `lookups` liefert je Rufzeichen Via/Manager/Adresse; ohne Eintrag gilt
    `default_via` und ein leeres „Via:"-Feld. Es wird **nicht** nach Via gefiltert.
    """
    gen = config.generation

    # Der globale Remarks-Text entscheidet, ob der Remarks-Kasten gezeichnet wird
    # (dynamisch) — und damit, wie viele QSO-Zeilen je Karte Platz haben: mit
    # Remarks weniger (der Kasten braucht Raum), ohne Remarks mehr. Der Builder
    # splittet je Station nach dieser Grenze in Folge-Karten.
    remarks = (gen.remarks or "").strip()
    max_rows = MAX_ROWS_WITH_REMARKS if remarks else MAX_ROWS_PLAIN

    if gen.card_mode == "per_station":
        cards = _group_per_station(qsos, lookups, gen.default_via, max_rows)
    else:  # "per_qso" (Default)
        cards = _group_per_qso(qsos, lookups, gen.default_via)

    # Globale, manuelle Markierungen aus der Config je Karte übernehmen.
    for card in cards:
        card.qsl_mark = gen.qsl_mark
        card.confirm_mark = gen.confirm_mark
        card.remarks = remarks

    # Deterministische Sortierung: Call, dann Datum/Zeit, dann Via.
    cards.sort(key=_card_sort_key)
    return cards


def max_rows_for_remarks(remarks: str | None) -> int:
    """Zeilen je Karte abhängig vom Remarks-Zustand: mit Remarks weniger (der
    Kasten braucht Platz), ohne Remarks mehr (siehe geometry.MAX_ROWS_*)."""
    return MAX_ROWS_WITH_REMARKS if (remarks or "").strip() else MAX_ROWS_PLAIN


def regroup_card_by_remarks(card: Card) -> list[Card]:
    """Teilt die Zeilen **einer** Karte in so viele Karten auf, wie je Karte
    Platz haben: mit Remarks MAX_ROWS_WITH_REMARKS, ohne Remarks MAX_ROWS_PLAIN.

    Rein **pro Karte** (kein Merge über Karten hinweg); zum Zusammenführen mehrerer
    Karten einer Station vorher deren Zeilen zu einer Karte verbinden und dann hier
    durchreichen (so macht es die Vorschau bei einer Remarks-Änderung). Ohne
    Überlauf bleibt es bei genau dieser einen Karte. Idempotent.
    """
    max_rows = max_rows_for_remarks(card.remarks)
    if len(card.rows) <= max_rows:
        return [card]
    return [
        replace(card, rows=card.rows[start : start + max_rows])
        for start in range(0, len(card.rows), max_rows)
    ]


def normalize_station_cards(cards: list[Card]) -> list[Card]:
    """Normalisiert die Karten **einer** Station (Call+Via), Reihenfolge bleibt.

    Remarks sind **pro Karte** unabhängig:
    - Karten **mit** Remarks bleiben eigenständig (je eigener Text) und werden in
      Blöcke <= MAX_ROWS_WITH_REMARKS geteilt.
    - Nur **aufeinanderfolgende** Karten **ohne** Remarks werden zusammengeführt
      und in Blöcke <= MAX_ROWS_PLAIN geteilt (entfernt reine Split-Artefakte).

    Dadurch kann man ein Remarks auf genau einer Karte haben (die Nachbarn ohne
    Remarks bleiben separat), und leert man alle zusammenhängenden Karten, führen
    sie sich wieder zu einer zusammen. Idempotent.
    """
    result: list[Card] = []
    buffer: list[CardRow] = []
    template: Card | None = None

    def flush() -> None:
        if buffer and template is not None:
            # Zusammengeführter No-Remarks-Block: kein Text, kein Manuell-Flag
            # (das Flag gehört nur zu Karten mit eigenständigem Remarks-Text).
            merged = replace(template, rows=list(buffer), remarks="", remarks_manual=False)
            result.extend(regroup_card_by_remarks(merged))
            buffer.clear()

    for card in cards:
        if template is None:
            template = card
        if (card.remarks or "").strip():
            flush()  # laufenden No-Remarks-Block abschließen
            result.extend(regroup_card_by_remarks(card))
        else:
            buffer.extend(card.rows)
    flush()
    return result


def _group_per_qso(qsos: list[QSO], lookups: Lookups | None, default_via: str) -> list[Card]:
    cards: list[Card] = []
    for qso in qsos:
        via_routes, via_text, recipient = _resolve_via(qso.call, lookups, default_via)
        cards.append(
            Card(
                recipient_call=qso.call,
                via_text=via_text,
                via_routes=via_routes,
                rows=[_make_row(qso)],
                recipient=recipient,
            )
        )
    return cards


def _group_per_station(
    qsos: list[QSO], lookups: Lookups | None, default_via: str, max_rows: int
) -> list[Card]:
    # Gruppieren nach Rufzeichen (die akzeptierten Wege sind je Call konstant, da
    # sie aus dem Lookup kommen). OrderedDict wahrt die Ersteinfüge-Reihenfolge.
    groups: OrderedDict[str, dict] = OrderedDict()
    for qso in qsos:
        via_routes, via_text, recipient = _resolve_via(qso.call, lookups, default_via)
        entry = groups.setdefault(
            qso.call,
            {"qsos": [], "via_routes": via_routes, "via_text": via_text, "recipient": recipient},
        )
        entry["qsos"].append(qso)

    cards: list[Card] = []
    for call, entry in groups.items():
        group: list[QSO] = entry["qsos"]
        # innerhalb der Station nach Datum/Zeit sortieren
        group.sort(key=lambda q: (q.qso_date, q.time_on))
        rows = [_make_row(q) for q in group]
        # Überlauf über max_rows: Folge-Karten mit demselben Call anlegen. Bis zu
        # max_rows QSOs landen als Zeilen auf einer Karte (dynamische Tabelle);
        # max_rows hängt davon ab, ob Remarks gedruckt werden (siehe build_cards).
        for start in range(0, len(rows), max_rows):
            cards.append(
                Card(
                    recipient_call=call,
                    via_text=entry["via_text"],
                    via_routes=entry["via_routes"],
                    rows=rows[start : start + max_rows],
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
        "".join(card.via_routes),
    )
