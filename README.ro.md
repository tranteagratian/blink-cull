# Blink Cull (română)

Găsește pozele cu ochi închiși dintr-un folder de fișiere Sony ARW, în câteva minute, pe calculatorul tău.
Versiunea în engleză, cu toate detaliile: [README.md](README.md).

**Ce face:** citește JPEG-ul incorporat în fiecare ARW, găsește fețele, măsoară cât de închiși sunt ochii fiecărei persoane
și îți arată primele pozele suspecte. Este un **ajutor la sortare**, nu un înlocuitor al verificării tale.

- **Privat:** nimic nu iese din calculatorul tău. Fără cloud, fără cont.
- **Doar citire:** fișierele RAW nu sunt modificate sau șterse niciodată. Fișierele `.xmp` se scriu doar la cererea ta, implicit într-un folder separat.
- **Rapid:** ~0.3 secunde pe poză (~6 minute pentru 1400 de poze) pe un Mac cu procesor Apple.
- Trei moduri de folosire: **aplicație desktop**, **plugin Lightroom Classic** și **linie de comandă**.

## Cât de bun este (măsurat pe o singură nuntă, 1363 de poze, etichetate de fotograf)

| Pragul de scor | Poze de revăzut | Chiar închise | Precizie | Recall estimat | Față de alegerea la întâmplare |
|---|---|---|---|---|---|
| ≥ 0.55 | 97 | 93 | 96% | ~21% | 2.9× |
| **≥ 0.45** (grupa roșie) | 197 | 171 | **87%** | ~38% | 2.6× |
| ≥ 0.35 | 353 | 258 | 73% | ~57% | 2.2× |
| **≥ 0.25** (roșu + galben) | 594 | 336 | 57% | **~74%** (interval 65–82%) | 1.7× |

În acea nuntă, aproximativ **1 poză din 3** avea pe cineva cu ochii închiși (fotograful a numărat și clipirile parțiale și privitul în jos).
Grupa roșie e corectă în 87% din cazuri, dar chiar dacă revezi toate cele 594 de poze marcate, găsești aproximativ trei sferturi din probleme.
Profilurile, îmbrățișările și privitul în jos sunt punctele slabe. Explicații și analiza erorilor: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) (în engleză).

## Pornire rapidă (din sursă)

Ai nevoie de Python 3.12 și [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tranteagratian/blink-cull
cd blink-cull
uv sync
uv run python fetch_models.py     # descarcă două fișiere de model mici în ./models
uv run python app.py              # aplicația desktop
```

În aplicație: alegi folderul cu ARW-uri → aștepți analiza → te uiți la pozele roșii și galbene (clic = mărit; tasta `1` = închis, `2` = e ok,
`←` `→` = următoarea) → opțional exporți etichetele pentru Lightroom.

**Linia de comandă:** `uv run python blinkcull.py /calea/spre/poze --xmp-dir out/xmp`
**Plugin Lightroom Classic (experimental):** vezi [lightroom/README.md](lightroom/README.md). Scrie etichetele direct în catalog și merge și pe poze deja importate.

## Limite

- Puncte slabe: fețe de profil, îmbrățișări, privit în jos, fețe neclare sau foarte întunecate (acestea sunt sărite, nu judecate).
- **O singură galerie, un singur etichetator.** Pragurile (0.45 / 0.25) pot trebui ajustate pentru alte evenimente, aparate sau lumină.
- Doar **Sony ARW** pentru moment.
- Aplicația împachetată e doar pentru macOS (Apple silicon). Windows și Linux din sursă nu au fost testate.
- Interfața aplicației e în română; traducerea în engleză e binevenită.

## Confidențialitate

Pozele sunt doar citite. Aplicația își servește interfața dintr-un server local legat doar la `127.0.0.1`, iar fiecare cerere cere un token aleator
și un antet `Host` corect. **Nu pune niciodată poze cu oameni reali, fișiere RAW, `.xmp` sau fișiere cu etichete în repo sau în issue-uri.**

## Licență

Apache-2.0, vezi [LICENSE](LICENSE). Componentele și modelele terțe își păstrează licențele, vezi [NOTICE](NOTICE).
