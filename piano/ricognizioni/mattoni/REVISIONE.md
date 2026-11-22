# Revisione della ricognizione «mattoni» (tappa 1-bis)

Revisore: sola lettura sul repository. Esperimenti, copie e foto in
`/tmp/claude-0/-home-user-gestionale-agende-versioni/e320334c-e9fc-59d6-bb37-15e83858aab7/scratchpad/veste-revisore-mattoni/`
(sotto: `copia/` è un `git archive` di HEAD con le bozze applicate, `misure/` gli script e i risultati, `foto/` le foto).
Server di prova usati: 5147-5150 e 5163, ora fermi.

Come ho provato: ho preso le bozze (base.html B, gettoni.css, veste.css, _pezzi.html), le ho messe in una copia
delle due cartelle e ho fatto girare tutte le prove senza browser (tranne campagna) e 5 raccolte nel browser. Poi ho
confrontato con le foto due gestionali di prova accesi insieme sugli stessi dati: il principale (il repository) e il
ramo (la copia).

## A. Bloccanti: con le bozze così come sono, le prove diventano rosse

1. **La base.html della bozza è vecchia.** È stata scritta prima di `ed4c6ee` e `91a02d6` (tappa 1, 22/11 alle 03:54
   e alle 03:57). Se la si copia, sparisce `<main id="principale">…</main>`: `prove_pagine.py` p_main va in rosso.
   Sparisce anche `animazioni.js` in fondo alla pagina: l'animata resta senza le sue animazioni in JavaScript. Anche
   la frase del collega «la variabile variante arriva con la tappa 1» non vale più: `variante` è già in base.html.
   - Bozza rifatta sulla base.html di oggi:
     `veste-revisore-mattoni/bozze/templates/base.html` e la sua differenza `base.html.diff`. Tocca solo la testa
     della pagina.
   - base.html cambia ancora: proprio ora un altro agente le aggiunge `role="status"` su `.avvisi`. Quindi la
     modifica si applica come patch alle righe della testa, mai copiando il file intero.
2. **La soluzione B rompe `prove_pagine.py`** (misurato, non supposto).
   - Animata: p_variante è ROTTO (`'/static/animazioni.css'` manca nelle risorse di tutte le pagine).
   - Normale: g_variante è ROTTO («non reagiscono»).
   - Il motivo: `Guarda.fonti` raccoglie solo `<link href>` e `<script src>`, mentre con B animazioni.css arriva con un
     `@import` dentro `<style>`. Il collega aveva controllato solo p_esterni e p_fogli_di_stile, perché p_variante e
     g_variante sono nate dopo il suo lavoro.
   - Rimedio: prima la prova, poi la pagina. Bastano due righe in `handle_data`: dentro `<style>`, si aggiungono a
     `fonti` gli indirizzi degli `@import url(...)`. La differenza è in `veste-revisore-mattoni/bozze/prove_pagine.py.diff`.
     Con la correzione: 14/14 in tutte e due le cartelle. Sulle pagine di oggi non cambia niente, perché non ci sono
     `@import`.
