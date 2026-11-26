"""Schritt-Assistent: immer nur ein Schritt sichtbar, Pflichtprüfung beim Weiter,
Wavelog als Quelle bis zum Markieren nach dem Druck."""

from __future__ import annotations

from unittest import mock

import pytest
from test_gui import _load, app  # noqa: F401  (Fixture)

from qslcards.gui import app as appmod
from qslcards.wavelog import WavelogStation, qso_from_json


def _visible_pages(app):  # noqa: F811
    return [i for i, page in enumerate(app.wizard.pages) if page.winfo_manager()]


def test_only_the_current_step_is_shown(app):  # noqa: F811
    assert _visible_pages(app) == [appmod.STEP_SOURCE]
    app.wizard.go(appmod.STEP_CARDS, check=False)
    assert _visible_pages(app) == [appmod.STEP_CARDS]
    app.wizard.back()
    assert _visible_pages(app) == [appmod.STEP_LOOKUP]


def test_next_is_blocked_without_a_log(app):  # noqa: F811
    app.wizard.next()
    assert app.wizard.index == appmod.STEP_SOURCE
    assert "Logbuch" in app.wizard.hint_var.get()
    assert str(app.file_section.path_entry.cget("style")) == "Invalid.TEntry"


def test_jumping_ahead_stops_at_the_first_unfinished_step(app, tmp_path):  # noqa: F811
    _load(app, tmp_path)
    for field in app.sender_section.vars:
        app.sender_section.vars[field].set("")
    assert app.wizard.go(appmod.STEP_PRINT) is False
    assert app.wizard.index == appmod.STEP_SENDER
    assert "Pflichtfelder" in app.wizard.hint_var.get()


def test_last_step_has_no_next_button(app):  # noqa: F811
    app.wizard.go(appmod.STEP_PRINT, check=False)
    assert not app.wizard.next_btn.winfo_manager()
    app.wizard.back()
    assert app.wizard.next_btn.winfo_manager()


def test_source_switch_shows_only_the_matching_section(app):  # noqa: F811
    app.source_section.kind.set("wavelog")
    assert app.wavelog_section.frame.winfo_manager()
    assert not app.file_section.frame.winfo_manager()
    app.source_section.kind.set("file")
    assert app.file_section.frame.winfo_manager()
    assert not app.wavelog_section.frame.winfo_manager()


def test_new_credentials_restart_the_lookup_after_step_3(app, tmp_path):  # noqa: F811
    _load(app, tmp_path)  # ohne Zugangsdaten geladen
    app.lookup_section.hamqth_user.set("me")
    app.lookup_section.hamqth_pass.set("pw")
    with mock.patch.object(app, "_start_lookups") as start:
        app._on_step_leave(appmod.STEP_LOOKUP)
    start.assert_called_once()


def _wavelog_qsos():
    return [
        qso_from_json(
            {
                "id": 10,
                "call": "EA8ABC",
                "qso_date": "2026-10-19 14:38:00",
                "mode": "SSB",
                "freq": 14230000,
                "rst_sent": "59",
                "qsl_sent": "N",
            }
        ),
        qso_from_json(
            {
                "id": 11,
                "call": "JA1XYZ",
                "qso_date": "2026-10-20 08:00:00",
                "mode": "CW",
                "freq": 7025000,
                "rst_sent": "599",
                "qsl_sent": "Y",
            }
        ),
    ]


def test_wavelog_qsos_fill_the_log_and_prefill_the_sender(app):  # noqa: F811
    station = WavelogStation(1, "Home", "DL0QSL", "JO62QM", "14", "28", True)
    app.sender_section.vars["callsign"].set("")
    app.sender_section.vars["name"].set("Max")
    app.source_section.kind.set("wavelog")
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    assert [q.call for q in app.qsos] == ["EA8ABC"]  # schon gesendete ausgelassen
    assert app.qsos_source == "wavelog"
    assert app.sender_section.vars["callsign"].get() == "DL0QSL"
    assert app.sender_section.vars["name"].get() == "Max"  # nie überschrieben
    assert "1 schon gesendet" in app.wavelog_section.count_var.get()
    assert app._step_problem(appmod.STEP_SOURCE) is None


