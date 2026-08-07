# QSL-Karten-Generator

Erzeugt aus einem Logbuch eine PDF mit QSL-Karten. Jede Karte besteht aus
zwei A6-Seiten: einer Bild-Vorderseite (ein Bild für alle Karten) und einer
Rückseite im DARC-QSL-Layout.

## Features
- **Zwei Logformate**: ADIF (`.adi`, `.adif`) aus dem Log-Programm und
  **Cabrillo** (`.cbr`, `.log`) aus dem Contest. Das Format wird am Inhalt
  erkannt, nicht an der Endung. Eigene Parser, kein Fremd-Package.
- Ein Frontbild (png/jpg/…) für alle Karten.
- Rückseite exakt nach Referenz-Layout (`docs/CARD_LAYOUT.md`).
- Absenderdaten aus der Config (im Programm eingetragen, nie aus dem Log).
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
- **Bogendruck**: wahlweise eine Karte je A6-Seite oder **vier Karten auf einem
  A4-Bogen** (quer, 2×2) mit gestrichelten Schnitt-Hilfslinien; der einstellbare
  Druckrand gilt dabei je Karte, jede geschnittene Karte hat ihn ringsum.
- Lookup über HamQTH (kostenlos) / QRZ (optional) — **automatisch beim Log-Laden**
  im Hintergrund, gecacht. Liefert Via, QSL-Manager (aufs Feld „Via:") und Adresse
  (nur für optionalen Kuvert-/Label-Export, nicht auf der Karte).
- **Menüleiste** (Datei / Bearbeiten / Aktionen / Ansicht / Hilfe) mit den
  gewohnten Tastenkürzeln — ⌘ auf macOS, Strg unter Windows und Linux.
- **Handbuch im Programm** (`Hilfe ▸ Handbuch`, F1 bzw. ⌘?): Kapitel zu jedem
  Arbeitsschritt, links eine Kapitelliste, Verweise sind anklickbar. Jeder
  Abschnitt der Oberfläche hat ein „?", das direkt sein Kapitel öffnet.
- **Farbthema** in Hell und Dunkel; folgt standardmäßig dem Betriebssystem,
  umschaltbar über „Ansicht → Farbthema".

## Voraussetzungen
- Python 3.11+ (zum **Bündeln** siehe unten: dort zählt Tk 9)
- `pip install -r requirements.txt`
- Ein Frontbild.

## Schnellstart
```bash
pip install -r requirements.txt
python -m qslcards               # startet die GUI
```

Absenderdaten, Zugangsdaten und alles Weitere trägt man **im Programmfenster**
ein; die `config.yaml` entsteht dabei von selbst und wird bei jeder Änderung
gespeichert. Von Hand bearbeitet wird sie nicht — `config.example.yaml` zeigt
nur, wie sie aussieht.

## Ablauf in der GUI
1. (Einmalig) HamQTH-/QRZ-Konto in Abschnitt 6 eintragen — sonst kann die App die
   Versandart nicht nachschlagen (alle Karten fallen auf `default_via`).
2. Logbuch wählen und laden — der Lookup startet automatisch im Hintergrund
   und füllt Via/Manager/Adresse; „PDF erzeugen" ist gesperrt, bis er fertig ist.
3. Frontbild wählen, Absenderdaten prüfen (läuft parallel zum Lookup).
4. Zustellwege priorisieren (Liste + Trennlinie) und Kartenmodus wählen.
5. Vorschau prüfen (alle QSOs mit Via/Route), ggf. einzelne Karten ab-/anwählen
   (auch reine eQSL-/LOTW-Stationen manuell aktivierbar); bei Bedarf „Neu abrufen".
6. Druckmodus wählen und „PDF erzeugen".

Mit einem roten `*` markierte Angaben sind **Pflicht**: Logbuch, Frontbild und im
Absender Rufzeichen, Name, Locator, DOK, CQ-Zone und ITU. Fehlt davon etwas,
nennt ein Hinweis beim Erzeugen alles Fehlende auf einmal und markiert die
betroffenen Felder.

Logbuch und Frontbild lassen sich auch über die **Menüleiste** öffnen
(`Datei ▸ Logbuch öffnen…` / `Frontbild wählen…`, samt „Zuletzt
verwendet"-Listen).

> Der Bereich unten rechts auf der Rückseite (in der Vorlage das Logo) bleibt frei.

## Bauen (auslieferbare Anwendung)

```bash
pip install -e ".[build]"
python scripts/build_app.py --clean
```

Ergebnis in `dist/`: ein Programmordner plus ein Archiv, benannt nach Version und
Plattform. Das Skript prüft vorher die Voraussetzungen und bricht mit Klartext ab,
statt still etwas Kaputtes zu bauen.

**Cross-Compile gibt es nicht** — PyInstaller bündelt den Interpreter, unter dem
es läuft. Jedes Ziel braucht sein eigenes Betriebssystem:

| Ziel | Gebaut auf | Python | Ergebnis |
|---|---|---|---|
| Windows 64-Bit | Windows (VM genügt) | **3.14.7+** x64 von python.org | `…-windows-x64.zip` |
| Fedora | Fedora 42+ oder der Container in `packaging/linux/` | System-Python 3.13+ | `…-linux-x86_64.tar.gz` |
| macOS | macOS (Apple Silicon) | Homebrew oder python.org **3.14.7+** | `…-macos-arm64.zip` |

**Die entscheidende Größe ist Tk 9, nicht die Python-Version.** Die
Vorschautabelle zeichnet ihre Stift- und Schaltersymbole aus SVG, was erst Tk 9
kann; mit Tk 8.6 fehlen sie **ohne Fehlermeldung**. Woher Tk kommt, ist
plattformabhängig: unter Windows und macOS steckt es im Python-Installer — und
dort zählt die **Punktversion**: erst **3.14.7** bringt Tcl/Tk 9.0.4 mit,
3.14.0–3.14.6 und 3.13 liefern noch 8.6.15. Unter Linux kommt Tk vom System
(Fedora 42+ hat Tcl/Tk 9.0, dort genügt das mitgelieferte Python 3.13).
PyInstaller muss **≥ 6.21** sein — davor kann es Tcl/Tk 9 gar nicht bündeln.

**Für Windows reicht auch 6.21.0 noch nicht:** Python 3.14.7 legt die
Tcl-Bibliothek *in die DLL*, und das kennt erst die noch unveröffentlichte
Entwicklungsfassung. `build_app.py` erkennt das und nennt den Ausweg; Einzelheiten
in `packaging/windows/README.md`.

**Windows 32-Bit wird bewusst nicht gebaut** — die Gründe stehen in
`packaging/windows/README.md`. Windows 11 ist 64-Bit-only, und Windows 10 in
32 Bit ist seit Oktober 2025 ohne Support.

Ausführliche Anleitungen samt Prüfliste nach dem Bauen:
`packaging/windows/README.md` und `packaging/linux/README.md`.

## Dokumentation

Für **Anwender**: `handbuch.md` im Programmordner — dieselbe Datei, die
`Hilfe ▸ Handbuch` im Programm anzeigt. Eine ganz normale Textdatei; wer mag,
liest oder ergänzt sie im Editor, das Fenster übernimmt Änderungen beim nächsten
Blick.

Für die **Implementierung**:
- `CLAUDE.md` — Leitfaden für die Umsetzung mit Claude Code.
- `docs/SPECIFICATION.md` — Funktions-/Technik-Spezifikation.
- `docs/CARD_LAYOUT.md` — exaktes Rückseiten-Layout.

## Hinweise
- HamQTH benötigt ein kostenloses Konto und ist die primäre Quelle für die
  Versandart (Büro/Direkt-Flags, Manager). QRZ liefert ohne bezahltes XML-Abo nur
  eingeschränkte Daten (im Wesentlichen den Manager); Lookup-Fehler brechen die
  Erzeugung nie ab — betroffene Stationen fallen dann auf `default_via`.
- Der Signalrapport auf der Karte ist `RST_SENT` (wie wir die Gegenstation gehört
  haben). In einem Contest-Log fehlt er oft ganz — viele Contests tauschen statt
  eines Rapports einen Locator oder eine Sektion aus; die Spalte bleibt dann leer.
- Das Programm-Icon wird aus `qslcards/assets/icons/app_icon.svg` erzeugt. Nach
  einer Änderung am SVG die PNG/ICO/ICNS-Dateien neu rendern:
  `python scripts/make_icon.py`.
