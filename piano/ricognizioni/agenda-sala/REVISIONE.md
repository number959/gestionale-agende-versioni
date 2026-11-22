# Revisione della ricognizione «agenda-sala» (tappa 5)

Revisore scettico, in sola lettura sul ramo `ccr-interfaccia` (HEAD `878f2eb`, 22/11 04:48). Ho controllato tutto sui
file veri e sulle pagine vere. Le pagine le ho aperte con un gestionale di prova mio sulla porta 5177, che ho fermato
alla fine. Script e foto sono in `veste-agenda-sala/revisione/`.

**Nota sul metodo.** La copia del risultato del collega che ho ricevuto si ferma a metà di `settimana.html` («resta»).
Per questo ho ricontrollato da capo tutti e sette i modelli. Le correzioni qui sotto valgono comunque.

**Nota sull'ordine nel tempo.** Il collega ha lavorato fra le 03:33 e le 03:43. Il commit `5046da4` (04:28) ha cambiato
proprio i punti che lui descrive. Inoltre `strumenti/confronta_rami.py` e `strumenti/cambiamenti_approvati.txt` sono
in modifica adesso, non ancora salvati, da un altro agente della tappa 1. Lo stesso vale per `_menu.html` e `base.html`.

---

## 1. Affermazioni da correggere

| Il collega dice | Com'è adesso (verificato) | Conseguenza per la tappa 5 |
|---|---|---|
| La guida trova i punti con le classi: `'.barra .comandi .passo'`, `'td.aperta'`, `'a.voce'`, `'.segni-sala'`, `'.sala-giorno'`, `'details.nota-giorno'`, `'thead .fasce-turno'`… | Dal `5046da4` `guida.py` usa solo `[data-guida="…"]` o un id. `prove_guida.py` vuole che sia così e che il nome esista in un modello (`gestionale/CLAUDE.md:149-151`). | Le classi si possono rinominare. Non si deve perdere nessun `data-guida`: l'elenco completo per modello è al punto 2. |
| `genera_immagini_guida.py:107` e `genera_video_guida.py:84` cercano `a.voce` | Ora cercano `[data-guida="giorno-appuntamento"]` (righe 107 e 84). | Va tenuto `data-guida="giorno-appuntamento"` su `a.voce`. |
| `bozza-intestazioni.html`: le frecce ‹ › hanno solo `data-tasto` | Oggi hanno anche `data-guida="giorno-passo"` (`griglia.html:9-10`). La guida «Un giorno alla volta» (`guida.py:523-524`) punta lì. | La bozza, copiata così, toglie un `data-guida`. Sarebbe una differenza vera e un passo della guida che non trova più niente. |
| `prove_112_browser.py:39-56` (`.gruppo-comandi .apri-gruppo`) guarda la griglia | Guarda `/ambulatori/settimana` (riga 75-76), cioè la tappa 8. | Riguarda la tappa 5 solo se «Stampa e scarica» diventa una macro comune di `_pezzi.html`, usata anche da Ambulatori. |
| `prove_icone_animate.py:23` | La riga 23 è la griglia (la notifica). Le righe 31-55 guardano `sala.html`: l'icona di `p.vuoto` «Nessun intervento.», `form.checklist .conto-checklist` e la `.spunta-checklist` inserita dal JS. | Vedi il punto 3, JS della checklist. |
| `confronta_rami` confronta in ordine e serve «l'elenco dei cambiamenti approvati» | L'elenco c'è: `strumenti/cambiamenti_approvati.txt`, con le regole `aggiunto` e `sostituisci`. L'ordine conta ancora: non c'è una regola per «spostato». | I limiti veri dello strumento sono al punto 4. |

---

## 2. Gli attributi da non toccare, modello per modello (dopo `5046da4`)

Restano sullo **stesso elemento**: `data-guida`, `data-tasto`, id, `role` e `aria-label`. Gli ultimi due adesso
entrano fra i «segni» del confronto (`SEGNI` nella versione non salvata di `confronta_rami.py`).

