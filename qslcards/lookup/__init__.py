"""Lookups für QSL-Empfänger: Versandart (Via) + Manager + Adresse (§6).

Öffentliche API:
  - `LookupResult`, `LookupProvider`, `ChainedLookup` (base)
  - `HamQTHClient`, `QRZClient`, `LookupCache`
  - `build_lookup(config, cache_path)` — Cache + Provider → `ChainedLookup`.
  - `has_lookup_credentials(config)` — sind HamQTH- oder QRZ-Zugangsdaten gesetzt?
  - `lookup_calls(calls, config, ...)` — schlägt alle (eindeutigen) Rufzeichen
    nach und liefert eine Map `CALL -> LookupResult | None`.
  - `accepted_routes(result, default_via)` — Menge der Zustellwege einer Station.
  - `resolve_route(accepted, active_priority)` — höchstpriorisierter aktiver Weg.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Sequence
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
    "accepted_routes",
    "resolve_route",
    "extract_manager_callsign",
    "normalize_via_priority",
    "active_via_priority",
    "VIA_CODES",
    "VIA_LABELS",
]

DEFAULT_CACHE_PATH = "lookup_cache.json"

# Zustellweg-Codes in kanonischer Reihenfolge: B=Büro (inkl. Manager),
# D=Direkt, Q=eQSL, L=LOTW. Der Nutzer priorisiert diese Wege in der GUI und
# zieht eine Trennlinie: Wege über der Linie werden gedruckt (in Reihenfolge),
# Wege darunter nicht.
VIA_CODES = ("B", "D", "Q", "L")

# Anzeigelabels für die GUI-Prioritätsliste.
VIA_LABELS: dict[str, str] = {
    "B": "Büro",
    "D": "Direkt",
    "Q": "eQSL",
    "L": "LOTW",
}


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


# Rufzeichen-Muster: Präfix (Buchstaben/Ziffern), mind. eine Ziffer, Suffix aus
# Buchstaben, optional ein „/…"-Zusatz (Portabel-Kennung). Die Ziffernpflicht
# filtert reine Routing-Wörter (BUREAU/DIRECT/EQSL/LOTW/OQRS/SASE) automatisch aus.
_CALLSIGN_RE = re.compile(r"[A-Z0-9]{1,3}[0-9]+[A-Z]{1,4}(?:/[A-Z0-9]+)?")
# Trennt Rufzeichen-Kandidaten voneinander (Whitespace + gängige Satzzeichen).
# `/` bleibt bewusst erhalten, damit Portabel-Kennungen (z. B. "DK1XY/P") am
# Rufzeichen hängen bleiben und vom Muster mit erfasst werden.
_MANAGER_SPLIT_RE = re.compile(r"[\s,;]+")


def extract_manager_callsign(text: str | None) -> str:
    """Zieht aus dem freien qsl_via/qslmgr-Text genau EIN Manager-Rufzeichen.

    Der Rückgabewert landet im Feld „Via:" auf der Karte, das ausschließlich ein
    Rufzeichen enthalten darf. Gibt `""` zurück, wenn kein Rufzeichen erkennbar
    ist (nur Routing-Wörter wie Bureau/Direct/eQSL/LoTW/OQRS, E-Mail, leer). Bei
    mehreren Kandidaten wird das **erste** genommen.

    Beispiele:
      "QSL via DK1XY direct" → "DK1XY"; "M0OXO OQRS" → "M0OXO";
      "dk1xy@example.com" → "DK1XY"; "Bureau"/"LoTW"/"" → "".
    """
    if not text:
        return ""
    for token in _MANAGER_SPLIT_RE.split(text.strip().upper()):
        if not token:
            continue
        # E-Mail-Adressen: nur der Local-Part kann ein Rufzeichen sein; die
        # Domain (z. B. "web2mail.com") würde sonst falsche Treffer liefern.
        token = token.split("@", 1)[0]
        match = _CALLSIGN_RE.search(token)
        if match:
            return match.group(0)
    return ""


def accepted_routes(result: LookupResult | None, default_via: str = "B") -> tuple[str, ...]:
    """Menge der Zustellwege, die eine Station laut Lookup akzeptiert (§6.2).

    Kanonisch geordnet (B, D, Q, L):
      - `B` (Büro) wenn `qsl == "Y"` **oder** ein echtes Manager-Rufzeichen
        hinterlegt ist (der Manager zählt als Büro-Weg; sein Callsign steht dann
        im Feld „Via:"). Reiner Routing-Freitext ohne Rufzeichen (z. B. „LoTW")
        zählt **nicht** als Büro.
      - `D` (Direkt) wenn `qsldirect == "Y"`.
      - `Q` (eQSL) wenn `eqsl == "Y"`.
      - `L` (LOTW) wenn `lotw == "Y"`.

    Ist die Menge leer (kein Treffer, nur „?"/„N", oder keine Credentials), gilt
    die Station als unbekannt und wird auf `default_via` zurückgeführt (Default
    „B"), damit sie druckbar bleibt.
    """
    default = (default_via or "B").upper()
    if default not in VIA_CODES:
        default = "B"

    routes: list[str] = []
    if result is not None:
        if result.accepts_bureau == "Y" or extract_manager_callsign(result.manager):
            routes.append("B")
        if result.accepts_direct == "Y":
            routes.append("D")
        if result.eqsl == "Y":
            routes.append("Q")
        if result.lotw == "Y":
            routes.append("L")

    if not routes:
        return (default,)
    return tuple(routes)


def resolve_route(accepted: Sequence[str], active_priority: Sequence[str]) -> str | None:
    """Wählt den zu druckenden Weg: erster Code aus `active_priority` (Reihenfolge
    = Priorität, nur Wege über der Trennlinie), der in `accepted` liegt.

    Gibt es keinen solchen Weg, wird die Karte **nicht** gedruckt (`None`).
    """
    accepted_set = set(accepted)
    for code in active_priority:
        if code in accepted_set:
            return code
    return None


def normalize_via_priority(priority: Sequence[str] | None) -> list[str]:
    """Bringt eine (evtl. unvollständige/fehlerhafte) Prioritätsliste in Form:
    genau die gültigen Codes (B, D, Q, L), Reihenfolge aus `priority`, Duplikate
    und Unbekanntes entfernt, fehlende Codes in kanonischer Reihenfolge angehängt.
    """
    order: list[str] = []
    for code in priority or ():
        c = str(code).strip().upper()
        if c in VIA_CODES and c not in order:
            order.append(c)
    for code in VIA_CODES:
        if code not in order:
            order.append(code)
    return order


def active_via_priority(priority: Sequence[str] | None, cut: int) -> list[str]:
    """Die aktiven Wege (über der Trennlinie) in Prioritätsreihenfolge:
    die ersten `cut` Einträge der normalisierten Liste."""
    order = normalize_via_priority(priority)
    n = max(0, min(int(cut), len(order)))
    return order[:n]


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
    dann `None` (→ `accepted_routes` fällt auf `default_via`). `progress_cb(done,
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
