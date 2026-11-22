# Revisione della ricognizione «cornice» (tappe 2 e 3)

Ho controllato sui file veri: ramo `ccr-interfaccia`, partendo da `b64cac2`. Durante la revisione è arrivato il
commit `5046da4`, che porta i passi della guida con `data-guida`, `prove_guida.py`, i cambiamenti approvati in
`confronta_rami.py` e il nuovo `strumenti/cambiamenti_approvati.txt`.
Non ho modificato il repository. I miei esperimenti stanno in `veste-cornice/revisione/`:

- `tasti_dialog.py`: i tasti rapidi con una `<dialog>` aperta;
- `tendina_aside.py`: una tendina dentro un menu che scorre;
- `stretto.py` e `tavola-stretta-*.png`: le tavole a 390, 420 e 683 px;
- `sticky.py`: le intestazioni ferme quando la colonna ha un `overflow`.

La ricetta Jinja della sezione A1 l'ho provata in Python.

---

## A. Errori da correggere nella ricognizione

1. **`<main id="contenuto">` nella bozza.** Oggi l'elemento è `<main id="principale">` (`templates/base.html:27`, tappa 1,
   commit `91a02d6`). Nessun file usa l'id, ma cambiarlo va contro «stessi id»: si tiene `principale`.
   Ricetta provata: il blocco del menu viene scritto prima e non esce nella pagina; poi la pagina lo legge con
   `self.menu()|trim`. Il corpo sta fuori dall'`if`. Funziona con le pagine normali, con i fogli (blocco vuoto) e con
   `riepilogo_live`, con e senza schermo.
   ```jinja
   {%- if false %}{% block menu %}{% include "_menu.html" %}{% endblock %}{% endif -%}
   {%- set _menu = self.menu()|trim -%}
   {%- if _menu %}<div class="vn-cornice"><aside …>{{ _menu }}</aside><div class="vn-colonna"><header …>…</header>{% endif -%}
   <main id="principale">…{% block corpo %}{% endblock %}</main>
   {%- if _menu %}</div></div>{% endif %}
   ```
   Le variabili che `_menu.html` calcola (`_sid`, `_data`, `_sez`) non arrivano fino a `base.html`: la barra deve
   calcolarle di nuovo.

2. **«Contrasto con il piano» sulle domande: è sbagliato.** `piano2/s7.md:30` ha già la decisione aperta «Domande ed
   errori» (prima della tappa 3):
   - si rinuncia con «Annulla», oppure con «No, torna indietro» quando il verbo è «Annulla…», come nelle tavole;
   - l'errore va in basso e, se il modulo è uno solo, anche sopra.

   La finestra unica `<dialog>` resta. Il bottone del sì prende il verbo della tavola (per esempio «Elimina»,
   «Annulla il pagamento»), non «Sì». Anche la proposta «errori fissi finché si chiudono» va confrontata con questa
   decisione.

3. **«La tendina Aiuto, per la decisione…»: la decisione non c'è ancora.** In `s7.md:28` la casella «Quello che le
   tavole non disegnano» è ancora aperta: è una proposta.

4. **I selettori `nav.menu […]` di guida.py sono superati.** Nel lavoro in corso (T1 guida) i passi usano già
   `[data-guida="…"]` senza `nav.menu`. C'è anche una regola nuova (`gestionale/CLAUDE.md:149-150`,
   `prove_guida.py:162-178`): ogni nome di `data-guida` usato dalla guida deve essere scritto in un modello
   `templates/*.html`. Se `menu.py` tiene `guida='menu-oggi'` e il modello scrive `data-guida="{{ v.guida }}"`,
   11 nomi spariscono dai modelli e `prove_guida.py` cade. Due strade: i `data-guida` restano scritti nel modello
   (`_menu.html`, con un `if` per voce), oppure la prova legge anche `menu.py`. È da decidere nella tappa.

5. **Numeri di riga del ramo principale o vecchi.** Sul ramo i numeri giusti sono:
   - `app.py`: 849 (svuota-danneggiati, non 825) e 469 (elimina appuntamento, non 445);
   - `templates/impostazioni.html`: 104 (Ripristina, non 91);
   - `prove_112.py`: 759, 1231, 1246, 1973-1977, 2232, 2650-2657.

   Le altre righe di `domande.tsv` le ho rilette una per una: sono giuste.

6. **`prove_19.py:954-955` cade per due motivi, non solo per l'ordine degli attributi:**
   - la regola chiede `>Dove si fa</a>` subito dopo il tag: con l'icona dentro il link (`<svg…><span>Dove si fa</span>`)
     non trova più niente;
   - `'Strutture del gruppo' in corpo` su `/oggi`: con la bozza le linguette di Configura ci sono solo nelle pagine di
     Configura.

   Lo stesso vale per `strumenti/prove_installato.py:189`: la regola parte da `<a data-tasto="d" href=`, quindi
   `data-tasto` deve restare il primo attributo, prima di qualsiasi `class`.

