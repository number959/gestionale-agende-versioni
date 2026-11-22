# Le scritte fisse: quelle delle tavole Turni1-6 che oggi non ci sono, e quelle di oggi che le tavole non hanno.
# Prende i testi visibili, title, aria-label e placeholder; toglie quelli con cifre e i nomi delle persone (dati).
# Uso: python -I testi.py   (gestionale di prova sulla porta 5146)
import json, os, re
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

V = os.path.dirname(os.path.abspath(__file__))
oggi = date.today()
lun = oggi - timedelta(days=oggi.weekday())
COPPIE = [('Turni1-Mese', ['/personale/turni/mese/%s' % oggi.strftime('%Y-%m')]),
          ('Turni2-Settimana', ['/personale/turni/settimana/%s' % lun.isoformat()]),
          ('Turni3-Giorno', ['/personale/turni/giorno/%s' % lun.isoformat(), '/personale/turni/giorno/%s' % oggi.isoformat()]),
          ('Turni4-Persone', ['/personale/persone']),
          ('Turni5-Persona', ['/personale/persone/1', '/personale/persone/nuova']),
          ('Turni6-Tipi', ['/personale/tipi'])]
JS = r'''(tavola) => {
  const radice = tavola ? (document.querySelector('main') || document.querySelector('[data-dc-root], #dc-radice') || document.body) : document.body;
  const fuori = tavola ? Array.from(document.querySelectorAll('aside')) : Array.from(document.querySelectorAll('nav.menu, #aiuto-tasti, .popup-aggiornamento'));
  const out = new Set();
  const w = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode; const t = n.textContent.replace(/\s+/g, ' ').trim();
    if (!t || fuori.some(f => f.contains(n))) continue;
    const el = n.parentElement; if (!el || ['SCRIPT', 'STYLE', 'TITLE'].includes(el.tagName)) continue;
    out.add(t);
  }
  for (const el of radice.querySelectorAll('[title], [aria-label], [placeholder]')) {
    if (fuori.some(f => f.contains(el))) continue;
    for (const a of ['title', 'aria-label', 'placeholder']) { const v = el.getAttribute(a); if (v) out.add('@' + a + ': ' + v.replace(/\s+/g, ' ').trim()); }
  }
  return Array.from(out);
}'''


def pulisci(testi, nomi):
    r = set()
    for t in testi:
        if re.search(r'\d', t) or any(n in t for n in nomi) or len(t) < 2:
            continue
        r.add(t)
    return r


with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': 1440, 'height': 1000}, locale='it-IT')
    pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') and '127.0.0.1' not in r.request.url else r.continue_())
    risultato = {}
    for tavola, pagine in COPPIE:
        pg.goto('file://' + os.path.join(V, 'tavole', tavola + '.dc.html'))
        pg.wait_for_function('window.__pronto === true', timeout=15000)
        pg.wait_for_timeout(200)
        t_tav = pg.evaluate(JS, True)
        t_oggi = []
        for u in pagine:
            pg.goto('http://127.0.0.1:5146' + u)
            pg.wait_for_timeout(200)
            t_oggi += pg.evaluate(JS, False)
        # nomi di persone (tavola e demo): parole con la maiuscola che compaiono come «Cognome Nome»
        nomi = set()
        for t in t_tav + t_oggi:
            for m in re.finditer(r"\b([A-Z][a-zà-ù']+) ([A-Z][a-zà-ù']+)\b", t):
                pass
        solo_tavola = sorted(pulisci(t_tav, nomi) - pulisci(t_oggi, nomi))
        solo_oggi = sorted(pulisci(t_oggi, nomi) - pulisci(t_tav, nomi))
        risultato[tavola] = {'solo_tavola': solo_tavola, 'solo_oggi': solo_oggi}
    br.close()
with open(os.path.join(V, 'testi.json'), 'w') as f:
    json.dump(risultato, f, indent=1, ensure_ascii=False)
for k, v in risultato.items():
    print('=====', k)
    print('  SOLO NELLA TAVOLA:', ' | '.join(v['solo_tavola']))
    print('  SOLO OGGI:', ' | '.join(v['solo_oggi']))
