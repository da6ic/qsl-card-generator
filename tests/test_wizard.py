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
