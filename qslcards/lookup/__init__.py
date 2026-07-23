"""Lookups für QSL-Empfänger: Versandart (Via) + Manager + Adresse (§6).

Öffentliche API:
  - `LookupResult`, `LookupProvider`, `ChainedLookup` (base)
  - `HamQTHClient`, `QRZClient`, `LookupCache`
  - `build_lookup(config, cache_path)` — Cache + Provider → `ChainedLookup`.
  - `has_lookup_credentials(config)` — sind HamQTH- oder QRZ-Zugangsdaten gesetzt?
  - `lookup_calls(calls, config, ...)` — schlägt alle (eindeutigen) Rufzeichen
    nach und liefert eine Map `CALL -> LookupResult | None`.
  - `derive_via(result, default_via)` — Versandart aus dem Lookup (M>B>D>E).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from qslcards.lookup.base import ChainedLookup, LookupProvider, LookupResult
from qslcards.lookup.cache import LookupCache
from qslcards.lookup.hamqth import HamQTHClient
from qslcards.lookup.qrz import QRZClient

if TYPE_CHECKING:
    from qslcards.config import LookupConfig

logger = logging.getLogger(__name__)

__all__ = [
    "LookupResult",
    "LookupProvider",
    "ChainedLookup",
    "LookupCache",
    "HamQTHClient",
    "QRZClient",
    "build_lookup",
    "has_lookup_credentials",
    "lookup_calls",
    "derive_via",
]

DEFAULT_CACHE_PATH = "lookup_cache.json"

# Gültige Versandart-Codes (E = Elektronisch = Ausschluss, kein Druckweg).
VIA_CODES = ("B", "D", "M", "E")


def has_lookup_credentials(config: LookupConfig) -> bool:
    """True, wenn HamQTH- **oder** QRZ-Zugangsdaten vollständig gesetzt sind."""
    return bool(
        (config.hamqth_user and config.hamqth_pass) or (config.qrz_user and config.qrz_pass)
    )


def build_lookup(
    config: LookupConfig,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
) -> ChainedLookup:
    """Baut die Lookup-Fassade: HamQTH zuerst, QRZ als Fallback, mit JSON-Cache.

    Nur Provider mit Credentials werden eingehängt. Fehlen alle, bleibt eine
    reine Cache-Fassade übrig (liefert nur bereits gecachte Treffer).
    """
    providers: list[LookupProvider] = []
    if config.hamqth_user and config.hamqth_pass:
        providers.append(
            HamQTHClient(
                config.hamqth_user,
                config.hamqth_pass,
                config.program_id,
            )
        )
    if config.qrz_user and config.qrz_pass:
        providers.append(QRZClient(config.qrz_user, config.qrz_pass))

    cache = LookupCache(cache_path)
    return ChainedLookup(providers, cache=cache)


def derive_via(result: LookupResult | None, default_via: str = "B") -> str:
    """Bestimmt die Versandart aus einem Lookup-Ergebnis (§6.2).

    Feste Priorität **M > B > D > E** (Ham-Standard: Manager hat Vorrang;
    Elektronisch schließt nur aus, wenn kein Papierweg vorhanden ist):
      1. Manager vorhanden            → "M"
      2. Büro akzeptiert (`qsl=Y`)    → "B"
      3. Direkt akzeptiert (`qsldirect=Y`) → "D"
      4. LoTW/eQSL (`lotw`/`eqsl` = Y) → "E" (angezeigt, aber nicht gedruckt)
      5. sonst (nichts/„?"/kein Treffer) → `default_via`

    `E` ist **kein** Druckweg, sondern eine Ausschluss-Kategorie.
    """
    default = (default_via or "B").upper()
    if default not in VIA_CODES:
        default = "B"
    if result is None:
        return default
    if result.manager:
        return "M"
    if result.accepts_bureau == "Y":
        return "B"
    if result.accepts_direct == "Y":
        return "D"
    if result.lotw == "Y" or result.eqsl == "Y":
        return "E"
    return default


def lookup_calls(
    calls: Iterable[str],
    config: LookupConfig,
    *,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    force: bool = False,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, LookupResult | None]:
    """Schlägt alle (eindeutigen) Rufzeichen nach → Map `CALL -> LookupResult|None`.

    Jedes Rufzeichen wird höchstens einmal abgefragt; der Cache schont zusätzlich
    API-Limits über Läufe hinweg. Mit `force=True` wird der Cache übersprungen
    (z. B. um nach einem Abbruch fehlende Stationen erneut zu holen).

    Netz-/Auth-Fehler sind **nie** fatal: sie werden geloggt, das Ergebnis ist
    dann `None` (→ `derive_via` fällt auf `default_via`). `progress_cb(done,
    total)` wird nach jedem abgefragten Rufzeichen aufgerufen.
    """
    unique: list[str] = []
    seen: set[str] = set()
    for raw in calls:
        call = (raw or "").strip().upper()
        if call and call not in seen:
            seen.add(call)
            unique.append(call)

    results: dict[str, LookupResult | None] = {}
    if not unique:
        return results

    try:
        lookup = build_lookup(config, cache_path)
    except Exception as exc:  # nie fatal
        logger.warning("Lookup konnte nicht initialisiert werden: %s", exc)
        return {call: None for call in unique}

    total = len(unique)
    for done, call in enumerate(unique, start=1):
        try:
            results[call] = lookup.lookup(call, force=force)
        except Exception as exc:  # defensiv; lookup() fängt eigentlich alles ab
            logger.warning("Lookup für %s fehlgeschlagen: %s", call, exc)
            results[call] = None
        if progress_cb is not None:
            progress_cb(done, total)

    return results
