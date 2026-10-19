# -*- coding: utf-8 -*-
"""Un database delle prestazioni INVENTATO, com'e' fatto quello vero del gruppo
(un foglio con Branca, Prestazione, Sinonimi, una colonna per struttura con le
X e le Note, piu' altri fogli che il programma deve saltare), per la prova
(strumenti/demo.py) e per le prove automatiche (prove_19.py).

Le strutture sono inventate, tranne Clinica Posillipo, la struttura di questo
gestionale nei dati di prova (cosi' si vede il segno «qui»). Recapiti finti:
telefoni 081 000 00xx, email @example.it.

    from strumenti.catalogo_prova import libro, STRUTTURE, VOCI
    dati = libro()                       # i byte del file .xlsx
"""
import io

# sigla usata nelle note -> (nome della colonna, recapiti del foglio Strutture o None)
STRUTTURE = [
    ('CP', 'Clinica Posillipo', {'indirizzo': 'Via Posillipo 1', 'citta': 'Napoli', 'telefono': '081 000 0000',
                                 'orari': 'dal lunedì al venerdì 8-19'}),
    ('CN', 'Centro Nord', {'indirizzo': 'Via Esempio 10', 'citta': 'Caserta', 'telefono': '0823 000 011',
                           'telefono2': '333 000 0011', 'email': 'prenotazioni@centronord.example.it',
                           'sito': 'https://www.example.it/centro-nord/prenota',
                           'orari': 'dal lunedì al sabato 7.30-19.30',
                           'prenotazione': 'Per telefono o online; per gli esami con contrasto serve la creatinina.'}),
    ('CS', 'Centro Sud', {'indirizzo': 'Corso Prova 25', 'citta': 'Salerno', 'telefono': '089 000 022',
                          'orari': 'dal lunedì al venerdì 8-18'}),
    ('PM', 'Poliambulatorio Mare', {'indirizzo': 'Viale Fittizio 3', 'citta': 'Pozzuoli', 'telefono': '081 000 0033',
                                    'email': 'info@poliambulatoriomare.example.it',
                                    'prenotazione': 'Solo per telefono, al mattino.'}),
    ('CC', 'Clinica Collina', {'indirizzo': 'Piazza Campione 7', 'citta': 'Avellino', 'telefono': '0825 000 044'}),
    ('DL', 'Diagnostica Lago', None),      # recapiti da scrivere nel programma
]

