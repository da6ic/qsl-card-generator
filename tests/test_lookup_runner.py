"""LookupRunner: neuestes Log gewinnt, Abbruch, Restzeit (Bewertung 1.4/2.4)."""

from __future__ import annotations

import threading

from qslcards.controllers.lookup_runner import LookupRunner, format_eta
from qslcards.lookup import LookupCredentials, LookupResult

CREDS = LookupCredentials(hamqth_user="u", hamqth_pass="p")


class _ManualThread:
    """Thread, der erst auf Zuruf läuft — so lassen sich Läufe überlappen."""

    created: list[_ManualThread] = []

    def __init__(self, target=None, args=(), daemon=None):
        self.target, self.args = target, args
        _ManualThread.created.append(self)

    def start(self):
        pass

    def run(self):
        self.target(*self.args)


def _runner(lookup):
    _ManualThread.created = []
    queue: list = []
    runner = LookupRunner(
        lambda fn, *a: queue.append((fn, a)), lookup=lookup, thread_factory=_ManualThread
    )
    return runner, queue


def _drain(queue):
    while queue:
        fn, args = queue.pop(0)
        fn(*args)


def _fake(calls, creds, *, force, progress_cb, auth_error_cb, cancel):
    out = {}
    for i, c in enumerate(calls, start=1):
        if cancel.is_set():
            break
        out[c] = LookupResult(call=c, source="hamqth")
        progress_cb(i, len(calls))
    return out


def test_second_start_cancels_first_and_only_newest_delivers():
    runner, queue = _runner(_fake)
    done = []
    runner.start(["A1A"], CREDS, on_done=done.append)
    runner.start(["B2B", "C3C"], CREDS, on_done=done.append)
    assert len(_ManualThread.created) == 1  # der zweite wartet
    assert runner.running

    first = _ManualThread.created[0]
    assert first.args[0].cancel.is_set()  # alter Lauf wurde abgebrochen
    first.run()
    _drain(queue)  # Ergebnis des alten wird verworfen, der neue startet
    assert done == []
    assert len(_ManualThread.created) == 2
    _ManualThread.created[1].run()
    _drain(queue)
    assert len(done) == 1
    assert set(done[0].results) == {"B2B", "C3C"}  # nichts von A1A beigemischt
    assert not done[0].cancelled
    assert not runner.running


def test_user_cancel_delivers_partial_result():
    def slow(calls, creds, *, force, progress_cb, auth_error_cb, cancel):
        out = {calls[0]: None}
        cancel.wait(0)  # erster Anruf erledigt, dann Abbruch geprüft
        return out

    runner, queue = _runner(slow)
    done = []
    runner.start(["A1A", "B2B"], CREDS, on_done=done.append)
    assert runner.cancel()
    _ManualThread.created[0].run()
    _drain(queue)
    assert done and done[0].cancelled
    assert "A1A" in done[0].results


def test_cancel_while_one_is_queued_answers_the_queued_one():
    runner, queue = _runner(_fake)
    done = []
    runner.start(["A1A"], CREDS, on_done=done.append)
    runner.start(["B2B"], CREDS, on_done=done.append)
    runner.cancel()
    _drain(queue)
    assert len(done) == 1 and done[0].cancelled and done[0].results == {}
    assert not runner.running
    _ManualThread.created[0].run()  # alter Thread endet später -> nichts passiert
    _drain(queue)
    assert len(done) == 1
    assert not runner.busy


def test_progress_reports_eta_after_a_few_calls():
    times = iter([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    seen = []
    queue: list = []
    runner = LookupRunner(
        lambda fn, *a: queue.append((fn, a)),
        lookup=_fake,
        thread_factory=lambda **kw: threading.Thread(**kw),
        clock=lambda: next(times),
    )
    runner.start(["A", "B", "C", "D", "E"], CREDS, on_done=lambda _o: None, on_progress=seen.append)
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(2)
    _drain(queue)
    assert seen[-1].done == 5
    with_eta = [p for p in seen if p.eta_seconds is not None]
    assert with_eta and with_eta[0].done == 3


def test_format_eta():
    assert format_eta(None) == ""
    assert format_eta(42) == "noch ca. 40 s"
    assert format_eta(600) == "noch ca. 10 min"
