# -*- coding: utf-8 -*-
"""La guida del programma, scritta una volta sola e usata in tre modi:

1. la pagina Aiuto → Come fare… con un articolo per ogni cosa da fare,
   i passi numerati e un'immagine con gli stessi numeri;
2. la guida sullo schermo: il pulsante "Mostrami sullo schermo" (o Aiuto →
   Guida di questa pagina) apre la pagina giusta e, passo per passo,
   illumina il punto dove cliccare con un fumetto che spiega;
3. la versione da stampare (e il PDF), tutti gli articoli di seguito;
4. la videoguida: «Guarda il video» mostra la guida sullo schermo registrata
   sui dati di prova, con un puntatore che va dove si clicca
   (static/video/<articolo>.webm, prodotti da strumenti/genera_video_guida.py
   con gli stessi passi).

Un passo e' un dizionario: 'titolo' e 'testo', e se il passo indica un punto
della pagina 'sel' (selettore CSS) e facoltativo 'contiene' (il testo che
l'elemento deve contenere, per scegliere fra piu' pulsanti uguali). Un passo
senza 'sel' e' un fumetto al centro. Le immagini le produce
strumenti/genera_immagini_guida.py dai dati di prova, con gli stessi 'sel'.
"""
import json
import os
import re
from datetime import date

from flask import Blueprint, render_template, abort, url_for, request, Response

bp = Blueprint('guida', __name__, url_prefix='/aiuto')


def P(titolo, testo, sel=None, contiene=None):
    d = {'titolo': titolo, 'testo': testo}
    if sel:
        d['sel'] = sel
    if contiene:
        d['contiene'] = contiene
    return d


