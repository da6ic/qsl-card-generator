"""Smoke-Tests für pdf.generator.generate (SPECIFICATION.md §7)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from qslcards.cards.models import Card, CardRow
from qslcards.config import AppConfig, LookupConfig
from qslcards.lookup.base import LookupResult
from qslcards.pdf.generator import generate


def _front_image(tmp_path: Path) -> Path:
    path = tmp_path / "front.png"
    Image.new("RGB", (120, 90), (180, 200, 220)).save(path)
    return path


def _dummy_cards(n: int, via: str = "B", with_address: bool = False) -> list[Card]:
    cards = []
    for i in range(1, n + 1):
        recipient = None
        if with_address:
            recipient = LookupResult(
                call=f"DL{i}AA",
                name=f"Name {i}",
                street="Musterweg 1",
                city="Stadt",
                source="hamqth",
            )
        cards.append(
            Card(
                recipient_call=f"DL{i}AA",
                via_text="",
                via_code=via,
                rows=[CardRow("19", "07", "26", "14:38", "14.230", "SSB", "59")],
                recipient=recipient,
            )
        )
    return cards


def test_generate_two_pages_per_card(tmp_path: Path):
    cards = _dummy_cards(3)
    out = tmp_path / "cards.pdf"
    generate(cards, AppConfig(), str(_front_image(tmp_path)), str(out))

    assert out.exists()
    reader = PdfReader(str(out))
    assert len(reader.pages) == 6  # 3 Karten * 2 Seiten


def test_card_with_remarks_over_limit_is_split(tmp_path: Path):
    # 6 QSO-Zeilen + Remarks passen nicht auf eine Karte -> Aufteilung in zwei
    # Karten (je 3 Zeilen) -> 2 * 2 = 4 Seiten. Der Grenzfall darf nicht in die
    # PDF gelangen (Sicherung pro Karte im Generator).
    rows = [CardRow("19", "07", "26", "14:38", "14.230", "SSB", "59") for _ in range(6)]
    card = Card(recipient_call="DL1AA", via_text="", via_code="B", rows=rows, remarks="TNX QSO")
    out = tmp_path / "split.pdf"
    generate([card], AppConfig(), str(_front_image(tmp_path)), str(out))
    assert len(PdfReader(str(out)).pages) == 4


def test_progress_callback_called_per_card(tmp_path: Path):
    cards = _dummy_cards(3)
    out = tmp_path / "cards.pdf"
    calls: list[tuple[int, int]] = []
    generate(
        cards,
        AppConfig(),
        str(_front_image(tmp_path)),
        str(out),
        progress_cb=lambda done, total: calls.append((done, total)),
    )
    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_empty_cards_produces_empty_pdf(tmp_path: Path):
    out = tmp_path / "empty.pdf"
    generate([], AppConfig(), str(_front_image(tmp_path)), str(out))
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 0


def test_address_export_only_when_enabled(tmp_path: Path):
    img = _front_image(tmp_path)
    cards = _dummy_cards(2, with_address=True)

    # Aus: keine CSV.
    out_off = tmp_path / "off.pdf"
    generate(cards, AppConfig(), str(img), str(out_off))
    assert not (tmp_path / "off_addresses.csv").exists()

    # An: CSV mit allen Stationen, die eine Adresse haben.
    out_on = tmp_path / "on.pdf"
    cfg = AppConfig(lookup=LookupConfig(address_export=True))
    generate(cards, cfg, str(img), str(out_on))
    csv_path = tmp_path / "on_addresses.csv"
    assert csv_path.exists()
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("call,")
    assert len(lines) == 1 + len(cards)  # Header + 2 Stationen


def test_address_export_covers_all_vias(tmp_path: Path):
    # Nicht mehr nur via=D: auch Büro-Stationen mit Adresse werden exportiert.
    img = _front_image(tmp_path)
    cards = _dummy_cards(2, via="B", with_address=True)
    cfg = AppConfig(lookup=LookupConfig(address_export=True))
    out = tmp_path / "cards.pdf"
    generate(cards, cfg, str(img), str(out))
    lines = (tmp_path / "cards_addresses.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 + 2  # Header + beide Büro-Stationen


def test_address_export_skips_stations_without_address(tmp_path: Path):
    img = _front_image(tmp_path)
    cards = _dummy_cards(2, via="D", with_address=False)  # kein Lookup-Treffer
    cfg = AppConfig(lookup=LookupConfig(address_export=True))
    out = tmp_path / "cards.pdf"
    generate(cards, cfg, str(img), str(out))
    lines = (tmp_path / "cards_addresses.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # nur Header, keine Adressdaten


def test_address_export_dedupes_by_call(tmp_path: Path):
    img = _front_image(tmp_path)
    # Zwei Karten mit demselben Call (per_qso, mehrfach gearbeitet) → eine Zeile.
    cards = _dummy_cards(1, with_address=True) + _dummy_cards(1, with_address=True)
    cfg = AppConfig(lookup=LookupConfig(address_export=True))
    out = tmp_path / "cards.pdf"
    generate(cards, cfg, str(img), str(out))
    lines = (tmp_path / "cards_addresses.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 + 1  # Header + eine eindeutige Station
