# Revisione della ricognizione «configura-aiuto» (tappa 9)

Revisore scettico, 22/11/2026. Ho lavorato in sola lettura sul ramo `ccr-interfaccia`: HEAD `878f2eb`, più le modifiche
non salvate della tappa 1 (`confronta_rami.py`, `cambiamenti_approvati.txt`, `_menu.html`, `base.html`). Esperimenti, foto e
script stanno in `/tmp/claude-0/-home-user-gestionale-agende-versioni/e320334c-e9fc-59d6-bb37-15e83858aab7/scratchpad/veste-revisore-configura-aiuto/`:

- `confronta_segni.py` → `confronto-bozze-lanciatore-di-oggi.txt`: le bozze del collega rilette con il Lettore e con la
  regola «aggiunto» del lanciatore di adesso;
- `testi_nuovi.py` → `testi-tavole-non-nel-programma.txt`: i testi delle tavole Conf1-7 che non si trovano in nessun
  modello, `.py` o `.js` (fra questi ci sono anche i dati inventati);
- `foto/tavola-Conf{2,4,6,7}-1366.png`: la prima schermata delle tavole a 1366×657;
- `campo-file-it.png`: il campo «file» del browser con la lingua italiana. Su Linux resta in inglese, va guardato su Windows;
- `proponi_regole_inutili.py`: la copia dello script del collega, fatta girare nelle due cartelle.

Il risultato del collega mi è arrivato tagliato a metà della voce `invii.html`. Per regola_email, importa_*, impostazioni,
moduli, autoriparazione, aggiornamenti, Aiuto, Novità ed errori ho controllato i file direttamente: se una cosa qui sotto
lui l'aveva già scritta, conta come conferma.

I 15 modelli sono quelli giusti: sono tutti e soli i modelli che passano una delle sei sezioni di Configura
(`aggiornamenti.py:783`, `anagrafiche.py:136, 216`, `app.py:894`, `documenti.py:214, 262, 277`, `dovesifa.py:1092, 1135, 1184`,
`importa.py:2088, 2214, 2234`, `invii.py:1678, 1711`, `viste.py:603`). Anche `abort(404)`, che sono 41, e `abort(400)`, che sono 6,
tornano.

---

## 1. Cose da correggere nella ricognizione

1. **Le linguette di Configura sono della tappa 2, non della 9.** `s4.md:85-86` dice che nella tappa 2 le tendine di Ambulatori,
   Segreteria e Configura diventano linguette, scritte da `menu.py`. La bozza della cornice ha già le 6 voci di Configura con
   il commento «M2: qui la settima» (`veste-cornice/menu_bozza.py:108-121`). Il collega invece scrive un secondo elenco in
   `_configura.html`, valido «finché menu.py non c'è». Se entrano tutte e due le bozze, la pagina mostra le linguette due volte.
   Nella tappa 9 va solo la testa (riga piccola, titolo, sottotitolo), messa sopra le linguette della cornice. Il posto
   della settima è `LINGUETTE['configura']` in `menu.py`. Il rischio n. 1 del collega (il lanciatore e le linguette) è quindi
   un compito della tappa 2: è lei che deve chiudersi con «il lanciatore non trova differenze fuori dall'elenco»
   (`s4.md:89`).
2. **Il rischio n. 1 è anche superato dal lanciatore di adesso.** La regola «aggiunto» non tiene più «tutto quello che c'è già
   nel principale». `togli_aggiunti` (in `confronta_rami.py`, non ancora salvato) mette in fila i due elenchi con difflib e
   toglie ogni elemento in più che corrisponde all'espressione, anche se un elemento uguale c'è altrove. Ho provato con
   l'HTML salvato dal collega: i 6 collegamenti e i 6 testi in più delle linguette si possono filtrare con una riga `aggiunto`.
