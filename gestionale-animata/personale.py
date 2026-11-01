# -*- coding: utf-8 -*-
"""Turni del personale: medici, infermieri, OSS, tecnici, accettazione, ausiliari.

Tre viste dello stesso planning:
- il mese, il foglio dei turni classico: una riga per persona, una colonna per
  giorno, il codice del turno nella cella (M, P, N, R, F...), i totali in fondo
  alla riga e la copertura del giorno in fondo a ogni gruppo;
- la settimana, con orari e aree, e le ore di ciascuno contro quelle del contratto;
- il giorno, a ore: chi c'e' e quando, con quanti presenti per ruolo ora per ora.

Nelle viste del mese e della settimana i turni si mettono come in un foglio di
calcolo: un clic sulla cella (o la selezione di piu' celle) apre la scelta del
turno; da tastiera si scrive il codice, Canc lo toglie, le frecce si spostano.

Regole (si controllano qui, non nella pagina):
- due turni della stessa persona non si sovrappongono, nemmeno con la notte del
  giorno prima; riposo e assenze valgono tutto il giorno e non stanno insieme
  ad altri turni dello stesso giorno;
- un riposo di meno di 11 ore fra due turni si segnala, ma si puo' tenere;
- la copertura del giorno si confronta con le coperture minime (Tipi di turno):
  dove manca qualcuno, il giorno si colora.

Le ore di un turno sono la sua durata meno la pausa del tipo; una notte conta
nel giorno in cui comincia. I festivi sono le domeniche e le festivita' del
calendario della struttura."""
import re
import threading
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

import calendario
import servizi
from comune import (PRIMA, ULTIMA, data_da, destinazione_sicura, intero, json_sicuro, mese_da, scarica_excel,
                    struttura_scelta)
from modelli import (CATEGORIE_TURNO, ETICHETTA_CATEGORIA, ETICHETTA_RUOLO, ORDINE_RUOLO, RUOLI, CoperturaMinima,
                     Operatore, Persona, TipoTurno, TurnoPersonale, testo_su)

bp = Blueprint('personale', __name__, url_prefix='/personale')
_fornitore = None
_lucchetto = threading.Lock()

RIPOSO_MINIMO = 11 * 60          # minuti fra due turni sotto i quali si segnala un riposo breve
AREE_INIZIALI = ['Ambulatori', 'Degenza', 'Sala operatoria', 'Endoscopia', 'Accettazione']
GIORNI_CORTI = ['L', 'M', 'M', 'G', 'V', 'S', 'D']
GIORNI_NOMI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']
MASSIMO_CELLE = 500              # celle riempite insieme in una volta
MASSIMO_SCHEMA = 120             # giorni di uno schema a rotazione


class ErroreTurno(Exception):
    """Un turno che non si puo' mettere, con il motivo da mostrare."""


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ================================================================ orari
def leggi_ora(testo):
    """'7', '7:30', '07.30', '0730' -> time; None se non e' un'ora."""
    t = (testo or '').strip().replace('.', ':')
    m = re.fullmatch(r'(\d{1,2})(?::?(\d{2}))?', t)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h == 24 and mi == 0:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return time(h, mi)


def intervallo(giorno, ora_inizio, ora_fine):
    """(inizio, fine) di un turno che comincia 'giorno' a ora_inizio: una fine
    non dopo l'inizio cade il giorno dopo (la notte 21-07)."""
    inizio = datetime.combine(giorno, ora_inizio)
    fine = datetime.combine(giorno, ora_fine)
    if fine <= inizio:
        fine += timedelta(days=1)
    return inizio, fine


def testo_ore(minuti):
    """420 -> '7', 450 -> '7:30', 0 -> '0'."""
    minuti = int(round(minuti or 0))
    segno = '-' if minuti < 0 else ''
    h, m = divmod(abs(minuti), 60)
    return '%s%d' % (segno, h) if not m else '%s%d:%02d' % (segno, h, m)


def testo_orario(ora_inizio, ora_fine):
    def corta(t):
        return '%d' % t.hour if not t.minute else '%d:%02d' % (t.hour, t.minute)
    return '%s–%s' % (corta(ora_inizio), corta(ora_fine))


# ================================================================ lettura
def tipi(s, anche_spenti=False):
    q = select(TipoTurno).order_by(TipoTurno.ordine, TipoTurno.id)
    if not anche_spenti:
        q = q.where(TipoTurno.attivo == True)
    return s.scalars(q).all()


def turni_tra(s, dal, al, persone_ids=None):
    """I turni dei giorni dal..al (compresi), con persona e tipo gia' letti."""
    q = (select(TurnoPersonale).options(joinedload(TurnoPersonale.tipo), joinedload(TurnoPersonale.persona))
         .where(TurnoPersonale.giorno >= dal, TurnoPersonale.giorno <= al)
         .order_by(TurnoPersonale.giorno, TurnoPersonale.inizio, TurnoPersonale.id))
    if persone_ids is not None:
        q = q.where(TurnoPersonale.persona_id.in_(list(persone_ids) or [-1]))
    return s.scalars(q).unique().all()


def persone_della_vista(s, st=None, ruolo='', dal=None, al=None):
    """Le persone da mostrare: quelle attive (della struttura o di tutte) e chi,
    anche se non e' piu' attivo, ha turni nel periodo. In ordine di ruolo,
    poi di ordine scelto, poi di cognome."""
    q = select(Persona)
    if st is not None:
        q = q.where(or_(Persona.struttura_id == None, Persona.struttura_id == st.id))
    if ruolo:
        q = q.where(Persona.ruolo == ruolo)
    tutte = s.scalars(q).all()
    con_turni = set()
    if dal is not None and al is not None:
        con_turni = set(s.scalars(select(TurnoPersonale.persona_id).where(
            TurnoPersonale.giorno >= dal, TurnoPersonale.giorno <= al)).all())
    scelte = [p for p in tutte if p.attiva or p.id in con_turni]
    return sorted(scelte, key=lambda p: (ORDINE_RUOLO.get(p.ruolo, 99), p.ordine or 0,
                                         (p.cognome or '').lower(), (p.nome or '').lower(), p.id))


# ================================================================ regole
def conflitti(s, persona_id, giorno, inizio, fine, escludi_ids=()):
    """I turni della persona che non possono stare con uno nuovo in 'giorno'
    (inizio e fine None: riposo o assenza, tutto il giorno)."""
    vicini = s.scalars(select(TurnoPersonale).options(joinedload(TurnoPersonale.tipo)).where(
        TurnoPersonale.persona_id == persona_id,
        TurnoPersonale.giorno >= giorno - timedelta(days=1),
        TurnoPersonale.giorno <= giorno + timedelta(days=1))).all()
    trovati = []
    for t in vicini:
        if t.id in escludi_ids:
            continue
        if t.giorno == giorno and (inizio is None or not t.con_orario):
            trovati.append(t)
        elif inizio is not None and t.con_orario and t.inizio < fine and inizio < t.fine:
            trovati.append(t)
    return trovati


def descrivi(t):
    """'«Notte» il 12/10, 21–7', '«Ferie» il 12/10', 'un turno il 12/10, 8–12'."""
    nome = '«%s»' % t.tipo.nome if t.tipo is not None else 'un turno'
    quando = t.giorno.strftime('%d/%m')
    if t.con_orario:
        return '%s il %s, %s' % (nome, quando, testo_orario(t.inizio.time(), t.fine.time()))
    return '%s il %s' % (nome, quando)


def nell_area(t, area):
    """Il turno va mostrato con il filtro per area? Riposi e assenze sempre."""
    return not area or (t.area or '') == area or t.categoria in ('ASSENZA', 'RIPOSO')


