# -*- coding: utf-8 -*-
"""Il lavoro quotidiano della segreteria, oltre a prenotare: chiudere la
giornata, la lista d'attesa, spostare appuntamenti (uno o tutti quelli di un
medico che va in ferie), le serie di appuntamenti, le note del giorno, le
cose da fare con le notifiche a scomparsa, gli appunti da confermare, la
ricerca rapida e l'agenda del giorno di ciascun medico."""
import logging
import re
import secrets
import threading
from datetime import date, datetime, time, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   abort)
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from modelli import (Struttura, Risorsa, Operatore, Prestazione, Appuntamento, Paziente,
                     Attesa, Attivita, NotaGiorno, Appunto, STATI_ATTIVI, ETICHETTA_STATO, FASCE_ATTESA)
import servizi
from comune import (PRIMA, ULTIMA, data_da, destinazione_sicura, giorno_breve, indirizzo_mail, intero,
                    json_sicuro, struttura_scelta)
import calendario
import pazienti
import backup
import sala

bp = Blueprint('segreteria', __name__)
_fornitore = None
_lucchetto = threading.Lock()

GIORNI_DA_CHIUDERE = 30           # oltre, un appuntamento aperto non fa piu' notifica
MASSIMO_SERIE = 52


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ============================================================== utilita'
def data_valida(testo):
    """La data del modulo, None se manca o non e' una data ammessa."""
    try:
        g = datetime.strptime(testo or '', '%Y-%m-%d').date()
    except ValueError:
        return None
    return g if PRIMA <= g <= ULTIMA else None


def carica(modello, ident):
    x = ses().get(modello, ident)
    if x is None:
        abort(404)
    return x


# ===================================================== chiusura giornata
def aperti_del_giorno(s, g, struttura_id, adesso=None):
    """Appuntamenti ancora prenotati o confermati di un giorno, gia' finiti:
    vanno segnati arrivati o non presentati."""
    adesso = adesso or datetime.now()
    return [a for a in servizi.elenco_giorno(s, g, struttura_id, ('PRENOTATO', 'CONFERMATO'))
            if a.fine <= adesso]


def giorni_da_chiudere(s, struttura_id, adesso=None, giorni=GIORNI_DA_CHIUDERE):
    """{data: quanti} degli ultimi 'giorni' giorni, oggi escluso, con
    appuntamenti ancora aperti."""
    adesso = adesso or datetime.now()
    oggi = adesso.date()
    dal = datetime.combine(oggi - timedelta(days=giorni), time(0, 0))
    q = (select(Appuntamento.inizio).join(Risorsa, Appuntamento.risorsa_id == Risorsa.id)
         .where(Appuntamento.stato.in_(('PRENOTATO', 'CONFERMATO')),
                Appuntamento.inizio >= dal,
                Appuntamento.inizio < datetime.combine(oggi, time(0, 0))))
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    conteggio = {}
    for (inizio,) in s.execute(q):
        conteggio[inizio.date()] = conteggio.get(inizio.date(), 0) + 1
    return dict(sorted(conteggio.items()))


@bp.route('/chiusura/<iso>', methods=['GET', 'POST'])
def chiusura(iso):
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso)
    oggi = date.today()
    if request.method == 'POST':
        azione = request.form.get('azione')
        nuovo = {'arrivati': 'ARRIVATO', 'non_presentati': 'NON_PRESENTATO'}.get(azione)
        scelti = {intero(x) for x in request.form.getlist('scelti')}
        if nuovo is None:
            flash('Azione non valida.', 'errore')
        elif not scelti:
            flash('Nessun appuntamento selezionato.', 'errore')
        else:
            fatti = 0
            with _lucchetto:
                # solo quelli davvero ancora aperti di quel giorno e di quella struttura
                for a in aperti_del_giorno(s, g, st.id):
                    if a.id in scelti and not servizi.imposta_stato(
                            s, a, nuovo, arrivo='adesso' if g == oggi else None):
                        fatti += 1
                s.commit()
            flash('%d appuntament%s segnat%s come %s.' % (
                fatti, 'o' if fatti == 1 else 'i', 'o' if fatti == 1 else 'i',
                ETICHETTA_STATO[nuovo].lower()), 'ok')
        return redirect(url_for('segreteria.chiusura', iso=g.isoformat(), struttura=st.id))
    aperti = aperti_del_giorno(s, g, st.id) if g <= oggi else []
    tutti = servizi.elenco_giorno(s, g, st.id)
    conteggi = {k: sum(1 for a in tutti if a.stato == k) for k in ETICHETTA_STATO}
    arretrati = {k: v for k, v in giorni_da_chiudere(s, st.id).items() if k != g}
    da_incassare = [a for a in tutti if a.stato == 'ARRIVATO' and a.importo_cent and not a.pagato]
    ancora_da_venire = sum(1 for a in tutti if a.stato in STATI_ATTIVI and a.fine > datetime.now())
    return render_template('chiusura.html', g=g, st=st, sid=st.id, strutture=strutture,
                           aperti=aperti, conteggi=conteggi, arretrati=arretrati,
                           da_incassare=da_incassare, ancora_da_venire=ancora_da_venire,
                           futuro=g > oggi, titolo=servizi.etichetta_giorno(g),
                           ieri=(g - timedelta(days=1)).isoformat(),
                           domani=(g + timedelta(days=1)).isoformat(),
                           giorno_breve=giorno_breve, sezione='chiusura', data_menu=g.isoformat())


# ======================================================== note del giorno
def nota_del_giorno(s, struttura_id, g):
    n = s.scalars(select(NotaGiorno).where(NotaGiorno.struttura_id == struttura_id,
                                           NotaGiorno.data == g)).first()
    return n.testo if n is not None and (n.testo or '').strip() else ''


@bp.route('/note-giorno', methods=['POST'])
def salva_nota():
    s = ses()
    st = s.get(Struttura, intero(request.form.get('struttura')))
    g = data_valida(request.form.get('data'))
    ripiego = url_for('giorno', iso=(g or date.today()).isoformat(), struttura=st.id if st else None)
    torna = destinazione_sicura(request.form.get('torna'), ripiego)
    if st is None or g is None:
        flash('Nota non salvata: struttura o giorno non validi.', 'errore')
        return redirect(torna)
    testo = (request.form.get('testo') or '').strip()
    if len(testo) > 1000:
        flash('La nota del giorno può avere al massimo 1000 caratteri.', 'errore')
        return redirect(torna)
    with _lucchetto:
        n = s.scalars(select(NotaGiorno).where(NotaGiorno.struttura_id == st.id,
                                               NotaGiorno.data == g)).first()
        if not testo:
            if n is not None:
                s.delete(n)
        elif n is None:
            s.add(NotaGiorno(struttura_id=st.id, data=g, testo=testo))
        else:
            n.testo = testo
        s.commit()
    flash('Nota del giorno salvata.' if testo else 'Nota del giorno tolta.', 'ok')
    return redirect(torna)


