# Revisione della ricognizione «pazienti-stat» (tappa 4)

Revisore in sola lettura sul ramo `ccr-interfaccia` (HEAD `5046da4`). Il repository non è stato toccato; i miei
esperimenti sono in `scratchpad/veste-revisore-pazienti-stat/`:

- `oggi/` è il ramo com'è adesso (`git archive HEAD`).
- `bozza/` è lo stesso ramo con le 5 bozze del collega, più `_pezzi.html` e `_pezzi_striscia_numeri.html`.
- `bozza-corretta/` è `bozza/` con i 3 data-guida rimessi (vedi il punto 1).
- `bozza-css/` aggiunge i fogli dei mattoni, e serve solo per le misure.

Tutti e due sono stati provati sullo stesso `demo.db` del collega, con il metodo del lanciatore (`raccogli.py`,
`confronta.py`), anche sulle risposte ai POST, e con un confronto degli attributi. I due gestionali di prova (porte
5187 e 5188) sono spenti.

## 1. Bloccante: le bozze sono state fatte su un ramo vecchio e perdono 3 data-guida

- **Cosa è successo.** Le bozze sono state scritte fra le 03:19 e le 03:22, su una copia fatta prima di cinque
  commit della tappa 1 (`967c534`, `ed4c6ee`, `91a02d6`, `b64cac2`, `5046da4`). Il commit `5046da4` (04:28) ha
  aggiunto nell'area tre segni per la guida:
  - `pazienti.html`: `data-guida="pazienti-cerca"` sul `<form>` e `data-guida="pazienti-apri"` sul nome di ogni
    riga;
  - `statistiche.html`: `data-guida="statistiche-riepilogo-medici"` su «Riepilogo del mese per medico».

  Le bozze non li hanno.
- **Misurato sul ramo di oggi.** Le pagine `/pazienti`, `?q=ferr`, `?q=zzzz` e le tre forme di `/statistiche`
  risultano DIVERSE per un data-guida tolto. `cambiamenti_approvati.txt` approva solo i data-guida aggiunti, quindi
  questa è una differenza vera. `prove_guida.py` su ramo e bozze dà ROTTO: «cercare passo 2: data-guida che nessun
  modello ha: ['pazienti-cerca']».
- **Cosa si rompe.** I passi della guida `guida.py:159`, `:161` e `:505`, e
  `strumenti/genera_immagini_guida.py:112` e `genera_video_guida.py:89`, che cercano
  `[data-guida="pazienti-apri"]`. Il risultato sarebbe «Elementi non trovati», e la tappa non si potrebbe chiudere.
- **Righe del collega da correggere.** Queste citazioni non valgono più:
  - `guida.py:159` (form.ricerca), `:161` (table.elenco a[href*="/pazienti/"]) e `:505` (a.bottone);
  - `genera_immagini_guida.py:111-112` e `genera_video_guida.py:88-89`;
  - nella bozza di Statistiche, la nota «la classe bottone serve alla guida».

  Oggi tutti questi punti usano `data-guida`.
- **Il confronto del collega.** «11 pagine su 12 UGUALI» era misurato contro `riassunti-oggi.json`, preso dalla
  copia vecchia: in quel file i tre nomi compaiono 0 volte.
- **Correzione provata** (`bozza-corretta/`). Con i 3 attributi rimessi sugli stessi elementi, le pagine uguali
  sono 20 su 23. Restano diverse solo le 3 di Statistiche, per il titolo (vedi il punto 4).

## 2. Bloccante: `prove_guida.py` vuole il nome scritto nel modello, e i pezzi lo passano come argomento

`prove_guida.py:165-175` cerca `data-guida="nome"` scritto per intero in un file di `templates/`. In
`codici_fiscali.html` la bozza scrive invece `scheda(..., guida='codici-non-validi')`. Nella pagina il segno c'è,
nei file no.

Con la correzione 1 applicata, `prove_guida.py` cade ancora. Mancano 5 nomi: codici-non-validi, codici-non-coerenti,
codici-doppi, codici-calcolabili e codici-senza.

