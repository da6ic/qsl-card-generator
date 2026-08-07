"""UI-Abschnitte des Hauptfensters (docs/SPECIFICATION.md §2).

Jede Klasse baut ihren LabelFrame und legt Tk-Variablen sowie Buttons offen.
Es steckt KEINE Geschäftslogik hier: Kommandos/Callbacks bindet `app.py`.

Farben und Abstände kommen ausschließlich aus `gui/theme.py` (benannte
ttk-Styles + Abstands-Konstanten) — kein Widget setzt hier eine Farbe selbst.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterable
from tkinter import ttk

from qslcards.lookup import (
    PROVIDER_HAMQTH,
    PROVIDER_QRZ,
    VIA_LABELS,
    normalize_via_priority,
)
from qslcards.pdf.geometry import PRINT_MARGIN_MAX, SHEET_MODE_A4_4UP, SHEET_MODE_SINGLE

from .icon_canvas import icon_canvas
from .theme import GAP_COL, GAP_ROW, PAD_INNER, Palette

# Kantenlänge des Icons im „Über"-Dialog (Tk-Punkte).
ABOUT_ICON_SIZE = 64

# Absender-Grunddaten (Adresse + Stationsblock), oben in Abschnitt 3.
STATION_FIELDS: list[tuple[str, str]] = [
    ("callsign", "Rufzeichen"),
    ("name", "Name"),
    ("street", "Straße"),
    ("zip", "PLZ"),
    ("city", "Ort"),
    ("country", "Land"),
    ("locator", "Locator"),
    ("dok", "DOK"),
    ("waz", "CQ-Zone"),
    ("itu", "ITU"),
]

# Funk-Ausrüstung: erscheinen dynamisch auf der Karte (nur der Wert, ohne Label),
# sobald gefüllt. In Abschnitt 3 durch eine Trennlinie von den Stationsdaten
# abgesetzt.
RADIO_FIELDS: list[tuple[str, str]] = [
    ("receiver", "Empfänger"),
    ("antenna", "Antenne"),
    ("power", "Leistung"),
]

# Alle Absenderfelder (Attributname, Label) – für app.py (gather/apply/autosave
# laufen über self.vars, das beide Gruppen enthält).
SENDER_FIELDS: list[tuple[str, str]] = STATION_FIELDS + RADIO_FIELDS

# Feld -> Beschriftung (für Meldungen, z.B. das Pflichtfeld-Popup).
SENDER_LABELS: dict[str, str] = dict(SENDER_FIELDS)

# Pflichtfelder: ohne diese Angaben ist die Karte unbrauchbar, deshalb tragen sie
# in der Oberfläche ein `*` und blockieren leer die PDF-Erzeugung (app._on_generate).
# Adresse (Straße/PLZ/Ort/Land) und Funk-Ausrüstung sind bewusst optional.
REQUIRED_SENDER_FIELDS: tuple[str, ...] = ("callsign", "name", "locator", "dok", "waz", "itu")

# Zeichen hinter der Beschriftung eines Pflichtfeldes.
REQUIRED_MARK = " *"

# Schaltfläche im Abschnittstitel, die das Handbuch beim passenden Kapitel öffnet.
# Mauszeiger: die Hand wie über einem Link. `question_arrow` (der X11-Zeiger mit
# Fragezeichen) war kurz gesetzt und sieht auf macOS unpassend aus — nicht
# zurückdrehen.
SECTION_HELP_MARK = "?"
SECTION_HELP_CURSOR = "hand2"

# Sentinel-Token für die Trennlinie in der Prioritätsliste (Abschnitt 4).
# Alles oberhalb wird gedruckt (in Reihenfolge = Priorität), alles darunter nicht.
VIA_DIVIDER = "\x00divider"
VIA_DIVIDER_LABEL = "──── nicht drucken ────"

# Zugangsdaten-Felder je Anbieter (Abschnitt 6) — welche Felder rot werden,
# wenn dieser Anbieter die Anmeldung ablehnt.
PROVIDER_FIELDS: dict[str, tuple[str, ...]] = {
    PROVIDER_HAMQTH: ("hamqth_user", "hamqth_pass"),
    PROVIDER_QRZ: ("qrz_user", "qrz_pass"),
}

QSL_MARK_CHOICES = ["Leer lassen", "PSE QSL", "TNX QSL"]
PORTABLE_CHOICES = ["Keins", "/p", "/m", "/t", "/r"]
CONFIRM_MARK_CHOICES = ["Leer lassen", "Confirming QSO", "Confirming SWL-Report"]

# Breite der Absender-Textfelder; Dropdowns bekommen dieselbe Breite, damit
# alle Eingabeelemente in Abschnitt 3 gleich lang sind.
SENDER_FIELD_WIDTH = 28

# Maximale Länge des Bemerkungs-/Remarks-Textes (globales Feld UND je Karte in
# der Vorschau). Passt in eine Zeile des Remarks-Kastens auf der Karte.
REMARKS_MAX_LEN = 80

# Statuspunkt der Fußzeile: Stufe -> (Zeichen, ttk-Style des Punktes).
STATUS_LEVELS = {
    "info": ("●", "Status.TLabel"),
    "busy": ("●", "StatusWarning.TLabel"),
    "ok": ("●", "StatusSuccess.TLabel"),
    "error": ("●", "StatusDanger.TLabel"),
}


def limit_entry_length(entry: ttk.Entry, max_len: int) -> None:
    """Begrenzt die Eingabelänge eines Entry per Tastatur-Validierung."""
    vcmd = (entry.register(lambda proposed: len(proposed) <= max_len), "%P")
    entry.config(validate="key", validatecommand=vcmd)


def parse_mm(text: str) -> float:
    """Millimeter-Eingabe aus einem Feld lesen (deutsches Komma erlaubt).

    Leer oder unlesbar -> 0.0; die Obergrenze setzt der Konsument
    (`geometry.clamp_print_margin`)."""
    try:
        return float(text.strip().replace(",", "."))
    except (AttributeError, ValueError):
        return 0.0


def _valid_mm(proposed: str, max_value: float) -> bool:
    """Tastatur-Validierung für ein mm-Feld: leerer Zwischenstand ist erlaubt,
    sonst eine Zahl mit höchstens einem Komma/Punkt innerhalb 0..max_value."""
    if not proposed:
        return True
    text = proposed.replace(",", ".")
    if text.count(".") > 1 or not all(ch.isdigit() or ch == "." for ch in text):
        return False
    if text == ".":
        return True
    return float(text) <= max_value


def limit_entry_number(entry: ttk.Entry | ttk.Spinbox, max_value: float) -> None:
    """Lässt in einem Feld nur mm-Zahlen bis `max_value` zu (siehe _valid_mm)."""
    vcmd = (entry.register(lambda proposed: _valid_mm(proposed, max_value)), "%P")
    entry.config(validate="key", validatecommand=vcmd)


def _center_over(dialog: tk.Toplevel, root: tk.Misc) -> None:
    """Platziert `dialog` mittig über dem Hauptfenster."""
    dialog.update_idletasks()
    px, py = root.winfo_rootx(), root.winfo_rooty()
    pw, ph = root.winfo_width(), root.winfo_height()
    dw, dh = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
    dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")


def ask_overwrite_manual_remarks(parent: tk.Misc) -> bool:
    """Modaler Dialog beim Ändern/Löschen der globalen Bemerkung, wenn Karten
    manuell geänderte Bemerkungen haben.

    Rückgabe: True = überschreiben, False = behalten. Schließen über das
    Fensterkreuz oder Escape zählt als *behalten* (sicherer Default).
    """
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(parent)
    dialog.title("Bemerkungen überschreiben?")
    dialog.transient(root)
    dialog.resizable(False, False)
    result = {"overwrite": False}

    ttk.Label(
        dialog,
        text=(
            "Es gibt Karten mit manuell geänderten Bemerkungen.\n\n"
            "Sollen diese mit der neuen globalen Bemerkung überschrieben werden?"
        ),
        justify="left",
        padding=12,
    ).grid(row=0, column=0, sticky="w")

    def choose(overwrite: bool) -> None:
        result["overwrite"] = overwrite
        dialog.destroy()

    btns = ttk.Frame(dialog, padding=(12, 0, 12, 12))
    btns.grid(row=1, column=0, sticky="e")
    ttk.Button(btns, text="Nicht überschreiben", command=lambda: choose(False)).pack(
        side="left", padx=(0, GAP_COL)
    )
    ttk.Button(
        btns, text="Überschreiben", style="Accent.TButton", command=lambda: choose(True)
    ).pack(side="left")

    dialog.protocol("WM_DELETE_WINDOW", lambda: choose(False))
    dialog.bind("<Escape>", lambda _e: choose(False))

    _center_over(dialog, root)
    dialog.grab_set()
    dialog.wait_window()
    return result["overwrite"]


def show_about_dialog(
    parent: tk.Misc, version: str, palette: Palette, icon_size: int = ABOUT_ICON_SIZE
) -> None:
    """„Über"-Fenster: Icon, Name, Version und die wichtigsten Eckdaten.

    Das Icon wird als Vektor auf einen Canvas gezeichnet statt als PNG geladen:
    Tk skaliert Bitmaps auf Retina-Displays sichtbar hoch (siehe
    `gui/icon_canvas.py`).
    """
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(parent)
    dialog.title("Über QSL-Karten-Generator")
    dialog.transient(root)
    dialog.resizable(False, False)

    body = ttk.Frame(dialog, padding=PAD_INNER * 2)
    body.pack(fill="both", expand=True)

    icon_canvas(body, icon_size, palette.bg).grid(
        row=0, column=0, rowspan=3, padx=(0, PAD_INNER * 2), sticky="n"
    )

    ttk.Label(body, text="QSL-Karten-Generator", style="Heading.TLabel").grid(
        row=0, column=1, sticky="w"
    )
    ttk.Label(body, text=f"Version {version}", style="Muted.TLabel").grid(
        row=1, column=1, sticky="w", pady=(2, PAD_INNER)
    )
    ttk.Label(
        body,
        text=(
            "Erzeugt aus einem ADIF-Logbuch QSL-Karten als PDF\n"
            "(A6, Bild-Vorderseite + Rückseite im DARC-Layout).\n\n"
            "Versandart je Station über HamQTH/QRZ.\n"
            "Absenderdaten aus config.yaml."
        ),
        justify="left",
    ).grid(row=2, column=1, sticky="w")

    btns = ttk.Frame(dialog, padding=(PAD_INNER * 2, 0, PAD_INNER * 2, PAD_INNER * 2))
    btns.pack(fill="x")
    ttk.Button(btns, text="Schließen", style="Accent.TButton", command=dialog.destroy).pack(
        side="right"
    )

    dialog.bind("<Escape>", lambda _e: dialog.destroy())
    _center_over(dialog, root)
    dialog.grab_set()


def confirm(parent: tk.Misc, title: str, message: str, ok_label: str = "OK") -> bool:
    """Schlichter Ja/Nein-Dialog im App-Stil (statt der System-Messagebox)."""
    root = parent.winfo_toplevel()
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(root)
    dialog.resizable(False, False)
    result = {"ok": False}

    ttk.Label(dialog, text=message, justify="left", padding=PAD_INNER * 2).grid(
        row=0, column=0, sticky="w"
    )

    def choose(ok: bool) -> None:
        result["ok"] = ok
        dialog.destroy()

    btns = ttk.Frame(dialog, padding=(PAD_INNER * 2, 0, PAD_INNER * 2, PAD_INNER * 2))
    btns.grid(row=1, column=0, sticky="e")
    ttk.Button(btns, text="Abbrechen", command=lambda: choose(False)).pack(
        side="left", padx=(0, GAP_COL)
    )
    ttk.Button(btns, text=ok_label, style="Accent.TButton", command=lambda: choose(True)).pack(
        side="left"
    )

    dialog.protocol("WM_DELETE_WINDOW", lambda: choose(False))
    dialog.bind("<Escape>", lambda _e: choose(False))
    _center_over(dialog, root)
    dialog.grab_set()
    dialog.wait_window()
    return result["ok"]


def required_section(parent: tk.Misc, caption: str) -> ttk.LabelFrame:
    """LabelFrame eines Pflicht-Abschnitts: Titel mit rotem `*`.

    Der Titel wird als eigenes Widget gesetzt (`labelwidget`), weil ein
    LabelFrame-Titel ein einziger Text ist und sich nicht zweifarbig setzen
    ließe — der Stern soll dieselbe Farbe haben wie in Abschnitt 3.
    """
    frame = ttk.LabelFrame(parent)
    title = ttk.Frame(frame)
    ttk.Label(title, text=caption, style="SectionTitle.TLabel").pack(side="left")
    ttk.Label(title, text=REQUIRED_MARK, style="Required.TLabel").pack(side="left")
    frame.configure(labelwidget=title)
    return frame


def required_legend(parent: tk.Misc) -> ttk.Frame:
    """Fußnote „* Pflichtfeld" für das ganze Fenster (unter allen Abschnitten).

    Der Stern trägt dieselbe Signalfarbe wie an den Feldern selbst (der Text
    daneben bleibt Sekundärtext) — deshalb zwei Labels statt einem.
    """
    holder = ttk.Frame(parent)
    ttk.Label(holder, text=REQUIRED_MARK.strip(), style="Required.TLabel").pack(side="left")
    ttk.Label(holder, text=" Pflichtfeld", style="Muted.TLabel").pack(side="left")
    return holder


class FileSection:
    """1. ADIF-Logbuch (Pflichtangabe).

    Ohne geladenes Log gibt es nichts zu drucken; `set_missing(True)` umrandet
    dann das Pfadfeld rot (wie die Pflichtfelder in Abschnitt 3).
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = required_section(parent, "1. ADIF-Logbuch")
        self.path_var = tk.StringVar()
        self.count_var = tk.StringVar(value="Keine Datei geladen")

        self.browse_btn = ttk.Button(self.frame, text="Durchsuchen…")
        self.browse_btn.grid(row=0, column=0, pady=GAP_ROW, sticky="w")
        self.path_entry = ttk.Entry(self.frame, textvariable=self.path_var, width=40)
        self.path_entry.grid(row=0, column=1, padx=GAP_COL, pady=GAP_ROW, sticky="we")
        self.load_btn = ttk.Button(self.frame, text="Log laden")
        self.load_btn.grid(row=0, column=2, pady=GAP_ROW)
        ttk.Label(self.frame, textvariable=self.count_var, style="Muted.TLabel").grid(
            row=1, column=0, columnspan=3, pady=(GAP_ROW, 0), sticky="w"
        )
        self.frame.columnconfigure(1, weight=1)

    def set_missing(self, missing: bool) -> None:
        """Markiert das fehlende Logbuch (roter Rahmen ums Pfadfeld)."""
        self.path_entry.configure(style="Invalid.TEntry" if missing else "TEntry")


