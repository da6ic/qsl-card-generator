"""Tests für cards.builder.build_cards (SPECIFICATION.md §5.2).

Neues Modell: **kein Via-Filter**. `build_cards` baut Karten für *alle* QSOs;
die Versandart (Via), der Manager und die Adresse kommen aus der optionalen
Lookup-Map `CALL -> LookupResult`; ohne Eintrag gilt `default_via`.
"""

from __future__ import annotations

from qslcards.cards.builder import (
    build_cards,
    effective_via,
    is_printable,
    mostwanted_rank,
    normalize_station_cards,
    regroup_card_by_remarks,
)
from qslcards.cards.models import Card, CardRow
from qslcards.config import AppConfig, GenerationConfig
from qslcards.logbook import QSO
from qslcards.lookup.base import LookupResult
from qslcards.mostwanted import MostWantedFilter, MostWantedList, RankedEntity
from qslcards.pdf.geometry import MAX_ROWS, MAX_ROWS_PLAIN, MAX_ROWS_WITH_REMARKS


def make_qso(call, date="20260719", time="1508", **kw) -> QSO:
    return QSO(call=call, qso_date=date, time_on=time, **kw)


def config(**gen) -> AppConfig:
    return AppConfig(generation=GenerationConfig(**gen))


def res(call, **kw) -> LookupResult:
    return LookupResult(call=call, **kw)


# --- Kein Via-Filter: alle QSOs werden zu Karten --------------------------


def test_all_qsos_become_cards_without_lookups():
    qsos = [make_qso("DL1AA"), make_qso("DL2BB"), make_qso("DL3CC")]
    cards = build_cards(qsos, config())  # keine Lookups
    assert {c.recipient_call for c in cards} == {"DL1AA", "DL2BB", "DL3CC"}
    # ohne Lookup-Info: default_via als einziger Weg, leeres Via-Feld
    assert all(c.via_routes == ("B",) for c in cards)
    assert all(c.via_text == "" for c in cards)


def test_default_via_configurable():
    qsos = [make_qso("DL1AA")]
    cards = build_cards(qsos, config(default_via="D"))
    assert cards[0].via_routes == ("D",)


# --- Wege/Manager/Adresse aus dem Lookup ----------------------------------


def test_routes_and_manager_from_lookup():
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", manager="DK0XYZ", accepts_bureau="Y")}
    card = build_cards(qsos, config(), lookups)[0]
    # Manager zählt als Büro-Weg; das Via-Feld bekommt den Manager-Call.
    assert card.via_routes == ("B",)
    assert card.via_text == "DK0XYZ"
    assert card.recipient is lookups["DL1AA"]


def test_freetext_manager_is_filtered_from_via_field():
    # Nur Routing-Freitext im Manager-Feld → Via-Feld bleibt leer und der
    # Freitext erzwingt keinen Büro-Weg (nur der explizite LOTW-Weg zählt).
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", manager="LoTW", lotw="Y")}
    card = build_cards(qsos, config(), lookups)[0]
    assert card.via_text == ""
    assert card.via_routes == ("L",)


def test_manager_callsign_extracted_from_freetext():
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", manager="QSL via DK1XY direct")}
    card = build_cards(qsos, config(), lookups)[0]
    assert card.via_text == "DK1XY"
    assert card.via_routes == ("B",)  # echtes Rufzeichen zählt als Büro-Weg


def test_routes_bureau_and_direct_from_flags():
    qsos = [make_qso("DL1AA"), make_qso("DL2BB")]
    lookups = {
        "DL1AA": res("DL1AA", accepts_bureau="Y"),
        "DL2BB": res("DL2BB", accepts_bureau="N", accepts_direct="Y"),
    }
    by_call = {c.recipient_call: c.via_routes for c in build_cards(qsos, config(), lookups)}
    assert by_call == {"DL1AA": ("B",), "DL2BB": ("D",)}


def test_electronic_station_gets_q_and_l_routes():
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", accepts_bureau="N", accepts_direct="N", eqsl="Y", lotw="Y")}
    card = build_cards(qsos, config(), lookups)[0]
    assert card.via_routes == ("Q", "L")


