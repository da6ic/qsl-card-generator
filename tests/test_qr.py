"""DARC-QR-Code auf der Rückseite (generation.qr_code, cards/qr.py)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from qslcards import config as cfg
from qslcards.cards.builder import build_cards, max_rows_for_remarks, regroup_card_by_remarks
from qslcards.cards.models import Card, CardRow
from qslcards.cards.qr import band_of, qr_text
from qslcards.config import AppConfig, GenerationConfig, SenderConfig
from qslcards.logbook import QSO
from qslcards.pdf import geometry as g
from qslcards.pdf import layout_back
from qslcards.pdf.generator import generate


def _card(rows: int = 2, via: str = "DL9MGR", qsl_mark: str = "pse", qr: bool = True) -> Card:
    samples = [
        CardRow("18", "10", "26", "14:05", "14.230", "SSB", "59"),
        CardRow("19", "10", "26", "09:12", "7.025", "CW", "599"),
        CardRow("20", "10", "26", "18:30", "3.573", "FT8", "-12"),
        CardRow("21", "10", "26", "10:00", "144.300", "SSB", "57"),
    ]
    return Card(
        recipient_call="DK2XYZ",
        via_text=via,
        via_routes=("B",),
        rows=samples[:rows],
        qsl_mark=qsl_mark,
        qr_code=qr,
    )


def _qsos(n: int) -> list[QSO]:
    return [
        QSO(
            call="DK2XYZ",
            qso_date="20261018",
            time_on=f"{10 + i:02d}0000",
            freq="14.230",
            mode="SSB",
            rst_sent="59",
        )
        for i in range(n)
    ]


@pytest.mark.parametrize(
    ("freq", "band"),
    [
        ("14.230", "20m"),
        ("7,025", "40m"),
        ("3.573", "80m"),
        ("144.300", "2m"),
        ("432.1", "70cm"),
        ("12.0", ""),
        ("", ""),
        (None, ""),
        ("abc", ""),
    ],
)
def test_band_of(freq, band):
    assert band_of(freq) == band


def test_qr_text_format():
    assert qr_text(_card(), "dl1abc") == (
        "From: DL1ABC Via: DL9MGR To: DK2XYZ\n"
        "Date: 18.10.26 Time: 14:05 Band: 20m Mode: SSB RST: 59 QSL: PSE\n"
        "Date: 19.10.26 Time: 09:12 Band: 40m Mode: CW RST: 599 QSL: PSE"
    )


def test_qr_text_without_manager_and_mark():
    text = qr_text(_card(rows=1, via="", qsl_mark="none"), "DL1ABC")
    assert text.splitlines()[0] == "From: DL1ABC To: DK2XYZ"
    assert text.endswith("QSL: -|-")


def test_qr_text_tnx():
    assert qr_text(_card(rows=1, qsl_mark="tnx"), "DL1ABC").endswith("QSL: TNX")


def test_qr_code_limits_rows_like_remarks():
    assert max_rows_for_remarks("", qr_code=True) == g.MAX_ROWS_WITH_REMARKS
    assert max_rows_for_remarks("") == g.MAX_ROWS_PLAIN


def test_build_cards_with_qr_splits_after_three_rows():
    config = AppConfig(generation=GenerationConfig(card_mode="per_station", qr_code=True))
    cards = build_cards(_qsos(5), config)
    assert [len(c.rows) for c in cards] == [3, 2]
    assert all(c.qr_code for c in cards)


def test_build_cards_without_qr_keeps_six_rows():
    config = AppConfig(generation=GenerationConfig(card_mode="per_station"))
    cards = build_cards(_qsos(5), config)
    assert [len(c.rows) for c in cards] == [5]
    assert not cards[0].qr_code


def test_regroup_respects_qr_flag():
    card = _card(rows=4)
    assert [len(c.rows) for c in regroup_card_by_remarks(card)] == [3, 1]


def test_config_default_and_roundtrip(tmp_path: Path):
    assert AppConfig().generation.qr_code is False
    path = tmp_path / "config.yaml"
    config = AppConfig()
    config.generation.qr_code = True
    cfg.save(config, path)
    assert cfg.load(path).generation.qr_code is True


def test_qr_is_drawn_only_when_enabled(tmp_path: Path, monkeypatch):
    calls = []
    monkeypatch.setattr(layout_back, "_draw_qr", lambda *a: calls.append(a))
    config = AppConfig(sender=SenderConfig(callsign="DL1ABC"))
    c = Canvas(str(tmp_path / "x.pdf"), pagesize=(g.PAGE_W, g.PAGE_H))
    layout_back.draw_back(c, _card(qr=False), config)
    assert calls == []
    layout_back.draw_back(c, _card(qr=True), config)
    assert len(calls) == 1


def test_generate_with_qr_code(tmp_path: Path):
    image = tmp_path / "front.png"
    Image.new("RGB", (120, 90), (180, 200, 220)).save(image)
    out = tmp_path / "karten.pdf"
    config = AppConfig(
        sender=SenderConfig(callsign="DL1ABC"),
        generation=GenerationConfig(qr_code=True, remarks="TNX QSO 73"),
    )
    generate([_card(rows=4, qr=True)], config, str(image), str(out))
    # vier Zeilen -> zwei Karten (3 + 1) -> vier Seiten im Duplex
    assert len(PdfReader(str(out)).pages) == 4
