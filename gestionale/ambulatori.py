# -*- coding: utf-8 -*-
"""Ambulatori (dalla 1.12): chi sta in quale stanza, calcolato dai turni dei
medici, e due fogli da stampare o mandare che prima si compilavano a mano.

1. La MATRICE della settimana («Matrice turni ambulatori e disponibilità
   integrative», chiesta dalla direzione sanitaria): righe = stanze, colonne =
   giorni divisi in mattina e pomeriggio. In ogni cella chi occupa la stanza
   con l'orario; una cella senza nessuno dice DISPONIBILE, in verde; le ore
   avanzate («libero 12:00-14:00») sono in verde anche loro. La pagina e' anche
   la PIANIFICAZIONE: dal «+» di una cella si mette un medico (ogni settimana o
   quel giorno solo), dal nome si apre il turno, dalla «x» si toglie da quella
   settimana in poi.
2. La PROGRAMMAZIONE del mese (il foglio «programmazione ambulatori» di
   un'altra struttura del gruppo): per specialita', medico, giorno della
   settimana, le date del mese in cui viene davvero, orario, stanza e note.

Perche' calcolate e non compilate: il foglio fatto a mano va riscritto ogni
mese e si allontana dall'agenda (le date in cui il medico non viene,
«no seduta 2-9-16», le scrive una persona). Qui tutto nasce dai turni, dalle
assenze e dalle chiusure gia' nel programma: le date del mese sono quelle in
cui il medico c'e' davvero, le note dicono da sole i giorni saltati e perche',
e i due fogli non possono dire una cosa diversa dall'agenda. Si ripetono
con un clic, per ogni mese e ogni settimana.

Mattina e pomeriggio si dividono alle META (14:00): la mattina va
dall'apertura della struttura alle 14, il pomeriggio dalle 14 alla chiusura.
Un'ora libera (MINIMO_LIBERO) o piu' dentro una mezza giornata occupata si
segnala come disponibilita'."""
import re
from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from sqlalchemy import and_, func, or_, select

import calendario
import servizi
from anagrafiche import Modulo, stanza_gia_assegnata
from comune import (FORMATO_ORA, FORMATO_ORE, FORMATO_PERCENTO, apri_foglio_excel, data_da, destinazione_sicura,
                    imposta_stampa_excel, intero, json_sicuro, mese_da, scarica_excel, stile_intestazione_excel,
                    struttura_scelta, tabella_excel, testo_excel, una_pagina_se_manca_poco)
from modelli import STATI_ATTIVI, Appuntamento, Operatore, Risorsa, Turno

bp = Blueprint('ambulatori', __name__, url_prefix='/ambulatori')
_fornitore = None
_lucchetto = None

META = time(14, 0)                 # la mattina finisce, il pomeriggio comincia
MINIMO_LIBERO = 60                 # minuti liberi da segnalare dentro una mezza giornata occupata
DESTINATARIO = 'Direttore Sanitario'
COMPILATO_DA = 'Segreteria'
TITOLO_MATRICE = 'MATRICE TURNI AMBULATORI E DISPONIBILITÀ INTEGRATIVE'
TITOLO_PROGRAMMAZIONE = 'PROGRAMMAZIONE AMBULATORI'
TIPO_SALA = 'SALA_OPERATORIA'
SALA_OPERATORIA = 'Sala operatoria'            # il nome della parte della sala nella matrice e nella programmazione
GIORNO_SOLO_SALA = 'solo sala operatoria'      # gli ambulatori in un giorno aperto solo per la sala
SENZA_SPECIALITA = 'Senza specialità'


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ================================================================ orari
def _minuti(t):
    return t.hour * 60 + t.minute