3. **«aria-label: non è testo, si può» è sbagliato.** Il lanciatore di adesso confronta i SEGNI `data-tasto`,
   `data-guida`, `data-prova`, `role`, `aria-label` e `aria-current`. Ogni `aria-label` aggiunto è una differenza e cambia il
   nome che sentono i lettori di schermo. L'ho misurato: le tre bozze del collega aggiungono in ogni pagina
   `aria-label=Pagine di Configura`, e nessuna riga di `cambiamenti_approvati.txt` lo copre. `aria-current=page` invece è già
   coperto dalla riga della tappa 1. Lo script del collega, `confronta_bozze.py`, guardava solo `data-guida` e per questo non
   l'ha visto.
4. **Il `title` delle linguette non c'è nel pezzo vero.** La macro `linguette` della bozza dei mattoni
   (`veste-mattoni/bozze/templates/_pezzi.html:118-127`) non scrive `title`. Il collega l'ha aggiunto solo nella sua
   `copia/templates/_pezzi.html:124-125`: non è in `bozze/` e non lo dice. Va chiesto alla tappa 1-bis (o 2), oppure tolto.
5. **scheda.html: «gli h2 dei riquadri diventano h3» rompe due prove.** `prove_tariffari.py:463` e `:465` cercano carattere
   per carattere `'<h2>Tariffario</h2>'` in `/anagrafiche/medici/<id>`, cioè il riquadro scritto da `scheda.html:86`. Le
   prove vanno cambiate prima, come vuole la regola «prima le prove».
6. **dove_strutture: con il pezzo `tabella` si perde `data-guida="gruppo-elenco"`.** La macro `tabella(etichetta, classe, id)`
   (`_pezzi.html:58-64`) non ha un posto per `data-guida`. Oggi l'attributo sta sulla tabella (`dove_strutture.html:28`) e lo
   usano il passo 3 della guida «strutture-gruppo» e il lanciatore. Si può aggiungere `guida=` alla macro, oppure lasciare
   quella tabella fuori dal pezzo.
7. **«small.fasce-turno (prove_110.py, 13 volte)» è impreciso.** Quelle 13 volte riguardano la griglia del Giorno e la guida
   «fasce-turno» (`prove_110.py:1450, 1557-1566`). Per `/anagrafiche` la prova cerca il testo `fasce da 15'`
   (`prove_110.py:1531`). L'apostrofo deve restare scritto nel modello: se passa da un argomento di macro, Jinja lo cambia
   in `&#39;` e la prova si rompe.
8. **Importa: l'icona `chevron-down` non esiste.** `_icone.html` non ce l'ha, e nemmeno la bozza dei mattoni
   (`_pezzi.html:136`). La macro `icona` scrive allora un `<svg>` vuoto senza avvisare (`_icone.html:59-60`), quindi la freccia
   della tendina non si vede. Va aggiunta all'elenco di `strumenti/genera_icone.py` (tappa 1-bis).
9. **La misura di importa è stata fatta su una bozza vecchia.** `misure/html-bozza/importa.html` ha ancora
   `riquadro-elenco` e non ha la `v-tendina` con l'icona di `bozze/templates/importa.html`. Il confronto «moduli e campi
   identici» va rifatto.
10. **«Scegli file» e «Nessun file selezionato» non richiedono per forza un pezzo nuovo.** Sono le parole del campo «file» del
    browser in italiano (Edge e Chrome su Windows). Con il campo del browser non entra nessun testo nuovo. Un pezzo disegnato
    invece aggiunge due righe che il lanciatore vede. Su Linux non ho potuto verificare (la foto `campo-file-it.png` è in
    inglese): va guardato sul PC Windows. La cosa vale anche per Conf5, Importa.
