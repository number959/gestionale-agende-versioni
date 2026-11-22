# Revisione della ricognizione «ambulatori-dove» (tappa 8)

Revisore scettico, in sola lettura: il repository non l'ho toccato (`git status` uguale a prima, con le sole
modifiche degli altri agenti). Esperimenti e copie in
`/tmp/claude-0/-home-user-gestionale-agende-versioni/e320334c-e9fc-59d6-bb37-15e83858aab7/scratchpad/veste-revisore-ambulatori-dove/`
(copie di HEAD delle prove in `head/`, script `ispeziona.js`, `tabelle_tavola.js`, `testi_confronto.js`,
`periodo_stretto.js`, `font.js`). Il mio gestionale di prova (porta 5163) è spento.
Le righe delle prove sono quelle di HEAD (`878f2eb`): gli altri agenti stanno cambiando i file di prova.

## 1. Cosa ho verificato e regge

- Le tavole Nefro-Ambulatori 1, 2, 4 e 5 hanno 4 linguette, la 3 ne ha 5; `veste-cornice/menu_bozza.py:95-107`
  ne ha 5 con «Riepilogo live» (resta fino a M6). Giusto.
- `prove_112.py:577, 884-886, 965-966, 1197-1228, 1261, 2517, 2634-2637, 2646`: le stringhe esatte ci sono, alle
  righe dette. `stile.css:583-591, 631-636, 843-848, 1706-1708`, `gestionale.js:523-543, 714-771`,
  `guida.js:19-35` (salta gli elementi nascosti), `dove.js:116-118, 176-181`: tutto come detto.
- Il lanciatore confronta liste in ordine (in HEAD `confronta_rami.py:216-231`; nella copia di lavoro, non ancora
  salvata, le righe scendono di circa 10).
- La scheda di Dove si fa sotto `.menu`: dal codice (`dove.js:176-181`) e da `prove_19_browser.py:148-149`, che
  misura con lo stesso `.menu`, la conclusione regge.
- «DISPONIBILE» non sta nella cella: misurato di nuovo con il carattere Inter davvero caricato (lo stesso che il
  programma ha in `static/fonts/`): 77,6 px a 600 e 12,5 px (il collega 75,9). La conclusione regge, anzi peggiora.
- I 9 modelli dell'area e `dove.js` sono identici nelle due cartelle (`cmp`); `dove_stampa.html` è fra i 9 fogli
  di `strumenti/fogli_pdf.py:24-34`.

## 2. Errori e cose dette in modo sbagliato

1. **Bozza della testa: `<h1 class="giorno v-titolo">`** nel cruscotto e nello schermo. `prove_112.py:2646` cerca
   `'<h1 class="giorno">Riepilogo del periodo'`: con una classe in più la prova cade. La bozza contraddice il
   testo («h1 di oggi»). Si tiene `class="giorno"` da sola, oppure la prova si riscrive nel primo commit.
2. **Bozza della testa: `h1_di_oggi` come stringa con `<small>` dentro.** Con l'escape automatico di Flask il
   `<small class="sotto-titolo">` esce scritto come testo. Serve un `{% call %}` oppure il markup scritto nella
   pagina, non una stringa concatenata.
3. **«La striscia perde solo la virgola»: non è vero per il lanciatore.** `Lettore.handle_data` registra un
   elemento di testo per ogni nodo. Oggi «59 mezze giornate libere, 3 con ore libere» è UN nodo
   (`ambulatori_settimana.html:7`). Con il pezzo striscia (`veste-mattoni/bozze/templates/_pezzi.html:84-94`,
   numero e parola in due `<span>`) i nodi diventano quattro. In `cambiamenti_approvati.txt` la regola
   `sostituisci` cambia un elemento in uno solo (`_sostituisci` lo applica elemento per elemento). Uno
   spezzamento quindi non si approva, se non con regole `aggiunto` larghissime (`^\d+$`), che coprirebbero anche
   le differenze vere. Lo stesso vale per l'h1 diviso in h1 e h2, per «Sala operatoria:» in grassetto (tavola 2,
   `frase_sala`), per «libero» staccato dalla fascia (tavola 1) e per la legenda del live su due righe. Serve una
   decisione nel lanciatore (unire i nodi dentro un pezzo, per esempio `.v-striscia-voce`), oppure tenere il testo
   di oggi in un nodo solo.