# ========================================================= lista d'attesa
def candidati_attesa(s, a):
    """Chi in lista d'attesa va bene per la fascia dell'appuntamento a, dal
    piu' vecchio in lista."""
    richieste = s.scalars(select(Attesa).where(Attesa.chiusa_il == None)
                          .order_by(Attesa.creato_il, Attesa.id)).all()
    return [x for x in richieste if x.adatta_a(a)]


def messaggio_posto_libero(a):
    st = a.risorsa.struttura if a.risorsa else None
    return ('Buongiorno, si è liberato un posto %s il %s alle %s presso %s. '
            'Se le interessa %s. Grazie.') % (
        'con %s' % a.operatore.etichetta if a.operatore else '',
        a.inizio.strftime('%d/%m'), a.inizio.strftime('%H:%M'), st.nome if st else '',
        servizi.recapito(st))


def _leggi_attesa(s, f, x=None):
    """(valori, errori) dal modulo della lista d'attesa."""
    errori = []
    oid = intero(f.get('operatore'))
    pid = intero(f.get('prestazione'))
    sid = intero(f.get('struttura'))
    if oid and s.get(Operatore, oid) is None:
        errori.append('Medico non valido.')
    if pid and s.get(Prestazione, pid) is None:
        errori.append('Prestazione non valida.')
    if sid and s.get(Struttura, sid) is None:
        errori.append('Struttura non valida.')
    fascia = f.get('fascia') or ''
    if fascia not in dict(FASCE_ATTESA):
        errori.append('Fascia: scelta non valida.')
        fascia = ''
    dal = data_valida(f.get('dal')) if f.get('dal') else None
    entro = data_valida(f.get('entro')) if f.get('entro') else None
    if f.get('dal') and dal is None or f.get('entro') and entro is None:
        errori.append('Date non valide.')
    if dal and entro and entro < dal:
        errori.append('La data "entro" viene prima di "disponibile dal".')
    note = (f.get('note') or '').strip()
    if len(note) > 1000:
        errori.append('Note: al massimo 1000 caratteri.')
    return dict(operatore_id=oid or None, prestazione_id=pid or None, struttura_id=sid or None,
                fascia=fascia, dal=dal, entro=entro, note=note), errori


@bp.route('/attesa')
def attesa():
    s = ses()
    st, strutture = struttura_scelta(s)
    tutte = request.args.get('chiuse') == '1'
    medico = s.get(Operatore, intero(request.args.get('medico'))) if request.args.get('medico') else None
    q = select(Attesa).order_by(Attesa.creato_il, Attesa.id)
    if not tutte:
        q = q.where(Attesa.chiusa_il == None)
    if medico is not None:
        q = q.where((Attesa.operatore_id == medico.id) | (Attesa.operatore_id == None))
    richieste = s.scalars(q).all()
    oggi = date.today()
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    return render_template('attesa.html', richieste=richieste, tutte=tutte, medico=medico,
                           medici=medici, oggi=oggi, st=st, sid=st.id if st else None,
                           fasce=dict(FASCE_ATTESA), sezione='attesa')


@bp.route('/attesa/nuova', methods=['GET', 'POST'])
@bp.route('/attesa/<int:xid>', methods=['GET', 'POST'])
def attesa_scheda(xid=None):
    s = ses()
    x = carica(Attesa, xid) if xid else None
    st, strutture = struttura_scelta(s)
    if request.method == 'POST':
        with _lucchetto:
            azione = request.form.get('azione')
            if x is not None and azione in ('rinuncia', 'riapri', 'elimina'):
                if azione == 'elimina':
                    s.delete(x)
                    s.commit()
                    flash('Richiesta tolta dalla lista d\'attesa.', 'ok')
                    return redirect(url_for('segreteria.attesa'))
                x.chiusa_il, x.esito = (datetime.now(), 'RINUNCIA') if azione == 'rinuncia' else (None, '')
                s.commit()
                flash('Richiesta chiusa: non serve più.' if azione == 'rinuncia' else 'Richiesta riaperta.', 'ok')
                return redirect(url_for('segreteria.attesa'))
            valori, errori = _leggi_attesa(s, request.form, x)
            paz = x.paziente if x is not None else None
            if x is None:
                nuovi, errori_p = _paziente_dal_modulo(request.form)
                errori += errori_p
            if errori:
                for e in errori:
                    flash(e, 'errore')
                return _mostra_attesa(s, x, st, request.form)
            if x is None:
                paz = pazienti.trova_o_crea(s, intero(request.form.get('paziente_id')), nuovi['cognome'],
                                            nuovi['nome'], nuovi['telefono'], nuovi['email'])
                if paz is None:
                    flash('Paziente: serve almeno il cognome.', 'errore')
                    return _mostra_attesa(s, x, st, request.form)
                x = Attesa(paziente_id=paz.id)
                s.add(x)
            for k, v in valori.items():
                setattr(x, k, v)
            s.flush()
            servizi.registra(s, 'Attesa', x.id, 'SALVATO', paz.etichetta if paz else '')
            s.commit()
            flash('%s è in lista d\'attesa.' % (paz.etichetta if paz else 'Il paziente'), 'ok')
            return redirect(url_for('segreteria.attesa'))
    return _mostra_attesa(s, x, st, None)


def _paziente_dal_modulo(f):
    errori = []
    cognome = ' '.join((f.get('paziente') or '').split())
    if not cognome and not intero(f.get('paziente_id')):
        errori.append('Paziente: serve almeno il cognome.')
    if len(cognome) > 60:
        errori.append('Paziente: al massimo 60 caratteri.')
    email = (f.get('email_paziente') or '').strip()
    if email and not pazienti.email_valida(email):
        errori.append('Email del paziente non valida.')
    telefono = (f.get('telefono') or '').strip()
    if telefono and len(pazienti.cifre(telefono)) < 6:
        errori.append('Telefono: servono almeno 6 cifre.')
    return dict(cognome=cognome, nome=(f.get('nome_paziente') or '').strip()[:60],
                telefono=telefono[:30], email=email[:120]), errori


