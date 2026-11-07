# -*- coding: utf-8 -*-
"""Email e WhatsApp ai pazienti: le email che partono da sole alla
prenotazione (per esempio la preparazione agli esami endoscopici, con le
informative allegate), i promemoria del giorno prima, l'invio a comando
dalla pagina dell'appuntamento, il registro di tutto.

Ogni messaggio passa da una coda nel database (tabella invii): la
prenotazione la riempie e risponde subito; un thread manda i messaggi,
riprova se manca la rete e scrive l'esito. Cosi' una connessione lenta non
blocca la segreteria, e dopo un riavvio niente si perde e niente parte due
volte.

Il lucchetto dei salvataggi si tiene solo per scrivere nella coda, mai
durante l'invio: un server lento non ferma le prenotazioni. Per lo stesso
motivo, mentre si spedisce, la sessione non ha modifiche in sospeso (che
SQLAlchemy scriverebbe da sola alla prima lettura, fuori dal lucchetto).

Le email partono dalla casella della struttura, qualsiasi casella con un
server di posta in uscita (SMTP): quella del sito della clinica (dominio
proprio, bastano indirizzo e password), Aruba, Gmail (con la "password per le
app", che richiede la verifica in due passaggi) o un altro server, anche
della rete interna senza password (CASELLE). I WhatsApp automatici
richiedono la WhatsApp Business Platform di Meta: un numero dedicato, un
modello di messaggio approvato e il suo token; finche' mancano, i promemoria
vanno per email a chi ce l'ha e il resto resta nella pagina Conferme."""
import base64
import json
import logging
import os
import re
import smtplib
import socket
import ssl
import sys
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from html import escape
from io import BytesIO
from types import SimpleNamespace

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort, send_file)
from sqlalchemy import select, or_

from modelli import (Struttura, Operatore, Prestazione, Appuntamento, Paziente, RegolaEmail, AllegatoRegola,
                     Invio, Impostazione, STATI_ATTIVI, ETICHETTA_STATO, leggi_impostazione,
                     scrivi_impostazione, cartella_risorse)
import servizi
import pazienti
import documenti
import viste
import comune
from comune import intero, destinazione_sicura

bp = Blueprint('invii', __name__, url_prefix='/invii')
_fornitore = None
_fabbrica = None
_lucchetto = threading.Lock()
_sveglia = threading.Event()
_thread = None

CANALI = {'EMAIL': 'Email', 'WHATSAPP': 'WhatsApp'}
MOTIVI = {'PREPARAZIONE': 'Email automatica', 'PROMEMORIA': 'Promemoria', 'PROVA': 'Prova'}
STATI = {'DA_INVIARE': 'in coda', 'IN_CORSO': 'in partenza', 'INVIATO': 'inviato', 'ERRORE': 'non partito',
         'ANNULLATO': 'annullato'}
VIVI = ('DA_INVIARE', 'IN_CORSO', 'INVIATO')     # un messaggio cosi' non va rimesso in coda
SICUREZZE = [('ssl', 'SSL (di solito porta 465)'), ('starttls', 'STARTTLS (di solito porta 587)'),
             ('nessuna', 'Nessuna (solo un server della rete interna)')]
# I tipi di casella, con server, porta e sicurezza gia' pronti; la pagina li
# propone scegliendo il tipo. 'dominio' e' la casella del sito della clinica:
# il server e' mail. + il dominio dell'indirizzo, come nei pannelli cPanel
# degli hosting (lo si corregge se il fornitore ne indica un altro).
CASELLE = [
    dict(codice='dominio', nome='Casella del sito della clinica (consigliata)', server='', porta='465', sicurezza='ssl',
         password='Password della casella'),
    dict(codice='aruba', nome='Aruba', server='smtps.aruba.it', porta='465', sicurezza='ssl',
         password='Password della casella'),
    dict(codice='gmail', nome='Gmail (serve la verifica in due passaggi)', server='smtp.gmail.com', porta='587',
         sicurezza='starttls', password='Password per le app'),
    dict(codice='altro', nome='Altro server', server='', porta='', sicurezza='', password='Password'),
]
PER_CODICE = {c['codice']: c for c in CASELLE}
# un SSLError con uno di questi motivi, collegandosi con SSL: dall'altra parte
# non c'e' SSL (per esempio la porta 587, che vuole STARTTLS)
SENZA_SSL = {'WRONG_VERSION_NUMBER', 'RECORD_LAYER_FAILURE', 'PACKET_LENGTH_TOO_LONG', 'UNKNOWN_PROTOCOL'}
# dopo un errore di rete si riprova dopo questi minuti; poi ci si ferma
ATTESE = [2, 10, 30, 120, 360]
MINUTI_BLOCCATO = 15          # "in partenza" da piu' di tanto: il programma si e' fermato a meta'
MASSIMO_ALLEGATO = 10 * 1024 * 1024
MASSIMO_TESTO = 10000
# email: nessun server di partenza (fino alla 1.9 era quello di Gmail, che chi
# l'usava ha comunque salvato con il modulo); email_accesso e' il nome utente
# per entrare nel server quando non e' l'indirizzo (vuoto: l'indirizzo)
PREDEFINITI = {
    'email_tipo': '', 'email_server': '', 'email_porta': '587', 'email_sicurezza': 'starttls', 'email_utente': '',
    'email_accesso': '', 'email_password': '', 'email_senza_password': '0', 'email_mittente': '', 'email_attiva': '1',
    'promemoria_attivo': '0', 'promemoria_ora': '10:00', 'promemoria_whatsapp': '1', 'promemoria_email': '1',
    'wa_token': '', 'wa_numero_id': '', 'wa_modello': 'promemoria_appuntamento', 'wa_lingua': 'it',
    'wa_parametri': 'paziente,giorno,ora,struttura,recapito', 'wa_versione': 'v25.0',
    'wa_indirizzo': 'https://graph.facebook.com', 'wa_registrato': '',
}
# cosa vuol dire, in parole semplici, un errore di Meta (codice dell'errore -> spiegazione)
SPIEGAZIONI_META = {
    190: 'il token non vale (scaduto o copiato male): crearne uno permanente con un utente di sistema e incollarlo qui',
    10: 'al token manca un permesso: servono whatsapp_business_messaging e whatsapp_business_management',
    200: 'al token manca un permesso: servono whatsapp_business_messaging e whatsapp_business_management',
    100: 'un dato non va: controllare l\'ID del numero di telefono (lo mostra Meta in «Configurazione API»)',
    131030: 'con il numero di prova di Meta si scrive solo ai numeri aggiunti fra i destinatari consentiti',
    131031: 'l\'account WhatsApp è bloccato da Meta: va controllato in WhatsApp Manager',
    132000: 'le variabili mandate non sono quante ne ha il modello: controllare «Variabili del modello»',
    132001: 'un modello con questo nome e questa lingua non c\'è, o non è ancora approvato',
    133005: 'PIN sbagliato: il numero ha già la verifica in due passaggi con un altro PIN. Usare quello, oppure '
            'disattivarla in WhatsApp Manager e sceglierne uno nuovo',
    133006: 'il numero va verificato di nuovo (codice via SMS o chiamata in WhatsApp Manager), poi si registra',
    133008: 'troppi PIN sbagliati: aspettare il tempo indicato da Meta e riprovare con il PIN giusto',
    133009: 'PIN provati troppo in fretta: aspettare almeno mezzo minuto e riprovare',
    133010: 'il numero non è ancora registrato: in Configura → Email e WhatsApp premere «Registra il numero»',
    133015: 'il numero è stato cancellato da poco: aspettare qualche minuto e riprovare',
    133016: 'troppe registrazioni (al massimo 10 in 72 ore): riprovare fra tre giorni',
}


def spiega_meta(codice):
    """' Il token non vale...' da aggiungere al messaggio di Meta; vuoto se il codice non e' fra quelli noti."""
    try:
        testo = SPIEGAZIONI_META.get(int(codice))
    except (TypeError, ValueError):
        testo = None
    return '. %s%s.' % (testo[0].upper(), testo[1:]) if testo else ''
PARAMETRI_WA = ['paziente', 'giorno', 'data', 'ora', 'struttura', 'indirizzo', 'prestazione', 'medico',
                'stanza', 'recapito', 'telefono_struttura']
MODELLO_WA = ("Gentile {{1}}, le ricordiamo l'appuntamento di {{2}} alle ore {{3}} presso {{4}}. "
              "Per disdire o spostare l'appuntamento {{5}}. Grazie.")

# la regola gia' pronta per la Clinica Posillipo: la mail che l'accettazione
# manda oggi a mano, con le due informative del servizio di endoscopia
PRONTA_NOME = 'Preparazione esami endoscopici'
PRONTA_OGGETTO = 'INFORMAZIONI E PREPARAZIONE (GASTROSCOPIA/COLONSCOPIA)'
PRONTA_TESTO = """Gentile Paziente,

In allegato alla presente e-mail troverà le guide informative e le istruzioni di preparazione per gli esami endoscopici.

La preghiamo di consultare ed attenzionare esclusivamente il file relativo all'esame che dovrà effettuare con il Dr. Giovanni Galasso.
- Allegato Gastroscopia: da leggere solo se deve effettuare la Gastroscopia.
- Allegato Colonscopia: da leggere solo se deve effettuare la Colonscopia.

La invitiamo a leggere attentamente il documento di suo interesse con congruo anticipo e a seguire scrupolosamente le indicazioni riportate.

⚠️ ATTENZIONE:
Nel caso in cui effettuasse contestualmente entrambe le procedure endoscopiche, si raccomanda di interrompere l'assunzione di qualsiasi liquido (inclusa acqua) a partire da quattro ore prima dell'orario fissato per l'appuntamento.

Restiamo a disposizione per qualsiasi chiarimento.

Cordiali saluti,
La direzione."""
PRONTA_ALLEGATI = ['INFORMATIVA_EGDS.pdf', 'INFORMATIVA_COLONSCOPIA.pdf']
# parti del nome (senza accenti e spazi) delle prestazioni con quella
# preparazione. Non "gastro": prenderebbe anche la visita gastroenterologica
PRONTA_PRESTAZIONI = ('egds', 'gastroscop', 'colonscop')


class ErroreInvio(Exception):
    """'permanente': riprovare non serve (password sbagliata, indirizzo
    rifiutato); altrimenti e' la rete, e si riprova piu' tardi."""
    def __init__(self, messaggio, permanente=False):
        super().__init__(messaggio)
        self.permanente = permanente


def collega(app, fornitore_sessione, lucchetto=None, fabbrica=None):
    """fabbrica: una funzione che restituisce una sessione nuova, per il
    thread della coda e per gli invii dai pulsanti."""
    global _fornitore, _lucchetto, _fabbrica
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    _fabbrica = fabbrica
    app.register_blueprint(bp)


def ses():
    return _fornitore()


def fabbrica_sessioni():
    """Una sessione nuova, mai quella della pagina: manda_subito la chiude."""
    if _fabbrica is not None:
        return _fabbrica()
    return _fornitore().session_factory()


_ultimi_errori = {}


def _registra_errore(chiave):
    """Un errore che si ripete a ogni giro finisce nel registro una volta
    l'ora, non 1440 volte al giorno."""
    import traceback
    testo = traceback.format_exc()
    prima = _ultimi_errori.get(chiave)
    if prima is None or prima[0] != testo or datetime.now() - prima[1] > timedelta(hours=1):
        _ultimi_errori[chiave] = (testo, datetime.now())
        logging.error('%s:\n%s', chiave, testo)


# ============================================================ impostazioni
def impostazioni(s):
    salvate = {r.chiave: r.valore for r in s.scalars(
        select(Impostazione).where(Impostazione.chiave.in_(list(PREDEFINITI))))}
    return {k: (salvate.get(k) or v) for k, v in PREDEFINITI.items()}


def email_pronta(cfg):
    """Si possono mandare email: invio acceso, server, indirizzo e password
    (o un server che non la chiede)."""
    return cfg['email_attiva'] == '1' and bool(cfg['email_server'] and cfg['email_utente'] and (
        cfg['email_password'] or cfg.get('email_senza_password') == '1'))


def _dominio(indirizzo):
    return (indirizzo or '').strip().rpartition('@')[2].strip().lower().rstrip('.')


