# -*- coding: utf-8 -*-
"""Accesso dagli altri PC della rete (dalla 1.13, richiesta di Giovanni del 22/11/2026: «dammi la possibilità di
scegliere quale modulo rendere disponibile sugli altri PC della rete in locale a quale utente e quale no»).

Il PC principale (la segreteria) apre il programma da http://127.0.0.1:5000 e per lui non cambia niente: nessun
accesso, tutte le pagine. Se in *Configura → Aree e accessi* si accende l'accesso dalla rete, il programma ascolta
ANCHE su 0.0.0.0:<porta della rete> (5080 di partenza). Chi arriva da lì entra con nome e password e vede solo le
aree che gli sono state date, ognuna «non disponibile», «solo guardare» (solo pagine e file: niente salvataggi) o
«guardare e modificare». Il «Sistema» (aggiornamenti, copie e ripristino, controllo del programma, impostazioni,
questa stessa pagina) resta sempre e solo sul PC principale.

Conta come «dalla rete» una richiesta che:
- arriva dalla presa della rete (la segna MarcaRete con environ['gestionale.presa_rete']);
- porta un'intestazione di un portiere (X-Forwarded-For, Forwarded, X-Real-Ip, X-Forwarded-Host): per esempio
  Caddy sullo stesso PC, che passa il Modo schermo (per questo il server principale non le toglie più:
  app.crea_server, clear_untrusted_proxy_headers=False);
- arriva da un indirizzo che non è del PC (la presa principale è legata a 127.0.0.1: non dovrebbe succedere).

Tutto in un posto solo:
- CENSIMENTO: l'area di ogni pagina (funzione di Flask). Una pagina che manca è trattata come Sistema (rifiutata
  dalla rete) e prove_accessi.py cade finché non la si scrive qui;
- gli utenti fra le impostazioni (rete_utenti, JSON: id casuale, nome, impronta della password di werkzeug, attivo,
  aree, «cambia» = password da cambiare al prossimo accesso), con rete_accesa, rete_porta, rete_schermo_libero e
  rete_nomi: nessuna tabella nuova, lo schema resta il 12;
- le sessioni della rete sul server (Sessioni: id casuale nel cookie, firmato con la chiave; sul server solo
  l'impronta dell'id, in sessioni-rete.json accanto alla chiave): «Esci» le chiude davvero, «Fai uscire» e il cambio
  della password anche;
- la chiave che firma i cookie: casuale già all'avvio del modulo (app.py) e poi, all'avvio vero, quella di
  chiave-sessione accanto al database (mai nelle copie di sicurezza); la presa della rete non si accende con una
  chiave corta o fissa;
- i tentativi sbagliati: bloccati per PC e nome (5 in un quarto d'ora) e per nome da qualsiasi PC (dopo 20 l'attesa
  raddoppia a ogni errore, fino a un'ora); «Sblocca» nella pagina;
- il registro: accessi/accessi-AAAA-MM-GG.log, un file per giorno, senza caratteri di controllo.
"""
import collections
import hashlib
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from flask import (Blueprint, Response, current_app, flash, has_request_context, redirect, render_template,
                   render_template_string, request, session, url_for)
from flask import g as contesto
from flask.sessions import SecureCookieSessionInterface
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('accessi', __name__)
registro = logging.getLogger('gestionale.accessi')

# =================================================================== aree
# Le aree che si danno a un utente, con i nomi che la segreteria conosce (il menu di oggi) e cosa c'è dentro.
AREE = (
    ('agenda', 'Agenda', 'Oggi, giorno, settimana, mese, prenotazioni, spostamenti, stampe del giorno'),
    ('pazienti', 'Pazienti', 'schede dei pazienti, documenti, codici fiscali'),
    ('segreteria', 'Segreteria', "conferme, da confermare, chiusura della giornata, cose da fare, lista d'attesa"),
    ('cassa', 'Cassa', 'incassi, listino, tariffari dei medici'),
    ('sala', 'Sala operatoria', 'sala, lista operatoria, posti letto, checklist'),
    ('turni', 'Turni', 'turni del personale'),
    ('ambulatori', 'Ambulatori e dashboard', 'pianificazione, programmazione, riepiloghi, dashboard'),
    ('statistiche', 'Statistiche e report', 'statistiche, riepilogo dei medici, esportazioni in Excel'),
    ('dove', 'Dove si fa', 'ricerca delle prestazioni, registro, strutture del gruppo'),
    ('comunicazioni', 'Email e WhatsApp', 'regole delle email, promemoria, registro dei messaggi'),
    ('configura', 'Anagrafiche', 'stanze, medici, turni dei medici, prestazioni, strutture, importa, moduli da stampare'),
    ('guida', 'Guida e aiuto', 'le guide e le novità'),
)
CODICI_AREE = tuple(a for a, _, _ in AREE)
NOMI_AREE = {a: n for a, n, _ in AREE}
LIVELLI = (('no', 'non disponibile'), ('guarda', 'solo guardare'), ('modifica', 'guardare e modificare'))
LIVELLI_VALIDI = ('guarda', 'modifica')

# le pagine che non sono di un'area
LIBERO = 'libero'            # sempre aperte: file del programma, logo, pagina di accesso, uscita (nessun dato)
UTENTE = 'utente'            # basta essere entrati: la propria password, i passi della guida sullo schermo
SISTEMA = 'sistema'          # solo dal PC principale, anche per chi ha tutte le aree
SCHERMO = 'schermo'          # il Modo schermo: libero se la clinica lo vuole, altrimenti Ambulatori e dashboard
TRASVERSALE = 'trasversale'  # notifiche e ricerca rapida: con l'accesso, e il contenuto si filtra per area
CATEGORIE = (LIBERO, UTENTE, SISTEMA, SCHERMO, TRASVERSALE)

# la ricerca dei pazienti, i luoghi di nascita e il codice fiscale servono a tutte le pagine che prenotano o
# scrivono un paziente: chi ha una di queste aree li può chiedere (prove_accessi.py apre le pagine di ogni area e
# chiede tutti gli indirizzi che quelle pagine usano)
SERVIZIO_PAZIENTI = ('pazienti', 'agenda', 'segreteria', 'dove')

