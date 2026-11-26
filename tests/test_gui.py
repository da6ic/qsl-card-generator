"""Headless-GUI-Tests (macOS: Tk baut den Widget-Baum ohne sichtbares Fenster).

Kein Netz, kein echter Thread: `lookup_calls` wird gemockt und `threading.Thread`
durch eine synchrone Variante ersetzt, damit der Auto-Lookup deterministisch
im Test durchläuft. Braucht ein funktionierendes Tk — sonst wird übersprungen.
"""

from __future__ import annotations

import tkinter as tk
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tkinter import ttk
from unittest import mock

import pytest

from qslcards import config as cfg
from qslcards import mostwanted
from qslcards.gui import app as appmod
from qslcards.gui import sections
from qslcards.lookup.base import LookupResult
from qslcards.pdf.geometry import PRINT_MARGIN_MAX

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
    # Ebenso die gespeicherte Most-Wanted-Liste: ein Test sieht nur seine eigene.
    monkeypatch.setattr(appmod, "MOSTWANTED_PATH", str(tmp_path / "mostwanted.json"))
    # Die zuletzt abgerufene cty.dat ebenso; es gilt die mitgelieferte Kopie.
    monkeypatch.setattr(appmod, "CTY_PATH", str(tmp_path / "cty.dat"))
    # Selbst markierte Wavelog-QSOs: je Test eine eigene, leere Liste.
    monkeypatch.setattr(appmod, "WAVELOG_SENT_PATH", str(tmp_path / "wavelog_sent.json"))
    # Und nie ins Netz: der cty.dat-Abruf liefert im Test nur die lokale Kopie.
    monkeypatch.setattr(
        appmod.dxcc,
        "refresh",
        lambda stored, bundled, numbers, **_kw: appmod.dxcc.CtyRefreshResult(
            appmod.dxcc.load(stored, bundled, numbers)
        ),
    )
    try:
        application = appmod.App()
    except tk.TclError as exc:  # kein Display -> Test überspringen
        pytest.skip(f"kein Tk-Display: {exc}")
    # Fenster einmal abbilden lassen: an ein noch nicht gemapptes Widget
    # verschickt `event_generate` nichts. Unter Homebrew-Tk war es schon
    # gemappt, unter python.org-Tk (9.0.4) gingen <FocusOut>/<Button-1> verloren.
    application.update()
    yield application
    application.destroy()


def _load(app, tmp_path, log=ADIF, name="log.adi"):
    path = tmp_path / name
    path.write_text(log, encoding="utf-8")
    app.file_section.path_var.set(str(path))
    with (
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
        mock.patch.object(appmod, "lookup_calls", side_effect=_fake_lookup),
        mock.patch.object(appmod, "messagebox"),
    ):
        app._load_log()
        app.update()  # after()-Callbacks (Lookup fertig) abarbeiten


def _row_values(app, iid) -> dict:
    """Zeilenwerte als {Spaltenname: Wert} — über die Namen, nicht die
    Position: eine neue Spalte (wie „MW") verschöbe sonst still jeden Index."""
    columns = app.preview.tree.cget("columns")
    return dict(zip(columns, app.preview.tree.item(iid, "values"), strict=True))


def _row_map(app):
    """recipient_call -> {Spaltenname: Wert} (siehe `_row_values`)."""
    out = {}
    for iid in app.preview.tree.get_children():
        vals = _row_values(app, iid)
        out[vals["call"]] = vals
    return out


class _wheel:
    """Minimales Mausrad-Ereignis (tk.Event lässt sich nicht sinnvoll bauen)."""

    def __init__(self, delta: int, num: int | str = "??") -> None:
        self.delta = delta
        self.num = num


def _iid_for(app, call):
    for iid in app.preview.tree.get_children():
        if app.preview.tree.item(iid, "values")[1] == call:
            return iid
    raise AssertionError(f"Zeile {call} nicht gefunden")


CABRILLO = (
    "START-OF-LOG: 3.0\n"
    "CALLSIGN: DL0MT\n"
    "QSO: 14000 CW 2024-01-02 1200 DL0MT 599 14 DL1AA 599 35\n"
    "QSO:  7000 CW 2024-01-02 1230 DL0MT 599 14 DL2BB 599 35\n"
    "END-OF-LOG:\n"
)


def test_loads_a_cabrillo_log(app, tmp_path):
    """Contest-Logs kommen als Cabrillo — das Format wird am Inhalt erkannt."""
    _load(app, tmp_path, log=CABRILLO, name="contest.cbr")

    assert [q.call for q in app.qsos] == ["DL1AA", "DL2BB"]
    assert app.file_section.count_var.get() == "2 QSOs geladen"
    assert set(_row_map(app)) == {"DL1AA", "DL2BB"}


def test_unreadable_format_reports_and_keeps_the_old_log(app, tmp_path):
    """Fremdinhalt: Fehlermeldung statt „0 QSOs" — und kein Lookup-Lauf."""
    _load(app, tmp_path)
    before = list(app.qsos)

    path = tmp_path / "einkaufsliste.txt"
    path.write_text("Milch\nBrot\n", encoding="utf-8")
    app.file_section.path_var.set(str(path))
    with (
        mock.patch.object(appmod.threading, "Thread", side_effect=AssertionError("gestartet")),
        mock.patch.object(appmod, "messagebox") as box,
    ):
        app._load_log()

    box.showerror.assert_called_once()
    assert "nicht verwertbar" in box.showerror.call_args[0][1]
    assert app.qsos == before


def test_auto_lookup_fills_via_and_manager(app, tmp_path):
    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("p")
    _load(app, tmp_path)

    assert app._lookup_running is False
    rows = _row_map(app)
    # Standard-Priorität aktiv: Büro, Direkt. Manager zählt als Büro-Weg und
    # setzt den Manager-Call ins Via-Feld (Route-Spalte). Via wird ausgeschrieben.
    assert rows["DL1AA"]["via"] == "Büro" and rows["DL1AA"]["route"] == "DK0XYZ"
    assert rows["DL2BB"]["via"] == "Büro"
    # Reine LoTW-Station: kein aktiver Weg -> nicht gedruckt, aber die Via-Spalte
    # zeigt trotzdem den natürlichen Weg (LOTW), nicht „—".
    assert rows["DL3CC"]["via"] == "LOTW"
    assert rows["DL3CC"]["print"] == "Nein"
    assert {c.recipient_call for c in app.preview.included_cards()} == {"DL1AA", "DL2BB"}
    # „PDF erzeugen" nach dem Lookup wieder aktiv.
    assert str(app.output_section.generate_btn["state"]) == "normal"


def _load_with_rejected_login(app, tmp_path, provider="HamQTH", message="Wrong user name or pass"):
    """Log laden, wobei der Anbieter die Zugangsdaten ablehnt."""
    path = tmp_path / "log.adi"
    path.write_text(ADIF, encoding="utf-8")
    app.file_section.path_var.set(str(path))
    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("falsch")

    def rejecting(calls, cfg, **kw):
        kw["auth_error_cb"](provider, message)
        return {c.strip().upper(): None for c in calls}

    with (
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
        mock.patch.object(appmod, "lookup_calls", side_effect=rejecting),
        mock.patch.object(appmod, "messagebox") as box,
    ):
        app._load_log()
        app.update()
    return box


