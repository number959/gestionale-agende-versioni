# -*- coding: utf-8 -*-
"""Prove nel browser della 1.12 (gli ambulatori), su un gestionale gia'
avviato con i dati di prova (strumenti/demo.py):
    python prove_112_browser.py http://127.0.0.1:5001
- la pianificazione della settimana prossima: la matrice con due righe di
  intestazione (giorni, mezze giornate), Lippiello in Ambulatorio 1 tutte le
  mattine, celle DISPONIBILI;
- dal «+» di una cella libera si mette Galasso: compare il suo nome; dalla
  «x» (con la conferma) si toglie: la cella torna DISPONIBILE, e i dati di
  prova restano come prima;
- «Stampa e scarica»: i quattro collegamenti, la matrice in Excel scaricata
  con il suo nome;
- la programmazione del mese: la tabella e l'Excel scaricato con il suo nome;
- il gruppo Ambulatori del menu e' segnato attivo in tutte e due le pagine;
  nessun errore JavaScript.
Mette e toglie un turno sui dati di prova: alla fine sono come prima."""
import os
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000').rstrip('/')
esiti = []
OGGI = date.today()
LUN = OGGI - timedelta(days=OGGI.weekday()) + timedelta(days=7)        # il lunedi della settimana prossima: tutta nel futuro
GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT', accept_downloads=True)
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                        "localStorage.setItem('gestionale-tema', 'chiaro'); } catch (e) {}")
    pg = ctx.new_page()
    err, conferme = [], []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
    pg.on('dialog', lambda d: (conferme.append(d.message), d.accept()))

    settimana = B + '/ambulatori/settimana/%s?struttura=1' % LUN.isoformat()
    pg.goto(settimana)
    pg.wait_for_selector('#matrice-ambulatori')
    testa = pg.locator('#matrice-ambulatori thead tr')
    ok('la matrice ha due righe di intestazione', testa.count() == 2, testa.count())
    giorni = [x.strip().split('\n')[0] for x in testa.nth(0).locator('th').all_inner_texts()][1:]
    ok('i giorni di apertura, da lunedì a sabato, con la data',
       len(giorni) == 6 and all(g.startswith('%s %d/%d' % (GIORNI[k], (LUN + timedelta(days=k)).day, (LUN + timedelta(days=k)).month))
                                for k, g in enumerate(giorni)), giorni)
    meta = testa.nth(1).locator('th').all_inner_texts()
    ok('sotto ogni giorno mattina e pomeriggio (08:00–14:00, 14:00–20:00)',
       len(meta) == 12 and meta[0] == '08:00–14:00' and meta[1] == '14:00–20:00' and len(set(meta)) == 2, meta[:4])
    ok('almeno una cella DISPONIBILE in verde', pg.locator('#matrice-ambulatori td.libera .disponibile').count() >= 1)
    riga = pg.locator('#matrice-ambulatori tbody tr', has=pg.locator('th.stanza-sett', has_text='Ambulatorio 1'))
    mattine = riga.locator('td').evaluate_all("tds => tds.filter((td, i) => i % 2 === 0).map(td => td.textContent.replace(/\\s+/g, ' ').trim())")
    ok('Lippiello in Ambulatorio 1 tutte le mattine (dati di prova)', len(mattine) == 6 and all('Lippiello' in x and '08:00–14:00' in x for x in mattine), mattine[:2])
    pomeriggi = riga.locator('td').evaluate_all("tds => tds.filter((td, i) => i % 2 === 1).map(td => td.className)")
    ok('i pomeriggi di Ambulatorio 1 liberi', len(pomeriggi) == 6 and all('libera' in x for x in pomeriggi), pomeriggi)
    attivo = pg.locator('nav.menu .gruppo.attivo .apri-gruppo').first
    ok('il menu: il gruppo Ambulatori è segnato attivo', attivo.count() and 'Ambulatori' in attivo.inner_text(), attivo.inner_text() if attivo.count() else 'nessun gruppo attivo')
    voci = pg.locator('nav.menu .gruppo.attivo .tendina a').all_inner_texts()
    ok('nel gruppo: Pianificazione della settimana, Programmazione del mese e Riepilogo live', len(voci) == 3 and 'Pianificazione' in voci[0] and 'Programmazione' in voci[1] and 'Riepilogo live' in voci[2], voci)

    # Metti: una cella libera, il «+», Galasso, Metti
    cella = pg.locator('#matrice-ambulatori td.libera:has(details.metti)').first
    chiave = cella.get_attribute('data-cella')
    ok('una cella libera con il «+»', chiave, chiave)
    cella.locator('details.metti summary').click()
    modulo = cella.locator('details.metti form')
    modulo.wait_for(state='visible')
    ok('il modulo del «+» si apre con stanza e giorno', modulo.is_visible() and chiave.split('_')[1] == modulo.locator('input[name=data]').input_value(),
       modulo.locator('input[name=data]').input_value())
    ore = (modulo.locator('input[name=ora_inizio]').input_value(), modulo.locator('input[name=ora_fine]').input_value())
    ok('le ore proposte sono la mezza giornata intera', ore in (('08:00', '14:00'), ('14:00', '20:00')), ore)
    modulo.locator('select[name=operatore]').select_option(label='Galasso')
    with pg.expect_navigation():
        modulo.locator('button[type=submit]').click()
    avviso = pg.locator('.avvisi').inner_text() if pg.locator('.avvisi').count() else ''
    ok('«Turno salvato» con medico, stanza e ore', 'Turno salvato: Galasso' in avviso and 'ogni %s' % GIORNI[date.fromisoformat(chiave.split('_')[1]).weekday()] in avviso, avviso[:200])
    cella = pg.locator('td[data-cella="%s"]' % chiave)
    nomi = cella.locator('.turno-sett a').all_inner_texts()
    ok('Galasso compare nella cella, che non è più libera', nomi == ['Galasso'] and 'occupata' in (cella.get_attribute('class') or ''), (nomi, cella.get_attribute('class')))
    ok('il nome apre il turno e torna qui', '/anagrafiche/turni/' in (cella.locator('.turno-sett a').first.get_attribute('href') or '')
       and 'torna=' in (cella.locator('.turno-sett a').first.get_attribute('href') or ''), cella.locator('.turno-sett a').first.get_attribute('href'))

    # Togli: la «x» chiede conferma, poi la cella torna disponibile
    with pg.expect_navigation():
        cella.locator('form.togli-turno button').click()
    ok('la «x» chiede conferma', conferme and 'Togliere Galasso' in conferme[-1] and 'da questa settimana in poi' in conferme[-1], conferme[-1:] or 'nessuna conferma')
    avviso = pg.locator('.avvisi').inner_text() if pg.locator('.avvisi').count() else ''
    ok('«Turno tolto»', 'Turno tolto: Galasso' in avviso, avviso[:200])
    cella = pg.locator('td[data-cella="%s"]' % chiave)
    ok('la cella è di nuovo DISPONIBILE (i dati di prova come prima)', cella.locator('.disponibile').count() == 1 and 'libera' in (cella.get_attribute('class') or '')
       and cella.locator('.turno-sett').count() == 0, cella.get_attribute('class'))

    # Stampa e scarica
    voci = pg.locator('.gruppo-comandi .tendina a').all_inner_texts()
    ok('«Stampa e scarica»: matrice, settimana tipo, programmazione del mese, stampa',
       len(voci) == 4 and 'La matrice in Excel' in voci[0] and 'settimana tipo' in voci[1] and 'Programmazione del mese' in voci[2] and 'Stampa' in voci[3], voci)
    pg.locator('.gruppo-comandi .apri-gruppo').click()
    with pg.expect_download() as scaricato:
        pg.locator('.gruppo-comandi .tendina a', has_text='La matrice in Excel').click()
    ok('la matrice in Excel si scarica con il nome della settimana',
       scaricato.value.suggested_filename == 'matrice-ambulatori-%s.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)
    pg.locator('.gruppo-comandi .apri-gruppo').click()
    with pg.expect_download() as scaricato:
        pg.locator('.gruppo-comandi .tendina a', has_text='settimana tipo').click()
    ok('la settimana tipo in Excel', scaricato.value.suggested_filename == 'matrice-ambulatori-%s-settimana-tipo.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)

    # la programmazione del mese
    pg.goto(B + '/ambulatori/mese/%s?struttura=1' % LUN.strftime('%Y-%m'))
    pg.wait_for_selector('#programmazione-ambulatori')
    righe = pg.locator('#programmazione-ambulatori tr')
    corpo = pg.locator('#programmazione-ambulatori').inner_text()
    ok('la programmazione ha le sue righe, con Lippiello tutti i giorni in Ambulatorio 1',
       righe.count() > 6 and corpo.count('Lippiello') >= 6 and 'Ambulatorio 1' in corpo, (righe.count(), corpo.count('Lippiello')))
    ok('le date del mese sono numeri separati da virgole', any(',' in x for x in pg.locator('#programmazione-ambulatori tr td:nth-child(4)').all_inner_texts()))
    attivo = pg.locator('nav.menu .gruppo.attivo .apri-gruppo').first
    ok('anche qui il gruppo Ambulatori è attivo', attivo.count() and 'Ambulatori' in attivo.inner_text())
    with pg.expect_download() as scaricato:
        pg.locator('a.bottone.primario', has_text='Scarica in Excel').click()
    ok('la programmazione in Excel si scarica con il nome del mese',
       scaricato.value.suggested_filename == 'programmazione-ambulatori-%s.xlsx' % LUN.strftime('%Y-%m'), scaricato.value.suggested_filename)
    pg.locator('details.calendario-mese summary').click()
    ok('il calendario del mese si apre', pg.locator('details.calendario-mese[open] table tr').count() > 1)
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()

print('%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
