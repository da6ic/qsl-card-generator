"""Hauptfenster: verdrahtet die Abschnitte mit config/builder/generator.

Keine Geschäftslogik hier — die GUI ruft nur die fertigen Bausteine auf.
Langlaufende Arbeit (PDF-Erzeugung) läuft im Worker-Thread; UI-Updates
ausschließlich über `self.after(...)` (Tkinter ist nicht thread-safe).
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from qslcards import config as cfg
from qslcards.adif.parser import parse_file
from qslcards.cards.builder import build_cards
from qslcards.config import AppConfig, GenerationConfig, LookupConfig, SenderConfig
from qslcards.pdf.generator import generate

from .preview import PreviewTable
from .sections import (
    SENDER_FIELDS,
    FileSection,
    FilterSection,
    ImageSection,
    LookupSection,
    ModeSection,
    OutputSection,
    SenderSection,
)

CONFIG_PATH = "config.yaml"
EXAMPLE_CONFIG_PATH = "config.example.yaml"

IMAGE_TYPES = [("Bilder", "*.png *.jpg *.jpeg *.webp"), ("Alle Dateien", "*.*")]
ADIF_TYPES = [("ADIF-Logbuch", "*.adi *.adif"), ("Alle Dateien", "*.*")]

# Display <-> Code-Mappings der Dropdowns.
QSL_MARK_TO_CODE = {"Leer lassen": "none", "PSE QSL": "pse", "TNX QSL": "tnx"}
QSL_CODE_TO_DISPLAY = {v: k for k, v in QSL_MARK_TO_CODE.items()}
PORTABLE_TO_CODE = {"Keins": "none", "/p": "p", "/m": "m"}
PORTABLE_CODE_TO_DISPLAY = {v: k for k, v in PORTABLE_TO_CODE.items()}

THUMB_MAX = (220, 160)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("QSL-Karten-Generator")

        # Zustand
        self.qsos: list = []
        self._thumb: ImageTk.PhotoImage | None = None
        # Basis-Config für Felder, die nicht in der GUI editierbar sind
        # (default_via, static_footer, program_id, page_orientation).
        self.base_config: AppConfig = AppConfig()

        self._build_ui()
        self._wire_commands()
        self._load_initial_config()

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        # Linke Spalte: ADIF (fix) + Frontbild (dehnt sich bis zur Unterkante
        # der Absender-Config in der rechten Spalte).
        self._left = ttk.Frame(self)
        self.file_section = FileSection(self._left)
        self.image_section = ImageSection(self._left)
        self.file_section.frame.pack(side="top", fill="x")
        self.image_section.frame.pack(side="top", fill="both", expand=True, pady=(8, 0))

        self.sender_section = SenderSection(self)
        self.filter_section = FilterSection(self)
        self.mode_section = ModeSection(self)
        self.lookup_section = LookupSection(self)
        self.preview = PreviewTable(self)
        self.output_section = OutputSection(self)

        self._left.grid(row=0, column=0, padx=6, pady=4, sticky="nsew")
        self.sender_section.frame.grid(row=0, column=1, padx=6, pady=4, sticky="nsew")

        self.filter_section.frame.grid(row=1, column=0, padx=6, pady=4, sticky="nwe")
        self.lookup_section.frame.grid(row=1, column=1, padx=6, pady=4, sticky="nwe")
        self.mode_section.frame.grid(row=2, column=0, padx=6, pady=4, sticky="nwe")

        self.preview.frame.grid(row=3, column=0, columnspan=2, padx=6, pady=4, sticky="nsew")
        self.output_section.frame.grid(row=4, column=0, columnspan=2, padx=6, pady=4, sticky="we")

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        # Nur die Vorschau bekommt Extra-Höhe -> Zeile 0 bleibt auf natürlicher
        # (Absender-)Höhe, sodass die Bild-Vorschau bündig damit abschließt.
        self.rowconfigure(3, weight=1)

    def _wire_commands(self) -> None:
        self.file_section.browse_btn.config(command=self._browse_log)
        self.file_section.load_btn.config(command=self._load_log)
        self.image_section.choose_btn.config(command=self._choose_image)
        self.sender_section.save_btn.config(command=self._save_config)
        self.sender_section.load_btn.config(command=self._load_config)
        self.output_section.browse_btn.config(command=self._browse_output)
        self.output_section.generate_btn.config(command=self._on_generate)

        # Vorschau automatisch neu aufbauen, wenn Filter/Modus/Markierungen sich
        # ändern (die Markierungen fließen in build_cards ein).
        for cb in self.filter_section.checkbuttons:
            cb.config(command=self._rebuild_cards)
        self.filter_section.include_cb.config(command=self._rebuild_cards)
        self.mode_section.radio_qso.config(command=self._rebuild_cards)
        self.mode_section.radio_station.config(command=self._rebuild_cards)
        self.sender_section.qsl_combo.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_cards())
        self.sender_section.portable_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._rebuild_cards()
        )

    # ----------------------------------------------------------- Config
    def _load_initial_config(self) -> None:
        for path in (CONFIG_PATH, EXAMPLE_CONFIG_PATH):
            if Path(path).exists():
                self.base_config = cfg.load(path)
                break
        self._apply_config_to_widgets(self.base_config)

    def _apply_config_to_widgets(self, config: AppConfig) -> None:
        for field, _ in SENDER_FIELDS:
            self.sender_section.vars[field].set(getattr(config.sender, field))

        self.lookup_section.hamqth_user.set(config.lookup.hamqth_user)
        self.lookup_section.hamqth_pass.set(config.lookup.hamqth_pass)
        self.lookup_section.qrz_user.set(config.lookup.qrz_user)
        self.lookup_section.qrz_pass.set(config.lookup.qrz_pass)
        self.lookup_section.lookup_addresses.set(config.lookup.lookup_addresses)
        self.lookup_section.address_export.set(config.lookup.address_export)

        for code, var in self.filter_section.via_vars.items():
            var.set(code in config.generation.via_filter)
        self.filter_section.include_missing.set(config.generation.include_missing_via)
        self.mode_section.card_mode.set(config.generation.card_mode)
        self.sender_section.qsl_mark.set(
            QSL_CODE_TO_DISPLAY.get(config.generation.qsl_mark, "Leer lassen")
        )
        self.sender_section.portable.set(
            PORTABLE_CODE_TO_DISPLAY.get(config.generation.portable_mark, "Keins")
        )

    def _gather_config(self) -> AppConfig:
        sender = SenderConfig(
            **{field: self.sender_section.vars[field].get() for field, _ in SENDER_FIELDS}
        )
        lookup = LookupConfig(
            hamqth_user=self.lookup_section.hamqth_user.get(),
            hamqth_pass=self.lookup_section.hamqth_pass.get(),
            qrz_user=self.lookup_section.qrz_user.get(),
            qrz_pass=self.lookup_section.qrz_pass.get(),
            program_id=self.base_config.lookup.program_id,
            lookup_addresses=self.lookup_section.lookup_addresses.get(),
            address_export=self.lookup_section.address_export.get(),
        )
        via_filter = [c for c, v in self.filter_section.via_vars.items() if v.get()]
        generation = GenerationConfig(
            card_mode=self.mode_section.card_mode.get(),
            via_filter=via_filter,
            include_missing_via=self.filter_section.include_missing.get(),
            default_via=self.base_config.generation.default_via,
            page_orientation=self.base_config.generation.page_orientation,
            static_footer=self.base_config.generation.static_footer,
            qsl_mark=QSL_MARK_TO_CODE.get(self.sender_section.qsl_mark.get(), "none"),
            portable_mark=PORTABLE_TO_CODE.get(self.sender_section.portable.get(), "none"),
        )
        return AppConfig(sender=sender, lookup=lookup, generation=generation)

    def _save_config(self) -> None:
        config = self._gather_config()
        try:
            cfg.save(config, CONFIG_PATH)
        except OSError as exc:
            messagebox.showerror("Fehler", f"Config konnte nicht gespeichert werden:\n{exc}")
            return
        self.base_config = config
        messagebox.showinfo("Gespeichert", f"Config gespeichert: {CONFIG_PATH}")

    def _load_config(self) -> None:
        if not Path(CONFIG_PATH).exists():
            messagebox.showwarning("Nicht gefunden", f"{CONFIG_PATH} existiert nicht.")
            return
        self.base_config = cfg.load(CONFIG_PATH)
        self._apply_config_to_widgets(self.base_config)
        self._rebuild_cards()

    # ------------------------------------------------------------- ADIF
    def _browse_log(self) -> None:
        path = filedialog.askopenfilename(title="ADIF-Logbuch wählen", filetypes=ADIF_TYPES)
        if path:
            self.file_section.path_var.set(path)
            self._load_log()  # Hot-Load: direkt nach Auswahl laden

    def _load_log(self) -> None:
        path = self.file_section.path_var.get().strip()
        if not path:
            messagebox.showwarning("Kein Pfad", "Bitte zuerst eine ADIF-Datei wählen.")
            return
        try:
            self.qsos = parse_file(path)
        except OSError as exc:
            messagebox.showerror("Fehler", f"Logbuch nicht lesbar:\n{exc}")
            return
        self.file_section.count_var.set(f"{len(self.qsos)} QSOs geladen")
        self._rebuild_cards()

    # ------------------------------------------------------------ Bild
    def _choose_image(self) -> None:
        path = filedialog.askopenfilename(title="Frontbild wählen", filetypes=IMAGE_TYPES)
        if not path:
            return
        self.image_section.path_var.set(path)
        self._update_thumbnail(path)

    def _update_thumbnail(self, path: str) -> None:
        try:
            img = Image.open(path)
            img.thumbnail(THUMB_MAX)
            self._thumb = ImageTk.PhotoImage(img)
        except (OSError, ValueError) as exc:
            self.image_section.thumb_label.config(text=f"(Bild-Fehler: {exc})", image="")
            self._thumb = None
            return
        self.image_section.thumb_label.config(image=self._thumb, text="")

    # ---------------------------------------------------------- Karten
    def _rebuild_cards(self) -> None:
        if not self.qsos:
            self.preview.set_cards([])
            return
        cards = build_cards(self.qsos, self._gather_config())
        self.preview.set_cards(cards)

    # ---------------------------------------------------- PDF-Erzeugung
    def _on_generate(self) -> None:
        cards = self.preview.included_cards()
        if not cards:
            messagebox.showwarning("Keine Karten", "Es sind keine Karten zum Erzeugen ausgewählt.")
            return
        front = self.image_section.path_var.get().strip()
        if not front or not Path(front).exists():
            messagebox.showerror("Frontbild fehlt", "Bitte ein gültiges Frontbild wählen.")
            return
        output = self.output_section.output_var.get().strip()
        if not output:
            messagebox.showerror("Kein Ziel", "Bitte einen Ausgabepfad angeben.")
            return

        config = self._gather_config()
        self.output_section.generate_btn.config(state="disabled")
        self.output_section.progress.config(maximum=len(cards), value=0)
        self.output_section.status_var.set("Erzeuge PDF…")

        thread = threading.Thread(
            target=self._worker_generate,
            args=(cards, config, front, output),
            daemon=True,
        )
        thread.start()

    def _worker_generate(self, cards, config, front, output) -> None:
        def progress(done: int, total: int) -> None:
            self.after(0, self._update_progress, done, total)

        try:
            generate(cards, config, front, output, progress_cb=progress)
        except Exception as exc:  # bewusst breit: Fehler nicht in den Thread schlucken
            self.after(0, self._generate_done, output, exc)
            return
        self.after(0, self._generate_done, output, None)

    def _update_progress(self, done: int, total: int) -> None:
        self.output_section.progress.config(value=done)
        self.output_section.status_var.set(f"Erzeuge PDF… {done}/{total}")

    def _generate_done(self, output: str, error: Exception | None) -> None:
        self.output_section.generate_btn.config(state="normal")
        if error is not None:
            self.output_section.status_var.set(f"Fehler: {error}")
            messagebox.showerror("Fehler", f"PDF-Erzeugung fehlgeschlagen:\n{error}")
            return
        self.output_section.status_var.set(f"Fertig: {output}")
        messagebox.showinfo("Fertig", f"PDF erzeugt:\n{output}")

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="PDF speichern unter", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")]
        )
        if path:
            self.output_section.output_var.set(path)
