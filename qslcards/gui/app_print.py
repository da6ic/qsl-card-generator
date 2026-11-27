"""Hauptfenster, Teil „Druck": Pflichtangaben prüfen, PDF erzeugen, öffnen.

Ein Baustein von `App` (siehe `gui/app.py`, Bewertung 3.1). Der Hintergrund-
lauf steckt in `controllers.print_job`; hier stehen Prüfung und Rückmeldung.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from tkinter import filedialog

from .sections import SENDER_LABELS

logger = logging.getLogger(__name__)


def done_message(outputs: list[str]) -> str:
    """Hinweis, wenn die fertige PDF nicht von selbst aufging.

    Ordner und Dateinamen auf eigenen Zeilen: das Hinweisfenster bricht lange
    Zeilen hart um, ein voller Pfad zerriss dort mitten im Dateinamen
    („…rueckseiten.pd" / „f"). Die technische Ursache (z. B. fehlendes
    xdg-open) steht im Protokoll, nicht im Fenster.
    """
    folders = {str(Path(path).parent) for path in outputs}
    lines = ["PDF erzeugt.", ""]
    if len(folders) == 1:
        lines += [f"Ordner: {folders.pop()}", ""]
        lines += [Path(path).name for path in outputs]
    else:
        lines += list(outputs)
    lines += ["", "Sie ließ sich nicht automatisch öffnen — bitte im Ordner öffnen."]
    return "\n".join(lines)


class PrintMixin:
    @property
    def _generating(self) -> bool:
        return self._print_job.running

    @property
    def _generated_cards(self) -> list:
        return self._print_job.cards

    @_generated_cards.setter
    def _generated_cards(self, cards) -> None:
        self._print_job.cards = list(cards)

    def _update_generate_state(self) -> None:
        busy = self._lookup_running or self._mostwanted_running or self._generating
        self.output_section.generate_btn.config(state="disabled" if busy else "normal")
        self.menubar.set_generate_enabled(not busy)

    def _check_required(self) -> tuple[list[str], int]:
        """Prüft alle Pflichtangaben und markiert die fehlenden in der Oberfläche.

        Geprüft werden Logbuch (1), Frontbild (2) und die Pflichtfelder des
        Absenders (3) — in einem Durchgang, damit der Nutzer nicht mehrmals auf
        denselben Fehler klickt. Liefert (Beschriftungen der fehlenden Angaben,
        Nummer des ersten betroffenen Abschnitts).
        """
        log = self.file_section.path_var.get().strip()
        if self.qsos_source == "wavelog":
            log_missing = not self._visible_qsos()
        else:
            log_missing = not self._visible_qsos() or not log or not Path(log).exists()
            self.file_section.set_missing(log_missing)

        front = self.image_section.path_var.get().strip()
        front_missing = not front or not Path(front).exists()
        self.image_section.set_missing(front_missing)

        missing_fields = self.sender_section.missing_required()
        self.sender_section.mark_missing(missing_fields)

        labels: list[str] = []
        if log_missing:
            labels.append("Logbuch")
        if front_missing:
            labels.append("Frontbild")
        labels += [SENDER_LABELS[f] for f in missing_fields]
        first_section = 1 if log_missing else 2 if front_missing else 3
        return labels, first_section

    def _on_generate(self) -> None:
        box = self._messagebox
        if self._lookup_running:
            box.showinfo("Lookup läuft", "Bitte warten, bis die Stationen nachgeschlagen sind.")
            return
        if self._mostwanted_running:
            box.showinfo(
                "Most-Wanted-Liste lädt", "Bitte warten, bis die GDXF-Liste abgerufen ist."
            )
            return
        missing, first_section = self._check_required()
        if missing:
            # Kein Dialog (Bewertung 2.5): der Assistent springt zur ersten
            # Stelle und nennt alles Fehlende in der Navigationsleiste; die
            # Felder sind rot markiert.
            self.status.set("Pflichtangaben fehlen – nichts erzeugt.", "error")
            self._goto_section(first_section)
            self.wizard.show_problem("Pflichtangaben fehlen: " + ", ".join(missing))
            return
        front = self.image_section.path_var.get().strip()
        cards = self.preview.included_cards()
        if not cards:
            box.showwarning("Keine Karten", "Es sind keine Karten zum Erzeugen ausgewählt.")
            return
        output = self.output_section.output_var.get().strip()
        if not output:
            box.showerror("Kein Ziel", "Bitte einen Ausgabepfad angeben.")
            return

        self.output_section.progress.config(maximum=len(cards), value=0)
        self.status.set("Erzeuge PDF…", "busy")
        self._print_job.start(
            cards,
            self._gather_config(),
            front,
            output,
            on_progress=self._update_progress,
            on_done=self._generate_done,
        )
        self._update_generate_state()

    def _update_progress(self, done: int, total: int) -> None:
        # maximum mitziehen: im getrennten Modus sind es 2×Kartenzahl Schritte.
        self.output_section.progress.config(maximum=total, value=done)
        self.status.set(f"Erzeuge PDF… {done}/{total}", "busy")

    def _generate_done(self, outputs: list[str], error: Exception | None) -> None:
        self._update_generate_state()
        if error is not None:
            self.status.set(f"Fehler: {error}", "error")
            self._messagebox.showerror("Fehler", f"PDF-Erzeugung fehlgeschlagen:\n{error}")
            return
        # Erfolg: kein Popup — alle erzeugten PDFs (im getrennten Modus zwei)
        # werden direkt in der Standardanwendung geöffnet. Schlägt das Öffnen
        # fehl, bleibt nur der Statushinweis.
        joined = ", ".join(outputs)
        try:
            for path in outputs:
                self._open_file(path)
            self.status.set(f"Fertig: {joined} (geöffnet)", "ok")
        except (OSError, subprocess.SubprocessError) as exc:
            self.status.set(f"Fertig: {joined}", "ok")
            logger.info("PDF nicht automatisch geöffnet: %s", exc)
            self._messagebox.showinfo("Fertig", done_message(outputs))
        self._after_generate_wavelog()

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="PDF speichern unter", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")]
        )
        if path:
            self.output_section.output_var.set(path)
