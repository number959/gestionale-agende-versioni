# -*- coding: utf-8 -*-
"""Le esportazioni in Excel per giorno, settimana e mese, ciascuna in tre versioni: solo gli ambulatori, solo
la sala operatoria, oppure tutto insieme (dalla 1.12.3, richiesta di Giovanni: «esportazioni singole giornaliere,
settimanali e mensili rispettivamente di ambulatori e sale operatorie, e un'esportazione unica che accorpi tutto
per giorno, settimana e mese»).

Nove file, una pagina (menu Ambulatori → Esportazioni in Excel) e un indirizzo solo:
/esportazioni/<giorno|settimana|mese>/<ambulatori|sala|tutto>/<data>.xlsx. I fogli li scrivono le stesse
funzioni delle pagine (servizi.esporta_giorno, ambulatori.foglio_matrice, fogli_programmazione e i fogli della
sala), cosi' un'esportazione non puo' dire una cosa diversa dalla pagina. In «tutto insieme» ambulatori e sala
stanno in fogli separati, con il loro nome.

Cosa c'e' in ciascuno:
- giorno: il planning delle stanze (o delle sale) con l'elenco degli appuntamenti; tutto: due fogli di planning,
  Ambulatori e Sala operatoria, piu' l'elenco di tutto;
- settimana: la matrice per la direzione sanitaria; la sala con i chirurghi e gli interventi di ogni mattina e
  pomeriggio, piu' l'elenco degli interventi; tutto: i tre fogli insieme;
- mese: la programmazione e il calendario; la sala giorno per giorno, i turni dei chirurghi e l'elenco degli
  interventi; tutto: la programmazione, il calendario con la sala, e i fogli della sala.
Gli elenchi della sala non hanno i dati dei pazienti (per quelli c'e' la lista operatoria del giorno); il planning
del giorno si', come sempre."""
import threading
from datetime import date, datetime, timedelta
from io import BytesIO

from flask import Blueprint, abort, render_template, request
from openpyxl import Workbook

import ambulatori
import calendario
import servizi
from comune import data_da, scarica_excel, struttura_scelta

bp = Blueprint('esportazioni', __name__)
_fornitore = None
_lucchetto = threading.Lock()

PERIODI = (('giorno', 'Giorno'), ('settimana', 'Settimana'), ('mese', 'Mese'))
PARTI = (('ambulatori', 'Ambulatori'), ('sala', 'Sala operatoria'), ('tutto', 'Tutto insieme'))
PREFISSI = {'ambulatori': 'ambulatori', 'sala': 'sala-operatoria', 'tutto': 'ambulatori-e-sala'}
CONTENUTO = {
    ('giorno', 'ambulatori'): 'il planning delle stanze e l\'elenco degli appuntamenti',
    ('giorno', 'sala'): 'il planning delle sale e l\'elenco degli interventi',
    ('giorno', 'tutto'): 'ambulatori e sala in due fogli, più l\'elenco di tutto',
    ('settimana', 'ambulatori'): 'la matrice per la direzione sanitaria',
    ('settimana', 'sala'): 'chirurghi e interventi, mattina e pomeriggio, più l\'elenco degli interventi',
    ('settimana', 'tutto'): 'la matrice, la sala e gli interventi, in fogli separati',
    ('mese', 'ambulatori'): 'la programmazione per specialità e il calendario',
    ('mese', 'sala'): 'la sala giorno per giorno, i turni dei chirurghi e l\'elenco degli interventi',
    ('mese', 'tutto'): 'la programmazione, il calendario con la sala e i fogli della sala',
}


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


