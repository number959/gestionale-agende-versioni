# -*- coding: utf-8 -*-
"""Lo stile comune dei file Excel (1.12): ogni esportazione del programma si
riapre con openpyxl e si controlla che abbia il titolo con la struttura, le
intestazioni bianche su blu, il foglio A4 che sta in larghezza con le righe
da ripetere e «Pagina X di Y», i formati italiani (ore, euro, date), la riga
dei totali dove ha senso, e che un nome che comincia con «=» non diventi mai
una formula. Dati inventati.

    python prove_112_excel.py
"""
import logging
import os
import sys
import tempfile
import traceback
from datetime import date, datetime, time, timedelta
from io import BytesIO

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove_112_excel_')
os.environ['LOCALAPPDATA'] = os.path.join(PROVVISORIA, 'localappdata')
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
sys.path.insert(0, CARTELLA)
logging.getLogger().setLevel(logging.CRITICAL)

from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import select  # noqa: E402

import app as A  # noqa: E402
import comune  # noqa: E402
import servizi  # noqa: E402
import viste  # noqa: E402
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Turno, Appuntamento, Paziente,  # noqa: E402
                     Prestazione, Indirizzato)

A.app.config['TESTING'] = True
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
LUN = date(2026, 12, 7)


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


def mondo():
    """Una clinica inventata con una settimana piena: turni, appuntamenti
    (anche disdetti e non presentati), pagamenti, pazienti indirizzati, e un
    nome di stanza e uno di prestazione che cominciano con «=»."""
    _n[0] += 1
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'db_%d.db' % _n[0]))
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    st.nome, st.societa, st.giorni_apertura = 'Clinica Prova', 'Prova & Soci Srl', '1111110'
    s.add_all([Operatore(cognome='Galasso', nome='', specialita='cardiologia'),
               Operatore(cognome='Lippiello', nome='Anna', specialita='Dermatologia'),
               Operatore(cognome='Fintini', nome='Ugo')])
    s.add(Risorsa(nome='=Stanza strana', struttura_id=1, ordine=40))
    s.add(Prestazione(nome='=Visita strana', durata_min=30, tariffa_cent=8000))
    s.add_all([Paziente(cognome='Esempietti', nome='Rita', telefono='3330000001', email='rita@example.com'),
               Paziente(cognome='Provolo', nome='Ugo', telefono='3330000002')])
    s.commit()
    I = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    I.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    P = [p.id for p in s.scalars(select(Paziente).order_by(Paziente.id))]
    pr = {p.nome: p.id for p in s.scalars(select(Prestazione))}
    s.add(Turno(operatore_id=I['Galasso'], risorsa_id=I['Ambulatorio 1'], giorno_settimana=0, ora_inizio=time(8),
                ora_fine=time(13), valido_da=date(2026, 1, 5)))
    s.add(Turno(operatore_id=I['Lippiello'], risorsa_id=I['Ambulatorio 1'], giorno_settimana=0, ora_inizio=time(15),
                ora_fine=time(20), valido_da=date(2026, 1, 5)))
    s.add(Turno(operatore_id=I['Fintini'], risorsa_id=I['=Stanza strana'], giorno_settimana=0, ora_inizio=time(9),
                ora_fine=time(14), valido_da=date(2026, 1, 5)))

    def app(rid, oid, pid, h, m, dur, stato='PRENOTATO', importo=8000, prest='Visita', pagato=None):
        i = datetime.combine(LUN, time(h, m))
        a = Appuntamento(risorsa_id=rid, operatore_id=oid, paziente_id=pid, prestazione_id=pr.get(prest),
                         inizio=i, fine=i + timedelta(minutes=dur), stato=stato, importo_cent=importo)
        if pagato:
            a.pagato_cent, a.pagamento, a.pagato_il = pagato, 'POS', i + timedelta(hours=1)
        s.add(a)

    app(I['Ambulatorio 1'], I['Galasso'], P[0], 8, 0, 30, 'ARRIVATO', pagato=8000)
    app(I['Ambulatorio 1'], I['Galasso'], P[1], 8, 30, 60, 'CONFERMATO', prest='=Visita strana')
    app(I['Ambulatorio 1'], I['Galasso'], P[0], 9, 45, 15)
    app(I['Ambulatorio 1'], I['Galasso'], P[1], 9, 50, 10)
    app(I['Ambulatorio 1'], I['Lippiello'], P[0], 15, 0, 30, 'DISDETTO', 5000)
    app(I['=Stanza strana'], I['Fintini'], P[1], 10, 0, 90, 'NON_PRESENTATO')
    app(I['=Stanza strana'], I['Fintini'], P[0], 12, 0, 30, 'ARRIVATO', pagato=6000)
    s.add(Indirizzato(quando=datetime(2026, 12, 3, 10, 0), struttura_id=1, gruppo_nome='Centro Nord',
                      prestazione='Mammografia', branca='DIAGNOSTICA', paziente='Esempietti Rita', canale='telefono'))
    s.add(Indirizzato(quando=datetime(2026, 12, 4, 11, 0), struttura_id=1, gruppo_nome='Centro Nord',
                      prestazione='Holter', branca='CARDIOLOGIA', paziente='Provolo Ugo', canale='whatsapp'))
    s.add(Indirizzato(quando=datetime(2026, 12, 5, 11, 0), struttura_id=1, gruppo_nome='Centro Sud',
                      prestazione='=Formula', branca='X', paziente='Provolo Ugo', canale='email'))
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, I, A.app.test_client()