4. **Cruscotto senza schermo «senza linguette d'area»: toglie dei collegamenti.** `/riepilogo-live/statistiche`
   senza `schermo` ha il menu e `sezione='live'` (`ambulatori.py:1725`). Nel principale il menu porta le 5 voci di
   Ambulatori. Nella cornice nuova la voce del menu è una sola, e le altre 4 stanno nelle linguette. Se questa
   pagina le toglie, il lanciatore trova i collegamenti «solo nel principale». E dalla tappa 2 la cornice le
   mostra già, con «Riepilogo live» accesa. Proposta: senza schermo le linguette restano (accesa «Riepilogo
   live», come oggi nella tendina) e l'h1 resta quello di oggi; solo con `schermo=1` niente linguette.
5. **Le linguette di Dove si fa scritte a mano in `dove.html`** (bozza, `linguette([...])`). Il piano le vuole
   nell'elenco Python, l'aggancio per i moduli: s4.md, tappa 2 («voci e linguette stanno in un elenco in un file
   Python…»), e M3 sarà proprio Dove si fa. Mancano due cose:
   - `menu_bozza.py` ha solo l'argomento `struttura` (cioè `struttura=_sid` sempre), ma oggi i collegamenti di
     Dove tolgono la struttura quando ce n'è una sola (`dove.html:19`, `dove_registro.html:7`). Serve un tipo di
     argomento nuovo, oppure gli indirizzi cambiano e il lanciatore lo vede.
   - Se il registro prende una sezione sua, la voce `dove` del menu (`menu_bozza.py:35-36`, `sezioni={'dove'}`)
     deve comprenderla, altrimenti la prova della tappa 2 «ogni pagina accende una voce sola» cade.

## 3. Mancanze (cose non viste)

### Riepilogo live: il rinnovo di ogni minuto

`riepilogo_live.html:124-145` rinnova solo l'interno di `#riepilogo-live` (con `innerHTML`) e il solo `#live-ora`.

- Tutto quello che cambia ogni minuto deve restare DENTRO `#riepilogo-live`: la striscia (oggi
  `ul.conti-oggi-live` dentro `section.riassunto-live`), la frase, i fatti. Se la veste porta la striscia sopra,
  fuori dal contenitore (la tavola 3 la mette in una scheda sopra la frase), i numeri restano fermi.
- Dentro `#riepilogo-live` niente pezzi con JavaScript (tendine, `.gruppo-comandi`): `innerHTML` perde gli
  ascoltatori di `gestionale.js`, legati una sola volta al caricamento.
- Restano `id="riepilogo-live"`, `data-giorno`, `data-indirizzo`, `id="live-ora"` (unico) e
  `body.pagina-live` (`gestionale.js:624`).
- `prove_112_browser.py:366-425` prova il rinnovo, ma non che i numeri fuori dal contenitore si aggiornino:
  resterebbe verde.

### Nomi ripetuti dentro `<main>`

