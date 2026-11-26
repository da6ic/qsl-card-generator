"""HTTP-Client für die Wavelog-API v2 (siehe Paket-Docstring).

Bewusst schlank: `requests` mit kurzer Zeitgrenze. Jeder Fehler wird zu einem
`WavelogError` mit einem Satz, den die Oberfläche so anzeigen kann, und dem
HTTP-Statuscode als Attribut (nicht als Text zum Durchsuchen).

Wiederholt wird nur eins: **429 Too Many Requests**. Die Doku nennt als
Beispiel 120 Anfragen/Minute für QSOs, und markiert wird mit einem PATCH je
QSO — ohne Warten liefen große Stapel sonst reihenweise in Fehler (Bewertung
2.1). Dazu hält `mark_many` einen kleinen Abstand zwischen den Anfragen.
"""

from __future__ import annotations

import ipaddress
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date as _date
from typing import Any
from urllib.parse import urlsplit

import requests

from qslcards.logbook.models import QSO

TIMEOUT_S = 20
PER_PAGE = 500  # Wavelog erlaubt bis 5000; 500 hält die Antworten handlich
WAVELOG_ID_KEY = "wavelog_id"  # Schlüssel in QSO.raw: Primärschlüssel in Wavelog
# Sicherung gegen eine Instanz, die `has_more` nie auf false setzt.
MAX_PAGES = 1000
# 429: so oft neu versuchen, höchstens so lange je Pause warten.
MAX_RETRIES_429 = 5
MAX_RETRY_WAIT_S = 90.0
DEFAULT_RETRY_WAIT_S = 10.0
# Abstand zwischen zwei PATCHes beim Markieren (120/min = 0,5 s).
MARK_INTERVAL_S = 0.5


class WavelogError(Exception):
    """Fehler beim Zugriff auf Wavelog, mit anzeigbarer Meldung.

    `status` ist der HTTP-Statuscode (None bei Netzfehlern), `code` der
    Fehlercode aus der Antwort, falls Wavelog einen liefert (z. B.
    `token_expired`).
    """

    def __init__(self, message: str, *, status: int | None = None, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code

    @property
    def auth_failed(self) -> bool:
        return self.status in (401, 403)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date(text: str) -> bool:
    """„JJJJ-MM-TT" und ein echtes Datum — oder leer (= keine Grenze)."""
    text = (text or "").strip()
    if not text:
        return True
    if not _DATE_RE.match(text):
        return False
    try:
        _date.fromisoformat(text)
    except ValueError:
        return False
    return True


def insecure_url_warning(url: str) -> str | None:
    """Warnung, wenn der Token unverschlüsselt über ein fremdes Netz ginge.

    `http://` auf localhost, einer privaten Adresse oder `*.local`/`*.lan` ist
    in Ordnung (Instanz im Heimnetz); alles andere ohne HTTPS nicht.
    """
    text = (url or "").strip()
    if not text or "://" not in text:
        return None  # ohne Schema wird https angenommen
    parts = urlsplit(text)
    if parts.scheme.lower() != "http":
        return None
    host = (parts.hostname or "").lower()
    if host in ("localhost",) or host.endswith((".local", ".lan", ".home.arpa", ".internal")):
        return None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local):
        return None
    return (
        "Die Adresse beginnt mit http:// — der API-Key geht damit unverschlüsselt "
        "über das Netz. Wenn möglich https:// verwenden."
    )


@dataclass(frozen=True)
class WavelogStation:
    """Ein Stationsstandort („Station Location") aus Wavelog."""

    id: int
    name: str
    callsign: str
    gridsquare: str = ""
    cq: str = ""
    itu: str = ""
    active: bool = False

    @property
    def label(self) -> str:
        """Text im Dropdown, z.B. „DL0MT · Home (JO62QM)"."""
        grid = f" ({self.gridsquare})" if self.gridsquare else ""
        star = " ★" if self.active else ""
        return f"{self.callsign} · {self.name}{grid}{star}"


@dataclass(frozen=True)
class PaperQslMark:
    """Ein QSO, das nach dem Druck als „Papier-QSL gesendet" markiert wird."""

    qso_id: str
    via: str | None = None  # "B" Büro, "D" direkt, "M" Manager, None = offen lassen


