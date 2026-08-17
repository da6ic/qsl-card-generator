"""Lookup-Interface und gemeinsame Datentypen (siehe docs/SPECIFICATION.md §6).

`LookupResult` ist das einheitliche Ergebnis aller Provider (HamQTH, QRZ, Cache).
`LookupCredentials` hält die Zugangsdaten — nur zur Laufzeit, nie in der Config.
`LookupProvider` ist das Protokoll, das jeder Provider erfüllt. `ChainedLookup`
verdrahtet Cache + mehrere Provider zu einer Fassade für die GUI: erst Cache,
dann die Provider in Reihenfolge; Ergebnisse (auch negative) werden gecacht.

Grundregel: Netz-/Auth-Fehler sind **nie** fatal. Provider fangen alles ab,
loggen und liefern `None`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from qslcards.lookup.cache import LookupCache


@dataclass
class LookupResult:
    call: str
    name: str | None = None
    street: str | None = None
    zip: str | None = None
    city: str | None = None
    country: str | None = None
    grid: str | None = None
    # QSL-Routing (bestimmt die Zustellwege, siehe accepted_routes):
    manager: str | None = None  # qsl_via (HamQTH) / qslmgr (QRZ)
    accepts_bureau: str | None = None  # HamQTH qsl        ("Y"/"N"/"?")
    accepts_direct: str | None = None  # HamQTH qsldirect  ("Y"/"N"/"?")
    lotw: str | None = None  # HamQTH lotw               ("Y"/"N"/"?")
    eqsl: str | None = None  # HamQTH eqsl               ("Y"/"N"/"?")
    source: str = "none"  # "hamqth" | "qrz" | "cache" | "none"

    def is_empty(self) -> bool:
        """True, wenn weder Adressdaten noch verwertbare Routing-Infos vorliegen.

        Ein „negatives" Ergebnis (nichts gefunden) wird so im Cache markiert,
        damit dieselbe Abfrage nicht erneut ins Netz geht. Wichtig: ein Treffer
        mit **nur** Manager oder **nur** einem „Y"-Flag (z. B. `lotw=Y`) ist
        **nicht** leer — sonst ginge die Versandart-Info beim Cachen verloren.
        """
        has_address = any((self.name, self.street, self.zip, self.city, self.country, self.grid))
        has_routing = bool(self.manager) or any(
            flag == "Y" for flag in (self.accepts_bureau, self.accepts_direct, self.lotw, self.eqsl)
        )
        return not (has_address or has_routing)

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> LookupResult:
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs.setdefault("call", "")
        return cls(**kwargs)  # type: ignore[arg-type]


@dataclass
class LookupCredentials:
    """Zugangsdaten der Lookup-Anbieter — ausschließlich zur Laufzeit.

    Bewusst **nicht** Teil von `AppConfig`: `config.save` würde sie im Klartext
    in die `config.yaml` schreiben. Der Nutzer trägt sie in jeder Sitzung neu in
    GUI-Abschnitt 6 ein; beim Beenden sind sie weg.

    `program_id` reist hier mit (HamQTH verlangt eine prg-Kennung), damit
    `build_lookup`/`lookup_calls` genau ein Objekt brauchen. Den Wert füllt die
    GUI aus `config.LookupConfig.program_id` — dort steht er weiterhin.
    """

    hamqth_user: str = ""
    hamqth_pass: str = ""
    qrz_user: str = ""
    qrz_pass: str = ""
    program_id: str = "qslcards"


class LookupProvider(Protocol):
    def lookup(self, call: str) -> LookupResult | None: ...


class ChainedLookup:
    """Cache-gestützte Fassade über mehrere Provider.

    Ablauf pro Rufzeichen:
      1. Cache befragen. Treffer (positiv **oder** negativ) → sofort zurück.
      2. Sonst Provider der Reihe nach fragen; erster nicht-leerer Treffer gewinnt.
      3. Ergebnis cachen (auch „nichts gefunden" als negativer Eintrag).

    Der Cache ist optional; ohne ihn wird jedes Mal frisch abgefragt.

    `degraded()` meldet, dass ein Provider gerade unbrauchbar ist (abgelehnte
    Anmeldung). Dann wird **nichts** geschrieben: sonst stünde nach einem Lauf
    mit falschem Passwort für jede Station ein negativer Eintrag in der
    Cache-Datei, und selbst mit korrigierten Zugangsdaten fände der nächste
    Start nichts mehr. Gelesen wird weiter — alte Treffer bleiben gültig.
    """

    def __init__(
        self,
        providers: list[LookupProvider],
        cache: LookupCache | None = None,
        *,
        degraded: Callable[[], bool] | None = None,
    ) -> None:
        self._providers = list(providers)
        self._cache = cache
        self._degraded = degraded or (lambda: False)

    def lookup(self, call: str, *, force: bool = False) -> LookupResult | None:
        """Schlägt `call` nach. Mit `force=True` wird der Cache **übersprungen**
        (frische Abfrage) — z. B. um nach einem Netzabbruch einen negativ
        gecachten Eintrag erneut zu versuchen. Das Ergebnis wird trotzdem gecacht.
        """
        call = (call or "").strip().upper()
        if not call:
            return None

        if self._cache is not None and not force:
            cached = self._cache.get(call)
            if cached is not None:
                # Negativer Cache-Eintrag → kein erneuter Netz-Call.
                return None if cached.is_empty() else cached

        result: LookupResult | None = None
        for provider in self._providers:
            found = provider.lookup(call)
            if found is not None and not found.is_empty():
                result = found
                break

        if self._cache is not None and not self._degraded():
            self._cache.set(call, result or LookupResult(call=call, source="none"))

        return result