def _di_google(server):
    s = (server or '').strip().lower().rstrip('.')
    return s.endswith('gmail.com') or s.endswith('googlemail.com')


def _di_microsoft(server):
    s = (server or '').strip().lower().rstrip('.')
    return any(s.endswith(d) for d in ('office365.com', 'outlook.com', 'hotmail.com', 'live.com'))


def tipo_casella(cfg, indirizzo=''):
    """Il tipo di casella: quello scelto nella pagina; se non c'e' (salvato
    con la 1.9, o mai salvato) si ricava dal server e, senza server,
    dall'indirizzo. Una casella @gmail.com e' Gmail, il resto la casella del
    sito della clinica."""
    if cfg.get('email_tipo') in PER_CODICE:
        return cfg['email_tipo']
    server = (cfg.get('email_server') or '').strip().lower().rstrip('.')
    dominio = _dominio(indirizzo or cfg.get('email_utente'))
    if server:
        if _di_google(server):
            return 'gmail'
        if server in ('smtps.aruba.it', 'smtp.aruba.it'):
            return 'aruba'
        return 'dominio' if dominio and server == 'mail.' + dominio else 'altro'
    return 'gmail' if dominio in ('gmail.com', 'googlemail.com') else 'dominio'


def server_proposto(tipo, indirizzo=''):
    """Il server da proporre per il tipo: quello del fornitore, o per la
    casella del sito mail. + il dominio dell'indirizzo; vuoto se non si sa."""
    if tipo == 'dominio':
        dominio = _dominio(indirizzo)
        return 'mail.' + dominio if re.fullmatch(r'[a-z0-9.\-]{1,110}\.[a-z]{2,}', dominio) else ''
    return PER_CODICE.get(tipo, {}).get('server', '')


def whatsapp_pronto(cfg):
    return bool(cfg['wa_token'] and cfg['wa_numero_id'] and cfg['wa_modello'])


# La password e il token si salvano cifrati con la protezione dati di Windows
# (DPAPI): li legge solo lo stesso utente sullo stesso PC. Un database copiato
# altrove li ha illeggibili, e basta riscriverli. Fuori da Windows (le prove)
# restano solo codificati.
def _dpapi(dati, cifra):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    memoria = ctypes.create_string_buffer(dati, len(dati))
    entrata = BLOB(len(dati), ctypes.cast(memoria, ctypes.POINTER(ctypes.c_char)))
    uscita = BLOB()
    crypt32 = ctypes.windll.crypt32
    funzione = crypt32.CryptProtectData if cifra else crypt32.CryptUnprotectData
    # 0x01 = CRYPTPROTECT_UI_FORBIDDEN: mai una finestra di Windows
    if not funzione(ctypes.byref(entrata), None, None, None, None, 0x01, ctypes.byref(uscita)):
        raise OSError('protezione dati di Windows non riuscita')
    try:
        return ctypes.string_at(uscita.pbData, uscita.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(uscita.pbData)


def proteggi(testo):
    if not testo:
        return ''
    dati = testo.encode('utf-8')
    if sys.platform == 'win32':
        try:
            return 'dpapi:' + base64.b64encode(_dpapi(dati, True)).decode('ascii')
        except Exception as e:
            logging.warning('DPAPI non disponibile, password solo codificata: %s', e)
    return 'chiaro:' + base64.b64encode(dati).decode('ascii')


def svela(valore):
    if not valore:
        return ''
    tipo, _, resto = valore.partition(':')
    try:
        if tipo == 'dpapi':
            return _dpapi(base64.b64decode(resto), False).decode('utf-8')
        if tipo == 'chiaro':
            return base64.b64decode(resto).decode('utf-8')
    except Exception:
        pass
    raise ErroreInvio('la password salvata non si legge su questo PC o con questo utente di Windows: va '
                      'riscritta in Configura → Email e WhatsApp', permanente=True)


# ================================================================== testi
def firma(st):
    """Le righe in fondo alle email: come nella firma che la struttura usa
    gia' (societa', indirizzo, telefono, email)."""
    if st is None:
        return []
    righe = [st.societa or st.nome]
    if (st.indirizzo or '').strip():
        righe.append(st.indirizzo.strip())
    if (st.telefono or '').strip():
        righe.append('Tel: %s' % st.telefono.strip())
    if (st.email or '').strip():
        righe.append('Mail: %s' % st.email.strip())
    return [r for r in righe if r]


def compila(testo, a):
    """I segnaposto dei moduli ({giorno}, {ora}, {data-3}...), con il nome del
    paziente scritto per bene: 'Gentile {paziente}' diventa 'Gentile Anna
    Esposito', non 'Gentile ESPOSITO ANNA'."""
    testo = re.sub(r'\{paziente\}', lambda m: viste._cortese(a.paziente) or 'Paziente', testo or '', flags=re.I)
    return documenti.compila(testo, a)


def valori_whatsapp(a):
    """I valori puliti per le variabili del modello WhatsApp: senza le
    virgole che servono quando si incollano in una frase."""
    st = a.risorsa.struttura if a.risorsa else None
    tel = (st.telefono or '').strip() if st else ''
    return {
        'paziente': viste._cortese(a.paziente) or 'paziente',
        'giorno': '%s %d %s' % (servizi.GIORNI[a.inizio.weekday()], a.inizio.day, servizi.MESI[a.inizio.month - 1]),
        'data': a.inizio.strftime('%d/%m/%Y'), 'ora': a.inizio.strftime('%H:%M'),
        'struttura': st.nome if st else '', 'indirizzo': (st.indirizzo or '').strip() if st else '',
        'prestazione': a.prestazione.nome if a.prestazione else '',
        'medico': a.operatore.etichetta if a.operatore else '', 'stanza': a.risorsa.nome if a.risorsa else '',
        'recapito': ('chiami il ' + tel) if tel else 'ci contatti', 'telefono_struttura': tel,
    }


def parametri_whatsapp(cfg, a):
    valori = valori_whatsapp(a)
    nomi = [x.strip() for x in cfg['wa_parametri'].split(',') if x.strip()]
    # Meta rifiuta le variabili vuote e quelle con a capo o tabulazioni
    return [(' '.join((valori.get(n) or '').split()) or '-')[:200] for n in nomi]


def struttura_di(s, a=None):
    if a is not None and a.risorsa is not None and a.risorsa.struttura is not None:
        return a.risorsa.struttura
    return s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).first()


def appuntamento_di_prova(s, regola=None):
    """Un appuntamento finto per provare il testo di una regola: dati di
    esempio, mai un paziente vero, e nessun oggetto nel database."""
    st = struttura_di(s)
    quando = datetime.combine(date.today() + timedelta(days=3), time(9, 0))
    medico = regola.operatore if regola is not None and regola.operatore is not None else None
    prest = None
    if regola is not None and regola.id_prestazioni:
        prest = s.scalars(select(Prestazione).where(Prestazione.id.in_(sorted(regola.id_prestazioni)))
                          .order_by(Prestazione.nome)).first()
    paziente = SimpleNamespace(id=None, cognome='Prova', nome='Paziente', etichetta='Prova Paziente',
                               data_nascita=None, codice_fiscale='', telefono='', telefono2='', email='',
                               indirizzo='', promemoria=True, canale='EMAIL', sesso='', luogo_nascita='')
    return SimpleNamespace(
        id=None, paziente=paziente, paziente_id=None, inizio=quando, fine=quando + timedelta(minutes=30),
        stato='PRENOTATO', risorsa=SimpleNamespace(nome='Ambulatorio', struttura=st),
        operatore=SimpleNamespace(etichetta=medico.etichetta if medico else 'Dott. Medico'),
        prestazione=SimpleNamespace(nome=prest.nome if prest else 'Visita',
                                    preparazione=(prest.preparazione or '') if prest else ''))


# ============================================================== le regole
def regole_attive(s):
    return s.scalars(select(RegolaEmail).where(RegolaEmail.attiva == True).order_by(RegolaEmail.id)).all()


def scegli_regole(regole, operatore_id, prestazione_id, prestazioni_di=None):
    """Fra le regole (attive, in ordine) quelle che partono per un appuntamento
    di quel medico e di quella prestazione.

    Ogni medico puo' avere le sue email, con testi e informative sue: una
    regola del medico che nomina la prestazione prende il posto di quelle
    "per tutti i medici" per la stessa prestazione. Una regola del medico
    senza prestazioni (vale per tutte le sue) si aggiunge e basta: non deve
    togliere a nessuno la preparazione di un esame. Una regola senza medico
    e senza prestazioni non vale mai (non si salva, ma non si sa mai)."""
    if operatore_id is None:
        return []
    di = prestazioni_di or (lambda r: r.id_prestazioni)
    del_medico, per_tutti, sostituisce = [], [], False
    for r in regole:
        prestazioni = di(r)
        if r.operatore_id:
            if r.operatore_id != operatore_id:
                continue
            if not prestazioni:
                del_medico.append(r)
            elif prestazione_id in prestazioni:
                del_medico.append(r)
                sostituisce = True
        elif prestazioni and prestazione_id in prestazioni:
            per_tutti.append(r)
    return sorted(del_medico + ([] if sostituisce else per_tutti), key=lambda r: r.id or 0)


def regole_per(s, a):
    """Le regole attive che partono per questo appuntamento."""
    if a is None or a.operatore_id is None:
        return []
    return scegli_regole(regole_attive(s), a.operatore_id, a.prestazione_id)


def incroci(s, regola, regole=None):
    """Come la regola convive con le altre attive; lei conta come attiva anche
    se e' spenta, per dire cosa succede accendendola. Restituisce un
    dizionario con tre elenchi {id dell'altra regola: {medico: {prestazioni}}},
    dove il medico 0 vuol dire "un medico senza email sue" e la prestazione 0
    "una prestazione che nessuna regola nomina":
      insieme     le due email partono per lo stesso appuntamento: il paziente
                  ne riceve due;
      sostituita  (regola per tutti i medici) per quei medici parte invece la loro;
      sostituisce (regola di un medico) per lui parte questa al posto di quella
                  per tutti i medici;
    piu' 'medici' (quelli con email loro) e 'prestazioni' (quelle nominate),
    per descriverli. Basta provare i medici con email loro piu' uno
    qualsiasi, e le prestazioni nominate piu' una qualsiasi: tutti gli altri
    casi sono uguali a questi."""
    regole = [r for r in (regole if regole is not None else regole_attive(s)) if r.id != regola.id] + [regola]
    regole.sort(key=lambda r: r.id or 0)
    cache = {id(r): r.id_prestazioni for r in regole}
    di = lambda r: cache[id(r)]
    medici = sorted({r.operatore_id for r in regole if r.operatore_id})
    prestazioni = set().union(*[di(r) for r in regole])
    uscita = {'insieme': {}, 'sostituita': {}, 'sostituisce': {}, 'medici': medici, 'prestazioni': prestazioni}

    def segna(dove, altra, medico, prestazione):
        uscita[dove].setdefault(altra.id, {}).setdefault(medico, set()).add(prestazione)

    for m in medici + [0]:
        for p in sorted(prestazioni) + [0]:
            scelte = scegli_regole(regole, m or -1, p or -1, di)
            if regola in scelte:
                for altra in scelte:
                    if altra is not regola:
                        segna('insieme', altra, m, p)
                if regola.operatore_id and p in di(regola):
                    for altra in regole:
                        if not altra.operatore_id and p in di(altra):
                            segna('sostituisce', altra, m, p)
            elif not regola.operatore_id and p in di(regola):
                for altra in scelte:
                    if altra.operatore_id and p in di(altra):
                        segna('sostituita', altra, m, p)
    return uscita


def descrivi_incrocio(gruppi, info, nomi_medici, nomi_prestazioni):
    """{medico: {prestazioni}} di incroci() in parole, per esempio
    'Dr. Galasso (Colonscopia, EGDS); gli altri medici (Colonscopia)'."""
    parti = []
    for m in sorted(gruppi, key=lambda m: (m == 0, (nomi_medici.get(m) or '').lower())):
        quali = gruppi[m]
        if 0 in quali and quali >= info['prestazioni']:
            cosa = 'tutte le prestazioni'
        else:
            nomi = sorted((nomi_prestazioni.get(p) or '?' for p in quali if p), key=str.lower)
            if 0 in quali:
                nomi.append('le prestazioni che nessuna email nomina')
            cosa = ', '.join(nomi)
        if m:
            chi = nomi_medici.get(m) or '?'
        else:
            chi = 'gli altri medici' if info['medici'] else 'tutti i medici'
        parti.append('%s (%s)' % (chi, cosa))
    return '; '.join(parti)


