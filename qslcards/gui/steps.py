"""Die Schritte des Assistenten und wo die alten Abschnitte jetzt stehen."""

from __future__ import annotations

from .wizard import Step

# Reihenfolge = Arbeitsablauf.
STEP_SOURCE, STEP_SENDER, STEP_LOOKUP, STEP_CARDS, STEP_REVIEW, STEP_PRINT = range(6)
WIZARD_STEPS = [
    Step(
        "source",
        "Quelle",
        "Woher kommen die QSOs?",
        "Logdatei öffnen oder die QSOs direkt aus Wavelog holen.",
    ),
    Step(
        "sender",
        "Absender",
        "Deine Station",
        "Diese Angaben stehen als Absender auf jeder Karte. Sie werden gespeichert.",
    ),
    Step(
        "lookup",
        "Abfrage",
        "Zustellwege abfragen",
        "Mit QRZ/HamQTH erfährt das Programm, wie jede Station QSL-Karten möchte. "
        "Ohne Zugangsdaten gehen alle Karten über das Büro.",
    ),
    # Früher ein Schritt „Karten" mit Bild, Bemerkungen, Most Wanted UND
    # Vorschau — die Tabelle zeigte dort nur ~6 Zeilen in einer selbst
    # scrollenden Seite (Bewertung 2.5). Jetzt zwei Schritte; „Prüfen" gibt
    # der Tabelle die ganze Höhe und scrollt außen nicht.
    Step(
        "cards",
        "Gestalten",
        "Karten gestalten",
        "Frontbild wählen, Bemerkungen setzen und auf Wunsch nur Most Wanted drucken.",
    ),
    Step(
        "review",
        "Prüfen",
        "Karten prüfen",
        "In der Vorschau festlegen, welche Karten gedruckt werden. "
        "Ein Klick auf „Drucken“ schaltet eine Zeile um.",
    ),
    Step("print", "Druck", "Drucken und exportieren", "Druckart wählen und die PDF erzeugen."),
]
# Abschnittsnummer (Handbuch/Menü) -> Schritt, auf dem der Abschnitt steht.
SECTION_STEP = {1: 0, 2: 3, 3: 1, 4: 2, 5: 2, 6: 2, 7: 3, 8: 3, 9: 4, 10: 5, 11: 5}
