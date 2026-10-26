"""`cty.dat` laden und bei Bedarf bei AD1C neu abrufen.

Drei Stufen, damit der Most-Wanted-Filter auch ohne Netz sofort funktioniert:
  1. die zuletzt abgerufene Kopie im Datenordner (`paths.cty_path`),
  2. sonst die mit dem Programm ausgelieferte (`paths.bundled_cty_path`),
  3. neu abgerufen wird, wenn die Kopie im Datenordner fehlt oder älter als
     `MAX_AGE_DAYS` ist — AD1C veröffentlicht etwa alle 2–4 Wochen eine neue
     Fassung, vor allem wegen neuer DXpeditions-Rufzeichen.

Ein Abruf zählt nur, wenn er sich als `cty.dat` lesen lässt (Versionsvermerk
und genügend Präfixe) — eine Fehlerseite des Servers überschreibt so nie eine
gute Kopie. Netzfehler sind nie fatal.

Die Datei ist ASCII/Latin-1 und wird deshalb als Latin-1 gelesen: so bleibt
jedes Byte erhalten, egal was darin steht.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from qslcards import __app_name__, __version__

from .cty import CtyDatabase

logger = logging.getLogger(__name__)

URL = "https://www.country-files.com/cty/cty.dat"
TIMEOUT_S = 20.0
USER_AGENT = f"{__app_name__}/{__version__}"
MAX_AGE_DAYS = 14
ENCODING = "latin-1"
# So wenige Präfixe hat keine echte cty.dat (die aktuelle hat ~4800).
_MIN_PREFIXES = 1000


@dataclass
class CtyRefreshResult:
    """Die gültige Datenbank (oder None) und ggf. der Fehler des Abrufs."""

    database: CtyDatabase | None
    error: str | None = None
    fetched: bool = False


def fetch_text(*, http: requests.Session | None = None, timeout: float = TIMEOUT_S) -> str:
    """Holt die aktuelle `cty.dat`. Fehler werden weitergereicht (siehe `refresh`)."""
    session = http if http is not None else requests.Session()
    response = session.get(URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    return response.content.decode(ENCODING)


def load(stored: str | Path, bundled: str | Path, numbers: str | Path) -> CtyDatabase | None:
    """Gespeicherte Kopie, sonst die mitgelieferte; None, wenn keine lesbar ist."""
    try:
        numbers_text = Path(numbers).read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("DXCC-Nummerntabelle nicht lesbar (%s): %s", numbers, exc)
        return None
    for path in (Path(stored), Path(bundled)):
        database = _read(path, numbers_text)
        if database is not None:
            return database
    return None


def is_stale(
    stored: str | Path, *, now: datetime | None = None, max_age_days: int = MAX_AGE_DAYS
) -> bool:
    """True, wenn die Kopie im Datenordner fehlt oder älter als `max_age_days` ist.

    Gemessen am Dateidatum: es ist der Zeitpunkt des letzten Abrufs. Die
    mitgelieferte Kopie zählt hier nicht — sie ist der Rückfall, kein Stand.
    """
    try:
        mtime = datetime.fromtimestamp(Path(stored).stat().st_mtime, UTC)
    except OSError:
        return True
    return (now or datetime.now(UTC)) - mtime > timedelta(days=max_age_days)


def refresh(
    stored: str | Path,
    bundled: str | Path,
    numbers: str | Path,
    *,
    force: bool = False,
    now: datetime | None = None,
    fetch: Callable[[], str] = fetch_text,
) -> CtyRefreshResult:
    """Datenbank liefern und bei Bedarf neu abrufen (im Hintergrund-Thread).

    Ohne Bedarf (frische Kopie, kein `force`) kein Netzzugriff. Scheitert der
    Abruf oder ist das Ergebnis keine `cty.dat`, gilt die vorhandene Kopie und
    der Grund steht in `error`.
    """
    current = load(stored, bundled, numbers)
    if not force and not is_stale(stored, now=now):
        return CtyRefreshResult(current)
    try:
        text = fetch()
        database = CtyDatabase(text, Path(numbers).read_text(encoding="utf-8"))
        if not _looks_valid(database):
            raise ValueError("Antwort ist keine cty.dat")
        target = Path(stored)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode(ENCODING))
    except Exception as exc:  # nie fatal: Netz-, HTTP-, Format- und Schreibfehler
        logger.warning("cty.dat nicht abrufbar, nehme die vorhandene Kopie: %s", exc)
        return CtyRefreshResult(current, error=str(exc) or type(exc).__name__)
    return CtyRefreshResult(database, fetched=True)


def _read(path: Path, numbers_text: str) -> CtyDatabase | None:
    if not path.is_file():
        return None
    try:
        database = CtyDatabase(path.read_bytes().decode(ENCODING), numbers_text)
    except OSError as exc:
        logger.warning("cty.dat nicht lesbar (%s): %s", path, exc)
        return None
    return database if _looks_valid(database) else None


def _looks_valid(database: CtyDatabase) -> bool:
    return bool(database.version) and len(database) >= _MIN_PREFIXES