La bozza della testa mette le linguette DENTRO `<main>`, mentre la cornice di `veste-cornice/base_bozza.html:37`
le mette fuori. Con le linguette in `<main>`, `aiuti_browser.py` (`principale()` = main, `nome_voce` confronta
l'inizio del nome, `_uno` vuole un elemento solo) trova due elementi per:

- Live: «Riepilogo del periodo», la linguetta (→ `/ambulatori/riepilogo`) e il bottone
  (→ `/riepilogo-live/statistiche`). Stesso nome, pagine diverse. È proprio la confusione che
  `prove_112.py:2666-2673` vieta («un solo pulsante con quel nome»). C'è anche «Pianificazione», che con
  `nome_voce` trova pure «Pianificazione della settimana».
- Periodo: «Riepilogo live» (linguetta e bottone di riga 37).
- Mese: «Pianificazione della settimana» (linguetta e bottone della barra, stesso indirizzo).
- Settimana: «Programmazione del mese» (linguetta, e la voce «Programmazione del mese per specialità…» della
  tendina).

Si decide prima (testo diverso, o prove limitate alla barra), non a prove cadute.

### «Questa settimana» / «Questo mese» → «Oggi»: solo nei bottoni

Le stesse parole sono anche nomi di periodo:

- i periodi pronti del Riepilogo del periodo (`ambulatori.py:1255-1256`; la tavola 4 li tiene);
- le scorciatoie delle Statistiche (`viste.py:390`).

Non vanno cambiate. Una regola `sostituisci testo ^Questa settimana$ Oggi` vale per tutte le pagine (il formato
non ha un filtro per pagina) e farebbe differenze false lì. `prove_112_browser.py:298` cerca proprio
`.periodi-pronti .bottone.attivo` = «Questa settimana».

### Prove che guardano l'HTML

Oltre a quelle elencate dal collega, in HEAD:

`prove_112.py`:
- 1197: `'libero 14:00–15:00'` in un nodo solo;
- 1975 `'Riepilogo live</b>'` e 2232 `'Riepilogo del periodo</b>'`: il menu, tappa 2;
- 1977: `'class="pagina-live schermo"'` esatto;
- 2084: conta `'class="riga-live '`;
- 2402: `'<b>1</b> mezza giornata su 2 senza nessun medico'`;
- 2403, 2723, 2760, 2769, 2772: `<h2 class="sezione">… <small class="sotto-titolo">`;
- 2670-2673: `split('<div class="barra">')` e «Riepilogo del periodo» contato una volta;
- 2767: `<p class="frase-live[^>]*>([^<]*)</p>`, cioè niente tag dentro la frase;
- 2773: `'di turno nelle stanze</li>'`.

`prove_112_browser.py`:
- 182: `a.bottone.primario` «Scarica in Excel» nel mese. Cade quando l'Excel va nella tendina;
- 195-197: la tendina ha 3 voci, diventano 5;
- 298: vedi sopra;
- 304: `a.passo[data-tasto="precedente"]`. Il pezzo `passo()` della bozza ha la classe `v-passo`;
- 279: la grandezza della legenda del live.

`prove_19_browser.py`:
- **151-153 «la pagina lascia posto alla scheda»: CADE** quando si toglie `margin-right: 460px`
  (`stile.css:1708`, cambiamento approvato «scheda sopra la pagina»). È una prova d'aspetto: si cambia nel primo
  commit e va nell'elenco del pacchetto;
- 246-248 e 252: a 390 px niente scorrimento di lato. Le tre linguette di Dove devono andare a capo o scorrere
  dentro la loro fila.

Nessuna prova stampa le pagine dell'area: in `prove_112_browser.py` non c'è `emulate_media`.

### Testi della tavola che oggi non ci sono, non segnalati

Misurati con `testi_confronto.js`, tavola contro pagina di oggi:

- «Struttura», etichetta nascosta della tendina delle strutture, in tutte e 5 le tavole di Ambulatori. Dà un nome
  a un campo che oggi non ce l'ha: la regola dell'accessibilità la vorrebbe, ma è un testo nuovo.
- Esportazioni: h2 con la data («giovedì 19 novembre 2026»; oggi nessun titolo con la data); intestazione di
  colonna «Periodo» (oggi `<th></th>`); il `title` con il nome del file sui 9 «Scarica».
- Registro: «Togli dal registro» (intestazione nascosta); aria-label «Togli: Nome, data» su ogni Togli; `title`
  sulle frecce del mese; aria-label «I numeri del mese» e «Pazienti indirizzati · Novembre 2026».
- aria-label «Periodi pronti», «Periodo precedente/successivo», «Settimana/Mese precedente/successivo» (dal pezzo
  `passo()`), «Calendario del mese» (tavola 2).
- Live: `title` su «Riepilogo del periodo», «Modo schermo», «Pianificazione» e «Oggi»; aria-label «Le stanze
  adesso», «Mezze giornate libere», «Giorno»; «Visite ora per ora» con role=img e una descrizione lunga.

Nella copia di lavoro di `confronta_rami.py` (non ancora salvata) i «segni» comprendono anche `role`,
`aria-label`, `aria-current` e `data-prova`. Ogni aria-label nuova delle tavole diventa quindi una differenza da
mettere nell'elenco, anche quelle che il collega chiama «solo se approvate».

### Guida (`guida.py`): parole che diventano sbagliate in questa tappa

- 662-666: il passo «In Excel» e il passo intitolato «Altre esportazioni».
- 720: «Stampa» stampa la pagina; adesso sta in «Stampa e scarica».
- 730: «Ci si arriva anche da «Altre esportazioni» nel giorno e nella programmazione del mese».
- 675-677 (live, «Sotto, la barra e i quattro numeri») e 711-713 (periodo, «In cima una frase…; sotto…»): non
  valgono più se la striscia va sopra la frase.
- 625-627: «Il «+» in alto a destra della cella». È già sbagliato oggi: `stile.css:583` lo mette in basso a
  destra.
- `novita.py:85` è storia: non si tocca.

### Animata

I modelli sono uguali, ma il CSS e il JS dell'animata dipendono dalle classi di oggi:
- `animazioni.js:135` (`ul.numeri b`, il conteggio che sale: il registro ha `<ul class="numeri">`);
- `animazioni.js:119` (`table.elenco`: programmazione, calendario, tabelle del periodo, esportazioni,
  indirizzati);
- `animazioni.js:244` (`p.vuoto`);
- `animazioni.css:109` (`.anim ul.numeri li`);
- `animazioni.css:220-235` (`.voce-dove`, `.scheda-dove:not([hidden])`, `.pagina-dove`, la cui transizione del
  margine perde senso se il margine se ne va).

Il collega dice «nessun selettore della matrice»; per Dove e per il registro questi selettori ci sono.

### Stampa delle 3 pagine di Ambulatori fra «le 8 pagine che si stampano» (s7.md:29, decisione aperta)

Stamparle identiche a oggi è incompatibile con la testa nuova:
- il titolo stampato oggi è l'h1 della `.barra` («Ambulatori · Settimana dal…», «Programmazione ambulatori ·
  mese», «Riepilogo del periodo <small>…</small>»);
