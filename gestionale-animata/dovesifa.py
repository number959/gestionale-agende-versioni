# -*- coding: utf-8 -*-
"""Dove si fa: in quale struttura del gruppo si fa una prestazione, per
indirizzarci il paziente.

I dati vengono dal database delle prestazioni del gruppo, un file Excel: una
riga per prestazione (branca, nome, sinonimi, note) e una colonna per
struttura, con una X dove la prestazione si fa. Si importa da Configura →
Strutture del gruppo, e si reimporta quando esce una versione nuova: i
recapiti scritti nel programma, gli id delle prestazioni e il registro dei
pazienti indirizzati restano. Un foglio facoltativo "Strutture" nello stesso
file puo' portare i recapiti (indirizzo, telefono, orari...).

La ricerca e' fatta qui, una volta sola, per la pagina Dove si fa e per la
ricerca rapida del menu: tutte le parole devono trovarsi (all'inizio di una
parola del nome, dei sinonimi o della branca), con le abbreviazioni d'uso
(RM, TC, RX, ECG, mdc...) e senza badare a maiuscole, accenti e finali
("ginocchio" trova anche "ginocchia")."""
import difflib
import io
import json
import os
import re
import threading
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload

import pazienti
import servizi
from comune import destinazione_sicura, intero, json_sicuro, mese_da, scarica_excel, struttura_scelta
from modelli import (CANALI_INDIRIZZO, Indirizzato, Paziente, Prestazione, SedeVoce, Struttura, StrutturaGruppo,
                     VoceCatalogo, leggi_impostazione, scrivi_impostazione)

bp = Blueprint('dovesifa', __name__, url_prefix='/dove-si-fa')
_fornitore = None
_lucchetto = threading.Lock()

MASSIMO_FILE = 10 * 1024 * 1024
MASSIMO_RISULTATI = 60
# i colori delle strutture, uno per ciascuna finche' bastano (solo un segno accanto al nome)
COLORI = ['#2F6FDB', '#12A594', '#8E4EC6', '#D9480F', '#2B9A3E', '#C2255C', '#0B7285', '#B08300', '#5F3DC4', '#495057']
CANALI = dict(CANALI_INDIRIZZO)
# lunghezze massime delle colonne (le stesse di modelli.py)
LUNGHEZZE = {'nome': 80, 'nome_breve': 30, 'indirizzo': 160, 'citta': 80, 'telefono': 40, 'telefono2': 40,
             'email': 120, 'sito': 300, 'orari': 200, 'prenotazione': 400, 'note': 400}
CAMPI_RECAPITI = ['nome_breve', 'indirizzo', 'citta', 'telefono', 'telefono2', 'email', 'sito', 'orari',
                  'prenotazione', 'note']


class ErroreDatabase(ValueError):
    """Un file che non e' il database delle prestazioni, con il motivo."""


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ================================================================ testo
def chiave(testo):
    """minuscolo, senza accenti, solo lettere e cifre separate da uno spazio."""
    t = unicodedata.normalize('NFKD', str(testo or ''))
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', t).split())


