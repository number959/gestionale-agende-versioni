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
             guida='email-gmail'),
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
