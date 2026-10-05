# -*- coding: utf-8 -*-
"""Codice fiscale delle persone fisiche: controllo, lettura e calcolo.

Com'e' fatto (DM 23/12/1976):

    FNT PRV 80 A 01 F839 W
    |   |   |  | |  |    +- carattere di controllo
    |   |   |  | |  +------ luogo di nascita: codice del comune (il "codice
    |   |   |  | |          catastale") o dello stato estero (Z...)
    |   |   |  | +--------- giorno di nascita; per le donne piu' 40
    |   |   |  +----------- mese: A B C D E H L M P R S T
    |   |   +-------------- ultime due cifre dell'anno
    |   +------------------ nome: consonanti (se sono quattro o piu': la
    |                       prima, la terza e la quarta), poi vocali, poi X
    +---------------------- cognome: consonanti, poi vocali, poi X

Omocodia: quando due persone avrebbero lo stesso codice, l'Agenzia delle
Entrate cambia le cifre in lettere (0=L, 1=M ... 9=V) partendo da destra e
ricalcola il carattere di controllo. Il codice calcolato dai dati e' quindi
quello "di base": quello vero si legge sulla tessera sanitaria, e un codice
omocodico scritto a mano si accetta e si legge come gli altri.

I luoghi (comuni italiani, anche soppressi o rinominati, con il periodo in
cui sono esistiti, e stati esteri) stanno in dati/luoghi_nascita.json,
scritto da strumenti/genera_luoghi_nascita.py. Qui niente Flask e niente
database: lo usano le pagine, le importazioni e l'aggiornamento dello schema.
"""
import json
import os
import re
import sys
import threading
import unicodedata
from datetime import date

VOCALI = 'AEIOU'
MESI = 'ABCDEHLMPRST'
NOMI_MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre',
             'ottobre', 'novembre', 'dicembre']
OMOCODIA = 'LMNPQRSTUV'
POSIZIONI_CIFRE = (6, 7, 9, 10, 12, 13, 14)
PRIMA_NASCITA = date(1900, 1, 1)
_DISPARI = dict(zip('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                    [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21,
                     2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))
