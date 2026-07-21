"""Rendert eine Testkarte mit Beispieldaten als back_preview.pdf.

Zum visuellen Abgleich der Rückseite mit der Referenz (CARD_LAYOUT.md §5).

Aufruf:
    python scripts/preview_back.py [AUSGABE.pdf]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Projektwurzel in den Importpfad.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.pdfgen import canvas  # noqa: E402

from qslcards.cards.models import Card, CardRow  # noqa: E402
from qslcards.config import AppConfig, GenerationConfig, SenderConfig  # noqa: E402
from qslcards.pdf.geometry import PAGE_H, PAGE_W  # noqa: E402
from qslcards.pdf.layout_back import draw_back  # noqa: E402

SAMPLE_CARD = Card(
    recipient_call="DL2SCT",
    via_text="via DARC-Büro",
    via_code="B",
    rows=[
        CardRow("19", "07", "26", "14:38", "14.230", "SSB", "59"),
        CardRow("20", "07", "26", "09:00", "7.150", "SSB", "599"),
        CardRow("21", "07", "26", "10:15", "144.300", "CW", "57"),
    ],
    qsl_mark="tnx",
    portable_mark="p",
)

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
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "back_preview.pdf"
    c = canvas.Canvas(str(out), pagesize=(PAGE_W, PAGE_H))
    draw_back(c, SAMPLE_CARD, SAMPLE_CONFIG)
    c.showPage()
    c.save()
    print(f"geschrieben: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
