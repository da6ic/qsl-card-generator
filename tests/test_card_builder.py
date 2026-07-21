"""Tests für cards.builder.build_cards (SPECIFICATION.md §5.2)."""

from __future__ import annotations

from qslcards.adif.models import QSO
from qslcards.cards.builder import build_cards
from qslcards.config import AppConfig, GenerationConfig
from qslcards.pdf.geometry import MAX_ROWS


def make_qso(call, date="20260719", time="1508", via=None, qsl_via=None, **kw) -> QSO:
    return QSO(
        call=call,
        qso_date=date,
        time_on=time,
        qsl_sent_via=via,
        qsl_via=qsl_via,
        **kw,
    )


def config(**gen) -> AppConfig:
    return AppConfig(generation=GenerationConfig(**gen))


# --- Via-Filter -----------------------------------------------------------


def test_via_filter_keeps_only_selected():
    qsos = [
        make_qso("DL1AA", via="B"),
        make_qso("DL2BB", via="D"),
        make_qso("DL3CC", via="E"),
    ]
    cards = build_cards(qsos, config(via_filter=["B", "D"]))
    assert {c.recipient_call for c in cards} == {"DL1AA", "DL2BB"}


def test_missing_via_excluded_by_default():
    qsos = [make_qso("DL1AA", via=None)]
    cards = build_cards(qsos, config())  # include_missing_via=False (Default)
    assert cards == []


def test_missing_via_included_uses_default_via():
    qsos = [make_qso("DL1AA", via=None)]
    cards = build_cards(
        qsos,
        config(include_missing_via=True, default_via="B", via_filter=["B"]),
    )
    assert len(cards) == 1
    assert cards[0].via_code == "B"


# --- Datum-Split / UTC / freq --------------------------------------------


def test_date_split_dmy_and_utc():
    qsos = [make_qso("DL1AA", date="20260719", time="143825", via="B")]
    row = build_cards(qsos, config(via_filter=["B"]))[0].rows[0]
    assert (row.date_d, row.date_m, row.date_y) == ("19", "07", "26")
    assert row.utc == "14:38"  # Sekunden abgeschnitten


def test_utc_hhmm_without_seconds():
    qsos = [make_qso("DL1AA", time="0900", via="B")]
    row = build_cards(qsos, config(via_filter=["B"]))[0].rows[0]
    assert row.utc == "09:00"


def test_freq_from_field_then_band():
    qsos = [
        make_qso("DL1AA", via="B", freq="14.074", band="20m"),
        make_qso("DL2BB", via="B", freq=None, band="40m"),  # aus Band abgeleitet
        make_qso("DL3CC", via="B", freq=None, band=None),  # unbekannt -> leer
    ]
    cards = build_cards(qsos, config(via_filter=["B"]))
    by_call = {c.recipient_call: c.rows[0].freq_mhz for c in cards}
    assert by_call["DL1AA"] == "14.074"
    assert by_call["DL2BB"] == "7.0"
    assert by_call["DL3CC"] == ""


# --- per_qso vs per_station ----------------------------------------------


def test_per_qso_one_card_per_qso():
    qsos = [
        make_qso("DL1AA", date="20260719", time="1000", via="B"),
        make_qso("DL1AA", date="20260720", time="1100", via="B"),
    ]
    cards = build_cards(qsos, config(card_mode="per_qso", via_filter=["B"]))
    assert len(cards) == 2
    assert all(len(c.rows) == 1 for c in cards)


def test_per_station_groups_same_call_and_via():
    # per_station sammelt QSOs einer (Call, Via) und teilt sie in MAX_ROWS-große
    # Karten auf; die Zeilen bleiben nach Datum/Zeit sortiert.
    import math

    qsos = [
        make_qso("DL1AA", date="20260720", time="1100", via="B"),
        make_qso("DL1AA", date="20260719", time="1000", via="B"),
    ]
    cards = build_cards(qsos, config(card_mode="per_station", via_filter=["B"]))
    assert len(cards) == math.ceil(len(qsos) / MAX_ROWS)
    all_rows = [r for c in cards for r in c.rows]
    assert [r.date_d for r in all_rows] == ["19", "20"]  # sortiert über alle Karten
    assert all(len(c.rows) <= MAX_ROWS for c in cards)


def test_per_station_different_via_not_merged():
    qsos = [
        make_qso("DL1AA", via="B"),
        make_qso("DL1AA", via="D"),
    ]
    cards = build_cards(qsos, config(card_mode="per_station", via_filter=["B", "D"]))
    assert len(cards) == 2
    assert {c.via_code for c in cards} == {"B", "D"}


# --- MAX_ROWS-Überlauf ----------------------------------------------------


def test_max_rows_overflow_creates_followup_cards():
    n = MAX_ROWS * 2 + 1  # zwei volle Karten + eine Rest-Karte
    qsos = [make_qso("DL1AA", date="20260719", time=f"{h:02d}00", via="B") for h in range(n)]
    cards = build_cards(qsos, config(card_mode="per_station", via_filter=["B"]))
    assert len(cards) == 3
    assert [len(c.rows) for c in cards] == [MAX_ROWS, MAX_ROWS, 1]
    assert all(c.recipient_call == "DL1AA" for c in cards)


# --- Markierungen (Schritt 7) --------------------------------------------


def test_marks_taken_from_config_no_auto_logic():
    qsos = [make_qso("DL1AA", via="B"), make_qso("DL2BB", via="D")]
    cards = build_cards(
        qsos,
        config(via_filter=["B", "D"], qsl_mark="tnx", portable_mark="p"),
    )
    assert cards  # nicht leer
    assert all(c.qsl_mark == "tnx" for c in cards)
    assert all(c.portable_mark == "p" for c in cards)


def test_marks_default_none():
    qsos = [make_qso("DL1AA", via="B")]
    card = build_cards(qsos, config(via_filter=["B"]))[0]
    assert card.qsl_mark == "none"
    assert card.portable_mark == "none"


# --- Sortierung -----------------------------------------------------------


def test_cards_sorted_by_call_then_date():
    qsos = [
        make_qso("DL2BB", date="20260719", via="B"),
        make_qso("DL1AA", date="20260720", via="B"),
        make_qso("DL1AA", date="20260719", via="B"),
    ]
    cards = build_cards(qsos, config(card_mode="per_qso", via_filter=["B"]))
    keys = [(c.recipient_call, c.rows[0].date_d) for c in cards]
    assert keys == [("DL1AA", "19"), ("DL1AA", "20"), ("DL2BB", "19")]


# --- via_text -------------------------------------------------------------


def test_via_text_from_qsl_via():
    qsos = [make_qso("DL1AA", via="M", qsl_via="DK0XYZ")]
    card = build_cards(qsos, config(via_filter=["M"]))[0]
    assert card.via_text == "DK0XYZ"