def test_after_the_pdf_the_wavelog_qsos_are_marked(app):  # noqa: F811
    station = WavelogStation(1, "Home", "DL0QSL")
    app.source_section.kind.set("wavelog")
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    app._generated_cards = app.preview.included_cards()
    with (
        mock.patch.object(appmod, "confirm", return_value=True),
        mock.patch.object(app, "_wavelog_mark_pending") as mark,
    ):
        app._after_generate_wavelog()
    mark.assert_called_once()
    assert [(m.qso_id, m.via) for m in app._pending_marks] == [("10", "B")]


@pytest.mark.parametrize("answer", [False])
def test_marking_needs_confirmation(app, answer):  # noqa: F811
    station = WavelogStation(1, "Home", "DL0QSL")
    app.source_section.kind.set("wavelog")
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    app._generated_cards = app.preview.included_cards()
    with (
        mock.patch.object(appmod, "confirm", return_value=answer),
        mock.patch.object(app, "_wavelog_mark_pending") as mark,
    ):
        app._after_generate_wavelog()
    mark.assert_not_called()
    # Später nachholbar über „Jetzt markieren".
    assert str(app.wavelog_mark_section.mark_now_btn.cget("state")) == "normal"


SENT_ADIF = (
    "<EOH>\n"
    "<CALL:6>EA8ABC <QSO_DATE:8>20261019 <TIME_ON:4>1438 <BAND:3>20m <MODE:3>SSB "
    "<RST_SENT:2>59 <QSL_SENT:1>Y <EOR>\n"
    "<CALL:6>JA1XYZ <QSO_DATE:8>20261020 <TIME_ON:4>0800 <BAND:3>40m <MODE:2>CW "
    "<RST_SENT:3>599 <QSL_SENT:1>N <EOR>\n"
)


def test_log_file_skips_already_sent_cards(app, tmp_path):  # noqa: F811
    _load(app, tmp_path, log=SENT_ADIF)
    assert [q.call for q in app.qsos] == ["JA1XYZ"]
    assert "1 schon gesendet" in app.file_section.count_var.get()


def test_marked_qsos_leave_the_session_and_stay_skipped(app):  # noqa: F811
    station = WavelogStation(1, "Home", "DL0QSL")
    app.source_section.kind.set("wavelog")
    app.wavelog_section.url.set("https://log.example.org")
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    app._pending_marks = app._marks_for(app.preview.included_cards())
    app._wavelog_mark_done((["10"], []), None)
    assert app.qsos == []  # gesendet -> keine Karte mehr in dieser Sitzung

    # Neuer Abruf: Wavelog meldet den Status diesmal NICHT mit (Feld fehlt).
    fresh = [
        qso_from_json(
            {
                "id": 10,
                "call": "EA8ABC",
                "qso_date": "2026-10-19 14:38:00",
                "mode": "SSB",
                "freq": 14230000,
                "rst_sent": "59",
            }
        )
    ]
    app._wavelog_qsos_done(station, fresh, None)
    assert app.qsos == []  # die eigene Liste fängt es ab


# -- Bewertung 1.3 / 1.4 / 2.2 ---------------------------------------------


def test_wavelog_without_status_shows_a_visible_warning(app):  # noqa: F811
    station = WavelogStation(1, "Home", "DL0QSL")
    app.source_section.kind.set("wavelog")
    qsos = _wavelog_qsos()
    for q in qsos:
        q.raw.pop("qsl_sent", None)  # Instanz liefert den Status nicht
    app._wavelog_qsos_done(station, qsos, None)
    warning = app.wavelog_section.warning_var.get()
    assert "meldet den Versandstatus nicht" in warning
    assert "2 geladenen" in warning


def test_broken_sent_list_is_reported_and_kept(app, tmp_path):  # noqa: F811
    path = tmp_path / "wavelog_sent.json"
    path.write_text("{kaputt", encoding="utf-8")
    station = WavelogStation(1, "Home", "DL0QSL")
    app.source_section.kind.set("wavelog")
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    assert "beschädigt" in app.wavelog_section.warning_var.get()
    app._pending_marks = app._marks_for(app.preview.included_cards())
    with mock.patch.object(appmod, "messagebox"):
        app._wavelog_mark_done((["10"], []), None)
    assert path.read_text(encoding="utf-8") == "{kaputt"  # nie still ersetzt