DC = 'dedotta dal listino generale, da confermare'
# (branca, prestazione, sinonimi, dove si fa: sigle, note)
VOCI = [
    ('DIAGNOSTICA PER IMMAGINI', 'RM ginocchio', 'risonanza ginocchio, risonanza magnetica ginocchio', 'CN DL', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'RM ginocchio con mezzo di contrasto', 'risonanza ginocchio con contrasto', 'CN', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'RM encefalo', 'risonanza cervello, risonanza testa', 'CN CS DL', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'RM encefalo con mezzo di contrasto', 'risonanza cervello con contrasto', 'CN DL', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'RM rachide lombo-sacrale', 'risonanza colonna, risonanza schiena', 'CN CS DL', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'RM spalla', 'risonanza spalla', 'DL', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'TC torace', 'tac torace, tac polmoni', 'CN CS', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'TC torace con mezzo di contrasto', 'tac torace con contrasto', 'CN', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'TC cranio', 'tac testa, tac cervello', 'CN CS', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Radiografia torace', 'lastra torace, rx torace', 'CN CS PM CC', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Radiografia ginocchio', 'lastra ginocchio, rx ginocchio', 'CN CS PM', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Radiografia mano', 'lastra mano, rx mano', 'CS PM', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Ecografia addome completo', 'eco addome, ecografia pancia', 'CP CN CS PM CC', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Ecografia tiroide', 'eco tiroide, ecografia collo', 'CP CS PM',
     'PM: nel suo listino «Ecografia del collo»'),
    ('DIAGNOSTICA PER IMMAGINI', 'Ecografia mammaria', 'eco seno, ecografia seno', 'CN PM CC', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Ecografia renale', 'eco reni', 'CS CC', 'CC: ' + DC),
    ('DIAGNOSTICA PER IMMAGINI', 'Mammografia', 'mammografia bilaterale', 'CN CC', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Densitometria ossea (MOC)', 'moc, densitometria', 'CS CC', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Ecocolordoppler tronchi sovraaortici (TSA)', 'ecodoppler carotidi, doppler tsa',
     'CP CN CS', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Ecocolordoppler arti inferiori', 'doppler gambe, ecodoppler vene', 'CP CS CC', ''),
    ('DIAGNOSTICA PER IMMAGINI', 'Ecocardiogramma', 'ecocardio, eco cuore', 'CP CN CS', ''),
    ('CARDIOLOGIA', 'Visita cardiologica', 'cardiologo', 'CP CN CS PM CC', ''),
    ('CARDIOLOGIA', 'Elettrocardiogramma (ECG)', 'ecg, elettrocardiogramma', 'CP CN CS PM CC', ''),
    ('CARDIOLOGIA', 'Holter ECG', 'holter cardiaco, holter 24 ore', 'CP CN CS', ''),
    ('CARDIOLOGIA', 'Holter pressorio', 'holter pressione', 'CP CN', ''),
    ('CARDIOLOGIA', 'Test da sforzo', 'prova da sforzo, ecg da sforzo', 'CN', 'CN: da verificare'),
    ('GASTROENTEROLOGIA ED ENDOSCOPIA DIGESTIVA', 'Gastroscopia (EGDS)', 'egds, esofagogastroduodenoscopia',
     'CP CC', ''),
    ('GASTROENTEROLOGIA ED ENDOSCOPIA DIGESTIVA', 'Colonscopia', 'colonscopia totale', 'CP CC', ''),
    ('GASTROENTEROLOGIA ED ENDOSCOPIA DIGESTIVA', 'Visita gastroenterologica', 'gastroenterologo', 'CP CS CC', ''),
    ('OCULISTICA', 'Visita oculistica', 'oculista, controllo della vista', 'CN CS PM', ''),
    ('OCULISTICA', "Fondo dell'occhio", 'fundus oculi', 'CN PM', ''),
    ('OCULISTICA', 'Tomografia ottica a coerenza (OCT)', 'oct', 'CN', ''),
    ('DERMATOLOGIA', 'Visita dermatologica', 'dermatologo', 'CP CS PM', ''),
    ('DERMATOLOGIA', 'Mappatura dei nei in epiluminescenza', 'controllo nei, mappatura nei, nevi', 'CP PM',
     'PM: ' + DC),
    ('ORTOPEDIA E TRAUMATOLOGIA', 'Visita ortopedica', 'ortopedico', 'CN CS CC', ''),
    ('ORTOPEDIA E TRAUMATOLOGIA', 'Infiltrazione articolare', 'infiltrazione ginocchio, infiltrazione spalla',
     'CN CC', ''),
    ('OSTETRICIA E GINECOLOGIA', 'Visita ginecologica', 'ginecologo', 'CP CS PM', ''),
    ('OSTETRICIA E GINECOLOGIA', 'Pap test', 'pap-test, citologico', 'CP PM', ''),
    ('OSTETRICIA E GINECOLOGIA', 'Ecografia ginecologica', 'ecografia transvaginale, eco pelvica', 'CP CS PM', ''),
    ('UROLOGIA', 'Visita urologica', 'urologo', 'CS CC', ''),
    ('UROLOGIA', 'Uroflussimetria', '', 'CC', ''),
    ('PNEUMOLOGIA', 'Spirometria', 'prova del respiro, esame del respiro', 'CS PM', ''),
    ('PNEUMOLOGIA', 'Visita pneumologica', 'pneumologo', 'CS', ''),
    ('NEUROLOGIA', 'Visita neurologica', 'neurologo', 'CN CS', ''),
    ('NEUROLOGIA', 'Elettromiografia (EMG)', 'emg, elettromiografia arti', 'CN', ''),
    ('NEUROLOGIA', 'Elettroencefalogramma (EEG)', 'eeg', 'CN', ''),
    ('LABORATORIO ANALISI', 'Analisi di laboratorio', 'prelievo, esami del sangue, analisi del sangue, esame urine',
     'CP CN CS PM', ''),
    ('OTORINOLARINGOIATRIA', 'Visita otorinolaringoiatrica', 'otorino, visita orl', 'CS PM', ''),
    ('OTORINOLARINGOIATRIA', 'Esame audiometrico', 'audiometria, esame dell\'udito', 'PM', ''),
    ('ENDOCRINOLOGIA', 'Visita endocrinologica', 'endocrinologo, tiroide', 'CP CS', ''),
    ('DIETOLOGIA E NUTRIZIONE', 'Visita nutrizionistica', 'nutrizionista, dieta', 'CP PM', ''),
    ('MEDICINA FISICA E RIABILITAZIONE', 'Seduta di fisioterapia', 'fisioterapia, riabilitazione', 'CS CC', ''),
    ('MEDICINA FISICA E RIABILITAZIONE', 'Tecarterapia', 'tecar', 'CC', ''),
    ('ODONTOIATRIA', 'Visita odontoiatrica', 'dentista', 'PM', ''),
    ('ODONTOIATRIA', 'Igiene dentale', 'pulizia dei denti, ablazione del tartaro', 'PM', ''),
    ('PSICOLOGIA E PSICOTERAPIA', 'Consulenza psicologica', 'psicologo', '', ''),     # in nessuna struttura
]


def libro(con_recapiti=True, voci=None, strutture=None, segno='X', titolo=True, altri_fogli=True):
    """I byte di un file .xlsx com'e' fatto il database vero. 'voci' e
    'strutture' (le liste qui sopra, o versioni cambiate) per le prove; 'segno'
    e' quello che si scrive nelle celle dove la prestazione si fa."""
    import openpyxl
    voci = VOCI if voci is None else voci
    strutture = STRUTTURE if strutture is None else strutture
    wb = openpyxl.Workbook()
    ws = wb.active
    if altri_fogli:
        # come nel file vero: un riepilogo prima del foglio intero (il programma lo salta)
        ws.title = 'RIEPILOGO'
        ws.append(['Riepilogo del database delle prestazioni (dati di prova)'])
        ws.append(['Struttura', 'Prestazioni'])
        for sigla, nome, _ in strutture:
            ws.append([nome, sum(1 for v in voci if sigla in v[3].split())])
        ws = wb.create_sheet('DATABASE PRESTAZIONI')
    else:
        ws.title = 'DATABASE PRESTAZIONI'
    if titolo:
        ws.append(['DATABASE PRESTAZIONI DEL GRUPPO — dati di prova'])
        ws.append([])
    ws.append(['Branca', 'Prestazione', 'Sinonimi'] + [nome for _, nome, _ in strutture] + ['Note'])
    for branca, nome, sinonimi, dove, nota in voci:
        sigle = dove.split()
        ws.append([branca, nome, sinonimi or None] + [segno if sigla in sigle else None for sigla, _, _ in strutture]
                  + [nota or None])
    if altri_fogli:
        # un foglio per struttura, senza le X: il programma usa quello intero
        sigla, nome, _ = strutture[1] if len(strutture) > 1 else strutture[0]
        ws2 = wb.create_sheet(nome[:31])
        ws2.append(['Branca', 'Prestazione', 'Sinonimi'])
        for branca, n, sinonimi, dove, _ in voci:
            if sigla in dove.split():
                ws2.append([branca, n, sinonimi])
        ws3 = wb.create_sheet('REGOLE')
        ws3.append(['Regole del database (dati di prova)'])
    if con_recapiti:
        ws4 = wb.create_sheet('Strutture')
        campi = ['indirizzo', 'citta', 'telefono', 'telefono2', 'email', 'sito', 'orari', 'prenotazione']
        ws4.append(['Struttura', 'Indirizzo', 'Città', 'Telefono', 'Altro telefono', 'Email', 'Prenotazione online',
                    'Orari', 'Come si prenota'])
        for _, nome, recapiti in strutture:
            if recapiti:
                ws4.append([nome] + [recapiti.get(c) for c in campi])
    uscita = io.BytesIO()
    wb.save(uscita)
    return uscita.getvalue()
