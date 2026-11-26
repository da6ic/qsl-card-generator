"""Hauptfenster, Teil „Karten": Karten bauen, Drucken-Markierung, Most Wanted.

Ein Baustein von `App` (siehe `gui/app.py`, Bewertung 3.1). Die Regeln selbst
stehen in `cards.builder` und `controllers.mostwanted_flow`; hier wird nur
angestoßen und angezeigt.
"""

from __future__ import annotations

from qslcards import mostwanted
from qslcards.cards.builder import build_cards, is_printable, mostwanted_rank
from qslcards.lookup import active_via_priority


class CardsMixin:
    # ------------------------------------------------------------ Regeln
    def _active_via_priority(self) -> list[str]:
        """Die aktiven Wege (über der Trennlinie) in Prioritätsreihenfolge."""
        priority, cut = self.filter_section.get_priority()
        return active_via_priority(priority, cut)

    def _mostwanted_filter(self) -> mostwanted.MostWantedFilter:
        """Die aktuelle Most-Wanted-Regel (auch wenn der Filter aus ist)."""
        return self._mostwanted.rule(
            self.mostwanted_section.top_value(), self.mostwanted_section.category_code()
        )

    def _included_default(self, card) -> bool:
        """Drucken-Voreinstellung: ein aktiver Weg passt **und**, falls der
        Most-Wanted-Filter an ist, das Gebiet liegt unter den ersten N."""
        rule = self._mostwanted_filter() if self.mostwanted_section.enabled.get() else None
        return is_printable(card, self._active_via_priority(), rule)

    def _mostwanted_rank(self):
        """Rang je Karte für die Spalte „MW" — oder None, solange es keine Liste
        gibt (dann bleibt die Spalte leer statt überall „–" zu zeigen)."""
        if self.mostwanted_list is None:
            return None
        rule = self._mostwanted_filter()
        return lambda card: mostwanted_rank(card, rule)

    # ------------------------------------------------------------ Karten
    def _visible_qsos(self) -> list:
        """Offene QSOs plus — falls eingeblendet — die schon gesendeten."""
        return self.session.visible_qsos(self.preview.show_sent.get())

    def _update_show_sent(self) -> None:
        """Beschriftung/Zustand von „Schon gesendete anzeigen" nachziehen."""
        count = len(self.sent_qsos)
        self.preview.show_sent_check.configure(
            text=f"Schon gesendete anzeigen ({count})" if count else "Schon gesendete anzeigen",
            state="normal" if count else "disabled",
        )
        if not count and self.preview.show_sent.get():
            self.preview.show_sent.set(False)

    def _on_show_sent_toggle(self, *_args) -> None:
        """Gesendete ein-/ausgeblendet: Karten neu bauen; fehlende Lookups holen."""
        if self.preview.show_sent.get() and self.session.missing_lookups(show_sent=True):
            # Alle offenen mitgeben: ein laufender Lookup wird durch diesen
            # ersetzt, der Cache macht die schon geholten sofort wieder gültig.
            self._start_lookups(self._lookup_calls_needed())
            return
        self._rebuild_cards()

    def _build_all_cards(self) -> list:
        """Karten der offenen QSOs plus (eingeblendet) eigene Karten der schon
        gesendeten — nie gemischt, damit eine Nachdruck-Karte nicht neue QSOs
        mitnimmt und umgekehrt."""
        config = self._gather_config()
        resolve = self._mostwanted.resolve_dxcc()
        cards = build_cards(self.qsos, config, self.lookups, resolve_dxcc=resolve)
        if self.preview.show_sent.get() and self.sent_qsos:
            again = build_cards(self.sent_qsos, config, self.lookups, resolve_dxcc=resolve)
            for card in again:
                card.already_sent = True
            cards += again
        return cards

    def _rebuild_cards(self) -> None:
        if not self.qsos and not (self.sent_qsos and self.preview.show_sent.get()):
            self.preview.set_cards([])
            return
        self.preview.set_cards(
            self._build_all_cards(),
            included=self._included_default,
            pending=self._lookup_running,
            groupable=self.mode_section.card_mode.get() == "per_station",
            active_priority=self._active_via_priority(),
            rank=self._mostwanted_rank(),
        )

    def _apply_filter(self) -> None:
        """Priorität oder Most-Wanted-Filter geändert: nur die Drucken-Markierung
        und die Anzeige neu setzen (kein Rebuild)."""
        self.preview.apply_print_filter(
            self._active_via_priority(), self._included_default, self._mostwanted_rank()
        )

    def _on_priority_move(self, direction: str) -> None:
        """▲/▼ in der Prioritätsliste: verschieben, dann Auto-Save + Filter neu.

        Die Listbox hat keine tk.Variable, daher wird der Auto-Save hier manuell
        angestoßen (wie bei den beobachteten Variablen)."""
        section = self.filter_section
        moved = section.move_up() if direction == "up" else section.move_down()
        if not moved:
            return
        self._apply_filter()
        self._on_var_change()

    def _on_remarks_commit(self, _event=None) -> None:
        """Globaler Remarks-Text bestätigt (Fokusverlust/Enter): Karten neu bauen,
        aber nur wenn sich der Text wirklich geändert hat (spart Rebuilds und
        erhält per-Karte-Überschreibungen bei unverändertem Text).

        Gibt es manuell geänderte Bemerkungen, fragt ein Dialog, ob diese vom neuen
        globalen Text überschrieben werden sollen. Bei „Nicht überschreiben" werden
        sie nach dem Rebuild wiederhergestellt (nur die manuellen Karten sind
        geschützt; alle übrigen übernehmen den neuen/geleerten globalen Text).
        """
        if self._remarks_dialog_open:
            return  # Re-Entrancy: Dialog hat den Fokus gestohlen
        value = self.remarks_section.remarks.get()
        if value == self._last_remarks_built:
            return

        keep: list = []
        manual = self.preview.manual_remark_cards()
        if manual:
            self._remarks_dialog_open = True
            try:
                overwrite = self._ask_overwrite_remarks(self.remarks_section.frame)
            finally:
                self._remarks_dialog_open = False
            if not overwrite:
                keep = manual

        self._last_remarks_built = value
        self._rebuild_cards()
        self.preview.reapply_manual_remarks(keep)

    def _on_cell_edited(self, iid: str, card, column: str) -> None:
        """Nach einer Via-Bearbeitung die Drucken-Markierung der Zeile nachziehen
        (manuell erzwungener Weg -> drucken, sofern der Most-Wanted-Filter die
        Karte nicht ausschließt). Route-Edits ändern nur den Kartentext."""
        if column == "via":
            self.preview.set_row_included(iid, self._included_default(card))

    # ------------------------------------------------------- Most Wanted
    def _init_mostwanted(self) -> None:
        """Beim Start: gespeicherte Liste und cty.dat lesen (lokal, ohne Netz)
        und — wenn der Filter an ist und etwas fehlt oder veraltet ist — neu
        abrufen."""
        self._mostwanted.load_local()
        self._show_mostwanted_status()
        self._ensure_mostwanted()

    def _on_mostwanted_toggle(self, *_args) -> None:
        """Filter ein-/ausgeschaltet: beim Einschalten die Liste bei Bedarf holen
        (auch der Weg, einen gescheiterten Abruf zu wiederholen)."""
        if self._suppress_save:
            return
        self._ensure_mostwanted()
        self._on_mostwanted_change()

    def _on_mostwanted_change(self, *_args) -> None:
        """Top/Kategorie geändert: Statuszeile und Drucken-Markierung neu.

        Beim programmatischen Setzen (Config laden) passiert hier nichts — der
        Aufrufer zieht danach selbst nach (`_init_mostwanted`/`_reload_from_file`).
        """
        if self._suppress_save:
            return
        self._show_mostwanted_status()
        self._apply_filter()

    def _ensure_mostwanted(self) -> None:
        """Ruft GDXF-Liste und cty.dat im Hintergrund ab, falls nötig. Während
        des Abrufs ist „PDF erzeugen" gesperrt. Nur das Einschalten ruft ab,
        Top/Kategorie nie (sonst nach einem Fehlschlag ein Abruf je Tastendruck)."""
        started = self._mostwanted.ensure(
            self.mostwanted_section.enabled.get(), self._mostwanted_done
        )
        if started:
            self._show_mostwanted_status()
            self._update_generate_state()

    def _mostwanted_done(self, cty_changed: bool) -> None:
        self._update_generate_state()
        self._show_mostwanted_status()
        if cty_changed:
            # Neue cty.dat: Gebiete können sich geändert haben (neue
            # DXpeditions-Rufzeichen). Kommt höchstens alle 14 Tage vor.
            self._rebuild_cards()
        else:
            self._apply_filter()

    def _show_mostwanted_status(self) -> None:
        text, error = self._mostwanted.status()
        self.mostwanted_section.set_status(text, error=error)
