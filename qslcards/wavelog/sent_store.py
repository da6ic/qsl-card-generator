"""Lokale Liste der QSOs, die dieses Programm in Wavelog als gesendet markiert hat.

Sicherheitsnetz: Liefert eine Wavelog-Instanz den Versandstatus (`qsl_sent`)
beim Abruf nicht mit, würden schon verschickte Karten sonst erneut gedruckt.
Die Liste steht neben der config.yaml in `wavelog_sent.json`, je Instanz
(normalisierte API-URL) eine Menge von QSO-IDs.

Seit 0.4.0 stehen dort zusätzlich die **offenen** Markierungen: QSOs, deren
Karten gedruckt, aber (noch) nicht in Wavelog markiert wurden — etwa weil der
Nutzer „erst Probedruck" gewählt hat. So geht „Jetzt markieren" auch nach einem
Neustart noch (Bewertung 2.2).

Dateiformat (Version 2)::

    {"version": 2,
     "sent":    {"<api-url>": ["12", "13"]},
     "pending": {"<api-url>": [{"id": "14", "via": "B"}]}}

Die alte Form (`{"<api-url>": [...]}`) wird weiter gelesen.

**Robustheit** (Bewertung 1.3): geschrieben wird atomar (`fileio`); eine
unlesbare Datei wird **nie** still durch eine leere ersetzt — sonst wäre das
Sicherheitsnetz ohne Hinweis weg. Stattdessen `SentStoreError`, die GUI meldet
es, und die Datei bleibt zur Reparatur liegen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from qslcards.fileio import atomic_write_text

FORMAT_VERSION = 2


class SentStoreError(Exception):
    """`wavelog_sent.json` existiert, ist aber nicht lesbar."""


@dataclass
class PendingMark:
    qso_id: str
    via: str | None = None


@dataclass
class _Data:
    sent: dict[str, list[str]] = field(default_factory=dict)
    pending: dict[str, list[dict]] = field(default_factory=dict)


def _read(path: str | Path) -> _Data:
    path = Path(path)
    if not path.exists():
        return _Data()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SentStoreError(f"{path.name} nicht lesbar: {exc}") from exc
    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise SentStoreError(f"{path.name} ist beschädigt: {exc}") from exc
    if not isinstance(raw, dict):
        raise SentStoreError(f"{path.name} hat ein unerwartetes Format")
    if "version" not in raw:  # alte Form: url -> [ids]
        return _Data(sent={k: list(v) for k, v in raw.items() if isinstance(v, list)})
    sent = raw.get("sent") or {}
    pending = raw.get("pending") or {}
    if not isinstance(sent, dict) or not isinstance(pending, dict):
        raise SentStoreError(f"{path.name} hat ein unerwartetes Format")
    return _Data(
        sent={k: list(v) for k, v in sent.items() if isinstance(v, list)},
        pending={k: list(v) for k, v in pending.items() if isinstance(v, list)},
    )


def _write(path: str | Path, data: _Data) -> None:
    payload = {
        "version": FORMAT_VERSION,
        "sent": {k: v for k, v in data.sent.items() if v},
        "pending": {k: v for k, v in data.pending.items() if v},
    }
    atomic_write_text(path, json.dumps(payload, indent=1, ensure_ascii=False) + "\n")


def _sort_ids(ids: set[str]) -> list[str]:
    return sorted(ids, key=lambda v: (len(v), v))


# ------------------------------------------------------------- gesendet


def load(path: str | Path, api_url: str) -> set[str]:
    """Die als gesendet gemerkten QSO-IDs dieser Instanz.

    Wirft `SentStoreError`, wenn die Datei da, aber kaputt ist — der Aufrufer
    muss dann warnen (das Sicherheitsnetz fehlt), statt leise weiterzumachen.
    """
    ids = _read(path).sent.get(api_url, [])
    return {str(i) for i in ids if str(i).strip()}


def add(path: str | Path, api_url: str, ids: list[str]) -> None:
    """IDs als gesendet merken und aus den offenen Markierungen nehmen."""
    data = _read(path)  # wirft bei kaputter Datei -> nie überschreiben
    known = {str(i) for i in data.sent.get(api_url, [])}
    known.update(str(i) for i in ids)
    data.sent[api_url] = _sort_ids(known)
    done = {str(i) for i in ids}
    data.pending[api_url] = [
        m for m in data.pending.get(api_url, []) if str(m.get("id")) not in done
    ]
    _write(path, data)


def remove(path: str | Path, api_url: str, ids: list[str]) -> None:
    """IDs aus der Liste nehmen (bewusster Nachdruck nach Zurücksetzen)."""
    data = _read(path)
    drop = {str(i) for i in ids}
    data.sent[api_url] = [i for i in data.sent.get(api_url, []) if str(i) not in drop]
    _write(path, data)


# ------------------------------------------------------------ offen


def load_pending(path: str | Path, api_url: str) -> list[PendingMark]:
    marks = []
    for item in _read(path).pending.get(api_url, []):
        if isinstance(item, dict) and str(item.get("id", "")).strip():
            via = item.get("via")
            marks.append(PendingMark(str(item["id"]), str(via) if via else None))
    return marks


def set_pending(path: str | Path, api_url: str, marks: list[PendingMark]) -> None:
    """Ersetzt die offenen Markierungen dieser Instanz."""
    data = _read(path)
    data.pending[api_url] = [{"id": m.qso_id, "via": m.via} for m in marks]
    _write(path, data)
