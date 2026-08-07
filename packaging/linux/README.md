# Linux-Bündel bauen (Fedora)

## Auf einem Fedora-Rechner

```bash
sudo dnf install python3 python3-pip python3-tkinter binutils
python3 -m venv .venv
.venv/bin/pip install -e ".[build]"
.venv/bin/python scripts/build_app.py --clean
```

Ergebnis: `dist/QSL-Karten-Generator-<version>-linux-x86_64.tar.gz`

## Im Container (auch vom Mac aus)

Grundlage ist `fedora:42`, das offizielle Abbild von Docker Hub.

```bash
docker build --platform linux/amd64 -f packaging/linux/Dockerfile.fedora -t qslcards-build .
docker run  --rm --platform linux/amd64 -v "$PWD:/src" qslcards-build
```

`--platform linux/amd64` ist auf Apple Silicon nötig — ohne die Angabe entsteht
ein aarch64-Programm, das auf keinem üblichen Fedora-PC läuft. Die Emulation
macht den Lauf spürbar langsam, das Ergebnis ist aber richtig.

Mit podman derselbe Aufruf, zusätzlich `:z` an der Einhängung
(`-v "$PWD:/src:z"`) wegen SELinux.

## Warum Fedora 42 und nicht das neueste

PyInstaller bündelt **keine glibc**. Ein Programm läuft nur auf Systemen, deren
glibc mindestens so neu ist wie die des Baurechners — gebaut wird deshalb auf der
ältesten Fedora-Version, die unterstützt werden soll.

Fedora 42 ist die erste mit **Tcl/Tk 9.0** systemweit. Das ist die Untergrenze:
mit Tk 8.6 fehlen der Vorschautabelle stillschweigend die Stift- und
Schalter-Symbole (`qslcards/gui/preview.py` fängt den Fehler ab).

Das Python 3.13 aus Fedora 42 genügt. Unter Linux kommt Tk vom System, nicht vom
Interpreter — die Empfehlung „Python 3.14" gilt nur für Windows und macOS.

## Installieren (beim Anwender)

```bash
tar xzf QSL-Karten-Generator-*-linux-x86_64.tar.gz
cd QSL-Karten-Generator
./install.sh
```

Landet unter `~/.local/opt/qsl-karten-generator`, mit Menüeintrag und Symbolen in
`~/.local/share`. Kein `sudo` — das Programm soll seinen eigenen Ordner
beschreiben können und ein Update darf kein Passwort kosten.
Entfernen: `./install.sh --uninstall`.

Ohne Installation läuft es genauso: `./QSL-Karten-Generator` im entpackten Ordner.

## Laufzeitabhängigkeiten außerhalb des Bündels

Auf einer Fedora-Workstation beides vorhanden; in einer minimalen Installation
nicht. Es stirbt nichts, es fehlt nur eine Funktion — `install.sh` weist darauf hin.

| Werkzeug    | Paket       | Wofür |
|-------------|-------------|-------|
| `xdg-open`  | `xdg-utils` | „PDF öffnen", „Ordner anzeigen" |
| `gsettings` | `glib2`     | Farbthema folgt dem System (hell/dunkel) |

## Nach dem Bauen prüfen

1. Programm startet, kein Terminalfenster.
2. **Vorschautabelle zeigt Stift- und Schaltersymbole** — der Beweis, dass Tk 9
   mitgekommen ist. Fehlen sie, wurde mit Tk 8.6 gebaut.
3. Logbuch laden, PDF erzeugen — **Umlaute auf der Karte** korrekt (DejaVuSans
   aus dem Bündel, sonst Helvetica-Fallback).
4. `Hilfe ▸ Handbuch` zeigt Text.
5. Nach dem Erzeugen öffnet sich die PDF von selbst. Passiert nichts, erbt
   `xdg-open` die Bibliothekspfade des Bündels — siehe `paths.subprocess_env()`.
6. „Aktionen ▸ Ausgabeordner anzeigen" öffnet den Dateimanager (gleicher Grund).
7. `~/.config/qsl-karten-generator/config.yaml` entsteht, sobald ein Feld
   geändert wird, und trägt oben die Zeile „bitte nicht von Hand bearbeiten".
8. Eine `config.yaml` neben `QSL-Karten-Generator` legen → Portable-Modus:
   Config, Cache und `qslcards.log` bleiben im Programmordner.
