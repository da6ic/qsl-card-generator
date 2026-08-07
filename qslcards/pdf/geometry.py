"""Seitenmaße, mm-Helfer und ALLE Layout-Konstanten der Rückseite.

Quelle: docs/CARD_LAYOUT.md §1 und §3. Gemäß CLAUDE.md §7 stehen sämtliche
Layout-Zahlen ausschließlich hier als benannte Konstanten — der Zeichencode in
layout_back.py enthält keine Magic Numbers.

Konvention (CARD_LAYOUT.md §1): Der ReportLab-Ursprung liegt unten links.
Positionen werden als `x` (von links) und `yt` (von *oben*) angegeben; die
Umrechnung ist `y_pdf = PAGE_H - <yt>`. Alle hier abgelegten Maße sind bereits in
**Punkten** (über mm() umgerechnet), außer den reinen Zählwerten (MAX_ROWS) und
Schriftgrößen (bereits in pt) und Linienstärken (in pt).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from qslcards import paths

if TYPE_CHECKING:
    from qslcards.config import AppConfig

# --------------------------------------------------------------------------- #
# mm-Helfer und Seitengeometrie (§1)
# --------------------------------------------------------------------------- #

MM = 72 / 25.4  # Punkte pro mm


def mm(v: float) -> float:
    """Millimeter -> PDF-Punkte."""
    return v * MM


PAGE_W = mm(148)  # A6 quer: Breite
PAGE_H = mm(105)  # A6 quer: Höhe
# Einheitlicher Inhaltsrand auf ALLEN vier Kanten. Es gibt keinen sichtbaren
# Rahmen mehr (die schwarze Umrandung sah im Druck unruhig aus); MARGIN legt nur
# noch fest, wie weit der Inhalt von der Papierkante wegbleibt. Linke/obere
# Anker liegen bei MARGIN, rechte/untere Kanten bei PAGE_W/PAGE_H - MARGIN.
MARGIN = mm(3)

LINE_WIDTH = 0.6  # Standard-Rahmenlinienstärke in pt

# --------------------------------------------------------------------------- #
# Schriften (§1 / SPECIFICATION §8): DejaVuSans für saubere Umlaute.
# Registrierung darf nie fatal sein -> bei Fehlschlag Fallback auf Helvetica.
# --------------------------------------------------------------------------- #

_FONT_DIR = paths.resource_path("qslcards", "assets", "fonts")
_DEJAVU_REGULAR = _FONT_DIR / "DejaVuSans.ttf"
_DEJAVU_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"

_FALLBACK_REGULAR = "Helvetica"
_FALLBACK_BOLD = "Helvetica-Bold"


def _register_fonts() -> tuple[str, str]:
    """Registriert DejaVuSans (regular + bold) und liefert die zu nutzenden
    Fontnamen. Fehlt eine Datei oder schlägt die Registrierung fehl, wird auf
    die Standard-PDF-Fonts zurückgefallen (nicht fatal)."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        regular = _FALLBACK_REGULAR
        bold = _FALLBACK_BOLD
        if _DEJAVU_REGULAR.exists():
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(_DEJAVU_REGULAR)))
            regular = "DejaVuSans"
        if _DEJAVU_BOLD.exists():
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(_DEJAVU_BOLD)))
            bold = "DejaVuSans-Bold"
        return regular, bold
    except Exception:  # pragma: no cover - Registrierung nie fatal
        return _FALLBACK_REGULAR, _FALLBACK_BOLD


# Aufgelöste Fontnamen (DejaVuSans, falls verfügbar, sonst Helvetica).
FONT_REGULAR, FONT_BOLD = _register_fonts()

# --------------------------------------------------------------------------- #
# Schriftgrößen (§3), in pt
# --------------------------------------------------------------------------- #

