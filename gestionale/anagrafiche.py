# -*- coding: utf-8 -*-
"""Anagrafiche: medici, turni, stanze, prestazioni e nome della struttura.

Al primo avvio il programma crea stanze e prestazioni, ma medici e turni
esistono solo se qualcuno li inserisce: senza questa parte il gestionale
appena installato non permetterebbe di prenotare niente.

Ogni regola e' controllata qui sul server. Il modulo nel browser aiuta a
compilare, ma quello che arriva va sempre verificato.
"""
import re
import threading
from datetime import datetime, date, timedelta, time

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort)
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError

from modelli import (Struttura, Risorsa, Operatore, Prestazione, Turno,
                     Appuntamento, Assenza, Chiusura, Appunto, RegolaEmail, COLORE_PREDEFINITO, PASSI_AMMESSI,
                     TariffarioMedico, VoceTariffario,
                     PASSI_TURNO, STATI_ATTIVI)
import servizi
from comune import PALETTE, PRIMA, ULTIMA, colore_libero, destinazione_sicura      # PALETTE: la leggono anche le prove
import marchio
import calendario

bp = Blueprint('anagrafiche', __name__, url_prefix='/anagrafiche')
_fornitore = None
_lucchetto = threading.Lock()

TIPI_STANZA = [('AMBULATORIO', 'Ambulatorio'),
               ('SALA_OPERATORIA', 'Sala operatoria'),
               ('ENDOSCOPIA', 'Sala endoscopia'),
               ('ALTRO', 'Altro')]
ETICHETTA_TIPO = dict(TIPI_STANZA)

COLORE = re.compile(r'#[0-9A-Fa-f]{6}')


def collega(app, fornitore_sessione, lucchetto=None):
    """Registra le pagine sull'applicazione. La sessione arriva da fuori per
    usare la stessa, una per thread, del resto del programma."""
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ====================================================== lettura dei moduli
class Modulo:
    """Legge un modulo inviato e raccoglie tutti gli errori, non solo il
    primo: chi compila deve poterli correggere in una volta sola."""

    def __init__(self, dati):
        self.dati = dati
        self.errori = []

    def testo(self, nome, etichetta, massimo, richiesto=False):
        v = (self.dati.get(nome) or '').strip()
        if richiesto and not v:
            self.errori.append('%s: campo obbligatorio.' % etichetta)
        elif len(v) > massimo:
            self.errori.append('%s: al massimo %d caratteri.' % (etichetta, massimo))
        return v

    def intero(self, nome, etichetta, minimo, massimo):
        grezzo = (self.dati.get(nome) or '').strip()
        try:
            v = int(grezzo)
        except ValueError:
            self.errori.append('%s: serve un numero intero.' % etichetta)
            return None
        if not minimo <= v <= massimo:
            self.errori.append('%s: deve stare fra %d e %d.' % (etichetta, minimo, massimo))
            return None
        return v

    def ora(self, nome, etichetta):
        grezzo = (self.dati.get(nome) or '').strip()
        for formato in ('%H:%M', '%H:%M:%S'):
            try:
                return datetime.strptime(grezzo, formato).time()
            except ValueError:
                pass
        self.errori.append('%s: ora non valida.' % etichetta)
        return None

    def data(self, nome, etichetta, richiesta=True):
        grezzo = (self.dati.get(nome) or '').strip()
        if not grezzo:
            if richiesta:
                self.errori.append('%s: campo obbligatorio.' % etichetta)
            return None
        try:
            g = datetime.strptime(grezzo, '%Y-%m-%d').date()
        except ValueError:
            self.errori.append('%s: data non valida.' % etichetta)
            return None
        if not PRIMA <= g <= ULTIMA:
            self.errori.append('%s: data fuori dall\'intervallo ammesso.' % etichetta)
            return None
        return g

    def scelta(self, nome, etichetta, ammessi):
        v = self.dati.get(nome)
        if v not in ammessi:
            self.errori.append('%s: scelta non valida.' % etichetta)
            return None
        return v

    def spunta(self, nome):
        return self.dati.get(nome) in ('1', 'on', 'true')


def campo(nome, etichetta, tipo='text', valore='', **altro):
    c = dict(nome=nome, etichetta=etichetta, tipo=tipo, valore=valore)
    c.update(altro)
    return c


def scheda(titolo, campi, errori=None, eliminabile=False, conferma='', salva='Salva',
           nota='', sid=None, elenco_extra=None):
    for e in errori or []:
        flash(e, 'errore')
    return render_template('scheda.html', titolo=titolo, campi=campi,
                           eliminabile=eliminabile, conferma_elimina=conferma,
                           etichetta_salva=salva, nota=nota, sid=sid,
                           con_file=any(x['tipo'] == 'file' for x in campi),
                           elenco_extra=elenco_extra, sezione='anagrafiche')


def carica(modello, ident):
    """None per un elemento nuovo, 404 per un id che non esiste."""
    if ident is None:
        return None
    oggetto = ses().get(modello, ident)
    if oggetto is None:
        abort(404)
    return oggetto


def salva_e_torna(s, oggetto, entita, messaggio, avviso=None, torna=None):
    """'torna': la pagina interna da cui si era partiti (1.12: la pianificazione
    degli ambulatori); senza, l'elenco delle anagrafiche."""
    try:
        s.flush()
        servizi.registra(s, entita, oggetto.id, 'SALVATO', messaggio)
        s.commit()
    except IntegrityError:
        s.rollback()
        flash('Salvataggio non riuscito: esiste già un elemento con lo stesso nome.', 'errore')
        return redirect(request.url)
    flash(messaggio, 'ok')
    if avviso:
        flash(avviso, 'avviso')
    return redirect(destinazione_sicura(torna, url_for('anagrafiche.elenco')))


def usi(s, riferimenti, ident):
    """Quante righe di altre tabelle puntano all'elemento: con anche un solo
    uso non lo si puo' eliminare senza lasciare dati orfani."""
    trovati = []
    for modello, colonna, singolare, plurale in riferimenti:
        n = s.scalar(select(func.count()).select_from(modello).where(colonna == ident))
        if n:
            trovati.append('%d %s' % (n, singolare if n == 1 else plurale))
    return trovati


def elimina(s, oggetto, entita, riferimenti, descrizione, eliminato, alternativa,
            femminile=False):
    trovati = usi(s, riferimenti, oggetto.id)
    if trovati:
        flash('%s non si può eliminare: è %s da %s. %s'
              % (descrizione, 'usata' if femminile else 'usato', ' e '.join(trovati), alternativa),
              'errore')
        return redirect(request.url)
    servizi.registra(s, entita, oggetto.id, 'ELIMINATO', descrizione)
    s.delete(oggetto)
    s.commit()
    flash(eliminato, 'ok')
    return redirect(url_for('anagrafiche.elenco'))


