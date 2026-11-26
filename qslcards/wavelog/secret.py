"""API-Key im Schlüsselbund des Betriebssystems ablegen (optional).

Windows: Anmeldeinformationsverwaltung, macOS: Schlüsselbund, Linux: Secret
Service. Dafür wird das Paket `keyring` gebraucht. Fehlt es oder hat das System
keinen Schlüsselbund, wird der Key einfach nicht gespeichert — nie im Klartext
in die config.yaml.
"""

from __future__ import annotations

SERVICE = "QSL-Karten-Generator Wavelog"


def _keyring():
    try:
        import keyring  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 - optional
        return None
    return keyring


def available() -> bool:
    kr = _keyring()
    if kr is None:
        return False
    try:
        backend = kr.get_keyring()
    except Exception:  # noqa: BLE001
        return False
    # Der „fail"-Backend heißt so, wenn es keinen echten Schlüsselbund gibt.
    return "fail" not in type(backend).__module__.lower()


def load_key(url: str) -> str:
    kr = _keyring()
    if kr is None or not url:
        return ""
    try:
        return kr.get_password(SERVICE, url.strip()) or ""
    except Exception:  # noqa: BLE001
        return ""


def save_key(url: str, key: str) -> bool:
    kr = _keyring()
    if kr is None or not url or not key:
        return False
    try:
        kr.set_password(SERVICE, url.strip(), key)
        return True
    except Exception:  # noqa: BLE001
        return False


def delete_key(url: str) -> None:
    kr = _keyring()
    if kr is None or not url:
        return
    try:
        kr.delete_password(SERVICE, url.strip())
    except Exception:  # noqa: BLE001
        pass
