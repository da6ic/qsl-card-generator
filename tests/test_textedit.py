"""Tests für die Bearbeitungs-Kürzel der Eingabefelder (`gui/textedit.py`).

Zweiteilig: die Wortgrenzen-Logik läuft ohne Tk, das Zusammenspiel mit dem
Widget braucht ein **sichtbares** Fenster — ein zurückgezogenes (`withdraw`)
nimmt keine synthetischen Tastenereignisse an. Deshalb wird das Testfenster
weit außerhalb des Bildschirms geöffnet statt versteckt.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from qslcards.gui import textedit

TEXT = "TNX FR NICE QSO"


# -- Wortgrenzen (ohne Tk) --------------------------------------------------


@pytest.mark.parametrize(
    ("text", "cursor", "expected"),
    [
        (TEXT, len(TEXT), 12),  # am Ende -> Anfang von "QSO"
        (TEXT, 12, 7),  # -> Anfang von "NICE"
        (TEXT + " ", 16, 12),  # Leerzeichen davor wird mit übersprungen
        ("Wilhelmstr. 76", 14, 12),  # Satzzeichen hängt am Wort
        (TEXT, 0, 0),  # am Anfang: nichts zu tun
        ("   ", 3, 0),  # nur Leerraum
        (TEXT, 999, 12),  # Index außerhalb -> geklemmt
    ],
)
def test_word_start(text, cursor, expected):
    assert textedit.word_start(text, cursor) == expected


@pytest.mark.parametrize(
    ("text", "cursor", "expected"),
    [
        (TEXT, 0, 3),  # -> Ende von "TNX"
        (TEXT, 3, 6),  # Leerzeichen wird übersprungen
        (TEXT, len(TEXT), len(TEXT)),  # am Ende: nichts zu tun
        ("   ", 0, 3),
        (TEXT, -5, 3),  # Index außerhalb -> geklemmt
    ],
)
def test_word_end(text, cursor, expected):
    assert textedit.word_end(text, cursor) == expected


def test_word_functions_never_move_backwards():
    """`word_start` geht nie nach rechts, `word_end` nie nach links."""
    for index in range(len(TEXT) + 1):
        assert textedit.word_start(TEXT, index) <= index
        assert textedit.word_end(TEXT, index) >= index


# -- Belegung je Plattform --------------------------------------------------


def test_shortcut_set_matches_platform():
    sequences = [seq for seq, _ in textedit.entry_shortcuts()]
    if textedit.IS_MAC:
        assert sequences == [
            "<Option-BackSpace>",
            "<Option-Delete>",
            "<Command-BackSpace>",
            "<Command-Delete>",
        ]
    else:
        # Windows/Linux: Strg-Kombinationen; Strg+K liefert Tk bereits selbst.
        assert sequences == ["<Control-BackSpace>", "<Control-Delete>", "<Control-u>"]


# -- Zusammenspiel mit dem Eingabefeld -------------------------------------


@pytest.fixture
def entry():
    """Sichtbares (aber weit außerhalb liegendes) Fenster mit einem Feld."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"kein Tk-Display: {exc}")
    root.geometry("300x60+3000+3000")
    root.update()
    textedit.install_entry_shortcuts(root)
    widget = ttk.Entry(root)
    widget.pack()
    widget.focus_force()
    root.update()
    yield widget
    root.destroy()


def _press(entry: ttk.Entry, sequence: str, text: str, cursor: int) -> str:
    entry.delete(0, "end")
    entry.insert(0, text)
    entry.icursor(cursor)
    entry.update()
    entry.event_generate(sequence, when="now")
    entry.update()
    return entry.get()


@pytest.mark.skipif(not textedit.IS_MAC, reason="macOS-Tastenbelegung")
def test_macos_shortcuts_edit_the_field(entry):
    assert _press(entry, "<Option-BackSpace>", TEXT, len(TEXT)) == "TNX FR NICE "
    assert _press(entry, "<Option-Delete>", TEXT, 4) == "TNX  NICE QSO"
    assert _press(entry, "<Command-BackSpace>", TEXT, 11) == " QSO"
    assert _press(entry, "<Command-Delete>", TEXT, 4) == "TNX "


@pytest.mark.skipif(textedit.IS_MAC, reason="Windows-/Linux-Tastenbelegung")
def test_windows_linux_shortcuts_edit_the_field(entry):  # pragma: no cover - andere Plattform
    assert _press(entry, "<Control-BackSpace>", TEXT, len(TEXT)) == "TNX FR NICE "
    assert _press(entry, "<Control-Delete>", TEXT, 4) == "TNX  NICE QSO"
    assert _press(entry, "<Control-u>", TEXT, 11) == " QSO"


def test_selection_takes_precedence(entry):
    """Bei bestehender Auswahl löschen die Kürzel die Auswahl — wie überall."""
    sequence = "<Option-BackSpace>" if textedit.IS_MAC else "<Control-BackSpace>"
    entry.delete(0, "end")
    entry.insert(0, TEXT)
    entry.selection_range(4, 7)
    entry.update()
    entry.event_generate(sequence, when="now")
    entry.update()
    assert entry.get() == "TNX NICE QSO"


def test_shortcuts_are_bound_to_the_entry_class(entry):
    """Gebunden wird an die Klasse — damit gelten sie auch für die Editoren in
    der Vorschautabelle, nicht nur für die Felder der Abschnitte."""
    bound = entry.bind_class(textedit.ENTRY_CLASS)
    for sequence, _ in textedit.entry_shortcuts():
        # Tk normalisiert die Schreibweise (z.B. <Option-Key-BackSpace>).
        key = sequence.strip("<>").split("-")[-1]
        assert any(key in existing for existing in bound), sequence


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
