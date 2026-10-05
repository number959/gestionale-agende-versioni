# -*- coding: utf-8 -*-
"""La pagina "Oggi", che si apre all'avvio, e il riepilogo del mese per
ciascun medico, da stampare, scaricare in Excel o mandare per email."""
import re
import threading
from datetime import datetime, time, timedelta

from flask import Blueprint, render_template, request, url_for, abort
from sqlalchemy import select

from modelli import (Struttura, Risorsa, Operatore, Appuntamento, Attivita, STATI_ATTIVI, ETICHETTA_STATO,
                     ETICHETTA_PAGAMENTO, importo_in_testo)
import servizi
from comune import indirizzo_mail, mese_da, scarica_excel
import segreteria
import sala
import cassa
import pazienti
import backup

bp = Blueprint('cruscotto', __name__)
_fornitore = None
_lucchetto = threading.Lock()

TRA_POCO = timedelta(hours=2)        # "tra poco": gli appuntamenti delle prossime due ore
IN_RITARDO = timedelta(hours=3)      # oltre, un appuntamento non arrivato va nella chiusura giornata


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ===================================================================== oggi
def quadro_di_oggi(s, st, adesso=None):
    """Tutto quello che serve sapere entrando la mattina, per una struttura."""
    adesso = adesso or datetime.now()
    oggi = adesso.date()
    domani = oggi + timedelta(days=1)
    del_giorno = servizi.elenco_giorno(s, oggi, st.id)
    attivi = [a for a in del_giorno if a.stato in STATI_ATTIVI]
    # in ritardo: cominciati da poco e non ancora arrivati; tra poco: le prossime due ore
    in_ritardo = [a for a in attivi if a.stato != 'ARRIVATO' and adesso - IN_RITARDO <= a.inizio <= adesso]
    tra_poco = [a for a in attivi if a.stato != 'ARRIVATO' and adesso < a.inizio <= adesso + TRA_POCO]
    in_struttura = [a for a in attivi if a.stato == 'ARRIVATO' and a.fine > adesso]
    voci = sala.voci_checklist(s)
    interventi = sala.interventi(s, oggi, oggi, st.id)
    prossimo_sala = next((oggi + timedelta(days=i) for i in range(1, 8)
                          if sala.interventi(s, oggi + timedelta(days=i), oggi + timedelta(days=i), st.id)), None)
    interventi_poi = sala.interventi(s, prossimo_sala, prossimo_sala, st.id) if prossimo_sala else []
    prossimo = servizi.prossimo_giorno_con_appuntamenti(s, oggi, st.id)
    da_confermare = servizi.elenco_giorno(s, prossimo, st.id, ('PRENOTATO',)) if prossimo > oggi else []
    pagati = cassa.incassi(s, oggi, oggi, st.id)
    per_metodo, incassato = cassa.totali(pagati)
    letti_notte = sala.notti_occupate(s, st.id, oggi, oggi)[oggi]
    return {
        'adesso': adesso, 'oggi': oggi, 'domani': domani,
        'totale': len(attivi), 'arrivati': sum(1 for a in attivi if a.stato == 'ARRIVATO'),
        'annullati': [a for a in del_giorno if a.stato not in STATI_ATTIVI],
        'in_ritardo': in_ritardo, 'tra_poco': tra_poco, 'in_struttura': in_struttura,
        'primo': attivi[0] if attivi else None, 'ultimo': attivi[-1] if attivi else None,
        'interventi': interventi, 'voci': voci,
        'prossimo_sala': prossimo_sala, 'interventi_poi': interventi_poi,
        'incompleti_poi': [a for a in interventi_poi if not (sala.stato_checklist(a, voci) or {'completa': True})['completa']],
        'chirurghi': sala.chirurghi_del_giorno(s, oggi, st.id, interventi) if sala.ha_sale(s, st.id) else None,
        'appunti': [x for x in segreteria.appunti_aperti(s, st.id) if x.giorno and x.giorno <= domani],
        'appunti_tutti': segreteria.quanti_appunti(s),
        'cose': s.scalars(select(Attivita).where(Attivita.fatto_il == None, Attivita.per_il <= oggi)
                          .order_by(Attivita.per_il, Attivita.id).limit(8)).all(),
        'prossimo': prossimo, 'da_confermare': da_confermare,
        'n_prossimo': len(servizi.elenco_giorno(s, prossimo, st.id, STATI_ATTIVI)) if prossimo > oggi else 0,
        'arretrati': segreteria.giorni_da_chiudere(s, st.id, adesso),
        'incassato': incassato, 'n_pagati': len(pagati),
        # 0 e' gratuito: niente da incassare. Senza importo resta, finche' non si sa
        'da_incassare': [a for a in attivi if a.stato == 'ARRIVATO' and not a.pagato and a.importo_cent != 0],
        'letti': len(letti_notte), 'posti': st.posti_letto,
        'letti_oltre': sala.notti_oltre(s, st, oggi),
        'allarme': backup.allarme(adesso),
        'nota': segreteria.nota_del_giorno(s, st.id, oggi),
    }