# ================================================================ elenco
@bp.route('')
def elenco():
    s = ses()
    return render_template(
        'anagrafiche.html',
        strutture=s.scalars(select(Struttura).order_by(Struttura.id)).all(),
        risorse=s.scalars(select(Risorsa).order_by(
            Risorsa.struttura_id, Risorsa.ordine, Risorsa.nome)).all(),
        operatori=s.scalars(select(Operatore).order_by(
            Operatore.attivo.desc(), Operatore.cognome, Operatore.nome)).all(),
        turni=[t for t in s.scalars(select(Turno).order_by(
            Turno.giorno_settimana, Turno.ora_inizio)) if not servizi.e_di_un_giorno(t)],
        # i turni di un giorno: quelli da oggi in poi, piu' l'ultima settimana
        turni_giorno=s.scalars(select(Turno).where(
            Turno.valido_a != None, Turno.valido_da == Turno.valido_a,
            Turno.valido_a >= date.today() - timedelta(days=7))
            .order_by(Turno.valido_da, Turno.ora_inizio)).all(),
        assenze=s.scalars(select(Assenza).where(Assenza.al >= date.today() - timedelta(days=7))
                          .order_by(Assenza.dal)).all(),
        chiusure=s.scalars(select(Chiusura).where(Chiusura.al >= date.today() - timedelta(days=7))
                           .order_by(Chiusura.dal)).all(),
        prestazioni=s.scalars(select(Prestazione).order_by(Prestazione.nome)).all(),
        giorni=servizi.GIORNI, tipi=ETICHETTA_TIPO, oggi=date.today(),
        nome_iniziale=servizi.NOME_INIZIALE, sezione='anagrafiche')


# ================================================================ medici
@bp.route('/medici/nuovo', methods=['GET', 'POST'])
@bp.route('/medici/<int:oid>', methods=['GET', 'POST'])
def medico(oid=None):
    s = ses()
    o = carica(Operatore, oid)
    titolo = 'Modifica medico' if o else 'Nuovo medico'
    v = request.form if request.method == 'POST' else None

    def campi(errore=False):
        dati = v if errore else None
        return [
            campo('cognome', 'Cognome', valore=dati.get('cognome') if dati else (o.cognome if o else ''),
                  richiesto=True, massimo=60),
            campo('nome', 'Nome', valore=dati.get('nome') if dati else (o.nome if o else ''),
                  massimo=60),
            campo('specialita', 'Specialità', valore=dati.get('specialita') if dati else (o.specialita if o else ''),
                  massimo=60),
            campo('email', 'Email', tipo='email', valore=dati.get('email') if dati else ((o.email or '') if o else ''),
                  massimo=120, aiuto='Per mandargli la sua agenda del giorno.'),
            campo('telefono', 'Telefono', tipo='tel', valore=dati.get('telefono') if dati else ((o.telefono or '') if o else ''),
                  massimo=30),
            campo('colore', 'Colore nella griglia', tipo='color',
                  valore=dati.get('colore') if dati else (o.colore_sicuro if o else colore_libero(s))),
            campo('attivo', 'Attivo: compare nelle prenotazioni', tipo='checkbox',
                  valore=(dati.get('attivo') in ('1', 'on')) if dati else (o.attivo if o else True)),
        ]

    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and o:
                return elimina(
                    s, o, 'Operatore',
                    [(Appuntamento, Appuntamento.operatore_id, 'appuntamento', 'appuntamenti'),
                     (Turno, Turno.operatore_id, 'turno', 'turni'),
                     (Appunto, Appunto.operatore_id, 'appunto da confermare', 'appunti da confermare'),
                     (RegolaEmail, RegolaEmail.operatore_id, 'regola delle email automatiche',
                      'regole delle email automatiche'),
                     (TariffarioMedico, TariffarioMedico.operatore_id, 'tariffario', 'tariffari')],
                    'Il medico %s' % o.etichetta, 'Medico eliminato: %s.' % o.etichetta,
                    'Si può disattivare togliendo la spunta "Attivo".')
            m = Modulo(request.form)
            cognome = m.testo('cognome', 'Cognome', 60, richiesto=True)
            nome = m.testo('nome', 'Nome', 60)
            specialita = m.testo('specialita', 'Specialità', 60)
            email = m.testo('email', 'Email', 120) if 'email' in request.form else None
            telefono = m.testo('telefono', 'Telefono', 30) if 'telefono' in request.form else None
            if email:
                import pazienti
                if not pazienti.email_valida(email):
                    m.errori.append('Email: indirizzo non valido.')
            colore = (request.form.get('colore') or '').strip()
            if not COLORE.fullmatch(colore):
                m.errori.append('Colore: formato non valido.')
            attivo = m.spunta('attivo')
            if not m.errori:
                # due medici con lo stesso nome sarebbero indistinguibili nella griglia
                doppio = s.scalars(select(Operatore).where(
                    func.lower(Operatore.cognome) == cognome.lower(),
                    func.lower(func.coalesce(Operatore.nome, '')) == nome.lower(),
                    Operatore.id != (o.id if o else -1))).first()
                if doppio:
                    m.errori.append('Esiste già un medico %s: aggiungere il nome per distinguerli.'
                                    % doppio.etichetta)
            if m.errori:
                return scheda(titolo, campi(errore=True), m.errori, eliminabile=bool(o),
                              conferma='Eliminare questo medico?', elenco_extra=[email_del_medico(s, o), riquadro_tariffario(s, o)])
            if o is None:
                o = Operatore()
                s.add(o)
            o.cognome, o.nome, o.specialita = cognome, nome, specialita
            o.colore, o.attivo = colore.lower(), attivo
            if email is not None:
                o.email = email
            if telefono is not None:
                o.telefono = telefono
            return salva_e_torna(s, o, 'Operatore', 'Medico salvato: %s.' % o.etichetta)

    return scheda(titolo, campi(), eliminabile=bool(o), conferma='Eliminare questo medico?',
                  elenco_extra=[email_del_medico(s, o), riquadro_tariffario(s, o)])


def riquadro_tariffario(s, o):
    """Sotto la scheda del medico (1.12.6): il suo tariffario e se e' attivo."""
    import tariffari
    return tariffari.del_medico(s, o)


def email_del_medico(s, o):
    """Sotto la scheda del medico: le email automatiche dei suoi pazienti,
    per vederle e farne una nuova (ognuno puo' avere le sue informative)."""
    if o is None or o.id is None:
        return None
    import invii
    righe = [{'url': url_for('invii.regola', rid=r.id), 'testo': r.nome,
              'dettaglio': '' if r.attiva else 'spenta'} for r in invii.regole_del_medico(s, o.id)]
    return {'titolo': 'Email automatiche ai suoi pazienti',
            'nota': ('Partono da sole quando si prenota con questo medico; dove non ne ha una sua per la prestazione '
                     'parte quella per tutti i medici, se c\'è.') if righe else
                    ('Nessuna email sua: ai suoi pazienti partono quelle per tutti i medici, se ci sono. Se ha '
                     'un\'informativa diversa, gli si fa la sua.'),
            'righe': righe,
            'azione': {'url': url_for('invii.regola', medico=o.id), 'testo': 'Nuova email per questo medico'}}