def _mostra_attesa(s, x, st, modulo):
    scelto = None
    if x is None and modulo is None and request.args.get('paziente_id'):
        scelto = s.get(Paziente, intero(request.args.get('paziente_id')))
    return render_template(
        'attesa_scheda.html', x=x, modulo=modulo, paziente_scelto=scelto,
        medici=s.scalars(select(Operatore).where(Operatore.attivo == True)
                         .order_by(Operatore.cognome, Operatore.nome)).all(),
        prestazioni=s.scalars(select(Prestazione).order_by(Prestazione.nome)).all(),
        strutture=s.scalars(select(Struttura).where(Struttura.attiva == True)).all(),
        fasce=FASCE_ATTESA, proposto_medico=intero(request.args.get('medico')),
        proposta_prestazione=intero(request.args.get('prestazione')),
        st=st, sid=st.id if st else None, sezione='attesa')


@bp.route('/attesa/per/<int:aid>')
def attesa_per(aid):
    """Chi chiamare per la fascia lasciata libera dall'appuntamento aid."""
    s = ses()
    a = carica(Appuntamento, aid)
    candidati = candidati_attesa(s, a)
    testo = messaggio_posto_libero(a)
    contatti = {x.id: pazienti.collegamenti_paziente(x.paziente, testo) for x in candidati}
    st = a.risorsa.struttura if a.risorsa else None
    libera = not servizi.conflitti(s, a.risorsa_id, a.operatore_id, a.inizio, a.fine, escludi_id=a.id)
    return render_template('attesa_per.html', a=a, candidati=candidati, contatti=contatti,
                           libera=libera, st=st, sid=st.id if st else None,
                           giorno=servizi.etichetta_giorno(a.inizio.date()), sezione='attesa')


def chiudi_attesa_prenotata(s, xid, a):
    """Dopo aver prenotato dalla lista d'attesa: la richiesta e' soddisfatta."""
    x = s.get(Attesa, xid) if xid else None
    if x is not None and x.aperta and x.paziente_id == a.paziente_id:
        x.chiusa_il, x.esito, x.appuntamento_id = datetime.now(), 'PRENOTATO', a.id
        return True
    return False


# ================================================================= sposta
@bp.route('/appuntamento/<int:aid>/sposta', methods=['GET', 'POST'])
def sposta(aid):
    s = ses()
    a = carica(Appuntamento, aid)
    st = a.risorsa.struttura if a.risorsa else None
    if request.method == 'POST':
        try:
            inizio = datetime.strptime(request.form.get('inizio') or '', '%Y-%m-%dT%H:%M')
        except ValueError:
            inizio = None
        rid = intero(request.form.get('risorsa'))
        if inizio is None or not PRIMA <= inizio.date() <= ULTIMA:
            flash('Data e ora non valide.', 'errore')
            return redirect(url_for('segreteria.sposta', aid=a.id))
        with _lucchetto:
            prima = a.inizio
            motivi = servizi.sposta(s, a, inizio, rid or None)
            if motivi:
                flash('Non spostato: %s' % ' '.join(motivi), 'errore')
                return redirect(url_for('segreteria.sposta', aid=a.id))
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                flash('Quella fascia risulta già presa.', 'errore')
                return redirect(url_for('segreteria.sposta', aid=a.id))
        flash('Spostato dal %s al %s: avvisare il paziente.' % (
            prima.strftime('%d/%m alle %H:%M'), inizio.strftime('%d/%m alle %H:%M')), 'ok')
        return redirect(url_for('appuntamento', aid=a.id))
    dal = max(data_da(request.args.get('dal'), date.today()), date.today())
    tutte = request.args.get('tutte') == '1'
    proposte = servizi.disponibilita(s, a.operatore_id, a.durata_min, dal,
                                     None if tutte or st is None else st.id, giorni=90, massimo=20)
    testo = messaggio_spostamento(a, None)
    return render_template('sposta.html', a=a, proposte=proposte, dal=dal, tutte=tutte, st=st,
                           sid=st.id if st else None, giorni_nomi=servizi.GIORNI,
                           mesi=servizi.MESI, sezione='giorno', data_menu=a.inizio.date().isoformat())


def messaggio_spostamento(a, prima):
    st = a.risorsa.struttura if a.risorsa else None
    return ('Buongiorno, il suo appuntamento%s è stato spostato a %s alle %s presso %s. '
            'Per qualsiasi necessità %s. Grazie.') % (
        (' del %s' % prima.strftime('%d/%m')) if prima else '',
        giorno_breve(a.inizio.date()), a.inizio.strftime('%H:%M'), st.nome if st else '', servizi.recapito(st))


def proposte_blocco(s, apps, modo, dopo, sostituto_id=None):
    """Una nuova collocazione per ciascun appuntamento, tenendo conto di quelle
    gia' proposte agli altri: due pazienti non finiscono nella stessa fascia.

    modo 'dopo': stesso medico, primo posto libero da 'dopo' in poi.
    modo 'sostituto': stesso giorno, ora e stanza, con un altro medico."""
    prenotati = []          # (inizio, fine, risorsa_id, operatore_id) gia' assegnati
    uscita = []

    def libero(inizio, fine, rid, oid):
        return not any(i < fine and f > inizio and (r == rid or o == oid) for i, f, r, o in prenotati)

    for a in apps:
        proposta, motivo = None, ''
        if modo == 'sostituto':
            if not sostituto_id:
                motivo = 'scegliere il medico che sostituisce'
            else:
                problemi = servizi.conflitti(s, a.risorsa_id, sostituto_id, a.inizio, a.fine, escludi_id=a.id)
                if problemi or not libero(a.inizio, a.fine, a.risorsa_id, sostituto_id):
                    motivo = ' '.join(problemi) or 'il sostituto è già impegnato a quell\'ora'
                else:
                    proposta = (a.inizio, a.risorsa_id, sostituto_id)
        else:
            posti = servizi.disponibilita(s, a.operatore_id, a.durata_min, dopo,
                                          a.risorsa.struttura_id if a.risorsa else None,
                                          giorni=120, massimo=len(apps) + 20)
            for p in posti:
                if libero(p['inizio'], p['fine'], p['risorsa'].id, a.operatore_id):
                    proposta = (p['inizio'], p['risorsa'].id, a.operatore_id)
                    break
            if proposta is None:
                motivo = 'nessun posto libero nei 120 giorni successivi'
        if proposta:
            inizio, rid, oid = proposta
            prenotati.append((inizio, inizio + (a.fine - a.inizio), rid, oid))
        uscita.append({'a': a, 'proposta': proposta, 'motivo': motivo})
    return uscita


