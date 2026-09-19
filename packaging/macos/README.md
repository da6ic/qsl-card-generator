# macOS-Bündel bauen (Apple Silicon)

Es gibt **kein** Cross-Compile: PyInstaller bündelt den Interpreter, unter dem es
läuft. Ein macOS-Programm entsteht nur auf einem Mac.

## Warum hier kein eigenes Bauskript liegt

Windows hat `build.ps1` und Linux ein `Dockerfile.fedora`, weil dort erst einmal
etwas beschafft werden muss — ein Interpreter samt venv bzw. überhaupt ein
Fedora. Auf dem Entwicklungsrechner steht beides längst; ein Skript wäre eine
Zeile Fassade um den Aufruf, der ohnehin für alle Plattformen gilt:

```bash
.venv/bin/python scripts/build_app.py --clean
```

`scripts/build_app.py` **ist** das plattformübergreifende Bauskript. Was
speziell macOS betrifft, steht dort in `macos_delivery_folder` und
`package_macos`; was ins Bündel wandert, in `packaging/qslcards.spec`.

Soll dabei zugleich die **Version** steigen, ist `scripts/release.py
patch|minor|major` der richtige Aufruf: er hebt die Zeile in
`qslcards/__init__.py` an, läuft durch die Tests, ruft genau das obige Bauskript
und setzt Commit und Tag (Einzelheiten in `README.md`). Der Versionssprung
gehört auf **einen** Rechner — Windows und Fedora bauen danach denselben Stand
mit `build_app.py`, nicht mit `release.py`, sonst entstünden drei Tags für eine
Version.

## Python besorgen

Die Bedingung ist **Tk ≥ 9**, nicht eine bestimmte Python-Version: die
Vorschautabelle zeichnet ihre Stift- und Schaltersymbole aus SVG, und das kann
erst Tk 9. Mit Tk 8.6 fehlen sie **ohne jede Fehlermeldung** — das Programm
startet, es sieht nur falsch aus (`qslcards/gui/preview.py` fängt den Fehler ab).

Woher Tk kommt, hängt davon ab, wie Python installiert wurde:

| Herkunft | Was zählt |
|---|---|
| **Homebrew** | Das Paket `tcl-tk` (9.0), nicht die Python-Punktversion. `brew install python-tk` zieht es mit. |
| **python.org** | Die **Punktversion**: erst **3.14.7** bringt Tcl/Tk 9.0.4 mit, 3.14.0–3.14.6 und 3.13 liefern noch 8.6.15. |

> **Für ein Archiv, das weitergegeben wird, ist python.org ab 3.14.7 Pflicht** —
> nicht wegen Tk, sondern wegen des Deployment-Targets (nächster Abschnitt).
> Homebrew genügt, solange nur auf dem eigenen Rechner ausprobiert wird.

Prüfen, was das venv wirklich hat:

```bash
.venv/bin/python -c "import tkinter; print(tkinter.TkVersion)"   # 9.0 oder höher
```

`build_app.py` prüft dasselbe vorab und bricht mit Klartext ab, statt still
etwas Kaputtes zu bauen. **PyInstaller 6.21.0 genügt hier** — den
Entwicklungsstand braucht nur Windows, weil dort Tcl seine Bibliothek in die DLL
legt (`//zipfs:/…`). Auf macOS liegen die Tcl-Daten weiterhin als Ordner vor.

## Auf welchen macOS-Versionen das Ergebnis läuft

**Die Herkunft des Interpreters entscheidet das — nicht eine Einstellung.**
PyInstaller bündelt dessen Bibliotheken (CPython-Erweiterungen, Tcl/Tk, OpenSSL,
zlib), und die tragen sein `MACOSX_DEPLOYMENT_TARGET`. `dyld` lehnt eine dylib
ab, die für ein neueres System gebaut wurde als das laufende — das Programm
startet auf einem älteren Mac also gar nicht.

| Herkunft | Deployment-Target | Ergebnis läuft ab |
|---|---|---|
| **Homebrew** | das **gerade laufende** macOS | genau dieser Version |
| **python.org** | fest (10.13 bzw. 11.0) | allen unterstützten Versionen |

Das ist das macOS-Gegenstück zur glibc-Frage unter Linux, wo deshalb im ältesten
unterstützten Fedora gebaut wird. Nur sieht man es hier **nie**: der Baurechner
erfüllt seine eigene Anforderung per Definition.

Nachsehen, wofür gebaut würde:

```bash
.venv/bin/python -c "import sysconfig; print(sysconfig.get_config_var('MACOSX_DEPLOYMENT_TARGET'))"
```

Am fertigen Bündel nachmessen (`minos` je Binärdatei):