def scarica(C, indirizzo):
    r = C.get(indirizzo)
    assert r.status_code == 200 and r.data[:2] == b'PK', (indirizzo, r.status_code)
    return r, load_workbook(BytesIO(r.data))


def colore(cella):
    try:
        return (cella.fill.fgColor.rgb or '')[-6:]
    except Exception:
        return ''


def senza_dollaro(testo):
    return (testo or '').replace('$', '')


def riga_intestazione(ws, massimo=10):
    """La prima riga con la prima cella blu: l'intestazione della tabella."""
    for i in range(1, massimo + 1):
        if colore(ws.cell(i, 1)) == comune.EXCEL_BLU:
            return i
    raise AssertionError('nessuna riga di intestazione blu nelle prime %d righe' % massimo)


def controlla_foglio(ws, struttura='Clinica Prova', titolo=True):
    """Le regole comuni: A4 che sta in larghezza, righe da ripetere, «Pagina X
    di Y», il titolo con la struttura, l'intestazione bianca su blu."""
    assert str(ws.page_setup.paperSize) == '9', (ws.title, 'carta', ws.page_setup.paperSize)
    assert ws.page_setup.fitToWidth == 1 and ws.sheet_properties.pageSetUpPr.fitToPage, (ws.title, 'adatta')
    assert ws.print_title_rows, (ws.title, 'righe da ripetere')
    assert ws.oddFooter.right.text == 'Pagina &P di &N', (ws.title, ws.oddFooter.right.text)
    assert ws.oddFooter.left.text, (ws.title, 'pie\' senza societa\'')
    m = ws.page_margins
    assert m.top - m.header >= 0.3 and m.bottom - m.footer >= 0.3, \
        (ws.title, 'spazio per testata e piede (fino alla 1.12.3 un decimo di pollice)', m.top, m.header, m.bottom, m.footer)
    if titolo and struttura:
        assert struttura.lower() in str(ws['A1'].value).lower(), (ws.title, ws['A1'].value)
    i = riga_intestazione(ws)
    c = ws.cell(i, 1)
    assert c.font.bold and (c.font.color.rgb or '').endswith('FFFFFF'), (ws.title, 'intestazione')
    assert senza_dollaro(ws.print_title_rows).endswith('%d' % i) or senza_dollaro(ws.print_title_rows) == '1:2', (ws.title, ws.print_title_rows, i)
    return i


