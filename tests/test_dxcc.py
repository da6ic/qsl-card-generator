"""Tests für qslcards.dxcc: Rufzeichen -> DXCC über die cty.dat (AD1C).

Die Fälle der Zuordnung stammen aus dem Programm „DXCC-Filter", nach dessen
Regeln das Modul gebaut ist. Kein Netz: abgerufen wird über ein `fetch`, das
der Test selbst stellt.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from qslcards import dxcc, paths
from qslcards.logbook import parse_file

NUMBERS = paths.dxcc_numbers_path()
BUNDLED = paths.bundled_cty_path()
NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

# Ein paar Einträge im cty.dat-Format (Auszug, wie die echte Datei aufgebaut).
CTY = """\
Turkey:                   20:  39:  EU:   39.18:   -35.65:    -3.0:  TA:
    TA,TB,TC,YM;
European Turkey:          20:  39:  EU:   41.02:   -28.97:    -2.0:  *TA1:
    =TA1C,=TA1D;
Madeira Islands:          33:  36:  AF:   32.75:    16.95:     0.0:  CT3:
    CQ3,CQ9,CR3,CR9,CS3,CS9,CT3,CT9;
Morocco:                  33:  37:  AF:   32.00:     5.00:     0.0:  CN:
    5C,5D,5E,5F,5G,CN;
Canary Islands:           33:  36:  AF:   28.32:    15.85:     0.0:  EA8:
    AM8,AN8,EA8,EB8,EC8,ED8,EE8,EF8,EG8,EH8;
Fed. Rep. of Germany:     14:  28:  EU:   51.00:   -10.00:    -1.0:  DL:
    DA,DB,DC,DD,DE,DF,DG,DH,DI,DJ,DK,DL,DM,DN,DO,DP,DQ,DR,=DL0ABC(15);
Australia:                30:  59:  OC:  -23.70:  -132.33:   -10.0:  VK:
    AX,VH,VI,VJ,VK,VL,VM,VN,VZ;
Norfolk Island:           32:  60:  OC:  -29.03:  -167.93:   -11.0:  VK9N:
    VK9N,=VK9DX;
United States:            05:  08:  NA:   37.53:    91.67:     5.0:  K:
    AA,K,N,W,=VER20261023;
