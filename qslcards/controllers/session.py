"""Zustand einer Arbeitssitzung ohne Tk (Bewertung 3.1).

Was geladen ist und was daraus folgt — die GUI zeigt es nur an. Vorher lagen
diese Felder lose in `App` und jede Funktion pflegte sie selbst (so entstand
das Lookup-Rennen aus 1.4).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from qslcards.cards.builder import effective_via
from qslcards.cards.models import Card
from qslcards.logbook.models import QSO
from qslcards.lookup import LookupResult
from qslcards.wavelog import PaperQslMark


@dataclass
class SessionState:
    # Offene QSOs (bekommen eine Karte).
    qsos: list[QSO] = field(default_factory=list)
    # Schon gesendete (nur für einen bewussten Nachdruck einblendbar).
    sent_qsos: list[QSO] = field(default_factory=list)
    # Woher die QSOs stammen: "file" | "wavelog" | None.
    source: str | None = None
    # CALL -> LookupResult|None (None = nachgeschlagen, nichts gefunden).
    lookups: dict[str, LookupResult | None] = field(default_factory=dict)
    # Wavelog-QSOs, deren Karten gedruckt, aber noch nicht markiert sind.
    pending_marks: list[PaperQslMark] = field(default_factory=list)

    # ------------------------------------------------------------ Laden
    def load(self, qsos: Iterable[QSO], source: str, is_sent: Callable[[QSO], bool]) -> None:
        """Neue QSOs übernehmen: aufteilen in offen/gesendet, Lookups verwerfen."""
        self.qsos, self.sent_qsos = split_already_sent(qsos, is_sent)
        self.source = source
        self.lookups = {}

    # ------------------------------------------------------------ Abfragen
    def visible_qsos(self, show_sent: bool) -> list[QSO]:
        return [*self.qsos, *self.sent_qsos] if show_sent else list(self.qsos)

    def has_any(self) -> bool:
        return bool(self.qsos or self.sent_qsos)

    def missing_lookups(self, show_sent: bool) -> list[str]:
        """Rufzeichen der angezeigten QSOs, die noch gar nicht nachgeschlagen sind."""
        return [
            q.call
            for q in self.visible_qsos(show_sent)
            if (q.call or "").strip().upper() not in self.lookups
        ]

    # ------------------------------------------------------------ Markieren
    def mark_sent(self, qso_ids: Iterable[str]) -> None:
        """In Wavelog markierte QSOs von „offen" nach „gesendet" verschieben."""
        gone = {str(i) for i in qso_ids}
        moved = [q for q in self.qsos if q.raw.get("wavelog_id") in gone]
        self.qsos = [q for q in self.qsos if q.raw.get("wavelog_id") not in gone]
        self.sent_qsos += moved
        self.pending_marks = [m for m in self.pending_marks if m.qso_id not in gone]

    def add_pending(self, marks: Iterable[PaperQslMark]) -> None:
        merged = {m.qso_id: m for m in self.pending_marks}
        for mark in marks:
            merged[mark.qso_id] = mark
        self.pending_marks = list(merged.values())


def split_already_sent(
    qsos: Iterable[QSO], is_sent: Callable[[QSO], bool]
) -> tuple[list[QSO], list[QSO]]:
    """(offen, schon gesendet) — Reihenfolge bleibt erhalten."""
    open_, sent = [], []
    for qso in qsos:
        (sent if is_sent(qso) else open_).append(qso)
    return open_, sent


def marks_for_cards(cards: Iterable[Card], active_priority: list[str]) -> list[PaperQslMark]:
    """Die Wavelog-QSOs gedruckter Karten, mit dem Zustellweg fürs Markieren.

    * Nachdruck-Karten (`already_sent`) werden nicht erneut markiert.
    * eQSL/LoTW sind keine Papierkarten und werden nie als „Papier-QSL
      gesendet" markiert (Bewertung 2.2).
    * Büro mit Manager-Rufzeichen -> „M", sonst „B"/„D".
    """
    marks: dict[str, PaperQslMark] = {}
    for card in cards:
        if card.already_sent:
            continue
        route = effective_via(card, active_priority)
        if route not in ("B", "D"):
            continue
        via = "M" if card.via_text and route == "B" else route
        for row in card.rows:
            if row.qso_id:
                marks[row.qso_id] = PaperQslMark(row.qso_id, via)
    return list(marks.values())
