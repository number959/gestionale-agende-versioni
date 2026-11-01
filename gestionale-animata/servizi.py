# -*- coding: utf-8 -*-
"""Logica applicativa: griglia, turni e assenze, conflitti, viste di
settimana e mese, prima disponibilita', statistiche, export."""
import bisect
import json
import os
from datetime import datetime, date, time, timedelta
from math import gcd

from sqlalchemy import select, func
from modelli import (Struttura, Risorsa, Operatore, Turno, Appuntamento, Modifica,
                     Assenza, Chiusura, Paziente, Prestazione, STATI_ATTIVI,
                     ETICHETTA_TIPO_VISITA, cartella_risorse)
import calendario

PASSO = 30                      # minuti per fascia, se la struttura non dice altro
APERTURA = time(8, 0)
CHIUSURA = time(19, 30)         # inizio dell'ultima fascia
GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì',
          'venerdì', 'sabato', 'domenica']
GIORNI_BREVI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']
MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
        'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']


STANZE_INIZIALI = ['Ambulatorio 1', 'Ambulatorio 2', 'Ambulatorio 3',
                   'Ambulatorio 4', 'Ambulatorio 5', 'Sala endoscopia']
PRESTAZIONI_INIZIALI = [
    ('Prima visita', 30), ('Controllo', 20), ('Ecografia', 20),
    ('EGDS', 30), ('Colonscopia', 45), ('Intervento', 60),
]


NOME_INIZIALE = 'La mia struttura'


def prepara_primo_avvio(ses, nome_struttura=NOME_INIZIALE):
    """Al primo avvio il database e' vuoto: senza stanze la griglia non esiste.

    Crea una struttura con sei stanze e le prestazioni piu' comuni, cosi'
    il programma parte gia' configurato. Nome, logo, medici e turni si
    inseriscono dalla pagina Anagrafiche: la griglia lo segnala
    finche' mancano. Il nome e' volutamente generico: lo stesso installatore
    serve per tutte le sedi.
    """
    if ses.scalars(select(Struttura)).first():
        return None
    st = Struttura(nome=nome_struttura)
    ses.add(st)
    ses.flush()
    for i, nome in enumerate(STANZE_INIZIALI, start=1):
        tipo = 'ENDOSCOPIA' if 'endoscopia' in nome.lower() else 'AMBULATORIO'
        ses.add(Risorsa(nome=nome, tipo=tipo, struttura=st, ordine=i))
    for nome, durata in PRESTAZIONI_INIZIALI:
        if not ses.scalars(select(Prestazione).where(Prestazione.nome == nome)).first():
            ses.add(Prestazione(nome=nome, durata_min=durata))
    ses.commit()
    return st


def dopo_aggiornamento(ses, colonne_aggiunte):
    """Una tantum, nell'avvio in cui il database riceve le colonne del logo.

    Fino alla versione 1.1 il logo della Clinica Posillipo era scritto nel
    programma. Dove quel logo si vedeva, cioe' nelle strutture che si chiamano
    Posillipo, lo si copia nel database: aggiornando, a video non cambia nulla.
    Solo in questo avvio: se poi qualcuno toglie il logo, resta tolto.
    """
    import marchio
    if 'strutture.logo' not in (colonne_aggiunte or []):
        return []
    percorso = os.path.join(cartella_risorse(), 'static', 'logo-posillipo.png')
    if not os.path.exists(percorso):
        return []
    with open(percorso, 'rb') as f:
        logo = marchio.normalizza_logo(f.read())
    aggiornate = []
    for st in ses.scalars(select(Struttura)):
        if 'posillipo' in (st.nome or '').lower() and not st.ha_logo:
            st.logo, st.logo_aggiornato = logo, datetime.now()
            aggiornate.append(st.nome)
    ses.commit()
    return aggiornate


def logo_nuovo(ses, colonne_aggiunte):
    """Una tantum, nell'avvio che porta il database alla 1.5: dove si vede
    ancora il logo precedente della Clinica Posillipo (quello con "Gruppo
    NefroCenter", copiato nel database dalla 1.2) si mette quello nuovo, con
    "Longevity Institute". Un logo diverso, caricato a mano, resta com'e'; una
    struttura senza logo resta senza. Solo in questo avvio."""
    import marchio
    if 'pazienti.indirizzo' not in (colonne_aggiunte or []):
        return []
    cartella = os.path.join(cartella_risorse(), 'static')
    try:
        with open(os.path.join(cartella, 'logo-posillipo-precedente.png'), 'rb') as f:
            vecchio = f.read()
        with open(os.path.join(cartella, 'logo-posillipo.png'), 'rb') as f:
            nuovo = marchio.normalizza_logo(f.read())
    except (OSError, marchio.LogoNonValido):
        return []
    aggiornate = []
    for st in ses.scalars(select(Struttura)):
        if st.ha_logo and marchio.stesso_logo(st.logo, vecchio):
            st.logo, st.logo_aggiornato = nuovo, datetime.now()
            aggiornate.append(st.nome)
    ses.commit()
    return aggiornate


# l'indirizzo da cui la Clinica Posillipo manda le email ai pazienti
EMAIL_POSILLIPO = 'medicinamigliorenapolisrl@gmail.com'


def email_della_struttura(ses, colonne_aggiunte):
    """Una tantum, nell'avvio che porta il database alla 1.5: nelle strutture
    che si chiamano Posillipo e non hanno ancora un'email si scrive quella
    della clinica, che compare nelle stampe e nella firma delle email. Solo
    in questo avvio: se poi qualcuno la cambia o la toglie, resta cosi'."""
    if 'pazienti.indirizzo' not in (colonne_aggiunte or []):
        return []
    aggiornate = []
    for st in ses.scalars(select(Struttura)):
        if 'posillipo' in (st.nome or '').lower() and not (st.email or '').strip():
            st.email = EMAIL_POSILLIPO
            aggiornate.append(st.nome)
    ses.commit()
    return aggiornate


# ================================================================== fasce
def _minuti(t):
    return t.hour * 60 + t.minute


def _allinea(m, passo=PASSO):
    """Arrotonda all'inizio della fascia che contiene il minuto m."""
    return m - (m % passo)