def test_rejected_login_warns_and_marks_the_fields(app, tmp_path):
    """Ohne Warnung sähe der Nutzer nur „0 Stationen gefunden"."""
    box = _load_with_rejected_login(app, tmp_path)

    box.showwarning.assert_called_once()
    title, text = box.showwarning.call_args.args
    assert title == "Anmeldung fehlgeschlagen"
    assert "HamQTH" in text and "Wrong user name or pass" in text

    entries = app.lookup_section.entries
    assert str(entries["hamqth_user"].cget("style")) == "Invalid.TEntry"
    assert str(entries["hamqth_pass"].cget("style")) == "Invalid.TEntry"
    assert str(entries["qrz_user"].cget("style")) != "Invalid.TEntry"  # QRZ war nicht dran
    assert "Anmeldung bei HamQTH fehlgeschlagen" in app.status.status_var.get()


def test_editing_the_password_clears_the_mark(app, tmp_path):
    _load_with_rejected_login(app, tmp_path)
    app.lookup_section.hamqth_pass.set("richtig")
    assert str(app.lookup_section.entries["hamqth_pass"].cget("style")) == "TEntry"


def test_successful_lookup_clears_earlier_marks(app, tmp_path):
    _load_with_rejected_login(app, tmp_path)
    _load(app, tmp_path)  # zweiter Lauf, diesmal ohne Ablehnung
    for entry in app.lookup_section.entries.values():
        assert str(entry.cget("style")) != "Invalid.TEntry"
    assert "Lookup fertig" in app.status.status_var.get()


def test_credentials_never_reach_the_config_file(app, tmp_path):
    """Zugangsdaten gelten nur für die laufende Sitzung.

    Sie standen einmal im Klartext in der config.yaml — jetzt darf sie kein
    Schreibvorgang mehr dorthin tragen.
    """
    app.lookup_section.hamqth_user.set("dl1abc")
    app.lookup_section.hamqth_pass.set("geheim")
    app.lookup_section.qrz_user.set("dl1abc")
    app.lookup_section.qrz_pass.set("auchgeheim")
    app.sender_section.vars["callsign"].set("DN5MT")  # damit es etwas zu speichern gibt
    app._auto_save()

    text = Path(appmod.CONFIG_PATH).read_text(encoding="utf-8")
    assert "DN5MT" in text  # der Auto-Save lief wirklich
    assert "geheim" not in text and "auchgeheim" not in text
    assert "hamqth" not in text and "qrz" not in text


def test_reloading_the_config_keeps_typed_credentials(app, tmp_path):
    """Eine extern geänderte config.yaml darf die getippten Zugangsdaten nicht
    wegräumen — sie stehen dort gar nicht drin."""
    app.lookup_section.hamqth_user.set("dl1abc")
    app.lookup_section.hamqth_pass.set("geheim")
    app._write_config()

    app._reload_from_file()

    assert app.lookup_section.hamqth_user.get() == "dl1abc"
    assert app.lookup_section.hamqth_pass.get() == "geheim"


def test_lookup_section_shows_the_session_hint(app):
    """Der Hinweis erklärt die beim nächsten Start leeren Felder.

    Die Farbe kommt aus dem Style (Themenwechsel!), nicht aus dem Widget.
    """
    hint = app.lookup_section.session_hint
    assert hint.cget("text") == sections.LOOKUP_SESSION_HINT
    assert str(hint.cget("style")) == "Muted.TLabel"


def test_address_export_sits_above_the_output_target(app):
    """Der Adress-/Label-Export gehört zur Ausgabe, nicht zu den Lookups.

    Die CSV entsteht beim Erzeugen und landet neben der PDF — also über der
    Zielwahl in Abschnitt 10 (und in Abschnitt 6 nicht mehr).
    """
    check = app.output_section.address_export_check
    assert str(check.winfo_parent()) == str(app.output_section.frame)
    assert check.grid_info()["row"] < app.output_section.browse_btn.grid_info()["row"]
    # Einziger Haken in Abschnitt 6 ist „Im Schlüsselbund merken" (seit 0.4.0).
    assert [
        child
        for child in app.lookup_section.frame.winfo_children()
        if isinstance(child, ttk.Checkbutton)
    ] == [app.lookup_section.remember_check]


def test_address_export_still_auto_saves(app):
    """Der Umzug ändert nur den Ort in der Oberfläche, nicht den Config-Weg."""
    app.output_section.address_export.set(True)
    app._auto_save()
    assert cfg.load(appmod.CONFIG_PATH).lookup.address_export is True


def test_without_credentials_all_default_via(app, tmp_path):
    # Keine Zugangsdaten -> kein Netzcall, alle Via = default_via ("B" -> „Büro").
    _load(app, tmp_path)
    rows = _row_map(app)
    assert all(rows[c]["via"] == "Büro" for c in ("DL1AA", "DL2BB", "DL3CC"))
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
    assert rows["DL3CC"]["print"] == "Ja"
    assert rows["DL2BB"]["print"] == "Nein"
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
    row = _row_values(app, iid)
    assert row["via"] == "Büro"  # ausgeschrieben
    assert row["print"] == "Ja"  # Drucken nachgezogen
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
    row = _row_values(app, iid)
    assert row["route"] == "via bureau"
    assert row["via"] == "Büro"  # unverändert (Manager zählt als Büro)


def test_edit_via_rejects_invalid_code(app, tmp_path):
    _load(app, tmp_path)  # ohne Credentials -> alle B
    iid = _iid_for(app, "DL1AA")
    app.preview._commit_edit(iid, "via", "Z")  # ungültig -> ignoriert
    card = next(c for c, _ in app.preview._rows.values() if c.recipient_call == "DL1AA")
    assert card.via_override is None  # ungültiger Code setzt keinen Override
    assert card.via_routes == ("B",)


# -- Schutz manuell geänderter Bemerkungen beim Ändern der globalen ----------

# ADIF mit einer Station (DL1AA) mit vier QSOs -> im Modus „pro Station" mehrere
# Karten, sobald Remarks die Zeilen/Karte begrenzen (für den Struktur-Fall).
ADIF_MULTI = "".join(
    f"<call:5>DL1AA<qso_date:8>2024010{n}<time_on:4>12{n:02d}<band:3>20m"
    f"<mode:3>SSB<rst_sent:2>59<eor>\n"
    for n in range(1, 5)
) + (
    "<call:5>DL2BB<qso_date:8>20240105<time_on:4>1200<band:3>20m" "<mode:3>SSB<rst_sent:2>59<eor>\n"
)


def _set_global_remarks(app, value, *, overwrite):
    """Setzt die globale Bemerkung und stößt den Commit an; der Überschreiben-Dialog
    wird auf die gewünschte Antwort gemockt."""
    app.remarks_section.remarks.set(value)
    with mock.patch.object(appmod, "ask_overwrite_manual_remarks", return_value=overwrite):
        app._on_remarks_commit()


def test_manual_remark_kept_on_global_change(app, tmp_path):
    _load(app, tmp_path)  # per_qso, drei Stationen
    _set_global_remarks(app, "A", overwrite=False)  # noch keine manuelle -> kein Dialog
    app.preview._commit_edit(_iid_for(app, "DL1AA"), "remarks", "X")

    _set_global_remarks(app, "B", overwrite=False)  # „Nicht überschreiben"

    remarks = {
        c.recipient_call: (c.remarks, c.remarks_manual) for c, _ in app.preview._rows.values()
    }
    assert remarks["DL1AA"] == ("X", True)  # manuelle Bemerkung geschützt
    assert remarks["DL2BB"] == ("B", False)  # übrige folgen dem neuen globalen Text


