"""Zeichnet die Rückseite einer QSL-Karte (docs/CARD_LAYOUT.md §2–§4).

Der Zeichencode benutzt ausschließlich benannte Konstanten aus geometry.py –
keine Layout-Zahlen hier. Positionen werden als `yt` (von oben) angegeben; die
Umrechnung in ReportLab-Koordinaten (Ursprung unten links) übernimmt der
Helfer `text` und die internen `_box`/`_hline`/`_vline`.

Alle Helfer bekommen dafür den `PageLayout` der Seite (`geometry.page_layout`):
er liefert die virtuelle Seitenhöhe für die Y-Spiegelung und die Maße, die beim
Druckrand mitwachsen (Call-/Via-Box, Tabellenbreite, Fußblock). Ohne Druckrand
sind das exakt die Konstanten aus geometry.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reportlab.pdfbase.pdfmetrics import getAscent, getDescent

from . import geometry as g

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas

    from qslcards.cards.models import Card, CardRow
    from qslcards.config import AppConfig

    from .geometry import PageLayout

# Statische Kopftexte der Tabelle (Inhalt, kein Layout). Einzeilige Kopfzeile:
# je Spalte genau ein Label. Die DATE-Spalte hat keinen Titel mehr, nur die
# Unterlabels D/M/Y. Die Report-Spalte zeigt je Zeile einen Wert (RST wie im Log
# für Phone/CW, dB für Digimodes wie FT8).
_HEAD_DATE_SUB = ("D", "M", "Y")
_HEAD_UTC = "UTC TIME"
_HEAD_FREQ = "FREQ MHZ"
_HEAD_2WAY = "2-WAY QSO IN"
_HEAD_RST = "SIGNAL REPORT"


# --------------------------------------------------------------------------- #
# Öffentliche Helfer (CARD_LAYOUT.md §4)
# --------------------------------------------------------------------------- #


def text(
    c: Canvas,
    page: PageLayout,
    x: float,
    yt: float,
    s: str,
    font: str,
    size: float,
    align: str = "left",
) -> None:
    """Zeichnet Text, `yt` = Abstand der Glyphen-Oberkante von oben.

    Intern: baseline = page.page_h - yt - ascent, sodass die Textoberkante bei
    `yt` liegt (leichter mit der Vorlage von oben abzugleichen)."""
    baseline = page.page_h - yt - getAscent(font, size)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, baseline, s)
    elif align == "right":
        c.drawRightString(x, baseline, s)
    else:
        c.drawString(x, baseline, s)


# --------------------------------------------------------------------------- #
# Interne Zeichen-Helfer
# --------------------------------------------------------------------------- #


def _text_in_band(
    c: Canvas,
    page: PageLayout,
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
    center_y = page.page_h - (yt_top + band_h / 2)
    baseline = center_y - (ascent + descent) / 2
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, baseline, s)
    elif align == "right":
        c.drawRightString(x, baseline, s)
    else:
        c.drawString(x, baseline, s)


def _box(c: Canvas, page: PageLayout, x: float, yt: float, w: float, h: float) -> None:
    """Rahmen mit Oberkante bei `yt` (von oben)."""
    c.setLineWidth(g.LINE_WIDTH)
    c.rect(x, page.page_h - yt - h, w, h, stroke=1, fill=0)


def _hline(c: Canvas, page: PageLayout, x0: float, x1: float, yt: float) -> None:
    y = page.page_h - yt
    c.line(x0, y, x1, y)


def _vline(c: Canvas, page: PageLayout, x: float, yt0: float, yt1: float) -> None:
    c.line(x, page.page_h - yt0, x, page.page_h - yt1)


# --------------------------------------------------------------------------- #
# Öffentliche Zeichen-Funktion
# --------------------------------------------------------------------------- #


def _radio_entries(config: AppConfig) -> list[tuple[str, str]]:
    """Gefüllte Funk-Felder als (Beschriftung, Wert)-Paare in fester Reihenfolge
    (RIG/ANT/PWR); leere Felder werden übersprungen (dynamisch)."""
    s = config.sender
    pairs = (
        (g.RADIO_LABEL_RIG, s.receiver),
        (g.RADIO_LABEL_ANT, s.antenna),
        (g.RADIO_LABEL_PWR, s.power),
    )
    return [(label, v.strip()) for label, v in pairs if v and v.strip()]


def draw_back(c: Canvas, card: Card, config: AppConfig) -> None:
    """Zeichnet die komplette Rückseite für `card` auf das Canvas `c`."""
    # Druckrand (docs/CARD_LAYOUT.md §1): die Karte wird proportional in den
    # bedruckbaren Rahmen gesetzt; ohne Druckrand ist das die volle A6-Seite und
    # die Transformation ist die Identität.
    page = g.page_layout(config)

    c.saveState()
    try:
        c.translate(page.dx, page.dy)
        c.scale(page.scale, page.scale)
        c.setLineWidth(g.LINE_WIDTH)
        # Sind Funk-Werte gesetzt, wird der Funk-Block unter dem Stationsblock
        # gezeichnet; QSL-Markierung und Tabelle rücken dann nach unten.
        radio = _radio_entries(config)
        qsl_yt = g.QSL_MARK_YT_RADIO if radio else g.QSL_MARK_YT
        table_top = g.TABLE_YT_TOP_RADIO if radio else g.TABLE_YT_TOP

        _draw_sender(c, page, config, card.portable_mark)
        _draw_recipient(c, page, card)
        _draw_station(c, page, config)
        _draw_radio(c, page, radio)
        _draw_confirm(c, page, card, qsl_yt)
        _draw_table(c, page, card.rows, table_top)
        _draw_footer(c, page, card, config)
    finally:
        c.restoreState()


def _draw_radio(c: Canvas, page: PageLayout, entries: list[tuple[str, str]]) -> None:
    """Funk-Block als kleine beschriftete Tabelle (Kopfzeile RIG/ANT/PWR, Werte
    darunter). Nur befüllte Felder bekommen eine Spalte; die vorhandenen Spalten
    teilen sich die volle Breite (RADIO_TABLE_X0..X1) gleichmäßig auf. Sitzt
    linksbündig direkt unter dem Stationsblock, links der Via-Box."""
    if not entries:
        return
    n = len(entries)
    x0 = g.RADIO_TABLE_X0
    total_w = g.RADIO_TABLE_X1 - g.RADIO_TABLE_X0
    col_w = total_w / n
    top = g.RADIO_TABLE_YT_TOP
    head_bottom = top + g.RADIO_HEAD_H
    bottom = g.RADIO_TABLE_YT_BOTTOM  # bündig mit der Via-Box-Unterkante
    value_h = bottom - head_bottom  # Wertezeile füllt den Rest bis zur Unterkante

    c.setLineWidth(g.LINE_WIDTH)
    # Senkrechte Spaltentrenner (inkl. Außenkanten) über die volle Höhe.
    for k in range(n + 1):
        _vline(c, page, x0 + k * col_w, top, bottom)
    # Waagerechte Linien: oben, Kopf/Wert-Trenner, unten.
    _hline(c, page, x0, g.RADIO_TABLE_X1, top)
    _hline(c, page, x0, g.RADIO_TABLE_X1, head_bottom)
    _hline(c, page, x0, g.RADIO_TABLE_X1, bottom)

    for i, (label, value) in enumerate(entries):
        cx = x0 + (i + 0.5) * col_w
        _text_in_band(c, page, cx, top, g.RADIO_HEAD_H, label, g.FONT_BOLD, g.SIZE_RADIO_HEAD)
        _text_in_band(c, page, cx, head_bottom, value_h, value, g.FONT_REGULAR, g.SIZE_RADIO)


def _draw_sender(c: Canvas, page: PageLayout, config: AppConfig, portable_mark: str) -> None:
    s = config.sender
    callsign = s.callsign
    if portable_mark and portable_mark != "none":
        callsign = f"{callsign}/{portable_mark}"
    text(c, page, g.SENDER_X, g.CALLSIGN_YT, callsign, g.FONT_BOLD, g.SIZE_CALLSIGN)
    text(c, page, g.SENDER_X, g.ADDR_Z1_YT, s.name, g.FONT_REGULAR, g.SIZE_ADDRESS)
    text(c, page, g.SENDER_X, g.ADDR_Z2_YT, s.street, g.FONT_REGULAR, g.SIZE_ADDRESS)
    text(
        c,
        page,
        g.SENDER_X,
        g.ADDR_Z3_YT,
        f"{s.zip} {s.city}".strip(),
        g.FONT_REGULAR,
        g.SIZE_ADDRESS,
    )
    text(c, page, g.SENDER_X, g.ADDR_Z4_YT, s.country, g.FONT_REGULAR, g.SIZE_ADDRESS)


def _draw_recipient(c: Canvas, page: PageLayout, card: Card) -> None:
    # Label + Box + Empfänger-Rufzeichen. Die Boxen reichen bis zur rechten
    # Inhaltskante und wachsen daher beim Druckrand mit (page.call_box_w).
    text(
        c,
        page,
        g.TO_LABEL_X,
        g.TO_LABEL_YT,
        "To Amateur Radio Station:",
        g.FONT_REGULAR,
        g.SIZE_LABEL,
    )
    _box(c, page, g.CALL_BOX_X, g.CALL_BOX_YT, page.call_box_w, g.CALL_BOX_H)
    _text_in_band(
        c,
        page,
        g.CALL_BOX_X + page.call_box_w / 2,
        g.CALL_BOX_YT,
        g.CALL_BOX_H,
        card.recipient_call,
        g.FONT_BOLD,
        g.SIZE_CALL_BOX,
        align="center",
    )
    # Via
    text(c, page, g.VIA_LABEL_X, g.VIA_LABEL_YT, "Via:", g.FONT_REGULAR, g.SIZE_LABEL)
    _box(c, page, g.VIA_BOX_X, g.VIA_BOX_YT, page.via_box_w, g.VIA_BOX_H)
    _text_in_band(
        c,
        page,
        g.VIA_BOX_X + page.via_box_w / 2,
        g.VIA_BOX_YT,
        g.VIA_BOX_H,
        card.via_text,
        g.FONT_REGULAR,
        g.SIZE_VIA,
        align="center",
    )
    # Confirm-Markierung (global aus der Config über card.confirm_mark): nur die
    # ausgewählte Option steht hier, kein Kästchen. Position ist fest (zentriert),
    # unabhängig davon, ob/welche Portabel-Markierung gewählt ist.
    if card.confirm_mark == "qso":
        text(
            c,
            page,
            g.CONFIRM_MARK_X,
            g.CONFIRM_MARK_YT,
            "Confirming QSO",
            g.FONT_BOLD,
            g.SIZE_MARK,
            align="center",
        )
    elif card.confirm_mark == "swl":
        text(
            c,
            page,
            g.CONFIRM_MARK_X,
            g.CONFIRM_MARK_YT,
            "Confirming SWL-Report",
            g.FONT_BOLD,
            g.SIZE_MARK,
            align="center",
        )


def _draw_station(c: Canvas, page: PageLayout, config: AppConfig) -> None:
    # Stationsblock als Label/Wert-Spalten rechts neben der Adresse.
    s = config.sender
    rows = (
        ("Locator:", s.locator, g.STATION_Z1_YT),
        ("DOK:", s.dok, g.STATION_Z2_YT),
        ("CQ-Zone:", s.waz, g.STATION_Z3_YT),
        ("ITU:", s.itu, g.STATION_Z4_YT),
    )
    for label, value, yt in rows:
        text(c, page, g.STATION_LABEL_X, yt, label, g.FONT_REGULAR, g.SIZE_STATION)
        text(c, page, g.STATION_VALUE_X, yt, value, g.FONT_REGULAR, g.SIZE_STATION)


def _draw_confirm(c: Canvas, page: PageLayout, card: Card, yt: float) -> None:
    # PSE/TNX QSL (global aus der Config über card.qsl_mark): nur die
    # ausgewählte Option steht hier, kein Kästchen. `yt` rutscht nach unten,
    # wenn der Funk-Block gezeichnet wird.
    if card.qsl_mark == "pse":
        text(c, page, g.QSL_MARK_X, yt, "PSE QSL", g.FONT_BOLD, g.SIZE_MARK)
    elif card.qsl_mark == "tnx":
        text(c, page, g.QSL_MARK_X, yt, "TNX QSL", g.FONT_BOLD, g.SIZE_MARK)


def _column_edges(page: PageLayout) -> list[float]:
    edges = [g.TABLE_X0]
    for w in page.column_widths:
        edges.append(edges[-1] + w)
    return edges


def _draw_table(c: Canvas, page: PageLayout, rows: list[CardRow], top: float) -> None:
    c.setLineWidth(g.LINE_WIDTH)
    edges = _column_edges(page)
    # Dynamische Tabelle: genau so viele Datenzeilen zeichnen, wie die Karte QSOs
    # hat (mind. 1, höchstens MAX_ROWS). Die Tabellenhöhe wächst mit der Zeilenzahl.
    # `top` rutscht nach unten, wenn der Funk-Block gezeichnet wird.
    n_rows = max(1, min(len(rows), g.MAX_ROWS))
    head_bottom = top + g.HEAD_H
    bottom = head_bottom + n_rows * g.ROW_H

    # Hauptspalten-Trennlinien über die volle Höhe.
    for x in edges:
        _vline(c, page, x, top, bottom)
    # Waagerechte Linien: oben, Kopf/Daten-Trenner, Zeilentrenner, unten.
    _hline(c, page, g.TABLE_X0, page.table_x1, top)
    _hline(c, page, g.TABLE_X0, page.table_x1, head_bottom)
    for i in range(1, n_rows):
        _hline(c, page, g.TABLE_X0, page.table_x1, head_bottom + i * g.ROW_H)
    _hline(c, page, g.TABLE_X0, page.table_x1, bottom)

    # Unterspalten-Trenner nur für DATE (D/M/Y), über die volle Höhe inkl. der
    # einzeiligen Kopfzeile (D/M/Y ist dort die Beschriftung). Die SIGNAL-REPORT-
    # Spalte hat keine Unterspalten (ein Wert je Zeile).
    date_left = edges[0]
    _vline(c, page, date_left + page.sub_date_w, top, bottom)
    _vline(c, page, date_left + 2 * page.sub_date_w, top, bottom)

    _draw_table_header(c, page, edges, top)
    for i, row in enumerate(rows[: g.MAX_ROWS]):
        _draw_table_row(c, page, edges, head_bottom + i * g.ROW_H, row)


def _col_center(edges: list[float], idx: int) -> float:
    return (edges[idx] + edges[idx + 1]) / 2


def _draw_table_header(c: Canvas, page: PageLayout, edges: list[float], top: float) -> None:
    # Einzeilige Kopfzeile: je Spalte ein Label, vertikal mittig in der Kopfhöhe.
    # DATE-Spalte trägt die Unterlabels D/M/Y (kein DATE-Titel mehr).
    h = g.HEAD_H
    font = g.FONT_BOLD
    size = g.SIZE_TABLE_HEAD

    date_left = edges[0]
    for k, lbl in enumerate(_HEAD_DATE_SUB):
        _text_in_band(c, page, date_left + page.sub_date_w * (k + 0.5), top, h, lbl, font, size)
    _text_in_band(c, page, _col_center(edges, 1), top, h, _HEAD_UTC, font, size)
    _text_in_band(c, page, _col_center(edges, 2), top, h, _HEAD_FREQ, font, size)
    _text_in_band(c, page, _col_center(edges, 3), top, h, _HEAD_2WAY, font, size)
    _text_in_band(c, page, _col_center(edges, 4), top, h, _HEAD_RST, font, size)


def _draw_table_row(
    c: Canvas, page: PageLayout, edges: list[float], row_top: float, row: CardRow
) -> None:
    font = g.FONT_REGULAR
    size = g.SIZE_TABLE_CELL
    h = g.ROW_H

    date_left = edges[0]
    for k, val in enumerate((row.date_d, row.date_m, row.date_y)):
        _text_in_band(c, page, date_left + page.sub_date_w * (k + 0.5), row_top, h, val, font, size)
    _text_in_band(c, page, _col_center(edges, 1), row_top, h, row.utc, font, size)
    _text_in_band(c, page, _col_center(edges, 2), row_top, h, row.freq_mhz, font, size)
    _text_in_band(c, page, _col_center(edges, 3), row_top, h, row.mode, font, size)
    # Report als ein Wert: RST wie im Log (Phone/CW) bzw. dB (Digimodes wie FT8).
    _text_in_band(
        c, page, _col_center(edges, 4), row_top, h, (row.rst_sent or "").strip(), font, size
    )


def _draw_footer(c: Canvas, page: PageLayout, card: Card, config: AppConfig) -> None:
    # REMARKS **dynamisch**: Label + Kasten + Text nur zeichnen, wenn die Karte
    # einen Remarks-Text hat. Ohne Remarks bleibt der Platz frei (der Builder gibt
    # solchen Karten mehr QSO-Zeilen, siehe geometry.MAX_ROWS_*). Der Footer-Text
    # (static_footer) steht unabhängig davon immer unten.
    # Der ganze Fußblock ist an der Unterkante verankert (page.*_yt), damit er
    # beim Druckrand mit nach unten wandert statt an der Tabelle zu kleben.
    remarks = (card.remarks or "").strip()
    if remarks:
        text(
            c,
            page,
            g.REMARKS_LABEL_X,
            page.remarks_label_yt,
            "REMARKS",
            g.FONT_REGULAR,
            g.SIZE_LABEL,
        )
        _box(c, page, g.REMARKS_BOX_X, page.remarks_box_yt, page.remarks_box_w, g.REMARKS_BOX_H)
        _text_in_band(
            c,
            page,
            g.REMARKS_BOX_X + g.REMARKS_TEXT_PAD,
            page.remarks_box_yt,
            g.REMARKS_BOX_H,
            remarks,
            g.FONT_REGULAR,
            g.SIZE_REMARKS,
            align="left",
        )
    text(
        c,
        page,
        g.FOOTER_TEXT_X,
        page.footer_text_yt,
        config.generation.static_footer,
        g.FONT_BOLD,
        g.SIZE_FOOTER,
    )