- **griglia.html**:
  - `data-guida`: `giorno-passo` (×2), `giorno-nuovo`, `giorno-elenco`, `giorno-stampa`, `giorno-sala`, `giorno-fasce-turno`, `giorno-occupata`, `giorno-appuntamento`, `giorno-segni-sala`, `giorno-libera`, `giorno-fascia-ora`;
  - `data-tasto`: `precedente`, `successivo`, `oggi`, `nuovo`;
  - `role="menu"` su `.tendina`.
- **_nota_giorno.html** (incluso in griglia ed elenco): `data-guida="giorno-nota"` su `details.nota-giorno`.
- **settimana.html**: `data-tasto` solo `precedente` e `successivo`. Nessun `data-guida`.
- **mese.html**: `data-guida` `mese-medico` (sulla select), `mese-giorno` (su ogni `a.giorno-mese`), `mese-sala` (×2). `data-tasto` solo precedente e successivo.
- **elenco.html**: `data-tasto` precedente, successivo e oggi. Da `_stato.html` arrivano `data-guida` `stato-pulsanti` e `stato-contatti`.
- **oggi.html**:
  - `data-guida`: `oggi-adesso`, `oggi-in-servizio`;
  - `data-tasto="nuovo"` su «Nuovo appuntamento»;
  - `role="img"` con `aria-label="al lavoro adesso"`.
- **sala.html**:
  - `data-tasto` precedente, successivo e oggi;
  - `data-guida` `sala-lista-operatoria`, `sala-posti-letto`, `sala-checklist` (sul `form.checklist[data-auto]`).
- **appuntamento.html**:
  - `data-guida`: `appuntamento-sposta`, `appuntamento-stato`, `appuntamento-salva`, `luogo-nascita`, `codice-fiscale`;
  - id cercati dalla guida: `#cerca_paziente` (anche come condizione: `prove_guida.py:157-160`), `#paziente`, `#risorsa`, `#prestazione`, `#data`, `#sesso`;
  - `role="status"` su `#esito-cf`; `aria-label="Email da mandare"`.

Questo elenco sta cambiando con la tappa 1: base, menu e tendine prendono `role`, `aria-label` e `aria-current`.
All'inizio della tappa 5 conviene rifarlo con il `Lettore` di `confronta_rami.py` sulle pagine del principale, e non
copiarlo da qui.

---

## 3. Cose che mancano (dalla più grave)

### A. La stampa di Settimana e Mese (misurato)

Settimana e Mese sono 2 delle «8 pagine normali che si stampano» (`piano2/s7.md:29`). La proposta è che restino
stampate identiche a oggi, con il confronto in PDF dalla tappa 2. Il collega non parla della stampa.

Ho guardato le pagine in modo stampa (`revisione/stampa.js`, `revisione/marchio.js`, `revisione/foto/*-stampa-oggi.png`).

**Cosa si stampa oggi:**
- il logo, cioè l'IMG 162×27 di `.barra .marchio`;
- `h1`;
- `.conteggio` sulla stessa riga;
- la tabella;
- in Settimana anche `p.nota`.

`.comandi` sparisce (`stile.css:843`). Nell'agenda del medico «libero» resta trasparente anche in stampa
(`rgba(0,0,0,0)`).

**Con la tavola cambierebbe:**
- la riga «Agenda · …»;
- la striscia dei conti con i numeri grandi;
- la legenda;
- le linguette, «Prima disponibilità» e «Nuovo appuntamento», se stanno fuori da `.comandi`;
- «libero» sempre scritto, che finirebbe sul foglio;
- il logo che va nel menu, che in stampa è nascosto: sparirebbe dal foglio.

**Cosa serve:**
- le parti nuove solo sullo schermo;
- una copia solo per la stampa della riga di oggi (logo, titolo e conteggio);
- «libero» visibile solo sullo schermo.

Lo stesso vale per il Giorno, se qualcuno lo stampa con Ctrl+P (non è fra le 8).

