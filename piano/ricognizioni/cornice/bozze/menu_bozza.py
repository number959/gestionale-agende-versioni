# -*- coding: utf-8 -*-
"""BOZZA per la tappa 2 (non e' nel repository): il menu e le linguette da un elenco Python.

Ogni voce: indirizzo (endpoint), argomenti che porta (struttura, giorno, mese: come _menu.html:1-4), parola,
icona (nome Lucide di templates/_icone.html), sezioni che la accendono, condizione (come la Sala, _menu.html:17-18),
e gli attributi che oggi stanno sui collegamenti (data-tasto, data-guida) e che il lanciatore confronta.
I moduli (M1-M2) aggiungeranno le loro voci con registra_voce(), senza toccare i modelli; la condizione e' anche il
posto dove un domani si guarda se il modulo e' acceso (e, se Giovanni lo vorra', per quale PC o persona).

Argomenti: 'struttura' -> struttura=_sid; 'giorno' -> iso=_data; 'giorno_data' -> data=_data (esportazioni);
'mese' -> aaaamm=_data[:7]. Gli stessi di oggi, voce per voce."""

# ---------------------------------------------------------------- il menu a sinistra (tavole Nefro-*)
GRUPPI = [
    ('agende', 'Agende'),                       # testo nuovo (intestazione del gruppo nella tavola)
    ('aree', 'Aree'),                           # testo nuovo
    ('aiuto', None),                            # nav «Aiuto e impostazioni» nella tavola: senza intestazione visibile
]

VOCI = [
    # gruppo, chiave, endpoint, argomenti, parola, icona, sezioni, condizione, attributi
    dict(gruppo='agende', chiave='oggi', endpoint='cruscotto.oggi', argomenti=('struttura',), parola='Oggi',
         icona='sun', sezioni={'oggi'}, guida='menu-oggi'),
    dict(gruppo='agende', chiave='agenda', endpoint='giorno', argomenti=('giorno', 'struttura'), parola='Agenda',
         icona='calendar', sezioni={'giorno', 'settimana', 'mese', 'elenco'}, tasto='g', guida='menu-giorno'),
    dict(gruppo='agende', chiave='sala', endpoint='sala.giornata', argomenti=('giorno', 'struttura'), parola='Sala',
         icona='activity', sezioni={'sala'}, condizione='ci_sono_sale', guida='menu-sala'),
    dict(gruppo='aree', chiave='pazienti', endpoint='pazienti.elenco', argomenti=(), parola='Pazienti',
         icona='users', sezioni={'pazienti'}, guida='menu-pazienti'),
    dict(gruppo='aree', chiave='turni', endpoint='personale.turni', argomenti=('struttura',), parola='Turni',
         icona='clock', sezioni={'personale'}, guida='menu-turni'),
    dict(gruppo='aree', chiave='ambulatori', endpoint='ambulatori.settimana', argomenti=('giorno', 'struttura'),
         parola='Ambulatori', icona='door-closed',
         sezioni={'ambulatori', 'programmazione', 'live', 'riepilogo-periodo', 'esportazioni'}, guida='menu-ambulatori'),
    dict(gruppo='aree', chiave='dove', endpoint='dovesifa.pagina', argomenti=('struttura',), parola='Dove si fa',
         icona='map-pin', sezioni={'dove'}, tasto='d', guida='menu-dove'),
    # la voce porta alle Conferme, come la prima linguetta: il tasto C resta su un collegamento di ogni pagina
    dict(gruppo='aree', chiave='segreteria', endpoint='viste.conferme', argomenti=('struttura',), parola='Segreteria',
         icona='phone', sezioni={'conferme', 'confermare', 'chiusura', 'cose', 'attesa', 'disponibilita'},
         tasto='c', guida='menu-segreteria', contatore='n_da_confermare'),
    dict(gruppo='aree', chiave='cassa', endpoint='cassa.cassa_giorno', argomenti=('giorno', 'struttura'), parola='Cassa',
         icona='euro', sezioni={'cassa'}),
    dict(gruppo='aree', chiave='statistiche', endpoint='viste.statistiche', argomenti=('struttura',),
         parola='Statistiche', icona='chart-no-axes-column', sezioni={'statistiche'}),
    # Aiuto resta una tendina (decisione «quello che le tavole non disegnano»): voci in AIUTO qui sotto
    dict(gruppo='aiuto', chiave='aiuto', endpoint=None, argomenti=(), parola='Aiuto', icona='circle-question-mark',
         sezioni={'aiuto'}, guida='menu-aiuto', tendina='AIUTO'),
    dict(gruppo='aiuto', chiave='configura', endpoint='anagrafiche.elenco', argomenti=(), parola='Configura',
         icona='sliders-horizontal',
         sezioni={'anagrafiche', 'gruppo', 'invii', 'importa', 'impostazioni', 'aggiornamenti'}, guida='menu-configura'),
]

