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

from pathlib import Path

# --------------------------------------------------------------------------- #
# mm-Helfer und Seitengeometrie (§1)
# --------------------------------------------------------------------------- #

MM = 72 / 25.4  # Punkte pro mm


def mm(v: float) -> float:
    """Millimeter -> PDF-Punkte."""
    return v * MM


PAGE_W = mm(148)  # A6 quer: Breite
PAGE_H = mm(105)  # A6 quer: Höhe
MARGIN = mm(5)  # Außenrand ringsum

LINE_WIDTH = 0.6  # Standard-Rahmenlinienstärke in pt

# --------------------------------------------------------------------------- #
# Schriften (§1 / SPECIFICATION §8): DejaVuSans für saubere Umlaute.
# Registrierung darf nie fatal sein -> bei Fehlschlag Fallback auf Helvetica.
# --------------------------------------------------------------------------- #

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
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
SIZE_SUBTITLE = 7
SIZE_ADDRESS = 8  # Absenderadresse (kompakter unter dem Untertitel)
SIZE_LABEL = 10  # "To Amateur…", "Via:" (größer, besser lesbar)
SIZE_CALL_BOX = 16  # Empfänger-Rufzeichen in der Box (größer)
SIZE_VIA = 11
SIZE_STATION = 8  # Locator/DOK/WAZ/ITU-Zeile
SIZE_CHECK = 8  # Bestätigungs-Checkboxen
SIZE_TABLE_HEAD = 6.5
SIZE_TABLE_CELL = 8
SIZE_FOOTER = 8

# --------------------------------------------------------------------------- #
# Kopf links: Absenderblock (§3)
# --------------------------------------------------------------------------- #

SENDER_X = mm(6)
CALLSIGN_YT = mm(6)
SUBTITLE_YT = mm(16)
# Adresse dichter unter "Responsive" und enger gesetzt (kleinere Schrift)
ADDR_Z1_YT = mm(21)  # name
ADDR_Z2_YT = mm(25.5)  # street
ADDR_Z3_YT = mm(30)  # zip + city
ADDR_Z4_YT = mm(34.5)  # country

# --------------------------------------------------------------------------- #
# Kopf rechts: Empfänger + Via (§3)
# --------------------------------------------------------------------------- #

TO_LABEL_X = mm(78)
TO_LABEL_YT = mm(6)

# /p und /m sitzen zwischen dem Label und der Rufzeichen-Box.
PORTABLE_P_X = mm(78)
PORTABLE_M_X = mm(92)
PORTABLE_YT = mm(12)

CALL_BOX_X = mm(78)
CALL_BOX_YT = mm(17)
CALL_BOX_W = mm(64)  # bis zur rechten Inhaltskante (78+64=142)
CALL_BOX_H = mm(12)  # größer

VIA_LABEL_X = mm(78)
VIA_LABEL_YT = mm(33)

VIA_BOX_X = mm(90)
VIA_BOX_YT = mm(33)
VIA_BOX_W = mm(52)  # 90+52=142
VIA_BOX_H = mm(10)  # größer

# --------------------------------------------------------------------------- #
# Stationsblock (§3)
# --------------------------------------------------------------------------- #

STATION_X = mm(6)
STATION_YT = mm(40)

# --------------------------------------------------------------------------- #
# Bestätigungs-Checkboxen (§3)
# --------------------------------------------------------------------------- #

CONFIRM_QSO_X = mm(6)
CONFIRM_SWL_X = mm(60)
CONFIRM_YT = mm(46)

# --------------------------------------------------------------------------- #
# QSO-Tabelle (§3)
# --------------------------------------------------------------------------- #

TABLE_X0 = mm(6)  # linke Kante
TABLE_X1 = mm(142)  # rechte Kante
TABLE_WIDTH = mm(136)  # = TABLE_X1 - TABLE_X0
TABLE_YT_TOP = mm(52)  # obere Kante (von oben)
TABLE_YT_BOTTOM = mm(67)  # untere Kante (von oben)

HEAD_H = mm(8)  # Höhe der Kopfzeile
MAX_ROWS = 1  # Datenzeilen pro Karte: genau ein QSO (siehe Builder-Kopplung)
# Höhe einer Datenzeile: (Tabellenhöhe - Kopfzeile) / MAX_ROWS  (= 7 mm)
ROW_H = ((TABLE_YT_BOTTOM - TABLE_YT_TOP) - HEAD_H) / MAX_ROWS

# Spaltenbreiten (Summe = TABLE_WIDTH = 136 mm)
COL_DATE_W = mm(30)  # Unterspalten D/M/Y
COL_UTC_W = mm(24)
COL_FREQ_W = mm(26)
COL_2WAY_W = mm(26)
COL_RST_W = mm(30)  # Unterspalten R/S/T

# Reihenfolge der Hauptspalten (links -> rechts)
COLUMN_WIDTHS = (COL_DATE_W, COL_UTC_W, COL_FREQ_W, COL_2WAY_W, COL_RST_W)

# Unterspaltenbreiten
SUB_DATE_W = mm(10)  # je D, M, Y
SUB_RST_W = mm(10)  # je R, S, T

# --------------------------------------------------------------------------- #
# Fuß (§3)
# --------------------------------------------------------------------------- #

REMARKS_LABEL_X = mm(6)
REMARKS_LABEL_YT = mm(70)

# Box-Unterkante bei yt=99: gleicher Abstand (1 mm) zum unteren Rahmen (yt=100)
# wie links (Box-Kante x=6 zum linken Rahmen x=5).
REMARKS_BOX_X = mm(6)
REMARKS_BOX_YT = mm(73)
REMARKS_BOX_W = mm(60)
REMARKS_BOX_H = mm(26)

# Footer-Text und PSE/TNX rechts neben der REMARKS-Box.
FOOTER_TEXT_X = mm(72)
FOOTER_TEXT_YT = mm(78)

PSE_QSL_X = mm(72)
TNX_QSL_X = mm(100)
FOOTER_MARK_YT = mm(88)

# --------------------------------------------------------------------------- #
# Checkbox-Hilfsmaß (§4)
# --------------------------------------------------------------------------- #

CHECKBOX_SIZE = mm(3)  # Seitenlänge des Kästchens
CHECKBOX_GAP = mm(1.5)  # Abstand zwischen Kästchen und Label