3. **L'icona `chevron-down` non esiste** in `templates/_icone.html`, eppure `_pezzi.html` (stampa_e_scarica) e il
   catalogo (`.v-tendina`) la usano.
   - `icona()` con un nome sconosciuto scrive un SVG vuoto, senza dare errore. Risultato: «Stampa e scarica» e la
     tendina della struttura restano senza freccina (si vede in `veste-mattoni/foto/catalogo/barra-tendina-chiaro.png`).
     La tavola la freccina ce l'ha (`SPEC-AGENDE.md:88`: «con la freccina»). Un `<select>` con `appearance: none` e
     senza freccia non si riconosce più come tendina.
   - `prove_18.py:1104` (p_contrasti_icone) diventa ROTTO in tutte e due le cartelle: `{'chevron-down'}`.
   - Rimedio provato: aggiungere `'chevron-down'` a `ICONE` in `strumenti/genera_icone.py` e rigenerare con Lucide
     1.55.0 (c'è già in `scratchpad/lucide_pacchetto/estratto/package/icons`). Esce `m6 9 6 6 6-6`, e prove_18 torna
     35/35.
   - Se serve la freccina di «Elenco del giorno» (vedi D2), aggiungere anche `arrow-up-right`.
   - La prova delle icone guarda solo `templates/`: il catalogo in `strumenti/` non lo controlla nessuno.

Le altre prove sulla copia con le bozze:
- tutte le prove senza browser: verdi (tranne campagna, non lanciata, e le due in rosso qui sopra);
- nel browser, sull'animata: guida 61/61, sicurezza 10/10, animazioni 51/51, icone animate 14/14, tendine 167/167.

## B. Cosa regge (verificato di nuovo, sul codice di oggi con `<main>`)

- **Lo strato non cambia le pagine di oggi.** Ho confrontato il principale con il ramo, due server sugli stessi dati:
  95 casi (`misure/foto_principale_ramo.py`, risultati in `foto/esito.json`). Dentro ci sono 31 pagine in chiaro e in
  scuro, e in più le cose che la prima ricognizione non guardava:
  - la tendina aperta (Giorno, Ambulatori settimana e mese, Turni);
  - il fuoco della tastiera (12 pagine, in scuro);
  - 9 pagine stampate con Ctrl+P (emulazione della stampa);
  - le notifiche a scomparsa visibili;
  - la pagina 404.

  92 casi sono identici. Degli altri tre: uno è rumore (Cassa in scuro, 36 px, uguale fra due foto del principale).
  Gli altri due sono Impostazioni in chiaro e in scuro, 100 px: cambia solo il percorso del database scritto nella
  pagina (`dati-p` invece di `dati-r`), quindi non dipende dallo strato. Errori JavaScript: nessuno.
- **Animata in movimento** (senza «riduci movimento»). Su 11 pagine, in chiaro e in scuro, ho confrontato per ogni
  elemento gli stili calcolati delle animazioni (nome, durata, ritardo, transizioni) e i colori: 22 casi, 0 differenze
  (`misure/animata_calcolati.txt`). Il collega aveva provato l'animata solo da ferma.
- **Il colore della struttura** dentro lo strato è giusto. Fuori dallo strato sono 12 pagine diverse, non 13:
  la tredicesima, `/riepilogo-live`, è rumore. Il commento della bozza base.html dice 13: va corretto.
- **I pezzi nelle prove rigide.** I pezzi funzionano con `GESTIONALE_PROVE_RIGIDE=1` (VariabileMancante): ho provato
  ogni macro. Anche il catalogo si apre in modo rigido, e nella sua pagina non c'è nessun nome vero (cercati: il nome
  della clinica, la società, i medici di seed.py).
- **Il prefisso `v-` è libero**, anche nei .py, in `animazioni.js` e `animazioni.css`. Anche `--v-` è libero.
- **euro().** In tutti i 13 punti d'uso l'importo è un intero: somme di colonne Integer, `servizi.py:1022, 1040, 1080`.
  La prova del collega su 22.013 interi copre quindi i casi veri.
- **@import con layer().** Chiede Chrome o Edge 99 o più nuovi. Ce l'hanno anche Chrome ed Edge 109, gli ultimi per
  Windows 7. La cache non dà problemi: `/static/` risponde `no-cache` con ETag, quindi dopo l'aggiornamento il browser
  non usa fogli vecchi.

## C. Contrasti: mancano proprio le coppie che dipendono dal colore della struttura

Le 27 coppie della prova usano solo i gettoni con un valore scritto. Lasciano fuori tutto quello che segue
`--primario`. Ho misurato le coppie che veste.css usa davvero su 334 colori: quelli di prova più una griglia di tinte,
passati da `marchio.leggibile()` come fa il programma (`misure/contrasti_primario.py` e `.txt`).

