# Revisione della ricognizione «turni» (tappa 7)

Repository solo letto (ramo `ccr-interfaccia`). Le mie misure e gli script stanno in
`/tmp/claude-0/-home-user-gestionale-agende-versioni/e320334c-e9fc-59d6-bb37-15e83858aab7/scratchpad/veste-turni-rev/`,
con un gestionale di prova sulla porta 5187, fermato alla fine.
Lì ci sono anche le foto a 1366×657 delle tavole Turni4, 5 e 6, che nella cartella `foto/` del collega mancano.

La bozza regge quasi tutta. Va corretta in sei punti; due sono misurati e romperebbero la proposta principale.

## 1. Da correggere nella bozza (misurato)

1. **`v-attaccata` ferma la riga dei giorni.** La bozza scrive `class="telaio-turni v-scheda v-attaccata"` sul
   genitore di `.scorri-turni`. Nei mattoni `.v-scheda.v-attaccata` ha `overflow: hidden`
   (`veste-mattoni/bozze/static/veste.css:63`). Così la riga dei giorni non resta ferma quando scorre la pagina.
   Misura a 1366×657, dopo 700 px di scorrimento:
   - senza `overflow`: la riga sta a y=0;
   - con `overflow: hidden`: sta a y=-238, cioè è uscita dallo schermo;
   - con `overflow-x: clip`: sta a y=0.

   Script: `veste-turni-rev/attaccata.py`. La correzione: niente `v-attaccata` su `.telaio-turni`, oppure
   `.v-turni .telaio-turni { overflow: visible }` (va bene anche `clip`). Nella prova nuova va aggiunto: «dopo lo
   scorrimento la riga dei giorni sta a y=0».

2. **Il Giorno senza `telaio` scorre di lato.** Su schermi stretti si sposta tutta la pagina:
   - a 683 px la pagina diventa larga 760 px (oggi 683);
   - a 390 px diventa larga 760 px (oggi 390);
   - a 1024 px non cambia niente.

   Il motivo è `.linea-tempo { min-width: 760px }` sotto 760 px (`stile.css:1583`). La bozza lo dice in un
   commento, ma la regola manca. Va aggiunto `@media (max-width: 760px) { .v-turni #vista-giorno { overflow-x: auto } }`.
   Sotto 760 px la scala delle ore non resta ferma, come oggi. La prova «schermo stretto» (`prove_18_browser.py:508-519`)
   oggi guarda solo il Mese: va fatta anche sul Giorno. Script: `giorno_stretto.py`.