# L'area di ogni pagina (funzione di Flask): una tupla vuol dire «una qualsiasi di queste». Una pagina nuova va
# scritta qui (prove_accessi.py cade finché manca: intanto dalla rete è rifiutata come il Sistema).
CENSIMENTO = {
    # sempre aperte: servono alla pagina di accesso, nessun dato dei pazienti
    'static': LIBERO, 'logo': LIBERO, 'home': LIBERO, 'accessi.accesso': LIBERO, 'accessi.esci': LIBERO,
    # basta essere entrati
    'accessi.password': UTENTE, 'guida.passi_json': UTENTE,
    # solo sul PC principale
    'salute': SISTEMA, 'autoriparazione': SISTEMA, 'aggiornamenti.pagina': SISTEMA,
    'aggiornamenti.aggiorna': SISTEMA, 'aggiornamenti.piu_tardi': SISTEMA, 'aggiornamenti.stato_json': SISTEMA,
    'viste.impostazioni': SISTEMA, 'viste.scarica_backup': SISTEMA, 'viste.ripristina': SISTEMA,
    'accessi.pagina': SISTEMA,
    # il Modo schermo
    'live.pagina': SCHERMO, 'live.dati': SCHERMO, 'live.statistiche': SCHERMO, 'live.statistiche_json': SCHERMO,
    # trasversali
    'segreteria.notifiche': TRASVERSALE, 'segreteria.cerca_tutto': TRASVERSALE,
    # Agenda
    'cruscotto.oggi': 'agenda', 'giorno': 'agenda', 'viste.settimana': 'agenda', 'viste.mese': 'agenda',
    'viste.elenco_giorno': 'agenda', 'viste.stampa': 'agenda', 'esporta': 'agenda', 'appuntamento': 'agenda',
    'cambia_stato': 'agenda', 'segreteria.sposta': 'agenda', 'segreteria.sposta_blocco': 'agenda',
    'segreteria.avvisa_spostati': 'agenda', 'segreteria.serie': 'agenda', 'segreteria.salva_nota': 'agenda',
    'segreteria.agenda_medico': 'agenda', 'viste.disponibilita': 'agenda', 'viste.promemoria': 'agenda',
    'documenti.stampa_modulo': 'agenda',
    # Pazienti (e i tre servizi chiesti anche dalle altre pagine)
    'pazienti.elenco': 'pazienti', 'pazienti.scheda': 'pazienti', 'pazienti.unisci_pagina': 'pazienti',
    'pazienti.codici_fiscali': 'pazienti', 'documenti.mostra_documento': 'pazienti',
    'documenti.carica_documento': 'pazienti', 'documenti.elimina_documento': 'pazienti',
    'pazienti.cerca_json': SERVIZIO_PAZIENTI, 'pazienti.codice_fiscale_json': SERVIZIO_PAZIENTI,
    'pazienti.luoghi_json': SERVIZIO_PAZIENTI,
    # Segreteria
    'viste.conferme': 'segreteria', 'segreteria.da_confermare': 'segreteria', 'segreteria.appunto_azione': 'segreteria',
    'segreteria.prenota_appunti': 'segreteria', 'segreteria.chiusura': 'segreteria',
    'segreteria.cose_da_fare': 'segreteria', 'segreteria.cosa_fatta': 'segreteria', 'segreteria.attesa': 'segreteria',
    'segreteria.attesa_scheda': 'segreteria', 'segreteria.attesa_per': 'segreteria',
    # Cassa
    'cassa.cassa_giorno': 'cassa', 'cassa.cassa_mese': 'cassa', 'cassa.cassa_mese_excel': 'cassa',
    'cassa.listino': 'cassa', 'cassa.pagamento': 'cassa', 'tariffari.elenco': 'cassa', 'tariffari.scheda': 'cassa',
    'tariffari.stampa': 'cassa', 'tariffari.anteprima': 'cassa',
    # Sala operatoria
    'sala.giornata': 'sala', 'sala.lista_operatoria': 'sala', 'sala.posti_letto': 'sala', 'sala.chirurghi': 'sala',
    'sala.checklist': 'sala', 'sala.salva_voci': 'sala',
    # Turni del personale
    'personale.persone': 'turni', 'personale.persona': 'turni', 'personale.medici_dall_agenda': 'turni',
    'personale.tipi_turno': 'turni', 'personale.turni': 'turni', 'personale.cambia': 'turni', 'personale.copia': 'turni',
    'personale.giorno': 'turni', 'personale.mese': 'turni', 'personale.mese_excel': 'turni', 'personale.schema': 'turni',
    'personale.settimana': 'turni',
    # Ambulatori e dashboard
    'ambulatori.inizio': 'ambulatori', 'ambulatori.settimana': 'ambulatori', 'ambulatori.settimana_excel': 'ambulatori',
    'ambulatori.mese': 'ambulatori', 'ambulatori.mese_excel': 'ambulatori', 'ambulatori.metti': 'ambulatori',
    'ambulatori.togli': 'ambulatori', 'ambulatori.riepilogo': 'ambulatori', 'ambulatori.riepilogo_excel': 'ambulatori',
    'ambulatori.riepilogo_json': 'ambulatori',
    # Statistiche e report (il riepilogo dei medici e le esportazioni: decisione del 22/11, Statistiche e report)
    'viste.statistiche': 'statistiche', 'viste.statistiche_excel': 'statistiche', 'cruscotto.riepilogo': 'statistiche',
    'cruscotto.riepilogo_excel': 'statistiche', 'esportazioni.pagina': 'statistiche',
    'esportazioni.scarica': 'statistiche',
    # Dove si fa (anche le Strutture del gruppo, che ne sono la configurazione)
    'dovesifa.pagina': 'dove', 'dovesifa.cerca_json': 'dove', 'dovesifa.risultati': 'dove', 'dovesifa.scheda': 'dove',
    'dovesifa.stampa': 'dove', 'dovesifa.indirizza': 'dove', 'dovesifa.togli': 'dove', 'dovesifa.registro': 'dove',
    'dovesifa.registro_excel': 'dove', 'dovesifa.strutture': 'dove', 'dovesifa.struttura': 'dove',
    'dovesifa.anteprima': 'dove',
    # Email e WhatsApp
    'invii.pagina': 'comunicazioni', 'invii.regola': 'comunicazioni', 'invii.allegato': 'comunicazioni',
    'invii.appuntamento': 'comunicazioni',
    # Anagrafiche (anche Importa da Excel: decisione del 22/11, area Anagrafiche con «modificare», non Sistema)
    'anagrafiche.elenco': 'configura', 'anagrafiche.medico': 'configura', 'anagrafiche.stanza': 'configura',
    'anagrafiche.prestazione': 'configura', 'anagrafiche.turno': 'configura', 'anagrafiche.struttura': 'configura',
    'anagrafiche.assenza': 'configura', 'anagrafiche.chiusura': 'configura', 'importa.carica': 'configura',
    'importa.anteprima': 'configura', 'importa.scarti': 'configura', 'documenti.moduli': 'configura',
    'documenti.modulo': 'configura',
    # Guida e aiuto
    'guida.indice': 'guida', 'guida.articolo': 'guida', 'guida.stampa': 'guida', 'aggiornamenti.novita_pagina': 'guida',
}

# Le parti del Sistema dentro una pagina di un'area (correzione 3 della revisione): nella pagina Email e WhatsApp la
# casella email (server, porta, sicurezza, utente: con un altro server la password salvata partirebbe verso di lui) e
# il token di WhatsApp, con le loro prove e la registrazione del numero, si configurano solo dal PC principale. Dalla
# rete i loro moduli rispondono 403 (sistema_dentro) e la pagina non li mostra ({% if puo('sistema') %} in invii.html).
SISTEMA_DENTRO = {'invii.pagina': lambda f: f.get('azione') in ('prova_email', 'prova_whatsapp', 'registra_whatsapp')
                  or (f.get('azione') == 'salva' and f.get('sezione') in ('email', 'whatsapp'))}

# la prima pagina da aprire dopo l'accesso (nell'ordine di AREE: la prima area che l'utente ha)
PRIMA_PAGINA = {'agenda': 'cruscotto.oggi', 'pazienti': 'pazienti.elenco', 'segreteria': 'viste.conferme',
                'cassa': 'cassa.listino', 'sala': 'sala.posti_letto', 'turni': 'personale.turni',
                'ambulatori': 'ambulatori.inizio', 'statistiche': 'viste.statistiche', 'dove': 'dovesifa.pagina',
                'comunicazioni': 'invii.pagina', 'configura': 'anagrafiche.elenco', 'guida': 'guida.indice'}

# Le notifiche: l'area di ognuna dall'inizio della sua chiave (la chiave la scrive chi la fa: segreteria.notifiche_di,
# sala, invii, aggiornamenti, autoripara), e la pagina a cui porta se la sua (per esempio la scheda del paziente)
# non è disponibile. Una notifica con una chiave che non è qui, dalla rete, non si mostra (come il Sistema):
# prove_accessi.py cerca le chiavi nei sorgenti e cade se ne trova una senza area.
AREA_NOTIFICHE = (('cosa-', 'segreteria', 'segreteria.cose_da_fare'), ('appunti-', 'segreteria', None),
                  ('conferme-', 'segreteria', None), ('chiudere-', 'segreteria', None),
                  ('chiudi-oggi-', 'segreteria', None), ('checklist-', 'sala', None), ('letti-', 'sala', None),
                  ('invii-errore-', 'comunicazioni', None), ('novita-', 'guida', None),
                  ('aggiornamenti-', SISTEMA, None), ('aggiornamento-', SISTEMA, None), ('backup-', SISTEMA, None),
                  ('autoripara-', SISTEMA, None))

# le letture dalla rete che si scrivono nel registro, oltre a ogni salvataggio: schede dei pazienti, documenti,
# allegati e ogni file Excel (prove_accessi.py controlla che ogni Excel e ogni documento scaricato sia qui)
REGISTRA_LETTURE = frozenset({
    'pazienti.scheda', 'documenti.mostra_documento', 'invii.allegato', 'importa.scarti', 'esporta',
    'esportazioni.scarica', 'viste.statistiche_excel', 'cruscotto.riepilogo_excel', 'cassa.cassa_mese_excel',
    'personale.mese_excel', 'ambulatori.settimana_excel', 'ambulatori.mese_excel', 'ambulatori.riepilogo_excel',
    'dovesifa.registro_excel'})

PORTA_RETE = 5080
FILI_RETE = 4                   # le richieste dalla rete servite insieme: fili loro, non quelli del PC principale
# I limiti di waitress, uguali per il server del PC principale (app.crea_server) e per quello della rete (correzione
# 2 della revisione): moduli fino a 13 MB (Flask ne accetta 12, MAX_CONTENT_LENGTH: oltre risponde 413 da sé), al
# massimo 20 collegamenti aperti insieme (gli altri aspettano il loro turno), e un collegamento fermo da 30 secondi si
# chiude (solo se non ha una richiesta in corso: un Excel lungo da preparare non si taglia)
LIMITI_SERVER = {'max_request_body_size': 13 * 1024 * 1024, 'connection_limit': 20, 'channel_timeout': 30}
NOME_REGOLA_FIREWALL = 'Gestionale Agende (rete della clinica)'
TENTATIVI_COPPIA = 5            # password sbagliate dallo stesso PC per lo stesso nome...
FINESTRA = 15 * 60              # ...in un quarto d'ora: poi si aspetta un quarto d'ora dall'ultima
SOGLIA_NOME = 20                # per un nome, da qualsiasi PC: dopo 20 sbagliate di fila si aspetta...
ATTESA_NOME = 60                # ...un minuto, poi 2, 4, 8... a ogni altra sbagliata
ATTESA_MASSIMA = 3600           # al massimo un'ora
INATTIVITA = 4 * 3600           # dopo 4 ore senza usarlo si rientra
DURATA_MASSIMA = 12 * 3600      # e comunque dopo 12 ore
MINIMO_PASSWORD = 10
COOKIE_RETE = 'gestionale_rete'
CHIAVI_FISSE = (b'gestionale-locale', 'gestionale-locale')     # la chiave di prima della 1.13, uguale per tutti
GIORNI_REGISTRO = 400           # i file del registro più vecchi si cancellano all'avvio
NOME_VALIDO = re.compile(r'[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9 ._\'-]{1,39}')
MESSAGGIO_SBAGLIATO = 'Nome o password non giusti.'
INTESTAZIONI_PORTIERE = ('HTTP_X_FORWARDED_FOR', 'HTTP_FORWARDED', 'HTTP_X_REAL_IP', 'HTTP_X_FORWARDED_HOST')
LOOPBACK = ('127.', '::1', '::ffff:127.')
_HASH_FINTO = []                # per un nome che non c'è: lo stesso tempo di risposta di uno vero