class ImageSection:
    """2. Frontbild (Pflichtangabe). Das Vorschaufeld dehnt sich (bündig mit
    Abschnitt 3), das Thumbnail selbst hat eine feste Maximalgröße und ist
    zentriert.

    Fehlt das Bild beim Druckversuch, färbt `set_missing(True)` den Rahmen des
    Vorschaufeldes — das ist hier die Markierung (ein Eingabefeld, das man rot
    umranden könnte, gibt es nicht).
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = required_section(parent, "2. Frontbild")
        self.path_var = tk.StringVar()

        self.choose_btn = ttk.Button(self.frame, text="Bild wählen…")
        self.choose_btn.grid(row=0, column=0, pady=GAP_ROW, sticky="w")
        ttk.Entry(self.frame, textvariable=self.path_var, width=32).grid(
            row=0, column=1, padx=(GAP_COL, 0), pady=GAP_ROW, sticky="we"
        )
        # Vorschaufeld füllt den restlichen Platz; das Thumbnail (feste Größe,
        # PhotoImage in app.py gesetzt/gehalten) wird darin zentriert.
        self.thumb_label = ttk.Label(
            self.frame, text="keine Vorschau", anchor="center", style="Thumb.TLabel"
        )
        self.thumb_label.grid(row=1, column=0, columnspan=2, pady=(GAP_ROW, 0), sticky="nsew")
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(1, weight=1)

    def set_missing(self, missing: bool) -> None:
        """Markiert das fehlende Frontbild (roter Rahmen) bzw. hebt sie auf."""
        self.thumb_label.configure(style="Invalid.Thumb.TLabel" if missing else "Thumb.TLabel")


class SenderSection:
    """3. Absender (Config) inkl. globaler Markierungen (QSL/Portabel).

    Die Pflichtfelder (`REQUIRED_SENDER_FIELDS`) tragen ein rotes `*`. Bleiben sie
    leer, blockieren sie die PDF-Erzeugung; `mark_missing` umrandet sie dann rot.
    Die Markierung erscheint bewusst erst nach dem Druckversuch — beim ersten
    Start wäre sonst der halbe Abschnitt rot — und verschwindet je Feld wieder,
    sobald etwas darin steht.
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="3. Absender")
        self.vars: dict[str, tk.StringVar] = {}
        self.entries: dict[str, ttk.Entry] = {}
        self._marked: set[str] = set()

        # Stationsdaten (Adresse + Locator/DOK/CQ/ITU).
        row = self._add_fields(STATION_FIELDS, 0)
        # Die Fußnote „* Pflichtfeld" steht bewusst NICHT hier, sondern ganz
        # unten im Fenster (app._build_ui): der Stern kommt auch in den
        # Abschnitten 1 und 2 vor, die Erklärung gilt also für das ganze Fenster.
        row = self._add_separator(row, "Funk-Ausrüstung")

        # Funk-Ausrüstung (Empfänger/Antenne/Leistung): dynamisch auf der Karte.
        row = self._add_fields(RADIO_FIELDS, row)
        row = self._add_separator(row, "Markierungen")

        # Globale Markierungen (gelten für alle Karten).
        self.qsl_mark = tk.StringVar(value=QSL_MARK_CHOICES[0])
        self.qsl_combo = self._add_combo(row, "QSL-Markierung", self.qsl_mark, QSL_MARK_CHOICES)
        row += 1
        self.portable = tk.StringVar(value=PORTABLE_CHOICES[0])
        self.portable_combo = self._add_combo(row, "Portabel", self.portable, PORTABLE_CHOICES)
        row += 1
        self.confirm_mark = tk.StringVar(value=CONFIRM_MARK_CHOICES[0])
        self.confirm_combo = self._add_combo(
            row, "Bestätigung", self.confirm_mark, CONFIRM_MARK_CHOICES
        )

        # Kein Speichern/Laden-Button mehr: die Config wird automatisch
        # gespeichert und bei externer Änderung neu geladen.
        self.frame.columnconfigure(1, weight=1)

    def _add_fields(self, fields: list[tuple[str, str]], row: int) -> int:
        """Legt Label+Entry je Feld an (dynamisch dehnbar) und liefert die
        nächste freie Zeile zurück. Die Variablen landen in self.vars."""
        for field, label in fields:
            self._add_label(field, label).grid(row=row, column=0, pady=GAP_ROW, sticky="w")
            var = tk.StringVar()
            self.vars[field] = var
            entry = ttk.Entry(self.frame, textvariable=var, width=SENDER_FIELD_WIDTH)
            entry.grid(row=row, column=1, padx=(GAP_COL, 0), pady=GAP_ROW, sticky="we")
            self.entries[field] = entry
            if field in REQUIRED_SENDER_FIELDS:
                # Sobald etwas im Feld steht, ist die Markierung erledigt.
                var.trace_add("write", lambda *_a, name=field: self._clear_if_filled(name))
            row += 1
        return row

    def _add_label(self, field: str, label: str) -> ttk.Widget:
        """Beschriftung eines Feldes; Pflichtfelder bekommen einen roten `*`.

        Für den zweifarbigen Text braucht es zwei Labels in einem Frame — ein
        einzelnes Label kann nur eine Vordergrundfarbe.
        """
        if field not in REQUIRED_SENDER_FIELDS:
            return ttk.Label(self.frame, text=label)
        holder = ttk.Frame(self.frame)
        ttk.Label(holder, text=label).pack(side="left")
        ttk.Label(holder, text=REQUIRED_MARK, style="Required.TLabel").pack(side="left")
        return holder

    # -- Pflichtfelder (Prüfung + Markierung) ------------------------------
    def missing_required(self) -> list[str]:
        """Leere Pflichtfelder in Anzeigereihenfolge (Feldnamen)."""
        return [
            f
            for f, _ in STATION_FIELDS
            if f in REQUIRED_SENDER_FIELDS and not self.vars[f].get().strip()
        ]

    def mark_missing(self, fields: list[str]) -> None:
        """Markiert genau `fields` rot und hebt alle anderen Markierungen auf."""
        self.clear_marks()
        for field in fields:
            entry = self.entries.get(field)
            if entry is not None:
                entry.configure(style="Invalid.TEntry")
                self._marked.add(field)

    def clear_marks(self) -> None:
        for field in list(self._marked):
            self._unmark(field)

    def _clear_if_filled(self, field: str) -> None:
        if field in self._marked and self.vars[field].get().strip():
            self._unmark(field)

    def _unmark(self, field: str) -> None:
        self._marked.discard(field)
        entry = self.entries.get(field)
        if entry is not None:
            entry.configure(style="TEntry")

    def _add_separator(self, row: int, caption: str) -> int:
        """Trennlinie mit Beschriftung; gliedert den langen Absender-Block."""
        ttk.Separator(self.frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="we", pady=(PAD_INNER, GAP_ROW)
        )
        ttk.Label(self.frame, text=caption, style="Muted.TLabel").grid(
            row=row + 1, column=0, columnspan=2, pady=(0, GAP_ROW), sticky="w"
        )
        return row + 2

    def _add_combo(
        self, row: int, label: str, var: tk.StringVar, choices: list[str]
    ) -> ttk.Combobox:
        ttk.Label(self.frame, text=label).grid(row=row, column=0, pady=GAP_ROW, sticky="w")
        combo = ttk.Combobox(
            self.frame,
            textvariable=var,
            values=choices,
            state="readonly",
            width=SENDER_FIELD_WIDTH,
        )
        combo.grid(row=row, column=1, padx=(GAP_COL, 0), pady=GAP_ROW, sticky="we")
        return combo


