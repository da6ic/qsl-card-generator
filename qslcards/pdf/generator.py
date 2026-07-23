"""Orchestriert die Gesamt-PDF aller Karten (docs/SPECIFICATION.md §7).

Reihenfolge pro Karte: zuerst Vorderseite (Frontbild), dann Rückseite, mit
`showPage()` dazwischen. So ergibt sich Seite 1=Front(Karte1), 2=Back(Karte1),
3=Front(Karte2), … — passend für Duplexdruck (lange Kante).
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.pdfgen import canvas

from .geometry import PAGE_H, PAGE_W
from .layout_back import draw_back
from .layout_front import draw_front

if TYPE_CHECKING:
    from qslcards.cards.models import Card
    from qslcards.config import AppConfig

# progress_cb(done, total): wird nach jeder fertigen Karte aufgerufen.
ProgressCb = Callable[[int, int], None]


def generate(
    cards: list[Card],
    config: AppConfig,
    front_image_path: str | Path,
    output_path: str | Path,
    progress_cb: ProgressCb | None = None,
) -> None:
    """Erzeugt die Gesamt-PDF (2 Seiten je Karte) und optional den Adress-Export."""
    total = len(cards)
    c = canvas.Canvas(str(output_path), pagesize=(PAGE_W, PAGE_H))

    for done, card in enumerate(cards, start=1):
        draw_front(c, str(front_image_path), config)
        c.showPage()
        draw_back(c, card, config)
        c.showPage()
        if progress_cb is not None:
            progress_cb(done, total)

    c.save()

    # Optionaler Adress-/Label-Export (nur wenn aktiviert). Fehler dabei dürfen
    # die bereits erzeugte PDF nicht entwerten -> defensiv, aber schlicht.
    if config.lookup.address_export:
        _export_addresses(cards, output_path)


def _export_addresses(cards: list[Card], output_path: str | Path) -> Path:
    """Schreibt eine simple CSV mit Empfängeradressen **aller** Stationen, die
    per Lookup eine Adresse haben (dedupliziert pro Rufzeichen).

    Genutzt werden die per Lookup gefüllten `card.recipient`-Daten; Stationen
    ohne jegliche Adressdaten werden übersprungen. Datei liegt neben der PDF.
    """
    out = Path(output_path)
    export_path = out.with_name(f"{out.stem}_addresses.csv")

    with open(export_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["call", "name", "street", "zip", "city", "country", "via"])
        seen: set[str] = set()
        for card in cards:
            call = card.recipient_call
            if call in seen:
                continue
            r = card.recipient
            fields = [
                getattr(r, "name", "") or "",
                getattr(r, "street", "") or "",
                getattr(r, "zip", "") or "",
                getattr(r, "city", "") or "",
                getattr(r, "country", "") or "",
            ]
            if not any(fields):  # keine Adressdaten -> nicht exportieren
                continue
            seen.add(call)
            writer.writerow([call, *fields, card.via_code])
    return export_path
