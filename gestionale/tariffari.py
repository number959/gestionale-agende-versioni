# -*- coding: utf-8 -*-
"""Tariffari dei medici (1.12.6, richiesta di Giovanni del 12 novembre 2026: «le schermate dove inserire le tariffe
non funzionano: per agevolarli implementa il tariffario, prendendo i prezzi da questo file»).

Il listino della Cassa ha un prezzo solo per prestazione; i tariffari della clinica invece sono per medico (o per
gruppo di medici) e hanno pacchetti, voci aggiuntive (istologico per sedi, citologico) e note per i pazienti. Qui:

- Cassa -> Tariffari: i tariffari, con il controllo per medico (chi ha il tariffario attivo, chi no, cosa manca);
- «Carica tariffario»: uno o piu' fogli Excel (un tariffario per foglio), letti con `leggi_tariffari`; un'anteprima
  dove si scelgono i medici e le prestazioni a cui corrispondono le voci; i file veri restano fuori dal programma;
- la scheda del tariffario: voci, prezzi, medici, note, si cambia tutto; la stampa;
- nel modulo di prenotazione il prezzo del medico per quella prestazione si propone da solo
  (`prezzi_dei_medici`, in `cassa.mappa_tariffe`): prima la convenzione, poi il tariffario del medico, poi il listino.
"""
import json
import os
import re
import secrets
import threading
import unicodedata
from datetime import datetime
from io import BytesIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from sqlalchemy import select

from modelli import Tariffario, TariffarioMedico, VoceTariffario, Operatore, Prestazione, importo_in_testo
from comune import intero, struttura_scelta

bp = Blueprint('tariffari', __name__)
_fornitore = None
_lucchetto = threading.Lock()

MASSIMO_FILE = 5 * 1024 * 1024
MASSIMO_TARIFFARI = 20               # fogli letti da un file
MASSIMO_VOCI = 400                   # voci di un tariffario
MASSIMO_RIGHE = 1000                 # righe lette da un foglio
RIGHE_VUOTE = 8                      # tante righe vuote di seguito: il foglio e' finito
NUOVE_RIGHE = 3                      # righe vuote nella scheda per aggiungere voci
DURATA_NUOVA = 30                    # minuti di una prestazione creata dall'anteprima

PAROLE_PREZZO = ('prezzo', 'prezzi', 'tariffa', 'tariffe', 'importo', 'costo', 'euro', '€')
PAROLE_MODALITA = ('modalita',)
PAROLE_DETTAGLI = ('dettagli', 'dettaglio', 'protocollo', 'note', 'nota')
PAROLE_SEZIONE = ('sezione', 'categoria')
# le intestazioni che vogliono dire solo «la voce»: non diventano il nome di una sezione
NOMI_GENERICI = {'prestazione', 'prestazioni', 'voce', 'voci', 'descrizione', 'trattamento', 'trattamenti',
                 'prestazione tipologia visita', 'trattamento terapia', 'esame', 'esami', 'visita', 'visite'}
# parole che non contano per riconoscere una prestazione
VUOTE = {'di', 'del', 'della', 'dello', 'dei', 'degli', 'delle', 'con', 'e', 'ed', 'il', 'lo', 'la', 'i', 'gli',
         'le', 'per', 'in', 'a', 'al', 'da', 'un', 'una', 'eventuale', 'specifica', 'specifico'}
SINONIMI = {'egds': 'gastroscopia', 'esofagogastroduodenoscopia': 'gastroscopia', 'gastroscopia': 'gastroscopia',
            'colonscopia': 'colonscopia', 'pancolonscopia': 'colonscopia'}