class FilterSection:
    """4. Zustellwege: priorisierbare Liste mit Trennlinie.

    Eine Listbox zeigt die Wege (Büro, Direkt, eQSL, LOTW) in Prioritätsreihenfolge
    plus eine verschiebbare Trennlinie. Wege oberhalb der Linie werden gedruckt
    (der jeweils höchste akzeptierte Weg je Empfänger), Wege darunter nicht. Die
    Buttons ▲/▼ verschieben den ausgewählten Eintrag (Trennlinie eingeschlossen).
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="4. Zustellwege")

        # Modell: Folge von Tokens (Weg-Codes + Trennlinie); die Listbox ist nur
        # die Ansicht. Start: alle Wege, Trennlinie nach den ersten zwei.
        self._tokens: list[str] = normalize_via_priority(None)
        self._tokens.insert(2, VIA_DIVIDER)

        self.listbox = tk.Listbox(
            self.frame, height=5, width=24, exportselection=False, activestyle="none"
        )
        self.listbox.grid(row=0, column=0, rowspan=2, pady=GAP_ROW, sticky="nsew")

        # command wird in app.py gesetzt (verschieben + speichern + Filter neu).
        self.btn_up = ttk.Button(self.frame, text="▲", width=3, style="Icon.TButton")
        self.btn_down = ttk.Button(self.frame, text="▼", width=3, style="Icon.TButton")
        self.btn_up.grid(row=0, column=1, padx=(GAP_COL, 0), pady=(GAP_ROW, 1), sticky="s")
        self.btn_down.grid(row=1, column=1, padx=(GAP_COL, 0), pady=(1, GAP_ROW), sticky="n")

        self.frame.columnconfigure(0, weight=1)
        self._render(select=0)

    # -- Ansicht ----------------------------------------------------------
    def _render(self, select: int | None = None) -> None:
        """Zeichnet die Listbox aus dem Token-Modell; optional Zeile auswählen."""
        self.listbox.delete(0, tk.END)
        for token in self._tokens:
            label = VIA_DIVIDER_LABEL if token == VIA_DIVIDER else VIA_LABELS.get(token, token)
            self.listbox.insert(tk.END, label)
        if select is not None and 0 <= select < len(self._tokens):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(select)
            self.listbox.activate(select)

    def _selected_index(self) -> int | None:
        sel = self.listbox.curselection()
        return int(sel[0]) if sel else None

    # -- Verschieben (von app.py über die Buttons ausgelöst) --------------
    def move_up(self) -> bool:
        return self._move(-1)

    def move_down(self) -> bool:
        return self._move(1)

    def _move(self, delta: int) -> bool:
        i = self._selected_index()
        if i is None:
            return False
        j = i + delta
        if not (0 <= j < len(self._tokens)):
            return False
        self._tokens[i], self._tokens[j] = self._tokens[j], self._tokens[i]
        self._render(select=j)
        return True

    # -- Zustand (für app.py: gather/apply) -------------------------------
    def get_priority(self) -> tuple[list[str], int]:
        """Liefert (Wege in Prioritätsreihenfolge, Trennlinien-Index = via_cut)."""
        codes = [t for t in self._tokens if t != VIA_DIVIDER]
        cut = self._tokens.index(VIA_DIVIDER) if VIA_DIVIDER in self._tokens else len(codes)
        return codes, cut

    def set_priority(self, priority: list[str] | None, cut: int) -> None:
        """Setzt Reihenfolge + Trennlinie (z.B. beim Laden der Config)."""
        codes = normalize_via_priority(priority)
        n = max(0, min(int(cut), len(codes)))
        self._tokens = [*codes[:n], VIA_DIVIDER, *codes[n:]]
        self._render(select=None)


class ModeSection:
    """5. Kartenmodus."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="5. Kartenmodus")
        self.card_mode = tk.StringVar(value="per_qso")

        self.radio_qso = ttk.Radiobutton(
            self.frame, text="Eine Karte pro QSO", variable=self.card_mode, value="per_qso"
        )
        self.radio_station = ttk.Radiobutton(
            self.frame,
            text="Eine Karte pro Station",
            variable=self.card_mode,
            value="per_station",
        )
        self.radio_qso.grid(row=0, column=0, pady=GAP_ROW, sticky="w")
        self.radio_station.grid(row=1, column=0, pady=GAP_ROW, sticky="w")


