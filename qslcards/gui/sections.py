"""UI-Abschnitte des Hauptfensters (docs/SPECIFICATION.md §2).

Jede Klasse baut ihren LabelFrame und legt Tk-Variablen sowie Buttons offen.
Es steckt KEINE Geschäftslogik hier: Kommandos/Callbacks bindet `app.py`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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

# Druck-Kategorien im Filter (E = Elektronisch ist kein Druckweg -> nicht hier).
VIA_CODES: list[tuple[str, str]] = [
    ("B", "B Büro"),
    ("D", "D Direkt"),
    ("M", "M Manager"),
]

QSL_MARK_CHOICES = ["Leer lassen", "PSE QSL", "TNX QSL"]
PORTABLE_CHOICES = ["Keins", "/p", "/m", "/t", "/r"]
CONFIRM_MARK_CHOICES = ["Leer lassen", "Confirming QSO", "Confirming SWL-Report"]

# Breite der Absender-Textfelder; Dropdowns bekommen dieselbe Breite, damit
# alle Eingabeelemente in Abschnitt 3 gleich lang sind.
SENDER_FIELD_WIDTH = 28

# Maximale Länge des Bemerkungs-/Remarks-Textes (globales Feld UND je Karte in
# der Vorschau). Passt in eine Zeile des Remarks-Kastens auf der Karte.
REMARKS_MAX_LEN = 80


def limit_entry_length(entry: ttk.Entry, max_len: int) -> None:
    """Begrenzt die Eingabelänge eines Entry per Tastatur-Validierung."""
    vcmd = (entry.register(lambda proposed: len(proposed) <= max_len), "%P")
    entry.config(validate="key", validatecommand=vcmd)


class FileSection:
    """1. ADIF-Logbuch."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="1. ADIF-Logbuch")
        self.path_var = tk.StringVar()
        self.count_var = tk.StringVar(value="Keine Datei geladen")

        self.browse_btn = ttk.Button(self.frame, text="Durchsuchen…")
        self.browse_btn.grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Entry(self.frame, textvariable=self.path_var, width=40).grid(
            row=0, column=1, padx=4, pady=4, sticky="we"
        )
        self.load_btn = ttk.Button(self.frame, text="Log laden")
        self.load_btn.grid(row=0, column=2, padx=4, pady=4)
        ttk.Label(self.frame, textvariable=self.count_var).grid(
            row=1, column=0, columnspan=3, padx=4, pady=(0, 4), sticky="w"
        )
        self.frame.columnconfigure(1, weight=1)


class ImageSection:
    """2. Frontbild. Das Vorschaufeld dehnt sich (bündig mit Abschnitt 3),
    das Thumbnail selbst hat eine feste Maximalgröße und ist zentriert."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="2. Frontbild")
        self.path_var = tk.StringVar()

        self.choose_btn = ttk.Button(self.frame, text="Bild wählen…")
        self.choose_btn.grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Entry(self.frame, textvariable=self.path_var, width=32).grid(
            row=0, column=1, padx=4, pady=4, sticky="we"
        )
        # Vorschaufeld füllt den restlichen Platz; das Thumbnail (feste Größe,
        # PhotoImage in app.py gesetzt/gehalten) wird darin zentriert.
        self.thumb_label = ttk.Label(self.frame, text="keine Vorschau", anchor="center")
        self.thumb_label.grid(row=1, column=0, columnspan=2, padx=4, pady=4, sticky="nsew")
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(1, weight=1)


class SenderSection:
    """3. Absender (Config) inkl. globaler Markierungen (QSL/Portabel)."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="3. Absender")
        self.vars: dict[str, tk.StringVar] = {}

        # Stationsdaten (Adresse + Locator/DOK/CQ/ITU).
        row = self._add_fields(STATION_FIELDS, 0)

        ttk.Separator(self.frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="we", padx=4, pady=4
        )
        row += 1

        # Funk-Ausrüstung (Empfänger/Antenne/Leistung): dynamisch auf der Karte.
        row = self._add_fields(RADIO_FIELDS, row)

        ttk.Separator(self.frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="we", padx=4, pady=4
        )
        row += 1

        # Globale Markierungen (gelten für alle Karten).
        ttk.Label(self.frame, text="QSL-Markierung").grid(
            row=row, column=0, padx=4, pady=1, sticky="w"
        )
        self.qsl_mark = tk.StringVar(value=QSL_MARK_CHOICES[0])
        self.qsl_combo = ttk.Combobox(
            self.frame,
            textvariable=self.qsl_mark,
            values=QSL_MARK_CHOICES,
            state="readonly",
            width=SENDER_FIELD_WIDTH,
        )
        self.qsl_combo.grid(row=row, column=1, padx=4, pady=1, sticky="we")
        row += 1

        ttk.Label(self.frame, text="Portabel").grid(row=row, column=0, padx=4, pady=1, sticky="w")
        self.portable = tk.StringVar(value=PORTABLE_CHOICES[0])
        self.portable_combo = ttk.Combobox(
            self.frame,
            textvariable=self.portable,
            values=PORTABLE_CHOICES,
            state="readonly",
            width=SENDER_FIELD_WIDTH,
        )
        self.portable_combo.grid(row=row, column=1, padx=4, pady=1, sticky="we")
        row += 1

        ttk.Label(self.frame, text="Bestätigung").grid(
            row=row, column=0, padx=4, pady=1, sticky="w"
        )
        self.confirm_mark = tk.StringVar(value=CONFIRM_MARK_CHOICES[0])
        self.confirm_combo = ttk.Combobox(
            self.frame,
            textvariable=self.confirm_mark,
            values=CONFIRM_MARK_CHOICES,
            state="readonly",
            width=SENDER_FIELD_WIDTH,
        )
        self.confirm_combo.grid(row=row, column=1, padx=4, pady=1, sticky="we")

        # Kein Speichern/Laden-Button mehr: die Config wird automatisch
        # gespeichert und bei externer Änderung neu geladen.
        self.frame.columnconfigure(1, weight=1)

    def _add_fields(self, fields: list[tuple[str, str]], row: int) -> int:
        """Legt Label+Entry je Feld an (dynamisch dehnbar) und liefert die
        nächste freie Zeile zurück. Die Variablen landen in self.vars."""
        for field, label in fields:
            ttk.Label(self.frame, text=label).grid(row=row, column=0, padx=4, pady=1, sticky="w")
            var = tk.StringVar()
            self.vars[field] = var
            ttk.Entry(self.frame, textvariable=var, width=SENDER_FIELD_WIDTH).grid(
                row=row, column=1, padx=4, pady=1, sticky="we"
            )
            row += 1
        return row


