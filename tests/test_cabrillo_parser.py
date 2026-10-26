"""Tests für den Cabrillo-Parser (Fälle aus SPECIFICATION.md §4.5).

Die QSO-Zeilen stammen wörtlich aus den offiziellen Contest-Templates — genau
deren Vielfalt (2 bis 5 Austauschfelder, mit und ohne Rapport, mit und ohne
Transmitter-ID) muss die Zerlegung aushalten.
"""

from __future__ import annotations

from qslcards.cards.builder import build_cards
from qslcards.config import AppConfig
from qslcards.logbook.cabrillo import _band, _norm_freq, parse_text

HEADER = "START-OF-LOG: 3.0\nCALLSIGN: DL0MT\nCONTEST: CQ-WW-CW\n"


def _log(*qso_lines: str, header: str = HEADER) -> str:
    return header + "\n".join(qso_lines) + "\nEND-OF-LOG:\n"


# ------------------------------------------------------------------- Kopf


def test_minimal_log():
    text = _log("QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35")
    qsos = parse_text(text)
    assert len(qsos) == 1
    q = qsos[0]
    assert q.call == "XT2DX"
    assert q.qso_date == "20011124"
    assert q.time_on == "2209"
    assert q.freq == "14"
    assert q.band == "20m"
    assert q.mode == "CW"
    assert q.rst_sent == "599"
    assert q.rst_rcvd == "599"
    assert q.dxcc is None  # Cabrillo kennt kein DXCC-Feld -> nur aus dem Lookup


def test_sender_data_from_header_never_lands_in_qso():
    """CALLSIGN/GRID-LOCATOR/NAME/ADDRESS sind Absenderdaten (CLAUDE.md §5.3).

    Sie dürfen nur informativ in `raw` stehen — der Absender kommt aus der Config.
    """
    header = (
        "START-OF-LOG: 3.0\n"
        "CALLSIGN: DL0MT\n"
        "GRID-LOCATOR: JO60HS\n"
        "NAME: Axel Tuener\n"
        "ADDRESS: Wilhelmstr. 76\n"
    )
    text = _log(
        "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35",
        header=header,
    )
    q = parse_text(text)[0]
    assert q.call == "XT2DX"
    assert q.gridsquare is None  # JO60HS ist UNSER Locator
    assert q.name is None
    assert q.qth is None
    assert q.country is None
    assert q.raw["station_callsign"] == "DL0MT"
    assert q.raw["my_gridsquare"] == "JO60HS"


def test_callsign_header_after_qso_lines():
    """Die Kopf-Reihenfolge ist in Cabrillo beliebig — daher zwei Durchläufe."""
    text = (
        "START-OF-LOG: 3.0\n"
        "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35\n"
        "CALLSIGN: DL0MT\n"
        "END-OF-LOG:\n"
    )
    q = parse_text(text)[0]
    assert q.call == "XT2DX"
    assert q.raw["station_callsign"] == "DL0MT"


def test_without_header():
    text = "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35\n"
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].call == "XT2DX"


def test_repeated_header_tags():
    header = (
        "START-OF-LOG: 3.0\n"
        "CALLSIGN: DL0MT\n"
        "OPERATORS: DL0MT\n"
        "OPERATORS: DL2ND\n"
        "SOAPBOX: Danke\n"
        "SOAPBOX: fuer die QSOs\n"
    )
    text = _log("QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35", header=header)
    q = parse_text(text)[0]
    assert q.raw["operator"] == "DL0MT DL2ND"


# ------------------------------------------------------- Zeilenzerlegung


def test_cq_ww_three_fields_with_rst():
    text = _log("QSO:  3799 PH 2000-11-26 0711 N6TW 59 03 JT1Z 59 23")
    q = parse_text(text)[0]
    assert q.call == "JT1Z"
    assert q.rst_sent == "59"
    assert q.rst_rcvd == "59"
    assert q.mode == "SSB"
    assert q.raw["cabrillo_exch_rcvd"] == "59 23"


def test_transmitter_id_is_split_off():
    text = _log("QSO:  3799 PH 2000-11-26 0711 N6TW 59 03 JT1Z 59 23 0")
    q = parse_text(text)[0]
    assert q.call == "JT1Z"
    assert q.rst_sent == "59"
    assert q.raw["cabrillo_transmitter"] == "0"


def test_serial_is_not_mistaken_for_transmitter_id():
    """9A-CW: „… 599 001 9A2UE 599 101" — die 101 ist eine Seriennummer."""
    text = _log("QSO: 14000 CW 2001-11-24 2209 W3KM 599 001 9A2UE 599 101")
    q = parse_text(text)[0]
    assert q.call == "9A2UE"
    assert q.rst_sent == "599"
    assert q.rst_rcvd == "599"
    assert q.raw["cabrillo_exch_rcvd"] == "599 101"
    assert "cabrillo_transmitter" not in q.raw


def test_naqp_without_rst():
    text = _log("QSO: 14000 CW 2001-11-24 2209 N5TJ JEFF TX K6ZZ BOB CA 1")
    q = parse_text(text)[0]
    assert q.call == "K6ZZ"
    assert q.rst_sent is None
    assert q.rst_rcvd is None
    assert q.raw["cabrillo_transmitter"] == "1"


