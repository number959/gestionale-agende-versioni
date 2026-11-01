# -*- coding: utf-8 -*-
"""Le pagine della segreteria oltre alla griglia del giorno: settimana, mese,
elenco del giorno, conferme, stampa, promemoria per il paziente, prima
disponibilita', statistiche, impostazioni (backup e testo dei messaggi)."""
import json
import os
import re
import threading
from datetime import date, datetime, time, timedelta

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   abort, send_file)
from sqlalchemy import select

from modelli import (Risorsa, Operatore, Prestazione, Appuntamento, Paziente,
                     STATI, STATI_ATTIVI, ETICHETTA_STATO, leggi_impostazione,
                     scrivi_impostazione, aggiorna_database)
import servizi
from comune import PRIMA, ULTIMA, data_da, intero, scarica_excel, struttura_scelta
import calendario
import pazienti
import backup
import autoripara
import sala

bp = Blueprint('viste', __name__)
_fornitore = None
_lucchetto = threading.Lock()
_sessionmaker = None        # funzione che restituisce la fabbrica di sessioni dell'app


TESTO_PREDEFINITO = (
    "Gentile {paziente}, le ricordiamo l'appuntamento di {giorno} alle ore {ora} "
    "presso {struttura}{indirizzo} ({prestazione}, {medico}).{preparazione} "
    "Per disdire o spostare l'appuntamento {recapito}. Grazie.")
OGGETTO_PREDEFINITO = 'Promemoria appuntamento del {data} alle {ora} - {struttura}'
SEGNAPOSTO = ['paziente', 'giorno', 'data', 'ora', 'struttura', 'indirizzo', 'prestazione',
              'medico', 'stanza', 'preparazione', 'recapito', 'telefono_struttura']


def collega(app, fornitore_sessione, lucchetto=None, fabbrica=None):
    global _fornitore, _lucchetto, _sessionmaker
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    _sessionmaker = fabbrica
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ===================================================== testo dei messaggi
def _cortese(p):
    """'ESPOSITO ANNA' -> 'Anna Esposito': nei messaggi il tutto maiuscolo
    sembra un urlo."""
    testo = ('%s %s' % (p.nome or '', p.cognome or '')).strip() if p else ''
    return testo.title() if testo.isupper() else testo


def testo_messaggio(a, modello=None):
    """Il messaggio di promemoria per l'appuntamento, dal modello scelto in
    Impostazioni. I segnaposto vuoti non lasciano parentesi o virgole sole."""
    st = a.risorsa.struttura if a.risorsa else None
    prep = (a.prestazione.preparazione or '').strip() if a.prestazione else ''
    valori = {
        'paziente': _cortese(a.paziente) or 'paziente',
        'giorno': '%s %d %s' % (servizi.GIORNI[a.inizio.weekday()], a.inizio.day,
                                servizi.MESI[a.inizio.month - 1]),
        'data': a.inizio.strftime('%d/%m/%Y'),
        'ora': a.inizio.strftime('%H:%M'),
        'struttura': st.nome if st else '',
        'indirizzo': (', ' + st.indirizzo.strip()) if st and (st.indirizzo or '').strip() else '',
        'prestazione': a.prestazione.nome if a.prestazione else '',
        'medico': a.operatore.etichetta if a.operatore else '',
        'stanza': a.risorsa.nome if a.risorsa else '',
        'preparazione': (' ' + prep if prep.endswith(('.', '!', '?')) else ' ' + prep + '.') if prep else '',
        'recapito': ('chiami il ' + st.telefono.strip()) if st and (st.telefono or '').strip() else 'ci contatti',
        'telefono_struttura': (st.telefono or '').strip() if st else '',
    }
    # {Paziente} come {paziente}: a inizio frase Word mette la maiuscola
    testo = re.sub(r'\{(\w+)\}', lambda m: valori.get(m.group(1).lower(), m.group(0)),
                   modello or TESTO_PREDEFINITO)
    for brutto, bello in (('(, ', '('), (', )', ')'), (' ()', ''), ('()', ''), (' .', '.'), ('..', '.')):
        testo = testo.replace(brutto, bello)
    return ' '.join(testo.split())


