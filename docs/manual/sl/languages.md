<!-- translated from en/languages.md at 3d2662cc5dd9 -->
# Jeziki

Hrček govori angleško in slovensko. Privzeto uporabi jezik, ki ga
zahteva vaš brskalnik ali aplikacija, to izbiro pa lahko preglasite na
kateri koli strani.

## Izbira jezika

Na dnu vsake strani sta navedena oba jezika: tisti, ki je v rabi, kot
navadno besedilo, drugi kot povezava. Izberite enega in Hrček ostane pri
njem — v tem brskalniku — dokler ne izberete znova, ne glede na jezikovne
nastavitve brskalnika. Za to vam ni treba biti prijavljeni.

## Kako se jezik izbere sicer

Če jezika niste nikoli izbrali, vsaka zahteva nosi jezike, ki jih imate
raje, po vrsti, Hrček pa odgovori v prvem, ki ga pozna, sicer pa v
angleščini. Če spremenite prednostni jezik brskalnika ali telefona, se
spremenijo tudi Hrčkovi odgovori.

## Če odgovor pride v napačnem jeziku

Najprej poglejte na dno strani — če je bil jezik izbran tam, ima
prednost. Sicer preverite jezikovne nastavitve brskalnika. Če ima
slovenščina prednost na obeh mestih, odgovori pa še vedno prihajajo v
angleščini, je to napaka, ki jo je vredno prijaviti.

## Neposredna zahteva za jezik

Če Hrček kličete iz skripte:

```bash
curl -H "Accept-Language: sl" http://localhost:8000/api/health
```
