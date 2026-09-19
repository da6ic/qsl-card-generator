#!/usr/bin/env python3
"""Baut die auslieferbare Anwendung für die Plattform, auf der es läuft.

    python scripts/build_app.py            # bauen und verpacken
    python scripts/build_app.py --no-package   # nur bauen (zum Nachsehen)
    python scripts/build_app.py --clean        # vorher build/ und dist/ leeren

**Cross-Compile gibt es nicht.** PyInstaller bündelt den Interpreter, unter dem
es läuft — ein Windows-Programm entsteht nur auf Windows, ein Fedora-Programm nur
auf Linux. Die Anleitungen dafür stehen in `packaging/windows/README.md` und
`packaging/linux/README.md`.

Warum die Prüfungen am Anfang so streng sind: die beiden häufigsten Fehler beim
Bündeln dieser Anwendung äußern sich **nicht** als Absturz, sondern als stilles
Fehlen. Mit Tk 8.6 verschwinden die Stift-/Schalter-Icons der Vorschautabelle
(`gui/preview.py` fängt den Fehler ab), und mit PyInstaller < 6.21 kommt Tcl/Tk 9
gar nicht erst mit. Beides fällt erst dem Anwender auf.

**Die harte Bedingung ist Tk 9, nicht eine Python-Version** — woher Tk kommt, ist
je nach Plattform verschieden:

* Windows und macOS: Tcl/Tk steckt im Python-Installer. Erst **3.14** bringt 9.0.4
  mit; 3.13 hat nur 8.6.15.
* Linux: Tk kommt vom System, nicht vom Interpreter. Auf Fedora 42 liefert schon
  das mitgelieferte Python 3.13 ein Tk 9.0 — eine Python-Hürde wäre hier falsch.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from qslcards import __app_name__ as APP_NAME  # noqa: E402
from qslcards import __version__  # noqa: E402

SPEC = ROOT / "packaging" / "qslcards.spec"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"

# Untergrenzen, mit Begründung im Modul-Docstring.
MIN_PYTHON = (3, 11)  # wie `requires-python` in pyproject.toml
MIN_PYINSTALLER = (6, 21)
MIN_TK = 9.0  # die eigentliche Bedingung — siehe Modul-Docstring

# Ältestes macOS, das die Anleitung (`packaging/macos/README.md`) zusagt. Ob das
# Bündel dort wirklich läuft, hängt aber nicht von dieser Zahl ab, sondern vom
# **bauenden Interpreter** — siehe `macos_deployment_target`.
MACOS_SUPPORTED_FLOOR = (11, 0)

# Apple Silicon gibt es erst ab macOS 11 — ein arm64-Bündel kann gar nicht älter
# sein, was auch immer das Deployment-Target behauptet. Der universal2-Installer
# von python.org meldet `10.15` (das gilt für die x86_64-Hälfte), die arm64-Hälfte
# trägt trotzdem `minos 11.0`. Ohne diese Untergrenze stünde in der Info.plist
# wieder eine Zahl, die die mitgelieferten Bibliotheken nicht halten — derselbe
# Fehler wie beim festen „11.0", nur eine Etage tiefer.
MACOS_ARCH_FLOOR = {"arm64": (11, 0)}


# --------------------------------------------------------------- Vorbedingungen
def _tk_version() -> float | None:
    """Tk-Version des bauenden Interpreters (nicht die von PyInstaller)."""
    try:
        import tkinter

        return float(tkinter.TkVersion)
    except Exception:
        return None


def _pyinstaller_version() -> tuple[int, ...] | None:
    try:
        import PyInstaller

        return tuple(int(p) for p in PyInstaller.__version__.split(".")[:2])
    except Exception:
        return None


def _tcl_uses_embedded_data() -> bool:
    """Trägt Tcl seine Bibliothek in der DLL statt in einem Ordner daneben?

    Tcl 9 kann das (`info library` liefert dann einen virtuellen Pfad
    `//zipfs:/…`). Der Windows-Installer von Python 3.14.7 macht davon Gebrauch.
    """
    try:
        import tkinter

        return tkinter.Tcl().eval("info library").startswith("//zipfs:/")
    except Exception:
        return False


def _pyinstaller_handles_embedded_tcl() -> bool:
    """Kommt dieses PyInstaller mit eingebetteten Tcl-Daten zurecht?

    Über die Versionsnummer ist das **nicht** zu beantworten: die Fassung mit dem
    Fix meldet sich weiterhin als 6.21.0, weil sie noch nicht veröffentlicht ist.
    Deshalb wird die Fähigkeit direkt an der Quelle geprüft.
    """
    try:
        import inspect

        from PyInstaller.utils.hooks import tcl_tk

        return "//zipfs:/" in inspect.getsource(tcl_tk)
    except Exception:
        return False


def check_prerequisites() -> list[str]:
    """Liefert die Liste der Probleme — leer heißt: es kann losgehen."""
    problems: list[str] = []

    if sys.version_info[:2] < MIN_PYTHON:
        problems.append(
            f"Python {'.'.join(map(str, MIN_PYTHON))}+ nötig, gefunden "
            f"{platform.python_version()}."
        )

    pyi = _pyinstaller_version()
    if pyi is None:
        problems.append('PyInstaller fehlt. Abhilfe: pip install -e ".[build]"')
    elif pyi < MIN_PYINSTALLER:
        problems.append(
            f"PyInstaller {'.'.join(map(str, MIN_PYINSTALLER))}+ nötig — erst dort kommt "
            "Tcl/Tk 9 mit eingebettetem Datenarchiv mit."
        )

    tk = _tk_version()
    if tk is None:
        problems.append(
            "tkinter ist in diesem Python nicht verfügbar (Fedora: dnf install python3-tkinter, "
            "Homebrew: brew install python-tk)."
        )
    elif tk < MIN_TK:
        # Nicht „3.14" — beim Installer von python.org zählt die Punktversion:
        # 3.14.0 bis 3.14.6 lieferten noch Tcl/Tk 8.6.15, erst 3.14.7 bringt
        # 9.0.4 mit. Homebrew und Linux hängen dagegen gar nicht am Interpreter.
        if sys.platform.startswith("win"):
            hint = (
                "Python 3.14.7 oder neuer verwenden — erst dieser Installer bringt "
                "Tcl/Tk 9.0.4 mit (3.14.0–3.14.6 und 3.13 haben 8.6.15)."
            )
        elif sys.platform == "darwin":
            hint = (
                "Von python.org Python 3.14.7 oder neuer verwenden — erst dieser "
                "Installer bringt Tcl/Tk 9.0.4 mit (3.14.0–3.14.6 und 3.13 haben "
                "8.6.15). Mit Homebrew zählt die Punktversion nicht: dessen Python "
                "bindet das Paket tcl-tk ein (brew install tcl-tk python-tk)."
            )
        else:
            hint = "Tk kommt hier vom System: Fedora 42+ liefert Tcl/Tk 9."
        problems.append(
            f"Tk {tk} statt {MIN_TK}+ (mit Python {platform.python_version()}). Die Stift-/"
            f"Schalter-Icons der Vorschautabelle würden im fertigen Programm fehlen — "
            f"ohne jede Fehlermeldung. {hint}"
        )

    # Tcl 9 mit eingebetteter Bibliothek + PyInstaller ohne die passende
    # Behandlung ergibt ein Bündel, das erst beim **Start** stirbt
    # („Tcl data directory ... not found"). Deshalb hier abfangen.
    if _tcl_uses_embedded_data() and not _pyinstaller_handles_embedded_tcl():
        problems.append(
            "Dieses Tcl trägt seine Bibliothek in der DLL (Tcl 9, wie im "
            "Windows-Installer von Python 3.14.7), aber dieses PyInstaller kennt "
            "den Fall noch nicht — das fertige Programm bräche beim Start ab. Der "
            "Fix ist in PyInstaller, aber noch nicht veröffentlicht (6.21.0 hat ihn "
            "nicht). Abhilfe:\n"
            '      pip install --force-reinstall "pyinstaller @ '
            'git+https://github.com/pyinstaller/pyinstaller.git@develop"'
        )

    for needed in (SPEC, ROOT / "handbuch.md", ROOT / "config.example.yaml"):
        if not needed.is_file():
            problems.append(f"Datei fehlt: {needed.relative_to(ROOT)}")

    return problems


# --------------------------------------------------------- macOS-Mindestversion
def macos_deployment_target() -> tuple[int, int] | None:
    """Ältestes macOS, gegen das der bauende Interpreter gelinkt ist.

    PyInstaller bündelt die Bibliotheken **dieses** Interpreters — CPythons
    Erweiterungsmodule, Tcl/Tk, OpenSSL, zlib. Sie tragen alle dessen
    Deployment-Target, und `dyld` lehnt eine dylib ab, die für ein neueres
    System gebaut wurde als das laufende. Das Bündel startet dort also nicht.

    Entscheidend ist die Herkunft des Interpreters: **Homebrew baut immer gegen
    das gerade laufende System** — auf einem Mac mit macOS 26 entsteht damit ein
    Bündel, das auf macOS 15 nicht startet. Der Installer von python.org ist
    dagegen gegen ein altes Ziel gebaut (10.13 bzw. 11.0).

    Außerhalb von macOS `None` (dort gibt es keine `.app`).
    """
    if sys.platform != "darwin":
        return None
    raw = str(sysconfig.get_config_var("MACOSX_DEPLOYMENT_TARGET") or "").strip()
    if not raw:
        return None
    try:
        parts = [int(p) for p in raw.split(".")[:2]]
    except ValueError:
        return None
    if not parts:
        return None
    major = parts[0]
    minor = parts[1] if len(parts) > 1 else 0
    return (major, minor)


def macos_minimum_system_version() -> str:
    """Der Wert für `LSMinimumSystemVersion` in der `Info.plist`.

    Er wird **nicht** fest eingetragen, sondern hier abgeleitet: eine zu niedrige
    Angabe ist die schlimmere Sorte Fehler. Launch Services lässt das Programm
    dann starten, der Bootloader von PyInstaller (der bei 11.0 liegt) läuft
    tatsächlich an — und erst beim Nachladen der Bibliotheken bricht alles mit
    einer dyld-Meldung ab, die dem Anwender nichts sagt. Steht die Wahrheit
    drin, meldet macOS sauber „erfordert macOS X oder neuer".

    Zwei Werte gehen ein: das Deployment-Target des Interpreters **und** die
    Untergrenze der Architektur (`MACOS_ARCH_FLOOR`). Der universal2-Installer
    von python.org meldet `10.15`, seine arm64-Hälfte trägt aber `minos 11.0` —
    die höhere der beiden Zahlen ist die wahre.
    """
    target = macos_deployment_target() or MACOS_SUPPORTED_FLOOR
    floor = MACOS_ARCH_FLOOR.get(platform.machine().lower())
    if floor is not None and floor > target:
        target = floor
    return f"{target[0]}.{target[1]}"


def check_warnings() -> list[str]:
    """Hinweise, die den Build nicht verhindern, aber die **Auslieferung**
    einschränken — anders als `check_prerequisites` ist das keine Hürde, sondern
    eine Information: für wen das Ergebnis taugt, entscheidet der Bauende."""
    notes: list[str] = []
    target = macos_deployment_target()
    if target is not None and target > MACOS_SUPPORTED_FLOOR:
        version = f"{target[0]}.{target[1]}"
        notes.append(
            f"Dieser Interpreter ist gegen macOS {version} gebaut "
            f"(MACOSX_DEPLOYMENT_TARGET). Das Bündel läuft damit **nur auf macOS "
            f"{version} und neuer** — auf älteren Systemen lehnt dyld die "
            f"mitgelieferten Bibliotheken (CPython, Tcl/Tk, OpenSSL) ab und das "
            f"Programm startet gar nicht.\n"
            f"    Die Info.plist trägt {version} korrekt ein, macOS meldet also "
            f"sauber \u201eerfordert macOS {version}\u201c statt abzustürzen.\n"
            f"    Für ältere Systeme mit dem Installer von python.org bauen "
            f"(3.14.7+, Ziel 10.13/11.0) statt mit Homebrew — Homebrew baut "
            f"immer gegen das laufende System."
        )
    return notes


# ------------------------------------------------------------------ Benennung
def platform_tag() -> str:
    """Kurzname für den Dateinamen: `windows-x64`, `linux-x86_64`, `macos-arm64`."""
    machine = platform.machine().lower()
    if sys.platform.startswith("win"):
        # `platform.machine()` meldet unter einem 32-Bit-Python auf 64-Bit-Windows
        # trotzdem AMD64 — entscheidend ist die Bitbreite des Interpreters.
        bits = "x64" if sys.maxsize > 2**32 else "x86"
        if machine.startswith("arm"):
            bits = "arm64"
        return f"windows-{bits}"
    if sys.platform == "darwin":
        return f"macos-{'arm64' if machine == 'arm64' else 'x86_64'}"
    return f"linux-{machine}"


def archive_stem() -> str:
    return f"{APP_NAME}-{__version__}-{platform_tag()}"


# ------------------------------------------------------------- Windows-Ressource
def write_version_resource() -> None:
    """Erzeugt die Versions-Ressource, die Windows in den Dateieigenschaften zeigt.

    Das Format erwartet vier Zahlen; `__version__` hat drei — die vierte ist 0.
    """
    parts = [int(p) for p in __version__.split(".")[:3]]
    while len(parts) < 4:
        parts.append(0)
    quad = ", ".join(str(p) for p in parts)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "version_info.txt").write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({quad}), prodvers=({quad}), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704b0', [
        StringStruct('FileDescription', '{APP_NAME}'),
        StringStruct('FileVersion', '{__version__}'),
        StringStruct('InternalName', 'qslcards'),
        StringStruct('OriginalFilename', '{APP_NAME}.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
""",
        encoding="utf-8",
    )


