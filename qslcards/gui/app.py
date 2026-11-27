"""Hauptfenster: verdrahtet den Assistenten mit den Abläufen.

Keine Geschäftslogik hier — die GUI ruft nur die fertigen Bausteine auf.
Langlaufende Arbeit (Lookup, Most Wanted, Wavelog, PDF) läuft im Hintergrund;
UI-Updates ausschließlich über `self.after(...)` (Tkinter ist nicht thread-safe).

Aufteilung (Bewertung 3.1):

* `controllers/` — Abläufe **ohne Tk**: Sitzungszustand, Lookup, Most Wanted,
  Wavelog, Druck, config.yaml. Ohne Xvfb testbar.
* `gui/config_form.py` — Eingabefelder <-> `AppConfig` an einer Stelle.
* `gui/app_cards.py`, `app_lookup.py`, `app_wavelog.py`, `app_print.py` — die
  Fensterteile je Arbeitsbereich (Mixins von `App`): sie zeigen an und rufen auf.
* hier: Aufbau, Verdrahtung, Config-Abgleich, Logbuch/Bild, Ansicht/Hilfe,
  Schrittwechsel.

Was die Tests ersetzen, bleibt bewusst **hier** im Modul und wird erst beim
Aufruf aufgelöst: die Pfade (`CONFIG_PATH` …), `lookup_calls`, `generate`,
`open_file`, `messagebox`, `confirm`, `ask_overwrite_manual_remarks`. Die
Mixins kommen nur über `_messagebox`/`_confirm`/`_ask_overwrite_remarks`/
`_open_file` daran.
"""

from __future__ import annotations

import subprocess
import sys
import threading  # noqa: F401  (Tests ersetzen appmod.threading.Thread)
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from qslcards import __version__, dxcc, mostwanted, paths  # noqa: F401  (dxcc/mostwanted: Tests)
from qslcards.config import AppConfig, AppearanceConfig, RecentConfig, push_recent
from qslcards.controllers.config_file import ConfigFile
from qslcards.controllers.lookup_runner import LookupRunner
from qslcards.controllers.mostwanted_flow import MostWantedFlow, MostWantedPaths
from qslcards.controllers.print_job import PrintJob
from qslcards.controllers.session import SessionState
from qslcards.controllers.wavelog_flow import WavelogFlow
from qslcards.logbook import LogFormatError, parse_file, qsl_already_sent
from qslcards.lookup import DEFAULT_CACHE_PATH, lookup_calls
from qslcards.lookup import secret as lookup_secret
from qslcards.pdf.generator import generate
from qslcards.wavelog import secret as wavelog_secret

from . import theme
from .app_cards import CardsMixin
from .app_lookup import LookupMixin
from .app_print import PrintMixin
from .app_wavelog import WavelogMixin
from .config_form import ConfigForm
from .desktop import (  # noqa: F401  (ICON_SIZES/load_icon: Tests, Altnamen)
    ICON_DIR,
    ICON_SIZES,
    load_app_icons,
    load_icon,
    open_file,
    reveal_in_file_manager,
)
from .help import HelpWindow, open_help
from .menu import MenuActions, MenuBar
from .preview import PreviewTable
from .scrollframe import ScrollableFrame
from .sections import (
    SENDER_LABELS,
    FileSection,
    FilterSection,
    ImageSection,
    LookupSection,
    ModeSection,
    MostWantedSection,
    OutputSection,
    PrintModeSection,
    RemarksSection,
    SenderSection,
    SourceSection,
    StatusBar,
    WavelogMarkSection,
    WavelogSection,
    add_section_help,
    ask_overwrite_manual_remarks,
    confirm,
    required_legend,
    show_about_dialog,
)
from .steps import (  # noqa: F401  (Tests lesen die Schrittnummern hier)
    SECTION_STEP,
    STEP_CARDS,
    STEP_LOOKUP,
    STEP_PRINT,
    STEP_REVIEW,
    STEP_SENDER,
    STEP_SOURCE,
    WIZARD_STEPS,
)
from .textedit import install_entry_shortcuts
from .wizard import Wizard

# Aus der Quelle die Projektwurzel, gebündelt der Programm- bzw. Benutzerordner
# (siehe `paths.data_dir`). Bleiben bewusst Modulattribute: die Tests setzen sie um.
CONFIG_PATH = str(paths.config_path())
EXAMPLE_CONFIG_PATH = str(paths.example_config_path())
MOSTWANTED_PATH = str(paths.mostwanted_path())
# cty.dat (Rufzeichen -> DXCC): zuletzt abgerufene Kopie, mitgelieferte Kopie,
# Nummerntabelle. Ebenfalls Modulattribute, damit die Tests sie umsetzen können.
CTY_PATH = str(paths.cty_path())
BUNDLED_CTY_PATH = str(paths.bundled_cty_path())
DXCC_NUMBERS_PATH = str(paths.dxcc_numbers_path())
# Selbst in Wavelog markierte QSOs (Sicherheitsnetz gegen Doppeldruck).
WAVELOG_SENT_PATH = str(paths.wavelog_sent_path())

IMAGE_TYPES = [("Bilder", "*.png *.jpg *.jpeg *.webp"), ("Alle Dateien", "*.*")]
LOG_TYPES = [
    ("Logbuch (ADIF/Cabrillo)", "*.adi *.adif *.cbr *.log"),
    ("ADIF", "*.adi *.adif"),
    ("Cabrillo", "*.cbr *.log"),
    ("Alle Dateien", "*.*"),
]

