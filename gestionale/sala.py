# -*- coding: utf-8 -*-
"""Sala operatoria: la checklist pre-operatoria di ogni intervento, la lista
operatoria da stampare, i posti letto per chi resta la notte e i giorni in
cui opera ciascun chirurgo.

Un intervento e' un appuntamento in una stanza di tipo "Sala operatoria".
"""
import json
import threading
from datetime import date, datetime, time, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   g as contesto)
from sqlalchemy import select, func

from modelli import (Struttura, Risorsa, Operatore, Appuntamento, Assenza, STATI_ATTIVI, CHECKLIST_PREDEFINITA,
                     MASSIMO_NOTTI, leggi_impostazione, scrivi_impostazione)
import servizi
from comune import data_da, destinazione_sicura, giorno_breve, struttura_scelta

bp = Blueprint('sala', __name__)
_fornitore = None
_lucchetto = threading.Lock()

TIPO_SALA = 'SALA_OPERATORIA'
MASSIMO_VOCI = 10
GIORNI_LETTI = 28           # notti mostrate in "Posti letto"
GIORNI_AVVISO_LETTI = 14    # notti controllate per le notifiche
SETTIMANE_PASSATE = 12      # quanto indietro si guarda per proporre i giorni di sala
SETTIMANE_FUTURE = 8


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)

    @app.context_processor
    def funzioni_sala():
        return {'checklist_di': checklist_richiesta, 'ci_sono_sale': ci_sono_sale}


def ses():
    return _fornitore()


# =============================================================== checklist
def voci_checklist(s):
    """Le voci della checklist, da Impostazioni. Una lista vuota salvata vuol
    dire "nessuna checklist"; un valore rovinato torna a quelle predefinite."""
    grezzo = leggi_impostazione(s, 'checklist_voci', '')
    if not grezzo:
        return list(CHECKLIST_PREDEFINITA)
    try:
        voci = json.loads(grezzo)
    except ValueError:
        return list(CHECKLIST_PREDEFINITA)
    if not isinstance(voci, list):
        return list(CHECKLIST_PREDEFINITA)
    return [str(v)[:60] for v in voci if str(v).strip()][:MASSIMO_VOCI]


def leggi_voci(testo):
    """Il riquadro di Impostazioni: una voce per riga, doppioni e righe vuote tolti."""
    voci, viste = [], set()
    for riga in (testo or '').splitlines():
        v = ' '.join(riga.split())[:60]
        if v and v.lower() not in viste:
            viste.add(v.lower())
            voci.append(v)
    if len(voci) > MASSIMO_VOCI:
        raise ValueError('Al massimo %d voci.' % MASSIMO_VOCI)
    return voci


def e_intervento(a):
    return a is not None and a.risorsa is not None and a.risorsa.tipo == TIPO_SALA


def stato_checklist(a, voci):
    """{'fatte', 'totale', 'mancanti', 'completa'} per un intervento; None per
    gli altri appuntamenti o se la checklist non ha voci."""
    if not e_intervento(a) or not voci:
        return None
    spunte = a.spunte
    mancanti = [v for v in voci if v not in spunte]
    return {'fatte': len(voci) - len(mancanti), 'totale': len(voci), 'mancanti': mancanti,
            'completa': not mancanti, 'spunte': spunte}


def checklist_richiesta(a):
    """Per le pagine: le voci si leggono una volta per richiesta."""
    if 'voci_checklist' not in contesto:
        try:
            contesto.voci_checklist = voci_checklist(ses())
        except Exception:
            contesto.voci_checklist = []
    return stato_checklist(a, contesto.voci_checklist)


def ci_sono_sale():
    """Per il menu: la voce Sala compare solo se c'e' una sala operatoria."""
    if 'ci_sono_sale' not in contesto:
        try:
            contesto.ci_sono_sale = ha_sale(ses(), None)
        except Exception:
            contesto.ci_sono_sale = False
    return contesto.ci_sono_sale


def anestesista(a):
    """Dal campo in piu' "Anestesista" o "Medico anestesista", se c'e'."""
    for k, v in a.valori_extra.items():
        if 'anestesi' in k.lower() and v.strip():
            return v
    return ''


def altri_extra(a):
    return [(k, v) for k, v in a.valori_extra.items() if 'anestesi' not in k.lower()]


