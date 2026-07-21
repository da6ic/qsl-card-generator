"""Inspektions-Skript: parst ein ADIF-Log und gibt eine kurze Übersicht aus.

Ausgabe: Anzahl QSOs, alle vorkommenden (rohen) Feldnamen, Verteilung von
qsl_sent_via und drei Beispiel-QSOs.

Aufruf:
    python scripts/inspect_log.py [PFAD]
Ohne Argument wird tests/data/real_log.adi verwendet.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

# Projektwurzel in den Importpfad, damit "qslcards" ohne Installation gefunden wird.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qslcards.adif.parser import parse_file  # noqa: E402

DEFAULT_LOG = ROOT / "tests" / "data" / "real_log.adi"


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_LOG
    if not path.exists():
        print(f"Datei nicht gefunden: {path}")
        return 1

    qsos = parse_file(path)
    print(f"Datei: {path}")
    print(f"Anzahl QSOs: {len(qsos)}")
    print()

    # Alle vorkommenden Feldnamen (roh, kleingeschrieben) mit Häufigkeit.
    field_counter: Counter[str] = Counter()
    for q in qsos:
        field_counter.update(q.raw.keys())
    print(f"Vorkommende Feldnamen ({len(field_counter)}):")
    for name, count in sorted(field_counter.items()):
        print(f"  {name:<20} {count:>5} / {len(qsos)}")
    print()

    # Verteilung von qsl_sent_via (nach Normalisierung durch den Parser).
    via_counter: Counter[str] = Counter(
        (q.qsl_sent_via if q.qsl_sent_via is not None else "<none>") for q in qsos
    )
    print("Verteilung qsl_sent_via (normalisiert):")
    for code, count in sorted(via_counter.items()):
        print(f"  {code:<8} {count:>5}")
    # Zusätzlich: rohes Feld, falls es anders heißt / andere Werte hat.
    raw_via = Counter(q.raw.get("qsl_sent_via", "<absent>") for q in qsos)
    print("  (roh qsl_sent_via:", dict(raw_via), ")")
    print()

    # Drei Beispiel-QSOs.
    print("Beispiel-QSOs (bis zu 3):")
    for i, q in enumerate(qsos[:3], 1):
        print(f"  --- QSO {i} ---")
        print(f"    call={q.call!r} date={q.qso_date!r} time_on={q.time_on!r}")
        print(f"    band={q.band!r} freq={q.freq!r} mode={q.mode!r}")
        print(f"    rst_sent={q.rst_sent!r} rst_rcvd={q.rst_rcvd!r}")
        print(f"    qsl_sent_via={q.qsl_sent_via!r} qsl_via={q.qsl_via!r}")
        print(f"    name={q.name!r} gridsquare={q.gridsquare!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