def testo_cella(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return ' '.join(str(v).split())


def sigle(nome):
    """I modi in cui le note del database chiamano una struttura: il nome intero
    e le iniziali ("Casa di cura Collina" -> "cdcc" e "ccc"; "Centro Nord" -> "cn")."""
    parole = chiave(nome).split()
    uscita = {' '.join(parole), ''.join(parole)}
    if len(parole) > 1:
        uscita.add(''.join(p[0] for p in parole))
        uscita.add(''.join(p[0] for p in parole if p not in PAROLE_VUOTE))
    return {x for x in uscita if x}


# ======================================================== il file Excel
SI = {'x', 'si', 's', '1', 'true', 'vero', 'ok', 'yes', 'v'}
SEGNI_SI = {'✓', '✔', '✗', '•', '●'}            # un segno nella cella vale una X ('✗' compreso: e' una crocetta)
NO = {'', 'no', 'n', '0', 'false', 'falso', '-', '—'}
INTESTAZIONI = {'branca': 'branca', 'specialita': 'branca', 'prestazione': 'nome', 'prestazioni': 'nome',
                'sinonimi': 'sinonimi', 'sinonimo': 'sinonimi', 'note': 'note', 'nota': 'note'}
# colonne che non sono strutture anche se ci sono: si ignorano senza avviso
NON_STRUTTURE = {'codice', 'id', 'slug', 'n', 'numero', 'tariffa', 'prezzo', 'importo', 'durata', 'categoria',
                 'totale', 'strutture', 'quante', 'voci totali'}
CAMPI_FOGLIO_STRUTTURE = {
    'nome breve': 'nome_breve', 'sigla': 'nome_breve', 'indirizzo': 'indirizzo', 'citta': 'citta',
    'comune': 'citta', 'telefono': 'telefono', 'telefono 1': 'telefono', 'altro telefono': 'telefono2',
    'telefono 2': 'telefono2', 'secondo telefono': 'telefono2', 'email': 'email', 'e mail': 'email',
    'mail': 'email', 'prenotazione online': 'sito', 'sito': 'sito', 'sito web': 'sito', 'orari': 'orari',
    'orario': 'orari', 'come si prenota': 'prenotazione', 'prenotazioni': 'prenotazione',
    'prenotazione': 'prenotazione', 'note': 'note', 'nota': 'note'}


def _e_si(v):
    t = testo_cella(v)
    return t in SEGNI_SI or chiave(t) in SI


def _e_no(v):
    return chiave(testo_cella(v)) in NO


def _righe(foglio, quante=None):
    for i, riga in enumerate(foglio.iter_rows(values_only=True)):
        if quante is not None and i >= quante:
            return
        yield list(riga)


def _testa(righe):
    """(indice della riga d'intestazione, {campo: colonna}) cercando 'Branca' e
    'Prestazione' nelle prime righe; None se il foglio non le ha."""
    for i, riga in enumerate(righe[:15]):
        campi = {}
        for j, v in enumerate(riga):
            c = INTESTAZIONI.get(chiave(testo_cella(v)))
            if c and c not in campi:
                campi[c] = j
        if 'branca' in campi and 'nome' in campi:
            return i, campi
    return None


def leggi_database(dati, nome_file=''):
    """Il database delle prestazioni da un file Excel. Restituisce
    {'file', 'foglio', 'strutture': [nomi, nell'ordine delle colonne],
     'voci': [{'branca', 'nome', 'sinonimi', 'note', 'sedi': {struttura: {'da_confermare', 'nota'}}}],
     'recapiti': {struttura: {campo: valore}}, 'avvisi': [...]}.
    ErroreDatabase se il file non e' quello giusto."""
    try:
        import openpyxl
        libro = openpyxl.load_workbook(io.BytesIO(dati), read_only=True, data_only=True)
    except Exception:
        raise ErroreDatabase('Il file non si apre come foglio Excel (.xlsx). Va caricato il file Excel del '
                             'database delle prestazioni del gruppo.')
    try:
        return _leggi_libro(libro, nome_file)
    finally:
        try:
            libro.close()
        except Exception:
            pass


def _scegli_foglio(libro):
    candidati = []
    for i, foglio in enumerate(libro.worksheets):
        righe = list(_righe(foglio, 15))
        trovato = _testa(righe)
        if trovato is None:
            continue
        nome = chiave(foglio.title)
        # il foglio intero vince sui fogli per struttura (Branca, Prestazione, Sinonimi e basta)
        candidati.append((0 if 'database' in nome else 1, i, foglio))
    if not candidati:
        return None
    candidati.sort(key=lambda x: (x[0], x[1]))
    return candidati[0][2]


def _leggi_libro(libro, nome_file):
    foglio = _scegli_foglio(libro)
    if foglio is None:
        raise ErroreDatabase('Nel file non c\'è un foglio con le colonne «Branca» e «Prestazione»: non sembra il '
                             'database delle prestazioni.')
    righe = list(_righe(foglio))
    indice_testa, campi = _testa(righe)
    testa = righe[indice_testa]
    corpo = righe[indice_testa + 1:]
    avvisi = []
    note_col = campi.get('note')
    usate = set(campi.values())
    candidate = []                       # (colonna, nome della struttura)
    for j, v in enumerate(testa):
        nome = testo_cella(v)
        if j in usate or not nome or chiave(nome) in NON_STRUTTURE:
            continue
        candidate.append((j, nome))
    strutture = []
    for j, nome in candidate:
        valori = [r[j] if j < len(r) else None for r in corpo]
        strani = [testo_cella(x) for x in valori if not (_e_si(x) or _e_no(x))]
        if strani:
            avvisi.append('Colonna «%s» ignorata: oltre alle X contiene altro (per esempio «%s»).' % (nome, strani[0][:40]))
            continue
        if any(chiave(nome) == chiave(n) for _, n in strutture):
            avvisi.append('Colonna «%s» ignorata: c\'è già una struttura con questo nome.' % nome)
            continue
        strutture.append((j, nome[:LUNGHEZZE['nome']]))
    if not strutture:
        raise ErroreDatabase('Nel foglio «%s» non c\'è nessuna colonna di struttura con le X.' % foglio.title)
    per_sigla = {}
    for _, nome in strutture:
        for sg in sigle(nome):
            per_sigla.setdefault(sg, nome)
    voci, per_chiave, senza_nome, doppie = [], {}, 0, []
    for riga in corpo:
        def cella(campo):
            j = campi.get(campo)
            return testo_cella(riga[j]) if j is not None and j < len(riga) else ''
        if not any(testo_cella(x) for x in riga):
            continue
        nome = cella('nome')
        if not nome:
            senza_nome += 1
            continue
        sedi = {}
        for j, s_nome in strutture:
            if j < len(riga) and _e_si(riga[j]):
                sedi[s_nome] = {'da_confermare': False, 'nota': ''}
        nota = _note_per_struttura(cella('note'), sedi, per_sigla)
        k = chiave(nome)
        if k in per_chiave:
            doppie.append(nome)
            gia = per_chiave[k]
            for s_nome, x in sedi.items():
                gia['sedi'].setdefault(s_nome, x)
            if nota and nota not in gia['note']:
                gia['note'] = ((gia['note'] + '; ') if gia['note'] else '') + nota
                gia['note'] = gia['note'][:1000]
            continue
        voce = {'branca': cella('branca').upper()[:80], 'nome': nome[:160], 'sinonimi': cella('sinonimi')[:1000],
                'note': nota[:1000], 'sedi': sedi}
        per_chiave[k] = voce
        voci.append(voce)
    if not voci:
        raise ErroreDatabase('Nel foglio «%s» non ci sono prestazioni.' % foglio.title)
    if senza_nome:
        avvisi.append('Righe senza il nome della prestazione, saltate: %d.' % senza_nome)
    if doppie:
        avvisi.append('Prestazioni scritte due volte, unite in una: %d (per esempio «%s»).' % (len(doppie), doppie[0]))
    vuote = [n for _, n in strutture if not any(n in v['sedi'] for v in voci)]
    if vuote:
        avvisi.append('Nessuna prestazione segnata per: %s.' % ', '.join(vuote))
    senza_struttura = [v['nome'] for v in voci if not v['sedi']]
    if senza_struttura:
        avvisi.append('Prestazioni senza nessuna X, che nella ricerca compaiono «in nessuna struttura»: %d '
                      '(per esempio «%s»).' % (len(senza_struttura), senza_struttura[0]))
    return {'file': (nome_file or '')[:120], 'foglio': foglio.title, 'strutture': [n for _, n in strutture],
            'voci': voci, 'recapiti': _leggi_recapiti(libro, [n for _, n in strutture], avvisi),
            'avvisi': avvisi, 'note_colonna': note_col is not None}


def _note_per_struttura(nota, sedi, per_sigla):
    """'CN: dedotta dal listino, da confermare; PM: chiamata in un altro modo': ogni
    pezzo che comincia con il nome (o la sigla) di una struttura dove la
    prestazione si fa va a quella struttura; 'da confermare' o 'da verificare' la
    segnano come da confermare. Restituisce il resto della nota (i pezzi che non
    sono di nessuna struttura), che resta sulla prestazione."""
    if not nota:
        return ''
    resto = []
    for pezzo in re.split(r'\s*;\s*', nota):
        m = re.match(r'\s*([^:]{1,40}):\s*(.+)', pezzo)
        nome = per_sigla.get(chiave(m.group(1))) if m else None
        if nome is None or nome not in sedi:
            if pezzo.strip():
                resto.append(pezzo.strip())
            continue
        testo = m.group(2).strip()
        sedi[nome]['nota'] = ((sedi[nome]['nota'] + '; ') if sedi[nome]['nota'] else '') + testo
        sedi[nome]['nota'] = sedi[nome]['nota'][:400]
        if re.search(r'\bda (confermare|verificare)\b', chiave(testo)):
            sedi[nome]['da_confermare'] = True
    return '; '.join(resto)


def _leggi_recapiti(libro, strutture, avvisi):
    """Il foglio facoltativo dei recapiti: una riga per struttura."""
    per_chiave = {chiave(n): n for n in strutture}
    uscita = {}
    for foglio in libro.worksheets:
        if chiave(foglio.title) not in ('strutture', 'recapiti', 'contatti', 'sedi', 'recapiti strutture'):
            continue
        righe = list(_righe(foglio))
        for i, riga in enumerate(righe[:10]):
            nomi = [chiave(testo_cella(v)) for v in riga]
            if 'struttura' in nomi:
                col_nome = nomi.index('struttura')
                colonne = {j: CAMPI_FOGLIO_STRUTTURE[n] for j, n in enumerate(nomi) if n in CAMPI_FOGLIO_STRUTTURE}
                for r in righe[i + 1:]:
                    nome = testo_cella(r[col_nome]) if col_nome < len(r) else ''
                    if not nome:
                        continue
                    vero = per_chiave.get(chiave(nome))
                    if vero is None:
                        avvisi.append('Foglio «%s»: «%s» non è fra le strutture del database, saltata.'
                                      % (foglio.title, nome[:60]))
                        continue
                    campi = {c: testo_cella(r[j])[:LUNGHEZZE[c]] for j, c in colonne.items()
                             if j < len(r) and testo_cella(r[j])}
                    if 'sito' in campi and not sito_valido(campi['sito']):
                        avvisi.append('Foglio «%s»: indirizzo di prenotazione online di «%s» non valido, saltato.'
                                      % (foglio.title, vero))
                        campi.pop('sito')
                    if 'email' in campi and not pazienti.email_valida(campi['email']):
                        avvisi.append('Foglio «%s»: email di «%s» non valida, saltata.' % (foglio.title, vero))
                        campi.pop('email')
                    uscita.setdefault(vero, {}).update(campi)
                break
    return uscita


def sito_valido(testo):
    t = (testo or '').strip()
    return bool(re.fullmatch(r'https?://[^\s<>"\']+\.[^\s<>"\']+', t)) and len(t) <= LUNGHEZZE['sito']


# ========================================================== importazione
def confronto(s, letto):
    """Cosa cambia importando il file: per l'anteprima."""
    attuali = {chiave(v.nome): v for v in s.scalars(select(VoceCatalogo))}
    nuove = {chiave(v['nome']): v for v in letto['voci']}
    gruppo = {chiave(g.nome): g for g in s.scalars(select(StrutturaGruppo))}
    nel_file = {chiave(n) for n in letto['strutture']}
    per_struttura = []
    for nome in letto['strutture']:
        g = gruppo.get(chiave(nome))
        prima = 0
        if g is not None:
            prima = s.scalar(select(func.count()).select_from(SedeVoce).where(SedeVoce.struttura_id == g.id)) or 0
        per_struttura.append({'nome': nome, 'nuova': g is None, 'voci': sum(1 for v in letto['voci'] if nome in v['sedi']),
                              'prima': prima, 'recapiti': bool(letto['recapiti'].get(nome))})
    return {
        'aggiunte': sorted(v['nome'] for k, v in nuove.items() if k not in attuali),
        'tolte': sorted(v.nome for k, v in attuali.items() if k not in nuove),
        'spostate': sorted(v['nome'] for k, v in nuove.items()
                           if k in attuali and (attuali[k].branca or '') != v['branca']),
        'strutture': per_struttura,
        'sparite': sorted(g.nome for k, g in gruppo.items() if k not in nel_file and g.nel_database),
        'branche': len({v['branca'] for v in letto['voci']}),
        'primo': not attuali,
    }


def importa_catalogo(s, letto):
    """Porta nel programma il database letto: strutture (i recapiti gia' scritti
    restano, quelli del foglio Strutture si aggiungono), prestazioni (stessi id
    per lo stesso nome) e dove si fanno. Chi chiama tiene il lucchetto, ha fatto
    il backup e fa il commit."""
    adesso = datetime.now()
    gruppo = {chiave(g.nome): g for g in s.scalars(select(StrutturaGruppo))}
    # una struttura del gruppo con lo stesso nome di una di questo gestionale e' lei ("qui")
    locali = {chiave(x.nome): x.id for x in s.scalars(select(Struttura))}
    per_nome = {}
    for i, nome in enumerate(letto['strutture']):
        g = gruppo.get(chiave(nome))
        if g is None:
            g = StrutturaGruppo(nome=nome, colore=COLORI[len(gruppo) % len(COLORI)], attiva=True,
                                creato_il=adesso, struttura_id=locali.get(chiave(nome)))
            s.add(g)
            gruppo[chiave(nome)] = g
        g.nome = nome
        g.ordine = i
        g.nel_database = True
        g.modificato_il = adesso
        per_nome[nome] = g
    nel_file = set(id(g) for g in per_nome.values())
    for g in gruppo.values():
        if id(g) not in nel_file:
            g.nel_database = False
    # i recapiti del foglio Strutture riempiono solo quelli che mancano: quelli scritti nel programma restano
    for nome, campi in letto['recapiti'].items():
        g = per_nome.get(nome)
        if g is not None:
            for campo, valore in campi.items():
                if not (getattr(g, campo) or '').strip():
                    setattr(g, campo, valore)
    s.flush()
    attuali = {chiave(v.nome): v for v in s.scalars(select(VoceCatalogo).options(selectinload(VoceCatalogo.sedi)))}
    prima = set(attuali)
    viste = set()
    for i, d in enumerate(letto['voci']):
        k = chiave(d['nome'])
        viste.add(k)
        v = attuali.get(k)
        if v is None:
            v = VoceCatalogo(nome=d['nome'])
            s.add(v)
            attuali[k] = v
        v.nome, v.branca, v.sinonimi, v.note, v.ordine = d['nome'], d['branca'], d['sinonimi'], d['note'], i
        voluti = {per_nome[n].id: x for n, x in d['sedi'].items()}
        for sede in list(v.sedi):
            if sede.struttura_id not in voluti:
                v.sedi.remove(sede)
            else:
                x = voluti.pop(sede.struttura_id)
                sede.da_confermare, sede.nota = x['da_confermare'], x['nota']
        for gid, x in voluti.items():
            v.sedi.append(SedeVoce(struttura_id=gid, da_confermare=x['da_confermare'], nota=x['nota']))
    tolte = [v for k, v in attuali.items() if k not in viste]
    if tolte:
        ids = [v.id for v in tolte if v.id is not None]
        if ids:
            s.execute(update(Indirizzato).where(Indirizzato.voce_id.in_(ids)).values(voce_id=None))
        for v in tolte:
            s.delete(v)
    info = {'file': letto['file'], 'foglio': letto['foglio'], 'importato': adesso.strftime('%Y-%m-%d %H:%M'),
            'voci': len(letto['voci']), 'strutture': len(letto['strutture']),
            'branche': len({v['branca'] for v in letto['voci']})}
    scrivi_impostazione(s, 'catalogo_info', json.dumps(info, ensure_ascii=False))
    segna_cambio(s)
    return {'aggiunte': len(viste - prima), 'tolte': len(tolte), 'voci': len(letto['voci']),
            'strutture': len(letto['strutture'])}


def info_catalogo(s):
    try:
        return json.loads(leggi_impostazione(s, 'catalogo_info', '') or '{}')
    except ValueError:
        return {}


def segna_cambio(s):
    """Le ricerche si rifanno sui dati nuovi (vedi indice())."""
    scrivi_impostazione(s, 'catalogo_versione', datetime.now().strftime('%Y%m%d%H%M%S%f'))


# ================================================================ ricerca
PAROLE_VUOTE = {'di', 'del', 'della', 'dello', 'dei', 'degli', 'delle', 'da', 'dal', 'dalla', 'dallo', 'dai',
                'dagli', 'dalle', 'con', 'per', 'e', 'ed', 'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'una', 'uno',
                'al', 'alla', 'allo', 'ai', 'agli', 'alle', 'in', 'nel', 'nella', 'nello', 'nei', 'negli', 'nelle',
                'su', 'sul', 'sulla', 'a', 'ad', 'o', 'od', 'l', 'd', 'fare', 'esame', 'esami',
                # con l'apostrofo (che chiave() cambia in spazio): «dell'addome», «all'anca» (1.11)
                'dell', 'all', 'nell', 'sull', 'dall', 'coll', 'quest'}
# abbreviazioni e parole d'uso: la parola cercata vale anche come le altre della lista
ESPANSIONI = {
    'rm': ['rm', 'risonanza'], 'rmn': ['rm', 'risonanza'], 'risonanza': ['risonanza', 'rm'],
    'tac': ['tc', 'tac'], 'tc': ['tc', 'tac'], 'tomografia': ['tomografia', 'tc'],
    'rx': ['rx', 'radiografia'], 'radiografia': ['radiografia', 'rx'], 'lastra': ['rx', 'radiografia'],
    'lastre': ['rx', 'radiografia'], 'mdc': ['mdc', 'contrasto'], 'contrasto': ['contrasto', 'mdc'],
    'ecg': ['ecg', 'elettrocardiogramma'], 'elettrocardiogramma': ['elettrocardiogramma', 'ecg'],
    'eeg': ['eeg', 'elettroencefalogramma'], 'elettroencefalogramma': ['elettroencefalogramma', 'eeg'],
    'emg': ['emg', 'elettromiografia'], 'elettromiografia': ['elettromiografia', 'emg'],
    'moc': ['moc', 'densitometria'], 'densitometria': ['densitometria', 'moc'],
    'egds': ['egds', 'gastroscopia', 'esofagogastroduodenoscopia'],
    'gastroscopia': ['gastroscopia', 'egds', 'esofagogastroduodenoscopia'],
    'ecodoppler': ['ecodoppler', 'ecocolordoppler', 'doppler'], 'doppler': ['doppler', 'ecocolordoppler'],
    'eco': ['eco', 'ecografia'], 'ecografia': ['ecografia', 'eco'],
    'dentista': ['dentista', 'odontoiatrica', 'odontoiatria'], 'oculista': ['oculista', 'oculistica'],
    'nutrizionista': ['nutrizionista', 'nutrizione', 'dietologica', 'dietologia'],
    'dietologo': ['dietologo', 'dietologica', 'dietologia'], 'otorino': ['otorino', 'otorinolaringoiatrica'],
    'analisi': ['analisi', 'laboratorio'], 'prelievo': ['prelievo', 'laboratorio'],
    'colonna': ['colonna', 'rachide'], 'schiena': ['schiena', 'rachide'],
    'lombare': ['lombare', 'lombo'], 'lombosacrale': ['lombosacrale', 'lombo'],
    'vene': ['vene', 'venoso', 'venosa', 'venose', 'venosi'], 'varici': ['varici', 'varicose', 'venoso'],
    'encefalo': ['encefalo', 'cranio'], 'cranio': ['cranio', 'encefalo'], 'testa': ['testa', 'cranio', 'encefalo'],
    'reni': ['reni', 'rene', 'renale', 'renali'], 'rene': ['rene', 'reni', 'renale', 'renali'],
    'seno': ['seno', 'mammella', 'mammaria', 'mammario'], 'pancia': ['pancia', 'addome', 'addominale'],
    'cuore': ['cuore', 'cardiaco', 'cardiaca', 'ecocardiogramma'],
}
# "cardiologo", "oculista", "chirurgo": si cerca lo specialista, prima la visita
SPECIALISTA = re.compile(r'(olog[oaie]|ist[aei]|iatr[aie]|urg[oh]i?|edic[oa])$')
# l'indice per la ricerca, rifatto solo quando il catalogo cambia: ogni ricerca
# usa la fotografia che trova, anche se intanto un'altra ne prepara una nuova
_indice = {'versione': None, 'dati': None}
_indice_lucchetto = threading.Lock()


def parole(testo):
    return chiave(testo).split()


def parole_indice(testo):
    """Le parole di un nome per la ricerca: quelle con il trattino anche unite
    ('lombo-sacrale' trova anche 'lombosacrale')."""
    testo = testo or ''
    unite = [chiave(m).replace(' ', '') for m in re.findall(r'[^\W_]+(?:-[^\W_]+)+', testo)]
    return parole(testo) + [u for u in unite if u]


def radice(p):
    """'ginocchio' e 'ginocchia' -> 'ginocchi': la vocale finale non conta."""
    return p[:-1] if len(p) > 4 and p[-1] in 'aeiou' else p


def _radici(alternative):
    """Per ogni parola cercata: (radice, parola intera, radice corta). La radice
    corta serve alle parole di quattro lettere ('mani' trova 'mano', 'reni'
    trova 'rene'), che con la radice normale resterebbero intere."""
    return [(radice(a), a, a[:3] if len(a) == 4 and a[3] in 'aeiou' and a[:3].isalpha() else None)
            for a in alternative]


def indice(s):
    """Le prestazioni pronte per la ricerca, rifatte solo se il catalogo e'
    cambiato (importazione o strutture modificate): {'voci', 'vocabolario',
    'strutture'}."""
    versione = leggi_impostazione(s, 'catalogo_versione', '')
    with _indice_lucchetto:
        if versione and _indice['versione'] == versione:
            return _indice['dati']
        gruppo = {g.id: g for g in s.scalars(select(StrutturaGruppo))}
        voci = []
        vocabolario = set()
        for v in s.scalars(select(VoceCatalogo).options(selectinload(VoceCatalogo.sedi))
                           .order_by(VoceCatalogo.ordine, VoceCatalogo.id)):
            sedi = sorted(((x.struttura_id, x.da_confermare, x.nota or '') for x in v.sedi
                           if x.struttura_id in gruppo and gruppo[x.struttura_id].attiva),
                          key=lambda x: (gruppo[x[0]].ordine, gruppo[x[0]].id))
            sinonimi = [x.strip() for x in re.split(r'[,;]', v.sinonimi or '') if x.strip()]
            w_nome, w_sin, w_bra = parole_indice(v.nome), parole_indice(', '.join(sinonimi)), parole(v.branca)
            vocabolario.update(w for w in w_nome + w_sin if len(w) >= 3 and not w.isdigit())
            voci.append({'id': v.id, 'nome': v.nome, 'branca': v.branca or '', 'sinonimi': sinonimi,
                         'note': v.note or '', 'w_nome': w_nome, 'w_sin': w_sin, 'w_bra': w_bra, 'sedi': sedi})
        dati = {'voci': voci, 'vocabolario': sorted(vocabolario),
                'strutture': {gid: {'id': g.id, 'nome': g.nome, 'etichetta': g.etichetta,
                                    'citta': (g.citta or '').strip(), 'colore': colore_sicuro(g.colore),
                                    'qui': g.struttura_id, 'recapiti': g.con_recapiti, 'ordine': g.ordine,
                                    'attiva': g.attiva}
                              for gid, g in gruppo.items()}}
        _indice.update(versione=versione, dati=dati)
        return dati


def gettoni(q):
    """Le parole cercate, senza quelle vuote ('di', 'con', 'la'...). Se restano
    solo parole vuote si tengono quelle: «nei» sono anche i nei."""
    tutte = [p for p in parole(q) if len(p) >= 2 or p.isdigit()]
    piene = [p for p in tutte if p not in PAROLE_VUOTE]
    return piene or [p for p in tutte if p not in ('fare', 'esame', 'esami')]


def _trova(radici, lista):
    """0 se nessuna parola comincia con una delle radici, 1 se si', 2 se una
    parola e' proprio quella cercata."""
    meglio = 0
    for r, intera, corta in radici:
        for w in lista:
            if w == intera:
                return 2
            if w.startswith(r) or (corta and len(w) == 4 and w.startswith(corta) and w[3] in 'aeiou'):
                meglio = 1
    return meglio


def punteggio(voce, ricerca):
    """Punti di una prestazione per le parole cercate; None se una manca."""
    totale, tutte_nel_nome = 0, True
    for alternative in ricerca:
        radici = _radici(alternative)
        n = _trova(radici, voce['w_nome'])
        if n:
            totale += 3 + (n == 2)
            continue
        tutte_nel_nome = False
        if _trova(radici, voce['w_sin']):
            totale += 2
        elif _trova(radici, voce['w_bra']):
            totale += 1
        else:
            return None
    if tutte_nel_nome:
        totale += 2
    if voce['w_nome'] and ricerca and any(voce['w_nome'][0].startswith(radice(a)) for a in ricerca[0]):
        totale += 1
    piatte = {a for alt in ricerca for a in alt}
    # "TC torace con mdc": prima le voci con contrasto che quelle "senza mdc"
    if 'senza' not in piatte and 'senza' in voce['w_nome'] and piatte & {'mdc', 'contrasto'}:
        totale -= 2
    # "cardiologo": prima la visita cardiologica
    if voce['w_nome'][:1] == ['visita'] and any(SPECIALISTA.search(alt[0]) for alt in ricerca):
        totale += 2
    return totale


def cerca(s, q, branca='', limite=MASSIMO_RISULTATI, sede=None):
    """{'risultati', 'totale', 'corretta'}: le voci dell'indice che corrispondono,
    della branca e della struttura del gruppo ('sede', il suo id) se scelte.
    Se non si trova niente ma correggendo una parola scritta male si', i
    risultati sono quelli della ricerca corretta, scritta in 'corretta'
    ('ecocardiogrma' -> 'ecocardiogramma'). Senza parole, branca e struttura:
    nessun risultato."""
    idx = indice(s)
    toks = gettoni(q)
    b = chiave(branca)
    if not toks and not b and sede is None:
        return {'risultati': [], 'totale': 0, 'corretta': None}

    def filtro(v):
        return (not b or chiave(v['branca']) == b) and (sede is None or any(x[0] == sede for x in v['sedi']))
    risultati, totale = _cerca(idx, toks, filtro, limite)
    corretta = None
    if not totale and toks:
        corretta = _forse(idx, toks, filtro)
        if corretta:
            risultati, totale = _cerca(idx, corretta.split(), filtro, limite)
    return {'risultati': risultati, 'totale': totale, 'corretta': corretta}


def _cerca(idx, toks, filtro, limite):
    ricerca = [ESPANSIONI.get(t, [t]) for t in toks]
    trovati = []
    for v in idx['voci']:
        if not filtro(v):
            continue
        if not toks:
            trovati.append((0, v))
            continue
        p = punteggio(v, ricerca)
        if p is not None:
            trovati.append((p, v))
    if toks:
        trovati.sort(key=lambda x: (-x[0], len(x[1]['w_nome']), x[1]['nome'].lower()))
    else:
        trovati.sort(key=lambda x: x[1]['nome'].lower())
    return [v for _, v in trovati[:limite]], len(trovati)


def _forse(idx, toks, filtro):
    """Una ricerca corretta che trova qualcosa ('ecocardiogrma' -> 'ecocardiogramma')."""
    corretti, cambiato = [], False
    vocabolario = idx['vocabolario']
    for t in toks:
        if t in ESPANSIONI or t.isdigit() or _trova(_radici([t]), vocabolario):
            corretti.append(t)
            continue
        simili = difflib.get_close_matches(t, vocabolario, n=1, cutoff=0.75)
        if not simili:
            return None
        corretti.append(simili[0])
        cambiato = True
    if not cambiato:
        return None
    ricerca = [ESPANSIONI.get(t, [t]) for t in corretti]
    if any(punteggio(v, ricerca) is not None for v in idx['voci'] if filtro(v)):
        return ' '.join(corretti)
    return None


def branche(s):
    """[(branca, quante prestazioni, quante strutture)] dalla piu' grande."""
    idx = indice(s)
    conta, dove = {}, {}
    for v in idx['voci']:
        conta[v['branca']] = conta.get(v['branca'], 0) + 1
        dove.setdefault(v['branca'], set()).update(x[0] for x in v['sedi'])
    return sorted(((b, n, len(dove[b])) for b, n in conta.items()), key=lambda x: (-x[1], x[0]))


def nel_nostro_listino(s, q):
    """Le prestazioni del listino di questo gestionale che corrispondono alla
    ricerca: magari si fa anche qui."""
    toks = gettoni(q)
    if not toks:
        return []
    ricerca = [ESPANSIONI.get(t, [t]) for t in toks]
    uscita = []
    for p in s.scalars(select(Prestazione).order_by(Prestazione.nome)):
        w = parole(p.nome)
        if all(_trova(_radici(alt), w) for alt in ricerca):
            uscita.append(p)
    return uscita[:5]


def colore_sicuro(colore):
    """Il colore della struttura com'e' scritto nel database, se e' un colore
    vero (#RRGGBB): finisce in un attributo style."""
    return colore if re.fullmatch(r'#[0-9A-Fa-f]{6}', colore or '') else COLORI[0]


def risultato_json(v, idx, qui_id=None):
    strutture = idx.get('strutture', {})
    return {'id': v['id'], 'nome': v['nome'], 'branca': v['branca'], 'sinonimi': v['sinonimi'][:6], 'note': v['note'],
            'sedi': [{'id': gid, 'nome': strutture[gid]['nome'], 'etichetta': strutture[gid]['etichetta'],
                      'citta': strutture[gid]['citta'], 'colore': strutture[gid]['colore'], 'da_confermare': dc,
                      'nota': nota, 'qui': qui_id is not None and strutture[gid]['qui'] == qui_id}
                     for gid, dc, nota in v['sedi'] if gid in strutture]}


# ======================================================== per il paziente
def mappa(g):
    luogo = ', '.join(x for x in ((g.indirizzo or '').strip(), (g.citta or '').strip()) if x)
    return 'https://www.google.com/maps/search/?api=1&query=' + quote(luogo + ', ' + g.nome) if luogo else ''


def telefoni(g):
    uscita = []
    for t in (g.telefono, g.telefono2):
        t = ' '.join((t or '').split())
        if not t:
            continue
        n = pazienti.numero_internazionale(t)
        uscita.append({'numero': t, 'tel': ('tel:+' + n) if n else ''})
    return uscita


def nome_per_messaggio(paziente):
    """'Mario Esempio': il nome e poi il cognome, con le maiuscole giuste anche
    se in anagrafica e' scritto tutto maiuscolo."""
    if paziente is None:
        return ''
    parti = []
    for x in (paziente.nome, paziente.cognome):
        x = ' '.join((x or '').split())
        if x and x.isupper():
            x = ' '.join(p[:1] + p[1:].lower() for p in x.split())
        if x:
            parti.append(x)
    return ' '.join(parti)


def messaggio(g, voce, paziente=None, firma=''):
    """Il testo da dare al paziente: dove si fa e come si prenota."""
    righe = []
    nome = nome_per_messaggio(paziente)
    righe.append('Gentile %s,' % nome if nome else 'Buongiorno,')
    cosa = 'la prestazione «%s»' % voce.nome if voce is not None else 'la prestazione richiesta'
    citta = (g.citta or '').strip()
    righe.append('%s si può fare presso %s%s.' % (cosa, g.nome, (' (%s)' % citta) if citta else ''))
    if (g.indirizzo or '').strip():
        righe.append('Indirizzo: %s' % ', '.join(x for x in (g.indirizzo.strip(), citta) if x))
    tel = [t['numero'] for t in telefoni(g)]
    if tel:
        righe.append('Per prenotare: %s' % ' oppure '.join(tel))
    if sito_valido(g.sito):
        righe.append('Prenotazione online: %s' % g.sito.strip())
    if (g.orari or '').strip():
        righe.append('Orari: %s' % g.orari.strip())
    if (g.prenotazione or '').strip():
        righe.append(g.prenotazione.strip())
    righe.append('')
    righe.append('Cordiali saluti' + (('\n' + firma) if firma else ''))
    return '\n'.join(righe)


def branche_della_struttura(s, gid):
    """[(branca, quante prestazioni)] di una struttura, dalla piu' grande: per la
    scheda aperta senza una prestazione («cosa si fa qui»)."""
    conta = {}
    for v in indice(s)['voci']:
        if any(x[0] == gid for x in v['sedi']):
            conta[v['branca']] = conta.get(v['branca'], 0) + 1
    return sorted(conta.items(), key=lambda x: (-x[1], chiave(x[0])))


def scheda_struttura(s, g, voce=None, paziente=None, st=None):
    """Tutto quello che serve alla scheda della struttura: recapiti, il
    messaggio per il paziente e i collegamenti per mandarglielo."""
    firma = st.nome if st is not None else ''
    testo = messaggio(g, voce, paziente, firma)
    oggetto = ('Dove fare: %s' % voce.nome) if voce is not None else 'Dove fare la prestazione'
    sede = None
    if voce is not None:
        sede = next((x for x in voce.sedi if x.struttura_id == g.id), None)
    mobile = pazienti.cellulare_whatsapp(paziente) if paziente is not None else None
    email_paziente = (paziente.email or '').strip() if paziente is not None else ''
    if email_paziente and not pazienti.email_valida(email_paziente):
        email_paziente = ''
    # i collegamenti si rifanno nella pagina se si cambia il testo: base + testo codificato
    base_whatsapp = 'https://wa.me/%s?text=' % (mobile or '')
    base_email = 'mailto:%s?subject=%s&body=' % (quote(email_paziente, safe='@.+'), quote(oggetto))
    return {
        'id': g.id, 'nome': g.nome, 'etichetta': g.etichetta, 'colore': colore_sicuro(g.colore),
        'indirizzo': (g.indirizzo or '').strip(), 'citta': (g.citta or '').strip(), 'mappa': mappa(g),
        'telefoni': telefoni(g), 'email': g.email or '', 'sito': g.sito.strip() if sito_valido(g.sito) else '',
        'orari': g.orari or '', 'prenotazione': g.prenotazione or '', 'note': g.note or '',
        'con_recapiti': g.con_recapiti, 'attiva': g.attiva,
        'qui': st is not None and g.struttura_id == st.id,
        'voce': {'id': voce.id, 'nome': voce.nome, 'branca': voce.branca or '', 'si_fa': sede is not None,
                 'da_confermare': bool(sede and sede.da_confermare), 'nota': (sede.nota if sede else '') or ''}
        if voce is not None else None,
        'paziente': {'id': paziente.id, 'etichetta': paziente.etichetta, 'whatsapp': bool(mobile),
                     'email': bool(email_paziente)} if paziente is not None else None,
        'messaggio': testo, 'oggetto': oggetto,
        'base_whatsapp': base_whatsapp, 'whatsapp': base_whatsapp + quote(testo),
        'base_email': base_email, 'email_link': base_email + quote(testo),
        'stampa': url_for('dovesifa.stampa', gruppo=g.id, voce=voce.id if voce is not None else None,
                          paziente=paziente.id if paziente is not None else None,
                          struttura=st.id if st is not None else None),
        'modifica': url_for('dovesifa.struttura', gid=g.id),
        'branche': branche_della_struttura(s, g.id) if voce is None else [],
        'ultimi': [{'quando': x.quando.strftime('%d/%m %H:%M'), 'paziente': x.paziente or '',
                    'prestazione': x.prestazione or ''}
                   for x in s.scalars(select(Indirizzato).where(Indirizzato.gruppo_id == g.id)
                                      .order_by(Indirizzato.quando.desc(), Indirizzato.id.desc()).limit(3))],
    }


# ================================================================ pagine
def _paziente(s, valore):
    pid = intero(valore)
    return s.get(Paziente, pid) if pid else None


def _voce(s, valore):
    vid = intero(valore)
    return s.get(VoceCatalogo, vid) if vid else None


def leggi_richiesta(s):
    """q, branca, sede: quello che si cerca (dall'indirizzo); sede e' l'id di una
    struttura del gruppo che esiste, altrimenti None."""
    sede = intero(request.args.get('sede')) or None
    if sede is not None and sede not in indice(s)['strutture']:
        sede = None
    return (request.args.get('q') or '').strip()[:80], (request.args.get('branca') or '').strip()[:80], sede


def contesto_ricerca(s, st, strutture, q, branca, paziente, sede=None):
    """I dati dei risultati: gli stessi per la pagina intera e per i
    risultati che la pagina chiede mentre si scrive. 'sid_link' va negli
    indirizzi solo se le strutture del gestionale sono piu' d'una."""
    idx = indice(s)
    esito = cerca(s, q, branca, sede=sede)
    uscita = {'q': q, 'branca': branca, 'sede': sede, 'sede_info': idx['strutture'].get(sede) if sede else None,
              'paziente': paziente, 'st': st, 'sid': st.id if st else None,
              'sid_link': st.id if st is not None and len(strutture) > 1 else None,
              'risultati': [risultato_json(v, idx, st.id if st else None) for v in esito['risultati']],
              'totale': esito['totale'], 'corretta': esito['corretta'], 'vuoto': not idx['voci'],
              'nostri': [nostro_json(p, st, paziente) for p in nel_nostro_listino(s, esito['corretta'] or q)]
              if q else [],
              'canali': CANALI}
    if not q and not branca and not sede:
        uscita['branche'] = sorted(branche(s), key=lambda x: chiave(x[0]))
        uscita['gruppo'] = [dict(x, voci=sum(1 for v in idx['voci'] for y in v['sedi'] if y[0] == x['id']))
                            for x in sorted(idx['strutture'].values(), key=lambda x: (x['ordine'], x['id']))
                            if x['attiva']]
        uscita['recenti'] = s.scalars(select(Indirizzato).order_by(Indirizzato.quando.desc(), Indirizzato.id.desc())
                                      .limit(6)).all()
    return uscita


def nostro_json(p, st, paziente=None):
    """Una prestazione del listino di questo gestionale, da prenotare qui."""
    return {'id': p.id, 'nome': p.nome,
            'url': url_for('appuntamento', prestazione=p.id, struttura=st.id if st else None,
                           paziente_id=paziente.id if paziente is not None else None)}


def _html(testo):
    """Un pezzo di pagina chiesto dalla pagina stessa: con i nomi dei pazienti,
    da non conservare nella cache del browser."""
    from flask import make_response
    r = make_response(testo)
    r.headers['Cache-Control'] = 'no-store'
    r.headers['X-Content-Type-Options'] = 'nosniff'
    return r


@bp.route('/')
def pagina():
    s = ses()
    st, strutture = struttura_scelta(s)
    q, branca, sede = leggi_richiesta(s)
    paziente = _paziente(s, request.args.get('paziente'))
    contesto = contesto_ricerca(s, st, strutture, q, branca, paziente, sede)
    scheda = None
    g = s.get(StrutturaGruppo, intero(request.args.get('gruppo'))) if request.args.get('gruppo') else None
    if g is not None:
        scheda = scheda_struttura(s, g, _voce(s, request.args.get('voce')), paziente, st)
    return render_template('dove.html', sezione='dove', strutture=strutture, info=info_catalogo(s),
                           tutte_branche=sorted((b for b, _, _ in branche(s)), key=chiave), scheda=scheda,
                           voce_scelta=intero(request.args.get('voce')) or None, **contesto)


@bp.route('/risultati')
def risultati():
    """I risultati mentre si scrive: lo stesso modello della pagina intera."""
    s = ses()
    st, strutture = struttura_scelta(s)
    q, branca, sede = leggi_richiesta(s)
    contesto = contesto_ricerca(s, st, strutture, q, branca, _paziente(s, request.args.get('paziente')), sede)
    return _html(render_template('_dove_risultati.html', **contesto))


@bp.route('/scheda/<int:gid>')
def scheda(gid):
    """La scheda di una struttura, nel riquadro a destra della pagina."""
    s = ses()
    st, strutture = struttura_scelta(s)
    g = s.get(StrutturaGruppo, gid)
    if g is None:
        abort(404)
    q, branca, sede = leggi_richiesta(s)
    paziente = _paziente(s, request.args.get('paziente'))
    return _html(render_template('_dove_scheda.html', scheda=scheda_struttura(s, g, _voce(s, request.args.get('voce')),
                                                                              paziente, st),
                                 q=q, branca=branca, sede=sede, paziente=paziente, st=st, sid=st.id if st else None,
                                 sid_link=st.id if st is not None and len(strutture) > 1 else None, canali=CANALI))


@bp.route('/cerca.json')
def cerca_json():
    s = ses()
    st, _ = struttura_scelta(s)
    q, branca, sede = leggi_richiesta(s)
    idx = indice(s)
    esito = cerca(s, q, branca, sede=sede)
    return json_sicuro({'q': q, 'branca': branca, 'sede': sede, 'totale': esito['totale'], 'corretta': esito['corretta'],
                        'risultati': [risultato_json(v, idx, st.id if st else None) for v in esito['risultati']],
                        'nostri': [nostro_json(p, st) for p in nel_nostro_listino(s, esito['corretta'] or q)]})


def per_ricerca_rapida(s, q, limite=4):
    """Le prestazioni per la ricerca rapida del menu: dove si fanno, in breve."""
    if len((q or '').strip()) < 3:
        return []
    idx = indice(s)
    if not idx['voci']:
        return []
    esito = cerca(s, q, limite=limite)
    uscita = []
    for v in esito['risultati']:
        nomi = [idx['strutture'][gid]['etichetta'] for gid, _, _ in v['sedi'] if gid in idx['strutture']]
        dove = ', '.join(nomi[:3]) + (' e altre %d' % (len(nomi) - 3) if len(nomi) > 3 else '')
        uscita.append({'etichetta': v['nome'], 'dettaglio': ('si fa a: ' + dove) if nomi else 'in nessuna struttura',
                       'url': url_for('dovesifa.pagina', q=esito['corretta'] or q, voce=v['id'])})
    return uscita


@bp.route('/stampa')
def stampa():
    s = ses()
    st, _ = struttura_scelta(s)
    g = s.get(StrutturaGruppo, intero(request.args.get('gruppo')))
    if g is None:
        abort(404)
    voce = _voce(s, request.args.get('voce'))
    paziente = _paziente(s, request.args.get('paziente'))
    return render_template('dove_stampa.html', g=g, voce=voce, paziente=paziente, st=st, sid=st.id if st else None,
                           scheda=scheda_struttura(s, g, voce, paziente, st), oggi=date.today())


@bp.route('/indirizza', methods=['POST'])
def indirizza():
    """Segna un paziente indirizzato (dalla scheda della struttura)."""
    s = ses()
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):            # un JSON che non e' un dizionario non ha campi (1.11)
        dati = request.form
    st, _ = struttura_scelta(s)
    g = s.get(StrutturaGruppo, intero(dati.get('gruppo')))
    if g is None:
        return json_sicuro({'errore': 'Struttura non trovata: ricaricare la pagina.'}), 400
    voce = _voce(s, dati.get('voce'))
    paziente = _paziente(s, dati.get('paziente'))
    canale = dati.get('canale') if isinstance(dati.get('canale'), str) and dati.get('canale') in CANALI else 'telefono'
    with _lucchetto:
        x = Indirizzato(quando=datetime.now(), struttura_id=st.id if st else None, gruppo_id=g.id,
                        gruppo_nome=g.nome[:80], voce_id=voce.id if voce else None,
                        prestazione=voce.nome[:160] if voce else '', branca=(voce.branca or '')[:80] if voce else '',
                        paziente_id=paziente.id if paziente else None,
                        paziente=paziente.etichetta[:120] if paziente else '', canale=canale,
                        note=' '.join(str(dati.get('note') or '').split())[:200])
        s.add(x)
        s.commit()
        chi = paziente.etichetta if paziente is not None else 'Paziente'
        finale = 'a' if paziente is not None and paziente.sesso == 'F' else 'o'
        testo = '%s indirizzat%s a %s%s%s.' % (chi, finale, g.nome, (' per «%s»' % voce.nome) if voce else '',
                                              '' if canale == 'voce' else ' (%s)' % CANALI[canale])
        return json_sicuro({'id': x.id, 'testo': testo, 'togli': url_for('dovesifa.togli', iid=x.id)})