### B. Il JavaScript della checklist (`sala.html`, `appuntamento.html`, e `oggi.html` nell'animata)

**`gestionale.js:680-705`:**
- il contatore si cerca dentro il modulo oppure nel riquadro, con `modulo.closest('.riquadro-modulo')`;
- dopo ogni spunta il JS riscrive la classe: `conto.className = 'conto-checklist ' + (completa ? 'completa' : 'incompleta')`. Una classe nuova con il prefisso, messa sulla pillola, **sparisce al primo clic**.

**`animazioni.js` (animata):**
- 109-117: un MutationObserver sul testo della pillola;
- 259-270: un MutationObserver su `class`, che aggiunge `.spunta-checklist` subito dopo la pillola (`c.parentNode.insertBefore(box, c.nextSibling)`).

**Le prove che lo guardano:**
- `prove_animazioni.py:31-35` (`.conto-checklist.appena`);
- `prove_icone_animate.py:38-55`.

**Cosa serve:**
- la pillola resta `span.conto-checklist.completa|incompleta` e si colora solo con queste classi;
- in `appuntamento.html` il modulo della checklist resta dentro un `.riquadro-modulo`. Se la scheda nuova cambia classe, il JS si cambia nella stessa tappa, con una prova.

### C. Tendine e suggerimenti che finiscono sotto o vengono tagliati

`.barra` ha `z-index: 40` (`stile.css:60-67`). È la correzione del 21/11 per l'animata: la tendina «Stampa e scarica»
finiva sotto la nota e la griglia (`prove_tendine_browser.py:18-21`).

La scheda nuova dei comandi deve:
- stare dentro `.barra`, oppure avere lo stesso piano;
- non avere `overflow: hidden` per gli angoli tondi, perché taglierebbe la tendina.

Lo stesso vale nell'appuntamento per `#suggerimenti` e `#suggerimenti-luogo`, che sono posizionati assoluti
(`prove_tendine_browser.py:157-163`). Le schede dei campi non devono tagliarli.

### D. I tasti rapidi in Settimana e Mese

Oggi Settimana e Mese non hanno `data-tasto="oggi"` né `"nuovo"`.

Se «Oggi» e «Nuovo appuntamento» nuovi li prendono:
- T e N cominciano a funzionare, perché `gestionale.js:523` clicca il primo `[data-tasto]` che trova. È un funzionamento nuovo;
- `confronta_rami` lo conta come differenza: un `data-tasto` aggiunto non si approva.

La bozza del collega lo dice solo per Settimana. Vale anche per Mese.

### E. Pezzi comuni con altre tappe

- `_stato.html` (`pulsanti`, `contatti`) lo usa anche `conferme.html`, che è della tappa 6. Cambiarne il markup nella tappa 5 cambia una pagina della tappa 6.
- `_marchio.html` sta anche nei fogli da stampare: `stampa`, `agenda_medico`, `lista_operatoria`, `promemoria` e altri. Toccarlo cambia i PDF dei 9 fogli.
- `_nota_giorno.html` sta in griglia ed elenco.

Questi pezzi si vestono dal CSS della pagina, non cambiando il file comune. Oppure ci si accorda con la tappa 6.

### F. Prove che leggono l'HTML e che il collega non cita (verificate)

**Prove che dipendono dalla forma esatta dell'HTML:**
- `prove_guida.py:144-147`: `t.split('data-guida="giorno-stampa"')[1].split('</div>\n    </div>')[0]`. Dipende dagli **a capo e dai rientri** di `griglia.html`: basta spostare la tendina e la prova cade.
- `prove_guida.py:149-160`: le guide della pagina.
  - Giorno: `fasce-turno`, `stampare-giornata`, `griglia`.
  - Appuntamento: `prenotare`, `stato`, `spostare`, con la condizione `#cerca_paziente`.