# ------------------------------------------------------------------ Verpacken
# Platzhalter in `packaging/macos/LIESMICH.txt`, den das Verpacken füllt.
MACOS_MINIMUM_PLACEHOLDER = "@MINIMUM@"


def write_macos_guide(folder: Path) -> Path | None:
    """Legt die Kurzanleitung in den Auslieferordner — mit der **echten**
    Systemvoraussetzung statt eines Platzhalters.

    Sie hängt am bauenden Interpreter (siehe `macos_deployment_target`) und kann
    deshalb nicht im Quelltext der Anleitung stehen. Ohne diesen Schritt läse der
    Empfänger eine Datei, die von „macOS 14 und älter" spricht, während das
    Programm dort gar nicht startet.
    """
    guide = ROOT / "packaging" / "macos" / "LIESMICH.txt"
    if not guide.is_file():
        return None
    text = guide.read_text(encoding="utf-8").replace(
        MACOS_MINIMUM_PLACEHOLDER, macos_minimum_system_version()
    )
    target = folder / guide.name
    target.write_text(text, encoding="utf-8")
    return target


def package_macos(folder: Path) -> Path:
    """Auslieferordner als ZIP — zwingend mit `ditto`.

    Ein gewöhnliches `zip` (auch der Umweg über `shutil.make_archive`) löst die
    Symlinks in `Contents/Frameworks` auf und zerstört damit die Code-Signatur;
    die entpackte Anwendung startet dann auf Apple Silicon nicht mehr
    („is damaged").

    Die Kurzanleitung wandert **in den Ordner**, nicht bloß ins Archiv — dasselbe
    Prinzip wie bei Windows und Linux: was ausgeliefert wird, ist genau das, was
    in `dist/` ausprobiert wurde.
    """
    write_macos_guide(folder)

    target = DIST_DIR / f"{archive_stem()}.zip"
    target.unlink(missing_ok=True)
    subprocess.run(
        ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(folder), str(target)],
        check=True,
    )
    return target


