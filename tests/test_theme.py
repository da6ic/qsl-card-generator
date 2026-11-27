"""Tests für das Farbthema (`gui/theme.py`).

Die reinen Funktionen (Palette, Modus-Auflösung) laufen ohne Tk; alles, was
Widgets färbt, braucht ein Tk-Display und wird sonst übersprungen.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import fields
from tkinter import ttk
from unittest import mock

import pytest

from qslcards.gui import theme


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # kein Display -> Test überspringen
        pytest.skip(f"kein Tk-Display: {exc}")
    window.withdraw()
    yield window
    window.destroy()


# -- Palette ---------------------------------------------------------------


def test_palettes_define_every_role():
    """Beide Paletten füllen jede Rolle mit einer Hex-Farbe (keine Lücken)."""
    for palette in (theme.LIGHT, theme.DARK):
        for f in fields(theme.Palette):
            value = getattr(palette, f.name)
            assert value, f"{palette.name}.{f.name} ist leer"
            if f.name == "name":
                continue
            assert value.startswith("#") and len(value) == 7, f"{palette.name}.{f.name}={value}"


def test_light_and_dark_differ():
    """Hell und dunkel müssen sich in den Flächenfarben unterscheiden."""
    assert theme.LIGHT.bg != theme.DARK.bg
    assert theme.LIGHT.surface != theme.DARK.surface
    assert theme.LIGHT.text != theme.DARK.text


def test_resolve_mode_explicit_modes_skip_detection():
    """„light"/„dark" werden direkt übernommen — ohne Systemabfrage."""
    with mock.patch.object(theme, "detect_system_theme", side_effect=AssertionError):
        assert theme.resolve_mode("light") == "light"
        assert theme.resolve_mode("dark") == "dark"
        assert theme.resolve_mode("DARK") == "dark"


def test_resolve_mode_system_asks_os():
    with mock.patch.object(theme, "detect_system_theme", return_value="dark"):
        assert theme.resolve_mode("system") == "dark"
        assert theme.resolve_mode(None) == "dark"
        assert theme.resolve_mode("quatsch") == "dark"  # unbekannt -> wie „system"


def test_detect_system_theme_never_raises():
    """Schlägt die Erkennung fehl, gilt „light" (nie eine Exception nach oben)."""
    with mock.patch.object(theme.subprocess, "run", side_effect=OSError("kein Tool")):
        assert theme.detect_system_theme() == "light"


def test_palette_for_returns_matching_palette():
    assert theme.palette_for("light") is theme.LIGHT
    assert theme.palette_for("dark") is theme.DARK


# -- Anwendung auf Widgets (braucht Tk) ------------------------------------


def test_apply_uses_clam_and_colors_styles(root):
    palette = theme.apply(root, "dark")
    assert palette is theme.DARK
    style = ttk.Style(root)
    assert style.theme_use() == "clam"  # nur clam lässt sich voll einfärben
    assert style.lookup("TFrame", "background") == theme.DARK.bg
    assert style.lookup("Accent.TButton", "background") == theme.DARK.accent
    assert style.lookup("Treeview", "fieldbackground") == theme.DARK.surface


def test_apply_switches_back_to_light(root):
    theme.apply(root, "dark")
    theme.apply(root, "light")
    style = ttk.Style(root)
    assert style.lookup("TFrame", "background") == theme.LIGHT.bg
    assert style.lookup("Accent.TButton", "background") == theme.LIGHT.accent


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_required_and_invalid_styles_use_danger(root, mode):
    """Pflichtfeld-Stern und die Markierung leerer Pflichtangaben sind rot —
    in beiden Themen und auch, während das Feld den Fokus hat (sonst wäre die
    Markierung genau im Feld weg, das ausgefüllt werden soll)."""
    palette = theme.apply(root, mode)
    style = ttk.Style(root)

    assert style.lookup("Required.TLabel", "foreground") == palette.danger
    assert style.lookup("Invalid.TEntry", "bordercolor") == palette.danger
    assert style.lookup("Invalid.Thumb.TLabel", "bordercolor") == palette.danger
    for state in ("focus", "hover"):
        assert style.lookup("Invalid.TEntry", "bordercolor", [state]) == palette.danger
    # Erbt sonst alles von Thumb.TLabel (Fläche, Rahmenbreite, Polsterung).
    assert style.lookup("Invalid.Thumb.TLabel", "background") == palette.surface


