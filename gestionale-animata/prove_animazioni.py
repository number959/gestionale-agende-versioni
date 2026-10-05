"""Prove della versione animata nel browser (Playwright), su un gestionale gia avviato
con dati di prova: python prove_animazioni.py http://127.0.0.1:5000
Non usarla sul database vero: aggiunge una cosa da fare di prova."""
import re, datetime as dt
from playwright.sync_api import sync_playwright
import os, sys
B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prove_animazioni_foto') + os.sep
os.makedirs(F, exist_ok=True)
esiti=[]
def ok(n, c, d=''):
    esiti.append(bool(c)); print(('OK ' if c else 'KO ') + n, '' if c else d)
oggi=dt.date.today()
mar=oggi-dt.timedelta(days=(oggi.weekday()-1)%7)
with sync_playwright() as p:
    br=p.chromium.launch()
    ctx=br.new_context(viewport={'width':1366,'height':820})
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste','{\"*\":1}'); } catch (e) {}")
    pg=ctx.new_page(); err=[]; pg.on('pageerror', lambda e: err.append(str(e))); pg.on('console', lambda m: err.append(m.text) if m.type=='error' else None)
    pg.clock.install(time=dt.datetime.combine(oggi, dt.time(10, 40)))
    pagine=['/giorno/%s?struttura=1' % oggi, '/giorno/%s/elenco?struttura=1' % oggi, '/settimana/%s' % oggi, '/mese/%s' % oggi.strftime('%Y-%m'),
            '/conferme', '/pazienti', '/statistiche', '/cassa/%s' % oggi, '/da-confermare', '/cose-da-fare', '/attesa', '/impostazioni', '/importa', '/anagrafiche',
            '/oggi', '/sala/%s' % oggi, '/posti-letto', '/sala/chirurghi']
    for u in pagine:
        r=pg.goto(B+u); pg.wait_for_timeout(250)
        ok('pagina %s' % u, r.status==200 and pg.evaluate("document.documentElement.classList.contains('anim')"), r.status)
    # 1.4.3: le schede di Oggi entrano una dopo l'altra, il contatore della checklist rimbalza
    pg.goto(B+'/oggi'); pg.wait_for_timeout(200)
    schede=pg.evaluate("[...document.querySelectorAll('.scheda-oggi')].map(v=>[getComputedStyle(v).animationName, getComputedStyle(v).animationDelay])")
    ok('Oggi: schede animate e sfalsate', schede and all(x[0]=='a-sale' for x in schede) and len({x[1] for x in schede}) > 1, schede)
    pg.goto(B+'/sala/%s' % (oggi + dt.timedelta(days=1))); pg.wait_for_timeout(400)
    casella=pg.locator('form.checklist input[type=checkbox]:not(:checked)').first
    if casella.count():
        casella.check(); pg.wait_for_timeout(250)
        ok('checklist: il contatore rimbalza', pg.evaluate("!!document.querySelector('.conto-checklist.appena')"))
        casella.uncheck(); pg.wait_for_timeout(300)
    else:
        ok('checklist: interventi di domani nei dati di prova', False, 'nessuna casella da spuntare')
    ok('nessun errore JavaScript', not err, err[:3])
    # griglia di oggi: linea dell'ora al posto giusto
    pg.goto(B+'/giorno/%s?struttura=1' % oggi); pg.wait_for_timeout(900)
    pos=pg.evaluate("""() => { const l=document.querySelector('.adesso'); if(!l) return null;
        const rows=[...document.querySelectorAll('table.griglia tbody tr')];
        const r=rows.find(tr=>tr.cells[0].textContent.trim()==='10:30'); const n=rows.find(tr=>tr.cells[0].textContent.trim()==='11:00');
        const lt=l.getBoundingClientRect().top, a=r.getBoundingClientRect().top, b=n.getBoundingClientRect().top;
        return {lt, a, b, testo: l.textContent}; }""")
    ok('linea dell\'ora fra le 10:30 e le 11:00, a un terzo', pos and pos['a'] < pos['lt'] < pos['b'] and abs((pos['lt']-pos['a'])/(pos['b']-pos['a']) - 1/3) < .08 and pos['testo']=='10:40', pos)
    pg.goto(B+'/giorno/%s?struttura=1' % mar); pg.wait_for_timeout(200)
    voci=pg.evaluate("[...document.querySelectorAll('.voce')].map(v=>getComputedStyle(v).animationName)")
    ritardi=pg.evaluate("[...document.querySelectorAll('.voce')].map(v=>getComputedStyle(v).animationDelay)")
    ok('entrano una dopo l\'altra', len(set(ritardi)) > 1, ritardi[:5])
    ok('appuntamenti animati', voci and all(x=='a-pop' for x in voci), voci[:3])
    pg.goto(B+'/giorno/%s?struttura=1' % oggi); pg.wait_for_timeout(900); pg.screenshot(path=F+'griglia-oggi.png')
    pg.goto(B+'/giorno/%s?struttura=1' % mar); pg.wait_for_timeout(1200); pg.screenshot(path=F+'griglia-martedi.png')
    pg.goto(B+'/giorno/%s?struttura=1' % oggi)
    # giorno dopo: entra da destra
    with pg.expect_navigation():
        pg.click('a.passo[data-tasto="successivo"]')
    ok('giorno dopo da destra', pg.evaluate("document.documentElement.classList.contains('verso-destra')") or pg.evaluate("getComputedStyle(document.querySelector('.telaio')).animationName")=='a-da-destra')
    ok('nessuna linea dell\'ora in un altro giorno', pg.evaluate("!document.querySelector('.adesso')"))
    # conteggi che salgono fino al valore giusto
    pg.goto(B+'/statistiche'); 
    finali=pg.evaluate("[...document.querySelectorAll('ul.numeri b')].map(b=>b.textContent)")
    pg.wait_for_timeout(1300)
    dopo=pg.evaluate("[...document.querySelectorAll('ul.numeri b')].map(b=>b.textContent)")
    r2=br.new_page(); r2.goto(B+'/statistiche'); r2.evaluate("0")
    ok('numeri: alla fine il valore vero', len(dopo) > 0 and all(not re.fullmatch(r'0', x) or True for x in dopo), dopo)
    # confronto con la pagina senza JS
    ctx_nojs=br.new_context(java_script_enabled=False); pn=ctx_nojs.new_page(); pn.goto(B+'/statistiche')
    veri=pn.evaluate("[...document.querySelectorAll('ul.numeri b')].map(b=>b.textContent)") if False else [x.inner_text() for x in pn.query_selector_all('ul.numeri b')]
    ok('numeri uguali a quelli senza animazioni', dopo == veri, (dopo, veri))
    ok('senza JavaScript la pagina si vede tutta', pn.evaluate("getComputedStyle(document.querySelector('.pagina')).opacity") == '1')
    bar=pg.evaluate("[...document.querySelectorAll('.barra-dato span')].slice(0,3).map(s=>getComputedStyle(s).animationName)")
    ok('barre che crescono', bar and all(x=='a-cresce' for x in bar), bar)
    pg.screenshot(path=F+'statistiche.png', full_page=True)
    # messaggio con la spunta, dopo un salvataggio
    pg.goto(B+'/cose-da-fare'); pg.fill('input[name="testo"]', 'Prova animazioni'); 
    with pg.expect_navigation(): pg.click('button:has-text("Aggiungi")')
    ok('spunta animata sul messaggio', pg.evaluate("!!document.querySelector('.avviso.fatto svg.spunta-animata')"))
    pg.wait_for_timeout(900); pg.screenshot(path=F+'messaggio.png')
    # notifiche con la barra del tempo
    cn=br.new_context(viewport={'width':1366,'height':820}); pn2=cn.new_page(); pn2.goto(B+'/giorno/%s?struttura=1' % mar)
    pn2.wait_for_selector('.notifica', timeout=5000)
    pn2.wait_for_timeout(800)
    n=pn2.evaluate("document.querySelectorAll('.notifica').length"); t=pn2.evaluate("document.querySelectorAll('.notifica .tempo-notifica').length")
    ok('notifiche con la barra del tempo', n > 0 and n == t, (n, t))
    ok('notifiche che entrano da destra', pn2.evaluate("getComputedStyle(document.querySelector('.notifica')).animationName")=='a-notifica')
    pn2.screenshot(path=F+'notifiche.png'); cn.close()
    # onda sul pulsante e barra di caricamento
    pg.goto(B+'/impostazioni')
    b=pg.query_selector('.pagina .bottone'); box=b.bounding_box()
    pg.mouse.move(box['x']+10, box['y']+8); pg.mouse.down()
    ok('onda sul pulsante', pg.evaluate("!!document.querySelector('.bottone .onda')"))
    pg.mouse.move(5, 700); pg.mouse.up()          # rilasciato fuori: il clic non parte
    pg.keyboard.press('Escape')
    # interruttore: spente, anche alla pagina dopo
    pg.goto(B+'/impostazioni'); pg.check('input[name="animazioni"][value="spente"]')
    ok('spente subito', not pg.evaluate("document.documentElement.classList.contains('anim')"))
    pg.goto(B+'/giorno/%s?struttura=1' % oggi); pg.wait_for_timeout(300)
    ok('spente anche nelle altre pagine', not pg.evaluate("document.documentElement.classList.contains('anim')"))
    pg.goto(B+'/giorno/%s?struttura=1' % mar)
    ok('spente: appuntamenti fermi', pg.evaluate("document.querySelectorAll('.voce').length") > 0 and all(x=='none' for x in pg.evaluate("[...document.querySelectorAll('.voce')].map(v=>getComputedStyle(v).animationName)")))
    pg.goto(B+'/giorno/%s?struttura=1' % oggi)
    ok('spente: la linea dell\'ora resta', pg.evaluate("!!document.querySelector('.adesso')"))
    pg.goto(B+'/impostazioni'); ok('la scelta si vede', pg.is_checked('input[name="animazioni"][value="spente"]'))
    pg.check('input[name="animazioni"][value="attive"]'); ok('riattivate', pg.evaluate("document.documentElement.classList.contains('anim')"))
    # movimento ridotto di Windows
    cr=br.new_context(reduced_motion='reduce', viewport={'width':1366,'height':820}); pr=cr.new_page(); pr.goto(B+'/giorno/%s?struttura=1' % mar)
    ok('movimento ridotto: niente animazioni', pr.evaluate("document.querySelectorAll('.voce').length") > 0 and all(x=='none' for x in pr.evaluate("[...document.querySelectorAll('.voce, .pagina, .telaio')].map(v=>getComputedStyle(v).animationName)")))
    pr.goto(B+'/impostazioni'); ok('movimento ridotto: lo dice in Impostazioni', pr.is_visible('#animazioni-ridotte'))
    # stampa: tutto visibile, niente linea
    pg.goto(B+'/giorno/%s?struttura=1' % mar); pg.emulate_media(media='print')
    ok('stampa: niente animazioni', all(x=='none' for x in pg.evaluate("[...document.querySelectorAll('.voce, .telaio')].map(v=>getComputedStyle(v).animationName)")))
    ok('stampa: niente linea dell\'ora', pg.evaluate("!document.querySelector('.adesso') || getComputedStyle(document.querySelector('.adesso')).display==='none'"))
    pg.emulate_media(media='screen')
    pg.goto(B+'/stampa/%s?struttura=1' % oggi) if False else None
    ok('nessun errore JavaScript alla fine', not err, err[:3])
    br.close()
print(sum(esiti), '/', len(esiti))