@bp.route('/indirizzati/<int:iid>/togli', methods=['POST'])
def togli(iid):
    s = ses()
    with _lucchetto:
        x = s.get(Indirizzato, iid)
        if x is not None:
            s.delete(x)
            s.commit()
    if request.is_json:
        return json_sicuro({'tolto': iid})
    flash('Tolto dal registro.' if x is not None else 'Era già stato tolto.', 'ok')
    return redirect(destinazione_sicura(request.form.get('torna'), url_for('dovesifa.registro')))


def _del_mese(s, primo, ultimo, ordine):
    return s.scalars(select(Indirizzato)
                     .where(Indirizzato.quando >= datetime.combine(primo, datetime.min.time()),
                            Indirizzato.quando < datetime.combine(ultimo + timedelta(days=1), datetime.min.time()))
                     .order_by(*ordine)).all()


@bp.route('/registro')
def registro():
    s = ses()
    st, _ = struttura_scelta(s)
    primo, ultimo = mese_da(request.args.get('mese'))
    righe = _del_mese(s, primo, ultimo, (Indirizzato.quando.desc(), Indirizzato.id.desc()))
    conta = {}
    for x in righe:
        conta[x.gruppo_nome or '—'] = conta.get(x.gruppo_nome or '—', 0) + 1
    return render_template('dove_registro.html', sezione='dove', st=st, sid=st.id if st else None, righe=righe,
                           conta=sorted(conta.items(), key=lambda x: (-x[1], x[0])), primo=primo, ultimo=ultimo,
                           mese=primo.strftime('%Y-%m'), precedente=(primo - timedelta(days=1)).strftime('%Y-%m'),
                           successivo=(ultimo + timedelta(days=1)).strftime('%Y-%m'), canali=CANALI,
                           mese_nome='%s %d' % (servizi.MESI[primo.month - 1], primo.year))