def test_apply_never_overrides_styles_on_existing_widgets(root):
    """Ein Themenwechsel darf keine Farbe *am Widget* festschreiben.

    `tk_setPalette` tat genau das: es lief über den ganzen Widget-Baum und setzte
    `-foreground`/`-background` als Instanz-Option — auch auf ttk-Widgets, die
    diese Optionen kennen. Eine Instanz-Option schlägt den Style, der rote `*`
    der Pflichtfelder war nach dem ersten Wechsel textfarben und blieb danach auf
    den Farben des alten Themas stehen.
    """
    theme.apply(root, "dark")
    star = ttk.Label(root, text="*", style="Required.TLabel")
    entry = ttk.Entry(root)
    star.pack()
    entry.pack()

    for mode in ("light", "dark", "light"):
        theme.apply(root, mode)
        for widget in (star, entry):
            for option in ("foreground", "background"):
                assert (
                    str(widget.cget(option)) == ""
                ), f"{mode}: {option} am Widget gesetzt — der Style greift nicht mehr"


def test_apply_sets_defaults_for_widgets_created_later(root):
    """Die Optionsdatenbank bleibt die Vorgabe für später erzeugte tk-Widgets.

    Dialoge und das Handbuch-Fenster entstehen erst nach `apply` und werden von
    `restyle_tree` nicht mehr erfasst — sie holen ihre Grundfarbe hier.
    """
    for mode in ("dark", "light"):
        palette = theme.apply(root, mode)
        window = tk.Toplevel(root)
        try:
            assert window.cget("background") == palette.bg
        finally:
            window.destroy()


def test_restyle_tree_colors_classic_widgets(root):
    """Listbox/Canvas sind keine ttk-Widgets: sie werden direkt umgefärbt."""
    listbox = tk.Listbox(root)
    canvas = tk.Canvas(root)
    listbox.pack()
    canvas.pack()

    theme.restyle_tree(root, theme.DARK)
    assert listbox.cget("background") == theme.DARK.surface
    assert canvas.cget("background") == theme.DARK.bg

    theme.restyle_tree(root, theme.LIGHT)
    assert listbox.cget("background") == theme.LIGHT.surface
    assert canvas.cget("background") == theme.LIGHT.bg


def test_listbox_has_padding_and_no_black_border(root):
    """Zustellwege-Liste: 1-px-Ring in Rahmenfarbe, Text mit Abstand dazu.
    `relief="solid"` malte unter X11 einen schwarzen Rand zusätzlich."""
    listbox = tk.Listbox(root)
    theme.restyle_tree(root, theme.LIGHT)
    assert str(listbox.cget("relief")) == "flat"
    assert int(listbox.cget("highlightthickness")) == 1
    assert int(listbox.cget("borderwidth")) == theme.LISTBOX_PAD
    assert listbox.cget("highlightbackground") == theme.LIGHT.border


def test_named_fonts_survive_garbage_collection(root):
    """QslMono & Co. müssen als benannte Tk-Schriften bestehen bleiben. Über
    `tkfont.Font(exists=False)` angelegt, löschte der Garbage Collector sie
    sofort wieder — Tabelle und Schrittleiste standen dann in einer
    Ersatzschrift (unter Linux große Noto Sans statt Festbreite)."""
    import gc

    theme.apply(root, "light")
    gc.collect()
    theme.apply(root, "dark")  # zweiter Lauf: vorhandene Schriften umstellen
    gc.collect()
    names = root.tk.splitlist(root.tk.call("font", "names"))
    for name in ("QslMono", "QslMonoBold", "QslMonoTitle", "QslTitle", "QslHeadingBold"):
        assert name in names
    assert int(root.tk.call("font", "configure", "QslMono", "-size")) == theme.FONT_SIZE_BASE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
