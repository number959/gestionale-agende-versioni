# -*- coding: utf-8 -*-
"""Il riepilogo live di agende e ambulatori (dalla 1.12): una pagina che si
aggiorna da sola ogni minuto e dice, adesso, come va la giornata e com'e'
ogni stanza: chi e' di turno, se c'e' una visita in corso, fino a quando e'
libera, quante visite ha fatto e quante ne restano; sotto, le mezze giornate
libere dei prossimi giorni (dalla matrice degli ambulatori) e le visite ora
per ora. Con ?schermo=1 si apre a caratteri grandi, senza menu, per il
secondo monitor o lo schermo della direzione.

Dalla 1.12.2 la pagina e' piu' chiara: gli appuntamenti di oggi sono divisi in
quattro gruppi che sommano al totale (fatti, in corso, da segnare = orario
passato senza l'arrivo segnato, da fare), una frase in cima dice com'e' la
giornata, le stanze sono su una linea del tempo con i turni dei medici e le
visite colorate per stato, e le mezze giornate libere sono raggruppate per
giorno.

Gli stessi numeri escono in JSON (/riepilogo-live.json): sono solo conteggi,
orari e nomi di stanze e medici, mai un paziente. E' il formato con cui un
giorno il programma potra' alimentare il cruscotto su internet (vedi le
proposte in PASSAGGIO_DI_CONSEGNE.md): la prova controlla che nessun nome,
telefono o email dei pazienti finisca nel JSON."""
from datetime import datetime, time, timedelta

from flask import Blueprint, render_template, request

import ambulatori
import calendario
import cruscotto
import servizi
from comune import json_sicuro, struttura_scelta
from modelli import STATI_ATTIVI

bp = Blueprint('live', __name__)
_fornitore = None

GIORNI_AVANTI = 7           # le mezze giornate libere da qui a una settimana
MASSIMO_LIBERE = 12         # quante elencarne nella pagina


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore
    _fornitore = fornitore_sessione
    app.register_blueprint(bp)


def ses():
    return _fornitore()


def _ora(t):
    return t.strftime('%H:%M') if t else None


def _min(t):
    """Minuti dalla mezzanotte di un orario (time o datetime)."""
    return t.hour * 60 + t.minute


def _uno_o_tanti(n, uno, tanti):
    return '%d %s' % (n, uno if n == 1 else tanti)


def _senza_doppi(nomi):
    """I nomi nell'ordine, una volta sola (due turni dello stesso medico nella stessa stanza)."""
    visti = []
    for n in nomi:
        if n not in visti:
            visti.append(n)
    return visti


def _unisci(intervalli):
    """[(da, a)] in minuti, uniti dove si toccano o si sovrappongono."""
    uniti = []
    for da, a in sorted(intervalli):
        if uniti and da <= uniti[-1][1]:
            uniti[-1][1] = max(uniti[-1][1], a)
        else:
            uniti.append([da, a])
    return [tuple(x) for x in uniti]


def _hhmm(minuti):
    return '%02d:%02d' % divmod(minuti, 60)


def stato_visita(a, adesso):
    """Il gruppo di un appuntamento attivo, adesso: i quattro gruppi sommano al totale."""
    if a.inizio > adesso:
        return 'da-fare'
    if a.fine > adesso:
        return 'in-corso'
    return 'fatto' if a.stato == 'ARRIVATO' else 'da-segnare'


NOMI_STATO = {'fatto': 'fatto', 'in-corso': 'in corso', 'da-segnare': 'orario passato, arrivo non segnato',
              'da-fare': 'da fare'}


