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
MARGIN = mm(3)  # Außenrand des Rückseiten-Rahmens (nur Rückseite; Front clippt voll)

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
SIZE_REMARKS = 9  # Remarks-Text (dynamisch, nur wenn gesetzt)
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

RADIO_TABLE_X0 = SENDER_X  # x=6, linke Kante (bündig unter dem Absenderblock)
RADIO_TABLE_X1 = mm(85)  # rechte Kante: Lücke vor der Via-Box (x=88) lassen
RADIO_TABLE_YT_TOP = mm(38.5)  # obere Kante, knapp unter der ITU-Zeile (34.5)
RADIO_HEAD_H = mm(3.4)  # Höhe der Beschriftungszeile (RIG/ANT/PWR)
RADIO_VALUE_H = mm(3.9)  # Höhe der Wertezeile (Unterkante bei ~45.8)

# --------------------------------------------------------------------------- #
# PSE/TNX QSL-Markierung (früher als Bestätigungs-Checkboxen an dieser
# Position; jetzt zeigt nur die ausgewählte Option als Text, kein Kästchen).
# --------------------------------------------------------------------------- #

QSL_MARK_X = mm(6)
QSL_MARK_YT = mm(44)
# Wenn der Funk-Block gezeichnet wird, rutscht die QSL-Markierung unter die
# Funk-Tabelle (deren Unterkante bei ~45.8 liegt), mit etwas Abstand.
QSL_MARK_YT_RADIO = mm(47)

# --------------------------------------------------------------------------- #
# QSO-Tabelle (§3)
# --------------------------------------------------------------------------- #

TABLE_X0 = mm(6)  # linke Kante
TABLE_X1 = mm(142)  # rechte Kante
TABLE_WIDTH = mm(136)  # = TABLE_X1 - TABLE_X0
TABLE_YT_TOP = mm(50)  # obere Kante (von oben)
# Ist der Funk-Block sichtbar, beginnt die Tabelle etwas tiefer (rutscht mit der
# QSL-Markierung nach unten). Der Versatz ist klein genug, dass weiterhin
# MAX_ROWS_PLAIN=6 bzw. MAX_ROWS_WITH_REMARKS=3 Zeilen über den Fuß passen.
TABLE_YT_TOP_RADIO = mm(52)

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
TABLE_YT_BOTTOM_WITH_REMARKS = TABLE_YT_TOP + HEAD_H + MAX_ROWS_WITH_REMARKS * ROW_H  # = mm(74)
TABLE_YT_BOTTOM = TABLE_YT_TOP + HEAD_H + MAX_ROWS_PLAIN * ROW_H  # = mm(92)

# Spaltenbreiten (Summe = TABLE_WIDTH = 136 mm)
COL_DATE_W = mm(30)  # Unterspalten D/M/Y
COL_UTC_W = mm(24)
COL_FREQ_W = mm(26)
COL_2WAY_W = mm(26)
COL_RST_W = mm(30)  # SIGNAL REPORT (ein Wert je Zeile, keine Unterspalten mehr)

# Reihenfolge der Hauptspalten (links -> rechts)
COLUMN_WIDTHS = (COL_DATE_W, COL_UTC_W, COL_FREQ_W, COL_2WAY_W, COL_RST_W)

# Unterspaltenbreite nur noch für DATE (D/M/Y). Die Report-Spalte hat keine.
SUB_DATE_W = mm(10)  # je D, M, Y

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
REMARKS_TEXT_PAD = mm(2)  # linker Innenabstand des Remarks-Textes in der Box

# Footer-Text unter der REMARKS-Box (Unterkante ~yt 99). PSE/TNX steht jetzt
# weiter oben (QSL_MARK_X/QSL_MARK_YT), der Footer bleibt frei dafür.
FOOTER_TEXT_X = mm(6)
FOOTER_TEXT_YT = mm(96)