| coppia (dove) | minimo | esempi |
|---|---|---|
| scuro: bianco sul bottone principale sotto il mouse (`--v-primario-premuto` = 80% primario + bianco) | **3,14** | #2e7d32 (colore delle prove) 3,50; #6b4e9b 4,16 |
| scuro: riga piccola della voce della tendina sotto il mouse (testo-tenue su `--primario-tenue` scuro) | **4,11** | #2e7d32 4,41 |
| chiaro, con le varianti di oggi: linguetta accesa, collegamento sul fondo, linguetta sotto il mouse | **4,01-4,15** | |
| chiaro, con le varianti proposte (`marchio_tema_nuovo.py`): linguetta sotto il mouse (primario-testo su incasso) | **4,35** | la bozza controlla «testo» solo sulla tinta |

- Il piano dice «Nei pezzi nuovi contrasto almeno 4,5:1» (`piano2/s2.md`). Quindi «in scuro è già così oggi»
  (rischio 3 del collega) non basta.
- Rimedi, misurati sulla stessa griglia:
  - in scuro `--v-primario-premuto: color-mix(in srgb, var(--primario) 82%, #000)`: minimo 6,19;
  - riga piccola della voce sotto il mouse con `--v-testo-medio`: minimo 6,20;
  - `testo` di `varianti_nuove` scurito finché si legge su tinta, incasso **e** fondo: minimo 4,51. È quello che il
    piano chiede in tappa 2 per il menu.