def test_missing_lookup_entry_uses_default_via():
    qsos = [make_qso("DL1AA")]
    lookups = {}  # Call nicht enthalten
    assert build_cards(qsos, config(default_via="B"), lookups)[0].via_routes == ("B",)


# --- effective_via: Auflösung aus Prioritätsliste --------------------------


def test_effective_via_picks_highest_active_route():
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", manager="DK0XYZ", eqsl="Y", lotw="Y")}
    card = build_cards(qsos, config(), lookups)[0]  # Wege: ("B", "Q", "L")
    # Aktiv absteigend Büro, Direkt -> Manager zählt als Büro -> gedruckt per B.
    assert effective_via(card, ["B", "D"]) == "B"
    # Nur eQSL aktiv -> Q gewinnt.
    assert effective_via(card, ["Q", "L"]) == "Q"


def test_effective_via_none_when_no_active_route_matches():
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", accepts_bureau="N", accepts_direct="N", lotw="Y")}
    card = build_cards(qsos, config(), lookups)[0]  # Wege: ("L",)
    assert effective_via(card, ["B", "D"]) is None  # nicht gedruckt


def test_effective_via_override_forces_route_but_respects_cut():
    qsos = [make_qso("DL1AA")]
    card = build_cards(qsos, config(), {})[0]  # Wege: ("B",)
    card.via_override = "L"
    # Override erzwingt den Weg, aber LOTW liegt unter der Linie -> nicht gedruckt.
    assert effective_via(card, ["B", "D"]) is None
    # LOTW aktiv -> der erzwungene Weg wird gedruckt.
    assert effective_via(card, ["L", "B"]) == "L"


# --- Datum-Split / UTC / freq --------------------------------------------


def test_date_split_dmy_and_utc():
    qsos = [make_qso("DL1AA", date="20260719", time="143825")]
    row = build_cards(qsos, config())[0].rows[0]
    assert (row.date_d, row.date_m, row.date_y) == ("19", "07", "26")
    assert row.utc == "14:38"  # Sekunden abgeschnitten


def test_utc_hhmm_without_seconds():
    qsos = [make_qso("DL1AA", time="0900")]
    assert build_cards(qsos, config())[0].rows[0].utc == "09:00"


def test_freq_from_field_then_band():
    qsos = [
        make_qso("DL1AA", freq="14.074", band="20m"),
        make_qso("DL2BB", freq=None, band="40m"),  # aus Band abgeleitet
        make_qso("DL3CC", freq=None, band=None),  # unbekannt -> leer
    ]
    by_call = {c.recipient_call: c.rows[0].freq_mhz for c in build_cards(qsos, config())}
    assert by_call["DL1AA"] == "14.074"
    assert by_call["DL2BB"] == "7.000"  # aus Band abgeleitet, auf 3 Nachkommastellen
    assert by_call["DL3CC"] == ""


# --- per_qso vs per_station ----------------------------------------------


def test_per_qso_one_card_per_qso():
    qsos = [
        make_qso("DL1AA", date="20260719", time="1000"),
        make_qso("DL1AA", date="20260720", time="1100"),
    ]
    cards = build_cards(qsos, config(card_mode="per_qso"))
    assert len(cards) == 2
    assert all(len(c.rows) == 1 for c in cards)


def test_per_station_groups_same_call():
    import math

    qsos = [
        make_qso("DL1AA", date="20260720", time="1100"),
        make_qso("DL1AA", date="20260719", time="1000"),
    ]
    cards = build_cards(qsos, config(card_mode="per_station"))
    assert len(cards) == math.ceil(len(qsos) / MAX_ROWS)
    all_rows = [r for c in cards for r in c.rows]
    assert [r.date_d for r in all_rows] == ["19", "20"]  # sortiert über alle Karten
    assert all(len(c.rows) <= MAX_ROWS for c in cards)


def test_per_station_different_calls_not_merged():
    qsos = [make_qso("DL1AA"), make_qso("DL2BB")]
    cards = build_cards(qsos, config(card_mode="per_station"))
    assert {c.recipient_call for c in cards} == {"DL1AA", "DL2BB"}


