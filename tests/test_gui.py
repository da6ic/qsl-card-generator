"""Headless-GUI-Tests (macOS: Tk baut den Widget-Baum ohne sichtbares Fenster).

Kein Netz, kein echter Thread: `lookup_calls` wird gemockt und `threading.Thread`
durch eine synchrone Variante ersetzt, damit der Auto-Lookup deterministisch
im Test durchläuft. Braucht ein funktionierendes Tk — sonst wird übersprungen.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from unittest import mock

import pytest

from qslcards import config as cfg
from qslcards.gui import app as appmod
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
    try:
        application = appmod.App()
    except tk.TclError as exc:  # kein Display -> Test überspringen
        pytest.skip(f"kein Tk-Display: {exc}")
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


def _row_map(app):
    """recipient_call -> Zeilenwerte (Drucken, Call, #QSOs, Via, Route, …)."""
    out = {}
    for iid in app.preview.tree.get_children():
        vals = app.preview.tree.item(iid, "values")
        out[vals[1]] = vals
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
    assert rows["DL1AA"][3] == "Büro" and rows["DL1AA"][4] == "DK0XYZ"
    assert rows["DL2BB"][3] == "Büro"
    # Reine LoTW-Station: kein aktiver Weg -> nicht gedruckt, aber die Via-Spalte
    # zeigt trotzdem den natürlichen Weg (LOTW), nicht „—".
    assert rows["DL3CC"][3] == "LOTW"
    assert rows["DL3CC"][0] == "Nein"
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
    """Abschnitt 7 zeigt „geschrieben/erlaubt" und läuft beim Tippen mit."""
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
    """Abschnitt 9: die Randfelder erscheinen erst über „Erweiterte
    Einstellungen" und verschwinden wieder."""
    section = app.printmode_section
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
    """Der Platz des Randblocks ist immer reserviert: Abschnitt 9 behält seine
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
    """Abschnitt 9: die Checkbox trägt den Config-Wert direkt (on/off-value),
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
    app.update_idletasks()
    assert app.printmode_section.margin_vars["margin_bottom"].get() == "8"
    assert app.printmode_section.margin_frame.winfo_ismapped()


def test_menu_generate_entry_follows_button_state(app, tmp_path):
    app._lookup_running = True
    app._update_generate_state()
    assert str(app.output_section.generate_btn["state"]) == "disabled"
    app._lookup_running = False
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


def test_goto_section_scrolls(app, tmp_path):
    _load(app, tmp_path)
    app.update()
    app._goto_section(10)  # Ausgabe ganz unten
    app.update()
    assert app.body.canvas.yview()[0] > 0.0


def _help_marks(app) -> dict[int, tk.Misc]:
    """Das „?" jedes Abschnitts (letztes Kind seines Titel-Widgets)."""
    marks = {}
    for number, frame in app._sections.items():
        title = frame.nametowidget(str(frame.cget("labelwidget")))
        marks[number] = title.winfo_children()[-1]
    return marks


def test_every_section_has_a_help_mark(app):
    marks = _help_marks(app)
    assert sorted(marks) == list(range(1, 11))
    assert {mark.cget("text") for mark in marks.values()} == {"?"}
    # Der Titel selbst bleibt sichtbar (der Text ist ins Label gewandert).
    title = app.output_section.frame.nametowidget(str(app.output_section.frame.cget("labelwidget")))
    assert title.winfo_children()[0].cget("text") == "10. Ausgabe"


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
    assert str(star.cget("style")) == "Required.TLabel"  # gleiche Farbe wie an den Feldern
    assert "Pflichtfeld" in text.cget("text")
    assert app.required_legend.master is app  # nicht im Scrollbereich
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