def test_manual_remark_overwritten_when_chosen(app, tmp_path):
    _load(app, tmp_path)
    _set_global_remarks(app, "A", overwrite=False)
    app.preview._commit_edit(_iid_for(app, "DL1AA"), "remarks", "X")

    _set_global_remarks(app, "B", overwrite=True)  # „Überschreiben"

    remarks = {
        c.recipient_call: (c.remarks, c.remarks_manual) for c, _ in app.preview._rows.values()
    }
    assert remarks["DL1AA"] == ("B", False)
    assert remarks["DL2BB"] == ("B", False)


def test_manual_remark_kept_on_global_delete_per_station(app, tmp_path):
    # Struktur-Fall: „pro Station", global setzen -> weniger Zeilen/Karte -> Station
    # gesplittet; eine Karte manuell ändern; global löschen -> Zeilen mergen wieder.
    # Die manuelle Bemerkung muss an ihren QSO-Zeilen hängen bleiben.
    app.mode_section.card_mode.set("per_station")
    _load(app, tmp_path, log=ADIF_MULTI)
    _set_global_remarks(app, "A", overwrite=False)

    # Erste DL1AA-Karte (mehrere Zeilen) manuell auf „X".
    app.preview._commit_edit(_iid_for(app, "DL1AA"), "remarks", "X")

    _set_global_remarks(app, "", overwrite=False)  # global löschen, nicht überschreiben

    dl1 = [c for c, _ in app.preview._rows.values() if c.recipient_call == "DL1AA"]
    manual = [c for c in dl1 if c.remarks_manual]
    assert len(manual) == 1 and manual[0].remarks == "X"  # manuelle Karte überlebt
    # Nicht-manuelle DL1AA-Zeilen tragen den (geleerten) globalen Text.
    assert all(c.remarks == "" for c in dl1 if not c.remarks_manual)


# -- Absender ---------------------------------------------------------------


def test_callsign_is_uppercased_when_leaving_the_field(app):
    """Rufzeichen groß, sobald das Feld den Fokus verliert.

    Beim Tippen bewusst nicht: das Setzen der Variablen rückte die Schreibmarke
    ans Ende. Die Karte selbst schreibt zusätzlich groß (layout_back).
    """
    entry = app.sender_section.entries["callsign"]
    var = app.sender_section.vars["callsign"]

    var.set(" dl2sct ")
    assert var.get() == " dl2sct "  # während des Tippens unangetastet

    entry.event_generate("<FocusOut>")
    assert var.get() == "DL2SCT"
    assert app._gather_config().sender.callsign == "DL2SCT"


@pytest.mark.parametrize(
    "field,typed,expected", [("locator", "jo31ab", "JO31AB"), ("dok", "b01", "B01")]
)
def test_locator_and_dok_are_uppercased(app, field, typed, expected):
    app.sender_section.vars[field].set(typed)
    app.sender_section.entries[field].event_generate("<FocusOut>")
    assert app.sender_section.vars[field].get() == expected


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("f/dl0mt/p", "F/DL0MT/P"),  # Gastrufzeichen + Portabel-Kennung
        ("dl0mt/qrp", "DL0MT/QRP"),
        ("dl0mt/mm", "DL0MT/MM"),  # maritime mobile
        ("w1aw/4", "W1AW/4"),  # Rufbezirk
    ],
)
def test_callsign_keeps_everything_that_belongs_to_it(app, typed, expected):
    """Das Rufzeichenfeld ist die einzige Wahrheit — nichts wird abgetrennt.

    Ein Dropdown für die Portabel-Kennung gab es kurz; es musste Präfixe,
    `/QRP`, `/MM` und Rufbezirke von den vier eigenen Kennungen unterscheiden.
    Ohne das Dropdown gibt es diese Fälle nicht mehr.
    """
    app.sender_section.vars["callsign"].set(typed)
    app.sender_section.entries["callsign"].event_generate("<FocusOut>")

    assert app.sender_section.vars["callsign"].get() == expected
    assert app._gather_config().sender.callsign == expected


def test_sender_section_has_no_portable_widget(app):
    """Das Dropdown ist weg — und darf nicht durch die Hintertür zurückkommen."""
    assert not hasattr(app.sender_section, "portable")
    assert not hasattr(app.sender_section, "portable_combo")


# -- Aussehen, Menüleiste und „Zuletzt verwendet" ---------------------------


def test_theme_applied_on_start(app):
    """Beim Start hängt das Farbthema am Fenster (clam + Palette)."""
    from tkinter import ttk

    from qslcards.gui import theme

    assert app.palette in (theme.LIGHT, theme.DARK)
    style = ttk.Style(app)
    assert style.theme_use() == "clam"
    assert style.lookup("Accent.TButton", "background") == app.palette.accent
    # Der Erzeugen-Button ist der Primärbutton.
    assert str(app.output_section.generate_btn.cget("style")) == "Accent.TButton"


def test_remarks_counter_follows_input(app):
    """Abschnitt 8 zeigt „geschrieben/erlaubt" und läuft beim Tippen mit."""
    from qslcards.gui.sections import REMARKS_MAX_LEN

    section = app.remarks_section
    assert section.count_var.get() == f"0/{REMARKS_MAX_LEN}"

    section.remarks.set("TNX FR QSO")
    assert section.count_var.get() == f"10/{REMARKS_MAX_LEN}"
    assert str(section.count_label.cget("style")) == "Muted.TLabel"

    # Limit erreicht -> Zähler wird hervorgehoben.
    section.remarks.set("x" * REMARKS_MAX_LEN)
    assert section.count_var.get() == f"{REMARKS_MAX_LEN}/{REMARKS_MAX_LEN}"
    # Hervorhebung in der Akzentfarbe des Themas, nicht in Warn-Orange.
    assert str(section.count_label.cget("style")) == "Accent.TLabel"

    section.remarks.set("")
    assert section.count_var.get() == f"0/{REMARKS_MAX_LEN}"
    assert str(section.count_label.cget("style")) == "Muted.TLabel"


def test_remarks_entry_still_enforces_the_limit(app):
    """Der Zähler ersetzt die Begrenzung nicht — mehr als 80 Zeichen sind per
    Tastatur weiterhin nicht eingebbar."""
    from qslcards.gui.sections import REMARKS_MAX_LEN

    entry = app.remarks_section.remarks_entry
    assert str(entry.cget("validate")) == "key"
    # validatecommand ist "<befehlsname> %P" -> für den direkten Aufruf muss der
    # Platzhalter für den vorgeschlagenen Text abgeschnitten werden.
    command = str(entry.cget("validatecommand")).rsplit(" ", 1)[0]
    assert app.call(command, "x" * REMARKS_MAX_LEN) in (1, "1", True)
    assert app.call(command, "x" * (REMARKS_MAX_LEN + 1)) in (0, "0", False)


def test_listbox_selection_uses_theme_color(app):
    """Die Prioritätsliste (klassisches tk-Widget) muss schon beim Start die
    Auswahlfarbe des Themas tragen — nicht die des Betriebssystems."""
    listbox = app.filter_section.listbox
    assert listbox.cget("selectbackground") == app.palette.select_bg
    assert listbox.cget("selectforeground") == app.palette.text
    assert listbox.cget("background") == app.palette.surface


def test_radio_and_checkbutton_indicators_use_accent(app):
    """Angewählte Radio-/Checkbuttons zeigen die Akzentfarbe.

    `clam` färbt den Indikator über `indicatorbackground`/`indicatorforeground`
    — `indicatorcolor` (die Option der alten tk-Widgets) wird ignoriert.
    """
    from tkinter import ttk

    style = ttk.Style(app)
    for widget in ("TRadiobutton", "TCheckbutton"):
        assert style.lookup(widget, "indicatorbackground", ["selected"]) == app.palette.accent
        assert style.lookup(widget, "indicatorforeground", ["selected"]) == app.palette.accent_text
        # nicht angewählt: unauffällige Fläche in Feldfarbe
        assert style.lookup(widget, "indicatorbackground") == app.palette.surface