def test_serial_001_is_not_read_as_rst():
    """EU-SPRINT: „001" ist eine Seriennummer, kein Rapport (R=0 gibt es nicht)."""
    text = _log("QSO: 14000 CW 2001-11-24 2209 I2UIY 001 PAOLO UR4PWC 1 ANDY")
    q = parse_text(text)[0]
    assert q.call == "UR4PWC"
    assert q.rst_sent is None
    assert q.rst_rcvd is None


def test_arrl_ss_five_fields_without_rst():
    text = _log("QSO:  3799 CW 2001-11-24 2209 N5KO 3 B 74 STX K9ZO 2 A 69 IL")
    q = parse_text(text)[0]
    assert q.call == "K9ZO"
    assert q.rst_sent is None
    assert q.raw["cabrillo_exch_rcvd"] == "2 A 69 IL"


def test_vhf_grid_exchange():
    """Der Locator der GEGENstation ist der rechte, nicht der eigene."""
    text = _log("QSO: 144 PH 2003-08-03 0224 AA1ZZZ FN31 W2AJM FN21")
    q = parse_text(text)[0]
    assert q.call == "W2AJM"
    assert q.gridsquare == "FN21"
    assert q.freq == "144"
    assert q.band == "2m"


def test_ww_digi_grid_with_transmitter_id():
    text = _log("QSO: 14000 DG 2019-08-31 1200 HC8N EI00 W1AW FN32 0")
    q = parse_text(text)[0]
    assert q.call == "W1AW"
    assert q.gridsquare == "FN32"
    assert q.mode == "DIGI"
    assert q.raw["cabrillo_mode"] == "DG"


def test_iota_four_fields_with_transmitter_id():
    text = _log("QSO: 14000 PH 2003-07-26 1200 HC8N 59 0901 SA-004 G3XTT 59 0031 EU-005 0")
    q = parse_text(text)[0]
    assert q.call == "G3XTT"
    assert q.rst_sent == "59"
    assert q.rst_rcvd == "59"
    assert q.raw["cabrillo_exch_rcvd"] == "59 0031 EU-005"


def test_portable_suffix_in_line():
    """Der Kopf nennt „DL0MT", die Zeile „DL0MT/P" — trotzdem korrekt zerlegt."""
    text = _log("QSO: 14000 CW 2001-11-24 2209 DL0MT/P 599 14 XT2DX 599 35")
    q = parse_text(text)[0]
    assert q.call == "XT2DX"


def test_tabs_and_multiple_spaces():
    text = _log("QSO:\t14000\tCW   2001-11-24\t2209  DL0MT  599  14   XT2DX  599  35")
    q = parse_text(text)[0]
    assert q.call == "XT2DX"
    assert q.rst_sent == "599"


def test_six_character_grid_is_not_mistaken_for_a_call():
    """„FN12FR" erfüllt das Rufzeichen-Muster — der Locator-Ausschluss fängt das."""
    text = _log("QSO: 432 PH 2003-08-03 0224 NJ2L FN12fr K2AN FN02")
    q = parse_text(text)[0]
    assert q.call == "K2AN"
    assert q.gridsquare == "FN02"


# --------------------------------------------------------- Normalisierung


def test_date_and_time_normalized_for_the_builder():
    text = _log("QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35")
    q = parse_text(text)[0]
    assert q.qso_date == "20011124"  # nicht "2001-11-24"
    assert q.time_on == "2209"


def test_freq_normalization():
    assert _norm_freq("3799") == "3.799"  # kHz
    assert _norm_freq("14000") == "14"
    assert _norm_freq("50313") == "50.313"
    assert _norm_freq("144174") == "144.174"
    assert _norm_freq("50") == "50"  # Bandbezeichner
    assert _norm_freq("144") == "144"
    assert _norm_freq("432") == "432"
    assert _norm_freq("1.2G") == "1240"
    assert _norm_freq("2.3G") == "2300"
    assert _norm_freq("10G") == "10000"
    assert _norm_freq("1.2") == "1240"  # Kurzform aus dem ARRL-UHF-Template
    assert _norm_freq("LIGHT") is None  # hat keine Frequenz
    assert _norm_freq("Quatsch") is None
    assert _norm_freq("") is None


def test_band_from_freq():
    assert _band("14") == "20m"
    assert _band("3.799") == "80m"
    assert _band("50") == "6m"
    assert _band("144.174") == "2m"
    assert _band("1240") == "23cm"
    assert _band("999") is None  # in keinem Amateurband
    assert _band(None) is None


def test_mode_mapping():
    for code, expected in (("CW", "CW"), ("PH", "SSB"), ("FM", "FM"), ("RY", "RTTY")):
        text = _log(f"QSO: 14000 {code} 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35")
        q = parse_text(text)[0]
        assert q.mode == expected
        assert q.raw["cabrillo_mode"] == code


