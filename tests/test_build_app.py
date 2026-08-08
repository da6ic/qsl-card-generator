"""Vorbedingungsprüfung des Build-Skripts (`scripts/build_app.py`).

Der Grund für diese Tests ist ein konkreter Fehlschlag: ein Windows-Bündel ließ
sich ohne Murren bauen und starb dann beim Doppelklick mit „Tcl data directory
… not found". Ursache war Tcl 9 mit **eingebetteter** Bibliothek (der
Windows-Installer von Python 3.14.7 macht das) und ein PyInstaller, das diesen
Fall noch nicht kennt.

Die Tücke: die PyInstaller-Fassung **mit** dem Fix meldet sich weiterhin als
6.21.0, weil sie noch nicht veröffentlicht ist. Eine Versionsprüfung greift
also nicht — es braucht eine Fähigkeitsprüfung. Genau die wird hier festgehalten.
"""

from __future__ import annotations

import stat
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_app  # noqa: E402


@pytest.fixture
def sane(monkeypatch):
    """Alle Vorbedingungen erfüllt — Ausgangspunkt für die Einzelfälle."""
    monkeypatch.setattr(build_app, "_pyinstaller_version", lambda: (6, 21))
    monkeypatch.setattr(build_app, "_tk_version", lambda: 9.0)
    monkeypatch.setattr(build_app, "_tcl_uses_embedded_data", lambda: False)
    monkeypatch.setattr(build_app, "_pyinstaller_handles_embedded_tcl", lambda: True)


def test_no_problems_when_everything_fits(sane):
    assert build_app.check_prerequisites() == []


def test_embedded_tcl_without_support_is_refused(sane, monkeypatch):
    """Der Fall, der das kaputte Windows-Bündel erzeugt hat."""
    monkeypatch.setattr(build_app, "_tcl_uses_embedded_data", lambda: True)
    monkeypatch.setattr(build_app, "_pyinstaller_handles_embedded_tcl", lambda: False)

    problems = build_app.check_prerequisites()

    assert len(problems) == 1
    # Die Meldung muss den Ausweg nennen, sonst hilft sie niemandem.
    assert "git+https://github.com/pyinstaller/pyinstaller.git@develop" in problems[0]


def test_embedded_tcl_with_support_is_fine(sane, monkeypatch):
    monkeypatch.setattr(build_app, "_tcl_uses_embedded_data", lambda: True)
    assert build_app.check_prerequisites() == []


def test_external_tcl_needs_no_support(sane, monkeypatch):
    """Ohne eingebettete Daten ist die alte PyInstaller-Fassung völlig in Ordnung.

    Sonst würde die Prüfung auf macOS und Linux grundlos meckern — dort liegen
    die Tcl-Daten weiterhin als Ordner vor.
    """
    monkeypatch.setattr(build_app, "_pyinstaller_handles_embedded_tcl", lambda: False)
    assert build_app.check_prerequisites() == []


def test_old_tk_is_refused_with_the_patch_level_in_the_hint(sane, monkeypatch):
    """„Python 3.14" als Rat genügt nicht — 3.14.0 bis 3.14.6 haben Tk 8.6."""
    monkeypatch.setattr(build_app, "_tk_version", lambda: 8.6)

    problems = build_app.check_prerequisites()

    assert len(problems) == 1
    if sys.platform.startswith("win") or sys.platform == "darwin":
        assert "3.14.7" in problems[0]


def test_missing_pyinstaller_is_refused(sane, monkeypatch):
    monkeypatch.setattr(build_app, "_pyinstaller_version", lambda: None)
    assert any("PyInstaller fehlt" in p for p in build_app.check_prerequisites())


def test_platform_tag_is_usable_as_a_filename():
    tag = build_app.platform_tag()
    assert tag and " " not in tag
    assert build_app.archive_stem().endswith(tag)


def test_windows_zip_carries_the_short_guide(tmp_path, monkeypatch):
    """Die Kurzanleitung muss neben der `.exe` landen, nicht nur im Repository.

    Sie ist das Einzige, was den Anwender **vor** dem ersten Start erreicht —
    fehlt sie, steht er ohne Hinweis vor der SmartScreen-Meldung und hält das
    Programm für gefährlich.
    """
    dist = tmp_path / "dist"
    folder = dist / build_app.APP_NAME
    folder.mkdir(parents=True)
    (folder / f"{build_app.APP_NAME}.exe").write_bytes(b"")
    monkeypatch.setattr(build_app, "DIST_DIR", dist)

    archive = build_app.package_zip(folder)

    assert (folder / "LIESMICH.txt").is_file()
    with zipfile.ZipFile(archive) as bundle:
        assert f"{build_app.APP_NAME}/LIESMICH.txt" in bundle.namelist()


def _fake_app(dist: Path) -> Path:
    """Eine `.app`-Attrappe mit dem Symlink, auf den es beim Packen ankommt."""
    app = dist / f"{build_app.APP_NAME}.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "MacOS" / build_app.APP_NAME).write_bytes(b"")
    (app / "Contents" / "Frameworks").mkdir()
    (app / "Contents" / "Frameworks" / "Tk.framework").symlink_to("Versions/Current")
    return app


def test_macos_app_moves_into_a_folder_that_can_carry_the_guide(tmp_path, monkeypatch):
    """Auf macOS ist das Bauergebnis die `.app` — und in die gehört nichts hinein.

    Deshalb bekommt sie einen Ordner, der auch die Kurzanleitung trägt. Er wird
    verschoben, nicht kopiert: sonst lägen 200 MB doppelt in `dist/` und der
    Anwender bekäme womöglich eine andere `.app` als die ausprobierte.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    app = _fake_app(dist)
    monkeypatch.setattr(build_app, "DIST_DIR", dist)

    folder = build_app.macos_delivery_folder(app)

    assert folder.name == build_app.archive_stem()
    assert (folder / app.name).is_dir()
    assert not app.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="`ditto` gibt es nur auf macOS")
def test_macos_archive_keeps_symlinks_and_carries_the_guide(tmp_path, monkeypatch):
    """`ditto` statt `zip` — und die Kurzanleitung muss mit.

    Ein gewöhnliches `zip` (auch `shutil.make_archive`) löst die Symlinks in
    `Contents/Frameworks` auf und zerstört damit die Code-Signatur; die
    entpackte Anwendung startet dann gar nicht mehr („is damaged"). Der Test
    prüft deshalb den Symlink **im Archiv**, nicht bloß, dass eine Datei entsteht.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.setattr(build_app, "DIST_DIR", dist)
    folder = build_app.macos_delivery_folder(_fake_app(dist))

    archive = build_app.package_macos(folder)

    assert (folder / "LIESMICH.txt").is_file()
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert f"{folder.name}/LIESMICH.txt" in names
        assert (
            f"{folder.name}/{build_app.APP_NAME}.app/Contents/MacOS/{build_app.APP_NAME}" in names
        )

        link = f"{folder.name}/{build_app.APP_NAME}.app/Contents/Frameworks/Tk.framework"
        assert stat.S_ISLNK(bundle.getinfo(link).external_attr >> 16)