def orario(st):
    """(apertura, inizio dell'ultima fascia, passo) della struttura."""
    if st is None:
        return APERTURA, CHIUSURA, PASSO
    passo = st.passo_min
    da, a = _minuti(st.apertura), _minuti(st.chiusura)
    ultima = max(da, _allinea(a - 1 - da, passo) + da) if a > da else da
    return time(da // 60, da % 60), time(ultima // 60, ultima % 60), passo


def fasce(appuntamenti=None, apertura=APERTURA, ultima=CHIUSURA, passo=PASSO):
    """Gli orari della colonna di sinistra.

    Parte dalla finestra della struttura (08:00-19:30 se non dice altro) e la
    allarga quanto serve se ci sono appuntamenti fuori orario: altrimenti
    sparirebbero dalla vista. Le fasce restano allineate all'apertura.
    """
    base = _minuti(apertura)
    da, a = base, _minuti(ultima)

    def allinea(m):
        return base + ((m - base) // passo) * passo

    for ap in (appuntamenti or []):
        da = min(da, allinea(_minuti(ap.inizio.time())))
        fine = _minuti(ap.fine.time()) if ap.fine.date() == ap.inizio.date() else 24 * 60
        a = max(a, allinea(max(fine - 1, 0)))
    while da < 0:               # si resta allineati all'apertura anche prima di mezzanotte
        da += passo
    a = min(a, allinea(24 * 60 - passo))     # l'ultima fascia finisce entro mezzanotte
    return [time(m // 60, m % 60) for m in range(da, a + passo, passo)]


# ================================================= fasce dei turni (1.10)
# Un turno puo' avere fasce sue (Turno.passo): dall'ora di inizio, ogni tot
# minuti. La griglia allora ha righe piu' fitte, il massimo comun divisore
# fra le fasce della struttura e quelle dei turni (e i loro orari), e ogni
# colonna e' divisa in "pezzi": le fasce dei turni con fasce proprie, e per
# il resto le fasce della struttura come fino alla 1.9 (aperte se un turno
# senza fasce proprie copre il loro inizio). Un appuntamento sta nel pezzo
# dove comincia e blocca i pezzi interi che tocca. Senza turni a fasce
# proprie le righe sono le fasce della struttura e tutto e' come prima.
MINIMA_RIGA = 5


def _ora(m):
    m = max(0, min(int(m), 24 * 60 - 1))
    return time(m // 60, m % 60)


def base_righe(passo, apertura, turni):
    """I minuti di una riga della tabella: il passo della struttura, oppure il
    massimo comun divisore con le fasce dei turni che ne hanno di proprie e
    con i loro orari (contati dall'apertura), cosi' ogni fascia comincia e
    finisce su una riga. Mai meno di 5 minuti."""
    propri = [t for t in turni if t.passo_proprio]
    if not propri:
        return passo
    a = _minuti(apertura)
    b = passo
    for t in propri:
        for x in (t.passo_proprio, _minuti(t.ora_inizio) - a, _minuti(t.ora_fine) - a):
            b = gcd(b, abs(x))
    return max(MINIMA_RIGA, b)


def ultima_riga(ultima, passo, base):
    """L'inizio dell'ultima riga con righe di 'base' minuti: la tabella finisce
    dove finiva con le fasce della struttura."""
    if base == passo:
        return ultima
    return _ora(_minuti(ultima) + passo - base)


def pezzi_colonna(primo, fine, passo, apertura, turni):
    """La colonna divisa in pezzi [inizio, fine, turno] (minuti dalla
    mezzanotte), in ordine e senza buchi da 'primo' a 'fine'. I turni con
    fasce proprie hanno le loro, dall'ora di inizio del turno (l'ultima si
    ferma alla fine del turno); il resto della colonna segue le fasce della
    struttura dall'apertura, con il turno senza fasce proprie che copre il
    loro inizio (aperte) o nessuno (chiuse)."""
    a = _minuti(apertura)
    normali = [t for t in turni if not t.passo_proprio]
    pezzi = []
    s = a + ((primo - a) // passo) * passo
    while s < fine:
        t = next((x for x in normali if _minuti(x.ora_inizio) <= s < _minuti(x.ora_fine)), None)
        pezzi.append([max(s, primo), min(s + passo, fine), t])
        s += passo
    for t in sorted((x for x in turni if x.passo_proprio), key=lambda x: (x.ora_inizio, x.id or 0)):
        ts, te, c = _minuti(t.ora_inizio), _minuti(t.ora_fine), t.passo_proprio
        da, a_ = max(ts, primo), min(te, fine)
        if da >= a_:
            continue
        resto = []
        for p in pezzi:
            if p[1] <= da or p[0] >= a_:
                resto.append(p)
                continue
            if p[0] < da:
                resto.append([p[0], da, p[2]])
            if p[1] > a_:
                resto.append([a_, p[1], p[2]])
        m = ts
        while m < te:
            x0, x1 = max(m, primo), min(m + c, te, fine)
            if x0 < x1:
                resto.append([x0, x1, t])
            m += c
        pezzi = sorted(resto, key=lambda p: p[0])
    return pezzi


def _fine_nel_giorno(a, g):
    return _minuti(a.fine.time()) if a.fine.date() == g else 24 * 60


def celle_colonna(elenco, base, pezzi, appuntamenti, g):
    """Le celle di una colonna, una per riga della tabella, come le usa la
    griglia: 'occupata' (gli appuntamenti che cominciano nel pezzo, 'righe'
    fino alla fine dell'ultimo pezzo che toccano, senza coprire il pezzo di
    un altro appuntamento), 'aperta' (con il turno) o 'chiusa' per un pezzo
    senza appuntamenti, 'coperta' per le righe dentro una cella che comincia
    sopra. 'ora' e' l'inizio del pezzo (della fascia)."""
    n = len(elenco)
    primo = _minuti(elenco[0])
    righe = []                       # (prima riga, riga dopo l'ultima, pezzo)
    prec = 0
    for p in pezzi:
        i0 = max(prec, (p[0] - primo) // base)
        i1 = min(n, -(-(p[1] - primo) // base))
        if i1 > i0:
            righe.append((i0, i1, p))
            prec = i1
    if not righe:
        righe = [(0, n, [primo, primo + n * base, None])]
    elif righe[-1][1] < n:                     # orari strani: l'ultimo pezzo arriva in fondo
        i0, _, p = righe[-1]
        righe[-1] = (i0, n, p)
    inizi = [r[2][0] for r in righe]
    per_pezzo = {}
    for a in sorted(appuntamenti, key=lambda x: x.inizio):
        k = max(0, bisect.bisect_right(inizi, _minuti(a.inizio.time())) - 1)
        per_pezzo.setdefault(k, []).append(a)
    celle = [None] * n
    k = 0
    while k < len(righe):
        i0, i1, p = righe[k]
        lista = per_pezzo.get(k)
        if lista:
            fine_app = max(_fine_nel_giorno(x, g) for x in lista)
            j = k
            while j + 1 < len(righe) and righe[j + 1][2][0] < fine_app and (j + 1) not in per_pezzo:
                j += 1
            fino = righe[j][1]
            celle[i0] = {'stato': 'occupata', 'ora': _ora(p[0]), 'apps': lista, 'righe': fino - i0,
                         'turno': p[2]}
            k = j + 1
        else:
            fino = i1
            celle[i0] = {'stato': 'aperta' if p[2] is not None else 'chiusa', 'ora': _ora(p[0]),
                         'turno': p[2], 'righe': i1 - i0, 'fine': _ora(p[1])}
            k += 1
        for r in range(i0 + 1, fino):
            celle[r] = {'stato': 'coperta', 'ora': elenco[r], 'righe': 1}
    for i in range(n):
        if celle[i] is None:
            celle[i] = {'stato': 'chiusa', 'ora': elenco[i], 'turno': None, 'righe': 1}
    return celle


def blocco(t, inizio, fine):
    """Il tempo che un appuntamento [inizio, fine) occupa nel turno t con
    fasce proprie: dall'inizio della fascia in cui comincia alla fine
    dell'ultima fascia che tocca (dentro il turno; fuori, gli orari veri).
    Senza fasce proprie, gli orari veri."""
    c = t.passo_proprio if t is not None else None
    if not c:
        return inizio, fine
    g = inizio.date()
    ts, te = datetime.combine(g, t.ora_inizio), datetime.combine(g, t.ora_fine)
    passo = timedelta(minutes=c)
    b0 = inizio
    if ts <= inizio < te:
        b0 = ts + ((inizio - ts) // passo) * passo
    b1 = fine
    if ts < fine <= te:
        b1 = min(te, ts + (-((ts - fine) // passo)) * passo)
    return b0, max(b1, fine)


def turno_con_fasce(regole, st, risorsa_id, quando):
    """Il turno a fasce proprie della stanza che copre quel momento, o None."""
    g, ora = quando.date(), quando.time()
    return next((t for t in regole.turni_effettivi(g, st, risorsa_id)
                 if t.passo_proprio and t.ora_inizio <= ora < t.ora_fine), None)


def turno_con_fasce_per(regole, st, risorsa_id, inizio, fine):
    """Il turno a fasce proprie per un appuntamento [inizio, fine): quello che
    copre l'inizio, altrimenti (1.11) il primo che l'appuntamento tocca. Prima
    contava solo l'inizio: un appuntamento cominciato appena prima del turno e
    finito dentro una fascia gia' occupata passava, mentre nell'ordine inverso
    si rifiutava."""
    t = turno_con_fasce(regole, st, risorsa_id, inizio)
    if t is not None:
        return t
    g = inizio.date()
    return next((t for t in regole.turni_effettivi(g, st, risorsa_id)
                 if t.passo_proprio and datetime.combine(g, t.ora_inizio) < fine
                 and datetime.combine(g, t.ora_fine) > inizio), None)


def stanze_attive(ses):
    """1.11: le stanze disattivate non si propongono (prima disponibilita', Sposta,
    agenda del medico): un appuntamento messo li' spariva dalla griglia. I loro
    turni restano, per le statistiche dei mesi passati (Regole non le filtra)."""
    return set(ses.scalars(select(Risorsa.id).where(Risorsa.attiva == True)))


def etichetta_giorno(g):
    return '%s %d %s %d' % (GIORNI[g.weekday()], g.day, MESI[g.month - 1], g.year)


def etichetta_breve(g):
    return '%s %d/%d' % (GIORNI_BREVI[g.weekday()], g.day, g.month)


# ================================================== turni, assenze, chiusure
def turni_del_giorno(ses, g, risorsa_id=None):
    """Turni validi quel giorno, cosi' come sono scritti: senza tenere conto
    di assenze e chiusure (per quelle c'e' Regole)."""
    q = select(Turno)
    if risorsa_id:
        q = q.where(Turno.risorsa_id == risorsa_id)
    return [t for t in ses.scalars(q) if t.vale_il(g)]


def e_di_un_giorno(t):
    return t.valido_a is not None and t.valido_da == t.valido_a


class Regole:
    """Turni, assenze, chiusure e festivita' di un intervallo di date, letti
    dal database una volta sola: la settimana, il mese e le statistiche
    chiedono la stessa cosa per decine di giorni."""

    def __init__(self, ses, dal, al):
        self.turni = ses.scalars(select(Turno)).all()
        self.assenze = ses.scalars(select(Assenza).where(Assenza.al >= dal, Assenza.dal <= al)).all()
        self.chiusure = ses.scalars(select(Chiusura).where(Chiusura.al >= dal, Chiusura.dal <= al)).all()
        self.struttura_di_stanza = dict(ses.execute(select(Risorsa.id, Risorsa.struttura_id)).all())

    def assenze_del(self, g):
        return {a.operatore_id: (a.motivo or 'assente') for a in self.assenze if a.copre(g)}

    def chiusura(self, g, struttura_id):
        return next(((c.motivo or 'chiusura') for c in self.chiusure
                     if c.struttura_id == struttura_id and c.copre(g)), None)

    def giorno(self, g, st):
        festivo = calendario.festivo(g, st.patrono_giorno_mese if st is not None else None)
        chiusura = self.chiusura(g, st.id) if st is not None else None
        return {
            'data': g,
            'festivo': festivo,
            'chiusura': chiusura,
            # i festivi chiudono solo se la struttura lo ha scelto
            'chiude_festivo': bool(festivo and st is not None and st.chiusa_festivi),
            'assenze': self.assenze_del(g),
            'giorno_di_apertura': st is None or g.weekday() in st.giorni_aperti,
        }

    def turni_validi(self, g, st=None, risorsa_id=None):
        uscita = []
        for t in self.turni:
            if not t.vale_il(g):
                continue
            if risorsa_id and t.risorsa_id != risorsa_id:
                continue
            if st is not None and self.struttura_di_stanza.get(t.risorsa_id) != st.id:
                continue
            uscita.append(t)
        return uscita

    def turni_effettivi(self, g, st=None, risorsa_id=None, info=None):
        """I turni che aprono davvero le fasce: medico presente, struttura
        aperta. Nei festivi di una struttura che chiude restano solo i turni
        di un giorno, messi apposta per quella data."""
        info = info or self.giorno(g, st)
        uscita = []
        for t in self.turni_validi(g, st, risorsa_id):
            if t.operatore_id in info['assenze'] or info['chiusura']:
                continue
            if info['chiude_festivo'] and not e_di_un_giorno(t):
                continue
            uscita.append(t)
        return uscita


# ================================================================ griglia
def griglia(ses, g, struttura_id, regole=None):
    """Restituisce le fasce del giorno e, per ogni stanza, la colonna di celle.

    Ogni appuntamento attivo finisce nella fascia che contiene il suo inizio,
    anche se l'orario non e' allineato (10:45) o cade fuori apertura (07:00).
    Se due appuntamenti brevi cadono nella stessa fascia vengono impilati.
    Disdetti e non presentati non occupano la stanza: sono elencati a parte.
    """
    st = ses.get(Struttura, struttura_id) if struttura_id else None
    regole = regole or Regole(ses, g, g)
    info = regole.giorno(g, st)
    risorse = ses.scalars(
        select(Risorsa).where(Risorsa.struttura_id == struttura_id,
                              Risorsa.attiva == True).order_by(Risorsa.ordine)).all()
    inizio_g = datetime.combine(g, time(0, 0))
    appuntamenti = ses.scalars(
        select(Appuntamento).where(Appuntamento.inizio >= inizio_g,
                                   Appuntamento.inizio < inizio_g + timedelta(days=1))
    ).all()
    ids = {r.id for r in risorse}
    del_giorno = [a for a in appuntamenti if a.risorsa_id in ids and a.stato in STATI_ATTIVI]
    annullati = sorted([a for a in appuntamenti if a.risorsa_id in ids and a.stato not in STATI_ATTIVI],
                       key=lambda x: x.inizio)
    apertura, ultima, passo = orario(st)
    effettivi = regole.turni_effettivi(g, st, info=info)
    validi = regole.turni_validi(g, st)
    # con un turno a fasce proprie le righe sono piu' fitte (vedi base_righe)
    base = base_righe(passo, apertura, effettivi)
    elenco = fasce(del_giorno, apertura, ultima_riga(ultima, passo, base), base)
    primo = _minuti(elenco[0])
    fine_tabella = primo + len(elenco) * base

    colonne = []
    for r in risorse:
        app_r = sorted([a for a in del_giorno if a.risorsa_id == r.id],
                       key=lambda x: x.inizio)
        turni_r = [t for t in effettivi if t.risorsa_id == r.id]
        assenti = [(t.operatore, info['assenze'][t.operatore_id]) for t in validi
                   if t.risorsa_id == r.id and t.operatore_id in info['assenze']]
        celle = celle_colonna(elenco, base, pezzi_colonna(primo, fine_tabella, passo, apertura, turni_r),
                              app_r, g)
        colonne.append({'risorsa': r, 'celle': celle, 'turni': turni_r, 'assenti': assenti,
                        'occupate': len(app_r),
                        'libere': sum(1 for c in celle if c['stato'] == 'aperta'),
                        'fasce_proprie': sorted({t.passo_proprio for t in turni_r if t.passo_proprio})})
    return {'fasce': elenco, 'colonne': colonne, 'annullati': annullati, 'giorno': info,
            'struttura': st, 'passo': passo, 'base': base,
            # con un turno a fasce proprie: ogni fascia libera dice la sua ora, righe in proporzione
            'misto': any(t.passo_proprio for t in effettivi),
            'etichette': [((_minuti(f) - _minuti(apertura)) % passo == 0) for f in elenco],
            'altezza_riga': altezza_riga(passo, base, effettivi)}


def altezza_riga(passo, base, turni):
    """I pixel di una riga della griglia: 36 per una fascia della struttura
    (come fino alla 1.9); con fasce piu' brevi in qualche turno, quanto basta
    perche' la fascia piu' breve sia alta almeno 24 pixel."""
    if base == passo:
        return 36
    minima = min([passo] + [t.passo_proprio for t in turni if t.passo_proprio])
    per_minuto = max(36.0 / passo, 24.0 / minima)
    return max(8, int(round(base * per_minuto)))


# ============================================================= controlli
def conflitti(ses, risorsa_id, operatore_id, inizio, fine, escludi_id=None):
    """Restituisce l'elenco dei motivi per cui l'appuntamento non si puo salvare.
    Contano solo gli appuntamenti attivi: un disdetto libera la fascia.

    Dalla 1.10, nei turni con fasce proprie un appuntamento occupa le fasce
    intere che tocca (blocco): nella stessa stanza un altro non ci sta, anche
    se gli orari veri non si toccano. Modificando un appuntamento gia'
    prenotato (escludi_id) non contano le fasce che divideva gia' con un altro
    (orari presi prima che il turno avesse le sue fasce): solo quelle nuove,
    cosi' cambiare una nota o il medico non viene mai rifiutato."""
    motivi = []
    stanza = ses.get(Risorsa, risorsa_id) if risorsa_id else None
    t_fasce = None
    if stanza is not None:
        t_fasce = turno_con_fasce_per(Regole(ses, inizio.date(), inizio.date()), stanza.struttura, risorsa_id,
                                      inizio, fine)
    b0, b1 = blocco(t_fasce, inizio, fine)
    prima = None                     # le fasce che l'appuntamento modificato occupava gia'
    if t_fasce is not None and escludi_id:
        x = ses.get(Appuntamento, escludi_id)
        if x is not None and x.stato in STATI_ATTIVI and x.risorsa_id == risorsa_id:
            prima = blocco(t_fasce, x.inizio, x.fine)
    q = select(Appuntamento).where(Appuntamento.inizio < max(fine, b1),
                                   Appuntamento.fine > min(inizio, b0),
                                   Appuntamento.stato.in_(STATI_ATTIVI))
    if escludi_id:
        q = q.where(Appuntamento.id != escludi_id)
    sovrapposti = ses.scalars(q).all()

    for a in sovrapposti:
        reale = a.inizio < fine and a.fine > inizio
        if a.risorsa_id == risorsa_id:
            if reale:
                motivi.append('La stanza %s è già occupata dalle %s alle %s da %s.'
                              % (a.risorsa.nome, a.inizio.strftime('%H:%M'),
                                 a.fine.strftime('%H:%M'), a.operatore.etichetta))
                continue
            a0, a1 = blocco(t_fasce, a.inizio, a.fine)
            i0, i1 = max(a0, b0), min(a1, b1)          # le fasce che dividerebbero
            # 1.11: si perdonano solo le fasce che divideva gia' (prima), non tutte quelle
            # dell'altro appuntamento: spostarsi in una fascia nuova gia' occupata non passa
            if i0 < i1 and not (prima and prima[0] <= i0 and i1 <= prima[1]):
                nuova = i0 if not prima or i0 < prima[0] else max(i0, prima[1])
                motivi.append('In %s la fascia delle %s è già occupata dall\'appuntamento delle %s-%s di %s: '
                              'nel turno di %s le fasce sono da %d minuti e ogni prestazione occupa fasce intere.'
                              % (a.risorsa.nome, nuova.strftime('%H:%M'), a.inizio.strftime('%H:%M'),
                                 a.fine.strftime('%H:%M'), a.operatore.etichetta, t_fasce.operatore.etichetta,
                                 t_fasce.passo_proprio))
        elif a.operatore_id == operatore_id and reale:
            motivi.append('%s è già in %s dalle %s alle %s.'
                          % (a.operatore.etichetta, a.risorsa.nome,
                             a.inizio.strftime('%H:%M'), a.fine.strftime('%H:%M')))
    return motivi


def fuori_turno(ses, risorsa_id, operatore_id, inizio, fine):
    """Avvisi non bloccanti: medico assente, struttura chiusa, festivo, fascia
    fuori dai turni, orario che non e' l'inizio di una fascia di un turno con
    fasce proprie. None se non c'e' niente da segnalare."""
    stanza = ses.get(Risorsa, risorsa_id)
    st = stanza.struttura if stanza is not None else None
    g = inizio.date()
    regole = Regole(ses, g, g)
    info = regole.giorno(g, st)
    avvisi = []
    if operatore_id in info['assenze']:
        medico = ses.get(Operatore, operatore_id)
        avvisi.append('%s risulta assente il %s (%s).' % (
            medico.etichetta if medico else 'Il medico', g.strftime('%d/%m'), info['assenze'][operatore_id]))
    if info['chiusura']:
        avvisi.append('La struttura risulta chiusa il %s (%s).' % (g.strftime('%d/%m'), info['chiusura']))
    elif info['festivo']:
        avvisi.append('Il %s è festivo: %s.' % (g.strftime('%d/%m'), info['festivo']))
    effettivi = regole.turni_effettivi(g, st, risorsa_id, info=info)
    if operatore_id not in info['assenze'] and not info['chiusura']:
        dentro = any(t.operatore_id == operatore_id and t.ora_inizio <= inizio.time()
                     and fine.time() <= t.ora_fine and fine.date() == g
                     for t in effettivi)
        if not dentro:
            avvisi.append('Fascia fuori dai turni previsti per questa stanza.')
    # le fasce sono della stanza: valgono per chiunque ci prenoti, anche con il medico assente
    t = next((t for t in effettivi if t.passo_proprio and t.ora_inizio <= inizio.time() < t.ora_fine), None)
    if t is not None and (_minuti(inizio.time()) - _minuti(t.ora_inizio)) % t.passo_proprio:
        b0, b1 = blocco(t, inizio, fine)
        avvisi.append('Le fasce di questo turno sono da %d minuti dalle %s: alle %s non ne comincia una, '
                      'l\'appuntamento occupa la fascia intera (%s-%s).' % (
                          t.passo_proprio, t.ora_inizio.strftime('%H:%M'), inizio.strftime('%H:%M'),
                          b0.strftime('%H:%M'), b1.strftime('%H:%M')))
    return ' '.join(avvisi) or None


def registra(ses, entita, entita_id, azione, dettaglio=''):
    ses.add(Modifica(entita=entita, entita_id=entita_id,
                     azione=azione, dettaglio=dettaglio))


# ======================================================== elenco del giorno
def elenco_giorno(ses, g, struttura_id=None, stati=None):
    """Gli appuntamenti del giorno in ordine di ora, di tutte le stanze della
    struttura (di tutte le strutture se None)."""
    inizio = datetime.combine(g, time(0, 0))
    q = (select(Appuntamento).join(Risorsa, Appuntamento.risorsa_id == Risorsa.id)
         .where(Appuntamento.inizio >= inizio, Appuntamento.inizio < inizio + timedelta(days=1)))
    if struttura_id:
        q = q.where(Risorsa.struttura_id == struttura_id)
    if stati:
        q = q.where(Appuntamento.stato.in_(stati))
    return ses.scalars(q.order_by(Appuntamento.inizio, Risorsa.ordine)).all()


def prossimo_giorno_con_appuntamenti(ses, dopo, struttura_id=None, entro=14):
    """Il primo giorno dopo 'dopo' con appuntamenti attivi: il venerdi le
    conferme da fare sono quelle del sabato o del lunedi."""
    for i in range(1, entro + 1):
        g = dopo + timedelta(days=i)
        if elenco_giorno(ses, g, struttura_id, STATI_ATTIVI):
            return g
    return dopo + timedelta(days=1)


# ============================================================== settimana
def settimana(ses, lunedi, struttura_id):
    """Vista per stanza: per ogni stanza e giorno, chi c'e' e quanto e' pieno.
    E' il "planning ambulatori" dei fogli Excel, calcolato."""
    st = ses.get(Struttura, struttura_id) if struttura_id else None
    giorni_tutti = [lunedi + timedelta(days=i) for i in range(7)]
    regole = Regole(ses, giorni_tutti[0], giorni_tutti[-1])
    viste = {g: griglia(ses, g, struttura_id, regole) for g in giorni_tutti}
    aperti = st.giorni_aperti if st is not None else set(range(6))
    # si mostrano i giorni di apertura, piu' quelli in cui c'e' comunque qualcosa
    giorni = [g for g in giorni_tutti
              if g.weekday() in aperti
              or any(c['occupate'] or c['turni'] for c in viste[g]['colonne'])]
    stanze = [c['risorsa'] for c in viste[lunedi]['colonne']]
    righe = []
    for k, r in enumerate(stanze):
        celle = []
        for g in giorni:
            col = viste[g]['colonne'][k]
            celle.append({'data': g, 'turni': col['turni'], 'assenti': col['assenti'],
                          'occupate': col['occupate'], 'libere': col['libere'],
                          'giorno': viste[g]['giorno']})
        righe.append({'risorsa': r, 'celle': celle})
    return {'giorni': giorni, 'righe': righe,
            'info': {g: viste[g]['giorno'] for g in giorni},
            'totali': {g: sum(c['occupate'] for c in viste[g]['colonne']) for g in giorni}}


def settimana_medico(ses, lunedi, operatore_id, struttura_id):
    """Agenda della settimana di un medico, nelle stanze della struttura:
    righe = fasce, colonne = giorni. Come le agende Excel per medico.

    Ogni giorno e' una colonna divisa come quelle della griglia (vedi
    pezzi_colonna): con i turni a fasce proprie le righe sono piu' fitte e una
    fascia occupa piu' righe ('righe'). Ogni cella ha anche le chiavi di prima:
    'apps' (gli appuntamenti che cominciano li'), 'copre' (l'appuntamento
    cominciato sopra che la occupa) e 'turno' (il turno, se la fascia e' libera
    o comincia li' un appuntamento)."""
    st = ses.get(Struttura, struttura_id) if struttura_id else None
    giorni = [lunedi + timedelta(days=i) for i in range(7)]
    regole = Regole(ses, giorni[0], giorni[-1])
    stanze = {r.id: r for r in ses.scalars(select(Risorsa).where(Risorsa.struttura_id == struttura_id))}
    inizio = datetime.combine(giorni[0], time(0, 0))
    apps = [a for a in ses.scalars(select(Appuntamento).where(
        Appuntamento.operatore_id == operatore_id, Appuntamento.inizio >= inizio,
        Appuntamento.inizio < inizio + timedelta(days=7),
        Appuntamento.stato.in_(STATI_ATTIVI))) if a.risorsa_id in stanze]
    apertura, ultima, passo = orario(st)
    attive = stanze_attive(ses)
    turni = {g: [t for t in regole.turni_effettivi(g, st)
                 if t.operatore_id == operatore_id and t.risorsa_id in attive]
             for g in giorni}
    base = base_righe(passo, apertura, [t for g in giorni for t in turni[g]])
    elenco = fasce(apps, apertura, ultima_riga(ultima, passo, base), base)
    primo = _minuti(elenco[0])
    fine_tabella = primo + len(elenco) * base
    info = {g: regole.giorno(g, st) for g in giorni}
    aperti = st.giorni_aperti if st is not None else set(range(6))
    giorni = [g for g in giorni if g.weekday() in aperti or turni[g]
              or any(a.inizio.date() == g for a in apps)]
    colonne = {}
    for g in giorni:
        del_giorno = sorted([a for a in apps if a.inizio.date() == g], key=lambda x: x.inizio)
        colonne[g] = celle_colonna(elenco, base, pezzi_colonna(primo, fine_tabella, passo, apertura, turni[g]),
                                   del_giorno, g)
    righe = []
    for i, f in enumerate(elenco):
        celle = []
        for g in giorni:
            c = colonne[g][i]
            stato = c['stato']
            copre = None
            if stato == 'coperta':
                # dentro un appuntamento cominciato sopra? (risalendo fino alla sua cella)
                k = i - 1
                while k >= 0 and colonne[g][k]['stato'] == 'coperta':
                    k -= 1
                sopra = colonne[g][k] if k >= 0 else None
                if sopra is not None and sopra['stato'] == 'occupata':
                    copre = max(sopra['apps'], key=lambda x: x.fine)
                    turno = None
                else:
                    turno = sopra['turno'] if sopra is not None else None
            else:
                turno = c.get('turno')
            celle.append({'data': g, 'ora': f, 'apps': c['apps'] if stato == 'occupata' else [],
                          'turno': turno, 'copre': copre, 'stato': stato, 'righe': c['righe'],
                          'inizio': c['ora']})
        righe.append({'ora': f, 'celle': celle})
    return {'giorni': giorni, 'righe': righe, 'info': info, 'turni': turni,
            'totale': len(apps), 'passo': passo, 'base': base,
            'misto': any(t.passo_proprio for g in giorni for t in turni[g]),
            'etichette': [((_minuti(f) - _minuti(apertura)) % passo == 0) for f in elenco],
            'altezza_riga': altezza_riga(passo, base, [t for g in giorni for t in turni[g]])}


# ================================================================== mese
def sala_del_mese(ses, st, dal, al, regole, operatore_id=None, oggi=None):
    """{giorno: {'interventi', 'chirurghi': [(medico, quanti)], 'liberi'}} per
    il calendario del mese; vuoto se la struttura non ha sale operatorie.
    'liberi': i chirurghi che di solito operano in quel giorno della
    settimana e non hanno ancora niente (solo da oggi in poi). Con il filtro
    sul medico, solo i suoi."""
    import sala
    if st is None or not sala.ha_sale(ses, st.id):
        return {}
    oggi = oggi or date.today()
    per_giorno = {}
    for a in sala.interventi(ses, dal, al, st.id):
        if not operatore_id or a.operatore_id == operatore_id:
            per_giorno.setdefault(a.inizio.date(), []).append(a)
    chirurghi = [o for o in ses.scalars(select(Operatore).where(Operatore.attivo == True)
                                        .order_by(Operatore.cognome, Operatore.nome))
                 if o.giorni_di_sala and (not operatore_id or o.id == operatore_id)]
    uscita = {}
    g = dal
    while g <= al:
        in_sala = {}
        for a in per_giorno.get(g, []):
            in_sala.setdefault(a.operatore_id, [a.operatore, 0])[1] += 1
        info = regole.giorno(g, st)
        liberi = []
        # solo nei giorni in cui la struttura lavora: di domenica nessuno e' "libero"
        if g >= oggi and g.weekday() in st.giorni_aperti and not info['chiusura'] and not info['chiude_festivo']:
            assenti = info['assenze']
            liberi = [o for o in chirurghi if g.weekday() in o.giorni_di_sala
                      and o.id not in in_sala and o.id not in assenti]
        uscita[g] = {'interventi': len(per_giorno.get(g, [])),
                     'chirurghi': sorted((tuple(x) for x in in_sala.values() if x[0] is not None),
                                         key=lambda x: (x[0].cognome, x[0].nome or '')),
                     'liberi': liberi}
        g += timedelta(days=1)
    return uscita


def mese(ses, anno, numero, struttura_id, operatore_id=None):
    """Calendario del mese: per ogni giorno appuntamenti, medici in sede,
    fasce libere, festivita', chiusure e assenze, e la sala operatoria."""
    st = ses.get(Struttura, struttura_id) if struttura_id else None
    settimane = calendario.settimane_del_mese(anno, numero)
    dal, al = settimane[0][0], settimane[-1][-1]
    regole = Regole(ses, dal, al)
    sale = sala_del_mese(ses, st, dal, al, regole, operatore_id)
    giorni = {}
    for sett in settimane:
        for g in sett:
            v = griglia(ses, g, struttura_id, regole)
            apps = [a for c in v['colonne'] for cella in c['celle'] if cella['stato'] == 'occupata'
                    for a in cella['apps']]
            turni = [t for c in v['colonne'] for t in c['turni']]
            if operatore_id:
                apps = [a for a in apps if a.operatore_id == operatore_id]
                turni = [t for t in turni if t.operatore_id == operatore_id]
                libere = sum(1 for c in v['colonne'] for cella in c['celle']
                             if cella['stato'] == 'aperta' and cella['turno'] is not None
                             and cella['turno'].operatore_id == operatore_id)
            else:
                libere = sum(c['libere'] for c in v['colonne'])
            medici = []
            for t in sorted(turni, key=lambda x: (x.ora_inizio, x.operatore.cognome)):
                if t.operatore not in medici:
                    medici.append(t.operatore)
            info = v['giorno']
            assenti = [ses.get(Operatore, oid) for oid in info['assenze']]
            giorni[g] = {'data': g, 'appuntamenti': len(apps), 'libere': libere,
                         'medici': medici, 'info': info,
                         'assenti': [o for o in assenti if o is not None and
                                     (not operatore_id or o.id == operatore_id)],
                         'del_mese': g.month == numero, 'sala': sale.get(g)}
    return {'settimane': settimane, 'giorni': giorni, 'ci_sono_sale': bool(sale),
            'totale': sum(d['appuntamenti'] for d in giorni.values() if d['del_mese']),
            'interventi': sum(d['sala']['interventi'] for d in giorni.values() if d['del_mese'] and d['sala'])}


# ====================================================== prima disponibilita'
def disponibilita(ses, operatore_id, durata, dal, struttura_id=None, giorni=60, massimo=15,
                  risorsa_id=None, dalle=None, alle=None):
    """I primi posti liberi per un medico: fascia dentro un suo turno
    effettivo, stanza e medico liberi per tutta la durata, mai nel passato.

    Le ore di inizio seguono le fasce del turno, se ne ha di proprie (1.10:
    allora nella stanza contano le fasce intere occupate, vedi blocco),
    altrimenti il passo della struttura a partire dall'inizio del turno.
    dalle/alle limitano l'ora di inizio (mattina, pomeriggio)."""
    trovati = []
    adesso = datetime.now()
    durata = max(5, int(durata or 30))
    strutture = {s.id: s for s in ses.scalars(select(Struttura))}
    regole = Regole(ses, dal, dal + timedelta(days=giorni))
    attive = stanze_attive(ses)
    for n in range(giorni + 1):
        g = dal + timedelta(days=n)
        candidati = []
        for st in strutture.values():
            if struttura_id and st.id != struttura_id:
                continue
            info = regole.giorno(g, st)
            for t in regole.turni_effettivi(g, st, risorsa_id, info=info):
                if t.operatore_id == operatore_id and t.risorsa_id in attive:
                    candidati.append((st, t))
        if not candidati:
            continue
        inizio_g = datetime.combine(g, time(0, 0))
        occupati = ses.scalars(select(Appuntamento).where(
            Appuntamento.inizio < inizio_g + timedelta(days=1),
            Appuntamento.fine > inizio_g,
            Appuntamento.stato.in_(STATI_ATTIVI))).all()
        visti, del_giorno = set(), []
        for st, t in candidati:
            # le fasce del turno (1.10), o il passo della struttura dall'inizio del turno
            passo = t.passo_proprio or st.passo_min
            # nella stanza, con le fasce del turno, contano le fasce intere occupate
            stanza = [blocco(t, a.inizio, a.fine) for a in occupati if a.risorsa_id == t.risorsa_id]
            m = _minuti(t.ora_inizio)
            while m + durata <= _minuti(t.ora_fine):
                inizio = inizio_g + timedelta(minutes=m)
                fine = inizio + timedelta(minutes=durata)
                b0, b1 = blocco(t, inizio, fine)
                ora = inizio.time()
                if (inizio > adesso and (dalle is None or ora >= dalle)
                        and (alle is None or ora < alle)
                        and (inizio, t.risorsa_id) not in visti
                        and not any(x0 < b1 and x1 > b0 for x0, x1 in stanza)
                        and not any(a.inizio < fine and a.fine > inizio and a.operatore_id == operatore_id
                                    for a in occupati)):
                    visti.add((inizio, t.risorsa_id))
                    del_giorno.append({'inizio': inizio, 'fine': fine, 'risorsa': t.risorsa,
                                       'struttura': st})
                m += passo
        # prima tutto il giorno, poi l'ordine: con due turni lo stesso giorno i
        # primi trovati non sono per forza i primi in ordine di ora
        trovati += sorted(del_giorno, key=lambda x: (x['inizio'], x['risorsa'].ordine))
        if len(trovati) >= massimo:
            return trovati[:massimo]
    return sorted(trovati, key=lambda x: (x['inizio'], x['risorsa'].ordine))


# ============================================================ statistiche
def statistiche(ses, struttura_id, dal, al):
    """Numeri del periodo per la struttura: saturazione delle stanze (ore
    prenotate su ore di turno), medici, prestazioni, giorni della settimana."""
    st = ses.get(Struttura, struttura_id) if struttura_id else None
    regole = Regole(ses, dal, al)
    stanze = ses.scalars(select(Risorsa).where(Risorsa.struttura_id == struttura_id)
                         .order_by(Risorsa.ordine)).all()
    ids = {r.id for r in stanze}
    inizio, fine = datetime.combine(dal, time(0, 0)), datetime.combine(al + timedelta(days=1), time(0, 0))
    tutti = [a for a in ses.scalars(select(Appuntamento).where(
        Appuntamento.inizio >= inizio, Appuntamento.inizio < fine)) if a.risorsa_id in ids]
    validi = [a for a in tutti if a.stato in STATI_ATTIVI]
    capacita = {r.id: 0 for r in stanze}          # minuti di turno
    ore_medico = {}
    g = dal
    while g <= al:
        for t in regole.turni_effettivi(g, st):
            if t.risorsa_id in capacita:
                minuti = _minuti(t.ora_fine) - _minuti(t.ora_inizio)
                capacita[t.risorsa_id] += minuti
                ore_medico[t.operatore_id] = ore_medico.get(t.operatore_id, 0) + minuti
        g += timedelta(days=1)

    def minuti_di(a):
        return int((a.fine - a.inizio).total_seconds() // 60)

    per_stanza = []
    for r in stanze:
        prenotati = sum(minuti_di(a) for a in validi if a.risorsa_id == r.id)
        per_stanza.append({'risorsa': r, 'capacita': capacita[r.id], 'prenotati': prenotati,
                           'appuntamenti': sum(1 for a in validi if a.risorsa_id == r.id),
                           'saturazione': (100.0 * prenotati / capacita[r.id]) if capacita[r.id] else None})

    # la percentuale di assenze si calcola sugli appuntamenti gia' avvenuti:
    # quelli futuri non si sa ancora come andranno
    adesso = datetime.now()
    per_medico = {}
    for a in tutti:
        m = per_medico.setdefault(a.operatore_id, {'operatore': a.operatore, 'appuntamenti': 0,
                                                   'minuti': 0, 'disdetti': 0, 'assenti': 0,
                                                   'importo_cent': 0, 'passati': 0})
        if a.stato in STATI_ATTIVI:
            m['appuntamenti'] += 1
            m['minuti'] += minuti_di(a)
            m['importo_cent'] += a.importo_cent or 0
            m['passati'] += a.inizio < adesso
        elif a.stato == 'DISDETTO':
            m['disdetti'] += 1
        elif a.stato == 'NON_PRESENTATO':
            m['assenti'] += 1
    for oid, m in per_medico.items():
        m['turno_minuti'] = ore_medico.get(oid, 0)
        chiusi = m['passati'] + m['assenti']
        m['tasso_assenze'] = (100.0 * m['assenti'] / chiusi) if chiusi else None

    per_prestazione = {}
    for a in validi:
        nome = a.prestazione.nome if a.prestazione else '(senza prestazione)'
        p = per_prestazione.setdefault(nome, {'nome': nome, 'appuntamenti': 0, 'minuti': 0,
                                              'importo_cent': 0})
        p['appuntamenti'] += 1
        p['minuti'] += minuti_di(a)
        p['importo_cent'] += a.importo_cent or 0

    per_tipo = {}
    for a in validi:
        etichetta = ETICHETTA_TIPO_VISITA.get(a.tipo, '') if a.tipo else 'Non indicato'
        per_tipo[etichetta] = per_tipo.get(etichetta, 0) + 1

    per_giorno_settimana = [0] * 7
    for a in validi:
        per_giorno_settimana[a.inizio.weekday()] += 1

    q = select(Paziente).where(Paziente.creato_il >= inizio, Paziente.creato_il < fine)
    if ses.scalar(select(func.count()).select_from(Struttura).where(Struttura.attiva == True)) > 1:
        # i pazienti sono di tutte le sedi: con piu' strutture, sono "nuovi" di
        # questa quelli che hanno un appuntamento nelle sue stanze. Con una sola,
        # tutti, anche chi per ora e' solo in lista d'attesa
        q = q.where(select(Appuntamento.id).where(Appuntamento.paziente_id == Paziente.id,
                                                  Appuntamento.risorsa_id.in_(sorted(ids))).exists())
    nuovi = ses.scalars(q).all()
    pazienti_nuovi = len(nuovi)
    per_provenienza = {}
    for p in nuovi:
        etichetta = p.etichetta_provenienza or 'Non indicata'
        per_provenienza[etichetta] = per_provenienza.get(etichetta, 0) + 1
    inviati = {}
    for p in nuovi:
        if (p.inviato_da or '').strip():
            chiave = ' '.join(p.inviato_da.split())
            inviati[chiave] = inviati.get(chiave, 0) + 1
    incassato = sum(a.pagato_cent or 0 for a in ses.scalars(
        select(Appuntamento).where(Appuntamento.pagato_il >= inizio, Appuntamento.pagato_il < fine))
        if a.risorsa_id in ids)
    assenti = sum(1 for a in tutti if a.stato == 'NON_PRESENTATO')
    avvenuti = sum(1 for a in validi if a.inizio < adesso) + assenti
    return {
        'dal': dal, 'al': al,
        'appuntamenti': len(validi),
        'disdetti': sum(1 for a in tutti if a.stato == 'DISDETTO'),
        'non_presentati': assenti,
        'tasso_assenze': (100.0 * assenti / avvenuti) if avvenuti else None,
        'importo_cent': sum(a.importo_cent or 0 for a in validi),
        'pazienti_nuovi': pazienti_nuovi or 0,
        'per_provenienza': sorted(per_provenienza.items(), key=lambda x: (-x[1], x[0])),
        'inviati': sorted(inviati.items(), key=lambda x: (-x[1], x[0]))[:10],
        'incassato_cent': incassato,
        'capacita': sum(capacita.values()),
        'prenotati': sum(x['prenotati'] for x in per_stanza),
        'per_stanza': per_stanza,
        'per_medico': sorted(per_medico.values(), key=lambda m: (-m['appuntamenti'], m['operatore'].cognome)),
        'per_prestazione': sorted(per_prestazione.values(), key=lambda p: (-p['appuntamenti'], p['nome'])),
        'per_tipo': sorted(per_tipo.items(), key=lambda x: -x[1]),
        'per_giorno_settimana': per_giorno_settimana,
    }


# ------------------------------------------------------------------ export
def esporta_giorno(ses, g, struttura_id, percorso):
    """Esporta la giornata nel formato dei fogli che l'accettazione usa oggi,
    piu' un secondo foglio con l'elenco completo, recapiti compresi."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    sottile = Side(style='thin')
    box = Border(left=sottile, right=sottile, top=sottile, bottom=sottile)
    ciano = PatternFill('solid', fgColor='FF00B0F0')
    verde = PatternFill('solid', fgColor='FFE2EFDA')

    vista = griglia(ses, g, struttura_id)
    colonne, elenco_fasce = vista['colonne'], vista['fasce']
    st = ses.get(Struttura, struttura_id)
    wb = Workbook()
    ws = wb.active
    ws.title = g.strftime('%d-%m-%Y')

    # logo della struttura, dal database; senza logo il titolo va in A1
    colonna_titolo = 1
    if st is not None and st.ha_logo:
        from io import BytesIO
        from openpyxl.drawing.image import Image as ImmagineXL
        im = ImmagineXL(BytesIO(st.logo))
        altezza = 35
        im.width, im.height = round(im.width * altezza / im.height), altezza
        ws.add_image(im, 'A1')
        ws.row_dimensions[1].height = 30
        # il titolo parte dopo il logo: colonna A larga 8, le altre 22 e 26
        larghezze = [8] + [22, 26] * len(colonne)
        spazio, colonna_titolo = 0, 1
        for n, l in enumerate(larghezze, start=1):
            if spazio * 7 >= im.width + 10:
                colonna_titolo = n
                break
            spazio += l
    nome = st.nome if st is not None else ''
    titolo = ('%s - planning del %s' % (nome, etichetta_giorno(g))) if nome else \
        'Planning del %s' % etichetta_giorno(g)
    t = ws.cell(1, colonna_titolo, titolo.upper())
    t.font = Font(name='Calibri', size=14, bold=True)
    if st is not None and st.societa:
        ws.oddFooter.left.text = st.societa
    ws.oddFooter.right.text = 'Pagina &P di &N'

    ws.cell(2, 1, 'ORA').font = Font(bold=True, size=10)
    ws.cell(2, 1).border = box
    for i, col in enumerate(colonne):
        c = 2 + i * 2
        ws.merge_cells(start_row=2, start_column=c, end_row=2, end_column=c + 1)
        h = ws.cell(2, c, col['risorsa'].nome)
        h.font = Font(bold=True, size=10)
        h.fill = ciano
        h.alignment = Alignment(horizontal='center')
        ws.cell(2, c).border = box
        ws.cell(2, c + 1).border = box
        ws.column_dimensions[get_column_letter(c)].width = 22
        ws.column_dimensions[get_column_letter(c + 1)].width = 26
    ws.column_dimensions['A'].width = 8

    for r, f in enumerate(elenco_fasce, start=3):
        o = ws.cell(r, 1, f)
        o.number_format = 'h:mm'
        o.font = Font(bold=True, size=10)
        o.alignment = Alignment(horizontal='center')
        o.border = box
        for i, col in enumerate(colonne):
            cella = col['celle'][r - 3]
            c = 2 + i * 2
            ws.cell(r, c).border = box
            ws.cell(r, c + 1).border = box
            if cella['stato'] == 'occupata':
                righe = [('%s%s' % (a.operatore.etichetta,
                                    '' if a.inizio.time() == cella['ora']
                                    else ' (%s)' % a.inizio.strftime('%H:%M')),
                          '%s%s' % (a.prestazione.nome if a.prestazione else '',
                                    ' - ' + a.paziente.etichetta if a.paziente else ''))
                         for a in cella['apps']]
                m = ws.cell(r, c, '\n'.join(x[0] for x in righe))
                d = ws.cell(r, c + 1, '\n'.join(x[1] for x in righe))
                for x in (m, d):
                    x.fill = verde
                    x.font = Font(size=10)
                    x.alignment = Alignment(horizontal='center', wrap_text=True)
                if cella['righe'] > 1:
                    ws.merge_cells(start_row=r, start_column=c,
                                   end_row=r + cella['righe'] - 1, end_column=c)
                    ws.merge_cells(start_row=r, start_column=c + 1,
                                   end_row=r + cella['righe'] - 1, end_column=c + 1)

    ws.freeze_panes = 'B3'
    ws.page_setup.orientation = 'landscape'
    _foglio_elenco(wb, ses, g, struttura_id, box, ciano)
    wb.active = 0
    wb.save(percorso)
    return percorso


def _foglio_elenco(wb, ses, g, struttura_id, box, ciano):
    """Secondo foglio: una riga per appuntamento, con le colonne delle agende
    Excel dell'accettazione. Anche disdetti e non presentati, con lo stato."""
    from comune import testo_excel        # qui dentro: comune importa questo modulo
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter
    ws = wb.create_sheet('Elenco')
    apps = elenco_giorno(ses, g, struttura_id)
    extra = []
    for a in apps:
        for k in a.valori_extra:
            if k not in extra:
                extra.append(k)
    intestazioni = ['ORA', 'FINE', 'STANZA', 'MEDICO', 'PAZIENTE', 'TELEFONO', 'EMAIL',
                    'PRESTAZIONE', 'TIPO', 'CONVENZIONE / ASSICURAZIONE', 'IMPORTO', 'STATO',
                    'NOTE'] + [e.upper() for e in extra]
    larghezze = [7, 7, 18, 20, 24, 15, 24, 20, 13, 22, 10, 14, 30] + [16] * len(extra)
    for c, (testo, l) in enumerate(zip(intestazioni, larghezze), start=1):
        h = ws.cell(1, c, testo)
        h.font = Font(bold=True, size=10)
        h.fill = ciano
        h.border = box
        h.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = l
    for r, a in enumerate(apps, start=2):
        valori = [a.inizio.time(), a.fine.time(), a.risorsa.nome if a.risorsa else '',
                  a.operatore.etichetta if a.operatore else '',
                  a.paziente.etichetta if a.paziente else '',
                  a.paziente.telefono if a.paziente else '',
                  a.paziente.email if a.paziente else '',
                  a.prestazione.nome if a.prestazione else '', a.etichetta_tipo,
                  a.convenzione or '',
                  (a.importo_cent / 100.0) if a.importo_cent is not None else None,
                  a.etichetta_stato, a.note or ''] + [a.valori_extra.get(e, '') for e in extra]
        for c, v in enumerate(valori, start=1):
            x = ws.cell(r, c, testo_excel(v))
            x.border = box
            x.font = Font(size=10)
            if c in (1, 2):
                x.number_format = 'h:mm'
            elif c == 11:
                x.number_format = '#,##0.00'
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(intestazioni)), max(1, len(apps) + 1))
    ws.page_setup.orientation = 'landscape'
    ws.print_title_rows = '1:1'


# ================================================== stato e spostamenti (1.4)
def imposta_stato(ses, a, nuovo, arrivo='adesso'):
    """Cambia lo stato di un appuntamento, senza salvare. Restituisce i
    motivi per cui non si puo' (vuoto = fatto). Rimettere attivo un
    disdetto e' possibile solo se la fascia e' ancora libera.

    arrivo: 'adesso' registra l'ora di arrivo (allo sportello); None la
    lascia vuota (chiusura di un giorno passato: l'ora vera non si sa)."""
    vecchio = a.stato
    if nuovo == vecchio:
        return []
    if nuovo in STATI_ATTIVI and vecchio not in STATI_ATTIVI:
        motivi = conflitti(ses, a.risorsa_id, a.operatore_id, a.inizio, a.fine, escludi_id=a.id)
        if motivi:
            return motivi
    a.stato = nuovo
    a.stato_il = datetime.now()
    if nuovo == 'ARRIVATO':
        if arrivo == 'adesso':
            a.arrivato_alle = a.arrivato_alle or datetime.now()
    else:
        a.arrivato_alle = None
    registra(ses, 'Appuntamento', a.id, 'STATO', '%s -> %s' % (vecchio, nuovo))
    return []


def sposta(ses, a, inizio, risorsa_id=None, operatore_id=None):
    """Porta l'appuntamento a un'altra data e ora (e stanza o medico), con la
    stessa durata. Restituisce i motivi per cui non si puo' (vuoto = fatto).
    Un appuntamento confermato torna prenotato: la data nuova va confermata."""
    durata = a.fine - a.inizio
    rid = risorsa_id or a.risorsa_id
    oid = operatore_id or a.operatore_id
    fine = inizio + durata
    stanza = ses.get(Risorsa, rid)
    if stanza is None or ses.get(Operatore, oid) is None:
        return ['Stanza o medico non validi.']
    if not stanza.attiva and rid != a.risorsa_id:
        # 1.11: in una stanza disattivata l'appuntamento sparirebbe dalla griglia
        return ['La stanza %s non è più attiva: sceglierne un\'altra.' % stanza.nome]
    motivi = conflitti(ses, rid, oid, inizio, fine, escludi_id=a.id) if a.stato in STATI_ATTIVI else []
    if motivi:
        return motivi
    prima = '%s %s' % (a.inizio.strftime('%d/%m/%Y %H:%M'), a.risorsa.nome if a.risorsa else '')
    a.inizio, a.fine, a.risorsa_id, a.operatore_id = inizio, fine, rid, oid
    if a.stato == 'CONFERMATO':
        a.stato, a.stato_il = 'PRENOTATO', datetime.now()
    registra(ses, 'Appuntamento', a.id, 'SPOSTATO', 'da %s a %s' % (prima, inizio.strftime('%d/%m/%Y %H:%M')))
    return []


def date_serie(inizio, ogni, unita, volte):
    """Le date di una serie di appuntamenti, la prima compresa. Ogni mese:
    stesso giorno del mese, o l'ultimo se il mese e' piu' corto (31 -> 30)."""
    import calendar
    uscita = []
    for k in range(volte):
        if unita == 'giorni':
            uscita.append(inizio + timedelta(days=ogni * k))
        elif unita == 'settimane':
            uscita.append(inizio + timedelta(weeks=ogni * k))
        else:
            mesi = inizio.month - 1 + ogni * k
            anno, mese = inizio.year + mesi // 12, mesi % 12 + 1
            giorno = min(inizio.day, calendar.monthrange(anno, mese)[1])
            uscita.append(inizio.replace(year=anno, month=mese, day=giorno))
    return uscita
