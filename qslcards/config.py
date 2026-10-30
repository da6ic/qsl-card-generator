"""Config-Datenmodell und YAML-Persistenz.

Siehe docs/SPECIFICATION.md §3. Fehlende YAML-Felder werden mit den dort
genannten Defaults aufgefüllt, unbekannte Felder ignoriert.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

import yaml


@dataclass
class SenderConfig:
    callsign: str = ""
    name: str = ""
    street: str = ""
    zip: str = ""
    city: str = ""
    country: str = ""
    locator: str = ""
    dok: str = ""
    waz: str = ""
    itu: str = ""
    # Funk-Ausrüstung: erscheint dynamisch auf der Karte, sobald mindestens eins
    # der Felder gefüllt ist — als kleine Tabelle mit den Spaltenköpfen
    # RIG/ANT/PWR. Alle leer -> der Block wird gar nicht gezeichnet.
    receiver: str = ""  # Empfänger/TRX
    antenna: str = ""  # Antenne
    power: str = ""  # Sendeleistung (Watt)


@dataclass
class LookupConfig:
    program_id: str = "qslcards"  # HamQTH verlangt prg-Kennung
    address_export: bool = False  # Adress-/Label-CSV zu den gedruckten Karten
    # Kein `lookup_addresses` mehr: der Lookup läuft automatisch beim Log-Laden,
    # sobald Zugangsdaten eingegeben sind (siehe docs/SPECIFICATION.md §6).
    #
    # Die Zugangsdaten (HamQTH-/QRZ-Benutzer und -Passwort) stehen bewusst NICHT
    # hier: `save` schriebe sie im Klartext in die config.yaml. Sie leben nur zur
    # Laufzeit in `lookup.LookupCredentials` und werden in jeder Sitzung neu
    # eingegeben. `program_id` bleibt die einzige konfigurierte Angabe; die GUI
    # kopiert sie beim Lookup in die Credentials.


@dataclass
class GenerationConfig:
    card_mode: str = "per_qso"  # "per_qso" | "per_station"
    # Zustellwege in Prioritätsreihenfolge (oben = höchste Priorität):
    # B=Büro (inkl. Manager), D=Direkt, Q=eQSL, L=LOTW. `via_cut` ist die
    # Trennlinie: die ersten `via_cut` Wege sind aktiv (werden gedruckt), der
    # Rest steht unter der Linie und wird nicht gedruckt.
    via_priority: list[str] = field(default_factory=lambda: ["B", "D", "Q", "L"])
    via_cut: int = 2  # Default: Büro + Direkt aktiv, eQSL/LOTW unter der Linie
    default_via: str = "B"  # Fallback, wenn der Lookup nichts/"?" liefert
    #   -> nur hier in der Config, kein GUI-Widget. Via kommt sonst aus dem Lookup.
    page_orientation: str = "landscape"  # A6, siehe CARD_LAYOUT.md
    # Wie die PDF(s) erzeugt werden:
    #   "duplex"   -> eine PDF, pro Karte Vorder-/Rückseite abwechselnd (Duplexdruck).
    #   "separate" -> zwei PDFs (alle Vorderseiten, alle Rückseiten) für Drucker
    #                 ohne beidseitigen Druck: erst Vorderseiten drucken, Papier
    #                 umgedreht neu einlegen, dann Rückseiten drucken.
    print_mode: str = "duplex"  # "duplex" | "separate"
    # Bogendruck (quer zum Druckmodus, GUI-Abschnitt 10):
    #   "single" -> eine Karte je PDF-Seite (A6 quer), wie bisher.
    #   "a4_4up" -> vier Karten je PDF-Seite (A4 quer, 2×2) mit gestrichelten
    #               Schnitt-Hilfslinien zwischen den Karten (nur auf den
    #               Rückseiten). Der Druckrand gilt weiterhin **je Karte**.
    sheet_mode: str = "single"  # "single" | "a4_4up"
    # Druckrand („Erweiterte Einstellungen" in GUI-Abschnitt 10): viele Drucker
    # drucken nicht bis zur Blattkante und beschneiden sonst den Inhalt. Ist
    # print_margin_enabled aktiv, wird die Karte proportional so verkleinert,
    # dass diese Ränder (in **mm**, je Kante) frei bleiben; der dabei auf einer
    # Achse übrige Platz fließt ins Layout (siehe pdf/geometry.page_layout).
    # Aus -> unverändert randlos wie bisher. Im Bogenmodus („a4_4up") gelten die
    # Werte je Karte (also je Zelle des 2×2-Rasters), damit jede geschnittene
    # Karte denselben Rand ringsum hat.
    print_margin_enabled: bool = False
    print_margin_top: float = 0.0
    print_margin_bottom: float = 0.0
    print_margin_left: float = 0.0
    print_margin_right: float = 0.0
    static_footer: str = "TNX FR NICE CONTACT, 73"
    remarks: str = ""  # globaler REMARKS-Text (alle Karten); leer -> kein Kasten
    qsl_mark: str = "none"  # "pse" | "tnx" | "none" (global)
    # Die Portabel-Kennung hatte hier bis Version 0.1 ein eigenes Feld samt
    # Dropdown. Sie steht jetzt einfach im Rufzeichen (`F/DL0MT/P`) — ein Feld
    # weniger, und Gastrufzeichen, `/QRP`, `/MM` oder `/4` brauchen keine
    # Sonderbehandlung mehr.
    confirm_mark: str = "none"  # "qso" | "swl" | "none" (global)
    # DARC-QR-Code rechts unten auf der Rückseite (GUI-Abschnitt 10). Der Text
    # folgt dem Format von DM2PF/QSL_QR_Label (siehe `cards/qr.py`). Der Code
    # braucht den Platz unter der Tabelle: an -> höchstens
    # MAX_ROWS_WITH_REMARKS QSO-Zeilen je Karte, wie mit Remarks.
    qr_code: bool = False


@dataclass
class MostWantedConfig:
    """Most-Wanted-Filter (GUI-Abschnitt 7): nur Karten an gesuchte DXCC-Gebiete.

    Die Rangliste ist die der GDXF (https://gdxf.de/mostwanted/, aus Sicht
    Mitteleuropas). Ist der Filter an, wird eine Karte nur gedruckt, wenn ihr
    DXCC-Gebiet unter den ersten `top` Rängen liegt — zusätzlich zur
    Trennlinie der Zustellwege. Ein unbekanntes Gebiet wird dann nicht gedruckt.
    """

    enabled: bool = False
    top: int = 100  # 1..340 (Zahl der aktuellen DXCC-Gebiete)
    # "auto" = Rangliste nach dem Mode des QSOs (CW/Phone/Digital);
    # sonst fest "mixed" | "cw" | "phone" | "digital".
    category: str = "auto"


@dataclass
class AppearanceConfig:
    """Aussehen der Oberfläche (nicht der Karte!).

    `theme`: "system" folgt der Betriebssystem-Einstellung (hell/dunkel),
    "light"/"dark" erzwingen einen Modus. Umschaltbar über Menü „Ansicht".
    """

    theme: str = "system"  # "system" | "light" | "dark"


# Wie viele Einträge die Menüs „Zuletzt verwendet" höchstens führen.
MAX_RECENT = 8


@dataclass
class RecentConfig:
    """Zuletzt geöffnete Dateien für das Menü „Datei" (neueste zuerst)."""

    logs: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)


