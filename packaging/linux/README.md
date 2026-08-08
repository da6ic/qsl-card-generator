# Linux-Bündel bauen (Fedora)

## Auf einem Fedora-Rechner

```bash
sudo dnf install python3.14 python3.14-tkinter binutils
python3.14 -m venv .venv
.venv/bin/pip install -e ".[build]"
.venv/bin/python scripts/build_app.py --clean
```

**`python3.14`, nicht `python3`** — die Begründung steht gleich unten, es ist der
eine Punkt, an dem dieser Build kippt.

Ergebnis: `dist/QSL-Karten-Generator-<version>-linux-x86_64.tar.gz`

## Im Container (auch vom Mac aus)

Grundlage ist `fedora:42`, das offizielle Abbild von Docker Hub.

```bash
docker build --platform linux/amd64 -f packaging/linux/Dockerfile.fedora -t qslcards-build .
docker run  --rm --platform linux/amd64 --user "$(id -u):$(id -g)" \
            -v "$PWD:/src" qslcards-build
```

`--platform linux/amd64` ist auf Apple Silicon nötig — ohne die Angabe entsteht
ein aarch64-Programm, das auf keinem üblichen Fedora-PC läuft.

`--user` ist keine Kür: ohne die Angabe baut der Container als root, und `dist/`,
`build/` und `qslcards.egg-info/` gehören hinterher root — vom Mac aus ließen sie
sich nicht einmal mehr löschen.

Mit podman derselbe Aufruf ohne `--user` (podman bildet den Benutzer von sich aus
ab), dafür mit `:z` an der Einhängung (`-v "$PWD:/src:z"`) wegen SELinux.

> **Vorher `dist/` sichern.** Der Container ruft `build_app.py --clean` auf, und
> `dist/` wie `build/` sind über die Einhängung dieselben Ordner wie auf dem
> Host — ein Container-Lauf löscht also das macOS- oder Windows-Bündel, das dort
> noch liegt. Dasselbe gilt umgekehrt. Die Archive selbst kollidieren nicht
> (`…-linux-x86_64.tar.gz` neben `…-macos-arm64.zip`), es ist allein das
> `--clean`. Ohne `--clean` zu bauen wäre keine Lösung: dann fände PyInstaller in
> `build/pyinstaller` noch die Analyse-Zwischenstände der anderen Plattform.

## Warum Fedora 42 und nicht das neueste

PyInstaller bündelt **keine glibc**. Ein Programm läuft nur auf Systemen, deren
glibc mindestens so neu ist wie die des Baurechners — gebaut wird deshalb auf der
ältesten Fedora-Version, die unterstützt werden soll. Fedora 42 hat glibc 2.41.

## Warum `python3.14` und nicht das Standard-Python

Weil sonst mit **Tk 8.6** gebaut würde, und damit fehlen der Vorschautabelle
stillschweigend die Stift- und Schalter-Symbole (`qslcards/gui/preview.py` fängt
den Fehler ab). `scripts/build_app.py` bricht deshalb vorher ab.

Der Reihe nach — Fedora 42 hat Tcl/Tk 9 **als Systempaket**:

| Paket   | Version auf F42 |
|---------|-----------------|
| `tcl`   | 9.0.0           |
| `tk`    | 9.0.0           |
| `tcl8`  | 8.6.15 (Kompatibilität) |
| `tk8`   | 8.6.15 (Kompatibilität) |

Sein Standard-Python ist aber 3.13, und dessen tkinter ist gegen die
**Kompatibilitätspakete** gebaut (`dnf repoquery --requires`):

```
python3-tkinter     (3.13)  ->  libtcl8.6.so    libtk8.6.so
python3.14-tkinter  (3.14)  ->  libtcl9.0.so    libtcl9tk9.0.so
```

`python3 -c "import tkinter; print(tkinter.TkVersion)"` meldet auf Fedora 42
also **8.6**, `python3.14` dagegen **9.0**. Fedora liefert 3.14 als
Parallel-Interpreter mit; mehr braucht es nicht.

*Verworfen:* auf `fedora:43` zu wechseln, dessen Standard-Python bereits 3.14 ist.
Dessen glibc ist 2.42 — das fertige Programm liefe dann nicht mehr auf Fedora 42,
und genau darum geht es bei der Wahl der Basis.

Die Regel „erst Python 3.14.7 bringt Tcl/Tk 9.0.4" gilt hier **nicht**: sie
beschreibt die Installer von python.org für Windows und macOS, die Tcl/Tk
mitbringen. Unter Linux kommt Tk vom System — das Fedora-Python 3.14.5 genügt.
Ebenso genügt das veröffentlichte **PyInstaller 6.21.0**: `info library` liefert
hier einen echten Ordner (`/usr/share/tcl9.0`), keinen eingebetteten
`//zipfs:/`-Pfad. Die `develop`-Fassung ist nur unter Windows nötig.

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
3. **Frontbild wählen → die Miniatur in Abschnitt 2 zeigt das Bild.** Bleibt dort
   „keine Vorschau" stehen, fehlt `PIL._tkinter_finder` im Bündel (siehe unten).
