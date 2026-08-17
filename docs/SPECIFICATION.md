# SPECIFICATION.md — QSL-Karten-Generator

Ausführliche Spezifikation. Ergänzt `CLAUDE.md`. Layout separat in `CARD_LAYOUT.md`.

---

## 1. Anwendungsfall

Ein Funkamateur (Absender, z.B. DN5MT) hat ein Logbuch — im **ADIF**-Format aus
dem Log-Programm oder im **Cabrillo**-Format aus einem Contest. Er will
QSL-Karten für bestätigte QSOs drucken. Das Programm erzeugt eine PDF, in der
jede Karte aus zwei A6-Seiten besteht (Bild vorne, Daten hinten) — wahlweise
auch zu viert auf einem A4-Bogen. Vor der Erzeugung wählt er das Logbuch,
Frontbild, Absenderdaten, die Priorität der Zustellwege (inkl. Trennlinie),
Kartenmodus und Druckmodus.

---

## 2. GUI (Tkinter)

Ein Hauptfenster mit **Menüleiste** (§2.1), einem scrollbaren Bereich mit den
Abschnitten 1–10 und einer **Statusleiste** am Fuß (§2.3). Farben und Abstände
kommen ausschließlich aus `gui/theme.py` (§2.2) — kein Widget setzt selbst eine
Farbe, so wie kein Zeichencode eine Layoutzahl setzt (`pdf/geometry.py`).

**Pflichtangaben** (§2.4) tragen einen roten `*`: Logbuch (1), Frontbild (2)
und im Absender (3) Rufzeichen, Name, Locator, DOK, CQ-Zone, ITU. Fehlt davon
etwas, blockiert „PDF erzeugen" mit **einem** Popup und markiert die Stellen.

Die Abschnitte (top → bottom) liegen in `gui/sections.py`:

1. **Logbuch (ADIF/Cabrillo)** (Pflicht, `*` im Titel): `Durchsuchen…`-Button,
   Pfadanzeige, Button `Log laden`. Nach der Auswahl wird das Log **automatisch
   geladen** (Hot-Load); der Button dient als manueller Reload. Das Format wird
   am Inhalt erkannt (§4.6), die Endung ist nur ein Filter im Dateidialog. Nach
   dem Laden: Anzahl gelesener QSOs. Ohne geladenes Log wird das Pfadfeld
   markiert (§2.4).
2. **Frontbild** (Pflicht, `*` im Titel): `Bild wählen…` (png/jpg/jpeg/webp),
   kleine Vorschau (Thumbnail). Fehlt das Bild, ist der **Rahmen des
   Vorschaufeldes** die Markierung — ein Eingabefeld gibt es hier nicht.
3. **Absender**: Eingabefelder für Call, Name, Straße, PLZ, Ort, Land, Locator,
   DOK, CQ-Zone (WAZ), ITU; davon sind **Rufzeichen, Name, Locator, DOK, CQ-Zone
   und ITU** Pflicht (`*` an der Beschriftung), Adresse und Funk-Ausrüstung nicht.
   Durch eine Trennlinie abgesetzt die **Funk-Ausrüstung**
   (erscheint dynamisch auf der Karte, sobald gefüllt): `Empfänger` (RIG),
   `Antenne` (ANT), `Leistung` (PWR). Zusätzlich zwei globale Dropdowns (gelten für
   **alle** Karten):
   - **QSL-Markierung** (`qsl_mark`): `PSE QSL` / `TNX QSL` / `Leer lassen`.
   - **Bestätigung** (`confirm_mark`): `Leer lassen` / `Confirming QSO` /
     `Confirming SWL-Report`.

   **Rufzeichen, Locator und DOK** werden beim Verlassen des Feldes in
   Großbuchstaben umgestellt (die Karte tut es beim Zeichnen noch einmal, damit
   auch eine von Hand geänderte `config.yaml` richtig gedruckt wird). Das
   Rufzeichen trägt dabei **alles**, was dazugehört: Landespräfix (`F/DL0MT`),
   Portabel-Kennung (`F/DL0MT/P`), `/QRP`, `/MM`, Rufbezirk (`W1AW/4`). Ein
   eigenes Dropdown für die Portabel-Kennung gab es und wurde entfernt — es
   musste diese Fälle auseinanderhalten, ohne etwas zu gewinnen.
   Kein „Untertitel"/„Responsive" mehr. Keine Speichern/Laden-Buttons: die
   Config wird **automatisch** gespeichert (debounced) und bei externer Änderung
   von `config.yaml` **automatisch neu geladen**. Ausgenommen sind die
   Lookup-Zugangsdaten (Abschnitt 6) — sie werden weder gespeichert noch beim
   Neuladen überschrieben.
4. **Zustellwege**: eine priorisierbare **Liste** (Listbox) der Wege `Büro` (B),
   `Direkt` (D), `eQSL` (Q), `LOTW` (L) plus eine verschiebbare **Trennlinie**
   (`via_cut`). Buttons ▲/▼ verschieben den ausgewählten Eintrag (Trennlinie
   eingeschlossen). Wege **oberhalb** der Linie sind aktiv (werden gedruckt, in
   Reihenfolge = Priorität), Wege **darunter** nicht. Gedruckt wird je Empfänger
   der höchstpriorisierte aktive Weg aus dessen **akzeptierten** Wegen (aus dem
   Lookup, §6). Die Liste **entfernt keine Zeilen**, sondern setzt nur die
   Drucken-Markierung. Kein Via-Filter (B/D/M) mehr.
5. **Kartenmodus**: Radiobuttons `Eine Karte pro QSO` / `Eine Karte pro Station`.
   (Die globalen Markierungen QSL/Bestätigung stehen in Abschnitt 3.)
