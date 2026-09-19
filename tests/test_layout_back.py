"""Tests für pdf.layout_back — vor allem die Breitenbegrenzung (`fit_size`).

Die Karte kennt keinen Zeilenumbruch. Ohne Begrenzung lief jeder zu lange Wert
über seinen Nachbarn: ein langer Name über den Stationsblock, eine ausführliche
Antennenbezeichnung über die Spaltenlinie — und „Confirming SWL-Report" über das
„To Amateur Radio Station:"-Label, also schon bei Standardeinstellungen ohne
jedes Zutun des Anwenders.

Geprüft wird deshalb nicht nur die Rechenregel, sondern das **gezeichnete
Ergebnis**: ein Aufnahme-Canvas merkt sich jeden Text samt Schrift, Größe und
Ausrichtung, daraus ergeben sich die tatsächlichen linken und rechten Kanten.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from reportlab.pdfbase.pdfmetrics import stringWidth

from qslcards.cards.models import Card, CardRow
from qslcards.config import AppConfig, GenerationConfig, SenderConfig
from qslcards.pdf import geometry as g
from qslcards.pdf.layout_back import draw_back, fit_size

EPS = 1e-6


# --- Aufnahme-Canvas ------------------------------------------------------


@dataclass(frozen=True)
class _Text:
    """Ein gezeichneter Text mit seinen tatsächlichen Kanten (in Punkten)."""

    s: str
    font: str
    size: float
    left: float
    right: float


class _RecordingCanvas:
    """Canvas-Attrappe: zeichnet nichts, merkt sich nur die Texte.

    `draw_back` braucht nur diese Handvoll Methoden; Linien und Rahmen sind für
    die Frage „läuft ein Text über seinen Nachbarn?" ohne Belang.
    """

    def __init__(self) -> None:
        self.texts: list[_Text] = []
        self._font: tuple[str, float] = ("", 0.0)

    # -- ignorierte Zeichenbefehle
    def saveState(self) -> None: ...
    def restoreState(self) -> None: ...
    def translate(self, *_a: float) -> None: ...
    def scale(self, *_a: float) -> None: ...
    def setLineWidth(self, *_a: float) -> None: ...
    def rect(self, *_a: float, **_k: object) -> None: ...
    def line(self, *_a: float) -> None: ...

    # -- aufgezeichnete Zeichenbefehle
    def setFont(self, name: str, size: float) -> None:
        self._font = (name, size)

    def drawString(self, x: float, _y: float, s: str) -> None:
        self._record(x, s, "left")

    def drawCentredString(self, x: float, _y: float, s: str) -> None:
        self._record(x, s, "center")

    def drawRightString(self, x: float, _y: float, s: str) -> None:
        self._record(x, s, "right")

    def _record(self, x: float, s: str, align: str) -> None:
        font, size = self._font
        width = stringWidth(s, font, size)
        left = x if align == "left" else x - width / 2 if align == "center" else x - width
        self.texts.append(_Text(s, font, size, left, left + width))


def _draw(config: AppConfig, card: Card) -> list[_Text]:
    canvas = _RecordingCanvas()
    draw_back(canvas, card, config)  # type: ignore[arg-type]
    return canvas.texts


def _find(texts: list[_Text], s: str) -> _Text:
    for item in texts:
        if item.s == s:
            return item
    raise AssertionError(f"Text {s!r} wurde nicht gezeichnet")


# --- Beispieldaten --------------------------------------------------------


def _card(**kwargs: object) -> Card:
    data: dict = {
        "recipient_call": "DL2SCT",
        "via_text": "",
        "via_routes": ("B",),
        "rows": [
            CardRow(
                date_d="19",
                date_m="07",
                date_y="26",
                utc="12:06",
                freq_mhz="7.076",
                mode="SSB",
                rst_sent="59",
            )
        ],
    }
    data.update(kwargs)
    return Card(**data)


NORMAL_SENDER = SenderConfig(
    callsign="DN5MT",
    name="Axel Tüner",
    street="Wilhelmstr. 76",
    zip="72124",
    city="Pliezhausen",
    country="Deutschland",
    locator="JN48OM",
    dok="P31",
    waz="14",
    itu="28",
)

# Alles bewusst zu lang: so sieht eine Karte aus, die vor der Begrenzung
# überall übereinandergedruckt hätte.
LONG_SENDER = SenderConfig(
    callsign="SV2/DL1ABC/QRP",
    name="Hans-Joachim Schmidt-Brinkmann",
    street="Oberer Katzenbuckelweg 123a",
    zip="72124",
    city="Pliezhausen-Gniebel",
    country="Bundesrepublik Deutschland",
    locator="JN48OM",
    dok="P31",
    waz="14",
    itu="28",
    receiver="Yaesu FT-991A",
    antenna="Hy-Gain TH-11DX Beam 11 el.",
    power="750 W PEP",
)


# --- fit_size (die Rechenregel) -------------------------------------------


def test_fit_size_keeps_the_size_when_the_text_fits():
    """Der Normalfall darf sich nicht ändern — sonst wäre jede bisherige Karte anders."""
    assert fit_size("DN5MT", g.FONT_BOLD, g.SIZE_CALLSIGN, g.SENDER_CALLSIGN_W) == g.SIZE_CALLSIGN


def test_fit_size_shrinks_exactly_until_the_text_fits():
    text = "Hans-Joachim Schmidt-Brinkmann"
    size = fit_size(text, g.FONT_REGULAR, g.SIZE_ADDRESS, g.SENDER_TEXT_W)
    assert size < g.SIZE_ADDRESS
    assert stringWidth(text, g.FONT_REGULAR, size) == pytest.approx(g.SENDER_TEXT_W)


def test_fit_size_never_truncates_and_never_reaches_zero():
    """Vom Nutzer so entschieden: lieber klein als unvollständig."""
    size = fit_size("M" * 200, g.FONT_REGULAR, g.SIZE_REMARKS, g.mm(5))
    assert size >= g.MIN_FONT_SIZE


@pytest.mark.parametrize("max_w", [None, 0.0, -1.0])
def test_fit_size_without_a_usable_limit_leaves_the_size_alone(max_w):
    assert fit_size("egal wie lang", g.FONT_REGULAR, g.SIZE_ADDRESS, max_w) == g.SIZE_ADDRESS


def test_fit_size_ignores_empty_text():
    assert fit_size("", g.FONT_REGULAR, g.SIZE_ADDRESS, g.mm(1)) == g.SIZE_ADDRESS


# --- Gezeichnetes Ergebnis: nichts läuft über seinen Nachbarn -------------


def test_normal_card_is_drawn_at_the_configured_sizes():
    """Regressionsschutz: eine gewöhnliche Karte wird unverändert gesetzt."""
    config = AppConfig(sender=NORMAL_SENDER)
    texts = _draw(config, _card())
    assert _find(texts, "DN5MT").size == g.SIZE_CALLSIGN
    assert _find(texts, "Axel Tüner").size == g.SIZE_ADDRESS
    assert _find(texts, "DL2SCT").size == g.SIZE_CALL_BOX
    assert _find(texts, "JN48OM").size == g.SIZE_STATION


def test_confirm_mark_stays_left_of_the_recipient_label():
    """Der Fall, der schon ohne lange Eingaben auftrat: „Confirming SWL-Report"
    ist bei SIZE_MARK breiter als sein Platz und überlappte das Label rechts."""
    config = AppConfig(sender=NORMAL_SENDER, generation=GenerationConfig(confirm_mark="swl"))
    mark = _find(_draw(config, _card(confirm_mark="swl")), "Confirming SWL-Report")
    assert mark.right <= g.TO_LABEL_X + EPS
    assert mark.size < g.SIZE_MARK  # er passt nur verkleinert


def test_long_sender_lines_stay_left_of_the_station_block():
    texts = _draw(AppConfig(sender=LONG_SENDER), _card())
    for line in (LONG_SENDER.name, LONG_SENDER.street, LONG_SENDER.country):
        assert _find(texts, line).right <= g.STATION_LABEL_X + EPS


def test_long_callsign_stays_left_of_the_confirm_mark():
    config = AppConfig(sender=LONG_SENDER, generation=GenerationConfig(confirm_mark="qso"))
    texts = _draw(config, _card(confirm_mark="qso"))
    callsign = _find(texts, LONG_SENDER.callsign)
    mark = _find(texts, "Confirming QSO")
    assert callsign.right <= mark.left + EPS


def test_callsign_may_use_the_full_width_without_a_confirm_mark():
    """Ohne Markierung steht der Platz bis zum „To Amateur…"-Label zur Verfügung —
    sonst würde ein Rufzeichen grundlos kleiner gesetzt."""
    config = AppConfig(sender=LONG_SENDER, generation=GenerationConfig(confirm_mark="none"))
    callsign = _find(_draw(config, _card(confirm_mark="none")), LONG_SENDER.callsign)
    assert callsign.right <= g.TO_LABEL_X + EPS
    assert callsign.size == g.SIZE_CALLSIGN  # 14 Zeichen passen hier noch


def test_long_radio_values_stay_inside_their_column():
    texts = _draw(AppConfig(sender=LONG_SENDER), _card())
    col_w = (g.RADIO_TABLE_X1 - g.RADIO_TABLE_X0) / 3
    for index, value in enumerate((LONG_SENDER.receiver, LONG_SENDER.antenna, LONG_SENDER.power)):
        cell_left = g.RADIO_TABLE_X0 + index * col_w
        item = _find(texts, value)
        assert item.left >= cell_left - EPS
        assert item.right <= cell_left + col_w + EPS


def test_long_mode_stays_inside_its_table_column():
    row = CardRow(
        date_d="19",
        date_m="07",
        date_y="26",
        utc="12:06",
        freq_mhz="7.076",
        mode="OLIVIA 8/250",
        rst_sent="-06",
    )
    texts = _draw(AppConfig(sender=NORMAL_SENDER), _card(rows=[row]))
    left = g.TABLE_X0 + sum(g.COLUMN_WIDTHS[:3])
    item = _find(texts, "OLIVIA 8/250")
    assert item.left >= left - EPS
    assert item.right <= left + g.COL_2WAY_W + EPS


def test_maximum_length_remarks_stay_inside_their_box():
    """80 Zeichen sind erlaubt (GUI-Limit) — 80 **breite** Zeichen passen nicht
    in eine Zeile und werden deshalb kleiner gesetzt."""
    remarks = "M" * 80
    texts = _draw(AppConfig(sender=NORMAL_SENDER), _card(remarks=remarks))
    item = _find(texts, remarks)
    assert item.left >= g.REMARKS_BOX_X + g.REMARKS_TEXT_PAD - EPS
    assert item.right <= g.REMARKS_BOX_X + g.REMARKS_BOX_W - g.REMARKS_TEXT_PAD + EPS


def test_nothing_is_drawn_outside_the_card_content_area():
    """Sammelnetz: kein einziger Text verlässt den 3-mm-Inhaltsrahmen."""
    config = AppConfig(
        sender=LONG_SENDER,
        generation=GenerationConfig(
            qsl_mark="tnx",
            confirm_mark="swl",
            remarks="Vielen Dank für das nette QSO – 73 und hoffentlich bis bald am Band!",
        ),
    )
    card = _card(
        recipient_call="OH2XX/MM",
        via_text="DK1XY/P",
        confirm_mark="swl",
        qsl_mark="tnx",
        remarks=config.generation.remarks,
    )
    for item in _draw(config, card):
        assert item.left >= g.MARGIN - EPS, item
        assert item.right <= g.PAGE_W - g.MARGIN + EPS, item
