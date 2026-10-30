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

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.pdfbase.pdfmetrics import getAscent, getDescent, stringWidth

from qslcards.cards.qr import qr_text

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

# Text der Bestätigungs-Markierung je Code (Inhalt, kein Layout). Ein Eintrag
# fehlt für "none" — dann wird nichts gezeichnet und das eigene Rufzeichen darf
# den Platz bis zum „To Amateur…"-Label nutzen (siehe `_draw_sender`).
_CONFIRM_TEXTS = {"qso": "Confirming QSO", "swl": "Confirming SWL-Report"}


# --------------------------------------------------------------------------- #
# Öffentliche Helfer (CARD_LAYOUT.md §4)
# --------------------------------------------------------------------------- #


def fit_size(s: str, font: str, size: float, max_w: float | None) -> float:
    """Schriftgröße, bei der `s` in `max_w` passt — **nur verkleinern, nie kürzen**.

    Die Karte hat keinen Zeilenumbruch; ohne diese Bremse lief ein langer Name,
    eine ausführliche Antennenbezeichnung oder ein Rufzeichen mit Präfix einfach
    über den Nachbarblock. Statt abzuschneiden wird der Text proportional kleiner
    gesetzt (vom Nutzer so entschieden: lieber klein als unvollständig).

    Passt der Text ohnehin — der Normalfall —, bleibt `size` unverändert; die
    Ausgabe ist dann Zeichen für Zeichen dieselbe wie zuvor. `max_w=None`
    schaltet die Begrenzung ab (Texte ohne Nachbarn, z. B. „PSE QSL")."""
    if not s or max_w is None or max_w <= 0:
        return size
    width = stringWidth(s, font, size)
    if width <= max_w:
        return size
    return max(size * max_w / width, g.MIN_FONT_SIZE)


def text(
    c: Canvas,
    page: PageLayout,
    x: float,
    yt: float,
    s: str,
    font: str,
    size: float,
    align: str = "left",
    max_w: float | None = None,
) -> None:
    """Zeichnet Text, `yt` = Abstand der Glyphen-Oberkante von oben.

    Intern: baseline = page.page_h - yt - ascent, sodass die Textoberkante bei
    `yt` liegt (leichter mit der Vorlage von oben abzugleichen). `max_w` begrenzt
    die Breite (siehe `fit_size`); die Oberkante bleibt dabei bei `yt`, weil die
    Grundlinie aus der **verkleinerten** Schriftgröße berechnet wird."""
    size = fit_size(s, font, size, max_w)
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
    max_w: float | None = None,
) -> None:
    """Text vertikal mittig in einem Band [yt_top .. yt_top+band_h] (von oben).

    `max_w` begrenzt die Breite (siehe `fit_size`) — nötig überall dort, wo der
    Text in einem Kasten oder einer Tabellenzelle steht."""
    size = fit_size(s, font, size, max_w)
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

        _draw_sender(c, page, config, card.confirm_mark in _CONFIRM_TEXTS)
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

    cell_w = col_w - 2 * g.BOX_TEXT_PAD  # Werte bleiben in ihrer Spalte
    for i, (label, value) in enumerate(entries):
        cx = x0 + (i + 0.5) * col_w
        _text_in_band(
            c, page, cx, top, g.RADIO_HEAD_H, label, g.FONT_BOLD, g.SIZE_RADIO_HEAD, max_w=cell_w
        )
        _text_in_band(
            c,
            page,
            cx,
            head_bottom,
            value_h,
            value,
            g.FONT_REGULAR,
            g.SIZE_RADIO,
            max_w=cell_w,
        )