def niente_formule(wb):
    for ws in wb.worksheets:
        for riga in ws.iter_rows():
            for c in riga:
                assert c.data_type != 'f', (ws.title, c.coordinate, c.value)
                if isinstance(c.value, str) and c.value.startswith('='):
                    raise AssertionError('%s %s comincia con =: %r' % (ws.title, c.coordinate, c.value))


def riga_totale(ws, testa):
    for i in range(testa + 1, ws.max_row + 1):
        if str(ws.cell(i, 1).value or '').startswith('Totale'):
            return i
    raise AssertionError('%s: nessuna riga Totale' % ws.title)


# ============================================================= planning
area('planning del giorno')


def a_planning():
    S, I, C = mondo()
    r, wb = scarica(C, '/esporta/%s?struttura=1' % LUN.isoformat())
    assert 'planning-2026-12-07.xlsx' in r.headers.get('Content-Disposition', '')
    assert wb.sheetnames == ['07-12-2026', 'Elenco'], wb.sheetnames
    ws = wb['07-12-2026']
    assert 'CLINICA PROVA' in ws['A1'].value and 'PLANNING DEL LUNEDÌ 7 DICEMBRE 2026' in ws['A1'].value, ws['A1'].value
    assert str(ws.page_setup.paperSize) == '9' and ws.page_setup.fitToWidth == 1 and ws.page_setup.orientation == 'landscape'
    assert senza_dollaro(ws.print_title_rows) == '1:2' and senza_dollaro(ws.print_title_cols) == 'A:A', (ws.print_title_rows, ws.print_title_cols)
    assert ws.oddFooter.right.text == 'Pagina &P di &N' and ws.oddFooter.left.text == 'Prova && Soci Srl', ws.oddFooter.left.text
    assert 'Clinica Prova' in ws.oddHeader.center.text and 'lunedì 7 dicembre 2026' in ws.oddHeader.center.text
    # intestazione blu con i turni del giorno
    assert ws.cell(2, 1).value == 'ORA' and colore(ws.cell(2, 1)) == comune.EXCEL_BLU
    teste = {ws.cell(2, c).value.split('\n')[0]: ws.cell(2, c) for c in range(2, ws.max_column + 1, 2) if ws.cell(2, c).value}
    assert 'Galasso 08:00-13:00' in teste['Ambulatorio 1'].value and 'Lippiello Anna 15:00-20:00' in teste['Ambulatorio 1'].value, teste['Ambulatorio 1'].value
    assert ' =Stanza strana' in teste, list(teste)
    assert ws.freeze_panes == 'B3'
    # le celle: appuntamento verde, fascia libera nel turno azzurra, fuori turno grigia
    ore = {ws.cell(r_, 1).value: r_ for r_ in range(3, ws.max_row + 1) if isinstance(ws.cell(r_, 1).value, time)}
    assert ws.cell(ore[time(8, 0)], 1).number_format == 'hh:mm'
    c_amb1 = [c for c in range(2, ws.max_column + 1, 2) if (ws.cell(2, c).value or '').startswith('Ambulatorio 1')][0]
    assert colore(ws.cell(ore[time(8, 0)], c_amb1)) == 'E2EFDA' and 'Galasso' in ws.cell(ore[time(8, 0)], c_amb1).value
    assert ws.cell(ore[time(8, 0)], c_amb1).alignment.vertical == 'center'
    assert colore(ws.cell(ore[time(12, 0)], c_amb1)) == 'EEF3FA', 'libera nel turno di Galasso'
    assert colore(ws.cell(ore[time(14, 0)], c_amb1)) == 'ECEEF0', 'fra i due turni: chiusa'
    # due appuntamenti nella stessa fascia (9:45 e 9:50): la riga cresce
    assert ws.cell(ore[time(9, 30)], c_amb1).value.count('\n') == 1 and (ws.row_dimensions[ore[time(9, 30)]].height or 15) > 15
    assert '=Visita strana' in ws.cell(ore[time(8, 30)], c_amb1 + 1).value and ws.cell(ore[time(8, 30)], c_amb1 + 1).data_type == 's'
    legenda = [ws.cell(r_, 1).value for r_ in range(ws.max_row - 3, ws.max_row + 1) if str(ws.cell(r_, 1).value or '').startswith('Legenda')]
    assert legenda and 'azzurro' in legenda[0] and 'grigio' in legenda[0], legenda
    niente_formule(wb)
    return '%d righe, %d colonne' % (ws.max_row, ws.max_column)


