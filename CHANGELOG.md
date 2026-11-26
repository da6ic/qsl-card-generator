# Änderungen

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).
Versionsnummern setzt `scripts/release.py`, nie die Hand.

## [0.4.0] – vorbereitet, noch nicht getaggt

Freigabe erst nach dem Test gegen eine echte Wavelog-Instanz
(`scripts/wavelog_check.py`, siehe Bewertung 1.5), dann
`python scripts/release.py 0.4.0`.

### Neu
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
- Intern: Zustand und Lookup-Ablauf ohne Tk (`qslcards/controllers/`),
  `gui/desktop.py`, `gui/scrollframe.py` aus `app.py` herausgelöst.

## [0.3.1]
Stand vor QR-Code, Assistent und Wavelog (Commit `2f9936f`).
