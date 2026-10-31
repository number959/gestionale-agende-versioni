"""Prove nel browser della 1.10 (le fasce di ogni turno), su un gestionale gia'
avviato con i dati di prova (strumenti/demo.py: il martedi la sala endoscopia ha
fasce da 15 minuti, il resto della struttura resta a 30):
    python prove_110_browser.py http://127.0.0.1:5001
- griglia del martedi: "fasce da 15'" in testa alla sala, righe tutte alte
  uguali, celle alte quanto le loro fasce (la colonscopia tre fasce, la EGDS
  due), le fasce libere della sala con la loro ora ("libero" al passaggio del
  mouse), quelle degli ambulatori come prima;
- un clic su una fascia libera apre il modulo con quell'ora, la sala e il
  medico di turno;
- la guida sullo schermo «Le fasce di ogni ambulatorio» illumina i suoi punti;
- agenda della settimana del medico, modulo del turno, tema scuro, schermo
  stretto; nessun errore JavaScript.
Non salva niente."""
import os
import re
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000').rstrip('/')
esiti = []
OGGI = date.today()
MAR = OGGI - timedelta(days=(OGGI.weekday() - 1) % 7)       # il martedi di questa settimana, come demo.py


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


# le misure della griglia: righe, colonna della sala, celle con quante righe coprono e quanto sono alte
MISURE = """() => {
  const t = document.querySelector('table.griglia');
  const corpo = t.querySelector('tbody');
  const righe = Array.from(corpo.rows);
  const intest = Array.from(t.querySelectorAll('thead th'));
  const sala = intest.findIndex(th => th.textContent.includes('Sala endoscopia'));
  // la colonna di ogni cella, contando quelle alte piu' righe che arrivano da sopra
  const prese = {}, celle = [];
  righe.forEach((tr, i) => {
    let c = 0;
    Array.from(tr.cells).forEach(td => {
      while (prese[i + ',' + c]) c++;
      for (let k = 0; k < td.rowSpan; k++) prese[(i + k) + ',' + c] = true;
      const r = td.getBoundingClientRect();
      const a = td.querySelector('a.posa');
      celle.push({riga: i, col: c, righe: td.rowSpan, classe: td.className, testo: td.textContent.trim(),
                  alta: r.height, posa: a ? a.className : '', posaAlta: a ? a.getBoundingClientRect().height : 0,
                  href: a ? a.getAttribute('href') : ''});
      c++;
    });
  });
  const altezze = righe.map(tr => tr.getBoundingClientRect().height);
  const complete = righe.every((tr, i) => Object.keys(prese).filter(k => k.startsWith(i + ',')).length === intest.length);
  return {misto: corpo.classList.contains('fasce-miste'), riga: getComputedStyle(corpo).getPropertyValue('--riga').trim(),
          testa: intest.map(th => th.textContent.replace(/\\s+/g, ' ').trim()), sala: sala, altezze: altezze,
          complete: complete, celle: celle, ore: righe.map(tr => tr.querySelector('th').textContent.trim())};
}"""


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                        "localStorage.setItem('gestionale-tema', 'chiaro'); } catch (e) {}")
    pg = ctx.new_page()
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)

    giorno = B + '/giorno/%s?struttura=1' % MAR.isoformat()
    pg.goto(giorno)
    pg.wait_for_timeout(700)
    m = pg.evaluate(MISURE)
    ok('griglia del martedi con le fasce proprie', m['misto'] and m['sala'] > 0, (m['misto'], m['sala']))
    ok("in testa alla sala: fasce da 15'", "fasce da 15'" in m['testa'][m['sala']], m['testa'][m['sala']])
    ok('le altre colonne non dicono fasce', all('fasce da' not in x for i, x in enumerate(m['testa']) if i != m['sala']))
    riga = int(re.sub(r'\D', '', m['riga']) or 0)
    # (il testo di un appuntamento sta nelle sue fasce: una fascia corta lo mette su una riga sola)
    ok('righe da 15 minuti alte 24 pixel, tutte uguali', riga == 24 and all(abs(h - riga) <= 1.01 for h in m['altezze']),
       (m['riga'], sorted(set(round(h, 1) for h in m['altezze']))))
    ok('ogni riga ha tutte le colonne', m['complete'])
    ok('ore a meta\' fascia della struttura nella prima colonna (8:15)', '08:15' in m['ore'], m['ore'][:4])
    sala = [c for c in m['celle'] if c['col'] == m['sala']]
    colo = next((c for c in sala if 'Colonscopia' in c['testo']), None)
    egds = next((c for c in sala if 'occupata' in c['classe'] and c['riga'] == m['ore'].index('09:00')), None)
    ok('colonscopia delle 8: tre fasce da 15, alta tre righe', colo and colo['righe'] == 3 and abs(colo['alta'] - 3 * riga) <= 2,
       colo and (colo['righe'], colo['alta']))
    ok('EGDS delle 9: due fasce', egds and egds['righe'] == 2, egds and egds['righe'])
    libere = [c for c in sala if 'aperta' in c['classe']]
    ok('fasce libere della sala con la loro ora', libere and all('con-ora' in c['posa'] and re.match(r'^\d\d:\d\d', c['testo'])
                                                                 for c in libere), [c['testo'] for c in libere][:4])
    ok('la prima fascia libera della sala e\' alle 8:45', libere and libere[0]['testo'].startswith('08:45'),
       libere and libere[0]['testo'])
    altre = [c for c in m['celle'] if 'aperta' in c['classe'] and c['col'] not in (0, m['sala'])]
    ok('negli ambulatori "libero", alto una fascia da 30 (due righe)',
       altre and all(c['testo'] == 'libero' and 'con-ora' not in c['posa'] and c['righe'] == 2
                     and abs(c['posaAlta'] - (2 * riga - 2)) <= 1.5 for c in altre),
       [(c['testo'], c['righe'], c['posaAlta']) for c in altre][:3])
    # "libero" compare passando con il mouse
    x = pg.locator('tbody.fasce-miste td.aperta a.posa.con-ora').first
    nascosto = x.locator('span').evaluate('e => getComputedStyle(e).display')
    x.hover()
    pg.wait_for_timeout(150)
    visibile = x.locator('span').evaluate('e => getComputedStyle(e).display')
    ok('"libero" accanto all\'ora solo al passaggio del mouse', nascosto == 'none' and visibile != 'none', (nascosto, visibile))
    # clic su una fascia libera della sala: il modulo con quell'ora
    scelta = next((c for c in libere if c['testo'].startswith('09:30')), libere[0] if libere else None)
    pg.goto(B + scelta['href'])
    pg.wait_for_timeout(600)
    medico = pg.evaluate("(() => { const s = document.querySelector('#operatore'); return s ? s.options[s.selectedIndex].text : ''; })()")
    stanza = pg.evaluate("(() => { const s = document.querySelector('#risorsa'); return s ? s.options[s.selectedIndex].text : ''; })()")
    ok('il clic apre il modulo con l\'ora della fascia, la sala e il medico di turno',
       pg.input_value('#ora') == scelta['testo'][:5] and 'Sala endoscopia' in stanza and 'Galasso' in medico,
       (pg.input_value('#ora'), scelta['testo'][:5], stanza, medico))

    # la guida sullo schermo: ogni passo con un punto da illuminare lo trova
    pg.goto(giorno + '&guida=fasce-turno')
    pg.wait_for_timeout(900)
    passi, trovati, mancati = 0, 0, []
    while pg.locator('.giro-fumetto').count() and passi < 12:
        titolo = pg.locator('.giro-fumetto h3').inner_text().strip()
        centro = pg.evaluate("document.querySelector('.giro-riflettore').classList.contains('al-centro')")
        passi += 1
        if titolo in ('Nella griglia', 'Le fasce libere', 'Fasce intere'):
            if centro:
                mancati.append(titolo)
            else:
                trovati += 1
        pg.keyboard.press('ArrowRight')
        pg.wait_for_timeout(200)
    ok('la guida «Le fasce di ogni ambulatorio» illumina i suoi tre punti', passi == 5 and trovati == 3 and not mancati,
       (passi, trovati, mancati))

    # l'agenda della settimana del medico
    pg.goto(B + '/settimana/%s?struttura=1' % MAR.isoformat())
    pg.wait_for_timeout(400)
    gid = pg.evaluate("(() => { const o = Array.from(document.querySelectorAll('select[name=medico] option')).find(o => o.text.includes('Galasso')); return o ? o.value : ''; })()")
    pg.goto(B + '/settimana/%s?struttura=1&medico=%s' % (MAR.isoformat(), gid))
    pg.wait_for_timeout(500)
    a = pg.evaluate("""() => {
      const t = document.querySelector('table.agenda-medico');
      const righe = Array.from(t.tBodies[0].rows), n = t.querySelectorAll('thead th').length, prese = {};
      righe.forEach((tr, i) => { let c = 0; Array.from(tr.cells).forEach(td => {
        while (prese[i + ',' + c]) c++; for (let k = 0; k < td.rowSpan; k++) prese[(i + k) + ',' + c] = true; c++; }); });
      return {misto: t.tBodies[0].classList.contains('fasce-miste'), testa: t.tHead.textContent,
              complete: righe.every((tr, i) => Object.keys(prese).filter(k => k.startsWith(i + ',')).length === n),
              libere: Array.from(t.querySelectorAll('a.posa.con-ora')).map(x => x.textContent.trim()).slice(0, 3)};
    }""")
    ok("agenda del medico: fasce da 15' il martedi, righe complete, ore nelle fasce libere",
       a['misto'] and "fasce da 15'" in a['testa'] and a['complete'] and a['libere'] and a['libere'][0].startswith('08:45'), a)

    # il modulo del turno
    pg.goto(B + '/anagrafiche')
    pg.wait_for_timeout(400)
    link = pg.evaluate("(() => { const tr = Array.from(document.querySelectorAll('tr')).find(r => r.textContent.includes(\"fasce da 15'\")); const a = tr && tr.querySelector('a[href*=\"/anagrafiche/turni/\"]'); return a ? a.getAttribute('href') : ''; })()")
    ok('in Anagrafiche il turno dice le sue fasce', bool(link), link)
    if link:
        pg.goto(B + link)
        pg.wait_for_timeout(400)
        valori = pg.evaluate("Array.from(document.querySelectorAll('#passo option')).map(o => o.value)")
        ok('modulo del turno: Durata delle fasce a 15 minuti', pg.input_value('#passo') == '15'
           and valori[:2] == ['0', '10'] and 'Come la struttura' in pg.locator('#passo option').first.inner_text(),
           (pg.input_value('#passo'), valori))

    # tema scuro (un'altra finestra, con il tema scelto prima di aprire): l'ora delle fasce libere si legge
    ctx2 = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT')
    ctx2.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                         "localStorage.setItem('gestionale-tema', 'scuro'); } catch (e) {}")
    pg2 = ctx2.new_page()
    pg2.on('pageerror', lambda e: err.append(str(e)))
    pg2.goto(giorno)
    pg2.wait_for_timeout(500)
    colori = pg2.evaluate("""() => {
      const a = document.querySelector('tbody.fasce-miste td.aperta a.posa.con-ora');
      const lum = c => { const v = c.match(/\\d+(\\.\\d+)?/g).slice(0, 3).map(Number).map(x => x / 255)
        .map(x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4)); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
      let el = a, sfondo = 'rgba(0, 0, 0, 0)';
      while (el && (sfondo === 'rgba(0, 0, 0, 0)' || sfondo === 'transparent')) { sfondo = getComputedStyle(el).backgroundColor; el = el.parentElement; }
      const l1 = lum(getComputedStyle(a).color), l2 = lum(sfondo);
      return {scuro: document.documentElement.classList.contains('scuro'), colore: getComputedStyle(a).color, sfondo: sfondo,
              contrasto: (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)};
    }""")
    ok('tema scuro: l\'ora delle fasce libere si legge (contrasto almeno 3)', colori['scuro'] and colori['contrasto'] >= 3, colori)
    ctx2.close()

    # schermo stretto: la griglia scorre dentro il suo riquadro, niente errori
    pg.set_viewport_size({'width': 420, 'height': 800})
    pg.goto(giorno)
    pg.wait_for_timeout(500)
    larga = pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    ok('schermo stretto: la pagina non si allarga (scorre solo la griglia)', larga)
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()

print('%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
