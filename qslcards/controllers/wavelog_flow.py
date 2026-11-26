"""Wavelog-Ablauf ohne Tk: Client, Hintergrundabruf, Sicherheitsnetz.

Aus `gui/app.py` herausgezogen (Bewertung 3.1). Hier steht, was beim Laden,
Drucken und Markieren *gilt*; die GUI zeigt nur Knöpfe, Hinweise und Status.

* `WavelogFlow` hält den Client (wiederverwendet, weil `stations()` lernen
  kann, dass die Instanz ohne `index.php` antwortet), die geladenen Stationen,
  den Besetzt-Zustand und den Pfad zu `wavelog_sent.json`.
* `prepare_load` entscheidet, welche QSOs schon gesendet sind und welche
  Warnungen der Nutzer sehen muss.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from qslcards import wavelog
from qslcards.logbook.models import QSO
from qslcards.wavelog import PaperQslMark, sent_store
from qslcards.wavelog.client import paper_qsl_already_sent, reports_qsl_sent

from .background import Schedule, run_in_background


@dataclass
class LoadPlan:
    """Was beim Übernehmen geladener Wavelog-QSOs gilt."""

    is_sent: Callable[[QSO], bool]
    # Offene Markierungen aus einem früheren Druck (auch nach Neustart).
    pending: list[PaperQslMark] = field(default_factory=list)
    # Hinweise für Schritt 1 (leer = alles gut).
    warnings: list[str] = field(default_factory=list)
    # `wavelog_sent.json` unlesbar: nie überschreiben, Hinweis als Fehler zeigen.
    store_broken: bool = False
    # Anzahl der selbst markierten (für den Hinweis ohne Versandstatus).
    marked_count: int = 0
    # Liefert die Instanz `qsl_sent` überhaupt mit?
    status_known: bool = True


def missing_status_warning(marked: int, open_count: int) -> str:
    return (
        f"Achtung: Diese Wavelog-Instanz meldet den Versandstatus nicht mit. "
        f"Ausgelassen werden nur die {marked} QSO(s), die dieses Programm "
        f"selbst markiert hat. Wurden QSOs in Wavelog von Hand oder von einem "
        f"anderen Rechner als gesendet gesetzt, stehen sie unter den "
        f"{open_count} geladenen und würden noch einmal gedruckt."
    )


class WavelogFlow:
    def __init__(self, schedule: Schedule, sent_path: Callable[[], str]) -> None:
        self._schedule = schedule
        self._sent_path = sent_path
        self._client: tuple[tuple[str, str], wavelog.WavelogClient] | None = None
        self.stations: list[wavelog.WavelogStation] = []
        self.busy = False
        # `wavelog_sent.json` beim letzten Laden unlesbar -> nichts hineinschreiben.
        self.store_broken = False

    # ------------------------------------------------------------ Client
    def client(self, url: str, key: str) -> wavelog.WavelogClient:
        """Derselbe Client, solange sich Adresse und Key nicht ändern.
        Wirft `WavelogError` bei unbrauchbarer Adresse."""
        if self._client is not None and self._client[0] == (url, key):
            return self._client[1]
        client = wavelog.WavelogClient(url, key)
        self._client = ((url, key), client)
        return client

    @staticmethod
    def api_url(url: str) -> str:
        """Normalisierte Adresse (Schlüssel in `wavelog_sent.json`), "" wenn unbrauchbar."""
        try:
            return wavelog.normalize_base_url(url)
        except wavelog.WavelogError:
            return ""

    def run(
        self,
        client: wavelog.WavelogClient,
        work: Callable[[wavelog.WavelogClient], Any],
        done: Callable[[Any, wavelog.WavelogError | None], None],
    ) -> None:
        """`work(client)` im Hintergrund, `done(result, error)` im GUI-Thread.
        Jeder Fehler kommt als `WavelogError` an."""
        self.busy = True

        def finish(result, error) -> None:
            self.busy = False
            done(result, error)

        run_in_background(
            self._schedule,
            lambda: work(client),
            finish,
            wrap_error=lambda exc: (
                exc if isinstance(exc, wavelog.WavelogError) else wavelog.WavelogError(str(exc))
            ),
        )

    def station(self, station_id: str | None) -> wavelog.WavelogStation | None:
        return next((s for s in self.stations if s.id == station_id), None)

    # ------------------------------------------------------------ Laden
    def prepare_load(self, qsos: Sequence[QSO], url: str) -> LoadPlan:
        """Schon gesendet ist, was Wavelog als gesendet meldet **oder** was
        dieses Programm selbst dort markiert hat (falls die Instanz den Status
        beim Abruf nicht mitliefert)."""
        api = self.api_url(url)
        warnings: list[str] = []
        broken = False
        try:
            path = self._sent_path()
            marked = sent_store.load(path, api)
            pending = sent_store.load_pending(path, api)
        except sent_store.SentStoreError as exc:
            # Nie still weitermachen: ohne die Liste fehlt das Sicherheitsnetz.
            marked, pending, broken = set(), [], True
            warnings.append(
                f"Die Liste der hier markierten QSOs ist beschädigt ({exc}). Sie wird "
                "nicht überschrieben; bis zur Reparatur fehlt das Sicherheitsnetz."
            )
        self.store_broken = broken

        def is_sent(q: QSO) -> bool:
            return paper_qsl_already_sent(q) or q.raw.get("wavelog_id") in marked

        return LoadPlan(
            is_sent=is_sent,
            pending=[PaperQslMark(m.qso_id, m.via) for m in pending],
            warnings=warnings,
            store_broken=broken,
            marked_count=len(marked),
            status_known=not qsos or reports_qsl_sent(qsos),
        )

    # ------------------------------------------------------------ Markieren
    def save_pending(self, url: str, marks: Iterable[PaperQslMark]) -> None:
        """Offene Markierungen sichern (überlebt Neustart). Wirft `OSError`/
        `SentStoreError`; bei kaputter Liste wird nichts geschrieben."""
        if self.store_broken:
            return
        sent_store.set_pending(
            self._sent_path(),
            self.api_url(url),
            [sent_store.PendingMark(m.qso_id, m.via) for m in marks],
        )

    def record_marked(self, url: str, ids: list[str]) -> None:
        """In Wavelog markierte IDs merken (Sicherheitsnetz für den nächsten Abruf).
        Wirft `OSError`/`SentStoreError`."""
        sent_store.add(self._sent_path(), self.api_url(url), ids)
