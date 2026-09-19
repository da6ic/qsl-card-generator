"""Cabrillo-Parser für Contest-Logs (siehe docs/SPECIFICATION.md §4.5).

Cabrillo ist zeilenorientiert: Kopfzeilen `TAG: wert` und QSO-Zeilen

    QSO: freq mo yyyy-mm-dd nnnn <sende-austausch> <empfangs-austausch> [t]

Die Spezifikation zeigt zwar feste Spalten, erklärt sie aber ausdrücklich für
**nicht** verbindlich (Tabs sind erlaubt, lange Rufzeichen wie `DL0MT/P` sprengen
die Felder). Deshalb wird tokenweise zerlegt, nicht nach Spaltenpositionen.

Die Zahl der Austauschfelder hängt am Contest (2 bei VHF-Grid-Contests, 5 bei
ARRL-SS) und RST fehlt in vielen Contests ganz — die Heuristik dafür steht in
`_find_split`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .models import QSO

logger = logging.getLogger(__name__)

# Cabrillo-Modus-Kurzcodes -> Text für die Kartenspalte „2-WAY QSO IN".
# Unbekannte Codes werden unverändert (großgeschrieben) durchgereicht.
MODE_MAP: dict[str, str] = {
    "CW": "CW",
    "PH": "SSB",  # Phone
    "FM": "FM",
    "RY": "RTTY",
    "DG": "DIGI",  # allgemein digital (FT4/FT8 bei WW-Digi)
}

# Bandbezeichner (VHF und höher) -> MHz. Cabrillo schreibt oberhalb 902 MHz
# keine Frequenz, sondern das Band. Die Kurzformen ohne „G" kommen real vor —
# das ARRL-UHF-Template schreibt selbst `QSO: 1.2 PH …`.
BAND_DESIGNATORS: dict[str, str] = {
    "50": "50",
    "70": "70",
    "144": "144",
    "222": "222",
    "432": "432",
    "902": "902",
    "1.2G": "1240",
    "2.3G": "2300",
    "3.4G": "3400",
    "5.7G": "5650",
    "10G": "10000",
    "24G": "24000",
    "47G": "47000",
    "75G": "75500",
    "122G": "122250",
    "134G": "134000",
    "241G": "241000",
    "1.2": "1240",
    "2.3": "2300",
    "3.4": "3400",
    "5.7": "5650",
    "10": "10000",
    "24": "24000",
    "47": "47000",
    "75": "75500",
    "122": "122250",
    "134": "134000",
    "241": "241000",
}

# Bandgrenzen in MHz -> ADIF-Bandname. Nur zur Ableitung des `band`-Feldes aus
# der Frequenz (die Gegenrichtung von `cards.builder.BAND_TO_MHZ`).
BAND_EDGES: tuple[tuple[float, float, str], ...] = (
    (1.8, 2.0, "160m"),
    (3.5, 4.0, "80m"),
    (5.06, 5.45, "60m"),
    (7.0, 7.3, "40m"),
    (10.1, 10.15, "30m"),
    (14.0, 14.35, "20m"),
    (18.068, 18.168, "17m"),
    (21.0, 21.45, "15m"),
    (24.89, 24.99, "12m"),
    (28.0, 29.7, "10m"),
    (50.0, 54.0, "6m"),
    (70.0, 71.0, "4m"),
    (144.0, 148.0, "2m"),
    (222.0, 225.0, "1.25m"),
    (420.0, 450.0, "70cm"),
    (902.0, 928.0, "33cm"),
    (1240.0, 1300.0, "23cm"),
    (2300.0, 2450.0, "13cm"),
    (3300.0, 3500.0, "9cm"),
    (5650.0, 5925.0, "6cm"),
    (10000.0, 10500.0, "3cm"),
    (24000.0, 24250.0, "1.25cm"),
    (47000.0, 47200.0, "6mm"),
    (75500.0, 81000.0, "4mm"),
    (122250.0, 123000.0, "2.5mm"),
    (134000.0, 141000.0, "2mm"),
    (241000.0, 250000.0, "1mm"),
)

# Zeilenarten: alles andere ist Kopfzeile.
_QSO_TAGS = frozenset({"QSO", "X-QSO"})
# Tags, die laut Spezifikation mehrfach vorkommen dürfen.
_MULTI_TAGS = frozenset({"ADDRESS", "CLUB", "OPERATORS", "SOAPBOX"})
_HEADER_TAG_RE = re.compile(r"^[A-Z][A-Z0-9-]*$")

_DATE_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_TIME_RE = re.compile(r"^(\d{2}):?(\d{2})(?::?\d{2})?$")
# Strenges RST-Muster: R 1-5, S 1-9, T 1-9. Genau diese Strenge sortiert
# Contest-Seriennummern wie „001" (R=0) und „101" (S=0) automatisch aus.
_RST_RE = re.compile(r"^[1-5][1-9][1-9]?$")
_RST_NN_RE = re.compile(r"^([1-5])NN$")  # CW-Kurzform „5NN"
# Rufzeichen: Präfix, mind. eine Ziffer, Suffix aus Buchstaben, optional „/…".
_CALL_RE = re.compile(r"^[A-Z0-9]{1,3}\d[A-Z]{1,4}(?:/[A-Z0-9]+)*$")
_GRID_RE = re.compile(r"^[A-R]{2}\d{2}(?:[A-X]{2})?$")


def parse_file(path: str | Path) -> list[QSO]:
    """Liest eine Cabrillo-Datei und liefert die enthaltenen QSOs."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse_text(fh.read())


