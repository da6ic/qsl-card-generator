"""Lokaler JSON-Cache für Lookups (siehe docs/SPECIFICATION.md §6.5).

Speichert positive **und** negative Ergebnisse, damit API-Limits geschont
werden und dieselbe Abfrage nicht wiederholt ins Netz geht. Optional altern
Einträge nach `max_age_days` (Default 180 Tage), danach gelten sie als Miss.

Dateiformat (`lookup_cache.json`):

    {
      "CALL": {
        "result": { ...LookupResult-Felder... },
        "queried_at": "2026-07-23T12:34:56+00:00"
      },
      ...
    }

Disk-Fehler sind nicht fatal: schlägt Laden/Schreiben fehl, arbeitet der Cache
in-memory weiter und loggt eine Warnung.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from qslcards.lookup.base import LookupResult

logger = logging.getLogger(__name__)


class LookupCache:
    def __init__(
        self,
        path: str | Path,
        max_age_days: int | None = 180,
    ) -> None:
        self._path = Path(path)
        self._max_age_days = max_age_days
        self._entries: dict[str, dict] = {}
        self._load()

    # -- Persistenz --------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._entries = {str(k).upper(): v for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, ValueError) as exc:
            logger.warning("Cache konnte nicht geladen werden (%s): %s", self._path, exc)
            self._entries = {}

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Cache konnte nicht gespeichert werden (%s): %s", self._path, exc)

    # -- Zugriff -----------------------------------------------------------

    def get(self, call: str) -> LookupResult | None:
        """Liefert den gecachten Eintrag oder `None` (nicht/abgelaufen).

        Ein negatives Ergebnis liegt als leerer `LookupResult` (source="none")
        vor; `None` bedeutet ausschließlich „nicht im Cache".
        """
        entry = self._entries.get((call or "").strip().upper())
        if entry is None:
            return None
        if self._is_expired(entry):
            return None
        data = entry.get("result")
        if not isinstance(data, dict):
            return None
        result = LookupResult.from_dict(data)
        # Herkunft für positive Treffer auf „cache" umstellen, damit der
        # Aufrufer sieht, dass kein frischer Call erfolgt ist.
        if not result.is_empty():
            result.source = "cache"
        return result

    def set(self, call: str, result: LookupResult) -> None:
        self._entries[(call or "").strip().upper()] = {
            "result": result.to_dict(),
            "queried_at": datetime.now(UTC).isoformat(),
        }
        self.save()

    def __contains__(self, call: str) -> bool:
        return self.get(call) is not None

    def _is_expired(self, entry: dict) -> bool:
        if self._max_age_days is None:
            return False
        stamp = entry.get("queried_at")
        if not isinstance(stamp, str):
            return False
        try:
            queried_at = datetime.fromisoformat(stamp)
        except ValueError:
            return False
        if queried_at.tzinfo is None:
            queried_at = queried_at.replace(tzinfo=UTC)
        age = datetime.now(UTC) - queried_at
        return age.days > self._max_age_days