"""


@pytest.fixture(scope="module")
def db() -> dxcc.CtyDatabase:
    return dxcc.CtyDatabase(CTY, NUMBERS.read_text(encoding="utf-8"))


# ------------------------------------------------------------- Zuordnung


@pytest.mark.parametrize(
    "call,expected",
    [
        ("TA3T", 390),  # Türkei
        ("CN3A", 446),  # Marokko
        ("CT9/M0CCC", 256),  # Präfix vor dem Schrägstrich: Madeira
        ("DL1ABC/EA8", 29),  # Präfix dahinter: Kanaren
        ("DL1ABC/P", 230),  # /P sagt nichts über den Ort
        ("DL0ABC", 230),  # exakter Eintrag (mit Zonen-Überschreibung)
        ("VK9DX", 189),  # exakter Eintrag schlägt den Präfix VK (Australien)
        ("VK9NA", 189),  # längster Präfix: VK9N vor VK
        ("VK2ABC", 150),
        ("dl1abc", 230),  # Kleinschreibung
    ],
)
def test_lookup(db, call, expected):
    assert db.dxcc(call) == expected


def test_maritime_and_aeronautical_mobile_have_no_entity(db):
    assert db.lookup("DL1ABC/MM") is None
    assert db.lookup("DL1ABC/AM") is None


def test_unknown_or_empty_call(db):
    assert db.lookup("") is None
    assert db.lookup("0XYZ") is None


def test_wae_only_entities_are_skipped(db):
    """`*TA1` ist nur ein WAE-Gebiet, kein DXCC-Gebiet: TA1C zählt als Türkei."""
    assert db.dxcc("TA1C") == 390


def test_version_is_read(db):
    assert db.version == "2026-10-23"


@pytest.mark.parametrize(
    "call,expected",
    [
        ("CT9/M0CCC", "CT9"),
        ("DL1ABC/EA8", "EA8"),
        ("W1AW/4", "W4AW"),
        ("DL1ABC/P", "DL1ABC"),
        ("DL1ABC/QRP", "DL1ABC"),
        ("F/DL0MT/P", "F"),
        ("DL1ABC/MM", None),
    ],
)
def test_location_part(call, expected):
    assert dxcc.location_part(call) == expected


def test_parse_numbers_skips_comments_and_garbage():
    text = "# Kopf\n1A;246;Malta\nkaputt\nXX;keine;Zahl\n"
    assert dxcc.parse_numbers(text) == {"1A": 246}


# ---------------------------------------------------- mitgelieferte Daten


def test_bundled_data_is_complete():
    """Jedes DXCC-Gebiet der mitgelieferten cty.dat hat eine Nummer, und die
    Tabelle kennt jede der 340 Nummern genau einmal (so viele führt die GDXF)."""
    database = dxcc.load(Path("fehlt.dat"), BUNDLED, NUMBERS)
    assert database is not None and database.version
    entities = {*database.prefixes.values(), *database.exact.values()}
    assert [e.prefix for e in entities if e.dxcc is None] == []
    numbers = dxcc.parse_numbers(NUMBERS.read_text(encoding="utf-8"))
    assert len(numbers) == len(set(numbers.values())) == 340


_SAMPLE_ADIF = Path(__file__).resolve().parent.parent / "beispiel-logs" / "cqww26.adi"


@pytest.mark.skipif(not _SAMPLE_ADIF.exists(), reason="Beispiel-Log liegt nicht im Repository")
def test_bundled_cty_matches_the_logger_on_the_sample_contest():
    """QARTest hat in cqww26.adi jedes Gebiet selbst gesetzt — die cty.dat muss
    dasselbe liefern (Cabrillo hat kein DXCC-Feld und ist darauf angewiesen)."""
    database = dxcc.load(Path("fehlt.dat"), BUNDLED, NUMBERS)
    qsos = parse_file(_SAMPLE_ADIF)
    wrong = [
        (q.call, q.dxcc, database.dxcc(q.call))
        for q in qsos
        if int(q.dxcc) != database.dxcc(q.call)
    ]
    assert wrong == []


# ------------------------------------------------------- Laden/Neuladen


def _cty_text() -> str:
    return BUNDLED.read_bytes().decode("latin-1")


def _age(path: Path, days: float) -> None:
    stamp = (NOW - timedelta(days=days)).timestamp()
    os.utime(path, (stamp, stamp))


def _no_fetch() -> str:
    raise AssertionError("darf nicht abrufen")


def test_load_prefers_the_stored_copy(tmp_path: Path):
    stored = tmp_path / "cty.dat"
    stored.write_bytes(_cty_text().replace("=VER20261023", "=VER20261101").encode("latin-1"))
    assert dxcc.load(stored, BUNDLED, NUMBERS).version == "2026-11-01"


@pytest.mark.parametrize("content", [None, b"", b"<html>Fehler</html>"])
def test_load_falls_back_to_the_bundled_copy(tmp_path: Path, content):
    stored = tmp_path / "cty.dat"
    if content is not None:
        stored.write_bytes(content)
    database = dxcc.load(stored, BUNDLED, NUMBERS)
    assert database is not None and database.version  # mitgelieferte Kopie


def test_is_stale_by_file_age(tmp_path: Path):
    stored = tmp_path / "cty.dat"
    assert dxcc.is_stale(stored, now=NOW)  # fehlt
    stored.write_bytes(b"x")
    _age(stored, 13)
    assert not dxcc.is_stale(stored, now=NOW)
    _age(stored, 15)
    assert dxcc.is_stale(stored, now=NOW)


def test_refresh_fresh_copy_does_not_touch_the_network(tmp_path: Path):
    stored = tmp_path / "cty.dat"
    stored.write_bytes(BUNDLED.read_bytes())
    _age(stored, 1)
    result = dxcc.refresh(stored, BUNDLED, NUMBERS, now=NOW, fetch=_no_fetch)
    assert result.database is not None and not result.fetched and result.error is None


def test_refresh_fetches_and_saves(tmp_path: Path):
    stored = tmp_path / "cty.dat"
    result = dxcc.refresh(stored, BUNDLED, NUMBERS, now=NOW, fetch=_cty_text)
    assert result.fetched and result.error is None
    assert stored.read_bytes() == BUNDLED.read_bytes()  # byteweise wie geladen


@pytest.mark.parametrize(
    "answer", ["<html>403 Forbidden</html>", "Turkey: 20: 39: EU: 1: 2: 3: TA:\n TA;"]
)
def test_refresh_rejects_something_that_is_no_cty_dat(tmp_path: Path, answer):
    """Eine Fehlerseite (oder ein Bruchstück) darf nie eine gute Kopie ersetzen."""
    stored = tmp_path / "cty.dat"
    stored.write_bytes(BUNDLED.read_bytes())
    _age(stored, 30)
    result = dxcc.refresh(stored, BUNDLED, NUMBERS, now=NOW, fetch=lambda: answer)
    assert result.error and not result.fetched and result.database is not None
    assert stored.read_bytes() == BUNDLED.read_bytes()


def test_refresh_network_error_keeps_the_copy(tmp_path: Path):
    def offline() -> str:
        raise OSError("offline")

    result = dxcc.refresh(tmp_path / "cty.dat", BUNDLED, NUMBERS, now=NOW, fetch=offline)
    assert result.database is not None and "offline" in result.error
