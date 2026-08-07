# Windows-Bündel bauen (32- und 64-Bit)

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
(*Windows installer (64-bit)*, für die zweite Bitbreite *(32-bit)*). Eine
vorhandene ältere 3.14 wird dabei aktualisiert, nicht danebengelegt.

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

# 64-Bit
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Python "py -3.14"

# 32-Bit
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Python "py -3.14-32" -VenvDir ".venv-build32"
```

`py -3.14` bzw. `py -3.14-32` wählt der Python-Launcher aus — **kein Pfad nötig**.
Fehlt der Launcher, geht auch der vollständige Pfad:
`-Python "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"`.

`build_app.py` nennt vor dem Bauen Python-Version, Tk-Version und Plattform-
Kürzel (`windows-x64` / `windows-x86`) — genau die Angaben, die man dem fertigen
Programm nicht mehr ansieht. Steht dort `Tk 8.6` oder die falsche Bitbreite:
abbrechen statt weiterbauen.

Ergebnis: `dist\QSL-Karten-Generator-<version>-windows-x64.zip` bzw. `-x86.zip`.

**Zwischen den beiden Läufen `dist\` leeren** (oder das erste ZIP wegkopieren) —
sonst überschreibt der zweite Lauf den Programmordner des ersten.

## 32-Bit: PyYAML hat kein Wheel für Python 3.14

Hier beißen sich zwei Anforderungen, und das lässt sich nicht wegkonfigurieren:

- Für **Tk 9** braucht es Python **3.14.7+**.
- **PyYAML** liefert für `cp314` **kein win32-Wheel** mehr (für `cp310`–`cp313`
  gibt es eines, für 3.14 nur noch `win_amd64` und `win_arm64`). Pillow hat sein
  win32-Wheel weiterhin, ReportLab und Requests sind reines Python — PyYAML ist
  der einzige Stolperstein.

pip baut PyYAML dann aus den Quellen. Das braucht die MSVC-Build-Tools und
Cython, und Windows blockiert dabei gern die entpackten Hilfsdateien im
Temp-Ordner: „Eine Anwendungssteuerungsrichtlinie hat diese Datei blockiert"
(Smart App Control bzw. AppLocker/WDAC).

Drei Wege, in der Reihenfolge, in der ich sie empfehlen würde:

1. **32-Bit weglassen.** Windows 11 ist ohnehin 64-Bit-only und Windows 10 in
   32 Bit seit Oktober 2025 ohne Support. Das 64-Bit-Bündel deckt jedes System
   ab, das noch Updates bekommt.
2. **32-Bit mit Python 3.13 bauen.** Alle Wheels sind da, der Build läuft glatt
   durch — aber Tk ist dort 8.6, der Vorschautabelle fehlen also die Stift- und
   Schaltersymbole. Funktionsfähig, optisch abgespeckt. `build_app.py` meldet
   das und bricht ab; für diesen bewussten Fall die Tk-Prüfung überspringen
   (`MIN_TK` in `scripts/build_app.py`) — und den Verzicht dokumentieren.
3. **PyYAML aus den Quellen bauen.** „Desktop development with C++" aus den
   [Build Tools für Visual Studio](https://visualstudio.microsoft.com/downloads/)
   installieren und die App-Steuerungsrichtlinie für den Temp-Ordner lockern.
   Der meiste Aufwand für das kleinste Publikum.

## Ausliefern

Der Anwender entpackt das ZIP an einen Ort, den er beschreiben darf
(`Dokumente`, Desktop, USB-Stick) und startet `QSL-Karten-Generator.exe`.
Ein Installer ist nicht nötig; das Programm ist bewusst als Ordner gebaut.

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
7. `%APPDATA%\QSL-Karten-Generator\config.yaml` entsteht **mit Kommentaren** und
   wird beim Ändern eines Feldes aktualisiert.
8. Eine `config.yaml` neben die `.exe` legen → Portable-Modus: Config, Cache und
   `qslcards.log` bleiben im Programmordner.
9. Nur beim 32-Bit-Bündel: einmal auf einem 64-Bit-Windows starten (läuft dort
   über WOW64) — das ist der Regelfall beim Empfänger.