def test_app_icons_are_largest_first(app):
    """Das größte Bild muss zuerst kommen.

    `wm iconphoto` skaliert auf macOS das ERSTE übergebene Bild auf alle
    gebrauchten Größen — steht dort ein kleines, ist das Dock-Icon verpixelt.
    """
    icons = appmod.load_app_icons(app)
    assert icons, "keine Icon-PNGs gefunden (scripts/make_icon.py ausführen)"
    widths = [icon.width() for icon in icons]
    assert widths == sorted(widths, reverse=True)
    assert widths[0] == appmod.ICON_SIZES[0]


def test_switch_theme_updates_widgets_and_config(app, tmp_path):
    from qslcards.gui import theme

    app._set_theme("dark")
    assert app.palette is theme.DARK
    assert app.base_config.appearance.theme == "dark"
    assert app.menubar.theme_var.get() == "dark"
    assert app.filter_section.listbox.cget("background") == theme.DARK.surface
    assert app.preview._palette is theme.DARK

    app._set_theme("light")
    assert app.palette is theme.LIGHT
    assert app.filter_section.listbox.cget("background") == theme.LIGHT.surface

    # Das Thema landet in der Config-Datei und übersteht ein erneutes Laden.
    saved = cfg.load(appmod.CONFIG_PATH)
    assert saved.appearance.theme == "light"


def test_switch_theme_keeps_label_styles(app):
    """Nach einem Wechsel färben weiter die Styles, nicht das Widget selbst.

    Vorher schrieb `tk_setPalette` die Textfarbe auf jedes Label — der rote `*`
    der Pflichtfelder, die blauen Abschnittstitel und die Statusleiste verloren
    dabei ihre Farbe. Deshalb hier über den ganzen Baum: kein `TLabel` darf eine
    eigene Farbe tragen, sonst kommt der Style nicht mehr durch.
    """
    from tkinter import ttk

    from qslcards.gui import theme

    app._set_theme("dark")
    app._set_theme("light")

    stamped: list[str] = []

    def walk(widget):
        if widget.winfo_class() == "TLabel":
            for option in ("foreground", "background"):
                if str(widget.cget(option)):
                    stamped.append(f"{widget}: {option}={widget.cget(option)}")
        for child in widget.winfo_children():
            walk(child)

    walk(app)
    assert not stamped, f"Labels mit eigener Farbe: {stamped[:3]}"

    # Und die Styles selbst tragen die Farben des hellen Themas.
    style = ttk.Style(app)
    assert style.lookup("Required.TLabel", "foreground") == theme.LIGHT.danger
    assert style.lookup("SectionTitle.TLabel", "foreground") == theme.LIGHT.accent
    assert style.lookup("Status.TLabel", "background") == theme.LIGHT.surface_alt


def test_status_bar_reports_loaded_log(app, tmp_path):
    _load(app, tmp_path)
    assert "3 QSOs" in app.status.info_var.get()
    assert app.status.status_var.get()  # irgendeine Meldung steht da


def test_recent_files_are_remembered(app, tmp_path):
    _load(app, tmp_path)
    log_path = str(tmp_path / "log.adi")
    assert app.base_config.recent.logs == [log_path]

    image = tmp_path / "bild.png"
    image.write_bytes(b"")  # Inhalt egal: das Thumbnail scheitert nur sichtbar
    app._set_image(str(image))
    assert app.base_config.recent.images == [str(image)]

    # Gespeichert wird sofort -> nach dem Neuladen der Datei noch da.
    saved = cfg.load(appmod.CONFIG_PATH)
    assert saved.recent.logs == [log_path]
    assert saved.recent.images == [str(image)]

    app._clear_recent()
    assert app.base_config.recent.logs == [] and app.base_config.recent.images == []


def test_autosave_keeps_appearance_and_recent(app, tmp_path):
    """Der Auto-Save baut die Config aus den Widgets — Aussehen und
    „Zuletzt verwendet" haben keine Widgets und dürfen nicht verloren gehen."""
    _load(app, tmp_path)
    app._set_theme("dark")
    app.sender_section.vars["callsign"].set("DN5MT")
    app._auto_save()

    saved = cfg.load(appmod.CONFIG_PATH)
    assert saved.sender.callsign == "DN5MT"
    assert saved.appearance.theme == "dark"
    assert saved.recent.logs == [str(tmp_path / "log.adi")]


def test_print_margin_block_follows_the_toggle(app):
    """Abschnitt 10: die Randfelder erscheinen erst über „Erweiterte
    Einstellungen" und verschwinden wieder."""
    section = app.printmode_section
    app.wizard.go(appmod.STEP_PRINT, check=False)  # Abschnitt 10 steht auf Schritt 5
    app.update_idletasks()
    assert not section.margin_frame.winfo_ismapped()

    section.advanced.set(True)
    section.update_advanced_visibility()
    app.update_idletasks()
    assert section.margin_frame.winfo_ismapped()

    section.advanced.set(False)
    section.update_advanced_visibility()
    app.update_idletasks()
    assert not section.margin_frame.winfo_ismapped()


def test_print_margin_toggle_does_not_move_the_radios(app):
    """Der Umschalter sitzt rechts neben den Druckmodi; das Ein-/Ausblenden des
    Randblocks darf die Radiobuttons nicht verrücken.

    (Ein `rowspan` über die Radio-Zeilen täte genau das: Tk verteilt die Höhe
    des übergreifenden Widgets auf die übersprungenen Zeilen.)"""
    section = app.printmode_section

    def positions():
        app.update_idletasks()
        return [
            (w.winfo_rootx(), w.winfo_rooty())
            for w in (section.radio_duplex, section.radio_separate, section.advanced_check)
        ]

    closed = positions()
    # Checkbox steht rechts neben den Radios, auf Höhe der ersten Zeile.
    assert closed[2][0] > closed[0][0] + section.radio_duplex.winfo_width()
    assert closed[2][1] == closed[0][1]

    section.advanced.set(True)
    section.update_advanced_visibility()
    assert positions() == closed

    section.advanced.set(False)
    section.update_advanced_visibility()
    assert positions() == closed


def test_print_margin_toggle_keeps_the_section_height(app):
    """Der Platz des Randblocks ist immer reserviert: Abschnitt 10 behält seine
    Höhe und schiebt die Ausgabe darunter beim Auf-/Zuklappen nicht weg."""
    section = app.printmode_section

    def geometry():
        app.update_idletasks()
        return section.frame.winfo_reqheight(), app.output_section.frame.winfo_rooty()

    closed = geometry()
    section.advanced.set(True)
    section.update_advanced_visibility()
    assert geometry() == closed

    section.advanced.set(False)
    section.update_advanced_visibility()
    assert geometry() == closed


def test_print_margins_parsed_and_clamped(app):
    """Eingaben landen als geclampte mm-Werte in der Config: deutsches Komma,
    leeres Feld = 0, Übergroßes auf die Obergrenze."""
    section = app.printmode_section
    section.advanced.set(True)
    section.margin_vars["margin_top"].set("3")
    section.margin_vars["margin_bottom"].set("8,5")  # Komma wie im Deutschen
    section.margin_vars["margin_left"].set("")  # leer -> 0
    section.margin_vars["margin_right"].set("99")  # über der Obergrenze

    gen = app._gather_config().generation
    assert gen.print_margin_enabled is True
    assert gen.print_margin_top == 3.0
    assert gen.print_margin_bottom == 8.5
    assert gen.print_margin_left == 0.0
    assert gen.print_margin_right == PRINT_MARGIN_MAX