# --- MAX_ROWS-Überlauf ----------------------------------------------------


def test_max_rows_overflow_creates_followup_cards():
    # Ohne Remarks gilt die höhere Grenze MAX_ROWS_PLAIN.
    n = MAX_ROWS_PLAIN * 2 + 1  # zwei volle Karten + eine Rest-Karte
    qsos = [make_qso("DL1AA", date="20260719", time=f"{h:02d}00") for h in range(n)]
    cards = build_cards(qsos, config(card_mode="per_station"))
    assert len(cards) == 3
    assert [len(c.rows) for c in cards] == [MAX_ROWS_PLAIN, MAX_ROWS_PLAIN, 1]
    assert all(c.recipient_call == "DL1AA" for c in cards)
    assert MAX_ROWS == MAX_ROWS_PLAIN  # Layout-Cap = Plain-Maximum


# --- Remarks koppeln die Zeilen-Aufteilung --------------------------------


def test_remarks_reduce_rows_per_card():
    # Mit globalem Remarks-Text passen weniger QSOs auf eine Karte -> mehr Karten.
    n = MAX_ROWS_WITH_REMARKS * 2 + 1
    qsos = [make_qso("DL1AA", date="20260719", time=f"{h:02d}00") for h in range(n)]
    cards = build_cards(qsos, config(card_mode="per_station", remarks="TNX QSO"))
    assert [len(c.rows) for c in cards] == [MAX_ROWS_WITH_REMARKS, MAX_ROWS_WITH_REMARKS, 1]
    # Der Remarks-Text landet (als Default) auf jeder Karte.
    assert all(c.remarks == "TNX QSO" for c in cards)


def test_no_remarks_leaves_card_remarks_empty():
    qsos = [make_qso("DL1AA")]
    cards = build_cards(qsos, config())
    assert cards[0].remarks == ""


# --- regroup_card_by_remarks: Zeilen je Karte pro Remarks-Zustand ---------


def _card(n_rows: int, remarks: str = "") -> Card:
    rows = [CardRow("19", "07", "26", "14:38", "14.230", "SSB", "59") for _ in range(n_rows)]
    return Card(recipient_call="DL1AA", via_text="", via_routes=("B",), rows=rows, remarks=remarks)


def test_regroup_splits_overflow_with_remarks():
    parts = regroup_card_by_remarks(_card(MAX_ROWS_PLAIN, remarks="TNX"))
    # 6 Zeilen + Remarks -> zwei Karten (3 + 3), beide mit demselben Remarks-Text.
    assert [len(p.rows) for p in parts] == [MAX_ROWS_WITH_REMARKS, MAX_ROWS_WITH_REMARKS]
    assert all(p.remarks == "TNX" for p in parts)
    assert all(p.recipient_call == "DL1AA" for p in parts)


def test_regroup_noop_without_remarks_up_to_plain_limit():
    card = _card(MAX_ROWS_PLAIN, remarks="")
    assert regroup_card_by_remarks(card) == [card]


def test_regroup_splits_overflow_without_remarks():
    # Ohne Remarks gilt die höhere Grenze; erst darüber wird geteilt.
    parts = regroup_card_by_remarks(_card(MAX_ROWS_PLAIN + 2, remarks=""))
    assert [len(p.rows) for p in parts] == [MAX_ROWS_PLAIN, 2]


def test_regroup_noop_when_fits():
    card = _card(MAX_ROWS_WITH_REMARKS, remarks="X")
    assert regroup_card_by_remarks(card) == [card]


def test_regroup_is_idempotent():
    once = regroup_card_by_remarks(_card(MAX_ROWS_PLAIN + 1, remarks="Y"))
    twice = [p for c in once for p in regroup_card_by_remarks(c)]
    assert [len(p.rows) for p in once] == [len(p.rows) for p in twice]


# --- normalize_station_cards: Remarks pro Karte unabhängig ----------------


def test_normalize_merges_consecutive_no_remarks():
    # Reines Split-Artefakt (beide ohne Remarks) -> wieder eine Karte.
    out = normalize_station_cards([_card(3, ""), _card(2, "")])
    assert [(len(c.rows), c.remarks) for c in out] == [(5, "")]


