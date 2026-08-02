"""Config-Datenmodell und YAML-Persistenz.

Siehe docs/SPECIFICATION.md §3. Fehlende YAML-Felder werden mit den dort
genannten Defaults aufgefüllt, unbekannte Felder ignoriert.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

import yaml


@dataclass
class SenderConfig:
    callsign: str = ""
    name: str = ""
    street: str = ""
    zip: str = ""
    city: str = ""
    country: str = ""
    locator: str = ""
    dok: str = ""
    waz: str = ""
    itu: str = ""


@dataclass
class LookupConfig:
    hamqth_user: str = ""
    hamqth_pass: str = ""
    qrz_user: str = ""
    qrz_pass: str = ""
    program_id: str = "qslcards"  # HamQTH verlangt prg-Kennung
    address_export: bool = False  # Adress-/Label-CSV für alle Stationen
    # Kein `lookup_addresses` mehr: der Lookup läuft automatisch beim Log-Laden,
    # sobald Credentials gesetzt sind (siehe docs/SPECIFICATION.md §6).


@dataclass
class GenerationConfig:
    card_mode: str = "per_qso"  # "per_qso" | "per_station"
    via_filter: list[str] = field(default_factory=lambda: ["B", "D", "M"])
    default_via: str = "B"  # Fallback, wenn der Lookup nichts/"?" liefert
    #   -> nur hier in der Config, kein GUI-Widget. Via kommt sonst aus dem Lookup.
    page_orientation: str = "landscape"  # A6, siehe CARD_LAYOUT.md
    static_footer: str = "TNX FR NICE CONTACT, 73"
    remarks: str = ""  # globaler REMARKS-Text (alle Karten); leer -> kein Kasten
    qsl_mark: str = "none"  # "pse" | "tnx" | "none" (global)
    portable_mark: str = "none"  # "none" | "p" | "m" | "t" | "r" (global)
    confirm_mark: str = "none"  # "qso" | "swl" | "none" (global)


@dataclass
class AppConfig:
    sender: SenderConfig = field(default_factory=SenderConfig)
    lookup: LookupConfig = field(default_factory=LookupConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)


T = TypeVar("T")


def _from_dict(cls: type[T], data: Any) -> T:
    """Baut eine Dataclass aus einem Dict: unbekannte Felder ignorieren,
    fehlende Felder über die Dataclass-Defaults auffüllen."""
    if not isinstance(data, dict):
        return cls()
    known = {f.name for f in fields(cls)}
    kwargs = {key: value for key, value in data.items() if key in known}
    return cls(**kwargs)


def load(path: str | Path) -> AppConfig:
    """Lädt die YAML-Config und füllt fehlende Felder mit Defaults auf."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    return AppConfig(
        sender=_from_dict(SenderConfig, data.get("sender")),
        lookup=_from_dict(LookupConfig, data.get("lookup")),
        generation=_from_dict(GenerationConfig, data.get("generation")),
    )


def save(config: AppConfig, path: str | Path) -> None:
    """Schreibt die Config als YAML."""
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(
            asdict(config),
            fh,
            allow_unicode=True,
            sort_keys=False,
        )
