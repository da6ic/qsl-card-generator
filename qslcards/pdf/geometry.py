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
MARGIN = mm(3)  # Außenrand des Rahmens (näher am Blattrand)

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
SIZE_ADDRESS = 9  # Absenderadresse
SIZE_LABEL = 10  # "To Amateur…", "Via:" (größer, besser lesbar)
SIZE_CALL_BOX = 16  # Empfänger-Rufzeichen in der Box (größer)
SIZE_VIA = 11
SIZE_STATION = 9  # Locator/DOK/CQ-Zone/ITU-Block (neben der Adresse)
SIZE_CHECK = 8  # Bestätigungs-Checkboxen
SIZE_TABLE_HEAD = 6.5
SIZE_TABLE_CELL = 8
SIZE_FOOTER = 8

# --------------------------------------------------------------------------- #
# Kopf links: Absenderblock (§3)
# --------------------------------------------------------------------------- #

SENDER_X = mm(6)
CALLSIGN_YT = mm(6)
# Adresse direkt unter dem Rufzeichen (kein Untertitel mehr)
ADDR_Z1_YT = mm(18)  # name
ADDR_Z2_YT = mm(23.5)  # street
ADDR_Z3_YT = mm(29)  # zip + city
ADDR_Z4_YT = mm(34.5)  # country

# --------------------------------------------------------------------------- #
# Kopf rechts: Empfänger + Via (§3)
# --------------------------------------------------------------------------- #

TO_LABEL_X = mm(88)
TO_LABEL_YT = mm(8)

CALL_BOX_X = mm(88)
CALL_BOX_YT = mm(12)
CALL_BOX_W = mm(54)  # bis zur rechten Inhaltskante (88+54=142)
CALL_BOX_H = mm(15)

VIA_LABEL_X = mm(88)
VIA_LABEL_YT = mm(31)

VIA_BOX_X = mm(88)
VIA_BOX_YT = mm(35)
VIA_BOX_W = mm(54)  # 88+54=142
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

CONFIRM_MARK_X = mm(66)  # Zentrum von [52 .. 80]
CONFIRM_MARK_YT = mm(8)

# --------------------------------------------------------------------------- #
# Stationsblock (§3): rechts neben der Adresse, als Label/Wert-Spalten,
# vertikal auf Höhe der Adresszeilen.
# --------------------------------------------------------------------------- #

STATION_LABEL_X = mm(50)  # "Locator:", "DOK:", ...
# Werte beginnen alle an derselben x-Position (vertikal bündige Spalte). Muss
# breiter sein als das längste Label ("CQ-Zone:" ≈ 15 mm bei SIZE_STATION),
# sonst rückt der Wert zu dicht an das Label heran.
STATION_VALUE_X = mm(68)
STATION_Z1_YT = ADDR_Z1_YT  # Locator (auf Höhe name)
STATION_Z2_YT = ADDR_Z2_YT  # DOK
STATION_Z3_YT = ADDR_Z3_YT  # CQ-Zone (WAZ)
STATION_Z4_YT = ADDR_Z4_YT  # ITU

# --------------------------------------------------------------------------- #
# PSE/TNX QSL-Markierung (früher als Bestätigungs-Checkboxen an dieser
# Position; jetzt zeigt nur die ausgewählte Option als Text, kein Kästchen).
# --------------------------------------------------------------------------- #

QSL_MARK_X = mm(6)
QSL_MARK_YT = mm(44)

# --------------------------------------------------------------------------- #
# QSO-Tabelle (§3)
# --------------------------------------------------------------------------- #

TABLE_X0 = mm(6)  # linke Kante
TABLE_X1 = mm(142)  # rechte Kante
TABLE_WIDTH = mm(136)  # = TABLE_X1 - TABLE_X0
TABLE_YT_TOP = mm(50)  # obere Kante (von oben)
TABLE_YT_BOTTOM = mm(67)  # untere Kante (von oben)

HEAD_H = mm(8)  # Höhe der Kopfzeile
MAX_ROWS = 1  # Datenzeilen pro Karte: genau ein QSO (siehe Builder-Kopplung)
# Höhe einer Datenzeile: (Tabellenhöhe - Kopfzeile) / MAX_ROWS  (= 9 mm)
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

# REMARKS-Box über die volle Breite, flach. Das Fuß-Konstrukt sitzt unten mit
# ~3 mm Abstand zum Rahmen (gleich wie seitlich: Inhalt x=6, Rahmen x=3).
# Label -> Box mit gleichem Abstand wie "Via:" -> Via-Box (4 mm).
REMARKS_LABEL_X = mm(6)
REMARKS_LABEL_YT = mm(79)

REMARKS_BOX_X = mm(6)
REMARKS_BOX_YT = mm(83)
REMARKS_BOX_W = mm(136)  # volle Inhaltsbreite (6..142)
REMARKS_BOX_H = mm(10)  # flacher

# Footer-Text unter der REMARKS-Box (Unterkante ~yt 99). PSE/TNX steht jetzt
# weiter oben (QSL_MARK_X/QSL_MARK_YT), der Footer bleibt frei dafür.
FOOTER_TEXT_X = mm(6)
FOOTER_TEXT_YT = mm(96)