# ================================================================ stanze
@bp.route('/stanze/nuova', methods=['GET', 'POST'])
@bp.route('/stanze/<int:rid>', methods=['GET', 'POST'])
def stanza(rid=None):
    s = ses()
    r = carica(Risorsa, rid)
    titolo = 'Modifica stanza' if r else 'Nuova stanza'
    strutture = s.scalars(select(Struttura).order_by(Struttura.id)).all()
    if not strutture:
        flash('Manca la struttura: chiudere e riaprire il programma per ricrearla.', 'errore')
        return redirect(url_for('anagrafiche.elenco'))
    v = request.form if request.method == 'POST' else None

    def struttura_proposta():
        # dalla griglia di una struttura senza stanze si arriva con ?struttura=
        grezzo = (request.args.get('struttura') or '').strip()
        richiesta = int(grezzo) if grezzo.isdigit() and len(grezzo) < 10 else 0
        return richiesta if any(x.id == richiesta for x in strutture) else strutture[0].id

    def prossimo_ordine():
        massimo = s.scalar(select(func.max(Risorsa.ordine)))
        return (massimo or 0) + 1

    def campi(errore=False):
        dati = v if errore else None
        return [
            campo('nome', 'Nome', valore=dati.get('nome') if dati else (r.nome if r else ''),
                  richiesto=True, massimo=60),
            campo('tipo', 'Tipo', tipo='select', opzioni=TIPI_STANZA,
                  valore=dati.get('tipo') if dati else (r.tipo if r else 'AMBULATORIO')),
            campo('struttura', 'Struttura', tipo='select',
                  opzioni=[(str(x.id), x.nome) for x in strutture],
                  valore=dati.get('struttura') if dati else str(r.struttura_id if r else struttura_proposta())),
            campo('ordine', 'Posizione nella griglia', tipo='number', minimo=0, massimo_n=999,
                  valore=dati.get('ordine') if dati else (r.ordine if r else prossimo_ordine()),
                  aiuto='Le colonne vanno da sinistra a destra in ordine crescente.'),
            campo('attiva', 'Attiva: compare nella griglia', tipo='checkbox',
                  valore=(dati.get('attiva') in ('1', 'on')) if dati else (r.attiva if r else True)),
        ]

    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and r:
                return elimina(
                    s, r, 'Risorsa',
                    [(Appuntamento, Appuntamento.risorsa_id, 'appuntamento', 'appuntamenti'),
                     (Turno, Turno.risorsa_id, 'turno', 'turni'),
                     (Appunto, Appunto.risorsa_id, 'appunto da confermare', 'appunti da confermare')],
                    'La stanza %s' % r.nome, 'Stanza eliminata: %s.' % r.nome,
                    'Si può disattivare togliendo la spunta "Attiva".', femminile=True)
            m = Modulo(request.form)
            nome = m.testo('nome', 'Nome', 60, richiesto=True)
            tipo = m.scelta('tipo', 'Tipo', [t for t, _ in TIPI_STANZA])
            sid = m.scelta('struttura', 'Struttura', [str(x.id) for x in strutture])
            ordine = m.intero('ordine', 'Posizione nella griglia', 0, 999)
            attiva = m.spunta('attiva')
            if not m.errori:
                doppia = s.scalars(select(Risorsa).where(
                    Risorsa.struttura_id == int(sid),
                    func.lower(Risorsa.nome) == nome.lower(),
                    Risorsa.id != (r.id if r else -1))).first()
                if doppia:
                    m.errori.append('Esiste già una stanza chiamata %s in questa struttura.' % doppia.nome)
            if not m.errori and r is not None and r.attiva and not attiva:
                # la griglia mostra solo le stanze attive: disattivandone una con
                # prenotazioni in arrivo, quelle prenotazioni sparirebbero dalla vista.
                # I disdetti non contano: disdire tutto e' proprio il modo di chiuderla
                da_oggi = datetime.combine(date.today(), datetime.min.time())
                future = s.scalar(select(func.count()).select_from(Appuntamento).where(
                    Appuntamento.risorsa_id == r.id, Appuntamento.inizio >= da_oggi,
                    Appuntamento.stato.in_(STATI_ATTIVI)))
                if future:
                    m.errori.append(
                        'La stanza ha %d %s da oggi in poi: spostarli prima di disattivarla, '
                        'altrimenti non si vedrebbero più nella griglia.'
                        % (future, 'appuntamento' if future == 1 else 'appuntamenti'))
            if m.errori:
                return scheda(titolo, campi(errore=True), m.errori, eliminabile=bool(r),
                              conferma='Eliminare questa stanza?')
            if r is None:
                r = Risorsa()
                s.add(r)
            r.nome, r.tipo, r.struttura_id = nome, tipo, int(sid)
            r.ordine, r.attiva = ordine, attiva
            return salva_e_torna(s, r, 'Risorsa', 'Stanza salvata: %s.' % r.nome)

    return scheda(titolo, campi(), eliminabile=bool(r), conferma='Eliminare questa stanza?')


# =========================================================== prestazioni
@bp.route('/prestazioni/nuova', methods=['GET', 'POST'])
@bp.route('/prestazioni/<int:pid>', methods=['GET', 'POST'])
def prestazione(pid=None):
    s = ses()
    p = carica(Prestazione, pid)
    titolo = 'Modifica prestazione' if p else 'Nuova prestazione'
    v = request.form if request.method == 'POST' else None

    def campi(errore=False):
        dati = v if errore else None
        return [
            campo('nome', 'Nome', valore=dati.get('nome') if dati else (p.nome if p else ''),
                  richiesto=True, massimo=80),
            campo('durata', 'Durata abituale in minuti', tipo='number', minimo=5, massimo_n=1440,
                  valore=dati.get('durata') if dati else (p.durata_min if p else 30),
                  aiuto='Proposta come durata del nuovo appuntamento, si può sempre cambiare.'),
            campo('campi_extra', 'Campi in più nella prenotazione', massimo=200,
                  valore=dati.get('campi_extra') if dati else (p.campi_extra if p else ''),
                  aiuto='Separati da virgole. Con il punto interrogativo finale il campo è una casella '
                        'sì/no. Esempio: Sedazione?, Anestesista, Preparazione consegnata?'),
            campo('preparazione', 'Indicazioni per il paziente', tipo='textarea', massimo=1000,
                  valore=dati.get('preparazione') if dati else (p.preparazione if p else ''),
                  aiuto='Finiscono sul promemoria stampato e nei messaggi. Esempio: digiuno da 6 ore.'),
            # 1.12.6: il prezzo anche qui, dove lo si cerca (lo stesso della pagina Listino)
            campo('tariffa', 'Prezzo di listino (€)', massimo=12,
                  valore=dati.get('tariffa') if dati else (p.tariffa_testo if p else ''),
                  aiuto='Si propone da solo nella prenotazione, se il medico non ha un suo tariffario (Cassa → Tariffari). '
                        'Vuoto: nessun prezzo. Esempio: 80 o 1.250,50.'),
        ]

    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and p:
                # le regole delle email tengono gli id in un elenco: si controlla a mano
                regole = [r.nome for r in s.scalars(select(RegolaEmail)) if p.id in r.id_prestazioni]
                if regole:
                    flash('La prestazione %s non si può eliminare: è usata dalle email automatiche (%s). '
                          'Toglierla prima da Configura → Email e WhatsApp, oppure rinominarla.'
                          % (p.nome, ', '.join(regole)), 'errore')
                    return redirect(request.url)
                return elimina(
                    s, p, 'Prestazione',
                    [(Appuntamento, Appuntamento.prestazione_id, 'appuntamento', 'appuntamenti'),
                     (Appunto, Appunto.prestazione_id, 'appunto da confermare', 'appunti da confermare'),
                     (VoceTariffario, VoceTariffario.prestazione_id, 'voce di un tariffario', 'voci dei tariffari')],
                    'La prestazione %s' % p.nome, 'Prestazione eliminata: %s.' % p.nome,
                    'Si può rinominare invece di eliminarla.', femminile=True)
            m = Modulo(request.form)
            nome = m.testo('nome', 'Nome', 80, richiesto=True)
            durata = m.intero('durata', 'Durata abituale in minuti', 5, 1440)
            # campi non inviati: restano com'erano
            campi_extra = m.testo('campi_extra', 'Campi in più', 200) if 'campi_extra' in request.form else None
            preparazione = m.testo('preparazione', 'Indicazioni per il paziente', 1000) \
                if 'preparazione' in request.form else None
            tariffa = None
            if 'tariffa' in request.form:
                import tariffari
                scritto = (request.form.get('tariffa') or '').strip()
                tariffa = tariffari.leggi_importo(scritto) if scritto else ''
                if tariffa is None:
                    m.errori.append('Prezzo di listino non valido: si scrive per esempio 80 o 1.250,50.')
            if not m.errori:
                doppia = s.scalars(select(Prestazione).where(
                    func.lower(Prestazione.nome) == nome.lower(),
                    Prestazione.id != (p.id if p else -1))).first()
                if doppia:
                    m.errori.append('Esiste già la prestazione %s.' % doppia.nome)
            if m.errori:
                return scheda(titolo, campi(errore=True), m.errori, eliminabile=bool(p),
                              conferma='Eliminare questa prestazione?')
            if p is None:
                p = Prestazione()
                s.add(p)
            p.nome, p.durata_min = nome, durata
            if campi_extra is not None:
                p.campi_extra = ', '.join(e + ('?' if si_no else '') for e, si_no in
                                          Prestazione(campi_extra=campi_extra).elenco_campi_extra)
            if preparazione is not None:
                p.preparazione = preparazione
            if tariffa is not None:
                p.tariffa_cent = tariffa if tariffa != '' else None
            return salva_e_torna(s, p, 'Prestazione', 'Prestazione salvata: %s.' % p.nome)

    return scheda(titolo, campi(), eliminabile=bool(p), conferma='Eliminare questa prestazione?')