def test_sheet_checkbox_maps_to_the_config_value(app):
    """Abschnitt 10: die Checkbox trägt den Config-Wert direkt (on/off-value),
    damit app.py nichts umrechnen muss."""
    section = app.printmode_section
    assert section.sheet_mode.get() == "single"
    assert app._gather_config().generation.sheet_mode == "single"

    section.sheet_check.invoke()
    assert section.sheet_mode.get() == "a4_4up"
    assert app._gather_config().generation.sheet_mode == "a4_4up"

    section.sheet_check.invoke()
    assert app._gather_config().generation.sheet_mode == "single"


def test_sheet_mode_survives_autosave(app, tmp_path):
    _load(app, tmp_path)
    app.printmode_section.sheet_mode.set("a4_4up")
    app._auto_save()

    saved = cfg.load(appmod.CONFIG_PATH)
    assert saved.generation.sheet_mode == "a4_4up"

    app._apply_config_to_widgets(saved)
    assert app.printmode_section.sheet_mode.get() == "a4_4up"


def test_sheet_mode_falls_back_on_broken_config(app, tmp_path):
    """Handgeschriebene config.yaml darf die Checkbox nicht in einen dritten
    Zustand bringen — Unbekanntes fällt auf „single" zurück."""
    broken = cfg.AppConfig()
    broken.generation.sheet_mode = "vier-pro-blatt"
    app._apply_config_to_widgets(broken)
    assert app.printmode_section.sheet_mode.get() == "single"


def test_qr_checkbox_rebuilds_cards_and_survives_autosave(app, tmp_path):
    """Abschnitt 10: der QR-Schalter landet in der Config und auf allen Karten."""
    _load(app, tmp_path)
    assert app._gather_config().generation.qr_code is False
    assert not any(c.qr_code for c, _ in app.preview._rows.values())

    app.printmode_section.qr_check.invoke()
    assert app._gather_config().generation.qr_code is True
    assert all(c.qr_code for c, _ in app.preview._rows.values())

    app._auto_save()
    saved = cfg.load(appmod.CONFIG_PATH)
    assert saved.generation.qr_code is True
    app.printmode_section.qr_code.set(False)
    app._apply_config_to_widgets(saved)
    assert app.printmode_section.qr_code.get() is True


def test_print_margins_survive_autosave(app, tmp_path):
    """Neue Variablen müssen am Auto-Save hängen, sonst gehen sie verloren."""
    _load(app, tmp_path)
    app.printmode_section.advanced.set(True)
    app.printmode_section.margin_vars["margin_bottom"].set("8")
    app._auto_save()

    saved = cfg.load(appmod.CONFIG_PATH)
    assert saved.generation.print_margin_enabled is True
    assert saved.generation.print_margin_bottom == 8.0

    # … und beim Laden stehen sie wieder in den Feldern, inklusive Sichtbarkeit.
    app._apply_config_to_widgets(saved)
    app.wizard.go(appmod.STEP_PRINT, check=False)
    app.update_idletasks()
    assert app.printmode_section.margin_vars["margin_bottom"].get() == "8"
    assert app.printmode_section.margin_frame.winfo_ismapped()


def test_menu_generate_entry_follows_button_state(app, tmp_path):
    running = mock.PropertyMock(return_value=True)
    with mock.patch.object(appmod.LookupRunner, "running", running):
        app._update_generate_state()
        assert str(app.output_section.generate_btn["state"]) == "disabled"
    app._update_generate_state()
    assert str(app.output_section.generate_btn["state"]) == "normal"


def test_open_recent_log_loads_it(app, tmp_path):
    _load(app, tmp_path)
    path = str(tmp_path / "log.adi")
    app.qsos = []
    with (
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
        mock.patch.object(appmod, "lookup_calls", side_effect=_fake_lookup),
        mock.patch.object(appmod, "messagebox"),
    ):
        app._open_recent_log(path)
        app.update()
    assert len(app.qsos) == 3
    assert app.file_section.path_var.get() == path


def test_preview_icon_backgrounds_match_their_row(app, tmp_path):
    """Die SVG-Icons sind transparent und werden gegen den Label-Hintergrund
    gemischt — der muss zur Zeile passen, sonst liegt ein Kästchen darauf."""
    from tkinter import ttk

    _load(app, tmp_path)
    preview, style, pal = app.preview, ttk.Style(app), app.palette

    # Kopf-Icons: Hintergrund = Farbe des Spaltenkopfs.
    for label in preview._header_icons.values():
        assert str(label.cget("style")) == "TreeIconHead.TLabel"
    assert style.lookup("TreeIconHead.TLabel", "background") == pal.surface_alt

    # Zellen-Icons: Zebra-Zeile hell/getönt, markierte Zeile in Auswahlfarbe.
    rows = preview.tree.get_children()
    assert preview._row_icon_style(rows[0]) == "TreeIconOdd.TLabel"
    assert preview._row_icon_style(rows[1]) == "TreeIconEven.TLabel"
    preview.tree.selection_set(rows[1])
    assert preview._row_icon_style(rows[1]) == "TreeIconSelected.TLabel"

    for name, expected in (
        ("TreeIconOdd.TLabel", pal.surface),
        ("TreeIconEven.TLabel", pal.surface_alt),
        ("TreeIconSelected.TLabel", pal.select_bg),
    ):
        assert style.lookup(name, "background") == expected


def test_preview_rows_are_striped(app, tmp_path):
    """Zebrastreifen + Graustufe für nicht gedruckte Zeilen hängen als Tags."""
    app.lookup_section.hamqth_user.set("u")
    app.lookup_section.hamqth_pass.set("p")
    _load(app, tmp_path)

    tags_by_call = {}
    for index, iid in enumerate(app.preview.tree.get_children()):
        call = app.preview.tree.item(iid, "values")[1]
        tags = app.preview.tree.item(iid, "tags")
        assert tags[0] == ("even" if index % 2 else "odd")
        tags_by_call[call] = tags
    # DL3CC (nur LoTW) wird nicht gedruckt -> zusätzliches „off"-Tag.
    assert "off" in tags_by_call["DL3CC"]
    assert "off" not in tags_by_call["DL1AA"]


def test_wheel_over_table_scrolls_the_page_at_the_end(app, tmp_path):
    """Die Vorschautabelle darf das Mausrad nur verschlucken, solange sie selbst
    scrollen kann — sonst hinge die Seite fest, sobald der Zeiger über der
    Tabelle steht (sie ist das größte Element der Oberfläche)."""
    _load(app, tmp_path)  # 3 Zeilen -> Tabelle ist nicht scrollbar
    app.wizard.go(appmod.STEP_CARDS, check=False)  # die Vorschau steht auf Schritt 4
    app.update()
    tree = app.preview.tree

    # Mit zu wenigen Zeilen steht die Tabelle sofort am Anschlag: nach unten wie
    # nach oben muss sie das Ereignis durchreichen.
    assert app.preview._on_wheel(_wheel(-120)) is None  # nach unten
    assert app.preview._on_wheel(_wheel(120)) is None  # nach oben

    # Mit vielen Zeilen scrollt die Tabelle selbst und behält das Ereignis…
    _load(app, tmp_path, log=ADIF * 6)
    app.update()
    assert app.preview._on_wheel(_wheel(-120)) == "break"
    # …bis sie unten angekommen ist.
    tree.yview_moveto(1.0)
    app.update()
    assert app.preview._on_wheel(_wheel(-120)) is None