@bp.route('/sposta', methods=['GET', 'POST'])
def sposta_blocco():
    """Tutti gli appuntamenti di un medico in un periodo: ferie, malattia."""
    s = ses()
    st, strutture = struttura_scelta(s)
    medici = s.scalars(select(Operatore).order_by(Operatore.attivo.desc(), Operatore.cognome)).all()
    f = request.values
    medico = s.get(Operatore, intero(f.get('medico'))) if f.get('medico') else None
    dal = data_da(f.get('dal'), date.today())
    al = data_da(f.get('al'), dal)
    if al < dal:
        dal, al = al, dal
    if (al - dal).days > 366:
        al = dal + timedelta(days=366)
    modo = 'sostituto' if f.get('modo') == 'sostituto' else 'dopo'
    sostituto = s.get(Operatore, intero(f.get('sostituto'))) if f.get('sostituto') else None
    if sostituto is not None and medico is not None and sostituto.id == medico.id:
        sostituto = None
    if request.method == 'POST' and medico is not None:
        scelti = {intero(x) for x in request.form.getlist('scelti')}
        spostati, falliti, avvisi = 0, [], []
        notizie, avvisi_email = [], []
        import invii
        with _lucchetto:
            for aid in sorted(scelti):
                a = s.get(Appuntamento, aid)
                valore = request.form.get('p_%d' % aid) or ''
                m = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\|(\d+)\|(\d+)', valore)
                if a is None or a.operatore_id != medico.id or not m or a.stato not in STATI_ATTIVI:
                    continue
                inizio = datetime.strptime(m.group(1), '%Y-%m-%dT%H:%M')
                prima = a.inizio
                motivi = servizi.sposta(s, a, inizio, int(m.group(2)), int(m.group(3)))
                if motivi:
                    falliti.append('%s: %s' % (a.paziente.etichetta if a.paziente else prima.strftime('%d/%m %H:%M'),
                                               ' '.join(motivi)))
                    continue
                if a.operatore_id != medico.id:
                    # al sostituto: le sue email (le sue informative), se ne ha
                    s.expire(a, ['operatore'])
                    try:
                        invii.dopo_salvataggio(s, a, notizie, avvisi_email)
                    except Exception as e:
                        logging.exception('email automatiche dell\'appuntamento %s', a.id)
                        avvisi_email.append('Email automatica non preparata (%s): si può mandare dalla pagina '
                                            'dell\'appuntamento.' % e)
                try:
                    s.commit()
                except IntegrityError:
                    s.rollback()
                    falliti.append('%s: fascia già presa' % prima.strftime('%d/%m %H:%M'))
                    continue
                spostati += 1
                avvisi.append(a.id)
        flash('%d appuntament%s spostat%s.' % (spostati, 'o' if spostati == 1 else 'i',
                                                'o' if spostati == 1 else 'i'), 'ok' if not falliti else 'avviso')
        if notizie:
            invii.sveglia()
        for x in list(dict.fromkeys(notizie))[:10]:
            flash(x, 'ok')
        for x in list(dict.fromkeys(avvisi_email))[:10]:
            flash(x, 'avviso')
        for x in falliti:
            flash('Non spostato — %s' % x, 'errore')
        return redirect(url_for('segreteria.avvisa_spostati', ids=','.join(map(str, avvisi))))
    apps, proposte = [], []
    if medico is not None:
        inizio = datetime.combine(dal, time(0, 0))
        fine = datetime.combine(al + timedelta(days=1), time(0, 0))
        apps = s.scalars(select(Appuntamento).where(
            Appuntamento.operatore_id == medico.id, Appuntamento.inizio >= inizio,
            Appuntamento.inizio < fine, Appuntamento.inizio > datetime.now(),
            Appuntamento.stato.in_(STATI_ATTIVI)).order_by(Appuntamento.inizio)).all()
        proposte = proposte_blocco(s, apps, modo, al + timedelta(days=1),
                                   sostituto.id if sostituto else None)
    return render_template('sposta_blocco.html', medici=medici, medico=medico, dal=dal, al=al,
                           modo=modo, sostituto=sostituto, proposte=proposte, st=st,
                           sid=st.id if st else None, giorno_breve=giorno_breve,
                           sezione='giorno')


@bp.route('/sposta/avvisi')
def avvisa_spostati():
    """Dopo lo spostamento in blocco: chi avvisare, con il messaggio pronto."""
    s = ses()
    ids = [intero(x) for x in (request.args.get('ids') or '').split(',') if x.strip()][:500]
    apps = [a for a in (s.get(Appuntamento, i) for i in ids if i) if a is not None]
    apps.sort(key=lambda a: a.inizio)
    contatti = {a.id: pazienti.collegamenti_paziente(a.paziente, messaggio_spostamento(a, None))
                for a in apps if a.paziente}
    st, _ = struttura_scelta(s)
    return render_template('sposta_avvisi.html', apps=apps, contatti=contatti, st=st,
                           sid=st.id if st else None, giorno_breve=giorno_breve, sezione='giorno')


# ================================================================== serie
def crea_serie(s, a, ogni, unita, volte):
    """Le ripetizioni dell'appuntamento a (gia' salvato, e' la prima della
    serie). Restituisce (create, saltate); saltate = [(inizio, motivo)].
    Una ripetizione in conflitto non si sposta da sola: si segnala."""
    codice = secrets.token_hex(4)
    a.serie = codice
    create, saltate = [a], []
    momenti = servizi.date_serie(a.inizio, ogni, unita, volte)[1:]
    durata = a.fine - a.inizio
    for inizio in momenti:
        fine = inizio + durata
        motivi = servizi.conflitti(s, a.risorsa_id, a.operatore_id, inizio, fine)
        if motivi:
            saltate.append((inizio, ' '.join(motivi)))
            continue
        b = Appuntamento(risorsa_id=a.risorsa_id, operatore_id=a.operatore_id,
                         paziente_id=a.paziente_id, prestazione_id=a.prestazione_id,
                         inizio=inizio, fine=fine, stato='PRENOTATO', note=a.note,
                         tipo=a.tipo, convenzione=a.convenzione, importo_cent=a.importo_cent,
                         degenza=a.degenza, notti=a.notti, extra=a.extra, serie=codice)
        s.add(b)
        s.flush()
        create.append(b)
    servizi.registra(s, 'Appuntamento', a.id, 'SERIE', '%s: %d create, %d saltate' % (
        codice, len(create), len(saltate)))
    return create, saltate


