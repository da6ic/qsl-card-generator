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
SIZE_ADDRESS = 9
SIZE_LABEL = 8  # "To Amateur…", "Via:", Checkbox-Labels
SIZE_CALL_BOX = 12  # Empfänger-Rufzeichen in der Box
SIZE_VIA = 9
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
ADDR_Z1_YT = mm(24)  # name
ADDR_Z2_YT = mm(29)  # street
ADDR_Z3_YT = mm(34)  # zip + city
ADDR_Z4_YT = mm(39)  # country

# --------------------------------------------------------------------------- #
# Kopf rechts: Empfänger + Via (§3)
# --------------------------------------------------------------------------- #

TO_LABEL_X = mm(78)
TO_LABEL_YT = mm(6)

CALL_BOX_X = mm(78)
CALL_BOX_YT = mm(10)
CALL_BOX_W = mm(62)
CALL_BOX_H = mm(9)

VIA_LABEL_X = mm(78)
VIA_LABEL_YT = mm(22)

VIA_BOX_X = mm(88)
VIA_BOX_YT = mm(21)
VIA_BOX_W = mm(52)
VIA_BOX_H = mm(8)

PORTABLE_P_X = mm(78)
PORTABLE_M_X = mm(90)
PORTABLE_YT = mm(33)

# --------------------------------------------------------------------------- #
# Stationsblock (§3)
# --------------------------------------------------------------------------- #

STATION_X = mm(6)
STATION_YT = mm(45)

# --------------------------------------------------------------------------- #
# Bestätigungs-Checkboxen (§3)
# --------------------------------------------------------------------------- #

CONFIRM_QSO_X = mm(6)
CONFIRM_SWL_X = mm(60)
CONFIRM_YT = mm(51)

# --------------------------------------------------------------------------- #
# QSO-Tabelle (§3)
# --------------------------------------------------------------------------- #

TABLE_X0 = mm(6)  # linke Kante
TABLE_X1 = mm(142)  # rechte Kante
TABLE_WIDTH = mm(136)  # = TABLE_X1 - TABLE_X0
TABLE_YT_TOP = mm(56)  # obere Kante (von oben)
TABLE_YT_BOTTOM = mm(84)  # untere Kante (von oben)

HEAD_H = mm(8)  # Höhe der Kopfzeile
MAX_ROWS = 3  # maximale Datenzeilen pro Karte (Überlauf -> Folge-Karte)
# Höhe einer Datenzeile: (Tabellenhöhe - Kopfzeile) / MAX_ROWS  (~6.7 mm)
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
REMARKS_LABEL_YT = mm(86)

REMARKS_BOX_X = mm(6)
REMARKS_BOX_YT = mm(89)
REMARKS_BOX_W = mm(48)
REMARKS_BOX_H = mm(13)

FOOTER_TEXT_X = mm(6)
FOOTER_TEXT_YT = mm(99)

PSE_QSL_X = mm(70)
TNX_QSL_X = mm(92)
FOOTER_MARK_YT = mm(99)

# --------------------------------------------------------------------------- #
# Checkbox-Hilfsmaß (§4)
# --------------------------------------------------------------------------- #

CHECKBOX_SIZE = mm(3)  # Seitenlänge des Kästchens
