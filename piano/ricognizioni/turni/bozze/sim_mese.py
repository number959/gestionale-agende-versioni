# Il mese dei turni in 1046 px (1366 meno il menu di 248 e i margini di 36+36): con il markup di oggi e le colonne
# proposte, si misura se ogni codice e ogni orario scritto a mano sta intero nel suo tassello.
# Uso: python -I sim_mese.py [giorno_px] [ore_px] [tot_px]   (gestionale di prova sulla porta 5146)
import json, os, sys
from playwright.sync_api import sync_playwright

V = os.path.dirname(os.path.abspath(__file__))
G = int(sys.argv[1]) if len(sys.argv) > 1 else 24
ORE = int(sys.argv[2]) if len(sys.argv) > 2 else 58
TOT = int(sys.argv[3]) if len(sys.argv) > 3 else 32
MESE = sys.argv[4] if len(sys.argv) > 4 else '2026-12'      # dicembre: 31 giorni, il caso peggiore

CSS = '''
nav.menu { display: none !important; }
body { margin-left: 248px !important; background: #F3F6FA; }
.barra-turni { padding-left: 36px !important; padding-right: 36px !important; }
.legenda-turni { padding-left: 36px !important; padding-right: 36px !important; }
.telaio-turni { padding: 10px 36px 40px !important; }
.scorri-turni { border-color: #E3E9F4 !important; border-radius: 16px !important; }
table.turni-mese col.col-nome { width: auto !important; }
table.turni-mese col.col-giorno { width: %(G)dpx !important; }
table.turni-mese col.col-tot { width: %(TOT)dpx !important; }
table.turni-mese col.col-tot:nth-last-child(4) { width: %(ORE)dpx !important; }
table.turni-mese td.cella { height: 40px; }
table.turni-mese td.cella .turno { width: calc(100%% - 2px); min-width: 0; padding: 0; font-size: 11px; letter-spacing: 0; }
table.turni-mese td.cella .turno.lungo-3 { font-size: 9px; letter-spacing: -.03em; }
table.turni-mese td.cella .turno.lungo-4 { font-size: 8px; letter-spacing: -.03em; }
table.turni-mese td.cella .turno.a-mano { width: calc(100%% - 1px); }
table.turni-mese td.cella .turno b.orario-stretto { font: 600 8px/1.1 var(--testo); letter-spacing: -.02em; }
table.turni-mese td.cella .turno.a-mano.doppio b { font: 600 8px/1 var(--testo); letter-spacing: -.02em; }
table.turni-mese td.cella .turno.doppio { font-size: 9.5px; }
table.turni-mese td.tot { padding: 2px 1px; }
table.turni-mese td.tot b { display: block; }
table.turni-mese td.tot small { display: block; margin: 0; font-size: 10.5px; }
''' % {'G': G, 'ORE': ORE, 'TOT': TOT}

# i tasselli di prova: lo stesso disegno di chipCella() (turni.js) e della macro contenuto()
PROVE = r'''() => {
  const casi = [['M'], ['RE'], ['SN'], ['MA'], ['PE'], ['MM'], ['WW'], ['REP'], ['MAL'], ['WWW'], ['L104'], ['MMMM'],
                [null, '8', '12'], [null, '7:30', '13:30'], [null, '13:30', '19:45'], [null, '21:15', '23:45'],
                ['M', 'P'], ['RE', 'SN'], [null, '13:30', null, '19:45']];
  const riga = document.querySelector('#griglia-turni tr.riga-persona');
  const celle = Array.from(riga.querySelectorAll('td.cella'));
  casi.forEach((caso, i) => {
    const td = celle[i]; td.textContent = '';
    const chip = (testo, cls, orario) => {
      const s = document.createElement('span'); s.className = 'turno' + cls;
      s.style.setProperty('--c', '#B8EAE0'); s.style.setProperty('--t', '#16263F');
      const b = document.createElement('b');
      if (orario) { b.className = 'orario-stretto'; orario.forEach(o => { const x = document.createElement('span'); x.textContent = o; b.appendChild(x); }); }
      else b.textContent = testo;
      s.appendChild(b); td.appendChild(s);
    };
    if (caso.length === 1) chip(caso[0], caso[0].length >= 4 ? ' lungo-4' : caso[0].length === 3 ? ' lungo-3' : '');
    else if (caso.length === 3 && caso[0] === null) chip(null, ' a-mano', [caso[1], caso[2]]);
    else if (caso.length === 2) { chip(caso[0], ' doppio'); chip(caso[1], ' doppio'); }
    else { chip(caso[1], ' a-mano doppio'); chip(caso[3], ' a-mano doppio'); }
    td.dataset.caso = caso.filter(x => x !== null).join('/');
  });
}'''

