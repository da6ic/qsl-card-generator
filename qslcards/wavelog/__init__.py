"""Wavelog-Anbindung (API v2): Stationen laden, QSOs holen, Papier-QSL markieren.

Wavelog (https://www.wavelog.org) ist ein webbasiertes Logbuch. Ab Version 3.2.5
bietet die API v2 alles, was der Generator braucht:

* ``GET  /api/v2/station``          — Stationsstandorte (Dropdown im Assistenten)
* ``GET  /api/v2/qso``              — QSOs eines Standorts (seitenweise)
* ``PATCH /api/v2/qso/{id}``        — ``qsl_sent = "Y"`` nach dem Kartendruck

Angemeldet wird mit der Basis-URL der Instanz und einem API-v2-Token
(``wl2_…``, Bereiche ``station:read``, ``qso:read`` und zum Markieren
``qso:write``). Der Token wird nie in die config.yaml geschrieben; auf Wunsch
legt ``secret`` ihn im Schlüsselbund des Betriebssystems ab.
"""

from .client import (
    PaperQslMark,
    WavelogClient,
    WavelogError,
    WavelogStation,
    normalize_base_url,
    qso_from_json,
)

__all__ = [
    "PaperQslMark",
    "WavelogClient",
    "WavelogError",
    "WavelogStation",
    "normalize_base_url",
    "qso_from_json",
]
