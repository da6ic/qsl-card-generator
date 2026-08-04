"""Übliche Bearbeitungs-Tastenkürzel für die Eingabefelder.

Tk bringt in `ttk::entry` nur das Nötigste mit: ein Zeichen löschen und
`Ctrl+K` (bis Zeilenende, Emacs-Stil). Die Kürzel, die Nutzer von jedem anderen
Programm kennen — ein **Wort** oder die **ganze Zeile** löschen — fehlen; die
Auffang-Bindungen `<Alt-Key>`/`<Meta-Key>` verschlucken sie zusätzlich.

Belegung je Plattform (die Konventionen unterscheiden sich):

| Wirkung              | macOS         | Windows / Linux    |
|----------------------|---------------|--------------------|
| Wort links löschen   | ⌥⌫            | Strg+Rücktaste     |
| Wort rechts löschen  | ⌥⌦            | Strg+Entf          |
| bis Zeilenanfang     | ⌘⌫            | Strg+U             |
| bis Zeilenende       | ⌘⌦ / Ctrl+K   | Strg+K (von Tk)    |

Gebunden wird an die **Widget-Klasse** `TEntry`, gilt also für alle Felder der
App — auch für die Editoren in der Vorschautabelle.
"""

from __future__ import annotations

import sys
import tkinter as tk

# Auf macOS gelten andere Tastenkonventionen (Option/Command statt Strg).
IS_MAC = sys.platform == "darwin"

ENTRY_CLASS = "TEntry"


def word_start(text: str, index: int) -> int:
    """Anfang des Wortes **links** von `index`.

    Erst wird der Leerraum unmittelbar vor dem Cursor übersprungen, dann das
    Wort selbst. Als Worttrenner zählt ausschließlich Leerraum — in kurzen
    Feldern (Rufzeichen, „Wilhelmstr. 76", Bemerkungen) ist das die
    erwartbarste Regel, weil Satzzeichen am Wort hängen bleiben.
    """
    i = max(0, min(index, len(text)))
    while i > 0 and text[i - 1].isspace():
        i -= 1
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    return i


def word_end(text: str, index: int) -> int:
    """Ende des Wortes **rechts** von `index` (Gegenstück zu `word_start`)."""
    n = len(text)
    i = max(0, min(index, n))
    while i < n and text[i].isspace():
        i += 1
    while i < n and not text[i].isspace():
        i += 1
    return i


def _delete_selection(entry: tk.Entry) -> bool:
    """Löscht eine bestehende Auswahl; liefert True, wenn etwas gelöscht wurde.

    Alle Kürzel wirken zuerst auf die Auswahl — so wie in jedem anderen
    Eingabefeld auch.
    """
    try:
        if entry.selection_present():
            entry.delete("sel.first", "sel.last")
            return True
    except tk.TclError:  # Widget ohne Auswahl-Unterstützung
        pass
    return False


def delete_word_left(event: tk.Event) -> str:
    entry = event.widget
    if not _delete_selection(entry):
        cursor = entry.index("insert")
        start = word_start(entry.get(), cursor)
        if start < cursor:
            entry.delete(start, cursor)
    return "break"


def delete_word_right(event: tk.Event) -> str:
    entry = event.widget
    if not _delete_selection(entry):
        cursor = entry.index("insert")
        end = word_end(entry.get(), cursor)
        if end > cursor:
            entry.delete(cursor, end)
    return "break"


def delete_to_start(event: tk.Event) -> str:
    entry = event.widget
    if not _delete_selection(entry):
        entry.delete(0, "insert")
    return "break"


def delete_to_end(event: tk.Event) -> str:
    entry = event.widget
    if not _delete_selection(entry):
        entry.delete("insert", "end")
    return "break"


def entry_shortcuts() -> list[tuple[str, object]]:
    """(Tastenfolge, Aktion) für diese Plattform — Reihenfolge ohne Bedeutung."""
    if IS_MAC:
        return [
            ("<Option-BackSpace>", delete_word_left),
            ("<Option-Delete>", delete_word_right),
            ("<Command-BackSpace>", delete_to_start),
            ("<Command-Delete>", delete_to_end),
        ]
    return [
        ("<Control-BackSpace>", delete_word_left),
        ("<Control-Delete>", delete_word_right),
        ("<Control-u>", delete_to_start),
        # Strg+K (bis Zeilenende) bringt Tk bereits selbst mit.
    ]


def install_entry_shortcuts(widget: tk.Misc) -> list[str]:
    """Bindet die Kürzel an die Klasse `TEntry` (gilt für alle Felder).

    Gibt die gebundenen Tastenfolgen zurück (für Tests/Diagnose).
    """
    for sequence, action in entry_shortcuts():
        widget.bind_class(ENTRY_CLASS, sequence, action)
    return [sequence for sequence, _ in entry_shortcuts()]