6. **Lookups (optional)**: HamQTH-Benutzer/Passwort, QRZ-Benutzer/Passwort,
   darunter die Hinweiszeile `sections.LOOKUP_SESSION_HINT` („Gilt nur für diese
   Sitzung — wird nicht gespeichert.", Style `Muted.TLabel`), dann die Checkbox
   „Adress-/Label-Export erzeugen". **Kein** Schalter „Adressen nachschlagen"
   mehr — der Lookup läuft **automatisch beim Log-Laden** (§6), sofern
   Zugangsdaten eingetragen sind.
   Die vier Zugangsdaten-Felder werden **nicht persistiert** (§3,
   `LookupCredentials`): sie starten jedes Mal leer, ihr Inhalt löst keinen
   Auto-Save aus und ein Neuladen der `config.yaml` lässt sie unangetastet. Die
   Hinweiszeile ist die bewusste Ausnahme von „keine Erklärtexte in den
   Abschnitten" — ohne sie wirkten die leeren Felder beim zweiten Start wie ein
   Fehler.
7. **Bemerkungen**: ein Textfeld „Text für alle Karten" (global, `generation.
   remarks`). Steht Text drin, erscheint auf der Rückseite der REMARKS-Kasten
   (dynamisch, §7); leer → kein Kasten. Max. **80 Zeichen**. Je Karte in der
   Vorschau (Abschnitt 8) überschreibbar.
8. **Vorschau**: Tabelle (`ttk.Treeview`) **aller** Karten/QSOs (nicht nur der
   gefilterten): Spalten `Drucken`, `Call`, `#QSOs`, `Via`, `Route/Manager`,
   `Remarks`, `Datum`, `UTC`. Die `Via`-Spalte zeigt den Zustellweg
   **ausgeschrieben** (`Büro`/`Direkt`/`eQSL`/`LOTW`); solange der Lookup läuft,
   steht dort „…". Auch bei **nicht** gedruckten Karten wird der (natürliche) Weg
   angezeigt, nie ein „—" — ob gedruckt wird, steht in der Spalte „Drucken".
   Zeilen sind über die Spalte „Drucken" ab-/anwählbar (auch Wege unter der
   Trennlinie manuell druckbar). Ein Klick in diese Spalte **wählt die Zeile
   nicht aus** (`"break"`), und `_toggle_print` nimmt sie aus einer bestehenden
   Auswahl: ttk zeichnet ausgewählte Zeilen in den Auswahlfarben und überdeckt
   damit den `off`-Tag — „Ja → Nein" würde sonst erst grau, wenn die Auswahl
   woanders hinwandert. **`Via`, `Route/Manager` und `Remarks` sind
   editierbar** (Doppelklick oder Klick auf das Hover-Icon; `Via` als Dropdown mit
   den ausgeschriebenen Wegen, die anderen als Textfeld; `Remarks` max. 80
   Zeichen) — so lassen sich Lookup-Fehlklassifizierungen von Hand korrigieren und
   Remarks je Karte setzen. **Bedien-Hinweise:** In den bearbeitbaren Spalten
   (inkl. `Drucken`) erscheint ein Stift-Icon im Spaltenkopf und beim Hovern
   rechtsbündig in der Zelle (vertikal mittig); die `Drucken`-Zelle zeigt beim
   Hovern stattdessen ein Umschalt-Icon (Klick toggelt Ja/Nein). Es ist immer nur
   **ein** Editor gleichzeitig offen; er schließt (übernimmt wie „Fokus verloren")
   beim Scrollen, damit er nicht an alter Position hängen bleibt. Icons liegen als
   SVG in `qslcards/assets/icons/` (Tk 9 rendert SVG nativ). Eine Via-Änderung
   zieht die Drucken-Markierung der Zeile nach. Eine **Remarks-Änderung**
   normalisiert im
   Modus „pro Station" die Karten der Station: Karten mit Remarks bleiben
   eigenständig (max. 3 Zeilen), aufeinanderfolgende Karten **ohne** Remarks
   führen sich wieder zusammen (max. 6 Zeilen) — so ist ein Remarks je Karte
   unabhängig möglich (§5.2). Die Korrekturen gelten für die Sitzung; ein
   erneuter Lookup („Neu abrufen"/Log neu laden) leitet Via/Remarks wieder ab.
   **Oben rechts** ein Button „Neu abrufen" (holt fehlende/abgebrochene Stationen
   nach) sowie eine Lookup-Statuszeile. Die gesamte Oberfläche ist scrollbar; die
   Tabelle zeigt mindestens ~5 Einträge.
9. **Druckmodus**: Zweispaltig. **Links** die Radiobuttons `Duplexdruck
   (Vorder-/Rückseite abwechselnd)` / `Vorder-/Rückseite getrennt (2 PDFs)` →
   `generation.print_mode` (`duplex` | `separate`, siehe §7), darunter — durch
   einen `ttk.Separator` abgesetzt, damit sie nicht wie eine dritte Modus-Option
   wirkt — die Checkbox `4 A6 QSL-Karten auf einem A4-Bogen` →
   `generation.sheet_mode` (`single` | `a4_4up`, siehe §7 „Bogendruck"). Sie ist
   **quer** zum Druckmodus und mit beiden kombinierbar. Die Tk-Variable trägt
   über `onvalue`/`offvalue` direkt den Config-Wert, `app.py` rechnet nichts um;
   Unbekanntes aus einer handgeschriebenen `config.yaml` fällt über
   `geometry.normalize_sheet_mode` auf `single` zurück.
   **Rechts daneben**
   die Checkbox `Erweiterte Einstellungen` (`generation.print_margin_enabled`);
   ist sie gesetzt, erscheint darunter der Block **Seitenrand (mm)** mit vier
   `ttk.Spinbox` (oben/unten/links/rechts, 0…`PRINT_MARGIN_MAX` = 15 mm, Schritt
   0,5) → `generation.print_margin_top/bottom/left/right` (siehe §7 „Druckrand").
   Beide Spalten liegen in **eigenen Containern** in derselben Grid-Zeile, oben
   verankert und **ohne `rowspan`**: sonst verteilt Tk die Höhe des Randblocks
   auf die übersprungenen Zeilen und verrückt beim Aufklappen die Radiobuttons.
   Der **Platz des Randblocks bleibt immer reserviert**
   (`_reserve_margin_space` misst ihn einmal und setzt ihn als `minsize` der
   Zeile): der Abschnitt behält so in beiden Zuständen seine Höhe, und das
   Ein-/Ausblenden schiebt die Abschnitte darunter nicht weg.
   Erklärtexte unter Checkbox und Randblock gab es zwischenzeitlich; sie wurden
   vom Nutzer wieder entfernt.
10. **Ausgabe**: Zielpfad der PDF, Button `PDF erzeugen` (Primärbutton,
   `Accent.TButton`) und Fortschrittsbalken (`ttk.Progressbar`). Die Statuszeile
   steht **nicht** mehr hier, sondern in der Fußleiste (§2.3). `PDF erzeugen` ist
   **deaktiviert**, solange der Lookup nach dem Log-Laden noch läuft, und wird erst
   danach wieder aktiv (synchron dazu der Menüeintrag). Fehlende Pflichtangaben
   sperren den Button **nicht**, sondern werden beim Klick gemeldet (§2.4). Nach Erfolg werden die
   erzeugten PDF(s) direkt in der Standardanwendung geöffnet.

Langlaufende Arbeit (PDF, Lookups) läuft in einem **Worker-Thread**; UI-Updates
nur über `root.after(...)` (Tkinter ist nicht thread-safe). Der Lookup startet
automatisch beim Log-Laden im Hintergrund, ohne die GUI zu blockieren (Bild/
Einstellungen bleiben bedienbar); es läuft immer nur **ein** Lookup-Thread.

### 2.1 Menüleiste (`gui/menu.py`)

`MenuBar` bekommt die Aktionen als Callbacks (`MenuActions`) — **keine**
Geschäftslogik, verdrahtet wird in `app.py` (wie bei `sections.py`).

| Menü | Einträge |
|------|----------|
| **Datei** | Logbuch öffnen… (⌘/Strg+O), Zuletzt verwendete Logs ▸, Frontbild wählen… (+B), Zuletzt verwendete Bilder ▸, Ausgabeziel wählen… (+⇧S), PDF erzeugen (+P) |
| **Bearbeiten** | Ausschneiden/Kopieren/Einfügen/Alles auswählen — als virtuelle Events ans fokussierte Widget |
| **Aktionen** | Log neu laden (+R), Lookups neu abrufen (+⇧R), Lookup-Cache leeren… |
| **Ansicht** | Farbthema ▸ System/Hell/Dunkel, Gehe zu Abschnitt ▸ 1–10 |
| **Hilfe** | Handbuch (F1 bzw. ⌘?), config.yaml öffnen, Ausgabeordner anzeigen, Lookup-Cache anzeigen, Über… |

Plattform-Eigenheiten sind in `menu.py` gekapselt: auf **macOS** ⌘-Kürzel sowie
„Über…"/„Beenden" im Programm-Menü (`name="apple"`, `tk::mac::Quit`), sonst
Strg-Kürzel mit „Beenden" in „Datei" und „Über…" in „Hilfe". Ein `accelerator`
ist bei Tk nur Beschriftung — die Kürzel werden zusätzlich per `bind_all`
registriert. Das Handbuch fällt aus dem Buchstaben-Schema von
`accelerator()`/`binding()` heraus und hat deshalb eigene Konstanten
(`HELP_ACCELERATOR`/`HELP_BINDING`): macOS `⌘?` (dort das übliche Hilfe-Kürzel),
sonst `F1`.

Die früher hier verlinkten Projektdokumente (README/Spezifikation/Karten-Layout)
sind **bewusst nicht mehr im Menü** — sie richten sich an Entwickler. An ihrer
Stelle steht das Anwender-Handbuch (§2.5).

### 2.2 Farbthema (`gui/theme.py`)

Palette „Funk-Blau" in **hell** und **dunkel**, je Rolle benannt (`bg`,
`surface`, `surface_alt`, `text`, `text_muted`, `border`, `accent`, `select_bg`,
`success`/`warning`/`danger`). Basis ist das ttk-Theme **`clam`** — nur die
mitgelieferten „klassischen" Themes lassen sich vollständig einfärben; die App
sieht dadurch auf allen Plattformen gleich aus.

- Modus aus `appearance.theme`: `system` (Default, erkennt macOS `defaults`,
  Windows-Registry, Linux `gsettings`), `light`, `dark`. Jede Erkennung ist „best
  effort" und fällt bei Fehlern auf hell zurück — nie fatal.
- Klassische tk-Widgets (Listbox, Canvas, Menüs) kennen keine ttk-Styles und
  werden per `restyle_tree(widget, palette)` eingefärbt — **beim Start und** bei
  jedem Wechsel, sonst behalten sie die Farben des Betriebssystems. Die Vorgabe
  für erst *später* erzeugte tk-Widgets (Dialog-Toplevel) steht in der
  Optionsdatenbank (`option_add("*Background"/"*Foreground")`).
- Achtung: **kein `tk_setPalette`.** Es setzt nicht nur diese Vorgaben, sondern
  läuft zusätzlich über den ganzen Widget-Baum und schreibt `-foreground`/
  `-background` als *Instanz*-Option auf jedes Widget, das sie kennt — auch auf
  `ttk::label`/`entry`/`combobox`/`spinbox`. Eine Instanz-Option schlägt den
  ttk-Style: nach dem ersten Wechsel wäre der rote `*` textfarben, ab dem
  zweiten blieben die Widgets sogar auf den Farben des alten Themas stehen.
- Achtung `clam`: Radio-/Checkbuttons färbt man über `indicatorbackground`/
  `indicatorforeground`; `indicatorcolor` (die Option der alten tk-Widgets) wird
  ignoriert.
- Pflichtangaben (§2.4) haben eigene Styles: `Required.TLabel` (der `*`),
  `Invalid.TEntry` (leeres Pflichtfeld) und `Invalid.Thumb.TLabel` (fehlendes
  Frontbild) — alle in `danger`. `Invalid.TEntry` braucht eine eigene `map`,
  sonst zieht die geerbte `TEntry`-Map den Rahmen bei Fokus/Hover wieder auf die
  Akzentfarbe, ausgerechnet im Feld, das gerade ausgefüllt wird.
  `SectionTitle.TLabel` ist der Abschnittstitel als eigenes Widget.
- Die Icon-Overlays in der Vorschautabelle sind transparent und werden gegen den
  Hintergrund ihres **Labels** gemischt. Dafür gibt es je einen Style pro
  möglichem Untergrund (`TreeIconHead`/`Odd`/`Even`/`Selected`), sonst liegt ein
  andersfarbiges Kästchen auf der Zeile.

Das Programm-Icon liegt als `assets/icons/app_icon.svg` und wird von
`scripts/make_icon.py` zu PNG (16–1024), `.ico` und `.icns` gerendert. Fürs
Fenster werden die PNGs **größte zuerst** an `iconphoto` übergeben (macOS
skaliert das erste Bild auf alle Größen); im „Über"-Dialog wird das Icon als
**Vektor** auf einen Canvas gezeichnet (`gui/icon_canvas.py`), weil Tk Bitmaps
auf Retina-Displays sichtbar hochskaliert.

### 2.3 Statusleiste, Scrollen, Tastenkürzel

- **Statusleiste** am Fensterfuß: farbiger Punkt + Meldung links
  (`info`/`busy`/`ok`/`error`), Kurzinfo rechts (QSO-Zahl, Dateiname). Sie liegt
  außerhalb des scrollbaren Bereichs und ist damit immer sichtbar.
- **Scrollen** (`gui/scrolling.py`): Die Fenstersysteme melden das Mausrad
  unterschiedlich — macOS kleine `delta`, Windows Vielfache von 120, X11 mit
  Tk 9 ebenfalls `<MouseWheel>`, X11 mit Tk 8.6 dagegen `<Button-4>`/`<Button-5>`.
  Die Alt-Buttons dürfen **nur** bei X11 + Tk < 9 gebunden werden, sonst kommt
  jede Rastung doppelt an. Die Vorschautabelle verschluckt das Rad nur, solange
  sie selbst scrollen kann, und reicht es am Anschlag an die Seite weiter.
- **Tastenkürzel in Eingabefeldern** (`gui/textedit.py`): Tk kann nur zeichenweise
  löschen. Ergänzt werden wort- und zeilenweises Löschen (macOS ⌥⌫/⌥⌦/⌘⌫/⌘⌦,
  sonst Strg+Rücktaste/Strg+Entf/Strg+U), gebunden an die Klasse `TEntry` und
  damit auch in den Editoren der Vorschautabelle wirksam.

### 2.4 Pflichtangaben

Ohne diese Angaben ist eine Karte unbrauchbar, deshalb blockieren sie die
Erzeugung: **Logbuch** (1), **Frontbild** (2) sowie im **Absender** (3)
`Rufzeichen`, `Name`, `Locator`, `DOK`, `CQ-Zone`, `ITU`
(`sections.REQUIRED_SENDER_FIELDS`). Adresse (Straße/PLZ/Ort/Land) und
Funk-Ausrüstung sind bewusst optional.

- **Kennzeichnung**: roter `*` — bei 1 und 2 im Abschnittstitel (deshalb baut
  `required_section()` den Titel als eigenes Widget: ein LabelFrame-Titel ist ein
  einziger Text und ließe sich nicht zweifarbig setzen), bei 3 an der
  Beschriftung jedes Pflichtfeldes. Die Fußnote „* Pflichtfeld"
  (`required_legend()`) steht **ganz unten im Fenster**, außerhalb des
  scrollbaren Bereichs über der Statusleiste — sie gilt für alle Abschnitte, in
  Abschnitt 3 sähe sie aus, als beträfe sie nur den Absender.
- **Prüfung**: `App._check_required()` prüft alles in **einem** Durchgang und
  liefert die fehlenden Angaben in Abschnittsreihenfolge. `_on_generate` zeigt
  daraufhin **ein** Popup mit der vollständigen Liste, setzt die Statuszeile auf
  `error` und scrollt zum **ersten** betroffenen Abschnitt. Erzeugt wird nichts.
- **Markierung**: leere Pflichtfelder bekommen `Invalid.TEntry` (roter Rahmen),
  das fehlende Frontbild `Invalid.Thumb.TLabel`. Sie erscheint **erst nach einem
  Druckversuch** — beim ersten Start wäre sonst das halbe Fenster rot — und
  verschwindet je Feld wieder, sobald es gefüllt ist (Trace je Variable bzw.
  `set_missing(False)` beim Bild-/Log-Laden).

### 2.5 Anwender-Handbuch (`gui/help.py`, `handbuch.md`)

Ein **Handbuch für den Anwender**, angezeigt **im Programm**: links die
Kapitelliste, rechts der Text. Der Inhalt steht in **`handbuch.md` neben dem
Programm** — also dort, wo auch `config.yaml` liegt. Bewusst **eine** Datei und
keine Kopie im Paket: der Nutzer soll sie mit jedem Texteditor lesen und
ergänzen können, und zwei Kopien wären zwei Wahrheiten. Gesucht wird sie zuerst
im Arbeitsverzeichnis, dann im Programmordner; fehlt sie, zeigt das Fenster
einen Hinweis mit dem erwarteten Pfad statt einer Ausnahme.

- **Renderer** (`parse`/`parse_inline`): kein allgemeiner Markdown-Parser,
  sondern genau der Umfang, den das Handbuch braucht — Überschriften (`#`–`###`)
  mit optionaler Anker-ID `{#name}`, Absätze, Aufzählungen (eine Unterebene),
  Codeblöcke sowie inline `**fett**`, `` `code` `` und `[Text](ziel)`. **Keine
  Tabellen** (im Handbuch deshalb Aufzählungen), keine Bilder, keine
  verschachtelte Auszeichnung — `**` in einer Link-Beschriftung wird entfernt,
  damit keine rohen Sternchen stehen bleiben.
- Mehrzeilige Absätze und Aufzählungspunkte werden **erst zusammengefügt und
  dann** ausgezeichnet, sonst zerreißt ein `**fett**`, das im Quelltext über den
  Zeilenumbruch reicht.
- **Darstellung**: ein `tk.Text` (`state="disabled"`). Je Block eine Tk-Marke
  (Sprungziel), je Blocktyp/Span ein Tag; Farben, Schriften und Abstände der Tags
  kommen aus der `Palette` (`apply_palette`, deshalb folgt ein offenes Fenster
  dem Themenwechsel ohne Neuaufbau).
- **Anker sind der Vertrag zur Oberfläche**: das „?" im Titel von Abschnitt N
  springt zu `abschnitt-N`. Ein Test prüft, dass es diesen Anker für alle zehn
  Abschnitte gibt, und dass jeder interne Verweis ein existierendes Ziel hat.
- **Verweise**: `#anker` springt im Handbuch, alles andere geht an
  `webbrowser.open`.
- **Kapitelliste**: alle `##`-Überschriften. Beim Scrollen wird das Kapitel
  hervorgehoben, das **oben** steht — am unteren Anschlag jedoch das der
  **letzten** Zeile, weil die letzten Kapitel kürzer sind als das Fenster und
  oben sonst für immer das vorletzte stünde.
- **Kontexthilfe**: `sections.add_section_help(frame, command)` hängt das „?" an
  den Abschnittstitel; es funktioniert für beide Bauweisen (LabelFrame mit `text`
  bekommt dafür ein `labelwidget`, `required_section` hat schon eins). `app.py`
  hängt es zentral über `self._sections` an alle zehn Rahmen — kein
  Abschnitts-Konstruktor weiß davon.
- Das Fenster ist **nicht modal** (man soll beim Ausfüllen nachlesen können), es
  gibt immer nur eines, es lädt bei `<FocusIn>` nach einer Änderung der Datei neu
  (mtime), und es übernimmt die **Menüleiste des Hauptfensters** — sonst zeigt
  macOS über einem Fenster ohne eigenes Menü die Standardleiste von Tk (mit
  „Python"-Menü und Tk-Hilfeeinträgen).

---

## 3. Config-Datenmodell (`config.py`)

YAML-Datei `config.yaml`. Dataclass-Struktur:

```python
@dataclass
class SenderConfig:
    callsign: str            # "DN5MT"
    name: str                # "Axel Tüner"
    street: str              # "Wilhelmstr. 76"
    zip: str                 # "72124"
    city: str                # "Pliezhausen"
    country: str             # "Deutschland"
    locator: str             # "JN48OM"
    dok: str                 # "P31"
    waz: str                 # "14"  (auf der Karte als "CQ-Zone")
    itu: str                 # "28"
    # Funk-Ausrüstung: erscheint dynamisch auf der Karte (RIG/ANT/PWR-Tabelle),
    # nur wenn gefüllt. Leer -> keine Spalte.
    receiver: str = ""       # Empfänger/TRX, z.B. "IC-7300"
    antenna: str = ""        # Antenne, z.B. "Dipol 2×20 m"
    power: str = ""          # Sendeleistung, z.B. "100 W"

@dataclass
class LookupConfig:
    program_id: str = "qslcards"   # HamQTH verlangt prg-Kennung
    address_export: bool = False   # Adress-/Label-Export erzeugen (alle Stationen)
    # Hinweis: KEIN `lookup_addresses` mehr — der Lookup läuft automatisch beim
    # Log-Laden, sobald Zugangsdaten eingetragen sind (siehe §6).
    # Die Zugangsdaten selbst stehen bewusst NICHT hier, sondern in
    # `lookup.LookupCredentials` (nur zur Laufzeit) — `config.save` schriebe sie
    # sonst im Klartext in die config.yaml. `program_id` bleibt die einzige
    # konfigurierte Angabe; die GUI kopiert sie in die Credentials.

@dataclass
class GenerationConfig:
    card_mode: str = "per_qso"         # "per_qso" | "per_station"
    # Zustellwege in Prioritätsreihenfolge (oben = höchste Priorität):
    #   B=Büro (inkl. Manager), D=Direkt, Q=eQSL, L=LOTW.
    via_priority: list[str] = ["B","D","Q","L"]
    via_cut: int = 2                   # Trennlinie: die ersten `via_cut` Wege sind
                                       #   aktiv (werden gedruckt), der Rest nicht.
    default_via: str = "B"             # Fallback, wenn der Lookup nichts/"?" liefert
                                       #   -> NUR hier in der Config, kein GUI-Widget
    page_orientation: str = "landscape" # A6, siehe CARD_LAYOUT.md
    print_mode: str = "duplex"         # "duplex" (eine PDF) | "separate" (2 PDFs)
    # Bogendruck (§7), quer zum Druckmodus:
    #   "single" -> eine Karte je PDF-Seite (A6 quer)
    #   "a4_4up" -> vier Karten je PDF-Seite (A4 quer, 2×2) + Schnittlinien
    sheet_mode: str = "single"
    # Druckrand (§7): Ränder in mm je Kante, nur wirksam wenn eingeschaltet.
    #   Gilt IMMER je Karte — im Bogen also je Zelle des 2×2-Rasters.
    print_margin_enabled: bool = False # „Erweiterte Einstellungen" in Abschnitt 9
    print_margin_top: float = 0.0      # 0 .. PRINT_MARGIN_MAX (15 mm)
    print_margin_bottom: float = 0.0
    print_margin_left: float = 0.0
    print_margin_right: float = 0.0
    static_footer: str = "TNX FR NICE CONTACT, 73"
    remarks: str = ""                  # globaler REMARKS-Text (alle Karten); leer
                                       #   -> kein Kasten. Max. 80 Zeichen (GUI).
    qsl_mark: str = "none"             # "pse" | "tnx" | "none" (global)
    confirm_mark: str = "none"         # "none" | "qso" | "swl" (global)
    # Hinweis: KEIN `portable_mark` mehr — die Portabel-Kennung steht im
    # Rufzeichen des Absenders (`F/DL0MT/P`), siehe §2.1 Abschnitt 3.
    # Hinweis: KEIN `via_filter`/`include_missing_via` mehr — die Via steht nie im
    # Log, sie wird immer per Lookup bestimmt (§6).

@dataclass
class AppearanceConfig:
    theme: str = "system"        # "system" (folgt dem OS) | "light" | "dark"
                                 #   Menü „Ansicht > Farbthema" schreibt hierher.

@dataclass
class RecentConfig:              # Menü „Datei > Zuletzt verwendet", neueste zuerst
    logs: list[str] = []         # max. MAX_RECENT (8) Einträge
    images: list[str] = []

@dataclass
class AppConfig:
    sender: SenderConfig
    lookup: LookupConfig
    generation: GenerationConfig
    appearance: AppearanceConfig
    recent: RecentConfig
```

`load(path) -> AppConfig` / `save(config, path)`. Fehlende Felder → Defaults.
`recent` wird **defensiv** geladen (nur nicht-leere Strings, auf `MAX_RECENT`
gekürzt) — die Listen schreibt zwar die App, sie können aber von Hand editiert
worden sein. `push_recent(entries, path)` setzt einen Pfad duplikatfrei nach vorn.

`save` schreibt `config.CONFIG_HEADER` als erste Zeile („bitte nicht von Hand
bearbeiten"). Die Warnung steht dort und nicht bloß in `config.example.yaml`,
weil `yaml.safe_dump` die Datei beim Auto-Save komplett neu schreibt — ein nur in
der Vorlage stehender Hinweis wäre nach der ersten Änderung im Programm weg.
`config.example.yaml` ist folgerichtig **byteweise** das, was
`save(AppConfig())` erzeugt (leer, ohne Beispieldaten); ein Test hält das fest.

> **Achtung beim Auto-Save:** `App._gather_config()` baut die Config aus den
> Widgets. Sechs Werte haben **keins** und müssen aus der Basis-Config übernommen
> werden, sonst löscht das nächste automatische Speichern sie:
> `appearance.theme` und `recent` (beide über das Menü bedient) sowie
> `generation.default_via`, `generation.page_orientation`,
> `generation.static_footer` und `lookup.program_id`. Die letzten vier sind
> bewusst gar nicht bedienbar — sie gelten als Programmkonstanten, die zufällig
> in der Config liegen (mit dem Nutzer so entschieden). Wer einen davon
> einstellbar machen will, braucht ein Widget; „einfach in der Datei ändern"
> widerspricht der Kopfzeile.

---

## 4. Logbuch-Parser (`logbook/`)

Zwei Formate, ein Datenmodell: ADIF aus dem Alltags-Logbuch (§4.1–4.4) und
**Cabrillo** aus dem Contest (§4.5). Beide liefern `list[QSO]`
(`logbook/models.py`); alles danach — Lookup, Builder, Karten, PDF — kennt den
Unterschied nicht mehr. Welches Format vorliegt, entscheidet der Dispatcher am
**Inhalt** (§4.6).

Für beide gilt bewusst: **kein** externes Package, eigener getesteter Parser.

```
logbook/
  __init__.py   # Formaterkennung + Dispatcher (die öffentliche API)
  models.py     # QSO
  adif.py       # §4.1–4.4
  cabrillo.py   # §4.5
```

### 4.1 ADIF: Formatregeln
- ADIF besteht aus **Feld-Specifiern** `<NAME:LÄNGE>WERT` oder
  `<NAME:LÄNGE:TYP>WERT`. `LÄNGE` = Byte-Länge des Werts.
- Feldnamen sind **case-insensitive** → intern immer `lower()`.
- `<EOH>` beendet den optionalen Header (alles davor ignorieren).
- `<EOR>` beendet einen QSO-Record.
- Werte können beliebige Zeichen (inkl. Zeilenumbrüche) enthalten; die Länge
  ist maßgeblich, **nicht** Whitespace/Zeilenenden.
- Text außerhalb von `<...>`-Tags nach `<EOH>` bis zum ersten `<` gehört nicht
  zum Wert und wird verworfen.

### 4.2 ADIF: Algorithmus (Tokenizer)
1. Optional: falls `<EOH>` (case-insensitive) vorkommt, ab dort weiterarbeiten.
2. Cursor durch den String. An jedem `<`:
   - bis `>` lesen → Tag-Inhalt.
   - Tag-Inhalt an `:` splitten → `name`, optional `length`, optional `type`.
   - `name` in `lower()`.
   - Ist `name == "eor"` → aktuellen Record abschließen, neuen beginnen.
   - Ist `name == "eoh"` → ignorieren/überspringen.
   - Sonst: `length` parsen, exakt `length` Bytes ab hinter `>` als **Wert**
     lesen (Vorsicht: Byte- vs. Zeichenlänge; ADIF ist byteorientiert — bei
     UTF-8 auf Bytes rechnen, dann dekodieren). Wert im Record unter `name` ablegen.
     Cursor hinter den Wert setzen.
   - **Robustheit gegen zu groß angegebene Längen**: Manche Logger (z.B. HAMRS)
     zählen kurze Werte falsch und beziehen Zeilenumbruch bzw. den Beginn des
     nächsten Tags mit ein (etwa `<RST_SENT:3>0` für den Wert „0"). Enthält der
     nach `length` gelesene Wert ein `<`, markiert das den Start des nächsten
     Feld-Specifiers → Wert dort abschneiden **und den Cursor dorthin
     zurücksetzen**, damit das folgende Tag nicht verschluckt wird. Bei korrekt
     angegebenen Längen ändert das nichts.
3. Am Ende: falls Record nicht leer, ebenfalls übernehmen (toleranter Umgang mit
   fehlendem letzten `<EOR>`).

### 4.3 ADIF: Mapping Record → `QSO`
| ADIF-Feld        | QSO-Attribut     | Hinweis                                    |
|------------------|------------------|--------------------------------------------|
| `call`           | `call`           | Pflicht; Record ohne `call` überspringen   |
| `qso_date`       | `qso_date`       | "YYYYMMDD"                                  |
| `time_on`        | `time_on`        | "HHMM" oder "HHMMSS"                        |
| `band`           | `band`           |                                            |
| `freq`           | `freq`           | MHz-String                                 |
| `mode`           | `mode`           | ggf. mit `submode` kombinieren             |
| `rst_sent`       | `rst_sent`       | **→ Signalrapport auf der Karte**          |
| `rst_rcvd`       | `rst_rcvd`       | nur informativ                             |
| `qsl_sent_via`   | `qsl_sent_via`   | nur informativ (im Log i.d.R. **nicht** vorhanden; Via kommt aus dem Lookup, §6) |
| `qsl_via`        | `qsl_via`        | nur informativ; der Manager fürs Feld „Via:" kommt aus dem **Lookup**, nicht aus dem Log |
| `name`           | `name`           | falls vorhanden                            |
| `gridsquare`     | `gridsquare`     |                                            |
| `qth`            | `qth`            | Ort der Gegenstation (falls vorhanden)     |
| `country`        | `country`        | Land der Gegenstation (falls vorhanden)    |
| (alle)           | `raw`            | vollständiger Roh-Record                   |

Die Felder `qsl_sent_via`/`qsl_via` werden weiterhin geparst (Rohdaten), steuern
aber **nichts** mehr: Versandart **und** Manager werden je Station per Lookup
bestimmt (§6). Das Testlog enthält diese Felder ohnehin nicht.

### 4.4 ADIF: Testfälle (mind.)
- Header vorhanden / fehlt.
- Groß-/Kleinschreibung gemischt (`<Call:5>`, `<CALL:5>`).
- Typ-Suffix (`<freq:6:N>14.074`).
- Zeilenumbruch im Wert (z.B. Kommentarfeld).
- Fehlendes letztes `<EOR>`.
- Record ohne `call` → übersprungen.
- Mehrere QSOs mit demselben Call (für Gruppierung).

### 4.5 Cabrillo (`logbook/cabrillo.py`)

Contest-Logs: die Datei, die man beim Veranstalter abgibt. Zeilenorientiert,
Version 3.0 (WWROF).

#### 4.5.1 Formatregeln
- Kopfzeilen `TAG: wert`, erste Zeile `START-OF-LOG: 3.0`, letzte `END-OF-LOG:`.
  Die **Reihenfolge ist beliebig** — `CALLSIGN:` darf hinter den QSO-Zeilen
  stehen. Mehrfach erlaubt: `ADDRESS`, `CLUB`, `OPERATORS`, `SOAPBOX`.
- QSO-Zeilen:

  ```
  QSO: freq  mo date       time call          rst exch   call          rst exch   t
  QSO:  3799 PH 2000-11-26 0711 N6TW          59  03     JT1Z          59  23     0
  ```

- **Die Spaltenpositionen sind nicht verbindlich.** Die Spezifikation zeigt sie
  zwar, erklärt in den Notes aber ausdrücklich, dass jedes Leerzeichen und jeder
  Tabulator als Trenner gilt. Lange Rufzeichen (`DL0MT/P`) sprengen die Felder
  ohnehin → **tokenweise** zerlegen, nie nach Spalten.
- Datum `yyyy-mm-dd`, Zeit `nnnn` (UTC), Rufzeichen nur `A-Z`, `0-9`, `/`.
- `t` = Transmitter-ID, ein Zeichen `0`/`1`, nur bei Multi-TX-Kategorien.
- `X-QSO:` sind vom Contest gestrichene Verbindungen. Sie werden **mit**
  importiert (das QSO hat stattgefunden, die Gegenstation bekommt ihre Karte;
  gestrichen wird meist wegen eines Regelverstoßes auf der eigenen Seite) und in
  `raw["cabrillo_x_qso"]` markiert. Mit dem Nutzer so entschieden.
- **`CALLSIGN`, `GRID-LOCATOR`, `NAME`, `ADDRESS*` sind Absenderdaten.** Sie
  kommen laut §5.3 immer aus der Config. `CALLSIGN` wird ausschließlich intern
  zur Zeilenzerlegung benutzt; beide landen nur informativ in `raw`
  (`station_callsign`/`my_gridsquare`). `GRID-LOCATOR` darf **niemals** in
  `qso.gridsquare` — das ist der Locator der *Gegen*station.

#### 4.5.2 Algorithmus (zwei Durchläufe)
1. Kopfzeilen sammeln (eigener Durchlauf, weil die Reihenfolge beliebig ist).
2. Je `QSO:`/`X-QSO:`-Zeile zerlegen und normalisieren.

Die Zahl der Austauschfelder hängt am Contest (2 bei VHF-Grid-Contests, 5 bei
ARRL-SS) und ein Rapport fehlt in vielen Contests ganz. Über alle geprüften
Templates gelten aber drei Invarianten: **beide Seiten haben gleich viele
Felder**, das **erste Feld je Seite ist das Rufzeichen**, und ein Rapport steht —
falls vorhanden — **direkt dahinter**. Darauf baut die Zerlegung:

1. **Das Datum ist der Anker**, nicht ein fester Index: davor stehen genau
   Frequenz und Modus. Damit ist die Zerlegung immun gegen Tabs, mehrfache
   Leerzeichen und führende Ausrichtung.
2. **Transmitter-ID nur abtrennen, wenn die Feldzahl dadurch gerade wird.** Sonst
   verschwände bei einem Contest mit Seriennummern die letzte Nummer — 9A-CW
   schreibt `… 599 001 9A2UE 599 101`, und `101` ist keine Transmitter-ID.
3. **Trennstelle per Score**, nicht blind die Mitte: Symmetrie (+4), rechts
   beginnt ein Rufzeichen-Muster und *kein* Locator (+3), links steht das eigene
   Rufzeichen (+1), die Austauschfelder beider Seiten passen paarweise in der
   Form zusammen (0–2). Im Normalfall gewinnt ohnehin die Mitte; das Scoring
   rettet zusätzlich asymmetrische Exoten, statt die Zeile zu verwerfen.
   Das eigene Rufzeichen ist bewusst nur ein *Signal*, keine Bedingung —
   Portabel-Zusätze und Multi-Op-Logs machen einen harten Vergleich unbrauchbar.
4. **Rapport rein positionell** (`felder[1]`), validiert gegen `[1-5][1-9][1-9]?`
   plus die CW-Kurzform `5NN`. Genau diese Strenge ist der Trick: Seriennummern
   wie `001` (R=0) und `101` (S=0) fallen automatisch durch, ebenso `JEFF`,
   `FN12fr` oder `3`. **Fehlt der Rapport, bleibt er leer** — ein erfundenes „59"
   wäre eine falsche Bestätigung auf einer QSL-Karte.

Der Locator-Ausschluss in Schritt 3 ist nötig, weil ein sechsstelliger Locator
wie `FN12FR` das Rufzeichen-Muster erfüllt (Präfix `FN1`, Ziffer `2`, Suffix `FR`).

#### 4.5.3 Normalisierung nach `QSO`
`cards/builder.py` diktiert die Formate (`_split_date` schneidet Positionen,
`_format_freq` macht `float(...)`) — also normalisieren, nicht durchreichen:

| Cabrillo | QSO | Regel |
|----------|-----|-------|
| `2000-11-26` | `qso_date` | → `"20001126"` |
| `0711` | `time_on` | → `"0711"` |
| Frequenzfeld | `freq` | MHz-String, siehe unten |
| (aus `freq`) | `band` | über `BAND_EDGES`; außerhalb aller Bänder → leer |
| `CW/PH/FM/RY/DG` | `mode` | `MODE_MAP`: PH→SSB, RY→RTTY, DG→DIGI; Unbekanntes durchgereicht |
| `felder[1]` je Seite | `rst_sent`/`rst_rcvd` | nur bei gültigem Rapportmuster |
| Empfangs-Austausch | `gridsquare` | nur wenn er **genau einen** Locator enthält |
| — | `qsl_sent_via`, `qsl_via`, `name`, `qth`, `country` | immer leer: Cabrillo kennt keine Versandart (§6) |

Die Frequenz in drei Regeln, **in dieser Reihenfolge**:
1. **Bandbezeichner-Tabelle zuerst** (`1.2G`→1240, `2.3G`→2300, `10G`→10000, dazu
   die real vorkommenden Kurzformen ohne `G` — das ARRL-UHF-Template schreibt
   selbst `QSO: 1.2 PH …`). `2.3` ist 2,3 GHz und keine 2,3-MHz-Frequenz.
2. **Zahl ≥ 1000 → kHz** (`3799`→`"3.799"`, `14000`→`"14"`). Die Schwelle ist
   sauber: die niedrigste kHz-Angabe auf Kurzwelle ist 1800, der höchste
   MHz-Bandbezeichner 902.
3. **Sonst leer** — `LIGHT` hat keine Frequenz. Nichts raten; das Rohtoken bleibt
   in `raw["cabrillo_freq"]`.

`raw` trägt ADIF-Feldnamen, wo es sie gibt, plus `station_callsign`,
`my_gridsquare`, `operator`, `contest_id` und die `cabrillo_*`-Rohwerte
(`freq`, `mode`, `exch_sent`, `exch_rcvd`, `transmitter`, `x_qso`, `line`).

**Bewusst verworfen:** den Austausch auf `name`/`qth` zu mappen (NAQP schickt
`BOB CA`). Das erfordert Contest-Wissen und produziert bei jedem anderen Contest
Müll — bei ARRL-SS würde `A` zum Namen. Name und QTH liefert der Lookup.

#### 4.5.4 Testfälle (mind.)
- Kopfdaten landen **nicht** im QSO (`CALLSIGN`/`GRID-LOCATOR`/`NAME`/`ADDRESS`
  nur in `raw`) — der wichtigste Test des Moduls.
- `CALLSIGN:` hinter den QSO-Zeilen; Datei ganz ohne Kopf; mehrfache Tags.
- Je ein Beispiel aus den Contest-Templates: CQ-WW (3 Felder mit Rapport),
  Transmitter-ID, 9A-CW (`101` bleibt Seriennummer), NAQP (kein Rapport, mit
  `t`), EU-SPRINT (`001` ist kein Rapport), ARRL-SS (5 Felder), VHF-Grid
  (Locator der Gegenstation), WW-Digi, RSGB-IOTA, Portabel-Zusatz in der Zeile,
  Tabs statt Leerzeichen, sechsstelliger Locator.
- Normalisierung: Datum/Zeit, Frequenztabelle, Bandableitung, Modus-Mapping.
- **Integrationstest gegen den Builder**: aus einem Cabrillo-QSO wird eine
  korrekte Kartenzeile (Datum gesplittet, `freq_mhz` gerechnet).
- Robustheit: `X-QSO:` importiert und markiert; kaputte Zeile übersprungen, die
  folgende gültige geparst; nur Kopf → leere Liste; `\r\n`.

### 4.6 Formaterkennung und Fehlerverhalten (`logbook/__init__.py`)

`detect_format(text)` entscheidet am **Inhalt**, nicht an der Dateiendung
(`.log`/`.txt` sind mehrdeutig), in dieser Reihenfolge:
1. `START-OF-LOG:` → Cabrillo (eindeutig).
2. `<EOH>`/`<EOR>`/`<CALL:n>` → ADIF. Vor der nackten `QSO:`-Zeile, weil ein
   ADIF-Kommentarwert durchaus „QSO:" enthalten kann.
3. `QSO:`/`X-QSO:` am Zeilenanfang → kopfloses Cabrillo.
4. sonst nichts.

**Die Format-Parser werfen nie, der Dispatcher schon.** `adif.parse_text` und
`cabrillo.parse_text` sind reine Formatumsetzer: eine unbrauchbare Zeile wird
übersprungen und geloggt, das Ergebnis ist notfalls `[]`. Erst der Dispatcher
weiß, dass ein *Anwender* eine *Datei* ausgewählt hat — nur dort ist „leer" ein
Fehler statt eines Ergebnisses (`LogFormatError`, siehe §8).

---

## 5. Kartenaufbau (`cards/builder.py`)

### 5.1 Datenmodelle (`cards/models.py`)
```python
@dataclass
class CardRow:                 # eine Tabellenzeile der Rückseite
    date_d: str; date_m: str; date_y: str
    utc: str
    freq_mhz: str
    mode: str
    rst_sent: str

@dataclass
class Card:
    recipient_call: str
    via_text: str              # Feld "Via:" (Manager-Callsign aus dem Lookup, oder leer)
    via_routes: tuple[str, ...] # akzeptierte Zustellwege der Station (B/D/Q/L)
    rows: list[CardRow]        # 1..N (per_station kann mehrere haben)
    qsl_mark: str = "none"     # global aus config: "pse" | "tnx" | "none"
    confirm_mark: str = "none" # global aus config: "none" | "qso" | "swl"
    remarks: str = ""          # REMARKS-Text dieser Karte (leer -> kein Kasten);
                               #   Default = config.remarks, je Karte überschreibbar
    remarks_manual: bool = False  # True, sobald in der Vorschau manuell gesetzt
                               #   (schützt vor Überschreiben durch den globalen Text)
    via_override: str | None = None  # manuell erzwungener Weg (Vorschau), respektiert
                               #   weiterhin die Trennlinie
    # Empfängeradresse nur bei Bedarf gefüllt (Export), NICHT auf der Karte:
    recipient: LookupResult | None = None
```

Der tatsächlich zu druckende Weg ist **nicht** direkt am Card, sondern wird über
`effective_via(card, active_priority)` ermittelt (höchstpriorisierter aktiver Weg
aus `via_routes`, ggf. per `via_override` erzwungen; `None` = nicht drucken).

### 5.2 Ablauf `build_cards(qsos, config, lookups=None)`
1. **Kein Via-Filter!** `build_cards` behält **alle** QSOs. Die Via kommt nicht
   aus dem Log, sondern aus dem Lookup (§6): `lookups` ist eine Map
   `CALL -> LookupResult`. Je Karte wird gesetzt:
   - `via_routes = accepted_routes(lookups[call], config.default_via)` (Menge der
     akzeptierten Wege B/D/Q/L; leer → `(default_via,)`; siehe §6).
   - `via_text = extract_manager_callsign(lookups[call].manager)` (genau **ein**
     Manager-Rufzeichen oder leer) → Feld „Via:".
   - `recipient = lookups[call]` (Adresse, nur für den Export; nicht auf der Karte).
   Fehlt `lookups` oder der Eintrag → `via_routes = (default_via,)`, `via_text` leer.
   Das **Drucken/Abwählen** ermittelt die GUI über `effective_via` anhand der
   Priorität + Trennlinie (Wege unter der Linie standardmäßig abgewählt), nicht der
   Builder.
2. **Datum splitten**: `qso_date` "YYYYMMDD" → `date_y=YY` (2-stellig, wie
   Referenz „D M Y"), `date_m=MM`, `date_d=DD`. (Reihenfolge auf der Karte: D M Y.)
3. **UTC**: `time_on` → "HH:MM" (Sekunden abschneiden, sofern vorhanden).
4. **freq_mhz**: aus `freq`; fehlt es, aus `band` ableiten (optionale Tabelle).
5. **Gruppieren**:
   - `per_qso`: eine `Card` je QSO, `rows` mit genau einer Zeile.
   - `per_station`: QSOs je (Call, Via) sortiert nach Datum/Zeit, dann in Blöcke
     aufgeteilt. Die Blockgröße hängt vom Remarks-Zustand ab (siehe
     `CARD_LAYOUT.md`): **ohne** globalen Remarks bis `MAX_ROWS_PLAIN = 6` QSOs je
     Karte, **mit** globalem Remarks bis `MAX_ROWS_WITH_REMARKS = 3` (der
     Remarks-Kasten braucht Platz); mehr → Folge-Karte(n).
6. **Sortierung**: Karten deterministisch nach `recipient_call`, dann Datum.
7. **Markierungen (global, manuell)**: jede Karte erhält unverändert die
   Werte aus der Config:
   - `card.qsl_mark = config.qsl_mark` (`"pse"` | `"tnx"` | `"none"`).
   - `card.confirm_mark = config.confirm_mark` (`"none"` | `"qso"` | `"swl"`).
   - `card.remarks = config.remarks` (globaler REMARKS-Text; je Karte in der
     Vorschau überschreibbar).
   Es gibt **keine** automatische Ableitung aus dem Log; der Nutzer wählt die
   Markierungen in der GUI/Config, sie gelten für **alle** Karten gleich.

Hilfsfunktionen fürs Remarks-Splitting (rein, ohne Seiteneffekte):
- `regroup_card_by_remarks(card)`: teilt die Zeilen **einer** Karte in Blöcke je
  nach Remarks-Zustand (3 mit / 6 ohne Remarks); idempotent, kein Merge.
- `normalize_station_cards(cards)`: normalisiert die Karten **einer** Station —
  Karten mit Remarks bleiben eigenständig, aufeinanderfolgende Karten ohne
  Remarks werden zusammengeführt (Merge). Nutzt die Vorschau bei einer
  Remarks-Änderung, damit ein Remarks je Karte unabhängig gesetzt werden kann.

---

## 6. Lookups (`lookup/`) — Herzstück: Via + Manager + Adresse

> Vor Implementierung gegen die **aktuelle** Doku prüfen; Endpunkte können sich
> ändern. Netz-/Auth-Fehler sind **nie** fatal (loggen, Feld leer, weiter).

**Warum zentral:** Das Log enthält **keine** Versandart — weder ADIF noch
Cabrillo kennen sie. Der Lookup ist der
einzige Weg, je Station herauszufinden, **wie** die QSL verschickt wird (Büro,
Direkt, Manager) bzw. dass die Station **elektronisch** quittiert und keine Karte
braucht. Er liefert außerdem den **QSL-Manager** (für Karte + Tabelle) und die
**Adresse** (für den Export).

### 6.1 `LookupResult` (`lookup/base.py`)
Neben `call`, `name`, `street`, `zip`, `city`, `country`, `grid`, `source`
zusätzlich die QSL-Routing-Felder:
- `manager: str | None` — QSL-Manager/Route (HamQTH `qsl_via`, QRZ `qslmgr`).
- `accepts_bureau: str | None` — HamQTH `qsl` („Y"/„N"/„?").
- `accepts_direct: str | None` — HamQTH `qsldirect` („Y"/„N"/„?").
- `lotw: str | None`, `eqsl: str | None` — HamQTH `lotw`/`eqsl` („Y"/„N"/„?").

### 6.1a `LookupCredentials` (`lookup/base.py`)
```python
@dataclass
class LookupCredentials:
    hamqth_user: str = ""
    hamqth_pass: str = ""
    qrz_user: str = ""
    qrz_pass: str = ""
    program_id: str = "qslcards"   # füllt die GUI aus LookupConfig.program_id
```
Die Zugangsdaten leben **ausschließlich zur Laufzeit**: sie sind kein Teil von
`AppConfig`, werden nie in die `config.yaml` geschrieben und sind bei jedem
Programmstart wieder leer (§2.6). `has_lookup_credentials`, `build_lookup` und
`lookup_calls` nehmen dieses Objekt entgegen — `program_id` reist darin mit,
damit es bei genau **einem** Parameter bleibt. In der GUI baut
`App._lookup_credentials()` es aus den Widgets von Abschnitt 6 plus
`base_config.lookup.program_id`.

### 6.2 Wege-Ableitung `accepted_routes(result, default_via="B") -> tuple[str,...]`
Der Lookup liefert je Station die **Menge** akzeptierter Zustellwege (kanonisch
geordnet B, D, Q, L) — nicht einen einzelnen Code:
- **B** (Büro) wenn `accepts_bureau == "Y"` **oder** ein echtes Manager-Rufzeichen
  hinterlegt ist (`extract_manager_callsign(manager)` liefert eins). Der Manager
  zählt als Büro-Weg; sein Callsign steht dann im Feld „Via:". Reiner Routing-
  Freitext ohne Rufzeichen (z.B. „LoTW") zählt **nicht** als Büro.
- **D** (Direkt) wenn `accepts_direct == "Y"`.
- **Q** (eQSL) wenn `eqsl == "Y"`.
- **L** (LOTW) wenn `lotw == "Y"`.
- leere Menge (kein Treffer/nur „?"/„N"/keine Credentials) → `(default_via,)`
  (Default „B"), damit die Station druckbar bleibt.

**Welcher Weg gedruckt wird**, entscheidet erst die GUI-Priorität + Trennlinie:
`resolve_route(accepted, active_priority)` liefert den ersten Weg aus
`active_priority` (Reihenfolge = Priorität, nur Wege über der Linie), der in der
akzeptierten Menge liegt; gibt es keinen, wird die Karte **nicht** gedruckt
(`None`). `active_via_priority(priority, cut)` sind die aktiven Wege (die ersten
`cut` der normalisierten Prioritätsliste). `effective_via(card, active_priority)`
kapselt das inkl. `via_override` und ist die **einzige** Quelle der Wahrheit für
Vorschau **und** Export.

### 6.3 HamQTH (primär, kostenlos — kostenloses Konto nötig)
> `USER`/`PASS` kommen aus `LookupCredentials` (§6.1a), nie aus der Config.
- Session holen: `https://www.hamqth.com/xml.php?u=USER&p=PASS`
  → XML mit `<session_id>`. Session ~1 Stunde gültig.
- Abfrage: `https://www.hamqth.com/xml.php?id=SESSION&callsign=CALL&prg=PROGRAMID`
  → XML (Namespace `https://www.hamqth.com`, daher namespace-agnostisch parsen):
  `nick`/`adr_name`, `adr_street1`, `adr_city`, `adr_zip`, `country`/`adr_country`,
  `grid`, sowie fürs Routing `qsl_via`, `qsl`, `qsldirect`, `lotw`, `eqsl`.
- Bei „session does not exist / expired" → neu anmelden, einmal wiederholen.

### 6.4 QRZ (optional, best effort)
- Session: `https://xmldata.qrz.com/xml/current/?username=USER;password=PASS;agent=qslcards1.0`
  → `<Key>`. Query-Parameter mit `;` (nicht `&`) trennen; Namespace beachten.
- Abfrage: `https://xmldata.qrz.com/xml/current/?s=KEY;callsign=CALL`.
- Liefert Adresse + Manager (`qslmgr`), aber **keine** Büro/Direkt/LoTW/eQSL-Flags
  → diese bleiben `None`, solche Stationen landen (ohne Manager) auf `default_via`.
- **Ohne bezahltes XML-Abo** sind Felder oft leer/limitiert → „best effort".

### 6.5 Cache (`lookup/cache.py`)
- JSON-Datei `lookup_cache.json`: `{ "CALL": {result, queried_at}, ... }`.
- Vor jeder API-Abfrage Cache prüfen; Ergebnisse (auch negative) cachen.
- Cache-Alter optional beachten (Default 180 Tage), sonst dauerhaft.
- **Ausnahme:** Solange ein Provider die Anmeldung abgelehnt hat (§6.7), schreibt
  `ChainedLookup` **nichts** (`degraded()`). Sonst stünde nach einem Lauf mit
  falschem Passwort für jede Station ein negativer Eintrag in der Datei, und
  selbst mit korrigierten Zugangsdaten fände der nächste Start nichts mehr.
  Gelesen wird weiter — alte Treffer bleiben gültig.

### 6.6 Wann/wie wird gelookt?
- **Automatisch beim Log-Laden**, für **alle** Stationen (eindeutige Rufzeichen),
  im Hintergrund-Thread. Kein `lookup_addresses`-Schalter mehr.
- Läuft nur, wenn HamQTH- **oder** QRZ-Zugangsdaten eingetragen sind. Ohne sie:
  keine Netzcalls, alle Via = `default_via`, Adressen leer. Da sie nicht
  gespeichert werden (§6.1a), gilt das nach jedem Start erneut, bis der Nutzer
  sie eingibt.
- Manueller **„Neu abrufen"**-Button holt fehlende/abgebrochene Stationen nach.
- **Adresse**: wird für alle nachgeschlagenen Stationen geholt und (wenn
  `address_export`) für **alle** exportiert — sie steht **nicht** auf der Karte.

### 6.7 Abgelehnte Zugangsdaten
Lehnt ein Anbieter die Anmeldung ab, sähe der Nutzer sonst nur „0/N Stationen
gefunden" und die Meldung stünde allein im Log. Deshalb:
- Die Clients melden das über `on_auth_error(meldung)` und merken es sich in
  `auth_failed` — **danach kein weiterer Anmeldeversuch** (vorher klopfte jedes
  Rufzeichen neu an). Wichtig: nur eine **Antwort des Servers**, die den Login
  ablehnt, zählt; ein Netzfehler wirft und landet in `lookup()`, er darf nicht
  als falsches Passwort durchgehen.
- `build_lookup`/`lookup_calls` reichen das als `auth_error_cb(anbieter, meldung)`
  nach oben (Anbietername aus `PROVIDER_HAMQTH`/`PROVIDER_QRZ`).
- Die GUI sammelt **je Anbieter die erste** Meldung (sonst stünde sie einmal pro
  Station da), zeigt **ein** Hinweisfenster, setzt die Statuszeile auf `error`,
  scrollt zu Abschnitt 6 und umrandet dessen Feldpaar rot
  (`LookupSection.mark_auth_failed`, Zuordnung in `sections.PROVIDER_FIELDS`).
  Die Markierung verschwindet, sobald das Feld geändert wird — dieselbe Sprache
  wie bei den Pflichtfeldern (§2.4).

---

## 7. PDF-Erzeugung (`pdf/`)

- **Seitengröße**: A6 quer (bzw. A4 quer im Bogenmodus, siehe unten). Querformat
  als Default, da die Referenzkarte querformatig ist. In `geometry.py` umschaltbar.
- **Druckmodus** (`generation.print_mode`), `generate(...) -> list[Path]`:
  - `"duplex"`: **eine** PDF, pro Karte zuerst Vorderseite, dann Rückseite, dann
    `canvas.showPage()`. So entsteht Seite 1=Front(Karte1), 2=Back(Karte1),
    3=Front(Karte2), … → passt für Duplexdruck (lange Kante).
  - `"separate"`: **zwei** PDFs (`…_vorderseiten.pdf`, `…_rueckseiten.pdf`) für
    Drucker ohne beidseitigen Druck: erst alle Vorderseiten drucken, Papier
    umgedreht neu einlegen, dann die Rückseiten. Da **ein** Frontbild für alle
    Karten gilt, sind alle Vorderseiten identisch (keine Umkehrung nötig).
- **Bogendruck** (`generation.sheet_mode`, GUI-Abschnitt 9, `pdf/layout_sheet.py`):
  quer zum Druckmodus, beide Modi funktionieren damit unverändert — nur trägt eine
  „Seite" dann bis zu vier Karten.
  - `"single"`: eine Karte je PDF-Seite (A6 quer), wie bisher.
  - `"a4_4up"`: **vier** Karten je PDF-Seite (A4 quer, 297 × 210 mm). Der Bogen
    wird lückenlos in vier Zellen à **148,5 × 105 mm** geteilt — ein Viertel von
    A4 und damit das echte ISO-A6-Maß. Eine Zelle tritt an die Stelle der
    A6-Seite: `content_box`/`page_layout` arbeiten unverändert darin, `layout_
    sheet` **verschiebt** das Canvas nur auf den Zellen-Ursprung. Gefüllt wird in
    Lesereihenfolge (oben-links, oben-rechts, unten-links, unten-rechts); der
    letzte Bogen darf angebrochen bleiben, leere Zellen bleiben leer.
  - **Schnitt-Hilfslinien**: gestricheltes Kreuz durch die Blattmitte (also exakt
    auf der Zellengrenze), `CUT_LINE_WIDTH = 0,3 pt`, `CUT_GRAY = 0,5`,
    `CUT_DASH = 2/2 mm`. Es läuft über den ganzen **bedruckbaren** Bereich
    (`sheet_printable_box`), nicht nur über die Karten — sonst müsste man das
    letzte Stück schätzen. Gezeichnet wird es **nur auf den Rückseitenbogen**:
    dort liegt an der Schnittkante der 3-mm-Weißraum der Karte, während ein
    Strich über dem randlosen Frontbild bei schiefem Schnitt sichtbar bliebe.
    Auch angebrochene Bögen bekommen das volle Kreuz.
  - **Keine gespiegelte Zellenreihenfolge nötig**: projektbedingt gilt *ein*
    Frontbild für alle Karten, alle vier Vorderseiten eines Bogens sind also
    identisch — egal um welche Kante der Drucker wendet, hinter jeder Rückseite
    liegt dieselbe Vorderseite (gleiche Begründung wie bei `"separate"`).
- **Druckrand** (`generation.print_margin_*`, GUI-Abschnitt 9): Viele Drucker
  drucken nicht bis zur Blattkante und beschneiden sonst den Inhalt. Die vier
  Werte bedeuten „so viel Rand **muss** frei bleiben", und zwar **je Karte** —
  im Bogen also in jeder der vier Zellen. Zwischen zwei Karten steht dadurch der
  doppelte Rand, dessen Mitte die Schnittkante ist; so hat jede geschnittene
  Karte denselben Rand ringsum. (Läge er nur einmal um den ganzen Bogen, hätte
  jede Karte ihn nur auf ihren zwei äußeren Kanten und der Inhalt säße
  außermittig — deshalb wurde diese Variante verworfen.) Das Blatt behält seine
  Größe (`setPageSize` wird nie aufgerufen) — nur die Zeichnung rückt ein:
  1. Rahmen = Seite minus der vier (geclampten) Ränder → `geometry.content_box`;
     „Seite" ist die A6-Seite bzw. im Bogen die Zelle (148,5 × 105 mm).
  2. `scale = min(rahmen_b/PAGE_W, rahmen_h/PAGE_H)` — **ein** Faktor für beide
     Achsen, die Karte wird also nie verzerrt (nur kleiner, Schrift inklusive).
  3. Weil `scale` nur von einer Achse bestimmt wird, bleibt auf der anderen Platz
     übrig. Der wird **nicht** als Rand verschenkt, sondern ins Layout gegeben:
     gezeichnet wird auf einer größeren **virtuellen Seite**
     `page_w = rahmen_b/scale`, `page_h = rahmen_h/scale` (eine davon ist exakt
     `PAGE_W`/`PAGE_H`). Nach `translate`+`scale` füllt die Zeichnung den Rahmen
     exakt → alle vier Ränder stimmen auf den Millimeter.
  4. Mitwachsend sind die schon immer aus `PAGE_W` abgeleiteten Maße (Call-/Via-
     Box, `TABLE_X1`, Remarks-Kasten) plus die **anteilig** verteilten
     Tabellenspalten; der Fußblock (REMARKS + `static_footer`) ist an der
     **Unterkante** verankert. Links/oben verankerte Blöcke (Absender, Station,
     Funk) bleiben, wo sie sind.

  Alles davon liefert `geometry.page_layout(config) -> PageLayout`. Ist der
  Druckrand aus (und kein Bogen), ist das Ergebnis die Identität (`scale=1`,
  virtuelle Seite = A6) und die Ausgabe byteweise dieselbe wie ohne das Feature.
  Im Bogen ohne Druckrand ist die Zelle 0,5 mm breiter als A6 — dieser halbe
  Millimeter fließt über denselben Mechanismus ins Layout. `MAX_ROWS_*` bleibt
  unberührt — senkrechter Überschuss vergrößert nur den Abstand zwischen Tabelle
  und Fuß, die Kartenaufteilung im Builder ändert sich nicht. Ein Deckel
  (`MAX_STRETCH`) begrenzt den elastischen Überschuss bei absurden Randwerten;
  der Rest wird dann zentriert (der Rand ist dort größer als eingestellt).
- **Front** (`layout_front.py`): Frontbild im **Cover-Modus** den ganzen Rahmen
  füllen (kein weißer Rand innerhalb des Rahmens), Seitenverhältnis wahren,
  Überstand beschneiden (Clip), zentriert. Der Rahmen ist `geometry.content_box`
  — ohne Druckrand die volle Seite (im Bogen: die volle Zelle), sonst derselbe
  Rahmen wie die Rückseite, damit beide Seiten deckungsgleich liegen. Mit
  Druckrand hat also auch das Frontbild den weißen Rand ringsum. Das Bild wird auch bei ungleichen
  Rändern **nie verzerrt**.

  > **`drawImage` bekommt den Dateipfad, nie ein `ImageReader`.** ReportLab
  > bildet den Cache-Schlüssel eines `ImageReader` aus einem MD5 über die
  > komplette entpackte Bitmap — bei **jedem** Aufruf. Ein 4096×3072-Foto sind
  > 37,7 MB, die dann je Karte einmal kopiert und einmal gehasht werden:
  > gemessene 119 ms pro Seite statt 4,6 ms. Bei 3525 Karten aus einem
  > Contest-Log ist das der Unterschied zwischen 308 s und 4,6 s; obendrein
  > reicht ReportLab ein JPEG nur über den Pfad unverändert durch, statt es als
  > rohes RGB neu zu komprimieren (22 MB → 6,6 MB). Pillow wird hier nur noch
  > für die Bildmaße gebraucht (Cover-Fit), die je Pfad gecacht werden.
  > Nachweis: `test_front_image_is_passed_as_a_path`. Die *Wirkung* (ein
  > Bild-XObject fürs ganze Dokument) taugt nicht als Test — der Digest ist ja
  > jedes Mal derselbe, das Bild landet auch mit `ImageReader` nur einmal drin.
- **Back** (`layout_back.py`): exakt nach `CARD_LAYOUT.md`. Alle Positionen/
  Größen aus `geometry.py`; die mitwachsenden Maße und die Y-Spiegelung kommen
  aus dem `PageLayout`, den `draw_back` einmal baut und an alle Helfer
  weiterreicht. Der REMARKS-Block (Label + Kasten + Text) wird nur
  gezeichnet, wenn `card.remarks` gesetzt ist (dynamisch); der Footer-Text steht
  immer. Der **Funk-Block** (RIG/ANT/PWR-Tabelle) erscheint nur, wenn mindestens
  eins der Felder `receiver`/`antenna`/`power` gefüllt ist; dann rücken QSL-
  Markierung und QSO-Tabelle nach unten. Das eigene Rufzeichen wird
  großgeschrieben so gezeichnet, wie es in der Config steht (samt Präfix und
  Portabel-Kennung); die Bestätigungs-Markierung steht oben mittig.
- **Normalisierung vor dem Zeichnen**: `generate` wendet auf jede Karte
  `regroup_card_by_remarks` an (§5.2) — so bekommt keine Karte mehr Zeilen, als je
  nach Remarks-Zustand Platz haben (Sicherung pro Karte, egal wie die Remarks auf
  die Karte kamen: global, Vorschau, direkte API). Die Seitenzahl richtet sich
  nach der so normalisierten Kartenliste.
- **Fortschritt**: `generator.generate(..., progress_cb)` ruft
  `progress_cb(done, total)` nach jeder Karte → GUI aktualisiert Balken via
  `root.after`.
- **Adress-/Label-Export (optional)**: zusätzlich zu den Karten eine CSV mit
  Empfängeradressen **aller** nachgeschlagenen Stationen erzeugen, wenn
  `address_export == True`. Format simpel (Adressblöcke), separat von den Karten.

---

## 8. Fehler- & Randfälle

| Fall                                   | Verhalten                                   |
|----------------------------------------|---------------------------------------------|
| Logdatei nicht lesbar (fehlt, Rechte)  | `OSError` → GUI-Meldung „Logbuch nicht lesbar" |
| Format weder ADIF noch Cabrillo        | `LogFormatError` → GUI-Meldung „Logbuch nicht verwertbar"; die bisher geladenen QSOs bleiben stehen, kein Lookup startet |
| Log erkannt, aber ohne QSOs            | ebenfalls `LogFormatError` (§4.6) — „0 QSOs geladen" wäre keine Antwort |
| QSO ohne `call`                        | überspringen                                |
| einzelne kaputte Cabrillo-Zeile        | überspringen + loggen, Import läuft weiter  |
| Lookup ohne Treffer/„?"                | `via_routes = (default_via,)`, Karte trotzdem |
| Station nur elektronisch (LoTW/eQSL)   | Wege = `Q`/`L`; unter der Trennlinie standardmäßig nicht gedruckt (manuell aktivierbar) |
| keine Lookup-Zugangsdaten eingetragen  | kein Netzcall, alle `via_routes = (default_via,)` |
| Frontbild fehlt                        | Erzeugung blockieren, Popup + roter Rahmen ums Vorschaufeld (§2.4) |
| Pflichtfeld leer / kein Log geladen     | Erzeugung blockieren, **ein** Popup mit allen fehlenden Angaben, Felder rot markiert (§2.4) |
| Lookup schlägt fehl / kein Konto       | Via = `default_via`, Adressfelder leer, kein Abbruch |
| zu viele QSOs pro Station für Tabelle  | Folge-Karte(n) anlegen                      |
| Umlaute/UTF-8 im Namen                 | korrekt kodieren (ReportLab-Font mit Umlauten) |

**Fonts/Umlaute**: Standard-PDF-Fonts (Helvetica) unterstützen Latin-1-Umlaute.
Für saubere Umlaute ggf. eine TrueType-Font (z.B. DejaVu Sans) registrieren und
in `geometry.py` referenzieren.

---

## 9. Tests (`tests/`)
- `test_adif_parser.py`: alle Fälle aus §4.4.
- `test_cabrillo_parser.py`: alle Fälle aus §4.5.4.
- `test_logbook.py`: Formaterkennung und Fehlerverhalten des Dispatchers (§4.6),
  inkl. „`parse_file` auf `Log.adi` liefert dasselbe wie der ADIF-Parser" als
  Regressionsschutz und „fehlende Datei → `OSError`, nicht `LogFormatError`".
- `test_card_builder.py`: alle QSOs (kein Via-Filter mehr), `via_routes` aus
  Lookup-Map + `default_via`-Fallback, `effective_via` (Priorität + Trennlinie +
  `via_override`), Datum-Split, Gruppierung per_qso/per_station, Zeilen-Überlauf
  (MAX_ROWS_PLAIN/WITH_REMARKS), `regroup_card_by_remarks` und
  `normalize_station_cards` (Split/Merge, Remarks je Karte, Idempotenz).
- `test_lookup.py`: `accepted_routes` (B/D/Q/L; Manager zählt als Büro; leer →
  `default_via`), `resolve_route`/`active_via_priority`/`normalize_via_priority`,
  `extract_manager_callsign`, Parsing der Routing-Felder (HamQTH inkl. lotw/eqsl,
  QRZ-Manager), Enrichment über alle Stationen, Cache, Reauth — HTTP gemockt.
- `test_config.py`: Laden/Speichern, fehlende Felder → Defaults, `appearance`/
  `recent` (Roundtrip, defensives Laden, Kappung, `push_recent`), `sheet_mode`
  (Default `single`, Roundtrip, alte Config ohne das Feld).
- `test_geometry.py`: mm-Umrechnung, Seitenmaße, dass alle Konstanten definiert
  sind und im Blattbereich liegen; Druckrand (Clamping, Rahmen, elastisches
  Layout) und **Bogendruck**: Raster kachelt A4 lückenlos und hängt nicht am
  Rand, jede der vier Karten hat denselben Rand auf allen vier Seiten, zwischen
  zwei Karten liegt der doppelte Rand, Schnittlinien bleiben im bedruckbaren
  Bereich.
- `test_generator.py`: Smoke-Test beider Druckmodi (läuft ohne Exception; duplex
  erzeugt eine Datei mit 2 × Kartenanzahl Seiten, separate zwei Dateien). Für den
  **Bogen** zusätzlich am fertigen PDF: A4-Seitengröße, 4 Karten je Bogen (auch
  angebrochen), Schnittlinien nur auf den Rückseiten, Fortschritt zählt Karten,
  Ränder je Karte, und `single` liefert byteweise die bisherige Ausgabe.
- `test_gui.py`: Widget-Baum baut headless; Auto-Sync der Config (inkl. Erhalt von
  `appearance`/`recent`); Themenwechsel, Statusleiste, „Zuletzt verwendet",
  Icon-Reihenfolge, Zebra-/Icon-Hintergründe, Zeichenzähler, Seiten-Scroll;
  **Pflichtangaben** (§2.4: Popup statt Erzeugung, Markierung an Log/Bild/Feldern,
  Markierung geht beim Ausfüllen weg, Fußnote unter allen Abschnitten) und dass
  „Drucken → Nein" die Zeile sofort ausgraut (Auswahl aufgehoben).
- `test_theme.py`: Paletten vollständig, Modus-Auflösung, `clam` + gesetzte
  Style-Farben, `restyle_tree` für klassische tk-Widgets.
- `test_menu.py`: Menüstruktur, dynamische Teile („Zuletzt verwendet", Sperre von
  „PDF erzeugen"), jeder Eintrag löst seinen Callback aus, Kürzel je Plattform.
- `test_icon_canvas.py`: **gleicht die Vektor-Zeichnung mit `app_icon.svg` ab**
  (Rechtecke, Bögen, Strichstärke, gemischte Schattenfarbe) — schlägt fehl, sobald
  SVG und Canvas auseinanderlaufen.
- `test_scrolling.py`: Schrittweite je Meldeart (macOS/Windows/X11) und dass unter
  Tk 9/X11 **nicht** beide Meldearten gebunden sind (sonst doppeltes Scrollen).
- `test_textedit.py`: Wortgrenzen, Belegung je Plattform, echtes Tastenverhalten.
  **Merke:** ein per `withdraw()` verstecktes Fenster nimmt keine synthetischen
  Tastenereignisse an — Testfenster off-screen öffnen statt verstecken.
- `test_help.py`: Handbuch-Renderer, Kapitelliste, Sprungziele — jeder Abschnitt
  hat seinen Anker `{#abschnitt-N}`, jeder interne Verweis trifft ein Ziel.
- `test_paths.py`: §10 — Quellmodus zeigt in die Projektwurzel (auch aus fremdem
  Arbeitsverzeichnis), gebündelt Portable- vs. Benutzerordner, macOS-Sonderfall
  `.app/Contents/MacOS`, Config und Cache im selben Ordner, `subprocess_env`.
- `test_build_app.py`: die Vorbedingungsprüfung des Build-Skripts (§10.5), vor
  allem die vier Kombinationen aus „Tcl-Daten eingebettet" × „PyInstaller kennt
  den Fall" — die falsche davon erzeugte ein Bündel, das erst beim Doppelklick
  starb. Außerdem, dass der Tk-Hinweis die **Punktversion** 3.14.7 nennt.

---

## 10. Pfade und Auslieferung (`paths.py`, `packaging/`)

### 10.1 Warum es das Modul gibt

Aus der Quelle gestartet ist das Arbeitsverzeichnis üblicherweise der
Projektordner, und ein relativer Pfad wie `"config.yaml"` trifft. Per Doppelklick
auf eine gebündelte Anwendung ist es `C:\Windows\System32` bzw. `$HOME` — derselbe
Pfad zeigt dann irgendwohin. **Alle** Pfade stehen deshalb in `paths.py`, nach
derselben Regel wie die Layout-Zahlen in `pdf/geometry.py`. Kein anderes Modul
baut sich einen Pfad aus `__file__` oder einem relativen String zusammen.

Drei Orte werden streng auseinandergehalten:

| Funktion | Bedeutung | gebündelt | aus der Quelle |
|---|---|---|---|
| `resource_path(*teile)` | mitgeliefert, **nur lesbar**: Schriften, Icons, `handbuch.md`, `config.example.yaml` | `sys._MEIPASS/…` | Projektwurzel |
| `program_dir()` | wo das Programm für den Anwender „liegt" | Ordner der Binary (macOS: **über** der `.app`) | Projektwurzel |
| `user_data_dir()` | plattformüblich, immer beschreibbar | `%APPDATA%` / `~/Library/Application Support` / `$XDG_CONFIG_HOME` | (dito, ungenutzt) |

### 10.2 Datenablage (hybrid)

`data_dir()` entscheidet **einmal** für Config, Lookup-Cache und Protokoll —
laufen sie auseinander, gehört der Cache zu einem anderen Konto.

- **Nicht gebündelt** → immer `program_dir()` (Projektwurzel). Der
  Entwickler-Workflow ändert sich durch das Bündeln nicht.
- **Gebündelt, `config.yaml` liegt daneben** → `program_dir()` (Portable-Modus,
  USB-Stick).
- **Sonst** → `user_data_dir()`.

`ensure_data_dir()` legt den Ordner an (mehr nicht: `open(..., "w")` erzeugt kein
Verzeichnis). Die `config.yaml` entsteht beim ersten Auto-Save; bis dahin liest
das Programm die mitgelieferte `config.example.yaml`, die inhaltlich identisch
ist (beide aus denselben Defaults, siehe §3).

Vorgeschlagenes Ausgabeziel: `default_output_dir()/qsl_karten.pdf` — **absolut**,
sonst landete die PDF im Arbeitsverzeichnis des Systems.

### 10.3 Kindprozesse

PyInstaller stellt seinen Bibliothekspfad an den Anfang von `LD_LIBRARY_PATH`
(Linux) bzw. `DYLD_LIBRARY_PATH` (macOS) und sichert den alten Wert unter
`…_ORIG`. Ein davon geerbtes `xdg-open` oder `gsettings` lädt die gebündelten
Bibliotheken statt der eigenen und stirbt mit „symbol lookup error". **Jeder**
externe Aufruf bekommt deshalb `env=paths.subprocess_env()`; aus der Quelle
bleibt die Umgebung unangetastet.

### 10.4 Protokoll

Ein Fensterprogramm hat kein `stderr` (unter Windows ist es `None`). Ohne
Gegenmaßnahme verschwinden alle `logger.warning` spurlos und Tks
`report_callback_exception` läuft gegen `None.write()`.
`main._prepare_frozen_runtime` ersetzt fehlende Ströme durch Attrappen und
schreibt in `paths.log_path()` (`RotatingFileHandler`, 1 MB, 2 Sicherungen).
Menü „Hilfe ▸ Protokoll anzeigen" führt hin.

### 10.5 Bauen

`scripts/build_app.py` + `packaging/qslcards.spec`, Modus **onedir** auf allen
Plattformen (Start ohne Entpacken, weniger Virenscanner-Fehlalarme, und der
Portable-Modus braucht einen Ordner).

**Cross-Compile gibt es nicht** — PyInstaller bündelt den Interpreter, unter dem
es läuft. Die harte Bedingung ist **Tk ≥ 9**: die SVG-Icons der Vorschautabelle
(§2) fehlen sonst ohne Fehlermeldung. Woher Tk kommt, ist plattformabhängig —
Windows/macOS aus dem Python-Installer (erst **3.14.7** bringt 9.0.4 mit —
3.14.0-3.14.6 haben noch 8.6.15), Linux vom System. Auf Fedora 42 genügt es
nicht, dass Tcl/Tk 9.0 als Systempaket vorliegt: das Standard-Python 3.13 ist
gegen die Kompatibilitätspakete `tcl8`/`tk8` gebaut und meldet 8.6 — gebaut wird
dort mit dem mitgelieferten **`python3.14`**.
PyInstaller muss **≥ 6.21** sein — für Windows sogar die noch
unveröffentlichte Entwicklungsfassung, weil Python 3.14.7 die Tcl-Bibliothek
in die DLL legt (`//zipfs:/…`) und 6.21.0 das nicht kennt; das Bündel bräche
sonst erst beim Start ab. Das Skript prüft alle Punkte vorab und bricht mit
Klartext ab, statt still etwas Kaputtes zu bauen — die PyInstaller-Fähigkeit
dabei am Quelltext, weil die Fassung mit dem Fix sich weiterhin als 6.21.0
meldet.

Verpackt wird plattformabhängig: Windows/Linux als ZIP bzw. `tar.gz` (letzteres
erhält die Ausführungsrechte), macOS zwingend mit **`ditto`** — ein gewöhnliches
`zip` löst die Symlinks in `Contents/Frameworks` auf und zerstört die Signatur.

Ausgeliefert wird überall ein **Ordner**, in dem neben dem Programm eine
`LIESMICH.txt` liegt; unter Linux kommen `install.sh` und die `.desktop`-Datei
dazu. Die READMEs aus `packaging/` gehören **nicht** ins Archiv — sie beschreiben
das Bauen und wären für den Anwender die falsche Datei. Auf
macOS entsteht er eigens (`macos_delivery_folder`): das Bauergebnis ist dort die
`.app`, und in die gehört nichts hinein. Die `.app` wird dabei **verschoben**,
nicht kopiert — was ausgeliefert wird, ist genau das, was in `dist/` ausprobiert
wurde.

Ein eigenes Bauskript hat nur die Plattform, auf der etwas zu beschaffen ist:
`packaging/windows/build.ps1` (Interpreter über den `py`-Launcher, venv,
PyInstaller aus `develop`) und `packaging/linux/Dockerfile.fedora` (überhaupt
ein Fedora 42). Auf macOS steht die Umgebung ohnehin — dort ist `build_app.py`
der ganze Vorgang.

Anleitungen und Prüflisten: `packaging/macos/README.md`,
`packaging/windows/README.md`, `packaging/linux/README.md`.
