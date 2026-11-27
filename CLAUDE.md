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
  Empfänger-/Routing-Daten aus **QRZ** (erste Wahl) bzw. **HamQTH** (zweite Wahl,
  einzige Quelle der Zustellweg-Flags; ergänzt QRZ, siehe §5.7).
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
- **Most-Wanted-Filter** (optional, GUI-Abschnitt 7): nur Karten an die
  gesuchtesten DXCC-Gebiete der **GDXF-Liste** (https://gdxf.de/mostwanted/),
  Top N je Kategorie. Das DXCC-Gebiet kommt aus dem Log-Feld `DXCC`, sonst aus der
  mitgelieferten **`cty.dat`** (AD1C) — damit auch für Cabrillo und ohne Lookup.

---

## 2. Technik-Stack

| Zweck              | Wahl                          | Begründung                                   |
|--------------------|-------------------------------|----------------------------------------------|
| Sprache            | Python **3.11+**              | `tomllib`, moderne Typing-Syntax             |
| GUI                | **Tkinter** (stdlib)          | vorgegeben, keine Extra-Abhängigkeit         |
| PDF                | **ReportLab**                 | präzise mm-genaue Positionierung, A6, Tabellen |
| Bilder             | **Pillow**                    | Skalierung/Format des Frontbilds             |
| HTTP/Lookups       | **requests**                  | HamQTH-/QRZ-XML-API                           |
| Config             | **PyYAML** (`config.yaml`)    | lesbar und diff-bar; **vom Programm** gepflegt, nicht von Hand (§11) |
| Tests              | **pytest**                    | Unit-Tests, v.a. Parser & Kartenlogik        |
| Bündeln            | **PyInstaller ≥ 6.21**        | einzige Option mit Tcl/Tk 9 + allen drei Zielsystemen |

Bewusst **kein** externes Parser-Package (weder ADIF noch Cabrillo): eigene,
getestete Parser (Anforderung).

---

## 3. Projektstruktur

```
qslcards/
  __init__.py             # __version__ (einzige Quelle, pyproject liest sie aus)
  __main__.py             # `python -m qslcards`
  main.py                 # Einstiegspunkt: GUI starten (+ Protokoll im Bündel)
  paths.py                # ALLE Datei-/Verzeichnispfade (Bündel vs. Quelle)
  config.py               # Config-Dataclasses + Laden/Speichern (YAML, atomar + .bak)
  fileio.py               # atomic_write_text (Temp-Datei + os.replace)
  redact.py               # Zugangsdaten aus Log-/Fehlertexten maskieren
  controllers/            # Abläufe OHNE Tk (testbar ohne Xvfb)
    session.py            # SessionState (QSOs/gesendete/Lookups/Markierungen)
    lookup_runner.py      # Hintergrund-Lookup: Generation, Warteschlange, Abbruch
    background.py         # run_in_background(schedule, work, done)
    config_file.py        # config.yaml lesen/speichern/mtime-Überwachung
    mostwanted_flow.py    # GDXF-Liste + cty.dat: laden, abrufen, Statuszeile
    wavelog_flow.py       # Client, Abruf, Sicherheitsnetz (wavelog_sent.json)
    print_job.py          # PDF-Erzeugung im Hintergrund
  wavelog/
    client.py             # API v2: Stationen, QSOs, PATCH qsl_sent (429/Retry)
    sent_store.py         # wavelog_sent.json: selbst markierte + offene IDs
    secret.py             # API-Key im System-Schlüsselbund (optional)
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
    secret.py             # QRZ/HamQTH optional im Schlüsselbund (seit 0.4.0)
  mostwanted/
    __init__.py           # Fassade + CATEGORY_LABELS
    models.py             # MostWantedList/RankedEntity/MostWantedFilter, Mode->Kategorie
    gdxf.py               # GDXF-Seite abrufen (1 POST, show=500) + HTML-Parser
    store.py              # mostwanted.json: laden/speichern, Neuladen nach 30 Tagen
  dxcc/
    __init__.py
    cty.py                # Rufzeichen -> DXCC über cty.dat + Nummerntabelle
    store.py              # cty.dat: gespeichert > mitgeliefert, Neuladen nach 14 Tagen
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
    app.py                # Hauptfenster: Aufbau, Verdrahtung, Config, Logbuch/Bild
    app_cards.py          #   Mixin: Karten bauen, Drucken-Markierung, Most Wanted
    app_lookup.py         #   Mixin: Lookups anstoßen/anzeigen, Schlüsselbund
    app_wavelog.py        #   Mixin: Wavelog-Knöpfe, Hinweise, Markieren
    app_print.py          #   Mixin: Pflichtangaben, PDF erzeugen/öffnen
    config_form.py        # Eingabefelder <-> AppConfig (apply/gather/watched_vars)
    steps.py              # Schritte des Assistenten + SECTION_STEP
    wizard.py             # Schritt-Assistent (Kopfleiste, Seiten, Navigation)
    desktop.py            # Datei öffnen/zeigen, Programm-Icons
    scrollframe.py        # scrollbare Seite; set_fill() für die Vorschau
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
    dxcc/                 # cty.dat (AD1C, MIT) + dxcc-numbers.csv + LICENSE-cty.txt
tests/
  test_adif_parser.py     test_theme.py
  test_cabrillo_parser.py test_menu.py
  test_logbook.py         test_icon_canvas.py
  test_card_builder.py    test_scrolling.py
  test_lookup.py          test_textedit.py
  test_geometry.py        test_gui.py
  test_config.py          test_help.py
  test_generator.py       test_paths.py
  test_layout_back.py     test_build_app.py
  test_release.py         test_mostwanted.py
  test_dxcc.py
scripts/
  preview_card.py         # Karten-Preview als PDF (`--4up [RAND_MM]` = A4-Bogen)
  make_icon.py            # app_icon.svg -> PNG (16–1024) + .ico + .icns
  build_app.py            # auslieferbare Anwendung bauen + verpacken
  release.py              # Version anheben -> Tests -> bauen -> Commit + Tag
  mock_wavelog.py         # Mini-Wavelog (API v2) zum Ausprobieren/Testen
  wavelog_check.py        # Prüfung gegen eine ECHTE Instanz (Bericht als Fixture)
.gitlab-ci.yml            # CI: ruff, black --check, pytest/xvfb, uv-Python mit Tk 9
.github/workflows/        #   dasselbe für GitHub
CHANGELOG.md              # Änderungen je Version (Pflege bei jedem Release)
packaging/
  qslcards.spec           # PyInstaller: eine Spec für alle drei Plattformen
  linux/                  # .desktop, install.sh, LIESMICH.txt, Dockerfile.fedora,
                          #   README (python3.14 statt python3, glibc, Prüfliste)
  windows/                # build.ps1, LIESMICH.txt, README (Python, SmartScreen)
  macos/                  # LIESMICH.txt, README (Tk-Herkunft, Gatekeeper, ditto)
                          #   kein Bauskript — build_app.py genügt hier
config.example.yaml       # Vorlage = genau das, was config.save(AppConfig())
                          #   schreibt (Test hält das fest). Fällt zurück, solange
                          #   es noch keine config.yaml gibt.
handbuch.md               # Anwender-Handbuch (zeigt „Hilfe > Handbuch" an)
.dockerignore             # Build-Kontext für Dockerfile.fedora klein halten
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
   └─> je CALL: akzeptierte Wege {B,D,Q,L} + Manager + Adresse (+ DXCC)
cty.dat (mitgeliefert/gespeichert) ──> je CALL: DXCC-Nummer (ohne Netz)
                            │
                            ▼
        builder(alle QSOs, via_routes aus Lookup, DXCC Log>cty>Lookup,
                Gruppierung) ──> [Card, ...]
                                                    │
Config (Absender) ──────────────────────────────────┤
Frontbild ──────────────────────────────────────────┤
GDXF-Liste (mostwanted.json, nur bei Filter an) ────┤
                                                    ▼
GUI: Priorität + Trennlinie + Most Wanted (is_printable)
                       ──> generator ──> PDF(s) (+ Adress-CSV)
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
   nur in den **optionalen Adress-/Label-Export**. Der umfasst genau die
   **gedruckten** Karten (Spalte „Drucken: Ja"), nicht alle nachgeschlagenen
   Stationen: die CSV liefert die Etiketten zum Stapel, der gerade entsteht.
5. **Lookup läuft automatisch** beim Log-Laden für **alle** Stationen im
   Hintergrund-Thread (kein `lookup_addresses`-Schalter), sofern QRZ-/HamQTH-
   Zugangsdaten eingetragen sind; sonst kein Netzcall und alle Via =
   `default_via`. Die **Zugangsdaten stehen nicht in der Config** — sie leben nur
   zur Laufzeit in `LookupCredentials` und werden je Sitzung neu eingegeben (§11).
   Ergebnisse (auch negative) werden gecacht (`lookup/cache.py`). „PDF erzeugen"
   ist gesperrt, bis der Lookup fertig ist; „Neu abrufen" holt Fehlende nach.
6. **Karte pro QSO vs. pro Station**: Bei „pro Station" werden alle QSOs mit
   demselben Call (innerhalb desselben Via) zu **einer** Karte zusammengefasst;
   die Tabelle bekommt dann **mehrere Zeilen** (max. Zeilenzahl aus
   `CARD_LAYOUT.md`, Rest ggf. Folge-Karte).
7. **Anbieter-Reihenfolge: QRZ zuerst, HamQTH danach** — und die Kette
   **ergänzt**, statt beim ersten Treffer abzubrechen. QRZ liefert Adresse und
   Manager, aber prinzipiell **keine** Zustellweg-Flags; die kommen nur von
   HamQTH. Bei reinem Abbruch hätte jede von QRZ gefundene Station eine leere
   Wegemenge und fiele auf `default_via` — Abschnitt 4 liefe leer. Der erste
   Treffer gewinnt bei seinen Feldern, die folgenden Anbieter füllen die Lücken
   (`source` = z. B. `"qrz+hamqth"`). Preis: mit beiden Zugangsdaten wird fast
   jede Station **zweimal** abgefragt, der Lookup dauert rund doppelt so lange.
8. **Most Wanted: Rangliste allein von der GDXF, DXCC aus Log > cty.dat >
   Lookup.** Ist der Filter an, wird eine Karte nur gedruckt, wenn sie einen
   aktiven Zustellweg hat **und** ihr Gebiet unter den ersten `top` Rängen liegt
   (`builder.is_printable`). Kategorie `auto` misst jedes QSO an der Liste seines
   Modes, `mixed` alle an Mixed, `cw`/`phone`/`digital` zählen **nur** QSOs in
   dieser Betriebsart. Karte „pro Station" = bester Rang. **Unbekanntes Gebiet
   oder keine Liste → nicht drucken.** Der Rang steht nie auf der Karte.

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
    dxcc: str | None           # ADIF-Feld DXCC (roh); Cabrillo: immer None
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
    dxcc: str | None            # HamQTH adif / QRZ dxcc (NICHT adr_adif/ccode)
    source: str          # "hamqth" | "qrz" | "cache" | "none"

@dataclass
class LookupCredentials:   # NUR zur Laufzeit — nie in AppConfig/config.yaml
    hamqth_user: str = ""
    hamqth_pass: str = ""
    qrz_user: str = ""
    qrz_pass: str = ""
    program_id: str = "qslcards"   # füllt die GUI aus LookupConfig.program_id

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
- **Reihenfolge: QRZ zuerst, HamQTH danach** (§5.7). Eingehängt wird nur, wer
  Zugangsdaten hat. `ChainedLookup` **ergänzt**: der erste Treffer gewinnt bei
  seinen Feldern, die folgenden Anbieter füllen nur die Lücken
  (`LookupResult.merged_with`, Feldliste `base.DATA_FIELDS`); ist nichts mehr
  offen (`missing_fields()`), wird der Rest nicht gefragt.
- QRZ: ohne bezahltes Abo nur eingeschränkte Felder → „best effort", Fehler nicht
  fatal. Liefert **nie** Zustellweg-Flags.
- HamQTH: Session per `u`/`p` holen, dann `id`+`callsign` abfragen; Session ~1h
  gültig, bei Ablauf neu anmelden. Endpunkte/Details in `docs/SPECIFICATION.md`.
- Die Clients heißen `QRZClient` und `HamQTHClient` (`lookup/qrz.py`,
  `lookup/hamqth.py`); `VIA_CODES` (kanonische Reihenfolge `B, D, Q, L`) und
  `VIA_LABELS` (ausgeschriebene Namen für GUI und Vorschau) stehen im Paketkopf,
  damit Prioritätsliste und Tabelle dieselbe Quelle benutzen.
- `has_lookup_credentials(credentials)` / `build_lookup(credentials, cache_path)`
  / `lookup_calls(calls, credentials, ...)` nehmen alle **`LookupCredentials`**,
  nicht `LookupConfig`. `lookup_calls` schlägt **alle** (eindeutigen) Rufzeichen
  nach → Map `CALL -> LookupResult|None`; der Builder füllt daraus je Karte
  `via_routes`/`via_text`/`recipient`. Netz-/Auth-Fehler nie fatal.

### `cards/builder.py`
- `build_cards(qsos, config, lookups=None, *, resolve_dxcc=None) -> list[Card]`
  — `resolve_dxcc(call) -> int | None` ist die cty.dat (`CtyDatabase.dxcc`);
  `card.dxcc` = Log-Feld > `resolve_dxcc` > `lookups[call].dxcc`.
- **kein Via-Filter**: baut Karten für **alle** QSOs; `via_routes` via
  `accepted_routes(lookups[call], config.default_via)`, `via_text` =
  `extract_manager_callsign(...)`. Gruppiert nach `config.card_mode`
  (`per_qso`|`per_station`), sortiert deterministisch.
- `effective_via(card, active_priority)` = der tatsächlich zu druckende Weg (oder
  `None` = nicht drucken).
- `is_printable(card, active_priority, mostwanted=None)` = Drucken-Voreinstellung:
  `effective_via` **und** (Filter an) Most-Wanted-Regel; einzige Quelle der
  Wahrheit für die Vorschau, der Export druckt genau die „Ja"-Zeilen.
  `mostwanted_rank(card, rule)` = Rang für die Spalte „MW".

### `mostwanted/` (§6a SPECIFICATION)
- `parse_html(text) -> MostWantedList` (wirft `MostWantedFormatError`),
  `fetch_html()` (POST `show=500`, eigener User-Agent).
- `load(path)` / `is_stale(ranking)` / `refresh(path, force=False) -> RefreshResult`
  (`ranking`, `error`, `fetched`; Fehler nie fatal, alte Kopie bleibt).
- `MostWantedFilter(ranking, top, category)`: `rank(dxcc, modes)`,
  `accepts(dxcc, modes)`; `ranking=None` → nichts besteht.
- `category_for_mode`, `clamp_top` (1..340), `normalize_category`, `CATEGORY_LABELS`.

### `dxcc/`
- `CtyDatabase(cty_text, numbers_text)`: `lookup(call) -> Entity | None`,
  `dxcc(call) -> int | None`, `version`. `location_part(call)` (Schrägstrich-Regeln).
- `load(stored, bundled, numbers)` (gespeichert > mitgeliefert),
  `is_stale(stored)` (Dateidatum, 14 Tage), `refresh(stored, bundled, numbers)`
  → `CtyRefreshResult` (eine Fehlerseite überschreibt nie eine gute Kopie).

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

### `pdf/layout_back.py`
- `draw_back(c, card, config)` — zeichnet die Rückseite nach `CARD_LAYOUT.md`.
- `fit_size(s, font, size, max_w) -> float` — Schriftgröße, bei der `s` in `max_w`
  passt: **nur verkleinern, nie kürzen**. `text(...)`/`_text_in_band(...)` nehmen
  die Grenze als `max_w=`; ohne Angabe ändert sich nichts. Die Grenzen selbst
  stehen als Konstanten in `geometry.py` (siehe §11 „Layout-Wahrheit").

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
- Alle **Pfade** ausschließlich in `paths.py` (dieselbe Regel). Kein Modul baut
  sich einen Pfad aus `__file__` oder einem relativen String zusammen — sonst
  bricht es beim Bündeln, und zwar still (siehe §11).
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
8. **`lookup/*`** — QRZ zuerst, HamQTH danach, dazu der Cache.
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
- [x] **Most-Wanted-Filter** (Abschnitt 7) nach der GDXF-Liste: Top N +
      Kategorie, Spalte „MW" in der Vorschau, Liste und `cty.dat` automatisch
      aktuell gehalten. Nachgewiesen: das Cabrillo-Beispiel-Log liefert **ohne**
      Lookup dieselben 4 Karten (Top 100) wie das ADIF mit DXCC-Feld.

### Darüber hinaus: Auslieferung

- [x] **Alle Pfade in `paths.py`**; Config/Cache/Protokoll im plattformüblichen
      Benutzerordner, Portable-Modus wenn eine `config.yaml` daneben liegt. Aus
      der Quelle unverändert die Projektwurzel.
- [x] **`scripts/build_app.py` + `packaging/qslcards.spec`** bauen die
      auslieferbare Anwendung für die Plattform, auf der sie laufen, prüfen
      vorher Tk 9 / PyInstaller ≥ 6.21 und verpacken das Ergebnis.
- [x] **`scripts/release.py`** hebt die Version an (`patch`/`minor`/`major` oder
      `X.Y.Z`), lässt die Tests laufen, baut, verpackt und setzt Commit und Tag
      `vX.Y.Z` — der Ersatz für `npm version`. Version **und** Anwendungsname
      stehen dafür in `qslcards/__init__.py` (`__version__`/`__app_name__`).
- [x] **macOS-Bündel gebaut und geprüft** (arm64, ad-hoc signiert, ZIP via
      `ditto`): startet aus dem Archiv, Tk 9.0.4 und alle Assets an Bord. Im
      Archiv liegt die `.app` zusammen mit `LIESMICH.txt` in einem Ordner;
      Anleitung und Prüfliste in `packaging/macos/README.md`. Gebaut wird mit dem
      **python.org-Interpreter** (3.14.7, venv `.venv-build`) — mit Homebrew
      liefe das Ergebnis nur auf dem macOS des Baurechners. Nachgemessen: alle 90
      mitgelieferten Binärdateien `minos 11.0`, `LSMinimumSystemVersion` 11.0,
      `LIESMICH.txt` nennt dieselbe Zahl.
- [x] **Windows-Bündel gebaut und geprüft** (x64, Python 3.14.7/Tk 9.0.4,
      PyInstaller aus `develop` wegen eingebetteter Tcl-9-Daten, ZIP): startet
      aus dem Archiv ohne Konsolenfenster und läuft stabil. Drei Stolperfallen
      auf dem Weg dahin (Tk erst ab 3.14.7, eingebettete Tcl-Daten,
      PowerShell-Zitierung) sind in `packaging/windows/README.md` festgehalten.
      **32-Bit entfällt bewusst.**
- [x] **Fedora-Bündel gebaut und geprüft** (x86_64, `tar.gz`, im Container
      `fedora:42` mit `python3.14`/Tk 9.0, auf einer Fedora-VM abgenommen):
      startet, Vorschautabelle zeigt ihre SVG-Symbole, PDF mit Umlauten,
      `install.sh` richtet Menüeintrag und Symbole ein, Portable-Modus greift.
      Zwei Stolperfallen unterwegs (Standard-Python 3.13 baut mit **Tk 8.6**;
      `PIL._tkinter_finder` fehlte im Bündel) stehen in
      `packaging/linux/README.md`.
---

## 10. Nicht raten — nachschlagen

- ADIF-Feldnamen/Enums: `docs/SPECIFICATION.md` §4.3.
- Cabrillo-Zeilenformat, Modus-Codes, Bandbezeichner: `docs/SPECIFICATION.md`
  §4.5. Vor Änderungen gegen die WWROF-Spezifikation gegenprüfen — vor allem die
  Notiz, dass die Spaltenpositionen **nicht** verbindlich sind. Das Scoring in
  `_find_split` hat **drei** Signale; das eigene Rufzeichen aus `CALLSIGN:`
  gehört nicht dazu und darf nicht zurück (§4.5.2 nennt den Grund).
- Exakte Layout-Koordinaten: `docs/CARD_LAYOUT.md`.
- API-Endpunkte/Session-Flow: `docs/SPECIFICATION.md` §Lookups. Vor Implementierung
  gegen die **aktuelle** HamQTH-/QRZ-Doku gegenprüfen (APIs können sich ändern).
- GDXF-Seite, `cty.dat`-Format und die Zuordnungsregeln: `docs/SPECIFICATION.md`
  §6a. Ändert die GDXF ihr Layout, schlägt `parse_html` fehl und die alte Liste
  gilt weiter — dann den Parser gegen die echte Seite nachziehen.

---

## 11. Arbeitsweise & gelernte Fakten (schnelles Wiedereinsteigen)

**Umgebung / Tooling**
- Python liegt im venv: **`.venv/bin/python`** benutzen (Interpreter ist
  **python.org 3.15.2** mit **Tk 9.0.4** — deshalb funktionieren die SVG-Icons
  hier). Seit 2026-10-26: das alte `.venv` (Homebrew 3.14.6, angelegt unter
  `/Users/johannes/…`) und `.venv-build` (python.org 3.14.7) zeigten auf
  Interpreter, die es auf diesem Rechner nicht gibt; Homebrew-Python ist hier
  nicht installiert. `.venv-build` ist deshalb **kaputt**, bis python.org 3.14.7+
  wieder installiert ist — 3.15 ist zum Bauen noch nicht geprüft. PyCharm startet
  die App über die Startkonfiguration `.idea/runConfigurations/QSL_Karten_Generator.xml`
  (`.venv/bin/python -m qslcards`).
  Abhängigkeiten: `.venv/bin/python -m pip install -r requirements.txt`
  (das ist `-e .[dev]`); zum Bündeln zusätzlich `pip install -e ".[build]"`.
- Auslieferbare Anwendung: `.venv/bin/python scripts/build_app.py --clean`
  → `dist/`. Auf diesem Rechner entsteht nur das macOS-Bündel (siehe §11).
- Neue Version ausliefern: `.venv/bin/python scripts/release.py patch|minor|major`
  (auch `X.Y.Z`, `--show`, `--dry-run`; abschaltbar `--no-tests`/`--no-build`/
  `--no-git`). Das ist der ganze Vorgang — Version anheben, Tests, bauen,
  `git commit` + `git tag vX.Y.Z`. **Die Versionszeile nie von Hand ändern**,
  sonst fehlen Tag und Prüfungen.
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
- **`tk_setPalette` ist Gift für ttk.** Es setzt nicht nur die Optionsdatenbank,
  sondern läuft über den kompletten Widget-Baum und schreibt `-foreground`/
  `-background` als **Instanz**-Option auf jedes Widget, das sie kennt — und
  `ttk::label`/`entry`/`combobox`/`spinbox`/`progressbar` kennen sie. Eine
  Instanz-Option schlägt den Style. Beim Start folgenlos (`theme.apply` läuft vor
  `_build_ui`), beim Wechsel verloren 81 Widgets ihre Farbe: der rote `*`, die
  blauen Abschnittstitel, das „?", die Fläche der Statusleiste, der
  Thumbnail-Rahmen und die Icon-Untergründe der Tabelle. Ab dem **zweiten**
  Wechsel blieben sie sogar auf den Farben des alten Themas stehen (Tk ersetzt
  dort nur noch, was dem alten Vorgabewert entspricht). Ersatz: `option_add`
  („*Background"/„*Foreground") für künftige tk-Widgets + `restyle_tree` für die
  bestehenden. Zwei Tests halten dagegen (kein `TLabel` darf nach einem Wechsel
  eine eigene Farbe tragen).
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
- **Auch ein noch nicht abgebildetes Fenster nicht.** Unter python.org-Tk 9.0.4
  ist `App()` direkt nach dem Bau noch nicht gemappt; `event_generate("<FocusOut>")`
  bzw. `<Button-1>` verpuffen dann, unter Homebrew-Tk fiel es nie auf. Das
  GUI-Fixture ruft deshalb einmal `update()`.
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
- **Kein Text ohne Höchstbreite.** Die Karte hat keinen Zeilenumbruch; vor der
  Regel lief jeder zu lange Wert über seinen Nachbarn — ein langer Name über den
  Stationsblock, die Antennenbezeichnung über die Spaltenlinie, und
  „Confirming SWL-Report" über das „To Amateur Radio Station:"-Label, **ohne**
  Zutun des Anwenders. Jeder freie Text bekommt deshalb `max_w=` und wird über
  `layout_back.fit_size` proportional kleiner gesetzt. Die Grenzen stehen als
  Konstanten in `geometry.py` (`SENDER_TEXT_W`, `CONFIRM_MARK_W`,
  `SENDER_CALLSIGN_W[_PLAIN]`, `STATION_VALUE_W`, `BOX_TEXT_PAD`, `TEXT_GAP`) und
  sind **Abstände zum Nachbarblock**, keine Positionen — verschiebt man eine
  Spalte, wandert die Grenze mit. Was beim Druckrand mitwächst, kommt weiter aus
  dem `PageLayout`, nicht von hier. Ein Aufnahme-Canvas in
  `tests/test_layout_back.py` prüft die **gezeichneten** Kanten.
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
  neue Erklärtexte nur auf ausdrücklichen Wunsch. **Eine** Ausnahme steht
  wieder in Abschnitt 6 (`sections.LOOKUP_SESSION_HINT`, vom Nutzer ausdrücklich
  gewünscht): ohne sie sähen die beim Start leeren Zugangsdaten-Felder wie ein
  Fehler aus (siehe „Zugangsdaten nur zur Laufzeit").
- **Zugangsdaten nur zur Laufzeit** (vom Nutzer so entschieden): HamQTH-/QRZ-
  Benutzer und -Passwort standen im Klartext in der `config.yaml` und wurden bei
  jedem Tastendruck neu hineingeschrieben. Jetzt gilt:
  * `LookupConfig` behält nur `program_id` und `address_export`; die vier
    Zugangsdaten leben in `lookup.LookupCredentials` (nur im Arbeitsspeicher).
    `has_lookup_credentials`/`build_lookup`/`lookup_calls` nehmen dieses Objekt.
  * Die Felder bleiben in GUI-Abschnitt 6, starten aber **jedes Mal leer**. Sie
    hängen **nicht** am Auto-Save (`_wire_autosave`) und werden von
    `_apply_config_to_widgets` **nicht** gesetzt — sonst löschte ein Neuladen der
    `config.yaml` gerade Getipptes. `App._lookup_credentials()` baut das Objekt
    beim Lookup aus den Widgets plus `base_config.lookup.program_id`.
  * **Keine Migration alter Configs** (Muster `portable_mark`): `_from_dict`
    ignoriert die vier Schlüssel, der nächste Auto-Save schreibt die Datei ohne
    sie neu. *Verworfen:* aktives Ausputzen beim Start.
  * Rote Markierung bei abgelehnter Anmeldung, Cache und „Neu abrufen" bleiben
    unverändert — nur die Herkunft der Werte hat sich geändert.
- **QRZ ist erste Wahl, HamQTH zweite — und beide werden zusammengeführt** (vom
  Nutzer so entschieden, siehe §5.7):
  * `build_lookup` hängt QRZ vor HamQTH; nur Anbieter mit Zugangsdaten kommen in
    die Kette. In GUI-Abschnitt 6 stehen die QRZ-Felder deshalb **oben**
    (`sections.LookupSection.rows`, `PROVIDER_FIELDS`).
  * `ChainedLookup` bricht **nicht** beim ersten Treffer ab: die folgenden
    Anbieter füllen die Lücken (`LookupResult.merged_with`, `missing_fields`,
    `base.DATA_FIELDS`), eigene Werte des ersten gewinnen immer. *Verworfen:*
    „strikt QRZ gewinnt, HamQTH nur bei Fehltreffer" — dann liefert QRZ keine
    Flags, jede gefundene Station fällt auf `default_via` und die Priorisierung
    in Abschnitt 4 hat nichts mehr zu entscheiden.
  * **Bewusst unverändert:** `degraded()` gilt weiter für die **ganze** Kette —
    lehnt einer der beiden Anbieter die Anmeldung ab, wird gar nichts gecacht,
    auch wenn der andere funktioniert. Vom Nutzer geprüft und so gelassen (die
    Karten entstehen trotzdem, nur der Cache bleibt leer).
- **GUI-Abschnitte**: 1 Logbuch (ADIF/Cabrillo), 2 Frontbild, 3 Absender (inkl. Funk-Ausrüstung +
  globale Markierungen QSL/Bestätigung), 4 Zustellwege (priorisierbare
  Liste + Trennlinie), 5 Kartenmodus, 6 Lookups (nur Zugangsdaten — QRZ oben,
  HamQTH darunter — + Hinweiszeile),
  **7 Most Wanted** (eine Zeile über die volle Breite), **8 Bemerkungen**,
  9 Vorschau, 10 Druckmodus (inkl. Bogendruck + Druckrand),
  11 Ausgabe (inkl. Adress-/Label-Export).
- **Adress-/Label-Export steht bei der Ausgabe, nicht bei den Lookups** (vom
  Nutzer so entschieden): die Checkbox sitzt in Abschnitt 11 **über** der
  Zielwahl, weil die CSV erst beim Erzeugen entsteht und am Basis-Ausgabepfad
  landet (`…_addresses.csv`). Der Config-Schlüssel bleibt bewusst
  `lookup.address_export` — die Anschriften kommen aus dem Lookup, und ein
  Umzug nach `generation` hätte (Muster `portable_mark`: keine Migration) ein
  bestehendes `true` still auf `false` fallen lassen. Die Variable lebt jetzt auf
  `OutputSection`; `_apply_config_to_widgets`/`_gather_config`/`_wire_autosave`
  greifen entsprechend auf `output_section`.
- **Zu langer Text wird kleiner gesetzt, nie abgeschnitten** (vom Nutzer so
  entschieden, nachdem der Überlauf gefunden war):
  * *Verworfen:* „nur kürzen mit `…`" (Schriftbild bliebe ruhig, aber lange Namen
    und Antennenbezeichnungen verlören Text) und „schrumpfen bis 70 %, dann
    kürzen". Begründung des Nutzers: lieber klein als unvollständig — auf einer
    QSL-Karte ist ein halber Name schlimmer als ein kleiner.
  * Folge: es gibt **kein** gestalterisches Minimum, nur `MIN_FONT_SIZE = 0.5 pt`
    als technischen Boden. Ein absurd langer Wert wird eben winzig; das ist
    sichtbar und damit korrigierbar, ein abgeschnittener Wert wäre es nicht.
  * **Das eigene Rufzeichen bekommt mehr Platz ohne Bestätigungs-Markierung**
    (`SENDER_CALLSIGN_W_PLAIN`, 83,5 statt 39,5 mm) — sonst würde `F/DL0MT/P`
    verkleinert, obwohl der Platz daneben frei ist.
  * **`Confirming SWL-Report` wird immer leicht verkleinert** (51,5 mm auf 42 mm
    Band). Das ist kein Sonderfall, sondern der Auslöser der ganzen Regel.
  * Das **Remarks-Limit bleibt bei 80 Zeichen** (Handbuch, GUI-Zähler); 80 breite
    Zeichen passen nicht in eine Zeile und werden verkleinert. *Verworfen:*
    zweizeiliger Kasten (rührt an `MAX_ROWS_WITH_REMARKS`) und ein Limit von 60.
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
- **Rufzeichen: ein Feld, alles drin, alles groß** (in zwei Runden mit dem Nutzer
  erarbeitet; die verworfenen Zwischenstände stehen bewusst mit da):
  * **Rufzeichen, Locator und DOK werden großgeschrieben** — in der GUI beim
    Verlassen des Feldes (nicht beim Tippen: das Setzen der `tk.Variable` rückt
    die Schreibmarke ans Ende), und beim Zeichnen noch einmal in `layout_back`.
    Doppelt mit Absicht: die GUI ist die sichtbare Rückmeldung, die Karte die
    Garantie für eine von Hand geänderte `config.yaml`. CQ-Zone/ITU sind Zahlen,
    Name/Adresse gehören dem Anwender.
  * **Der ADIF-Parser schreibt `call` groß** (Cabrillo tat es schon). Sonst stand
    die Kleinschreibung auf der Karte, und `dl2sct` war im Modus „pro Station"
    eine **andere** Station als `DL2SCT` — zwei Karten statt einer. Der Rohwert
    bleibt in `raw`.
  * **Das Dropdown „Portabel" (`portable_mark`) ist entfernt** — Feld, Widget,
    `Card`-Attribut, Config-Eintrag. Die Kennung wird ins Rufzeichen getippt
    (`F/DL0MT/P`). *Verworfen (zwei Zwischenstände):* erst ein Popup, das die
    mitgetippte Kennung ins Dropdown übernimmt (trennte am **ersten**
    Schrägstrich und ließ `F/DL0MT/p` durchfallen), dann dasselbe am **letzten**
    Schrägstrich. Beides musste Landespräfixe (`F/`), `/QRP`, `/MM` (maritime
    mobile — **nicht** das `/m` des Dropdowns!) und Rufbezirke (`W1AW/4`) von den
    vier eigenen Kennungen unterscheiden. Ohne das Dropdown gibt es diese Fälle
    schlicht nicht mehr. **Folge:** die Kennung wird jetzt **groß** gedruckt
    (`/P` statt `/p`) — die Kleinschreibung zurückzuholen hieße, die
    Fallunterscheidung wieder einzubauen.
  * **Keine Migration alter Configs:** ein `portable_mark` in einer bestehenden
    `config.yaml` wird beim Laden ignoriert und verschwindet beim nächsten
    Auto-Save; die Kennung muss einmal ins Rufzeichen getippt werden.
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
- `MARGIN = 3 mm`; Bestätigungs-Markierung (Confirming QSO/SWL) oben mittig;
  Stationsdaten als Label/Wert-Spalte neben der Adresse; Funk-Block (RIG/ANT/PWR)
  dynamisch darunter; REMARKS über volle Breite; Fuß unten mit ~3 mm Rahmenabstand.
- **GUI: keine Speichern/Laden-Buttons** — Config wird automatisch gespeichert
  (debounced) und bei externer Datei-Änderung neu geladen (mtime-Poll, Loop-Schutz
  via `_suppress_save`). Enter in Eingabefeldern gibt den Fokus frei.
  **Achtung:** `_gather_config()` baut die Config aus den Widgets — Felder ohne
  Widget (`appearance`, `recent`, `lookup.program_id`) müssen aus `base_config`
  übernommen werden, sonst löscht der nächste Auto-Save sie. Umgekehrt gilt für
  die Zugangsdaten-Widgets: sie haben **kein** Config-Feld und dürfen in keiner
  Richtung mitlaufen (siehe „Zugangsdaten nur zur Laufzeit").
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
- **Most-Wanted-Filter** (mit dem Nutzer Schritt für Schritt abgestimmt, die
  verworfenen Varianten stehen bewusst mit da):
  * **Filter, kein Aufdruck**: der Rang steht nur in der Vorschau-Spalte „MW",
    nie auf der Karte. Maß ist **Top N** (keine Prozent-Schwelle), Default 100.
  * **Kategorie „Automatisch (nach Mode)" ist Default.** Feste Listen
    (CW/Phone/Digital) zählen **nur** QSOs ihrer Betriebsart — übernommen aus
    dem DXCC-Filter des Kollegen; vorher maß die CW-Liste auch SSB-QSOs.
  * **Unbekanntes Gebiet → nicht drucken**, ebenso ohne Liste. „Pro Station":
    die Karte zählt, sobald **ein** QSO darauf passt (bester Rang).
  * **Platz in der GUI**: eine Zeile über die volle Breite vor den Bemerkungen
    („lang gezogen wie Bereich 8"). *Verworfen:* rechts unter den Lookups (erst
    so gebaut, ließ links 114 px Lücke). Die Statusanzeige steht rechtsbündig in
    derselben Zeile und muss **kurz** bleiben (Standardfenster 969 px).
  * **Liste automatisch aktuell**: nur bei eingeschaltetem Filter, nach 30
    Tagen; **nur das Einschalten** ruft ab, Top/Kategorie nie (sonst nach einem
    Fehlschlag ein Abruf je Tastendruck). **Eine** Anfrage (`show=500`) statt je
    Gebiet eine Seite wie im DXCC-Filter.
  * **Rangliste nur von der GDXF** — vom Nutzer ausdrücklich so gewollt. Das
    **Gebiet** aus der GDXF-Präfixspalte abzuleiten wurde gemessen und verworfen
    (51 % richtig, die seltenen Gebiete fehlten). Stattdessen die `cty.dat` von
    AD1C (MIT, mitgeliefert, Neuladen nach 14 Tagen) mit der Nummerntabelle aus
    dem DXCC-Filter des Kollegen — **mit seinem Einverständnis** übernommen.
    Reihenfolge Log > cty.dat > Lookup.
  * **Keine Cache-Migration**: alte `lookup_cache.json`-Einträge ohne `dxcc`
    bleiben, wie sie sind (seit der cty.dat ohnehin kaum noch nötig).
  * **Keine Kopie der GDXF-Liste** im Programm oder Repository (fremde Daten
    ohne Lizenzvermerk); `mostwanted.json` ist gitignored.

**Realität der Testdaten (`Log.adi`, `beispiel-logs/`)**
- **Keine der Dateien liegt im Repository** (`*.adi` und `beispiel-logs/` sind
  gitignored, persönliche Daten). Tests, die sie lesen, tragen ein `skipif` und
  überspringen sich in einer frischen Kopie; alles Fachliche daran prüfen
  Inline-Fälle mit. Gefunden am 2026-10-26 beim Probe-Klon für die Übergabe an
  einen Kollegen: vorher waren dort **drei Tests rot**, weil sie `Log.adi`
  stillschweigend voraussetzten. Vor einer Weitergabe deshalb einmal frisch
  klonen, venv anlegen, `pytest` — erst dann ist „bei mir grün" etwas wert.
- Enthält **kein** `QSL_SENT_VIA` (und keine Via-Info) — das ist der **Normalfall**:
  die Via kommt aus dem Lookup, nicht aus dem Log. Ohne Lookup-Credentials fallen
  alle Karten auf `default_via` (Default `B`); mit Credentials liefert der Lookup
  je Station die akzeptierten Wege {B,D,Q,L}.
- **`beispiel-logs/`** (gitignored, persönliche Daten im Cabrillo-Kopf): CQ WW SSB
  2026 von DL0MT, **341 QSOs, 294 Stationen**, einmal als Cabrillo
  (`DL0MT.log`, Windows-1252, Mode `PH`, **kein** DXCC) und einmal als ADIF aus
  QARTest (`cqww26.adi`, **mit** `DXCC` für alle 341). Ideal zum Prüfen der
  `cty.dat`: QARTest hat die Gebiete selbst gesetzt; `tests/test_dxcc.py`
  vergleicht dagegen, wenn die Datei lokal da ist. Mit der GDXF-Liste 2025 und
  Top 100 bleiben 4 Karten: HF0PAS, VK9DX, XX9TXN, AH2R.
- **40 QSOs, 36 eindeutige Rufzeichen**: `PA3BRB` kommt fünfmal vor, alle übrigen
  einmal. Damit unterscheiden sich „pro QSO" (40 Karten) und „pro Station"
  (36 Karten) sichtbar — genau dafür taugt die Datei.
- **25 der 40 QSOs haben gar keinen Rapport** (`<RST_SENT:0>`, so schreibt HAMRS
  es), die Spalte SIGNAL REPORT bleibt dort leer. Von den 33 FT8-QSOs tragen nur
  8 einen dB-Wert (`+00`, `+14`, `-9`); der Rest ist leer. dB-Rapporte passen
  **bewusst** nicht ins R/S/T-Raster, und ein leeres Feld bleibt leer — geraten
  wird nie (so vom Nutzer akzeptiert).
- **Drei Rapporte im Log tragen einen Zeilenumbruch in der deklarierten Länge**
  (`<RST_SENT:3>+9\n`). Zwei davon sind formal korrekt — es gibt kein `<` im
  Wert, der Wiederherstellungszweig greift also **nicht**. Deshalb schneidet
  `_tokenize` abschließenden Leerraum generell ab (`value.rstrip()`, die einzige
  bewusste Abweichung von „die Länge ist maßgeblich"); vorher stand `"+9\n"` in
  `qso.rst_sent` und in `raw`. Auf der Karte fiel es nie auf, weil
  `builder._make_row` ohnehin `strip()` — im Datenmodell schon.
- Für Cabrillo gibt es **kein** Beispiel-Log im Repo: die Testfälle stehen inline
  in `tests/test_cabrillo_parser.py`, je einer pro Contest-Template. Zum
  Ausprobieren ein gemischtes Log im Scratchpad anlegen, nicht im Projekt-Root.
- **Ein Contest-Log ist groß** (500–5000 QSOs) — gemessen (5000 QSOs, 3525
  Karten, Bogendruck): Parser 95 ms, `build_cards` 32 ms, Vorschautabelle
  122 ms, PDF 4,6 s. Alles linear, die GUI bleibt bedienbar. Der Engpass war die
  PDF-Erzeugung (308 s) und lag am `ImageReader` (siehe oben), nicht am Umfang.
- **Der Lookup ist die eigentliche Geduldsprobe** und bleibt es: 3500 eindeutige
  Rufzeichen bedeuten 3500 Abfragen — mit QRZ **und** HamQTH-Zugangsdaten das
  Doppelte, weil QRZ keine Zustellweg-Flags liefert und HamQTH sie fast immer
  nachfüllen muss (§5.7). `LookupCache.set()` schreibt dabei
  je Rufzeichen die ganze JSON-Datei neu (quadratisch: 0,7 s bei 700, 16,4 s bei
  3500 Einträgen) — das **bleibt bewusst so**: neben zwanzig Minuten Netzzeit
  fällt es nicht ins Gewicht, und das sofortige Schreiben macht den Cache
  absturzsicher (ein abgebrochener Lauf behält jedes geholte Rufzeichen). Beim
  zweiten Laden mit warmem Cache wird gar nicht mehr geschrieben.

**Bündeln (PyInstaller) — teuer erkaufte Fakten**
- **Tk 9 ist die harte Bedingung, nicht eine Python-Version.** Die SVG-Icons der
  Vorschautabelle (`gui/preview.py`, `format="svg …"`) brauchen Tk ≥ 9 und fehlen
  sonst **ohne Fehlermeldung** (der `except` daneben schluckt es). Woher Tk kommt,
  ist plattformabhängig — wer daraus eine Python-Hürde macht, sperrt Fedora aus:
  * Windows/macOS: Tcl/Tk steckt im Python-Installer, und dort zählt die
    **Punktversion**: **3.14.7 → 9.0.4**, aber 3.14.0–3.14.6 und 3.13 → nur
    8.6.15 (nachgeprüft in `PCbuild/tcltk.props` an den Tags `v3.14.0` bis
    `v3.14.7`). Nur „Python 3.14" zu fordern genügt **nicht** — genau daran ist
    der erste Windows-Bauversuch gescheitert.
  * **Windows 32-Bit ist doppelt blockiert** und wird deshalb nicht mehr gebaut
    (siehe Entscheidungen unten): PyYAML hat für `cp314` kein win32-Wheel mehr,
    und PyInstallers `develop` bringt keinen vorgebauten 32-Bit-Bootloader mit.
  * Linux: Tk kommt vom System — aber **„Fedora 42 hat Tcl/Tk 9" genügt nicht**.
    Das Systempaket `tk` ist dort 9.0.0, das Standard-Python 3.13 ist jedoch
    gegen die Kompatibilitätspakete gebaut und meldet **8.6**:
    `python3-tkinter → libtcl8.6.so/libtk8.6.so`, dagegen
    `python3.14-tkinter → libtcl9.0.so/libtcl9tk9.0.so` (`dnf repoquery
    --requires`). Gebaut wird deshalb mit dem parallel mitgelieferten
    **`python3.14`**. *Verworfen:* `fedora:43` (Standard-Python ist dort 3.14) —
    dessen glibc 2.42 ist neuer, das Bündel liefe dann nicht mehr auf F42.
    Hier genügt das **veröffentlichte** PyInstaller 6.21.0: `info library`
    liefert einen echten Ordner, keinen `//zipfs:/`-Pfad wie unter Windows.
  * **PyInstaller ≥ 6.21** — davor kennt es Tcl/Tk 9 überhaupt nicht.
- **`PIL._tkinter_finder` muss in `hiddenimports`** — sonst bleibt die Miniatur
  in GUI-Abschnitt 2 nach der Bildauswahl leer. Pillow lädt das Modul erst zur
  Laufzeit aus seiner C-Erweiterung `_imagingtk`, die statische Analyse sieht den
  Import nie. **Nur Linux ist betroffen**: dort lädt CPython `_tkinter.so` mit
  `RTLD_LOCAL`, die Tcl/Tk-Symbole sind unsichtbar und Pillow nimmt den Umweg
  über `_tkinter_finder` + `dlopen`; auf macOS sind sie global sichtbar, Windows
  hat einen eigenen Zweig über `GetProcAddress`. Der Eintrag gilt trotzdem für
  alle drei Ziele — er kostet nichts. **Silent** ist der Fehler, weil
  `app._update_thumbnail` nur `OSError`/`ValueError` fängt: der
  `ModuleNotFoundError` landet im Protokoll, im Fenster steht weiter „keine
  Vorschau", und die **PDF ist völlig in Ordnung** (`drawImage(pfad)` braucht
  kein Tk). Prüfen: `"PIL._tkinter_finder" in sys.modules` nach einem
  `ImageTk.PhotoImage(...)`.
- **Für Windows genügt auch 6.21.0 nicht.** Python 3.14.7 legt die Tcl-Bibliothek
  *in die DLL* (`info library` liefert `//zipfs:/…`). PyInstaller 6.21.0 sammelt
  dann nichts ein, und sein Laufzeit-Hook bricht beim **Start** des fertigen
  Programms ab: „Tcl data directory … `_tcl_data` not found". Der Fix liegt in
  `develop` (`news/9470.*`), ist aber in keinem Release — `pip install
  "pyinstaller @ git+…@develop"`, ohne Compiler, die Bootloader liegen vorgebaut
  im Repo (Windows-**32**-Bit allerdings nicht).
  **Die Version verrät das nicht:** die Fassung mit dem Fix meldet weiter 6.21.0.
  `build_app.py` prüft deshalb die **Fähigkeit** (`//zipfs:/` im Quelltext von
  `PyInstaller.utils.hooks.tcl_tk`) und nur dann, wenn das lokale Tcl die
  eingebettete Form nutzt — sonst meckerte es auf macOS/Linux grundlos.
  `tests/test_build_app.py` hält alle vier Kombinationen fest.
- **Cross-Compile existiert nicht.** PyInstaller bündelt den Interpreter, unter
  dem es läuft. Windows-Bündel nur auf Windows, Fedora-Bündel nur auf Linux
  (Container-Rezept in `packaging/linux/Dockerfile.fedora`, Basis `fedora:42`
  von Docker Hub — die **älteste** unterstützte Version, weil PyInstaller keine
  glibc mitbringt und das Ergebnis sonst nur auf neueren Systemen läuft;
  F42 = glibc 2.41). Die **Architektur** ist genauso wenig frei: auf Apple
  Silicon braucht es `--platform linux/amd64`, sonst entsteht ein aarch64-
  Programm. Und `--user "$(id -u):$(id -g)"`, sonst gehören `dist/`, `build/`
  und `qslcards.egg-info/` hinterher root und lassen sich vom Mac aus nicht
  einmal mehr löschen.
- **Das Linux-Bündel lässt sich ohne Fedora-Rechner prüfen**: zweiter Container
  aus **nacktem** `fedora:42` (ohne Python — sonst beweist ein Start nichts über
  die Vollständigkeit), darin `Xvfb :99`, `xdotool` für Menü/Kürzel und
  `import -window root` für den Screenshot. So sind die SVG-Symbole der
  Vorschautabelle, die Bildminiatur und eine fertige PDF nachweisbar, ohne zu
  klicken. Ein `xdg-open`, das mit **Exit 3** („no method available") scheitert,
  ist dabei in Ordnung — im Container fehlt bloß ein Betrachter. Ein
  `symbol lookup error` wäre das Warnzeichen (siehe `paths.subprocess_env()`).
- **`ditto`, nicht `zip`, für die `.app`.** Ein gewöhnliches `zip` löst die
  Symlinks in `Contents/Frameworks` auf und zerstört damit die Signatur; die
  entpackte Anwendung startet dann gar nicht mehr („is damaged"). Auf arm64 ist
  eine (ad-hoc genügende) Signatur Pflicht — PyInstaller setzt sie selbst.
- **Der Rechtsklick-Trick ist tot.** Mit **macOS 15 (Sequoia)** hat Apple
  „Rechtsklick ▸ Öffnen" für nicht notarisierte Programme entfernt; der Anwender
  muss seitdem über *Systemeinstellungen ▸ Datenschutz & Sicherheit ▸ Dennoch
  öffnen*. Beim Selbsttest **sieht man das nie**: die Meldung hängt am
  Quarantäne-Flag, das nur Browser/Mail/AirDrop setzen, nicht ein lokaler
  Kopiervorgang (nachstellen mit `xattr -w com.apple.quarantine …`).
- **Homebrew-Python hängt nicht an der Punktversion.** Die Regel „erst 3.14.7
  bringt Tk 9" gilt für die Installer von python.org. Homebrew bindet das Paket
  `tcl-tk` ein und liefert Tk 9.0 auch mit älteren Punktversionen — deshalb ist
  `.venv` (Homebrew) zum Entwickeln völlig in Ordnung. Zum **Ausliefern** taugt
  es trotzdem nicht, siehe den nächsten Punkt.
- **…dafür hängt Homebrew am laufenden macOS — und das entscheidet, wer das
  Bündel starten kann.** PyInstaller nimmt die Bibliotheken des bauenden
  Interpreters mit (CPython-Erweiterungen, Tcl/Tk, OpenSSL, zlib), und die tragen
  dessen `MACOSX_DEPLOYMENT_TARGET`; `dyld` lehnt eine dylib ab, die für ein
  neueres System gebaut ist als das laufende. Homebrew baut **immer gegen das
  gerade laufende macOS**: auf diesem Rechner (macOS 26) meldet `sysconfig`
  `MACOSX_DEPLOYMENT_TARGET = 26`, und 59 der mitgelieferten Binärdateien tragen
  `minos 26.0` (nachgemessen mit `otool -l` am Bündel in `dist/`). Das Ergebnis
  läuft damit **nur auf macOS 26+**. Dasselbe Problem wie glibc unter Linux — nur
  unsichtbar, weil der Baurechner es per Definition erfüllt. Prüfen:
  `python -c "import sysconfig; print(sysconfig.get_config_var('MACOSX_DEPLOYMENT_TARGET'))"`.
  Wer ältere Systeme bedienen will, baut mit dem **Installer von python.org**
  (3.14.7+, Ziel 10.13/11.0) statt mit Homebrew.
- **Ausgeliefert wird auf macOS mit python.org, entwickelt mit Homebrew.** Die
  beiden hier vorhandenen Interpreter können je nur die Hälfte: python.org 3.13
  hat Deployment-Target 10.13, aber Tk 8.6 (SVG-Icons fehlen); Homebrew 3.14.7
  hat Tk 9.0, aber Ziel 26 (läuft nur auf macOS 26). Beides zugleich kann nur
  der **python.org-Installer ab 3.14.7** (10.13 + Tk 9.0.4). Einrichtung in
  `packaging/macos/README.md`; das venv dafür heißt `.venv-build` wie unter
  Windows. Zum Entwickeln und Ausprobieren genügt weiterhin `.venv` (Homebrew).
- **`LSMinimumSystemVersion` darf nie fest im Spec stehen.** Sie stand auf
  `"11.0"`, während das Bündel 26 brauchte — die schlimmere Richtung: Launch
  Services lässt das Programm los, PyInstallers Bootloader (Ziel 11.0) läuft
  wirklich an, und erst das Nachladen stirbt mit einer dyld-Meldung, die dem
  Anwender nichts sagt. Jetzt kommt der Wert aus
  `build_app.macos_minimum_system_version()` (die Spec importiert ihn aus
  `scripts/`, gleiche Begründung wie bei `__app_name__`), und
  `build_app.check_warnings()` sagt beim Bauen, für welche Systeme das Ergebnis
  taugt. Bewusst **Warnung statt Hürde**: das Zielpublikum wählt der Bauende.
- **`LD_LIBRARY_PATH` vergiftet jeden Kindprozess.** PyInstaller stellt den
  Bibliothekspfad des Bündels nach vorn; ein davon geerbtes `xdg-open` oder
  `gsettings` lädt die gebündelten Bibliotheken statt der eigenen und stirbt mit
  „symbol lookup error". Deshalb bekommt **jeder** `subprocess.run`-Aufruf
  `env=paths.subprocess_env()` (stellt `…_ORIG` wieder her). Aus der Quelle
  bleibt die Umgebung unangetastet.
- **Ein Fensterprogramm hat kein `stderr`** — unter Windows ist es sogar `None`.
  Ohne Gegenmaßnahme verschwinden alle `logger.warning` spurlos, und Tks
  `report_callback_exception` läuft bei jeder Ausnahme gegen `None.write()`.
  `main._prepare_frozen_runtime` ersetzt fehlende Ströme und schreibt ins
  Protokoll; Menü „Hilfe ▸ Protokoll anzeigen" führt hin.
- macOS: `sys.executable` liegt in `Name.app/Contents/MacOS/` — „neben dem
  Programm" heißt für den Anwender aber *neben der `.app`*, also drei Ebenen
  höher (`paths.program_dir`). Zudem legt PyInstaller neben der `.app` noch den
  rohen COLLECT-Ordner ab; `build_app.py` räumt ihn weg, sonst läge er genau
  dort, wo der Portable-Modus nach `config.yaml` sucht.
- Prüfen ohne GUI-Bedienung: `sys.frozen`/`sys._MEIPASS`/`sys.executable` auf ein
  echtes Bündel zeigen lassen und die Pfade auflösen — das findet fehlende
  Assets, ohne dass man klicken muss (`tests/test_paths.py` macht es synthetisch).

**Wichtige Entscheidungen zum Bündeln (nicht ohne Rückfrage kippen)**
- **Datenablage hybrid**: liegt eine `config.yaml` neben dem Programm, gewinnt
  sie (Portable-Modus, USB-Stick); sonst der plattformübliche Benutzerordner
  (`%APPDATA%` / `~/Library/Application Support` / `~/.config`). Aus der Quelle
  **immer** die Projektwurzel — dadurch ändert sich der Entwickler-Workflow
  nicht. Config, Cache und Protokoll liegen stets im selben Ordner
  (`paths.data_dir`): laufen sie auseinander, gehört der Cache zu einem anderen
  Konto.
- **onedir, kein onefile**: schnellerer Start (kein Entpacken bei jedem Lauf),
  weniger Virenscanner-Fehlalarme, und der Portable-Modus braucht einen Ordner.
- **Windows nur 64-Bit** (32-Bit vom Nutzer gestrichen, drei unabhängige
  Blockaden: kein PyYAML-win32-Wheel für `cp314`, kein vorgebauter 32-Bit-
  Bootloader in PyInstallers `develop`, und Windows 10 in 32 Bit ist seit
  Oktober 2025 ohne Support — Begründung in `packaging/windows/README.md`),
  macOS **arm64 ad-hoc signiert** (nicht notarisiert — Empfänger müssen den
  Start einmal erlauben, siehe oben), Linux **Fedora, nur x86_64** (auf Apple
  Silicon deshalb `--platform linux/amd64`; ein natives aarch64-Bündel wurde
  vom Nutzer verworfen — der übliche Fedora-PC ist x86_64). Bewusst außen
  vor: Inno-Setup, RPM, AppImage, Notarisierung, CI, Windows-ARM64.
- **Der Container-Lauf und `dist/` teilen sich einen Ordner.** `docker run` hängt
  das Repo ein, und der CMD ist `build_app.py --clean` — ein Fedora-Lauf löscht
  also ein danebenliegendes macOS-/Windows-Bündel. Vor dem Bauen `dist/` sichern.
  Nur dokumentiert, **nicht** im Code gelöst (vom Nutzer so entschieden;
  Alternative „PyInstaller-Arbeitsordner je Plattform" wurde verworfen). Ohne
  `--clean` zu bauen wäre keine Lösung: dann fände PyInstaller in
  `build/pyinstaller` noch die Analyse-Zwischenstände der anderen Plattform.
- **Ins Archiv gehört `LIESMICH.txt`, nie die README aus `packaging/`.** Die
  beschreibt das **Bauen** (Container, PyInstaller, glibc) und ist für den
  Anwender die falsche Datei; unter Linux lag sie eine Zeit lang mit drin.
  `install.sh` und die `.desktop`-Datei müssen dagegen mit — sonst bräuchte er
  fürs Einrichten zusätzlich das Repository.
- **Ein Bauskript je Plattform nur, wo etwas zu beschaffen ist**: `build.ps1`
  (Windows: Interpreter, venv, PyInstaller aus `develop`), `Dockerfile.fedora`
  (Linux: überhaupt ein Fedora 42). Auf macOS steht die Umgebung — dort ist
  `scripts/build_app.py` der ganze Vorgang, ein Wrapper wäre reine Fassade.
  Ausgeliefert wird auf **allen** Plattformen ein Ordner mit Kurzanleitung
  daneben; auf macOS legt ihn `macos_delivery_folder` an (in die `.app` gehört
  nichts hinein), und die `.app` wandert **hinein** statt hineinkopiert zu
  werden.
- **`config.example.yaml` wird nicht von Hand gepflegt**: sie ist byteweise das,
  was `config.save(AppConfig())` schreibt — leer, ohne Kommentare, mit
  `config.CONFIG_HEADER` als erster Zeile („bitte nicht von Hand bearbeiten").
  Ein Test hält die Gleichheit fest. Die Warnung steht in `save`, nicht bloß in
  der Vorlage: `yaml.safe_dump` schreibt die Datei beim Auto-Save komplett neu,
  ein nur dort stehender Hinweis wäre nach der ersten Änderung weg.
- **Vier Werte haben bewusst kein Eingabefeld** und gelten als Programm-
  konstanten, die zufällig in der Config liegen: `default_via`,
  `page_orientation`, `static_footer`, `program_id` (vom Nutzer so entschieden,
  Alternative „`static_footer` bekommt ein Widget" wurde verworfen). Wer einen
  bedienbar machen will, braucht ein Widget — „einfach in der Datei ändern"
  widerspricht der Kopfzeile.
- **Version nur in `qslcards/__init__.py`**; `pyproject.toml` liest sie über
  `[tool.setuptools.dynamic]`. `requirements.txt` ist nur noch `-e .[dev]`, die
  Abhängigkeiten stehen in `pyproject.toml` (Extras `dev` und `build`).
- **Auch der Anwendungsname steht dort** (`__app_name__`): `scripts/build_app.py`
  und `packaging/qslcards.spec` lasen ihn vorher je aus einer **eigenen**
  Konstante. Laufen die auseinander, sucht das Bauskript das Ergebnis von
  PyInstaller unter dem falschen Namen und bricht mit „… fehlt" ab, obwohl
  gebaut wurde. Die Texte in der **Oberfläche** (Fenstertitel, „Über", Menü,
  `paths.APP_DIR_NAME`) bleiben bewusst ausgeschrieben dort, wo sie stehen —
  `APP_DIR_NAME` ist sogar ein eigener Vertrag: er benennt den Datenordner des
  Anwenders und darf sich nicht ändern, nur weil das Bündel anders heißt.
- **Ein Versionssprung ist ein Skriptlauf, kein Handgriff**
  (`scripts/release.py`, vom Nutzer als Ersatz für `npm version patch`
  gewünscht; alle drei Punkte bewusst so entschieden):
  * **Kein npm, keine `package.json`.** Das Projekt hat kein Node, und eine
    `package.json` wäre eine zweite Versionsquelle neben `__init__.py`.
    *Verworfen:* ebenso `bump-my-version` (neue Abhängigkeit für eine Regex)
    und `setuptools-scm` (Version aus dem Git-Tag — im Bündel gibt es kein
    `.git`, und `__init__.py` soll die eine Wahrheit bleiben).
  * **Gebaut wird VOR Commit und Tag** — anders als `npm version`, das den Build
    in einen `postversion`-Hook hängt. Am Ergebnis ändert das nichts (der Build
    liest nur), am Aufräumen alles: scheitert er, wird die Versionszeile
    zurückgeschrieben und die Arbeitskopie ist wieder sauber. Bei der
    npm-Reihenfolge stünden Commit **und** Tag schon für eine Fassung, die es
    nie gab. `tests/test_release.py` hält das fest.
  * **Gebaut wird in einem eigenen Prozess** (`subprocess`, nicht
    `build_app.main()`): `build_app` liest `__version__` beim **Import** — im
    selben Prozess stünde dort noch die alte Nummer und das Archiv hieße nach
    der Vorgängerversion.
  * **Kein `git push`** und keine Vorabversionen (`0.2.0-rc1` wird abgelehnt);
    Tags sind leichtgewichtig. Es gibt sie erst **ab `v0.2.0`** — die Fassung
    0.1.0 entstand vor `release.py` und hat keinen; rückwirkend einen zu setzen
    wurde verworfen (er stünde auf einem Commit, der nie als 0.1.0 ausgeliefert
    wurde).
  * `release.py` baut nur für **sein** System (Cross-Compile gibt es nicht). Die
    anderen beiden Archive entstehen danach auf ihrem Rechner mit `git pull` +
    `build_app.py --clean` — die Versionszeile ist dann schon committet.
- **Kein „Schließen" im „Über"-Dialog** — wie beim Handbuchfenster macht das die
  Fenstersteuerung des Systems (Escape bleibt gebunden).

**Stand 0.4.0: Assistent, Wavelog, Robustheit (Bewertung vom 26.11.2026)**
- Die Oberfläche ist ein **Schritt-Assistent** mit sechs Schritten: 1 Quelle
  (Datei oder Wavelog), 2 Absender, 3 Abfrage (Lookups, Zustellwege,
  Kartenmodus), 4 Gestalten (Frontbild, Bemerkungen, Most Wanted), 5 Prüfen
  (Vorschau), 6 Druck. Die alten **Abschnittsnummern 1–11** leben als Anker im
  Handbuch (`abschnitt-N`) und im Menü weiter; `app.SECTION_STEP` bildet sie auf
  Schritte ab. In Texten für den Anwender „Schritt" sagen, nicht „Abschnitt".
- **Prüfen füllt das Fenster** (`ScrollableFrame.set_fill`): die Vorschau
  scrollt nur in sich, der Außen-Scroll ruht. Vorher zwei verschachtelte
  Scrollbalken mit ~6 sichtbaren Zeilen.
- **Pflichtangaben**: kein Popup mehr, die Navigationsleiste nennt alles
  Fehlende (`wizard.show_problem`), die Felder werden weiter rot markiert.
- **Schon gesendet = keine Karte** (`QSL_SENT = Y`, auch ADIF; bei Wavelog
  zusätzlich `wavelog_sent.json`). Bewusster Nachdruck über „Schon gesendete
  anzeigen": eigene Karten mit `Card.already_sent`, nie vorausgewählt
  (`is_printable`), nie mit offenen QSOs zusammengelegt
  (`normalize_station_cards`), nie erneut markiert (`marks_for_cards`).
- **Markiert wird nur Papier**: Wege B/D (B mit Manager -> `M`); eQSL/LoTW nie.
  Offene Markierungen stehen in `wavelog_sent.json` (`pending`) und überleben
  einen Neustart.
- **Dateien atomar schreiben** (`fileio.atomic_write_text`): config.yaml (mit
  `.bak`, Rückfall + `.defekt` in `config.load_safely`), Lookup-Cache,
  `wavelog_sent.json`. Eine **unlesbare** `wavelog_sent.json` wird nie
  überschrieben (`SentStoreError`), sonst wäre das Sicherheitsnetz still weg.
  `config.load` wirft für leere Dateien `ConfigError` — eine leere Datei ist
  abgebrochen geschrieben, kein „alles Standard".
- **Zugangsdaten nie in Protokoll oder Fehlermeldung**: HamQTH/QRZ tragen das
  Passwort in der URL, `requests` hängt sie an Fehler. `redact.describe_error`
  in den Clients, `RedactingFilter` am Datei-Handler. Der Wavelog-Client nennt
  bei Netzfehlern nur den Typ.
- **Lookups laufen über `LookupRunner`**: jede Anfrage eine Generation, nur die
  neueste liefert ab; ein laufender Lauf wird per `threading.Event` (geprüft vor
  jedem Rufzeichen in `lookup_calls`) abgebrochen und der neue startet, wenn er
  endet — nie zwei Threads gleichzeitig am Cache. `App._lookup_running` ist
  eine Eigenschaft darauf. Tests ersetzen weiter `appmod.threading.Thread` und
  `appmod.lookup_calls` (der Runner löst beide erst beim Aufruf auf).
- **`app.py` ist aufgeteilt (Bewertung 3.1)**: Abläufe ohne Tk in
  `controllers/` (eigene Tests in `tests/test_controllers.py`, ohne Xvfb),
  Feld<->Config-Abbildung in `gui/config_form.py`, die Fensterteile als Mixins
  `gui/app_*.py`. Was die Tests über `appmod` ersetzen (Pfade, `lookup_calls`,
  `generate`, `open_file`, `messagebox`, `confirm`,
  `ask_overwrite_manual_remarks`), bleibt in `app.py` und wird erst beim Aufruf
  aufgelöst; die Mixins erreichen Dialoge nur über `self._messagebox`,
  `self._confirm`, `self._ask_overwrite_remarks`, `self._open_file`. Ein
  Mixin, das `messagebox` selbst importiert, entkommt den Test-Attrappen und
  öffnet im Test echte Dialoge.
- **Wavelog-Client**: `WavelogError.status/code` statt Textsuche; 429 ->
  `retry_after` abwarten (max. 5×), 0,5 s Abstand beim Markieren; Seitenlimit
  (`total_pages`, `MAX_PAGES`); `index.php` wird bei 404 einmal weggelassen,
  wenn der Nutzer es nicht selbst getippt hat (Client wird deshalb in der App
  wiederverwendet). Schlüsselbund-Eintrag unter der **normalisierten** Adresse.
- **Zugangsdaten nur zur Laufzeit — mit Ausnahme auf Wunsch**: seit 0.4.0 darf
  der Nutzer QRZ/HamQTH per Haken in den **Schlüsselbund** legen
  (`lookup/secret.py`, Config nur `lookup.remember`, Standard aus). Die
  Grundregel „nie im Klartext in einer Datei" gilt unverändert.
- **Config-Überwachung (mtime-Poll) bleibt bewusst**: sie gleicht zwei offene
  Fenster bzw. einen Netzlaufwerk-Ordner ab. Eine extern kaputt geschriebene
  Datei wird dabei ignoriert (Werte im Fenster gelten weiter), der nächste
  Auto-Save repariert sie. (Bewertung 3.4)
- **Noch nie gegen echtes Wavelog getestet.** Vor dem Release 0.4.0
  `scripts/wavelog_check.py` gegen die Instanz laufen lassen und den Bericht
  als Fixture in `tests/test_wavelog.py` übernehmen.
- **CI**: `.gitlab-ci.yml` (Remote ist GitLab) und GitHub-Workflow; beide holen
  per `uv` ein Python mit **Tk 9** und brechen ab, wenn es Tk 8.6 ist.

**AppImage auf Fedora Kinoite (0.4.2, gefunden am 2026-11-27)**
- **Das AppImage 0.4.2 startete auf einem frischen Fedora Kinoite gar nicht** —
  Doppelklick, nichts passiert. Ursache: das Tk mit Xft (`tk_xft.sh`, PR 5)
  braucht `libXft.so.2` und `libXrender.so.1`; im .deb/.rpm sind sie
  Abhängigkeiten, im AppImage fehlten sie, und Kinoite hat sie nicht. Im
  Terminal: `ImportError: libXft.so.2: cannot open shared object file`.
  Seitdem legt `build_packages.sh` (`bundle_xft_libs`) beide ins AppImage.
  libX11, fontconfig und freetype bleiben **bewusst** draußen (AppImage-
  „excludelist": die hat jeder Desktop, eine fremde fontconfig passt nicht zur
  Schriftkonfiguration des Systems).
- **FUSE war nicht schuld.** appimagetool 1.9 schreibt die statische
  type2-Runtime (bringt libfuse3 mit, ruft nur `fusermount3`); das fuse2, das
  Fedora 44 aus den Atomic Desktops entfernt hat, braucht sie nicht.
- **Prüfen ohne Kinoite:** quay.io (Kinoite-Abbild) und die Fedora-Mirrors sind
  im Cloud-Container gesperrt. Ersatz: `ubuntu:24.04` mit `xvfb xdotool
  x11-apps`, danach `dpkg --purge --force-depends libxft2 libxrender1` — so
  fehlen dieselben Bibliotheken wie auf Kinoite. Dort das AppImage mit
  `--appimage-extract-and-run` starten (kein FUSE im Container), mit `xdotool`
  durch alle sechs Schritte klicken, `xwd -root` + `convert` für Screenshots.
  Fehlende Bibliotheken zusätzlich mit `ldd` in nacktem `fedora:latest` prüfen.
- **`QslMono` & Co. gab es nie — auf keiner Plattform.** `theme._configure_fonts`
  legte die eigenen Schriften mit `tkfont.Font(name=…, exists=False)` an und
  behielt das Objekt nicht; dessen `__del__` ruft `font delete`, die Schrift war
  sofort wieder weg. Tk las „QslMono" danach als **Familienname** und nahm eine
  Ersatzschrift in Standardgröße — unter Linux standen Vorschautabelle und
  Schrittleiste in großer Noto Sans neben 12-px-Text. Jetzt direkt über Tcl
  (`font create`/`font configure`), ein Test prüft nach `gc.collect()`. Faustregel:
  ein `tkfont.Font`, das einen Namen anlegt, muss **gehalten** werden.
- Im selben Testlauf gefunden und behoben: schwarzer Doppelrand und Text am
  Rand der Zustellwege-Liste (`relief="solid"` unter X11 → jetzt flacher Rand
  in Flächenfarbe + 1-px-Ring), `*kursiv*` stand roh im Handbuch (Renderer
  kann es jetzt), ein getippter Bildpfad zeigte keine Vorschau
  (`_on_image_entry_commit` beim Verlassen des Feldes), die Bemerkung war in der
  Vorschautabelle schon nach 20 Zeichen abgeschnitten (nur „Remarks" wächst
  jetzt mit dem Fenster, die übrigen Spalten haben feste, ausreichende Breiten),
  und der Hinweis „PDF erzeugt" brach lange Pfade mitten im Dateinamen um
  (`app_print.done_message`: Ordner + Dateinamen je eine Zeile).
- **Das Linux-tar.gz von 0.4.2 hat noch Pixelschrift**: `build_app.py` packt es,
  bevor `tk_xft.sh` das Tk tauscht. Der Release-Workflow ruft danach
  `build_app.package_tar` erneut auf. Prüfen: `strings …/libtcl9tk9.0.so | grep -ci xft`
  (ohne Xft: 1 Treffer, mit: ~30).

**Workflow-Konventionen**
- Branch **`build/mvp`**. **Nicht selbst committen** — erst nach Review; committen,
  wenn der Nutzer die nächste Aufgabe vorschlägt. Commit-Messages Deutsch, Präfixe
  `feat/fix/docs/chore`, GUI-Zwischenstände als **WIP** markieren.
- IDE-Dateien (`.idea/`, `.DS_Store`) nie mitcommitten.
- Doku-Änderungen erst nach Abnahme des Codes.
- **Vor jedem Push und nach jeder Programmänderung das gebaute Programm testen**
  (Vorgabe von Meister, 2026-11-27): so, wie es auf GitHub landet — Paket wie in
  der CI bauen (Linux: `ubuntu:22.04`, `build_app.py`, `tk_xft.sh`,
  `build_packages.sh`), mit **echtem Fensterstart** durch alle Schritte klicken,
  PDF erzeugen, Screenshots ansehen. Jede Funktion muss gehen, alle Texte und
  Grafiken müssen sauber sein. Grüne Unit-Tests allein genügen nicht: das
  AppImage 0.4.2 war trotz grüner Tests auf Kinoite nicht startfähig.
- **Weitergeben nur über Git** (Klon oder `git bundle create … --all`), nie den
  Arbeitsordner: darin liegen `config.yaml`, `lookup_cache.json` (Anschriften
  fremder Stationen), die Logs, PDFs und ein venv mit fremden Pfaden.
