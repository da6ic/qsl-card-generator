# QSL-Karten-Generator: zweite kritische Bewertung

Stand: 26.11.2026, `main` bei `cd1fbdf`. Die Version im Code ist weiterhin **0.3.1**, der CHANGELOG führt 0.4.0 als „vorbereitet, noch nicht getaggt". PR #1 (README) ist offen und wurde hier nicht mitbewertet.

Die erste Bewertung vom selben Tag (Stand `1720a9b`) ist der Maßstab. Ihre Nummern (1.1 bis 3.6) werden hier weiterverwendet. Dieses Dokument ändert keinen Code.

**Wie geprüft:**
- Frischer Klon, Python 3.12 mit Tk 9.0 (uv), Testlauf unter Xvfb: **855 bestanden, 6 übersprungen, 0 Fehler**. Abdeckung **89 %** (vorher 87 %), `ruff check` ist sauber.
- GitHub-Actions auf `main` und am PR sind grün.
- Die zwei schwersten Befunde der ersten Runde habe ich am neuen Code noch einmal nachgestellt (siehe 1.1 und 1.2).
- Alles, was zwischen `1720a9b` und `cd1fbdf` geändert wurde, habe ich gelesen (56 Dateien, rund +5.500/−1.200 Zeilen).

---

## Kurzfazit

Fast alles aus der ersten Bewertung ist umgesetzt, und zwar gründlich: mit Tests, Erklärung im Code und Eintrag in CLAUDE.md und CHANGELOG. Von 16 Punkten sind **14 erledigt**, **einer teilweise** und **einer bewusst anders entschieden** (mit nachvollziehbarer Begründung).

Offen bleibt das, was nur mit echter Hardware geht: der **Test gegen eine echte Wavelog-Instanz**. Er ist jetzt mit `scripts/wavelog_check.py` gut vorbereitet, aber noch nicht gelaufen. Bis dahin sollte 0.4.0 nicht getaggt werden, und so steht es auch im CHANGELOG.

Neu dazugekommen sind vor allem kleinere Punkte:
- `QSL_SENT = N/I` wird nicht beachtet.
- Nach einem **abgebrochenen Lookup** werden die nicht nachgeschlagenen Stationen still auf „Büro / Drucken: Ja" gesetzt.
- Das **Debian-Installationsskript** hat ein paar Kanten.
- Die **Lizenzlage** ist ungeklärt (GPL-3 im Repo, Code vom Kumpel, Schrift ohne Lizenztext).
- **CLAUDE.md** widerspricht sich an einigen Stellen selbst.

---

## Teil A: Was aus der ersten Bewertung geworden ist