class LookupSection:
    """6. Lookups (optional).

    Lehnt ein Anbieter die Anmeldung ab, umrandet `mark_auth_failed` sein
    Feldpaar rot — dieselbe Sprache wie bei den Pflichtfeldern in Abschnitt 3.
    Die Markierung geht weg, sobald der Nutzer das Feld ändert.
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="6. Lookups")
        self.hamqth_user = tk.StringVar()
        self.hamqth_pass = tk.StringVar()
        self.qrz_user = tk.StringVar()
        self.qrz_pass = tk.StringVar()
        self.address_export = tk.BooleanVar(value=False)

        self.vars: dict[str, tk.StringVar] = {
            "hamqth_user": self.hamqth_user,
            "hamqth_pass": self.hamqth_pass,
            "qrz_user": self.qrz_user,
            "qrz_pass": self.qrz_pass,
        }
        self.entries: dict[str, ttk.Entry] = {}
        self._marked: set[str] = set()

        rows = [
            ("hamqth_user", "HamQTH Benutzer", False),
            ("hamqth_pass", "HamQTH Passwort", True),
            ("qrz_user", "QRZ Benutzer", False),
            ("qrz_pass", "QRZ Passwort", True),
        ]
        for i, (field, label, secret) in enumerate(rows):
            var = self.vars[field]
            ttk.Label(self.frame, text=label).grid(row=i, column=0, pady=GAP_ROW, sticky="w")
            entry = ttk.Entry(
                self.frame,
                textvariable=var,
                width=22,
                show="•" if secret else "",
            )
            entry.grid(row=i, column=1, padx=(GAP_COL, 0), pady=GAP_ROW, sticky="we")
            self.entries[field] = entry
            var.trace_add("write", lambda *_a, f=field: self._unmark(f))

        ttk.Checkbutton(
            self.frame,
            text="Adress-/Label-Export erzeugen",
            variable=self.address_export,
        ).grid(row=4, column=0, columnspan=2, pady=(PAD_INNER, GAP_ROW), sticky="w")
        self.frame.columnconfigure(1, weight=1)

    def mark_auth_failed(self, providers: Iterable[str]) -> None:
        """Markiert die Felder genau dieser Anbieter rot, alle anderen nicht mehr."""
        for field in list(self._marked):
            self._unmark(field)
        for provider in providers:
            for field in PROVIDER_FIELDS.get(provider, ()):
                entry = self.entries.get(field)
                if entry is not None:
                    entry.configure(style="Invalid.TEntry")
                    self._marked.add(field)

    def _unmark(self, field: str) -> None:
        """Markierung eines Feldes aufheben (auch bei jeder Änderung daran)."""
        if field not in self._marked:
            return
        self._marked.discard(field)
        entry = self.entries.get(field)
        if entry is not None:
            entry.configure(style="TEntry")


class RemarksSection:
    """7. Bemerkungen (Remarks). Globaler Text für ALLE Karten.

    Erscheint dynamisch auf der Rückseite: nur wenn Text gesetzt ist, wird der
    Remarks-Kasten gezeichnet (und die Karte bekommt dann weniger QSO-Zeilen).
    In der Vorschau (Abschnitt 8) lässt sich der Text je Karte überschreiben.
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="7. Bemerkungen")
        self.remarks = tk.StringVar()

        ttk.Label(self.frame, text="Text für alle Karten").grid(row=0, column=0, sticky="w")
        self.remarks_entry = ttk.Entry(self.frame, textvariable=self.remarks)
        self.remarks_entry.grid(row=0, column=1, padx=GAP_COL, sticky="we")
        limit_entry_length(self.remarks_entry, REMARKS_MAX_LEN)

        # Mitlaufender Zähler „geschrieben/erlaubt". Feste Breite und rechts-
        # bündig, damit die Spalte beim Wechsel der Stellenzahl nicht springt.
        self.count_var = tk.StringVar()
        self.count_label = ttk.Label(
            self.frame,
            textvariable=self.count_var,
            style="Muted.TLabel",
            width=len(str(REMARKS_MAX_LEN)) * 2 + 1,
            anchor="e",
        )
        self.count_label.grid(row=0, column=2, sticky="e")
        self.remarks.trace_add("write", lambda *_: self._update_count())
        self._update_count()

        self.frame.columnconfigure(1, weight=1)

    def _update_count(self) -> None:
        """Setzt „x/80" und hebt den Zähler hervor, sobald das Limit erreicht ist.

        Hervorgehoben wird in der Akzentfarbe (nicht in der Warnfarbe): das
        erreichte Limit ist kein Fehler, und Orange fiele im blauen Thema
        unangenehm auf.
        """
        used = len(self.remarks.get())
        self.count_var.set(f"{used}/{REMARKS_MAX_LEN}")
        self.count_label.configure(
            style="Accent.TLabel" if used >= REMARKS_MAX_LEN else "Muted.TLabel"
        )


