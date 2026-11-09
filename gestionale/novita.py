# -*- coding: utf-8 -*-
"""Le novita' di ogni versione, scritte una volta sola e usate in tre posti:

1. la pagina Aiuto → Novità (dopo un aggiornamento si apre da sola), con il
   video della guida che spiega ciascuna novita';
2. la notifica «Novità della versione …» nei giorni dopo l'aggiornamento;
3. il file delle versioni pubblicato insieme al Setup (aggiornamento.json,
   lo scrive strumenti/prepara_aggiornamento.py): la pagina Configura →
   Aggiornamenti mostra cosa porta la versione nuova prima di installarla.

Una voce: titolo breve, testo in parole semplici e, se c'e', la guida che la
spiega (lo slug di guida.py: il suo video e il suo articolo).
Nessun import: lo legge anche prepara_aggiornamento.py, senza Flask."""

NOVITA = [
    ('1.12.3', [
        dict(titolo='Esportazioni in Excel: ambulatori, sala operatoria o tutto insieme',
             testo='Menu Ambulatori → Esportazioni in Excel: per il giorno, la settimana e il mese della data scelta, '
                   'un file solo degli ambulatori, uno solo della sala operatoria e uno con tutto insieme, dove '
                   'ambulatori e sala stanno in fogli separati. Nove pulsanti, un clic per ciascun file; ci si arriva '
                   'anche da «Altre esportazioni» nel giorno e nel mese e da «Stampa e scarica» nella settimana.',
             guida='esportazioni'),
        dict(titolo='La sala operatoria del mese',
             testo='Un Excel della sala per tutto il mese: giorno per giorno, per ogni sala la mattina e il pomeriggio '
                   'con i chirurghi e quanti interventi, i turni dei chirurghi con le date e gli interventi di ciascuno '
                   '(e chi ha operato fuori dai turni), e l\'elenco degli interventi del mese.',
             guida='esportazioni'),
        dict(titolo='La sala nella settimana e nel mese, anche in pagina',
             testo='La pianificazione della settimana e la programmazione del mese mostrano in fondo la sala '
                   'operatoria: chi opera e quanti interventi. Le mezze giornate libere degli ambulatori si contano '
                   'come prima.',
             guida='ambulatori'),
    ]),
    ('1.12.2', [
        dict(titolo='Il riepilogo live più chiaro',
             testo='In cima una frase dice com\'è la giornata. Gli appuntamenti di oggi sono divisi in fatti, in corso, '
                   'da segnare (orario passato senza l\'arrivo segnato) e da fare, e i quattro numeri sommano al totale. '
                   'Ogni stanza ha la sua linea del tempo con il turno del medico, le visite colorate e una linea rossa '
                   'sull\'ora di adesso, e dice perché è libera e fino a quando. Le mezze giornate libere sono in una '
                   'tabellina per giorno e per stanza. Le notifiche non coprono più la pagina.',
             guida='riepilogo-live'),
        dict(titolo='Il riepilogo del periodo',
             testo='Ambulatori → Riepilogo del periodo: com\'è andato un giorno, una settimana o un mese. Le ore di '
                   'turno delle stanze e quanto sono state occupate, le visite fatte, i non presentati, i disdetti e '
                   'quelli ancora da segnare, le mezze giornate senza nessun medico, per stanza, per medico e giorno per '
                   'giorno. Si scarica in Excel e si stampa.',
             guida='riepilogo-periodo'),
    ]),
    ('1.12.1', [
        dict(titolo='Le ore vere nelle notti del cambio dell\'ora',
             testo='Un turno di notte a cavallo del cambio dell\'ora legale conta le ore davvero lavorate (una in più a '
                   'ottobre, una in meno a marzo), nelle ore del mese, nei riposi e nei controlli dei turni.',
             guida='turni-personale'),
        dict(titolo='Codici dei turni scritti di seguito',
             testo='Nei turni del personale si possono scrivere i codici uno dopo l\'altro senza aspettare («M» e subito '
                   '«P»: mattina oggi, pomeriggio domani): il programma li separa come farebbe una persona, provando '
                   'prima i codici più lunghi (MA, PE e RE restano un codice solo).',
             guida='turni-personale'),
        dict(titolo='I file rovinati messi da parte si possono svuotare',
             testo='In Impostazioni → Controllo del programma si vede quanto spazio occupano i database rovinati messi '
                   'da parte dall\'autoriparazione e, con una conferma, si cancellano quelli più vecchi di tre mesi.',
             guida='autoriparazione'),
    ]),
    ('1.12', [
        dict(titolo='Pianificazione degli ambulatori',
             testo='La pagina Ambulatori → Pianificazione della settimana dice chi occupa ogni stanza, mattina e '
                   'pomeriggio, calcolato dai turni: una stanza senza nessuno è «DISPONIBILE», le ore avanzate sono '
                   'segnate come libere. Dal «+» di una cella si mette un medico (ogni settimana o quel giorno solo), '
                   'dalla «×» si toglie da quella settimana in poi.',
             guida='ambulatori'),
        dict(titolo='La matrice degli ambulatori in Excel',
             testo='Il foglio «Matrice turni ambulatori e disponibilità integrative» per la direzione sanitaria, con '
                   'intestazione, legenda e firme, si scarica già compilato: questa settimana (con assenze e chiusure) '
                   'oppure la settimana tipo.',
             guida='ambulatori'),
        dict(titolo='La programmazione ambulatori del mese',
             testo='Ambulatori → Programmazione del mese: per ogni specialità e medico il giorno della settimana, le '
                   'date del mese in cui viene davvero (tolte assenze, chiusure e festivi), l\'orario e la stanza, con le '
                   'note che spiegano i giorni saltati. In Excel, con il calendario giorno per giorno.',
             guida='programmazione'),
        dict(titolo='Riepilogo live di agende e ambulatori',
             testo='Ambulatori → Riepilogo live: come va la giornata adesso (fatti, in corso, da fare, in ritardo, '
                   'da confermare) e ogni stanza con il medico di turno, la visita in corso o fino a quando è libera; '
                   'le visite ora per ora e le mezze giornate libere dei prossimi giorni. Si rinnova da solo ogni '
                   'minuto; «Modo schermo» per il secondo monitor.',
             guida='riepilogo-live'),
        dict(titolo='Foglio del giorno più completo',
             testo='Su ogni foglio stampato si ripetono testata e piede, con il numero di pagina; ogni stanza dice '
                   'quanti appuntamenti ha, chi è di turno e chi è assente; le stanze con un medico ma senza '
                   'appuntamenti compaiono lo stesso; le colonne in più solo dove servono; i totali degli importi; '
                   'a scelta la data di nascita e una casella da spuntare a penna; si può stampare sempre anche con '
                   'disdetti e non presentati (barrati, con lo Stato e l\'ora di arrivo).',
             guida='aspetto'),
        dict(titolo='Tutti gli Excel con lo stesso aspetto',
             testo='Planning del giorno, elenco, statistiche, incassi, riepilogo medici, turni del personale, Dove si '
                   'fa e ambulatori: stesso stile di intestazione, foglio A4 adattato alla larghezza, intestazioni '
                   'ripetute su ogni pagina, numero di pagina, data di esportazione e righe dei totali dove servono.',
             guida='aspetto'),
        dict(titolo='Aggiornamenti anche se Windows non conosce il sito',
             testo='Il controllo degli aggiornamenti (e le email) riconosce i certificati dei siti con un elenco '
                   'portato dentro il programma: non dipende più da quelli che Windows ha già incontrato. Se un '
                   'controllo non riesce, la pagina dice perché e come aggiornare a mano dal browser.',
             guida='aggiornare'),
    ]),
    ('1.11', [
        dict(titolo='Il programma si ripara da solo',
             testo='Se il database si rovina (per esempio dopo che è saltata la corrente) il programma se ne accorge e '
                   'lo ripara: senza perdere niente quando si può, altrimenti rimettendo l\'ultima copia di sicurezza '
                   'buona e dicendo da che ora ricontrollare. Il file rovinato non si cancella: resta da parte per '
                   'l\'assistenza.',
             guida='autoriparazione'),
        dict(titolo='Se il programma si blocca, basta riaprirlo',
             testo='Cliccando l\'icona Agende mentre il programma è bloccato, quello bloccato si chiude e se ne apre '
                   'uno nuovo. Se una pagina resta ferma troppo a lungo, o mancano i file del programma, si riavvia '
                   'da solo. Se la porta del programma è occupata da un altro programma, si apre su un\'altra.',
             guida='autoriparazione'),
        dict(titolo='Copie di sicurezza più frequenti',
             testo='Oltre alla copia del giorno, una copia ogni due ore se ci sono state modifiche (si tengono le '
                   'ultime tre). Se la cartella scelta per le copie non si raggiunge (la chiavetta tolta), la copia si '
                   'fa lo stesso accanto al database, e le copie di tutte e due le cartelle si vedono in Impostazioni.',
             guida='backup'),
        dict(titolo='Controllo del programma',
             testo='In Impostazioni → «Controllo del programma» si vede com\'è il programma (database, copie, lavori '
                   'in sottofondo, spazio sul disco) e cosa ha riparato da solo; «Controlla adesso» fa il controllo '
                   'completo. Quello che ha riparato lo dice anche la campanella.',
             guida='autoriparazione'),
    ]),
    ('1.10', [
        dict(titolo='Fasce di ogni ambulatorio',
             testo='Ogni turno può avere fasce sue: Configura → Anagrafiche → il turno → «Durata delle fasce» '
                   '(per esempio visite ogni 20 minuti, endoscopia ogni 15). Prima la durata era una sola per tutta '
                   'la clinica; il resto della struttura resta com\'era.',
             guida='fasce-turno'),
        dict(titolo='La prestazione occupa fasce intere',
             testo='Nella griglia una colonscopia da 45 minuti con fasce da 15 ne occupa tre; una visita più corta '
                   'della fascia la occupa tutta. Così non restano buchi da prenotare per sbaglio, e un altro '
                   'appuntamento nella stessa fascia non si salva.',
             guida='fasce-turno'),
        dict(titolo='Prima disponibilità e spostamenti seguono le fasce',
             testo='Prima disponibilità e Sposta propongono gli orari delle fasce di ogni turno. Un orario scritto a '
                   'mano che non è l\'inizio di una fascia si salva con un avviso.',
             guida='fasce-turno'),
        dict(titolo='Gli appuntamenti già presi restano',
             testo='Cambiando le fasce di un turno gli appuntamenti già prenotati non si spostano: salvando il turno '
                   'il programma dice quanti non stanno nelle fasce nuove, da controllare nella griglia. Si possono '
                   'sempre modificare.',
             guida='fasce-turno'),
    ]),
    ('1.9.1', [
        dict(titolo='L\'email con qualsiasi casella, anche senza Gmail',
             testo='In Configura → Email e WhatsApp si sceglie il tipo di casella: quella del sito della clinica '
                   '(bastano indirizzo e password, niente verifica in due passaggi), Aruba, Gmail o un altro server. '
                   'Server, porta e sicurezza si compilano da soli. La casella Gmail già collegata continua a '
                   'funzionare com\'è.',
             guida='email-casella'),
        dict(titolo='Se un\'email non parte, il motivo in chiaro',
             testo='Il messaggio dice cosa correggere: la password, porta e sicurezza che non vanno insieme, il nome '
                   'del server sbagliato o con un certificato che non corrisponde. Salvando, il programma avvisa già '
                   'delle scelte che di solito non funzionano.',
             guida='email-casella'),
        dict(titolo='Nome utente diverso e server della rete interna',
             testo='Per i fornitori che danno un nome utente diverso dall\'indirizzo c\'è il suo campo; per un '
                   'server della rete interna che non chiede la password basta una spunta.',
             guida='email-casella'),
    ]),
    ('1.9', [
        dict(titolo='Dove si fa: in quale struttura del gruppo',
             testo='Nuovo menu Dove si fa (tasto D): si scrive la prestazione come la dice il paziente («risonanza '
                   'ginocchio», «tac torace», «holter») e si vedono subito le strutture del gruppo dove si fa. Valgono '
                   'le sigle d\'uso (RM, TC, RX, ECG…) e le parole scritte male si correggono da sole.',
             guida='dove-si-fa'),
        dict(titolo='La scheda della struttura e il messaggio per il paziente',
             testo='Un clic sulla struttura: indirizzo, telefoni, prenotazione online, orari e come si prenota, con il '
                   'messaggio già scritto per il paziente da copiare, mandare su WhatsApp o per email, o stampare. I '
                   'pazienti indirizzati restano in un registro, anche nelle Statistiche e in Excel.',
             guida='dove-si-fa'),
        dict(titolo='Il database delle prestazioni del gruppo',
             testo='Configura → Strutture del gruppo: si carica il file Excel con le prestazioni di ogni struttura (prima '
                   'si vede cosa cambia, poi si conferma) e si scrivono i recapiti di ciascuna. Per una versione nuova del '
                   'database basta caricarla allo stesso modo.',
             guida='strutture-gruppo'),
        dict(titolo='Anche dalla ricerca e dalla scheda del paziente',
             testo='La ricerca in alto (tasto /) trova anche le prestazioni e dice dove si fanno; dalla scheda di un '
                   'paziente, «Dove si fa una prestazione» prepara il messaggio con il suo nome.',
             guida='dove-si-fa'),
    ]),
    ('1.8', [
        dict(titolo='Turni del personale',
             testo='Nuovo menu Turni: medici, infermieri, OSS, tecnici, accettazione e ausiliari, nel mese, nella '
                   'settimana e nel giorno a ore. I turni si mettono con un clic sulla cella o scrivendo il codice (M, P, '
                   'N…), come in un foglio di calcolo; Ctrl+Z annulla. Stampa ed Excel del mese.',
             guida='turni-personale'),
        dict(titolo='Controlli, ore e coperture minime',
             testo='Due turni della stessa persona che si sovrappongono (anche con la notte del giorno prima) non si '
                   'salvano; meno di 11 ore di riposo si segnalano. In fondo alla riga ore lavorate contro quelle del '
                   'contratto, notti, festivi e assenze; con le coperture minime il giorno in cui manca qualcuno si '
                   'colora di rosso.',
             guida='turni-tipi'),
        dict(titolo='Il giorno a ore e «In servizio oggi»',
             testo='La vista Giorno mostra chi c\'è ora per ora, ruolo per ruolo, con gli ambulatori dei medici '
                   'dall\'agenda. Nella pagina Oggi la scheda «In servizio oggi» dice chi lavora e chi è già al lavoro.',
             guida='turni-giorno'),
        dict(titolo='Schema a rotazione e copia della settimana',
             testo='Una sequenza come M M P P N SN R R si ripete da sola per le persone scelte, ognuna sfasata di '
                   'qualche giorno, e prima di applicarla si vede come verrà. La settimana si copia dalla precedente.',
             guida='turni-schema'),
        dict(titolo='Persone e tipi di turno',
             testo='Turni → Persone: il personale con ruolo e ore del contratto; i medici dell\'agenda si aggiungono '
                   'tutti con un clic. Turni → Tipi di turno: codici, orari, colori e coperture minime.',
             guida='turni-persone'),
        dict(titolo='WhatsApp: il numero si registra dal programma',
             testo='In Configura → Email e WhatsApp c\'è il passo che mancava: «Registra il numero», con il PIN di 6 '
                   'cifre. E gli errori di Meta ora si spiegano in parole semplici (token scaduto, PIN sbagliato, '
                   'numero non registrato…).',
             guida='whatsapp-numero'),
        dict(titolo='La tendina «Stampa e scarica» si vede per intero',
             testo='Nella versione con le animazioni, aprendo Stampa e scarica nella griglia del giorno, la tendina '
                   'restava in parte sotto la nota del giorno, gli avvisi e la griglia. Ora si vede sempre per intero, e '
                   'anche le tendine del menu restano sopra le notifiche.',
             guida='stampare-giornata'),
    ]),
    ('1.7', [
        dict(titolo='Codice fiscale controllato mentre si scrive',
             testo='Nella scheda del paziente e nella prenotazione il codice fiscale si controlla mentre lo si scrive: '
                   'se è sbagliato il programma dice cosa non va (per esempio l\'ultima lettera) e non lo salva. Da un '
                   'codice giusto si riempiono da soli data, sesso e luogo di nascita.',
             guida='codice-fiscale'),
        dict(titolo='Codice fiscale calcolato dai dati',
             testo='Senza la tessera sanitaria sottomano: con cognome, nome, sesso, data e luogo di nascita il codice si '
                   'calcola da solo. Il luogo si sceglie dall\'elenco dei comuni, anche quelli che non esistono più, e '
                   'degli stati esteri.',
             guida='codice-fiscale'),
        dict(titolo='Controllo dei codici fiscali in archivio',
             testo='Pazienti → Controllo dei codici fiscali: i codici già salvati che non vanno, quelli che non '
                   'corrispondono ai dati, lo stesso codice su due schede, e chi è senza codice, a partire da chi ha un '
                   'appuntamento. Aggiornando, sesso, luogo e data di nascita si ricavano dai codici già in archivio.',
             guida='controllo-codici-fiscali'),
        dict(titolo='Aggiornamenti già impostati',
             testo='Il programma sa già dove trovare le versioni nuove: alla clinica non c\'è niente da configurare. '
                   'Quando ne esce una, compare la notifica «Aggiornamento disponibile».',
             guida='aggiornare'),
    ]),
    ('1.6', [
        dict(titolo='Videoguide',
             testo='Ogni guida di Aiuto → Come fare… ha il suo video: «Guarda il video» mostra passo per passo dove '
                   'cliccare, con i fumetti della guida sullo schermo. Comincia da «Come è fatto il programma».',
             guida='come-e-fatto'),
        dict(titolo='Aggiornamenti dal programma',
             testo='Quando esce una versione nuova compare la notifica «Aggiornamento disponibile». Da Configura → '
                   'Aggiornamenti, «Aggiorna adesso»: il programma fa una copia di sicurezza dei dati, si aggiorna e si '
                   'riapre da solo in circa un minuto. Niente da scaricare né da disinstallare.',
             guida='aggiornare'),
        dict(titolo='Le novità, con i loro video',
             testo='Dopo ogni aggiornamento si apre questa pagina: cosa c\'è di nuovo e il video che lo spiega. Si '
                   'ritrova quando si vuole in Aiuto → Novità.',
             guida=None),
    ]),
    ('1.5', [
        dict(titolo='Email automatiche alla prenotazione',
             testo='Prenotando un esame endoscopico del Dr. Galasso parte da sola l\'email di preparazione, con le '
                   'informative allegate. Ogni email si manda anche a comando dalla pagina dell\'appuntamento.',
             guida='email-automatiche'),
        dict(titolo='Un\'email diversa per ogni medico',
             testo='Ogni medico può avere le sue email, con testi e informative sue: per le sue prestazioni parte la sua '
                   'al posto di quella per tutti i medici.',
             guida='email-per-medico'),
        dict(titolo='Promemoria del giorno prima',
             testo='All\'ora scelta parte il promemoria a chi ha appuntamento il giorno dopo: su WhatsApp o per email. La '
                   'pagina Conferme dice cosa è partito e chi resta da chiamare.',
             guida='promemoria'),
        dict(titolo='L\'email della clinica',
             testo='Le email ai pazienti partono dall\'account Gmail della clinica, collegato una volta con la '
                   '«password per le app».',
             guida='email-casella'),
        dict(titolo='Nascita, codice fiscale e indirizzo',
             testo='Nel modulo di prenotazione: scritto il codice fiscale, la data di nascita si riempie da sola.',
             guida='prenotare'),
        dict(titolo='La sala operatoria nel mese',
             testo='Il mese mostra gli interventi e i chirurghi di ogni giorno, e chi opera di solito quel giorno ed è '
                   'ancora libero.',
             guida='mese'),
        dict(titolo='Logo e caratteri nuovi',
             testo='Il logo Clinica Posillipo · Longevity Institute e i caratteri del sito della clinica.',
             guida=None),
        dict(titolo='Aggiornare senza disinstallare',
             testo='Il Setup nuovo si avvia sopra il vecchio: dice quale versione c\'è e quale arriva, e i dati restano.',
             guida='aggiornare'),
    ]),
]


