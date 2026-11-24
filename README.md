# Setinrakentaja

Työpöytäsovellus Rekordbox-soittolistojen kokoamiseen. Suodata kirjastoa BPM:n,
sävellajin, genren, tähtien, värin, My Tagien, päivämäärien, pituuden ja
toistokertojen mukaan. Järjestä lista harmoniseksi setiksi tai energiakaareksi ja vie
valmiit soittolistat (kansioineen) uutena `rekordbox.xml`-tiedostona Rekordboxiin.

**Turvallisuus:**

- Sovellus **ei koskaan kirjoita** Rekordboxin tietokantaan (`master.db`).
- Se lukee vain Rekordboxin XML-viennin ja tallentaa aina **uuden** tiedoston.
- Alkuperäisen XML-tiedoston päälle kirjoittaminen on estetty.
- Kappaleiden `TRACK`-tiedot (myös `Location`-tiedostopolut, beatgrid ja cue-pisteet)
  kopioidaan vientiin muuttumattomina, jotta Rekordbox tunnistaa kappaleet.

---

## 1. Asennus (macOS)

### A) Valmis sovellus (helpoin)

1. Avaa https://github.com/markusket/DJ-setset/actions ja valitse uusin vihreä (✓)
   **Rakenna macOS-sovellus** -ajo. Sinun on oltava kirjautuneena GitHubiin.
2. Lataa sivun alaosan **Artifacts**-kohdasta `Setinrakentaja-macOS`. Purkaminen voi
   vaatia kaksi kertaa: ensin ladattu zip ja sen sisältä `Setinrakentaja-macOS.zip`.
3. Siirrä `Setinrakentaja.app` Ohjelmat-kansioon (Applications).
4. **Ensimmäinen avaus:** sovellusta ei ole allekirjoitettu Applen kehittäjätunnuksella,
   joten macOS estää sen aluksi. Avaa se näin:
   - Kaksoisnapsauta sovellusta ja sulje varoitus.
   - Avaa **Järjestelmäasetukset > Tietosuoja ja turvallisuus**. Selaa alas ja valitse
     **Avaa silti** (Open Anyway) Setinrakentajan kohdalla.
   - Jos macOS sanoo, että sovellus on vahingoittunut, aja Päätteessä:
     `xattr -dr com.apple.quarantine /Applications/Setinrakentaja.app`

Valmis sovellus on rakennettu Apple Silicon -koneille (M1–M4). Intel-Macilla rakenna
sovellus itse (kohta B).

### B) Rakenna itse

Tarvitset Python 3.10 tai uudemman. Tarkista versio Päätteessä komennolla
`python3 --version`. Pythonin saa osoitteesta python.org tai Homebrew'lla
(`brew install python`).

```bash
git clone https://github.com/markusket/DJ-setset.git
cd DJ-setset
./build_mac.sh
```

Skripti tekee kolme asiaa:

1. Luo virtuaaliympäristön (`.venv`) ja asentaa riippuvuudet.
2. Ajaa testit.
3. Rakentaa sovelluksen `dist/Setinrakentaja.app`.

### C) Käynnistys suoraan Pythonilla (kehitys)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m setinrakentaja            # tai: python run_setinrakentaja.py
python -m pytest                    # testit
```

---

## 2. Kirjaston vienti Rekordboxista (XML)

1. Avaa Rekordbox 7.
2. Valitse **File > Export Collection in xml format**
   (Tiedosto > Vie kokoelma XML-muodossa).
3. Tallenna tiedosto esim. nimellä `rekordbox_kirjasto.xml`.
4. Avaa Setinrakentajassa **Tiedosto > Avaa kirjasto** ja valitse tiedosto.
   Sovellus muistaa viimeksi avatun kirjaston.

Kun kirjastosi muuttuu, vie XML uudelleen samaan tiedostoon ja valitse Setinrakentajassa
**Tiedosto > Lataa kirjasto uudelleen** (⌘R). Vientijonossa olevat listat luodaan
silloin automaattisesti uudelleen resepteistään.

### My Tagit

Rekordboxin XML-vienti **ei sisällä My Tageja** sellaisenaan. Saat ne mukaan näin:

- Ota Rekordboxin My Tag -asetuksista käyttöön valinta, joka lisää My Tagit
  kappaleen kommenttiin (englanniksi *Add My Tag to Comments*). Valinnan tarkka
  paikka vaihtelee Rekordbox-versioittain. Rekordbox kirjoittaa tagit kommenttiin
  muodossa `/* Peak Time / Vocal */`, ja Setinrakentaja tunnistaa ne.
- Vaihtoehtoisesti voit kirjoittaa kommenttiin #hashtageja, esim. `#warmup #vocal`.
  Nekin näkyvät sovelluksessa My Tageina.

