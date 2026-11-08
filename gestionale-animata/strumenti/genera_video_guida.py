# -*- coding: utf-8 -*-
"""Produce le videoguide (static/video/<articolo>.webm) dalla guida sullo
schermo, sul programma avviato con i DATI DI PROVA, mai con quelli veri: i
video finiscono nel programma.

Per ogni articolo di guida.py apre la pagina indicata in 'foto' con la guida
sullo schermo accesa (?guida=...), fotografa ogni passo (il fumetto e il punto
illuminato, come li vede la segreteria) e monta il video: un cartello con il
titolo, poi passo per passo un puntatore rosso che va sul punto illuminato,
lascia il tempo di leggere il fumetto e preme Avanti; in fondo un cartello
"Fatto". I passi sono gli stessi della guida con le immagini: scritti una
volta sola in guida.py.

    python strumenti/genera_video_guida.py http://127.0.0.1:5000 [articolo ...]

Serve Playwright con Chromium, Pillow e ffmpeg (con libvpx-vp9). Scrive anche
static/video/durate.json (i secondi di ogni video, per "Guarda il video 1:25").
Stampa i passi che la guida sullo schermo non ha trovato: vuol dire che la
guida va corretta, come per le immagini."""
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import guida  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
SCELTI = sys.argv[2:]
USCITA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'video')
L, H = 1366, 768
FPS = 20
ROSSO = (225, 7, 23)

CARTELLO = """(t) => { const d = document.createElement('div'); d.id = 'cartello-video';
  d.style.cssText = 'position:fixed;inset:0;z-index:99999;display:flex;flex-direction:column;align-items:center;' +
    'justify-content:center;background:#14294F;color:#fff;text-align:center;padding:0 80px';
  const riga = (testo, stile) => { const e = document.createElement('div'); e.textContent = testo; e.style.cssText = stile; d.appendChild(e); };
  riga('GESTIONALE AGENDE · VIDEOGUIDA', 'font:600 17px Inter,sans-serif;letter-spacing:.28em;color:#AFC4E2;margin-bottom:22px');
  riga(t.titolo, 'font:800 46px/1.15 Manrope,Inter,sans-serif;max-width:1050px');
  riga(t.sotto, 'font:400 21px/1.4 Inter,sans-serif;color:#D5E2F1;margin-top:20px;max-width:950px');
  if (t.piede) { riga(t.piede, 'font:400 16px Inter,sans-serif;color:#8FA6C6;margin-top:34px'); }
  document.body.appendChild(d); }"""
TOGLI_CARTELLO = "() => { const d = document.getElementById('cartello-video'); if (d) { d.remove(); } }"
STATO = """() => {
  const f = document.querySelector('.giro-fumetto'); if (!f) { return null; }
  const centro = (el) => { if (!el) { return null; } const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
  const l = document.querySelector('.giro-riflettore');
  const conto = (f.querySelector('.giro-conto') || {}).textContent || '';
  const m = conto.match(/(\\d+) di (\\d+)/);
  const r = f.getBoundingClientRect();
  return { luce: l && !l.classList.contains('al-centro') ? centro(l) : null, avanti: centro(f.querySelector('.bottone.primario')),
           fumetto: [r.left, r.top, r.right, r.bottom], testo: (f.querySelector('p') || {}).textContent || '',
           passo: m ? +m[1] : 0, passi: m ? +m[2] : 0 };
}"""


def segnaposto():
    oggi = date.today()
    martedi = oggi - timedelta(days=(oggi.weekday() - 1) % 7)
    return {'oggi': oggi.isoformat(), 'domani': (oggi + timedelta(days=1)).isoformat(),
            'ieri': (oggi - timedelta(days=1)).isoformat(), 'martedi': martedi.isoformat(),
            'mese': oggi.strftime('%Y-%m'),
            'lunedi_prossimo': (oggi + timedelta(days=7 - oggi.weekday())).isoformat()}


def foto(pg):
    return Image.open(io.BytesIO(pg.screenshot())).convert('RGB')


