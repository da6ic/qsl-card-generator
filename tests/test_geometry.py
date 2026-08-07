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


# --- Bogendruck: vier A6-Karten auf einem A4-Bogen ------------------------


def _sheet(top=0.0, bottom=0.0, left=0.0, right=0.0, enabled=True) -> AppConfig:
    config = _config(top, bottom, left, right, enabled)
    config.generation.sheet_mode = g.SHEET_MODE_A4_4UP
    return config


def test_a4_holds_exactly_four_a6_cards():
    """Die Rechnung hinter dem Feature: 2×2 A6 quer = 296 × 210 mm ≈ A4 quer."""
    assert (g.SHEET_W, g.SHEET_H) == (g.mm(297), g.mm(210))
    assert g.CARDS_PER_SHEET == 4
    assert g.BLOCK_W == pytest.approx(2 * g.PAGE_W)
    assert g.BLOCK_H == pytest.approx(2 * g.PAGE_H)
    assert g.BLOCK_W <= g.SHEET_W
    assert g.BLOCK_H <= g.SHEET_H


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("single", "single"),
        ("a4_4up", "a4_4up"),
        ("", "single"),  # alte/leere Config
        (None, "single"),  # YAML kann alles enthalten -> nie fatal
        ("4up", "single"),  # Tippfehler fällt auf den Default zurück
    ],
)
def test_normalize_sheet_mode(value, expected):
    assert g.normalize_sheet_mode(value) == expected


def test_sheet_mode_is_off_by_default():
    assert not g.is_sheet_mode(AppConfig())
    assert g.is_sheet_mode(_sheet())


def test_sheet_cells_tile_the_whole_sheet_in_reading_order():
    """Das Raster hängt an nichts: vier Zellen à 148,5 × 105 mm kacheln A4 quer
    lückenlos — ein Viertel von A4 ist das echte ISO-A6-Maß."""
    layout = g.sheet_layout(_sheet(top=5, bottom=5, left=5, right=5))
    assert layout.cell_w == pytest.approx(g.mm(148.5))
    assert layout.cell_h == pytest.approx(g.mm(105))
    # oben-links, oben-rechts, unten-links, unten-rechts (ReportLab: y von unten)
    assert layout.cells == (
        (0.0, layout.cell_h),
        (layout.cell_w, layout.cell_h),
        (0.0, 0.0),
        (layout.cell_w, 0.0),
    )
    assert layout.cut_x == pytest.approx(g.SHEET_W / 2)
    assert layout.cut_y == pytest.approx(g.SHEET_H / 2)


def _drawn_boxes(config: AppConfig) -> list[tuple[float, float, float, float]]:
    """Die vier bedruckten Flächen auf dem Bogen als (x0, y0, x1, y1)."""
    layout = g.sheet_layout(config)
    page = g.page_layout(config)
    w, h = page.page_w * page.scale, page.page_h * page.scale
    return [(x + page.dx, y + page.dy, x + page.dx + w, y + page.dy + h) for x, y in layout.cells]


@pytest.mark.parametrize(
    ("top", "bottom", "left", "right"),
    [(5, 5, 5, 5), (3, 8, 3, 3), (0, 6, 2, 9), (15, 15, 15, 15)],
)
def test_sheet_gives_every_card_the_same_margin_on_all_four_sides(top, bottom, left, right):
    """Der Kern der Korrektur: der Rand steckt in **jeder** Zelle, nicht einmal um
    den Bogen. Nach dem Schnitt auf der Zellengrenze hat jede der vier Karten
    denselben Rand ringsum — sonst säße ihr Inhalt außermittig."""
    config = _sheet(top, bottom, left, right)
    layout = g.sheet_layout(config)

    for (cell_x, cell_y), (x0, y0, x1, y1) in zip(layout.cells, _drawn_boxes(config), strict=True):
        assert x0 - cell_x == pytest.approx(g.mm(left))
        assert cell_x + layout.cell_w - x1 == pytest.approx(g.mm(right))
        assert y0 - cell_y == pytest.approx(g.mm(bottom))
        assert cell_y + layout.cell_h - y1 == pytest.approx(g.mm(top))


