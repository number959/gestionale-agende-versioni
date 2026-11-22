# -*- coding: utf-8 -*-
"""Accesso dagli altri PC della rete (BOZZA, M2-bis, 22/11/2026).

Il PC principale (la segreteria) apre il programma da http://127.0.0.1:5000 e non cambia niente: nessun accesso,
tutte le pagine. Se in *Configura → Aree e accessi* si accende l'accesso dalla rete, il programma ascolta ANCHE su
0.0.0.0:<porta della rete> (5080 di partenza). Chi arriva da lì deve entrare con nome e password, e vede solo le aree
che gli sono state date: «non disponibile», «solo guardare» (solo pagine e file, niente salvataggi) o «guardare e
modificare». Alcune cose restano sempre e solo sul PC principale (il «Sistema»): aggiornamenti, copie e ripristino,
controllo del programma, chiusura e questa stessa pagina degli accessi.

Conta come «dalla rete» una richiesta che:
- arriva dalla presa della rete (la segna AscoltoRete con environ['gestionale.presa_rete']);
- porta X-Forwarded-For o Forwarded (un portiere, per esempio Caddy, sullo stesso PC);
- arriva da un indirizzo che non e' del PC (la presa principale e' legata a 127.0.0.1: non dovrebbe succedere mai).

Tutto sta fra le impostazioni (coppie nome-valore, schema 12): rete_accesa, rete_porta, rete_schermo_libero,
rete_nomi (altri nomi con cui gli altri PC chiamano questo), rete_utenti (JSON). La chiave che firma i cookie e'
casuale, una per installazione, in un file accanto al database (non nelle copie di sicurezza).
"""
import collections
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit

from flask import (Blueprint, Response, current_app, flash, redirect, render_template, request, session,
                   url_for)
from flask import g as contesto
from flask.sessions import SecureCookieSessionInterface
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('accessi', __name__)
registro = logging.getLogger('gestionale.accessi')

# ------------------------------------------------------------------ aree
# Le aree che si danno a un utente: il nucleo diviso in quattro, piu' gli otto moduli del piano.
AREE = (
    ('agenda', 'Agenda', 'Oggi, giorno, settimana, mese, prenotazioni, stampe del giorno'),
    ('pazienti', 'Pazienti', 'schede, documenti, codici fiscali'),
    ('configura', 'Configura e anagrafiche', 'stanze, medici, turni dei medici, prestazioni, strutture, importa, '
                                             'moduli da stampare'),
    ('guida', 'Guida e aiuto', 'le guide e le novità'),
    ('turni', 'Turni', 'turni del personale'),
    ('cassa', 'Cassa', 'incassi, listino, tariffari'),
    ('dove', 'Dove si fa', 'ricerca, registro, strutture del gruppo'),
    ('comunicazioni', 'Comunicazioni', 'email e WhatsApp'),
    ('statistiche', 'Statistiche e report', 'statistiche, riepilogo dei medici, esportazioni'),
    ('ambulatori', 'Ambulatori e dashboard', 'pianificazione, programmazione, riepiloghi, dashboard'),
    ('sala', 'Sala', 'sala operatoria, lista operatoria, posti letto'),
    ('segreteria', 'Segreteria', "conferme, da confermare, chiusura, da fare, lista d'attesa"),
)
NOMI_AREE = {a: n for a, n, _ in AREE}
LIVELLI = (('no', 'non disponibile'), ('guarda', 'solo guardare'), ('modifica', 'guardare e modificare'))

LIBERO, SISTEMA, SCHERMO, TRASVERSALE = 'libero', 'sistema', 'schermo', 'trasversale'

