"""Die aus gui/app.py herausgezogenen Abläufe — ohne Tk, ohne Xvfb (Bewertung 3.1)."""

from __future__ import annotations

import os
import threading
from unittest import mock

import pytest

from qslcards import config as cfg
from qslcards import dxcc, mostwanted
from qslcards.config import AppConfig
from qslcards.controllers.background import run_in_background
from qslcards.controllers.config_file import ConfigFile
from qslcards.controllers.mostwanted_flow import MostWantedFlow, MostWantedPaths, format_date
from qslcards.controllers.print_job import PrintJob
from qslcards.controllers.wavelog_flow import WavelogFlow, missing_status_warning
from qslcards.logbook.models import QSO
from qslcards.wavelog import PaperQslMark, WavelogError, sent_store


class _SyncThread:
    def __init__(self, target=None, args=(), daemon=None):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)


def _now(fn, *args):
    fn(*args)


@pytest.fixture
def sync_threads():
    with mock.patch.object(threading, "Thread", _SyncThread):
        yield


# ------------------------------------------------------------ background
def test_background_delivers_result_and_errors(sync_threads):
    got = []
    run_in_background(_now, lambda: 42, lambda r, e: got.append((r, e)))
    run_in_background(_now, lambda: 1 / 0, lambda r, e: got.append((r, type(e))))
    run_in_background(
        _now,
        lambda: 1 / 0,
        lambda r, e: got.append((r, type(e))),
        wrap_error=lambda exc: WavelogError(str(exc)),
    )
    assert got == [(42, None), (None, ZeroDivisionError), (None, WavelogError)]


# ------------------------------------------------------------ config.yaml
def test_config_file_ignores_its_own_save_and_sees_foreign_changes(tmp_path):
    path = tmp_path / "config.yaml"
    file = ConfigFile(lambda: str(path))
    file.read()
    config = AppConfig()
    config.sender.callsign = "DL0MT"
    file.save(config)
    assert file.reload_if_changed().config is None  # eigenes Speichern

    other = AppConfig()
    other.sender.callsign = "DN5MT"
    cfg.save(other, path)
    os.utime(path, (file.last_mtime + 5, file.last_mtime + 5))
    result = file.reload_if_changed()
    assert result.config is not None and result.config.sender.callsign == "DN5MT"
    assert file.reload_if_changed().config is None  # nur einmal


def test_config_file_keeps_values_when_the_file_is_broken(tmp_path):
    path = tmp_path / "config.yaml"
    file = ConfigFile(lambda: str(path))
    file.save(AppConfig())
    path.write_text("sender: [kaputt", encoding="utf-8")
    os.utime(path, (file.last_mtime + 5, file.last_mtime + 5))
    result = file.reload_if_changed()
    assert result.config is None and result.error
    # Nicht bei jedem Poll erneut melden.
    assert file.reload_if_changed().error is None


