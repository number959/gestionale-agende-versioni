# -*- coding: utf-8 -*-
"""Gestionale appuntamenti - avvio locale, utente singolo."""
import json
import logging
import mimetypes
import os
import re
import socket
import sys
import threading
import webbrowser
from datetime import datetime, date, time, timedelta
from logging.handlers import RotatingFileHandler
from time import monotonic
from decimal import Decimal, InvalidOperation

from io import BytesIO

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, send_file, abort, Response)
from markupsafe import Markup
from flask import g as contesto      # "g" nel resto del file e' la data del giorno
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session
from werkzeug.routing import IntegerConverter

from modelli import (crea_sessione, aggiorna_database, VERSIONE_SCHEMA, percorso_db, cartella_risorse, Struttura, Risorsa, Operatore,
                     Prestazione, Paziente, Turno, Appuntamento, Attivita, Appunto, COLORE_PREDEFINITO,
                     STATI_ATTIVI, ETICHETTA_STATO, TIPI_VISITA, ETICHETTA_TIPO_VISITA,
                     METODI_PAGAMENTO, PROVENIENZE, leggi_impostazione, importo_in_testo,
                     DEGENZE, ETICHETTA_DEGENZA, MASSIMO_NOTTI, MASSIMO_IMPORTO)
import servizi
from comune import MASSIMO_ID, VERSIONE, data_da, destinazione_sicura, intero, scarica_excel
data_da_stringa = data_da              # il nome di sempre, nel resto del file
import anagrafiche
import pazienti
import viste
import backup
import marchio
import segreteria
import cassa
import documenti
import importa
import sala
import cruscotto
import guida
import invii
import aggiornamenti
import personale
import dovesifa
import autoripara

# i tipi dei file del programma non si chiedono a Windows: sul PC il registro puo'
# dire "text/plain" per i .js o non conoscere i video, e il browser li rifiuterebbe
for _estensione, _tipo in (('.css', 'text/css'), ('.js', 'text/javascript'), ('.woff2', 'font/woff2'),
                           ('.webm', 'video/webm'), ('.png', 'image/png')):
    mimetypes.add_type(_tipo, _estensione)

BASE = cartella_risorse()
app = Flask(__name__,
            template_folder=os.path.join(BASE, "templates"),
            static_folder=os.path.join(BASE, "static"))
app.secret_key = 'gestionale-locale'


class Identificativo(IntegerConverter):
    def __init__(self, mappa, *args, **kwargs):
        kwargs.setdefault('max', MASSIMO_ID)
        super().__init__(mappa, *args, **kwargs)


# va registrato prima di dichiarare le pagine: vale per tutti i <int:...>
app.url_map.converters['int'] = Identificativo
# un documento allegato puo' pesare 10 MB (il logo 3): il resto e' margine
# per gli altri campi del modulo
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
Sessione = None
_registro = None
LUCCHETTO = threading.Lock()   # serializza i salvataggi
MASSIMA_DURATA = 24 * 60       # oltre, la somma sulla data straborda
FILI = 4                       # le richieste che waitress serve insieme
LENTA = 120                    # secondi: una pagina ferma da piu' di cosi' tiene occupato un filo
_in_corso = {}                 # filo -> (inizio, pagina): le richieste che si stanno servendo
_lucchetto_istanza = None      # il file bloccato del gestionale principale (autoripara.entra)


def ses():
    """Una sessione per thread. Con waitress le richieste sono concorrenti:
    una sessione condivisa fa esplodere SQLite."""
    global _registro
    if _registro is None:
        _registro = scoped_session(Sessione)
    return _registro


@app.teardown_appcontext
def chiudi(_):
    if _registro is not None:
        _registro.remove()


# ------------------------------------------------ richieste da altre pagine
# Il gestionale risponde solo sul PC, ma nello stesso browser la segreteria
# apre anche altri siti. Una pagina qualsiasi potrebbe mandargli un modulo
# (eliminare un appuntamento, cambiare le impostazioni), e con il "DNS
# rebinding" (un nome di un altro sito che punta a 127.0.0.1) anche leggerne
# le pagine. Quindi: solo gli indirizzi del PC, e i moduli solo dalle pagine
# del gestionale.
NOMI_LOCALI = re.compile(r'(127\.0\.0\.1|localhost)(:\d{1,5})?', re.I)


def stessa_origine(indirizzo):
    """L'indirizzo (Origin o Referer) e' una pagina del gestionale, sulla
    stessa porta? 'null', un'altra porta o un altro nome: no."""
    m = re.match(r'https?://([^/?#]*)', indirizzo or '', re.I)
    return bool(m) and m.group(1).lower() == request.host.lower()


@app.before_request
def solo_dal_gestionale():
    if not NOMI_LOCALI.fullmatch(request.host or ''):
        return Response('Indirizzo non valido: il gestionale si apre da http://127.0.0.1:5000.',
                        status=400, mimetype='text/plain')
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    sito = request.headers.get('Sec-Fetch-Site')
    origine = request.headers.get('Origin')
    provenienza = request.headers.get('Referer')
    if sito is not None and sito not in ('same-origin', 'none') or \
            origine is not None and not stessa_origine(origine) or \
            origine is None and provenienza is not None and not stessa_origine(provenienza):
        logging.warning('richiesta %s %s rifiutata: arriva da %s', request.method, request.path,
                        origine or provenienza or sito)
        return Response('Richiesta rifiutata: arriva da una pagina che non è del gestionale.',
                        status=403, mimetype='text/plain')
    return None


@app.before_request
def segna_inizio():
    # per /salute: un gestionale con tutti i fili fermi su una pagina e' bloccato
    _in_corso[threading.get_ident()] = (monotonic(), request.path)


@app.teardown_request
def segna_fine(_):
    _in_corso.pop(threading.get_ident(), None)