def parse_text(text: str) -> list[QSO]:
    """Parst Cabrillo-Text und liefert die enthaltenen QSOs.

    Wirft nie: unbrauchbare Zeilen werden übersprungen und geloggt. `X-QSO:`
    (vom Contest gestrichene Verbindungen) werden **mit** importiert — das QSO
    hat stattgefunden, die Gegenstation bekommt ihre Karte — und in
    `raw["cabrillo_x_qso"]` markiert.
    """
    header = _parse_header(text)

    qsos: list[QSO] = []
    for number, line in enumerate(text.splitlines(), start=1):
        tag, sep, rest = line.strip().partition(":")
        if not sep or tag.strip().upper() not in _QSO_TAGS:
            continue
        parsed = _split_qso_line(rest.split())
        if parsed is None:
            logger.warning("Cabrillo-Zeile %d nicht verwertbar: %s", number, line.strip())
            continue
        qso = _to_qso(
            parsed,
            header,
            x_qso=tag.strip().upper() == "X-QSO",
            line_number=number,
        )
        if qso is not None:
            qsos.append(qso)
    return qsos


# --------------------------------------------------------------------- Kopf


def _parse_header(text: str) -> dict[str, str]:
    """Sammelt die Kopfzeilen (`TAG: wert`) als Map mit großgeschriebenen Tags.

    Eigener Durchlauf, weil die Reihenfolge in Cabrillo beliebig ist: `CALLSIGN:`
    darf hinter den QSO-Zeilen stehen, wird zum Zerlegen aber vorher gebraucht.
    """
    header: dict[str, str] = {}
    for line in text.splitlines():
        tag, sep, value = line.strip().partition(":")
        key = tag.strip().upper()
        if not sep or key in _QSO_TAGS or not _HEADER_TAG_RE.match(key):
            continue
        value = value.strip()
        if not value:
            continue
        if key in _MULTI_TAGS and key in header:
            header[key] = f"{header[key]} {value}"
        else:
            header.setdefault(key, value)
    return header


# ----------------------------------------------------------- QSO-Zeile


@dataclass(frozen=True)
class _QsoLine:
    """Zerlegte, aber noch nicht normalisierte QSO-Zeile."""

    freq: str
    mode: str
    date: str
    time: str
    sent: tuple[str, ...]  # (eigenes Rufzeichen, Austauschfelder...)
    rcvd: tuple[str, ...]  # (Gegenstation, Austauschfelder...)
    transmitter: str | None


def _split_qso_line(tokens: Sequence[str]) -> _QsoLine | None:
    """Zerlegt die Tokens hinter `QSO:`/`X-QSO:`. Unverwertbare Zeile -> None."""
    # Das Datum ist der Anker: davor stehen genau Frequenz und Modus. Über die
    # Position statt über feste Indizes zu gehen macht das Ganze unempfindlich
    # gegen Tabs, Mehrfach-Leerzeichen und führende Ausrichtung.
    date_at = next((i for i, t in enumerate(tokens[:6]) if _DATE_RE.match(t)), -1)
    if date_at < 2 or date_at + 2 >= len(tokens):
        return None
    if not _TIME_RE.match(tokens[date_at + 1]):
        return None

    rest = list(tokens[date_at + 2 :])
    # Transmitter-ID (`0`/`1`, nur bei Multi-TX) nur abtrennen, wenn die
    # Feldzahl dadurch gerade wird: sonst verschwände bei einem Contest mit
    # Seriennummern die letzte Nummer (9A-CW: „… 599 001 9A2UE 599 101").
    transmitter = rest.pop() if len(rest) % 2 and rest[-1] in ("0", "1") else None

    cut = _find_split(rest)
    if cut is None:
        return None
    return _QsoLine(
        freq=tokens[date_at - 2],
        mode=tokens[date_at - 1],
        date=tokens[date_at],
        time=tokens[date_at + 1],
        sent=tuple(rest[:cut]),
        rcvd=tuple(rest[cut:]),
        transmitter=transmitter,
    )


