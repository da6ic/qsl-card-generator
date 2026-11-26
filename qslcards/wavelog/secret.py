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


def account(url: str) -> str:
    """Schlüssel des Eintrags: die normalisierte API-Adresse.

    So sind „log.example.com" und „https://log.example.com/" derselbe Eintrag
    (Bewertung 2.1). Unbrauchbare Eingaben bleiben, wie sie sind.
    """
    from qslcards.wavelog.client import WavelogError, normalize_base_url

    try:
        return normalize_base_url(url)
    except WavelogError:
        return (url or "").strip()


def load_key(url: str) -> str:
    kr = _keyring()
    if kr is None or not (url or "").strip():
        return ""
    # Normalisiert zuerst; danach der alte, wie getippt gespeicherte Eintrag
    # (vor 0.4.0), damit ein gemerkter Key nach dem Update nicht verschwindet.
    for name in dict.fromkeys((account(url), url.strip())):
        try:
            key = kr.get_password(SERVICE, name)
        except Exception:  # noqa: BLE001
            key = None
        if key:
            return key
    return ""


def save_key(url: str, key: str) -> bool:
    kr = _keyring()
    if kr is None or not (url or "").strip() or not key:
        return False
    try:
        kr.set_password(SERVICE, account(url), key)
        return True
    except Exception:  # noqa: BLE001
        return False


def delete_key(url: str) -> None:
    kr = _keyring()
    if kr is None or not (url or "").strip():
        return
    for name in dict.fromkeys((account(url), url.strip())):
        try:
            kr.delete_password(SERVICE, name)
        except Exception:  # noqa: BLE001
            pass
