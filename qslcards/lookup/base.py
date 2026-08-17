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

# Die inhaltlichen Felder eines Treffers — alles außer `call` und `source`.
# Maßgeblich fürs Zusammenführen zweier Anbieter (`LookupResult.merged_with`)
# und für die Frage, ob sich der nächste Anbieter überhaupt noch lohnt.
DATA_FIELDS = (
    "name",
    "street",
    "zip",
    "city",
    "country",
    "grid",
    "manager",
    "accepts_bureau",
    "accepts_direct",
    "lotw",
    "eqsl",
)


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

    def missing_fields(self) -> tuple[str, ...]:
        """Datenfelder, die dieser Treffer nicht füllt (leer oder `None`).

        `call` und `source` zählen nicht mit — sie sind immer gesetzt. Solange
        etwas fehlt, lohnt sich für `ChainedLookup` der nächste Anbieter.
        """
        return tuple(name for name in DATA_FIELDS if not getattr(self, name))

    def merged_with(self, other: LookupResult) -> LookupResult:
        """Füllt die eigenen Lücken aus `other`; **eigene** Werte gewinnen immer.

        Nötig, weil die Anbieter Verschiedenes können: QRZ liefert Adresse und
        Manager, aber **keine** Zustellweg-Flags (§6.3) — die kommen nur von
        HamQTH. Ohne Zusammenführen bliebe jede von QRZ gefundene Station ohne
        akzeptierte Wege und fiele auf `default_via` zurück.

        `source` nennt beide Anbieter (z. B. „qrz+hamqth"), sobald wirklich
        etwas übernommen wurde — sonst bleibt die eigene Herkunft stehen.
        """
        taken = False
        merged = LookupResult(**asdict(self))
        for name in DATA_FIELDS:
            if not getattr(merged, name):
                value = getattr(other, name)
                if value:
                    setattr(merged, name, value)
                    taken = True
        if taken and other.source and other.source != merged.source:
            merged.source = f"{merged.source}+{other.source}"
        return merged

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
      2. Sonst Provider der Reihe nach fragen. Der **erste** nicht-leere Treffer
         gewinnt bei jedem Feld, das er füllt; die folgenden Provider füllen nur
         noch die Lücken (`LookupResult.merged_with`). Ist nichts mehr offen,
         wird der Rest der Kette gar nicht erst gefragt.
      3. Ergebnis cachen (auch „nichts gefunden" als negativer Eintrag).

    Punkt 2 ist bewusst „ergänzen" statt „abbrechen": QRZ steht vorn, liefert
    aber keine Zustellweg-Flags — die kommen von HamQTH. Ein reines Abbrechen
    beim ersten Treffer würde jede von QRZ gefundene Station ohne akzeptierte
    Wege lassen (§6.2/§6.2a).

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
            if result is not None and not result.missing_fields():
                # Nichts mehr nachzufüllen → kein weiterer Netz-Call.
                break
            found = provider.lookup(call)
            if found is None or found.is_empty():
                continue
            result = found if result is None else result.merged_with(found)

        if self._cache is not None and not self._degraded():
            self._cache.set(call, result or LookupResult(call=call, source="none"))

        return result