@pytest.mark.parametrize(
    ("top", "bottom", "left", "right"),
    [(5, 5, 5, 5), (3, 8, 3, 3), (0, 6, 2, 9)],
)
def test_sheet_gap_between_two_cards_is_twice_the_margin(top, bottom, left, right):
    """Zwischen zwei Karten liegen zwei Ränder; die Schnittkante läuft genau
    durch die Mitte dieses weißen Streifens. Nach außen bleibt der Rand einfach —
    das ist der Bereich, den der Drucker ohnehin nicht bedrucken kann."""
    config = _sheet(top, bottom, left, right)
    tl, tr, bl, _br = _drawn_boxes(config)

    assert tr[0] - tl[2] == pytest.approx(g.mm(left + right))  # senkrechte Naht
    assert tl[1] - bl[3] == pytest.approx(g.mm(top + bottom))  # waagerechte Naht
    # Nach außen: genau ein Rand.
    assert tl[0] == pytest.approx(g.mm(left))
    assert g.SHEET_H - tl[3] == pytest.approx(g.mm(top))


@pytest.mark.parametrize(
    ("top", "bottom", "left", "right"),
    [(5, 5, 5, 5), (3, 8, 3, 3), (0, 6, 2, 9), (0, 0, 0, 0)],
)
def test_sheet_card_fills_its_cell_without_distortion(top, bottom, left, right):
    """Die Karte wird in ihre Zelle eingepasst wie sonst in die Seite: ein Faktor
    für beide Achsen, der Überschuss auf der freien Achse fließt ins Layout."""
    config = _sheet(top, bottom, left, right)
    cell_w, cell_h = g.sheet_cell_size(config)
    page = g.page_layout(config)

    assert 0 < page.scale <= 1
    assert (page.dx, page.dy) == (pytest.approx(g.mm(left)), pytest.approx(g.mm(bottom)))
    assert page.page_w * page.scale == pytest.approx(cell_w - g.mm(left + right))
    assert page.page_h * page.scale == pytest.approx(cell_h - g.mm(top + bottom))
    # Eine Achse bleibt A6, die andere trägt den Überschuss.
    assert page.page_w >= g.PAGE_W and page.page_h >= g.PAGE_H
    assert page.page_w == pytest.approx(g.PAGE_W) or page.page_h == pytest.approx(g.PAGE_H)
    # Die Tabelle schließt weiterhin sauber an der rechten Kante ab.
    assert sum(page.column_widths) == pytest.approx(page.table_width)


def test_sheet_cut_guides_stay_inside_the_printable_area():
    """Die Hilfslinien laufen nur so weit, wie der Drucker kann."""
    config = _sheet(top=3, bottom=8, left=4, right=7)
    x, y, w, h = g.sheet_layout(config).printable
    assert (x, y) == (pytest.approx(g.mm(4)), pytest.approx(g.mm(8)))
    assert w == pytest.approx(g.SHEET_W - g.mm(11))
    assert h == pytest.approx(g.SHEET_H - g.mm(11))


def test_sheet_content_box_is_the_cell_minus_the_margins():
    """Der Rahmen einer Karte ist im Bogen ihre Zelle, abzüglich derselben
    Ränder wie beim Einzeldruck — nur die Seitengröße wechselt."""
    config = _sheet(top=6, bottom=6, left=6, right=6)
    cell_w, cell_h = g.sheet_cell_size(config)

    assert g.print_margins(config) == pytest.approx((g.mm(6),) * 4)
    x, y, w, h = g.content_box(config)
    assert (x, y) == (pytest.approx(g.mm(6)), pytest.approx(g.mm(6)))
    assert w == pytest.approx(cell_w - g.mm(12))
    assert h == pytest.approx(cell_h - g.mm(12))


def test_sheet_grid_does_not_move_with_the_margin():
    """Das 2×2-Raster hängt nicht am Druckrand: die Schnittkanten liegen immer
    auf der Blattmitte, egal wie groß der Rand ist."""
    for margin in (0, 5, 15):
        layout = g.sheet_layout(_sheet(margin, margin, margin, margin))
        assert layout.cell_w == pytest.approx(g.SHEET_W / 2)
        assert layout.cell_h == pytest.approx(g.SHEET_H / 2)
        assert (layout.cut_x, layout.cut_y) == (
            pytest.approx(g.SHEET_W / 2),
            pytest.approx(g.SHEET_H / 2),
        )


def test_single_mode_card_margins_are_untouched():
    """Regressionsschutz: ohne Bogenmodus wirkt der Rand weiter auf die Karte."""
    config = _config(top=6, bottom=6, left=6, right=6)
    assert g.print_margins(config) != (0.0, 0.0, 0.0, 0.0)
    assert g.page_layout(config).scale < 1
    assert g.content_box(config)[2] == pytest.approx(g.PAGE_W - g.mm(12))