def leggi_ripetizione(f):
    """(ogni, unita, volte) dal modulo di prenotazione, None se non si ripete.
    ValueError con il motivo se i valori non vanno."""
    if f.get('ripeti') not in ('1', 'on'):
        return None
    try:
        ogni = int(f.get('ripeti_ogni') or 1)
        volte = int(f.get('ripeti_volte') or 0)
    except ValueError:
        raise ValueError('Ripetizione: servono numeri interi.')
    unita = f.get('ripeti_unita')
    if unita not in ('giorni', 'settimane', 'mesi'):
        raise ValueError('Ripetizione: unità non valida.')
    if not 1 <= ogni <= 52:
        raise ValueError('Ripetizione: "ogni" deve stare fra 1 e 52.')
    if not 2 <= volte <= MASSIMO_SERIE:
        raise ValueError('Ripetizione: le volte devono stare fra 2 e %d.' % MASSIMO_SERIE)
    return ogni, unita, volte


@bp.route('/serie/<codice>', methods=['GET', 'POST'])
def serie(codice):
    s = ses()
    if not re.fullmatch(r'[0-9a-f]{8}', codice or ''):
        abort(404)
    apps = s.scalars(select(Appuntamento).where(Appuntamento.serie == codice)
                     .order_by(Appuntamento.inizio)).all()
    if not apps:
        abort(404)
    if request.method == 'POST' and request.form.get('azione') == 'disdici':
        dal = intero(request.form.get('dal'))
        partenza = next((a for a in apps if a.id == dal), None)
        n = 0
        with _lucchetto:
            for a in apps:
                if partenza and a.inizio >= partenza.inizio and a.stato in STATI_ATTIVI and a.inizio > datetime.now():
                    servizi.imposta_stato(s, a, 'DISDETTO')
                    n += 1
            s.commit()
        flash('%d appuntament%s della serie disdett%s.' % (n, 'o' if n == 1 else 'i', 'o' if n == 1 else 'i'), 'ok')
        return redirect(url_for('segreteria.serie', codice=codice))
    st = apps[0].risorsa.struttura if apps[0].risorsa else None
    return render_template('serie.html', apps=apps, codice=codice, st=st, sid=st.id if st else None,
                           adesso=datetime.now(), giorno_breve=giorno_breve, sezione='giorno')


# ============================================================ cose da fare
@bp.route('/cose-da-fare', methods=['GET', 'POST'])
def cose_da_fare():
    s = ses()
    st, _ = struttura_scelta(s)
    if request.method == 'POST':
        testo = ' '.join((request.form.get('testo') or '').split())
        per_il = data_valida(request.form.get('per_il')) if request.form.get('per_il') else date.today()
        pid = intero(request.form.get('paziente_id'))
        aid = intero(request.form.get('appuntamento_id'))
        torna = destinazione_sicura(request.form.get('torna'), url_for('segreteria.cose_da_fare'))
        if not testo or len(testo) > 300 or per_il is None:
            flash('Cosa da fare: serve un testo (al massimo 300 caratteri) e una data valida.', 'errore')
            return redirect(torna)
        with _lucchetto:
            s.add(Attivita(testo=testo, per_il=per_il,
                           paziente_id=pid if pid and s.get(Paziente, pid) else None,
                           appuntamento_id=aid if aid and s.get(Appuntamento, aid) else None))
            s.commit()
        flash('Aggiunta alle cose da fare per %s.' % (
            'oggi' if per_il == date.today() else giorno_breve(per_il)), 'ok')
        return redirect(torna)
    oggi = date.today()
    aperte = s.scalars(select(Attivita).where(Attivita.fatto_il == None)
                       .order_by(Attivita.per_il, Attivita.id)).all()
    fatte = s.scalars(select(Attivita).where(Attivita.fatto_il != None)
                      .order_by(Attivita.fatto_il.desc()).limit(30)).all()
    return render_template('cose_da_fare.html', scadute=[x for x in aperte if x.per_il < oggi],
                           di_oggi=[x for x in aperte if x.per_il == oggi],
                           prossime=[x for x in aperte if x.per_il > oggi], fatte=fatte,
                           oggi=oggi, st=st, sid=st.id if st else None, giorno_breve=giorno_breve,
                           sezione='cose')


@bp.route('/cose-da-fare/<int:xid>/<azione>', methods=['POST'])
def cosa_fatta(xid, azione):
    s = ses()
    x = carica(Attivita, xid)
    with _lucchetto:
        if azione == 'fatto':
            x.fatto_il = datetime.now()
        elif azione == 'rimanda':
            x.per_il = max(x.per_il, date.today()) + timedelta(days=1)
        elif azione == 'riapri':
            x.fatto_il = None
        elif azione == 'elimina':
            s.delete(x)
        else:
            abort(404)
        s.commit()
    if request.headers.get('X-Richiesta') == 'notifica':
        return json_sicuro({'ok': True})
    return redirect(destinazione_sicura(request.form.get('torna'), url_for('segreteria.cose_da_fare')))


# ====================================================== appunti da confermare
def appunti_aperti(s, struttura_id=None):
    q = select(Appunto).where(Appunto.chiuso_il == None)
    if struttura_id:
        q = q.where((Appunto.struttura_id == struttura_id) | (Appunto.struttura_id == None))
    return s.scalars(q.order_by(Appunto.giorno.is_(None), Appunto.giorno, Appunto.ora, Appunto.id)).all()


def appunti_del_giorno(s, g, struttura_id):
    return [x for x in appunti_aperti(s, struttura_id) if x.giorno == g]


def quanti_appunti(s):
    return s.scalar(select(func.count()).select_from(Appunto).where(Appunto.chiuso_il == None)) or 0


def modulo_da_appunto(x):
    """I campi del modulo di prenotazione gia' compilati con l'appunto."""
    p = x.paziente
    return {
        'paziente_id': str(p.id) if p else '',
        'paziente': p.cognome if p else (x.cognome or ''),
        'nome_paziente': p.nome if p else (x.nome or ''),
        'telefono': p.telefono if p else (x.telefono or ''),
        'email_paziente': (p.email or '') if p else '',
        'operatore': str(x.operatore_id or ''),
        'prestazione': str(x.prestazione_id or ''),
        'durata': str(x.durata_min or ''),
        'note': x.note or '',
        'tipo': '', 'convenzione': '', 'importo': '', 'provenienza': '',
    }


