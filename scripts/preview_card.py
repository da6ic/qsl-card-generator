"""Rendert eine Testauflage mehrerer Karten (Vorder- + Rückseite) als PDF.

Nutzt den echten Generator: pro Karte Seite Front dann Rückseite. Mit 3
Beispiel-QSOs entstehen 6 Seiten.

Aufruf:
    python scripts/preview_card.py [AUSGABE.pdf] [FRONTBILD]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Projektwurzel in den Importpfad.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qslcards.cards.models import Card, CardRow  # noqa: E402
from qslcards.config import AppConfig, GenerationConfig, SenderConfig  # noqa: E402
from qslcards.pdf.generator import generate  # noqa: E402

DEFAULT_IMAGE = ROOT / "Bild.jpg"

# Drei Beispiel-QSOs mit etwas Variation (Call, Via, Modus, Markierungen).
SAMPLE_CARDS = [
    Card(
        recipient_call="DL2SCT",
        via_text="via DARC-Büro",
        via_code="B",
        rows=[CardRow("19", "07", "26", "14:38", "14.230", "SSB", "59")],
        qsl_mark="tnx",
        portable_mark="p",
    ),
    Card(
        recipient_call="G3NFV",
        via_text="",
        via_code="D",
        rows=[CardRow("19", "07", "26", "15:11", "7.030", "CW", "599")],
        qsl_mark="tnx",
        portable_mark="none",
    ),
    Card(
        recipient_call="F5ABC",
        via_text="via F6XYZ",
        via_code="M",
        rows=[CardRow("20", "07", "26", "09:05", "144.300", "SSB", "57")],
        qsl_mark="pse",
        portable_mark="m",
    ),
]

SAMPLE_CONFIG = AppConfig(
    sender=SenderConfig(
        callsign="DN5MT",
        subtitle="Responsive",
        name="Axel Tüner",
        street="Wilhelmstr. 76",
        zip="72124",
        city="Pliezhausen",
        country="Deutschland",
        locator="JN48OM",
        dok="P31",
        waz="14",
        itu="28",
    ),
    generation=GenerationConfig(static_footer="TNX FR NICE CONTACT, 73"),
)


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "card_preview.pdf"
    image = Path(argv[2]) if len(argv) > 2 else DEFAULT_IMAGE

    if not image.exists():
        print(f"Warnung: Frontbild fehlt ({image}).")

    generate(SAMPLE_CARDS, SAMPLE_CONFIG, str(image), str(out))
    pages = 2 * len(SAMPLE_CARDS)
    print(f"geschrieben: {out} ({len(SAMPLE_CARDS)} Karten, {pages} Seiten, Front={image.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