def interventi(s, dal, al, struttura_id=None, stati=STATI_ATTIVI):
    """Gli interventi dal giorno 'dal' al giorno 'al' compresi, in ordine di ora."""
    q = (select(Appuntamento).join(Risorsa, Appuntamento.risorsa_id == Risorsa.id)
         .where(Risorsa.tipo == TIPO_SALA,
                Appuntamento.inizio >= datetime.combine(dal, time(0, 0)),
                Appuntamento.inizio < datetime.combine(al + timedelta(days=1), time(0, 0))))
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    if stati:
        q = q.where(Appuntamento.stato.in_(stati))
    return s.scalars(q.order_by(Appuntamento.inizio, Risorsa.ordine)).all()


def ha_sale(s, struttura_id):
    q = select(Risorsa.id).where(Risorsa.tipo == TIPO_SALA, Risorsa.attiva == True)
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    return s.scalars(q).first() is not None


@bp.route('/appuntamento/<int:aid>/checklist', methods=['POST'])
def checklist(aid):
    """Spunta o toglie una voce (dalla pagina, senza ricaricarla) oppure
    salva tutte le caselle insieme (senza JavaScript)."""
    s = ses()
    a = s.get(Appuntamento, aid)
    if a is None:
        abort(404)
    voci = voci_checklist(s)
    with _lucchetto:
        spunte = a.spunte
        adesso = datetime.now().strftime('%Y-%m-%d %H:%M')
        if 'voce' in request.form:
            voce = request.form.get('voce')
            if voce not in voci:
                abort(400)
            if request.form.get('fatto') in ('1', 'on', 'true'):
                spunte.setdefault(voce, adesso)
            else:
                spunte.pop(voce, None)
        else:
            scelte = set(request.form.getlist('spunte'))
            for v in voci:
                if v in scelte:
                    spunte.setdefault(v, adesso)
                else:
                    spunte.pop(v, None)
        # le voci tolte da Impostazioni non restano appese
        spunte = {k: v for k, v in spunte.items() if k in voci}
        a.checklist = json.dumps(spunte, ensure_ascii=False) if spunte else ''
        servizi.registra(s, 'Appuntamento', a.id, 'CHECKLIST', '%d/%d' % (len(spunte), len(voci)))
        s.commit()
    stato = stato_checklist(a, voci)
    if request.headers.get('X-Richiesta') == 'fetch':
        from segreteria import json_sicuro
        return json_sicuro({'fatte': stato['fatte'] if stato else len(spunte),
                            'totale': stato['totale'] if stato else len(voci),
                            'completa': bool(stato and stato['completa']),
                            'quando': spunte.get(request.form.get('voce', ''), '')})
    flash('Checklist salvata.', 'ok')
    return redirect(destinazione_sicura(request.form.get('torna'), url_for('appuntamento', aid=a.id)))


@bp.route('/sala/checklist-voci', methods=['POST'])
def salva_voci():
    s = ses()
    try:
        voci = leggi_voci(request.form.get('voci'))
    except ValueError as e:
        flash('Checklist: %s' % e, 'errore')
        return redirect(url_for('viste.impostazioni') + '#checklist')
    with _lucchetto:
        scrivi_impostazione(s, 'checklist_voci', '' if voci == CHECKLIST_PREDEFINITA else json.dumps(voci, ensure_ascii=False))
        s.commit()
    flash('Checklist pre-operatoria: %d voci salvate.' % len(voci) if voci else
          'Checklist pre-operatoria tolta: nessuna voce.', 'ok')
    return redirect(url_for('viste.impostazioni') + '#checklist')


# ============================================================== posti letto
def notti_occupate(s, struttura_id, dal, al):
    """{notte: [appuntamenti]} per le notti da 'dal' ad 'al' compresi. La notte
    D e' quella che comincia la sera del giorno D: un intervento del 10 con una
    notte occupa la notte del 10; un ricovero di 3 notti quelle del 10, 11 e 12."""
    q = (select(Appuntamento).join(Risorsa, Appuntamento.risorsa_id == Risorsa.id)
         .where(Appuntamento.degenza.in_(('NOTTE', 'RICOVERO')),
                Appuntamento.stato.in_(STATI_ATTIVI),
                Appuntamento.inizio >= datetime.combine(dal - timedelta(days=MASSIMO_NOTTI), time(0, 0)),
                Appuntamento.inizio < datetime.combine(al + timedelta(days=1), time(0, 0))))
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    notti = {dal + timedelta(days=i): [] for i in range((al - dal).days + 1)}
    for a in s.scalars(q.order_by(Appuntamento.inizio)):
        primo = a.inizio.date()
        for i in range(a.notti_letto):
            n = primo + timedelta(days=i)
            if n in notti:
                notti[n].append(a)
    return notti


