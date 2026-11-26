"""Vertikal scrollbarer Seitenbereich des Assistenten.

Aus `gui/app.py` herausgelöst (Bewertung 3.1). Neu: `set_fill` — Seiten mit
eigenem Scrollbereich (Vorschau) füllen das Fenster, der Außen-Scroll ruht.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .scrolling import bind_wheel, wheel_step


class ScrollableFrame:
    """Vertikal scrollbarer Container (Canvas + inneres Frame + Scrollbar).

    Bei kleinem Fenster kann so der gesamte Inhalt gescrollt werden, nichts wird
    abgeschnitten. `inner` ist das Elternelement für die eigentlichen Abschnitte.
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.outer = ttk.Frame(parent)
        self.canvas = tk.Canvas(self.outer, highlightthickness=0)
        self.vscroll = ttk.Scrollbar(self.outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.vscroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.fill = False
        self._height = 1
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # Mausrad überall im Fenster (bind_all) -> Seite scrollen. Welche
        # Ereignisse die Plattform dafür liefert, entscheidet `bind_wheel`.
        bind_wheel(self.canvas, self._on_mousewheel, everywhere=True)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        # Inneres Frame auf Canvas-Breite ziehen (horizontal füllen).
        self.canvas.itemconfigure(self._window, width=event.width)
        self._height = event.height
        if self.fill:
            self.canvas.itemconfigure(self._window, height=event.height)

    def set_fill(self, fill: bool) -> None:
        """Seite auf genau Fensterhöhe ziehen und den Außen-Scroll abschalten.

        Für Seiten mit eigenem Scrollbereich (Vorschautabelle): zwei
        verschachtelte Scrollbalken ließen sich mit dem Mausrad schlecht
        bedienen (Bewertung 2.5).
        """
        if fill == self.fill:
            return
        self.fill = fill
        if fill:
            self.canvas.itemconfigure(self._window, height=max(1, self._height))
            self.canvas.yview_moveto(0.0)
            self.vscroll.pack_forget()
        else:
            self.canvas.itemconfigure(self._window, height=0)  # 0 = natürliche Höhe
            self.vscroll.pack(side="right", fill="y", before=self.canvas)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Mausrad/Trackpad -> Seite scrollen (Schrittweite siehe `scrolling`)."""
        if self.fill:
            return
        step = wheel_step(event)
        if step:
            self.canvas.yview_scroll(step, "units")