Jos tagit eivät näy sovelluksen My Tag -listassa, tarkista, missä muodossa ne näkyvät
kappaleen kommentissa. Muodon voi tarvittaessa lisätä sovellukseen.

### Energiamerkinnät (valinnainen)

Energiakaari käyttää kappaleen energiaa asteikolla 1–10:

- Jos kappaleen kommentissa tai My Tageissa on merkintä `Energy 7`, `Energia 7` tai
  `E7`, käytetään sitä. Esikatselussa merkinnän perusteella saatu energia näkyy
  tähdellä, esim. `7.0*`.
- Muuten energia arvioidaan BPM:stä (75 %) suhteessa listan tempoalueeseen ja
  tähtiarviosta (25 %).

---

## 3. Soittolistan kokoaminen

Sovelluksen vasemmassa reunassa ovat suodattimet ja oikeassa reunassa kappalelistan
esikatselu.

| Suodatin | Selitys |
|---|---|
| BPM | Väli, esim. 122–128. Valinnalla *puolikas / tupla-tempo* esim. 64 BPM:n kappale kelpaa väliin 122–130. |
| Sävellaji | Camelot-pyörän napit (8A = Am). *Myös yhteensopivat* lisää viereiset (±1) ja rinnakkaissävellajin (A↔B). *Laajennettu* lisää myös +2:n ja diagonaalit. Kirjasto voi käyttää kumpaa tahansa merkintää (8A tai Am); sovellus tunnistaa molemmat. |
| Genre | *Sisällytä*-välilehdellä valitut genret otetaan mukaan, *Poissulje*-välilehdellä valitut jätetään pois. |
| Arvio ja väri | Tähtien vähimmäis- ja enimmäismäärä. Rekordboxin värit sisällytettävinä tai poissuljettavina. |
| My Tag ja kommentti | Tagit (*jokin* tai *kaikki* valituista), sekä sanat, joita kommentissa on tai ei ole. |
| Vuosi, lisäyspäivä | Julkaisuvuosiväli, lisäyspäivän väli tai *viimeiset N päivää*. |
| Pituus, toistot | Kappaleen pituus minuutteina. Toistokerrat, esim. enintään 2 = vähän soitetut. |
| Tekstihaku | Hakee artistista, nimestä, albumista, remixeristä ja levy-yhtiöstä. *Ei sisällä* -kentän mikä tahansa sana sulkee kappaleen pois. |

**Viiva (—) kentässä tarkoittaa, ettei rajausta ole.**

### Järjestys

- **BPM, sävellaji, arvio, lisäyspäivä, vuosi, artisti, nimi, toistot**: tavallinen
  järjestys. *Laskeva järjestys* kääntää suunnan.
- **Harmoninen setti**: peräkkäiset kappaleet valitaan niin, että ne ovat
  Camelot-pyörällä yhteensopivia ja BPM nousee, laskee tai pysyy tasaisena valintasi
  mukaan.
- **Energiakaari**: anna energian alku-, huippu- ja lopputaso sekä huipun kohta
  (esim. 70 % setistä). Valinta *Suosi harmonisia siirtymiä* ottaa samalla huomioon
  sävellajit.
- **Kappalemäärä / kokonaiskesto**: lista rajataan haluttuun määrään tai kestoon.
  Harmonisessa setissä ja energiakaaressa kappaleet valitaan koko suodatetusta
  joukosta niin, että kaari toteutuu.

Paina **Luo lista ▶**.

Esikatselun *Siirtymä*-sarake näyttää, miten kappale sopii edelliseen:

- ✓ = yhteensopiva sävellaji
- ~ = kohtuullinen
- ✗ = riitasointu

Sarakkeessa näkyy myös BPM-muutos.

### Käsin muokkaus

- **Siirrä**: raahaa rivejä hiirellä tai käytä ▲/▼-nappeja (⌘↑ / ⌘↓).
- **Poista**: valitse rivit ja paina **Poista valitut** (tai Delete / ⌫).
  Poistetut kappaleet tallentuvat myös reseptiin, joten ne pysyvät poissa, kun listan
  luo uudelleen. **Palauta poistetut** tyhjentää poistolistan.
- **Järjestä sarakkeen mukaan**: klikkaa sarakeotsikkoa. Toinen klikkaus kääntää
  suunnan.

### Vientijono ja kansiot

1. Anna listalle **nimi** ja halutessasi **kansio**. Kansiot erotetaan
   kauttaviivalla, esim. `Keikat/2026 Joulu`.