_PARI = {c: (int(c) if c.isdigit() else ord(c) - 65) for c in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'}
_CIFRA = '[0-9%s]' % OMOCODIA
FORMA = re.compile(r'[A-Z]{6}%s{2}[%s]%s{2}[A-Z]%s{3}[A-Z]' % (_CIFRA, MESI, _CIFRA, _CIFRA))
# lettere che la scomposizione Unicode non riduce a lettere latine semplici
_SPECIALI = {'ß': 'SS', 'Æ': 'AE', 'æ': 'AE', 'Ø': 'O', 'ø': 'O', 'Œ': 'OE', 'œ': 'OE', 'Ł': 'L', 'ł': 'L',
             'Đ': 'D', 'đ': 'D', 'Þ': 'TH', 'þ': 'TH', 'ı': 'I'}


class DatiMancanti(ValueError):
    """Per calcolare il codice manca qualcosa: .mancano dice cosa."""

    def __init__(self, mancano):
        self.mancano = mancano
        super().__init__('mancano: %s' % ', '.join(mancano))


# =================================================================== forma
def pulisci(testo):
    """Maiuscolo, senza spazi, trattini e punti: com'e' scritto sulla tessera."""
    return re.sub(r'[\s\-.]', '', testo or '').upper()


def carattere_controllo(primi15):
    somma = sum((_DISPARI if i % 2 == 0 else _PARI)[c] for i, c in enumerate(primi15[:15]))
    return chr(ord('A') + somma % 26)


def senza_omocodia(cf):
    """Le lettere al posto delle cifre tornano cifre (il carattere di
    controllo resta quello scritto)."""
    lettere = list(cf)
    for i in POSIZIONI_CIFRE:
        if i < len(lettere) and lettere[i] in OMOCODIA:
            lettere[i] = str(OMOCODIA.index(lettere[i]))
    return ''.join(lettere)


def _data_esiste(anno2, mese, giorno):
    """Il giorno esiste in almeno uno dei due secoli possibili (il 29
    febbraio dell'anno 00 c'e' nel 2000, non nel 1900)."""
    for secolo in (1900, 2000):
        try:
            date(secolo + anno2, mese, giorno)
            return True
        except ValueError:
            continue
    return False


def difetto(cf):
    """Perche' il codice non e' valido, in parole semplici; '' se e' valido.
    Il codice va gia' pulito (pulisci)."""
    if not cf:
        return 'Il codice fiscale è vuoto.'
    if not re.fullmatch(r'[A-Z0-9]*', cf):
        return 'Il codice fiscale contiene caratteri che non vanno: solo lettere e cifre.'
    if len(cf) != 16:
        return 'Il codice fiscale ha %d caratter%s: ne servono 16.' % (len(cf), 'e' if len(cf) == 1 else 'i')
    if not re.fullmatch(r'[A-Z]{6}', cf[:6]):
        return 'I primi sei caratteri devono essere lettere (cognome e nome).'
    if not re.fullmatch(_CIFRA + '{2}', cf[6:8]):
        return 'Al 7° e all\'8° posto va l\'anno di nascita, due cifre: c\'è «%s».' % cf[6:8]
    if cf[8] not in MESI:
        return 'Al 9° posto va la lettera del mese (A B C D E H L M P R S T): c\'è «%s».' % cf[8]
    if not re.fullmatch(_CIFRA + '{2}', cf[9:11]):
        return 'Al 10° e all\'11° posto va il giorno di nascita, due cifre: c\'è «%s».' % cf[9:11]
    if not re.fullmatch('[A-Z]' + _CIFRA + '{3}', cf[11:15]):
        return 'Dal 12° al 15° posto va il codice del luogo di nascita, una lettera e tre cifre: c\'è «%s».' % cf[11:15]
    if not cf[15].isalpha():
        return 'L\'ultimo carattere deve essere una lettera.'
    base = senza_omocodia(cf)
    anno2, mese, giorno = int(base[6:8]), MESI.index(base[8]) + 1, int(base[9:11])
    if giorno > 40:
        giorno -= 40
    if not 1 <= giorno <= 31:
        return 'Il giorno di nascita «%s» non esiste: va da 01 a 31 (da 41 a 71 per le donne).' % base[9:11]
    if not _data_esiste(anno2, mese, giorno):
        return 'La data di nascita del codice, %d %s, non esiste.' % (giorno, NOMI_MESI[mese - 1])
    giusto = carattere_controllo(cf)
    if cf[15] != giusto:
        return ('Il carattere di controllo (l\'ultimo) non torna: con questi caratteri sarebbe «%s». Di solito '
                'vuol dire che una lettera o una cifra è stata scritta male.' % giusto)
    return ''


def valido(cf):
    """Forma, data esistente e carattere di controllo."""
    cf = pulisci(cf)
    return bool(cf) and not difetto(cf)


# ================================================================= lettura
def nascita(cf, oggi=None):
    """La data di nascita scritta nel codice valido, None altrimenti. Il
    secolo non c'e': si sceglie la data piu' recente che non sia nel futuro
    (un 25 e' il 2025 per un bambino gia' nato, altrimenti il 1925)."""
    cf = pulisci(cf)
    if not valido(cf):
        return None
    base = senza_omocodia(cf)
    anno2, mese, giorno = int(base[6:8]), MESI.index(base[8]) + 1, int(base[9:11])
    if giorno > 40:
        giorno -= 40
    oggi = oggi or date.today()
    for secolo in (2000, 1900):
        try:
            d = date(secolo + anno2, mese, giorno)
        except ValueError:
            continue
        if d <= oggi:
            return d if d >= PRIMA_NASCITA else None
    return None


def leggi(cf, oggi=None):
    """Cosa dice un codice valido: {'sesso', 'data_nascita', 'luogo',
    'luogo_testo', 'omocodico'}; None se non e' valido. luogo_testo e'
    vuoto se il codice del luogo non e' fra quelli conosciuti."""
    cf = pulisci(cf)
    if not valido(cf):
        return None
    base = senza_omocodia(cf)
    d = nascita(cf, oggi)
    luogo = base[11:15]
    return {'sesso': 'F' if int(base[9:11]) > 40 else 'M', 'data_nascita': d, 'luogo': luogo,
            'luogo_testo': testo_luogo(luogo, d), 'omocodico': base[:15] != cf[:15]}


# ================================================================= calcolo
def lettere(testo):
    """Le sole lettere, maiuscole e senza accenti: «D'Angelo» -> DANGELO."""
    t = ''.join(_SPECIALI.get(c, c) for c in testo or '')
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c)).upper()
    return re.sub(r'[^A-Z]', '', t)


