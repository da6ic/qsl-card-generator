"""Farbthema der Oberfläche („Funk-Blau", hell + dunkel).

Eine zentrale Stelle für **alle** Farben und Schriftgrößen der GUI — analog zu
`pdf/geometry.py` für die Karte. Kein Widget setzt Farben selbst; die Abschnitte
verwenden benannte ttk-Styles (`Accent.TButton`, `Section.TLabelframe`, …).

Warum `clam` statt `aqua`/`vista`: nur die von Tk mitgelieferten „klassischen"
Themes lassen sich vollständig einfärben. Damit sieht die App auf macOS,
Windows und Linux identisch aus (bewusst so abgestimmt).

Der Modus kommt aus der Config (`appearance.theme`): `system` (Default, folgt
dem Betriebssystem), `light` oder `dark`.
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk

# Modi, die `appearance.theme` annehmen darf.
THEME_MODES = ("system", "light", "dark")
THEME_LABELS = {"system": "System", "light": "Hell", "dark": "Dunkel"}


@dataclass(frozen=True)
class Palette:
    """Alle Farben eines Modus. Namen beschreiben die Rolle, nicht den Farbton."""

    name: str  # "light" | "dark"
    bg: str  # Fensterhintergrund (hinter den Abschnitten)
    surface: str  # Eingabefelder, Tabelle, Karten-/Abschnittsflächen
    surface_alt: str  # Zebrastreifen / getönte Kopfzeilen
    text: str  # Fließtext
    text_muted: str  # Sekundärtext (Status, Spaltentitel, Hinweise)
    text_disabled: str  # deaktivierte Widgets
    border: str  # Rahmen, Trennlinien
    accent: str  # Primärfarbe (Aktionsbutton, Fokus, Auswahl, Icon-Wellen)
    accent_hover: str  # Primärfarbe im Hover/Active-Zustand
    accent_text: str  # Text auf Akzentfläche
    select_bg: str  # Auswahlhintergrund (Tabelle, Listbox, Textmarkierung)
    success: str  # Statuspunkt „fertig"
    warning: str  # Statuspunkt „läuft/Achtung"
    danger: str  # Statuspunkt „Fehler"


LIGHT = Palette(
    name="light",
    bg="#F4F6F9",
    surface="#FFFFFF",
    surface_alt="#EDF1F6",
    text="#1B1F27",
    text_muted="#5A6270",
    text_disabled="#9AA2AE",
    border="#D4D9E0",
    accent="#1F6FEB",
    accent_hover="#1A5FCC",
    accent_text="#FFFFFF",
    select_bg="#DCE8FD",
    success="#1B8A5A",
    warning="#C8791A",
    danger="#C0392B",
)

DARK = Palette(
    name="dark",
    bg="#16181D",
    surface="#1E2128",
    surface_alt="#22262E",
    text="#E6E8EC",
    text_muted="#9AA2AE",
    text_disabled="#6B717C",
    border="#2E323B",
    accent="#4C93FF",
    accent_hover="#6BA6FF",
    accent_text="#0B0D11",
    select_bg="#24344F",
    success="#3FBF87",
    warning="#E0A048",
    danger="#E5695B",
)

PALETTES = {"light": LIGHT, "dark": DARK}

# --- Maße (eine Quelle der Wahrheit für Abstände/Größen) -------------------
PAD_SECTION = 8  # Außenabstand zwischen zwei Abschnitten
PAD_INNER = 8  # Innenabstand eines Abschnitts
GAP_ROW = 3  # vertikaler Abstand zweier Eingabezeilen
GAP_COL = 6  # horizontaler Abstand Label -> Eingabefeld
ROW_HEIGHT = 24  # Zeilenhöhe der Vorschau-Tabelle
FONT_SIZE_SMALL = -11  # negative Größe = Pixel (plattformunabhängig)
FONT_SIZE_BASE = -12
FONT_SIZE_HEADING = -12


def detect_system_theme() -> str:
    """Liefert `"dark"` oder `"light"` gemäß Betriebssystem-Einstellung.

    Jede Erkennung ist „best effort": schlägt sie fehl (kein Tool, andere
    Desktop-Umgebung, Timeout), wird `"light"` angenommen — nie fatal.
    """
    try:
        if sys.platform == "darwin":
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            # Im hellen Modus existiert der Schlüssel nicht (returncode != 0).
            return "dark" if "dark" in out.stdout.strip().lower() else "light"
        if sys.platform.startswith("win"):
            import winreg  # nur unter Windows vorhanden

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            with key:
                # AppsUseLightTheme: 0 = dunkel, 1 = hell
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if int(value) else "dark"
        # Linux (GNOME/Fedora, Debian): color-scheme, sonst der Theme-Name.
        for args in (
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
        ):
            out = subprocess.run(args, capture_output=True, text=True, timeout=2)
            value = out.stdout.strip().strip("'\"").lower()
            if value and value not in ("default", "prefer-light"):
                return "dark" if "dark" in value else "light"
    except Exception:  # bewusst breit: Themenerkennung darf nie den Start kippen
        return "light"
    return "light"


def resolve_mode(mode: str | None) -> str:
    """Übersetzt den Config-Wert (`system`/`light`/`dark`) in `light`/`dark`."""
    mode = (mode or "system").strip().lower()
    if mode in ("light", "dark"):
        return mode
    return detect_system_theme()


def palette_for(mode: str | None) -> Palette:
    return PALETTES[resolve_mode(mode)]


def _configure_fonts() -> None:
    """Setzt die benannten Tk-Standardschriften auf einheitliche Größen.

    Die Familie bleibt die des Systems (auf jeder Plattform die passende);
    nur die Größen werden vereinheitlicht, damit die Abschnitte auf allen
    Plattformen gleich hoch sind.
    """
    for name, size in (
        ("TkDefaultFont", FONT_SIZE_BASE),
        ("TkTextFont", FONT_SIZE_BASE),
        ("TkHeadingFont", FONT_SIZE_HEADING),
        ("TkMenuFont", FONT_SIZE_BASE),
        ("TkSmallCaptionFont", FONT_SIZE_SMALL),
    ):
        try:
            tkfont.nametofont(name).configure(size=size)
        except tk.TclError:  # Schrift auf dieser Plattform unbekannt
            continue


def apply(root: tk.Misc, mode: str | None) -> Palette:
    """Wendet das Farbthema auf `root` und alle künftigen Widgets an.

    Gibt die aktive Palette zurück. Nach einem Wechsel zur Laufzeit muss der
    Aufrufer zusätzlich `restyle_tree(root, palette)` rufen, damit auch die
    klassischen tk-Widgets (Listbox, Canvas, Menü) die neuen Farben bekommen.
    """
    pal = palette_for(mode)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # einzige Basis, die sich voll einfärben lässt
    except tk.TclError:  # pragma: no cover - clam gehört zum Tk-Lieferumfang
        pass
    _configure_fonts()

    # Fenster + Optionsdatenbank (gilt auch für später erzeugte tk-Widgets).
    try:
        root.tk_setPalette(background=pal.bg, foreground=pal.text)
    except tk.TclError:  # pragma: no cover - je nach Plattform nicht unterstützt
        pass
    root.option_add("*TCombobox*Listbox.background", pal.surface)
    root.option_add("*TCombobox*Listbox.foreground", pal.text)
    root.option_add("*TCombobox*Listbox.selectBackground", pal.accent)
    root.option_add("*TCombobox*Listbox.selectForeground", pal.accent_text)

    _configure_styles(style, pal)
    return pal


def _configure_styles(style: ttk.Style, pal: Palette) -> None:
    """Alle ttk-Styles der App. Reihenfolge: Basis -> Widgets -> Sonderstyles."""
    style.configure(
        ".",
        background=pal.bg,
        foreground=pal.text,
        fieldbackground=pal.surface,
        troughcolor=pal.surface_alt,
        bordercolor=pal.border,
        lightcolor=pal.bg,
        darkcolor=pal.bg,
        focuscolor=pal.accent,
        selectbackground=pal.select_bg,
        selectforeground=pal.text,
        insertcolor=pal.text,
    )
    style.map(".", foreground=[("disabled", pal.text_disabled)])

    style.configure("TFrame", background=pal.bg)
    style.configure("TLabel", background=pal.bg, foreground=pal.text)
    style.configure("Muted.TLabel", foreground=pal.text_muted)
    style.configure("Heading.TLabel", foreground=pal.text, font="TkHeadingFont")
    # Titel eines Abschnitts als eigenes Widget (LabelFrame mit `labelwidget`,
    # siehe ImageSection) — sieht aus wie „TLabelframe.Label".
    style.configure("SectionTitle.TLabel", foreground=pal.accent, font="TkHeadingFont")
    # Der `*` an Pflichtfeldern (Abschnitte 2 und 3).
    style.configure("Required.TLabel", foreground=pal.danger)
    for role, color in (
        ("Success", pal.success),
        ("Warning", pal.warning),
        ("Danger", pal.danger),
        ("Accent", pal.accent),
    ):
        style.configure(f"{role}.TLabel", foreground=color, background=pal.bg)

    # Abschnitte: 1px-Rahmen in Randfarbe, Titel in Akzentfarbe.
    style.configure(
        "TLabelframe",
        background=pal.bg,
        bordercolor=pal.border,
        lightcolor=pal.border,
        darkcolor=pal.border,
        relief="solid",
        borderwidth=1,
        padding=PAD_INNER,
    )
    style.configure(
        "TLabelframe.Label",
        background=pal.bg,
        foreground=pal.accent,
        font="TkHeadingFont",
    )

    # Buttons: flach, 1px-Rahmen; der Primärbutton („PDF erzeugen") in Akzentfarbe.
    style.configure(
        "TButton",
        background=pal.surface,
        foreground=pal.text,
        bordercolor=pal.border,
        lightcolor=pal.surface,
        darkcolor=pal.surface,
        relief="flat",
        padding=(10, 4),
        anchor="center",
    )
    style.map(
        "TButton",
        background=[
            ("disabled", pal.bg),
            ("pressed", pal.surface_alt),
            ("active", pal.surface_alt),
        ],
        bordercolor=[("focus", pal.accent), ("active", pal.accent)],
        foreground=[("disabled", pal.text_disabled)],
    )
    style.configure(
        "Accent.TButton",
        background=pal.accent,
        foreground=pal.accent_text,
        bordercolor=pal.accent,
        lightcolor=pal.accent,
        darkcolor=pal.accent,
        padding=(14, 5),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", pal.border),
            ("pressed", pal.accent_hover),
            ("active", pal.accent_hover),
        ],
        bordercolor=[("disabled", pal.border), ("active", pal.accent_hover)],
        foreground=[("disabled", pal.text_disabled)],
    )
    # Schmale Buttons (▲/▼ der Prioritätsliste): ohne die breite Polsterung.
    style.configure("Icon.TButton", padding=(2, 0))

    # Eingaben: Rahmen wechselt bei Fokus auf die Akzentfarbe.
    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            widget,
            fieldbackground=pal.surface,
            background=pal.surface,
            foreground=pal.text,
            bordercolor=pal.border,
            lightcolor=pal.border,
            darkcolor=pal.border,
            insertcolor=pal.text,
            arrowcolor=pal.text_muted,
            padding=(5, 3),
        )
        style.map(
            widget,
            bordercolor=[("focus", pal.accent), ("hover", pal.accent)],
            lightcolor=[("focus", pal.accent)],
            darkcolor=[("focus", pal.accent)],
            fieldbackground=[("disabled", pal.bg), ("readonly", pal.surface)],
            foreground=[("disabled", pal.text_disabled)],
            arrowcolor=[("disabled", pal.text_disabled)],
        )
    style.map(
        "TCombobox",
        selectbackground=[("readonly", pal.surface)],
        selectforeground=[("readonly", pal.text)],
    )

    # Leer gebliebenes Pflichtfeld (nach einem Druckversuch, siehe sections.py):
    # roter Rahmen. Die `map` muss sein — ohne sie zieht die geerbte TEntry-Map
    # den Rahmen bei Fokus/Hover wieder auf die Akzentfarbe, und ausgerechnet im
    # Feld, das der Nutzer gerade ausfüllen soll, wäre die Markierung weg.
    style.configure(
        "Invalid.TEntry",
        bordercolor=pal.danger,
        lightcolor=pal.danger,
        darkcolor=pal.danger,
    )
    style.map(
        "Invalid.TEntry",
        bordercolor=[("focus", pal.danger), ("hover", pal.danger)],
        lightcolor=[("focus", pal.danger)],
        darkcolor=[("focus", pal.danger)],
    )

    # Achtung: `clam` kennt KEIN `indicatorcolor` (das ist die Option der
    # alten Tk-Widgets). Das Kästchen/der Kreis wird über
    # `indicatorbackground` (Fläche) und `indicatorforeground` (Haken/Punkt)
    # gefärbt — angewählt in der Akzentfarbe, wie die Auswahl in Eingabefeldern.
    for widget in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            widget,
            background=pal.bg,
            foreground=pal.text,
            indicatorbackground=pal.surface,
            indicatorforeground=pal.accent_text,
            upperbordercolor=pal.border,
            lowerbordercolor=pal.border,
            focuscolor=pal.accent,
            padding=2,
        )
        style.map(
            widget,
            background=[("active", pal.bg)],
            foreground=[("disabled", pal.text_disabled)],
            indicatorbackground=[
                ("disabled", pal.bg),
                ("selected", pal.accent),
                ("pressed", pal.surface_alt),
                ("active", pal.surface_alt),
            ],
            indicatorforeground=[
                ("disabled", pal.text_disabled),
                ("selected", pal.accent_text),
            ],
            upperbordercolor=[("selected", pal.accent), ("active", pal.accent)],
            lowerbordercolor=[("selected", pal.accent), ("active", pal.accent)],
        )

    style.configure("TSeparator", background=pal.border)
    style.configure(
        "TProgressbar",
        background=pal.accent,
        troughcolor=pal.surface_alt,
        bordercolor=pal.border,
        lightcolor=pal.accent,
        darkcolor=pal.accent,
        thickness=6,
    )
    style.configure(
        "TScrollbar",
        background=pal.border,
        troughcolor=pal.bg,
        bordercolor=pal.bg,
        arrowcolor=pal.text_muted,
        relief="flat",
    )
    style.map("TScrollbar", background=[("active", pal.text_disabled)])

    # Vorschau-Tabelle: Fläche in `surface`, getönter Kopf, Zebra über Tags
    # (die Tag-Farben setzt preview.py aus derselben Palette).
    style.configure(
        "Treeview",
        background=pal.surface,
        fieldbackground=pal.surface,
        foreground=pal.text,
        bordercolor=pal.border,
        lightcolor=pal.border,
        darkcolor=pal.border,
        rowheight=ROW_HEIGHT,
        borderwidth=1,
        relief="solid",
    )
    style.map(
        "Treeview",
        background=[("selected", pal.select_bg)],
        foreground=[("selected", pal.text)],
    )
    style.configure(
        "Treeview.Heading",
        background=pal.surface_alt,
        foreground=pal.text_muted,
        bordercolor=pal.border,
        relief="flat",
        padding=(4, 4),
        font="TkSmallCaptionFont",
    )
    style.map(
        "Treeview.Heading",
        background=[("active", pal.border)],
        foreground=[("active", pal.text)],
    )

    # Icon-Overlays IN der Vorschau-Tabelle (Stift im Spaltenkopf, Hover-Icon in
    # der Zelle). Die SVG-Icons sind transparent, Tk mischt sie aber gegen den
    # Hintergrund des *Labels* — steht der auf der Fensterfarbe, sitzt sichtbar
    # ein Kästchen auf der Tabellenzeile. Deshalb je ein Style pro möglichem
    # Untergrund; preview.py wählt ihn anhand der Zeile aus.
    for name, color in (
        ("TreeIconHead", pal.surface_alt),  # Spaltenkopf
        ("TreeIconOdd", pal.surface),  # Zeile ohne Zebra-Tönung
        ("TreeIconEven", pal.surface_alt),  # getönte Zebra-Zeile
        ("TreeIconSelected", pal.select_bg),  # markierte Zeile
    ):
        style.configure(f"{name}.TLabel", background=color, borderwidth=0, padding=0, relief="flat")

    # Statusleiste am Fensterfuß (eigene Fläche, oben abgesetzt).
    style.configure("Status.TFrame", background=pal.surface_alt)
    style.configure("Status.TLabel", background=pal.surface_alt, foreground=pal.text_muted)
    style.configure("StatusAccent.TLabel", background=pal.surface_alt, foreground=pal.text)
    for role, color in (
        ("StatusSuccess", pal.success),
        ("StatusWarning", pal.warning),
        ("StatusDanger", pal.danger),
    ):
        style.configure(f"{role}.TLabel", background=pal.surface_alt, foreground=color)

    # Bildvorschau: abgesetzte Fläche mit Rahmen, damit das Thumbnail „sitzt".
    style.configure(
        "Thumb.TLabel",
        background=pal.surface,
        foreground=pal.text_muted,
        bordercolor=pal.border,
        relief="solid",
        borderwidth=1,
        anchor="center",
        padding=6,
    )
    # Fehlendes Frontbild: derselbe Rahmen in Rot. Der Name erbt über ttk die
    # übrigen Optionen von `Thumb.TLabel` — nur die Rahmenfarbe wird ersetzt.
    style.configure(
        "Invalid.Thumb.TLabel",
        bordercolor=pal.danger,
        lightcolor=pal.danger,
        darkcolor=pal.danger,
    )


# Klassische (nicht-ttk) Widgets: ttk-Styles greifen hier nicht, deshalb werden
# die Farben pro Widget-Klasse gesetzt. Wird beim Start und bei jedem
# Themenwechsel über den kompletten Widget-Baum angewandt.
def _options_for(widget: tk.Misc, pal: Palette) -> dict[str, str]:
    if isinstance(widget, tk.Listbox):
        return {
            "background": pal.surface,
            "foreground": pal.text,
            "selectbackground": pal.select_bg,
            "selectforeground": pal.text,
            "highlightbackground": pal.border,
            "highlightcolor": pal.accent,
            "borderwidth": 1,
            "relief": "solid",
        }
    if isinstance(widget, tk.Canvas):
        return {"background": pal.bg, "highlightthickness": 0}
    if isinstance(widget, tk.Menu):
        # Auf macOS zeichnet das System die Menüs selbst und ignoriert Farben.
        if sys.platform == "darwin":
            return {}
        return {
            "background": pal.surface,
            "foreground": pal.text,
            "activebackground": pal.accent,
            "activeforeground": pal.accent_text,
            "selectcolor": pal.accent,
            "borderwidth": 0,
        }
    if isinstance(widget, tk.Text):
        return {
            "background": pal.surface,
            "foreground": pal.text,
            "insertbackground": pal.text,
            "selectbackground": pal.select_bg,
            "highlightbackground": pal.border,
            "highlightcolor": pal.accent,
        }
    if isinstance(widget, tk.Toplevel | tk.Tk):
        return {"background": pal.bg}
    return {}


def restyle_tree(widget: tk.Misc, pal: Palette) -> None:
    """Färbt `widget` und alle Kinder (klassische tk-Widgets) neu ein."""
    options = _options_for(widget, pal)
    if options:
        try:
            widget.configure(**options)
        except tk.TclError:  # Widget kennt eine Option nicht -> überspringen
            pass
    for child in widget.winfo_children():
        restyle_tree(child, pal)
