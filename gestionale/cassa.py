# -*- coding: utf-8 -*-
"""Listino e incassi. Il gestionale non fa fatture: registra quanto e'
stato pagato, come e quando, e a fine giornata da' il totale per metodo di
pagamento da confrontare con il cassetto e con il POS."""
import threading
from datetime import datetime, time, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from modelli import (Risorsa, Prestazione, Appuntamento, Tariffa, STATI_ATTIVI,
                     METODI_PAGAMENTO, ETICHETTA_PAGAMENTO, importo_in_testo)
import servizi
from comune import data_da, destinazione_sicura, intero, mese_da, scarica_excel, struttura_scelta

bp = Blueprint('cassa', __name__)
_fornitore = None
_lucchetto = threading.Lock()
_leggi_importo = None            # la stessa lettura degli importi del modulo di prenotazione


def collega(app, fornitore_sessione, lucchetto=None, leggi_importo=None):
    global _fornitore, _lucchetto, _leggi_importo
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    _leggi_importo = leggi_importo
    app.register_blueprint(bp)


def ses():
    return _fornitore()


def normalizza_convenzione(testo):
    return ' '.join((testo or '').split()).lower()


# ================================================================ listino
def tariffa_per(s, prestazione_id, convenzione=''):
    """Il prezzo proposto: quello della convenzione se c'e', altrimenti il
    listino della prestazione. None se non indicato."""
    conv = normalizza_convenzione(convenzione)
    if conv and conv != 'privato':
        for t in s.scalars(select(Tariffa).where(Tariffa.prestazione_id == prestazione_id)):
            if normalizza_convenzione(t.convenzione) == conv:
                return t.importo_cent
    p = s.get(Prestazione, prestazione_id)
    return p.tariffa_cent if p is not None else None


def mappa_tariffe(s):
    """Per il modulo di prenotazione: {id prestazione: {'': listino,
    'convenzione': prezzo}}, cosi' il prezzo si propone da solo."""
    uscita = {}
    for p in s.scalars(select(Prestazione)):
        if p.tariffa_cent is not None:
            uscita.setdefault(str(p.id), {})[''] = importo_in_testo(p.tariffa_cent)
    for t in s.scalars(select(Tariffa)):
        uscita.setdefault(str(t.prestazione_id), {})[normalizza_convenzione(t.convenzione)] = t.importo_testo
    return uscita


@bp.route('/cassa/listino', methods=['GET', 'POST'])
def listino():
    s = ses()
    st, _ = struttura_scelta(s)
    if request.method == 'POST':
        azione = request.form.get('azione')
        with _lucchetto:
            if azione == 'listino':
                errori, cambiati = [], 0
                for p in s.scalars(select(Prestazione)):
                    chiave = 'tariffa_%d' % p.id
                    if chiave not in request.form:
                        continue
                    try:
                        valore = _leggi_importo(request.form.get(chiave))
                    except ValueError:
                        errori.append('%s: importo non valido.' % p.nome)
                        continue
                    if valore != p.tariffa_cent:
                        p.tariffa_cent = valore
                        cambiati += 1
                if errori:
                    s.rollback()
                    for e in errori:
                        flash(e, 'errore')
                else:
                    s.commit()
                    flash('Listino salvato (%d prezz%s cambiat%s).' % (
                        cambiati, 'o' if cambiati == 1 else 'i', 'o' if cambiati == 1 else 'i'), 'ok')
            elif azione == 'aggiungi':
                p = s.get(Prestazione, intero(request.form.get('prestazione')))
                conv = ' '.join((request.form.get('convenzione') or '').split())
                try:
                    valore = _leggi_importo(request.form.get('importo'))
                except ValueError:
                    valore = None
                if p is None or not conv or len(conv) > 80 or valore is None:
                    flash('Tariffa: servono prestazione, convenzione (al massimo 80 caratteri) e importo.', 'errore')
                elif normalizza_convenzione(conv) == 'privato':
                    flash('Per i privati vale il prezzo di listino: si scrive nella tabella sopra.', 'errore')
                else:
                    esistente = next((t for t in s.scalars(select(Tariffa).where(Tariffa.prestazione_id == p.id))
                                      if normalizza_convenzione(t.convenzione) == normalizza_convenzione(conv)), None)
                    if esistente is not None:
                        esistente.importo_cent = valore
                    else:
                        s.add(Tariffa(prestazione_id=p.id, convenzione=conv, importo_cent=valore))
                    try:
                        s.commit()
                        flash('Tariffa salvata: %s con %s, %s €.' % (p.nome, conv, importo_in_testo(valore)), 'ok')
                    except IntegrityError:
                        s.rollback()
                        flash('Tariffa già presente.', 'errore')
            elif azione == 'elimina':
                t = s.get(Tariffa, intero(request.form.get('tariffa')))
                if t is not None:
                    s.delete(t)
                    s.commit()
                    flash('Tariffa tolta.', 'ok')
        return redirect(url_for('cassa.listino'))
    prestazioni = s.scalars(select(Prestazione).order_by(Prestazione.nome)).all()
    tariffe = s.scalars(select(Tariffa).join(Prestazione).order_by(Prestazione.nome, Tariffa.convenzione)).all()
    convenzioni = [c for c, in s.execute(
        select(Appuntamento.convenzione).where(Appuntamento.convenzione != '')
        .group_by(Appuntamento.convenzione).order_by(func.count().desc()).limit(30))]
    return render_template('listino.html', prestazioni=prestazioni, tariffe=tariffe,
                           convenzioni=convenzioni, st=st, sid=st.id if st else None, sezione='cassa')


