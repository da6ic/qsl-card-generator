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
- optional ein **QRZ-** und/oder ein (kostenloses) **HamQTH-Konto**, damit das
  Programm herausfindet, über welchen Weg jede Station QSLs annimmt.

Deine Absenderangaben und alle Einstellungen werden für die nächste Benutzung
**automatisch gespeichert**. Nur die Zugangsdaten für die Lookups
([Kapitel 6](#abschnitt-6)) nicht — die trägst du bei jedem Start neu ein.

Pflichtangaben sind mit einem roten `*` markiert. Fehlt eine davon, nennt dir das
Programm unten in der Leiste neben „Weiter", was noch fehlt, und markiert die
betroffenen Felder rot.

## Der Weg zur fertigen PDF {#ueberblick}

Das Programm führt dich als **Assistent** in sechs Schritten zur PDF. Es zeigt
immer nur den aktuellen Schritt; oben siehst du, wo du stehst (blau = aktuell,
grün = erledigt), unten geht es mit **Weiter** und **Zurück** voran. Fehlt noch
etwas Wichtiges, bleibt **Weiter** stehen und sagt rot daneben, was fehlt. Auf
einen Schritt oben kannst du auch direkt klicken.

1. **Quelle** — [Logdatei laden](#abschnitt-1) *oder* die QSOs direkt
   [aus Wavelog holen](#wavelog).
2. **Absender** — [deine Stationsdaten](#abschnitt-3).
3. **Abfrage** — [Lookups einrichten](#abschnitt-6) (optional),
   [Zustellwege ordnen](#abschnitt-4) und den [Kartenmodus](#abschnitt-5) wählen.
4. **Gestalten** — [Frontbild wählen](#abschnitt-2),
   [Bemerkung eintragen](#abschnitt-8) (optional) und
   [Most Wanted](#abschnitt-7) (optional).
5. **Prüfen** — in der [Vorschau](#abschnitt-9) Einzelfälle korrigieren. Die
   Tabelle nutzt hier die ganze Fensterhöhe.
6. **Druck** — [Druckmodus einstellen](#abschnitt-10) (Duplex, Bogen,
   QR-Code, Seitenrand) und die [PDF erzeugen](#abschnitt-11). Kamen die QSOs
   aus Wavelog, markiert das Programm sie danach auf Wunsch als
   „Papier-QSL gesendet".

Hast du die Zugangsdaten für QRZ/HamQTH erst in Schritt 3 eingetragen, schlägt
das Programm die Stationen beim Verlassen von Schritt 3 automatisch nach.

Die Farben der Oberfläche sind nicht einzeln ausgesucht, sondern aus einer
Grundfarbe (Funk-Cyan) über den Farbkreis abgeleitet: Grün liegt 60° daneben,
Rot und Bernstein auf den beiden „geteilten Komplementärfarben" gegenüber.

Die unterstrichenen Verweise kannst du anklicken — auch überall sonst im
Handbuch, wo auf ein anderes Kapitel hingewiesen wird. Über die Kapitelliste am
linken Rand kommst du ebenfalls direkt zu jedem Kapitel.

Bei jedem Abschnitt steht im Titel ein kleines **?**. Das öffnet
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
  ([Kapitel 9](#abschnitt-9)) auf **Drucken: Nein**.
- **Oberhalb von 902 MHz steht im Contest-Log nur das Band**, keine genaue
  Frequenz. Auf der Karte steht dann die Bandmitte, zum Beispiel `1240` für das
  23-cm-Band.
- **Ein Contest-Log ist groß.** Bei mehreren hundert QSOs dauert die
  Stationsabfrage ([Kapitel 6](#abschnitt-6)) entsprechend lange. „Eine Karte
  pro Station" ([Kapitel 5](#abschnitt-5)) ist hier meist die bessere Wahl.

Ein erneutes **Log laden** baut die Kartenliste komplett neu auf. Deine
Korrekturen in der Vorschau ([Kapitel 9](#abschnitt-9)) gehen dabei verloren,
und die Stationsabfrage startet von vorn.

## Wavelog als Quelle {#wavelog}

Statt einer Logdatei kannst du die QSOs direkt aus deinem
[Wavelog](https://www.wavelog.org) holen. Wähle in Schritt 1 **Direkt aus
Wavelog**:

1. **Adresse** deiner Wavelog-Instanz eintragen, z.B. `https://log.example.org`.
2. **API-Key** eintragen. Gebraucht wird ein Token der API v2 (beginnt mit
   `wl2_`, in Wavelog unter den API-Einstellungen deines Kontos) mit den Rechten
   `station:read` und `qso:read`, zum Markieren zusätzlich `qso:write`. Wavelog
   muss mindestens Version 3.2.5 haben (die API v2 gibt es ab 3.1, das
   Markieren als gesendet erst ab 3.2.5). Beginnt die Adresse mit `http://` und
   zeigt nicht in dein Heimnetz, warnt das Programm: der Key ginge dann
   unverschlüsselt über das Internet.
3. **Stationen laden** drücken und im Dropdown den Stationsstandort wählen, für
   den du Karten drucken willst. Die aktive Station steht oben und trägt einen ★.
4. Optional einen **Zeitraum** (JJJJ-MM-TT) eingeben. Ein Tippfehler wird
   sofort rot markiert, bevor Wavelog gefragt wird.
5. **QSOs laden** drücken.

QSOs, für die schon eine Papier-QSL gesendet wurde, lässt das Programm
**immer** weg — das gilt auch für Logdateien (ADIF-Feld `QSL_SENT` = Y). Bei
Wavelog merkt es sich zusätzlich jedes QSO, das es selbst als gesendet markiert
hat (`wavelog_sent.json` neben der `config.yaml`). So wird auch dann keine Karte
doppelt gedruckt, wenn eine Wavelog-Version den Versandstatus beim Abruf nicht
mitliefert.

**Achtung, Grenze dieser Liste:** Sie kennt nur, was *dieses* Programm auf
*diesem* Rechner markiert hat. Liefert deine Wavelog-Instanz den Versandstatus
nicht mit, zeigt Schritt 1 nach dem Laden einen gelben Hinweis mit der Zahl der
betroffenen QSOs. Dann gilt: was du in Wavelog von Hand oder von einem anderen
Rechner aus als gesendet gesetzt hast, steht wieder in der Liste. Prüfe die
Vorschau in dem Fall besonders genau. Ist die Datei `wavelog_sent.json`
beschädigt, meldet das Programm das rot und überschreibt sie **nicht** — sonst
wäre das Sicherheitsnetz unbemerkt weg.

**Bewusst nachdrucken** (Karte verloren, Rückläufer vom Büro): In der
[Vorschau](#abschnitt-9) **Schon gesendete anzeigen** anhaken. Die gesendeten
QSOs erscheinen als eigene Karten auf „Drucken: Nein"; hake die gewünschten an.
Nachdrucke werden in Wavelog nicht noch einmal markiert.

**Bei Logdateien** vermerkt das Programm nach dem Druck nichts: wer dieselbe
ADIF-Datei zweimal lädt, druckt zweimal. Setze die gedruckten QSOs deshalb in
deinem Logprogramm auf „QSL gesendet" und exportiere neu.

Leere Absenderfelder (Rufzeichen, Locator, CQ-Zone, ITU) füllt das Programm aus
dem Stationsstandort; was du schon eingetragen hast, bleibt stehen.

**Nach dem Druck:** Ist in Schritt 6 „als Papier-QSL gesendet markieren" an,
fragt das Programm nach dem Erzeugen der PDF, ob es die QSOs der gedruckten
Karten in Wavelog markieren soll. Es setzt dann *QSL gesendet = Ja*, das heutige
Datum und den Weg (Büro, Direkt oder Manager). Sagst du „Abbrechen", kannst du
das später mit **Jetzt markieren** nachholen — auch nach einem Neustart: die
offenen Markierungen merkt sich das Programm in `wavelog_sent.json`. Karten über
**eQSL oder LoTW** werden nie als Papier-QSL markiert. Nach dem Markieren steht
auf der Druckseite eine kurze Zusammenfassung; Fehler kannst du dort markieren
und kopieren. Bremst Wavelog wegen zu vieler Anfragen, wartet das Programm die
verlangte Zeit ab und macht dann weiter.

Der API-Key wird **nicht** in die `config.yaml` geschrieben. Mit **Im
Schlüsselbund merken** legt das Programm ihn im Schlüsselbund deines Systems ab
(Windows: Anmeldeinformationsverwaltung, macOS: Schlüsselbund). Ist dort nichts
verfügbar, ist das Kästchen ausgegraut und du trägst den Key bei jedem Start neu
ein.

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
- Ist in [Abschnitt 10](#abschnitt-10) ein Seitenrand eingestellt, rückt auch das
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

**Lange Angaben werden kleiner gedruckt, nie abgeschnitten.** Auf der Karte hat
jedes Feld seinen festen Platz — ein sehr langer Name oder eine ausführliche
Antennenbezeichnung wird deshalb so weit verkleinert, bis sie hineinpasst, statt
über den Nachbarn zu laufen. Wirkt eine Zeile auf der fertigen Karte
auffällig klein, ist das der Hinweis, sie kürzer zu fassen.

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
([Kapitel 8](#abschnitt-8)), braucht deren Kasten Platz und es passen nur noch
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
du kannst noch keine Karten erzeugen. Die Vorschau zeigt den Fortschritt und
eine geschätzte Restzeit; mit **Abbrechen** hältst du ihn an (schon Gefundenes
bleibt, **Neu abrufen** holt den Rest). Lädst du während eines Lookups ein
anderes Log, wird der alte abgebrochen und das neue Log nachgeschlagen.

**QRZ** wird zuerst gefragt. Trage Benutzername und Passwort in die beiden
QRZ-Felder ein — bei jedem Programmstart neu oder aus dem Schlüsselbund, siehe
unten. Ohne bezahltes
XML-Abo liefert QRZ allerdings eingeschränkte Angaben und in keinem Fall die
Zustellwege.

**HamQTH** ist die zweite Wahl: Ein Konto auf
[hamqth.com](https://www.hamqth.com) ist kostenlos und liefert als einziges alle
vier Zustellwege. Trage auch diese Zugangsdaten ein, wenn du keine QRZ-Daten hast
— **oder gerade zusätzlich zu ihnen**: Was QRZ zu einer Station nicht weiß, holt
das Programm dann bei HamQTH nach und setzt beides zu einer Antwort zusammen.
Angaben von QRZ haben dabei Vorrang. Mit beiden Konten dauert der Lookup etwas
länger, weil für viele Stationen beide Anbieter gefragt werden.

Ohne Zugangsdaten schaut das Programm nicht nach. Alle Stationen bekommen dann
den Standardweg Büro, Adressen bleiben leer.

Damit dieselbe Station nicht bei jedem Start neu abgefragt wird, merkt sich das
Programm die Antworten in der Datei `lookup_cache.json`. Auch „nicht gefunden"
wird gemerkt.

- **Neu abrufen** (Knopf in der Vorschau) holt zuerst nur die noch offenen
  Stationen nach. Sind alle aufgelöst, fragt es alle noch einmal frisch ab.
- **Aktionen ▸ Lookup-Cache leeren…** wirft alles weg. Das ist der richtige
  Griff, wenn du weißt, dass sich Angaben geändert haben.

**Wenn du Zugangsdaten nachträgst, drücke „Neu abrufen".** Ein Beispiel: Du hast
eine Sitzung lang nur mit QRZ gearbeitet — dann stehen im Cache Antworten *ohne*
Zustellwege, weil QRZ keine liefert. Trägst du später zusätzlich HamQTH ein,
antwortet für diese Stationen weiterhin der Cache, und in Abschnitt 4 tut sich
nichts. **Neu abrufen** (oder der Cache-Griff darüber) fragt frisch nach und
holt die Wege dann nach.

Die gefundenen Anschriften kannst du dir als Datei ausgeben lassen — die Checkbox
dafür steht bei der Ausgabe ([Kapitel 11](#abschnitt-11)), weil die Datei dort
entsteht. Auf der Karte selbst steht die Anschrift des Empfängers grundsätzlich
nicht, dort erscheint nur sein Rufzeichen.

**Die Zugangsdaten stehen nie in einer Datei.** Ohne weiteres Zutun gelten sie
nur für die laufende Sitzung — weder in der `config.yaml` noch sonst wo (siehe
[Wo liegen meine Dateien?](#dateien)). Beim nächsten Start sind die vier Felder
wieder leer. Das ist Absicht: ein Passwort im Klartext auf der Platte wäre für
jeden lesbar, der an deinen Rechner kommt.

Wer sie nicht jedes Mal eintippen mag, hakt **Im Schlüsselbund merken** an.
Dann legt das Programm Benutzer und Passwort in den Schlüsselbund deines
Systems (wie den Wavelog-Key) und trägt sie beim Start selbst ein. Haken weg
löscht den Eintrag wieder. Auch im Protokoll tauchen Passwörter nicht auf.

## 7. Most Wanted {#abschnitt-7}

Hier kannst du die Karten auf die **gesuchtesten DXCC-Gebiete** beschränken —
etwa um nach einer DXpedition-Saison zuerst die seltenen Bestätigungen auf den
Weg zu bringen.

Die Rangliste stammt von der German DX Foundation
([gdxf.de/mostwanted](https://gdxf.de/mostwanted/)). Sie zeigt, welche Gebiete
aus Sicht Mitteleuropas am meisten gesucht sind — Platz 1 ist das seltenste,
ganz hinten steht Deutschland selbst. Die GDXF stellt sie einmal im Jahr neu
auf, getrennt nach Mixed, CW, Phone und Digital.

- **Nur Most Wanted drucken** — schaltet den Filter ein. Aus: Es zählen nur die
  Zustellwege ([Kapitel 4](#abschnitt-4)), wie gewohnt.
- **Top** — wie viele Plätze der Rangliste zählen, von 1 bis 340. Mit „50" wird
  nur gedruckt, was unter den 50 gesuchtesten Gebieten ist.
- **Kategorie** — an welcher Rangliste gemessen wird. **Automatisch (nach
  Mode)** nimmt für jedes QSO die passende: CW für CW, Phone für SSB, AM und FM,
  Digital für FT8, RTTY und alles andere. Ein Gebiet kann in CW gesucht sein und
  in FT8 nicht. Stehen auf einer Karte ([Kapitel 5](#abschnitt-5)) QSOs in
  verschiedenen Modes, zählt der beste Platz. **Mixed** misst alle QSOs an der
  Mixed-Liste. **CW**, **Phone** oder **Digital** zählen dagegen **nur** QSOs in
  dieser Betriebsart — ein SSB-QSO bestätigt kein gesuchtes CW-Gebiet.

Ist der Filter an, muss eine Karte **beides** erfüllen: einen aktiven Zustellweg
haben und unter den ersten Plätzen liegen. Alles andere steht in der Vorschau auf
„Drucken: Nein" ([Kapitel 9](#abschnitt-9)), wo du einzelne Karten trotzdem von
Hand einschalten kannst.

**Woher kennt das Programm das DXCC-Gebiet?** In dieser Reihenfolge:

1. Schreibt dein Log-Programm das ADIF-Feld `DXCC`, gilt das.
2. Sonst leitet das Programm das Gebiet aus dem Rufzeichen ab — über die
   `cty.dat` von AD1C ([country-files.com](https://www.country-files.com/)),
   die auch Contest-Logger wie QARTest oder N1MM benutzen. Sie kennt neben den
   Präfixen auch die Sonderrufzeichen von DXpeditionen. Das klappt **ohne
   Internet und ohne Zugangsdaten** und auch für ein Cabrillo-Log, das kein
   DXCC-Feld hat.
3. Kennt auch die `cty.dat` das Rufzeichen nicht, hilft der Lookup ([Kapitel
   6](#abschnitt-6)), falls du Zugangsdaten eingetragen hast.

**Eine Karte ohne bekanntes Gebiet wird bei eingeschaltetem Filter nicht
gedruckt**; in der Vorschau steht dann `?` in der Spalte „MW". `/MM` (auf See)
und `/AM` (in der Luft) zählen für kein Gebiet.

Die Liste holt das Programm **selbst**, sobald du den Filter einschaltest, und
merkt sie sich in der Datei `mostwanted.json`. Nach 30 Tagen fragt es beim
nächsten Einschalten bzw. Programmstart neu bei der GDXF nach. Die `cty.dat`
bringt das Programm mit; eine neuere holt es nach 14 Tagen auf dieselbe Weise.
Solange geladen wird, kannst du noch keine Karten erzeugen. Rechts in der Zeile
steht, welcher Jahrgang der GDXF-Liste gilt und wann er abgerufen wurde.

Ist die GDXF-Seite nicht erreichbar, gilt die zuletzt gespeicherte Liste weiter
(rechts steht dann „Abruf fehlgeschlagen").
Gibt es noch gar keine, steht dort „GDXF-Liste nicht abrufbar" und **keine**
Karte ist zum Drucken markiert — schalte den Filter dann aus oder versuche es
später noch einmal (Filter aus- und wieder einschalten).

## 8. Bemerkungen {#abschnitt-8}

Der Text unter **Text für alle Karten** erscheint auf jeder Karte im
REMARKS-Kasten, zum Beispiel „Vielen Dank für das nette QSO im 40-m-Band".

- Maximal **80 Zeichen**. Ein gewöhnlicher Satz dieser Länge passt in die Zeile;
  wird er breiter, druckt das Programm ihn kleiner, statt ihn abzuschneiden.
- Lässt du das Feld leer, gibt es keinen Kasten und es passen wieder 6 QSOs auf
  eine Karte statt 3 ([Kapitel 5](#abschnitt-5)) — außer der DARC-QR-Code ist an
  ([Kapitel 10](#abschnitt-10)), der braucht denselben Platz.
- Der Text wird übernommen, sobald du das Feld verlässt oder Enter drückst.
- In der Vorschau kannst du die Bemerkung **je Karte** überschreiben. Änderst du
  danach den globalen Text, fragt das Programm nach, ob es die von Hand
  gesetzten Bemerkungen überschreiben soll.

## 9. Vorschau {#abschnitt-9}

Die Tabelle zeigt jede Karte, die erzeugt werden würde. Hier korrigierst du
Einzelfälle, bevor gedruckt wird.

Die Spalten:

- **Drucken** — `Ja` oder `Nein`. Zeilen auf „Nein" sind ausgegraut und landen
  nicht in der PDF.
- **Call** — das Rufzeichen der Gegenstation.
- **MW** — der Platz des DXCC-Gebiets in der Most-Wanted-Liste
  ([Kapitel 7](#abschnitt-7)), in der dort gewählten Kategorie. `?` heißt: das
  Gebiet ist unbekannt, `–`: es hat keinen Platz in der Liste. Leer, solange
  noch keine Liste geladen ist.
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
„Drucken: Ja" gesetzt — außer der Most-Wanted-Filter ([Kapitel 7](#abschnitt-7))
schließt sie aus.

Steht in Via und Route noch `…`, läuft der Lookup — dann ist nichts änderbar,
warte kurz.

**Schon gesendete anzeigen** (oben in der Vorschau, mit Anzahl) blendet QSOs
ein, für die schon eine Papier-QSL gesendet wurde — für einen bewussten
Nachdruck. Sie stehen als eigene Karten auf „Nein"; hake an, was du nachdrucken
willst.

Alle Korrekturen hier gelten **nur für diese Sitzung**. „Log laden" oder „Neu
abrufen" bauen die Liste neu auf und verwerfen sie.

## 10. Druckmodus {#abschnitt-10}

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

**DARC-QR-Code auf die Rückseite** druckt rechts unten auf jede Karte einen
QR-Code von 2 × 2 cm. Er enthält dein Rufzeichen, den Manager (falls vorhanden),
den Empfänger und je QSO Datum, Uhrzeit, Band, Mode, Rapport und PSE/TNX — im
Format, das die DARC-QSL-Vermittlung maschinell lesen kann. Der Code braucht den
Platz unter der Tabelle: Ist er an, passen höchstens **3 QSOs** auf eine Karte
(wie mit Bemerkung), weitere QSOs mit derselben Station kommen auf Folgekarten.
REMARKS-Kasten und Fußtext werden dafür etwas schmaler.

Gut zu wissen: Karten mit QR-Code werden derzeit nur **innerhalb Deutschlands**
maschinell vermittelt und sollen beim DARC-Büro **getrennt sortiert** abgegeben
werden. Frag im Zweifel bei der QSL-Vermittlung nach.

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

## 11. Ausgabe {#abschnitt-11}

Mit **Ziel…** wählst du, wohin die PDF geschrieben wird; voreingestellt ist
`qsl_karten.pdf` in deinem Dokumentenordner. Dann **PDF erzeugen** — der Balken
zeigt den Fortschritt.

Die Checkbox **Adress-/Label-Export erzeugen** darüber legt zusätzlich eine
CSV-Datei mit den Anschriften an, die der Lookup gefunden hat
([Kapitel 6](#abschnitt-6)) — praktisch für Adressetiketten beim Direktversand.
Sie landet neben der PDF und enthält genau die Stationen, deren Karten auch
gedruckt werden (Spalte **Drucken: Ja**); Stationen ohne gefundene Anschrift
stehen nicht darin.

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

Fertige Fassungen gibt es auf
[github.com/da6ic/qsl-card-generator/releases](https://github.com/da6ic/qsl-card-generator/releases).

**Windows** — den Installer `…-windows-x64-setup.exe` herunterladen und per
Doppelklick starten. Er braucht keine Adminrechte, legt einen Eintrag im
Startmenü an und lässt sich unter *Einstellungen ▸ Apps* wieder entfernen.
Eine neue Fassung installierst du einfach darüber, deine Einstellungen
bleiben. Beim ersten
Start meldet Windows „Der Computer wurde durch Windows geschützt" — das
Programm ist nicht signiert. Über *Weitere Informationen* ▸ *Trotzdem
ausführen* geht es weiter.

**macOS** — die `.dmg` öffnen und die App auf „Programme" ziehen (oder das ZIP
entpacken und die App dorthin legen, wo du sie haben willst). Beim ersten Start
verweigert macOS den Start: die App ist signiert, aber nicht bei Apple
registriert. Der Weg daran vorbei hängt an der Version — auf **macOS 15 und
neuer** klickst du die Meldung weg und erlaubst den Start unter
*Systemeinstellungen ▸ Datenschutz & Sicherheit* mit *Dennoch öffnen*; auf
**macOS 14 und älter** genügt einmal **Rechtsklick ▸ Öffnen** statt
Doppelklick. Danach reicht der Doppelklick.

**Debian und Ubuntu** — über die Paketquelle, dann kommen neue Fassungen mit
dem normalen Systemupdate. Die Befehle zum Einrichten stehen auf
[da6ic.github.io/qsl-card-generator](https://da6ic.github.io/qsl-card-generator/);
danach genügt `sudo apt install qsl-karten-generator`. Entfernen mit
`sudo apt remove qsl-karten-generator`.

**Fedora** — genauso: die Paketquelle von derselben Seite einrichten, dann
`sudo dnf install qsl-karten-generator`. Entfernen mit
`sudo dnf remove qsl-karten-generator`.

**Andere Linux-Systeme** — das AppImage herunterladen, mit
`chmod +x QSL-Karten-Generator-*.AppImage` ausführbar machen und starten. Oder
das `tar.gz`: `tar xzf QSL-Karten-Generator-*.tar.gz`, dann im entpackten
Ordner `./install.sh`. Das legt das Programm nach `~/.local/opt` und trägt es
ins Anwendungsmenü ein, ohne `sudo`. Entfernen mit `./install.sh --uninstall`.

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

Darin liegen bis zu sieben Dateien:

- `config.yaml` — alle deine Einstellungen. Das Programm schreibt sie bei jeder
  Änderung selbst; bearbeite sie nicht von Hand, sonst überschreibt der nächste
  Klick deine Änderung. Zum Sichern oder Umziehen auf einen neuen Rechner
  kopierst du einfach diese eine Datei. Die Zugangsdaten für die Lookups stehen
  **nicht** darin ([Kapitel 6](#abschnitt-6)) — die gibst du auf dem neuen
  Rechner einmal neu ein. Bei jedem Speichern bleibt die vorige Fassung als
  `config.yaml.bak` liegen. Ist die `config.yaml` einmal beschädigt (Absturz,
  Stromausfall), lädt das Programm diese Sicherung, sagt es dir und legt die
  kaputte Datei als `config.yaml.defekt` daneben.
- `lookup_cache.json` — die gemerkten Antworten der Lookups
  ([Kapitel 6](#abschnitt-6)).
- `mostwanted.json` — die zuletzt abgerufene Most-Wanted-Liste der GDXF
  ([Kapitel 7](#abschnitt-7)). Sie entsteht erst, wenn du den Filter einmal
  einschaltest.
- `cty.dat` — die zuletzt abgerufene Präfixliste von AD1C, mit der das Programm
  Rufzeichen ihrem DXCC-Gebiet zuordnet ([Kapitel 7](#abschnitt-7)). Fehlt sie,
  gilt die mitgelieferte.
- `wavelog_sent.json` — nur mit Wavelog: die QSOs, die das Programm dort
  selbst als gesendet markiert hat, und noch offene Markierungen.
- `qslcards.log` — das Protokoll. Klemmt etwas, steht hier der Grund.
  Zugangsdaten stehen darin nie.

Die fertigen PDFs landen dort, wo du sie in [Abschnitt 11](#abschnitt-11)
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

**„Pflichtangaben fehlen"** — es fehlt eine der mit `*` markierten Angaben. Die
Leiste unten nennt alle auf einmal, die Stellen sind rot markiert und der
Assistent springt zur ersten davon.

**„Einstellungen beschädigt"** — die `config.yaml` war nicht lesbar (meist ein
Absturz beim Speichern). Das Programm hat die letzte Sicherung geladen; die
kaputte Datei liegt als `config.yaml.defekt` daneben ([Dateien](#dateien)).

**„Logbuch nicht verwertbar"** — die Datei ist weder ADIF noch Cabrillo.
Hast du vielleicht eine Auswertung oder eine Tabelle erwischt statt der
Logdatei selbst? Ein ADIF-Log enthält Einträge wie `<CALL:5>`, ein Cabrillo-Log
beginnt mit `START-OF-LOG:` ([Kapitel 1](#abschnitt-1)).

**Die Spalte SIGNAL REPORT bleibt leer** — bei einem Contest-Log ist das normal:
viele Contests tauschen gar keinen Rapport aus ([Kapitel 1](#abschnitt-1)).

**„PDF erzeugen" reagiert nicht** — läuft noch der Lookup oder lädt die
Most-Wanted-Liste? Solange ist der Knopf gesperrt. Der Status unten im Fenster
bzw. in Abschnitt 7 sagt, wie weit es ist.

**Eine Station fehlt in der Kartenliste** — sie nimmt keinen der aktiven
Zustellwege an ([Kapitel 4](#abschnitt-4)). Zieh die Trennlinie tiefer oder
setze die Karte in der Vorschau von Hand auf „Drucken: Ja". Ist der
Most-Wanted-Filter an ([Kapitel 7](#abschnitt-7)), liegt ihr Gebiet vielleicht
nicht unter den ersten Plätzen — oder es ist unbekannt (`?` in der Spalte „MW").

**Alle Karten stehen auf Büro** — dann gibt es keine Lookup-Zugangsdaten oder
die Abfrage ist fehlgeschlagen. Prüfe [Abschnitt 6](#abschnitt-6). Nach jedem
Programmstart sind die vier Felder leer, außer du hast **Im Schlüsselbund
merken** angehakt.

**Der Manager stimmt nicht** — die Datenbank ist nicht immer aktuell. Korrigiere
das Feld „Route/Manager" in der Vorschau, oder leere den Cache und frage neu ab.

**Die Ränder im Ausdruck stimmen nicht** — fast immer die Skalierung im
Druckdialog; sie muss auf 100 % / „keine Anpassung" stehen ([Kapitel
10](#abschnitt-10)).

**Etwas anderes klemmt** — dann schau ins Protokoll: **Hilfe ▸ Protokoll
anzeigen** ([Wo liegen meine Dateien?](#dateien)). Dort notiert das Programm,
was es nicht geschafft hat. Die letzten Zeilen sind die interessanten.
