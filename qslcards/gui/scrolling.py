"""Plattformübergreifendes Mausrad-Handling.

Die drei Fenstersysteme melden das Mausrad unterschiedlich — und Tk 9 hat das
Verhalten unter X11 geändert (TIP 474). Damit die Oberfläche überall gleich
scrollt, liegt die Fallunterscheidung an genau **einer** Stelle:

| System                     | Ereignis                    | `delta`            |
|----------------------------|-----------------------------|--------------------|
| macOS (aqua)               | `<MouseWheel>`              | kleine Beträge     |
| Windows (win32, 32/64 Bit) | `<MouseWheel>`              | Vielfache von 120  |
| Linux/X11 mit Tk 9         | `<MouseWheel>`              | ±120               |
| Linux/X11 mit Tk 8.6       | `<Button-4>` / `<Button-5>` | kein `delta`       |

Die Bitbreite von Windows spielt keine Rolle — 32- und 64-Bit-Builds liefern
dieselben Ereignisse. Debian und Fedora unterscheiden sich ebenfalls nicht
voneinander, wohl aber in der ausgelieferten Tk-Version (Debian 12: Tk 8.6,
neuere Fedora: Tk 9) — genau das deckt die Fallunterscheidung ab. Unter Wayland
laufen beide über XWayland und verhalten sich wie X11.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

# Ein „Rastungsschritt" unter Windows/X11-Tk9; kleinere Beträge (macOS-Trackpad,
# hochauflösende Räder) zählen als ein Schritt.
WHEEL_NOTCH = 120


def windowing_system(widget: tk.Misc) -> str:
    """`"aqua"` (macOS), `"win32"` (Windows) oder `"x11"` (Linux)."""
    try:
        return str(widget.tk.call("tk", "windowingsystem"))
    except tk.TclError:  # pragma: no cover - sollte nie passieren
        return "x11"


def tk_major_version(widget: tk.Misc) -> int:
    try:
        return int(str(widget.tk.call("info", "patchlevel")).split(".")[0])
    except (tk.TclError, ValueError):  # pragma: no cover
        return 8


def uses_legacy_x11_buttons(widget: tk.Misc) -> bool:
    """Braucht diese Umgebung die alten `<Button-4>`/`<Button-5>`-Ereignisse?

    Nur X11 mit Tk 8.x. Ab Tk 9 meldet auch X11 das Rad als `<MouseWheel>`;
    würde man dort beides binden, scrollte die Seite doppelt so weit.
    """
    return windowing_system(widget) == "x11" and tk_major_version(widget) < 9


def wheel_step(event: object) -> int:
    """Ereignis -> Scroll-Schritte (positiv = nach unten), 0 = ignorieren.

    Deckt alle Meldearten ab: X11-Buttons ohne `delta`, Windows-Vielfache von
    120 (mehrere Rastungen in einem Ereignis) und die kleinen macOS-Beträge.
    Ein `delta` von 0 (winzige Trackpad-Bewegung) ergibt 0, sonst spränge die
    Seite ohne Zutun des Nutzers.
    """
    num = getattr(event, "num", None)
    if num == 4:  # X11: Rad nach oben
        return -1
    if num == 5:  # X11: Rad nach unten
        return 1
    delta = getattr(event, "delta", 0) or 0
    if abs(delta) >= WHEEL_NOTCH:
        return -round(delta / WHEEL_NOTCH)
    return 0 if delta == 0 else (-1 if delta > 0 else 1)


def bind_wheel(
    widget: tk.Misc, handler: Callable[[tk.Event], object], *, everywhere: bool = False
) -> list[str]:
    """Bindet `handler` an alle Mausrad-Ereignisse dieser Plattform.

    `everywhere=True` bindet über `bind_all` (für den Seiten-Scroll, der überall
    im Fenster greifen soll), sonst nur an `widget` selbst. Gibt die gebundenen
    Sequenzen zurück (für Tests/Diagnose).
    """
    bind = widget.bind_all if everywhere else widget.bind
    sequences = ["<MouseWheel>"]
    if uses_legacy_x11_buttons(widget):
        sequences += ["<Button-4>", "<Button-5>"]
    for sequence in sequences:
        bind(sequence, handler)
    return sequences