# endpoint: la pagina dove si fa (per la guida sullo schermo)
# apri: come aprirla dal programma (endpoint, argomenti; 'OGGI' = la data di oggi, 'MESE' = il mese)
# condizione: la guida vale solo se nella pagina c'e' questo elemento
# foto: la pagina da fotografare sui dati di prova ({martedi}, {domani}, {oggi})
ARTICOLI = [
    # ------------------------------------------------------------ primi passi
    dict(slug='come-e-fatto', gruppo='Primi passi', titolo='Come è fatto il programma',
         in_breve='Un giro di un minuto: il menu, la pagina Oggi, la ricerca e dove trovare aiuto.',
         endpoint='cruscotto.oggi', apri=('cruscotto.oggi', {}), foto='/oggi',
         passi=[
             P('Per cominciare', 'Il gestionale si apre sempre sulla pagina Oggi: quello che serve sapere entrando la mattina. '
               'Questo giro mostra dove sono le cose; si chiude quando si vuole con Esc o con la ×.'),
             P('Oggi', 'Chi aspettare adesso e nelle prossime due ore, con il pulsante Arrivato; sotto, interventi, '
               'cose da fare, telefonate e cassa.', 'nav.menu [data-guida="menu-oggi"]'),
             P('Il giorno', 'La griglia del giorno: una colonna per stanza, una riga per fascia oraria. È da qui che si prenota.',
               'nav.menu [data-guida="menu-giorno"]'),
             P('Pazienti', 'L\'anagrafica: cercare, aprire la scheda, vedere gli appuntamenti e i documenti di un paziente.',
               'nav.menu [data-guida="menu-pazienti"]'),
             P('Segreteria', 'Il lavoro di tutti i giorni oltre a prenotare: conferme, da confermare, chiusura della '
               'giornata, cose da fare, lista d\'attesa. Il numero arancione dice quante prenotazioni sono in sospeso.',
               'nav.menu [data-guida="menu-segreteria"]'),
             P('Cerca', 'Scrivere qui (o premere il tasto /) un cognome, un telefono o un giorno come "domani" o "24/9".',
               'nav.menu [data-guida="menu-cerca"]'),
             P('Aiuto', 'Da qui si torna sempre a questa guida: "Guida di questa pagina" per un giro sulla pagina aperta, '
               '"Come fare…" per tutte le guide, con le immagini e i video, "Novità" per cosa c\'è di nuovo.',
               'nav.menu [data-guida="menu-aiuto"]'),
             P('Configura', 'Stanze, medici e turni, l\'importazione da Excel, le impostazioni e gli aggiornamenti: si '
               'usano di rado.', 'nav.menu [data-guida="menu-configura"]'),
             P('Adesso', 'In cima a Oggi: chi è in ritardo e chi arriva, con i pulsanti per segnarlo arrivato.',
               '.scheda-oggi.larga'),
         ]),
    dict(slug='medici-turni', gruppo='Primi passi', titolo='Aggiungere un medico e i suoi turni',
         in_breve='Senza turni la griglia resta grigia: i turni dicono chi c\'è, dove e a che ora.',
         endpoint='anagrafiche.elenco', apri=('anagrafiche.elenco', {}), foto='/anagrafiche',
         passi=[
             P('Apri le anagrafiche', 'Menu Configura → Anagrafiche. In alto, "Per cominciare" dice cosa manca ancora.'),
             P('Aggiungi il medico', 'Cognome, nome, specialità e colore (serve a riconoscerlo nella griglia). '
               'Email e telefono servono per mandargli la sua agenda.', 'a.bottone.aggiungi', 'Aggiungi medico'),
             P('Aggiungi un turno', 'Medico, stanza, giorno della settimana e orario: per esempio Lippiello, Ambulatorio 1, '
               'lunedì dalle 8 alle 14. Si ripete ogni settimana.', 'a.bottone.aggiungi', 'Aggiungi turno'),
             P('Chi viene senza giorno fisso', 'Per una sostituzione o per chi viene ogni tanto c\'è il turno di un giorno solo.',
               'a.bottone.aggiungi', 'Aggiungi turno di un giorno'),
             P('Ferie e assenze', 'Nei giorni di assenza i turni del medico non aprono fasce, e il programma elenca gli '
               'appuntamenti da spostare.', 'a.bottone.aggiungi', 'Aggiungi assenza'),
             P('Quando un turno finisce', 'Si apre il turno e si scrive la data in "Fino al". Eliminarlo toglierebbe le '
               'sue ore anche dalle statistiche dei mesi già passati.'),
             P('Le sue email', 'Aprendo il medico, in fondo ci sono le email automatiche ai suoi pazienti e "Nuova email '
               'per questo medico", se ha informative sue.'),
         ]),
    # --------------------------------------------------------- tutti i giorni
    dict(slug='prenotare', gruppo='Tutti i giorni', titolo='Prenotare un appuntamento',
         in_breve='Dalla griglia: clic su una fascia "libero", paziente, prestazione, Salva.',
         endpoint='appuntamento', apri=('appuntamento', {'data': 'OGGI'}), condizione='#cerca_paziente',
         foto='/appuntamento?data={martedi}&ora=11:00&risorsa=1&struttura=1',
         passi=[
             P('Dalla griglia', 'Nella griglia del giorno si clicca su una fascia con scritto "libero": il modulo si apre '
               'con stanza, ora e medico di turno già scelti. In alternativa, il pulsante Nuovo appuntamento.'),
             P('Cerca il paziente', 'Si scrivono le prime lettere del cognome o il telefono e si sceglie dall\'elenco. '
               'Se è la prima volta basta scrivere cognome e telefono: la scheda si crea da sola.', '#cerca_paziente'),
             P('Cognome e telefono', 'Per un paziente nuovo. Il telefono serve per le conferme su WhatsApp, l\'email per le '
               'email automatiche (per esempio la preparazione agli esami).', '#paziente'),
             P('Nascita, codice fiscale, indirizzo', 'Finiscono nella scheda del paziente. Il codice fiscale si controlla '
               'mentre si scrive e riempie data, sesso e luogo di nascita; senza codice, si calcola dai dati.',
               '[data-guida="codice-fiscale"]'),
             P('Stanza e medico', 'Già scelti dalla fascia cliccata; si possono cambiare.', '#risorsa'),
             P('Prestazione', 'La durata segue la prestazione; se serve diversa, si cambia in "Durata in minuti".',
               '#prestazione'),
             P('Giorno e ora', 'Si possono cambiare anche qui. Se la stanza o il medico sono già occupati il programma lo '
               'dice e non salva.', '#data'),
             P('Salva', 'Salva appuntamento (anche Ctrl + Invio). Si torna alla giornata con l\'appuntamento al suo posto.',
               '#modulo-appuntamento button.primario[type="submit"]'),
         ]),
    dict(slug='mese', gruppo='Tutti i giorni', titolo='Il mese: chi c\'è e la sala operatoria',
         in_breve='Menu Mese: giorno per giorno appuntamenti, posti liberi, medici e interventi in sala.',
         endpoint='viste.mese', apri=('viste.mese', {'aaaamm': 'MESE'}), foto='/mese/{mese}?struttura=1',
         passi=[
             P('Apri il mese', 'Menu Mese: il mese del giorno che si sta guardando; le frecce cambiano mese.',
               'nav.menu [data-guida="menu-mese"]'),
             P('Ogni giorno', 'Quanti appuntamenti, quante fasce sono ancora libere e chi è di turno. Clic sul giorno per '
               'aprire la sua griglia.', 'a.giorno-mese'),
             P('Sala operatoria', 'Gli interventi del giorno con i chirurghi. "Sala libera" dice chi opera di solito in '
               'quel giorno della settimana e non ha ancora interventi: lì c\'è posto.', '.sala-mese'),
             P('Un medico solo', 'Scelto un medico, il mese mostra solo i suoi appuntamenti. Stampa per il foglio.',
               'select[name="medico"]'),
         ]),
    dict(slug='cercare', gruppo='Tutti i giorni', titolo='Trovare un paziente o un giorno',
         in_breve='La casella Cerca in alto trova pazienti, medici e giorni, da qualsiasi pagina.',
         endpoint='pazienti.elenco', apri=('pazienti.elenco', {}), foto='/pazienti?q=sepe',
         passi=[
             P('Da ogni pagina', 'Tasto / oppure clic sulla casella Cerca nel menu. Si scrive un cognome, un numero di '
               'telefono, un medico o un giorno ("domani", "lunedì", "24/9").', 'nav.menu [data-guida="menu-cerca"]'),
             P('La pagina Pazienti', 'Per cercare con più calma, vedere gli ultimi inseriti o aggiungere un paziente senza '
               'prenotare.', 'form.ricerca'),
             P('La scheda', 'Clic sul nome: telefono, appuntamenti passati e futuri, documenti, cose da fare.',
               'table.elenco a[href*="/pazienti/"]'),
             P('Doppioni', 'Se lo stesso paziente è stato scritto due volte, dalla scheda "Possibili doppioni" si uniscono '
               'le due schede senza perdere niente.'),
         ]),
    dict(slug='codice-fiscale', gruppo='Tutti i giorni', titolo='Codice fiscale, data e luogo di nascita',
         in_breve='Il codice fiscale si controlla mentre lo si scrive e riempie data, sesso e luogo di nascita; se '
                  'manca, si calcola dai dati.',
         endpoint='pazienti.scheda', apri=('pazienti.scheda', {}), condizione='[data-guida="codice-fiscale"]',
         foto='/pazienti/{paziente_esempio}',
         passi=[
             P('Il codice fiscale', 'Si scrive com\'è sulla tessera sanitaria, anche con gli spazi. Il programma lo '
               'controlla mentre si scrive: sotto compare «Codice fiscale corretto» oppure cosa non va, per esempio '
               'l\'ultima lettera sbagliata. Un codice sbagliato non si salva.', '[data-guida="codice-fiscale"]'),
             P('Data, sesso e luogo', 'Da un codice giusto si riempiono da soli data, sesso e luogo di nascita, se sono '
               'vuoti. Si possono sempre correggere.', '#sesso'),
             P('Il luogo di nascita', 'Si scrivono le prime lettere del comune o dello stato estero e si sceglie '
               'dall\'elenco, che ha anche i comuni che non esistono più. Due comuni con lo stesso nome si distinguono '
               'dalla provincia.', '[data-guida="luogo-nascita"]'),
             P('Senza la tessera', 'Con cognome, nome, sesso, data e luogo di nascita il codice si calcola da solo. Va '
               'controllato sulla tessera alla prima occasione: in rari casi (omocodia) quello vero è diverso.'),
             P('Se non torna', 'Se il codice non corrisponde al cognome, al nome, alla data o al luogo scritti, salvando '
               'compare un avviso: è sbagliato uno dei due, e fa fede la tessera sanitaria.'),
             P('Anche nella prenotazione', 'Gli stessi campi, con lo stesso controllo, ci sono nel modulo di '
               'prenotazione: i dati finiscono nella scheda del paziente.'),
         ]),
    dict(slug='controllo-codici-fiscali', gruppo='Tutti i giorni', titolo='Controllare i codici fiscali in archivio',
         in_breve='Pazienti → Controllo dei codici fiscali: quelli che non vanno, quelli che non tornano con i dati, i '
                  'doppioni e chi è senza codice.',
         endpoint='pazienti.codici_fiscali', apri=('pazienti.codici_fiscali', {}), foto='/pazienti/codici-fiscali',
         passi=[
             P('Apri il controllo', 'Dalla pagina Pazienti, pulsante «Controllo dei codici fiscali». In cima, quanti '
               'sono da vedere.', '[data-guida="codici-riepilogo"]'),
             P('Non validi', 'Codici salvati con un errore prima della versione 1.7, con il motivo. Clic sul nome: nella '
               'scheda si corregge e si vede subito se va.', '[data-guida="codici-non-validi"]'),
             P('Non corrispondono', 'Codici validi che però dicono un altro cognome, nome, data, sesso o luogo: è '
               'sbagliato il codice o il dato.', '[data-guida="codici-non-coerenti"]'),
             P('Su più schede', 'Lo stesso codice su due schede: di solito la stessa persona inserita due volte. «Unisci» '
               'mette insieme le schede, con tutti gli appuntamenti.', '[data-guida="codici-doppi"]'),
             P('Da calcolare', 'Schede con tutti i dati ma senza codice: «Calcola e salva» li scrive tutti, dopo una '
               'copia di sicurezza.', '[data-guida="codici-calcolabili"]'),
             P('Senza codice', 'Chi non ha il codice né i dati per calcolarlo, a partire da chi ha un appuntamento: si '
               'chiedono quando viene, o si scrive il codice della tessera.', '[data-guida="codici-senza"]'),
         ]),
    dict(slug='stato', gruppo='Tutti i giorni', titolo='Arrivato, disdetto, non presentato',
         in_breve='Un clic sull\'appuntamento e un clic sullo stato. I disdetti liberano la fascia.',
         endpoint='appuntamento', apri=('giorno', {'iso': 'OGGI'}), condizione='.barra-stato',
         foto='/appuntamento/{app_esempio}',
         passi=[
             P('Apri l\'appuntamento', 'Nella griglia si clicca sull\'appuntamento colorato.'),
             P('Cambia lo stato', 'Confermato (ha risposto alla conferma), Arrivato (è in sala d\'attesa), Non presentato, '
               'Disdetto. Rimetti prenotato annulla l\'ultimo cambio.', '.barra-stato'),
             P('Più veloce', 'Dalla pagina Oggi e dalla Chiusura della giornata il pulsante Arrivato è già accanto al nome, '
               'senza aprire l\'appuntamento.'),
             P('Posto liberato', 'Se un appuntamento futuro viene disdetto, il programma dice chi in lista d\'attesa va bene '
               'per quel posto.'),
         ]),
    dict(slug='spostare', gruppo='Tutti i giorni', titolo='Spostare un appuntamento',
         in_breve='Dall\'appuntamento, Sposta: il programma propone i primi posti liberi dello stesso medico.',
         endpoint='appuntamento', apri=('giorno', {'iso': 'OGGI'}), condizione='.barra-stato',
         foto='/appuntamento/{app_esempio}',
         passi=[
             P('Sposta', 'Nell\'appuntamento, in alto, il collegamento Sposta.', 'p.sotto a[href*="/sposta"]'),
             P('Scegli il posto', 'Sposta qui accanto a uno dei posti proposti, oppure data e ora a mano. Il messaggio per '
               'avvisare il paziente è già scritto.'),
             P('Tutti gli appuntamenti di un medico', 'Per ferie o assenza: Anagrafiche → Aggiungi assenza, poi il '
               'programma propone dove spostare ciascun appuntamento.'),
         ]),
    dict(slug='conferme', gruppo='Tutti i giorni', titolo='Le conferme del giorno dopo',
         in_breve='Segreteria → Conferme: per ogni paziente WhatsApp o email con il messaggio già scritto.',
         endpoint='viste.conferme', apri=('viste.conferme', {}), foto='/conferme',
         passi=[
             P('Apri le conferme', 'Menu Segreteria → Conferme (tasto C). Si apre il prossimo giorno di lavoro: il venerdì '
               'mostra il sabato o il lunedì.', 'nav.menu [data-guida="menu-segreteria"]'),
             P('Contatta', 'WhatsApp o Email aprono il messaggio già scritto con giorno, ora e indicazioni: resta solo da '
               'inviarlo. Chiama compone il numero.', '.contatti-rapidi'),
             P('Segna la risposta', 'Confermato quando il paziente risponde; Disdetto se rinuncia (la fascia si libera).',
               '.pulsanti-stato'),
             P('Promemoria automatici', 'Con i promemoria accesi (Configura → Email e WhatsApp) la colonna Promemoria dice '
               'cosa è partito da solo; Manda lo manda adesso. Restano da chiamare solo gli altri.'),
             P('Il testo', 'Il messaggio si cambia in Configura → Impostazioni → Messaggi ai pazienti.'),
         ]),
    dict(slug='chiusura', gruppo='Tutti i giorni', titolo='Chiudere la giornata',
         in_breve='A fine giornata: chi è arrivato e chi no, in un colpo solo.',
         endpoint='segreteria.chiusura', apri=('segreteria.chiusura', {'iso': 'OGGI'}), foto='/chiusura/{martedi}',
         passi=[
             P('Apri la chiusura', 'Menu Segreteria → Chiusura della giornata. Dopo le 18 arriva anche una notifica.'),
             P('Seleziona e segna', 'Si spuntano i pazienti e si preme Segna i selezionati come arrivati (o come non '
               'presentati).', 'button[value="arrivati"]'),
             P('Da incassare', 'Sotto, chi è arrivato con un importo e non ha ancora pagato.'),
             P('Giorni indietro', 'Se qualche giornata passata è rimasta aperta, è elencata in fondo e fra le notifiche.'),
         ]),
    dict(slug='da-confermare', gruppo='Tutti i giorni', titolo='Prenotazioni in sospeso (Da confermare)',
         in_breve='Quando manca la stanza o il paziente deve richiamare: un appunto che poi diventa appuntamento.',
         endpoint='segreteria.da_confermare', apri=('segreteria.da_confermare', {}), foto='/da-confermare',
         passi=[
             P('Scrivi l\'appunto', 'Cosa c\'è da confermare, e se si sa giorno, ora, medico, paziente. Aggiungi.',
               'textarea[name="testo"], input[name="testo"]'),
             P('Prenota', 'Quando si sa tutto, Prenota apre il modulo già compilato; salvando, l\'appunto si chiude.',
               'a.bottone.primario', 'Prenota'),
             P('Più insieme', 'Spuntati più appunti e scelta la stanza, Prenota i selezionati li mette tutti in agenda.',
               '#prenota-insieme'),
             P('Nella giornata', 'Gli appunti di un giorno compaiono anche in cima alla griglia di quel giorno.'),
         ]),
    dict(slug='attesa', gruppo='Tutti i giorni', titolo='Lista d\'attesa',
         in_breve='Chi vuole un posto prima: quando uno si libera, il programma dice chi chiamare.',
         endpoint='segreteria.attesa', apri=('segreteria.attesa', {}), foto='/attesa',
         passi=[
             P('Aggiungi', 'Paziente, medico o prestazione se contano, e da quando a quando va bene.',
               'a.bottone.primario', 'Aggiungi alla lista'),
             P('Posto libero', 'Quando un appuntamento futuro viene disdetto, il programma avvisa e propone chi in lista va '
               'bene, dal più vecchio.'),
             P('Prima disponibilità', 'Da ogni riga si cerca il primo posto libero di quel medico.'),
         ]),
    dict(slug='cose-da-fare', gruppo='Tutti i giorni', titolo='Cose da fare e notifiche',
         in_breve='Promemoria per la segreteria: richiamare, sollecitare un referto. Arrivano come notifica.',
         endpoint='segreteria.cose_da_fare', apri=('segreteria.cose_da_fare', {}), foto='/cose-da-fare',
         passi=[
             P('Scrivi cosa', 'Cosa fare e per che giorno. Anche dalla scheda del paziente o dall\'appuntamento, con '
               '"Ricordami di…".', 'form.filtri'),
             P('Le notifiche', 'Nel giorno indicato compare una notifica in basso a destra, con Fatto e Domani. Si chiude con '
               'la ×; ricompare solo se c\'è qualcosa di nuovo.'),
             P('Fatto', 'Fatto la toglie; Domani la rimanda di un giorno.', 'button', 'Fatto'),
         ]),
    # ---------------------------------------------------------- sala operatoria
    dict(slug='checklist', gruppo='Sala operatoria', titolo='Checklist pre-operatoria',
         in_breve='Esami, consenso, anestesista, preparazione, acconto: le caselle si salvano da sole.',
         endpoint='sala.giornata', apri=('sala.giornata', {'iso': 'OGGI'}), foto='/sala/{domani}',
         passi=[
             P('La pagina Sala', 'Menu Sala: gli interventi del giorno o dei prossimi sette.', 'nav.menu [data-guida="menu-sala"]'),
             P('Spunta', 'Clic sulla casella: si salva subito, con data e ora. Il numero dice quante sono fatte.',
               'form.checklist'),
             P('Nella griglia', 'Ogni intervento mostra quante voci mancano (3/5); passandoci sopra, quali.'),
             P('Il giorno prima', 'Arriva una notifica con gli interventi di domani ancora da completare.'),
             P('Le voci', 'Si cambiano in Configura → Impostazioni → Checklist pre-operatoria.'),
         ]),
    dict(slug='lista-operatoria', gruppo='Sala operatoria', titolo='Lista operatoria e posti letto',
         in_breve='Il foglio per la sala e il conto dei letti per chi resta la notte.',
         endpoint='sala.giornata', apri=('sala.giornata', {'iso': 'OGGI'}), foto='/sala/{domani}',
         passi=[
             P('Degenza', 'Nel modulo dell\'intervento: Day hospital, Una notte o Ricovero con le notti.'),
             P('Stampa la lista operatoria', 'Una tabella per sala con età, telefono, chirurgo, anestesista, degenza e cosa '
               'manca della checklist.', 'a.bottone', 'Stampa la lista operatoria'),
             P('Posti letto', 'Notte per notte, quanti letti sono occupati. Salvando un intervento che non trova letto '
               'compare un avviso.', 'a.bottone', 'Posti letto'),
             P('Quanti letti', 'Il numero si scrive una volta in Configura → Anagrafiche → Nome, logo e colori.'),
         ]),
    dict(slug='chirurghi', gruppo='Sala operatoria', titolo='Giorni di sala dei chirurghi',
         in_breve='In che giorni opera ciascun chirurgo: la griglia dice chi è in sala e chi è libero.',
         endpoint='sala.chirurghi', apri=('sala.chirurghi', {}), foto='/sala/chirurghi',
         passi=[
             P('Proponi dagli interventi', 'Il programma spunta i giorni in cui ciascuno ha operato almeno due volte.',
               'a.bottone', 'Proponi dagli interventi'),
             P('Controlla e salva', 'Si tolgono o aggiungono spunte e si salva.', 'table.giorni-sala'),
             P('A cosa serve', 'La riga Sala operatoria in cima alla griglia dice chi è in sala e chi, operando di solito quel '
               'giorno, è ancora libero. Prenotando un chirurgo in un altro giorno compare un avviso.'),
         ]),
    # --------------------------------------------------------- cassa e fogli
    dict(slug='cassa', gruppo='Cassa e fogli', titolo='Pagamenti e chiusura di cassa',
         in_breve='Un clic sul metodo di pagamento; a fine giornata la chiusura di cassa da stampare.',
         endpoint='cassa.cassa_giorno', apri=('cassa.cassa_giorno', {'iso': 'OGGI'}), foto='/cassa/{martedi}',
         passi=[
             P('Apri la cassa', 'Menu Cassa: gli incassi del giorno e chi deve ancora pagare.'),
             P('Registra', 'Accanto a chi deve pagare, il pulsante del metodo (Contanti, POS…) registra l\'importo previsto. '
               'Altro… per un importo diverso.', '.pulsanti-stato, form.in-linea button', 'Contanti'),
             P('Chiusura', 'Stampa la chiusura di cassa: totali per metodo di pagamento.', 'button', 'Stampa la chiusura'),
             P('Il mese', 'Mese mostra i totali giorno per giorno, anche in Excel.', 'a.bottone', 'Mese'),
         ]),
    dict(slug='riepilogo', gruppo='Cassa e fogli', titolo='Riepilogo del mese per medico',
         in_breve='Da Statistiche: un foglio per medico da stampare, scaricare in Excel o mandare per email.',
         endpoint='viste.statistiche', apri=('viste.statistiche', {}), foto='/statistiche',
         passi=[
             P('Dalle statistiche', 'Menu Statistiche → Riepilogo del mese per medico.', 'a.bottone', 'Riepilogo del mese'),
             P('Scegli', 'Tutti i medici o uno solo; frecce per il mese prima e dopo.'),
             P('Manda', 'Stampa (un medico per pagina), Scarica in Excel, o Manda per email con il messaggio già scritto.'),
         ]),
    dict(slug='stampare-giornata', gruppo='Cassa e fogli', titolo='Stampare la giornata',
         in_breve='Dalla griglia, Stampa e scarica: il foglio del giorno, le agende dei medici, l\'Excel.',
         endpoint='giorno', apri=('giorno', {'iso': 'OGGI'}), foto='/giorno/{martedi}?struttura=1',
         passi=[
             P('Stampa e scarica', 'Nella barra della griglia: il foglio del giorno, un foglio per medico (anche per email), '
               'la lista operatoria, il planning in Excel.', '[data-guida="giorno-stampa"]'),
             P('Le colonne', 'Quali colonne, foglio verticale o orizzontale: Configura → Impostazioni → Foglio del giorno.'),
         ]),
    # ---------------------------------------------------------- configurazione
    dict(slug='griglia', gruppo='Primi passi', titolo='Leggere la griglia del giorno',
         in_breve='Colori, fasce libere e chiuse, i segni sugli appuntamenti.',
         endpoint='giorno', apri=('giorno', {'iso': 'OGGI'}), foto='/giorno/{domani}?struttura=1',
         passi=[
             P('Un giorno alla volta', 'Le frecce cambiano giorno (anche ← → sulla tastiera), Vai a oggi torna a oggi.',
               '.barra .comandi .passo'),
             P('Fasce libere', 'Le celle bianche con "libero" sono dentro un turno: clic per prenotare. Le grigie sono chiuse.',
               'td.aperta'),
             P('Gli appuntamenti', 'Il bordo colorato è il medico. Verde: arrivato; ✓: confermato. Clic per aprirlo.',
               'a.voce'),
             P('Interventi', 'Negli interventi il numero arancione è la checklist (3/5) e il riquadro viola la degenza.',
               '.segni-sala'),
             P('Sala operatoria', 'La riga in alto: quanti interventi, checklist da completare, letti della notte, chi è in sala.',
               '.sala-giorno'),
             P('Nota del giorno', 'Un appunto per tutta la giornata: "Lippiello arriva alle 10". Si vede anche in stampa.',
               'details.nota-giorno, .nota-giorno'),
         ]),
    dict(slug='importare', gruppo='Configurazione', titolo='Importare dai file Excel',
         in_breve='Rubrica dei pazienti o agende vecchie: il programma riconosce le colonne e mostra un\'anteprima.',
         endpoint='importa.carica', apri=('importa.carica', {}), foto='/importa',
         passi=[
             P('Scegli il file', '.xlsx o .csv (va bene anche il .txt "Testo Unicode" di Excel). Il vecchio .xls va '
               'salvato prima come .xlsx da Excel.', 'input[type="file"]'),
             P('Anteprima', 'Carica e mostra l\'anteprima: niente viene salvato finché non si conferma. Le colonne si possono '
               'correggere.', 'button[type="submit"]', 'Carica'),
             P('Importa', 'Prima di importare il programma fa un backup. Le righe in conflitto finiscono fra i Da confermare.'),
         ]),
    dict(slug='backup', gruppo='Configurazione', titolo='Backup e ripristino',
         in_breve='Una copia al giorno è automatica; si può farne una subito e tornare a una copia.',
         endpoint='viste.impostazioni', apri=('viste.impostazioni', {}), foto='/impostazioni#backup',
         passi=[
             P('Automatico', 'Ogni giorno il programma fa una copia verificata e tiene le ultime 30 più una al mese.',
               '#backup'),
             P('Adesso', 'Fai un backup adesso, prima di un\'operazione importante.', 'button', 'Fai un backup adesso'),
             P('Un\'altra cartella', 'Meglio una chiavetta o una cartella di rete: si sceglie nella stessa sezione.'),
         ]),
    dict(slug='aggiornare', gruppo='Configurazione', titolo='Aggiornare a una versione nuova',
         in_breve='Quando esce una versione nuova il programma lo dice: «Aggiorna adesso», e in un minuto si riapre '
                  'aggiornato. I dati restano.',
         endpoint='aggiornamenti.pagina', apri=('aggiornamenti.pagina', {}), foto='/aggiornamenti',
         passi=[
             P('La notifica', 'Quando c\'è una versione nuova compare la notifica «Aggiornamento disponibile»: un clic '
               'apre la pagina degli aggiornamenti, che è anche in Configura → Aggiornamenti.'),
             P('Cosa arriva', 'La pagina dice quale versione è installata, quale è pronta e cosa porta di nuovo.',
               '[data-guida="aggiornamento-stato"]'),
             P('Aggiorna adesso', 'Il programma fa prima una copia di sicurezza dei dati, poi si chiude, si aggiorna e si '
               'riapre da solo: circa un minuto. Meglio farlo quando non si sta prenotando.', '[data-guida="aggiorna-adesso"]'),
             P('Le novità', 'Finito l\'aggiornamento si apre la pagina delle novità, con i loro video. Si ritrova in '
               'Aiuto → Novità.'),
             P('I dati restano', 'Non serve disinstallare niente: appuntamenti, pazienti, documenti e impostazioni stanno '
               'in una cartella a parte (%LOCALAPPDATA%\\GestionaleAgende), che né l\'aggiornamento né la '
               'disinstallazione toccano.'),
             P('Da dove arriva', 'L\'indirizzo è già scritto: quello predefinito, le versioni del Gestionale Agende su '
               'GitHub. Non serve toccarlo. Vuoto, gli aggiornamenti automatici si spengono; «Rimetti l\'indirizzo '
               'predefinito» li riaccende.', '[data-guida="aggiornamenti-indirizzo"]'),
             P('A mano', 'Senza internet si aggiorna come prima: doppio clic sul Setup nuovo (GestionaleAgende-setup.exe), '
               'Avanti, Fine. Il Setup dice quale versione c\'è e quale arriva.'),
         ]),
    dict(slug='aspetto', gruppo='Configurazione', titolo='Logo, colori e tema scuro',
         in_breve='Il nome e il logo della struttura, il colore del programma, il tema chiaro o scuro.',
         endpoint='viste.impostazioni', apri=('viste.impostazioni', {}), foto='/impostazioni',
         passi=[
             P('Tema', 'Chiaro, scuro o come Windows: vale per questo PC. Le stampe restano chiare.', '#aspetto-tema'),
             P('Logo e colori', 'Configura → Anagrafiche → Nome, logo e colori: caricando un logo si propone il suo colore.'),
             P('Foglio del giorno', 'Colonne e orientamento della stampa.', '#stampa'),
         ]),
]

