<!-- translated from en/troubleshooting.md at a79f1873e7d6 -->
# Ko gre kaj narobe

Hrček vsako težavo sporoči s kodo, na primer `HRC-CORE-0003`, skupaj z
opisom v vašem jeziku. Opis se med različicami lahko preoblikuje; **koda
nikoli ne spremeni pomena**, zato ob prošnji za pomoč navedite kodo.

Napaka je videti takole:

```json
{
  "error": {
    "code": "HRC-CORE-0003",
    "message": "Zahtevani vir ne obstaja.",
    "details": {}
  }
}
```

## Kaj pomenijo kode

| Koda | Kaj se je zgodilo | Kaj storiti |
|---|---|---|
| `HRC-CORE-0001` | V Hrčku je šlo nekaj narobe. | Ni vaša krivda. Sporočite to, s kodo, časom in tem, kar ste počeli. |
| `HRC-CORE-0002` | Poslani podatki niso bili veljavni. | Preverite, kaj ste vpisali. `details` navede napačna polja. |
| `HRC-CORE-0003` | Stvar, ki ste jo zahtevali, ne obstaja. | Preverite naslov ali identifikator. Morda je bila tudi izbrisana. |
| `HRC-AUTH-0001` | E-poštni naslov ali geslo ni bilo sprejeto. | Preverite oboje. Hrček da enak odgovor za onemogočen račun, zato vprašajte upravljavca, če ste prepričani, da sta pravilna. |
| `HRC-AUTH-0002` | Vaš e-poštni naslov še ni potrjen. | Sledite povezavi v e-poštnem sporočilu s potrditvijo. Če je potekla, se znova registrirajte za novo. |
| `HRC-AUTH-0003` | Prijavljeni morate biti. | Prijavite se in poskusite znova. |
| `HRC-AUTH-0004` | Uporabljeni API-žeton ni veljaven. | Morda je bil preklican ali je potekel. Prosite za novega. |
| `HRC-AUTH-0005` | Zahteve ni bilo mogoče preveriti. | Običajno zastarela stran. Naložite jo znova in poskusite znova. |
| `HRC-ACCT-0001` | S tem naslovom tu ni mogoče ustvariti računa. | Prosite za povabilo ali za dovoljenje za svoj naslov. |
| `HRC-ACCT-0002` | Povezava v povabilu ni uporabna. | Potekla je, bila je že uporabljena ali umaknjena. Prosite za novo povabilo. |
| `HRC-ACCT-0003` | Povezava za potrditev ni uporabna. | Najverjetneje je potekla. Znova se registrirajte, da dobite novo. |
| `HRC-ACCT-0004` | To prikazno ime je zasedeno. | Izberite drugo. Velike črke ga ne naredijo drugačnega. |

## Prijava težave

Navedite kodo napake, približno kdaj se je zgodila in kaj ste počeli.
Če vidite glave odgovora, navedite tudi `X-Request-ID` — ta kaže
naravnost na ustrezen zapis v dnevnikih.