11. **I data-guida delle Anagrafiche non sono «in corso».** Sono già salvati in HEAD (commit `5046da4`).
12. **Lo script delle regole CSS inutili non trova proprio quelle che la tappa 9 vuole togliere.** Considera «usata» ogni
    parola che compare in un modello, un `.js` o un `.py`, commenti compresi. Ho misurato, togliendo tutti i modelli: `pagina`,
    `barra`, `larga`, `marchio`, `sezione`, `riquadro`, `sotto`, `azioni`, `campo`, `meta` e `elenco` risultano usate lo stesso,
    perché sono nomi di variabili in `turni.js`, `guida.py`, `marchio.py`, `ambulatori.py` e `gestionale.js`. Le regole di
    `div.pagina` e `div.barra` non verranno mai proposte, e sono proprio quelle della condizione «è finita quando» (`s4.md:143`).
    Anche i commenti delle bozze tengono in vita le classi (per esempio «Tolta la classe riquadro-elenco»). Correzione:
    - nei modelli, leggere solo i valori di `class="…"`;
    - nei `.js`, solo le stringhe passate a `classList`, `className` e `querySelector`;
    - nei `.py`, solo le stringhe che costruiscono HTML;
    - togliere prima i commenti (`{# #}`, `<!-- -->`, `/* */`, `//`, `#`).

    Oggi propone una regola sola (`.da-pagare`, `stile.css:928`), e quella è giusta. `stile.css` è comune alle due cartelle,
    quindi conviene far girare lo script anche in `gestionale-animata`, dove ci sono `animazioni.js` e `animazioni.css`.
    L'ho fatto e il risultato è lo stesso.

## 2. Cose che mancano

**«Pagina non trovata» (`bozze/app_404.py`)**
- Il ramo JSON restituisce `{'errore': 'non trovato'}`, e questo testo arriva alla segreteria. `turni.js:707, 739, 901, 917`
  mostra `d.errore` al posto di «Non salvato: il programma non risponde…». `dove.js:298` scrive «Non segnato nel registro:
  non trovato.». È un testo nuovo che non è nell'elenco da approvare (`cambiamenti_approvati_tappa9.txt`). Si può proporre
  una frase intera, oppure togliere la chiave `errore` così gli script usano i loro messaggi di oggi.
- `senza_cornice` scrive a mano gli indirizzi che il portiere lascia passare (`/riepilogo-live`, `/logo/`, `/static/`). Lo
  stesso elenco è già in `CLAUDE.md:277` e in `PASSAGGIO_DI_CONSEGNE.md:1105`. Con M2 («Aree e accessi»: quali aree, e per
  quale utente, dagli altri PC) questo elenco cambia. Va messo in una costante sola, che M2 potrà allargare.
- `da_configurare.html` ha lo stesso problema, ed esiste già oggi: `/riepilogo-live` e `/riepilogo-live/statistiche` la
  mostrano con il menu intero, anche con `?schermo=1`, quando non c'è nessuna struttura attiva (`live.py:350, 367`). Va
  vestita in questa tappa, quindi conviene darle la stessa regola `senza_cornice`.
- `prove_senza_menu.py` dice che «i modelli che tolgono il menu sono proprio questi undici», e che anche le pagine
  d'errore sono senza menu. La prova va cambiata prima della pagina.
- Il popup dell'aggiornamento non compare mai sotto `/riepilogo-live*`: per le pagine `live.` e per l'endpoint vuoto
  `popup_aggiornamento` restituisce None (`aggiornamenti.py:671`). Va bene così.

**Le due pagine d'errore di `app.py`**
- `PAGINA_ERRORE` (`app.py:188-196`) e `PAGINA_AVVIO_NON_RIUSCITO` (`app.py:1018-1027`) devono restare pagine chiuse in se
  stesse: solo `<style>` dentro la pagina e caratteri del sistema, niente `/static/` e niente modelli. L'errore 500 può
  venire proprio dai file mancanti (`risorse_presenti`). La pagina di avvio si apre da `file://`, quando il server non c'è.
- Le prove che le guardano: `prove_autoriparazione.py:564` e `:1456-1472` (i testi «disco del computer è pieno»,
  «occupato da un altro programma», «Quello che era già salvato è al sicuro», «non è partito», «&lt;guasto&gt;»).
- «Configura → Controllo del programma» in `PAGINA_ERRORE` è già impreciso oggi: è un bottone di Impostazioni. Si cambia
  solo con un sì.