ARTICOLI += [
    # ------------------------------------------------------- email e WhatsApp
    dict(slug='email-gmail', gruppo='Email e WhatsApp', titolo='Collegare l\'email della clinica',
         in_breve='Le email ai pazienti partono dall\'account Gmail della clinica, con una "password per le app".',
         endpoint='invii.pagina', apri=('invii.pagina', {}), foto='/invii#email',
         passi=[
             P('Apri la pagina', 'Menu Configura → Email e WhatsApp.', 'nav.menu [data-guida="menu-configura"]'),
             P('La password per le app', 'Gmail non accetta la password normale: con la verifica in due passaggi attiva, in '
               'myaccount.google.com/apppasswords si crea una password di 16 lettere. I passi sono nella pagina.',
               '[data-guida="email-istruzioni"]'),
             P('Indirizzo e password', 'L\'indirizzo è già proposto (quello della struttura): si incolla la password per le '
               'app e si salva. Resta in questo PC, cifrata con la protezione di Windows.', '[data-guida="email-account"]'),
             P('Prova', 'Manda la prova al proprio indirizzo: se arriva, le email ai pazienti partono.',
               '[data-guida="email-prova"]'),
         ]),
    dict(slug='email-automatiche', gruppo='Email e WhatsApp', titolo='Email automatiche alla prenotazione',
         in_breve='La preparazione agli esami endoscopici parte da sola, con le informative allegate, appena si prenota.',
         endpoint='invii.pagina', apri=('invii.pagina', {}), foto='/invii#regole',
         passi=[
             P('Le email', 'Raggruppate per medico, con oggetto, testo e PDF allegati; in fondo quelle per tutti i medici. '
               'Per il Dr. Galasso c\'è quella già pronta: un clic e parte per EGDS e colonscopia.', '#regole'),
             P('Nuova email', 'Si sceglie il medico (o tutti i medici) e Crea: prestazioni, testo (con giorno e ora '
               'dell\'appuntamento, se servono) e i PDF. Prova la manda al proprio indirizzo prima di attivarla.',
               '[data-guida="nuova-regola"]'),
             P('Alla prenotazione', 'Salvando l\'appuntamento compare "Email … in partenza per …". Se il paziente non ha '
               'l\'email lo dice subito: la si aggiunge e la si manda dalla pagina dell\'appuntamento.'),
             P('A comando', 'Nella pagina dell\'appuntamento, riquadro Email e WhatsApp al paziente: Manda l\'email (anche di '
               'nuovo) e Manda il promemoria adesso.'),
             P('Il registro', 'Registro, in alto, porta in fondo alla pagina: cosa è partito, cosa è in coda, cosa non è '
               'partito e perché. Senza rete si riprova da solo; per un errore da correggere, Riprova.',
               '.stato-invii a[href="#registro"]'),
         ]),
    dict(slug='email-per-medico', gruppo='Email e WhatsApp', titolo='Un\'email diversa per ogni medico',
         in_breve='Ogni medico può avere le sue informative: per le sue prestazioni parte la sua email, non quella '
                  'per tutti.',
         endpoint='invii.pagina', apri=('invii.pagina', {}), foto='/invii#regole',
         passi=[
             P('Una per medico', 'Ogni medico ha il suo gruppo, con le sue email e i suoi PDF. "Nuova email per…" sotto il '
               'gruppo ne aggiunge un\'altra per lui.', '.gruppo-regole h3'),
             P('Chi parte', 'Per la stessa prestazione parte l\'email del medico al posto di quella per tutti i medici: '
               'sotto ogni email è scritto dove ne sostituisce un\'altra. Un\'email del medico senza prestazioni spuntate '
               'si aggiunge alle altre.', '.gruppo-regole .nota-riga', 'Al posto di'),
             P('Per un medico nuovo', 'Si sceglie il medico e Crea: il medico è già scelto, restano prestazioni, testo e PDF.',
               '[data-guida="nuova-regola"]'),
             P('Partire da una già fatta', 'Aperta un\'email, in fondo "Duplica per un altro medico": una copia spenta con '
               'testo e PDF. Si mettono le informative del medico, si spunta Attiva e si salva.'),
             P('Due email allo stesso paziente', 'Se due email partono per lo stesso appuntamento il programma lo dice, '
               'salvando e nella pagina dell\'email: a volte è voluto, altrimenti se ne spegne una.'),
         ]),
    dict(slug='promemoria', gruppo='Email e WhatsApp', titolo='Promemoria del giorno prima',
         in_breve='Ogni giorno all\'ora scelta il promemoria parte su WhatsApp o per email a chi ha appuntamento domani.',
         endpoint='invii.pagina', apri=('invii.pagina', {}), foto='/invii#promemoria',
         passi=[
             P('Accendi', 'Spunta "Manda i promemoria da solo", scegli l\'ora e i canali, salva. Il venerdì (con il sabato '
               'chiuso) partono anche quelli di lunedì.', '[data-guida="promemoria"]'),
             P('WhatsApp', 'Per i WhatsApp automatici serve la piattaforma WhatsApp Business di Meta: numero dedicato, modello '
               'approvato, token. Finché manca, i promemoria vanno per email a chi ce l\'ha.', '[data-guida="whatsapp-requisiti"]'),
             P('Nelle conferme', 'La pagina Conferme dice per ogni paziente cosa è partito; chi non ha né cellulare né email '
               'resta da chiamare come prima.'),
         ]),
]

