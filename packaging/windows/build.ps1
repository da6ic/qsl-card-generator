# Baut das Windows-Bündel. Im Projektordner ausführen:
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
#
# Ohne Angabe nimmt es Python 3.14 (64 Bit) über den Python-Launcher `py`. Der
# findet den Interpreter unabhängig davon, wohin er installiert wurde — man
# braucht also keinen Pfad zu kennen. Für die andere Bitbreite:
#
#   ... build.ps1 -Python "py -3.14-32" -VenvDir ".venv-build32"   # -> windows-x86
#   ... build.ps1 -Python "py -3.14"                               # -> windows-x64
#
# Die Bitbreite des Bündels ist die des **bauenden** Interpreters, nicht die von
# Windows. Welche Interpreter installiert sind und wo sie liegen, zeigt `py -0p`.
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

# Zeigt vor dem Bauen, was wirklich verwendet wird — Bitbreite und Tk-Version
# sind genau die beiden Dinge, die man dem fertigen Programm nicht mehr ansieht.
# Einfache Anführungszeichen: sonst ersetzt PowerShell alles mit $ im Python-Code.
& $VenvPython -c @'
import struct, sys, tkinter
bits = struct.calcsize("P") * 8
print(f"Python {sys.version.split()[0]}  {bits}-bit  Tk {tkinter.TkVersion}")
'@

& $VenvPython scripts\build_app.py --clean