class PrintModeSection:
    """9. Druckmodus.

    Wählt, wie die PDF(s) erzeugt werden: „duplex" (eine PDF, Vorder-/Rückseite
    abwechselnd, für Duplexdrucker) oder „separate" (zwei PDFs – erst alle
    Vorderseiten, dann alle Rückseiten – für Drucker ohne beidseitigen Druck).

    Quer dazu steht der **Bogendruck** (`sheet_mode`): vier Karten auf einem
    A4-Bogen (quer, 2×2) statt einer je A6-Seite, mit gestrichelten
    Schnitt-Hilfslinien zwischen den Karten. Er lässt sich mit beiden Druckmodi
    kombinieren, deshalb eine Checkbox und kein dritter Radiobutton.

    Unter „Erweiterte Einstellungen" steht der **Druckrand**: viele Drucker
    drucken nicht bis zur Blattkante. Die vier Werte (in mm, je Kante) sagen
    „so viel Rand muss frei bleiben"; die Karte wird dann proportional
    verkleinert, sodass sie hineinpasst (siehe pdf/geometry.page_layout). Im
    Bogenmodus gilt der Rand für den ganzen Bogen (pdf/geometry.sheet_layout).
    """

    # Randfelder in Anzeigereihenfolge: (Attributname, Beschriftung, Zeile, Spalte)
    MARGIN_FIELDS = (
        ("margin_top", "oben", 0, 0),
        ("margin_bottom", "unten", 0, 2),
        ("margin_left", "links", 1, 0),
        ("margin_right", "rechts", 1, 2),
    )

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="9. Druckmodus")
        self.print_mode = tk.StringVar(value="duplex")

        # Zwei nebeneinanderliegende Container: links die Druckmodi, rechts der
        # Umschalter mit dem Randblock. Beide sitzen in Zeile 0 und sind oben
        # verankert — **kein rowspan**: Tk verteilt die Höhe eines übergreifenden
        # Widgets sonst auf die übersprungenen Zeilen, wodurch die Radiobuttons
        # beim Ein-/Ausblenden auseinandergezogen würden.
        self.modes_frame = ttk.Frame(self.frame)
        self.modes_frame.grid(row=0, column=0, sticky="nw")

        self.radio_duplex = ttk.Radiobutton(
            self.modes_frame,
            text="Duplexdruck (Vorder-/Rückseite abwechselnd)",
            variable=self.print_mode,
            value="duplex",
        )
        self.radio_separate = ttk.Radiobutton(
            self.modes_frame,
            text="Vorder-/Rückseite getrennt (2 PDFs)",
            variable=self.print_mode,
            value="separate",
        )
        self.radio_duplex.grid(row=0, column=0, pady=GAP_ROW, sticky="w")
        self.radio_separate.grid(row=1, column=0, pady=GAP_ROW, sticky="w")

        # Bogendruck: quer zu den beiden Druckmodi, deshalb durch eine Trennlinie
        # abgesetzt (sonst läse sich die Checkbox wie eine dritte Modus-Option).
        # Die Variable trägt direkt den Config-Wert (on/off-value), damit app.py
        # nichts umrechnen muss.
        ttk.Separator(self.modes_frame, orient="horizontal").grid(
            row=2, column=0, pady=(PAD_INNER, GAP_ROW), sticky="we"
        )
        self.sheet_mode = tk.StringVar(value=SHEET_MODE_SINGLE)
        self.sheet_check = ttk.Checkbutton(
            self.modes_frame,
            text="4 A6 QSL-Karten auf einem A4-Bogen",
            variable=self.sheet_mode,
            onvalue=SHEET_MODE_A4_4UP,
            offvalue=SHEET_MODE_SINGLE,
        )
        self.sheet_check.grid(row=3, column=0, pady=GAP_ROW, sticky="w")

        # Rechte Spalte: Umschalter oben, darunter der ein-/ausblendbare Block.
        # Ausgeschaltet werden die Werte ignoriert (aber nicht vergessen) ->
        # Ausgabe wie ohne Druckrand.
        self.advanced_frame = ttk.Frame(self.frame)
        self.advanced_frame.grid(row=0, column=1, padx=(PAD_INNER * 3, 0), sticky="nw")

        self.advanced = tk.BooleanVar(value=False)
        self.advanced_check = ttk.Checkbutton(
            self.advanced_frame,
            text="Erweiterte Einstellungen",
            variable=self.advanced,
            command=self.update_advanced_visibility,
        )
        self.advanced_check.grid(row=0, column=0, pady=GAP_ROW, sticky="w")

        self.margin_frame = ttk.Frame(self.advanced_frame)
        ttk.Label(self.margin_frame, text="Seitenrand (mm)").grid(
            row=0, column=0, columnspan=4, pady=(0, GAP_ROW), sticky="w"
        )
        self.margin_vars: dict[str, tk.StringVar] = {}
        for name, label, row, col in self.MARGIN_FIELDS:
            var = tk.StringVar(value="0")
            self.margin_vars[name] = var
            setattr(self, name, var)
            ttk.Label(self.margin_frame, text=label).grid(
                row=row + 1, column=col, padx=(0, GAP_COL), pady=GAP_ROW, sticky="w"
            )
            spin = ttk.Spinbox(
                self.margin_frame,
                textvariable=var,
                from_=0,
                to=PRINT_MARGIN_MAX,
                increment=0.5,
                width=6,
            )
            spin.grid(row=row + 1, column=col + 1, padx=(0, GAP_COL * 2), pady=GAP_ROW, sticky="w")
            limit_entry_number(spin, PRINT_MARGIN_MAX)

        self._reserve_margin_space()
        self.update_advanced_visibility()

    def _reserve_margin_space(self) -> None:
        """Hält den Platz des Randblocks dauerhaft frei.

        Sonst wächst der Abschnitt beim Aufklappen und schiebt alles darunter
        (Ausgabe, Fortschritt) nach unten — das Fenster „springt", nur weil
        Optionen sichtbar werden. Die Höhe wird einmal am eingeblendeten Block
        gemessen; `update_idletasks` ist nötig, weil `grid` die angeforderte
        Größe erst im Leerlauf berechnet.
        """
        self.margin_frame.grid(row=1, column=0, pady=(PAD_INNER, 0), sticky="w")
        self.frame.update_idletasks()
        self.advanced_frame.rowconfigure(1, minsize=self.margin_frame.winfo_reqheight() + PAD_INNER)

    def update_advanced_visibility(self) -> None:
        """Randblock unter dem Umschalter ein-/ausblenden.

        Er liegt in der rechten Spalte unter der Checkbox; sein Platz bleibt in
        beiden Zuständen reserviert (`_reserve_margin_space`), damit nichts
        verrutscht."""
        if self.advanced.get():
            self.margin_frame.grid(row=1, column=0, pady=(PAD_INNER, 0), sticky="w")
        else:
            self.margin_frame.grid_remove()


