# -*- coding: utf-8 -*-
"""Documenti del paziente (impegnative, referti, consensi firmati: PDF o
foto) e moduli da stampare compilati con i dati dell'appuntamento.

I file stanno nel database: il backup resta un file solo e porta con se'
anche i documenti. Si accettano solo PDF, JPEG e PNG, riconosciuti dal
contenuto e non dal nome."""
import re
import threading
from datetime import date, datetime, timedelta
from io import BytesIO

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   send_file)
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from modelli import Paziente, Appuntamento, Prestazione, Documento, ModuloStampa
import servizi
import pazienti
from comune import intero

bp = Blueprint('documenti', __name__)
_fornitore = None
_lucchetto = threading.Lock()

MASSIMO_DOCUMENTO = 10 * 1024 * 1024
FIRME = {'application/pdf': b'%PDF-', 'image/jpeg': b'\xff\xd8\xff', 'image/png': b'\x89PNG\r\n\x1a\n'}
ESTENSIONE = {'application/pdf': '.pdf', 'image/jpeg': '.jpg', 'image/png': '.png'}


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


def tipo_del_contenuto(dati):
    for tipo, firma in FIRME.items():
        if dati.startswith(firma):
            return tipo
    return None


def nome_pulito(nome, tipo):
    """Il nome del file com'era, senza percorso e senza caratteri che
    rompono l'intestazione di scaricamento."""
    nome = re.split(r'[\\/]', nome or '')[-1]
    nome = re.sub(r'[\x00-\x1f"<>|:*?]', '', nome).strip(' .') or 'documento'
    base = nome[:100]
    if not base.lower().endswith(ESTENSIONE[tipo]) and not (tipo == 'image/jpeg' and base.lower().endswith('.jpeg')):
        base += ESTENSIONE[tipo]
    return base


# ============================================================== documenti
@bp.route('/pazienti/<int:pid>/documenti', methods=['POST'])
def carica_documento(pid):
    s = ses()
    p = s.get(Paziente, pid)
    if p is None:
        abort(404)
    torna = url_for('pazienti.scheda', pid=p.id) + '#documenti'
    f = request.files.get('file')
    if f is None or not f.filename:
        flash('Scegliere un file da allegare.', 'errore')
        return redirect(torna)
    dati = f.read(MASSIMO_DOCUMENTO + 1)
    if len(dati) > MASSIMO_DOCUMENTO:
        flash('Il documento supera 10 MB: per una foto conviene ridurla, per un PDF scansionarlo a risoluzione più bassa.', 'errore')
        return redirect(torna)
    if not dati:
        flash('Il file è vuoto.', 'errore')
        return redirect(torna)
    tipo = tipo_del_contenuto(dati)
    if tipo is None:
        flash('Si possono allegare solo PDF, JPG e PNG.', 'errore')
        return redirect(torna)
    descrizione = ' '.join((request.form.get('descrizione') or '').split())[:200]
    aid = intero(request.form.get('appuntamento_id'))
    a = s.get(Appuntamento, aid) if aid else None
    with _lucchetto:
        d = Documento(paziente_id=p.id, appuntamento_id=a.id if a is not None and a.paziente_id == p.id else None,
                      nome=nome_pulito(f.filename, tipo), descrizione=descrizione, tipo=tipo,
                      dimensione=len(dati), dati=dati)
        s.add(d)
        s.flush()
        servizi.registra(s, 'Documento', d.id, 'CARICATO', '%s: %s' % (p.etichetta, d.nome))
        s.commit()
    flash('Documento allegato: %s.' % d.nome, 'ok')
    return redirect(torna)


def documenti_di(s, paziente_id):
    return s.scalars(select(Documento).where(Documento.paziente_id == paziente_id)
                     .order_by(Documento.caricato_il.desc(), Documento.id.desc())).all()


@bp.route('/documenti/<int:did>')
def mostra_documento(did):
    s = ses()
    d = s.get(Documento, did)
    if d is None or d.tipo not in FIRME:
        abort(404)
    risposta = send_file(BytesIO(d.dati or b''), mimetype=d.tipo, download_name=d.nome,
                         as_attachment=request.args.get('scarica') == '1', max_age=0)
    risposta.headers['X-Content-Type-Options'] = 'nosniff'
    if d.tipo != 'application/pdf':
        # un'immagine aperta da sola non deve poter caricare o eseguire niente.
        # Al PDF non si mette: il visualizzatore di Chrome ha regole sue e gira isolato
        risposta.headers['Content-Security-Policy'] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    return risposta


