# -*- coding: utf-8 -*-
"""Prove della guida e del menu a gruppi: ogni articolo si apre, ha la sua
immagine e il suo video, i suoi passi in JSON per la guida sullo schermo, e porta a una
pagina che esiste; il menu contiene ancora tutte le pagine di prima; la
ricerca nella guida trova quello che deve; la versione da stampare contiene
tutto. La prova nel browser (fumetti, riflettore, tasti) e' in
prove_guida_browser.py."""
import json
import os
import re
import shutil
import sys
import traceback
from datetime import date

import servizi
import viste
import guida
import app as A
from modelli import crea_sessione, Operatore, Risorsa

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_guida_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti = []


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', nome, traceback.format_exc().strip().splitlines()[-1]))


def mondo():
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'g%d.db' % len(esiti)))
    s = S()
    servizi.prepara_primo_avvio(s)
    s.add(Operatore(cognome='Rossi'))
    s.add(Risorsa(nome='Sala A', tipo='SALA_OPERATORIA', struttura_id=1, ordine=9))
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, A.app.test_client()


def html(r):
    return r.get_data(as_text=True)


def gu_articoli():
    S, C = mondo()
    regole = {r.endpoint for r in A.app.url_map.iter_rules()}
    slug = set()
    for a in guida.ARTICOLI:
        assert a['slug'] not in slug, 'doppione: %s' % a['slug']
        slug.add(a['slug'])
        assert re.fullmatch(r'[a-z0-9-]{1,40}', a['slug']), a['slug']
        assert a['gruppo'] in guida.GRUPPI, a['gruppo']
        assert a['endpoint'] in regole, '%s: pagina %s inesistente' % (a['slug'], a['endpoint'])
        assert a['apri'][0] in regole, '%s: %s' % (a['slug'], a['apri'])
        r = C.get('/aiuto/' + a['slug'])
        t = html(r)
        assert r.status_code == 200 and a['titolo'] in t.replace('&#39;', "'"), a['slug']
        assert t.count('<li') >= len(a['passi']), '%s: passi mancanti' % a['slug']
        assert os.path.exists(os.path.join(CARTELLA, 'static', 'guida', a['slug'] + '.png')), 'immagine mancante: ' + a['slug']
        assert '/static/guida/%s.png' % a['slug'] in t, 'immagine non mostrata: ' + a['slug']
        assert os.path.exists(os.path.join(CARTELLA, 'static', 'video', a['slug'] + '.webm')), 'video mancante: ' + a['slug']
        assert 'href="/static/video/%s.webm" data-video=' % a['slug'] in t, 'video non mostrato: ' + a['slug']
        j = C.get('/aiuto/%s/passi.json' % a['slug'])
        d = json.loads(j.get_data(as_text=True))
        assert j.status_code == 200 and d['passi'] == a['passi'], a['slug']
        assert '<' not in j.get_data(as_text=True), 'JSON non protetto'
        # "Mostrami sullo schermo" porta alla pagina giusta con la guida
        if any('sel' in p for p in a['passi']):
            m = re.search(r'href="([^"]+)" data-guida-mostra', t)
            assert m, '%s: manca Mostrami sullo schermo' % a['slug']
            dest = m.group(1).replace('&amp;', '&')
            rr = C.get(dest)
            assert rr.status_code == 200, '%s -> %s: %d' % (a['slug'], dest, rr.status_code)
            if a['endpoint'] == a['apri'][0]:
                assert 'guida=%s' % a['slug'] in dest, dest
        for p in a['passi']:
            assert p['titolo'] and len(p['testo']) > 15, (a['slug'], p)
    return '%d articoli' % len(guida.ARTICOLI)


def gu_indice_ricerca_stampa():
    S, C = mondo()
    t = html(C.get('/aiuto'))
    assert all(a['titolo'].replace("'", '&#39;') in t for a in guida.ARTICOLI), 'indice incompleto'
    for q, atteso, escluso in (('backup', 'Backup e ripristino', 'Prenotare un appuntamento'),
                               ('WHATSAPP', 'Le conferme del giorno dopo', 'Backup e ripristino'),
                               ('checklist', 'Checklist pre-operatoria', 'Importare dai file Excel')):
        t = html(C.get('/aiuto?q=' + q))
        assert atteso in t and escluso not in t, q
    t = html(C.get('/aiuto?q=zzzzqqq'))
    assert 'Nessuna guida parla' in t
    for sporco in ('<script>alert(1)</script>', '%00', 'x' * 500, "'\""):
        r = C.get('/aiuto', query_string={'q': sporco})
        assert r.status_code == 200 and '<script>alert' not in html(r)
    assert C.get('/aiuto/nonesiste').status_code == 404
    assert C.get('/aiuto/nonesiste/passi.json').status_code == 404
    assert C.get('/aiuto/../app.py').status_code == 404
    # nessun articolo puo' chiamarsi come una pagina della guida
    assert not {a['slug'] for a in guida.ARTICOLI} & {'stampa', 'novita'}, 'slug che coincide con /aiuto/stampa o /aiuto/novita'
    t = html(C.get('/aiuto/stampa'))
    assert all(a['titolo'].replace("'", '&#39;') in t for a in guida.ARTICOLI) and 'size: A4 portrait' in t
    assert t.count('class="articolo-stampa"') == len(guida.ARTICOLI)