def _draw_sender(c: Canvas, page: PageLayout, config: AppConfig, confirm: bool) -> None:
    s = config.sender
    # Das Rufzeichen steht so auf der Karte, wie es in der Config steht — mit
    # allem, was dazugehört: Landespräfix (`F/DL0MT`), Portabel-Kennung
    # (`/P`), `/QRP`, `/MM`. Nur großgeschrieben wird es, auch bei einer von
    # Hand geänderten Config.
    #
    # Wie viel Platz es hat, hängt am Nachbarn: steht rechts daneben eine
    # Bestätigungs-Markierung, endet das Rufzeichen vor deren Band, sonst erst
    # vor dem „To Amateur…"-Label. Lange Rufzeichen werden entsprechend kleiner
    # gesetzt statt in den Nachbarn zu laufen (siehe `fit_size`).
    callsign_w = g.SENDER_CALLSIGN_W if confirm else g.SENDER_CALLSIGN_W_PLAIN
    text(
        c,
        page,
        g.SENDER_X,
        g.CALLSIGN_YT,
        s.callsign.strip().upper(),
        g.FONT_BOLD,
        g.SIZE_CALLSIGN,
        max_w=callsign_w,
    )
    # Die Adresszeilen enden vor dem Stationsblock („Locator:", „DOK:", …).
    for yt, value in (
        (g.ADDR_Z1_YT, s.name),
        (g.ADDR_Z2_YT, s.street),
        (g.ADDR_Z3_YT, f"{s.zip} {s.city}".strip()),
        (g.ADDR_Z4_YT, s.country),
    ):
        text(
            c,
            page,
            g.SENDER_X,
            yt,
            value,
            g.FONT_REGULAR,
            g.SIZE_ADDRESS,
            max_w=g.SENDER_TEXT_W,
        )


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
        max_w=page.call_box_w - 2 * g.BOX_TEXT_PAD,
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
        max_w=page.via_box_w - 2 * g.BOX_TEXT_PAD,
    )
    # Confirm-Markierung (global aus der Config über card.confirm_mark): nur die
    # ausgewählte Option steht hier, kein Kästchen. Position ist fest (zentriert),
    # unabhängig davon, ob/welche Portabel-Markierung gewählt ist. Das Band endet
    # vor dem „To Amateur…"-Label — ohne die Begrenzung überlappte „Confirming
    # SWL-Report" es schon bei Standardeinstellungen.
    confirm_text = _CONFIRM_TEXTS.get(card.confirm_mark, "")
    if confirm_text:
        text(
            c,
            page,
            g.CONFIRM_MARK_X,
            g.CONFIRM_MARK_YT,
            confirm_text,
            g.FONT_BOLD,
            g.SIZE_MARK,
            align="center",
            max_w=g.CONFIRM_MARK_W,
        )


def _draw_station(c: Canvas, page: PageLayout, config: AppConfig) -> None:
    # Stationsblock als Label/Wert-Spalten rechts neben der Adresse.
    # Locator und DOK sind — wie das Rufzeichen — Großbuchstaben-Felder; die
    # Oberfläche stellt sie beim Verlassen des Feldes um, hier steht die Garantie
    # für von Hand geänderte Config-Dateien. CQ-Zone/ITU sind Zahlen.
    s = config.sender
    rows = (
        ("Locator:", s.locator.strip().upper(), g.STATION_Z1_YT),
        ("DOK:", s.dok.strip().upper(), g.STATION_Z2_YT),
        ("CQ-Zone:", s.waz, g.STATION_Z3_YT),
        ("ITU:", s.itu, g.STATION_Z4_YT),
    )
    for label, value, yt in rows:
        text(c, page, g.STATION_LABEL_X, yt, label, g.FONT_REGULAR, g.SIZE_STATION)
        text(
            c,
            page,
            g.STATION_VALUE_X,
            yt,
            value,
            g.FONT_REGULAR,
            g.SIZE_STATION,
            max_w=g.STATION_VALUE_W,
        )


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


def _col_text_w(edges: list[float], idx: int) -> float:
    """Nutzbare Textbreite einer Tabellenspalte (Spaltenbreite minus Innenabstand).

    Nötig für lange Betriebsarten-Namen (z. B. „OLIVIA 8/250") — sie liefen sonst
    über die Spaltenlinie in die Nachbarspalte."""
    return (edges[idx + 1] - edges[idx]) - 2 * g.BOX_TEXT_PAD