def a_elenco():
    S, I, C = mondo()
    _, wb = scarica(C, '/esporta/%s?struttura=1' % LUN.isoformat())
    ws = wb['Elenco']
    testa = controlla_foglio(ws)
    assert 'Elenco del lunedì 7 dicembre 2026' in ws['A1'].value and '5 appuntamenti attivi' in ws['A2'].value, (ws['A1'].value, ws['A2'].value)
    assert '1 disdetto' in ws['A2'].value and '1 non presentato' in ws['A2'].value, ws['A2'].value
    assert ws['A3'].value.startswith('Esportato il ')
    assert [ws.cell(testa, c).value for c in range(1, 7)] == ['ORA', 'FINE', 'STANZA', 'MEDICO', 'PAZIENTE', 'TELEFONO']
    righe = [[ws.cell(i, c) for c in range(1, 14)] for i in range(testa + 1, ws.max_row + 1) if isinstance(ws.cell(i, 1).value, time)]
    assert len(righe) == 7, len(righe)
    assert righe[0][0].number_format == 'hh:mm' and righe[0][10].number_format == comune.FORMATO_EURO
    disdetto = next(r_ for r_ in righe if r_[11].value == 'Disdetto')
    assert disdetto[4].font.strike and disdetto[4].font.italic, 'disdetto barrato in grigio'
    non_pres = next(r_ for r_ in righe if r_[11].value == 'Non presentato')
    assert non_pres[4].font.italic and not non_pres[4].font.strike
    tot = riga_totale(ws, testa)
    assert ws.cell(tot, 1).value == 'Totale (solo attivi)' and ws.cell(tot, 5).value == '5 appuntamenti', (ws.cell(tot, 1).value, ws.cell(tot, 5).value)
    assert abs(ws.cell(tot, 11).value - 400.0) < 0.001 and ws.cell(tot, 11).number_format == comune.FORMATO_EURO, ws.cell(tot, 11).value
    assert ws.cell(tot, 1).font.bold and ws.cell(tot, 1).border.top.style == 'medium'
    assert ws.freeze_panes == 'A%d' % (testa + 1) and ws.auto_filter.ref.startswith('A%d:' % testa), (ws.freeze_panes, ws.auto_filter.ref)
    note = next(c for c in range(1, ws.max_column + 1) if ws.cell(testa, c).value == 'NOTE')
    assert righe[0][note - 1].alignment.wrap_text, 'le note a capo'
    strana = next(r_ for r_ in righe if r_[7].value and 'Visita strana' in r_[7].value)
    assert strana[7].value == ' =Visita strana' and strana[7].data_type == 's'
    niente_formule(wb)


prova('il planning: titolo, turni nelle intestazioni, celle colorate, legenda, A4 in larghezza', a_planning)
prova('l\'elenco: titolo e conteggi, formati, disdetti barrati, totali solo degli attivi, filtri', a_elenco)


# =================================================================== cassa
area('cassa, riepilogo medici, registro, turni, ambulatori')


