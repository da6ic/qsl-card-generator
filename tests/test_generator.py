"""Smoke-Tests für pdf.generator.generate (SPECIFICATION.md §7)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from qslcards.cards.models import Card, CardRow
from qslcards.config import AppConfig, GenerationConfig, LookupConfig
from qslcards.pdf.generator import generate


def _front_image(tmp_path: Path) -> Path:
    path = tmp_path / "front.png"
    Image.new("RGB", (120, 90), (180, 200, 220)).save(path)
    return path


def _dummy_cards(n: int, via: str = "B") -> list[Card]:
    return [
        Card(
            recipient_call=f"DL{i}AA",
            via_text="",
            via_code=via,
            rows=[CardRow("19", "07", "26", "14:38", "14.230", "SSB", "59")],
        )
        for i in range(1, n + 1)
    ]


def test_generate_two_pages_per_card(tmp_path: Path):
    cards = _dummy_cards(3)
    out = tmp_path / "cards.pdf"
    generate(cards, AppConfig(), str(_front_image(tmp_path)), str(out))

    assert out.exists()
    reader = PdfReader(str(out))
    assert len(reader.pages) == 6  # 3 Karten * 2 Seiten


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
    cards = _dummy_cards(2, via="D")

    # Aus: keine CSV.
    out_off = tmp_path / "off.pdf"
    generate(cards, AppConfig(), str(img), str(out_off))
    assert not (tmp_path / "off_addresses.csv").exists()

    # An: CSV mit Direkt-Karten (via=D).
    out_on = tmp_path / "on.pdf"
    cfg = AppConfig(lookup=LookupConfig(address_export=True))
    generate(cards, cfg, str(img), str(out_on))
    csv_path = tmp_path / "on_addresses.csv"
    assert csv_path.exists()
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("call,")
    assert len(lines) == 1 + len(cards)  # Header + 2 Direkt-Karten


def test_address_export_skips_non_direct(tmp_path: Path):
    img = _front_image(tmp_path)
    cards = _dummy_cards(2, via="B")  # keine Direkt-Karten
    cfg = AppConfig(lookup=LookupConfig(address_export=True), generation=GenerationConfig())
    out = tmp_path / "cards.pdf"
    generate(cards, cfg, str(img), str(out))
    csv_path = tmp_path / "cards_addresses.csv"
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # nur Header, keine via=D-Zeilen
