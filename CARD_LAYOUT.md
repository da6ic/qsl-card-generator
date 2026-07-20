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
- Außenrand (Inhalt): `MARGIN = 5 mm` ringsum.
- Standard-Linienstärke Rahmen: `0.6 pt`. Schrift-Default: Helvetica.
  Für Umlaute optional DejaVuSans registrieren (siehe SPECIFICATION §8).

`geometry.py` stellt bereit:
```python
MM = 72 / 25.4                      # Punkte pro mm
def mm(v): return v * MM
PAGE_W, PAGE_H = mm(148), mm(105)   # Querformat A6
MARGIN = mm(5)
```

---

## 2. Zonen-Übersicht (Skizze, nicht maßstабsgetreu)

```
(0,0) oben-links ───────────────────────────────────────────────► x
│  ┌──────────────────────────────────────────────────────────┐
│  │ DN5MT                    To Amateur Radio Station:        │
│  │ Responsive               ┌────────────────────────────┐   │
│  │                          │ <CALL>                     │   │
│  │ Axel Tüner               └────────────────────────────┘   │
│  │ Wilhelmstr. 76           Via: ┌───────────────────────┐   │
│  │ 72124 Pliezhausen             │ <VIA_TEXT>            │   │
│  │ Deutschland                   └───────────────────────┘   │
│  │                          ☐ /p    ☐ /m                     │
│  │ Locator: JN48OM  DOK: P31   WAZ: 14   ITU: 28             │
│  │ ☐ Confirming QSO        ☐ Confirming SWL-Report           │
│  │ ┌──────┬───────┬─────────┬──────────┬──────────────┐      │
│  │ │ DATE │UNIV.  │FREQUENCY│ 2-WAY    │SIGNAL REPORT │      │
│  │ │D M Y │TIME UTC│  MHZ   │ QSO  IN  │  R   S   T   │      │
│  │ ├──┬─┬─┼───────┼─────────┼──────────┼───┬───┬──────┤      │
│  │ │  │ │ │       │         │          │   │   │      │ row1 │
│  │ ├──┼─┼─┼───────┼─────────┼──────────┼───┼───┼──────┤      │
│  │ │  │ │ │       │         │          │   │   │      │ row2 │
│  │ ├──┼─┼─┼───────┼─────────┼──────────┼───┼───┼──────┤      │
│  │ │  │ │ │       │         │          │   │   │      │ row3 │
│  │ └──┴─┴─┴───────┴─────────┴──────────┴───┴───┴──────┘      │
│  │ REMARKS                                                   │
│  │ ┌───────────────┐                                         │
│  │ │               │                                         │
│  │ └───────────────┘                                         │
│  │ TNX FR NICE CONTACT, 73  ☐ PSE QSL  ☐ TNX QSL            │
│  └──────────────────────────────────────────────────────────┘
▼ yt
```

---

## 3. Elemente (Inhalt, Quelle, Schrift, Startposition)

Positionen `x / yt` in mm, gemessen vom oberen linken Inhaltsrand. `size` in pt.
Linksbündig, sofern nicht anders angegeben.

### Kopf links
| Element        | Inhalt / Quelle            | x   | yt  | Font/Size            |
|----------------|----------------------------|-----|-----|----------------------|
| Rufzeichen     | `sender.callsign`          | 6   | 6   | Helvetica-Bold 22    |
| Untertitel     | `sender.subtitle`          | 6   | 16  | Helvetica 7          |
| Adresse Z1     | `sender.name`              | 6   | 24  | Helvetica 9          |
| Adresse Z2     | `sender.street`            | 6   | 29  | Helvetica 9          |
| Adresse Z3     | `sender.zip` + " " + `city`| 6   | 34  | Helvetica 9          |
| Adresse Z4     | `sender.country`           | 6   | 39  | Helvetica 9          |

