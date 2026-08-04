"""Das Programm-Icon als **Vektorzeichnung** auf einem Tk-Canvas.

Warum nicht einfach das PNG? Tk bildet ein Bildpixel auf einen Tk-Punkt ab.
Auf einem Retina-Display (hier: 1440 logische Punkte auf 2560 echten Pixeln)
skaliert macOS jedes Bitmap um ~1,8× hoch — das Icon wirkt weich. Canvas-Formen
werden dagegen von Core Graphics mit voller Geräteauflösung gerastert und sind
bei jeder Größe scharf.

**Zwei Stellen, eine Form:** Die Koordinaten hier entsprechen 1:1 denen in
`assets/icons/app_icon.svg` (beide im 512er-Koordinatensystem). Wird das SVG
geändert, müssen `ROUNDED_RECTS`/`WAVE_*` mitgezogen werden —
`tests/test_icon_canvas.py` vergleicht dafür die Zahlen beider Dateien und
schlägt fehl, sobald sie auseinanderlaufen.

Die Farben sind **fest** (nicht aus der Palette): ein Programmsymbol muss in
hell wie dunkel identisch zum Dock-/Taskleisten-Icon aussehen.
"""

from __future__ import annotations

import math
import tkinter as tk

# Koordinatensystem des SVG (viewBox="0 0 512 512").
VIEWBOX = 512

# Farben aus app_icon.svg.
COLOR_BG = "#1F6FEB"  # Grundfläche (= theme.LIGHT.accent)
COLOR_CARD = "#FFFFFF"  # Kartenfläche und Funkwellen
COLOR_LINE = "#C7D3E4"  # angedeutete Textzeilen auf der Karte
# Der Kartenschatten liegt im SVG als #0B2A5B mit 28 % Deckkraft auf der
# Grundfläche. Der Tk-Canvas kennt keine Transparenz -> die Mischfarbe ist hier
# fest ausgerechnet (0,28 × Schatten + 0,72 × Grundfläche).
COLOR_SHADOW = "#195CC3"

# Runde Rechtecke: (x, y, breite, höhe, radius, farbe) — Zeichenreihenfolge
# von hinten nach vorn, identisch zum SVG.
ROUNDED_RECTS: list[tuple[float, float, float, float, float, str]] = [
    (0, 0, 512, 512, 112, COLOR_BG),  # Grundfläche
    (66, 188, 340, 232, 26, COLOR_SHADOW),  # Kartenschatten
    (52, 172, 340, 232, 26, COLOR_CARD),  # Karte
    (88, 208, 140, 28, 14, COLOR_BG),  # Rufzeichen-Balken
    (88, 268, 200, 18, 9, COLOR_LINE),  # Textzeilen
    (88, 306, 272, 18, 9, COLOR_LINE),
    (88, 344, 150, 18, 9, COLOR_LINE),
]

# Funkwellen: Sender-Punkt und zwei Kreisbögen um ihn herum.
WAVE_CENTER = (318.0, 138.0)
WAVE_DOT_R = 15.0
WAVE_RADII = (58.0, 112.0)
WAVE_WIDTH = 26.0
# Winkelbereich der Bögen (Grad, 90° = nach oben, 0° = nach rechts) — die
# Wellen strahlen nach oben rechts ab.
WAVE_ANGLE_FROM = 90.0
WAVE_ANGLE_TO = 0.0
_WAVE_STEPS = 24  # Stützpunkte je Bogen; darüber ist keine Kante mehr sichtbar


def _rounded_rect(
    canvas: tk.Canvas, x: float, y: float, w: float, h: float, r: float, fill: str, s: float
) -> list[int]:
    """Zeichnet ein rundes Rechteck (Tk kennt dafür keine eigene Form).

    Aufbau: vier Kreissegmente in den Ecken plus zwei überlappende Rechtecke.
    Alle Werte in SVG-Koordinaten, `s` ist der Skalierungsfaktor.
    """
    x0, y0, x1, y1 = x * s, y * s, (x + w) * s, (y + h) * s
    r = min(r * s, (x1 - x0) / 2, (y1 - y0) / 2)
    items = []
    # Ecken: (Bounding-Box der Ecke, Startwinkel) — jeweils eine Viertelscheibe.
    corners = (
        ((x0, y0, x0 + 2 * r, y0 + 2 * r), 90),  # oben links
        ((x1 - 2 * r, y0, x1, y0 + 2 * r), 0),  # oben rechts
        ((x1 - 2 * r, y1 - 2 * r, x1, y1), 270),  # unten rechts
        ((x0, y1 - 2 * r, x0 + 2 * r, y1), 180),  # unten links
    )
    for box, start in corners:
        items.append(
            # outline=fill statt "": sonst bleibt an der Nahtstelle ein Haarriss.
            canvas.create_arc(
                *box, start=start, extent=90, style="pieslice", fill=fill, outline=fill
            )
        )
    items.append(canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=fill))
    items.append(canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline=fill))
    return items


def _wave_arc(canvas: tk.Canvas, radius: float, s: float) -> int:
    """Ein Funkwellen-Bogen als Linienzug mit runden Enden.

    `create_arc` zeichnet nur stumpfe Enden; das SVG hat runde (`stroke-linecap`).
    Deshalb wird der Bogen als Polylinie mit `capstyle="round"` gezogen.
    """
    cx, cy = WAVE_CENTER
    points: list[float] = []
    for step in range(_WAVE_STEPS + 1):
        angle = WAVE_ANGLE_FROM + (WAVE_ANGLE_TO - WAVE_ANGLE_FROM) * step / _WAVE_STEPS
        rad = math.radians(angle)
        # y-Achse zeigt im Canvas (wie im SVG) nach unten.
        points.append((cx + radius * math.cos(rad)) * s)
        points.append((cy - radius * math.sin(rad)) * s)
    return canvas.create_line(
        *points,
        fill=COLOR_CARD,
        width=max(1.0, WAVE_WIDTH * s),
        capstyle="round",
        joinstyle="round",
        smooth=True,
    )


def draw_app_icon(canvas: tk.Canvas, size: int) -> None:
    """Zeichnet das Programm-Icon in `size`×`size` Punkten auf `canvas`.

    Der Canvas wird vorher geleert, sodass die Funktion beim Größenwechsel
    einfach erneut aufgerufen werden kann.
    """
    canvas.delete("all")
    s = size / VIEWBOX

    for x, y, w, h, r, fill in ROUNDED_RECTS[:2]:  # Grundfläche + Schatten
        _rounded_rect(canvas, x, y, w, h, r, fill, s)

    # Wellen liegen im SVG zwischen Grundfläche und Karte.
    for radius in WAVE_RADII:
        _wave_arc(canvas, radius, s)
    cx, cy = WAVE_CENTER
    canvas.create_oval(
        (cx - WAVE_DOT_R) * s,
        (cy - WAVE_DOT_R) * s,
        (cx + WAVE_DOT_R) * s,
        (cy + WAVE_DOT_R) * s,
        fill=COLOR_CARD,
        outline=COLOR_CARD,
    )

    for x, y, w, h, r, fill in ROUNDED_RECTS[2:]:  # Karte + Inhalt
        _rounded_rect(canvas, x, y, w, h, r, fill, s)


def icon_canvas(parent: tk.Misc, size: int, background: str) -> tk.Canvas:
    """Fertiger Canvas mit dem gezeichneten Icon (randlos, feste Größe)."""
    canvas = tk.Canvas(
        parent,
        width=size,
        height=size,
        background=background,
        highlightthickness=0,
        borderwidth=0,
    )
    draw_app_icon(canvas, size)
    return canvas