@bp.route('/registro/<mese>.xlsx')
def registro_excel(mese):
    s = ses()
    primo, ultimo = mese_da(mese)
    import openpyxl
    from openpyxl.styles import Font
    righe = _del_mese(s, primo, ultimo, (Indirizzato.quando, Indirizzato.id))
    libro = openpyxl.Workbook()
    ws = libro.active
    ws.title = 'Indirizzati'
    ws.append(['Data', 'Ora', 'Paziente', 'Prestazione', 'Branca', 'Struttura', 'Come', 'Note'])
    for c in ws[1]:
        c.font = Font(bold=True)
    for x in righe:
        ws.append([x.quando.date(), x.quando.strftime('%H:%M'), x.paziente, x.prestazione, x.branca, x.gruppo_nome,
                   CANALI.get(x.canale, x.canale), x.note])
        ws.cell(row=ws.max_row, column=1).number_format = 'DD/MM/YYYY'
    for lettera, larga in zip('ABCDEFGH', (11, 7, 28, 42, 28, 24, 16, 30)):
        ws.column_dimensions[lettera].width = larga
    return scarica_excel(libro, 'Pazienti indirizzati %s.xlsx' % primo.strftime('%Y-%m'))


def conteggi_periodo(s, dal, al, struttura_id=None):
    """[(struttura del gruppo, quanti)] per le statistiche: i pazienti
    indirizzati da questa struttura (e quelli segnati senza struttura)."""
    condizioni = [Indirizzato.quando >= datetime.combine(dal, datetime.min.time()),
                  Indirizzato.quando < datetime.combine(al + timedelta(days=1), datetime.min.time())]
    if struttura_id is not None:
        condizioni.append(or_(Indirizzato.struttura_id == struttura_id, Indirizzato.struttura_id.is_(None)))
    righe = s.execute(select(Indirizzato.gruppo_nome, func.count()).where(*condizioni)
                      .group_by(Indirizzato.gruppo_nome)).all()
    return sorted(((n or '—', c) for n, c in righe), key=lambda x: (-x[1], x[0]))


