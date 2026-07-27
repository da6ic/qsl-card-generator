"""Tests für pdf.geometry (CARD_LAYOUT.md §1 und §3)."""

from __future__ import annotations

import pytest

from qslcards.pdf import geometry as g

# --- mm-Umrechnung --------------------------------------------------------


def test_mm_conversion():
    assert g.MM == pytest.approx(72 / 25.4)
    assert g.mm(25.4) == pytest.approx(72.0)  # 1 Zoll = 72 pt
    assert g.mm(0) == 0
    assert g.mm(10) == pytest.approx(28.3464567)


def test_page_size_a6_landscape():
    assert g.PAGE_W == pytest.approx(g.mm(148))
    assert g.PAGE_H == pytest.approx(g.mm(105))
    assert g.PAGE_W > g.PAGE_H  # Querformat
    assert g.MARGIN == pytest.approx(g.mm(3))


# --- Alle erwarteten Konstanten sind definiert ---------------------------

REQUIRED_CONSTANTS = [
    "MM",
    "PAGE_W",
    "PAGE_H",
    "MARGIN",
    "LINE_WIDTH",
    "FONT_REGULAR",
    "FONT_BOLD",
    "SIZE_CALLSIGN",
    "SIZE_ADDRESS",
    "SIZE_LABEL",
    "SIZE_CALL_BOX",
    "SIZE_VIA",
    "SIZE_STATION",
    "SIZE_CHECK",
    "SIZE_TABLE_HEAD",
    "SIZE_TABLE_CELL",
    "SIZE_FOOTER",
    "SENDER_X",
    "CALLSIGN_YT",
    "ADDR_Z1_YT",
    "ADDR_Z2_YT",
    "ADDR_Z3_YT",
    "ADDR_Z4_YT",
    "TO_LABEL_X",
    "TO_LABEL_YT",
    "CALL_BOX_X",
    "CALL_BOX_YT",
    "CALL_BOX_W",
    "CALL_BOX_H",
    "VIA_LABEL_X",
    "VIA_LABEL_YT",
    "VIA_BOX_X",
    "VIA_BOX_YT",
    "VIA_BOX_W",
    "VIA_BOX_H",
    "CONFIRM_MARK_X",
    "CONFIRM_MARK_YT",
    "STATION_LABEL_X",
    "STATION_VALUE_X",
    "STATION_Z1_YT",
    "STATION_Z2_YT",
    "STATION_Z3_YT",
    "STATION_Z4_YT",
    "QSL_MARK_X",
    "QSL_MARK_YT",
    "TABLE_X0",
    "TABLE_X1",
    "TABLE_WIDTH",
    "TABLE_YT_TOP",
    "TABLE_YT_BOTTOM",
    "HEAD_H",
    "MAX_ROWS",
    "ROW_H",
    "COL_DATE_W",
    "COL_UTC_W",
    "COL_FREQ_W",
    "COL_2WAY_W",
    "COL_RST_W",
    "COLUMN_WIDTHS",
    "SUB_DATE_W",
    "SUB_RST_W",
    "REMARKS_LABEL_X",
    "REMARKS_LABEL_YT",
    "REMARKS_BOX_X",
    "REMARKS_BOX_YT",
    "REMARKS_BOX_W",
    "REMARKS_BOX_H",
    "FOOTER_TEXT_X",
    "FOOTER_TEXT_YT",
]


@pytest.mark.parametrize("name", REQUIRED_CONSTANTS)
def test_constant_defined(name):
    assert hasattr(g, name), f"Konstante {name} fehlt in geometry.py"


# --- Tabellenspalten summieren auf die Tabellenbreite ---------------------


def test_columns_sum_to_table_width():
    assert sum(g.COLUMN_WIDTHS) == pytest.approx(g.TABLE_WIDTH)


def test_table_width_matches_edges():
    assert g.TABLE_WIDTH == pytest.approx(g.TABLE_X1 - g.TABLE_X0)


def test_date_and_rst_subcolumns_sum():
    assert 3 * g.SUB_DATE_W == pytest.approx(g.COL_DATE_W)  # D+M+Y
    assert 3 * g.SUB_RST_W == pytest.approx(g.COL_RST_W)  # R+S+T


def test_row_height_positive_and_fits():
    assert g.ROW_H > 0
    # Kopfzeile + MAX_ROWS Datenzeilen füllen die Tabellenhöhe genau aus
    total = g.HEAD_H + g.MAX_ROWS * g.ROW_H
    assert total == pytest.approx(g.TABLE_YT_BOTTOM - g.TABLE_YT_TOP)
    assert g.MAX_ROWS == 1


# --- Alle Positionen liegen im Blattbereich -------------------------------

X_POSITIONS = [
    "SENDER_X",
    "TO_LABEL_X",
    "CALL_BOX_X",
    "VIA_LABEL_X",
    "VIA_BOX_X",
    "CONFIRM_MARK_X",
    "STATION_LABEL_X",
    "STATION_VALUE_X",
    "QSL_MARK_X",
    "TABLE_X0",
    "TABLE_X1",
    "REMARKS_LABEL_X",
    "REMARKS_BOX_X",
    "FOOTER_TEXT_X",
]

YT_POSITIONS = [
    "CALLSIGN_YT",
    "ADDR_Z1_YT",
    "ADDR_Z2_YT",
    "ADDR_Z3_YT",
    "ADDR_Z4_YT",
    "TO_LABEL_YT",
    "CALL_BOX_YT",
    "VIA_LABEL_YT",
    "VIA_BOX_YT",
    "CONFIRM_MARK_YT",
    "STATION_Z1_YT",
    "STATION_Z2_YT",
    "STATION_Z3_YT",
    "STATION_Z4_YT",
    "QSL_MARK_YT",
    "TABLE_YT_TOP",
    "TABLE_YT_BOTTOM",
    "REMARKS_LABEL_YT",
    "REMARKS_BOX_YT",
    "FOOTER_TEXT_YT",
]


@pytest.mark.parametrize("name", X_POSITIONS)
def test_x_positions_within_sheet(name):
    x = getattr(g, name)
    assert 0 <= x <= g.PAGE_W, f"{name}={x} liegt außerhalb 0..{g.PAGE_W}"


@pytest.mark.parametrize("name", YT_POSITIONS)
def test_yt_positions_within_sheet(name):
    yt = getattr(g, name)
    assert 0 <= yt <= g.PAGE_H, f"{name}={yt} liegt außerhalb 0..{g.PAGE_H}"


def test_boxes_stay_within_sheet():
    # Rechte Kanten der Boxen dürfen den rechten Rand nicht überschreiten.
    assert g.CALL_BOX_X + g.CALL_BOX_W <= g.PAGE_W
    assert g.VIA_BOX_X + g.VIA_BOX_W <= g.PAGE_W
    assert g.REMARKS_BOX_X + g.REMARKS_BOX_W <= g.PAGE_W
    assert g.TABLE_X0 + g.TABLE_WIDTH <= g.PAGE_W
    # Untere Boxkanten (von oben gemessen) innerhalb der Seitenhöhe.
    assert g.CALL_BOX_YT + g.CALL_BOX_H <= g.PAGE_H
    assert g.REMARKS_BOX_YT + g.REMARKS_BOX_H <= g.PAGE_H


def test_fonts_registered_or_fallback():
    # Entweder DejaVuSans registriert, oder sauberer Helvetica-Fallback.
    assert g.FONT_REGULAR in ("DejaVuSans", "Helvetica")
    assert g.FONT_BOLD in ("DejaVuSans-Bold", "Helvetica-Bold")
