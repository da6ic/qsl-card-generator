# CARD_LAYOUT.md — Rückseiten-Layout

Exakte Layout-Spezifikation der **Rückseite** nach der Referenzkarte (DARC-QSL,
DN5MT). Alle Zahlen sind **Startwerte**: rendern, mit der Referenz vergleichen,
Konstanten in `pdf/geometry.py` iterativ feinjustieren. Die Front ist nur das
eingepasste Bild und braucht keinen Detailplan.

---

## 1. Seitengeometrie

- Format: **A6**, **Querformat** → `148 mm × 105 mm` (Breite × Höhe).
- ReportLab-Ursprung ist **unten links**. In diesem Dokument werden Positionen
  als `x` (von links) und `yt` (von **oben**) angegeben, weil das leichter mit der
  Vorlage abzugleichen ist. Umrechnung im Code:
  `y_pdf = PAGE_H - yt`.
- Außenrand des Rahmens: `MARGIN = 3 mm` ringsum (nah am Blattrand).
- Standard-Linienstärke Rahmen: `0.6 pt`. Schrift: **DejaVuSans** (regular/bold),
  registriert für saubere Umlaute; Fallback Helvetica (siehe SPECIFICATION §8).

`geometry.py` stellt bereit:
```python
MM = 72 / 25.4                      # Punkte pro mm
def mm(v): return v * MM
PAGE_W, PAGE_H = mm(148), mm(105)   # Querformat A6
MARGIN = mm(3)
```

> **Maßgeblich sind die Konstanten in `pdf/geometry.py`.** Die Zahlen hier sind
> der Stand des Referenz-Nachbaus; bei Abweichungen gilt der Code.

---

## 2. Zonen-Übersicht (Skizze, nicht maßstабsgetreu)

```
(0,0) oben-links ───────────────────────────────────────────────► x
│  ┌──────────────────────────────────────────────────────────┐
│  │ DN5MT        ☐ /p   ☐ /m       To Amateur Radio Station:  │
│  │                                ┌────────────────────────┐ │
│  │ Axel Tüner     Locator: JN48OM │ <CALL>                 │ │
│  │ Wilhelmstr.76  DOK:     P31    └────────────────────────┘ │
│  │ 72124 Ort      WAZ:     14     Via:                       │
│  │ Deutschland    ITU:     28     ┌────────────────────────┐ │
│  │                                │ <VIA_TEXT>             │ │
│  │ ☐ Confirming QSO   ☐ Confirming SWL-Report               │
│  │ ┌──────┬───────┬─────────┬──────────┬──────────────┐      │
│  │ │ DATE │UNIV.  │FREQUENCY│ 2-WAY    │SIGNAL REPORT │      │
│  │ │D M Y │TIME UTC│  MHZ   │ QSO  IN  │  R   S   T   │      │
│  │ ├──┬─┬─┼───────┼─────────┼──────────┼───┬───┬──────┤      │
│  │ │  │ │ │       │         │          │   │   │      │ row  │
│  │ └──┴─┴─┴───────┴─────────┴──────────┴───┴───┴──────┘      │
│  │ REMARKS                                                   │
│  │ ┌────────────────────────────────────────────────────────┐│
│  │ └────────────────────────────────────────────────────────┘│
│  │ TNX FR NICE CONTACT, 73        ☐ PSE QSL   ☐ TNX QSL       │
│  └──────────────────────────────────────────────────────────┘
▼ yt
```

Gegenüber der Original-DARC-Karte bewusst geändert: kein „Responsive"-Untertitel,
`/p`/`/m` oben zwischen eigenem Call und dem „To Amateur…"-Block, Stationsdaten
(Locator/DOK/WAZ/ITU) als Spalte neben der Adresse, nur **eine** Datenzeile
(`MAX_ROWS = 1`), REMARKS über die volle Breite mit Footer darunter (kein
TRAINEE-Feld).

---

## 3. Elemente (Inhalt, Quelle, Schrift, Startposition)

Positionen `x / yt` in mm, gemessen von der oberen linken Blattecke. `size` in pt.
Schrift = DejaVuSans (regular/bold). Linksbündig, sofern nicht anders angegeben.

### Kopf links
| Element        | Inhalt / Quelle            | x   | yt   | Font/Size   |
|----------------|----------------------------|-----|------|-------------|
| Rufzeichen     | `sender.callsign`          | 6   | 6    | Bold 22     |
| Adresse Z1     | `sender.name`              | 6   | 18   | Regular 9   |
| Adresse Z2     | `sender.street`            | 6   | 23.5 | Regular 9   |
| Adresse Z3     | `sender.zip` + " " + `city`| 6   | 29   | Regular 9   |
| Adresse Z4     | `sender.country`           | 6   | 34.5 | Regular 9   |

Kein „Untertitel"/„Responsive" mehr (Feld `subtitle` entfernt).

### Portabel-Markierungen (oben mittig)
| Element | Inhalt / Quelle                     | x  | yt | Font/Size |
|---------|-------------------------------------|----|----|-----------|
| ☐ /p    | checked, wenn `portable_mark=="p"`  | 52 | 8  | Regular 8 |
| ☐ /m    | checked, wenn `portable_mark=="m"`  | 66 | 8  | Regular 8 |

