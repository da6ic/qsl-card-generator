"""Tests für die Formaterkennung und den Dispatcher (`qslcards.logbook`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from qslcards.logbook import LogFormatError, detect_format, parse_file, parse_text
from qslcards.logbook import adif as adif_parser

SAMPLE_LOG = Path(__file__).resolve().parent.parent / "Log.adi"

ADIF = "<CALL:5>DL2ND<QSO_DATE:8>20260719<TIME_ON:4>1508<EOR>"
ADIF_WITH_HEADER = "Erzeugt von Hand\n<ADIF_VER:5>3.1.0<EOH>\n" + ADIF
CABRILLO = (
    "START-OF-LOG: 3.0\n"
    "CALLSIGN: DL0MT\n"
    "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35\n"
    "END-OF-LOG:\n"
)
CABRILLO_BARE = "QSO: 14000 CW 2001-11-24 2209 DL0MT 599 14 XT2DX 599 35\n"


# ------------------------------------------------------- detect_format


def test_detects_adif_with_and_without_header():
    assert detect_format(ADIF) == "adif"
    assert detect_format(ADIF_WITH_HEADER) == "adif"


def test_detects_cabrillo_with_and_without_start_of_log():
    assert detect_format(CABRILLO) == "cabrillo"
    assert detect_format(CABRILLO_BARE) == "cabrillo"


def test_detects_nothing_in_foreign_text():
    assert detect_format("Hallo Welt\nnichts davon ist ein Logbuch\n") is None
    assert detect_format("") is None


def test_adif_comment_containing_qso_colon_stays_adif():
    """Ein ADIF-Kommentar darf „QSO:" enthalten, ohne Cabrillo zu werden."""
    text = "<CALL:5>DL2ND<COMMENT:11>QSO: schoen<EOR>"
    assert detect_format(text) == "adif"


# ----------------------------------------------------------- parse_text


def test_parses_adif_and_cabrillo():
    assert [q.call for q in parse_text(ADIF)] == ["DL2ND"]
    assert [q.call for q in parse_text(CABRILLO)] == ["XT2DX"]


def test_foreign_text_raises_with_both_formats_named():
    with pytest.raises(LogFormatError) as excinfo:
        parse_text("Das hier ist eine Einkaufsliste.\n")
    message = str(excinfo.value)
    assert "ADIF" in message and "Cabrillo" in message


def test_cabrillo_without_qsos_raises():
    with pytest.raises(LogFormatError) as excinfo:
        parse_text("START-OF-LOG: 3.0\nCALLSIGN: DL0MT\nEND-OF-LOG:\n")
    assert "Cabrillo" in str(excinfo.value)


def test_adif_without_records_raises():
    with pytest.raises(LogFormatError) as excinfo:
        parse_text("<ADIF_VER:5>3.1.0<EOH>\n")
    assert "ADIF" in str(excinfo.value)


# ----------------------------------------------------------- parse_file


def test_parse_file_matches_the_adif_parser():
    """Regressionsschutz für den Umbau: der Dispatcher ändert nichts am Ergebnis."""
    expected = adif_parser.parse_file(SAMPLE_LOG)
    assert parse_file(SAMPLE_LOG) == expected


def test_missing_file_raises_oserror_not_logformaterror(tmp_path):
    """Die GUI unterscheidet beide Fälle — der Unterschied muss echt sein."""
    with pytest.raises(OSError):
        parse_file(tmp_path / "gibtsnicht.adi")


def test_parse_file_reads_cabrillo(tmp_path):
    path = tmp_path / "contest.cbr"
    path.write_text(CABRILLO, encoding="utf-8")
    assert [q.call for q in parse_file(path)] == ["XT2DX"]
