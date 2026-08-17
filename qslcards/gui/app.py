"""Hauptfenster: verdrahtet die Abschnitte mit config/builder/generator.

Keine Geschäftslogik hier — die GUI ruft nur die fertigen Bausteine auf.
Langlaufende Arbeit (PDF-Erzeugung) läuft im Worker-Thread; UI-Updates
ausschließlich über `self.after(...)` (Tkinter ist nicht thread-safe).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from qslcards import __version__, paths
from qslcards import config as cfg
from qslcards.cards.builder import build_cards, effective_via
from qslcards.config import (
    AppConfig,
    AppearanceConfig,
    GenerationConfig,
    LookupConfig,
    RecentConfig,
    SenderConfig,
    push_recent,
)
from qslcards.logbook import LogFormatError, parse_file
from qslcards.lookup import (
    DEFAULT_CACHE_PATH,
    LookupCredentials,
    active_via_priority,
    has_lookup_credentials,
    lookup_calls,
)
from qslcards.pdf.generator import generate
from qslcards.pdf.geometry import clamp_print_margin, normalize_sheet_mode

from . import theme
from .help import HelpWindow, open_help
from .menu import MenuActions, MenuBar
from .preview import PreviewTable
from .scrolling import bind_wheel, wheel_step
from .sections import (
    SENDER_FIELDS,
    SENDER_LABELS,
    FileSection,
    FilterSection,
    ImageSection,
    LookupSection,
    ModeSection,
    OutputSection,
    PrintModeSection,
    RemarksSection,
    SenderSection,
    StatusBar,
    add_section_help,
    ask_overwrite_manual_remarks,
    confirm,
    parse_mm,
    required_legend,
    show_about_dialog,
)
from .textedit import install_entry_shortcuts

# Aus der Quelle die Projektwurzel, gebündelt der Programm- bzw. Benutzerordner
# (siehe `paths.data_dir`). Bleiben bewusst Modulattribute: die Tests setzen sie um.
CONFIG_PATH = str(paths.config_path())
EXAMPLE_CONFIG_PATH = str(paths.example_config_path())

# Fenster-/Programm-Icon: die von `scripts/make_icon.py` gerenderten PNGs.
ICON_DIR = paths.resource_path("qslcards", "assets", "icons")
# GRÖSSTE ZUERST: `wm iconphoto` auf macOS nimmt das erste Bild und skaliert es
# auf die jeweils gebrauchte Größe. Steht dort ein kleines, wirkt das Dock-Icon
# verpixelt. Windows/X11 suchen sich aus der Liste die passende Größe.
ICON_SIZES = (1024, 512, 256, 128, 64, 48, 32, 16)


def open_file(path: str) -> None:
    """Öffnet `path` mit der Standardanwendung des Betriebssystems.

    Plattformübergreifend (Windows, macOS, Linux/Debian). Fehler werden nach
    oben gereicht, damit der Aufrufer bei Bedarf einen Hinweis anzeigen kann.

    `env=paths.subprocess_env()`: im gebündelten Betrieb zeigen `LD_LIBRARY_PATH`
    bzw. `DYLD_LIBRARY_PATH` in die Anwendung, und ein davon geerbtes `xdg-open`
    lädt die falschen Bibliotheken.
    """
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # nur unter Windows
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=True, env=paths.subprocess_env())
    else:
        subprocess.run(["xdg-open", path], check=True, env=paths.subprocess_env())


def reveal_in_file_manager(path: str) -> None:
    """Zeigt `path` im Dateimanager (Finder/Explorer/Dateien) an.

    macOS: `open -R` markiert die Datei; Windows: `explorer /select,`; Linux
    (Debian/Fedora): es gibt keinen portablen „auswählen"-Aufruf, daher wird der
    enthaltende Ordner geöffnet.
    """
    target = Path(path)
    env = paths.subprocess_env()
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(target)], check=True, env=env)
    elif sys.platform.startswith("win"):
        # explorer liefert auch im Erfolgsfall != 0 -> Rückgabewert ignorieren.
        subprocess.run(["explorer", f"/select,{target}"], check=False, env=env)
    else:
        folder = target if target.is_dir() else target.parent
        subprocess.run(["xdg-open", str(folder)], check=True, env=env)


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


def load_icon(widget: tk.Misc, size: int) -> tk.PhotoImage | None:
    """Lädt ein einzelnes Icon-PNG; fehlt es, gibt es `None` (nie fatal)."""
    try:
        return tk.PhotoImage(master=widget, file=str(ICON_DIR / f"app_icon_{size}.png"))
    except (tk.TclError, OSError):
        return None


def load_app_icons(widget: tk.Misc) -> list[tk.PhotoImage]:
    """Icon-Bilder für `wm iconphoto`, **größtes zuerst**.

    Auf macOS bekommt Tk bewusst nur das größte Bild: die dortige Umsetzung
    skaliert das erste übergebene Bild auf alle gebrauchten Größen, und aus
    einem kleinen PNG wird dabei ein sichtbar verpixeltes Dock-Icon.
    Windows/X11 dagegen profitieren von mehreren Größen, weil der
    Fenstermanager sich die passende heraussucht.
    """
    sizes = ICON_SIZES[:1] if sys.platform == "darwin" else ICON_SIZES
    icons = [load_icon(widget, size) for size in sizes]
    return [icon for icon in icons if icon is not None]


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
        # Mausrad überall im Fenster (bind_all) -> Seite scrollen. Welche
        # Ereignisse die Plattform dafür liefert, entscheidet `bind_wheel`.
        bind_wheel(self.canvas, self._on_mousewheel, everywhere=True)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        # Inneres Frame auf Canvas-Breite ziehen (horizontal füllen).
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Mausrad/Trackpad -> Seite scrollen (Schrittweite siehe `scrolling`)."""
        step = wheel_step(event)
        if step:
            self.canvas.yview_scroll(step, "units")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("QSL-Karten-Generator")
        self.geometry("1000x780")
        self.minsize(720, 480)

        # Zustand
        self.qsos: list = []
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

        # Lookup-Zustand: Map CALL -> LookupResult|None (Via/Manager/Adresse).
        self.lookups: dict = {}
        self._lookup_running = False
        self._generating = False

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

        self._build_ui()
        self._build_menu()
        # Die klassischen tk-Widgets (Listbox, Canvas, Menüs) entstehen erst im
        # UI-Aufbau und werden von ttk-Styles nicht erfasst — sie bekommen ihre
        # Farben hier. Ohne diesen Aufruf behielte z.B. die Prioritätsliste die
        # Auswahlfarbe des Betriebssystems.
        theme.restyle_tree(self, self.palette)
        self._wire_commands()
        self._apply_config_to_widgets(self.base_config)
        self._last_mtime = self._config_mtime()
        self._wire_autosave()
        self.after(POLL_MS, self._poll_config)

    # ---------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        # Statusleiste zuerst packen (side="bottom"), damit sie beim Verkleinern
        # des Fensters stehen bleibt und der scrollbare Rest darüber schrumpft.
        self.status = StatusBar(self)
        self.status.frame.pack(side="bottom", fill="x")
        ttk.Separator(self, orient="horizontal").pack(side="bottom", fill="x")
        # Fußnote zum Stern: sie steht außerhalb des scrollbaren Bereichs, weil
        # sie für das ganze Fenster gilt (Abschnitte 1, 2 und 3) — in Abschnitt 3
        # sah sie aus, als beträfe sie nur den Absender.
        self.required_legend = required_legend(self)
        self.required_legend.pack(
            side="bottom", anchor="w", padx=theme.PAD_SECTION, pady=(0, theme.GAP_ROW)
        )

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
        self.remarks_section = RemarksSection(root)
        self.preview = PreviewTable(root, palette=self.palette)
        self.printmode_section = PrintModeSection(root)
        self.output_section = OutputSection(root)

        pad = theme.PAD_SECTION
        self._left.grid(row=0, column=0, padx=(pad, pad // 2), pady=(pad, 0), sticky="nsew")
        self.sender_section.frame.grid(
            row=0, column=1, padx=(pad // 2, pad), pady=(pad, 0), sticky="nsew"
        )
        self._midleft.grid(row=1, column=0, padx=(pad, pad // 2), pady=(pad, 0), sticky="nsew")
        self.lookup_section.frame.grid(
            row=1, column=1, padx=(pad // 2, pad), pady=(pad, 0), sticky="nsew"
        )
        # Abschnitt 7 (Remarks) über volle Breite, dann Vorschau (8), Druckmodus (9)
        # und Ausgabe (10).
        for section, row, fill in (
            (self.remarks_section.frame, 2, "we"),
            (self.preview.frame, 3, "nsew"),
            (self.printmode_section.frame, 4, "we"),
            (self.output_section.frame, 5, "we"),
        ):
            section.grid(row=row, column=0, columnspan=2, padx=pad, pady=(pad, 0), sticky=fill)
        self.output_section.frame.grid_configure(pady=(pad, pad))

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)

        # Sprungziele für „Ansicht > Gehe zu Abschnitt" (Nummer -> Rahmen).
        self._sections: dict[int, ttk.LabelFrame] = {
            1: self.file_section.frame,
            2: self.image_section.frame,
            3: self.sender_section.frame,
            4: self.filter_section.frame,
            5: self.mode_section.frame,
            6: self.lookup_section.frame,
            7: self.remarks_section.frame,
            8: self.preview.frame,
            9: self.printmode_section.frame,
            10: self.output_section.frame,
        }

        # Kontexthilfe: jeder Abschnittstitel bekommt ein „?", das das Handbuch
        # beim zugehörigen Kapitel öffnet (Anker `abschnitt-N` in handbuch.md).
        for number, frame in self._sections.items():
            add_section_help(frame, lambda n=number: self._show_help(f"abschnitt-{n}"))

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
        # Nach einer Via-Bearbeitung die Drucken-Markierung der Zeile nachziehen.
        self.preview.on_cell_edited = self._on_cell_edited

    # ----------------------------------------------------------- Config
    def _read_config(self) -> AppConfig:
        """Liest `config.yaml` (ersatzweise die Beispieldatei); Defaults sonst.

        Wird vor dem UI-Aufbau gebraucht (Farbthema, Icon, „Zuletzt verwendet"),
        deshalb getrennt vom Setzen der Widget-Werte.
        """
        for path in (CONFIG_PATH, EXAMPLE_CONFIG_PATH):
            if Path(path).exists():
                try:
                    return cfg.load(path)
                except (OSError, ValueError):  # kaputte Datei -> Defaults
                    break
        return AppConfig()

    def _apply_config_to_widgets(self, config: AppConfig) -> None:
        # Programmatisches Setzen darf keinen Auto-Save auslösen.
        self._suppress_save = True
        try:
            for field, _ in SENDER_FIELDS:
                self.sender_section.vars[field].set(getattr(config.sender, field))

            # Die Zugangsdaten stehen bewusst NICHT in der Config und werden
            # hier deshalb auch nicht gesetzt: ein Neuladen der Datei (externe
            # Änderung) darf nicht löschen, was der Nutzer gerade getippt hat.
            self.lookup_section.address_export.set(config.lookup.address_export)

            self.filter_section.set_priority(
                config.generation.via_priority, config.generation.via_cut
            )
            self.mode_section.card_mode.set(config.generation.card_mode)
            self.printmode_section.print_mode.set(config.generation.print_mode)
            self.printmode_section.sheet_mode.set(
                normalize_sheet_mode(config.generation.sheet_mode)
            )
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
            address_export=self.lookup_section.address_export.get(),
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
        )
        # Aussehen und „Zuletzt verwendet" haben keine Eingabefelder: sie werden
        # aus der Basis-Config übernommen, damit der Auto-Save sie nicht verliert.
        return AppConfig(
            sender=sender,
            lookup=lookup,
            generation=generation,
            appearance=AppearanceConfig(theme=self.base_config.appearance.theme),
            recent=RecentConfig(
                logs=list(self.base_config.recent.logs),
                images=list(self.base_config.recent.images),
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
            self.lookup_section.address_export,
            self.mode_section.card_mode,
            self.printmode_section.print_mode,
            self.printmode_section.sheet_mode,
            self.printmode_section.advanced,
            *self.printmode_section.margin_vars.values(),
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
        except OSError:
            return
        previous_theme = self.base_config.appearance.theme
        self.base_config = config
        self._apply_config_to_widgets(config)  # unterdrückt Auto-Save intern
        if config.appearance.theme != previous_theme:
            self._apply_theme(config.appearance.theme)
        self._last_mtime = self._config_mtime()
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
        self.qsos = qsos
        self.file_section.set_missing(False)  # Markierung eines Druckversuchs weg
        self.file_section.count_var.set(f"{len(self.qsos)} QSOs geladen")
        self.status.set_info(f"{len(self.qsos)} QSOs · {Path(path).name}")
        self._remember_recent("logs", path)
        # Frische Lookups: alte Ergebnisse verwerfen und automatisch neu abrufen.
        self.lookups = {}
        self._start_lookups([q.call for q in self.qsos])

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

    def _included_default(self, card) -> bool:
        """Drucken-Voreinstellung: Karte druckbar, wenn ein aktiver Weg passt."""
        return effective_via(card, self._active_via_priority()) is not None

    def _rebuild_cards(self) -> None:
        if not self.qsos:
            self.preview.set_cards([])
            return
        cards = build_cards(self.qsos, self._gather_config(), self.lookups)
        self.preview.set_cards(
            cards,
            included=self._included_default,
            pending=self._lookup_running,
            groupable=self.mode_section.card_mode.get() == "per_station",
            active_priority=self._active_via_priority(),
        )

    def _apply_filter(self) -> None:
        """Priorität geändert: nur die Drucken-Markierung neu setzen (kein Rebuild)."""
        self.preview.apply_via_filter(self._active_via_priority())

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
        (manuell erzwungener Weg -> drucken). Route-Edits ändern nur den
        Kartentext und lassen die Markierung unberührt."""
        if column == "via":
            included = effective_via(card, self._active_via_priority()) is not None
            self.preview.set_row_included(iid, included)

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

    def _start_lookups(self, calls: list[str], *, force: bool = False) -> None:
        """Schlägt `calls` im Hintergrund nach (Via/Manager/Adresse).

        Ohne Zugangsdaten passiert kein Netzcall: alle Via fallen auf den
        Standard. Während des Laufs ist „PDF erzeugen" gesperrt.
        """
        if self._lookup_running or not calls:
            self._rebuild_cards()
            return
        credentials = self._lookup_credentials()
        if not has_lookup_credentials(credentials):
            self._rebuild_cards()
            self.preview.set_status("Keine Lookup-Zugangsdaten – Via = Standard.")
            self._update_generate_state()
            return

        self._lookup_running = True
        self._rebuild_cards()  # zeigt „…" für Via/Route
        self.preview.set_status("Schlage Stationen nach…")
        self.status.set("Schlage Stationen nach…", "busy")
        self.preview.refresh_btn.config(state="disabled")
        self._update_generate_state()

        thread = threading.Thread(
            target=self._lookups_worker,
            args=(list(calls), credentials, force),
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

    def _lookups_worker(self, calls, credentials, force) -> None:
        def progress(done: int, total: int) -> None:
            self.after(0, self.preview.set_status, f"Schlage Stationen nach… {done}/{total}")

        # Je Anbieter nur die erste Meldung — sonst stünde sie einmal pro Station da.
        auth_errors: dict[str, str] = {}

        def auth_error(provider: str, message: str) -> None:
            auth_errors.setdefault(provider, message)

        # lookup_calls fängt Netz-/Auth-Fehler ab (nie fatal).
        results = lookup_calls(
            calls,
            credentials,
            force=force,
            progress_cb=progress,
            auth_error_cb=auth_error,
        )
        self.after(0, self._lookups_done, results, auth_errors)

    def _lookups_done(self, results: dict, auth_errors: dict | None = None) -> None:
        self._lookup_running = False
        self.lookups.update(results)
        self._rebuild_cards()
        self.preview.refresh_btn.config(state="normal")
        self._update_generate_state()

        auth_errors = auth_errors or {}
        self.lookup_section.mark_auth_failed(auth_errors)
        if auth_errors:
            self._report_auth_errors(auth_errors)
            return

        total = len({(q.call or "").strip().upper() for q in self.qsos if q.call})
        found = sum(1 for r in self.lookups.values() if r is not None)
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
        busy = self._lookup_running or self._generating
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
        """Menü „Ansicht > Gehe zu Abschnitt": den Abschnitt nach oben scrollen."""
        target = self._sections.get(number)
        if target is None:
            return
        canvas = self.body.canvas
        canvas.update_idletasks()
        total = self.body.inner.winfo_height()
        if total <= 0:
            return
        # y des Abschnitts relativ zum inneren Frame -> Bruchteil für yview_moveto.
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

    # ---------------------------------------------------- PDF-Erzeugung
    def _check_required(self) -> tuple[list[str], int]:
        """Prüft alle Pflichtangaben und markiert die fehlenden in der Oberfläche.

        Geprüft werden Logbuch (1), Frontbild (2) und die Pflichtfelder des
        Absenders (3) — in einem Durchgang, damit der Nutzer nicht mehrmals auf
        denselben Fehler klickt. Liefert (Beschriftungen der fehlenden Angaben,
        Nummer des ersten betroffenen Abschnitts).
        """
        log = self.file_section.path_var.get().strip()
        log_missing = not self.qsos or not log or not Path(log).exists()
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
        missing, first_section = self._check_required()
        if missing:
            listed = "\n".join(f"• {label}" for label in missing)
            messagebox.showerror(
                "Pflichtangaben fehlen",
                f"Ohne diese Angaben lassen sich keine Karten drucken:\n\n{listed}",
            )
            self.status.set("Pflichtangaben fehlen – nichts erzeugt.", "error")
            self._goto_section(first_section)  # zur ersten betroffenen Stelle
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

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="PDF speichern unter", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")]
        )
        if path:
            self.output_section.output_var.set(path)
