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

### Druckrand (elastischer Rahmen)

Alle folgenden Maße beschreiben die Karte auf der **vollen** A6-Fläche. Ist der
Druckrand aktiv (`generation.print_margin_*`, GUI-Abschnitt 9), wird die Karte
in einen kleineren Rahmen gesetzt — das Blatt bleibt A6, nur die Zeichnung rückt
ein. `geometry.page_layout(config)` liefert dafür einen `PageLayout`:

- `dx`/`dy`/`scale` gehören aufs Canvas (`translate` + **gleichmäßiges** `scale`,
  daher nie verzerrt); `draw_back` klammert damit sein gesamtes Zeichnen.
- Gezeichnet wird danach im System einer **virtuellen Seite** `page_w × page_h`,
  die auf einer Achse größer als A6 ist (der Überschuss, der sonst als Leerraum
  verfiele). Die Y-Spiegelung lautet deshalb `y_pdf = page_h - yt`, nicht
  `PAGE_H - yt` — alle Helfer bekommen den `PageLayout` übergeben.
- Mit der virtuellen Breite wachsen: `call_box_w`, `via_box_w`, `table_x1`,
  `table_width`, `column_widths` (anteilig), `sub_date_w`, `remarks_box_w`.
- Mit der virtuellen Höhe wandern nach unten: `remarks_label_yt`,
  `remarks_box_yt`, `footer_text_yt` — der Fußblock hängt an der **Unterkante**
  (6,5 mm über ihr), nicht an einem festen Abstand von oben.
- Alles andere (Absender-, Stations-, Funk-Block, QSO-Tabelle oben links) ist
  links/oben verankert und bleibt unverändert stehen.
- `MAX_ROWS_*` ändert sich **nicht**: senkrechter Überschuss vergrößert nur den
  Abstand zwischen Tabelle und Fuß.

Ohne Druckrand ist der `PageLayout` die Identität (`scale = 1`, virtuelle Seite
= A6, alle Maße = die Konstanten unten) — die Ausgabe ist dann byteweise
dieselbe wie vor dem Feature.

### Textbreiten (Einpassen statt Überlaufen)

Die Karte kennt **keinen Zeilenumbruch**. Jeder freie Text — Name, Straße,
Rufzeichen samt Präfix/Kennung, Antennenbezeichnung, Betriebsart, Remarks — hat
deshalb eine **Höchstbreite**; passt er nicht, wird er **proportional kleiner
gesetzt und nie abgeschnitten** (mit dem Nutzer so entschieden: lieber klein als
unvollständig). Ohne diese Regel lief zu langer Text schlicht über den Nachbarn.

- Gerechnet wird in `layout_back.fit_size(s, font, size, max_w)`:
  `size · max_w / stringWidth(s, font, size)`, nach unten nur durch
  `MIN_FONT_SIZE` begrenzt (technischer Boden, kein gestalterisches Minimum).
- Übergeben wird die Grenze als `max_w=` an `text(...)` bzw. `_text_in_band(...)`.
  Die Oberkante bleibt dabei bei `yt`, weil die Grundlinie aus der **verkleinerten**
  Größe berechnet wird.
- **Passt der Text — der Normalfall —, ändert sich nichts.** Die Ausgabe einer
  gewöhnlichen Karte ist byteweise dieselbe wie vor der Regel.

Die Grenzen stehen als Konstanten in `geometry.py` und sind **Abstände zum
nächsten Block**, keine neuen Positionen — verschiebt man eine Spalte, wandert
die Grenze mit:

| Konstante | gilt für | Grenze |
|---|---|---|
| `SENDER_TEXT_W` | Adresszeilen Z1–Z4 | bis zum Stationsblock (`STATION_LABEL_X`) |
| `SENDER_CALLSIGN_W` | eigenes Rufzeichen **mit** Bestätigungs-Markierung | bis zu deren Band |
| `SENDER_CALLSIGN_W_PLAIN` | eigenes Rufzeichen **ohne** Markierung | bis zum „To Amateur…"-Label |
| `CONFIRM_MARK_W` | Bestätigungs-Markierung | symmetrisch um `CONFIRM_MARK_X`, rechts bis `TO_LABEL_X` |
| `STATION_VALUE_W` | Locator/DOK/CQ-Zone/ITU | bis zur Empfängerspalte |
| `BOX_TEXT_PAD` | Call-/Via-Box, Funk- und QSO-Tabellenzellen | Innenabstand je Seite |
| `REMARKS_TEXT_PAD` | REMARKS-Text | Innenabstand der Box |
| `TEXT_GAP` | Luft zwischen zwei Textblöcken | (Basis der obigen Werte) |