# ==================================================== strutture del gruppo
@bp.route('/strutture', methods=['GET', 'POST'])
def strutture():
    s = ses()
    if request.method == 'POST':
        f = request.files.get('file')
        if f is None or not f.filename:
            flash('Scegliere il file Excel del database delle prestazioni.', 'errore')
            return redirect(url_for('dovesifa.strutture'))
        dati = f.read(MASSIMO_FILE + 1)
        if len(dati) > MASSIMO_FILE:
            flash('Il file supera 10 MB.', 'errore')
            return redirect(url_for('dovesifa.strutture'))
        try:
            leggi_database(dati, f.filename)
        except ErroreDatabase as e:
            flash(str(e), 'errore')
            return redirect(url_for('dovesifa.strutture'))
        import importa as caricamenti
        import secrets
        token = secrets.token_hex(16)
        with open(caricamenti.percorso_caricato(token), 'wb') as out:
            out.write(dati)
        with open(caricamenti.percorso_caricato(token, '.json'), 'w', encoding='utf-8') as out:
            json.dump({'nome': (f.filename or '')[-120:], 'tipo': 'catalogo'}, out)
        return redirect(url_for('dovesifa.anteprima', token=token))
    gruppo = s.scalars(select(StrutturaGruppo).order_by(StrutturaGruppo.nel_database.desc(), StrutturaGruppo.ordine,
                                                        StrutturaGruppo.id)).all()
    conta = dict(s.execute(select(SedeVoce.struttura_id, func.count()).group_by(SedeVoce.struttura_id)).all())
    return render_template('dove_strutture.html', sezione='gruppo', gruppo=gruppo, conta=conta,
                           info=info_catalogo(s), voci=s.scalar(select(func.count()).select_from(VoceCatalogo)) or 0,
                           colore_sicuro=colore_sicuro)