### Kopf rechts (Empfänger + Via)
| Element              | Inhalt / Quelle          | x   | yt  | Font/Size        |
|----------------------|--------------------------|-----|-----|------------------|
| Label „To Amateur…"  | statisch                 | 78  | 6   | Helvetica 8      |
| Box + Call           | `card.recipient_call`    | 78  | 10  | Helvetica-Bold 12|
|  Box-Maße            | b=62, h=9                |     |     | Rahmen 0.6pt     |
| Label „Via:"         | statisch                 | 78  | 22  | Helvetica 8      |
| Box + Via-Text       | `card.via_text`          | 88  | 21  | Helvetica 9      |
|  Box-Maße            | b=52, h=8                |     |     |                  |
| ☐ /p                 | checked, wenn `portable_mark=="p"` | 78 | 33 | Helvetica 8   |
| ☐ /m                 | checked, wenn `portable_mark=="m"` | 90 | 33 | Helvetica 8   |

### Stationsblock (Absender-Stationsdaten, aus Config)
Eine Zeile, vier Paare, linksbündig ab x=6, yt=45:
`Locator: {locator}   DOK: {dok}   WAZ: {waz}   ITU: {itu}` — Helvetica 8.
(Optional als rechte Spalte anordnen, falls die Referenz das so zeigt — beim
Feinschliff am Bild ausrichten.)

### Bestätigungs-Checkboxen
| Element                    | x  | yt | Font/Size   |
|----------------------------|----|----|-------------|
| ☐ Confirming QSO           | 6  | 51 | Helvetica 8 |
| ☐ Confirming SWL-Report    | 60 | 51 | Helvetica 8 |

### QSO-Tabelle
- Bounding-Box: `x=6 … 142` (Breite 136), oben `yt=56`, unten `yt=84`.
- **Kopfzeile** Höhe `HEAD_H = 8`. **Datenzeilen**: `MAX_ROWS = 3`, je
  `ROW_H = ((84-56)-HEAD_H)/MAX_ROWS` ≈ 6.7.
- Spalten (Breiten in mm, Summe = 136):
  | Spalte            | Breite | Unterspalten                    |
  |-------------------|--------|---------------------------------|
  | DATE              | 30     | D=10, M=10, Y=10                |
  | UNIVERSAL TIME UTC| 24     | –                               |
  | FREQUENCY MHZ     | 26     | –                               |
  | 2-WAY QSO IN      | 26     | –                               |
  | SIGNAL REPORT     | 30     | R=10, S=10, T=10               |
- Kopftexte (zentriert, Helvetica-Bold 6.5, ggf. zweizeilig):
  `DATE` über `D  M  Y`; `UNIVERSAL TIME (UTC)`; `FREQUENCY MHZ`;
  `2-WAY QSO IN`; `SIGNAL REPORT` über `R  S  T`.
- **Datenzeile je `CardRow`** (zentriert, Helvetica 8):
  - DATE: `date_d` | `date_m` | `date_y` in die drei Unterspalten.
  - UTC: `utc` (z.B. „14:32").
  - FREQ: `freq_mhz` (z.B. „14.074").
  - 2-WAY QSO IN: `mode` (z.B. „SSB").
  - SIGNAL REPORT: `rst_sent` zerlegt in R/S/T (Ziffern einzeln in die
    Unterspalten; bei 2-stelligem Rapport T leer lassen).
- Alle Zell-/Unterspalten-Trennlinien zeichnen (Rahmen 0.6pt).

### Fuß
| Element              | Inhalt / Quelle                 | x   | yt | Font/Size    |
|----------------------|---------------------------------|-----|----|--------------|
| Label „REMARKS"      | statisch                        | 6   | 86 | Helvetica 8  |
| REMARKS-Box          | leer (b=48, h=13)               | 6   | 89 | Rahmen 0.6pt |
| Footer-Text          | `generation.static_footer`      | 6   | 99 | Helvetica-Bold 8 |
| ☐ PSE QSL            | checked, wenn `qsl_mark=="pse"` | 70  | 99 | Helvetica 8  |
| ☐ TNX QSL            | checked, wenn `qsl_mark=="tnx"` | 92  | 99 | Helvetica 8  |

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
