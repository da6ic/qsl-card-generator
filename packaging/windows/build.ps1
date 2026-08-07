# Baut das Windows-Bündel. Im Projektordner ausführen:
#
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
#
# Standardmäßig mit dem Python, das gerade im PATH liegt. Für die andere
# Bitbreite den Interpreter ausdrücklich angeben — die Bitbreite des Bündels ist
# die des bauenden Interpreters, nicht die von Windows:
#
#   ... build.ps1 -Python "C:\Python314-32\python.exe"   # ergibt windows-x86
#   ... build.ps1 -Python "C:\Python314\python.exe"      # ergibt windows-x64

param(
    [string]$Python = "py -3.14",
    [string]$VenvDir = ".venv-build"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

Write-Host "Erzeuge virtuelle Umgebung in $VenvDir"
# `py -3.14` ist zwei Wörter, ein Pfad ist eines — beides muss funktionieren.
$parts = $Python.Split(" ")
& $parts[0] @($parts[1..($parts.Length - 1)]) -m venv $VenvDir

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -e ".[build]" --quiet

# Zeigt vor dem Bauen, was wirklich verwendet wird — die Bitbreite und die
# Tk-Version sind genau die beiden Dinge, die man hinterher nicht mehr sieht.
# Einfach-anführungszeichen: sonst ersetzt PowerShell alles mit $ im Python-Code.
& $VenvPython -c @'
import struct, sys, tkinter
bits = struct.calcsize("P") * 8
print(f"Python {sys.version.split()[0]}  {bits}-bit  Tk {tkinter.TkVersion}")
'@

& $VenvPython scripts\build_app.py --clean