def notti_oltre(s, st, dal, giorni=GIORNI_AVVISO_LETTI):
    """[(notte, occupati)] delle notti in cui i letti non bastano."""
    if st is None or not st.posti_letto:
        return []
    notti = notti_occupate(s, st.id, dal, dal + timedelta(days=giorni - 1))
    return [(n, len(x)) for n, x in sorted(notti.items()) if len(x) > st.posti_letto]


def avviso_letti(s, a):
    """Dopo aver salvato un intervento con una notte: i letti bastano?"""
    if a is None or not a.notti_letto or a.stato not in STATI_ATTIVI or a.risorsa is None:
        return None
    st = a.risorsa.struttura
    if st is None or not st.posti_letto:
        return None
    primo = a.inizio.date()
    oltre = [(n, k) for n, k in notti_oltre(s, st, primo, a.notti_letto)]
    if not oltre:
        return None
    n, k = oltre[0]
    return 'Posti letto: la notte del %s servono %d letti e ce ne sono %d.' % (
        n.strftime('%d/%m'), k, st.posti_letto)


@bp.route('/posti-letto')
def posti_letto():
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    dal = data_da(request.args.get('dal'), date.today())
    notti = notti_occupate(s, st.id, dal, dal + timedelta(days=GIORNI_LETTI - 1))
    righe = []
    for n, apps in sorted(notti.items()):
        righe.append({'notte': n, 'apps': apps, 'n': len(apps),
                      'oltre': bool(st.posti_letto and len(apps) > st.posti_letto)})
    massimo = max([r['n'] for r in righe] + [st.posti_letto or 0, 1])
    return render_template('posti_letto.html', st=st, strutture=strutture, sid=st.id, righe=righe,
                           dal=dal, massimo=massimo, giorno_breve=giorno_breve,
                           prima=(dal - timedelta(days=GIORNI_LETTI)).isoformat(),
                           dopo=(dal + timedelta(days=GIORNI_LETTI)).isoformat(),
                           sezione='sala', data_menu=dal.isoformat())


# ==================================================== la sala del giorno
def riassunto_giorno(s, g, struttura_id):
    """Per la griglia: quanti interventi, checklist incomplete, letti della notte."""
    st = s.get(Struttura, struttura_id) if struttura_id else None
    if st is None or not ha_sale(s, struttura_id):
        return None
    lista = interventi(s, g, g, struttura_id)
    voci = voci_checklist(s)
    incomplete = [a for a in lista if (stato_checklist(a, voci) or {'completa': True})['completa'] is False]
    letti = len(notti_occupate(s, struttura_id, g, g)[g])
    return {'interventi': len(lista), 'incomplete': len(incomplete), 'letti': letti,
            'posti': st.posti_letto, 'oltre': bool(st.posti_letto and letti > st.posti_letto),
            'chirurghi': chirurghi_del_giorno(s, g, struttura_id, lista)}


def chirurghi_del_giorno(s, g, struttura_id, lista=None):
    """Chi e' in sala quel giorno (con quanti interventi) e chi di solito
    opera in quel giorno della settimana ma non ha ancora niente: e' libero."""
    lista = lista if lista is not None else interventi(s, g, g, struttura_id)
    in_sala = {}
    for a in lista:
        in_sala.setdefault(a.operatore_id, [a.operatore, 0])[1] += 1
    assenti = set(s.scalars(select(Assenza.operatore_id).where(Assenza.dal <= g, Assenza.al >= g)))
    disponibili = [o for o in s.scalars(select(Operatore).where(Operatore.attivo == True)
                                        .order_by(Operatore.cognome, Operatore.nome))
                   if g.weekday() in o.giorni_di_sala and o.id not in in_sala and o.id not in assenti]
    # in ordine di cognome come gli altri elenchi; chi non e' piu' attivo non e' "assente"
    return {'in_sala': sorted(in_sala.values(), key=lambda x: (x[0].cognome, x[0].nome or '')),
            'disponibili': disponibili,
            'assenti': [o for o in s.scalars(select(Operatore).where(Operatore.id.in_(assenti),
                                                                     Operatore.attivo == True)
                                             .order_by(Operatore.cognome, Operatore.nome))
                        if g.weekday() in o.giorni_di_sala] if assenti else []}


