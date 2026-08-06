"""Tests für pdf.geometry (CARD_LAYOUT.md §1 und §3)."""

from __future__ import annotations

import pytest

from qslcards.config import AppConfig, GenerationConfig
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
    "SIZE_REMARKS",
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
    "TABLE_YT_BOTTOM_WITH_REMARKS",
    "HEAD_H",
    "MAX_ROWS",
    "MAX_ROWS_PLAIN",
    "MAX_ROWS_WITH_REMARKS",
    "ROW_H",
    "COL_DATE_W",
    "COL_UTC_W",
    "COL_FREQ_W",
    "COL_2WAY_W",
    "COL_RST_W",
    "COLUMN_WIDTHS",
    "SUB_DATE_W",
    "REMARKS_LABEL_X",
    "REMARKS_LABEL_YT",
    "REMARKS_BOX_X",
    "REMARKS_BOX_YT",
    "REMARKS_BOX_W",
    "REMARKS_BOX_H",
    "REMARKS_TEXT_PAD",
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


def test_date_subcolumns_sum():
    assert 3 * g.SUB_DATE_W == pytest.approx(g.COL_DATE_W)  # D+M+Y


def test_row_height_positive_and_fits():
    assert g.ROW_H > 0
    assert g.MAX_ROWS_WITH_REMARKS == 3
    assert g.MAX_ROWS_PLAIN == 6
    assert g.MAX_ROWS == g.MAX_ROWS_PLAIN  # absolute Obergrenze je Karte

    # Mit Remarks: Kopfzeile + weniger Datenzeilen; die Tabelle darf nicht in den
    # REMARKS-Block ragen (der Kasten braucht darunter Platz).
    with_rem = g.HEAD_H + g.MAX_ROWS_WITH_REMARKS * g.ROW_H
    assert with_rem == pytest.approx(g.TABLE_YT_BOTTOM_WITH_REMARKS - g.TABLE_YT_TOP)
    assert g.TABLE_YT_BOTTOM_WITH_REMARKS <= g.REMARKS_LABEL_YT

    # Ohne Remarks: mehr Datenzeilen; die Tabelle muss über dem Footer bleiben.
    plain = g.HEAD_H + g.MAX_ROWS_PLAIN * g.ROW_H
    assert plain == pytest.approx(g.TABLE_YT_BOTTOM - g.TABLE_YT_TOP)
    assert g.TABLE_YT_BOTTOM <= g.FOOTER_TEXT_YT


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
    "TABLE_YT_BOTTOM_WITH_REMARKS",
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


# --- Druckrand: Clamping, Rahmen und elastisches Layout -------------------


def _config(top=0.0, bottom=0.0, left=0.0, right=0.0, enabled=True) -> AppConfig:
    return AppConfig(
        generation=GenerationConfig(
            print_margin_enabled=enabled,
            print_margin_top=top,
            print_margin_bottom=bottom,
            print_margin_left=left,
            print_margin_right=right,
        )
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0.0),
        (4.5, 4.5),
        (-3, 0.0),  # negative Ränder gibt es nicht
        (999, g.PRINT_MARGIN_MAX),  # Obergrenze
        (None, 0.0),  # YAML kann alles enthalten -> nie fatal
        ("Unsinn", 0.0),
        ("4.5", 4.5),  # als Text notierte Zahl bleibt gültig
        (float("nan"), 0.0),
    ],
)
def test_clamp_print_margin(value, expected):
    assert g.clamp_print_margin(value) == pytest.approx(expected)


def test_content_box_is_full_page_without_margins():
    # Schalter aus -> voller Bogen, egal was in den Randfeldern steht.
    x, y, w, h = g.content_box(_config(top=5, bottom=5, left=5, right=5, enabled=False))
    assert (x, y) == (0.0, 0.0)
    assert (w, h) == (g.PAGE_W, g.PAGE_H)


def test_content_box_subtracts_margins():
    x, y, w, h = g.content_box(_config(top=3, bottom=8, left=4, right=6))
    assert x == pytest.approx(g.mm(4))  # links
    assert y == pytest.approx(g.mm(8))  # unten
    assert w == pytest.approx(g.PAGE_W - g.mm(10))
    assert h == pytest.approx(g.PAGE_H - g.mm(11))


