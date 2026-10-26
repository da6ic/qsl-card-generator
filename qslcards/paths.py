"""Alle Datei- und Verzeichnispfade des Programms — die einzige Wahrheit.

Dieselbe Regel wie `pdf/geometry.py` fürs Kartenlayout und `gui/theme.py` für die
Farben: kein Modul baut sich seine Pfade selbst zusammen.

Der Grund ist das Bündeln (PyInstaller). Aus der Quelle gestartet ist das
Arbeitsverzeichnis üblicherweise der Projektordner, und relative Pfade wie
``"config.yaml"`` treffen. Per Doppelklick auf eine gebündelte Anwendung ist das
Arbeitsverzeichnis dagegen `C:\\Windows\\System32` bzw. `$HOME` — dieselben Pfade
zeigen dann irgendwohin. Hier werden deshalb drei Orte streng auseinandergehalten:

* **Mitgelieferte Dateien** (`resource_path`): Schriften, Icons, `handbuch.md`,
  `config.example.yaml`. Nur lesbar. Im Bündel liegen sie in `sys._MEIPASS`.
* **Programmordner** (`program_dir`): der Ordner der ausführbaren Datei bzw. die
  Projektwurzel. Hier sucht der Portable-Modus seine `config.yaml`.
* **Benutzerordner** (`user_data_dir`): plattformüblich, immer beschreibbar.
  Dorthin gehen Config, Lookup-Cache und Protokoll, wenn nichts daneben liegt.

Die Modul-Funktionen fragen den Zustand **bei jedem Aufruf** neu ab (statt ihn in
Konstanten einzufrieren), damit die Tests `sys.frozen`/`sys.executable` setzen
können.

Reine Standardbibliothek und keine Importe aus dem eigenen Paket: `paths` steht
unter allem anderen und darf keine Zyklen erzeugen.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Name des Programmordners im Benutzerverzeichnis. Unter Windows und macOS ist
# ein sprechender Name mit Großbuchstaben üblich, unter Linux ein kleingeschriebener
# ohne Leerzeichen (er landet in `~/.config`).
APP_DIR_NAME = "QSL-Karten-Generator"
APP_DIR_NAME_XDG = "qsl-karten-generator"

# Dateinamen. Sie stehen hier, nicht bei den Aufrufern — sonst tauchte derselbe
# String in `gui/app.py`, `lookup/` und den Tests dreimal auf.
CONFIG_NAME = "config.yaml"
EXAMPLE_CONFIG_NAME = "config.example.yaml"
CACHE_NAME = "lookup_cache.json"
MOSTWANTED_NAME = "mostwanted.json"
CTY_NAME = "cty.dat"
HANDBOOK_NAME = "handbuch.md"
LOG_NAME = "qslcards.log"


# ------------------------------------------------------------------ Zustand
def is_frozen() -> bool:
    """`True`, wenn das Programm als gebündelte Anwendung läuft (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Wurzel der mitgelieferten Dateien.

    Im Bündel entpackt PyInstaller sie nach `sys._MEIPASS`; aus der Quelle ist es
    die Projektwurzel (ein Verzeichnis über dem Paket). In beiden Fällen liegt das
    Paket darunter als `qslcards/`, die Aufrufe sehen also denselben Aufbau.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Pfad einer mitgelieferten Datei, z. B. `resource_path("handbuch.md")`."""
    return resource_dir().joinpath(*parts)


def program_dir() -> Path:
    """Ordner, in dem das Programm für den Anwender „liegt".

    Aus der Quelle die Projektwurzel — bewusst nicht das Arbeitsverzeichnis, damit
    die `config.yaml` des Projekts auch dann gefunden wird, wenn das Programm aus
    einem anderen Ordner gestartet wurde.

    Gebündelt der Ordner der ausführbaren Datei. Auf macOS steckt die aber drei
    Ebenen tief in `Name.app/Contents/MacOS/` — der Anwender sieht dort nur die
    `.app`, und „daneben" heißt für ihn *neben der `.app`*.
    """
    if not is_frozen():
        return Path(__file__).resolve().parent.parent

    exe_dir = Path(sys.executable).resolve().parent
    if exe_dir.name == "MacOS" and exe_dir.parent.name == "Contents":
        bundle = exe_dir.parent.parent
        if bundle.suffix == ".app":
            return bundle.parent
    return exe_dir


def user_data_dir() -> Path:
    """Plattformüblicher, immer beschreibbarer Ordner für Config/Cache/Protokoll."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
        return root / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / APP_DIR_NAME_XDG


# -------------------------------------------------------------- Datenablage
def is_portable() -> bool:
    """`True`, wenn neben dem Programm eine `config.yaml` liegt.

    Nur im gebündelten Betrieb interessant: dann arbeitet das Programm komplett in
    seinem eigenen Ordner (USB-Stick, „mitnehmbare" Installation) und fasst den
    Benutzerordner nicht an. Aus der Quelle ist ohnehin immer die Projektwurzel
    zuständig.
    """
    return is_frozen() and (program_dir() / CONFIG_NAME).is_file()


def data_dir() -> Path:
    """Ordner für Config, Lookup-Cache und Protokoll.

    Config und Cache gehören zusammen — laufen sie auseinander, gehört der Cache
    plötzlich zu einem anderen Konto. Deshalb entscheidet **eine** Funktion.
    """
    if not is_frozen():
        return program_dir()
    if is_portable():
        return program_dir()
    return user_data_dir()


def config_path() -> Path:
    return data_dir() / CONFIG_NAME


def cache_path() -> Path:
    return data_dir() / CACHE_NAME


def mostwanted_path() -> Path:
    """Gespeicherte GDXF-Rangliste (Most-Wanted-Filter) — neben dem Lookup-Cache."""
    return data_dir() / MOSTWANTED_NAME


def cty_path() -> Path:
    """Zuletzt geladene `cty.dat` (Rufzeichen -> DXCC) — neben dem Lookup-Cache.

    Fehlt sie, gilt die mitgelieferte Kopie (`bundled_cty_path`)."""
    return data_dir() / CTY_NAME


def bundled_cty_path() -> Path:
    """Die mit dem Programm ausgelieferte `cty.dat` (nur lesbar)."""
    return resource_path("qslcards", "assets", "dxcc", CTY_NAME)


def dxcc_numbers_path() -> Path:
    """Hauptpräfix der `cty.dat` -> ADIF-DXCC-Nummer (mitgeliefert, nur lesbar)."""
    return resource_path("qslcards", "assets", "dxcc", "dxcc-numbers.csv")


def log_path() -> Path:
    return data_dir() / LOG_NAME


def example_config_path() -> Path:
    """Die kommentierte Beispiel-Config (mitgeliefert, nur lesbar)."""
    return resource_path(EXAMPLE_CONFIG_NAME)


def default_output_dir() -> Path:
    """Vorschlag für die erzeugte PDF: der Dokumentenordner, sonst das Zuhause."""
    documents = Path.home() / "Documents"
    return documents if documents.is_dir() else Path.home()


def ensure_data_dir() -> Path:
    """Legt den Datenordner an, damit Config, Cache und Protokoll hineinpassen.

    Mehr ist nicht nötig: fehlt die `config.yaml`, liest das Programm die
    mitgelieferte `config.example.yaml` und der erste Auto-Save schreibt die
    echte Datei — inhaltlich identisch, weil beide aus denselben Defaults
    entstehen (`config.save`).

    Nie fatal — schlägt das Anlegen fehl (Nur-Lese-Medium), meldet das später der
    Auto-Save an der Statusleiste.
    """
    target = data_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return target


# ------------------------------------------------------------- Kindprozesse
# PyInstaller stellt seinen Bibliothekspfad an den Anfang von `LD_LIBRARY_PATH`
# (Linux) bzw. `DYLD_LIBRARY_PATH` (macOS) und sichert den ursprünglichen Wert
# unter `..._ORIG`. Das gilt auch für jeden Kindprozess — und ein `xdg-open` oder
# `gsettings`, das dadurch die gebündelten Bibliotheken statt der eigenen lädt,
# stirbt mit „symbol lookup error". Deshalb bekommt jeder externe Aufruf eine
# bereinigte Umgebung.
_LIBRARY_PATH_VARS = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "LD_PRELOAD")


def subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Umgebung für externe Programme, ohne die Bibliothekspfade des Bündels.

    Aus der Quelle bleibt die Umgebung unangetastet: dort hat niemand sie
    verbogen, und ein selbst gesetztes `LD_LIBRARY_PATH` gehört dem Entwickler.
    """
    env = dict(os.environ if base is None else base)
    if not is_frozen():
        return env
    for name in _LIBRARY_PATH_VARS:
        original = env.pop(f"{name}_ORIG", None)
        if original:
            env[name] = original
        else:
            env.pop(name, None)
    return env
