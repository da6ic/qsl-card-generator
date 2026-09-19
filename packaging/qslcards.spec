# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Beschreibung für alle drei Plattformen.

Aufgerufen wird sie über `scripts/build_app.py` — dort stehen die
Vorbedingungsprüfungen und das Verpacken; hier steht nur, *was* ins Bündel kommt.

Eine Spec für alles, weil sich die Ziele nur in Kleinigkeiten unterscheiden
(Icon-Format, macOS-Bundle). Die **Bitbreite ist kein Unterschied**: 32- und
64-Bit-Windows entstehen aus derselben Spec, nur mit einem anderen Python.

Modus ist überall **onedir** (ein Ordner statt einer Einzeldatei):
* Start ohne Entpacken bei jedem Lauf — bei einer onefile-Anwendung landen ~80 MB
  jedes Mal im Temp-Verzeichnis.
* Virenscanner unter Windows schlagen bei selbstentpackenden Dateien deutlich
  häufiger fehl an.
* Der Portable-Modus braucht einen Ordner, in den die `config.yaml` passt
  (siehe `qslcards/paths.py`).
"""

import sys
from pathlib import Path

# `__file__` ist in einer Spec nicht gesetzt; PyInstaller stellt stattdessen
# `SPECPATH` bereit.
PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821

BUNDLE_ID = "de.qslcards.generator"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
# Name **und** Version kommen aus dem Paket — dieselbe Quelle, aus der auch
# `scripts/build_app.py` liest. Stand der Name hier doppelt, fände das
# Bauskript hinterher das Ergebnis von PyInstaller nicht wieder.
from qslcards import __app_name__ as APP_NAME, __version__  # noqa: E402

# Die macOS-Mindestversion kommt aus demselben Skript, das auch davor warnt —
# aus genau dem Grund, aus dem der Name dort steht: zwei Quellen liefen
# auseinander, und ausgerechnet hier wäre das Auseinanderlaufen unsichtbar
# (eine zu niedrige Angabe merkt man erst auf einem fremden Mac).
from build_app import macos_minimum_system_version  # noqa: E402

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"

# Mitgelieferte Dateien. Die Zielpfade spiegeln den Aufbau des Projekts, weil
# `qslcards/paths.py` genau diesen Aufbau erwartet (`resource_path("qslcards",
# "assets", ...)` bzw. `resource_path("handbuch.md")`).
datas = [
    (str(PROJECT_ROOT / "qslcards" / "assets"), "qslcards/assets"),
    (str(PROJECT_ROOT / "handbuch.md"), "."),
    (str(PROJECT_ROOT / "config.example.yaml"), "."),
]

# Module, die die statische Analyse **nicht** finden kann und die deshalb von
# Hand genannt werden müssen.
#
# `PIL._tkinter_finder` sucht die Tcl/Tk-Bibliothek für Pillows C-Erweiterung
# `_imagingtk`; nachgeladen wird es erst zur Laufzeit und aus C heraus, also
# sieht PyInstaller den Import nirgends. Ohne diese Zeile stirbt
# `ImageTk.PhotoImage(...)` mit „No module named 'PIL._tkinter_finder'" — und
# damit **still**: `app._update_thumbnail` fängt nur `OSError`/`ValueError`, die
# Ausnahme landet im Protokoll und der Anwender sieht in Abschnitt 2 lediglich
# weiterhin „keine Vorschau", nachdem er ein Bild gewählt hat. Die PDF ist davon
# nicht betroffen (dort geht das Bild über `drawImage(pfad)`, ohne Tk) — genau
# deshalb fällt es beim Ausprobieren so leicht durchs Raster.
# Gefunden beim Linux-Bündel, betrifft aber alle drei Plattformen.
hiddenimports = ["PIL._tkinter_finder"]

# Was nicht mit hinein soll. Entwicklungswerkzeuge landen sonst über die
# venv-Analyse mit im Bündel und blähen es auf.
excludes = [
    "pytest",
    "black",
    "ruff",
    "pypdf",
    "setuptools",
    "pip",
    "numpy",
    "matplotlib",
    "pandas",
    "IPython",
    "unittest",
    "pydoc_data",
    "tkinter.test",
    "test",
]

a = Analysis(  # noqa: F821
    [str(PROJECT_ROOT / "qslcards" / "__main__.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821

# Windows: die .ico sorgt für ein sauberes Symbol in Taskleiste und Explorer,
# die Versions-Ressource für Name und Version in den Dateieigenschaften.
# macOS: das Icon kommt am BUNDLE, nicht an der ausführbaren Datei.
exe_icon = None
version_file = None
if IS_WINDOWS:
    exe_icon = str(PROJECT_ROOT / "qslcards" / "assets" / "icons" / "app_icon.ico")
    candidate = PROJECT_ROOT / "build" / "version_info.txt"
    if candidate.is_file():
        version_file = str(candidate)

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX bringt hier wenig und lässt Virenscanner anschlagen
    console=False,  # Fensterprogramm: siehe `main._prepare_frozen_runtime`
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # macOS: PyInstaller signiert ad-hoc (auf arm64 Pflicht)
    entitlements_file=None,
    icon=exe_icon,
    version=version_file,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if IS_MACOS:
    app = BUNDLE(  # noqa: F821
        coll,
        name=f"{APP_NAME}.app",
        icon=str(PROJECT_ROOT / "qslcards" / "assets" / "icons" / "app_icon.icns"),
        bundle_identifier=BUNDLE_ID,
        version=__version__,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            # Ohne diesen Schlüssel rendert macOS das Fenster in doppelter
            # Pixelgröße hoch — die ganze Oberfläche wäre unscharf.
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
            # **Nicht** fest eintragen: PyInstaller bündelt die Bibliotheken des
            # bauenden Interpreters, und die tragen dessen Deployment-Target.
            # Ein zu niedriger Wert ist die schlimmere Sorte Fehler — Launch
            # Services lässt das Programm dann starten und es stirbt erst beim
            # Nachladen mit einer dyld-Meldung. Siehe
            # `build_app.macos_minimum_system_version`.
            "LSMinimumSystemVersion": macos_minimum_system_version(),
            "NSHumanReadableCopyright": "QSL-Karten-Generator",
        },
    )