def intervallo(periodo, g):
    """(primo, ultimo) giorno del periodo che contiene g."""
    if periodo == 'giorno':
        return g, g
    if periodo == 'settimana':
        lunedi = calendario.lunedi_di(g)
        return lunedi, lunedi + timedelta(days=6)
    primo = g.replace(day=1)
    return primo, (primo + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def titolo_periodo(periodo, g):
    primo, ultimo = intervallo(periodo, g)
    if periodo == 'giorno':
        return servizi.etichetta_giorno(primo)
    if periodo == 'settimana':
        return 'settimana ' + ambulatori.titolo_periodo(primo, ultimo)
    return '%s %d' % (servizi.MESI[primo.month - 1], primo.year)


def nome_file(periodo, parte, g):
    primo, _ = intervallo(periodo, g)
    quando = primo.strftime('%Y-%m') if periodo == 'mese' else primo.isoformat()
    return '%s-%s-%s.xlsx' % (PREFISSI[parte], periodo, quando)


def _nuovo_foglio(wb):
    """Il primo foglio vuoto del libro appena creato, poi uno nuovo per volta."""
    ws = wb.active
    if len(wb.worksheets) == 1 and ws.max_row == 1 and ws['A1'].value is None and ws.title == 'Sheet':
        return ws
    return wb.create_sheet()


def libro(s, st, periodo, parte, g, adesso=None):
    """Il libro Excel di un'esportazione: un Workbook, oppure i byte del planning del giorno."""
    adesso = adesso or datetime.now()
    primo, ultimo = intervallo(periodo, g)
    if periodo == 'giorno':
        dati = BytesIO()
        servizi.esporta_giorno(s, g, st.id, dati, parte=parte)
        return dati
    wb = Workbook()
    if periodo == 'settimana':
        vista = ambulatori.matrice(s, primo, st)
        if parte in ('ambulatori', 'tutto'):
            ws = ambulatori.foglio_matrice(_nuovo_foglio(wb), st, vista, adesso)
            if parte == 'tutto':
                ws.title = 'Ambulatori'
        if parte in ('sala', 'tutto'):
            ambulatori.foglio_sala_settimana(_nuovo_foglio(wb), st, vista, adesso)
            ambulatori.foglio_interventi(_nuovo_foglio(wb), st, ambulatori.interventi_periodo(s, st, primo, ultimo),
                                         titolo_periodo(periodo, g))
    else:
        vista = ambulatori.programmazione(s, primo.year, primo.month, st)
        if parte in ('ambulatori', 'tutto'):
            ambulatori.fogli_programmazione(wb, st, vista, adesso, con_sala=(parte == 'tutto'))
        if parte in ('sala', 'tutto'):
            ambulatori.foglio_sala_mese(_nuovo_foglio(wb), st, ambulatori.sala_del_mese(s, st, primo, ultimo), adesso)
            ambulatori.foglio_turni_sala(_nuovo_foglio(wb), st, vista, adesso)
            ambulatori.foglio_interventi(_nuovo_foglio(wb), st, ambulatori.interventi_periodo(s, st, primo, ultimo),
                                         titolo_periodo(periodo, g))
    wb.active = 0
    return wb


@bp.route('/esportazioni')
def pagina():
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(request.args.get('data'), date.today())
    voci = []
    for periodo, nome_periodo in PERIODI:
        quando = titolo_periodo(periodo, g)
        voci.append({'periodo': periodo, 'nome': nome_periodo,
                     'quando': quando[len('settimana '):] if periodo == 'settimana' else quando,
                     'parti': [{'parte': parte, 'nome': nome_parte, 'contenuto': CONTENUTO[(periodo, parte)],
                                'file': nome_file(periodo, parte, g)} for parte, nome_parte in PARTI]})
    return render_template('esportazioni.html', st=st, sid=st.id, strutture=strutture, g=g, voci=voci,
                           ha_sale=bool(ambulatori.sale_della(st)), oggi=date.today(), sezione='esportazioni',
                           data_menu=g.isoformat())


@bp.route('/esportazioni/<periodo>/<parte>/<iso>.xlsx')
def scarica(periodo, parte, iso):
    if periodo not in dict(PERIODI) or parte not in dict(PARTI):
        abort(404)
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso, date.today())
    return scarica_excel(libro(s, st, periodo, parte, g), nome_file(periodo, parte, g))