def hash_finto():
    if not _HASH_FINTO:
        _HASH_FINTO.append(generate_password_hash(secrets.token_hex(8)))
    return _HASH_FINTO[0]


# ================================================= da dove arriva la richiesta
def dalla_rete(environ=None):
    """True se la richiesta non è del PC principale (vedi in testa al file). Fuori da una richiesta: False."""
    if environ is None:
        if not has_request_context():
            return False
        environ = request.environ
    if environ.get('gestionale.presa_rete'):
        return True
    if any(environ.get(k) for k in INTESTAZIONI_PORTIERE):
        return True
    return not str(environ.get('REMOTE_ADDR') or '127.0.0.1').startswith(LOOPBACK)


def indirizzo_chi_chiama():
    """L'indirizzo del PC che chiama: dietro un portiere sullo stesso PC, l'ultimo di X-Forwarded-For (quello
    che ha scritto il portiere: i primi li può scrivere chiunque)."""
    if not has_request_context():
        return ''
    e = request.environ
    remoto = e.get('REMOTE_ADDR') or ''
    inoltrato = (e.get('HTTP_X_FORWARDED_FOR') or '').split(',')[-1].strip()
    if not inoltrato:
        m = re.findall(r'for="?\[?([0-9a-fA-F:.]+)', e.get('HTTP_FORWARDED') or '')
        inoltrato = m[-1] if m else (e.get('HTTP_X_REAL_IP') or '').strip()
    if inoltrato and remoto.startswith(LOOPBACK):
        return pulito(inoltrato, 64)
    return pulito(remoto, 64)


def pulito(testo, massimo=200):
    """Per il registro: niente a capo né altri caratteri di controllo (una riga finta scritta nel nome)."""
    return ''.join(c if c.isprintable() else '?' for c in str(testo or ''))[:massimo]


# ============================================================ impostazioni
def configurazione(s):
    from modelli import leggi_impostazione
    try:
        utenti = json.loads(leggi_impostazione(s, 'rete_utenti', '') or '[]')
    except ValueError:
        logging.error('accessi: rete_utenti non si legge: nessun utente dalla rete')
        utenti = []
    porta = leggi_impostazione(s, 'rete_porta', '') or ''
    return {'accesa': leggi_impostazione(s, 'rete_accesa', '') == '1',
            'porta': int(porta) if porta.isdigit() else PORTA_RETE,
            # spento di partenza: con la rete accesa il Modo schermo vuole l'accesso finché non lo si accende
            'schermo_libero': leggi_impostazione(s, 'rete_schermo_libero', '') == '1',
            'nomi': [x for x in (leggi_impostazione(s, 'rete_nomi', '') or '').split() if x][:20],
            'utenti': [u for u in utenti if isinstance(u, dict) and u.get('nome') and u.get('id')
                       and isinstance(u.get('hash'), str)] if isinstance(utenti, list) else []}


def salva_utenti(s, utenti):
    from modelli import scrivi_impostazione
    scrivi_impostazione(s, 'rete_utenti', json.dumps(utenti, ensure_ascii=False))


def chiave_nome(nome):
    return ' '.join((nome or '').split()).casefold()


def trova(utenti, nome):
    chiave = chiave_nome(nome)
    return next((u for u in utenti if chiave_nome(u['nome']) == chiave), None)


def trova_id(utenti, ident):
    return next((u for u in utenti if u.get('id') == ident), None) if ident else None


def nuovo_utente(nome, password, impronta=None):
    """Un utente nuovo: nessuna area (le sceglie chi lo crea) e la password da cambiare al primo accesso."""
    return {'id': secrets.token_hex(8), 'nome': nome, 'hash': impronta or generate_password_hash(password), 'attivo': True,
            'cambia': True, 'aree': {}, 'creato': datetime.now().isoformat(timespec='seconds')}


def livello(utente, area):
    """'no', 'guarda' o 'modifica' di un utente per un'area (o una tupla di aree: la migliore)."""
    if isinstance(area, tuple):
        livelli = [livello(utente, a) for a in area]
        return 'modifica' if 'modifica' in livelli else 'guarda' if 'guarda' in livelli else 'no'
    if area == LIBERO:
        return 'modifica'
    if area not in CODICI_AREE or utente is None:
        return 'no'                     # il Sistema non si dà a nessuno, nemmeno scritto a mano nel JSON
    v = (utente.get('aree') or {}).get(area, 'no')
    return v if v in LIVELLI_VALIDI else 'no'


def area_di(endpoint):
    return CENSIMENTO.get(endpoint, SISTEMA)


def senza_area(endpoint_presenti):
    """Le funzioni di Flask senza una riga nel censimento (dalla rete sarebbero rifiutate senza motivo)."""
    return sorted(set(endpoint_presenti) - set(CENSIMENTO))


def area_di_indirizzo(indirizzo, metodo='GET'):
    """L'area di un collegamento interno (per filtrare notifiche e ricerca rapida), o SISTEMA se non si capisce."""
    parti = urlsplit(indirizzo or '')
    if parti.scheme or parti.netloc or not parti.path.startswith('/'):
        return SISTEMA
    try:
        endpoint, _ = current_app.url_map.bind('x').match(parti.path, method=metodo)
    except HTTPException:
        return SISTEMA
    return area_di(endpoint)


def area_notifica(chiave):
    for inizio, area, _ in AREA_NOTIFICHE:
        if (chiave or '').startswith(inizio):
            return area
    return SISTEMA


def pagina_notifica(chiave):
    for inizio, area, pagina in AREA_NOTIFICHE:
        if (chiave or '').startswith(inizio):
            return pagina or PRIMA_PAGINA.get(area)
    return None


# ================================================= per le pagine del programma
def utente_attuale():
    return getattr(contesto, 'utente_rete', None) if has_request_context() else None


def puo(area):
    """Si può guardare quell'area? Sul PC principale sempre; il Sistema mai dalla rete."""
    if not dalla_rete():
        return True
    return livello(utente_attuale(), area) != 'no'


def puo_cambiare(area):
    """Si può salvare in quell'area? Sul PC principale sempre."""
    if not dalla_rete():
        return True
    return livello(utente_attuale(), area) == 'modifica'


def ricorda_spostati(ids):
    """Dopo «Sposta gli appuntamenti di un medico»: dalla rete la pagina di chi avvisare mostra solo questi."""
    if dalla_rete():
        sessioni.metti(session.get('sid'), 'spostati', [int(x) for x in ids][:500])


def spostati_permessi(ids):
    """Gli appuntamenti che la pagina di chi avvisare può mostrare: sul PC tutti, dalla rete solo quelli che
    questo utente ha appena spostato (altrimenti, cambiando i numeri nell'indirizzo, nomi e telefoni di chiunque)."""
    if not dalla_rete():
        return ids
    miei = set(sessioni.prendi(session.get('sid'), 'spostati') or ())
    return [x for x in ids if x in miei]


# ============================================================ la chiave
def chiave_sessione(cartella):
    """La chiave che firma i cookie: casuale, una per installazione, nel file chiave-sessione accanto al
    database. Se il file non si può scrivere vale finché il programma resta aperto (poi chi è dalla rete rientra)."""
    percorso = os.path.join(cartella, 'chiave-sessione')
    try:
        with open(percorso, 'rb') as f:
            chiave = f.read()
        if len(chiave) >= 32 and chiave not in CHIAVI_FISSE:
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


def chiave_buona(chiave):
    """La presa della rete si accende solo con una chiave lunga e non fissa: con 'gestionale-locale' chiunque
    potrebbe scriversi un cookie da solo."""
    if isinstance(chiave, str):
        chiave = chiave.encode('utf-8')
    return isinstance(chiave, bytes) and len(chiave) >= 32 and chiave not in CHIAVI_FISSE