# la tendina Aiuto di oggi, identica (_menu.html:54-62)
AIUTO = [
    dict(endpoint=None, azione_guida='pagina', nascosta=True, parola='Guida di questa pagina',
         sotto='un giro sullo schermo, passo per passo'),
    dict(endpoint='guida.indice', parola='Come fare…', sotto='tutte le guide, con immagini e video'),
    dict(endpoint='aggiornamenti.novita_pagina', parola='Novità', sotto='cosa c\'è di nuovo in questa versione'),
    dict(endpoint=None, azione_guida='tasti', parola='Tasti rapidi', sotto='anche con il tasto ?'),
]

# il tasto E: «Elenco del giorno» non e' piu' nel menu; un collegamento nascosto nella cornice di ogni pagina
# (a.click() su un <a> nascosto apre la pagina: provato con Chromium il 22/11)
NASCOSTI = [
    dict(endpoint='viste.elenco_giorno', argomenti=('giorno', 'struttura'), parola='Elenco del giorno', tasto='e'),
]

# ---------------------------------------------------------------- le linguette (al posto delle tendine)
# sotto = la riga piccola delle tendine di oggi: nelle tavole Seg e Conf diventa il title della linguetta;
# nelle tavole di Ambulatori non c'e' (domanda aperta)
LINGUETTE = {
    'agenda': dict(etichetta="Viste dell'agenda", voci=[
        dict(endpoint='giorno', argomenti=('giorno', 'struttura'), parola='Giorno', sezioni={'giorno'}),
        dict(endpoint='viste.settimana', argomenti=('giorno', 'struttura'), parola='Settimana', sezioni={'settimana'}),
        dict(endpoint='viste.mese', argomenti=('mese', 'struttura'), parola='Mese', sezioni={'mese'}, guida='menu-mese'),
        dict(endpoint='viste.elenco_giorno', argomenti=('giorno', 'struttura'), parola='Elenco', sezioni={'elenco'}),
    ]),
    'segreteria': dict(etichetta='Pagine di Segreteria', voci=[
        dict(endpoint='viste.conferme', argomenti=('struttura',), parola='Conferme', sezioni={'conferme'},
             sotto='telefonate per il prossimo giorno'),
        dict(endpoint='segreteria.da_confermare', argomenti=('struttura',), parola='Da confermare',
             sezioni={'confermare'}, sotto='prenotazioni ancora in sospeso', contatore='n_da_confermare'),
        dict(endpoint='segreteria.chiusura', argomenti=('giorno', 'struttura'), parola='Chiusura della giornata',
             sezioni={'chiusura'}, sotto='arrivati e non presentati'),
        dict(endpoint='segreteria.cose_da_fare', argomenti=('struttura',), parola='Da fare', sezioni={'cose'},
             sotto='richiamare, sollecitare, ricordare'),
        dict(endpoint='segreteria.attesa', argomenti=('struttura',), parola='Lista d\'attesa', sezioni={'attesa'},
             sotto='chi vuole un posto prima'),
        dict(endpoint='viste.disponibilita', argomenti=('struttura',), parola='Prima disponibilità',
             sezioni={'disponibilita'}, sotto='il primo posto libero di un medico'),
        # nella tavola Seg1: porta all'Agenda (freccia, title nuovo «...: si apre nell'Agenda»), non si accende qui
        dict(endpoint='viste.elenco_giorno', argomenti=('giorno', 'struttura'), parola='Elenco del giorno',
             sezioni=set(), sotto='tutti gli appuntamenti in ordine di ora', fuori=True),
    ]),
    'ambulatori': dict(etichetta='Pagine di Ambulatori', voci=[
        dict(endpoint='ambulatori.settimana', argomenti=('giorno', 'struttura'), parola='Pianificazione della settimana',
             sezioni={'ambulatori'}, sotto='chi sta in quale stanza, mattina e pomeriggio; le stanze libere'),
        dict(endpoint='ambulatori.mese', argomenti=('mese', 'struttura'), parola='Programmazione del mese',
             sezioni={'programmazione'}, sotto='per specialità e medico, con le date in cui viene'),
        # resta fino a M6 (tavola Nefro-Ambulatori3-Live)
        dict(endpoint='live.pagina', argomenti=('struttura',), parola='Riepilogo live', sezioni={'live'},
             sotto='adesso: come va la giornata, stanza per stanza; si aggiorna da solo'),
        dict(endpoint='ambulatori.riepilogo', argomenti=('struttura',), parola='Riepilogo del periodo',
             sezioni={'riepilogo-periodo'}, sotto='com\'è andata: un giorno, una settimana, un mese, per stanza e per medico'),
        dict(endpoint='esportazioni.pagina', argomenti=('giorno_data', 'struttura'), parola='Esportazioni in Excel',
             sezioni={'esportazioni'}, sotto=None),    # oggi il testo dipende da ci_sono_sale(): _menu.html:29
    ]),
    'configura': dict(etichetta='Pagine di Configura', voci=[
        dict(endpoint='anagrafiche.elenco', argomenti=(), parola='Anagrafiche', sezioni={'anagrafiche'},
             sotto='stanze, medici, turni, prestazioni, strutture'),
        dict(endpoint='dovesifa.strutture', argomenti=(), parola='Strutture del gruppo', sezioni={'gruppo'},
             sotto='database delle prestazioni e recapiti, per Dove si fa'),
        dict(endpoint='invii.pagina', argomenti=(), parola='Email e WhatsApp', sezioni={'invii'},
             sotto='email automatiche, promemoria, registro'),
        dict(endpoint='importa.carica', argomenti=(), parola='Importa da Excel', sezioni={'importa'},
             sotto='rubrica e agende dei file vecchi'),
        dict(endpoint='viste.impostazioni', argomenti=(), parola='Impostazioni', sezioni={'impostazioni'},
             sotto='backup, messaggi, stampa, tema'),
        dict(endpoint='aggiornamenti.pagina', argomenti=(), parola='Aggiornamenti', sezioni={'aggiornamenti'},
             sotto='versione installata, Aggiorna adesso'),
        # M2: qui la settima (la pagina dei moduli), con il suo nome da decidere
    ]),
}


def argomenti_di(voce, sid, data):
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


def voce_accesa(sezione):
    """La voce del menu accesa per una sezione: una sola (prova nuova della tappa 2)."""
    accese = [v['chiave'] for v in VOCI if sezione in v['sezioni']]
    assert len(accese) <= 1, (sezione, accese)
    return accese[0] if accese else None


def linguette_di(sezione):
    """Il gruppo di linguette da mostrare in una pagina: quello della voce accesa, se ne ha."""
    chiave = voce_accesa(sezione)
    return LINGUETTE.get(chiave) if chiave else None
