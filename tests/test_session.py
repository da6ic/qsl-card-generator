"""SessionState/marks_for_cards: Logik ohne Tk (Bewertung 3.1)."""

from __future__ import annotations

from qslcards.cards.models import Card, CardRow
from qslcards.controllers.session import SessionState, marks_for_cards
from qslcards.logbook.models import QSO
from qslcards.wavelog import PaperQslMark


def _qso(call, wid="", sent=False):
    raw = {"wavelog_id": wid}
    if sent:
        raw["qsl_sent"] = "Y"
    return QSO(call=call, qso_date="20261019", time_on="1200", raw=raw)


def _card(route, qso_id, via_text="", already_sent=False):
    row = CardRow("19", "10", "26", "12:00", "14.074", "FT8", "", qso_id=qso_id)
    return Card(
        recipient_call="DL1ABC",
        via_text=via_text,
        via_routes=(route,),
        rows=[row],
        already_sent=already_sent,
    )


def test_load_splits_and_resets_lookups():
    state = SessionState(lookups={"OLD": None})
    state.load([_qso("A"), _qso("B", sent=True)], "file", lambda q: q.raw.get("qsl_sent") == "Y")
    assert [q.call for q in state.qsos] == ["A"]
    assert [q.call for q in state.sent_qsos] == ["B"]
    assert state.lookups == {} and state.source == "file"
    assert [q.call for q in state.visible_qsos(True)] == ["A", "B"]
    assert state.missing_lookups(False) == ["A"]


def test_mark_sent_moves_qsos_and_clears_pending():
    state = SessionState(qsos=[_qso("A", "1"), _qso("B", "2")])
    state.add_pending([PaperQslMark("1", "B"), PaperQslMark("2", "D")])
    state.add_pending([PaperQslMark("1", "M")])  # ersetzt, nicht doppelt
    assert [(m.qso_id, m.via) for m in state.pending_marks] == [("1", "M"), ("2", "D")]
    state.mark_sent(["1"])
    assert [q.call for q in state.qsos] == ["B"]
    assert [q.call for q in state.sent_qsos] == ["A"]
    assert [m.qso_id for m in state.pending_marks] == ["2"]


def test_marks_for_cards_rules():
    cards = [
        _card("B", "1"),
        _card("B", "2", via_text="DL9MGR"),
        _card("D", "3"),
        _card("Q", "4"),  # eQSL: keine Papierkarte
        _card("L", "5"),  # LoTW: keine Papierkarte
        _card("B", "6", already_sent=True),  # Nachdruck
        _card("B", ""),  # Datei-Log: keine ID
    ]
    marks = marks_for_cards(cards, ["B", "D", "Q", "L"])
    assert [(m.qso_id, m.via) for m in marks] == [("1", "B"), ("2", "M"), ("3", "D")]
