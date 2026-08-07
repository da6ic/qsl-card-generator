"""Zeichnet die Vorderseite: das Frontbild füllt die komplette A6-Seite.

Cover-Modus: das Bild wird proportional so skaliert, dass es die ganze Seite
ohne weißen Rand bedeckt; Überstand wird am Seitenrand beschnitten (kein
Verzerren).

**`drawImage` bekommt den Dateipfad, nie ein `ImageReader`-Objekt.** ReportLab
bildet den Cache-Schlüssel eines Bildes sonst aus einem MD5 über die komplette
entpackte Bitmap — und zwar bei **jedem** Aufruf. Bei einem 4096×3072-Foto sind
das 37,7 MB, die je Karte einmal kopiert und einmal gehasht werden: gemessene
119 ms pro Seite statt 4,6 ms. Bei einem Contest-Log mit dreitausend Karten ist
das der Unterschied zwischen fünf Minuten und zwanzig Sekunden. Mit dem Pfad ist
der Schlüssel der Dateiname, und ReportLab reicht ein JPEG unverändert in die
PDF durch, statt es als rohes RGB neu zu komprimieren (Datei ~5× kleiner).
Gebraucht wird Pillow hier nur noch für die Bildmaße (Cover-Fit), die gecacht
werden (SPEC §7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from . import geometry as g

if TYPE_CHECKING:
    from reportlab.pdfgen.canvas import Canvas

    from qslcards.config import AppConfig

# Cache: Pfad -> (Breite, Höhe) in Pixeln. Die Maße braucht der Cover-Fit für
# jede Karte; die Datei selbst öffnet ReportLab (einmal je Dokument).
_SIZE_CACHE: dict[str, tuple[int, int]] = {}


def _image_size(image_path: str) -> tuple[int, int]:
    """Bildmaße in Pixeln, je Pfad gecacht."""
    size = _SIZE_CACHE.get(image_path)
    if size is None:
        with Image.open(image_path) as img:
            size = img.size
        _SIZE_CACHE[image_path] = size
    return size


def clear_cache() -> None:
    """Leert den Maß-Cache (z.B. wenn der Nutzer ein anderes Bild wählt)."""
    _SIZE_CACHE.clear()


def draw_front(c: Canvas, image_path: str, config: AppConfig) -> None:
    """Zeichnet das Frontbild zentriert und proportional in den Rahmen.

    Der Rahmen ist ohne Druckrand die volle Seite, sonst das Blatt minus der
    eingestellten Ränder (`geometry.content_box`) — derselbe Rahmen, in den auch
    die Rückseite gesetzt wird, damit beide Seiten deckungsgleich liegen."""
    img_w, img_h = _image_size(image_path)
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
    c.drawImage(image_path, x, y, width=draw_w, height=draw_h, mask="auto")
    c.restoreState()