@bp.route('/strutture/importa/<token>', methods=['GET', 'POST'])
def anteprima(token):
    s = ses()
    import importa as caricamenti
    dati, meta = caricamenti.carica_caricato(token)
    if dati is None or (meta or {}).get('tipo') != 'catalogo':
        flash('Il file caricato non c\'è più: caricarlo di nuovo.', 'errore')
        return redirect(url_for('dovesifa.strutture'))
    try:
        letto = leggi_database(dati, meta['nome'])
    except ErroreDatabase as e:
        flash(str(e), 'errore')
        return redirect(url_for('dovesifa.strutture'))
    if request.method == 'POST' and request.form.get('azione') == 'importa':
        with _lucchetto:
            try:
                import backup
                import viste
                percorso, _ = viste.percorso_database()
                if percorso:
                    backup.esegui(percorso, viste.cartella_effettiva(s, percorso), 'prima-del-database-prestazioni')
            except Exception as e:
                flash('Importazione annullata: il backup di sicurezza non è riuscito (%s).' % e, 'errore')
                return redirect(request.url)
            try:
                esito = importa_e_conferma(s, letto)
            except Exception as e:
                s.rollback()
                flash('Importazione non riuscita, niente è stato cambiato: %s' % e, 'errore')
                return redirect(request.url)
        for estensione in ('.dat', '.json'):
            try:
                os.remove(caricamenti.percorso_caricato(token, estensione))
            except OSError:
                pass
        flash('Database delle prestazioni importato: %d prestazioni in %d strutture.'
              % (esito['voci'], esito['strutture']), 'ok')
        return redirect(url_for('dovesifa.strutture'))
    return render_template('dove_anteprima.html', sezione='gruppo', letto=letto, token=token,
                           diff=confronto(s, letto), nome=meta['nome'])