| # | Thema | Status | Beleg |
|---|---|---|---|
| 1.1 | Passwörter im Protokoll | ✅ erledigt, **nachgestellt** | `qslcards/redact.py`, `describe_error` in `hamqth.py`/`qrz.py`, `RedactingFilter` am Datei-Handler (`main.py`) |
| 1.2 | config.yaml atomar, YAML-Fehler | ✅ erledigt, **nachgestellt** | `fileio.atomic_write_text`, `config.load_safely` (Rückfall `.bak`, kaputte Datei als `.defekt`), `ConfigError` für leere Datei |
| 1.3 | Doppeldruck bei Wavelog | ✅ weitgehend | `sent_store` wirft `SentStoreError` statt still zu leeren, Nachdruck über „Schon gesendete anzeigen", Warnung, wenn die Instanz `qsl_sent` nicht liefert |
| 1.4 | Lookup-Rennen beim Log-Wechsel | ✅ erledigt | `controllers/lookup_runner.py`: Generationen, Warteschlange, Abbruch per `threading.Event` |
| 1.5 | Test gegen echtes Wavelog | ⏳ **vorbereitet, nicht gelaufen** | `scripts/wavelog_check.py` plus Tests; CHANGELOG sperrt 0.4.0 bis dahin |
| 2.1 | Wavelog-Client härter | ✅ erledigt | `WavelogError.status/code`, 429 mit `retry_after` (max. 5×, gedeckelt auf 90 s), `MAX_PAGES`, Fallback ohne `index.php`, Hinweis bei http, Datum geprüft |
| 2.2 | eQSL/LoTW nicht als Papier markieren, offene Markierungen sichern | ✅ erledigt | nur B/D (B mit Manager → `M`); `pending` in `wavelog_sent.json` |
| 2.3 | Lookup-Zugänge im Schlüsselbund | ✅ erledigt | `lookup/secret.py`, Standard aus |
| 2.4 | Lookup abbrechbar, Restzeit | ✅ erledigt | Abbrechen-Knopf, `format_eta` (siehe aber B.2) |
| 2.5 | Schritt 4 entzerren | ✅ erledigt | sechs Schritte, „Prüfen" füllt das Fenster (`ScrollableFrame.set_fill`), weniger Dialoge |
| 3.1 | `app.py` aufteilen | 🟡 **teilweise** | 1.762 → 948 Zeilen, Abläufe ohne Tk in `controllers/` (97–100 % Abdeckung); GUI-Teile als Mixins (siehe B.6) |
| 3.2 | Version 0.4.0 + CHANGELOG | ✅ CHANGELOG da | Tag bewusst zurückgehalten bis 1.5 |
| 3.3 | CI mit Tk 9 | ✅ erledigt | GitLab und GitHub, prüft `TkVersion >= 9`, ruff, black, pytest; läuft grün |
| 3.4 | Config-Überwachung | ↔️ **bewusst behalten** | begründet (zwei Fenster, Netzlaufwerk); eine extern kaputt geschriebene Datei wird jetzt ignoriert statt übernommen |
| 3.5 | Repo-Hygiene | ✅ erledigt | `Bild.jpg` (3,2 MB) ersetzt durch `docs/beispielbild.jpg` (220 KB) |
| 3.6 | CLAUDE.md aktualisieren | 🟡 **teilweise** | neuer Abschnitt „Stand 0.4.0" ist gut, ältere Abschnitte widersprechen ihm aber (siehe B.7) |

**Die Nachstellungen im Einzelnen:**
- **1.1:** Ein nicht erreichbarer Server mit Sonderzeichen im Passwort ergibt jetzt `url: /xml.php?u=DL1ABC&p=***` (HamQTH) und `…;password=***;agent=…` (QRZ). Vorher stand das Passwort im Klartext.
- **1.2:** Eine halb geschriebene `config.yaml` führt jetzt zu einer klaren Meldung. Die Datei wird als `.defekt` gesichert, und das Programm startet (vorher stürzte es ab).

---

## Teil B: Was noch offen ist oder neu dazugekommen ist

### Priorität 1

#### B.1 Test gegen echtes Wavelog (Rest von 1.5)
Unverändert der wichtigste offene Punkt. Das Prüfskript ist ordentlich gebaut:
- Es fragt den Token ab oder liest ihn aus der Umgebungsvariablen.
- Der Bericht enthält keinen Token.
- Markiert wird nur mit `--mark-one ID` und nach einer Rückfrage.

Ablauf:
1. `python scripts/wavelog_check.py https://<instanz> --station <id>`
2. Im Bericht nachsehen, ob `qsl_sent` beim Abruf kommt.
3. Ein Test-QSO mit `--mark-one` markieren und in Wavelog kontrollieren.
4. Den Bericht als Fixture in `tests/test_wavelog.py` übernehmen und danach `scripts/release.py 0.4.0` aufrufen.

Kleiner Hinweis zur Anonymisierung im Bericht: `_PRIVATE` deckt `call`, `name`, `qth` usw. ab, aber nicht `qsl_via` (Manager-Rufzeichen der Gegenstation), `darc_dok`, `state`/`cnty`, `sota_ref`/`pota_ref`/`wwff_ref` und `sig_info`. Vor dem Einchecken des Berichts als Fixture einmal drüberschauen oder die Liste ergänzen.

