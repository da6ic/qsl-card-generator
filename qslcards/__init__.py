"""QSL-Karten-Generator: Logbuch (ADIF/Cabrillo) -> QSL-Karten als PDF."""

from __future__ import annotations

# Die Programmversion — hier und nur hier. `pyproject.toml` liest sie über
# `[tool.setuptools.dynamic]` aus, der „Über"-Dialog (Menü „Hilfe") zeigt sie an,
# und `scripts/build_app.py` benennt die Bündel danach. Angehoben wird sie nicht
# von Hand, sondern mit `scripts/release.py patch|minor|major` (das schreibt
# genau diese Zeile, baut und setzt Commit und Tag).
__version__ = "0.3.1"

# Der Name, unter dem das Programm ausgeliefert wird: Programmdatei, `.app`,
# Archivname und die Windows-Dateieigenschaften. `scripts/build_app.py` und
# `packaging/qslcards.spec` lesen ihn beide von hier — liefen sie auseinander,
# suchte das Bauskript das Ergebnis von PyInstaller unter dem falschen Namen.
# Die Texte in der Oberfläche (Fenstertitel, „Über", Menü) stehen bewusst
# weiterhin ausgeschrieben dort, wo sie angezeigt werden.
__app_name__ = "QSL-Karten-Generator"
