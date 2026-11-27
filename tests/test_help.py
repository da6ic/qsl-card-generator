"""Tests für das Handbuch (`gui/help.py`).

Zwei Teile: der Markdown-Renderer (reine Funktionen, laufen überall) und das
Fenster selbst (braucht ein Tk-Display, sonst Skip).

Der wichtigste Test ist `test_handbook_has_an_anchor_for_every_section`: er hält
die Kontexthilfe („?" am Abschnittstitel) und den Handbuchtext zusammen. Ohne
ihn würde ein umbenanntes Kapitel die Sprungziele still kaputtmachen.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from unittest import mock

import pytest

from qslcards.gui import help as helpmod
from qslcards.gui.menu import SECTIONS
from qslcards.gui.theme import DARK, LIGHT

SAMPLE = """\
# Titel

## Kapitel eins {#kap-1}

Ein Absatz, der über
zwei Zeilen läuft.

- Erster Punkt mit **fett** und `code`
- Zweiter Punkt
  mit Fortsetzung
  - Unterpunkt

1. Nummeriert

### Unterüberschrift

```
roher Text
```

Ein [Link](https://example.org) im Text.
"""


# ------------------------------------------------------------------- Parser
def test_headings_keep_their_level_and_anchor():
    blocks = helpmod.parse(SAMPLE)
    kinds = [(b.kind, b.text, b.anchor) for b in blocks if b.kind.startswith("h")]
    assert kinds == [
        ("h1", "Titel", ""),
        ("h2", "Kapitel eins", "kap-1"),
        ("h3", "Unterüberschrift", ""),
    ]


def test_paragraph_lines_are_joined():
    paragraphs = [b.text for b in helpmod.parse(SAMPLE) if b.kind == "p"]
    assert "Ein Absatz, der über zwei Zeilen läuft." in paragraphs


def test_italic_and_lone_asterisk():
    """*kursiv* wird ausgezeichnet (stand vorher roh mit Sternchen im Fenster),
    ein freistehendes „*" (Pflichtfeld-Stern) bleibt Text."""
    spans = helpmod.parse_inline("Log *oder* Wavelog, **fett**, Stern * bleibt")
    assert [(s.text, s.style) for s in spans] == [
        ("Log ", ""),
        ("oder", "italic"),
        (" Wavelog, ", ""),
        ("fett", "bold"),
        (", Stern * bleibt", ""),
    ]


def test_manual_has_no_raw_asterisks():
    """Im fertig gerenderten Handbuch steht nirgends ein Markdown-Sternchen."""
    text = helpmod.handbook_path().read_text(encoding="utf-8")
    for block in helpmod.parse(text):
        for span in block.spans:
            if span.style != "code":
                assert "*" not in span.text.replace(" * ", ""), span.text


def test_inline_styles():
    spans = helpmod.parse_inline("Ein **fettes** Wort, `code` und [Link](https://example.org).")
    assert [(s.text, s.style) for s in spans] == [
        ("Ein ", ""),
        ("fettes", "bold"),
        (" Wort, ", ""),
        ("code", "code"),
        (" und ", ""),
        ("Link", "link"),
        (".", ""),
    ]
    assert spans[5].href == "https://example.org"


def test_bullets_carry_marker_level_and_continuation():
    bullets = [b for b in helpmod.parse(SAMPLE) if b.kind == "bullet"]
    assert [(b.marker, b.level) for b in bullets] == [
        ("•", 0),
        ("•", 0),
        ("•", 1),
        ("1.", 0),
    ]
    # Die eingerückte Folgezeile gehört zum zweiten Punkt, nicht zu einem Absatz.
    assert bullets[1].text == "Zweiter Punkt mit Fortsetzung"


def test_internal_link_keeps_its_anchor():
    spans = helpmod.parse_inline("siehe [Kapitel 4](#abschnitt-4) dazu")
    link = next(s for s in spans if s.style == "link")
    assert (link.text, link.href) == ("Kapitel 4", "#abschnitt-4")


def test_bold_inside_a_link_does_not_leak_asterisks():
    """Verschachtelte Auszeichnung kann der Renderer nicht — sie darf aber auch
    nicht als `**` im Text stehen bleiben."""
    spans = helpmod.parse_inline("[**Kapitel 4**](#abschnitt-4)")
    assert [(s.text, s.style) for s in spans] == [("Kapitel 4", "link")]


def test_code_block_keeps_its_text_raw():
    code = [b for b in helpmod.parse(SAMPLE) if b.kind == "code"]
    assert [b.text for b in code] == ["roher Text"]


def test_chapters_are_the_h2_headings():
    assert [b.text for b in helpmod.chapters(helpmod.parse(SAMPLE))] == ["Kapitel eins"]


# ------------------------------------------------------------------ Datei
def test_shipped_handbook_is_readable_and_has_chapters():
    blocks = helpmod.parse(helpmod.load_handbook())
    assert helpmod.handbook_path().is_file()
    assert len(helpmod.chapters(blocks)) >= 11


def test_handbook_has_an_anchor_for_every_section():
    """Jedes „?" in der Oberfläche muss im Handbuch landen können."""
    found = helpmod.anchors(helpmod.parse(helpmod.load_handbook()))
    missing = [f"abschnitt-{number}" for number, _title in SECTIONS]
    assert [anchor for anchor in missing if anchor not in found] == []


def test_every_internal_link_in_the_handbook_resolves():
    """Ein vertippter Verweis wäre im Fenster ein Klick, der nichts tut."""
    blocks = helpmod.parse(helpmod.load_handbook())
    known = helpmod.anchors(blocks)
    targets = [
        span.href
        for block in blocks
        for span in block.spans
        if span.style == "link" and span.href.startswith("#")
    ]
    assert targets, "das Handbuch soll interne Verweise haben"
    assert [href for href in targets if href[1:] not in known] == []


def test_missing_file_yields_a_hint_instead_of_an_error(tmp_path):
    text = helpmod.load_handbook(tmp_path / "gibtsnicht.md")
    blocks = helpmod.parse(text)
    assert blocks[0].kind == "h1"
    assert "nicht gefunden" in blocks[0].text
    # Der erwartete Pfad steht mit drin, damit man weiß, wohin die Datei gehört.
    assert "gibtsnicht.md" in text


def test_handbook_is_searched_next_to_the_program():
    """Auch aus einem fremden Arbeitsverzeichnis muss die Datei gefunden werden."""
    program_copy = helpmod.handbook_candidates()[1]
    assert program_copy.name == helpmod.HANDBOOK_NAME
    assert program_copy.is_absolute()


# ----------------------------------------------------------------- Fenster
@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"kein Tk-Display: {exc}")
    # Off-screen statt `withdraw()`: ein verstecktes Fenster rechnet keine
    # Geometrie aus, und genau die braucht der Sprung zum Kapitel.
    window.geometry("900x700+3000+3000")
    window.update_idletasks()
    yield window
    window.destroy()


