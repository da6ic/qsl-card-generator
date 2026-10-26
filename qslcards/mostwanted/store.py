"""Gespeicherte Rangliste (`mostwanted.json`) und die Regel fürs Neuladen.

Die GDXF aktualisiert ihre Liste einmal im Jahr. Abgerufen wird deshalb nur,
wenn die gespeicherte Kopie fehlt oder älter als `MAX_AGE_DAYS` ist — und auch
dann nur, wenn der Filter eingeschaltet ist (entscheidet die GUI). Schlägt der
Abruf fehl, gilt die alte Kopie weiter; Netzfehler sind nie fatal.

Dateiformat:

    {
      "format": 1,
      "year": 2025,
      "updated": "May 3, 2026",
      "fetched_at": "2026-10-26T18:00:00+00:00",
      "rankings": {"mixed": [{"dxcc": 344, "rank": 1, "prefix": "P5",
                              "name": "DPRK (North Korea)", "needed_pct": 96.4}, …],
                   "cw": […], "phone": […], "digital": […]}
    }

Ein anderes `format` oder eine kaputte Datei zählt als „nicht vorhanden" —
die Datei gehört allein dem Programm und wird beim nächsten Abruf neu
geschrieben.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .gdxf import fetch_html, parse_html
from .models import MostWantedList, RankedEntity

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
# Ab diesem Alter wird beim Einschalten des Filters neu abgerufen.
MAX_AGE_DAYS = 30


@dataclass
class RefreshResult:
    """Ergebnis von `refresh`: die gültige Liste (oder None) und ggf. der Fehler.

    `error` ist gesetzt, wenn ein Abruf nötig war und scheiterte — `ranking`
    ist dann die ältere gespeicherte Kopie, falls es eine gibt.
    """

    ranking: MostWantedList | None
    error: str | None = None
    fetched: bool = False  # True = frisch aus dem Netz geholt


def load(path: str | Path) -> MostWantedList | None:
    """Liest die gespeicherte Liste; fehlt sie oder ist sie unlesbar -> None."""
    file = Path(path)
    if not file.exists():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("format") != FORMAT_VERSION:
            return None
        rankings = {
            category: {entry.dxcc: entry for entry in (RankedEntity(**row) for row in rows)}
            for category, rows in data["rankings"].items()
        }
        ranking = MostWantedList(
            year=data.get("year"),
            rankings=rankings,
            updated=data.get("updated"),
            fetched_at=data.get("fetched_at"),
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        logger.warning("Most-Wanted-Liste nicht lesbar (%s): %s", file, exc)
        return None
    return None if ranking.is_empty() else ranking


def save(ranking: MostWantedList, path: str | Path) -> None:
    """Schreibt die Liste. Fehler werden geloggt, nicht geworfen."""
    data = {
        "format": FORMAT_VERSION,
        "year": ranking.year,
        "updated": ranking.updated,
        "fetched_at": ranking.fetched_at,
        "rankings": {
            category: [asdict(entry) for entry in sorted(entries.values(), key=_by_rank)]
            for category, entries in ranking.rankings.items()
        },
    }
    file = Path(path)
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        logger.warning("Most-Wanted-Liste nicht gespeichert (%s): %s", file, exc)


def is_stale(
    ranking: MostWantedList | None, *, now: datetime | None = None, max_age_days: int = MAX_AGE_DAYS
) -> bool:
    """True, wenn neu abgerufen werden sollte (keine Liste, kein/kaputter
    Zeitstempel oder älter als `max_age_days`)."""
    if ranking is None or not ranking.fetched_at:
        return True
    try:
        fetched = datetime.fromisoformat(ranking.fetched_at)
    except ValueError:
        return True
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)
    return (now or datetime.now(UTC)) - fetched > timedelta(days=max_age_days)


def refresh(
    path: str | Path,
    *,
    force: bool = False,
    now: datetime | None = None,
    fetch: Callable[[], str] = fetch_html,
) -> RefreshResult:
    """Gespeicherte Liste liefern und bei Bedarf neu abrufen.

    Ist die Kopie frisch (und kein `force`), passiert kein Netzzugriff. Sonst
    wird abgerufen, gelesen und gespeichert. Jeder Fehler (Netz, HTTP,
    geändertes Layout) landet in `error`; die alte Kopie bleibt dann gültig.
    Läuft im Hintergrund-Thread der GUI — keine Tk-Aufrufe hier.
    """
    cached = load(path)
    if not force and not is_stale(cached, now=now):
        return RefreshResult(cached)
    try:
        ranking = parse_html(fetch())
    except Exception as exc:  # nie fatal: Netz-, HTTP- und Formatfehler
        logger.warning("GDXF-Most-Wanted-Liste nicht abrufbar: %s", exc)
        return RefreshResult(cached, error=str(exc) or type(exc).__name__)
    ranking = replace(ranking, fetched_at=(now or datetime.now(UTC)).isoformat())
    save(ranking, path)
    return RefreshResult(ranking, fetched=True)


def _by_rank(entry: RankedEntity) -> int:
    return entry.rank
