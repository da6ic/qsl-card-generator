"""Rufzeichen -> DXCC-Gebiet über die `cty.dat` von AD1C (country-files.com).

Nachgebaut nach dem Programm „DXCC-Filter" (gleiche Regeln, gemessen 294/294
Stationen richtig gegen die DXCC-Werte von QARTest im CQ-WW-Beispiel-Log).

Format der `cty.dat` (ein Datensatz je Gebiet, endet mit `;`):

    Name: CQ: ITU: Kontinent: Breite: Länge: UTC-Versatz: Hauptpräfix:
        Präfix,Präfix,=EXAKTES_RUFZEICHEN(zone)[itu],…;

Die `cty.dat` nennt jedes Gebiet nur über seinen Hauptpräfix, nicht über die
ADIF-DXCC-Nummer, die die GDXF verwendet. Die Brücke ist die mitgelieferte
Tabelle `dxcc-numbers.csv` (Hauptpräfix -> Nummer).

Zuordnung eines Rufzeichens:
  1. exakter Eintrag (`=VK9DX`) — so stehen DXpeditionen und Sonderrufzeichen drin;
  2. sonst der Teil, der den Standort nennt (`CT9/M0CCC` -> `CT9`,
     `DL1ABC/P` -> `DL1ABC`, `W1AW/4` -> `W4AW`), und davon der **längste**
     passende Präfix.
`/MM` (maritime mobile) und `/AM` (aeronautical mobile) zählen für kein Gebiet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Zusätze nach „/", die nichts über den Standort sagen.
_IGNORED_SUFFIXES = frozenset({"P", "M", "QRP", "QRPP", "A", "B", "LH", "J", "R"})
# Maritime/aeronautical mobile: gilt für kein DXCC-Gebiet.
_NO_ENTITY_SUFFIXES = frozenset({"MM", "AM"})
# Zonen-/Kontinent-Überschreibungen an einem Eintrag, z. B. `=K1ABC(5)[8]`.
_OVERRIDES = re.compile(r"[(\[<{~].*$")
# Versionsvermerk der Datei, ein Pseudo-Rufzeichen wie `=VER20261023`.
_VERSION = re.compile(r"=VER(\d{4})(\d{2})(\d{2})")


@dataclass(frozen=True)
class Entity:
    """Ein Gebiet der `cty.dat`."""

    prefix: str  # Hauptpräfix in der cty.dat, z. B. "P5", "3Y/b"
    name: str
    dxcc: int | None  # ADIF-DXCC-Nummer; None, wenn die Tabelle sie nicht kennt


class CtyDatabase:
    """Die eingelesene `cty.dat` samt Nummerntabelle."""

    def __init__(self, cty_text: str, numbers_text: str) -> None:
        numbers = parse_numbers(numbers_text)
        self.exact: dict[str, Entity] = {}
        self.prefixes: dict[str, Entity] = {}
        self.version = ""  # "2026-10-23", leer wenn die Datei keinen Vermerk hat

        for record in cty_text.split(";"):
            fields = record.split(":")
            if len(fields) < 9:
                continue
            name, main_prefix = fields[0].strip(), fields[7].strip()
            if main_prefix.startswith("*"):
                continue  # nur WAE-Gebiet (z. B. *TA1), kein DXCC-Gebiet
            entity = Entity(main_prefix, name, numbers.get(main_prefix))
            for alias in fields[8].replace("\n", " ").split(","):
                alias = _OVERRIDES.sub("", alias.strip())
                if alias.startswith("="):
                    self.exact[alias[1:]] = entity
                    version = _VERSION.fullmatch(alias)
                    if version:
                        self.version = "-".join(version.groups())
                elif alias:
                    self.prefixes[alias] = entity

    def __len__(self) -> int:
        return len(self.prefixes)

    def lookup(self, call: str) -> Entity | None:
        """Gebiet eines Rufzeichens; None = unbekannt oder kein Gebiet (/MM)."""
        call = (call or "").strip().upper()
        if not call:
            return None
        if call in self.exact:
            return self.exact[call]
        location = location_part(call)
        if location is None:
            return None
        if location in self.exact:
            return self.exact[location]
        for length in range(len(location), 0, -1):
            entity = self.prefixes.get(location[:length])
            if entity is not None:
                return entity
        return None

    def dxcc(self, call: str) -> int | None:
        """Kurzform für den Builder: nur die ADIF-DXCC-Nummer."""
        entity = self.lookup(call)
        return entity.dxcc if entity is not None else None


def location_part(call: str) -> str | None:
    """Der Teil eines Rufzeichens, der sagt, **wo** gefunkt wurde.

    `CT9/M0CCC` -> `CT9`, `DL1ABC/EA8` -> `EA8`, `W1AW/4` -> `W4AW`,
    `DL1ABC/P` -> `DL1ABC`; `DL1ABC/MM` -> None.
    """
    parts = [part for part in call.split("/") if part]
    if any(part in _NO_ENTITY_SUFFIXES for part in parts):
        return None
    parts = [part for part in parts if part not in _IGNORED_SUFFIXES]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        base, extra = parts
        if extra.isdigit():  # W1AW/4: gleiches Land, anderer Rufbezirk
            return re.sub(r"\d", extra, base, count=1)
        return min(parts, key=len)  # der kürzere Teil ist der Landespräfix
    return parts[0] if parts else None


def parse_numbers(text: str) -> dict[str, int]:
    """`dxcc-numbers.csv` lesen: `Hauptpräfix;Nummer;Name`, `#` = Kommentar."""
    numbers: dict[str, int] = {}
    for line in text.splitlines():
        if line.startswith("#") or ";" not in line:
            continue
        prefix, number = line.split(";")[:2]
        if number.strip().isdigit():
            numbers[prefix.strip()] = int(number)
    return numbers
