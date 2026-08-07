"""HamQTH-XML-Client (siehe docs/SPECIFICATION.md §6.1).

Ablauf:
  1. Session holen: `xml.php?u=USER&p=PASS` → `<session_id>` (≈1 h gültig).
  2. Abfrage: `xml.php?id=SESSION&callsign=CALL&prg=PROGRAM` → `<search>…`.
  3. Meldet die Antwort „Session does not exist or expired", wird **einmal**
     neu angemeldet und die Abfrage wiederholt.

Die HamQTH-Antwort steht im XML-Namespace `https://www.hamqth.com`; Tags werden
daher namespace-agnostisch gelesen (`{*}tag`).

Robustheit: Netz-, HTTP-, Parse- und Auth-Fehler werden abgefangen, geloggt und
als `None` zurückgegeben — sie dürfen die PDF-Erzeugung nie abbrechen.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from xml.etree import ElementTree as ET

import requests

from qslcards.lookup.base import LookupResult

logger = logging.getLogger(__name__)

BASE_URL = "https://www.hamqth.com/xml.php"
_EXPIRED_MARKERS = ("session does not exist", "session id is missing", "expired")


class HamQTHClient:
    def __init__(
        self,
        user: str,
        password: str,
        program_id: str = "qslcards",
        *,
        http: requests.Session | None = None,
        timeout: float = 10.0,
        on_auth_error: Callable[[str], None] | None = None,
    ) -> None:
        self._user = user
        self._password = password
        self._program_id = program_id or "qslcards"
        self._http = http if http is not None else requests.Session()
        self._timeout = timeout
        self._on_auth_error = on_auth_error
        self._session_id: str | None = None
        # Der Server hat die Anmeldung abgelehnt (fast immer: falsche
        # Zugangsdaten). Danach ist dieser Client für den Lauf unbrauchbar.
        self.auth_failed = False

    # -- öffentliches Interface -------------------------------------------

    def lookup(self, call: str) -> LookupResult | None:
        call = (call or "").strip().upper()
        if not call or not self._user or not self._password:
            return None
        try:
            return self._lookup(call, allow_reauth=True)
        except Exception as exc:  # nie fatal
            logger.warning("HamQTH-Lookup für %s fehlgeschlagen: %s", call, exc)
            return None

    # -- interne Helfer ----------------------------------------------------

    def _lookup(self, call: str, *, allow_reauth: bool) -> LookupResult | None:
        session_id = self._ensure_session()
        if session_id is None:
            return None

        root = self._get({"id": session_id, "callsign": call, "prg": self._program_id})
        if root is None:
            return None

        error = _find_text(root, "error")
        if error:
            if allow_reauth and _looks_expired(error):
                logger.info("HamQTH-Session abgelaufen, melde neu an.")
                self._session_id = None
                return self._lookup(call, allow_reauth=False)
            logger.warning("HamQTH meldet für %s: %s", call, error)
            return None

        search = root.find("{*}search")
        if search is None:
            return None
        return _parse_search(call, search)

    def _ensure_session(self) -> str | None:
        if self._session_id:
            return self._session_id
        if self.auth_failed:
            # Eine abgelehnte Anmeldung wird von allein nicht gültig: nicht für
            # jedes weitere Rufzeichen erneut anklopfen (schont die API und
            # macht den Lauf sofort fertig, statt N-mal ins Leere zu greifen).
            return None
        root = self._get({"u": self._user, "p": self._password})
        if root is None:
            return None
        session_id = _find_text(root, "session_id")
        if session_id:
            self._session_id = session_id
            return session_id
        self._fail_auth(_find_text(root, "error"))
        return None

    def _fail_auth(self, message: str | None) -> None:
        """Der Server hat die Anmeldung beantwortet und abgelehnt.

        Nur hier — ein Netzfehler wirft und landet in `lookup()`, der darf nicht
        als „falsches Passwort" durchgehen.
        """
        text = message or "unbekannter Fehler"
        logger.warning("HamQTH-Anmeldung fehlgeschlagen: %s", text)
        self.auth_failed = True
        if self._on_auth_error is not None:
            self._on_auth_error(text)

    def _get(self, params: dict[str, str]) -> ET.Element | None:
        resp = self._http.get(BASE_URL, params=params, timeout=self._timeout)
        resp.raise_for_status()
        return ET.fromstring(resp.text)


def _looks_expired(message: str) -> bool:
    low = message.lower()
    return any(marker in low for marker in _EXPIRED_MARKERS)


def _find_text(element: ET.Element, tag: str) -> str | None:
    """Text eines beliebig namespaced Kind-Tags (rekursiv), oder None."""
    found = element.find(f".//{{*}}{tag}")
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _parse_search(call: str, search: ET.Element) -> LookupResult:
    def field(tag: str) -> str | None:
        return _find_text(search, tag)

    def flag(tag: str) -> str | None:
        # Y/N/?-Flags auf Großbuchstaben normalisieren.
        value = field(tag)
        return value.upper() if value else None

    name = field("adr_name") or field("nick")
    country = field("adr_country") or field("country")
    return LookupResult(
        call=field("callsign") or call,
        name=name,
        street=field("adr_street1"),
        zip=field("adr_zip"),
        city=field("adr_city"),
        country=country,
        grid=field("grid"),
        manager=field("qsl_via"),
        accepts_bureau=flag("qsl"),
        accepts_direct=flag("qsldirect"),
        lotw=flag("lotw"),
        eqsl=flag("eqsl"),
        source="hamqth",
    )
