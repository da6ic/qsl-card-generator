# SPECIFICATION.md — QSL-Karten-Generator

Ausführliche Spezifikation. Ergänzt `CLAUDE.md`. Layout separat in `CARD_LAYOUT.md`.

---

## 1. Anwendungsfall

Ein Funkamateur (Absender, z.B. DN5MT) hat ein Logbuch im ADIF-Format. Er will
QSL-Karten für bestätigte QSOs drucken. Das Programm erzeugt eine PDF, in der
jede Karte aus zwei A6-Seiten besteht (Bild vorne, Daten hinten). Vor der
Erzeugung wählt er ADIF, Frontbild, Absenderdaten, Via-Filter und Kartenmodus.

---

## 2. GUI (Tkinter)

Ein Hauptfenster mit klaren Abschnitten (top → bottom), jeweils in `gui/sections.py`:

1. **ADIF-Logbuch**: `Durchsuchen…`-Button, Pfadanzeige, Button `Log laden`.
   Nach der Auswahl wird das Log **automatisch geladen** (Hot-Load); der Button
   dient als manueller Reload. Nach dem Laden: Anzahl gelesener QSOs.
2. **Frontbild**: `Bild wählen…` (png/jpg/jpeg/webp), kleine Vorschau (Thumbnail).
3. **Absender**: Eingabefelder für Call, Name, Straße, PLZ, Ort, Land, Locator,
   DOK, WAZ, ITU. Zusätzlich die beiden globalen Dropdowns (gelten für **alle**
   Karten):
   - **QSL-Markierung** (`qsl_mark`): `PSE QSL` / `TNX QSL` / `Leer lassen`.
   - **Portabel-Markierung** (`portable_mark`): `Keins` / `/p` / `/m`.
   Kein „Untertitel"/„Responsive" mehr. Keine Speichern/Laden-Buttons: die
   Config wird **automatisch** gespeichert (debounced) und bei externer Änderung
   von `config.yaml` **automatisch neu geladen**.
4. **Via-Filter**: drei Checkboxen `B Büro`, `D Direkt`, `M Manager`. **Kein**
   `E`-Filter (Elektronisch ist eine Ausschluss-Kategorie, kein Druckweg — siehe
   §6). Der Filter **entfernt keine Zeilen**, sondern setzt nur die Drucken-
   Markierung: gedruckt werden Karten mit `via_code ∈ Filter` (E-Karten sind
   damit standardmäßig abgewählt). Die Via je Karte kommt aus dem **Lookup**
   (§6), nicht aus dem Log.
5. **Kartenmodus**: Radiobuttons `Eine Karte pro QSO` / `Eine Karte pro Station`.
   (Die globalen Markierungen QSL/Portabel stehen in Abschnitt 3.)
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
   `Remarks`, `Datum`, `UTC`. Solange der Lookup läuft, zeigt die `Via`-Zelle „…".
   Zeilen sind über die Spalte „Drucken" ab-/anwählbar (auch E-Zeilen manuell
   aktivierbar). **`Via`, `Route/Manager` und `Remarks` sind per Doppelklick
   editierbar** (`Via` als Auswahl B/D/M/E, die anderen als Textfeld; `Remarks`
   max. 80 Zeichen) — so lassen sich Lookup-Fehlklassifizierungen von Hand
   korrigieren und Remarks je Karte setzen. Eine Via-Änderung zieht die
   Drucken-Markierung der Zeile nach. Eine **Remarks-Änderung** normalisiert im
   Modus „pro Station" die Karten der Station: Karten mit Remarks bleiben
   eigenständig (max. 3 Zeilen), aufeinanderfolgende Karten **ohne** Remarks
   führen sich wieder zusammen (max. 6 Zeilen) — so ist ein Remarks je Karte
   unabhängig möglich (§5.2). Die Korrekturen gelten für die Sitzung; ein
   erneuter Lookup („Neu abrufen"/Log neu laden) leitet Via/Remarks wieder ab.
   **Oben rechts** ein Button „Neu abrufen" (holt fehlende/abgebrochene Stationen
   nach) sowie eine Lookup-Statuszeile. Die gesamte Oberfläche ist scrollbar; die
   Tabelle zeigt mindestens ~5 Einträge.
9. **Ausgabe**: Zielpfad der PDF, Button `PDF erzeugen`, Fortschrittsbalken
   (`ttk.Progressbar`) + Statuszeile. `PDF erzeugen` ist **deaktiviert**, solange
   der Lookup nach dem Log-Laden noch läuft, und wird erst danach wieder aktiv.

Langlaufende Arbeit (PDF, Lookups) läuft in einem **Worker-Thread**; UI-Updates
nur über `root.after(...)` (Tkinter ist nicht thread-safe). Der Lookup startet
automatisch beim Log-Laden im Hintergrund, ohne die GUI zu blockieren (Bild/
Einstellungen bleiben bedienbar); es läuft immer nur **ein** Lookup-Thread.

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
    waz: str                 # "14"
    itu: str                 # "28"

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
    via_filter: list[str] = ["B","D","M"]   # Druck-Kategorien; E nie im Filter
    default_via: str = "B"             # Fallback, wenn der Lookup nichts/"?" liefert
                                       #   -> NUR hier in der Config, kein GUI-Widget
    page_orientation: str = "landscape" # A6, siehe CARD_LAYOUT.md
    static_footer: str = "TNX FR NICE CONTACT, 73"
    remarks: str = ""                  # globaler REMARKS-Text (alle Karten); leer
                                       #   -> kein Kasten. Max. 80 Zeichen (GUI).
    qsl_mark: str = "none"             # "pse" | "tnx" | "none" (global)
    portable_mark: str = "none"        # "none" | "p" | "m" (global)
    # Hinweis: KEIN `include_missing_via` mehr — die Via steht nie im Log,
    # sie wird immer per Lookup bestimmt (§6).