def modelli_messaggio(s):
    return (leggi_impostazione(s, 'testo_promemoria', '') or TESTO_PREDEFINITO,
            leggi_impostazione(s, 'oggetto_promemoria', '') or OGGETTO_PREDEFINITO)


def contatti(a, modello, oggetto):
    """Collegamenti tel:, WhatsApp e email col messaggio gia' scritto."""
    if a.paziente is None:
        return {}
    return pazienti.collegamenti_paziente(a.paziente, testo_messaggio(a, modello),
                                          testo_messaggio(a, oggetto))


# ============================================================== settimana
@bp.route('/settimana/<iso>')
def settimana(iso):
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso)
    lunedi = calendario.lunedi_di(g)
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    medico = s.get(Operatore, intero(request.args.get('medico'))) if request.args.get('medico') else None
    if medico is not None:
        vista = servizi.settimana_medico(s, lunedi, medico.id, st.id)
    else:
        vista = servizi.settimana(s, lunedi, st.id)
    domenica = lunedi + timedelta(days=6)
    return render_template(
        'settimana.html', vista=vista, st=st, sid=st.id, strutture=strutture, medici=medici,
        medico=medico, lunedi=lunedi, oggi=date.today(),
        titolo='Settimana dal %d %s al %d %s %d' % (
            lunedi.day, servizi.MESI[lunedi.month - 1], domenica.day,
            servizi.MESI[domenica.month - 1], domenica.year),
        prima=(lunedi - timedelta(days=7)).isoformat(), dopo=(lunedi + timedelta(days=7)).isoformat(),
        giorni_nomi=servizi.GIORNI, sezione='settimana', data_menu=g.isoformat())


# ================================================================== mese
@bp.route('/mese/<aaaamm>')
def mese(aaaamm):
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    m = re.fullmatch(r'(\d{4})-(\d{2})', aaaamm or '')
    anno, numero = (int(m.group(1)), int(m.group(2))) if m else (date.today().year, date.today().month)
    if not (1 <= numero <= 12 and PRIMA.year <= anno <= ULTIMA.year - 1):
        anno, numero = date.today().year, date.today().month
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    medico = s.get(Operatore, intero(request.args.get('medico'))) if request.args.get('medico') else None
    vista = servizi.mese(s, anno, numero, st.id, medico.id if medico else None)
    precedente = date(anno, numero, 1) - timedelta(days=1)
    seguente = date(anno + (numero == 12), numero % 12 + 1, 1)
    return render_template(
        'mese.html', vista=vista, st=st, sid=st.id, strutture=strutture, medici=medici,
        medico=medico, oggi=date.today(), numero=numero,
        titolo='%s %d' % (servizi.MESI[numero - 1].capitalize(), anno),
        prima='%04d-%02d' % (precedente.year, precedente.month),
        dopo='%04d-%02d' % (seguente.year, seguente.month),
        giorni_brevi=servizi.GIORNI_BREVI, sezione='mese',
        data_menu=date(anno, numero, 1).isoformat())


