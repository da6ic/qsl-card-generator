"""Einstiegspunkt: startet die Tkinter-GUI.

Start:
    python -m qslcards.main
"""

from __future__ import annotations


def main() -> None:
    from qslcards.gui.app import App

    App().mainloop()


if __name__ == "__main__":
    main()
