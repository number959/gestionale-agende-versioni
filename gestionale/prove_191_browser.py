"""Prove nel browser della 1.9.1 (l'email con qualsiasi casella), su un
gestionale gia' avviato con i dati di prova (strumenti/demo.py: la casella del
sito accettazione@example.it, server mail.example.it):
    python prove_191_browser.py http://127.0.0.1:5001
- scegliendo il tipo di casella: server, porta e sicurezza proposti, nome del
  campo della password, istruzioni e note del tipo scelto (le altre nascoste);
- «Altro server» svuota solo un server proposto, non uno scritto a mano;
- casella del sito: il server segue l'indirizzo mentre si scrive, finche' non
  lo si scrive a mano; un indirizzo @gmail.com passa a Gmail;
- la tendina del tipo, fuori dal modulo, si salva con il modulo;
- nessun errore JavaScript, anche a schermo stretto.
Salva le impostazioni email: usarla su un gestionale di prova, mai su quello
vero (alla fine rimette la casella del sito della prova)."""
import os
import sys

from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000').rstrip('/')
esiti = []


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 800}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                        "localStorage.setItem('gestionale-tema', 'chiaro'); } catch (e) {}")
    pg = ctx.new_page()
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)

    def valori():
        return (pg.input_value('#email_server'), pg.input_value('#email_porta'), pg.input_value('#email_sicurezza'))

    def nascosti_giusti(tipo):
        return pg.evaluate("(t) => Array.from(document.querySelectorAll('[data-casella]')).every(function (x) {"
                           " return x.hidden === (x.getAttribute('data-casella') !== t); })", tipo)

    def scegli(tipo):
        pg.select_option('#email_tipo', tipo)
        pg.wait_for_timeout(120)

    def scrivi(sel, testo_):
        pg.fill(sel, '')
        pg.type(sel, testo_, delay=8)
        pg.wait_for_timeout(80)

    pg.goto(B + '/invii#email')
    pg.wait_for_timeout(400)
    ok('pagina: tipo della prova (casella del sito) con i suoi valori',
       pg.input_value('#email_tipo') == 'dominio' and valori() == ('mail.example.it', '465', 'ssl'), (pg.input_value('#email_tipo'), valori()))
    ok('solo le istruzioni del tipo scelto', nascosti_giusti('dominio'))
    salvata = pg.get_attribute('#email_password', 'placeholder')

    scegli('gmail')
    ok('Gmail: smtp.gmail.com, 587, STARTTLS', valori() == ('smtp.gmail.com', '587', 'starttls'), valori())
    ok('Gmail: «Password per le app» e le sue istruzioni', pg.text_content('#etichetta-password') == 'Password per le app'
       and nascosti_giusti('gmail'), pg.text_content('#etichetta-password'))
    ok('la password salvata resta indicata', pg.get_attribute('#email_password', 'placeholder') == salvata, salvata)

    scegli('aruba')
    ok('Aruba: smtps.aruba.it, 465, SSL', valori() == ('smtps.aruba.it', '465', 'ssl'), valori())
    ok('Aruba: «Password della casella»', pg.text_content('#etichetta-password') == 'Password della casella'
       and nascosti_giusti('aruba'))

    scegli('altro')
    ok('Altro server: il server proposto si svuota, porta e sicurezza restano', valori() == ('', '465', 'ssl'), valori())
    ok('Altro server: «Server e accesso» aperto', pg.evaluate("document.getElementById('email-server').open"))
    ok('Altro server: le sue istruzioni', nascosti_giusti('altro'))
    scrivi('#email_server', 'smtp.fornitore.example')
    scegli('gmail')
    scegli('altro')
    ok('Altro server dopo un tipo pronto: si svuota ancora', valori()[0] == '', valori())
    scrivi('#email_server', 'smtp.fornitore.example')
    scegli('altro')
    ok('un server scritto a mano non si tocca', valori()[0] == 'smtp.fornitore.example', valori())

    scegli('dominio')
    ok('casella del sito: mail. + dominio dell\'indirizzo', valori() == ('mail.example.it', '465', 'ssl'), valori())
    scrivi('#email_utente', 'segreteria@clinica-esempio.it')
    ok('il server segue l\'indirizzo mentre si scrive', valori()[0] == 'mail.clinica-esempio.it', valori())
    scrivi('#email_server', 'server12.hosting.example')
    scrivi('#email_utente', 'info@studio-esempio.it')
    ok('scritto a mano, il server non segue più l\'indirizzo', valori()[0] == 'server12.hosting.example', valori())
    scrivi('#email_server', '')
    scrivi('#email_utente', 'info@studio-esempio.it')
    ok('svuotato, torna a seguire l\'indirizzo', valori()[0] == 'mail.studio-esempio.it', valori())
    scrivi('#email_utente', 'clinica.esempio.prova@gmail.com')
    ok('un indirizzo @gmail.com passa a Gmail', pg.input_value('#email_tipo') == 'gmail'
       and valori() == ('smtp.gmail.com', '587', 'starttls') and nascosti_giusti('gmail'), (pg.input_value('#email_tipo'), valori()))

    # la tendina e' fuori dal modulo (attributo form): si salva con il modulo
    scrivi('#email_utente', 'info@studio-esempio.it')
    scegli('aruba')
    pg.fill('#email_password', 'Password di prova')
    pg.click('#modulo-email button[type="submit"]')
    pg.wait_for_load_state()
    pg.wait_for_timeout(300)
    testo_avvisi = ' '.join(pg.locator('.avviso').all_inner_texts())
    ok('salvato con il tipo scelto', 'Impostazioni salvate' in testo_avvisi and pg.input_value('#email_tipo') == 'aruba'
       and valori() == ('smtps.aruba.it', '465', 'ssl') and pg.input_value('#email_utente') == 'info@studio-esempio.it',
       (testo_avvisi[:120], pg.input_value('#email_tipo'), valori()))
    ok('la spia dice email pronte', 'Email: pronte' in pg.text_content('.stato-invii'))

    # schermo stretto
    pg.set_viewport_size({'width': 420, 'height': 800})
    pg.goto(B + '/invii#email')
    pg.wait_for_timeout(300)
    riquadro = pg.evaluate("""(function () {
        var r = document.querySelector('[data-guida="email-tipo"]');
        var s = document.getElementById('email_tipo').getBoundingClientRect();
        return [r.scrollWidth <= r.clientWidth + 1, s.right <= window.innerWidth]; })()""")
    ok('schermo stretto: la tendina del tipo ci sta', all(riquadro), riquadro)
    pg.set_viewport_size({'width': 1366, 'height': 800})

    # si rimette la casella della prova
    pg.goto(B + '/invii#email')
    scegli('dominio')
    scrivi('#email_utente', 'accettazione@example.it')
    pg.fill('#email_password', 'Password-di-prova')
    pg.click('#modulo-email button[type="submit"]')
    pg.wait_for_load_state()
    pg.wait_for_timeout(300)
    ok('rimessa la casella della prova', pg.input_value('#email_tipo') == 'dominio' and valori()[0] == 'mail.example.it', valori())
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