- per rifarlo servirebbe una copia del titolo vecchio solo per la stampa, cioè testo doppio per il lanciatore e
  per i lettori di schermo.

Va chiesto prima. Comunque la barra nuova deve sparire in stampa come oggi `.comandi`, `.barra .comandi` e
`.solo-schermo` (`stile.css:843`).

### Misura: le tabelle del periodo non stanno a 1366

- Tavola 4, `tabelle_tavola.js`: «Le stanze» è larga 1112 px in una scheda di 1044, e scorre di 68 px (nella
  foto l'ultima colonna «Mezze giornate senza medico» è tagliata). «I medici» è larga 1056 px su 1044.
- Pagina di oggi, con il CSS di oggi, contenuto stretto a 1044 px (`periodo_stretto.js`): 1071 px (27 di troppo)
  per gli ambulatori, 1062 px per la sala.

Va deciso (intestazioni più corte, o lo scorrimento accettato e detto a Giovanni).

### Pezzo «Stampa e scarica» della bozza dei mattoni

`_pezzi.html:134-143` non sa fare la voce «Stampa» (`href="#" onclick="window.print()"`): ogni voce è un
indirizzo. Quindi o il pezzo si allarga, o le tre tendine dell'area restano scritte a mano (la bozza del collega
fa così).

### Pagine sotto `/riepilogo-live*`

Live e cruscotto, con e senza schermo, sono le pagine che vedono gli altri PC. Dalla cornice non deve arrivare
niente con nomi scritto dal server: campanella, risultati della ricerca, popup.
- `prove_canarino.py:99-116` prova tutti gli indirizzi, con e senza schermo;
- `prove_16.py:1066` prova che lì non c'è il popup dell'aggiornamento.

La testa d'area aggiunge il nome della struttura, che va bene; dati di pazienti no.

### Registro di Dove si fa: collegamenti nuovi

Con le tre linguette il registro prende due collegamenti nuovi: «Cerca» e «Strutture del gruppo»
(`/dove-si-fa/strutture`). «Pazienti indirizzati» punta alla pagina stessa. Per il lanciatore sono regole
`aggiunto` da scrivere.