- `prove_funzioni.py:1364-1370` (`ec_elenco`): regex `<span class="conteggio">([^<]+)</span>` sull'Elenco. Una striscia con i numeri in elementi separati la fa cadere.
- `prove_personalizzazione.py:633`: regex `href="([^"]*)">Torna alla giornata`. Dopo `href` non ci può essere un altro attributo, e prima del testo nessuna icona.
- `prove_anagrafiche.py:160, 617` e `prove_gemelli.py`: `id="modulo-appuntamento"`.

**Prove che leggono testi e struttura delle pagine:**
- `prove_143.py`:
  - :426-430, testo della Sala: `'1/5'`, `'In sala: Borrelli (1), Mancini (1)'`, `'7 giorni'`;
  - :339, `'Checklist pre-operatoria'`, cioè l'h2 dell'appuntamento;
  - `campi-degenza`.
- `prove_112.py:582, 632`: il testo della pagina Sala usato come gemello.
- `prove_18.py:1060-1078`: Oggi, `'In servizio oggi'` e `'Fittizi Ada 21:00–07:00 da ieri · Degenza'`. Conta l'ordine dei testi nel `li`.
- `prove_18_browser.py:505`: `.in-servizio` deve essere uno solo.
- `prove_110.py:1455-1484` (`e_settimana`): `Tabella('agenda-medico')`, `class="fasce-miste"`, `'08:45<span> libero</span>'`.
- `prove_110_browser.py:138-150`:
  - il testo delle `option` di `select[name=medico]` contiene il cognome;
  - `table.agenda-medico` con `tBodies[0]`;
  - `a.posa.con-ora` comincia con `08:45`.
- Appuntamento:
  - `prove_17.py` e `prove_17_browser.py`: `esito-cf`, `luogo_nascita_testo`, `suggerimenti`;
  - `prove_15_browser.py`: `cerca_paziente`;
  - `prove_145.py`: `#incasso`;
  - `prove_14.py`: `'Serie di'`;
  - `prove_15.py`: `'Manda il promemoria'`.

**Animata:**
- `prove_animazioni.py`:
  - :28-29, Oggi, `.scheda-oggi` con animazione e ritardo;
  - :31-35, checklist della Sala;
  - :51-52, `.in-servizio li`.

### G. Animata: selettori oltre la griglia

**`animazioni.js`:**
- `table.griglia, table.lista-giorno`: l'entrata dal lato giusto vale **anche per l'Elenco**;
- `table.elenco tr` prende `.entra`: Elenco, Sala, Oggi (`table.elenco.compatta`) e i messaggi dell'appuntamento;
- `table.mese td, table.settimana tbody td`;
- `.scheda-oggi`, `ul.righe-oggi li`, `.in-servizio li`, `.appunti-giorno li`;
- `p.vuoto`: l'icona animata viene scelta dal testo che comincia con «Nessun» o «Niente»;
- `.pagina h1`;
- `.conto-checklist`;
- `.bottone, .passo`: l'onda al clic.

**`animazioni.css`:**
- `.anim .pagina` (appuntamento) e `.anim .campo input/select/textarea`;
- `a.cella-sett`, `a.giorno-mese`, `table.mese td`, `table.settimana td`;
- `.checklist-voce`, `.conto-checklist`;
- `.scheda-oggi`, `.in-servizio .al-lavoro`.

Se `appuntamento.html` lascia `div.pagina` (la tappa 9 vuole che sparisca ovunque), l'appuntamento perde
l'animazione d'entrata.

### H. Altezza misurata anche nelle altre viste

Misure a 1366×657 (`revisione/misura2.js`):

| Vista | Dove comincia oggi | Dove comincia nella tavola |
|---|---|---|
| Settimana | 155 px | 384 px |
| Mese | 155 px | 384 px |
| Elenco | 198 px (294 con la nota) | 561 px |

Il Mese della tavola è alto 1567 px, cioè circa 260 px per ogni settimana: a 1366×657 se ne vede circa una, oggi tre
intere.

Quindi il problema dell'altezza non è solo del Giorno. La stessa intestazione più bassa (conti accanto al titolo,
barra su una riga) serve in tutte e quattro le viste. Nel Mese bisogna anche decidere quante righe di medici mostrare
in ogni casella.