def b_cassa():
    S, I, C = mondo()
    r, wb = scarica(C, '/cassa/mese/2026-12/excel?struttura=1')
    assert 'incassi-2026-12.xlsx' in r.headers.get('Content-Disposition', '')
    assert wb.sheetnames == ['Per giorno', 'Pagamenti']
    ws = wb['Per giorno']
    testa = controlla_foglio(ws)
    assert 'Incassi di dicembre 2026' in ws['A1'].value and '140,00 € in 2 pagamenti' in ws['A2'].value, (ws['A1'].value, ws['A2'].value)
    assert ws.page_setup.orientation == 'portrait'
    assert [ws.cell(testa, c).value for c in range(1, 3)] == ['Giorno', 'Pagamenti']
    giorni = [ws.cell(i, 1).value for i in range(testa + 1, ws.max_row + 1) if isinstance(ws.cell(i, 1).value, datetime)]
    assert len(giorni) == 1 and giorni[0].date() == LUN, 'solo i giorni con incassi'
    assert ws.cell(testa + 1, 1).number_format == comune.FORMATO_DATA and ws.cell(testa + 1, ws.max_column).number_format == comune.FORMATO_EURO
    tot = riga_totale(ws, testa)
    assert abs(ws.cell(tot, ws.max_column).value - 140.0) < 0.001 and ws.cell(tot, 2).value == 2, (ws.cell(tot, ws.max_column).value, ws.cell(tot, 2).value)
    ws2 = wb['Pagamenti']
    testa2 = controlla_foglio(ws2)
    righe = [i for i in range(testa2 + 1, ws2.max_row + 1) if isinstance(ws2.cell(i, 1).value, datetime)]
    assert len(righe) == 2 and ws2.cell(righe[0], 1).number_format == comune.FORMATO_DATA_ORA and ws2.cell(righe[0], 8).number_format == comune.FORMATO_EURO
    tot2 = riga_totale(ws2, testa2)
    assert ws2.cell(tot2, 3).value == '2 pagamenti' and abs(ws2.cell(tot2, 8).value - 140.0) < 0.001
    niente_formule(wb)


def b_riepilogo_medici():
    S, I, C = mondo()
    r, wb = scarica(C, '/riepilogo-medici/2026-12/excel?struttura=1')
    ws = wb['Riepilogo']
    testa = controlla_foglio(ws)
    assert 'Riepilogo per medico' in ws['A1'].value and 'dicembre 2026' in ws['A2'].value.lower(), (ws['A1'].value, ws['A2'].value)
    medici = {ws.cell(i, 1).value: i for i in range(testa + 1, ws.max_row + 1)}
    assert 'Galasso' in medici and 'Fintini Ugo' in medici and 'Lippiello Anna' in medici, list(medici)
    assert ws.cell(medici['Galasso'], 3).value == 4 and ws.cell(medici['Galasso'], 9).number_format == comune.FORMATO_EURO
    tot = riga_totale(ws, testa)
    assert ws.cell(tot, 3).value == 7 and abs(ws.cell(tot, 10).value - 140.0) < 0.001, (ws.cell(tot, 3).value, ws.cell(tot, 10).value)
    w = wb['Galasso']
    testa_g = controlla_foglio(w)
    assert 'Galasso' in w['A1'].value and '4 appuntamenti in 1 giorno' in w['A2'].value, (w['A1'].value, w['A2'].value)
    assert w.cell(testa_g + 1, 1).number_format == comune.FORMATO_DATA and w.cell(testa_g + 1, 2).number_format == 'hh:mm'
    assert isinstance(w.cell(testa_g + 1, 2).value, time), 'Ora come orario, non testo'
    tot_g = riga_totale(w, testa_g)
    assert w.cell(tot_g, 5).value == '4 appuntamenti' and abs(w.cell(tot_g, 10).value - 320.0) < 0.001 and abs(w.cell(tot_g, 11).value - 80.0) < 0.001
    niente_formule(wb)


