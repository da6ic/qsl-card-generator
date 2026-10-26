"""GDXF-Rangliste abrufen und aus dem HTML lesen.

Die GDXF bietet weder API noch CSV — nur die Seite https://gdxf.de/mostwanted/.
Ein einziger POST mit `show=500` („all") liefert alle vier Tabellen auf einmal
(Mixed, CW, Phone, Digital, je ~340 Zeilen, rund 1 MB). Jede Tabelle hat die
Kategorie als `id`, jede Zeile die Spalten

    Rang | Präfix (Link entity.php?entity=N) | Gebiet | needed by (%) | Verlauf …

Die Zahl `N` im Link ist die ADIF-DXCC-Nummer — der Schlüssel, über den der
Filter Karten und Rangliste zusammenbringt.

Bewusst ohne HTML-Bibliothek (wie die Log-Parser): `html.parser` aus der
Standardbibliothek genügt, und der Parser liest nur, was er braucht. Ändert die
GDXF ihr Layout, wirft `parse_html` `MostWantedFormatError` — der Aufrufer
behält dann die zuletzt gespeicherte Liste.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

import requests

from qslcards import __app_name__, __version__

from .models import CATEGORY_TABLE_IDS, MostWantedList, RankedEntity

URL = "https://gdxf.de/mostwanted/index.php"
# `show` ist der Radiobutton „Show Top" der Seite; 500 steht dort für „all".
FORM_DATA = {"show": "500"}
TIMEOUT_S = 20.0
# Wir sagen, wer fragt — die Seite ist ein Angebot der GDXF, keine API.
USER_AGENT = f"{__app_name__}/{__version__}"

_TABLE_IDS = {table_id: code for code, table_id in CATEGORY_TABLE_IDS.items()}
_ENTITY_RE = re.compile(r"entity=(\d+)")
_YEAR_RE = re.compile(r"Most Wanted Ranking\s+(\d{4})")
_UPDATED_RE = re.compile(r"last updated:\s*([^\n<]+)", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


class MostWantedFormatError(ValueError):
    """Die Seite enthält keine lesbare Rangliste (Layout geändert, Fehlerseite)."""


def fetch_html(*, http: requests.Session | None = None, timeout: float = TIMEOUT_S) -> str:
    """Holt die komplette Seite (alle vier Kategorien, alle Ränge).

    Netz-/HTTP-Fehler werden als `requests.RequestException` weitergereicht —
    abgefangen wird eine Ebene höher (`store.refresh`), wo auch entschieden
    wird, was stattdessen gilt.
    """
    session = http if http is not None else requests.Session()
    response = session.post(
        URL, data=FORM_DATA, headers={"User-Agent": USER_AGENT}, timeout=timeout
    )
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def parse_html(text: str) -> MostWantedList:
    """Liest die Ranglisten aus dem HTML der GDXF-Seite.

    Zeilen ohne verwertbaren Rang oder ohne gültigen DXCC-Link werden
    übersprungen, nicht geraten.
    """
    parser = _RankingParser()
    parser.feed(text)
    parser.close()

    rankings: dict[str, dict[int, RankedEntity]] = {}
    for code, rows in parser.tables.items():
        entries: dict[int, RankedEntity] = {}
        for cells, href in rows:
            entry = _row_to_entity(cells, href)
            if entry is not None and entry.dxcc not in entries:
                entries[entry.dxcc] = entry
        if entries:
            rankings[code] = entries
    if not rankings:
        raise MostWantedFormatError("keine Most-Wanted-Tabelle auf der Seite gefunden")

    page_text = "".join(parser.text)
    year = _YEAR_RE.search(page_text)
    updated = _UPDATED_RE.search(page_text)
    return MostWantedList(
        year=int(year.group(1)) if year else None,
        rankings=rankings,
        updated=updated.group(1).strip() if updated else None,
    )


def _row_to_entity(cells: list[str], href: str | None) -> RankedEntity | None:
    if len(cells) < 3 or href is None:
        return None
    match = _ENTITY_RE.search(href)
    rank_text = cells[0].strip()
    if match is None or not rank_text.isdigit():
        return None
    dxcc = int(match.group(1))
    if dxcc <= 0:
        return None
    pct = _PERCENT_RE.search(cells[3]) if len(cells) > 3 else None
    return RankedEntity(
        dxcc=dxcc,
        rank=int(rank_text),
        prefix=cells[1].strip(),
        name=" ".join(cells[2].split()),
        needed_pct=float(pct.group(1).replace(",", ".")) if pct else None,
    )


class _RankingParser(HTMLParser):
    """Sammelt die Zeilen der vier Ranglisten-Tabellen und den Seitentext.

    Zustand pro Tabelle: nur `<tbody>`-Zeilen zählen (der Kopf steht in
    `<thead>` und nutzt `<th>`). Je Zeile die Texte der `<td>` und der erste
    `href` darin (der Link auf das DXCC-Gebiet).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: dict[str, list[tuple[list[str], str | None]]] = {}
        self.text: list[str] = []
        self._table: str | None = None
        self._in_body = False
        self._row: list[str] | None = None
        self._href: str | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self._table = _TABLE_IDS.get(attributes.get("id") or "")
            self._in_body = False
            if self._table is not None:
                self.tables.setdefault(self._table, [])
        elif self._table is None:
            return
        elif tag == "tbody":
            self._in_body = True
        elif tag == "tr" and self._in_body:
            self._row, self._href = [], None
        elif tag == "td" and self._row is not None:
            self._cell = []
        elif tag == "a" and self._row is not None and self._href is None:
            self._href = attributes.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self._table, self._in_body, self._row, self._cell = None, False, None, None
        elif self._table is None:
            return
        elif tag == "tbody":
            self._in_body = False
        elif tag == "td" and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[self._table].append((self._row, self._href))
            self._row, self._href = None, None

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)