def package_zip(folder: Path) -> Path:
    """ZIP für Windows — mit der Kurzanleitung neben der `.exe`.

    Sie beantwortet nur, was **vor** dem ersten Start zählt (wohin entpacken,
    SmartScreen) und verweist für alles Weitere aufs Handbuch; das bleibt die
    eine Wahrheit zur Bedienung.

    Die Datei wandert **in den Ordner**, nicht bloß ins Archiv: so ist das, was
    ausgeliefert wird, genau das, was in `dist/` ausprobiert wurde — und
    `shutil.make_archive` könnte eine Einzeldatei ohnehin nicht nachtragen.
    """
    guide = ROOT / "packaging" / "windows" / "LIESMICH.txt"
    if guide.is_file():
        shutil.copy2(guide, folder / guide.name)

    target = DIST_DIR / f"{archive_stem()}.zip"
    target.unlink(missing_ok=True)
    shutil.make_archive(str(target.with_suffix("")), "zip", folder.parent, folder.name)
    return target


def package_tar(folder: Path) -> Path:
    """tar.gz für Linux — erhält im Gegensatz zu ZIP die Ausführungsrechte.

    Mitgeliefert wird die Kurzanleitung, nicht `packaging/linux/README.md`: die
    beschreibt, wie man dieses Programm **baut** (Container, PyInstaller) und
    geht den Anwender nichts an, der es gerade heruntergeladen hat. Damit hat
    jede der drei Plattformen dieselbe `LIESMICH.txt` neben dem Programm.

    `install.sh` und die `.desktop`-Datei müssen mit, sonst bräuchte der
    Anwender für die Einrichtung zusätzlich das Repository.
    """
    guide = ROOT / "packaging" / "linux" / "LIESMICH.txt"
    if guide.is_file():
        shutil.copy2(guide, folder / guide.name)

    target = DIST_DIR / f"{archive_stem()}.tar.gz"
    target.unlink(missing_ok=True)
    extras = ROOT / "packaging" / "linux"
    with tarfile.open(target, "w:gz") as tar:
        tar.add(folder, arcname=folder.name)
        for name in ("install.sh", "qsl-karten-generator.desktop"):
            source = extras / name
            if source.is_file():
                tar.add(source, arcname=f"{folder.name}/{name}")
    return target


