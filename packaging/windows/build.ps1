# Baut das Windows-Bündel. Im Projektordner ausführen:
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
#
# Ohne Angabe nimmt es Python 3.14 (64 Bit) über den Python-Launcher `py`. Der
# findet den Interpreter unabhängig davon, wohin er installiert wurde — man
# braucht also keinen Pfad zu kennen. **Mindestens 3.14.7**: erst dieser
# Installer bringt Tcl/Tk 9 mit (siehe README.md daneben).
#
# Die Bitbreite des Bündels ist die des **bauenden** Interpreters, nicht die von
# Windows. Welche Interpreter installiert sind und wo sie liegen, zeigt `py -0p`.
# 32 Bit wird bewusst nicht mehr gebaut — Begründung im README.md daneben.
#
# Ein vollständiger Pfad geht genauso, falls der Launcher fehlt:
#
#   ... build.ps1 -Python "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe"

param(
    [string]$Python = "py -3.14",
    [string]$VenvDir = ".venv-build"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

# `py -3.14` sind zwei Wörter, ein Pfad ist eines — beides muss funktionieren.
# Achtung: `$parts[1..0]` wäre in PowerShell ein **rückwärts** laufender Bereich
# und lieferte bei einem einzelnen Wort ein zusätzliches `$null` als Argument.
# Deshalb der ausdrückliche Test auf die Länge statt eines Bereichs.
$parts = $Python.Split(" ", [StringSplitOptions]::RemoveEmptyEntries)
$exe = $parts[0]
$exeArgs = @()
if ($parts.Length -gt 1) { $exeArgs = $parts[1..($parts.Length - 1)] }

Write-Host "Interpreter: $Python"
Write-Host "Erzeuge virtuelle Umgebung in $VenvDir"
& $exe @exeArgs -m venv $VenvDir
if ($LASTEXITCODE -ne 0) {
    Write-Error "Interpreter '$Python' nicht gefunden. Installierte Versionen: py -0p"
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -e ".[build]" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error @"
Die Abhängigkeiten ließen sich nicht installieren.

Fehlt fuer ein Paket ein fertiges Wheel, baut pip es aus den Quellen - das
verlangt einen C-Compiler, und Windows blockiert dabei gern die Hilfsdateien im
Temp-Ordner ("Eine Anwendungssteuerungsrichtlinie hat diese Datei blockiert").
Genau daran scheitert ein 32-Bit-Bau (PyYAML); 32 Bit wird deshalb nicht mehr
unterstuetzt - siehe packaging\windows\README.md.
"@
}

# Kein `python -c` zur Ausgabe der Version: Windows PowerShell 5.1 schluckt beim
# Aufruf einer nativen .exe die doppelten Anführungszeichen im Argument, der
# Python-Code kam als Syntaxfehler an. `build_app.py` gibt Python-Version,
# Tk-Version und Bitbreite (im Plattform-Kürzel) ohnehin selbst aus.
& $VenvPython scripts\build_app.py --clean