Zwei Feinheiten:

- **Das Rufzeichen bekommt mehr Platz, wenn keine Bestätigungs-Markierung
  gedruckt wird** (83,5 statt 39,5 mm). Sonst würde `F/DL0MT/P` verkleinert,
  obwohl der Platz daneben frei ist.
- **`Confirming SWL-Report` passt bei Bold 11 grundsätzlich nicht** (51,5 mm auf
  42 mm Band) und wird immer leicht verkleinert. Das ist der Fall, der die Regel
  überhaupt nötig gemacht hat: er überlappte vorher das „To Amateur Radio
  Station:"-Label, **ohne** dass der Anwender etwas Ungewöhnliches eingetragen
  hätte.
- Was beim Druckrand mitwächst (Call-/Via-Box, Tabellenspalten, Remarks-Kasten),
  kommt **nicht** aus diesen Konstanten, sondern aus dem `PageLayout`.

### Bogendruck (vier Karten auf A4)

Ist `generation.sheet_mode == "a4_4up"`, liegen vier Karten auf einem A4-Bogen
(quer). Am Kartenlayout ändert das **nichts** — es wechselt nur, was „die Seite"
ist:

- Der Bogen wird lückenlos in vier Zellen à **148,5 × 105 mm** geteilt (ein
  Viertel von A4 = das echte ISO-A6-Maß). Das Raster hängt an keiner Einstellung,
  die Schnittkanten liegen immer auf der Blattmitte.
- Eine **Zelle** tritt an die Stelle der A6-Seite: `content_box` liefert die Zelle
  minus Druckrand, `page_layout` passt die Karte wie gewohnt hinein (ein Faktor,
  nie verzerrt, Überschuss ins Layout). `pdf/layout_sheet.py` **verschiebt** das
  Canvas nur auf den Zellen-Ursprung.
- Weil die Zelle 0,5 mm breiter als `PAGE_W` ist, wächst die virtuelle Seite auch
  ohne Druckrand minimal — derselbe elastische Mechanismus wie oben.
- Der **Druckrand gilt je Karte**: zwischen zwei Karten steht der doppelte Rand,
  dessen Mitte die Schnittkante ist. Jede geschnittene Karte hat ihn damit auf
  allen vier Seiten (läge er nur um den Bogen, säße der Inhalt außermittig).
- Zwischen den Karten läuft ein **gestricheltes Schnittkreuz** über den ganzen
  bedruckbaren Bereich — nur auf den **Rückseitenbogen**, damit über dem
  randlosen Frontbild kein Strich stehen bleibt.

---

## 2. Zonen-Übersicht (Skizze, nicht maßstабsgetreu)

```
(0,0) oben-links ───────────────────────────────────────────────► x
│  ┌──────────────────────────────────────────────────────────┐
│  │ F/DL0MT/P     Confirming QSO   To Amateur Radio Station:  │
│  │                                ┌────────────────────────┐ │
│  │ Axel Tüner     Locator: JN48OM │ <CALL>                 │ │
│  │ Wilhelmstr.76  DOK:     P31    └────────────────────────┘ │
│  │ 72124 Ort      CQ-Zone: 14     Via:                       │
│  │ Deutschland    ITU:     28     ┌────────────────────────┐ │
│  │ ┌────┬────┬────┐               │ <VIA_TEXT>             │ │
│  │ │RIG │ANT │PWR │  (dynamisch)                             │
│  │ │… │… │… │                                                │
│  │ PSE QSL   └────┴────┴────┘                                │
│  │ ┌──┬──┬──┬──────────┬──────────┬────────────┬─────────────┐│
│  │ │D │M │Y │ UTC TIME │ FREQ MHZ │2-WAY QSO IN│SIGNAL REPORT││
│  │ ├──┼──┼──┼──────────┼──────────┼────────────┼─────────────┤│
│  │ │  │  │  │          │          │            │ <rst / dB>  ││
│  │ └──┴──┴──┴──────────┴──────────┴────────────┴─────────────┘│
│  │ REMARKS                                                   │
│  │ ┌────────────────────────────────────────────────────────┐│
│  │ └────────────────────────────────────────────────────────┘│
│  │ TNX FR NICE CONTACT, 73                                   │
│  └──────────────────────────────────────────────────────────┘
▼ yt
```