### I. Modelli dimenticati

`posti_letto.html`, `chirurghi.html`, `sposta.html`, `sposta_blocco.html`, `sposta_avvisi.html` e `serie.html`:
- si aprono dalla Sala e dall'appuntamento;
- usano `div.barra` (posti letto, con data-tasto precedente, successivo e oggi) oppure `div.pagina`;
- non sono in nessuna tappa. Sposta e Serie sono fra le «32 pagine senza tavola» (`piano/letture.json:805`);
- la fine della tappa 9 chiede che nessun modello usi più `div.barra` o `div.pagina`.

Bisogna decidere: o si fanno nella tappa 5 con i pezzi comuni (stessa area, stesse prove: `prove_143`, `prove_14`
per sposta e serie), o si scrivono nella tappa 9.

Restano fuori dalla tappa 5:
- `disponibilita.html` e `da_confermare.html`: tavole Seg6 e Seg2, tappa 6;
- i fogli `stampa`, `agenda_medico`, `lista_operatoria` e `promemoria`: non cambiano.

### J. Testi nuovi delle tavole non segnalati (letti con `revisione/testi.js`)

**Settimana:**
- la legenda «bianco: c'è un turno · grigio: nessun turno · azzurro: oggi · libere: solo da oggi in poi»;
- l'etichetta nascosta «Tutte le stanze o l'agenda di un medico»;
- la riga «la settimana così com'è, su un foglio A4 orizzontale»;
- gli aria-label delle caselle, per esempio «lunedì 16 novembre, Ambulatorio 1: Gallo 08:00–14:00, 6 app.. Apri il giorno». Nella tavola c'è un **refuso: «app..»**;
- gli aria-label delle intestazioni, per esempio «Apri lunedì 16 novembre: 12 appuntamenti».

**Mese:**
- la legenda «grigio: mese prima e dopo · grigio chiaro: chiuso di solito · arancio chiaro: festivo o chiusura · bordo: oggi · «Sala 5»: 5 interventi · «sala libera»: chirurghi senza interventi»;
- l'etichetta nascosta «Medico»;
- la riga «il calendario così com'è, con la finestra di stampa»;
- gli aria-label, per esempio «lunedì 26 ottobre, 13 app.: apri il giorno», e il title «Apri il giorno».

**Elenco:**
- l'intestazione nascosta «Cambia lo stato» nella colonna dei bottoni, che oggi è un `th` vuoto;
- gli aria-label «Non presentato: <paziente>»;
- la riga «apre la Stampa del giorno in una nuova scheda»;
- «Griglia» che diventa la linguetta «Giorno». È nei «Nomi unificati» di `SPEC-AGENDE.md:116`, ma **non** fra le cinque correzioni di `piano2/s1.md`. Va scritta nell'elenco dei cambiamenti approvati, oppure va approvata.

**Tutte e quattro le viste:** «Struttura» come etichetta nascosta e `aria-label` «Giorno precedente», «Settimana
precedente» e simili. Oggi le stesse parole sono nel `title`. Con i segni nuovi sono differenze da approvare.

### K. «Prima disponibilità» in Settimana e Mese: il giorno

Secondo `piano2/s7.md:31`, «Nuovo appuntamento» e «Prima disponibilità» propongono oggi se è nel periodo, altrimenti
il primo giorno. `viste.disponibilita` accetta già `dal=`, e una data passata diventa oggi (`viste.py:347`).

La bozza del collega mette per «Prima disponibilità» solo `struttura=`, cioè lo stesso indirizzo del menu. Così per
una settimana futura cerca da oggi. Se vale la proposta di s7, serve `dal=<primo giorno>`: è una forma di indirizzo
nuova da scrivere nell'elenco.

---

## 4. I limiti dello strumento di confronto per questa tappa