def indirizzo_prenota(x):
    return url_for('appuntamento', appunto=x.id, data=x.giorno.isoformat() if x.giorno else None,
                   ora=x.ora.strftime('%H:%M') if x.ora else None, risorsa=x.risorsa_id or None,
                   struttura=x.struttura_id or None)


def chiudi_appunto_prenotato(s, xid, a):
    """Salvato l'appuntamento nato da un appunto: l'appunto e' fatto."""
    x = s.get(Appunto, xid) if xid else None
    if x is None or not x.aperto or a is None:
        return False
    x.chiuso_il, x.esito, x.appuntamento_id = datetime.now(), 'PRENOTATO', a.id
    return True


def leggi_appunto(s, f):
    """Appunto dal modulo: testo obbligatorio, il resto se c'e'."""
    testo = ' '.join((f.get('testo') or '').split())
    if not testo or len(testo) > 1000:
        raise ValueError('Serve cosa c\'è da confermare (al massimo 1000 caratteri).')
    giorno = data_valida(f.get('giorno')) if f.get('giorno') else None
    if f.get('giorno') and giorno is None:
        raise ValueError('Giorno non valido.')
    ora = None
    if f.get('ora'):
        try:
            ora = datetime.strptime(f.get('ora'), '%H:%M').time()
        except ValueError:
            raise ValueError('Ora non valida.')
    def esistente(modello, chiave):
        i = intero(f.get(chiave))
        return i if i and s.get(modello, i) is not None else None
    telefono = ' '.join((f.get('telefono') or '').split())[:30]
    return dict(testo=testo, giorno=giorno, ora=ora, struttura_id=esistente(Struttura, 'struttura'),
                risorsa_id=esistente(Risorsa, 'risorsa'), operatore_id=esistente(Operatore, 'operatore'),
                prestazione_id=esistente(Prestazione, 'prestazione'), paziente_id=esistente(Paziente, 'paziente_id'),
                cognome=' '.join((f.get('cognome') or '').split())[:60],
                nome=' '.join((f.get('nome') or '').split())[:60], telefono=telefono, origine='inserito a mano')


@bp.route('/da-confermare', methods=['GET', 'POST'])
def da_confermare():
    s = ses()
    st, strutture = struttura_scelta(s)
    torna = destinazione_sicura(request.form.get('torna'), url_for('segreteria.da_confermare'))
    if request.method == 'POST':
        try:
            campi = leggi_appunto(s, request.form)
        except ValueError as e:
            flash(str(e), 'errore')
            return redirect(torna)
        with _lucchetto:
            s.add(Appunto(**campi))
            s.commit()
        flash('Appunto aggiunto ai da confermare.', 'ok')
        return redirect(torna)
    aperti = appunti_aperti(s)
    oggi = date.today()
    chiusi = s.scalars(select(Appunto).where(Appunto.chiuso_il != None)
                       .order_by(Appunto.chiuso_il.desc()).limit(30)).all()
    return render_template(
        'da_confermare.html', aperti=aperti, chiusi=chiusi, oggi=oggi, st=st, sid=st.id if st else None,
        passati=[x for x in aperti if x.giorno and x.giorno < oggi],
        prossimi=[x for x in aperti if x.giorno and x.giorno >= oggi],
        senza_giorno=[x for x in aperti if not x.giorno],
        stanze=s.scalars(select(Risorsa).where(Risorsa.attiva == True).order_by(Risorsa.struttura_id, Risorsa.ordine)).all(),
        medici=s.scalars(select(Operatore).where(Operatore.attivo == True).order_by(Operatore.cognome)).all(),
        prestazioni=s.scalars(select(Prestazione).order_by(Prestazione.nome)).all(),
        indirizzo_prenota=indirizzo_prenota, giorno_breve=giorno_breve, sezione='confermare')


@bp.route('/da-confermare/<int:xid>/<azione>', methods=['POST'])
def appunto_azione(xid, azione):
    s = ses()
    x = carica(Appunto, xid)
    with _lucchetto:
        if azione == 'chiudi':
            x.chiuso_il, x.esito = datetime.now(), 'SCARTATO'
        elif azione == 'riapri':
            x.chiuso_il, x.esito = None, ''
        elif azione == 'elimina':
            s.delete(x)
        else:
            abort(404)
        s.commit()
    return redirect(destinazione_sicura(request.form.get('torna'), url_for('segreteria.da_confermare')))


@bp.route('/da-confermare/prenota', methods=['POST'])
def prenota_appunti():
    """Piu' appunti in agenda insieme, nella stanza scelta: la giornata della
    dott.ssa arrivata senza stanza diventa un clic, appena si sa quale."""
    s = ses()
    torna = destinazione_sicura(request.form.get('torna'), url_for('segreteria.da_confermare'))
    scelti = [s.get(Appunto, intero(v)) for v in request.form.getlist('scelti')]
    scelti = [x for x in scelti if x is not None and x.aperto]
    stanza = s.get(Risorsa, intero(request.form.get('risorsa')))
    if not scelti:
        flash('Nessun appunto scelto.', 'errore')
        return redirect(torna)
    fatti, rimasti, notizie, avvisi = 0, [], [], []
    import invii
    with _lucchetto:
        try:
            for x in scelti:
                r = stanza or x.risorsa
                medico = x.operatore
                prest = x.prestazione
                if r is None or medico is None or x.giorno is None or x.ora is None:
                    rimasti.append('%s: %s' % (x.chi or x.testo[:40], 'mancano ' + ', '.join(
                        n for n, v in (('la stanza', r), ('il medico', medico), ('il giorno', x.giorno),
                                       ('l\'ora', x.ora)) if v is None)))
                    continue
                inizio = datetime.combine(x.giorno, x.ora)
                minuti = x.durata_min or (prest.durata_min if prest else 30)
                fine = inizio + timedelta(minutes=minuti)
                motivi = servizi.conflitti(s, r.id, medico.id, inizio, fine)
                if motivi:
                    rimasti.append('%s alle %s: %s' % (x.chi or x.testo[:40], x.ora.strftime('%H:%M'), motivi[0]))
                    continue
                paz = x.paziente or pazienti.trova_o_crea(s, None, x.cognome, x.nome, x.telefono)
                a = Appuntamento(risorsa_id=r.id, operatore_id=medico.id, paziente_id=paz.id if paz else None,
                                 prestazione_id=prest.id if prest else None, inizio=inizio, fine=fine,
                                 stato='PRENOTATO', note=x.note or '')
                s.add(a)
                s.flush()
                servizi.registra(s, 'Appuntamento', a.id, 'CREATO', 'da appunto: %s %s' % (r.nome, inizio))
                x.chiuso_il, x.esito, x.appuntamento_id = datetime.now(), 'PRENOTATO', a.id
                if x.risorsa_id is None:
                    x.risorsa_id = r.id
                # le email automatiche, come per una prenotazione dal modulo
                try:
                    invii.dopo_salvataggio(s, a, notizie, avvisi)
                except Exception as e:
                    logging.exception('email automatiche dell\'appuntamento %s', a.id)
                    avvisi.append('Email automatica non preparata (%s): si può mandare dalla pagina '
                                  'dell\'appuntamento.' % e)
                fatti += 1
            s.commit()
        except IntegrityError:
            # la rete di sicurezza del database: tutto o niente, come prima del clic
            s.rollback()
            flash('Nessun appunto messo in agenda: una delle fasce risulta già presa. '
                  'Ricaricare la pagina e riprovare.', 'errore')
            return redirect(torna)
    if fatti:
        flash('%d appuntament%s messi in agenda.' % (fatti, 'o' if fatti == 1 else 'i'), 'ok')
    if notizie:
        invii.sveglia()
    # lo stesso avviso per piu' appuntamenti si dice una volta
    for m in list(dict.fromkeys(notizie))[:10]:
        flash(m, 'ok')
    for m in list(dict.fromkeys(avvisi))[:10]:
        flash(m, 'avviso')
    for m in rimasti[:20]:
        flash('Non messo in agenda: ' + m, 'errore')
    return redirect(torna)