def importa_e_conferma(s, letto):
    esito = importa_catalogo(s, letto)
    s.commit()
    return esito


@bp.route('/strutture/<int:gid>', methods=['GET', 'POST'])
def struttura(gid):
    """I recapiti di una struttura del gruppo (il nome e' quello del database)."""
    s = ses()
    g = s.get(StrutturaGruppo, gid)
    if g is None:
        abort(404)
    locali = s.scalars(select(Struttura).order_by(Struttura.id)).all()
    errori = []
    campi = {c: getattr(g, c) or '' for c in CAMPI_RECAPITI}
    scelte = {'attiva': g.attiva, 'struttura_id': g.struttura_id}
    if request.method == 'POST':
        f = request.form
        campi = {c: ' '.join((f.get(c) or '').split()) if c not in ('prenotazione', 'note')
                 else (f.get(c) or '').strip() for c in CAMPI_RECAPITI}
        for c in CAMPI_RECAPITI:
            if len(campi[c]) > LUNGHEZZE[c]:
                errori.append('«%s» è troppo lungo (al massimo %d caratteri).' % (ETICHETTE[c], LUNGHEZZE[c]))
        if campi['email'] and not pazienti.email_valida(campi['email']):
            errori.append('L\'email non è scritta bene: per esempio prenotazioni@esempio.it.')
        if campi['sito'] and not sito_valido(campi['sito']):
            errori.append('La prenotazione online va scritta come indirizzo web completo, per esempio '
                          'https://www.esempio.it/prenota.')
        locale = intero(f.get('struttura_id')) or None
        if locale is not None and s.get(Struttura, locale) is None:
            locale = None
        scelte = {'attiva': f.get('attiva') == '1', 'struttura_id': locale}
        if not errori:
            with _lucchetto:
                for c, v in campi.items():
                    setattr(g, c, v)
                g.struttura_id = scelte['struttura_id']
                g.attiva = scelte['attiva']
                g.modificato_il = datetime.now()
                segna_cambio(s)
                s.commit()
            flash('Recapiti di %s salvati.' % g.nome, 'ok')
            return redirect(url_for('dovesifa.strutture'))
    conta = s.scalar(select(func.count()).select_from(SedeVoce).where(SedeVoce.struttura_id == g.id)) or 0
    return render_template('dove_struttura.html', sezione='gruppo', g=g, campi=campi, scelte=scelte, errori=errori,
                           locali=locali, conta=conta, etichette=ETICHETTE, colore=colore_sicuro(g.colore))


ETICHETTE = {'nome_breve': 'Nome breve', 'indirizzo': 'Indirizzo', 'citta': 'Città', 'telefono': 'Telefono',
             'telefono2': 'Altro telefono', 'email': 'Email', 'sito': 'Prenotazione online', 'orari': 'Orari',
             'prenotazione': 'Come si prenota', 'note': 'Note per la segreteria'}