class OutputSection:
    """10. Ausgabe. Der Status steht in der Fußzeile (`StatusBar`)."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="10. Ausgabe")
        self.output_var = tk.StringVar(value="qsl_karten.pdf")

        self.browse_btn = ttk.Button(self.frame, text="Ziel…")
        self.browse_btn.grid(row=0, column=0, pady=GAP_ROW, sticky="w")
        ttk.Entry(self.frame, textvariable=self.output_var, width=40).grid(
            row=0, column=1, padx=GAP_COL, pady=GAP_ROW, sticky="we"
        )
        self.generate_btn = ttk.Button(self.frame, text="PDF erzeugen", style="Accent.TButton")
        self.generate_btn.grid(row=0, column=2, pady=GAP_ROW)

        self.progress = ttk.Progressbar(self.frame, mode="determinate")
        self.progress.grid(row=1, column=0, columnspan=3, pady=(GAP_ROW, 0), sticky="we")
        self.frame.columnconfigure(1, weight=1)


class StatusBar:
    """Fußzeile des Fensters: Statuspunkt + Meldung links, Kurzinfo rechts.

    Ersetzt die frühere Statuszeile in Abschnitt 10 — der Status ist damit immer
    sichtbar, auch wenn die Seite gescrollt ist.
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.Frame(parent, style="Status.TFrame", padding=(PAD_INNER, 4))
        self.status_var = tk.StringVar(value="Bereit")
        self.info_var = tk.StringVar(value="")

        self.dot = ttk.Label(self.frame, text="●", style="Status.TLabel")
        self.dot.pack(side="left", padx=(0, GAP_COL))
        ttk.Label(self.frame, textvariable=self.status_var, style="StatusAccent.TLabel").pack(
            side="left"
        )
        ttk.Label(self.frame, textvariable=self.info_var, style="Status.TLabel").pack(side="right")

    def set(self, text: str, level: str = "info") -> None:
        """Setzt Meldung + Farbe des Punktes (`info`/`busy`/`ok`/`error`)."""
        symbol, style = STATUS_LEVELS.get(level, STATUS_LEVELS["info"])
        self.status_var.set(text)
        self.dot.configure(text=symbol, style=style)

    def set_info(self, text: str) -> None:
        self.info_var.set(text)