def fotografa(pg, a, valori):
    """I fotogrammi chiave dell'articolo: cartello, un'immagine per passo con
    la posizione del punto illuminato e del pulsante Avanti, cartello finale.
    Restituisce (cartello, passi, fine, passi saltati)."""
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
    pg.goto(B + guida.con_guida(percorso.format(**valori), a['slug']))
    pg.add_style_tag(content='#notifiche, .giro-invito { display: none !important; }')
    pg.evaluate('document.fonts.ready.then(() => true)')
    try:
        pg.wait_for_selector('.giro-fumetto', timeout=8000)
    except Exception:                            # la guida non parte: nessun passo trovato
        pass
    pg.wait_for_timeout(900)                     # la guida si sistema dopo le animazioni d'entrata
    pg.evaluate(CARTELLO, {'titolo': a['titolo'], 'sotto': a['in_breve'], 'piede': '%d passi' % len(a['passi'])})
    pg.wait_for_timeout(150)
    cartello = foto(pg)
    pg.evaluate(TOGLI_CARTELLO)
    passi = []
    while True:
        pg.wait_for_timeout(550)
        s = pg.evaluate(STATO)
        if s is None:
            break
        passi.append((foto(pg), s))
        if s['passo'] >= s['passi']:
            break
        pg.click('.giro-fumetto .bottone.primario')
    totale = passi[0][1]['passi'] if passi else 0
    pg.evaluate(CARTELLO, {'titolo': 'Fatto', 'sotto': 'La stessa guida, passo per passo e con l\'immagine, è in '
                                                         'Aiuto → Come fare… → ' + a['titolo'] + '.',
                           'piede': 'Per farla sulla pagina vera: «Mostrami sullo schermo».'})
    pg.wait_for_timeout(150)
    fine = foto(pg)
    pg.evaluate(TOGLI_CARTELLO)
    return cartello, passi, fine, len(a['passi']) - totale


def puntatori():
    """Il puntatore a varie dimensioni (per il clic che si stringe): immagini RGBA."""
    uscita = {}
    for scala in (1.0, .85, .7, .6):
        r = int(round(13 * scala))
        img = Image.new('RGBA', (2 * r + 8, 2 * r + 8), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([4, 4, 4 + 2 * r, 4 + 2 * r], fill=ROSSO + (95,), outline=ROSSO + (255,), width=3)
        uscita[scala] = img
    return uscita


class Montaggio:
    """I fotogrammi, uno dopo l'altro, mandati a ffmpeg."""

    def __init__(self, destinazione):
        self.n = 0
        self.ffmpeg = subprocess.Popen(
            ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (L, H),
             '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libvpx-vp9', '-crf', '42', '-b:v', '0', '-deadline', 'realtime',
             '-cpu-used', '6', '-row-mt', '1', '-g', str(FPS * 10), '-pix_fmt', 'yuv420p', destinazione],
            stdin=subprocess.PIPE)
        self.sprite = puntatori()

    def scrivi(self, img, volte=1):
        dati = img.tobytes()
        for _ in range(volte):
            self.ffmpeg.stdin.write(dati)
        self.n += volte

    def con_puntatore(self, base, pos, scala=1.0):
        if pos is None:
            return base
        img = base.copy()
        s = self.sprite[scala]
        img.paste(s, (int(pos[0] - s.width / 2), int(pos[1] - s.height / 2)), s)
        return img

    def fermo(self, base, pos, secondi):
        self.scrivi(self.con_puntatore(base, pos), max(1, int(round(secondi * FPS))))

    def sposta(self, base, da, a, secondi):
        """Il puntatore va da 'da' ad 'a' con partenza e arrivo dolci."""
        n = max(1, int(round(secondi * FPS)))
        for i in range(1, n + 1):
            t = i / n
            t = t * t * (3 - 2 * t)
            self.scrivi(self.con_puntatore(base, (da[0] + (a[0] - da[0]) * t, da[1] + (a[1] - da[1]) * t)))

    def clic(self, base, pos):
        for scala in (.85, .7, .6, .6, .7, .85, 1.0):
            self.scrivi(self.con_puntatore(base, pos, scala))

    def dissolvi(self, da, a, pos, secondi):
        n = max(1, int(round(secondi * FPS)))
        for i in range(1, n + 1):
            self.scrivi(self.con_puntatore(Image.blend(da, a, i / n), pos))

    def chiudi(self):
        self.ffmpeg.stdin.close()
        if self.ffmpeg.wait() != 0:
            raise RuntimeError('ffmpeg non ha finito')
        return self.n / FPS


