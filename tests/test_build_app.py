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

import sys
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
