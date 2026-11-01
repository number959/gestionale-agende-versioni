# -*- coding: utf-8 -*-
"""Anagrafica pazienti: ricerca, scheda con storico, doppioni, unione.

La ricerca non distingue maiuscole, accenti e apostrofi: "dangelo" trova
D'Angelo, "de luca" trova DELUCA. Si fa in Python sull'elenco intero: con
qualche migliaio di pazienti sono millisecondi, e SQLite da solo non sa
ignorare gli accenti.
"""
import os
import re
import threading
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, jsonify)
from sqlalchemy import select, func, update

from modelli import (Paziente, Appuntamento, Attivita, Attesa, Documento, Appunto, Invio, Indirizzato, STATI_ATTIVI,
                     CANALI, PROVENIENZE, ETICHETTA_PROVENIENZA)
import servizi
import codice_fiscale as CF
from comune import json_sicuro

bp = Blueprint('pazienti', __name__, url_prefix='/pazienti')
_fornitore = None
_lucchetto = threading.Lock()

PRIMA_NASCITA = date(1900, 1, 1)


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ================================================================ testi
def semplifica(testo):
    """minuscolo, senza accenti, senza apostrofi, spazi e trattini."""
    t = unicodedata.normalize('NFKD', testo or '')
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[\s'’`\-.]", '', t)


def cifre(testo):
    return re.sub(r'\D', '', testo or '')


def telefono_confronto(testo):
    """Il numero ridotto alla forma confrontabile: solo cifre, senza il
    prefisso internazionale italiano. '+39 333 12.34.567' -> '3331234567'.

    Il 39 iniziale si toglie solo se e' davvero un prefisso: 393 1234567 e'
    un cellulare italiano di dieci cifre e resta com'e'."""
    grezzo = (testo or '').strip()
    c = cifre(grezzo)
    if grezzo.startswith('+39') or c.startswith('0039'):
        return c[4:] if c.startswith('0039') else c[2:]
    if grezzo.startswith('+'):
        return c                      # numero estero, col suo prefisso
    if c.startswith('00'):
        return c[2:]
    if c.startswith('39') and len(c) >= 11:
        return c[2:]                  # undici cifre non sono un numero italiano senza prefisso
    return c


def e_cellulare(testo):
    """Cellulare italiano: 3 seguito da 8-9 cifre."""
    grezzo = (testo or '').strip()
    if (grezzo.startswith('+') and not grezzo.startswith('+39')) or \
            (cifre(grezzo).startswith('00') and not cifre(grezzo).startswith('0039')):
        return False
    return bool(re.fullmatch(r'3\d{8,9}', telefono_confronto(grezzo)))


def numero_internazionale(testo):
    """Per i collegamenti WhatsApp e tel:, senza '+': '393331234567'.
    None se non e' un numero utilizzabile."""
    grezzo = (testo or '').strip()
    c = cifre(grezzo)
    if len(c) < 6:
        return None
    if grezzo.startswith('+39') or c.startswith('0039'):
        return '39' + telefono_confronto(grezzo)
    if grezzo.startswith('+'):
        return c if len(c) >= 8 else None
    if c.startswith('00'):
        return c[2:] if len(c) >= 10 else None
    locale = telefono_confronto(grezzo)
    return '39' + locale if locale[:1] in '03' else None


EMAIL = re.compile(r"[^@\s,;<>()\[\]\"']+@[^@\s,;<>()\[\]\"']+\.[A-Za-z]{2,}")


def email_valida(testo):
    return bool(EMAIL.fullmatch((testo or '').strip()))


# ======================================================== codice fiscale
# Il codice fiscale sta in codice_fiscale.py (controllo, lettura, calcolo,
# luoghi di nascita): qui restano i nomi usati dal resto del programma.
FORMA_CF = CF.FORMA
MESI_CF = CF.MESI
_DISPARI, _PARI, _OMOCODIA = CF._DISPARI, CF._PARI, CF.OMOCODIA
SESSI = (('', '—'), ('F', 'Femmina'), ('M', 'Maschio'))


def codice_fiscale_valido(cf):
    """Forma, data esistente e carattere di controllo del codice fiscale delle persone fisiche."""
    return CF.valido(cf)


def nascita_da_cf(cf, oggi=None):
    """La data di nascita scritta nel codice fiscale (anche con l'omocodia),
    None se il codice non e' valido. Il secolo non c'e': si sceglie la data
    piu' recente che non sia nel futuro (un 25 e' il 2025 solo per un
    bambino nato prima di oggi, altrimenti il 1925)."""
    return CF.nascita(cf, oggi)


def stessa_nascita(cf, nascita):
    """Il codice fiscale e la data di nascita dicono lo stesso giorno? Si
    confrontano giorno, mese e le ultime due cifre dell'anno: il secolo nel
    codice non c'e'. True se manca uno dei due."""
    dal_cf = nascita_da_cf(cf)
    if dal_cf is None or nascita is None:
        return True
    return (dal_cf.day, dal_cf.month, dal_cf.year % 100) == (nascita.day, nascita.month, nascita.year % 100)


def leggi_nascita(grezza):
    """(data, errore) dal campo della data di nascita; vuoto va bene."""
    grezza = (grezza or '').strip()
    if not grezza:
        return None, ''
    for forma in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            nascita = datetime.strptime(grezza, forma).date()
            break
        except ValueError:
            continue
    else:
        return None, 'Data di nascita: non valida.'
    if not PRIMA_NASCITA <= nascita <= date.today():
        return None, 'Data di nascita: fuori dall\'intervallo ammesso.'
    return nascita, ''


def leggi_codice_fiscale(grezzo):
    """(codice, errore): maiuscolo, senza spazi; vuoto va bene. L'errore dice
    cosa non va (lunghezza, posto sbagliato, data inesistente, carattere di
    controllo)."""
    cf = CF.pulisci(grezzo)
    if cf and not CF.valido(cf):
        return cf[:16], 'Codice fiscale: non valido. ' + CF.difetto(cf)
    return cf, ''


def leggi_luogo(codice, testo, nascita=None):
    """(codice del luogo di nascita, errore). Il codice arriva dal campo
    nascosto, scelto fra i suggerimenti; senza codice si cerca il nome
    scritto (va bene se e' uno solo)."""
    codice = (codice or '').strip().upper()
    if codice:
        if not re.fullmatch(r'[A-Z][0-9]{3}', codice):
            return '', 'Luogo di nascita: non valido.'
        return codice, ''
    return CF.risolvi_luogo(testo, nascita)


def leggi_anagrafica(f, cognome='', nome=''):
    """Data, sesso e luogo di nascita e codice fiscale dal modulo, controllati
    e completati: (valori, errori, calcolato).
    - un codice fiscale scritto deve essere valido;
    - da un codice valido si completano i campi lasciati vuoti (quelli
      scritti restano: se non tornano, lo dicono gli avvisi dopo il
      salvataggio);
    - codice vuoto e tutti i dati: si calcola (calcolato = True)."""
    errori = []
    nascita, errore = leggi_nascita(f.get('data_nascita'))
    if errore:
        errori.append(errore)
    sesso = (f.get('sesso') or '').strip().upper()
    if sesso not in ('', 'M', 'F'):
        errori.append('Sesso: scelta non valida.')
        sesso = ''
    luogo, errore = leggi_luogo(f.get('luogo_nascita'), f.get('luogo_nascita_testo'), nascita)
    if errore:
        errori.append(errore)
    cf, errore = leggi_codice_fiscale(f.get('codice_fiscale'))
    calcolato = False
    if errore:
        errori.append(errore)
    elif cf:
        dati = CF.leggi(cf)
        if nascita is None and dati['data_nascita']:
            nascita = dati['data_nascita']
        sesso = sesso or dati['sesso']
        luogo = luogo or dati['luogo']
        if f.get('cf_calcolato') == '1':
            # calcolato nel modulo mentre si scriveva (e non toccato dopo): vale come calcolato qui
            try:
                calcolato = CF.calcola(cognome, nome, nascita, sesso, luogo) == cf
            except CF.DatiMancanti:
                pass
    elif not errori:
        try:
            cf, calcolato = CF.calcola(cognome, nome, nascita, sesso, luogo), True
        except CF.DatiMancanti:
            pass
    return dict(data_nascita=nascita, sesso=sesso, luogo_nascita=luogo, codice_fiscale=cf), errori, calcolato


def completa_da_codice(p):
    """Sesso, luogo e data di nascita dal codice fiscale valido della scheda,
    dove mancano. True se ha cambiato qualcosa."""
    dati = CF.leggi(p.codice_fiscale) if p is not None and p.codice_fiscale else None
    if not dati:
        return False
    cambiato = False
    if not p.data_nascita and dati['data_nascita']:
        p.data_nascita, cambiato = dati['data_nascita'], True
    if not p.sesso:
        p.sesso, cambiato = dati['sesso'], True
    if not p.luogo_nascita:
        p.luogo_nascita, cambiato = dati['luogo'], True
    return cambiato


def avvisi_anagrafica(p):
    """Dopo il salvataggio: il codice fiscale corrisponde a cognome, nome,
    data, sesso e luogo di nascita? Avvisi, non errori."""
    if p is None or not p.codice_fiscale:
        return []
    return CF.confronta(p.codice_fiscale, p.cognome, p.nome, p.data_nascita, p.sesso, p.luogo_nascita)


def nota_calcolato(cf):
    return ('Codice fiscale calcolato dai dati: %s (controllarlo sulla tessera sanitaria: in rari casi è diverso).'
            % cf)


def leggi_indirizzo(grezzo):
    """(indirizzo, errore): una riga, spazi in piu' tolti."""
    indirizzo = ' '.join((grezzo or '').split())
    if len(indirizzo) > 200:
        return indirizzo[:200], 'Indirizzo: al massimo 200 caratteri.'
    return indirizzo, ''


def avviso_nascita(cf, nascita):
    """Un avviso (non un errore) se data di nascita e codice fiscale non
    tornano: uno dei due e' scritto male."""
    if stessa_nascita(cf, nascita):
        return ''
    return ('La data di nascita (%s) non corrisponde a quella del codice fiscale (%s): controllare.'
            % (nascita.strftime('%d/%m/%Y'), nascita_da_cf(cf).strftime('%d/%m/%Y')))


# ================================================================ ricerca
def cerca(s, q, limite=50):
    """Pazienti che corrispondono a tutte le parole cercate. Una parola di
    sole cifre (almeno 3) si cerca nei telefoni; le altre in cognome, nome,
    email e codice fiscale."""
    parole = [p for p in re.split(r'\s+', (q or '').strip()) if p]
    if not parole:
        return []
    righe = s.execute(select(Paziente.id, Paziente.cognome, Paziente.nome, Paziente.telefono,
                             Paziente.telefono2, Paziente.email, Paziente.codice_fiscale)).all()
    trovati = []
    for r in righe:
        nomi = semplifica('%s %s' % (r.cognome or '', r.nome or '')) + ' ' + \
            semplifica('%s %s' % (r.nome or '', r.cognome or ''))
        altro = ((r.email or '') + ' ' + (r.codice_fiscale or '')).lower()
        telefoni = telefono_confronto(r.telefono) + ' ' + telefono_confronto(r.telefono2)
        punteggio = 0
        for p in parole:
            if re.fullmatch(r'[\d+ ]{3,}', p):
                if telefono_confronto(p) not in telefoni:
                    break
                punteggio += 1
            else:
                sp = semplifica(p)
                if not sp:
                    continue
                if sp in nomi:
                    punteggio += 3 if semplifica(r.cognome).startswith(sp) else 2
                elif p.lower() in altro:
                    punteggio += 1
                else:
                    break
        else:
            trovati.append((-punteggio, semplifica(r.cognome), semplifica(r.nome), r.id))
    trovati.sort()
    ids = [t[3] for t in trovati[:limite]]
    per_id = {p.id: p for p in s.scalars(select(Paziente).where(Paziente.id.in_(ids)))} if ids else {}
    return [per_id[i] for i in ids if i in per_id]


def doppioni(s, cognome, nome='', telefono='', email='', escludi_id=None, codice_fiscale=''):
    """Pazienti che potrebbero essere la stessa persona: stesso cognome e
    nome, oppure stesso telefono, oppure stessa email, oppure stesso codice
    fiscale."""
    c, n = semplifica(cognome), semplifica(nome)
    tel = telefono_confronto(telefono)
    mail = (email or '').strip().lower()
    cf = CF.pulisci(codice_fiscale)
    trovati = []
    for p in s.scalars(select(Paziente)):
        if escludi_id and p.id == escludi_id:
            continue
        stesso_nome = c and semplifica(p.cognome) == c and (
            (n and semplifica(p.nome) == n) or (not n and not semplifica(p.nome)))
        stesso_tel = len(tel) >= 6 and tel in (telefono_confronto(p.telefono),
                                               telefono_confronto(p.telefono2))
        stessa_mail = mail and (p.email or '').strip().lower() == mail
        stesso_cf = cf and CF.pulisci(p.codice_fiscale) == cf
        if stesso_nome or stesso_tel or stessa_mail or stesso_cf:
            trovati.append(p)
    return trovati[:10]


# ================================================================ storico
def storico(s, paziente_id):
    return s.scalars(select(Appuntamento).where(Appuntamento.paziente_id == paziente_id)
                     .order_by(Appuntamento.inizio.desc())).all()


def riepilogo(appuntamenti, adesso=None):
    adesso = adesso or datetime.now()
    anno_fa = adesso - timedelta(days=365)
    attivi = [a for a in appuntamenti if a.stato in STATI_ATTIVI]
    futuri = sorted([a for a in attivi if a.inizio >= adesso], key=lambda a: a.inizio)
    passati = [a for a in appuntamenti if a.inizio < adesso and a.stato in STATI_ATTIVI + ('NON_PRESENTATO',)]
    return {
        'totale': len(appuntamenti),
        'futuri': futuri,
        'prossimo': futuri[0] if futuri else None,
        'ultimo': max(passati, key=lambda a: a.inizio) if passati else None,
        'visite': sum(1 for a in passati if a.stato in STATI_ATTIVI),
        'disdetti': sum(1 for a in appuntamenti if a.stato == 'DISDETTO'),
        'assenze_anno': sum(1 for a in appuntamenti if a.stato == 'NON_PRESENTATO' and a.inizio >= anno_fa),
    }


def avvisi_prenotazione(s, paziente, appuntamento):
    """Cose da far notare a chi ha appena prenotato: un altro appuntamento
    lo stesso giorno, assenze ripetute."""
    if paziente is None:
        return []
    avvisi = []
    g = appuntamento.inizio.date()
    inizio = datetime.combine(g, datetime.min.time())
    stesso_giorno = s.scalars(select(Appuntamento).where(
        Appuntamento.paziente_id == paziente.id, Appuntamento.id != appuntamento.id,
        Appuntamento.inizio >= inizio, Appuntamento.inizio < inizio + timedelta(days=1),
        Appuntamento.stato.in_(STATI_ATTIVI)).order_by(Appuntamento.inizio)).all()
    for a in stesso_giorno:
        avvisi.append('%s ha anche un appuntamento alle %s (%s).' % (
            paziente.etichetta, a.inizio.strftime('%H:%M'), a.risorsa.nome if a.risorsa else ''))
    assenze = s.scalar(select(func.count()).select_from(Appuntamento).where(
        Appuntamento.paziente_id == paziente.id, Appuntamento.stato == 'NON_PRESENTATO',
        Appuntamento.inizio >= datetime.now() - timedelta(days=365)))
    if assenze and assenze >= 2:
        avvisi.append('Attenzione: %s non si è presentato %d volte nell\'ultimo anno.' % (
            paziente.etichetta, assenze))
    return avvisi


def _altra_persona(p, nome, data_nascita, codice_fiscale, cf_calcolato):
    """Scelto dall'elenco, ma il modulo descrive chiaramente un'altra persona con
    lo stesso cognome (un familiare): un altro nome e un'altra data di nascita, o
    un altro codice fiscale scritto. Fino alla 1.10 la scheda scelta veniva
    sovrascritta con i dati dell'altro (1.11). Solo il nome diverso non basta:
    puo' essere una correzione, e la scheda scelta resta."""
    if not nome or not p.nome or semplifica(nome) == semplifica(p.nome):
        return False
    if data_nascita and p.data_nascita and data_nascita != p.data_nascita:
        return True
    return bool(codice_fiscale and not cf_calcolato and p.codice_fiscale and
                codice_fiscale != p.codice_fiscale.upper())


def trova_o_crea(s, paziente_id, cognome, nome='', telefono='', email='', data_nascita=None,
                 codice_fiscale='', indirizzo='', sesso='', luogo_nascita='', cf_calcolato=False):
    """Il paziente dell'appuntamento.

    - scelto dall'elenco (paziente_id) e con lo stesso cognome: e' lui, e
      i dati scritti nel modulo aggiornano la sua scheda (un campo lasciato
      vuoto non cancella niente);
    - altrimenti si riusa una scheda se coincidono cognome e codice fiscale,
      oppure cognome e uno dei due telefoni (e il nome, se scritto): due
      omonimi non diventano la stessa persona. Della scheda trovata si
      completano solo i campi vuoti;
    - altrimenti scheda nuova. Senza cognome, nessun paziente.

    I valori arrivano gia' controllati (codice fiscale valido, data
    plausibile). Un codice fiscale calcolato dai dati (cf_calcolato) non
    prende mai il posto di quello gia' nella scheda: quello vero puo'
    essere diverso (omocodia)."""
    cognome, nome = (cognome or '').strip(), (nome or '').strip()
    sesso, luogo_nascita = (sesso or '').strip().upper(), (luogo_nascita or '').strip().upper()
    telefono, email = (telefono or '').strip(), (email or '').strip()
    codice_fiscale = (codice_fiscale or '').strip().upper()
    indirizzo = ' '.join((indirizzo or '').split())
    p = s.get(Paziente, paziente_id) if paziente_id else None
    if p is not None and (not cognome or semplifica(cognome) == semplifica(p.cognome)) and \
            not _altra_persona(p, nome, data_nascita, codice_fiscale, cf_calcolato):
        if nome and not p.nome:
            p.nome = nome
        if telefono and telefono_confronto(telefono) not in (telefono_confronto(p.telefono),
                                                             telefono_confronto(p.telefono2)):
            if p.telefono and not p.telefono2:
                p.telefono2 = p.telefono      # il numero vecchio non si perde
            p.telefono = telefono
        if email and email.lower() != (p.email or '').lower():
            p.email = email
        if data_nascita and data_nascita != p.data_nascita:
            p.data_nascita = data_nascita
        if codice_fiscale and codice_fiscale != (p.codice_fiscale or '').upper() and not (
                cf_calcolato and p.codice_fiscale):
            p.codice_fiscale = codice_fiscale
        if indirizzo and indirizzo != (p.indirizzo or ''):
            p.indirizzo = indirizzo
        if sesso and sesso != (p.sesso or ''):
            p.sesso = sesso
        if luogo_nascita and luogo_nascita != (p.luogo_nascita or ''):
            p.luogo_nascita = luogo_nascita
        return p
    if not cognome:
        return None

    def completa(c):
        for campo, valore in (('nome', nome), ('email', email), ('data_nascita', data_nascita),
                              ('codice_fiscale', codice_fiscale), ('indirizzo', indirizzo), ('sesso', sesso),
                              ('luogo_nascita', luogo_nascita)):
            if valore and not getattr(c, campo):
                setattr(c, campo, valore)
        return c

    c_s, n_s = semplifica(cognome), semplifica(nome)
    if codice_fiscale and not cf_calcolato:
        # lo stesso codice fiscale e lo stesso cognome: e' lui, anche se chiama da un altro numero
        for r in s.execute(select(Paziente.id, Paziente.cognome).where(
                func.upper(Paziente.codice_fiscale) == codice_fiscale).order_by(Paziente.id)):
            if semplifica(r.cognome) == c_s:
                c = completa(s.get(Paziente, r.id))
                # il numero nuovo non si perde: va nel secondo telefono, se e' libero
                if telefono and not c.telefono2 and telefono_confronto(telefono) not in (
                        telefono_confronto(c.telefono), ''):
                    if c.telefono:
                        c.telefono2 = telefono
                    else:
                        c.telefono = telefono
                return c
    tel = telefono_confronto(telefono)
    if len(tel) >= 6:
        # il cognome come lo confronta la ricerca: senza accenti, apostrofi
        # (anche quello curvo del telefonino) e spazi; e tutti e due i telefoni
        for r in s.execute(select(Paziente.id, Paziente.cognome, Paziente.nome, Paziente.telefono,
                                  Paziente.telefono2, Paziente.codice_fiscale).order_by(Paziente.id)):
            if semplifica(r.cognome) != c_s or tel not in (telefono_confronto(r.telefono),
                                                           telefono_confronto(r.telefono2)):
                continue
            if nome and r.nome and semplifica(r.nome) != n_s:
                continue
            # stesso numero ma un altro codice fiscale: un familiare, non lui. Un codice
            # calcolato dai dati si confronta senza le lettere dell'omocodia (1.11): quello
            # vero di una persona puo' averle, e prima la sua scheda veniva scartata e ne
            # nasceva un doppione
            if codice_fiscale and r.codice_fiscale:
                if cf_calcolato:
                    if CF.senza_omocodia(r.codice_fiscale.upper())[:15] != codice_fiscale[:15]:
                        continue
                elif r.codice_fiscale.upper() != codice_fiscale:
                    continue
            return completa(s.get(Paziente, r.id))
    p = Paziente(cognome=cognome, nome=nome, telefono=telefono, email=email, data_nascita=data_nascita,
                 codice_fiscale=codice_fiscale, indirizzo=indirizzo, sesso=sesso, luogo_nascita=luogo_nascita)
    s.add(p)
    s.flush()
    return p


def unisci(s, tenuto, eliminato):
    """Porta gli appuntamenti di 'eliminato' su 'tenuto', completa i campi
    vuoti di 'tenuto' e cancella 'eliminato'. Restituisce quanti spostati."""
    n = s.execute(update(Appuntamento).where(Appuntamento.paziente_id == eliminato.id)
                  .values(paziente_id=tenuto.id)).rowcount
    # documenti, cose da fare e lista d'attesa seguono la persona
    for modello in (Documento, Attivita, Attesa, Appunto, Invio, Indirizzato):
        s.execute(update(modello).where(modello.paziente_id == eliminato.id).values(paziente_id=tenuto.id))
    for campo in ('nome', 'email', 'codice_fiscale', 'data_nascita', 'indirizzo', 'sesso', 'luogo_nascita'):
        if not getattr(tenuto, campo) and getattr(eliminato, campo):
            setattr(tenuto, campo, getattr(eliminato, campo))
    # i telefoni (1.11): prima quelli della scheda tenuta, poi quelli dell'altra, senza
    # doppioni (lo stesso numero scritto in due modi conta una volta). Prima il
    # cellulare dell'altra si perdeva quando la tenuta aveva solo il fisso: il
    # secondo telefono vuoto si riempiva con il suo secondo numero, non con il primo.
    # Quelli che non ci stanno nei due campi vanno nelle note: non si perde niente
    numeri, visti = [], set()
    for t in (tenuto.telefono, tenuto.telefono2, eliminato.telefono, eliminato.telefono2):
        t = (t or '').strip()
        chiave = telefono_confronto(t)
        if t and chiave not in visti:
            visti.add(chiave)
            numeri.append(t)
    tenuto.telefono = numeri[0] if numeri else ''
    tenuto.telefono2 = numeri[1] if len(numeri) > 1 else ''
    if numeri[2:]:
        tenuto.note = ((tenuto.note or '').strip() + '\nAltro telefono: ' + ', '.join(numeri[2:])).strip()
    completa_da_codice(tenuto)
    if (eliminato.note or '').strip():
        tenuto.note = ((tenuto.note or '').strip() + '\n' + eliminato.note.strip()).strip()
    servizi.registra(s, 'Paziente', tenuto.id, 'UNITO',
                     'unito %s (id %d): %d appuntamenti' % (eliminato.etichetta, eliminato.id, n))
    s.delete(eliminato)
    return n


# ================================================================ pagine
def _intero(valore):
    try:
        v = int(valore)
    except (TypeError, ValueError):
        return 0
    return v if 0 < v < 2 ** 63 else 0


@bp.route('')
def elenco():
    s = ses()
    q = (request.args.get('q') or '').strip()[:100]
    if q:
        risultati = cerca(s, q)
    else:
        # senza ricerca: gli ultimi inseriti
        risultati = s.scalars(select(Paziente).order_by(Paziente.id.desc()).limit(30)).all()
    prossimi = {}
    if risultati:
        adesso = datetime.now()
        for a in s.scalars(select(Appuntamento).where(
                Appuntamento.paziente_id.in_([p.id for p in risultati]),
                Appuntamento.inizio >= adesso, Appuntamento.stato.in_(STATI_ATTIVI))
                .order_by(Appuntamento.inizio)):
            prossimi.setdefault(a.paziente_id, a)
    totale = s.scalar(select(func.count()).select_from(Paziente))
    return render_template('pazienti.html', q=q, risultati=risultati, prossimi=prossimi,
                           totale=totale, sezione='pazienti')


@bp.route('/cerca')
def cerca_json():
    """Suggerimenti per il modulo di prenotazione, mentre si scrive."""
    s = ses()
    q = (request.args.get('q') or '').strip()[:100]
    if len(q) < 2:
        return json_sicuro([])
    uscita = []
    adesso = datetime.now()
    for p in cerca(s, q, limite=8):
        prossimo = s.scalars(select(Appuntamento).where(
            Appuntamento.paziente_id == p.id, Appuntamento.inizio >= adesso,
            Appuntamento.stato.in_(STATI_ATTIVI)).order_by(Appuntamento.inizio)).first()
        uscita.append({
            'id': p.id, 'cognome': p.cognome or '', 'nome': p.nome or '',
            'telefono': p.telefono or '', 'email': p.email or '',
            'nascita': p.data_nascita.strftime('%d/%m/%Y') if p.data_nascita else '',
            'nascita_iso': p.data_nascita.isoformat() if p.data_nascita else '',
            'codice_fiscale': p.codice_fiscale or '', 'indirizzo': p.indirizzo or '',
            'sesso': p.sesso or '', 'luogo': p.luogo_nascita or '',
            'luogo_testo': CF.testo_luogo(p.luogo_nascita, p.data_nascita) if p.luogo_nascita else '',
            'prossimo': prossimo.inizio.strftime('%d/%m %H:%M') if prossimo else '',
        })
    return json_sicuro(uscita)


@bp.route('/codice-fiscale')
def codice_fiscale_json():
    """Il codice fiscale mentre si scrive, nella scheda e nel modulo di
    prenotazione: esito (con il motivo, se non va), dati letti dal codice,
    avvisi se non corrisponde ai dati, codice calcolato se manca."""
    a = request.args
    nascita, _ = leggi_nascita(a.get('data_nascita'))
    luogo = (a.get('luogo') or '').strip().upper()[:4]
    if not luogo and (a.get('luogo_testo') or '').strip():
        luogo, _ = CF.risolvi_luogo((a.get('luogo_testo') or '')[:80], nascita)
    sesso = (a.get('sesso') or '').strip().upper()
    esito = CF.esamina((a.get('cf') or '')[:40], (a.get('cognome') or '')[:60], (a.get('nome') or '')[:60],
                       nascita, sesso if sesso in ('M', 'F') else '', luogo)
    esito['luogo'] = luogo
    esito['luogo_testo'] = CF.testo_luogo(luogo, nascita) if luogo else ''
    return json_sicuro(esito)


@bp.route('/luoghi')
def luoghi_json():
    """Suggerimenti per il luogo di nascita: comuni (anche soppressi) e stati esteri."""
    q = (request.args.get('q') or '').strip()[:60]
    if len(CF.chiave(q)) < 2:
        return json_sicuro([])
    nascita, _ = leggi_nascita(request.args.get('data_nascita'))
    return json_sicuro(CF.cerca_luoghi(q, nascita))


# ===================================================== codici fiscali in archivio
def esamina_archivio(s, adesso=None):
    """Il controllo di tutti i codici fiscali in anagrafica:
    - non validi, con il motivo;
    - validi ma che non corrispondono a cognome, nome, data, sesso o luogo;
    - lo stesso codice su piu' schede (doppioni da unire);
    - mancanti ma calcolabili (ci sono tutti i dati);
    - mancanti e non calcolabili, con quello che manca: prima chi ha un
      appuntamento in programma, da chiedere quando viene."""
    adesso = adesso or datetime.now()
    prossimi = {}
    for pid, inizio in s.execute(select(Appuntamento.paziente_id, func.min(Appuntamento.inizio)).where(
            Appuntamento.paziente_id.isnot(None), Appuntamento.inizio >= adesso,
            Appuntamento.stato.in_(STATI_ATTIVI)).group_by(Appuntamento.paziente_id)):
        prossimi[pid] = inizio
    r = {'totale': 0, 'validi': 0, 'non_validi': [], 'non_coerenti': [], 'doppi': [], 'calcolabili': [],
         'senza': [], 'senza_totale': 0, 'prossimi': prossimi}
    per_codice = {}
    for p in s.scalars(select(Paziente).order_by(Paziente.cognome, Paziente.nome, Paziente.id)):
        r['totale'] += 1
        cf = CF.pulisci(p.codice_fiscale)
        if cf:
            motivo = CF.difetto(cf)
            if motivo:
                r['non_validi'].append((p, motivo))
                continue
            r['validi'] += 1
            per_codice.setdefault(cf, []).append(p)
            avvisi = CF.confronta(cf, p.cognome, p.nome, p.data_nascita, p.sesso, p.luogo_nascita)
            if avvisi:
                r['non_coerenti'].append((p, avvisi))
            continue
        try:
            r['calcolabili'].append((p, CF.calcola(p.cognome, p.nome, p.data_nascita, p.sesso, p.luogo_nascita)))
        except CF.DatiMancanti as e:
            r['senza'].append((p, e.mancano))
    r['doppi'] = [gruppo for gruppo in per_codice.values() if len(gruppo) > 1]
    r['senza_totale'] = len(r['senza'])
    r['senza'].sort(key=lambda x: (x[0].id not in prossimi, prossimi.get(x[0].id, adesso), x[0].cognome or ''))
    r['senza'] = r['senza'][:100]
    r['da_vedere'] = len(r['non_validi']) + len(r['non_coerenti']) + len(r['doppi']) + len(r['calcolabili'])
    return r


@bp.route('/codici-fiscali', methods=['GET', 'POST'])
def codici_fiscali():
    s = ses()
    if request.method == 'POST' and request.form.get('azione') == 'calcola':
        import backup
        import viste
        with _lucchetto:
            calcolabili = esamina_archivio(s)['calcolabili']
            if not calcolabili:
                flash('Non c\'è nessun codice fiscale da calcolare.', 'ok')
                return redirect(url_for('pazienti.codici_fiscali'))
            percorso, _ = viste.percorso_database()
            copia = ''
            if percorso:
                try:
                    copia = backup.esegui(percorso, viste.cartella_effettiva(s, percorso), 'prima-dei-codici-fiscali')
                except Exception as e:
                    flash('La copia di sicurezza non è riuscita (%s): nessun codice calcolato.' % e, 'errore')
                    return redirect(url_for('pazienti.codici_fiscali'))
            for p, codice in calcolabili:
                p.codice_fiscale = codice
                servizi.registra(s, 'Paziente', p.id, 'CODICE_FISCALE', 'calcolato dai dati: %s' % codice)
            s.commit()
        flash('Calcolat%s %d codic%s fiscal%s dai dati%s: vanno controllati sulla tessera sanitaria quando il paziente '
              'viene.' % ('o' if len(calcolabili) == 1 else 'i', len(calcolabili),
                          'e' if len(calcolabili) == 1 else 'i', 'e' if len(calcolabili) == 1 else 'i',
                          ' (prima, la copia di sicurezza %s)' % os.path.basename(copia) if copia else ''), 'ok')
        return redirect(url_for('pazienti.codici_fiscali'))
    return render_template('codici_fiscali.html', r=esamina_archivio(s), testo_luogo=testo_luogo_paziente,
                           sezione='pazienti')


def testo_luogo_paziente(p):
    """'Napoli (NA)' per la scheda; il codice se non e' fra quelli conosciuti."""
    luogo = getattr(p, 'luogo_nascita', '') if p is not None else ''
    if not luogo:
        return ''
    return CF.testo_luogo(luogo, getattr(p, 'data_nascita', None)) or luogo


def _campi_modulo(p, dati=None):
    def v(nome, predefinito=''):
        if dati is not None:
            return dati.get(nome, '')
        return predefinito
    return {
        'cognome': v('cognome', p.cognome if p else ''),
        'nome': v('nome', p.nome if p else ''),
        'data_nascita': v('data_nascita', p.data_nascita.isoformat() if p and p.data_nascita else ''),
        'codice_fiscale': v('codice_fiscale', p.codice_fiscale if p else ''),
        'sesso': v('sesso', (p.sesso if p else '') or ''),
        'luogo_nascita': v('luogo_nascita', (p.luogo_nascita if p else '') or ''),
        'luogo_nascita_testo': v('luogo_nascita_testo', testo_luogo_paziente(p) if p else ''),
        'telefono': v('telefono', p.telefono if p else ''),
        'telefono2': v('telefono2', p.telefono2 if p else ''),
        'email': v('email', p.email if p else ''),
        'indirizzo': v('indirizzo', (p.indirizzo if p else '') or ''),
        'canale': v('canale', (p.canale if p else '') or 'WHATSAPP'),
        'promemoria': (dati.get('promemoria') in ('1', 'on')) if dati is not None
        else (p.promemoria if p and p.promemoria is not None else True),
        'note': v('note', p.note if p else ''),
        'provenienza': v('provenienza', (p.provenienza if p else '') or ''),
        'inviato_da': v('inviato_da', (p.inviato_da if p else '') or ''),
    }


def leggi_modulo(f):
    """Controlla il modulo del paziente. Restituisce (valori, errori)."""
    errori = []
    cognome = (f.get('cognome') or '').strip()
    nome = (f.get('nome') or '').strip()
    if not cognome:
        errori.append('Cognome: campo obbligatorio.')
    for testo, etichetta, massimo in ((cognome, 'Cognome', 60), (nome, 'Nome', 60)):
        if len(testo) > massimo:
            errori.append('%s: al massimo %d caratteri.' % (etichetta, massimo))
    telefoni = {}
    for campo, etichetta in (('telefono', 'Telefono'), ('telefono2', 'Altro telefono')):
        t = ' '.join((f.get(campo) or '').split())
        if len(t) > 30:
            errori.append('%s: al massimo 30 caratteri.' % etichetta)
        elif t and len(cifre(t)) < 6:
            errori.append('%s: servono almeno 6 cifre.' % etichetta)
        telefoni[campo] = t
    email = (f.get('email') or '').strip()
    if email and (len(email) > 120 or not email_valida(email)):
        errori.append('Email: indirizzo non valido.')
    anagrafica, errori_anagrafica, calcolato = leggi_anagrafica(f, cognome, nome)
    indirizzo, errore_indirizzo = leggi_indirizzo(f.get('indirizzo'))
    errori += errori_anagrafica + [e for e in (errore_indirizzo,) if e]
    canale = f.get('canale') or 'WHATSAPP'
    if canale not in dict(CANALI):
        errori.append('Canale: scelta non valida.')
    note = (f.get('note') or '').strip()
    if len(note) > 2000:
        errori.append('Note: al massimo 2000 caratteri.')
    provenienza = f.get('provenienza') or ''
    if provenienza not in ETICHETTA_PROVENIENZA:
        errori.append('Provenienza: scelta non valida.')
        provenienza = ''
    inviato_da = ' '.join((f.get('inviato_da') or '').split())
    if len(inviato_da) > 80:
        errori.append('Inviato da: al massimo 80 caratteri.')
    valori = dict(cognome=cognome, nome=nome, telefono=telefoni['telefono'],
                  telefono2=telefoni['telefono2'], email=email, indirizzo=indirizzo, canale=canale,
                  promemoria=f.get('promemoria') in ('1', 'on'), note=note,
                  provenienza=provenienza, inviato_da=inviato_da, **anagrafica)
    return valori, errori, calcolato


@bp.route('/nuovo', methods=['GET', 'POST'])
@bp.route('/<int:pid>', methods=['GET', 'POST'])
def scheda(pid=None):
    s = ses()
    p = s.get(Paziente, pid) if pid else None
    if pid and p is None:
        abort(404)
    possibili = []
    if request.method == 'POST':
        with _lucchetto:
            if request.form.get('azione') == 'elimina' and p is not None:
                n = s.scalar(select(func.count()).select_from(Appuntamento)
                             .where(Appuntamento.paziente_id == p.id))
                documenti = s.scalar(select(func.count()).select_from(Documento)
                                     .where(Documento.paziente_id == p.id))
                if documenti and not n:
                    flash('%s ha %d document%s allegat%s: eliminarli prima dalla scheda.' % (
                        p.etichetta, documenti, 'o' if documenti == 1 else 'i', 'o' if documenti == 1 else 'i'), 'errore')
                    return redirect(url_for('pazienti.scheda', pid=p.id))
                if n:
                    flash('%s ha %d appuntament%s: non si può eliminare. Se è un doppione, '
                          'si può unire a un\'altra scheda.' % (p.etichetta, n, 'o' if n == 1 else 'i'),
                          'errore')
                    return redirect(url_for('pazienti.scheda', pid=p.id))
                servizi.registra(s, 'Paziente', p.id, 'ELIMINATO', p.etichetta)
                for modello in (Attivita, Attesa):
                    for x in s.scalars(select(modello).where(modello.paziente_id == p.id)):
                        s.delete(x)
                # il registro dei messaggi e quello dei pazienti indirizzati restano, senza il
                # collegamento alla scheda (il nome e' copiato)
                for modello in (Invio, Indirizzato):
                    s.execute(update(modello).where(modello.paziente_id == p.id).values(paziente_id=None))
                # gli appunti restano, con il nome scritto
                for x in s.scalars(select(Appunto).where(Appunto.paziente_id == p.id)):
                    x.cognome, x.nome, x.telefono, x.paziente_id = p.cognome, p.nome or '', p.telefono or '', None
                s.delete(p)
                s.commit()
                flash('Paziente eliminato.', 'ok')
                return redirect(url_for('pazienti.elenco'))
            valori, errori, calcolato = leggi_modulo(request.form)
            if not errori and request.form.get('doppione_confermato') != '1':
                possibili = doppioni(s, valori['cognome'], valori['nome'], valori['telefono'],
                                     valori['email'], escludi_id=p.id if p else None,
                                     codice_fiscale='' if calcolato else valori['codice_fiscale'])
            if errori or possibili:
                for e in errori:
                    flash(e, 'errore')
                return _mostra(s, p, _campi_modulo(p, request.form), possibili)
            nuovo = p is None
            if nuovo:
                p = Paziente()
                s.add(p)
            for k, v in valori.items():
                setattr(p, k, v)
            s.flush()
            servizi.registra(s, 'Paziente', p.id, 'SALVATO', p.etichetta)
            s.commit()
            avvisi = avvisi_anagrafica(p)
            testi = ([nota_calcolato(p.codice_fiscale)] if calcolato else []) + avvisi
            flash('Scheda salvata: %s.%s' % (p.etichetta, ' ' + ' '.join(testi) if testi else ''),
                  'avviso' if avvisi else 'ok')
            torna = request.form.get('torna') or ''
            if nuovo and torna.startswith('/appuntamento'):
                # arrivati dal modulo di prenotazione: si torna li', col paziente scelto
                separatore = '&' if '?' in torna else '?'
                return redirect(torna + separatore + 'paziente_id=%d' % p.id)
            return redirect(url_for('pazienti.scheda', pid=p.id))
    return _mostra(s, p, _campi_modulo(p), possibili)


def _mostra(s, p, campi, possibili):
    apps = storico(s, p.id) if p is not None else []
    documenti, cose, attese = [], [], []
    if p is not None:
        documenti = s.scalars(select(Documento).where(Documento.paziente_id == p.id)
                              .order_by(Documento.caricato_il.desc(), Documento.id.desc())).all()
        cose = s.scalars(select(Attivita).where(Attivita.paziente_id == p.id, Attivita.fatto_il == None)
                         .order_by(Attivita.per_il)).all()
        attese = s.scalars(select(Attesa).where(Attesa.paziente_id == p.id, Attesa.chiusa_il == None)).all()
    return render_template('paziente.html', p=p, campi=campi, possibili=possibili,
                           appuntamenti=apps, riepilogo=riepilogo(apps), canali=CANALI,
                           provenienze=PROVENIENZE, documenti=documenti, cose=cose, attese=attese,
                           oggi=date.today(),
                           torna=request.values.get('torna', ''),
                           collegamenti=collegamenti_paziente(p) if p else {},
                           sezione='pazienti')


@bp.route('/<int:pid>/unisci', methods=['GET', 'POST'])
def unisci_pagina(pid):
    """Unire due schede della stessa persona: si sceglie la scheda da
    assorbire, si vede cosa succede, si conferma."""
    s = ses()
    p = s.get(Paziente, pid)
    if p is None:
        abort(404)
    altro = s.get(Paziente, _intero(request.values.get('altro')))
    if altro is not None and altro.id == p.id:
        altro = None
    if request.method == 'POST' and altro is not None and request.form.get('conferma') == '1':
        with _lucchetto:
            n = unisci(s, p, altro)
            s.commit()
        flash('Schede unite: %d appuntament%s spostat%s su %s.' % (
            n, 'o' if n == 1 else 'i', 'o' if n == 1 else 'i', p.etichetta), 'ok')
        return redirect(url_for('pazienti.scheda', pid=p.id))
    q = (request.args.get('q') or '').strip()[:100]
    candidati = [x for x in (cerca(s, q) if q else doppioni(s, p.cognome, p.nome, p.telefono, p.email,
                                                           escludi_id=p.id)) if x.id != p.id]
    return render_template('unisci.html', p=p, altro=altro, q=q, candidati=candidati,
                           appuntamenti_altro=storico(s, altro.id) if altro else [],
                           sezione='pazienti')


# ======================================================== collegamenti
def cellulare_whatsapp(p):
    """Il numero per WhatsApp, senza '+': il primo cellulare (o numero
    estero) fra i due telefoni, anche se e' il secondo: spesso il primo e'
    il fisso di casa. None se non c'e'."""
    if p is None:
        return None
    for t in (p.telefono, p.telefono2):
        n = numero_internazionale(t)
        if n and (e_cellulare(t) or not n.startswith('39')):
            return n
    return None


def collegamenti_paziente(p, testo='', oggetto=''):
    """Collegamenti per chiamare, scrivere su WhatsApp e mandare una email."""
    uscita = {}
    if p is None:
        return uscita
    # si chiama il primo numero valido; WhatsApp va al primo cellulare (o
    # numero estero), anche se e' il secondo: spesso il primo e' il fisso di casa
    numeri = [(t, numero_internazionale(t)) for t in (p.telefono, p.telefono2)]
    numeri = [(t, n) for t, n in numeri if n]
    if numeri:
        uscita['tel'] = 'tel:+' + numeri[0][1]
        uscita['tel_numero'] = ' '.join(numeri[0][0].split())
    mobile = cellulare_whatsapp(p)
    if mobile:
        uscita['whatsapp'] = 'https://wa.me/%s%s' % (mobile, ('?text=' + quote(testo)) if testo else '')
    if p.email and email_valida(p.email):
        parametri = []
        if oggetto:
            parametri.append('subject=' + quote(oggetto))
        if testo:
            parametri.append('body=' + quote(testo))
        uscita['email'] = 'mailto:%s%s' % (quote(p.email.strip(), safe='@.+'),
                                            ('?' + '&'.join(parametri)) if parametri else '')
    return uscita
