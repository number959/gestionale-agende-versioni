# -*- coding: utf-8 -*-
"""BOZZA tappa 6 (non è nel repository): le linguette della Cassa, da aggiungere all'elenco di menu.py della tappa 2
(stessa forma di scratchpad/veste-cornice/menu_bozza.py, LINGUETTE).

Oggi Giorno, Mese, Listino e Tariffari hanno tutte sezione='cassa' (cassa.py:140, 217, 248; tariffari.py:436, 543, 612):
la linguetta accesa non si può dedurre dalla sezione. Due strade, senza toccare quello che il programma fa:
  A) (proposta) la voce dice anche gli endpoint che la accendono, e menu.py guarda request.endpoint;
  B) le viste passano sezioni diverse ('cassa', 'cassa-mese', 'listino', 'tariffari') e la voce Cassa del menu le
     elenca tutte: cambia una riga in 6 render_template, nessun indirizzo.
Gli argomenti sono quelli dei bottoni di oggi (cassa.html:19-21): Mese porta il mese del giorno guardato, che è
data_menu[:7] (cassa.py:217 passa data_menu=g); dal Listino e dai Tariffari data_menu non c'è e vale oggi."""

LINGUETTE_CASSA = dict(etichetta=None, voci=[      # etichetta del <nav> (aria-label): solo se approvata
    dict(endpoint='cassa.cassa_giorno', argomenti=('giorno', 'struttura'), parola='Giorno',            # parola nuova
         accende={'cassa.cassa_giorno'}),
    dict(endpoint='cassa.cassa_mese', argomenti=('mese', 'struttura'), parola='Mese',
         accende={'cassa.cassa_mese'}, guida=None),            # se la tappa 1 dà un data-guida al bottone Mese, qui
    dict(endpoint='cassa.listino', argomenti=('struttura',), parola='Listino', accende={'cassa.listino'}),
    dict(endpoint='tariffari.elenco', argomenti=('struttura',), parola='Tariffari dei medici',          # oggi «Tariffari»
         accende={'tariffari.elenco', 'tariffari.scheda', 'tariffari.anteprima'}),
])


def accesa(voce, endpoint):
    """Una linguetta sola accesa per pagina (prova della tappa 2): quella che elenca l'endpoint della richiesta."""
    return endpoint in voce.get('accende', ())


if __name__ == '__main__':
    # controllo veloce: ogni endpoint della Cassa accende una linguetta sola
    for ep in ('cassa.cassa_giorno', 'cassa.cassa_mese', 'cassa.listino', 'tariffari.elenco', 'tariffari.scheda',
               'tariffari.anteprima'):
        accese = [v['parola'] for v in LINGUETTE_CASSA['voci'] if accesa(v, ep)]
        assert len(accese) == 1, (ep, accese)
        print(ep, '->', accese[0])