@pytest.fixture
def window(root):
    dialog = helpmod.HelpWindow(root, LIGHT)
    dialog.update_idletasks()
    yield dialog
    if dialog.winfo_exists():
        dialog.destroy()


def test_window_lists_the_chapters(window):
    titles = list(window.sidebar.get(0, "end"))
    expected = [b.text for b in helpmod.chapters(helpmod.parse(helpmod.load_handbook()))]
    assert titles == expected


def test_goto_jumps_to_the_chapter(window):
    assert window.goto("abschnitt-9") is True
    window.update_idletasks()
    top = window.text.index("@0,0")
    assert window.text.compare(top, ">", "1.0")
    # Die Seitenleiste zeigt mit: das Kapitel steht als ausgewählt da.
    assert window.sidebar.curselection()


def test_scrolling_to_the_end_selects_the_last_chapter(window):
    """Die letzten Kapitel sind kürzer als das Fenster — oben stünde dort sonst
    für immer das vorletzte, obwohl man ganz unten angekommen ist."""
    window.text.yview_moveto(1.0)
    window.update_idletasks()
    window._sync_sidebar()

    assert window.text.yview()[1] >= 1.0  # wirklich am Ende
    assert window.sidebar.curselection() == (len(window._chapters) - 1,)


def test_scrolling_to_the_top_selects_the_first_chapter(window):
    window.text.yview_moveto(1.0)
    window.update_idletasks()
    window.text.yview_moveto(0.0)
    window.update_idletasks()
    window._sync_sidebar()

    assert window.sidebar.curselection() == (0,)


def test_internal_link_jumps_within_the_handbook(window):
    window._follow_link("#abschnitt-9")
    window.update_idletasks()
    assert window.text.compare(window.text.index("@0,0"), ">", "1.0")
    # Und die Kapitelliste zieht mit.
    assert window.sidebar.curselection()


def test_external_link_goes_to_the_browser(window):
    with mock.patch.object(helpmod.webbrowser, "open") as opener:
        window._follow_link("https://www.hamqth.com")
    opener.assert_called_once_with("https://www.hamqth.com")


def test_unknown_anchor_is_ignored(window):
    assert window.goto("gibtsnicht") is False


def test_palette_change_recolors_the_text(window):
    window.apply_palette(DARK)
    assert window.text.cget("background") == DARK.surface
    assert window.text.tag_cget("h2", "foreground") == DARK.accent
    window.apply_palette(LIGHT)
    assert window.text.tag_cget("h2", "foreground") == LIGHT.accent


def test_edited_file_is_reloaded_on_focus(root, tmp_path, monkeypatch):
    path = tmp_path / helpmod.HANDBOOK_NAME
    path.write_text("# Alt\n\n## Erstes {#abschnitt-1}\n", encoding="utf-8")
    monkeypatch.setattr(helpmod, "handbook_path", lambda: path)

    dialog = helpmod.HelpWindow(root, LIGHT)
    try:
        assert list(dialog.sidebar.get(0, "end")) == ["Erstes"]
        # Zwei verschiedene mtimes erzwingen (write_text allein kann zu schnell sein).
        path.write_text("# Neu\n\n## Zweites {#abschnitt-1}\n", encoding="utf-8")
        stat = path.stat()
        os.utime(path, (stat.st_atime, stat.st_mtime + 10))

        dialog.event_generate("<FocusIn>")
        dialog.update_idletasks()
        assert list(dialog.sidebar.get(0, "end")) == ["Zweites"]
    finally:
        dialog.destroy()


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def test_window_shows_only_the_text(window):
    """Keine Fußleiste: Schließen macht die Fenstersteuerung des Systems."""
    extras = [w for w in _descendants(window) if isinstance(w, ttk.Button | ttk.Label)]
    assert extras == []


def test_window_keeps_the_menubar_of_the_app(root):
    """Ohne eigenes Menü zeigt macOS über dem Fenster die Standardleiste von Tk
    („Python"-Menü, Tk-Hilfe) — das Handbuch übernimmt deshalb die der App."""
    menubar = tk.Menu(root)
    menubar.add_cascade(label="Datei", menu=tk.Menu(menubar, tearoff=0))
    root.configure(menu=menubar)

    dialog = helpmod.HelpWindow(root, LIGHT, menubar=menubar)
    try:
        assert dialog.cget("menu") == str(menubar)
        assert root.cget("menu") == str(menubar)  # das Hauptfenster behält seine
    finally:
        dialog.destroy()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