```bash
APP="dist/QSL-Karten-Generator-<version>-macos-arm64/QSL-Karten-Generator.app"
find "$APP/Contents/Frameworks" -name "*.dylib" -o -name "*.so" | while read -r f; do
  otool -l "$f" | awk '/LC_BUILD_VERSION/{g=1} g&&/minos/{print $2; exit}'
done | sort | uniq -c
```

`build_app.py` sagt beim Bauen, für welche Systeme das Ergebnis taugt, und
`LSMinimumSystemVersion` in der `Info.plist` wird aus demselben Wert abgeleitet
(`build_app.macos_minimum_system_version`). Das ist wichtiger, als es klingt:
stünde dort wie früher fest `11.0`, ließe Launch Services das Programm auf jedem
Mac starten — PyInstallers Bootloader (Ziel 11.0) liefe tatsächlich an, und erst
das Nachladen bräche mit einer dyld-Meldung ab, mit der ein Anwender nichts
anfangen kann. Mit dem echten Wert meldet macOS sauber „erfordert macOS X oder
neuer".

Bewusst nur eine **Warnung**, kein Abbruch: für welches Publikum gebaut wird,
entscheidet, wer baut.

### Die Auslieferungs-Umgebung einrichten

Einmalig, und danach ist sie das, womit Archive entstehen:

1. Von <https://www.python.org/downloads/macos/> den **„macOS 64-bit universal2
   installer"** ab **3.14.7** laden und ausführen (braucht Administratorrechte).
   Homebrew ist hier kein Ersatz — es baut immer gegen das laufende System.
2. Gegenprobe: **beides** muss stimmen, sonst ist es die falsche Fassung.

   ```bash
   PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14
   "$PY" -c "import sysconfig, tkinter; \
     print(sysconfig.get_config_var('MACOSX_DEPLOYMENT_TARGET'), tkinter.TkVersion)"
   # erwartet: 10.13 9.0   (nicht: 26 9.0  und nicht: 10.13 8.6)
   ```

3. Eigenes venv dafür — `.venv` bleibt die Entwicklungsumgebung, `.venv-build`
   ist die zum Ausliefern (beide sind in `.gitignore`, der Name ist derselbe wie
   unter Windows):

   ```bash
   "$PY" -m venv .venv-build
   .venv-build/bin/python -m pip install -e ".[dev,build]"
   .venv-build/bin/python scripts/build_app.py --clean
   ```

   Bleibt die `Achtung:`-Meldung zum Deployment-Target aus, stimmt die Umgebung.

Danach prüfen wie oben beschrieben: `LSMinimumSystemVersion` in der `Info.plist`,
die `minos`-Zählung über die mitgelieferten Bibliotheken und die Zeile
„Systemvoraussetzung" in der `LIESMICH.txt` im Archiv.

## Bauen

```bash
.venv/bin/pip install -e ".[build]"
.venv/bin/python scripts/build_app.py --clean
```

Ergebnis in `dist/`:

```
QSL-Karten-Generator-<version>-macos-arm64/     ← zum Ausprobieren
    QSL-Karten-Generator.app
    LIESMICH.txt
QSL-Karten-Generator-<version>-macos-arm64.zip  ← das, was weitergegeben wird
```

Die `.app` liegt bewusst **in einem Ordner** und nicht allein in `dist/`: unter
Windows und Linux passt die Kurzanleitung neben die Programmdatei, auf macOS
gibt es dafür keinen Platz — in die `.app` gehört nichts hinein. Der Ordner
trägt beides. Nebenbei räumt der Build den rohen COLLECT-Ordner weg, den
PyInstaller zusätzlich zur `.app` ablegt; er wäre nicht nur doppelt, er läge
auch genau dort, wo der Portable-Modus nach `config.yaml` sucht.

**Gepackt wird mit `ditto`, niemals mit `zip`.** Ein gewöhnliches `zip` (auch
`shutil.make_archive`) löst die Symlinks in `Contents/Frameworks` auf und
zerstört damit die Code-Signatur. Die entpackte Anwendung startet dann gar nicht
mehr: „…is damaged and can't be opened".

**Nur arm64.** `target_arch=None` in der Spec heißt „die Architektur des
bauenden Python" — ein Universal-Bündel entsteht nicht. Auf einem Intel-Mac
gebaut hieße das Archiv `…-macos-x86_64`; geprüft ist ausschließlich arm64.

## Signatur und Gatekeeper

PyInstaller signiert die `.app` selbst **ad hoc** (`codesign_identity=None` in
der Spec). Auf Apple Silicon ist eine Signatur Pflicht — ohne sie startet nichts.

