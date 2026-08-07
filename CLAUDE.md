# CLAUDE.md — QSL-Karten-Generator

Diese Datei ist die zentrale Anleitung für Claude Code. Sie beschreibt Ziel,
Technik-Stack, Architektur, Konventionen und die empfohlene Build-Reihenfolge.
Details stehen in `docs/SPECIFICATION.md` und `docs/CARD_LAYOUT.md`.

---

## 1. Ziel des Projekts

Ein Desktop-Programm (Python + Tkinter), das aus einem **Logbuch** (ADIF oder
Cabrillo) automatisch **QSL-Karten** erzeugt und als **eine große PDF** ausgibt.

- Jede Karte = **2 A6-Seiten**: Vorderseite (Bild) + Rückseite (QSL-Layout).
- Die Rückseite folgt **exakt** dem Referenz-Layout aus `docs/CARD_LAYOUT.md`
  (Vorlage: DARC-QSL-Karte, Rückseite von DN5MT).
- Ein **einziges Frontbild** wird für **alle** Karten verwendet.
- Absenderdaten kommen aus der **Config**, QSO-Daten aus dem **Log**,
  Empfänger-/Routing-Daten aus **HamQTH** (primär) bzw. **QRZ** (optional).
- **Zwei Logformate, ein Datenmodell**: ADIF (Alltags-Logbuch) und Cabrillo
  (Contest). Das Format wird am **Inhalt** erkannt; alles hinter `logbook/`
  kennt den Unterschied nicht mehr.
- Die **Versandart (Via)** steht **nicht** im Log — der Lookup liefert je Station
  die **Menge akzeptierter Zustellwege** (B=Büro inkl. Manager, D=Direkt, Q=eQSL,
  L=LOTW, siehe §5). In der GUI **priorisiert** der Nutzer diese Wege und zieht
  eine **Trennlinie** (`via_cut`): Wege darüber werden gedruckt, Wege darunter
  nicht. Gedruckt wird je Karte der höchstpriorisierte aktive Weg der Station.
- Modus wählbar: **eine Karte pro QSO** oder **eine Karte pro Station**.
- Druckmodus wählbar: **Duplex** (eine PDF, Vorder-/Rückseite abwechselnd) oder
  **getrennt** (zwei PDFs: alle Vorderseiten, alle Rückseiten).
- **Bogendruck** (quer dazu): wahlweise eine Karte je A6-Seite oder **vier Karten
  auf einem A4-Bogen** (quer, 2×2) mit gestrichelten Schnitt-Hilfslinien.

---

## 2. Technik-Stack

| Zweck              | Wahl                          | Begründung                                   |
|--------------------|-------------------------------|----------------------------------------------|
| Sprache            | Python **3.11+**              | `tomllib`, moderne Typing-Syntax             |
| GUI                | **Tkinter** (stdlib)          | vorgegeben, keine Extra-Abhängigkeit         |
| PDF                | **ReportLab**                 | präzise mm-genaue Positionierung, A6, Tabellen |
| Bilder             | **Pillow**                    | Skalierung/Format des Frontbilds             |
| HTTP/Lookups       | **requests**                  | HamQTH-/QRZ-XML-API                           |
| Config             | **PyYAML** (`config.yaml`)    | kommentierbar, gut editierbar                |
| Tests              | **pytest**                    | Unit-Tests, v.a. Parser & Kartenlogik        |

Bewusst **kein** externes Parser-Package (weder ADIF noch Cabrillo): eigene,
getestete Parser (Anforderung).

---

## 3. Projektstruktur

```
qslcards/
  __init__.py
  main.py                 # Einstiegspunkt: startet die GUI
  config.py               # Config-Dataclasses + Laden/Speichern (YAML)
  logbook/
    __init__.py           # Formaterkennung + Dispatcher (die öffentliche API)
    models.py             # QSO-Dataclass (für BEIDE Formate)
    adif.py               # ADIF-Tokenizer + Record-Parser
    cabrillo.py           # Cabrillo-Parser (Contest-Logs)
  lookup/
    __init__.py
    base.py               # LookupProvider-Interface + Ergebnis-Dataclass
    hamqth.py             # HamQTH-Client (Session-basiert)
    qrz.py                # QRZ-Client (optional)
    cache.py              # lokaler Cache (JSON), spart API-Calls
  cards/
    __init__.py
    models.py             # Card, CardEntry (Recipient) Dataclasses
    builder.py            # QSOs -> Karten: filtern (Via), gruppieren (QSO/Station)
  pdf/
    __init__.py
    geometry.py           # Seitenmaße, mm-Helfer, ALLE Layout-Konstanten
    layout_front.py       # zeichnet die Bild-Vorderseite
    layout_back.py        # zeichnet die Rückseite (Referenz-Layout)
    layout_sheet.py       # Bogendruck: 4 Karten je A4-Seite + Schnittlinien
    generator.py          # orchestriert die Gesamt-PDF (alle Karten)
  gui/
    __init__.py
    app.py                # Hauptfenster, verdrahtet alles
    sections.py           # UI-Abschnitte (Datei, Bild, Absender, Filter, ...)
    preview.py            # Tabelle: ALLE QSOs/Karten + Via/Route, Drucken-Flag
    theme.py              # Farbthema (hell/dunkel) + ALLE Farben/Abstände der GUI
    menu.py               # Menüleiste (plattformabhängige Kürzel/Sonderfälle)
    help.py               # Handbuch-Fenster + kleiner Markdown-Renderer
    icon_canvas.py        # Programm-Icon als Vektor (für den „Über"-Dialog)
    scrolling.py          # Mausrad je Fenstersystem (macOS/Windows/X11)
    textedit.py           # Wort-/zeilenweises Löschen in Eingabefeldern
  assets/
    fonts/                # DejaVuSans (Umlaute auf der Karte)
    icons/                # Tabellen-Icons + app_icon.svg und dessen Renderings
tests/
  test_adif_parser.py     test_theme.py
  test_cabrillo_parser.py test_menu.py
  test_logbook.py         test_icon_canvas.py
  test_card_builder.py    test_scrolling.py
  test_lookup.py          test_textedit.py
  test_geometry.py        test_gui.py
  test_config.py          test_help.py
  test_generator.py
scripts/
  preview_card.py         # Karten-Preview als PDF (`--4up [RAND_MM]` = A4-Bogen)
  make_icon.py            # app_icon.svg -> PNG (16–1024) + .ico + .icns
config.example.yaml       # Vorlage -> Nutzer kopiert nach config.yaml
handbuch.md               # Anwender-Handbuch (zeigt „Hilfe > Handbuch" an)
requirements.txt
README.md
docs/
  SPECIFICATION.md        # ausführliche Funktions-/Technik-Spezifikation
  CARD_LAYOUT.md          # exakte Layout-Spezifikation der Rückseite
```