4. Logbuch laden, PDF erzeugen — **Umlaute auf der Karte** korrekt (DejaVuSans
   aus dem Bündel, sonst Helvetica-Fallback).
5. `Hilfe ▸ Handbuch` zeigt Text.
6. Nach dem Erzeugen öffnet sich die PDF von selbst. Passiert nichts, erbt
   `xdg-open` die Bibliothekspfade des Bündels — siehe `paths.subprocess_env()`.
7. „Aktionen ▸ Ausgabeordner anzeigen" öffnet den Dateimanager (gleicher Grund).
8. `~/.config/qsl-karten-generator/config.yaml` entsteht, sobald ein Feld
   geändert wird, und trägt oben die Zeile „bitte nicht von Hand bearbeiten".
9. Eine `config.yaml` neben `QSL-Karten-Generator` legen → Portable-Modus:
   Config, Cache und `qslcards.log` bleiben im Programmordner.

Prüfen lässt sich das alles ohne Fedora-Rechner: ein zweiter Container mit
`Xvfb` und `xdotool` genügt (`DISPLAY=:99`, Screenshot mit `import -window root`).
Wichtig ist, diesen Prüfcontainer aus dem **nackten** `fedora:42` zu bauen, ohne
Python — sonst beweist ein Start nichts über die Vollständigkeit des Bündels.

## Die Falle, die dieser Bauvorgang aufgedeckt hat

Beim ersten Prüfdurchlauf blieb die Bildvorschau leer. Im Protokoll stand:

```
File "qslcards/gui/app.py", line 704, in _update_thumbnail
File "PIL/ImageTk.py", line 63, in _pyimagingtkcall
ModuleNotFoundError: No module named 'PIL._tkinter_finder'
```

`PIL._tkinter_finder` wird erst zur Laufzeit und aus Pillows C-Erweiterung
`_imagingtk` heraus geladen — die statische Analyse von PyInstaller kann diesen
Import nirgends sehen. Behoben mit `hiddenimports` in `packaging/qslcards.spec`.

Zwei Dinge daran sind lehrreich:

* **Die PDF war trotzdem in Ordnung.** Das Frontbild geht dort über
  `drawImage(pfad)`, ganz ohne Tk. Betroffen ist allein die Miniatur in der GUI.
* **Es fiel niemandem auf**, weil `_update_thumbnail` nur `OSError`/`ValueError`
  fängt: der `ModuleNotFoundError` landet im Protokoll, und im Fenster steht
  weiterhin „keine Vorschau" — dasselbe, was vor der Bildauswahl dort stand.

### Warum das **nur** Linux trifft

Naheliegender Verdacht war, dass macOS und Windows denselben Fehler haben — die
Spec ist schließlich dieselbe, und `PIL._tkinter_finder` fehlt tatsächlich auch
im macOS-Bündel (nachgeprüft mit `PyInstaller.archive.readers` in dessen PYZ).
**Stimmt aber nicht:** dort wird das Modul nie importiert.

Der Grund steckt in Pillows `src/Tk/tkImaging.c`. `load_tkinter_funcs()` sucht
die Tcl/Tk-Symbole zuerst im laufenden Prozess. Auf macOS sind sie global
sichtbar, die Suche gelingt sofort. Auf Linux lädt CPython `_tkinter.so` mit
`RTLD_LOCAL` — die Symbole sind unsichtbar, und Pillow greift auf den Umweg
zurück: `PIL._tkinter_finder` importieren, daraus `TKINTER_LIB` lesen und die
Bibliothek selbst per `dlopen` öffnen. Windows hat für denselben Zweck einen
eigenen Zweig über `GetProcAddress`, ganz ohne dieses Modul.

Nachstellen lässt sich das in drei Zeilen — der Aufruf aus `_update_thumbnail`,
danach ein Blick in `sys.modules`:

```python
photo = ImageTk.PhotoImage(Image.new("RGB", (40, 30)))
"PIL._tkinter_finder" in sys.modules   # Linux: True, macOS: False
```

Der Zeichenkettenfund im Binary beweist dagegen **nichts**: `_imagingtk.so`
enthält „PIL._tkinter_finder" auf beiden Plattformen, nur wird der Zweig auf
macOS nie betreten.

Ein Neubau von macOS und Windows ist deshalb nicht nötig. Der `hiddenimports`-
Eintrag bleibt trotzdem in der Spec und gilt für alle drei Ziele: er kostet
nichts und beschreibt eine echte Abhängigkeit.