Il problema vale per ogni pezzo dei mattoni con `guida=`: scheda, striscia, barra_comandi, linguette e
stampa_e_scarica. Va deciso una volta sola, nella 1-bis o nel primo passo della tappa 4, con un mutante. Le strade
sono due:

- (a) la prova legge anche `guida='nome'` nelle chiamate dei pezzi;
- (b) il segno resta scritto nella pagina, per esempio `<section data-guida="codici-non-validi">` intorno alla
  scheda.

## 3. Bloccante per l'animata: senza la classe `bottone` sparisce l'onda

L'animata mette l'onda e l'effetto della pressione solo su `.bottone` (`animazioni.js:70`
`closest('.bottone, .passo')`; `animazioni.css:68-73`).

**Misurato nella bozza.** Perdono `.bottone`: Cerca, Nuovo paziente, Controllo dei codici fiscali, Aggiorna, Salva
scheda, Aggiungi, Allega, Unisci le schede, Cerca (in Unisci), Calcola e salva, Scarica ed Elimina del documento. Lo
tengono solo «Scarica in Excel» e «Riepilogo del mese per medico».

Non dà errori, e `prove_animazioni.py:104-108` prova l'onda solo su `/impostazioni`, quindi non se ne accorge.
«L'animata continua a funzionare» è vero solo per `ul.numeri` e `.barra-dato`.

**Da fare**, nei mattoni e per tutte le tappe:

- `animazioni.js` e `animazioni.css` devono valere anche per `.v-bottone`; sono file della sola animata, da
  adattare nella stessa tappa (s2);
- una prova dell'onda su una pagina della tappa 4.

## 4. Testi della tavola che non ci sono oggi

Per Paz1 e Paz2 l'elenco del collega è completo. L'ho verificato estraendo nel browser testi, aria-label, title e
placeholder delle tavole e confrontandoli con le pagine di oggi.

Per Stat1 il suo resoconto si interrompe. Questi testi vanno nell'elenco: si aggiungono solo se Giovanni li
approva, e la bozza giustamente non li mette.

- La riga piccola «Statistiche · <sede>» con sopra l'`<h1>` «Statistiche». È l'unica riga di testo in più trovata
  dal confronto (riga 83 del riassunto).
  - Oggi solo `statistiche.html` ha «· struttura» nell'h1.
  - La «riga piccola» però c'è in molte tavole (Turni, Cassa…). Conviene decidere una regola sola in
    `cambiamenti_approvati.txt`, non pagina per pagina.
- `aria-label` «Struttura e periodo delle statistiche» sul modulo (Stat1:129).
- `role="group"` con `aria-label` «I numeri del periodo» sulla striscia (Stat1:156).
- `title` sulle barre: «Saturazione 45%» per le stanze, «131 appuntamenti» per medici, prestazioni e giorni
  (Stat1:196, 225, 256, 287).
  - La SPEC li mette fra le cose «da provare» (`SPEC-TDSC.md:286-287`), quindi Giovanni se li aspetta: va chiesto.
- Le `<label for>` esplicite (Struttura, Dal, Al) hanno le stesse parole di oggi: nessun testo nuovo.

## 5. Affermazioni controllate

**Confermate**, sul ramo di oggi più le bozze, con le variabili rigide (`GESTIONALE_PROVE_RIGIDE=1`, nate con
`91a02d6`, dopo la copia del collega):