def fuori_dal_fumetto(s):
    """Dove aspetta il puntatore in un passo senza punto illuminato: appena
    fuori dall'angolo in basso a destra del fumetto, per non coprire il testo."""
    x0, y0, x1, y1 = s['fumetto']
    return (min(x1 + 26, L - 20), min(y1 + 22, H - 20)) if x1 + 26 < L - 10 or y1 + 22 < H - 10 else (max(x0 - 26, 20), y1 - 10)


def dentro(pos, s):
    x0, y0, x1, y1 = s['fumetto']
    return x0 - 16 <= pos[0] <= x1 + 16 and y0 - 16 <= pos[1] <= y1 + 16


def monta(destinazione, cartello, passi, fine):
    """Restituisce la durata in secondi."""
    m = Montaggio(destinazione)
    m.fermo(cartello, None, 3.6)
    pos = fuori_dal_fumetto(passi[0][1]) if passi else (L / 2, H / 2)
    precedente = cartello
    for img, s in passi:
        m.dissolvi(precedente, img, None if precedente is cartello else pos, .45)
        if s['luce']:
            m.sposta(img, pos, s['luce'], .75)
            pos = s['luce']
        elif dentro(pos, s):                     # il puntatore coprirebbe il fumetto: si sposta di lato
            nuovo = fuori_dal_fumetto(s)
            m.sposta(img, pos, nuovo, .5)
            pos = nuovo
        m.fermo(img, pos, min(2.6 + .055 * len(s['testo']), 9.0))
        if s['avanti']:
            m.sposta(img, pos, s['avanti'], .65)
            pos = s['avanti']
            m.fermo(img, pos, .25)
            m.clic(img, pos)
        precedente = img
    m.dissolvi(precedente, fine, None, .5)
    m.fermo(fine, None, 3.2)
    return m.chiudi()


def principale():
    if not shutil.which('ffmpeg'):
        print('Serve ffmpeg (con libvpx-vp9).')
        return 2
    os.makedirs(USCITA, exist_ok=True)
    durate_file = os.path.join(USCITA, 'durate.json')
    try:
        with open(durate_file, encoding='utf-8') as f:
            durate = json.load(f)
    except (OSError, ValueError):
        durate = {}
    articoli = [a for a in guida.ARTICOLI if not SCELTI or a['slug'] in SCELTI]
    mancanti = []
    with sync_playwright() as p:
        # date e ore come in Italia: le caselle di data e ora seguono la lingua del browser
        br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None, args=['--lang=it'],
                               env=dict(os.environ, LANG='it_IT.UTF-8', LANGUAGE='it'))
        ctx = br.new_context(viewport={'width': L, 'height': H}, locale='it-IT', timezone_id='Europe/Rome')
        # niente inviti della guida, tema chiaro; le animazioni restano come le vede la segreteria
        ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                            "localStorage.setItem('gestionale-tema','chiaro'); } catch (e) {}")
        pg = ctx.new_page()
        valori = segnaposto()
        for a in articoli:
            cartello, passi, fine, saltati = fotografa(pg, a, valori)
            if saltati or not passi:
                mancanti.append('%s: %d passi su %d non trovati dalla guida sullo schermo' % (a['slug'], saltati, len(a['passi'])))
            destinazione = os.path.join(USCITA, a['slug'] + '.webm')
            secondi = monta(destinazione + '.parziale.webm', cartello, passi, fine)
            os.replace(destinazione + '.parziale.webm', destinazione)
            durate[a['slug']] = round(secondi, 1)
            print('%-18s %2d passi  %5.1f s  %4d KB' % (a['slug'], len(passi), secondi, os.path.getsize(destinazione) // 1024),
                  flush=True)
        br.close()
    validi = {a['slug'] for a in guida.ARTICOLI}
    with open(durate_file, 'w', encoding='utf-8') as f:
        json.dump({k: v for k, v in sorted(durate.items()) if k in validi}, f, ensure_ascii=False, indent=1)
        f.write('\n')
    if mancanti:
        print('\nPassi non trovati:')
        for m in mancanti:
            print('  ' + m)
    return 1 if mancanti else 0


if __name__ == '__main__':
    sys.exit(principale())