class SessioniDueNomi(SecureCookieSessionInterface):
    """Il cookie della rete ha un nome suo e SameSite=Strict: sul PC principale 127.0.0.1:5000 e 127.0.0.1:5080
    condividerebbero lo stesso cookie (i cookie non guardano la porta)."""

    def get_cookie_name(self, app):
        return COOKIE_RETE if dalla_rete() else super().get_cookie_name(app)

    def get_cookie_samesite(self, app):
        return 'Strict' if dalla_rete() else super().get_cookie_samesite(app)


# ============================================================ le sessioni
def impronta_id(sid):
    return hashlib.sha256(sid.encode('ascii', 'replace')).hexdigest() if isinstance(sid, str) else ''


class Sessioni:
    """Le sessioni della rete, tenute sul server. Nel cookie (firmato) c'è solo un id casuale; qui la sua impronta,
    chi è entrato, da quando, l'ultima richiesta. Senza la riga qui il cookie non vale più niente: «Esci» e «Fai
    uscire» chiudono davvero. Il file (sessioni-rete.json accanto alla chiave) fa restare dentro chi era entrato
    anche dopo un riavvio del programma."""

    def __init__(self):
        self.dati = {}
        self.file = None
        self._lucchetto = threading.Lock()
        self._salvato = 0.0
        self._da_salvare = False

    def carica(self, cartella):
        self.file = os.path.join(cartella, 'sessioni-rete.json')
        try:
            with open(self.file, encoding='utf-8') as f:
                letti = json.load(f)
        except (OSError, ValueError):
            letti = None
        adesso = time.time()
        with self._lucchetto:
            self.dati = {k: v for k, v in (letti.items() if isinstance(letti, dict) else ())
                         if isinstance(v, dict) and not self._scaduta(v, adesso)}
            if letti is not None:
                self._salva(forza=True)     # via le scadute; con la rete mai usata nessun file nuovo

    @staticmethod
    def _scaduta(r, adesso):
        return adesso - r.get('ultimo', 0) > INATTIVITA or adesso - r.get('dal', 0) > DURATA_MASSIMA

    def _salva(self, forza=False):
        self._da_salvare = True
        if not self.file or (not forza and time.time() - self._salvato < 60):
            return
        try:
            provvisorio = self.file + '.nuovo'
            with open(provvisorio, 'w', encoding='utf-8') as f:
                json.dump(self.dati, f)
            os.replace(provvisorio, self.file)
            self._salvato, self._da_salvare = time.time(), False
        except OSError:
            logging.exception('accessi: sessioni non salvate')

    def nuova(self, utente_id, da=''):
        sid = secrets.token_urlsafe(32)
        adesso = time.time()
        with self._lucchetto:
            self.dati[impronta_id(sid)] = {'utente': utente_id, 'dal': adesso, 'ultimo': adesso, 'da': da}
            self._salva(forza=True)
        return sid

    def leggi(self, sid):
        """La sessione se c'è e non è scaduta (e l'ultima richiesta segnata), altrimenti None."""
        k = impronta_id(sid)
        adesso = time.time()
        with self._lucchetto:
            r = self.dati.get(k)
            if r is None:
                return None
            if self._scaduta(r, adesso):
                del self.dati[k]
                self._salva(forza=True)
                return None
            if adesso - r.get('ultimo', 0) > 30:
                r['ultimo'] = adesso
                self._salva()
            return dict(r)

    def metti(self, sid, chiave, valore):
        with self._lucchetto:
            r = self.dati.get(impronta_id(sid))
            if r is not None:
                r[chiave] = valore
                self._salva(forza=True)

    def prendi(self, sid, chiave):
        with self._lucchetto:
            return (self.dati.get(impronta_id(sid)) or {}).get(chiave)

    def togli(self, sid):
        with self._lucchetto:
            if self.dati.pop(impronta_id(sid), None) is not None:
                self._salva(forza=True)

    def togli_utente(self, utente_id, tranne=None):
        """Chiude tutte le sessioni di un utente (tranne quella con l'id dato): quante."""
        salva = impronta_id(tranne) if tranne else None
        with self._lucchetto:
            via = [k for k, r in self.dati.items() if r.get('utente') == utente_id and k != salva]
            for k in via:
                del self.dati[k]
            if via:
                self._salva(forza=True)
        return len(via)

    def quante(self, utente_id):
        adesso = time.time()
        with self._lucchetto:
            return sum(1 for r in self.dati.values() if r.get('utente') == utente_id and not self._scaduta(r, adesso))

    def svuota(self):
        with self._lucchetto:
            self.dati.clear()
            self._salva(forza=True)


sessioni = Sessioni()


def utente_di_sessione(cfg):
    """L'utente entrato con questo cookie, o None (e il cookie si svuota)."""
    sid = session.get('sid')
    if not sid:
        return None
    r = sessioni.leggi(sid)
    u = trova_id(cfg['utenti'], r['utente']) if r else None
    if u is None or not u.get('attivo', True):
        sessioni.togli(sid)
        session.pop('sid', None)
        return None
    return u


