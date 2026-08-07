"""Pfad-Auflösung (`qslcards/paths.py`).

Die Tests hier halten das fest, was beim Bündeln still schiefgeht und sich
hinterher nur mit einer fertigen `.exe` in der Hand nachweisen ließe: wo Config
und Cache landen, wann der Portable-Modus greift und dass ein Kindprozess nicht
die Bibliotheken der Anwendung erbt.

„Gebündelt" wird dabei simuliert (`sys.frozen`, `sys.executable`, `sys._MEIPASS`)
— genau die drei Dinge, an denen PyInstaller sich erkennen lässt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from qslcards import paths

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    """Simuliert eine gebündelte Anwendung und liefert deren Programmordner."""
    program = tmp_path / "programm"
    program.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(program / "QSL-Karten-Generator"))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "_MEI123"), raising=False)
    return program


# ------------------------------------------------------------------- Quelle
def test_source_mode_keeps_everything_in_the_project_folder():
    """Der Entwickler-Workflow darf sich durch das Bündeln nicht ändern."""
    assert not paths.is_frozen()
    assert paths.program_dir() == PROJECT_ROOT
    assert paths.config_path() == PROJECT_ROOT / "config.yaml"
    assert paths.cache_path() == PROJECT_ROOT / "lookup_cache.json"
    assert paths.resource_dir() == PROJECT_ROOT


def test_source_mode_ignores_the_working_directory(monkeypatch, tmp_path):
    """Aus einem fremden Ordner gestartet zeigt die Config trotzdem ins Projekt.

    Vorher war `"config.yaml"` ein relativer Pfad — das Programm hätte in
    `tmp_path` gesucht und dort eine zweite, leere Config angelegt.
    """
    monkeypatch.chdir(tmp_path)
    assert paths.config_path() == PROJECT_ROOT / "config.yaml"


def test_shipped_resources_exist_where_the_code_looks_for_them():
    assert paths.resource_path("qslcards", "assets", "fonts", "DejaVuSans.ttf").is_file()
    assert paths.resource_path("qslcards", "assets", "icons", "app_icon.ico").is_file()
    assert paths.resource_path("handbuch.md").is_file()
    assert paths.example_config_path().is_file()


# ------------------------------------------------------------------ Bündel
def test_frozen_resources_come_from_meipass(frozen, tmp_path):
    """Mitgelieferte Dateien liegen im Entpackordner, nicht neben der Binary."""
    assert paths.resource_dir() == tmp_path / "_MEI123"
    assert paths.resource_path("handbuch.md") == tmp_path / "_MEI123" / "handbuch.md"


def test_frozen_without_local_config_uses_the_user_folder(frozen):
    """Ohne Config daneben gehören Config, Cache und Protokoll ins Benutzerprofil.

    Der Programmordner ist bei einer Installation nicht beschreibbar
    (`Program Files`, `/usr/bin`), und in der Config stehen Klartext-Passwörter.
    """
    assert not paths.is_portable()
    assert paths.data_dir() == paths.user_data_dir()
    assert paths.config_path().parent == paths.user_data_dir()
    assert paths.log_path().parent == paths.user_data_dir()


def test_frozen_with_local_config_switches_to_portable(frozen):
    """Liegt eine `config.yaml` daneben, bleibt alles im Programmordner."""
    (frozen / "config.yaml").write_text("sender: {}\n", encoding="utf-8")
    assert paths.is_portable()
    assert paths.data_dir() == frozen
    assert paths.config_path() == frozen / "config.yaml"


def test_config_and_cache_never_drift_apart(frozen):
    """Ein Cache neben einer fremden Config gehörte zu einem anderen Konto."""
    assert paths.cache_path().parent == paths.config_path().parent
    (frozen / "config.yaml").write_text("sender: {}\n", encoding="utf-8")
    assert paths.cache_path().parent == paths.config_path().parent


def test_macos_app_bundle_looks_next_to_the_app(monkeypatch, tmp_path):
    """Auf macOS steckt die Binary drei Ebenen tief in der `.app`.

    Für den Anwender ist „neben dem Programm" der Ordner mit der `.app` darin —
    nicht `Contents/MacOS`, das er im Finder gar nicht zu sehen bekommt.
    """
    exe = tmp_path / "QSL-Karten-Generator.app" / "Contents" / "MacOS" / "QSL-Karten-Generator"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert paths.program_dir() == tmp_path


def test_ensure_data_dir_creates_the_folder(frozen, monkeypatch, tmp_path):
    """Ohne den Ordner scheitert der erste Auto-Save — `open(..., "w")` legt
    kein Verzeichnis an."""
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path / "benutzer" / "tiefer")

    created = paths.ensure_data_dir()

    assert created.is_dir()
    assert created == tmp_path / "benutzer" / "tiefer"


def test_ensure_data_dir_touches_no_existing_file(frozen, monkeypatch, tmp_path):
    """Es wird nichts geschrieben — die `config.yaml` legt erst der Auto-Save an."""
    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path / "benutzer")
    (tmp_path / "benutzer").mkdir()
    config = tmp_path / "benutzer" / paths.CONFIG_NAME
    config.write_text("sender:\n  callsign: DL1ABC\n", encoding="utf-8")

    paths.ensure_data_dir()

    assert "DL1ABC" in config.read_text(encoding="utf-8")


def test_ensure_data_dir_survives_a_read_only_location(frozen, monkeypatch, tmp_path):
    """Kein Start scheitert daran, dass der Datenordner nicht anlegbar ist."""
    blocker = tmp_path / "keine-datei"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "user_data_dir", lambda: blocker / "unmoeglich")
    paths.ensure_data_dir()  # darf nicht werfen


# ------------------------------------------------------------- Kindprozesse
def test_subprocess_env_leaves_the_source_environment_alone(monkeypatch):
    """Ein selbst gesetztes LD_LIBRARY_PATH gehört dem Entwickler."""
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/eigenes")
    assert paths.subprocess_env()["LD_LIBRARY_PATH"] == "/opt/eigenes"


def test_subprocess_env_restores_the_original_library_path(frozen, monkeypatch):
    """PyInstaller sichert den Originalwert unter `..._ORIG` — der zählt.

    Sonst lädt ein geerbtes `xdg-open` die gebündelten Bibliotheken und stirbt
    mit „symbol lookup error".
    """
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI123")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib64")

    env = paths.subprocess_env()

    assert env["LD_LIBRARY_PATH"] == "/usr/lib64"
    assert "LD_LIBRARY_PATH_ORIG" not in env


def test_subprocess_env_drops_the_library_path_without_an_original(frozen, monkeypatch):
    """War vorher nichts gesetzt, muss der Eintrag ganz verschwinden."""
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/tmp/_MEI123")
    monkeypatch.delenv("DYLD_LIBRARY_PATH_ORIG", raising=False)
    assert "DYLD_LIBRARY_PATH" not in paths.subprocess_env()


# ------------------------------------------------------------------ Ausgabe
def test_default_output_is_an_absolute_folder():
    """Ein relativer Vorschlag landete beim Doppelklick im Systemordner."""
    target = paths.default_output_dir()
    assert target.is_absolute()
    assert target.is_dir()