# Absenderfelder, die fachlich Großbuchstaben tragen: sie werden beim Verlassen
# des Feldes umgestellt. CQ-Zone/ITU sind Zahlen, Name/Adresse gehören dem
# Anwender. Die Karte stellt dieselben Felder beim Zeichnen noch einmal um
# (layout_back) — dort ist es die Garantie, hier die sichtbare Rückmeldung.
# Das Rufzeichen trägt dabei alles, was dazugehört: `F/DL0MT/P`, `DL0MT/QRP`.
UPPERCASE_SENDER_FIELDS = ("callsign", "locator", "dok")

# Thumbnail-Maximalgröße. Die Höhe bleibt unter der natürlichen Höhe des
# Absender-Blocks, damit ein geladenes Bild die linke Spalte (und damit das
# Fenster) nicht höher zieht.
THUMB_MAX = (340, 210)

# Auto-Sync der Config
SAVE_DEBOUNCE_MS = 600  # Verzögerung nach der letzten Änderung vor dem Speichern
POLL_MS = 1500  # Intervall, in dem config.yaml auf externe Änderungen geprüft wird


def _mostwanted_paths() -> MostWantedPaths:
    return MostWantedPaths(MOSTWANTED_PATH, CTY_PATH, BUNDLED_CTY_PATH, DXCC_NUMBERS_PATH)


