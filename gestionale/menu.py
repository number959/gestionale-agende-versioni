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
porta a un'altra voce (l'Elenco del giorno sta nell'Agenda): nella veste nuova lì non si accende. Una linguetta si
accende per sezione (le sezioni della sua voce che la accendono) e, se le serve, solo in certe pagine («pagine»: le
funzioni, request.endpoint): così più linguette possono stare sulla stessa sezione (le quattro della Cassa nella
tappa 6: Giorno, Mese, Listino, Tariffari, tutte sulla sezione «cassa»). La tendina Aiuto (AIUTO) resta com'è;
NASCOSTI sono i collegamenti che servono solo a un tasto (E, l'Elenco del giorno). Linguette, voci della tendina e
nascosti hanno anche loro la condizione, come le voci: un modulo spento toglie anche una sua linguetta messa sotto la
voce di un altro (per esempio in Configura) e il suo tasto.

I moduli (dalla 1.14) aggiungono voci e linguette con registra_voce() e registra_linguetta(), senza toccare i modelli;
una linguetta di un modulo sotto la voce di un altro si accende su una sezione sua, data alla voce con registra_sezioni()
(«Aree e accessi», la settima linguetta di Configura, la registra accessi.py sulla sezione «accessi»).

La condizione per pagina (dalla 1.13, l'accesso dagli altri PC): oltre alla condizione di ognuna, voci, linguette, voci
della tendina e collegamenti nascosti ci sono solo se la loro pagina si apre per chi guarda. La decide una funzione sola,
data da app.py con condizione_per_pagina() (accessi.si_apre: l'area della pagina presa dal censimento di accessi.py, e
il livello dell'utente in quell'area); sul PC principale è sempre vera e il menu resta quello di sempre. Dalla rete una
voce la cui pagina non si apre porta alla prima delle sue linguette che si apre, senza il suo tasto (Configura, a chi ha
solo Email e WhatsApp, porta lì); se non ne ha nessuna, non c'è.
Ogni voce vuole la sua icona, che deve essere in templates/_icone.html (collega() le controlla quando i modelli ci
sono: senza, nel menu stretto resterebbe un quadrato vuoto). costruisci() fa le voci per la pagina aperta, con gli
indirizzi scritti da url_for; nei modelli è menu_della_pagina().

Il disegno (dalla tappa 2, la cornice della veste nuova): templates/_menu.html fa il menu a sinistra (le voci con
la loro icona, la tendina Aiuto, il collegamento nascosto del tasto E), _barra.html la barra in alto (percorso,
ricerca rapida, posto della campanella) e _linguette.html le linguette della voce accesa, in cima al contenuto. Ogni
pezzo sta in un contenitore con data-cornice (strumenti/confronta_rami.py lo confronta a parte). Come il menu di prima
(in alto, con le tendine) disegnava le stesse voci lo sa solo prove_menu.py, che confronta le voci con il menu del ramo
principale: qui niente che serva soltanto alle prove.
"""
import re
from datetime import date

from flask import g as contesto, has_request_context, request as richiesta, url_for
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
ICONE = None                    # i nomi delle icone di templates/_icone.html, letti da collega()
SI_APRE = None                  # la condizione per pagina: funzione(endpoint) -> la pagina si apre? (condizione_per_pagina)


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
                  tasto=None, guida=None, contatore=None, titolo_contatore=None, tendina=None, dopo=None):
    """Aggiunge una voce al menu (alla fine del suo gruppo, o dopo la voce «dopo»). Torna la voce.
    Due voci non possono avere la stessa chiave, una sezione in comune o lo stesso tasto. «tendina»: le voci di una
    tendina che non porta a una pagina (Aiuto)."""
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
    _controlla_icona(chiave, icona)
    voce = dict(gruppo=gruppo, chiave=chiave, endpoint=endpoint, argomenti=_controlla_argomenti(argomenti),
                parola=parola, icona=icona, sezioni=sezioni, condizione=condizione, tasto=tasto, guida=guida,
                contatore=contatore, titolo_contatore=titolo_contatore, tendina=tendina)
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


def registra_sezioni(voce, sezioni):
    """Dà alla voce «voce» (la chiave) altre sezioni, per la linguetta di un modulo che sta sotto di lei e ha una pagina
    sua (accessi.py: «Aree e accessi» in Configura, sezione «accessi»). Una sezione già di un'altra voce è rifiutata:
    ogni pagina accende una voce sola. Torna la voce."""
    sua = next((v for v in VOCI if v['chiave'] == voce), None)
    if sua is None:
        raise ValueError('voce sconosciuta: %s' % voce)
    sezioni = frozenset(sezioni or ())
    doppie = [(v['chiave'], s) for v in VOCI if v is not sua for s in sezioni & v['sezioni']]
    if doppie:
        raise ValueError('sezioni già di un\'altra voce: %s' % doppie)
    sua['sezioni'] = sua['sezioni'] | sezioni
    return sua


def condizione_per_pagina(funzione):
    """La condizione per pagina (vedi in testa): funzione(endpoint) dice se la pagina si apre per chi guarda; None la
    toglie (tutte le voci, come sul PC principale). La dà app.py: accessi.si_apre."""
    global SI_APRE
    SI_APRE = funzione


def _controlla_icona(chiave, icona):
    if not icona:
        raise ValueError('una voce del menu vuole la sua icona (un nome di templates/_icone.html): %s' % chiave)
    if ICONE is not None and icona not in ICONE:
        raise ValueError('l\'icona %s della voce %s non c\'è in templates/_icone.html (strumenti/genera_icone.py)'
                         % (icona, chiave))


def registra_linguetta(voce, endpoint, parola, argomenti=(), sezioni=(), sotto=None, contatore=None, guida=None,
                       tasto=None, fuori=False, etichetta=None, pagine=(), condizione=None):
    """Aggiunge una linguetta alle pagine della voce «voce» (la chiave), in fondo. Torna la linguetta.
    La prima linguetta di una voce dà l'etichetta del gruppo di linguette (per i lettori di schermo).
    «pagine»: se c'è, la linguetta si accende solo nelle pagine di quelle funzioni (request.endpoint), dentro le sue
    sezioni; due linguette della stessa voce possono allora avere una sezione in comune, ma non una pagina.
    «condizione»: come per le voci (il nome di una funzione dei modelli o una funzione senza argomenti); falsa, la
    linguetta non c'è."""
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
    pagine = frozenset(pagine or ())
    if not fuori:
        # due linguette si pestano se hanno una sezione in comune e nessuna delle due dice le sue pagine, o se le pagine
        # che dicono si toccano
        doppie = [(x['parola'], s) for x in gruppo['voci'] if not x['fuori'] for s in sezioni & x['sezioni']
                  if not pagine or not x['pagine'] or pagine & x['pagine']]
        if doppie:
            raise ValueError('sezioni già di un\'altra linguetta di %s: %s' % (voce, doppie))
    linguetta = dict(endpoint=endpoint, argomenti=_controlla_argomenti(argomenti), parola=parola, sezioni=sezioni,
                     sotto=sotto, contatore=contatore, guida=guida, tasto=tasto, fuori=fuori, pagine=pagine,
                     condizione=condizione)
    gruppo['voci'].append(linguetta)
    return linguetta


# ---------------------------------------------------------------- le voci del programma
def _sotto_esportazioni(vale):
    return 'giorno, settimana e mese' + (': ambulatori, sala operatoria o tutto insieme' if vale('ci_sono_sale')
                                         else ' degli ambulatori')


registra_voce('agende', 'oggi', 'cruscotto.oggi', 'Oggi', ('struttura',), icona='sun', sezioni={'oggi'},
              guida='menu-oggi')
# l'Agenda: Giorno, Settimana, Mese ed Elenco sono le sue linguette
registra_voce('agende', 'agenda', 'giorno', 'Agenda', ('giorno', 'struttura'), icona='calendar',
              sezioni={'giorno', 'settimana', 'mese', 'elenco'}, tasto='g', guida='menu-giorno')
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
# Aiuto resta una tendina, con le voci di prima (AIUTO)
registra_voce('aiuto', 'aiuto', None, 'Aiuto', icona='circle-question-mark', sezioni={'aiuto'}, guida='menu-aiuto',
              tendina=AIUTO)
registra_voce('aiuto', 'configura', 'anagrafiche.elenco', 'Configura', icona='sliders-horizontal',
              sezioni={'anagrafiche', 'gruppo', 'invii', 'importa', 'impostazioni', 'aggiornamenti'},
              guida='menu-configura')

# la tendina Aiuto: «Guida di questa pagina» resta nascosta finché guida.js non la mostra
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

# le linguette: prima le tendine del menu (e Giorno, Settimana, Mese in fila), con le stesse parole e gli stessi indirizzi
registra_linguetta('agenda', 'giorno', 'Giorno', ('giorno', 'struttura'), sezioni={'giorno'},
                   etichetta='Viste dell\'agenda')
registra_linguetta('agenda', 'viste.settimana', 'Settimana', ('giorno', 'struttura'), sezioni={'settimana'})
registra_linguetta('agenda', 'viste.mese', 'Mese', ('mese', 'struttura'), sezioni={'mese'}, guida='menu-mese')
# prima l'Elenco stava nella tendina Segreteria («Elenco del giorno», qui sotto)
registra_linguetta('agenda', 'viste.elenco_giorno', 'Elenco', ('giorno', 'struttura'), sezioni={'elenco'},
                   sotto='tutti gli appuntamenti in ordine di ora')

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
# la settima linguetta, «Aree e accessi» (DECISIONI-VESTE.md, Configura), la registra accessi.py, con la sua sezione


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


def costruisci(sezione, sid, data, funzioni=None, endpoint=None):
    """Le voci del menu per una pagina: sezione, struttura (sid) e giorno (data, «AAAA-MM-GG») della pagina; funzioni:
    le funzioni dei modelli che condizioni e contatori nominano (ci_sono_sale, n_da_confermare), di solito il contesto
    del modello; endpoint: la funzione della pagina (request.endpoint), per le linguette che dicono le loro «pagine».
    Torna un dizionario: voci (solo quelle la cui condizione è vera, con indirizzo, accesa, linguette…), gruppi, accese
    e accesa (la voce accesa, se è una sola), linguette ed etichetta_linguette (quelle della voce accesa), nascosti.
    Linguette, voci della tendina e nascosti con una condizione falsa non ci sono, e nemmeno quelli la cui pagina non si
    apre (la condizione per pagina, SI_APRE: dalla rete); una voce la cui pagina non si apre porta alla prima delle sue
    linguette che si apre, senza il suo tasto, o non c'è. Le parole sono testo semplice: le scrive testo()."""
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

    def si_apre(x):
        # la condizione per pagina: chi non porta a una pagina (le voci della guida sullo schermo) c'è sempre
        return SI_APRE is None or not x.get('endpoint') or bool(SI_APRE(x['endpoint']))

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
                      sezioni=x.get('sezioni', frozenset()), pagine=x.get('pagine', frozenset()),
                      contatore=conta(x.get('contatore')))
        uscita.update(altro)
        return uscita

    def linguetta_accesa(x):
        return not x['fuori'] and sez in x['sezioni'] and (not x['pagine'] or endpoint in x['pagine'])

    voci = []
    for v in VOCI:
        if not vale(v['condizione']):
            continue
        linguette = [fatta(x, fuori=x['fuori'], accesa=linguetta_accesa(x))
                     for x in LINGUETTE.get(v['chiave'], dict(voci=[]))['voci']
                     if vale(x.get('condizione')) and si_apre(x)]
        tendina = [fatta(x, classe=x.get('classe'), azione_guida=x.get('azione_guida'), nascosta=x.get('nascosta', False),
                         accesa=False) for x in (v['tendina'] or []) if vale(x.get('condizione')) and si_apre(x)]
        al_posto = None
        if not si_apre(v):
            # dalla rete: la sua pagina non si apre, la voce porta alla prima delle sue linguette che si apre (mai una
            # «fuori», che è di un'altra voce), senza il tasto (porterebbe altrove); senza linguette non c'è
            al_posto = next((x for x in linguette if not x['fuori']), None)
            if al_posto is None:
                continue
        voce = fatta(v, chiave=v['chiave'], gruppo=v['gruppo'], icona=v['icona'], accesa=sez in v['sezioni'],
                     titolo_contatore=v['titolo_contatore'], linguette=linguette, tendina=tendina,
                     etichetta_linguette=LINGUETTE.get(v['chiave'], {}).get('etichetta'))
        if al_posto is not None:
            voce.update(endpoint=al_posto['endpoint'], argomenti=al_posto['argomenti'], url=al_posto['url'], tasto=None)
        voci.append(voce)
    accese = [v for v in voci if v['accesa']]
    menu = dict(sezione=sez, sid=sid, data=data, voci=voci,
                gruppi=[(g, testo(t), [v for v in voci if v['gruppo'] == g]) for g, t in GRUPPI],
                accesa=accese[0] if len(accese) == 1 else None, accese=accese, endpoint=endpoint,
                nascosti=[fatta(x, accesa=False) for x in NASCOSTI if vale(x.get('condizione')) and si_apre(x)])
    menu['linguette'] = menu['accesa']['linguette'] if menu['accesa'] else []
    menu['etichetta_linguette'] = testo(menu['accesa']['etichetta_linguette']) if menu['accesa'] else None
    # per il pezzo linguette di _pezzi.html: la riga piccola delle tendine di prima diventa il title; la linguetta che
    # porta in un'altra area ha la freccina (arrow-up-right) e non si accende
    menu['linguette_del_pezzo'] = [dict(testo=x['parola'], indirizzo=x['url'], accesa=x['accesa'], tasto=x['tasto'],
                                        guida=x['guida'], titolo=x['sotto'], conta=x['contatore'],
                                        icona='arrow-up-right' if x['fuori'] else None) for x in menu['linguette']]
    return menu


def iniziali(nome):
    """Le iniziali della struttura per il menu stretto (al posto del logo): le prime lettere delle prime due parole
    che non sono articoli o preposizioni («Clinica Posillipo» → «CP», «Villa dei Fiori» → «VF»)."""
    piccole = {'di', 'del', 'della', 'dei', 'degli', 'delle', 'da', 'la', 'il', 'lo', 'le', 'gli', 'e', 'a', 'in', 'al'}
    parole = [p for p in str(nome or '').replace('.', ' ').replace("'", ' ').split() if p[:1].isalnum()]
    scelte = [p for p in parole if p.lower() not in piccole] or parole
    return ''.join(p[0] for p in scelte[:2]).upper()


def percorso(menu, endpoint, nome_struttura):
    """Il percorso della barra in alto: struttura › voce › linguetta. La struttura solo per le voci che la portano
    (non Pazienti, Configura, Aiuto: come nelle tavole); la linguetta solo se è proprio la sua pagina (sull'appuntamento
    la linguetta Giorno resta accesa, ma il percorso si ferma all'Agenda), o una delle sue «pagine»."""
    voce = menu['accesa']
    if voce is None:
        return []
    pezzi = [nome_struttura] if 'struttura' in voce['argomenti'] and nome_struttura else []
    pezzi.append(voce['parola'])
    pezzi += [x['parola'] for x in voce['linguette'] if x['accesa'] and (x['endpoint'] == endpoint or endpoint in x['pagine'])]
    return pezzi


@pass_context
def menu_della_pagina(ctx):
    """Per _menu.html, _barra.html e _linguette.html: le voci della pagina che si sta disegnando, dal suo contesto
    (sezione, sid, data_menu, e le funzioni ci_sono_sale e n_da_confermare), con le stesse regole che il modello del
    menu aveva nelle sue prime righe fino alla tappa 2. Fatte una volta per pagina (e per sezione, struttura e giorno)."""
    data = ctx.get('data_menu') or ctx.get('oggi_iso') or date.today().isoformat()
    endpoint = richiesta.endpoint if has_request_context() else None
    chiave = (ctx.get('sezione'), ctx.get('sid') or None, data, endpoint)
    fatti = contesto.setdefault('menu_fatti', {})
    if chiave not in fatti:                   # una volta per pagina: menu, barra e linguette lo chiedono tutti e tre
        fatti[chiave] = costruisci(chiave[0], chiave[1], data, ctx, endpoint)
    return fatti[chiave]


def icone_dei_modelli(app):
    """I nomi delle icone di templates/_icone.html (il dizionario scritto da strumenti/genera_icone.py)."""
    sorgente = app.jinja_env.loader.get_source(app.jinja_env, '_icone.html')[0]
    return set(re.findall(r"^  '([a-z0-9-]+)':", sorgente, re.M))


def collega(app):
    global ICONE
    ICONE = icone_dei_modelli(app)
    for v in VOCI:                  # quelle registrate finora; le altre le controlla registra_voce
        _controlla_icona(v['chiave'], v['icona'])
    app.add_template_global(menu_della_pagina, 'menu_della_pagina')
    app.add_template_global(iniziali, 'iniziali_struttura')
    app.add_template_global(percorso, 'percorso_della_pagina')
