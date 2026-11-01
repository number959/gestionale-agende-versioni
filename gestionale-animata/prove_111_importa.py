# -*- coding: utf-8 -*-
"""Prove della 1.11: i difetti dell'importazione da Excel e CSV trovati dalla
revisione del codice di novembre 2026, uno per uno. Ognuno era stato
riprodotto da un controllo indipendente prima di correggerlo; qui ogni prova
lo rifa' e controlla la correzione (le prove sono state verificate anche
rimettendo il difetto: devono fallire). Il numero fra parentesi quadre e'
quello della segnalazione: PROVE_SOLO='[5]' rifa' solo quella.

- [1] orari scritti come numeri in Excel (9,30 in una cella normale e' 9.3);
- [2] data di nascita con l'anno a due cifre ("12/03/65" diventava il 2065);
- [3] stanza nuova con un nome oltre 60 caratteri: dalla seconda importazione
      un errore del database e niente importato;
- [4] la stessa stanza scritta con maiuscole diverse: due stanze, e due
      appuntamenti alla stessa ora;
- [5] una riga disdetta occupava la stanza nel file; reimportando, il
      disdetto si duplicava;
- [8] oltre il numero massimo di righe per foglio il file si troncava senza
      dirlo;
- [9] "Dott. Galasso" nella colonna del medico diventava un medico nuovo;
- [10] la durata scritta come orario (0:45) ignorata, "INF" fermava l'anteprima;
- [11] reimportando, le righe in conflitto o incomplete diventavano ogni volta
      un da confermare nuovo; quelle entrate poi in agenda restavano aperte;
- [12] nella rubrica, i dati della seconda riga della stessa persona si perdevano.

Dove si puo' il risultato si confronta con un calcolo fatto a parte (un
oracolo) e non con quello che il programma stesso ha prodotto."""
import io
import logging
import os
import re
import shutil
import sys
import tempfile
import traceback
from datetime import date, datetime, time, timedelta
from html import unescape
from urllib.parse import urlencode

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove_111_importa_')
os.environ['LOCALAPPDATA'] = os.path.join(PROVVISORIA, 'localappdata')
# i file caricati per l'anteprima finiscono qui dentro, e se ne vanno alla fine
tempfile.tempdir = PROVVISORIA
sys.path.insert(0, CARTELLA)
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select, func  # noqa: E402

import app as A  # noqa: E402
import codice_fiscale as CF  # noqa: E402
import importa  # noqa: E402
import servizi  # noqa: E402
import viste  # noqa: E402
from modelli import crea_sessione, Risorsa, Operatore, Appuntamento, Paziente, Appunto  # noqa: E402

A.app.config['TESTING'] = True
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
OGGI = date.today()


def area(nome):
    _area[0] = nome


def prova(nome, f):
    if SOLO and not any(x in nome for x in SOLO):
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


# ================================================================ il mondo
def mondo(medici=(('Galasso', 'Luigi'), ('Lippiello', 'Anna'))):
    """Un database nuovo (le sei stanze e le prestazioni del primo avvio) con
    i medici dati, collegato al programma. (S, client)."""
    _n[0] += 1
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'db_%d.db' % _n[0]))
    s = S()
    servizi.prepara_primo_avvio(s)
    for cognome, nome in medici:
        s.add(Operatore(cognome=cognome, nome=nome))
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, A.app.test_client()


def giorno(settimane=2):
    """Un martedi' fra qualche settimana, lontano dai festivi."""
    g = OGGI + timedelta(days=7 * settimane)
    g += timedelta(days=(1 - g.weekday()) % 7)
    while any(servizi.calendario.festivo(g + timedelta(days=k)) for k in range(-3, 4)):
        g += timedelta(days=7)
    return g


G = giorno()
D0 = datetime.combine(G, time(0, 0))
PAZIENTI = ['FINTINI MARIO', 'ESEMPIETTI ANNA', 'PROVOLO GINA', 'TESTABIANCA LUCA', 'FITTIZI ROSA', 'ESEMPIO CARLO',
            'FINTINI LUCIA', 'ESEMPIETTI PAOLO']


def xlsx(righe, titolo='Agenda'):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = titolo
    for r in righe:
        ws.append(list(r))
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def csv_(righe):
    return ('\r\n'.join(';'.join('' if v is None else str(v) for v in r) for r in righe) + '\r\n').encode('cp1252')


def testo(r):
    """Il testo della pagina, senza i tag."""
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', r.get_data(as_text=True))).split())