class ErroreTariffario(Exception):
    pass


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ================================================================ testi
def _testo(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return ' '.join(str(v).split())


def _parole(testo):
    t = unicodedata.normalize('NFKD', testo or '')
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return re.findall(r'[a-z0-9€]+', t)


def chiave(testo):
    """Per confrontare due nomi: minuscolo, senza accenti e punteggiatura."""
    return ' '.join(_parole(testo))


def _normale(testo):
    """«CITOLOGICO» -> «Citologico», «1 SEDE» -> «1 sede»: nei file le maiuscole servono solo da titolo."""
    t = _testo(testo)
    lettere = [c for c in t if c.isalpha()]
    if lettere and all(c.isupper() for c in lettere) and len(lettere) > 2:
        t = t.lower()
        if t[:1].isalpha():                    # «1 SEDE» resta «1 sede»
            t = t[0].upper() + t[1:]
    return t


def _titolo(testo):
    """«TARIFFARIO  GRUPPO FITTIZI» -> «Gruppo Fittizi», «TARIFFARIO DOTT. GALASSO» -> «Dott. Galasso»."""
    t = _testo(testo)
    t = re.sub(r'^(tariffario|tariffe|listino)( prezzi| delle prestazioni| prestazioni)?\b[\s:.-]*', '', t,
               flags=re.I).strip()
    lettere = [c for c in t if c.isalpha()]
    if lettere and all(c.isupper() for c in lettere):
        t = ' '.join(p[:1].upper() + p[1:].lower() for p in t.split())
    return t[:120]


def leggi_importo(v):
    """Un prezzo del file in centesimi: 180, 180.5, «€ 1.000,00», «130,00», «1.500». None se non e' un prezzo."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if v != v or v < 0 or v > 10 ** 7:
            return None
        return int(round(v * 100))
    t = str(v).replace('€', '').replace('EUR', '').replace('euro', '').replace(' ', '').replace('\xa0', '').strip()
    if not t:
        return None
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
        t = t.replace('.', '')
    if not re.fullmatch(r'\d{1,7}(\.\d{1,2})?', t):
        return None
    euro, _, cent = t.partition('.')
    return int(euro) * 100 + int((cent + '00')[:2])


def _e_prezzo(intestazione):
    p = _parole(intestazione)
    return bool(p) and any(x in PAROLE_PREZZO for x in p) or '€' in (intestazione or '')


def _tipo_colonna(intestazione):
    p = _parole(intestazione)
    if not p:
        return None
    if _e_prezzo(intestazione):
        return 'prezzo'
    if any(x in PAROLE_MODALITA for x in p):
        return 'modalita'
    if p[0] in PAROLE_DETTAGLI or 'dettagli' in p:
        return 'dettagli'
    if p[0] in PAROLE_SEZIONE:
        return 'sezione'
    return 'nome'


# ================================================================ lettura
def leggi_tariffari(dati, nome_file=''):
    """I tariffari di un file Excel, uno per foglio: [{'nome', 'foglio', 'voci': [{'sezione', 'nome', 'modalita',
    'importo_cent', 'dettagli'}], 'note', 'avvisi'}]. Si riconoscono la riga delle intestazioni (una colonna con
    «Prezzo», «Tariffa», «Importo» o «€»), il titolo sopra (il nome del tariffario), piu' coppie voce-prezzo nello
    stesso foglio (la seconda diventa una sezione: «Istologico»), le righe di sezione senza prezzo, le righe senza
    nome che continuano la voce di sopra (singola e pacchetto) e le righe «Nota: ...». ErroreTariffario se il file
    non si apre o non ha nessun tariffario."""
    if not dati:
        raise ErroreTariffario('Il file è vuoto.')
    try:
        import openpyxl
        libro = openpyxl.load_workbook(BytesIO(dati), read_only=True, data_only=True)
    except Exception:
        raise ErroreTariffario('Il file non si apre come foglio Excel (.xlsx). Va caricato il tariffario in Excel; '
                               'un PDF si ricopia prima in un foglio Excel, con le colonne Prestazione e Prezzo.')
    try:
        uscita = []
        for foglio in libro.worksheets[:MASSIMO_TARIFFARI]:
            t = _leggi_foglio(foglio, nome_file, len(libro.worksheets))
            if t is not None:
                uscita.append(t)
    finally:
        try:
            libro.close()
        except Exception:
            pass
    if not uscita:
        raise ErroreTariffario('Nel file non c\'è nessun tariffario: serve una riga di intestazioni con una colonna '
                               '«Prestazione» e una «Prezzo» (o «Tariffa»), e sotto le voci con i prezzi.')
    return uscita


def _leggi_foglio(foglio, nome_file, quanti_fogli):
    righe = []
    vuote = 0
    for r in foglio.iter_rows(values_only=True):
        valori = [v for v in r]
        if any(_testo(v) for v in valori):
            vuote = 0
        else:
            vuote += 1
            if vuote >= RIGHE_VUOTE and righe:
                break
        righe.append(valori)
        if len(righe) >= MASSIMO_RIGHE:
            break
    testa = None
    for i, r in enumerate(righe[:30]):
        tipi = [_tipo_colonna(_testo(v)) for v in r]
        if 'prezzo' in tipi and 'nome' in tipi[:tipi.index('prezzo')]:
            testa = i
            break
    if testa is None:
        return None
    intest = [_testo(v) for v in righe[testa]]
    tipi = [_tipo_colonna(x) for x in intest]
    # le coppie voce-prezzo: ogni colonna di prezzo con la colonna di nome piu' vicina alla sua sinistra
    coppie, usate = [], set()
    for j, tipo in enumerate(tipi):
        if tipo != 'prezzo':
            continue
        n = next((k for k in range(j - 1, -1, -1) if tipi[k] == 'nome' and k not in usate), None)
        if n is None:
            continue
        usate.add(n)
        coppie.append((n, j))
    extra = {tipo: tipi.index(tipo) for tipo in ('modalita', 'dettagli', 'sezione') if tipo in tipi}
    # il titolo: il primo testo sopra le intestazioni; poi il nome del foglio, poi quello del file
    titolo = next((_testo(v) for r in righe[:testa] for v in r if _testo(v)), '')
    nome = _titolo(titolo)
    if not nome and chiave(foglio.title) not in ('tariffario', 'foglio1', 'sheet1', 'foglio 1', ''):
        nome = _testo(foglio.title)[:120]
    if not nome:
        nome = _titolo(os.path.splitext(os.path.basename(nome_file or ''))[0].replace('_', ' ')) or 'Tariffario'
    voci, note, avvisi = [], [], []
    sezioni = {}
    for k, (cn, cp) in enumerate(coppie):
        h = intest[cn]
        sezioni[k] = '' if chiave(h) in NOMI_GENERICI else _normale(h)
    ultimo = {}
    for r in righe[testa + 1:]:
        celle = [_testo(v) for v in r]
        if not any(celle):
            continue
        primo = next((c for c in celle if c), '')
        if re.match(r'^(nota|note|n\.b\.)\s*[:.-]', primo, re.I):
            note.append(re.sub(r'^(nota|note|n\.b\.)\s*[:.-]\s*', '', primo, flags=re.I))
            continue
        for k, (cn, cp) in enumerate(coppie):
            nome_v = celle[cn] if cn < len(celle) else ''
            grezzo = r[cp] if cp < len(r) else None
            importo = leggi_importo(grezzo)
            modalita = celle[extra['modalita']] if k == 0 and 'modalita' in extra and extra['modalita'] < len(celle) else ''
            dettagli = celle[extra['dettagli']] if k == 0 and 'dettagli' in extra and extra['dettagli'] < len(celle) else ''
            sezione = celle[extra['sezione']] if k == 0 and 'sezione' in extra and extra['sezione'] < len(celle) else ''
            if sezione:
                sezioni[k] = _normale(re.sub(r'^\s*\d+\s*[.)-]\s*', '', sezione))[:120]
            if nome_v and importo is None and not _testo(grezzo) and not modalita:
                # una riga di sezione: «1. VISITE SPECIALISTICHE»
                sezioni[k] = _normale(re.sub(r'^\s*\d+\s*[.)-]\s*', '', nome_v))[:120]
                continue
            if not nome_v and importo is not None and k in ultimo:
                nome_v = ultimo[k]                         # la riga sotto: «Pacchetto» della stessa voce
            if not nome_v:
                continue
            if importo is None and _tipo_colonna(_testo(grezzo)) == 'prezzo':
                continue                               # le intestazioni ripetute più sotto
            if importo is None:
                if _testo(grezzo):
                    avvisi.append('«%s»: prezzo «%s» non letto.' % (nome_v, _testo(grezzo)))
                continue
            ultimo[k] = nome_v
            if len(voci) >= MASSIMO_VOCI:
                avvisi.append('Più di %d voci: lette le prime %d.' % (MASSIMO_VOCI, MASSIMO_VOCI))
                break
            voci.append({'sezione': sezioni[k][:120], 'nome': _normale(nome_v)[:200], 'modalita': _normale(modalita)[:60],
                         'importo_cent': importo, 'dettagli': dettagli[:300]})
    if not voci:
        return None
    # le voci in ordine di sezione, come nel file: prima tutte quelle della prima coppia
    ordine = {}
    for v in voci:
        ordine.setdefault(v['sezione'], len(ordine))
    voci.sort(key=lambda v: ordine[v['sezione']])
    return {'nome': nome, 'foglio': _testo(foglio.title), 'voci': voci, 'note': '\n'.join(note)[:4000],
            'avvisi': avvisi, 'titolo': titolo}


# ================================================================ proposte
def medici_proposti(s, nome):
    """I medici attivi il cui cognome c'e' nel nome del tariffario («Dott. Galasso», «Gruppo Fittizi»)."""
    parole = set(_parole(nome))
    uscita = []
    for o in s.scalars(select(Operatore).where(Operatore.attivo == True).order_by(Operatore.cognome)):
        cognome = _parole(o.cognome)
        if cognome and all(p in parole for p in cognome):
            uscita.append(o.id)
    return uscita


def _segno(testo):
    p = [SINONIMI.get(x, x) for x in _parole(testo) if x not in VUOTE]
    return set(p)


def prestazione_proposta(voce, prestazioni):
    """La prestazione del programma che corrisponde a una voce: stesso nome (senza maiuscole, accenti,
    articoli), un sinonimo (EGDS e gastroscopia), oppure la sola prestazione le cui parole sono tutte nella voce.
    None se non e' chiaro (i pacchetti non si collegano: il prezzo proposto e' quello della seduta)."""
    if 'pacchett' in chiave(voce.get('modalita', '')):
        return None
    segno = _segno(voce['nome'])
    if not segno:
        return None
    uguali = [p for p in prestazioni if _segno(p.nome) == segno]
    if len(uguali) == 1:
        return uguali[0].id
    dentro = [p for p in prestazioni if _segno(p.nome) and _segno(p.nome) <= segno]
    if dentro:
        massimo = max(len(_segno(p.nome)) for p in dentro)
        migliori = [p for p in dentro if len(_segno(p.nome)) == massimo]
        if len(migliori) == 1 and massimo >= 1:
            return migliori[0].id
    return None


# ================================================================ prezzi
def prezzi_dei_medici(s):
    """{(id medico, id prestazione): (centesimi, nome del tariffario)} dai tariffari attivi: per il modulo di
    prenotazione. Una voce «pacchetto» non vale come prezzo della seduta; con due tariffari attivi per lo stesso
    medico e la stessa prestazione vale il primo (il controllo dei medici lo dice)."""
    uscita = {}
    for t in s.scalars(select(Tariffario).where(Tariffario.attivo == True).order_by(Tariffario.id)):
        for v in t.voci:
            if v.prestazione_id is None or v.importo_cent is None or 'pacchett' in chiave(v.modalita):
                continue
            for oid in sorted(t.id_medici):
                uscita.setdefault((oid, v.prestazione_id), (v.importo_cent, t.nome))
    return uscita


def controllo_medici(s):
    """Il controllo per medico (richiesta di Giovanni: «per le persone di riferimento, fai un controllo se questa
    funzione e' attiva»): per ogni medico attivo i suoi tariffari, quante prestazioni hanno il prezzo che si propone da
    solo, e cosa manca. Piu' gli avvisi sui tariffari senza medici e sui doppi prezzi."""
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    tariffari = s.scalars(select(Tariffario).order_by(Tariffario.nome, Tariffario.id)).all()
    righe = []
    for o in medici:
        suoi = [t for t in tariffari if o.id in t.id_medici]
        attivi = [t for t in suoi if t.attivo]
        prestazioni = {}
        for t in attivi:
            for v in t.voci:
                if v.prestazione_id is not None and v.importo_cent is not None and 'pacchett' not in chiave(v.modalita):
                    prestazioni.setdefault(v.prestazione_id, set()).add((v.importo_cent, t.nome))
        doppi = [s.get(Prestazione, pid).nome for pid, prezzi in prestazioni.items()
                 if len({x[0] for x in prezzi}) > 1 and s.get(Prestazione, pid) is not None]
        if attivi and prestazioni:
            stato, testo = 'attivo', 'Attivo: il prezzo si propone da solo per %d prestazion%s.' % (
                len(prestazioni), 'e' if len(prestazioni) == 1 else 'i')
        elif attivi:
            stato, testo = 'scollegato', ('Attivo, ma nessuna voce è collegata a una prestazione: nella '
                                          'prenotazione il prezzo non si propone (vale il listino).')
        elif suoi:
            stato, testo = 'spento', 'Spento: vale il listino.'
        else:
            stato, testo = 'nessuno', 'Nessun tariffario: vale il listino.'
        if doppi:
            testo += ' Due prezzi diversi per %s: vale quello del primo tariffario.' % ', '.join(sorted(doppi))
        righe.append({'medico': o, 'tariffari': suoi, 'stato': stato, 'testo': testo,
                      'n_prestazioni': len(prestazioni), 'doppi': doppi})
    senza_medici = [t for t in tariffari if t.attivo and not t.medici]
    return {'righe': righe, 'senza_medici': senza_medici,
            'con_tariffario': sum(1 for r in righe if r['stato'] == 'attivo')}


def del_medico(s, o):
    """Il riquadro della scheda del medico (Anagrafiche): il suo tariffario e se e' attivo."""
    if o is None or o.id is None:
        return None
    riga = next((r for r in controllo_medici(s)['righe'] if r['medico'].id == o.id), None)
    tariffari = riga['tariffari'] if riga else [t for t in s.scalars(select(Tariffario)) if o.id in t.id_medici]
    testo = riga['testo'] if riga else ('Medico non attivo: i suoi tariffari non si usano.' if tariffari
                                        else 'Nessun tariffario: vale il listino.')
    return {'titolo': 'Tariffario', 'nota': testo,
            'righe': [{'url': url_for('tariffari.scheda', tid=t.id), 'testo': t.nome,
                       'dettaglio': '%d voci%s' % (len(t.voci), '' if t.attivo else ', spento')} for t in tariffari],
            'azione': {'url': url_for('tariffari.elenco'), 'testo': 'Tariffari'}}


# ================================================================ pagine
def _medici(s):
    return s.scalars(select(Operatore).order_by(Operatore.attivo.desc(), Operatore.cognome, Operatore.nome)).all()


def _prestazioni(s):
    return s.scalars(select(Prestazione).order_by(Prestazione.nome)).all()


@bp.route('/cassa/tariffari', methods=['GET', 'POST'])
def elenco():
    s = ses()
    st, _ = struttura_scelta(s)
    if request.method == 'POST':
        azione = request.form.get('azione')
        if azione == 'carica':
            f = request.files.get('file')
            if f is None or not f.filename:
                flash('Scegliere il file Excel del tariffario.', 'errore')
                return redirect(url_for('tariffari.elenco'))
            dati = f.read(MASSIMO_FILE + 1)
            if len(dati) > MASSIMO_FILE:
                flash('Il file supera 5 MB.', 'errore')
                return redirect(url_for('tariffari.elenco'))
            try:
                leggi_tariffari(dati, f.filename)
            except ErroreTariffario as e:
                flash(str(e), 'errore')
                return redirect(url_for('tariffari.elenco'))
            import importa as caricamenti
            token = secrets.token_hex(16)
            with open(caricamenti.percorso_caricato(token), 'wb') as out:
                out.write(dati)
            with open(caricamenti.percorso_caricato(token, '.json'), 'w', encoding='utf-8') as out:
                json.dump({'nome': (f.filename or '')[-120:], 'tipo': 'tariffario'}, out)
            return redirect(url_for('tariffari.anteprima', token=token))
        if azione == 'nuovo':
            nome = _testo(request.form.get('nome'))[:120] or 'Nuovo tariffario'
            with _lucchetto:
                t = Tariffario(nome=nome, attivo=True)
                s.add(t)
                s.commit()
                tid = t.id
            flash('Tariffario «%s» creato: scegliere i medici e scrivere le voci.' % nome, 'ok')
            return redirect(url_for('tariffari.scheda', tid=tid))
        return redirect(url_for('tariffari.elenco'))
    tariffari = s.scalars(select(Tariffario).order_by(Tariffario.nome, Tariffario.id)).all()
    return render_template('tariffari.html', tariffari=tariffari, controllo=controllo_medici(s), st=st,
                           sid=st.id if st else None, sezione='cassa')


def _caricato(token):
    import importa as caricamenti
    p = caricamenti.percorso_caricato(token)
    if not os.path.exists(p):
        return None, None
    with open(p, 'rb') as f:
        dati = f.read()
    try:
        with open(caricamenti.percorso_caricato(token, '.json'), encoding='utf-8') as f:
            info = json.load(f)
    except (OSError, ValueError):
        info = {}
    if info.get('tipo') != 'tariffario':
        return None, None
    return dati, info.get('nome', '')


def _togli_caricato(token):
    import importa as caricamenti
    for est in ('.dat', '.json'):
        try:
            os.remove(caricamenti.percorso_caricato(token, est))
        except OSError:
            pass


@bp.route('/cassa/tariffari/anteprima/<token>', methods=['GET', 'POST'])
def anteprima(token):
    s = ses()
    st, _ = struttura_scelta(s)
    dati, nome_file = _caricato(token)
    if dati is None:
        flash('Il file caricato non c\'è più: caricarlo di nuovo.', 'errore')
        return redirect(url_for('tariffari.elenco'))
    try:
        trovati = leggi_tariffari(dati, nome_file)
    except ErroreTariffario as e:
        flash(str(e), 'errore')
        return redirect(url_for('tariffari.elenco'))
    prestazioni = _prestazioni(s)
    esistenti = {chiave(t.nome): t for t in s.scalars(select(Tariffario))}
    if request.method == 'POST':
        if request.form.get('azione') == 'annulla':
            _togli_caricato(token)
            flash('Caricamento annullato: niente è cambiato.', 'ok')
            return redirect(url_for('tariffari.elenco'))
        validi_medici = {o.id for o in _medici(s)}
        validi_prestazioni = {p.id for p in prestazioni}
        fatti, nuove = [], 0
        with _lucchetto:
            for i, t in enumerate(trovati):
                if request.form.get('carica_%d' % i) != '1':
                    continue
                nome = _testo(request.form.get('nome_%d' % i))[:120] or t['nome']
                medici = [x for x in (intero(v) for v in request.form.getlist('medici_%d' % i)) if x in validi_medici]
                esistente = next((x for k, x in esistenti.items() if k == chiave(nome)), None)
                if esistente is not None:
                    tar = esistente
                    tar.voci.clear()
                    tar.medici.clear()
                    s.flush()
                else:
                    tar = Tariffario(nome=nome, attivo=True)
                    s.add(tar)
                tar.nome, tar.attivo = nome, True
                tar.note, tar.origine, tar.aggiornato_il = t['note'], (nome_file or '')[-200:], datetime.now()
                for oid in sorted(set(medici)):
                    tar.medici.append(TariffarioMedico(operatore_id=oid))
                for j, v in enumerate(t['voci']):
                    scelta = request.form.get('prestazione_%d_%d' % (i, j), '')
                    pid = intero(scelta) if scelta not in ('', 'nuova') else None
                    if pid is not None and pid not in validi_prestazioni:
                        pid = None
                    if scelta == 'nuova':
                        p = s.scalars(select(Prestazione).where(Prestazione.nome == v['nome'][:80])).first()
                        if p is None:
                            p = Prestazione(nome=v['nome'][:80], durata_min=DURATA_NUOVA)
                            s.add(p)
                            s.flush()
                            nuove += 1
                            validi_prestazioni.add(p.id)
                        pid = p.id
                    tar.voci.append(VoceTariffario(sezione=v['sezione'], nome=v['nome'], modalita=v['modalita'],
                                                   importo_cent=v['importo_cent'], dettagli=v['dettagli'],
                                                   prestazione_id=pid, ordine=j))
                s.flush()
                fatti.append('%s (%d voci, %d medic%s)' % (nome, len(t['voci']), len(medici),
                                                          'o' if len(medici) == 1 else 'i'))
            s.commit()
        _togli_caricato(token)
        if fatti:
            flash('Tariffari caricati: %s.%s' % ('; '.join(fatti), (' Prestazioni nuove create: %d (durata %d minuti, '
                  'da controllare in Anagrafiche).' % (nuove, DURATA_NUOVA)) if nuove else ''), 'ok')
        else:
            flash('Nessun tariffario scelto: niente è cambiato.', 'avviso')
        return redirect(url_for('tariffari.elenco'))
    proposte = []
    for t in trovati:
        esistente = esistenti.get(chiave(t['nome']))
        proposte.append({'t': t, 'medici': set(medici_proposti(s, t['nome'] + ' ' + t.get('titolo', ''))),
                         'esistente': esistente,
                         'prestazioni': [prestazione_proposta(v, prestazioni) for v in t['voci']]})
    return render_template('tariffari_anteprima.html', proposte=proposte, medici=_medici(s), prestazioni=prestazioni,
                           token=token, nome_file=nome_file, importo_in_testo=importo_in_testo, st=st,
                           sid=st.id if st else None, sezione='cassa')


@bp.route('/cassa/tariffari/<int:tid>', methods=['GET', 'POST'])
def scheda(tid):
    s = ses()
    st, _ = struttura_scelta(s)
    t = s.get(Tariffario, tid)
    if t is None:
        abort(404)
    prestazioni = _prestazioni(s)
    if request.method == 'POST':
        f = request.form
        if f.get('azione') == 'elimina':
            with _lucchetto:
                nome = t.nome
                s.delete(t)
                s.commit()
            flash('Tariffario «%s» eliminato.' % nome, 'ok')
            return redirect(url_for('tariffari.elenco'))
        errori = []
        validi_medici = {o.id for o in _medici(s)}
        validi_prestazioni = {p.id for p in prestazioni}
        nome = _testo(f.get('nome'))[:120]
        if not nome:
            errori.append('Il tariffario ha bisogno di un nome.')
        ids, sezioni, nomi = f.getlist('voce_id'), f.getlist('sezione'), f.getlist('voce')
        modalita, prezzi, dettagli = f.getlist('modalita'), f.getlist('prezzo'), f.getlist('dettagli')
        collegate, togli = f.getlist('prestazione'), set(f.getlist('togli'))
        voci = []
        for k in range(len(nomi)):
            def campo(lista, n):
                return _testo(lista[k])[:n] if k < len(lista) else ''
            vid = campo(ids, 20)
            if vid and vid in togli:
                continue
            nome_v, prezzo = campo(nomi, 200), campo(prezzi, 20)
            if not nome_v and not prezzo:
                continue                       # riga vuota (o svuotata: la voce si toglie)
            importo = leggi_importo(prezzo) if prezzo else None
            if not nome_v:
                errori.append('Riga %d: manca il nome della voce.' % (k + 1))
                continue
            if prezzo and importo is None:
                errori.append('«%s»: prezzo «%s» non valido.' % (nome_v, prezzo))
                continue
            pid = intero(campo(collegate, 20))
            voci.append(dict(sezione=campo(sezioni, 120), nome=nome_v, modalita=campo(modalita, 60),
                             importo_cent=importo, dettagli=campo(dettagli, 300),
                             prestazione_id=pid if pid in validi_prestazioni else None, ordine=len(voci)))
        if errori:
            for e in errori:
                flash(e, 'errore')
            return redirect(url_for('tariffari.scheda', tid=tid))
        with _lucchetto:
            t.nome, t.attivo = nome, f.get('attivo') == '1'
            t.note, t.aggiornato_il = (f.get('note') or '').strip()[:4000], datetime.now()
            t.medici.clear()
            t.voci.clear()
            s.flush()
            for oid in sorted({x for x in (intero(v) for v in f.getlist('medici')) if x in validi_medici}):
                t.medici.append(TariffarioMedico(operatore_id=oid))
            for v in voci:
                t.voci.append(VoceTariffario(**v))
            s.commit()
        flash('Tariffario «%s» salvato: %d voci.' % (nome, len(voci)), 'ok')
        return redirect(url_for('tariffari.scheda', tid=tid))
    return render_template('tariffario.html', t=t, medici=_medici(s), prestazioni=prestazioni,
                           nuove=NUOVE_RIGHE, controllo=controllo_medici(s), st=st, sid=st.id if st else None,
                           sezione='cassa')


def sezioni_di(t):
    """[(sezione, [voci])] nell'ordine del tariffario, per la stampa."""
    uscita = []
    for v in t.voci:
        if not uscita or uscita[-1][0] != (v.sezione or ''):
            uscita.append((v.sezione or '', []))
        uscita[-1][1].append(v)
    return uscita


@bp.route('/cassa/tariffari/<int:tid>/stampa')
def stampa(tid):
    s = ses()
    st, _ = struttura_scelta(s)
    t = s.get(Tariffario, tid)
    if t is None:
        abort(404)
    return render_template('tariffario_stampa.html', t=t, sezioni=sezioni_di(t), st=st, sid=st.id if st else None,
                           con_modalita=any(v.modalita for v in t.voci), con_dettagli=any(v.dettagli for v in t.voci))