# ======================================================= elenco del giorno
@bp.route('/giorno/<iso>/elenco')
def elenco_giorno(iso):
    """La scrivania dell'accettazione: tutti gli appuntamenti del giorno in
    ordine di ora, con telefono e i pulsanti per arrivato, disdetto..."""
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso)
    apps = servizi.elenco_giorno(s, g, st.id)
    modello, oggetto = modelli_messaggio(s)
    adesso = datetime.now()
    attesa = {a.id: int((adesso - a.arrivato_alle).total_seconds() // 60)
              for a in apps if a.stato == 'ARRIVATO' and a.arrivato_alle and g == date.today()
              and a.arrivato_alle <= adesso}
    conteggi = {k: sum(1 for a in apps if a.stato == k) for k, _ in STATI}
    import segreteria
    chi_chiamare = {}
    for a in apps:
        if a.stato == 'DISDETTO' and a.inizio > adesso:
            n = len(segreteria.candidati_attesa(s, a))
            if n:
                chi_chiamare[a.id] = n
    return render_template(
        'elenco.html', apps=apps, g=g, st=st, sid=st.id, strutture=strutture,
        chi_chiamare=chi_chiamare, nota=segreteria.nota_del_giorno(s, st.id, g),
        appunti=segreteria.appunti_del_giorno(s, g, st.id), indirizzo_prenota=segreteria.indirizzo_prenota,
        contatti={a.id: contatti(a, modello, oggetto) for a in apps},
        attesa=attesa, conteggi=conteggi, stati=STATI, titolo=servizi.etichetta_giorno(g),
        ieri=(g - timedelta(days=1)).isoformat(), domani=(g + timedelta(days=1)).isoformat(),
        torna=request.full_path.rstrip('?'), sezione='elenco', data_menu=g.isoformat())


# ================================================================ conferme
@bp.route('/conferme')
def conferme():
    """Il giro delle conferme: gli appuntamenti del prossimo giorno di
    lavoro, con WhatsApp, email e telefono gia' pronti."""
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(request.args.get('data'), None) if request.args.get('data') else \
        servizi.prossimo_giorno_con_appuntamenti(s, date.today(), st.id)
    apps = servizi.elenco_giorno(s, g, st.id, STATI_ATTIVI)
    modello, oggetto = modelli_messaggio(s)
    apps = sorted(apps, key=lambda a: (a.stato != 'PRENOTATO', a.inizio))
    import invii
    cfg = invii.impostazioni(s)
    return render_template(
        'conferme.html', apps=apps, g=g, st=st, sid=st.id, strutture=strutture,
        contatti={a.id: contatti(a, modello, oggetto) for a in apps},
        promemoria=invii.stato_promemoria(s, apps), stati_invio=invii.STATI, canali_invio=invii.CANALI,
        canale={a.id: invii.canale_promemoria(cfg, a.paziente)[0] for a in apps},
        promemoria_attivi=cfg['promemoria_attivo'] == '1', ora_promemoria=cfg['promemoria_ora'],
        da_confermare=sum(1 for a in apps if a.stato == 'PRENOTATO'),
        titolo=servizi.etichetta_giorno(g),
        ieri=(g - timedelta(days=1)).isoformat(), domani=(g + timedelta(days=1)).isoformat(),
        torna=request.full_path.rstrip('?'), sezione='conferme', data_menu=g.isoformat())


# ================================================================== stampa
@bp.route('/stampa/<iso>')
def stampa(iso):
    """Il foglio del giorno in A4 orizzontale: una tabella per stanza, oppure
    tutto in ordine di ora."""
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    g = data_da(iso)
    preferenze = impostazioni_stampa(s)
    per = request.args.get('per') if request.args.get('per') in ('ora', 'stanza') else preferenze['ordine']
    orientamento = request.args.get('orientamento') if request.args.get('orientamento') in (
        'orizzontale', 'verticale') else preferenze['orientamento']
    tutti = request.args.get('tutti') == '1'
    apps = servizi.elenco_giorno(s, g, st.id, None if tutti else STATI_ATTIVI)
    gruppi = []
    if per == 'stanza':
        for r in s.scalars(select(Risorsa).where(Risorsa.struttura_id == st.id).order_by(Risorsa.ordine)):
            qui = [a for a in apps if a.risorsa_id == r.id]
            if qui:
                gruppi.append((r.nome, qui))
    elif apps:
        gruppi.append(('', apps))
    extra = []
    for a in apps:
        for k in a.valori_extra:
            if k not in extra:
                extra.append(k)
    colonne = set(preferenze['colonne'])
    if 'extra' not in colonne:
        extra = []
    info = servizi.Regole(s, g, g).giorno(g, st)
    import segreteria
    return render_template('stampa.html', gruppi=gruppi, g=g, st=st, sid=st.id, per=per,
                           nota=segreteria.nota_del_giorno(s, st.id, g),
                           tutti=tutti, extra=extra, info=info, totale=len(apps), colonne=colonne,
                           orientamento=orientamento,
                           titolo=servizi.etichetta_giorno(g), adesso=datetime.now())


# ======================================================= foglio del giorno
COLONNE_STAMPA = [('telefono', 'Telefono'), ('prestazione', 'Prestazione'), ('medico', 'Medico'),
                  ('tipo', 'Tipo di visita e convenzione'), ('importo', 'Importo'),
                  ('extra', 'Campi in più della prestazione (sedazione, anestesista…)'), ('note', 'Note')]
STAMPA_PREDEFINITA = {'colonne': [c for c, _ in COLONNE_STAMPA], 'orientamento': 'orizzontale', 'ordine': 'stanza'}


def impostazioni_stampa(s):
    """Colonne, orientamento e ordine del foglio del giorno: quello salvato in
    Impostazioni, con i valori sconosciuti scartati (arriva dal database)."""
    try:
        dati = json.loads(leggi_impostazione(s, 'stampa_giorno', '') or '{}')
    except ValueError:
        dati = {}
    if not isinstance(dati, dict):
        dati = {}
    note = {c for c, _ in COLONNE_STAMPA}
    colonne = dati.get('colonne')
    return {
        'colonne': [c for c in colonne if c in note] if isinstance(colonne, list) else list(STAMPA_PREDEFINITA['colonne']),
        'orientamento': dati.get('orientamento') if dati.get('orientamento') in ('orizzontale', 'verticale') else 'orizzontale',
        'ordine': dati.get('ordine') if dati.get('ordine') in ('stanza', 'ora') else 'stanza',
    }


@bp.route('/appuntamento/<int:aid>/promemoria')
def promemoria(aid):
    """Il foglietto da dare al paziente che prenota allo sportello."""
    s = ses()
    a = s.get(Appuntamento, aid)
    if a is None:
        abort(404)
    st = a.risorsa.struttura if a.risorsa else None
    return render_template('promemoria.html', a=a, st=st, sid=st.id if st else None,
                           giorno=servizi.etichetta_giorno(a.inizio.date()))


# ==================================================== prima disponibilita'
@bp.route('/disponibilita')
def disponibilita():
    s = ses()
    st, strutture = struttura_scelta(s)
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    prestazioni = s.scalars(select(Prestazione).order_by(Prestazione.nome)).all()
    medico = s.get(Operatore, intero(request.args.get('medico'))) if request.args.get('medico') else None
    prest = s.get(Prestazione, intero(request.args.get('prestazione'))) if request.args.get('prestazione') else None
    durata = intero(request.args.get('durata')) or (prest.durata_min if prest else 30)
    durata = min(max(durata, 5), 8 * 60)
    dal = max(data_da(request.args.get('dal'), date.today()), date.today())
    fascia = request.args.get('fascia') or ''
    dalle, alle = {'mattina': (None, time(13, 0)), 'pomeriggio': (time(13, 0), None)}.get(fascia, (None, None))
    tutte = request.args.get('tutte') == '1'
    paziente = s.get(Paziente, intero(request.args.get('paziente_id'))) if request.args.get('paziente_id') else None
    risultati = None
    if medico is not None:
        risultati = servizi.disponibilita(s, medico.id, durata, dal,
                                          None if tutte or st is None else st.id,
                                          giorni=90, massimo=20, dalle=dalle, alle=alle)
    return render_template('disponibilita.html', medici=medici, prestazioni=prestazioni,
                           medico=medico, prest=prest, durata=durata, dal=dal, fascia=fascia,
                           tutte=tutte, risultati=risultati, st=st, sid=st.id if st else None,
                           strutture=strutture, paziente=paziente, giorni_nomi=servizi.GIORNI,
                           attesa=intero(request.args.get('attesa')) or None,
                           mesi=servizi.MESI, sezione='disponibilita')


# ============================================================ statistiche
def periodo_statistiche():
    oggi = date.today()
    predefinito_dal = oggi.replace(day=1)
    dal = data_da(request.args.get('dal'), predefinito_dal) if request.args.get('dal') else predefinito_dal
    al = data_da(request.args.get('al'), oggi) if request.args.get('al') else \
        (date(oggi.year + (oggi.month == 12), oggi.month % 12 + 1, 1) - timedelta(days=1))
    if al < dal:
        dal, al = al, dal
    if (al - dal).days > 3 * 366:
        al = dal + timedelta(days=3 * 366)       # oltre tre anni la pagina diventerebbe lenta
    return dal, al


@bp.route('/statistiche')
def statistiche():
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    dal, al = periodo_statistiche()
    oggi = date.today()
    inizio_mese = oggi.replace(day=1)
    mese_scorso_fine = inizio_mese - timedelta(days=1)
    scorciatoie = [
        ('Questo mese', inizio_mese, (date(oggi.year + (oggi.month == 12), oggi.month % 12 + 1, 1) - timedelta(days=1))),
        ('Mese scorso', mese_scorso_fine.replace(day=1), mese_scorso_fine),
        ('Ultimi 3 mesi', (inizio_mese - timedelta(days=62)).replace(day=1), oggi),
        ('Anno in corso', date(oggi.year, 1, 1), date(oggi.year, 12, 31)),
    ]
    dati = servizi.statistiche(s, st.id, dal, al)
    import dovesifa
    return render_template('statistiche.html', dati=dati, st=st, sid=st.id, strutture=strutture,
                           dal=dal, al=al, scorciatoie=scorciatoie, giorni_nomi=servizi.GIORNI,
                           indirizzati=dovesifa.conteggi_periodo(s, dal, al, st.id), sezione='statistiche')


@bp.route('/statistiche/excel')
def statistiche_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        abort(404)
    dal, al = periodo_statistiche()
    d = servizi.statistiche(s, st.id, dal, al)
    wb = Workbook()
    grassetto, fondo = Font(bold=True), PatternFill('solid', fgColor='FF00B0F0')

    def foglio(titolo, intestazioni, righe, primo=False):
        ws = wb.active if primo else wb.create_sheet()
        ws.title = titolo
        ws.append(intestazioni)
        for c in ws[1]:
            c.font, c.fill = grassetto, fondo
        for r in righe:
            ws.append(r)
        for i, _ in enumerate(intestazioni, start=1):
            ws.column_dimensions[get_column_letter(i)].width = 22
        return ws

    ore = lambda m: round(m / 60.0, 2)
    foglio('Riepilogo', ['Voce', 'Valore'], [
        ['Struttura', st.nome], ['Dal', dal], ['Al', al],
        ['Appuntamenti', d['appuntamenti']], ['Disdetti', d['disdetti']],
        ['Non presentati', d['non_presentati']],
        ['Ore di turno', ore(d['capacita'])], ['Ore prenotate', ore(d['prenotati'])],
        ['Importi indicati (EUR)', d['importo_cent'] / 100.0], ['Incassati (EUR)', d['incassato_cent'] / 100.0],
        ['Pazienti nuovi', d['pazienti_nuovi']],
    ], primo=True)
    foglio('Stanze', ['Stanza', 'Ore di turno', 'Ore prenotate', 'Saturazione %', 'Appuntamenti'],
           [[x['risorsa'].nome, ore(x['capacita']), ore(x['prenotati']),
             round(x['saturazione'], 1) if x['saturazione'] is not None else None, x['appuntamenti']]
            for x in d['per_stanza']])
    foglio('Medici', ['Medico', 'Appuntamenti', 'Ore prenotate', 'Ore di turno', 'Disdetti',
                      'Non presentati', 'Importi (EUR)'],
           [[m['operatore'].etichetta, m['appuntamenti'], ore(m['minuti']), ore(m['turno_minuti']),
             m['disdetti'], m['assenti'], m['importo_cent'] / 100.0] for m in d['per_medico']])
    foglio('Prestazioni', ['Prestazione', 'Appuntamenti', 'Ore', 'Importi (EUR)'],
           [[p['nome'], p['appuntamenti'], ore(p['minuti']), p['importo_cent'] / 100.0]
            for p in d['per_prestazione']])
    foglio('Giorni', ['Giorno', 'Appuntamenti'],
           [[servizi.GIORNI[i], n] for i, n in enumerate(d['per_giorno_settimana'])])
    foglio('Provenienza', ['Come ci hanno conosciuto', 'Pazienti nuovi'],
           [list(x) for x in d['per_provenienza']] + [[]] + [['Inviati da', '']] + [list(x) for x in d['inviati']])
    import dovesifa
    indirizzati = dovesifa.conteggi_periodo(s, dal, al, st.id)
    if indirizzati:
        foglio('Indirizzati', ['Struttura del gruppo', 'Pazienti indirizzati'], [list(x) for x in indirizzati])
    nome = 'statistiche-%s-%s.xlsx' % (dal.isoformat(), al.isoformat())
    return scarica_excel(wb, nome)


# ============================================================ impostazioni
def cartella_backup():
    """La cartella dei backup scelta nelle impostazioni, letta con una
    sessione propria: la chiama anche il thread dei backup."""
    fabbrica = _sessionmaker() if _sessionmaker else None
    if fabbrica is None:
        return None
    s = fabbrica()
    try:
        return leggi_impostazione(s, 'backup_cartella', '') or None
    finally:
        s.close()


def percorso_database():
    fabbrica = _sessionmaker() if _sessionmaker else None
    motore = getattr(fabbrica, 'motore', None) if fabbrica else None
    if motore is None or motore.dialect.name != 'sqlite' or not motore.url.database:
        return None, None
    return os.path.abspath(motore.url.database), motore


def cartella_effettiva(s, percorso_db):
    scelta = leggi_impostazione(s, 'backup_cartella', '')
    return scelta or (backup.cartella_predefinita(percorso_db) if percorso_db else '')


def copie_di(s, percorso_db):
    """Le copie da mostrare e da poter rimettere: quelle della cartella scelta e
    (1.11) anche quelle della cartella accanto al database, dove vanno le copie
    «prima della versione», quelle fatte quando la cartella scelta non si
    raggiungeva e quelle di prima di una cartella nuova. Prima si vedevano
    solo le altre, e quelle restavano nascoste proprio quando servivano."""
    if not percorso_db:
        return []
    cartelle = [cartella_effettiva(s, percorso_db)]
    predefinita = backup.cartella_predefinita(percorso_db)
    if os.path.normcase(os.path.abspath(predefinita)) != os.path.normcase(os.path.abspath(cartelle[0])):
        cartelle.append(predefinita)
    visti, uscita = set(), []
    for i, c in enumerate(cartelle):
        for x in backup.elenco(c):
            if x['nome'] not in visti:
                visti.add(x['nome'])
                uscita.append(dict(x, altrove=i > 0))
    return sorted(uscita, key=lambda x: x['quando'], reverse=True)


@bp.route('/impostazioni', methods=['GET', 'POST'])
def impostazioni():
    s = ses()
    percorso_db, motore = percorso_database()
    if request.method == 'POST':
        azione = request.form.get('azione')
        if azione == 'cartella':
            cartella = (request.form.get('cartella') or '').strip()
            if cartella:
                if len(cartella) > 300 or '\x00' in cartella:
                    flash('Cartella non valida.', 'errore')
                    return redirect(url_for('viste.impostazioni'))
                try:
                    os.makedirs(cartella, exist_ok=True)
                    prova = os.path.join(cartella, '.prova-scrittura')
                    with open(prova, 'w') as f:
                        f.write('ok')
                    os.remove(prova)
                except OSError as e:
                    flash('Nella cartella non si riesce a scrivere: %s' % e, 'errore')
                    return redirect(url_for('viste.impostazioni'))
            with _lucchetto:
                scrivi_impostazione(s, 'backup_cartella', cartella)
                s.commit()
            # anche fuori dal database: se un giorno non si legge, le copie si trovano lo stesso
            if percorso_db:
                autoripara.ricorda(os.path.dirname(percorso_db), cartella_backup=cartella)
            flash('Cartella dei backup salvata.' if cartella else
                  'Si torna alla cartella predefinita, accanto al database.', 'ok')
        elif azione == 'backup_ora':
            if not percorso_db:
                flash('Il database non è un file: backup non disponibile.', 'errore')
            else:
                try:
                    finale = backup.esegui(percorso_db, cartella_effettiva(s, percorso_db))
                    flash('Backup fatto: %s' % os.path.basename(finale), 'ok')
                except Exception as e:
                    flash('Backup non riuscito: %s' % e, 'errore')
        elif azione == 'testo':
            testo = ' '.join((request.form.get('testo') or '').split())
            oggetto = ' '.join((request.form.get('oggetto') or '').split())
            if len(testo) > 1000 or len(oggetto) > 200:
                flash('Testo troppo lungo: al massimo 1000 caratteri, 200 per l\'oggetto.', 'errore')
                return redirect(url_for('viste.impostazioni'))
            with _lucchetto:
                scrivi_impostazione(s, 'testo_promemoria', '' if testo == TESTO_PREDEFINITO else testo)
                scrivi_impostazione(s, 'oggetto_promemoria', '' if oggetto == OGGETTO_PREDEFINITO else oggetto)
                s.commit()
            flash('Testo dei messaggi salvato.', 'ok')
        elif azione == 'stampa':
            note = {c for c, _ in COLONNE_STAMPA}
            scelte = [c for c in request.form.getlist('colonne') if c in note]
            dati = {'colonne': [c for c, _ in COLONNE_STAMPA if c in scelte],
                    'orientamento': request.form.get('orientamento') if request.form.get('orientamento') in (
                        'orizzontale', 'verticale') else 'orizzontale',
                    'ordine': request.form.get('ordine') if request.form.get('ordine') in ('stanza', 'ora') else 'stanza'}
            with _lucchetto:
                scrivi_impostazione(s, 'stampa_giorno', json.dumps(dati))
                s.commit()
            flash('Foglio del giorno: impostazioni salvate.', 'ok')
            return redirect(url_for('viste.impostazioni') + '#stampa')
        elif azione == 'testo_predefinito':
            with _lucchetto:
                scrivi_impostazione(s, 'testo_promemoria', '')
                scrivi_impostazione(s, 'oggetto_promemoria', '')
                s.commit()
            flash('Testo dei messaggi riportato a quello predefinito.', 'ok')
        return redirect(url_for('viste.impostazioni'))
    cartella = cartella_effettiva(s, percorso_db)
    copie = copie_di(s, percorso_db) if cartella else []
    modello, oggetto = modelli_messaggio(s)
    esempio = s.scalars(select(Appuntamento).where(Appuntamento.paziente_id != None)
                        .order_by(Appuntamento.inizio.desc())).first()
    return render_template(
        'impostazioni.html', cartella=cartella,
        scelta=leggi_impostazione(s, 'backup_cartella', ''),
        predefinita=backup.cartella_predefinita(percorso_db) if percorso_db else '',
        copie=copie, stato=backup.stato, percorso_db=percorso_db, modello=modello,
        oggetto=oggetto, esempio=testo_messaggio(esempio, modello) if esempio else '',
        segnaposto=SEGNAPOSTO, colonne_stampa=COLONNE_STAMPA, stampa=impostazioni_stampa(s),
        voci_checklist=sala.voci_checklist(s),
        sid=None, sezione='impostazioni')


@bp.route('/impostazioni/backup/<nome>')
def scarica_backup(nome):
    s = ses()
    percorso_db, _ = percorso_database()
    if not backup.NOME.match(nome or '') or not percorso_db:
        abort(404)
    copia = next((c for c in copie_di(s, percorso_db) if c['nome'] == nome), None)
    if copia is None:
        abort(404)
    return send_file(copia['percorso'], as_attachment=True, download_name=nome)


@bp.route('/impostazioni/ripristina', methods=['POST'])
def ripristina():
    """Rimette una copia al posto del database attuale. Il database di prima
    resta fra i backup ("prima del ripristino"): anche questo si annulla."""
    s = ses()
    percorso_db, motore = percorso_database()
    nome = request.form.get('nome') or ''
    if not percorso_db or not backup.NOME.match(nome):
        flash('Copia non valida.', 'errore')
        return redirect(url_for('viste.impostazioni'))
    if request.form.get('conferma') != '1':
        flash('Per ripristinare va spuntata la conferma.', 'errore')
        return redirect(url_for('viste.impostazioni'))
    cartella = cartella_effettiva(s, percorso_db)
    copia = next((c for c in copie_di(s, percorso_db) if c['nome'] == nome), None)
    if copia is None:
        flash('Copia non trovata.', 'errore')
        return redirect(url_for('viste.impostazioni'))
    s.close()
    with _lucchetto:
        try:
            sicurezza = backup.ripristina(percorso_db, copia['percorso'], motore, cartella)
            _, aggiunte, _ = aggiorna_database(motore)
            fabbrica = _sessionmaker()
            nuova = fabbrica()
            try:
                servizi.dopo_aggiornamento(nuova, aggiunte)
            finally:
                nuova.close()
        except Exception as e:
            flash('Ripristino non riuscito: %s' % e, 'errore')
            return redirect(url_for('viste.impostazioni'))
    flash('Ripristinata la copia del %s. Il database di prima è stato salvato come %s.' % (
        copia['quando'].strftime('%d/%m/%Y %H:%M'), os.path.basename(sicurezza)), 'ok')
    return redirect(url_for('viste.impostazioni'))