@bp.route('/sala/<iso>')
def giornata(iso):
    """Gli interventi del giorno (o dei prossimi sette), con la checklist da
    spuntare, chirurgo, anestesista e degenza."""
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso)
    giorni = 7 if request.args.get('giorni') == '7' else 1
    voci = voci_checklist(s)
    lista = interventi(s, g, g + timedelta(days=giorni - 1), st.id)
    per_giorno = {}
    for a in lista:
        per_giorno.setdefault(a.inizio.date(), []).append(a)
    notti = notti_occupate(s, st.id, g, g + timedelta(days=giorni - 1))
    blocchi = []
    for i in range(giorni):
        d = g + timedelta(days=i)
        if giorni == 1 or per_giorno.get(d) or notti.get(d):
            blocchi.append({'giorno': d, 'apps': per_giorno.get(d, []), 'letti': len(notti.get(d, [])),
                            'chirurghi': chirurghi_del_giorno(s, d, st.id, per_giorno.get(d, []))})
    return render_template('sala.html', st=st, strutture=strutture, sid=st.id, g=g, giorni=giorni,
                           blocchi=blocchi, voci=voci, stato_checklist=stato_checklist,
                           anestesista=anestesista, giorno_breve=giorno_breve, sale=ha_sale(s, st.id),
                           titolo=servizi.etichetta_giorno(g),
                           ieri=(g - timedelta(days=giorni)).isoformat(),
                           domani=(g + timedelta(days=giorni)).isoformat(),
                           torna=request.full_path.rstrip('?'), sezione='sala', data_menu=g.isoformat())


@bp.route('/lista-operatoria/<iso>')
def lista_operatoria(iso):
    """Il foglio per la sala: una tabella per sala operatoria."""
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso)
    voci = voci_checklist(s)
    lista = interventi(s, g, g, st.id)
    sale = s.scalars(select(Risorsa).where(Risorsa.struttura_id == st.id, Risorsa.tipo == TIPO_SALA)
                     .order_by(Risorsa.ordine, Risorsa.nome)).all()
    gruppi = [(r, [a for a in lista if a.risorsa_id == r.id]) for r in sale]
    gruppi = [x for x in gruppi if x[1]]
    letti = notti_occupate(s, st.id, g, g)[g]
    return render_template('lista_operatoria.html', st=st, sid=st.id, g=g, gruppi=gruppi, voci=voci,
                           totale=len(lista), letti=len(letti), stato_checklist=stato_checklist,
                           anestesista=anestesista, altri_extra=altri_extra,
                           titolo=servizi.etichetta_giorno(g), adesso=datetime.now(),
                           ieri=(g - timedelta(days=1)).isoformat(), domani=(g + timedelta(days=1)).isoformat())


