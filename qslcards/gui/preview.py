"""7. Vorschau-Tabelle aller Karten/QSOs (docs/SPECIFICATION.md §2, §7).

Zeigt **alle** QSOs (nicht nur die gefilterten). Die Spalte „Via" zeigt die per
Lookup bestimmte Versandart; während der Lookup läuft, steht dort „…". Über die
Spalte „Drucken" werden einzelne Karten ab-/angewählt. Oben rechts ein Button
„Neu abrufen" plus eine Lookup-Statuszeile.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING

from qslcards.cards.builder import effective_via, normalize_station_cards
from qslcards.lookup import VIA_CODES, VIA_LABELS, resolve_route

from .sections import REMARKS_MAX_LEN, limit_entry_length

if TYPE_CHECKING:
    from qslcards.cards.models import Card

_COLUMNS = ("print", "call", "qsos", "via", "route", "remarks", "date", "utc")
_HEADINGS = {
    "print": "Drucken",
    "call": "Call",
    "qsos": "#QSOs",
    "via": "Via",
    "route": "Route/Manager",
    "remarks": "Remarks",
    "date": "Datum",
    "utc": "UTC",
}
_PENDING = "…"  # Platzhalter, solange der Lookup für die Zeile noch läuft
_EDITABLE = ("via", "route", "remarks")  # per Doppelklick editierbare Spalten
# Spalten mit Editier-Hinweis im Kopf (Stift): die editierbaren + „Drucken"
# (Drucken ist per Klick umschaltbar, gilt also auch als bearbeitbar).
_HEADER_HINT = ("print", *_EDITABLE)
_VIA_CHOICES = VIA_CODES  # Auswahl für die Via-Zelle (erzwungener Weg): B/D/Q/L
# Labels für das Via-Dropdown (ausgeschrieben) und Rückabbildung Label -> Code.
_VIA_CHOICE_LABELS = [VIA_LABELS[c] for c in _VIA_CHOICES]
_VIA_LABEL_TO_CODE = {VIA_LABELS[c]: c for c in _VIA_CHOICES}

# Icons (Editier-Hinweise). Tk 9 rendert SVG nativ; `currentColor` wird durch eine
# konkrete Farbe ersetzt, sonst bleibt der Strich evtl. unsichtbar.
_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
_EDIT_ICON_PATH = _ICON_DIR / "edit_icon.svg"  # Stift: Text/Dropdown bearbeiten
_TOGGLE_ICON_PATH = _ICON_DIR / "toggle_icon.svg"  # Schalter: Drucken Ja/Nein
_ICON_COLOR = "#555555"
_ICON_HEIGHT = 13  # Zielhöhe der (Hover-)Icons in px
_HOVER_ICON_PAD = 4  # Abstand des Hover-Icons zum rechten Zellrand (px)
_DEFAULT_HEADER_PX = 28  # Start-Header-Höhe (wird beim ersten set_cards nachgemessen)


def _load_svg_icon(widget: tk.Misc, path: Path) -> tk.PhotoImage | None:
    """Lädt ein SVG als Tk-`PhotoImage` (Tk 9 kann SVG nativ).

    `currentColor` wird durch eine konkrete Farbe ersetzt, sonst bleibt der Strich
    unsichtbar. Jeder Fehler (alte Tk-Version, fehlende Datei) ist nicht fatal —
    dann gibt es eben kein Icon.
    """
    try:
        svg = path.read_text(encoding="utf-8").replace("currentColor", _ICON_COLOR)
        return tk.PhotoImage(master=widget, data=svg, format=f"svg -scaletoheight {_ICON_HEIGHT}")
    except Exception:
        return None


class PreviewTable:
    """Treeview der Karten; Zeilen per Klick auf die Spalte 'Drucken' abwählbar."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="8. Vorschau")

        # Kopfzeile: Lookup-Status links, „Neu abrufen"-Button rechts.
        header = ttk.Frame(self.frame)
        header.grid(row=0, column=0, columnspan=2, sticky="we", padx=4, pady=(2, 0))
        self.status_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.status_var).pack(side="left")
        self.refresh_btn = ttk.Button(header, text="Neu abrufen")
        self.refresh_btn.pack(side="right")

        # Icons laden (als Attribut halten gegen Garbage Collection). Schlägt das
        # Laden fehl (alte Tk-Version, fehlende Datei), bleibt es None und die
        # Hinweise fallen still weg — nie fatal.
        self._edit_icon = _load_svg_icon(self.frame, _EDIT_ICON_PATH)  # Stift
        self._toggle_icon = _load_svg_icon(self.frame, _TOGGLE_ICON_PATH)  # Schalter

        # height=6 -> immer mindestens ~5 Einträge sichtbar; bei mehr Karten
        # scrollt die Tabelle intern (zusätzlich zum Seiten-Scroll).
        self.tree = ttk.Treeview(self.frame, columns=_COLUMNS, show="headings", height=6)
        for col in _COLUMNS:
            self.tree.column(col, width=70, anchor="center")
        self.tree.column("call", width=90)
        self.tree.column("route", width=110)
        self.tree.column("remarks", width=140, anchor="w")
        self.tree.column("date", width=90)
        self._apply_headings()  # nur Spaltentitel; der Stift kommt als Overlay

        self.scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        # yscrollcommand über einen Wrapper: beim Scrollen einen offenen Editor
        # schließen (er würde sonst pixelfest hängen bleiben) und den Hover-Stift
        # verstecken (seine Position wäre veraltet).
        self.tree.configure(yscrollcommand=self._on_yview)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid(row=1, column=1, sticky="ns")
        self.frame.rowconfigure(1, weight=1)
        self.frame.columnconfigure(0, weight=1)

        # ttk zeichnet ein Bild im Spaltenkopf nicht vertikal auf die Textmitte;
        # daher wird der Stift im Kopf als eigenes, randloses Overlay-Label
        # rechtsbündig und vertikal mittig platziert (wie in den Zellen). Höhe des
        # Kopfbereichs wird zur Laufzeit gemessen.
        self._header_px = _DEFAULT_HEADER_PX
        self._header_icons: dict[str, ttk.Label] = {}
        if self._edit_icon is not None:
            for col in _HEADER_HINT:
                self._header_icons[col] = ttk.Label(
                    self.tree, image=self._edit_icon, borderwidth=0, padding=0
                )
        self.tree.bind("<Configure>", lambda _e: self._place_header_icons(), add="+")

        # iid -> (Card, included?)
        self._rows: dict[str, tuple[Card, bool]] = {}
        # Aktive Wege (über der Trennlinie) in Prioritätsreihenfolge; bestimmt den
        # angezeigten „Via"-Weg und die Drucken-Markierung. Von set_cards/
        # apply_via_filter gesetzt (aus der Prioritätsliste in Abschnitt 4).
        self._active_priority: list[str] = []
        self._pending = False  # während des Lookups keine Bearbeitung
        # Ob Karten derselben Station zusammengehören (Modus „pro Station"): dann
        # führt eine Remarks-Änderung die Station neu zusammen/teilt sie neu auf.
        self._groupable = False
        # Callback (von app.py gesetzt): nach einer Zellen-Bearbeitung aufgerufen
        # mit (iid, card, spaltenname) -> z.B. Drucken-Markierung nachziehen.
        self.on_cell_edited: Callable[[str, Card, str], None] | None = None
        # Immer nur EIN Editor gleichzeitig offen (Combobox/Entry über einer Zelle).
        self._editor: tk.Widget | None = None
        # Übernehmen-Callback des offenen Editors (wie „Fokus verloren"): wird beim
        # Scrollen aufgerufen, damit der Editor nicht pixelfest hängen bleibt.
        self._editor_commit: Callable[[], object] | None = None
        # Schwebendes Icon-Label, das beim Hovern rechtsbündig in der Zelle
        # erscheint (Stift für Text/Dropdown, Umschalter für „Drucken"). Merkt sich
        # die zuletzt gehoverte Zelle, damit ein Klick genau diese Zelle bedient.
        self._hover_iid: str | None = None
        self._hover_col: str | None = None
        self._hover_icon: ttk.Label | None = None
        start_icon = self._edit_icon or self._toggle_icon
        if start_icon is not None:
            # randlos (borderwidth/padding=0), sonst sitzt das Icon ~2px zu tief.
            self._hover_icon = ttk.Label(
                self.tree, image=start_icon, borderwidth=0, padding=0, cursor="hand2"
            )
            self._hover_icon.bind("<Button-1>", self._on_hover_icon_click)

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._begin_edit)
        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", self._hide_hover_icon)
        # Mausrad über der Tabelle scrollt die Tabelle (nicht die Seite).
        self.tree.bind("<MouseWheel>", self._on_wheel)

    def _apply_headings(self) -> None:
        """Setzt nur die Spaltentitel (zentriert). Der Stift wird als Overlay
        (`_place_header_icons`) gesetzt, weil ttk ein Header-Bild nicht vertikal
        auf die Textmitte ausrichtet."""
        for col in _COLUMNS:
            self.tree.heading(col, text=_HEADINGS[col], anchor="center")

    def _first_visible_row(self) -> str | None:
        """Erste aktuell sichtbare Zeile (für Spalten-Geometrie), oder None."""
        for iid in self.tree.get_children():
            if self.tree.bbox(iid):
                return iid
        return None

    def _place_header_icons(self) -> None:
        """Platziert die Stift-Overlays im Kopf der bearbeitbaren Spalten:
        rechtsbündig und vertikal mittig. Ohne sichtbare Zeile (Spalten-Geometrie
        nicht bestimmbar) werden sie versteckt."""
        if not self._header_icons:
            return
        icon = self._edit_icon
        ref = self._first_visible_row()
        # Kopfhöhe = y der obersten Zeile, sofern die Tabelle nicht gescrollt ist.
        if ref is not None and self.tree.yview()[0] == 0.0:
            top = self.tree.bbox(ref, "#1")
            if top:
                self._header_px = top[1]
        for col, lbl in self._header_icons.items():
            bbox = self.tree.bbox(ref, f"#{_COLUMNS.index(col) + 1}") if ref else None
            if not bbox or icon is None or self._header_px <= 0:
                lbl.place_forget()
                continue
            x, _y, w, _h = bbox
            px = x + w - icon.width() - _HOVER_ICON_PAD  # rechtsbündig
            py = (self._header_px - icon.height()) // 2  # vertikal mittig im Kopf
            lbl.place(x=px, y=py)

    def _on_wheel(self, event: tk.Event) -> str:
        step = -1 if event.delta > 0 else 1
        self.tree.yview_scroll(step, "units")
        return "break"

    def _on_yview(self, first: str, last: str) -> None:
        """yscrollcommand-Wrapper: hält die Scrollbar synchron und schließt beim
        Scrollen einen offenen Editor (übernimmt wie „Fokus verloren"), damit er
        nicht an alter Pixelposition hängen bleibt; versteckt den Hover-Stift."""
        self.scroll.set(first, last)
        if self._editor_commit is not None:
            self._editor_commit()
        self._hide_hover_icon()

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def set_cards(
        self,
        cards: list[Card],
        *,
        included: Callable[[Card], bool] | None = None,
        pending: bool = False,
        groupable: bool = False,
        active_priority: list[str] | None = None,
    ) -> None:
        """Füllt die Tabelle neu.

        `included(card)` bestimmt die Drucken-Voreinstellung je Karte (None → alle
        drucken). `pending=True` zeigt „…" für Via/Route (Lookup läuft noch).
        `groupable=True` (Modus „pro Station") lässt eine Remarks-Änderung die
        ganze Station neu gruppieren (zusammenführen bzw. aufteilen).
        `active_priority` sind die aktiven Wege (für die „Via"-Anzeige).
        """
        self._pending = pending
        self._groupable = groupable
        if active_priority is not None:
            self._active_priority = active_priority
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        for card in cards:
            inc = True if included is None else bool(included(card))
            self._insert_card(card, inc)
        # Spalten-Geometrie/Kopfhöhe erst jetzt (mit Zeilen) messbar -> Stift-
        # Overlays im Kopf platzieren.
        self.tree.update_idletasks()
        self._place_header_icons()

    def _card_values(self, card: Card, inc: bool) -> tuple:
        """Werte-Tupel einer Baumzeile in Spaltenreihenfolge (_COLUMNS)."""
        date = ""
        utc = ""
        if card.rows:
            r = card.rows[0]
            date = f"{r.date_d}.{r.date_m}.{r.date_y}"
            utc = r.utc
        via = _PENDING if self._pending else self._via_display(card)
        route = _PENDING if self._pending else card.via_text
        return (
            "Ja" if inc else "Nein",
            card.recipient_call,
            len(card.rows),
            via,
            route,
            card.remarks,
            date,
            utc,
        )

    def _insert_card(self, card: Card, inc: bool, index: int | str = "end") -> str:
        iid = self.tree.insert("", index, values=self._card_values(card, inc))
        self._rows[iid] = (card, inc)
        return iid

    def _via_display(self, card: Card) -> str:
        """Anzeigetext der „Via"-Spalte: der Zustellweg **ausgeschrieben**.

        Zeigt den effektiven (zu druckenden) Weg; liegt der Weg unter der Trennlinie
        (Karte wird nicht gedruckt), wird trotzdem der natürliche Weg der Station
        gezeigt (Fallback über die kanonische Reihenfolge, ignoriert die Linie), nie
        ein „—". Ob gedruckt wird, steht in der Spalte „Drucken"."""
        code = (
            card.via_override
            or resolve_route(card.via_routes, self._active_priority)
            or resolve_route(card.via_routes, VIA_CODES)
        )
        if not code:
            return ""
        return VIA_LABELS.get(code, code)

    def apply_via_filter(self, active_priority: list[str]) -> None:
        """Setzt Anzeige + Drucken-Markierung je Zeile neu anhand der aktiven
        Prioritätsliste (Weg über der Trennlinie)."""
        self._active_priority = active_priority
        for iid, (card, _inc) in self._rows.items():
            inc = effective_via(card, active_priority) is not None
            self._rows[iid] = (card, inc)
            values = list(self.tree.item(iid, "values"))
            values[0] = "Ja" if inc else "Nein"
            values[_COLUMNS.index("via")] = self._via_display(card)
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
        """Doppelklick auf eine editierbare Zelle -> Editor über der Zelle."""
        cell = self._cell_at(event.x, event.y, _EDITABLE)
        if cell is None:
            return
        self._begin_edit_cell(*cell)

    def _cell_at(self, x: int, y: int, allowed: tuple[str, ...]) -> tuple[str, str] | None:
        """(iid, Spaltenname) der Zelle an (x, y), sofern die Spalte in `allowed`
        liegt; sonst None. Während des Lookups (`_pending`) immer None."""
        if self._pending:
            return None  # während des Lookups keine Bearbeitung (Zelle zeigt „…")
        if self.tree.identify("region", x, y) != "cell":
            return None
        column = self.tree.identify_column(x)  # z.B. "#4"
        iid = self.tree.identify_row(y)
        if not iid or iid not in self._rows:
            return None
        col_index = int(column[1:]) - 1
        if not 0 <= col_index < len(_COLUMNS):
            return None
        col_name = _COLUMNS[col_index]
        if col_name not in allowed:
            return None
        return iid, col_name

    def _begin_edit_cell(self, iid: str, col_name: str) -> None:
        """Öffnet den Zellen-Editor. Immer nur EIN Editor gleichzeitig offen."""
        self._close_editor()  # evtl. noch offenen Editor schließen
        self._hide_hover_icon()  # während der Bearbeitung keinen Hover-Stift
        column = f"#{_COLUMNS.index(col_name) + 1}"
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            return
        x, y, w, h = bbox
        card, _inc = self._rows[iid]

        if col_name == "via":
            combo = ttk.Combobox(self.tree, values=_VIA_CHOICE_LABELS, state="readonly")
            code = (
                card.via_override
                or resolve_route(card.via_routes, self._active_priority)
                or resolve_route(card.via_routes, VIA_CODES)
            )
            combo.set(VIA_LABELS.get(code, "") if code else "")
            editor: ttk.Entry | ttk.Combobox = combo
        else:  # "route" oder "remarks": freies Textfeld
            editor = ttk.Entry(self.tree)
            editor.insert(0, card.via_text if col_name == "route" else card.remarks)
            if col_name == "remarks":
                limit_entry_length(editor, REMARKS_MAX_LEN)

        editor.place(x=x, y=y, width=w, height=h)
        editor.focus_set()
        self._editor = editor

        done = {"v": False}

        def close(apply: bool) -> None:
            if done["v"]:
                return
            done["v"] = True
            try:
                value = editor.get().strip() if apply else None
            except tk.TclError:
                value = None
            try:
                editor.destroy()
            except tk.TclError:
                pass
            self._editor = None
            self._editor_commit = None
            if value is not None:
                self._commit_edit(iid, col_name, value)

        # "break": verhindert, dass die Klassen-Bindung (_defocus_entry auf TEntry)
        # nach dem Commit noch auf dem zerstörten Editor feuert.
        def commit(_event: tk.Event | None = None) -> str:
            close(apply=True)
            return "break"

        def cancel(_event: tk.Event | None = None) -> str:
            close(apply=False)
            return "break"

        # Wie „Fokus verloren" (übernimmt) — vom Scroll-Wrapper aufgerufen.
        self._editor_commit = lambda: close(apply=True)

        editor.bind("<Return>", commit)
        editor.bind("<Escape>", cancel)
        editor.bind("<FocusOut>", commit)
        if col_name == "via":
            editor.bind("<<ComboboxSelected>>", commit)

    def _close_editor(self) -> None:
        """Schließt einen offenen Editor mit Übernahme (wie „Fokus verloren"),
        z.B. bevor ein neuer Editor geöffnet wird (nur ein Editor gleichzeitig)."""
        if self._editor_commit is not None:
            self._editor_commit()

    def _commit_edit(self, iid: str, col_name: str, value: str) -> None:
        if iid not in self._rows:
            return
        card, _inc = self._rows[iid]
        if col_name == "via":
            # Editor liefert das Label (z.B. „Büro"); ein roher Code (B/D/Q/L) wird
            # ebenfalls akzeptiert (Robustheit / programmatische Aufrufe).
            code = _VIA_LABEL_TO_CODE.get(value)
            if code is None and value.upper() in _VIA_CHOICES:
                code = value.upper()
            if code is None:
                return
            card.via_override = code  # erzwingt diesen Weg für diese Karte
            display = VIA_LABELS[code]
        elif col_name == "remarks":  # REMARKS-Text nur dieser Karte
            card.remarks = value
            display = card.remarks
        else:  # "route" -> Manager-/Routentext auf der Karte
            card.via_text = value
            display = card.via_text

        values = list(self.tree.item(iid, "values"))
        values[_COLUMNS.index(col_name)] = display
        self.tree.item(iid, values=values)

        if self.on_cell_edited is not None:
            self.on_cell_edited(iid, card, col_name)

        # Remarks-Änderung: im Modus „pro Station" die Station neu normalisieren.
        # Remarks sind pro Karte unabhängig — Karten mit Remarks bleiben eigen-
        # ständig, nur aufeinanderfolgende Karten OHNE Remarks führen sich wieder
        # zusammen (siehe normalize_station_cards). So kann man ein Remarks auf
        # genau einer Karte haben, und leert man alle, fallen sie wieder zusammen.
        if col_name == "remarks":
            self._regroup_station(iid)

    def _regroup_station(self, iid: str) -> None:
        if iid not in self._rows or not self._groupable:
            return  # per_qso: 1-Zeilen-Karten, kein Merge/Split nötig
        card, _inc = self._rows[iid]
        key = self._station_key(card)
        # Alle Karten derselben Station (Call + Via) in Baumreihenfolge einsammeln.
        group_iids = [
            i
            for i in self.tree.get_children()
            if i in self._rows and self._station_key(self._rows[i][0]) == key
        ]
        if not group_iids:
            return
        inc = self._rows[group_iids[0]][1]
        station_cards = [self._rows[i][0] for i in group_iids]
        parts = normalize_station_cards(station_cards)

        index = self.tree.index(group_iids[0])
        for i in group_iids:
            self.tree.delete(i)
            del self._rows[i]
        for offset, part in enumerate(parts):
            self._insert_card(part, inc, index + offset)

    @staticmethod
    def _station_key(card: Card) -> str:
        # Gruppierung „pro Station" erfolgt je Rufzeichen (die akzeptierten Wege
        # sind je Call konstant, da sie aus dem Lookup stammen).
        return card.recipient_call

    # -- Hover-Hinweis (schwebendes Icon: Stift bzw. Umschalter) ------------

    def _hover_image(self, col_name: str) -> tk.PhotoImage | None:
        """Icon für die Hover-Zelle: Umschalter für „Drucken", sonst Stift."""
        return self._toggle_icon if col_name == "print" else self._edit_icon

    def _on_motion(self, event: tk.Event) -> None:
        """Zeigt beim Hovern das passende Icon rechtsbündig in der Zelle (Stift für
        Text/Dropdown, Umschalter für „Drucken")."""
        if self._hover_icon is None or self._editor is not None:
            return
        cell = self._cell_at(event.x, event.y, _HEADER_HINT)
        if cell is None:
            self._hide_hover_icon()
            return
        iid, col_name = cell
        if iid == self._hover_iid and col_name == self._hover_col:
            return  # Icon steht bereits an dieser Zelle
        self._show_hover_icon(iid, col_name)

    def _show_hover_icon(self, iid: str, col_name: str) -> None:
        icon = self._hover_image(col_name)
        if self._hover_icon is None or icon is None:
            self._hide_hover_icon()
            return
        column = f"#{_COLUMNS.index(col_name) + 1}"
        bbox = self.tree.bbox(iid, column)
        if not bbox:
            self._hide_hover_icon()
            return
        x, y, w, h = bbox
        px = x + w - icon.width() - _HOVER_ICON_PAD  # rechtsbündig
        py = y + (h - icon.height()) // 2  # vertikal mittig
        self._hover_icon.configure(image=icon)
        self._hover_icon.place(x=px, y=py)
        self._hover_iid = iid
        self._hover_col = col_name

    def _hide_hover_icon(self, event: tk.Event | None = None) -> None:
        if self._hover_icon is None:
            return
        # Zeiger nur auf das Icon selbst gewandert (Leave mit NotifyInferior) ->
        # nicht verstecken, sonst flackert es.
        if event is not None:
            under = self.tree.winfo_containing(event.x_root, event.y_root)
            if under is self._hover_icon:
                return
        self._hover_icon.place_forget()
        self._hover_iid = None
        self._hover_col = None

    def _on_hover_icon_click(self, _event: tk.Event) -> str:
        """Klick aufs Hover-Icon: „Drucken" umschalten bzw. Zelle bearbeiten."""
        iid, col = self._hover_iid, self._hover_col
        if iid is None or col is None:
            return "break"
        if col == "print":
            self._toggle_print(iid)
        else:
            self._begin_edit_cell(iid, col)
        return "break"

    def _on_click(self, event: tk.Event) -> None:
        # Nur Klicks in die Spalte "Drucken" (Spalte #1) schalten die Zeile um.
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        row = self.tree.identify_row(event.y)
        if not row or row not in self._rows:
            return
        self._toggle_print(row)

    def _toggle_print(self, iid: str) -> None:
        """Schaltet die Drucken-Markierung einer Zeile um (Ja/Nein)."""
        if iid not in self._rows:
            return
        card, inc = self._rows[iid]
        inc = not inc
        self._rows[iid] = (card, inc)
        values = list(self.tree.item(iid, "values"))
        values[0] = "Ja" if inc else "Nein"
        self.tree.item(iid, values=values)