- **Pagine.** Moduli, campi, collegamenti e testo sono uguali su:
  - `/pazienti/nuovo` e `/pazienti/nuovo?torna=/appuntamento`;
  - le schede `/pazienti/1`, `/3`, `/4` (con un disdetto), `/6` (con cose da fare), `/10` (in lista d'attesa) e
    `/17`;
  - le tre forme di Unisci;
  - la pagina dei codici fiscali.
- **Risposte ai POST, che il lanciatore non vede** (fa solo GET: `confronta_rami.py`, testo iniziale). Sono uguali
  anche queste:
  - il doppione: riquadro «Potrebbe essere già in anagrafica» e spunta `doppione_confermato`;
  - un'email sbagliata;
  - un codice fiscale sbagliato;
  - un errore su una scheda già esistente;
  - Unisci senza la spunta.
- **Attributi** (`raccogli.py`, chiave `attributi`). Uguali su tutte le 23 pagine: id, name, required, maxlength,
  autofocus, placeholder, target, onclick, formnovalidate, role, aria-live e hidden. Le sole differenze:
  - i 3 data-guida del punto 1;
  - gli `svg aria-hidden` delle icone;
  - tre `section aria-labelledby` nuove (`titolo-in-breve`, `titolo-appuntamenti`, `documenti`): sono tre regioni
    nuove per i lettori di schermo, senza testo nuovo;
  - «Da fare» che passa da h2 a h3.
- **Attenzione.** Il lanciatore non guarda id, classi, aria-*, title, required, maxlength, target né onclick. Un
  UGUALE del lanciatore non dimostra quello che il collega elenca in «resta». Nella tappa serve anche un confronto
  degli attributi come questo, oppure una prova.
- **Prove sul ramo di oggi più le bozze.**
  - `prove_17.py` 33/33.
  - `prove_19.py` 27/27.
  - `prove_funzioni.py` 67/68: cade solo `:1271` (`<td>0,0</td>`), come già detto.
  - `prove_guida.py` 3/4: cade per i punti 1 e 2.
- **`prove_14.py:1836`.** La causa è confermata. La prova cerca `tema-scuro.css` nell'HTML, ma la copia del collega
  usa `vecchio.css`, che lo nasconde. La `base.html` attuale dei mattoni lo scrive con `@import`, quindi lì
  passerebbe.

**Da rifare.** Le prove nel browser del collega (`prove_17_browser`, `prove_tendine_browser`, le foto) sono state
fatte sulla copia vecchia: senza `<main>`, senza `variante` e senza variabili rigide. Vanno rifatte sul ramo del
momento.

**«Prenota si allunga a 61 px».** Ho misurato 64×36 px con display:block: è la larghezza, non l'altezza. Lo stesso
conflitto di `.v-piccolo` (`veste.css:96` dei mattoni) fa due danni in più, che si vedono in
`veste-revisore-pazienti-stat/foto/bozza-documenti-1366.png`:

- i «KB» del documento vanno a capo (display:block, anche con `.v-in-riga`);
- Scarica ed Elimina stanno uno sotto l'altro, mentre la tavola li ha in riga.

## 6. Misure a 1366×657 e 1440 (bozza con i fogli dei mattoni)

- **La pagina resta larga 960 px** sia a 1366 sia a 1440. Il limite è `max-width` di `.pagina.larga`
  (`stile.css:294`), che resta nello strato vecchio, e `.v-pagina` non lo toglie.
  - La tavola a 1440 usa circa 1118 px: tabella di Paz1 da x=285 a x=1403, Stat1 da 284 a 1403.
  - Conseguenze: la striscia di Statistiche va su 3 righe (nella tavola e oggi su 2), e i nomi dei medici vanno a
    capo.
  - Bisogna decidere chi toglie `.pagina` (620 e 960 px, margin 26px auto): la cornice nella tappa 2 o
    `veste.css`, una volta per tutte le pagine.
  - La classe `pagina` va tenuta: la usano `animazioni.css:35`, `animazioni.js:255` e `prove_animazioni.py:106`.
- **Altezza delle righe.**

  | Pagina | Bozza | Tavola | Oggi |
  |---|---|---|---|
  | Pazienti | 49 px | 47 px | 33 px |
  | Appuntamenti della scheda | 43 px | 46 px | |
  | Statistiche | 39 px | 43 px circa | |

  A 1366×657 si vedono 6 righe intere di Pazienti; oggi 11.
- **Striscia.** La prima voce di ogni riga ha il filo a sinistra. La tavola non ce l'ha (nota Stat1:150-154).
- **Giorni della settimana.** La barra sta nella sola `td.largo` (36%, `stile.css:790`), quindi è corta e a
  destra. Nella tavola è lunga e parte da sinistra.

## 7. Pezzi comuni scritti nel file dell'area

La tappa si chiude con «nessun pezzo comune è scritto due volte», ma `veste-pazienti-stat.css` definisce classi
generiche che serviranno anche alle altre aree:

- `v-cerca`: il campo con la lente (Pazienti, Unisci, poi Dove si fa);
- `v-filo-giallo`: il riquadro d'avviso, al posto dei `div.guida` anche in altre pagine;
- `v-etichetta-in-riga`: i campi in riga nelle barre (Cassa, Ambulatori…);
- `v-elenco-puntato`, `v-separa`, `v-riga-comandi`, `v-spunta`, `v-vuoto`, `v-testo`, `v-blocco`, `v-piede-scheda`,
  `v-barra-e-numero`, `v-in-riga` e `v-allega`.

Vanno nei mattoni (`veste.css`, `_pezzi.html`), non nel file dell'area.

**La striscia.** `striscia_numeri()` accanto a `striscia()` sono due pezzi per la stessa cosa. `ul.numeri` c'è in 7
modelli: `chiusura`, `dove_anteprima`, `dove_registro`, `importa_anteprima`, `importa_esito`, `paziente` e
`statistiche`. Meglio una sola `striscia()` che scriva `ul.numeri > li > b`, cioè l'aggancio dell'animata, e
accetti più numeri per voce. Si decide nella 1-bis.

**Il codice fiscale.** Il blocco codice fiscale e luogo di nascita c'è anche in `appuntamento.html:97-109` (tappa
5). La regola `.v-modulo .esito-cf` va scritta generale, così la tappa 5 non la riscrive. Su `#esito-cf` non va
nessuna classe nuova (`gestionale.js:144`).