def gu_menu():
    S, C = mondo()
    t = html(C.get('/giorno/%s?struttura=1' % date.today().isoformat()))
    menu = t.split('<nav class="menu"')[1].split('</nav>')[0]
    for voce in ('Oggi', 'Giorno', 'Settimana', 'Mese', 'Sala', 'Pazienti', 'Segreteria', 'Conferme', 'Da confermare',
                 'Chiusura della giornata', 'Da fare', "Lista d'attesa", 'Prima disponibilità', 'Elenco del giorno',
                 'Cassa', 'Statistiche', 'Aiuto', 'Come fare…', 'Novità', 'Configura', 'Anagrafiche', 'Importa da Excel',
                 'Impostazioni', 'Aggiornamenti'):
        assert voce in menu, 'manca nel menu: ' + voce
    for tasto in ('g', 'e', 'c'):
        assert 'data-tasto="%s"' % tasto in menu, 'tasto rapido perso: ' + tasto
    # la voce di gruppo si evidenzia nelle sue pagine
    for u, gruppo in (('/conferme', 'menu-segreteria'), ('/cose-da-fare', 'menu-segreteria'), ('/anagrafiche', 'menu-configura'),
                      ('/impostazioni', 'menu-configura'), ('/importa', 'menu-configura'), ('/aiuto', 'menu-aiuto'),
                      ('/aggiornamenti', 'menu-configura'), ('/aiuto/novita', 'menu-aiuto')):
        t = html(C.get(u))
        assert re.search(r'class="gruppo[^"]*attivo"[^>]*data-guida="%s"' % gruppo, t), '%s: gruppo non evidenziato' % u
    # la barra del giorno: Stampa e scarica raccoglie le stampe
    t = html(C.get('/giorno/%s?struttura=1' % date.today().isoformat()))
    blocco = t.split('data-guida="giorno-stampa"')[1].split('</div>\n    </div>')[0]
    for voce in ('Stampa del giorno', 'Agenda dei medici', 'Scarica in Excel'):
        assert voce in blocco, voce
    # le guide della pagina arrivano alla guida sullo schermo
    m = re.search(r'data-guide="([^"]*)"', t)
    guide = json.loads(m.group(1).replace('&#34;', '"').replace('&quot;', '"').replace('&#39;', "'"))
    # (dalla 1.10 anche le fasce di ogni ambulatorio, ma solo dove un turno ha le sue fasce)
    assert {g['slug'] for g in guide} == {'fasce-turno', 'stampare-giornata', 'griglia'} and \
        {g['condizione'] for g in guide if g['slug'] == 'fasce-turno'} == {'thead .fasce-turno'}, guide
    t = html(C.get('/appuntamento?data=%s' % date.today().isoformat()))
    m = re.search(r'data-guide="([^"]*)"', t)
    guide = json.loads(m.group(1).replace('&#34;', '"').replace('&quot;', '"').replace('&#39;', "'"))
    assert {g['slug'] for g in guide} == {'prenotare', 'stato', 'spostare'} and \
        {g['condizione'] for g in guide if g['slug'] == 'prenotare'} == {'#cerca_paziente'}, guide


prova('ogni articolo: pagina, immagine, passi per lo schermo, Mostrami che porta alla pagina giusta', gu_articoli)
prova('indice, ricerca nella guida (anche sporca), pagine inesistenti, versione da stampare', gu_indice_ricerca_stampa)
prova('menu a gruppi: tutte le pagine di prima, tasti rapidi, gruppo evidenziato, guide della pagina', gu_menu)

if __name__ == '__main__':
    for e in esiti:
        print('%-6s %s%s' % (e[0], e[1], ('\n       ' + e[2]) if e[0] != 'OK' or os.environ.get('DETTAGLIO') else ''))
    rotte = [e for e in esiti if e[0] != 'OK']
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
