"""Tests für qslcards.mostwanted: GDXF-Parser, Filterregel, Ablage, Neuladen.

Kein Netz: die Seite ist ein kleiner, von Hand gebauter Ausschnitt mit dem
Aufbau der echten GDXF-Tabellen (thead mit `th`, tbody mit `td`, Präfix als
Link `entity.php?entity=N`, Flaggenbild vor dem Namen). Eine Kopie der echten
Seite gehört nicht ins Repository — es sind Daten der GDXF.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import requests

from qslcards.mostwanted import (
    MostWantedFilter,
    MostWantedFormatError,
    MostWantedList,
    RankedEntity,
    category_for_mode,
    clamp_top,
    fetch_html,
    gdxf,
    is_stale,
    load,
    normalize_category,
    parse_html,
    refresh,
    store,
)

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def _row(rank: str, entity: str, prefix: str, name: str, pct: str) -> str:
    return (
        "<tr>\n"
        f'  <td class="center">{rank}</td>\n'
        f'  <td><a href="entity.php?entity={entity}">{prefix}</a></td>\n'
        f'  <td class="entity"><img src="../flags/X.png" alt=""> {name}</td>\n'
        f'  <td class="center">{pct}</td>\n'
        '  <td class="yellowcenter"><strong>1</strong></td>\n'
        '  <td class="center">2</td>\n'
        "</tr>\n"
    )


def _table(table_id: str, rows: str) -> str:
    return (
        f'<table class="mega" id="{table_id}">\n<thead>\n'
        f'<tr><th colspan="4">{table_id}</th><th colspan="2">Ranks</th></tr>\n'
        "<tr><th>#</th><th>Prefix</th><th>DXCC Entity</th><th>needed by</th>"
        "<th>2025</th><th>2024</th></tr>\n"
        f"</thead>\n<tbody>\n{rows}</tbody>\n</table>\n"
    )


PAGE = (
    "<html><body><h2>Most Wanted Ranking 2025</h2>"
    + _table(
        "Mixed",
        _row("1", "344", "P5", "DPRK (North Korea)", "96.4%")
        + _row("2", "138", "KH7K", "Kure Island", "94.3%")
        + _row("340", "230", "DL", "Federal Republic of Germany", "0.4%")
        # kaputte Zeilen: ohne gültigen Link, ohne Rang -> übersprungen
        + _row("3", "-1", "P5", "Somewhere near N.Korea", "1%")
        + _row("", "123", "KH3", "Johnston Island", "92.6%"),
    )
    + _table("CW", _row("1", "344", "P5", "DPRK (North Korea)", "100.0%"))
    + _table("Phone", _row("3", "174", "KH4", "Midway Island", "94.9%"))
    + _table("Digital", _row("1", "506", "BS7", "Scarborough Reef", "100.0%"))
    # eine fremde Tabelle (ohne Kategorie-id) wird nicht gelesen
    + '<table id="other"><tbody>'
    + _row("1", "1", "VE", "Canada", "1%")
    + "</tbody></table>"
    + "<footer>Page last updated: May 3, 2026 </footer>\n</body></html>"
)


def _ranking(fetched_at: datetime | None = NOW) -> MostWantedList:
    parsed = parse_html(PAGE)
    parsed.fetched_at = fetched_at.isoformat() if fetched_at else None
    return parsed


# ----------------------------------------------------------------- Parser


def test_parse_reads_all_four_categories():
    ranking = parse_html(PAGE)
    assert ranking.year == 2025
    assert ranking.updated == "May 3, 2026"
    assert set(ranking.rankings) == {"mixed", "cw", "phone", "digital"}
    assert ranking.rankings["mixed"][344] == RankedEntity(
        dxcc=344, rank=1, prefix="P5", name="DPRK (North Korea)", needed_pct=96.4
    )
    assert ranking.rank(230, "mixed") == 340
    assert ranking.rank(174, "phone") == 3


def test_parse_skips_rows_without_valid_entity_or_rank():
    mixed = parse_html(PAGE).rankings["mixed"]
    assert set(mixed) == {344, 138, 230}  # -1 und die Zeile ohne Rang fehlen
    assert 1 not in mixed  # die fremde Tabelle zählt nicht


def test_parse_without_ranking_tables_is_an_error():
    with pytest.raises(MostWantedFormatError):
        parse_html("<html><body><p>Wartungsarbeiten</p></body></html>")


def test_rank_of_unknown_or_unlisted_entity_is_none():
    ranking = parse_html(PAGE)
    assert ranking.rank(None, "mixed") is None
    assert ranking.rank(999, "mixed") is None


# --------------------------------------------------------------- Regeln


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("CW", "cw"),
        ("cw", "cw"),
        ("SSB", "phone"),
        ("FM", "phone"),
        ("AM", "phone"),
        ("DIGITALVOICE", "phone"),
        ("FT8", "digital"),
        ("RTTY", "digital"),
        ("DIGI", "digital"),  # Cabrillo `DG`
        ("", "mixed"),
        (None, "mixed"),
    ],
)
def test_category_for_mode(mode, expected):
    assert category_for_mode(mode) == expected


@pytest.mark.parametrize(
    "value,expected", [(100, 100), ("25", 25), (0, 1), (999, 340), ("", 100), ("x", 100)]
)
def test_clamp_top(value, expected):
    assert clamp_top(value) == expected


def test_normalize_category():
    assert normalize_category("CW") == "cw"
    assert normalize_category("auto") == "auto"
    assert normalize_category("bogus") == "auto"
    assert normalize_category(None) == "auto"


def test_filter_auto_uses_the_mode_list():
    """P5 ist in Digital nicht gelistet (im Ausschnitt), in CW Rang 1."""
    flt = MostWantedFilter(parse_html(PAGE), top=10)
    assert flt.rank(344, ["CW"]) == 1
    assert flt.rank(344, ["FT8"]) is None
    assert flt.accepts(344, ["FT8", "CW"])  # der beste Rang einer Karte zählt
    assert not flt.accepts(344, ["FT8"])


def test_filter_fixed_category_and_top_limit():
    ranking = parse_html(PAGE)
    assert MostWantedFilter(ranking, top=2, category="mixed").accepts(138, ["CW"])
    assert not MostWantedFilter(ranking, top=1, category="mixed").accepts(138, ["CW"])
    # ohne Mode zählt bei „Automatisch" Mixed
    assert MostWantedFilter(ranking, top=340).accepts(230, [])


def test_filter_fixed_mode_category_ignores_other_modes():
    ranking = parse_html(PAGE)
    cw = MostWantedFilter(ranking, top=10, category="cw")
    assert cw.accepts(344, ["CW"])
    assert not cw.accepts(344, ["SSB"])  # ein SSB-QSO bestätigt kein CW-Gebiet
    assert cw.accepts(344, ["SSB", "CW"])  # Karte „pro Station" mit einem CW-QSO
    assert MostWantedFilter(ranking, top=10, category="mixed").accepts(344, ["SSB"])


def test_filter_without_list_or_dxcc_rejects():
    assert not MostWantedFilter(None).accepts(344, ["CW"])
    assert not MostWantedFilter(parse_html(PAGE)).accepts(None, ["CW"])


# ---------------------------------------------------------------- Ablage


def test_store_roundtrip(tmp_path: Path):
    path = tmp_path / "mostwanted.json"
    store.save(_ranking(), path)
    loaded = load(path)
    assert loaded == _ranking()


@pytest.mark.parametrize("content", ["{kaputt", '{"format": 99, "rankings": {}}', "[]"])
def test_store_unreadable_or_foreign_file_counts_as_missing(tmp_path: Path, content: str):
    path = tmp_path / "mostwanted.json"
    path.write_text(content, encoding="utf-8")
    assert load(path) is None


def test_is_stale():
    assert is_stale(None, now=NOW)
    assert is_stale(_ranking(fetched_at=None), now=NOW)
    assert not is_stale(_ranking(NOW - timedelta(days=29)), now=NOW)
    assert is_stale(_ranking(NOW - timedelta(days=31)), now=NOW)


# -------------------------------------------------------------- Neuladen


def _no_fetch() -> str:
    raise AssertionError("darf nicht abrufen")


def _failing_fetch() -> str:
    raise requests.ConnectionError("offline")


def test_refresh_fresh_copy_does_not_touch_the_network(tmp_path: Path):
    path = tmp_path / "mostwanted.json"
    store.save(_ranking(NOW - timedelta(days=3)), path)
    result = refresh(path, now=NOW, fetch=_no_fetch)
    assert result.ranking is not None and not result.fetched and result.error is None


def test_refresh_fetches_when_missing_and_saves(tmp_path: Path):
    path = tmp_path / "mostwanted.json"
    result = refresh(path, now=NOW, fetch=lambda: PAGE)
    assert result.fetched and result.error is None
    assert result.ranking.fetched_at == NOW.isoformat()
    assert load(path) == result.ranking


def test_refresh_force_fetches_even_when_fresh(tmp_path: Path):
    path = tmp_path / "mostwanted.json"
    store.save(_ranking(NOW), path)
    assert refresh(path, force=True, now=NOW, fetch=lambda: PAGE).fetched


def test_refresh_failure_keeps_the_old_copy(tmp_path: Path):
    path = tmp_path / "mostwanted.json"
    old = _ranking(NOW - timedelta(days=90))
    store.save(old, path)
    for fetch in (_failing_fetch, lambda: "<html>Wartung</html>"):
        result = refresh(path, now=NOW, fetch=fetch)
        assert result.ranking == old and result.error and not result.fetched
    assert load(path) == old  # nichts überschrieben


def test_refresh_failure_without_copy_has_no_list(tmp_path: Path):
    result = refresh(tmp_path / "mostwanted.json", now=NOW, fetch=_failing_fetch)
    assert result.ranking is None and "offline" in result.error


# ----------------------------------------------------------------- Abruf


class _FakeResponse:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text, self.status_code, self.encoding = text, status, "utf-8"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
        return self.response


def test_fetch_asks_for_all_ranks_and_says_who_asks():
    http = _FakeSession(_FakeResponse(PAGE))
    assert fetch_html(http=http) == PAGE
    call = http.calls[0]
    assert call["url"] == gdxf.URL
    assert call["data"] == {"show": "500"}  # „all" statt der Top 25
    assert call["headers"]["User-Agent"].startswith("QSL-Karten-Generator/")
    assert call["timeout"]


def test_fetch_http_error_is_raised_for_refresh_to_handle():
    with pytest.raises(requests.HTTPError):
        fetch_html(http=_FakeSession(_FakeResponse("", status=503)))


def test_saved_file_is_sorted_by_rank(tmp_path: Path):
    path = tmp_path / "mostwanted.json"
    store.save(_ranking(), path)
    ranks = [row["rank"] for row in json.loads(path.read_text("utf-8"))["rankings"]["mixed"]]
    assert ranks == sorted(ranks)
