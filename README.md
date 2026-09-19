# QSL-Karten-Generator

Erzeugt aus einem Logbuch eine PDF mit QSL-Karten. Jede Karte besteht aus
zwei A6-Seiten: einer Bild-Vorderseite (ein Bild für alle Karten) und einer
Rückseite im DARC-QSL-Layout.

## Features
- **Zwei Logformate**: ADIF (`.adi`, `.adif`) aus dem Log-Programm und
  **Cabrillo** (`.cbr`, `.log`) aus dem Contest. Das Format wird am Inhalt
  erkannt, nicht an der Endung. Eigene Parser, kein Fremd-Package.
- Ein Frontbild (png/jpg/…) für alle Karten.
- Rückseite exakt nach Referenz-Layout (`docs/CARD_LAYOUT.md`). Zu lange Werte
  (Name, Antennenbezeichnung, Rufzeichen mit Präfix) werden **kleiner gesetzt,
  nie abgeschnitten** — nichts läuft über seinen Nachbarn.
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
- Lookup über QRZ (erste Wahl) / HamQTH (kostenlos) — **automatisch beim Log-Laden**
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
nur, wie sie aussieht. Die **Lookup-Zugangsdaten sind die Ausnahme**: sie werden
nirgends gespeichert und gelten nur für die laufende Sitzung.

## Ablauf in der GUI
1. QRZ-/HamQTH-Konto in Abschnitt 6 eintragen — sonst kann die App die
   Versandart nicht nachschlagen (alle Karten fallen auf `default_via`). Das ist
   bei **jedem Start** nötig, die Zugangsdaten werden bewusst nicht gespeichert.
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

**Auf macOS entscheidet der Interpreter, wer das Ergebnis starten kann.**
PyInstaller bündelt dessen Bibliotheken, und die tragen sein Deployment-Target;
Homebrew baut immer gegen das laufende System. Für ein Archiv, das weitergegeben
wird, gehört deshalb der Installer von **python.org ab 3.14.7** genommen
(Einrichtung in `packaging/macos/README.md`). Zum Ausprobieren auf dem eigenen
Rechner genügt Homebrew.

### Eine neue Version ausliefern

Die Version steht an **einer** Stelle: `qslcards/__init__.py`. Von dort kommen
der Archivname, `CFBundleShortVersionString` des macOS-Bündels, die
Windows-Dateieigenschaften, der „Über"-Dialog und die pip-Metadaten — und
daneben mit `__app_name__` der Name, unter dem das Programm ausgeliefert wird.

Angehoben wird sie nicht von Hand, sondern mit `scripts/release.py` — dem, was
in einem Node-Projekt `npm version patch` täte (Node und eine `package.json`
gibt es hier nicht; sie wären eine zweite Versionsquelle):

```bash
python scripts/release.py patch       # 0.1.0 -> 0.1.1
python scripts/release.py minor       # 0.1.0 -> 0.2.0
python scripts/release.py major       # 0.1.0 -> 1.0.0
python scripts/release.py 1.2.3       # genau diese Version
python scripts/release.py --show      # nur nachsehen, was gerade gilt
python scripts/release.py patch --dry-run   # den Ablauf zeigen, nichts tun
```

Ein Lauf macht der Reihe nach: **Vorbedingungen** prüfen (saubere Arbeitskopie,
Tag noch frei, neue Version größer als die alte, dazu die Bauprüfungen aus
`build_app.py`) → **Tests** → **Versionszeile** schreiben → **bauen und
verpacken** → **`git commit`** und **`git tag vX.Y.Z`**. Jeder Schritt ist
einzeln abschaltbar (`--no-tests`, `--no-build`, `--no-git`). Ein `git push`
macht das Skript nicht — das bleibt eine bewusste Handlung.

**Gebaut wird vor dem Commit**, anders als bei `npm version` (das den Build in
einen `postversion`-Hook hängt). Am Ergebnis ändert das nichts, am Aufräumen
viel: scheitert der Build, wird die Versionszeile zurückgesetzt und die
Arbeitskopie ist wieder sauber — statt eines Tags für eine Fassung, die es nie
gab.

Für die **anderen Plattformen** gilt weiter: Cross-Compile gibt es nicht.
`release.py` baut nur für das System, auf dem es läuft; die übrigen Archive
entstehen danach dort mit `git pull` und `python scripts/build_app.py --clean`,
die Versionszeile ist dann ja schon committet.

