#!/usr/bin/env python3
"""Version anheben, prüfen, bauen, festschreiben — in einem Aufruf.

    python scripts/release.py patch       # 0.1.0 -> 0.1.1
    python scripts/release.py minor       # 0.1.0 -> 0.2.0
    python scripts/release.py major       # 0.1.0 -> 1.0.0
    python scripts/release.py 1.2.3       # genau diese Version
    python scripts/release.py --show      # nur nachsehen, was gerade gilt
    python scripts/release.py patch --dry-run   # den Ablauf zeigen, nichts tun

Abschaltbar ist jeder Schritt einzeln: `--no-tests`, `--no-build`, `--no-git`.

**Was dieses Skript ersetzt:** `npm version patch`. Das Projekt hat weder Node
noch eine `package.json`; eine anzulegen hieße, die Versionsnummer an zwei
Stellen zu führen. Der Ablauf ist derselbe, nur dass die eine Wahrheit
`qslcards/__init__.py` bleibt.

Reihenfolge eines Laufs — und warum sie so ist:

1. **Alle Vorbedingungen auf einmal** (saubere Arbeitskopie, Tag noch frei, neue
   Version größer als die alte, dazu die Prüfungen von `build_app`: Tk 9,
   PyInstaller). Sie laufen, **bevor** irgendetwas geändert wird: ein Release,
   das an Schritt vier scheitert, hinterlässt sonst eine halb angehobene
   Arbeitskopie.
2. **Tests.** Rote Tests kosten so gar nichts — die Versionszeile ist noch
   unberührt.
3. **Versionszeile schreiben.**
4. **Bauen und verpacken** (`build_app.py --clean`).
5. **Commit und Tag.**

Punkt 4 steht bewusst **vor** Punkt 5, anders als bei `npm version` (das erst
committet und den Build in einen `postversion`-Hook hängt). Am Ergebnis ändert
das nichts — der Build liest nur, er schreibt keine Quelldatei —, wohl aber am
Aufräumen: scheitert der Build hier, wird die Versionszeile zurückgesetzt und
die Arbeitskopie ist wieder sauber. Bei der npm-Reihenfolge stünden Commit und
Tag bereits für eine Fassung, die es nie gegeben hat.

Ein `git push` macht dieses Skript **nicht**. Das bleibt eine bewusste Handlung.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_app  # noqa: E402

INIT_FILE = ROOT / "qslcards" / "__init__.py"
BUILD_APP = ROOT / "scripts" / "build_app.py"

# Genau die eine Zeile, in der die Version steht — streng gefasst (drei Zahlen,
# doppelte Anführungszeichen, Zeilenanfang), damit ein Treffer nie ein Zufall
# ist: im selben Modul steht mit `__app_name__` eine ähnliche Zuweisung.
VERSION_LINE = re.compile(r'^__version__ = "(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)
VERSION_TEXT = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

LEVELS = ("major", "minor", "patch")
TAG_PREFIX = "v"
COMMIT_MESSAGE = "chore(release): Version {version}"

Version = tuple[int, int, int]


# ------------------------------------------------------------------- Version
def read_version() -> Version:
    text = INIT_FILE.read_text(encoding="utf-8")
    match = VERSION_LINE.search(text)
    if match is None:
        raise SystemExit(
            f'In {INIT_FILE.relative_to(ROOT)} steht keine Zeile __version__ = "X.Y.Z".'
        )
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def format_version(version: Version) -> str:
    return ".".join(str(part) for part in version)


def bumped(current: Version, level: str) -> Version:
    """Eine Stelle hoch, alle kleineren auf 0 — wie bei `npm version`."""
    major, minor, patch = current
    if level == "major":
        return major + 1, 0, 0
    if level == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def target_version(request: str, current: Version) -> Version:
    """`patch`/`minor`/`major` oder eine ausgeschriebene Version `X.Y.Z`."""
    if request in LEVELS:
        return bumped(current, request)

    match = VERSION_TEXT.match(request)
    if match is None:
        raise SystemExit(f"„{request}“ ist weder {' | '.join(LEVELS)} noch eine Version X.Y.Z.")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def tag_name(version: Version) -> str:
    return f"{TAG_PREFIX}{format_version(version)}"


def write_version(version: Version) -> str:
    """Schreibt die neue Version und liefert den **vorherigen** Dateiinhalt.

    Der Rückgabewert ist die Rücknahme: scheitert der Build, wird er
    unverändert zurückgeschrieben.
    """
    before = INIT_FILE.read_text(encoding="utf-8")
    after, count = VERSION_LINE.subn(f'__version__ = "{format_version(version)}"', before)
    if count != 1:
        raise SystemExit(
            f"{INIT_FILE.relative_to(ROOT)}: {count} Versionszeilen gefunden, genau eine erwartet."
        )
    INIT_FILE.write_text(after, encoding="utf-8")
    return before


# ----------------------------------------------------------------------- Git
def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def working_tree_is_clean() -> bool:
    return git("status", "--porcelain") == ""


def tag_exists(tag: str) -> bool:
    return git("tag", "--list", tag) != ""


# ------------------------------------------------------------- Vorbedingungen
def check_prerequisites(
    current: Version, new: Version, *, use_git: bool, do_build: bool
) -> list[str]:
    """Liefert die Liste der Probleme — leer heißt: es kann losgehen.

    Alle auf einmal, wie in `build_app.check_prerequisites`: wer eine Version
    ausliefert, möchte nicht dreimal hintereinander an einer neuen Hürde
    scheitern.
    """
    problems: list[str] = []

    if new <= current:
        problems.append(
            f"Die Version soll von {format_version(current)} auf {format_version(new)} — "
            "das geht rückwärts oder nirgendwohin. Vermutlich ein Vertipper."
        )

    if use_git:
        if not working_tree_is_clean():
            problems.append(
                "Die Arbeitskopie ist nicht sauber (git status). Der Release-Commit soll "
                "nur die Versionszeile enthalten — alles andere vorher committen oder "
                "mit --no-git arbeiten."
            )
        tag = tag_name(new)
        if tag_exists(tag):
            problems.append(f"Den Tag {tag} gibt es schon.")

    if do_build:
        problems += build_app.check_prerequisites()

    return problems


# --------------------------------------------------------------------- Schritte
def run_tests() -> bool:
    """Die Testsuite — Ausgabe läuft durch, ein roter Test soll lesbar sein."""
    cmd = [sys.executable, "-m", "pytest", "tests", "-q"]
    print("→", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode == 0


def run_build() -> bool:
    """Bauen in einem **eigenen** Prozess — nicht über `build_app.main()`.

    `build_app` liest `__version__` beim Import. In diesem Prozess steht dort
    noch die alte Nummer, das Archiv hieße also nach der Vorgängerversion. Ein
    frischer Interpreter liest die gerade geschriebene Datei.
    """
    cmd = [sys.executable, str(BUILD_APP), "--clean"]
    print("→", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode == 0


def find_archive(version: Version) -> Path | None:
    """Das eben erzeugte Archiv (`.zip` bzw. `.tar.gz`) in `dist/`.

    Gesucht statt zusammengebaut: welche Endung die Plattform bekommt, weiß
    `build_app` — diese Regel soll nicht an zwei Stellen stehen.
    """
    stem = f"{build_app.APP_NAME}-{format_version(version)}-{build_app.platform_tag()}"
    for candidate in sorted(build_app.DIST_DIR.glob(f"{stem}.*")):
        if candidate.is_file():
            return candidate
    return None


def describe_plan(new: Version, *, run_tests_first: bool, do_build: bool, use_git: bool) -> None:
    print("\n--dry-run — es wird nichts geändert. Geplant wäre:")
    if run_tests_first:
        print("  - Tests laufen lassen")
    print(f"  - {INIT_FILE.relative_to(ROOT)}: Version {format_version(new)} schreiben")
    if do_build:
        print(f"  - bauen und verpacken für {build_app.platform_tag()}")
    if use_git:
        print(f'  - git commit -m "{COMMIT_MESSAGE.format(version=format_version(new))}"')
        print(f"  - git tag {tag_name(new)}")


# ---------------------------------------------------------------------- Ablauf
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "version", nargs="?", help=f"{' | '.join(LEVELS)} oder eine Version der Form X.Y.Z"
    )
    parser.add_argument("--show", action="store_true", help="nur die aktuelle Version nennen")
    parser.add_argument("--no-tests", action="store_true", help="die Testsuite überspringen")
    parser.add_argument("--no-build", action="store_true", help="nur anheben, nicht bauen")
    parser.add_argument("--no-git", action="store_true", help="nicht committen und nicht taggen")
    parser.add_argument("--dry-run", action="store_true", help="nur zeigen, was geschähe")
    args = parser.parse_args(argv)

    current = read_version()
    if args.show:
        print(f"{build_app.APP_NAME} {format_version(current)}")
        return 0
    if args.version is None:
        parser.error(f"{' | '.join(LEVELS)}, eine Version X.Y.Z oder --show angeben")

    new = target_version(args.version, current)
    run_tests_first = not args.no_tests
    do_build = not args.no_build
    use_git = not args.no_git

    problems = check_prerequisites(current, new, use_git=use_git, do_build=do_build)
    if problems:
        print("Der Release kann so nicht laufen:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"{build_app.APP_NAME} {format_version(current)} → {format_version(new)}")
    if args.dry_run:
        describe_plan(new, run_tests_first=run_tests_first, do_build=do_build, use_git=use_git)
        return 0

    if run_tests_first and not run_tests():
        print("\nTests rot — die Version bleibt, wie sie war.", file=sys.stderr)
        return 1

    before = write_version(new)
    print(f"  {INIT_FILE.relative_to(ROOT)}: Version {format_version(new)}")

    if do_build and not run_build():
        INIT_FILE.write_text(before, encoding="utf-8")
        print(
            f"\nDer Build ist gescheitert. Die Version steht wieder auf "
            f"{format_version(current)}, die Arbeitskopie ist unverändert.",
            file=sys.stderr,
        )
        return 1

    if use_git:
        git("add", str(INIT_FILE))
        git("commit", "-m", COMMIT_MESSAGE.format(version=format_version(new)))
        git("tag", tag_name(new))
        print(f"  git commit + git tag {tag_name(new)}  (kein push — das bleibt bei dir)")

    if do_build:
        archive = find_archive(new)
        print(f"\nArchiv: {archive}" if archive else "\nGebaut, aber kein Archiv in dist/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
