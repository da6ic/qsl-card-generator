"""Orchestriert die Gesamt-PDF aller Karten (docs/SPECIFICATION.md §7).

Zwei Druckmodi (config.generation.print_mode):

- ``"duplex"``: **eine** PDF, pro Karte zuerst Vorderseite (Frontbild), dann
  Rückseite, mit `showPage()` dazwischen. So ergibt sich Seite 1=Front(Karte1),
  2=Back(Karte1), 3=Front(Karte2), … — passend für Duplexdruck (lange Kante).
- ``"separate"``: **zwei** PDFs für Drucker ohne beidseitigen Druck – eine mit
  allen Vorderseiten (`…_vorderseiten.pdf`), eine mit allen Rückseiten
  (`…_rueckseiten.pdf`). Erst die Vorderseiten drucken, das Papier umgedreht neu
  einlegen, dann die Rückseiten drucken. Weil projektbedingt **ein** Frontbild
  für alle Karten gilt, sind alle Vorderseiten identisch; die Blattzuordnung ist
  daher egal (keine Umkehrung der Rückseiten-Reihenfolge nötig).
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.pdfgen import canvas

from qslcards.cards.builder import effective_via, regroup_card_by_remarks
from qslcards.lookup import active_via_priority

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
) -> list[Path]:
    """Erzeugt die PDF(s) je nach Druckmodus und optional den Adress-Export.

    Liefert die Liste der erzeugten PDF-Pfade zurück (eine im Duplex-, zwei im
    getrennten Modus), damit der Aufrufer sie z. B. öffnen kann.
    """
    # Sicherstellen (pro Karte): keine Karte bekommt mehr Zeilen, als je nach
    # Remarks-Zustand Platz haben — sonst Aufteilung in Folge-Karten. So kann der
    # Grenzfall „viele Zeilen + Remarks" gar nicht in die PDF gelangen, egal wie
    # die Remarks auf die Karte kamen (global, Vorschau, direkte API).
    cards = [part for card in cards for part in regroup_card_by_remarks(card)]

    if config.generation.print_mode == "separate":
        outputs = _generate_separate(cards, config, front_image_path, output_path, progress_cb)
    else:
        outputs = _generate_duplex(cards, config, front_image_path, output_path, progress_cb)

    # Optionaler Adress-/Label-Export (nur wenn aktiviert). Fehler dabei dürfen
    # die bereits erzeugte PDF nicht entwerten -> defensiv, aber schlicht. An den
    # Basis-Ausgabepfad gekoppelt (unabhängig vom Druckmodus).
    if config.lookup.address_export:
        gen = config.generation
        active = active_via_priority(gen.via_priority, gen.via_cut)
        _export_addresses(cards, output_path, active)

    return outputs


def _generate_duplex(
    cards: list[Card],
    config: AppConfig,
    front_image_path: str | Path,
    output_path: str | Path,
    progress_cb: ProgressCb | None,
) -> list[Path]:
    """Eine PDF, pro Karte Vorder- dann Rückseite (Duplexdruck)."""
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
    return [Path(output_path)]


def _generate_separate(
    cards: list[Card],
    config: AppConfig,
    front_image_path: str | Path,
    output_path: str | Path,
    progress_cb: ProgressCb | None,
) -> list[Path]:
    """Zwei PDFs: erst alle Vorderseiten, dann alle Rückseiten (einfache Drucker).

    Fortschritt über beide Durchläufe (total = 2 × Kartenzahl).
    """
    out = Path(output_path)
    front_path = out.with_name(f"{out.stem}_vorderseiten{out.suffix}")
    back_path = out.with_name(f"{out.stem}_rueckseiten{out.suffix}")
    total = 2 * len(cards)

    cf = canvas.Canvas(str(front_path), pagesize=(PAGE_W, PAGE_H))
    for done, _card in enumerate(cards, start=1):
        draw_front(cf, str(front_image_path), config)
        cf.showPage()
        if progress_cb is not None:
            progress_cb(done, total)
    cf.save()

    offset = len(cards)
    cb = canvas.Canvas(str(back_path), pagesize=(PAGE_W, PAGE_H))
    for done, card in enumerate(cards, start=1):
        draw_back(cb, card, config)
        cb.showPage()
        if progress_cb is not None:
            progress_cb(offset + done, total)
    cb.save()

    return [front_path, back_path]


def _export_addresses(
    cards: list[Card], output_path: str | Path, active_priority: list[str]
) -> Path:
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
            via = effective_via(card, active_priority) or ""
            writer.writerow([call, *fields, via])
    return export_path
