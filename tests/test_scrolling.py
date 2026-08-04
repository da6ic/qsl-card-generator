"""Tests für das plattformübergreifende Mausrad-Handling (`gui/scrolling.py`).

Die Umgebungen lassen sich hier nicht wirklich herstellen, wohl aber die
Ereignisse, die sie liefern — genau die werden nachgebildet: macOS (kleine
`delta`), Windows 32/64 Bit (Vielfache von 120), Linux/X11 mit Tk 9
(`<MouseWheel>` mit ±120) und mit Tk 8.6 (`<Button-4>`/`<Button-5>`).
"""

from __future__ import annotations

import tkinter as tk
from unittest import mock

import pytest

from qslcards.gui import scrolling


class Wheel:
    """Mausrad-Ereignis (tk.Event lässt sich nicht sinnvoll konstruieren)."""

    def __init__(self, delta: int = 0, num: int | str = "??") -> None:
        self.delta = delta
        self.num = num


# -- Schrittweite je Plattform ---------------------------------------------


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (-120, 1),  # eine Rastung nach unten
        (120, -1),  # eine Rastung nach oben
        (-240, 2),  # zwei Rastungen in einem Ereignis
        (360, -3),
        (-60, 1),  # hochauflösendes Rad: Teilschritt zählt als einer
    ],
)
def test_windows_notches(delta, expected):
    """Windows meldet Vielfache von 120 — 32- und 64-Bit-Builds identisch."""
    assert scrolling.wheel_step(Wheel(delta)) == expected


@pytest.mark.parametrize(("delta", "expected"), [(-1, 1), (1, -1), (-3, 1), (7, -1)])
def test_macos_small_deltas(delta, expected):
    """macOS liefert kleine Beträge; entscheidend ist nur die Richtung."""
    assert scrolling.wheel_step(Wheel(delta)) == expected


def test_zero_delta_is_ignored():
    """Winzige Trackpad-Bewegungen (delta 0) dürfen die Seite nicht bewegen."""
    assert scrolling.wheel_step(Wheel(0)) == 0


def test_x11_buttons():
    """Linux mit Tk 8.6: Button 4 = hoch, Button 5 = runter, kein `delta`."""
    assert scrolling.wheel_step(Wheel(num=4)) == -1
    assert scrolling.wheel_step(Wheel(num=5)) == 1


def test_missing_attributes_are_safe():
    """Ein Ereignis ohne delta/num darf nicht zu einer Exception führen."""
    assert scrolling.wheel_step(object()) == 0


# -- Welche Ereignisse gebunden werden -------------------------------------


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"kein Tk-Display: {exc}")
    window.withdraw()
    yield window
    window.destroy()


@pytest.mark.parametrize(
    ("system", "tk_major", "legacy"),
    [
        ("aqua", 9, False),  # macOS
        ("win32", 8, False),  # Windows (Tk 8.6)
        ("win32", 9, False),  # Windows (Tk 9)
        ("x11", 8, True),  # Debian 12: Tk 8.6 -> Button-4/5
        ("x11", 9, False),  # neuere Fedora: Tk 9 -> nur MouseWheel (TIP 474)
    ],
)
def test_legacy_buttons_only_on_old_x11(root, system, tk_major, legacy):
    with (
        mock.patch.object(scrolling, "windowing_system", return_value=system),
        mock.patch.object(scrolling, "tk_major_version", return_value=tk_major),
    ):
        assert scrolling.uses_legacy_x11_buttons(root) is legacy
        bound = scrolling.bind_wheel(tk.Frame(root), lambda _e: None)
    assert ("<Button-4>" in bound) is legacy
    assert "<MouseWheel>" in bound  # überall gebunden


def test_double_scroll_is_impossible_on_tk9_x11(root):
    """Unter Tk 9/X11 dürfen NICHT beide Meldearten gebunden sein — sonst käme
    jede Rastung zweimal an und die Seite spränge doppelt so weit."""
    with (
        mock.patch.object(scrolling, "windowing_system", return_value="x11"),
        mock.patch.object(scrolling, "tk_major_version", return_value=9),
    ):
        bound = scrolling.bind_wheel(tk.Frame(root), lambda _e: None)
    assert bound == ["<MouseWheel>"]


def test_bind_wheel_registers_on_the_widget(root):
    frame = tk.Frame(root)
    scrolling.bind_wheel(frame, lambda _e: None)
    assert "<MouseWheel>" in frame.bind()


def test_bind_wheel_everywhere_uses_bind_all(root):
    frame = tk.Frame(root)
    scrolling.bind_wheel(frame, lambda _e: None, everywhere=True)
    assert frame.bind_all("<MouseWheel>")


def test_environment_probes_are_readable(root):
    """Die Abfragen selbst müssen auf der Testmaschine funktionieren."""
    assert scrolling.windowing_system(root) in ("aqua", "win32", "x11")
    assert scrolling.tk_major_version(root) >= 8


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
