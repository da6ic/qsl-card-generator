"""Zeichnet die Rückseite einer QSL-Karte (docs/CARD_LAYOUT.md §2–§4).

Der Zeichencode benutzt ausschließlich benannte Konstanten aus geometry.py –
keine Layout-Zahlen hier. Positionen werden als `yt` (von oben) angegeben; die
Umrechnung in ReportLab-Koordinaten (Ursprung unten links) übernehmen die
Helfer `text`, `checkbox` und die internen `_box`/`_hline`/`_vline`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reportlab.pdfbase.pdfmetrics import getAscent, getDescent

from . import geometry as g

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas

    from qslcards.cards.models import Card, CardRow
    from qslcards.config import AppConfig

# Statische Kopftexte der Tabelle (Inhalt, kein Layout).
_HEAD_DATE = "DATE"
_HEAD_DATE_SUB = ("D", "M", "Y")
_HEAD_UTC = ("UNIVERSAL TIME", "(UTC)")
_HEAD_FREQ = ("FREQUENCY", "MHZ")
_HEAD_2WAY = ("2-WAY QSO", "IN")
_HEAD_RST = "SIGNAL REPORT"
_HEAD_RST_SUB = ("R", "S", "T")


# --------------------------------------------------------------------------- #
# Öffentliche Helfer (CARD_LAYOUT.md §4)
# --------------------------------------------------------------------------- #


def text(
    c: Canvas,
    x: float,
    yt: float,
    s: str,
    font: str,
    size: float,
    align: str = "left",
) -> None:
    """Zeichnet Text, `yt` = Abstand der Glyphen-Oberkante von oben.

    Intern: baseline = PAGE_H - yt - ascent, sodass die Textoberkante bei `yt`
    liegt (leichter mit der Vorlage von oben abzugleichen)."""
    baseline = g.PAGE_H - yt - getAscent(font, size)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, baseline, s)
    elif align == "right":
        c.drawRightString(x, baseline, s)
    else:
        c.drawString(x, baseline, s)


def checkbox(
    c: Canvas,
    x: float,
    yt: float,
    label: str,
    checked: bool = False,
    size: float = g.SIZE_CHECK,
) -> None:
    """Kleines Quadrat (Seite CHECKBOX_SIZE) mit Label rechts daneben.

    `yt` = Oberkante des Kästchens von oben. Bei `checked=True` wird ein Kreuz
    ins Kästchen gezeichnet."""
    box_bottom = g.PAGE_H - yt - g.CHECKBOX_SIZE
    c.setLineWidth(g.LINE_WIDTH)
    c.rect(x, box_bottom, g.CHECKBOX_SIZE, g.CHECKBOX_SIZE, stroke=1, fill=0)
    if checked:
        # Kreuz größer als das Kästchen: Endpunkte ragen um CROSS_OVERHANG hinaus.
        o = g.CHECKBOX_CROSS_OVERHANG
        left, right = x - o, x + g.CHECKBOX_SIZE + o
        bottom, top = box_bottom - o, box_bottom + g.CHECKBOX_SIZE + o
        c.line(left, bottom, right, top)
        c.line(left, top, right, bottom)
    # Label vertikal mittig zum Kästchen.
    _text_in_band(
        c,
        x + g.CHECKBOX_SIZE + g.CHECKBOX_GAP,
        yt,
        g.CHECKBOX_SIZE,
        label,
        g.FONT_REGULAR,
        size,
        align="left",
    )


# --------------------------------------------------------------------------- #
# Interne Zeichen-Helfer
# --------------------------------------------------------------------------- #


def _text_in_band(
    c: Canvas,
    x: float,
    yt_top: float,
    band_h: float,
    s: str,
    font: str,
    size: float,
    align: str = "center",
) -> None:
    """Text vertikal mittig in einem Band [yt_top .. yt_top+band_h] (von oben)."""
    ascent = getAscent(font, size)
    descent = getDescent(font, size)  # negativ
    center_y = g.PAGE_H - (yt_top + band_h / 2)
    baseline = center_y - (ascent + descent) / 2
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, baseline, s)
    elif align == "right":
        c.drawRightString(x, baseline, s)
    else:
        c.drawString(x, baseline, s)


def _box(c: Canvas, x: float, yt: float, w: float, h: float) -> None:
    """Rahmen mit Oberkante bei `yt` (von oben)."""
    c.setLineWidth(g.LINE_WIDTH)
    c.rect(x, g.PAGE_H - yt - h, w, h, stroke=1, fill=0)


def _hline(c: Canvas, x0: float, x1: float, yt: float) -> None:
    y = g.PAGE_H - yt
    c.line(x0, y, x1, y)


def _vline(c: Canvas, x: float, yt0: float, yt1: float) -> None:
    c.line(x, g.PAGE_H - yt0, x, g.PAGE_H - yt1)


def _split_rst(rst: str) -> tuple[str, str, str]:
    """Rapport in R/S/T zerlegen; bei 2-stelligem Rapport bleibt T leer."""
    digits = list((rst or "").strip())
    r = digits[0] if len(digits) > 0 else ""
    s = digits[1] if len(digits) > 1 else ""
    t = digits[2] if len(digits) > 2 else ""
    return r, s, t


# --------------------------------------------------------------------------- #
# Öffentliche Zeichen-Funktion
# --------------------------------------------------------------------------- #


def draw_back(c: Canvas, card: Card, config: AppConfig) -> None:
    """Zeichnet die komplette Rückseite für `card` auf das Canvas `c`."""
    c.setLineWidth(g.LINE_WIDTH)
    _draw_frame(c)
    _draw_sender(c, config)
    _draw_recipient(c, card)
    _draw_station(c, config)
    _draw_confirm(c)
    _draw_table(c, card.rows)
    _draw_footer(c, card, config)


def _draw_frame(c: Canvas) -> None:
    """Äußerer Rahmen entlang des Rands."""
    c.setLineWidth(g.LINE_WIDTH)
    c.rect(
        g.MARGIN,
        g.MARGIN,
        g.PAGE_W - 2 * g.MARGIN,
        g.PAGE_H - 2 * g.MARGIN,
        stroke=1,
        fill=0,
    )


def _draw_sender(c: Canvas, config: AppConfig) -> None:
    s = config.sender
    text(c, g.SENDER_X, g.CALLSIGN_YT, s.callsign, g.FONT_BOLD, g.SIZE_CALLSIGN)
    text(c, g.SENDER_X, g.ADDR_Z1_YT, s.name, g.FONT_REGULAR, g.SIZE_ADDRESS)
    text(c, g.SENDER_X, g.ADDR_Z2_YT, s.street, g.FONT_REGULAR, g.SIZE_ADDRESS)
    text(
        c,
        g.SENDER_X,
        g.ADDR_Z3_YT,
        f"{s.zip} {s.city}".strip(),
        g.FONT_REGULAR,
        g.SIZE_ADDRESS,
    )
    text(c, g.SENDER_X, g.ADDR_Z4_YT, s.country, g.FONT_REGULAR, g.SIZE_ADDRESS)


def _draw_recipient(c: Canvas, card: Card) -> None:
    # Label + Box + Empfänger-Rufzeichen
    text(c, g.TO_LABEL_X, g.TO_LABEL_YT, "To Amateur Radio Station:", g.FONT_REGULAR, g.SIZE_LABEL)
    _box(c, g.CALL_BOX_X, g.CALL_BOX_YT, g.CALL_BOX_W, g.CALL_BOX_H)
    _text_in_band(
        c,
        g.CALL_BOX_X + g.CALL_BOX_W / 2,
        g.CALL_BOX_YT,
        g.CALL_BOX_H,
        card.recipient_call,
        g.FONT_BOLD,
        g.SIZE_CALL_BOX,
        align="center",
    )
    # Via
    text(c, g.VIA_LABEL_X, g.VIA_LABEL_YT, "Via:", g.FONT_REGULAR, g.SIZE_LABEL)
    _box(c, g.VIA_BOX_X, g.VIA_BOX_YT, g.VIA_BOX_W, g.VIA_BOX_H)
    _text_in_band(
        c,
        g.VIA_BOX_X + g.VIA_BOX_W / 2,
        g.VIA_BOX_YT,
        g.VIA_BOX_H,
        card.via_text,
        g.FONT_REGULAR,
        g.SIZE_VIA,
        align="center",
    )
    # Portabel-Markierungen (global aus der Config über card.portable_mark)
    checkbox(c, g.PORTABLE_P_X, g.PORTABLE_YT, "/p", checked=card.portable_mark == "p")
    checkbox(c, g.PORTABLE_M_X, g.PORTABLE_YT, "/m", checked=card.portable_mark == "m")


def _draw_station(c: Canvas, config: AppConfig) -> None:
    # Stationsblock als Label/Wert-Spalten rechts neben der Adresse.
    s = config.sender
    rows = (
        ("Locator:", s.locator, g.STATION_Z1_YT),
        ("DOK:", s.dok, g.STATION_Z2_YT),
        ("WAZ:", s.waz, g.STATION_Z3_YT),
        ("ITU:", s.itu, g.STATION_Z4_YT),
    )
    for label, value, yt in rows:
        text(c, g.STATION_LABEL_X, yt, label, g.FONT_REGULAR, g.SIZE_STATION)
        text(c, g.STATION_VALUE_X, yt, value, g.FONT_REGULAR, g.SIZE_STATION)


def _draw_confirm(c: Canvas) -> None:
    # Manuelle Bestätigungs-Checkboxen (ohne Auto-Logik, standardmäßig leer).
    checkbox(c, g.CONFIRM_QSO_X, g.CONFIRM_YT, "Confirming QSO", checked=False)
    checkbox(c, g.CONFIRM_SWL_X, g.CONFIRM_YT, "Confirming SWL-Report", checked=False)


def _column_edges() -> list[float]:
    edges = [g.TABLE_X0]
    for w in g.COLUMN_WIDTHS:
        edges.append(edges[-1] + w)
    return edges


def _draw_table(c: Canvas, rows: list[CardRow]) -> None:
    c.setLineWidth(g.LINE_WIDTH)
    edges = _column_edges()
    top = g.TABLE_YT_TOP
    head_bottom = g.TABLE_YT_TOP + g.HEAD_H
    head_mid = g.TABLE_YT_TOP + g.HEAD_H / 2
    bottom = g.TABLE_YT_BOTTOM

    # Hauptspalten-Trennlinien über die volle Höhe.
    for x in edges:
        _vline(c, x, top, bottom)
    # Waagerechte Linien: oben, Kopf/Daten-Trenner, Zeilentrenner, unten.
    _hline(c, g.TABLE_X0, g.TABLE_X1, top)
    _hline(c, g.TABLE_X0, g.TABLE_X1, head_bottom)
    for i in range(1, g.MAX_ROWS):
        _hline(c, g.TABLE_X0, g.TABLE_X1, head_bottom + i * g.ROW_H)
    _hline(c, g.TABLE_X0, g.TABLE_X1, bottom)

    # Unterspalten-Trenner (DATE und SIGNAL REPORT) ab Kopf-Unterzeile.
    date_left = edges[0]
    _vline(c, date_left + g.SUB_DATE_W, head_mid, bottom)
    _vline(c, date_left + 2 * g.SUB_DATE_W, head_mid, bottom)
    rst_left = edges[4]
    _vline(c, rst_left + g.SUB_RST_W, head_mid, bottom)
    _vline(c, rst_left + 2 * g.SUB_RST_W, head_mid, bottom)

    _draw_table_header(c, edges, head_mid)
    for i, row in enumerate(rows[: g.MAX_ROWS]):
        _draw_table_row(c, edges, head_bottom + i * g.ROW_H, row)


def _col_center(edges: list[float], idx: int) -> float:
    return (edges[idx] + edges[idx + 1]) / 2


def _draw_table_header(c: Canvas, edges: list[float], head_mid: float) -> None:
    top = g.TABLE_YT_TOP
    half = g.HEAD_H / 2
    font = g.FONT_BOLD
    size = g.SIZE_TABLE_HEAD

    # Obere Kopf-Halbzeile: Hauptbezeichnungen.
    _text_in_band(c, _col_center(edges, 0), top, half, _HEAD_DATE, font, size)
    _text_in_band(c, _col_center(edges, 1), top, half, _HEAD_UTC[0], font, size)
    _text_in_band(c, _col_center(edges, 2), top, half, _HEAD_FREQ[0], font, size)
    _text_in_band(c, _col_center(edges, 3), top, half, _HEAD_2WAY[0], font, size)
    _text_in_band(c, _col_center(edges, 4), top, half, _HEAD_RST, font, size)

    # Untere Kopf-Halbzeile: Unterspalten / zweite Textzeile.
    date_left = edges[0]
    for k, lbl in enumerate(_HEAD_DATE_SUB):
        _text_in_band(c, date_left + g.SUB_DATE_W * (k + 0.5), head_mid, half, lbl, font, size)
    _text_in_band(c, _col_center(edges, 1), head_mid, half, _HEAD_UTC[1], font, size)
    _text_in_band(c, _col_center(edges, 2), head_mid, half, _HEAD_FREQ[1], font, size)
    _text_in_band(c, _col_center(edges, 3), head_mid, half, _HEAD_2WAY[1], font, size)
    rst_left = edges[4]
    for k, lbl in enumerate(_HEAD_RST_SUB):
        _text_in_band(c, rst_left + g.SUB_RST_W * (k + 0.5), head_mid, half, lbl, font, size)


def _draw_table_row(c: Canvas, edges: list[float], row_top: float, row: CardRow) -> None:
    font = g.FONT_REGULAR
    size = g.SIZE_TABLE_CELL
    h = g.ROW_H

    date_left = edges[0]
    for k, val in enumerate((row.date_d, row.date_m, row.date_y)):
        _text_in_band(c, date_left + g.SUB_DATE_W * (k + 0.5), row_top, h, val, font, size)
    _text_in_band(c, _col_center(edges, 1), row_top, h, row.utc, font, size)
    _text_in_band(c, _col_center(edges, 2), row_top, h, row.freq_mhz, font, size)
    _text_in_band(c, _col_center(edges, 3), row_top, h, row.mode, font, size)
    r, s, t = _split_rst(row.rst_sent)
    rst_left = edges[4]
    for k, val in enumerate((r, s, t)):
        _text_in_band(c, rst_left + g.SUB_RST_W * (k + 0.5), row_top, h, val, font, size)


def _draw_footer(c: Canvas, card: Card, config: AppConfig) -> None:
    text(c, g.REMARKS_LABEL_X, g.REMARKS_LABEL_YT, "REMARKS", g.FONT_REGULAR, g.SIZE_LABEL)
    _box(c, g.REMARKS_BOX_X, g.REMARKS_BOX_YT, g.REMARKS_BOX_W, g.REMARKS_BOX_H)
    text(
        c,
        g.FOOTER_TEXT_X,
        g.FOOTER_TEXT_YT,
        config.generation.static_footer,
        g.FONT_BOLD,
        g.SIZE_FOOTER,
    )
    # PSE/TNX global aus der Config über card.qsl_mark.
    checkbox(c, g.PSE_QSL_X, g.FOOTER_MARK_YT, "PSE QSL", checked=card.qsl_mark == "pse")
    checkbox(c, g.TNX_QSL_X, g.FOOTER_MARK_YT, "TNX QSL", checked=card.qsl_mark == "tnx")
