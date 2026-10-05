# -*- coding: utf-8 -*-
"""Produce le immagini della guida (static/guida/<articolo>.png) fotografando
il programma avviato con i DATI DI PROVA, mai con quelli veri: le immagini
finiscono nel programma e nella guida stampata.

Per ogni articolo di guida.py apre la pagina indicata in 'foto', trova gli
elementi dei passi con lo stesso criterio della guida sullo schermo, li
contorna e ci mette il numero del passo, poi ritaglia la parte che serve.

    python strumenti/genera_immagini_guida.py http://127.0.0.1:5000 [cartella]

Serve Playwright con Chromium e Pillow. Stampa i passi il cui elemento non
e' stato trovato: vuol dire che la guida va corretta."""
import io
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import guida  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
USCITA = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'guida')
LARGHEZZA_MASSIMA = 1100
ROSSO = (208, 52, 44)

TROVA = """(p) => {
  let tutti; try { tutti = document.querySelectorAll(p.sel); } catch (e) { return null; }
  for (const el of tutti) {
    if (p.contiene && !(el.textContent || '').includes(p.contiene)) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden') {
      return {x: r.left + window.scrollX, y: r.top + window.scrollY, w: r.width, h: r.height};
    }
  }
  return null;
}"""


def carattere(dim):
    for f in ('C:/Windows/Fonts/segoeuib.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(f):
            return ImageFont.truetype(f, dim)
    return ImageFont.load_default()


def segna(img, caselle):
    d = ImageDraw.Draw(img)
    f = carattere(15)
    for n, (x, y, w, h) in caselle:
        d.rounded_rectangle([x - 5, y - 5, x + w + 5, y + h + 5], radius=6, outline=ROSSO, width=3)
    for n, (x, y, w, h) in caselle:
        cx, cy, r = max(15, x - 6), max(15, y - 6), 14
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ROSSO, outline=(255, 255, 255), width=2)
        t = str(n)
        l, a, dx, dy = d.textbbox((0, 0), t, font=f)
        d.text((cx - (dx - l) / 2 - l, cy - (dy - a) / 2 - a), t, fill=(255, 255, 255), font=f)
    return img


def segnaposto(pagina_):
    oggi = date.today()
    martedi = oggi - timedelta(days=(oggi.weekday() - 1) % 7)
    return {'oggi': oggi.isoformat(), 'domani': (oggi + timedelta(days=1)).isoformat(),
            'ieri': (oggi - timedelta(days=1)).isoformat(), 'martedi': martedi.isoformat(),
            'mese': oggi.strftime('%Y-%m')}


def principale():
    os.makedirs(USCITA, exist_ok=True)
    mancanti = []
    with sync_playwright() as p:
        # date e ore come in Italia: le caselle di data e ora seguono la lingua del browser
        br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None, args=['--lang=it'],
                               env=dict(os.environ, LANG='it_IT.UTF-8', LANGUAGE='it'))
        # in italiano, come sul PC dell'accettazione: date gg/mm/aaaa e ore a 24 ore
        ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT', timezone_id='Europe/Rome')
        # niente inviti della guida e niente notifiche nelle foto
        ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                            "localStorage.setItem('gestionale-animazioni','spente'); localStorage.setItem('gestionale-tema','chiaro'); } catch (e) {}")
        pg = ctx.new_page()
        valori = segnaposto(pg)
        for a in guida.ARTICOLI:
            if not a.get('foto'):
                continue
            percorso = a['foto']
            if '{app_esempio}' in percorso:
                pg.goto(B + '/giorno/%s?struttura=1' % valori['martedi'])
                href = pg.locator('a.voce').first.get_attribute('href')
                valori['app_esempio'] = href.split('/appuntamento/')[1].split('?')[0]
            if '{paziente_esempio}' in percorso:
                # la scheda di un paziente di prova con il codice fiscale giusto (Fintini Prova)
                pg.goto(B + '/pazienti?q=Fintini')
                href = pg.locator('table.elenco a[href*="/pazienti/"]').first.get_attribute('href')
                valori['paziente_esempio'] = href.rstrip('/').split('/')[-1]
            pg.goto(B + percorso.format(**valori))
            pg.add_style_tag(content='#notifiche, .giro-invito { display: none !important; } '
                                     '*, *::before, *::after { animation: none !important; transition: none !important; }')
            pg.wait_for_timeout(500)
            caselle = []
            for i, passo in enumerate(a['passi'], 1):
                if 'sel' not in passo:
                    continue
                r = pg.evaluate(TROVA, passo)
                if r is None:
                    mancanti.append('%s, passo %d: %s %s' % (a['slug'], i, passo['sel'], passo.get('contiene', '')))
                    continue
                caselle.append((i, (r['x'], r['y'], r['w'], r['h'])))
            img = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert('RGB')
            if caselle:
                segna(img, caselle)
                # si ritaglia intorno ai punti segnati, con un po' di contesto
                x0 = min(x for _, (x, y, w, h) in caselle) - 60
                y0 = min(y for _, (x, y, w, h) in caselle) - 70
                x1 = max(x + w for _, (x, y, w, h) in caselle) + 60
                y1 = max(y + h for _, (x, y, w, h) in caselle) + 70
                if x1 - x0 < 900:
                    c = (x0 + x1) / 2
                    x0, x1 = c - 450, c + 450
                if y1 - y0 < 380:
                    y1 = y0 + 380
                if y1 > img.height:            # in fondo alla pagina: il contesto si prende sopra
                    y0, y1 = y0 - (y1 - img.height), img.height
                x0, y0 = max(0, x0), max(0, y0)
                x1, y1 = min(img.width, x1), min(img.height, y1)
                img = img.crop((int(x0), int(y0), int(x1), int(y1)))
            else:
                img = img.crop((0, 0, img.width, min(img.height, 820)))
            if img.width > LARGHEZZA_MASSIMA:
                img = img.resize((LARGHEZZA_MASSIMA, int(img.height * LARGHEZZA_MASSIMA / img.width)), Image.LANCZOS)
            img = img.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE)
            img.save(os.path.join(USCITA, a['slug'] + '.png'), optimize=True)
            print('%-18s %d segni  %dx%d' % (a['slug'], len(caselle), img.width, img.height))
        br.close()
    if mancanti:
        print('\nElementi non trovati:')
        for m in mancanti:
            print('  ' + m)
    return 1 if mancanti else 0


if __name__ == '__main__':
    sys.exit(principale())