def lettere_cognome(cognome):
    t = lettere(cognome)
    consonanti = [c for c in t if c not in VOCALI]
    vocali = [c for c in t if c in VOCALI]
    return (''.join(consonanti + vocali) + 'XXX')[:3]


def lettere_nome(nome):
    t = lettere(nome)
    consonanti = [c for c in t if c not in VOCALI]
    vocali = [c for c in t if c in VOCALI]
    if len(consonanti) >= 4:
        consonanti = [consonanti[0], consonanti[2], consonanti[3]]
    return (''.join(consonanti + vocali) + 'XXX')[:3]


def calcola(cognome, nome, data_nascita, sesso, luogo):
    """Il codice di base dai dati (vedi in cima: con l'omocodia quello vero
    puo' essere diverso). DatiMancanti se manca qualcosa."""
    mancano = []
    if not lettere(cognome):
        mancano.append('cognome')
    if not lettere(nome):
        mancano.append('nome')
    if sesso not in ('M', 'F'):
        mancano.append('sesso')
    if not isinstance(data_nascita, date):
        mancano.append('data di nascita')
    luogo = (luogo or '').strip().upper()
    if not re.fullmatch(r'[A-Z][0-9]{3}', luogo):
        mancano.append('luogo di nascita')
    if mancano:
        raise DatiMancanti(mancano)
    primi = (lettere_cognome(cognome) + lettere_nome(nome) + '%02d' % (data_nascita.year % 100)
             + MESI[data_nascita.month - 1] + '%02d' % (data_nascita.day + (40 if sesso == 'F' else 0)) + luogo)
    return primi + carattere_controllo(primi)


# ================================================================ confronto
def _giorno(d):
    return '%02d/%02d/%04d' % (d.day, d.month, d.year)


def confronta(cf, cognome='', nome='', data_nascita=None, sesso='', luogo=''):
    """Gli avvisi se il codice valido non corrisponde ai dati scritti (solo
    quelli scritti). Non sono errori: puo' essere sbagliato il codice o il
    dato, e qualche codice assegnato in passato non segue le regole."""
    cf = pulisci(cf)
    if not valido(cf):
        return []
    avvisi = []
    if lettere(cognome) and lettere_cognome(cognome) != cf[:3]:
        avvisi.append('Le lettere del cognome non tornano: per «%s» sarebbero %s, nel codice fiscale c\'è %s.'
                      % (cognome.strip(), lettere_cognome(cognome), cf[:3]))
    if lettere(nome) and lettere_nome(nome) != cf[3:6]:
        avvisi.append('Le lettere del nome non tornano: per «%s» sarebbero %s, nel codice fiscale c\'è %s.'
                      % (nome.strip(), lettere_nome(nome), cf[3:6]))
    dal_cf = leggi(cf)
    if isinstance(data_nascita, date) and dal_cf['data_nascita'] and (
            data_nascita.day, data_nascita.month, data_nascita.year % 100) != (
            dal_cf['data_nascita'].day, dal_cf['data_nascita'].month, dal_cf['data_nascita'].year % 100):
        avvisi.append('La data di nascita (%s) non corrisponde a quella del codice fiscale (%s).'
                      % (_giorno(data_nascita), _giorno(dal_cf['data_nascita'])))
    if sesso in ('M', 'F') and sesso != dal_cf['sesso']:
        avvisi.append('Il sesso (%s) non corrisponde a quello del codice fiscale (%s).' % (sesso, dal_cf['sesso']))
    luogo = (luogo or '').strip().upper()
    if luogo and luogo != dal_cf['luogo']:
        avvisi.append('Il luogo di nascita (%s) non corrisponde a quello del codice fiscale (%s).' % (
            testo_luogo(luogo, data_nascita) or luogo, dal_cf['luogo_testo'] or dal_cf['luogo']))
    return avvisi