---

## 4. Datenfluss (Big Picture)

```
Logdatei ──logbook (erkennt ADIF|Cabrillo)──> [QSO, QSO, ...]
                            │
HamQTH/QRZ (auto beim Laden, alle Stationen, gecacht)
   └─> je CALL: akzeptierte Wege {B,D,Q,L} + Manager + Adresse
                            │
                            ▼
        builder(alle QSOs, via_routes aus Lookup, Gruppierung) ──> [Card, ...]
                                                    │
Config (Absender) ──────────────────────────────────┤
Frontbild ──────────────────────────────────────────┤
                                                    ▼
GUI: Priorität + Trennlinie (effective_via) ──> generator ──> PDF(s) (+ Adress-CSV)
```

Jede `Card` erzeugt genau zwei Seiten: `layout_front` + `layout_back`.

---

## 5. Wichtige fachliche Regeln (nicht raten — hier steht's)

1. **Signalrapport auf der Karte = `RST_SENT`** (der Rapport, den *wir* dem
   Gegenüber gegeben haben = wie wir ihn gehört haben). Nicht `RST_RCVD`.
2. **Via kommt aus dem Lookup, NICHT aus dem Log.** Das Log enthält keine
   Versandart. `accepted_routes(result, default_via)` liefert je Station die
   **Menge** akzeptierter Zustellwege (kanonisch geordnet B, D, Q, L):
   - `B` (Büro) wenn `qsl=Y` **oder** ein echtes Manager-Rufzeichen hinterlegt
     ist (der Manager zählt als Büro-Weg; sein Callsign steht dann im Feld „Via:").
   - `D` (Direkt) wenn `qsldirect=Y`.
   - `Q` (eQSL) wenn `eqsl=Y`.
   - `L` (LOTW) wenn `lotw=Y`.
   - leere Menge (kein Treffer/nur „?"/„N"/keine Credentials) → `(default_via,)`
     (Config-only, Default `B`), damit die Station druckbar bleibt.
   In der GUI (Abschnitt 4) **priorisiert** der Nutzer die Wege (Listbox) und zieht
   eine **Trennlinie** (`via_cut`): die ersten `via_cut` Wege sind aktiv. Gedruckt
   wird je Karte der höchstpriorisierte **aktive** Weg, der in der Menge der Station
   liegt (`resolve_route`/`effective_via`); liegt keiner über der Linie, wird die
   Karte **nicht** gedruckt. Ein manueller `via_override` (Vorschau) erzwingt einen
   Weg, respektiert aber weiter die Trennlinie. Kein `derive_via`/`include_missing_
   via`/Via-Filter (B/D/M) mehr.
3. **Absenderblock** (Call, Name, Straße, PLZ/Ort, Land, Locator, DOK, WAZ, ITU)
   kommt **immer aus der Config**, nie aus dem Log.
4. **Empfänger** auf der Karte = **nur das Rufzeichen** (`CALL`) im Feld
   „To Amateur Radio Station:". Der **Manager** (aus dem Lookup) steht im Feld
   „Via:". Name/Adresse des Empfängers stehen **nicht** auf der Karte — sie gehen
   nur in den **optionalen Adress-/Label-Export** (für **alle** Stationen).
5. **Lookup läuft automatisch** beim Log-Laden für **alle** Stationen im
   Hintergrund-Thread (kein `lookup_addresses`-Schalter), sofern HamQTH-/QRZ-
   Credentials gesetzt sind; sonst kein Netzcall und alle Via = `default_via`.
   Ergebnisse (auch negative) werden gecacht (`lookup/cache.py`). „PDF erzeugen"
   ist gesperrt, bis der Lookup fertig ist; „Neu abrufen" holt Fehlende nach.
6. **Karte pro QSO vs. pro Station**: Bei „pro Station" werden alle QSOs mit
   demselben Call (innerhalb desselben Via) zu **einer** Karte zusammengefasst;
   die Tabelle bekommt dann **mehrere Zeilen** (max. Zeilenzahl aus
   `CARD_LAYOUT.md`, Rest ggf. Folge-Karte).

---

## 6. Modul-Verträge (Contracts)

### `logbook/models.py`
```python
@dataclass
class QSO:
    call: str
    qso_date: str        # "YYYYMMDD" (roh, wie im Log)
    time_on: str         # "HHMM" oder "HHMMSS"
    band: str | None
    freq: str | None     # MHz als String, z.B. "14.074"
    mode: str | None
    rst_sent: str | None
    rst_rcvd: str | None
    qsl_sent_via: str | None   # Rohwert aus dem Log, rein informativ
    qsl_via: str | None        # Manager/Route-Text (roh, informativ)
    name: str | None           # falls im Log vorhanden
    gridsquare: str | None
    qth: str | None            # Ort der Gegenstation (falls im Log)
    country: str | None        # Land der Gegenstation (falls im Log)
    raw: dict[str, str]        # alle Felder roh, kleingeschrieben
```

### `logbook/adif.py`
- `parse_file(path) -> list[QSO]`
- `parse_text(text) -> list[QSO]`
- Algorithmus in `docs/SPECIFICATION.md` §4.1–4.4. Robust gegen: fehlenden
  Header, gemischte Groß/Kleinschreibung, Typ-Suffixe (`<FREQ:5:N>`), `<EOH>`,
  `<EOR>`, Zeilenumbrüche innerhalb von Werten.

### `logbook/cabrillo.py`
- gleiche API (`parse_file`/`parse_text`), Algorithmus in §4.5.
- Zerlegt die `QSO:`-Zeile **tokenweise** (die Spaltenpositionen der Cabrillo-
  Spezifikation sind ausdrücklich unverbindlich): Datum als Anker,
  Transmitter-ID nur bei ungerader Feldzahl abtrennen, Trennstelle per Score,
  Rapport streng validiert (`[1-5][1-9][1-9]?` — so fallen Seriennummern wie
  `001`/`101` durch). Kein Rapport im Log → Feld bleibt leer, **nie** raten.
- Normalisiert nach `QSO`: Datum `yyyy-mm-dd`→`YYYYMMDD`, Frequenz (kHz bzw.
  Bandbezeichner)→MHz-String, Band aus der Frequenz, Modus `PH`→`SSB`/`RY`→
  `RTTY`/`DG`→`DIGI`. Ohne das rechnen `builder._split_date`/`_format_freq` falsch.
- `CALLSIGN:`/`GRID-LOCATOR:` aus dem Kopf sind **Absender**daten: nur intern
  zum Zerlegen bzw. informativ in `raw` — nie in `qso.gridsquare` (§5.3).

### `logbook/__init__.py`
- `detect_format(text) -> "adif" | "cabrillo" | None` — am **Inhalt**, nicht an
  der Dateiendung (`.log`/`.txt` sind mehrdeutig).
- `parse_file(path)`/`parse_text(text)` — erkennt und delegiert.
- `LogFormatError` — unbekanntes Format **oder** kein einziges QSO. Die
  Format-Parser werfen **nie**; nur der Dispatcher weiß, dass ein Anwender eine
  Datei ausgewählt hat, und nur dort ist „leer" ein Fehler (§4.6).

### `lookup/base.py`
```python
@dataclass
class LookupResult:
    call: str
    name: str | None
    street: str | None
    zip: str | None
    city: str | None
    country: str | None
    grid: str | None
    # QSL-Routing (fürs Via + Feld „Via:"):
    manager: str | None         # qsl_via (HamQTH) / qslmgr (QRZ)
    accepts_bureau: str | None  # HamQTH qsl      ("Y"/"N"/"?")
    accepts_direct: str | None  # HamQTH qsldirect
    lotw: str | None            # HamQTH lotw
    eqsl: str | None            # HamQTH eqsl
    source: str          # "hamqth" | "qrz" | "cache" | "none"

class LookupProvider(Protocol):
    def lookup(self, call: str) -> LookupResult | None: ...

# Menge akzeptierter Wege (B/D/Q/L), kanonisch geordnet; leer -> (default_via,).
def accepted_routes(result, default_via="B") -> tuple[str, ...]: ...
# Höchstpriorisierter aktiver Weg (erster aus active_priority, der akzeptiert ist)
def resolve_route(accepted, active_priority) -> str | None: ...
# Nur ein Manager-Rufzeichen aus dem freien qsl_via/qslmgr-Text ziehen (fürs "Via:")
def extract_manager_callsign(text) -> str: ...
# Aktive Wege (über der Trennlinie) = die ersten `cut` der normalisierten Liste
def active_via_priority(priority, cut) -> list[str]: ...
```
- HamQTH: Session per `u`/`p` holen, dann `id`+`callsign` abfragen; Session ~1h
  gültig, bei Ablauf neu anmelden. Endpunkte/Details in `docs/SPECIFICATION.md`.
- QRZ: nur wenn Credentials gesetzt; ohne bezahltes Abo liefert QRZ nur
  eingeschränkte Felder → als „best effort" behandeln, Fehler nicht fatal.
- `lookup_calls(calls, config, ...)` schlägt **alle** (eindeutigen) Rufzeichen
  nach → Map `CALL -> LookupResult|None`; der Builder füllt daraus je Karte
  `via_routes`/`via_text`/`recipient`. Netz-/Auth-Fehler nie fatal.

### `cards/builder.py`
- `build_cards(qsos, config, lookups=None) -> list[Card]`
- **kein Via-Filter**: baut Karten für **alle** QSOs; `via_routes` via
  `accepted_routes(lookups[call], config.default_via)`, `via_text` =
  `extract_manager_callsign(...)`. Gruppiert nach `config.card_mode`
  (`per_qso`|`per_station`), sortiert deterministisch.
- `effective_via(card, active_priority)` = der tatsächlich zu druckende Weg (oder
  `None` = nicht drucken); einzige Quelle der Wahrheit für Vorschau **und** Export.

### `pdf/generator.py`
- `generate(cards, config, front_image_path, output_path, progress_cb=None) -> list[Path]`
- `config.generation.print_mode`:
  - `"duplex"` → **eine** PDF, pro Karte `draw_front` dann `draw_back` mit
    `showPage()` dazwischen (Seite 1=Front, 2=Back, …; Duplexdruck lange Kante).
  - `"separate"` → **zwei** PDFs (`…_vorderseiten.pdf`, `…_rueckseiten.pdf`) für
    Drucker ohne beidseitigen Druck.
- Liefert die Liste der erzeugten PDF-Pfade zurück.
- `config.generation.sheet_mode` (**quer** zum Druckmodus, beide kombinierbar):
  - `"single"` → eine Karte je PDF-Seite (A6 quer), wie bisher.
  - `"a4_4up"` → vier Karten je PDF-Seite (A4 quer). Der Generator arbeitet
    deshalb **seitenweise** (`layout_sheet.chunk_pages`), nicht kartenweise; der
    Fortschritt zählt weiter in Karten.
- **Druckrand** (`print_margin_*`): steckt **nicht** im Generator, sondern in den
  Zeichenmodulen (`geometry.page_layout` / `content_box`) — dadurch wirkt er auch
  für `scripts/preview_card.py` und direkte API-Aufrufe. Die PDF-Seiten bleiben
  immer A6 bzw. im Bogen A4 (`setPageSize` wird nie aufgerufen, die Größe steht
  beim Anlegen des Canvas).

### `pdf/layout_sheet.py`
- `page_size(config)`, `cards_per_page(config)`, `chunk_pages(items, config)`
- `draw_page(c, config, items, draw_card, *, cut_guides=False)` — verschiebt das
  Canvas je Karte auf ihre Zelle und ruft `draw_card`; **skaliert selbst nichts**
  (das macht `page_layout`, dessen „Seite" im Bogen die Zelle ist).
- `draw_cut_guides(c, layout)` — gestricheltes Schnittkreuz, gezeichnet in
  Bogenkoordinaten, nur auf den **Rückseiten** (siehe §11).

---

## 7. Coding-Konventionen

- **Code + Bezeichner: Englisch.** Doku/Kommentare dürfen Deutsch sein.
- Type Hints überall; `from __future__ import annotations` in jedem Modul.
- Dataclasses statt Dicts für Domänenmodelle.
- **Keine Geschäftslogik in der GUI** — GUI ruft nur `builder`/`generator`.
- Alle Layout-Zahlen (Positionen, Schriftgrößen, Spaltenbreiten) **ausschließlich**
  in `pdf/geometry.py` als benannte Konstanten. Kein „magic number" im Zeichen-Code.
- Fehler beim Lookup/Netz dürfen die PDF-Erzeugung **nie** abbrechen: loggen,
  Feld leer lassen, weitermachen.
- Formatierung: `black` + `ruff`. `python -m pytest` muss grün sein.

---

## 8. Empfohlene Build-Reihenfolge

Baue in dieser Reihenfolge, jeweils mit Tests, bevor es weitergeht:

1. **`config.py` + `config.example.yaml`** — Datenmodell steht damit fest.
2. **`logbook/`** — `models.py`, dann `adif.py`, `cabrillo.py` und die
   Formaterkennung im `__init__.py`; mit `tests/test_adif_parser.py`,
   `test_cabrillo_parser.py`, `test_logbook.py` (Beispiel-Logs in den Tests
   einbetten; Kantenfälle abdecken).
3. **`cards/builder.py`** — Filter + Gruppierung, `tests/test_card_builder.py`.
4. **`pdf/geometry.py`** — Seitenmaße + Layout-Konstanten (Startwerte aus
   `CARD_LAYOUT.md`).
5. **`pdf/layout_back.py`** — Rückseite zeichnen. **Iterativ**: rendern,
   mit `docs/CARD_LAYOUT.md`/Referenzbild vergleichen, Konstanten anpassen.
6. **`pdf/layout_front.py`** — Bild einpassen (Seitenverhältnis wahren, zentriert).
7. **`pdf/generator.py`** — Gesamt-PDF, `progress_cb` für die GUI.
8. **`lookup/*`** — HamQTH zuerst, dann Cache, QRZ optional.
9. **`gui/*`** — zuletzt; verdrahtet die fertigen Bausteine.

So ist alles ohne GUI testbar; die GUI ist nur die Fernbedienung.

---

## 9. Definition of Done (MVP)

- [x] Logdatei wählbar (**ADIF oder Cabrillo**, am Inhalt erkannt), Parser
      liefert korrekte QSO-Liste (Tests grün). Unbrauchbare Datei → Meldung
      statt „0 QSOs".
- [x] Frontbild wählbar + Vorschau.
- [x] Absender-Config editierbar, wird gespeichert/geladen.
- [x] Zustellwege priorisierbar (Liste B/D/Q/L + Trennlinie) und Modus (pro QSO /
      pro Station) wählbar; die Priorität setzt nur die Drucken-Markierung, die
      akzeptierten Wege kommen aus dem Lookup.
- [x] Druckmodus wählbar (Duplex / getrennte Vorder-/Rückseiten-PDFs) inkl.
      einstellbarem **Druckrand** (4 Kanten in mm, hinter „Erweiterte
      Einstellungen"): die Karte wird unverzerrt so eingepasst, dass die Ränder
      exakt frei bleiben.
- [x] **Bogendruck** wählbar: vier A6-Karten auf einem A4-Bogen (quer, 2×2) mit
      gestrichelten Schnitt-Hilfslinien; der Druckrand gilt dabei je Karte, jede
      geschnittene Karte hat ihn ringsum.
- [x] Vorschau-Tabelle zeigt **alle** QSOs mit Via (ausgeschrieben) / Route;
      Lookup-Status sichtbar; bearbeitbare Zellen mit Stift-/Umschalt-Hinweis.
- [x] „PDF erzeugen" liefert eine PDF mit 2 A6-Seiten pro Karte.
- [x] Rückseite entspricht `docs/CARD_LAYOUT.md` (visuell iteriert).
- [x] Auto-Lookup beim Laden bestimmt die akzeptierten Wege {B,D,Q,L} + Manager +
      Adresse für alle Stationen; Cache funktioniert; Ausfälle sind nicht fatal.
- [x] Farbthema (hell/dunkel, folgt dem System) + Programm-Icon; Menüleiste mit
      Datei/Bearbeiten/Aktionen/Ansicht/Hilfe auf macOS, Windows und Linux.
- [x] **Pflichtangaben** (Logbuch, Frontbild, Rufzeichen/Name/Locator/DOK/
      CQ-Zone/ITU) mit rotem `*`; fehlen welche, blockiert „PDF erzeugen" mit
      **einem** Popup und markiert die Stellen rot.
- [x] **Abgelehnte Lookup-Zugangsdaten** werden gemeldet (Hinweisfenster, rote
      Felder in Abschnitt 6) statt nur „0 Stationen gefunden"; der Cache bleibt
      dabei sauber.
- [x] **Anwender-Handbuch** im Programm (`Hilfe ▸ Handbuch`, F1 / ⌘?) aus
      `handbuch.md`, mit Kapitelliste, klickbaren Verweisen und einem „?" je
      Abschnitt, das ins passende Kapitel springt.
---

## 10. Nicht raten — nachschlagen

- ADIF-Feldnamen/Enums: `docs/SPECIFICATION.md` §4.3.
- Cabrillo-Zeilenformat, Modus-Codes, Bandbezeichner: `docs/SPECIFICATION.md`
  §4.5. Vor Änderungen gegen die WWROF-Spezifikation gegenprüfen — vor allem die
  Notiz, dass die Spaltenpositionen **nicht** verbindlich sind.
- Exakte Layout-Koordinaten: `docs/CARD_LAYOUT.md`.
- API-Endpunkte/Session-Flow: `docs/SPECIFICATION.md` §Lookups. Vor Implementierung
  gegen die **aktuelle** HamQTH-/QRZ-Doku gegenprüfen (APIs können sich ändern).

---

## 11. Arbeitsweise & gelernte Fakten (schnelles Wiedereinsteigen)

**Umgebung / Tooling**
- Python liegt im venv: **`.venv/bin/python`** benutzen (Interpreter ist 3.14).
  Abhängigkeiten: `.venv/bin/python -m pip install -r requirements.txt`.
- Vor jedem Commit: `.venv/bin/python -m black qslcards/ tests/ scripts/` und
  `.venv/bin/python -m ruff check ...` und `.venv/bin/python -m pytest tests/ -q`.
- `ruff`/`black` schreiben gelegentlich nach dem Write nach (Trailing-Newline,
  `Callable` aus `collections.abc`, `UP037` Quotes an Annotationen) — einfach
  `black` laufen lassen und ruff-Hinweise übernehmen.

**Ergebnis ansehen (Pflicht: der Nutzer will jedes Ergebnis sehen)**
- Karten-Preview: `.venv/bin/python scripts/preview_card.py` → schreibt
  **`card_preview.pdf`** in den Projekt-Root (gitignored) → mit `open card_preview.pdf`
  zeigen. Beispiel zeigt eine volle 6-Zeilen-Karte ohne Remarks (PA3BRB) und zwei
  Karten mit dynamischem REMARKS-Kasten (3 Karten, 6 Seiten).
  Mit `--4up [RAND_MM]` denselben Satz als **A4-Bogen** (2 Seiten: Vorder-/
  Rückseitenbogen, letzte Zelle leer) — so sieht man Raster, Ränder und
  Schnittlinien in einem Rutsch.
- PDF-Seite als Bild prüfen (kein Display nötig):
  `qlmanage -t -s 1400 -o <ausgabeordner> datei.pdf` erzeugt `datei.pdf.png`.
  Nur Seite 1; für andere Seiten mit `pypdf` (PdfReader/PdfWriter) einzelne Seiten
  heraussplitten. Seitenzahl prüfen: `pypdf.PdfReader(...).pages`.
- **Scratchpad** für temporäre PDFs/PNGs nutzen, nicht den Projekt-Root zumüllen.

**GUI ist headless testbar (macOS, ohne sichtbares Fenster):** `App()` baut den
kompletten Widget-Baum; damit Struktur/Größen prüfen
(`winfo_reqheight`, Variablenwerte), z. B. `THUMB_MAX` gegen Absender-Höhe.
Für Auto-Sync-Tests `app.CONFIG_PATH` auf einen Temp-Pfad setzen, um die echte
`config.yaml` nicht zu überschreiben.

**Aussehen der GUI (Stolperfallen, alle teuer erkauft)**
- **Alle** Farben/Abstände der Oberfläche stehen in `gui/theme.py` — dieselbe
  Regel wie `pdf/geometry.py` fürs Kartenlayout. Basis ist `clam` (nur die
  klassischen ttk-Themes lassen sich voll einfärben; `aqua` ignoriert Farben).
- `restyle_tree` muss **beim Start** laufen, nicht nur beim Themenwechsel: Listbox,
  Canvas und Menüs sind keine ttk-Widgets und behielten sonst die Systemfarben
  (die Auswahl in der Prioritätsliste war deshalb schwarz).
- `clam` kennt **kein** `indicatorcolor` — Radio-/Checkbuttons färbt man über
  `indicatorbackground`/`indicatorforeground`. Eine Zuweisung an `indicatorcolor`
  schlägt nicht fehl, sie wirkt nur nicht.
- Transparente Icons in der Tabelle werden gegen den Hintergrund ihres **Labels**
  gemischt, nicht gegen die Zeile darunter → je ein Style pro Untergrund
  (`TreeIconHead/Odd/Even/Selected`), sonst liegt ein Kästchen auf der Zeile.
- **Tk bildet 1 Bildpixel auf 1 Tk-Punkt ab.** Auf Retina (hier 1440 Punkte auf
  2560 Pixeln) skaliert macOS jedes Bitmap ~1,8× hoch — eine größere PNG-Datei
  hilft **nicht**, das Bild würde nur proportional größer. Scharf wird es nur als
  Canvas-Vektor (`icon_canvas.py`, gegen das SVG getestet).
- `wm iconphoto` bekommt die PNGs **größte zuerst**: macOS skaliert das *erste*
  übergebene Bild auf alle Größen (mit 16 px zuerst wirkt das Dock-Icon pixelig).
- Mausrad: X11 meldet ab **Tk 9** `<MouseWheel>` statt `<Button-4/5>` (TIP 474) —
  beides zu binden scrollt doppelt (`scrolling.py` unterscheidet). Scrollbare
  Kinder dürfen das Ereignis nur verschlucken, solange sie selbst scrollen können.
- **`rowspan` verrückt die Nachbarn.** Ein ein-/ausblendbarer Block, der per
  `rowspan` über fremde Zeilen greift, lässt Tk seine Höhe auf genau diese Zeilen
  verteilen — beim Aufklappen springen die Widgets daneben auseinander (so
  passiert in Abschnitt 9 mit den Druckmodus-Radiobuttons). Lösung: **je einen
  eigenen Container pro Spalte**, beide in derselben Grid-Zeile mit `sticky="nw"`,
  ganz ohne `rowspan`. Ein Test vergleicht dafür `winfo_rootx/y` vor und nach dem
  Umschalten.
- **Ein-/ausblendbare Blöcke halten ihren Platz frei.** Sonst wächst der Abschnitt
  beim Aufklappen und schiebt alles darunter weg — das Fenster springt, nur weil
  Optionen sichtbar werden. `PrintModeSection._reserve_margin_space` misst den
  Randblock einmal (`update_idletasks`, weil `grid` die angeforderte Größe erst im
  Leerlauf berechnet) und setzt ihn als `minsize` der Grid-Zeile.
- **Ein Tag färbt keine ausgewählte Zeile.** In der Vorschautabelle überdecken die
  Auswahlfarben (`style.map("Treeview", ...)`) die Tag-Farben — „Drucken: Ja → Nein"
  blieb deshalb hell, bis die Auswahl woanders hinwanderte. Lösung: der Klick in
  die Spalte „Drucken" gibt `"break"` zurück (wählt also nicht aus) und
  `_toggle_print` nimmt die Zeile aus einer bestehenden Auswahl.
- Ein per `withdraw()` verstecktes Fenster nimmt **keine** synthetischen
  Tastenereignisse an — Testfenster off-screen öffnen (`geometry("+3000+3000")`),
  sonst sieht ein funktionierendes Kürzel wie ein kaputtes aus.
- Screenshots der laufenden App sind hier **nicht** möglich (`screencapture`
  scheitert ohne die macOS-Berechtigung „Bildschirmaufnahme"). Optische Änderungen
  headless prüfen (Style-Werte, `winfo`-Maße) und den Nutzer draufschauen lassen.
- **Ein Toplevel ohne eigenes Menü ist auf macOS nicht menülos.** Tk setzt dann
  seine Standardleiste ein — mit „Python"-Programmmenü und Tk-Hilfeeinträgen. Ein
  eigenes Fenster bekommt deshalb `configure(menu=<Menüleiste des Hauptfensters>)`;
  Tk legt sich dafür intern einen Klon an, das Hauptfenster behält seine.
  Das gilt auch für eine gebündelte App — nur der Menütitel heißt dann wie das
  Bundle statt „Python" (der Titel kommt vom Prozess, Tk kann ihn nicht setzen).

**Handbuch (`gui/help.py` + `handbuch.md`)**
- Der Text liegt **neben dem Programm** (`handbuch.md`, wie `config.yaml`), nicht
  im Paket: der Nutzer soll ihn im Editor lesen und ergänzen können. Genau **eine**
  Datei — zwei Kopien wären zwei Wahrheiten. Fehlt sie, zeigt das Fenster einen
  Hinweis (selbst erzeugtes Markdown), keine Ausnahme.
- Der Renderer kann **nur**, was das Handbuch braucht (siehe `SPECIFICATION.md`
  §2.5). Deshalb dort **keine Tabellen** — die Tastenkürzel sind bewusst eine
  Aufzählung. Verschachtelte Auszeichnung geht nicht: `**` in einer
  Link-Beschriftung wird entfernt.
- **Erst zusammenfügen, dann auszeichnen.** Ein `**fett**`, das im Quelltext über
  den Zeilenumbruch reicht, zerriss anfangs in zwei Hälften und stand roh im
  Fenster. Absätze *und* Aufzählungspunkte sammeln ihre Zeilen erst komplett.
- **Anker sind der Vertrag zur Oberfläche**: `{#abschnitt-N}` ist das Sprungziel
  des „?" von Abschnitt N. Bewusst explizit statt aus dem Überschriftentext
  abgeleitet — sonst bricht jedes Umbenennen still die Kontexthilfe. Preis: die
  IDE kennt diese Pandoc-Syntax nicht und meldet „Cannot resolve anchor"; das ist
  eine Falschmeldung. Zwei Tests halten dagegen (jeder Abschnitt hat seinen Anker,
  jeder interne Verweis trifft ein Ziel).
- **Kapitelliste am unteren Anschlag**: dort zählt die **letzte** Zeile, sonst die
  oberste. Die letzten Kapitel sind kürzer als das Fenster — oben stünde beim
  Herunterscrollen für immer das vorletzte.
- Das „?" hängt `sections.add_section_help` an; `app.py` verteilt es zentral über
  `self._sections` an alle zehn Rahmen, **kein** Abschnitts-Konstruktor weiß davon.
  Mauszeiger `hand2` (`question_arrow` war kurz gesetzt und sah auf macOS falsch aus).
- Das Fenster ist **nicht modal** (Nachlesen beim Ausfüllen) und lädt bei
  `<FocusIn>` nach einer mtime-Änderung neu. Eine Fußleiste mit „Schließen"/„Im
  Editor öffnen" gab es kurz und wurde vom Nutzer verworfen — das macht die
  Fenstersteuerung des Systems.

**Layout-Wahrheit**
- **Alle** Layout-Zahlen stehen in `pdf/geometry.py` (maßgeblich; `docs/CARD_LAYOUT.md`
  ist nur Beschreibung). Positionen als `yt` (von oben), Umrechnung in den
  `text`/`checkbox`/`_box`-Helfern. Font-Metriken (`getAscent`/`getDescent`) statt
  Magic-Faktoren fürs Zentrieren.
- **DejaVuSans** (regular+bold) liegt gebündelt in `qslcards/assets/fonts/` und wird
  in `geometry.py` registriert (Umlaute); Fallback Helvetica, Registrierung nie fatal.
- **Druckrand = `PageLayout`, nicht neue Konstanten.** Die Konstanten beschreiben
  weiter die Karte auf voller A6-Fläche; `geometry.page_layout(config)` leitet
  daraus den eingerückten Rahmen ab und `draw_back` reicht ihn an **alle** Helfer
  weiter. Die Y-Spiegelung ist deshalb `page.page_h - yt` (nicht `PAGE_H - yt`) —
  wer das zurückdreht, bricht den Druckrand still. Ohne Druckrand ist der
  `PageLayout` die Identität; ein Test vergleicht die Content-Streams byteweise.

**Wichtige, mit dem Nutzer getroffene Entscheidungen (nicht ohne Rückfrage kippen)**
- **Zeilen je Karte hängen am Remarks-Zustand (dynamisch)**: ohne Remarks
  `MAX_ROWS_PLAIN = 6`, mit Remarks `MAX_ROWS_WITH_REMARKS = 3` (der REMARKS-Kasten
  braucht darunter Platz; `MAX_ROWS = MAX_ROWS_PLAIN` ist der Layout-Cap). Koppelt
  Layout **und** Builder; die Rückseiten-Tabelle zeichnet genau so viele Zeilen,
  wie die Karte QSOs hat (feste `ROW_H`, mitwachsende Höhe), `per_station` fasst
  entsprechend viele QSOs zusammen (Überlauf → Folge-Karte). Werte nur als
  Konstanten in `geometry.py`, **kein** GUI-Widget (so mit dem Nutzer vereinbart).
- **REMARKS dynamisch + je Karte**: der REMARKS-Kasten erscheint nur, wenn die
  Karte einen Text hat (`card.remarks`). Globales Feld in GUI-Abschnitt 7
  (`generation.remarks`, alle Karten), je Karte in der Vorschau überschreibbar,
  **max. 80 Zeichen** (`REMARKS_MAX_LEN`). Remarks sind **pro Karte unabhängig**:
  `normalize_station_cards` lässt Karten mit Remarks eigenständig und führt nur
  aufeinanderfolgende Karten **ohne** Remarks wieder zusammen. Sicherung pro Karte
  zusätzlich im Generator (`regroup_card_by_remarks`). Vom Nutzer iterativ so
  bestätigt (Split beim Setzen, Merge beim Leeren, Einzel-Remarks möglich).
- **Pflichtangaben: Stern, ein Popup, Markierung erst nach dem Druckversuch**
  (Abschnitte 1, 2, 3; mit dem Nutzer so abgestimmt):
  * Pflicht sind **Logbuch**, **Frontbild** und im Absender **Rufzeichen, Name,
    Locator, DOK, CQ-Zone, ITU** (`sections.REQUIRED_SENDER_FIELDS`) — Adresse
    und Funk-Ausrüstung bewusst **nicht**.
  * Roter `*` (`Required.TLabel`, Farbe `danger`) im Titel von Abschnitt 1/2 und
    an den Beschriftungen in Abschnitt 3. Die Fußnote „* Pflichtfeld" steht
    **ganz unten im Fenster** (außerhalb des Scrollbereichs, über der
    Statusleiste): in Abschnitt 3 sah sie aus, als gälte sie nur dort.
  * **Ein** Popup listet alles Fehlende auf einmal (Abschnittsreihenfolge) und
    scrollt zur ersten Fundstelle; die Markierung (`Invalid.TEntry` /
    `Invalid.Thumb.TLabel`) kommt **erst nach dem Klick** auf „PDF erzeugen" —
    beim ersten Start wäre sonst das halbe Fenster rot — und geht je Feld weg,
    sobald es gefüllt ist. Der Button bleibt bedienbar (kein Sperren).
  * `Invalid.TEntry` braucht eine eigene `style.map`, sonst überschreibt die
    geerbte `TEntry`-Map den roten Rahmen bei Fokus/Hover.
- **Keine Erklärtexte in den Abschnitten**: die Hinweiszeilen unter der
  Prioritätsliste (4) und den Zugangsdaten (6) sowie die Klammern
  „(optional)"/„(für alle Karten)" in Abschnitt 3 wurden vom Nutzer verworfen —
  neue Erklärtexte nur auf ausdrücklichen Wunsch.
- **GUI-Abschnitte**: 1 Logbuch (ADIF/Cabrillo), 2 Frontbild, 3 Absender (inkl. Funk-Ausrüstung +
  globale Markierungen QSL/Portabel/Bestätigung), 4 Zustellwege (priorisierbare
  Liste + Trennlinie), 5 Kartenmodus, 6 Lookups, **7 Bemerkungen**, 8 Vorschau,
  9 Druckmodus (inkl. Bogendruck + Druckrand), 10 Ausgabe.
- **Druckrand: vier Werte, keine Verzerrung, Überschuss ins Layout** (iterativ mit
  dem Nutzer erarbeitet, alle drei Punkte bewusst so entschieden):
  * **Vier einzelne Kanten** (oben/unten/links/rechts), nicht ein Wert für alle —
    Drucker lassen unten oft mehr Rand. Bedeutung: „so viel Rand **muss** sein".
  * **Nie verzerren.** Ein einziger Faktor für beide Achsen. Die Alternative
    („exakt in den Rahmen dehnen", ~3–7 % Stauchung) war zwischenzeitlich gewählt
    und wurde vom Nutzer wieder verworfen.
  * **Der Überschuss auf der freien Achse fließt ins Layout** (Call-/Via-Box,
    Tabellenspalten anteilig, Remarks-Kasten; Fuß an der Unterkante verankert),
    nicht in einen breiteren Rand — die Karte zentriert stehen zu lassen wurde
    ausdrücklich abgelehnt. Deshalb stimmen alle vier Ränder auf den Millimeter.
  * **Frontbild rückt mit ein** (deckungsgleich mit der Rückseite), bleibt dabei
    aber unverzerrt: Cover-Fit **in den Rahmen**, kein Dehnen.
  * `MAX_ROWS_*` bleibt unberührt — Kartenaufteilung ändert sich nie mit dem Rand.
- **Bogendruck: 4 Karten auf A4, Rand je Karte, Schnittlinien nur hinten**
  (`sheet_mode`, in zwei Runden mit dem Nutzer korrigiert — die verworfenen
  Varianten stehen bewusst mit da, sie sehen auf dem Papier plausibel aus):
  * **Das 2×2-Raster hängt an nichts.** Der Bogen wird immer in vier Zellen à
    148,5 × 105 mm geteilt (ein Viertel von A4 = das echte ISO-A6-Maß; die Karte
    selbst ist auf 148 × 105 gebaut, der halbe Millimeter geht ins Layout).
    Die Zelle tritt an die Stelle der A6-Seite, den Rest macht das gewohnte
    `content_box`/`page_layout`. `layout_sheet` **verschiebt nur**.
  * **Der Druckrand gilt je Karte, nicht je Bogen.** Zwischen zwei Karten liegt
    dadurch der doppelte Rand, die Schnittkante läuft mittig hindurch — so hat
    jede geschnittene Karte ihn auf allen vier Seiten. *Verworfen:* Rand einmal
    um den ganzen Bogen (erst so gebaut). Dann hat jede Karte ihn nur auf ihren
    zwei äußeren Kanten und der Inhalt sitzt außermittig.
  * *Verworfen (Zwischenstand):* den 2×2-Block als starres A6-Raster skalieren
    und zentrieren. Weil das Seitenverhältnis des Blocks nicht zum bedruckbaren
    Bereich passt, wurde der Rand auf einer Achse größer (bei 5 mm Einstellung
    7,55 mm links/rechts) — genau der Fehler, den die Elastik der Einzelkarte
    schon löst.
  * **Schnitt-Hilfslinien nur auf den Rückseitenbogen** (gestrichelt, 0,3 pt,
    50 % grau, 2/2 mm): dort liegt an der Schnittkante Weißraum, über dem
    randlosen Frontbild bliebe bei schiefem Schnitt ein Strich stehen. Sie laufen
    über den ganzen **bedruckbaren** Bereich (nicht nur über den Kartenblock),
    sonst muss man das letzte Stück schätzen. Auch der angebrochene letzte Bogen
    bekommt sein Kreuz.
  * **Front/Rück-Zuordnung ist beim Wenden egal** — projektbedingt gilt *ein*
    Frontbild für alle Karten, alle vier Vorderseiten eines Bogens sind also
    identisch. Deshalb **keine** gespiegelte Zellenreihenfolge (gleiche
    Begründung wie beim Druckmodus „separate"). Leere Zellen auf dem letzten
    Bogen bleiben leer.
- **Absender kommt komplett aus der Config** (Rufzeichen, Locator, DOK, …), nie
  aus dem Log — vom Nutzer bewusst so bestätigt (ein kurzer Versuch, Rufzeichen/
  Locator aus `STATION_CALLSIGN`/`MY_GRIDSQUARE` zu ziehen, wurde zurückgenommen).
- **Kein `subtitle`/„Responsive"** — komplett entfernt.
- **Front im Cover-Modus** (füllt die Seite randlos, Überstand wird geclippt).
- **`drawImage` bekommt den Dateipfad, nie ein `ImageReader`** (`layout_front.py`).
  ReportLab hasht ein `ImageReader` sonst bei **jedem** Aufruf komplett (MD5 über
  die entpackte Bitmap): gemessene 119 ms je Seite statt 4,6 ms, bei 3525 Karten
  308 s statt 4,6 s, und die PDF wird 22 statt 6,6 MB groß (mit Pfad wandert ein
  JPEG unverändert hinein). Pillow liefert nur noch die Maße für den Cover-Fit.
  Ein Test hält das fest — er prüft den **Aufruf**, nicht die Wirkung: dass das
  Bild nur einmal im Dokument landet, stimmt auch mit `ImageReader`.
- `MARGIN = 3 mm`; Portabel-Kennung `/p`/`/m`/`/t`/`/r` **hinter dem eigenen
  Rufzeichen**; Bestätigungs-Markierung (Confirming QSO/SWL) oben mittig;
  Stationsdaten als Label/Wert-Spalte neben der Adresse; Funk-Block (RIG/ANT/PWR)
  dynamisch darunter; REMARKS über volle Breite; Fuß unten mit ~3 mm Rahmenabstand.
- **GUI: keine Speichern/Laden-Buttons** — Config wird automatisch gespeichert
  (debounced) und bei externer Datei-Änderung neu geladen (mtime-Poll, Loop-Schutz
  via `_suppress_save`). Enter in Eingabefeldern gibt den Fokus frei.
  **Achtung:** `_gather_config()` baut die Config aus den Widgets — Felder ohne
  Widget (`appearance`, `recent`) müssen aus `base_config` übernommen werden,
  sonst löscht der nächste Auto-Save sie.
- **Farbthema „Funk-Blau"** (Akzent `#1F6FEB` hell / `#4C93FF` dunkel), hell +
  dunkel, Default folgt dem System. Bewusst **gleiches Aussehen auf allen
  Plattformen** statt nativem macOS-Look.
- **Icon-Farben folgen NICHT dem Thema** (blaue Fläche, weiße Karte) — ein
  Programmsymbol muss dem Dock-/Taskleisten-Icon entsprechen.
- **Zeichenzähler** der Bemerkung zeigt „x/80" und hebt bei erreichtem Limit in der
  **Akzentfarbe** hervor, nicht in der Warnfarbe (Limit ist kein Fehler).
- **Kein „Alle/Keine Karten drucken"** im Menü — vom Nutzer als überflüssig
  verworfen; Karten werden über die Spalte „Drucken" bzw. die Trennlinie gesteuert.
- **Keine Entwicklerdokumente im Hilfe-Menü.** README/Spezifikation/Karten-Layout
  standen dort einmal und wurden vom Nutzer ausdrücklich entfernt: das Menü
  „Hilfe" gehört dem Anwender, dafür gibt es das Handbuch. Nicht zurückholen.
- **Cabrillo-Import** (alle vier Punkte vorab mit dem Nutzer abgestimmt):
  * **Paket `logbook/` statt `adif/`** — ein Zuhause für `QSO`. Ein
    Cabrillo-Parser, der sein Modell aus dem *ADIF*-Paket holt, wäre ein
    schiefer Vertrag. Kein Kompatibilitäts-Shim: zwei Importwege wären zwei
    Wahrheiten. Der Dispatcher liegt im `__init__.py` — dieselbe Form wie
    `lookup/__init__.py` (Teile in Modulen, Fassade im Paket-Kopf).
  * **Beschriftung „Logbuch (ADIF/Cabrillo)"** in Abschnitt 1, im Sprungmenü und
    im Handbuch; der Menüeintrag heißt kurz „Logbuch öffnen…" (die Formatliste
    gehört in den Dateidialog, nicht in einen Verb-Eintrag).
  * **`X-QSO:` wird mitimportiert**, nicht übersprungen — vom Nutzer so
    entschieden: das QSO hat stattgefunden, gestrichen wird meist wegen eines
    Regelverstoßes auf der *eigenen* Seite, die Gegenstation bekommt ihre Karte.
    Markiert in `raw["cabrillo_x_qso"]`; abwählbar über die Spalte „Drucken".
  * **Modus-Kurzcodes werden übersetzt** (PH→SSB, RY→RTTY, DG→DIGI); der Rohcode
    bleibt in `raw["cabrillo_mode"]`. Auf der Karte soll „SSB" stehen, nicht „PH".
- **Leeres/unlesbares Logbuch ist ein Fehler, keine Antwort.** Bis dahin zeigte
  ein leeres ADIF „0 QSOs geladen"; jetzt kommt für beide Formate eine Meldung
  (`LogFormatError`, getrennt von `OSError`) und die bisher geladenen QSOs
  bleiben stehen. `SPECIFICATION.md` §8 forderte das ohnehin schon.

**Realität der Testdaten (`Log.adi`)**
- Enthält **kein** `QSL_SENT_VIA` (und keine Via-Info) — das ist der **Normalfall**:
  die Via kommt aus dem Lookup, nicht aus dem Log. Ohne Lookup-Credentials fallen
  alle Karten auf `default_via` (Default `B`); mit Credentials liefert der Lookup
  je Station die akzeptierten Wege {B,D,Q,L}. Jede Station kommt nur 1× vor.
- FT8-QSOs haben dB-Rapporte (z. B. `-07`), die **bewusst** nicht sinnvoll ins
  R/S/T-Raster passen (so vom Nutzer akzeptiert).
- Für Cabrillo gibt es **kein** Beispiel-Log im Repo: die Testfälle stehen inline
  in `tests/test_cabrillo_parser.py`, je einer pro Contest-Template. Zum
  Ausprobieren ein gemischtes Log im Scratchpad anlegen, nicht im Projekt-Root.
- **Ein Contest-Log ist groß** (500–5000 QSOs) — gemessen (5000 QSOs, 3525
  Karten, Bogendruck): Parser 95 ms, `build_cards` 32 ms, Vorschautabelle
  122 ms, PDF 4,6 s. Alles linear, die GUI bleibt bedienbar. Der Engpass war die
  PDF-Erzeugung (308 s) und lag am `ImageReader` (siehe oben), nicht am Umfang.
- **Der Lookup ist die eigentliche Geduldsprobe** und bleibt es: 3500 eindeutige
  Rufzeichen bedeuten 3500 HamQTH-Abfragen. `LookupCache.set()` schreibt dabei
  je Rufzeichen die ganze JSON-Datei neu (quadratisch: 0,7 s bei 700, 16,4 s bei
  3500 Einträgen) — das **bleibt bewusst so**: neben zwanzig Minuten Netzzeit
  fällt es nicht ins Gewicht, und das sofortige Schreiben macht den Cache
  absturzsicher (ein abgebrochener Lauf behält jedes geholte Rufzeichen). Beim
  zweiten Laden mit warmem Cache wird gar nicht mehr geschrieben.

**Workflow-Konventionen**
- Branch **`build/mvp`**. **Nicht selbst committen** — erst nach Review; committen,
  wenn der Nutzer die nächste Aufgabe vorschlägt. Commit-Messages Deutsch, Präfixe
  `feat/fix/docs/chore`, GUI-Zwischenstände als **WIP** markieren.
- IDE-Dateien (`.idea/`, `.DS_Store`) nie mitcommitten.
- Doku-Änderungen erst nach Abnahme des Codes.