# ======================================================== giorni di sala
def storico_sala(s, dal, al):
    """{operatore_id: {giorno_settimana: numero di giorni diversi in sala}}."""
    conteggio = {}
    for a in interventi(s, dal, al, None, stati=('PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'NON_PRESENTATO')):
        conteggio.setdefault(a.operatore_id, {}).setdefault(a.inizio.weekday(), set()).add(a.inizio.date())
    return {o: {gs: len(d) for gs, d in x.items()} for o, x in conteggio.items()}


def proposta_giorni(storico_medico):
    """I giorni della settimana in cui ha operato almeno due volte."""
    return {gs for gs, n in storico_medico.items() if n >= 2}


@bp.route('/sala/chirurghi', methods=['GET', 'POST'])
def chirurghi():
    s = ses()
    st, strutture = struttura_scelta(s)
    oggi = date.today()
    dal, al = oggi - timedelta(weeks=SETTIMANE_PASSATE), oggi + timedelta(weeks=SETTIMANE_FUTURE)
    storico = storico_sala(s, dal, al)
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    if request.method == 'POST':
        with _lucchetto:
            cambiati = 0
            for o in medici:
                if 'presente_%d' % o.id not in request.form:
                    continue          # riga non mostrata: resta com'era
                nuovo = ''.join('1' if request.form.get('sala_%d_%d' % (o.id, i)) in ('1', 'on') else '0'
                                for i in range(7))
                nuovo = '' if nuovo == '0000000' else nuovo
                if nuovo != (o.giorni_sala or ''):
                    o.giorni_sala = nuovo
                    servizi.registra(s, 'Medico', o.id, 'GIORNI_SALA', nuovo)
                    cambiati += 1
            s.commit()
        flash('Giorni di sala salvati (%d medic%s cambiat%s).' % (cambiati, 'o' if cambiati == 1 else 'i',
                                                                   'o' if cambiati == 1 else 'i'), 'ok')
        return redirect(url_for('sala.chirurghi', struttura=st.id if st else None))
    proponi = request.args.get('proponi') == '1'
    chirurghi_, altri = [], []
    for o in medici:
        riga = {'o': o, 'storico': storico.get(o.id, {}),
                'giorni': proposta_giorni(storico.get(o.id, {})) if proponi and o.id in storico else o.giorni_di_sala}
        (chirurghi_ if o.id in storico or o.giorni_di_sala else altri).append(riga)
    return render_template('chirurghi.html', chirurghi=chirurghi_, altri=altri, proponi=proponi,
                           giorni=servizi.GIORNI_BREVI, dal=dal, al=al, st=st, sid=st.id if st else None,
                           sezione='sala')


def avviso_giorno_sala(a):
    """Salvando un intervento: il chirurgo di solito opera in quel giorno?"""
    if not e_intervento(a) or a.operatore is None or not a.operatore.giorni_di_sala:
        return None
    if a.inizio.weekday() in a.operatore.giorni_di_sala:
        return None
    giorni = ', '.join(servizi.GIORNI[i] for i in sorted(a.operatore.giorni_di_sala))
    return '%s di solito opera: %s.' % (a.operatore.etichetta, giorni)


# ================================================================ notifiche
def notifiche(s, struttura_id, adesso=None):
    adesso = adesso or datetime.now()
    oggi = adesso.date()
    uscita = []
    st = s.get(Struttura, struttura_id) if struttura_id else None
    if st is None:
        return uscita
    voci = voci_checklist(s)
    if voci:
        # oggi (gli interventi non ancora cominciati) e il prossimo giorno con interventi
        prossimo = next((oggi + timedelta(days=i) for i in range(1, 8)
                         if interventi(s, oggi + timedelta(days=i), oggi + timedelta(days=i), st.id)), None)
        for d in [oggi] + ([prossimo] if prossimo else []):
            lista = [a for a in interventi(s, d, d, st.id) if d > oggi or a.inizio > adesso]
            incomplete = [a for a in lista if not stato_checklist(a, voci)['completa']]
            if incomplete:
                quando = 'Oggi' if d == oggi else ('Domani' if d == oggi + timedelta(days=1)
                                                   else giorno_breve(d).capitalize())
                uscita.append({
                    'chiave': 'checklist-%s-%s' % (d.isoformat(), '-'.join(
                        '%d.%d' % (a.id, stato_checklist(a, voci)['fatte']) for a in incomplete[:20])),
                    'titolo': 'Checklist pre-operatoria',
                    'testo': '%s: %d intervent%s su %d con la checklist da completare.' % (
                        quando, len(incomplete), 'o' if len(incomplete) == 1 else 'i', len(lista)),
                    'link': url_for('sala.giornata', iso=d.isoformat(), struttura=st.id),
                    'azioni': [], 'livello': 'normale'})
    oltre = notti_oltre(s, st, oggi)
    if oltre:
        n, k = oltre[0]
        uscita.append({
            'chiave': 'letti-%s-%s' % (oggi.isoformat(), '-'.join('%s.%d' % (x.isoformat(), y) for x, y in oltre)),
            'titolo': 'Posti letto',
            'testo': 'La notte del %s servono %d letti e ce ne sono %d%s.' % (
                giorno_breve(n), k, st.posti_letto,
                (' (e altre %d notti)' % (len(oltre) - 1)) if len(oltre) > 1 else ''),
            'link': url_for('sala.posti_letto', dal=n.isoformat(), struttura=st.id),
            'azioni': [], 'livello': 'errore'})
    return uscita
