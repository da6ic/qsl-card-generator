"""Smoke-Tests für pdf.generator.generate (SPECIFICATION.md §7)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from qslcards.cards.models import Card, CardRow
from qslcards.config import AppConfig, GenerationConfig, LookupConfig
from qslcards.lookup.base import LookupResult
from qslcards.pdf import geometry as g
from qslcards.pdf.generator import generate
from qslcards.pdf.geometry import PAGE_H, PAGE_W


def _front_image(tmp_path: Path) -> Path:
    path = tmp_path / "front.png"
    Image.new("RGB", (120, 90), (180, 200, 220)).save(path)
    return path


def _dummy_cards(
    n: int, routes: tuple[str, ...] = ("B",), with_address: bool = False
) -> list[Card]:
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
                via_routes=routes,
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
    card = Card(
        recipient_call="DL1AA", via_text="", via_routes=("B",), rows=rows, remarks="TNX QSO"
    )
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


# --- Druckmodus „separate" ------------------------------------------------


def test_separate_mode_writes_two_pdfs(tmp_path: Path):
    cards = _dummy_cards(3)
    out = tmp_path / "cards.pdf"
    outputs = generate(
        cards,
        AppConfig(generation=GenerationConfig(print_mode="separate")),
        str(_front_image(tmp_path)),
        str(out),
    )

    front, back = outputs
    assert front.name == "cards_vorderseiten.pdf"
    assert back.name == "cards_rueckseiten.pdf"
    assert not out.exists()  # im getrennten Modus gibt es keine Sammel-PDF
    assert len(PdfReader(str(front)).pages) == 3  # je Karte eine Vorderseite
    assert len(PdfReader(str(back)).pages) == 3  # je Karte eine Rückseite


def test_separate_mode_progress_covers_both_runs(tmp_path: Path):
    cards = _dummy_cards(2)
    calls: list[tuple[int, int]] = []
    generate(
        cards,
        AppConfig(generation=GenerationConfig(print_mode="separate")),
        str(_front_image(tmp_path)),
        str(tmp_path / "cards.pdf"),
        progress_cb=lambda done, total: calls.append((done, total)),
    )
    # Erst alle Vorderseiten, dann alle Rückseiten -> total = 2 x Kartenzahl.
    assert calls == [(1, 4), (2, 4), (3, 4), (4, 4)]


# --- Druckrand ------------------------------------------------------------


def _margin_config(**kwargs) -> AppConfig:
    return AppConfig(generation=GenerationConfig(print_margin_enabled=True, **kwargs))


def test_print_margin_keeps_page_size_and_count(tmp_path: Path):
    """Der Druckrand verkleinert den Inhalt, nicht das Blatt: die PDF-Seiten
    bleiben A6, nur die Zeichnung rückt ein."""
    cards = _dummy_cards(2)
    out = tmp_path / "cards.pdf"
    generate(
        cards,
        _margin_config(
            print_margin_top=3,
            print_margin_bottom=8,
            print_margin_left=3,
            print_margin_right=3,
        ),
        str(_front_image(tmp_path)),
        str(out),
    )

    reader = PdfReader(str(out))
    assert len(reader.pages) == 4
    for page in reader.pages:
        assert float(page.mediabox.width) == pytest.approx(PAGE_W)
        assert float(page.mediabox.height) == pytest.approx(PAGE_H)


def test_print_margin_scales_the_back(tmp_path: Path):
    """Die Rückseite wird über *eine* Transformation eingerückt: im
    Content-Stream steht genau der Faktor aus geometry.page_layout."""
    cfg = _margin_config(
        print_margin_top=3, print_margin_bottom=8, print_margin_left=3, print_margin_right=3
    )
    out = tmp_path / "cards.pdf"
    generate(_dummy_cards(1), cfg, str(_front_image(tmp_path)), str(out))

    page = g.page_layout(cfg)
    back = PdfReader(str(out)).pages[1].get_contents().get_data().decode("latin-1")

    # Die Transformation der Rückseite aus dem Content-Stream ziehen (ReportLab
    # kürzt Zahlen, deshalb numerisch statt als Text vergleichen).
    matrices = re.findall(r"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) cm", back)
    sx, b, c, sy, dx, dy = (float(v) for v in matrices[-1])
    assert (b, c) == (0.0, 0.0)  # keine Scherung/Drehung
    assert sx == pytest.approx(sy)  # gleichmäßig -> keine Verzerrung
    assert sx == pytest.approx(page.scale, abs=1e-5)
    assert dx == pytest.approx(page.dx, abs=1e-4)
    assert dy == pytest.approx(page.dy, abs=1e-4)


def test_disabled_print_margin_draws_like_before(tmp_path: Path):
    """Ohne Druckrand muss die Ausgabe Byte für Byte die alte bleiben."""
    img = _front_image(tmp_path)
    plain = tmp_path / "plain.pdf"
    off = tmp_path / "off.pdf"
    # Werte gesetzt, Schalter aus -> dürfen keine Wirkung haben.
    cfg_off = AppConfig(
        generation=GenerationConfig(
            print_margin_enabled=False,
            print_margin_top=5,
            print_margin_left=5,
        )
    )
    generate(_dummy_cards(2), AppConfig(), str(img), str(plain))
    generate(_dummy_cards(2), cfg_off, str(img), str(off))

    reader_a, reader_b = PdfReader(str(plain)), PdfReader(str(off))
    for page_a, page_b in zip(reader_a.pages, reader_b.pages, strict=True):
        assert page_a.get_contents().get_data() == page_b.get_contents().get_data()


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
    # Nicht mehr nur Direkt: auch Büro-Stationen mit Adresse werden exportiert.
    img = _front_image(tmp_path)
    cards = _dummy_cards(2, routes=("B",), with_address=True)
    cfg = AppConfig(lookup=LookupConfig(address_export=True))
    out = tmp_path / "cards.pdf"
    generate(cards, cfg, str(img), str(out))
    lines = (tmp_path / "cards_addresses.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 + 2  # Header + beide Büro-Stationen


def test_address_export_skips_stations_without_address(tmp_path: Path):
    img = _front_image(tmp_path)
    cards = _dummy_cards(2, routes=("D",), with_address=False)  # kein Lookup-Treffer
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