SIZE_CALLSIGN = 22
SIZE_ADDRESS = 9  # Absenderadresse
SIZE_LABEL = 10  # "To Amateur…", "Via:" (größer, besser lesbar)
SIZE_CALL_BOX = 16  # Empfänger-Rufzeichen in der Box (größer)
SIZE_VIA = 11
SIZE_STATION = 9  # Locator/DOK/CQ-Zone/ITU-Block (neben der Adresse)
SIZE_CHECK = 8  # Bestätigungs-Checkboxen
# PSE/TNX-QSL- und Confirming-Markierung: bewusst markanter (fett + größer),
# damit die gewählte Aussage sofort ins Auge fällt.
SIZE_MARK = 11
SIZE_TABLE_HEAD = 6.5
SIZE_TABLE_CELL = 8
SIZE_REMARKS = 9  # Remarks-Text (dynamisch, nur wenn gesetzt)
SIZE_FOOTER = 8

# --------------------------------------------------------------------------- #
# Kopf links: Absenderblock (§3)
# --------------------------------------------------------------------------- #

SENDER_X = MARGIN  # linke Inhaltskante (3 mm)
CALLSIGN_YT = MARGIN  # obere Inhaltskante (3 mm)
# Adresse direkt unter dem Rufzeichen (kein Untertitel mehr); Zeilenabstand 6 mm
ADDR_Z1_YT = mm(15.5)  # name
ADDR_Z2_YT = mm(21.5)  # street
ADDR_Z3_YT = mm(27.5)  # zip + city
ADDR_Z4_YT = mm(33.5)  # country

# --------------------------------------------------------------------------- #
# Kopf rechts: Empfänger + Via (§3)
# --------------------------------------------------------------------------- #

TO_LABEL_X = mm(88.5)
TO_LABEL_YT = mm(5)

CALL_BOX_X = mm(88.5)
CALL_BOX_YT = mm(9.5)
CALL_BOX_W = PAGE_W - MARGIN - CALL_BOX_X  # bis zur rechten Inhaltskante (145)
CALL_BOX_H = mm(15)

VIA_LABEL_X = mm(88.5)
VIA_LABEL_YT = mm(29.5)

VIA_BOX_X = mm(88.5)
VIA_BOX_YT = mm(34)
VIA_BOX_W = PAGE_W - MARGIN - VIA_BOX_X  # bis zur rechten Inhaltskante (145)
VIA_BOX_H = mm(12)

# --------------------------------------------------------------------------- #
# Confirm-Markierung ("Confirming QSO" / "Confirming SWL-Report"): oben, im
# Bereich zwischen eigenem Call und dem "To Amateur…"-Block, wo früher die /p
# /m-Kästchen standen. Nur die ausgewählte Option wird als Text gezeichnet
# (kein Kästchen mehr, da die Karte ohnehin gezielt für diese Auswahl gedruckt
# wird). /p /m /t /r stehen stattdessen dynamisch hinter dem eigenen Rufzeichen
# (siehe _draw_sender). Die Position ist FEST (unabhängig davon, ob/welche
# Portabel-Markierung gewählt ist): zentriert zwischen dem alten Start der
# Portabel-Markierung (PORTABLE_P_X wäre 52) und deren theoretischem Ende
# (PORTABLE_M_X=66 + Kästchen/Label-Breite ≈ 80).
# --------------------------------------------------------------------------- #

CONFIRM_MARK_X = mm(65.5)  # zentriert zwischen eigenem Call und "To Amateur…"
CONFIRM_MARK_YT = mm(5)

# --------------------------------------------------------------------------- #
# Stationsblock (§3): rechts neben der Adresse, als Label/Wert-Spalten,
# vertikal auf Höhe der Adresszeilen.
# --------------------------------------------------------------------------- #

