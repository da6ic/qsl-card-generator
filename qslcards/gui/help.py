"""Anwender-Handbuch im Programm anzeigen (Menü „Hilfe > Handbuch").

Der Text steht in `handbuch.md` **neben dem Programm** — also dort, wo auch
`config.yaml` liegt. Bewusst keine Kopie im Paket: der Nutzer soll die Datei mit
jedem Texteditor lesen und für sich ergänzen können, und zwei Kopien wären zwei
Wahrheiten.

Der Renderer hier ist kein allgemeiner Markdown-Parser, sondern deckt genau das
ab, was im Handbuch vorkommt: Überschriften (mit optionaler Anker-ID
`{#name}`), Absätze, Aufzählungen, Codeblöcke sowie **fett**, `code` und Links.
Tabellen gibt es im Handbuch deshalb absichtlich nicht.

Die Anker verbinden die Oberfläche mit dem Text: das „?" an Abschnitt N springt
zu `abschnitt-N` (siehe `app._show_help`).
"""

from __future__ import annotations

import re
import sys
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from qslcards import paths

from .scrolling import bind_wheel, wheel_step
from .theme import PAD_INNER, Palette

# Dateiname des Handbuchs (der Name steht in `paths`, wie alle anderen auch).
HANDBOOK_NAME = paths.HANDBOOK_NAME

# Fenstergröße beim Öffnen und Breite der Kapitelliste (Zeichen).
WINDOW_SIZE = "880x640"
WINDOW_MIN = (560, 360)
SIDEBAR_WIDTH = 26

# Schriftgrößen relativ zur Grundschrift (Pixel; siehe theme.FONT_SIZE_BASE).
H1_DELTA = 7
H2_DELTA = 4
H3_DELTA = 1

# Einzug einer Aufzählungsebene (Pixel).
BULLET_INDENT = 18


# --------------------------------------------------------------- Handbuchdatei
def handbook_candidates() -> list[Path]:
    """Mögliche Orte des Handbuchs, in der Reihenfolge der Suche.

    Zuerst das Arbeitsverzeichnis, dann der Ordner des Programms — damit die
    Hilfe auch dann etwas anzeigt, wenn die App aus einem anderen Verzeichnis
    gestartet wurde. Zuletzt die mitgelieferte Kopie aus dem Bündel.

    Die Reihenfolge ist der eigentliche Vertrag: eine vom Anwender **neben das
    Programm gelegte** Datei schlägt die mitgelieferte. Damit bleibt es bei einer
    Wahrheit — wer das Handbuch für sich ergänzt, sieht seine Fassung, alle
    anderen die ausgelieferte. Ins Benutzerverzeichnis kopiert wird bewusst
    nichts: diese Kopie wäre beim nächsten Programm-Update veraltet.
    """
    candidates: list[Path] = [Path(HANDBOOK_NAME)]
    folders = [
        paths.program_dir(),
        Path(sys.argv[0]).resolve().parent,
        paths.resource_dir(),
    ]
    for folder in folders:
        candidate = folder / HANDBOOK_NAME
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def handbook_path() -> Path:
    """Pfad des Handbuchs. Fehlt es überall, der erste Kandidat (für die Meldung)."""
    for candidate in handbook_candidates():
        if candidate.is_file():
            return candidate
    return handbook_candidates()[0]


def load_handbook(path: Path | None = None) -> str:
    """Handbuchtext lesen. Fehlt oder klemmt die Datei: Hinweis statt Ausnahme."""
    path = path or handbook_path()
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            "# Handbuch nicht gefunden\n\n"
            f"Die Datei `{HANDBOOK_NAME}` konnte nicht gelesen werden "
            f"({exc.strerror or exc}).\n\n"
            f"Erwartet wird sie hier:\n\n```\n{path.resolve()}\n```\n\n"
            "Sie gehört in denselben Ordner wie das Programm und die "
            "`config.yaml`.\n"
        )


# ------------------------------------------------------------------- Parser
@dataclass(frozen=True)
class Span:
    """Ein Textstück einer Zeile. `style`: `""`, `"bold"`, `"code"` oder `"link"`."""

    text: str
    style: str = ""
    href: str = ""