def b_registro():
    S, I, C = mondo()
    r, wb = scarica(C, '/dove-si-fa/registro/2026-12.xlsx')
    ws = wb.active
    testa = controlla_foglio(ws, struttura=None)
    assert ws.oddFooter.left.text == 'Gestionale Agende', ws.oddFooter.left.text
    assert 'Pazienti indirizzati' in ws['A1'].value and 'Dicembre 2026 · 3 in tutto' == ws['A2'].value, (ws['A1'].value, ws['A2'].value)
    assert ws.cell(testa, 1).value == 'Data' and ws.cell(testa + 1, 1).number_format == comune.FORMATO_DATA
    tot = riga_totale(ws, testa)
    assert ws.cell(tot, 3).value == '3 indirizzati', ws.cell(tot, 3).value
    per = {ws.cell(i, 1).value: ws.cell(i, 2).value for i in range(tot + 1, ws.max_row + 1)}
    assert per.get('Centro Nord') == 2 and per.get('Centro Sud') == 1 and per.get('Totale') == 3, per
    strana = next(i for i in range(testa + 1, tot) if 'Formula' in str(ws.cell(i, 4).value))
    assert ws.cell(strana, 4).value == ' =Formula' and ws.cell(strana, 4).data_type == 's'
    niente_formule(wb)


def b_turni_personale():
    S, I, C = mondo()
    r, wb = scarica(C, '/personale/turni/mese/2026-12.xlsx?struttura=1')
    assert wb.sheetnames == ['Turni 12-2026', 'Elenco'], wb.sheetnames
    ws = wb['Turni 12-2026']
    assert 'dicembre 2026' in ws['A1'].value and 'Clinica Prova' in ws['A1'].value and ws['A2'].value.startswith('Esportato il ')
    assert colore(ws.cell(3, 1)) == comune.EXCEL_BLU and ws.cell(3, 1).value == 'Cognome e nome'
    assert str(ws.page_setup.paperSize) == '9' and senza_dollaro(ws.print_title_rows) == '3:3' and senza_dollaro(ws.print_title_cols) == 'A:B'
    assert ws.oddFooter.right.text == 'Pagina &P di &N' and 'Clinica Prova' in ws.oddHeader.center.text
    el = wb['Elenco']
    testa = controlla_foglio(el, struttura=None)
    assert el.cell(testa, 1).value == 'Data' and 'Elenco dei turni' in el['A1'].value
    assert riga_totale(el, testa) == testa + 1, 'senza turni: subito la riga dei totali'
    niente_formule(wb)


def b_ambulatori():
    S, I, C = mondo()
    _, wb = scarica(C, '/ambulatori/settimana/2026-12-07.xlsx?struttura=1')
    ws = wb['Matrice']
    assert str(ws.page_setup.paperSize) == '9' and ws.page_setup.fitToWidth == 1 and senza_dollaro(ws.print_title_rows) == '6:7'
    assert ws.oddFooter.right.text == 'Pagina &P di &N' and ws.oddFooter.left.text == 'Prova && Soci Srl'
    assert 'Clinica Prova' in ws.oddHeader.center.text and 'matrice ambulatori' in ws.oddHeader.center.text
    assert colore(ws.cell(6, 1)) == comune.EXCEL_BLU and ws.cell(6, 1).font.bold
    _, wb = scarica(C, '/ambulatori/mese/2026-12.xlsx?struttura=1')
    for nome, righe in (('Programmazione', '5:5'), ('Calendario', '3:3')):
        w = wb[nome]
        assert str(w.page_setup.paperSize) == '9' and senza_dollaro(w.print_title_rows) == righe and w.oddFooter.right.text == 'Pagina &P di &N', nome
        assert 'Clinica Prova' in w.oddHeader.center.text, w.oddHeader.center.text
    niente_formule(wb)


prova('incassi del mese: solo i giorni con incassi, totali, euro, pagamenti con i totali', b_cassa)
prova('riepilogo per medico: titolo, totali, fogli dei medici con ore vere e totali', b_riepilogo_medici)
prova('registro dei pazienti indirizzati: titolo, totali, conteggi per struttura', b_registro)
prova('turni del personale: titolo, intestazione, A4 con righe e colonne ripetute, elenco con i totali', b_turni_personale)
prova('ambulatori: matrice e programmazione con la testata e il pie\' comuni', b_ambulatori)


# ================================================================ aiutanti
area('gli aiutanti comuni')


