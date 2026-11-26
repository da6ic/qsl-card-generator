"""Abläufe ohne Tk: was die GUI anstößt, aber nicht selbst wissen muss.

Hier liegen die Teile, die aus `gui/app.py` herausgezogen wurden (Bewertung
3.1): sie kennen keine Widgets, bekommen eine `schedule`-Funktion für den
Rückweg in den GUI-Thread und sind deshalb ohne Xvfb testbar.
"""
