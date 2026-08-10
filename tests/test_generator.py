"""Smoke-Tests für pdf.generator.generate (SPECIFICATION.md §7)."""

from __future__ import annotations

import re
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from qslcards.cards.models import Card, CardRow
from qslcards.config import AppConfig, GenerationConfig, LookupConfig, SenderConfig
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


def test_front_image_is_passed_as_a_path(tmp_path: Path):
    """`drawImage` muss den **Dateipfad** bekommen, nie ein `ImageReader`.

    ReportLab schlüsselt ein `ImageReader`-Objekt über einen MD5 der komplett
    entpackten Bitmap — und zwar bei jedem Aufruf neu. Bei einem 4096×3072-Foto
    sind das 37,7 MB je Karte: gemessene 119 ms pro Seite statt 4,6 ms, bei
    einem Contest-Log mit dreitausend Karten fünf Minuten statt zwanzig
    Sekunden. Außerdem reicht ReportLab ein JPEG nur über den Pfad unverändert
    durch, statt es als rohes RGB neu zu komprimieren (Datei ~5× kleiner).

    Die Wirkung (ein Bild-XObject für alle Seiten) taugt **nicht** als Test:
    der Digest ist ja jedes Mal derselbe, das Bild landet auch mit
    `ImageReader` nur einmal im Dokument. Nachweisbar ist nur der Aufruf selbst.
    """
    img = _front_image(tmp_path)
    seen: list[object] = []
    real = Canvas.drawImage

    def spy(self, image, *args, **kwargs):
        seen.append(image)
        return real(self, image, *args, **kwargs)

    with mock.patch.object(Canvas, "drawImage", spy):
        generate(_dummy_cards(3), AppConfig(), str(img), str(tmp_path / "cards.pdf"))

    assert len(seen) == 3  # je Karte eine Vorderseite
    assert all(arg == str(img) for arg in seen), f"kein Pfad übergeben: {seen}"


def test_front_image_is_embedded_only_once(tmp_path: Path):
    """Egal wie viele Karten: das Frontbild steht **einmal** im Dokument."""
    img = _front_image(tmp_path)
    out = tmp_path / "many.pdf"
    generate(_dummy_cards(40), AppConfig(), str(img), str(out))

    images = {
        name
        for page in PdfReader(str(out)).pages
        for name, obj in page.get("/Resources", {}).get("/XObject", {}).items()
        if obj.get_object().get("/Subtype") == "/Image"
    }
    assert len(images) == 1


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


# --- Bogendruck: vier Karten auf einem A4-Bogen ---------------------------

# ReportLab schreibt setDash als "[strich lücke] phase d" — nur die
# Schnitt-Hilfslinien sind gestrichelt, daher taugt das als Nachweis.
DASH_RE = re.compile(r"\[[\d. ]+\] \d+ d")


def _sheet_config(**kwargs) -> AppConfig:
    return AppConfig(generation=GenerationConfig(sheet_mode=g.SHEET_MODE_A4_4UP, **kwargs))


def _content(page) -> str:
    return page.get_contents().get_data().decode("latin-1")


def test_sheet_mode_puts_four_cards_on_one_a4_page(tmp_path: Path):
    out = tmp_path / "cards.pdf"
    generate(_dummy_cards(8), _sheet_config(), str(_front_image(tmp_path)), str(out))

    reader = PdfReader(str(out))
    assert len(reader.pages) == 4  # 2 Bögen × (Vorder- + Rückseite)
    for page in reader.pages:
        assert float(page.mediabox.width) == pytest.approx(g.SHEET_W)
        assert float(page.mediabox.height) == pytest.approx(g.SHEET_H)


def test_sheet_mode_last_sheet_may_stay_partial(tmp_path: Path):
    """5 Karten -> ein voller Bogen + ein Bogen mit einer Karte (3 Zellen leer)."""
    out = tmp_path / "cards.pdf"
    generate(_dummy_cards(5), _sheet_config(), str(_front_image(tmp_path)), str(out))
    pages = PdfReader(str(out)).pages
    assert len(pages) == 4
    # Auch der angebrochene Bogen bekommt sein Schnittkreuz — sonst müsste man
    # den letzten Bogen anders schneiden als alle davor.
    assert DASH_RE.search(_content(pages[3]))


def test_sheet_cut_guides_only_on_the_backs(tmp_path: Path):
    """Mit dem Nutzer so entschieden: die Striche liegen auf der Rückseite (dort
    ist an der Schnittkante Weißraum), nicht über dem randlosen Frontbild."""
    out = tmp_path / "cards.pdf"
    generate(_dummy_cards(4), _sheet_config(), str(_front_image(tmp_path)), str(out))
    front, back = PdfReader(str(out)).pages[0], PdfReader(str(out)).pages[1]
    assert not DASH_RE.search(_content(front))
    assert DASH_RE.search(_content(back))


def test_sheet_mode_progress_counts_cards(tmp_path: Path):
    calls: list[tuple[int, int]] = []
    generate(
        _dummy_cards(6),
        _sheet_config(),
        str(_front_image(tmp_path)),
        str(tmp_path / "cards.pdf"),
        progress_cb=lambda done, total: calls.append((done, total)),
    )
    # Ein Aufruf je fertigem Bogen (4 + 2 Karten), gezählt wird in Karten.
    assert calls == [(4, 6), (6, 6)]


