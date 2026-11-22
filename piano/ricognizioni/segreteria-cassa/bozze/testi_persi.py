# -*- coding: utf-8 -*-
"""Per ogni modello: i pezzi di testo fisso di oggi che la tavola non mostra (anche quelli sotto condizione)."""
import json, os, re
QUI = os.path.dirname(os.path.abspath(__file__))
G = '/home/user/gestionale-agende-versioni/gestionale/templates'
COPPIE = {'conferme.html': 'Seg1-Conferme', '_stato.html': 'Seg1-Conferme', 'da_confermare.html': 'Seg2-DaConfermare',
          'chiusura.html': 'Seg3-Chiusura', 'cose_da_fare.html': 'Seg4-DaFare', 'attesa.html': 'Seg5-Attesa',
          'disponibilita.html': 'Seg6-Disponibilita', 'cassa.html': 'Cassa1-Giorno', 'cassa_mese.html': 'Cassa2-Mese',
          'listino.html': 'Cassa3-Listino', 'tariffari.html': 'Cassa4-Tariffari'}
def frammenti(nome):
    t = open(os.path.join(G, nome), encoding='utf-8').read()
    t = re.sub(r'\{#.*?#\}', ' ', t, flags=re.S)
    # attributi visibili: placeholder, title, aria-label
    attr = re.findall(r'(?:placeholder|title|aria-label)="([^"{]+)"', t)
    t = re.sub(r'\{%.*?%\}', '\n', t, flags=re.S); t = re.sub(r'\{\{.*?\}\}', '\n', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '\n', t).replace('&rsaquo;', '›').replace('&lsaquo;', '‹')
    fr = [re.sub(r'\s+', ' ', x).strip() for x in t.split('\n')]
    return [x for x in fr if len(x) > 1 and not re.fullmatch(r'[\W\d]+', x)], attr
for m, tav in COPPIE.items():
    d = json.load(open(os.path.join(QUI, 'schema', tav + '.json'), encoding='utf-8'))
    testo = ' '.join(r['testo'] for r in d['righe'])
    attr_tav = open(os.path.join(QUI, 'tavole', tav + '.dc.html'), encoding='utf-8').read()
    fr, attr = frammenti(m)
    persi = [x for x in dict.fromkeys(fr) if x not in testo]
    persi_attr = [x for x in dict.fromkeys(attr) if x not in attr_tav]
    print('=====', m, '->', tav)
    print('  testi che la tavola non mostra:', ' | '.join(persi))
    print('  title/placeholder/aria che la tavola non ha:', ' | '.join(persi_attr))