def test_page_wheel_handles_platform_deltas(app):
    """Der Seiten-Scroll verarbeitet die Ereignisse aller Plattformen.

    (Die Schrittweite selbst prüft `tests/test_scrolling.py`; hier geht es um
    die Verdrahtung mit dem Canvas.)
    """
    canvas = app.body.canvas
    scrolled = []
    canvas.yview_scroll = lambda step, what: scrolled.append(step)  # type: ignore[method-assign]
    wheel = app.body._on_mousewheel

    wheel(_wheel(-120))  # Windows: eine Rastung nach unten
    wheel(_wheel(240))  # Windows: zwei Rastungen nach oben
    wheel(_wheel(-3))  # macOS: kleine Bewegung nach unten
    wheel(_wheel(0))  # macOS: zu kleine Bewegung -> ignorieren
    assert scrolled == [1, -2, 1]

    scrolled.clear()
    wheel(_wheel(0, num=4))  # X11/Tk 8.6: Rad nach oben
    wheel(_wheel(0, num=5))  # X11/Tk 8.6: Rad nach unten
    assert scrolled == [-1, 1]


def test_goto_section_switches_to_its_step(app, tmp_path):
    """„Gehe zu Abschnitt" springt im Assistenten auf den Schritt, auf dem der
    Abschnitt steht — ohne Pflichtprüfung, damit man überall hinkommt."""
    _load(app, tmp_path)
    for number, step in appmod.SECTION_STEP.items():
        app._goto_section(number)
        app.update()
        assert app.wizard.index == step
        assert app._sections[number].winfo_ismapped()


def _help_marks(app) -> dict[int, tk.Misc]:
    """Das „?" jedes Abschnitts (letztes Kind seines Titel-Widgets)."""
    marks = {}
    for number, frame in app._sections.items():
        title = frame.nametowidget(str(frame.cget("labelwidget")))
        marks[number] = title.winfo_children()[-1]
    return marks


def test_every_section_has_a_help_mark(app):
    marks = _help_marks(app)
    assert sorted(marks) == list(range(1, 12))
    assert {mark.cget("text") for mark in marks.values()} == {"?"}
    # Der Titel selbst bleibt sichtbar (der Text ist ins Label gewandert).
    title = app.output_section.frame.nametowidget(str(app.output_section.frame.cget("labelwidget")))
    assert title.winfo_children()[0].cget("text") == "Ausgabe"


def test_help_mark_opens_its_chapter(app):
    with mock.patch.object(app, "_show_help") as show:
        _help_marks(app)[6].event_generate("<Button-1>")
        app.update()
    show.assert_called_once_with("abschnitt-6")


def test_help_window_is_reused_and_follows_the_theme(app):
    with mock.patch.object(appmod, "open_help") as opener:
        app._show_help("abschnitt-3")
        opener.assert_called_once()
        assert opener.call_args.kwargs["anchor"] == "abschnitt-3"

    window = app._help
    assert window is not None
    with mock.patch.object(appmod, "open_help") as opener:
        app._show_help()  # zweiter Aufruf: kein zweites Fenster
        opener.assert_not_called()
    window.show.assert_called_once_with(None)

    app._apply_theme("dark")
    window.apply_palette.assert_called_once_with(app.palette)


def test_toggling_print_greys_the_row_at_once(app, tmp_path):
    """Ja -> Nein muss sofort ausgegraut sein. Eine ausgewählte Zeile zeichnet ttk
    in den Auswahlfarben und verdeckt damit den `off`-Tag — das Umschalten nimmt
    die Zeile deshalb aus der Auswahl."""
    _load(app, tmp_path)
    preview = app.preview
    iid = _iid_for(app, "DL1AA")
    preview.tree.selection_set(iid)  # Zeile war vorher ausgewählt

    preview._toggle_print(iid)
    assert preview.tree.item(iid, "values")[0] == "Nein"
    assert "off" in preview.tree.item(iid, "tags")
    assert iid not in preview.tree.selection()

    # Zurück auf Ja: Grau weg, Auswahl weiterhin nicht angetastet.
    preview._toggle_print(iid)
    assert preview.tree.item(iid, "values")[0] == "Ja"
    assert "off" not in preview.tree.item(iid, "tags")
    assert iid not in preview.tree.selection()


def _fill_required(app):
    """Alle Pflichtfelder des Absenders plausibel befüllen."""
    values = {
        "callsign": "DN5MT",
        "name": "Axel Tüner",
        "locator": "JN48OM",
        "dok": "P31",
        "waz": "14",
        "itu": "28",
    }
    for field, value in values.items():
        app.sender_section.vars[field].set(value)


def _set_front_image(app, tmp_path):
    image = tmp_path / "front.png"
    image.write_bytes(b"")  # Inhalt egal: nur die Existenz wird geprüft
    with mock.patch.object(appmod, "push_recent", side_effect=lambda items, p: items):
        app._set_image(str(image))
    return image


def test_generate_blocked_while_required_fields_are_empty(app, tmp_path):
    """Leere Pflichtfelder: ein Popup mit allen fehlenden Angaben, rote Rahmen
    an genau diesen Feldern — und nichts wird erzeugt."""
    _load(app, tmp_path)
    _set_front_image(app, tmp_path)
    _fill_required(app)
    app.sender_section.vars["callsign"].set("")
    app.sender_section.vars["dok"].set("")

    with (
        mock.patch.object(appmod, "messagebox") as box,
        mock.patch.object(appmod.threading, "Thread", side_effect=AssertionError("gestartet")),
    ):
        app._on_generate()

    box.showerror.assert_called_once()
    message = box.showerror.call_args[0][1]
    assert "Rufzeichen" in message and "DOK" in message
    assert "Name" not in message  # gefüllte Pflichtfelder tauchen nicht auf
    entries = app.sender_section.entries
    assert str(entries["callsign"].cget("style")) == "Invalid.TEntry"
    assert str(entries["dok"].cget("style")) == "Invalid.TEntry"
    assert str(entries["name"].cget("style")) in ("", "TEntry")


def test_missing_log_is_a_required_field(app, tmp_path):
    """Ohne geladenes Logbuch: Popup nennt es zuerst, das Pfadfeld wird rot —
    und nach dem Laden ist die Markierung wieder weg."""
    _fill_required(app)
    _set_front_image(app, tmp_path)

    with (
        mock.patch.object(appmod, "messagebox") as box,
        mock.patch.object(appmod.threading, "Thread", side_effect=AssertionError("gestartet")),
    ):
        app._on_generate()

    message = box.showerror.call_args[0][1]
    assert "Logbuch" in message
    assert str(app.file_section.path_entry.cget("style")) == "Invalid.TEntry"

    _load(app, tmp_path)
    assert str(app.file_section.path_entry.cget("style")) == "TEntry"


def test_required_legend_sits_below_the_sections(app, tmp_path):
    """Die Fußnote gilt fürs ganze Fenster: sie liegt außerhalb des scrollbaren
    Bereichs und unter allen Abschnitten, aber über der Statusleiste."""
    _load(app, tmp_path)
    app.update_idletasks()
    star, text = app.required_legend.winfo_children()
    # Gleiche Signalfarbe wie an den Feldern (eigener Style nur wegen der Fläche).
    assert str(star.cget("style")) == "NavRequired.TLabel"
    assert "Pflichtfeld" in text.cget("text")
    assert app.required_legend.master is app.wizard.nav  # nicht im Scrollbereich
    assert app.required_legend.winfo_rooty() > app.body.outer.winfo_rooty()
    assert app.required_legend.winfo_rooty() < app.status.frame.winfo_rooty()


