"""Menüleiste des Hauptfensters (plattformübergreifend).

Enthält **keine** Geschäftslogik: `MenuBar` bekommt die Aktionen als Callbacks
(`MenuActions`) und meldet nur zurück, was angeklickt wurde — verdrahtet wird in
`app.py`, genauso wie bei den Abschnitten in `sections.py`.

Plattform-Eigenheiten, die hier gekapselt sind:

* **macOS**: Tastenkürzel mit ⌘ statt Ctrl; „Über…" und „Beenden" gehören ins
  Programm-Menü (`name="apple"` bzw. `tk::mac::Quit`), nicht in „Datei"/„Hilfe".
* **Windows/Linux (Debian, Fedora)**: Ctrl-Kürzel, „Beenden" in „Datei",
  „Über…" in „Hilfe".

Die Kürzel werden zusätzlich als echte Bindings am Fenster registriert — ein
`accelerator` ist nur Beschriftung, Tk löst davon nichts aus.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

from .theme import THEME_LABELS, THEME_MODES

IS_MAC = sys.platform == "darwin"

# Modifier für Tastenkürzel: Anzeige (im Menü) und Binding-Präfix.
_MOD_LABEL = "Command" if IS_MAC else "Ctrl"
_MOD_BIND = "Command" if IS_MAC else "Control"


def accelerator(key: str, *, shift: bool = False) -> str:
    """Beschriftung eines Kürzels, z.B. „Command-Shift-R" / „Ctrl+Shift+R"."""
    parts = [_MOD_LABEL, *(["Shift"] if shift else []), key.upper()]
    return ("-" if IS_MAC else "+").join(parts)


def binding(key: str, *, shift: bool = False) -> str:
    """Passendes Tk-Event zum Kürzel, z.B. „<Command-Shift-R>"."""
    parts = [_MOD_BIND, *(["Shift"] if shift else []), key.upper() if shift else key.lower()]
    return f"<{'-'.join(parts)}>"


def _noop(*_args: object) -> None:
    """Platzhalter, damit ein nicht gesetzter Callback nichts tut."""


@dataclass
class MenuActions:
    """Alle Aktionen der Menüleiste. `app.py` füllt sie mit seinen Methoden."""

    # Datei
    open_log: Callable[[], None] = _noop
    open_image: Callable[[], None] = _noop
    open_recent_log: Callable[[str], None] = _noop
    open_recent_image: Callable[[str], None] = _noop
    clear_recent: Callable[[], None] = _noop
    choose_output: Callable[[], None] = _noop
    generate: Callable[[], None] = _noop
    quit: Callable[[], None] = _noop
    # Aktionen
    reload_log: Callable[[], None] = _noop
    refresh_lookups: Callable[[], None] = _noop
    clear_lookup_cache: Callable[[], None] = _noop
    # Ansicht
    set_theme: Callable[[str], None] = _noop
    goto_section: Callable[[int], None] = _noop
    # Hilfe
    show_about: Callable[[], None] = _noop
    show_help: Callable[[str | None], None] = _noop
    open_config: Callable[[], None] = _noop
    reveal_output: Callable[[], None] = _noop
    reveal_cache: Callable[[], None] = _noop


# Abschnitte für „Ansicht > Gehe zu" (Nummer, Titel) — Reihenfolge wie im Fenster.
SECTIONS: list[tuple[int, str]] = [
    (1, "ADIF-Logbuch"),
    (2, "Frontbild"),
    (3, "Absender"),
    (4, "Zustellwege"),
    (5, "Kartenmodus"),
    (6, "Lookups"),
    (7, "Bemerkungen"),
    (8, "Vorschau"),
    (9, "Druckmodus"),
    (10, "Ausgabe"),
]

# Kürzel des Handbuchs: auf macOS ⌘? (dort das übliche Hilfe-Kürzel), sonst F1.
# Beides passt nicht in das Buchstaben-Schema von `accelerator()`/`binding()`.
HELP_ACCELERATOR = "Command-?" if IS_MAC else "F1"
HELP_BINDING = "<Command-question>" if IS_MAC else "<F1>"

_RECENT_EMPTY = "(noch nichts geöffnet)"


@dataclass
class _Entry:
    """Ein Menüeintrag mit Kürzel: Menü + Index, um ihn später zu (de)aktivieren."""

    menu: tk.Menu
    index: int


