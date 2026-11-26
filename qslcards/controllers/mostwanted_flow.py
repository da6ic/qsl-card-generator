"""GDXF-Liste und cty.dat: laden, bei Bedarf abrufen, Status — ohne Tk.

Aus `gui/app.py` herausgezogen (Bewertung 3.1). Die GUI fragt nur noch
`ensure(...)`, zeigt `status()` an und baut nach `on_done` die Karten neu.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from qslcards import dxcc, mostwanted

from .background import Schedule, run_in_background


@dataclass(frozen=True)
class MostWantedPaths:
    ranking: str  # mostwanted.json
    cty: str  # zuletzt abgerufene cty.dat
    bundled_cty: str  # mitgelieferte cty.dat
    dxcc_numbers: str  # Nummerntabelle


def format_date(iso: str | None) -> str:
    """ISO-Zeitstempel (UTC) -> „26.10.2026" in lokaler Zeit; unlesbar -> „?"."""
    try:
        return datetime.fromisoformat(iso or "").astimezone().strftime("%d.%m.%Y")
    except ValueError:
        return "?"


class MostWantedFlow:
    """Hält Rangliste, cty.dat, Abrufzustand und letzten Fehler."""

    def __init__(self, schedule: Schedule, paths: Callable[[], MostWantedPaths]) -> None:
        self._schedule = schedule
        self._paths = paths
        self.ranking: mostwanted.MostWantedList | None = None
        self.cty: dxcc.CtyDatabase | None = None
        self.running = False
        self.error: str | None = None

    # ------------------------------------------------------------ lokal
    def load_local(self) -> None:
        """Gespeicherte Liste und cty.dat lesen (ohne Netz). Eine cty.dat gibt
        es immer: notfalls die mitgelieferte."""
        p = self._paths()
        self.ranking = mostwanted.load(p.ranking)
        self.cty = dxcc.load(p.cty, p.bundled_cty, p.dxcc_numbers)

    def resolve_dxcc(self) -> Callable[[str], int | None] | None:
        return self.cty.dxcc if self.cty is not None else None

    def rule(self, top: int, category: str) -> mostwanted.MostWantedFilter:
        return mostwanted.MostWantedFilter(self.ranking, top=top, category=category)

    # ------------------------------------------------------------ Abruf
    def needs_refresh(self, enabled: bool) -> bool:
        """Nur bei eingeschaltetem Filter und nur, was fehlt oder veraltet ist
        (GDXF nach 30, cty.dat nach 14 Tagen). Wer den Filter nicht nutzt,
        löst keinen Netzzugriff aus."""
        if self.running or not enabled:
            return False
        return mostwanted.is_stale(self.ranking) or dxcc.is_stale(self._paths().cty)

    def ensure(self, enabled: bool, on_done: Callable[[bool], None]) -> bool:
        """Startet den Abruf im Hintergrund, falls nötig. True = gestartet.

        `on_done(cty_changed)` kommt im GUI-Thread; `cty_changed` heißt: neue
        cty.dat, die Karten müssen neu gebaut werden.
        """
        if not self.needs_refresh(enabled):
            return False
        self.running = True
        paths = self._paths()

        def work():
            # Beide `refresh` fangen Netz-, HTTP- und Formatfehler selbst ab (nie
            # fatal) und rufen nur ab, was veraltet ist.
            ranking = mostwanted.refresh(paths.ranking)
            cty = dxcc.refresh(paths.cty, paths.bundled_cty, paths.dxcc_numbers)
            return ranking, cty

        def done(result, error) -> None:
            if error is not None:
                result = (mostwanted.RefreshResult(self.ranking, str(error)), None)
            on_done(self.finish(*result))

        run_in_background(self._schedule, work, done)
        return True

    def finish(
        self, result: mostwanted.RefreshResult, cty: dxcc.CtyRefreshResult | None = None
    ) -> bool:
        """Ergebnis übernehmen. True, wenn eine neue cty.dat da ist."""
        self.running = False
        self.ranking = result.ranking
        self.error = result.error
        if cty is not None and cty.fetched and cty.database is not None:
            self.cty = cty.database
            return True
        return False

    # ------------------------------------------------------------ Anzeige
    def status(self) -> tuple[str, bool]:
        """(Text, ist_Fehler) für die Statuszeile des Most-Wanted-Abschnitts.

        Kurz gehalten: die Zeile steht rechts in einer einzigen Zeile über die
        Fensterbreite, eine längere Fassung lief dort über den Rand.
        """
        ranking = self.ranking
        if self.running:
            return "Lade GDXF-Liste…", False
        if ranking is None and self.error:
            return "GDXF-Liste nicht abrufbar", True
        if ranking is None:
            return "Noch keine GDXF-Liste geladen", False
        date = format_date(ranking.fetched_at)
        if self.error:
            return f"GDXF {ranking.year or '?'} · {date} · Abruf fehlgeschlagen", True
        return f"GDXF {ranking.year or '?'} · abgerufen {date}", False
