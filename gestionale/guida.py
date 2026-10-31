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
import logging
import os
import re
from datetime import date, timedelta

from flask import Blueprint, render_template, abort, url_for, request, Response, redirect

bp = Blueprint('guida', __name__, url_prefix='/aiuto')


def P(titolo, testo, sel=None, contiene=None):
    d = {'titolo': titolo, 'testo': testo}
    if sel:
        d['sel'] = sel
    if contiene:
        d['contiene'] = contiene
    return d


# endpoint: la pagina dove si fa (per la guida sullo schermo)
# apri: come aprirla dal programma (endpoint, argomenti; 'OGGI' = la data di oggi, 'MESE' = il mese,
#   'FASCE' = il primo giorno da oggi con un turno a fasce proprie, nella sua struttura)
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
             P('Turni', 'I turni del personale (medici, infermieri, OSS e gli altri) nel mese, nella settimana e nel '
               'giorno a ore.', 'nav.menu [data-guida="menu-turni"]'),
             P('Dove si fa', 'In quale struttura del gruppo si fa una prestazione: si scrive la prestazione e si vedono le '
               'strutture, i loro recapiti e il messaggio pronto per il paziente.', 'nav.menu [data-guida="menu-dove"]'),
             P('Segreteria', 'Il lavoro di tutti i giorni oltre a prenotare: conferme, da confermare, chiusura della '
               'giornata, cose da fare, lista d\'attesa. Il numero arancione dice quante prenotazioni sono in sospeso.',
               'nav.menu [data-guida="menu-segreteria"]'),
             P('Cerca', 'Scrivere qui (o premere il tasto /) un cognome, un telefono, un giorno come "domani" o "24/9", '
               'oppure una prestazione per sapere dove si fa.', 'nav.menu [data-guida="menu-cerca"]'),
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
               'lunedì dalle 8 alle 14. Si ripete ogni settimana. "Durata delle fasce" dice ogni quanto comincia una '
               'visita in quel turno (vedi Le fasce di ogni ambulatorio).', 'a.bottone.aggiungi', 'Aggiungi turno'),
             P('Chi viene senza giorno fisso', 'Per una sostituzione o per chi viene ogni tanto c\'è il turno di un giorno solo.',
               'a.bottone.aggiungi', 'Aggiungi turno di un giorno'),
             P('Ferie e assenze', 'Nei giorni di assenza i turni del medico non aprono fasce, e il programma elenca gli '
               'appuntamenti da spostare.', 'a.bottone.aggiungi', 'Aggiungi assenza'),
             P('Quando un turno finisce', 'Si apre il turno e si scrive la data in "Fino al". Eliminarlo toglierebbe le '
               'sue ore anche dalle statistiche dei mesi già passati.'),
             P('Le sue email', 'Aprendo il medico, in fondo ci sono le email automatiche ai suoi pazienti e "Nuova email '
               'per questo medico", se ha informative sue.'),
         ]),
    dict(slug='fasce-turno', gruppo='Primi passi', titolo='Le fasce di ogni ambulatorio',
         in_breve='Ogni turno può avere fasce sue (visite ogni 20 minuti, endoscopia ogni 15): la prestazione '
                  'occupa le fasce intere che le servono.',
         endpoint='giorno', apri=('giorno', {'iso': 'FASCE'}), condizione='thead .fasce-turno',
         foto='/giorno/{martedi}?struttura=1',
         passi=[
             P('La durata delle fasce', 'Configura → Anagrafiche, Modifica sul turno, "Durata delle fasce": ogni quanto '
               'comincia una fascia, dall\'ora di inizio del turno. "Come la struttura" lascia le fasce di tutta la '
               'clinica, che si scelgono nella struttura.'),
             P('Nella griglia', 'La colonna lo dice in alto: "fasce da 15\'". Le altre stanze restano come prima.',
               'thead .fasce-turno'),
             P('Le fasce libere', 'Ogni fascia libera mostra la sua ora: un clic e il modulo si apre con quell\'orario e '
               'il medico di turno.', 'td.aperta a.con-ora'),
             P('Fasce intere', 'La prestazione occupa tutte le fasce che tocca: una colonscopia da 45 minuti con fasce da '
               '15 ne occupa tre, una visita più corta della fascia la occupa tutta. Nella stessa fascia il programma '
               'non salva un altro appuntamento.', 'td.occupata', 'Colonscopia'),
             P('Prima disponibilità e orari a mano', 'Prima disponibilità e Sposta propongono le ore delle fasce. Un\'ora '
               'scritta a mano che non è l\'inizio di una fascia si salva, con un avviso che lo dice.'),
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
    # ------------------------------------------------------------- dove si fa
    dict(slug='dove-si-fa', gruppo='Dove si fa', titolo='Dove si fa una prestazione: indirizzare il paziente',
         in_breve='Si scrive la prestazione: le strutture del gruppo dove si fa, i loro recapiti e il messaggio già '
                  'pronto per il paziente, da copiare, mandare su WhatsApp o per email, o stampare.',
         endpoint='dovesifa.pagina', apri=('dovesifa.pagina', {'q': 'ecografia'}), condizione='#q-dove',
         foto='/dove-si-fa/?q=rm+ginocchio&voce=1&gruppo=2&struttura=1',
         passi=[
             P('Apri la pagina', 'Menu Dove si fa, o il tasto D. Si può anche scrivere la prestazione nella ricerca in alto '
               '(tasto /): le prestazioni compaiono insieme ai pazienti.', 'nav.menu [data-guida="menu-dove"]'),
             P('Scrivi la prestazione', 'Come la dice il paziente: «risonanza ginocchio», «tac torace», «eco addome», '
               '«holter». Bastano le prime lettere; valgono le sigle d\'uso (RM, TC, RX, ECG, MOC) e i sinonimi del '
               'database. Una parola scritta male si corregge da sola.', '#q-dove'),
             P('Dove si fa', 'Sotto ogni prestazione le strutture dove si fa, ciascuna con il suo colore. «qui» è questa '
               'struttura; «da confermare» vuol dire che il database non ne è sicuro: meglio chiedere alla struttura '
               'prima di mandarci il paziente.', '[data-guida="dove-sedi"]'),
             P('La scheda della struttura', 'Un clic sulla struttura apre la sua scheda: indirizzo con la mappa, telefoni, '
               'prenotazione online, orari e come si prenota. Esc la chiude.', '.recapiti-scheda'),
             P('Il messaggio per il paziente', 'Già scritto, con la prestazione e i recapiti; si può cambiare. Copia, '
               'WhatsApp, Email, oppure Stampa per un foglio da dare al paziente allo sportello.',
               '[data-guida="dove-azioni"]'),
             P('Segna come indirizzato', 'Il registro dei pazienti mandati alle altre strutture: si vede in «Pazienti '
               'indirizzati», nelle Statistiche e in Excel. WhatsApp, email e stampa si segnano da sole, con Annulla se '
               'non serviva.', '[data-guida="dove-segna"]'),
             P('Per un paziente', 'Scegliendo il paziente (anche dalla sua scheda: «Dove si fa una prestazione») il '
               'messaggio porta il suo nome e WhatsApp ed email partono verso i suoi recapiti.',
               '[data-guida="dove-paziente"]'),
             P('Si fa anche qui', 'Se la prestazione è anche nel listino di questo gestionale, sopra i risultati c\'è il '
               'collegamento per prenotarla subito.'),
         ]),
    dict(slug='strutture-gruppo', gruppo='Dove si fa', titolo='Il database delle prestazioni e i recapiti',
         in_breve='Il file Excel del gruppo con le prestazioni di ogni struttura: si carica una volta e di nuovo a ogni '
                  'versione; i recapiti delle strutture si scrivono nel programma.',
         endpoint='dovesifa.strutture', apri=('dovesifa.strutture', {}), foto='/dove-si-fa/strutture',
         passi=[
             P('Apri la pagina', 'Menu Configura → Strutture del gruppo.', 'nav.menu [data-guida="menu-configura"]'),
             P('Carica il database', 'Il file Excel del database delle prestazioni: una riga per prestazione e una colonna '
               'per struttura, con una X dove si fa. Prima si vede cosa cambia e si conferma; il programma fa una copia '
               'di sicurezza.', '[data-guida="gruppo-carica"]'),
             P('Una versione nuova', 'Quando il database viene aggiornato si carica il file nuovo allo stesso modo: si '
               'vedono le prestazioni nuove, quelle tolte e le strutture nuove. I recapiti scritti e il registro dei '
               'pazienti indirizzati restano.'),
             P('I recapiti', '«Recapiti», accanto a ogni struttura: indirizzo, telefoni, email, prenotazione online, orari '
               'e come si prenota. Finiscono nella scheda, nel messaggio e nel foglio per il paziente.',
               '[data-guida="gruppo-elenco"]'),
             P('Questa struttura', 'Una struttura del database con lo stesso nome di una di questo gestionale porta il '
               'segno «qui»; altrimenti si sceglie nei suoi recapiti.'),
             P('Spegnere una struttura', 'Togliendo la spunta «Compare nelle ricerche di Dove si fa» la struttura non '
               'viene più proposta, senza cancellare niente.'),
         ]),
    # ------------------------------------------------------------ turni del personale
    dict(slug='turni-personale', gruppo='Turni del personale', titolo='I turni del personale: il mese e la settimana',
         in_breve='Menu Turni: una riga per persona, una colonna per giorno. Clic sulla cella, oppure il codice scritto '
                  'da tastiera, come in un foglio di calcolo.',
         endpoint='personale.mese', apri=('personale.mese', {'aaaamm': 'MESE'}), foto='/personale/turni/mese/{mese}',
         passi=[
             P('Apri i turni', 'Menu Turni: il foglio del mese, con una riga per persona divisa per ruolo (medici, '
               'infermieri, OSS, tecnici, accettazione, ausiliari) e una colonna per giorno.',
               'nav.menu [data-guida="menu-turni"]'),
             P('Giorno, settimana, mese', 'Il mese è il foglio dei turni con i codici. La settimana mostra anche orari e '
               'aree, e le ore di ciascuno contro quelle del contratto. Il giorno è a ore: chi c\'è e quando.',
               '[data-guida="turni-viste"]'),
             P('I codici', 'Ogni turno ha un codice e un colore: M mattina, P pomeriggio, N notte, R riposo, F ferie… Si '
               'cambiano e se ne aggiungono in Tipi di turno.', '[data-guida="turni-legenda"]'),
             P('Mettere un turno', 'Clic sulla cella della persona nel giorno: si apre la scelta con tutti i turni. Oppure, '
               'con la cella scelta, si scrive il codice: il turno si mette e si passa al giorno dopo. Invio apre la '
               'scelta, le frecce si spostano.', '[data-guida="turni-griglia"]'),
             P('Più celle insieme', 'Trascinando con il mouse, o con Maiusc e le frecce, si scelgono più celle, anche di '
               'più persone: il turno va in tutte. Canc toglie i turni delle celle scelte.'),
             P('Orario diverso, area, nota', 'Nella scelta, «Orario diverso, area, nota»: un orario scritto a mano (per '
               'esempio 8–12), l\'area (Degenza, Sala operatoria…) o una nota; e un secondo turno nello stesso giorno.'),
             P('Annullare', 'Ogni modifica si annulla con Ctrl+Z, o con «Annulla» nell\'avviso in basso, e si rifà con '
               'Ctrl+Y.'),
             P('I controlli', 'Due turni della stessa persona che si sovrappongono, anche con la notte del giorno prima, non '
               'si salvano: il programma dice perché. Meno di 11 ore di riposo fra due turni si possono tenere, ma la '
               'cella ha un triangolino arancione.'),
             P('Totali e copertura', 'In fondo alla riga le ore lavorate (con quelle del contratto), le notti, i festivi e '
               'i giorni di assenza. Sotto ogni ruolo la copertura del giorno, quanti per turno: in rosso dove manca '
               'qualcuno rispetto alle coperture minime.', 'tr.copertura'),
             P('Filtri', 'Solo un ruolo (per esempio gli infermieri) o solo un\'area.', '[data-guida="turni-filtri"]'),
             P('Stampa ed Excel', 'In Strumenti: il foglio da stampare in orizzontale e il mese in Excel, con un secondo '
               'foglio di un turno per riga (per le paghe).', '[data-guida="turni-strumenti"]'),
         ]),
    dict(slug='turni-giorno', gruppo='Turni del personale', titolo='Il giorno a ore: chi c\'è e quando',
         in_breve='Turni → Giorno: una riga per persona sulle 24 ore, quanti al lavoro ora per ora, gli ambulatori dei '
                  'medici. Clic sulla riga per cambiare il turno.',
         endpoint='personale.giorno', apri=('personale.giorno', {'iso': 'OGGI'}),
         foto='/personale/turni/giorno/{martedi}',
         passi=[
             P('Il giorno a ore', 'Una riga per chi ha un turno quel giorno, sulla linea delle 24 ore; la notte cominciata '
               'il giorno prima parte da sinistra. La linea rossa è adesso.', '.scala-ore'),
             P('Quanti al lavoro', 'Per ogni ruolo, le barre dicono quante persone sono al lavoro ora per ora. «Manca '
               'qualcuno» se una copertura minima non è raggiunta.', '.riga-presenze .presenze'),
             P('Gli ambulatori', 'Per i medici collegati all\'agenda si vedono anche i loro ambulatori del giorno, '
               'tratteggiati (sotto il turno, se c\'è anche quello): così turno e agenda si confrontano a colpo '
               'd\'occhio.'),
             P('Cambiare un turno', 'Clic sulla riga della persona (o Invio, con il tasto Tab fin lì): si apre la stessa '
               'scelta della griglia. Si può anche scrivere il codice.', '.pista'),
             P('Riposi e assenze', 'Valgono tutto il giorno e compaiono accanto al nome.', '.nome-giorno .giorno-intero'),
             P('Un turno a chi non c\'è', '«Turno a…»: si sceglie la persona e poi il turno.', '#aggiungi-persona'),
         ]),
    dict(slug='turni-schema', gruppo='Turni del personale', titolo='Schema a rotazione e copia della settimana',
         in_breve='Una sequenza come M M P P N SN R R che si ripete da sola, persona per persona; oppure la settimana '
                  'prima copiata nelle celle vuote.',
         endpoint='personale.settimana', apri=('personale.settimana', {'iso': 'OGGI'}),
         foto='/personale/turni/settimana/{oggi}',
         passi=[
             P('Strumenti', 'Nella settimana e nel mese, Strumenti → «Schema a rotazione…»; nella settimana anche «Copia '
               'la settimana prima».', '[data-guida="turni-strumenti"]'),
             P('La sequenza', 'I codici che si ripetono giorno dopo giorno, per esempio M M P P N SN R R. Si scrivono o si '
               'compongono con i pulsanti colorati; un trattino è un giorno vuoto.'),
             P('Lo sfasamento', 'Con più persone ognuna comincia qualche giorno più avanti nella sequenza: con otto '
               'infermieri e una sequenza di otto giorni sfasata di uno, ogni giorno ci sono due mattine, due pomeriggi '
               'e una notte.'),
             P('Prima di applicare', 'Sotto si vede come verranno i primi giorni per le persone scelte. Le celle già piene '
               'restano come sono, a meno di «Sostituisci anche i turni già messi».'),
             P('Più veloce dalla griglia', 'Scelto prima un gruppo di celle nella griglia (persone e giorni), lo schema si '
               'apre già con quelle persone e quel periodo.', '[data-guida="turni-griglia"]'),
             P('Copia la settimana prima', 'Gli stessi turni della settimana precedente, nelle celle ancora vuote; poi si '
               'correggono le eccezioni.'),
         ]),
    dict(slug='turni-persone', gruppo='Turni del personale', titolo='Le persone del personale',
         in_breve='Turni → Persone: chi fa i turni, con ruolo e ore del contratto. I medici dell\'agenda si aggiungono '
                  'tutti insieme.',
         endpoint='personale.persone', apri=('personale.persone', {}), foto='/personale/persone',
         passi=[
             P('Aggiungi una persona', 'Cognome, nome e ruolo: medico, infermiere, OSS, tecnico, accettazione, ausiliario.',
               '[data-guida="persone-nuova"]'),
             P('Le ore del contratto', 'Le ore a settimana (36, oppure 37:30 o 37,5): nei turni si confrontano con quelle '
               'lavorate, settimana per settimana e nel mese.'),
             P('I medici dell\'agenda', '«Aggiungi i medici dell\'agenda» li aggiunge tutti insieme, già collegati: nella '
               'vista del giorno si vedono anche i loro ambulatori. Il pulsante c\'è finché qualche medico manca.'),
             P('Chi non lavora più', 'Nella sua scheda si toglie la spunta «In servizio»: non compare nei turni nuovi ma '
               'resta in quelli passati. Si può eliminare solo chi non ha turni.'),
             P('Modificare', 'Modifica, sulla riga della persona.', 'table.elenco-persone td.azione a'),
         ]),
    dict(slug='turni-tipi', gruppo='Turni del personale', titolo='Tipi di turno e coperture minime',
         in_breve='Turni → Tipi di turno: codici, orari e colori dei turni, e quante persone servono almeno, per ruolo '
                  'e turno.',
         endpoint='personale.tipi_turno', apri=('personale.tipi_turno', {}), foto='/personale/tipi',
         passi=[
             P('I tipi di turno', 'Codice, nome, orario e colore di ogni turno. Si comincia con mattina, pomeriggio, notte, '
               'giornata, reperibilità, smonto notte, riposo, ferie, malattia e permesso.', '[data-guida="tipi-elenco"]'),
             P('Un tipo nuovo', 'Codice (da una a quattro lettere o cifre), nome, categoria e colore; per lavoro e '
               'reperibilità anche inizio, fine e pausa. Le ore contate sono la durata meno la pausa; se la fine viene '
               'prima dell\'inizio, il turno finisce il giorno dopo.', '#modulo-tipo'),
             P('Le categorie', 'Lavoro: conta nelle ore e nella copertura. Reperibilità: ore a parte. Riposo e assenza: '
               'valgono tutto il giorno e non stanno insieme ad altri turni.'),
             P('Le coperture minime', 'Quante persone servono almeno, per ruolo e turno, nei giorni scelti (ed '
               'eventualmente in un\'area): dove manca qualcuno la copertura del giorno si colora di rosso.', '#coperture'),
             P('Cambiare un orario', 'I turni già messi tengono l\'orario di prima. Un tipo già usato non si elimina: '
               'smette solo di comparire fra quelli da mettere.'),
         ]),
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
    dict(slug='email-casella', gruppo='Email e WhatsApp', titolo='Collegare l\'email della clinica',
         in_breve='Le email ai pazienti partono da una casella della clinica: quella del sito (bastano indirizzo e '
                  'password), Aruba, Gmail o un altro server.',
         endpoint='invii.pagina', apri=('invii.pagina', {}), foto='/invii#email',
         passi=[
             P('Apri la pagina', 'Menu Configura → Email e WhatsApp.', 'nav.menu [data-guida="menu-configura"]'),
             P('Il tipo di casella', 'Va bene qualsiasi casella. Quella del sito della clinica (per esempio segreteria@ e '
               'il dominio del sito) è la più semplice: bastano indirizzo e password, niente verifica in due passaggi. '
               'Poi Aruba, Gmail (vuole la password per le app) o un altro server.', '[data-guida="email-tipo"]'),
             P('Come si collega', 'Le istruzioni cambiano con il tipo scelto: dove si crea la casella, quale password '
               'serve, cosa fare se il fornitore indica un altro server.', '[data-guida="email-istruzioni"]'),
             P('Indirizzo e password', 'L\'indirizzo è già proposto (quello della struttura): si scrive la password della '
               'casella (con Gmail la password per le app) e si salva. Resta in questo PC, cifrata con la protezione di '
               'Windows.', '[data-guida="email-account"]'),
             P('Server e accesso', 'Server, porta e sicurezza si compilano da soli con il tipo di casella; si cambiano solo '
               'se il fornitore ne indica altri. Il nome utente serve solo se è diverso dall\'indirizzo.',
               '[data-guida="email-server"]'),
             P('Prova', 'Manda la prova al proprio indirizzo: se arriva, le email ai pazienti partono. Se non parte, il '
               'messaggio dice cosa correggere (password, porta e sicurezza, nome del server).',
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
    dict(slug='whatsapp-numero', gruppo='Email e WhatsApp', titolo='Attivare i WhatsApp automatici',
         in_breve='Token e ID del numero da Meta, poi «Registra il numero» con un PIN di 6 cifre e una prova al proprio '
                  'cellulare.',
         endpoint='invii.pagina', apri=('invii.pagina', {}), foto='/invii#whatsapp',
         passi=[
             P('Cosa serve', 'I passi da fare in Meta, in ordine: account Meta Business, app con il caso d\'uso WhatsApp, '
               'numero dedicato verificato, modello di messaggio approvato, token permanente.',
               '[data-guida="whatsapp-requisiti"]'),
             P('Token e ID del numero', 'Si incollano qui e si preme «Salva WhatsApp». L\'ID lo mostra Meta in WhatsApp → '
               'Configurazione API; il token si crea con un utente di sistema, scadenza «mai».', '#wa_numero_id'),
             P('Registra il numero', 'Una volta sola: un PIN di 6 cifre e «Registra il numero». Se il numero ha già la '
               'verifica in due passaggi il PIN è quello; altrimenti questo diventa il suo PIN. Conservarlo.',
               '[data-guida="whatsapp-registra"]'),
             P('La prova', 'Una prova al proprio cellulare: se arriva, i promemoria del giorno prima possono partire.',
               'input[name="a"][type="tel"]'),
             P('Se qualcosa non va', 'Il messaggio dice cosa fare in parole semplici: token scaduto, PIN sbagliato, numero '
               'non registrato, modello non approvato. Nel Registro, in fondo alla pagina, l\'esito di ogni messaggio.'),
         ]),
]

PER_SLUG = {a['slug']: a for a in ARTICOLI}
# guide che hanno cambiato nome: il vecchio indirizzo porta a quella nuova
# (1.9.1: «email-gmail» e' diventata «email-casella», l'email va con ogni casella)
NOMI_VECCHI = {'email-gmail': 'email-casella'}
GRUPPI = ['Primi passi', 'Tutti i giorni', 'Dove si fa', 'Turni del personale', 'Sala operatoria', 'Cassa e fogli',
          'Email e WhatsApp', 'Configurazione']


def collega(app):
    app.register_blueprint(bp)

    @app.context_processor
    def funzioni_guida():
        return {'guide_della_pagina': guide_della_pagina, 'video_guida': video}


def giorno_con_fasce(entro=21):
    """(data, id della struttura) del primo giorno, da oggi e per tre settimane, in cui
    un turno ha fasce sue: "Mostrami sullo schermo" della guida sulle fasce apre quel
    giorno, dove ci sono i punti da illuminare. (oggi, None) se non ce n'e'."""
    oggi = date.today()
    try:
        from sqlalchemy import select
        import servizi
        import viste
        from modelli import Struttura
        s = viste.ses()
        strutture = s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).all()
        regole = servizi.Regole(s, oggi, oggi + timedelta(days=entro))
        for n in range(entro + 1):
            g = oggi + timedelta(days=n)
            for st in strutture:
                if any(t.passo_proprio for t in regole.turni_effettivi(g, st)):
                    return g, st.id
    except Exception:              # la pagina della guida si apre comunque, su oggi
        logging.exception('guida: ricerca del giorno con le fasce dei turni')
    return oggi, None


def indirizzo_apri(a, guida=True):
    endpoint, argomenti = a['apri']
    valori = {'OGGI': date.today().isoformat(), 'MESE': date.today().strftime('%Y-%m')}
    if 'FASCE' in argomenti.values():
        g, sid = giorno_con_fasce()
        valori['FASCE'] = g.isoformat()
        if sid:
            argomenti = dict(argomenti, struttura=sid)
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
    if slug in NOMI_VECCHI:
        return redirect(url_for('guida.articolo', slug=NOMI_VECCHI[slug]))
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
    if slug in NOMI_VECCHI:
        return redirect(url_for('guida.passi_json', slug=NOMI_VECCHI[slug]))
    a = PER_SLUG.get(slug)
    if a is None:
        abort(404)
    testo = json.dumps({'slug': a['slug'], 'titolo': a['titolo'], 'passi': a['passi'],
                        'articolo': url_for('guida.articolo', slug=slug)}, ensure_ascii=False)
    testo = testo.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    r = Response(testo, mimetype='application/json')
    r.headers['Cache-Control'] = 'no-store'
    return r
