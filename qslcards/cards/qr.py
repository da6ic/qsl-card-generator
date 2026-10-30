"""Text des DARC-QR-Codes einer Karte.

Das Format folgt DM2PF/QSL_QR_Label (https://github.com/DM2PF/QSL_QR_Label),
das nach eigener Angabe die QR-Spezifikation der DARC-QSL-Vermittlung umsetzt.
Nachgebaut, nicht übernommen (das Repository hat keine Lizenz). Aufbau:

    From: DL1ABC Via: DL9MGR To: DK2XYZ
    Date: 18.10.26 Time: 14:05 Band: 20m Mode: SSB RST: 59 QSL: PSE
    …je QSO eine Zeile

`Via:` entfällt ohne Manager. `QSL:` kommt aus der globalen PSE/TNX-Markierung
(`TNX` bzw. `PSE`, sonst `-|-`). Das Band wird aus der Frequenz der Kartenzeile
bestimmt; liegt sie in keinem Amateurfunkband, bleibt das Feld leer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Card

# (untere Kante, obere Kante in MHz, ADIF-Bandname)
_BANDS: tuple[tuple[float, float, str], ...] = (
    (0.1357, 0.1378, "2190m"),
    (0.472, 0.479, "630m"),
    (1.8, 2.0, "160m"),
    (3.5, 4.0, "80m"),
    (5.06, 5.45, "60m"),
    (7.0, 7.3, "40m"),
    (10.1, 10.15, "30m"),
    (14.0, 14.35, "20m"),
    (18.068, 18.168, "17m"),
    (21.0, 21.45, "15m"),
    (24.89, 24.99, "12m"),
    (28.0, 29.7, "10m"),
    (50.0, 54.0, "6m"),
    (70.0, 71.0, "4m"),
    (144.0, 148.0, "2m"),
    (430.0, 440.0, "70cm"),
    (1240.0, 1300.0, "23cm"),
)

_QSL_TEXTS = {"tnx": "TNX", "pse": "PSE"}


def band_of(freq_mhz: str | None) -> str:
    """Bandname (`"20m"`) zu einer Frequenz in MHz; leer, wenn unbekannt."""
    try:
        freq = float((freq_mhz or "").replace(",", "."))
    except ValueError:
        return ""
    return next((band for low, high, band in _BANDS if low <= freq <= high), "")


def qr_text(card: Card, own_call: str) -> str:
    """Der komplette QR-Text der Karte (eine Kopfzeile, dann je QSO eine Zeile)."""
    head = f"From: {own_call.strip().upper()} "
    if card.via_text:
        head += f"Via: {card.via_text} "
    head += f"To: {card.recipient_call}"
    qsl = _QSL_TEXTS.get(card.qsl_mark, "-|-")
    lines = [head]
    for row in card.rows:
        lines.append(
            f"Date: {row.date_d}.{row.date_m}.{row.date_y[-2:]} Time: {row.utc} "
            f"Band: {band_of(row.freq_mhz)} Mode: {row.mode} "
            f"RST: {(row.rst_sent or '').strip()} QSL: {qsl}"
        )
    return "\n".join(lines)