@bp.route('/oggi')
def oggi():
    s = ses()
    st, strutture = segreteria.struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    q = quadro_di_oggi(s, st)
    return render_template('oggi.html', q=q, st=st, strutture=strutture, sid=st.id,
                           stato_checklist=sala.stato_checklist, giorno_breve=segreteria.giorno_breve,
                           titolo=servizi.etichetta_giorno(q['oggi']), torna=request.full_path.rstrip('?'),
                           sezione='oggi', data_menu=q['oggi'].isoformat())


# ============================================================ riepilogo medici
def riepilogo_medici(s, primo, ultimo, operatore_id=None, struttura_id=None):
    """Per ogni medico con appuntamenti nel mese: gli appuntamenti, quanti per
    stato e per prestazione, importi previsti e incassati."""
    q = (select(Appuntamento).join(Risorsa, Appuntamento.risorsa_id == Risorsa.id)
         .where(Appuntamento.inizio >= datetime.combine(primo, time(0, 0)),
                Appuntamento.inizio < datetime.combine(ultimo + timedelta(days=1), time(0, 0))))
    if operatore_id:
        q = q.where(Appuntamento.operatore_id == operatore_id)
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    per_medico = {}
    for a in s.scalars(q.order_by(Appuntamento.inizio, Risorsa.ordine)):
        per_medico.setdefault(a.operatore_id, []).append(a)
    uscita = []
    for oid, apps in per_medico.items():
        o = apps[0].operatore
        conteggio = {k: 0 for k in ETICHETTA_STATO}
        prestazioni = {}
        for a in apps:
            conteggio[a.stato] = conteggio.get(a.stato, 0) + 1
            if a.stato in STATI_ATTIVI:
                nome = a.prestazione.nome if a.prestazione else '(senza prestazione)'
                prestazioni[nome] = prestazioni.get(nome, 0) + 1
        validi = [a for a in apps if a.stato in STATI_ATTIVI]
        uscita.append({
            'operatore': o, 'apps': apps, 'conteggio': conteggio,
            'validi': len(validi),
            'prestazioni': sorted(prestazioni.items(), key=lambda x: (-x[1], x[0])),
            'previsto': sum(a.importo_cent or 0 for a in validi),
            'incassato': sum(a.pagato_cent or 0 for a in apps if a.pagato),
            'giorni': len({a.inizio.date() for a in validi}),
        })
    uscita.sort(key=lambda x: (x['operatore'].cognome.lower(), x['operatore'].nome.lower()))
    return uscita


def nome_mese(primo):
    return '%s %d' % (servizi.MESI[primo.month - 1], primo.year)