# ================================================================== luoghi
_tabella = None
_per_codice = None
_carica = threading.Lock()


def _percorso_dati():
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'dati', 'luoghi_nascita.json')


def chiave(testo):
    """Per cercare: minuscolo, senza accenti, apostrofi, spazi e trattini."""
    t = unicodedata.normalize('NFKD', testo or '')
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", '', t)


def parole_chiave(testo):
    """Le parole, ognuna come chiave: "Sant'Agata de' Goti" -> ['sant', 'agata', 'de', 'goti']."""
    return [k for k in (chiave(p) for p in re.split(r"[\s'’`\-.,()/]+", testo or '')) if k]


class Luogo:
    __slots__ = ('codice', 'nome', 'provincia', 'dal', 'al', 'altro', 'chiave', 'chiave_altro', 'parole',
                 'parole_altro')

    def __init__(self, riga):
        self.codice, self.nome, self.provincia, dal, al = riga[:5]
        self.dal = date.fromisoformat(dal) if dal else None
        self.al = date.fromisoformat(al) if al else None
        self.altro = riga[5] if len(riga) > 5 else ''
        self.chiave, self.chiave_altro = chiave(self.nome), chiave(self.altro)
        self.parole, self.parole_altro = parole_chiave(self.nome), parole_chiave(self.altro)

    @property
    def estero(self):
        return self.provincia == 'EE'

    @property
    def esiste(self):
        return self.al is None

    def valido_il(self, giorno):
        return (self.dal is None or self.dal <= giorno) and (self.al is None or giorno <= self.al)

    @property
    def testo(self):
        """Come si scrive nel campo: 'Napoli (NA)', 'Germania (estero)'."""
        return '%s (%s)' % (self.nome, 'estero' if self.estero else self.provincia)

    @property
    def periodo(self):
        """Per i luoghi che non esistono piu', o nati da poco: 'fino al 1924', 'dal 2014'."""
        if self.al is not None:
            return 'fino al %d' % self.al.year
        if self.dal is not None and self.dal.year >= 1990 and not self.estero:
            return 'dal %d' % self.dal.year
        return ''

    def come_dizionario(self):
        return {'codice': self.codice, 'testo': self.testo, 'nome': self.nome, 'provincia': self.provincia,
                'estero': self.estero, 'periodo': self.periodo}


def tabella():
    """I luoghi, letti una volta sola (circa 15 mila righe)."""
    global _tabella, _per_codice
    if _tabella is None:
        with _carica:
            if _tabella is None:
                with open(_percorso_dati(), encoding='utf-8') as f:
                    righe = json.load(f)['luoghi']
                luoghi = [Luogo(r) for r in righe]
                per_codice = {}
                for x in luoghi:
                    per_codice.setdefault(x.codice, []).append(x)
                _per_codice = per_codice
                _tabella = luoghi
    return _tabella


def luoghi_del_codice(codice):
    tabella()
    return _per_codice.get((codice or '').strip().upper(), [])


def luogo(codice, giorno=None):
    """Il luogo con quel codice com'era il giorno indicato (nome e provincia
    possono essere cambiati), altrimenti com'e' oggi o com'era per ultimo.
    None se il codice non c'e'."""
    righe = luoghi_del_codice(codice)
    if not righe:
        return None
    if isinstance(giorno, date):
        for x in righe:
            if x.valido_il(giorno):
                return x
    attuale = [x for x in righe if x.esiste]
    return attuale[0] if attuale else max(righe, key=lambda x: x.al)


def testo_luogo(codice, giorno=None):
    x = luogo(codice, giorno)
    return x.testo if x else ''


def codice_conosciuto(codice):
    return bool(luoghi_del_codice(codice))