def riposi(s, persona_id, inizio, fine, escludi_ids=()):
    """Minuti di riposo prima e dopo un turno con orario (None se non c'e'
    un turno vicino entro due giorni)."""
    vicini = s.scalars(select(TurnoPersonale).where(
        TurnoPersonale.persona_id == persona_id, TurnoPersonale.inizio != None,
        TurnoPersonale.giorno >= inizio.date() - timedelta(days=2),
        TurnoPersonale.giorno <= fine.date() + timedelta(days=1))).all()
    prima = [inizio - t.fine for t in vicini if t.id not in escludi_ids and t.fine <= inizio]
    dopo = [t.inizio - fine for t in vicini if t.id not in escludi_ids and t.inizio >= fine]
    return (int(min(prima).total_seconds() // 60) if prima else None,
            int(min(dopo).total_seconds() // 60) if dopo else None)


def avvisi_riposo(s, turno):
    prima, dopo = riposi(s, turno.persona_id, turno.inizio, turno.fine, escludi_ids=(turno.id,))
    avvisi = []
    for minuti, dove in ((prima, 'prima'), (dopo, 'dopo')):
        if minuti is not None and minuti < RIPOSO_MINIMO:
            quanto = 'nessun riposo' if minuti <= 0 else 'solo %s ore di riposo' % testo_ore(minuti)
            avvisi.append('%s: %s %s turno del %s.' % (turno.persona.etichetta, quanto,
                                                       'prima del' if dove == 'prima' else 'dopo il',
                                                       turno.giorno.strftime('%d/%m')))
    return avvisi


# ================================================================ scrittura
def _testo_breve(valore, massimo):
    return ' '.join((valore or '').split())[:massimo]


def assegna(s, persona, giorno, tipo=None, ora_inizio=None, ora_fine=None, area='', note='', aggiungi=False,
            adesso=None, area_filtro='', ripristino=False):
    """Mette un turno: di quel tipo (con il suo orario, o con orari scritti a
    mano se il tipo ha un orario e se ne danno altri) oppure, senza tipo, con
    l'orario scritto. Sostituisce i turni della persona in quel giorno, a meno
    di 'aggiungi' (un secondo turno nello stesso giorno, spezzato); con
    'area_filtro' sostituisce solo quelli che si vedono con quel filtro (gli
    altri restano, e un turno nuovo che si sovrappone a loro si rifiuta).
    'ripristino' solo per «Annulla»: rimette un turno com'era anche a chi non
    e' piu' in servizio o con un tipo non piu' in uso (le sovrapposizioni si
    controllano lo stesso).
    Restituisce (turno, avvisi); se non si puo', ErroreTurno con il motivo.
    Non fa commit."""
    if persona is None or (not persona.attiva and not ripristino):
        raise ErroreTurno('Persona non trovata, o non più in servizio.')
    if not isinstance(giorno, date) or not (PRIMA <= giorno <= ULTIMA):
        raise ErroreTurno('Giorno non valido.')
    if tipo is not None and not tipo.attivo and not ripristino:
        raise ErroreTurno('Il tipo di turno %s non è più in uso.' % tipo.codice)
    if tipo is not None and tipo.tutto_il_giorno:
        inizio = fine = None
    else:
        if ora_inizio is None or ora_fine is None:
            if tipo is None:
                raise ErroreTurno('Scrivere l\'orario: inizio e fine.')
            ora_inizio, ora_fine = tipo.ora_inizio, tipo.ora_fine
        if ora_inizio == ora_fine:
            raise ErroreTurno('Inizio e fine sono uguali: scrivere un orario di almeno un quarto d\'ora.')
        inizio, fine = intervallo(giorno, ora_inizio, ora_fine)
    stessi = s.scalars(select(TurnoPersonale).where(TurnoPersonale.persona_id == persona.id,
                                                   TurnoPersonale.giorno == giorno)).all()
    # con il filtro per area la cella mostra solo i turni di quell'area (e riposi e assenze):
    # si sostituisce quello che si vede, mai un turno nascosto di un'altra area
    da_togliere = [] if aggiungi else [t for t in stessi if nell_area(t, area_filtro)]
    contro = conflitti(s, persona.id, giorno, inizio, fine, escludi_ids={t.id for t in da_togliere})
    if contro:
        raise ErroreTurno('%s ha già %s: i due turni non possono stare insieme.' % (
            persona.etichetta, descrivi(contro[0])))
    for t in da_togliere:
        s.delete(t)
    s.flush()
    adesso = adesso or datetime.now()
    nuovo = TurnoPersonale(persona_id=persona.id, persona=persona, giorno=giorno, tipo=tipo,
                           tipo_id=tipo.id if tipo is not None else None, inizio=inizio, fine=fine,
                           area=_testo_breve(area, 60), note=_testo_breve(note, 200),
                           creato_il=adesso, modificato_il=adesso)
    s.add(nuovo)
    s.flush()
    return nuovo, (avvisi_riposo(s, nuovo) if nuovo.con_orario else [])


def togli(s, persona_id, giorno, turno_id=None, area_filtro=''):
    """Toglie i turni della persona in quel giorno (o solo quello indicato);
    con 'area_filtro' solo quelli che si vedono con quel filtro.
    Restituisce quanti. Non fa commit."""
    q = select(TurnoPersonale).where(TurnoPersonale.persona_id == persona_id, TurnoPersonale.giorno == giorno)
    if turno_id:
        q = q.where(TurnoPersonale.id == turno_id)
    tolti = [t for t in s.scalars(q).all() if nell_area(t, area_filtro)]
    for t in tolti:
        s.delete(t)
    s.flush()
    return len(tolti)


def copia_settimana(s, da_lunedi, a_lunedi, persone, sostituisci=False):
    """Copia i turni della settimana da_lunedi nella settimana a_lunedi, per le
    persone indicate, giorno per giorno. Le celle gia' piene restano (a meno di
    'sostituisci'); un turno che non sta (sovrapposto) si salta.
    Restituisce (copiati, saltati)."""
    copiati = saltati = 0
    ids = {p.id for p in persone}
    per_id = {p.id: p for p in persone}
    sorgente = [t for t in turni_tra(s, da_lunedi, da_lunedi + timedelta(days=6), ids)]
    gia = {(t.persona_id, t.giorno) for t in turni_tra(s, a_lunedi, a_lunedi + timedelta(days=6), ids)}
    spostamento = a_lunedi - da_lunedi
    fatti = set()
    for t in sorgente:
        g = t.giorno + spostamento
        chiave = (t.persona_id, g)
        persona = per_id[t.persona_id]
        if not persona.attiva or (chiave in gia and not sostituisci):
            saltati += 1
            continue
        try:
            assegna(s, persona, g, t.tipo,
                    t.inizio.time() if t.con_orario else None, t.fine.time() if t.con_orario else None,
                    t.area or '', t.note or '', aggiungi=chiave in fatti)
        except ErroreTurno:
            saltati += 1
            continue
        fatti.add(chiave)
        copiati += 1
    return copiati, saltati


def leggi_sequenza(testo, per_codice):
    """'M M P P N SN R R' (o con virgole) -> [tipo o None (cella vuota)].
    Un trattino o un punto lasciano il giorno vuoto. ErroreTurno se un codice
    non esiste."""
    pezzi = [x for x in re.split(r'[\s,;]+', (testo or '').strip().upper()) if x]
    if not pezzi:
        raise ErroreTurno('Scrivere la sequenza dei turni, per esempio: M M P P N SN R R.')
    if len(pezzi) > 60:
        raise ErroreTurno('Sequenza troppo lunga: al massimo 60 giorni.')
    sequenza, sconosciuti = [], []
    for x in pezzi:
        if x in ('-', '.', '_'):
            sequenza.append(None)
        elif x in per_codice:
            sequenza.append(per_codice[x])
        else:
            sconosciuti.append(x)
    if sconosciuti:
        raise ErroreTurno('Codici sconosciuti: %s.' % ', '.join(dict.fromkeys(sconosciuti)))
    return sequenza


def applica_schema(s, persone, dal, al, sequenza, sfasamento=0, sostituisci=False):
    """Ripete la sequenza dal..al per ciascuna persona: la prima comincia dal
    primo turno, la seconda 'sfasamento' giorni piu' avanti nella sequenza, e
    cosi' via (le rotazioni dei reparti). Celle gia' piene: restano, a meno di
    'sostituisci'. Restituisce (messi, saltati, motivi dei saltati)."""
    if al < dal:
        raise ErroreTurno('Il periodo finisce prima di cominciare.')
    if (al - dal).days >= MASSIMO_SCHEMA:
        raise ErroreTurno('Periodo troppo lungo: al massimo %d giorni alla volta.' % MASSIMO_SCHEMA)
    if not sequenza:
        raise ErroreTurno('Sequenza vuota.')
    ids = {p.id for p in persone}
    gia = {(t.persona_id, t.giorno) for t in turni_tra(s, dal, al, ids)}
    messi = saltati = 0
    motivi = []
    for i, p in enumerate(persone):
        if not p.attiva:
            continue
        for d in range((al - dal).days + 1):
            g = dal + timedelta(days=d)
            tipo = sequenza[(d + i * sfasamento) % len(sequenza)]
            if tipo is None:
                continue
            if (p.id, g) in gia and not sostituisci:
                saltati += 1
                continue
            try:
                assegna(s, p, g, tipo)
            except ErroreTurno as e:
                saltati += 1
                if len(motivi) < 5:
                    motivi.append(str(e))
                continue
            messi += 1
    return messi, saltati, motivi


# ================================================================ conti
def festivo(g, st=None):
    """Domenica o festivita' (del calendario e del patrono della struttura)."""
    return g.weekday() == 6 or bool(calendario.festivo(g, st.patrono_giorno_mese if st is not None else None))


def totali(turni, st=None):
    """I conti di ciascuna persona sui turni dati: ore di lavoro, ore di
    reperibilita', notti, turni nei festivi, giorni per ogni assenza."""
    conti = defaultdict(lambda: {'lavoro': 0, 'reperibilita': 0, 'notti': 0, 'festivi': 0, 'turni': 0,
                                 'assenze': defaultdict(int), 'riposi': 0})
    for t in turni:
        c = conti[t.persona_id]
        cat = t.categoria
        if cat == 'LAVORO':
            c['lavoro'] += t.minuti
            c['turni'] += 1
            if t.di_notte:
                c['notti'] += 1
            if festivo(t.giorno, st):
                c['festivi'] += 1
        elif cat == 'REPERIBILITA':
            c['reperibilita'] += t.minuti
        elif cat == 'ASSENZA':
            c['assenze'][t.codice] += 1
        else:
            c['riposi'] += 1
    return conti


def contratto(persona, giorni):
    """Minuti del contratto in un periodo di 'giorni' giorni (None se non indicati)."""
    if not persona.minuti_settimana:
        return None
    return persona.minuti_settimana * giorni / 7


def presenti_per_ora(turni, giorno):
    """Per ogni ora del giorno (0..23), le persone al lavoro (turni di lavoro
    che coprono almeno mezz'ora di quell'ora)."""
    ore = [[] for _ in range(24)]
    inizio_giorno = datetime.combine(giorno, time(0, 0))
    for t in turni:
        if t.categoria != 'LAVORO' or not t.con_orario:
            continue
        for h in range(24):
            a = inizio_giorno + timedelta(hours=h)
            b = a + timedelta(hours=1)
            sovrapposto = (min(b, t.fine) - max(a, t.inizio)).total_seconds()
            if sovrapposto >= 1800:
                ore[h].append(t)
    return ore


def copertura(turni_del_giorno, ruolo, regole, g, area=''):
    """(conteggi per codice, carenze) dei turni di lavoro di un ruolo in un
    giorno; le carenze sono le coperture minime non raggiunte."""
    conteggi = defaultdict(int)
    ordine = {}
    for t in turni_del_giorno:
        if t.persona.ruolo == ruolo and t.categoria in ('LAVORO', 'REPERIBILITA'):
            if not area or (t.area or '') == area:
                conteggi[t.codice] += 1
                ordine[t.codice] = t.tipo.ordine if t.tipo is not None else 999
    # nell'ordine dei tipi di turno (M, P, N...), come nella legenda
    conteggi = dict(sorted(conteggi.items(), key=lambda kv: (ordine[kv[0]], kv[0])))
    carenze = []
    for r in regole:
        if r.ruolo != ruolo or not r.vale_il(g):
            continue
        if area and r.area and r.area != area:
            continue
        presenti = sum(1 for t in turni_del_giorno if t.persona.ruolo == ruolo and t.tipo_id == r.tipo_id
                       and (not r.area or (t.area or '') == r.area))
        if presenti < r.minimo:
            carenze.append('%s %s%s: %d su %d' % (ETICHETTA_RUOLO.get(ruolo, ruolo), r.tipo.nome.lower(),
                                                 ' in %s' % r.area.lower() if r.area else '', presenti, r.minimo))
    return conteggi, carenze


# ================================================================ celle
def descrizione(t):
    """'Mattina 7–14, Degenza (cambio con Rossi)': il turno in una riga."""
    testo = (t.tipo.nome if t.tipo is not None else 'Orario scritto a mano') + \
        (' ' + testo_orario(t.inizio.time(), t.fine.time()) if t.con_orario else '')
    if t.area:
        testo += ', ' + t.area
    if t.note:
        testo += ' (%s)' % t.note
    return testo


def cella(turni_cella, avviso=''):
    """Quello che serve alla pagina (e al JavaScript) per disegnare una cella."""
    voci = []
    for t in turni_cella:
        if t.tipo is not None:
            colore = t.tipo.colore_sicuro
            nome = t.tipo.nome
        else:
            colore = '#F1F3F4'
            nome = 'Orario scritto a mano'
        voci.append({
            'id': t.id, 'tipo': t.tipo_id, 'codice': t.codice if t.tipo is not None else '',
            'orario': testo_orario(t.inizio.time(), t.fine.time()) if t.con_orario else '',
            'diverso': bool(t.tipo is not None and t.con_orario and t.tipo.con_orario and
                            (t.inizio.time(), t.fine.time()) != (t.tipo.ora_inizio, t.tipo.ora_fine)),
            'colore': colore, 'testo': testo_su(colore), 'nome': nome, 'categoria': t.categoria,
            'area': t.area or '', 'note': t.note or '', 'ore': testo_ore(t.minuti) if t.con_orario else '',
            'notte': t.di_notte, 'desc': descrizione(t),
        })
    return {'turni': voci, 'avviso': avviso}


def titolo_cella(persona, g, c):
    """Il testo che compare passando sopra la cella e che legge il lettore di schermo."""
    parti = ['%s, %s %d/%d' % (persona.etichetta, GIORNI_NOMI[g.weekday()], g.day, g.month)]
    if not c['turni']:
        parti.append('nessun turno')
    parti.extend(v['desc'] for v in c['turni'])
    if c['avviso']:
        parti.append(c['avviso'])
    return ' · '.join(parti)


def avvisi_celle(turni):
    """{(persona_id, giorno): avviso} per i riposi brevi fra turni consecutivi."""
    per_persona = defaultdict(list)
    for t in turni:
        if t.con_orario:
            per_persona[t.persona_id].append(t)
    avvisi = {}
    for lista in per_persona.values():
        lista.sort(key=lambda t: t.inizio)
        for a, b in zip(lista, lista[1:]):
            pausa = (b.inizio - a.fine).total_seconds() // 60
            if 0 <= pausa < RIPOSO_MINIMO:
                avvisi[(b.persona_id, b.giorno)] = ('nessun riposo prima' if not pausa else
                                                    'riposo di %s ore prima' % testo_ore(pausa))
    return avvisi


# ================================================================ viste
def filtri_della_richiesta():
    ruolo = (request.args.get('ruolo') or '').strip().upper()
    area = ' '.join((request.args.get('area') or '').split())[:60]
    return (ruolo if ruolo in ETICHETTA_RUOLO else ''), area


def griglia(s, st, giorni, ruolo='', area=''):
    """Le righe della vista del mese o della settimana: gruppi per ruolo, con
    persone, celle, totali e copertura del giorno."""
    dal, al = giorni[0], giorni[-1]
    persone = persone_della_vista(s, st, ruolo, dal, al)
    ids = {p.id for p in persone}
    # anche il giorno prima e quello dopo: riposi brevi a cavallo del periodo
    turni = turni_tra(s, dal - timedelta(days=1), al + timedelta(days=1), ids)
    avvisi = avvisi_celle(turni)
    nel_periodo = [t for t in turni if dal <= t.giorno <= al]
    nel_periodo_area = [t for t in nel_periodo if nell_area(t, area)]
    per_cella = defaultdict(list)
    for t in nel_periodo_area:
        per_cella[(t.persona_id, t.giorno)].append(t)
    per_giorno = defaultdict(list)
    for t in nel_periodo:
        per_giorno[t.giorno].append(t)
    conti = totali(nel_periodo, st)
    regole = s.scalars(select(CoperturaMinima).options(joinedload(CoperturaMinima.tipo))).all()
    gruppi = []
    for codice, nome, singolare, icona in RUOLI:
        del_ruolo = [p for p in persone if p.ruolo == codice]
        if not del_ruolo:
            continue
        righe = []
        for p in del_ruolo:
            celle = []
            for g in giorni:
                c = cella(per_cella.get((p.id, g), []), avvisi.get((p.id, g), ''))
                c['titolo'] = titolo_cella(p, g, c)
                celle.append((g, c))
            c = conti.get(p.id)
            previsto = contratto(p, len(giorni))
            righe.append({'persona': p, 'celle': celle, 'conti': c, 'previsto': previsto})
        copertura_giorni = []
        for g in giorni:
            conteggi, carenze = copertura(per_giorno.get(g, []), codice, regole, g, area)
            copertura_giorni.append((g, conteggi, carenze))
        gruppi.append({'ruolo': codice, 'nome': nome, 'icona': icona, 'righe': righe,
                       'copertura': copertura_giorni})
    return gruppi


def info_giorni(giorni, st):
    oggi = date.today()
    return [{'data': g, 'corto': GIORNI_CORTI[g.weekday()], 'nome': GIORNI_NOMI[g.weekday()],
             'festivo': festivo(g, st), 'festa': calendario.festivo(g, st.patrono_giorno_mese if st else None) or '',
             'oggi': g == oggi, 'sabato': g.weekday() == 5} for g in giorni]


def aree_note(s):
    usate = [a for a in s.scalars(select(TurnoPersonale.area).distinct()) if a]
    usate += [a for a in s.scalars(select(CoperturaMinima.area).distinct()) if a]
    return sorted(set(AREE_INIZIALI) | set(usate), key=str.lower)


def dati_tipi(lista):
    """I tipi di turno per il JavaScript della pagina (codici e colori)."""
    return [{'id': t.id, 'codice': t.codice, 'nome': t.nome, 'categoria': t.categoria,
             'orario': testo_orario(t.ora_inizio, t.ora_fine) if t.con_orario else '',
             'inizio': t.ora_inizio.strftime('%H:%M') if t.con_orario else '',
             'fine': t.ora_fine.strftime('%H:%M') if t.con_orario else '',
             'colore': t.colore_sicuro, 'testo': t.colore_testo, 'ore': testo_ore(t.minuti) if t.con_orario else ''}
            for t in lista]


def contesto_comune(s, st, strutture, vista, ruolo, area):
    lista = tipi(s)
    return {'st': st, 'sid': st.id if st else None, 'strutture': strutture, 'vista': vista, 'ruolo': ruolo,
            'area': area, 'tipi': lista, 'tipi_json': dati_tipi(lista), 'aree': aree_note(s),
            'ruoli': RUOLI, 'categorie': CATEGORIE_TURNO, 'etichetta_categoria': ETICHETTA_CATEGORIA,
            'sezione': 'personale', 'testo_ore': testo_ore, 'oggi': date.today(),
            'testi_totali': testi_totali, 'testo_copertura': testo_copertura, 'descrizione': descrizione,
            'nessuno': not s.scalars(select(Persona.id).limit(1)).first()}


@bp.route('/turni')
def turni():
    return redirect(url_for('personale.mese', **_argomenti_filtro()))


def _argomenti_filtro(**altri):
    a = {k: v for k, v in (('struttura', request.args.get('struttura')), ('ruolo', request.args.get('ruolo')),
                           ('area', request.args.get('area'))) if v}
    a.update(altri)
    return a


@bp.route('/turni/mese/')
@bp.route('/turni/mese/<aaaamm>')
def mese(aaaamm=None):
    s = ses()
    st, strutture = struttura_scelta(s)
    primo, ultimo = mese_da(aaaamm)
    giorni = [primo + timedelta(days=i) for i in range((ultimo - primo).days + 1)]
    ruolo, area = filtri_della_richiesta()
    c = contesto_comune(s, st, strutture, 'mese', ruolo, area)
    precedente = (primo - timedelta(days=1)).strftime('%Y-%m')
    successivo = (ultimo + timedelta(days=1)).strftime('%Y-%m')
    return render_template('personale_turni.html', **c, giorni=info_giorni(giorni, st),
                           gruppi=griglia(s, st, giorni, ruolo, area),
                           titolo='Turni di %s %d' % (servizi.MESI[primo.month - 1], primo.year),
                           periodo=primo.strftime('%Y-%m'), dal=primo, al=ultimo,
                           indietro=url_for('personale.mese', aaaamm=precedente, **_argomenti_filtro()),
                           avanti=url_for('personale.mese', aaaamm=successivo, **_argomenti_filtro()),
                           adesso_url=url_for('personale.mese', aaaamm=date.today().strftime('%Y-%m'),
                                              **_argomenti_filtro()))


@bp.route('/turni/settimana/')
@bp.route('/turni/settimana/<iso>')
def settimana(iso=None):
    s = ses()
    st, strutture = struttura_scelta(s)
    lunedi = calendario.lunedi_di(min(max(data_da(iso), PRIMA + timedelta(days=7)), ULTIMA - timedelta(days=7)))
    giorni = [lunedi + timedelta(days=i) for i in range(7)]
    ruolo, area = filtri_della_richiesta()
    c = contesto_comune(s, st, strutture, 'settimana', ruolo, area)
    domenica = giorni[-1]
    if lunedi.month == domenica.month:
        titolo = 'Turni dal %d al %d %s' % (lunedi.day, domenica.day, servizi.MESI[domenica.month - 1])
    else:
        titolo = 'Turni dal %d %s al %d %s' % (lunedi.day, servizi.MESI[lunedi.month - 1], domenica.day,
                                               servizi.MESI[domenica.month - 1])
    return render_template('personale_turni.html', **c, giorni=info_giorni(giorni, st),
                           gruppi=griglia(s, st, giorni, ruolo, area), titolo=titolo,
                           periodo=lunedi.isoformat(), dal=lunedi, al=domenica,
                           indietro=url_for('personale.settimana', iso=(lunedi - timedelta(days=7)).isoformat(),
                                            **_argomenti_filtro()),
                           avanti=url_for('personale.settimana', iso=(lunedi + timedelta(days=7)).isoformat(),
                                          **_argomenti_filtro()),
                           adesso_url=url_for('personale.settimana', iso=date.today().isoformat(),
                                              **_argomenti_filtro()))


def vista_giorno(s, st, g, ruolo='', area=''):
    """Le righe della vista a ore: chi ha un turno quel giorno (anche la notte
    cominciata il giorno prima), con le barre gia' in percentuale della giornata."""
    persone = persone_della_vista(s, st, ruolo, g - timedelta(days=1), g)
    ids = {p.id for p in persone}
    turni = turni_tra(s, g - timedelta(days=1), g, ids)
    inizio_g = datetime.combine(g, time(0, 0))
    fine_g = inizio_g + timedelta(days=1)
    del_giorno = []
    for t in turni:
        if (t.giorno == g or (t.con_orario and t.fine > inizio_g)) and nell_area(t, area):
            del_giorno.append(t)
    # i medici collegati all'agenda: i loro ambulatori di quel giorno
    regole = servizi.Regole(s, g, g)
    agenda = defaultdict(list)
    for t in regole.turni_effettivi(g, st):
        agenda[t.operatore_id].append(t)
    righe_per_ruolo = defaultdict(list)
    for p in persone:
        suoi = [t for t in del_giorno if t.persona_id == p.id]
        ambulatori = agenda.get(p.operatore_id, []) if p.operatore_id else []
        if not suoi and not ambulatori:
            continue
        barre, tutto_il_giorno = [], []
        for t in suoi:
            if not t.con_orario:
                tutto_il_giorno.append(t)
                continue
            a, b = max(t.inizio, inizio_g), min(t.fine, fine_g)
            if b <= a:
                continue
            barre.append({'turno': t, 'sinistra': (a - inizio_g).total_seconds() / 864,
                          'larghezza': (b - a).total_seconds() / 864,
                          'continua_prima': t.inizio < inizio_g, 'continua_dopo': t.fine > fine_g})
        sedute = []
        for t in ambulatori:
            a = datetime.combine(g, t.ora_inizio)
            b = datetime.combine(g, t.ora_fine)
            if b <= a:
                continue
            sedute.append({'turno': t, 'sinistra': (a - inizio_g).total_seconds() / 864,
                           'larghezza': (b - a).total_seconds() / 864})
        righe_per_ruolo[p.ruolo].append({'persona': p, 'barre': barre, 'giorno_intero': tutto_il_giorno,
                                        'ambulatori': sedute, 'turni': [t for t in suoi if t.giorno == g]})
    gruppi = []
    lavoro = [t for t in del_giorno if t.categoria == 'LAVORO']
    regole_cop = s.scalars(select(CoperturaMinima).options(joinedload(CoperturaMinima.tipo))).all()
    for codice, nome, singolare, icona in RUOLI:
        righe = righe_per_ruolo.get(codice)
        if not righe:
            continue
        ore = presenti_per_ora([t for t in lavoro if t.persona.ruolo == codice], g)
        conteggi, carenze = copertura([t for t in del_giorno if t.giorno == g], codice, regole_cop, g, area)
        gruppi.append({'ruolo': codice, 'nome': nome, 'icona': icona, 'righe': righe,
                       'per_ora': [len(x) for x in ore], 'massimo': max([len(x) for x in ore] + [1]),
                       'carenze': carenze})
    return gruppi


@bp.route('/turni/giorno/')
@bp.route('/turni/giorno/<iso>')
def giorno(iso=None):
    s = ses()
    st, strutture = struttura_scelta(s)
    g = data_da(iso)
    ruolo, area = filtri_della_richiesta()
    c = contesto_comune(s, st, strutture, 'giorno', ruolo, area)
    adesso = datetime.now()
    attive = [p for p in persone_della_vista(s, st, ruolo) if p.attiva]
    return render_template('personale_giorno.html', **c, g=g, gruppi=vista_giorno(s, st, g, ruolo, area),
                           persone_attive=attive,
                           giorni=info_giorni([g], st), periodo=g.isoformat(), dal=g, al=g,
                           titolo='Turni di %s' % servizi.etichetta_giorno(g),
                           ora_adesso=(adesso.hour * 60 + adesso.minute) / 14.4 if g == adesso.date() else None,
                           indietro=url_for('personale.giorno', iso=(g - timedelta(days=1)).isoformat(),
                                            **_argomenti_filtro()),
                           avanti=url_for('personale.giorno', iso=(g + timedelta(days=1)).isoformat(),
                                          **_argomenti_filtro()),
                           adesso_url=url_for('personale.giorno', iso=date.today().isoformat(), **_argomenti_filtro()))


# ================================================================ modifiche dalla pagina
def _dati_richiesta():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        dati = request.form.to_dict()
    return dati


def _tipo_da(s, valore):
    if valore in (None, ''):
        return None
    if isinstance(valore, int) or (isinstance(valore, str) and valore.isdigit()):
        t = s.get(TipoTurno, intero(valore))
    else:
        t = s.scalars(select(TipoTurno).where(TipoTurno.codice == str(valore).strip().upper())).first()
    if t is None:
        raise ErroreTurno('Tipo di turno sconosciuto.')
    return t


def _celle_aggiornate(s, st, chiavi, ruolo, area, dal, al):
    """Celle, totali e copertura da ridisegnare dopo una modifica: le celle
    toccate e le vicine (i riposi brevi dipendono dai turni accanto)."""
    persone_ids = {pid for pid, _ in chiavi}
    giorni_toccati = {g for _, g in chiavi}
    if not persone_ids:
        return {'celle': {}, 'totali': {}, 'copertura': {}}
    lo = min(min(giorni_toccati) - timedelta(days=1), dal)
    hi = max(max(giorni_toccati) + timedelta(days=1), al)
    turni = turni_tra(s, lo - timedelta(days=1), hi + timedelta(days=1))
    avvisi = avvisi_celle([t for t in turni if t.persona_id in persone_ids])
    per_cella = defaultdict(list)
    for t in turni:
        if t.persona_id in persone_ids and dal <= t.giorno <= al and nell_area(t, area):
            per_cella[(t.persona_id, t.giorno)].append(t)
    persone = {p.id: p for p in s.scalars(select(Persona).where(Persona.id.in_(persone_ids)))}
    celle = {}
    vicini = set()
    for pid, g in chiavi:
        for d in (-1, 0, 1):
            if dal <= g + timedelta(days=d) <= al:
                vicini.add((pid, g + timedelta(days=d)))
    for pid, g in vicini:
        p = persone.get(pid)
        if p is None:
            continue
        c = cella(per_cella.get((pid, g), []), avvisi.get((pid, g), ''))
        c['titolo'] = titolo_cella(p, g, c)
        celle['%d_%s' % (pid, g.isoformat())] = c
    nel_periodo = [t for t in turni if dal <= t.giorno <= al]
    conti = totali([t for t in nel_periodo if t.persona_id in persone_ids], st)
    giorni = (al - dal).days + 1
    tot = {}
    for pid, p in persone.items():
        c = conti.get(pid)
        tot[str(pid)] = testi_totali(c, contratto(p, giorni))
    regole = s.scalars(select(CoperturaMinima).options(joinedload(CoperturaMinima.tipo))).all()
    cop = {}
    ruoli = {p.ruolo for p in persone.values()}
    # la copertura conta chi si vede nella pagina: con piu' strutture, solo quelli della struttura scelta
    nella_vista = {p.id for p in persone_della_vista(s, st, '', dal, al)}
    for g in giorni_toccati:
        if not (dal <= g <= al):
            continue
        del_giorno = [t for t in nel_periodo if t.giorno == g and t.persona_id in nella_vista]
        for r in ruoli:
            conteggi, carenze = copertura(del_giorno, r, regole, g, area)
            cop['%s_%s' % (r, g.isoformat())] = {'conteggi': conteggi, 'carenze': carenze,
                                                  'testo': testo_copertura(conteggi)}
    return {'celle': celle, 'totali': tot, 'copertura': cop}


def testo_copertura(conteggi):
    """'M2 P2 N1': quanti per turno (conteggi gia' in ordine, da copertura())."""
    return ' '.join('%s%d' % (k, v) for k, v in conteggi.items())


def testi_totali(c, previsto):
    """I totali di una riga, gia' scritti: ore, ore previste, differenza, notti, festivi, assenze."""
    lavoro = c['lavoro'] if c else 0
    assenze = sum(c['assenze'].values()) if c else 0
    return {
        'ore': testo_ore(lavoro), 'previste': testo_ore(previsto) if previsto is not None else '',
        'differenza': (testo_ore(lavoro - previsto) if previsto is not None else ''),
        'segno': ('' if previsto is None else ('sotto' if lavoro < previsto - 59 else
                                               'sopra' if lavoro > previsto + 59 else 'pari')),
        'notti': c['notti'] if c else 0, 'festivi': c['festivi'] if c else 0, 'assenze': assenze,
        'reperibilita': testo_ore(c['reperibilita']) if c and c['reperibilita'] else '',
        'dettaglio_assenze': ', '.join('%s %d' % kv for kv in sorted(c['assenze'].items())) if c else '',
    }


def _periodo_della_richiesta(dati):
    """Il periodo mostrato nella pagina (per i totali); (None, None) se manca o
    non va. Attenzione: data_da() senza data restituisce oggi, qui non serve."""
    def leggi(x):
        try:
            g = datetime.strptime(str(x or ''), '%Y-%m-%d').date()
        except ValueError:
            return None
        return g if PRIMA <= g <= ULTIMA else None
    dal, al = leggi(dati.get('dal')), leggi(dati.get('al'))
    if dal is None or al is None or al < dal or (al - dal).days > 42:
        return None, None
    return dal, al


def specifica(t):
    """Quello che serve per rimettere un turno com'era (per «Annulla»)."""
    return {'tipo': t.tipo_id, 'inizio': t.inizio.strftime('%H:%M') if t.con_orario else '',
            'fine': t.fine.strftime('%H:%M') if t.con_orario else '', 'area': t.area or '', 'note': t.note or ''}


def stato_cella(s, persona_id, giorno):
    """I turni di una cella, come specifiche (in ordine di inizio)."""
    turni = s.scalars(select(TurnoPersonale).where(TurnoPersonale.persona_id == persona_id,
                                                   TurnoPersonale.giorno == giorno)).all()
    turni.sort(key=lambda t: (t.inizio or datetime.combine(t.giorno, time(0, 0)), t.id))
    return [specifica(t) for t in turni]


def _leggi_stato(s, stato, chiavi, celle):
    """Le specifiche mandate dalla pagina per «Annulla», controllate:
    {(persona_id, giorno): [(tipo, inizio, fine, area, note)]}. ErroreTurno se
    qualcosa non torna."""
    letto = {}
    for chiave, x in zip(chiavi, celle):
        lista = stato.get(x)
        if not isinstance(lista, list) or len(lista) > 6:
            raise ErroreTurno('Richiesta non valida.')
        voci = []
        for v in lista:
            if not isinstance(v, dict):
                raise ErroreTurno('Richiesta non valida.')
            tipo = None
            if v.get('tipo') not in (None, '', 0):
                tipo = s.get(TipoTurno, intero(v.get('tipo')))
                if tipo is None:
                    raise ErroreTurno('Un tipo di turno di prima non c\'è più: non si può annullare.')
            ora_inizio = leggi_ora(v.get('inizio')) if v.get('inizio') else None
            ora_fine = leggi_ora(v.get('fine')) if v.get('fine') else None
            if (v.get('inizio') and ora_inizio is None) or (v.get('fine') and ora_fine is None):
                raise ErroreTurno('Richiesta non valida.')
            voci.append((tipo, ora_inizio, ora_fine, str(v.get('area') or ''), str(v.get('note') or '')))
        letto[chiave] = voci
    return letto


@bp.route('/turni/cambia', methods=['POST'])
def cambia():
    """Una o piu' celle della griglia: azione 'metti' (un tipo, o un orario),
    'aggiungi' (un secondo turno), 'togli' (tutto, o un turno), 'ripristina'
    (rimette le celle come erano: «Annulla»). Con il filtro per area della
    pagina ('area_filtro') metti, aggiungi e togli toccano solo i turni che si
    vedono. Risponde con le celle, i totali e la copertura da ridisegnare, gli
    avvisi, gli errori e com'erano prima le celle cambiate, intere (per poter
    annullare)."""
    s = ses()
    dati = _dati_richiesta()
    azione = dati.get('azione') or 'metti'
    stato = None
    if azione == 'ripristina':
        stato = dati.get('stato')
        celle = list(stato.keys()) if isinstance(stato, dict) else []
    else:
        celle = dati.get('celle') or []
        if isinstance(celle, str):
            celle = [x for x in celle.split(',') if x]
    if azione not in ('metti', 'aggiungi', 'togli', 'ripristina') or not isinstance(celle, list) or not celle:
        return json_sicuro({'ok': False, 'errore': 'Richiesta non valida.'}), 400
    if len(celle) > MASSIMO_CELLE:
        return json_sicuro({'ok': False, 'errore': 'Troppe celle insieme: al massimo %d.' % MASSIMO_CELLE}), 400
    chiavi = []
    for x in celle:
        m = re.fullmatch(r'(\d{1,18})_(\d{4}-\d{2}-\d{2})', str(x))
        g = data_da(m.group(2), None) if m else None
        if not m or g is None or m.group(2) != g.isoformat():
            return json_sicuro({'ok': False, 'errore': 'Cella non valida.'}), 400
        chiavi.append((int(m.group(1)), g))
    if len(set(chiavi)) != len(chiavi):
        chiavi_uniche = list(dict.fromkeys(chiavi))
        celle = [celle[chiavi.index(k)] for k in chiavi_uniche]
        chiavi = chiavi_uniche
    dal, al = _periodo_della_richiesta(dati)
    if dal is None:
        dal, al = min(g for _, g in chiavi), max(g for _, g in chiavi)
    st, _ = struttura_scelta(s)
    ruolo = (dati.get('ruolo') or '').upper()
    area = ' '.join(str(dati.get('area_filtro') or '').split())[:60]
    errori, avvisi, prima = [], [], {}
    with _lucchetto:
        try:
            tipo = _tipo_da(s, dati.get('tipo')) if azione in ('metti', 'aggiungi') else None
            ora_inizio = leggi_ora(dati.get('inizio')) if dati.get('inizio') else None
            ora_fine = leggi_ora(dati.get('fine')) if dati.get('fine') else None
            if (dati.get('inizio') and ora_inizio is None) or (dati.get('fine') and ora_fine is None):
                raise ErroreTurno('Orario non valido: per esempio 7:30.')
            if azione in ('metti', 'aggiungi') and tipo is None and (ora_inizio is None or ora_fine is None):
                raise ErroreTurno('Scegliere un turno, o scrivere inizio e fine.')
            voci = _leggi_stato(s, stato, chiavi, celle) if azione == 'ripristina' else None
        except ErroreTurno as e:
            s.rollback()
            return json_sicuro({'ok': False, 'errore': str(e)}), 400
        persone = {p.id: p for p in s.scalars(select(Persona).where(Persona.id.in_({pid for pid, _ in chiavi})))}
        fatti = []
        if azione == 'ripristina':
            # tutto o niente: prima si svuotano tutte le celle (intere, anche con
            # il filtro per area: lo stato di prima e' della cella intera), poi si
            # rimettono i turni di prima (che stavano insieme), cella per cella.
            # 'ripristino': si rimettono anche i turni di chi nel frattempo non e'
            # piu' in servizio o di un tipo non piu' in uso (Canc non li ferma,
            # Annulla nemmeno); una sovrapposizione invece fa rifiutare tutto.
            try:
                for pid, g in chiavi:
                    p = persone.get(pid)
                    if p is None:
                        raise ErroreTurno('Persona non trovata.')
                    prima['%d_%s' % (pid, g.isoformat())] = stato_cella(s, pid, g)
                    togli(s, pid, g)
                for pid, g in chiavi:
                    for i, (t, a, b, ar, no) in enumerate(voci[(pid, g)]):
                        assegna(s, persone[pid], g, t, a, b, ar, no, aggiungi=i > 0, ripristino=True)
                    fatti.append((pid, g))
                s.commit()
            except ErroreTurno as e:
                s.rollback()
                errori.append('Non si può annullare: %s' % e)
                fatti, prima = [], {}
        else:
            area_scritta = str(dati.get('area') or '')
            con_orario = tipo is None or tipo.con_orario
            # dalla tastiera (o su piu' celle) si cambia il turno ma si tiene l'area che c'era
            tieni_area = bool(dati.get('tieni_area')) and azione == 'metti' and not area_scritta.strip() and con_orario
            # con il filtro per area si vede (e si cambia) solo quell'area: un turno nuovo con orario
            # senza un'area scritta va li', cosi' compare nella cella (riposi e assenze restano senza area)
            area_nuovi = area if area and con_orario and not area_scritta.strip() else ''
            for pid, g in chiavi:
                p = persone.get(pid)
                try:
                    if p is None:
                        raise ErroreTurno('Persona non trovata.')
                    # com'era la cella intera, anche i turni nascosti dal filtro: Annulla la rimette tutta
                    com_era = stato_cella(s, pid, g)
                    if azione == 'togli':
                        if not togli(s, pid, g, intero(dati.get('turno')) or None, area_filtro=area):
                            continue
                    else:
                        area_cella = area_scritta
                        if area_nuovi:
                            area_cella = area_nuovi
                        elif tieni_area:
                            area_cella = next((v['area'] for v in com_era if v['area']), '')
                        _, a = assegna(s, p, g, tipo, ora_inizio, ora_fine, area_cella,
                                       str(dati.get('note') or ''), aggiungi=(azione == 'aggiungi'), area_filtro=area)
                        avvisi.extend(a)
                    fatti.append((pid, g))
                    prima['%d_%s' % (pid, g.isoformat())] = com_era
                except ErroreTurno as e:
                    errori.append(str(e))
            s.commit()
    risposta = _celle_aggiornate(s, st, chiavi, ruolo, area, dal, al)
    risposta.update({'ok': not errori, 'fatti': len(fatti), 'errori': list(dict.fromkeys(errori))[:8],
                     'avvisi': list(dict.fromkeys(avvisi))[:8], 'prima': prima})
    return json_sicuro(risposta)


@bp.route('/turni/copia-settimana', methods=['POST'])
def copia():
    s = ses()
    st, _ = struttura_scelta(s)
    lunedi = calendario.lunedi_di(data_da(request.form.get('lunedi')))
    ruolo = (request.form.get('ruolo') or '').upper()
    ruolo = ruolo if ruolo in ETICHETTA_RUOLO else ''
    sostituisci = request.form.get('sostituisci') == '1'
    with _lucchetto:
        persone = persone_della_vista(s, st, ruolo)
        copiati, saltati = copia_settimana(s, lunedi - timedelta(days=7), lunedi, persone, sostituisci)
        s.commit()
    if copiati:
        flash('Copiati %d turni della settimana prima%s.' % (copiati, ', %d già presenti o che non stavano' % saltati
                                                             if saltati else ''), 'ok')
    else:
        flash('Niente da copiare: la settimana prima non ha turni%s.' % (
            ' che si possano mettere (%d saltati)' % saltati if saltati else ''), 'avviso')
    return redirect(url_for('personale.settimana', iso=lunedi.isoformat(), struttura=st.id if st else None,
                            ruolo=ruolo or None))


@bp.route('/turni/schema', methods=['POST'])
def schema():
    s = ses()
    st, _ = struttura_scelta(s)
    f = request.form
    dal = data_da(f.get('dal'))
    al = data_da(f.get('al'), dal)
    ids = [intero(x) for x in f.getlist('persone') if intero(x)]
    sfasamento = max(0, min(intero(f.get('sfasamento'), 0), 60))
    torna = destinazione_sicura(f.get('torna'), url_for('personale.turni'))
    with _lucchetto:
        try:
            if not ids:
                raise ErroreTurno('Scegliere almeno una persona.')
            per_codice = {t.codice: t for t in tipi(s)}
            sequenza = leggi_sequenza(f.get('sequenza'), per_codice)
            persone = [p for p in persone_della_vista(s, st) if p.id in ids]
            persone.sort(key=lambda p: ids.index(p.id))
            messi, saltati, motivi = applica_schema(s, persone, dal, al, sequenza, sfasamento,
                                                    f.get('sostituisci') == '1')
            s.commit()
        except ErroreTurno as e:
            s.rollback()
            flash(str(e), 'errore')
            return redirect(torna)
    flash('Schema applicato: %d turni messi%s.%s' % (
        messi, ', %d celle saltate (già piene o con turni che non stavano)' % saltati if saltati else '',
        (' ' + ' '.join(motivi[:2])) if motivi else ''), 'ok' if messi else 'avviso')
    return redirect(torna)


# ================================================================ persone
def leggi_ore_settimana(testo):
    """Le ore del contratto in minuti: '36' -> 2160, '37:30' e '37,5' -> 2250,
    '37.25' -> 2235; None se vuoto, False se non si legge (o piu' di 80 ore)."""
    t = (testo or '').strip().replace(' ', '')
    if not t:
        return None
    m = re.fullmatch(r'(\d{1,2})(?:([:.,])(\d{1,2}))?', t)
    if not m:
        return False
    ore, segno, resto = int(m.group(1)), m.group(2), m.group(3) or ''
    if segno in ('.', ','):                      # decimali: 37,5 sono 37 ore e mezza
        minuti = ore * 60 + round(int(resto) * 60 / 10 ** len(resto))
    else:
        if resto and int(resto) > 59:
            return False
        minuti = ore * 60 + int(resto or 0)
    return minuti if 0 < minuti <= 80 * 60 else False


def leggi_persona(f):
    """(valori, errori) dal modulo di una persona."""
    errori = []
    cognome = ' '.join((f.get('cognome') or '').split())[:60]
    nome = ' '.join((f.get('nome') or '').split())[:60]
    if not cognome:
        errori.append('Il cognome serve.')
    ruolo = (f.get('ruolo') or '').upper()
    if ruolo not in ETICHETTA_RUOLO:
        errori.append('Scegliere il ruolo.')
    minuti = leggi_ore_settimana(f.get('ore_settimana'))
    if minuti is False:
        errori.append('Ore settimanali: un numero come 36, 37:30 o 37,5.')
        minuti = None
    email = (f.get('email') or '').strip()[:120]
    if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        errori.append('Email non valida.')
    valori = {'cognome': cognome, 'nome': nome, 'ruolo': ruolo, 'minuti_settimana': minuti,
              'qualifica': ' '.join((f.get('qualifica') or '').split())[:60],
              'telefono': ' '.join((f.get('telefono') or '').split())[:30], 'email': email,
              'note': ' '.join((f.get('note') or '').split())[:300],
              'operatore_id': intero(f.get('operatore_id')) or None,
              'struttura_id': intero(f.get('struttura_id')) or None,
              'attiva': f.get('attiva') in ('1', 'on')}
    return valori, errori


@bp.route('/persone')
def persone():
    s = ses()
    st, strutture = struttura_scelta(s)
    tutte = s.scalars(select(Persona)).all()
    tutte.sort(key=lambda p: (not p.attiva, ORDINE_RUOLO.get(p.ruolo, 99), p.ordine or 0, (p.cognome or '').lower()))
    medici_liberi = [o for o in s.scalars(select(Operatore).where(Operatore.attivo == True).order_by(Operatore.cognome))
                     if not any(p.operatore_id == o.id for p in tutte)]
    gruppi = []
    for codice, nome, singolare, icona in RUOLI:
        del_ruolo = [p for p in tutte if p.ruolo == codice]
        if del_ruolo:
            gruppi.append({'ruolo': codice, 'nome': nome, 'icona': icona, 'persone': del_ruolo})
    return render_template('personale_persone.html', gruppi=gruppi, medici_liberi=medici_liberi, ruoli=RUOLI,
                           st=st, sid=st.id if st else None, strutture=strutture, sezione='personale',
                           n_attive=sum(1 for p in tutte if p.attiva))


@bp.route('/persone/nuova', methods=['GET', 'POST'])
@bp.route('/persone/<int:pid>', methods=['GET', 'POST'])
def persona(pid=None):
    s = ses()
    p = s.get(Persona, pid) if pid else None
    if pid and p is None:
        abort(404)
    st, strutture = struttura_scelta(s)
    operatori = s.scalars(select(Operatore).order_by(Operatore.cognome, Operatore.nome)).all()
    if request.method == 'POST':
        if request.form.get('azione') == 'elimina' and p is not None:
            with _lucchetto:
                n = s.scalars(select(TurnoPersonale.id).where(TurnoPersonale.persona_id == p.id)).all()
                if n:
                    flash('%s ha %d turni: non si può eliminare. Si può segnare come non più in servizio '
                          '(togliendo la spunta «In servizio»): resta nei turni passati.' % (p.etichetta, len(n)),
                          'errore')
                    return redirect(url_for('personale.persona', pid=p.id))
                s.delete(p)
                s.commit()
            flash('Persona eliminata.', 'ok')
            return redirect(url_for('personale.persone'))
        valori, errori = leggi_persona(request.form)
        if valori['operatore_id'] and s.get(Operatore, valori['operatore_id']) is None:
            errori.append('Medico dell\'agenda non trovato.')
        if valori['operatore_id']:
            altro = s.scalars(select(Persona).where(Persona.operatore_id == valori['operatore_id'],
                                                    Persona.id != (p.id if p else -1))).first()
            if altro:
                errori.append('Quel medico dell\'agenda è già collegato a %s.' % altro.etichetta)
        if valori['struttura_id'] and not any(x.id == valori['struttura_id'] for x in strutture):
            valori['struttura_id'] = None
        if errori:
            for e in errori:
                flash(e, 'errore')
            return render_template('personale_persona.html', p=p, campi=request.form, operatori=operatori,
                                   ruoli=RUOLI, strutture=strutture, st=st, sid=st.id if st else None,
                                   sezione='personale')
        with _lucchetto:
            nuova = p is None
            if nuova:
                p = Persona()
                s.add(p)
            for k, v in valori.items():
                setattr(p, k, v)
            s.commit()
        flash('%s: %s salvat%s.' % (p.ruolo_etichetta, p.etichetta, 'a' if nuova else 'o'), 'ok')
        if request.form.get('ancora') == '1':
            return redirect(url_for('personale.persona', ruolo=p.ruolo))
        return redirect(url_for('personale.persone'))
    campi = {}
    if p is None:
        campi = {'ruolo': (request.args.get('ruolo') or 'INFERMIERE').upper(), 'attiva': '1'}
    return render_template('personale_persona.html', p=p, campi=campi, operatori=operatori, ruoli=RUOLI,
                           strutture=strutture, st=st, sid=st.id if st else None, sezione='personale')


@bp.route('/persone/medici-dall-agenda', methods=['POST'])
def medici_dall_agenda():
    """Una persona del personale per ogni medico attivo dell'agenda che non ce l'ha."""
    s = ses()
    with _lucchetto:
        collegati = {x for x in s.scalars(select(Persona.operatore_id)) if x}
        nuovi = 0
        for o in s.scalars(select(Operatore).where(Operatore.attivo == True)):
            if o.id in collegati:
                continue
            s.add(Persona(cognome=o.cognome, nome=o.nome or '', ruolo='MEDICO', qualifica=o.specialita or '',
                          telefono=o.telefono or '', email=o.email or '', operatore_id=o.id, attiva=True))
            nuovi += 1
        s.commit()
    flash('Aggiunti %d medici dall\'agenda: ora si possono mettere i loro turni.' % nuovi if nuovi
          else 'Tutti i medici dell\'agenda sono già nel personale.', 'ok' if nuovi else 'avviso')
    return redirect(url_for('personale.persone'))


# ================================================================ tipi di turno e coperture
def leggi_tipo(f, s, tipo=None):
    errori = []
    codice = re.sub(r'\s', '', (f.get('codice') or '')).upper()[:4]
    if not re.fullmatch(r'[A-Z][A-Z0-9]{0,3}', codice):
        errori.append('Codice: da una a quattro lettere o cifre, comincia con una lettera (M, P, N, SN...).')
    else:
        altro = s.scalars(select(TipoTurno).where(TipoTurno.codice == codice,
                                                  TipoTurno.id != (tipo.id if tipo else -1))).first()
        if altro:
            errori.append('Il codice %s è già di «%s».' % (codice, altro.nome))
    nome = ' '.join((f.get('nome') or '').split())[:40]
    if not nome:
        errori.append('Il nome serve.')
    categoria = f.get('categoria') or 'LAVORO'
    if categoria not in ETICHETTA_CATEGORIA:
        errori.append('Categoria non valida.')
    inizio = fine = None
    if categoria in ('LAVORO', 'REPERIBILITA'):
        inizio, fine = leggi_ora(f.get('ora_inizio')), leggi_ora(f.get('ora_fine'))
        if inizio is None or fine is None:
            errori.append('Per un turno di lavoro o di reperibilità servono inizio e fine (per esempio 7:00 e 14:00).')
        elif inizio == fine:
            errori.append('Inizio e fine sono uguali.')
    pausa = intero(f.get('pausa_min'), 0)
    if not (0 <= pausa <= 240):
        errori.append('Pausa: da 0 a 240 minuti.')
    colore = (f.get('colore') or '').strip()
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}', colore):
        colore = '#E8E8EC'
    return {'codice': codice, 'nome': nome, 'categoria': categoria, 'ora_inizio': inizio, 'ora_fine': fine,
            'pausa_min': pausa if categoria in ('LAVORO', 'REPERIBILITA') else 0, 'colore': colore.upper(),
            'attivo': f.get('attivo') in ('1', 'on')}, errori


@bp.route('/tipi', methods=['GET', 'POST'])
def tipi_turno():
    s = ses()
    st, strutture = struttura_scelta(s)
    modifica = s.get(TipoTurno, intero(request.args.get('tipo'))) if request.args.get('tipo') else None
    if request.method == 'POST':
        azione = request.form.get('azione')
        with _lucchetto:
            if azione in ('salva_tipo', 'nuovo_tipo'):
                t = s.get(TipoTurno, intero(request.form.get('id'))) if azione == 'salva_tipo' else None
                if azione == 'salva_tipo' and t is None:
                    abort(404)
                valori, errori = leggi_tipo(request.form, s, t)
                if errori:
                    for e in errori:
                        flash(e, 'errore')
                    return redirect(url_for('personale.tipi_turno', tipo=t.id if t else None) + '#modulo-tipo')
                if t is None:
                    t = TipoTurno(ordine=(max([x.ordine for x in tipi(s, True)] + [0]) + 1))
                    s.add(t)
                for k, v in valori.items():
                    setattr(t, k, v)
                s.commit()
                flash('Tipo di turno %s salvato. I turni già messi tengono il loro orario.' % t.codice, 'ok')
            elif azione == 'elimina_tipo':
                t = s.get(TipoTurno, intero(request.form.get('id')))
                if t is None:
                    abort(404)
                usati = s.scalars(select(TurnoPersonale.id).where(TurnoPersonale.tipo_id == t.id).limit(1)).first()
                regole = s.scalars(select(CoperturaMinima.id).where(CoperturaMinima.tipo_id == t.id).limit(1)).first()
                if usati or regole:
                    t.attivo = False
                    s.commit()
                    flash('%s è usato in turni o coperture: non si elimina, si toglie dall\'elenco dei turni da '
                          'mettere (i turni già messi restano).' % t.codice, 'avviso')
                else:
                    s.delete(t)
                    s.commit()
                    flash('Tipo di turno eliminato.', 'ok')
            elif azione == 'nuova_copertura':
                ruolo = (request.form.get('ruolo') or '').upper()
                tipo = s.get(TipoTurno, intero(request.form.get('tipo_id')))
                minimo = intero(request.form.get('minimo'), 0)
                giorni = ''.join('1' if request.form.get('g%d' % i) else '0' for i in range(7))
                errori = []
                if ruolo not in ETICHETTA_RUOLO:
                    errori.append('Scegliere il ruolo.')
                if tipo is None or not tipo.con_orario:
                    errori.append('Scegliere un turno con orario (le coperture valgono per i turni di lavoro).')
                if not (1 <= minimo <= 50):
                    errori.append('Quante persone: da 1 a 50.')
                if giorni == '0000000':
                    errori.append('Scegliere almeno un giorno.')
                if errori:
                    for e in errori:
                        flash(e, 'errore')
                else:
                    s.add(CoperturaMinima(ruolo=ruolo, tipo_id=tipo.id, minimo=minimo, giorni=giorni,
                                          area=' '.join((request.form.get('area') or '').split())[:60]))
                    s.commit()
                    flash('Copertura minima aggiunta: nei giorni dove manca qualcuno il planning lo segna.', 'ok')
            elif azione == 'elimina_copertura':
                r = s.get(CoperturaMinima, intero(request.form.get('id')))
                if r is not None:
                    s.delete(r)
                    s.commit()
                    flash('Copertura minima tolta.', 'ok')
            else:
                abort(400)
        return redirect(url_for('personale.tipi_turno') + ('#coperture' if 'copertura' in (azione or '') else ''))
    tutte = s.scalars(select(CoperturaMinima).options(joinedload(CoperturaMinima.tipo))).all()
    tutte.sort(key=lambda r: (ORDINE_RUOLO.get(r.ruolo, 99), r.tipo.ordine if r.tipo else 0, r.area or ''))
    return render_template('personale_tipi.html', tipi=tipi(s, True), modifica=modifica, coperture=tutte,
                           ruoli=RUOLI, categorie=CATEGORIE_TURNO, etichetta_ruolo=ETICHETTA_RUOLO,
                           giorni_corti=GIORNI_CORTI, aree=aree_note(s), st=st, sid=st.id if st else None,
                           strutture=strutture, sezione='personale', testo_ore=testo_ore)


# ================================================================ oggi
def in_servizio(s, adesso=None, st=None):
    """Per la pagina Oggi: chi lavora oggi, per ruolo, e chi e' al lavoro adesso."""
    adesso = adesso or datetime.now()
    oggi = adesso.date()
    persone = persone_della_vista(s, st, '', oggi - timedelta(days=1), oggi)
    ids = {p.id for p in persone}
    turni = [t for t in turni_tra(s, oggi - timedelta(days=1), oggi, ids)
             if t.categoria in ('LAVORO', 'REPERIBILITA') and t.con_orario and
             (t.giorno == oggi or t.fine > datetime.combine(oggi, time(0, 0)))]
    gruppi = []
    for codice, nome, singolare, icona in RUOLI:
        suoi = sorted([t for t in turni if t.persona.ruolo == codice], key=lambda t: (t.inizio, t.persona.cognome))
        if suoi:
            gruppi.append({'nome': nome, 'icona': icona,
                           'voci': [{'turno': t, 'adesso': t.inizio <= adesso < t.fine, 'finito': t.fine <= adesso}
                                    for t in suoi]})
    return gruppi


# ================================================================ excel
def esporta_mese(s, st, primo, ultimo, ruolo='', area=''):
    """Il foglio dei turni del mese, come la pagina: colori, totali, legenda;
    e un secondo foglio con un turno per riga (per le paghe)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.properties import PageSetupProperties
    giorni = [primo + timedelta(days=i) for i in range((ultimo - primo).days + 1)]
    gruppi = griglia(s, st, giorni, ruolo, area)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Turni %s' % primo.strftime('%m-%Y')
    blu = '154381'
    sottile = Side(style='thin', color='CFD5D8')
    bordo = Border(left=sottile, right=sottile, top=sottile, bottom=sottile)
    titolo = 'Turni del personale · %s %d' % (servizi.MESI[primo.month - 1], primo.year)
    if st is not None:
        titolo += ' · ' + st.nome
    if ruolo:
        titolo += ' · ' + ETICHETTA_RUOLO[ruolo]
    if area:
        titolo += ' · ' + area
    ws.cell(row=1, column=1, value=titolo).font = Font(bold=True, size=14, color=blu)
    riga = 3
    intestazioni = ['Cognome e nome', 'Qualifica'] + ['%s\n%d' % (GIORNI_CORTI[g.weekday()], g.day) for g in giorni] + \
                   ['Ore', 'Notti', 'Festivi', 'Assenze']
    for i, testo in enumerate(intestazioni, 1):
        c = ws.cell(row=riga, column=i, value=testo)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor=blu)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = bordo
    ws.row_dimensions[riga].height = 30
    for j, g in enumerate(giorni):
        if festivo(g, st):
            ws.cell(row=riga, column=3 + j).fill = PatternFill('solid', fgColor='A8582B')
    riga += 1
    for gr in gruppi:
        c = ws.cell(row=riga, column=1, value=gr['nome'])
        c.font = Font(bold=True, color=blu)
        riga += 1
        for r in gr['righe']:
            p = r['persona']
            ws.cell(row=riga, column=1, value=p.etichetta).border = bordo
            ws.cell(row=riga, column=2, value=p.qualifica or '').border = bordo
            for j, (g, cel) in enumerate(r['celle']):
                c = ws.cell(row=riga, column=3 + j)
                voci = cel['turni']
                if voci:
                    c.value = '/'.join(v['codice'] or v['orario'] for v in voci)
                    colore = voci[0]['colore'].lstrip('#')
                    c.fill = PatternFill('solid', fgColor=colore)
                    c.font = Font(bold=True, color=voci[0]['testo'].lstrip('#'))
                elif festivo(g, st):
                    c.fill = PatternFill('solid', fgColor='F6EDE6')
                c.alignment = Alignment(horizontal='center', vertical='center')
                c.border = bordo
            tt = testi_totali(r['conti'], r['previsto'])
            for k, valore in enumerate((tt['ore'] + (' / ' + tt['previste'] if tt['previste'] else ''),
                                        tt['notti'], tt['festivi'], tt['assenze'])):
                c = ws.cell(row=riga, column=3 + len(giorni) + k, value=valore)
                c.alignment = Alignment(horizontal='center')
                c.border = bordo
            riga += 1
        riga += 1
    ws.cell(row=riga, column=1, value='Legenda').font = Font(bold=True)
    riga += 1
    for t in tipi(s):
        c = ws.cell(row=riga, column=1, value=t.codice)
        c.fill = PatternFill('solid', fgColor=t.colore_sicuro.lstrip('#'))
        c.font = Font(bold=True, color=t.colore_testo.lstrip('#'))
        ws.cell(row=riga, column=2, value='%s%s' % (t.nome, ' ' + t.orario if t.orario else ''))
        riga += 1
    ws.column_dimensions['A'].width = 26
    ws.column_dimensions['B'].width = 16
    for j in range(len(giorni)):
        ws.column_dimensions[get_column_letter(3 + j)].width = 5
    for k in range(4):
        ws.column_dimensions[get_column_letter(3 + len(giorni) + k)].width = 10
    ws.freeze_panes = 'C4'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    # un turno per riga
    el = wb.create_sheet('Elenco')
    teste = ['Data', 'Giorno', 'Cognome e nome', 'Ruolo', 'Codice', 'Turno', 'Inizio', 'Fine', 'Ore', 'Area', 'Note']
    for i, testo in enumerate(teste, 1):
        c = el.cell(row=1, column=i, value=testo)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor=blu)
    ids = {r['persona'].id for gr in gruppi for r in gr['righe']}
    n = 2
    for t in turni_tra(s, primo, ultimo, ids):
        if area and t.con_orario and (t.area or '') != area:
            continue
        el.cell(row=n, column=1, value=t.giorno).number_format = 'DD/MM/YYYY'
        el.cell(row=n, column=2, value=GIORNI_NOMI[t.giorno.weekday()])
        el.cell(row=n, column=3, value=t.persona.etichetta)
        el.cell(row=n, column=4, value=t.persona.ruolo_etichetta)
        el.cell(row=n, column=5, value=t.codice if t.tipo is not None else '')
        el.cell(row=n, column=6, value=t.tipo.nome if t.tipo is not None else 'Orario scritto a mano')
        if t.con_orario:
            el.cell(row=n, column=7, value=t.inizio).number_format = 'DD/MM/YYYY HH:MM'
            el.cell(row=n, column=8, value=t.fine).number_format = 'DD/MM/YYYY HH:MM'
            el.cell(row=n, column=9, value=round(t.minuti / 60, 2))
        el.cell(row=n, column=10, value=t.area or '')
        el.cell(row=n, column=11, value=t.note or '')
        n += 1
    for i, w in enumerate((12, 8, 26, 16, 8, 22, 17, 17, 7, 18, 30), 1):
        el.column_dimensions[get_column_letter(i)].width = w
    el.freeze_panes = 'A2'
    return wb


@bp.route('/turni/mese/<aaaamm>.xlsx')
def mese_excel(aaaamm):
    s = ses()
    st, _ = struttura_scelta(s)
    primo, ultimo = mese_da(aaaamm)
    ruolo, area = filtri_della_richiesta()
    wb = esporta_mese(s, st, primo, ultimo, ruolo, area)
    return scarica_excel(wb, 'turni-%s.xlsx' % primo.strftime('%Y-%m'))