1. **Le regole valgono per tutte le pagine.** `sostituisci testo ^Questa settimana$ → Oggi` cambierebbe anche il
   principale dove quella parola deve restare:
   - i periodi del Riepilogo del periodo (`ambulatori.py:1255-1256`, «Questa settimana», «Questo mese»);
   - le Statistiche (`viste.py:390`, «Questo mese»);
   - la Pianificazione e la Programmazione di Ambulatori (`ambulatori_settimana.html:12`, `ambulatori_mese.html:12, 25`), che cambiano solo nella tappa 8.

   Ne verrebbero differenze false in quelle pagine. Serve un ambito per indirizzo nella regola, per esempio una
   quinta colonna con l'espressione del percorso. Lo stesso vale per «Altre esportazioni», che resta nel Mese di
   Ambulatori fino alla tappa 8.
2. **L'ordine.** Spostare «Nuovo appuntamento» dopo «Stampa e scarica» (e Chiudi la giornata dopo le linguette
   nell'Elenco) cambia l'ordine di segni, testo e collegamenti. Né `aggiunto` né `sostituisci` lo approvano.
3. **Un collegamento uguale a uno del menu** (`/disponibilita?struttura=N`):
   - con la versione salvata (HEAD) `aggiunto collegamenti` non lo approva, perché lo tiene: c'è già nel principale;
   - con la versione in corso (`togli_aggiunti` con difflib) sì.

   Prima della tappa 5 va controllata la versione finale.
4. **I segni nuovi.** Con `role`, `aria-label` e `aria-current` fra i segni, ogni nome della tavola diventa una
   regola `aggiunto segni`, con il suo perché: «Viste dell'agenda», «I conti del giorno», «Griglia del giorno»,
   «Struttura», «Giorno precedente», `aria-current=page` sulla linguetta…

---

## 5. Rischi in più

- **La guida fra la tappa 5 e la 10.** `guida.py:514, 523` dice ancora «Altre esportazioni» e «Vai a oggi». Il
  pacchetto che Giovanni vede dopo la tappa 5 mostrerebbe parole che non ci sono più. Sono parole già approvate: si
  possono correggere nella tappa 5, oppure si scrive nell'elenco del pacchetto che la guida si aggiorna nella tappa 10.
- **«libero» nel tema scuro.** Oggi `a.posa` è trasparente in tutti e due i temi. Solo `con-ora` ha un colore scuro
  (`tema-scuro.css:26`). Serve un gettone scuro anche per «libero», con contrasto di almeno 4,5:1.
- **`confronta_rami.py`, `cambiamenti_approvati.txt`, `_menu.html` e `base.html` non sono salvati** e stanno cambiando
  (tappa 1). Chi fa la tappa 5 deve ripartire dalla loro versione finale, non da questa revisione.

---

## Ciò che ho verificato e regge

**Misure:**
- la griglia della tavola del Giorno comincia a 618 px su 657 (misurato di nuovo: 618);
- oggi comincia a 244 px.

**Il markup di `griglia.html`:**
- `th.ora` con l'ora in ogni riga;
- `tbody.fasce-miste` con `--riga`;
- `<th>{{nome}}\n<span class="sotto">` senza attributi (`prove_anagrafiche.py:461`);
- la tendina della struttura sempre presente nel Giorno; nell'Elenco e in Oggi c'è solo con più strutture.

**I colori e il CSS:**
- la linea dell'ora dell'animata (`animazioni.js:153-199`: `tBodies[0].rows`, `cells[0]`, `closest('.telaio')`);
- «libero» trasparente, con lo span nascosto in `fasce-miste` (`stile.css:193-235`);
- la Sala viola già usata dal programma (`#EFE9F7`, `#4B3474`, `#6B4E9B`, `stile.css:781, 978, 997`).

**Prove e tavole:**
- le righe di prova citate per la griglia: `prove_143:329, 339, 878`; `prove_funzioni:410`; `prove_14:1638, 1660`; `prove_110_browser:98-108`;
- la tavola Oggi ha funzioni che il programma non ha («In visita», «Incassa», «in sala d'attesa»).
