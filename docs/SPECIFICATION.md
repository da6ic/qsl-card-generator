# SPECIFICATION.md — QSL-Karten-Generator

Ausführliche Spezifikation. Ergänzt `CLAUDE.md`. Layout separat in `CARD_LAYOUT.md`.

---

## 1. Anwendungsfall

Ein Funkamateur (Absender, z.B. DN5MT) hat ein Logbuch im ADIF-Format. Er will
QSL-Karten für bestätigte QSOs drucken. Das Programm erzeugt eine PDF, in der
jede Karte aus zwei A6-Seiten besteht (Bild vorne, Daten hinten). Vor der
Erzeugung wählt er ADIF, Frontbild, Absenderdaten, die Priorität der Zustellwege
(inkl. Trennlinie), Kartenmodus und Druckmodus.

---

## 2. GUI (Tkinter)

Ein Hauptfenster mit **Menüleiste** (§2.1), einem scrollbaren Bereich mit den
Abschnitten 1–10 und einer **Statusleiste** am Fuß (§2.3). Farben und Abstände
kommen ausschließlich aus `gui/theme.py` (§2.2) — kein Widget setzt selbst eine
Farbe, so wie kein Zeichencode eine Layoutzahl setzt (`pdf/geometry.py`).

Die Abschnitte (top → bottom) liegen in `gui/sections.py`:

1. **ADIF-Logbuch**: `Durchsuchen…`-Button, Pfadanzeige, Button `Log laden`.
   Nach der Auswahl wird das Log **automatisch geladen** (Hot-Load); der Button
   dient als manueller Reload. Nach dem Laden: Anzahl gelesener QSOs.
2. **Frontbild**: `Bild wählen…` (png/jpg/jpeg/webp), kleine Vorschau (Thumbnail).
3. **Absender**: Eingabefelder für Call, Name, Straße, PLZ, Ort, Land, Locator,
   DOK, CQ-Zone (WAZ), ITU. Durch eine Trennlinie abgesetzt die **Funk-Ausrüstung**
   (erscheint dynamisch auf der Karte, sobald gefüllt): `Empfänger` (RIG),
   `Antenne` (ANT), `Leistung` (PWR). Zusätzlich drei globale Dropdowns (gelten für
   **alle** Karten):
   - **QSL-Markierung** (`qsl_mark`): `PSE QSL` / `TNX QSL` / `Leer lassen`.
   - **Portabel-Markierung** (`portable_mark`): `Keins` / `/p` / `/m` / `/t` / `/r`
     (Kennung hinter dem eigenen Rufzeichen).
   - **Bestätigung** (`confirm_mark`): `Leer lassen` / `Confirming QSO` /
     `Confirming SWL-Report`.
   Kein „Untertitel"/„Responsive" mehr. Keine Speichern/Laden-Buttons: die
   Config wird **automatisch** gespeichert (debounced) und bei externer Änderung
   von `config.yaml` **automatisch neu geladen**.
4. **Zustellwege**: eine priorisierbare **Liste** (Listbox) der Wege `Büro` (B),
   `Direkt` (D), `eQSL` (Q), `LOTW` (L) plus eine verschiebbare **Trennlinie**
   (`via_cut`). Buttons ▲/▼ verschieben den ausgewählten Eintrag (Trennlinie
   eingeschlossen). Wege **oberhalb** der Linie sind aktiv (werden gedruckt, in
   Reihenfolge = Priorität), Wege **darunter** nicht. Gedruckt wird je Empfänger
   der höchstpriorisierte aktive Weg aus dessen **akzeptierten** Wegen (aus dem
   Lookup, §6). Die Liste **entfernt keine Zeilen**, sondern setzt nur die
   Drucken-Markierung. Kein Via-Filter (B/D/M) mehr.
5. **Kartenmodus**: Radiobuttons `Eine Karte pro QSO` / `Eine Karte pro Station`.
   (Die globalen Markierungen QSL/Portabel/Bestätigung stehen in Abschnitt 3.)
