"""Bogendruck: vier A6-Karten auf einem A4-Bogen + Schnitt-Hilfslinien.

Siehe docs/SPECIFICATION.md §7 „Bogendruck". Der Generator kennt nur noch
„Seiten mit einer oder mehreren Karten"; wie die Karten auf dem Blatt liegen,
steht ausschließlich hier (Zahlen wie immer in `geometry.py`).

Zwei Punkte, die das Zusammenspiel tragen:

- **Hier wird nur verschoben, nicht skaliert.** Der Bogen wird lückenlos in vier
  Zellen à 148,5 × 105 mm geteilt; das Canvas wandert je Karte auf den
  Zellen-Ursprung, den Rest erledigt das gewohnte `page_layout` (dessen Rahmen
  im Bogen die Zelle minus Druckrand ist). Dadurch gilt im Bogen dieselbe Regel
  wie beim Einzeldruck: die Karte wird proportional eingepasst, der Überschuss
  auf der freien Achse fließt ins Layout, und jede Karte hat ihren Rand ringsum.
- **Vorder- und Rückseite dürfen sich beim Wenden vertauschen.** Projektbedingt
  gilt *ein* Frontbild für alle Karten, alle vier Vorderseiten eines Bogens sind
  also identisch — egal um welche Kante der Drucker wendet, hinter jeder
  Rückseite liegt dieselbe Vorderseite. Deshalb braucht es keine gespiegelte
  Zellenreihenfolge (gleiche Begründung wie beim Druckmodus „separate").
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, TypeVar

from . import geometry as g

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas

    from qslcards.config import AppConfig

T = TypeVar("T")


def page_size(config: AppConfig) -> tuple[float, float]:
    """Seitengröße der PDF: A4 quer im Bogenmodus, sonst A6 quer."""
    if g.is_sheet_mode(config):
        return (g.SHEET_W, g.SHEET_H)
    return (g.PAGE_W, g.PAGE_H)


def cards_per_page(config: AppConfig) -> int:
    """Wie viele Karten auf eine PDF-Seite kommen (4 im Bogenmodus, sonst 1)."""
    return g.CARDS_PER_SHEET if g.is_sheet_mode(config) else 1


def chunk_pages(items: Sequence[T], config: AppConfig) -> list[list[T]]:
    """Teilt die Karten in Gruppen je PDF-Seite auf.

    Der letzte Bogen bleibt ggf. unvollständig — die leeren Zellen werden nicht
    gefüllt (die Schnittlinien laufen trotzdem durch, damit jeder Bogen gleich
    geschnitten wird)."""
    step = cards_per_page(config)
    return [list(items[i : i + step]) for i in range(0, len(items), step)]


def draw_page(
    c: Canvas,
    config: AppConfig,
    items: Sequence[T],
    draw_card: Callable[[T], None],
    *,
    cut_guides: bool = False,
) -> None:
    """Zeichnet die Karten **einer** PDF-Seite.

    `draw_card(item)` zeichnet eine Karte so, als wäre der Ursprung die untere
    linke Ecke ihres Rahmens — ohne Bogenmodus ist das die Seite selbst, im
    Bogenmodus die jeweilige Zelle, auf die vorher verschoben wird."""
    if not g.is_sheet_mode(config):
        for item in items:  # ohne Bogen: genau eine Karte je Seite
            draw_card(item)
        return

    layout = g.sheet_layout(config)
    # strict=False ist Absicht: der letzte Bogen hat oft weniger als vier
    # Karten, die restlichen Zellen bleiben leer.
    for (cell_x, cell_y), item in zip(layout.cells, items, strict=False):
        c.saveState()
        try:
            c.translate(cell_x, cell_y)
            draw_card(item)
        finally:
            c.restoreState()

    if cut_guides:
        draw_cut_guides(c, layout)


def draw_cut_guides(c: Canvas, layout: g.SheetLayout) -> None:
    """Gestricheltes Schnittkreuz zwischen den vier Karten.

    Gezeichnet wird in **Bogenkoordinaten** (außerhalb der Zellen-Verschiebung):
    die Linien laufen über den ganzen bedruckbaren Bereich und liegen dabei exakt
    auf der Zellengrenze. Strichstärke und Muster bleiben so unabhängig davon,
    wie stark die Karten eingepasst wurden."""
    x, y, w, h = layout.printable

    c.saveState()
    try:
        c.setLineWidth(g.CUT_LINE_WIDTH)
        c.setStrokeGray(g.CUT_GRAY)
        c.setDash(list(g.CUT_DASH))
        c.line(x, layout.cut_y, x + w, layout.cut_y)  # waagerecht
        c.line(layout.cut_x, y, layout.cut_x, y + h)  # senkrecht
    finally:
        c.restoreState()
