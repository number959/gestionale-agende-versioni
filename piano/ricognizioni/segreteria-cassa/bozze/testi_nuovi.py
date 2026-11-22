# -*- coding: utf-8 -*-
"""Per ogni tavola: i testi visibili del contenuto che non si trovano nei modelli e nel codice di oggi
(candidati «testi nuovi»), tolti i dati (nomi, numeri, date, importi). Solo lettura del repository.
    python3 -I testi_nuovi.py"""
import json
import os
import re

QUI = os.path.dirname(os.path.abspath(__file__))
G = '/home/user/gestionale-agende-versioni/gestionale'
MODELLI = {
    'Seg1-Conferme': ['conferme.html', '_stato.html'],
    'Seg2-DaConfermare': ['da_confermare.html'],
    'Seg3-Chiusura': ['chiusura.html'],
    'Seg4-DaFare': ['cose_da_fare.html'],
    'Seg5-Attesa': ['attesa.html'],
    'Seg6-Disponibilita': ['disponibilita.html'],
    'Cassa1-Giorno': ['cassa.html'],
    'Cassa2-Mese': ['cassa_mese.html'],
    'Cassa3-Listino': ['listino.html'],
    'Cassa4-Tariffari': ['tariffari.html'],
}
CODICE = ['modelli.py', 'segreteria.py', 'cassa.py', 'tariffari.py', 'viste.py', 'servizi.py', 'invii.py', 'app.py']


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def testo_modello(nome):
    t = open(os.path.join(G, 'templates', nome), encoding='utf-8').read()
    t = re.sub(r'\{#.*?#\}', ' ', t, flags=re.S)
    t = re.sub(r'\{%.*?%\}', '\n', t, flags=re.S)
    t = re.sub(r'\{\{.*?\}\}', '\n', t, flags=re.S)
    t = re.sub(r'<[^>]+>', '\n', t)
    return norm(t.replace('&rsaquo;', '›').replace('&lsaquo;', '‹'))


tutto_codice = ' '.join(norm(open(os.path.join(G, f), encoding='utf-8').read()) for f in CODICE)
tutti_modelli = ' '.join(testo_modello(f) for f in os.listdir(os.path.join(G, 'templates')) if f.endswith('.html'))
DATI = re.compile(r'^[\d\s.,:/€–\-()]+$|^\d|€$|^(lun|mar|mer|gio|ven|sab|dom)\b|@|^\+|\d{2}/\d{2}')
spec = open(os.path.join(QUI, '..', 'anteprime', 'SPEC-PSC.md'), encoding='utf-8').read()
nomi = set(re.findall(r'\b([A-Z][a-zà-ù]+ [A-Z][a-zà-ù]+)\b', spec))

for tavola, modelli in MODELLI.items():
    d = json.load(open(os.path.join(QUI, 'schema', tavola + '.json'), encoding='utf-8'))
    propri = ' '.join(testo_modello(m) for m in modelli)
    nuovi, altrove = [], []
    visti = set()
    for r in d['righe']:
        t = r['testo']
        if t in visti or DATI.search(t) or t in nomi or len(t) < 2:
            continue
        visti.add(t)
        if t in propri:
            continue
        if t in tutto_codice or t in tutti_modelli:
            altrove.append(t)
        else:
            nuovi.append(t)
    print('=====', tavola)
    print('  NON nei modelli né nel codice:', ' | '.join(nuovi))
    print('  solo altrove (codice o altri modelli):', ' | '.join(altrove))