def test_normalize_keeps_single_remarks_card_separate():
    # Genau eine Karte mit Remarks, die andere ohne -> bleiben getrennt.
    out = normalize_station_cards([_card(3, "TNX"), _card(2, "")])
    assert [(len(c.rows), c.remarks) for c in out] == [(3, "TNX"), (2, "")]


def test_normalize_remarks_card_acts_as_barrier():
    # No-Remarks / Remarks / No-Remarks -> die beiden No-Remarks NICHT mergen.
    out = normalize_station_cards([_card(2, ""), _card(2, "X"), _card(2, "")])
    assert [(len(c.rows), c.remarks) for c in out] == [(2, ""), (2, "X"), (2, "")]


def test_normalize_merge_clears_remarks_manual_flag():
    # Ein zusammengeführter No-Remarks-Block darf das Manuell-Flag nicht erben,
    # selbst wenn die erste (Template-)Karte manuell gesetzt war.
    manual = _card(2, "")
    manual.remarks_manual = True
    out = normalize_station_cards([manual, _card(2, "")])
    assert [(len(c.rows), c.remarks, c.remarks_manual) for c in out] == [(4, "", False)]


def test_normalize_splits_overflow_per_state():
    assert [len(c.rows) for c in normalize_station_cards([_card(MAX_ROWS_PLAIN + 2, "")])] == [
        MAX_ROWS_PLAIN,
        2,
    ]
    assert [len(c.rows) for c in normalize_station_cards([_card(5, "A")])] == [
        MAX_ROWS_WITH_REMARKS,
        2,
    ]


def test_normalize_is_idempotent():
    once = normalize_station_cards([_card(5, "A"), _card(4, "")])
    twice = normalize_station_cards(once)
    assert [(len(c.rows), c.remarks) for c in once] == [(len(c.rows), c.remarks) for c in twice]


# --- Markierungen ---------------------------------------------------------


def test_marks_taken_from_config_no_auto_logic():
    qsos = [make_qso("DL1AA"), make_qso("DL2BB")]
    cards = build_cards(qsos, config(qsl_mark="tnx", confirm_mark="swl"))
    assert cards
    assert all(c.qsl_mark == "tnx" for c in cards)
    assert all(c.confirm_mark == "swl" for c in cards)


def test_marks_default_none():
    card = build_cards([make_qso("DL1AA")], config())[0]
    assert card.qsl_mark == "none"
    assert card.confirm_mark == "none"


# --- Sortierung -----------------------------------------------------------


def test_cards_sorted_by_call_then_date():
    qsos = [
        make_qso("DL2BB", date="20260719"),
        make_qso("DL1AA", date="20260720"),
        make_qso("DL1AA", date="20260719"),
    ]
    cards = build_cards(qsos, config(card_mode="per_qso"))
    keys = [(c.recipient_call, c.rows[0].date_d) for c in cards]
    assert keys == [("DL1AA", "19"), ("DL1AA", "20"), ("DL2BB", "19")]


# --- DXCC + Most-Wanted-Filter -------------------------------------------

# Kleine Rangliste: P5 (344) überall vorn, JA (339) in CW weit hinten,
# DL (230) ganz am Ende.
RANKING = MostWantedList(
    year=2025,
    rankings={
        category: {
            dxcc: RankedEntity(dxcc=dxcc, rank=rank, prefix="", name="")
            for dxcc, rank in ranks.items()
        }
        for category, ranks in {
            "mixed": {344: 1, 339: 60, 230: 340},
            "cw": {344: 1, 339: 300, 230: 339},
            "phone": {344: 1, 339: 20, 230: 339},
            "digital": {344: 9, 339: 150, 230: 339},
        }.items()
    },
)


def test_dxcc_from_log_wins_over_lookup():
    qsos = [make_qso("JA1AA", dxcc="339")]
    lookups = {"JA1AA": res("JA1AA", dxcc="291")}
    assert build_cards(qsos, config(), lookups)[0].dxcc == 339


