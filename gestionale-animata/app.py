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

from modelli import (crea_sessione, percorso_db, cartella_risorse, Struttura, Risorsa, Operatore,
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


def porta_in_uso(porta):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def prepara_registro():
    """Il programma gira senza finestra: gli errori devono finire su file."""
    cartella = os.path.dirname(percorso_db())
    logging.basicConfig(
        filename=os.path.join(cartella, "gestionale.log"),
        level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s")
    return os.path.join(cartella, "gestionale.log")


def avvia(porta=5000, apri=True):
    from waitress import serve
    indirizzo = "http://127.0.0.1:%d/" % porta

    # doppio avvio: non e' un errore, la segreteria ha solo cliccato due volte
    if porta_in_uso(porta):
        if apri:
            logging.info("gia in esecuzione sulla porta %d, apro solo il browser", porta)
            webbrowser.open(indirizzo)
        return

    if apri:   # con un ritardo, altrimenti il browser trova la porta chiusa
        threading.Timer(1.5, webbrowser.open, [indirizzo]).start()
    logging.info("avvio su %s", indirizzo)
    # solo loopback: il gestionale non e raggiungibile dalla rete
    serve(app, host="127.0.0.1", port=porta, threads=4)


def principale():
    global Sessione
    registro = prepara_registro()
    try:
        Sessione = crea_sessione()
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
        primo = not porta_in_uso(5000)
        if primo:
            # versione avviata (per le novita'), esito di un "Aggiorna adesso", Setup vecchi
            try:
                for nota in aggiornamenti.dopo_avvio(s):
                    logging.info("aggiornamenti: %s", nota)
            except Exception:
                s.rollback()
                logging.exception("aggiornamenti: controllo all'avvio")
        s.close()
        if primo:
            # una sola copia fa i backup, manda i messaggi e guarda gli aggiornamenti:
            # la seconda istanza apre solo il browser
            backup.avvia_automatico(percorso_db(), viste.cartella_backup)
            invii.avvia(lambda: Sessione())
            aggiornamenti.avvia(lambda: Sessione())
        # dall'avvio automatico di Windows parte in silenzio, senza aprire il
        # browser a ogni accesso: la pagina la apre l'icona sul desktop
        avvia(apri="--avvio-automatico" not in sys.argv)
    except Exception:
        logging.exception("avvio non riuscito")
        print("Avvio non riuscito. Dettagli in %s" % registro)
        raise


if __name__ == "__main__":
    principale()