# ============================================================== pagamenti
@bp.route('/appuntamento/<int:aid>/pagamento', methods=['POST'])
def pagamento(aid):
    s = ses()
    a = s.get(Appuntamento, aid)
    if a is None:
        abort(404)
    torna = destinazione_sicura(request.form.get('torna'), url_for('appuntamento', aid=a.id))
    azione = request.form.get('azione')
    with _lucchetto:
        if azione == 'annulla':
            if a.pagato:
                servizi.registra(s, 'Appuntamento', a.id, 'PAGAMENTO', 'annullato %s € %s' % (
                    a.pagato_testo, a.pagamento))
            a.pagato_cent, a.pagamento, a.pagato_il = None, '', None
            s.commit()
            flash('Pagamento annullato.', 'ok')
            return redirect(torna)
        metodo = request.form.get('metodo')
        if metodo not in ETICHETTA_PAGAMENTO:
            flash('Metodo di pagamento non valido.', 'errore')
            return redirect(torna)
        grezzo = request.form.get('importo')
        try:
            valore = _leggi_importo(grezzo) if (grezzo or '').strip() else a.importo_cent
        except ValueError:
            flash('Importo pagato non valido (esempio: 80,00).', 'errore')
            return redirect(torna)
        if not valore:
            flash('Manca l\'importo: scriverlo nel modulo o nel campo del pagamento.', 'errore')
            return redirect(torna)
        if a.importo_cent is None:
            a.importo_cent = valore          # pagato senza prezzo scritto: il prezzo e' quello
        a.pagato_cent, a.pagamento, a.pagato_il = valore, metodo, datetime.now()
        servizi.registra(s, 'Appuntamento', a.id, 'PAGAMENTO', '%s € %s' % (importo_in_testo(valore), metodo))
        s.commit()
    chi = a.paziente.etichetta if a.paziente else 'Appuntamento'
    flash('%s: pagati %s € (%s).' % (chi, importo_in_testo(valore), ETICHETTA_PAGAMENTO[metodo]), 'ok')
    return redirect(torna)


def incassi(s, dal, al, struttura_id=None):
    """Appuntamenti pagati fra dal e al compresi, per data di pagamento."""
    q = (select(Appuntamento).join(Risorsa, Appuntamento.risorsa_id == Risorsa.id)
         .where(Appuntamento.pagato_il >= datetime.combine(dal, time(0, 0)),
                Appuntamento.pagato_il < datetime.combine(al + timedelta(days=1), time(0, 0))))
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    return s.scalars(q.order_by(Appuntamento.pagato_il)).all()


def totali(pagati):
    per_metodo = {k: 0 for k, _ in METODI_PAGAMENTO}
    for a in pagati:
        per_metodo[a.pagamento] = per_metodo.get(a.pagamento, 0) + (a.pagato_cent or 0)
    return per_metodo, sum(per_metodo.values())


@bp.route('/cassa/<iso>')
def cassa_giorno(iso):
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso)
    pagati = incassi(s, g, g, st.id)
    per_metodo, totale = totali(pagati)
    del_giorno = servizi.elenco_giorno(s, g, st.id)
    da_incassare = [a for a in del_giorno if a.stato in STATI_ATTIVI and not a.pagato and a.importo_cent != 0]
    return render_template('cassa.html', g=g, st=st, sid=st.id, strutture=strutture, pagati=pagati,
                           per_metodo=per_metodo, totale=totale, da_incassare=da_incassare,
                           metodi=METODI_PAGAMENTO, etichette=ETICHETTA_PAGAMENTO,
                           titolo=servizi.etichetta_giorno(g), adesso=datetime.now(),
                           ieri=(g - timedelta(days=1)).isoformat(), domani=(g + timedelta(days=1)).isoformat(),
                           torna=request.full_path.rstrip('?'), sezione='cassa', data_menu=g.isoformat())


