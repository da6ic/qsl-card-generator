"""Anbindung ans Betriebssystem: Dateien öffnen/zeigen, Programm-Icons.

Aus `gui/app.py` herausgelöst (Bewertung 3.1) — nichts davon braucht den
Zustand der Anwendung.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path

from qslcards import paths

# Fenster-/Programm-Icon: die von `scripts/make_icon.py` gerenderten PNGs.
ICON_DIR = paths.resource_path("qslcards", "assets", "icons")
# GRÖSSTE ZUERST: `wm iconphoto` auf macOS nimmt das erste Bild und skaliert es
# auf die jeweils gebrauchte Größe. Steht dort ein kleines, wirkt das Dock-Icon
# verpixelt. Windows/X11 suchen sich aus der Liste die passende Größe.
ICON_SIZES = (1024, 512, 256, 128, 64, 48, 32, 16)


def open_file(path: str) -> None:
    """Öffnet `path` mit der Standardanwendung des Betriebssystems.

    Plattformübergreifend (Windows, macOS, Linux/Debian). Fehler werden nach
    oben gereicht, damit der Aufrufer bei Bedarf einen Hinweis anzeigen kann.

    `env=paths.subprocess_env()`: im gebündelten Betrieb zeigen `LD_LIBRARY_PATH`
    bzw. `DYLD_LIBRARY_PATH` in die Anwendung, und ein davon geerbtes `xdg-open`
    lädt die falschen Bibliotheken.
    """
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # nur unter Windows
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=True, env=paths.subprocess_env())
    else:
        subprocess.run(["xdg-open", path], check=True, env=paths.subprocess_env())


def reveal_in_file_manager(path: str) -> None:
    """Zeigt `path` im Dateimanager (Finder/Explorer/Dateien) an.

    macOS: `open -R` markiert die Datei; Windows: `explorer /select,`; Linux
    (Debian/Fedora): es gibt keinen portablen „auswählen"-Aufruf, daher wird der
    enthaltende Ordner geöffnet.
    """
    target = Path(path)
    env = paths.subprocess_env()
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(target)], check=True, env=env)
    elif sys.platform.startswith("win"):
        # explorer liefert auch im Erfolgsfall != 0 -> Rückgabewert ignorieren.
        subprocess.run(["explorer", f"/select,{target}"], check=False, env=env)
    else:
        folder = target if target.is_dir() else target.parent
        subprocess.run(["xdg-open", str(folder)], check=True, env=env)


def load_icon(widget: tk.Misc, size: int) -> tk.PhotoImage | None:
    """Lädt ein einzelnes Icon-PNG; fehlt es, gibt es `None` (nie fatal)."""
    try:
        return tk.PhotoImage(master=widget, file=str(ICON_DIR / f"app_icon_{size}.png"))
    except (tk.TclError, OSError):
        return None


def load_app_icons(widget: tk.Misc) -> list[tk.PhotoImage]:
    """Icon-Bilder für `wm iconphoto`, **größtes zuerst**.

    Auf macOS bekommt Tk bewusst nur das größte Bild: die dortige Umsetzung
    skaliert das erste übergebene Bild auf alle gebrauchten Größen, und aus
    einem kleinen PNG wird dabei ein sichtbar verpixeltes Dock-Icon.
    Windows/X11 dagegen profitieren von mehreren Größen, weil der
    Fenstermanager sich die passende heraussucht.
    """
    sizes = ICON_SIZES[:1] if sys.platform == "darwin" else ICON_SIZES
    icons = [load_icon(widget, size) for size in sizes]
    return [icon for icon in icons if icon is not None]