STATION_LABEL_X = mm(49)  # "Locator:", "DOK:", ...
# Werte beginnen alle an derselben x-Position (vertikal bündige Spalte). Muss
# breiter sein als das längste Label ("CQ-Zone:" ≈ 15 mm bei SIZE_STATION),
# sonst rückt der Wert zu dicht an das Label heran.
STATION_VALUE_X = mm(67.5)
STATION_Z1_YT = ADDR_Z1_YT  # Locator (auf Höhe name)
STATION_Z2_YT = ADDR_Z2_YT  # DOK
STATION_Z3_YT = ADDR_Z3_YT  # CQ-Zone (WAZ)
STATION_Z4_YT = ADDR_Z4_YT  # ITU

# --------------------------------------------------------------------------- #
# Funk-Block (Empfänger/Antenne/Leistung): dynamisch, nur wenn gefüllt. Wird als
# **kleine beschriftete Tabelle** gezeichnet (3 Spalten mit Kopfzeile oben:
# RIG / ANT / PWR, Werte in der Zeile darunter). Die Tabelle sitzt linksbündig
# **direkt unter dem Stationsblock** (knapp unter der ITU-Zeile) und **schöpft die
# freie Breite links der Via-Box aus** (x=6 … RADIO_TABLE_X1). Nur befüllte Felder
# bekommen eine Spalte; die Spalten teilen sich die volle Breite gleichmäßig auf
# (1, 2 oder 3 Spalten). Ist mindestens ein Feld gesetzt, rücken QSL-Markierung
# und QSO-Tabelle nach unten (QSL_MARK_YT_RADIO / TABLE_YT_TOP_RADIO).
# --------------------------------------------------------------------------- #

SIZE_RADIO = 8  # Funk-Werte (kompakt)
SIZE_RADIO_HEAD = 6  # Beschriftung (RIG/ANT/PWR), etwas kleiner als die Werte

# Feste Spaltenbeschriftungen (Inhalt, nicht Layout): funkerübliche Kurzformen.
RADIO_LABEL_RIG = "RIG"  # Transceiver / Empfänger
RADIO_LABEL_ANT = "ANT"  # Antenne
RADIO_LABEL_PWR = "PWR"  # Sendeleistung (Watt)

RADIO_TABLE_X0 = SENDER_X  # x=3, linke Kante (bündig unter dem Absenderblock)
RADIO_TABLE_X1 = mm(85.5)  # rechte Kante: Lücke vor der Via-Box (x=88.5) lassen
RADIO_TABLE_YT_TOP = mm(37.5)  # obere Kante, knapp unter der ITU-Zeile (33.5)
# Unterkante **bündig mit der Via-Box** (deren Unterkante liegt bei
# VIA_BOX_YT + VIA_BOX_H = 46). Die Beschriftungszeile ist fix hoch, die
# Wertezeile füllt den Rest bis zur Unterkante (siehe layout_back._draw_radio).
RADIO_TABLE_YT_BOTTOM = VIA_BOX_YT + VIA_BOX_H
RADIO_HEAD_H = mm(3.4)  # Höhe der Beschriftungszeile (RIG/ANT/PWR)

# --------------------------------------------------------------------------- #
# PSE/TNX QSL-Markierung (früher als Bestätigungs-Checkboxen an dieser
# Position; jetzt zeigt nur die ausgewählte Option als Text, kein Kästchen).
# --------------------------------------------------------------------------- #

QSL_MARK_X = MARGIN
QSL_MARK_YT = mm(43.5)
# Wenn der Funk-Block gezeichnet wird, rutscht die QSL-Markierung unter die
# Funk-Tabelle (deren Unterkante nun bündig zur Via-Box bei yt=46 liegt).
QSL_MARK_YT_RADIO = mm(47.5)

# --------------------------------------------------------------------------- #
# QSO-Tabelle (§3)
# --------------------------------------------------------------------------- #