3. **Il lanciatore boccia la barra della bozza, e oggi nessuna regola la può approvare.** Ho simulato la barra della
   bozza sul Mese di oggi, con `riassunto`, `applica_approvati` e `differenze` di `confronta_rami.py` e con
   `cambiamenti_approvati.txt` di oggi. Script: `lanciatore_barra.py`. Risultato: DIVERSA, per tre motivi.
   - **Collegamenti in un altro ordine.** Persone e Tipi passano davanti alle frecce, quindi i collegamenti hanno
     un ordine diverso. Anche `data-guida=turni-persone` e `turni-tipi` si spostano. La regola della tappa 1
     `aggiunto segni ^data-guida=…` toglie le copie spostate, e così i due segni sembrano spariti.
   - **Nomi nuovi sulle frecce.** `aria-label=Mese precedente` e `Mese successivo` vengono da `passo()`. Una regola
     `aggiunto` basta a coprirli.
   - **Frecce tolte dal testo.** I segni «‹» e «›» spariscono. Una regola `sostituisci` li trasforma in stringhe
     vuote, e la pagina resta diversa.

   Anche aggiungendo le due regole possibili, restano «ordine diverso» e due stringhe vuote. In `confronta_rami.py`
   servono due tipi di regola nuovi: uno per gli spostamenti (per esempio `spostato`, che confronta gli elementi
   senza guardare l'ordine) e uno per le cose tolte (`tolto`, che toglie dal principale). C'è un'alternativa: il
   piano (`s4.md`, tappa 1) confronta il testo solo nelle 32 pagine senza tavola, mentre oggi lo strumento lo
   confronta in tutte. Va deciso prima del secondo passo della tappa 7. Vale anche per le tappe 5, 6 e 8, che
   usano `passo()`.
   Nelle pagine Persone, Tipi e scheda, l'elenco deve anche permettere:
   - le linguette nuove, cioè i collegamenti a giorno, settimana e `/personale/turni`;
   - i testi «Giorno», «Settimana», «Mese»;
   - `aria-label=Vista dei turni`.

4. **Stampa.** Le regole d'aspetto della bozza non stanno sotto `@media screen`: thead,
   `col.festivo`/`col.sabato`, `td.tot`, `tr.testa-ruolo` e `td.manca` (`turni-veste.css:66-77`).
   Con `vecchio.css` in un layer (tappa 1-bis), queste regole vincono anche sulla stampa di `stile.css:1593-1608`.
   Il foglio dei turni cambierebbe colori: per esempio la riga dei giorni non sarebbe più blu.

   Anche il marchio `solo-stampa`, messo in un blocco prima dell'intestazione, cambia la riga in alto del foglio.
   Oggi logo, titolo e «Turni del personale» stanno su una riga sola (`.barra`).

   `s7.md:29` propone di stampare identiche le 8 pagine che si stampano, fra cui la barra dei Turni, e di
   confrontarle in PDF dalla tappa 2. Se Giovanni dice sì, servono due cose:
   - tutte le regole nuove sotto `@media screen`;
   - una regola di stampa che rimetta logo, h1 e sottotitolo su una riga.

5. **I mattoni usati in modo diverso da come sono fatti.**
   - `<select class="v-tendina">`: nei mattoni `v-tendina` è il `<label>` che avvolge la tendina. Lo stile è su
     `.v-tendina select` (`veste.css:185-193`, `_pezzi.html:100`). Sulla select la classe non dà quasi niente.
   - Strumenti con `v-stampa`: `.v-stampa .tendina a` è in colonna (`veste.css:234`), quindi le icone delle voci
     vanno sopra il testo. Oggi le voci sono una griglia da 22 px, ma la regola sta sotto `.barra-turni`
     (`stile.css:1205-1206`), che sparisce. Serve una regola apposta.
   - `span.v-freccia` vuoto: nei mattoni contiene l'icona `chevron-down`.
   - Queste classi della bozza non esistono nei mattoni: `.v-due-colonne`, `.v-filtri`, `.v-separa`,
     `.v-griglia-turni`. Vanno scritte nella tappa 7 o tolte.

6. **Animata: si perde più di una regola.** Il collega cita solo `.anim .schede-vista a`. Ma la bozza toglie anche
   le classi `barra`, `telaio`, `bottone` (sul bottone Oggi e su Strumenti) e `passo`. Così si perdono:
   - l'entrata della pagina per barra e griglia (`animazioni.css:35-36`);
   - l'onda sui pulsanti (`animazioni.css:68-73`, `animazioni.js:70`, che cerca `.bottone, .passo`).

   La revisione dei mattoni ne parla al punto 3. Il passaggio da destra o da sinistra (`verso-…`) vale solo per
   `table.griglia`: i turni non lo hanno.

## 2. Prove e strumenti che guardano quell'HTML (mancano nell'elenco)

- `strumenti/prove_installato.py:164-173` gira in Wine sull'eseguibile. Cerca queste parti:
  - le scritte `id="griglia-turni"`, `id="vista-giorno"`, «Per cominciare, il personale», «Aggiungi una persona»;
  - nella pagina dei Tipi, la regex `<span class="turno[^"]*"[^>]*><b>([A-Z0-9]{1,4})</b></span>`.

  Per questo il tassello nella tabella dei tipi deve restare uno `span.turno` con dentro solo il `<b>`, attaccato.
- `strumenti/equivalenza_selettori.py` (nuovo, tappa 1, righe 238-330), e le prove riscritte con lui, usano:
  - `get_by_role('button', name='Strumenti')`;
  - le voci di menu «Copia la settimana prima» e «Schema a rotazione…»;
  - `get_by_role('link', name='Modifica')` nella tabella delle persone;
  - `get_by_role('button', name='Elimina', exact=True)` nella scheda della persona;
  - `get_by_role('button', name='Annulla', exact=True)` sull'avviso dei turni.

  L'`aria-label` «Elimina la persona» della tavola Turni5 romperebbe la prova con `exact`. Quindi non si aggiunge,
  oppure la prova cambia nel primo passo.
- `dove.html:25` usa anche `.vuoto-turni`: non va cambiata fuori da `.v-turni`.
- `tema-scuro.css:384-389, 474-475` riguardano legenda, `.scorri-turni` e `.vuoto-turni`.
- `guida.py:383` (`#aggiungi-persona`) e il passo dei Tipi (`#modulo-tipo`) cercano un id, non un `data-guida`.
- Le foto della guida dei 5 argomenti dei turni vanno rifatte: turni-personale, turni-giorno, turni-schema,
  turni-persone, turni-tipi.

## 3. Testi della tavola che oggi non ci sono e che il riassunto non nomina

Questi `aria-label` ci sono solo nelle tavole. Si aggiungono solo con il via di Giovanni:

- **Turni1 e Turni2:** «Legenda dei turni», «Pagine di Turni», «Mese precedente/successivo», «Settimana
  precedente/successivo».
- **Turni3:** «Legenda», «Giorno precedente/successivo».
- **Turni4:** le sezioni «Medici», «Infermieri», «OSS», «Accettazione e amministrazione»; «Aggiungi: ‹gruppo›»;
  «Modifica: ‹persona›».
- **Turni5:** «Scheda della persona», «Elimina la persona» (vedi sopra: rompe una prova).
- **Turni6:** «Tipi di turno», «Coperture minime», «Modifica ‹codice› · ‹nome›», «Togli: ‹ruolo›, ‹turno›,
  ‹area›», «Giorni: lun, mar, …» / «Giorni: tutti», «Nuova copertura minima».

Fonte: `veste-turni/testi.json`, voci `solo_tavola`. I testi visibili nuovi sono quelli già segnalati.

## 4. Rischi in più

- **La struttura si perde.** Le linguette Persone e Tipi, e «Torna ai turni», non portano `struttura`. Da Turni
  della seconda struttura si va a Persone e si torna alla prima. Cambia anche il menu, perché `_menu.html` usa la
  struttura della pagina. È un difetto di oggi.

  Però la prova nuova della tappa 2 (`s4.md:88`) dice: «ogni linguetta porta ancora struttura e giorno». Se guarda
  anche le linguette dei turni, cade. Va deciso:
  - aggiungere `struttura=sid` alle linguette (il collegamento cambia: serve una regola `sostituisci` nell'elenco);
  - oppure escludere le linguette dei turni da quella prova.
- **Le linguette dei turni stanno nella pagina, non in `menu.py`.** `LINGUETTE` della bozza della cornice non ha la
  voce «turni». Le prove della tappa 2 («una linguetta sola accesa») devono saperlo.

  Nella scheda della persona la linguetta Persone avrebbe `aria-current="page"`, anche se la pagina è un'altra.
  `aria-current="true"` è più giusto, ed è già coperto dalla regola della tappa 1.
- **Un codice lungo non si legge intero.** Il piano dice che la tappa è finita quando «in ogni cella il codice del
  turno si legge intero» (`s4.md:128`). Con la proposta non succede per tutti i codici possibili: il server accetta
  `[A-Z][A-Z0-9]{0,3}` (`personale.py:1196`). Misure:
  - MMMM è largo 26,4 px a 8 px;
  - WWW è largo 22,7 px;
  - il posto è circa 22 px.

  La prova proposta misura solo le celle dei dati di prova. Va fatta su tutti i tipi, aggiungendo un tipo MMMM.
  Poi o si scrive il limite nel criterio, o si decide con Giovanni. Per esempio `transform: scaleX(...)` solo per
  `lungo-4`: cambia solo l'aspetto, nei due disegni della cella resta la stessa classe.
- **Due zone di avvisi in basso.** Dalla tappa 3 i messaggi della cornice vanno in basso. In basso al centro ci
  sono già `.avvisi-turni` di `turni.js` (fixed, z-index 46). Da guardare dopo, con la tappa 3.
- **Quattro domande `confirm()` restano fino alla tappa 3:** `turni.js:679` e `1192`,
  `personale_persona.html:59`, `personale_tipi.html:56`. Su quest'ultima nessun pericolo di apostrofo: il codice
  è solo lettere e cifre, lo controlla `personale.py:1196`.
- **Righe citate sbagliate:**
  - lo spostamento nel body è a `turni.js:236`, non 229 (HEAD; nel lavoro in corso è 237);
  - la regola dei due disegni è a `gestionale/CLAUDE.md:319-320`, non 306-308;
  - il piano cita 274-277, che è la riga del commit `e902e25`;
  - oggi `CLAUDE.md` dice che «le prove nel browser lo controllano», ma una prova delle due celle uguali non c'è
    (cercato in `prove_18_browser.py`). La prova nuova proposta dal collega serve davvero.

## 5. Verificato e confermato

- **La pagina che scorre è come nella tavola.** Nelle tavole Turni1 e Turni2 la riga dei giorni è `sticky top:0`
  dentro la pagina che scorre, e la barra in alto non resta ferma. Script: `sticky_tavola.py`.
- **Scelta di molte celle.** Ho provato 17 celle in colonna, con la pagina che scorre, a 1366×657 e 1366×768. La
  scelta resta nello schermo e non copre le celle scelte visibili, come oggi. Nessun errore JS. Script:
  `scelta_lunga.py`.
- **I due difetti di oggi ci sono.**
  - Nuova persona: `scrollWidth` 2171 a 1366, per la radio larga 1366 px.
  - Giorno: la scala delle ore passa da y=194 a y=-405 dopo 600 px di scorrimento, per colpa di `.telaio`
    (`overflow` auto/auto).
- **Le misure tornano.** 1046 px = 1366 - 248 - 2×36 (`--v-spazio-9` = 36 px). La tavola Turni3 a 1366 è larga
  1403 px.
- **I testi della tavola ci sono.** Quelli di Scelta e Schema stanno nel sorgente delle tavole (anche se a
  finestra chiusa non sono nel DOM). In Turni5 i ruoli sono gli stessi 7 di `modelli.RUOLI`. In Turni6 i giorni
  L M M G V S D sono quelli di oggi (`GIORNI_CORTI`).
- **Le due cartelle sono uguali.** I 9 modelli sono identici in `gestionale/` e `gestionale-animata/`, e nessun
  altro modello include i pezzi dei turni. `turni.js` è diverso solo per il lavoro non salvato di un altro agente
  (`role=status`).
- **Le prove di oggi.** `prove_18.py:840-856` e `prove_111_turni.py:146, 287, 298` sono come dice il collega.
