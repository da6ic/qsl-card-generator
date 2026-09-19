# Windows-Bündel bauen (64-Bit)

Es gibt **kein** Cross-Compile: PyInstaller bündelt den Interpreter, unter dem es
läuft. Ein Windows-Programm entsteht nur auf Windows — echter Rechner oder VM.

## Python besorgen

**Zwingend Python 3.14.7 oder neuer** — die Punktversion zählt. Tcl/Tk steckt
unter Windows im Python-Installer, und der Wechsel auf **Tcl/Tk 9.0.4** kam erst
mit **3.14.7**; 3.14.0 bis 3.14.6 liefern noch 8.6.15, ebenso 3.13. Mit Tk 8.6
fehlen der Vorschautabelle stillschweigend die Stift- und Schaltersymbole — das
Programm startet, es sieht nur falsch aus.

Prüfen, was installiert ist:

```powershell
py -3.14 -VV                       # Punktversion
py -3.14 -m tkinter                # das Fenster nennt oben die Tk-Version
```

Von <https://www.python.org/downloads/windows/> die aktuelle 3.14.x holen
(*Windows installer (64-bit)*). Eine vorhandene ältere 3.14 wird dabei
aktualisiert, nicht danebengelegt.

Beim Installieren **„tcl/tk and IDLE" angehakt lassen** (Standard) — ohne das
gibt es kein tkinter. Ebenso **„py launcher"** anhaken; damit muss man sich
später um Installationspfade nicht kümmern.

**Wohin sie installiert werden, ist egal.** Der Standardpfad hängt davon ab, ob
man „für alle Benutzer" oder „nur für mich" wählt (dann liegt Python unter
`%LOCALAPPDATA%\Programs\Python\…`). Welche Interpreter installiert sind und wo,
zeigt:

```powershell
py -0p
```

## PyInstaller: hier braucht es die Entwicklungsfassung

Python 3.14.7 unter Windows bringt Tcl/Tk 9 mit **eingebetteter** Bibliothek —
die Tcl-Skripte stecken in der DLL statt in einem Ordner daneben. Das
veröffentlichte PyInstaller 6.21.0 kennt diesen Fall noch nicht: es sammelt
nichts ein, und sein Laufzeit-Hook bricht beim **Start** des fertigen Programms
ab mit

```
Tcl data directory "...\_internal\_tcl_data" not found.
```

Der Fix ist geschrieben, aber noch in keinem Release (siehe `news/9470.*` im
PyInstaller-Repository; 6.21.0 ist vom Juni 2026). Bis zur nächsten
Veröffentlichung deshalb:

```powershell
.venv-build\Scripts\python.exe -m pip install --force-reinstall `
    "pyinstaller @ git+https://github.com/pyinstaller/pyinstaller.git@develop"
```

Das braucht **keinen** C-Compiler — die vorgebauten Bootloader liegen im
Repository (Windows-64bit, Linux-64bit, Darwin-64bit; für Windows **32-Bit gibt
es keinen**, ein weiterer Grund gegen diese Bitbreite).

`build_app.py` erkennt die Lage selbst und bricht mit genau diesem Hinweis ab —
die Versionsnummer hilft dabei nicht, denn die Fassung mit dem Fix meldet sich
weiterhin als 6.21.0.

## Bauen

```powershell
git clone git@gitlab.j-homelab.de:side-projects/qsl-karten-generator.git
cd qsl-karten-generator
git checkout build/mvp

powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Python "py -3.14"
```

`py -3.14` wählt der Python-Launcher aus — **kein Pfad nötig**. Fehlt der
Launcher, geht auch der vollständige Pfad:
`-Python "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"`.

`build_app.py` nennt vor dem Bauen Python-Version, Tk-Version und Plattform-
Kürzel (`windows-x64`) — genau die Angaben, die man dem fertigen Programm nicht
mehr ansieht. Steht dort `Tk 8.6` oder die falsche Bitbreite: abbrechen statt
weiterbauen.

Ergebnis: `dist\QSL-Karten-Generator-<version>-windows-x64.zip`.

`<version>` kommt aus `qslcards/__init__.py`. **Angehoben wird sie hier nicht** —
das macht `scripts/release.py` einmal auf dem Entwicklungsrechner (samt Commit
und Tag, siehe `README.md`); hier wird nur derselbe Stand gebaut.

## Warum es kein 32-Bit-Bündel gibt

Mit dem Nutzer so entschieden, nachdem sich im Bauversuch drei voneinander
unabhängige Blockaden zeigten. Nicht ohne Rückfrage zurückdrehen — die Punkte 1
und 2 lassen sich nicht wegkonfigurieren:

1. **PyYAML hat kein win32-Wheel für Python 3.14** (bis `cp313` gab es eines, ab
   `cp314` nur noch `win_amd64` und `win_arm64`). pip baut es dann aus den
   Quellen — das verlangt die MSVC-Build-Tools und Cython, und die
   Windows-App-Steuerung blockiert dabei die entpackten Hilfsdateien im
   Temp-Ordner („Eine Anwendungssteuerungsrichtlinie hat diese Datei
   blockiert"). Pillow hat sein win32-Wheel weiterhin, ReportLab und Requests
   sind reines Python; PyYAML ist der einzige Stolperstein — er genügt.
2. **PyInstaller aus `develop` hat keinen vorgebauten 32-Bit-Bootloader.**
   Im Repository liegen nur Windows-64bit, Linux-64bit und Darwin-64bit. Für
   32 Bit müsste er selbst kompiliert werden — und die Entwicklungsfassung
   brauchen wir für Tcl/Tk 9 zwingend (siehe oben).
3. **Es gibt kaum noch Publikum.** Windows 11 ist 64-Bit-only, Windows 10 in
   32 Bit seit Oktober 2025 ohne Support. Das 64-Bit-Bündel deckt jedes System
   ab, das noch Updates bekommt.

Käme die Anforderung doch zurück, wäre der gangbarste Weg **Python 3.13 in
32 Bit**: dort sind alle Wheels vorhanden und PyInstaller 6.21.0 genügt, weil
Tcl/Tk 8.6 seine Daten in Ordnern hält. Preis: Tk 8.6 heißt keine Stift- und
Schaltersymbole in der Vorschautabelle. Dafür müsste `MIN_TK` in
`scripts/build_app.py` bewusst übergangen und der Verzicht dokumentiert werden.

## Ausliefern

Der Anwender entpackt das ZIP an einen Ort, den er beschreiben darf
(`Dokumente`, Desktop, USB-Stick) und startet `QSL-Karten-Generator.exe`.
Ein Installer ist nicht nötig; das Programm ist bewusst als Ordner gebaut.

Im Archiv liegt dafür `LIESMICH.txt` neben der `.exe` — `build_app.py` kopiert
sie beim Verpacken aus diesem Ordner dorthin (dasselbe Prinzip wie `install.sh`
im Linux-Archiv). Sie beantwortet **nur**, was vor dem ersten Start zählt: wohin
entpacken und wie man an SmartScreen vorbeikommt. Alles Weitere steht im
Handbuch, Kapitel „Installieren und weitergeben" — das bleibt die eine Wahrheit
zur Bedienung, und die Kurzanleitung verweist ausdrücklich dorthin. Wer sie
erweitert, baut sich zwei Dokumente, die auseinanderlaufen.

**SmartScreen:** Das Programm ist nicht signiert. Beim ersten Start meldet
Windows „Der Computer wurde durch Windows geschützt". Der Weg dahin: *Weitere
Informationen* ▸ *Trotzdem ausführen*. Ein Zertifikat, das das abstellt
(EV-Code-Signing), kostet einen dreistelligen Betrag pro Jahr.

**Nach `C:\Program Files` gehört das Programm nicht** — dorthin darf es nicht
schreiben. Der Portable-Modus (`config.yaml` neben der `.exe`) fiele damit aus,
und der Anwender fände seine Config nur noch unter `%APPDATA%`.

## Wo die Daten landen

| | Ort |
|---|---|
| Standard | `%APPDATA%\QSL-Karten-Generator\` (Config, `lookup_cache.json`, `qslcards.log`) |
| Portable | neben der `.exe`, sobald dort eine `config.yaml` liegt |

## Nach dem Bauen prüfen

1. `QSL-Karten-Generator.exe` startet, **kein** schwarzes Konsolenfenster daneben.
2. Symbol in Taskleiste und Explorer stimmt; Rechtsklick ▸ Eigenschaften ▸ Details
   zeigt Name und Version.
3. **Vorschautabelle zeigt Stift- und Schaltersymbole** — der Beweis für Tk 9.
4. Logbuch laden, PDF erzeugen — **Umlaute auf der Karte** korrekt.
5. `Hilfe ▸ Handbuch` zeigt Text.
6. Nach dem Erzeugen öffnet sich die PDF von selbst; „Aktionen ▸ Ausgabeordner
   anzeigen" öffnet den Explorer.
7. `%APPDATA%\QSL-Karten-Generator\config.yaml` entsteht, sobald ein Feld
   geändert wird, und trägt oben die Zeile „bitte nicht von Hand bearbeiten".
8. Eine `config.yaml` neben die `.exe` legen → Portable-Modus: Config, Cache und
   `qslcards.log` bleiben im Programmordner.
