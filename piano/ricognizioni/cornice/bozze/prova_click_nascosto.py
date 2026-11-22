from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page()
    pg.goto('http://127.0.0.1:5142/oggi')
    # un collegamento nascosto con hidden, come uno dentro un riquadro chiuso
    pg.evaluate("""() => { const d = document.createElement('div'); d.hidden = true;
       const a = document.createElement('a'); a.href = '/elenco'; a.setAttribute('data-tasto', 'zz'); d.appendChild(a);
       document.body.appendChild(d); a.click(); }""")
    pg.wait_for_timeout(800)
    print('dopo click su <a> dentro un div hidden:', pg.url)
    br.close()