def test_required_mark_disappears_when_the_field_is_filled(app, tmp_path):
    _load(app, tmp_path)
    app.sender_section.mark_missing(["callsign"])
    assert str(app.sender_section.entries["callsign"].cget("style")) == "Invalid.TEntry"

    app.sender_section.vars["callsign"].set("DN5MT")
    assert str(app.sender_section.entries["callsign"].cget("style")) == "TEntry"


def test_missing_front_image_colors_the_preview_frame(app, tmp_path):
    """Beim Frontbild ist der Rahmen des Vorschaufeldes die Markierung."""
    _load(app, tmp_path)
    _fill_required(app)

    with (
        mock.patch.object(appmod, "messagebox") as box,
        mock.patch.object(appmod.threading, "Thread", side_effect=AssertionError("gestartet")),
    ):
        app._on_generate()

    assert "Frontbild" in box.showerror.call_args[0][1]
    assert str(app.image_section.thumb_label.cget("style")) == "Invalid.Thumb.TLabel"

    _set_front_image(app, tmp_path)
    assert str(app.image_section.thumb_label.cget("style")) == "Thumb.TLabel"


def test_generate_runs_once_everything_is_filled(app, tmp_path):
    """Gegenprobe: mit allen Pflichtangaben kommt kein Popup, die Erzeugung läuft."""
    _load(app, tmp_path)
    _fill_required(app)
    _set_front_image(app, tmp_path)
    app.output_section.output_var.set(str(tmp_path / "karten.pdf"))

    with (
        mock.patch.object(appmod, "messagebox") as box,
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
        mock.patch.object(appmod, "generate", return_value=[tmp_path / "karten.pdf"]) as gen,
        mock.patch.object(appmod, "open_file"),
    ):
        app._on_generate()
        app.update()

    gen.assert_called_once()
    box.showerror.assert_not_called()
    box.showwarning.assert_not_called()


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def test_about_dialog_has_no_close_button(app):
    """Kein „Schließen": das macht die Fenstersteuerung des Systems (und Escape).

    Dieselbe Entscheidung wie beim Handbuchfenster (`test_help`), damit die
    beiden Fenster sich nicht unterschiedlich verhalten.
    """
    app._show_about()
    app.update_idletasks()
    dialog = app.winfo_children()[-1]
    try:
        assert isinstance(dialog, tk.Toplevel)
        assert dialog.title() == "Über QSL-Karten-Generator"
        widgets = list(_descendants(dialog))
        # Gegenprobe: der Inhalt ist da — die leere Button-Liste kommt nicht
        # daher, dass hier das falsche Fenster durchsucht wird.
        assert any(isinstance(w, ttk.Label) for w in widgets)
        assert [w for w in widgets if isinstance(w, ttk.Button)] == []
    finally:
        dialog.destroy()


# -- Abschnitt 7: Most Wanted ---------------------------------------------

# DXCC aus dem Log (ADIF-Feld `DXCC`), damit kein Lookup nötig ist: P5 und JA
# sind gesucht, DL nicht; XX1AA hat kein bekanntes Gebiet.
MW_ADIF = (
    "<call:4>P5AA<qso_date:8>20240102<time_on:4>1200<mode:2>CW<dxcc:3>344<eor>\n"
    "<call:5>JA1AA<qso_date:8>20240102<time_on:4>1300<mode:3>FT8<dxcc:3>339<eor>\n"
    "<call:5>DL1AA<qso_date:8>20240102<time_on:4>1400<mode:3>SSB<dxcc:3>230<eor>\n"
    "<call:5>XX1AA<qso_date:8>20240102<time_on:4>1500<mode:3>SSB<eor>\n"
)


def _mw_ranking(fetched_at=None):
    ranks = {"mixed": {344: 1, 339: 40, 230: 340}, "cw": {344: 1}, "digital": {339: 60}}
    return mostwanted.MostWantedList(
        year=2025,
        rankings={
            category: {
                dxcc: mostwanted.RankedEntity(dxcc=dxcc, rank=rank, prefix="", name="")
                for dxcc, rank in entries.items()
            }
            for category, entries in ranks.items()
        },
        fetched_at=(fetched_at or datetime.now(UTC)).isoformat(),
    )


def _enable_mostwanted(app, result):
    """Filter einschalten; der Abruf läuft synchron und liefert `result`."""
    with (
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
        mock.patch.object(appmod.mostwanted, "refresh", return_value=result) as refresh,
    ):
        app.mostwanted_section.enabled.set(True)
        app.update()
    return refresh


def test_mostwanted_is_as_wide_as_the_remarks(app):
    """Abschnitt 7 steht auf Schritt 4 unter den Bemerkungen und ist genauso
    breit („lang gezogen wie Abschnitt 8", vom Nutzer so gewünscht)."""
    app.wizard.go(appmod.STEP_CARDS, check=False)
    app.update_idletasks()
    most_wanted, remarks = app.mostwanted_section.frame, app.remarks_section.frame
    assert most_wanted.winfo_rootx() == remarks.winfo_rootx()
    assert most_wanted.winfo_width() == remarks.winfo_width()
    assert remarks.winfo_rooty() + remarks.winfo_height() <= most_wanted.winfo_rooty()
    assert app._sections[7] is most_wanted


def test_mostwanted_filter_marks_only_the_top_n(app, tmp_path):
    _load(app, tmp_path, log=MW_ADIF)
    assert {r["print"] for r in _row_map(app).values()} == {"Ja"}  # Filter aus

    refresh = _enable_mostwanted(app, mostwanted.RefreshResult(_mw_ranking(), fetched=True))
    refresh.assert_called_once()
    rows = _row_map(app)
    # Automatisch: P5 in CW Rang 1, JA in Digital Rang 60 (> Top 50 nicht, < 100 ja)
    assert rows["P5AA"]["mw"] == "1" and rows["JA1AA"]["mw"] == "60"
    assert rows["DL1AA"]["mw"] == "–"  # DL ist in Phone nicht gelistet
    assert rows["XX1AA"]["mw"] == "?"  # Gebiet unbekannt
    assert {c for c, r in rows.items() if r["print"] == "Ja"} == {"JA1AA", "P5AA"}

    # Top 50: JA fällt heraus — ohne Rebuild, nur die Markierung.
    app.mostwanted_section.top.set("50")
    rows = _row_map(app)
    assert {c for c, r in rows.items() if r["print"] == "Ja"} == {"P5AA"}

    # Feste Kategorie Mixed: DL Rang 340 liegt weiter außerhalb, JA (40) wieder drin.
    app.mostwanted_section.set_category("mixed")
    rows = _row_map(app)
    assert {c for c, r in rows.items() if r["print"] == "Ja"} == {"P5AA", "JA1AA"}
    assert rows["DL1AA"]["mw"] == "340"


def test_mostwanted_works_for_cabrillo_without_lookup(app, tmp_path):
    """Cabrillo kennt kein DXCC-Feld und ohne Zugangsdaten gibt es keinen
    Lookup — das Gebiet kommt dann aus der mitgelieferten cty.dat."""
    cabrillo = (
        "START-OF-LOG: 3.0\nCALLSIGN: DL0MT\n"
        "QSO: 14020 CW 2026-10-24 0624 DL0MT 599 14 P5AA 599 25\n"
        "QSO: 14170 PH 2026-10-24 0625 DL0MT 59 14 DL1AA 59 14\n"
        "END-OF-LOG:\n"
    )
    _load(app, tmp_path, log=cabrillo, name="contest.log")
    _enable_mostwanted(app, mostwanted.RefreshResult(_mw_ranking(), fetched=True))
    rows = _row_map(app)
    assert {c for c, r in rows.items() if r["print"] == "Ja"} == {"P5AA"}
    assert rows["P5AA"]["mw"] == "1"  # CW-Liste
    assert rows["DL1AA"]["mw"] == "–"  # Gebiet bekannt (DL), aber in Phone ohne Rang


