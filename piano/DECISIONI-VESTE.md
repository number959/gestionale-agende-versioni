# Decisioni per la veste nuova (tappe 1-bis–9), prese il 22/11/2026

Giovanni ha chiesto di completare tutto seguendo il piano senza fermarsi a ogni tappa. Le 84 domande aperte della
ricognizione (scratchpad/veste-*/RICOGNIZIONE.json e REVISIONE.md) sono decise qui con il criterio del piano: stessi
indirizzi, moduli, campi, bottoni, dati; parole cambiate solo se approvate; niente funzioni nuove nella base. Ogni
decisione va nel resoconto per Giovanni (che può cambiarla) e, se cambia testo o segni, in
strumenti/cambiamenti_approvati.txt con il perché.

## Il lanciatore (vale da subito, tappa 2)
- La cornice (menu, barra in alto, linguette, campanella, zona dei messaggi) sta in contenitori con `data-cornice`:
  confronta_rami.py la confronta UNA volta a parte (le voci: parola + indirizzo + data-tasto/data-guida) e la toglie dal
  confronto di ogni pagina.
- Collegamenti, segni e righe di testo di una pagina si confrontano come INSIEMI CON LE QUANTITÀ (senza ordine): la veste
  sposta le cose. `--con-ordine` per vedere anche gli spostamenti. I moduli restano confrontati per indirizzo, metodo e
  campi (campi senza ordine, ma con le quantità).
