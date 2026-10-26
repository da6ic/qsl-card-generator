"""Rufzeichen -> DXCC-Gebiet, ohne Datenbankabfrage (für den Most-Wanted-Filter).

Grundlage ist die `cty.dat` von AD1C (https://www.country-files.com/, MIT-
Lizenz, siehe `assets/dxcc/LICENSE-cty.txt`), die auch Contest-Logger wie
QARTest oder N1MM verwenden. Damit funktioniert der Filter auch für ein
Cabrillo-Log und ohne QRZ-/HamQTH-Zugangsdaten. Die Rangliste selbst kommt
weiterhin allein von der GDXF (`qslcards.mostwanted`).

Öffentliche API:
  - `CtyDatabase`, `Entity`, `location_part` (cty)
  - `load(stored, bundled, numbers)` — gespeicherte oder mitgelieferte Kopie
  - `refresh(stored, bundled, numbers, force=False)` — bei Bedarf neu abrufen
  - `is_stale(stored)` — ohne Netzzugriff
"""

from __future__ import annotations

from qslcards.dxcc.cty import CtyDatabase, Entity, location_part, parse_numbers
from qslcards.dxcc.store import MAX_AGE_DAYS, CtyRefreshResult, fetch_text, is_stale, load, refresh

__all__ = [
    "MAX_AGE_DAYS",
    "CtyDatabase",
    "CtyRefreshResult",
    "Entity",
    "fetch_text",
    "is_stale",
    "load",
    "location_part",
    "parse_numbers",
    "refresh",
]