PER_SLUG = {a['slug']: a for a in ARTICOLI}
GRUPPI = ['Primi passi', 'Tutti i giorni', 'Sala operatoria', 'Cassa e fogli', 'Email e WhatsApp', 'Configurazione']


def collega(app):
    app.register_blueprint(bp)

    @app.context_processor
    def funzioni_guida():
        return {'guide_della_pagina': guide_della_pagina, 'video_guida': video}


def indirizzo_apri(a, guida=True):
    endpoint, argomenti = a['apri']
    valori = {'OGGI': date.today().isoformat(), 'MESE': date.today().strftime('%Y-%m')}
    argomenti = {k: valori.get(v, v) if isinstance(v, str) else v for k, v in argomenti.items()}
    if guida and a['endpoint'] == endpoint:
        argomenti['guida'] = a['slug']
    return url_for(endpoint, **argomenti)


def con_guida(percorso, slug):
    """L'indirizzo di una pagina con la guida sullo schermo accesa (?guida=...),
    prima dell'eventuale #ancora: '/invii#regole' -> '/invii?guida=x#regole'."""
    pagina, _, ancora = percorso.partition('#')
    pagina += ('&' if '?' in pagina else '?') + 'guida=' + slug
    return pagina + ('#' + ancora if ancora else '')