# L'area di ogni pagina (endpoint di Flask). Una pagina che manca qui, dalla rete, e' trattata come Sistema
# (rifiutata): la prova prove_accessi.py controlla che non ne manchi nessuna. Con M1 ogni modulo dichiarera' le
# sue pagine da se'; per la bozza stanno tutte qui.
AREA = {
    # sempre aperte (servono alla pagina di accesso, nessun dato)
    'static': LIBERO, 'logo': LIBERO, 'accessi.accesso': LIBERO, 'accessi.esci': LIBERO, 'home': LIBERO,
    # solo sul PC principale, anche per chi ha tutto
    'salute': SISTEMA, 'autoriparazione': SISTEMA, 'aggiornamenti.pagina': SISTEMA,
    'aggiornamenti.aggiorna': SISTEMA, 'aggiornamenti.piu_tardi': SISTEMA, 'aggiornamenti.stato_json': SISTEMA,
    'viste.impostazioni': SISTEMA, 'viste.scarica_backup': SISTEMA, 'viste.ripristina': SISTEMA,
    'accessi.pagina': SISTEMA,
    # Modo schermo: libero se la clinica lo vuole, altrimenti area Ambulatori e dashboard
    'live.pagina': SCHERMO, 'live.dati': SCHERMO, 'live.statistiche': SCHERMO, 'live.statistiche_json': SCHERMO,
    # trasversali: con l'accesso, il contenuto si filtra per area (notifiche, ricerca rapida del menu)
    'segreteria.notifiche': TRASVERSALE, 'segreteria.cerca_tutto': TRASVERSALE,
    # Agenda
    'cruscotto.oggi': 'agenda', 'giorno': 'agenda', 'viste.settimana': 'agenda', 'viste.mese': 'agenda',
    'viste.elenco_giorno': 'agenda', 'viste.stampa': 'agenda', 'esporta': 'agenda', 'appuntamento': 'agenda',
    'cambia_stato': 'agenda', 'segreteria.sposta': 'agenda', 'segreteria.sposta_blocco': 'agenda',
    'segreteria.avvisa_spostati': 'agenda', 'segreteria.serie': 'agenda', 'segreteria.salva_nota': 'agenda',
    'segreteria.agenda_medico': 'agenda', 'viste.disponibilita': 'agenda', 'viste.promemoria': 'agenda',
    'documenti.stampa_modulo': 'agenda',
    # Pazienti
    'pazienti.elenco': 'pazienti', 'pazienti.scheda': 'pazienti', 'pazienti.unisci_pagina': 'pazienti',
    'pazienti.cerca_json': 'pazienti', 'pazienti.codice_fiscale_json': 'pazienti', 'pazienti.luoghi_json': 'pazienti',
    'pazienti.codici_fiscali': 'pazienti', 'documenti.mostra_documento': 'pazienti',
    'documenti.carica_documento': 'pazienti', 'documenti.elimina_documento': 'pazienti',
    # Configura e anagrafiche
    'anagrafiche.elenco': 'configura', 'anagrafiche.medico': 'configura', 'anagrafiche.stanza': 'configura',
    'anagrafiche.prestazione': 'configura', 'anagrafiche.turno': 'configura', 'anagrafiche.struttura': 'configura',
    'anagrafiche.assenza': 'configura', 'anagrafiche.chiusura': 'configura', 'importa.carica': 'configura',
    'importa.anteprima': 'configura', 'importa.scarti': 'configura', 'documenti.moduli': 'configura',
    'documenti.modulo': 'configura',
    # Guida e aiuto
    'guida.indice': 'guida', 'guida.articolo': 'guida', 'guida.passi_json': 'guida', 'guida.stampa': 'guida',
    'aggiornamenti.novita_pagina': 'guida',
    # Turni
    'personale.persone': 'turni', 'personale.persona': 'turni', 'personale.medici_dall_agenda': 'turni',
    'personale.tipi_turno': 'turni', 'personale.turni': 'turni', 'personale.cambia': 'turni', 'personale.copia': 'turni',
    'personale.giorno': 'turni', 'personale.mese': 'turni', 'personale.mese_excel': 'turni', 'personale.schema': 'turni',
    'personale.settimana': 'turni',
    # Cassa
    'cassa.cassa_giorno': 'cassa', 'cassa.cassa_mese': 'cassa', 'cassa.cassa_mese_excel': 'cassa',
    'cassa.listino': 'cassa', 'cassa.pagamento': 'cassa', 'tariffari.elenco': 'cassa', 'tariffari.scheda': 'cassa',
    'tariffari.stampa': 'cassa', 'tariffari.anteprima': 'cassa',
    # Dove si fa
    'dovesifa.pagina': 'dove', 'dovesifa.cerca_json': 'dove', 'dovesifa.risultati': 'dove', 'dovesifa.scheda': 'dove',
    'dovesifa.stampa': 'dove', 'dovesifa.indirizza': 'dove', 'dovesifa.togli': 'dove', 'dovesifa.registro': 'dove',
    'dovesifa.registro_excel': 'dove', 'dovesifa.strutture': 'dove', 'dovesifa.struttura': 'dove',
    'dovesifa.anteprima': 'dove',
    # Comunicazioni
    'invii.pagina': 'comunicazioni', 'invii.regola': 'comunicazioni', 'invii.allegato': 'comunicazioni',
    'invii.appuntamento': 'comunicazioni',
    # Statistiche e report
    'viste.statistiche': 'statistiche', 'viste.statistiche_excel': 'statistiche', 'cruscotto.riepilogo': 'statistiche',
    'cruscotto.riepilogo_excel': 'statistiche', 'esportazioni.pagina': 'statistiche',
    'esportazioni.scarica': 'statistiche',
    # Ambulatori e dashboard
    'ambulatori.inizio': 'ambulatori', 'ambulatori.settimana': 'ambulatori', 'ambulatori.settimana_excel': 'ambulatori',
    'ambulatori.mese': 'ambulatori', 'ambulatori.mese_excel': 'ambulatori', 'ambulatori.metti': 'ambulatori',
    'ambulatori.togli': 'ambulatori', 'ambulatori.riepilogo': 'ambulatori', 'ambulatori.riepilogo_excel': 'ambulatori',
    'ambulatori.riepilogo_json': 'ambulatori',
    # Sala
    'sala.giornata': 'sala', 'sala.lista_operatoria': 'sala', 'sala.posti_letto': 'sala', 'sala.chirurghi': 'sala',
    'sala.checklist': 'sala', 'sala.salva_voci': 'sala',
    # Segreteria
    'viste.conferme': 'segreteria', 'segreteria.da_confermare': 'segreteria', 'segreteria.appunto_azione': 'segreteria',
    'segreteria.prenota_appunti': 'segreteria', 'segreteria.chiusura': 'segreteria',
    'segreteria.cose_da_fare': 'segreteria', 'segreteria.cosa_fatta': 'segreteria', 'segreteria.attesa': 'segreteria',
    'segreteria.attesa_scheda': 'segreteria', 'segreteria.attesa_per': 'segreteria',
}

