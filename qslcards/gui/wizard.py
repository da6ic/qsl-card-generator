"""Schritt-Assistent: führt durch die Arbeit und zeigt immer nur einen Schritt.

Aufbau des Fensters (von oben nach unten):

* **Kopfleiste** — Programmname, „Schritt 2 von 5" und die Schrittleiste. Jeder
  Schritt ist anklickbar; der aktuelle ist in der Akzentfarbe, erledigte in der
  Erfolgsfarbe (siehe `theme._configure_wizard_styles`).
* **Seite** — Titel, ein Satz, was hier zu tun ist, und die Abschnitte dieses
  Schritts. Die Seite liegt in einem scrollbaren Bereich (kleine Fenster).
* **Navigationsleiste** — „Zurück", ein Hinweis, warum es (noch) nicht
  weitergeht, und „Weiter".

Der Assistent kennt keine Fachlogik. `app.py` hängt zwei Rückrufe ein:
`can_leave(index) -> str | None` (Fehlertext oder None) und
`on_enter(index)`/`on_leave(index)`.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from .theme import GAP_COL, PAD_INNER, PAD_SECTION


@dataclass(frozen=True)
class Step:
    key: str
    title: str  # kurzer Name in der Schrittleiste
    heading: str  # Seitentitel
    hint: str  # ein Satz: was ist hier zu tun


class _StepTab:
    """Ein Eintrag der Schrittleiste: „1 Quelle" + Farbbalken darunter."""

    def __init__(self, parent: tk.Misc, number: int, step: Step, command: Callable[[], None]):
        self.frame = ttk.Frame(parent, style="StepTodo.TFrame", cursor="hand2")
        self.label = ttk.Label(
            self.frame, text=f"{number}  {step.title}", style="StepTodo.TLabel", cursor="hand2"
        )
        self.label.pack(side="top", anchor="w", padx=(2, 12), pady=(0, 4))
        self.bar = ttk.Frame(self.frame, style="StepBarTodo.TFrame", height=3)
        self.bar.pack(side="top", fill="x")
        for widget in (self.frame, self.label, self.bar):
            widget.bind("<Button-1>", lambda _e: command())

    def set_state(self, state: str) -> None:
        """`state`: "Todo" | "Current" | "Done"."""
        self.frame.configure(style=f"Step{state}.TFrame")
        self.label.configure(style=f"Step{state}.TLabel")
        self.bar.configure(style=f"StepBar{state}.TFrame")
        self.state = state