6. **Lookups (optional)**: HamQTH-Benutzer/Passwort, QRZ-Benutzer/Passwort,
   Checkbox „Adress-/Label-Export erzeugen". **Kein** Schalter „Adressen
   nachschlagen" mehr — der Lookup läuft **automatisch beim Log-Laden** (§6),
   sofern Credentials gesetzt sind.
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
   Trennlinie manuell druckbar). **`Via`, `Route/Manager` und `Remarks` sind
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
   `generation.print_mode` (`duplex` | `separate`, siehe §7). **Rechts daneben**
   die Checkbox `Erweiterte Einstellungen` (`generation.print_margin_enabled`);
   ist sie gesetzt, erscheint darunter der Block **Seitenrand (mm)** mit vier
   `ttk.Spinbox` (oben/unten/links/rechts, 0…`PRINT_MARGIN_MAX` = 15 mm, Schritt
   0,5) → `generation.print_margin_top/bottom/left/right` (siehe §7 „Druckrand").
   Beide Spalten liegen in **eigenen Containern** in derselben Grid-Zeile, oben
   verankert und **ohne `rowspan`**: sonst verteilt Tk die Höhe des Randblocks
   auf die übersprungenen Zeilen und verrückt beim Aufklappen die Radiobuttons.
10. **Ausgabe**: Zielpfad der PDF, Button `PDF erzeugen` (Primärbutton,
   `Accent.TButton`) und Fortschrittsbalken (`ttk.Progressbar`). Die Statuszeile
   steht **nicht** mehr hier, sondern in der Fußleiste (§2.3). `PDF erzeugen` ist
   **deaktiviert**, solange der Lookup nach dem Log-Laden noch läuft, und wird erst
   danach wieder aktiv (synchron dazu der Menüeintrag). Nach Erfolg werden die
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
| **Datei** | ADIF-Logbuch öffnen… (⌘/Strg+O), Zuletzt verwendete Logs ▸, Frontbild wählen… (+B), Zuletzt verwendete Bilder ▸, Ausgabeziel wählen… (+⇧S), PDF erzeugen (+P) |
| **Bearbeiten** | Ausschneiden/Kopieren/Einfügen/Alles auswählen — als virtuelle Events ans fokussierte Widget |
| **Aktionen** | Log neu laden (+R), Lookups neu abrufen (+⇧R), Lookup-Cache leeren… |
| **Ansicht** | Farbthema ▸ System/Hell/Dunkel, Gehe zu Abschnitt ▸ 1–10 |
| **Hilfe** | Dokumentation ▸, config.yaml öffnen, Ausgabeordner anzeigen, Lookup-Cache anzeigen, Über… |

Plattform-Eigenheiten sind in `menu.py` gekapselt: auf **macOS** ⌘-Kürzel sowie
„Über…"/„Beenden" im Programm-Menü (`name="apple"`, `tk::mac::Quit`), sonst
Strg-Kürzel mit „Beenden" in „Datei" und „Über…" in „Hilfe". Ein `accelerator`
ist bei Tk nur Beschriftung — die Kürzel werden zusätzlich per `bind_all`
registriert.

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
  jedem Wechsel, sonst behalten sie die Farben des Betriebssystems.
- Achtung `clam`: Radio-/Checkbuttons färbt man über `indicatorbackground`/
  `indicatorforeground`; `indicatorcolor` (die Option der alten tk-Widgets) wird
  ignoriert.
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
    hamqth_user: str = ""
    hamqth_pass: str = ""
    qrz_user: str = ""
    qrz_pass: str = ""
    program_id: str = "qslcards"   # HamQTH verlangt prg-Kennung
    address_export: bool = False   # Adress-/Label-Export erzeugen (alle Stationen)
    # Hinweis: KEIN `lookup_addresses` mehr — der Lookup läuft automatisch beim
    # Log-Laden, sobald Credentials gesetzt sind (siehe §6).

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
    # Druckrand (§7): Ränder in mm je Kante, nur wirksam wenn eingeschaltet.
    print_margin_enabled: bool = False # „Erweiterte Einstellungen" in Abschnitt 9
    print_margin_top: float = 0.0      # 0 .. PRINT_MARGIN_MAX (15 mm)
    print_margin_bottom: float = 0.0
    print_margin_left: float = 0.0
    print_margin_right: float = 0.0
    static_footer: str = "TNX FR NICE CONTACT, 73"
    remarks: str = ""                  # globaler REMARKS-Text (alle Karten); leer
                                       #   -> kein Kasten. Max. 80 Zeichen (GUI).
    qsl_mark: str = "none"             # "pse" | "tnx" | "none" (global)
    portable_mark: str = "none"        # "none" | "p" | "m" | "t" | "r" (global)
    confirm_mark: str = "none"         # "none" | "qso" | "swl" (global)
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

> **Achtung beim Auto-Save:** `appearance` und `recent` haben keine Eingabefelder.
> `App._gather_config()` baut die Config aus den Widgets und muss beide aus der
> Basis-Config übernehmen, sonst löscht das nächste automatische Speichern sie.

---

## 4. ADIF-Parser (`adif/parser.py`)

### 4.1 Formatregeln
- ADIF besteht aus **Feld-Specifiern** `<NAME:LÄNGE>WERT` oder
  `<NAME:LÄNGE:TYP>WERT`. `LÄNGE` = Byte-Länge des Werts.
- Feldnamen sind **case-insensitive** → intern immer `lower()`.
- `<EOH>` beendet den optionalen Header (alles davor ignorieren).
- `<EOR>` beendet einen QSO-Record.
- Werte können beliebige Zeichen (inkl. Zeilenumbrüche) enthalten; die Länge
  ist maßgeblich, **nicht** Whitespace/Zeilenenden.
- Text außerhalb von `<...>`-Tags nach `<EOH>` bis zum ersten `<` gehört nicht
  zum Wert und wird verworfen.

### 4.2 Algorithmus (Tokenizer)
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

### 4.3 Mapping Record → `QSO`
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

### 4.4 Testfälle (mind.)
- Header vorhanden / fehlt.
- Groß-/Kleinschreibung gemischt (`<Call:5>`, `<CALL:5>`).
- Typ-Suffix (`<freq:6:N>14.074`).
- Zeilenumbruch im Wert (z.B. Kommentarfeld).
- Fehlendes letztes `<EOR>`.
- Record ohne `call` → übersprungen.
- Mehrere QSOs mit demselben Call (für Gruppierung).

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
    portable_mark: str = "none" # global aus config: "none" | "p" | "m" | "t" | "r"
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
   - `card.portable_mark = config.portable_mark`
     (`"none"` | `"p"` | `"m"` | `"t"` | `"r"`).
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

**Warum zentral:** Das ADIF-Log enthält **keine** Versandart. Der Lookup ist der
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

### 6.6 Wann/wie wird gelookt?
- **Automatisch beim Log-Laden**, für **alle** Stationen (eindeutige Rufzeichen),
  im Hintergrund-Thread. Kein `lookup_addresses`-Schalter mehr.
- Läuft nur, wenn HamQTH- **oder** QRZ-Credentials gesetzt sind. Ohne Credentials:
  keine Netzcalls, alle Via = `default_via`, Adressen leer.
- Manueller **„Neu abrufen"**-Button holt fehlende/abgebrochene Stationen nach.
- **Adresse**: wird für alle nachgeschlagenen Stationen geholt und (wenn
  `address_export`) für **alle** exportiert — sie steht **nicht** auf der Karte.

---

## 7. PDF-Erzeugung (`pdf/`)

- **Seitengröße**: A6. Querformat (`landscape`) als Default, da die Referenzkarte
  querformatig ist. In `geometry.py` umschaltbar.
- **Druckmodus** (`generation.print_mode`), `generate(...) -> list[Path]`:
  - `"duplex"`: **eine** PDF, pro Karte zuerst Vorderseite, dann Rückseite, dann
    `canvas.showPage()`. So entsteht Seite 1=Front(Karte1), 2=Back(Karte1),
    3=Front(Karte2), … → passt für Duplexdruck (lange Kante).
  - `"separate"`: **zwei** PDFs (`…_vorderseiten.pdf`, `…_rueckseiten.pdf`) für
    Drucker ohne beidseitigen Druck: erst alle Vorderseiten drucken, Papier
    umgedreht neu einlegen, dann die Rückseiten. Da **ein** Frontbild für alle
    Karten gilt, sind alle Vorderseiten identisch (keine Umkehrung nötig).
- **Druckrand** (`generation.print_margin_*`, GUI-Abschnitt 9): Viele Drucker
  drucken nicht bis zur Blattkante und beschneiden sonst den Inhalt. Die vier
  Werte bedeuten „so viel Rand **muss** frei bleiben". Das Blatt bleibt A6
  (`setPageSize` wird nie aufgerufen) — nur die Zeichnung rückt ein:
  1. Rahmen = Blatt minus der vier (geclampten) Ränder → `geometry.content_box`.
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
  Druckrand aus, ist das Ergebnis die Identität (`scale=1`, virtuelle Seite = A6)
  und die Ausgabe byteweise dieselbe wie ohne das Feature. `MAX_ROWS_*` bleibt
  unberührt — senkrechter Überschuss vergrößert nur den Abstand zwischen Tabelle
  und Fuß, die Kartenaufteilung im Builder ändert sich nicht. Ein Deckel
  (`MAX_STRETCH`) begrenzt den elastischen Überschuss bei absurden Randwerten;
  der Rest wird dann zentriert (der Rand ist dort größer als eingestellt).
- **Front** (`layout_front.py`): Frontbild im **Cover-Modus** den ganzen Rahmen
  füllen (kein weißer Rand innerhalb des Rahmens), Seitenverhältnis wahren,
  Überstand beschneiden (Clip), zentriert. Der Rahmen ist `geometry.content_box`
  — ohne Druckrand die volle Seite, sonst derselbe Rahmen wie die Rückseite,
  damit beide Seiten deckungsgleich liegen. Das Bild wird auch bei ungleichen
  Rändern **nie verzerrt**. Einmal via Pillow geladen und als ImageReader
  gecacht, für alle Karten wiederverwenden.
- **Back** (`layout_back.py`): exakt nach `CARD_LAYOUT.md`. Alle Positionen/
  Größen aus `geometry.py`; die mitwachsenden Maße und die Y-Spiegelung kommen
  aus dem `PageLayout`, den `draw_back` einmal baut und an alle Helfer
  weiterreicht. Der REMARKS-Block (Label + Kasten + Text) wird nur
  gezeichnet, wenn `card.remarks` gesetzt ist (dynamisch); der Footer-Text steht
  immer. Der **Funk-Block** (RIG/ANT/PWR-Tabelle) erscheint nur, wenn mindestens
  eins der Felder `receiver`/`antenna`/`power` gefüllt ist; dann rücken QSL-
  Markierung und QSO-Tabelle nach unten. Portabel-Kennung (`/p`/`/m`/`/t`/`/r`)
  steht hinter dem eigenen Rufzeichen, die Bestätigungs-Markierung oben mittig.
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
| ADIF unlesbar/leer                     | GUI-Meldung, keine Karten                   |
| QSO ohne `call`                        | überspringen                                |
| Lookup ohne Treffer/„?"                | `via_routes = (default_via,)`, Karte trotzdem |
| Station nur elektronisch (LoTW/eQSL)   | Wege = `Q`/`L`; unter der Trennlinie standardmäßig nicht gedruckt (manuell aktivierbar) |
| keine Lookup-Credentials               | kein Netzcall, alle `via_routes = (default_via,)` |
| Frontbild fehlt                        | Erzeugung blockieren + Hinweis              |
| Lookup schlägt fehl / kein Konto       | Via = `default_via`, Adressfelder leer, kein Abbruch |
| zu viele QSOs pro Station für Tabelle  | Folge-Karte(n) anlegen                      |
| Umlaute/UTF-8 im Namen                 | korrekt kodieren (ReportLab-Font mit Umlauten) |

**Fonts/Umlaute**: Standard-PDF-Fonts (Helvetica) unterstützen Latin-1-Umlaute.
Für saubere Umlaute ggf. eine TrueType-Font (z.B. DejaVu Sans) registrieren und
in `geometry.py` referenzieren.

---

## 9. Tests (`tests/`)
- `test_adif_parser.py`: alle Fälle aus §4.4.
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
  `recent` (Roundtrip, defensives Laden, Kappung, `push_recent`).
- `test_geometry.py`: mm-Umrechnung, Seitenmaße, dass alle Konstanten definiert
  sind und im Blattbereich liegen.
- `test_generator.py`: Smoke-Test beider Druckmodi (läuft ohne Exception; duplex
  erzeugt eine Datei mit 2 × Kartenanzahl Seiten, separate zwei Dateien).
- `test_gui.py`: Widget-Baum baut headless; Auto-Sync der Config (inkl. Erhalt von
  `appearance`/`recent`); Themenwechsel, Statusleiste, „Zuletzt verwendet",
  Icon-Reihenfolge, Zebra-/Icon-Hintergründe, Zeichenzähler, Seiten-Scroll.
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
