# Giro delle pagine del gestionale di prova (5142): per ogni tipo di pagina, quale voce del menu di oggi e' accesa
# (a.attivo o .gruppo.attivo), quanti nav.menu ci sono, e quali parti della cornice. Solo GET.
import re, sys, urllib.request, urllib.error, json
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, parse_qsl

B = 'http://127.0.0.1:5142'


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.link, self.attivi, self.menu, self.dentro, self.gruppo, self.pagina = [], [], 0, 0, None, ''
        self.testo_attivo = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        c = (a.get('class') or '').split()
        if tag == 'body':
            self.pagina = a.get('data-pagina', '')
        if tag == 'nav' and 'menu' in c:
            self.menu += 1
            self.dentro = 1
        if tag == 'a' and a.get('href'):
            self.link.append(a['href'])
        if self.dentro and tag == 'div' and 'gruppo' in c and 'attivo' in c:
            self.attivi.append('gruppo:' + (a.get('data-guida') or '?'))
        if self.dentro and tag == 'a' and 'attivo' in c:
            self.attivi.append('a:' + (a.get('data-guida') or a.get('href', '')[:30]))

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.dentro = 0


def forma(u):
    s = urlsplit(u)
    return re.sub(r'\d+', 'N', s.path) + '?' + '&'.join(sorted({k for k, _ in parse_qsl(s.query)}))


visti, coda, righe = set(), ['/oggi', '/giorno/2026-11-25?struttura=2', '/pazienti', '/anagrafiche', '/aiuto'], []
contate = {}
while coda and len(righe) < 220:
    u = coda.pop(0)
    f = forma(u)
    if f in visti or contate.get(f, 0) >= 1:
        continue
    if any(x in u for x in ('/static/', '.xlsx', '.json', '.pdf', '/logo/', 'scarica', '/backup/', '.png', '/video')):
        continue
    visti.add(f)
    try:
        r = urllib.request.urlopen(B + u, timeout=30)
        if 'text/html' not in r.headers.get('Content-Type', ''):
            continue
        h = r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        righe.append((f, 'HTTP %d' % e.code, '', 0))
        continue
    except Exception as e:
        continue
    p = P()
    p.feed(h)
    righe.append((f, p.pagina, ','.join(p.attivi), p.menu))
    for l in p.link:
        if l.startswith('/') and not l.startswith('//'):
            coda.append(l.split('#')[0])

senza = [r for r in righe if r[3] == 1 and not r[2]]
piu = [r for r in righe if r[2].count(',') >= 1]
print('pagine viste:', len(righe), '- con menu:', sum(1 for r in righe if r[3] == 1), '- senza menu:', sum(1 for r in righe if r[3] == 0))
print('\ncon menu ma nessuna voce accesa (%d):' % len(senza))
for r in senza:
    print('   ', r[0], r[1])
print('\npiu di una voce accesa (%d):' % len(piu))
for r in piu:
    print('   ', r[0], r[1], r[2])
print('\nsenza menu:')
for r in righe:
    if r[3] == 0:
        print('   ', r[0], r[1])
json.dump(righe, open(__file__.replace('.py', '.json'), 'w'), indent=0, ensure_ascii=False)
