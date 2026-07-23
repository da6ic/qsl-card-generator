"""7. Vorschau-Tabelle aller Karten/QSOs (docs/SPECIFICATION.md §2, §7).

Zeigt **alle** QSOs (nicht nur die gefilterten). Die Spalte „Via" zeigt die per
Lookup bestimmte Versandart; während der Lookup läuft, steht dort „…". Über die
Spalte „Drucken" werden einzelne Karten ab-/angewählt. Oben rechts ein Button
„Neu abrufen" plus eine Lookup-Statuszeile.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qslcards.cards.models import Card

_COLUMNS = ("print", "call", "qsos", "via", "route", "date", "utc")
_HEADINGS = {
    "print": "Drucken",
    "call": "Call",
    "qsos": "#QSOs",
    "via": "Via",
    "route": "Route/Manager",
    "date": "Datum",
    "utc": "UTC",
}
_PENDING = "…"  # Platzhalter, solange der Lookup für die Zeile noch läuft
_EDITABLE = ("via", "route")  # per Doppelklick editierbare Spalten
_VIA_CHOICES = ("B", "D", "M", "E")  # Auswahl für die Via-Zelle


class PreviewTable:
    """Treeview der Karten; Zeilen per Klick auf die Spalte 'Drucken' abwählbar."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="7. Vorschau")

        # Kopfzeile: Lookup-Status links, „Neu abrufen"-Button rechts.
        header = ttk.Frame(self.frame)
        header.grid(row=0, column=0, columnspan=2, sticky="we", padx=4, pady=(2, 0))
        self.status_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.status_var).pack(side="left")
        self.refresh_btn = ttk.Button(header, text="Neu abrufen")
        self.refresh_btn.pack(side="right")

        # height=6 -> immer mindestens ~5 Einträge sichtbar; bei mehr Karten
        # scrollt die Tabelle intern (zusätzlich zum Seiten-Scroll).
        self.tree = ttk.Treeview(self.frame, columns=_COLUMNS, show="headings", height=6)
        for col in _COLUMNS:
            self.tree.heading(col, text=_HEADINGS[col])
            self.tree.column(col, width=70, anchor="center")
        self.tree.column("call", width=90)
        self.tree.column("route", width=110)
        self.tree.column("date", width=90)

        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        self.frame.rowconfigure(1, weight=1)
        self.frame.columnconfigure(0, weight=1)

        # iid -> (Card, included?)
        self._rows: dict[str, tuple[Card, bool]] = {}
        self._pending = False  # während des Lookups keine Bearbeitung
        # Callback (von app.py gesetzt): nach einer Zellen-Bearbeitung aufgerufen
        # mit (iid, card, spaltenname) -> z.B. Drucken-Markierung nachziehen.
        self.on_cell_edited: Callable[[str, Card, str], None] | None = None

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._begin_edit)
        # Mausrad über der Tabelle scrollt die Tabelle (nicht die Seite).
        self.tree.bind("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, event: tk.Event) -> str:
        step = -1 if event.delta > 0 else 1
        self.tree.yview_scroll(step, "units")
        return "break"

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def set_cards(
        self,
        cards: list[Card],
        *,
        included: Callable[[Card], bool] | None = None,
        pending: bool = False,
    ) -> None:
        """Füllt die Tabelle neu.

        `included(card)` bestimmt die Drucken-Voreinstellung je Karte (None → alle
        drucken). `pending=True` zeigt „…" für Via/Route (Lookup läuft noch).
        """
        self._pending = pending
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        for card in cards:
            inc = True if included is None else bool(included(card))
            date = ""
            utc = ""
            if card.rows:
                r = card.rows[0]
                date = f"{r.date_d}.{r.date_m}.{r.date_y}"
                utc = r.utc
            via = _PENDING if pending else card.via_code
            route = _PENDING if pending else card.via_text
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    "Ja" if inc else "Nein",
                    card.recipient_call,
                    len(card.rows),
                    via,
                    route,
                    date,
                    utc,
                ),
            )
            self._rows[iid] = (card, inc)

    def apply_via_filter(self, via_codes: set[str]) -> None:
        """Setzt die Drucken-Markierung je Zeile neu: `via_code ∈ via_codes`."""
        for iid, (card, _inc) in self._rows.items():
            inc = card.via_code in via_codes
            self._rows[iid] = (card, inc)
            values = list(self.tree.item(iid, "values"))
            values[0] = "Ja" if inc else "Nein"
            self.tree.item(iid, values=values)

    def set_row_included(self, iid: str, included: bool) -> None:
        """Setzt die Drucken-Markierung einer einzelnen Zeile (z.B. nach Via-Edit)."""
        if iid not in self._rows:
            return
        card, _inc = self._rows[iid]
        self._rows[iid] = (card, included)
        values = list(self.tree.item(iid, "values"))
        values[0] = "Ja" if included else "Nein"
        self.tree.item(iid, values=values)

    def included_cards(self) -> list[Card]:
        return [card for (card, inc) in self._rows.values() if inc]

    # -- Inline-Bearbeitung (Via / Route-Manager) --------------------------

    def _begin_edit(self, event: tk.Event) -> None:
        """Doppelklick auf die Via- oder Route-Zelle -> Editor über der Zelle."""
        if self._pending:
            return  # während des Lookups nicht editieren (Zelle zeigt „…")
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        column = self.tree.identify_column(event.x)  # z.B. "#4"
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self._rows:
            return
        col_index = int(column[1:]) - 1
        if not 0 <= col_index < len(_COLUMNS):
            return
        col_name = _COLUMNS[col_index]
        if col_name not in _EDITABLE:
            return
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return
        x, y, w, h = bbox
        card, _inc = self._rows[iid]

        if col_name == "via":
            editor: ttk.Entry | ttk.Combobox = ttk.Combobox(
                self.tree, values=list(_VIA_CHOICES), state="readonly"
            )
            editor.set(card.via_code)
        else:  # "route"
            editor = ttk.Entry(self.tree)
            editor.insert(0, card.via_text)

        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()

        done = {"v": False}

        def commit(_event: tk.Event | None = None) -> str:
            # "break": verhindert, dass die Klassen-Bindung (_defocus_entry auf
            # TEntry) nach dem Commit noch auf dem zerstörten Editor feuert.
            if done["v"]:
                return "break"
            done["v"] = True
            try:
                value = editor.get().strip()
            except tk.TclError:
                return "break"
            editor.destroy()
            self._commit_edit(iid, col_name, value)
            return "break"

        def cancel(_event: tk.Event | None = None) -> str:
            done["v"] = True
            editor.destroy()
            return "break"

        editor.bind("<Return>", commit)
        editor.bind("<Escape>", cancel)
        if col_name == "via":
            editor.bind("<<ComboboxSelected>>", commit)
        else:
            editor.bind("<FocusOut>", commit)

    def _commit_edit(self, iid: str, col_name: str, value: str) -> None:
        if iid not in self._rows:
            return
        card, _inc = self._rows[iid]
        if col_name == "via":
            value = value.upper()
            if value not in _VIA_CHOICES:
                return
            card.via_code = value
            display = card.via_code
        else:  # "route" -> Manager-/Routentext auf der Karte
            card.via_text = value
            display = card.via_text

        values = list(self.tree.item(iid, "values"))
        values[_COLUMNS.index(col_name)] = display
        self.tree.item(iid, values=values)

        if self.on_cell_edited is not None:
            self.on_cell_edited(iid, card, col_name)

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