@bp.route('/documenti/<int:did>/elimina', methods=['POST'])
def elimina_documento(did):
    s = ses()
    d = s.get(Documento, did)
    if d is None:
        abort(404)
    pid = d.paziente_id
    with _lucchetto:
        servizi.registra(s, 'Documento', d.id, 'ELIMINATO', d.nome)
        s.delete(d)
        s.commit()
    flash('Documento eliminato.', 'ok')
    return redirect(url_for('pazienti.scheda', pid=pid) + '#documenti')


# ================================================================= moduli
SEGNAPOSTO_MODULI = ['paziente', 'cognome', 'nome', 'data_nascita', 'luogo_nascita', 'sesso', 'codice_fiscale',
                     'indirizzo_paziente', 'telefono', 'data', 'giorno', 'ora', 'medico', 'prestazione', 'stanza',
                     'struttura', 'indirizzo', 'telefono_struttura', 'oggi', 'preparazione']

ESEMPIO = """Gentile {paziente},

il suo appuntamento per {prestazione} è fissato per {giorno} alle ore {ora} presso {struttura}{indirizzo}, con {medico}.

Da {giorno-3}: seguire le indicazioni ricevute dal medico.
Il giorno prima, {giorno-1}: ...
Il giorno dell'esame: presentarsi in accettazione 15 minuti prima, con documento d'identità, tessera sanitaria ed eventuali esami precedenti.

Per qualsiasi dubbio può chiamare il {telefono_struttura}.

Testo di esempio: va adattato e fatto verificare dal medico prima di usarlo."""

# maiuscole o minuscole: un testo preparato in Word ha spesso {Paziente} a inizio frase
VARIAZIONE = re.compile(r'\{(data|giorno)([+-])(\d{1,3})\}', re.I)


def compila(testo, a, adesso=None):
    """Il testo del modulo con i dati dell'appuntamento. {data-3} e
    {giorno-3} sono la data tre giorni prima dell'appuntamento, come
    '28/09/2026' e 'lunedì 28 settembre'. Un segnaposto sconosciuto resta
    com'e': si vede subito che va corretto."""
    adesso = adesso or datetime.now()
    p = a.paziente
    st = a.risorsa.struttura if a.risorsa else None

    def giorno_lungo(g):
        return '%s %d %s' % (servizi.GIORNI[g.weekday()], g.day, servizi.MESI[g.month - 1])

    valori = {
        'paziente': p.etichetta if p else '',
        'cognome': p.cognome if p else '',
        'nome': (p.nome or '') if p else '',
        'data_nascita': p.data_nascita.strftime('%d/%m/%Y') if p and p.data_nascita else '',
        'codice_fiscale': (p.codice_fiscale or '') if p else '',
        'luogo_nascita': pazienti.testo_luogo_paziente(p) if p else '',
        'sesso': (getattr(p, 'sesso', '') or '') if p else '',
        'indirizzo_paziente': (getattr(p, 'indirizzo', '') or '') if p else '',
        'telefono': (p.telefono or '') if p else '',
        'data': a.inizio.strftime('%d/%m/%Y'),
        'giorno': giorno_lungo(a.inizio.date()),
        'ora': a.inizio.strftime('%H:%M'),
        'medico': a.operatore.etichetta if a.operatore else '',
        'prestazione': a.prestazione.nome if a.prestazione else '',
        'stanza': a.risorsa.nome if a.risorsa else '',
        'struttura': st.nome if st else '',
        'indirizzo': (', ' + st.indirizzo.strip()) if st and (st.indirizzo or '').strip() else '',
        'telefono_struttura': (st.telefono or '') if st else '',
        'oggi': adesso.strftime('%d/%m/%Y'),
        'preparazione': (a.prestazione.preparazione or '') if a.prestazione else '',
    }

    def variazione(m):
        giorni = int(m.group(3)) * (1 if m.group(2) == '+' else -1)
        g = a.inizio.date() + timedelta(days=giorni)
        return g.strftime('%d/%m/%Y') if m.group(1).lower() == 'data' else giorno_lungo(g)

    testo = VARIAZIONE.sub(variazione, testo or '')
    return re.sub(r'\{([A-Za-z_]+)\}', lambda m: valori.get(m.group(1).lower(), m.group(0)), testo)