Ad hoc heißt: kein Entwicklerzertifikat, keine Notarisierung. Für den Anwender
bedeutet das eine Meldung beim ersten Start, und der Weg daran vorbei hat sich
mit **macOS 15 (Sequoia)** geändert — Apple hat den bekannten Rechtsklick-Trick
für nicht notarisierte Programme entfernt:

* **macOS 15 und neuer**: Doppelklick, Meldung wegklicken, dann
  *Systemeinstellungen ▸ Datenschutz & Sicherheit ▸ Dennoch öffnen*.
* **macOS 14 und älter**: Rechtsklick ▸ *Öffnen*.

Beides steht für den Anwender in `LIESMICH.txt` (wandert beim Verpacken in den
Ordner) und im Handbuch, Kapitel „Installieren und weitergeben".

Die Meldung kommt nur, wenn die App das Quarantäne-Flag trägt — das setzen
Browser, Mail und AirDrop, ein lokaler Kopiervorgang nicht. **Deshalb sieht man
sie beim Selbsttest aus `dist/` nie.** Zum Nachstellen:

```bash
xattr -w com.apple.quarantine "0083;00000000;Safari;" \
    "dist/…-macos-arm64/QSL-Karten-Generator.app"
xattr -d com.apple.quarantine "…/QSL-Karten-Generator.app"   # wieder weg
```

Signatur ansehen: `codesign -dv --verbose=2 "…/QSL-Karten-Generator.app"`.
`spctl -a -vv` meldet dagegen „rejected (the code is valid but does not seem to
be an app)" — das ist bei einer ad hoc signierten App **erwartet** und kein
Fehler.

Notarisierung ist bewusst außen vor: sie setzt ein Apple-Developer-Programm
voraus (99 USD/Jahr).

## Ausliefern

Der Anwender entpackt das ZIP und zieht die `.app` dorthin, wo er sie haben
will — „Programme", Schreibtisch oder USB-Stick. Ein Installationsprogramm gibt
es nicht; zum Entfernen genügt der Papierkorb.

`LSMinimumSystemVersion` steht im Info.plist auf **11.0**. Wie weit es
tatsächlich zurückreicht, hängt an den Bibliotheken des bauenden Python
(Homebrew baut für die aktuellen macOS-Versionen); geprüft ist nur macOS 26.

## Wo die Daten landen

| | Ort |
|---|---|
| Standard | `~/Library/Application Support/QSL-Karten-Generator/` (Config, `lookup_cache.json`, `qslcards.log`) |
| Portable | neben der `.app`, sobald dort eine `config.yaml` liegt |

„Neben der `.app`" ist wörtlich zu nehmen: `sys.executable` liegt in
`QSL-Karten-Generator.app/Contents/MacOS/`, für den Anwender „liegt" das
Programm aber drei Ebenen höher — `paths.program_dir()` rechnet das um. Behält
der Anwender den entpackten Ordner (etwa auf einem USB-Stick), genügt eine
`config.yaml` **darin**. Den Finder erreicht man über `Hilfe ▸ config.yaml
öffnen`; `~/Library` ist von Haus aus ausgeblendet.

## Nach dem Bauen prüfen

1. `QSL-Karten-Generator.app` startet per Doppelklick, kein Terminalfenster.
2. **Vorschautabelle zeigt Stift- und Schaltersymbole** — der Beweis für Tk 9.
3. Dock-Symbol und Programmmenü tragen den richtigen Namen; „Über
   QSL-Karten-Generator" zeigt die Version.
4. Die Oberfläche ist **scharf** (Retina): fehlt `NSHighResolutionCapable` im
   Info.plist, rendert macOS alles in doppelter Pixelgröße hoch.
5. Logbuch laden, PDF erzeugen — **Umlaute auf der Karte** korrekt (DejaVuSans
   aus dem Bündel, sonst Helvetica-Fallback).
6. `Hilfe ▸ Handbuch` zeigt Text.
7. Nach dem Erzeugen öffnet sich die PDF von selbst; „Aktionen ▸ Ausgabeordner
   anzeigen" öffnet den Finder (`paths.subprocess_env()` — sonst erbt `open` die
   Bibliothekspfade des Bündels).
8. `~/Library/Application Support/QSL-Karten-Generator/config.yaml` entsteht,
   sobald ein Feld geändert wird, und trägt oben die Zeile „bitte nicht von Hand
   bearbeiten".
9. Eine `config.yaml` neben die `.app` legen → Portable-Modus: Config, Cache und
   `qslcards.log` bleiben dort.
10. **Aus dem Archiv heraus prüfen**, nicht nur aus `dist/`: ZIP an einen anderen
    Ort entpacken und von dort starten. Das ist der Test, der ein kaputtes
    `zip` (aufgelöste Symlinks, zerstörte Signatur) auffliegen lässt.