MISURA = r'''() => {
  const tab = document.getElementById('griglia-turni');
  const scorri = tab.parentElement;
  const out = {contenitore: Math.round(scorri.getBoundingClientRect().width), tabella: tab.scrollWidth,
               scorre_di_lato: scorri.scrollWidth > scorri.clientWidth + 1,
               giorni: tab.querySelectorAll('thead th.giorno-col').length,
               col_nome: Math.round(tab.querySelector('th.nome-col').getBoundingClientRect().width),
               cella: Math.round(tab.querySelector('td.cella').getBoundingClientRect().width), casi: [], tagliati: [], nomi_tagliati: []};
  for (const td of tab.querySelectorAll('td.cella')) {
    for (const s of td.querySelectorAll('.turno')) {
      const b = s.querySelector('b');
      const parti = b.classList.contains('orario-stretto') ? Array.from(b.children) : [b];
      const serve = Math.max(...parti.map(x => x.getBoundingClientRect().width));
      const c = getComputedStyle(s);
      const posto = s.clientWidth - parseFloat(c.paddingLeft) - parseFloat(c.paddingRight);
      const r = {caso: td.dataset.caso || b.textContent, testo: parti.map(x => x.textContent).join('/'),
                 serve: Math.round(serve * 10) / 10, posto: Math.round(posto * 10) / 10, corpo: c.fontSize};
      if (td.dataset.caso) out.casi.push(r);
      if (serve > posto + 0.5) out.tagliati.push(r);
    }
  }
  for (const a of tab.querySelectorAll('th.nome-col a')) if (a.scrollWidth > a.clientWidth + 1) out.nomi_tagliati.push(a.textContent.trim());
  out.nomi_totali = tab.querySelectorAll('th.nome-col a').length;
  const intest = Array.from(tab.querySelectorAll('thead th.tot-col')).map(th => ({t: th.textContent.trim(), ok: th.scrollWidth <= th.clientWidth + 1}));
  out.intestazioni_totali = intest;
  const ore = Array.from(tab.querySelectorAll('td.tot[data-tot="ore"]')).filter(td => td.scrollWidth > td.clientWidth + 1).length;
  out.ore_tagliate = ore;
  return out;
}'''

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': 1366, 'height': 657}, locale='it-IT')
    pg.goto('http://127.0.0.1:5146/personale/turni/mese/' + MESE)
    pg.add_style_tag(content=CSS)
    pg.evaluate(PROVE)
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(400)
    m = pg.evaluate(MISURA)
    nome = 'sim-mese-%s-%d-%d-%d' % (MESE, G, ORE, TOT)
    pg.screenshot(path=os.path.join(V, 'foto', nome + '.png'))
    pg.locator('#griglia-turni tr.riga-persona').first.screenshot(path=os.path.join(V, 'foto', nome + '-riga.png'))
    br.close()
with open(os.path.join(V, nome + '.json'), 'w') as f:
    json.dump(m, f, indent=1, ensure_ascii=False)
print(nome)
print('contenitore', m['contenitore'], 'tabella', m['tabella'], 'scorre di lato', m['scorre_di_lato'], 'giorni', m['giorni'],
      'col nome', m['col_nome'], 'cella', m['cella'])
print('nomi tagliati %d su %d: %s' % (len(m['nomi_tagliati']), m['nomi_totali'], m['nomi_tagliati']))
print('intestazioni dei totali', m['intestazioni_totali'], 'celle Ore tagliate', m['ore_tagliate'])
for r in m['casi']:
    print('  %-12s %-12s serve %5.1f posto %5.1f %s %s' % (r['caso'], r['testo'], r['serve'], r['posto'], r['corpo'],
                                                         'TAGLIATO' if r['serve'] > r['posto'] + 0.5 else 'intero'))
print('tasselli tagliati in tutta la griglia:', len(m['tagliati']), [x['testo'] for x in m['tagliati']][:20])
