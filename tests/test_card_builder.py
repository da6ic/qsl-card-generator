"""Tests für cards.builder.build_cards (SPECIFICATION.md §5.2).

Neues Modell: **kein Via-Filter**. `build_cards` baut Karten für *alle* QSOs;
die Versandart (Via), der Manager und die Adresse kommen aus der optionalen
Lookup-Map `CALL -> LookupResult`; ohne Eintrag gilt `default_via`.
"""

from __future__ import annotations

from qslcards.adif.models import QSO
from qslcards.cards.builder import build_cards
from qslcards.config import AppConfig, GenerationConfig
from qslcards.lookup.base import LookupResult
from qslcards.pdf.geometry import MAX_ROWS


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
    # ohne Lookup-Info: default_via, leeres Via-Feld
    assert all(c.via_code == "B" for c in cards)
    assert all(c.via_text == "" for c in cards)


def test_default_via_configurable():
    qsos = [make_qso("DL1AA")]
    cards = build_cards(qsos, config(default_via="D"))
    assert cards[0].via_code == "D"


# --- Via/Manager/Adresse aus dem Lookup -----------------------------------


def test_via_and_manager_from_lookup():
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", manager="DK0XYZ", accepts_bureau="Y")}
    card = build_cards(qsos, config(), lookups)[0]
    assert card.via_code == "M"  # Manager hat Vorrang
    assert card.via_text == "DK0XYZ"
    assert card.recipient is lookups["DL1AA"]


def test_via_bureau_and_direct_from_flags():
    qsos = [make_qso("DL1AA"), make_qso("DL2BB")]
    lookups = {
        "DL1AA": res("DL1AA", accepts_bureau="Y"),
        "DL2BB": res("DL2BB", accepts_bureau="N", accepts_direct="Y"),
    }
    by_call = {c.recipient_call: c.via_code for c in build_cards(qsos, config(), lookups)}
    assert by_call == {"DL1AA": "B", "DL2BB": "D"}


def test_electronic_station_gets_via_e():
    qsos = [make_qso("DL1AA")]
    lookups = {"DL1AA": res("DL1AA", accepts_bureau="N", accepts_direct="N", lotw="Y")}
    assert build_cards(qsos, config(), lookups)[0].via_code == "E"


def test_missing_lookup_entry_uses_default_via():
    qsos = [make_qso("DL1AA")]
    lookups = {}  # Call nicht enthalten
    assert build_cards(qsos, config(default_via="B"), lookups)[0].via_code == "B"


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
    assert by_call["DL2BB"] == "7.0"
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
    n = MAX_ROWS * 2 + 1  # zwei volle Karten + eine Rest-Karte
    qsos = [make_qso("DL1AA", date="20260719", time=f"{h:02d}00") for h in range(n)]
    cards = build_cards(qsos, config(card_mode="per_station"))
    assert len(cards) == 3
    assert [len(c.rows) for c in cards] == [MAX_ROWS, MAX_ROWS, 1]
    assert all(c.recipient_call == "DL1AA" for c in cards)


# --- Markierungen ---------------------------------------------------------


def test_marks_taken_from_config_no_auto_logic():
    qsos = [make_qso("DL1AA"), make_qso("DL2BB")]
    cards = build_cards(qsos, config(qsl_mark="tnx", portable_mark="p"))
    assert cards
    assert all(c.qsl_mark == "tnx" for c in cards)
    assert all(c.portable_mark == "p" for c in cards)


def test_marks_default_none():
    card = build_cards([make_qso("DL1AA")], config())[0]
    assert card.qsl_mark == "none"
    assert card.portable_mark == "none"


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
