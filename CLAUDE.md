# CLAUDE.md — QSL-Karten-Generator

Diese Datei ist die zentrale Anleitung für Claude Code. Sie beschreibt Ziel,
Technik-Stack, Architektur, Konventionen und die empfohlene Build-Reihenfolge.
Details stehen in `docs/SPECIFICATION.md` und `docs/CARD_LAYOUT.md`.

---

## 1. Ziel des Projekts

Ein Desktop-Programm (Python + Tkinter), das aus einem **ADIF-Logbuch**
automatisch **QSL-Karten** erzeugt und als **eine große PDF** ausgibt.

- Jede Karte = **2 A6-Seiten**: Vorderseite (Bild) + Rückseite (QSL-Layout).
- Die Rückseite folgt **exakt** dem Referenz-Layout aus `docs/CARD_LAYOUT.md`
  (Vorlage: DARC-QSL-Karte, Rückseite von DN5MT).
- Ein **einziges Frontbild** wird für **alle** Karten verwendet.
- Absenderdaten kommen aus der **Config**, QSO-Daten aus dem **ADIF-Log**,
  Empfängerdaten bei Bedarf aus **HamQTH** (primär) bzw. **QRZ** (optional).
- Karten werden nach **Via** gefiltert (`QSL_SENT_VIA`: B/D/E/M).
- Modus wählbar: **eine Karte pro QSO** oder **eine Karte pro Station**.

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

Bewusst **kein** externes ADIF-Package: eigener, getesteter Parser (Anforderung).

---

## 3. Projektstruktur

```
qslcards/
  __init__.py
  main.py                 # Einstiegspunkt: startet die GUI
  config.py               # Config-Dataclasses + Laden/Speichern (YAML)
  adif/
    __init__.py
    parser.py             # ADIF-Tokenizer + Record-Parser
    models.py             # QSO-Dataclass
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
    generator.py          # orchestriert die Gesamt-PDF (alle Karten)
  gui/
    __init__.py
    app.py                # Hauptfenster, verdrahtet alles
    sections.py           # UI-Abschnitte (Datei, Bild, Absender, Filter, ...)
    preview.py            # Tabelle: geparste & gefilterte QSOs/Karten
tests/
  test_adif_parser.py
  test_card_builder.py
  test_geometry.py
config.example.yaml       # Vorlage -> Nutzer kopiert nach config.yaml
requirements.txt
README.md
docs/
  SPECIFICATION.md        # ausführliche Funktions-/Technik-Spezifikation
  CARD_LAYOUT.md          # exakte Layout-Spezifikation der Rückseite
```

---

## 4. Datenfluss (Big Picture)

```
ADIF-Datei ──parser──> [QSO, QSO, ...] ──builder(Filter Via + Gruppierung)──> [Card, ...]
                                                    │
Config (Absender) ──────────────────────────────────┤
                                                    │
Frontbild ──────────────────────────────────────────┤
                                                    ▼
HamQTH/QRZ (nur bei Bedarf, gecacht) ──> Recipient-Adresse ──> generator ──> gesamt.pdf
```

Jede `Card` erzeugt genau zwei Seiten: `layout_front` + `layout_back`.

---

## 5. Wichtige fachliche Regeln (nicht raten — hier steht's)

1. **Signalrapport auf der Karte = `RST_SENT`** (der Rapport, den *wir* dem
   Gegenüber gegeben haben = wie wir ihn gehört haben). Nicht `RST_RCVD`.
2. **Via-Filter** = ADIF-Feld `QSL_SENT_VIA`. Enum: `B`=Büro, `D`=Direkt,
   `E`=Elektronisch, `M`=Manager. Nur QSOs mit ausgewähltem Via werden zu Karten.
   Fehlt das Feld, gilt ein konfigurierbarer Default (siehe Config).
3. **Absenderblock** (Call, Name, Straße, PLZ/Ort, Land, Locator, DOK, WAZ, ITU)
   kommt **immer aus der Config**, nie aus dem Log.
4. **Empfänger** auf der Karte = **nur das Rufzeichen** (`CALL`) im Feld
   „To Amateur Radio Station:". Name/Adresse des Empfängers stehen **nicht** auf
   der Karte — sie werden nur für den **optionalen Adress-/Label-Export** (Kuvert
   bei Direkt-Karten) per Lookup geholt, und nur **wenn benötigt**.
5. **Lookup nur bei Bedarf**: Adress-Lookup standardmäßig nur für via=`D`
   (Direkt) und nur, wenn der Adress-/Label-Export aktiviert ist. Ergebnisse
   werden gecacht (`lookup/cache.py`), um API-Limits zu schonen.
6. **Karte pro QSO vs. pro Station**: Bei „pro Station" werden alle QSOs mit
   demselben Call (innerhalb desselben Via) zu **einer** Karte zusammengefasst;
   die Tabelle bekommt dann **mehrere Zeilen** (max. Zeilenzahl aus
   `CARD_LAYOUT.md`, Rest ggf. Folge-Karte).

---

## 6. Modul-Verträge (Contracts)

### `adif/models.py`
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
    qsl_sent_via: str | None   # B/D/E/M oder None
    qsl_via: str | None        # Manager/Route-Text
    name: str | None           # falls im Log vorhanden
    gridsquare: str | None
    raw: dict[str, str]        # alle Felder roh, kleingeschrieben