def regole_del_medico(s, operatore_id):
    return s.scalars(select(RegolaEmail).where(RegolaEmail.operatore_id == operatore_id)
                     .order_by(RegolaEmail.nome, RegolaEmail.id)).all()


def gia_in_coda(s, a, regola=None, motivo='PREPARAZIONE', per_inizio=None):
    """C'e' gia' un messaggio di quel tipo, in coda o partito, per questo
    appuntamento e questo paziente?"""
    q = select(Invio.id).where(Invio.appuntamento_id == a.id, Invio.motivo == motivo, Invio.stato.in_(VIVI))
    if a.paziente_id:
        q = q.where(Invio.paziente_id == a.paziente_id)
    if regola is not None:
        q = q.where(Invio.regola_id == regola.id)
    if per_inizio is not None:
        q = q.where(Invio.per_inizio == per_inizio)
    return s.scalars(q).first() is not None


def gemello(s, a, regola):
    """La stessa email gia' mandata allo stesso paziente per un altro
    appuntamento dello stesso giorno (gastroscopia e colonscopia prenotate
    separatamente: il testo parla gia' di tutte e due)."""
    if not a.paziente_id:
        return None
    inizio = datetime.combine(a.inizio.date(), time(0, 0))
    return s.scalars(select(Invio).where(
        Invio.paziente_id == a.paziente_id, Invio.regola_id == regola.id, Invio.motivo == 'PREPARAZIONE',
        # 1.11: anche quella di un appuntamento poi eliminato (appuntamento_id vuoto):
        # con «!= a.id» da sola SQLite la scartava, e l'email partiva una seconda volta
        Invio.stato.in_(VIVI), or_(Invio.appuntamento_id.is_(None), Invio.appuntamento_id != a.id),
        Invio.per_inizio >= inizio,
        Invio.per_inizio < inizio + timedelta(days=1))).first()


def gia_per_la_serie(s, a, regola):
    """La stessa email automatica e' gia' in coda o partita per un altro
    appuntamento della stessa serie, per lo stesso paziente? Una serie riceve
    l'email una volta sola (la preparazione e' la stessa): prima, modificando
    un appuntamento della serie dopo il primo, partiva di nuovo. Per regola e
    per paziente: un appuntamento della serie passato a un altro medico (con
    la sua email) o a un altro paziente la riceve lo stesso."""
    if not a.serie or not a.paziente_id:
        return False
    return s.scalars(select(Invio.id).join(Appuntamento, Invio.appuntamento_id == Appuntamento.id).where(
        Appuntamento.serie == a.serie, Appuntamento.id != a.id, Invio.paziente_id == a.paziente_id,
        Invio.regola_id == regola.id, Invio.motivo == 'PREPARAZIONE', Invio.stato.in_(VIVI))).first() is not None


def accoda(s, canale, motivo, destinatario, a=None, regola=None, a_mano=False, oggetto='', testo='',
           subito=False):
    """Un messaggio nella coda. 'subito': lo manda chi lo crea, adesso (i
    pulsanti), quindi nasce gia' "in partenza" e il thread non lo tocca."""
    adesso = datetime.now()
    x = Invio(canale=canale, motivo=motivo, destinatario=(destinatario or '')[:120],
              appuntamento_id=a.id if a is not None else None,
              paziente_id=a.paziente_id if a is not None else None, regola_id=regola.id if regola else None,
              per_inizio=a.inizio if a is not None else None, oggetto=(oggetto or '')[:200], testo=testo or '',
              stato='IN_CORSO' if subito else 'DA_INVIARE', prossimo=adesso, a_mano=a_mano, creato_il=adesso,
              tentativi=0, errore='')
    s.add(x)
    s.flush()
    return x


def dopo_salvataggio(s, a, notizie, avvisi, adesso=None):
    """Dalla prenotazione, col lucchetto preso e prima del commit: le email
    delle regole che valgono per l'appuntamento entrano in coda (una volta
    sola per regola e paziente, anche se l'appuntamento si modifica).
    'notizie' e 'avvisi' dicono a chi prenota cosa e' successo, mentre il
    paziente e' ancora al telefono. Niente email per gli appuntamenti gia'
    passati: chi ricopia l'agenda di ieri non manda preparazioni."""
    adesso = adesso or datetime.now()
    if a.stato not in STATI_ATTIVI or a.inizio < adesso or not a.paziente_id:
        return []
    regole = [r for r in regole_per(s, a) if not gia_in_coda(s, a, r)]
    della_serie = [r for r in regole if gia_per_la_serie(s, a, r)]
    if della_serie:
        notizie.append('Email %s già mandata per questa serie di appuntamenti.' % ', '.join(
            '«%s»' % r.nome for r in della_serie))
        regole = [r for r in regole if r not in della_serie]
    if not regole:
        return []
    p = s.get(Paziente, a.paziente_id)
    cfg = impostazioni(s)
    email = (p.email or '').strip() if p is not None else ''
    nomi = ', '.join('«%s»' % r.nome for r in regole)
    if not email_pronta(cfg):
        avvisi.append('Email %s non mandata: l\'invio delle email non è ancora configurato '
                      '(Configura → Email e WhatsApp).' % nomi)
        return []
    if not pazienti.email_valida(email):
        avvisi.append('Email %s non mandata: il paziente non ha un indirizzo email. Si può mandare dopo '
                      'dalla pagina dell\'appuntamento.' % nomi)
        return []
    fatti = []
    for r in regole:
        doppio = gemello(s, a, r)
        if doppio is not None:
            notizie.append('Email «%s» già mandata al paziente per l\'appuntamento delle %s.' % (
                r.nome, doppio.per_inizio.strftime('%H:%M')))
            continue
        fatti.append(accoda(s, 'EMAIL', 'PREPARAZIONE', email, a, r))
    if fatti:
        notizie.append('Email %s in partenza per %s.' % (', '.join('«%s»' % x.regola.nome for x in fatti), email))
    return fatti


# ============================================================ il promemoria
def canale_promemoria(cfg, p):
    """WhatsApp se e' configurato, il paziente ha un cellulare e non preferisce
    l'email; altrimenti email, se ce l'ha. (None, ''): resta da fare a mano."""
    if p is None or p.promemoria is False:
        return None, ''
    numero = pazienti.cellulare_whatsapp(p)
    email = (p.email or '').strip()
    con_whatsapp = cfg['promemoria_whatsapp'] == '1' and whatsapp_pronto(cfg) and bool(numero)
    con_email = cfg['promemoria_email'] == '1' and email_pronta(cfg) and pazienti.email_valida(email)
    if con_whatsapp and not (p.canale == 'EMAIL' and con_email):
        return 'WHATSAPP', numero
    if con_email:
        return 'EMAIL', email
    return None, ''


def accoda_promemoria(s, a, cfg, a_mano=False):
    p = s.get(Paziente, a.paziente_id) if a.paziente_id else None
    canale, destinatario = canale_promemoria(cfg, p)
    if canale is None:
        return None
    if not a_mano and gia_in_coda(s, a, motivo='PROMEMORIA', per_inizio=a.inizio):
        return None
    return accoda(s, canale, 'PROMEMORIA', destinatario, a, a_mano=a_mano, subito=a_mano)


def prossimo_giorno_aperto(s, st, dopo):
    """Il primo giorno dopo 'dopo' in cui la struttura lavora: il sabato e' il
    lunedi', prima di un ponte e' il giorno dopo il ponte."""
    regole = servizi.Regole(s, dopo + timedelta(days=1), dopo + timedelta(days=10))
    for i in range(1, 11):
        g = dopo + timedelta(days=i)
        info = regole.giorno(g, st)
        if info.get('chiusura') or info.get('chiude_festivo'):
            continue
        if g.weekday() in st.giorni_aperti:
            return g
    return None


def giorni_del_giro(s, st, oggi):
    """I giorni di cui il giro di oggi manda i promemoria: fino al prossimo
    giorno di lavoro compreso. Il venerdi' (sabato chiuso) sono sabato,
    domenica e lunedi': un intervento fissato di domenica non resta escluso."""
    ultimo = prossimo_giorno_aperto(s, st, oggi)
    if ultimo is None:
        return []
    return [oggi + timedelta(days=i) for i in range(1, (ultimo - oggi).days + 1)]


def giro_promemoria(s, adesso, cfg=None):
    """Una volta al giorno, dall'ora scelta: i promemoria fino al prossimo
    giorno di lavoro di ogni struttura. Se il PC era spento a quell'ora, il
    giro si fa appena il programma parte. Restituisce quanti ne ha messi in
    coda; il chiamante tiene il lucchetto e fa il commit."""
    cfg = cfg or impostazioni(s)
    if cfg['promemoria_attivo'] != '1':
        return 0
    try:
        ora = datetime.strptime(cfg['promemoria_ora'], '%H:%M').time()
    except ValueError:
        ora = time(10, 0)
    oggi = adesso.date()
    if adesso.time() < ora or leggi_impostazione(s, 'promemoria_ultimo_giro', '') == oggi.isoformat():
        return 0
    n = 0
    for st in s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).all():
        for g in giorni_del_giro(s, st, oggi):
            for a in servizi.elenco_giorno(s, g, st.id, ('PRENOTATO', 'CONFERMATO')):
                if a.paziente_id and a.inizio > adesso and accoda_promemoria(s, a, cfg):
                    n += 1
    scrivi_impostazione(s, 'promemoria_ultimo_giro', oggi.isoformat())
    logging.info('promemoria in coda: %d', n)
    return n


def anteprima_promemoria(s, cfg, oggi=None):
    """Per la pagina: chi riceverebbe il promemoria nel prossimo giro."""
    oggi = oggi or date.today()
    conti = {'WHATSAPP': 0, 'EMAIL': 0, None: 0}
    giorni = []
    for st in s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).all():
        for g in giorni_del_giro(s, st, oggi):
            if g not in giorni:
                giorni.append(g)
            for a in servizi.elenco_giorno(s, g, st.id, ('PRENOTATO', 'CONFERMATO')):
                if a.paziente_id:
                    conti[canale_promemoria(cfg, a.paziente)[0]] += 1
    return {'giorni': sorted(giorni), 'whatsapp': conti['WHATSAPP'], 'email': conti['EMAIL'],
            'a_mano': conti[None]}


# ================================================================== spedire
def contesto_tls():
    """I certificati del sistema piu' l'elenco Mozilla dentro il programma
    (comune.contesto_tls)."""
    return comune.contesto_tls()


def testi_email(s, x, a):
    """(oggetto, testo, allegati) dell'email, compilati adesso: se nel
    frattempo l'appuntamento e' stato spostato, la mail dice l'ora giusta."""
    if x.motivo == 'PREPARAZIONE' or (x.motivo == 'PROVA' and x.regola_id):
        r = x.regola
        if r is None:
            raise ErroreInvio('la regola di questa email è stata eliminata', permanente=True)
        base = a if x.motivo == 'PREPARAZIONE' else appuntamento_di_prova(s, r)
        oggetto = compila(r.oggetto, base)
        if x.motivo == 'PROVA':
            oggetto = '[PROVA] ' + oggetto
        return oggetto, compila(r.testo, base), [(g.nome, g.tipo, g.dati) for g in r.allegati]
    if x.motivo == 'PROMEMORIA':
        modello, modello_oggetto = viste.modelli_messaggio(s)
        return viste.testo_messaggio(a, modello_oggetto), viste.testo_messaggio(a, modello), []
    return x.oggetto or '', x.testo or '', []


