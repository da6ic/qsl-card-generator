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
- **Versandart (Via) je Station automatisch per Lookup bestimmt** (steht nicht im
  Log): Der Lookup liefert die **Menge** akzeptierter Zustellwege — **B** Büro
  (inkl. Manager), **D** Direkt, **Q** eQSL, **L** LOTW. In der GUI priorisiert
  man diese Wege und zieht eine **Trennlinie**: Wege darüber werden gedruckt,
  Wege darunter nicht. Gedruckt wird je Karte der höchstpriorisierte Weg, den die
  Station akzeptiert; einzelne Karten lassen sich in der Vorschau von Hand
  ab-/anwählen.
- Modus wählbar: eine Karte **pro QSO** oder **pro Station**.
- Druckmodus wählbar: **Duplex** (eine PDF) oder **getrennt** (zwei PDFs).
- Lookup über HamQTH (kostenlos) / QRZ (optional) — **automatisch beim Log-Laden**
  im Hintergrund, gecacht. Liefert Via, QSL-Manager (aufs Feld „Via:") und Adresse
  (nur für optionalen Kuvert-/Label-Export, nicht auf der Karte).
- **Menüleiste** (Datei / Bearbeiten / Aktionen / Ansicht / Hilfe) mit den
  gewohnten Tastenkürzeln — ⌘ auf macOS, Strg unter Windows und Linux.
- **Farbthema** in Hell und Dunkel; folgt standardmäßig dem Betriebssystem,
  umschaltbar über „Ansicht → Farbthema".

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
1. (Einmalig) HamQTH-/QRZ-Konto in der Config eintragen — sonst kann die App die
   Versandart nicht nachschlagen (alle Karten fallen auf `default_via`).
2. ADIF-Logbuch wählen und laden — der Lookup startet automatisch im Hintergrund
   und füllt Via/Manager/Adresse; „PDF erzeugen" ist gesperrt, bis er fertig ist.
3. Frontbild wählen, Absenderdaten prüfen (läuft parallel zum Lookup).
4. Zustellwege priorisieren (Liste + Trennlinie) und Kartenmodus wählen.
5. Vorschau prüfen (alle QSOs mit Via/Route), ggf. einzelne Karten ab-/anwählen
   (auch reine eQSL-/LOTW-Stationen manuell aktivierbar); bei Bedarf „Neu abrufen".
6. Druckmodus wählen und „PDF erzeugen".

Logbuch und Frontbild lassen sich auch über die **Menüleiste** öffnen
(`Datei ▸ ADIF-Logbuch öffnen…` / `Frontbild wählen…`, samt „Zuletzt
verwendet"-Listen).

> Der Bereich unten rechts auf der Rückseite (in der Vorlage das Logo) bleibt frei.

## Dokumentation für die Implementierung
- `CLAUDE.md` — Leitfaden für die Umsetzung mit Claude Code.
- `docs/SPECIFICATION.md` — Funktions-/Technik-Spezifikation.
- `docs/CARD_LAYOUT.md` — exaktes Rückseiten-Layout.

## Hinweise
- HamQTH benötigt ein kostenloses Konto und ist die primäre Quelle für die
  Versandart (Büro/Direkt-Flags, Manager). QRZ liefert ohne bezahltes XML-Abo nur
  eingeschränkte Daten (im Wesentlichen den Manager); Lookup-Fehler brechen die
  Erzeugung nie ab — betroffene Stationen fallen dann auf `default_via`.
- Der Signalrapport auf der Karte ist `RST_SENT` (wie wir die Gegenstation gehört
  haben).
- Das Programm-Icon wird aus `qslcards/assets/icons/app_icon.svg` erzeugt. Nach
  einer Änderung am SVG die PNG/ICO/ICNS-Dateien neu rendern:
  `python scripts/make_icon.py`.