# la prima pagina da aprire dopo l'accesso, area per area (nell'ordine di AREE)
PRIMA_PAGINA = {'agenda': 'cruscotto.oggi', 'pazienti': 'pazienti.elenco', 'configura': 'anagrafiche.elenco',
                'guida': 'guida.indice', 'turni': 'personale.turni', 'cassa': 'cassa.listino',
                'dove': 'dovesifa.pagina', 'comunicazioni': 'invii.pagina', 'statistiche': 'viste.statistiche',
                'ambulatori': 'ambulatori.inizio', 'sala': 'sala.posti_letto', 'segreteria': 'viste.conferme'}

PORTA_RETE = 5080
FILI_RETE = 4                   # le richieste dalla rete che si servono insieme: fili loro, non quelli del PC
MASSIMO_TENTATIVI = 5           # password sbagliate di fila...
FINESTRA_TENTATIVI = 15 * 60    # ...in un quarto d'ora: poi si aspetta un quarto d'ora
INATTIVITA = 4 * 3600           # dopo 4 ore senza usarlo si rientra
DURATA_MASSIMA = 12 * 3600      # e comunque dopo 12 ore
COOKIE_RETE = 'gestionale_rete'
LOOPBACK = ('127.', '::1', '::ffff:127.')
NOME_VALIDO = re.compile(r'[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9 ._-]{1,39}')
HASH_FINTO = generate_password_hash(secrets.token_hex(8))   # per un nome che non c'e': stesso tempo di risposta


# --------------------------------------------------- da dove arriva la richiesta
def dalla_rete(environ=None):
    """True se la richiesta non e' del PC principale (vedi in testa al file)."""
    e = environ if environ is not None else request.environ
    if e.get('gestionale.presa_rete'):
        return True
    if e.get('HTTP_X_FORWARDED_FOR') or e.get('HTTP_FORWARDED'):
        return True
    return not str(e.get('REMOTE_ADDR') or '127.0.0.1').startswith(LOOPBACK)


def indirizzo_chi_chiama():
    """L'indirizzo del PC che chiama: dietro un portiere sullo stesso PC, l'ultimo di X-Forwarded-For."""
    e = request.environ
    remoto = e.get('REMOTE_ADDR') or ''
    inoltrato = (e.get('HTTP_X_FORWARDED_FOR') or '').split(',')[-1].strip()
    if inoltrato and remoto.startswith(LOOPBACK):
        return inoltrato[:64]
    return remoto[:64]


# ------------------------------------------------------------- impostazioni
def configurazione(s):
    from modelli import leggi_impostazione
    try:
        utenti = json.loads(leggi_impostazione(s, 'rete_utenti', '[]') or '[]')
    except ValueError:
        logging.error('accessi: rete_utenti non si legge: nessun utente dalla rete')
        utenti = []
    porta = leggi_impostazione(s, 'rete_porta', '')
    return {'accesa': leggi_impostazione(s, 'rete_accesa', '') == '1',
            'porta': int(porta) if porta.isdigit() else PORTA_RETE,
            'schermo_libero': leggi_impostazione(s, 'rete_schermo_libero', '1') == '1',
            'nomi': [x for x in (leggi_impostazione(s, 'rete_nomi', '') or '').split() if x],
            'utenti': [u for u in utenti if isinstance(u, dict) and u.get('nome')]}


def salva_utenti(s, utenti):
    from modelli import scrivi_impostazione
    scrivi_impostazione(s, 'rete_utenti', json.dumps(utenti, ensure_ascii=False))


def trova(utenti, nome):
    chiave = (nome or '').strip().casefold()
    return next((u for u in utenti if u['nome'].casefold() == chiave), None)


def livello(utente, area):
    if area in (SISTEMA, None):
        return 'no'                     # il Sistema non si da' a nessuno, nemmeno scritto a mano nel JSON
    if area == LIBERO:
        return 'modifica'
    v = (utente or {}).get('aree', {}).get(area, 'no')
    return v if v in ('guarda', 'modifica') else 'no'


def area_di(endpoint):
    return AREA.get(endpoint, SISTEMA)


def area_di_indirizzo(indirizzo, metodo='GET'):
    """L'area di un collegamento interno (per filtrare notifiche e ricerca), o None."""
    parti = urlsplit(indirizzo or '')
    if parti.scheme or parti.netloc:
        return None
    try:
        endpoint, _ = current_app.url_map.bind('x').match(parti.path, method=metodo)
    except HTTPException:
        return None
    return area_di(endpoint)