class FilterSection:
    """4. Via-Filter (markiert nur, welche Karten gedruckt werden)."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="4. Via-Filter (Drucken)")
        self.via_vars: dict[str, tk.BooleanVar] = {}

        # command wird in app.py gesetzt (Drucken-Markierung neu setzen).
        self.checkbuttons: list[ttk.Checkbutton] = []
        for i, (code, label) in enumerate(VIA_CODES):
            var = tk.BooleanVar(value=True)
            self.via_vars[code] = var
            cb = ttk.Checkbutton(self.frame, text=label, variable=var)
            cb.grid(row=0, column=i, padx=4, pady=4, sticky="w")
            self.checkbuttons.append(cb)

        ttk.Label(
            self.frame,
            text="Via kommt aus dem Lookup. E (elektronisch) wird nicht gedruckt.",
            foreground="gray",
        ).grid(row=1, column=0, columnspan=3, padx=4, pady=(0, 4), sticky="w")


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
        self.radio_qso.grid(row=0, column=0, padx=4, pady=1, sticky="w")
        self.radio_station.grid(row=1, column=0, padx=4, pady=(1, 4), sticky="w")


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
            ttk.Label(self.frame, text=label).grid(row=i, column=0, padx=4, pady=1, sticky="w")
            ttk.Entry(
                self.frame,
                textvariable=var,
                width=22,
                show="•" if secret else "",
            ).grid(row=i, column=1, padx=4, pady=1, sticky="we")

        ttk.Label(
            self.frame,
            text="Lookup läuft automatisch beim Log-Laden.",
            foreground="gray",
        ).grid(row=4, column=0, columnspan=2, padx=4, pady=1, sticky="w")
        ttk.Checkbutton(
            self.frame,
            text="Adress-/Label-Export erzeugen",
            variable=self.address_export,
        ).grid(row=5, column=0, columnspan=2, padx=4, pady=(1, 4), sticky="w")
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

        ttk.Label(self.frame, text="Text für alle Karten").grid(
            row=0, column=0, padx=4, pady=4, sticky="w"
        )
        self.remarks_entry = ttk.Entry(self.frame, textvariable=self.remarks)
        self.remarks_entry.grid(row=0, column=1, padx=4, pady=4, sticky="we")
        limit_entry_length(self.remarks_entry, REMARKS_MAX_LEN)
        self.frame.columnconfigure(1, weight=1)


class OutputSection:
    """9. Ausgabe."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="9. Ausgabe")
        self.output_var = tk.StringVar(value="qsl_karten.pdf")
        self.status_var = tk.StringVar(value="Bereit")

        self.browse_btn = ttk.Button(self.frame, text="Ziel…")
        self.browse_btn.grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Entry(self.frame, textvariable=self.output_var, width=40).grid(
            row=0, column=1, padx=4, pady=4, sticky="we"
        )
        self.generate_btn = ttk.Button(self.frame, text="PDF erzeugen")
        self.generate_btn.grid(row=0, column=2, padx=4, pady=4)

        self.progress = ttk.Progressbar(self.frame, mode="determinate")
        self.progress.grid(row=1, column=0, columnspan=3, padx=4, pady=2, sticky="we")
        ttk.Label(self.frame, textvariable=self.status_var).grid(
            row=2, column=0, columnspan=3, padx=4, pady=(0, 4), sticky="w"
        )
        self.frame.columnconfigure(1, weight=1)