TABLE_X0 = MARGIN  # linke Kante (3 mm)
TABLE_X1 = PAGE_W - MARGIN  # rechte Kante (145 mm)
TABLE_WIDTH = TABLE_X1 - TABLE_X0  # 142 mm
TABLE_YT_TOP = mm(49.5)  # obere Kante (von oben)
# Ist der Funk-Block sichtbar, beginnt die Tabelle etwas tiefer (rutscht mit der
# QSL-Markierung nach unten). Der Versatz ist klein genug, dass weiterhin
# MAX_ROWS_PLAIN=6 bzw. MAX_ROWS_WITH_REMARKS=3 Zeilen über den Fuß passen.
TABLE_YT_TOP_RADIO = mm(51.5)

# Die Tabelle wird **dynamisch** gezeichnet: sie bekommt genau so viele Daten-
# zeilen, wie die Karte QSOs hat; mehr QSOs einer Station -> Folge-Karte(n)
# (siehe Builder-Kopplung). ROW_H ist daher eine feste Zeilenhöhe, nicht aus der
# Tabellenhöhe abgeleitet.
#
# Die **Maximalzahl der Zeilen hängt davon ab, ob ein Remarks-Text auf der Karte
# steht** (Remarks werden dynamisch gezeichnet, siehe Fuß-Block):
#   * Mit Remarks braucht der Remarks-Block darunter Platz -> die Tabelle muss
#     oberhalb von REMARKS_LABEL_YT enden -> MAX_ROWS_WITH_REMARKS Zeilen.
#   * Ohne Remarks entfällt der Block -> die Tabelle darf bis knapp über den
#     Footer laufen -> MAX_ROWS_PLAIN Zeilen (mehr).
# Der Builder splittet je Station nach dieser Grenze in Folge-Karten.
MAX_ROWS_WITH_REMARKS = 3  # Datenzeilen pro Karte, wenn Remarks gesetzt sind
MAX_ROWS_PLAIN = 6  # Datenzeilen pro Karte ohne Remarks (mehr Platz)
MAX_ROWS = MAX_ROWS_PLAIN  # absolute Obergrenze je Karte (Layout-Cap)
ROW_H = mm(6)  # feste Höhe einer Datenzeile
# Kopfzeile: einzeilig und so hoch wie eine Datenzeile.
HEAD_H = ROW_H
# Untere Kanten der Tabelle bei voller Belegung. Bei weniger Zeilen endet die
# Tabelle entsprechend höher (dynamisch, siehe layout_back._draw_table).
#   * mit Remarks: muss oberhalb des REMARKS-Blocks (REMARKS_LABEL_YT) bleiben.
#   * ohne Remarks: muss oberhalb des Footers (FOOTER_TEXT_YT) bleiben.
TABLE_YT_BOTTOM_WITH_REMARKS = TABLE_YT_TOP + HEAD_H + MAX_ROWS_WITH_REMARKS * ROW_H  # = mm(73.5)
TABLE_YT_BOTTOM = TABLE_YT_TOP + HEAD_H + MAX_ROWS_PLAIN * ROW_H  # = mm(91.5)

# Spaltenbreiten (Summe = TABLE_WIDTH = 142 mm)
COL_DATE_W = mm(31.5)  # Unterspalten D/M/Y (durch 3 teilbar)
COL_UTC_W = mm(25)
COL_FREQ_W = mm(27.5)
COL_2WAY_W = mm(27.5)
COL_RST_W = mm(30.5)  # SIGNAL REPORT (ein Wert je Zeile, keine Unterspalten mehr)

# Reihenfolge der Hauptspalten (links -> rechts)
COLUMN_WIDTHS = (COL_DATE_W, COL_UTC_W, COL_FREQ_W, COL_2WAY_W, COL_RST_W)

# Unterspaltenbreite nur noch für DATE (D/M/Y). Die Report-Spalte hat keine.
SUB_DATE_W = COL_DATE_W / 3  # je D, M, Y (= mm(10.5))

# --------------------------------------------------------------------------- #
# Fuß (§3)
# --------------------------------------------------------------------------- #