@dataclass(frozen=True)
class Block:
    """Ein Absatz des Handbuchs.

    `kind`: `h1`/`h2`/`h3`, `p`, `bullet`, `code`.
    `anchor` tragen nur Überschriften mit `{#name}`, `level` nur Aufzählungen.
    """

    kind: str
    spans: tuple[Span, ...]
    anchor: str = ""
    level: int = 0
    marker: str = ""

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)


_HEADING = re.compile(r"^(?P<hashes>#{1,3})\s+(?P<title>.*?)\s*$")
_ANCHOR = re.compile(r"\s*\{#(?P<anchor>[A-Za-z0-9_-]+)\}\s*$")
_BULLET = re.compile(r"^(?P<indent>\s*)(?P<marker>-|\d+\.)\s+(?P<rest>.*)$")
_INLINE = re.compile(
    r"\*\*(?P<bold>.+?)\*\*" r"|`(?P<code>[^`]+)`" r"|\[(?P<label>[^\]]+)\]\((?P<href>[^)\s]+)\)"
)
_FENCE = "```"


def parse_inline(text: str) -> tuple[Span, ...]:
    """Zerlegt eine Zeile in Textstücke (**fett**, `code`, [Link](url))."""
    spans: list[Span] = []
    pos = 0
    for match in _INLINE.finditer(text):
        if match.start() > pos:
            spans.append(Span(text[pos : match.start()]))
        if match.group("bold") is not None:
            spans.append(Span(match.group("bold"), "bold"))
        elif match.group("code") is not None:
            spans.append(Span(match.group("code"), "code"))
        else:
            # `**` in der Beschriftung entfernen: Links sind ohnehin
            # hervorgehoben, und verschachtelte Auszeichnung kann der Renderer
            # nicht — die Sternchen stünden sonst roh im Text.
            label = match.group("label").replace("**", "")
            spans.append(Span(label, "link", match.group("href")))
        pos = match.end()
    if pos < len(text):
        spans.append(Span(text[pos:]))
    return tuple(spans)


def parse(text: str) -> list[Block]:
    """Handbuch-Markdown -> Blockliste (siehe Modul-Docstring zum Umfang).

    Mehrzeilige Absätze und Aufzählungspunkte werden **erst zusammengefügt und
    dann** ausgezeichnet — sonst zerrisse ein `**fett**`, das im Quelltext über
    den Zeilenumbruch reicht, in zwei unbrauchbare Hälften.
    """
    blocks: list[Block] = []
    pending: list[str] = []
    bullet_style: tuple[int, str] | None = None  # (Ebene, Aufzählungszeichen)

    def flush() -> None:
        nonlocal bullet_style
        if pending:
            spans = parse_inline(" ".join(pending))
            if bullet_style is None:
                blocks.append(Block("p", spans))
            else:
                level, marker = bullet_style
                blocks.append(Block("bullet", spans, level=level, marker=marker))
            pending.clear()
        bullet_style = None

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        stripped = line.strip()

        if stripped.startswith(_FENCE):  # Codeblock bis zum schließenden ```
            flush()
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith(_FENCE):
                code.append(lines[index])
                index += 1
            index += 1  # schließende Zeile überspringen
            blocks.append(Block("code", (Span("\n".join(code)),)))
            continue

        if not stripped:
            flush()
            continue

        heading = _HEADING.match(line)
        if heading:
            flush()
            title = heading.group("title")
            anchor = ""
            found = _ANCHOR.search(title)
            if found:
                anchor = found.group("anchor")
                title = title[: found.start()].rstrip()
            blocks.append(
                Block(f"h{len(heading.group('hashes'))}", parse_inline(title), anchor=anchor)
            )
            continue

        bullet = _BULLET.match(line)
        if bullet:
            flush()
            marker = bullet.group("marker")
            bullet_style = (
                1 if len(bullet.group("indent")) >= 2 else 0,
                "•" if marker == "-" else marker,
            )
            pending.append(bullet.group("rest"))
            continue

        # Folgezeile: gehört zum laufenden Absatz bzw. Aufzählungspunkt.
        pending.append(stripped)

    flush()
    return blocks