# ================================================================= turni
def si_sovrappongono(a_da, a_a, b_da, b_a):
    """Due periodi di validita': None come fine vuol dire a tempo indeterminato."""
    return a_da <= (b_a or ULTIMA) and b_da <= (a_a or ULTIMA)


def stanza_gia_assegnata(s, rid, giorno, inizio, fine, da, a, oid, escludi_id=None):
    """Una stanza ospita un medico alla volta: il motivo per cui il turno
    (stanza rid, giorno della settimana, orario, validita' da-a, medico oid)
    non si puo' salvare, oppure None. Lo stesso medico su due stanze nella
    stessa fascia invece va bene (visite su due ambulatori). Dalla 1.12 la
    usano anche la pianificazione degli ambulatori."""
    singolo = da == a
    for altro in s.scalars(select(Turno).where(
            Turno.risorsa_id == rid, Turno.giorno_settimana == giorno,
            Turno.id != (escludi_id if escludi_id else -1))):
        if singolo and s.scalars(select(Assenza).where(
                Assenza.operatore_id == altro.operatore_id,
                Assenza.dal <= da, Assenza.al >= da)).first():
            continue          # chi ha la stanza quel giorno e' assente: si puo' sostituire
        # 1.11: e al contrario: l'altro e' la sostituzione di un giorno in cui questo
        # medico e' assente. Prima il turno del medico sostituito non si salvava piu'
        # (ne' le fasce ne' «Fino al»), finche' non si cancellava la sostituzione
        if servizi.e_di_un_giorno(altro) and s.scalars(select(Assenza).where(
                Assenza.operatore_id == oid,
                Assenza.dal <= altro.valido_da, Assenza.al >= altro.valido_da)).first():
            continue
        if (inizio < altro.ora_fine and altro.ora_inizio < fine
                and si_sovrappongono(da, a, altro.valido_da, altro.valido_a)):
            return ('La stanza è già assegnata a %s il %s dalle %s alle %s.'
                    % (altro.operatore.etichetta, servizi.GIORNI[altro.giorno_settimana],
                       altro.ora_inizio.strftime('%H:%M'), altro.ora_fine.strftime('%H:%M')))
    return None