def componi_email(s, x, cfg, oggetto, testo, allegati, st):
    """Il messaggio pronto: testo semplice e la stessa cosa in HTML, con il
    logo e la firma della struttura in fondo, e gli allegati."""
    righe_firma = firma(st)
    m = EmailMessage()
    m['Subject'] = ' '.join((oggetto or '(senza oggetto)').split())
    m['From'] = formataddr((cfg['email_mittente'] or (st.nome if st else ''), cfg['email_utente']))
    m['To'] = x.destinatario
    risposte = (st.email or '').strip() if st is not None else ''
    if pazienti.email_valida(risposte) and risposte.lower() != cfg['email_utente'].lower():
        m['Reply-To'] = risposte
    m['Date'] = formatdate(localtime=True)
    m['Message-ID'] = make_msgid(domain=(cfg['email_utente'].split('@')[-1] or 'gestionale.local'))
    m.set_content(testo + ('\n\n--\n' + '\n'.join(righe_firma) if righe_firma else '') + '\n')
    logo = st.logo if st is not None and st.ha_logo and st.logo else None
    cid = make_msgid(domain='logo.gestionale')
    paragrafi = ''.join('<p style="margin:0 0 12px">%s</p>' % escape(p).replace('\n', '<br>')
                        for p in re.split(r'\n\s*\n', testo.strip()) if p.strip())
    piede = ''
    if righe_firma or logo:
        piede = ('<table style="margin-top:22px;border-top:1px solid #d0d7de;padding-top:12px"><tr>%s'
                 '<td style="font-size:13px;color:#33475b;line-height:1.5">%s</td></tr></table>') % (
            '<td style="padding-right:14px;vertical-align:top"><img src="cid:%s" alt="" style="max-height:56px"></td>'
            % cid[1:-1] if logo else '', '<br>'.join(escape(r) for r in righe_firma))
    # i caratteri del sito della clinica, dove il PC del paziente li ha; altrimenti quelli di sistema
    m.add_alternative('<!doctype html><html><body style="font-family:Inter,-apple-system,\'Segoe UI\',Arial,sans-serif;'
                      'font-size:15px;'
                      'color:#1f2328;line-height:1.45">%s%s</body></html>' % (paragrafi, piede), subtype='html')
    if logo:
        m.get_payload()[1].add_related(logo, 'image', 'png', cid=cid)
    for nome, tipo, dati in allegati:
        principale, _, secondario = (tipo or 'application/octet-stream').partition('/')
        m.add_attachment(dati or b'', maintype=principale, subtype=secondario or 'octet-stream', filename=nome)
    return m


def _risposta(e, quanto=120):
    """La risposta del server, codice e testo, in una riga accorciata
    («535 5.7.8 Username and Password not accepted»)."""
    grezza = getattr(e, 'smtp_error', b'') or b''
    testo = grezza.decode('utf-8', 'replace') if isinstance(grezza, bytes) else str(grezza)
    codice = getattr(e, 'smtp_code', None)
    testo = ' '.join(('%s %s' % (codice, testo) if isinstance(codice, int) and codice > 0 else testo).split())
    return testo if len(testo) <= quanto else testo[:quanto - 1] + '…'


def spiega_accesso_rifiutato(cfg, e=None):
    """Il server non ha accettato nome utente e password: cosa controllare,
    secondo il fornitore, con la risposta del server per chi ne sa."""
    if _di_google(cfg.get('email_server')):
        testo = ('Gmail non ha accettato indirizzo e password: serve la "password per le app" (16 lettere), non la '
                 'password normale dell\'account')
    elif _di_microsoft(cfg.get('email_server')):
        testo = ('Microsoft non ha accettato l\'accesso: con Outlook.com e Hotmail non si entra più con la password da '
                 'un programma come questo, con Microsoft 365 l\'invio con password (SMTP AUTH) deve permetterlo '
                 'l\'amministratore. Meglio la casella del sito della clinica o Aruba')
    else:
        testo = ('il server email non ha accettato nome utente e password: controllare la password della casella (la '
                 'stessa della webmail) e, se il fornitore ne dà uno diverso dall\'indirizzo, il nome utente')
    risposta = _risposta(e) if e is not None else ''
    return testo + (' (risposta del server: %s)' % risposta if risposta else '')


ACCESSO_NON_ASCII = ('la password (o il nome utente) contiene lettere accentate o simboli come € £ § che questo '
                     'server non accetta per l\'accesso: nel pannello della casella sceglierne una con lettere senza '
                     'accento, numeri e simboli comuni, e scriverla in Configura → Email e WhatsApp')


def accedi(server, utente, password):
    """L'accesso al server della casella. smtplib manda nome utente e password
    solo in ASCII: con una lettera accentata o un simbolo come € si fermava con
    un «errore inatteso: ascii codec». In quel caso l'accesso AUTH PLAIN si fa
    a mano in UTF-8 (RFC 4616), che i server di solito accettano; se il server
    non lo offre, l'errore dice cosa correggere."""
    if utente.isascii() and password.isascii():
        server.login(utente, password)
        return
    server.ehlo_or_helo_if_needed()
    if 'PLAIN' not in (server.esmtp_features.get('auth') or '').upper().split():
        raise ErroreInvio(ACCESSO_NON_ASCII, permanente=True)
    credenziali = base64.b64encode(('\0%s\0%s' % (utente, password)).encode('utf-8')).decode('ascii')
    codice, risposta = server.docmd('AUTH', 'PLAIN ' + credenziali)
    if codice not in (235, 503):          # 503: gia' entrati
        raise smtplib.SMTPAuthenticationError(codice, risposta)


def manda_email(cfg, messaggio):
    """Con la casella della struttura. Gli errori diventano ErroreInvio, con un
    testo che la segreteria capisce e che dice cosa correggere; permanente
    quando riprovare non serve (va cambiato qualcosa nelle impostazioni)."""
    senza_password = cfg.get('email_senza_password') == '1'
    password = '' if senza_password else svela(cfg['email_password'])
    try:
        porta = int(cfg['email_porta'] or 587)
    except ValueError:
        raise ErroreInvio('porta del server email non valida', permanente=True)
    nome_server = (cfg['email_server'] or '').strip()
    sicurezza = cfg['email_sicurezza']
    # il nome del PC per il saluto al server: senza, smtplib lo chiede al DNS, e su
    # certe reti la risposta si fa attendere
    nome_pc = re.sub(r'[^A-Za-z0-9.\-]', '', socket.gethostname()) or 'gestionale'
    try:
        if sicurezza == 'ssl':
            server = smtplib.SMTP_SSL(nome_server, porta, local_hostname=nome_pc, timeout=30, context=contesto_tls())
        else:
            server = smtplib.SMTP(nome_server, porta, local_hostname=nome_pc, timeout=30)
        try:
            if sicurezza == 'starttls':
                server.starttls(context=contesto_tls())
            if password:
                accedi(server, (cfg.get('email_accesso') or '').strip() or cfg['email_utente'], password)
            server.send_message(messaggio)
        finally:
            try:
                server.quit()
            except Exception:
                pass
    except smtplib.SMTPAuthenticationError as e:
        raise ErroreInvio(spiega_accesso_rifiutato(cfg, e), permanente=True)
    except smtplib.SMTPNotSupportedError as e:
        if 'STARTTLS' in str(e).upper():
            raise ErroreInvio('il server non offre STARTTLS su questa porta: provare la porta 465 con SSL, o chiedere '
                              'a chi gestisce la casella porta e sicurezza giuste', permanente=True)
        if 'SMTPUTF8' in str(e).upper():
            # 1.11: un indirizzo con lettere accentate; prima la colpa andava alle impostazioni dell'accesso
            mittente = cfg.get('email_utente') or ''
            chi = mittente if not mittente.isascii() else str(messaggio['To'] or '')
            raise ErroreInvio('l\'indirizzo «%s» contiene lettere accentate o caratteri speciali che il server email '
                              'non accetta: di solito è un errore di battitura, da correggere %s' % (
                                  chi, 'in Configura → Email e WhatsApp' if chi == mittente
                                  else 'nella scheda del paziente'), permanente=True)
        raise ErroreInvio('il server non accetta l\'accesso con nome utente e password così (%s): controllare porta e '
                          'sicurezza (molti server lo accettano solo con SSL o STARTTLS); per un server della rete '
                          'interna che non chiede la password, spuntare «Il server non chiede la password»' % e,
                          permanente=True)
    except smtplib.SMTPRecipientsRefused as e:
        risposte = [x for x in e.recipients.values() if isinstance(x, tuple) and len(x) == 2]
        risposta = _risposta(SimpleNamespace(smtp_code=risposte[0][0], smtp_error=risposte[0][1])) if risposte else ''
        testo = 'indirizzo del destinatario rifiutato: %s' % ', '.join(e.recipients)
        if risposta:
            testo += ' (risposta del server: %s)' % risposta
        if 'relay' in risposta.lower():
            testo += ('. Il server non lascia mandare a indirizzi di fuori: di solito si entra con nome utente e '
                      'password della casella%s' % (' (togliere la spunta «Il server non chiede la password»)'
                                                    if senza_password else ''))
        raise ErroreInvio(testo, permanente=True)
    except smtplib.SMTPSenderRefused as e:
        if e.smtp_code == 530 or (senza_password and e.smtp_code in (550, 553, 554) and
                                  'auth' in _risposta(e).lower()):
            raise ErroreInvio('il server vuole nome utente e password prima di mandare: scrivere la password della '
                              'casella%s (risposta del server: %s)' % (
                                  ' e togliere la spunta «Il server non chiede la password»' if senza_password else '',
                                  _risposta(e)), permanente=True)
        raise ErroreInvio('mittente rifiutato dal server: %s. Di solito l\'indirizzo del mittente deve essere quello '
                          'della casella con cui si entra nel server' % _risposta(e), permanente=True)
    except smtplib.SMTPDataError as e:
        # 4xx: il server e' occupato o ha un limite momentaneo, si riprova
        raise ErroreInvio('messaggio rifiutato dal server: %s' % _risposta(e, 160), permanente=e.smtp_code >= 500)
    except ssl.SSLCertVerificationError as e:
        # 62 e 64: il certificato e' di un altro nome (o indirizzo), va corretto il server;
        # gli altri (scaduto, autofirmato...) possono sistemarsi dal fornitore: si riprova
        sbagliato = getattr(e, 'verify_code', None) in (62, 64)
        raise ErroreInvio('connessione protetta non riuscita: il certificato del server «%s» non va bene (%s)%s' % (
            nome_server, getattr(e, 'verify_message', '') or e,
            ': scrivere il nome del server esatto che indica il fornitore della casella (negli hosting a volte è il '
            'nome del server, non mail. seguito dal dominio)' if sbagliato else ''), permanente=sbagliato)
    except ssl.SSLError as e:
        if sicurezza == 'ssl' and getattr(e, 'reason', '') in SENZA_SSL:
            raise ErroreInvio('sulla porta %d il server non usa SSL: con la porta 587 scegliere STARTTLS (oppure la '
                              'porta 465 con SSL)' % porta, permanente=True)
        raise ErroreInvio('connessione protetta non riuscita: %s' % e, permanente=False)
    except socket.gaierror:
        raise ErroreInvio('server email non raggiungibile: «%s» non si trova (controllare il nome del server e la '
                          'connessione a internet)' % nome_server, permanente=False)
    except ConnectionRefusedError:
        raise ErroreInvio('server email non raggiungibile: «%s» rifiuta il collegamento sulla porta %d (controllare la '
                          'porta: di solito 465 con SSL o 587 con STARTTLS)' % (nome_server, porta), permanente=False)
    except (TimeoutError, socket.timeout) as e:
        consiglio = ('con la porta 465 la sicurezza è SSL' if porta == 465 and sicurezza != 'ssl' else
                     'controllare server e porta, e la connessione a internet')
        raise ErroreInvio('server email non raggiungibile: «%s» non risponde (%s)' % (nome_server, consiglio),
                          permanente=False)
    except (smtplib.SMTPException, OSError) as e:
        consiglio = ' (con la porta 465 la sicurezza è SSL)' if porta == 465 and sicurezza != 'ssl' else ''
        raise ErroreInvio('server email non raggiungibile: %s%s' % (e or e.__class__.__name__, consiglio),
                          permanente=False)