@app.route('/salute')
def salute():
    """Il secondo clic sull'icona chiede qui se il gestionale aperto risponde
    (autoripara.entra). Niente database e niente lucchetto: deve rispondere
    anche quando il resto e' fermo; 'bloccato' se tutti gli altri fili sono
    fermi su una pagina da piu' di LENTA secondi."""
    adesso, io = monotonic(), threading.get_ident()
    lente = sum(1 for filo, (inizio, _) in list(_in_corso.items()) if filo != io and adesso - inizio > LENTA)
    r = Response(json.dumps({'programma': autoripara.PROGRAMMA, 'versione': VERSIONE, 'pid': os.getpid(),
                             'lente': lente, 'bloccato': lente >= FILI - 1}), mimetype='application/json')
    r.headers['Cache-Control'] = 'no-store'
    return r


PAGINA_ERRORE = '''<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Qualcosa non è andato</title>
<style>body{font-family:Inter,Segoe UI,Arial,sans-serif;max-width:40em;margin:4em auto;padding:0 1em;line-height:1.5;color:#1d2433;background:#fff}
h1{font-size:1.4em}a{color:#154381}</style></head><body>
<h1>Qualcosa non è andato</h1>
<p>%(motivo)s</p>
<p>Tornare indietro e riprovare. Se succede di nuovo, il programma prova a ripararsi da solo: guardare
<a href="/autoriparazione">Configura → Controllo del programma</a>. Per l'assistenza il dettaglio è nel registro
(<code>gestionale.log</code>).</p>
<p><a href="/">Torna alla pagina Oggi</a></p></body></html>'''


@app.errorhandler(500)
def errore_interno(e):
    """Al posto della pagina di errore del server, una spiegazione in parole
    semplici. Un errore del database rovinato fa partire subito il controllo
    (il custode lo ripara con i salvataggi fermi)."""
    originale = getattr(e, 'original_exception', None)
    testo = str(originale or '').lower()
    if any(p in testo for p in ('malformed', 'not a database', 'disk image')):
        autoripara.chiedi_controllo()
    if 'disk is full' in testo or 'no space left' in testo:
        motivo = ('Non salvato: il disco del computer è pieno. Liberare spazio (per esempio svuotare il Cestino e '
                  'la cartella Download) e riprovare.')
    elif 'database is locked' in testo or 'database is busy' in testo:
        motivo = ('Non salvato: il database era occupato da un altro programma (per esempio una copia in corso). '
                  'Riprovare fra qualche secondo.')
    else:
        motivo = 'La pagina non si è aperta per un errore del programma. Quello che era già salvato è al sicuro.'
    return Response(PAGINA_ERRORE % {'motivo': motivo}, status=500, mimetype='text/html')