def guide_della_pagina():
    """Per il menu Aiuto: le guide sullo schermo della pagina aperta, in JSON."""
    ep = request.endpoint or ''
    trovate = [{'slug': a['slug'], 'titolo': a['titolo'], 'condizione': a.get('condizione', '')}
               for a in ARTICOLI if a['endpoint'] == ep and any('sel' in p for p in a['passi'])]
    return json.dumps(trovate, ensure_ascii=False)


def immagine(slug):
    """L'indirizzo dell'immagine dell'articolo; None se non e' stata prodotta."""
    from modelli import cartella_risorse
    if not os.path.exists(os.path.join(cartella_risorse(), 'static', 'guida', '%s.png' % slug)):
        return None
    return url_for('static', filename='guida/%s.png' % slug)


_durate = {}


def durate_video():
    """Secondi di ogni videoguida, scritti da genera_video_guida.py in
    static/video/durate.json; letti una volta sola."""
    if 'tutte' not in _durate:
        from modelli import cartella_risorse
        try:
            with open(os.path.join(cartella_risorse(), 'static', 'video', 'durate.json'), encoding='utf-8') as f:
                letti = json.load(f)
            _durate['tutte'] = {k: v for k, v in letti.items() if isinstance(v, (int, float))} if isinstance(letti, dict) else {}
        except (OSError, ValueError):
            _durate['tutte'] = {}
    return _durate['tutte']


