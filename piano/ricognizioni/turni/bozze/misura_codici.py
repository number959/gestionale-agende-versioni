# Quanto sono larghi i codici dei turni con i caratteri veri del programma (Manrope e Inter di static/fonts),
# e in quale cella stanno interi. Uso: python -I misura_codici.py  (gestionale di prova sulla porta 5146)
import json, os
from playwright.sync_api import sync_playwright

V = os.path.dirname(os.path.abspath(__file__))
CODICI = ['M', 'P', 'N', 'G', 'R', 'F', 'RE', 'SN', 'MA', 'PE', 'MM', 'MP', 'WW', 'REP', 'MAL', 'WWW', 'L104', 'MMMM', 'WWWW']
ORARI = ['8', '12', '7:30', '13:30', '19:45', '21:15', '23:45']
JS = r'''([codici, orari]) => {
  const misura = (testo, font, ls) => {
    const s = document.createElement('span');
    s.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;font:' + font + ';letter-spacing:' + ls;
    s.textContent = testo; document.body.appendChild(s);
    const w = s.getBoundingClientRect().width; s.remove(); return Math.round(w * 10) / 10;
  };
  const out = {codici: {}, orari: {}};
  for (const c of codici) {
    out.codici[c] = {
      'Manrope 700 12px +.02em (oggi)': misura(c, "700 12px Manrope", '.02em'),
      'Manrope 700 11px 0 (tavola)': misura(c, "700 11px Manrope", '0'),
      'Manrope 700 10px 0': misura(c, "700 10px Manrope", '0'),
      'Manrope 700 9.5px 0 (doppio)': misura(c, "700 9.5px Manrope", '0'),
      'Manrope 700 9px -.02em': misura(c, "700 9px Manrope", '-.02em'),
      'Manrope 700 8px -.03em': misura(c, "700 8px Manrope", '-.03em'),
    };
  }
  for (const o of orari) {
    out.orari[o] = {
      'Inter 600 9px -.01em (oggi)': misura(o, "600 9px Inter", '-.01em'),
      'Inter 600 9px 0 (tavola)': misura(o, "600 9px Inter", '0'),
      'Inter 600 8.5px -.02em': misura(o, "600 8.5px Inter", '-.02em'),
      'Manrope 700 9.5px 0 (doppio)': misura(o, "700 9.5px Manrope", '0'),
    };
  }
  out.caratteri = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight);
  return out;
}'''

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': 1366, 'height': 657})
    pg.goto('http://127.0.0.1:5146/personale/turni/mese/')
    pg.evaluate('document.fonts.ready')
    # i caratteri si caricano solo quando servono: li chiedo tutti prima di misurare
    pg.evaluate('''Promise.all(["700 12px Manrope", "700 9px Manrope", "600 9px Inter", "400 13px Inter"].map(f => document.fonts.load(f, "MW")))''')
    r = pg.evaluate(JS, [CODICI, ORARI])
    br.close()
with open(os.path.join(V, 'misure_codici.json'), 'w') as f:
    json.dump(r, f, indent=1, ensure_ascii=False)
print('caratteri caricati:', r['caratteri'])
chiavi = list(r['codici']['M'].keys())
print('%-6s' % 'codice', ' | '.join('%8s' % k.split(' (')[0].replace('Manrope ', 'Mr').replace('700 ', '') for k in chiavi))
for c, v in r['codici'].items():
    print('%-6s' % c, ' | '.join('%8.1f' % v[k] for k in chiavi))
chiavi = list(r['orari']['8'].keys())
print()
for o, v in r['orari'].items():
    print('%-6s' % o, ' | '.join('%s %.1f' % (k, v[k]) for k in chiavi))
