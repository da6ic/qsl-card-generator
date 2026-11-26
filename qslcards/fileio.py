"""Dateien absturzsicher schreiben.

Gemeinsam für `config.yaml` und `wavelog_sent.json` (Bewertung 1.2/1.3): beide
wurden direkt überschrieben, ein Absturz oder Stromausfall hinterließ eine
leere oder halbe Datei.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: str | Path, text: str) -> None:
    """Schreibt `text` so, dass `path` nie halb geschrieben zurückbleibt.

    Erst in eine temporäre Datei im **selben** Ordner (sonst ist `os.replace`
    kein atomarer Umbenenner), `fsync`, dann ersetzen. Fällt mittendrin der
    Strom aus, liegt am Ziel entweder die alte oder die neue Fassung.
    """
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        try:  # Rechte der bisherigen Datei übernehmen (mkstemp legt 0600 an)
            os.chmod(tmp, path.stat().st_mode & 0o777)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