def video(slug):
    """La videoguida dell'articolo: {'url': …, 'durata': '1:25'} oppure None
    se non e' stata prodotta."""
    from modelli import cartella_risorse
    if not slug or not re.fullmatch(r'[a-z0-9-]{1,40}', slug) or \
            not os.path.exists(os.path.join(cartella_risorse(), 'static', 'video', '%s.webm' % slug)):
        return None
    secondi = durate_video().get(slug)
    return {'url': url_for('static', filename='video/%s.webm' % slug),
            'durata': '%d:%02d' % divmod(int(round(secondi)), 60) if secondi else ''}


@bp.route('')
def indice():
    q = ' '.join((request.args.get('q') or '').lower().split())[:60]
    scelti = [a for a in ARTICOLI if not q or q in (a['titolo'] + ' ' + a['in_breve'] + ' ' +
                                                   ' '.join(p['titolo'] + ' ' + p['testo'] for p in a['passi'])).lower()]
    gruppi = [(g, [a for a in scelti if a['gruppo'] == g]) for g in GRUPPI]
    return render_template('aiuto.html', gruppi=[x for x in gruppi if x[1]], q=q, n=len(scelti),
                           indirizzo_apri=indirizzo_apri, sezione='aiuto')


@bp.route('/stampa')
def stampa():
    return render_template('aiuto_stampa.html', gruppi=[(g, [a for a in ARTICOLI if a['gruppo'] == g]) for g in GRUPPI],
                           immagine=immagine, oggi=date.today())


@bp.route('/<slug>')
def articolo(slug):
    a = PER_SLUG.get(slug)
    if a is None:
        abort(404)
    stesso = [x for x in ARTICOLI if x['gruppo'] == a['gruppo'] and x['slug'] != slug]
    return render_template('aiuto_articolo.html', a=a, immagine=immagine, altri=stesso,
                           indirizzo_apri=indirizzo_apri, con_giro=any('sel' in p for p in a['passi']),
                           sezione='aiuto')


@bp.route('/<slug>/passi.json')
def passi_json(slug):
    """I passi per la guida sullo schermo."""
    a = PER_SLUG.get(slug)
    if a is None:
        abort(404)
    testo = json.dumps({'slug': a['slug'], 'titolo': a['titolo'], 'passi': a['passi'],
                        'articolo': url_for('guida.articolo', slug=slug)}, ensure_ascii=False)
    testo = testo.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    r = Response(testo, mimetype='application/json')
    r.headers['Cache-Control'] = 'no-store'
    return r
