"""config.yaml lesen, schreiben und auf fremde Änderungen prüfen — ohne Tk.

Vorher lag das in `App` verstreut (`_read_config`, `_write_config`,
`_config_mtime`, `_poll_config`, `_reload_from_file`). Die GUI entscheidet nur
noch, was sie mit dem Ergebnis anzeigt.

Die Pfade kommen als Funktionen herein: `gui/app.py` hält `CONFIG_PATH` und
`EXAMPLE_CONFIG_PATH` bewusst als Modulattribute, die Tests setzen sie um.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from qslcards import config as cfg
from qslcards.config import AppConfig


@dataclass
class ReloadResult:
    """Ergebnis von `ConfigFile.reload_if_changed`."""

    # Die neu gelesene Config, oder None (unverändert bzw. unlesbar).
    config: AppConfig | None = None
    # Fehlermeldung, wenn die geänderte Datei nicht lesbar war.
    error: str | None = None


class ConfigFile:
    def __init__(
        self,
        path: Callable[[], str],
        example_path: Callable[[], str] | None = None,
    ) -> None:
        self._path = path
        self._example_path = example_path or (lambda: "")
        self.last_mtime: float | None = None
        # Hinweis, wenn beim Lesen auf die Sicherung zurückgegriffen wurde.
        self.problem: str | None = None

    @property
    def path(self) -> str:
        return self._path()

    def mtime(self) -> float | None:
        try:
            return Path(self._path()).stat().st_mtime
        except OSError:
            return None

    def read(self) -> AppConfig:
        """Liest die Config robust (Sicherung/Beispiel/Defaults, siehe
        `cfg.load_safely`); ein Problem steht danach in `problem`."""
        result = cfg.load_safely(self._path(), self._example_path() or None)
        self.problem = result.problem
        self.last_mtime = self.mtime()
        return result.config

    def take_problem(self) -> str | None:
        """Den Hinweis genau einmal abholen."""
        problem, self.problem = self.problem, None
        return problem

    def save(self, config: AppConfig) -> None:
        """Schreibt atomar; wirft `OSError`. Merkt sich die eigene mtime, damit
        die Überwachung das eigene Speichern nicht für eine fremde Änderung hält."""
        cfg.save(config, self._path())
        self.last_mtime = self.mtime()

    def reload_if_changed(self) -> ReloadResult:
        """Hat jemand anderes die Datei geändert? Dann neu lesen.

        Eine extern halb geschriebene oder verdorbene Datei wird nicht
        übernommen (Werte im Fenster gelten weiter); ihre mtime wird trotzdem
        gemerkt, sonst meldete jeder Poll dasselbe. Der nächste Auto-Save
        repariert sie (Bewertung 3.4).
        """
        mtime = self.mtime()
        if mtime is None or mtime == self.last_mtime:
            return ReloadResult()
        try:
            config = cfg.load(self._path())
        except (OSError, cfg.ConfigError) as exc:
            self.last_mtime = self.mtime()
            return ReloadResult(error=str(exc))
        self.last_mtime = self.mtime()
        return ReloadResult(config=config)