# REMARKS-Box über die volle Breite, flach. Das Fuß-Konstrukt sitzt unten mit
# dem einheitlichen 3-mm-Rand (Inhalt x=3, wie überall).
# Label -> Box mit gleichem Abstand wie "Via:" -> Via-Box (4 mm).
REMARKS_LABEL_X = MARGIN
REMARKS_LABEL_YT = mm(80.5)

REMARKS_BOX_X = MARGIN
REMARKS_BOX_YT = mm(84.5)
REMARKS_BOX_W = TABLE_WIDTH  # volle Inhaltsbreite (3..145)
REMARKS_BOX_H = mm(10)  # flacher
REMARKS_TEXT_PAD = mm(2)  # linker Innenabstand des Remarks-Textes in der Box

# Footer-Text unter der REMARKS-Box. PSE/TNX steht jetzt weiter oben
# (QSL_MARK_X/QSL_MARK_YT), der Footer bleibt frei dafür.
FOOTER_TEXT_X = MARGIN
FOOTER_TEXT_YT = mm(98.5)

# --------------------------------------------------------------------------- #
# Bogendruck: vier A6-Karten auf einem A4-Bogen (config.generation.sheet_mode)
#
# 2 × A6 quer nebeneinander = 296 mm, 2 × übereinander = 210 mm — das passt in
# **A4 quer** (297 × 210 mm). Der Bogen wird lückenlos in vier Zellen à
# 148,5 × 105 mm geteilt (`sheet_cell_size`); jede Zelle tritt an die Stelle
# einer A6-Seite und wird über das übliche `page_layout` gefüllt — Druckrand
# inklusive, damit jede geschnittene Karte ringsum denselben Rand hat.
# Zwischen den Karten laufen gestrichelte Schnitt-Hilfslinien (nur auf den
# Rückseitenbogen, siehe layout_sheet.py).
# --------------------------------------------------------------------------- #

SHEET_MODE_SINGLE = "single"  # eine Karte je PDF-Seite (A6) — Default
SHEET_MODE_A4_4UP = "a4_4up"  # vier Karten je PDF-Seite (A4 quer)
SHEET_MODES = (SHEET_MODE_SINGLE, SHEET_MODE_A4_4UP)

SHEET_W = mm(297)  # A4 quer: Breite
SHEET_H = mm(210)  # A4 quer: Höhe

SHEET_COLS = 2  # Karten nebeneinander
SHEET_ROWS = 2  # Karten übereinander
CARDS_PER_SHEET = SHEET_COLS * SHEET_ROWS  # 4
BLOCK_W = SHEET_COLS * PAGE_W  # 296 mm — Breite des 2×2-Blocks
BLOCK_H = SHEET_ROWS * PAGE_H  # 210 mm — Höhe des 2×2-Blocks

# Gestrichelte Schnitt-Hilfslinien zwischen den Karten (Kreuz durch die
# Blockmitte, bis an die Kanten des bedruckbaren Bereichs). Bewusst dünn und
# grau: sie liegen exakt auf der Schnittkante, ein leicht schiefer Schnitt soll
# keinen kräftigen Strich am Kartenrand hinterlassen.
CUT_LINE_WIDTH = 0.3  # pt
CUT_DASH = (mm(2), mm(2))  # Strich/Lücke
CUT_GRAY = 0.5  # 0 = schwarz, 1 = weiß


def normalize_sheet_mode(value: object) -> str:
    """Bogenmodus aus der Config lesen; alles Unbekannte -> Einzelkarte."""
    return value if value in SHEET_MODES else SHEET_MODE_SINGLE  # type: ignore[return-value]


def is_sheet_mode(config: AppConfig) -> bool:
    """True, wenn vier Karten auf einen A4-Bogen sollen."""
    mode = normalize_sheet_mode(getattr(config.generation, "sheet_mode", SHEET_MODE_SINGLE))
    return mode == SHEET_MODE_A4_4UP


