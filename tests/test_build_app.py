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
import tarfile
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


def test_linux_tar_carries_the_short_guide_and_the_install_helpers(tmp_path, monkeypatch):
    """Auch das Linux-Archiv trägt die Kurzanleitung — und **nicht** die README.

    `packaging/linux/README.md` beschreibt, wie man das Programm baut
    (Container, PyInstaller, glibc). Sie lag früher im Archiv und war für den
    Anwender, der es gerade heruntergeladen hat, schlicht die falsche Datei.

    `install.sh` und die `.desktop`-Datei müssen dagegen mit: ohne sie bräuchte
    er für die Einrichtung zusätzlich das Repository.
    """
    dist = tmp_path / "dist"
    folder = dist / build_app.APP_NAME
    folder.mkdir(parents=True)
    (folder / build_app.APP_NAME).write_bytes(b"")
    monkeypatch.setattr(build_app, "DIST_DIR", dist)

    archive = build_app.package_tar(folder)

    assert (folder / "LIESMICH.txt").is_file()
    with tarfile.open(archive) as bundle:
        names = bundle.getnames()
    assert f"{build_app.APP_NAME}/LIESMICH.txt" in names
    assert f"{build_app.APP_NAME}/install.sh" in names
    assert f"{build_app.APP_NAME}/qsl-karten-generator.desktop" in names
    assert f"{build_app.APP_NAME}/README.md" not in names


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


# --- macOS-Mindestversion -------------------------------------------------
#
# Der zweite Fall derselben Sorte wie oben: etwas, das beim Selbsttest **nie**
# auffällt. PyInstaller bündelt die Bibliotheken des bauenden Interpreters, und
# die tragen dessen Deployment-Target. Homebrew baut immer gegen das laufende
# System — auf einem Mac mit macOS 26 entsteht damit ein Bündel, das auf
# macOS 15 nicht startet (dyld lehnt die dylibs ab). Die `Info.plist` behauptete
# vorher fest „11.0": Launch Services ließ das Programm also los, und es starb
# erst beim Nachladen. Auf dem Baurechner selbst sieht man davon nichts.


@pytest.fixture
def on_macos(monkeypatch):
    monkeypatch.setattr(build_app.sys, "platform", "darwin")


def _target(monkeypatch, value):
    monkeypatch.setattr(build_app.sysconfig, "get_config_var", lambda name: value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("26", (26, 0)),  # so meldet es Homebrew auf macOS 26
        ("11.0", (11, 0)),
        ("10.13", (10, 13)),  # der Installer von python.org
        ("", None),
        (None, None),
        ("Unsinn", None),
    ],
)
def test_deployment_target_is_read_from_the_interpreter(on_macos, monkeypatch, value, expected):
    _target(monkeypatch, value)
    assert build_app.macos_deployment_target() == expected


def test_no_deployment_target_outside_macos(monkeypatch):
    monkeypatch.setattr(build_app.sys, "platform", "linux")
    assert build_app.macos_deployment_target() is None


def test_plist_minimum_follows_the_interpreter(on_macos, monkeypatch):
    """Die `Info.plist` sagt die Wahrheit statt einer Wunschzahl."""
    _target(monkeypatch, "26")
    assert build_app.macos_minimum_system_version() == "26.0"


def test_plist_minimum_falls_back_to_the_documented_floor(on_macos, monkeypatch):
    """Lässt sich das Ziel nicht ermitteln, gilt, was die Anleitung zusagt."""
    _target(monkeypatch, None)
    floor = build_app.MACOS_SUPPORTED_FLOOR
    assert build_app.macos_minimum_system_version() == f"{floor[0]}.{floor[1]}"


def test_a_too_new_deployment_target_is_reported(on_macos, monkeypatch):
    _target(monkeypatch, "26")
    notes = build_app.check_warnings()
    assert len(notes) == 1
    assert "26.0" in notes[0]
    # Die Meldung muss den Ausweg nennen, sonst hilft sie niemandem.
    assert "python.org" in notes[0]


def test_an_old_deployment_target_is_silent(on_macos, monkeypatch):
    _target(monkeypatch, "11.0")
    assert build_app.check_warnings() == []


def test_the_warning_does_not_block_the_build(on_macos, sane, monkeypatch):
    """Für wen das Ergebnis taugt, entscheidet der Bauende — nicht das Skript."""
    _target(monkeypatch, "26")
    assert build_app.check_prerequisites() == []


def test_macos_guide_carries_the_real_system_requirement(tmp_path, monkeypatch, on_macos):
    """Die Kurzanleitung im Archiv muss die **echte** Voraussetzung nennen.

    Sie hängt am bauenden Interpreter und kann deshalb nicht im Quelltext der
    Anleitung stehen. Ohne das Einsetzen läse der Empfänger eine Datei, die
    Gatekeeper-Schritte für „macOS 14 und älter" beschreibt, während das
    Programm dort gar nicht erst startet.
    """
    _target(monkeypatch, "26")
    folder = tmp_path / "Auslieferung"
    folder.mkdir()

    written = build_app.write_macos_guide(folder)

    assert written is not None
    text = written.read_text(encoding="utf-8")
    assert build_app.MACOS_MINIMUM_PLACEHOLDER not in text
    assert "macOS 26.0 oder neuer" in text


def test_the_guide_template_still_carries_the_placeholder():
    """Sonst schreibt das Verpacken still nichts hinein."""
    guide = build_app.ROOT / "packaging" / "macos" / "LIESMICH.txt"
    assert build_app.MACOS_MINIMUM_PLACEHOLDER in guide.read_text(encoding="utf-8")


def test_arm64_never_claims_a_macos_older_than_big_sur(on_macos, monkeypatch):
    """Apple Silicon gibt es erst ab macOS 11 — ein arm64-Bündel auch.

    Der universal2-Installer von python.org meldet `10.15` (das gilt für die
    x86_64-Hälfte), die arm64-Hälfte trägt aber `minos 11.0`. Ohne die
    Untergrenze stünde in der Info.plist wieder eine Zahl, welche die
    mitgelieferten Bibliotheken nicht halten.
    """
    _target(monkeypatch, "10.15")
    monkeypatch.setattr(build_app.platform, "machine", lambda: "arm64")
    assert build_app.macos_minimum_system_version() == "11.0"


def test_the_floor_never_lowers_a_higher_target(on_macos, monkeypatch):
    _target(monkeypatch, "26")
    monkeypatch.setattr(build_app.platform, "machine", lambda: "arm64")
    assert build_app.macos_minimum_system_version() == "26.0"


def test_intel_keeps_the_interpreters_target(on_macos, monkeypatch):
    """Für x86_64 gibt es keine solche Untergrenze — dort gilt 10.15 wirklich."""
    _target(monkeypatch, "10.15")
    monkeypatch.setattr(build_app.platform, "machine", lambda: "x86_64")
    assert build_app.macos_minimum_system_version() == "10.15"
