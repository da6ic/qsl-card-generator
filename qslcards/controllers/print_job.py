"""PDF-Erzeugung im Hintergrund — ohne Tk.

Aus `gui/app.py` herausgezogen (Bewertung 3.1). Hält fest, ob gerade gedruckt
wird und welche Karten der letzte Druck enthielt (die braucht danach die
Wavelog-Markierung).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qslcards.cards.models import Card
from qslcards.config import AppConfig

from .background import Schedule, run_in_background

ProgressCb = Callable[[int, int], None]


class PrintJob:
    def __init__(self, schedule: Schedule, *, generate: Callable[..., Any]) -> None:
        self._schedule = schedule
        self._generate = generate
        self.running = False
        # Karten des letzten gestarteten Drucks.
        self.cards: list[Card] = []

    def start(
        self,
        cards: Sequence[Card],
        config: AppConfig,
        front: str,
        output: str,
        *,
        on_progress: ProgressCb,
        on_done: Callable[[list[str], BaseException | None], None],
    ) -> None:
        """Erzeugt die PDF(s); `on_done(pfade, fehler)` kommt im GUI-Thread.
        Via/Manager/Adresse stecken bereits in den Karten."""
        self.cards = list(cards)
        self.running = True

        def progress(done: int, total: int) -> None:
            self._schedule(on_progress, done, total)

        def work() -> list[str]:
            outputs = self._generate(self.cards, config, front, output, progress_cb=progress)
            return [str(p) for p in outputs]

        def finish(outputs, error) -> None:
            self.running = False
            on_done([output] if error is not None else outputs, error)

        run_in_background(self._schedule, work, finish)