def chiave_sessione(cartella):
    """La chiave che firma i cookie: casuale, una per installazione, in un file accanto al database. Se il file
    non si puo' scrivere vale finche' il programma resta aperto (dopo, chi e' dalla rete rientra)."""
    percorso = os.path.join(cartella, 'chiave-sessione')
    try:
        with open(percorso, 'rb') as f:
            chiave = f.read()
        if len(chiave) >= 32:
            return chiave
    except OSError:
        pass
    chiave = secrets.token_bytes(32)
    try:
        provvisorio = percorso + '.nuova'
        with open(provvisorio, 'wb') as f:
            f.write(chiave)
        os.replace(provvisorio, percorso)
    except OSError:
        logging.exception('accessi: chiave della sessione non salvata')
    return chiave


class SessioniDueNomi(SecureCookieSessionInterface):
    """Il cookie della rete ha un nome suo e SameSite=Strict: sul PC principale 127.0.0.1:5000 e 127.0.0.1:5080
    condividerebbero lo stesso cookie (i cookie non guardano la porta)."""

    def get_cookie_name(self, app):
        return COOKIE_RETE if dalla_rete() else super().get_cookie_name(app)

    def get_cookie_samesite(self, app):
        return 'Strict' if dalla_rete() else super().get_cookie_samesite(app)


# ---------------------------------------------------------------- tentativi
_tentativi = collections.defaultdict(collections.deque)
_lucchetto_tentativi = threading.Lock()
eventi = collections.deque(maxlen=200)       # gli ultimi accessi, per la pagina (anche nel file accessi.log)


def annota(testo, nome='', livello_log=logging.INFO):
    riga = (datetime.now().strftime('%d/%m %H:%M:%S'), nome, indirizzo_chi_chiama() if request else '', testo)
    eventi.appendleft(riga)
    registro.log(livello_log, '%s utente=%r da=%s', testo, nome, riga[2])


def bloccato(*chiavi):
    """Secondi da aspettare se una delle chiavi (indirizzo, nome) ha sbagliato troppe volte, altrimenti 0."""
    adesso = time.monotonic()
    with _lucchetto_tentativi:
        attesa = 0
        for k in chiavi:
            coda = _tentativi[k]
            while coda and adesso - coda[0] > FINESTRA_TENTATIVI:
                coda.popleft()
            if len(coda) >= MASSIMO_TENTATIVI:
                attesa = max(attesa, int(FINESTRA_TENTATIVI - (adesso - coda[-1])) + 1)
        return attesa


def sbagliato(*chiavi):
    with _lucchetto_tentativi:
        for k in chiavi:
            _tentativi[k].append(time.monotonic())


def riuscito(*chiavi):
    with _lucchetto_tentativi:
        for k in chiavi:
            _tentativi.pop(k, None)


# ------------------------------------------------------------ chi e' entrato
def utente_di_sessione(cfg):
    nome = session.get('utente')
    if not nome:
        return None
    u = trova(cfg['utenti'], nome)
    adesso = time.time()
    if u is None or not u.get('attivo', True) or session.get('v') != u.get('versione', 0) or \
            adesso - session.get('ultimo', 0) > INATTIVITA or adesso - session.get('dal', 0) > DURATA_MASSIMA:
        session.clear()
        return None
    if adesso - session.get('ultimo', 0) > 60:      # non riscrivere il cookie a ogni richiesta
        session['ultimo'] = adesso
    return u


def prima_pagina(utente):
    for area, _, _ in AREE:
        if livello(utente, area) != 'no':
            return url_for(PRIMA_PAGINA[area])
    return url_for('accessi.accesso', nessuna=1)


def vuole_json():
    return request.path.endswith('.json') or request.headers.get('X-Richiesta') or \
        request.accept_mimetypes.best == 'application/json'


PAGINA_NO = '''<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Non disponibile</title>
<link rel="stylesheet" href="/static/stile.css"></head><body><div class="pagina" style="max-width:40em;margin:4em auto">
<h1>{{ titolo }}</h1><p>{{ motivo }}</p>
<p>{% if utente %}Si è entrati come <b>{{ utente }}</b>. {% endif %}Per avere anche questa parte, chiedere a chi usa il
PC della segreteria (<i>Configura → Aree e accessi</i>).</p>
<p>{% if torna %}<a class="bottone" href="{{ torna }}">Torna alle pagine disponibili</a>{% endif %}
{% if utente %}<form method="post" action="{{ url_for('accessi.esci') }}" style="display:inline">
<button class="bottone">Esci</button></form>{% endif %}</p></div></body></html>'''


def rifiuta(motivo, titolo='Questa parte non è disponibile', utente=None, codice=403):
    from flask import render_template_string
    if vuole_json():
        return Response(json.dumps({'errore': motivo}, ensure_ascii=False), status=codice,
                        mimetype='application/json')
    return Response(render_template_string(PAGINA_NO, titolo=titolo, motivo=motivo,
                                           utente=utente['nome'] if utente else '',
                                           torna=prima_pagina(utente) if utente else ''),
                    status=codice, mimetype='text/html')


