# Revisione della ricognizione «segreteria-cassa» (tappa 6)

Revisore scettico, 22/11/2026, ramo `ccr-interfaccia` (HEAD `878f2eb` più le modifiche non salvate della tappa 1 in
`confronta_rami.py` e `cambiamenti_approvati.txt`). Il repository non è stato toccato.

Come ho controllato:
- due copie congelate del programma in `veste-revisore-seg-cassa/`: `oggi/` (l'albero di lavoro di adesso) e `bozza/`
  (la stessa più `_pezzi.html` della 1-bis e le bozze `_area.html`, `conferme.html`, `chiusura.html`, `cassa.html`);
- dati di `strumenti/demo.py`, lo stesso database copiato due volte, due server (5273 oggi, 5274 bozza; ora spenti);
- il Lettore e le regole di `cambiamenti_approvati.txt` dell'albero di lavoro (`confronta.py`, `diff_testo.py`), i segni
  e gli id di ogni pagina (`segni_oggi.py`), `prove_guida.py` sulla copia con le bozze, la posizione delle righe nelle
  tavole a 1366×657 (`y_testi.js`, `misura.js`).

Quello che regge: moduli e campi identici nelle tre bozze (misurato); collegamenti di Conferme e Chiusura identici e
nello stesso ordine (misurato); le tre frasi approvate e il difetto vero «2 appuntamenti segnati come non presentato.»
(da `segreteria.py:117-119`); le due righe di `prove_15.py` (1398 e 1517) da cambiare nel primo passo.

---

## 1. Errori: cose dette che sul ramo di adesso non sono vere

**E1. Le bozze perdono 4 `data-guida`, e `prove_guida.py` cade.**
Le bozze sono delle 03:38–03:55. Il commit `5046da4` delle 04:28 («i passi della guida indicano i punti con
data-guida») ha messo i nomi nei modelli e cambiato `guida.py`. Le citazioni della ricognizione sono quindi vecchie:
`guida.py:235-237` (`.contatti-rapidi`, `.pulsanti-stato`), `:247` (`button[value="arrivati"]`), `:256-261`
(`textarea[name="testo"]`, `a.bottone.primario`) e `:476` (`form.in-linea`). Adesso i passi puntano a
`[data-guida="…"]` (`guida.py:233-277, 474-478`).

Misurato con il Lettore, bozza contro oggi:

| pagina | segni che la bozza perde |
|---|---|
| `/chiusura/2026-11-17`, `/chiusura/2026-11-20` | `data-guida=chiusura-arrivati` |
| `/cassa/2026-11-17`, `/cassa/2026-11-19`, `/cassa/2026-11-20` | `data-guida=cassa-mese`, `cassa-stampa`, `cassa-incassa` (uno per bottone) |

Con le bozze `python prove_guida.py` dà:
`ROTTO … prove_guida.py:175 · chiusura passo 2: data-guida che nessun modello ha: ['chiusura-arrivati']`.

Correzione:
- `data-guida="chiusura-arrivati"` sul bottone `value="arrivati"`;
- `guida='cassa-mese'` sulla linguetta Mese (`linguette()` accetta `v.guida`);
- `data-guida="cassa-stampa"` su «Stampa la chiusura di cassa»;
- `data-guida="cassa-incassa"` sui bottoni dei metodi.

Nelle pagine senza bozza i nomi da tenere sono nella tabella del punto M4.

**E2. «Cambiano solo l'intestazione e ‹ ›» non è completo.** Righe di testo misurate (`diff_testo.py`):
- Conferme: «3 da confermare su 3» diventa due righe, «3» e «da confermare su 3». La striscia divide numero e parole,
  quindi anche questo cambio va approvato.
- Cassa del giorno: le righe passano da 197 a 202.
  - «Cassa · martedì 17 novembre 2026» compare due volte: h1 della testata solo-stampa e h2 a schermo. Il Lettore
    legge anche quello che il CSS nasconde.
  - «incassati 330,77 €» resta nella testata di stampa e in più compare diviso, «incassati» e «330,77 €».
  - «Tariffari» diventa «Tariffari dei medici».

**E3. Segni nuovi, non approvati.** Sono in tutte e tre le bozze: `aria-label=Giorno precedente`,
`aria-label=Giorno successivo` (dal pezzo `passo`) e `aria-label=Struttura` (sulla tendina). Il Lettore
dell'albero di lavoro (`SEGNI` con role, aria-label, aria-current, data-prova) le conta come differenze. Servono
righe in `cambiamenti_approvati.txt`, con il via:
- quella delle frecce va scritta una volta per tutti i 18 modelli (veste-mattoni/REVISIONE.md:119-124);
- quella di «Struttura» qui.

**E4. Le linguette della Cassa: l'ordine nuovo dei collegamenti oggi non si può approvare.** Le regole hanno solo
«aggiunto» e «sostituisci», e la regola «aggiunto» lavora con difflib: un collegamento che c'era e ora manca conta
sempre. Sulla cassa la bozza mette Mese, Listino e Tariffari prima di ‹ ›, e per il Lettore quei tre risultano tolti
(misurato: 54 collegamenti contro 55, 3 tolti e 4 aggiunti). Le soluzioni possibili:
- la regola «cornice» proposta in `veste-cornice/REVISIONE.md:135-150` (B5): le linguette segnate, per esempio con
  `data-cornice`, che il Lettore salta e confronta a parte. Oggi `_area.html` non segna niente;
- oppure le linguette nel DOM dopo i comandi di oggi.

Senza una delle due, la tappa non chiude «senza differenze fuori dall'elenco».

**E5. Da confermare: l'ordine delle parti.** La ricognizione scrive «Da oggi in poi» → «Giorni passati» e «Senza
giorno». Nel modello di oggi l'ordine è Giorni passati → Da oggi in poi → Senza giorno → Chiusi di recente
(`da_confermare.html:71-75`). Si tiene questo: con l'altro cambiano l'ordine del testo e dei collegamenti.

**E6. Le bozze sono sulla pagina di oggi, ma la tappa 6 parte dopo la 2 e la 3.**
- Le bozze tengono `onclick="return confirm(…)"` (cassa «Annulla», «Elimina» di Da confermare, Da fare, Lista
  d'attesa, tariffario). La tappa 3 li toglie tutti e aggiunge `risposta=si` (s4.md:96-100), e con questo cambiano
  anche i moduli.
- La tappa 2 mette il logo nel menu (s4.md:85).
- Le bozze vanno quindi rifatte sui modelli che escono dalle tappe 1–3. Lo mostra già E1.

**E7. `testa_segreteria(approvata=true)` e `testa_cassa(approvata=true)`.** Il valore di partenza fa entrare i testi
non approvati. Va messo `approvata=false`, e acceso solo con il via.

**E8. Animata: mancano tre agganci del CSS e uno del JS.** La ricognizione cita `animazioni.js:61, 70, 119, 135`.
Mancano:
- `animazioni.css:35`: l'entrata della pagina vale per `.pagina` e `.barra`, che le bozze tolgono (diventa
  `.v-pagina`);
- `animazioni.css:40-41`: con ‹ › entra da destra o da sinistra `.barra .giorno` (h1.giorno), che sparisce;
- `animazioni.css:109` e `animazioni.js:96`: `ul.numeri li` scalati uno dopo l'altro.

Senza questi agganci, in Conferme, Chiusura e Cassa l'animata perde l'entrata e lo scorrimento di lato. La regola è
che le animazioni si adattano nella stessa tappa (s2.md, «Due cartelle»).

## 2. Mancanze

**M1. Incassi del mese è una delle 8 pagine che si stampano** (s7.md:29, s4.md:88), come la cassa del giorno. Serve
lo stesso lavoro:
- testata di carta con il logo, «Incassi · mese» e «X € in N pagamenti» solo in stampa;
- `v-stampa-come-oggi`;
- confronto in PDF.

La striscia della tavola Cassa2 («20.460,00 € incassati», «185 pagamenti») cambia le parole di oggi «X € in N
pagamenti» (`cassa_mese.html:8`): sparisce «in», «incassati» è nuovo e l'ordine cambia. Questo va approvato.
Altrimenti restano le parole di oggi in una voce sola, come fa la bozza delle Conferme. Inoltre la macro locale
`euro(c)` (`cassa_mese.html:3`) ha lo stesso nome di `euro()` di `_pezzi.html`, come `tabella` in Da confermare:
importando il pezzo va rinominata.

**M2. Le quattro pagine senza tavola** (`attesa_scheda`, `attesa_per`, `tariffari_anteprima`, `tariffario`). La
regola è «pezzi comuni, tutto uguale; il lanciatore guarda le righe di testo» (s1.md:20, s4.md:60).
- Niente intestazione d'area: niente h1 «Cassa» o «Segreteria» e niente sottotitolo.
- L'h1 di oggi resta, con il suo `<small class="sotto-titolo">` (nome del file, «tariffario»).
- `_area.html` accende la linguetta Tariffari per tutto `tariffari.*`: le linguette in quelle pagine sono testo
  nuovo, a meno che non siano cornice (E4).

**M3. L'anteprima del tariffario il lanciatore non la vede**: ci si arriva solo caricando un file. La guardano:
- `prove_tariffari.py`;
- `prove_tariffari_browser.py:83-85` (`input[name="medici_0"]`, `select[name="prestazione_0_0"]`);
- un confronto a mano.

Il suo h2 contiene una casella e un campo di testo (`tariffari_anteprima.html:11-13`): `scheda(titolo=…)` scrive solo
testo, quindi quella testa resta scritta a mano.

**M4. Segni e id da non perdere, pagina per pagina** (misurati dentro `<main>` con `segni_oggi.py`):

| pagina | segni | id |
|---|---|---|
| /conferme | data-tasto precedente, successivo; data-guida stato-contatti, stato-pulsanti (da `_stato.html`) | — |
| /da-confermare | data-guida da-confermare-testo (sull'input), da-confermare-prenota (sul link Prenota); aria-label=Scegli | prenota-insieme |
| /chiusura/… | data-tasto precedente, successivo, oggi; aria-label Seleziona tutti, Seleziona; data-guida chiusura-arrivati | — |
| /cose-da-fare | data-guida cose-da-fare-nuova (sulla form), cose-da-fare-fatto (sul primo «Fatto») | — |
| /attesa | data-guida attesa-nuova (su «Aggiungi alla lista») | — |
| /attesa/nuova | — | cerca_paziente, suggerimenti, paziente-scelto, paziente_id, paziente, nome_paziente, telefono, email_paziente, operatore, prestazione, struttura_attesa, fascia, dal, entro, note |
| /cassa/… | data-tasto precedente, successivo, oggi; data-guida cassa-mese, cassa-stampa, cassa-incassa | — |
| /cassa/mese/… | data-tasto precedente, successivo | — |
| /cassa/listino | aria-label «Prezzo di …» per ogni riga | lista_convenzioni |
| /cassa/tariffari | data-guida tariffari-controllo, tariffari-carica, tariffari-nuovo: con `scheda(guida=…)` | — |
| /cassa/tariffari/N | data-guida tariffario-medici, tariffario-voci; tutti gli aria-label delle celle | nome, note |
| anteprima | data-guida anteprima-tariffario, anteprima-medici | — |

`/attesa/nuova` ha anche `.cerca-paziente` sul contenitore: serve a `stile.css:465` (position: relative) per mettere la
tendina `#suggerimenti` sotto il campo. In Tariffari restano `tr[data-medico]` e le classi `stato-tariffario-*`
(`prove_tariffari.py:459`, `prove_tariffari_browser.py:52-59`).

**M5. Prove che guardano l'HTML dell'area e che la ricognizione non elenca:**
- `prove_14.py:979-1001`: Chi chiamare, ordine «Primo» prima di «Terzo», `wa.me/39…`;
- `prove_14.py:1184-1190`: cassa e mese, `Altro…` 4 volte, totale nella pagina del mese;
- `prove_tendine_browser.py:170-173`: `/attesa/nuova`, `#suggerimenti button`;
- `prove_funzioni.py:1183-1190`: Prima disponibilità, `'Prenota' in t and '15:00' in t`. Se entra l'intestazione di
  colonna «Prenota» della tavola, il primo controllo non vale più niente: resta solo «15:00»;
- `prove_tariffari.py:459`;
- `prove_tariffari_browser.py:52-59, 83-85`;
- `prove_animazioni.py:22` (le pagine dell'area aprono con `html.anim`) e `:92-93` (`button:has-text("Aggiungi")`
  su /cose-da-fare: un solo «Aggiungi» nella pagina);
- `prove_guida.py`: ogni nome dei passi deve stare in un modello.

**M6. Testi nuovi delle tavole non segnalati** (si aggiungono solo con il via):
- Seg5 Lista d'attesa: l'intestazione della colonna azioni «Apri o cerca posto» (oggi `<th></th>`, `attesa.html:17`).
- Seg6 Prima disponibilità: l'intestazione «Prenota» (oggi `<th></th>`, `disponibilita.html:33`).
- Seg1: aria-label nuovi «Conferme di venerdì 20 novembre 2026», «I conti delle conferme», «Pagine di Segreteria»,
  più uno per riga sui bottoni (`r.confermaAria`, `r.disdiciAria`).
- Cassa3 Listino:
  - l'aria-label «Togli la tariffa»;
  - la tavola toglie anche «Cassa del giorno ·» e «Tariffari dei medici» dal sottotitolo, non solo «(prezzi diversi
    per medico, pacchetti, da Excel)». I due collegamenti possono sparire senza differenza solo perché le linguette
    Giorno e Tariffari portano allo stesso indirizzo: il Listino non manda `data_menu`, quindi Giorno =
    `cassa_giorno(oggi_iso, sid)`, come oggi. Il testo tolto va approvato.
- Cassa2: vedi M1.

**M7. Spazio in verticale nei modelli che la ricognizione non ha misurato** (tavola a 1366×657, prima riga utile):
- Lista d'attesa: la prima riga è a y=490 e la terza è tagliata (640–676), quindi si vedono 2 righe. Oggi la prima
  riga è a y=262, con righe da 51 px: ne entrano circa 7.
- Da fare: la prima cosa di «Oggi» è a y=487 (oggi 254).
- Tariffari: il primo medico è a y=529, e se ne vede 1 intero (Monti a 623–659 è tagliato). Oggi la prima riga è a
  y=308 e se ne vedono 8.

**M8. Il logo (`_marchio.html`) tolto dalle barre di Conferme e Chiusura.** Si fa insieme alla tappa 2, che mette il
logo nel menu. Se una struttura non ha logo, sparisce dalla pagina anche il testo con il suo nome
(`span.marchio-nome`): è una differenza di testo.

**M9. La stampa «pixel per pixel» della cassa è stata misurata sulla bozza dei mattoni.** `all: revert-layer
!important` dipende dagli strati (`@layer`) che sceglierà la 1-bis (`alternativa-A/vecchio.css` o no). La prova va
rifatta quando la 1-bis è nel ramo.

## 3. Righe da proporre per `cambiamenti_approvati.txt` (solo con il via di Giovanni)

```
aggiunto	segni	^aria-label=(Giorno|Mese) (precedente|successivo)$	le frecce diventano icone: il title diventa anche il nome letto (pezzo passo)
aggiunto	segni	^aria-label=Struttura$	tappa 6: la tendina della struttura (Conferme, Chiusura, Cassa) ha un nome
```

Le frecce tolte («‹», «›») e le righe di testo divise dalla striscia non si possono approvare con «aggiunto» e
«sostituisci». Serve una regola nuova («tolto», o la «cornice» di B5) prima della tappa 6, oppure il pezzo `striscia`
deve lasciare numero e parole in una riga sola di testo quando le parole sono quelle di oggi.