# ================================================================ notifiche
def notifiche_di(s, struttura_id, adesso=None):
    """Le notifiche a scomparsa: cose da fare scadute, conferme del prossimo
    giorno, giornate da chiudere, backup. Ognuna ha una chiave che cambia
    quando cambia il contenuto: chiusa una volta, ricompare solo se c'e'
    qualcosa di nuovo."""
    adesso = adesso or datetime.now()
    oggi = adesso.date()
    uscita = []
    for x in s.scalars(select(Attivita).where(Attivita.fatto_il == None, Attivita.per_il <= oggi)
                       .order_by(Attivita.per_il, Attivita.id).limit(5)):
        chi = x.paziente.etichetta if x.paziente else ''
        uscita.append({
            'chiave': 'cosa-%d-%s' % (x.id, x.per_il.isoformat()),
            'titolo': 'Da fare' + (' (dal %s)' % x.per_il.strftime('%d/%m') if x.per_il < oggi else ''),
            'testo': x.testo + (' — %s' % chi if chi else ''),
            'link': url_for('pazienti.scheda', pid=x.paziente_id) if x.paziente_id else url_for('segreteria.cose_da_fare'),
            'azioni': [{'etichetta': 'Fatto', 'url': url_for('segreteria.cosa_fatta', xid=x.id, azione='fatto')},
                       {'etichetta': 'Domani', 'url': url_for('segreteria.cosa_fatta', xid=x.id, azione='rimanda')}],
            'livello': 'normale'})
    vicini = [x for x in appunti_aperti(s, struttura_id) if x.giorno and x.giorno <= oggi + timedelta(days=1)]
    if vicini:
        passati = [x for x in vicini if x.giorno < oggi]
        uscita.append({
            'chiave': 'appunti-%s-%s' % (oggi.isoformat(), '-'.join(str(x.id) for x in vicini[:20])),
            'titolo': 'Da confermare',
            'testo': '%d appunt%s da confermare fino a domani%s.' % (
                len(vicini), 'o' if len(vicini) == 1 else 'i',
                (' (%d dei giorni scorsi)' % len(passati)) if passati else ''),
            'link': url_for('segreteria.da_confermare'), 'azioni': [], 'livello': 'normale'})
    if struttura_id:
        prossimo = servizi.prossimo_giorno_con_appuntamenti(s, oggi, struttura_id)
        if prossimo and prossimo > oggi:
            da_confermare = len(servizi.elenco_giorno(s, prossimo, struttura_id, ('PRENOTATO',)))
            if da_confermare:
                uscita.append({
                    'chiave': 'conferme-%s-%d' % (prossimo.isoformat(), da_confermare),
                    'titolo': 'Conferme',
                    'testo': '%s: %d appuntament%s da confermare.' % (
                        giorno_breve(prossimo).capitalize(), da_confermare, 'o' if da_confermare == 1 else 'i'),
                    'link': url_for('viste.conferme', data=prossimo.isoformat(), struttura=struttura_id),
                    'azioni': [], 'livello': 'normale'})
        arretrati = giorni_da_chiudere(s, struttura_id, adesso)
        if arretrati:
            primo = min(arretrati)
            n = sum(arretrati.values())
            uscita.append({
                'chiave': 'chiudere-%s-%d' % (oggi.isoformat(), n),
                'titolo': 'Giornate da chiudere',
                'testo': '%d appuntament%s dei giorni scorsi ancora da segnare arrivat%s o non presentat%s.' % (
                    n, 'o' if n == 1 else 'i', 'o' if n == 1 else 'i', 'o' if n == 1 else 'i'),
                'link': url_for('segreteria.chiusura', iso=primo.isoformat(), struttura=struttura_id),
                'azioni': [], 'livello': 'normale'})
        if adesso.hour >= 18:
            aperti = aperti_del_giorno(s, oggi, struttura_id, adesso)
            if aperti:
                uscita.append({
                    'chiave': 'chiudi-oggi-%s-%d' % (oggi.isoformat(), len(aperti)),
                    'titolo': 'Fine giornata',
                    'testo': '%d appuntament%s di oggi da chiudere.' % (len(aperti), 'o' if len(aperti) == 1 else 'i'),
                    'link': url_for('segreteria.chiusura', iso=oggi.isoformat(), struttura=struttura_id),
                    'azioni': [], 'livello': 'normale'})
    if struttura_id:
        uscita += sala.notifiche(s, struttura_id, adesso)
    import invii
    uscita += invii.notifiche(s, adesso)
    import aggiornamenti
    uscita += aggiornamenti.notifiche(s, adesso)
    allarme = backup.allarme(adesso)
    if allarme:
        uscita.append({'chiave': 'backup-%s' % oggi.isoformat(), 'titolo': 'Backup', 'testo': allarme,
                       'link': url_for('viste.impostazioni'), 'azioni': [], 'livello': 'errore'})
    # 1.11: quello che il programma ha riparato da solo, e i problemi di adesso
    try:
        import autoripara
        uscita += autoripara.notifiche(adesso, url_for('autoriparazione'))
    except Exception:
        logging.exception('notifiche dell\'autoriparazione')
    return uscita


