"""7. Vorschau-Tabelle der zu erzeugenden Karten (docs/SPECIFICATION.md §2)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qslcards.cards.models import Card

_COLUMNS = ("print", "call", "qsos", "via", "date", "utc")
_HEADINGS = {
    "print": "Drucken",
    "call": "Call",
    "qsos": "#QSOs",
    "via": "Via",
    "date": "Datum",
    "utc": "UTC",
}


class PreviewTable:
    """Treeview der Karten; Zeilen per Klick auf die Spalte 'Drucken' abwählbar."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="7. Vorschau (Karten)")
        # height=6 -> immer mindestens ~5 Einträge sichtbar; bei mehr Karten
        # scrollt die Tabelle intern (zusätzlich zum Seiten-Scroll).
        self.tree = ttk.Treeview(self.frame, columns=_COLUMNS, show="headings", height=6)
        for col in _COLUMNS:
            self.tree.heading(col, text=_HEADINGS[col])
            self.tree.column(col, width=70, anchor="center")
        self.tree.column("call", width=90)
        self.tree.column("date", width=90)

        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        # iid -> (Card, included?)
        self._rows: dict[str, tuple[Card, bool]] = {}
        self.tree.bind("<Button-1>", self._on_click)
        # Mausrad über der Tabelle scrollt die Tabelle (nicht die Seite).
        self.tree.bind("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, event: tk.Event) -> str:
        step = -1 if event.delta > 0 else 1
        self.tree.yview_scroll(step, "units")
        return "break"

    def set_cards(self, cards: list[Card]) -> None:
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        for card in cards:
            date = ""
            utc = ""
            if card.rows:
                r = card.rows[0]
                date = f"{r.date_d}.{r.date_m}.{r.date_y}"
                utc = r.utc
            iid = self.tree.insert(
                "",
                "end",
                values=("Ja", card.recipient_call, len(card.rows), card.via_code, date, utc),
            )
            self._rows[iid] = (card, True)

    def included_cards(self) -> list[Card]:
        return [card for (card, inc) in self._rows.values() if inc]

    def _on_click(self, event: tk.Event) -> None:
        # Nur Klicks in die Spalte "Drucken" (Spalte #1) schalten die Zeile um.
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        row = self.tree.identify_row(event.y)
        if not row or row not in self._rows:
            return
        card, inc = self._rows[row]
        inc = not inc
        self._rows[row] = (card, inc)
        values = list(self.tree.item(row, "values"))
        values[0] = "Ja" if inc else "Nein"
        self.tree.item(row, values=values)
