"""Der Versionssprung (`scripts/release.py`).

Warum das Tests braucht: dieses Skript schreibt in eine Quelldatei, committet
und setzt einen Tag — die drei Dinge, die man nach einem Fehlgriff von Hand
wieder auseinandersortieren muss. Festgehalten wird deshalb vor allem, was
**nicht** passieren darf:

* eine rückwärts laufende Versionsnummer (der klassische Vertipper),
* ein Commit, der nicht nur die Versionszeile enthält,
* und eine angehobene Versionszeile, die nach einem gescheiterten Build stehen
  bleibt.

Gebaut und committet wird hier natürlich nie: die Schritte sind einzelne
Funktionen im Modul, genau damit sie sich austauschen lassen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_app  # noqa: E402
import release  # noqa: E402

PACKAGE_HEAD = '''"""QSL-Karten-Generator."""

from __future__ import annotations

__version__ = "1.2.3"
__app_name__ = "QSL-Karten-Generator"
'''


@pytest.fixture
def init_file(tmp_path, monkeypatch):
    """Eine Attrappe von `qslcards/__init__.py` — die echte bleibt unberührt."""
    path = tmp_path / "__init__.py"
    path.write_text(PACKAGE_HEAD, encoding="utf-8")
    monkeypatch.setattr(release, "INIT_FILE", path)
    monkeypatch.setattr(release, "ROOT", tmp_path)
    return path


@pytest.fixture
def no_side_effects(monkeypatch):
    """Git, Tests und Build stillgelegt; der Lauf geht sonst durch."""
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(release, "git", lambda *args: calls.append(args) or "")
    monkeypatch.setattr(release, "working_tree_is_clean", lambda: True)
    monkeypatch.setattr(release, "tag_exists", lambda tag: False)
    monkeypatch.setattr(release, "run_tests", lambda: True)
    monkeypatch.setattr(release, "run_build", lambda: True)
    monkeypatch.setattr(release, "find_archive", lambda version: None)
    monkeypatch.setattr(build_app, "check_prerequisites", list)
    return calls


# ------------------------------------------------------------------- Rechnen
def test_reads_the_version_from_the_package(init_file):
    assert release.read_version() == (1, 2, 3)


@pytest.mark.parametrize(
    ("level", "expected"),
    [("patch", (1, 2, 4)), ("minor", (1, 3, 0)), ("major", (2, 0, 0))],
)
def test_bump_resets_the_smaller_places(level, expected):
    """Wie bei `npm version`: 1.2.3 minor ist 1.3.0, nicht 1.3.3."""
    assert release.bumped((1, 2, 3), level) == expected


def test_an_explicit_version_is_taken_as_it_is():
    assert release.target_version("2.0.0", (1, 2, 3)) == (2, 0, 0)


@pytest.mark.parametrize("request_", ["1.2", "v1.2.3", "1.2.3-rc1", "next", ""])
def test_anything_else_is_refused(request_):
    with pytest.raises(SystemExit):
        release.target_version(request_, (1, 2, 3))


# -------------------------------------------------------------------- Schreiben
def test_only_the_version_line_changes(init_file):
    before = release.write_version((1, 3, 0))

    after = init_file.read_text(encoding="utf-8")
    assert before == PACKAGE_HEAD  # die Rücknahme für einen geplatzten Build
    assert '__version__ = "1.3.0"' in after
    # Der Name sieht der Versionszeile ähnlich und darf nicht mitgefangen werden.
    assert '__app_name__ = "QSL-Karten-Generator"' in after
    assert after.splitlines()[0] == '"""QSL-Karten-Generator."""'


# -------------------------------------------------------------- Vorbedingungen
def test_a_backwards_version_is_refused(init_file):
    problems = release.check_prerequisites((1, 2, 3), (1, 2, 0), use_git=False, do_build=False)
    assert len(problems) == 1
    assert "rückwärts" in problems[0]


def test_the_same_version_twice_is_refused(init_file):
    problems = release.check_prerequisites((1, 2, 3), (1, 2, 3), use_git=False, do_build=False)
    assert len(problems) == 1


def test_a_dirty_working_tree_is_refused(monkeypatch):
    monkeypatch.setattr(release, "working_tree_is_clean", lambda: False)
    monkeypatch.setattr(release, "tag_exists", lambda tag: False)

    problems = release.check_prerequisites((1, 2, 3), (1, 2, 4), use_git=True, do_build=False)

    assert any("nicht sauber" in problem for problem in problems)


def test_an_existing_tag_is_refused(monkeypatch):
    monkeypatch.setattr(release, "working_tree_is_clean", lambda: True)
    monkeypatch.setattr(release, "tag_exists", lambda tag: tag == "v1.2.4")

    problems = release.check_prerequisites((1, 2, 3), (1, 2, 4), use_git=True, do_build=False)

    assert any("v1.2.4" in problem for problem in problems)


def test_the_build_prerequisites_are_checked_before_anything_changes(init_file, monkeypatch):
    """Tk 9 und PyInstaller werden **vorher** geprüft, nicht erst beim Bauen.

    Sonst stünde die neue Version schon in der Datei, wenn `build_app` absagt.
    """
    monkeypatch.setattr(release, "working_tree_is_clean", lambda: True)
    monkeypatch.setattr(release, "tag_exists", lambda tag: False)
    monkeypatch.setattr(build_app, "check_prerequisites", lambda: ["Tk 8.6 statt 9.0"])

    assert release.main(["patch"]) == 1
    assert '__version__ = "1.2.3"' in init_file.read_text(encoding="utf-8")


# --------------------------------------------------------------------- Ablauf
def test_dry_run_changes_nothing(init_file, no_side_effects, capsys):
    assert release.main(["minor", "--dry-run"]) == 0

    assert init_file.read_text(encoding="utf-8") == PACKAGE_HEAD
    assert no_side_effects == []
    assert "1.3.0" in capsys.readouterr().out


def test_a_full_run_writes_commits_and_tags(init_file, no_side_effects):
    assert release.main(["patch"]) == 0

    assert '__version__ = "1.2.4"' in init_file.read_text(encoding="utf-8")
    assert ("commit", "-m", "chore(release): Version 1.2.4") in no_side_effects
    assert ("tag", "v1.2.4") in no_side_effects


def test_red_tests_leave_the_version_alone(init_file, no_side_effects, monkeypatch):
    monkeypatch.setattr(release, "run_tests", lambda: False)

    assert release.main(["patch"]) == 1
    assert init_file.read_text(encoding="utf-8") == PACKAGE_HEAD
    assert no_side_effects == []


def test_a_failed_build_rolls_the_version_back(init_file, no_side_effects, monkeypatch):
    """Der Grund, warum gebaut wird, **bevor** committet wird.

    Andersherum (die Reihenfolge von `npm version`) bliebe ein Release-Commit
    samt Tag für eine Fassung stehen, die nie gebaut werden konnte.
    """
    monkeypatch.setattr(release, "run_build", lambda: False)

    assert release.main(["major"]) == 1
    assert init_file.read_text(encoding="utf-8") == PACKAGE_HEAD
    assert no_side_effects == []  # kein Commit, kein Tag


def test_no_git_skips_commit_and_tag(init_file, no_side_effects):
    assert release.main(["patch", "--no-git"]) == 0

    assert '__version__ = "1.2.4"' in init_file.read_text(encoding="utf-8")
    assert no_side_effects == []


def test_show_only_reports(init_file, no_side_effects, capsys):
    assert release.main(["--show"]) == 0

    assert init_file.read_text(encoding="utf-8") == PACKAGE_HEAD
    assert "1.2.3" in capsys.readouterr().out


def test_the_archive_name_carries_name_version_and_platform(tmp_path, monkeypatch):
    """Der Dateiname des Archivs ist das, was der Anwender herunterlädt."""
    dist = tmp_path / "dist"
    dist.mkdir()
    stem = f"{build_app.APP_NAME}-1.2.4-{build_app.platform_tag()}"
    (dist / f"{stem}.zip").write_bytes(b"")
    monkeypatch.setattr(build_app, "DIST_DIR", dist)

    assert release.find_archive((1, 2, 4)).name == f"{stem}.zip"
    assert release.find_archive((9, 9, 9)) is None
