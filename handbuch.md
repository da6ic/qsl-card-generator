# Handbuch — QSL-Karten-Generator

## Was das Programm macht {#einfuehrung}

Der QSL-Karten-Generator nimmt dein **Logbuch** und macht daraus fertige
**QSL-Karten als PDF**. Jede Karte besteht aus zwei A6-Seiten: vorne dein Bild,
hinten das gewohnte QSL-Layout mit Absender, Empfänger und der QSO-Tabelle.

Was du dafür brauchst:

- ein **Logbuch** — im ADIF-Format (`.adi`, `.adif`) aus deinem Log-Programm
  oder im Cabrillo-Format (`.cbr`, `.log`) aus einem Contest,
- ein **Frontbild**, das auf allen Karten vorne erscheint,
- deine **Absenderdaten** (Rufzeichen, Name, Locator, DOK, CQ-Zone, ITU),
- optional ein kostenloses **HamQTH-Konto**, damit das Programm herausfindet,
  über welchen Weg jede Station QSLs annimmt.

Deine Absenderangaben und alle Einstellungen werden für die nächste Benutzung
**automatisch gespeichert**. Nur die Zugangsdaten für die Lookups
([Kapitel 6](#abschnitt-6)) nicht — die trägst du bei jedem Start neu ein.

Pflichtangaben sind mit einem roten `*` markiert. Fehlt eine davon, sagt dir das
Programm beim Klick auf „PDF erzeugen" in einem einzigen Hinweisfenster, was
noch fehlt, und markiert die betroffenen Felder rot.

## Der Weg zur fertigen PDF {#ueberblick}

Die Oberfläche ist von oben nach unten in zehn Abschnitte geteilt — in dieser
Reihenfolge arbeitest du sie ab:

1. [Logbuch laden](#abschnitt-1) — ADIF- oder Cabrillo-Datei wählen und einlesen.
2. [Frontbild wählen](#abschnitt-2) — ein Bild für alle Karten.
3. [Absender ausfüllen](#abschnitt-3) — deine Stationsdaten.
4. [Zustellwege ordnen](#abschnitt-4) — welche QSLs überhaupt gedruckt werden.
5. [Kartenmodus wählen](#abschnitt-5) — eine Karte pro QSO oder pro Station.
6. [Lookups einrichten](#abschnitt-6) — Zugangsdaten für HamQTH/QRZ (optional).
7. [Bemerkung eintragen](#abschnitt-7) — ein kurzer Text auf der Karte
   (optional).
8. [Vorschau prüfen](#abschnitt-8) — Liste aller Karten, hier korrigierst du
   Einzelfälle.
9. [Druckmodus einstellen](#abschnitt-9) — Duplex, Bogen, Seitenrand.
10. [PDF erzeugen](#abschnitt-10) — Ziel wählen und drucken lassen.

Die unterstrichenen Verweise kannst du anklicken — auch überall sonst im
Handbuch, wo auf ein anderes Kapitel hingewiesen wird. Über die Kapitelliste am
linken Rand kommst du ebenfalls direkt zu jedem Kapitel.

Bei jedem Abschnitt steht oben rechts im Titel ein kleines **?**. Das öffnet
genau das Kapitel dieses Handbuchs.

## 1. Logbuch (ADIF/Cabrillo) {#abschnitt-1}

Wähle mit **Durchsuchen…** deine Logdatei und klicke auf **Log laden**. Unter
dem Feld steht danach, wie viele QSOs eingelesen wurden.

Akzeptiert werden zwei Formate:

- **ADIF** (`.adi`, `.adif`) — was jedes Log-Programm ausgibt.
- **Cabrillo** (`.cbr`, `.log`) — die Datei, die du nach einem Contest beim
  Veranstalter abgibst.

Welches der beiden vorliegt, erkennt das Programm am Inhalt der Datei. Die
Dateiendung ist nur ein Filter im Auswahlfenster; heißt deine Cabrillo-Datei
`contest.txt`, stelle im Dateidialog auf **Alle Dateien** um, dann klappt es
trotzdem.

Passt der Inhalt zu keinem der beiden Formate, sagt das Programm dir das —
statt kommentarlos „0 QSOs" anzuzeigen. Dein bisher geladenes Log bleibt in dem
Fall unverändert stehen.

Diese Felder aus dem Log landen auf der Karte:

- `CALL` — das Rufzeichen der Gegenstation. **Ohne Rufzeichen wird ein Eintrag
  übersprungen**, denn dann gibt es niemanden, an den die Karte ginge.
- `QSO_DATE` — Tag, Monat und Jahr in den Spalten D, M, Y.
- `TIME_ON` — die Spalte UTC TIME.
- `FREQ` — die Spalte FREQ MHZ. Fehlt sie, nimmt das Programm die untere
  Bandkante aus `BAND`; das ist ein Näherungswert, kein exakter QRG-Eintrag.
- `MODE` — die Spalte 2-WAY QSO IN.
- `RST_SENT` — die Spalte SIGNAL REPORT. Das ist bewusst der Rapport, den **du
  gegeben** hast, nicht der empfangene. Digimode-Rapporte wie `-07` stehen dort
  genauso wie `59`.

Fehlt eines dieser Felder, bleibt die Spalte auf der Karte einfach leer.

### Was bei einem Contest-Log anders ist

Ein Cabrillo-Log ist knapper als ein ADIF-Log — es enthält nur, was der Contest
braucht. Daran ändert sich für dich Folgendes:

- **Der Rapport fehlt oft.** Viele Contests tauschen statt `59` einen Locator,
  einen Namen oder eine Sektion aus (NAQP, die VHF-Contests, ARRL Sweepstakes).
  Dann bleibt die Spalte SIGNAL REPORT leer. Das Programm erfindet dort bewusst
  nichts — eine QSL-Karte soll nur bestätigen, was wirklich im Log steht.
- **Dein eigenes Rufzeichen im Kopf der Datei wird nicht übernommen.** Der
  Absender auf der Karte kommt immer aus [Abschnitt 3](#abschnitt-3), auch wenn
  du im Contest unter einem anderen Rufzeichen gefahren bist.
- **Gestrichene QSOs kommen mit.** Der Contest wertet sie nicht,
  aber die Verbindung hat ja stattgefunden — die Gegenstation bekommt ihre
  Karte. Willst du das nicht, setze die Zeile in der Vorschau
  ([Kapitel 8](#abschnitt-8)) auf **Drucken: Nein**.
- **Oberhalb von 902 MHz steht im Contest-Log nur das Band**, keine genaue
  Frequenz. Auf der Karte steht dann die Bandmitte, zum Beispiel `1240` für das
  23-cm-Band.
- **Ein Contest-Log ist groß.** Bei mehreren hundert QSOs dauert die
  Stationsabfrage ([Kapitel 6](#abschnitt-6)) entsprechend lange. „Eine Karte
  pro Station" ([Kapitel 5](#abschnitt-5)) ist hier meist die bessere Wahl.

Ein erneutes **Log laden** baut die Kartenliste komplett neu auf. Deine
Korrekturen in der Vorschau ([Kapitel 8](#abschnitt-8)) gehen dabei verloren,
und die Stationsabfrage startet von vorn.

## 2. Frontbild {#abschnitt-2}

Ein Bild, das auf **allen** Karten vorne erscheint — unterschiedliche Motive je
Karte sind nicht vorgesehen.

Unterstützt werden die Bildformate **PNG, JPG/JPEG und WEBP**. Klappt das
Einlesen nicht, steht im Vorschaufeld ein Hinweis statt des Bildes.

Wichtig für ein gutes Ergebnis:

- Das Bild füllt die Karte **randlos** aus. Passt das Seitenverhältnis nicht
  genau, wird über die Kanten hinaus beschnitten — verzerrt wird nie. Lass
  deshalb an den Rändern etwas Luft und setze nichts Wichtiges (Rufzeichen,
  Text) ganz nach außen.
- Die Karte ist **quer** (148 × 105 mm). Ein Querformat-Bild passt am besten.
- Für sauberen Druck mit 300 dpi sollte das Bild etwa **1750 × 1240 Pixel** oder
  größer sein.
- Ist in [Abschnitt 9](#abschnitt-9) ein Seitenrand eingestellt, rückt auch das
  Frontbild um denselben Rand ein, damit Vorder- und Rückseite deckungsgleich
  sitzen.

## 3. Absender {#abschnitt-3}

Diese Angaben stehen auf **jeder** Karte und kommen immer aus diesem Abschnitt —
nie aus dem Logbuch.

**Pflicht** sind: Rufzeichen, Name, Locator, DOK, CQ-Zone und ITU. Rufzeichen
und Name stehen links oben, Locator/DOK/CQ-Zone/ITU rechts daneben als
Stationsblock.

**Freiwillig** sind Straße, PLZ, Ort und Land. Trägst du sie ein, erscheinen sie
unter deinem Namen; lässt du sie leer, bleibt die Karte eben ohne Adresse.

Unter **Funk-Ausrüstung** kannst du Empfänger, Antenne und Leistung angeben. Der
Block erscheint auf der Karte nur, wenn mindestens eines der Felder gefüllt ist,
und zeigt nur die ausgefüllten Werte.

Unter **Markierungen** stellst du zwei Dinge für alle Karten ein:

- **QSL-Markierung** — `PSE QSL` (bitte um Karte) oder `TNX QSL` (Dank für die
  erhaltene Karte); „Leer lassen" druckt nichts.
- **Bestätigung** — `Confirming QSO` oder `Confirming SWL-Report`, mittig oben
  auf der Karte.

Eine **Portabel-Kennung** tippst du einfach mit ins Rufzeichen: `DL0MT/P`. Genauso
alles andere, was dazugehört — ein Landespräfix aus dem Urlaub (`F/DL0MT`), beides
zusammen (`F/DL0MT/P`), `/QRP` oder `/MM`. Was im Feld steht, steht auf der Karte;
klein Getipptes wird dabei großgeschrieben, sobald du das Feld verlässt (das gilt
auch für Locator und DOK).

Alles, was du hier eintippst, wird kurz darauf automatisch gespeichert. Beim
nächsten Start steht es wieder da.

## 4. Zustellwege {#abschnitt-4}

Hier entscheidest du, **welche QSLs überhaupt gedruckt werden**.

Es gibt vier Wege, eine QSL zuzustellen:

- **Büro** — über das QSL-Büro des Verbandes, inklusive der Stationen mit einem
  QSL-Manager.
- **Direkt** — per Post an die Station selbst.
- **eQSL** — elektronisch über eQSL.cc.
- **LOTW** — elektronisch über Logbook of the World.

Welche davon eine Station annimmt, steht **nicht im Logbuch**. Das ermittelt der
Lookup ([Kapitel 6](#abschnitt-6)) für jede Station einzeln — eine Station kann
mehrere Wege akzeptieren.

In der Liste bringst du die vier Wege mit **▲** und **▼** in deine
Wunschreihenfolge und schiebst die Trennlinie **──── nicht drucken ────** an die
passende Stelle:

- Alles **über** der Linie ist aktiv. Je weiter oben, desto lieber.
- Alles **unter** der Linie wird nicht gedruckt.

Gedruckt wird pro Karte der oberste aktive Weg, den die Station auch annimmt.
Nimmt sie keinen der aktiven Wege an, steht die Karte in der Vorschau auf
„Drucken: Nein".

**Beispiel:** Die Voreinstellung ist `Büro`, `Direkt`, dann die Trennlinie. So
werden Papierkarten gedruckt, für rein elektronische Bestätigungen brauchst du
keine. Eine Station, die nur LoTW nutzt, fällt damit heraus — genau so ist es
gemeint. Willst du sie trotzdem, ziehe die Trennlinie tiefer oder schalte die
einzelne Karte in der Vorschau von Hand auf „Ja".

Ohne Lookup-Zugangsdaten kennt das Programm keine Wege und setzt alle Stationen
auf Büro. Dann werden schlicht alle Karten gedruckt.

## 5. Kartenmodus {#abschnitt-5}

- **Eine Karte pro QSO** — jedes QSO bekommt seine eigene Karte mit einer
  Tabellenzeile.
- **Eine Karte pro Station** — alle QSOs mit demselben Rufzeichen kommen auf
  eine Karte untereinander. Das spart Karten und Porto, wenn du eine Station
  mehrfach gearbeitet hast.

Auf eine Karte passen **6 QSO-Zeilen**. Steht auf der Karte eine Bemerkung
([Kapitel 7](#abschnitt-7)), braucht deren Kasten Platz und es passen nur noch
**3 Zeilen**. Hat eine Station mehr QSOs, entstehen automatisch Folgekarten.

## 6. Lookups {#abschnitt-6}

Ein „Lookup" ist die Abfrage einer Rufzeichendatenbank im Internet. Sie liefert
drei Dinge, die im Logbuch nicht stehen:

- welche **Zustellwege** die Station annimmt ([Kapitel 4](#abschnitt-4)),
- den **QSL-Manager**, falls es einen gibt — sein Rufzeichen steht dann auf der
  Karte im Feld „Via:",
- die **Postanschrift** für den Adressexport.

Der Lookup startet **automatisch**, sobald du ein Logbuch lädst, und läuft im
Hintergrund für alle Stationen. Solange er läuft, steht in der Vorschau `…` und
du kannst noch keine Karten erzeugen.

**HamQTH** ist die erste Wahl: Ein Konto auf
[hamqth.com](https://www.hamqth.com) ist kostenlos und liefert alle vier
Zustellwege, Manager und Adresse. Trage Benutzername und Passwort in die beiden
HamQTH-Felder ein — bei jedem Programmstart neu, siehe unten.

**QRZ** ist optional und ein Zusatz für Stationen, die HamQTH nicht kennt. Ohne
bezahltes XML-Abo liefert QRZ im Wesentlichen nur den Manager, keine
Zustellwege.

Ohne Zugangsdaten schaut das Programm nicht nach. Alle Stationen bekommen dann
den Standardweg Büro, Adressen bleiben leer.

Damit dieselbe Station nicht bei jedem Start neu abgefragt wird, merkt sich das
Programm die Antworten in der Datei `lookup_cache.json`. Auch „nicht gefunden"
wird gemerkt.

- **Neu abrufen** (Knopf in der Vorschau) holt zuerst nur die noch offenen
  Stationen nach. Sind alle aufgelöst, fragt es alle noch einmal frisch ab.
- **Aktionen ▸ Lookup-Cache leeren…** wirft alles weg. Das ist der richtige
  Griff, wenn du weißt, dass sich Angaben geändert haben.

Die gefundenen Anschriften kannst du dir als Datei ausgeben lassen — die Checkbox
dafür steht bei der Ausgabe ([Kapitel 10](#abschnitt-10)), weil die Datei dort
entsteht. Auf der Karte selbst steht die Anschrift des Empfängers grundsätzlich
nicht, dort erscheint nur sein Rufzeichen.

**Die Zugangsdaten werden nicht gespeichert.** Sie gelten nur für die laufende
Sitzung und stehen in keiner Datei — weder in der `config.yaml` noch sonst wo
(siehe [Wo liegen meine Dateien?](#dateien)). Beim nächsten Start sind die vier
Felder deshalb wieder leer und du trägst sie erneut ein. Das ist Absicht: ein
Passwort im Klartext auf der Platte wäre für jeden lesbar, der an deinen Rechner
kommt. Alle übrigen Einstellungen bleiben natürlich erhalten.

## 7. Bemerkungen {#abschnitt-7}

Der Text unter **Text für alle Karten** erscheint auf jeder Karte im
REMARKS-Kasten, zum Beispiel „Vielen Dank für das nette QSO im 40-m-Band".

- Maximal **80 Zeichen**
- Lässt du das Feld leer, gibt es keinen Kasten und es passen wieder 6 QSOs auf
  eine Karte statt 3 ([Kapitel 5](#abschnitt-5)).
- Der Text wird übernommen, sobald du das Feld verlässt oder Enter drückst.
- In der Vorschau kannst du die Bemerkung **je Karte** überschreiben. Änderst du
  danach den globalen Text, fragt das Programm nach, ob es die von Hand
  gesetzten Bemerkungen überschreiben soll.

## 8. Vorschau {#abschnitt-8}

Die Tabelle zeigt jede Karte, die erzeugt werden würde. Hier korrigierst du
Einzelfälle, bevor gedruckt wird.

Die Spalten:

- **Drucken** — `Ja` oder `Nein`. Zeilen auf „Nein" sind ausgegraut und landen
  nicht in der PDF.
- **Call** — das Rufzeichen der Gegenstation.
- **#QSOs** — wie viele QSO-Zeilen auf dieser Karte stehen.
- **Via** — der Zustellweg, über den diese Karte ginge.
- **Route/Manager** — das Manager-Rufzeichen für das Feld „Via:" auf der Karte.
- **Remarks** — die Bemerkung dieser einen Karte.
- **Datum** und **UTC** — vom ersten QSO der Karte.

Bedienen:

- **Drucken umschalten**: einmal in die Spalte klicken.
- **Via, Route/Manager und Remarks ändern**: Doppelklick in die Zelle. Enter
  übernimmt, Escape verwirft. Fährst du mit der Maus über eine änderbare Zelle,
  erscheint rechts ein kleines Stift- bzw. Schaltersymbol — ein Klick darauf tut
  dasselbe.
- **Sortieren**: Klick auf einen Spaltentitel; nochmal klicken dreht die
  Richtung um, ein drittes Mal hebt die Sortierung auf. Die PDF folgt der
  Reihenfolge, die du hier siehst.

Stellst du bei einer Karte den Via-Weg von Hand ein, wird sie automatisch auf
„Drucken: Ja" gesetzt.

Steht in Via und Route noch `…`, läuft der Lookup — dann ist nichts änderbar,
warte kurz.

Alle Korrekturen hier gelten **nur für diese Sitzung**. „Log laden" oder „Neu
abrufen" bauen die Liste neu auf und verwerfen sie.

## 9. Druckmodus {#abschnitt-9}

**Duplexdruck (Vorder-/Rückseite abwechselnd)** erzeugt eine einzige PDF, in der
sich Bild- und Textseite abwechseln. Das ist die richtige Wahl für Drucker, die
beidseitig drucken können. Stelle im Druckdialog beidseitig mit Wendung an der
**langen Kante** ein.

**Vorder-/Rückseite getrennt (2 PDFs)** erzeugt zwei Dateien: erst alle
Vorderseiten, dann alle Rückseiten. So gehst du vor:

1. Die Datei `…_vorderseiten.pdf` drucken.
2. Den Stapel wenden und wieder einlegen.
3. Die Datei `…_rueckseiten.pdf` auf dieselben Blätter drucken.

Weil alle Karten dasselbe Frontbild haben, kann beim Wenden nichts
durcheinandergeraten. Mache trotzdem einen Probedruck mit zwei Blättern, um die
Einlegerichtung deines Druckers zu finden.

**4 A6 QSL-Karten auf einem A4-Bogen** lässt sich mit beiden Druckmodi
kombinieren. Dann stehen vier Karten im 2×2-Raster auf einem A4-Blatt quer, das
du hinterher zerschneidest. Auf den Rückseitenbögen sind dafür gestrichelte
Schnittlinien eingezeichnet.

Hinter **Erweiterte Einstellungen** liegt der **Seitenrand (mm)**. Die meisten
Drucker können nicht bis an die Blattkante drucken; hier stellst du ein, wie
viel Rand mindestens frei bleiben muss — für jede der vier Kanten einzeln, denn
unten brauchen viele Drucker mehr Platz. Erlaubt sind 0 bis 15 mm.

Die Karte wird dafür verkleinert. Der Rand gilt auch beim Bogendruck **je
Karte**: zwischen zwei Karten liegt deshalb ein doppelt breiter weißer Streifen,
durch dessen Mitte du schneidest — so hat jede fertige Karte ringsum ihren Rand.

Wichtig beim Drucken: Stelle im Druckdialog die Skalierung auf **100 % bzw.
„keine Anpassung"**. Wählt der Druckertreiber „An Seite anpassen", schrumpft er
die Karte ein zweites Mal und die eingestellten Ränder stimmen nicht mehr.

## 10. Ausgabe {#abschnitt-10}

Mit **Ziel…** wählst du, wohin die PDF geschrieben wird; voreingestellt ist
`qsl_karten.pdf` in deinem Dokumentenordner. Dann **PDF erzeugen** — der Balken
zeigt den Fortschritt.

Die Checkbox **Adress-/Label-Export erzeugen** darüber legt zusätzlich eine
CSV-Datei mit den Anschriften an, die der Lookup gefunden hat
([Kapitel 6](#abschnitt-6)) — praktisch für Adressetiketten beim Direktversand.
Sie landet neben der PDF; Stationen ohne gefundene Anschrift stehen nicht darin.

Je nach Einstellung entstehen:

- im Duplexmodus **eine** PDF unter dem gewählten Namen,
- im getrennten Modus **zwei** PDFs mit den Zusätzen `_vorderseiten` und
  `_rueckseiten`,
- zusätzlich eine CSV-Datei mit dem Zusatz `_addresses`, falls du den
  Adressexport eingeschaltet hast.

Ist alles fertig, öffnet das Programm die Dateien gleich in deinem
PDF-Betrachter.

## Menü und Tastenkürzel {#menue}

Die Kürzel unterscheiden sich je nach Betriebssystem: unter **Windows und
Linux** hältst du `Strg`, unter **macOS** die Befehlstaste `⌘`. Die
Umschalttaste heißt hier `Umschalt` bzw. `⇧`. Im Menü selbst steht immer das
Kürzel, das auf deinem Rechner gilt.

### Datei

- **Logbuch öffnen…** — Windows/Linux `Strg + O`, macOS `⌘ + O`
- **Zuletzt verwendete Logs** — kein Kürzel
- **Frontbild wählen…** — Windows/Linux `Strg + B`, macOS `⌘ + B`
- **Zuletzt verwendete Bilder** — kein Kürzel
- **Ausgabeziel wählen…** — Windows/Linux `Strg + Umschalt + S`, macOS `⌘ + ⇧ +
  S`
- **PDF erzeugen** — Windows/Linux `Strg + P`, macOS `⌘ + P`
- **Beenden** — Windows/Linux `Strg + Q`. Auf macOS steht „Beenden" wie üblich
  im Programmmenü ganz links und hört auf `⌘ + Q`.

### Aktionen

- **Log neu laden** — Windows/Linux `Strg + R`, macOS `⌘ + R`
- **Lookups neu abrufen** — Windows/Linux `Strg + Umschalt + R`, macOS `⌘ + ⇧ +
  R`
- **Lookup-Cache leeren…** — kein Kürzel

### Ansicht

- **Farbthema** — System, Hell oder Dunkel. Kein Kürzel.
- **Gehe zu Abschnitt** — springt zum gewünschten Abschnitt im Fenster. Kein
  Kürzel.

### Hilfe

- **Handbuch** — Windows/Linux `F1`, macOS `⌘ + ?`. Öffnet dieses Fenster.
- **config.yaml öffnen**, **Ausgabeordner anzeigen**, **Lookup-Cache anzeigen**,
  **Protokoll anzeigen** — keine Kürzel. Wo diese Dateien liegen, steht im
  Kapitel [Wo liegen meine Dateien?](#dateien).
- **Über QSL-Karten-Generator** — auf Windows und Linux hier, auf macOS im
  Programmmenü ganz links.

## Installieren und weitergeben {#installation}

Das Programm kommt als Archiv und braucht kein Installationsprogramm. Du
entpackst es an einen Ort, den du beschreiben darfst, und startest es von dort.
Zum Entfernen löschst du den Ordner wieder.

**Windows** — ZIP entpacken nach Dokumente, Desktop oder auf einen USB-Stick,
dann `QSL-Karten-Generator.exe` starten. **Nicht** nach `C:\Programme`: dorthin
darf das Programm nicht schreiben. Beim ersten Start meldet Windows „Der
Computer wurde durch Windows geschützt" — das Programm ist nicht signiert. Über
*Weitere Informationen* ▸ *Trotzdem ausführen* geht es weiter.

**macOS** — ZIP entpacken und die App dorthin legen, wo du sie haben willst
(`Programme`, Schreibtisch oder USB-Stick); die `LIESMICH.txt` daneben brauchst
du danach nicht mehr. Beim ersten Start verweigert macOS den Start: die App ist
signiert, aber nicht bei Apple registriert. Der Weg daran vorbei hängt an der
Version — auf **macOS 15 und neuer** klickst du die Meldung weg und erlaubst den
Start unter *Systemeinstellungen ▸ Datenschutz & Sicherheit* mit *Dennoch
öffnen*; auf **macOS 14 und älter** genügt einmal **Rechtsklick ▸ Öffnen** statt
Doppelklick. Danach reicht der Doppelklick.

**Linux** — `tar xzf QSL-Karten-Generator-*.tar.gz`, dann im entpackten Ordner
`./install.sh`. Das legt das Programm nach `~/.local/opt` und trägt es ins
Anwendungsmenü ein, ohne `sudo`. Entfernen mit `./install.sh --uninstall`. Ohne
Installation läuft es genauso: `./QSL-Karten-Generator` im entpackten Ordner.

Gibst du das Archiv weiter, gib den Hinweis auf die Startmeldung mit — sonst
hält der Empfänger das Programm für gefährlich und löscht es.

## Wo liegen meine Dateien? {#dateien}

Das Programm legt seine Dateien dort ab, wo dein Betriebssystem sie erwartet.
Von Hand musst du dort nie etwas ändern — **config.yaml öffnen**,
**Lookup-Cache anzeigen** und **Protokoll anzeigen** im Menü **Hilfe** bringen
dich direkt hin ([Menü](#menue)).

- **Windows** — `%APPDATA%\QSL-Karten-Generator\`
- **macOS** — `~/Library/Application Support/QSL-Karten-Generator/`
  (der Finder versteckt `Library`; nimm den Menüeintrag)
- **Linux** — `~/.config/qsl-karten-generator/`

Darin liegen drei Dateien:

- `config.yaml` — alle deine Einstellungen. Das Programm schreibt sie bei jeder
  Änderung selbst; bearbeite sie nicht von Hand, sonst überschreibt der nächste
  Klick deine Änderung. Zum Sichern oder Umziehen auf einen neuen Rechner
  kopierst du einfach diese eine Datei. Die Zugangsdaten für die Lookups stehen
  **nicht** darin ([Kapitel 6](#abschnitt-6)) — die gibst du auf dem neuen
  Rechner einmal neu ein.
- `lookup_cache.json` — die gemerkten Antworten der Lookups
  ([Kapitel 6](#abschnitt-6)).
- `qslcards.log` — das Protokoll. Klemmt etwas, steht hier der Grund.

Die fertigen PDFs landen dort, wo du sie in [Abschnitt 10](#abschnitt-10)
hinlegst; vorgeschlagen wird dein Dokumentenordner.

### Das Programm mitnehmen

Legst du eine `config.yaml` **direkt neben das Programm**, benutzt es diese und
lässt den Ordner oben unberührt. Damit läuft alles von einem USB-Stick, und du
kannst dieselbe Einrichtung an einen anderen Rechner mitnehmen. Wie du an eine
`config.yaml` kommst: einmal normal starten, etwas eintragen, dann die Datei aus
dem Ordner oben neben das Programm kopieren.

Das geht nur, wenn der Programmordner beschreibbar ist — unter Windows also
**nicht** aus `C:\Programme` heraus.

## Wenn etwas nicht klappt {#probleme}

**„Pflichtangaben fehlen"** — es fehlt eine der mit `*` markierten Angaben. Das
Fenster listet alle auf einmal auf, danach sind die Stellen rot markiert und die
Ansicht springt zur ersten davon.

**„Logbuch nicht verwertbar"** — die Datei ist weder ADIF noch Cabrillo.
Hast du vielleicht eine Auswertung oder eine Tabelle erwischt statt der
Logdatei selbst? Ein ADIF-Log enthält Einträge wie `<CALL:5>`, ein Cabrillo-Log
beginnt mit `START-OF-LOG:` ([Kapitel 1](#abschnitt-1)).

**Die Spalte SIGNAL REPORT bleibt leer** — bei einem Contest-Log ist das normal:
viele Contests tauschen gar keinen Rapport aus ([Kapitel 1](#abschnitt-1)).

**„PDF erzeugen" reagiert nicht** — läuft noch der Lookup? Solange Stationen
abgefragt werden, ist der Knopf gesperrt. Der Status unten im Fenster sagt, wie
weit es ist.

**Eine Station fehlt in der Kartenliste** — sie nimmt keinen der aktiven
Zustellwege an ([Kapitel 4](#abschnitt-4)). Zieh die Trennlinie tiefer oder
setze die Karte in der Vorschau von Hand auf „Drucken: Ja".

**Alle Karten stehen auf Büro** — dann gibt es keine Lookup-Zugangsdaten oder
die Abfrage ist fehlgeschlagen. Prüfe [Abschnitt 6](#abschnitt-6). Nach jedem
Programmstart sind die vier Felder leer; sie werden bewusst nicht gespeichert.

**Der Manager stimmt nicht** — die Datenbank ist nicht immer aktuell. Korrigiere
das Feld „Route/Manager" in der Vorschau, oder leere den Cache und frage neu ab.

**Die Ränder im Ausdruck stimmen nicht** — fast immer die Skalierung im
Druckdialog; sie muss auf 100 % / „keine Anpassung" stehen ([Kapitel
9](#abschnitt-9)).

**Etwas anderes klemmt** — dann schau ins Protokoll: **Hilfe ▸ Protokoll
anzeigen** ([Wo liegen meine Dateien?](#dateien)). Dort notiert das Programm,
was es nicht geschafft hat. Die letzten Zeilen sind die interessanten.