def manda_whatsapp(cfg, numero, parametri):
    """Il modello approvato, con le sue variabili, al numero (formato
    internazionale senza +). Restituisce l'id del messaggio di Meta: vuol
    dire che Meta l'ha accettato, non ancora che e' stato letto."""
    token = svela(cfg['wa_token'])
    indirizzo = '%s/%s/%s/messages' % (cfg['wa_indirizzo'].rstrip('/'), cfg['wa_versione'].strip('/'),
                                      cfg['wa_numero_id'].strip())
    corpo = {'messaging_product': 'whatsapp', 'recipient_type': 'individual', 'to': numero, 'type': 'template',
             'template': {'name': cfg['wa_modello'], 'language': {'code': cfg['wa_lingua'] or 'it'},
                          'components': [{'type': 'body',
                                          'parameters': [{'type': 'text', 'text': p} for p in parametri]}]}}
    richiesta = urllib.request.Request(indirizzo, data=json.dumps(corpo).encode('utf-8'), method='POST', headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'GestionaleAgende'})
    try:
        with urllib.request.urlopen(richiesta, timeout=30) as r:
            risposta = json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        try:
            errore = json.loads(e.read().decode('utf-8') or '{}').get('error', {})
        except (ValueError, AttributeError):
            errore = {}
        testo = errore.get('message') or e.reason or 'errore %d' % e.code
        codice = errore.get('code')
        # 429 e 5xx: Meta e' occupata, si riprova; il resto e' da correggere
        raise ErroreInvio('WhatsApp ha rifiutato il messaggio: %s%s%s' % (
            testo, ' (codice %s)' % codice if codice else '', spiega_meta(codice)),
            permanente=not (e.code == 429 or e.code >= 500))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErroreInvio('WhatsApp non raggiungibile: %s' % e, permanente=False)
    try:
        return str(risposta['messages'][0]['id'])
    except (KeyError, IndexError, TypeError):
        raise ErroreInvio('risposta di WhatsApp non prevista: %s' % str(risposta)[:150], permanente=False)


def registra_numero(cfg, pin):
    """Attiva il numero sulla piattaforma di Meta per gli invii dal programma
    (una volta, dopo averlo aggiunto e verificato in Meta). Il PIN e' quello
    della verifica in due passaggi: se il numero non l'ha ancora, lo imposta.
    Il PIN non si salva da nessuna parte. ErroreInvio se Meta dice di no."""
    token = svela(cfg['wa_token'])
    indirizzo = '%s/%s/%s/register' % (cfg['wa_indirizzo'].rstrip('/'), cfg['wa_versione'].strip('/'),
                                      cfg['wa_numero_id'].strip())
    corpo = {'messaging_product': 'whatsapp', 'pin': pin}
    richiesta = urllib.request.Request(indirizzo, data=json.dumps(corpo).encode('utf-8'), method='POST', headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'GestionaleAgende'})
    try:
        with urllib.request.urlopen(richiesta, timeout=30) as r:
            risposta = json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        try:
            errore = json.loads(e.read().decode('utf-8') or '{}').get('error', {})
        except (ValueError, AttributeError):
            errore = {}
        codice = errore.get('code')
        testo = errore.get('error_user_msg') or errore.get('message') or e.reason or 'errore %d' % e.code
        raise ErroreInvio('Meta non ha registrato il numero: %s%s%s' % (
            testo, ' (codice %s)' % codice if codice else '', spiega_meta(codice)))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErroreInvio('Meta non raggiungibile: %s. Controllare la connessione a internet e riprovare.' % e)
    if not (isinstance(risposta, dict) and risposta.get('success') is True):
        raise ErroreInvio('risposta di Meta non prevista: %s' % str(risposta)[:150])


PASSATO = 'appuntamento già passato'
NON_VALE_PIU = 'non vale più per questo appuntamento (cambiati medico, prestazione o email automatiche)'
CAMBIATO_PAZIENTE = 'cambiato il paziente dell\'appuntamento'
CAMBIATO_RECAPITO = 'cambiato il recapito del paziente'


def _controlla(x, a, adesso, s=None):
    """Il messaggio ha ancora senso? Il motivo per cui no, None se si'.
    Con la sessione controlla anche che un'email automatica valga ancora per
    l'appuntamento: se nel frattempo e' cambiato il medico (o la prestazione,
    o le regole) non deve partire l'informativa sbagliata."""
    if x.motivo not in ('PREPARAZIONE', 'PROMEMORIA'):
        return None
    if a is None:
        return 'appuntamento eliminato'
    if a.stato not in STATI_ATTIVI:
        return 'appuntamento %s' % ETICHETTA_STATO.get(a.stato, a.stato).lower()
    # 1.11: il testo si scrive dall'appuntamento com'e' adesso, ma il destinatario e'
    # quello di quando il messaggio e' entrato in coda. Cambiato il paziente (o
    # corretto il suo indirizzo) mentre il messaggio aspettava di riprovare, sarebbe
    # arrivato all'indirizzo vecchio con il nome e la prestazione del paziente nuovo.
    # Si annulla: al suo posto ne entra uno per il paziente e il recapito di adesso.
    if x.paziente_id is not None and a.paziente_id != x.paziente_id:
        return CAMBIATO_PAZIENTE
    if a.paziente is not None:
        if x.canale == 'EMAIL':
            adesso_a = (a.paziente.email or '').strip().lower()
        elif x.canale == 'WHATSAPP':
            adesso_a = (pazienti.cellulare_whatsapp(a.paziente) or '').strip().lower()
        else:
            adesso_a = None
        if adesso_a is not None and adesso_a != (x.destinatario or '').strip().lower():
            return CAMBIATO_RECAPITO
    if a.inizio < adesso and (x.motivo == 'PROMEMORIA' or not x.a_mano):
        return PASSATO
    if x.motivo == 'PROMEMORIA' and not x.a_mano and x.per_inizio is not None \
            and a.inizio.date() != x.per_inizio.date():
        return 'appuntamento spostato a un altro giorno'
    if s is not None and x.motivo == 'PREPARAZIONE' and not x.a_mano \
            and x.regola_id not in {r.id for r in regole_per(s, a)}:
        return NON_VALE_PIU
    return None


def ricontrolla(s, paziente_id, quando, adesso=None, anche=None):
    """Un'email automatica non e' partita perche' l'appuntamento e' cambiato
    (eliminato, disdetto, altro medico): le email che adesso valgono per gli
    appuntamenti attivi del paziente in quel giorno, che magari contavano su
    quella (gastroscopia e colonscopia lo stesso giorno: una email sola), e
    per 'anche', l'appuntamento cambiato. Col lucchetto preso.
    Restituisce i messaggi messi in coda."""
    if not paziente_id or quando is None:
        return []
    adesso = adesso or datetime.now()
    inizio = datetime.combine(quando.date(), time(0, 0))
    apps = s.scalars(select(Appuntamento).where(
        Appuntamento.paziente_id == paziente_id, Appuntamento.inizio >= inizio,
        Appuntamento.inizio < inizio + timedelta(days=1), Appuntamento.stato.in_(STATI_ATTIVI))
        .order_by(Appuntamento.inizio, Appuntamento.id)).all()
    if anche is not None and anche not in apps:
        apps.append(anche)
    fatti = []
    for b in apps:
        fatti += dopo_salvataggio(s, b, [], [], adesso)
    return fatti


def _spedisci(s, x, cfg):
    """Manda il messaggio. Restituisce (oggetto, testo) di cio' che e'
    partito, per il registro. Non modifica niente nella sessione."""
    a = x.appuntamento
    if x.canale == 'EMAIL':
        if not email_pronta(cfg):
            raise ErroreInvio('invio delle email non configurato o spento', permanente=True)
        oggetto, testo, allegati = testi_email(s, x, a)
        manda_email(cfg, componi_email(s, x, cfg, oggetto, testo, allegati, struttura_di(s, a)))
        if allegati:
            testo += '\n\n[allegati: %s]' % ', '.join(nome for nome, _, _ in allegati)
        return oggetto, testo
    if x.canale == 'WHATSAPP':
        if not whatsapp_pronto(cfg):
            raise ErroreInvio('WhatsApp non configurato', permanente=True)
        if x.motivo == 'PROVA':
            parametri = [p.strip() or '-' for p in (x.testo or '').split('|')]
        else:
            parametri = parametri_whatsapp(cfg, a)
        rif = manda_whatsapp(cfg, x.destinatario, parametri)
        return 'Modello %s · id %s' % (cfg['wa_modello'], rif), ' | '.join(parametri)
    raise ErroreInvio('canale sconosciuto: %s' % x.canale, permanente=True)


def _esegui(s, i, adesso):
    """Un messaggio gia' "in partenza": prova a mandarlo e scrive l'esito.
    Restituisce (id, stato, errore)."""
    x = s.get(Invio, i)
    if x is None or x.stato != 'IN_CORSO':
        return (i, x.stato if x is not None else 'SPARITO', '')
    stato, errore, permanente, spedito = 'ERRORE', '', True, None
    try:
        motivo = _controlla(x, x.appuntamento, adesso, s)
        if motivo:
            stato, errore = 'ANNULLATO', motivo
        else:
            spedito = _spedisci(s, x, impostazioni(s))
            stato = 'INVIATO'
    except ErroreInvio as e:
        errore, permanente = str(e), e.permanente
    except Exception as e:          # un difetto del programma non deve fermare la coda
        logging.exception('invio %d', i)
        errore = 'errore inatteso: %s' % e
    rimessi = []
    with _lucchetto:
        x = s.get(Invio, i)
        x.errore = errore[:300]
        if stato == 'INVIATO':
            x.stato, x.inviato_il, x.tentativi = 'INVIATO', datetime.now(), (x.tentativi or 0) + 1
            x.oggetto, x.testo = (spedito[0] or '')[:200], spedito[1] or ''
        elif stato == 'ERRORE':
            x.tentativi = (x.tentativi or 0) + 1
            if not permanente and not x.a_mano and x.tentativi <= len(ATTESE):
                x.stato, x.prossimo = 'DA_INVIARE', datetime.now() + timedelta(minutes=ATTESE[x.tentativi - 1])
            else:
                x.stato = 'ERRORE'
        else:
            x.stato = stato
        s.commit()
        esito = (x.id, x.stato, x.errore)
        # un'email automatica annullata perche' l'appuntamento e' cambiato: al
        # suo posto quelle che valgono adesso (a parte, perche' un difetto qui
        # non deve impedire di segnare l'annullamento)
        if stato == 'ANNULLATO' and x.motivo == 'PREPARAZIONE' and not x.a_mano and errore != PASSATO:
            try:
                rimessi = ricontrolla(s, x.paziente_id, x.per_inizio, adesso, x.appuntamento)
                s.commit()
            except Exception:
                s.rollback()
                logging.exception('invio %d: email da rimettere in coda', i)
                rimessi = []
        # 1.11: un promemoria annullato perche' e' cambiato il paziente o il suo recapito:
        # quello giusto al suo posto (il giro del giorno e' gia' passato e non lo rifarebbe)
        if stato == 'ANNULLATO' and x.motivo == 'PROMEMORIA' and not x.a_mano and \
                errore in (CAMBIATO_PAZIENTE, CAMBIATO_RECAPITO) and x.appuntamento is not None:
            try:
                nuovo = accoda_promemoria(s, x.appuntamento, impostazioni(s))
                s.commit()
                rimessi = [nuovo] if nuovo is not None else []
            except Exception:
                s.rollback()
                logging.exception('invio %d: email da rimettere in coda', i)
                rimessi = []
    if stato == 'ERRORE':
        logging.warning('invio %d (%s a %s) non partito: %s', i, x.canale, x.destinatario, errore)
    if rimessi:
        sveglia()
    return esito


def elabora(fabbrica, adesso=None, limite=25):
    """Il giro della coda: manda i messaggi arrivati alla loro ora.
    Restituisce [(id, stato, errore)]."""
    adesso = adesso or datetime.now()
    s = fabbrica()
    try:
        with _lucchetto:
            ids = list(s.scalars(select(Invio.id).where(
                Invio.stato == 'DA_INVIARE', (Invio.prossimo == None) | (Invio.prossimo <= adesso))
                .order_by(Invio.id).limit(limite)))
            for i in ids:
                x = s.get(Invio, i)
                x.stato, x.prossimo = 'IN_CORSO', datetime.now()     # 'prossimo' ricorda da quando
            s.commit()
        return [_esegui(s, i, adesso) for i in ids]
    finally:
        s.close()