def _find_split(rest: list[str]) -> int | None:
    """Trennstelle zwischen Sende- und Empfangsteil (Index des Gegen-Rufzeichens).

    Drei unabhängige Signale, deren Summe entscheidet. Im Normalfall gewinnt
    ohnehin die Mitte; das Scoring rettet zusätzlich Contests mit asymmetrischem
    Austausch, statt die Zeile zu verwerfen.

    **Das eigene Rufzeichen aus `CALLSIGN:` taugt hier nicht als Signal** — es
    stand einmal mit `+1` drin und wurde entfernt. Der Grund ist die Invariante,
    auf der die ganze Zerlegung steht: das erste Feld jeder Seite ist das
    Rufzeichen. Damit liegt unser eigenes immer auf `rest[0]`, also für **jeden**
    Kandidaten links der Trennstelle — der Term war für alle `cut` derselbe
    Summand und konnte das Maximum nie verschieben. Ein Signal, das nichts
    unterscheidet, ist keines.
    """
    if len(rest) < 2:
        return None
    best: int | None = None
    best_score = -1
    for cut in range(1, len(rest)):
        score = 0
        if cut * 2 == len(rest):  # Symmetrie: beide Seiten gleich viele Felder
            score += 4
        if _is_call(rest[cut]):  # rechts beginnt ein Rufzeichen
            score += 3
        score += _shape_match(rest[1:cut], rest[cut + 1 :])
        if score > best_score:
            best, best_score = cut, score
    return best


def _is_call(token: str) -> bool:
    """Sieht das Token nach einem Rufzeichen aus? Locator zählt nicht.

    Der Locator-Ausschluss ist nötig, weil ein Sechsstelliger wie „FN12FR" das
    Rufzeichen-Muster erfüllt (Präfix „FN1", Ziffer „2", Suffix „FR").
    """
    upper = token.upper()
    return bool(_CALL_RE.match(upper)) and not _GRID_RE.match(upper)


def _shape(token: str) -> str:
    """Grobe Form eines Austauschfeldes — Rapport, Locator, Zahl, Wort, Rest."""
    upper = token.upper()
    if _RST_RE.match(upper) or _RST_NN_RE.match(upper):
        return "rst"
    if _GRID_RE.match(upper):
        return "grid"
    if upper.isdigit():
        return "num"
    return "alpha" if upper.isalpha() else "other"


def _shape_match(left: Sequence[str], right: Sequence[str]) -> int:
    """Wie gut passen die Austauschfelder beider Seiten paarweise zusammen (0-2)?"""
    if len(left) != len(right):
        return 0
    if not left:
        return 1
    same = sum(_shape(a) == _shape(b) for a, b in zip(left, right, strict=True))
    if same == len(left):
        return 2
    return 1 if same * 2 >= len(left) else 0


def _rst(fields: Sequence[str]) -> str | None:
    """Der Rapport steht per Konvention direkt hinter dem Rufzeichen — sonst gibt
    es keinen. Fehlt er (NAQP, VHF-Contests, Sprint), bleibt das Feld leer; ein
    erfundenes „59" auf einer QSL-Karte wäre eine falsche Bestätigung."""
    if len(fields) < 2:
        return None
    token = fields[1].strip().upper()
    shortcut = _RST_NN_RE.match(token)
    if shortcut:
        return f"{shortcut.group(1)}99"
    return token if _RST_RE.match(token) else None


def _single_grid(fields: Sequence[str]) -> str | None:
    """Der Locator der Gegenstation, falls der Austausch genau einen enthält."""
    grids = [f.upper() for f in fields if _GRID_RE.match(f.upper())]
    return grids[0] if len(grids) == 1 else None


# ------------------------------------------------------------ Normalisierung


def _norm_date(token: str) -> str:
    """„2000-11-26" -> „20001126" (das Format, das `cards.builder` erwartet)."""
    match = _DATE_RE.match(token)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}{int(month):02d}{int(day):02d}"