# ------------------------------------------------------------- il controllo
def controlla_accesso():
    """before_request: sul PC principale non fa niente (e non apre il database: /salute deve rispondere anche
    a database fermo). Dalla rete: accesso, area e livello."""
    if not dalla_rete():
        return None
    endpoint = request.endpoint
    if endpoint is None:            # 404 o 405: risponde Flask, senza dire di piu'
        return None
    area = area_di(endpoint)
    if area == SISTEMA:             # prima di leggere qualsiasi cosa
        if endpoint not in AREA:
            logging.warning('accessi: la pagina %s non ha un\'area: rifiutata dalla rete', endpoint)
        return rifiuta('Questa pagina si apre solo dal PC della segreteria.', titolo='Solo dal PC della segreteria')
    if endpoint in ('static', 'logo'):
        return None                 # file del programma e logo: nessun dato
    from app import ses
    cfg = configurazione(ses())
    contesto.accessi_cfg = cfg
    if not host_valido_dalla_rete(request.host, cfg['nomi'], cfg['porta']):
        # come NOMI_LOCALI per il PC principale: un nome di un altro sito che punta qui (DNS rebinding) non passa
        return Response('Indirizzo non valido: dagli altri PC il gestionale si apre con il nome o l\'indirizzo del '
                        'PC della segreteria.', status=400, mimetype='text/plain')
    if area == SCHERMO and cfg['schermo_libero'] and request.method in ('GET', 'HEAD'):
        return None
    if not cfg['accesa']:
        return rifiuta("L'accesso dagli altri PC è spento.", titolo='Accesso dalla rete spento', codice=403)
    if endpoint in ('accessi.accesso', 'accessi.esci'):
        return None
    utente = utente_di_sessione(cfg)
    if utente is None:
        if vuole_json():
            return rifiuta('Bisogna entrare con nome e password.', titolo='Accesso', codice=401)
        dopo = request.full_path.rstrip('?') if request.method == 'GET' else ''
        return redirect(url_for('accessi.accesso', dopo=dopo or None))
    contesto.utente_rete = utente
    if endpoint == 'home':
        return redirect(prima_pagina(utente))
    if area == SCHERMO:
        area = 'ambulatori'
    if area == TRASVERSALE:
        return None                 # il contenuto si filtra in dopo_la_risposta
    lv = livello(utente, area)
    if lv == 'no':
        annota('negato %s %s' % (request.method, request.path), utente['nome'], logging.WARNING)
        return rifiuta('«%s» non è fra le parti disponibili per questo utente.' % NOMI_AREE.get(area, area),
                       utente=utente)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if lv != 'modifica':
            annota('negato (solo guardare) %s %s' % (request.method, request.path), utente['nome'], logging.WARNING)
            return rifiuta('Per «%s» questo utente può solo guardare: non si salva niente.'
                           % NOMI_AREE.get(area, area), titolo='Solo guardare', utente=utente)
        annota('%s %s' % (request.method, request.path), utente['nome'])      # chi ha cambiato cosa
    return None


def _filtra(dati, utente):
    """Toglie dai JSON trasversali le voci che portano a pagine non disponibili, e i bottoni (POST) di aree
    dove si puo' solo guardare."""
    if isinstance(dati, list):
        return [x for x in (_filtra(v, utente) for v in dati) if x is not None]
    if isinstance(dati, dict):
        indirizzo = dati.get('url') or dati.get('link')
        if indirizzo and livello(utente, area_di_indirizzo(indirizzo)) == 'no':
            return None
        uscita = {}
        for k, v in dati.items():
            if k == 'azioni' and isinstance(v, list):
                v = [a for a in v if isinstance(a, dict) and livello(utente, area_di_indirizzo(a.get('url'), 'POST'))
                     == 'modifica']
            else:
                v = _filtra(v, utente)
            uscita[k] = v
        return uscita
    return dati


