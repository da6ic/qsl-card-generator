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
from qslcards.lookup import has_lookup_credentials, lookup_calls
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
PORTABLE_TO_CODE = {"Keins": "none", "/p": "p", "/m": "m", "/t": "t", "/r": "r"}
PORTABLE_CODE_TO_DISPLAY = {v: k for k, v in PORTABLE_TO_CODE.items()}
CONFIRM_MARK_TO_CODE = {
    "Leer lassen": "none",
    "Confirming QSO": "qso",
    "Confirming SWL-Report": "swl",
}
CONFIRM_CODE_TO_DISPLAY = {v: k for k, v in CONFIRM_MARK_TO_CODE.items()}

# Thumbnail-Maximalgröße. Die Höhe bleibt unter der natürlichen Höhe des
# Absender-Blocks, damit ein geladenes Bild die linke Spalte (und damit das
# Fenster) nicht höher zieht.
THUMB_MAX = (340, 210)

# Auto-Sync der Config
SAVE_DEBOUNCE_MS = 600  # Verzögerung nach der letzten Änderung vor dem Speichern
POLL_MS = 1500  # Intervall, in dem config.yaml auf externe Änderungen geprüft wird


class _ScrollableFrame:
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
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        # Inneres Frame auf Canvas-Breite ziehen (horizontal füllen).
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("QSL-Karten-Generator")
        self.geometry("980x760")
        self.minsize(720, 480)

        # Zustand
        self.qsos: list = []
        self._thumb: ImageTk.PhotoImage | None = None
        # Basis-Config für Felder, die nicht in der GUI editierbar sind
        # (default_via, static_footer, program_id, page_orientation).
        self.base_config: AppConfig = AppConfig()

        # Lookup-Zustand: Map CALL -> LookupResult|None (Via/Manager/Adresse).
        self.lookups: dict = {}
        self._lookup_running = False
        self._generating = False

        # Auto-Sync-Zustand
        self._suppress_save = False  # unterdrückt Auto-Save beim programmatischen Setzen
        self._save_after_id: str | None = None  # laufender Debounce-Timer
        self._last_mtime: float | None = None  # zuletzt bekannte mtime von config.yaml

        self._build_ui()
        self._wire_commands()
        self._load_initial_config()
        self._last_mtime = self._config_mtime()
        self._wire_autosave()
        self.after(POLL_MS, self._poll_config)

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        # Gesamte Oberfläche in einen scrollbaren Container -> bei kleinem
        # Fenster ist alles per Scrollbar/Mausrad erreichbar (Export zuletzt).
        self.body = _ScrollableFrame(self)
        self.body.outer.pack(fill="both", expand=True)
        root = self.body.inner

        # Oben links: ADIF (fix) + Frontbild (dehnt sich bündig zur Absender-Config).
        self._left = ttk.Frame(root)
        self.file_section = FileSection(self._left)
        self.image_section = ImageSection(self._left)
        self.file_section.frame.pack(side="top", fill="x")
        self.image_section.frame.pack(side="top", fill="both", expand=True, pady=(8, 0))

        # Mitte links: Filter(4) über Modus(5); Modus dehnt sich bündig zu Lookups(6).
        self._midleft = ttk.Frame(root)
        self.filter_section = FilterSection(self._midleft)
        self.mode_section = ModeSection(self._midleft)
        self.filter_section.frame.pack(side="top", fill="x")
        self.mode_section.frame.pack(side="top", fill="both", expand=True, pady=(8, 0))

        self.sender_section = SenderSection(root)
        self.lookup_section = LookupSection(root)
        self.preview = PreviewTable(root)
        self.output_section = OutputSection(root)

        self._left.grid(row=0, column=0, padx=6, pady=4, sticky="nsew")
        self.sender_section.frame.grid(row=0, column=1, padx=6, pady=4, sticky="nsew")
        self._midleft.grid(row=1, column=0, padx=6, pady=4, sticky="nsew")
        self.lookup_section.frame.grid(row=1, column=1, padx=6, pady=4, sticky="nsew")
        self.preview.frame.grid(row=2, column=0, columnspan=2, padx=6, pady=4, sticky="nsew")
        self.output_section.frame.grid(row=3, column=0, columnspan=2, padx=6, pady=4, sticky="we")

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)

    def _wire_commands(self) -> None:
        self.file_section.browse_btn.config(command=self._browse_log)
        self.file_section.load_btn.config(command=self._load_log)
        self.image_section.choose_btn.config(command=self._choose_image)
        self.output_section.browse_btn.config(command=self._browse_output)
        self.output_section.generate_btn.config(command=self._on_generate)

        # Enter in einem Eingabefeld gibt den Fokus frei -> kein Highlight/Auswahl.
        self.bind_class("TEntry", "<Return>", self._defocus_entry)

        # Der Via-Filter entfernt keine Zeilen mehr, sondern setzt nur die
        # Drucken-Markierung (kein Rebuild nötig).
        for cb in self.filter_section.checkbuttons:
            cb.config(command=self._apply_filter)
        # Modus/Markierungen ändern die Karten selbst -> Rebuild (mit Lookups).
        self.mode_section.radio_qso.config(command=self._rebuild_cards)
        self.mode_section.radio_station.config(command=self._rebuild_cards)
        self.sender_section.qsl_combo.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_cards())
        self.sender_section.portable_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._rebuild_cards()
        )
        self.sender_section.confirm_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._rebuild_cards()
        )
        # „Neu abrufen": fehlende/abgebrochene Stationen erneut nachschlagen.
        self.preview.refresh_btn.config(command=self._refresh_lookups)
        # Nach einer Via-Bearbeitung die Drucken-Markierung der Zeile nachziehen.
        self.preview.on_cell_edited = self._on_cell_edited

    # ----------------------------------------------------------- Config
    def _load_initial_config(self) -> None:
        for path in (CONFIG_PATH, EXAMPLE_CONFIG_PATH):
            if Path(path).exists():
                self.base_config = cfg.load(path)
                break
        self._apply_config_to_widgets(self.base_config)

    def _apply_config_to_widgets(self, config: AppConfig) -> None:
        # Programmatisches Setzen darf keinen Auto-Save auslösen.
        self._suppress_save = True
        try:
            for field, _ in SENDER_FIELDS:
                self.sender_section.vars[field].set(getattr(config.sender, field))

            self.lookup_section.hamqth_user.set(config.lookup.hamqth_user)
            self.lookup_section.hamqth_pass.set(config.lookup.hamqth_pass)
            self.lookup_section.qrz_user.set(config.lookup.qrz_user)
            self.lookup_section.qrz_pass.set(config.lookup.qrz_pass)
            self.lookup_section.address_export.set(config.lookup.address_export)

            for code, var in self.filter_section.via_vars.items():
                var.set(code in config.generation.via_filter)
            self.mode_section.card_mode.set(config.generation.card_mode)
            self.sender_section.qsl_mark.set(
                QSL_CODE_TO_DISPLAY.get(config.generation.qsl_mark, "Leer lassen")
            )
            self.sender_section.portable.set(
                PORTABLE_CODE_TO_DISPLAY.get(config.generation.portable_mark, "Keins")
            )
            self.sender_section.confirm_mark.set(
                CONFIRM_CODE_TO_DISPLAY.get(config.generation.confirm_mark, "Leer lassen")
            )
        finally:
            self._suppress_save = False

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
            address_export=self.lookup_section.address_export.get(),
        )
        via_filter = [c for c, v in self.filter_section.via_vars.items() if v.get()]
        generation = GenerationConfig(
            card_mode=self.mode_section.card_mode.get(),
            via_filter=via_filter,
            default_via=self.base_config.generation.default_via,
            page_orientation=self.base_config.generation.page_orientation,
            static_footer=self.base_config.generation.static_footer,
            qsl_mark=QSL_MARK_TO_CODE.get(self.sender_section.qsl_mark.get(), "none"),
            portable_mark=PORTABLE_TO_CODE.get(self.sender_section.portable.get(), "none"),
            confirm_mark=CONFIRM_MARK_TO_CODE.get(self.sender_section.confirm_mark.get(), "none"),
        )
        return AppConfig(sender=sender, lookup=lookup, generation=generation)

    def _defocus_entry(self, event: tk.Event) -> str:
        """Enter im Eingabefeld: Auswahl aufheben und Fokus abgeben (kein Highlight)."""
        try:
            event.widget.selection_clear()
        except tk.TclError:
            pass
        self.focus_set()
        return "break"

    # --------------------------------------------------- Auto-Sync (Config)
    def _config_mtime(self) -> float | None:
        try:
            return Path(CONFIG_PATH).stat().st_mtime
        except OSError:
            return None

    def _wire_autosave(self) -> None:
        """Alle Eingabe-Variablen beobachten -> Änderung speichert automatisch."""
        watched: list[tk.Variable] = [
            *self.sender_section.vars.values(),
            self.sender_section.qsl_mark,
            self.sender_section.portable,
            self.sender_section.confirm_mark,
            self.lookup_section.hamqth_user,
            self.lookup_section.hamqth_pass,
            self.lookup_section.qrz_user,
            self.lookup_section.qrz_pass,
            self.lookup_section.address_export,
            *self.filter_section.via_vars.values(),
            self.mode_section.card_mode,
        ]
        for var in watched:
            var.trace_add("write", self._on_var_change)

    def _on_var_change(self, *_args) -> None:
        if self._suppress_save:
            return
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(SAVE_DEBOUNCE_MS, self._auto_save)

    def _auto_save(self) -> None:
        self._save_after_id = None
        if self._write_config():
            self.output_section.status_var.set("Config automatisch gespeichert")

    def _write_config(self) -> bool:
        """Sammelt die Config und schreibt sie; hält _last_mtime aktuell."""
        config = self._gather_config()
        try:
            cfg.save(config, CONFIG_PATH)
        except OSError as exc:
            self.output_section.status_var.set(f"Speichern fehlgeschlagen: {exc}")
            return False
        self.base_config = config
        self._last_mtime = self._config_mtime()
        return True

    def _poll_config(self) -> None:
        """Prüft periodisch, ob config.yaml extern geändert wurde -> neu laden."""
        try:
            mtime = self._config_mtime()
            if mtime is not None and mtime != self._last_mtime:
                self._reload_from_file()
        finally:
            self.after(POLL_MS, self._poll_config)

    def _reload_from_file(self) -> None:
        try:
            config = cfg.load(CONFIG_PATH)
        except OSError:
            return
        self.base_config = config
        self._apply_config_to_widgets(config)  # unterdrückt Auto-Save intern
        self._last_mtime = self._config_mtime()
        self._rebuild_cards()
        self.output_section.status_var.set("Config neu geladen (Datei geändert)")

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
        # Frische Lookups: alte Ergebnisse verwerfen und automatisch neu abrufen.
        self.lookups = {}
        self._start_lookups([q.call for q in self.qsos])

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
    def _via_filter_set(self) -> set[str]:
        return {code for code, var in self.filter_section.via_vars.items() if var.get()}

    def _included_default(self, card) -> bool:
        """Drucken-Voreinstellung: nur Karten mit ausgewählter Via (E nie im Filter)."""
        return card.via_code in self._via_filter_set()

    def _rebuild_cards(self) -> None:
        if not self.qsos:
            self.preview.set_cards([])
            return
        cards = build_cards(self.qsos, self._gather_config(), self.lookups)
        self.preview.set_cards(cards, included=self._included_default, pending=self._lookup_running)

    def _apply_filter(self) -> None:
        """Via-Filter geändert: nur die Drucken-Markierung neu setzen (kein Rebuild)."""
        self.preview.apply_via_filter(self._via_filter_set())

    def _on_cell_edited(self, iid: str, card, column: str) -> None:
        """Nach einer Via-Bearbeitung die Drucken-Markierung der Zeile nachziehen
        (neue Via im Filter -> drucken, sonst nicht). Route-Edits ändern nur den
        Kartentext und lassen die Markierung unberührt."""
        if column == "via":
            self.preview.set_row_included(iid, card.via_code in self._via_filter_set())

    # ------------------------------------------------------- Lookup (async)
    def _start_lookups(self, calls: list[str], *, force: bool = False) -> None:
        """Schlägt `calls` im Hintergrund nach (Via/Manager/Adresse).

        Ohne Zugangsdaten passiert kein Netzcall: alle Via fallen auf den
        Standard. Während des Laufs ist „PDF erzeugen" gesperrt.
        """
        if self._lookup_running or not calls:
            self._rebuild_cards()
            return
        config = self._gather_config()
        if not has_lookup_credentials(config.lookup):
            self._rebuild_cards()
            self.preview.set_status("Keine Lookup-Zugangsdaten – Via = Standard.")
            self._update_generate_state()
            return

        self._lookup_running = True
        self._rebuild_cards()  # zeigt „…" für Via/Route
        self.preview.set_status("Schlage Stationen nach…")
        self.preview.refresh_btn.config(state="disabled")
        self._update_generate_state()

        thread = threading.Thread(
            target=self._lookups_worker,
            args=(list(calls), config.lookup, force),
            daemon=True,
        )
        thread.start()

    def _refresh_lookups(self) -> None:
        """„Neu abrufen": offene (nicht aufgelöste) Stationen erneut versuchen;
        sind alle aufgelöst, wird ein vollständiger Force-Refresh gemacht."""
        if self._lookup_running or not self.qsos:
            return
        unresolved = [
            q.call for q in self.qsos if self.lookups.get((q.call or "").strip().upper()) is None
        ]
        self._start_lookups(unresolved or [q.call for q in self.qsos], force=True)

    def _lookups_worker(self, calls, lookup_config, force) -> None:
        def progress(done: int, total: int) -> None:
            self.after(0, self.preview.set_status, f"Schlage Stationen nach… {done}/{total}")

        # lookup_calls fängt Netz-/Auth-Fehler ab (nie fatal).
        results = lookup_calls(calls, lookup_config, force=force, progress_cb=progress)
        self.after(0, self._lookups_done, results)

    def _lookups_done(self, results: dict) -> None:
        self._lookup_running = False
        self.lookups.update(results)
        self._rebuild_cards()
        self.preview.refresh_btn.config(state="normal")
        total = len({(q.call or "").strip().upper() for q in self.qsos if q.call})
        found = sum(1 for r in self.lookups.values() if r is not None)
        self.preview.set_status(f"Lookup fertig – {found}/{total} Stationen gefunden.")
        self._update_generate_state()

    def _update_generate_state(self) -> None:
        busy = self._lookup_running or self._generating
        self.output_section.generate_btn.config(state="disabled" if busy else "normal")

    # ---------------------------------------------------- PDF-Erzeugung
    def _on_generate(self) -> None:
        if self._lookup_running:
            messagebox.showinfo(
                "Lookup läuft", "Bitte warten, bis die Stationen nachgeschlagen sind."
            )
            return
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
        self._generating = True
        self._update_generate_state()
        self.output_section.progress.config(maximum=len(cards), value=0)
        self.output_section.status_var.set("Erzeuge PDF…")

        thread = threading.Thread(
            target=self._worker_generate,
            args=(cards, config, front, output),
            daemon=True,
        )
        thread.start()

    def _worker_generate(self, cards, config, front, output) -> None:
        # Via/Manager/Adresse stecken bereits in den Karten (Auto-Lookup beim
        # Laden). Hier wird nur noch die PDF (+ optionaler Adress-Export) erzeugt.
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
        self._generating = False
        self._update_generate_state()
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
