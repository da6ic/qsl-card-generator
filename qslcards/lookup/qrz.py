"""QRZ-XML-Client (erste Wahl, best effort; siehe docs/SPECIFICATION.md §6.3).

Ablauf:
  1. Session: `xml/current/?username=U;password=P;agent=…` → `<Key>`.
  2. Abfrage: `xml/current/?s=KEY;callsign=CALL` → `<Callsign>…`.
  3. Bei „Session Timeout"/„Invalid session key" wird **einmal** neu angemeldet.

QRZ trennt Query-Parameter traditionell mit `;` (nicht `&`); die URL wird daher
von Hand zusammengesetzt. Die Antwort steht im Namespace `http://xmldata.qrz.com`
und wird namespace-agnostisch gelesen (`{*}tag`).

Ohne bezahltes XML-Abo liefert QRZ oft nur eingeschränkte/leere Adressfelder →
als „best effort" behandeln. Alle Fehler (Netz, HTTP, Parse, Auth) werden
abgefangen, geloggt und als `None` zurückgegeben.

QRZ ist die **erste** Wahl der Kette, kennt aber keine Zustellweg-Flags: die
holt `ChainedLookup` anschließend bei HamQTH nach (§6.2a).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

from qslcards.lookup.base import LookupResult, normalize_dxcc
from qslcards.redact import describe_error

logger = logging.getLogger(__name__)

BASE_URL = "https://xmldata.qrz.com/xml/current/"
AGENT = "qslcards1.0"
_EXPIRED_MARKERS = ("session timeout", "invalid session", "session does not exist")


class QRZClient:
    def __init__(
        self,
        user: str,
        password: str,
        *,
        http: requests.Session | None = None,
        timeout: float = 10.0,
        on_auth_error: Callable[[str], None] | None = None,
    ) -> None:
        self._user = user
        self._password = password
        self._http = http if http is not None else requests.Session()
        self._timeout = timeout
        self._on_auth_error = on_auth_error
        self._session_key: str | None = None
        # Anmeldung vom Server abgelehnt -> Client für diesen Lauf unbrauchbar.
        self.auth_failed = False

    # -- öffentliches Interface -------------------------------------------

    def lookup(self, call: str) -> LookupResult | None:
        call = (call or "").strip().upper()
        if not call or not self._user or not self._password:
            return None
        try:
            return self._lookup(call, allow_reauth=True)
        except Exception as exc:  # nie fatal
            # Die URL in der Meldung trägt `password=…` (siehe qslcards.redact).
            logger.warning(
                "QRZ-Lookup für %s fehlgeschlagen: %s",
                call,
                describe_error(exc, self._password, self._session_key),
            )
            return None

    # -- interne Helfer ----------------------------------------------------

    def _lookup(self, call: str, *, allow_reauth: bool) -> LookupResult | None:
        key = self._ensure_session()
        if key is None:
            return None

        root = self._get(f"s={quote_plus(key)};callsign={quote_plus(call)}")
        if root is None:
            return None

        error = _session_error(root)
        if error:
            if allow_reauth and _looks_expired(error):
                logger.info("QRZ-Session abgelaufen, melde neu an.")
                self._session_key = None
                return self._lookup(call, allow_reauth=False)
            # „Not found" u. Ä. sind reguläre Nicht-Treffer, kein Fehler.
            logger.info("QRZ meldet für %s: %s", call, error)
            return None

        callsign = root.find("{*}Callsign")
        if callsign is None:
            return None
        return _parse_callsign(call, callsign)

    def _ensure_session(self) -> str | None:
        if self._session_key:
            return self._session_key
        if self.auth_failed:
            # Abgelehnte Anmeldung nicht für jedes weitere Rufzeichen wiederholen.
            return None
        root = self._get(
            f"username={quote_plus(self._user)};"
            f"password={quote_plus(self._password)};agent={AGENT}"
        )
        if root is None:
            return None
        key = _find_text(root, "Key")
        if key:
            self._session_key = key
            return key
        self._fail_auth(_session_error(root))
        return None

    def _fail_auth(self, message: str | None) -> None:
        """Der Server hat die Anmeldung beantwortet und abgelehnt (siehe HamQTH)."""
        text = message or "unbekannter Fehler"
        logger.warning("QRZ-Anmeldung fehlgeschlagen: %s", text)
        self.auth_failed = True
        if self._on_auth_error is not None:
            self._on_auth_error(text)

    def _get(self, query: str) -> ET.Element | None:
        resp = self._http.get(f"{BASE_URL}?{query}", timeout=self._timeout)
        resp.raise_for_status()
        return ET.fromstring(resp.text)


def _looks_expired(message: str) -> bool:
    low = message.lower()
    return any(marker in low for marker in _EXPIRED_MARKERS)


def _session_error(root: ET.Element) -> str | None:
    session = root.find("{*}Session")
    if session is None:
        return None
    return _find_text(session, "Error")


def _find_text(element: ET.Element, tag: str) -> str | None:
    found = element.find(f".//{{*}}{tag}")
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _parse_callsign(call: str, node: ET.Element) -> LookupResult:
    def field(tag: str) -> str | None:
        return _find_text(node, tag)

    name = field("name_fmt")
    if not name:
        parts = [p for p in (field("fname"), field("name")) if p]
        name = " ".join(parts) or None

    return LookupResult(
        call=field("call") or call,
        name=name,
        street=field("addr1"),
        zip=field("zip"),
        city=field("addr2"),
        country=field("country"),
        grid=field("grid"),
        manager=field("qslmgr"),
        # `dxcc` ist das Gebiet des Rufzeichens; `ccode`/`country` beziehen sich
        # auf die Postanschrift. Ohne Abo fehlt es evtl. — dann füllt HamQTH.
        dxcc=normalize_dxcc(field("dxcc")),
        # QRZ liefert keine zuverlässigen Büro/Direkt/LoTW/eQSL-Flags → None.
        source="qrz",
    )