# --------------------------------------------------------------------------- #
# Druckrand: elastischer Seitenrahmen (config.generation.print_margin_*)
#
# Viele Drucker drucken nicht bis zur Blattkante. Ist der Druckrand aktiv, soll
# die Karte innerhalb der eingestellten Ränder Platz finden — **ohne Verzerrung**
# (ein einziger Faktor für beide Achsen) und **ohne verschenkten Rand**.
#
# Rechenweg (docs/CARD_LAYOUT.md §1):
#   1. Rahmen = Blatt minus der vier Ränder.
#   2. scale  = min(rahmen_b/PAGE_W, rahmen_h/PAGE_H)  -> proportional, nie verzerrt.
#   3. Weil `scale` nur von einer Achse bestimmt wird, bleibt auf der anderen
#      Platz übrig. Statt ihn als Leerraum stehen zu lassen, wird auf einer
#      **größeren virtuellen Seite** gezeichnet: page_w = rahmen_b/scale,
#      page_h = rahmen_h/scale. Eine der beiden ist exakt PAGE_W bzw. PAGE_H,
#      die andere größer. Nach translate+scale füllt die Zeichnung den Rahmen exakt.
#   4. Die von PAGE_W/PAGE_H abgeleiteten Maße (Call-/Via-Box, Tabelle, Remarks)
#      wachsen dadurch mit; der Fußblock wird von **unten** verankert. Alle
#      links/oben verankerten Blöcke (Absender, Station, Funk) bleiben, wo sie sind.
#
# MAX_ROWS_* bleibt unberührt: senkrechter Überschuss vergrößert nur den Abstand
# zwischen Tabelle und Fuß, die Kartenaufteilung im Builder ändert sich nicht.
# --------------------------------------------------------------------------- #

PRINT_MARGIN_MAX = 15.0  # mm, Obergrenze je Kante (GUI-Spinbox + Clamping)
# Deckel für den elastischen Überschuss je Achse: bei extremen Randwerten würden
# Boxen und Spalten sonst absurd breit. Was darüber hinausgeht, wird zentriert
# (der Rand ist dann größer als eingestellt — nur ein Sicherheitsventil).
MAX_STRETCH = mm(20)

# Reihenfolge der Ränder überall: oben, unten, links, rechts.
_MARGIN_FIELDS = (
    "print_margin_top",
    "print_margin_bottom",
    "print_margin_left",
    "print_margin_right",
)


def clamp_print_margin(value: object) -> float:
    """Einen Randwert aus der Config auf 0..PRINT_MARGIN_MAX mm begrenzen.

    Robust gegen alles, was in einer handgeschriebenen YAML stehen kann
    (None, Text, negative Zahlen) — die Config wird bewusst ungeprüft geladen
    und erst hier beim Konsumenten geclampt."""
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    if v != v:  # NaN
        return 0.0
    return max(0.0, min(v, PRINT_MARGIN_MAX))


def print_margins(config: AppConfig) -> tuple[float, float, float, float]:
    """Die vier geclampten Druckränder (oben, unten, links, rechts) in Punkten.

    Sie gelten **je Karte**, auch im Bogen: dort bekommt jede der vier Zellen den
    Rand auf allen vier Kanten. Nur so hat jede geschnittene Karte denselben Rand
    ringsum — läge er einmal um den ganzen Bogen, hätte jede Karte ihn nur auf
    zwei Seiten und der Inhalt säße außermittig. Zwischen zwei Karten entsteht
    dadurch ein doppelt breiter weißer Streifen, durch dessen Mitte geschnitten
    wird; nach außen bleibt der Rand einfach frei (was der Drucker ohnehin
    braucht).

    Ist der Druckrand abgeschaltet, sind alle vier 0 -> alles wie bisher."""
    gen = config.generation
    if not gen.print_margin_enabled:
        return (0.0, 0.0, 0.0, 0.0)
    return tuple(mm(clamp_print_margin(getattr(gen, name, 0.0))) for name in _MARGIN_FIELDS)  # type: ignore[return-value]