# ================================================================ tentativi
class Tentativi:
    """Password sbagliate: per coppia (PC, nome) 5 in un quarto d'ora, poi si aspetta un quarto d'ora; per nome
    da qualsiasi PC, dopo 20 di fila l'attesa raddoppia a ogni altra sbagliata (1, 2, 4... minuti, fino a un'ora).
    Così un PC dove entrano in tanti non si blocca per uno che sbaglia, e chi prova da più PC si ferma lo stesso.
    I nomi che non esistono contano come gli altri (non si capisce dal blocco se un nome c'è)."""

    MASSIMO_VOCI = 5000

    def __init__(self):
        self.coppie = {}                # (indirizzo, nome) -> [istanti]
        self.nomi = {}                  # nome -> {'n': sbagliate di fila, 'ultimo': istante}
        self._lucchetto = threading.Lock()

    def attesa(self, indirizzo, nome, adesso=None):
        """Secondi da aspettare prima di poter provare (0: si può)."""
        adesso = time.time() if adesso is None else adesso
        nome = chiave_nome(nome)
        with self._lucchetto:
            attesa = 0
            coda = [t for t in self.coppie.get((indirizzo, nome), ()) if adesso - t < FINESTRA]
            if len(coda) >= TENTATIVI_COPPIA:
                attesa = int(FINESTRA - (adesso - coda[-1])) + 1
            v = self.nomi.get(nome)
            if v and v['n'] >= SOGLIA_NOME:
                durata = min(ATTESA_NOME * 2 ** (v['n'] - SOGLIA_NOME), ATTESA_MASSIMA)
                attesa = max(attesa, int(durata - (adesso - v['ultimo'])) + 1)
            return max(attesa, 0)

    def sbagliata(self, indirizzo, nome, adesso=None):
        adesso = time.time() if adesso is None else adesso
        nome = chiave_nome(nome)
        with self._lucchetto:
            if len(self.coppie) > self.MASSIMO_VOCI or len(self.nomi) > self.MASSIMO_VOCI:
                self._sfoltisci(adesso)
            coda = [t for t in self.coppie.get((indirizzo, nome), ()) if adesso - t < FINESTRA]
            self.coppie[(indirizzo, nome)] = (coda + [adesso])[-TENTATIVI_COPPIA:]
            v = self.nomi.setdefault(nome, {'n': 0, 'ultimo': adesso})
            v['n'] += 1
            v['ultimo'] = adesso

    def riuscita(self, indirizzo, nome):
        nome = chiave_nome(nome)
        with self._lucchetto:
            self.coppie.pop((indirizzo, nome), None)
            self.nomi.pop(nome, None)

    def sblocca(self, nome):
        nome = chiave_nome(nome)
        with self._lucchetto:
            for k in [k for k in self.coppie if k[1] == nome]:
                del self.coppie[k]
            self.nomi.pop(nome, None)

    def bloccati(self, adesso=None):
        """[(nome, da quali PC, minuti di attesa)] dei nomi che adesso devono aspettare, per la pagina."""
        adesso = time.time() if adesso is None else adesso
        nomi = {n for _, n in self.coppie} | set(self.nomi)
        uscita = []
        for n in sorted(nomi):
            per_pc = [i for (i, x) in list(self.coppie) if x == n and self.attesa(i, n, adesso)]
            attesa = max([self.attesa(i, n, adesso) for i in per_pc] + [self.attesa('', n, adesso)])
            if attesa:
                uscita.append((n, per_pc, max(1, (attesa + 59) // 60)))
        return uscita

    def _sfoltisci(self, adesso):
        self.coppie = {k: v for k, v in self.coppie.items() if v and adesso - v[-1] < FINESTRA}
        self.nomi = {k: v for k, v in self.nomi.items() if adesso - v['ultimo'] < ATTESA_MASSIMA * 2}

    def svuota(self):
        with self._lucchetto:
            self.coppie.clear()
            self.nomi.clear()


tentativi = Tentativi()


# ================================================================ password
# Le password che si indovinano subito: le più usate, le parole del posto, quelle della tastiera. Si confrontano
# senza maiuscole, accenti, cifre e segni (Posillipo2026! è «posillipo»), anche ripetute (ciaociao).
VIETATE = frozenset('''
password passwort passw0rd parola parolachiave parolasegreta chiave segreto segreta segreti admin amministratore
administrator root utente user users guest ospite login accesso accedi entra entrare benvenuto benvenuti welcome
qwerty qwertz azerty qwertyuiop asdfgh asdfghjkl zxcvbn zxcvbnm qazwsx abc abcd abcde abcdef abcdefg abcdefgh
abcdefghi abcdefghij letmein iloveyou ciao amore tiamo ciaobella dragon monkey sunshine princess football
calcio napoli juventus juve milan inter roma lazio forzanapoli maradona italia italy napoletano
gestionale gestione agende agenda clinica cliniche posillipo nefrocenter nefro longevity longevityinstitute
segreteria segretaria reception accettazione dottore dottoressa medico medici infermiere infermiera paziente
pazienti ospedale sanita salute studio studiomedico ambulatorio ambulatori cassa turni sala
lunedi martedi mercoledi giovedi venerdi sabato domenica gennaio febbraio marzo aprile maggio giugno luglio
agosto settembre ottobre novembre dicembre primavera estate autunno inverno computer pc windows internet
'''.split())
SEQUENZE = ('0123456789', '9876543210', 'abcdefghijklmnopqrstuvwxyz', 'zyxwvutsrqponmlkjihgfedcba',
            'qwertyuiop', 'asdfghjkl', 'zxcvbnm', 'poiuytrewq')
CONSIGLIO_PASSWORD = ('Meglio una frase di tre o quattro parole che non c\'entrano fra loro, con gli spazi: è lunga, '
                      'difficile da indovinare e facile da ricordare. Mai il proprio nome, il nome della clinica o '
                      'una password usata altrove.')


def _solo_lettere(testo):
    t = unicodedata.normalize('NFKD', testo.casefold())
    return ''.join(c for c in t if 'a' <= c <= 'z')


def problema_password(password, nome=''):
    """None se la password va bene, altrimenti cosa non va, in parole semplici."""
    if len(password) < MINIMO_PASSWORD:
        return 'La password deve avere almeno %d caratteri.' % MINIMO_PASSWORD
    if len(password) > 200:
        return 'La password può avere al massimo 200 caratteri.'
    if any(not c.isprintable() for c in password):
        return 'La password non può contenere a capo o altri caratteri speciali invisibili.'
    if len(set(password.casefold())) < 5:
        return 'La password ha troppi caratteri uguali: si indovina subito.'
    lettere = _solo_lettere(password)
    if not lettere:
        return 'La password non può essere fatta solo di numeri o segni: si indovina subito.'
    for v in VIETATE:
        if lettere == v or (len(lettere) % len(v) == 0 and lettere == v * (len(lettere) // len(v))):
            return 'Questa password è fra quelle che si indovinano subito: sceglierne un\'altra.'
    semplice = re.sub(r'[\s\W_]', '', password.casefold())
    if any(semplice in s for s in SEQUENZE) or any(semplice in s * 3 for s in SEQUENZE):
        return 'Questa password è una sequenza della tastiera: si indovina subito.'
    for parte in re.split(r'[\s._\'-]+', nome or ''):
        if len(_solo_lettere(parte)) >= 3 and _solo_lettere(parte) in lettere:
            return 'La password non può contenere il nome dell\'utente.'
    return None


# ================================================================ registro
class FilePerGiorno(logging.Handler):
    """Il registro degli accessi: un file per giorno (accessi-AAAA-MM-GG.log), aperto e chiuso a ogni riga
    (poche righe, e su Windows nessun file tenuto aperto)."""

    def __init__(self, cartella):
        super().__init__()
        self.cartella = cartella

    def emit(self, record):
        try:
            os.makedirs(self.cartella, exist_ok=True)
            percorso = os.path.join(self.cartella, 'accessi-%s.log' % date.today().isoformat())
            with open(percorso, 'a', encoding='utf-8') as f:
                f.write(self.format(record) + '\n')
        except Exception:
            self.handleError(record)


eventi = collections.deque(maxlen=200)       # gli ultimi, per la pagina (tutti nel registro)


def annota(testo, nome='', livello_log=logging.INFO):
    # nel file i campi sono separati da « | »: un nome scritto con | non deve poter spostare gli altri campi
    riga = (datetime.now().strftime('%d/%m %H:%M:%S'), pulito(nome, 60).replace('|', '/'), indirizzo_chi_chiama(),
            pulito(testo, 200).replace('|', '/'))
    eventi.appendleft(riga + (livello_log >= logging.WARNING,))
    registro.log(livello_log, '%s | utente=%s | da=%s', riga[3], riga[1] or '-', riga[2] or '-')


RIGA_REGISTRO = re.compile(r'(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d:\d\d)[,.]\d+ (\w+) (.*) \| utente=(.*) \| da=(.*)')


def ultimi_accessi(giorni=7, quanti=150):
    """Le righe del registro degli ultimi giorni, dai file (le più recenti prima): (quando, utente, da, cosa,
    attenzione). Senza la cartella del registro (il gestionale di prova di demo.py), quelle dall'avvio."""
    cartella = _cartella_registro[0]
    if not cartella:
        return list(eventi)[:quanti]
    righe = []
    oggi = date.today()
    for n in range(giorni):
        percorso = os.path.join(cartella, 'accessi-%s.log' % (oggi - timedelta(days=n)).isoformat())
        try:
            with open(percorso, encoding='utf-8', errors='replace') as f:
                del_giorno = f.read().splitlines()
        except OSError:
            continue
        for testo in reversed(del_giorno):
            m = RIGA_REGISTRO.fullmatch(testo)
            if m:
                a, me, g, ora, lv, cosa, nome, da = m.groups()
                righe.append(('%s/%s %s' % (g, me, ora), '' if nome == '-' else nome, '' if da == '-' else da, cosa,
                              lv in ('WARNING', 'ERROR', 'CRITICAL')))
            if len(righe) >= quanti:
                return righe
    return righe


_cartella_registro = [None]


def prepara_registro(cartella):
    """Il registro accanto al database, nella cartella accessi; via i file più vecchi di GIORNI_REGISTRO."""
    cartella = os.path.join(cartella, 'accessi')
    _cartella_registro[0] = cartella
    for h in list(registro.handlers):
        if isinstance(h, FilePerGiorno):
            registro.removeHandler(h)
    gestore = FilePerGiorno(cartella)
    gestore.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    registro.addHandler(gestore)
    registro.setLevel(logging.INFO)
    registro.propagate = False            # solo nel registro degli accessi, non anche in gestionale.log
    limite = (date.today() - timedelta(days=GIORNI_REGISTRO)).isoformat()
    try:
        for n in os.listdir(cartella):
            m = re.fullmatch(r'accessi-(\d{4}-\d{2}-\d{2})\.log', n)
            if m and m.group(1) < limite:
                os.remove(os.path.join(cartella, n))
    except OSError:
        pass
    return cartella


# ============================================================= il controllo
PAGINA_NO = '''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ titolo }}</title><link rel="stylesheet" href="/static/stile.css"><link rel="icon" type="image/png" href="/static/icona.png"></head><body>
<main class="pagina" style="max-width:40em;margin:4em auto"><h1>{{ titolo }}</h1><p>{{ motivo }}</p>
{% if sistema %}<p>Aggiornamenti, copie di sicurezza, impostazioni, controllo del programma e la scelta degli accessi si
fanno solo dal PC della segreteria, anche per chi dagli altri PC ha tutte le parti.</p>
{% else %}<p>{% if utente %}Si è entrati come <b>{{ utente }}</b>. {% endif %}Quali parti del programma si aprono dagli
altri PC, e per chi, lo sceglie chi usa il PC della segreteria (<i>Configura → Aree e accessi</i>): per avere anche
questa parte, chiedere a lei.</p>{% endif %}
<p>{% if torna %}<a class="bottone" href="{{ torna }}">Torna alle pagine disponibili</a>{% endif %}
{% if utente %}<form method="post" action="/esci" style="display:inline"><button class="bottone" type="submit">Esci</button></form>{% endif %}</p>
</main></body></html>'''


def vuole_json():
    return request.path.endswith('.json') or bool(request.headers.get('X-Richiesta')) or \
        request.accept_mimetypes.best == 'application/json'


def rifiuta(motivo, titolo='Questa parte non è disponibile', utente=None, codice=403, sistema=False):
    """La risposta di un rifiuto: la pagina in italiano (chi è entrato, a chi chiedere, «Torna alle pagine
    disponibili» ed «Esci») o, per gli script, il JSON con l'errore."""
    if vuole_json():
        return Response(json.dumps({'errore': motivo}, ensure_ascii=False), status=codice,
                        mimetype='application/json')
    return Response(render_template_string(PAGINA_NO, titolo=titolo, motivo=motivo, sistema=sistema,
                                           utente=utente['nome'] if utente else '',
                                           torna=prima_pagina(utente) if utente else ''),
                    status=codice, mimetype='text/html')


def prima_pagina(utente):
    for area in CODICI_AREE:
        if livello(utente, area) != 'no':
            return url_for(PRIMA_PAGINA[area])
    return url_for('accessi.accesso', nessuna=1)


def schermo_libero(cfg, endpoint):
    """Il Modo schermo senza password: con la rete spenta come prima della 1.13 (il portiere Caddy lo passa);
    con la rete accesa solo se la clinica lo vuole, e le pagine solo in modo schermo (?schermo=1, senza menu)."""
    if request.method not in ('GET', 'HEAD'):
        return False
    if not cfg['accesa']:
        return True
    if not cfg['schermo_libero']:
        return False
    return endpoint.endswith('_json') or endpoint == 'live.dati' or request.args.get('schermo') == '1'


def controlla_accesso():
    """before_request: sul PC principale non fa niente (e non apre il database: /salute deve rispondere anche
    a database fermo). Dalla rete: chi è, l'area della pagina e il livello."""
    if not dalla_rete():
        return None
    endpoint = request.endpoint
    if endpoint is None:            # 404 o 405: risponde Flask, senza dire di più
        return None
    area = area_di(endpoint)
    if area == SISTEMA:             # prima di leggere qualsiasi cosa
        if endpoint not in CENSIMENTO:
            logging.warning('accessi: la pagina %s non ha un\'area: rifiutata dalla rete', endpoint)
        return rifiuta('Questa pagina si apre solo dal PC della segreteria.', titolo='Solo dal PC della segreteria',
                       sistema=True)
    if endpoint == 'static':
        return None                 # i file del programma: nessun dato
    from app import ses
    cfg = configurazione(ses())
    contesto.accessi_cfg = cfg
    if not host_valido_dalla_rete(request.host, cfg['nomi'], cfg['porta']):
        # come NOMI_LOCALI per il PC principale: un nome di un altro sito che punta qui (DNS rebinding) non passa
        return Response('Indirizzo non valido: dagli altri PC il gestionale si apre con il nome o l\'indirizzo del '
                        'PC della segreteria.', status=400, mimetype='text/plain')
    if area == SCHERMO and schermo_libero(cfg, endpoint):
        return None
    if endpoint == 'logo':
        return None
    if not cfg['accesa']:
        return rifiuta("L'accesso dagli altri PC è spento.", titolo='Accesso dalla rete spento')
    utente = utente_di_sessione(cfg)
    contesto.utente_rete = utente
    if endpoint in ('accessi.accesso', 'accessi.esci'):
        return None
    if utente is None:
        if vuole_json():
            return rifiuta('Bisogna entrare con nome e password.', titolo='Accesso', codice=401)
        dopo = request.full_path.rstrip('?') if request.method == 'GET' else ''
        return redirect(url_for('accessi.accesso', dopo=dopo or None))
    if utente.get('cambia') and endpoint != 'accessi.password':
        # la password data da chi l'ha creato si cambia prima di tutto il resto
        if vuole_json():
            return rifiuta('Prima va cambiata la password.', titolo='Password da cambiare', codice=401)
        return redirect(url_for('accessi.password'))
    if endpoint == 'home':
        return redirect(prima_pagina(utente))
    if area in (UTENTE, TRASVERSALE):
        return None                 # le trasversali si filtrano in dopo_la_risposta
    if area == SCHERMO:
        area = 'ambulatori'
    if sistema_dentro(endpoint):
        annota('negato (Sistema) %s %s' % (request.method, request.path), utente['nome'], logging.WARNING)
        return rifiuta('Questa parte si configura solo dal PC della segreteria.', titolo='Solo dal PC della segreteria',
                       utente=utente, sistema=True)
    lv = livello(utente, area)
    nome_area = NOMI_AREE.get(area if isinstance(area, str) else area[0], '')
    if lv == 'no':
        annota('negato %s %s' % (request.method, request.path), utente['nome'], logging.WARNING)
        return rifiuta('«%s» non è fra le parti disponibili per questo utente.' % nome_area, utente=utente)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if lv != 'modifica':
            annota('negato (solo guardare) %s %s' % (request.method, request.path), utente['nome'], logging.WARNING)
            return rifiuta('Per «%s» questo utente può solo guardare: non si salva niente.' % nome_area,
                           titolo='Solo guardare', utente=utente)
        annota('%s %s' % (request.method, request.full_path.rstrip('?')), utente['nome'])
    elif endpoint in REGISTRA_LETTURE:
        annota('aperto %s' % request.full_path.rstrip('?'), utente['nome'])
    return None


def sistema_dentro(endpoint):
    """La richiesta tocca una parte del Sistema dentro una pagina di un'area (SISTEMA_DENTRO)? Solo i salvataggi:
    le pagine si guardano, senza quelle parti."""
    controllo = SISTEMA_DENTRO.get(endpoint)
    return controllo is not None and request.method not in ('GET', 'HEAD', 'OPTIONS') and bool(controllo(request.form))


def _filtra_notifiche(lista, utente):
    uscita = []
    for n in lista if isinstance(lista, list) else []:
        if not isinstance(n, dict):
            continue
        area = area_notifica(n.get('chiave'))
        if livello(utente, area) == 'no':
            continue
        n = dict(n)
        if livello(utente, area_di_indirizzo(n.get('link'))) == 'no':
            n['link'] = url_for(pagina_notifica(n.get('chiave')))      # alla pagina dell'area
        n['azioni'] = [a for a in n.get('azioni') or [] if isinstance(a, dict)
                       and livello(utente, area_di_indirizzo(a.get('url'), 'POST')) == 'modifica']
        uscita.append(n)
    return uscita


def _filtra_ricerca(dati, utente):
    """La ricerca rapida: via le voci che portano a pagine non disponibili (pazienti senza Pazienti...)."""
    if not isinstance(dati, dict):
        return {}
    uscita = dict(dati)
    for k, v in dati.items():
        if isinstance(v, list):
            uscita[k] = [x for x in v if isinstance(x, dict) and livello(utente, area_di_indirizzo(x.get('url'))) != 'no']
        elif isinstance(v, dict) and 'url' in v:
            uscita[k] = v if livello(utente, area_di_indirizzo(v.get('url'))) != 'no' else None
    return uscita


def dopo_la_risposta(risposta):
    if not dalla_rete():
        return risposta
    if request.endpoint not in ('static', 'logo'):
        # sul PC di un altro reparto la pagina non deve restare nella cache del browser
        risposta.headers['Cache-Control'] = 'no-store'
    risposta.headers.setdefault('X-Content-Type-Options', 'nosniff')
    risposta.headers.setdefault('Referrer-Policy', 'same-origin')
    utente = getattr(contesto, 'utente_rete', None)
    if utente is not None and area_di(request.endpoint) == TRASVERSALE and risposta.mimetype == 'application/json' \
            and risposta.status_code == 200:
        dati = json.loads(risposta.get_data(as_text=True))
        if request.endpoint == 'segreteria.notifiche':
            dati = _filtra_notifiche(dati, utente)
        else:
            dati = _filtra_ricerca(dati, utente)
        testo = json.dumps(dati, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e') \
            .replace('&', '\\u0026')
        risposta.set_data(testo)
    return risposta


# ================================================== nome dell'host e origine
_nomi_del_pc = {'quando': -1e9, 'nomi': []}
IPV4 = re.compile(r'(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}')


def nomi_del_pc():
    """Come gli altri PC possono chiamare questo: nome, nome completo, nome.local e indirizzi IPv4 (senza 127.* e
    169.254.*). Solo quello che sa il PC stesso: nessuna connessione. Si rifanno ogni minuto: con il DHCP
    l'indirizzo del PC può cambiare a programma aperto."""
    if time.monotonic() - _nomi_del_pc['quando'] < 60:
        return _nomi_del_pc['nomi']
    nomi = set()
    try:
        nome = socket.gethostname()
        nomi.update({nome.lower(), socket.getfqdn().lower(), nome.lower() + '.local'})
        for info in socket.getaddrinfo(nome, None, socket.AF_INET):
            nomi.add(info[4][0])
    except OSError:
        pass
    _nomi_del_pc['nomi'] = sorted(n for n in nomi if n and n != 'localhost' and not n.startswith(('127.', '169.254.')))
    _nomi_del_pc['quando'] = time.monotonic()
    return _nomi_del_pc['nomi']


def indirizzi_da_usare(porta):
    """Gli indirizzi da scrivere sugli altri PC: prima il nome del PC, poi gli IP."""
    try:
        nome = socket.gethostname()
    except OSError:
        nome = 'NOME-DEL-PC'
    ip = [n for n in nomi_del_pc() if IPV4.fullmatch(n)]
    return ['http://%s:%d/' % (nome, porta)] + ['http://%s:%d/' % (x, porta) for x in ip]


def host_valido_dalla_rete(host, cfg_nomi, porta):
    """Il nome con cui è stata chiamata la pagina (Host) è di questo PC? Contro il DNS rebinding, come NOMI_LOCALI
    per il PC principale: un altro nome che punta qui non passa. 127.0.0.1 e localhost vanno bene (il portiere
    sullo stesso PC, o il PC della segreteria sulla porta della rete). Un indirizzo scritto in numeri (192.168.1.10)
    va sempre bene sulla porta della rete: il DNS rebinding passa per un nome, mai per i numeri (così un indirizzo
    cambiato dal DHCP, o di una seconda scheda di rete, funziona subito)."""
    m = re.fullmatch(r'\[?([^\]\[/@]+?)\]?(?::(\d{1,5}))?', (host or '').lower())
    if not m:
        return False
    nome, p = m.group(1), int(m.group(2) or 80)
    if nome in ('127.0.0.1', 'localhost'):
        return True
    return p == porta and (bool(IPV4.fullmatch(nome)) or nome in nomi_del_pc() or
                           nome in [x.lower() for x in cfg_nomi])


# ============================================================ secondo ascolto
class MarcaRete:
    """Avvolge l'applicazione per la presa della rete: ogni richiesta arrivata di qui è «dalla rete», qualunque
    indirizzo abbia (anche chi apre http://NOME:5080 dal PC della segreteria)."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['gestionale.presa_rete'] = True
        return self.app(environ, start_response)


def presa_della_rete(porta):
    """La presa su tutte le schede di rete (0.0.0.0). Su Windows SO_EXCLUSIVEADDRUSE (nessun altro programma può
    legarsi alla stessa porta su un indirizzo più preciso) e niente SO_REUSEADDR, come app.presa_in_ascolto."""
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


def porta_ammessa(porta, principale=None):
    """Una porta per la rete: fra 1024 e 65535, mai quella del PC principale (5000, o quella su cui è partito) né
    quelle di riserva 5001-5009 (al prossimo avvio il PC principale potrebbe doverne usare una)."""
    import autoripara
    principale = principale or autoripara.stato.get('porta') or 5000
    return 1024 <= porta <= 65535 and porta not in (principale, 5000) and porta not in autoripara.PORTE_DI_RISERVA


def spiega_errore_porta(porta, e):
    codice = getattr(e, 'winerror', None) or getattr(e, 'errno', None)
    if codice in (10048, 98, 48):          # in uso
        return 'La porta %d è già usata da un altro programma: sceglierne un\'altra.' % porta
    if codice in (10013, 13):              # vietata (su Windows: una fascia riservata da Hyper-V o WSL)
        return ('Windows non lascia usare la porta %d (può essere riservata, per esempio da Hyper-V): sceglierne '
                'un\'altra, per esempio 8080.' % porta)
    return 'La porta %d non si può usare: %s' % (porta, e)


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
            if not chiave_buona(app.secret_key):
                self.errore = ('La chiave che protegge gli accessi non è pronta: chiudere e riaprire il programma, '
                               'poi riprovare.')
                logging.error('accessi: presa della rete non accesa, chiave corta o fissa')
                return False
            if self.acceso() and self.porta == porta:
                return True
            try:
                presa = presa_della_rete(porta)        # prima la presa nuova: se non si può, resta quella di prima
            except OSError as e:
                self.errore = spiega_errore_porta(porta, e)
                logging.warning('accessi: porta %d della rete non utilizzabile: %s', porta, e)
                return False
            self._spegni()
            # i portieri non si fidano (le loro intestazioni restano: dalla rete comunque), con i limiti di sempre
            self.server = create_server(MarcaRete(app), sockets=[presa], threads=FILI_RETE,
                                        clear_untrusted_proxy_headers=False, ident='Gestionale Agende',
                                        **LIMITI_SERVER)
            self.porta, self.errore = porta, ''
            server = self.server

            def gira():
                try:
                    server.run()
                except Exception:
                    logging.exception('accessi: ascolto della rete fermo')
                finally:
                    try:
                        server.task_dispatcher.shutdown(timeout=5)
                    except Exception:
                        pass
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


ascolto = AscoltoRete()


def applica(app, sessione_fabbrica=None):
    """Accende o spegne l'ascolto della rete come dicono le impostazioni: all'avvio, dopo un ripristino o una
    riparazione (le impostazioni possono essere cambiate con la copia rimessa). True se è come deve essere."""
    if sessione_fabbrica is None:
        from app import Sessione as sessione_fabbrica
    s = sessione_fabbrica()
    try:
        cfg = configurazione(s)
    finally:
        s.close()
    if not cfg['accesa']:
        ascolto.spegni()
        return True
    return ascolto.accendi(app, cfg['porta'])


RIPROVE_AVVIO = 10              # all'avvio, con la porta della rete occupata: 10 tentativi...
PAUSA_AVVIO = 30                # ...ogni mezzo minuto (cinque minuti in tutto)


def all_avvio(app, sessione_fabbrica, cartella, prove=None, pausa=None):
    """Dall'avvio del programma (app.principale), dopo che il server principale è in ascolto: registro, sessioni
    e, se è acceso, l'ascolto della rete. Se la porta non è ancora libera (il programma di prima si sta chiudendo,
    la rete di Windows non è pronta) si riprova per qualche minuto, in un filo a parte. Il PC principale intanto
    funziona già: la rete non ferma mai il suo avvio (app.principale la chiama dentro un try)."""
    prove = RIPROVE_AVVIO if prove is None else prove
    pausa = PAUSA_AVVIO if pausa is None else pausa
    prepara_registro(cartella)
    sessioni.carica(cartella)
    try:
        if applica(app, sessione_fabbrica):
            return
    except Exception:
        logging.exception('accessi: avvio dell\'ascolto della rete')

    def riprova():
        for _ in range(prove):
            time.sleep(pausa)
            try:
                if applica(app, sessione_fabbrica):
                    return
            except Exception:
                logging.exception('accessi: avvio dell\'ascolto della rete')
        import autoripara
        autoripara.annota('Accesso dagli altri PC non partito: %s' % ascolto.errore, 'attenzione')
    threading.Thread(target=riprova, name='accessi-avvio', daemon=True).start()


# ==================================================================== pagine
@bp.route('/accesso', methods=['GET', 'POST'])
def accesso():
    from comune import destinazione_sicura
    if not dalla_rete():
        return redirect(url_for('home'))          # sul PC principale non serve
    cfg = contesto.accessi_cfg
    dopo = destinazione_sicura(request.values.get('dopo'), '')
    if dopo.startswith(('/accesso', '/esci')):
        dopo = ''
    errore, nome, codice = '', '', 200
    if request.method == 'POST':
        nome = ' '.join((request.form.get('nome') or '').split())[:40]
        password = (request.form.get('password') or '')[:200]
        da = indirizzo_chi_chiama()
        attesa = tentativi.attesa(da, nome)
        if attesa:
            annota('bloccato: troppi tentativi', nome, logging.WARNING)
            errore = 'Troppi tentativi sbagliati: riprovare fra %d minut%s.' % (
                max(1, (attesa + 59) // 60), 'o' if attesa <= 60 else 'i')
            codice = 429
        else:
            u = trova(cfg['utenti'], nome)
            giusta = check_password_hash(u['hash'] if u else hash_finto(), password)
            if u is not None and giusta and u.get('attivo', True):
                tentativi.riuscita(da, nome)
                vecchio = session.get('sid')
                if vecchio:
                    sessioni.togli(vecchio)
                session.clear()
                session['sid'] = sessioni.nuova(u['id'], da)
                contesto.utente_rete = u
                annota('entrato', u['nome'])
                if u.get('cambia'):
                    return redirect(url_for('accessi.password'))
                return redirect(dopo or prima_pagina(u))
            tentativi.sbagliata(da, nome)
            annota('password sbagliata' if u is not None and not giusta else 'non entrato (nome sconosciuto o '
                   'utente spento)', nome, logging.WARNING)
            errore = MESSAGGIO_SBAGLIATO          # sempre lo stesso: non si capisce se il nome c'è
    return render_template('accesso.html', errore=errore, nome=nome, dopo=dopo,
                           nessuna=bool(request.args.get('nessuna')), sid=None), codice


@bp.route('/esci', methods=['POST'])
def esci():
    sid = session.get('sid')
    if sid:
        utente = getattr(contesto, 'utente_rete', None)
        sessioni.togli(sid)
        annota('uscito', utente['nome'] if utente else '')
    session.clear()
    return redirect(url_for('accessi.accesso') if dalla_rete() else url_for('home'))


@bp.route('/accesso/password', methods=['GET', 'POST'])
def password():
    """La propria password, dagli altri PC (la prima volta è obbligatorio cambiarla)."""
    if not dalla_rete():
        return redirect(url_for('home'))
    from app import ses, LUCCHETTO
    utente = contesto.utente_rete
    errore = ''
    if request.method == 'POST':
        attuale = (request.form.get('attuale') or '')[:200]
        nuova = request.form.get('nuova') or ''
        ancora = request.form.get('ancora') or ''
        da = indirizzo_chi_chiama()
        # i controlli (lenti: l'impronta della password) fuori dal lucchetto; poi si salva, con il lucchetto, solo se
        # nel frattempo nessuno ha cambiato quella password
        if tentativi.attesa(da, utente['nome']):
            errore = 'Troppi tentativi sbagliati: riprovare più tardi.'
        elif not check_password_hash(utente['hash'], attuale):
            tentativi.sbagliata(da, utente['nome'])
            annota('cambio della password: password attuale sbagliata', utente['nome'], logging.WARNING)
            errore = 'La password attuale non è giusta.'
        elif nuova != ancora:
            errore = 'Le due password nuove non sono uguali.'
        elif nuova == attuale:
            errore = 'La password nuova deve essere diversa da quella di prima.'
        else:
            errore = problema_password(nuova, utente['nome']) or ''
        if not errore:
            impronta = generate_password_hash(nuova)
            with LUCCHETTO:
                s = ses()
                cfg = configurazione(s)
                u = trova_id(cfg['utenti'], utente['id'])
                if u is None or u['hash'] != utente['hash']:
                    return redirect(url_for('accessi.accesso'))
                u['hash'], u['cambia'] = impronta, False
                salva_utenti(s, cfg['utenti'])
                s.commit()
            sessioni.togli_utente(u['id'], tranne=session.get('sid'))       # gli altri PC dove era entrato: fuori
            annota('password cambiata', u['nome'])
            flash('Password cambiata.', 'ok')
            return redirect(prima_pagina(u))
    return render_template('accesso_password.html', errore=errore, utente=utente, consiglio=CONSIGLIO_PASSWORD,
                           minimo=MINIMO_PASSWORD, sid=None)


def _modulo_aree(u):
    return {a: request.form.get('area_' + a) for a in CODICI_AREE if request.form.get('area_' + a) in LIVELLI_VALIDI}


@bp.route('/configura/accessi', methods=['GET', 'POST'])
def pagina():
    """Configura → Aree e accessi, la parte «Accesso dagli altri PC». Solo dal PC principale (Sistema)."""
    from app import ses, LUCCHETTO
    from modelli import scrivi_impostazione
    s = ses()
    if request.method == 'POST':
        azione = request.form.get('azione')
        password_nuova = request.form.get('password') or ''
        # l'impronta della password (lenta) prima del lucchetto, che ferma i salvataggi di tutti
        impronta = generate_password_hash(password_nuova) if azione in ('nuovo', 'password') and \
            not problema_password(password_nuova) else None
        with LUCCHETTO:
            cfg = configurazione(s)
            utenti = cfg['utenti']
            if azione == 'rete':
                accesa = request.form.get('accesa') == '1'
                testo_porta = (request.form.get('porta') or '').strip()
                porta = int(testo_porta) if testo_porta.isdigit() and len(testo_porta) < 6 else 0
                if not porta_ammessa(porta):
                    flash('Porta non valida: un numero fra 1024 e 65535, non la 5000 né quelle di riserva 5001–5009.',
                          'errore')
                    return redirect(url_for('accessi.pagina'))
                nomi = ' '.join(x for x in (request.form.get('nomi') or '').lower().split()
                                if re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,62}', x))[:300]
                scrivi_impostazione(s, 'rete_schermo_libero', '1' if request.form.get('schermo_libero') else '')
                scrivi_impostazione(s, 'rete_nomi', nomi)
                if accesa and not current_app.config.get('TESTING') and not ascolto.accendi(current_app._get_current_object(), porta):
                    # la porta si salva solo se l'ascolto è partito: altrimenti resta quella di prima
                    s.commit()
                    flash('L\'accesso dagli altri PC non è partito: %s' % ascolto.errore, 'errore')
                    return redirect(url_for('accessi.pagina'))
                scrivi_impostazione(s, 'rete_porta', str(porta))
                scrivi_impostazione(s, 'rete_accesa', '1' if accesa else '')
                s.commit()
                if accesa:
                    flash('Accesso dagli altri PC acceso: sugli altri PC aprire %s' % ' oppure '.join(
                        indirizzi_da_usare(porta)[:3]), 'ok')
                    if not [u for u in utenti if u.get('attivo', True)]:
                        flash('Nessun utente ancora: dagli altri PC non entra nessuno finché non se ne aggiunge uno qui '
                              'sotto.', 'avviso')
                else:
                    ascolto.spegni()
                    flash('Accesso dagli altri PC spento.', 'ok')
            elif azione == 'nuovo':
                nome = ' '.join((request.form.get('nome') or '').split())
                problema = problema_password(password_nuova, nome)
                if not NOME_VALIDO.fullmatch(nome):
                    flash('Nome non valido: da 2 a 40 fra lettere, cifre, spazi, punti, apostrofi e trattini.', 'errore')
                elif trova(utenti, nome):
                    flash('C\'è già un utente con questo nome.', 'errore')
                elif problema:
                    flash(problema, 'errore')
                else:
                    u = nuovo_utente(nome, password_nuova, impronta)
                    u['aree'] = _modulo_aree(u)
                    utenti.append(u)
                    salva_utenti(s, utenti)
                    s.commit()
                    annota('utente aggiunto dal PC principale', nome)
                    flash('Utente %s aggiunto: al primo accesso sceglierà la sua password.' % nome, 'ok')
            elif azione in ('salva', 'password', 'elimina', 'fai-uscire'):
                u = trova_id(utenti, request.form.get('utente'))
                if u is None:
                    flash('Utente non trovato.', 'errore')
                elif azione == 'salva':
                    u['aree'] = _modulo_aree(u)
                    attivo = request.form.get('attivo') == '1'
                    u['attivo'] = attivo
                    salva_utenti(s, utenti)
                    s.commit()
                    n = 0 if attivo else sessioni.togli_utente(u['id'])         # spento: esce subito
                    annota('aree salvate dal PC principale%s' % ('' if attivo else ' (utente spento)'), u['nome'])
                    flash('Aree di %s salvate.%s' % (u['nome'], ' Utente spento: è uscito.' if n else ''), 'ok')
                elif azione == 'password':
                    problema = problema_password(password_nuova, u['nome'])
                    if problema:
                        flash(problema, 'errore')
                    else:
                        u['hash'] = impronta
                        u['cambia'] = True
                        salva_utenti(s, utenti)
                        s.commit()
                        sessioni.togli_utente(u['id'])                         # chi era entrato rientra
                        tentativi.sblocca(u['nome'])
                        annota('password data dal PC principale', u['nome'])
                        flash('Password di %s cambiata: al prossimo accesso sceglierà la sua.' % u['nome'], 'ok')
                elif azione == 'fai-uscire':
                    n = sessioni.togli_utente(u['id'])
                    annota('fatto uscire dal PC principale', u['nome'])
                    flash('%s è uscito da %d PC.' % (u['nome'], n) if n else '%s non era entrato.' % u['nome'], 'ok')
                else:
                    utenti.remove(u)
                    salva_utenti(s, utenti)
                    s.commit()
                    sessioni.togli_utente(u['id'])
                    annota('utente tolto dal PC principale', u['nome'])
                    flash('Utente %s tolto.' % u['nome'], 'ok')
            elif azione == 'sblocca':
                tentativi.sblocca(request.form.get('nome'))
                annota('sbloccato dal PC principale', request.form.get('nome'))
                flash('Sbloccato: si può riprovare subito.', 'ok')
        return redirect(url_for('accessi.pagina'))
    cfg = configurazione(s)
    return render_template('accessi.html', cfg=cfg, aree=AREE, livelli=LIVELLI, acceso=ascolto.acceso(),
                           porta_accesa=ascolto.porta, errore_ascolto=ascolto.errore,
                           indirizzi=indirizzi_da_usare(ascolto.porta or cfg['porta']),
                           eventi=ultimi_accessi(), giorni_registro=7, bloccati=tentativi.bloccati(),
                           entrati=sessioni.quante, firewall=comandi_firewall(ascolto.porta or cfg['porta']),
                           consiglio=CONSIGLIO_PASSWORD, minimo=MINIMO_PASSWORD, sezione='impostazioni', sid=None)


def comandi_firewall(porta):
    """Per chi fa la regola del firewall di Windows a mano (prompt dei comandi aperto come amministratore): la
    regola solo per le reti private, e il comando che la toglie."""
    return ('netsh advfirewall firewall add rule name="%s" dir=in action=allow protocol=TCP localport=%d '
            'profile=private' % (NOME_REGOLA_FIREWALL, porta),
            'netsh advfirewall firewall delete rule name="%s"' % NOME_REGOLA_FIREWALL)


# ================================================================= aggancio
def installa(app):
    """Da app.py, dopo aver dichiarato tutte le pagine."""
    app.register_blueprint(bp)
    app.session_interface = SessioniDueNomi()
    app.before_request(controlla_accesso)
    app.after_request(dopo_la_risposta)

    @app.context_processor
    def per_i_modelli():
        valori = {'puo': puo, 'puo_cambiare': puo_cambiare, 'utente_rete': utente_attuale()}
        if dalla_rete():
            valori['popup_aggiornamento'] = lambda: None     # l'aggiornamento si fa solo dal PC principale
        return valori
