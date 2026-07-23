"""Tests für qslcards.config: Laden der Beispiel-Config, Defaults, Round-Trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from qslcards import config as cfg

EXAMPLE = Path(__file__).resolve().parent.parent / "config.example.yaml"


def test_load_example_all_fields():
    c = cfg.load(EXAMPLE)

    # Sender
    assert c.sender.callsign == "DN5MT"
    assert c.sender.name == "Axel Tüner"
    assert c.sender.street == "Wilhelmstr. 76"
    assert c.sender.zip == "72124"
    assert c.sender.city == "Pliezhausen"
    assert c.sender.country == "Deutschland"
    assert c.sender.locator == "JN48OM"
    assert c.sender.dok == "P31"
    assert c.sender.waz == "14"
    assert c.sender.itu == "28"

    # Lookup
    assert c.lookup.hamqth_user == ""
    assert c.lookup.hamqth_pass == ""
    assert c.lookup.qrz_user == ""
    assert c.lookup.qrz_pass == ""
    assert c.lookup.program_id == "qslcards"
    assert c.lookup.address_export is False
    assert not hasattr(c.lookup, "lookup_addresses")

    # Generation
    assert c.generation.card_mode == "per_qso"
    assert c.generation.via_filter == ["B", "D", "M"]
    assert not hasattr(c.generation, "include_missing_via")
    assert c.generation.default_via == "B"
    assert c.generation.page_orientation == "landscape"
    assert c.generation.static_footer == "TNX FR NICE CONTACT, 73"
    assert c.generation.qsl_mark == "none"
    assert c.generation.portable_mark == "none"


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
    assert c.generation.via_filter == ["B", "D", "M"]
    assert c.lookup.program_id == "qslcards"


def test_unknown_fields_ignored(tmp_path: Path):
    weird = tmp_path / "weird.yaml"
    weird.write_text(
        "sender:\n  callsign: ZZ9ZZ\n  bogus_field: ignore_me\nunknown_section: 42\n",
        encoding="utf-8",
    )
    c = cfg.load(weird)
    assert c.sender.callsign == "ZZ9ZZ"
    assert not hasattr(c.sender, "bogus_field")


def test_empty_file_uses_all_defaults(tmp_path: Path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    c = cfg.load(empty)
    assert c == cfg.AppConfig()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