def riepilogo(s, st, adesso=None):
    """Tutti i numeri del riepilogo, gia' pronti per il JSON (date e orari in
    testo). Nessun dato di pazienti: solo conteggi, orari, stanze e medici."""
    adesso = adesso or datetime.now()
    oggi = adesso.date()
    stanze_mostrate = ambulatori.stanze_della(st)
    # i conti sono quelli delle stanze della pagina (non le sale operatorie): cosi' le stanze sommano al totale
    ids_mostrate = {r.id for r in stanze_mostrate}
    del_giorno = [a for a in servizi.elenco_giorno(s, oggi, st.id) if a.risorsa_id in ids_mostrate]
    attivi = [a for a in del_giorno if a.stato in STATI_ATTIVI]
    regole = servizi.Regole(s, oggi, oggi)
    info = regole.giorno(oggi, st)
    chiusa = info['chiusura'] or (info['festivo'] if info['chiude_festivo'] else None)
    ora_adesso = adesso.time()

    stanze = []
    # la linea del tempo: dall'apertura alla chiusura, allargata se un turno o una visita escono
    inizio_asse, fine_asse = _min(st.apertura), _min(st.chiusura)
    for r in stanze_mostrate:
        for t in regole.turni_effettivi(oggi, st, r.id, info):
            inizio_asse, fine_asse = min(inizio_asse, _min(t.ora_inizio)), max(fine_asse, _min(t.ora_fine))
    for a in attivi:
        inizio_asse = min(inizio_asse, _min(a.inizio))
        fine_asse = max(fine_asse, _min(a.fine) if a.fine.date() == oggi else 24 * 60)
    inizio_asse, fine_asse = inizio_asse // 60 * 60, min(24 * 60, -(-fine_asse // 60) * 60)
    durata_asse = max(60, fine_asse - inizio_asse)

    def posizione(da, a):
        """(sinistra, larghezza) in percento sulla linea del tempo, dentro i bordi."""
        da, a = max(da, inizio_asse), min(a, fine_asse)
        return round(100.0 * (da - inizio_asse) / durata_asse, 2), round(100.0 * max(0, a - da) / durata_asse, 2)

    for r in stanze_mostrate:
        turni = sorted(regole.turni_effettivi(oggi, st, r.id, info), key=lambda t: t.ora_inizio)
        di_turno = [t for t in turni if t.ora_inizio <= ora_adesso < t.ora_fine]
        prossimo_turno = next((t for t in turni if t.ora_inizio > ora_adesso), None)
        qui = sorted((a for a in attivi if a.risorsa_id == r.id), key=lambda a: a.inizio)
        in_corso = [a for a in qui if a.inizio <= adesso < a.fine]
        prossimo = next((a for a in qui if a.inizio > adesso), None)
        motivo = None
        if chiusa and not turni and not qui:
            stato, fino = 'chiusa', None
        elif in_corso:
            stato, fino = 'occupata', max(a.fine for a in in_corso).time()
        elif di_turno:
            stato = 'libera'
            # libera fino al prossimo appuntamento o alla fine del turno
            adesso_m = _min(ora_adesso)
            pezzo = next((x for x in _unisci((_min(t.ora_inizio), _min(t.ora_fine)) for t in turni)
                          if x[0] <= adesso_m < x[1]), None)
            fine_turno = (time(*divmod(pezzo[1], 60)) if pezzo and pezzo[1] < 24 * 60
                          else max(t.ora_fine for t in di_turno))
            if prossimo and prossimo.inizio.time() < fine_turno:
                fino, motivo = prossimo.inizio.time(), 'appuntamento'
            else:
                fino, motivo = fine_turno, 'fine turno'
        elif prossimo_turno:
            stato, fino, motivo = 'senza turno', prossimo_turno.ora_inizio, 'inizio turno'
        else:
            stato, fino = 'finita' if turni else 'senza turno', None
        medici_ora = _senza_doppi(t.operatore.etichetta for t in di_turno)
        prossimo_medico = prossimo_turno.operatore.etichetta if prossimo_turno and not di_turno else None
        # la frase della stanza, in parole semplici
        if stato == 'chiusa':
            frase = 'Chiusa oggi'
        elif stato == 'occupata':
            frase = 'Visita in corso fino alle %s' % _ora(fino)
        elif stato == 'libera' and motivo == 'appuntamento':
            frase = 'Libera, prossimo paziente alle %s' % _ora(fino)
        elif stato == 'libera':
            frase = 'Libera fino a fine turno (%s)' % _ora(fino)
        elif stato == 'senza turno' and fino:
            frase = 'Nessun medico fino alle %s%s' % (_ora(fino), ', poi %s' % prossimo_medico if prossimo_medico else '')
        elif stato == 'finita':
            frase = 'Turni finiti per oggi'
        else:
            frase = 'Nessun medico oggi'
        # la linea del tempo della stanza: i turni (uniti per medico) e le visite, solo orari e stato
        per_medico = {}
        for t in turni:
            per_medico.setdefault(t.operatore.etichetta, []).append((_min(t.ora_inizio), _min(t.ora_fine)))
        linea_turni = []
        for nome, pezzi in per_medico.items():
            for da, a in _unisci(pezzi):
                sx, larg = posizione(da, a)
                linea_turni.append({'medico': nome, 'da': _hhmm(da), 'a': _hhmm(a), 'sx': sx, 'larg': larg})
        linea_turni.sort(key=lambda x: x['sx'])
        linea_visite = []
        for a in qui:
            fine_a = _min(a.fine) if a.fine.date() == oggi else 24 * 60
            sx, larg = posizione(_min(a.inizio), fine_a)
            linea_visite.append({'da': _ora(a.inizio), 'a': _ora(a.fine), 'stato': stato_visita(a, adesso), 'sx': sx,
                                 'larg': larg})
        gruppi = [stato_visita(a, adesso) for a in qui]
        stanze.append({
            'stanza': r.nome, 'stato': stato, 'fino': _ora(fino), 'motivo': motivo, 'frase': frase,
            'medico': ', '.join(medici_ora) or None, 'prossimo_medico': prossimo_medico,
            'turni': _senza_doppi('%s %s–%s' % (t.operatore.etichetta, _ora(t.ora_inizio), _ora(t.ora_fine)) for t in turni),
            'totale': len(qui), 'arrivati': sum(1 for a in qui if a.stato == 'ARRIVATO'),
            'fatte': gruppi.count('fatto'), 'in_corso': len(in_corso), 'restanti': gruppi.count('da-fare'),
            'da_segnare': gruppi.count('da-segnare'),
            'prossima': _ora(prossimo.inizio.time()) if prossimo else None,
            'linea': {'turni': linea_turni, 'visite': linea_visite},
        })

    in_ritardo = [a for a in attivi if a.stato != 'ARRIVATO' and adesso - cruscotto.IN_RITARDO <= a.inizio <= adesso]
    tra_poco = [a for a in attivi if a.stato != 'ARRIVATO' and adesso < a.inizio <= adesso + cruscotto.TRA_POCO]
    per_ora = []
    prima_ora = min([st.apertura.hour] + [a.inizio.hour for a in attivi])
    ultima_ora = max([st.chiusura.hour + (1 if st.chiusura.minute else 0)] + [a.inizio.hour + 1 for a in attivi])
    for h in range(prima_ora, ultima_ora):
        nell_ora = [a for a in attivi if a.inizio.hour == h]
        per_ora.append({'ora': '%02d:00' % h, 'totale': len(nell_ora),
                        'arrivati': sum(1 for a in nell_ora if a.stato == 'ARRIVATO'),
                        'quando': 'passata' if h < adesso.hour else ('adesso' if h == adesso.hour else 'dopo')})
    prossimo_giorno = servizi.prossimo_giorno_con_appuntamenti(s, oggi, st.id)
    da_confermare = (len(servizi.elenco_giorno(s, prossimo_giorno, st.id, ('PRENOTATO',)))
                     if prossimo_giorno and prossimo_giorno > oggi else 0)

    # le mezze giornate libere da qui a una settimana, dalla matrice degli ambulatori; per la tabella
    # anche le altre: occupate (c'e' un medico), passate (stamattina) e chiuse
    libere = []
    celle_tab = {}
    stanze_tab = []
    lunedi = calendario.lunedi_di(oggi)
    for settimana in (lunedi, lunedi + timedelta(days=7)):
        vista = ambulatori.matrice(s, settimana, st)
        for riga in vista['righe']:
            if riga['risorsa'].nome not in stanze_tab:
                stanze_tab.append(riga['risorsa'].nome)
            for c in riga['celle']:
                if c['data'] < oggi or c['data'] > oggi + timedelta(days=GIORNI_AVANTI):
                    continue
                passata = c['data'] == oggi and c['meta']['a'] <= ora_adesso
                celle_tab.setdefault((c['data'], riga['risorsa'].nome), {})[c['meta']['nome']] = (
                    'passata' if passata else 'chiusa' if c['chiuso'] else 'libera' if c['tutta_libera'] else 'occupata')
                if passata:
                    continue
                if c['tutta_libera']:
                    libere.append({'data': c['data'].isoformat(), 'giorno': servizi.GIORNI[c['data'].weekday()],
                                   'stanza': riga['risorsa'].nome, 'meta': c['meta']['nome'],
                                   'orario': '%s–%s' % (_ora(c['meta']['da']), _ora(c['meta']['a']))})
    libere.sort(key=lambda x: (x['data'], x['stanza'], x['orario']))
    # raggruppate per giorno: una riga per giorno, una voce per stanza («tutto il giorno» se libere tutte e due)
    libere_giorni = []
    for l in libere:
        if not libere_giorni or libere_giorni[-1]['data'] != l['data']:
            g = datetime.strptime(l['data'], '%Y-%m-%d').date()
            libere_giorni.append({'data': l['data'], 'giorno': l['giorno'],
                                  'etichetta': '%s %d/%d' % (l['giorno'], g.day, g.month), 'oggi': g == oggi,
                                  'stanze': []})
        voci = libere_giorni[-1]['stanze']
        if voci and voci[-1]['stanza'] == l['stanza']:
            voci[-1]['quando'] = 'tutto il giorno'
            voci[-1]['orario'] = voci[-1]['orario'].split('–')[0] + '–' + l['orario'].split('–')[1]
        else:
            voci.append({'stanza': l['stanza'], 'quando': l['meta'], 'orario': l['orario']})

    nomi_meta = [m['nome'] for m in ambulatori.mezze_giornate(st)]
    tabella_giorni = []
    for g in sorted({d for d, _ in celle_tab}):
        celle = [[celle_tab.get((g, nome), {}).get(m, 'chiusa') for m in nomi_meta] for nome in stanze_tab]
        if all(x == 'chiusa' for riga_c in celle for x in riga_c):
            continue
        tabella_giorni.append({'data': g.isoformat(), 'etichetta': '%s %d/%d' % (servizi.GIORNI[g.weekday()], g.day, g.month),
                               'oggi': g == oggi, 'celle': celle,
                               'libere': sum(1 for riga_c in celle for x in riga_c if x == 'libera')})
    libere_tabella = {'meta': nomi_meta, 'stanze': stanze_tab, 'giorni': tabella_giorni}

    oggi_conti = {
        'totale': len(attivi), 'arrivati': sum(1 for a in attivi if a.stato == 'ARRIVATO'),
        'in_struttura': sum(1 for a in attivi if a.stato == 'ARRIVATO' and a.fine > adesso),
        'fatte': sum(1 for a in attivi if stato_visita(a, adesso) == 'fatto'),
        'in_corso': sum(1 for a in attivi if a.inizio <= adesso < a.fine),
        'da_segnare': sum(1 for a in attivi if stato_visita(a, adesso) == 'da-segnare'),
        'restanti': sum(1 for a in attivi if a.inizio > adesso),
        'in_ritardo': len(in_ritardo), 'tra_poco': len(tra_poco),
        'disdetti': sum(1 for a in del_giorno if a.stato == 'DISDETTO'),
        'non_presentati': sum(1 for a in del_giorno if a.stato == 'NON_PRESENTATO'),
        'da_confermare': da_confermare,
        'prossimo_giorno': prossimo_giorno.isoformat() if prossimo_giorno and prossimo_giorno > oggi else None,
        'prossimo_giorno_etichetta': ('%s %d/%d' % (servizi.GIORNI[prossimo_giorno.weekday()], prossimo_giorno.day,
                                                    prossimo_giorno.month)
                                      if prossimo_giorno and prossimo_giorno > oggi else None),
    }
    # la frase in cima, in parole semplici
    con_medico = sum(1 for x in stanze if x['medico'])
    turni_oggi = any(x['turni'] for x in stanze)
    motivo_chiusa = chiusa if chiusa and chiusa.strip().lower() not in ('', 'chiusura') else None
    if chiusa and not attivi and not turni_oggi:
        riassunto = 'Oggi la struttura è chiusa%s.' % (': %s' % motivo_chiusa if motivo_chiusa else '')
    elif not attivi and not turni_oggi:
        riassunto = 'Oggi non ci sono né appuntamenti né turni nelle stanze.'
    else:
        pezzi = ['%s in corso' % _uno_o_tanti(oggi_conti['in_corso'], 'visita', 'visite'),
                 '%d stanz%s su %d con un medico adesso' % (con_medico, 'a' if con_medico == 1 else 'e', len(stanze))]
        riassunto = 'Alle %s: %s.' % (adesso.strftime('%H:%M'), ', '.join(pezzi))
        if chiusa:
            riassunto = 'Oggi la struttura è chiusa%s, ma ci sono turni o appuntamenti. ' % (
                ' (%s)' % motivo_chiusa if motivo_chiusa else '') + riassunto
        if oggi_conti['da_segnare']:
            riassunto += ' %s con l\'orario passato %s segnat%s arrivat%s: da controllare in Oggi.' % (
                _uno_o_tanti(oggi_conti['da_segnare'], 'paziente', 'pazienti'),
                'non è' if oggi_conti['da_segnare'] == 1 else 'non sono',
                'o' if oggi_conti['da_segnare'] == 1 else 'i', 'o' if oggi_conti['da_segnare'] == 1 else 'i')
        dopo = sorted((a for a in attivi if a.inizio > adesso), key=lambda a: a.inizio)
        if dopo:
            stanza = next((r.nome for r in stanze_mostrate if r.id == dopo[0].risorsa_id), None)
            riassunto += ' Prossimo appuntamento alle %s%s.' % (_ora(dopo[0].inizio.time()),
                                                                 ' in %s' % stanza if stanza else '')
        elif attivi:
            riassunto += ' Nessun altro appuntamento oggi.'
        else:
            riassunto += ' Oggi non ci sono appuntamenti nelle stanze.'
    adesso_min = _min(adesso)
    posto_adesso = (round(100.0 * (adesso_min - inizio_asse) / durata_asse, 2)
                    if inizio_asse <= adesso_min <= fine_asse else None)
    # le tacche vicine all'etichetta rossa di adesso non si scrivono (si sovrapporrebbero); sul telefono
    # restano solo quelle pari
    ore_asse = [{'ora': '%02d' % (m // 60), 'sx': round(100.0 * (m - inizio_asse) / durata_asse, 2),
                 'vicina': posto_adesso is not None and abs(100.0 * (m - inizio_asse) / durata_asse - posto_adesso) < 4,
                 'dispari': (m - inizio_asse) // 60 % 2 == 1}
                for m in range(inizio_asse, fine_asse + 1, 60)]
    asse = {'da': _hhmm(inizio_asse), 'a': _hhmm(fine_asse) if fine_asse < 24 * 60 else '24:00', 'ore': ore_asse,
            'adesso': posto_adesso,
            'bordo': ('sinistra' if posto_adesso is not None and posto_adesso < 5 else
                      'destra' if posto_adesso is not None and posto_adesso > 95 else '')}

    return {
        'aggiornato': adesso.strftime('%H:%M'), 'data': oggi.isoformat(), 'giorno': servizi.etichetta_giorno(oggi),
        'struttura': st.nome, 'chiusa': chiusa, 'riassunto': riassunto,
        'oggi': oggi_conti,
        'stanze': stanze, 'asse': asse,
        'stanze_occupate': sum(1 for x in stanze if x['stato'] == 'occupata'),
        'stanze_libere': sum(1 for x in stanze if x['stato'] == 'libera'),
        'stanze_con_medico': con_medico,
        'per_ora': per_ora,
        'libere': libere[:MASSIMO_LIBERE], 'n_libere': len(libere), 'libere_giorni': libere_giorni,
        'libere_tabella': libere_tabella,
    }


@bp.route('/riepilogo-live')
def pagina():
    s = ses()
    st, strutture = struttura_scelta(s)
    if st is None:
        return render_template('da_configurare.html'), 200
    schermo = request.args.get('schermo') == '1'
    r = riepilogo(s, st)
    return render_template('riepilogo_live.html', r=r, st=st, sid=st.id, strutture=strutture, schermo=schermo,
                           nomi_stato=NOMI_STATO,
                           sezione='live', data_menu=r['data'], titolo='Riepilogo live · %s' % r['giorno'])


@bp.route('/riepilogo-live.json')
def dati():
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return json_sicuro({'errore': 'nessuna struttura'})
    return json_sicuro(riepilogo(s, st))