def _ora(minuti):
    return time(minuti // 60, minuti % 60)


def fascia(da, a):
    return '%s–%s' % (da.strftime('%H:%M'), a.strftime('%H:%M'))


def mezze_giornate(st):
    """Le due meta' della giornata della struttura: mattina (apertura–META) e
    pomeriggio (META–chiusura). Una struttura che apre dopo le 14 ha solo il
    pomeriggio; una che chiude prima, solo la mattina."""
    apertura, chiusura = st.apertura, st.chiusura
    meta = []
    for nome, da, a in (('mattina', apertura, min(META, chiusura)), ('pomeriggio', max(META, apertura), chiusura)):
        if da < a:
            meta.append({'nome': nome, 'etichetta': nome.capitalize(), 'da': da, 'a': a})
    return meta or [{'nome': 'giornata', 'etichetta': 'Giornata', 'da': apertura, 'a': chiusura}]


def buchi(presenze, da, a, minimo=MINIMO_LIBERO):
    """Le ore libere [da, a) non coperte dalle presenze, lunghe almeno
    'minimo' minuti: le disponibilita' da offrire."""
    occupati = sorted((_minuti(p['da']), _minuti(p['a'])) for p in presenze)
    liberi, cursore = [], _minuti(da)
    for inizio, fine in occupati:
        if inizio - cursore >= minimo:
            liberi.append((_ora(cursore), _ora(inizio)))
        cursore = max(cursore, fine)
    if _minuti(a) - cursore >= minimo:
        liberi.append((_ora(cursore), a))
    return liberi


# ============================================================== matrice
def stanze_della(st):
    """Le stanze attive della struttura, nel loro ordine, senza le sale
    operatorie: quelle si programmano nella pagina Sala, e nella matrice
    degli ambulatori una sala sempre «disponibile» confonderebbe."""
    return [r for r in st.risorse if r.attiva and r.tipo != TIPO_SALA]


def sale_della(st):
    """Le sale operatorie attive della struttura, nel loro ordine. Dalla 1.12.3 la matrice della settimana e
    la programmazione del mese le mostrano in una parte loro, sotto gli ambulatori: chi opera e quanti
    interventi, mai nei conti delle mezze giornate libere degli ambulatori."""
    return [r for r in st.risorse if r.attiva and r.tipo == TIPO_SALA]


def interventi_attivi(ses, sale_ids, dal, al):
    """Gli interventi attivi (prenotati, confermati, arrivati) nelle sale indicate, dal giorno 'dal' al giorno
    'al' compresi: quelli che occupano la sala. I disdetti e i non presentati non contano."""
    if not sale_ids:
        return []
    return ses.scalars(select(Appuntamento).where(
        Appuntamento.risorsa_id.in_(list(sale_ids)), Appuntamento.stato.in_(STATI_ATTIVI),
        Appuntamento.inizio >= datetime.combine(dal, time(0)),
        Appuntamento.inizio < datetime.combine(al + timedelta(days=1), time(0)))
        .order_by(Appuntamento.inizio)).all()


def intervento_nella_meta(x, meta, k):
    """Se l'intervento x comincia nella mezza giornata k: la prima comincia a mezzanotte e l'ultima finisce a
    mezzanotte, cosi' anche un intervento prima dell'apertura o dopo la chiusura sta in una delle due."""
    ora = x.inizio.time()
    return (k == 0 or ora >= meta[k]['da']) and (k == len(meta) - 1 or ora < meta[k]['a'])


def matrice(ses, lunedi, st, tipo=False):
    """La matrice della settimana che comincia il lunedi: per ogni stanza
    attiva e ogni mezza giornata dei giorni di apertura, chi c'e' (turni
    effettivi: medico presente, struttura aperta), le ore libere, gli assenti
    e le chiusure. Con tipo=True e' la settimana tipo: solo i turni che si
    ripetono, senza assenze, chiusure e festivi, come sara' una settimana
    qualsiasi."""
    giorni_tutti = [lunedi + timedelta(days=i) for i in range(7)]
    regole = servizi.Regole(ses, giorni_tutti[0], giorni_tutti[-1])
    stanze = stanze_della(st)
    sale = sale_della(st)
    ids = {r.id for r in stanze}
    ids_sale = {r.id for r in sale}

    def con_turni(g, quali):
        return any(t.risorsa_id in quali and not (tipo and servizi.e_di_un_giorno(t)) for t in regole.turni_validi(g, st))

    # i giorni di apertura, quelli con un turno in una stanza e quelli con un turno o un intervento in sala
    # (1.12.3); in un giorno che c'e' solo per la sala (un sabato di interventi) gli ambulatori sono chiusi, non
    # DISPONIBILI
    interventi = [] if tipo else interventi_attivi(ses, ids_sale, giorni_tutti[0], giorni_tutti[-1])
    con_interventi = {x.inizio.date() for x in interventi}
    giorni = [g for g in giorni_tutti if g.weekday() in st.giorni_aperti or con_turni(g, ids) or con_turni(g, ids_sale)
              or g in con_interventi]
    solo_sala = {g for g in giorni if g.weekday() not in st.giorni_aperti and not con_turni(g, ids)}
    meta = mezze_giornate(st)
    info = {g: regole.giorno(g, st) for g in giorni}
    righe, righe_sale, libere, parziali = [], [], 0, 0
    for r in stanze + sale:
        di_sala = r.id in ids_sale
        celle = []
        for g in giorni:
            i = info[g]
            if tipo:
                turni = [t for t in regole.turni_validi(g, st, r.id) if not servizi.e_di_un_giorno(t)]
                assenti, chiuso = [], None
            else:
                turni = regole.turni_effettivi(g, st, r.id, i)
                assenti = [(t.operatore, i['assenze'][t.operatore_id], t)
                           for t in regole.turni_validi(g, st, r.id) if t.operatore_id in i['assenze']]
                chiuso = i['chiusura'] or (i['festivo'] if i['chiude_festivo'] else None)
            if g in solo_sala and not di_sala:
                chiuso = chiuso or GIORNO_SOLO_SALA
            for k, m in enumerate(meta):
                # in sala la prima mezza giornata comincia a mezzanotte e l'ultima finisce a mezzanotte, come per
                # gli interventi (intervento_nella_meta): un turno prima dell'apertura o dopo la chiusura si vede
                da_m = time(0) if di_sala and k == 0 else m['da']
                fino = None if di_sala and k == len(meta) - 1 else m['a']
                presenze = sorted(({'turno': t, 'operatore': t.operatore, 'da': max(t.ora_inizio, da_m),
                                    'a': t.ora_fine if fino is None else min(t.ora_fine, fino)}
                                   for t in turni if (fino is None or t.ora_inizio < fino) and da_m < t.ora_fine),
                                  key=lambda p: (p['da'], p['operatore'].cognome))
                # in un festivo in cui la struttura chiude resta solo chi ha un turno di quel
                # giorno: la sua mezza giornata e' occupata, l'altra resta chiusa
                chiuso_qui = chiuso if not presenze else None
                # le ore libere si elencano solo in una mezza giornata occupata: una tutta
                # libera dice DISPONIBILE e basta (in sala niente ore libere: si guardano gli interventi)
                vuoti = [] if chiuso_qui or not presenze or di_sala else buchi(presenze, m['da'], m['a'])
                cella = {'data': g, 'meta': m, 'presenze': presenze, 'libere': vuoti, 'chiuso': chiuso_qui,
                         'assenti': [x for x in assenti if (fino is None or x[2].ora_inizio < fino) and da_m < x[2].ora_fine],
                         'tutta_libera': not presenze and not chiuso_qui,
                         'proposta': (vuoti[0] if vuoti else (m['da'], m['a']))}
                if di_sala:
                    # gli interventi della mezza giornata; chi opera senza un turno in quella mezza giornata si dice
                    # per nome, e la sala e' «libera» solo senza turni e senza interventi
                    qui = [x for x in interventi if x.risorsa_id == r.id and x.inizio.date() == g
                           and intervento_nella_meta(x, meta, k)]
                    in_turno = {p['operatore'].id for p in presenze}
                    cella['interventi'] = len(qui)
                    # quanti ne fa ciascun chirurgo in questa mezza giornata (1.12.5, richiesta di Giovanni: «gli
                    # interventi si assegnano al medico, cosi' si capisce quanti ne fa quella giornata»)
                    cella['per_chirurgo'] = {}
                    for x in qui:
                        if x.operatore_id is not None:
                            cella['per_chirurgo'][x.operatore_id] = cella['per_chirurgo'].get(x.operatore_id, 0) + 1
                    cella['senza_chirurgo'] = sum(1 for x in qui if x.operatore_id is None)
                    cella['senza_turno'] = sorted({x.operatore for x in qui
                                                   if x.operatore is not None and x.operatore_id not in in_turno},
                                                  key=lambda o: o.etichetta)
                    cella['tutta_libera'] = cella['tutta_libera'] and not qui
                elif cella['tutta_libera']:
                    libere += 1
                elif vuoti:
                    parziali += 1
                celle.append(cella)
        (righe_sale if di_sala else righe).append({'risorsa': r, 'celle': celle})
    return {'lunedi': lunedi, 'giorni': giorni, 'meta': meta, 'righe': righe, 'sale': righe_sale, 'info': info,
            'tipo': tipo, 'libere': libere, 'parziali': parziali, 'solo_sala': solo_sala,
            'interventi': sum(c['interventi'] for x in righe_sale for c in x['celle'])}


# ======================================================= programmazione
def _gruppo(specialita):
    s = (specialita or '').strip()
    return s[:1].upper() + s[1:] if s else SENZA_SPECIALITA


def _il(giorno):
    """'il 2', ma 'l\'1', 'l\'8', 'l\'11'."""
    return ("l'%d" if giorno in (1, 8, 11) else 'il %d') % giorno


def _dal(giorno):
    return servizi.dal_giorno(giorno)


def _al(giorno):
    return servizi.al_giorno(giorno)


def _elenco_giorni(giorni):
    """'il 2, il 9 e il 16' (con l'apostrofo davanti a 1, 8 e 11)."""
    testi = [_il(g.day) for g in giorni]
    return testi[0] if len(testi) == 1 else ', '.join(testi[:-1]) + ' e ' + testi[-1]


def motivo_assenza(motivo):
    """'assente: ferie'; senza motivo solo 'assente'."""
    m = (motivo or '').strip()
    return 'assente' if not m or m.lower() == 'assente' else 'assente: %s' % m.lower()


def motivo_chiusura(motivo):
    """'chiusa: manutenzione'; senza motivo solo 'chiusa'."""
    m = (motivo or '').strip()
    return 'chiusa' if not m or m.lower() == 'chiusura' else 'chiusa: %s' % m.lower()


def programmazione(ses, anno, mese, st):
    """La programmazione del mese: una riga per ogni turno delle stanze attive
    della struttura che tocca il mese, con le date in cui il medico viene
    davvero (niente assenze, chiusure, festivi in cui si chiude) e le note che
    spiegano i giorni saltati. Raggruppata per specialita' del medico, poi per
    medico, giorno della settimana e ora."""
    giorni = calendario.giorni_del_mese(anno, mese)
    primo, ultimo = giorni[0], giorni[-1]
    regole = servizi.Regole(ses, primo, ultimo)
    info = {g: regole.giorno(g, st) for g in giorni}
    stanze = {r.id: r for r in stanze_della(st)}
    # 1.12.3: anche la sala operatoria, in una parte sua; gli interventi attivi del mese per contarli
    sale = {r.id: r for r in sale_della(st)}
    interventi = interventi_attivi(ses, sale, primo, ultimo)
    contati = set()
    righe, righe_sala = [], []
    # i turni in ordine di ora di inizio: ogni intervento va a un turno solo, il primo che lo contiene (lo stesso
    # chirurgo puo' avere due turni sovrapposti, per esempio uno di un giorno messo sopra quello di ogni settimana)
    for t in sorted(regole.turni, key=lambda t: (t.ora_inizio, t.id)):
        if t.risorsa_id not in stanze and t.risorsa_id not in sale:
            continue
        di_sala = t.risorsa_id in sale
        date_valide = [g for g in giorni if t.vale_il(g)]
        if not date_valide:
            continue
        singolo = servizi.e_di_un_giorno(t)
        presenti, saltate = [], []
        for g in date_valide:
            i = info[g]
            if t.operatore_id in i['assenze']:
                saltate.append((g, motivo_assenza(i['assenze'][t.operatore_id])))
            elif i['chiusura']:
                saltate.append((g, motivo_chiusura(i['chiusura'])))
            elif i['chiude_festivo'] and not singolo:
                saltate.append((g, motivo_chiusura(i['festivo'])))
            else:
                presenti.append(g)
        note = []
        if singolo:
            note.append('un giorno solo')
        else:
            if t.valido_da and t.valido_da > primo:
                note.append(_dal(t.valido_da.day))
            if t.valido_a and t.valido_a < ultimo:
                note.append('fino ' + _al(t.valido_a.day))
        motivi = {}
        for g, motivo in saltate:
            motivi.setdefault(motivo, []).append(g)
        for motivo, quando in motivi.items():
            note.append('non %s (%s)' % (_elenco_giorni(quando), motivo))
        if not presenti:
            note.append('nessuna seduta nel mese')
        if t.passo_proprio:
            note.append('fasce da %d minuti' % t.passo_proprio)
        riga = {'turno': t, 'operatore': t.operatore, 'specialita': _gruppo(t.operatore.specialita),
                'giorno': t.giorno_settimana, 'date': presenti, 'saltate': saltate, 'singolo': singolo,
                'ora_inizio': t.ora_inizio, 'ora_fine': t.ora_fine,
                'risorsa': sale[t.risorsa_id] if di_sala else stanze[t.risorsa_id], 'note': note}
        if di_sala:
            # gli interventi del chirurgo in quella sala, nelle date e nelle ore di questo turno
            date_turno = set(presenti)
            suoi = [x for x in interventi if x.risorsa_id == t.risorsa_id and x.operatore_id == t.operatore_id
                    and x.inizio.date() in date_turno and t.ora_inizio <= x.inizio.time() < t.ora_fine
                    and x.id not in contati]
            contati.update(x.id for x in suoi)
            riga['interventi'] = len(suoi)
            if suoi:
                note.append('%d intervent%s' % (len(suoi), 'o' if len(suoi) == 1 else 'i'))
            righe_sala.append(riga)
        else:
            righe.append(riga)
    righe.sort(key=lambda r: (r['specialita'] == SENZA_SPECIALITA, r['specialita'].lower(),
                              r['operatore'].cognome.lower(), (r['operatore'].nome or '').lower(),
                              r['giorno'], r['ora_inizio'], r['risorsa'].ordine, r['risorsa'].nome))
    righe_sala.sort(key=lambda r: (r['risorsa'].ordine, r['risorsa'].nome, r['operatore'].cognome.lower(),
                                   (r['operatore'].nome or '').lower(), r['giorno'], r['ora_inizio']))
    gruppi = []
    for r in righe:
        if not gruppi or gruppi[-1]['specialita'].casefold() != r['specialita'].casefold():
            gruppi.append({'specialita': r['specialita'], 'righe': []})
        gruppi[-1]['righe'].append(r)
    # il calendario: giorno per giorno, chi c'e' in quale stanza, poi la sala con i suoi interventi
    calendario_mese = []
    for g in giorni:
        effettivi = regole.turni_effettivi(g, st, None, info[g])
        presenze = sorted((t for t in effettivi if t.risorsa_id in stanze),
                          key=lambda t: (stanze[t.risorsa_id].ordine, t.ora_inizio))
        in_sala = sorted((t for t in effettivi if t.risorsa_id in sale),
                         key=lambda t: (sale[t.risorsa_id].ordine, sale[t.risorsa_id].nome, t.ora_inizio, t.id))
        del_giorno = [x for x in interventi if x.inizio.date() == g]
        voci_sala, presi = [], set()
        for t in in_sala:
            suoi = [x for x in del_giorno if x.risorsa_id == t.risorsa_id and x.operatore_id == t.operatore_id
                    and t.ora_inizio <= x.inizio.time() < t.ora_fine and x.id not in presi]
            presi.update(x.id for x in suoi)
            voci_sala.append({'turno': t, 'risorsa': t.risorsa, 'operatore': t.operatore, 'interventi': len(suoi)})
        # gli interventi del giorno fuori dai turni: una riga per sala e chirurgo, senza orario
        resto = {}
        for x in del_giorno:
            if x.id not in presi:
                resto.setdefault((x.risorsa_id, x.operatore_id), []).append(x)
        for (rid, oid), lista in sorted(resto.items(), key=lambda kv: (sale[kv[0][0]].ordine, sale[kv[0][0]].nome,
                                                                         kv[1][0].inizio)):
            voci_sala.append({'turno': None, 'risorsa': sale[rid], 'operatore': lista[0].operatore,
                              'interventi': len(lista)})
        calendario_mese.append({'data': g, 'info': info[g], 'presenze': presenze, 'sala': voci_sala,
                                'interventi_sala': len(del_giorno)})
    fuori = [x for x in interventi if x.id not in contati]
    # chi ha operato fuori dai suoi turni (o senza turni): una riga per chirurgo e sala, con le date
    n_turni = len(righe_sala)
    senza = {}
    for x in fuori:
        senza.setdefault((x.risorsa_id, x.operatore_id), []).append(x)
    for (rid, oid), lista in senza.items():
        o = lista[0].operatore
        date_f = sorted({x.inizio.date() for x in lista})
        righe_sala.append({'turno': None, 'operatore': o, 'specialita': _gruppo(o.specialita if o else ''),
                           'giorno': None, 'date': date_f, 'saltate': [], 'singolo': False, 'ora_inizio': None,
                           'ora_fine': None, 'risorsa': sale[rid], 'interventi': len(lista), 'senza_turno': True,
                           'note': ['%d intervent%s fuori dai turni' % (len(lista), 'o' if len(lista) == 1 else 'i')]})
    righe_sala.sort(key=lambda r: (r['risorsa'].ordine, r['risorsa'].nome,
                                   (r['operatore'].cognome if r['operatore'] else '').lower(),
                                   ((r['operatore'].nome if r['operatore'] else '') or '').lower(),
                                   r['giorno'] if r['giorno'] is not None else 9, r['ora_inizio'] or time(0)))
    return {'primo': primo, 'ultimo': ultimo, 'righe': righe, 'gruppi': gruppi, 'calendario': calendario_mese,
            'medici': len({r['operatore'].id for r in righe}),
            'sala': {'righe': righe_sala, 'turni': n_turni,
                     'chirurghi': len({r['operatore'].id for r in righe_sala if r['operatore'] is not None}),
                     'interventi': len(interventi), 'fuori_turno': len(fuori), 'sale': list(sale.values())}}


# ================================================================ Excel
BLU = '154381'
VERDE_PIENO = 'C6EFCE'      # DISPONIBILE
VERDE_CHIARO = 'EAF5E3'     # ore libere dentro una mezza giornata occupata
GRIGIO = 'E7E9E6'
ARANCIO = 'B35F16'
AZZURRO_SALA = 'E8EEF7'     # la riga che apre la parte della sala operatoria
_sottile = Side(style='thin', color='9AA5AD')
BORDO = Border(left=_sottile, right=_sottile, top=_sottile, bottom=_sottile)
_spesso = Side(style='medium', color=BLU)


def _intestazione(c, testo):
    """L'intestazione nello stile comune degli Excel (comune.stile_intestazione_excel)."""
    stile_intestazione_excel(c, testo)
    c.border = BORDO


def _stampa(ws, righe_titolo, orizzontale=True, st=None, periodo=''):
    """A4 che sta in larghezza, righe ripetute, testata e pie' di pagina comuni."""
    imposta_stampa_excel(ws, orizzontale, righe_titolo, None, st, periodo)


def _titolo(ws, riga, testo, colonne, dimensione=14):
    c = ws.cell(riga, 1, testo)
    c.font = Font(name='Calibri', size=dimensione, bold=True, color=BLU)
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    c.alignment = Alignment(horizontal='left', vertical='center')


def _altezza_riga(ws, riga, celle):
    """L'altezza di una riga della matrice: una riga di testo ogni 22 caratteri circa, in una colonna larga 19."""
    righe_testo = 1
    for k in range(celle):
        v = ws.cell(riga, 2 + k).value or ''
        righe_testo = max(righe_testo, sum(max(1, -(-len(pezzo) // 22)) for pezzo in str(v).split('\n')))
    ws.row_dimensions[riga].height = max(30, 15 * righe_testo)


def conta_interventi(n):
    return '%d intervent%s' % (n, 'o' if n == 1 else 'i')


def testo_cella_sala(cella):
    """Il testo di una mezza giornata della sala operatoria, uguale nella pagina e nell'Excel: i chirurghi in
    turno, chi opera senza un turno, gli assenti; «sala libera» senza turni e senza interventi. Dalla 1.12.5 gli
    interventi sono contati per chirurgo: il numero sta subito sotto il chirurgo che li fa (con un chirurgo solo,
    come prima: il nome e poi «2 interventi»); quelli senza chirurgo in fondo."""
    per = cella.get('per_chirurgo')
    detti = set()
    testi = []

    def suoi(o):
        if per is not None and o is not None and per.get(o.id) and o.id not in detti:
            detti.add(o.id)
            testi.append(conta_interventi(per[o.id]))
    if cella['chiuso']:
        testi.append('CHIUSO: %s' % cella['chiuso'])
    else:
        for p in cella['presenze']:
            testi.append('%s %s' % (p['operatore'].etichetta, fascia(p['da'], p['a']).replace('–', '-')))
            suoi(p['operatore'])
        if cella['tutta_libera']:
            testi.append('sala libera')
    for o in cella.get('senza_turno') or []:
        testi.append('%s, senza turno' % o.etichetta)
        suoi(o)
    n = cella.get('interventi') or 0
    if per is None and n:
        testi.append(conta_interventi(n))
    elif cella.get('senza_chirurgo'):
        testi.append('%s senza chirurgo' % conta_interventi(cella['senza_chirurgo']))
    if not cella['chiuso']:
        testi += ['(%s %s)' % (o.etichetta, motivo_assenza(motivo)) for o, motivo, _ in cella['assenti']]
    return '\n'.join(testi)


def _carattere(**altro):
    """Il carattere dei fogli degli ambulatori e della sala: Calibri 11 come le celle senza stile. Fino alla 1.12.3
    i grassetti e i corsivi non avevano il nome del carattere: Excel metteva il suo, altri programmi un carattere con
    le grazie (1.12.4)."""
    altro.setdefault('name', 'Calibri')
    altro.setdefault('size', 11)
    return Font(**altro)


def _settimana_testo(vista):
    lunedi = vista['lunedi']
    domenica = lunedi + timedelta(days=6)
    return '%s %s %s %s %d' % (servizi.dal_giorno(lunedi.day), servizi.MESI[lunedi.month - 1],
                               servizi.al_giorno(domenica.day), servizi.MESI[domenica.month - 1], domenica.year)


def _testa_settimana(ws, r0, vista, prima):
    """Le due righe di intestazione della settimana: il giorno sopra le sue mezze giornate."""
    giorni, meta = vista['giorni'], vista['meta']
    _intestazione(ws.cell(r0, 1), prima)
    ws.merge_cells(start_row=r0, start_column=1, end_row=r0 + 1, end_column=1)
    for k, g in enumerate(giorni):
        c1 = 2 + k * len(meta)
        i = vista['info'][g]
        testo = '%s %d/%d' % (servizi.GIORNI[g.weekday()].capitalize(), g.day, g.month)
        if not vista['tipo'] and (i['chiusura'] or i['festivo']):
            testo += '\n%s' % testo_excel(i['chiusura'] or i['festivo'])
        if vista['tipo']:
            testo = servizi.GIORNI[g.weekday()].capitalize()
        _intestazione(ws.cell(r0, c1), testo)
        if len(meta) > 1:
            ws.merge_cells(start_row=r0, start_column=c1, end_row=r0, end_column=c1 + len(meta) - 1)
        for j, m in enumerate(meta):
            _intestazione(ws.cell(r0 + 1, c1 + j), fascia(m['da'], m['a']).replace('–', '-'))
            ws.column_dimensions[get_column_letter(c1 + j)].width = 19
    ws.column_dimensions['A'].width = 20
    ws.row_dimensions[r0].height = 30


def excel_matrice(st, vista, adesso=None):
    """Il file della matrice per la direzione sanitaria: solo gli ambulatori (dalla 1.12.3 la sala operatoria
    ha i suoi file e il suo foglio, vedi esportazioni.py)."""
    wb = Workbook()
    foglio_matrice(wb.active, st, vista, adesso)
    return wb


def foglio_matrice(ws, st, vista, adesso=None):
    """Il foglio della matrice: intestazione con struttura, titolo, settimana,
    destinatario e chi lo compila; la tabella stanze x mezze giornate; la
    legenda e le righe per le firme."""
    adesso = adesso or datetime.now()
    ws.title = 'Matrice'
    # i giorni che ci sono solo per la sala (un sabato di interventi) non sono degli ambulatori: il foglio della
    # direzione resta quello di prima della 1.12.3
    solo_sala = vista.get('solo_sala') or set()
    if solo_sala:
        vista = dict(vista, giorni=[g for g in vista['giorni'] if g not in solo_sala],
                     righe=[dict(r, celle=[c for c in r['celle'] if c['data'] not in solo_sala]) for r in vista['righe']])
    giorni, meta = vista['giorni'], vista['meta']
    colonne = 1 + len(giorni) * len(meta)
    _titolo(ws, 1, testo_excel(st.nome), colonne, 16)
    _titolo(ws, 2, TITOLO_MATRICE, colonne, 13)
    settimana = _settimana_testo(vista)
    periodo = ('Settimana tipo: i turni che si ripetono ogni settimana (quelli validi nella settimana %s), senza '
               'assenze e chiusure' % settimana if vista['tipo'] else 'Settimana %s' % settimana)
    ws.cell(3, 1, periodo).font = _carattere(italic=True)
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=colonne)
    ws.cell(4, 1, 'Destinatario: %s   ·   Compilato da: %s   ·   Data: %s' % (
        DESTINATARIO, COMPILATO_DA, adesso.strftime('%d/%m/%Y')))
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=colonne)
    r0 = 6
    _testa_settimana(ws, r0, vista, 'AMBULATORIO')
    verde, verde_chiaro, grigio = (PatternFill('solid', fgColor=x) for x in (VERDE_PIENO, VERDE_CHIARO, GRIGIO))
    riga = r0 + 2
    for r in vista['righe']:
        c = ws.cell(riga, 1, testo_excel(r['risorsa'].nome))
        c.font, c.border = _carattere(bold=True), BORDO
        c.alignment = Alignment(vertical='center', wrap_text=True)
        for k, cella in enumerate(r['celle']):
            c = ws.cell(riga, 2 + k)
            c.border = BORDO
            c.alignment = Alignment(vertical='top', wrap_text=True)
            if cella['chiuso']:
                c.value = testo_excel('CHIUSO: %s' % cella['chiuso'])
                c.fill = grigio
                c.font = _carattere(color='5B6B75', italic=True)
            elif cella['tutta_libera']:
                c.value = testo_excel('DISPONIBILE' + ''.join('\n(%s %s)' % (o.etichetta, motivo_assenza(motivo))
                                                              for o, motivo, _ in cella['assenti']))
                c.fill = verde
                c.font = _carattere(bold=True, color='1E6B2E')
            else:
                testi = ['%s %s' % (testo_excel(p['operatore'].etichetta), fascia(p['da'], p['a']).replace('–', '-'))
                         for p in cella['presenze']]
                testi += ['libero %s' % fascia(da, a).replace('–', '-') for da, a in cella['libere']]
                testi += ['(%s %s)' % (o.etichetta, motivo_assenza(motivo)) for o, motivo, _ in cella['assenti']]
                c.value = testo_excel('\n'.join(testi))
                if cella['libere']:
                    c.fill = verde_chiaro
        _altezza_riga(ws, riga, len(r['celle']))
        riga += 1
    if not vista['righe']:
        ws.cell(riga, 1, 'Nessuna stanza attiva in questa struttura.')
        riga += 1
    riga += 1
    ws.cell(riga, 1, 'In verde le fasce libere, disponibili per nuovi ambulatori (disponibilità integrative): '
                     '«DISPONIBILE» è una mezza giornata tutta libera, «libero» un\'ora o più rimasta libera in una mezza '
                     'giornata occupata.')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    ws.cell(riga, 1).alignment = Alignment(wrap_text=True)
    ws.row_dimensions[riga].height = 30
    riga += 1
    ws.cell(riga, 1, 'Calcolata dai turni, dalle assenze e dalle chiusure scritte nel Gestionale Agende il %s alle %s.'
            % (adesso.strftime('%d/%m/%Y'), adesso.strftime('%H:%M'))).font = _carattere(italic=True, color='5B6B75')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    riga += 2
    ws.cell(riga, 1, 'Il %s' % DESTINATARIO).font = _carattere(bold=True)
    ws.cell(riga, 1 + colonne // 2, 'La %s' % COMPILATO_DA).font = _carattere(bold=True)
    riga += 1
    ws.cell(riga, 1, '_' * 30)
    ws.cell(riga, 1 + colonne // 2, '_' * 30)
    ws.freeze_panes = ws.cell(r0 + 2, 2)
    _stampa(ws, '%d:%d' % (r0, r0 + 1), True, st, 'matrice ambulatori · ' + periodo.lower().split(':')[0])
    return ws


def frase_sala_mese(sala):
    """La riga sotto la programmazione: quanti interventi nel mese e quanti fuori dai turni dei chirurghi."""
    n, f = sala['interventi'], sala['fuori_turno']
    testo = 'Sala operatoria: %s nel mese' % ('nessun intervento' if not n else '%d intervent%s' % (n, 'o' if n == 1 else 'i'))
    if f:
        testo += ', di cui %d fuori dai turni dei chirurghi' % f
    return testo + '.'


def excel_programmazione(st, vista, adesso=None):
    """Il file della programmazione degli ambulatori: due fogli, la programmazione per specialita' e il calendario
    del mese, senza la sala operatoria (dalla 1.12.3 ha i suoi file, vedi esportazioni.py)."""
    wb = Workbook()
    fogli_programmazione(wb, st, vista, adesso)
    return wb


def fogli_programmazione(wb, st, vista, adesso=None, con_sala=False):
    """Due fogli: la programmazione per specialita' (il foglio che si
    compilava a mano, con le date calcolate) e il calendario del mese; con
    con_sala il calendario ha anche le righe della sala e la colonna degli
    interventi (l'esportazione di tutto insieme)."""
    adesso = adesso or datetime.now()
    primo = vista['primo']
    nome_mese = '%s %d' % (servizi.MESI[primo.month - 1], primo.year)
    ws = wb.active if wb.active is not None and wb.active.max_row == 1 and wb.active['A1'].value is None \
        and len(wb.worksheets) == 1 else wb.create_sheet()
    ws.title = 'Programmazione'
    intestazioni = ['Specialità', 'Medico', 'Giorno', 'Date di %s' % servizi.MESI[primo.month - 1], 'Orario',
                    'Stanza', 'Note']
    larghezze = [22, 26, 11, 24, 13, 18, 48]
    sala = vista.get('sala') or {'righe': [], 'interventi': 0, 'fuori_turno': 0}
    _titolo(ws, 1, '%s — %s' % (testo_excel(st.nome), TITOLO_PROGRAMMAZIONE), len(intestazioni), 15)
    ws.cell(2, 1, nome_mese.capitalize()).font = _carattere(size=12, bold=True)
    ws.cell(3, 1, 'Calcolata dai turni, dalle assenze e dalle chiusure scritte nel Gestionale Agende il %s alle %s: '
                  'le date sono quelle in cui il medico c\'è davvero.' % (adesso.strftime('%d/%m/%Y'),
                                                                        adesso.strftime('%H:%M'))
            ).font = _carattere(italic=True, color='5B6B75')
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(intestazioni))
    r0 = 5
    for c, (testo, l) in enumerate(zip(intestazioni, larghezze), start=1):
        _intestazione(ws.cell(r0, c), testo)
        ws.column_dimensions[get_column_letter(c)].width = l
    riga = r0 + 1
    for gruppo in vista['gruppi']:
        for n, r in enumerate(gruppo['righe']):
            valori = [testo_excel(gruppo['specialita']), testo_excel(r['operatore'].etichetta if r['operatore'] else '?'),
                      servizi.GIORNI[r['giorno']].capitalize() if r['giorno'] is not None else '—',
                      ', '.join(str(g.day) for g in r['date']) or '—',       # sempre testo, anche con una data sola (1.12.4)
                      fascia(r['ora_inizio'], r['ora_fine']).replace('–', '-') if r['ora_inizio'] else '—',
                      testo_excel(r['risorsa'].nome), testo_excel('; '.join(r['note']))]
            for c, v in enumerate(valori, start=1):
                cella = ws.cell(riga, c, v)
                cella.border = BORDO
                cella.alignment = Alignment(vertical='top', wrap_text=True)
                if n == 0:
                    cella.border = Border(left=_sottile, right=_sottile, top=_spesso, bottom=_sottile)
            ws.cell(riga, 1).font = _carattere(bold=True, color=BLU) if n == 0 else _carattere(color='5B6B75')
            if not r['date']:
                ws.cell(riga, 4).font = _carattere(color=ARANCIO)
            riga += 1
    if not vista['righe']:
        ws.cell(riga, 1, 'Nessun turno nelle stanze attive di questa struttura in %s.' % nome_mese)
        riga += 1
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    if vista['righe']:
        ws.auto_filter.ref = 'A%d:%s%d' % (r0, get_column_letter(len(intestazioni)), riga - 1)
    _stampa(ws, '%d:%d' % (r0, r0), True, st, 'programmazione ambulatori · ' + nome_mese)
    # il calendario: giorno per giorno
    wc = wb.create_sheet('Calendario')
    con_sala = bool(con_sala and (sala['righe'] or sala['interventi']))
    colonne_cal = ['Data', 'Giorno', 'Stanza', 'Medico', 'Orario'] + (['Interventi'] if con_sala else [])
    _titolo(wc, 1, 'Calendario di %s — %s' % (nome_mese, testo_excel(st.nome)), len(colonne_cal), 14)
    # quando e' stato calcolato, come negli altri fogli: un calendario stampato cambia con ogni assenza (1.12.4)
    wc.cell(2, 1, 'Calcolato dai turni, dalle assenze e dalle chiusure scritte nel Gestionale Agende il %s alle %s.'
            % (adesso.strftime('%d/%m/%Y'), adesso.strftime('%H:%M'))).font = _carattere(italic=True, color='5B6B75', size=9)
    for c, (testo, l) in enumerate(zip(colonne_cal, [12, 11, 18, 26, 13, 11]), start=1):
        _intestazione(wc.cell(3, c), testo)
        wc.column_dimensions[get_column_letter(c)].width = l
    riga = 4
    grigio = PatternFill('solid', fgColor=GRIGIO)
    for giorno in vista['calendario']:
        g, i = giorno['data'], giorno['info']
        in_sala = (giorno.get('sala') or []) if con_sala else []
        if g.weekday() not in st.giorni_aperti and not giorno['presenze'] and not in_sala:
            continue
        motivo = i['chiusura'] or (i['festivo'] if i['chiude_festivo'] else None)
        if not giorno['presenze']:
            # nessun medico negli ambulatori: la riga grigia resta anche se sotto c'e' la sala
            for c, v in enumerate([g, servizi.GIORNI[g.weekday()].capitalize(),
                                   testo_excel(motivo_chiusura(motivo)) if motivo else
                                   GIORNO_SOLO_SALA if g.weekday() not in st.giorni_aperti else 'nessun medico in turno', '', '']
                                  + ([None] if con_sala else []), start=1):
                cella = wc.cell(riga, c, v)
                cella.border, cella.fill = BORDO, grigio
            wc.cell(riga, 1).number_format = 'dd/mm/yyyy'
            riga += 1
        voci = [(t.risorsa, t.operatore, t, None) for t in giorno['presenze']] + \
            [(x['risorsa'], x['operatore'], x['turno'], x['interventi']) for x in in_sala]
        for n, (stanza, medico, t, n_int) in enumerate(voci, start=0 if giorno['presenze'] else 1):
            # la data e il giorno in ogni riga (in grigio dopo la prima del giorno): una pagina nuova, un filtro o un
            # ordinamento non lasciano righe senza data, come fino alla 1.12.3 (1.12.4)
            valori = [g, servizi.GIORNI[g.weekday()].capitalize(),
                      testo_excel(stanza.nome), testo_excel(medico.etichetta if medico else '?'),
                      fascia(t.ora_inizio, t.ora_fine).replace('–', '-') if t else 'fuori turno'] + \
                ([n_int] if con_sala else [])
            for c, v in enumerate(valori, start=1):
                cella = wc.cell(riga, c, v)
                cella.border = BORDO
                if n == 0:
                    cella.border = Border(left=_sottile, right=_sottile, top=_spesso, bottom=_sottile)
                elif c <= 2:
                    cella.font = _carattere(color='9AA5AD')
            wc.cell(riga, 1).number_format = 'dd/mm/yyyy'
            wc.cell(riga, 1).alignment = Alignment(horizontal='center')
            riga += 1
    wc.freeze_panes = 'A4'
    _stampa(wc, '3:3', False, st, 'calendario · ' + nome_mese)
    return wb


# ======================================================== la sala operatoria in Excel (1.12.3)
TITOLO_SALA = 'SALA OPERATORIA · CHIRURGHI E INTERVENTI'
LEGENDA_SALA = ('Per ogni sala, mattina e pomeriggio: i chirurghi in turno, chi opera senza un turno e quanti '
                'interventi (prenotati, confermati o arrivati; i disdetti e i non presentati no). «sala libera»: nessun '
                'turno e nessun intervento. La sala si programma dalla pagina Sala.')


def _cella_sala_excel(c, cella, grigio, per_riga=99):
    c.border = BORDO
    c.alignment = Alignment(vertical='top', wrap_text=True)
    # in una colonna stretta «Valente Paolo 08:00-14:00» andava a capo dopo «08:00-»: l'orario va sotto il nome
    # intero (1.12.4). Il testo resta quello della pagina (testo_cella_sala), cambia solo dove va a capo
    righe = [re.sub(r' (\d\d:\d\d-\d\d:\d\d)$', r'\n\1', r) if len(r) > per_riga else r
             for r in testo_cella_sala(cella).split('\n')]
    c.value = testo_excel('\n'.join(righe))
    if cella['chiuso']:
        c.fill = grigio
        c.font = _carattere(color='5B6B75', italic=True)
    elif cella['tutta_libera']:
        c.font = _carattere(color='5B6B75', italic=True)
    elif cella['senza_turno']:
        c.font = _carattere(color=ARANCIO)


def foglio_sala_settimana(ws, st, vista, adesso=None):
    """La sala operatoria della settimana, in un foglio suo: una riga per sala, una colonna per ogni mattina e
    pomeriggio, come la matrice degli ambulatori."""
    adesso = adesso or datetime.now()
    ws.title = 'Sala operatoria'
    giorni, meta = vista['giorni'], vista['meta']
    colonne = 1 + len(giorni) * len(meta)
    _titolo(ws, 1, testo_excel(st.nome), colonne, 16)
    _titolo(ws, 2, TITOLO_SALA, colonne, 13)
    settimana = _settimana_testo(vista)
    periodo = ('Settimana tipo: i turni che si ripetono ogni settimana (quelli validi nella settimana %s)' % settimana
               if vista['tipo'] else 'Settimana %s' % settimana)
    ws.cell(3, 1, periodo).font = _carattere(italic=True)
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=colonne)
    r0 = 5
    _testa_settimana(ws, r0, vista, 'SALA')
    grigio = PatternFill('solid', fgColor=GRIGIO)
    riga = r0 + 2
    for r in vista['sale']:
        c = ws.cell(riga, 1, testo_excel(r['risorsa'].nome))
        c.font, c.border = _carattere(bold=True), BORDO
        c.alignment = Alignment(vertical='center', wrap_text=True)
        for k, cella in enumerate(r['celle']):
            _cella_sala_excel(ws.cell(riga, 2 + k), cella, grigio, per_riga=22)
        _altezza_riga(ws, riga, len(r['celle']))
        riga += 1
    if not vista['sale']:
        ws.cell(riga, 1, 'Nessuna sala operatoria attiva in questa struttura.')
        riga += 1
    riga += 1
    ws.cell(riga, 1, LEGENDA_SALA if not vista['tipo'] else
            'I turni dei chirurghi che si ripetono ogni settimana; gli interventi sono nella settimana vera.')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    ws.cell(riga, 1).alignment = Alignment(wrap_text=True)
    ws.row_dimensions[riga].height = 30
    riga += 1
    ws.cell(riga, 1, 'Calcolata dai turni e dagli interventi scritti nel Gestionale Agende il %s alle %s.'
            % (adesso.strftime('%d/%m/%Y'), adesso.strftime('%H:%M'))).font = _carattere(italic=True, color='5B6B75')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    ws.freeze_panes = ws.cell(r0 + 2, 2)
    _stampa(ws, '%d:%d' % (r0, r0 + 1), True, st, 'sala operatoria · ' + periodo.lower().split(':')[0])
    return ws


def sala_del_mese(ses, st, primo, ultimo):
    """La sala operatoria giorno per giorno: i giorni del mese che le matrici delle settimane mostrano (di
    apertura, o con turni o interventi), con le celle di ogni sala. Le celle sono quelle della matrice, cosi'
    la settimana e il mese non possono dire cose diverse."""
    giorni = []
    lunedi = calendario.lunedi_di(primo)
    while lunedi <= ultimo:
        v = matrice(ses, lunedi, st)
        for g in v['giorni']:
            if primo <= g <= ultimo:
                giorni.append({'data': g, 'info': v['info'][g],
                               'celle': {r['risorsa'].id: [c for c in r['celle'] if c['data'] == g] for r in v['sale']}})
        lunedi += timedelta(days=7)
    return {'giorni': giorni, 'sale': sale_della(st), 'meta': mezze_giornate(st), 'primo': primo, 'ultimo': ultimo}


def foglio_sala_mese(ws, st, mese, adesso=None):
    """La sala operatoria del mese, giorno per giorno: una riga per giorno, per ogni sala la mattina e il
    pomeriggio (chi opera e quanti interventi)."""
    adesso = adesso or datetime.now()
    ws.title = 'Sala operatoria'
    sale, meta, primo = mese['sale'], mese['meta'], mese['primo']
    nome_mese = '%s %d' % (servizi.MESI[primo.month - 1], primo.year)
    colonne = 1 + max(1, len(sale)) * len(meta)
    _titolo(ws, 1, testo_excel(st.nome), colonne, 16)
    _titolo(ws, 2, TITOLO_SALA, colonne, 13)
    ws.cell(3, 1, nome_mese.capitalize()).font = _carattere(size=12, bold=True)
    r0 = 5
    _intestazione(ws.cell(r0, 1), 'GIORNO')
    ws.merge_cells(start_row=r0, start_column=1, end_row=r0 + 1, end_column=1)
    ws.column_dimensions['A'].width = 18
    for k, sala in enumerate(sale):
        c1 = 2 + k * len(meta)
        _intestazione(ws.cell(r0, c1), testo_excel(sala.nome))
        if len(meta) > 1:
            ws.merge_cells(start_row=r0, start_column=c1, end_row=r0, end_column=c1 + len(meta) - 1)
        for j, m in enumerate(meta):
            _intestazione(ws.cell(r0 + 1, c1 + j), fascia(m['da'], m['a']).replace('–', '-'))
            ws.column_dimensions[get_column_letter(c1 + j)].width = 24
    grigio = PatternFill('solid', fgColor=GRIGIO)
    riga = r0 + 2
    for giorno in (mese['giorni'] if sale else []):
        g, i = giorno['data'], giorno['info']
        testo = '%s %d/%d' % (servizi.GIORNI[g.weekday()].capitalize(), g.day, g.month)
        if i['chiusura'] or i['festivo']:
            testo += '\n%s' % testo_excel(i['chiusura'] or i['festivo'])
        c = ws.cell(riga, 1, testo)
        c.font, c.border = _carattere(bold=True), BORDO
        c.alignment = Alignment(vertical='top', wrap_text=True)
        for k, sala in enumerate(sale):
            for j, cella in enumerate(giorno['celle'].get(sala.id, [])):
                _cella_sala_excel(ws.cell(riga, 2 + k * len(meta) + j), cella, grigio, per_riga=28)
        righe_testo = 2 if '\n' in testo else 1
        for k in range(len(sale) * len(meta)):
            v = ws.cell(riga, 2 + k).value or ''
            righe_testo = max(righe_testo, sum(max(1, -(-len(pezzo) // 28)) for pezzo in str(v).split('\n')))
        # alta quanto il testo: con almeno 30 punti un mese andava su due pagine, la seconda quasi vuota (1.12.4)
        ws.row_dimensions[riga].height = 15 * righe_testo + 3
        riga += 1
    if not sale:
        ws.cell(riga, 1, 'Nessuna sala operatoria attiva in questa struttura.')
        riga += 1
    riga += 1
    ws.cell(riga, 1, LEGENDA_SALA)
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    ws.cell(riga, 1).alignment = Alignment(wrap_text=True)
    ws.row_dimensions[riga].height = 30
    riga += 1
    ws.cell(riga, 1, 'Calcolata dai turni e dagli interventi scritti nel Gestionale Agende il %s alle %s.'
            % (adesso.strftime('%d/%m/%Y'), adesso.strftime('%H:%M'))).font = _carattere(italic=True, color='5B6B75')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    ws.freeze_panes = ws.cell(r0 + 2, 2)
    _stampa(ws, '%d:%d' % (r0, r0 + 1), len(sale) * len(meta) > 4, st, 'sala operatoria · ' + nome_mese)
    una_pagina_se_manca_poco(ws, riga, not (len(sale) * len(meta) > 4))
    return ws


def foglio_turni_sala(ws, st, vista, adesso=None):
    """I turni dei chirurghi in sala nel mese, come la programmazione degli ambulatori: le date in cui operano
    davvero, gli interventi di ogni turno, una riga per chi ha operato fuori dai suoi turni e la frase in fondo."""
    adesso = adesso or datetime.now()
    ws.title = 'Turni di sala'
    primo = vista['primo']
    nome_mese = '%s %d' % (servizi.MESI[primo.month - 1], primo.year)
    sala = vista['sala']
    intestazioni = ['Sala', 'Chirurgo', 'Giorno', 'Date di %s' % servizi.MESI[primo.month - 1], 'Orario', 'Note']
    larghezze = [20, 26, 11, 24, 13, 44]
    _titolo(ws, 1, '%s — SALA OPERATORIA: I TURNI DEI CHIRURGHI' % testo_excel(st.nome), len(intestazioni), 15)
    ws.cell(2, 1, nome_mese.capitalize()).font = _carattere(size=12, bold=True)
    ws.cell(3, 1, 'Calcolata dai turni, dalle assenze, dalle chiusure e dagli interventi scritti nel Gestionale Agende '
                  'il %s alle %s.' % (adesso.strftime('%d/%m/%Y'), adesso.strftime('%H:%M'))).font = _carattere(italic=True, color='5B6B75')
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(intestazioni))
    r0 = 5
    for c, (testo, l) in enumerate(zip(intestazioni, larghezze), start=1):
        _intestazione(ws.cell(r0, c), testo)
        ws.column_dimensions[get_column_letter(c)].width = l
    riga = r0 + 1
    prima_sala = None
    for r in sala['righe']:
        valori = [testo_excel(r['risorsa'].nome), testo_excel(r['operatore'].etichetta if r['operatore'] else '?'),
                  servizi.GIORNI[r['giorno']].capitalize() if r['giorno'] is not None else '—',
                  ', '.join(str(g.day) for g in r['date']) or '—',       # sempre testo, anche con una data sola (1.12.4)
                  fascia(r['ora_inizio'], r['ora_fine']).replace('–', '-') if r['ora_inizio'] else '—',
                  testo_excel('; '.join(r['note']))]
        nuova = r['risorsa'].id != prima_sala
        prima_sala = r['risorsa'].id
        for c, v in enumerate(valori, start=1):
            cella = ws.cell(riga, c, v)
            cella.border = Border(left=_sottile, right=_sottile, top=_spesso, bottom=_sottile) if nuova else BORDO
            cella.alignment = Alignment(vertical='top', wrap_text=True)
        ws.cell(riga, 1).font = _carattere(bold=True, color=BLU) if nuova else _carattere(color='5B6B75')
        if r.get('senza_turno'):
            ws.cell(riga, 6).font = _carattere(color=ARANCIO)
        elif not r['date']:
            ws.cell(riga, 4).font = _carattere(color=ARANCIO)
        riga += 1
    if not sala['righe']:
        ws.cell(riga, 1, 'Nessun turno e nessun intervento in sala operatoria in %s.' % nome_mese)
        riga += 1
    ultima = riga - 1
    riga += 1
    ws.cell(riga, 1, testo_excel(frase_sala_mese(sala))).font = _carattere(italic=True, color='5B6B75')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=len(intestazioni))
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    if sala['righe']:
        ws.auto_filter.ref = 'A%d:%s%d' % (r0, get_column_letter(len(intestazioni)), ultima)
    _stampa(ws, '%d:%d' % (r0, r0), True, st, 'turni di sala · ' + nome_mese)
    return ws


def interventi_periodo(ses, st, dal, al):
    """Tutti gli interventi nelle sale operatorie della struttura (anche in quelle spente dopo), in ogni stato,
    dal giorno 'dal' al giorno 'al' compresi, in ordine di ora."""
    ids = [r.id for r in st.risorse if r.tipo == TIPO_SALA]
    if not ids:
        return []
    return ses.scalars(select(Appuntamento).where(
        Appuntamento.risorsa_id.in_(ids), Appuntamento.inizio >= datetime.combine(dal, time(0)),
        Appuntamento.inizio < datetime.combine(al + timedelta(days=1), time(0)))
        .order_by(Appuntamento.inizio, Appuntamento.risorsa_id)).all()


def attivita_per_medico(ses, st, dal, al):
    """Per ogni medico, giorno per giorno, quanti appuntamenti attivi ha negli ambulatori e quanti interventi attivi in
    sala operatoria (prenotati, confermati o arrivati; i disdetti e i non presentati no), separati (1.12.5, richiesta di
    Giovanni: «si distinguano gli interventi e gli ambulatori per medico, cosi' si capisce quanti ne fa quella
    giornata»). Contano tutte le stanze della struttura, anche quelle spente, come gli elenchi. Solo numeri: niente dati
    dei pazienti. 'amb' e 'sala' sono {id del medico o None: {giorno: [appuntamenti]}}."""
    risorse = {r.id: r for r in ses.scalars(select(Risorsa).where(Risorsa.struttura_id == st.id))}
    apps = ses.scalars(select(Appuntamento).where(
        Appuntamento.risorsa_id.in_(list(risorse)), Appuntamento.stato.in_(STATI_ATTIVI),
        Appuntamento.inizio >= datetime.combine(dal, time(0)),
        Appuntamento.inizio < datetime.combine(al + timedelta(days=1), time(0)))
        .order_by(Appuntamento.inizio)).all() if risorse else []
    amb, sala, medici = {}, {}, {}
    for a in apps:
        dove = sala if risorse[a.risorsa_id].tipo == TIPO_SALA else amb
        dove.setdefault(a.operatore_id, {}).setdefault(a.inizio.date(), []).append(a)
        if a.operatore is not None:
            medici[a.operatore_id] = a.operatore
    return {'dal': dal, 'al': al, 'amb': amb, 'sala': sala, 'medici': medici}


PAROLE_PER_MEDICO = {'amb': ('AMBULATORI · appuntamenti', 'appuntament', 'Stanze',
                             'Nessun appuntamento negli ambulatori in questo periodo.'),
                     'sala': ('SALA OPERATORIA · interventi', 'intervent', 'Sale',
                              'Nessun intervento in sala operatoria in questo periodo.')}


def foglio_per_medico(ws, st, dati, parti, periodo, adesso=None):
    """Il foglio «Per medico» delle esportazioni: una tabella per gli ambulatori e una per la sala operatoria (in
    «tutto insieme» tutte e due, una sotto l'altra), una riga per medico e una colonna per giorno, con il totale. Nel
    giorno, invece delle colonne dei giorni, le stanze (o le sale) e l'orario dal primo all'ultimo."""
    adesso = adesso or datetime.now()
    ws.title = 'Per medico'
    giorni = [dati['dal'] + timedelta(days=k) for k in range((dati['al'] - dati['dal']).days + 1)]
    un_giorno = len(giorni) == 1
    usati = set()
    for parte in parti:
        for per_giorno in dati[parte].values():
            usati |= set(per_giorno)
    # i giorni di apertura e quelli in cui c'e' stato qualcosa (anche una domenica di sola sala)
    giorni = [g for g in giorni if un_giorno or g.weekday() in st.giorni_aperti or g in usati]
    colonne = 1 + (3 if un_giorno else len(giorni) + 1)
    cosa = ' e '.join({'amb': 'quanti appuntamenti negli ambulatori', 'sala': 'quanti interventi in sala operatoria'}[x]
                      for x in parti)
    riga = apri_foglio_excel(ws, 'Per medico · %s' % periodo,
                             cosa[0].upper() + cosa[1:] + ' ha ogni medico'
                             + ('' if un_giorno else ', giorno per giorno')
                             + ' (prenotati, confermati o arrivati; i disdetti e i non presentati no)', st, adesso,
                             colonne=colonne)
    for parte in parti:
        testa, parola, dove_nome, vuoto = PAROLE_PER_MEDICO[parte]
        c = ws.cell(riga, 1, testa)
        c.font = _carattere(bold=True, color=BLU)
        riga += 1
        voci = dati[parte]
        ordine = sorted((k for k in voci if k is not None), key=lambda k: dati['medici'][k].etichetta.lower())
        ordine += [None] if None in voci else []
        if not ordine:
            ws.cell(riga, 1, vuoto).font = _carattere(italic=True, color='5B6B75')
            riga += 2
            continue
        def nome(k):
            return dati['medici'][k].etichetta if k is not None else 'senza medico'
        if un_giorno:
            g = giorni[0]
            intestazioni = ['Medico', parola.capitalize() + 'i', dove_nome, 'Orario']
            righe = []
            for k in ordine:
                lista = voci[k].get(g, [])
                righe.append([nome(k), len(lista), ', '.join(sorted({a.risorsa.nome for a in lista if a.risorsa})),
                              '%s-%s' % (min(a.inizio for a in lista).strftime('%H:%M'),
                                         max(a.fine for a in lista).strftime('%H:%M')) if lista else ''])
            larghezze = [26, 15, 30, 13]
            totali = {1: 'Totale', 2: 'somma'}
        else:
            intestazioni = ['Medico'] + ['%s\n%d/%d' % (servizi.GIORNI[g.weekday()][:3].capitalize(), g.day, g.month)
                                         for g in giorni] + ['Totale']
            righe = []
            for k in ordine:
                n = [len(voci[k].get(g, [])) for g in giorni]
                righe.append([nome(k)] + [x or None for x in n] + [sum(n)])
            larghezze = [26] + [7] * len(giorni) + [9]
            totali = {1: 'Totale'}
            totali.update({c_: 'somma' for c_ in range(2, len(intestazioni) + 1)})
        riga = tabella_excel(ws, riga, intestazioni, larghezze, righe, totali=totali, filtro=False, blocca=False)
        if not un_giorno:
            for c_ in range(2, len(intestazioni)):      # nei totali dei giorni lo zero resta vuoto, come nelle righe
                if ws.cell(riga - 2, c_).value == 0:
                    ws.cell(riga - 2, c_).value = None
    ws.cell(riga, 1, 'Un intervento conta per il chirurgo scritto nell\'intervento, un appuntamento per il medico '
                     'dell\'appuntamento. Il dettaglio è negli altri fogli del file.').font = \
        _carattere(italic=True, color='5B6B75', size=9)
    imposta_stampa_excel(ws, not un_giorno and len(giorni) > 7, None, None, st, 'per medico · ' + periodo)
    una_pagina_se_manca_poco(ws, riga, not (not un_giorno and len(giorni) > 7))
    return ws


def foglio_interventi(ws, st, lista, periodo):
    """L'elenco degli interventi del periodo: data, ora, sala, chirurgo, prestazione e stato. Senza i dati dei
    pazienti (per quelli c'e' la lista operatoria del giorno); i disdetti barrati, i non presentati in grigio, i
    totali contano solo gli attivi."""
    ws.title = 'Interventi'
    intestazioni = ['DATA', 'ORA', 'FINE', 'SALA', 'CHIRURGO', 'PRESTAZIONE', 'STATO']
    larghezze = [12, 8, 8, 18, 24, 30, 15]
    attivi = [x for x in lista if x.stato in STATI_ATTIVI]
    disdetti = sum(1 for x in lista if x.stato == 'DISDETTO')
    non_pres = sum(1 for x in lista if x.stato == 'NON_PRESENTATO')
    sotto = '%d intervent%s attiv%s' % (len(attivi), 'o' if len(attivi) == 1 else 'i', 'o' if len(attivi) == 1 else 'i')
    altri = [x for x in ('%d disdett%s' % (disdetti, 'o' if disdetti == 1 else 'i') if disdetti else '',
                         '%d non presentat%s' % (non_pres, 'o' if non_pres == 1 else 'i') if non_pres else '') if x]
    if altri:
        sotto += ' (più %s)' % ' e '.join(altri)
    riga = apri_foglio_excel(ws, 'Interventi in sala operatoria · %s' % periodo, sotto, st, colonne=len(intestazioni))
    righe = [[x.inizio.date(), x.inizio.time(), x.fine.time(), x.risorsa.nome if x.risorsa else '',
              x.operatore.etichetta if x.operatore else '', x.prestazione.nome if x.prestazione else '',
              x.etichetta_stato] for x in lista]
    barrato = Font(name='Calibri', size=10, italic=True, color='5B6B75', strike=True)
    grigio_f = Font(name='Calibri', size=10, italic=True, color='5B6B75')
    stati = {servizi.ETICHETTA_STATO.get('DISDETTO', 'Disdetto'): barrato,
             servizi.ETICHETTA_STATO.get('NON_PRESENTATO', 'Non presentato'): grigio_f}
    tabella_excel(ws, riga, intestazioni, larghezze, righe,
                  formati={1: 'dd/mm/yyyy', 2: FORMATO_ORA, 3: FORMATO_ORA},
                  totali={1: 'Totale (solo attivi): %d intervent%s' % (len(attivi), 'o' if len(attivi) == 1 else 'i')} if lista else None,
                  a_capo=(6,), stile_riga=lambda v: {'font': stati[v[6]]} if v[6] in stati else None)
    if not lista:
        ws.cell(riga + 1, 1, 'Nessun intervento in questo periodo.')
    imposta_stampa_excel(ws, True, '%d:%d' % (riga, riga), None, st, 'interventi · ' + periodo)
    return ws


# =============================================================== pagine
def _settimana_di(iso):
    g = data_da(iso)
    return calendario.lunedi_di(g), g


def _titolo_settimana(lunedi):
    domenica = lunedi + timedelta(days=6)
    return 'Settimana %s %s %s %s %d' % (servizi.dal_giorno(lunedi.day), servizi.MESI[lunedi.month - 1],
                                        servizi.al_giorno(domenica.day), servizi.MESI[domenica.month - 1], domenica.year)


@bp.route('/')
def inizio():
    sid = intero(request.args.get('struttura'))
    return redirect(url_for('ambulatori.settimana', iso=date.today().isoformat(), struttura=sid or None))


@bp.route('/settimana/<iso>')
def settimana(iso):
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    lunedi, g = _settimana_di(iso)
    vista = matrice(s, lunedi, st)
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    return render_template('ambulatori_settimana.html', vista=vista, st=st, sid=st.id, strutture=strutture,
                           medici=medici, lunedi=lunedi, oggi=date.today(), titolo=_titolo_settimana(lunedi),
                           prima=(lunedi - timedelta(days=7)).isoformat(), dopo=(lunedi + timedelta(days=7)).isoformat(),
                           giorni_nomi=servizi.GIORNI, fascia=fascia, sezione='ambulatori', data_menu=g.isoformat(),
                           aaaamm=lunedi.strftime('%Y-%m'), motivo_assenza=motivo_assenza, motivo_chiusura=motivo_chiusura)


@bp.route('/settimana/<iso>.xlsx')
def settimana_excel(iso):
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    lunedi, _ = _settimana_di(iso)
    tipo = request.args.get('tipo') == '1'
    vista = matrice(s, lunedi, st, tipo=tipo)
    nome = 'matrice-ambulatori-%s%s.xlsx' % (lunedi.isoformat(), '-settimana-tipo' if tipo else '')
    return scarica_excel(excel_matrice(st, vista), nome)


@bp.route('/mese/<aaaamm>')
def mese(aaaamm):
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    primo, ultimo = mese_da(aaaamm)
    vista = programmazione(s, primo.year, primo.month, st)
    prima = (primo - timedelta(days=1)).replace(day=1)
    dopo = ultimo + timedelta(days=1)
    return render_template('ambulatori_mese.html', vista=vista, st=st, sid=st.id, strutture=strutture, primo=primo,
                           titolo='Programmazione ambulatori · %s %d' % (servizi.MESI[primo.month - 1], primo.year),
                           mese_nome=servizi.MESI[primo.month - 1],
                           prima=prima.strftime('%Y-%m'), dopo=dopo.strftime('%Y-%m'), aaaamm=primo.strftime('%Y-%m'),
                           oggi=date.today(), giorni_nomi=servizi.GIORNI, fascia=fascia, sezione='programmazione',
                           data_menu=max(primo, min(date.today(), ultimo)).isoformat(), motivo_chiusura=motivo_chiusura,
                           frase_sala=frase_sala_mese(vista['sala']))


@bp.route('/mese/<aaaamm>.xlsx')
def mese_excel(aaaamm):
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    primo, _ = mese_da(aaaamm)
    vista = programmazione(s, primo.year, primo.month, st)
    return scarica_excel(excel_programmazione(st, vista), 'programmazione-ambulatori-%s.xlsx' % primo.strftime('%Y-%m'))


# ======================================================== pianificazione
def _torna(st, g):
    return destinazione_sicura(request.form.get('torna'),
                               url_for('ambulatori.settimana', iso=g.isoformat(), struttura=st.id))


@bp.route('/metti', methods=['POST'])
def metti():
    """Dal «+» di una cella: un turno nuovo per quella stanza, quel giorno
    della settimana e quelle ore, ogni settimana da quel giorno in poi
    oppure quel giorno solo. Le stesse regole della scheda del turno."""
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    m = Modulo(request.form)
    g = m.data('data', 'Giorno')
    if g is None:
        flash('Giorno non valido.', 'errore')
        return redirect(url_for('ambulatori.settimana', iso=date.today().isoformat(), struttura=st.id))
    stanza = s.get(Risorsa, intero(request.form.get('risorsa')))
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)).all()
    oid = m.scelta('operatore', 'Medico', [str(x.id) for x in medici])
    inizio, fine = m.ora('ora_inizio', 'Dalle'), m.ora('ora_fine', 'Alle')
    ripetizione = m.scelta('ripetizione', 'Ripetizione', ['settimanale', 'giorno'])
    if stanza is None or not stanza.attiva or stanza.struttura_id != st.id:
        m.errori.append('Stanza non valida.')
    if inizio and fine and fine <= inizio:
        m.errori.append('L\'ora di fine deve venire dopo quella di inizio.')
    if not m.errori:
        singolo = ripetizione == 'giorno'
        da, a = g, (g if singolo else None)
        with _lucchetto:
            occupata = stanza_gia_assegnata(s, stanza.id, g.weekday(), inizio, fine, da, a, int(oid))
            if occupata:
                m.errori.append(occupata)
            else:
                t = Turno(operatore_id=int(oid), risorsa_id=stanza.id, giorno_settimana=g.weekday(),
                          ora_inizio=inizio, ora_fine=fine, valido_da=da, valido_a=a)
                s.add(t)
                s.flush()
                medico = next(x for x in medici if x.id == int(oid))
                quando = ('il %s' % g.strftime('%d/%m/%Y')) if singolo else ('ogni %s dal %s' % (
                    servizi.GIORNI[g.weekday()], g.strftime('%d/%m/%Y')))
                messaggio = 'Turno salvato: %s in %s %s dalle %s alle %s.' % (
                    medico.etichetta, stanza.nome, quando, inizio.strftime('%H:%M'), fine.strftime('%H:%M'))
                servizi.registra(s, 'Turno', t.id, 'SALVATO', messaggio)
                s.commit()
                flash(messaggio, 'ok')
    if m.errori:
        flash(' '.join(m.errori), 'errore')
    return redirect(_torna(st, g))


@bp.route('/togli', methods=['POST'])
def togli():
    """Dalla «x» di un nome nella matrice: il turno non vale piu' da quella
    settimana in poi. Un turno di un giorno, o uno che comincia in quella
    settimana o dopo, si elimina; uno che veniva da prima si chiude la
    domenica precedente (le settimane gia' fatte restano com'erano, anche
    nelle statistiche)."""
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = Modulo(request.form).data('data', 'Giorno')
    if g is None:
        flash('Giorno non valido: il turno non è stato toccato.', 'errore')
        return redirect(url_for('ambulatori.settimana', iso=date.today().isoformat(), struttura=st.id))
    lunedi = calendario.lunedi_di(g)
    t = s.get(Turno, intero(request.form.get('turno')))
    if t is None or t.risorsa.struttura_id != st.id:
        flash('Turno non trovato: forse è già stato tolto.', 'errore')
        return redirect(_torna(st, g))
    if t.valido_a is not None and t.valido_a < lunedi:
        flash('Quel turno era già finito il %s: non c\'è niente da togliere.' % t.valido_a.strftime('%d/%m/%Y'), 'avviso')
        return redirect(_torna(st, g))
    with _lucchetto:
        chi = '%s, %s dalle %s alle %s' % (t.operatore.etichetta, servizi.GIORNI[t.giorno_settimana],
                                           t.ora_inizio.strftime('%H:%M'), t.ora_fine.strftime('%H:%M'))
        if servizi.e_di_un_giorno(t) or t.valido_da >= lunedi:
            servizi.registra(s, 'Turno', t.id, 'ELIMINATO', 'Turno di %s' % chi)
            s.delete(t)
            messaggio = 'Turno tolto: %s.' % chi
        else:
            t.valido_a = lunedi - timedelta(days=1)
            messaggio = 'Turno di %s chiuso: vale fino al %s, le settimane prima restano com\'erano.' % (
                chi, t.valido_a.strftime('%d/%m/%Y'))
            servizi.registra(s, 'Turno', t.id, 'SALVATO', messaggio)
        s.commit()
    flash(messaggio, 'ok')
    return redirect(_torna(st, g))


# ================================================== riepilogo del periodo (1.12.2)
# Il riepilogo «non live»: com'e' andato un giorno, una settimana o un mese, per stanza, per medico e
# giorno per giorno. Ore di turno (i turni effettivi di ogni stanza, uniti), ore occupate (gli
# appuntamenti che tengono il posto, dentro i turni), visite fatte, non presentati, disdetti, ancora da
# segnare e da fare, mezze giornate senza nessun medico. Tutto calcolato, niente ricopiato; nel JSON e
# nell'Excel solo conteggi, ore, stanze e medici, mai un paziente.
MASSIMO_GIORNI_RIEPILOGO = 93
STATI_OCCUPANO = ('PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'NON_PRESENTATO')   # un disdetto libera il posto
GRUPPI_PERIODO = (('fatti', 'fatti'), ('non_presentati', 'non presentati'), ('disdetti', 'disdetti'),
                  ('da_segnare', 'da segnare'), ('da_fare', 'da fare'))
SINGOLARI_PERIODO = {'fatti': 'fatto', 'non_presentati': 'non presentato', 'disdetti': 'disdetto',
                     'da_segnare': 'da segnare', 'da_fare': 'da fare'}
PERIODI = (('oggi', 'Oggi'), ('ieri', 'Ieri'), ('settimana', 'Questa settimana'),
           ('settimana-scorsa', 'Settimana scorsa'), ('mese', 'Questo mese'), ('mese-scorso', 'Mese scorso'))


def periodo_da(nome, oggi):
    """(primo, ultimo giorno) di un periodo con nome, oppure None."""
    lunedi = calendario.lunedi_di(oggi)
    primo_mese = oggi.replace(day=1)
    fine_mese = (primo_mese + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return {
        'oggi': (oggi, oggi), 'ieri': (oggi - timedelta(days=1), oggi - timedelta(days=1)),
        'settimana': (lunedi, lunedi + timedelta(days=6)),
        'settimana-scorsa': (lunedi - timedelta(days=7), lunedi - timedelta(days=1)),
        'mese': (primo_mese, fine_mese),
        'mese-scorso': ((primo_mese - timedelta(days=1)).replace(day=1), primo_mese - timedelta(days=1)),
    }.get(nome)


def unisci_intervalli(intervalli):
    """[(da, a)] in minuti, uniti dove si toccano o si sovrappongono."""
    uniti = []
    for da, a in sorted(x for x in intervalli if x[1] > x[0]):
        if uniti and da <= uniti[-1][1]:
            uniti[-1][1] = max(uniti[-1][1], a)
        else:
            uniti.append([da, a])
    return [tuple(x) for x in uniti]


def durata_intervalli(intervalli):
    return sum(a - da for da, a in intervalli)


def sovrapposizione(primi, secondi):
    """I minuti in comune fra due elenchi di intervalli gia' uniti."""
    totale, i, j = 0, 0, 0
    while i < len(primi) and j < len(secondi):
        da, a = max(primi[i][0], secondi[j][0]), min(primi[i][1], secondi[j][1])
        totale += max(0, a - da)
        if primi[i][1] < secondi[j][1]:
            i += 1
        else:
            j += 1
    return totale


def gruppo_periodo(a, adesso):
    """Il gruppo di un appuntamento nel riepilogo del periodo: i cinque gruppi sommano al totale."""
    if a.stato == 'ARRIVATO':
        return 'fatti'
    if a.stato == 'NON_PRESENTATO':
        return 'non_presentati'
    if a.stato == 'DISDETTO':
        return 'disdetti'
    return 'da_segnare' if a.fine <= adesso else 'da_fare'


def testo_ore(minuti):
    """450 -> '7 h 30', 420 -> '7 h', 0 -> '0 h'."""
    h, m = divmod(int(round(minuti or 0)), 60)
    return '%d h %02d' % (h, m) if m else '%d h' % h


def ore_in_parole(minuti):
    """450 -> '7 ore e 30 minuti', 60 -> '1 ora', 0 -> '0 ore'."""
    h, m = divmod(int(round(minuti or 0)), 60)
    minuti_ = '%d minut%s' % (m, 'o' if m == 1 else 'i')
    if not h and m:
        return minuti_
    ore = '%d or%s' % (h, 'a' if h == 1 else 'e')
    return ore + (' e %s' % minuti_ if m else '')


def titolo_periodo(da, a):
    """'martedì 3 novembre 2026', 'dal 2 all'8 novembre 2026', 'dal 26 ottobre al 1° novembre 2026'."""
    if da == a:
        return servizi.etichetta_giorno(da)
    mese_a = '%s %d' % (servizi.MESI[a.month - 1], a.year)
    if (da.year, da.month) == (a.year, a.month):
        return '%s %s %s' % (_dal(da.day), _al(a.day), mese_a)
    inizio = '%s %s' % (_dal(da.day), servizi.MESI[da.month - 1]) + ('' if da.year == a.year else ' %d' % da.year)
    return '%s %s %s' % (inizio, _al(a.day), mese_a)


def il_percento(valore):
    """'il 54%', ma 'l'11,6%', 'l'8%', 'l'80%' (davanti a una vocale l'articolo si apostrofa)."""
    valore = round(valore, 1)                   # l'articolo segue il numero scritto: 0,96 -> «l'1%»
    intero_ = int(valore)
    testo = ('%g' % valore).replace('.', ',')
    if intero_ == 0:
        return 'lo %s%%' % testo
    return ("l'%s%%" if str(intero_).startswith('8') or intero_ in (1, 11) else 'il %s%%') % testo


def _percento(parte, tutto):
    return round(100.0 * parte / tutto, 1) if tutto else None


# le parole del riepilogo del periodo: degli ambulatori o della sala operatoria (1.12.6, richiesta di Giovanni:
# «implementare nella scheda riepilogo anche quello mensile/settimanale/giornaliero di ambulatori e sale operatorie»)
PARTI_RIEPILOGO = (('ambulatori', 'Ambulatori'), ('sala', 'Sala operatoria'))
PAROLE_RIEPILOGO = {
    'ambulatori': dict(app='appuntament', stanza='stanza', stanze='stanze', Stanza='Stanza', Stanze='Stanze',
                       la_stanza='la stanza', nelle='nelle stanze', medico='medico', medici='medici', Medico='Medico',
                       Medici='Medici', senza='senza nessun medico', Senza='Senza medico',
                       occupate='Le stanze sono state occupate', fatti='Fatti', titolo='Riepilogo di agende e ambulatori',
                       file='riepilogo-ambulatori', di_turno='di turno nelle stanze'),
    'sala': dict(app='intervent', stanza='sala', stanze='sale', Stanza='Sala', Stanze='Sale', la_stanza='la sala',
                 nelle='nelle sale', medico='chirurgo', medici='chirurghi', Medico='Chirurgo', Medici='Chirurghi',
                 senza='con la sala libera', Senza='Sala libera', occupate='Le sale sono state occupate',
                 fatti='Arrivati', titolo='Riepilogo della sala operatoria', file='riepilogo-sala-operatoria',
                 di_turno='di turno in sala'),
}


def parte_riepilogo(valore):
    return valore if valore in PAROLE_RIEPILOGO else 'ambulatori'


def stanze_del_periodo(ses, st, da, a, parte='ambulatori'):
    """(stanze, fino) del riepilogo: le stanze attive (senza sale operatorie) e anche quelle disattivate dopo, se
    nel periodo avevano appuntamenti (anche solo la coda dopo la mezzanotte di una visita della sera prima): in un
    mese passato il lavoro fatto in una stanza chiusa poi conta ancora. Disattivando una stanza i suoi turni non si
    chiudono e la data non resta scritta: per una stanza disattivata i turni contano solo fino al giorno del suo
    ultimo appuntamento non disdetto ('fino', per id), che viene per forza prima dello spegnimento (la scheda non
    lascia disattivare una stanza con appuntamenti da oggi in poi)."""
    # le sale operatorie hanno un riepilogo loro (parte='sala'), con le stesse regole (1.12.6)
    stanze = list(sale_della(st) if parte == 'sala' else stanze_della(st))
    spente = ses.scalars(select(Risorsa).where(Risorsa.struttura_id == st.id, Risorsa.attiva == False,
                                               (Risorsa.tipo == TIPO_SALA) if parte == 'sala' else
                                               (Risorsa.tipo != TIPO_SALA)).order_by(Risorsa.ordine)).all()
    inizio, fine = datetime.combine(da, time(0)), datetime.combine(a + timedelta(days=1), time(0))
    fino = {}
    for r in spente:
        tocca = ses.scalar(select(Appuntamento.id).where(
            Appuntamento.risorsa_id == r.id,
            or_(and_(Appuntamento.inizio >= inizio, Appuntamento.inizio < fine),
                and_(Appuntamento.inizio < inizio, Appuntamento.fine > inizio,
                     Appuntamento.stato.in_(STATI_OCCUPANO)))).limit(1))
        if tocca:
            stanze.append(r)
            ultimo = ses.scalar(select(func.max(Appuntamento.inizio)).where(
                Appuntamento.risorsa_id == r.id, Appuntamento.stato != 'DISDETTO'))
            fino[r.id] = ultimo.date() if ultimo else None
    return stanze, fino


def riepilogo_periodo(ses, st, da, a, adesso=None, parte='ambulatori'):
    """Tutti i numeri del riepilogo fra 'da' e 'a' (compresi), gia' pronti per la pagina, l'Excel e il JSON. Con
    parte='sala' lo stesso conto per le sale operatorie (1.12.6): ore di turno dei chirurghi in sala, ore occupate dagli
    interventi, interventi per gruppo, chirurghi, giorni e mezze giornate con la sala libera."""
    adesso = adesso or datetime.now()
    parte = parte_riepilogo(parte)
    w = PAROLE_RIEPILOGO[parte]
    regole = servizi.Regole(ses, da, a)
    stanze, fino = stanze_del_periodo(ses, st, da, a, parte)
    per_id = {r.id: r for r in stanze}
    attive = {r.id for r in (sale_della(st) if parte == 'sala' else stanze_della(st))}
    # anche il giorno prima: la coda dopo la mezzanotte di una visita cominciata la sera prima conta nel giorno dopo
    appuntamenti = ses.scalars(select(Appuntamento).where(
        Appuntamento.risorsa_id.in_(list(per_id) or [0]),
        Appuntamento.inizio >= datetime.combine(da - timedelta(days=1), time(0)),
        Appuntamento.inizio < datetime.combine(a + timedelta(days=1), time(0)))).all()
    etichette = {o.id: o.etichetta for o in ses.scalars(select(Operatore))}

    def conti():
        x = {k: 0 for k, _ in GRUPPI_PERIODO}
        x.update(totale=0, minuti_turno=0, minuti_occupati=0, minuti_fuori_turno=0)
        return x

    totale = dict(conti(), mezze=0, libere=0)
    righe_stanze = {r.id: dict(conti(), stanza=r.nome + ('' if r.id in attive else
                                                         ' (non più attiva)' if parte == 'ambulatori' else ' (spenta)'),
                               medici=[], mezze=0, libere=0) for r in stanze}
    righe_medici = {}
    giorni = []
    per_giorno, code = {}, {}
    for x in appuntamenti:
        per_giorno.setdefault(x.inizio.date(), []).append(x)
        # solo le visite che vanno davvero oltre la mezzanotte (una che finisce alle 24:00 non ha coda)
        if x.fine > datetime.combine(x.inizio.date() + timedelta(days=1), time(0)):
            code.setdefault(x.inizio.date() + timedelta(days=1), []).append(x)

    def intervallo(x, g):
        """I minuti dell'appuntamento x nel giorno g (la parte prima o dopo la mezzanotte)."""
        da_m = x.inizio.hour * 60 + x.inizio.minute if x.inizio.date() == g else 0
        a_m = x.fine.hour * 60 + x.fine.minute if x.fine.date() == g else 24 * 60
        return da_m, a_m

    g = da
    while g <= a:
        info = regole.giorno(g, st)
        chiusa = info['chiusura'] or (info['festivo'] if info['chiude_festivo'] else None)
        del_giorno = [x for x in per_giorno.get(g, []) if x.risorsa_id in per_id]
        nel_giorno = del_giorno + [x for x in code.get(g, []) if x.risorsa_id in per_id]
        # una stanza disattivata conta i suoi turni solo fino al suo ultimo appuntamento (vedi stanze_del_periodo)
        turni_giorno = {r.id: regole.turni_effettivi(g, st, r.id, info)
                        if r.id in attive or (fino.get(r.id) and g <= fino[r.id]) else [] for r in stanze}
        # un giorno chiuso con soli appuntamenti disdetti (si disdice proprio per chiudere) resta chiuso
        attivo = any(turni_giorno.values()) or any(x.stato != 'DISDETTO' for x in del_giorno)
        riga_g = dict(conti(), data=g.isoformat(), giorno=servizi.GIORNI[g.weekday()],
                      etichetta='%s %d/%d' % (servizi.GIORNI[g.weekday()], g.day, g.month),
                      # chiusa solo se quel giorno non c'e' niente: un turno di un giorno nel festivo lo apre
                      chiusa=chiusa if not attivo else None, aperto=info['giorno_di_apertura'] or attivo,
                      chiusa_ma_aperta=chiusa if attivo else None)
        # i medici: la loro presenza nel giorno, unita su tutte le stanze (due stanze insieme non contano doppio)
        turni_medico, occupa_medico = {}, {}
        for r in stanze:
            turni = turni_giorno[r.id]
            qui = [x for x in nel_giorno if x.risorsa_id == r.id]
            int_turni = unisci_intervalli((_minuti(t.ora_inizio), _minuti(t.ora_fine)) for t in turni)
            int_occ = unisci_intervalli(intervallo(x, g) for x in qui if x.stato in STATI_OCCUPANO)
            m_turno, m_occ = durata_intervalli(int_turni), sovrapposizione(int_turni, int_occ)
            m_fuori = durata_intervalli(int_occ) - m_occ
            for d in (totale, righe_stanze[r.id], riga_g):
                d['minuti_turno'] += m_turno
                d['minuti_occupati'] += m_occ
                d['minuti_fuori_turno'] += m_fuori
            for t in turni:
                turni_medico.setdefault(t.operatore_id, []).append((_minuti(t.ora_inizio), _minuti(t.ora_fine)))
                m = righe_medici.setdefault(t.operatore_id, dict(conti(), medico=etichette.get(t.operatore_id, '?'),
                                                                 giorni=set(), stanze=[]))
                m['giorni'].add(g)
                if r.nome not in m['stanze']:
                    m['stanze'].append(r.nome)
                if etichette.get(t.operatore_id) and etichette[t.operatore_id] not in righe_stanze[r.id]['medici']:
                    righe_stanze[r.id]['medici'].append(etichette[t.operatore_id])
            for x in qui:
                if x.stato in STATI_OCCUPANO:
                    occupa_medico.setdefault(x.operatore_id, []).append(intervallo(x, g))
            for x in qui:
                if x.inizio.date() != g:
                    continue                      # la coda della sera prima: conta nei minuti, non negli appuntamenti
                gruppo = gruppo_periodo(x, adesso)
                m = righe_medici.setdefault(x.operatore_id, dict(conti(), medico=etichette.get(x.operatore_id, '?'),
                                                                 giorni=set(), stanze=[]))
                for d in (totale, righe_stanze[r.id], riga_g, m):
                    d['totale'] += 1
                    d[gruppo] += 1
        for oid in set(turni_medico) | set(occupa_medico):
            t_op = unisci_intervalli(turni_medico.get(oid, []))
            o_op = unisci_intervalli(occupa_medico.get(oid, []))
            m = righe_medici.setdefault(oid, dict(conti(), medico=etichette.get(oid, '?'), giorni=set(), stanze=[]))
            m['minuti_turno'] += durata_intervalli(t_op)
            m['minuti_occupati'] += sovrapposizione(t_op, o_op)
            m['minuti_fuori_turno'] += durata_intervalli(o_op) - sovrapposizione(t_op, o_op)
        giorni.append(riga_g)
        g += timedelta(days=1)

    # le mezze giornate senza nessun medico, dalla matrice degli ambulatori (come la pianificazione); in un giorno
    # che non e' di apertura (la domenica) contano solo quelle con un turno, non tutte le stanze. Per la sala le mezze
    # giornate con la sala libera (nessun turno e nessun intervento), dalla parte della sala della stessa matrice
    aperti = {x['data'] for x in giorni if x['aperto'] and x['chiusa'] is None}
    lunedi = calendario.lunedi_di(da)
    while lunedi <= a:
        for riga in matrice(ses, lunedi, st)['sale' if parte == 'sala' else 'righe']:
            r = righe_stanze.get(riga['risorsa'].id)
            for c in riga['celle']:
                if r is None or not (da <= c['data'] <= a) or c['chiuso'] or c['data'].isoformat() not in aperti:
                    continue
                if c['data'].weekday() not in st.giorni_aperti and c['tutta_libera']:
                    continue
                r['mezze'] += 1
                totale['mezze'] += 1
                if c['tutta_libera']:
                    r['libere'] += 1
                    totale['libere'] += 1
        lunedi += timedelta(days=7)

    def rifinisci(d):
        d['occupazione'] = _percento(d['minuti_occupati'], d['minuti_turno'])
        d['non_presentati_su'] = _percento(d['non_presentati'], d['fatti'] + d['non_presentati'])
        d['ore_turno'], d['ore_occupate'] = testo_ore(d['minuti_turno']), testo_ore(d['minuti_occupati'])
        d['ore_fuori_turno'] = testo_ore(d['minuti_fuori_turno'])
        return d

    medici = []
    for m in righe_medici.values():
        m['n_giorni'] = len(m.pop('giorni'))
        medici.append(rifinisci(m))
    medici.sort(key=lambda m: (-m['minuti_turno'], -m['totale'], m['medico']))
    rifinisci(totale)
    # la frase in cima
    code_minuti = totale['minuti_occupati'] + totale['minuti_fuori_turno']   # senza appuntamenti: solo code
    visite = 'visite' if parte == 'ambulatori' else 'interventi'
    if not totale['totale'] and not totale['minuti_turno'] and not code_minuti:
        frase = 'Nel periodo non ci sono %si né turni %s.' % (w['app'], w['nelle'])
    elif not totale['totale']:
        frase = '%s: nessun %so %s.' % (titolo_periodo(da, a)[:1].upper() + titolo_periodo(da, a)[1:], w['app'], w['nelle'])
        if totale['minuti_turno']:
            frase += ' %s di turno%s.' % (ore_in_parole(totale['minuti_turno']).capitalize(),
                                          '' if totale['minuti_occupati'] else ', senza %s' % visite)
        if code_minuti:
            frase += ' Dopo la mezzanotte ci sono %s di %s cominciat%s il giorno prima.' % (
                ore_in_parole(code_minuti), visite, 'e' if parte == 'ambulatori' else 'i')
        if totale['mezze']:
            frase += ' %d mezz%s giornat%s su %d %s.' % (
                totale['libere'], 'a' if totale['libere'] == 1 else 'e', 'a' if totale['libere'] == 1 else 'e', totale['mezze'],
                w['senza'])
    else:
        pezzi = ['%d %s%s' % (totale['totale'], w['app'], 'o' if totale['totale'] == 1 else 'i')]
        dettagli = ['%d %s' % (totale['fatti'], ('fatt%s' % ('o' if totale['fatti'] == 1 else 'i')) if parte == 'ambulatori'
                                else ('arrivat%s' % ('o' if totale['fatti'] == 1 else 'i')))]
        if totale['non_presentati']:
            dettagli.append('%d non presentat%s%s' % (totale['non_presentati'], 'o' if totale['non_presentati'] == 1 else 'i',
                                                      ' (%s%%)' % ('%g' % totale['non_presentati_su']).replace('.', ',')
                                                      if totale['non_presentati_su'] is not None else ''))
        if totale['disdetti']:
            dettagli.append('%d disdett%s' % (totale['disdetti'], 'o' if totale['disdetti'] == 1 else 'i'))
        if totale['da_segnare']:
            dettagli.append('%d ancora da segnare' % totale['da_segnare'])
        if totale['da_fare']:
            dettagli.append('%d da fare' % totale['da_fare'])
        frase = '%s: %s, %s.' % (titolo_periodo(da, a)[:1].upper() + titolo_periodo(da, a)[1:], pezzi[0],
                                ', '.join(dettagli[:-1]) + (' e ' if len(dettagli) > 1 else '') + dettagli[-1])
        if totale['minuti_turno']:
            frase += ' %s per %s delle ore di turno (%s su %s).' % (
                w['occupate'], il_percento(totale['occupazione']), ore_in_parole(totale['minuti_occupati']),
                ore_in_parole(totale['minuti_turno']))
        if totale['mezze']:
            frase += ' %d mezz%s giornat%s su %d %s.' % (
                totale['libere'], 'a' if totale['libere'] == 1 else 'e', 'a' if totale['libere'] == 1 else 'e', totale['mezze'],
                w['senza'])
    return {
        'parte': parte, 'parole': w,
        'da': da.isoformat(), 'a': a.isoformat(), 'titolo': titolo_periodo(da, a), 'struttura': st.nome,
        'giorni_periodo': (a - da).days + 1, 'frase': frase, 'totale': totale,
        'stanze': [rifinisci(righe_stanze[r.id]) for r in stanze], 'medici': medici,
        'giorni': [rifinisci(x) for x in giorni],
        'aggiornato': adesso.strftime('%d/%m/%Y %H:%M'),
    }


def excel_riepilogo(st, r, adesso=None):
    """Il riepilogo del periodo in Excel: la frase e i totali, poi le stanze, i medici e i giorni (della sala: le sale,
    i chirurghi e i giorni, 1.12.6)."""
    w_ = r.get('parole') or PAROLE_RIEPILOGO['ambulatori']
    App = w_['app'].capitalize() + 'i'
    wb = Workbook()
    ws = wb.active
    ws.title = 'Riepilogo'
    riga = apri_foglio_excel(ws, w_['titolo'], r['titolo'], st, adesso, colonne=6)
    c = ws.cell(riga, 1, testo_excel(r['frase']))
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=6)
    ws.row_dimensions[riga].height = 48
    t = r['totale']
    righe = [[App, t['totale']]] + [[(w_['fatti'] if k == 'fatti' else nome.capitalize()), t[k]]
                                    for k, nome in GRUPPI_PERIODO] + [
        ['Ore di turno', t['minuti_turno'] / 60], ['Ore occupate (dentro i turni)', t['minuti_occupati'] / 60],
        ['Ore prenotate fuori turno', t['minuti_fuori_turno'] / 60],
        ['Occupazione delle ore di turno', t['occupazione']], ['Non presentati su chi doveva venire', t['non_presentati_su']],
        ['Mezze giornate', t['mezze']], ['Mezze giornate %s' % w_['senza'], t['libere']]]
    tabella_excel(ws, riga + 2, ['Cosa', 'Quanto'], [42, 14], righe, filtro=False, blocca=False)
    for n, v in enumerate(righe, start=riga + 3):
        if v[0].startswith('Ore'):
            ws.cell(n, 2).number_format = FORMATO_ORE
        elif v[0].startswith(('Occupazione', 'Non presentati su')):
            ws.cell(n, 2).number_format = FORMATO_PERCENTO
    imposta_stampa_excel(ws, orizzontale=False, struttura=st, periodo=r['titolo'])

    def foglio(nome, intestazioni, larghezze, righe_f, formati, orizzontale=True, a_capo=(), senza_somma=()):
        w = wb.create_sheet(nome)
        rr = apri_foglio_excel(w, '%s · %s' % (w_['titolo'], nome.lower()), r['titolo'], st, adesso,
                               colonne=len(intestazioni))
        tabella_excel(w, rr, intestazioni, larghezze, righe_f, formati=formati, zebra=True, a_capo=a_capo,
                      totali={k: 'somma' for k in range(3, len(intestazioni) + 1)
                              if formati.get(k) != FORMATO_PERCENTO and k not in senza_somma})
        imposta_stampa_excel(w, orizzontale=orizzontale, righe_titolo='%d:%d' % (rr, rr), struttura=st, periodo=r['titolo'])

    numeri = [App, w_['fatti'], 'Non presentati', 'Disdetti', 'Da segnare', 'Da fare']
    chiavi = ['totale'] + [k for k, _ in GRUPPI_PERIODO]
    foglio(w_['Stanze'], [w_['Stanza'], w_['Medici'], 'Ore di turno', 'Ore occupate', 'Occupazione'] + numeri +
           ['Mezze giornate', w_['Senza']], [20, 30, 11, 11, 12, 13, 9, 13, 10, 11, 9, 12, 12],
           [[x['stanza'], ', '.join(x['medici']), x['minuti_turno'] / 60, x['minuti_occupati'] / 60,
             x['occupazione']] + [x[k] for k in chiavi] + [x['mezze'], x['libere']] for x in r['stanze']],
           {3: FORMATO_ORE, 4: FORMATO_ORE, 5: FORMATO_PERCENTO}, a_capo=(2,))
    foglio(w_['Medici'], [w_['Medico'], w_['Stanze'], 'Giorni di turno', 'Ore di turno', 'Ore occupate', 'Occupazione'] + numeri +
           ['Non presentati %'], [24, 30, 10, 11, 11, 12, 13, 9, 13, 10, 11, 9, 13],
           [[x['medico'], ', '.join(x['stanze']), x['n_giorni'], x['minuti_turno'] / 60,
             x['minuti_occupati'] / 60, x['occupazione']] + [x[k] for k in chiavi] + [x['non_presentati_su']]
            for x in r['medici']],
           {4: FORMATO_ORE, 5: FORMATO_ORE, 6: FORMATO_PERCENTO, 13: FORMATO_PERCENTO}, a_capo=(2,), senza_somma=(3,))
    if r['giorni_periodo'] > 1:
        foglio('Giorni', ['Giorno', 'Chiusa', 'Ore di turno', 'Ore occupate', 'Occupazione'] + numeri,
               [16, 22, 11, 11, 12, 13, 9, 13, 10, 11, 9],
               [[x['etichetta'], x['chiusa'] or ('%s, ma con turni o %si' % (x['chiusa_ma_aperta'], w_['app'])
                                                 if x['chiusa_ma_aperta'] else ('' if x['aperto'] else 'giorno di chiusura')),
                 x['minuti_turno'] / 60,
                 x['minuti_occupati'] / 60,
                 x['occupazione']] + [x[k] for k in chiavi] for x in r['giorni']],
               {3: FORMATO_ORE, 4: FORMATO_ORE, 5: FORMATO_PERCENTO}, orizzontale=False, a_capo=(2,))
    return wb


def _periodo_chiesto():
    """(da, a, nome del periodo o '') dall'indirizzo: ?periodo=settimana, oppure ?da=…&a=…; di partenza la
    settimana in corso. Un intervallo al contrario si gira, uno troppo lungo si accorcia."""
    oggi = date.today()
    nome = request.args.get('periodo') or ''
    trovato = periodo_da(nome, oggi)
    if trovato:
        return trovato[0], trovato[1], nome
    if request.args.get('da') or request.args.get('a'):
        da = data_da(request.args.get('da'), oggi)
        a = data_da(request.args.get('a'), da)
        da, a = min(da, a), max(da, a)
        a = min(a, da + timedelta(days=MASSIMO_GIORNI_RIEPILOGO - 1))
        return da, a, ''
    da, a = periodo_da('settimana', oggi)
    return da, a, 'settimana'


def _vicini(da, a, nome):
    """(prima, dopo) come parametri dell'indirizzo: la settimana o il mese accanto, altrimenti lo stesso numero di giorni."""
    if nome in ('settimana', 'settimana-scorsa') or (da.weekday() == 0 and (a - da).days == 6):
        return ({'da': (da - timedelta(days=7)).isoformat(), 'a': (a - timedelta(days=7)).isoformat()},
                {'da': (da + timedelta(days=7)).isoformat(), 'a': (a + timedelta(days=7)).isoformat()})
    if nome in ('mese', 'mese-scorso') or (da.day == 1 and (a + timedelta(days=1)).day == 1):
        # uno o piu' mesi interi: lo stesso numero di mesi prima e dopo
        mesi = (a.year - da.year) * 12 + a.month - da.month + 1

        def primo_del_mese(g, k):
            n = g.year * 12 + g.month - 1 + k
            return date(n // 12, n % 12 + 1, 1)
        prima_da = primo_del_mese(da, -mesi)
        dopo_da = primo_del_mese(da, mesi)
        return ({'da': prima_da.isoformat(), 'a': (da - timedelta(days=1)).isoformat()},
                {'da': dopo_da.isoformat(), 'a': (primo_del_mese(dopo_da, mesi) - timedelta(days=1)).isoformat()})
    n = (a - da).days + 1
    return ({'da': (da - timedelta(days=n)).isoformat(), 'a': (da - timedelta(days=1)).isoformat()},
            {'da': (a + timedelta(days=1)).isoformat(), 'a': (a + timedelta(days=n)).isoformat()})


@bp.route('/riepilogo')
def riepilogo():
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    return pagina_riepilogo(s, st, strutture)


def pagina_riepilogo(s, st, strutture, cruscotto=False):
    """La pagina del riepilogo del periodo; con cruscotto=True la stessa dentro la dashboard (le Statistiche del
    riepilogo live, 1.12.6): senza menu se ?schermo=1, senza Excel e senza collegamenti alle pagine fuori dalla
    dashboard, cosi' passa dal «portiere» della rete locale."""
    da, a, nome = _periodo_chiesto()
    parte = parte_riepilogo(request.args.get('parte'))
    r = riepilogo_periodo(s, st, da, a, parte=parte)
    prima, dopo = _vicini(da, a, nome)
    schermo = cruscotto and request.args.get('schermo') == '1'
    return render_template('ambulatori_riepilogo.html', r=r, st=st, sid=st.id, strutture=strutture, periodi=PERIODI,
                           periodo=nome, prima=prima, dopo=dopo, gruppi=GRUPPI_PERIODO, singolari=SINGOLARI_PERIODO,
                           parte=parte, parti=PARTI_RIEPILOGO, ha_sale=bool(sale_della(st)), w=r['parole'],
                           cruscotto=cruscotto, schermo=schermo,
                           vista='live.statistiche' if cruscotto else 'ambulatori.riepilogo',
                           sezione='live' if cruscotto else 'riepilogo-periodo',
                           massimo=MASSIMO_GIORNI_RIEPILOGO, data_menu=min(a, date.today()).isoformat(),
                           titolo='%s · %s' % ('Statistiche' if cruscotto else 'Riepilogo del periodo', r['titolo']))


@bp.route('/riepilogo.xlsx')
def riepilogo_excel():
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    da, a, _ = _periodo_chiesto()
    r = riepilogo_periodo(s, st, da, a, parte=parte_riepilogo(request.args.get('parte')))
    nome = '%s-%s%s.xlsx' % (r['parole']['file'], da.isoformat(), '' if da == a else '-%s' % a.isoformat())
    return scarica_excel(excel_riepilogo(st, r), nome)


@bp.route('/riepilogo.json')
def riepilogo_json():
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return json_sicuro({'errore': 'nessuna struttura'})
    da, a, _ = _periodo_chiesto()
    return json_sicuro(riepilogo_periodo(s, st, da, a, parte=parte_riepilogo(request.args.get('parte'))))
