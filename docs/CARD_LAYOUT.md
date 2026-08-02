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
│  │ ┌──┬──┬──┬──────────┬──────────┬────────────┬─────────────┐│
│  │ │D │M │Y │ UTC TIME │ FREQ MHZ │2-WAY QSO IN│SIGNAL REPORT││
│  │ ├──┼──┼──┼──────────┼──────────┼────────────┼─────────────┤│
│  │ │  │  │  │          │          │            │ <rst / dB>  ││
│  │ └──┴──┴──┴──────────┴──────────┴────────────┴─────────────┘│
│  │ REMARKS                                                   │
│  │ ┌────────────────────────────────────────────────────────┐│
│  │ └────────────────────────────────────────────────────────┘│
│  │ TNX FR NICE CONTACT, 73        ☐ PSE QSL   ☐ TNX QSL       │
│  └──────────────────────────────────────────────────────────┘
▼ yt
```

Gegenüber der Original-DARC-Karte bewusst geändert: kein „Responsive"-Untertitel,
`/p`/`/m` oben zwischen eigenem Call und dem „To Amateur…"-Block, Stationsdaten
(Locator/DOK/WAZ/ITU) als Spalte neben der Adresse, eine **dynamisch hohe**
Datentabelle (ohne Remarks bis `MAX_ROWS_PLAIN = 6` Zeilen, mit Remarks bis
`MAX_ROWS_WITH_REMARKS = 3`) und ein **dynamischer** REMARKS-Block, der nur
erscheint, wenn die Karte einen Remarks-Text hat (Footer darunter, kein
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
| ☐ Confirming QSO           | 6  | 44 | Regular 8 |
| ☐ Confirming SWL-Report    | 48 | 44 | Regular 8 |

(yt=44 -> Kästchen-Unterkante bündig mit der Via-Box-Unterkante.)

### QSO-Tabelle
- Bounding-Box: `x=6 … 142` (Breite 136), oben `yt=50`; die Unterkante ist
  **dynamisch** (`TABLE_YT_TOP + HEAD_H + n·ROW_H`). Ohne Remarks endet sie bei
  voller Belegung (6 Zeilen) bei `yt=92` (`TABLE_YT_BOTTOM`, oberhalb des Footers);
  mit Remarks bei voller Belegung (3 Zeilen) bei `yt=74`
  (`TABLE_YT_BOTTOM_WITH_REMARKS`, oberhalb des REMARKS-Blocks).
- **Kopfzeile einzeilig**, so hoch wie eine Datenzeile (`HEAD_H = ROW_H = 6`).
  **Datenzeilen**: feste Höhe `ROW_H = 6`. Die Tabelle wird **dynamisch** gezeichnet
  — genau so viele Zeilen, wie die Karte QSOs hat. Die Maximalzahl hängt vom
  Remarks-Zustand ab: **ohne** Remarks bis `MAX_ROWS_PLAIN = 6`, **mit** Remarks
  bis `MAX_ROWS_WITH_REMARKS = 3` (der Remarks-Kasten braucht darunter Platz).
  Im Modus „pro Station" landen so viele QSOs derselben Station auf einer Karte,
  wie erlaubt; mehr → Folge-Karte(n). Remarks sind **je Karte** unabhängig.
- Spalten (Breiten in mm, Summe = 136):
  | Spalte            | Breite | Unterspalten                    |
  |-------------------|--------|---------------------------------|
  | D M Y (Datum)     | 30     | D=10, M=10, Y=10                |
  | UTC TIME          | 24     | –                               |
  | FREQ MHZ          | 26     | –                               |
  | 2-WAY QSO IN      | 26     | –                               |
  | SIGNAL REPORT     | 30     | – (ein Wert je Zeile)           |
- Kopftexte (zentriert, Bold 6.5, **einzeilig**): DATE-Spalte nur `D  M  Y`
  (kein DATE-Titel mehr, die D/M/Y-Trenner laufen durch die volle Höhe);
  `UTC TIME`; `FREQ MHZ`; `2-WAY QSO IN`; `SIGNAL REPORT`.
- **Datenzeile je `CardRow`** (zentriert, Regular 8):
  - DATE: `date_d` | `date_m` | `date_y` in die drei Unterspalten.
  - UTC: `utc` (z.B. „14:32").
  - FREQ: `freq_mhz` (z.B. „14.074").
  - 2-WAY QSO IN: `mode` (z.B. „SSB").
  - SIGNAL REPORT: `rst_sent` als **ein** Wert (keine R/S/T-Aufteilung mehr, keine
    Unterlabels). So passt jede Betriebsart: RST wie im Log für Phone/CW
    (`59`/`599`), dB für Digimodes wie FT8 (`-06`, `+14`); leerer Report bleibt leer.
- Alle Zell-/Unterspalten-Trennlinien zeichnen (Rahmen 0.6pt); die SIGNAL-REPORT-
  Spalte hat keine Unterspalten mehr.

### Fuß
REMARKS-Block über die volle Breite und flach; Footer-Text und PSE/TNX
**darunter**. Der REMARKS-Block wird **dynamisch** gezeichnet: nur wenn die Karte
einen Remarks-Text (`card.remarks`) hat — sonst bleibt der Platz frei (und die
Tabelle darf mehr Zeilen nutzen, siehe QSO-Tabelle). Der Block sitzt an fester
Position knapp über dem Footer (~3 mm Abstand zum Rahmen); Abstand Label→Box wie
„Via:"→Via-Box (4 mm). Der Footer-Text steht **immer** (unabhängig von Remarks).
| Element              | Inhalt / Quelle                    | x   | yt | Font/Size |
|----------------------|------------------------------------|-----|----|-----------|
| Label „REMARKS"      | statisch (nur wenn Remarks)        | 6   | 79 | Regular 10 |
| REMARKS-Box          | `card.remarks` (b=136, h=10)       | 6   | 83 | Rahmen 0.6pt |
| REMARKS-Text         | `card.remarks`, links, mittig-vert.| 8   | –  | Regular 9 |
| Footer-Text          | `generation.static_footer`         | 6   | 96 | Bold 8    |
| ☐ PSE QSL            | checked, wenn `qsl_mark=="pse"`    | 62  | 96 | Regular 8 |
| ☐ TNX QSL            | checked, wenn `qsl_mark=="tnx"`    | 92  | 96 | Regular 8 |

Der Remarks-Text ist auf **80 Zeichen** begrenzt (passt in eine Zeile der Box);
die Begrenzung sitzt in den Eingabefeldern der GUI (global + je Karte).

---

## 4. Checkbox- & Hilfsfunktionen (in `layout_back.py`)

- `checkbox(c, x, yt, label, checked=False, size=8)`: kleines Quadrat
  (Seite ≈ 3mm) + Text rechts daneben. `checked=True` zeichnet ein Kreuz, das
  über das Kästchen hinausragt (`CHECKBOX_CROSS_OVERHANG`), sonst leer.
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