### Kopf rechts (Empfänger + Via)
| Element              | Inhalt / Quelle          | x   | yt  | Font/Size |
|----------------------|--------------------------|-----|-----|-----------|
| Label „To Amateur…"  | statisch                 | 88  | 8   | Regular 10|
| Box + Call           | `card.recipient_call`    | 88  | 12  | Bold 16   |
|  Box-Maße            | b=54, h=15               |     |     | Rahmen 0.6pt |
| Label „Via:"         | statisch                 | 88  | 31  | Regular 10|
| Box + Via-Text       | `card.via_text`          | 88  | 35  | Regular 11|
|  Box-Maße            | b=54, h=12               |     |     |           |

### Stationsblock (Absender-Stationsdaten, aus Config)
Als Label/Wert-Spalte **neben** der Adresse, auf Höhe der Adresszeilen
(yt = 18 / 23.5 / 29 / 34.5), Regular 9:
Label-Spalte `x=50`, Wert-Spalte `x=64`; Zeilen `Locator:` / `DOK:` / `WAZ:` / `ITU:`.

### Bestätigungs-Checkboxen
| Element                    | x  | yt | Font/Size |
|----------------------------|----|----|-----------|
| ☐ Confirming QSO           | 6  | 45 | Regular 8 |
| ☐ Confirming SWL-Report    | 48 | 45 | Regular 8 |

### QSO-Tabelle
- Bounding-Box: `x=6 … 142` (Breite 136), oben `yt=50`, unten `yt=67`.
- **Kopfzeile** Höhe `HEAD_H = 8`. **Datenzeilen**: `MAX_ROWS = 1`, je
  `ROW_H = ((67-50)-HEAD_H)/MAX_ROWS = 9`. (Genau **ein** QSO pro Karte; im Modus
  „pro Station" werden Mehrfach-QSOs auf mehrere Einzelkarten aufgeteilt.)
- Spalten (Breiten in mm, Summe = 136):
  | Spalte            | Breite | Unterspalten                    |
  |-------------------|--------|---------------------------------|
  | DATE              | 30     | D=10, M=10, Y=10                |
  | UNIVERSAL TIME UTC| 24     | –                               |
  | FREQUENCY MHZ     | 26     | –                               |
  | 2-WAY QSO IN      | 26     | –                               |
  | SIGNAL REPORT     | 30     | R=10, S=10, T=10               |
- Kopftexte (zentriert, Bold 6.5, ggf. zweizeilig):
  `DATE` über `D  M  Y`; `UNIVERSAL TIME (UTC)`; `FREQUENCY MHZ`;
  `2-WAY QSO IN`; `SIGNAL REPORT` über `R  S  T`.
- **Datenzeile je `CardRow`** (zentriert, Regular 8):
  - DATE: `date_d` | `date_m` | `date_y` in die drei Unterspalten.
  - UTC: `utc` (z.B. „14:32").
  - FREQ: `freq_mhz` (z.B. „14.074").
  - 2-WAY QSO IN: `mode` (z.B. „SSB").
  - SIGNAL REPORT: `rst_sent` zerlegt in R/S/T (Ziffern einzeln in die
    Unterspalten; bei 2-stelligem Rapport T leer lassen).
- Alle Zell-/Unterspalten-Trennlinien zeichnen (Rahmen 0.6pt).

### Fuß
REMARKS-Box über die volle Breite und flach; Footer-Text und PSE/TNX **darunter**.
| Element              | Inhalt / Quelle                 | x   | yt | Font/Size |
|----------------------|---------------------------------|-----|----|-----------|
| Label „REMARKS"      | statisch                        | 6   | 71 | Regular 8 |
| REMARKS-Box          | leer (b=136, h=14)              | 6   | 74 | Rahmen 0.6pt |
| Footer-Text          | `generation.static_footer`      | 6   | 92 | Bold 8    |
| ☐ PSE QSL            | checked, wenn `qsl_mark=="pse"` | 62  | 91 | Regular 8 |
| ☐ TNX QSL            | checked, wenn `qsl_mark=="tnx"` | 92  | 91 | Regular 8 |

---

## 4. Checkbox- & Hilfsfunktionen (in `layout_back.py`)

- `checkbox(c, x, yt, label, checked=False, size=8)`: kleines Quadrat
  (Seite ≈ 3mm) + Text rechts daneben. `checked=True` zeichnet ein X/gefülltes
  Kreuz im Kästchen (für die gewählte PSE/TNX-Markierung), sonst leer.
- Text-Helfer `text(c, x, yt, s, font, size, align="left")` mit interner
  `y_pdf = PAGE_H - mm(yt)`-Umrechnung, damit im Zeichencode nur „von-oben"-mm
  benutzt werden.

---

## 5. Vorgehen zum exakten Nachbau

1. Alle Werte aus §3 als benannte Konstanten in `geometry.py` anlegen.
2. `layout_back.py` implementieren, das ausschließlich diese Konstanten nutzt.
3. Eine Testkarte mit Beispieldaten rendern.
4. Neben die Referenz (`WhatsApp_Image…jpeg`, um 90° gedreht) legen und
   vergleichen: Positionen/Größen in `geometry.py` nachziehen. **Nur dort**
   ändern, nicht im Zeichencode.
5. Wiederholen, bis das Layout passt. Danach mit echten ADIF-Daten testen
   (mehrere Zeilen bei „pro Station").

> Hinweis: Das Frontbild stellt der Nutzer bereit. Der Bereich unten rechts
> (in der Referenz das Logo) bleibt frei; er kann später anderweitig genutzt werden.