Gegenüber der Original-DARC-Karte bewusst geändert:
- kein „Responsive"-Untertitel;
- eine **Portabel-Kennung** steht im Rufzeichen selbst (`F/DL0MT/P`), nicht als
  separate Kästchen — siehe unten;
- die **Bestätigungs-Markierung** (`Confirming QSO`/`Confirming SWL-Report`) steht
  oben mittig — nur der gewählte Text, kein Kästchen;
- die **QSL-Markierung** (`PSE QSL`/`TNX QSL`) steht links unter dem Stationsblock
  als Text (kein Kästchen, kein Fuß-Feld mehr);
- Stationsdaten (Locator/DOK/CQ-Zone/ITU) als Spalte neben der Adresse;
- ein **dynamischer Funk-Block** (RIG/ANT/PWR-Tabelle), der nur erscheint, wenn
  mind. eins der Felder gefüllt ist; dann rücken QSL-Markierung und Tabelle nach
  unten;
- eine **dynamisch hohe** Datentabelle (ohne Remarks bis `MAX_ROWS_PLAIN = 6`
  Zeilen, mit Remarks bis `MAX_ROWS_WITH_REMARKS = 3`);
- ein **dynamischer** REMARKS-Block, der nur erscheint, wenn die Karte einen
  Remarks-Text hat (Footer darunter, kein TRAINEE-Feld).

---

## 3. Elemente (Inhalt, Quelle, Schrift, Startposition)

Positionen `x / yt` in mm, gemessen von der oberen linken Blattecke. `size` in pt.
Schrift = DejaVuSans (regular/bold). Linksbündig, sofern nicht anders angegeben.

### Kopf links
| Element        | Inhalt / Quelle            | x   | yt   | Font/Size   |
|----------------|----------------------------|-----|------|-------------|
| Rufzeichen     | `sender.callsign`          | 3   | 3    | Bold 22     |
| Adresse Z1     | `sender.name`              | 3   | 15.5 | Regular 9   |
| Adresse Z2     | `sender.street`            | 3   | 21.5 | Regular 9   |
| Adresse Z3     | `sender.zip` + " " + `city`| 3   | 27.5 | Regular 9   |
| Adresse Z4     | `sender.country`           | 3   | 33.5 | Regular 9   |

Kein „Untertitel"/„Responsive" mehr (Feld `subtitle` entfernt).