def macos_delivery_folder(app: Path) -> Path:
    """Legt die `.app` in den Ordner, der später ausgeliefert wird.

    Unter Windows und Linux ist das Bauergebnis von sich aus ein Ordner, neben
    die Programmdatei passt also eine Kurzanleitung. Auf macOS ist das Ergebnis
    die `.app` — und **in** die gehört nichts hinein, sie ist die Anwendung.
    Deshalb bekommt sie einen Ordner, der beides trägt.

    Verschoben statt kopiert: sonst lägen 200 MB doppelt in `dist/`, und der
    Anwender bekäme womöglich eine andere `.app` als die ausprobierte.

    Nebeneffekt, der willkommen ist: `paths.program_dir()` ist auf macOS der
    Ordner **über** der `.app` — behält der Anwender diesen Ordner (etwa auf
    einem USB-Stick), genügt eine `config.yaml` darin für den Portable-Modus.
    """
    folder = DIST_DIR / archive_stem()
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    app.rename(folder / app.name)
    return folder


# ---------------------------------------------------------------------- Ablauf
def build(clean: bool) -> Path:
    """Ruft PyInstaller auf und liefert das erzeugte Programm zurück."""
    if sys.platform.startswith("win"):
        write_version_resource()

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)]
    if clean:
        cmd.append("--clean")
    # `distpath`/`workpath` explizit, damit das Ergebnis unabhängig davon liegt,
    # aus welchem Ordner das Skript aufgerufen wurde.
    cmd += ["--distpath", str(DIST_DIR), "--workpath", str(BUILD_DIR / "pyinstaller")]

    print("→", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)

    result = DIST_DIR / (f"{APP_NAME}.app" if sys.platform == "darwin" else APP_NAME)
    if not result.exists():
        raise SystemExit(f"PyInstaller lief durch, aber {result} fehlt.")

    if sys.platform == "darwin":
        # Auf macOS entstehen zwei Ergebnisse: der rohe COLLECT-Ordner und die
        # `.app`, die dessen Inhalt bereits enthält. Der Ordner ist doppelt und
        # wäre neben der `.app` nur verwirrend — außerdem läge er im selben
        # Verzeichnis, in dem der Portable-Modus nach `config.yaml` sucht.
        shutil.rmtree(DIST_DIR / APP_NAME, ignore_errors=True)
        # Damit ist das Bauergebnis auf allen drei Plattformen der Ordner, der
        # ausgeliefert wird — `--no-package` zeigt genau ihn.
        result = macos_delivery_folder(result)

    return result


def folder_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / 1024 / 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-package", action="store_true", help="nur bauen, kein Archiv")
    parser.add_argument("--clean", action="store_true", help="build/ und dist/ vorher leeren")
    args = parser.parse_args()

    problems = check_prerequisites()
    if problems:
        print("Der Build kann so nicht laufen:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if args.clean:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    print(f"{APP_NAME} {__version__} für {platform_tag()}")
    print(f"Python {platform.python_version()}, Tk {_tk_version()}")
    if sys.platform == "darwin":
        print(f"Mindestens macOS {macos_minimum_system_version()}")
    print()

    for note in check_warnings():
        print(f"Achtung: {note}\n", file=sys.stderr)

    result = build(args.clean)
    print(f"\nFertig: {result}  ({folder_size_mb(result):.0f} MB)")

    if args.no_package:
        return 0

    if sys.platform == "darwin":
        archive = package_macos(result)
    elif sys.platform.startswith("win"):
        archive = package_zip(result)
    else:
        archive = package_tar(result)

    print(f"Archiv:  {archive}  ({archive.stat().st_size / 1024 / 1024:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