@bp.route('/turni/nuovo', methods=['GET', 'POST'])
@bp.route('/turni/<int:tid>', methods=['GET', 'POST'])
def turno(tid=None):
    s = ses()
    t = carica(Turno, tid)
    titolo = 'Modifica turno' if t else 'Nuovo turno'
    medici = s.scalars(select(Operatore).where(
        (Operatore.attivo == True) | (Operatore.id == (t.operatore_id if t else -1)))
        .order_by(Operatore.cognome, Operatore.nome)).all()
    stanze = s.scalars(select(Risorsa).where(
        (Risorsa.attiva == True) | (Risorsa.id == (t.risorsa_id if t else -1)))
        .order_by(Risorsa.struttura_id, Risorsa.ordine)).all()
    if not medici:
        flash('Prima di creare un turno va inserito almeno un medico.', 'errore')
        return redirect(url_for('anagrafiche.medico'))
    if not stanze:
        flash('Prima di creare un turno serve almeno una stanza attiva.', 'errore')
        return redirect(url_for('anagrafiche.stanza'))
    piu_strutture = len({x.struttura_id for x in stanze}) > 1
    v = request.form if request.method == 'POST' else None
    # le fasce della struttura, da dire nella prima scelta (se le strutture sono piu' d'una e
    # hanno fasce diverse, senza numero)
    passi_strutture = {x.struttura.passo_min for x in stanze}
    come_struttura = ('Come la struttura (%d minuti)' % passi_strutture.pop() if len(passi_strutture) == 1
                      else 'Come la struttura')

    def campi(errore=False):
        dati = v if errore else None
        preso = request.args.get('medico') or request.args.get('operatore')
        singolo = t is not None and servizi.e_di_un_giorno(t)
        return [
            campo('ripetizione', 'Ripetizione', tipo='select',
                  opzioni=[('settimanale', 'Ogni settimana'), ('giorno', 'Un giorno solo')],
                  valore=dati.get('ripetizione', 'settimanale') if dati else
                  ('giorno' if singolo or request.args.get('ripetizione') == 'giorno' else 'settimanale'),
                  aiuto='"Un giorno solo" per chi viene senza giorno fisso o per una sostituzione.'),
            campo('operatore', 'Medico', tipo='select',
                  opzioni=[(str(x.id), x.etichetta + ('' if x.attivo else ' (non attivo)')) for x in medici],
                  valore=dati.get('operatore') if dati else str(t.operatore_id if t else (preso or medici[0].id))),
            campo('risorsa', 'Stanza', tipo='select',
                  opzioni=[(str(x.id), x.nome + (' — %s' % x.struttura.nome if piu_strutture else ''))
                           for x in stanze],
                  valore=dati.get('risorsa') if dati else str(t.risorsa_id if t else stanze[0].id)),
            campo('data_singola', 'Giorno', tipo='date', classe='solo-giorno',
                  valore=dati.get('data_singola') if dati else
                  (t.valido_da.isoformat() if singolo else (request.args.get('data') or ''))),
            campo('giorno', 'Giorno della settimana', tipo='select', classe='solo-settimanale',
                  opzioni=[(str(i), g) for i, g in enumerate(servizi.GIORNI)],
                  valore=dati.get('giorno') if dati else str(t.giorno_settimana if t else 0)),
            campo('ora_inizio', 'Dalle', tipo='time', meta=True,
                  valore=dati.get('ora_inizio') if dati else (t.ora_inizio.strftime('%H:%M') if t else '08:00')),
            campo('ora_fine', 'Alle', tipo='time', meta=True,
                  valore=dati.get('ora_fine') if dati else (t.ora_fine.strftime('%H:%M') if t else '14:00')),
            campo('valido_da', 'Valido dal', tipo='date', meta=True, classe='solo-settimanale',
                  valore=dati.get('valido_da') if dati else (t.valido_da.isoformat() if t else date.today().isoformat())),
            campo('valido_a', 'Fino al', tipo='date', meta=True, facoltativo=True, classe='solo-settimanale',
                  valore=dati.get('valido_a') if dati else (t.valido_a.isoformat() if t and t.valido_a else ''),
                  aiuto='Vuoto: a tempo indeterminato.'),
            campo('passo', 'Durata delle fasce', tipo='select',
                  # '0' e non '': un elenco obbligatorio non accetta una prima scelta vuota
                  opzioni=[('0', come_struttura)] + [(str(p), '%d minuti' % p) for p in PASSI_TURNO],
                  valore=dati.get('passo', '0') if dati else (str(t.passo_proprio) if t and t.passo_proprio else '0'),
                  aiuto='La programmazione dell\'ambulatorio: ogni quanto comincia una fascia, dall\'ora di inizio del '
                        'turno. Una prestazione più lunga occupa più fasce intere; una più corta occupa comunque la '
                        'fascia intera.'),
        ]

    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and t:
                descrizione = 'Turno di %s, %s' % (t.operatore.etichetta, servizi.GIORNI[t.giorno_settimana])
                rimasti = appuntamenti_senza_turno(s, t)
                servizi.registra(s, 'Turno', t.id, 'ELIMINATO', descrizione)
                s.delete(t)
                s.commit()
                if rimasti:
                    flash('Turno eliminato: %s. Restano in agenda %d appuntament%s già prenotat%s in quel turno, '
                          'da oggi in poi: non spariscono, ma ora sono fuori turno.' % (
                              descrizione, len(rimasti), 'o' if len(rimasti) == 1 else 'i',
                              'o' if len(rimasti) == 1 else 'i'), 'avviso')
                else:
                    flash('Turno eliminato: %s.' % descrizione, 'ok')
                return redirect(destinazione_sicura(request.values.get('torna'), url_for('anagrafiche.elenco')))
            m = Modulo(request.form)
            oid = m.scelta('operatore', 'Medico', [str(x.id) for x in medici])
            rid = m.scelta('risorsa', 'Stanza', [str(x.id) for x in stanze])
            singolo = request.form.get('ripetizione') == 'giorno'
            if singolo:
                # un giorno solo: e' un turno valido dal giorno al giorno stesso
                da = a = m.data('data_singola', 'Giorno')
                giorno = str(da.weekday()) if da else None
            else:
                giorno = m.scelta('giorno', 'Giorno della settimana', [str(i) for i in range(7)])
                da = m.data('valido_da', 'Valido dal')
                a = m.data('valido_a', 'Fino al', richiesta=False)
            inizio = m.ora('ora_inizio', 'Dalle')
            fine = m.ora('ora_fine', 'Alle')
            if inizio and fine and fine <= inizio:
                m.errori.append('L\'ora di fine deve venire dopo quella di inizio.')
            # 1.10: la durata delle fasce; un modulo di una versione precedente, senza il campo, la lascia com'e'
            passo = t.passo if t else None
            if 'passo' in request.form:
                grezzo = request.form.get('passo') or ''
                if grezzo in ('', '0'):
                    passo = None
                elif grezzo in [str(p) for p in PASSI_TURNO]:
                    passo = int(grezzo)
                else:
                    m.errori.append('Durata delle fasce: scelta non valida.')
            if da and a and a < da:
                m.errori.append('La data di fine validità viene prima di quella di inizio.')
            if not m.errori:
                occupata = stanza_gia_assegnata(s, int(rid), int(giorno), inizio, fine, da, a, int(oid),
                                                escludi_id=t.id if t else None)
                if occupata:
                    m.errori.append(occupata)
            if m.errori:
                return scheda(titolo, campi(errore=True), m.errori, eliminabile=bool(t),
                              conferma='Eliminare questo turno?')
            if t is None:
                t = Turno()
                s.add(t)
            t.operatore_id, t.risorsa_id, t.giorno_settimana = int(oid), int(rid), int(giorno)
            t.ora_inizio, t.ora_fine, t.valido_da, t.valido_a = inizio, fine, da, a
            t.passo = passo
            # il nome si prende dall'elenco e non da t.operatore: cambiando medico
            # la relazione puo' ancora contenere quello di prima
            scelto = next(x for x in medici if x.id == int(oid))
            quando = ('il %s' % da.strftime('%d/%m/%Y')) if singolo else servizi.GIORNI[int(giorno)]
            return salva_e_torna(s, t, 'Turno', 'Turno salvato: %s, %s dalle %s alle %s%s.' % (
                scelto.etichetta, quando, inizio.strftime('%H:%M'), fine.strftime('%H:%M'),
                ', fasce da %d minuti' % passo if passo else ''), avviso=avviso_fasce(s, t),
                torna=request.values.get('torna'))

    return scheda(titolo, campi(), eliminabile=bool(t), conferma='Eliminare questo turno?',
                  nota='I turni decidono quali fasce compaiono libere nella griglia. Quelli '
                       'settimanali si ripetono nel giorno scelto; quelli di un giorno valgono solo quel giorno. '
                       'Ogni turno può avere fasce sue (Durata delle fasce): per esempio visite ogni 20 minuti o '
                       'esami ogni 15, mentre il resto della struttura resta con le sue. '
                       'Per chiudere un turno da una certa data senza cambiare le statistiche passate '
                       '(le ore di turno contano anche nei mesi già fatti), basta scrivere la data in '
                       '"Fino al" invece di eliminarlo.')


def appuntamenti_senza_turno(s, t):
    """Gli appuntamenti attivi, da adesso in poi, che stanno nel turno t e che
    nessun altro turno dello stesso medico nella stessa stanza copre: dopo
    l'eliminazione restano in agenda, ma fuori turno."""
    altri = [u for u in s.scalars(select(Turno).where(
        Turno.operatore_id == t.operatore_id, Turno.risorsa_id == t.risorsa_id, Turno.id != t.id))]
    q = select(Appuntamento).where(
        Appuntamento.operatore_id == t.operatore_id, Appuntamento.risorsa_id == t.risorsa_id,
        Appuntamento.inizio >= max(datetime.now(), datetime.combine(t.valido_da, time(0, 0))),
        Appuntamento.stato.in_(STATI_ATTIVI))
    if t.valido_a:
        q = q.where(Appuntamento.inizio < datetime.combine(t.valido_a + timedelta(days=1), time(0, 0)))
    dentro = []
    for a in s.scalars(q.order_by(Appuntamento.inizio)):
        g, ora = a.inizio.date(), a.inizio.time()
        if not (t.vale_il(g) and t.ora_inizio <= ora < t.ora_fine):
            continue
        if any(u.vale_il(g) and u.ora_inizio <= ora < u.ora_fine for u in altri):
            continue
        dentro.append(a)
    return dentro


