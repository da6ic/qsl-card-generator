"""Tests für die Vektor-Zeichnung des Programm-Icons (`gui/icon_canvas.py`).

Kern dieser Datei ist der **Abgleich mit `assets/icons/app_icon.svg`**: das SVG
ist die Quelle für die gerenderten PNG/ICO/ICNS, die Canvas-Zeichnung ist die
Quelle für den „Über"-Dialog. Laufen die Zahlen auseinander, sähe das Icon im
Dialog anders aus als im Dock — genau das fängt dieser Test ab.
"""

from __future__ import annotations

import math
import re
import tkinter as tk
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from qslcards.gui import icon_canvas as ic

SVG_PATH = Path(ic.__file__).resolve().parent.parent / "assets" / "icons" / "app_icon.svg"
SVG_NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def svg() -> ET.Element:
    return ET.fromstring(SVG_PATH.read_text(encoding="utf-8"))


def _find(root: ET.Element, tag: str) -> list[ET.Element]:
    return list(root.iter(f"{SVG_NS}{tag}"))


def _num(element: ET.Element, name: str, default: float = 0.0) -> float:
    value = element.get(name)
    return float(value) if value is not None else default


# -- Abgleich SVG <-> Canvas-Zeichnung -------------------------------------


def test_viewbox_matches(svg):
    assert svg.get("viewBox") == f"0 0 {ic.VIEWBOX} {ic.VIEWBOX}"


def test_rounded_rects_match_svg(svg):
    """Jedes <rect> im SVG steht in derselben Reihenfolge in ROUNDED_RECTS."""
    rects = _find(svg, "rect")
    assert len(rects) == len(ic.ROUNDED_RECTS)

    for element, shape in zip(rects, ic.ROUNDED_RECTS, strict=True):
        x, y, w, h, r, fill = shape
        assert (_num(element, "x"), _num(element, "y")) == (x, y)
        assert (_num(element, "width"), _num(element, "height")) == (w, h)
        assert _num(element, "rx") == r
        if element.get("opacity") is None:
            assert element.get("fill") == fill
        else:
            # Der Schatten ist im SVG halbtransparent; der Canvas kennt keine
            # Transparenz und nutzt die vorab gemischte Farbe.
            assert fill == ic.COLOR_SHADOW


def test_shadow_color_is_the_correct_blend(svg):
    """COLOR_SHADOW muss die Mischung aus Schattenfarbe und Grundfläche sein."""
    shadow = next(r for r in _find(svg, "rect") if r.get("opacity"))
    alpha = float(shadow.get("opacity"))

    def rgb(value: str) -> tuple[int, int, int]:
        return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5))

    top, bottom = rgb(shadow.get("fill")), rgb(ic.COLOR_BG)
    expected = tuple(round(alpha * t + (1 - alpha) * b) for t, b in zip(top, bottom, strict=True))
    assert rgb(ic.COLOR_SHADOW) == expected


def test_wave_dot_matches_svg(svg):
    circle = _find(svg, "circle")[0]
    assert (_num(circle, "cx"), _num(circle, "cy")) == ic.WAVE_CENTER
    assert _num(circle, "r") == ic.WAVE_DOT_R
    assert circle.get("fill") == ic.COLOR_CARD


def test_wave_arcs_match_svg(svg):
    """Radien, Endpunkte und Strichstärke der Bögen stimmen mit dem SVG überein."""
    paths = _find(svg, "path")
    assert len(paths) == len(ic.WAVE_RADII)

    # stroke-width steht an der umgebenden <g>-Gruppe.
    group = next(g for g in _find(svg, "g") if g.get("stroke-width"))
    assert float(group.get("stroke-width")) == ic.WAVE_WIDTH
    assert group.get("stroke-linecap") == "round"  # -> capstyle="round" im Canvas

    cx, cy = ic.WAVE_CENTER

    def point(angle: float, radius: float) -> tuple[float, float]:
        rad = math.radians(angle)
        return cx + radius * math.cos(rad), cy - radius * math.sin(rad)

    for element, radius in zip(paths, ic.WAVE_RADII, strict=True):
        # "M x1 y1 A r r 0 0 1 x2 y2"
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", element.get("d"))]
        x1, y1, rx, ry = numbers[0], numbers[1], numbers[2], numbers[3]
        x2, y2 = numbers[-2], numbers[-1]
        assert rx == ry == radius
        assert point(ic.WAVE_ANGLE_FROM, radius) == pytest.approx((x1, y1))
        assert point(ic.WAVE_ANGLE_TO, radius) == pytest.approx((x2, y2))


# -- Zeichnen (braucht Tk) --------------------------------------------------


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"kein Tk-Display: {exc}")
    window.withdraw()
    yield window
    window.destroy()


def test_draw_creates_all_shapes(root):
    canvas = tk.Canvas(root, width=64, height=64)
    ic.draw_app_icon(canvas, 64)
    items = canvas.find_all()
    # Je rundes Rechteck 4 Kreissegmente + 2 Rechtecke, dazu 2 Wellen + 1 Punkt.
    assert len(items) == len(ic.ROUNDED_RECTS) * 6 + len(ic.WAVE_RADII) + 1
    types = {canvas.type(i) for i in items}
    assert types == {"arc", "rectangle", "line", "oval"}


def test_draw_is_idempotent(root):
    """Erneutes Zeichnen leert den Canvas — es sammeln sich keine Formen an."""
    canvas = tk.Canvas(root, width=64, height=64)
    ic.draw_app_icon(canvas, 64)
    first = len(canvas.find_all())
    ic.draw_app_icon(canvas, 128)
    assert len(canvas.find_all()) == first


@pytest.mark.parametrize("size", [16, 32, 64, 256])
def test_drawing_stays_inside_the_box(root, size):
    """Alle Formen liegen im Quadrat (keine Überstände bei kleinen Größen)."""
    canvas = tk.Canvas(root, width=size, height=size)
    ic.draw_app_icon(canvas, size)
    x0, y0, x1, y1 = canvas.bbox("all")
    # Toleranz: halbe Strichstärke der Wellen, dazu 2 px für die 1-px-Kontur der
    # Formen (outline=fill) und die auswärts rundende Messung von `bbox`.
    slack = ic.WAVE_WIDTH * size / ic.VIEWBOX + 2
    assert x0 >= -slack and y0 >= -slack
    assert x1 <= size + slack and y1 <= size + slack


def test_icon_canvas_has_requested_size(root):
    canvas = ic.icon_canvas(root, 64, "#FFFFFF")
    assert int(canvas.cget("width")) == 64
    assert int(canvas.cget("highlightthickness")) == 0
    assert canvas.find_all()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