def dopo_la_risposta(risposta):
    if not dalla_rete():
        return risposta
    if request.endpoint not in ('static', 'logo'):
        # sul PC di un altro reparto la pagina non deve restare nella cache del browser
        risposta.headers['Cache-Control'] = 'no-store'
    risposta.headers.setdefault('X-Content-Type-Options', 'nosniff')
    risposta.headers.setdefault('Referrer-Policy', 'same-origin')
    utente = getattr(contesto, 'utente_rete', None)
    if utente is not None and area_di(request.endpoint) == TRASVERSALE and risposta.mimetype == 'application/json':
        dati = _filtra(json.loads(risposta.get_data(as_text=True)), utente)
        testo = json.dumps(dati, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e') \
            .replace('&', '\\u0026')
        risposta.set_data(testo)
    return risposta


# ----------------------------------------------------- nome dell'host e origine
_nomi_del_pc = []


def nomi_del_pc():
    """Come gli altri PC possono chiamare questo: nome, nome completo, indirizzi IPv4 (senza 127.* e 169.254.*)."""
    if _nomi_del_pc:
        return _nomi_del_pc
    nomi = set()
    try:
        nome = socket.gethostname()
        nomi.update({nome.lower(), socket.getfqdn().lower(), nome.lower() + '.local'})
        for info in socket.getaddrinfo(nome, None, socket.AF_INET):
            nomi.add(info[4][0])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
            u.connect(('192.0.2.1', 9))        # non manda niente: serve solo a sapere l'indirizzo di uscita
            nomi.add(u.getsockname()[0])
    except OSError:
        pass
    _nomi_del_pc.extend(sorted(n for n in nomi if n and not n.startswith(('127.', '169.254.'))))
    return _nomi_del_pc


def indirizzi_da_usare(porta):
    """Gli indirizzi da scrivere sugli altri PC: prima il nome del PC, poi gli IP."""
    nome = socket.gethostname()
    ip = [n for n in nomi_del_pc() if re.fullmatch(r'\d+\.\d+\.\d+\.\d+', n)]
    return ['http://%s:%d/' % (nome, porta)] + ['http://%s:%d/' % (x, porta) for x in ip]


def host_valido_dalla_rete(host, cfg_nomi, porta):
    """Il nome con cui e' stata chiamata la pagina (Host) e' di questo PC? Contro il DNS rebinding, come
    NOMI_LOCALI per il PC principale: un altro nome che punta qui non passa."""
    m = re.fullmatch(r'\[?([^\]]+?)\]?(?::(\d{1,5}))?', (host or '').lower())
    if not m:
        return False
    nome, p = m.group(1), int(m.group(2) or 80)
    if nome in ('127.0.0.1', 'localhost'):
        return True
    return p == porta and (nome in nomi_del_pc() or nome in [x.lower() for x in cfg_nomi])


# ------------------------------------------------------------ secondo ascolto
class MarcaRete:
    """Avvolge l'applicazione per la presa della rete: ogni richiesta arrivata di qui e' «dalla rete», qualunque
    indirizzo abbia (anche chi apre http://NOME:5080 dal PC della segreteria)."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['gestionale.presa_rete'] = True
        return self.app(environ, start_response)


def presa_della_rete(porta):
    """La presa su tutte le schede di rete (0.0.0.0). Su Windows SO_EXCLUSIVEADDRUSE (nessun altro programma puo'
    legarsi alla stessa porta su un indirizzo piu' preciso) e niente SO_REUSEADDR, come app.presa_in_ascolto."""
    presa = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt':
            presa.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_EXCLUSIVEADDRUSE', -5), 1)
        else:
            presa.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        presa.bind(('0.0.0.0', porta))
    except OSError:
        presa.close()
        raise
    return presa


def porta_ammessa(porta, principale=5000):
    from autoripara import PORTE_DI_RISERVA
    return 1024 <= porta <= 65535 and porta != principale and porta not in PORTE_DI_RISERVA


class AscoltoRete:
    """Il secondo server di waitress, con fili e mappa sue: si accende e si spegne a programma aperto, e una pagina
    lenta chiesta da un altro PC non ferma mai il PC della segreteria."""

    def __init__(self):
        self.server = None
        self.filo = None
        self.porta = None
        self.errore = ''
        self._lucchetto = threading.Lock()

    def acceso(self):
        return self.server is not None and self.filo is not None and self.filo.is_alive()

    def accendi(self, app, porta):
        from waitress import create_server
        with self._lucchetto:
            if self.acceso() and self.porta == porta:
                return True
            try:
                presa = presa_della_rete(porta)        # prima la presa nuova: se non si puo', resta quella di prima
            except OSError as e:
                self.errore = spiega_errore_porta(porta, e)
                logging.warning('accessi: porta %d della rete non utilizzabile: %s', porta, e)
                return False
            self._spegni()
            self.server = create_server(MarcaRete(app), sockets=[presa], threads=FILI_RETE,
                                        ident='Gestionale Agende')
            self.porta, self.errore = porta, ''
            server = self.server

            def gira():
                try:
                    server.run()
                finally:
                    server.task_dispatcher.shutdown(timeout=5)
            self.filo = threading.Thread(target=gira, name='ascolto-rete', daemon=True)
            self.filo.start()
            logging.info('accessi: in ascolto anche sulla rete, porta %d', porta)
            return True

    def spegni(self):
        with self._lucchetto:
            self._spegni()

    def _spegni(self):
        server, filo = self.server, self.filo
        self.server = self.filo = self.porta = None
        if server is None:
            return
        from waitress import wasyncore
        # la chiusura va fatta dal filo del server (wasyncore non si tocca da due fili): con il «trigger»
        server.trigger.pull_trigger(lambda: wasyncore.close_all(server._map))
        if filo is not None:
            filo.join(10)
        logging.info('accessi: ascolto sulla rete spento')


def spiega_errore_porta(porta, e):
    codice = getattr(e, 'winerror', None) or getattr(e, 'errno', None)
    if codice in (10048, 98, 48):          # in uso
        return 'La porta %d è già usata da un altro programma: sceglierne un\'altra.' % porta
    if codice in (10013, 13):              # vietata (su Windows: una fascia riservata da Hyper-V o WSL)
        return ('Windows non lascia usare la porta %d (può essere riservata, per esempio da Hyper-V): sceglierne '
                'un\'altra, per esempio 8080.' % porta)
    return 'La porta %d non si può usare: %s' % (porta, e)


ascolto = AscoltoRete()


def all_avvio(app, sessione_fabbrica, cartella_dati):
    """Dall'avvio del programma (app.principale), dopo che il server principale e' in ascolto."""
    gestore = logging.handlers.RotatingFileHandler(os.path.join(cartella_dati, 'accessi.log'),
                                                   maxBytes=1024 * 1024, backupCount=3, encoding='utf-8')
    gestore.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    registro.addHandler(gestore)
    s = sessione_fabbrica()
    try:
        cfg = configurazione(s)
    finally:
        s.close()
    if cfg['accesa']:
        if not ascolto.accendi(app, cfg['porta']):
            import autoripara
            autoripara.annota('Accesso dalla rete non partito: %s' % ascolto.errore, 'attenzione')


# ------------------------------------------------------------------ pagine
PAGINA_ACCESSO = '''{% extends "base.html" %}{% block titolo %}Accesso{% endblock %}{% block menu %}{% endblock %}
{% block corpo %}<div class="pagina" style="max-width:28em;margin:3em auto">
<h1>Gestionale Agende</h1>
{% if nessuna %}<p class="avviso errore">Questo utente non ha nessuna parte del programma disponibile.</p>{% endif %}
{% if errore %}<p class="avviso errore" role="alert">{{ errore }}</p>{% endif %}
<form method="post" class="riquadro">
  <input type="hidden" name="dopo" value="{{ dopo }}">
  <p><label>Nome<br><input name="nome" autocomplete="username" required maxlength="40" value="{{ nome }}" autofocus></label></p>
  <p><label>Password<br><input name="password" type="password" autocomplete="current-password" required maxlength="200"></label></p>
  <p><button class="bottone primario">Entra</button></p>
</form>
<p class="nota-riga">Collegamento senza protezione (http): nome, password e dati passano in chiaro nella rete della
clinica. Usarlo solo dai PC della clinica, mai da una rete Wi-Fi aperta.</p>
</div>{% endblock %}'''


@bp.route('/accesso', methods=['GET', 'POST'])
def accesso():
    from flask import render_template_string
    from comune import destinazione_sicura
    if not dalla_rete():
        return redirect(url_for('home'))          # sul PC principale non serve
    from app import ses
    cfg = configurazione(ses())
    if not cfg['accesa']:
        return rifiuta("L'accesso dagli altri PC è spento.", titolo='Accesso dalla rete spento')
    dopo = destinazione_sicura(request.values.get('dopo'), '')
    errore, nome = '', ''
    if request.method == 'POST':
        nome = (request.form.get('nome') or '').strip()[:40]
        password = request.form.get('password') or ''
        chi = 'ip:' + indirizzo_chi_chiama()
        quale = 'nome:' + nome.casefold()
        attesa = bloccato(chi, quale)
        if attesa:
            annota('bloccato: troppi tentativi', nome, logging.WARNING)
            errore = 'Troppi tentativi sbagliati: riprovare fra %d minuti.' % max(1, (attesa + 59) // 60)
        else:
            u = trova(cfg['utenti'], nome)
            giusta = check_password_hash(u['hash'] if u else HASH_FINTO, password)
            if u and giusta and u.get('attivo', True):
                riuscito(chi, quale)
                session.clear()
                adesso = time.time()
                session.update(utente=u['nome'], v=u.get('versione', 0), dal=adesso, ultimo=adesso)
                annota('entrato', u['nome'])
                return redirect(dopo or prima_pagina(u))
            sbagliato(chi, quale)
            annota('password sbagliata' if u else 'nome sconosciuto', nome, logging.WARNING)
            errore = 'Nome o password non giusti.' if not u or u.get('attivo', True) else 'Utente disattivato.'
    return render_template_string(PAGINA_ACCESSO, errore=errore, nome=nome, dopo=dopo,
                                  nessuna=request.args.get('nessuna')), (429 if errore.startswith('Troppi') else 200)


@bp.route('/esci', methods=['POST'])
def esci():
    if session.get('utente'):
        annota('uscito', session.get('utente'))
    session.clear()
    return redirect(url_for('accessi.accesso'))


@bp.route('/aree-e-accessi', methods=['GET', 'POST'])
def pagina():
    """Configura → Aree e accessi, parte «Accesso dagli altri PC» (bozza). Solo dal PC principale (Sistema)."""
    from app import ses, LUCCHETTO, app as applicazione
    from modelli import scrivi_impostazione
    s = ses()
    cfg = configurazione(s)
    if request.method == 'POST':
        azione = request.form.get('azione')
        utenti = cfg['utenti']
        with LUCCHETTO:
            if azione == 'rete':
                accesa = request.form.get('accesa') == '1'
                testo_porta = (request.form.get('porta') or '').strip()
                porta = int(testo_porta) if testo_porta.isdigit() else 0
                if not porta_ammessa(porta):
                    flash('Porta non valida: fra 1024 e 65535, non la 5000 né quelle di riserva 5001–5009.', 'errore')
                    return redirect(url_for('accessi.pagina'))
                scrivi_impostazione(s, 'rete_porta', str(porta))
                scrivi_impostazione(s, 'rete_schermo_libero', '1' if request.form.get('schermo_libero') else '')
                scrivi_impostazione(s, 'rete_nomi', ' '.join((request.form.get('nomi') or '').split())[:300])
                scrivi_impostazione(s, 'rete_accesa', '1' if accesa else '')
                s.commit()
                if accesa and not current_app.config.get('TESTING'):
                    if ascolto.accendi(applicazione, porta):
                        flash('Accesso dalla rete acceso: gli altri PC aprono %s' % indirizzi_da_usare(porta)[0], 'ok')
                    else:
                        flash('Salvato, ma l\'ascolto non è partito: %s' % ascolto.errore, 'errore')
                elif not accesa:
                    ascolto.spegni()
                    flash('Accesso dalla rete spento.', 'ok')
            elif azione == 'nuovo':
                nome = ' '.join((request.form.get('nome') or '').split())
                password = request.form.get('password') or ''
                if not NOME_VALIDO.fullmatch(nome):
                    flash('Nome non valido: da 2 a 40 fra lettere, cifre, spazio, punto, trattino.', 'errore')
                elif trova(utenti, nome):
                    flash('C\'è già un utente con questo nome.', 'errore')
                elif len(password) < 8:
                    flash('La password deve avere almeno 8 caratteri.', 'errore')
                else:
                    utenti.append({'nome': nome, 'hash': generate_password_hash(password), 'attivo': True,
                                   'versione': 1, 'aree': {'guida': 'guarda'}})
                    salva_utenti(s, utenti)
                    s.commit()
                    flash('Utente %s aggiunto: ora scegliere le sue aree.' % nome, 'ok')
            elif azione in ('salva', 'password', 'elimina'):
                u = trova(utenti, request.form.get('utente'))
                if u is None:
                    flash('Utente non trovato.', 'errore')
                elif azione == 'salva':
                    u['aree'] = {a: request.form.get('area_' + a) for a, _, _ in AREE
                                 if request.form.get('area_' + a) in ('guarda', 'modifica')}
                    attivo = request.form.get('attivo') == '1'
                    if attivo != u.get('attivo', True):
                        u['versione'] = u.get('versione', 0) + 1      # disattivato: esce subito
                    u['attivo'] = attivo
                    salva_utenti(s, utenti)
                    s.commit()
                    flash('Aree di %s salvate.' % u['nome'], 'ok')
                elif azione == 'password':
                    password = request.form.get('password') or ''
                    if len(password) < 8:
                        flash('La password deve avere almeno 8 caratteri.', 'errore')
                    else:
                        u['hash'] = generate_password_hash(password)
                        u['versione'] = u.get('versione', 0) + 1          # chi era entrato rientra
                        salva_utenti(s, utenti)
                        s.commit()
                        flash('Password di %s cambiata.' % u['nome'], 'ok')
                else:
                    utenti.remove(u)
                    salva_utenti(s, utenti)
                    s.commit()
                    flash('Utente %s tolto.' % u['nome'], 'ok')
        return redirect(url_for('accessi.pagina'))
    return render_template('accessi.html', cfg=cfg, aree=AREE, livelli=LIVELLI, acceso=ascolto.acceso(),
                           errore_ascolto=ascolto.errore, indirizzi=indirizzi_da_usare(cfg['porta']),
                           eventi=list(eventi)[:30], sezione='impostazioni', sid=None)


# --------------------------------------------------------------- aggancio
def installa(app, cartella_chiave=None):
    """Da app.py, dopo aver dichiarato tutte le pagine."""
    app.register_blueprint(bp)
    if cartella_chiave:
        app.secret_key = chiave_sessione(cartella_chiave)
    app.session_interface = SessioniDueNomi()
    app.before_request(controlla_accesso)
    app.after_request(dopo_la_risposta)

    @app.context_processor
    def per_i_modelli():
        rete = dalla_rete()
        utente = getattr(contesto, 'utente_rete', None)

        def puo(area):
            return not rete or livello(utente, area) != 'no'

        def puo_cambiare(area):
            return not rete or livello(utente, area) == 'modifica'
        valori = {'puo': puo, 'puo_cambiare': puo_cambiare, 'utente_rete': utente}
        if rete:
            valori['popup_aggiornamento'] = lambda: None     # l'aggiornamento si fa solo dal PC principale
        return valori


import logging.handlers  # noqa: E402  (RotatingFileHandler per accessi.log)