def testo_riepilogo(r, primo, st_nome):
    o, c = r['operatore'], r['conteggio']
    righe = ['Riepilogo di %s — %s%s' % (o.etichetta, nome_mese(primo), (' — %s' % st_nome) if st_nome else ''), '',
             'Appuntamenti: %d (arrivati %d, prenotati o confermati %d, non presentati %d, disdetti %d)' % (
                 len(r['apps']), c.get('ARRIVATO', 0), c.get('PRENOTATO', 0) + c.get('CONFERMATO', 0),
                 c.get('NON_PRESENTATO', 0), c.get('DISDETTO', 0)),
             'Giorni: %d' % r['giorni']]
    if r['previsto']:
        righe.append('Importi previsti: %s €' % importo_in_testo(r['previsto']))
    if r['incassato']:
        righe.append('Incassato: %s €' % importo_in_testo(r['incassato']))
    if r['prestazioni']:
        righe += ['', 'Per prestazione:'] + ['  %s: %d' % x for x in r['prestazioni']]
    righe += ['', 'Elenco:']
    for a in r['apps']:
        righe.append('%s %s  %s  %s%s' % (
            a.inizio.strftime('%d/%m'), a.inizio.strftime('%H:%M'),
            a.paziente.etichetta if a.paziente else '(senza paziente)',
            a.prestazione.nome if a.prestazione else '',
            '' if a.stato in STATI_ATTIVI else ' (%s)' % ETICHETTA_STATO[a.stato].lower()))
    return '\n'.join(righe)


def mail_riepilogo(r, primo, st_nome):
    o = r['operatore']
    if not (o.email and pazienti.email_valida(o.email)):
        return None
    # l'indirizzo mailto ha un limite: il resto e' nel foglio o nell'Excel
    return indirizzo_mail(o.email, 'Riepilogo di %s' % nome_mese(primo), testo_riepilogo(r, primo, st_nome),
                          '… (l\'elenco completo è nel file Excel allegato)')


def filtri_riepilogo(s):
    oid = segreteria.intero(request.args.get('medico')) or None
    scelto = s.get(Operatore, oid) if oid else None
    sid = segreteria.intero(request.args.get('struttura')) or None
    st = s.get(Struttura, sid) if sid else None
    return scelto, st


@bp.route('/riepilogo-medici/<aaaamm>')
def riepilogo(aaaamm):
    s = ses()
    primo, ultimo = mese_da(aaaamm)
    scelto, st = filtri_riepilogo(s)
    fogli = riepilogo_medici(s, primo, ultimo, scelto.id if scelto else None, st.id if st else None)
    for f in fogli:
        f['mail'] = mail_riepilogo(f, primo, st.nome if st else '')
    precedente = (primo - timedelta(days=1)).strftime('%Y-%m')
    successivo = (ultimo + timedelta(days=1)).strftime('%Y-%m')
    medici = s.scalars(select(Operatore).order_by(Operatore.attivo.desc(), Operatore.cognome, Operatore.nome)).all()
    strutture = s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).all()
    return render_template('riepilogo_medici.html', fogli=fogli, primo=primo, ultimo=ultimo,
                           mese=nome_mese(primo), aaaamm=primo.strftime('%Y-%m'), scelto=scelto, st=st,
                           sid=st.id if st else None, medici=medici, strutture=strutture,
                           precedente=precedente, successivo=successivo, etichette=ETICHETTA_STATO,
                           pagamenti=ETICHETTA_PAGAMENTO, adesso=datetime.now(),
                           piu_strutture=len(strutture) > 1)