def _draw_table_header(c: Canvas, page: PageLayout, edges: list[float], top: float) -> None:
    # Einzeilige Kopfzeile: je Spalte ein Label, vertikal mittig in der Kopfhöhe.
    # DATE-Spalte trägt die Unterlabels D/M/Y (kein DATE-Titel mehr).
    h = g.HEAD_H
    font = g.FONT_BOLD
    size = g.SIZE_TABLE_HEAD

    date_left = edges[0]
    sub_w = page.sub_date_w - g.BOX_TEXT_PAD
    for k, lbl in enumerate(_HEAD_DATE_SUB):
        _text_in_band(
            c, page, date_left + page.sub_date_w * (k + 0.5), top, h, lbl, font, size, max_w=sub_w
        )
    for idx, label in ((1, _HEAD_UTC), (2, _HEAD_FREQ), (3, _HEAD_2WAY), (4, _HEAD_RST)):
        _text_in_band(
            c,
            page,
            _col_center(edges, idx),
            top,
            h,
            label,
            font,
            size,
            max_w=_col_text_w(edges, idx),
        )


def _draw_table_row(
    c: Canvas, page: PageLayout, edges: list[float], row_top: float, row: CardRow
) -> None:
    font = g.FONT_REGULAR
    size = g.SIZE_TABLE_CELL
    h = g.ROW_H

    date_left = edges[0]
    sub_w = page.sub_date_w - g.BOX_TEXT_PAD
    for k, val in enumerate((row.date_d, row.date_m, row.date_y)):
        _text_in_band(
            c,
            page,
            date_left + page.sub_date_w * (k + 0.5),
            row_top,
            h,
            val,
            font,
            size,
            max_w=sub_w,
        )
    # Report als ein Wert: RST wie im Log (Phone/CW) bzw. dB (Digimodes wie FT8).
    values = (
        (1, row.utc),
        (2, row.freq_mhz),
        (3, row.mode),
        (4, (row.rst_sent or "").strip()),
    )
    for idx, val in values:
        _text_in_band(
            c,
            page,
            _col_center(edges, idx),
            row_top,
            h,
            val,
            font,
            size,
            max_w=_col_text_w(edges, idx),
        )


def _draw_footer(c: Canvas, page: PageLayout, card: Card, config: AppConfig) -> None:
    # REMARKS **dynamisch**: Label + Kasten + Text nur zeichnen, wenn die Karte
    # einen Remarks-Text hat. Ohne Remarks bleibt der Platz frei (der Builder gibt
    # solchen Karten mehr QSO-Zeilen, siehe geometry.MAX_ROWS_*). Der Footer-Text
    # (static_footer) steht unabhängig davon immer unten.
    # Der ganze Fußblock ist an der Unterkante verankert (page.*_yt), damit er
    # beim Druckrand mit nach unten wandert statt an der Tabelle zu kleben.
    # Mit QR-Code rücken Kasten und Footer-Text links vom Code zusammen.
    foot_w = page.remarks_box_w
    if card.qr_code:
        foot_w -= g.QR_SIZE + g.QR_GAP
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
        _box(c, page, g.REMARKS_BOX_X, page.remarks_box_yt, foot_w, g.REMARKS_BOX_H)
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
            max_w=foot_w - 2 * g.REMARKS_TEXT_PAD,
        )
    text(
        c,
        page,
        g.FOOTER_TEXT_X,
        page.footer_text_yt,
        config.generation.static_footer,
        g.FONT_BOLD,
        g.SIZE_FOOTER,
        max_w=foot_w,
    )
    if card.qr_code:
        _draw_qr(c, page, card, config)


def _draw_qr(c: Canvas, page: PageLayout, card: Card, config: AppConfig) -> None:
    """DARC-QR-Code rechts unten, rechtsbündig mit der Tabelle. Wie der Fußblock
    von der Unterkante her verankert (wandert beim Druckrand mit nach unten).
    Als Vektorgrafik gezeichnet, ohne Ruhezone im Widget: der Abstand zu Tabelle
    und Kartenrand ergibt die Ruhezone."""
    widget = QrCodeWidget(qr_text(card, config.sender.callsign), barLevel="M", barBorder=0)
    x0, y0, x1, y1 = widget.getBounds()
    size = g.QR_SIZE
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    top = page.page_h - (g.PAGE_H - g.QR_YT)
    renderPDF.draw(drawing, c, page.table_x1 - size, page.page_h - top - size)