#### B.2 Abgebrochener Lookup: Reststationen werden still auf „Büro" gedruckt *(neu)*
Bei einem Abbruch liefert `lookup_calls` die nicht mehr abgefragten Rufzeichen **gar nicht** zurück. Das ist absichtlich so: Sie sollen nicht als `None` gleich „nicht gefunden" gelten.

Der Builder behandelt ein fehlendes Ergebnis aber genauso wie „kein Treffer", nämlich mit `accepted_routes(None)` → `default_via` (B). Die Folgen:
- Alle nicht abgefragten Stationen stehen in der Vorschau auf **„Büro, Drucken: Ja"**.
- „PDF erzeugen" ist nach dem Abbruch wieder freigegeben.

Einen Hinweis gibt es nur in der Statuszeile („Lookup abgebrochen – x/y gefunden. „Neu abrufen" holt den Rest.").

**Vorschlag:** Nicht abgefragte Stationen in der Vorschau sichtbar machen (Via „offen", Drucken vorausgewählt auf **Nein**) oder vor dem Erzeugen einmal nachfragen. „Nicht nachgeschlagen" und „nachgeschlagen, nichts gefunden" sind fachlich verschiedene Zustände und sollten das auch im Datenmodell sein.

#### B.3 `QSL_SENT = N` oder `I` wird ignoriert *(neu)*
`qsl_already_sent` und `paper_qsl_already_sent` prüfen nur auf `Y`. Die ADIF-Spezifikation kennt für `QSL_SENT` aber weitere Werte:

| Wert | Bedeutung laut ADIF | Heute | Richtig wäre |
|---|---|---|---|
| `Y` | gesendet | ausgelassen | ausgelassen ✅ |
| `N` | **nicht senden** | Karte wird gedruckt | ausgelassen oder abgewählt |
| `R` | angefordert | Karte wird gedruckt | drucken ✅ |
| `Q` | in der Warteschlange | Karte wird gedruckt | drucken ✅ |
| `I` | **ignorieren / ungültig** | Karte wird gedruckt | ausgelassen |

Wavelog nutzt genau diese Werte (die API nimmt `Y, N, R, Q, I` an).

`I` sollte sicher ausgelassen werden. Bei `N` gibt es eine Falle: Manche Logger schreiben `N` fälschlich als „noch nicht gesendet". Deshalb `N` nicht still auslassen, sondern in der Vorschau mit **Drucken: Nein** vorbelegen und kennzeichnen.

Dazu kommt eine Kleinigkeit: Es gibt **zwei** Funktionen für dieselbe Regel (`logbook.qsl_already_sent` mit `strip()`, `wavelog.client.paper_qsl_already_sent` ohne). Besser ist eine einzige Funktion, die beide benutzen.

### Priorität 2

#### B.4 Debian-Installationsskript (`packaging/linux/install-from-source.sh`) *(neu)*
Insgesamt ein gutes Skript: Es installiert ohne Root, die Benutzerdaten bleiben beim Update erhalten, `-P` im Starter verhindert einen fremden `cwd`, und `--uninstall` fragt nach. Ein paar Kanten:
- **`rsync` wird vorausgesetzt, aber nicht geprüft.** Auf minimalen Debian-Installationen fehlt es, und das Skript bricht dann mit einer unklaren Meldung ab. Am besten wie bei tkinter vorab prüfen und `sudo apt install rsync` empfehlen.
- **Python-Version wird nicht geprüft.** `requires-python >= 3.11`, aber Ubuntu 22.04 hat 3.10. Die venv wird dann noch angelegt, erst `pip` scheitert mit einer langen Meldung. Besser vorab `sys.version_info >= (3, 11)` prüfen.
- **`rsync --delete` löscht Dateien, die nicht in `DATA_FILES` stehen:** z. B. `config.yaml.defekt` (die Sicherung einer kaputten Config aus 1.2) oder übrig gebliebene `*.tmp`. Den `.defekt`-Fall in die Liste aufnehmen.
- **Kein Protokoll bei Start aus der Quelle.** `main.py` richtet die Protokolldatei (und den `RedactingFilter`) nur im Bündel ein (`paths.is_frozen()`). Wer über dieses Skript installiert und aus dem Menü startet, hat **gar kein** Protokoll: `stderr` geht ins Leere oder ins Journal, und „Hilfe ▸ Protokoll anzeigen" findet nichts. Vorschlag: Datei-Logging auch für Installationen aus der Quelle einschalten, z. B. per Umgebungsvariable im Starter.
- `INSTALL_DIR` ist frei setzbar, und `--uninstall` macht nach „j" ein `rm -rf "$INSTALL_DIR"`. Wer versehentlich `INSTALL_DIR=$HOME` setzt, löscht sein Home-Verzeichnis. Eine einfache Schutzabfrage (Ordner muss `app/qslcards` enthalten) kostet zwei Zeilen.
- Debian und Ubuntu liefern **Tk 8.6**. Das Skript sagt das ehrlich (Symbole fehlen). Im README sollte dann auch stehen, dass dort 11 Menü-Tests rot sind und das erwartet ist.

#### B.5 Lizenz *(neu)*
- Mit dem Zusammenführen des GitHub-Repos kam eine **GPL-3.0**-`LICENSE` dazu. Der Code stammt aber zum großen Teil vom Kumpel (privates GitLab), und für sein Repo war keine Lizenz hinterlegt. Eine Lizenz kann nur der Urheber vergeben. **Bitte mit ihm klären**, ob GPL-3 für ihn in Ordnung ist, und das kurz im README festhalten.
- `pyproject.toml` hat kein `license`-Feld, und die Quelldateien haben keinen Lizenzkopf. Für GPL ist beides nicht Pflicht, aber `license = "GPL-3.0-or-later"` (oder `-only`) im `pyproject.toml` ist üblich.
- **DejaVu-Schriften** liegen in `qslcards/assets/fonts/` ohne ihren Lizenztext. Die Bitstream-Vera/DejaVu-Lizenz verlangt, dass der Copyright-Hinweis mitgeliefert wird. Die `LICENSE` aus dem DejaVu-Paket daneben legen (wie bei `cty.dat` schon gemacht) und in `packaging/qslcards.spec` mitnehmen.

#### B.6 Aufteilung der GUI: Mixins sind ein Zwischenschritt
Die Aufteilung hat viel gebracht: `controllers/` ist Tk-frei und fast vollständig getestet. Die vier `gui/app_*.py` sind aber **Mixins einer einzigen Klasse**. Sie teilen sich den gesamten Zustand von `App` über `self`, ohne dass irgendwo steht, welches Mixin welches Attribut braucht. Fachlich ist das immer noch ein Objekt mit rund 1.800 Zeilen, nur auf fünf Dateien verteilt.

Die Abdeckung in diesem Teil ist am niedrigsten (`app_wavelog.py` 68 %, `app_lookup.py` 78 %, `app_print.py` 79 %). Ausgerechnet der Wavelog-Teil, also der mit den Schreibzugriffen, ist am schwächsten getestet.

**Vorschlag (kein Muss):**
- Einen Typprüfer in die CI aufnehmen (`mypy` oder `pyright`, zunächst nur für `controllers/`, `wavelog/`, `lookup/`). Bei Mixins findet er vergessene Attribute, die kein Test trifft.
- Langfristig die Mixins zu eigenen Klassen machen, die nur das bekommen, was sie brauchen (z. B. `WavelogPanel(session, wavelog_flow, ui)`).
- Kurzfristig gezielt Tests für `app_wavelog.py` ergänzen (Markieren mit Teilfehlern, `SentStoreError` in der GUI, offene Markierungen nach Neustart).

#### B.7 CLAUDE.md widerspricht sich
Der neue Abschnitt „Stand 0.4.0" ist korrekt. Ältere Stellen sagen aber noch das Gegenteil. Weil die Datei die Arbeitsgrundlage für jede künftige Claude-Sitzung ist, führt das zu falschen Annahmen:
- §5.5 und §11 sagen, die Zugangsdaten werden „je Sitzung neu eingegeben", seit 0.4.0 geht aber der Schlüsselbund.
- §9 sagt „blockiert ‚PDF erzeugen' mit **einem** Popup", seit 0.4.0 steht es in der Navigationsleiste, ohne Popup.
- §11 „GUI-Abschnitte 1–11" beschreibt noch die alte lange Seite.
- §11 „Workflow-Konventionen" nennt Branch `build/mvp`, „nicht selbst committen" und Remote GitLab. Gearbeitet wird inzwischen auf GitHub `main` mit Pull Requests (Projektregel). Auch die CI-Zeile „Remote ist GitLab" stimmt nicht mehr.
- „Wichtige Entscheidungen zum Bündeln": „Bewusst außen vor: … CI" stimmt nicht mehr.
- Die Teststruktur in §3 listet die neuen Testdateien (`test_controllers.py`, `test_redact.py`, `test_sent_store.py` …) nicht.

**Vorschlag:** einmal durchgehen, Veraltetes streichen statt ergänzen, und die Workflow-Regeln auf den GitHub-Ablauf umstellen.

### Priorität 3

#### B.8 Kleinigkeiten
- **Abhängigkeiten ohne Obergrenze und ohne Lockdatei** (`reportlab>=4.0`, `requests>=2.31` …). Für die CI ist das in Ordnung. Für Releases sorgt eine Lockdatei (`uv lock` oder `requirements-lock.txt` mit Hashes) dafür, dass ein Bündel in drei Monaten mit denselben Versionen entsteht.
- **Markieren ist bewusst langsam** (0,5 s je QSO, gegen das Rate-Limit). 500 Karten dauern gut 4 Minuten. Das ist in Ordnung, sollte aber bei der Rückfrage stehen („dauert ca. 4 min"), damit niemand das Programm vorher schließt. Die offenen Markierungen würden das zwar überleben, aber der Nutzer weiß das nicht.
- `_freq_mhz` in `wavelog/client.py` behandelt Werte unter 1.000.000 als „schon MHz/kHz" und gibt sie **unverändert** zurück. Laut Doku liefert Wavelog immer Hz, kHz-Werte (z. B. `14074`) würden also als „14074" auf der Karte landen. Das ist eher theoretisch, ein Test mit `freq: 14074` würde es aber festhalten.
- **CI:** Der GitHub-Workflow pinnt Actions nur auf Haupt-Tags (`@v4`, `@v6`). Für ein kleines Projekt reicht das. Wer es strenger möchte, pinnt auf Commit-SHAs.

---

## Übersicht zum Abhaken

| # | Thema | Aufwand | Risiko, wenn nicht erledigt |
|---|---|---|---|
| B.1 | Wavelog-Prüfskript gegen echte Instanz, dann 0.4.0 taggen | klein (braucht Zugang) | Markieren trifft falsche Felder |
| B.2 | Nicht nachgeschlagene Stationen nach Abbruch nicht vorauswählen | klein | Karten mit falschem Weg |
| B.3 | `QSL_SENT = N/I` beachten, eine einzige Funktion dafür | klein | Karten an Stationen, die keine wollen |
| B.4 | Installationsskript: rsync- und Python-Check, `.defekt`, Protokoll, Schutz bei `rm -rf` | klein | Abbruch bei Neuinstallation, keine Fehlersuche möglich |
| B.5 | Lizenz mit dem Kumpel klären, DejaVu-Lizenz beilegen | klein | rechtliche Unklarheit beim Weitergeben |
| B.6 | Typprüfer in CI, Tests für `app_wavelog.py` | mittel | Fehler im Schreibpfad bleiben unentdeckt |
| B.7 | CLAUDE.md bereinigen | klein | künftige Änderungen gehen von alten Annahmen aus |
| B.8 | Lockdatei, Dauer-Hinweis beim Markieren, Frequenz-Test | klein | Komfort, Reproduzierbarkeit |

Sinnvolle Reihenfolge: **B.1** (sobald Zugang zur Instanz da ist) → **B.2 + B.3** (je unter einer Stunde) → **B.5** (Gespräch mit dem Kumpel) → **B.7** → Release 0.4.0 → **B.4, B.6, B.8**.