def add_section_help(frame: ttk.LabelFrame, command: Callable[[], None]) -> ttk.Label:
    """Hängt ein kleines „?" an den Titel eines Abschnitts (öffnet das Handbuch).

    Deckt beide Bauweisen ab: Abschnitte mit `text=` bekommen dafür ein
    `labelwidget` (ihr Titel wandert in ein Label), die Pflicht-Abschnitte aus
    `required_section` haben schon eines und werden nur ergänzt. Deshalb muss
    kein einziger Abschnitts-Konstruktor davon wissen — `app.py` hängt das „?"
    zentral an alle Rahmen.
    """
    existing = str(frame.cget("labelwidget"))
    if existing:
        holder = frame.nametowidget(existing)
    else:
        holder = ttk.Frame(frame)
        ttk.Label(holder, text=frame.cget("text"), style="SectionTitle.TLabel").pack(side="left")
        frame.configure(text="", labelwidget=holder)

    mark = ttk.Label(
        holder, text=SECTION_HELP_MARK, style="SectionHelp.TLabel", cursor=SECTION_HELP_CURSOR
    )
    mark.pack(side="left", padx=(GAP_COL, 0))
    mark.bind("<Button-1>", lambda _e: command())
    mark.bind("<Enter>", lambda _e: mark.configure(style="SectionHelpHover.TLabel"))
    mark.bind("<Leave>", lambda _e: mark.configure(style="SectionHelp.TLabel"))
    return mark