def avvisi(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return ' '.join(x[1] for x in m)


def carica(C, dati, nome, tipo='', **campi):
    """Carica il file come dalla pagina: (indirizzo dell'anteprima, testo dell'anteprima)."""
    r = C.post('/importa', data={'file': (io.BytesIO(dati), nome), 'tipo': tipo},
               content_type='multipart/form-data')
    assert r.status_code == 302 and '/importa/' in r.headers['Location'], 'caricamento: HTTP %d %s' % (
        r.status_code, avvisi(C))
    indirizzo = r.headers['Location']
    if campi:
        indirizzo += ('&' if '?' in indirizzo else '?') + urlencode(campi)
    anteprima = C.get(indirizzo)
    assert anteprima.status_code == 200, 'anteprima HTTP %d %s' % (anteprima.status_code, avvisi(C))
    return indirizzo, testo(anteprima)


def conflitti(t):
    """Quante righe in conflitto dice l'anteprima ("1 in conflitto")."""
    m = re.search(r'\b(\d+) in conflitto\b', t)
    return int(m.group(1)) if m else 0


def importa_ora(C, indirizzo, **campi):
    """Conferma l'importazione: il testo della pagina finale."""
    dati = {'azione': 'importa', 'struttura': '1'}
    dati.update(campi)
    r = C.post(indirizzo, data=dati)
    t = testo(r)
    assert r.status_code == 200 and 'Importazione completata' in t, 'importazione: HTTP %d %s' % (
        r.status_code, avvisi(C))
    return t


def piano_di(S, dati, nome, **campi):
    """L'anteprima senza le pagine: (sessione, piano)."""
    s = S()
    a = importa.analizza(importa.leggi_file(dati, nome)[0])
    f = {'struttura': '1'}
    f.update(campi)
    return s, importa.prepara(s, a, importa.opzioni_da(f, a))


def quanti(S, modello, *condizioni):
    s = S()
    n = s.scalar(select(func.count(modello.id)).where(*condizioni))
    s.close()
    return n


def agenda(S):
    """[(ora, stanza, paziente, medico, stato)] in ordine di ora e di stanza."""
    s = S()
    uscita = [(a.inizio.strftime('%H:%M'), a.risorsa.nome, a.paziente.cognome if a.paziente else '',
               a.operatore.cognome, a.stato)
              for a in s.scalars(select(Appuntamento).order_by(Appuntamento.inizio, Appuntamento.risorsa_id,
                                                               Appuntamento.id))]
    s.close()
    return uscita


# =====================================================================
area('importazione: valori letti dal file')


def oracolo_ora(v):
    """9.3 -> 9:30: le due cifre dopo la virgola sono i minuti."""
    centesimi = int(round(v * 100))
    return time(centesimi // 100, centesimi % 100)


def i01_orari_numeri():
    casi = [9, 9.0, 9.3, 10.3, 9.45, 9.2, 9.05, 12.1, 23.59, 17.5]
    sbagliati = [(v, importa.come_ora(v), oracolo_ora(v)) for v in casi if importa.come_ora(v) != oracolo_ora(v)]
    assert not sbagliati, 'orari letti male (valore, letto, atteso): %s' % sbagliati
    # le stesse cose come testo, cosi' come le salva un CSV da una cella numerica
    for t, atteso in (('9,3', time(9, 30)), ('9.3', time(9, 30)), ('10,5', time(10, 50)), ('9,30', time(9, 30)),
                      ('9.30', time(9, 30)), ('9', time(9, 0))):
        assert importa.come_ora(t) == atteso, '%r -> %s' % (t, importa.come_ora(t))
    # non sono orari: troppe cifre, minuti oltre 59, oltre la mezzanotte
    for v in (9.333, 9.75, 24.0, 25.3, -1.0, True, '9:5', '25:00'):
        assert importa.come_ora(v) is None, '%r letto come %s' % (v, importa.come_ora(v))
    # come prima: frazione di giorno di Excel
    assert importa.come_ora(0.375) == time(9, 0)
    # le agende: a righe di mezz'ora e a righe di venti minuti, l'ora come numero
    for orari, passo in (([9, 9.3, 10, 10.3, 11, 11.3], 30), ([9, 9.2, 9.4, 10, 10.2, 10.4], 20)):
        S, C = mondo()
        righe = [['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA']]
        for i, o in enumerate(orari):
            righe.append([D0, o, PAZIENTI[i], '33312345%02d' % i, 'GALASSO', 'Ambulatorio 1'])
        indirizzo, t = carica(C, xlsx(righe), 'agenda.xlsx')
        assert "manca l'ora" not in t, 'anteprima: "manca l\'ora" per gli orari %s' % orari
        importa_ora(C, indirizzo)
        s = S()
        apps = s.scalars(select(Appuntamento).order_by(Appuntamento.inizio)).all()
        letti = [(a.inizio.time(), a.durata_min) for a in apps]
        s.close()
        attesi = [(oracolo_ora(o), passo) for o in orari]
        assert letti == attesi, 'orari %s: in agenda %s invece di %s' % (orari, letti, attesi)
    return 'mezz\'ora e venti minuti, %d valori' % len(casi)


def oracolo_nascita(testo_data):
    """Anno a due cifre: la data piu' recente che non sia nel futuro."""
    g, m, aa = (int(x) for x in testo_data.split('/'))
    if aa >= 100:
        return date(aa, m, g)
    for secolo in (2000, 1900):
        d = date(secolo + aa, m, g)
        if d <= OGGI:
            return d


def i02_nascita_due_cifre():
    casi = [('Fintini', 'Mario', '12/03/65'), ('Esempietti', 'Anna', '01/07/48'), ('Provolo', 'Gina', '15/04/24'),
            ('Testabianca', 'Luca', '20/10/85'), ('Fittizi', 'Rosa', '03/02/1965'),
            ('Esempio', 'Carlo', '31/12/%02d' % (OGGI.year % 100)), ('Fintini', 'Lucia', '01/01/00')]
    righe = [['Cognome', 'Nome', 'Telefono', 'Data di nascita']]
    righe += [[c, n, '33311122%02d' % i, d] for i, (c, n, d) in enumerate(casi)]
    dati = csv_(righe)
    S, C = mondo()
    s, piano = piano_di(S, dati, 'rubrica.csv', tipo='pazienti')
    s.close()
    # l'avviso solo dove la data potrebbe essere di cento anni prima
    avvisati = sorted(r['paziente']['cognome'] + ' ' + r['paziente']['nome'] for r in piano['righe']
                      if any('anno a due cifre' in x for x in r['avvisi']))
    attesi = sorted('%s %s' % (c, n) for c, n, d in casi
                    if len(d.split('/')[2]) == 2 and oracolo_nascita(d).year >= 2000)
    assert avvisati == attesi, 'avvisi sull\'anno a due cifre: %s invece di %s' % (avvisati, attesi)
    assert not any('nel futuro' in x for r in piano['righe'] for x in r['avvisi']), 'date tolte come future'
    indirizzo, t = carica(C, dati, 'rubrica.csv')
    assert 'anno a due cifre' in t, 'l\'anteprima non mostra l\'avviso'
    importa_ora(C, indirizzo)
    s = S()
    lette = {(p.cognome, p.nome): p.data_nascita for p in s.scalars(select(Paziente))}
    s.close()
    sbagliate = {'%s %s' % k: (str(lette.get(k)), str(oracolo_nascita(d)))
                 for c, n, d in casi for k in [(c, n)] if lette.get(k) != oracolo_nascita(d)}
    assert not sbagliate, 'date di nascita (lette, attese): %s' % sbagliate
    # le date degli appuntamenti restano come prima: "24/9/27" e' il 2027
    assert importa.come_data('24/9/27') == date(2027, 9, 24)
    return '%d date' % len(casi)


def i10_durata():
    S, C = mondo()
    # A) .xlsx: la durata come orario (h:mm) e come durata di Excel ([h]:mm)
    righe = [['DATA', 'ORA', 'DURATA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA']]
    durate = [(9, time(0, 45), 45), (11, time(1, 30), 90), (14, timedelta(minutes=30), 30),
              (15, timedelta(hours=2), 120)]
    for i, (h, d, _) in enumerate(durate):
        righe.append([D0, time(h, 0), d, PAZIENTI[i], '33312346%02d' % i, 'Galasso', 'Ambulatorio 1'])
    s, piano = piano_di(S, xlsx(righe), 'agenda.xlsx')
    s.close()
    letti = [(r['inizio'].hour, int((r['fine'] - r['inizio']).total_seconds() // 60), r['durata_esplicita'],
              any('durata' in x for x in r['avvisi'])) for r in piano['righe']]
    attesi = [(h, m, True, False) for h, _, m in durate]
    assert letti == attesi, 'durate da Excel (ora, minuti, scritta, avviso): %s invece di %s' % (letti, attesi)
    # B) CSV: ore e minuti come testo; valori che non sono durate, senza fermare l'anteprima.
    # Una riga ogni due ore: la durata del file, quando quella scritta non vale, e' di 120 minuti
    casi = [('0:45', 45), ('1h30', 90), ('45', 45), ('INF', None), ('Infinity', None), ('1e999', None),
            ('nan', None), ('2', None), ('3000', None)]
    righe = [['Data', 'Ora', 'Durata', 'Paziente', 'Telefono', 'Medico', 'Stanza']] + [
        [G.strftime('%d/%m/%Y'), '%02d:00' % (6 + 2 * i), v, PAZIENTI[i % len(PAZIENTI)], '33312347%02d' % i,
         'Galasso', 'Ambulatorio 2'] for i, (v, _) in enumerate(casi)]
    indirizzo, t = carica(C, csv_(righe), 'agenda.csv')
    assert 'durata non valida' in t, 'nessun avviso sulle durate che non si leggono'
    s, piano = piano_di(S, csv_(righe), 'agenda.csv')
    s.close()
    assert len(piano['righe']) == len(casi), len(piano['righe'])
    for r, (v, minuti) in zip(piano['righe'], casi):
        durata = int((r['fine'] - r['inizio']).total_seconds() // 60)
        avvisata = any('durata non valida' in x for x in r['avvisi'])
        if minuti is None:
            # non si legge o e' fuori misura: si dice, e vale la durata del file
            assert avvisata and not r['durata_esplicita'] and durata == 120, (v, durata, r['avvisi'])
        else:
            assert durata == minuti and r['durata_esplicita'] and not avvisata, (v, durata, r['avvisi'])
    importa_ora(C, indirizzo)
    assert quanti(S, Appuntamento) == len(casi), 'appuntamenti: %d' % quanti(S, Appuntamento)
    return '%d durate da Excel, %d dal CSV' % (len(durate), len(casi))


prova('[1] orari scritti come numeri in Excel (9,30 = 9.3)', i01_orari_numeri)
prova('[2] data di nascita con l\'anno a due cifre', i02_nascita_due_cifre)
prova('[10] durata come orario o durata di Excel; INF e NaN senza errori', i10_durata)


# =====================================================================
area('importazione: stanze e medici')

LUNGA = 'Ambulatorio di chirurgia plastica ricostruttiva ed estetica - piano terra'


def i03_stanza_lunga():
    assert len(LUNGA) > 60
    salvato = ' '.join(LUNGA.split())[:60].strip()      # oracolo: come la salva la scheda della stanza
    S, C = mondo()
    for mese, nomi in ((0, PAZIENTI[:2]), (1, PAZIENTI[2:4])):
        g = G + timedelta(days=28 * mese)
        righe = [['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA']]
        for i, nm in enumerate(nomi):
            righe.append([datetime.combine(g, time()), time(9 + i, 0), nm, '33355500%d%d' % (mese, i), 'GALASSO', LUNGA])
        indirizzo, t = carica(C, xlsx(righe), 'mese%d.xlsx' % mese)
        if mese:
            assert 'Stanze nuove' not in t, 'il mese dopo la stanza risulta ancora da creare'
        importa_ora(C, indirizzo)
    s = S()
    stanze = [r.nome for r in s.scalars(select(Risorsa).where(Risorsa.nome.like('Ambulatorio di chir%')))]
    s.close()
    assert stanze == [salvato], 'stanze: %s' % stanze
    assert quanti(S, Appuntamento) == 4, 'appuntamenti: %d invece di 4' % quanti(S, Appuntamento)
    # lo stesso con il nome lungo scritto sopra un blocco di un'agenda a sale affiancate
    lunga = LUNGA.upper().replace('AMBULATORIO', 'SALA OPERATORIA')
    S, C = mondo()
    for mese, (a, b) in enumerate((PAZIENTI[:2], PAZIENTI[2:4])):
        g = G + timedelta(days=28 * mese)
        righe = [['DATA', lunga, None, None, 'AMBULATORIO 2', None, None],
                 ['DATA', 'ORA', 'PAZIENTE', 'MEDICO', 'ORA', 'PAZIENTE', 'MEDICO'],
                 [datetime.combine(g, time()), time(9), a, 'GALASSO', time(9), b, 'GALASSO']]
        importa_ora(C, carica(C, xlsx(righe), 'blocchi%d.xlsx' % mese)[0])
    s = S()
    stanze = [r.nome for r in s.scalars(select(Risorsa).where(Risorsa.nome.like('%hirurgia%')))]
    s.close()
    assert len(stanze) == 1 and len(stanze[0]) <= 60, 'stanze: %s' % stanze
    assert quanti(S, Appuntamento) == 4, 'appuntamenti a blocchi: %d invece di 4' % quanti(S, Appuntamento)


def i04_stanza_maiuscole():
    S, C = mondo()
    righe = [['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA'],
             [D0, time(9), PAZIENTI[0], '3331230001', 'GALASSO', 'Sala Rossa'],
             [D0, time(9), PAZIENTI[1], '3331230002', 'LIPPIELLO', 'sala rossa'],
             [D0, time(10), PAZIENTI[2], '3331230003', 'GALASSO', 'Sala Rossa'],
             [D0, time(11), PAZIENTI[3], '3331230004', 'LIPPIELLO', 'SALA  ROSSA'],
             [D0, time(12), PAZIENTI[4], '3331230005', 'LIPPIELLO', 'Sala-rossa']]
    indirizzo, t = carica(C, xlsx(righe), 'agenda.xlsx')
    m = re.search(r'Stanze nuove: (.*?) (Note|Righe|Il file|\d+ appuntament)', t)
    assert m and m.group(1).strip() == 'Sala Rossa', 'stanze nuove in anteprima: %s' % (m.group(1) if m else None)
    importa_ora(C, indirizzo)
    s = S()
    nuove = [r.nome for r in s.scalars(select(Risorsa).order_by(Risorsa.id))][len(servizi.STANZE_INIZIALI):]
    appunti = [(x.ora, x.paziente.cognome) for x in s.scalars(select(Appunto))]
    s.close()
    assert nuove == ['Sala Rossa'], 'stanze create: %s' % nuove
    # oracolo: una stanza sola, quindi alle 9 entra la prima riga e la seconda e' in conflitto
    assert [(o, p) for o, _, p, _, _ in agenda(S)] == [('09:00', 'Fintini'), ('10:00', 'Provolo'),
                                                       ('11:00', 'Testabianca'), ('12:00', 'Fittizi')], agenda(S)
    assert appunti == [(time(9, 0), 'Esempietti')], 'da confermare: %s' % appunti
    # al momento di scrivere: una stanza con lo stesso nome nata dopo l'anteprima si usa, senza errori
    for gia in ('Sala Verde', 'SALA VERDE'):
        S, C = mondo()
        righe = [['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA'],
                 [D0, time(9), PAZIENTI[0], '3331230001', 'GALASSO', 'Sala Verde']]
        s, piano = piano_di(S, xlsx(righe), 'agenda.xlsx')
        assert piano['nuove_stanze'] == ['Sala Verde'], piano['nuove_stanze']
        s.add(Risorsa(nome=gia, tipo='AMBULATORIO', struttura_id=1, ordine=50))
        s.flush()
        esito = importa.esegui(s, piano, 'agenda.xlsx')
        verdi = [r.nome for r in s.scalars(select(Risorsa).where(func.lower(Risorsa.nome) == 'sala verde'))]
        s.close()
        assert verdi == [gia] and esito['stanze'] == 0 and esito['appuntamenti'] == 1, (gia, verdi, esito)
        assert agenda(S)[0][1] == gia, agenda(S)


def i09_titoli_medico():
    S, C = mondo()
    celle = [('Dott. Galasso', 'Galasso'), ('GALASSO', 'Galasso'), ('DOTT.SSA LIPPIELLO', 'Lippiello'),
             ('Dr. Galasso', 'Galasso'), ('D.SSA LIPPIELLO', 'Lippiello'), ('Prof. Galasso', 'Galasso'),
             ('Dottor Galasso', 'Galasso'), ('DR GALASSO', 'Galasso'), ('Dott.ssa Lippiello Anna', 'Lippiello'),
             ('Dott.Galasso', 'Galasso')]
    righe = [['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA']]
    for i, (cella, _) in enumerate(celle):
        righe.append([D0, time(8 + i), PAZIENTI[i % len(PAZIENTI)], '33312348%02d' % i, cella, 'Ambulatorio 1'])
    indirizzo, t = carica(C, xlsx(righe), 'agenda.xlsx')
    assert 'Medici nuovi' not in t, 'anteprima: medici nuovi per dei titoli'
    importa_ora(C, indirizzo)
    assert quanti(S, Operatore) == 2, 'medici: %d invece di 2' % quanti(S, Operatore)
    trovati = [m for _, _, _, m, _ in agenda(S)]
    assert trovati == [atteso for _, atteso in celle], 'medici in agenda: %s' % trovati
    # appena installato, senza medici: uno solo, con il nome giusto
    S, C = mondo(medici=())
    righe = [['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA'],
             [D0, time(9), PAZIENTI[0], '3331230011', 'DR. GALASSO', 'Ambulatorio 1'],
             [D0, time(10), PAZIENTI[1], '3331230012', 'GALASSO', 'Ambulatorio 1'],
             [D0, time(11), PAZIENTI[2], '3331230013', 'D.SSA GALASSO', 'Ambulatorio 1'],
             [D0, time(12), PAZIENTI[3], '3331230014', 'DOTT.', 'Ambulatorio 1']]
    s, piano = piano_di(S, xlsx(righe), 'agenda.xlsx')
    s.close()
    assert [(m['cognome'], m['nome']) for m in piano['nuovi_medici']] == [('Galasso', '')], piano['nuovi_medici']
    solo_titolo = piano['righe'][-1]
    assert solo_titolo['esito'] == 'scartato' and 'manca il medico' in solo_titolo['motivo'], solo_titolo['motivo']
    importa_ora(C, carica(C, xlsx(righe), 'agenda.xlsx')[0])
    s = S()
    medici = [(o.cognome, o.nome) for o in s.scalars(select(Operatore))]
    s.close()
    assert medici == [('Galasso', '')], 'medici creati: %s' % medici
    assert len(agenda(S)) == 3, agenda(S)
    # "D.SSA" anche nel titolo del file, come "Dott.ssa"
    assert importa.nome_medico_nel_titolo('AGENDA D.SSA LIPPIELLO OTTOBRE') == 'LIPPIELLO'
    assert importa.nome_medico_nel_titolo('x | Medico: Dott.ssa Lippiello | Data: 25/09/2026') == 'Lippiello'
    return '%d modi di scrivere il medico' % len(celle)


prova('[3] stanza nuova con il nome oltre 60 caratteri: il mese dopo si ritrova', i03_stanza_lunga)
prova('[4] la stessa stanza con maiuscole diverse è una sola', i04_stanza_maiuscole)
prova('[9] "Dott. Galasso" nella colonna del medico e\' Galasso', i09_titoli_medico)


# =====================================================================
area('importazione: righe disdette e reimportazioni')

INTESTAZIONE = ['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO', 'STANZA', 'STATO']


def riga(h, m, chi, stato=None, stanza='Ambulatorio 1', medico='GALASSO'):
    return [D0, time(h, m), PAZIENTI[chi], '33312349%02d' % chi, medico, stanza, stato]


def oracolo_disdetti(righe_file):
    """In ogni stanza, alla stessa ora, entra la prima riga attiva; le righe
    disdette entrano sempre (non occupano la stanza). [(ora, cognome, stato)]"""
    uscita, occupate = [], set()
    for r in righe_file:
        disdetto = r[6] in ('DISDETTO', 'DISDICE')
        chiave = (r[5], r[1])
        if disdetto:
            uscita.append((r[1].strftime('%H:%M'), r[2].split()[0].capitalize(), 'DISDETTO'))
        elif chiave not in occupate:
            occupate.add(chiave)
            uscita.append((r[1].strftime('%H:%M'), r[2].split()[0].capitalize(), 'PRENOTATO'))
    return sorted(uscita)


def i05_riga_disdetta():
    casi = [
        ('disdetto prima', [riga(9, 0, 0, 'DISDETTO'), riga(9, 0, 1), riga(10, 0, 2)]),
        ('disdetto dopo', [riga(9, 0, 1), riga(9, 0, 0, 'DISDETTO')]),
        ('DISDICE nelle note', [riga(9, 0, 0, 'DISDICE'), riga(9, 0, 1), riga(10, 0, 2)]),
        ('due disdetti e uno vero', [riga(9, 0, 0, 'DISDETTO'), riga(9, 0, 3, 'DISDETTO'), riga(9, 0, 1)]),
    ]
    for nome, righe_file in casi:
        S, C = mondo()
        intestazione = INTESTAZIONE[:6] + (['NOTE'] if nome.startswith('DISDICE') else ['STATO'])
        dati = xlsx([intestazione] + righe_file)
        indirizzo, t = carica(C, dati, 'agenda.xlsx')
        assert conflitti(t) == 0, '%s: anteprima con %d conflitti' % (nome, conflitti(t))
        importa_ora(C, indirizzo)
        trovati = sorted((o, p, st) for o, _, p, _, st in agenda(S))
        atteso = oracolo_disdetti(righe_file)
        assert trovati == atteso, '%s: in agenda %s invece di %s' % (nome, trovati, atteso)
        assert quanti(S, Appunto) == 0, '%s: %d da confermare per un disdetto' % (nome, quanti(S, Appunto))
        # lo stesso file importato di nuovo non aggiunge niente, nemmeno il disdetto
        indirizzo, t = carica(C, dati, 'agenda.xlsx')
        importa_ora(C, indirizzo)
        assert sorted((o, p, st) for o, _, p, _, st in agenda(S)) == atteso, '%s, di nuovo: %s' % (nome, agenda(S))
        assert quanti(S, Appunto) == 0, '%s, di nuovo: da confermare' % nome
    # un disdetto non accorcia l'appuntamento prima: durata di 60 minuti, disdetto alle 9:30
    S, C = mondo()
    s, piano = piano_di(S, xlsx([INTESTAZIONE, riga(9, 0, 0), riga(9, 30, 1, 'DISDETTO')]), 'agenda.xlsx', durata='60')
    s.close()
    fine = piano['righe'][0]['fine']
    assert fine == datetime.combine(G, time(10, 0)), 'accorciato fino al disdetto: finisce alle %s' % fine.time()
    # un disdetto del file alla stessa ora di un appuntamento gia' in agenda: si importa, non e' un conflitto
    S, C = mondo()
    importa_ora(C, carica(C, xlsx([INTESTAZIONE, riga(9, 0, 1)]), 'a.xlsx')[0])
    indirizzo, t = carica(C, xlsx([INTESTAZIONE, riga(9, 0, 2, 'DISDETTO')]), 'b.xlsx')
    assert conflitti(t) == 0, 'il disdetto risulta in conflitto con l\'agenda'
    importa_ora(C, indirizzo)
    assert sorted((p, st) for _, _, p, _, st in agenda(S)) == [('Esempietti', 'PRENOTATO'), ('Provolo', 'DISDETTO')]
    assert quanti(S, Appunto) == 0, 'un disdetto e\' finito fra i da confermare'
    return '%d file' % len(casi)


def i11_reimportare_da_confermare():
    S, C = mondo()
    righe = [INTESTAZIONE[:6],
             [D0, time(9), PAZIENTI[0], '3331234501', 'Galasso', 'Ambulatorio 1'],
             [D0, time(9), PAZIENTI[1], '3331234502', 'Galasso', 'Ambulatorio 1'],      # in conflitto
             [D0, time(10), PAZIENTI[2], '3331234503', None, 'Ambulatorio 1'],          # senza medico
             [D0, time(11), PAZIENTI[3], '3331234504', 'Galasso', 'Ambulatorio 1']]
    dati = xlsx(righe)
    for giro in range(1, 4):
        indirizzo, t = carica(C, dati, 'agenda.xlsx' if giro < 3 else 'agenda (2).xlsx')
        if giro == 1:
            assert conflitti(t) == 1 and '1 in conflitto (vanno fra i da confermare)' in t, 'prima anteprima'
        else:
            # l'anteprima dice quello che succedera': niente da confermare nuovi
            assert conflitti(t) == 0 and re.search(r'\b2 già fra i da confermare', t), \
                'anteprima del giro %d: %s' % (giro, t[t.find('Cosa succederà'):][:300])
        fine = importa_ora(C, indirizzo)
        assert quanti(S, Appuntamento) == 2 and quanti(S, Appunto) == 2, 'giro %d: %d appuntamenti, %d da confermare' % (
            giro, quanti(S, Appuntamento), quanti(S, Appunto))
        if giro > 1:
            assert '(in conflitto o incomplete)' not in fine, 'giro %d: la pagina finale conta da confermare nuovi' % giro
    # uno chiuso dalla segreteria ("non serve piu'") non torna
    s = S()
    xid = s.scalars(select(Appunto).order_by(Appunto.id)).first().id
    s.close()
    assert C.post('/da-confermare/%d/chiudi' % xid).status_code == 302
    importa_ora(C, carica(C, dati, 'agenda.xlsx')[0])
    assert quanti(S, Appunto) == 2 and quanti(S, Appunto, Appunto.chiuso_il.is_(None)) == 1, \
        'dopo averne chiuso uno: %d da confermare, %d aperti' % (
            quanti(S, Appunto), quanti(S, Appunto, Appunto.chiuso_il.is_(None)))

    # il file senza la stanza: tutto fra i da confermare; poi, con la stanza scelta, in agenda
    S, C = mondo()
    s = S()
    amb = s.scalars(select(Risorsa).where(Risorsa.nome == 'Ambulatorio 1')).one().id
    s.close()
    righe = [['DATA', 'ORA', 'PAZIENTE', 'TELEFONO', 'MEDICO'],
             [D0, time(9), PAZIENTI[0], '3331234501', 'Galasso'],
             [D0, time(10), PAZIENTI[1], '3331234502', 'Galasso']]
    dati = xlsx(righe)
    importa_ora(C, carica(C, dati, 'agenda.xlsx')[0])
    assert quanti(S, Appunto, Appunto.chiuso_il.is_(None)) == 2 and quanti(S, Appuntamento) == 0
    indirizzo, t = carica(C, dati, 'agenda.xlsx', stanza_0=str(amb))
    assert re.search(r'\b2 da confermare si chiudono', t), 'l\'anteprima non dice che si chiudono'
    fine = importa_ora(C, indirizzo, stanza_0=str(amb))
    assert re.search(r'\b2 da confermare chiusi', fine), 'la pagina finale non lo dice'
    s = S()
    per_paziente = {a.paziente_id: a.id for a in s.scalars(select(Appuntamento))}
    chiusi = [(x.esito, x.appuntamento_id == per_paziente.get(x.paziente_id), x.chiuso_il is not None)
              for x in s.scalars(select(Appunto))]
    s.close()
    assert len(per_paziente) == 2 and chiusi == [('PRENOTATO', True, True)] * 2, 'da confermare: %s' % chiusi

    # la riga e' gia' in agenda (prenotata a mano dalla segreteria): il suo da confermare si chiude
    S, C = mondo()
    dati = xlsx(righe[:2])
    importa_ora(C, carica(C, dati, 'agenda.xlsx')[0])
    s = S()
    x = s.scalars(select(Appunto)).one()
    a = Appuntamento(risorsa_id=amb, operatore_id=x.operatore_id, paziente_id=x.paziente_id, stato='PRENOTATO',
                     inizio=datetime.combine(G, time(9)), fine=datetime.combine(G, time(9, 30)))
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    indirizzo, t = carica(C, dati, 'agenda.xlsx', stanza_0=str(amb))
    assert re.search(r'\b1 già in agenda', t) and re.search(r'\b1 da confermare si chiudono', t), \
        t[t.find('Cosa succederà'):][:300]
    importa_ora(C, indirizzo, stanza_0=str(amb))
    s = S()
    x = s.scalars(select(Appunto)).one()
    stato = (x.esito, x.appuntamento_id, x.chiuso_il is not None)
    s.close()
    assert stato == ('PRENOTATO', aid, True) and quanti(S, Appuntamento) == 1, stato


prova('[5] una riga disdetta non occupa la stanza e non si duplica', i05_riga_disdetta)
prova('[11] reimportando, i da confermare non si duplicano e si chiudono', i11_reimportare_da_confermare)


# =====================================================================
area('importazione: file grandi e rubrica')


def i08_troppe_righe():
    vecchio = importa.MASSIMO_RIGHE
    # per fare presto un limite piccolo: quello vero e' di 20.000 righe per foglio
    importa.MASSIMO_RIGHE = 40
    try:
        letto = importa.MASSIMO_RIGHE + 30           # righe lette, intestazione compresa
        n = 100
        intestazione = ['Cognome', 'Nome', 'Telefono']
        dati_ = [['Fintini%d' % i, 'Mario', '3%09d' % (330000000 + i)] for i in range(n)]
        oltre = 1 + n - letto                          # oracolo: le righe scritte che non si leggono
        # in fondo, righe vuote: non contano
        csv_dati = csv_([intestazione] + dati_ + [[None, None, None]] * 5)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        for r in [intestazione] + dati_:
            ws.append(r)
        b = io.BytesIO()
        wb.save(b)
        for nome, dati in (('rubrica.csv', csv_dati), ('rubrica.xlsx', b.getvalue())):
            foglio = importa.leggi_file(dati, nome)[0]
            assert (len(foglio['righe']), foglio.get('oltre')) == (letto, oltre), '%s: lette %d, oltre %s' % (
                nome, len(foglio['righe']), foglio.get('oltre'))
            S, C = mondo()
            indirizzo, t = carica(C, dati, nome)
            messaggio = 'Righe non lette: %d, dalla riga %d in poi' % (oltre, letto + 1)
            assert messaggio in t, '%s: l\'anteprima non lo dice' % nome
            fine = importa_ora(C, indirizzo)
            assert messaggio in fine, '%s: la pagina finale non lo dice' % nome
            assert quanti(S, Paziente) == letto - 1, quanti(S, Paziente)
        # righe vuote con un formato oltre il limite (Excel le conta): nessun falso allarme
        from openpyxl.styles import PatternFill
        wb = Workbook()
        ws = wb.active
        for r in [intestazione] + dati_[:50]:
            ws.append(r)
        for k in range(60, 300):
            ws.cell(k, 2).fill = PatternFill('solid', fgColor='FFFF00')
        b = io.BytesIO()
        wb.save(b)
        foglio = importa.leggi_file(b.getvalue(), 'formati.xlsx')[0]
        assert foglio.get('oltre') == 0 and len(foglio['righe']) == 51, (foglio.get('oltre'), len(foglio['righe']))
        S, C = mondo()
        indirizzo, t = carica(C, b.getvalue(), 'formati.xlsx')
        assert 'Righe non lette' not in t, 'falso allarme per le righe vuote con un formato'
    finally:
        importa.MASSIMO_RIGHE = vecchio


def i12_rubrica_righe_doppie():
    cf = CF.calcola('Fintini', 'Mario', date(1960, 3, 12), 'M', 'F839')
    righe = [['Cognome', 'Nome', 'Telefono', 'Email', 'Data di nascita', 'Codice fiscale'],
             ['Fintini', 'Mario', '3331234501', None, None, None],
             ['Fintini', 'Mario', '3331234501', 'mario.fintini@example.com', '12/03/1960', cf],
             ['Esempietti', 'Anna', '3331234502', 'anna.esempietti@example.com', None, None],
             # la stessa persona, ritrovata solo con il codice fiscale portato dalla riga 3
             ['Fintini', 'Mario', '3339999999', None, None, cf]]
    dati = csv_(righe)
    S, C = mondo()
    s, piano = piano_di(S, dati, 'rubrica.csv', tipo='pazienti')
    s.close()
    esiti_ = [(r['n'], r['esito']) for r in piano['righe']]
    assert esiti_ == [(2, 'nuovo'), (3, 'doppio'), (4, 'nuovo'), (5, 'doppio')], esiti_
    indirizzo, t = carica(C, dati, 'rubrica.csv')
    assert re.search(r'\b2 pazienti nuovi', t) and 'completa la scheda' in t, t[t.find('Cosa succederà'):][:300]
    fine = importa_ora(C, indirizzo)
    # una persona si conta una volta sola: 2 nuovi, nessuno anche "completato"
    assert re.search(r'\b2 pazienti nuovi', fine) and re.search(r'\b0 pazienti completati', fine), \
        fine[max(0, fine.find('pazienti nuovi') - 10):][:120]
    s = S()
    schede = {p.etichetta: (p.telefono, p.telefono2, p.email, p.data_nascita, p.codice_fiscale)
              for p in s.scalars(select(Paziente))}
    s.close()
    assert schede == {'Fintini Mario': ('3331234501', '3339999999', 'mario.fintini@example.com', date(1960, 3, 12), cf),
                      'Esempietti Anna': ('3331234502', '', 'anna.esempietti@example.com', None, '')}, schede
    # e importando di nuovo lo stesso file non cambia niente
    importa_ora(C, carica(C, dati, 'rubrica.csv')[0])
    assert quanti(S, Paziente) == 2


prova('[8] oltre il massimo di righe per foglio: lo dicono anteprima e pagina finale', i08_troppe_righe)
prova('[12] rubrica: la seconda riga della stessa persona completa la scheda', i12_rubrica_righe_doppie)


# =====================================================================
if __name__ == '__main__':
    aree = []
    for e in esiti:
        if e[1] not in aree:
            aree.append(e[1])
    for a in aree:
        mie = [e for e in esiti if e[1] == a]
        rotte = [e for e in mie if e[0] != 'OK']
        print('%-48s %2d prove  %s' % (a, len(mie), 'tutte a posto' if not rotte else '%d DA SISTEMARE' % len(rotte)))
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