def test_page_layout_without_margins_matches_constants():
    """Regressionsschutz: ohne Druckrand darf sich am Ergebnis nichts ändern."""
    page = g.page_layout(AppConfig())
    assert (page.dx, page.dy, page.scale) == (0.0, 0.0, 1.0)
    assert page.page_w == pytest.approx(g.PAGE_W)
    assert page.page_h == pytest.approx(g.PAGE_H)
    assert page.call_box_w == pytest.approx(g.CALL_BOX_W)
    assert page.via_box_w == pytest.approx(g.VIA_BOX_W)
    assert page.table_x1 == pytest.approx(g.TABLE_X1)
    assert page.table_width == pytest.approx(g.TABLE_WIDTH)
    assert page.column_widths == pytest.approx(g.COLUMN_WIDTHS)
    assert page.sub_date_w == pytest.approx(g.SUB_DATE_W)
    assert page.remarks_box_w == pytest.approx(g.REMARKS_BOX_W)
    assert page.remarks_label_yt == pytest.approx(g.REMARKS_LABEL_YT)
    assert page.remarks_box_yt == pytest.approx(g.REMARKS_BOX_YT)
    assert page.footer_text_yt == pytest.approx(g.FOOTER_TEXT_YT)


@pytest.mark.parametrize(
    ("top", "bottom", "left", "right"),
    [(3, 8, 3, 3), (4, 4, 4, 4), (3, 3, 10, 10), (0, 6, 2, 9), (15, 15, 15, 15)],
)
def test_page_layout_hits_margins_exactly(top, bottom, left, right):
    """Die gezeichnete Fläche endet exakt an den eingestellten Rändern."""
    page = g.page_layout(_config(top, bottom, left, right))
    assert page.dx == pytest.approx(g.mm(left))
    assert page.dy == pytest.approx(g.mm(bottom))
    assert page.dx + page.page_w * page.scale == pytest.approx(g.PAGE_W - g.mm(right))
    assert page.dy + page.page_h * page.scale == pytest.approx(g.PAGE_H - g.mm(top))


@pytest.mark.parametrize(
    ("top", "bottom", "left", "right"),
    [(3, 8, 3, 3), (4, 4, 4, 4), (3, 3, 10, 10), (0, 6, 2, 9)],
)
def test_page_layout_never_distorts(top, bottom, left, right):
    """Es gibt genau *einen* Faktor: die Karte wird nie gestaucht/gestreckt.

    Eine der beiden virtuellen Achsen bleibt exakt A6, die andere trägt den
    Überschuss — nur so bleibt das Seitenverhältnis erhalten."""
    page = g.page_layout(_config(top, bottom, left, right))
    assert 0 < page.scale <= 1
    assert page.page_w >= g.PAGE_W and page.page_h >= g.PAGE_H
    assert page.page_w == pytest.approx(g.PAGE_W) or page.page_h == pytest.approx(g.PAGE_H)


@pytest.mark.parametrize(
    ("top", "bottom", "left", "right"),
    [(3, 8, 3, 3), (4, 4, 4, 4), (3, 3, 10, 10), (15, 15, 15, 15)],
)
def test_page_layout_keeps_table_and_footer_consistent(top, bottom, left, right):
    """Der Überschuss fließt ins Layout: Spalten schließen an der Tabellenkante
    ab, der Fußblock behält seinen Abstand zur Unterkante."""
    page = g.page_layout(_config(top, bottom, left, right))
    assert sum(page.column_widths) == pytest.approx(page.table_width)
    assert page.table_width == pytest.approx(page.table_x1 - g.TABLE_X0)
    assert 3 * page.sub_date_w == pytest.approx(page.column_widths[0])
    assert page.remarks_box_w == pytest.approx(page.table_width)
    # Boxen bleiben rechts innerhalb der virtuellen Seite …
    assert g.CALL_BOX_X + page.call_box_w == pytest.approx(page.page_w - g.MARGIN)
    assert g.VIA_BOX_X + page.via_box_w == pytest.approx(page.page_w - g.MARGIN)
    # … und der Fuß hängt unverändert 6,5 mm über der Unterkante.
    assert page.page_h - page.footer_text_yt == pytest.approx(g.PAGE_H - g.FOOTER_TEXT_YT)
    assert page.page_h - page.remarks_box_yt == pytest.approx(g.PAGE_H - g.REMARKS_BOX_YT)
    # Die Tabelle darf weiterhin nicht in den Fußblock ragen (MAX_ROWS bleibt).
    assert g.TABLE_YT_BOTTOM_WITH_REMARKS <= page.remarks_label_yt
    assert g.TABLE_YT_BOTTOM <= page.footer_text_yt


def test_page_layout_caps_extreme_stretch():
    """Sicherheitsventil: der elastische Überschuss ist gedeckelt, der Rest wird
    zentriert (nur bei absurden Randwerten; der Rand wird dann größer)."""
    page = g.page_layout(_config(top=0, bottom=0, left=15, right=15))
    assert page.page_h <= g.PAGE_H + g.MAX_STRETCH
    # Zentriert: oben und unten bleibt gleich viel übrig.
    assert page.dy == pytest.approx((g.PAGE_H - page.page_h * page.scale) / 2)