def c_aiutanti():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    st = Struttura(nome='Clinica & Figli', societa='')
    riga = comune.apri_foglio_excel(ws, 'Prova', 'sotto', st, adesso=datetime(2026, 12, 7, 10, 5), colonne=3)
    assert riga == 5 and ws['A1'].value == 'Clinica & Figli — Prova' and ws['A2'].value == 'sotto'
    assert ws['A3'].value == 'Esportato il 07/12/2026 alle 10:05 dal Gestionale Agende'
    assert 'A1:C1' in [str(m) for m in ws.merged_cells.ranges]
    dopo = comune.tabella_excel(ws, riga, ['Nome', 'Quando', 'Euro', 'Note'], [20, 12, 12, 30],
                                [['=uno', date(2026, 1, 2), 10.5, 'a'], ['due', date(2026, 1, 3), 2.25, 'b']],
                                formati={2: comune.FORMATO_DATA, 3: comune.FORMATO_EURO},
                                totali={1: 'Totale', 3: 'somma', 4: 'conta'}, a_capo=(4,), zebra=True)
    assert ws.cell(riga, 1).value == 'Nome' and colore(ws.cell(riga, 1)) == comune.EXCEL_BLU
    assert ws.cell(riga + 1, 1).value == ' =uno' and ws.cell(riga + 1, 1).data_type == 's'
    assert ws.cell(riga + 1, 2).number_format == comune.FORMATO_DATA and ws.cell(riga + 1, 3).number_format == comune.FORMATO_EURO
    assert colore(ws.cell(riga + 2, 1)) == comune.EXCEL_ZEBRA and ws.cell(riga + 1, 4).alignment.wrap_text
    assert ws.cell(riga + 3, 1).value == 'Totale' and abs(ws.cell(riga + 3, 3).value - 12.75) < 0.001 and ws.cell(riga + 3, 4).value == 2
    assert ws.cell(riga + 3, 3).number_format == comune.FORMATO_EURO and ws.cell(riga + 3, 1).border.top.style == 'medium'
    assert dopo == riga + 5 and ws.freeze_panes == 'A%d' % (riga + 1) and ws.auto_filter.ref == 'A%d:D%d' % (riga, riga + 2)
    comune.imposta_stampa_excel(ws, False, '%d:%d' % (riga, riga), 'A:A', st, 'periodo')
    assert ws.page_setup.orientation == 'portrait' and str(ws.page_setup.paperSize) == '9'
    assert ws.oddHeader.center.text == 'Clinica && Figli · periodo' and ws.oddFooter.left.text == 'Clinica && Figli'
    assert ws.oddFooter.right.text == 'Pagina &P di &N' and senza_dollaro(ws.print_title_cols) == 'A:A'
    # senza totali e senza righe: niente filtro, niente riga Totale
    ws2 = wb.create_sheet('vuoto')
    dopo2 = comune.tabella_excel(ws2, 1, ['A', 'B'], None, [])
    assert dopo2 == 3 and ws2.auto_filter.ref is None and ws2.cell(2, 1).value is None
    niente_formule(wb)


prova('apri_foglio_excel, tabella_excel, imposta_stampa_excel: titolo, formati, totali, zebra, & nei testi', c_aiutanti)


# ================================================================= esito
if __name__ == '__main__':
    aree = {}
    for esito, nome_area, nome, dettaglio in esiti:
        aree.setdefault(nome_area, []).append((esito, nome, dettaglio))
    rotte = [(e, a, n, d) for e, a, n, d in esiti if e != 'OK']
    for nome_area, lista in aree.items():
        quante = len(lista)
        ko = sum(1 for e, _, _ in lista if e != 'OK')
        print('%-50s %d prove  %s' % (nome_area, quante, 'tutte a posto' if not ko else '%d DA SISTEMARE' % ko))
    if rotte:
        print('\nDettaglio:')
        for e, a, n, d in rotte:
            print('  %-6s [%s] %s\n         %s' % (e, a, n, str(d)[:300]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    sys.exit(1 if rotte else 0)