**regola_email.html** (nessuna tavola)
- `prove_15_browser.py:84-85` legge `pg.locator('h1').text_content()` e si aspetta «Nuova email per <medico>». Con la testa
  di Configura (h1 «Configura») la prova si rompe, e con due h1 Playwright si ferma. Per le pagine secondarie la testa,
  oppure l'h1 che resta il titolo della pagina, si decide prima, e la prova si cambia prima.
- `prove_15.py:2486` conta `class="avviso-gmail"` anche in `/invii/regole/<id>` (`regola_email.html:37`).
- Il quarto `data-attesa` sta in `regola_email.html:65`; `gestionale.js:291` sostituisce il testo del bottone e toglie
  anche un'eventuale icona.

**invii.html**
- `prove_191.py:315` (`visibili`) usa `data-casella="(\w+)"(?! hidden)`: `hidden` deve venire subito dopo `data-casella`,
  senza attributi in mezzo (`invii.html:69-102`).
- `prove_191.py:306` vuole `<option value="…" selected` con questo ordine degli attributi.
- `.pagina.larga form.filtri` dà oggi la fila ai moduli «Manda la prova» (`stile.css:532`): senza `div.pagina` quella fila
  sparisce.

**I testi e i segni nuovi delle tavole** che la ricognizione non elenca (in `testi-tavole-non-nel-programma.txt`). Ognuno
cambia un nome letto, è una differenza per il lanciatore ed entra solo con un sì.
- Conf4: aria-label «Email di <medico>», «Email per tutti i medici», «Prova dell'email», «Prova di WhatsApp»,
  «Registro dei messaggi», «Riprova: <paziente>»; title «Apri l'email», «Apri il PDF», «Apri la scheda del paziente»,
  «Apri l'appuntamento, riquadro dei messaggi».
- Conf6: aria-label «Copie del database», e per ogni riga «Scarica la copia del …», «Ripristina la copia del …»,
  «confermo: copia del …».