def content_box(config: AppConfig) -> tuple[float, float, float, float]:
    """Der Rahmen **einer Karte** als (x, y, w, h) in Punkten.

    Ohne Druckrand ist das die volle A6-Seite, mit Druckrand die Seite minus der
    vier Ränder. Im Bogenmodus tritt die **Zelle** des 2×2-Rasters an die Stelle
    der Seite (Ursprung ist dann deren untere linke Ecke, denn `layout_sheet`
    verschiebt das Canvas vorher dorthin) — die Ränder werden genauso abgezogen,
    also bekommt jede Karte ihren Rand ringsum. Auch von der Vorderseite genutzt,
    damit Bild und Rückseite exakt denselben Rahmen bekommen."""
    top, bottom, left, right = print_margins(config)
    page_w, page_h = sheet_cell_size(config) if is_sheet_mode(config) else (PAGE_W, PAGE_H)
    return (left, bottom, page_w - left - right, page_h - top - bottom)


@dataclass(frozen=True)
class PageLayout:
    """Zeichenrahmen einer Seite: Transformation + die mitwachsenden Maße.

    `dx`/`dy`/`scale` gehören auf das Canvas (translate + gleichmäßiges scale);
    danach wird im System einer virtuellen Seite `page_w` × `page_h` gezeichnet.
    Die Felder tragen die Namen der Konstanten, aus denen sie abgeleitet sind —
    alle übrigen Maße bleiben die festen Konstanten oben."""

    dx: float
    dy: float
    scale: float
    page_w: float
    page_h: float
    # rechts angebundene Breiten (wachsen mit page_w)
    call_box_w: float
    via_box_w: float
    table_x1: float
    table_width: float
    column_widths: tuple[float, ...]
    sub_date_w: float
    remarks_box_w: float
    # Fußblock: von der Unterkante her verankert (wächst mit page_h nach unten)
    remarks_label_yt: float
    remarks_box_yt: float
    footer_text_yt: float


def page_layout(config: AppConfig) -> PageLayout:
    """Baut den Zeichenrahmen für die Rückseite aus den Druckrändern.

    Ohne Druckrand liefert sie exakt die heutigen Werte (scale=1, keine
    Verschiebung, virtuelle Seite = A6) — die Ausgabe ändert sich dann nicht."""
    x, y, w, h = content_box(config)
    scale = min(w / PAGE_W, h / PAGE_H)

    # Virtuelle Seite (im ungeskalierten System), gedeckelt auf MAX_STRETCH.
    page_w = min(w / scale, PAGE_W + MAX_STRETCH)
    page_h = min(h / scale, PAGE_H + MAX_STRETCH)
    # Was der Deckel übrig lässt, mittig verteilen (sonst ist der Rest 0).
    dx = x + (w - page_w * scale) / 2
    dy = y + (h - page_h * scale) / 2

    table_x1 = page_w - MARGIN
    table_width = table_x1 - TABLE_X0
    # Spalten anteilig auf die neue Breite verteilen, damit die letzte Spalte
    # wieder exakt an der rechten Tabellenkante schließt.
    stretch = table_width / TABLE_WIDTH
    column_widths = tuple(cw * stretch for cw in COLUMN_WIDTHS)

    return PageLayout(
        dx=dx,
        dy=dy,
        scale=scale,
        page_w=page_w,
        page_h=page_h,
        call_box_w=page_w - MARGIN - CALL_BOX_X,
        via_box_w=page_w - MARGIN - VIA_BOX_X,
        table_x1=table_x1,
        table_width=table_width,
        column_widths=column_widths,
        sub_date_w=column_widths[0] / 3,
        remarks_box_w=table_width,
        remarks_label_yt=page_h - (PAGE_H - REMARKS_LABEL_YT),
        remarks_box_yt=page_h - (PAGE_H - REMARKS_BOX_YT),
        footer_text_yt=page_h - (PAGE_H - FOOTER_TEXT_YT),
    )