def test_show_sent_offers_a_reprint_unchecked(app, tmp_path):  # noqa: F811
    from test_wizard import SENT_ADIF

    _load(app, tmp_path, log=SENT_ADIF)
    assert [c.recipient_call for c in app.preview.included_cards()] == ["JA1XYZ"]
    assert "(1)" in app.preview.show_sent_check.cget("text")
    app.preview.show_sent.set(True)
    app.update()
    calls = sorted(c.recipient_call for c in app.preview.all_cards())
    assert calls == ["EA8ABC", "JA1XYZ"]
    # Die Nachdruck-Karte steht auf „Nein".
    assert [c.recipient_call for c in app.preview.included_cards()] == ["JA1XYZ"]


def test_eqsl_and_lotw_cards_are_never_marked_as_paper(app):  # noqa: F811
    station = WavelogStation(1, "Home", "DL0QSL")
    app.source_section.kind.set("wavelog")
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    cards = app.preview.included_cards()
    for card in cards:
        card.via_override = "Q"
    with mock.patch.object(app, "_active_via_priority", return_value=["Q", "B"]):
        assert app._marks_for(cards) == []


def test_pending_marks_survive_a_restart(app):  # noqa: F811
    station = WavelogStation(1, "Home", "DL0QSL")
    app.source_section.kind.set("wavelog")
    app.wavelog_section.url.set("https://log.example.org")
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    app._generated_cards = app.preview.included_cards()
    with mock.patch.object(appmod, "confirm", return_value=False):  # „erst Probedruck"
        app._after_generate_wavelog()
    app._pending_marks = []  # „Neustart"
    app._wavelog_qsos_done(station, _wavelog_qsos(), None)
    assert [m.qso_id for m in app._pending_marks] == ["10"]
    assert str(app.wavelog_mark_section.mark_now_btn.cget("state")) == "normal"


def test_second_log_during_lookup_gets_its_own_lookup(app, tmp_path):  # noqa: F811
    """Bewertung 1.4: Log B während Lookup A — B wird nachgeschlagen, A verworfen."""
    from test_gui import ADIF, FAKE

    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("p")
    threads = []

    class _Deferred:
        def __init__(self, target=None, args=(), daemon=None):
            self.target, self.args = target, args
            threads.append(self)

        def start(self):
            pass

    seen_calls = []

    def fake_lookup(calls, creds, **kw):
        seen_calls.append(list(calls))
        return {c.strip().upper(): FAKE.get(c.strip().upper()) for c in calls}

    log_b = (
        "<EOH>\n<CALL:6>ZZ9ZZZ <QSO_DATE:8>20261019 <TIME_ON:4>1438 <BAND:3>20m "
        "<MODE:3>SSB <RST_SENT:2>59 <EOR>\n"
    )
    path_a, path_b = tmp_path / "a.adi", tmp_path / "b.adi"
    path_a.write_text(ADIF, encoding="utf-8")
    path_b.write_text(log_b, encoding="utf-8")
    with (
        mock.patch.object(appmod.threading, "Thread", _Deferred),
        mock.patch.object(appmod, "lookup_calls", side_effect=fake_lookup),
        mock.patch.object(appmod, "messagebox"),
    ):
        app.file_section.path_var.set(str(path_a))
        app._load_log()
        assert app._lookup_running
        app.file_section.path_var.set(str(path_b))
        app._load_log()  # während A noch läuft
        assert len(threads) == 1  # B wartet, bis A endet
        threads[0].target(*threads[0].args)  # A endet (abgebrochen)
        app.update()
        assert len(threads) == 2  # B läuft jetzt
        threads[1].target(*threads[1].args)
        app.update()
    assert not app._lookup_running
    assert seen_calls[-1] == ["ZZ9ZZZ"]
    assert set(app.lookups) == {"ZZ9ZZZ"}  # nichts aus Log A beigemischt
