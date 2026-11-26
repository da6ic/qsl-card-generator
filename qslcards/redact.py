"""Zugangsdaten aus Meldungen entfernen, bevor sie geloggt oder angezeigt werden.

HamQTH und QRZ verlangen Benutzer und Passwort **in der URL**
(`xml.php?u=…&p=…`, `?username=…;password=…`). `requests` hängt diese URL an
fast jede Fehlermeldung an („Max retries exceeded with url: …", „401 Client
Error … for url: …"). Ohne Bereinigung stünde das Passwort im Klartext in der
Protokolldatei der gebündelten App.

Zwei Ebenen:

* `redact(text, *secrets)` — für gezielte Aufrufe in den Clients: maskiert die
  bekannten Geheimnisse (roh und URL-kodiert) **und** alle Parameter, die nach
  Passwort/Token aussehen.
* `RedactingFilter` — ein Logging-Filter als Sicherheitsnetz für alles, was
  doch durchrutscht (hängt an jedem Handler, den `main` einrichtet).
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote, quote_plus

MASK = "***"

# Query-Parameter, deren Wert nie in ein Protokoll gehört. `p` ist HamQTH,
# `password` QRZ; `s`/`id` sind Sitzungsschlüssel (kurzlebig, aber gleichwertig
# mit einer Anmeldung, solange sie gelten).
_PARAM_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(p|pass|passwd|password|s|id|key|token|api_key)=([^&;\s'\"<>)]+)"
)
# Wavelog-Token (`wl2_…`) und Bearer-Header, falls sie je in einer Meldung landen.
_TOKEN_RE = re.compile(r"(?i)\b(bearer\s+)?wl2_[A-Za-z0-9_\-]+")
_BEARER_RE = re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?bearer\s+)[^\s'\"]+")


def redact(text: object, *secrets: str | None) -> str:
    """`text` als String, mit allen Zugangsdaten durch `***` ersetzt."""
    out = str(text)
    for secret in secrets:
        if not secret:
            continue
        # Längste Form zuerst, damit kein Teilstück stehen bleibt.
        for form in sorted(
            {secret, quote_plus(secret), quote(secret, safe="")}, key=len, reverse=True
        ):
            out = out.replace(form, MASK)
    out = _PARAM_RE.sub(lambda m: f"{m.group(1)}={MASK}", out)
    out = _BEARER_RE.sub(lambda m: f"{m.group(1)}{MASK}", out)
    out = _TOKEN_RE.sub(lambda m: f"{m.group(1) or ''}{MASK}", out)
    return out


def describe_error(exc: BaseException, *secrets: str | None) -> str:
    """Kurze, bereinigte Beschreibung einer Ausnahme fürs Protokoll."""
    message = redact(exc, *secrets)
    name = type(exc).__name__
    return f"{name}: {message}" if message else name


class RedactingFilter(logging.Filter):
    """Bereinigt jede Protokollzeile, bevor ein Handler sie schreibt.

    Der Filter formatiert die Meldung einmal selbst (`getMessage()`), maskiert
    sie und legt sie ohne Argumente zurück in den Record. Ausnahmetexte
    (`exc_info`) werden ebenfalls bereinigt.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # kaputte %-Argumente: lieber unverändert durchlassen
            return True
        record.msg = redact(message)
        record.args = None
        if record.exc_info and record.exc_info[1] is not None:
            # Formatter cacht den Text in exc_text; vorab bereinigt erzeugen.
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
        return True
