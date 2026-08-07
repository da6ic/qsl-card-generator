# Windows-Bündel bauen (32- und 64-Bit)

Es gibt **kein** Cross-Compile: PyInstaller bündelt den Interpreter, unter dem es
läuft. Ein Windows-Programm entsteht nur auf Windows — echter Rechner oder VM.

## Python besorgen

**Zwingend Python 3.14.** Grund: Tcl/Tk steckt unter Windows im Python-Installer,
und erst 3.14 bringt **Tcl/Tk 9.0.4** mit (3.13 nur 8.6.15). Mit Tk 8.6 fehlen
der Vorschautabelle stillschweigend die Stift- und Schaltersymbole — das Programm
startet, es sieht nur falsch aus.

Von <https://www.python.org/downloads/windows/>, Python 3.14.x:

| Ziel | Installer | Empfohlener Pfad |
|------|-----------|------------------|
| 64-Bit | *Windows installer (64-bit)* | `C:\Python314` |
| 32-Bit | *Windows installer (32-bit)* | `C:\Python314-32` |

Beim Installieren **tcl/tk and IDLE** angehakt lassen (Standard) — ohne das gibt
es kein tkinter. „Install for all users" mit eigenem Pfad macht die beiden
Bitbreiten leichter auseinanderzuhalten.

## Bauen

```powershell
git clone <repo> ; cd qsl-karten-generator

# 64-Bit
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Python "C:\Python314\python.exe"

# 32-Bit
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1 -Python "C:\Python314-32\python.exe" -VenvDir ".venv-build32"
```

Das Skript gibt vor dem Bauen Bitbreite und Tk-Version aus — genau die beiden
Angaben, die man dem fertigen Programm nicht mehr ansieht. Stimmen sie nicht,
abbrechen statt weiterbauen.

Ergebnis: `dist\QSL-Karten-Generator-<version>-windows-x64.zip` bzw. `-x86.zip`.

**Zwischen den beiden Läufen `dist\` leeren** (oder das erste ZIP wegkopieren) —
sonst überschreibt der zweite Lauf den Programmordner des ersten.

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
