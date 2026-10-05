# Blink Cull (română)

**Plugin pentru Lightroom Classic** care găsește pozele cu ochi închiși din fișierele tale Sony ARW, în câteva minute, pe calculatorul tău.
Versiunea în engleză, cu toate detaliile: [README.md](README.md).

Selectezi pozele în Lightroom, rulezi o comandă din meniu, iar pozele suspecte primesc **etichetă roșie sau galbenă, un cuvânt cheie și o colecție**
pe care le parcurgi direct în grilă. Este un **ajutor la sortare**, nu un înlocuitor al verificării tale.

> Stare: timpurie / experimentală. Detecția a fost construită și măsurată pe o singură nuntă (1363 de poze Sony a7 IV), etichetată de o singură persoană.
> Partea din Lightroom (etichete, cuvinte cheie, colecții) a fost puțin testată în practică, așa că spune-mi ce vezi.

- **Privat:** nimic nu iese din calculatorul tău. Fără cloud, fără cont, fără acces la rețea.
- **Doar citire:** fișierele RAW nu sunt modificate niciodată. Plugin-ul nu respinge și nu șterge poze: doar adaugă etichete, cuvinte cheie și colecții.
- **Rapid:** ~0.3 secunde pe poză pe un Mac cu procesor Apple (~6 minute la 1400 de poze), cu bară de progres și buton de anulare.
- **Fără aplicație separată:** motorul de analiză vine în folderul plugin-ului.

## Cât de bun este (măsurat pe acea nuntă)

| Scor ≥ | Poze de revăzut | Chiar închise | Precizie | Recall estimat | Față de alegerea la întâmplare |
|---|---|---|---|---|---|
| 0.55 | 97 | 93 | 96% | ~21% | 2.9× |
| **0.45** (roșu) | 197 | 171 | **87%** | ~38% | 2.6× |
| 0.35 | 353 | 258 | 73% | ~57% | 2.2× |
| **0.25** (roșu + galben) | 594 | 336 | 57% | **~74%** (65–82%) | 1.7× |

În acea nuntă ~1 poză din 3 avea pe cineva cu ochii închiși (fotograful a numărat și clipirile parțiale și privitul în jos). Roșul e corect în 87% din cazuri,
dar chiar dacă revezi toate pozele marcate, găsești aproximativ trei sferturi din probleme. Puncte slabe: profiluri, îmbrățișări, privit în jos.

## Instalare

Ai nevoie de Lightroom Classic și, deocamdată, de un Mac cu procesor Apple (acolo a fost construit motorul).

1. Obține folderul `BlinkCull.lrdevplugin` **cu motorul în el** (`bin/BlinkCullEngine/`): fie descarci un release (când va exista), fie îl construiești:
   `git clone https://github.com/tranteagratian/blink-cull && cd blink-cull && ./scripts/build_engine.sh` (Python 3.12 și [uv](https://docs.astral.sh/uv/)).
2. Lightroom Classic ▸ *File ▸ Plug-in Manager… ▸ Add* ▸ alegi `lightroom/BlinkCull.lrdevplugin`.
3. Dacă macOS blochează motorul (nu e semnat), rulezi o dată `xattr -dr com.apple.quarantine lightroom/BlinkCull.lrdevplugin`.

## Folosire

În modulul Library selectezi pozele (un folder, apoi Cmd+A) ▸ *Library ▸ Plug-in Extras ▸ Find photos with closed eyes (selected photos)*.
Alegi pragurile (implicit 0.45 roșu, 0.25 galben) și opțiunile, apoi *Analizează*. Primești un rezumat, etichete roșu/galben, cuvintele cheie
`blinkcull-closed` / `blinkcull-check` și două colecții. Fereastra există în engleză și română.

## Limite

- Puncte slabe: fețe de profil, îmbrățișări, privit în jos; fețele neclare sau foarte întunecate sunt sărite.
- **O singură galerie, un singur etichetator:** pragurile pot trebui ajustate la alte evenimente, aparate sau lumină.
- Doar **Sony ARW**, doar **Lightroom Classic**, motor construit doar pentru **macOS Apple silicon**.
- **Nu pune niciodată poze cu oameni reali, RAW-uri sau fișiere cu etichete în repo sau în issue-uri.**

## Licență

Apache-2.0, vezi [LICENSE](LICENSE). Componentele terțe își păstrează licențele, vezi [NOTICE](NOTICE).
