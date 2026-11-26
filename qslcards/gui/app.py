"""Hauptfenster: verdrahtet die Abschnitte mit config/builder/generator.

Keine Geschäftslogik hier — die GUI ruft nur die fertigen Bausteine auf.
Langlaufende Arbeit (PDF-Erzeugung) läuft im Worker-Thread; UI-Updates
ausschließlich über `self.after(...)` (Tkinter ist nicht thread-safe).
"""

from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from qslcards import __version__, dxcc, mostwanted, paths, wavelog
from qslcards import config as cfg
from qslcards.cards.builder import build_cards, is_printable, mostwanted_rank
from qslcards.config import (
    AppConfig,
    AppearanceConfig,
    GenerationConfig,
    LookupConfig,
    MostWantedConfig,
    RecentConfig,
    SenderConfig,
    SourceConfig,
    WavelogConfig,
    push_recent,
)
from qslcards.controllers.lookup_runner import (
    LookupOutcome,
    LookupProgress,
    LookupRunner,
    format_eta,
)
from qslcards.controllers.session import SessionState, marks_for_cards
from qslcards.logbook import LogFormatError, parse_file, qsl_already_sent
from qslcards.lookup import (
    DEFAULT_CACHE_PATH,
    LookupCredentials,
    active_via_priority,
    has_lookup_credentials,
    lookup_calls,
)
from qslcards.lookup import secret as lookup_secret
from qslcards.pdf.generator import generate
from qslcards.pdf.geometry import clamp_print_margin, normalize_sheet_mode
from qslcards.wavelog import secret as wavelog_secret
from qslcards.wavelog import sent_store
from qslcards.wavelog.client import (
    insecure_url_warning,
    paper_qsl_already_sent,
    reports_qsl_sent,
    validate_date,
)

from . import theme
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
    SENDER_FIELDS,
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
    parse_mm,
    required_legend,
    show_about_dialog,
)
from .textedit import install_entry_shortcuts
from .wizard import Step, Wizard

# Die Schritte des Assistenten (Reihenfolge = Arbeitsablauf).
STEP_SOURCE, STEP_SENDER, STEP_LOOKUP, STEP_CARDS, STEP_REVIEW, STEP_PRINT = range(6)
WIZARD_STEPS = [
    Step(
        "source",
        "Quelle",
        "Woher kommen die QSOs?",
        "Logdatei öffnen oder die QSOs direkt aus Wavelog holen.",
    ),
    Step(
        "sender",
        "Absender",
        "Deine Station",
        "Diese Angaben stehen als Absender auf jeder Karte. Sie werden gespeichert.",
    ),
    Step(
        "lookup",
        "Abfrage",
        "Zustellwege abfragen",
        "Mit QRZ/HamQTH erfährt das Programm, wie jede Station QSL-Karten möchte. "
        "Ohne Zugangsdaten gehen alle Karten über das Büro.",
    ),
    # Früher ein Schritt „Karten" mit Bild, Bemerkungen, Most Wanted UND
    # Vorschau — die Tabelle zeigte dort nur ~6 Zeilen in einer selbst
    # scrollenden Seite (Bewertung 2.5). Jetzt zwei Schritte; „Prüfen" gibt
    # der Tabelle die ganze Höhe und scrollt außen nicht.
    Step(
        "cards",
        "Gestalten",
        "Karten gestalten",
        "Frontbild wählen, Bemerkungen setzen und auf Wunsch nur Most Wanted drucken.",
    ),
    Step(
        "review",
        "Prüfen",
        "Karten prüfen",
        "In der Vorschau festlegen, welche Karten gedruckt werden. "
        "Ein Klick auf „Drucken“ schaltet eine Zeile um.",
    ),
    Step("print", "Druck", "Drucken und exportieren", "Druckart wählen und die PDF erzeugen."),
]
# Abschnittsnummer (Handbuch/Menü) -> Schritt, auf dem der Abschnitt steht.
SECTION_STEP = {1: 0, 2: 3, 3: 1, 4: 2, 5: 2, 6: 2, 7: 3, 8: 3, 9: 4, 10: 5, 11: 5}

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

# Display <-> Code-Mappings der Dropdowns.
QSL_MARK_TO_CODE = {"Leer lassen": "none", "PSE QSL": "pse", "TNX QSL": "tnx"}
QSL_CODE_TO_DISPLAY = {v: k for k, v in QSL_MARK_TO_CODE.items()}
CONFIRM_MARK_TO_CODE = {
    "Leer lassen": "none",
    "Confirming QSO": "qso",
    "Confirming SWL-Report": "swl",
}
CONFIRM_CODE_TO_DISPLAY = {v: k for k, v in CONFIRM_MARK_TO_CODE.items()}

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