def avviso_periodo(codice, giorno):
    """Un comune nato dopo la data di nascita, o soppresso prima: per chi e'
    nato allora il codice e' un altro. '' se va bene o non si sa."""
    righe = luoghi_del_codice(codice)
    if not righe or not isinstance(giorno, date) or any(x.valido_il(giorno) for x in righe):
        return ''
    x = luogo(codice)
    if x.dal and giorno < x.dal:
        return ('%s esiste dal %s: per chi è nato prima va scelto il comune di allora.'
                % (x.testo, _giorno(x.dal)))
    if x.al and giorno > x.al:
        return '%s non esisteva più nel %d: controllare il luogo di nascita.' % (x.testo, giorno.year)
    return ''


_PROVINCIA = re.compile(r'\(\s*([A-Za-z]{2}|estero)\s*\)|\s([A-Za-z]{2})\s*$')


def _separa_provincia(testo):
    """'Castro (LE)' o 'castro le' -> ('Castro', 'LE'); 'Napoli' -> ('Napoli', '')."""
    testo = (testo or '').strip()
    m = _PROVINCIA.search(testo)
    if not m:
        return testo, ''
    sigla = (m.group(1) or m.group(2)).upper()
    if sigla == 'ESTERO':
        sigla = 'EE'
    resto = (testo[:m.start()] + testo[m.end():]).strip()
    if m.group(2) and not resto:
        return testo, ''                   # 'Ne' e' un comune, non una provincia
    province = {x.provincia for x in tabella()}
    if sigla not in province:
        return testo, ''
    return resto, sigla


def cerca_luoghi(testo, giorno=None, limite=12):
    """I luoghi per i suggerimenti del campo: tutte le parole scritte devono
    esserci (anche a meta': 's giorgio cremano' trova San Giorgio a Cremano).
    Prima quelli che cominciano cosi', quelli che esistono ancora (o
    esistevano il giorno di nascita), i comuni prima degli stati."""
    nome, sigla = _separa_provincia(testo)
    uscita = _cerca(nome, sigla, giorno, limite)
    if not uscita and sigla:
        # 'Montecorvino Pu' mentre si scrive: PU e' una provincia, ma qui e' l'inizio di una parola
        uscita = _cerca(testo, '', giorno, limite)
    return uscita


def _corrisponde(cercate, parole, tutta):
    """Quanto bene le parole cercate trovano il nome: 0 uguale, 1 il nome
    comincia cosi', 2 ogni parola cercata e' l'inizio di una parola del nome
    (nell'ordine), None se non lo trova. Niente pezzi in mezzo alle parole:
    'nap' non deve trovare Arena Po."""
    insieme = ''.join(cercate)
    if insieme == tutta:
        return 0
    if tutta.startswith(insieme):
        return 1
    i = 0
    for c in cercate:
        while i < len(parole) and not parole[i].startswith(c):
            i += 1
        if i == len(parole):
            return None
        i += 1
    return 2


def _cerca(nome, sigla, giorno, limite):
    cercate = parole_chiave(nome)
    if not cercate:
        return []
    trovati = []
    for x in tabella():
        if sigla and x.provincia != sigla:
            continue
        punti = _corrisponde(cercate, x.parole, x.chiave)
        if x.parole_altro:
            altro = _corrisponde(cercate, x.parole_altro, x.chiave_altro)
            if altro is not None and (punti is None or altro < punti):
                punti = altro
        if punti is None:
            continue
        if isinstance(giorno, date):
            punti += 0 if x.valido_il(giorno) else 10
        else:
            punti += 0 if x.esiste else 10
        trovati.append((punti, x.estero, len(x.nome), x.nome, x.provincia, x))
    trovati.sort(key=lambda t: t[:5])
    uscita, visti = [], set()
    for t in trovati:
        x = t[-1]
        segno = (x.codice, x.testo)
        if segno in visti:
            continue
        visti.add(segno)
        uscita.append(x.come_dizionario())
        if len(uscita) >= limite:
            break
    return uscita


