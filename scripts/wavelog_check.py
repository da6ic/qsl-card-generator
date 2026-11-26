"""Prüfung gegen eine ECHTE Wavelog-Instanz (Bewertung 1.5).

Bisher ist die Wavelog-Anbindung nur gegen `scripts/mock_wavelog.py` getestet.
Dieses Skript macht die drei Schritte aus der Bewertung und schreibt einen
Bericht, der sich als Test-Fixture übernehmen lässt:

1. Stationen laden.
2. QSOs laden und protokollieren, welche Felder die Instanz liefert —
   vor allem, ob `qsl_sent` dabei ist (davon hängt das Sicherheitsnetz gegen
   Doppeldruck ab).
3. Nur mit `--mark-one ID` und nach Rückfrage: **ein** QSO als
   „Papier-QSL gesendet" markieren. Danach in Wavelog nachsehen.

Aufruf (Token wird abgefragt, nie als Argument übergeben):

    python scripts/wavelog_check.py https://log.example.org
    python scripts/wavelog_check.py https://log.example.org --station 1
    python scripts/wavelog_check.py https://log.example.org --station 1 --mark-one 4886

Alternativ liest es den Token aus der Umgebungsvariablen `WAVELOG_TOKEN`.
Der Bericht (`wavelog_check_bericht.json`) enthält keinen Token, keine
Rufzeichen-Liste und keine Namen — nur Feldnamen, Zähler und ein
anonymisiertes Beispiel-QSO.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qslcards.wavelog import PaperQslMark, WavelogClient, WavelogError  # noqa: E402

# Felder, die im Beispiel-QSO durch Platzhalter ersetzt werden (Datenschutz).
_PRIVATE = {"call", "name", "qth", "address", "email", "gridsquare", "comment", "notes"}


def _anonymize(item: dict) -> dict:
    return {k: ("…" if k.lower() in _PRIVATE and v else v) for k, v in item.items()}


def run(
    url: str,
    token: str,
    *,
    station_id: int | None = None,
    since: str = "",
    mark_one: str = "",
    confirm=input,
    out=print,
    session=None,
) -> dict:
    """Führt die Prüfung aus und liefert den Bericht (auch für Tests)."""
    client = WavelogClient(url, token, session=session)
    report: dict = {"api": None, "stations": 0, "qsos": 0, "fields": [], "qsl_sent": None}

    out("1) Stationen laden …")
    stations = client.stations()
    report["api"] = client.api  # zeigt auch, ob index.php nötig war
    report["stations"] = len(stations)
    for s in stations:
        out(f"   - {s.id}: {s.label}")
    if not stations:
        out("   Keine Stationen – Token-Berechtigung station:read prüfen.")
        return report
    sid = station_id or stations[0].id

    out(f"2) QSOs von Station {sid} laden …")
    # Rohantwort der ersten Seite für die Feldliste (der Client setzt sie um).
    raw_page = client._request(  # noqa: SLF001 - bewusst: Rohfelder sehen
        "GET", "qso", params={"station_id": sid, "per_page": 50, "page": 1}
    )
    items = [i for i in (raw_page.get("data") or []) if isinstance(i, dict)]
    fields = sorted({k for i in items for k in i})
    qsos = client.qsos(sid, since=since)
    report["qsos"] = len(qsos)
    report["fields"] = fields
    report["meta"] = raw_page.get("meta") or {}
    report["qsl_sent"] = "qsl_sent" in fields
    report["example"] = _anonymize(items[0]) if items else None
    out(f"   {len(qsos)} QSOs, Felder: {', '.join(fields) or '–'}")
    if report["qsl_sent"]:
        sent = sum(1 for q in qsos if q.raw.get("qsl_sent", "").upper() == "Y")
        out(f"   qsl_sent wird geliefert ✓ ({sent} als gesendet markiert)")
    else:
        out("   ACHTUNG: qsl_sent fehlt – das Programm kennt dann nur seine eigene Liste.")

    if mark_one:
        out(f"3) QSO {mark_one} als „Papier-QSL gesendet“ markieren?")
        answer = confirm("   Wirklich in Wavelog ändern? [j/N] ").strip().lower()
        if answer in ("j", "ja", "y", "yes"):
            client.mark_paper_sent(PaperQslMark(mark_one, "B"))
            report["marked"] = mark_one
            out("   Markiert. Bitte in Wavelog nachsehen: QSL gesendet = Ja, via Büro.")
        else:
            out("   Nicht markiert.")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", help="Adresse der Wavelog-Instanz")
    parser.add_argument("--station", type=int, default=None, help="Stations-ID")
    parser.add_argument("--since", default="", help="nur QSOs ab JJJJ-MM-TT")
    parser.add_argument("--mark-one", default="", help="ein QSO (ID) testweise markieren")
    parser.add_argument("--report", default="wavelog_check_bericht.json")
    args = parser.parse_args(argv)

    token = os.environ.get("WAVELOG_TOKEN") or getpass.getpass("API-Key (wl2_…): ")
    try:
        report = run(
            args.url, token, station_id=args.station, since=args.since, mark_one=args.mark_one
        )
    except WavelogError as exc:
        print(f"Fehler: {exc}")
        return 1
    Path(args.report).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Bericht: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
