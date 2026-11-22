# -*- coding: utf-8 -*-
"""Il menu e le linguette in un elenco (tappa 2 della base, 22/11/2026): le voci non si scrivono più a mano nel
modello, le disegna templates/_menu.html da qui.

Per ogni voce:
- endpoint: la funzione della pagina, per url_for (None per la tendina Aiuto, che non porta a una pagina);
- argomenti: cosa porta dalla pagina aperta, come faceva _menu.html: 'struttura' (struttura=sid), 'giorno'
  (iso=data), 'giorno_data' (data=data, le esportazioni) e 'mese' (aaaamm=i primi 7 caratteri della data). La data è
  quella della pagina (data_menu), altrimenti oggi; la struttura è quella della pagina (sid), altrimenti nessuna;
- parola, icona (un nome di Lucide, come in templates/_icone.html), gruppo del menu;
- sezioni: i valori di «sezione» (passati da ogni pagina al modello) che la accendono. Due voci non hanno mai una
  sezione in comune: ogni pagina accende una voce sola (prove_menu.py);
- condizione: la voce c'è solo se è vera, come oggi la Sala con una sala operatoria. È il nome di una funzione dei
  modelli (ci_sono_sale) o una funzione senza argomenti: un modulo potrà guardare lì se è acceso;
- tasto e guida: data-tasto (i tasti rapidi G, D, C, E di gestionale.js) e data-guida (i passi della guida);
- contatore: il numero accanto alla parola (n_da_confermare), con il suo title.
Le linguette stanno con la loro voce (LINGUETTE, per chiave della voce): le pagine della stessa area. «sotto» è la
riga piccola di oggi nelle tendine (nella veste nuova il title della linguetta); «fuori» vuol dire che la linguetta
porta a un'altra voce (l'Elenco del giorno sta nell'Agenda): nella veste nuova lì non si accende. La tendina Aiuto
(AIUTO) resta com'è; NASCOSTI sono i collegamenti che servono solo a un tasto (E, l'Elenco del giorno).

I moduli (dalla 1.14) aggiungono voci e linguette con registra_voce() e registra_linguetta(), senza toccare i modelli.
costruisci() fa le voci per la pagina aperta, con gli indirizzi scritti da url_for; nei modelli è menu_della_pagina().

Fino al passo dopo della tappa 2 il disegno resta quello di oggi, byte per byte (disegno_di_oggi): il menu in alto
con le tendine. Le stesse voci, messe come oggi:
- l'Agenda si mostra con le sue linguette in fila (Giorno, Settimana, Mese); la sua quarta, l'Elenco, oggi sta
  nella tendina Segreteria come «Elenco del giorno» (oggi=False qui sotto);
- le voci con linguette (Ambulatori, Segreteria, Configura) e la tendina Aiuto sono tendine, con le linguette dentro;
  quelle del gruppo «aiuto» stanno a destra, dopo la ricerca;
- il tasto e la guida di una voce vanno sul collegamento che porta alla stessa pagina (G su Giorno, C su
  Conferme); la guida di una tendina va sulla tendina; il tasto di un collegamento nascosto va sul collegamento
  visibile che porta alla stessa pagina (E su Elenco del giorno);
- una tendina è accesa se è accesa la sua voce o una delle sue linguette (anche una «fuori»: oggi l'Elenco del
  giorno accende la tendina Segreteria).
"""
from datetime import date

from flask import g as contesto, url_for
from jinja2 import pass_context
from markupsafe import Markup

ARGOMENTI = ('struttura', 'giorno', 'giorno_data', 'mese')

# i gruppi del menu, in ordine; il titolo (testo nuovo della veste) è None se non si mostra
GRUPPI = [
    ('agende', 'Agende'),
    ('aree', 'Aree'),
    ('aiuto', None),            # «Aiuto e impostazioni» in fondo al menu nelle tavole; oggi a destra, dopo la ricerca
]

VOCI = []
LINGUETTE = {}                  # chiave della voce -> dict(etichetta=..., voci=[...])
AIUTO = []                      # la tendina Aiuto, come oggi
NASCOSTI = []                   # collegamenti senza voce, solo per un tasto


