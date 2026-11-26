"""Zugangsdaten dürfen nie im Protokoll landen (Bewertung 1.1)."""

from __future__ import annotations

import logging

import requests

from qslcards.lookup.hamqth import HamQTHClient
from qslcards.lookup.qrz import QRZClient
from qslcards.redact import RedactingFilter, describe_error, redact

SECRET = "GEHEIM&12 3"


def _unreachable_session() -> requests.Session:
    """Echte requests-Session gegen einen Port, auf dem niemand lauscht.

    So entsteht genau die Meldung aus der Praxis („Max retries exceeded with
    url: …?u=…&p=…"), statt einer selbst ausgedachten.
    """
    http = requests.Session()
    real_get = http.get

    def get(url, params=None, timeout=None, **kw):
        url = url.replace("https://www.hamqth.com", "http://127.0.0.1:9")
        url = url.replace("https://xmldata.qrz.com", "http://127.0.0.1:9")
        return real_get(url, params=params, timeout=0.5, **kw)

    http.get = get  # type: ignore[method-assign]
    return http


def test_hamqth_network_error_does_not_log_password(caplog):
    client = HamQTHClient("DL1ABC", SECRET, http=_unreachable_session())
    with caplog.at_level(logging.WARNING):
        assert client.lookup("DL2XYZ") is None
    text = caplog.text
    assert "fehlgeschlagen" in text
    assert "GEHEIM" not in text
    assert "p=***" in text or "127.0.0.1" in text


def test_qrz_network_error_does_not_log_password(caplog):
    client = QRZClient("DL1ABC", SECRET, http=_unreachable_session())
    with caplog.at_level(logging.WARNING):
        assert client.lookup("DL2XYZ") is None
    assert "fehlgeschlagen" in caplog.text
    assert "GEHEIM" not in caplog.text


def test_redact_masks_known_secret_raw_and_encoded():
    text = "url: /xml.php?u=DL1ABC&p=GEHEIM%2612+3 und GEHEIM&12 3"
    out = redact(text, SECRET)
    assert "GEHEIM" not in out
    assert "u=DL1ABC" in out  # Benutzername bleibt lesbar


def test_redact_masks_password_params_without_known_secret():
    out = redact("?username=dl1abc;password=xyz;agent=qslcards1.0 and ?u=a&p=hunter2")
    assert "xyz" not in out and "hunter2" not in out
    assert "agent=qslcards1.0" in out


def test_redact_masks_wavelog_token():
    out = redact("Authorization: Bearer wl2_abcDEF123")
    assert "wl2_abc" not in out


def test_describe_error_has_type_name():
    assert describe_error(ValueError("p=x")).startswith("ValueError: p=***")


def test_redacting_filter_cleans_args_and_exception(caplog):
    logger = logging.getLogger("qslcards.test.redact")
    record = logger.makeRecord(
        logger.name, logging.WARNING, __file__, 1, "fehler: %s", ("?p=hunter2",), None
    )
    assert RedactingFilter().filter(record)
    assert record.getMessage() == "fehler: ?p=***"
    try:
        raise RuntimeError("password=hunter2")
    except RuntimeError:
        import sys

        rec2 = logger.makeRecord(logger.name, logging.ERROR, __file__, 1, "x", None, sys.exc_info())
    RedactingFilter().filter(rec2)
    assert "hunter2" not in rec2.exc_text