@dataclass
class AppConfig:
    sender: SenderConfig
    lookup: LookupConfig
    generation: GenerationConfig
```

`load(path) -> AppConfig` / `save(config, path)`. Fehlende Felder → Defaults.

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
    via_text: str              # Feld "Via:" (aus qsl_via oder leer)
    via_code: str              # B/D/E/M (für Export/Sortierung)
    rows: list[CardRow]        # 1..N (per_station kann mehrere haben)
    qsl_mark: str = "none"     # global aus config: "pse" | "tnx" | "none"
    portable_mark: str = "none" # global aus config: "none" | "p" | "m"
    remarks: str = ""          # REMARKS-Text dieser Karte (leer -> kein Kasten);
                               #   Default = config.remarks, je Karte überschreibbar
    # Empfängeradresse nur bei Bedarf gefüllt (Export), NICHT auf der Karte:
    recipient: LookupResult | None = None
```

### 5.2 Ablauf `build_cards(qsos, config, lookups=None)`
1. **Kein Via-Filter!** `build_cards` behält **alle** QSOs. Die Via kommt nicht
   aus dem Log, sondern aus dem Lookup (§6): `lookups` ist eine Map
   `CALL -> LookupResult`. Je Karte wird gesetzt:
   - `via_code = derive_via(lookups[call], config.default_via)` (Priorität
     M > B > D > E, Fallback `default_via`; siehe §6).
   - `via_text = lookups[call].manager` (Manager-Ruf oder leer) → Feld „Via:".
   - `recipient = lookups[call]` (Adresse, nur für den Export; nicht auf der Karte).
   Fehlt `lookups` oder der Eintrag → `via_code = default_via`, `via_text` leer.
   Das **Drucken/Abwählen** übernimmt die GUI anhand des Via-Filters (E-Karten
   standardmäßig abgewählt), nicht der Builder.
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
   - `card.portable_mark = config.portable_mark` (`"none"` | `"p"` | `"m"`).
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

### 6.2 Via-Ableitung `derive_via(result, default_via) -> "B"|"M"|"D"|"E"`
Feste Priorität (Ham-Standard: Manager hat Vorrang; Elektronisch schließt nur
aus, wenn **kein** Papierweg vorhanden ist):
1. `manager` gesetzt → **M** (drucken; Manager ins Feld „Via:").
2. sonst `accepts_bureau == "Y"` → **B** (drucken).
3. sonst `accepts_direct == "Y"` → **D** (drucken).
4. sonst `lotw == "Y"` oder `eqsl == "Y"` → **E** (Station wird in der Tabelle
   angezeigt, aber **standardmäßig nicht gedruckt**; manuell aktivierbar).
5. sonst (nichts/„?"/kein Treffer/Lookup-Fehler) → **`default_via`** (Default „B").

`E` ist damit **kein** Druckweg, sondern eine Ausschluss-Kategorie.

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
- **Reihenfolge**: für jede Karte zuerst Vorderseite, dann Rückseite, dann
  `canvas.showPage()`. So entsteht Seite 1=Front(Karte1), 2=Back(Karte1),
  3=Front(Karte2), … → passt für Duplexdruck (lange Kante).
- **Front** (`layout_front.py`): Frontbild im **Cover-Modus** die ganze Seite
  füllen (kein weißer Rand), Seitenverhältnis wahren, Überstand am Seitenrand
  beschneiden (Clip), zentriert. Einmal via Pillow geladen und als ImageReader
  gecacht, für alle Karten wiederverwenden.
- **Back** (`layout_back.py`): exakt nach `CARD_LAYOUT.md`. Alle Positionen/
  Größen aus `geometry.py`. Der REMARKS-Block (Label + Kasten + Text) wird nur
  gezeichnet, wenn `card.remarks` gesetzt ist (dynamisch); der Footer-Text steht
  immer.
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
| Lookup ohne Treffer/„?"                | Via = `default_via` (Config), Karte trotzdem |
| Station nur elektronisch (LoTW/eQSL)   | Via = `E`, angezeigt, nicht gedruckt (manuell aktivierbar) |
| keine Lookup-Credentials               | kein Netzcall, alle Via = `default_via`     |
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
- `test_card_builder.py`: alle QSOs (kein Via-Filter mehr), Via aus Lookup-Map +
  `default_via`-Fallback, Datum-Split, Gruppierung per_qso/per_station,
  Zeilen-Überlauf (MAX_ROWS_PLAIN/WITH_REMARKS), `regroup_card_by_remarks` und
  `normalize_station_cards` (Split/Merge, Remarks je Karte, Idempotenz).
- `test_lookup.py`: `derive_via`-Priorität M>B>D>E (inkl. E nur ohne Papierweg,
  Fallback `default_via`), Parsing der Routing-Felder (HamQTH inkl. lotw/eqsl,
  QRZ-Manager), Enrichment über alle Stationen, Cache, Reauth — HTTP gemockt.
- `test_geometry.py`: mm-Umrechnung, Seitenmaße, dass alle Konstanten definiert
  sind und im Blattbereich liegen.
- PDF-Erzeugung: Smoke-Test (läuft ohne Exception, erzeugt Datei mit
  2 × Kartenanzahl Seiten).