def numeri(versione):
    """'1.6.1 animata' -> [1, 6, 1]: dopo lo spazio c'e' la variante, non un
    numero. Un pezzo che non e' un numero vale 0, come nel Setup."""
    testo = (versione or '').strip().split(' ')[0]
    uscita = []
    for pezzo in testo.split('.'):
        try:
            uscita.append(int(pezzo.strip()))
        except ValueError:
            uscita.append(0)
    return uscita


def confronta(a, b):
    """-1, 0 o 1, numero per numero, come ConfrontaVersioni di installer.iss
    ("1.6" e "1.6.0" sono uguali, "1.10" viene dopo "1.9")."""
    x, y = numeri(a), numeri(b)
    n = max(len(x), len(y))
    x, y = x + [0] * (n - len(x)), y + [0] * (n - len(y))
    return (x > y) - (x < y)


def dopo(precedente, attuale):
    """Le versioni con le loro voci arrivate dopo 'precedente' fino ad
    'attuale' compresa, dalla piu' nuova. Senza 'precedente' (non si sa da
    dove si arriva) solo quella attuale."""
    return [(v, voci) for v, voci in NOVITA
            if confronta(v, attuale) <= 0 and (confronta(v, precedente) > 0 if precedente else confronta(v, attuale) == 0)]


def per_manifesto():
    """Tutte le novita', per il file delle versioni: chi aggiorna saltando
    qualche versione vede anche quelle di mezzo."""
    return [{'versione': v, 'voci': [{'titolo': x['titolo'], 'testo': x['testo']} for x in voci]} for v, voci in NOVITA]
