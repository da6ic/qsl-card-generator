"""Lokale Liste der QSOs, die dieses Programm in Wavelog als gesendet markiert hat.

Sicherheitsnetz: Liefert eine Wavelog-Instanz den Versandstatus (`qsl_sent`)
beim Abruf nicht mit, würden schon verschickte Karten sonst erneut gedruckt.
Die Liste steht neben der config.yaml in `wavelog_sent.json`, je Instanz (API-URL)
eine Menge von QSO-IDs. Lesefehler sind nie fatal: dann gilt die Liste als leer.
"""

from __future__ import annotations

import json
from pathlib import Path


def load(path: str | Path, api_url: str) -> set[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    ids = data.get(api_url, []) if isinstance(data, dict) else []
    return {str(i) for i in ids if str(i).strip()}


def add(path: str | Path, api_url: str, ids: list[str]) -> None:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    known = {str(i) for i in data.get(api_url, [])}
    known.update(str(i) for i in ids)
    data[api_url] = sorted(known, key=lambda v: (len(v), v))
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
