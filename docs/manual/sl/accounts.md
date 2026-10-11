<!-- translated from en/accounts.md at 59d98762f35a -->
# Vaš račun

Hrček vodi majhno število računov, enega na osebo. Ta stran pojasni,
kako pridete do računa in kako se vanj vrnete, ko gre kaj narobe.

## Kako do računa

Poti sta dve.

**Nekdo vas povabi.** Kdor skrbi za ta Hrček, pošlje povabilo na vaš
e-poštni naslov. Odprite povezavo v njem, izberite geslo in končali
ste — že to, da ste sledili povezavi, dokazuje, da je naslov vaš, zato
ni treba potrditi ničesar drugega.

Povezave v povabilih potečejo, privzeto po enem tednu. Če je vaša
potekla, prosite za novo; stare povezave ni mogoče oživiti.

**Registrirate se sami.** Pojdite na `/accounts/signup/` in vpišite
e-poštni naslov in geslo. To deluje samo, če je vaš naslov vnaprej
dovoljen, posamično ali zato, ker je dovoljena vsa vaša e-poštna
domena. Če ni, vam to povemo, pot naprej pa je povabilo.

Stran za prijavo pokaže povezavo za registracijo, kadar se sme sam
registrirati sploh kdorkoli. Če ne sme nihče, povezave ni, saj bi vodila
samo do obrazca, ki bi vas zavrnil.

Po registraciji prejmete e-poštno sporočilo s potrditvijo. **Dokler ne
sledite tej povezavi, se ne morete prijaviti.** Poteče po dveh dneh.

## Vaše prikazno ime

Prikazno ime ni obvezno. Če ga nastavite, se lahko z njim prijavite
namesto z e-poštnim naslovom, ki ga je dlje tipkati.

Dve pravili:

- Ne sme vsebovati `@`. Hrček ob prijavi sprejme kateregakoli od obeh,
  z `@` pa prikaznega imena ne bi bilo mogoče ločiti od e-poštnega
  naslova.
- Velike črke ne štejejo. Če je nekdo že `Nina`, vi ne morete biti
  `nina`.

Lahko ga pustite praznega, in to lahko stori poljubno veliko ljudi.

## Upravljanje računa

Ko ste prijavljeni, je `/accounts/me/` mesto za vse v zvezi z vašim
računom, v treh delih: *Profil*, *Prijava* ter *Polja in odjemalci*. Z
JavaScriptom so to zavihki, med katerimi preklapljate; brez njega so
preprosto razdelki ene dolge strani, drug za drugim.

Z JavaScriptom shranjevanje obrazca tam ne naloži strani znova: del, v
katerem ste delali, se posodobi na mestu, ostanete na istem zavihku,
obvestilo nad stranjo pa pove, kaj je bilo shranjeno. Če je treba kaj
popraviti, obrazec to pove ob polju in vas postavi vanj. Če shranjevanje
sploh ne uspe, se nad stranjo pokaže napaka »Nekaj je šlo narobe.
Preverite in poskusite znova.« in nič se ne spremeni.

**Prikazno ime.** Spremenite ga ali počistite, kadar želite. Pravila so
enaka kot ob prvi nastavitvi: brez `@`, velike črke pa ga ne naredijo
drugačnega od imena nekoga drugega.

**E-poštni naslov.** Sprememba zahteva vaše trenutno geslo, nato pa
pošlje povezavo za potrditev na *novi* naslov.

Tri stvari je dobro vedeti:

- **Stari naslov deluje, dokler ne sledite tej povezavi.** Še vedno se
  lahko prijavite in ponastavite geslo z naslovom, ki ste ga uporabljali
  doslej. Do potrditve se nič ne spremeni.
- **Na stari naslov pride obvestilo**, takoj ko je sprememba zahtevana.
  Če je niste zahtevali vi, poskuša nekdo drug premakniti vaš račun —
  prijavite se in jo prekličite, dokler stari naslov še deluje.
- Nova zahteva nadomesti prejšnjo, prejšnja povezava pa neha delovati.

Dokler naslov čaka na potrditev, je ob njem gumb za preklic.

**Polja.** Povezava na vaša polja, dodatke, ki jih beležite o vsakem
vnosu. Glejte [polja](entries.md#polja).

**Geslo.** Tu je povezava za spremembo. Vprašani boste za trenutno
geslo, potem pa ostanete prijavljeni.

## Odjemalci in API-žetoni

Odjemalec je skripta ali drug program, ki deluje v vašem imenu brez
brskalnika in brez vašega gesla. Vsak odjemalec se izkaže z API-žetonom.

Žetoni imajo svojo stran: na strani računa sledite povezavi *Upravljajte
odjemalce in njihova pooblastila*. Tam ustvarite žeton in mu dajte ime,
ki ga boste pozneje prepoznali. **Žeton se pokaže enkrat in nikoli
več** — kopirajte ga, preden zapustite stran. Shrani se samo njegov
prstni odtis, zato vam ga pozneje nihče, niti tisti, ki upravlja ta
Hrček, ne more poiskati.

Program si lahko žeton ustvari tudi sam, kar prihrani ročno lepljenje ob
nastavitvi: enkrat vpraša za vaš e-poštni naslov in geslo, ju zamenja za
žeton in obdrži samo žeton. Tako deluje razširitev za brskalnik. Vašega
gesla ne bi smel nikoli shraniti — če program želi obdržati geslo
namesto žetona, je to vredno vprašati. To je podrobnost za tistega, ki
program piše; opisana je v dokumentaciji za razvijalce.

Izbrišite žeton in takoj neha delovati; to storite, če mislite, da je
ušel v javnost. Brisanja ni mogoče razveljaviti; ustvarite novega.

## Prijava

Uporabite e-poštni naslov ali prikazno ime, skupaj z geslom. Velike črke
pri nobenem od njiju niso pomembne.

Če vam Hrček sporoči, da so podatki napačni, čeprav ste prepričani, da
niso, je vredno preveriti dvoje: ali ste kdaj sledili povezavi za
potrditev in ali je bil vaš račun onemogočen. Hrček za napačno geslo
namenoma da enak odgovor kot za onemogočen račun, zato vam ne more
povedati, za katero od obeh gre — vprašajte tistega, ki ga upravlja.

## Pozabljeno geslo

Pojdite na `/accounts/password/reset/` in vpišite e-poštni naslov. Če
zanj obstaja račun, prispe povezava; če ne, vseeno dobite isto stran,
tako da nihče ne more s tem obrazcem ugotoviti, kdo ima tu račun.

Povezava deluje enkrat. Ko nastavite novo geslo, neha delovati, zato
za vsako naslednjo spremembo prosite za novo povezavo.

## Ko gre kaj narobe

Vsaka napaka ima kodo, na primer `HRC-ACCT-0002`. Besedilo se med
različicami lahko spremeni, koda pa ne. Navedite jo, ko prosite za
pomoč — glejte [ko gre kaj narobe](troubleshooting.md).