def normalize_base_url(url: str) -> str:
    """Basis-URL -> Präfix der API v2.

    Akzeptiert „log.example.com", „https://log.example.com/",
    „https://example.com/wavelog/index.php" usw. Ohne Schema wird https
    angenommen. Liefert z.B. „https://log.example.com/index.php/api/v2".
    """
    url = (url or "").strip()
    if not url:
        raise WavelogError("Bitte die Adresse der Wavelog-Instanz eingeben.")
    if "://" not in url:
        url = "https://" + url
    url = url.rstrip("/")
    for suffix in ("/api/v2", "/api"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    if not url.endswith("/index.php"):
        url += "/index.php"
    return url + "/api/v2"


def _without_index_php(api: str) -> str | None:
    """API-Präfix ohne `index.php/` — für Instanzen mit „schönen" URLs.

    Laut Wavelog-Doku ist `index.php` je nach Webserver optional; manche
    Instanzen liefern mit ihm 404.
    """
    marker = "/index.php/api/v2"
    if api.endswith(marker):
        return api[: -len(marker)] + "/api/v2"
    return None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _freq_mhz(value: Any) -> str | None:
    """Wavelog liefert die Frequenz in Hz; die Karte will MHz („14.074")."""
    try:
        hz = float(value)
    except (TypeError, ValueError):
        return None
    if hz <= 0:
        return None
    if hz < 1_000_000:  # sieht schon nach MHz/kHz aus -> unverändert
        return _text(value)
    return f"{hz / 1_000_000:.6f}".rstrip("0").rstrip(".")


def qso_from_json(item: dict[str, Any]) -> QSO | None:
    """Ein QSO-Objekt der API v2 -> `QSO`. Unbrauchbare Einträge -> None."""
    call = _text(item.get("call")).upper()
    stamp = _text(item.get("qso_date"))  # "YYYY-MM-DD HH:MM:SS"
    if not call or len(stamp) < 10:
        return None
    date = stamp[:10].replace("-", "")
    time = stamp[11:19].replace(":", "") if len(stamp) >= 16 else "0000"
    if not date.isdigit() or len(date) != 8:
        return None
    # Wie im ADIF-Import: der Submode (FT8, FT4 …) ist das, was auf die Karte gehört.
    mode = _text(item.get("submode")) or _text(item.get("mode")) or None
    raw = {str(k).lower(): _text(v) for k, v in item.items() if v is not None}
    raw[WAVELOG_ID_KEY] = _text(item.get("id"))
    dxcc = item.get("dxcc") if item.get("dxcc") not in (None, "", 0, "0") else None
    return QSO(
        call=call,
        qso_date=date,
        time_on=time or "0000",
        band=_text(item.get("band")).lower() or None,
        freq=_freq_mhz(item.get("freq")),
        mode=mode.upper() if mode else None,
        rst_sent=_text(item.get("rst_sent")) or None,
        rst_rcvd=_text(item.get("rst_rcvd")) or None,
        qsl_sent_via=_text(item.get("qsl_sent_via")) or None,
        qsl_via=_text(item.get("qsl_via")) or None,
        name=_text(item.get("name")) or None,
        gridsquare=_text(item.get("gridsquare")) or None,
        qth=_text(item.get("qth")) or None,
        country=_text(item.get("country")) or None,
        dxcc=_text(dxcc) or None,
        raw=raw,
    )


def paper_qsl_already_sent(qso: QSO) -> bool:
    """True, wenn Wavelog für das QSO schon „Papier-QSL gesendet" meldet.

    Nur verlässlich, wenn die Instanz das Feld `qsl_sent` mitliefert; fehlt es,
    hilft die lokale Liste der selbst markierten QSOs (`sent_store`).
    """
    return qso.raw.get("qsl_sent", "").upper() == "Y"


def reports_qsl_sent(qsos: list[QSO]) -> bool:
    """Liefert diese Wavelog-Instanz den Versandstatus überhaupt mit?"""
    return any("qsl_sent" in q.raw for q in qsos)


class WavelogClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.api = normalize_base_url(base_url)
        # Hat der Nutzer `index.php` nicht selbst getippt, darf der erste
        # Kontakt es bei 404 auch ohne versuchen (siehe `stations`).
        typed = (base_url or "").lower()
        self._api_fallback = None if "index.php" in typed else _without_index_php(self.api)
        self._sleep = sleep
        self._clock = clock
        token = (token or "").strip()
        if not token:
            raise WavelogError("Bitte den API-Key (Token) eingeben.")
        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "qslcards",
        }

    # ------------------------------------------------------------ intern
    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Eine Anfrage; bei 429 nach `retry_after` warten und wiederholen."""
        for attempt in range(MAX_RETRIES_429 + 1):
            response = self._send(method, path, **kwargs)
            if response.status_code != 429 or attempt == MAX_RETRIES_429:
                break
            self._sleep(_retry_after(response))
        return self._handle(response)

    def _send(self, method: str, path: str, **kwargs: Any):
        url = f"{self.api}/{path.lstrip('/')}"
        try:
            return self.session.request(
                method, url, headers=self.headers, timeout=TIMEOUT_S, **kwargs
            )
        except requests.RequestException as exc:
            # Kein `exc` im Text: die URL ist harmlos, aber der Header nicht immer.
            raise WavelogError(
                f"Wavelog nicht erreichbar ({type(exc).__name__}). Adresse und Netz prüfen."
            ) from exc

    def _handle(self, response) -> dict[str, Any]:
        status = response.status_code
        body: Any = None
        if status >= 400:
            try:
                body = response.json()
            except (ValueError, AttributeError):
                body = None
        code, detail = _error_details(body)
        if status == 401:
            if code == "token_expired" or "expired" in detail.lower():
                raise WavelogError(
                    "Der API-Key ist abgelaufen (401). Bitte in Wavelog einen neuen anlegen.",
                    status=status,
                    code=code or "token_expired",
                )
            raise WavelogError(
                "Wavelog hat den API-Key abgelehnt (401). Bitte prüfen.", status=status, code=code
            )
        if status == 403:
            raise WavelogError(
                "Dem API-Key fehlt eine Berechtigung (403). Nötig sind station:read, "
                "qso:read und zum Markieren qso:write.",
                status=status,
                code=code,
            )
        if status == 404:
            raise WavelogError(
                "Wavelog-API v2 nicht gefunden (404). Stimmt die Adresse? Die API v2 gibt "
                "es ab Wavelog 3.1, das Markieren als gesendet ab 3.2.5.",
                status=status,
                code=code,
            )
        if status == 429:
            raise WavelogError(
                "Wavelog bremst gerade (429, zu viele Anfragen). Bitte später erneut versuchen.",
                status=status,
                code=code,
            )
        if status >= 400:
            raise WavelogError(
                f"Wavelog meldet Fehler {status}" + (f": {detail}" if detail else "."),
                status=status,
                code=code,
            )
        if status == 204 or not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise WavelogError(
                "Wavelog hat kein JSON geliefert — ist die Adresse die der Instanz?",
                status=status,
            ) from exc
        if not isinstance(body, dict):
            return {"data": body}
        return body

    # ------------------------------------------------------------ öffentlich
    def stations(self) -> list[WavelogStation]:
        """Alle Stationsstandorte des Kontos.

        Der erste Kontakt: liefert die Adresse mit `index.php` 404, wird sie
        einmal ohne versucht und bei Erfolg für alle weiteren Anfragen behalten.
        """
        try:
            body = self._request("GET", "station")
        except WavelogError as exc:
            if exc.status != 404 or self._api_fallback is None:
                raise
            primary, self.api = self.api, self._api_fallback
            self._api_fallback = None
            try:
                body = self._request("GET", "station")
            except WavelogError:
                self.api = primary
                raise exc from None
        items = body.get("data", [])
        if isinstance(items, dict):  # vorsichtshalber: einzelnes Objekt
            items = [items]
        stations: list[WavelogStation] = []
        for item in items or []:
            if not isinstance(item, dict) or item.get("id") in (None, ""):
                continue
            try:
                sid = int(item["id"])
            except (TypeError, ValueError):
                continue
            stations.append(
                WavelogStation(
                    id=sid,
                    name=_text(item.get("name")) or f"Station {sid}",
                    callsign=_text(item.get("callsign")).upper(),
                    gridsquare=_text(item.get("gridsquare")).upper(),
                    cq=_text(item.get("cq")),
                    itu=_text(item.get("itu")),
                    active=bool(item.get("active")),
                )
            )
        stations.sort(key=lambda s: (not s.active, s.callsign, s.name))
        return stations

    def qsos(
        self,
        station_id: int,
        *,
        since: str = "",
        until: str = "",
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> list[QSO]:
        """Alle QSOs eines Standorts, älteste zuerst. `since`/`until`: „JJJJ-MM-TT"."""
        params: dict[str, Any] = {"station_id": station_id, "per_page": PER_PAGE, "page": 1}
        if since:
            params["qso_since"] = since
        if until:
            params["qso_until"] = until
        result: list[QSO] = []
        while params["page"] <= MAX_PAGES:
            body = self._request("GET", "qso", params=params)
            items = body.get("data") or []
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict):
                    qso = qso_from_json(item)
                    if qso is not None:
                        result.append(qso)
            meta = body.get("meta") or {}
            if progress_cb is not None:
                progress_cb(len(result), int(meta.get("total") or len(result)))
            if not meta.get("has_more") or not items:
                break
            total_pages = _int(meta.get("total_pages"))
            if total_pages and params["page"] >= total_pages:
                break  # `has_more` widerspricht `total_pages`: der Zahl glauben
            params["page"] += 1
        result.sort(key=lambda q: (q.qso_date, q.time_on, q.call))
        return result

    def mark_paper_sent(self, mark: PaperQslMark, date: str = "") -> None:
        """Setzt für ein QSO „Papier-QSL gesendet" (`qsl_sent = Y`)."""
        payload: dict[str, Any] = {"qsl_sent": "Y"}
        if mark.via:
            payload["qsl_sent_via"] = mark.via
        if date:
            payload["qslsdate"] = date
        try:
            self._request("PATCH", f"qso/{mark.qso_id}", json=payload)
        except WavelogError as exc:
            if exc.status in (400, 422):
                # Ältere Instanzen (3.1 bis 3.2.4) kennen die QSL-Felder im PATCH
                # nicht und antworten mit „unbekanntes Feld".
                raise WavelogError(
                    f"{exc} Hinweis: Markieren braucht Wavelog 3.2.5 oder neuer.",
                    status=exc.status,
                    code=exc.code,
                ) from exc
            raise

    def mark_many(
        self,
        marks: Iterable[PaperQslMark],
        *,
        date: str = "",
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Markiert mehrere QSOs. Liefert (IDs der markierten QSOs, Fehlermeldungen)."""
        marks = list(marks)
        done: list[str] = []
        errors: list[str] = []
        last = None
        for index, mark in enumerate(marks, start=1):
            if last is not None:
                wait = MARK_INTERVAL_S - (self._clock() - last)
                if wait > 0:
                    self._sleep(wait)
            last = self._clock()
            try:
                self.mark_paper_sent(mark, date)
                done.append(mark.qso_id)
            except WavelogError as exc:
                errors.append(f"QSO {mark.qso_id}: {exc}")
                if exc.auth_failed:
                    break  # Key falsch -> die übrigen scheitern genauso
            if progress_cb is not None:
                progress_cb(index, len(marks))
        return done, errors


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _error_details(body: Any) -> tuple[str, str]:
    """(Fehlercode, Meldung) aus einer Fehlerantwort, so gut es geht."""
    if not isinstance(body, dict):
        return "", ""
    error = body.get("error")
    if isinstance(error, dict):
        return _text(error.get("code")), _text(error.get("message"))
    return _text(body.get("code")), _text(body.get("message") or error)


def _retry_after(response) -> float:
    """Wartezeit nach 429: `error.details.retry_after`, sonst Header, sonst Standard."""
    seconds: float | None = None
    try:
        body = response.json()
    except (ValueError, AttributeError):
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        details = (error.get("details") if isinstance(error, dict) else None) or body.get("details")
        if isinstance(details, dict):
            try:
                seconds = float(details.get("retry_after"))
            except (TypeError, ValueError):
                seconds = None
    if seconds is None:
        headers = getattr(response, "headers", None) or {}
        try:
            seconds = float(headers.get("Retry-After"))
        except (TypeError, ValueError):
            seconds = None
    if seconds is None or seconds <= 0:
        seconds = DEFAULT_RETRY_WAIT_S
    return min(seconds, MAX_RETRY_WAIT_S)