class App(CardsMixin, LookupMixin, WavelogMixin, PrintMixin, tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("QSL-Karten-Generator")
        self.geometry("1000x780")
        self.minsize(720, 480)

        def schedule(fn, *args):
            self.after(0, fn, *args)

        # Zustand und Abläufe ohne Tk (Bewertung 3.1). `qsos`, `sent_qsos`,
        # `lookups`, `qsos_source` und `_pending_marks` sind Eigenschaften auf
        # `session`. Pfade und ersetzbare Funktionen werden erst beim Aufruf
        # über dieses Modul aufgelöst, damit die Tests sie umsetzen können.
        self.session = SessionState()
        self._config_file = ConfigFile(lambda: CONFIG_PATH, lambda: EXAMPLE_CONFIG_PATH)
        self._lookups = LookupRunner(
            schedule,
            lookup=lambda *a, **kw: lookup_calls(*a, **kw),
            thread_factory=lambda **kw: threading.Thread(**kw),
        )
        self._mostwanted = MostWantedFlow(schedule, _mostwanted_paths)
        self._wavelog = WavelogFlow(schedule, lambda: WAVELOG_SENT_PATH)
        self._print_job = PrintJob(schedule, generate=lambda *a, **kw: generate(*a, **kw))

        self._thumb: ImageTk.PhotoImage | None = None
        self._thumb_path = ""  # Pfad, zu dem die aktuelle Vorschau gehört
        # Basis-Config für Felder, die nicht in der GUI editierbar sind
        # (default_via, static_footer, program_id, page_orientation) sowie für
        # Aussehen und „Zuletzt verwendet". Wird VOR dem UI-Aufbau gelesen, weil
        # das Farbthema vor dem ersten Widget stehen muss.
        self.base_config: AppConfig = self._read_config()

        # Aussehen: Theme zuerst, damit alle Widgets korrekt gefärbt entstehen.
        self.palette = theme.apply(self, self.base_config.appearance.theme)
        self._app_icons = load_app_icons(self)
        self._set_window_icon()

        # Handbuch-Fenster (höchstens eines, siehe `_show_help`).
        self._help: HelpWindow | None = None

        # Zuletzt für den Karten-Neuaufbau verwendeter globaler Remarks-Text.
        # Verhindert überflüssige Rebuilds bei jedem FocusOut ohne Textänderung.
        self._last_remarks_built = ""
        # Schutz gegen Re-Entrancy: der Überschreiben-Dialog stiehlt den Fokus und
        # löst sonst erneut FocusOut -> _on_remarks_commit aus.
        self._remarks_dialog_open = False

        # Auto-Sync-Zustand
        self._suppress_save = False  # unterdrückt Auto-Save beim programmatischen Setzen
        self._save_after_id: str | None = None  # laufender Debounce-Timer
        # Zugangsdaten, mit denen zuletzt nachgeschlagen wurde (Schritt 3 startet
        # den Lookup neu, wenn sie sich geändert haben).
        self._lookup_signature: tuple | None = None

        self._build_ui()
        self._build_menu()
        # Die klassischen tk-Widgets (Listbox, Canvas, Menüs) entstehen erst im
        # UI-Aufbau und werden von ttk-Styles nicht erfasst — sie bekommen ihre
        # Farben hier. Ohne diesen Aufruf behielte z.B. die Prioritätsliste die
        # Auswahlfarbe des Betriebssystems.
        theme.restyle_tree(self, self.palette)
        self.config_form = ConfigForm(
            source=self.source_section,
            sender=self.sender_section,
            lookup=self.lookup_section,
            filter=self.filter_section,
            mode=self.mode_section,
            remarks=self.remarks_section,
            mostwanted=self.mostwanted_section,
            printmode=self.printmode_section,
            output=self.output_section,
            wavelog=self.wavelog_section,
            wavelog_mark=self.wavelog_mark_section,
        )
        self._wire_commands()
        self._apply_config_to_widgets(self.base_config)
        self._restore_wavelog_key()
        self._restore_lookup_credentials()
        self._last_mtime = self._config_mtime()
        self._wire_autosave()
        self._init_mostwanted()
        self.after(POLL_MS, self._poll_config)
        if self._config_file.problem:
            # Gerettete Fassung gleich wieder als gültige Datei ablegen, damit
            # ein Absturz direkt danach nicht wieder bei der kaputten landet.
            self._write_config()
            self.after_idle(self._report_config_problem)

    # ------------------------------------------- Kurzwege auf die Abläufe
    # Für Tests und Altaufrufer: der Zustand selbst lebt in `controllers/`.
    @property
    def qsos(self) -> list:
        return self.session.qsos

    @qsos.setter
    def qsos(self, value: list) -> None:
        self.session.qsos = value

    @property
    def sent_qsos(self) -> list:
        return self.session.sent_qsos

    @sent_qsos.setter
    def sent_qsos(self, value: list) -> None:
        self.session.sent_qsos = value

    @property
    def lookups(self) -> dict:
        return self.session.lookups

    @lookups.setter
    def lookups(self, value: dict) -> None:
        self.session.lookups = value

    @property
    def qsos_source(self) -> str | None:
        return self.session.source

    @qsos_source.setter
    def qsos_source(self, value: str | None) -> None:
        self.session.source = value

    @property
    def _pending_marks(self) -> list:
        return self.session.pending_marks

    @_pending_marks.setter
    def _pending_marks(self, value: list) -> None:
        self.session.pending_marks = value

    @property
    def mostwanted_list(self) -> mostwanted.MostWantedList | None:
        return self._mostwanted.ranking

    @mostwanted_list.setter
    def mostwanted_list(self, value: mostwanted.MostWantedList | None) -> None:
        self._mostwanted.ranking = value

    @property
    def cty(self) -> dxcc.CtyDatabase | None:
        return self._mostwanted.cty

    @cty.setter
    def cty(self, value: dxcc.CtyDatabase | None) -> None:
        self._mostwanted.cty = value

    @property
    def _mostwanted_running(self) -> bool:
        return self._mostwanted.running

    @_mostwanted_running.setter
    def _mostwanted_running(self, value: bool) -> None:
        self._mostwanted.running = value

    @property
    def _wavelog_stations(self) -> list:
        return self._wavelog.stations

    @_wavelog_stations.setter
    def _wavelog_stations(self, value: list) -> None:
        self._wavelog.stations = list(value)

    @property
    def _wavelog_busy(self) -> bool:
        return self._wavelog.busy

    def _wavelog_sent_path(self) -> str:
        return WAVELOG_SENT_PATH

    # -------------------------------------- Dialoge (für die Mixins, ersetzbar)
    @property
    def _messagebox(self):
        return messagebox

    def _confirm(self, *args, **kwargs) -> bool:
        return confirm(*args, **kwargs)

    def _ask_overwrite_remarks(self, parent) -> bool:
        return ask_overwrite_manual_remarks(parent)

    def _open_file(self, path: str) -> None:
        open_file(path)

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        """Baut den Schritt-Assistenten (siehe `wizard.py`).

        Jeder Abschnitt von früher lebt weiter, nur steht er jetzt auf der
        Seite seines Schritts — es geht keine Funktion verloren:

        1 Quelle    Logdatei ODER Wavelog
        2 Absender  eigene Stationsdaten
        3 Abfrage   Lookups, Zustellwege, Kartenmodus
        4 Gestalten Frontbild, Bemerkungen, Most Wanted
        5 Prüfen    Vorschau (füllt die Seite, kein Außen-Scroll)
        6 Druck     Druckmodus (inkl. QR), Ausgabe, Wavelog-Markierung
        """
        # Statusleiste und Navigation zuerst packen (side="bottom"), damit sie
        # beim Verkleinern stehen bleiben und nur die Seite darüber schrumpft.
        self.status = StatusBar(self)
        self.status.frame.pack(side="bottom", fill="x")
        ttk.Separator(self, orient="horizontal").pack(side="bottom", fill="x")

        # Die Seiten liegen in einem scrollbaren Container; der Assistent packt
        # immer nur die aktuelle hinein.
        self.body = ScrollableFrame(self)
        self.wizard = Wizard(self, WIZARD_STEPS, self.body.inner)
        self.wizard.nav.pack(side="bottom", fill="x")
        ttk.Separator(self, orient="horizontal").pack(side="bottom", fill="x")
        self.wizard.head.pack(side="top", fill="x")
        ttk.Separator(self, orient="horizontal").pack(side="top", fill="x")
        self.body.outer.pack(fill="both", expand=True)
        # Fußnote zum Stern: gilt für alle Seiten -> in der Navigationsleiste.
        self.required_legend = required_legend(self.wizard.nav)
        self.required_legend.configure(style="WizardNav.TFrame")
        for child in self.required_legend.winfo_children():
            if child.cget("style") == "Muted.TLabel":
                child.configure(style="NavHint.TLabel")
            else:
                child.configure(style="NavRequired.TLabel")
        self.required_legend.pack(side="left", padx=(theme.PAD_SECTION * 2, 0))

        pad = theme.PAD_SECTION
        wiz = self.wizard

        # --- Schritt 1: Quelle
        page = wiz.page(STEP_SOURCE)
        self.source_section = SourceSection(page)
        self.source_section.frame.pack(side="top", fill="x", pady=(0, pad))
        self.file_section = FileSection(page)
        self.wavelog_section = WavelogSection(page)

        # --- Schritt 2: Absender
        page = wiz.page(STEP_SENDER)
        self.sender_section = SenderSection(page)
        self.sender_section.frame.pack(side="top", anchor="w")

        # --- Schritt 3: Abfrage & Zustellwege
        page = wiz.page(STEP_LOOKUP)
        self.lookup_section = LookupSection(page)
        right = ttk.Frame(page)
        self.filter_section = FilterSection(right)
        self.mode_section = ModeSection(right)
        self.filter_section.frame.pack(side="top", fill="x")
        self.mode_section.frame.pack(side="top", fill="x", pady=(pad, 0))
        self.lookup_section.frame.grid(row=0, column=0, padx=(0, pad // 2), sticky="nsew")
        right.grid(row=0, column=1, padx=(pad // 2, 0), sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=1)

        # --- Schritt 4: Gestalten
        page = wiz.page(STEP_CARDS)
        top = ttk.Frame(page)
        top.pack(side="top", fill="x")
        self.image_section = ImageSection(top)
        side = ttk.Frame(top)
        self.remarks_section = RemarksSection(side)
        self.mostwanted_section = MostWantedSection(side)
        self.remarks_section.frame.pack(side="top", fill="x")
        self.mostwanted_section.frame.pack(side="top", fill="x", pady=(pad, 0))
        self.image_section.frame.grid(row=0, column=0, padx=(0, pad // 2), sticky="nsew")
        side.grid(row=0, column=1, padx=(pad // 2, 0), sticky="nsew")
        top.columnconfigure(0, weight=0)  # Thumbnail hat eine feste Höchstgröße
        top.columnconfigure(1, weight=1)

        # --- Schritt 5: Prüfen (Vorschau über die ganze Höhe)
        page = wiz.page(STEP_REVIEW)
        self.preview = PreviewTable(page, palette=self.palette)
        self.preview.frame.pack(side="top", fill="both", expand=True)

        # --- Schritt 6: Druck & Export
        page = wiz.page(STEP_PRINT)
        self.printmode_section = PrintModeSection(page)
        self.output_section = OutputSection(page)
        self.wavelog_mark_section = WavelogMarkSection(page)
        self.printmode_section.frame.pack(side="top", fill="x")
        self.output_section.frame.pack(side="top", fill="x", pady=(pad, 0))

        # Sprungziele für „Ansicht > Gehe zu Abschnitt" (Nummer -> Rahmen); die
        # Nummern bleiben die des Handbuchs (Anker `abschnitt-N`).
        self._sections: dict[int, ttk.LabelFrame] = {
            1: self.file_section.frame,
            2: self.image_section.frame,
            3: self.sender_section.frame,
            4: self.filter_section.frame,
            5: self.mode_section.frame,
            6: self.lookup_section.frame,
            7: self.mostwanted_section.frame,
            8: self.remarks_section.frame,
            9: self.preview.frame,
            10: self.printmode_section.frame,
            11: self.output_section.frame,
        }

        # Kontexthilfe: jeder Abschnittstitel bekommt ein „?", das das Handbuch
        # beim zugehörigen Kapitel öffnet (Anker `abschnitt-N` in handbuch.md).
        for number, frame in self._sections.items():
            add_section_help(frame, lambda n=number: self._show_help(f"abschnitt-{n}"))
        add_section_help(self.wavelog_section.frame, lambda: self._show_help("wavelog"))

        wiz.can_leave = self._step_problem
        wiz.on_blocked = self._mark_step_problem
        wiz.on_leave = self._on_step_leave
        wiz.on_enter = self._on_step_enter
        self._show_source(self.source_section.kind.get())

    def _set_window_icon(self) -> None:
        """Setzt das Fenster-/Programmsymbol auf allen Plattformen.

        `iconphoto` funktioniert überall (Tk nimmt sich die passende Größe);
        unter Windows sorgt zusätzlich die .ico-Datei für ein sauberes Symbol in
        Taskleiste und Fensterrahmen.
        """
        if self._app_icons:
            try:
                self.iconphoto(True, *self._app_icons)
            except tk.TclError:  # pragma: no cover - je nach Fenstermanager
                pass
        if sys.platform.startswith("win"):  # pragma: no cover - nur Windows
            ico = ICON_DIR / "app_icon.ico"
            if ico.exists():
                try:
                    self.iconbitmap(default=str(ico))
                except tk.TclError:
                    pass

    # -------------------------------------------------------------- Menü
    def _build_menu(self) -> None:
        actions = MenuActions(
            open_log=self._browse_log,
            open_image=self._choose_image,
            open_recent_log=self._open_recent_log,
            open_recent_image=self._open_recent_image,
            clear_recent=self._clear_recent,
            choose_output=self._browse_output,
            generate=self._on_generate,
            quit=self.destroy,
            reload_log=self._load_log,
            refresh_lookups=self._refresh_lookups,
            clear_lookup_cache=self._clear_lookup_cache,
            set_theme=self._set_theme,
            goto_section=self._goto_section,
            show_about=self._show_about,
            show_help=self._show_help,
            open_config=lambda: self._open_path(Path(CONFIG_PATH)),
            reveal_output=self._reveal_output,
            reveal_cache=lambda: self._reveal_path(Path(DEFAULT_CACHE_PATH)),
            reveal_log=self._reveal_log,
        )
        self.menubar = MenuBar(self, actions, theme_mode=self.base_config.appearance.theme)
        self.menubar.set_recent(self.base_config.recent.logs, self.base_config.recent.images)
        theme.restyle_tree(self.menubar.menubar, self.palette)

    def _wire_commands(self) -> None:
        self.file_section.browse_btn.config(command=self._browse_log)
        self.file_section.load_btn.config(command=self._load_log)
        self.image_section.choose_btn.config(command=self._choose_image)
        self.image_section.path_entry.bind("<FocusOut>", self._on_image_entry_commit)
        self.output_section.browse_btn.config(command=self._browse_output)
        self.output_section.generate_btn.config(command=self._on_generate)
        self.source_section.kind.trace_add(
            "write", lambda *_a: self._show_source(self.source_section.kind.get())
        )
        self.wavelog_section.load_stations_btn.config(command=self._wavelog_load_stations)
        self.wavelog_section.load_qsos_btn.config(command=self._wavelog_load_qsos)
        self.wavelog_section.station_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_wavelog_station_selected()
        )
        self.wavelog_section.remember_key.trace_add("write", self._on_remember_key_toggle)
        self.lookup_section.remember.trace_add("write", self._on_remember_lookup_toggle)
        if not lookup_secret.available():
            self.lookup_section.remember.set(False)
            self.lookup_section.remember_check.configure(
                state="disabled", text="Im Schlüsselbund merken (nicht verfügbar)"
            )
        self.wavelog_mark_section.mark_now_btn.config(command=self._wavelog_mark_pending)
        if not wavelog_secret.available():
            self.wavelog_section.remember_key.set(False)
            self.wavelog_section.remember_check.configure(
                state="disabled", text="Im Schlüsselbund merken (nicht verfügbar)"
            )

        # Enter in einem Eingabefeld gibt den Fokus frei -> kein Highlight/Auswahl.
        self.bind_class("TEntry", "<Return>", self._defocus_entry)
        # Wort-/zeilenweises Löschen in allen Eingabefeldern (Tk bringt nur das
        # zeichenweise Löschen mit).
        install_entry_shortcuts(self)

        # Die Prioritätsliste entfernt keine Zeilen, sondern setzt nur die
        # Drucken-Markierung neu (kein Rebuild nötig). Die Listbox hat keine
        # tk.Variable -> Auto-Save wird hier manuell angestoßen.
        self.filter_section.btn_up.config(command=lambda: self._on_priority_move("up"))
        self.filter_section.btn_down.config(command=lambda: self._on_priority_move("down"))
        # Modus/Markierungen ändern die Karten selbst -> Rebuild (mit Lookups).
        self.mode_section.radio_qso.config(command=self._rebuild_cards)
        self.mode_section.radio_station.config(command=self._rebuild_cards)
        self.printmode_section.qr_check.config(command=self._rebuild_cards)
        self.sender_section.qsl_combo.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_cards())
        self.sender_section.confirm_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._rebuild_cards()
        )
        # Rufzeichen/Locator/DOK: beim Verlassen des Feldes großschreiben, damit
        # Oberfläche, Config und Karte dasselbe zeigen.
        for field in UPPERCASE_SENDER_FIELDS:
            self.sender_section.entries[field].bind(
                "<FocusOut>", lambda _e, name=field: self._on_uppercase_field_commit(name)
            )
        # Globaler Remarks-Text: ändert Kartentext UND ggf. die Zeilen-Aufteilung
        # (mit Remarks weniger Zeilen). Rebuild erst bei Fokusverlust/Enter, nicht
        # bei jedem Tastendruck (Enter gibt via _defocus_entry den Fokus frei).
        self.remarks_section.remarks_entry.bind("<FocusOut>", self._on_remarks_commit)
        # „Neu abrufen": fehlende/abgebrochene Stationen erneut nachschlagen.
        self.preview.refresh_btn.config(command=self._refresh_lookups)
        self.preview.cancel_btn.config(command=self._cancel_lookups)
        self.preview.show_sent.trace_add("write", self._on_show_sent_toggle)
        # Nach einer Via-Bearbeitung die Drucken-Markierung der Zeile nachziehen.
        self.preview.on_cell_edited = self._on_cell_edited

        # Most Wanted: jede Einstellung setzt nur die Drucken-Markierung neu
        # (kein Rebuild). Nur das Einschalten holt bei Bedarf die Liste — Top
        # und Kategorie nicht, sonst ginge nach einem gescheiterten Abruf jeder
        # Tastendruck im Top-Feld erneut ins Netz.
        section = self.mostwanted_section
        section.enabled.trace_add("write", self._on_mostwanted_toggle)
        for var in (section.top, section.category):
            var.trace_add("write", self._on_mostwanted_change)
        section.top_spin.bind("<FocusOut>", lambda _e: section.normalize_top())

    # ----------------------------------------------------------- Config
    def _read_config(self) -> AppConfig:
        """Liest `config.yaml` (ersatzweise die Beispieldatei); Defaults sonst.

        Wird vor dem UI-Aufbau gebraucht (Farbthema, Icon, „Zuletzt verwendet"),
        deshalb getrennt vom Setzen der Widget-Werte. Eine beschädigte Datei
        bringt den Start nicht zum Absturz: es gilt die Sicherung, die Meldung
        zeigt `_report_config_problem`.
        """
        return self._config_file.read()

    @property
    def _config_problem(self) -> str | None:
        return self._config_file.problem

    def _report_config_problem(self) -> None:
        problem = self._config_file.take_problem()
        if not problem:
            return
        self.status.set("Einstellungen waren beschädigt (siehe Hinweis)", "error")
        messagebox.showwarning("Einstellungen beschädigt", problem, parent=self)

    def _apply_config_to_widgets(self, config: AppConfig) -> None:
        # Programmatisches Setzen darf keinen Auto-Save auslösen.
        self._suppress_save = True
        try:
            self.config_form.apply(config)
            self._last_remarks_built = config.generation.remarks
            # Menü-Zustand (Farbthema-Markierung, „Zuletzt verwendet") nachziehen.
            self.menubar.set_theme_mode(config.appearance.theme)
            self.menubar.set_recent(config.recent.logs, config.recent.images)
        finally:
            self._suppress_save = False

    def _gather_config(self) -> AppConfig:
        return self.config_form.gather(self.base_config)

    def _defocus_entry(self, event: tk.Event) -> str:
        """Enter im Eingabefeld: Auswahl aufheben und Fokus abgeben (kein Highlight)."""
        try:
            event.widget.selection_clear()
        except tk.TclError:
            pass
        self.focus_set()
        return "break"

    def _on_uppercase_field_commit(self, field: str) -> None:
        """Rufzeichen/Locator/DOK beim Verlassen des Feldes großschreiben.

        Beim Tippen wird bewusst nicht umgestellt: das Setzen der Variablen
        rückt die Schreibmarke ans Ende, was mitten im Wort stört.
        """
        var = self.sender_section.vars[field]
        current = var.get()
        upper = current.strip().upper()
        if upper != current:
            var.set(upper)

    # --------------------------------------------------- Auto-Sync (Config)
    @property
    def _last_mtime(self) -> float | None:
        return self._config_file.last_mtime

    @_last_mtime.setter
    def _last_mtime(self, value: float | None) -> None:
        self._config_file.last_mtime = value

    def _config_mtime(self) -> float | None:
        return self._config_file.mtime()

    def _wire_autosave(self) -> None:
        """Alle Eingabe-Variablen beobachten -> Änderung speichert automatisch."""
        for var in self.config_form.watched_vars():
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
            self.status.set("Config automatisch gespeichert", "ok")

    def _write_config(self) -> bool:
        """Sammelt die Config und schreibt sie (atomar, merkt die mtime)."""
        config = self._gather_config()
        try:
            self._config_file.save(config)
        except OSError as exc:
            self.status.set(f"Speichern fehlgeschlagen: {exc}", "error")
            return False
        self.base_config = config
        return True

    def _poll_config(self) -> None:
        """Prüft periodisch, ob config.yaml extern geändert wurde -> neu laden."""
        try:
            self._reload_from_file()
        finally:
            self.after(POLL_MS, self._poll_config)

    def _reload_from_file(self) -> None:
        result = self._config_file.reload_if_changed()
        if result.error is not None:
            # Extern halb geschrieben oder von Hand verdorben: die Einstellungen
            # im Fenster bleiben gültig, der nächste Auto-Save repariert die Datei.
            self.status.set(
                f"Config-Datei nicht lesbar, behalte die aktuellen Werte ({result.error})",
                "error",
            )
            return
        config = result.config
        if config is None:
            return
        previous_theme = self.base_config.appearance.theme
        self.base_config = config
        self._apply_config_to_widgets(config)  # unterdrückt Auto-Save intern
        if config.appearance.theme != previous_theme:
            self._apply_theme(config.appearance.theme)
        self._ensure_mostwanted()  # Filter evtl. in der Datei eingeschaltet
        self._rebuild_cards()
        self.status.set("Config neu geladen (Datei geändert)", "ok")

    def _remember_recent(self, kind: str, path: str) -> None:
        """Nimmt `path` in die „Zuletzt verwendet"-Liste auf und speichert sie.

        `kind` ist "logs" oder "images". Die Menüs werden sofort aktualisiert.
        """
        recent = self.base_config.recent
        updated = push_recent(getattr(recent, kind), path)
        if updated == getattr(recent, kind):
            return
        setattr(recent, kind, updated)
        self.menubar.set_recent(recent.logs, recent.images)
        self._write_config()

    def _clear_recent(self) -> None:
        """Menü „Datei > … > Liste leeren": beide Listen verwerfen."""
        self.base_config.recent = RecentConfig()
        self.menubar.set_recent([], [])
        self._write_config()
        self.status.set("Liste „zuletzt verwendet“ geleert", "ok")

    # ---------------------------------------------------------- Logbuch
    def _browse_log(self) -> None:
        path = filedialog.askopenfilename(title="Logbuch wählen", filetypes=LOG_TYPES)
        if path:
            self.file_section.path_var.set(path)
            self._load_log()  # Hot-Load: direkt nach Auswahl laden

    def _open_recent_log(self, path: str) -> None:
        """Menü „Zuletzt verwendete Logs": Pfad übernehmen und laden."""
        self.file_section.path_var.set(path)
        self._load_log()

    def _load_log(self) -> None:
        path = self.file_section.path_var.get().strip()
        if not path:
            messagebox.showwarning("Kein Pfad", "Bitte zuerst eine Logdatei wählen.")
            return
        try:
            qsos = parse_file(path)
        except OSError as exc:
            messagebox.showerror("Fehler", f"Logbuch nicht lesbar:\n{exc}")
            self.status.set(f"Logbuch nicht lesbar: {exc}", "error")
            return
        except LogFormatError as exc:
            # Getrennt von OSError: „Datei fehlt/keine Rechte" und „Inhalt passt
            # nicht" sind für den Anwender verschiedene Probleme. Die bisher
            # geladenen QSOs bleiben stehen, es startet kein neuer Lookup.
            messagebox.showerror("Fehler", f"Logbuch nicht verwertbar:\n{exc}")
            self.status.set(f"Logbuch nicht verwertbar: {exc}", "error")
            return
        # Schon gesendete Karten (QSL_SENT = Y) bekommen keine neue.
        self.session.load(qsos, "file", qsl_already_sent)
        sent = len(self.sent_qsos)
        self._pending_marks = []
        self.file_section.set_missing(False)  # Markierung eines Druckversuchs weg
        note = f" ({sent} schon gesendet, ausgelassen)" if sent else ""
        self.file_section.count_var.set(f"{len(self.qsos)} QSOs geladen{note}")
        self.status.set_info(f"{len(self.qsos)} QSOs · {Path(path).name}")
        self._remember_recent("logs", path)
        # Frische Lookups: alte Ergebnisse verwerfen und automatisch neu abrufen.
        self.lookups = {}
        self._update_show_sent()
        self._start_lookups(self._lookup_calls_needed())

    # ------------------------------------------------------------ Bild
    def _choose_image(self) -> None:
        path = filedialog.askopenfilename(title="Frontbild wählen", filetypes=IMAGE_TYPES)
        if not path:
            return
        self._set_image(path)

    def _open_recent_image(self, path: str) -> None:
        """Menü „Zuletzt verwendete Bilder": Pfad übernehmen und Vorschau zeigen."""
        self._set_image(path)

    def _set_image(self, path: str) -> None:
        self.image_section.path_var.set(path)
        self._update_thumbnail(path)
        self.image_section.set_missing(False)  # Markierung eines Druckversuchs weg
        self._remember_recent("images", path)

    def _on_image_entry_commit(self, _event: object = None) -> None:
        """Von Hand getippter Bildpfad: Vorschau wie nach „Bild wählen…".

        Vorher blieb das Vorschaufeld bei einem getippten Pfad leer, obwohl die
        PDF das Bild verwendet hat — man sah nicht, ob der Pfad stimmt.
        """
        path = self.image_section.path_var.get().strip()
        if path == self._thumb_path:
            return  # unverändert (jeder Fokuswechsel löst FocusOut aus)
        if not path:
            self._thumb = None
            self._thumb_path = ""
            self.image_section.thumb_label.config(text="keine Vorschau", image="")
            return
        self._update_thumbnail(path)
        if self._thumb is not None:
            self.image_section.set_missing(False)
            self._remember_recent("images", path)

    def _update_thumbnail(self, path: str) -> None:
        self._thumb_path = path
        try:
            with Image.open(path) as img:
                img.thumbnail(THUMB_MAX)
                self._thumb = ImageTk.PhotoImage(img)
        except (OSError, ValueError) as exc:
            self.image_section.thumb_label.config(text=f"(Bild-Fehler: {exc})", image="")
            self._thumb = None
            return
        self.image_section.thumb_label.config(image=self._thumb, text="")

    # ------------------------------------------------------ Ansicht/Hilfe
    def _apply_theme(self, mode: str) -> None:
        """Färbt Fenster, Menüs und Tabelle auf den gewählten Modus um."""
        self.palette = theme.apply(self, mode)
        theme.restyle_tree(self, self.palette)
        theme.restyle_tree(self.menubar.menubar, self.palette)
        self.preview.apply_palette(self.palette)
        # Die Text-Tags des Handbuchs sind keine ttk-Styles und müssen von Hand
        # nachgezogen werden, sonst bleibt ein offenes Fenster im alten Thema.
        if self._help is not None and self._help.winfo_exists():
            self._help.apply_palette(self.palette)
        self.menubar.set_theme_mode(mode)

    def _set_theme(self, mode: str) -> None:
        """Menü „Ansicht > Farbthema": umschalten und in der Config festhalten."""
        self.base_config.appearance = AppearanceConfig(theme=mode)
        self._apply_theme(mode)
        self._write_config()
        self.status.set(f"Farbthema: {theme.THEME_LABELS.get(mode, mode)}", "ok")

    def _goto_section(self, number: int) -> None:
        """Menü „Ansicht > Gehe zu Abschnitt": zum Schritt des Abschnitts
        wechseln (ohne Prüfung) und den Abschnitt nach oben scrollen."""
        target = self._sections.get(number)
        if target is None:
            return
        self.wizard.go(SECTION_STEP.get(number, 0), check=False)
        canvas = self.body.canvas
        canvas.update_idletasks()
        total = self.body.inner.winfo_height()
        if total <= 0:
            return
        offset = target.winfo_rooty() - self.body.inner.winfo_rooty()
        canvas.yview_moveto(max(0.0, min(1.0, offset / total)))

    def _show_about(self) -> None:
        show_about_dialog(self, __version__, self.palette)

    def _show_help(self, anchor: str | None = None) -> None:
        """Handbuch zeigen — aus dem Menü (ohne Anker) oder aus einem „?".

        Es gibt immer nur **ein** Fenster: ein zweiter Aufruf holt das offene
        nach vorn und springt dort zum Kapitel.
        """
        if self._help is not None and self._help.winfo_exists():
            self._help.show(anchor)
            return
        self._help = open_help(self, self.palette, anchor=anchor, menubar=self.menubar.menubar)

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            self.status.set(f"Nicht gefunden: {path}", "error")
            return
        try:
            open_file(str(path))
        except (OSError, subprocess.SubprocessError) as exc:
            self.status.set(f"Öffnen fehlgeschlagen: {exc}", "error")

    def _reveal_path(self, path: Path) -> None:
        if not path.exists():
            self.status.set(f"Nicht gefunden: {path}", "error")
            return
        try:
            reveal_in_file_manager(str(path))
        except (OSError, subprocess.SubprocessError) as exc:
            self.status.set(f"Anzeigen fehlgeschlagen: {exc}", "error")

    def _reveal_log(self) -> None:
        """Menü „Hilfe": die Protokolldatei im Dateimanager zeigen.

        Ohne sie wäre das Protokoll unerreichbar: Ein Fensterprogramm hat keine
        Konsole, und der Ordner liegt je nach System woanders — auf macOS in
        `~/Library`, das der Finder von Haus aus versteckt.

        Geschrieben wird nur im gebündelten Betrieb (`main._prepare_frozen_runtime`);
        aus der Quelle gestartet gehen die Meldungen aufs Terminal.
        """
        path = paths.log_path()
        if not path.exists():
            self.status.set(
                "Noch kein Protokoll vorhanden (aus der Quelle gestartet: siehe Terminal).",
                "info",
            )
            return
        self._reveal_path(path)

    def _reveal_output(self) -> None:
        """Menü „Hilfe": den Ordner des eingestellten Ausgabeziels zeigen."""
        output = self.output_section.output_var.get().strip()
        if not output:
            self.status.set("Kein Ausgabeziel eingestellt.", "info")
            return
        path = Path(output).resolve()
        self._reveal_path(path if path.exists() else path.parent)

    # ------------------------------------------------------- Assistent
    def _show_source(self, kind: str) -> None:
        """Schritt 1: nur den Abschnitt der gewählten Quelle zeigen."""
        pad = theme.PAD_SECTION
        if kind == "wavelog":
            self.file_section.frame.pack_forget()
            self.wavelog_section.frame.pack(side="top", fill="x", pady=(pad, 0))
            self.wavelog_mark_section.frame.pack(side="top", fill="x", pady=(pad, 0))
        else:
            self.wavelog_section.frame.pack_forget()
            self.wavelog_mark_section.frame.pack_forget()
            self.file_section.frame.pack(side="top", fill="x", pady=(pad, 0))
        self.wizard.show_hint("")
        self.wizard.refresh()

    def _step_problem(self, index: int) -> str | None:
        """Was fehlt, um Schritt `index` zu verlassen? None = alles da.

        Rein lesend (wird auch zum Einfärben der Schrittleiste gefragt); das
        Markieren der Felder übernimmt `_mark_step_problem`.
        """
        if index == STEP_SOURCE:
            kind = self.source_section.kind.get()
            loaded = self.qsos or self.sent_qsos
            if not loaded or self.qsos_source != kind:
                if kind == "wavelog":
                    return "Bitte zuerst Station wählen und „QSOs laden“."
                return "Bitte zuerst ein Logbuch laden."
        elif index == STEP_SENDER:
            missing = self.sender_section.missing_required()
            if missing:
                names = ", ".join(SENDER_LABELS[f] for f in missing)
                return f"Pflichtfelder fehlen: {names}"
        elif index == STEP_CARDS:
            front = self.image_section.path_var.get().strip()
            if not front or not Path(front).exists():
                return "Bitte ein Frontbild wählen."
        return None

    def _mark_step_problem(self, index: int) -> None:
        if index == STEP_SOURCE:
            if self.source_section.kind.get() == "wavelog":
                self.wavelog_section.set_missing(not self.wavelog_section.selected_station_id())
            else:
                self.file_section.set_missing(True)
        elif index == STEP_SENDER:
            self.sender_section.mark_missing(self.sender_section.missing_required())
        elif index == STEP_CARDS:
            self.image_section.set_missing(True)

    def _on_step_leave(self, index: int) -> None:
        # Fokus abgeben: FocusOut-Bindungen (Großschreibung, Bemerkungen)
        # sollen greifen, bevor die Seite verschwindet.
        self.focus_set()
        if index == STEP_LOOKUP:
            self._store_lookup_credentials()
            self._maybe_restart_lookups()

    def _on_step_enter(self, index: int) -> None:
        # Auf „Prüfen" füllt die Seite das Fenster, gescrollt wird nur die Tabelle.
        self.body.set_fill(index == STEP_REVIEW)
        self.body.canvas.yview_moveto(0.0)
        if index == STEP_PRINT:
            self._update_mark_state()
