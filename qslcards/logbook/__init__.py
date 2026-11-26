"""Logbuch-Import: ADIF und Cabrillo -> QSO-Liste (siehe SPECIFICATION.md §4).

Öffentliche API:
  - `QSO` — Domänenmodell (models.py), gemeinsam für beide Formate.
  - `detect_format(text)` — „adif" | „cabrillo" | None, erkannt am **Inhalt**.
  - `parse_text(text)` / `parse_file(path)` — erkennt das Format und delegiert.
  - `LogFormatError` — die Datei ist kein verwertbares Logbuch.

Die Format-Parser (`logbook.adif`, `logbook.cabrillo`) werfen **nie**:
unbrauchbare Zeilen werden übersprungen, das Ergebnis ist notfalls `[]`. Erst
dieser Dispatcher weiß, dass ein *Anwender* eine *Datei* ausgewählt hat — nur
hier ist „leer" ein Fehler statt eines Ergebnisses.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from qslcards.logbook import adif, cabrillo
from qslcards.logbook.models import QSO

__all__ = [
    "qsl_already_sent",
    "QSO",
    "LogFormatError",
    "FORMAT_ADIF",
    "FORMAT_CABRILLO",
    "FORMAT_LABELS",
    "detect_format",
    "parse_file",
    "parse_text",
]

FORMAT_ADIF = "adif"
FORMAT_CABRILLO = "cabrillo"

FORMAT_LABELS: dict[str, str] = {FORMAT_ADIF: "ADIF", FORMAT_CABRILLO: "Cabrillo"}

_PARSERS: dict[str, Callable[[str], list[QSO]]] = {
    FORMAT_ADIF: adif.parse_text,
    FORMAT_CABRILLO: cabrillo.parse_text,
}

_START_OF_LOG_RE = re.compile(r"^\s*START-OF-LOG:", re.MULTILINE | re.IGNORECASE)
_QSO_LINE_RE = re.compile(r"^\s*X?-?QSO:", re.MULTILINE | re.IGNORECASE)
_ADIF_RE = re.compile(r"<(?:eoh|eor)>|<call:\d", re.IGNORECASE)


class LogFormatError(ValueError):
    """Die Datei ist kein verwertbares Logbuch (Format unbekannt oder ohne QSOs)."""


def qsl_already_sent(qso: QSO) -> bool:
    """True, wenn das Log für das QSO schon „Papier-QSL gesendet" führt.

    ADIF-Feld `QSL_SENT` = Y (bei Wavelog das gleichnamige Feld der API).
    Solche QSOs bekommen keine Karte mehr.
    """
    return (qso.raw.get("qsl_sent") or "").strip().upper() == "Y"


def detect_format(text: str) -> str | None:
    """Erkennt das Logbuchformat am Inhalt, nicht an der Dateiendung.

    `.log`/`.txt` sind mehrdeutig, deshalb wird immer der Inhalt befragt.
    Reihenfolge: `START-OF-LOG:` ist eindeutig Cabrillo. Sonst entscheiden die
    ADIF-Marker — eine ADIF-Datei kann in einem Kommentarwert durchaus „QSO:"
    enthalten. Erst danach zählt eine nackte `QSO:`-Zeile als kopfloses Cabrillo.
    """
    if _START_OF_LOG_RE.search(text):
        return FORMAT_CABRILLO
    if _ADIF_RE.search(text):
        return FORMAT_ADIF
    if _QSO_LINE_RE.search(text):
        return FORMAT_CABRILLO
    return None


def parse_text(text: str) -> list[QSO]:
    """Erkennt das Format und liefert die QSOs. Ohne verwertbares Ergebnis:
    `LogFormatError` (die GUI unterscheidet das von `OSError`)."""
    fmt = detect_format(text)
    if fmt is None:
        raise LogFormatError(
            "Unbekanntes Format: weder ADIF (<EOH>/<EOR>/<CALL:…>) "
            "noch Cabrillo (START-OF-LOG:/QSO:)."
        )
    qsos = _PARSERS[fmt](text)
    if not qsos:
        raise LogFormatError(f"{FORMAT_LABELS[fmt]}-Datei erkannt, aber ohne verwertbare QSOs.")
    return qsos


def parse_file(path: str | Path) -> list[QSO]:
    """Liest eine Logdatei (ADIF oder Cabrillo) und liefert die enthaltenen QSOs."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse_text(fh.read())
