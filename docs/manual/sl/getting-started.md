<!-- translated from en/getting-started.md at 3c9b6bdc893b -->
# Prvi koraki

Hrček teče kot majhna spletna storitev na računalniku, ki ga nadzorujete
sami — domačem strežniku, odvečnem računalniku, majhnem VPS-ju. Kdor ga
je postavil, vam lahko pove njegov naslov; spodnji primeri predpostavljajo
`http://localhost:8000`.

## Ali deluje?

V brskalniku odprite `http://localhost:8000/`. Videti bi morali obrazec
za prijavo, nad njim pa Hrčkovega hrčka.

Če želite namesto prijave preveriti samo storitev, odprite
`http://localhost:8000/api/health`. Zdrava storitev odgovori:

```json
{
  "status": "ok",
  "service": "hrcek",
  "version": "0.2.0",
  "message": "Storitev deluje."
}
```

Če se stran sploh ne naloži, Hrček ne teče. Prosite tistega, ki skrbi
zanj, naj storitev zažene.

## Videz

Hrček sledi nastavitvi videza vaše naprave: svetel je, ko je svetel vaš
sistem, in temen, ko je temen vaš sistem.

Če bi raje imeli drugega, pritisnite sonce ali luno v zgornjem desnem
kotu katere koli strani. Pritisnite znova in Hrček spet sledi napravi.
Izbiro si zapomni samo ta brskalnik, zato druga naprava ali drug
brskalnik na isti napravi še naprej sledi svoji nastavitvi.

## Kako do računa

Brez računa vam Hrček ne koristi kaj dosti. Nekdo vas povabi ali pa se
registrirate sami, če je vaš naslov dovoljen. Glejte
[vaš račun](accounts.md).

## Kaj vse Hrček zna

`http://localhost:8000/api/docs` našteje vse razpoložljive operacije in
vam pusti, da vsako preizkusite kar v brskalniku. Tako najhitreje vidite,
kaj podpira trenutna različica.

Na produkcijskih namestitvah je ta stran izklopljena, zato na vaši morda
ni na voljo.