class MenuBar:
    """Baut die Menüleiste und hält die dynamischen Teile aktuell."""

    def __init__(self, root: tk.Tk, actions: MenuActions, *, theme_mode: str = "system") -> None:
        self.root = root
        self.actions = actions
        self.menubar = tk.Menu(root)
        self.theme_var = tk.StringVar(value=theme_mode)
        self._generate_entry: _Entry | None = None
        self._bindings: list[tuple[str, Callable[[], None]]] = []

        if IS_MAC:
            self._build_apple_menu()
        self._build_file_menu()
        self._build_edit_menu()
        self._build_action_menu()
        self._build_view_menu()
        self._build_help_menu()

        root.config(menu=self.menubar)
        self._apply_bindings()

    # ------------------------------------------------------------- Aufbau
    def _build_apple_menu(self) -> None:
        """macOS-Programm-Menü: „Über…" gehört dorthin, nicht unter „Hilfe"."""
        apple = tk.Menu(self.menubar, name="apple")
        apple.add_command(
            label="Über QSL-Karten-Generator", command=lambda: self.actions.show_about()
        )
        apple.add_separator()
        self.menubar.add_cascade(menu=apple)
        # ⌘Q läuft über den System-Handler, damit auch das Programm-Menü greift.
        try:
            self.root.createcommand("tk::mac::Quit", lambda: self.actions.quit())
        except tk.TclError:  # pragma: no cover - nur auf macOS vorhanden
            pass

    def _build_file_menu(self) -> None:
        menu = tk.Menu(self.menubar, tearoff=0)
        self._command(menu, "ADIF-Logbuch öffnen…", self.actions.open_log, key="o")
        self.recent_logs_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Zuletzt verwendete Logs", menu=self.recent_logs_menu)
        menu.add_separator()
        self._command(menu, "Frontbild wählen…", self.actions.open_image, key="b")
        self.recent_images_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Zuletzt verwendete Bilder", menu=self.recent_images_menu)
        menu.add_separator()
        self._command(menu, "Ausgabeziel wählen…", self.actions.choose_output, key="s", shift=True)
        self._command(menu, "PDF erzeugen", self.actions.generate, key="p")
        self._generate_entry = _Entry(menu, menu.index("end"))
        if not IS_MAC:
            menu.add_separator()
            self._command(menu, "Beenden", self.actions.quit, key="q")
        self.menubar.add_cascade(label="Datei", menu=menu)
        self.set_recent([], [])

    def _build_edit_menu(self) -> None:
        """Standard-Bearbeiten-Menü: schickt die virtuellen Events an das Widget
        mit dem Tastaturfokus. Ohne dieses Menü fehlen auf macOS die gewohnten
        ⌘X/⌘C/⌘V in den Eingabefeldern."""
        menu = tk.Menu(self.menubar, tearoff=0)
        for label, event, key in (
            ("Ausschneiden", "<<Cut>>", "x"),
            ("Kopieren", "<<Copy>>", "c"),
            ("Einfügen", "<<Paste>>", "v"),
        ):
            menu.add_command(
                label=label,
                accelerator=accelerator(key),
                command=lambda e=event: self._to_focused(e),
            )
        menu.add_separator()
        menu.add_command(
            label="Alles auswählen",
            accelerator=accelerator("a"),
            command=lambda: self._to_focused("<<SelectAll>>"),
        )
        self.menubar.add_cascade(label="Bearbeiten", menu=menu)

    def _build_action_menu(self) -> None:
        menu = tk.Menu(self.menubar, tearoff=0)
        self._command(menu, "Log neu laden", self.actions.reload_log, key="r")
        self._command(
            menu, "Lookups neu abrufen", self.actions.refresh_lookups, key="r", shift=True
        )
        menu.add_command(
            label="Lookup-Cache leeren…", command=lambda: self.actions.clear_lookup_cache()
        )
        self.menubar.add_cascade(label="Aktionen", menu=menu)

    def _build_view_menu(self) -> None:
        menu = tk.Menu(self.menubar, tearoff=0)
        theme_menu = tk.Menu(menu, tearoff=0)
        for mode in THEME_MODES:
            theme_menu.add_radiobutton(
                label=THEME_LABELS[mode],
                value=mode,
                variable=self.theme_var,
                command=lambda m=mode: self.actions.set_theme(m),
            )
        menu.add_cascade(label="Farbthema", menu=theme_menu)
        menu.add_separator()
        goto = tk.Menu(menu, tearoff=0)
        for number, title in SECTIONS:
            goto.add_command(
                label=f"{number}. {title}", command=lambda n=number: self.actions.goto_section(n)
            )
        menu.add_cascade(label="Gehe zu Abschnitt", menu=goto)
        self.menubar.add_cascade(label="Ansicht", menu=menu)

    def _build_help_menu(self) -> None:
        # `name="help"` ist auf macOS reserviert (Suchfeld) -> nur sonst nutzen.
        menu = tk.Menu(self.menubar, tearoff=0)
        # Das Handbuch (für Anwender) statt der technischen Projektdokumente.
        menu.add_command(
            label="Handbuch",
            accelerator=HELP_ACCELERATOR,
            command=lambda: self.actions.show_help(None),
        )
        self._bindings.append((HELP_BINDING, lambda: self.actions.show_help(None)))
        menu.add_separator()
        menu.add_command(label="config.yaml öffnen", command=lambda: self.actions.open_config())
        menu.add_command(
            label="Ausgabeordner anzeigen", command=lambda: self.actions.reveal_output()
        )
        menu.add_command(label="Lookup-Cache anzeigen", command=lambda: self.actions.reveal_cache())
        if not IS_MAC:  # auf macOS steht „Über…" im Programm-Menü
            menu.add_separator()
            menu.add_command(
                label="Über QSL-Karten-Generator", command=lambda: self.actions.show_about()
            )
        self.menubar.add_cascade(label="Hilfe", menu=menu)

    # ------------------------------------------------------------ Helfer
    def _command(
        self,
        menu: tk.Menu,
        label: str,
        action: Callable[[], None],
        *,
        key: str,
        shift: bool = False,
    ) -> None:
        """Menüeintrag mit Kürzel; das Kürzel wird zusätzlich am Fenster gebunden."""
        menu.add_command(
            label=label, accelerator=accelerator(key, shift=shift), command=lambda: action()
        )
        self._bindings.append((binding(key, shift=shift), action))

    def _apply_bindings(self) -> None:
        """Registriert die Tastenkürzel global am Fenster.

        `bind_all` greift auch, wenn der Fokus in einem Eingabefeld steht;
        `break` verhindert, dass das Zeichen zusätzlich eingefügt wird.
        """
        for sequence, action in self._bindings:
            self.root.bind_all(sequence, lambda _e, a=action: (a(), "break")[1])

    def _to_focused(self, event: str) -> None:
        """Schickt ein virtuelles Event (Kopieren/Einfügen/…) ans fokussierte Widget."""
        widget = self.root.focus_get()
        if widget is not None:
            widget.event_generate(event)

    # --------------------------------------------------------- Zustand
    def set_recent(self, logs: list[str], images: list[str]) -> None:
        """Füllt die beiden „Zuletzt verwendet"-Untermenüs neu."""
        for menu, entries, callback in (
            (self.recent_logs_menu, logs, self.actions.open_recent_log),
            (self.recent_images_menu, images, self.actions.open_recent_image),
        ):
            menu.delete(0, "end")
            if not entries:
                menu.add_command(label=_RECENT_EMPTY, state="disabled")
                continue
            for path in entries:
                menu.add_command(label=_shorten(path), command=lambda p=path, cb=callback: cb(p))
            menu.add_separator()
            menu.add_command(label="Liste leeren", command=lambda: self.actions.clear_recent())

    def set_generate_enabled(self, enabled: bool) -> None:
        """Sperrt/entsperrt „Datei > PDF erzeugen" synchron zum Button (Abschnitt 10)."""
        if self._generate_entry is None:
            return
        self._generate_entry.menu.entryconfig(
            self._generate_entry.index, state="normal" if enabled else "disabled"
        )

    def set_theme_mode(self, mode: str) -> None:
        """Setzt die Markierung im Menü „Ansicht > Farbthema" (ohne Callback)."""
        self.theme_var.set(mode)


def _shorten(path: str, keep: int = 48) -> str:
    """Kürzt lange Pfade in der Mitte, damit das Menü schmal bleibt."""
    if len(path) <= keep:
        return path
    head = keep // 3
    return f"{path[:head]}…{path[-(keep - head - 1):]}"
