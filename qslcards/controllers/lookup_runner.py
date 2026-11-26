"""Hintergrund-Lookups mit Generationsnummer, Warteschlange und Abbruch.

Bewertung 1.4: Wurde während eines laufenden Lookups ein zweites Log geladen,
bekam es keinen eigenen Lookup, die Ergebnisse des ersten mischten sich hinein
und alle neuen Stationen standen ohne Hinweis auf „Büro". Jetzt gilt:

* Jeder `start()` bekommt eine **Generation**. Nur die neueste darf ihr
  Ergebnis abliefern; ältere werden verworfen.
* Läuft schon ein Lookup, wird er **abgebrochen** (`threading.Event`, geprüft
  vor jedem Rufzeichen) und der neue startet, **sobald der alte endet** — so
  schreiben nie zwei Läufe gleichzeitig in den Cache.
* `cancel()` bricht auf Wunsch des Nutzers ab; das Teilergebnis wird
  abgeliefert (`cancelled=True`), damit schon Gefundenes nicht verloren geht.

Kein Tk hier: der Rückweg in den GUI-Thread läuft über `schedule(fn, *args)`
(in der App `self.after(0, …)`).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from qslcards.lookup import LookupCredentials, LookupResult

Schedule = Callable[..., Any]


@dataclass
class LookupProgress:
    done: int
    total: int
    # Geschätzte Restzeit in Sekunden; None, solange zu wenig gemessen ist.
    eta_seconds: float | None = None


@dataclass
class LookupOutcome:
    generation: int
    results: dict[str, LookupResult | None]
    auth_errors: dict[str, str] = field(default_factory=dict)
    cancelled: bool = False


@dataclass
class _Job:
    generation: int
    calls: list[str]
    credentials: LookupCredentials
    force: bool
    on_progress: Callable[[LookupProgress], None] | None
    on_done: Callable[[LookupOutcome], None]
    cancel: threading.Event = field(default_factory=threading.Event)
    user_cancelled: bool = False


def format_eta(seconds: float | None) -> str:
    """„noch ca. 3 min" / „noch ca. 40 s" / "" (unbekannt)."""
    if seconds is None:
        return ""
    if seconds >= 90:
        return f"noch ca. {round(seconds / 60)} min"
    return f"noch ca. {max(5, round(seconds / 5) * 5)} s"


class LookupRunner:
    """Höchstens ein Lookup-Thread gleichzeitig, immer für die neueste Anfrage."""

    # Erst ab so vielen erledigten Rufzeichen eine Restzeit schätzen.
    ETA_MIN_DONE = 3

    def __init__(
        self,
        schedule: Schedule,
        *,
        lookup: Callable[..., dict[str, LookupResult | None]],
        thread_factory: Callable[..., Any] = threading.Thread,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._schedule = schedule
        self._lookup = lookup
        self._thread_factory = thread_factory
        self._clock = clock
        self.generation = 0
        self._active: _Job | None = None
        self._queued: _Job | None = None

    # ------------------------------------------------------------ Zustand
    @property
    def running(self) -> bool:
        """Läuft (oder wartet) ein Lookup, dessen Ergebnis noch zählt?"""
        if self._queued is not None:
            return True
        return self._active is not None and self._active.generation == self.generation

    @property
    def busy(self) -> bool:
        """Läuft überhaupt ein Thread (auch ein abgebrochener, der noch endet)?"""
        return self._active is not None or self._queued is not None

    # ------------------------------------------------------------ Steuerung
    def start(
        self,
        calls: Sequence[str],
        credentials: LookupCredentials,
        *,
        force: bool = False,
        on_done: Callable[[LookupOutcome], None],
        on_progress: Callable[[LookupProgress], None] | None = None,
    ) -> int:
        self.generation += 1
        job = _Job(self.generation, list(calls), credentials, force, on_progress, on_done)
        if self._active is not None:
            # Alten Lauf abbrechen, den neuen hinten anstellen (ein älterer
            # Wartender wird ersetzt — er wäre ohnehin veraltet).
            self._active.cancel.set()
            self._queued = job
        else:
            self._launch(job)
        return job.generation

    def cancel(self) -> bool:
        """Bricht den laufenden Lookup ab (Nutzerwunsch). True, wenn etwas lief.

        Wartet ein Lauf noch hinter einem schon abgebrochenen, bekommt er sofort
        sein (leeres) Ergebnis mit `cancelled=True` — sonst wartete die GUI auf
        eine Rückmeldung, die nie käme.
        """
        queued, self._queued = self._queued, None
        if queued is not None:
            self._schedule(queued.on_done, LookupOutcome(queued.generation, {}, {}, cancelled=True))
            if self._active is not None:
                self._active.cancel.set()
            return True
        job = self._active
        if job is None or job.cancel.is_set():
            return False
        job.user_cancelled = True
        job.cancel.set()
        return True

    # ------------------------------------------------------------ intern
    def _launch(self, job: _Job) -> None:
        self._active = job
        thread = self._thread_factory(target=self._work, args=(job,), daemon=True)
        thread.start()

    def _work(self, job: _Job) -> None:
        started = self._clock()
        auth_errors: dict[str, str] = {}

        def auth_error(provider: str, message: str) -> None:
            # Je Anbieter nur die erste Meldung, sonst stünde sie je Station da.
            auth_errors.setdefault(provider, message)

        def progress(done: int, total: int) -> None:
            eta = None
            if done >= self.ETA_MIN_DONE and done < total:
                elapsed = self._clock() - started
                eta = elapsed / done * (total - done)
            self._schedule(self._deliver_progress, job, LookupProgress(done, total, eta))

        try:
            results = self._lookup(
                job.calls,
                job.credentials,
                force=job.force,
                progress_cb=progress,
                auth_error_cb=auth_error,
                cancel=job.cancel,
            )
        except Exception:  # lookup_calls fängt eigentlich alles; nie hängen bleiben
            results = {}
        self._schedule(self._finish, job, results, auth_errors)

    def _deliver_progress(self, job: _Job, progress: LookupProgress) -> None:
        if job.generation == self.generation and job.on_progress is not None:
            job.on_progress(progress)

    def _finish(self, job: _Job, results: dict, auth_errors: dict) -> None:
        if self._active is job:
            self._active = None
        current = job.generation == self.generation
        if current:
            job.on_done(
                LookupOutcome(
                    job.generation,
                    results,
                    auth_errors,
                    cancelled=job.cancel.is_set() and job.user_cancelled,
                )
            )
        if self._queued is not None and self._active is None:
            nxt, self._queued = self._queued, None
            self._launch(nxt)