**Cross-Compile gibt es nicht** — PyInstaller bündelt den Interpreter, unter dem
es läuft. Jedes Ziel braucht sein eigenes Betriebssystem:

| Ziel | Gebaut auf | Python | Ergebnis |
|---|---|---|---|
| Windows 64-Bit | Windows (VM genügt) | **3.14.7+** x64 von python.org | `…-windows-x64.zip` |
| Fedora | Fedora 42+ oder der Container in `packaging/linux/` | **`python3.14`** aus den Fedora-Paketen | `…-linux-x86_64.tar.gz` |
| macOS | macOS (Apple Silicon) | Homebrew (mit `tcl-tk`) oder python.org **3.14.7+** | `…-macos-arm64.zip` |

**Die entscheidende Größe ist Tk 9, nicht die Python-Version.** Die
Vorschautabelle zeichnet ihre Stift- und Schaltersymbole aus SVG, was erst Tk 9
kann; mit Tk 8.6 fehlen sie **ohne Fehlermeldung**. Woher Tk kommt, ist
plattformabhängig: im Installer von python.org steckt es mit drin — und dort
zählt die **Punktversion**: erst **3.14.7** bringt Tcl/Tk 9.0.4 mit,
3.14.0–3.14.6 und 3.13 liefern noch 8.6.15. Bei Homebrew und unter Linux hängt
Tk dagegen gar nicht am Interpreter: dort zählt das Paket `tcl-tk` bzw. das
System. Auf Fedora 42 ist Tcl/Tk 9.0 zwar Systempaket, aber sein Standard-Python
3.13 ist gegen die Kompatibilitätspakete `tcl8`/`tk8` gebaut und meldet 8.6 —
gebaut wird dort deshalb mit dem mitgelieferten **`python3.14`**
(`packaging/linux/README.md` zeigt die Messung).
PyInstaller muss **≥ 6.21** sein — davor kann es Tcl/Tk 9 gar nicht bündeln.

**Für Windows reicht auch 6.21.0 noch nicht:** Python 3.14.7 legt die
Tcl-Bibliothek *in die DLL*, und das kennt erst die noch unveröffentlichte
Entwicklungsfassung. `build_app.py` erkennt das und nennt den Ausweg; Einzelheiten
in `packaging/windows/README.md`.

**Windows 32-Bit wird bewusst nicht gebaut** — die Gründe stehen in
`packaging/windows/README.md`. Windows 11 ist 64-Bit-only, und Windows 10 in
32 Bit ist seit Oktober 2025 ohne Support.

Ausführliche Anleitungen samt Prüfliste nach dem Bauen liegen je Plattform
daneben: `packaging/macos/README.md`, `packaging/windows/README.md` und
`packaging/linux/README.md`. Ein eigenes Bauskript hat nur, wo etwas zu
beschaffen ist — Windows `build.ps1` (Interpreter + venv), Linux
`Dockerfile.fedora` (überhaupt ein Fedora); auf macOS genügt `build_app.py`
selbst.

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
- **QRZ wird zuerst gefragt, HamQTH danach.** QRZ liefert ohne bezahltes XML-Abo
  nur eingeschränkte Daten und in keinem Fall die Zustellweg-Flags; HamQTH
  (kostenloses Konto) ist die einzige Quelle dafür. Sind beide Zugangsdaten
  gesetzt, **füllt HamQTH die Lücken** des QRZ-Treffers — QRZ hat bei jedem Feld
  Vorrang, das es selbst füllt. Der Lookup dauert dann etwa doppelt so lange, weil
  fast jede Station bei beiden Anbietern angefragt wird. Lookup-Fehler brechen die
  Erzeugung nie ab — betroffene Stationen fallen dann auf `default_via`.
- Die Zugangsdaten beider Anbieter leben nur zur Laufzeit
  (`lookup.LookupCredentials`) und werden nie in die `config.yaml` geschrieben —
  ein Passwort im Klartext auf der Platte wäre für jeden lesbar, der an den
  Rechner kommt.
- Der Signalrapport auf der Karte ist `RST_SENT` (wie wir die Gegenstation gehört
  haben). In einem Contest-Log fehlt er oft ganz — viele Contests tauschen statt
  eines Rapports einen Locator oder eine Sektion aus; die Spalte bleibt dann leer.
- Das Programm-Icon wird aus `qslcards/assets/icons/app_icon.svg` erzeugt. Nach
  einer Änderung am SVG die PNG/ICO/ICNS-Dateien neu rendern:
  `python scripts/make_icon.py`.
