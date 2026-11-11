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
- dalla 1.12.2 il riepilogo live: la frase, i quattro gruppi che sommano al
  totale, una riga per stanza con turni e visite come nel JSON, la linea di
  adesso, le notifiche nascoste, il telefono senza scorrimento laterale e il
  modo schermo; il riepilogo del periodo: i gruppi che sommano, i periodi
  pronti, la freccia, l'Excel; nessun errore JavaScript.
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
    ok('nel gruppo: Pianificazione della settimana, Programmazione del mese, Riepilogo live, Riepilogo del periodo, Esportazioni',
       len(voci) == 5 and 'Pianificazione' in voci[0] and 'Programmazione' in voci[1] and 'Riepilogo live' in voci[2] and
       'Riepilogo del periodo' in voci[3] and 'Esportazioni in Excel' in voci[4], voci)

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
    ok('«Stampa e scarica»: matrice, settimana tipo, sala, ambulatori e sala, programmazione, tutte le esportazioni, stampa',
       len(voci) == 7 and 'La matrice in Excel' in voci[0] and 'settimana tipo' in voci[1] and 'sala operatoria in Excel' in voci[2]
       and 'Ambulatori e sala' in voci[3] and 'Programmazione del mese' in voci[4] and 'Tutte le esportazioni' in voci[5]
       and 'Stampa' in voci[6], voci)
    pg.locator('.gruppo-comandi .apri-gruppo').click()
    with pg.expect_download() as scaricato:
        pg.locator('.gruppo-comandi .tendina a', has_text='Ambulatori e sala in Excel').click()
    ok('ambulatori e sala della settimana in un file solo',
       scaricato.value.suggested_filename == 'ambulatori-e-sala-settimana-%s.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)
    pg.locator('.gruppo-comandi .apri-gruppo').click()
    with pg.expect_download() as scaricato:
        pg.locator('.gruppo-comandi .tendina a', has_text='La matrice in Excel').click()
    ok('la matrice in Excel si scarica con il nome della settimana',
       scaricato.value.suggested_filename == 'matrice-ambulatori-%s.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)
    pg.locator('.gruppo-comandi .apri-gruppo').click()
    with pg.expect_download() as scaricato:
        pg.locator('.gruppo-comandi .tendina a', has_text='settimana tipo').click()
    ok('la settimana tipo in Excel', scaricato.value.suggested_filename == 'matrice-ambulatori-%s-settimana-tipo.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)

    # 1.12.3: la sala operatoria in fondo alla matrice, solo da guardare (la settimana di oggi ha interventi)
    pg.goto(B + '/ambulatori/settimana/%s?struttura=1' % OGGI.isoformat())
    pg.wait_for_selector('#matrice-ambulatori')
    parte = pg.locator('#matrice-ambulatori tbody.parte-sala')
    sale_viste = parte.locator('th.stanza-sett').all_inner_texts() if parte.count() else []
    ok('la sala operatoria in fondo alla matrice, con le due sale dei dati di prova',
       parte.count() == 1 and sale_viste == ['Sala A', 'Sala B'], sale_viste)
    ok('nella sala niente «+» e niente «×»: si programma dalla pagina Sala',
       parte.locator('details.metti').count() == 0 and parte.locator('form.togli-turno').count() == 0)
    link = parte.locator('a.interventi-sala')
    ok('gli interventi della settimana portano alla pagina Sala del giorno',
       link.count() >= 1 and '/sala/' in (link.first.get_attribute('href') or ''), link.count())
    ok('le sale non sono fra le stanze degli ambulatori',
       pg.locator('#matrice-ambulatori tbody:not(.parte-sala) th.stanza-sett', has_text='Sala A').count() == 0)
    larga = pg.evaluate("() => document.querySelector('tbody.parte-sala th.titolo-sala').colSpan")
    ok('il titolo della sala prende tutta la riga', larga == 1 + 2 * len(pg.locator('#matrice-ambulatori thead tr').nth(0).locator('th').all()) - 2,
       larga)

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
    # 1.12.3: la sala dopo le specialità e nel calendario, con la colonna degli interventi
    sala_mese = pg.locator('#programmazione-ambulatori tr.riga-sala')
    ok('la programmazione ha la sala operatoria dopo le specialità', sala_mese.count() >= 2 and
       'Sala operatoria' in sala_mese.first.inner_text(), sala_mese.count())
    ok('il calendario ha la colonna degli interventi e le righe della sala',
       'Interventi' in pg.locator('details.calendario-mese table tr').first.inner_text()
       and pg.locator('details.calendario-mese tr.riga-sala').count() >= 1)
    pg.locator('[data-guida="programmazione-altre"] .apri-gruppo').click()
    altre = pg.locator('[data-guida="programmazione-altre"] .tendina a').all_inner_texts()
    ok('«Altre esportazioni» del mese: la sala, tutto insieme, la pagina delle esportazioni',
       len(altre) == 3 and 'sala operatoria del mese' in altre[0] and 'Ambulatori e sala' in altre[1] and 'Tutte le esportazioni' in altre[2], altre)
    with pg.expect_download() as scaricato:
        pg.locator('[data-guida="programmazione-altre"] .tendina a', has_text='La sala operatoria del mese').click()
    # sul telefono la tendina aperta resta dentro lo schermo (prima usciva a sinistra)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.reload()
    pg.locator('[data-guida="programmazione-altre"] .apri-gruppo').click()
    box = pg.locator('[data-guida="programmazione-altre"] .tendina').bounding_box()
    ok('sul telefono la tendina «Altre esportazioni» resta dentro lo schermo',
       box and box['x'] >= 0 and box['x'] + box['width'] <= 390, box)
    pg.set_viewport_size({'width': 1366, 'height': 820})
    ok('la sala del mese in Excel', scaricato.value.suggested_filename == 'sala-operatoria-mese-%s.xlsx' % LUN.strftime('%Y-%m'),
       scaricato.value.suggested_filename)

    # 1.12.3: la pagina delle esportazioni: nove pulsanti, la data scelta, un file vero
    pg.goto(B + '/esportazioni?struttura=1&data=%s' % OGGI.isoformat())
    pg.wait_for_selector('#esportazioni')
    pulsanti = pg.locator('#esportazioni a.bottone')
    ok('esportazioni: nove pulsanti, giorno, settimana e mese per ambulatori, sala e tutto', pulsanti.count() == 9, pulsanti.count())
    righe_esp = pg.locator('#esportazioni tr[data-periodo]').evaluate_all("trs => trs.map(t => t.dataset.periodo)")
    ok('esportazioni: le righe sono giorno, settimana e mese', righe_esp == ['giorno', 'settimana', 'mese'], righe_esp)
    with pg.expect_download() as scaricato:
        pg.locator('#esportazioni tr[data-periodo="giorno"] a.bottone').nth(1).click()
    ok('esportazioni: la sala del giorno si scarica con il suo nome',
       scaricato.value.suggested_filename == 'sala-operatoria-giorno-%s.xlsx' % OGGI.isoformat(), scaricato.value.suggested_filename)
    pg.fill('form.scelta-data input[name="data"]', (OGGI + timedelta(days=40)).isoformat())
    pg.locator('form.scelta-data button').click()
    pg.wait_for_selector('#esportazioni')
    ok('esportazioni: cambiando la data cambiano i pulsanti',
       ((OGGI + timedelta(days=40)).isoformat() + '.xlsx') in (pulsanti.first.get_attribute('href') or ''), pulsanti.first.get_attribute('href'))
    attivo = pg.locator('nav.menu .gruppo.attivo .apri-gruppo').first
    ok('esportazioni: il gruppo Ambulatori è attivo', attivo.count() and 'Ambulatori' in attivo.inner_text())
    pg.set_viewport_size({'width': 390, 'height': 800})
    largo = pg.evaluate('document.documentElement.scrollWidth')
    ok('esportazioni: sul telefono niente scorrimento laterale', largo <= 392, largo)
    pg.set_viewport_size({'width': 1366, 'height': 820})

    # 1.12.2: il riepilogo live piu' chiaro, a qualsiasi ora la prova giri
    import json as _json
    import urllib.request as _url
    dati = _json.loads(_url.urlopen(B + '/riepilogo-live.json?struttura=1', timeout=30).read().decode('utf-8'))
    # le notifiche gia' viste nelle pagine di prima non contano: si azzera la memoria e si guardano le richieste
    pg.evaluate("sessionStorage.removeItem('notifiche-viste')")
    richieste_notifiche = []
    pg.on('request', lambda q: richieste_notifiche.append(q.url) if '/notifiche' in q.url else None)
    pg.goto(B + '/riepilogo-live?struttura=1')
    pg.wait_for_selector('#riepilogo-live .frase-live')
    ok('riepilogo live: la frase in cima, in parole', len(pg.inner_text('.frase-live').strip()) > 20, pg.inner_text('.frase-live'))
    conti = pg.locator('.conti-oggi-live li b').all_inner_texts()
    ok('riepilogo live: fatti, in corso, da segnare e da fare sommano agli appuntamenti di oggi',
       len(conti) == 5 and sum(int(x) for x in conti[1:]) == int(conti[0]) == dati['oggi']['totale'], conti)
    righe = pg.locator('.linea-live .riga-live:not(.asse-live)')
    frasi = [x.strip() for x in pg.locator('.linea-live .riga-live .stato-live').all_inner_texts()]
    ok('riepilogo live: una riga per stanza, ognuna con la frase del JSON', righe.count() == len(dati['stanze']) and
       frasi == [x['frase'] for x in dati['stanze']], (frasi, [x['frase'] for x in dati['stanze']]))
    ok('riepilogo live: i turni sulla linea del tempo come nel JSON',
       pg.locator('.pista-live .turno-live').count() == sum(len(x['linea']['turni']) for x in dati['stanze']) and
       pg.locator('.pista-live .visita-live').count() == sum(len(x['linea']['visite']) for x in dati['stanze']))
    linee = pg.locator('.pista-live .adesso-live').count()
    ok('riepilogo live: la linea di adesso in ogni stanza, o in nessuna fuori orario',
       linee == (len(dati['stanze']) if dati['asse']['adesso'] is not None else 0), linee)
    ok('riepilogo live: le notifiche non coprono la pagina', pg.evaluate("getComputedStyle(document.getElementById('notifiche')).display") == 'none')
    pg.wait_for_timeout(1500)
    ok('riepilogo live: le notifiche non si chiedono nemmeno (non risultano viste nelle altre pagine)',
       not richieste_notifiche and pg.evaluate("sessionStorage.getItem('notifiche-viste')") in (None, '{}') and
       pg.locator('#notifiche .notifica').count() == 0, (richieste_notifiche, pg.evaluate("sessionStorage.getItem('notifiche-viste')")))
    misura = pg.evaluate("(() => { const r = document.querySelector('.legenda-live .gr-turno').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })()")
    ok('riepilogo live: i quadratini della legenda sono tutti piccoli (nessuna classe di altre pagine)', misura[0] <= 16, misura)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(300)
    ok('riepilogo live: sul telefono la pagina non scorre di lato',
       pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), pg.evaluate('document.documentElement.scrollWidth'))
    pg.set_viewport_size({'width': 1366, 'height': 820})
    pg.goto(B + '/riepilogo-live?struttura=1&schermo=1')
    pg.wait_for_selector('#riepilogo-live .linea-live')
    ok('riepilogo live: il modo schermo senza menu, con la linea del tempo', pg.locator('nav.menu').count() == 0 and
       pg.locator('.linea-live .riga-live').count() == len(dati['stanze']) + 1)

    # 1.12.2: il riepilogo del periodo
    pg.goto(B + '/ambulatori/riepilogo?struttura=1&periodo=settimana')
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: la frase e i cinque gruppi che sommano al totale',
       (lambda c: len(c) == 6 and sum(int(x) for x in c[1:]) == int(c[0]))(pg.locator('.conti-oggi-live li b').all_inner_texts()),
       pg.locator('.conti-oggi-live li b').all_inner_texts())
    ok('riepilogo del periodo: «Questa settimana» scelto, sette giorni nella tabella',
       pg.locator('.periodi-pronti .bottone.attivo').inner_text() == 'Questa settimana' and
       pg.locator('.giorni-periodo tbody tr').count() == 7, pg.locator('.giorni-periodo tbody tr').count())
    pg.locator('.periodi-pronti a', has_text='Oggi').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: «Oggi» un giorno solo, senza la tabella dei giorni',
       pg.locator('.giorni-periodo').count() == 0 and 'periodo=oggi' in pg.url, pg.url)
    pg.locator('a.passo[data-tasto="precedente"]').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: la freccia va al giorno prima', ('da=%s' % (OGGI - timedelta(days=1)).isoformat()) in pg.url, pg.url)
    with pg.expect_download() as scarico:
        pg.click('[data-guida="periodo-excel"]')
    ok('riepilogo del periodo: l\'Excel si scarica con il suo nome',
       scarico.value.suggested_filename == 'riepilogo-ambulatori-%s.xlsx' % (OGGI - timedelta(days=1)).isoformat(),
       scarico.value.suggested_filename)
    attivo = pg.locator('nav.menu .gruppo.attivo .apri-gruppo').first
    ok('riepilogo del periodo: il gruppo Ambulatori è attivo', attivo.count() and 'Ambulatori' in attivo.inner_text())
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(300)
    ok('riepilogo del periodo: sul telefono la pagina non scorre di lato (scorrono le tabelle)',
       pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), pg.evaluate('document.documentElement.scrollWidth'))
    pg.set_viewport_size({'width': 1366, 'height': 820})
    # 1.12.6: la sala operatoria nel riepilogo del periodo e le statistiche dentro la dashboard
    pg.goto(B + '/ambulatori/riepilogo?struttura=1&periodo=settimana')
    pg.wait_for_selector('.pagina-periodo .frase-live')
    pg.locator('.parti-periodo a', has_text='Sala operatoria').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: la scheda Sala operatoria con sale e chirurghi',
       'parte=sala' in pg.url and 'Le sale' in pg.inner_text('.pagina-periodo') and 'I chirurghi' in pg.inner_text('.pagina-periodo'),
       pg.url)
    with pg.expect_download() as scarico:
        pg.click('[data-guida="periodo-excel"]')
    ok('riepilogo del periodo: l\'Excel della sala si scarica con il suo nome',
       scarico.value.suggested_filename.startswith('riepilogo-sala-operatoria-'), scarico.value.suggested_filename)
    pg.goto(B + '/riepilogo-live?struttura=1&schermo=1')
    pg.wait_for_selector('#riepilogo-live .frase-live')
    pg.click('[data-guida="live-statistiche"]')
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('dashboard: «Statistiche» apre il riepilogo del periodo senza menu, nel modo schermo',
       '/riepilogo-live/statistiche' in pg.url and 'schermo=1' in pg.url and pg.locator('nav.menu').count() == 0, pg.url)
    pg.locator('.parti-periodo a', has_text='Sala operatoria').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    pg.locator('.periodi-pronti a', has_text='Questo mese').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('dashboard: si sceglie la sala e il mese, restando nella dashboard',
       '/riepilogo-live/statistiche' in pg.url and 'parte=sala' in pg.url and 'periodo=mese' in pg.url and 'schermo=1' in pg.url, pg.url)
    fuori = [h for h in pg.eval_on_selector_all('a[href]', 'els => els.map(e => e.getAttribute("href"))')
             if not h.startswith('/riepilogo-live')]
    ok('dashboard: nelle statistiche nessun collegamento fuori dalla dashboard e niente Excel', not fuori, fuori[:5])
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(300)
    ok('dashboard: le statistiche sul telefono non scorrono di lato',
       pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), pg.evaluate('document.documentElement.scrollWidth'))
    pg.set_viewport_size({'width': 1366, 'height': 820})
    pg.click('[data-guida="statistiche-torna"]')
    pg.wait_for_selector('#riepilogo-live .frase-live')
    ok('dashboard: «Torna al riepilogo live» resta nel modo schermo', '/riepilogo-live' in pg.url and 'schermo=1' in pg.url, pg.url)
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()

print('%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
