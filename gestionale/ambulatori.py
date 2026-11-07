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
from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from sqlalchemy import select

import calendario
import servizi
from anagrafiche import Modulo, stanza_gia_assegnata
from comune import data_da, destinazione_sicura, intero, mese_da, scarica_excel, struttura_scelta, testo_excel
from modelli import Operatore, Risorsa, Turno

bp = Blueprint('ambulatori', __name__, url_prefix='/ambulatori')
_fornitore = None
_lucchetto = None

META = time(14, 0)                 # la mattina finisce, il pomeriggio comincia
MINIMO_LIBERO = 60                 # minuti liberi da segnalare dentro una mezza giornata occupata
DESTINATARIO = 'Direttore Sanitario'
COMPILATO_DA = 'Segreteria'
TITOLO_MATRICE = 'MATRICE TURNI AMBULATORI E DISPONIBILITÀ INTEGRATIVE'
TITOLO_PROGRAMMAZIONE = 'PROGRAMMAZIONE AMBULATORI'
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
    return [r for r in st.risorse if r.attiva and r.tipo != 'SALA_OPERATORIA']


def matrice(ses, lunedi, st, tipo=False):
    """La matrice della settimana che comincia il lunedi: per ogni stanza
    attiva e ogni mezza giornata dei giorni di apertura, chi c'e' (turni
    effettivi: medico presente, struttura aperta), le ore libere, gli assenti
    e le chiusure. Con tipo=True e' la settimana tipo: solo i turni che si
    ripetono, senza assenze, chiusure e festivi, come sara' una settimana
    qualsiasi."""
    giorni_tutti = [lunedi + timedelta(days=i) for i in range(7)]
    regole = servizi.Regole(ses, giorni_tutti[0], giorni_tutti[-1])
    giorni = [g for g in giorni_tutti if g.weekday() in st.giorni_aperti or regole.turni_validi(g, st)]
    meta = mezze_giornate(st)
    info = {g: regole.giorno(g, st) for g in giorni}
    righe, libere, parziali = [], 0, 0
    for r in stanze_della(st):
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
            for m in meta:
                presenze = sorted(({'turno': t, 'operatore': t.operatore,
                                    'da': max(t.ora_inizio, m['da']), 'a': min(t.ora_fine, m['a'])}
                                   for t in turni if t.ora_inizio < m['a'] and m['da'] < t.ora_fine),
                                  key=lambda p: (p['da'], p['operatore'].cognome))
                # in un festivo in cui la struttura chiude resta solo chi ha un turno di quel
                # giorno: la sua mezza giornata e' occupata, l'altra resta chiusa
                chiuso_qui = chiuso if not presenze else None
                # le ore libere si elencano solo in una mezza giornata occupata: una tutta
                # libera dice DISPONIBILE e basta
                vuoti = [] if chiuso_qui or not presenze else buchi(presenze, m['da'], m['a'])
                cella = {'data': g, 'meta': m, 'presenze': presenze, 'libere': vuoti, 'chiuso': chiuso_qui,
                         'assenti': [x for x in assenti if x[2].ora_inizio < m['a'] and m['da'] < x[2].ora_fine],
                         'tutta_libera': not presenze and not chiuso_qui,
                         'proposta': (vuoti[0] if vuoti else (m['da'], m['a']))}
                if cella['tutta_libera']:
                    libere += 1
                elif vuoti:
                    parziali += 1
                celle.append(cella)
        righe.append({'risorsa': r, 'celle': celle})
    return {'lunedi': lunedi, 'giorni': giorni, 'meta': meta, 'righe': righe, 'info': info, 'tipo': tipo,
            'libere': libere, 'parziali': parziali}


# ======================================================= programmazione
def _gruppo(specialita):
    s = (specialita or '').strip()
    return s[:1].upper() + s[1:] if s else SENZA_SPECIALITA


