# QSL-Karten-Generator

Erzeugt aus einem ADIF-Logbuch eine PDF mit QSL-Karten. Jede Karte besteht aus
zwei A6-Seiten: einer Bild-Vorderseite (ein Bild für alle Karten) und einer
Rückseite im DARC-QSL-Layout.

## Features
- Eigener ADIF-Parser (kein Fremd-Package).
- Ein Frontbild (png/jpg/…) für alle Karten.
- Rückseite exakt nach Referenz-Layout (`docs/CARD_LAYOUT.md`).
- Absenderdaten aus `config.yaml`.
- QSO-Daten (Datum, UTC, Frequenz, Mode, Rapport) aus dem Log.
- Via-Filter über `QSL_SENT_VIA`: **B** Büro, **D** Direkt, **E** Elektronisch,
  **M** Manager.
- Modus wählbar: eine Karte **pro QSO** oder **pro Station**.
- Optionaler Adress-Lookup über HamQTH (kostenlos) / QRZ (optional) — nur bei
  Bedarf, gecacht. Nur für Kuvert/Label bei Direkt-Karten, nicht auf der Karte.

## Voraussetzungen
- Python 3.11+
- `pip install -r requirements.txt`
- Ein Frontbild.

## Schnellstart
```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # Absenderdaten anpassen
python -m qslcards.main              # startet die GUI
```

## Ablauf in der GUI
1. ADIF-Logbuch wählen und laden.
2. Frontbild wählen.
3. Absenderdaten prüfen/speichern.
4. Via-Filter und Kartenmodus wählen.
5. (Optional) HamQTH-Konto eintragen, wenn Adressen für Direkt-Karten
   nachgeschlagen werden sollen.
6. Vorschau prüfen, ggf. einzelne Karten abwählen.
7. „PDF erzeugen".

> Der Bereich unten rechts auf der Rückseite (in der Vorlage das Logo) bleibt frei.

## Dokumentation für die Implementierung
- `CLAUDE.md` — Leitfaden für die Umsetzung mit Claude Code.
- `docs/SPECIFICATION.md` — Funktions-/Technik-Spezifikation.
- `docs/CARD_LAYOUT.md` — exaktes Rückseiten-Layout.

## Hinweise
- HamQTH benötigt ein kostenloses Konto. QRZ liefert ohne bezahltes XML-Abo nur
  eingeschränkte Daten; Lookup-Fehler brechen die Erzeugung nie ab.
- Der Signalrapport auf der Karte ist `RST_SENT` (wie wir die Gegenstation gehört
  haben).