- Conf7: aria-label «Stato degli aggiornamenti» (nella bozza giustamente non c'è).
- Conf3: «Recapiti di <struttura>», più quelli della mappa (dopo, nei moduli: M3).
- Conf2 e la barra: il percorso «Configura › Anagrafiche › Gallo Marco» (foto `tavola-Conf2-Medico-1366.png`). Il terzo
  pezzo lo passa la pagina (`{% block percorso %}` di `veste-cornice/base_bozza.html:24`). Con il nome del medico entra una
  riga di testo nuova; con il titolo di oggi («Modifica medico», `anagrafiche.py:225`) non entra niente. Lo stesso vale per
  regola_email, dove_struttura, dove_anteprima, importa_anteprima, importa_esito, modulo e autoriparazione.

**impostazioni.html**
- È uno dei tre modelli uguali nelle due cartelle. La sezione Animazioni (`id="aspetto"`, `impostazioni.html:29-41`) sta
  dentro `{% if variante == 'animata' %}` e la tavola Conf6 non ce l'ha: va vestita come «Aspetto».
- Gli script che la usano: `gestionale.js:662-667` (`input[name="tema"]`, `#stato-tema`) e `animazioni.js:16-26`
  (`input[name="animazioni"]`, `#stato-animazioni`, `#animazioni-ridotte`).
- «Tasti rapidi» apre `#aiuto-tasti` con un `onclick` scritto nel modello (`impostazioni.html:14`), e `#aiuto-tasti` lo sposta
  la tappa 2.
- I passi della guida usano `#backup`, `#stampa`, `#aspetto-tema` (guide «backup» e «aspetto»): gli id restano sui titoli.
- Il «Ripristina» del backup usa `onsubmit="return confirm(…)"`: la domanda dentro la pagina è della tappa 3.

**Togliere `div.pagina` spegne molte regole di `stile.css`**, non solo quella della scheda:
- `244-251` e `294` (larghezze);
- `271-277` e `964` (la griglia a due colonne dei moduli; serve a `campo meta` in regola_email ×3, modulo ×2, invii ×9,
  dove_struttura ×8 e scheda);
- `334` (`p.nota` della scheda);
- `532` (`form.filtri`);
- `958`;
- `1029` (`h1 small.sotto-titolo`);
- `1096` (`novita-piede`);
- `1780-1781` (`form.modulo-carica` di dove_strutture);
- `1793` (`form.conferma-dove` di dove_anteprima).

Ogni modulo dell'area va rifatto con la griglia nuova.

**scheda.html**
- Anche assenza e chiusura passano `elenco_extra`: gli appuntamenti da spostare e «Spostali tutti insieme»
  (`anagrafiche.py:1023-1031, 1090-1094`). Con la regola del collega avrebbero anche loro due colonne, senza una tavola che
  le mostri: da decidere.
- Gli `h2` di `titolo-sezione` dentro il modulo (`scheda.html:15-16`: Recapiti, Orario, Posti letto) vanno abbassati di
  livello insieme agli altri.

**aggiornamento_in_corso.html**
- Lo script vuole che `#messaggio-attesa` abbia come primo figlio `span.rotella` e come ultimo figlio il testo
  (`aggiornamento_in_corso.html:22-25`, che usa `p.lastChild.textContent` e `p.firstChild.className === 'rotella'`). Dopo il
  testo non ci devono essere spazi o a capo, e la rotella non può diventare un `<svg>`: il suo `className` non è una
  stringa.
- La pagina che si vede durante il passaggio dalla 1.12.x alla 1.13 è quella della 1.12.x. Conta la nuova, che deve
  rispondere a `/aggiornamenti/stato.json` e `/aiuto/novita`.
- Con `sezione='aggiornamenti'` (`aggiornamenti.py:840`) la cornice della tappa 2 metterebbe le linguette anche qui. Un clic
  porta via dalla pagina che aspetta il riavvio: meglio niente linguette su questa pagina.

**Aiuto**
- `aiuto_stampa.html` è uno dei 9 fogli confrontati pixel per pixel (`strumenti/fogli_pdf.py:6-7, 33`): non si veste.
- `prove_16.py:1313` cerca `<a class="bottone primario guarda-video" href=… data-video=…` carattere per carattere
  (`aiuto_articolo.html:10`; anche `novita.html:17` ha lo stesso collegamento).
- `guida.js:218` usa `a[data-video]`, `:170` `.bottone.primario` nel fumetto, `:180` `#aiuto-tasti`.

**Animazioni**
- `importa_anteprima` e `importa_esito` hanno `ul.numeri grandi` (`animazioni.js:93, 135`).
- `importa_anteprima` ha anche `table.lista-giorno` (`animazioni.js:61`).
- `animazioni.js:119` salta le righe che contengono un `th`: le righe del corpo delle tabelle non devono usare
  `<th scope="row">`.

**L'altezza della testa.** Nelle tavole la testa di Configura occupa 84→235 px su ogni pagina, compresa la scheda
(misurato, `misure/tavole-1366.json`). Su 657 px il primo contenuto parte a 253. Giovanni deve vederlo nella foto della
tappa, dato che vale anche per le pagine secondarie, se la testa ci va.

## 3. Cosa resta valido

Le misure delle linguette (6 = 838 px, 7 = 968 px, 1046 px disponibili a 1366) e le prove che il collega ha fatto girare
sulla copia le ho rilette e tornano. Le classi `c-` e `v-` usate nelle bozze sono tutte definite in `configura.css` o in
`veste.css` dei mattoni. Le tavole Conf hanno già i colori del gruppo (`#1C4184`, `#12244A` come Nefro-Colori). Sulla
settima linguetta (la richiesta di Giovanni: quali aree dagli altri PC, e a quale utente) il piano è giusto: resta nascosta
nella base, e la pagina arriva con M2. Va però scritta nell'elenco di `menu.py`, non in `_configura.html`.