def _elenco_giorni(giorni):
    """'il 2, il 9 e il 16'."""
    testi = ['il %d' % g.day for g in giorni]
    return testi[0] if len(testi) == 1 else ', '.join(testi[:-1]) + ' e ' + testi[-1]


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
    righe = []
    for t in regole.turni:
        if t.risorsa_id not in stanze:
            continue
        date_valide = [g for g in giorni if t.vale_il(g)]
        if not date_valide:
            continue
        singolo = servizi.e_di_un_giorno(t)
        presenti, saltate = [], []
        for g in date_valide:
            i = info[g]
            if t.operatore_id in i['assenze']:
                saltate.append((g, 'assente: %s' % i['assenze'][t.operatore_id].lower()))
            elif i['chiusura']:
                saltate.append((g, 'chiusa: %s' % i['chiusura'].lower()))
            elif i['chiude_festivo'] and not singolo:
                saltate.append((g, 'chiusa: %s' % i['festivo'].lower()))
            else:
                presenti.append(g)
        note = []
        if singolo:
            note.append('un giorno solo')
        else:
            if t.valido_da and t.valido_da > primo:
                note.append('dal %d' % t.valido_da.day)
            if t.valido_a and t.valido_a < ultimo:
                note.append('fino al %d' % t.valido_a.day)
        motivi = {}
        for g, motivo in saltate:
            motivi.setdefault(motivo, []).append(g)
        for motivo, quando in motivi.items():
            note.append('non %s (%s)' % (_elenco_giorni(quando), motivo))
        if not presenti:
            note.append('nessuna seduta nel mese')
        if t.passo_proprio:
            note.append('fasce da %d minuti' % t.passo_proprio)
        righe.append({'turno': t, 'operatore': t.operatore, 'specialita': _gruppo(t.operatore.specialita),
                      'giorno': t.giorno_settimana, 'date': presenti, 'saltate': saltate, 'singolo': singolo,
                      'ora_inizio': t.ora_inizio, 'ora_fine': t.ora_fine, 'risorsa': stanze[t.risorsa_id],
                      'note': note})
    righe.sort(key=lambda r: (r['specialita'] == SENZA_SPECIALITA, r['specialita'].lower(),
                              r['operatore'].cognome.lower(), (r['operatore'].nome or '').lower(),
                              r['giorno'], r['ora_inizio'], r['risorsa'].ordine, r['risorsa'].nome))
    gruppi = []
    for r in righe:
        if not gruppi or gruppi[-1]['specialita'] != r['specialita']:
            gruppi.append({'specialita': r['specialita'], 'righe': []})
        gruppi[-1]['righe'].append(r)
    # il calendario: giorno per giorno, chi c'e' in quale stanza
    calendario_mese = []
    for g in giorni:
        presenze = sorted(regole.turni_effettivi(g, st, None, info[g]),
                          key=lambda t: (stanze[t.risorsa_id].ordine if t.risorsa_id in stanze else 0, t.ora_inizio))
        calendario_mese.append({'data': g, 'info': info[g], 'presenze': [t for t in presenze if t.risorsa_id in stanze]})
    return {'primo': primo, 'ultimo': ultimo, 'righe': righe, 'gruppi': gruppi, 'calendario': calendario_mese,
            'medici': len({r['operatore'].id for r in righe})}


# ================================================================ Excel
BLU = '154381'
VERDE_PIENO = 'C6EFCE'      # DISPONIBILE
VERDE_CHIARO = 'EAF5E3'     # ore libere dentro una mezza giornata occupata
GRIGIO = 'E7E9E6'
ARANCIO = 'B35F16'
_sottile = Side(style='thin', color='9AA5AD')
BORDO = Border(left=_sottile, right=_sottile, top=_sottile, bottom=_sottile)
_spesso = Side(style='medium', color=BLU)


def _intestazione(c, testo):
    c.value = testo
    c.font = Font(bold=True, color='FFFFFF')
    c.fill = PatternFill('solid', fgColor=BLU)
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    c.border = BORDO


def _stampa(ws, righe_titolo, orizzontale=True):
    ws.page_setup.orientation = 'landscape' if orizzontale else 'portrait'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.print_title_rows = righe_titolo
    ws.oddFooter.right.text = 'Pagina &P di &N'
    ws.page_margins.left = ws.page_margins.right = 0.4