def test_dxcc_from_lookup_when_log_has_none():
    qsos = [make_qso("JA1AA")]
    assert build_cards(qsos, config(), {"JA1AA": res("JA1AA", dxcc="339")})[0].dxcc == 339
    # weder Log noch Lookup -> unbekannt
    assert build_cards(qsos, config())[0].dxcc is None


def test_dxcc_order_is_log_then_cty_then_lookup():
    """Log-Feld vor cty.dat vor Lookup — die cty.dat macht den Filter
    unabhängig von Zugangsdaten und funktioniert auch für Cabrillo."""
    cty = {"JA1AA": 339, "VK9DX": 189}.get
    lookups = {"JA1AA": res("JA1AA", dxcc="291"), "ZZ9ZZ": res("ZZ9ZZ", dxcc="1")}
    qsos = [make_qso("JA1AA"), make_qso("VK9DX", dxcc="150"), make_qso("ZZ9ZZ")]
    cards = {c.recipient_call: c for c in build_cards(qsos, config(), lookups, resolve_dxcc=cty)}
    assert cards["JA1AA"].dxcc == 339  # cty.dat schlägt den Lookup
    assert cards["VK9DX"].dxcc == 150  # das Log schlägt die cty.dat
    assert cards["ZZ9ZZ"].dxcc == 1  # cty.dat kennt es nicht -> Lookup


def test_dxcc_per_station_takes_first_known():
    qsos = [make_qso("JA1AA", time="1000"), make_qso("JA1AA", time="1100", dxcc="339")]
    card = build_cards(qsos, config(card_mode="per_station"))[0]
    assert card.dxcc == 339


def test_auto_category_measures_each_mode_and_takes_the_best():
    """„pro Station" mit CW (Rang 300) und SSB (Rang 20): die Karte zählt mit 20."""
    qsos = [
        make_qso("JA1AA", time="1000", mode="CW", dxcc="339"),
        make_qso("JA1AA", time="1100", mode="SSB", dxcc="339"),
    ]
    card = build_cards(qsos, config(card_mode="per_station"))[0]
    assert mostwanted_rank(card, MostWantedFilter(RANKING, top=50)) == 20
    assert mostwanted_rank(card, MostWantedFilter(RANKING, category="cw")) == 300


def test_fixed_category_counts_only_qsos_in_that_mode():
    """Wie im DXCC-Filter des Kollegen: an der CW-Liste zählen nur CW-QSOs.
    Mixed nimmt alle; „Automatisch" misst jedes QSO an seiner eigenen Liste."""
    ssb = build_cards([make_qso("JA1AA", mode="SSB", dxcc="339")], config())[0]
    assert mostwanted_rank(ssb, MostWantedFilter(RANKING, category="cw")) is None
    assert mostwanted_rank(ssb, MostWantedFilter(RANKING, category="phone")) == 20
    assert mostwanted_rank(ssb, MostWantedFilter(RANKING, category="mixed")) == 60


def test_is_printable_needs_route_and_mostwanted():
    rare = build_cards([make_qso("P5AA", mode="FT8", dxcc="344")], config())[0]
    common = build_cards([make_qso("DL1AA", mode="FT8", dxcc="230")], config())[0]
    active = ["B", "D"]
    top50 = MostWantedFilter(RANKING, top=50)

    # Filter aus -> nur die Zustellwege zählen.
    assert is_printable(rare, active) and is_printable(common, active)
    # Filter an -> nur die Top 50 (P5 ist Digital-Rang 9, DL Rang 339).
    assert is_printable(rare, active, top50)
    assert not is_printable(common, active, top50)
    # Kein aktiver Weg schlägt jeden Rang.
    assert not is_printable(rare, ["L"], top50)


def test_unknown_dxcc_or_missing_list_is_not_printed():
    """So mit dem Nutzer entschieden: ohne Gebiet bzw. ohne Liste kein Druck."""
    unknown = build_cards([make_qso("XX1AA")], config())[0]
    rare = build_cards([make_qso("P5AA", dxcc="344")], config())[0]
    assert not is_printable(unknown, ["B"], MostWantedFilter(RANKING))
    assert not is_printable(rare, ["B"], MostWantedFilter(None))