# --------------------------------------------------------------------------- #
# Bogen-Layout (4 Karten auf A4 quer)
# --------------------------------------------------------------------------- #


def sheet_cell_size(config: AppConfig) -> tuple[float, float]:
    """Größe einer Zelle des 2×2-Rasters in Punkten: 148,5 × 105 mm.

    Die vier Zellen kacheln den Bogen **restlos** — eine Zelle ist exakt ein
    Viertel von A4 und damit das echte ISO-A6-Maß (die Karte selbst ist auf
    148 × 105 ausgelegt, der halbe Millimeter Überschuss fließt über
    `page_layout` ins Layout). Der Druckrand steckt **in** der Zelle, nicht
    zwischen Zelle und Blattkante: geschnitten wird auf der Zellengrenze, und
    jede Karte behält ihren Rand ringsum (siehe `print_margins`).

    `config` wird noch nicht ausgewertet, gehört aber zur Signatur: die
    Zellengröße ist die Antwort auf „wie groß ist eine Seite in diesem Modus".
    """
    del config  # das Raster hängt (anders als der Rand) an keiner Einstellung
    return (SHEET_W / SHEET_COLS, SHEET_H / SHEET_ROWS)


def sheet_printable_box(config: AppConfig) -> tuple[float, float, float, float]:
    """Der Bereich des Bogens, in den überhaupt gedruckt wird, als (x, y, w, h).

    Das ist der Bogen minus des Druckrands — nur so weit dürfen die
    Schnitt-Hilfslinien laufen (weiter außen kann der Drucker nicht). Für die
    Platzierung der Karten ist er **nicht** zuständig, die sitzen im Raster aus
    `sheet_cell_size`."""
    top, bottom, left, right = print_margins(config)
    return (left, bottom, SHEET_W - left - right, SHEET_H - top - bottom)


@dataclass(frozen=True)
class SheetLayout:
    """Platzierung der vier Karten auf einem A4-Bogen.

    `cells` sind die Zellen-Ursprünge (unten links) in **Bogenkoordinaten**, in
    Lesereihenfolge: oben-links, oben-rechts, unten-links, unten-rechts. Das
    Canvas wird nur dorthin verschoben — eingepasst wird die Karte nicht hier,
    sondern in `page_layout` (deren Rahmen ist `content_box` = die Zelle minus
    Druckrand).

    `cut_x`/`cut_y` ist der Kreuzungspunkt der Schnittlinien (Blattmitte, also
    exakt die Zellengrenze), `printable` der bedruckbare Bereich des Bogens."""

    printable: tuple[float, float, float, float]
    cell_w: float
    cell_h: float
    cells: tuple[tuple[float, float], ...]
    cut_x: float
    cut_y: float


def sheet_layout(config: AppConfig) -> SheetLayout:
    """Baut die Bogen-Aufteilung: 2×2 Zellen à 148,5 × 105 mm, die den Bogen
    lückenlos kacheln.

    Der Druckrand verändert das Raster **nicht** — er wird innerhalb jeder Zelle
    abgezogen (`content_box`). Dadurch liegt zwischen zwei Karten ein doppelt
    breiter weißer Streifen, dessen Mitte die Schnittkante ist: jede Karte hat
    hinterher denselben Rand auf allen vier Seiten."""
    cell_w, cell_h = sheet_cell_size(config)

    # Lesereihenfolge (oben-links zuerst); ReportLab zählt y von unten.
    cells = tuple(
        (col * cell_w, (SHEET_ROWS - 1 - row) * cell_h)
        for row in range(SHEET_ROWS)
        for col in range(SHEET_COLS)
    )

    return SheetLayout(
        printable=sheet_printable_box(config),
        cell_w=cell_w,
        cell_h=cell_h,
        cells=cells,
        cut_x=SHEET_W / 2,
        cut_y=SHEET_H / 2,
    )