def risolvi_luogo(testo, giorno=None):
    """Il codice del luogo scritto a mano, senza sceglierlo dall'elenco:
    (codice, errore). Va bene il nome intero, con o senza la provincia; se
    ci sono piu' luoghi con quel nome vale quello che esisteva il giorno di
    nascita, poi quello che esiste oggi."""
    testo = ' '.join((testo or '').split())
    if not testo:
        return '', ''
    nome, sigla = _separa_provincia(testo)
    candidati = _con_nome(nome, sigla)
    if not candidati and sigla:
        nome, candidati = testo, _con_nome(testo, '')
    if not candidati:
        return '', 'Luogo di nascita: «%s» non si trova fra i comuni e gli stati esteri; sceglierlo dall\'elenco.' % testo
    ambiguo = ('Luogo di nascita: ci sono più luoghi chiamati «%s»; sceglierlo dall\'elenco, con la provincia.'
               % nome)
    gruppi = []
    if isinstance(giorno, date):
        gruppi.append({x.codice for x in candidati if x.valido_il(giorno)})
    gruppi += [{x.codice for x in candidati if x.esiste}, {x.codice for x in candidati}]
    for codici in gruppi:
        if len(codici) == 1:
            return codici.pop(), ''
        if len(codici) > 1:
            return '', ambiguo
    return '', ambiguo


def _con_nome(nome, sigla):
    k = chiave(nome)
    if not k:
        return []
    return [x for x in tabella() if (x.chiave == k or (x.chiave_altro and x.chiave_altro == k))
            and (not sigla or x.provincia == sigla)]


# ================================================================ insieme
def esamina(cf='', cognome='', nome='', data_nascita=None, sesso='', luogo_codice='', oggi=None):
    """Tutto quello che serve al modulo del paziente, mentre si scrive:
    {'cf', 'stato', 'messaggio', 'avvisi', 'da_cf', 'calcolato', 'mancano'}.
    stato: 'valido' (con eventuali avvisi sui dati), 'non_valido',
    'calcolato' (codice vuoto: calcolato dai dati), 'incompleto' (codice
    vuoto e dati che non bastano)."""
    cf = pulisci(cf)
    esito = {'cf': cf, 'stato': '', 'messaggio': '', 'avvisi': [], 'da_cf': None, 'calcolato': '', 'mancano': []}
    if cf:
        motivo = difetto(cf)
        if motivo:
            esito.update(stato='non_valido', messaggio=motivo)
            return esito
        dati = leggi(cf, oggi)
        esito['da_cf'] = {'data_nascita': dati['data_nascita'].isoformat() if dati['data_nascita'] else '',
                          'sesso': dati['sesso'], 'luogo': dati['luogo'], 'luogo_testo': dati['luogo_testo']}
        esito['stato'] = 'valido'
        esito['messaggio'] = 'Codice fiscale corretto.'
        if not dati['luogo_testo']:
            esito['avvisi'].append('Il codice del luogo di nascita (%s) non è fra i comuni e gli stati conosciuti: '
                                   'se è un comune nato da poco va bene, altrimenti controllare.' % dati['luogo'])
        esito['avvisi'] += confronta(cf, cognome, nome, data_nascita, sesso, luogo_codice)
        return esito
    try:
        esito['calcolato'] = calcola(cognome, nome, data_nascita, sesso, luogo_codice)
    except DatiMancanti as e:
        if len(e.mancano) >= 4:
            messaggio = 'Dal codice fiscale si riempiono data, sesso e luogo di nascita; senza, si calcola dai dati.'
        else:
            messaggio = 'Si calcola da solo quando ci sono anche: %s.' % ', '.join(e.mancano)
        esito.update(stato='incompleto', mancano=e.mancano, messaggio=messaggio)
        return esito
    esito.update(stato='calcolato', messaggio='Calcolato dai dati: controllarlo sulla tessera sanitaria.')
    periodo = avviso_periodo(luogo_codice, data_nascita)
    if periodo:
        esito['avvisi'].append(periodo)
    elif not codice_conosciuto(luogo_codice):
        esito['avvisi'].append('Il codice del luogo di nascita (%s) non è fra quelli conosciuti.' % luogo_codice)
    return esito
