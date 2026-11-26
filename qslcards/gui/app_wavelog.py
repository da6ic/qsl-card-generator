"""Hauptfenster, Teil „Wavelog": Stationen und QSOs holen, nach dem Druck markieren.

Ein Baustein von `App` (siehe `gui/app.py`, Bewertung 3.1). Was gilt (Client,
Sicherheitsnetz `wavelog_sent.json`, Warnungen), steht in
`controllers.wavelog_flow`; hier nur Knöpfe, Hinweise und Statuszeile.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from qslcards import wavelog
from qslcards.controllers.session import marks_for_cards
from qslcards.controllers.wavelog_flow import missing_status_warning
from qslcards.wavelog import secret as wavelog_secret
from qslcards.wavelog import sent_store
from qslcards.wavelog.client import insecure_url_warning, validate_date


class WavelogMixin:
    # ------------------------------------------------------------ Client
    def _wavelog_client(self) -> wavelog.WavelogClient:
        """Client für Adresse + Key; derselbe, solange sich beides nicht ändert."""
        return self._wavelog.client(self.wavelog_section.url.get(), self.wavelog_section.key.get())

    def _wavelog_api(self) -> str:
        return self._wavelog.api_url(self.wavelog_section.url.get())

    def _restore_wavelog_key(self) -> None:
        """Beim Start: einen gemerkten API-Key aus dem Schlüsselbund holen."""
        if not self.wavelog_section.remember_key.get():
            return
        key = wavelog_secret.load_key(self.wavelog_section.url.get())
        if key:
            self.wavelog_section.key.set(key)

    def _on_remember_key_toggle(self, *_args) -> None:
        if self._suppress_save:
            return
        url = self.wavelog_section.url.get()
        if self.wavelog_section.remember_key.get():
            wavelog_secret.save_key(url, self.wavelog_section.key.get())
        else:
            wavelog_secret.delete_key(url)

    def _set_wavelog_busy(self, busy: bool) -> None:
        self._wavelog.busy = busy
        section = self.wavelog_section
        section.load_stations_btn.configure(state="disabled" if busy else "normal")
        section.load_qsos_btn.configure(
            state="disabled" if busy or not self._wavelog.stations else "normal"
        )
        self._update_mark_state()

    def _run_wavelog(self, work, done) -> None:
        """`work(client)` im Hintergrund, `done(result, error)` im UI-Thread."""
        try:
            client = self._wavelog_client()
        except wavelog.WavelogError as exc:
            self.status.set(str(exc), "error")
            self.wizard.show_problem(str(exc))
            return
        self._set_wavelog_busy(True)
        self._wavelog.run(client, work, done)

    def _show_wavelog_error(self, error) -> None:
        self.status.set(str(error), "error")
        self.wizard.show_problem(str(error))

    # ------------------------------------------------------------ Stationen
    def _wavelog_load_stations(self) -> None:
        # Token im Klartext über fremdes Netz? Deutlich sagen (2.1), nicht sperren.
        url = self.wavelog_section.url.get()
        self.wavelog_section.set_warning(insecure_url_warning(url) or "")
        self.status.set("Lade Stationen aus Wavelog…", "busy")
        if self.wavelog_section.remember_key.get():
            wavelog_secret.save_key(url, self.wavelog_section.key.get())
        self._run_wavelog(lambda client: client.stations(), self._wavelog_stations_done)

    def _wavelog_stations_done(self, stations, error) -> None:
        self._set_wavelog_busy(False)
        if error is not None:
            self._show_wavelog_error(error)
            return
        self._wavelog.stations = list(stations)
        self.wavelog_section.set_stations(stations, self.base_config.wavelog.station_id)
        self._set_wavelog_busy(False)
        if not stations:
            self.status.set("Wavelog: keine Stationsstandorte gefunden.", "error")
            return
        self.wavelog_section.set_missing(False)
        self.status.set(f"Wavelog: {len(stations)} Station(en) geladen.", "ok")
        self.wizard.show_hint("Station wählen, dann „QSOs laden“.")

    def _selected_wavelog_station(self) -> wavelog.WavelogStation | None:
        return self._wavelog.station(self.wavelog_section.selected_station_id())

    def _on_wavelog_station_selected(self) -> None:
        self.wavelog_section.set_missing(False)
        self._on_var_change()

    # ------------------------------------------------------------ QSOs
    def _wavelog_load_qsos(self) -> None:
        station = self._selected_wavelog_station()
        if station is None:
            self.wavelog_section.set_missing(True)
            self.wizard.show_problem("Bitte eine Station wählen.")
            return
        since = self.wavelog_section.since.get().strip()
        until = self.wavelog_section.until.get().strip()
        bad = [
            label for label, value in (("von", since), ("bis", until)) if not validate_date(value)
        ]
        self.wavelog_section.mark_dates(
            since_bad=not validate_date(since), until_bad=not validate_date(until)
        )
        if bad:
            problem = "Datum „" + "“/„".join(bad) + "“ bitte als JJJJ-MM-TT angeben."
            self.wizard.show_problem(problem)
            self.status.set(problem, "error")
            return
        if since and until and since > until:
            self.wavelog_section.mark_dates(since_bad=True, until_bad=True)
            self.wizard.show_problem("„von“ liegt nach „bis“.")
            return
        self.status.set(f"Lade QSOs von {station.callsign} aus Wavelog…", "busy")

        def progress(done: int, total: int) -> None:
            self.after(0, self.status.set, f"Lade QSOs aus Wavelog… {done}/{total}", "busy")

        self._run_wavelog(
            lambda client: client.qsos(station.id, since=since, until=until, progress_cb=progress),
            lambda qsos, error: self._wavelog_qsos_done(station, qsos, error),
        )

    def _wavelog_qsos_done(self, station, qsos, error) -> None:
        self._set_wavelog_busy(False)
        if error is not None:
            self._show_wavelog_error(error)
            return
        # Schon gesendete Karten nie wieder drucken (Regeln in `prepare_load`).
        plan = self._wavelog.prepare_load(qsos, self.wavelog_section.url.get())
        self.session.load(qsos, "wavelog", plan.is_sent)
        skipped = len(self.sent_qsos)
        self._pending_marks = plan.pending
        self._prefill_sender_from_station(station)
        note = f" ({skipped} schon gesendet, ausgelassen)" if skipped else ""
        self.wavelog_section.count_var.set(f"{len(self.qsos)} QSOs geladen{note}")
        self.status.set_info(f"{len(self.qsos)} QSOs · Wavelog {station.callsign}")
        warnings = list(plan.warnings)
        if not plan.status_known:
            warnings.append(missing_status_warning(plan.marked_count, len(self.qsos)))
        self.wavelog_section.set_warning("\n\n".join(warnings), error=plan.store_broken)
        if warnings:
            self.status.set("Wavelog: QSOs geladen – bitte Hinweis in Schritt 1 beachten.", "error")
        else:
            self.status.set(f"Wavelog: {len(self.qsos)} QSOs geladen{note}.", "ok")
        self.wizard.show_hint("")
        self.wizard.refresh()
        self.lookups = {}
        self._update_show_sent()
        self._update_mark_state()
        self._start_lookups(self._lookup_calls_needed())

    def _prefill_sender_from_station(self, station: wavelog.WavelogStation) -> None:
        """Leere Absenderfelder mit den Daten des Wavelog-Standorts füllen
        (nie überschreiben, was schon dasteht)."""
        for field, value in (
            ("callsign", station.callsign),
            ("locator", station.gridsquare),
            ("waz", station.cq),
            ("itu", station.itu),
        ):
            var = self.sender_section.vars[field]
            if value and not var.get().strip():
                var.set(value)

    # ------------------------------------------------------------ Markieren
    def _marks_for(self, cards) -> list[wavelog.PaperQslMark]:
        """Die Wavelog-QSOs der gedruckten Karten, mit dem Zustellweg."""
        return marks_for_cards(cards, self._active_via_priority())

    def _save_pending_marks(self) -> None:
        """Offene Markierungen in `wavelog_sent.json` sichern (überlebt Neustart)."""
        if self.qsos_source != "wavelog":
            return
        try:
            self._wavelog.save_pending(self.wavelog_section.url.get(), self._pending_marks)
        except (OSError, sent_store.SentStoreError) as exc:
            self.status.set(f"Offene Markierungen nicht gesichert: {exc}", "error")

    def _update_mark_state(self) -> None:
        section = self.wavelog_mark_section
        enabled = bool(self._pending_marks) and not self._wavelog.busy
        section.mark_now_btn.configure(state="normal" if enabled else "disabled")
        if self._pending_marks:
            section.status_var.set(f"{len(self._pending_marks)} QSO(s) warten auf Markierung")

    def _after_generate_wavelog(self) -> None:
        """Nach dem PDF: die QSOs der Karten in Wavelog als gesendet markieren
        (nach Rückfrage — die PDF könnte ja nur ein Probedruck sein)."""
        if self.qsos_source != "wavelog":
            return
        # Zu den noch offenen aus früheren Drucken dazu, und sofort sichern:
        # „erst Probedruck" + Programm schließen verliert sie sonst (2.2).
        self.session.add_pending(self._marks_for(self._generated_cards))
        self._save_pending_marks()
        self._update_mark_state()
        if not self._pending_marks or not self.wavelog_mark_section.mark_sent.get():
            return
        if self._confirm(
            self,
            "In Wavelog markieren",
            f"{len(self._pending_marks)} QSO(s) in Wavelog als „Papier-QSL gesendet“ "
            "markieren?\n\nNur bestätigen, wenn die Karten wirklich verschickt werden.",
            ok_label="Markieren",
        ):
            self._wavelog_mark_pending()

    def _wavelog_mark_pending(self) -> None:
        marks = list(self._pending_marks)
        if not marks:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        self.status.set(f"Markiere {len(marks)} QSO(s) in Wavelog…", "busy")

        def progress(done: int, total: int) -> None:
            self.after(0, self.status.set, f"Markiere in Wavelog… {done}/{total}", "busy")

        self._run_wavelog(
            lambda client: client.mark_many(marks, date=today, progress_cb=progress),
            self._wavelog_mark_done,
        )

    def _wavelog_mark_done(self, result, error) -> None:
        self._set_wavelog_busy(False)
        if error is not None:
            self.status.set(str(error), "error")
            return
        done_ids, errors = result
        done = len(done_ids)
        if done_ids:
            # Merken (Sicherheitsnetz für den nächsten Abruf) und aus der
            # aktuellen Sitzung nehmen: gesendete Karten werden nie neu gedruckt.
            try:
                self._wavelog.record_marked(self.wavelog_section.url.get(), done_ids)
            except (OSError, sent_store.SentStoreError) as exc:
                self.status.set(f"Liste der gesendeten QSOs nicht speicherbar: {exc}", "error")
                self._messagebox.showwarning(
                    "Liste nicht gespeichert",
                    "Die QSOs sind in Wavelog markiert, aber die lokale Liste "
                    f"({Path(self._wavelog_sent_path()).name}) konnte nicht gespeichert "
                    f"werden:\n\n{exc}",
                    parent=self,
                )
            self.session.mark_sent(done_ids)
            self._update_show_sent()
            self._rebuild_cards()
            self.wavelog_section.count_var.set(f"{len(self.qsos)} offene QSOs")
        self.wavelog_mark_section.show_summary(done, errors)
        if errors:
            # Details stehen in der Zusammenfassung auf der Druckseite (kopierbar).
            self.status.set(f"Wavelog: {done} markiert, {len(errors)} Fehler.", "error")
        else:
            self.status.set(f"Wavelog: {done} QSO(s) als Papier-QSL gesendet markiert.", "ok")
        self.wavelog_mark_section.status_var.set(
            f"{done} QSO(s) markiert" + (f", {len(errors)} Fehler" if errors else "")
        )
        self._update_mark_state()