def anchors(blocks: list[Block]) -> set[str]:
    """Alle vergebenen Anker-IDs (für Tests und die Kontexthilfe)."""
    return {block.anchor for block in blocks if block.anchor}


def chapters(blocks: list[Block]) -> list[Block]:
    """Die Kapitel für die Seitenleiste (alle `##`-Überschriften)."""
    return [block for block in blocks if block.kind == "h2"]


# -------------------------------------------------------------------- Fenster
class HelpWindow(tk.Toplevel):
    """Handbuch-Fenster: Kapitelliste links, Text rechts.

    Bewusst **nicht** modal — man soll parallel weiterarbeiten und beim Ausfüllen
    nachlesen können. `App` hält genau eine Instanz und ruft `show()` erneut.
    """

    def __init__(
        self, parent: tk.Misc, palette: Palette, *, menubar: tk.Menu | None = None
    ) -> None:
        super().__init__(parent)
        self._palette = palette
        self._path = handbook_path()
        self._mtime: float | None = None
        self._blocks: list[Block] = []
        # Kapitel der Seitenleiste: (Titel, Name der Text-Marke).
        self._chapters: list[tuple[str, str]] = []
        self._anchor_marks: dict[str, str] = {}
        self._link_targets: dict[str, str] = {}
        self._syncing = False

        self.title("Handbuch — QSL-Karten-Generator")
        self.geometry(WINDOW_SIZE)
        self.minsize(*WINDOW_MIN)
        self.transient(parent.winfo_toplevel())
        # Dieselbe Menüleiste wie das Hauptfenster (Tk legt sich dafür einen Klon
        # an). Ohne das zeigt macOS über einem Fenster ohne eigenes Menü die
        # Standardleiste von Tk — mit „Python"-Menü und Tk-Hilfeeinträgen, die
        # nichts mit diesem Programm zu tun haben.
        if menubar is not None:
            self.configure(menu=menubar)

        self._build_fonts()
        self._build_widgets()
        self.apply_palette(palette)
        self.reload()

        self.bind("<Escape>", lambda _e: self.destroy())
        # Nach dem Bearbeiten im Editor: beim Zurückwechseln neu einlesen.
        self.bind("<FocusIn>", self._on_focus_in)

    # ------------------------------------------------------------ Aufbau
    def _build_fonts(self) -> None:
        base = tkfont.nametofont("TkDefaultFont")
        family = base.cget("family")
        size = int(base.cget("size"))

        def sized(delta: int, *, bold: bool = False) -> tkfont.Font:
            # Negative Größen sind Pixel: größer heißt dort „negativer".
            px = size - delta if size < 0 else size + delta
            return tkfont.Font(family=family, size=px, weight="bold" if bold else "normal")

        self._fonts = {
            "body": sized(0),
            "bold": sized(0, bold=True),
            "h1": sized(H1_DELTA, bold=True),
            "h2": sized(H2_DELTA, bold=True),
            "h3": sized(H3_DELTA, bold=True),
        }
        fixed = tkfont.nametofont("TkFixedFont")
        self._fonts["code"] = tkfont.Font(family=fixed.cget("family"), size=size)

    def _build_widgets(self) -> None:
        body = ttk.Frame(self, padding=PAD_INNER)
        body.pack(fill="both", expand=True)

        self.sidebar = tk.Listbox(
            body,
            width=SIDEBAR_WIDTH,
            activestyle="none",
            exportselection=False,
            highlightthickness=1,
        )
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, PAD_INNER))
        self.sidebar.bind("<<ListboxSelect>>", self._on_chapter_selected)
        bind_wheel(self.sidebar, self._on_sidebar_wheel)

        self.text = tk.Text(
            body,
            wrap="word",
            padx=PAD_INNER * 2,
            pady=PAD_INNER,
            borderwidth=1,
            relief="solid",
            highlightthickness=0,
            cursor="arrow",
            state="disabled",
        )
        self.text.grid(row=0, column=1, sticky="nsew")
        self.scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.scroll.grid(row=0, column=2, sticky="ns")
        self.text.configure(yscrollcommand=self._on_yview)
        bind_wheel(self.text, self._on_text_wheel)

        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

    # ------------------------------------------------------------- Inhalt
    def reload(self) -> None:
        """Handbuch neu einlesen und darstellen (Anzeigeposition geht verloren)."""
        self._path = handbook_path()
        self._mtime = self._current_mtime()
        self._blocks = parse(load_handbook(self._path))
        self._render()

    def _current_mtime(self) -> float | None:
        try:
            return self._path.stat().st_mtime
        except OSError:
            return None

    def _render(self) -> None:
        text = self.text
        text.configure(state="normal")
        text.delete("1.0", "end")
        self._chapters = []
        self._anchor_marks = {}
        self._link_targets = {}

        for number, block in enumerate(self._blocks):
            mark = f"block-{number}"
            text.mark_set(mark, "end-1c")
            text.mark_gravity(mark, "left")
            if block.anchor:
                self._anchor_marks[block.anchor] = mark
            if block.kind == "h2":
                self._chapters.append((block.text, mark))
            self._insert_block(number, block)

        text.configure(state="disabled")
        self.sidebar.delete(0, "end")
        for title, _mark in self._chapters:
            self.sidebar.insert("end", title)
        text.yview_moveto(0.0)
        self._sync_sidebar()

    def _insert_block(self, number: int, block: Block) -> None:
        text = self.text
        if block.kind == "code":
            text.insert("end", block.text + "\n", ("codeblock",))
            return

        tags: tuple[str, ...]
        if block.kind == "bullet":
            tags = (f"bullet{block.level}",)
            text.insert("end", f"{block.marker} ", tags)
        else:
            tags = (block.kind,)

        for index, span in enumerate(block.spans):
            span_tags = tags
            if span.style == "link":
                link_tag = f"link-{number}-{index}"
                self._link_targets[link_tag] = span.href
                text.tag_bind(link_tag, "<Button-1>", self._on_link_click)
                text.tag_bind(link_tag, "<Enter>", lambda _e: self.text.configure(cursor="hand2"))
                text.tag_bind(link_tag, "<Leave>", lambda _e: self.text.configure(cursor="arrow"))
                span_tags = tags + ("link", link_tag)
            elif span.style:
                span_tags = tags + (span.style,)
            text.insert("end", span.text, span_tags)
        text.insert("end", "\n", tags)

    # ------------------------------------------------------------- Farben
    def apply_palette(self, palette: Palette) -> None:
        """Farben nachziehen (Text-Tags sind keine ttk-Styles, siehe theme.py)."""
        self._palette = palette
        self.configure(background=palette.bg)
        self.text.configure(
            background=palette.surface,
            foreground=palette.text,
            insertbackground=palette.surface,  # kein blinkender Cursor im Lesetext
            selectbackground=palette.select_bg,
            selectforeground=palette.text,
            highlightbackground=palette.border,
        )
        self.sidebar.configure(
            background=palette.surface,
            foreground=palette.text,
            selectbackground=palette.select_bg,
            selectforeground=palette.text,
            highlightbackground=palette.border,
            highlightcolor=palette.border,
        )
        spacing = {"spacing1": 6, "spacing3": 2}
        self.text.tag_configure(
            "h1", font=self._fonts["h1"], foreground=palette.text, spacing1=2, spacing3=8
        )
        self.text.tag_configure(
            "h2", font=self._fonts["h2"], foreground=palette.accent, spacing1=16, spacing3=6
        )
        self.text.tag_configure(
            "h3", font=self._fonts["h3"], foreground=palette.text, spacing1=10, spacing3=4
        )
        self.text.tag_configure("p", font=self._fonts["body"], **spacing)
        for level in (0, 1):
            indent = BULLET_INDENT * (level + 1)
            self.text.tag_configure(
                f"bullet{level}",
                font=self._fonts["body"],
                lmargin1=indent,
                lmargin2=indent + BULLET_INDENT,
                spacing3=2,
            )
        self.text.tag_configure("bold", font=self._fonts["bold"])
        self.text.tag_configure("code", font=self._fonts["code"], foreground=palette.text_muted)
        self.text.tag_configure(
            "codeblock",
            font=self._fonts["code"],
            background=palette.surface_alt,
            foreground=palette.text_muted,
            lmargin1=BULLET_INDENT,
            lmargin2=BULLET_INDENT,
            spacing1=4,
            spacing3=6,
        )
        self.text.tag_configure("link", foreground=palette.accent, underline=True)

    # ---------------------------------------------------------- Navigation
    def show(self, anchor: str | None = None) -> None:
        """Fenster nach vorn holen und (falls angegeben) zum Anker springen."""
        if self._changed_on_disk():
            self.reload()
        self.deiconify()
        self.lift()
        self.focus_set()
        if anchor:
            self.goto(anchor)

    def goto(self, anchor: str) -> bool:
        """Springt zum Anker. Unbekannter Anker: nichts tun (kein Fehler)."""
        mark = self._anchor_marks.get(anchor)
        if mark is None:
            return False
        self.text.update_idletasks()
        self.text.yview(mark)
        self._sync_sidebar()
        return True

    def _on_chapter_selected(self, _event: tk.Event) -> None:
        if self._syncing:
            return
        selection = self.sidebar.curselection()
        if not selection:
            return
        _title, mark = self._chapters[selection[0]]
        self.text.yview(mark)

    def _sync_sidebar(self) -> None:
        """Hebt in der Liste das Kapitel hervor, das gerade oben steht.

        Am unteren Ende zählt stattdessen die **letzte** Zeile: die letzten
        Kapitel sind kürzer als das Fenster, oben stünde dort also für immer das
        vorletzte — man scrollt bis zum Schluss und die Liste zeigt trotzdem
        woanders hin.
        """
        if not self._chapters:
            return
        first, last = self.text.yview()
        at_end = last >= 1.0 and first > 0.0  # `first > 0`: passt alles hinein, gilt nicht
        reference = self.text.index("end-1c" if at_end else "@0,0")
        current = 0
        for index, (_title, mark) in enumerate(self._chapters):
            if self.text.compare(mark, "<=", reference):
                current = index
        self._syncing = True
        try:
            self.sidebar.selection_clear(0, "end")
            self.sidebar.selection_set(current)
            self.sidebar.see(current)
        finally:
            self._syncing = False

    def _on_yview(self, first: str, last: str) -> None:
        self.scroll.set(first, last)
        self._sync_sidebar()

    # -------------------------------------------------------------- Maus
    def _on_text_wheel(self, event: tk.Event) -> str:
        """Mausrad über dem Text.

        Immer „break": das Hauptfenster bindet den Seiten-Scroll über `bind_all`,
        sonst würde es hinter dem Handbuch mitscrollen. Zugleich hält das die
        eingebaute Text-Klassenbindung an (sonst doppelter Weg unter Linux).
        """
        step = wheel_step(event)
        if step:
            self.text.yview_scroll(step, "units")
        return "break"

    def _on_sidebar_wheel(self, event: tk.Event) -> str:
        step = wheel_step(event)
        if step:
            self.sidebar.yview_scroll(step, "units")
        return "break"

    def _on_link_click(self, event: tk.Event) -> None:
        for tag in self.text.tag_names(f"@{event.x},{event.y}"):
            href = self._link_targets.get(tag)
            if href:
                self._follow_link(href)
                return

    def _follow_link(self, href: str) -> None:
        """`#anker` springt im Handbuch selbst, alles andere geht in den Browser."""
        if href.startswith("#"):
            self.goto(href[1:])  # unbekannter Anker: passiert nichts
        else:
            webbrowser.open(href)

    # -------------------------------------------------------------- Datei
    def _changed_on_disk(self) -> bool:
        return handbook_path() != self._path or self._current_mtime() != self._mtime

    def _on_focus_in(self, _event: tk.Event) -> None:
        if self._changed_on_disk():
            self.reload()


def open_help(
    parent: tk.Misc,
    palette: Palette,
    *,
    anchor: str | None = None,
    menubar: tk.Menu | None = None,
) -> HelpWindow:
    """Ein neues Handbuch-Fenster öffnen (Wiederverwendung macht `App`)."""
    window = HelpWindow(parent, palette, menubar=menubar)
    window.show(anchor)
    return window