def test_config_file_reports_a_damaged_file_once(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")  # abgebrochen geschrieben
    file = ConfigFile(lambda: str(path))
    file.read()
    assert file.take_problem()
    assert file.take_problem() is None


def test_config_path_is_resolved_on_each_call(tmp_path):
    current = {"path": str(tmp_path / "a.yaml")}
    file = ConfigFile(lambda: current["path"])
    file.save(AppConfig())
    current["path"] = str(tmp_path / "b.yaml")
    file.save(AppConfig())
    assert (tmp_path / "a.yaml").exists() and (tmp_path / "b.yaml").exists()


# ------------------------------------------------------------ Most Wanted
def _paths(tmp_path) -> MostWantedPaths:
    from qslcards import paths

    return MostWantedPaths(
        str(tmp_path / "mostwanted.json"),
        str(tmp_path / "cty.dat"),
        str(paths.bundled_cty_path()),
        str(paths.dxcc_numbers_path()),
    )


def test_mostwanted_status_texts(tmp_path):
    flow = MostWantedFlow(_now, lambda: _paths(tmp_path))
    assert flow.status() == ("Noch keine GDXF-Liste geladen", False)
    flow.error = "kein Netz"
    assert flow.status() == ("GDXF-Liste nicht abrufbar", True)
    flow.ranking = mostwanted.MostWantedList(year=2025, fetched_at="2026-10-26T10:00:00+00:00")
    text, error = flow.status()
    assert error and "Abruf fehlgeschlagen" in text and "2025" in text
    flow.error = None
    assert flow.status() == (f"GDXF 2025 · abgerufen {format_date(flow.ranking.fetched_at)}", False)
    flow.running = True
    assert flow.status() == ("Lade GDXF-Liste…", False)


def test_mostwanted_does_not_touch_the_net_when_disabled(tmp_path):
    flow = MostWantedFlow(_now, lambda: _paths(tmp_path))
    with mock.patch.object(mostwanted, "refresh") as refresh:
        assert flow.ensure(False, lambda changed: None) is False
    refresh.assert_not_called()


def test_mostwanted_refresh_reports_a_new_cty(tmp_path, sync_threads):
    flow = MostWantedFlow(_now, lambda: _paths(tmp_path))
    flow.load_local()
    assert flow.cty is not None  # mitgelieferte Kopie
    ranking = mostwanted.MostWantedList(year=2025)
    database = flow.cty
    done = []
    with (
        mock.patch.object(mostwanted, "refresh", return_value=mostwanted.RefreshResult(ranking)),
        mock.patch.object(
            dxcc, "refresh", return_value=dxcc.CtyRefreshResult(database, fetched=True)
        ),
    ):
        assert flow.ensure(True, done.append) is True
    assert done == [True]
    assert flow.ranking is ranking and not flow.running


def test_mostwanted_worker_crash_keeps_the_old_list(tmp_path, sync_threads):
    flow = MostWantedFlow(_now, lambda: _paths(tmp_path))
    old = mostwanted.MostWantedList(year=2024)
    flow.ranking = old
    done = []
    with (
        mock.patch.object(mostwanted, "is_stale", return_value=True),
        mock.patch.object(mostwanted, "refresh", side_effect=RuntimeError("boom")),
    ):
        flow.ensure(True, done.append)
    assert done == [False]
    assert flow.ranking is old and flow.error == "boom" and not flow.running


# ------------------------------------------------------------ Wavelog
URL = "https://log.example.org"


def _qso(wid, **raw):
    return QSO(call="DL1ABC", qso_date="20261019", time_on="1200", raw={"wavelog_id": wid, **raw})


def test_wavelog_client_is_reused_until_url_or_key_change(tmp_path):
    flow = WavelogFlow(_now, lambda: str(tmp_path / "sent.json"))
    first = flow.client(URL, "wl2_a")
    assert flow.client(URL, "wl2_a") is first
    assert flow.client(URL, "wl2_b") is not first


def test_prepare_load_uses_status_and_own_marks(tmp_path):
    path = tmp_path / "sent.json"
    flow = WavelogFlow(_now, lambda: str(path))
    api = flow.api_url(URL)
    sent_store.add(path, api, ["2"])
    sent_store.set_pending(path, api, [sent_store.PendingMark("3", "B")])
    qsos = [_qso("1", qsl_sent="Y"), _qso("2", qsl_sent="N"), _qso("3", qsl_sent="N")]
    plan = flow.prepare_load(qsos, URL)
    assert [q.raw["wavelog_id"] for q in qsos if plan.is_sent(q)] == ["1", "2"]
    assert plan.pending == [PaperQslMark("3", "B")]
    assert plan.status_known and not plan.warnings and not plan.store_broken


def test_prepare_load_without_status_and_with_broken_list(tmp_path):
    path = tmp_path / "sent.json"
    path.write_text("[kaputt", encoding="utf-8")
    flow = WavelogFlow(_now, lambda: str(path))
    plan = flow.prepare_load([_qso("1")], URL)
    assert plan.store_broken and flow.store_broken and plan.warnings
    assert not plan.status_known
    # Kaputte Liste wird nie überschrieben.
    flow.save_pending(URL, [PaperQslMark("1", "B")])
    assert path.read_text(encoding="utf-8") == "[kaputt"
    assert "3 QSO(s)" in missing_status_warning(3, 10)


def test_wavelog_run_wraps_foreign_errors(tmp_path, sync_threads):
    flow = WavelogFlow(_now, lambda: str(tmp_path / "sent.json"))
    got = []
    flow.run(object(), lambda client: 1 / 0, lambda r, e: got.append((r, e, flow.busy)))
    assert got[0][0] is None and isinstance(got[0][1], WavelogError) and got[0][2] is False


# ------------------------------------------------------------ Druck
def test_print_job_reports_outputs_and_errors(tmp_path, sync_threads):
    calls = []

    def fake_generate(cards, config, front, output, progress_cb=None):
        progress_cb(1, 1)
        if output == "boom.pdf":
            raise OSError("Platte voll")
        return [tmp_path / "out.pdf"]

    job = PrintJob(_now, generate=fake_generate)
    job.start(
        ["karte"],
        AppConfig(),
        "front.jpg",
        "out.pdf",
        on_progress=lambda d, t: calls.append(("p", d, t)),
        on_done=lambda outs, err: calls.append(("done", outs, err, job.running)),
    )
    assert calls == [("p", 1, 1), ("done", [str(tmp_path / "out.pdf")], None, False)]
    assert job.cards == ["karte"]

    calls.clear()
    job.start(
        ["k"],
        AppConfig(),
        "f",
        "boom.pdf",
        on_progress=lambda *a: None,
        on_done=lambda o, e: calls.append((o, e)),
    )
    assert calls[0][0] == ["boom.pdf"] and isinstance(calls[0][1], OSError)
