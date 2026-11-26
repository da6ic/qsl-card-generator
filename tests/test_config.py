"""Tests für qslcards.config: Laden der Beispiel-Config, Defaults, Round-Trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from qslcards import config as cfg

EXAMPLE = Path(__file__).resolve().parent.parent / "config.example.yaml"


def test_load_example_all_fields():
    c = cfg.load(EXAMPLE)

    # Sender: die Vorlage ist leer — die Angaben trägt der Anwender im Programm
    # ein (Abschnitt 3), nicht in der Datei.
    assert c.sender.callsign == ""
    assert c.sender.name == ""
    assert c.sender.street == ""
    assert c.sender.zip == ""
    assert c.sender.city == ""
    assert c.sender.country == ""
    assert c.sender.locator == ""
    assert c.sender.dok == ""
    assert c.sender.waz == ""
    assert c.sender.itu == ""

    # Lookup
    assert c.lookup.program_id == "qslcards"
    assert c.lookup.address_export is False
    assert not hasattr(c.lookup, "lookup_addresses")
    # Zugangsdaten gehören nicht in die Config (siehe LookupCredentials).
    for field in ("hamqth_user", "hamqth_pass", "qrz_user", "qrz_pass"):
        assert not hasattr(c.lookup, field)

    # Generation
    assert c.generation.card_mode == "per_qso"
    assert c.generation.via_priority == ["B", "D", "Q", "L"]
    assert c.generation.via_cut == 2
    assert not hasattr(c.generation, "via_filter")
    assert not hasattr(c.generation, "include_missing_via")
    assert c.generation.default_via == "B"
    assert c.generation.page_orientation == "landscape"
    assert c.generation.print_mode == "duplex"
    # Bogendruck: standardmäßig eine Karte je Seite (A6).
    assert c.generation.sheet_mode == "single"
    # Druckrand: standardmäßig aus, alle vier Kanten 0 -> Ausgabe wie ohne.
    assert c.generation.print_margin_enabled is False
    assert c.generation.print_margin_top == 0.0
    assert c.generation.print_margin_bottom == 0.0
    assert c.generation.print_margin_left == 0.0
    assert c.generation.print_margin_right == 0.0
    assert c.generation.static_footer == "TNX FR NICE CONTACT, 73"
    assert c.generation.qsl_mark == "none"
    assert c.generation.confirm_mark == "none"

    # Most-Wanted-Filter: aus, Top 100, Rangliste nach dem Mode des QSOs.
    assert c.mostwanted.enabled is False
    assert c.mostwanted.top == 100
    assert c.mostwanted.category == "auto"


def test_mostwanted_roundtrip_and_old_config_without_it(tmp_path: Path):
    path = tmp_path / "c.yaml"
    # Eine config.yaml von vor dem Filter: gilt weiter, mit den Defaults.
    path.write_text("sender:\n  callsign: DL0MT\n", encoding="utf-8")
    assert cfg.load(path).mostwanted == cfg.MostWantedConfig()

    config = cfg.AppConfig()
    config.mostwanted = cfg.MostWantedConfig(enabled=True, top=25, category="cw")
    cfg.save(config, path)
    assert cfg.load(path).mostwanted == cfg.MostWantedConfig(enabled=True, top=25, category="cw")


def test_save_load_roundtrip(tmp_path: Path):
    original = cfg.load(EXAMPLE)
    out = tmp_path / "config.yaml"
    cfg.save(original, out)
    reloaded = cfg.load(out)
    assert reloaded == original


def test_missing_fields_use_defaults(tmp_path: Path):
    partial = tmp_path / "partial.yaml"
    partial.write_text(
        "sender:\n  callsign: XX1YY\ngeneration:\n  card_mode: per_station\n",
        encoding="utf-8",
    )
    c = cfg.load(partial)

    # gesetztes Feld
    assert c.sender.callsign == "XX1YY"
    assert c.generation.card_mode == "per_station"
    # fehlende Felder -> Defaults
    assert c.sender.name == ""
    assert c.generation.via_priority == ["B", "D", "Q", "L"]
    assert c.generation.via_cut == 2
    assert c.lookup.program_id == "qslcards"


def test_sheet_mode_defaults_and_roundtrip(tmp_path: Path):
    # Default: eine Karte je Seite; alte config.yaml ohne das Feld bleibt gültig.
    assert cfg.AppConfig().generation.sheet_mode == "single"

    path = tmp_path / "c.yaml"
    path.write_text("generation:\n  sheet_mode: a4_4up\n", encoding="utf-8")
    assert cfg.load(path).generation.sheet_mode == "a4_4up"

    c = cfg.AppConfig()
    c.generation.sheet_mode = "a4_4up"
    cfg.save(c, path)
    assert cfg.load(path).generation.sheet_mode == "a4_4up"


def test_unknown_fields_ignored(tmp_path: Path):
    weird = tmp_path / "weird.yaml"
    weird.write_text(
        "sender:\n  callsign: ZZ9ZZ\n  bogus_field: ignore_me\nunknown_section: 42\n",
        encoding="utf-8",
    )
    c = cfg.load(weird)
    assert c.sender.callsign == "ZZ9ZZ"
    assert not hasattr(c.sender, "bogus_field")


def test_empty_file_is_an_error_not_defaults(tmp_path: Path):
    """Eine leere Datei ist abgebrochen geschrieben (Bewertung 1.2).

    Früher wurde sie still als „alles Standard" gelesen — und der nächste
    Auto-Save hätte die Absenderdaten endgültig gelöscht.
    """
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(cfg.ConfigError):
        cfg.load(empty)
    header_only = tmp_path / "header.yaml"
    header_only.write_text(cfg.CONFIG_HEADER, encoding="utf-8")
    with pytest.raises(cfg.ConfigError):
        cfg.load(header_only)


def _saved_config(tmp_path: Path, callsign: str) -> Path:
    c = cfg.AppConfig()
    c.sender.callsign = callsign
    path = tmp_path / "config.yaml"
    cfg.save(c, path)
    return path


def test_half_written_yaml_raises_config_error(tmp_path: Path):
    path = _saved_config(tmp_path, "DL1ABC")
    text = path.read_text(encoding="utf-8")
    path.write_text(text[: len(text) // 3] + '\n  name: "unterbro', encoding="utf-8")
    with pytest.raises(cfg.ConfigError):
        cfg.load(path)
    # Bestehender Code fängt `ValueError` — das muss weiter greifen.
    assert issubclass(cfg.ConfigError, ValueError)


def test_save_keeps_previous_version_as_backup(tmp_path: Path):
    path = _saved_config(tmp_path, "DL1ABC")
    assert not cfg.backup_path(path).exists()  # erste Fassung: nichts zu sichern
    c = cfg.load(path)
    c.sender.callsign = "DL2XYZ"
    cfg.save(c, path)
    assert cfg.load(cfg.backup_path(path)).sender.callsign == "DL1ABC"
    assert cfg.load(path).sender.callsign == "DL2XYZ"


def test_broken_file_never_overwrites_good_backup(tmp_path: Path):
    path = _saved_config(tmp_path, "DL1ABC")
    cfg.save(cfg.load(path), path)  # .bak = DL1ABC
    path.write_text("", encoding="utf-8")  # Absturz beim Schreiben
    cfg.save(cfg.AppConfig(), path)
    assert cfg.load(cfg.backup_path(path)).sender.callsign == "DL1ABC"


@pytest.mark.parametrize("damage", ["", "sender: [kaputt\n", "nur ein text"])
def test_load_safely_falls_back_to_backup(tmp_path: Path, damage: str):
    path = _saved_config(tmp_path, "DL1ABC")
    cfg.save(cfg.load(path), path)
    path.write_text(damage, encoding="utf-8")
    result = cfg.load_safely(path)
    assert result.from_backup
    assert result.config.sender.callsign == "DL1ABC"
    assert result.problem and "Sicherung" in result.problem
    assert cfg.damaged_path(path).read_text(encoding="utf-8") == damage


def test_load_safely_without_backup_starts_with_defaults(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("sender: [kaputt\n", encoding="utf-8")
    result = cfg.load_safely(path)
    assert result.config == cfg.AppConfig()
    assert not result.from_backup
    assert result.problem and "keine" in result.problem


def test_load_safely_missing_file_uses_fallback_silently(tmp_path: Path):
    example = tmp_path / "example.yaml"
    c = cfg.AppConfig()
    c.sender.callsign = "EX4MPL"
    cfg.save(c, example)
    result = cfg.load_safely(tmp_path / "config.yaml", example)
    assert result.problem is None
    assert result.config.sender.callsign == "EX4MPL"


def test_atomic_write_keeps_old_file_on_failure(tmp_path: Path, monkeypatch):
    path = _saved_config(tmp_path, "DL1ABC")
    before = path.read_text(encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("Platte voll")

    monkeypatch.setattr(cfg.os, "replace", boom)
    with pytest.raises(OSError):
        cfg.save(cfg.AppConfig(), path)
    assert path.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("*.tmp"))


# -- Aussehen + „Zuletzt verwendet" ----------------------------------------


def test_appearance_defaults_and_roundtrip(tmp_path: Path):
    assert cfg.AppConfig().appearance.theme == "system"

    path = tmp_path / "c.yaml"
    config = cfg.AppConfig()
    config.appearance = cfg.AppearanceConfig(theme="dark")
    cfg.save(config, path)
    assert cfg.load(path).appearance.theme == "dark"


def test_recent_roundtrip_and_defensive_load(tmp_path: Path):
    path = tmp_path / "c.yaml"
    config = cfg.AppConfig()
    config.recent = cfg.RecentConfig(logs=["/a.adi"], images=["/b.png"])
    cfg.save(config, path)
    loaded = cfg.load(path)
    assert loaded.recent.logs == ["/a.adi"]
    assert loaded.recent.images == ["/b.png"]

    # Von Hand kaputt editiert: leere/nicht-String-Einträge fliegen raus.
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "recent:\n  logs: ['/ok.adi', '', 42, '  ']\n  images: 'kein_list'\n", encoding="utf-8"
    )
    loaded = cfg.load(broken)
    assert loaded.recent.logs == ["/ok.adi"]
    assert loaded.recent.images == []


def test_recent_is_capped(tmp_path: Path):
    path = tmp_path / "many.yaml"
    entries = "\n".join(f"    - /log{i}.adi" for i in range(cfg.MAX_RECENT + 5))
    path.write_text(f"recent:\n  logs:\n{entries}\n", encoding="utf-8")
    assert len(cfg.load(path).recent.logs) == cfg.MAX_RECENT


def test_push_recent_moves_to_front_without_duplicates():
    entries = ["/a", "/b", "/c"]
    assert cfg.push_recent(entries, "/c") == ["/c", "/a", "/b"]
    assert cfg.push_recent(entries, "/neu") == ["/neu", "/a", "/b", "/c"]
    assert cfg.push_recent(entries, "  ") == entries  # leer -> unverändert
    assert cfg.push_recent(entries, "/a") is not entries  # Original bleibt heil


def test_push_recent_respects_limit():
    entries = [f"/log{i}" for i in range(cfg.MAX_RECENT)]
    pushed = cfg.push_recent(entries, "/neu")
    assert len(pushed) == cfg.MAX_RECENT
    assert pushed[0] == "/neu" and entries[-1] not in pushed


# -- Die Vorlage ist genau das, was das Programm schreibt -------------------


def test_example_is_exactly_what_the_program_writes(tmp_path: Path):
    """`config.example.yaml` == `save(AppConfig())`, Byte für Byte.

    Damit kann die Vorlage nicht von den Defaults wegdriften: kommt ein Feld
    dazu oder ändert sich ein Standardwert, fällt dieser Test um, statt dass ein
    Anwender eine Vorlage bekommt, die nicht mehr zum Programm passt.
    """
    written = tmp_path / "config.yaml"
    cfg.save(cfg.AppConfig(), written)
    assert written.read_text(encoding="utf-8") == EXAMPLE.read_text(encoding="utf-8")


def test_saved_config_warns_against_editing_by_hand(tmp_path: Path):
    """Die Warnung steht in `save`, nicht nur in der Vorlage.

    `yaml.safe_dump` schreibt die Datei beim Auto-Save komplett neu — ein nur in
    der Vorlage stehender Hinweis wäre nach der ersten Änderung im Programm weg.
    """
    path = tmp_path / "config.yaml"
    config = cfg.AppConfig()
    config.sender.callsign = "DL1ABC"
    cfg.save(config, path)

    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == cfg.CONFIG_HEADER.rstrip("\n")
    assert "nicht von Hand bearbeiten" in text
    # Der Kommentar stört das Wiedereinlesen nicht.
    assert cfg.load(path).sender.callsign == "DL1ABC"


def test_example_contains_no_personal_sample_data():
    """Die Vorlage ist leer, nicht mit erfundenen Absenderdaten gefüllt."""
    c = cfg.load(EXAMPLE)
    assert c.sender == cfg.SenderConfig()


# -- Zugangsdaten stehen nie in der Datei -----------------------------------


def test_credentials_are_never_written(tmp_path: Path):
    """Die geschriebene Config enthält keinen der vier Zugangsdaten-Schlüssel.

    Sie standen dort einmal im Klartext. Jetzt leben sie nur zur Laufzeit in
    `LookupCredentials`; der Nutzer gibt sie in jeder Sitzung neu ein.
    """
    path = tmp_path / "config.yaml"
    cfg.save(cfg.AppConfig(), path)

    text = path.read_text(encoding="utf-8")
    for key in ("hamqth_user", "hamqth_pass", "qrz_user", "qrz_pass"):
        assert key not in text


def test_old_config_with_credentials_still_loads(tmp_path: Path):
    """Eine Datei aus der Zeit davor lädt ohne Fehler; die Felder verfallen.

    Kein Migrationscode — dasselbe Muster wie beim entfernten `portable_mark`:
    `_from_dict` ignoriert unbekannte Schlüssel, der nächste Auto-Save schreibt
    die Datei ohne sie neu.
    """
    path = tmp_path / "config.yaml"
    path.write_text(
        "lookup:\n"
        "  hamqth_user: dl1abc\n"
        "  hamqth_pass: geheim\n"
        "  qrz_user: dl1abc\n"
        "  qrz_pass: geheim\n"
        "  program_id: qslcards\n"
        "  address_export: true\n",
        encoding="utf-8",
    )

    c = cfg.load(path)
    assert c.lookup.address_export is True
    assert not hasattr(c.lookup, "hamqth_user")

    cfg.save(c, path)
    assert "geheim" not in path.read_text(encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
