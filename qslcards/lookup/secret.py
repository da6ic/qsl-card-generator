"""QRZ-/HamQTH-Zugangsdaten im Schlüsselbund ablegen (optional, Bewertung 2.3).

Bis 0.3 galt: Zugangsdaten nur zur Laufzeit, bei jedem Start neu eintippen
(CLAUDE.md „Zugangsdaten nur zur Laufzeit"). Das bleibt der **Standard**. Wer
mag, setzt in Schritt 3 „Im Schlüsselbund merken" — dann liegen Benutzer und
Passwort im Schlüsselbund des Betriebssystems, genau wie der Wavelog-Key.
In der config.yaml steht weiterhin nur der Schalter, nie die Daten.

Je Anbieter ein Eintrag (Dienst `SERVICE`, Konto `qrz`/`hamqth`), Wert ist
JSON `{"user": …, "pass": …}`.
"""

from __future__ import annotations

import json

from qslcards.wavelog.secret import _keyring, available

SERVICE = "QSL-Karten-Generator Lookup"
PROVIDERS = ("qrz", "hamqth")

__all__ = ["SERVICE", "PROVIDERS", "available", "load", "save", "delete"]


def load(provider: str) -> tuple[str, str]:
    """(Benutzer, Passwort) oder ("", "")."""
    kr = _keyring()
    if kr is None:
        return "", ""
    try:
        raw = kr.get_password(SERVICE, provider)
        data = json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001 - kaputter Eintrag/kein Backend: wie leer
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    return str(data.get("user") or ""), str(data.get("pass") or "")


def save(provider: str, user: str, password: str) -> bool:
    """Speichert; leere Angaben löschen den Eintrag stattdessen."""
    kr = _keyring()
    if kr is None:
        return False
    if not user.strip() or not password:
        delete(provider)
        return True
    try:
        kr.set_password(SERVICE, provider, json.dumps({"user": user.strip(), "pass": password}))
        return True
    except Exception:  # noqa: BLE001
        return False


def delete(provider: str) -> None:
    kr = _keyring()
    if kr is None:
        return
    try:
        kr.delete_password(SERVICE, provider)
    except Exception:  # noqa: BLE001
        pass
