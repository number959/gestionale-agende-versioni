# Controlla la bozza del menu contro il menu di oggi: gli indirizzi del menu di oggi (letti dal gestionale di
# prova sulla porta 5142, da una pagina della seconda struttura in un giorno che non e' oggi) devono essere
# tutti fra quelli che la bozza costruisce (menu + linguette + collegamenti nascosti), con gli stessi argomenti.
# Uso: LOCALAPPDATA=<cartella mia> PYTHONDONTWRITEBYTECODE=1 python controlla_bozza.py
import os, re, sys, urllib.request
from html.parser import HTMLParser

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = '/home/user/gestionale-agende-versioni/gestionale'
sys.path.insert(0, QUI)
import menu_bozza as M  # noqa: E402

PAGINA = '/giorno/2026-11-25?struttura=2'


class Menu(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.dentro, self.link, self.segni = 0, [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'nav' and 'menu' in (a.get('class') or '').split():
            self.dentro = 1
        elif tag == 'nav' and self.dentro:
            self.dentro += 1
        if self.dentro and tag == 'a' and a.get('href') and a['href'] != '#':
            self.link.append(a['href'])
        if self.dentro:
            for k in ('data-tasto', 'data-guida'):
                if k in a:
                    self.segni.append('%s=%s' % (k, a[k]))

    def handle_endtag(self, tag):
        if tag == 'nav' and self.dentro:
            self.dentro -= 1


html = urllib.request.urlopen('http://127.0.0.1:5142' + PAGINA).read().decode()
oggi = Menu()
oggi.feed(html)

os.chdir(REPO)
sys.path.insert(0, REPO)
import app as A  # noqa: E402
from flask import url_for  # noqa: E402

bozza, segni = [], []
with A.app.test_request_context(PAGINA):
    sid, data = 2, '2026-11-25'
    for v in M.VOCI:
        if v['endpoint']:
            bozza.append(url_for(v['endpoint'], **M.argomenti_di(v, sid, data)))
        for k in ('tasto', 'guida'):
            if v.get(k):
                segni.append('data-%s=%s' % (k, v[k]))
    for x in M.AIUTO:
        if x['endpoint']:
            bozza.append(url_for(x['endpoint']))
    for x in M.NASCOSTI:
        bozza.append(url_for(x['endpoint'], **M.argomenti_di(x, sid, data)))
        segni.append('data-tasto=%s' % x['tasto'])
    for g in M.LINGUETTE.values():
        for x in g['voci']:
            bozza.append(url_for(x['endpoint'], **M.argomenti_di(x, sid, data)))
            if x.get('guida'):
                segni.append('data-guida=%s' % x['guida'])

mancano = [u for u in oggi.link if u not in bozza]
nuovi = sorted(set(bozza) - set(oggi.link))
print('collegamenti del menu di oggi:', len(oggi.link), '- nella bozza:', len(set(bozza)))
print('del menu di oggi che la bozza non costruisce:', mancano or 'nessuno')
print('nuovi nella bozza (non nel menu di oggi):', nuovi or 'nessuno')
print('segni di oggi nel menu:', sorted(oggi.segni))
print('segni della bozza (menu+linguette+nascosti):', sorted(segni))
print('segni di oggi che la bozza non ha:', sorted(set(oggi.segni) - set(segni)) or 'nessuno')
for s in ('oggi', 'giorno', 'settimana', 'mese', 'elenco', 'sala', 'conferme', 'confermare', 'chiusura', 'cose',
          'attesa', 'disponibilita', 'pazienti', 'personale', 'ambulatori', 'programmazione', 'live',
          'riepilogo-periodo', 'esportazioni', 'dove', 'cassa', 'statistiche', 'aiuto', 'anagrafiche', 'gruppo',
          'invii', 'importa', 'impostazioni', 'aggiornamenti'):
    g = M.linguette_di(s)
    print('  sezione %-18s voce %-11s linguette %s' % (s, M.voce_accesa(s), g['etichetta'] if g else '-'))
