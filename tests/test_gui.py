"""Headless-GUI-Tests (macOS: Tk baut den Widget-Baum ohne sichtbares Fenster).

Kein Netz, kein echter Thread: `lookup_calls` wird gemockt und `threading.Thread`
durch eine synchrone Variante ersetzt, damit der Auto-Lookup deterministisch
im Test durchläuft. Braucht ein funktionierendes Tk — sonst wird übersprungen.
"""

from __future__ import annotations

import tkinter as tk
from unittest import mock

import pytest

from qslcards.gui import app as appmod
from qslcards.lookup.base import LookupResult

ADIF = (
    "<call:5>DL1AA<qso_date:8>20240102<time_on:4>1200<band:3>20m"
    "<mode:3>SSB<rst_sent:2>59<eor>\n"
    "<call:5>DL2BB<qso_date:8>20240102<time_on:4>1200<band:3>20m"
    "<mode:3>SSB<rst_sent:2>59<eor>\n"
    "<call:5>DL3CC<qso_date:8>20240102<time_on:4>1200<band:3>20m"
    "<mode:3>SSB<rst_sent:2>59<eor>\n"
)

FAKE = {
    "DL1AA": LookupResult(call="DL1AA", name="Anna", manager="DK0XYZ", source="hamqth"),
    "DL2BB": LookupResult(call="DL2BB", name="Bert", accepts_bureau="Y", source="hamqth"),
    "DL3CC": LookupResult(call="DL3CC", accepts_bureau="N", lotw="Y", source="hamqth"),
}


class _SyncThread:
    """Ersetzt threading.Thread: führt das Ziel sofort (synchron) aus."""

    def __init__(self, target=None, args=(), daemon=None):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)


def _fake_lookup(calls, cfg, **kw):
    return {c.strip().upper(): FAKE.get(c.strip().upper()) for c in calls}


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Echte config.yaml nicht anfassen.
    monkeypatch.setattr(appmod, "CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.setattr(appmod, "EXAMPLE_CONFIG_PATH", str(tmp_path / "missing.yaml"))
    try:
        application = appmod.App()
    except tk.TclError as exc:  # kein Display -> Test überspringen
        pytest.skip(f"kein Tk-Display: {exc}")
    yield application
    application.destroy()


def _load(app, tmp_path, log=ADIF):
    path = tmp_path / "log.adi"
    path.write_text(log, encoding="utf-8")
    app.file_section.path_var.set(str(path))
    with (
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
        mock.patch.object(appmod, "lookup_calls", side_effect=_fake_lookup),
        mock.patch.object(appmod, "messagebox"),
    ):
        app._load_log()
        app.update()  # after()-Callbacks (Lookup fertig) abarbeiten


def _row_map(app):
    """recipient_call -> Zeilenwerte (Drucken, Call, #QSOs, Via, Route, …)."""
    out = {}
    for iid in app.preview.tree.get_children():
        vals = app.preview.tree.item(iid, "values")
        out[vals[1]] = vals
    return out


def _iid_for(app, call):
    for iid in app.preview.tree.get_children():
        if app.preview.tree.item(iid, "values")[1] == call:
            return iid
    raise AssertionError(f"Zeile {call} nicht gefunden")


def test_auto_lookup_fills_via_and_manager(app, tmp_path):
    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("p")
    _load(app, tmp_path)

    assert app._lookup_running is False
    rows = _row_map(app)
    # Standard-Priorität aktiv: Büro, Direkt. Manager zählt als Büro-Weg und
    # setzt den Manager-Call ins Via-Feld (Route-Spalte). Via wird ausgeschrieben.
    assert rows["DL1AA"][3] == "Büro" and rows["DL1AA"][4] == "DK0XYZ"
    assert rows["DL2BB"][3] == "Büro"
    # Reine LoTW-Station: kein aktiver Weg -> nicht gedruckt, aber die Via-Spalte
    # zeigt trotzdem den natürlichen Weg (LOTW), nicht „—".
    assert rows["DL3CC"][3] == "LOTW"
    assert rows["DL3CC"][0] == "Nein"
    assert {c.recipient_call for c in app.preview.included_cards()} == {"DL1AA", "DL2BB"}
    # „PDF erzeugen" nach dem Lookup wieder aktiv.
    assert str(app.output_section.generate_btn["state"]) == "normal"


def test_without_credentials_all_default_via(app, tmp_path):
    # Keine Zugangsdaten -> kein Netzcall, alle Via = default_via ("B" -> „Büro").
    _load(app, tmp_path)
    rows = _row_map(app)
    assert all(rows[c][3] == "Büro" for c in ("DL1AA", "DL2BB", "DL3CC"))
    assert str(app.output_section.generate_btn["state"]) == "normal"


def test_priority_change_toggles_print_without_removing_rows(app, tmp_path):
    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("p")
    _load(app, tmp_path)

    # Nur LOTW über der Trennlinie -> die reine LoTW-Station (DL3CC) wird jetzt
    # gedruckt, die Büro-Stationen nicht. Alle Zeilen bleiben sichtbar.
    app.filter_section.set_priority(["L", "B", "D", "Q"], 1)
    app._apply_filter()
    rows = _row_map(app)
    assert set(rows) == {"DL1AA", "DL2BB", "DL3CC"}  # alle Zeilen noch da
    assert rows["DL3CC"][0] == "Ja"
    assert rows["DL2BB"][0] == "Nein"
    included = {c.recipient_call for c in app.preview.included_cards()}
    assert included == {"DL3CC"}


def test_edit_via_updates_card_and_print_flag(app, tmp_path):
    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("p")
    _load(app, tmp_path)

    # DL3CC (nur LoTW) wird nicht gedruckt. Via-Zelle auf B ändern (wie ein
    # Editor-Commit) erzwingt den Weg -> Karte + Anzeige aktualisiert, Zeile wird
    # jetzt gedruckt.
    iid = _iid_for(app, "DL3CC")
    app.preview._commit_edit(iid, "via", "B")

    card = next(c for c, _ in app.preview._rows.values() if c.recipient_call == "DL3CC")
    assert card.via_override == "B"
    row = app.preview.tree.item(iid, "values")
    assert row[3] == "Büro"  # Via-Spalte (ausgeschrieben)
    assert row[0] == "Ja"  # Drucken nachgezogen
    assert "DL3CC" in {c.recipient_call for c in app.preview.included_cards()}


def test_edit_route_changes_manager_text_only(app, tmp_path):
    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("p")
    _load(app, tmp_path)

    # DL1AA hatte via_text "DK0XYZ" (Manager). Route auf "via bureau" ändern:
    # nur der Kartentext ändert sich, Via/Drucken bleiben unberührt.
    iid = _iid_for(app, "DL1AA")
    app.preview._commit_edit(iid, "route", "via bureau")

    card = next(c for c, _ in app.preview._rows.values() if c.recipient_call == "DL1AA")
    assert card.via_text == "via bureau"
    row = app.preview.tree.item(iid, "values")
    assert row[4] == "via bureau"  # Route-Spalte
    assert row[3] == "Büro"  # Via unverändert (Manager zählt als Büro)


def test_edit_via_rejects_invalid_code(app, tmp_path):
    _load(app, tmp_path)  # ohne Credentials -> alle B
    iid = _iid_for(app, "DL1AA")
    app.preview._commit_edit(iid, "via", "Z")  # ungültig -> ignoriert
    card = next(c for c, _ in app.preview._rows.values() if c.recipient_call == "DL1AA")
    assert card.via_override is None  # ungültiger Code setzt keinen Override
    assert card.via_routes == ("B",)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
