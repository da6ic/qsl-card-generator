"""Zeichnet die Vorderseite: das Frontbild füllt die komplette A6-Seite.

Cover-Modus: das Bild wird proportional so skaliert, dass es die ganze Seite
ohne weißen Rand bedeckt; Überstand wird am Seitenrand beschnitten (kein
Verzerren). Das Bild wird einmal via Pillow geladen und als ImageReader
gecacht, damit es für alle Karten wiederverwendet werden kann (SPEC §7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image
from reportlab.lib.utils import ImageReader

from . import geometry as g

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas

    from qslcards.config import AppConfig

# Cache: Pfad -> ImageReader (einmal laden, mehrfach zeichnen).
_IMAGE_CACHE: dict[str, ImageReader] = {}


def _load_image(image_path: str) -> ImageReader:
    """Lädt das Bild via Pillow und cacht einen ImageReader je Pfad."""
    reader = _IMAGE_CACHE.get(image_path)
    if reader is None:
        with Image.open(image_path) as img:
            img.load()
            reader = ImageReader(img.copy())
        _IMAGE_CACHE[image_path] = reader
    return reader


def clear_cache() -> None:
    """Leert den Bild-Cache (z.B. wenn der Nutzer ein anderes Bild wählt)."""
    _IMAGE_CACHE.clear()


def draw_front(c: Canvas, image_path: str, config: AppConfig) -> None:
    """Zeichnet das Frontbild zentriert und proportional in den Rahmen.

    Der Rahmen ist ohne Druckrand die volle Seite, sonst das Blatt minus der
    eingestellten Ränder (`geometry.content_box`) — derselbe Rahmen, in den auch
    die Rückseite gesetzt wird, damit beide Seiten deckungsgleich liegen."""
    reader = _load_image(image_path)
    img_w, img_h = reader.getSize()
    box_x, box_y, box_w, box_h = g.content_box(config)

    # Cover: Bild füllt den kompletten Rahmen ohne weißen Rand. Skalierung nach
    # der größeren Achse; Überstand ragt über den Rahmen hinaus und wird per Clip
    # beschnitten. Seitenverhältnis bleibt gewahrt (das Bild wird nie verzerrt).
    scale = max(box_w / img_w, box_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = box_x + (box_w - draw_w) / 2
    y = box_y + (box_h - draw_h) / 2

    c.saveState()
    clip = c.beginPath()
    clip.rect(box_x, box_y, box_w, box_h)
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(reader, x, y, width=draw_w, height=draw_h, mask="auto")
    c.restoreState()