def _format_date(iso: str | None) -> str:
    """ISO-Zeitstempel (UTC) -> „26.10.2026" in lokaler Zeit; unlesbar -> „?"."""
    try:
        return datetime.fromisoformat(iso or "").astimezone().strftime("%d.%m.%Y")
    except ValueError:
        return "?"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("QSL-Karten-Generator")
        self.geometry("1000x780")
        self.minsize(720, 480)

        # Zustand
        # Geladene QSOs, Lookups, offene Markierungen: ohne Tk in
        # `controllers.session` (Bewertung 3.1). `qsos`, `sent_qsos`, `lookups`,
        # `qsos_source` und `_pending_marks` sind Eigenschaften darauf.
        self.session = SessionState()
        self._thumb: ImageTk.PhotoImage | None = None
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

        # Hintergrund-Lookups mit Generation/Abbruch (Bewertung 1.4). Thread und
        # lookup_calls werden erst beim Aufruf aufgelöst, damit Tests beides
        # über das Modul ersetzen können.
        self._lookups = LookupRunner(
            lambda fn, *args: self.after(0, fn, *args),
            lookup=lambda *a, **kw: lookup_calls(*a, **kw),
            thread_factory=lambda **kw: threading.Thread(**kw),
        )
        self._generating = False

        # Most-Wanted-Rangliste (Abschnitt 7): die gespeicherte bzw. zuletzt
        # abgerufene Liste, ob gerade abgerufen wird und der letzte Fehler.
        self.mostwanted_list: mostwanted.MostWantedList | None = None
        self._mostwanted_running = False
        self._mostwanted_error: str | None = None
        # cty.dat: ordnet Rufzeichen ohne DXCC-Feld ihr Gebiet zu — ohne Netz,
        # auch für Cabrillo und ohne Lookup-Zugangsdaten.
        self.cty: dxcc.CtyDatabase | None = None

        # Zuletzt für den Karten-Neuaufbau verwendeter globaler Remarks-Text.
        # Verhindert überflüssige Rebuilds bei jedem FocusOut ohne Textänderung.
        self._last_remarks_built = ""
        # Schutz gegen Re-Entrancy: der Überschreiben-Dialog stiehlt den Fokus und
        # löst sonst erneut FocusOut -> _on_remarks_commit aus.
        self._remarks_dialog_open = False

        # Auto-Sync-Zustand
        self._suppress_save = False  # unterdrückt Auto-Save beim programmatischen Setzen
        self._save_after_id: str | None = None  # laufender Debounce-Timer
        self._last_mtime: float | None = None  # zuletzt bekannte mtime von config.yaml

        # Woher die geladenen QSOs stammen ("file" | "wavelog" | None) und der
        # Wavelog-Zustand (geladene Stationen, laufender Abruf, zu markierende QSOs).
        self._wavelog_stations: list[wavelog.WavelogStation] = []
        self._wavelog_busy = False
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
        self._wire_commands()
        self._apply_config_to_widgets(self.base_config)
        self._restore_wavelog_key()
        self._restore_lookup_credentials()
        self._last_mtime = self._config_mtime()
        self._wire_autosave()
        self._init_mostwanted()
        self.after(POLL_MS, self._poll_config)
        if self._config_problem:
            # Gerettete Fassung gleich wieder als gültige Datei ablegen, damit
            # ein Absturz direkt danach nicht wieder bei der kaputten landet.
            self._write_config()
            self.after_idle(self._report_config_problem)

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

        # --- Schritt 4: Karten
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
        bringt den Start nicht mehr zum Absturz: `cfg.load_safely` greift auf
        die Sicherung zurück, die Meldung zeigt `_report_config_problem`.
        """
        result = cfg.load_safely(CONFIG_PATH, EXAMPLE_CONFIG_PATH)
        self._config_problem = result.problem
        return result.config

    def _report_config_problem(self) -> None:
        problem = getattr(self, "_config_problem", None)
        if not problem:
            return
        self._config_problem = None
        self.status.set("Einstellungen waren beschädigt (siehe Hinweis)", "error")
        messagebox.showwarning("Einstellungen beschädigt", problem, parent=self)

    def _apply_config_to_widgets(self, config: AppConfig) -> None:
        # Programmatisches Setzen darf keinen Auto-Save auslösen.
        self._suppress_save = True
        try:
            for field, _ in SENDER_FIELDS:
                self.sender_section.vars[field].set(getattr(config.sender, field))

            # Die Zugangsdaten stehen bewusst NICHT in der Config und werden
            # hier deshalb auch nicht gesetzt: ein Neuladen der Datei (externe
            # Änderung) darf nicht löschen, was der Nutzer gerade getippt hat.
            self.output_section.address_export.set(config.lookup.address_export)

            self.filter_section.set_priority(
                config.generation.via_priority, config.generation.via_cut
            )
            self.mode_section.card_mode.set(config.generation.card_mode)
            self.printmode_section.print_mode.set(config.generation.print_mode)
            self.printmode_section.sheet_mode.set(
                normalize_sheet_mode(config.generation.sheet_mode)
            )
            self.printmode_section.qr_code.set(bool(config.generation.qr_code))
            # Druckrand: Umschalter + die vier Randfelder (Feldname in der
            # Section = Config-Feld ohne das „print_"-Präfix).
            self.printmode_section.advanced.set(config.generation.print_margin_enabled)
            for name, var in self.printmode_section.margin_vars.items():
                value = clamp_print_margin(getattr(config.generation, f"print_{name}"))
                var.set(f"{value:g}")
            # Sichtbarkeit des Randblocks an den geladenen Zustand angleichen.
            self.printmode_section.update_advanced_visibility()
            self.sender_section.qsl_mark.set(
                QSL_CODE_TO_DISPLAY.get(config.generation.qsl_mark, "Leer lassen")
            )
            self.sender_section.confirm_mark.set(
                CONFIRM_CODE_TO_DISPLAY.get(config.generation.confirm_mark, "Leer lassen")
            )
            self.remarks_section.remarks.set(config.generation.remarks)
            self._last_remarks_built = config.generation.remarks

            self.mostwanted_section.enabled.set(config.mostwanted.enabled)
            self.mostwanted_section.top.set(str(mostwanted.clamp_top(config.mostwanted.top)))
            self.mostwanted_section.set_category(config.mostwanted.category)

            self.source_section.kind.set(
                config.source.kind if config.source.kind in ("file", "wavelog") else "file"
            )
            wl = config.wavelog
            self.lookup_section.remember.set(bool(config.lookup.remember))
            self.wavelog_section.url.set(wl.url)
            self.wavelog_section.remember_key.set(bool(wl.remember_key))
            self.wavelog_section.since.set(wl.qso_since)
            self.wavelog_section.until.set(wl.qso_until)
            self.wavelog_mark_section.mark_sent.set(bool(wl.mark_sent))

            # Menü-Zustand (Farbthema-Markierung, „Zuletzt verwendet") nachziehen.
            self.menubar.set_theme_mode(config.appearance.theme)
            self.menubar.set_recent(config.recent.logs, config.recent.images)
        finally:
            self._suppress_save = False

    def _gather_config(self) -> AppConfig:
        sender = SenderConfig(
            **{field: self.sender_section.vars[field].get() for field, _ in SENDER_FIELDS}
        )
        lookup = LookupConfig(
            program_id=self.base_config.lookup.program_id,
            address_export=self.output_section.address_export.get(),
            remember=self.lookup_section.remember.get(),
        )
        via_priority, via_cut = self.filter_section.get_priority()
        generation = GenerationConfig(
            card_mode=self.mode_section.card_mode.get(),
            via_priority=via_priority,
            via_cut=via_cut,
            default_via=self.base_config.generation.default_via,
            page_orientation=self.base_config.generation.page_orientation,
            print_mode=self.printmode_section.print_mode.get(),
            sheet_mode=normalize_sheet_mode(self.printmode_section.sheet_mode.get()),
            print_margin_enabled=self.printmode_section.advanced.get(),
            **{
                f"print_{name}": clamp_print_margin(parse_mm(var.get()))
                for name, var in self.printmode_section.margin_vars.items()
            },
            static_footer=self.base_config.generation.static_footer,
            remarks=self.remarks_section.remarks.get(),
            qsl_mark=QSL_MARK_TO_CODE.get(self.sender_section.qsl_mark.get(), "none"),
            confirm_mark=CONFIRM_MARK_TO_CODE.get(self.sender_section.confirm_mark.get(), "none"),
            qr_code=self.printmode_section.qr_code.get(),
        )
        most_wanted = MostWantedConfig(
            enabled=self.mostwanted_section.enabled.get(),
            top=self.mostwanted_section.top_value(),
            category=self.mostwanted_section.category_code(),
        )
        # Aussehen und „Zuletzt verwendet" haben keine Eingabefelder: sie werden
        # aus der Basis-Config übernommen, damit der Auto-Save sie nicht verliert.
        return AppConfig(
            sender=sender,
            lookup=lookup,
            generation=generation,
            mostwanted=most_wanted,
            appearance=AppearanceConfig(theme=self.base_config.appearance.theme),
            recent=RecentConfig(
                logs=list(self.base_config.recent.logs),
                images=list(self.base_config.recent.images),
            ),
            source=SourceConfig(kind=self.source_section.kind.get()),
            wavelog=WavelogConfig(
                url=self.wavelog_section.url.get().strip(),
                station_id=self.wavelog_section.selected_station_id()
                or self.base_config.wavelog.station_id,
                remember_key=self.wavelog_section.remember_key.get(),
                qso_since=self.wavelog_section.since.get().strip(),
                qso_until=self.wavelog_section.until.get().strip(),
                mark_sent=self.wavelog_mark_section.mark_sent.get(),
            ),
        )

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
            self.sender_section.confirm_mark,
            self.remarks_section.remarks,
            # Die Zugangsdaten fehlen hier mit Absicht: sie werden nicht
            # gespeichert, ein Tastendruck im Passwortfeld darf keinen
            # Schreibvorgang auslösen.
            self.output_section.address_export,
            self.mode_section.card_mode,
            self.printmode_section.print_mode,
            self.printmode_section.sheet_mode,
            self.printmode_section.qr_code,
            self.printmode_section.advanced,
            *self.printmode_section.margin_vars.values(),
            self.mostwanted_section.enabled,
            self.mostwanted_section.top,
            self.mostwanted_section.category,
            # Wavelog: alles außer dem API-Key (der geht höchstens in den
            # Schlüsselbund, siehe `_on_remember_key_toggle`).
            self.source_section.kind,
            self.wavelog_section.url,
            self.wavelog_section.station,
            self.wavelog_section.remember_key,
            self.lookup_section.remember,
            self.wavelog_section.since,
            self.wavelog_section.until,
            self.wavelog_mark_section.mark_sent,
        ]
        for var in watched:
            var.trace_add("write", self._on_var_change)
        # Die Prioritätsliste (Abschnitt 4) hat keine tk.Variable; ihr Auto-Save
        # läuft über _on_priority_move (an die ▲/▼-Buttons gebunden).

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
        """Sammelt die Config und schreibt sie; hält _last_mtime aktuell."""
        config = self._gather_config()
        try:
            cfg.save(config, CONFIG_PATH)
        except OSError as exc:
            self.status.set(f"Speichern fehlgeschlagen: {exc}", "error")
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
        except (OSError, cfg.ConfigError) as exc:
            # Extern halb geschrieben oder von Hand verdorben: die Einstellungen
            # im Fenster bleiben gültig. mtime merken, sonst meldet der nächste
            # Poll alle 1,5 s dasselbe; der nächste Auto-Save repariert die Datei.
            self._last_mtime = self._config_mtime()
            self.status.set(
                f"Config-Datei nicht lesbar, behalte die aktuellen Werte ({exc})", "error"
            )
            return
        previous_theme = self.base_config.appearance.theme
        self.base_config = config
        self._apply_config_to_widgets(config)  # unterdrückt Auto-Save intern
        if config.appearance.theme != previous_theme:
            self._apply_theme(config.appearance.theme)
        self._last_mtime = self._config_mtime()
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

    def _update_thumbnail(self, path: str) -> None:
        try:
            with Image.open(path) as img:
                img.thumbnail(THUMB_MAX)
                self._thumb = ImageTk.PhotoImage(img)
        except (OSError, ValueError) as exc:
            self.image_section.thumb_label.config(text=f"(Bild-Fehler: {exc})", image="")
            self._thumb = None
            return
        self.image_section.thumb_label.config(image=self._thumb, text="")

    # ---------------------------------------------------------- Karten
    def _active_via_priority(self) -> list[str]:
        """Die aktiven Wege (über der Trennlinie) in Prioritätsreihenfolge."""
        priority, cut = self.filter_section.get_priority()
        return active_via_priority(priority, cut)

    def _mostwanted_filter(self) -> mostwanted.MostWantedFilter:
        """Die aktuelle Most-Wanted-Regel aus Abschnitt 7 (auch wenn sie aus ist)."""
        return mostwanted.MostWantedFilter(
            self.mostwanted_list,
            top=self.mostwanted_section.top_value(),
            category=self.mostwanted_section.category_code(),
        )

    def _included_default(self, card) -> bool:
        """Drucken-Voreinstellung: ein aktiver Weg passt **und**, falls der
        Most-Wanted-Filter an ist, das Gebiet liegt unter den ersten N."""
        rule = self._mostwanted_filter() if self.mostwanted_section.enabled.get() else None
        return is_printable(card, self._active_via_priority(), rule)

    def _mostwanted_rank(self):
        """Rang je Karte für die Spalte „MW" — oder None, solange es keine Liste
        gibt (dann bleibt die Spalte leer statt überall „–" zu zeigen)."""
        if self.mostwanted_list is None:
            return None
        rule = self._mostwanted_filter()
        return lambda card: mostwanted_rank(card, rule)

    def _visible_qsos(self) -> list:
        """Die QSOs, für die Karten gebaut werden: offene plus — falls
        eingeblendet — die schon gesendeten."""
        return self.session.visible_qsos(self.preview.show_sent.get())

    def _update_show_sent(self) -> None:
        """Beschriftung/Zustand von „Schon gesendete anzeigen" nachziehen."""
        count = len(self.sent_qsos)
        check = self.preview.show_sent_check
        check.configure(
            text=f"Schon gesendete anzeigen ({count})" if count else "Schon gesendete anzeigen",
            state="normal" if count else "disabled",
        )
        if not count and self.preview.show_sent.get():
            self.preview.show_sent.set(False)

    def _on_show_sent_toggle(self, *_args) -> None:
        """Gesendete ein-/ausgeblendet: Karten neu bauen; fehlende Lookups holen."""
        if self.preview.show_sent.get():
            if self.session.missing_lookups(show_sent=True):
                # Alle offenen mitgeben: ein laufender Lookup wird durch diesen
                # ersetzt, der Cache macht die schon geholten sofort wieder gültig.
                self._start_lookups(self._lookup_calls_needed())
                return
        self._rebuild_cards()

    def _build_all_cards(self) -> list:
        """Karten der offenen QSOs plus (eingeblendet) eigene Karten der schon
        gesendeten — nie gemischt, damit eine Nachdruck-Karte nicht neue QSOs
        mitnimmt und umgekehrt."""
        config = self._gather_config()
        resolve = self.cty.dxcc if self.cty is not None else None
        cards = build_cards(self.qsos, config, self.lookups, resolve_dxcc=resolve)
        if self.preview.show_sent.get() and self.sent_qsos:
            again = build_cards(self.sent_qsos, config, self.lookups, resolve_dxcc=resolve)
            for card in again:
                card.already_sent = True
            cards += again
        return cards

    def _rebuild_cards(self) -> None:
        if not self.qsos and not (self.sent_qsos and self.preview.show_sent.get()):
            self.preview.set_cards([])
            return
        cards = self._build_all_cards()
        self.preview.set_cards(
            cards,
            included=self._included_default,
            pending=self._lookup_running,
            groupable=self.mode_section.card_mode.get() == "per_station",
            active_priority=self._active_via_priority(),
            rank=self._mostwanted_rank(),
        )

    def _apply_filter(self) -> None:
        """Priorität oder Most-Wanted-Filter geändert: nur die Drucken-Markierung
        und die Anzeige neu setzen (kein Rebuild)."""
        self.preview.apply_print_filter(
            self._active_via_priority(), self._included_default, self._mostwanted_rank()
        )

    def _on_priority_move(self, direction: str) -> None:
        """▲/▼ in der Prioritätsliste: verschieben, dann Auto-Save + Filter neu.

        Die Listbox hat keine tk.Variable, daher wird der Auto-Save hier manuell
        angestoßen (wie bei den beobachteten Variablen)."""
        moved = (
            self.filter_section.move_up() if direction == "up" else self.filter_section.move_down()
        )
        if not moved:
            return
        self._apply_filter()
        self._on_var_change()

    def _on_remarks_commit(self, _event=None) -> None:
        """Globaler Remarks-Text bestätigt (Fokusverlust/Enter): Karten neu bauen,
        aber nur wenn sich der Text wirklich geändert hat (spart Rebuilds und
        erhält per-Karte-Überschreibungen bei unverändertem Text).

        Gibt es manuell geänderte Bemerkungen, fragt ein Dialog, ob diese vom neuen
        globalen Text überschrieben werden sollen. Bei „Nicht überschreiben" werden
        sie nach dem Rebuild wiederhergestellt (nur die manuellen Karten sind
        geschützt; alle übrigen übernehmen den neuen/geleerten globalen Text).
        """
        if self._remarks_dialog_open:
            return  # Re-Entrancy: Dialog hat den Fokus gestohlen
        value = self.remarks_section.remarks.get()
        if value == self._last_remarks_built:
            return

        keep: list = []
        manual = self.preview.manual_remark_cards()
        if manual:
            self._remarks_dialog_open = True
            try:
                overwrite = ask_overwrite_manual_remarks(self.remarks_section.frame)
            finally:
                self._remarks_dialog_open = False
            if not overwrite:
                keep = manual

        self._last_remarks_built = value
        self._rebuild_cards()
        self.preview.reapply_manual_remarks(keep)

    def _on_cell_edited(self, iid: str, card, column: str) -> None:
        """Nach einer Via-Bearbeitung die Drucken-Markierung der Zeile nachziehen
        (manuell erzwungener Weg -> drucken, sofern der Most-Wanted-Filter die
        Karte nicht ausschließt). Route-Edits ändern nur den
        Kartentext und lassen die Markierung unberührt."""
        if column == "via":
            self.preview.set_row_included(iid, self._included_default(card))

    # ------------------------------------------------- Most Wanted (async)
    def _init_mostwanted(self) -> None:
        """Beim Start: gespeicherte Liste und cty.dat lesen (lokal, ohne Netz)
        und — wenn der Filter an ist und etwas fehlt oder veraltet ist — neu
        abrufen. Die cty.dat gibt es immer: notfalls die mitgelieferte."""
        self.mostwanted_list = mostwanted.load(MOSTWANTED_PATH)
        self.cty = dxcc.load(CTY_PATH, BUNDLED_CTY_PATH, DXCC_NUMBERS_PATH)
        self._show_mostwanted_status()
        self._ensure_mostwanted()

    def _on_mostwanted_toggle(self, *_args) -> None:
        """Filter ein-/ausgeschaltet: beim Einschalten die Liste bei Bedarf holen
        (auch der Weg, einen gescheiterten Abruf zu wiederholen)."""
        if self._suppress_save:
            return
        self._ensure_mostwanted()
        self._on_mostwanted_change()

    def _on_mostwanted_change(self, *_args) -> None:
        """Top/Kategorie geändert: Statuszeile und Drucken-Markierung neu.

        Beim programmatischen Setzen (Config laden) passiert hier nichts — der
        Aufrufer zieht danach selbst nach (`_init_mostwanted`/`_reload_from_file`).
        """
        if self._suppress_save:
            return
        self._show_mostwanted_status()
        self._apply_filter()

    def _ensure_mostwanted(self) -> None:
        """Ruft GDXF-Liste und cty.dat im Hintergrund ab — nur bei
        eingeschaltetem Filter und nur, was fehlt oder veraltet ist (GDXF nach
        30, cty.dat nach 14 Tagen). Wer den Filter nicht nutzt, löst keinen
        Netzzugriff aus. Während des Abrufs ist „PDF erzeugen" gesperrt."""
        if self._mostwanted_running or not self.mostwanted_section.enabled.get():
            return
        if not mostwanted.is_stale(self.mostwanted_list) and not dxcc.is_stale(CTY_PATH):
            return
        self._mostwanted_running = True
        self._show_mostwanted_status()
        self._update_generate_state()
        threading.Thread(target=self._mostwanted_worker, daemon=True).start()

    def _mostwanted_worker(self) -> None:
        # Beide `refresh` fangen Netz-, HTTP- und Formatfehler selbst ab (nie
        # fatal) und rufen nur ab, was veraltet ist.
        ranking = mostwanted.refresh(MOSTWANTED_PATH)
        cty = dxcc.refresh(CTY_PATH, BUNDLED_CTY_PATH, DXCC_NUMBERS_PATH)
        self.after(0, self._mostwanted_done, ranking, cty)

    def _mostwanted_done(
        self, result: mostwanted.RefreshResult, cty: dxcc.CtyRefreshResult | None = None
    ) -> None:
        self._mostwanted_running = False
        self.mostwanted_list = result.ranking
        self._mostwanted_error = result.error
        self._update_generate_state()
        self._show_mostwanted_status()
        if cty is not None and cty.fetched and cty.database is not None:
            # Neue cty.dat: Gebiete können sich geändert haben (neue
            # DXpeditions-Rufzeichen) -> Karten neu aufbauen. Kommt höchstens
            # alle 14 Tage beim Einschalten vor.
            self.cty = cty.database
            self._rebuild_cards()
        else:
            self._apply_filter()

    def _show_mostwanted_status(self) -> None:
        """Statuszeile von Abschnitt 7: Jahrgang + Abrufdatum, oder was fehlt."""
        section = self.mostwanted_section
        ranking = self.mostwanted_list
        if self._mostwanted_running:
            section.set_status("Lade GDXF-Liste…")
        elif ranking is None and self._mostwanted_error:
            section.set_status("GDXF-Liste nicht abrufbar", error=True)
        elif ranking is None:
            section.set_status("Noch keine GDXF-Liste geladen")
        elif self._mostwanted_error:
            # Kurz gehalten: die Zeile steht rechts in einer einzigen Zeile über
            # die Fensterbreite, die längere Fassung lief dort über den Rand.
            date = _format_date(ranking.fetched_at)
            section.set_status(
                f"GDXF {ranking.year or '?'} · {date} · Abruf fehlgeschlagen", error=True
            )
        else:
            date = _format_date(ranking.fetched_at)
            section.set_status(f"GDXF {ranking.year or '?'} · abgerufen {date}")

    # ------------------------------------------------------- Lookup (async)
    def _lookup_credentials(self) -> LookupCredentials:
        """Zugangsdaten aus Abschnitt 6 — nur zur Laufzeit, nie aus der Config.

        `program_id` ist der einzige Teil, der in der Config steht (siehe
        `config.LookupConfig`).
        """
        return LookupCredentials(
            hamqth_user=self.lookup_section.hamqth_user.get(),
            hamqth_pass=self.lookup_section.hamqth_pass.get(),
            qrz_user=self.lookup_section.qrz_user.get(),
            qrz_pass=self.lookup_section.qrz_pass.get(),
            program_id=self.base_config.lookup.program_id,
        )

    # ---------------------------------------------- Sitzungszustand (Kurzwege)
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
    def _lookup_running(self) -> bool:
        return self._lookups.running

    def _start_lookups(self, calls: list[str], *, force: bool = False) -> None:
        """Schlägt `calls` im Hintergrund nach (Via/Manager/Adresse).

        Ohne Zugangsdaten passiert kein Netzcall: alle Via fallen auf den
        Standard. Während des Laufs ist „PDF erzeugen" gesperrt. Läuft schon
        ein Lookup (z. B. für das vorige Log), wird er abgebrochen und dieser
        startet direkt danach; dessen Ergebnisse werden verworfen (1.4).
        """
        if not calls:
            if self._lookup_running:
                self._lookups.cancel()
            self._rebuild_cards()
            return
        credentials = self._lookup_credentials()
        if not has_lookup_credentials(credentials):
            if self._lookups.busy:
                self._lookups.cancel()
            self._lookup_signature = None
            self._rebuild_cards()
            self.preview.set_status("Keine Lookup-Zugangsdaten – Via = Standard.")
            self._update_generate_state()
            return

        self._lookup_signature = self._credential_signature()
        self._lookups.start(
            calls,
            credentials,
            force=force,
            on_done=self._lookups_done,
            on_progress=self._lookups_progress,
        )
        self._rebuild_cards()  # zeigt „…" für Via/Route
        self.preview.set_status("Schlage Stationen nach…")
        self.status.set("Schlage Stationen nach…", "busy")
        self._update_lookup_buttons()
        self._update_generate_state()

    def _update_lookup_buttons(self) -> None:
        running = self._lookup_running
        self.preview.refresh_btn.config(state="disabled" if running else "normal")
        self.preview.cancel_btn.config(state="normal" if running else "disabled")

    def _cancel_lookups(self) -> None:
        """„Abbrechen": laufenden Lookup stoppen; Gefundenes bleibt erhalten."""
        if self._lookups.cancel():
            self.preview.set_status("Breche Lookup ab…")

    def _lookup_calls_needed(self) -> list[str]:
        """Alle Rufzeichen der angezeigten QSOs (inkl. eingeblendeter gesendeter)."""
        return [q.call for q in self._visible_qsos()]

    def _refresh_lookups(self) -> None:
        """„Neu abrufen": offene (nicht aufgelöste) Stationen erneut versuchen;
        sind alle aufgelöst, wird ein vollständiger Force-Refresh gemacht."""
        if self._lookup_running or not self.qsos:
            return
        calls = self._lookup_calls_needed()
        unresolved = [c for c in calls if self.lookups.get((c or "").strip().upper()) is None]
        self._start_lookups(unresolved or calls, force=True)

    def _lookups_progress(self, progress: LookupProgress) -> None:
        eta = format_eta(progress.eta_seconds)
        text = f"Schlage Stationen nach… {progress.done}/{progress.total}"
        self.preview.set_status(f"{text} · {eta}" if eta else text)

    def _lookups_done(self, outcome: LookupOutcome) -> None:
        self.lookups.update(outcome.results)
        self._rebuild_cards()
        self._update_lookup_buttons()
        self._update_generate_state()

        auth_errors = outcome.auth_errors
        self.lookup_section.mark_auth_failed(auth_errors)
        if auth_errors:
            self._report_auth_errors(auth_errors)
            return

        calls = {(q.call or "").strip().upper() for q in self._visible_qsos() if q.call}
        total = len(calls)
        found = sum(1 for c in calls if self.lookups.get(c) is not None)
        if outcome.cancelled:
            text = (
                f"Lookup abgebrochen – {found}/{total} Stationen gefunden. "
                "„Neu abrufen“ holt den Rest."
            )
            self.preview.set_status(text)
            self.status.set(text, "error")
            return
        self.preview.set_status(f"Lookup fertig – {found}/{total} Stationen gefunden.")
        self.status.set(f"Lookup fertig – {found}/{total} Stationen gefunden.", "ok")

    def _report_auth_errors(self, auth_errors: dict) -> None:
        """Warnt, wenn ein Anbieter die Zugangsdaten abgelehnt hat.

        Ohne diesen Hinweis sähe der Nutzer nur „0 Stationen gefunden" und
        hätte keinen Anhaltspunkt, dass sein Passwort das Problem ist.
        """
        names = " und ".join(auth_errors)
        short = f"Anmeldung bei {names} fehlgeschlagen – Zugangsdaten prüfen."
        self.preview.set_status(short)
        self.status.set(short, "error")
        self._goto_section(6)
        details = "\n".join(f"• {provider}: {message}" for provider, message in auth_errors.items())
        messagebox.showwarning(
            "Anmeldung fehlgeschlagen",
            "Die Zugangsdaten wurden vom Anbieter abgelehnt:\n\n"
            f"{details}\n\n"
            "Bitte in Abschnitt 6 (Lookups) prüfen. Ohne Anmeldung bleiben alle "
            "Zustellwege auf dem Standard.",
        )

    def _update_generate_state(self) -> None:
        busy = self._lookup_running or self._mostwanted_running or self._generating
        self.output_section.generate_btn.config(state="disabled" if busy else "normal")
        self.menubar.set_generate_enabled(not busy)

    def _clear_lookup_cache(self) -> None:
        """Menü „Aktionen": die Cache-Datei löschen (nach Rückfrage).

        Danach fragt der nächste Lookup wieder frisch beim Anbieter nach — nützlich,
        wenn sich Routing-Daten einer Station geändert haben.
        """
        path = Path(DEFAULT_CACHE_PATH)
        if not path.exists():
            self.status.set("Kein Lookup-Cache vorhanden.", "info")
            return
        if not confirm(
            self,
            "Lookup-Cache leeren",
            f"Die Datei „{path.name}“ wird gelöscht.\n"
            "Beim nächsten Lookup werden alle Stationen neu abgefragt.",
            ok_label="Löschen",
        ):
            return
        try:
            path.unlink()
        except OSError as exc:
            self.status.set(f"Cache konnte nicht gelöscht werden: {exc}", "error")
            return
        self.status.set("Lookup-Cache geleert.", "ok")

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

    def _credential_signature(self) -> tuple:
        c = self._lookup_credentials()
        return (c.qrz_user, c.qrz_pass, c.hamqth_user, c.hamqth_pass)

    def _maybe_restart_lookups(self) -> None:
        """Nach Schritt 3: wurden (andere) Zugangsdaten eingegeben, als beim
        Laden des Logs da waren, jetzt neu nachschlagen."""
        if not self.qsos and not self.sent_qsos:
            return
        if not has_lookup_credentials(self._lookup_credentials()):
            return
        if self._lookup_signature == self._credential_signature():
            return
        self.lookups = {}
        self._start_lookups(self._lookup_calls_needed())

    # --------------------------------------------------------- Wavelog
    def _wavelog_client(self) -> wavelog.WavelogClient:
        """Client für Adresse + Key; derselbe, solange sich beides nicht ändert.

        Wiederverwendet, weil `stations()` beim ersten Kontakt lernen kann, dass
        die Instanz ohne `index.php` antwortet — das soll für QSOs und
        Markieren gelten.
        """
        url, key = self.wavelog_section.url.get(), self.wavelog_section.key.get()
        cached = getattr(self, "_wavelog_client_cache", None)
        if cached is not None and cached[0] == (url, key):
            return cached[1]
        client = wavelog.WavelogClient(url, key)
        self._wavelog_client_cache = ((url, key), client)
        return client

    def _wavelog_api(self) -> str:
        try:
            return wavelog.normalize_base_url(self.wavelog_section.url.get())
        except wavelog.WavelogError:
            return ""

    def _restore_wavelog_key(self) -> None:
        """Beim Start: einen gemerkten API-Key aus dem Schlüsselbund holen."""
        if not self.wavelog_section.remember_key.get():
            return
        key = wavelog_secret.load_key(self.wavelog_section.url.get())
        if key:
            self.wavelog_section.key.set(key)

    def _restore_lookup_credentials(self) -> None:
        """Beim Start: gemerkte QRZ-/HamQTH-Zugänge aus dem Schlüsselbund (2.3)."""
        if not self.lookup_section.remember.get():
            return
        section = self.lookup_section
        for provider, user_var, pass_var in (
            ("qrz", section.qrz_user, section.qrz_pass),
            ("hamqth", section.hamqth_user, section.hamqth_pass),
        ):
            user, password = lookup_secret.load(provider)
            if user and not user_var.get():
                user_var.set(user)
                pass_var.set(password)

    def _store_lookup_credentials(self) -> None:
        """Zugänge in den Schlüsselbund (nur mit Haken), sonst nichts."""
        if not self.lookup_section.remember.get():
            return
        c = self._lookup_credentials()
        lookup_secret.save("qrz", c.qrz_user, c.qrz_pass)
        lookup_secret.save("hamqth", c.hamqth_user, c.hamqth_pass)

    def _on_remember_lookup_toggle(self, *_args) -> None:
        if self._suppress_save:
            return
        if self.lookup_section.remember.get():
            self._store_lookup_credentials()
        else:
            for provider in lookup_secret.PROVIDERS:
                lookup_secret.delete(provider)

    def _on_remember_key_toggle(self, *_args) -> None:
        if self._suppress_save:
            return
        url = self.wavelog_section.url.get()
        if self.wavelog_section.remember_key.get():
            wavelog_secret.save_key(url, self.wavelog_section.key.get())
        else:
            wavelog_secret.delete_key(url)

    def _set_wavelog_busy(self, busy: bool) -> None:
        self._wavelog_busy = busy
        state = "disabled" if busy else "normal"
        self.wavelog_section.load_stations_btn.configure(state=state)
        self.wavelog_section.load_qsos_btn.configure(
            state="disabled" if busy or not self._wavelog_stations else "normal"
        )
        self._update_mark_state()

    def _run_wavelog(self, work, done) -> None:
        """`work(client)` im Hintergrund, `done(result, error)` im UI-Thread."""
        try:
            client = self._wavelog_client()
        except wavelog.WavelogError as exc:
            self.status.set(str(exc), "error")
            self.wizard.show_problem(str(exc))
            return
        self._set_wavelog_busy(True)

        def worker() -> None:
            try:
                result = work(client)
            except wavelog.WavelogError as exc:
                self.after(0, done, None, exc)
                return
            except Exception as exc:  # bewusst breit: nie den Thread sterben lassen
                self.after(0, done, None, wavelog.WavelogError(str(exc)))
                return
            self.after(0, done, result, None)

        threading.Thread(target=worker, daemon=True).start()

    def _wavelog_load_stations(self) -> None:
        # Token im Klartext über fremdes Netz? Deutlich sagen (2.1), nicht sperren.
        self.wavelog_section.set_warning(insecure_url_warning(self.wavelog_section.url.get()) or "")
        self.status.set("Lade Stationen aus Wavelog…", "busy")
        if self.wavelog_section.remember_key.get():
            wavelog_secret.save_key(self.wavelog_section.url.get(), self.wavelog_section.key.get())
        self._run_wavelog(lambda client: client.stations(), self._wavelog_stations_done)

    def _wavelog_stations_done(self, stations, error) -> None:
        self._set_wavelog_busy(False)
        if error is not None:
            self.status.set(str(error), "error")
            self.wizard.show_problem(str(error))
            return
        self._wavelog_stations = list(stations)
        self.wavelog_section.set_stations(stations, self.base_config.wavelog.station_id)
        self._set_wavelog_busy(False)
        if not stations:
            self.status.set("Wavelog: keine Stationsstandorte gefunden.", "error")
            return
        self.wavelog_section.set_missing(False)
        self.status.set(f"Wavelog: {len(stations)} Station(en) geladen.", "ok")
        self.wizard.show_hint("Station wählen, dann „QSOs laden“.")

    def _selected_wavelog_station(self) -> wavelog.WavelogStation | None:
        sid = self.wavelog_section.selected_station_id()
        return next((s for s in self._wavelog_stations if s.id == sid), None)

    def _on_wavelog_station_selected(self) -> None:
        self.wavelog_section.set_missing(False)
        self._on_var_change()

    def _wavelog_load_qsos(self) -> None:
        station = self._selected_wavelog_station()
        if station is None:
            self.wavelog_section.set_missing(True)
            self.wizard.show_problem("Bitte eine Station wählen.")
            return
        since = self.wavelog_section.since.get().strip()
        until = self.wavelog_section.until.get().strip()
        bad = [
            label for label, value in (("von", since), ("bis", until)) if not validate_date(value)
        ]
        self.wavelog_section.mark_dates(
            since_bad=not validate_date(since), until_bad=not validate_date(until)
        )
        if bad:
            problem = "Datum „" + "“/„".join(bad) + "“ bitte als JJJJ-MM-TT angeben."
            self.wizard.show_problem(problem)
            self.status.set(problem, "error")
            return
        if since and until and since > until:
            self.wavelog_section.mark_dates(since_bad=True, until_bad=True)
            self.wizard.show_problem("„von“ liegt nach „bis“.")
            return
        self.status.set(f"Lade QSOs von {station.callsign} aus Wavelog…", "busy")

        def progress(done: int, total: int) -> None:
            self.after(0, self.status.set, f"Lade QSOs aus Wavelog… {done}/{total}", "busy")

        self._run_wavelog(
            lambda client: client.qsos(station.id, since=since, until=until, progress_cb=progress),
            lambda qsos, error: self._wavelog_qsos_done(station, qsos, error),
        )

    def _wavelog_qsos_done(self, station, qsos, error) -> None:
        self._set_wavelog_busy(False)
        if error is not None:
            self.status.set(str(error), "error")
            self.wizard.show_problem(str(error))
            return
        # Schon gesendete Karten nie wieder drucken: was Wavelog als gesendet
        # meldet, und was dieses Programm selbst dort markiert hat (falls die
        # Instanz den Status beim Abruf nicht mitliefert).
        total = len(qsos)
        api = self._wavelog_api()
        warnings: list[str] = []
        store_broken = False
        try:
            marked = sent_store.load(WAVELOG_SENT_PATH, api)
            pending = sent_store.load_pending(WAVELOG_SENT_PATH, api)
        except sent_store.SentStoreError as exc:
            # Nie still weitermachen: ohne die Liste fehlt das Sicherheitsnetz.
            marked, pending, store_broken = set(), [], True
            warnings.append(
                f"Die Liste der hier markierten QSOs ist beschädigt ({exc}). Sie wird "
                "nicht überschrieben; bis zur Reparatur fehlt das Sicherheitsnetz."
            )
        status_known = reports_qsl_sent(qsos)

        def sent(q) -> bool:
            return paper_qsl_already_sent(q) or q.raw.get("wavelog_id") in marked

        self.session.load(qsos, "wavelog", sent)
        skipped = len(self.sent_qsos)
        self._sent_store_broken = store_broken
        # Offene Markierungen aus einem früheren Druck (auch nach Neustart).
        self._pending_marks = [wavelog.PaperQslMark(m.qso_id, m.via) for m in pending]
        self._prefill_sender_from_station(station)
        note = f" ({skipped} schon gesendet, ausgelassen)" if skipped else ""
        self.wavelog_section.count_var.set(f"{len(self.qsos)} QSOs geladen{note}")
        self.status.set_info(f"{len(self.qsos)} QSOs · Wavelog {station.callsign}")
        if total and not status_known:
            warnings.append(
                f"Achtung: Diese Wavelog-Instanz meldet den Versandstatus nicht mit. "
                f"Ausgelassen werden nur die {len(marked)} QSO(s), die dieses Programm "
                f"selbst markiert hat. Wurden QSOs in Wavelog von Hand oder von einem "
                f"anderen Rechner als gesendet gesetzt, stehen sie unter den "
                f"{len(self.qsos)} geladenen und würden noch einmal gedruckt."
            )
        self.wavelog_section.set_warning("\n\n".join(warnings), error=store_broken)
        if warnings:
            self.status.set("Wavelog: QSOs geladen – bitte Hinweis in Schritt 1 beachten.", "error")
        else:
            self.status.set(f"Wavelog: {len(self.qsos)} QSOs geladen{note}.", "ok")
        self.wizard.show_hint("")
        self.wizard.refresh()
        self.lookups = {}
        self._update_show_sent()
        self._update_mark_state()
        self._start_lookups(self._lookup_calls_needed())

    def _prefill_sender_from_station(self, station: wavelog.WavelogStation) -> None:
        """Leere Absenderfelder mit den Daten des Wavelog-Standorts füllen
        (nie überschreiben, was schon dasteht)."""
        for field, value in (
            ("callsign", station.callsign),
            ("locator", station.gridsquare),
            ("waz", station.cq),
            ("itu", station.itu),
        ):
            var = self.sender_section.vars[field]
            if value and not var.get().strip():
                var.set(value)

    def _marks_for(self, cards) -> list[wavelog.PaperQslMark]:
        """Die Wavelog-QSOs der gedruckten Karten, mit dem Zustellweg."""
        return marks_for_cards(cards, self._active_via_priority())

    def _save_pending_marks(self) -> None:
        """Offene Markierungen in `wavelog_sent.json` sichern (überlebt Neustart)."""
        if self.qsos_source != "wavelog" or getattr(self, "_sent_store_broken", False):
            return
        try:
            sent_store.set_pending(
                WAVELOG_SENT_PATH,
                self._wavelog_api(),
                [sent_store.PendingMark(m.qso_id, m.via) for m in self._pending_marks],
            )
        except (OSError, sent_store.SentStoreError) as exc:
            self.status.set(f"Offene Markierungen nicht gesichert: {exc}", "error")

    def _update_mark_state(self) -> None:
        section = self.wavelog_mark_section
        enabled = bool(self._pending_marks) and not self._wavelog_busy
        section.mark_now_btn.configure(state="normal" if enabled else "disabled")
        if self._pending_marks:
            section.status_var.set(f"{len(self._pending_marks)} QSO(s) warten auf Markierung")

    def _after_generate_wavelog(self) -> None:
        """Nach dem PDF: die QSOs der Karten in Wavelog als gesendet markieren
        (nach Rückfrage — die PDF könnte ja nur ein Probedruck sein)."""
        if self.qsos_source != "wavelog":
            return
        # Zu den noch offenen aus früheren Drucken dazu, und sofort sichern:
        # „erst Probedruck" + Programm schließen verliert sie sonst (2.2).
        self.session.add_pending(self._marks_for(getattr(self, "_generated_cards", [])))
        self._save_pending_marks()
        self._update_mark_state()
        if not self._pending_marks or not self.wavelog_mark_section.mark_sent.get():
            return
        if confirm(
            self,
            "In Wavelog markieren",
            f"{len(self._pending_marks)} QSO(s) in Wavelog als „Papier-QSL gesendet“ "
            "markieren?\n\nNur bestätigen, wenn die Karten wirklich verschickt werden.",
            ok_label="Markieren",
        ):
            self._wavelog_mark_pending()

    def _wavelog_mark_pending(self) -> None:
        marks = list(self._pending_marks)
        if not marks:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        self.status.set(f"Markiere {len(marks)} QSO(s) in Wavelog…", "busy")

        def progress(done: int, total: int) -> None:
            self.after(0, self.status.set, f"Markiere in Wavelog… {done}/{total}", "busy")

        self._run_wavelog(
            lambda client: client.mark_many(marks, date=today, progress_cb=progress),
            self._wavelog_mark_done,
        )

    def _wavelog_mark_done(self, result, error) -> None:
        self._set_wavelog_busy(False)
        if error is not None:
            self.status.set(str(error), "error")
            return
        done_ids, errors = result
        done = len(done_ids)
        if done_ids:
            # Merken (Sicherheitsnetz für den nächsten Abruf) und aus der
            # aktuellen Sitzung nehmen: gesendete Karten werden nie neu gedruckt.
            try:
                sent_store.add(WAVELOG_SENT_PATH, self._wavelog_api(), done_ids)
            except (OSError, sent_store.SentStoreError) as exc:
                self.status.set(f"Liste der gesendeten QSOs nicht speicherbar: {exc}", "error")
                messagebox.showwarning(
                    "Liste nicht gespeichert",
                    "Die QSOs sind in Wavelog markiert, aber die lokale Liste "
                    f"({Path(WAVELOG_SENT_PATH).name}) konnte nicht gespeichert "
                    f"werden:\n\n{exc}",
                    parent=self,
                )
            self.session.mark_sent(done_ids)
            self._update_show_sent()
            self._rebuild_cards()
            self.wavelog_section.count_var.set(f"{len(self.qsos)} offene QSOs")
        self.wavelog_mark_section.show_summary(done, errors)
        if errors:
            # Details stehen in der Zusammenfassung auf der Druckseite (kopierbar).
            self.status.set(f"Wavelog: {done} markiert, {len(errors)} Fehler.", "error")
        else:
            self.status.set(f"Wavelog: {done} QSO(s) als Papier-QSL gesendet markiert.", "ok")
        self.wavelog_mark_section.status_var.set(
            f"{done} QSO(s) markiert" + (f", {len(errors)} Fehler" if errors else "")
        )
        self._update_mark_state()

    # ---------------------------------------------------- PDF-Erzeugung
    def _check_required(self) -> tuple[list[str], int]:
        """Prüft alle Pflichtangaben und markiert die fehlenden in der Oberfläche.

        Geprüft werden Logbuch (1), Frontbild (2) und die Pflichtfelder des
        Absenders (3) — in einem Durchgang, damit der Nutzer nicht mehrmals auf
        denselben Fehler klickt. Liefert (Beschriftungen der fehlenden Angaben,
        Nummer des ersten betroffenen Abschnitts).
        """
        log = self.file_section.path_var.get().strip()
        if self.qsos_source == "wavelog":
            log_missing = not self._visible_qsos()
        else:
            log_missing = not self._visible_qsos() or not log or not Path(log).exists()
            self.file_section.set_missing(log_missing)

        front = self.image_section.path_var.get().strip()
        front_missing = not front or not Path(front).exists()
        self.image_section.set_missing(front_missing)

        missing_fields = self.sender_section.missing_required()
        self.sender_section.mark_missing(missing_fields)

        labels: list[str] = []
        if log_missing:
            labels.append("Logbuch")
        if front_missing:
            labels.append("Frontbild")
        labels += [SENDER_LABELS[f] for f in missing_fields]
        first_section = 1 if log_missing else 2 if front_missing else 3
        return labels, first_section

    def _on_generate(self) -> None:
        if self._lookup_running:
            messagebox.showinfo(
                "Lookup läuft", "Bitte warten, bis die Stationen nachgeschlagen sind."
            )
            return
        if self._mostwanted_running:
            messagebox.showinfo(
                "Most-Wanted-Liste lädt", "Bitte warten, bis die GDXF-Liste abgerufen ist."
            )
            return
        missing, first_section = self._check_required()
        if missing:
            # Kein Dialog mehr (Bewertung 2.5): der Assistent springt zur ersten
            # Stelle und nennt alles Fehlende in der Navigationsleiste; die
            # Felder sind rot markiert.
            self.status.set("Pflichtangaben fehlen – nichts erzeugt.", "error")
            self._goto_section(first_section)  # zur ersten betroffenen Stelle
            self.wizard.show_problem("Pflichtangaben fehlen: " + ", ".join(missing))
            return
        front = self.image_section.path_var.get().strip()
        cards = self.preview.included_cards()
        if not cards:
            messagebox.showwarning("Keine Karten", "Es sind keine Karten zum Erzeugen ausgewählt.")
            return
        output = self.output_section.output_var.get().strip()
        if not output:
            messagebox.showerror("Kein Ziel", "Bitte einen Ausgabepfad angeben.")
            return

        self._generated_cards = list(cards)
        config = self._gather_config()
        self._generating = True
        self._update_generate_state()
        self.output_section.progress.config(maximum=len(cards), value=0)
        self.status.set("Erzeuge PDF…", "busy")

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
            outputs = generate(cards, config, front, output, progress_cb=progress)
        except Exception as exc:  # bewusst breit: Fehler nicht in den Thread schlucken
            self.after(0, self._generate_done, [output], exc)
            return
        self.after(0, self._generate_done, [str(p) for p in outputs], None)

    def _update_progress(self, done: int, total: int) -> None:
        # maximum mitziehen: im getrennten Modus sind es 2×Kartenzahl Schritte.
        self.output_section.progress.config(maximum=total, value=done)
        self.status.set(f"Erzeuge PDF… {done}/{total}", "busy")

    def _generate_done(self, outputs: list[str], error: Exception | None) -> None:
        self._generating = False
        self._update_generate_state()
        if error is not None:
            self.status.set(f"Fehler: {error}", "error")
            messagebox.showerror("Fehler", f"PDF-Erzeugung fehlgeschlagen:\n{error}")
            return
        # Erfolg: kein Popup — alle erzeugten PDFs (im getrennten Modus zwei) werden
        # direkt in der Standardanwendung geöffnet. Schlägt das Öffnen einer Datei
        # fehl, bleibt nur der Statushinweis.
        joined = ", ".join(outputs)
        try:
            for path in outputs:
                open_file(path)
            self.status.set(f"Fertig: {joined} (geöffnet)", "ok")
        except (OSError, subprocess.SubprocessError) as exc:
            self.status.set(f"Fertig: {joined}", "ok")
            messagebox.showinfo(
                "Fertig",
                f"PDF erzeugt:\n{joined}\n\n(Automatisches Öffnen nicht möglich: {exc})",
            )
        self._after_generate_wavelog()

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="PDF speichern unter", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")]
        )
        if path:
            self.output_section.output_var.set(path)
