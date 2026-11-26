"""Hintergrundarbeit mit Rückweg in den GUI-Thread — ohne Tk.

Dasselbe Muster stand in `gui/app.py` dreimal (Most Wanted, Wavelog, PDF):
Thread starten, Ergebnis oder Fehler über `after(0, …)` zurückgeben. Hier
einmal, mit `schedule(fn, *args)` als Rückweg (in der App `self.after(0, …)`).

`threading.Thread` wird erst beim Aufruf aufgelöst, damit die Tests es wie
bisher über `threading.Thread` ersetzen können.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

Schedule = Callable[..., Any]


def run_in_background(
    schedule: Schedule,
    work: Callable[[], Any],
    done: Callable[[Any, BaseException | None], None],
    *,
    wrap_error: Callable[[BaseException], BaseException] | None = None,
) -> None:
    """`work()` im Hintergrund, danach `done(result, error)` im GUI-Thread.

    Jede Ausnahme kommt als `error` an, nie stirbt der Thread still.
    `wrap_error` darf eine fremde Ausnahme in die erwartete Art übersetzen.
    """

    def worker() -> None:
        try:
            result = work()
        except Exception as exc:  # bewusst breit: nie den Thread sterben lassen
            schedule(done, None, wrap_error(exc) if wrap_error else exc)
            return
        schedule(done, result, None)

    threading.Thread(target=worker, daemon=True).start()
