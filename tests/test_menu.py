"""Tests für die Menüleiste (`gui/menu.py`).

Geprüft werden Struktur (welche Menüs/Einträge gibt es), die dynamischen Teile
(„Zuletzt verwendet", Sperre von „PDF erzeugen") und dass jeder Eintrag genau
den hinterlegten Callback auslöst. Braucht ein Tk-Display, sonst Skip.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from qslcards.gui import menu as menumod
from qslcards.gui.menu import MenuActions, MenuBar


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"kein Tk-Display: {exc}")
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def calls():
    """Sammelt, welche Aktion mit welchen Argumenten aufgerufen wurde."""
    return []


@pytest.fixture
def bar(root, calls):
    def record(name):
        return lambda *args: calls.append((name, *args))

    actions = MenuActions(
        **{f.name: record(f.name) for f in MenuActions.__dataclass_fields__.values()}
    )
    return MenuBar(root, actions, theme_mode="light")


def _labels(menu: tk.Menu) -> list[str]:
    """Alle Beschriftungen eines Menüs (Trenner werden übersprungen)."""
    out = []
    for i in range(menu.index("end") + 1):
        if menu.type(i) == "separator":
            continue
        out.append(menu.entrycget(i, "label"))
    return out


def _submenu(menu: tk.Menu, label: str) -> tk.Menu:
    for i in range(menu.index("end") + 1):
        if menu.type(i) != "separator" and menu.entrycget(i, "label") == label:
            return menu.nametowidget(menu.entrycget(i, "menu"))
    raise AssertionError(f"Untermenü {label!r} nicht gefunden")


def _invoke(menu: tk.Menu, label: str) -> None:
    for i in range(menu.index("end") + 1):
        if menu.type(i) != "separator" and menu.entrycget(i, "label") == label:
            menu.invoke(i)
            return
    raise AssertionError(f"Eintrag {label!r} nicht gefunden")


def test_menubar_has_all_top_level_menus(bar, root):
    """Datei, Bearbeiten, Aktionen, Ansicht, Hilfe (auf macOS zusätzlich Apple)."""
    # Das macOS-Programm-Menü hängt ohne Beschriftung vorn (das System setzt
    # dort den Programmnamen) -> leere Labels ignorieren.
    labels = [label for label in _labels(bar.menubar) if label]
    assert labels == ["Datei", "Bearbeiten", "Aktionen", "Ansicht", "Hilfe"]
    assert root.cget("menu")  # ist auch wirklich am Fenster gesetzt


def test_file_menu_entries(bar):
    menu = _submenu(bar.menubar, "Datei")
    labels = _labels(menu)
    assert "ADIF-Logbuch öffnen…" in labels
    assert "Frontbild wählen…" in labels
    assert "Zuletzt verwendete Logs" in labels
    assert "Zuletzt verwendete Bilder" in labels
    assert "Ausgabeziel wählen…" in labels
    assert "PDF erzeugen" in labels
    # „Beenden" gehört auf macOS ins Programm-Menü, sonst in „Datei".
    assert ("Beenden" in labels) is not menumod.IS_MAC


def test_actions_and_view_menu_entries(bar):
    actions = _labels(_submenu(bar.menubar, "Aktionen"))
    assert actions == [
        "Log neu laden",
        "Lookups neu abrufen",
        "Lookup-Cache leeren…",
    ]
    view = _submenu(bar.menubar, "Ansicht")
    assert _labels(view) == ["Farbthema", "Gehe zu Abschnitt"]
    assert _labels(_submenu(view, "Farbthema")) == ["System", "Hell", "Dunkel"]
    assert len(_labels(_submenu(view, "Gehe zu Abschnitt"))) == 10


def test_help_menu_entries(bar):
    menu = _submenu(bar.menubar, "Hilfe")
    labels = _labels(menu)
    assert labels[0] == "Handbuch"  # steht bewusst ganz oben
    # Die technischen Projektdokumente sind hier nicht mehr verlinkt.
    assert "Dokumentation" not in labels
    assert "config.yaml öffnen" in labels
    assert "Ausgabeordner anzeigen" in labels
    assert "Lookup-Cache anzeigen" in labels
    # „Über…" steht auf macOS im Programm-Menü.
    assert ("Über QSL-Karten-Generator" in labels) is not menumod.IS_MAC


def test_handbook_entry_opens_help(bar, calls):
    menu = _submenu(bar.menubar, "Hilfe")
    # ⌘? auf macOS, sonst F1 — beides außerhalb des Buchstaben-Schemas.
    accel = menu.entrycget(menu.index("Handbuch"), "accelerator")
    assert accel == ("Command-?" if menumod.IS_MAC else "F1") == menumod.HELP_ACCELERATOR
    _invoke(menu, "Handbuch")
    # Ohne Anker: das Menü öffnet immer den Anfang des Handbuchs.
    assert calls == [("show_help", None)]


def test_entries_call_their_action(bar, calls):
    _invoke(_submenu(bar.menubar, "Datei"), "ADIF-Logbuch öffnen…")
    _invoke(_submenu(bar.menubar, "Aktionen"), "Log neu laden")
    _invoke(_submenu(bar.menubar, "Aktionen"), "Lookup-Cache leeren…")
    assert calls == [("open_log",), ("reload_log",), ("clear_lookup_cache",)]


def test_theme_entries_pass_the_mode(bar, calls):
    view = _submenu(bar.menubar, "Ansicht")
    _invoke(_submenu(view, "Farbthema"), "Dunkel")
    assert calls == [("set_theme", "dark")]
    assert bar.theme_var.get() == "dark"


def test_goto_section_passes_number(bar, calls):
    view = _submenu(bar.menubar, "Ansicht")
    _invoke(_submenu(view, "Gehe zu Abschnitt"), "8. Vorschau")
    assert calls == [("goto_section", 8)]


def test_recent_menus_start_empty_and_fill(bar, calls):
    logs = _submenu(_submenu(bar.menubar, "Datei"), "Zuletzt verwendete Logs")
    assert _labels(logs) == ["(noch nichts geöffnet)"]

    bar.set_recent(["/pfad/a.adi", "/pfad/b.adi"], ["/pfad/bild.png"])
    assert _labels(logs) == ["/pfad/a.adi", "/pfad/b.adi", "Liste leeren"]
    _invoke(logs, "/pfad/b.adi")
    assert calls == [("open_recent_log", "/pfad/b.adi")]

    images = _submenu(_submenu(bar.menubar, "Datei"), "Zuletzt verwendete Bilder")
    _invoke(images, "/pfad/bild.png")
    assert calls[-1] == ("open_recent_image", "/pfad/bild.png")


def test_recent_entry_shortens_long_paths(bar):
    long_path = "/sehr/langer/pfad/" + "x" * 80 + "/log.adi"
    bar.set_recent([long_path], [])
    logs = _submenu(_submenu(bar.menubar, "Datei"), "Zuletzt verwendete Logs")
    shown = _labels(logs)[0]
    assert len(shown) < len(long_path) and "…" in shown


def test_generate_entry_can_be_disabled(bar):
    menu = _submenu(bar.menubar, "Datei")
    index = _labels(menu).index("PDF erzeugen")
    # _labels überspringt Trenner -> Index über die echte Menüposition suchen.
    for i in range(menu.index("end") + 1):
        if menu.type(i) != "separator" and menu.entrycget(i, "label") == "PDF erzeugen":
            index = i
            break

    bar.set_generate_enabled(False)
    assert str(menu.entrycget(index, "state")) == "disabled"
    bar.set_generate_enabled(True)
    assert str(menu.entrycget(index, "state")) == "normal"


def test_accelerators_match_platform():
    """macOS zeigt ⌘-Kürzel (Command-…), sonst Ctrl+…; Bindings passend dazu."""
    if menumod.IS_MAC:
        assert menumod.accelerator("o") == "Command-O"
        assert menumod.binding("o") == "<Command-o>"
        assert menumod.binding("r", shift=True) == "<Command-Shift-R>"
    else:
        assert menumod.accelerator("o") == "Ctrl+O"
        assert menumod.binding("o") == "<Control-o>"
        assert menumod.binding("r", shift=True) == "<Control-Shift-R>"


def test_help_key_really_fires(calls):
    """Das Handbuch-Kürzel (⌘? bzw. F1) muss auch als Taste ankommen.

    Eigenes Fenster statt der `root`-Fixture: ein per `withdraw()` verstecktes
    Fenster nimmt keine synthetischen Tastenereignisse an — off-screen schon.
    """
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - nur ohne Display
        pytest.skip(f"kein Tk-Display: {exc}")
    window.geometry("400x300+3000+3000")
    window.update()
    try:
        MenuBar(window, MenuActions(show_help=lambda a: calls.append(("show_help", a))))
        window.event_generate(menumod.HELP_BINDING)
        window.update()
        assert calls == [("show_help", None)]
    finally:
        window.destroy()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
