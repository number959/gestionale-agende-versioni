# -*- coding: utf-8 -*-
"""Il riepilogo live di agende e ambulatori (dalla 1.12): una pagina che si
aggiorna da sola ogni minuto e dice, adesso, come va la giornata e com'e'
ogni stanza: chi e' di turno, se c'e' una visita in corso, fino a quando e'
libera, quante visite ha fatto e quante ne restano; sotto, le mezze giornate
libere dei prossimi giorni (dalla matrice degli ambulatori) e le visite ora
per ora. Con ?schermo=1 si apre a caratteri grandi, senza menu, per il
secondo monitor o lo schermo della direzione.

Gli stessi numeri escono in JSON (/riepilogo-live.json): sono solo conteggi,
orari e nomi di stanze e medici, mai un paziente. E' il formato con cui un
giorno il programma potra' alimentare il cruscotto su internet (vedi le
proposte in PASSAGGIO_DI_CONSEGNE.md): la prova controlla che nessun nome,
telefono o email dei pazienti finisca nel JSON."""
from datetime import datetime, timedelta

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


def riepilogo(s, st, adesso=None):
    """Tutti i numeri del riepilogo, gia' pronti per il JSON (date e orari in
    testo). Nessun dato di pazienti: solo conteggi, orari, stanze e medici."""
    adesso = adesso or datetime.now()
    oggi = adesso.date()
    del_giorno = servizi.elenco_giorno(s, oggi, st.id)
    attivi = [a for a in del_giorno if a.stato in STATI_ATTIVI]
    regole = servizi.Regole(s, oggi, oggi)
    info = regole.giorno(oggi, st)
    chiusa = info['chiusura'] or (info['festivo'] if info['chiude_festivo'] else None)
    ora_adesso = adesso.time()

    stanze = []
    for r in ambulatori.stanze_della(st):
        turni = sorted(regole.turni_effettivi(oggi, st, r.id, info), key=lambda t: t.ora_inizio)
        di_turno = [t for t in turni if t.ora_inizio <= ora_adesso < t.ora_fine]
        prossimo_turno = next((t for t in turni if t.ora_inizio > ora_adesso), None)
        qui = sorted((a for a in attivi if a.risorsa_id == r.id), key=lambda a: a.inizio)
        in_corso = [a for a in qui if a.inizio <= adesso < a.fine]
        prossimo = next((a for a in qui if a.inizio > adesso), None)
        if chiusa:
            stato, fino = 'chiusa', None
        elif in_corso:
            stato, fino = 'occupata', max(a.fine for a in in_corso).time()
        elif di_turno:
            stato = 'libera'
            # libera fino al prossimo appuntamento o alla fine del turno
            fino = min(([prossimo.inizio.time()] if prossimo else []) + [t.ora_fine for t in di_turno])
        elif prossimo_turno:
            stato, fino = 'senza turno', prossimo_turno.ora_inizio
        else:
            stato, fino = 'finita' if turni else 'senza turno', None
        stanze.append({
            'stanza': r.nome, 'stato': stato, 'fino': _ora(fino),
            'medico': ', '.join(t.operatore.etichetta for t in di_turno) or None,
            'turni': ['%s %s–%s' % (t.operatore.etichetta, _ora(t.ora_inizio), _ora(t.ora_fine)) for t in turni],
            'totale': len(qui), 'arrivati': sum(1 for a in qui if a.stato == 'ARRIVATO'),
            'fatte': sum(1 for a in qui if a.stato == 'ARRIVATO' and a.fine <= adesso),
            'in_corso': len(in_corso), 'restanti': sum(1 for a in qui if a.inizio > adesso),
            'prossima': _ora(prossimo.inizio.time()) if prossimo else None,
        })

    in_ritardo = [a for a in attivi if a.stato != 'ARRIVATO' and adesso - cruscotto.IN_RITARDO <= a.inizio <= adesso]
    tra_poco = [a for a in attivi if a.stato != 'ARRIVATO' and adesso < a.inizio <= adesso + cruscotto.TRA_POCO]
    per_ora = []
    for h in range(st.apertura.hour, st.chiusura.hour + (1 if st.chiusura.minute else 0)):
        nell_ora = [a for a in attivi if a.inizio.hour == h]
        per_ora.append({'ora': '%02d:00' % h, 'totale': len(nell_ora),
                        'arrivati': sum(1 for a in nell_ora if a.stato == 'ARRIVATO')})
    prossimo_giorno = servizi.prossimo_giorno_con_appuntamenti(s, oggi, st.id)
    da_confermare = (len(servizi.elenco_giorno(s, prossimo_giorno, st.id, ('PRENOTATO',)))
                     if prossimo_giorno and prossimo_giorno > oggi else 0)

    # le mezze giornate libere da qui a una settimana, dalla matrice degli ambulatori
    libere = []
    lunedi = calendario.lunedi_di(oggi)
    for settimana in (lunedi, lunedi + timedelta(days=7)):
        vista = ambulatori.matrice(s, settimana, st)
        for riga in vista['righe']:
            for c in riga['celle']:
                if c['data'] < oggi or c['data'] > oggi + timedelta(days=GIORNI_AVANTI):
                    continue
                if c['data'] == oggi and c['meta']['a'] <= ora_adesso:
                    continue
                if c['tutta_libera']:
                    libere.append({'data': c['data'].isoformat(), 'giorno': servizi.GIORNI[c['data'].weekday()],
                                   'stanza': riga['risorsa'].nome, 'meta': c['meta']['nome'],
                                   'orario': '%s–%s' % (_ora(c['meta']['da']), _ora(c['meta']['a']))})
    libere.sort(key=lambda x: (x['data'], x['stanza'], x['orario']))

    return {
        'aggiornato': adesso.strftime('%H:%M'), 'data': oggi.isoformat(), 'giorno': servizi.etichetta_giorno(oggi),
        'struttura': st.nome, 'chiusa': chiusa,
        'oggi': {
            'totale': len(attivi), 'arrivati': sum(1 for a in attivi if a.stato == 'ARRIVATO'),
            'in_struttura': sum(1 for a in attivi if a.stato == 'ARRIVATO' and a.fine > adesso),
            'fatte': sum(1 for a in attivi if a.stato == 'ARRIVATO' and a.fine <= adesso),
            'in_corso': sum(1 for a in attivi if a.inizio <= adesso < a.fine),
            'restanti': sum(1 for a in attivi if a.inizio > adesso),
            'in_ritardo': len(in_ritardo), 'tra_poco': len(tra_poco),
            'disdetti': sum(1 for a in del_giorno if a.stato == 'DISDETTO'),
            'non_presentati': sum(1 for a in del_giorno if a.stato == 'NON_PRESENTATO'),
            'da_confermare': da_confermare,
            'prossimo_giorno': prossimo_giorno.isoformat() if prossimo_giorno and prossimo_giorno > oggi else None,
        },
        'stanze': stanze,
        'stanze_occupate': sum(1 for x in stanze if x['stato'] == 'occupata'),
        'stanze_libere': sum(1 for x in stanze if x['stato'] == 'libera'),
        'per_ora': per_ora,
        'libere': libere[:MASSIMO_LIBERE], 'n_libere': len(libere),
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
                           sezione='live', data_menu=r['data'], titolo='Riepilogo live · %s' % r['giorno'])


@bp.route('/riepilogo-live.json')
def dati():
    s = ses()
    st, _ = struttura_scelta(s)
    if st is None:
        return json_sicuro({'errore': 'nessuna struttura'})
    return json_sicuro(riepilogo(s, st))
