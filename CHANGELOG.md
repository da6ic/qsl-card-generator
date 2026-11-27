# Änderungen

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).
Versionsnummern setzt `scripts/release.py`, nie die Hand.

## [Unveröffentlicht]

### Neu
- **Windows-Installer** (`…-windows-x64-setup.exe`, Inno Setup,
  `packaging/windows/installer.iss`): ohne Adminrechte, Startmenü-Eintrag,
  Deinstallation über *Apps*, Update über die alte Fassung. Das ZIP bleibt für
  den Einsatz ohne Installation.

### Doku
- README: Abschnitt „Installation" mit Installer, apt-/dnf-Befehlen, AppImage
  und macOS; Release-Workflow und die Dateien eines Releases beschrieben.
- Handbuch, Kapitel „Installieren und weitergeben": Installer, apt, dnf, AppImage.
- `packaging/windows/README.md`: PyInstaller ≥ 6.22 statt `develop`.

## [0.4.0] – 2026-11-26

Freigegeben nach dem Test gegen eine echte Wavelog-Instanz. Erste Fassung, die
der Release-Workflow für Windows, macOS und Linux baut.

### Neu
- **Release-Workflow** (`.github/workflows/release.yml`): ein Tag `vX.Y.Z`
  baut Windows (ZIP), macOS (DMG + ZIP), Linux (AppImage, .deb, .rpm, tar.gz)
  mit Tcl/Tk 9 und legt sie als GitHub-Release ab. Dazu ein signiertes
  **APT-/DNF-Repository auf GitHub Pages** (`packaging/repo/`), Installation per
  `apt install`/`dnf install qsl-karten-generator`.
- **Schritt-Assistent** statt einer langen Seite, sechs Schritte: Quelle,
  Absender, Abfrage, Gestalten, Prüfen, Druck. Farbschema aus einer Grundfarbe
  abgeleitet, hell und dunkel.
- **Wavelog als Quelle** (API v2): Stationen laden, QSOs eines Standorts holen,
  nach dem Druck „Papier-QSL gesendet" setzen (mit Rückfrage, auch später über
  „Jetzt markieren", auch nach Neustart). API-Key optional im Schlüsselbund.
- **DARC-QR-Code** auf der Rückseite (Schalter beim Druckmodus).
- **Schon gesendete QSLs** (`QSL_SENT = Y`, auch aus ADIF) bekommen keine Karte;
  „Schon gesendete anzeigen" in der Vorschau erlaubt einen bewussten Nachdruck.
- Lookup: **Abbrechen**-Knopf, Fortschritt mit Restzeit.
- QRZ-/HamQTH-Zugänge optional **im Schlüsselbund** merken (Standard: aus).
- `scripts/wavelog_check.py`: prüft eine echte Wavelog-Instanz (Felder,
  `qsl_sent`), markiert auf Wunsch genau ein QSO.
- CI für GitLab und GitHub (Tk 9, ruff, black, pytest unter Xvfb).

### Behoben
- Gebündeltes Programm startete nicht mehr („No module named
  'reportlab.graphics.barcode.code128'"): der QR-Code zieht alle Barcode-Module
  dynamisch nach, die Spec nimmt sie jetzt mit. Linux-Bündel mit einem Python
  aus python-build-standalone (uv) bekommen `libtcl9.0.so`/`libtcl9tk9.0.so`
  ausdrücklich mit — PyInstaller fand sie dort nicht.
- HamQTH-/QRZ-**Passwörter standen bei Netzfehlern im Protokoll** (aus der URL
  in der Fehlermeldung). Jetzt maskiert; ein Filter am Protokoll fängt den Rest.
  Wer eine alte `qslcards.log` hat, sollte sie löschen.
- **Kaputte `config.yaml`** brachte den Start zum Absturz, eine leere löschte
  beim nächsten Speichern alle Absenderdaten. Jetzt: atomar speichern,
  `config.yaml.bak`, beim Laden Rückfall auf die Sicherung mit Hinweis.
- **Log-Wechsel während eines Lookups**: das neue Log wurde nie nachgeschlagen
  und bekam Ergebnisse des alten. Jetzt wird der alte Lauf abgebrochen und das
  neue Log nachgeschlagen.
- `wavelog_sent.json` und Lookup-Cache werden atomar geschrieben; eine kaputte
  Liste wird gemeldet und nie still durch eine leere ersetzt.
- Karten über **eQSL/LoTW** wurden in Wavelog als Papier-QSL markiert.
- Wavelog: bei **429** wird gewartet statt abgebrochen, Abstand zwischen den
  Markierungen, Statuscodes statt Textsuche, abgelaufener Token wird benannt,
  Seitenlimit gegen Endlosschleife, `index.php` optional, Warnung bei `http://`
  ins Internet, Datumsfelder werden lokal geprüft.

### Geändert
- Die Vorschau hat einen eigenen Schritt und nutzt die ganze Höhe (kein
  doppelter Scrollbalken mehr).
- Fehlende Pflichtangaben: kein Popup mehr, die Leiste unten nennt sie.
- `Bild.jpg` (3,2 MB) aus dem Repository entfernt, kleines Beispielbild unter
  `docs/`.
- Intern: `gui/app.py` aufgeteilt (1.943 -> ~950 Zeilen). Zustand, Lookup,
  Most Wanted, Wavelog, Druck und config.yaml laufen ohne Tk
  (`qslcards/controllers/`, eigene Tests ohne Xvfb); Feld<->Config-Abbildung in
  `gui/config_form.py`; die Fensterteile in `gui/app_cards.py`,
  `app_lookup.py`, `app_wavelog.py`, `app_print.py`; dazu `gui/desktop.py`,
  `gui/scrollframe.py`, `gui/steps.py`.

## [0.3.1]
Stand vor QR-Code, Assistent und Wavelog (Commit `2f9936f`).
