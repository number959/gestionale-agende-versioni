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