7. **«Le 11 pagine senza menu non cambiano»: non del tutto.** Nella bozza la zona dei messaggi esce da `<main>` e la
   `<dialog>` va in tutte le pagine, fogli compresi. Le pagine senza menu cambiano anche loro, per il lanciatore
   (vedi B4).

---

## B. Quello che manca

### B1. Schermo del telefono (390 e 420 px): manca del tutto

La ricognizione guarda 683 e 1024 px. Il piano cita però la prova dello schermo stretto
(`s4.md:88` → `prove_110_browser.py:189-194`, a 420 px).

**Le prove che vogliono una pagina che non scorre di lato:**
- `prove_110_browser.py:189-194` (420 px, `/giorno`);
- `prove_112_browser.py`: 229-231 (390 px, esportazioni), 281-284 (riepilogo live), 314-317 (riepilogo del periodo);
- `prove_tariffari_browser.py:135-138`.

**Le prove che vogliono un riquadro dentro lo schermo:**
- `prove_112_browser.py:201-206`;
- `prove_18_browser.py:508-515`;
- `prove_191_browser.py:112-119`;
- `prove_19_browser.py:241-254`.

**Misure:**
- A 390 e 420 px tutte le tavole scorrono di lato (`scrollWidth` da 573 a 942 px; vedi `revisione/stretto.py`).
  Il menu da 72 px a sole icone non basta: restano 318 px, e la ricerca da 320 px non ci sta già da sola.
- `minmax(0,1fr)` da solo non impedisce lo scorrimento di lato (una tabella larga 900 px dà `scrollWidth` 972 a 420).
- `overflow-x: auto` o `hidden` sulla colonna rompe le intestazioni ferme: il `thead` finisce a -736 px
  (`stile.css:158, 1235, 1412, 1709`).
- `overflow-x: clip` tiene ferme le intestazioni ma taglia il contenuto, che non si raggiunge più.

**Proposta:** due soglie.
- Sotto circa 700 px il menu torna in alto, come oggi, su righe di icone, e la colonna ha tutta la larghezza.
  La ricerca si stringe (`flex: 1; min-width: 0`) e il percorso va a capo o sparisce.
- Fra 700 e 1100 px il menu resta a sole icone (72 px).

### B2. dove.js mette la scheda «sotto il menu»

`static/dove.js:175-180` calcola `top` della scheda da `document.querySelector('.menu').getBoundingClientRect().bottom`.
Con il menu a sinistra la scheda partirebbe dal fondo del menu, circa 700 px, cioè fuori da una finestra alta 657.
Anche `prove_19_browser.py:147-150` lo pretende.

Si rompe già nella tappa 2, anche se Dove si fa è della tappa 8: dove.js deve guardare la barra in alto (o 0), e la
prova deve dire «sotto la barra».

### B3. I tasti rapidi con la domanda aperta

Misurato (`revisione/tasti_dialog.py`): con la `<dialog>` aperta, ←, D ed E cambiano lo stesso pagina, perché
`gestionale.js:520-543` non sa niente delle finestre. Oggi `window.confirm` blocca tutto, quindi il problema non c'è.
Chi preme le frecce per passare fra «Sì» e «No» cambierebbe giorno.

**Cosa fare nella tappa 3:**
- `gestionale.js` esce subito se c'è un `dialog[open]` (vale anche per `finestra-schema` e `finestra-video`);
- `turni.js:845-848` controlla solo `finestra-schema` prima di Ctrl+Z: va aggiunta la domanda;
- Ctrl+Invio dentro la domanda clicca il `.primario` del suo modulo, cioè il sì (`gestionale.js:531`): il bottone
  del sì non deve avere la classe `primario`, oppure il tasto va fermato.

### B4. La `<form method="dialog">` in base.html cambia tutte le pagine per il lanciatore

Il `Lettore` di `confronta_rami.py` (righe 73-111) conta ogni `<form>` nei «moduli». Le regole «aggiunto» di
`cambiamenti_approvati.txt` guardano solo testi, mentre i moduli sono tuple: questa modifica non si può approvare.

**Proposta:** la finestra si crea in JavaScript la prima volta che serve, come fa già `guida.js` per `finestra-video`.
Così non ci sono moduli né testi nuovi in nessuna pagina.

### B5. Il lanciatore non sa dire «tolto»