def moduli_per(s, a):
    """I moduli che valgono per la prestazione dell'appuntamento, piu' quelli
    per tutte."""
    return s.scalars(select(ModuloStampa).where(
        (ModuloStampa.prestazione_id == None) | (ModuloStampa.prestazione_id == a.prestazione_id))
        .order_by(ModuloStampa.nome)).all()


@bp.route('/moduli')
def moduli():
    s = ses()
    return render_template('moduli.html', moduli=s.scalars(select(ModuloStampa).order_by(ModuloStampa.nome)).all(),
                           segnaposto=SEGNAPOSTO_MODULI, sezione='impostazioni')


@bp.route('/moduli/nuovo', methods=['GET', 'POST'])
@bp.route('/moduli/<int:mid>', methods=['GET', 'POST'])
def modulo(mid=None):
    s = ses()
    m = s.get(ModuloStampa, mid) if mid else None
    if mid and m is None:
        abort(404)
    prestazioni = s.scalars(select(Prestazione).order_by(Prestazione.nome)).all()
    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and m is not None:
                s.delete(m)
                s.commit()
                flash('Modulo eliminato.', 'ok')
                return redirect(url_for('documenti.moduli'))
            if request.form.get('azione') == 'esempio' and m is None:
                nome, n = 'Istruzioni per l\'appuntamento (esempio)', 2
                while s.scalars(select(ModuloStampa).where(ModuloStampa.nome == nome)).first():
                    nome = 'Istruzioni per l\'appuntamento (esempio %d)' % n
                    n += 1
                m = ModuloStampa(nome=nome, testo=ESEMPIO, firma=False)
                s.add(m)
                s.commit()
                flash('Creato un modulo di esempio: va adattato prima di usarlo.', 'ok')
                return redirect(url_for('documenti.modulo', mid=m.id))
            nome = ' '.join((request.form.get('nome') or '').split())
            testo = (request.form.get('testo') or '').replace('\r\n', '\n').strip()
            pid = intero(request.form.get('prestazione'))
            errori = []
            if not nome or len(nome) > 80:
                errori.append('Nome: obbligatorio, al massimo 80 caratteri.')
            if not testo or len(testo) > 20000:
                errori.append('Testo: obbligatorio, al massimo 20000 caratteri.')
            if pid and s.get(Prestazione, pid) is None:
                errori.append('Prestazione non valida.')
            if not errori:
                doppio = s.scalars(select(ModuloStampa).where(
                    func.lower(ModuloStampa.nome) == nome.lower(),
                    ModuloStampa.id != (m.id if m else -1))).first()
                if doppio:
                    errori.append('Esiste già un modulo con questo nome.')
            if errori:
                for e in errori:
                    flash(e, 'errore')
                return render_template('modulo.html', m=m, modulo=request.form, prestazioni=prestazioni,
                                       segnaposto=SEGNAPOSTO_MODULI, sezione='impostazioni')
            if m is None:
                m = ModuloStampa()
                s.add(m)
            m.nome, m.testo, m.prestazione_id = nome, testo, pid or None
            m.firma = request.form.get('firma') in ('1', 'on')
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                flash('Esiste già un modulo con questo nome.', 'errore')
                return redirect(request.url)
            flash('Modulo salvato: %s.' % m.nome, 'ok')
            return redirect(url_for('documenti.moduli'))
    return render_template('modulo.html', m=m, modulo=None, prestazioni=prestazioni,
                           segnaposto=SEGNAPOSTO_MODULI, sezione='impostazioni')


@bp.route('/appuntamento/<int:aid>/modulo/<int:mid>')
def stampa_modulo(aid, mid):
    s = ses()
    a = s.get(Appuntamento, aid)
    m = s.get(ModuloStampa, mid)
    if a is None or m is None:
        abort(404)
    st = a.risorsa.struttura if a.risorsa else None
    return render_template('stampa_modulo.html', a=a, m=m, st=st, sid=st.id if st else None,
                           testo=compila(m.testo, a))
