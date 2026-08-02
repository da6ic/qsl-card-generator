"""ADIF-Tokenizer und Record-Parser.

Algorithmus siehe docs/SPECIFICATION.md §4. ADIF ist byteorientiert: die Länge
im Feld-Specifier `<NAME:LÄNGE[:TYP]>` zählt Bytes des Werts (UTF-8). Daher wird
auf Byte-Ebene tokenisiert und der Wert anschließend dekodiert.
"""

from __future__ import annotations

from pathlib import Path

from .models import QSO

VIA_CODES = {"B", "D", "E", "M"}


def parse_file(path: str | Path) -> list[QSO]:
    """Liest eine ADIF-Datei und liefert die enthaltenen QSOs."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse_text(fh.read())


def parse_text(text: str) -> list[QSO]:
    """Parst ADIF-Text und liefert die enthaltenen QSOs."""
    records = _tokenize(text)
    qsos: list[QSO] = []
    for record in records:
        qso = _record_to_qso(record)
        if qso is not None:
            qsos.append(qso)
    return qsos


def _tokenize(text: str) -> list[dict[str, str]]:
    """Zerlegt den ADIF-Text in Roh-Records (Dicts mit kleingeschriebenen Keys).

    Header-Felder vor `<EOH>` werden verworfen. Ein fehlendes letztes `<EOR>`
    wird toleriert.
    """
    data = text.encode("utf-8")
    n = len(data)
    cursor = 0

    records: list[dict[str, str]] = []
    current: dict[str, str] = {}

    while cursor < n:
        start = data.find(b"<", cursor)
        if start == -1:
            break  # kein Tag mehr -> Rest ist loser Text, verwerfen

        end = data.find(b">", start + 1)
        if end == -1:
            break  # unvollständiges Tag am Ende

        tag = data[start + 1 : end].decode("utf-8", errors="replace")
        parts = tag.split(":")
        name = parts[0].strip().lower()

        cursor = end + 1  # hinter das '>'

        if name == "eor":
            if current:
                records.append(current)
                current = {}
            continue
        if name == "eoh":
            current = {}  # alles vor <EOH> ist Header -> verwerfen
            continue
        if not name:
            continue

        length = 0
        if len(parts) >= 2:
            try:
                length = int(parts[1].strip())
            except ValueError:
                length = 0

        raw_value = data[cursor : cursor + length]
        # Robustheit gegen zu groß angegebene Feldlängen: Manche Logger (z.B.
        # HAMRS) zählen kurze Werte falsch und schließen Zeilenumbruch bzw. den
        # Beginn des nächsten Tags mit ein (etwa `<RST_SENT:3>0` für den Wert
        # "0"). Ein `<` innerhalb des gelesenen Werts markiert den Start des
        # nächsten Feld-Specifiers -> Wert dort abschneiden und den Cursor dorthin
        # zurücksetzen, damit das folgende Tag nicht verschluckt wird.
        lt = raw_value.find(b"<")
        if lt != -1:
            value = raw_value[:lt].decode("utf-8", errors="replace")
            cursor += lt
        else:
            value = raw_value.decode("utf-8", errors="replace")
            cursor += length
        current[name] = value

    if current:  # fehlendes letztes <EOR>
        records.append(current)

    return records


def _normalize_via(raw_value: str | None) -> str | None:
    """`qsl_sent_via` normalisieren: Großbuchstabe, nur erstes Zeichen B/D/E/M."""
    if not raw_value:
        return None
    first = raw_value.strip().upper()[:1]
    return first if first in VIA_CODES else None


def _record_to_qso(record: dict[str, str]) -> QSO | None:
    """Bildet einen Roh-Record auf ein QSO ab. Records ohne `call` -> None."""
    call = record.get("call", "").strip()
    if not call:
        return None

    return QSO(
        call=call,
        qso_date=record.get("qso_date", ""),
        time_on=record.get("time_on", ""),
        band=record.get("band"),
        freq=record.get("freq"),
        mode=record.get("mode"),
        rst_sent=record.get("rst_sent"),
        rst_rcvd=record.get("rst_rcvd"),
        qsl_sent_via=_normalize_via(record.get("qsl_sent_via")),
        qsl_via=record.get("qsl_via"),
        name=record.get("name"),
        gridsquare=record.get("gridsquare"),
        qth=record.get("qth"),
        country=record.get("country"),
        raw=dict(record),
    )