`cambiamenti_approvati.txt` è in preparazione e ha solo «aggiunto» e «sostituisci». La cornice invece toglie molte
cose da ogni pagina:
- 14-16 collegamenti delle tendine;
- i testi `<b>` e `<small>`, che nelle tavole Seg e Conf diventano `title`;
- «Settimana» e «Mese» fuori dall'Agenda;
- `data-guida="menu-mese"` da circa 200 pagine.

**Serve una regola «cornice».** Il `Lettore` salta:
- nel principale: `nav.menu`, `#notifiche` e `#aiuto-tasti`;
- nel ramo: menu, barra e linguette, segnati con un attributo come `data-cornice`.

La cornice si confronta a parte: per ogni pagina, l'insieme degli indirizzi raggiungibili, cioè il menu più le
linguette della sua sezione.

Va bene invece il giro: segue solo i collegamenti del principale (`for nuovo in interni(percorso, la)`), quindi resta
uguale.

### B6. La campanella (tappa 3): decisioni che la ricognizione non prende

- **Memoria delle notifiche.** «Torna dopo 2 ore» (`notifiche-viste`, `gestionale.js:558-572`) e «al massimo 4»
  (`gestionale.js:633`) hanno senso solo per i cartoncini a scomparsa. Nel pannello serve un'altra regola: si
  mostrano tutte, e il numero conta quelle non chiuse (oppure quelle non viste). Va deciso.
  `prove_112_browser.py:246-253` («compaiono e risultano viste») va riscritta.
- **Lettori di schermo.** Oggi `#notifiche` ha `aria-live` (la regola è citata in `s2.md`); il pannello della bozza è
  una `section hidden` senza `aria-live`, quindi i nuovi avvisi non verrebbero più letti. Serve una zona `polite`
  nascosta con «N avvisi nuovi».
- **Riepilogo live.** `stile.css:644` nasconde `.notifiche` in `body.pagina-live`. Con la classe nuova la campanella
  resterebbe visibile ma vuota su `/riepilogo-live` senza schermo: va nascosta lì. Anche `prove_112_browser.py:274`
  legge lo stile di `#notifiche`.
- **prove_canarino.py.** `/riepilogo-live` senza schermo ha la cornice. Il pannello deve restare riempito da
  JavaScript, mai con testi scritti dal server, altrimenti il nome del canarino finisce sotto `/riepilogo-live`.
- **Foto e video della guida.** `genera_immagini_guida.py:115` e `genera_video_guida.py:92` nascondono `#notifiche`.
  Va nascosto anche il numero della campanella, che cambia ogni giorno.