def _titolo(ws, riga, testo, colonne, dimensione=14):
    c = ws.cell(riga, 1, testo)
    c.font = Font(name='Calibri', size=dimensione, bold=True, color=BLU)
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    c.alignment = Alignment(horizontal='left', vertical='center')


def excel_matrice(st, vista, adesso=None):
    """Il foglio della matrice: intestazione con struttura, titolo, settimana,
    destinatario e chi lo compila; la tabella stanze x mezze giornate; la
    legenda e le righe per le firme."""
    adesso = adesso or datetime.now()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Matrice'
    giorni, meta = vista['giorni'], vista['meta']
    colonne = 1 + len(giorni) * len(meta)
    lunedi = vista['lunedi']
    domenica = lunedi + timedelta(days=6)
    _titolo(ws, 1, testo_excel(st.nome), colonne, 16)
    _titolo(ws, 2, TITOLO_MATRICE, colonne, 13)
    periodo = ('Settimana tipo: i turni che si ripetono ogni settimana, senza assenze e chiusure' if vista['tipo'] else
               'Settimana dal %d %s al %d %s %d' % (lunedi.day, servizi.MESI[lunedi.month - 1], domenica.day,
                                                   servizi.MESI[domenica.month - 1], domenica.year))
    ws.cell(3, 1, periodo).font = Font(italic=True)
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=colonne)
    ws.cell(4, 1, 'Destinatario: %s   ·   Compilato da: %s   ·   Data: %s' % (
        DESTINATARIO, COMPILATO_DA, adesso.strftime('%d/%m/%Y')))
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=colonne)
    # intestazione della tabella: due righe, il giorno sopra le sue mezze giornate
    r0 = 6
    _intestazione(ws.cell(r0, 1), 'AMBULATORIO')
    ws.merge_cells(start_row=r0, start_column=1, end_row=r0 + 1, end_column=1)
    for k, g in enumerate(giorni):
        c1 = 2 + k * len(meta)
        i = vista['info'][g]
        testo = '%s %d/%d' % (servizi.GIORNI[g.weekday()].capitalize(), g.day, g.month)
        if not vista['tipo'] and (i['chiusura'] or i['festivo']):
            testo += '\n%s' % (i['chiusura'] or i['festivo'])
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
    verde, verde_chiaro, grigio = (PatternFill('solid', fgColor=x) for x in (VERDE_PIENO, VERDE_CHIARO, GRIGIO))
    riga = r0 + 2
    for r in vista['righe']:
        c = ws.cell(riga, 1, testo_excel(r['risorsa'].nome))
        c.font, c.border = Font(bold=True), BORDO
        c.alignment = Alignment(vertical='center', wrap_text=True)
        for k, cella in enumerate(r['celle']):
            c = ws.cell(riga, 2 + k)
            c.border = BORDO
            c.alignment = Alignment(vertical='top', wrap_text=True)
            if cella['chiuso']:
                c.value = 'CHIUSO: %s' % cella['chiuso']
                c.fill = grigio
                c.font = Font(color='5B6B75', italic=True)
            elif cella['tutta_libera']:
                c.value = 'DISPONIBILE' + ''.join('\n(%s assente: %s)' % (testo_excel(o.etichetta), motivo.lower())
                                                  for o, motivo, _ in cella['assenti'])
                c.fill = verde
                c.font = Font(bold=True, color='1E6B2E')
            else:
                testi = ['%s %s' % (testo_excel(p['operatore'].etichetta), fascia(p['da'], p['a']).replace('–', '-'))
                         for p in cella['presenze']]
                testi += ['libero %s' % fascia(da, a).replace('–', '-') for da, a in cella['libere']]
                testi += ['(%s assente: %s)' % (testo_excel(o.etichetta), motivo.lower()) for o, motivo, _ in cella['assenti']]
                c.value = '\n'.join(testi)
                if cella['libere']:
                    c.fill = verde_chiaro
        ws.row_dimensions[riga].height = max(30, 15 * max(1, max(
            (len(x['presenze']) + len(x['libere']) + len(x['assenti']) for x in r['celle']), default=1)))
        riga += 1
    if not vista['righe']:
        ws.cell(riga, 1, 'Nessuna stanza attiva in questa struttura.')
        riga += 1
    riga += 1
    ws.cell(riga, 1, 'In verde le fasce libere, disponibili per nuovi ambulatori (disponibilità integrative): '
                     '«DISPONIBILE» è una mezza giornata tutta libera, «libero» le ore avanzate in una occupata.')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    ws.cell(riga, 1).alignment = Alignment(wrap_text=True)
    ws.row_dimensions[riga].height = 30
    riga += 1
    ws.cell(riga, 1, 'Calcolata dai turni, dalle assenze e dalle chiusure scritte nel Gestionale Agende il %s alle %s.'
            % (adesso.strftime('%d/%m/%Y'), adesso.strftime('%H:%M'))).font = Font(italic=True, color='5B6B75')
    ws.merge_cells(start_row=riga, start_column=1, end_row=riga, end_column=colonne)
    riga += 2
    ws.cell(riga, 1, 'Il %s' % DESTINATARIO).font = Font(bold=True)
    ws.cell(riga, 1 + colonne // 2, 'La %s' % COMPILATO_DA).font = Font(bold=True)
    riga += 1
    ws.cell(riga, 1, '_' * 30)
    ws.cell(riga, 1 + colonne // 2, '_' * 30)
    ws.freeze_panes = ws.cell(r0 + 2, 2)
    _stampa(ws, '%d:%d' % (r0, r0 + 1))
    return wb


def excel_programmazione(st, vista, adesso=None):
    """Due fogli: la programmazione per specialita' (il foglio che si
    compilava a mano, con le date calcolate) e il calendario del mese."""
    adesso = adesso or datetime.now()
    primo = vista['primo']
    nome_mese = '%s %d' % (servizi.MESI[primo.month - 1], primo.year)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Programmazione'
    intestazioni = ['Specialità', 'Medico', 'Giorno', 'Date di %s' % servizi.MESI[primo.month - 1], 'Orario',
                    'Stanza', 'Note']
    larghezze = [22, 26, 11, 24, 13, 18, 48]
    _titolo(ws, 1, '%s — %s' % (testo_excel(st.nome), TITOLO_PROGRAMMAZIONE), len(intestazioni), 15)
    ws.cell(2, 1, nome_mese.capitalize()).font = Font(size=12, bold=True)
    ws.cell(3, 1, 'Calcolata dai turni, dalle assenze e dalle chiusure scritte nel Gestionale Agende il %s alle %s: '
                  'le date sono quelle in cui il medico c\'è davvero.' % (adesso.strftime('%d/%m/%Y'),
                                                                        adesso.strftime('%H:%M'))
            ).font = Font(italic=True, color='5B6B75')
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(intestazioni))
    r0 = 5
    for c, (testo, l) in enumerate(zip(intestazioni, larghezze), start=1):
        _intestazione(ws.cell(r0, c), testo)
        ws.column_dimensions[get_column_letter(c)].width = l
    riga = r0 + 1
    for gruppo in vista['gruppi']:
        for n, r in enumerate(gruppo['righe']):
            valori = [gruppo['specialita'], testo_excel(r['operatore'].etichetta),
                      servizi.GIORNI[r['giorno']].capitalize(),
                      ', '.join(str(g.day) for g in r['date']) or '—',
                      fascia(r['ora_inizio'], r['ora_fine']).replace('–', '-'), testo_excel(r['risorsa'].nome),
                      '; '.join(r['note'])]
            for c, v in enumerate(valori, start=1):
                cella = ws.cell(riga, c, v)
                cella.border = BORDO
                cella.alignment = Alignment(vertical='top', wrap_text=True)
                if n == 0:
                    cella.border = Border(left=_sottile, right=_sottile, top=_spesso, bottom=_sottile)
            ws.cell(riga, 1).font = Font(bold=True, color=BLU) if n == 0 else Font(color='5B6B75')
            if not r['date']:
                ws.cell(riga, 4).font = Font(color=ARANCIO)
            riga += 1
    if not vista['righe']:
        ws.cell(riga, 1, 'Nessun turno nelle stanze attive di questa struttura in %s.' % nome_mese)
        riga += 1
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    if vista['righe']:
        ws.auto_filter.ref = 'A%d:%s%d' % (r0, get_column_letter(len(intestazioni)), riga - 1)
    _stampa(ws, '%d:%d' % (r0, r0))
    # il calendario: giorno per giorno
    wc = wb.create_sheet('Calendario')
    _titolo(wc, 1, 'Calendario di %s — %s' % (nome_mese, testo_excel(st.nome)), 5, 14)
    for c, (testo, l) in enumerate(zip(['Data', 'Giorno', 'Stanza', 'Medico', 'Orario'], [12, 11, 18, 26, 13]), start=1):
        _intestazione(wc.cell(3, c), testo)
        wc.column_dimensions[get_column_letter(c)].width = l
    riga = 4
    grigio = PatternFill('solid', fgColor=GRIGIO)
    for giorno in vista['calendario']:
        g, i = giorno['data'], giorno['info']
        if g.weekday() not in st.giorni_aperti and not giorno['presenze']:
            continue
        motivo = i['chiusura'] or (i['festivo'] if i['chiude_festivo'] else None)
        if not giorno['presenze']:
            for c, v in enumerate([g, servizi.GIORNI[g.weekday()].capitalize(),
                                   ('chiusa: %s' % motivo) if motivo else 'nessun medico in turno', '', ''], start=1):
                cella = wc.cell(riga, c, v)
                cella.border, cella.fill = BORDO, grigio
            wc.cell(riga, 1).number_format = 'dd/mm/yyyy'
            riga += 1
            continue
        for n, t in enumerate(giorno['presenze']):
            valori = [g if n == 0 else None, servizi.GIORNI[g.weekday()].capitalize() if n == 0 else None,
                      testo_excel(t.risorsa.nome), testo_excel(t.operatore.etichetta),
                      fascia(t.ora_inizio, t.ora_fine).replace('–', '-')]
            for c, v in enumerate(valori, start=1):
                cella = wc.cell(riga, c, v)
                cella.border = BORDO
                if n == 0:
                    cella.border = Border(left=_sottile, right=_sottile, top=_spesso, bottom=_sottile)
            wc.cell(riga, 1).number_format = 'dd/mm/yyyy'
            riga += 1
    wc.freeze_panes = 'A4'
    _stampa(wc, '3:3', orizzontale=False)
    return wb


# =============================================================== pagine
def _settimana_di(iso):
    g = data_da(iso)
    return calendario.lunedi_di(g), g


def _titolo_settimana(lunedi):
    domenica = lunedi + timedelta(days=6)
    return 'Settimana dal %d %s al %d %s %d' % (lunedi.day, servizi.MESI[lunedi.month - 1], domenica.day,
                                               servizi.MESI[domenica.month - 1], domenica.year)


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
                           aaaamm=lunedi.strftime('%Y-%m'))


@bp.route('/settimana/<iso>.xlsx')
def settimana_excel(iso):
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    lunedi, _ = _settimana_di(iso)
    tipo = request.args.get('tipo') == '1'
    vista = matrice(s, lunedi, st, tipo=tipo)
    nome = 'matrice-ambulatori-%s.xlsx' % ('settimana-tipo' if tipo else lunedi.isoformat())
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
                           data_menu=max(primo, min(date.today(), ultimo)).isoformat())


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
    g = data_da(request.form.get('data'))
    lunedi = calendario.lunedi_di(g)
    t = s.get(Turno, intero(request.form.get('turno')))
    if t is None or t.risorsa.struttura_id != st.id:
        flash('Turno non trovato: forse è già stato tolto.', 'errore')
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