Alle vier Adresszeilen enden spätestens am Stationsblock (`SENDER_TEXT_W`);
längere Werte werden verkleinert, nicht abgeschnitten (siehe §1 „Textbreiten").

### Eigenes Rufzeichen (Schreibweise)
`sender.callsign` wird **großgeschrieben** und sonst unverändert gezeichnet — mit
allem, was zum Rufzeichen gehört: Landespräfix (`F/DL0MT`), Portabel-Kennung
(`F/DL0MT/P`), `/QRP`, `/MM`, Rufbezirk (`W1AW/4`). Es gibt **kein** eigenes Feld
und keine eigene Position dafür (siehe `_draw_sender`); ein Dropdown
`portable_mark` gab es und wurde entfernt, weil es Präfixe, `/MM` und Rufbezirke
von den vier eigenen Kennungen unterscheiden musste, ohne etwas zu gewinnen.

### Bestätigungs-Markierung (oben mittig)
Nur der **gewählte** Text (kein Kästchen), an fester, zentrierter Position.
| Element                | Inhalt / Quelle                          | x  | yt | Font/Size |
|------------------------|------------------------------------------|----|----|-----------|
| Confirming QSO         | Text, wenn `confirm_mark=="qso"`         | 65.5 | 5  | Bold 11   |
| Confirming SWL-Report  | Text, wenn `confirm_mark=="swl"`         | 65.5 | 5  | Bold 11   |

Das Band ist `CONFIRM_MARK_W` breit (symmetrisch um `CONFIRM_MARK_X`, rechts bis
zum „To Amateur…"-Label). `Confirming SWL-Report` ist bei Bold 11 breiter und
wird deshalb **immer** etwas verkleinert — vorher überlappte er das Label (§1
„Textbreiten").

### Kopf rechts (Empfänger + Via)
| Element              | Inhalt / Quelle          | x   | yt  | Font/Size |
|----------------------|--------------------------|-----|-----|-----------|
| Label „To Amateur…"  | statisch                 | 88.5| 5   | Regular 10|
| Box + Call           | `card.recipient_call`    | 88.5| 9.5 | Bold 16   |
|  Box-Maße            | b=56.5, h=15           |     |     | Rahmen 0.6pt |
| Label „Via:"         | statisch                 | 88.5| 29.5| Regular 10|
| Box + Via-Text       | `card.via_text`          | 88.5| 34   | Regular 11|
|  Box-Maße            | b=56.5, h=12           |     |     |           |

### Stationsblock (Absender-Stationsdaten, aus Config)
Als Label/Wert-Spalte **neben** der Adresse, auf Höhe der Adresszeilen
(yt = 15.5 / 21.5 / 27.5 / 33.5), Regular 9:
Label-Spalte `x=49` (`STATION_LABEL_X`), Wert-Spalte `x=67.5` (`STATION_VALUE_X`);
Zeilen `Locator:` / `DOK:` / `CQ-Zone:` (Wert = `sender.waz`) / `ITU:`.

### Funk-Block (RIG/ANT/PWR) — dynamisch, nur wenn gefüllt
Kleine beschriftete Tabelle **direkt unter dem Stationsblock**, linksbündig, die
Breite links der Via-Box ausschöpfend (`x=3 … RADIO_TABLE_X1=85.5`, oben
`RADIO_TABLE_YT_TOP=37.5`, unten bündig zur Via-Box `=46`). Kopfzeile (Bold 6)
`RIG`/`ANT`/`PWR`, Werte darunter (Regular 8). Nur **befüllte** Felder
(`sender.receiver`/`antenna`/`power`) bekommen eine Spalte; die vorhandenen Spalten
teilen sich die Breite gleichmäßig. Ist der Block sichtbar, rücken QSL-Markierung
und QSO-Tabelle nach unten (`QSL_MARK_YT_RADIO` / `TABLE_YT_TOP_RADIO`).

### QSL-Markierung (PSE/TNX QSL)
Links unter dem Stationsblock, nur der **gewählte** Text (kein Kästchen). `yt=43.5`
(`QSL_MARK_YT`); ist der Funk-Block sichtbar, rutscht sie auf `yt=47.5`
(`QSL_MARK_YT_RADIO`, unter die Funk-Tabelle).
| Element   | Inhalt / Quelle              | x | yt   | Font/Size |
|-----------|------------------------------|---|------|-----------|
| PSE QSL   | Text, wenn `qsl_mark=="pse"` | 3 | 43.5 | Bold 11   |
| TNX QSL   | Text, wenn `qsl_mark=="tnx"` | 3 | 43.5 | Bold 11   |

### QSO-Tabelle
- Bounding-Box: `x=3 … 145` (Breite 142), oben `yt=49.5`; die Unterkante ist
  **dynamisch** (`TABLE_YT_TOP + HEAD_H + n·ROW_H`). Ohne Remarks endet sie bei
  voller Belegung (6 Zeilen) bei `yt=91.5` (`TABLE_YT_BOTTOM`, oberhalb des
  Footers); mit Remarks bei voller Belegung (3 Zeilen) bei `yt=73.5`
  (`TABLE_YT_BOTTOM_WITH_REMARKS`, oberhalb des REMARKS-Blocks).
  Ist der Funk-Block sichtbar, beginnt sie bei `yt=51.5` (`TABLE_YT_TOP_RADIO`).
- **Kopfzeile einzeilig**, so hoch wie eine Datenzeile (`HEAD_H = ROW_H = 6`).
  **Datenzeilen**: feste Höhe `ROW_H = 6`. Die Tabelle wird **dynamisch** gezeichnet
  — genau so viele Zeilen, wie die Karte QSOs hat. Die Maximalzahl hängt vom
  Remarks-Zustand ab: **ohne** Remarks bis `MAX_ROWS_PLAIN = 6`, **mit** Remarks
  bis `MAX_ROWS_WITH_REMARKS = 3` (der Remarks-Kasten braucht darunter Platz).
  Im Modus „pro Station" landen so viele QSOs derselben Station auf einer Karte,
  wie erlaubt; mehr → Folge-Karte(n). Remarks sind **je Karte** unabhängig.
- Spalten (Breiten in mm, Summe = 142):
  | Spalte            | Breite | Unterspalten                    |
  |-------------------|--------|---------------------------------|
  | D M Y (Datum)     | 31.5   | je 10.5 für D, M und Y          |
  | UTC TIME          | 25     | –                               |
  | FREQ MHZ          | 27.5   | –                               |
  | 2-WAY QSO IN      | 27.5   | –                               |
  | SIGNAL REPORT     | 30.5   | – (ein Wert je Zeile)           |
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
REMARKS-Block über die volle Breite und flach; Footer-Text **darunter**. Der
REMARKS-Block wird **dynamisch** gezeichnet: nur wenn die Karte einen Remarks-Text
(`card.remarks`) hat — sonst bleibt der Platz frei (und die Tabelle darf mehr
Zeilen nutzen, siehe QSO-Tabelle). Der Block sitzt an fester Position knapp über
dem Footer (~3 mm Abstand zum Rahmen); Abstand Label→Box wie „Via:"→Via-Box
(4 mm). Der Footer-Text steht **immer** (unabhängig von Remarks). Die
PSE/TNX-QSL-Markierung steht **nicht** mehr im Fuß, sondern oben links (siehe
„QSL-Markierung").
| Element              | Inhalt / Quelle                    | x   | yt | Font/Size |
|----------------------|------------------------------------|-----|----|-----------|
| Label „REMARKS"      | statisch (nur wenn Remarks)        | 3   | 80.5 | Regular 10 |
| REMARKS-Box          | `card.remarks` (b=142, h=10)      | 3   | 84.5 | Rahmen 0.6pt |
| REMARKS-Text         | `card.remarks`, links, mittig-vert.| 5   | –  | Regular 9 |
| Footer-Text          | `generation.static_footer`         | 3   | 98.5 | Bold 8    |

Der Remarks-Text ist auf **80 Zeichen** begrenzt; die Begrenzung sitzt in den
Eingabefeldern der GUI (global + je Karte). Eine Zeile fasst 80 Zeichen nur bei
gewöhnlichem Text — 80 *breite* Zeichen wären 219 mm bei 138 mm Platz. Solche
Texte werden verkleinert (§1 „Textbreiten"), die Zeichenzahl bleibt bei 80.

### DARC-QR-Code (optional, `generation.qr_code`)
Rechts unten, rechtsbündig mit der Tabelle (x = 125 … 145), `yt` = 76.5 … 96.5,
20 × 20 mm. Mit QR hat die Tabelle höchstens 3 Zeilen (wie mit Remarks);
REMARKS-Kasten und Footer-Text enden 3 mm vor dem Code (Breite 119 statt 142).

---

## 4. Hilfsfunktionen (in `layout_back.py`)

Es gibt **keine** Checkbox-Funktion mehr: alle Markierungen (Bestätigung,
PSE/TNX QSL) werden als reiner **Text** gezeichnet (die Karte wird ohnehin gezielt
für die gewählte Aussage gedruckt).
Alle Helfer bekommen als zweites Argument den `PageLayout` der Seite (`page`,
siehe §1 „Druckrand"); er liefert die Seitenhöhe für die Y-Spiegelung. Ohne
Druckrand ist `page.page_h == PAGE_H`.
- `fit_size(s, font, size, max_w)`: Schriftgröße, bei der `s` in `max_w` passt —
  **nur verkleinern, nie kürzen** (§1 „Textbreiten"). `max_w=None` schaltet die
  Begrenzung ab (Texte ohne Nachbarn).
- Text-Helfer `text(c, page, x, yt, s, font, size, align="left", max_w=None)` mit
  interner `y_pdf = page.page_h - yt - ascent`-Umrechnung, damit im Zeichencode
  nur „von-oben"-mm benutzt werden.
- `_text_in_band(c, page, x, yt_top, band_h, s, font, size, align, max_w=None)`:
  Text vertikal mittig in einem Band (für Box-Inhalte und Tabellenzellen), über
  `getAscent`/`getDescent`.
- `_col_text_w(edges, idx)`: nutzbare Textbreite einer QSO-Tabellenspalte
  (Spaltenbreite minus `BOX_TEXT_PAD` je Seite).
- `_box`/`_hline`/`_vline`: Rahmen und Linien (Oberkante/Position als `yt`).

---

## 5. Vorgehen zum exakten Nachbau

1. Alle Werte aus §3 als benannte Konstanten in `geometry.py` anlegen.
2. `layout_back.py` implementieren, das ausschließlich diese Konstanten nutzt.
3. Eine Testkarte mit Beispieldaten rendern.
4. Neben die Referenzkarte legen und vergleichen: Positionen/Größen in
   `geometry.py` nachziehen. **Nur dort** ändern, nicht im Zeichencode. (Das
   Foto der Vorlage liegt nicht im Repository — es ist eine private Karte.)
5. Wiederholen, bis das Layout passt. Danach mit echten ADIF-Daten testen
   (mehrere Zeilen bei „pro Station").

> Hinweis: Das Frontbild stellt der Nutzer bereit. Der Bereich unten rechts
> (in der Referenz das Logo) bleibt frei; er kann später anderweitig genutzt werden.
