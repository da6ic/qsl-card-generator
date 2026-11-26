"""Prüfskript für die echte Instanz (1.5) — hier gegen den Mock."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import mock_wavelog  # noqa: E402
import wavelog_check  # noqa: E402


def _no_proxy_session():
    session = requests.Session()
    session.trust_env = False  # lokaler Mock, nie über einen Proxy
    return session


def test_check_reports_fields_and_marks_only_after_yes():
    server = mock_wavelog.start(0)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        lines: list[str] = []
        report = wavelog_check.run(
            url,
            mock_wavelog.TOKEN,
            station_id=1,
            mark_one="4001",
            confirm=lambda _p: "n",
            out=lines.append,
            session=_no_proxy_session(),
        )
        assert report["stations"] == 2
        assert report["qsl_sent"] is True
        assert "call" in report["fields"]
        assert report["example"]["call"] == "…"  # anonymisiert
        assert "marked" not in report and not mock_wavelog.PATCHES

        report = wavelog_check.run(
            url,
            mock_wavelog.TOKEN,
            station_id=1,
            mark_one="4001",
            confirm=lambda _p: "j",
            out=lines.append,
            session=_no_proxy_session(),
        )
        assert report["marked"] == "4001"
        assert mock_wavelog.PATCHES[-1] == (4001, {"qsl_sent": "Y", "qsl_sent_via": "B"})
    finally:
        server.shutdown()