def testo(s):
    """Una parola del menu, pronta per la pagina: & < > " scritti come entità, l'apostrofo no («Lista d'attesa»
    resta com'era nell'HTML di oggi). Nel testo e negli attributi fra virgolette doppie basta così."""
    if s is None:
        return None
    return Markup(str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&#34;'))


def _controlla_argomenti(argomenti):
    argomenti = tuple(argomenti or ())
    sbagliati = [a for a in argomenti if a not in ARGOMENTI]
    if sbagliati:
        raise ValueError('argomenti sconosciuti %s (si possono usare %s)' % (sbagliati, ', '.join(ARGOMENTI)))
    return argomenti


def _tasti_usati():
    tasti = [v['tasto'] for v in VOCI] + [x['tasto'] for x in NASCOSTI] + [x.get('tasto') for x in AIUTO]
    for gruppo in LINGUETTE.values():
        tasti += [x['tasto'] for x in gruppo['voci']]
    return {t for t in tasti if t}


def registra_voce(gruppo, chiave, endpoint, parola, argomenti=(), icona=None, sezioni=(), condizione=None,
                  tasto=None, guida=None, contatore=None, titolo_contatore=None, tendina=None, oggi=None, dopo=None):
    """Aggiunge una voce al menu (alla fine del suo gruppo, o dopo la voce «dopo»). Torna la voce.
    Due voci non possono avere la stessa chiave, una sezione in comune o lo stesso tasto. «tendina»: le voci di una
    tendina che non porta a una pagina (Aiuto). «oggi»: come la disegna il menu di oggi, 'in_fila' (le sue linguette
    in fila, come l'Agenda); senza, una tendina se ha linguette, altrimenti un collegamento."""
    if gruppo not in dict(GRUPPI):
        raise ValueError('gruppo sconosciuto: %s' % gruppo)
    if any(v['chiave'] == chiave for v in VOCI):
        raise ValueError('voce già nel menu: %s' % chiave)
    sezioni = frozenset(sezioni or ())
    doppie = [(v['chiave'], s) for v in VOCI for s in sezioni & v['sezioni']]
    if doppie:
        raise ValueError('sezioni già di un\'altra voce: %s' % doppie)
    if tasto and tasto in _tasti_usati():
        raise ValueError('tasto già usato: %s' % tasto)
    if endpoint is None and tendina is None:
        raise ValueError('una voce senza indirizzo deve avere una tendina: %s' % chiave)
    voce = dict(gruppo=gruppo, chiave=chiave, endpoint=endpoint, argomenti=_controlla_argomenti(argomenti),
                parola=parola, icona=icona, sezioni=sezioni, condizione=condizione, tasto=tasto, guida=guida,
                contatore=contatore, titolo_contatore=titolo_contatore, tendina=tendina, oggi=oggi)
    if dopo is not None:
        posto = next((i for i, v in enumerate(VOCI) if v['chiave'] == dopo and v['gruppo'] == gruppo), None)
        if posto is None:
            raise ValueError('«dopo» deve essere una voce dello stesso gruppo: %s' % dopo)
        posto += 1
    else:                       # dopo l'ultima voce del suo gruppo e prima di quelle dei gruppi che vengono dopo
        ordine = [g for g, _ in GRUPPI]
        posto = len([v for v in VOCI if ordine.index(v['gruppo']) <= ordine.index(gruppo)])
    VOCI.insert(posto, voce)
    return voce


def registra_linguetta(voce, endpoint, parola, argomenti=(), sezioni=(), sotto=None, contatore=None, guida=None,
                       tasto=None, fuori=False, oggi=True, etichetta=None):
    """Aggiunge una linguetta alle pagine della voce «voce» (la chiave), in fondo. Torna la linguetta.
    La prima linguetta di una voce dà l'etichetta del gruppo di linguette (per i lettori di schermo)."""
    sua = next((v for v in VOCI if v['chiave'] == voce), None)
    if sua is None:
        raise ValueError('voce sconosciuta: %s' % voce)
    if not fuori and not frozenset(sezioni or ()) <= sua['sezioni']:
        raise ValueError('una linguetta si accende solo nelle pagine della sua voce: %s fuori da %s'
                         % (sorted(frozenset(sezioni or ()) - sua['sezioni']), voce))
    if tasto and tasto in _tasti_usati():
        raise ValueError('tasto già usato: %s' % tasto)
    gruppo = LINGUETTE.setdefault(voce, dict(etichetta=etichetta, voci=[]))
    if etichetta and not gruppo['etichetta']:
        gruppo['etichetta'] = etichetta
    sezioni = frozenset(sezioni or ())
    if not fuori:
        doppie = [(x['parola'], s) for x in gruppo['voci'] if not x['fuori'] for s in sezioni & x['sezioni']]
        if doppie:
            raise ValueError('sezioni già di un\'altra linguetta di %s: %s' % (voce, doppie))
    linguetta = dict(endpoint=endpoint, argomenti=_controlla_argomenti(argomenti), parola=parola, sezioni=sezioni,
                     sotto=sotto, contatore=contatore, guida=guida, tasto=tasto, fuori=fuori, oggi=oggi)
    gruppo['voci'].append(linguetta)
    return linguetta


# ---------------------------------------------------------------- le voci del programma
def _sotto_esportazioni(vale):
    return 'giorno, settimana e mese' + (': ambulatori, sala operatoria o tutto insieme' if vale('ci_sono_sale')
                                         else ' degli ambulatori')


registra_voce('agende', 'oggi', 'cruscotto.oggi', 'Oggi', ('struttura',), icona='sun', sezioni={'oggi'},
              guida='menu-oggi')
# l'Agenda: oggi le sue linguette stanno in fila nel menu (Giorno, Settimana, Mese)
registra_voce('agende', 'agenda', 'giorno', 'Agenda', ('giorno', 'struttura'), icona='calendar',
              sezioni={'giorno', 'settimana', 'mese', 'elenco'}, tasto='g', guida='menu-giorno', oggi='in_fila')
registra_voce('agende', 'sala', 'sala.giornata', 'Sala', ('giorno', 'struttura'), icona='activity', sezioni={'sala'},
              condizione='ci_sono_sale', guida='menu-sala')
registra_voce('aree', 'pazienti', 'pazienti.elenco', 'Pazienti', icona='users', sezioni={'pazienti'},
              guida='menu-pazienti')
registra_voce('aree', 'turni', 'personale.turni', 'Turni', ('struttura',), icona='clock', sezioni={'personale'},
              guida='menu-turni')
registra_voce('aree', 'ambulatori', 'ambulatori.settimana', 'Ambulatori', ('giorno', 'struttura'), icona='door-closed',
              sezioni={'ambulatori', 'programmazione', 'live', 'riepilogo-periodo', 'esportazioni'},
              guida='menu-ambulatori')
registra_voce('aree', 'dove', 'dovesifa.pagina', 'Dove si fa', ('struttura',), icona='map-pin', sezioni={'dove'},
              tasto='d', guida='menu-dove')
# la voce porta alle Conferme, come la prima linguetta: il tasto C resta su un collegamento di ogni pagina
registra_voce('aree', 'segreteria', 'viste.conferme', 'Segreteria', ('struttura',), icona='phone',
              sezioni={'conferme', 'confermare', 'chiusura', 'cose', 'attesa', 'disponibilita'}, tasto='c',
              guida='menu-segreteria', contatore='n_da_confermare', titolo_contatore='da confermare')
registra_voce('aree', 'cassa', 'cassa.cassa_giorno', 'Cassa', ('giorno', 'struttura'), icona='euro',
              sezioni={'cassa'})
registra_voce('aree', 'statistiche', 'viste.statistiche', 'Statistiche', ('struttura',), icona='chart-no-axes-column',
              sezioni={'statistiche'})
# Aiuto resta una tendina, con le voci di oggi (AIUTO)
registra_voce('aiuto', 'aiuto', None, 'Aiuto', icona='circle-question-mark', sezioni={'aiuto'}, guida='menu-aiuto',
              tendina=AIUTO)
registra_voce('aiuto', 'configura', 'anagrafiche.elenco', 'Configura', icona='sliders-horizontal',
              sezioni={'anagrafiche', 'gruppo', 'invii', 'importa', 'impostazioni', 'aggiornamenti'},
              guida='menu-configura')

# la tendina Aiuto di oggi: «Guida di questa pagina» resta nascosta finché guida.js non la mostra
AIUTO.extend([
    dict(endpoint=None, classe='avvia-guida', azione_guida='pagina', nascosta=True, parola='Guida di questa pagina',
         sotto='un giro sullo schermo, passo per passo'),
    dict(endpoint='guida.indice', parola='Come fare…', sotto='tutte le guide, con immagini e video'),
    dict(endpoint='aggiornamenti.novita_pagina', parola='Novità', sotto='cosa c\'è di nuovo in questa versione'),
    dict(endpoint=None, azione_guida='tasti', parola='Tasti rapidi', sotto='anche con il tasto ?'),
])

# il tasto E: nella veste nuova l'Elenco del giorno non è più una voce; un collegamento nascosto in ogni pagina lo
# tiene (un clic su un <a hidden> apre la pagina: provato con Chromium il 22/11)
NASCOSTI.append(dict(endpoint='viste.elenco_giorno', argomenti=('giorno', 'struttura'), parola='Elenco del giorno',
                     tasto='e'))

# le linguette: oggi le tendine (e Giorno, Settimana, Mese in fila), con le stesse parole e gli stessi indirizzi
registra_linguetta('agenda', 'giorno', 'Giorno', ('giorno', 'struttura'), sezioni={'giorno'},
                   etichetta='Viste dell\'agenda')
registra_linguetta('agenda', 'viste.settimana', 'Settimana', ('giorno', 'struttura'), sezioni={'settimana'})
registra_linguetta('agenda', 'viste.mese', 'Mese', ('mese', 'struttura'), sezioni={'mese'}, guida='menu-mese')
# oggi=False: oggi l'Elenco sta nella tendina Segreteria («Elenco del giorno», qui sotto)
registra_linguetta('agenda', 'viste.elenco_giorno', 'Elenco', ('giorno', 'struttura'), sezioni={'elenco'}, oggi=False)

registra_linguetta('segreteria', 'viste.conferme', 'Conferme', ('struttura',), sezioni={'conferme'},
                   sotto='telefonate per il prossimo giorno', etichetta='Pagine di Segreteria')
registra_linguetta('segreteria', 'segreteria.da_confermare', 'Da confermare', ('struttura',), sezioni={'confermare'},
                   sotto='prenotazioni ancora in sospeso', contatore='n_da_confermare')
registra_linguetta('segreteria', 'segreteria.chiusura', 'Chiusura della giornata', ('giorno', 'struttura'),
                   sezioni={'chiusura'}, sotto='arrivati e non presentati')
registra_linguetta('segreteria', 'segreteria.cose_da_fare', 'Da fare', ('struttura',), sezioni={'cose'},
                   sotto='richiamare, sollecitare, ricordare')
registra_linguetta('segreteria', 'segreteria.attesa', 'Lista d\'attesa', ('struttura',), sezioni={'attesa'},
                   sotto='chi vuole un posto prima')
registra_linguetta('segreteria', 'viste.disponibilita', 'Prima disponibilità', ('struttura',), sezioni={'disponibilita'},
                   sotto='il primo posto libero di un medico')
# porta all'Agenda (fuori): nella veste nuova qui non si accende; oggi accende la tendina Segreteria
registra_linguetta('segreteria', 'viste.elenco_giorno', 'Elenco del giorno', ('giorno', 'struttura'),
                   sezioni={'elenco'}, sotto='tutti gli appuntamenti in ordine di ora', fuori=True)

registra_linguetta('ambulatori', 'ambulatori.settimana', 'Pianificazione della settimana', ('giorno', 'struttura'),
                   sezioni={'ambulatori'}, sotto='chi sta in quale stanza, mattina e pomeriggio; le stanze libere',
                   etichetta='Pagine di Ambulatori')
registra_linguetta('ambulatori', 'ambulatori.mese', 'Programmazione del mese', ('mese', 'struttura'),
                   sezioni={'programmazione'}, sotto='per specialità e medico, con le date in cui viene')
registra_linguetta('ambulatori', 'live.pagina', 'Riepilogo live', ('struttura',), sezioni={'live'},
                   sotto='adesso: come va la giornata, stanza per stanza; si aggiorna da solo')
registra_linguetta('ambulatori', 'ambulatori.riepilogo', 'Riepilogo del periodo', ('struttura',),
                   sezioni={'riepilogo-periodo'},
                   sotto='com\'è andata: un giorno, una settimana, un mese, per stanza e per medico')
registra_linguetta('ambulatori', 'esportazioni.pagina', 'Esportazioni in Excel', ('giorno_data', 'struttura'),
                   sezioni={'esportazioni'}, sotto=_sotto_esportazioni)

registra_linguetta('configura', 'anagrafiche.elenco', 'Anagrafiche', sezioni={'anagrafiche'},
                   sotto='stanze, medici, turni, prestazioni, strutture', etichetta='Pagine di Configura')
registra_linguetta('configura', 'dovesifa.strutture', 'Strutture del gruppo', sezioni={'gruppo'},
                   sotto='database delle prestazioni e recapiti, per Dove si fa')
registra_linguetta('configura', 'invii.pagina', 'Email e WhatsApp', sezioni={'invii'},
                   sotto='email automatiche, promemoria, registro')
registra_linguetta('configura', 'importa.carica', 'Importa da Excel', sezioni={'importa'},
                   sotto='rubrica e agende dei file vecchi')
registra_linguetta('configura', 'viste.impostazioni', 'Impostazioni', sezioni={'impostazioni'},
                   sotto='backup, messaggi, stampa, tema')
registra_linguetta('configura', 'aggiornamenti.pagina', 'Aggiornamenti', sezioni={'aggiornamenti'},
                   sotto='versione installata, Aggiorna adesso')
# M2: qui la settima linguetta, «Aree e accessi» (DECISIONI-VESTE.md, Configura)


# ---------------------------------------------------------------- le voci per la pagina aperta
def argomenti_di(voce, sid, data):
    """Gli argomenti di url_for per una voce, dalla pagina aperta (nell'ordine della voce: l'indirizzo esce uguale)."""
    a = {}
    for x in voce.get('argomenti', ()):
        if x == 'struttura':
            a['struttura'] = sid
        elif x == 'giorno':
            a['iso'] = data
        elif x == 'giorno_data':
            a['data'] = data
        elif x == 'mese':
            a['aaaamm'] = data[:7]
    return a


def indirizzo_di(voce, sid, data):
    """L'indirizzo di una voce dalla pagina aperta; '#' per chi non porta a una pagina (le voci della guida)."""
    if not voce.get('endpoint'):
        return '#'
    return url_for(voce['endpoint'], **argomenti_di(voce, sid, data))


def costruisci(sezione, sid, data, funzioni=None):
    """Le voci del menu per una pagina: sezione, struttura (sid) e giorno (data, «AAAA-MM-GG») della pagina; funzioni:
    le funzioni dei modelli che condizioni e contatori nominano (ci_sono_sale, n_da_confermare), di solito il contesto
    del modello. Torna un dizionario: voci (solo quelle la cui condizione è vera, con indirizzo, accesa, linguette…),
    gruppi, accese e accesa (la voce accesa, se è una sola), linguette (quelle della voce accesa), nascosti, oggi (il
    disegno di oggi). Le parole sono testo semplice: le scrive testo()."""
    funzioni = funzioni if funzioni is not None else {}
    sez = sezione or ''
    contatori = {}

    def vale(condizione):
        if condizione is None:
            return True
        if callable(condizione):
            return bool(condizione())
        f = funzioni.get(condizione)
        return bool(f()) if callable(f) else False

    def conta(nome):
        if not nome:
            return 0
        if nome not in contatori:
            f = nome if callable(nome) else funzioni.get(nome)
            contatori[nome] = f() if callable(f) else 0
        return contatori[nome]

    def fatta(x, **altro):
        sotto = x.get('sotto')
        if callable(sotto):
            sotto = sotto(vale)
        uscita = dict(endpoint=x.get('endpoint'), argomenti=x.get('argomenti', ()), url=indirizzo_di(x, sid, data),
                      parola=testo(x['parola']), sotto=testo(sotto), tasto=x.get('tasto'), guida=x.get('guida'),
                      sezioni=x.get('sezioni', frozenset()), contatore=conta(x.get('contatore')))
        uscita.update(altro)
        return uscita

    voci = []
    for v in VOCI:
        if not vale(v['condizione']):
            continue
        linguette = [fatta(x, fuori=x['fuori'], oggi=x['oggi'], accesa=sez in x['sezioni'] and not x['fuori'])
                     for x in LINGUETTE.get(v['chiave'], dict(voci=[]))['voci']]
        tendina = [fatta(x, classe=x.get('classe'), azione_guida=x.get('azione_guida'), nascosta=x.get('nascosta', False),
                         accesa=False) for x in (v['tendina'] or [])]
        voci.append(fatta(v, chiave=v['chiave'], gruppo=v['gruppo'], icona=v['icona'], accesa=sez in v['sezioni'],
                          titolo_contatore=v['titolo_contatore'], linguette=linguette, tendina=tendina,
                          etichetta_linguette=LINGUETTE.get(v['chiave'], {}).get('etichetta'),
                          oggi=v['oggi'] or ('tendina' if linguette or tendina else 'voce')))
    accese = [v for v in voci if v['accesa']]
    menu = dict(sezione=sez, sid=sid, data=data, voci=voci,
                gruppi=[(g, testo(t), [v for v in voci if v['gruppo'] == g]) for g, t in GRUPPI],
                accesa=accese[0] if len(accese) == 1 else None, accese=accese,
                nascosti=[fatta(x, accesa=False) for x in NASCOSTI])
    menu['linguette'] = menu['accesa']['linguette'] if menu['accesa'] else []
    menu['oggi'] = disegno_di_oggi(menu)
    return menu


def disegno_di_oggi(menu):
    """Il menu di oggi (in alto, con le tendine) fatto con le stesse voci: una lista di pezzi, in ordine, che
    _menu.html scrive così com'è. Le regole sono in testa al file."""
    nascosti = {x['url']: x for x in menu['nascosti']}

    def collegamento(x, tasto=None, guida=None):
        c = dict(x)
        c['tasto'] = tasto or x.get('tasto') or (nascosti[x['url']]['tasto'] if x['url'] in nascosti else None)
        c['guida'] = guida or x.get('guida')
        c['accesa'] = menu['sezione'] in x['sezioni']          # oggi si accende anche una linguetta «fuori»
        return c

    pezzi = []
    for g, _, voci in menu['gruppi']:
        if g == 'aree':
            pezzi.append(dict(tipo='separatore'))
        elif g == 'aiuto':
            pezzi += [dict(tipo='spinta'), dict(tipo='ricerca')]
        for v in voci:
            if v['oggi'] == 'in_fila':
                for x in v['linguette']:
                    if not x['oggi']:
                        continue
                    stessa = x['url'] == v['url']
                    pezzi.append(dict(tipo='voce', voce=collegamento(x, tasto=v['tasto'] if stessa else None,
                                                                     guida=v['guida'] if stessa else None)))
            elif v['oggi'] == 'tendina':
                dentro = [collegamento(x, tasto=v['tasto'] if x['url'] == v['url'] else None)
                          for x in v['linguette'] if x['oggi']] + [dict(x) for x in v['tendina']]
                pezzi.append(dict(tipo='tendina', voce=v, voci=dentro, a_destra=g == 'aiuto',
                                  accesa=v['accesa'] or any(x['accesa'] for x in dentro)))
            else:
                pezzi.append(dict(tipo='voce', voce=collegamento(v)))
    return pezzi


@pass_context
def menu_della_pagina(ctx):
    """Per _menu.html: le voci della pagina che si sta disegnando, dal suo contesto (sezione, sid, data_menu, e le
    funzioni ci_sono_sale e n_da_confermare), con le stesse regole che il modello aveva nelle sue prime righe."""
    data = ctx.get('data_menu') or ctx.get('oggi_iso') or date.today().isoformat()
    menu = costruisci(ctx.get('sezione'), ctx.get('sid') or None, data, ctx)
    contesto.menu_della_pagina = menu          # per le prove (prove_menu.py): l'ultimo menu fatto in questa richiesta
    return menu


def collega(app):
    app.add_template_global(menu_della_pagina, 'menu_della_pagina')