def riepilogo_mese(s, primo, ultimo, struttura_id):
    pagati = incassi(s, primo, ultimo, struttura_id)
    giorni = []
    g = primo
    while g <= ultimo:
        del_giorno = [a for a in pagati if a.pagato_il.date() == g]
        per_metodo, totale = totali(del_giorno)
        giorni.append({'data': g, 'per_metodo': per_metodo, 'totale': totale, 'n': len(del_giorno)})
        g += timedelta(days=1)
    per_metodo, totale = totali(pagati)
    return {'giorni': giorni, 'per_metodo': per_metodo, 'totale': totale, 'n': len(pagati),
            'pagati': pagati}


@bp.route('/cassa/mese/<aaaamm>')
def cassa_mese(aaaamm):
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    primo, ultimo = mese_da(aaaamm)
    r = riepilogo_mese(s, primo, ultimo, st.id)
    precedente = primo - timedelta(days=1)
    seguente = ultimo + timedelta(days=1)
    return render_template('cassa_mese.html', r=r, primo=primo, st=st, sid=st.id, strutture=strutture,
                           metodi=METODI_PAGAMENTO, titolo='%s %d' % (servizi.MESI[primo.month - 1].capitalize(), primo.year),
                           prima=precedente.strftime('%Y-%m'), dopo=seguente.strftime('%Y-%m'),
                           aaaamm=primo.strftime('%Y-%m'), giorni_brevi=servizi.GIORNI_BREVI,
                           sezione='cassa', data_menu=primo.isoformat())


@bp.route('/cassa/mese/<aaaamm>/excel')
def cassa_mese_excel(aaaamm):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        abort(404)
    primo, ultimo = mese_da(aaaamm)
    r = riepilogo_mese(s, primo, ultimo, st.id)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Per giorno'
    intestazioni = ['Giorno', 'Pagamenti'] + [e for _, e in METODI_PAGAMENTO] + ['Totale']
    ws.append(['%s - incassi di %s %d' % (st.nome, servizi.MESI[primo.month - 1], primo.year)])
    ws['A1'].font = Font(bold=True, size=13)
    ws.append(intestazioni)
    for c in ws[2]:
        c.font = Font(bold=True)
    for x in r['giorni']:
        ws.append([x['data'], x['n']] + [x['per_metodo'][k] / 100.0 for k, _ in METODI_PAGAMENTO]
                  + [x['totale'] / 100.0])
    ws.append(['Totale', r['n']] + [r['per_metodo'][k] / 100.0 for k, _ in METODI_PAGAMENTO] + [r['totale'] / 100.0])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for riga in ws.iter_rows(min_row=3):
        riga[0].number_format = 'dd/mm/yyyy'
        for c in riga[2:]:
            c.number_format = '#,##0.00'
    ws.column_dimensions['A'].width = 12
    ws2 = wb.create_sheet('Pagamenti')
    ws2.append(['Pagato il', 'Appuntamento', 'Paziente', 'Prestazione', 'Medico', 'Convenzione',
                'Metodo', 'Importo'])
    for c in ws2[1]:
        c.font = Font(bold=True)
    for a in r['pagati']:
        ws2.append([a.pagato_il, a.inizio, a.paziente.etichetta if a.paziente else '',
                    a.prestazione.nome if a.prestazione else '', a.operatore.etichetta if a.operatore else '',
                    a.convenzione or '', ETICHETTA_PAGAMENTO.get(a.pagamento, a.pagamento),
                    (a.pagato_cent or 0) / 100.0])
    for riga in ws2.iter_rows(min_row=2):
        riga[0].number_format = riga[1].number_format = 'dd/mm/yyyy hh:mm'
        riga[7].number_format = '#,##0.00'
    for colonna, larghezza in zip('ABCDEFGH', (17, 17, 26, 22, 20, 20, 12, 11)):
        ws2.column_dimensions[colonna].width = larghezza
    if st.societa:
        ws.oddFooter.left.text = ws2.oddFooter.left.text = st.societa
    nome = 'incassi-%s.xlsx' % primo.strftime('%Y-%m')
    return scarica_excel(wb, nome)