def manda_subito(fabbrica, xid):
    """Per i pulsanti: il messaggio, nato "in partenza", parte adesso e si
    sa subito com'e' andata. Restituisce (id, stato, errore)."""
    s = fabbrica()
    try:
        return _esegui(s, xid, datetime.now())
    finally:
        s.close()


def riprendi_interrotti(fabbrica, prima_di=None):
    """I messaggi rimasti "in partenza" (programma chiuso a meta' invio)
    tornano in coda: meglio un doppione che una preparazione mai arrivata.
    All'avvio tutti; poi solo quelli fermi da piu' di MINUTI_BLOCCATO."""
    s = fabbrica()
    try:
        with _lucchetto:
            q = select(Invio).where(Invio.stato == 'IN_CORSO')
            if prima_di is not None:
                q = q.where((Invio.prossimo == None) | (Invio.prossimo < prima_di))
            n = 0
            for x in s.scalars(q).all():
                x.stato, x.prossimo = 'DA_INVIARE', datetime.now()
                n += 1
            s.commit()
        if n:
            logging.info('invii rimasti a metà rimessi in coda: %d', n)
        return n
    finally:
        s.close()


def sveglia():
    _sveglia.set()


def un_giro(fabbrica, adesso=None):
    """Quello che il thread fa a ogni risveglio: promemoria del giorno (una
    volta), messaggi bloccati, coda."""
    adesso = adesso or datetime.now()
    # tre lavori indipendenti: un difetto in uno non ferma gli altri
    try:
        s = fabbrica()
        try:
            with _lucchetto:
                giro_promemoria(s, adesso)
                s.commit()
        finally:
            s.close()
    except Exception:
        _registra_errore('giro dei promemoria')
    try:
        riprendi_interrotti(fabbrica, adesso - timedelta(minutes=MINUTI_BLOCCATO))
    except Exception:
        _registra_errore('invii rimasti a metà')
    esiti = []
    try:
        for _ in range(40):                  # al massimo mille messaggi per giro
            fatti = elabora(fabbrica)
            esiti += fatti
            if len(fatti) < 25:
                break
    except Exception:
        _registra_errore('coda degli invii')
    return esiti


def avvia(fabbrica, intervallo=60):
    """Il thread della coda e dei promemoria: si sveglia ogni minuto, o subito
    quando una prenotazione mette qualcosa in coda."""
    global _thread, _fabbrica
    _fabbrica = fabbrica
    if _thread is not None and _thread.is_alive():
        return _thread

    def giro():
        try:
            riprendi_interrotti(fabbrica)
        except Exception:
            logging.exception('coda degli invii: ripresa all\'avvio')
        while True:
            try:
                un_giro(fabbrica)
            except Exception:
                _registra_errore('thread degli invii')
            _sveglia.wait(intervallo)
            _sveglia.clear()
    _thread = threading.Thread(target=giro, name='invii', daemon=True)
    _thread.start()
    return _thread


# ============================================================ per le pagine
def notifiche(s, adesso=None):
    """Per le notifiche a scomparsa: i messaggi non partiti degli ultimi giorni."""
    adesso = adesso or datetime.now()
    rotti = s.scalars(select(Invio).where(Invio.stato == 'ERRORE', Invio.motivo != 'PROVA',
                                          Invio.creato_il >= adesso - timedelta(days=7))
                      .order_by(Invio.id.desc())).all()
    if not rotti:
        return []
    n = len(rotti)
    return [{'chiave': 'invii-errore-%d-%d' % (rotti[0].id, n), 'titolo': 'Messaggi non partiti',
             'testo': '%d messagg%s ai pazienti non partit%s. L\'ultimo: %s' % (
                 n, 'io' if n == 1 else 'i', 'o' if n == 1 else 'i', (rotti[0].errore or '')[:120]),
             'link': url_for('invii.pagina') + '#registro', 'azioni': [], 'livello': 'errore'}]


def invii_di(s, a):
    return s.scalars(select(Invio).where(Invio.appuntamento_id == a.id).order_by(Invio.id.desc())).all()


def stato_promemoria(s, apps):
    """{id appuntamento: ultimo promemoria} per la pagina Conferme."""
    if not apps:
        return {}
    uscita = {}
    per_id = {a.id: a for a in apps}
    for x in s.scalars(select(Invio).where(Invio.motivo == 'PROMEMORIA',
                                           Invio.appuntamento_id.in_(list(per_id))).order_by(Invio.id)):
        # 1.11: un promemoria del giorno di prima (appuntamento spostato) non vale per quello
        # di adesso: la pagina diceva «inviato» e toglieva il pulsante per mandarlo
        a = per_id.get(x.appuntamento_id)
        if a is not None and x.per_inizio is not None and x.per_inizio.date() != a.inizio.date():
            continue
        uscita[x.appuntamento_id] = x
    return uscita


def perche_non_parte(r, a, valide):
    """Perche' una regola attiva non parte da sola per l'appuntamento: per
    l'elenco delle email da mandare a comando. '' se parte."""
    if r.id in valide:
        return ''
    if a.operatore_id is None:
        return 'l\'appuntamento non ha un medico'
    if r.operatore_id and r.operatore_id != a.operatore_id:
        return 'è di %s' % (r.operatore.etichetta if r.operatore else 'un altro medico')
    if r.id_prestazioni and a.prestazione_id not in r.id_prestazioni:
        return 'non è per questa prestazione'
    if not r.operatore_id:
        return 'per questo medico c\'è la sua'
    return 'non parte da sola per questo appuntamento'


def pannello(s, a):
    """Il riquadro "Email e WhatsApp" della pagina dell'appuntamento."""
    cfg = impostazioni(s)
    valide = {r.id for r in regole_per(s, a)}
    regole = sorted(regole_attive(s), key=lambda r: (r.id not in valide, (r.nome or '').lower()))
    perche = {r.id: perche_non_parte(r, a, valide) for r in regole}
    canale, destinatario = canale_promemoria(cfg, a.paziente)
    if a.paziente is not None and a.paziente.promemoria is False:
        motivo = 'il paziente non vuole promemoria (casella nella sua scheda)'
    elif not email_pronta(cfg) and not whatsapp_pronto(cfg):
        motivo = 'né email né WhatsApp automatico sono configurati (Configura → Email e WhatsApp)'
    else:
        motivo = ('serve un cellulare per WhatsApp o un indirizzo email del paziente, con quel canale acceso '
                  'in Configura → Email e WhatsApp')
    return {'invii': invii_di(s, a), 'regole': regole, 'valide': valide, 'perche': perche,
            'email_pronta': email_pronta(cfg),
            'whatsapp_pronto': whatsapp_pronto(cfg), 'canale': canale, 'destinatario': destinatario,
            'motivo_promemoria': motivo, 'attivo': a.stato in STATI_ATTIVI, 'passato': a.inizio < datetime.now(),
            'email_paziente': (a.paziente.email or '').strip() if a.paziente else '',
            'canali': CANALI, 'motivi': MOTIVI, 'stati': STATI}


def _cfg_modulo(f, cfg):
    """Le impostazioni dal modulo: (nuove impostazioni, errori, avvisi).
    Password e token restano quelli salvati se il campo e' vuoto. Server,
    porta e sicurezza lasciati vuoti si prendono dal tipo di casella."""
    errori, avvisi, nuovi = [], [], {}
    if f.get('sezione') == 'email':
        utente = (f.get('email_utente') or '').strip()
        if utente and (len(utente) > 120 or not pazienti.email_valida(utente)):
            errori.append('Indirizzo email non valido.')
        server = (f.get('email_server') or '').strip().rstrip('.')
        tipo = f.get('email_tipo') or ''
        if tipo and tipo not in PER_CODICE:
            errori.append('Tipo di casella: scelta non valida.')
            tipo = ''
        if not tipo:                     # un modulo senza il tipo (come quello della 1.9): dal server
            tipo = tipo_casella({'email_server': server}, utente)
        if tipo == 'dominio' and _dominio(utente) in ('gmail.com', 'googlemail.com'):
            tipo = 'gmail'               # una casella @gmail.com non e' quella del sito
        preset = PER_CODICE[tipo]
        if not server:
            server = server_proposto(tipo, utente)
        if server and not re.fullmatch(r'[A-Za-z0-9.\-]{1,120}', server):
            errori.append('Server non valido: solo il nome, per esempio mail.dominio.it, senza spazi né «smtp://».')
        elif not server and utente:
            errori.append('Manca il server della posta in uscita (SMTP): lo indica il fornitore della casella.')
        porta = (f.get('email_porta') or '').strip() or preset['porta'] or PREDEFINITI['email_porta']
        if not porta.isdigit() or not 0 < int(porta) < 65536:
            errori.append('Porta non valida.')
        sicurezza = f.get('email_sicurezza') or preset['sicurezza'] or PREDEFINITI['email_sicurezza']
        if sicurezza not in dict(SICUREZZE):
            errori.append('Sicurezza: scelta non valida.')
        accesso = (f.get('email_accesso') or '').strip()
        if accesso and (len(accesso) > 120 or not re.fullmatch(r'\S+', accesso)):
            errori.append('Nome utente non valido: senza spazi, al massimo 120 caratteri.')
        if accesso.lower() == utente.lower():
            accesso = ''                 # uguale all'indirizzo: e' gia' quello che si usa
        senza_password = '1' if f.get('email_senza_password') in ('1', 'on') else '0'
        mittente = ' '.join((f.get('email_mittente') or '').split())[:80]
        nuovi.update(email_tipo=tipo, email_utente=utente, email_server=server, email_porta=porta,
                     email_sicurezza=sicurezza, email_accesso=accesso, email_senza_password=senza_password,
                     email_mittente=mittente, email_attiva='1' if f.get('email_attiva') in ('1', 'on') else '0')
        gmail = tipo == 'gmail' or _di_google(server)
        grezza = f.get('email_password') or ''
        # Google mostra la password per le app a gruppi di quattro: gli spazi non contano.
        # Le altre password si tengono come sono, tolti solo gli spazi copiati prima e dopo.
        password = re.sub(r'\s', '', grezza) if gmail else grezza.strip()
        if password:
            nuovi['email_password'] = proteggi(password[:100])
            if gmail and not re.fullmatch(r'[A-Za-z]{16}', password):
                avvisi.append('La password per le app di Gmail sono 16 lettere: questa non lo sembra. Se la prova non '
                              'parte, crearne una nuova in myaccount.google.com/apppasswords.')
        elif f.get('togli_password') in ('1', 'on'):
            nuovi['email_password'] = ''
        if porta.isdigit() and sicurezza in dict(SICUREZZE):
            if int(porta) == 465 and sicurezza != 'ssl':
                avvisi.append('Con la porta 465 la sicurezza di solito è SSL: se la prova non parte, scegliere SSL.')
            elif int(porta) == 587 and sicurezza == 'ssl':
                avvisi.append('Con la porta 587 la sicurezza di solito è STARTTLS: se la prova non parte, scegliere '
                              'STARTTLS.')
            elif sicurezza == 'nessuna' and senza_password != '1':
                avvisi.append('Senza sicurezza la password viaggia in chiaro: se il server offre SSL o STARTTLS, '
                              'meglio usarli.')
    elif f.get('sezione') == 'promemoria':
        ora = (f.get('promemoria_ora') or '10:00').strip()
        if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', ora):
            errori.append('Ora del promemoria non valida.')
        nuovi.update(promemoria_attivo='1' if f.get('promemoria_attivo') in ('1', 'on') else '0',
                     promemoria_ora=ora,
                     promemoria_whatsapp='1' if f.get('promemoria_whatsapp') in ('1', 'on') else '0',
                     promemoria_email='1' if f.get('promemoria_email') in ('1', 'on') else '0')
    elif f.get('sezione') == 'whatsapp':
        numero_id = (f.get('wa_numero_id') or '').strip()
        if numero_id and not (numero_id.isdigit() and len(numero_id) <= 30):
            errori.append('ID del numero: solo cifre (lo mostra Meta in "Configurazione API").')
        modello = (f.get('wa_modello') or '').strip()
        if modello and not re.fullmatch(r'[a-z0-9_]{1,512}', modello):
            errori.append('Nome del modello: lettere minuscole, cifre e trattini bassi, come in Meta.')
        lingua = (f.get('wa_lingua') or 'it').strip()
        if not re.fullmatch(r'[a-z]{2,3}(_[A-Z]{2})?', lingua):
            errori.append('Lingua non valida (per esempio it).')
        parametri = [x.strip() for x in (f.get('wa_parametri') or '').split(',') if x.strip()]
        sconosciuti = [x for x in parametri if x not in PARAMETRI_WA]
        if sconosciuti:
            errori.append('Variabili sconosciute: %s.' % ', '.join(sconosciuti))
        if len(parametri) > 10:
            errori.append('Al massimo 10 variabili.')
        versione = (f.get('wa_versione') or PREDEFINITI['wa_versione']).strip()
        if not re.fullmatch(r'v\d{1,2}\.\d', versione):
            errori.append('Versione dell\'API non valida (per esempio v25.0).')
        nuovi.update(wa_numero_id=numero_id, wa_modello=modello or PREDEFINITI['wa_modello'], wa_lingua=lingua,
                     wa_parametri=','.join(parametri) or PREDEFINITI['wa_parametri'], wa_versione=versione)
        if numero_id != cfg['wa_numero_id']:
            nuovi['wa_registrato'] = ''          # un altro numero: va registrato anche lui
        token = re.sub(r'\s', '', f.get('wa_token') or '')
        if token:
            if len(token) > 1000 or not re.fullmatch(r'[A-Za-z0-9._\-]+', token):
                errori.append('Token non valido: va copiato tutto, senza altri caratteri.')
            else:
                nuovi['wa_token'] = proteggi(token)
        elif f.get('togli_token') in ('1', 'on'):
            nuovi['wa_token'] = ''
    else:
        errori.append('Sezione sconosciuta.')
    return nuovi, errori, avvisi