- La prova dei contrasti deve calcolare queste coppie su un insieme di colori: il predefinito #154381, i colori delle
  prove (#6b4e9b, #2e7d32) e una griglia.

## D. Pezzi: cose da aggiungere o correggere in `_pezzi.html` e `veste.css`

1. **`stampa_e_scarica` non riesce a scrivere le tendine di oggi.** Le tendine sono 4.
   - Turni, «Strumenti» (`_personale_barra.html:38-46`): `role="menuitem"`, `data-apri-schema` e `data-copia-settimana`
     (li legge turni.js), `onclick="window.print()"`, un'icona per voce.
   - Ambulatori settimana, la voce «Stampa» (`ambulatori_settimana.html:31`): `onclick`.
   - Ambulatori mese: il bottone si chiama «Altre esportazioni». La macro mette sempre l'icona della stampante.
   - Proposta: le voci scritte nella pagina dentro `{% call %}`, come vuole la regola dei pezzi, più un argomento
     `icona` per il bottone.
   - Attenzione: `.v-stampa .tendina a { display: flex; flex-direction: column }` sta fuori dallo strato, quindi vince
     su `stile.css:1205` (la griglia con l'icona dei Turni) e l'icona finirebbe sopra il testo. Serve una regola
     `.v-stampa .tendina a .icona`.
2. **`linguette`.** `SPEC-PSC.md:38-43` chiede su ogni linguetta un `title`, con la riga piccola del menu di oggi, e
   per «Elenco del giorno» una piccola freccia. La macro non ha i campi `titolo` e `icona`. Le `<nav>` di oggi hanno
   già il nome (`_personale_barra.html:9` «Vista dei turni», `ambulatori_riepilogo.html:44`): va passato a
   `etichetta`, ed essendo un testo di oggi non serve un'approvazione.
3. **`passo` scrive `v-passo` senza la classe `passo`.**
   - `prove_112_browser.py:304` cerca `a.passo[data-tasto="precedente"]`: la prova va cambiata prima, con
     `[data-tasto="precedente"]`.
   - `animazioni.js:70` mette l'onda solo su `.passo`.
   - In 18 modelli il testo «‹»/«›» sparisce, e il lanciatore lo conta come testo diverso: serve una riga in
     `strumenti/cambiamenti_approvati.txt` («le frecce diventano icone»).
4. **Bottoni spenti.** `v-bottone:disabled` non ha uno stile, mentre oggi `stile.css:1364` lo ha (opacità .45).
5. **Maiuscole.** Le tavole hanno etichette in maiuscolo (`text-transform: uppercase` in Paz2, Conf3, Dove1-3 e
   Dashboard) e 24 dichiarazioni di `letter-spacing` fra .06 e .07em. Nella scala c'è solo -0,012em: o si aggiunge un
   gettone, o si dice che nella base non entrano.

## E. Gettoni: affermazioni da correggere e scelte da far vedere a Giovanni

- **«Gli stati restano quelli di oggi»: non vale per tre stati.** Sono cambi d'aspetto che arrivano dalla tavola
  approvata. Vanno detti come tali e i commenti vanno corretti.
  - Non presentato: oggi è #9C4A1A, marrone (`stile.css:435`), e #8A1C16 sul bottone (`stile.css:439`). Il gettone usa
    #B3261E citando `stile.css:133`, ma quella riga è `.avviso.errore`. Anche la tavola (`Nefro-Colori.dc.html:101`)
    scrive «come oggi», e non è vero.
  - Confermato: oggi è verde (`stile.css:431, 437`). La pillola della tavola è blu fisso #1C4184 e resta blu del gruppo
    anche per una struttura con un altro colore.
  - Disdetto: oggi #8C979E (2,9:1), nella tavola #5B687C.
- **Bordo dei campi.** #B3BDCB al posto di #D8DFEB, che è il colore della tavola approvata: è una scelta diversa
  dalla tavola e va approvata da Giovanni insieme alle foto.
- **Colore del catalogo.** Il catalogo colora la struttura con #1C4184. Il predefinito è #154381
  (`modelli.py:46`), quindi le foto da approvare vanno fatte anche con il colore vero della clinica.

## F. Prove che il piano chiede e che le bozze non hanno

1. **Foto delle pagine nel lanciatore.** «Con il lanciatore, le foto delle pagine di oggi sono identiche». Oggi
   `confronta_rami.py` non fotografa le pagine a schermo. Lo script del collega cambiava la pagina al volo su un server
   solo: dopo la modifica non serve più. Serve un passo foto «principale contro ramo» dentro il lanciatore; il modello è
   `misure/foto_principale_ramo.py`. Va nascosto il percorso scritto in Impostazioni («Database:», «Cartella dei
   backup:»), perché le due copie del database stanno in cartelle diverse.
2. **«In scuro campo, bottone e collegamento nuovi prendono i colori dei gettoni».** Non c'è nessuna prova nel
   browser. Ho misurato (`misure/scuro_pezzi.txt`): senza strato il **campo** prende comunque il fondo giusto, perché
   `.v-campo :is(input:not(...):not(...))` pesa (0,3,1), più di `html.scuro input` (0,1,2). Quindi il campo da solo non
   trova l'errore. Lo trovano:
   - `<a class="v-bottone">`: il testo prende il colore dei collegamenti;
   - `.v-tendina select`: il fondo diventa #1B232C invece di #1C242D.
3. **`prove_mattoni.py`.**
   - Va messa in `SENZA_BROWSER` di `strumenti/tutte_le_prove.py` e scritta con `prova()`.
   - `pz_agganci` cerca solo delle stringhe: meglio far girare le macro con VariabileMancante.
   - Manca il mutante «icona che non esiste» (vedi A3).
   - Manca il mutante «strato diviso in sotto-strati». Non bisogna dividere lo strato in `vecchio.stile`,
     `vecchio.animazioni`, `vecchio.tema`: l'ordine degli strati vincerebbe sul peso dei selettori, e tema-scuro.css
     batterebbe sempre stile.css, cambiando le pagine.
4. **Autoriparazione.** `risorse_presenti` oggi è in `app.py:1011-1015`, non più a 987-991. `prove_installato.py:147`
   va esteso a `gettoni.css` e `veste.css`.

## G. Scostamenti dal piano da scrivere nel resoconto della tappa

- **B al posto di `static/vecchio.css`.** B scrive gli `@import` dentro base.html invece di usare il file
  `static/vecchio.css` del piano. È la scelta giusta: la tappa 1 ha portato i file propri delle due versioni a 3
  (`allinea_animata.py:26-27`, PROPRI). La soluzione A obbligherebbe ad aggiungere `static/vecchio.css` ai PROPRI.
  Però è diverso da come lo dice il piano: va scritto nel resoconto.
- **Il catalogo in uno script suo** (`strumenti/catalogo_pezzi.py`), e non dentro demo.py. È coerente con
  `piano2/s2.md`: demo.py non cambia dopo la tappa 1.

Fuori da quest'area («dopo, nei moduli»): niente.
