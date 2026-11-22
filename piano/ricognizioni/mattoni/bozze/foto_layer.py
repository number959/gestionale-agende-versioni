"""Le pagine di oggi prima e dopo vecchio.css (strato), in chiaro e in scuro, a 1366x657 e a pagina intera.
«dopo» = l'HTML che darebbe base.html della bozza: il browser riceve la pagina vera e la si cambia al volo come la
cambierebbe il modello (vecchio.css al posto dei due fogli, :root della struttura nello strato, gettoni.css e veste.css).
«mutante» = come «dopo» ma con :root fuori dallo strato: la prova deve trovarlo.
Uso: python foto_layer.py http://127.0.0.1:5141 cartella_bozze cartella_foto"""
import datetime, os, re, sys, json
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops
BASE, BOZZE, FOTO = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(FOTO, exist_ok=True)
oggi = datetime.date.today()
mar = oggi - datetime.timedelta(days=(oggi.weekday() - 1) % 7)
g = mar.isoformat()
PAGINE = ['/oggi', '/giorno/%s?struttura=1' % g, '/settimana/%s?struttura=1' % g, '/mese/%s?struttura=1' % mar.strftime('%Y%m'),
          '/giorno/%s/elenco?struttura=1' % g, '/sala/%s?struttura=1' % g, '/pazienti', '/conferme', '/cassa/%s?struttura=1' % g,
          '/personale/turni/mese/', '/dove-si-fa/', '/statistiche', '/impostazioni', '/ambulatori/riepilogo',
          '/appuntamento?data=%s&struttura=1' % g, '/aiuto', '/riepilogo-live', '/stampa/%s?struttura=1' % g]
LEGGI = lambda n: open(os.path.join(BOZZE, 'static', n), encoding='utf-8').read()
DUE = re.compile(r'<link rel="stylesheet" href="/static/stile\.css">\s*<link rel="stylesheet" href="/static/tema-scuro\.css">')
ROOT = re.compile(r'<style>(:root \{ --primario:[^<]*\})</style>')

def cambia(html, mutante):
    if 'if (true)' in html[:3000]:          # foglio da stampare: base.html non lo cambia
        return html
    assert DUE.search(html) and ROOT.search(html), 'segnaposto non trovati'
    html = DUE.sub('<link rel="stylesheet" href="/static/vecchio.css">', html, 1)
    radice = (r'<style>\1</style>' if mutante else r'<style>@layer vecchio { \1 }</style>')
    html = ROOT.sub(radice + '\n<link rel="stylesheet" href="/static/gettoni.css">\n<link rel="stylesheet" href="/static/veste.css">', html, 1)
    return html

def prepara(ctx, modo):
    if modo == 'prima':
        return
    def doc(route, *_):
        if route.request.resource_type != 'document':
            return route.continue_()
        r = route.fetch()
        ct = r.headers.get('content-type', '')
        if 'text/html' not in ct:
            return route.fulfill(response=r)
        route.fulfill(response=r, body=cambia(r.text(), modo == 'mutante'), headers={**r.headers, 'content-length': ''})
    ctx.route('**/*', doc)
    def foglio(n):
        return lambda route, *_: route.fulfill(status=200, content_type='text/css', body=LEGGI(n))
    for n in ('vecchio.css', 'gettoni.css', 'veste.css'):
        ctx.route('**/static/' + n, foglio(n))

def foto(b, modo, tema, pagina, nome, intera):
    ctx = b.new_context(viewport={'width': 1366, 'height': 657}, reduced_motion='reduce')
    if tema == 'scuro':
        ctx.add_init_script("try { localStorage.setItem('gestionale-tema', 'scuro'); } catch (e) {}")
    prepara(ctx, modo)
    p = ctx.new_page()
    errori = []
    p.on('pageerror', lambda e: errori.append(str(e)))
    p.goto(BASE + pagina, wait_until='load')
    p.wait_for_timeout(1200)
    # niente notifiche a scomparsa (arrivano con un ritardo che cambia fra una foto e l'altra) e niente cursore
    p.add_style_tag(content='#notifiche, .notifiche { visibility: hidden !important; } * { caret-color: transparent !important; }')
    p.wait_for_timeout(150)
    f = os.path.join(FOTO, nome)
    p.screenshot(path=f, full_page=intera)
    info = p.evaluate("""() => ({ fogli: [...document.styleSheets].map(s => s.href ? s.href.split('/').pop() : 'in linea'),
        link: getComputedStyle(document.querySelector('a') || document.body).color,
        primarioScuro: getComputedStyle(document.documentElement).getPropertyValue('--primario-scuro').trim(),
        vTesto: getComputedStyle(document.documentElement).getPropertyValue('--v-testo').trim() })""")
    ctx.close()
    return f, errori, info

def diff(a, b):
    A, B = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    if A.size != B.size:
        return 'misure diverse %s %s' % (A.size, B.size), None
    d = ImageChops.difference(A, B)
    box = d.getbbox()
    if not box:
        return 0, None
    n = sum(1 for px in d.getdata() if px != (0, 0, 0))
    return n, box

esito = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    for i, pagina in enumerate(PAGINE):
        for tema in ('chiaro', 'scuro'):
            for intera in (False, True):
                suff = '%02d-%s%s' % (i, tema, '-intera' if intera else '')
                r = {}
                for modo in ('prima', 'dopo', 'prima2', 'mutante'):
                    m = 'prima' if modo == 'prima2' else modo
                    if modo == 'mutante' and (tema == 'chiaro' or intera):
                        continue
                    r[modo] = foto(b, m, tema, pagina, '%s-%s.png' % (suff, modo), intera)
                riga = dict(pagina=pagina, tema=tema, intera=intera,
                            rumore=diff(r['prima'][0], r['prima2'][0])[0],
                            prima_dopo=diff(r['prima'][0], r['dopo'][0])[0],
                            errori_js=[r[k][1] for k in r if r[k][1]],
                            fogli_dopo=r['dopo'][2]['fogli'], link_prima=r['prima'][2]['link'], link_dopo=r['dopo'][2]['link'],
                            v_testo_dopo=r['dopo'][2]['vTesto'])
                if 'mutante' in r:
                    riga['prima_mutante'] = diff(r['prima'][0], r['mutante'][0])[0]
                    riga['link_mutante'] = r['mutante'][2]['link']
                esito.append(riga)
                print(json.dumps(riga, ensure_ascii=False), flush=True)
    b.close()
json.dump(esito, open(os.path.join(FOTO, 'esito.json'), 'w'), indent=1, ensure_ascii=False)