@bp.route('/notifiche.json')
def notifiche():
    s = ses()
    sid = intero(request.args.get('struttura'))
    if not sid or s.get(Struttura, sid) is None:
        prima = s.scalars(select(Struttura.id).where(Struttura.attiva == True).order_by(Struttura.id)).first()
        sid = prima or 0
    return json_sicuro(notifiche_di(s, sid))


# ========================================================== ricerca rapida
MESI_NOMI = {m: i + 1 for i, m in enumerate(servizi.MESI)}
MESI_NOMI.update({m[:3]: i + 1 for i, m in enumerate(servizi.MESI)})
GIORNI_NOMI = {}
for _i, _g in enumerate(servizi.GIORNI):
    GIORNI_NOMI[_g] = _i
    GIORNI_NOMI[_g.replace('ì', 'i')] = _i
    GIORNI_NOMI[_g[:3]] = _i


def interpreta_data(testo, oggi=None):
    """'oggi', 'domani', 'ieri', 'lunedì' (il prossimo, oggi compreso),
    '24/9', '24/09/26', '24-09-2026', '24 settembre', '24 set 2027'.
    None se non e' una data."""
    oggi = oggi or date.today()
    t = ' '.join((testo or '').strip().lower().split())
    if not t:
        return None
    if t in ('oggi',):
        return oggi
    if t == 'domani':
        return oggi + timedelta(days=1)
    if t == 'dopodomani':
        return oggi + timedelta(days=2)
    if t == 'ieri':
        return oggi - timedelta(days=1)
    if t in GIORNI_NOMI:
        return oggi + timedelta(days=(GIORNI_NOMI[t] - oggi.weekday()) % 7)
    m = re.fullmatch(r'(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2}|\d{4}))?', t)
    if m:
        giorno, mese = int(m.group(1)), int(m.group(2))
        anno = m.group(3)
    else:
        m = re.fullmatch(r'(\d{1,2}) ([a-zì]+)(?: (\d{4}))?', t)
        if not m or m.group(2) not in MESI_NOMI:
            return None
        giorno, mese, anno = int(m.group(1)), MESI_NOMI[m.group(2)], m.group(3)
    if anno is None:
        anno = oggi.year
    else:
        anno = int(anno) + (2000 if len(anno) == 2 else 0)
    try:
        g = date(anno, mese, giorno)
    except ValueError:
        return None
    return g if PRIMA <= g <= ULTIMA else None


@bp.route('/cerca-tutto.json')
def cerca_tutto():
    s = ses()
    q = (request.args.get('q') or '').strip()[:80]
    sid = intero(request.args.get('struttura')) or None
    uscita = {'giorno': None, 'pazienti': [], 'medici': [], 'prestazioni': []}
    g = interpreta_data(q)
    if g is not None:
        uscita['giorno'] = {'etichetta': servizi.etichetta_giorno(g),
                            'url': url_for('giorno', iso=g.isoformat(), struttura=sid)}
    if len(q) >= 2:
        for p in pazienti.cerca(s, q, limite=8):
            uscita['pazienti'].append({'etichetta': p.etichetta, 'telefono': p.telefono or '',
                                       'url': url_for('pazienti.scheda', pid=p.id)})
        chiave = pazienti.semplifica(q)
        for o in s.scalars(select(Operatore).where(Operatore.attivo == True)):
            if chiave and chiave in pazienti.semplifica(o.etichetta):
                uscita['medici'].append({'etichetta': o.etichetta,
                                         'url': url_for('viste.settimana', iso=date.today().isoformat(),
                                                        medico=o.id, struttura=sid)})
        uscita['medici'] = uscita['medici'][:4]
        # in quale struttura del gruppo si fa (Dove si fa), se il database delle prestazioni c'e':
        # un guasto qui non deve fermare la ricerca dei pazienti
        try:
            import dovesifa
            uscita['prestazioni'] = dovesifa.per_ricerca_rapida(s, q)
        except Exception:
            logging.exception('ricerca rapida: prestazioni non cercate')
    return json_sicuro(uscita)


# ========================================================= agenda del medico
def testo_agenda(o, g, apps):
    righe = ['Agenda di %s — %s' % (o.etichetta, servizi.etichetta_giorno(g)), '']
    for a in apps:
        righe.append('%s-%s  %s  %s%s%s' % (
            a.inizio.strftime('%H:%M'), a.fine.strftime('%H:%M'),
            a.risorsa.nome if a.risorsa else '',
            a.paziente.etichetta if a.paziente else '(senza paziente)',
            ' — %s' % a.prestazione.nome if a.prestazione else '',
            ' (%s)' % a.note.strip() if (a.note or '').strip() else ''))
    if not apps:
        righe.append('Nessun appuntamento.')
    return '\n'.join(righe)


@bp.route('/agenda-medico/<iso>')
def agenda_medico(iso):
    """Il foglio del giorno per ciascun medico: da stampare o mandare per
    email. Tutte le strutture: il medico e' la stessa persona ovunque."""
    s = ses()
    g = data_da(iso)
    st, strutture = struttura_scelta(s)
    scelto = s.get(Operatore, intero(request.args.get('medico'))) if request.args.get('medico') else None
    apps = servizi.elenco_giorno(s, g, None, STATI_ATTIVI)
    per_medico = {}
    for a in apps:
        if scelto is None or a.operatore_id == scelto.id:
            per_medico.setdefault(a.operatore_id, []).append(a)
    fogli = []
    for oid, lista in sorted(per_medico.items(), key=lambda x: (x[1][0].operatore.cognome, x[0])):
        o = lista[0].operatore
        testo = testo_agenda(o, g, lista)
        mail = None
        if o.email and pazienti.email_valida(o.email):
            mail = indirizzo_mail(o.email, 'Agenda del %s' % g.strftime('%d/%m/%Y'), testo,
                                  '… (l\'agenda completa è nel foglio da stampare)')
        fogli.append({'operatore': o, 'apps': lista, 'testo': testo, 'mail': mail})
    if scelto is not None and not fogli:
        fogli.append({'operatore': scelto, 'apps': [], 'testo': testo_agenda(scelto, g, []), 'mail': None})
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    return render_template('agenda_medico.html', fogli=fogli, g=g, scelto=scelto, medici=medici,
                           st=st, sid=st.id if st else None, titolo=servizi.etichetta_giorno(g),
                           ieri=(g - timedelta(days=1)).isoformat(),
                           domani=(g + timedelta(days=1)).isoformat(), adesso=datetime.now())