def _norm_time(token: str) -> str:
    """„0711"/„07:11"/„071100" -> „0711"."""
    match = _TIME_RE.match(token)
    return f"{match.group(1)}{match.group(2)}" if match else ""


def _norm_freq(token: str) -> str | None:
    """Cabrillo-Frequenzfeld -> MHz-String. Unbekanntes -> None (nichts raten).

    Die Reihenfolge ist wesentlich: `2.3` ist der Bandbezeichner für 2,3 GHz und
    keine 2,3-MHz-Frequenz, deshalb kommt die Tabelle vor der Zahl. Für nackte
    Zahlen ist die Schwelle 1000 sauber: die niedrigste kHz-Angabe auf Kurzwelle
    ist 1800, der höchste MHz-Bandbezeichner 902.
    """
    key = token.strip().upper()
    if not key:
        return None
    if key in BAND_DESIGNATORS:
        return BAND_DESIGNATORS[key]
    try:
        value = float(key)
    except ValueError:
        return None
    if value >= 1000:  # kHz
        return _trim(value / 1000)
    if 1.8 <= value <= 30.0:  # manche Logger schreiben Kurzwelle schon in MHz
        return _trim(value)
    return None


def _trim(value: float) -> str:
    """Frequenz als kurzer Dezimalstring (14.0 -> „14", 3.799 -> „3.799")."""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _band(freq_mhz: str | None) -> str | None:
    """Bandname aus der Frequenz; außerhalb aller Amateurbänder -> None."""
    if not freq_mhz:
        return None
    try:
        value = float(freq_mhz)
    except ValueError:
        return None
    for low, high, name in BAND_EDGES:
        if low <= value <= high:
            return name
    return None


def _to_qso(
    line: _QsoLine,
    header: dict[str, str],
    *,
    x_qso: bool,
    line_number: int,
) -> QSO | None:
    """Bildet eine zerlegte Zeile auf ein QSO ab. Ohne Gegenstation -> None."""
    call = line.rcvd[0].strip().upper()
    if not call:
        return None

    qso_date = _norm_date(line.date)
    time_on = _norm_time(line.time)
    freq = _norm_freq(line.freq)
    band = _band(freq)
    mode = MODE_MAP.get(line.mode.strip().upper(), line.mode.strip().upper())
    rst_sent = _rst(line.sent)
    rst_rcvd = _rst(line.rcvd)
    gridsquare = _single_grid(line.rcvd[1:])

    # `raw` trägt ADIF-Feldnamen, wo es sie gibt. CALLSIGN/GRID-LOCATOR aus dem
    # Kopf sind **Absender**daten (station_callsign/my_gridsquare) — sie stehen
    # hier nur informativ; auf die Karte kommt der Absender aus der Config.
    raw: dict[str, str] = {
        "call": call,
        "qso_date": qso_date,
        "time_on": time_on,
        "mode": mode,
        "cabrillo_freq": line.freq,
        "cabrillo_mode": line.mode.strip().upper(),
        "cabrillo_line": str(line_number),
    }
    _put(raw, "freq", freq)
    _put(raw, "band", band)
    _put(raw, "rst_sent", rst_sent)
    _put(raw, "rst_rcvd", rst_rcvd)
    _put(raw, "gridsquare", gridsquare)
    _put(raw, "cabrillo_exch_sent", " ".join(line.sent[1:]))
    _put(raw, "cabrillo_exch_rcvd", " ".join(line.rcvd[1:]))
    _put(raw, "cabrillo_transmitter", line.transmitter)
    _put(raw, "station_callsign", header.get("CALLSIGN"))
    _put(raw, "my_gridsquare", header.get("GRID-LOCATOR"))
    _put(raw, "operator", header.get("OPERATORS"))
    _put(raw, "contest_id", header.get("CONTEST"))
    if x_qso:
        raw["cabrillo_x_qso"] = "Y"

    return QSO(
        call=call,
        qso_date=qso_date,
        time_on=time_on,
        band=band,
        freq=freq,
        mode=mode,
        rst_sent=rst_sent,
        rst_rcvd=rst_rcvd,
        # Cabrillo kennt keine Versandart und keinen Manager: beides kommt aus
        # dem Lookup (siehe docs/SPECIFICATION.md §6).
        qsl_sent_via=None,
        qsl_via=None,
        name=None,
        gridsquare=gridsquare,
        qth=None,
        country=None,
        raw=raw,
    )


def _put(raw: dict[str, str], key: str, value: str | None) -> None:
    """Nimmt `value` in den Roh-Record auf, sofern es etwas zu speichern gibt."""
    if value:
        raw[key] = value
