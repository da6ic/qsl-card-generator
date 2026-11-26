"""HTTP-Client für die Wavelog-API v2 (siehe Paket-Docstring).

Bewusst schlank: `requests` mit kurzer Zeitgrenze, keine Wiederholungen. Jeder
Fehler wird zu einem `WavelogError` mit einem Satz, den die Oberfläche so
anzeigen kann.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import requests

from qslcards.logbook.models import QSO

TIMEOUT_S = 20
PER_PAGE = 500  # Wavelog erlaubt bis 5000; 500 hält die Antworten handlich
WAVELOG_ID_KEY = "wavelog_id"  # Schlüssel in QSO.raw: Primärschlüssel in Wavelog


class WavelogError(Exception):
    """Fehler beim Zugriff auf Wavelog, mit anzeigbarer Meldung."""


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
    gilt das QSO als offen.
    """
    return qso.raw.get("qsl_sent", "").upper() == "Y"


class WavelogClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        session: requests.Session | None = None,
    ) -> None:
        self.api = normalize_base_url(base_url)
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
        url = f"{self.api}/{path.lstrip('/')}"
        try:
            response = self.session.request(
                method, url, headers=self.headers, timeout=TIMEOUT_S, **kwargs
            )
        except requests.RequestException as exc:
            raise WavelogError(f"Wavelog nicht erreichbar: {exc}") from exc
        if response.status_code == 401:
            raise WavelogError("Wavelog hat den API-Key abgelehnt (401). Bitte prüfen.")
        if response.status_code == 403:
            raise WavelogError(
                "Dem API-Key fehlt eine Berechtigung (403). Nötig sind station:read, "
                "qso:read und zum Markieren qso:write."
            )
        if response.status_code == 404:
            raise WavelogError(
                "Wavelog-API v2 nicht gefunden (404). Stimmt die Adresse? "
                "Benötigt wird Wavelog 3.2.5 oder neuer."
            )
        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                detail = _text(
                    body.get("error", {}).get("message")
                    if isinstance(body.get("error"), dict)
                    else body.get("message") or body.get("error")
                )
            except (ValueError, AttributeError):
                pass
            raise WavelogError(
                f"Wavelog meldet Fehler {response.status_code}" + (f": {detail}" if detail else ".")
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            body = response.json()
        except ValueError as exc:
            raise WavelogError(
                "Wavelog hat kein JSON geliefert — ist die Adresse die der Instanz?"
            ) from exc
        if not isinstance(body, dict):
            return {"data": body}
        return body

    # ------------------------------------------------------------ öffentlich
    def stations(self) -> list[WavelogStation]:
        """Alle Stationsstandorte des Kontos."""
        body = self._request("GET", "station")
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
        while True:
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
        self._request("PATCH", f"qso/{mark.qso_id}", json=payload)

    def mark_many(
        self,
        marks: Iterable[PaperQslMark],
        *,
        date: str = "",
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> tuple[int, list[str]]:
        """Markiert mehrere QSOs. Liefert (Anzahl erfolgreich, Fehlermeldungen)."""
        marks = list(marks)
        done, errors = 0, []
        for index, mark in enumerate(marks, start=1):
            try:
                self.mark_paper_sent(mark, date)
                done += 1
            except WavelogError as exc:
                errors.append(f"QSO {mark.qso_id}: {exc}")
                if "401" in str(exc) or "403" in str(exc):
                    break  # Key falsch -> die übrigen scheitern genauso
            if progress_cb is not None:
                progress_cb(index, len(marks))
        return done, errors
