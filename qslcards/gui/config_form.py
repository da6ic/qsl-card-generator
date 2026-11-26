"""Eingabefelder <-> AppConfig: die eine Stelle, die beide Seiten kennt.

Vorher in `App._apply_config_to_widgets` / `_gather_config` / `_wire_autosave`
(Bewertung 3.1). Wer ein neues Config-Feld mit Widget einführt, ändert nur
diese Datei: setzen (`apply`), einsammeln (`gather`) und beobachten
(`watched_vars`) stehen hier nebeneinander und laufen nicht auseinander.

**Achtung (CLAUDE.md §11):** `gather` baut die Config aus den Widgets — Felder
ohne Widget (`appearance`, `recent`, `lookup.program_id`, `default_via`,
`page_orientation`, `static_footer`) kommen aus der Basis-Config, sonst löscht
der nächste Auto-Save sie. Die Zugangsdaten-Widgets (Lookup-Passwörter,
Wavelog-Key) haben **kein** Config-Feld und laufen in keiner Richtung mit.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

from qslcards import mostwanted
from qslcards.config import (
    AppConfig,
    AppearanceConfig,
    GenerationConfig,
    LookupConfig,
    MostWantedConfig,
    RecentConfig,
    SenderConfig,
    SourceConfig,
    WavelogConfig,
)
from qslcards.pdf.geometry import clamp_print_margin, normalize_sheet_mode

from .sections import (
    SENDER_FIELDS,
    FilterSection,
    LookupSection,
    ModeSection,
    MostWantedSection,
    OutputSection,
    PrintModeSection,
    RemarksSection,
    SenderSection,
    SourceSection,
    WavelogMarkSection,
    WavelogSection,
    parse_mm,
)

# Display <-> Code-Mappings der Dropdowns.
QSL_MARK_TO_CODE = {"Leer lassen": "none", "PSE QSL": "pse", "TNX QSL": "tnx"}
QSL_CODE_TO_DISPLAY = {v: k for k, v in QSL_MARK_TO_CODE.items()}
CONFIRM_MARK_TO_CODE = {
    "Leer lassen": "none",
    "Confirming QSO": "qso",
    "Confirming SWL-Report": "swl",
}
CONFIRM_CODE_TO_DISPLAY = {v: k for k, v in CONFIRM_MARK_TO_CODE.items()}


@dataclass
class ConfigForm:
    """Die Abschnitte, deren Felder in der Config stehen."""

    source: SourceSection
    sender: SenderSection
    lookup: LookupSection
    filter: FilterSection
    mode: ModeSection
    remarks: RemarksSection
    mostwanted: MostWantedSection
    printmode: PrintModeSection
    output: OutputSection
    wavelog: WavelogSection
    wavelog_mark: WavelogMarkSection

    # ------------------------------------------------------------ setzen
    def apply(self, config: AppConfig) -> None:
        """Alle Felder auf `config` setzen. Der Aufrufer unterdrückt dabei den
        Auto-Save. Zugangsdaten bleiben unberührt: ein Neuladen der Datei darf
        nicht löschen, was der Nutzer gerade getippt hat."""
        for field, _ in SENDER_FIELDS:
            self.sender.vars[field].set(getattr(config.sender, field))
        self.output.address_export.set(config.lookup.address_export)

        gen = config.generation
        self.filter.set_priority(gen.via_priority, gen.via_cut)
        self.mode.card_mode.set(gen.card_mode)
        pm = self.printmode
        pm.print_mode.set(gen.print_mode)
        pm.sheet_mode.set(normalize_sheet_mode(gen.sheet_mode))
        pm.qr_code.set(bool(gen.qr_code))
        # Druckrand: Umschalter + vier Felder (Feldname in der Section =
        # Config-Feld ohne das „print_"-Präfix).
        pm.advanced.set(gen.print_margin_enabled)
        for name, var in pm.margin_vars.items():
            var.set(f"{clamp_print_margin(getattr(gen, f'print_{name}')):g}")
        pm.update_advanced_visibility()
        self.sender.qsl_mark.set(QSL_CODE_TO_DISPLAY.get(gen.qsl_mark, "Leer lassen"))
        self.sender.confirm_mark.set(CONFIRM_CODE_TO_DISPLAY.get(gen.confirm_mark, "Leer lassen"))
        self.remarks.remarks.set(gen.remarks)

        mw = config.mostwanted
        self.mostwanted.enabled.set(mw.enabled)
        self.mostwanted.top.set(str(mostwanted.clamp_top(mw.top)))
        self.mostwanted.set_category(mw.category)

        kind = config.source.kind
        self.source.kind.set(kind if kind in ("file", "wavelog") else "file")
        wl = config.wavelog
        self.lookup.remember.set(bool(config.lookup.remember))
        self.wavelog.url.set(wl.url)
        self.wavelog.remember_key.set(bool(wl.remember_key))
        self.wavelog.since.set(wl.qso_since)
        self.wavelog.until.set(wl.qso_until)
        self.wavelog_mark.mark_sent.set(bool(wl.mark_sent))

    # ------------------------------------------------------------ einsammeln
    def gather(self, base: AppConfig) -> AppConfig:
        """Config aus den Feldern; was kein Feld hat, kommt aus `base`."""
        sender = SenderConfig(**{f: self.sender.vars[f].get() for f, _ in SENDER_FIELDS})
        lookup = LookupConfig(
            program_id=base.lookup.program_id,
            address_export=self.output.address_export.get(),
            remember=self.lookup.remember.get(),
        )
        via_priority, via_cut = self.filter.get_priority()
        pm = self.printmode
        generation = GenerationConfig(
            card_mode=self.mode.card_mode.get(),
            via_priority=via_priority,
            via_cut=via_cut,
            default_via=base.generation.default_via,
            page_orientation=base.generation.page_orientation,
            print_mode=pm.print_mode.get(),
            sheet_mode=normalize_sheet_mode(pm.sheet_mode.get()),
            print_margin_enabled=pm.advanced.get(),
            **{
                f"print_{name}": clamp_print_margin(parse_mm(var.get()))
                for name, var in pm.margin_vars.items()
            },
            static_footer=base.generation.static_footer,
            remarks=self.remarks.remarks.get(),
            qsl_mark=QSL_MARK_TO_CODE.get(self.sender.qsl_mark.get(), "none"),
            confirm_mark=CONFIRM_MARK_TO_CODE.get(self.sender.confirm_mark.get(), "none"),
            qr_code=pm.qr_code.get(),
        )
        most_wanted = MostWantedConfig(
            enabled=self.mostwanted.enabled.get(),
            top=self.mostwanted.top_value(),
            category=self.mostwanted.category_code(),
        )
        return AppConfig(
            sender=sender,
            lookup=lookup,
            generation=generation,
            mostwanted=most_wanted,
            # Aussehen und „Zuletzt verwendet" haben keine Eingabefelder.
            appearance=AppearanceConfig(theme=base.appearance.theme),
            recent=RecentConfig(logs=list(base.recent.logs), images=list(base.recent.images)),
            source=SourceConfig(kind=self.source.kind.get()),
            wavelog=WavelogConfig(
                url=self.wavelog.url.get().strip(),
                station_id=self.wavelog.selected_station_id() or base.wavelog.station_id,
                remember_key=self.wavelog.remember_key.get(),
                qso_since=self.wavelog.since.get().strip(),
                qso_until=self.wavelog.until.get().strip(),
                mark_sent=self.wavelog_mark.mark_sent.get(),
            ),
        )

    # ------------------------------------------------------------ beobachten
    def watched_vars(self) -> list[tk.Variable]:
        """Alle Variablen, deren Änderung gespeichert wird.

        Fehlen mit Absicht: die Zugangsdaten (ein Tastendruck im Passwortfeld
        darf keinen Schreibvorgang auslösen) und der Wavelog-Key (der geht
        höchstens in den Schlüsselbund). Die Prioritätsliste hat keine
        tk.Variable; ihr Auto-Save läuft über die ▲/▼-Buttons.
        """
        pm = self.printmode
        return [
            *self.sender.vars.values(),
            self.sender.qsl_mark,
            self.sender.confirm_mark,
            self.remarks.remarks,
            self.output.address_export,
            self.mode.card_mode,
            pm.print_mode,
            pm.sheet_mode,
            pm.qr_code,
            pm.advanced,
            *pm.margin_vars.values(),
            self.mostwanted.enabled,
            self.mostwanted.top,
            self.mostwanted.category,
            self.source.kind,
            self.wavelog.url,
            self.wavelog.station,
            self.wavelog.remember_key,
            self.lookup.remember,
            self.wavelog.since,
            self.wavelog.until,
            self.wavelog_mark.mark_sent,
        ]