def test_mostwanted_fresh_data_is_not_fetched_again(app, tmp_path):
    """Wer frische Daten hat (GDXF-Liste und cty.dat), löst beim Einschalten
    keinen Netzzugriff aus."""
    app.mostwanted_list = _mw_ranking()
    with mock.patch.object(appmod.dxcc, "is_stale", return_value=False):
        refresh = _enable_mostwanted(app, mostwanted.RefreshResult(None, error="darf nicht"))
    refresh.assert_not_called()


def test_mostwanted_without_list_prints_nothing_and_says_why(app, tmp_path):
    _load(app, tmp_path, log=MW_ADIF)
    _enable_mostwanted(app, mostwanted.RefreshResult(None, error="offline"))

    assert {r["print"] for r in _row_map(app).values()} == {"Nein"}
    section = app.mostwanted_section
    assert section.status_var.get() == "GDXF-Liste nicht abrufbar"
    assert section.status_label.cget("style") == "Danger.TLabel"


def test_mostwanted_failed_refresh_keeps_the_old_list(app, tmp_path):
    _load(app, tmp_path, log=MW_ADIF)
    old = _mw_ranking(datetime.now(UTC) - timedelta(days=90))
    _enable_mostwanted(app, mostwanted.RefreshResult(old, error="offline"))

    assert {c for c, r in _row_map(app).items() if r["print"] == "Ja"} == {"P5AA", "JA1AA"}
    assert "Abruf fehlgeschlagen" in app.mostwanted_section.status_var.get()
    assert "GDXF 2025" in app.mostwanted_section.status_var.get()


def test_mostwanted_settings_do_not_refetch_after_a_failure(app, tmp_path):
    """Nach einem gescheiterten Abruf bleibt die Liste „veraltet". Dann darf
    nicht jeder Tastendruck im Top-Feld erneut ins Netz gehen — nur das
    erneute Einschalten versucht es noch einmal."""
    failed = mostwanted.RefreshResult(None, error="offline")
    refresh = _enable_mostwanted(app, failed)
    with (
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
        mock.patch.object(appmod.mostwanted, "refresh", return_value=failed) as again,
    ):
        app.mostwanted_section.top.set("5")
        app.mostwanted_section.top.set("50")
        app.mostwanted_section.set_category("cw")
        again.assert_not_called()
        app.mostwanted_section.enabled.set(False)
        app.mostwanted_section.enabled.set(True)
        again.assert_called_once()
    refresh.assert_called_once()


def test_generate_waits_for_the_mostwanted_list(app, tmp_path):
    _load(app, tmp_path, log=MW_ADIF)
    app._mostwanted_running = True
    app._update_generate_state()
    assert str(app.output_section.generate_btn.cget("state")) == "disabled"
    with (
        mock.patch.object(appmod, "messagebox") as box,
        mock.patch.object(appmod, "generate") as gen,
    ):
        app._on_generate()
    box.showinfo.assert_called_once()
    gen.assert_not_called()


def test_mostwanted_settings_are_saved(app):
    section = app.mostwanted_section
    with (
        mock.patch.object(appmod.mostwanted, "refresh"),
        mock.patch.object(appmod.threading, "Thread", _SyncThread),
    ):
        section.enabled.set(True)
    section.top.set("25")
    section.set_category("cw")
    saved = app._gather_config().mostwanted
    assert (saved.enabled, saved.top, saved.category) == (True, 25, "cw")

    # Unsinn im Feld landet nie in der Config.
    section.top.set("")
    assert app._gather_config().mostwanted.top == mostwanted.DEFAULT_TOP


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))


# -- Beschädigte config.yaml (Bewertung 1.2) --------------------------------


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.setattr(appmod, "EXAMPLE_CONFIG_PATH", str(tmp_path / "missing.yaml"))
    monkeypatch.setattr(appmod, "MOSTWANTED_PATH", str(tmp_path / "mostwanted.json"))
    monkeypatch.setattr(appmod, "CTY_PATH", str(tmp_path / "cty.dat"))
    monkeypatch.setattr(appmod, "WAVELOG_SENT_PATH", str(tmp_path / "wavelog_sent.json"))
    monkeypatch.setattr(
        appmod.dxcc,
        "refresh",
        lambda stored, bundled, numbers, **_kw: appmod.dxcc.CtyRefreshResult(
            appmod.dxcc.load(stored, bundled, numbers)
        ),
    )
    try:
        return appmod.App()
    except tk.TclError as exc:
        pytest.skip(f"kein Tk-Display: {exc}")


def test_start_with_half_written_config_uses_backup(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    good = cfg.AppConfig()
    good.sender.callsign = "DL1ABC"
    cfg.save(good, path)
    cfg.save(good, path)  # legt config.yaml.bak an
    path.write_text("sender:\n  callsign: DL1A", encoding="utf-8")
    path.write_text("sender: [kaputt\n", encoding="utf-8")
    shown: list[str] = []
    monkeypatch.setattr(appmod.messagebox, "showwarning", lambda t, m, **k: shown.append(m))
    application = _make_app(tmp_path, monkeypatch)
    try:
        application.update()
        assert application.sender_section.vars["callsign"].get() == "DL1ABC"
        assert shown and "Sicherung" in shown[0]
        # Die Datei ist sofort wieder gültig und trägt die geretteten Werte.
        assert cfg.load(path).sender.callsign == "DL1ABC"
        assert (tmp_path / "config.yaml.defekt").exists()
    finally:
        application.destroy()


def test_external_broken_write_keeps_current_values(app):
    app.sender_section.vars["callsign"].set("DL1ABC")
    app._write_config()
    Path(appmod.CONFIG_PATH).write_text("", encoding="utf-8")
    app._reload_from_file()  # darf nicht werfen
    assert app.sender_section.vars["callsign"].get() == "DL1ABC"
    assert app._last_mtime == app._config_mtime()


def test_lookup_credentials_only_in_keyring_when_asked(app, monkeypatch):
    """Bewertung 2.3: Haken setzt Schlüsselbund, config.yaml bleibt frei."""
    from qslcards.lookup import secret as lookup_secret

    store: dict = {}

    class _Fake:
        def get_password(self, service, name):
            return store.get((service, name))

        def set_password(self, service, name, value):
            store[(service, name)] = value

        def delete_password(self, service, name):
            store.pop((service, name), None)

    monkeypatch.setattr(lookup_secret, "_keyring", lambda: _Fake())
    app.lookup_section.qrz_user.set("dl1abc")
    app.lookup_section.qrz_pass.set("geheim")
    app._on_step_leave(appmod.STEP_LOOKUP)
    assert store == {}  # ohne Haken: nirgends gespeichert
    app.lookup_section.remember.set(True)
    assert lookup_secret.load("qrz") == ("dl1abc", "geheim")
    app._write_config()
    text = Path(appmod.CONFIG_PATH).read_text(encoding="utf-8")
    assert "geheim" not in text and "dl1abc" not in text
    assert "remember: true" in text
    # Neustart: Felder kommen aus dem Schlüsselbund.
    app.lookup_section.qrz_user.set("")
    app.lookup_section.qrz_pass.set("")
    app._restore_lookup_credentials()
    assert app.lookup_section.qrz_pass.get() == "geheim"
    app.lookup_section.remember.set(False)
    assert store == {}