def momento(giorno, ora):
    """None se giorno oppure ora non sono scrivibili come data e ora."""
    try:
        return datetime.strptime('%s %s' % (giorno, ora), '%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return None


@app.errorhandler(413)
def troppo_grande(_):
    # invece della pagina di errore del server, si torna al modulo con una spiegazione
    flash('Il file è troppo grande: al massimo 10 MB per un documento o un\'importazione, 3 MB per il logo.', 'errore')
    return redirect(request.path)


def marchio_di(sid=None):
    """Nome, logo e colori della struttura da mostrare nella pagina: quella
    indicata, altrimenti la prima. Calcolato una volta per richiesta."""
    memoria = contesto.setdefault('_marchi', {})
    chiave = intero(sid, 0) or 0
    if chiave not in memoria:
        s = ses()
        st = s.get(Struttura, chiave) if chiave else None
        if st is None:
            st = s.scalars(select(Struttura).order_by(Struttura.id)).first()
        if st is None:
            memoria[chiave] = dict(id=None, nome='Gestionale Agende', societa='', logo_url=None,
                                   tema=marchio.tema(COLORE_PREDEFINITO))
        else:
            memoria[chiave] = dict(
                id=st.id, nome=st.nome, societa=st.societa or '',
                # la versione nell'indirizzo fa ricaricare il logo appena cambia
                logo_url=url_for('logo', sid=st.id, v=st.versione_logo)
                if st.ha_logo else None,
                tema=marchio.tema(st.colore_sicuro))
    return memoria[chiave]


app.jinja_env.filters['euro'] = importo_in_testo


@app.context_processor
def funzioni_modelli():
    def da_confermare():
        # il numero accanto a "Da confermare" nel menu; senza database, niente numero
        try:
            return segreteria.quanti_appunti(ses())
        except Exception:
            return 0
    return {'marchio_di': marchio_di, 'oggi_iso': date.today().isoformat(),
            'etichetta_stato': ETICHETTA_STATO, 'n_da_confermare': da_confermare, 'versione_programma': VERSIONE,
            'testo_luogo_paziente': pazienti.testo_luogo_paziente}


@app.route('/logo/<int:sid>')
def logo(sid):
    st = ses().get(Struttura, sid)
    if st is None or not st.ha_logo or not st.logo:
        abort(404)
    risposta = send_file(BytesIO(st.logo), mimetype='image/png', max_age=31536000,
                         etag='logo-%d-%d' % (sid, st.versione_logo))
    risposta.headers['X-Content-Type-Options'] = 'nosniff'
    return risposta


@app.route('/')
def home():
    # all'avvio la pagina Oggi: cosa c'e' da fare adesso
    return redirect(url_for('cruscotto.oggi'))


@app.route('/giorno/<iso>')
def giorno(iso):
    g = data_da_stringa(iso)
    strutture = ses().scalars(select(Struttura).where(Struttura.attiva == True)).all()
    if not strutture:
        # niente errore 500 in faccia alla segreteria: si spiega cosa manca
        return render_template('da_configurare.html'), 200
    sid = intero(request.args.get('struttura'), strutture[0].id) or strutture[0].id
    vista = servizi.griglia(ses(), g, sid)
    colonne = vista['colonne']
    # appena installato non ci sono medici ne' turni: la griglia sarebbe tutta
    # grigia senza spiegazione, quindi si dice cosa fare
    nessun_medico = ses().scalars(select(Operatore.id).where(Operatore.attivo == True)).first() is None
    nessun_turno = ses().scalars(select(Turno.id)).first() is None
    return render_template('griglia.html', g=g, colonne=colonne, fasce=vista['fasce'],
                           passo=vista['passo'], base=vista['base'], misto=vista['misto'],
                           etichette=vista['etichette'],
                           altezza_riga=vista['altezza_riga'],
                           strutture=strutture, sid=sid,
                           nessun_medico=nessun_medico, nessun_turno=nessun_turno,
                           titolo=servizi.etichetta_giorno(g),
                           ieri=(g - timedelta(days=1)).isoformat(),
                           domani=(g + timedelta(days=1)).isoformat(),
                           oggi=date.today().isoformat(),
                           totale=sum(c['occupate'] for c in colonne),
                           annullati=vista['annullati'], info=vista['giorno'],
                           nota=segreteria.nota_del_giorno(ses(), sid, g), adesso=datetime.now(),
                           appunti=segreteria.appunti_del_giorno(ses(), g, sid),
                           indirizzo_prenota=segreteria.indirizzo_prenota,
                           sala_giorno=sala.riassunto_giorno(ses(), g, sid),
                           torna=request.full_path.rstrip('?'),
                           allarme=backup.allarme(), sezione='giorno', data_menu=g.isoformat())


# ============================================================ appuntamento
def leggi_importo(testo):
    """'80', '80,00', '1.250,50', '€ 80' -> centesimi. None se vuoto,
    ValueError se non si capisce o e' fuori misura."""
    t = (testo or '').replace('€', '').replace(' ', '').strip()
    if not t:
        return None
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
        t = t.replace('.', '')                   # 1.250 all'italiana: milleduecentocinquanta
    # solo cifre e al piu' due decimali: niente 1e3, nan, inf, che Decimal accetterebbe
    if not re.fullmatch(r'\d+(\.\d{1,2})?', t):
        raise ValueError(testo)
    try:
        valore = Decimal(t)
    except InvalidOperation:
        raise ValueError(testo)
    if not valore.is_finite() or valore < 0 or valore > MASSIMO_IMPORTO:
        raise ValueError(testo)
    return int((valore * 100).quantize(Decimal('1')))


def leggi_extra(prest, modulo):
    """I campi extra della prestazione scelta. Le caselle si'/no valgono
    sempre qualcosa; i campi di testo solo se scritti."""
    valori = {}
    for i, (etichetta, si_no) in enumerate(prest.elenco_campi_extra):
        nome = 'extra_%d_%d' % (prest.id, i)
        if si_no:
            valori[etichetta] = 'Sì' if modulo.get(nome) in ('1', 'on') else 'No'
        else:
            v = ' '.join((modulo.get(nome) or '').split())[:80]
            if v:
                valori[etichetta] = v
    return valori


def controlla_campi_nuovi(modulo):
    """Paziente, tipo, convenzione e importo: (valori, errori)."""
    errori, valori = [], {}
    cognome = (modulo.get('paziente') or '').strip()
    if len(cognome) > 60:
        errori.append('Paziente: il cognome può avere al massimo 60 caratteri.')
    if len((modulo.get('nome_paziente') or '').strip()) > 60:
        errori.append('Paziente: il nome può avere al massimo 60 caratteri.')
    telefono = (modulo.get('telefono') or '').strip()
    if len(telefono) > 30:
        errori.append('Telefono: al massimo 30 caratteri.')
    elif telefono and len(pazienti.cifre(telefono)) < 6:
        # come la scheda del paziente: un numero cosi' non si chiama e non si salverebbe
        errori.append('Telefono: servono almeno 6 cifre.')
    email = (modulo.get('email_paziente') or '').strip()
    if email and (len(email) > 120 or not pazienti.email_valida(email)):
        errori.append('Email del paziente: indirizzo non valido.')
    tipo = modulo.get('tipo') or ''
    if tipo not in ETICHETTA_TIPO_VISITA:
        errori.append('Tipo: scelta non valida.')
        tipo = ''
    convenzione = ' '.join((modulo.get('convenzione') or '').split())
    if len(convenzione) > 80:
        errori.append('Convenzione: al massimo 80 caratteri.')
    try:
        importo = leggi_importo(modulo.get('importo'))
    except ValueError:
        errori.append('Importo: non valido (esempio: 80,00).')
        importo = None
    note = modulo.get('note', '') or ''
    if len(note) > 4000:
        errori.append('Note: al massimo 4000 caratteri.')
    degenza = modulo.get('degenza') or ''
    if degenza not in ETICHETTA_DEGENZA:
        errori.append('Degenza: scelta non valida.')
        degenza = ''
    notti = None
    if degenza == 'RICOVERO':
        testo_notti = (modulo.get('notti') or '').strip()
        if testo_notti:
            try:
                notti = int(testo_notti)
            except ValueError:
                notti = 0
            if not 1 <= notti <= MASSIMO_NOTTI:
                errori.append('Notti di ricovero: fra 1 e %d.' % MASSIMO_NOTTI)
                notti = None
    valori.update(tipo=tipo, convenzione=convenzione, importo_cent=importo, degenza=degenza, notti=notti)
    return valori, errori


def controlla_paziente(modulo):
    """Data, sesso e luogo di nascita, codice fiscale (controllato, o
    calcolato dai dati) e indirizzo del paziente, dal modulo di
    prenotazione: (valori, errori). Finiscono nella scheda del paziente, non
    nell'appuntamento."""
    valori, errori, calcolato = pazienti.leggi_anagrafica(modulo, modulo.get('paziente'), modulo.get('nome_paziente'))
    indirizzo, e3 = pazienti.leggi_indirizzo(modulo.get('indirizzo_paziente'))
    valori.update(indirizzo=indirizzo, cf_calcolato=calcolato)
    return valori, errori + [e for e in (e3,) if e]


@app.route('/appuntamento', methods=['GET', 'POST'])
@app.route('/appuntamento/<int:aid>', methods=['GET', 'POST'])
def appuntamento(aid=None):
    s = ses()
    a = s.get(Appuntamento, aid) if aid else None
    if aid and not a:
        abort(404)

    if request.method == 'POST':
        if request.form.get('azione') == 'elimina' and a:
            quando, iso = a.inizio, a.inizio.date().isoformat()
            sid_stanza = struttura_di(s, a, richiesta=request.form.get('struttura'))
            from sqlalchemy import update
            from modelli import Documento, Attesa, Invio
            notizie = []
            with LUCCHETTO:                  # come ogni altro salvataggio
                servizi.registra(s, 'Appuntamento', a.id, 'ELIMINATO',
                                 '%s %s' % (a.risorsa.nome, quando))
                # i messaggi non ancora partiti non partono piu'
                fermi = s.scalars(select(Invio).where(Invio.appuntamento_id == a.id,
                                                      Invio.stato == 'DA_INVIARE')).all()
                for x in fermi:
                    x.stato, x.errore = 'ANNULLATO', 'appuntamento eliminato'
                paziente_id = a.paziente_id
                # documenti, cose da fare e registro dei messaggi restano, sciolti
                for modello in (Documento, Attivita, Attesa, Appunto, Invio):
                    s.execute(update(modello).where(modello.appuntamento_id == a.id).values(appuntamento_id=None))
                s.delete(a)
                s.flush()
                # l'email automatica non partita poteva valere anche per un altro
                # appuntamento del paziente quel giorno (una sola per gastroscopia e
                # colonscopia): adesso parte per quello
                if any(x.motivo == 'PREPARAZIONE' and not x.a_mano for x in fermi):
                    try:
                        notizie = [x.destinatario for x in invii.ricontrolla(s, paziente_id, quando)]
                    except Exception:
                        logging.exception('email automatiche dopo l\'eliminazione di un appuntamento')
                s.commit()
            if notizie:
                invii.sveglia()
            flash('Appuntamento eliminato.' + (' L\'email automatica parte per l\'altro appuntamento del paziente '
                                               'nello stesso giorno.' if notizie else ''), 'ok')
            return redirect(url_for('giorno', iso=iso, struttura=sid_stanza))

        rid = intero(request.form.get('risorsa'))
        oid = intero(request.form.get('operatore'))
        pid = intero(request.form.get('prestazione'))
        sid_form = intero(request.form.get('struttura'), 1) or 1
        stanza, medico, prest = s.get(Risorsa, rid), s.get(Operatore, oid), s.get(Prestazione, pid)
        inizio = momento(request.form.get('data'), request.form.get('ora'))

        # niente di tutto questo puo' essere dato per buono: arriva da un modulo
        brutti = []
        if stanza is None:
            brutti.append('Stanza non valida.')
        if medico is None:
            brutti.append('Medico non valido.')
        if prest is None:
            brutti.append('Prestazione non valida.')
        if inizio is None:
            brutti.append('Giorno oppure ora non validi.')
        nuovi, errori_nuovi = controlla_campi_nuovi(request.form)
        brutti += errori_nuovi
        dati_paziente, errori_paziente = controlla_paziente(request.form)
        brutti += errori_paziente
        ripetizione = None
        if a is None:
            try:
                ripetizione = segreteria.leggi_ripetizione(request.form)
            except ValueError as e:
                brutti.append(str(e))
        if brutti:
            for m in brutti:
                flash(m, 'errore')
            return mostra_modulo(s, a, data_da_stringa(request.form.get('data')),
                                 request.form.get('ora') or '08:00', rid, sid_form, request.form)
        try:
            durata = int(request.form.get('durata') or prest.durata_min)
        except ValueError:
            durata = 0
        motivi = []
        if durata < 5 or durata > MASSIMA_DURATA:
            motivi.append('La durata deve stare fra 5 minuti e 24 ore.')
        fine = inizio + timedelta(minutes=min(max(durata, 5), MASSIMA_DURATA))
        # il controllo e il salvataggio devono stare insieme: senza il lucchetto
        # due salvataggi contemporanei passano entrambi il controllo. Un
        # appuntamento disdetto che si modifica non occupa la stanza: non entra
        # in conflitto finche' resta disdetto
        with LUCCHETTO:
            if a is None or a.stato in STATI_ATTIVI:
                motivi += servizi.conflitti(s, rid, oid, inizio, fine, escludi_id=aid)
            if motivi:
                for m in motivi:
                    flash(m, 'errore')
                # si torna al form con quello che era gia' stato scritto
                return mostra_modulo(s, a, inizio.date(), request.form.get('ora'), rid, sid_form,
                                     request.form)
            # si torna alla giornata della struttura in cui l'appuntamento ora sta
            return salva(s, a, aid, rid, oid, pid, inizio, fine, stanza.struttura_id or sid_form,
                         nuovi, leggi_extra(prest, request.form), ripetizione, dati_paziente)

    g = data_da_stringa(request.args.get('data') or (a.inizio.date().isoformat() if a else None))
    ora = request.args.get('ora') or (a.inizio.strftime('%H:%M') if a else '08:00')
    rid = intero(request.args.get('risorsa'), a.risorsa_id if a else 0)
    sid = struttura_di(s, a, rid, request.args.get('struttura'))
    # da un appunto da confermare: il modulo arriva gia' compilato
    appunto = s.get(Appunto, intero(request.args.get('appunto'))) if a is None and request.args.get('appunto') else None
    if appunto is not None and appunto.aperto:
        return mostra_modulo(s, a, g, ora, rid, sid, segreteria.modulo_da_appunto(appunto))
    return mostra_modulo(s, a, g, ora, rid, sid, None)


def mostra_modulo(s, a, g, ora, rid, sid, modulo):
    """Il modulo di prenotazione, nuovo o da correggere."""
    proposto = None
    if a is None and modulo is None:
        # dalla griglia: il medico di turno; da "prima disponibilita'": quello cercato
        proposto = intero(request.args.get('medico')) or medico_di_turno(s, g, rid, ora)
    scelto = s.get(Paziente, intero(request.args.get('paziente_id'))) if a is None and modulo is None else None
    prestazione_proposta = intero(request.args.get('prestazione')) if a is None and modulo is None else 0
    serie = []
    if a is not None and a.serie:
        serie = s.scalars(select(Appuntamento).where(Appuntamento.serie == a.serie)
                          .order_by(Appuntamento.inizio)).all()
    paziente_a = a.paziente if a is not None else None
    return render_template('appuntamento.html', a=a, g=g, ora=ora, rid=rid, sid=sid,
                           modulo=modulo, proposto=proposto, paziente_scelto=scelto,
                           prestazione_proposta=prestazione_proposta,
                           durata_proposta=intero(request.args.get('durata')) if modulo is None else 0,
                           collegamenti=pazienti.collegamenti_paziente(a.paziente) if a and a.paziente else {},
                           tariffe=json.dumps(cassa.mappa_tariffe(s), ensure_ascii=False),
                           moduli=documenti.moduli_per(s, a) if a is not None else [],
                           documenti=documenti.documenti_di(s, paziente_a.id) if paziente_a else [],
                           serie=serie, metodi=METODI_PAGAMENTO, provenienze=PROVENIENZE, degenze=DEGENZE,
                           checklist=sala.stato_checklist(a, sala.voci_checklist(s)) if a is not None else None,
                           voci_checklist=sala.voci_checklist(s) if a is not None else [],
                           attesa=intero(request.values.get('attesa')),
                           appunto=intero(request.values.get('appunto')),
                           candidati_attesa=segreteria.candidati_attesa(s, a) if a is not None and a.stato == 'DISDETTO'
                           and a.inizio > datetime.now() else [],
                           messaggi=invii.pannello(s, a) if a is not None else None,
                           sezione='giorno', data_menu=g.isoformat(), **elenchi(a, sid))


@app.route('/appuntamento/<int:aid>/stato', methods=['POST'])
def cambia_stato(aid):
    """Arrivato, confermato, disdetto, non presentato: un clic, senza aprire
    il modulo. Rimettere attivo un disdetto e' possibile solo se la fascia
    e' ancora libera."""
    s = ses()
    a = s.get(Appuntamento, aid)
    if a is None:
        abort(404)
    ripiego = url_for('giorno', iso=a.inizio.date().isoformat(), struttura=struttura_di(s, a))
    torna = destinazione_sicura(request.form.get('torna'), ripiego)
    nuovo = request.form.get('stato')
    if nuovo not in ETICHETTA_STATO:
        flash('Stato non valido.', 'errore')
        return redirect(torna)
    chi = a.paziente.etichetta if a.paziente else 'Appuntamento delle %s' % a.inizio.strftime('%H:%M')
    with LUCCHETTO:
        vecchio = a.stato
        if nuovo == vecchio:
            return redirect(torna)
        motivi = servizi.imposta_stato(s, a, nuovo)
        if motivi:
            flash('%s non si può rimettere in agenda: %s' % (chi, ' '.join(motivi)), 'errore')
            return redirect(torna)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            flash('Quella fascia risulta già presa da un altro appuntamento.', 'errore')
            return redirect(torna)
    messaggio = '%s: %s.' % (chi, ETICHETTA_STATO[nuovo].lower())
    # una fascia futura che si libera: chi e' in lista d'attesa per quella?
    if nuovo == 'DISDETTO' and a.inizio > datetime.now():
        candidati = segreteria.candidati_attesa(s, a)
        if candidati:
            flash(Markup('%s <a href="%s">%d in lista d\'attesa per questa fascia: chi chiamare</a>.') % (
                messaggio, url_for('segreteria.attesa_per', aid=a.id), len(candidati)), 'avviso')
            return redirect(torna)
    flash(messaggio, 'ok')
    return redirect(torna)


def medico_di_turno(s, g, rid, ora):
    """Chi e' di turno in quella stanza a quell'ora: aprendo una fascia libera
    dalla griglia il modulo propone lui, non il primo medico in ordine
    alfabetico. Un medico assente non viene proposto."""
    try:
        quando = datetime.strptime(ora, '%H:%M').time()
    except (TypeError, ValueError):
        return None
    stanza = s.get(Risorsa, rid) if rid else None
    if stanza is None:
        return None
    regole = servizi.Regole(s, g, g)
    for t in regole.turni_effettivi(g, stanza.struttura, rid):
        if t.ora_inizio <= quando < t.ora_fine and t.operatore.attivo:
            return t.operatore_id
    return None


def salva(s, a, aid, rid, oid, pid, inizio, fine, sid_form, nuovi=None, extra=None, ripetizione=None,
          dati_paziente=None):
    avviso = servizi.fuori_turno(s, rid, oid, inizio, fine)
    dp = dati_paziente or {}
    paz = pazienti.trova_o_crea(
        s, intero(request.form.get('paziente_id')), request.form.get('paziente'),
        request.form.get('nome_paziente'), request.form.get('telefono'),
        request.form.get('email_paziente'), dp.get('data_nascita'), dp.get('codice_fiscale', ''),
        dp.get('indirizzo', ''), dp.get('sesso', ''), dp.get('luogo_nascita', ''), dp.get('cf_calcolato', False))

    if not a:
        a = Appuntamento()
        s.add(a)
    a.risorsa_id, a.operatore_id, a.prestazione_id = rid, oid, pid
    a.paziente_id = paz.id if paz else None
    a.inizio, a.fine = inizio, fine
    a.note = request.form.get('note', '')
    for k, v in (nuovi or {}).items():
        setattr(a, k, v)
    a.extra = json.dumps(extra, ensure_ascii=False) if extra else ''
    nuovo = a.id is None
    try:
        s.flush()
        servizi.registra(s, 'Appuntamento', a.id, 'SALVATO',
                         '%s %s' % (a.risorsa.nome, inizio))
        avvisi = ([avviso] if avviso else []) + pazienti.avvisi_prenotazione(s, paz, a)
        s.expire(a, ['risorsa', 'operatore'])      # la stanza o il medico possono essere cambiati
        for x in (sala.avviso_giorno_sala(a), sala.avviso_letti(s, a)):
            if x:
                avvisi.append(x)
        if nuovo and paz is not None and request.form.get('provenienza') in dict(PROVENIENZE) \
                and not paz.provenienza:
            paz.provenienza = request.form.get('provenienza')
        if nuovo and segreteria.chiudi_attesa_prenotata(s, intero(request.form.get('attesa')), a):
            avvisi.append('Tolto dalla lista d\'attesa.')
        if nuovo and segreteria.chiudi_appunto_prenotato(s, intero(request.form.get('appunto')), a):
            avvisi.append('Tolto dai da confermare.')
        if ripetizione:
            create, saltate = segreteria.crea_serie(s, a, *ripetizione)
            avvisi.append('Serie: %d appuntamenti prenotati.' % len(create))
            for quando, motivo in saltate:
                avvisi.append('Non prenotato il %s: %s' % (quando.strftime('%d/%m/%Y alle %H:%M'), motivo))
        informazioni = []
        if paz is not None:
            avvisi += pazienti.avvisi_anagrafica(paz)
            if dp.get('cf_calcolato') and paz.codice_fiscale == dp.get('codice_fiscale'):
                informazioni.append(pazienti.nota_calcolato(paz.codice_fiscale))
        # le email automatiche (una per la serie intera: la preparazione e' la stessa).
        # Un difetto nei messaggi non deve mai far perdere la prenotazione
        notizie = []
        try:
            invii.dopo_salvataggio(s, a, notizie, avvisi)
        except Exception as e:
            logging.exception('email automatiche dell\'appuntamento %s', a.id)
            avvisi.append('Email automatica non preparata (%s): si può mandare dalla pagina dell\'appuntamento.' % e)
        s.commit()
    except IntegrityError:
        s.rollback()
        flash('Quella fascia risulta già presa: ricaricare la giornata.', 'errore')
        return redirect(url_for('giorno', iso=inizio.date().isoformat(), struttura=sid_form))
    if notizie:
        invii.sveglia()
    testi = notizie + informazioni + avvisi
    flash('Appuntamento salvato.' + (' ' + ' '.join(testi) if testi else ''),
          'avviso' if avvisi else 'ok')
    return redirect(url_for('giorno', iso=inizio.date().isoformat(), struttura=sid_form))


def elenchi(a=None, sid=None):
    """Stanze e medici tra cui scegliere. Se si modifica un appuntamento, i suoi
    stanza e medico restano in elenco anche se nel frattempo disattivati:
    altrimenti salvando, anche solo per una nota, passerebbe al primo della lista.

    Con piu' strutture le stanze sono raggruppate per struttura, e quelle della
    struttura da cui si arriva vengono per prime: quando non e' stata scelta una
    stanza il browser propone la prima dell'elenco, che deve essere di questa
    struttura e non di un'altra sede."""
    from sqlalchemy import func
    s = ses()
    rid = a.risorsa_id if a else -1
    oid = a.operatore_id if a else -1
    risorse = s.scalars(select(Risorsa).where((Risorsa.attiva == True) | (Risorsa.id == rid))
                        .order_by(Risorsa.ordine)).all()
    gruppi = {}
    for r in risorse:
        gruppi.setdefault(r.struttura_id, []).append(r)
    ordine = sorted(gruppi, key=lambda k: (k != sid, k or 0))
    # le convenzioni gia' usate, le piu' frequenti prima: si sceglie invece di riscrivere
    convenzioni = [c for c, in s.execute(
        select(Appuntamento.convenzione).where(Appuntamento.convenzione != '')
        .group_by(Appuntamento.convenzione).order_by(func.count().desc()).limit(30))]
    return dict(
        risorse=[r for k in ordine for r in gruppi[k]],
        gruppi_stanze=[(s.get(Struttura, k) if k else None, gruppi[k]) for k in ordine],
        operatori=s.scalars(select(Operatore).where((Operatore.attivo == True) | (Operatore.id == oid))
                            .order_by(Operatore.cognome, Operatore.nome)).all(),
        prestazioni=s.scalars(select(Prestazione).order_by(Prestazione.nome)).all(),
        tipi=TIPI_VISITA, convenzioni=convenzioni)


def struttura_di(s, a=None, rid=None, richiesta=None):
    """La struttura a cui appartiene cio' che si sta guardando: quella della
    stanza dell'appuntamento, poi della stanza scelta, poi quella chiesta
    nell'indirizzo, infine la prima."""
    if a is not None and a.risorsa is not None:
        return a.risorsa.struttura_id
    stanza = s.get(Risorsa, rid) if rid else None
    if stanza is not None:
        return stanza.struttura_id
    sid = intero(richiesta, 0)
    if sid and s.get(Struttura, sid) is not None:
        return sid
    prima = s.scalars(select(Struttura.id).order_by(Struttura.id)).first()
    return prima or 1


# medici, turni, stanze e prestazioni: stessa sessione per thread e stesso
# lucchetto dei salvataggi degli appuntamenti
anagrafiche.collega(app, ses, LUCCHETTO)
pazienti.collega(app, ses, LUCCHETTO)
viste.collega(app, ses, LUCCHETTO, lambda: Sessione)
segreteria.collega(app, ses, LUCCHETTO)
cassa.collega(app, ses, LUCCHETTO, leggi_importo)
documenti.collega(app, ses, LUCCHETTO)
importa.collega(app, ses, LUCCHETTO)
sala.collega(app, ses, LUCCHETTO)
cruscotto.collega(app, ses, LUCCHETTO)
personale.collega(app, ses, LUCCHETTO)
dovesifa.collega(app, ses, LUCCHETTO)
guida.collega(app)
# la coda dei messaggi lavora in un thread suo: le serve una sessione nuova ogni volta
invii.collega(app, ses, LUCCHETTO, lambda: Sessione())
# anche i controlli degli aggiornamenti
aggiornamenti.collega(app, ses, LUCCHETTO, lambda: Sessione())


@app.route('/esporta/<iso>')
def esporta(iso):
    g = data_da_stringa(iso)
    sid = intero(request.args.get('struttura'), 1) or 1
    # il nome nasce dalla data gia' convalidata, mai dal testo dell'indirizzo:
    # altrimenti bastano un byte nullo o 500 lettere per far cadere il server
    nome = 'planning-%s.xlsx' % g.isoformat()
    dati = BytesIO()
    servizi.esporta_giorno(ses(), g, sid, dati)
    return scarica_excel(dati, nome)


@app.route('/autoriparazione', methods=['GET', 'POST'])
def autoriparazione():
    """Configura → Controllo del programma: com'e' adesso e cosa ha riparato
    da solo (autoripara). «Controlla adesso» fa il controllo completo."""
    pdb, motore = viste.percorso_database()
    if request.method == 'POST':
        if not pdb:
            flash('Il database non è un file: il controllo non si può fare.', 'errore')
            return redirect(url_for('autoriparazione'))
        ses().close()
        autoripara.controlla_lavori()
        autoripara.controlla_spazio(os.path.dirname(pdb))
        try:
            esito, evento = autoripara.controlla_e_ripara(pdb, motore, LUCCHETTO, dopo=dopo_riparazione,
                                                         completo=True)
        except Exception as e:
            logging.exception('controllo del programma')
            flash('Il controllo non è riuscito: %s' % e, 'errore')
            return redirect(url_for('autoriparazione'))
        if evento:
            flash(evento['testo'], 'errore' if evento['livello'] == 'errore' else 'ok')
        elif esito == 'ok':
            flash('Controllo fatto: il database è integro.', 'ok')
        elif esito == 'occupato':
            flash('Il database in questo momento è occupato da un altro programma: riprovare fra poco.', 'errore')
        else:
            flash('Il database ha un problema che non si è riparato: chiamare l\'assistenza.', 'errore')
        return redirect(url_for('autoriparazione'))
    if pdb and autoripara.stato.get('spazio_libero') is None:
        autoripara.controlla_spazio(os.path.dirname(pdb))
    st = autoripara.stato
    return render_template('autoriparazione.html', problemi=autoripara.problemi_attuali(),
                           esito_db=st.get('esito_db'), controllo_db=st.get('controllo_db'), percorso_db=pdb,
                           backup=backup.stato, allarme=backup.allarme(), lavori=autoripara.lavori(),
                           spazio=st.get('spazio_libero'), porta=st.get('porta') or autoripara.PORTA,
                           eventi=autoripara.eventi()[:30], sid=None, sezione='impostazioni')


def porta_in_uso(porta):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def prepara_registro():
    """Il programma gira senza finestra: gli errori devono finire su file.
    Dalla 1.11 il registro non cresce per sempre: oltre 5 MB diventa
    gestionale.log.1 (e il .1 il .2, fino al .3) e se ne comincia uno nuovo."""
    cartella = os.path.dirname(percorso_db())
    percorso = os.path.join(cartella, "gestionale.log")
    gestore = RotatingFileHandler(percorso, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    # force: il registro va sempre sul file, anche se prima qualcuno ha gia' scritto a video
    logging.basicConfig(level=logging.INFO, handlers=[gestore], force=True,
                        format="%(asctime)s %(levelname)s %(message)s")
    return percorso


def crea_server(porta, riserva=()):
    """Il server, gia' in ascolto: (server, porta). Se la porta non si puo'
    usare (presa da un altro programma, o riservata da Windows: Hyper-V e WSL
    si tengono intere fasce di porte) si prova la prossima di 'riserva'."""
    from waitress import create_server
    candidate = [porta] + [x for x in riserva if x != porta]
    for i, p in enumerate(candidate):
        try:
            return create_server(app, sockets=[presa_in_ascolto(p)], threads=FILI), p
        except OSError as e:
            logging.warning("porta %d non utilizzabile: %s", p, e)
            if i == len(candidate) - 1:
                raise


def presa_in_ascolto(porta):
    """Il socket del server, legato a 127.0.0.1 (solo loopback: il gestionale
    non e' raggiungibile dalla rete). Lo crea il programma e non waitress
    perche' waitress mette sempre SO_REUSEADDR, che su Windows lascia legare
    una porta gia' in uso da un altro programma (due server sulla stessa
    porta, risponde l'uno o l'altro): senza, la porta occupata da' errore e
    si passa alla prossima. Su Linux invece SO_REUSEADDR serve a riprendere la
    porta subito dopo una chiusura e non permette due server insieme."""
    presa = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != 'nt':
            presa.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        presa.bind(("127.0.0.1", porta))
    except OSError:
        presa.close()
        raise
    return presa


def avvia(porta=5000, apri=True, riserva=(), pronto=None):
    """Avvia il server e resta li' finche' il programma gira. Il browser si apre
    solo dopo che la porta e' presa: prima, se la porta non si poteva usare,
    si apriva una pagina che non rispondeva. pronto(porta) si chiama appena il
    server e' in ascolto, prima di servire."""
    server, porta = crea_server(porta, riserva)
    indirizzo = "http://127.0.0.1:%d/" % porta
    if pronto is not None:
        pronto(porta)
    if apri:   # con un ritardo, il tempo che il server cominci a rispondere
        threading.Timer(1.5, webbrowser.open, [indirizzo]).start()
    logging.info("avvio su %s", indirizzo)
    server.run()


def dopo_riparazione():
    """Dopo una riparazione a programma aperto (autoripara): il database torna
    alla versione del programma, come dopo un ripristino dalle impostazioni
    (la copia di sicurezza rimessa puo' essere di una versione vecchia)."""
    _, aggiunte, note = aggiorna_database(Sessione.motore)
    for nota in note:
        logging.info("aggiornamento del database dopo la riparazione: %s", nota)
    s = Sessione()
    try:
        servizi.dopo_aggiornamento(s, aggiunte)
    finally:
        s.close()


def avvia_lavori():
    """I lavori in sottofondo (una copia sola del programma li fa): backup,
    messaggi, aggiornamenti; e il custode, che li tiene vivi e controlla il
    database (autoripara)."""
    pdb = percorso_db()
    filo_backup = [backup.avvia_automatico(pdb, viste.cartella_backup)]

    def riavvia_backup():
        filo_backup[0] = backup.avvia_automatico(pdb, viste.cartella_backup, attesa_iniziale=5)
        return filo_backup[0]
    autoripara.sorveglia('backup', lambda: filo_backup[0], riavvia_backup)
    invii.avvia(lambda: Sessione())
    autoripara.sorveglia('invii', lambda: invii._thread, lambda: invii.avvia(lambda: Sessione()))
    aggiornamenti.avvia(lambda: Sessione())
    autoripara.sorveglia('aggiornamenti', lambda: aggiornamenti._thread,
                         lambda: aggiornamenti.avvia(lambda: Sessione()))
    autoripara.avvia_custode(pdb, Sessione.motore, LUCCHETTO, dopo=dopo_riparazione)


def comando_riavvio():
    """Come far ripartire questo programma (autoripara.riavvia_programma)."""
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--avvio-automatico']
    return [sys.executable, os.path.abspath(__file__), '--avvio-automatico']


def richieste_ferme():
    """Da quanti secondi e' in corso ciascuna pagina che si sta servendo."""
    adesso = monotonic()
    return [adesso - inizio for inizio, _ in list(_in_corso.values())]


def risorse_presenti():
    """I file del programma ci sono? L'eseguibile li apre in una cartella
    temporanea di Windows, che la pulizia del disco puo' cancellare."""
    return os.path.isfile(os.path.join(app.template_folder, 'base.html')) and \
        os.path.isfile(os.path.join(app.static_folder, 'stile.css'))


PAGINA_AVVIO_NON_RIUSCITO = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<title>Gestionale Agende: il programma non è partito</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:42em;margin:4em auto;padding:0 1em;line-height:1.5;color:#1d2433}
code{background:#f1f3f5;padding:1px 4px}</style></head><body>
<h1>Il programma non è partito</h1>
<p>Il Gestionale Agende non si è aperto per un errore. I dati sono al sicuro: il database e le copie di sicurezza
non sono stati toccati.</p>
<p>Provare a riavviare il computer e a riaprire il programma dall'icona <b>Agende</b>. Se succede ancora, chiamare
l'assistenza: il dettaglio dell'errore è nel registro <code>%(registro)s</code>.</p>
<p style="color:#5b6b75">Errore: %(errore)s</p></body></html>"""


def avvio_non_riuscito(registro, errore):
    """Il programma gira senza finestra: se non parte, la segreteria non vede
    niente (o una finestra di errore in inglese). Una pagina in parole semplici
    accanto al registro, aperta nel browser."""
    from html import escape
    try:
        percorso = os.path.join(os.path.dirname(registro), 'avvio-non-riuscito.html')
        with open(percorso, 'w', encoding='utf-8') as f:
            f.write(PAGINA_AVVIO_NON_RIUSCITO % {'registro': escape(registro), 'errore': escape(str(errore)[:300])})
        webbrowser.open('file:///' + percorso.replace('\\', '/').lstrip('/'))
    except Exception:
        logging.exception("pagina dell'avvio non riuscito")


def principale():
    global Sessione, _lucchetto_istanza
    registro = prepara_registro()
    # dall'avvio automatico di Windows parte in silenzio, senza aprire il
    # browser a ogni accesso: la pagina la apre l'icona sul desktop
    apri = "--avvio-automatico" not in sys.argv
    try:
        cartella = os.path.dirname(percorso_db())
        # c'e' gia' un gestionale aperto? Se risponde si apre solo la pagina (la
        # segreteria ha cliccato due volte); se e' bloccato si chiude e si riparte
        ingresso = autoripara.entra(cartella)
        if not ingresso['principale']:
            logging.info("gestionale gia aperto sulla porta %d (%s): apro solo il browser",
                         ingresso['porta'], ingresso['nota'])
            if apri:
                webbrowser.open("http://127.0.0.1:%d/" % ingresso['porta'])
            return
        _lucchetto_istanza = ingresso['lucchetto']   # resta aperto finche' il programma gira
        porta = ingresso['porta']
        # il database si controlla (e se serve si ripara) prima di aprirlo
        autoripara.all_avvio(percorso_db())
        Sessione = crea_sessione()
        if Sessione.versione_precedente is not None and Sessione.versione_precedente > VERSIONE_SCHEMA:
            # un database di una versione piu' nuova (il programma rimesso indietro): funziona, ma va detto
            autoripara.stato['schema_nuovo'] = Sessione.versione_precedente
        if Sessione.colonne_aggiunte:
            logging.info("database aggiornato, colonne aggiunte: %s", ", ".join(Sessione.colonne_aggiunte))
        for nota in Sessione.migrazioni:
            logging.info("aggiornamento del database: %s", nota)
        s = Sessione()
        for nome in servizi.dopo_aggiornamento(s, Sessione.colonne_aggiunte):
            logging.info("logo della versione precedente copiato nella struttura %s", nome)
        for nome in servizi.email_della_struttura(s, Sessione.colonne_aggiunte):
            logging.info("email della struttura %s impostata", nome)
        for nome in servizi.logo_nuovo(s, Sessione.colonne_aggiunte):
            logging.info("logo nuovo (Longevity Institute) nella struttura %s", nome)
        nuova = servizi.prepara_primo_avvio(s)
        if nuova:
            logging.info("primo avvio: creata la struttura %s con le stanze iniziali", nuova.nome)
        # versione avviata (per le novita'), esito di un "Aggiorna adesso", Setup vecchi
        try:
            for nota in aggiornamenti.dopo_avvio(s):
                logging.info("aggiornamenti: %s", nota)
        except Exception:
            s.rollback()
            logging.exception("aggiornamenti: controllo all'avvio")
        try:
            # fuori dal database, per trovare le copie anche quando il database non si legge
            autoripara.ricorda(cartella_backup=leggi_impostazione(s, 'backup_cartella', ''),
                               ultimo_avvio=datetime.now().isoformat(timespec='seconds'))
        except Exception:
            logging.exception("autoriparazione: diario")
        s.close()
        autoripara.imposta_riavvio(comando_riavvio(), occupato=lambda: bool(aggiornamenti.stato.get('partito')),
                                   ferme=richieste_ferme, risorse=risorse_presenti, fili=FILI)
        avvia_lavori()

        def pronto(p):
            autoripara.stato['porta'] = p
            autoripara.scrivi_pid(cartella, p, 'in servizio')
            if p != porta:
                autoripara.annota('La porta %d non si poteva usare: il gestionale si apre su http://127.0.0.1:%d/.'
                                  % (porta, p), 'attenzione')
        avvia(porta=porta, apri=apri, riserva=[p for p in autoripara.PORTE_DI_RISERVA if p != porta], pronto=pronto)
    except Exception as e:
        logging.exception("avvio non riuscito")
        print("Avvio non riuscito. Dettagli in %s" % registro)
        if apri:
            avvio_non_riuscito(registro, e)
        raise


if __name__ == "__main__":
    principale()
