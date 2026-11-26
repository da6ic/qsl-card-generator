"""Hauptfenster, Teil „Abfrage": QRZ-/HamQTH-Lookups anstoßen und anzeigen.

Ein Baustein von `App` (siehe `gui/app.py`, Bewertung 3.1). Den Ablauf
(Generation, Warteschlange, Abbruch) regelt `controllers.lookup_runner`; hier
stehen nur Zugangsdaten aus den Feldern, Knöpfe und Meldungen.
"""

from __future__ import annotations

from pathlib import Path

from qslcards.controllers.lookup_runner import LookupOutcome, LookupProgress, format_eta
from qslcards.lookup import DEFAULT_CACHE_PATH, LookupCredentials, has_lookup_credentials
from qslcards.lookup import secret as lookup_secret


class LookupMixin:
    # ------------------------------------------------------- Zugangsdaten
    def _lookup_credentials(self) -> LookupCredentials:
        """Zugangsdaten aus Schritt 3 — nur zur Laufzeit, nie aus der Config.
        `program_id` ist der einzige Teil, der in der Config steht."""
        section = self.lookup_section
        return LookupCredentials(
            hamqth_user=section.hamqth_user.get(),
            hamqth_pass=section.hamqth_pass.get(),
            qrz_user=section.qrz_user.get(),
            qrz_pass=section.qrz_pass.get(),
            program_id=self.base_config.lookup.program_id,
        )

    def _credential_signature(self) -> tuple:
        c = self._lookup_credentials()
        return (c.qrz_user, c.qrz_pass, c.hamqth_user, c.hamqth_pass)

    def _restore_lookup_credentials(self) -> None:
        """Beim Start: gemerkte QRZ-/HamQTH-Zugänge aus dem Schlüsselbund (2.3)."""
        section = self.lookup_section
        if not section.remember.get():
            return
        for provider, user_var, pass_var in (
            ("qrz", section.qrz_user, section.qrz_pass),
            ("hamqth", section.hamqth_user, section.hamqth_pass),
        ):
            user, password = lookup_secret.load(provider)
            if user and not user_var.get():
                user_var.set(user)
                pass_var.set(password)

    def _store_lookup_credentials(self) -> None:
        """Zugänge in den Schlüsselbund (nur mit Haken), sonst nichts."""
        if not self.lookup_section.remember.get():
            return
        c = self._lookup_credentials()
        lookup_secret.save("qrz", c.qrz_user, c.qrz_pass)
        lookup_secret.save("hamqth", c.hamqth_user, c.hamqth_pass)

    def _on_remember_lookup_toggle(self, *_args) -> None:
        if self._suppress_save:
            return
        if self.lookup_section.remember.get():
            self._store_lookup_credentials()
        else:
            for provider in lookup_secret.PROVIDERS:
                lookup_secret.delete(provider)

    # ------------------------------------------------------------ Ablauf
    @property
    def _lookup_running(self) -> bool:
        return self._lookups.running

    def _lookup_calls_needed(self) -> list[str]:
        """Alle Rufzeichen der angezeigten QSOs (inkl. eingeblendeter gesendeter)."""
        return [q.call for q in self._visible_qsos()]

    def _start_lookups(self, calls: list[str], *, force: bool = False) -> None:
        """Schlägt `calls` im Hintergrund nach (Via/Manager/Adresse).

        Ohne Zugangsdaten passiert kein Netzcall: alle Via fallen auf den
        Standard. Während des Laufs ist „PDF erzeugen" gesperrt. Läuft schon
        ein Lookup (z. B. für das vorige Log), wird er abgebrochen und dieser
        startet direkt danach; dessen Ergebnisse werden verworfen (1.4).
        """
        if not calls:
            if self._lookup_running:
                self._lookups.cancel()
            self._rebuild_cards()
            return
        credentials = self._lookup_credentials()
        if not has_lookup_credentials(credentials):
            if self._lookups.busy:
                self._lookups.cancel()
            self._lookup_signature = None
            self._rebuild_cards()
            self.preview.set_status("Keine Lookup-Zugangsdaten – Via = Standard.")
            self._update_generate_state()
            return

        self._lookup_signature = self._credential_signature()
        self._lookups.start(
            calls,
            credentials,
            force=force,
            on_done=self._lookups_done,
            on_progress=self._lookups_progress,
        )
        self._rebuild_cards()  # zeigt „…" für Via/Route
        self.preview.set_status("Schlage Stationen nach…")
        self.status.set("Schlage Stationen nach…", "busy")
        self._update_lookup_buttons()
        self._update_generate_state()

    def _maybe_restart_lookups(self) -> None:
        """Nach Schritt 3: wurden (andere) Zugangsdaten eingegeben, als beim
        Laden des Logs da waren, jetzt neu nachschlagen."""
        if not self.session.has_any():
            return
        if not has_lookup_credentials(self._lookup_credentials()):
            return
        if self._lookup_signature == self._credential_signature():
            return
        self.lookups = {}
        self._start_lookups(self._lookup_calls_needed())

    def _update_lookup_buttons(self) -> None:
        running = self._lookup_running
        self.preview.refresh_btn.config(state="disabled" if running else "normal")
        self.preview.cancel_btn.config(state="normal" if running else "disabled")

    def _cancel_lookups(self) -> None:
        """„Abbrechen": laufenden Lookup stoppen; Gefundenes bleibt erhalten."""
        if self._lookups.cancel():
            self.preview.set_status("Breche Lookup ab…")

    def _refresh_lookups(self) -> None:
        """„Neu abrufen": offene (nicht aufgelöste) Stationen erneut versuchen;
        sind alle aufgelöst, wird ein vollständiger Force-Refresh gemacht."""
        if self._lookup_running or not self.qsos:
            return
        calls = self._lookup_calls_needed()
        unresolved = [c for c in calls if self.lookups.get((c or "").strip().upper()) is None]
        self._start_lookups(unresolved or calls, force=True)

    def _lookups_progress(self, progress: LookupProgress) -> None:
        eta = format_eta(progress.eta_seconds)
        text = f"Schlage Stationen nach… {progress.done}/{progress.total}"
        self.preview.set_status(f"{text} · {eta}" if eta else text)

    def _lookups_done(self, outcome: LookupOutcome) -> None:
        self.lookups.update(outcome.results)
        self._rebuild_cards()
        self._update_lookup_buttons()
        self._update_generate_state()

        auth_errors = outcome.auth_errors
        self.lookup_section.mark_auth_failed(auth_errors)
        if auth_errors:
            self._report_auth_errors(auth_errors)
            return

        calls = {(q.call or "").strip().upper() for q in self._visible_qsos() if q.call}
        total = len(calls)
        found = sum(1 for c in calls if self.lookups.get(c) is not None)
        if outcome.cancelled:
            text = (
                f"Lookup abgebrochen – {found}/{total} Stationen gefunden. "
                "„Neu abrufen“ holt den Rest."
            )
            self.preview.set_status(text)
            self.status.set(text, "error")
            return
        text = f"Lookup fertig – {found}/{total} Stationen gefunden."
        self.preview.set_status(text)
        self.status.set(text, "ok")

    def _report_auth_errors(self, auth_errors: dict) -> None:
        """Warnt, wenn ein Anbieter die Zugangsdaten abgelehnt hat.

        Ohne diesen Hinweis sähe der Nutzer nur „0 Stationen gefunden" und
        hätte keinen Anhaltspunkt, dass sein Passwort das Problem ist.
        """
        names = " und ".join(auth_errors)
        short = f"Anmeldung bei {names} fehlgeschlagen – Zugangsdaten prüfen."
        self.preview.set_status(short)
        self.status.set(short, "error")
        self._goto_section(6)
        details = "\n".join(f"• {provider}: {message}" for provider, message in auth_errors.items())
        self._messagebox.showwarning(
            "Anmeldung fehlgeschlagen",
            "Die Zugangsdaten wurden vom Anbieter abgelehnt:\n\n"
            f"{details}\n\n"
            "Bitte in Schritt 3 (Abfrage) prüfen. Ohne Anmeldung bleiben alle "
            "Zustellwege auf dem Standard.",
        )

    def _clear_lookup_cache(self) -> None:
        """Menü „Aktionen": die Cache-Datei löschen (nach Rückfrage).

        Danach fragt der nächste Lookup wieder frisch beim Anbieter nach — nützlich,
        wenn sich Routing-Daten einer Station geändert haben.
        """
        path = Path(DEFAULT_CACHE_PATH)
        if not path.exists():
            self.status.set("Kein Lookup-Cache vorhanden.", "info")
            return
        if not self._confirm(
            self,
            "Lookup-Cache leeren",
            f"Die Datei „{path.name}“ wird gelöscht.\n"
            "Beim nächsten Lookup werden alle Stationen neu abgefragt.",
            ok_label="Löschen",
        ):
            return
        try:
            path.unlink()
        except OSError as exc:
            self.status.set(f"Cache konnte nicht gelöscht werden: {exc}", "error")
            return
        self.status.set("Lookup-Cache geleert.", "ok")