def test_sheet_mode_works_with_separate_print_mode(tmp_path: Path):
    outputs = generate(
        _dummy_cards(5),
        _sheet_config(print_mode="separate"),
        str(_front_image(tmp_path)),
        str(tmp_path / "cards.pdf"),
    )
    front, back = outputs
    assert len(PdfReader(str(front)).pages) == 2  # zwei Vorderseiten-Bögen
    assert len(PdfReader(str(back)).pages) == 2  # zwei Rückseiten-Bögen
    assert not DASH_RE.search(_content(PdfReader(str(front)).pages[0]))
    assert DASH_RE.search(_content(PdfReader(str(back)).pages[0]))


@pytest.mark.parametrize("margin", [5, 6, 12])
def test_sheet_margin_is_identical_on_all_four_edges_of_every_card(tmp_path: Path, margin):
    """Zwei Fehler, die nacheinander auffielen: erst stand horizontal mehr Rand
    als vertikal, dann hatte jede geschnittene Karte den Rand nur auf zwei
    Seiten. Beides prüft dieser Test am fertigen PDF."""
    cfg = _sheet_config(
        print_margin_enabled=True,
        print_margin_top=margin,
        print_margin_bottom=margin,
        print_margin_left=margin,
        print_margin_right=margin,
    )
    out = tmp_path / "cards.pdf"
    generate(_dummy_cards(4), cfg, str(_front_image(tmp_path)), str(out))

    layout = g.sheet_layout(cfg)
    page = g.page_layout(cfg)
    drawn_w, drawn_h = page.page_w * page.scale, page.page_h * page.scale
    for cell_x, cell_y in layout.cells:  # jede Karte einzeln, nicht nur der Bogen
        assert page.dx == pytest.approx(g.mm(margin))
        assert layout.cell_w - (page.dx + drawn_w) == pytest.approx(g.mm(margin))
        assert page.dy == pytest.approx(g.mm(margin))
        assert layout.cell_h - (page.dy + drawn_h) == pytest.approx(g.mm(margin))
        # … und die Karte bleibt innerhalb ihrer Zelle.
        assert cell_x + page.dx + drawn_w <= cell_x + layout.cell_w + 1e-9
        assert cell_y + page.dy + drawn_h <= cell_y + layout.cell_h + 1e-9

    back = _content(PdfReader(str(out)).pages[1])
    matrices = [
        [float(v) for v in m]
        for m in re.findall(r"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) cm", back)
    ]
    # Identitäten überspringen (ReportLab schreibt eine an den Seitenanfang).
    moves = [m for m in matrices if m != [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]]

    # Zuerst wird nur auf die Zelle verschoben (erste Zelle: oben links) …
    cell = moves[0]
    assert cell[:4] == [1.0, 0.0, 0.0, 1.0]
    assert cell[4] == pytest.approx(layout.cells[0][0], abs=1e-4)
    assert cell[5] == pytest.approx(layout.cells[0][1], abs=1e-4)

    # … dann rückt das gewohnte page_layout die Karte um den Rand ein.
    card = moves[1]
    assert card[0] == pytest.approx(page.scale, abs=1e-5)
    assert card[0] == pytest.approx(card[3])  # ein Faktor -> keine Verzerrung
    assert (card[1], card[2]) == (0.0, 0.0)  # keine Scherung/Drehung
    assert card[4] == pytest.approx(g.mm(margin), abs=1e-4)
    assert card[5] == pytest.approx(g.mm(margin), abs=1e-4)


def test_sheet_mode_off_leaves_output_untouched(tmp_path: Path):
    """Regressionsschutz: „single" ist byteweise die bisherige Ausgabe."""
    img = _front_image(tmp_path)
    plain = tmp_path / "plain.pdf"
    single = tmp_path / "single.pdf"
    generate(_dummy_cards(2), AppConfig(), str(img), str(plain))
    generate(
        _dummy_cards(2),
        AppConfig(generation=GenerationConfig(sheet_mode="single")),
        str(img),
        str(single),
    )
    for page_a, page_b in zip(
        PdfReader(str(plain)).pages, PdfReader(str(single)).pages, strict=True
    ):
        assert page_a.get_contents().get_data() == page_b.get_contents().get_data()


# --- Großbuchstaben-Felder des Absenders ----------------------------------


@pytest.mark.parametrize(
    "typed,printed",
    [
        ("dl2sct", "DL2SCT"),
        ("f/dl0mt/p", "F/DL0MT/P"),  # Gastrufzeichen + Portabel-Kennung
        ("dl0mt/qrp", "DL0MT/QRP"),
    ],
)
def test_sender_callsign_is_printed_uppercase(tmp_path: Path, typed, printed):
    """Das Rufzeichen steht vollständig und groß auf der Karte.

    Alles, was dazugehört, steht im Feld selbst — Landespräfix, Portabel-Kennung,
    `/QRP`. Ein eigenes Feld für die Kennung gibt es nicht mehr.
    """
    cfg = AppConfig(sender=SenderConfig(callsign=typed))
    out = tmp_path / "cards.pdf"
    generate(_dummy_cards(1), cfg, str(_front_image(tmp_path)), str(out))

    back = _content(PdfReader(str(out)).pages[1])
    assert f"({printed}) Tj" in back
    assert typed not in back


def test_locator_and_dok_are_printed_uppercase(tmp_path: Path):
    """Auch aus einer von Hand geänderten Config kommen sie groß aufs Papier."""
    cfg = AppConfig(sender=SenderConfig(callsign="DL2SCT", locator="jo31ab", dok="b01"))
    out = tmp_path / "cards.pdf"
    generate(_dummy_cards(1), cfg, str(_front_image(tmp_path)), str(out))

    back = _content(PdfReader(str(out)).pages[1])
    assert "(JO31AB) Tj" in back
    assert "(B01) Tj" in back


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