def test_unknown_mode_is_passed_through():
    text = _log("QSO: 14000 XX 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35")
    q = parse_text(text)[0]
    assert q.mode == "XX"


def test_unknown_freq_keeps_the_raw_token():
    text = _log("QSO: LIGHT PH 2003-08-03 0224 AA1ZZZ FN31 W2AJM FN21")
    q = parse_text(text)[0]
    assert q.freq is None
    assert q.band is None
    assert q.raw["cabrillo_freq"] == "LIGHT"


def test_builds_a_card_row():
    """Die eigentliche Anforderung: aus einem Cabrillo-QSO wird eine Kartenzeile."""
    text = _log("QSO: 14025 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35")
    cards = build_cards(parse_text(text), AppConfig())
    assert len(cards) == 1
    row = cards[0].rows[0]
    assert (row.date_d, row.date_m, row.date_y) == ("24", "11", "01")
    assert row.utc == "22:09"
    assert row.freq_mhz == "14.025"
    assert row.mode == "CW"
    assert row.rst_sent == "599"


# ------------------------------------------------------------ Robustheit


def test_x_qso_is_imported_and_marked():
    text = _log(
        "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35",
        "X-QSO: 14000 CW 2001-11-24 2210 DL0MT 599 14 DL2ND 599 14",
    )
    qsos = parse_text(text)
    assert [q.call for q in qsos] == ["XT2DX", "DL2ND"]
    assert "cabrillo_x_qso" not in qsos[0].raw
    assert qsos[1].raw["cabrillo_x_qso"] == "Y"


def test_broken_line_is_skipped():
    text = _log(
        "QSO: 14000 CW",
        "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35",
    )
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].call == "XT2DX"


def test_line_without_date_is_skipped():
    text = _log("QSO: 14000 CW 24.11.01 2209 DL0MT 599 14 XT2DX 599 35")
    assert parse_text(text) == []


def test_header_only_returns_empty_list():
    """Der Parser wirft nie — der Dispatcher meldet „ohne QSOs"."""
    assert parse_text("START-OF-LOG: 3.0\nCALLSIGN: DL0MT\nEND-OF-LOG:\n") == []


def test_crlf_line_endings():
    text = (
        "START-OF-LOG: 3.0\r\n"
        "CALLSIGN: DL0MT\r\n"
        "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35\r\n"
        "END-OF-LOG:"
    )
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].call == "XT2DX"


def test_routing_fields_stay_empty():
    """Cabrillo kennt keine Versandart: Via und Manager kommen aus dem Lookup."""
    text = _log("QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35")
    q = parse_text(text)[0]
    assert q.qsl_sent_via is None
    assert q.qsl_via is None


def test_multiple_qsos_same_call():
    text = _log(
        "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35",
        "QSO:  7000 CW 2001-11-25 0815 DL0MT 599 14 XT2DX 599 35",
    )
    qsos = parse_text(text)
    assert [q.call for q in qsos] == ["XT2DX", "XT2DX"]
    assert [q.band for q in qsos] == ["20m", "40m"]


def test_the_split_does_not_depend_on_the_header_callsign():
    """`CALLSIGN:` aus dem Kopf beeinflusst die Trennstelle **nicht**.

    Es stand einmal mit `+1` im Scoring von `_find_split` und wurde entfernt: das
    erste Feld jeder Seite ist per Invariante das Rufzeichen, unser eigenes liegt
    also immer auf `rest[0]` und damit für **jeden** Kandidaten links der
    Trennstelle. Der Term war für alle `cut` derselbe Summand und konnte das
    Maximum nie verschieben.

    Der Test hält das Ergebnis fest, damit niemand die Zeile „zur Sicherheit"
    zurückholt: dieselbe QSO-Zeile muss mit passendem, fremdem und fehlendem
    Kopf-Rufzeichen identisch zerlegt werden.
    """
    line = "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35"
    headers = (
        "START-OF-LOG: 3.0\nCALLSIGN: DL0MT\n",  # passt zur Zeile
        "START-OF-LOG: 3.0\nCALLSIGN: XX9XXX\n",  # passt nicht
        "START-OF-LOG: 3.0\n",  # gar keines
    )
    results = [parse_text(_log(line, header=h))[0] for h in headers]
    for q in results:
        assert q.call == "XT2DX"
        assert q.rst_sent == "599"
        assert q.raw["cabrillo_exch_sent"] == "599 14"
        assert q.raw["cabrillo_exch_rcvd"] == "599 35"


def test_shortwave_frequency_in_mhz_is_accepted():
    """Manche Logger schreiben Kurzwelle schon in MHz statt in kHz.

    Die Regel steht **nach** der Bandbezeichner-Tabelle: „10" ist dort 10 GHz
    (ARRL-UHF-Template), „14.025" dagegen kann nur 20 m sein.
    """
    assert _norm_freq("14.025") == "14.025"
    assert _norm_freq("1.83") == "1.83"
    assert _norm_freq("10") == "10000"  # Bandbezeichner, nicht 10 MHz
    assert _norm_freq("0.5") is None  # unterhalb aller Amateurbänder
    assert _band(_norm_freq("14.025")) == "20m"