2. Paina **Lisää vientijonoon**. Samanniminen lista samassa kansiossa korvataan.
3. Toista muille listoille.
4. Avaa jonossa oleva lista muokattavaksi tuplaklikkaamalla sitä.
5. Kun jono on valmis, valitse **Vie XML-tiedostoksi…** (⌘E). Kaikki listat
   tallentuvat yhteen uuteen tiedostoon kansiorakenteineen.

### Reseptit

Resepti on JSON-tiedosto, johon tallentuvat suodattimet, järjestys, rajaus, nimi,
kansio ja käsin poistetut kappaleet.

- **Resepti > Tallenna nykyinen resepti** (⌘S) ja **Avaa resepti**.
- **Resepti > Luo soittolistat resepteistä vientijonoon**: valitse useita
  reseptejä kerralla. Näin saat esim. kaikki "vakiolistasi" päivitettyä uusimmasta
  kirjastosta yhdellä kertaa.
- **Resepti > Tallenna vientijonon reseptit kansioon** tallentaa koko jonon
  reseptit kerralla.

Käsin tehty järjestys ei tallennu reseptiin. Resepti tuottaa listan aina
suodattimien ja järjestystavan mukaan.

Esimerkkireseptejä löytyy kansiosta `esimerkit/reseptit/`.

---

## 4. Soittolistojen tuonti Rekordboxiin

1. **Kytke XML-tiedosto Rekordboxiin:** avaa Rekordboxissa **Preferences >
   Advanced > Database > rekordbox xml** (Asetukset > Lisäasetukset > Tietokanta).
   Valitse kohdassa **Imported Library** **Browse** ja valitse Setinrakentajan
   viemä tiedosto.
2. **Näytä rekordbox xml -puu:** jos selaimen vasemmassa puussa ei näy kohtaa
   **rekordbox xml**, ota se käyttöön kohdasta **Preferences > View > Layout**
   (Tree View) valitsemalla *rekordbox xml*.
3. **Tuo listat:** avaa selaimessa **rekordbox xml > Playlists**. Napsauta haluamaasi
   listaa tai kansiota hiiren oikealla ja valitse **Import Playlist**
   (Tuo soittolista). Lista ilmestyy tavallisiin soittolistoihisi.
4. **Seuraavalla viennillä:** voit tallentaa uuden viennin samaan tiedostoon, jolloin
   Rekordboxin asetusta ei tarvitse vaihtaa. Päivitä näkymä napsauttamalla
   *rekordbox xml* -kohdan päivityskuvaketta.

Kappaleet tunnistetaan tiedostopolun (`Location`) perusteella. Koska polut kopioidaan
täsmälleen alkuperäisestä viennistä, Rekordbox yhdistää ne kokoelmasi olemassa
oleviin kappaleisiin, ja cue-pisteet, beatgridit ja muut tiedot säilyvät.

**Tärkeää:**

- Älä valitse *Imported Library* -kohtaan samaa tiedostoa, jota käytät
  Setinrakentajan kirjastona. Sovellus estää kirjoittamasta sen päälle, mutta selkeintä
  on pitää ne erillisinä, esim. `rekordbox_kirjasto.xml` (luettava) ja
  `setinrakentaja_vienti.xml` (tuotava).
- Jos olet siirtänyt musiikkitiedostoja XML-viennin jälkeen, vie kirjasto uudelleen
  ennen listojen tekemistä.

---

## 5. Tekninen rakenne

```
setinrakentaja/
  core/
    library.py      XML:n luku (vain luku), Track-malli, My Tag- ja energiamerkinnät
    keys.py         Camelot ↔ perinteinen, yhteensopivuus, siirtymän "hinta"
    filters.py      suodattimet
    sequencing.py   järjestykset, harmoninen setti, energiakaari, rajaukset
    exporter.py     rekordbox.xml-vienti (TRACK-elementit kopioina, kansiopuu)
    recipe.py       reseptit (JSON)
    builder.py      resepti -> soittolista
  ui/               PySide6-käyttöliittymä
tests/              pytest-testit ja esimerkkikirjasto (tests/data/esimerkki_rekordbox.xml)
```

Vientitiedoston rakenne vastaa Rekordboxin omaa XML-formaattia:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="7.0.4" Company="AlphaTheta"/>
  <COLLECTION Entries="2">
    <TRACK TrackID="..." Name="..." Location="file://localhost/Users/..." ...>
      <TEMPO .../> <POSITION_MARK .../>
    </TRACK>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="1">
      <NODE Type="0" Name="Keikat" Count="1">
        <NODE Name="Lämmittely" Type="1" KeyType="0" Entries="2">
          <TRACK Key="..."/>
```

Kokoelmaan (`COLLECTION`) tulevat vain ne kappaleet, jotka ovat vietävillä listoilla.
Soittolistat viittaavat niihin `TrackID`:llä (`KeyType="0"`).
