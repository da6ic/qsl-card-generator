"""UI-Abschnitte des Hauptfensters (docs/SPECIFICATION.md §2).

Jede Klasse baut ihren LabelFrame und legt Tk-Variablen sowie Buttons offen.
Es steckt KEINE Geschäftslogik hier: Kommandos/Callbacks bindet `app.py`.

Farben und Abstände kommen ausschließlich aus `gui/theme.py` (benannte
ttk-Styles + Abstands-Konstanten) — kein Widget setzt hier eine Farbe selbst.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from qslcards.lookup import VIA_LABELS, normalize_via_priority

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

# Sentinel-Token für die Trennlinie in der Prioritätsliste (Abschnitt 4).
# Alles oberhalb wird gedruckt (in Reihenfolge = Priorität), alles darunter nicht.
VIA_DIVIDER = "\x00divider"
VIA_DIVIDER_LABEL = "──── nicht drucken ────"

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


class FileSection:
    """1. ADIF-Logbuch."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="1. ADIF-Logbuch")
        self.path_var = tk.StringVar()
        self.count_var = tk.StringVar(value="Keine Datei geladen")

        self.browse_btn = ttk.Button(self.frame, text="Durchsuchen…")
        self.browse_btn.grid(row=0, column=0, pady=GAP_ROW, sticky="w")
        ttk.Entry(self.frame, textvariable=self.path_var, width=40).grid(
            row=0, column=1, padx=GAP_COL, pady=GAP_ROW, sticky="we"
        )
        self.load_btn = ttk.Button(self.frame, text="Log laden")
        self.load_btn.grid(row=0, column=2, pady=GAP_ROW)
        ttk.Label(self.frame, textvariable=self.count_var, style="Muted.TLabel").grid(
            row=1, column=0, columnspan=3, pady=(GAP_ROW, 0), sticky="w"
        )
        self.frame.columnconfigure(1, weight=1)


class ImageSection:
    """2. Frontbild. Das Vorschaufeld dehnt sich (bündig mit Abschnitt 3),
    das Thumbnail selbst hat eine feste Maximalgröße und ist zentriert."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="2. Frontbild")
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


class SenderSection:
    """3. Absender (Config) inkl. globaler Markierungen (QSL/Portabel)."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="3. Absender")
        self.vars: dict[str, tk.StringVar] = {}

        # Stationsdaten (Adresse + Locator/DOK/CQ/ITU).
        row = self._add_fields(STATION_FIELDS, 0)
        row = self._add_separator(row, "Funk-Ausrüstung (optional)")

        # Funk-Ausrüstung (Empfänger/Antenne/Leistung): dynamisch auf der Karte.
        row = self._add_fields(RADIO_FIELDS, row)
        row = self._add_separator(row, "Markierungen (für alle Karten)")

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
            ttk.Label(self.frame, text=label).grid(row=row, column=0, pady=GAP_ROW, sticky="w")
            var = tk.StringVar()
            self.vars[field] = var
            ttk.Entry(self.frame, textvariable=var, width=SENDER_FIELD_WIDTH).grid(
                row=row, column=1, padx=(GAP_COL, 0), pady=GAP_ROW, sticky="we"
            )
            row += 1
        return row

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

        ttk.Label(
            self.frame,
            text="Über der Linie = wird gedruckt (oben = höchste Priorität).",
            style="Muted.TLabel",
            wraplength=260,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, pady=(GAP_ROW, 0), sticky="w")

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
    """6. Lookups (optional)."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="6. Lookups")
        self.hamqth_user = tk.StringVar()
        self.hamqth_pass = tk.StringVar()
        self.qrz_user = tk.StringVar()
        self.qrz_pass = tk.StringVar()
        self.address_export = tk.BooleanVar(value=False)

        rows = [
            ("HamQTH Benutzer", self.hamqth_user, False),
            ("HamQTH Passwort", self.hamqth_pass, True),
            ("QRZ Benutzer", self.qrz_user, False),
            ("QRZ Passwort", self.qrz_pass, True),
        ]
        for i, (label, var, secret) in enumerate(rows):
            ttk.Label(self.frame, text=label).grid(row=i, column=0, pady=GAP_ROW, sticky="w")
            ttk.Entry(
                self.frame,
                textvariable=var,
                width=22,
                show="•" if secret else "",
            ).grid(row=i, column=1, padx=(GAP_COL, 0), pady=GAP_ROW, sticky="we")

        ttk.Checkbutton(
            self.frame,
            text="Adress-/Label-Export erzeugen",
            variable=self.address_export,
        ).grid(row=4, column=0, columnspan=2, pady=(PAD_INNER, GAP_ROW), sticky="w")
        ttk.Label(
            self.frame,
            text="Ohne Zugangsdaten: kein Netzzugriff, alle Wege = Standard.",
            style="Muted.TLabel",
            wraplength=300,
            justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w")
        self.frame.columnconfigure(1, weight=1)


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
    """

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="9. Druckmodus")
        self.print_mode = tk.StringVar(value="duplex")

        self.radio_duplex = ttk.Radiobutton(
            self.frame,
            text="Duplexdruck (Vorder-/Rückseite abwechselnd)",
            variable=self.print_mode,
            value="duplex",
        )
        self.radio_separate = ttk.Radiobutton(
            self.frame,
            text="Vorder-/Rückseite getrennt (2 PDFs)",
            variable=self.print_mode,
            value="separate",
        )
        self.radio_duplex.grid(row=0, column=0, pady=GAP_ROW, sticky="w")
        self.radio_separate.grid(row=1, column=0, pady=GAP_ROW, sticky="w")


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


def project_root() -> Path:
    """Wurzel des Projekts (enthält README.md/docs/) — für Menü „Dokumentation"."""
    return Path(__file__).resolve().parent.parent.parent