def appuntamenti_fuori_fascia(s, t):
    """Gli appuntamenti attivi, da adesso in poi, nella stanza e negli orari del
    turno t con fasce proprie che non stanno nelle sue fasce: cominciano a meta'
    di una fascia, o ne dividono una con un altro (presi prima che il turno
    avesse quelle fasce). Restano dove sono: la griglia li mostra nella fascia
    in cui cominciano."""
    c = t.passo_proprio
    if not c:
        return []
    q = select(Appuntamento).where(
        Appuntamento.risorsa_id == t.risorsa_id, Appuntamento.stato.in_(STATI_ATTIVI),
        Appuntamento.inizio >= max(datetime.now(), datetime.combine(t.valido_da, time(0, 0))))
    if t.valido_a:
        q = q.where(Appuntamento.inizio < datetime.combine(t.valido_a + timedelta(days=1), time(0, 0)))
    per_giorno = {}
    for a in s.scalars(q.order_by(Appuntamento.inizio, Appuntamento.id)):
        if t.vale_il(a.inizio.date()) and t.ora_inizio <= a.inizio.time() < t.ora_fine:
            per_giorno.setdefault(a.inizio.date(), []).append(a)
    fuori = []
    for lista in per_giorno.values():
        blocchi = [servizi.blocco(t, a.inizio, a.fine) for a in lista]
        for i, a in enumerate(lista):
            storto = (servizi._minuti(a.inizio.time()) - servizi._minuti(t.ora_inizio)) % c
            diviso = any(j != i and b[0] < blocchi[i][1] and b[1] > blocchi[i][0] for j, b in enumerate(blocchi))
            if storto or diviso:
                fuori.append(a)
    return sorted(fuori, key=lambda a: (a.inizio, a.id))


def avviso_fasce(s, t):
    """Dopo aver salvato un turno con fasce proprie: quanti appuntamenti gia'
    prenotati non stanno nelle sue fasce (None se nessuno)."""
    fuori = appuntamenti_fuori_fascia(s, t)
    if not fuori:
        return None
    primo = fuori[0].inizio
    if len(fuori) == 1:
        return ('C\'è un appuntamento già prenotato in questo turno che non sta nelle fasce da %d minuti '
                '(comincia a metà di una fascia o ne divide una con un altro): il %s alle %s. Resta dov\'è; '
                'conviene controllarlo nella griglia.' % (t.passo_proprio, primo.strftime('%d/%m'),
                                                          primo.strftime('%H:%M')))
    return ('Ci sono %d appuntamenti già prenotati in questo turno che non stanno nelle fasce da %d minuti '
            '(cominciano a metà di una fascia o ne dividono una con un altro), il primo il %s alle %s. Restano '
            'dove sono; conviene controllarli nella griglia.' % (len(fuori), t.passo_proprio,
                                                                  primo.strftime('%d/%m'), primo.strftime('%H:%M')))


# ============================================================= struttura
def leggi_orario(m, f):
    """Recapiti e orario della struttura. Solo i campi inviati: un modulo di
    una versione precedente, senza questa parte, non li azzera."""
    import pazienti
    valori = {}
    for nome, etichetta, massimo in (('indirizzo', 'Indirizzo', 160), ('telefono', 'Telefono', 40),
                                     ('email', 'Email', 120)):
        if nome in f:
            valori[nome] = m.testo(nome, etichetta, massimo)
    if valori.get('email') and not pazienti.email_valida(valori['email']):
        m.errori.append('Email: indirizzo non valido.')
    if 'ora_apertura' in f or 'ora_chiusura' in f:
        apertura = m.ora('ora_apertura', 'Apertura')
        chiusura = m.ora('ora_chiusura', 'Chiusura')
        passo = m.scelta('passo', 'Durata di una fascia', [str(p) for p in PASSI_AMMESSI])
        if apertura and chiusura and passo:
            if chiusura <= apertura:
                m.errori.append('La chiusura deve venire dopo l\'apertura.')
            elif (chiusura.hour * 60 + chiusura.minute) - (apertura.hour * 60 + apertura.minute) < int(passo):
                m.errori.append('Fra apertura e chiusura deve starci almeno una fascia.')
            else:
                valori.update(ora_apertura=apertura, ora_chiusura=chiusura, passo=int(passo))
    if 'patrono' in f:
        patrono = (f.get('patrono') or '').strip()
        if patrono and Struttura(patrono=patrono).patrono_giorno_mese is None:
            m.errori.append('Festa del patrono: scrivere giorno e mese, per esempio 19/09.')
        else:
            valori['patrono'] = patrono
    if f.get('sezione_orario') == '1':
        giorni = ''.join('1' if f.get('giorno_%d' % i) in ('1', 'on') else '0' for i in range(7))
        if '1' not in giorni:
            m.errori.append('Giorni di apertura: almeno uno.')
        else:
            valori['giorni_apertura'] = giorni
        valori['chiusa_festivi'] = m.spunta('chiusa_festivi')
    if 'posti_letto' in f:
        grezzo = (f.get('posti_letto') or '').strip()
        if not grezzo:
            valori['posti_letto'] = None
        else:
            n = m.intero('posti_letto', 'Posti letto', 0, 500)
            if n is not None:
                valori['posti_letto'] = n or None
    return valori


