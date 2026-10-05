# -*- coding: utf-8 -*-
"""Dati finti per far vedere il gestionale funzionante.

I pazienti sono inventati. Serve solo a capire se la logica dei turni
e della griglia regge il modo in cui si lavora davvero.
"""
from datetime import date, time, datetime, timedelta
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Prestazione,
                     Paziente, Turno, Appuntamento)


def popola(url='sqlite:///demo.db'):
    Sessione = crea_sessione(url)
    s = Sessione()

    cp = Struttura(nome='Clinica Posillipo', societa='ME.MI. S.r.l.',
                   indirizzo='Via Posillipo 1, Napoli', telefono='081 000 0000')
    vdf = Struttura(nome='Villa dei Fiori')
    # il logo si legge dal database come nelle installazioni vere
    import os
    import marchio
    from modelli import cartella_risorse
    with open(os.path.join(cartella_risorse(), 'static', 'logo-posillipo.png'), 'rb') as f:
        cp.logo = marchio.normalizza_logo(f.read())
    cp.logo_aggiornato = datetime.now()
    s.add_all([cp, vdf])
    s.flush()

    risorse = []
    for i, nome in enumerate(['Ambulatorio 1', 'Ambulatorio 2', 'Ambulatorio 3',
                              'Ambulatorio 4', 'Ambulatorio 5'], start=1):
        risorse.append(Risorsa(nome=nome, tipo='AMBULATORIO',
                               struttura=cp, ordine=i))
    risorse.append(Risorsa(nome='Sala endoscopia', tipo='ENDOSCOPIA',
                           struttura=cp, ordine=6))
    risorse.append(Risorsa(nome='Sala A', tipo='SALA_OPERATORIA',
                           struttura=vdf, ordine=1))
    risorse.append(Risorsa(nome='Sala B', tipo='SALA_OPERATORIA',
                           struttura=vdf, ordine=2))
    s.add_all(risorse)

    medici = {
        'lippiello': Operatore(cognome='Lippiello', specialita='ginecologia', colore='#0087B4'),
        'galasso': Operatore(cognome='Galasso', specialita='gastroenterologia', colore='#5B7F3E'),
        'esposito': Operatore(cognome='Esposito', specialita='cardiologia', colore='#A8582B'),
        'russo': Operatore(cognome='Russo', specialita='diabetologia', colore='#6B4E9B'),
        'marino': Operatore(cognome='Marino', specialita='dermatologia', colore='#B3261E'),
    }
    s.add_all(medici.values())

    prest = {
        'gin': Prestazione(nome='Visita ginecologica', durata_min=30),
        'ctrl': Prestazione(nome='Controllo', durata_min=20),
        'eco': Prestazione(nome='Ecografia', durata_min=20),
        'egds': Prestazione(nome='EGDS', durata_min=30,
                            campi_extra='Sedazione?, Anestesista, Preparazione consegnata?',
                            preparazione='Digiuno da almeno 8 ore. Portare gli esami precedenti.'),
        'colon': Prestazione(nome='Colonscopia', durata_min=45,
                             campi_extra='Sedazione?, Anestesista, Preparazione consegnata?',
                             preparazione='Seguire la preparazione intestinale consegnata. '
                                          'Dieta senza scorie nei tre giorni precedenti.'),
        'card': Prestazione(nome='Visita cardiologica', durata_min=30),
        'diab': Prestazione(nome='Visita diabetologica', durata_min=30),
        'derm': Prestazione(nome='Visita dermatologica', durata_min=20),
    }
    s.add_all(prest.values())
    s.flush()

    amb = {r.nome: r for r in risorse}
    da = date(2026, 9, 1)

    # Lippiello: due o tre volte a settimana su due ambulatori (come da WhatsApp)
    turni = []
    for g in (1, 3):            # martedi e giovedi
        for nome in ('Ambulatorio 1', 'Ambulatorio 2'):
            turni.append(Turno(operatore=medici['lippiello'], risorsa=amb[nome],
                               giorno_settimana=g, ora_inizio=time(8, 0),
                               ora_fine=time(14, 0), valido_da=da))
    # Galasso: una seduta a settimana, sala endoscopica
    turni.append(Turno(operatore=medici['galasso'], risorsa=amb['Sala endoscopia'],
                       giorno_settimana=1, ora_inizio=time(8, 0),
                       ora_fine=time(13, 30), valido_da=da))
    turni.append(Turno(operatore=medici['esposito'], risorsa=amb['Ambulatorio 3'],
                       giorno_settimana=1, ora_inizio=time(15, 0),
                       ora_fine=time(19, 0), valido_da=da))
    turni.append(Turno(operatore=medici['russo'], risorsa=amb['Ambulatorio 4'],
                       giorno_settimana=1, ora_inizio=time(9, 0),
                       ora_fine=time(13, 0), valido_da=da))
    turni.append(Turno(operatore=medici['marino'], risorsa=amb['Ambulatorio 5'],
                       giorno_settimana=1, ora_inizio=time(16, 0),
                       ora_fine=time(19, 30), valido_da=da))
    s.add_all(turni)

    cognomi = ['Esposito', 'Russo', 'Coppola', 'Barbato', 'Sorrentino', 'De Luca',
               'Improta', 'Palumbo', 'Cutolo', 'Vitiello', 'Aiello', 'Ferrara',
               'Caputo', 'Migliaccio', 'Della Corte', 'Santoro', 'Iovine']
    pazienti = [Paziente(cognome=c, telefono='333%07d' % (1234500 + i))
                for i, c in enumerate(cognomi)]
    s.add_all(pazienti)
    s.flush()

    # giornata dimostrativa: martedi 15 settembre 2026
    g = date(2026, 9, 15)
    p = iter(pazienti)

    def appunta(risorsa, medico, prestazione, ora, minuti=None):
        inizio = datetime.combine(g, ora)
        durata = minuti or prestazione.durata_min
        s.add(Appuntamento(risorsa=risorsa, operatore=medico, prestazione=prestazione,
                           paziente=next(p), inizio=inizio,
                           fine=inizio + timedelta(minutes=durata)))

    for h, m in [(8, 0), (8, 30), (9, 0), (10, 0), (11, 0), (12, 30)]:
        appunta(amb['Ambulatorio 1'], medici['lippiello'], prest['gin'], time(h, m))
    for h, m in [(8, 30), (9, 30), (11, 30)]:
        appunta(amb['Ambulatorio 2'], medici['lippiello'], prest['eco'], time(h, m))
    appunta(amb['Sala endoscopia'], medici['galasso'], prest['colon'], time(8, 0))
    appunta(amb['Sala endoscopia'], medici['galasso'], prest['egds'], time(9, 0))
    appunta(amb['Sala endoscopia'], medici['galasso'], prest['egds'], time(10, 0))
    appunta(amb['Ambulatorio 3'], medici['esposito'], prest['card'], time(15, 30))
    appunta(amb['Ambulatorio 3'], medici['esposito'], prest['card'], time(16, 30))
    appunta(amb['Ambulatorio 4'], medici['russo'], prest['diab'], time(9, 30))
    appunta(amb['Ambulatorio 5'], medici['marino'], prest['derm'], time(17, 0))

    s.commit()
    s.close()
    return Sessione


if __name__ == '__main__':
    popola()
    print('demo.db creato')
