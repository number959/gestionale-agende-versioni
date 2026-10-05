"""Prove delle icone animate (Lottie) e del riquadro di attesa, nel browser, su un
gestionale gia' avviato con dati di prova che abbiano interventi domani e una
notte senza letti: python prove_icone_animate.py http://127.0.0.1:5000
Non usarla sul database vero: spunta e toglie caselle della checklist."""
import sys, time, os, datetime as dt
from playwright.sync_api import sync_playwright
B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prove_animazioni_foto') + os.sep
os.makedirs(F, exist_ok=True)
oggi=dt.date.today(); domani=oggi+dt.timedelta(days=1)
esiti=[]
def ok(n,c,d=''): esiti.append(bool(c)); print(('OK ' if c else 'KO ')+n, '' if c else d)
with sync_playwright() as p:
    br=p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx=br.new_context(viewport={'width':1366,'height':820})
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste','{\"*\":1}'); } catch (e) {}"); pg=ctx.new_page(); err=[]; richieste=[]
    pg.on('pageerror', lambda e: err.append(str(e))); pg.on('console', lambda m: err.append(m.text) if m.type=='error' else None)
    pg.on('request', lambda r: richieste.append(r.url))
    # pagina senza pagine vuote: il lettore non si carica
    richieste.clear(); pg.goto(B+'/lista-operatoria/%s?struttura=1' % domani); pg.wait_for_timeout(1200)
    ok('pagina senza icone: lettore Lottie non caricato', not any('lottie' in u for u in richieste), [u for u in richieste if 'lottie' in u])
    # prima pagina con il menu: la notifica rossa (letti che non bastano) con l'icona di avviso
    pg.goto(B+'/giorno/%s?struttura=1' % domani)
    pg.wait_for_selector('.notifica.errore', timeout=6000); pg.wait_for_timeout(1200)
    ok('notifica rossa con icona di avviso', pg.evaluate("!!document.querySelector('.notifica.errore b .icona-animata.pronta svg')"))
    pg.screenshot(path=F+'notifica.png', clip={'x':1000,'y':560,'width':366,'height':260})
    # Oggi: icone nelle parti vuote
    richieste.clear(); pg.goto(B+'/oggi'); pg.wait_for_timeout(1800)
    n=pg.evaluate("document.querySelectorAll('p.vuoto .icona-animata.pronta svg').length")
    ok('Oggi: icone animate nelle parti vuote', n>=1, n)
    ok('lettore caricato dal programma, non da internet', any(u.startswith(B) and 'lottie_light' in u for u in richieste) and all(u.startswith(B) or u.startswith('data:') for u in richieste), [u for u in richieste if not u.startswith(B)][:3])
    fin=pg.evaluate("[...document.querySelectorAll('p.vuoto .icona-animata')].map(b=>getComputedStyle(b.querySelector('path[stroke]')||b).stroke)")
    ok('colore dell\'icona dal tema', fin and all(x.startswith('rgb') for x in fin), fin)
    pg.screenshot(path=F+'oggi.png')
    # checklist completata: spunta verde che poi sparisce
    pg.goto(B+'/sala/%s' % domani); pg.wait_for_timeout(800)
    righe=pg.locator('form.checklist')
    trovata=None
    for i in range(righe.count()):
        f=righe.nth(i)
        if 'incompleta' in (f.locator('.conto-checklist').get_attribute('class') or ''):
            trovata=f; break
    if trovata:
        caselle=trovata.locator('input[type=checkbox]:not(:checked)')
        spuntate=[]
        while caselle.count():
            c=caselle.first; spuntate.append(c.get_attribute('value')); c.check(); pg.wait_for_timeout(350)
        pg.wait_for_timeout(700)
        ok('checklist completa: spunta verde', trovata.locator('.icona-animata.spunta-checklist svg').count()==1)
        pg.screenshot(path=F+'checklist.png', clip={'x':0,'y':250,'width':1366,'height':260})
        pg.wait_for_timeout(3500)
        ok('la spunta poi sparisce', trovata.locator('.icona-animata.spunta-checklist').count()==0)
        for v in spuntate: trovata.locator('input[value="%s"]' % v).uncheck(); pg.wait_for_timeout(300)
    else:
        ok('checklist da completare nei dati di prova', False)
    # attesa lunga: la risposta del server trattenuta; il modulo va in un riquadro
    # nascosto, cosi' la pagina resta interrogabile mentre aspetta
    import openpyxl
    wb=openpyxl.Workbook(); wb.active.append(['Cognome','Nome','Telefono']); wb.active.append(['Prova','Anna','3330000000'])
    prova_file=os.path.join(F, 'prova_attesa.xlsx'); wb.save(prova_file)
    sospese=[]
    pg.goto(B+'/importa'); pg.route('**/importa', lambda r: sospese.append(r) if r.request.method=='POST' else r.continue_())
    pg.evaluate("var i=document.createElement('iframe');i.name='riposto';i.style.display='none';document.body.appendChild(i);document.querySelector('form[enctype]').target='riposto'")
    pg.set_input_files('input[type=file]', prova_file)
    pg.click('form[enctype] button[type=submit]', no_wait_after=True); pg.wait_for_timeout(1300)
    ok('attesa lunga: riquadro con lo spinner', pg.evaluate("!!document.querySelector('.attesa-lunga.visibile .giro svg')"))
    ok('attesa lunga: dice cosa sta facendo', 'Caricamento del file' in pg.inner_text('.attesa-lunga'))
    pg.screenshot(path=F+'attesa.png')
    for r in sospese: r.abort()
    pg.unroute('**/importa')
    # risposta veloce: il riquadro non compare
    pg.goto(B+'/impostazioni'); pg.click('button:has-text("Salva il foglio del giorno")'); pg.wait_for_timeout(300)
    ok('salvataggio veloce: nessun riquadro', not pg.evaluate("!!document.querySelector('.attesa-lunga.visibile')"))
    # tema scuro
    pg.evaluate("localStorage.setItem('gestionale-tema','scuro')"); pg.goto(B+'/oggi'); pg.wait_for_timeout(1800); pg.screenshot(path=F+'oggi-scuro.png')
    pg.evaluate("localStorage.setItem('gestionale-tema','chiaro')")
    # animazioni spente: niente icone, niente lettore
    pg.evaluate("localStorage.setItem('gestionale-animazioni','spente')"); richieste.clear(); pg.goto(B+'/oggi'); pg.wait_for_timeout(1200)
    ok('animazioni spente: nessuna icona e nessun lettore', not pg.evaluate("document.querySelectorAll('.icona-animata').length") and not any('lottie' in u for u in richieste))
    pg.evaluate("localStorage.removeItem('gestionale-animazioni')")
    ok('nessun errore JavaScript', not err, err[:3])
    # movimento ridotto di Windows
    ctx2=br.new_context(viewport={'width':1366,'height':820}, reduced_motion='reduce'); p2=ctx2.new_page(); r2=[]
    p2.on('request', lambda r: r2.append(r.url)); p2.goto(B+'/oggi'); p2.wait_for_timeout(1200)
    ok('movimento ridotto: nessuna icona e nessun lettore', not p2.evaluate("document.querySelectorAll('.icona-animata').length") and not any('lottie' in u for u in r2))
    # stampa: niente icone
    pg.goto(B+'/oggi'); pg.wait_for_timeout(1500); pg.emulate_media(media='print')
    ok('in stampa le icone non ci sono', pg.evaluate("[...document.querySelectorAll('.icona-animata')].every(b=>getComputedStyle(b).display==='none')"))
    br.close()
print('%d / %d' % (sum(esiti), len(esiti)))
sys.exit(0 if all(esiti) else 1)