@bp.route('/strutture/nuova', methods=['GET', 'POST'])
@bp.route('/strutture/<int:sid>', methods=['GET', 'POST'])
def struttura(sid=None):
    """Nome, societa', logo e colore: quello che rende il programma di una sede."""
    s = ses()
    st = carica(Struttura, sid)
    titolo = 'Nome, logo e colori' if st else 'Nuova struttura'

    def campi(errore=False):
        dati = request.form if errore else None
        elenco = [
            campo('nome', 'Nome della struttura', richiesto=True, massimo=80,
                  valore=dati.get('nome') if dati else (st.nome if st else '')),
            campo('societa', 'Società', massimo=120,
                  valore=dati.get('societa') if dati else (st.societa if st else ''),
                  aiuto='Ragione sociale. Compare in fondo ai fogli esportati in Excel.'),
        ]
        if st is not None and st.ha_logo:
            elenco.append(campo('anteprima', 'Logo attuale', tipo='anteprima',
                                src=url_for('logo', sid=st.id, v=st.versione_logo),
                                alt=st.nome))
        elenco.append(campo('logo', 'Carica un logo nuovo' if st is not None and st.ha_logo else 'Logo',
                            tipo='file', accetta='image/png,image/jpeg,image/gif,image/webp,image/bmp',
                            aiuto='PNG o JPG, al massimo 3 MB. I margini vuoti vengono tolti da soli; '
                                  'senza logo al suo posto compare il nome.'))
        if st is not None and st.ha_logo:
            elenco.append(campo('rimuovi_logo', 'Togli il logo', tipo='checkbox', valore=False))
        elenco.append(campo('colore', 'Colore dell\'interfaccia', tipo='color',
                            # un colore non valido rimandato indietro il browser lo mostrerebbe nero
                            valore=dati.get('colore') if dati and COLORE.fullmatch(dati.get('colore') or '')
                            else (st.colore_sicuro if st else COLORE_PREDEFINITO),
                            aiuto='Caricando un logo si propone il suo colore, se questo non è stato cambiato.'))
        # recapiti e orario: il campo nascosto dice che la sezione e' stata
        # inviata, cosi' una casella non spuntata vale "no" e non "non inviato"
        valori = lambda nome, predefinito: dati.get(nome, '') if dati else predefinito
        elenco += [
            campo('sezione_orario', '', tipo='nascosto', valore='1'),
            campo('titolo_recapiti', 'Recapiti', tipo='titolo',
                  aiuto='In testa alla stampa del giorno, sul promemoria per il paziente e nei messaggi.'),
            campo('indirizzo', 'Indirizzo', massimo=160, valore=valori('indirizzo', st.indirizzo if st else '')),
            campo('telefono', 'Telefono', massimo=40, meta=True, valore=valori('telefono', st.telefono if st else '')),
            campo('email', 'Email', massimo=120, meta=True, tipo='email',
                  valore=valori('email', st.email if st else '')),
            campo('titolo_orario', 'Orario della griglia', tipo='titolo',
                  aiuto='Le fasce vanno dall\'apertura alla chiusura. Gli appuntamenti fuori orario '
                        'restano visibili: la griglia si allarga da sola.'),
            campo('ora_apertura', 'Apertura', tipo='time', meta=True,
                  valore=valori('ora_apertura', (st.apertura if st else time(8, 0)).strftime('%H:%M'))),
            campo('ora_chiusura', 'Chiusura', tipo='time', meta=True,
                  valore=valori('ora_chiusura', (st.chiusura if st else time(20, 0)).strftime('%H:%M'))),
            campo('passo', 'Durata di una fascia', tipo='select', meta=True,
                  opzioni=[(str(p), '%d minuti' % p) for p in PASSI_AMMESSI],
                  valore=valori('passo', str(st.passo_min if st else 30))),
            campo('patrono', 'Festa del patrono (gg/mm)', meta=True, massimo=5,
                  valore=valori('patrono', st.patrono if st else ''),
                  aiuto='Esempio: 19/09 per San Gennaro. Vuoto: nessuna.'),
            campo('giorni', 'Giorni di apertura', tipo='giorni', etichette=servizi.GIORNI_BREVI,
                  valore=({i for i in range(7) if dati.get('giorno_%d' % i) in ('1', 'on')} if dati
                          else (st.giorni_aperti if st else set(range(6))))),
            campo('chiusa_festivi', 'Chiusa nei giorni festivi: le fasce non si aprono '
                                    '(un turno di un giorno le riapre)', tipo='checkbox',
                  valore=(dati.get('chiusa_festivi') in ('1', 'on')) if dati
                  else (st.chiusa_festivi if st else False)),
            campo('titolo_letti', 'Posti letto', tipo='titolo',
                  aiuto='Per gli interventi con una notte o un ricovero: il programma conta i letti '
                        'occupati ogni notte e avvisa quando non bastano. Vuoto: nessun controllo.'),
            campo('posti_letto', 'Letti per la notte', tipo='number', meta=True, minimo=0, massimo_n=500,
                  valore=valori('posti_letto', st.posti_letto if st and st.posti_letto else '')),
        ]
        return elenco

    def mostra(errori=None):
        return scheda(titolo, campi(errore=bool(errori)), errori, eliminabile=bool(st),
                      conferma='Eliminare questa struttura?', sid=st.id if st else None)

    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and st:
                if s.scalar(select(func.count()).select_from(Struttura)) <= 1:
                    flash('È l\'unica struttura: non si può eliminare, si può rinominare.', 'errore')
                    return redirect(request.url)
                if not usi(s, [(Risorsa, Risorsa.struttura_id, 'stanza', 'stanze')], st.id):
                    # Dove si fa: la struttura del gruppo collegata a questa e il registro dei pazienti
                    # indirizzati perdono il collegamento, non i dati
                    import dovesifa
                    from modelli import StrutturaGruppo, Indirizzato
                    s.execute(update(StrutturaGruppo).where(StrutturaGruppo.struttura_id == st.id)
                              .values(struttura_id=None))
                    s.execute(update(Indirizzato).where(Indirizzato.struttura_id == st.id).values(struttura_id=None))
                    dovesifa.segna_cambio(s)
                return elimina(
                    s, st, 'Struttura',
                    [(Risorsa, Risorsa.struttura_id, 'stanza', 'stanze')],
                    'La struttura %s' % st.nome, 'Struttura eliminata: %s.' % st.nome,
                    'Vanno prima spostate o eliminate le sue stanze.', femminile=True)
            m = Modulo(request.form)
            nome = m.testo('nome', 'Nome della struttura', 80, richiesto=True)
            societa = m.testo('societa', 'Società', 120)
            colore = (request.form.get('colore') or '').strip()
            if not colore:
                # campo non inviato: il colore resta com'era, come il logo senza file
                colore = st.colore_sicuro if st is not None else COLORE_PREDEFINITO
            elif not COLORE.fullmatch(colore):
                m.errori.append('Colore: formato non valido.')
            nuovo_logo = None
            file = request.files.get('logo')
            if file is not None and file.filename:
                try:
                    # si legge al massimo un byte oltre il limite: basta per rifiutare
                    nuovo_logo = marchio.normalizza_logo(file.read(marchio.MASSIMO_BYTE + 1))
                except marchio.LogoNonValido as e:
                    m.errori.append('Logo: %s' % e)
            rimuovi = m.spunta('rimuovi_logo')
            orario = leggi_orario(m, request.form)
            if not m.errori:
                doppia = s.scalars(select(Struttura).where(
                    func.lower(Struttura.nome) == nome.lower(),
                    Struttura.id != (st.id if st else -1))).first()
                if doppia:
                    m.errori.append('Esiste già una struttura chiamata %s.' % doppia.nome)
            if m.errori:
                return mostra(m.errori)

            colore_prima = st.colore_sicuro if st is not None else COLORE_PREDEFINITO
            if st is None:
                st = Struttura()
                s.add(st)
            st.nome, st.societa = nome, societa
            for k, v in orario.items():
                setattr(st, k, v)
            avvisi = []
            if nuovo_logo is not None:
                st.logo, st.logo_aggiornato = nuovo_logo, datetime.now()
                # colore lasciato com'era: segue il logo nuovo
                if colore.lower() == colore_prima.lower():
                    proposto = marchio.colore_dominante(nuovo_logo)
                    if proposto:
                        colore = proposto
            elif rimuovi:
                st.logo, st.logo_aggiornato = None, None
            usato = marchio.leggibile(colore)
            if usato.lower() != colore.lower():
                avvisi.append('Il colore era troppo chiaro per il testo bianco: è stato scurito quanto basta.')
            st.colore = usato
            risposta = salva_e_torna(s, st, 'Struttura', 'Struttura salvata: %s.' % st.nome)
            for a in avvisi:
                flash(a, 'avviso')
            return risposta

    return mostra()


# ======================================================= assenze e chiusure
MOTIVI_ASSENZA = ['Ferie', 'Malattia', 'Congresso', 'Formazione', 'Permesso']
MOTIVI_CHIUSURA = ['Festività', 'Chiusura estiva', 'Ponte', 'Lavori', 'Disinfestazione']


def appuntamenti_da_spostare(s, dal, al, operatore_id=None, struttura_id=None):
    """Gli appuntamenti attivi, da adesso in poi, che cadono in un'assenza o in
    una chiusura: sono le telefonate da fare. Quelli di stamattina gia'
    passati non si spostano piu' (e lo spostamento in blocco non li mostra)."""
    inizio = max(datetime.combine(dal, time(0, 0)), datetime.now())
    fine = datetime.combine(al + timedelta(days=1), time(0, 0))
    q = select(Appuntamento).join(Risorsa, Appuntamento.risorsa_id == Risorsa.id).where(
        Appuntamento.inizio >= inizio, Appuntamento.inizio < fine,
        Appuntamento.stato.in_(STATI_ATTIVI))
    if operatore_id:
        q = q.where(Appuntamento.operatore_id == operatore_id)
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    return s.scalars(q.order_by(Appuntamento.inizio)).all()


def elenco_da_spostare(apps):
    if not apps:
        return None
    righe = []
    for a in apps:
        testo = '%s %s - %s - %s' % (a.inizio.strftime('%d/%m %H:%M'), a.risorsa.nome,
                                     a.operatore.etichetta,
                                     a.paziente.etichetta if a.paziente else 'senza paziente')
        righe.append({'testo': testo, 'url': url_for('appuntamento', aid=a.id),
                      'telefono': a.paziente.telefono if a.paziente else ''})
    return {'titolo': 'Appuntamenti da spostare (%d)' % len(apps), 'righe': righe,
            'nota': 'Sono ancora in agenda: vanno avvisati i pazienti e spostati o disdetti.'}


