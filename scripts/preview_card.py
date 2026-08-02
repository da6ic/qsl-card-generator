"""Rendert eine Testauflage mehrerer Karten (Vorder- + Rückseite) als PDF.

Nutzt den echten Builder + Generator: aus Beispiel-QSOs werden Karten gebaut
(Modus „pro Station"), pro Karte Seite Front dann Rückseite. So werden die
aktuellen Features direkt sichtbar:
- **mehrere QSOs pro Station auf einer Karte** (dynamische Tabelle).
- **volle Karte ohne Remarks**: bis zu 6 Zeilen (PA3BRB).
- **dynamischer REMARKS-Kasten**: erscheint nur bei Karten mit Remarks-Text
  (hier je Karte gesetzt, wie eine Überschreibung in der Vorschau).

Die Absenderdaten (Rufzeichen, Name, Adresse, Locator, DOK, CQ-Zone, ITU) kommen
wie gewohnt komplett aus der Config, nicht aus dem Log.

Aufruf:
    python scripts/preview_card.py [AUSGABE.pdf] [FRONTBILD]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Projektwurzel in den Importpfad.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qslcards.adif.models import QSO  # noqa: E402
from qslcards.cards.builder import build_cards  # noqa: E402
from qslcards.config import AppConfig, GenerationConfig, SenderConfig  # noqa: E402
from qslcards.pdf.generator import generate  # noqa: E402

DEFAULT_IMAGE = ROOT / "Bild.jpg"


def _qso(call: str, time: str, freq: str, mode: str, rst: str) -> QSO:
    return QSO(
        call=call,
        qso_date="20260719",
        time_on=time,
        freq=freq,
        mode=mode,
        rst_sent=rst,
    )


# Beispiel-QSOs mit verschiedenen Betriebsarten, um die Report-Darstellung zu
# zeigen: PA3BRB sechsmal FT8 (dB-Reports -> eine volle Karte mit sechs Zeilen,
# ohne Remarks), plus eine SSB- und eine CW-Station (RST wie im Log), die per
# Remarks-Text den dynamischen REMARKS-Kasten zeigen.
SAMPLE_QSOS = [
    _qso("PA3BRB", "120600", "7.075708", "FT8", "-06"),
    _qso("PA3BRB", "130600", "7.075708", "FT8", "+00"),
    _qso("PA3BRB", "140600", "7.075708", "FT8", "+14"),
    _qso("PA3BRB", "150600", "7.075708", "FT8", "-03"),
    _qso("PA3BRB", "160600", "7.075708", "FT8", "+07"),
    _qso("PA3BRB", "170600", "7.075708", "FT8", "-11"),
    _qso("DL2SCT", "143825", "14.230", "SSB", "59"),
    _qso("G3NFV", "151147", "7.030", "CW", "599"),
]

# Per-Karte gesetzte Remarks (wie eine Überschreibung in der Vorschau). PA3BRB
# bleibt bewusst ohne Remarks -> volle 6-Zeilen-Karte ohne Kasten.
SAMPLE_REMARKS = {
    "DL2SCT": "TNX FB SSB QSO – hpe cu agn 73!",
    "G3NFV": "Gud CW signal, 73 es dx!",
}

SAMPLE_CONFIG = AppConfig(
    sender=SenderConfig(
        callsign="DN5MT",  # Fallback, falls das Log kein Rufzeichen hätte
        name="Axel Tüner",
        street="Wilhelmstr. 76",
        zip="72124",
        city="Pliezhausen",
        country="Deutschland",
        locator="JN48OM",  # Fallback; im Log steht JN48PK
        dok="P31",
        waz="14",
        itu="28",
    ),
    generation=GenerationConfig(
        card_mode="per_station",
        static_footer="TNX FR NICE CONTACT, 73",
        qsl_mark="tnx",
        confirm_mark="qso",
    ),
)


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "card_preview.pdf"
    image = Path(argv[2]) if len(argv) > 2 else DEFAULT_IMAGE

    if not image.exists():
        print(f"Warnung: Frontbild fehlt ({image}).")

    cards = build_cards(SAMPLE_QSOS, SAMPLE_CONFIG)
    # Remarks je Karte setzen (Demo für den dynamischen Kasten).
    for card in cards:
        if card.recipient_call in SAMPLE_REMARKS:
            card.remarks = SAMPLE_REMARKS[card.recipient_call]

    generate(cards, SAMPLE_CONFIG, str(image), str(out))
    pages = 2 * len(cards)
    rows = [len(c.rows) for c in cards]
    print(
        f"geschrieben: {out} ({len(cards)} Karten, Zeilen/Karte={rows}, "
        f"{pages} Seiten, Front={image.name})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