```

### `adif/parser.py`
- `parse_file(path) -> list[QSO]`
- `parse_text(text) -> list[QSO]`
- Algorithmus in `docs/SPECIFICATION.md` §ADIF-Parser. Robust gegen: fehlenden
  Header, gemischte Groß/Kleinschreibung, Typ-Suffixe (`<FREQ:5:N>`), `<EOH>`,
  `<EOR>`, Zeilenumbrüche innerhalb von Werten.

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
    source: str          # "hamqth" | "qrz" | "cache" | "none"

class LookupProvider(Protocol):
    def lookup(self, call: str) -> LookupResult | None: ...
```
- HamQTH: Session per `u`/`p` holen, dann `id`+`callsign` abfragen; Session ~1h
  gültig, bei Ablauf neu anmelden. Endpunkte/Details in `docs/SPECIFICATION.md`.
- QRZ: nur wenn Credentials gesetzt; ohne bezahltes Abo liefert QRZ nur
  eingeschränkte Felder → als „best effort" behandeln, Fehler nicht fatal.

### `cards/builder.py`
- `build_cards(qsos, config) -> list[Card]`
- filtert nach `config.via_filter`, gruppiert nach `config.card_mode`
  (`per_qso` | `per_station`), sortiert deterministisch (Call, dann Datum/Zeit).

### `pdf/generator.py`
- `generate(cards, config, front_image_path, output_path, progress_cb=None)`
- iteriert Karten; pro Karte `draw_front(canvas, ...)` dann
  `draw_back(canvas, card, config)`, `canvas.showPage()` zwischen den Seiten.

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
2. **`adif/parser.py` + `adif/models.py`** — mit `tests/test_adif_parser.py`
   (Beispiel-ADIF in Test einbetten; Kantenfälle abdecken).
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

- [x] ADIF-Datei wählbar, Parser liefert korrekte QSO-Liste (Tests grün).
- [x] Frontbild wählbar + Vorschau.
- [x] Absender-Config editierbar, wird gespeichert/geladen.
- [ ] Via-Filter (B/D/E/M) und Modus (pro QSO / pro Station) wählbar.
- [ ] Vorschau-Tabelle zeigt, welche Karten erzeugt werden.
- [x] „PDF erzeugen" liefert eine PDF mit 2 A6-Seiten pro Karte.
- [ ] Rückseite entspricht `docs/CARD_LAYOUT.md` (visuell iteriert).
- [ ] HamQTH-Lookup + Cache funktionieren; Ausfälle sind nicht fatal.
---

## 10. Nicht raten — nachschlagen

- ADIF-Feldnamen/Enums: `docs/SPECIFICATION.md` §ADIF-Felder.
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
  zeigen. Es sind 3 Beispiel-QSOs (6 Seiten).
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

**Layout-Wahrheit**
- **Alle** Layout-Zahlen stehen in `pdf/geometry.py` (maßgeblich; `docs/CARD_LAYOUT.md`
  ist nur Beschreibung). Positionen als `yt` (von oben), Umrechnung in den
  `text`/`checkbox`/`_box`-Helfern. Font-Metriken (`getAscent`/`getDescent`) statt
  Magic-Faktoren fürs Zentrieren.
- **DejaVuSans** (regular+bold) liegt gebündelt in `qslcards/assets/fonts/` und wird
  in `geometry.py` registriert (Umlaute); Fallback Helvetica, Registrierung nie fatal.

**Wichtige, mit dem Nutzer getroffene Entscheidungen (nicht ohne Rückfrage kippen)**
- **`MAX_ROWS = 1`**: genau ein QSO pro Karte. Koppelt Layout **und** Builder;
  `per_station` teilt Mehrfach-QSOs in Einzelkarten. (Weicht von „bis 3 Zeilen" ab.)
- **Kein `subtitle`/„Responsive"** — komplett entfernt.
- **Front im Cover-Modus** (füllt die Seite randlos, Überstand wird geclippt).
- `MARGIN = 3 mm`; `/p`/`/m` oben mittig; Stationsdaten als Label/Wert-Spalte neben
  der Adresse; REMARKS über volle Breite; Fuß unten mit ~3 mm Rahmenabstand.
- **GUI: keine Speichern/Laden-Buttons** — Config wird automatisch gespeichert
  (debounced) und bei externer Datei-Änderung neu geladen (mtime-Poll, Loop-Schutz
  via `_suppress_save`). Enter in Eingabefeldern gibt den Fokus frei.

**Realität der Testdaten (`Log.adi`)**
- Enthält **kein** `QSL_SENT_VIA` → ohne `include_missing_via: true` (+ `default_via`)
  entstehen 0 Karten. Jede Station kommt nur 1× vor.
- FT8-QSOs haben dB-Rapporte (z. B. `-07`), die **bewusst** nicht sinnvoll ins
  R/S/T-Raster passen (so vom Nutzer akzeptiert).

**Workflow-Konventionen**
- Branch **`build/mvp`**. **Nicht selbst committen** — erst nach Review; committen,
  wenn der Nutzer die nächste Aufgabe vorschlägt. Commit-Messages Deutsch, Präfixe
  `feat/fix/docs/chore`, GUI-Zwischenstände als **WIP** markieren.
- IDE-Dateien (`.idea/`, `.DS_Store`) nie mitcommitten.
- Doku-Änderungen erst nach Abnahme des Codes.
