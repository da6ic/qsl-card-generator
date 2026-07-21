"""Seitenmaße und Layout-Konstanten (siehe docs/CARD_LAYOUT.md).

Hier stehen ALLE Layout-Zahlen als benannte Konstanten (CLAUDE.md §7). Diese
Datei wird in Build-Schritt 4 vervollständigt; vorerst nur die Konstanten, die
bereits von der Kartenlogik (`cards/builder.py`) benötigt werden.
"""

from __future__ import annotations

# Maximale Anzahl Datenzeilen pro Karte (CARD_LAYOUT.md: Datenzeilen MAX_ROWS = 3).
# Überschüssige Zeilen im Modus "pro Station" erzeugen Folge-Karten.
MAX_ROWS = 3
