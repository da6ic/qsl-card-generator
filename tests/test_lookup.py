"""Tests für qslcards.lookup: HamQTH-, QRZ-Client, Cache, ChainedLookup.

Kein echter Netzcall: HTTP wird über ein `FakeSession`-Objekt gemockt, das
vordefinierte XML-Antworten liefert (mit denselben Namespaces wie die echten
APIs). So sind Session-Handling, Reauth-Retry, Parsing und Fehlerpfade prüfbar.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from qslcards.config import LookupConfig
from qslcards.lookup import (
    accepted_routes,
    active_via_priority,
    build_lookup,
    extract_manager_callsign,
    has_lookup_credentials,
    lookup_calls,
    normalize_via_priority,
    resolve_route,
)
from qslcards.lookup.base import ChainedLookup, LookupResult
from qslcards.lookup.cache import LookupCache
from qslcards.lookup.hamqth import HamQTHClient
from qslcards.lookup.qrz import QRZClient

# -- HTTP-Mock ------------------------------------------------------------

HAMQTH_NS = 'xmlns="https://www.hamqth.com"'
QRZ_NS = 'xmlns="http://xmldata.qrz.com"'


class FakeResponse:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text = text
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Liefert Antworten aus einer Queue; zeichnet aufgerufene URLs/Params auf."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if not self._responses:
            raise AssertionError(f"Unerwarteter zusätzlicher HTTP-Call: {url}")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def hamqth_session_xml(session_id: str = "SESSION123") -> str:
    return (
        f'<?xml version="1.0"?><HamQTH version="2.7" {HAMQTH_NS}>'
        f"<session><session_id>{session_id}</session_id></session></HamQTH>"
    )


def hamqth_error_xml(message: str) -> str:
    return (
        f'<?xml version="1.0"?><HamQTH version="2.7" {HAMQTH_NS}>'
        f"<session><error>{message}</error></session></HamQTH>"
    )


def hamqth_search_xml(call: str = "DL1ABC") -> str:
    return (
        f'<?xml version="1.0"?><HamQTH version="2.7" {HAMQTH_NS}><search>'
        f"<callsign>{call}</callsign>"
        "<nick>Hans</nick>"
        "<adr_name>Hans Mustermann</adr_name>"
        "<adr_street1>Musterweg 1</adr_street1>"
        "<adr_city>Musterstadt</adr_city>"
        "<adr_zip>12345</adr_zip>"
        "<adr_country>Germany</adr_country>"
        "<grid>JO31AB</grid>"
        "<qsl_via>OH2BH</qsl_via>"
        "<qsl>Y</qsl>"
        "<qsldirect>N</qsldirect>"
        "<lotw>Y</lotw>"
        "<eqsl>?</eqsl>"
        "</search></HamQTH>"
    )


def qrz_session_xml(key: str = "KEY123") -> str:
    return (
        f'<?xml version="1.0"?><QRZDatabase version="1.34" {QRZ_NS}>'
        f"<Session><Key>{key}</Key><SubExp>Wed Jan 1 12:00:00 2027</SubExp>"
        "</Session></QRZDatabase>"
    )


def qrz_error_xml(message: str, with_key: bool = False) -> str:
    key = "<Key>KEY123</Key>" if with_key else ""
    return (
        f'<?xml version="1.0"?><QRZDatabase version="1.34" {QRZ_NS}>'
        f"<Session>{key}<Error>{message}</Error></Session></QRZDatabase>"
    )


def qrz_callsign_xml(call: str = "AA7BQ") -> str:
    return (
        f'<?xml version="1.0"?><QRZDatabase version="1.34" {QRZ_NS}><Callsign>'
        f"<call>{call}</call>"
        "<fname>Fred</fname><name>Lloyd</name>"
        "<name_fmt>Fred L Lloyd</name_fmt>"
        "<addr1>8711 E Pinnacle Peak Rd</addr1>"
        "<addr2>Scottsdale</addr2>"
        "<state>AZ</state><zip>85255</zip>"
        "<country>United States</country>"
        "<grid>DM43</grid>"
        "<qslmgr>W3HNK</qslmgr>"
        "</Callsign></QRZDatabase>"
    )


# -- HamQTH ---------------------------------------------------------------


def test_hamqth_login_and_lookup():
    http = FakeSession([FakeResponse(hamqth_session_xml()), FakeResponse(hamqth_search_xml())])
    client = HamQTHClient("user", "pass", "qslcards", http=http)

    result = client.lookup("dl1abc")

    assert result is not None
    assert result.call == "DL1ABC"
    assert result.name == "Hans Mustermann"
    assert result.street == "Musterweg 1"
    assert result.city == "Musterstadt"
    assert result.zip == "12345"
    assert result.country == "Germany"
    assert result.grid == "JO31AB"
    assert result.source == "hamqth"
    # QSL-Routing-Felder
    assert result.manager == "OH2BH"
    assert result.accepts_bureau == "Y"
    assert result.accepts_direct == "N"
    assert result.lotw == "Y"
    assert result.eqsl == "?"
    # 1. Call = Session, 2. Call = Lookup (mit prg-Parameter)
    assert http.calls[0][1] == {"u": "user", "p": "pass"}
    assert http.calls[1][1] == {"id": "SESSION123", "callsign": "DL1ABC", "prg": "qslcards"}


def test_hamqth_session_reused_across_lookups():
    http = FakeSession(
        [
            FakeResponse(hamqth_session_xml()),
            FakeResponse(hamqth_search_xml("DL1ABC")),
            FakeResponse(hamqth_search_xml("DL2XYZ")),
        ]
    )
    client = HamQTHClient("user", "pass", http=http)

    client.lookup("DL1ABC")
    client.lookup("DL2XYZ")

    # Nur eine Anmeldung für zwei Lookups.
    assert sum(1 for _, p in http.calls if p and "u" in p) == 1


def test_hamqth_reauth_on_expired_session():
    http = FakeSession(
        [
            FakeResponse(hamqth_session_xml("OLD")),
            FakeResponse(hamqth_error_xml("Session does not exist or expired")),
            FakeResponse(hamqth_session_xml("NEW")),
            FakeResponse(hamqth_search_xml()),
        ]
    )
    client = HamQTHClient("user", "pass", http=http)

    result = client.lookup("DL1ABC")

    assert result is not None
    assert result.name == "Hans Mustermann"
    # Zweite Anmeldung erfolgte, letzter Lookup nutzt die neue Session.
    assert http.calls[-1][1]["id"] == "NEW"


def test_hamqth_reauth_only_once():
    # Bleibt die Session dauerhaft „expired", wird nicht endlos wiederholt.
    http = FakeSession(
        [
            FakeResponse(hamqth_session_xml("OLD")),
            FakeResponse(hamqth_error_xml("Session does not exist or expired")),
            FakeResponse(hamqth_session_xml("NEW")),
            FakeResponse(hamqth_error_xml("Session does not exist or expired")),
        ]
    )
    client = HamQTHClient("user", "pass", http=http)

    assert client.lookup("DL1ABC") is None


def test_hamqth_callsign_not_found():
    http = FakeSession(
        [
            FakeResponse(hamqth_session_xml()),
            FakeResponse(hamqth_error_xml("Callsign not found")),
        ]
    )
    client = HamQTHClient("user", "pass", http=http)

    assert client.lookup("XX0XXX") is None


def test_hamqth_network_error_is_not_fatal():
    http = FakeSession([requests.ConnectionError("boom")])
    client = HamQTHClient("user", "pass", http=http)

    assert client.lookup("DL1ABC") is None


def test_hamqth_http_error_is_not_fatal():
    http = FakeSession([FakeResponse("", status=500)])
    client = HamQTHClient("user", "pass", http=http)

    assert client.lookup("DL1ABC") is None


def test_hamqth_login_failure_returns_none():
    http = FakeSession([FakeResponse(hamqth_error_xml("Wrong user name or password"))])
    client = HamQTHClient("user", "badpass", http=http)

    assert client.lookup("DL1ABC") is None


def test_hamqth_without_credentials_short_circuits():
    http = FakeSession([])  # kein einziger Call erwartet
    client = HamQTHClient("", "", http=http)

    assert client.lookup("DL1ABC") is None
    assert http.calls == []


# -- QRZ ------------------------------------------------------------------


def test_qrz_login_and_lookup():
    http = FakeSession([FakeResponse(qrz_session_xml()), FakeResponse(qrz_callsign_xml())])
    client = QRZClient("user", "pass", http=http)

    result = client.lookup("aa7bq")

    assert result is not None
    assert result.call == "AA7BQ"
    assert result.name == "Fred L Lloyd"
    assert result.street == "8711 E Pinnacle Peak Rd"
    assert result.city == "Scottsdale"
    assert result.zip == "85255"
    assert result.country == "United States"
    assert result.grid == "DM43"
    assert result.manager == "W3HNK"
    # QRZ liefert keine Büro/Direkt/LoTW/eQSL-Flags
    assert result.accepts_bureau is None
    assert result.accepts_direct is None
    assert result.source == "qrz"


def test_qrz_uses_semicolon_separated_query():
    http = FakeSession([FakeResponse(qrz_session_xml()), FakeResponse(qrz_callsign_xml())])
    client = QRZClient("user", "pass", http=http)
    client.lookup("AA7BQ")

    login_url = http.calls[0][0]
    lookup_url = http.calls[1][0]
    assert "username=user;password=pass;agent=" in login_url
    assert "s=KEY123;callsign=AA7BQ" in lookup_url


def test_qrz_name_fallback_without_name_fmt():
    xml = qrz_callsign_xml().replace("<name_fmt>Fred L Lloyd</name_fmt>", "")
    http = FakeSession([FakeResponse(qrz_session_xml()), FakeResponse(xml)])
    client = QRZClient("user", "pass", http=http)

    result = client.lookup("AA7BQ")
    assert result is not None
    assert result.name == "Fred Lloyd"


def test_qrz_reauth_on_session_timeout():
    http = FakeSession(
        [
            FakeResponse(qrz_session_xml("OLD")),
            FakeResponse(qrz_error_xml("Session Timeout")),
            FakeResponse(qrz_session_xml("NEW")),
            FakeResponse(qrz_callsign_xml()),
        ]
    )
    client = QRZClient("user", "pass", http=http)

    result = client.lookup("AA7BQ")
    assert result is not None
    assert "s=NEW;callsign=AA7BQ" in http.calls[-1][0]


def test_qrz_not_found_returns_none():
    http = FakeSession(
        [FakeResponse(qrz_session_xml()), FakeResponse(qrz_error_xml("Not found: AA7BQ"))]
    )
    client = QRZClient("user", "pass", http=http)

    assert client.lookup("AA7BQ") is None


def test_qrz_login_failure_returns_none():
    http = FakeSession([FakeResponse(qrz_error_xml("Username/password incorrect"))])
    client = QRZClient("user", "badpass", http=http)

    assert client.lookup("AA7BQ") is None


def test_qrz_network_error_is_not_fatal():
    http = FakeSession([requests.Timeout("slow")])
    client = QRZClient("user", "pass", http=http)

    assert client.lookup("AA7BQ") is None


# -- Cache ----------------------------------------------------------------


def test_cache_roundtrip(tmp_path: Path):
    path = tmp_path / "cache.json"
    cache = LookupCache(path)
    result = LookupResult(call="DL1ABC", name="Hans", city="Berlin", source="hamqth")
    cache.set("DL1ABC", result)

    # Neu laden von Platte
    reloaded = LookupCache(path).get("DL1ABC")
    assert reloaded is not None
    assert reloaded.name == "Hans"
    assert reloaded.city == "Berlin"
    # Positiver Treffer aus dem Cache meldet source="cache"
    assert reloaded.source == "cache"


def test_cache_miss_returns_none(tmp_path: Path):
    cache = LookupCache(tmp_path / "cache.json")
    assert cache.get("NOPE") is None
    assert "NOPE" not in cache


def test_cache_negative_entry(tmp_path: Path):
    cache = LookupCache(tmp_path / "cache.json")
    cache.set("XX0XXX", LookupResult(call="XX0XXX", source="none"))
    cached = cache.get("XX0XXX")
    assert cached is not None
    assert cached.is_empty()  # negativer Eintrag bleibt leer


def test_cache_case_insensitive(tmp_path: Path):
    cache = LookupCache(tmp_path / "cache.json")
    cache.set("dl1abc", LookupResult(call="DL1ABC", name="Hans", source="hamqth"))
    assert cache.get("DL1ABC") is not None
    assert cache.get("dl1abc") is not None


def test_cache_expiry(tmp_path: Path):
    path = tmp_path / "cache.json"
    cache = LookupCache(path, max_age_days=30)
    cache.set("DL1ABC", LookupResult(call="DL1ABC", name="Hans", source="hamqth"))

    # Zeitstempel künstlich altern lassen
    data = json.loads(path.read_text(encoding="utf-8"))
    data["DL1ABC"]["queried_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(json.dumps(data), encoding="utf-8")

    assert LookupCache(path, max_age_days=30).get("DL1ABC") is None


def test_cache_corrupt_file_is_not_fatal(tmp_path: Path):
    path = tmp_path / "cache.json"
    path.write_text("{ this is not json", encoding="utf-8")
    cache = LookupCache(path)  # darf nicht werfen
    assert cache.get("DL1ABC") is None


# -- ChainedLookup --------------------------------------------------------


class StubProvider:
    def __init__(self, results: dict[str, LookupResult | None]) -> None:
        self.results = results
        self.calls: list[str] = []

    def lookup(self, call: str) -> LookupResult | None:
        self.calls.append(call)
        return self.results.get(call)


def test_chain_prefers_first_provider():
    a = StubProvider({"DL1ABC": LookupResult(call="DL1ABC", name="A", source="hamqth")})
    b = StubProvider({"DL1ABC": LookupResult(call="DL1ABC", name="B", source="qrz")})
    chain = ChainedLookup([a, b])

    result = chain.lookup("DL1ABC")
    assert result is not None and result.name == "A"
    assert b.calls == []  # zweiter Provider gar nicht befragt


def test_chain_falls_back_to_second_provider():
    a = StubProvider({"DL1ABC": None})
    b = StubProvider({"DL1ABC": LookupResult(call="DL1ABC", name="B", source="qrz")})
    chain = ChainedLookup([a, b])

    result = chain.lookup("DL1ABC")
    assert result is not None and result.name == "B"


def test_chain_caches_positive_and_skips_second_lookup(tmp_path: Path):
    provider = StubProvider({"DL1ABC": LookupResult(call="DL1ABC", name="Hans", source="hamqth")})
    cache = LookupCache(tmp_path / "cache.json")
    chain = ChainedLookup([provider], cache=cache)

    first = chain.lookup("DL1ABC")
    second = chain.lookup("DL1ABC")

    assert first is not None and second is not None
    assert provider.calls == ["DL1ABC"]  # zweiter Aufruf aus Cache
    assert second.source == "cache"


def test_chain_caches_negative_and_skips_second_lookup(tmp_path: Path):
    provider = StubProvider({"XX0XXX": None})
    cache = LookupCache(tmp_path / "cache.json")
    chain = ChainedLookup([provider], cache=cache)

    assert chain.lookup("XX0XXX") is None
    assert chain.lookup("XX0XXX") is None
    assert provider.calls == ["XX0XXX"]  # negativer Treffer gecacht


def test_chain_force_bypasses_cache(tmp_path: Path):
    # Negativer Cache-Eintrag (z.B. nach Netzabbruch) soll mit force=True
    # erneut abgefragt werden.
    provider = StubProvider({"DL1ABC": LookupResult(call="DL1ABC", name="Hans", source="hamqth")})
    cache = LookupCache(tmp_path / "cache.json")
    cache.set("DL1ABC", LookupResult(call="DL1ABC", source="none"))  # negativ
    chain = ChainedLookup([provider], cache=cache)

    assert chain.lookup("DL1ABC") is None  # normal: negativer Cache-Treffer
    assert provider.calls == []

    forced = chain.lookup("DL1ABC", force=True)
    assert forced is not None and forced.name == "Hans"
    assert provider.calls == ["DL1ABC"]
    assert chain.lookup("DL1ABC") is not None  # jetzt positiv gecacht


def test_chain_empty_call_returns_none():
    chain = ChainedLookup([])
    assert chain.lookup("") is None
    assert chain.lookup("   ") is None


# -- Factory --------------------------------------------------------------


def test_build_lookup_without_credentials_is_cache_only(tmp_path: Path):
    chain = build_lookup(LookupConfig(), cache_path=tmp_path / "cache.json")
    assert isinstance(chain, ChainedLookup)
    # Ohne Credentials keine Provider → nur Cache; unbekanntes Call = None
    assert chain.lookup("DL1ABC") is None


def test_build_lookup_wires_providers(tmp_path: Path):
    cfg = LookupConfig(
        hamqth_user="u",
        hamqth_pass="p",
        qrz_user="qu",
        qrz_pass="qp",
    )
    chain = build_lookup(cfg, cache_path=tmp_path / "cache.json")
    assert len(chain._providers) == 2  # HamQTH + QRZ


def _seeded_cache(tmp_path: Path, entries: dict[str, LookupResult]) -> Path:
    path = tmp_path / "cache.json"
    cache = LookupCache(path)
    for call, result in entries.items():
        cache.set(call, result)
    return path


# -- accepted_routes ------------------------------------------------------


def test_accepted_routes_manager_counts_as_bureau():
    # Manager zählt als Büro-Weg (kein eigener Code).
    r = LookupResult(call="X", manager="OH2BH", source="hamqth")
    assert accepted_routes(r, "B") == ("B",)


def test_accepted_routes_bureau_and_direct():
    r = LookupResult(call="X", accepts_bureau="Y", accepts_direct="Y", source="hamqth")
    assert accepted_routes(r, "B") == ("B", "D")


def test_accepted_routes_direct_only():
    r = LookupResult(call="X", accepts_bureau="N", accepts_direct="Y", source="hamqth")
    assert accepted_routes(r, "B") == ("D",)


def test_accepted_routes_electronic_split_into_q_and_l():
    r = LookupResult(call="X", accepts_bureau="N", eqsl="Y", lotw="Y", source="hamqth")
    assert accepted_routes(r, "B") == ("Q", "L")


def test_accepted_routes_full_set_canonical_order():
    r = LookupResult(
        call="X", manager="OH2BH", accepts_direct="Y", eqsl="Y", lotw="Y", source="hamqth"
    )
    assert accepted_routes(r, "B") == ("B", "D", "Q", "L")


def test_accepted_routes_unknown_falls_back_to_default():
    r = LookupResult(call="X", accepts_bureau="?", accepts_direct="?", source="hamqth")
    assert accepted_routes(r, "B") == ("B",)
    assert accepted_routes(r, "D") == ("D",)


def test_accepted_routes_none_result_uses_default():
    assert accepted_routes(None, "B") == ("B",)
    assert accepted_routes(None, "D") == ("D",)


def test_accepted_routes_invalid_default_clamped_to_bureau():
    assert accepted_routes(None, "X") == ("B",)
    assert accepted_routes(None, "") == ("B",)


# -- extract_manager_callsign ---------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("DK1XY", "DK1XY"),
        ("dk1xy", "DK1XY"),  # klein → groß
        ("  OH2BH  ", "OH2BH"),  # getrimmt
        ("QSL via DK1XY direct", "DK1XY"),  # Rufzeichen aus Freitext
        ("M0OXO OQRS", "M0OXO"),  # OQRS-Manager
        ("DK1XY or DL2AB", "DK1XY"),  # mehrere → erstes
        ("DL2AB, DK1XY", "DL2AB"),  # Komma-getrennt → erstes
        ("dk1xy@example.com", "DK1XY"),  # E-Mail-Local-Part
        ("2E0ABC", "2E0ABC"),  # Präfix mit führender Ziffer
        ("DK1XY/P", "DK1XY/P"),  # Portabel-Kennung bleibt erhalten
        # Reiner Routing-/Rausch-Text ohne Rufzeichen → leer
        ("Bureau", ""),
        ("Direct", ""),
        ("DIRECT ONLY", ""),
        ("eQSL", ""),
        ("LoTW", ""),
        ("SASE", ""),
        ("OQRS", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_extract_manager_callsign(text, expected):
    assert extract_manager_callsign(text) == expected


# -- accepted_routes: Manager-Freitext ------------------------------------


def test_accepted_routes_freetext_manager_is_not_bureau():
    # „LoTW"-Freitext im Manager-Feld ist kein echtes Rufzeichen → kein Büro-Weg,
    # nur der LOTW-Weg zählt.
    r = LookupResult(call="X", manager="LoTW", lotw="Y", source="hamqth")
    assert accepted_routes(r, "B") == ("L",)


def test_accepted_routes_real_manager_callsign_is_bureau():
    r = LookupResult(call="X", manager="DK0XYZ", source="hamqth")
    assert accepted_routes(r, "B") == ("B",)


# -- resolve_route --------------------------------------------------------


def test_resolve_route_follows_priority_order():
    # Station akzeptiert Büro + eQSL; aktive Reihenfolge entscheidet.
    assert resolve_route(("B", "Q"), ["Q", "B"]) == "Q"
    assert resolve_route(("B", "Q"), ["B", "D", "Q"]) == "B"


def test_resolve_route_none_when_no_active_route_matches():
    # Nur LOTW akzeptiert, aber LOTW ist nicht aktiv -> nicht drucken.
    assert resolve_route(("L",), ["B", "D"]) is None


# -- normalize_via_priority / active_via_priority -------------------------


def test_normalize_via_priority_fills_and_dedupes():
    # Unbekanntes/Doppeltes raus, fehlende Codes kanonisch angehängt.
    assert normalize_via_priority(["Q", "Q", "X", "B"]) == ["Q", "B", "D", "L"]
    assert normalize_via_priority(None) == ["B", "D", "Q", "L"]


def test_active_via_priority_slices_at_cut():
    assert active_via_priority(["B", "D", "Q", "L"], 2) == ["B", "D"]
    assert active_via_priority(["Q", "L", "B", "D"], 1) == ["Q"]
    assert active_via_priority(["B", "D", "Q", "L"], 0) == []
    # Cut über die Länge hinaus wird geklemmt.
    assert active_via_priority(["B", "D", "Q", "L"], 99) == ["B", "D", "Q", "L"]


# -- lookup_calls ---------------------------------------------------------


def test_lookup_calls_dedupes_and_returns_map(tmp_path: Path):
    path = _seeded_cache(
        tmp_path,
        {"DL1ABC": LookupResult(call="DL1ABC", name="Hans", manager="OH2BH", source="hamqth")},
    )
    cfg = LookupConfig()  # keine Credentials → nur Cache
    progress: list[tuple[int, int]] = []
    results = lookup_calls(
        ["DL1ABC", "dl1abc", "XX0XXX"],
        cfg,
        cache_path=path,
        progress_cb=lambda d, t: progress.append((d, t)),
    )

    assert set(results) == {"DL1ABC", "XX0XXX"}  # dedupliziert, großgeschrieben
    assert results["DL1ABC"] is not None and results["DL1ABC"].manager == "OH2BH"
    assert results["XX0XXX"] is None  # nicht im Cache, keine Credentials
    assert progress[-1] == (2, 2)  # zwei eindeutige Rufzeichen


def test_lookup_calls_empty_input(tmp_path: Path):
    assert lookup_calls([], LookupConfig(), cache_path=tmp_path / "c.json") == {}
    assert lookup_calls(["", "   "], LookupConfig(), cache_path=tmp_path / "c.json") == {}


def test_lookup_calls_without_credentials_all_none(tmp_path: Path):
    results = lookup_calls(["DL1ABC", "DL2XYZ"], LookupConfig(), cache_path=tmp_path / "c.json")
    assert results == {"DL1ABC": None, "DL2XYZ": None}


# -- has_lookup_credentials ----------------------------------------------


def test_has_lookup_credentials():
    assert has_lookup_credentials(LookupConfig()) is False
    assert has_lookup_credentials(LookupConfig(hamqth_user="u", hamqth_pass="p")) is True
    assert has_lookup_credentials(LookupConfig(qrz_user="u", qrz_pass="p")) is True
    # unvollständig → False
    assert has_lookup_credentials(LookupConfig(hamqth_user="u")) is False


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