## 8. Dopo, nei moduli (correzione a «solo M5»)

M2 dice: «con Turni o Cassa spenti, le altre pagine … non mostrano pezzi loro» (s4.md:191). Le pagine dell'area
contengono pezzi di altri moduli:

- **Statistiche:**
  - «euro incassati» (Cassa, M2);
  - «Riepilogo del mese per medico» (Ambulatori e riepiloghi, M6);
  - «Indirizzati alle altre strutture» e il registro (Dove si fa, M3).
- **Scheda del paziente:**
  - «Dove si fa una prestazione» (M3);
  - «Contatta: WhatsApp / Email», il canale e i promemoria (Comunicazioni, M4);
  - lista d'attesa, «Da fare» e «Ricordami di…» (Segreteria, M9).

Nella tappa 4 non si fa niente. Conviene solo che ogni pezzo stia in un elemento suo, facile da togliere con un
`{% if %}`. Per esempio, oggi i « · » fra i collegamenti della scheda sono testo sciolto.

## 9. Ordine consigliato all'inizio della tappa 4

1. Rifare le bozze sui modelli del ramo di quel momento, cioè dopo le tappe 1-bis, 2 e 3. Riportare ogni
   data-guida e ogni `data-conferma` della tappa 3: `git diff 5046da4..HEAD -- gestionale/templates/{pazienti,paziente,unisci,codici_fiscali,statistiche}.html`.
2. Primo commit, solo prove:
   - `prove_funzioni.py:1271` legge la cella e non la stringa `<td>…</td>`;
   - `prove_guida.py` sceglie fra (a) e (b) del punto 2, con il mutante;
   - un confronto degli attributi, o una prova per id e aria, sulle pagine dell'area, anche dopo un POST;
   - l'onda dell'animata su una pagina dell'area.
3. Secondo commit: le pagine, con i punti 3, 6 e 7 risolti nei mattoni. Al lanciatore deve restare diverso solo il
   titolo di Statistiche, se approvato.
