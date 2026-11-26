"""Einstiegspunkt: startet die Tkinter-GUI.

Start:
    python -m qslcards
    python -m qslcards.main
"""

from __future__ import annotations

import io
import logging
import sys
from logging.handlers import RotatingFileHandler

from qslcards import paths
from qslcards.redact import RedactingFilter

# Größe der Protokolldatei, bevor sie umgeschichtet wird, und Anzahl der
# aufbewahrten Sicherungen.
LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 2


def _prepare_frozen_runtime() -> None:
    """Macht die gebündelte Anwendung diagnosefähig.

    Ein Fensterprogramm ohne Konsole hat **keine** Standardausgabe — unter
    Windows ist `sys.stderr` sogar `None`. Zwei Folgen, beide unangenehm:

    * Die `logger.warning`-Meldungen aus `lookup/cache.py` & Co. verschwinden
      spurlos; im Fehlerfall ist nichts nachvollziehbar.
    * Tks `report_callback_exception` schreibt Ausnahmen aus Callbacks auf
      `stderr` und liefe damit gegen `None.write()` — aus einem behebbaren
      Fehler würde ein zweiter, verwirrender.

    Deshalb: fehlende Ströme durch Attrappen ersetzen und ins Protokoll im
    Datenordner schreiben (`paths.log_path`).
    """
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            setattr(sys, name, io.StringIO())

    try:
        handler: logging.Handler = RotatingFileHandler(
            paths.log_path(),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUPS,
            encoding="utf-8",
        )
    except OSError:  # Nur-Lese-Medium o. Ä. — kein Grund, nicht zu starten.
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    # Sicherheitsnetz: keine Zugangsdaten in der Protokolldatei (qslcards.redact).
    handler.addFilter(RedactingFilter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def main() -> None:
    if paths.is_frozen():
        # Erst den Datenordner bereitstellen (dorthin geht auch das Protokoll).
        paths.ensure_data_dir()
        _prepare_frozen_runtime()

    from qslcards.gui.app import App

    App().mainloop()


if __name__ == "__main__":
    main()
