"""UI-Abschnitte des Hauptfensters (docs/SPECIFICATION.md §2).

Jede Klasse baut ihren LabelFrame und legt Tk-Variablen sowie Buttons offen.
Es steckt KEINE Geschäftslogik hier: Kommandos/Callbacks bindet `app.py`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Reihenfolge der Absenderfelder (Attributname, Label).
SENDER_FIELDS: list[tuple[str, str]] = [
    ("callsign", "Rufzeichen"),
    ("name", "Name"),
    ("street", "Straße"),
    ("zip", "PLZ"),
    ("city", "Ort"),
    ("country", "Land"),
    ("locator", "Locator"),
    ("dok", "DOK"),
    ("waz", "WAZ"),
    ("itu", "ITU"),
]

# Druck-Kategorien im Filter (E = Elektronisch ist kein Druckweg -> nicht hier).
VIA_CODES: list[tuple[str, str]] = [
    ("B", "B Büro"),
    ("D", "D Direkt"),
    ("M", "M Manager"),
]

QSL_MARK_CHOICES = ["Leer lassen", "PSE QSL", "TNX QSL"]
PORTABLE_CHOICES = ["Keins", "/p", "/m"]


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

        row = 0
        for field, label in SENDER_FIELDS:
            ttk.Label(self.frame, text=label).grid(row=row, column=0, padx=4, pady=1, sticky="w")
            var = tk.StringVar()
            self.vars[field] = var
            ttk.Entry(self.frame, textvariable=var, width=28).grid(
                row=row, column=1, padx=4, pady=1, sticky="we"
            )
            row += 1

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
            width=14,
        )
        self.qsl_combo.grid(row=row, column=1, padx=4, pady=1, sticky="w")
        row += 1

        ttk.Label(self.frame, text="Portabel").grid(row=row, column=0, padx=4, pady=1, sticky="w")
        self.portable = tk.StringVar(value=PORTABLE_CHOICES[0])
        self.portable_combo = ttk.Combobox(
            self.frame,
            textvariable=self.portable,
            values=PORTABLE_CHOICES,
            state="readonly",
            width=14,
        )
        self.portable_combo.grid(row=row, column=1, padx=4, pady=1, sticky="w")

        # Kein Speichern/Laden-Button mehr: die Config wird automatisch
        # gespeichert und bei externer Änderung neu geladen.
        self.frame.columnconfigure(1, weight=1)


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


class OutputSection:
    """8. Ausgabe."""

    def __init__(self, parent: tk.Misc) -> None:
        self.frame = ttk.LabelFrame(parent, text="8. Ausgabe")
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
