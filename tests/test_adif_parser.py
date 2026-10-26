"""Tests für den ADIF-Parser (Fälle aus SPECIFICATION.md §4.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from qslcards.logbook.adif import parse_file, parse_text

# Das echte Logbuch (HAMRS) liegt nur lokal: `*.adi` ist gitignored, es sind
# persönliche Daten. Tests daran überspringen sich in einer frischen Kopie — die
# Eigenheiten, um die es geht, prüfen die Fälle oben auch ohne die Datei.
SAMPLE_LOG = Path(__file__).resolve().parent.parent / "Log.adi"
requires_sample_log = pytest.mark.skipif(
    not SAMPLE_LOG.exists(), reason="Log.adi liegt nicht im Repository (persönliche Daten)"
)


def test_with_header():
    text = (
        "<ADIF_VER:5>3.1.6<PROGRAMID:5>HAMRS<EOH>\n"
        "<CALL:6>DL2SCT<QSO_DATE:8>20260719<TIME_ON:6>143825"
        "<FREQ:6>14.230<MODE:3>SSB<RST_SENT:2>59<EOR>\n"
    )
    qsos = parse_text(text)
    assert len(qsos) == 1
    q = qsos[0]
    assert q.call == "DL2SCT"
    assert q.qso_date == "20260719"
    assert q.time_on == "143825"
    assert q.freq == "14.230"
    assert q.mode == "SSB"
    assert q.rst_sent == "59"
    # Header-Felder dürfen nicht im Record landen
    assert "adif_ver" not in q.raw
    assert "programid" not in q.raw


def test_without_header():
    text = "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].call == "DL2ND"
    assert qsos[0].time_on == "1508"


def test_mixed_case_field_names():
    text = "<Call:5>DL2ND<Qso_Date:8>20260719<TIME_on:4>1508<eor>"
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].call == "DL2ND"
    assert qsos[0].qso_date == "20260719"
    assert qsos[0].time_on == "1508"


def test_type_suffix():
    text = "<CALL:5>DL2ND<freq:6:N>14.074<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].freq == "14.074"


def test_newline_inside_value():
    # Kommentar mit Zeilenumbruch: Länge (13 Bytes) ist maßgeblich, nicht das \n
    comment = "line1\nline2py"  # 13 Bytes
    assert len(comment.encode("utf-8")) == 13
    text = f"<CALL:5>DL2ND<COMMENT:13>{comment}<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].raw["comment"] == comment
    assert qsos[0].qso_date == "20260719"


def test_missing_final_eor():
    text = (
        "<CALL:6>DL2SCT<QSO_DATE:8>20260719<TIME_ON:4>1438<EOR>"
        "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508"  # kein abschließendes <EOR>
    )
    qsos = parse_text(text)
    assert len(qsos) == 2
    assert qsos[1].call == "DL2ND"


def test_record_without_call_skipped():
    text = (
        "<QSO_DATE:8>20260719<TIME_ON:4>1438<EOR>"  # kein CALL -> übersprungen
        "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
    )
    qsos = parse_text(text)
    assert len(qsos) == 1
    assert qsos[0].call == "DL2ND"


def test_lowercase_call_is_uppercased():
    """Rufzeichen kommen großgeschrieben aus dem Parser (wie bei Cabrillo).

    Sonst stünde die Kleinschreibung auf der Karte und „dl2nd" wäre im Modus
    „pro Station" eine andere Station als „DL2ND". Der Rohwert bleibt in `raw`.
    """
    text = "<CALL:5>dl2nd<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
    qsos = parse_text(text)
    assert qsos[0].call == "DL2ND"
    assert qsos[0].raw["call"] == "dl2nd"


def test_mixed_case_calls_are_one_station():
    text = (
        "<CALL:5>dl2nd<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
        "<CALL:5>DL2ND<QSO_DATE:8>20260720<TIME_ON:4>0900<EOR>"
    )
    assert {q.call for q in parse_text(text)} == {"DL2ND"}


def test_multiple_qsos_same_call():
    text = (
        "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
        "<CALL:5>DL2ND<QSO_DATE:8>20260720<TIME_ON:4>0900<EOR>"
    )
    qsos = parse_text(text)
    assert len(qsos) == 2
    assert {q.call for q in qsos} == {"DL2ND"}
    assert [q.qso_date for q in qsos] == ["20260719", "20260720"]


def test_qsl_sent_via_raw():
    # `qsl_sent_via` ist nur informativ und wird roh (gestrippt) übernommen; die
    # Versandart (Via) kommt aus dem Lookup, nicht aus dem Log (SPECIFICATION §6).
    text = (
        "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508<QSL_SENT_VIA:1>d<EOR>"
        "<CALL:5>DL2ME<QSO_DATE:8>20260719<TIME_ON:4>1509<QSL_SENT_VIA:1>X<EOR>"
        "<CALL:5>DL2XX<QSO_DATE:8>20260719<TIME_ON:4>1510<EOR>"
    )
    qsos = parse_text(text)
    assert qsos[0].qsl_sent_via == "d"  # Rohwert, keine Normalisierung mehr
    assert qsos[1].qsl_sent_via == "X"  # beliebiger Rohwert bleibt erhalten
    assert qsos[2].qsl_sent_via is None  # Feld fehlt -> None


def test_utf8_umlaut_value():
    name = "Axel Tüner"  # ü = 2 Bytes in UTF-8
    length = len(name.encode("utf-8"))
    text = f"<CALL:5>DL2ND<NAME:{length}>{name}<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
    qsos = parse_text(text)
    assert qsos[0].name == name


def test_recipient_fields_mapped():
    text = (
        "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508"
        "<NAME:10>Uwe Czaika<QTH:11>ST. EGIDIEN<COUNTRY:7>GERMANY"
        "<GRIDSQUARE:6>JO60hs<EOR>"
    )
    q = parse_text(text)[0]
    assert q.name == "Uwe Czaika"
    assert q.qth == "ST. EGIDIEN"
    assert q.country == "GERMANY"
    assert q.gridsquare == "JO60hs"


def test_dxcc_field_mapped():
    """`DXCC` (ADIF-Gebietsnummer) wird übernommen — er gewinnt im
    Most-Wanted-Filter vor dem Lookup. Fehlt er, bleibt das Feld leer."""
    with_dxcc = parse_text("<CALL:5>JA1AA<QSO_DATE:8>20260719<TIME_ON:4>1508<DXCC:3>339<EOR>")
    without = parse_text("<CALL:5>JA1AA<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>")
    assert with_dxcc[0].dxcc == "339"
    assert without[0].dxcc is None


def test_own_station_fields_not_promoted():
    # Eigene Stationsfelder bleiben roh, werden NICHT zu QSO-Attributen.
    text = (
        "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508"
        "<OPERATOR:5>DL0MT<MY_GRIDSQUARE:6>JN48PK<STATION_CALLSIGN:5>DL0MT<EOR>"
    )
    q = parse_text(text)[0]
    assert not hasattr(q, "operator")
    assert not hasattr(q, "my_gridsquare")
    # nur roh verfügbar
    assert q.raw["operator"] == "DL0MT"
    assert q.raw["my_gridsquare"] == "JN48PK"


def test_overlong_length_does_not_swallow_next_tag():
    # HAMRS-Realfall: `<RST_SENT:3>0` deklariert Länge 3, der Wert "0" ist aber
    # nur 1 Zeichen -> der Überlauf würde Zeilenumbruch + das '<' des nächsten
    # Tags mitlesen ("0\n<") und `RST_RCVD` verschlucken. Der Parser muss den
    # Wert am '<' abschneiden und das Folgefeld korrekt lesen.
    text = "<CALL:6>PA3BRB<MODE:3>FT8<RST_SENT:3>0\n<RST_RCVD:3>0\n<EOR>"
    q = parse_text(text)[0]
    assert q.rst_sent == "0"  # kein '<' / Zeilenumbruch mehr im Wert
    assert "<" not in q.rst_sent
    assert q.rst_rcvd == "0"  # Folgefeld nicht verschluckt


def test_overlong_length_that_counts_the_newline():
    """`<RST_SENT:3>+9\n` — der Umbruch steckt in der **deklarierten** Länge.

    Formal sind das korrekte drei Bytes, es gibt also kein `<` im Wert und der
    Wiederherstellungszweig greift gar nicht. Genau so schreibt HAMRS es, und
    genau deshalb schneidet der Tokenizer abschließenden Leerraum ab: sonst
    stünde `"+9\n"` im Datenmodell und in `raw`.
    """
    text = "<CALL:6>PA3BRB<RST_SENT:3>+9\n<RST_RCVD:3>-1\n<EOR>"
    q = parse_text(text)[0]
    assert q.rst_sent == "+9"
    assert q.rst_rcvd == "-1"


@requires_sample_log
def test_no_value_keeps_trailing_whitespace():
    """Sammelnetz am echten Logbuch: kein einziger Rohwert trägt Leerraum am Ende."""
    for qso in parse_file(SAMPLE_LOG):
        for feld, wert in qso.raw.items():
            assert wert == wert.rstrip(), f"{feld}: {wert!r}"


def test_leading_whitespace_is_part_of_the_value():
    """Nur **hinten** wird geschnitten — vorn beginnt der Wert direkt hinter `>`."""
    text = "<CALL:6>PA3BRB<COMMENT:8>  Hallo \n<EOR>"
    assert parse_text(text)[0].raw["comment"] == "  Hallo"


@requires_sample_log
def test_parse_real_sample_log():
    qsos = parse_file(SAMPLE_LOG)
    assert len(qsos) > 0
    first = qsos[0]
    assert first.call == "DL2SCT"
    assert first.rst_sent == "59"
    assert first.band == "20m"
    # jeder QSO hat ein Rufzeichen
    assert all(q.call for q in qsos)
