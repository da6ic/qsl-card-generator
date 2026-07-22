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
4. **Via-Filter**: vier Checkboxen `B Büro`, `D Direkt`, `E Elektronisch`,
   `M Manager`. Zusätzlich Checkbox „QSOs ohne Via einbeziehen" (nutzt Default-Via).
5. **Kartenmodus**: Radiobuttons `Eine Karte pro QSO` / `Eine Karte pro Station`.
   (Die globalen Markierungen QSL/Portabel stehen in Abschnitt 3.)
6. **Lookups (optional)**: HamQTH-Benutzer/Passwort, QRZ-Benutzer/Passwort,
   Checkbox „Adressen für Direkt-Karten nachschlagen", Checkbox „Adress-/
   Label-Export erzeugen".
7. **Vorschau**: Tabelle (`ttk.Treeview`) der Karten, die erzeugt werden
   (Call, #QSOs, Via, Datum, UTC). Zeilen über die Spalte „Drucken" abwählbar
   (Karte auslassen). Die gesamte Oberfläche ist scrollbar; die Tabelle zeigt
   mindestens ~5 Einträge.
8. **Ausgabe**: Zielpfad der PDF, Button `PDF erzeugen`, Fortschrittsbalken
   (`ttk.Progressbar`) + Statuszeile.

Langlaufende Arbeit (PDF, Lookups) läuft in einem **Worker-Thread**; UI-Updates
nur über `root.after(...)` (Tkinter ist nicht thread-safe).

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
    lookup_addresses: bool = False # nur wenn Adress-/Label-Export nötig
    address_export: bool = False

@dataclass
class GenerationConfig:
    card_mode: str = "per_qso"         # "per_qso" | "per_station"
    via_filter: list[str] = ["B","D","E","M"]
    include_missing_via: bool = False
    default_via: str = "B"             # gilt für QSOs ohne QSL_SENT_VIA
    page_orientation: str = "landscape" # A6, siehe CARD_LAYOUT.md
    static_footer: str = "TNX FR NICE CONTACT, 73"
    qsl_mark: str = "none"             # "pse" | "tnx" | "none" (global)
    portable_mark: str = "none"        # "none" | "p" | "m" (global)

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
| `qsl_sent_via`   | `qsl_sent_via`   | **→ Via-Filter** (B/D/E/M)                 |
| `qsl_via`        | `qsl_via`        | Manager/Route-Text → Feld „Via:" auf Karte |
| `name`           | `name`           | falls vorhanden                            |
| `gridsquare`     | `gridsquare`     |                                            |
| (alle)           | `raw`            | vollständiger Roh-Record                   |

`qsl_sent_via` auf Großbuchstaben normalisieren, nur erstes Zeichen `B/D/E/M`
berücksichtigen. Unbekannt/leer → als „ohne Via" behandeln.

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
    # Empfängeradresse nur bei Bedarf gefüllt (Export), NICHT auf der Karte:
    recipient: LookupResult | None = None
```

### 5.2 Ablauf `build_cards(qsos, config)`
1. **Filtern**: QSO behalten, wenn `qsl_sent_via` in `via_filter`; QSOs ohne Via
   nur, wenn `include_missing_via` (dann `default_via` verwenden).
2. **Datum splitten**: `qso_date` "YYYYMMDD" → `date_y=YY` (2-stellig, wie
   Referenz „D M Y"), `date_m=MM`, `date_d=DD`. (Reihenfolge auf der Karte: D M Y.)
3. **UTC**: `time_on` → "HH:MM" (Sekunden abschneiden, sofern vorhanden).
4. **freq_mhz**: aus `freq`; fehlt es, aus `band` ableiten (optionale Tabelle).
5. **Gruppieren**:
   - `per_qso`: eine `Card` je QSO, `rows` mit genau einer Zeile.
   - `per_station`: QSOs je (Call, Via) sortiert nach Datum/Zeit, dann in
     `MAX_ROWS`-große Blöcke aufgeteilt. Da aktuell **`MAX_ROWS = 1`** ist
     (eine Zeile pro Karte, siehe `CARD_LAYOUT.md`), ergibt eine mehrfach
     gearbeitete Station mehrere Einzelkarten.
6. **Sortierung**: Karten deterministisch nach `recipient_call`, dann Datum.
7. **Markierungen (global, manuell)**: jede Karte erhält unverändert die
   Werte aus der Config:
   - `card.qsl_mark = config.qsl_mark` (`"pse"` | `"tnx"` | `"none"`).
   - `card.portable_mark = config.portable_mark` (`"none"` | `"p"` | `"m"`).
   Es gibt **keine** automatische Ableitung aus dem Log; der Nutzer wählt die
   Markierungen in der GUI/Config, sie gelten für **alle** Karten gleich.

---

## 6. Lookups (`lookup/`)

> Vor Implementierung gegen die **aktuelle** Doku prüfen; Endpunkte können sich
> ändern. Netz-/Auth-Fehler sind **nie** fatal.

### 6.1 HamQTH (primär, kostenlos — kostenloses Konto nötig)
- Session holen: `https://www.hamqth.com/xml.php?u=USER&p=PASS`
  → XML mit `<session_id>`. Session ~1 Stunde gültig.
- Abfrage: `https://www.hamqth.com/xml.php?id=SESSION&callsign=CALL&prg=PROGRAMID`
  → XML mit Feldern wie `nick`/`name`, `adr_street1`, `adr_city`, `adr_zip`,
  `country`, `grid` (Feldnamen an aktueller Doku verifizieren).
- Bei „session does not exist / expired" → neu anmelden, einmal wiederholen.

### 6.2 QRZ (optional)
- Session: `https://xmldata.qrz.com/xml/current/?username=USER;password=PASS;agent=qslcards1.0`
  → `<Key>`.
- Abfrage: `https://xmldata.qrz.com/xml/current/?s=KEY;callsign=CALL`.
- **Ohne bezahltes XML-Abo** sind Adressfelder oft leer/limitiert → als
  „best effort" behandeln, Ausfall ignorieren.

### 6.3 Cache (`lookup/cache.py`)
- JSON-Datei `lookup_cache.json`: `{ "CALL": LookupResult, ... }`.
- Vor jeder API-Abfrage Cache prüfen; Ergebnisse (auch negative) cachen.
- Cache-Alter optional beachten (z.B. 180 Tage), sonst dauerhaft.

### 6.4 Wann wird gelookt?
- Nur wenn `lookup.lookup_addresses == True`.
- Standardmäßig nur für Karten mit `via_code == "D"` (Direkt), da nur dort eine
  Postadresse gebraucht wird. (Konfigurierbar erweiterbar.)

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
  Größen aus `geometry.py`.
- **Fortschritt**: `generator.generate(..., progress_cb)` ruft
  `progress_cb(done, total)` nach jeder Karte → GUI aktualisiert Balken via
  `root.after`.
- **Adress-/Label-Export (optional)**: zusätzlich zu den Karten eine zweite
  PDF (oder CSV) mit Empfängeradressen für via=D erzeugen, wenn
  `address_export == True`. Format simpel (Adressblöcke), separat von den Karten.

---

## 8. Fehler- & Randfälle

| Fall                                   | Verhalten                                   |
|----------------------------------------|---------------------------------------------|
| ADIF unlesbar/leer                     | GUI-Meldung, keine Karten                   |
| QSO ohne `call`                        | überspringen                                |
| kein Via im QSO                        | nur mit `include_missing_via` einbeziehen   |
| Frontbild fehlt                        | Erzeugung blockieren + Hinweis              |
| Lookup schlägt fehl / kein Konto       | Adressfelder leer, kein Abbruch             |
| zu viele QSOs pro Station für Tabelle  | Folge-Karte(n) anlegen                      |
| Umlaute/UTF-8 im Namen                 | korrekt kodieren (ReportLab-Font mit Umlauten) |

**Fonts/Umlaute**: Standard-PDF-Fonts (Helvetica) unterstützen Latin-1-Umlaute.
Für saubere Umlaute ggf. eine TrueType-Font (z.B. DejaVu Sans) registrieren und
in `geometry.py` referenzieren.

---

## 9. Tests (`tests/`)
- `test_adif_parser.py`: alle Fälle aus §4.4.
- `test_card_builder.py`: Via-Filter, Datum-Split, Gruppierung per_qso/per_station,
  MAX_ROWS-Überlauf.
- `test_geometry.py`: mm-Umrechnung, Seitenmaße, dass alle Konstanten definiert
  sind und im Blattbereich liegen.
- PDF-Erzeugung: Smoke-Test (läuft ohne Exception, erzeugt Datei mit
  2 × Kartenanzahl Seiten).