@dataclass
class AppConfig:
    sender: SenderConfig = field(default_factory=SenderConfig)
    lookup: LookupConfig = field(default_factory=LookupConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    mostwanted: MostWantedConfig = field(default_factory=MostWantedConfig)
    appearance: AppearanceConfig = field(default_factory=AppearanceConfig)
    recent: RecentConfig = field(default_factory=RecentConfig)


def push_recent(entries: list[str], path: str, limit: int = MAX_RECENT) -> list[str]:
    """Setzt `path` an die Spitze der Liste (ohne Duplikate) und kürzt auf `limit`.

    Rein (ohne Seiteneffekt): liefert die neue Liste zurück. Leere Pfade werden
    ignoriert, damit kein Leereintrag ins Menü rutscht.
    """
    path = (path or "").strip()
    if not path:
        return list(entries)
    rest = [p for p in entries if p != path]
    return [path, *rest][:limit]


T = TypeVar("T")


def _from_dict(cls: type[T], data: Any) -> T:
    """Baut eine Dataclass aus einem Dict: unbekannte Felder ignorieren,
    fehlende Felder über die Dataclass-Defaults auffüllen."""
    if not isinstance(data, dict):
        return cls()
    known = {f.name for f in fields(cls)}
    kwargs = {key: value for key, value in data.items() if key in known}
    return cls(**kwargs)


def _recent_from_dict(data: Any) -> RecentConfig:
    """Baut `RecentConfig` defensiv: nur nicht-leere Strings, auf MAX_RECENT gekürzt.

    Die Listen werden von der App geschrieben, können aber von Hand editiert
    worden sein — kaputte Einträge dürfen den Start nicht kippen.
    """

    def clean(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()][
            :MAX_RECENT
        ]

    if not isinstance(data, dict):
        return RecentConfig()
    return RecentConfig(logs=clean(data.get("logs")), images=clean(data.get("images")))


# Erste Zeile jeder geschriebenen Config. Sie steht in `save` und nicht bloß in
# `config.example.yaml`, weil `yaml.safe_dump` die Datei beim Auto-Save komplett
# neu schreibt: ein nur in der Vorlage stehender Hinweis wäre nach der ersten
# Änderung im Programm verschwunden — also genau dann, wenn er noch gilt.
#
# Vier Werte haben deshalb bewusst gar keinen Weg mehr, geändert zu werden:
# `default_via`, `page_orientation`, `static_footer` und `program_id` besitzen
# kein Eingabefeld (siehe `gui/app._gather_config`, das sie aus der geladenen
# Config übernimmt). Sie gelten als Programmkonstanten, die zufällig hier liegen
# — vom Nutzer so entschieden. Wer einen davon bedienbar machen will, braucht ein
# Widget; ihn „einfach in der Datei zu ändern" widerspricht der Zeile darüber.
CONFIG_HEADER = "# Diese Datei verwaltet das Programm selbst — bitte nicht von Hand bearbeiten.\n"


def load(path: str | Path) -> AppConfig:
    """Lädt die YAML-Config und füllt fehlende Felder mit Defaults auf."""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    return AppConfig(
        sender=_from_dict(SenderConfig, data.get("sender")),
        lookup=_from_dict(LookupConfig, data.get("lookup")),
        generation=_from_dict(GenerationConfig, data.get("generation")),
        mostwanted=_from_dict(MostWantedConfig, data.get("mostwanted")),
        appearance=_from_dict(AppearanceConfig, data.get("appearance")),
        recent=_recent_from_dict(data.get("recent")),
    )


def save(config: AppConfig, path: str | Path) -> None:
    """Schreibt die Config als YAML, mit der Warnung als erster Zeile."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(CONFIG_HEADER)
        yaml.safe_dump(
            asdict(config),
            fh,
            allow_unicode=True,
            sort_keys=False,
        )