@bp.route('/riepilogo-medici/<aaaamm>/excel')
def riepilogo_excel(aaaamm):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    s = ses()
    primo, ultimo = mese_da(aaaamm)
    scelto, st = filtri_riepilogo(s)
    fogli = riepilogo_medici(s, primo, ultimo, scelto.id if scelto else None, st.id if st else None)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Riepilogo'
    ws.append(['Riepilogo per medico — %s%s' % (nome_mese(primo), (' — %s' % st.nome) if st else '')])
    ws['A1'].font = Font(bold=True, size=13)
    intestazione = ['Medico', 'Specialità', 'Appuntamenti', 'Arrivati', 'Prenotati o confermati',
                    'Non presentati', 'Disdetti', 'Giorni', 'Importi previsti', 'Incassato']
    ws.append(intestazione)
    for c in ws[2]:
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=True, vertical='top')
    for f in fogli:
        c = f['conteggio']
        ws.append([f['operatore'].etichetta, f['operatore'].specialita or '', len(f['apps']),
                   c.get('ARRIVATO', 0), c.get('PRENOTATO', 0) + c.get('CONFERMATO', 0),
                   c.get('NON_PRESENTATO', 0), c.get('DISDETTO', 0), f['giorni'],
                   f['previsto'] / 100.0, f['incassato'] / 100.0])
    if fogli:
        ws.append(['Totale', '', sum(len(f['apps']) for f in fogli)]
                  + [sum(f['conteggio'].get(k, 0) for f in fogli) for k in ('ARRIVATO',)]
                  + [sum(f['conteggio'].get('PRENOTATO', 0) + f['conteggio'].get('CONFERMATO', 0) for f in fogli)]
                  + [sum(f['conteggio'].get(k, 0) for f in fogli) for k in ('NON_PRESENTATO', 'DISDETTO')]
                  + ['', sum(f['previsto'] for f in fogli) / 100.0, sum(f['incassato'] for f in fogli) / 100.0])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
    for riga in ws.iter_rows(min_row=3):
        riga[8].number_format = riga[9].number_format = '#,##0.00'
    for colonna, larghezza in zip('ABCDEFGHIJ', (28, 18, 13, 10, 13, 11, 10, 8, 13, 12)):
        ws.column_dimensions[colonna].width = larghezza
    usati = {'riepilogo'}
    for f in fogli:
        # un foglio per medico: il nome del foglio non puo' superare 31 caratteri ne' ripetersi
        base = re.sub(r'[\[\]:*?/\\]', ' ', f['operatore'].etichetta).strip()[:28] or 'Medico'
        nome, n = base, 2
        while nome.lower() in usati:
            nome, n = '%s %d' % (base[:26], n), n + 1
        usati.add(nome.lower())
        w = wb.create_sheet(nome)
        w.append(['%s — %s' % (f['operatore'].etichetta, nome_mese(primo))])
        w['A1'].font = Font(bold=True, size=12)
        w.append(['Giorno', 'Ora', 'Fine', 'Stanza', 'Paziente', 'Telefono', 'Prestazione', 'Stato',
                  'Convenzione', 'Importo', 'Pagato', 'Metodo', 'Note'])
        for c in w[2]:
            c.font = Font(bold=True)
        for a in f['apps']:
            w.append([a.inizio.date(), a.inizio.strftime('%H:%M'), a.fine.strftime('%H:%M'),
                      a.risorsa.nome if a.risorsa else '', a.paziente.etichetta if a.paziente else '',
                      a.paziente.telefono if a.paziente else '', a.prestazione.nome if a.prestazione else '',
                      ETICHETTA_STATO.get(a.stato, a.stato), a.convenzione or '',
                      (a.importo_cent / 100.0) if a.importo_cent is not None else None,
                      (a.pagato_cent / 100.0) if a.pagato else None,
                      ETICHETTA_PAGAMENTO.get(a.pagamento or '', '') if a.pagato else '', a.note or ''])
        for riga in w.iter_rows(min_row=3):
            riga[0].number_format = 'dd/mm/yyyy'
            riga[9].number_format = riga[10].number_format = '#,##0.00'
        for colonna, larghezza in zip('ABCDEFGHIJKLM', (11, 6, 6, 14, 26, 15, 24, 14, 16, 10, 10, 11, 40)):
            w.column_dimensions[colonna].width = larghezza
        w.freeze_panes = 'A3'
    societa = st.societa if st else next((x.societa for x in s.scalars(select(Struttura)) if x.societa), '')
    if societa:
        for w in wb.worksheets:
            w.oddFooter.left.text = societa
    nome = 'riepilogo-medici-%s%s.xlsx' % (primo.strftime('%Y-%m'), '-%d' % scelto.id if scelto else '')
    return scarica_excel(wb, nome)