class Wizard:
    """Rahmen des Assistenten. `page(i)` ist das Elternelement der Abschnitte."""

    def __init__(self, root: tk.Misc, steps: list[Step], body_parent: tk.Misc) -> None:
        self.steps = steps
        self.index = 0
        self.visited: set[int] = {0}
        self.can_leave: Callable[[int], str | None] = lambda _i: None
        self.on_enter: Callable[[int], None] = lambda _i: None
        self.on_leave: Callable[[int], None] = lambda _i: None
        self.on_blocked: Callable[[int], None] = lambda _i: None
        self.on_finish: Callable[[], None] | None = None

        # --- Kopfleiste
        self.head = ttk.Frame(root, style="WizardHead.TFrame", padding=(PAD_SECTION * 2, 10))
        top = ttk.Frame(self.head, style="WizardHead.TFrame")
        top.pack(side="top", fill="x")
        ttk.Label(top, text="QSL-KARTEN-GENERATOR", style="WizardBrand.TLabel").pack(side="left")
        self.count_var = tk.StringVar()
        ttk.Label(top, textvariable=self.count_var, style="WizardCount.TLabel").pack(side="right")
        tabs = ttk.Frame(self.head, style="WizardHead.TFrame")
        tabs.pack(side="top", fill="x", pady=(10, 0))
        self.tabs = [
            _StepTab(tabs, n, step, lambda i=n - 1: self.go(i))
            for n, step in enumerate(steps, start=1)
        ]
        for column, tab in enumerate(self.tabs):
            tab.frame.grid(row=0, column=column, sticky="we", padx=(0, 4))
            tabs.columnconfigure(column, weight=1, uniform="steps")

        # --- Navigationsleiste
        self.nav = ttk.Frame(root, style="WizardNav.TFrame", padding=(PAD_SECTION * 2, 8))
        self.back_btn = ttk.Button(self.nav, text="◀  Zurück", command=self.back)
        self.back_btn.pack(side="left")
        self.next_btn = ttk.Button(
            self.nav, text="Weiter  ▶", style="Accent.TButton", command=self.next
        )
        self.next_btn.pack(side="right")
        self.hint_var = tk.StringVar()
        self.hint_label = ttk.Label(self.nav, textvariable=self.hint_var, style="NavHint.TLabel")
        self.hint_label.pack(side="right", padx=(0, GAP_COL * 2))

        # --- Seiten (eine je Schritt, nur die aktuelle ist gepackt)
        self.pages: list[ttk.Frame] = []
        for step in steps:
            page = ttk.Frame(body_parent, padding=(PAD_SECTION * 2, PAD_SECTION * 2))
            ttk.Label(page, text=step.heading, style="PageTitle.TLabel").pack(
                side="top", anchor="w"
            )
            ttk.Label(page, text=step.hint, style="PageHint.TLabel", wraplength=820).pack(
                side="top", anchor="w", pady=(2, PAD_INNER * 2)
            )
            content = ttk.Frame(page)
            content.pack(side="top", fill="both", expand=True)
            page.content = content  # type: ignore[attr-defined]
            self.pages.append(page)
        self._render()

    # ------------------------------------------------------------ Zugriff
    def page(self, index: int) -> ttk.Frame:
        return self.pages[index].content  # type: ignore[attr-defined]

    @property
    def is_last(self) -> bool:
        return self.index == len(self.steps) - 1

    # --------------------------------------------------------- Navigation
    def next(self) -> None:
        if self.is_last:
            if self.on_finish is not None:
                self.on_finish()
            return
        self.go(self.index + 1)

    def back(self) -> None:
        if self.index > 0:
            self.go(self.index - 1)

    def go(self, target: int, *, check: bool = True) -> bool:
        """Wechselt zu Schritt `target`.

        Vorwärts müssen alle Schritte bis dahin „fertig" sein (`can_leave`);
        bleibt einer hängen, landet man dort und sieht den Grund. Zurück geht
        immer. Liefert True, wenn `target` erreicht wurde.
        """
        target = max(0, min(len(self.steps) - 1, target))
        if target == self.index:
            self._render()
            return True
        if check and target > self.index:
            for i in range(self.index, target):
                problem = self.can_leave(i)
                if problem:
                    if i != self.index:
                        self._switch(i)
                    self.show_problem(problem)
                    self.on_blocked(i)
                    return False
        self._switch(target)
        return True

    def _switch(self, target: int) -> None:
        self.on_leave(self.index)
        self.index = target
        self.visited.add(target)
        self.hint_var.set("")
        self._render()
        self.on_enter(target)

    def show_problem(self, text: str) -> None:
        self.hint_label.configure(style="NavDanger.TLabel")
        self.hint_var.set(text)

    def show_hint(self, text: str) -> None:
        self.hint_label.configure(style="NavHint.TLabel")
        self.hint_var.set(text)

    def _render(self) -> None:
        for i, page in enumerate(self.pages):
            if i == self.index:
                page.pack(side="top", fill="both", expand=True)
            else:
                page.pack_forget()
        for i, tab in enumerate(self.tabs):
            if i == self.index:
                tab.set_state("Current")
            elif i in self.visited and i < len(self.steps) - 1 and not self.can_leave(i):
                tab.set_state("Done")
            else:
                tab.set_state("Todo")
        self.count_var.set(f"SCHRITT {self.index + 1}/{len(self.steps)}")
        self.back_btn.configure(state="normal" if self.index > 0 else "disabled")
        if self.is_last:
            self.next_btn.pack_forget()  # auf der letzten Seite: „PDF erzeugen" im Inhalt
        elif not self.next_btn.winfo_manager():
            self.next_btn.pack(side="right", before=self.hint_label)
        nxt = self.steps[self.index + 1].title if not self.is_last else ""
        self.next_btn.configure(text=f"Weiter: {nxt}  ▶" if nxt else "Weiter  ▶")

    def refresh(self) -> None:
        """Schrittleiste neu einfärben (z.B. nachdem ein Schritt fertig wurde)."""
        self._render()