def _leggi_periodo(m):
    dal = m.data('dal', 'Dal')
    al = m.data('al', 'Al', richiesta=False) or dal
    if dal and al:
        if al < dal:
            m.errori.append('La data di fine viene prima di quella di inizio.')
        elif (al - dal).days > 366:
            m.errori.append('Al massimo un anno alla volta.')
    return dal, al


@bp.route('/assenze/nuova', methods=['GET', 'POST'])
@bp.route('/assenze/<int:xid>', methods=['GET', 'POST'])
def assenza(xid=None):
    s = ses()
    x = carica(Assenza, xid)
    titolo = 'Modifica assenza' if x else 'Nuova assenza'
    medici = s.scalars(select(Operatore).where(
        (Operatore.attivo == True) | (Operatore.id == (x.operatore_id if x else -1)))
        .order_by(Operatore.cognome, Operatore.nome)).all()
    if not medici:
        flash('Prima va inserito almeno un medico.', 'errore')
        return redirect(url_for('anagrafiche.medico'))

    def campi(errore=False):
        dati = request.form if errore else None
        return [
            campo('operatore', 'Medico', tipo='select',
                  opzioni=[(str(o.id), o.etichetta) for o in medici],
                  valore=dati.get('operatore') if dati else
                  str(x.operatore_id if x else (request.args.get('medico') or medici[0].id))),
            campo('dal', 'Dal', tipo='date', meta=True, richiesto=True,
                  valore=dati.get('dal') if dati else (x.dal.isoformat() if x else date.today().isoformat())),
            campo('al', 'Al (compreso)', tipo='date', meta=True,
                  valore=dati.get('al') if dati else (x.al.isoformat() if x else ''),
                  aiuto='Vuoto: un giorno solo.'),
            campo('motivo', 'Motivo', massimo=60, suggerimenti=MOTIVI_ASSENZA,
                  valore=dati.get('motivo') if dati else (x.motivo if x else 'Ferie')),
        ]

    def mostra(errori=None):
        extra = elenco_da_spostare(appuntamenti_da_spostare(s, x.dal, x.al, operatore_id=x.operatore_id)) \
            if x is not None and not errori else None
        if extra:
            extra['azione'] = {'testo': 'Spostali tutti insieme',
                               'url': url_for('segreteria.sposta_blocco', medico=x.operatore_id,
                                              dal=x.dal.isoformat(), al=x.al.isoformat())}
        return scheda(titolo, campi(errore=bool(errori)), errori, eliminabile=bool(x),
                      conferma='Eliminare questa assenza?', elenco_extra=extra,
                      nota='Nei giorni di assenza i turni del medico non aprono fasce nella griglia.')

    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and x:
                servizi.registra(s, 'Assenza', x.id, 'ELIMINATO', x.operatore.etichetta)
                s.delete(x)
                s.commit()
                flash('Assenza eliminata.', 'ok')
                return redirect(url_for('anagrafiche.elenco'))
            m = Modulo(request.form)
            oid = m.scelta('operatore', 'Medico', [str(o.id) for o in medici])
            dal, al = _leggi_periodo(m)
            motivo = m.testo('motivo', 'Motivo', 60)
            if m.errori:
                return mostra(m.errori)
            if x is None:
                x = Assenza()
                s.add(x)
            x.operatore_id, x.dal, x.al, x.motivo = int(oid), dal, al, motivo
            s.flush()
            medico = s.get(Operatore, int(oid))
            servizi.registra(s, 'Assenza', x.id, 'SALVATO', '%s dal %s al %s' % (medico.etichetta, dal, al))
            s.commit()
            apps = appuntamenti_da_spostare(s, dal, al, operatore_id=x.operatore_id)
            if apps:
                flash('Assenza salvata. Ci sono %d appuntamenti di %s da spostare: sono elencati qui sotto.'
                      % (len(apps), medico.etichetta), 'avviso')
                return redirect(url_for('anagrafiche.assenza', xid=x.id))
            flash('Assenza salvata: %s.' % medico.etichetta, 'ok')
            return redirect(url_for('anagrafiche.elenco'))
    return mostra()


@bp.route('/chiusure/nuova', methods=['GET', 'POST'])
@bp.route('/chiusure/<int:xid>', methods=['GET', 'POST'])
def chiusura(xid=None):
    s = ses()
    x = carica(Chiusura, xid)
    titolo = 'Modifica chiusura' if x else 'Nuova chiusura'
    strutture = s.scalars(select(Struttura).order_by(Struttura.id)).all()

    def campi(errore=False):
        dati = request.form if errore else None
        return [
            campo('struttura', 'Struttura', tipo='select',
                  opzioni=[(str(st.id), st.nome) for st in strutture],
                  valore=dati.get('struttura') if dati else
                  str(x.struttura_id if x else (request.args.get('struttura') or strutture[0].id))),
            campo('dal', 'Dal', tipo='date', meta=True, richiesto=True,
                  valore=dati.get('dal') if dati else (x.dal.isoformat() if x else date.today().isoformat())),
            campo('al', 'Al (compreso)', tipo='date', meta=True,
                  valore=dati.get('al') if dati else (x.al.isoformat() if x else ''),
                  aiuto='Vuoto: un giorno solo.'),
            campo('motivo', 'Motivo', massimo=80, suggerimenti=MOTIVI_CHIUSURA,
                  valore=dati.get('motivo') if dati else (x.motivo if x else '')),
        ]

    def mostra(errori=None):
        extra = elenco_da_spostare(appuntamenti_da_spostare(s, x.dal, x.al, struttura_id=x.struttura_id)) \
            if x is not None and not errori else None
        return scheda(titolo, campi(errore=bool(errori)), errori, eliminabile=bool(x),
                      conferma='Eliminare questa chiusura?', elenco_extra=extra,
                      nota='Nei giorni di chiusura nessuna fascia della struttura si apre.')

    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and x:
                servizi.registra(s, 'Chiusura', x.id, 'ELIMINATO', x.motivo or '')
                s.delete(x)
                s.commit()
                flash('Chiusura eliminata.', 'ok')
                return redirect(url_for('anagrafiche.elenco'))
            m = Modulo(request.form)
            sid = m.scelta('struttura', 'Struttura', [str(st.id) for st in strutture])
            dal, al = _leggi_periodo(m)
            motivo = m.testo('motivo', 'Motivo', 80)
            if m.errori:
                return mostra(m.errori)
            if x is None:
                x = Chiusura()
                s.add(x)
            x.struttura_id, x.dal, x.al, x.motivo = int(sid), dal, al, motivo
            s.flush()
            servizi.registra(s, 'Chiusura', x.id, 'SALVATO', '%s dal %s al %s' % (motivo, dal, al))
            s.commit()
            apps = appuntamenti_da_spostare(s, dal, al, struttura_id=x.struttura_id)
            if apps:
                flash('Chiusura salvata. Ci sono %d appuntamenti in quei giorni: sono elencati qui sotto.'
                      % len(apps), 'avviso')
                return redirect(url_for('anagrafiche.chiusura', xid=x.id))
            flash('Chiusura salvata.', 'ok')
            return redirect(url_for('anagrafiche.elenco'))
    return mostra()