def regola_pronta_possibile(s):
    """La regola gia' pronta si propone dove c'e' un medico Galasso e non
    c'e' ancora una regola con quel nome."""
    medico = next((o for o in s.scalars(select(Operatore).where(Operatore.attivo == True).order_by(Operatore.id))
                   if pazienti.semplifica(o.cognome) == 'galasso'), None)
    if medico is None or s.scalars(select(RegolaEmail.id).where(RegolaEmail.nome == PRONTA_NOME)).first():
        return None
    return medico


def crea_regola_pronta(s, medico):
    """Medico Galasso, le sue prestazioni endoscopiche, oggetto e testo della
    mail dell'accettazione, le due informative. Senza prestazioni adatte la
    regola nasce spenta: per il solo medico manderebbe la preparazione anche
    per le visite."""
    adatte = [p.id for p in s.scalars(select(Prestazione).order_by(Prestazione.nome))
              if any(k in pazienti.semplifica(p.nome) for k in PRONTA_PRESTAZIONI)]
    r = RegolaEmail(nome=PRONTA_NOME, attiva=bool(adatte), operatore_id=medico.id,
                    prestazioni=','.join(map(str, adatte)), oggetto=PRONTA_OGGETTO, testo=PRONTA_TESTO)
    s.add(r)
    cartella = os.path.join(cartella_risorse(), 'modelli_email')
    for nome in PRONTA_ALLEGATI:
        percorso = os.path.join(cartella, nome)
        if os.path.exists(percorso):
            with open(percorso, 'rb') as f:
                dati = f.read()
            r.allegati.append(AllegatoRegola(nome=nome, tipo='application/pdf', dimensione=len(dati), dati=dati))
    s.flush()
    return r


def duplica_regola(s, r, medico):
    """Una copia della regola per un altro medico (None: per tutti i medici),
    spenta: stesso oggetto, testo e prestazioni, una copia degli allegati. Si
    cambiano testo e informative con quelle del medico, poi la si accende."""
    nome = r.nome or 'Email'
    vecchio = ' · %s' % r.operatore.etichetta if r.operatore else ' · tutti i medici'
    if nome.endswith(vecchio):                 # la copia di una copia: niente nomi in fila
        nome = nome[:-len(vecchio)]
    dopo = ' · %s' % (medico.etichetta if medico else 'tutti i medici')
    copia = RegolaEmail(nome=(nome[:max(10, 80 - len(dopo))] + dopo)[:80], attiva=False,
                        operatore_id=medico.id if medico else None,
                        prestazioni=r.prestazioni or '', oggetto=r.oggetto, testo=r.testo)
    s.add(copia)
    for g in r.allegati:
        copia.allegati.append(AllegatoRegola(nome=g.nome, tipo=g.tipo, dimensione=g.dimensione, dati=g.dati))
    s.flush()
    return copia


def _manda_e_dici(xid, destinatario, cosa='Mandato'):
    """Manda subito il messaggio xid e mette l'esito fra i messaggi della pagina."""
    _, stato, errore = manda_subito(fabbrica_sessioni, xid)
    if stato == 'INVIATO':
        flash('%s a %s.' % (cosa, destinatario), 'ok')
    elif stato == 'ANNULLATO':
        flash('Non mandato: %s.' % errore, 'errore')
    else:
        flash('Non partito: %s' % (errore or STATI.get(stato, stato)), 'errore')
    return stato


@bp.route('', methods=['GET', 'POST'])
def pagina():
    s = ses()
    cfg = impostazioni(s)
    if request.method == 'POST':
        azione = request.form.get('azione')
        if azione == 'salva':
            nuovi, errori, avvisi = _cfg_modulo(request.form, cfg)
            for e in errori:
                flash(e, 'errore')
            if not errori:
                with _lucchetto:
                    for k, v in nuovi.items():
                        scrivi_impostazione(s, k, v)
                    s.commit()
                flash('Impostazioni salvate.', 'ok')
                for a in avvisi:
                    flash(a, 'avviso')
                sveglia()
            return redirect(url_for('invii.pagina') + '#' + re.sub(r'\W', '', request.form.get('sezione') or ''))
        if azione == 'prova_email':
            dest = (request.form.get('a') or '').strip()
            if not pazienti.email_valida(dest) or len(dest) > 120:
                flash('Scrivere un indirizzo email valido per la prova.', 'errore')
                return redirect(url_for('invii.pagina') + '#email')
            if not email_pronta(cfg):
                flash('Prima salvare indirizzo, password e server della casella, con l\'invio acceso.', 'errore')
                return redirect(url_for('invii.pagina') + '#email')
            st = struttura_di(s)
            with _lucchetto:
                xid = accoda(s, 'EMAIL', 'PROVA', dest, a_mano=True, subito=True, oggetto='Prova del gestionale',
                             testo='Questa è una prova: se arriva, le email ai pazienti partono.\n\n%s' % (
                                 st.nome if st else '')).id
                s.commit()
            _manda_e_dici(xid, dest, 'Prova mandata: controllare che sia arrivata')
            return redirect(url_for('invii.pagina') + '#email')
        if azione == 'prova_whatsapp':
            numero = pazienti.numero_internazionale(request.form.get('a') or '')
            if not numero:
                flash('Scrivere un numero di cellulare valido per la prova.', 'errore')
                return redirect(url_for('invii.pagina') + '#whatsapp')
            if not whatsapp_pronto(cfg):
                flash('Prima salvare token, ID del numero e nome del modello.', 'errore')
                return redirect(url_for('invii.pagina') + '#whatsapp')
            st = struttura_di(s)
            esempio = {'paziente': 'Paziente di prova', 'giorno': 'lunedì 1 marzo', 'data': '01/03/2027',
                       'ora': '09:00', 'struttura': st.nome if st else 'Struttura',
                       'indirizzo': (st.indirizzo or '-') if st else '-', 'prestazione': 'Visita',
                       'medico': 'Dott. Medico', 'stanza': 'Ambulatorio', 'recapito': 'ci contatti',
                       'telefono_struttura': (st.telefono or '-') if st else '-'}
            nomi = [x.strip() for x in cfg['wa_parametri'].split(',') if x.strip()]
            with _lucchetto:
                xid = accoda(s, 'WHATSAPP', 'PROVA', numero, a_mano=True, subito=True,
                             testo='|'.join(esempio.get(n, n) for n in nomi)).id
                s.commit()
            _manda_e_dici(xid, '+' + numero, 'Prova mandata: controllare che sia arrivata')
            return redirect(url_for('invii.pagina') + '#whatsapp')
        if azione == 'registra_whatsapp':
            pin = re.sub(r'\s', '', request.form.get('pin') or '')
            if not re.fullmatch(r'\d{6}', pin):
                flash('Il PIN sono 6 cifre.', 'errore')
                return redirect(url_for('invii.pagina') + '#registra-numero')
            if not (cfg['wa_token'] and cfg['wa_numero_id']):
                flash('Prima salvare il token e l\'ID del numero di telefono.', 'errore')
                return redirect(url_for('invii.pagina') + '#whatsapp')
            try:
                registra_numero(cfg, pin)        # senza lucchetto: e' una chiamata a internet
            except ErroreInvio as e:
                logging.warning('registrazione del numero WhatsApp non riuscita: %s', e)
                flash(str(e), 'errore')
                return redirect(url_for('invii.pagina') + '#registra-numero')
            with _lucchetto:
                scrivi_impostazione(s, 'wa_registrato', datetime.now().strftime('%Y-%m-%d %H:%M'))
                s.commit()
            flash('Numero registrato: ora il programma può mandare i WhatsApp. Conservare il PIN in un posto sicuro: '
                  'serve se un giorno il numero va registrato di nuovo.', 'ok')
            return redirect(url_for('invii.pagina') + '#whatsapp')
        if azione in ('riprova', 'annulla'):
            x = s.get(Invio, intero(request.form.get('invio')))
            if x is None:
                abort(404)
            with _lucchetto:
                if azione == 'riprova' and x.stato == 'ERRORE':
                    x.stato, x.prossimo, x.errore, x.tentativi = 'DA_INVIARE', datetime.now(), '', 0
                    flash('Il messaggio è di nuovo in coda: parte fra pochi secondi.', 'ok')
                elif azione == 'annulla' and x.stato == 'DA_INVIARE':
                    x.stato, x.errore = 'ANNULLATO', 'annullato a mano'
                    flash('Messaggio annullato.', 'ok')
                s.commit()
            sveglia()
            return redirect(destinazione_sicura(request.form.get('torna'), url_for('invii.pagina') + '#registro'))
        if azione == 'regola_pronta':
            medico = regola_pronta_possibile(s)
            if medico is None:
                flash('La regola già pronta c\'è già, o manca il medico Galasso fra i medici attivi.', 'errore')
                return redirect(url_for('invii.pagina') + '#regole')
            with _lucchetto:
                r = crea_regola_pronta(s, medico)
                s.commit()
            if r.attiva:
                flash('Regola «%s» creata e attiva: %d prestazioni, %d allegati. Controllarla qui sotto.' % (
                    r.nome, len(r.id_prestazioni), len(r.allegati)), 'ok')
            else:
                flash('Regola «%s» creata ma spenta: nessuna prestazione con EGDS, gastroscopia o colonscopia nel '
                      'nome. Scegliere le prestazioni e spuntare "Attiva".' % r.nome, 'avviso')
            return redirect(url_for('invii.regola', rid=r.id))
        abort(400)
    regole = s.scalars(select(RegolaEmail).order_by(RegolaEmail.id)).all()
    prestazioni = {p.id: p.nome for p in s.scalars(select(Prestazione))}
    medici = s.scalars(select(Operatore).order_by(Operatore.cognome, Operatore.nome)).all()
    nomi_medici = {o.id: o.etichetta for o in medici}
    # le email raggruppate per medico, in ordine di cognome; per ultime quelle per tutti
    gruppi = [(o, [r for r in regole if r.operatore_id == o.id]) for o in medici]
    gruppi = [(o, lista) for o, lista in gruppi if lista]
    per_tutti = [r for r in regole if not r.operatore_id]
    if per_tutti:
        gruppi.append((None, per_tutti))
    # per le email attive: con quali altre partono, quali sostituiscono o da quali sono sostituite
    attive = [r for r in regole if r.attiva]
    note = {}
    for r in attive:
        info = incroci(s, r, attive)
        note[r.id] = {chiave: [(s.get(RegolaEmail, k), descrivi_incrocio(v, info, nomi_medici, prestazioni))
                               for k, v in sorted(info[chiave].items())]
                      for chiave in ('insieme', 'sostituita', 'sostituisce')}
    registro = s.scalars(select(Invio).order_by(Invio.id.desc()).limit(80)).all()
    st = struttura_di(s)
    # l'indirizzo da proporre la prima volta: quello della struttura
    utente_proposto = cfg['email_utente'] or ((st.email or '').strip() if st is not None else '')
    # il tipo di casella e, se la casella non e' mai stata salvata, server, porta e
    # sicurezza proposti per quel tipo
    tipo_email = tipo_casella(cfg, utente_proposto)
    modulo_email = {'server': cfg['email_server'], 'porta': cfg['email_porta'], 'sicurezza': cfg['email_sicurezza']}
    if not cfg['email_server']:
        preset = PER_CODICE[tipo_email]
        modulo_email = {'server': server_proposto(tipo_email, utente_proposto),
                        'porta': preset['porta'] or cfg['email_porta'],
                        'sicurezza': preset['sicurezza'] or cfg['email_sicurezza']}
    ultimo_giro = leggi_impostazione(s, 'promemoria_ultimo_giro', '')
    return render_template('invii.html', cfg=cfg, email_pronta=email_pronta(cfg),
                           caselle=CASELLE, tipo_email=tipo_email, modulo_email=modulo_email,
                           whatsapp_pronto=whatsapp_pronto(cfg), regole=regole, prestazioni=prestazioni,
                           gruppi=gruppi, note=note, medici_attivi=[o for o in medici if o.attivo],
                           registro=registro, sicurezze=SICUREZZE, canali=CANALI, motivi=MOTIVI, stati=STATI,
                           pronta=regola_pronta_possibile(s), modello_wa=MODELLO_WA, parametri_wa=PARAMETRI_WA,
                           struttura=st, utente_proposto=utente_proposto,
                           password_salvata=bool(leggi_impostazione(s, 'email_password', '')),
                           token_salvato=bool(leggi_impostazione(s, 'wa_token', '')),
                           ultimo_giro=ultimo_giro, anteprima=anteprima_promemoria(s, cfg),
                           giorno_breve=servizi.etichetta_breve, sezione='invii')