- **Animata.** Nella tappa 3 vanno riscritti a mano, perché sono file della sola animata:
  - perdono senso `animazioni.js:312-335` (la barra di 15 secondi su ogni `.notifica`) e `animazioni.css:170-179`
    (l'entrata da destra);
  - `animazioni.js:127-131` aggiunge una spunta ai messaggi, ma il messaggio della tavola ha già la sua: sarebbero due;
  - le prove `prove_animazioni.py:94-103` e `prove_icone_animate.py:22-26`.

### B7. I messaggi in basso

- **La classe `.avviso`.** Ci sono 27 riquadri `.avviso` dentro le pagine (15 modelli, per esempio
  `importa_anteprima.html:97`) che non sono messaggi dopo un'azione. Lo stile del messaggio in basso va limitato alla
  sua zona (`.avvisi .avviso`, o una classe con il prefisso), mai su `.avviso` da solo.
- **Testo su una riga sola.** La tavola usa `white-space: nowrap`, ma i messaggi di oggi arrivano a 176 caratteri più
  le parti variabili (`invii.py:1869`, `invii.py:1820`, `aggiornamenti.py:797`). Su una riga escono dallo schermo già
  a 1366 meno 248 px. Il messaggio deve andare a capo, con una larghezza massima.
- **prove_sicurezza_browser.py.** `nella_zona` controlla con `get_by_text` che l'elemento trovato abbia la classe
  `errore`. Se il testo sta in uno `<span>`, come nella tavola, l'elemento trovato è lo span e la prova cade sugli
  errori. Il testo deve stare direttamente nell'elemento `.avviso`.
- **Id.** Non usare `id="messaggi"`: c'è già in `impostazioni.html:116` e `appuntamento.html:299`, e `prove_pagine.py`
  controlla gli id ripetuti.

### B8. Il menu troppo alto e la tendina Aiuto

- **Menu che scorre da solo.** Se il menu scorre per conto suo (`overflow-y: auto`), anche `overflow-x` diventa
  `auto`. La tendina Aiuto (`min-width` 270 px) viene tagliata a 248 px: misurato, il punto a x=255 è già `MAIN`.
- **Menu fermo.** La tendina si apre verso il basso (`top: 100%`) partendo da circa 650 px, quindi esce dalla finestra
  alta 657. `dentro()` (`gestionale.js:715-731`) la sposta solo di lato. `prove_tendine_browser.py` controlla
  proprio Aiuto a 1366×657, «fuori dallo schermo».
- **Proposta:** Aiuto si apre verso l'alto o a destra, con `position: fixed` o un popover, fuori dal contenitore che
  scorre.

### B9. In stampa

Nascondere il menu non basta: la griglia `248px + 1fr` lascia la colonna vuota, e le 8 pagine che si stampano
diventano più strette. Questo va contro la proposta `s7.md:29`, «identiche a oggi».

In `@media print`:
- `.vn-cornice { display: block }`;
- barra, linguette, campanella e `dialog` nell'elenco di `stile.css:843` e `951`.

### B10. La linguetta accesa per pagina, non per sezione

Una sezione copre più pagine:
- `giorno`: anche `appuntamento`, `segreteria.sposta` e `segreteria.sposta_blocco` (dal giro). «Giorno» resterebbe
  acceso e il percorso direbbe «Agenda › Giorno» su `/appuntamento`;
- `cassa`: `cassa_giorno`, `cassa_mese`, `listino` e `tariffari.elenco`. Nella tappa 6 le 4 linguette avrebbero una
  sezione sola, e accenderne una sola sarebbe impossibile.

**Proposta in menu.py:**
- la voce si accende per sezione;
- la linguetta si accende per `request.endpoint`;
- il percorso finisce con la linguetta solo se l'endpoint è il suo; altrimenti con il titolo della pagina
  (`self.titolo()`).

### B11. Le frasi che descrivono la cornice di oggi

`s2.md` ammette di cambiarle, ma vanno elencate e approvate:
- `guida.py:66` «Il numero arancione…»: nella tavola il numero è blu (#1C4184);
- `guida.py:140` e `:143` «Menu Mese»;
- `guida.py:156` «clic sulla casella Cerca nel menu»;
- `guida.py:232` e `:246` «Menu Segreteria → …»: vanno bene se si leggono come voce → linguetta;
- `guida.py:280` «una notifica in basso a destra, con Fatto e Domani»;
- `cose_da_fare.html:23` «compaiono come notifica in basso a destra».

Restano giuste `aiuto_stampa.html:20` e `esportazioni.html:42`.

Dove la tavola mette un testo nascosto («Cerca un paziente…» in uno span) si tiene invece l'`aria-label`, come oggi.
Lo span sarebbe un testo nuovo in ogni pagina.

### B12. Novità della tavola non segnalate

- Il link del logo verso `/oggi`: un collegamento nuovo in ogni pagina, il secondo verso Oggi.
- I «×» scritti come testo nei bottoni di chiusura: meglio un'icona con `aria-label`, così non c'è testo nuovo.

### B13. Le richieste che cancellano, anche fuori dalle prove

Anche `campagna.py:446-447` (elimina un appuntamento) e `campagna.py:586` (elimina una struttura, nei casi a sorte)
dovranno mandare `risposta=si`. Il file non comincia con «prove», quindi è facile dimenticarlo.

### B14. La condizione di menu.py e la richiesta dell'utente (dopo, nei moduli)

Il piano dice «tutto il programma» (`s7.md`: «Utenti e permessi: proposta no»). La richiesta di questo giro però è
«quale modulo sugli altri PC, a quale utente». La tappa 2 non deve farlo, ma conviene preparare l'aggancio:
- la condizione è una funzione della richiesta (PC o utente), calcolata una volta per pagina;
- da quella funzione passano anche le linguette, il link nascosto della E e i tasti G, E, C e D;
- il server rifiuta le pagine negate con lo stesso controllo, perché nascondere una voce non protegge niente.

Va chiesto a Giovanni prima della tappa 2 («se la risposta arriva prima della tappa 2, aiuta a fare il menu»).

---

## C. Cose della ricognizione che ho verificato e che tengono

- 25 `confirm(` e 1 `alert(` nei modelli e nei `.js`; 22 domande con `risposta=si`; le righe di `domande.tsv` sono
  giuste tranne `impostazioni.html` (vedi A5). È vero anche quello che dice su `dove.js:291` (il JSON di «Annulla»).
- Il tasto E su un `<a hidden>` apre la pagina (provato di nuovo).
- 211 pagine con il menu e 9 senza; in ognuna si accende una voce sola. Le sezioni della bozza coprono tutte le
  `sezione=` del programma.
- Restano valide le misure sulle regole vecchie (`perdite_menu.py`) e sull'altezza del menu; la scelta della tavola
  Nefro invece di `Main.dc.html`; le icone Lucide locali.