- Le 8 pagine che si stampano (mese, settimana, cassa, cassa_mese, ambulatori_settimana, ambulatori_mese,
  ambulatori_riepilogo, mese dei turni) restano IDENTICHE in stampa: dalla tappa 2 fogli_pdf.py le confronta in PDF come i
  9 fogli. In stampa la testa di oggi (titolo, marchio) torna con una regola di stampa (revert-layer nei mattoni o un
  pezzo solo-stampa che ripete il titolo di oggi; il testo doppio va nell'elenco approvato).
- Foto prima/dopo: strumento a parte strumenti/foto_pagine.py (due programmi sugli stessi dati, ora ferma), non dentro il
  lanciatore.

## Mattoni (1-bis)
- Strato: soluzione B (gli @import … layer(vecchio) dentro un <style> di base.html, nell'ordine di ogni variante); anche il
  :root con il colore della struttura dentro lo strato. Fogli da stampare (foglio_carta): link di oggi, senza strato.
- Prefisso unico delle classi nuove: `v-` (niente vn-). Bordo dei campi #B3BDCB. Testo del corpo 14px.
- Varianti del colore della struttura (tinta, bordo, profondo, testo) in marchio.tema già nella 1-bis, senza cambiare
  le 5 variabili di oggi.
- Le correzioni chieste dalle altre aree: due .v-piccolo con nomi diversi (bottone/testo), margini azzerati di
  table.v-tabella, p.vuoto, form.ricerca, ul.numeri; icone chevron-down e id-card; striscia_numeri con più parti.
- Catalogo: gestionale di prova a sé, strumenti/catalogo_pezzi.py (/catalogo-pezzi), fuori dall'eseguibile.
- Browser: @import con layer() vuole Chrome/Edge 99+. In clinica usano Chrome (aggiornato da solo): rischio scritto nel
  resoconto, da confermare con la telefonata prima di pubblicare la 1.13.
- Animata: le animazioni agganciate a .bottone/.passo, table.elenco, ul.numeri, .pagina h1 si allargano ai pezzi v- nella
  tappa di ogni area.

## Cornice (2-3)
- Menu a sole icone sotto 1200 px (nome nel title e per i lettori di schermo); nel menu stretto, al posto del logo, le
  iniziali della struttura. A 1366×657 il menu scorre per conto suo; voci da 40 px.
- Le righe piccole delle tendine di oggi diventano il title delle linguette, in tutte le aree (anche Ambulatori).
- Le linguette stanno sotto l'h1 della pagina (blocco linguette nella testa della pagina), come nelle tavole.
  Rinvio (revisione della tappa 2): nella tappa 2 stanno ancora in cima al contenuto, sopra l'h1 (blocco «linguette» di
  base.html), perché le teste delle pagine sono quelle di oggi; vanno sotto l'h1 nelle tappe 4-9, area per area, con la
  testa nuova. Da dire a Giovanni, che può chiederle sotto l'h1 già prima.
- Logo della struttura: nel menu; quello della pagina si nasconde a schermo e resta in stampa.
- Messaggi in basso: gli errori restano finché si chiudono; gli «ok» spariscono dopo 6 secondi (restano nella zona per
  i lettori di schermo fino al cambio pagina).
- Campanella: numero rosso per gli avvisi rossi; il pannello si apre da solo come la notifica di oggi (una volta ogni 2 ore).
- Domande: una sola <dialog> al centro (piano), con il bottone del sì che dice il verbo («Elimina», «Annulla il pagamento»,
  «Togli», «Ripristina») e il no «No, torna indietro» (così non si scontra con i bottoni che si chiamano «Annulla»).
- L'alert della checklist non salvata diventa un messaggio rosso in basso.
- Server senza risposta=si: «Non è stato cambiato niente: per farlo, usa il bottone e rispondi sì alla domanda.»
- Scheda di Dove si fa: posizione corretta già nella tappa 2, con una prova «la scheda è dentro la finestra».

## Testi delle tavole
- APPROVATI: la testa di ogni area (riga piccola «Area · struttura» o «Configura · tutte le sedi», h1 con il nome
  dell'area, sottotitolo della tavola), anche sulle pagine senza tavola della stessa area; le legende; le intestazioni di
  colonna oggi vuote («Cambia lo stato», «Apri o cerca posto»); i titoli delle sezioni delle tavole (es. «Visite e
  appuntamenti», «Luoghi di nascita», «I numeri del periodo»); le righe piccole delle voci di «Stampa e scarica»; il
  percorso (Pazienti › Nuovo paziente…); le frasi che descrivono i comandi spostati (es. «Altre esportazioni» → «Stampa e
  scarica», «menu Ambulatori» → linguette), anche nei passi della guida; «Pagina non trovata» e le pagine 405 e 400 in
  italiano; il placeholder della nota del giorno con un nome inventato («Gallo» al posto del medico vero).
- NON fatti: parole delle strisce cambiate di posto («915,00 € incassati»: resta «incassati 915,00 €»); conti nuovi che oggi
  la pagina non ha («3 appunti aperti», «7 pagamenti»); errori ripetuti in rosso dentro il modulo; il campo file disegnato
  in italiano; testi tolti (es. la parentesi del Listino resta); aria-label che cambiano il nome letto di bottoni e
  collegamenti che hanno già un testo (si usa aria-describedby se serve). Gli aria-label SOLO per ciò che oggi non ha un
  nome (regioni, nav, tendine senza etichetta).
- Parole delle linguette della Cassa: «Giorno», «Mese», «Listino», «Tariffari» (come oggi); accese da request.endpoint.

## Aree
- Agenda (5): «Nuovo appuntamento» e «Prima disponibilità» anche in Settimana, Mese ed Elenco, con data-tasto="nuovo"; giorno
  proposto: oggi se nel periodo, altrimenti il primo giorno; con il filtro di un medico, quel medico. Tasto T su «Oggi»
  anche in Settimana e Mese (data-tasto="oggi"; oggi l'aiuto lo promette e non va). Testa compatta (conto accanto al
  titolo, comandi su una riga, nota chiusa se vuota): a 1366×657 almeno le mezz'ore di oggi meno una. «Stampa» con
  window.print anche dentro la tendina (gestionale.js allargato a .tendina button). Oggi: stesso contenuto in schede
  bianche. Sala: «Stampa e scarica» con «Stampa la lista operatoria» (parola di oggi), niente Excel nuovi; «Un giorno /
  Prossimi 7 giorni» come linguette con le stesse parole; checklist in una cella come oggi (le colonne per voce in M7).
- Ambulatori/Dove (8): matrice a 1366: menu ridotto a icone su quella pagina e testo delle celle più piccolo (mai sotto
  11 px); con 7 giorni scorrimento laterale della sola matrice con la prima colonna ferma. Cruscotto: h1 «Riepilogo del
  periodo» con «Torna al riepilogo live». Dove senza mappa: ordine di oggi (si riordina in M3).
- Turni (7): colonne del mese giorni 24 px, Ore 56, Notti/Fest./Ass. 30, nome elastico; la riga dei giorni resta ferma
  scorrendo la pagina; classi lungo-3/lungo-4 nei due disegni della cella; riga in modifica azzurra; i due difetti trovati
  (scheda della persona che scorre di lato di 805 px; scala delle ore del Giorno che non resta ferma) si correggono con una
  prova e un gemello, e si scrivono nei LEGGIMI.
- Pazienti/Statistiche (4): titolo diviso di Statistiche approvato; righe delle tabelle compatte (~40 px) per vedere quasi
  le righe di oggi; sotto 900 px una colonna; Paziente.dc.html superata da Paz2-Scheda.
- Configura (9): testa approvata anche nelle pagine secondarie; «Tasti rapidi» resta un collegamento; la settima linguetta
  è «Aree e accessi», arrivata con l'unione dell'accesso dagli altri PC (22/11: registrata da accessi.py su una sezione
  sua, solo sul PC principale; dalla rete il menu mostra solo le pagine dell'utente).
