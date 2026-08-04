"""Rendert das Programm-Icon aus `assets/icons/app_icon.svg`.

Einzige Quelle der Wahrheit ist das SVG; dieses Skript erzeugt daraus die
Formate, die die Betriebssysteme brauchen:

  app_icon_16…1024.png                   -> Fenster-/Dock-Icon (Tk `iconphoto`)
  app_icon.ico                           -> Windows (Taskleiste, .exe)
  app_icon.icns                          -> macOS (App-Bundle)

1024 px ist die Größe, die das macOS-Dock auf Retina-Displays anfordert — ohne
sie skaliert Tk ein kleineres Bild hoch und das Icon wirkt verpixelt.

Rasterisiert wird mit Tk 9 (kann SVG nativ), die Container-Formate baut Pillow.
Aufruf (nach einer Änderung am SVG):

    .venv/bin/python scripts/make_icon.py
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from PIL import Image

ICON_DIR = Path(__file__).resolve().parent.parent / "qslcards" / "assets" / "icons"
SVG_PATH = ICON_DIR / "app_icon.svg"
PNG_SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(root: tk.Tk, size: int, target: Path) -> None:
    """Rendert das SVG in `size`×`size` und schreibt es als PNG."""
    svg = SVG_PATH.read_text(encoding="utf-8")
    image = tk.PhotoImage(master=root, data=svg, format=f"svg -scaletoheight {size}")
    image.write(str(target), format="png")


def main() -> int:
    if not SVG_PATH.exists():
        print(f"SVG fehlt: {SVG_PATH}", file=sys.stderr)
        return 1

    root = tk.Tk()
    root.withdraw()
    try:
        for size in PNG_SIZES:
            target = ICON_DIR / f"app_icon_{size}.png"
            render_png(root, size, target)
            print(f"geschrieben: {target.name}")
    finally:
        root.destroy()

    # Windows-.ico und macOS-.icns aus den gerenderten PNGs bauen.
    base = Image.open(ICON_DIR / "app_icon_512.png").convert("RGBA")
    ico_path = ICON_DIR / "app_icon.ico"
    base.save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    print(f"geschrieben: {ico_path.name}")

    icns_path = ICON_DIR / "app_icon.icns"
    try:
        base.save(icns_path, format="ICNS")
        print(f"geschrieben: {icns_path.name}")
    except (OSError, ValueError) as exc:  # ICNS-Support ist optional in Pillow
        print(f"ICNS übersprungen: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