@bp.route('/regole/nuova', methods=['GET', 'POST'])
@bp.route('/regole/<int:rid>', methods=['GET', 'POST'])
def regola(rid=None):
    s = ses()
    r = s.get(RegolaEmail, rid) if rid else None
    if rid and r is None:
        abort(404)
    # una email nuova "per" un medico (da Email e WhatsApp o dalla scheda del medico): gia' scelto
    proposto = s.get(Operatore, intero(request.args.get('medico'))) if r is None and request.args.get('medico') else None
    medici = s.scalars(select(Operatore).where((Operatore.attivo == True) | (Operatore.id == (r.operatore_id if r else -1)))
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    prestazioni = s.scalars(select(Prestazione).order_by(Prestazione.nome)).all()
    cfg = impostazioni(s)

    def mostra(modulo=None, scelte=None):
        insieme = sostituita = sostituisce = []
        if r is not None:
            info = incroci(s, r)
            nomi_medici = {o.id: o.etichetta for o in s.scalars(select(Operatore))}
            nomi_prestazioni = {p.id: p.nome for p in prestazioni}
            elenco = lambda chiave: [(s.get(RegolaEmail, k), descrivi_incrocio(v, info, nomi_medici, nomi_prestazioni))
                                     for k, v in sorted(info[chiave].items())]
            insieme, sostituita, sostituisce = elenco('insieme'), elenco('sostituita'), elenco('sostituisce')
        return render_template('regola_email.html', r=r, medici=medici, prestazioni=prestazioni, modulo=modulo,
                               scelte=scelte if scelte is not None else (r.id_prestazioni if r else set()),
                               segnaposto=documenti.SEGNAPOSTO_MODULI, email_pronta=email_pronta(cfg),
                               prova_a=cfg['email_utente'], proposto=proposto, insieme=insieme,
                               sostituita=sostituita, sostituisce=sostituisce,
                               altri_medici=[o for o in medici if o.attivo and (r is None or o.id != r.operatore_id)],
                               sezione='invii')

    if request.method == 'POST':
        f = request.form
        azione = f.get('azione') or 'salva'
        if azione == 'duplica' and r is not None:
            medico = s.get(Operatore, intero(f.get('medico'))) if f.get('medico') else None
            if f.get('medico') and medico is None:
                flash('Medico non valido.', 'errore')
                return redirect(url_for('invii.regola', rid=r.id) + '#duplica')
            if medico is None and not r.id_prestazioni:
                flash('Per tutti i medici serve almeno una prestazione: spuntarla qui e salvare, poi duplicare.',
                      'errore')
                return redirect(url_for('invii.regola', rid=r.id) + '#duplica')
            with _lucchetto:
                copia = duplica_regola(s, r, medico)
                s.commit()
            flash('Copia creata per %s, spenta: cambiare testo e allegati (le informative %s), poi spuntare '
                  '"Attiva" e salvare.' % (medico.etichetta if medico else 'tutti i medici',
                                           ('di ' + medico.etichetta) if medico else 'per tutti'), 'avviso')
            return redirect(url_for('invii.regola', rid=copia.id))
        if azione == 'elimina' and r is not None:
            with _lucchetto:
                for x in s.scalars(select(Invio).where(Invio.regola_id == r.id)).all():
                    if x.stato == 'DA_INVIARE':
                        x.stato, x.errore = 'ANNULLATO', 'regola eliminata'
                    if x.stato != 'IN_CORSO':
                        x.regola_id = None
                s.delete(r)
                s.commit()
            flash('Regola eliminata.', 'ok')
            return redirect(url_for('invii.pagina') + '#regole')
        if azione == 'togli_allegato' and r is not None:
            g = s.get(AllegatoRegola, intero(f.get('allegato')))
            if g is not None and g.regola_id == r.id:
                nome = g.nome
                with _lucchetto:
                    s.delete(g)
                    s.commit()
                flash('Allegato tolto: %s.' % nome, 'ok')
            return redirect(url_for('invii.regola', rid=r.id))
        if azione == 'prova' and r is not None:
            dest = (f.get('a') or '').strip()
            if not pazienti.email_valida(dest) or len(dest) > 120:
                flash('Scrivere un indirizzo email valido per la prova.', 'errore')
                return redirect(url_for('invii.regola', rid=r.id) + '#prova')
            if not email_pronta(cfg):
                flash('L\'invio delle email non è configurato: Configura → Email e WhatsApp.', 'errore')
                return redirect(url_for('invii.regola', rid=r.id) + '#prova')
            with _lucchetto:
                xid = accoda(s, 'EMAIL', 'PROVA', dest, regola=r, a_mano=True, subito=True).id
                s.commit()
            _manda_e_dici(xid, dest, 'Prova mandata, con gli allegati')
            return redirect(url_for('invii.regola', rid=r.id) + '#prova')
        if azione != 'salva':
            abort(400)
        errori = []
        nome = ' '.join((f.get('nome') or '').split())[:80]
        if not nome:
            errori.append('Serve un nome per la regola.')
        oid = intero(f.get('operatore'))
        if oid and s.get(Operatore, oid) is None:
            errori.append('Medico non valido.')
            oid = 0
        scelte = sorted({intero(x) for x in f.getlist('prestazioni')} & {p.id for p in prestazioni})
        oggetto = ' '.join((f.get('oggetto') or '').split())[:200]
        testo = (f.get('testo') or '').replace('\r\n', '\n').strip()
        if not oggetto or not testo:
            errori.append('Servono oggetto e testo dell\'email.')
        if len(testo) > MASSIMO_TESTO:
            errori.append('Testo troppo lungo: al massimo 10.000 caratteri.')
        if not oid and not scelte:
            errori.append('Scegliere almeno un medico o una prestazione: una regola per tutti gli appuntamenti '
                          'manderebbe un\'email a ogni prenotazione.')
        nuovi = []
        for file in request.files.getlist('allegati'):
            if not file or not file.filename:
                continue
            dati = file.read(MASSIMO_ALLEGATO + 1)
            nome_file = os.path.basename(file.filename.replace('\\', '/')).strip()[:120] or 'allegato.pdf'
            if len(dati) > MASSIMO_ALLEGATO:
                errori.append('%s: oltre 10 MB.' % nome_file)
            elif not dati.startswith(b'%PDF-'):
                errori.append('%s: non è un PDF.' % nome_file)
            else:
                if not nome_file.lower().endswith('.pdf'):
                    nome_file += '.pdf'
                nuovi.append((nome_file, dati))
        if errori:
            for e in errori:
                flash(e, 'errore')
            return mostra(f, set(scelte))
        with _lucchetto:
            if r is None:
                r = RegolaEmail()
                s.add(r)
            r.nome, r.operatore_id, r.prestazioni = nome, oid or None, ','.join(map(str, scelte))
            r.oggetto, r.testo, r.attiva = oggetto, testo, f.get('attiva') in ('1', 'on')
            for nome_file, dati in nuovi:
                r.allegati.append(AllegatoRegola(nome=nome_file, tipo='application/pdf', dimensione=len(dati),
                                                 dati=dati))
            s.commit()
        flash('Regola salvata: %s%s.' % (r.nome, '' if r.attiva else ' (spenta: non parte da sola)'), 'ok')
        if r.attiva:
            # due email per lo stesso appuntamento: a volte e' voluto, ma va detto
            info = incroci(s, r)
            if info['insieme']:
                nomi_medici = {o.id: o.etichetta for o in s.scalars(select(Operatore))}
                nomi_prestazioni = {p.id: p.nome for p in prestazioni}
                flash('Attenzione: insieme a questa parte anche %s; il paziente riceve due email. Se una basta, '
                      'spegnerne una o togliere le prestazioni in comune.' % '; '.join(
                          '«%s» per %s' % (s.get(RegolaEmail, k).nome,
                                           descrivi_incrocio(v, info, nomi_medici, nomi_prestazioni))
                          for k, v in sorted(info['insieme'].items())), 'avviso')
        return redirect(url_for('invii.regola', rid=r.id))
    return mostra()


@bp.route('/allegati/<int:aid>')
def allegato(aid):
    g = ses().get(AllegatoRegola, aid)
    if g is None:
        abort(404)
    risposta = send_file(BytesIO(g.dati or b''), mimetype=g.tipo or 'application/pdf', download_name=g.nome)
    risposta.headers['X-Content-Type-Options'] = 'nosniff'
    return risposta


@bp.route('/appuntamento/<int:aid>', methods=['POST'])
def appuntamento(aid):
    """Dalla pagina dell'appuntamento o dalle Conferme, a comando: l'email di
    una regola (anche di nuovo) o il promemoria adesso. Si manda subito e si
    dice com'e' andata."""
    s = ses()
    a = s.get(Appuntamento, aid)
    if a is None:
        abort(404)
    torna = destinazione_sicura(request.form.get('torna'), url_for('appuntamento', aid=a.id) + '#messaggi')
    cfg = impostazioni(s)
    azione = request.form.get('azione')
    with _lucchetto:
        if azione == 'regola':
            r = s.get(RegolaEmail, intero(request.form.get('regola')))
            if r is None:
                abort(404)
            email = (a.paziente.email or '').strip() if a.paziente else ''
            if not email_pronta(cfg):
                flash('L\'invio delle email non è configurato: Configura → Email e WhatsApp.', 'errore')
                return redirect(torna)
            if not pazienti.email_valida(email):
                flash('Il paziente non ha un indirizzo email: aggiungerlo nella scheda e riprovare.', 'errore')
                return redirect(torna)
            x = accoda(s, 'EMAIL', 'PREPARAZIONE', email, a, r, a_mano=True, subito=True)
        elif azione == 'promemoria':
            if a.paziente is None:
                abort(400)
            x = accoda_promemoria(s, a, cfg, a_mano=True)
            if x is None:
                flash('Promemoria non mandato: serve WhatsApp configurato e un cellulare, oppure l\'email del '
                      'paziente con l\'invio delle email configurato (e il consenso ai promemoria nella scheda).',
                      'errore')
                return redirect(torna)
        else:
            abort(400)
        s.commit()
        xid, destinatario = x.id, x.destinatario
    _manda_e_dici(xid, destinatario if '@' in destinatario else '+' + destinatario)
    return redirect(torna)
