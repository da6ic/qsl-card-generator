"""Wavelog-Anbindung: URL, Umsetzung der QSOs, Paging, Markieren — ohne Netz."""

from __future__ import annotations

import json

import pytest

from qslcards import config as cfg
from qslcards.wavelog import (
    PaperQslMark,
    WavelogClient,
    WavelogError,
    normalize_base_url,
    qso_from_json,
)
from qslcards.wavelog.client import paper_qsl_already_sent


class _Resp:
    def __init__(self, status: int, body=None):
        self.status_code = status
        self._body = body
        self.content = b"" if body is None else json.dumps(body).encode()

    def json(self):
        if self._body is None:
            raise ValueError("kein JSON")
        return self._body


class _Session:
    """Ersetzt `requests.Session`: merkt sich die Aufrufe, liefert Antworten."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        kwargs = {k: dict(v) if isinstance(v, dict) else v for k, v in kwargs.items()}
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


QSO_JSON = {
    "id": 4886,
    "station_id": 1,
    "call": "ea8abc",
    "band": "20M",
    "mode": "MFSK",
    "submode": "FT8",
    "freq": 14074000,
    "qso_date": "2026-10-19 14:38:05",
    "rst_sent": "-12",
    "rst_rcvd": "-08",
    "gridsquare": "IL18",
    "name": "Juan",
    "qsl_sent": "N",
}


@pytest.mark.parametrize(
    "given, expected",
    [
        ("log.example.com", "https://log.example.com/index.php/api/v2"),
        ("https://log.example.com/", "https://log.example.com/index.php/api/v2"),
        ("http://host/wavelog/index.php", "http://host/wavelog/index.php/api/v2"),
        ("https://host/index.php/api/v2/", "https://host/index.php/api/v2"),
    ],
)
def test_normalize_base_url(given, expected):
    assert normalize_base_url(given) == expected


def test_empty_url_or_key_is_a_readable_error():
    with pytest.raises(WavelogError):
        normalize_base_url("  ")
    with pytest.raises(WavelogError, match="API-Key"):
        WavelogClient("https://x", "")


def test_qso_from_json_maps_the_card_fields():
    qso = qso_from_json(QSO_JSON)
    assert qso is not None
    assert qso.call == "EA8ABC"
    assert (qso.qso_date, qso.time_on) == ("20261019", "143805")
    assert qso.freq == "14.074"  # Hz -> MHz
    assert qso.mode == "FT8"  # Submode gewinnt, wie beim ADIF-Import
    assert qso.band == "20m"
    assert qso.raw["wavelog_id"] == "4886"
    assert not paper_qsl_already_sent(qso)


def test_qso_from_json_skips_unusable_entries():
    assert qso_from_json({"id": 1, "call": "", "qso_date": "2026-10-19 14:38:05"}) is None
    assert qso_from_json({"id": 1, "call": "DL1A", "qso_date": "kaputt"}) is None


def test_stations_sends_bearer_and_puts_the_active_one_first():
    session = _Session(
        _Resp(
            200,
            {
                "data": [
                    {"id": 2, "name": "Portabel", "callsign": "dl0qsl/p", "active": False},
                    {
                        "id": 1,
                        "name": "Home",
                        "callsign": "DL0QSL",
                        "gridsquare": "jo62qm",
                        "cq": 14,
                        "itu": 28,
                        "active": True,
                    },
                ]
            },
        )
    )
    client = WavelogClient("log.example.com", "wl2_abc", session=session)
    stations = client.stations()
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("GET", "https://log.example.com/index.php/api/v2/station")
    assert kwargs["headers"]["Authorization"] == "Bearer wl2_abc"
    assert [s.id for s in stations] == [1, 2]
    assert stations[0].gridsquare == "JO62QM"
    assert stations[0].label == "DL0QSL · Home (JO62QM) ★"


def test_qsos_pages_until_has_more_is_false():
    second = dict(QSO_JSON, id=4887, qso_date="2026-10-18 10:00:00")
    session = _Session(
        _Resp(200, {"data": [QSO_JSON], "meta": {"total": 2, "has_more": True}}),
        _Resp(200, {"data": [second], "meta": {"total": 2, "has_more": False}}),
    )
    client = WavelogClient("https://h", "wl2_x", session=session)
    seen = []
    qsos = client.qsos(1, since="2026-10-01", progress_cb=lambda d, t: seen.append((d, t)))
    assert [q.raw["wavelog_id"] for q in qsos] == ["4887", "4886"]  # älteste zuerst
    params = [call[2]["params"] for call in session.calls]
    assert [p["page"] for p in params] == [1, 2]
    assert params[0]["station_id"] == 1 and params[0]["qso_since"] == "2026-10-01"
    assert seen[-1] == (2, 2)


@pytest.mark.parametrize(
    "status, text",
    [(401, "abgelehnt"), (403, "Berechtigung"), (404, "3.2.5"), (500, "500")],
)
def test_http_errors_become_readable_messages(status, text):
    client = WavelogClient("https://h", "wl2_x", session=_Session(_Resp(status, {})))
    with pytest.raises(WavelogError, match=text):
        client.stations()


def test_mark_paper_sent_patches_the_qso():
    session = _Session(_Resp(200, {"data": {}}))
    client = WavelogClient("https://h", "wl2_x", session=session)
    client.mark_paper_sent(PaperQslMark("4886", "B"), date="2026-11-26")
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("PATCH", "https://h/index.php/api/v2/qso/4886")
    assert kwargs["json"] == {"qsl_sent": "Y", "qsl_sent_via": "B", "qslsdate": "2026-11-26"}


def test_mark_many_stops_when_the_key_is_rejected():
    session = _Session(_Resp(200, {}), _Resp(401, {}), _Resp(200, {}))
    client = WavelogClient("https://h", "wl2_x", session=session)
    done, errors = client.mark_many([PaperQslMark(str(i)) for i in range(3)])
    assert done == ["0"] and len(errors) == 1
    assert len(session.calls) == 2  # der dritte wird gar nicht mehr versucht


def test_wavelog_settings_roundtrip_without_the_key(tmp_path):
    config = cfg.AppConfig()
    config.source = cfg.SourceConfig(kind="wavelog")
    config.wavelog = cfg.WavelogConfig(url="https://h", station_id=3, mark_sent=False)
    path = tmp_path / "config.yaml"
    cfg.save(config, path)
    loaded = cfg.load(path)
    assert loaded.source.kind == "wavelog"
    assert loaded.wavelog.station_id == 3 and loaded.wavelog.mark_sent is False
    assert "wl2_" not in path.read_text(encoding="utf-8")
    assert "\n  key:" not in path.read_text(encoding="utf-8")
