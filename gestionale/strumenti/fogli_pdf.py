# -*- coding: utf-8 -*-
"""I 9 fogli da stampare e le 8 pagine che si stampano, in PDF, confrontati pixel per pixel: lo usa
strumenti/confronta_rami.py (tappa 1 della base, 22/11/2026; le 8 pagine dalla tappa 2).

I «fogli da stampare» sono i 9 modelli con `{% set foglio_carta = true %}` e il blocco menu vuoto
(agenda_medico, aiuto_stampa, dove_stampa, lista_operatoria, promemoria, riepilogo_medici, stampa,
stampa_modulo, tariffario_stampa). Le «pagine che si stampano» sono 8 pagine di tutti i giorni, con il menu,
che si stampano con Ctrl+P (mese e settimana dell'Agenda, cassa del giorno e del mese, settimana, mese e
riepilogo degli Ambulatori, il mese dei Turni): la veste nuova le cambia a schermo, ma stampate restano
identiche a oggi (decisione del 22/11/2026). Il lanciatore li incontra già seguendo i collegamenti (provato: tutti
e 17, sulle 607 pagine del giro). Di ogni foglio si prendono le PER_TIPO pagine più piene (byte dell'HTML),
una per variante d'indirizzo, e la più vuota; si fa il PDF con Chromium come Ctrl+P (A4, formato e margini da
@page di stile.css, sfondi come Chrome di partenza: solo dove il CSS dice print-color-adjust: exact), lo si
trasforma in immagini con pdftoppm e si confronta con Pillow: stesso numero di pagine, nessun pixel diverso.
Le pagine con il menu si stampano un momento dopo che si sono aperte (ASPETTA_PAGINE), come chi preme Ctrl+P:
nell'animata i numeri contano fino al valore per meno di un secondo.

Data e ora di stampa («stampato il 22/11/2026 alle 09:41», «aggiornata al …», «… il 22/11/2026.») si
scrivono uguali nelle due pagine prima del PDF (solo le cifre), e un foglio diverso si rifà una volta.

Senza pdftoppm (Windows): foto della pagina intera con i CSS di stampa (emulate_media), larga come un
A4 orizzontale; vede meno (niente salti pagina, margini di @page né «Pagina X di Y»), e lo dice.
"""
import os
import re
import shutil
import subprocess

# nome, modello, indirizzo (senza la ?…), pagina con il menu. L'indirizzo serve solo se il programma non manda
# X-Modelli, o se il modello fa anche altre pagine (DA_INDIRIZZO): il mese dei Turni ha il modello della settimana dei
# Turni, il riepilogo degli Ambulatori quello del riepilogo della dashboard (/riepilogo-live/statistiche).
FOGLI = (
    ('stampa', 'stampa', r'/stampa/\d{4}-\d\d-\d\d', False),
    ('agenda_medico', 'agenda_medico', r'/agenda-medico/\d{4}-\d\d-\d\d', False),
    ('lista_operatoria', 'lista_operatoria', r'/lista-operatoria/\d{4}-\d\d-\d\d', False),
    ('promemoria', 'promemoria', r'/appuntamento/\d+/promemoria', False),
    ('riepilogo_medici', 'riepilogo_medici', r'/riepilogo-medici/\d{4}-\d\d', False),
    ('stampa_modulo', 'stampa_modulo', r'/appuntamento/\d+/modulo/\d+', False),
    ('tariffario_stampa', 'tariffario_stampa', r'/cassa/tariffari/\d+/stampa', False),
    ('dove_stampa', 'dove_stampa', r'/dove-si-fa/stampa', False),
    ('aiuto_stampa', 'aiuto_stampa', r'/aiuto/stampa', False),
    # le 8 pagine che si stampano (dalla tappa 2)
    ('mese', 'mese', r'/mese/\d{4}-\d\d', True),
    ('settimana', 'settimana', r'/settimana/\d{4}-\d\d-\d\d', True),
    ('cassa', 'cassa', r'/cassa/\d{4}-\d\d-\d\d', True),
    ('cassa_mese', 'cassa_mese', r'/cassa/mese/\d{4}-\d\d', True),
    ('ambulatori_settimana', 'ambulatori_settimana', r'/ambulatori/settimana/\d{4}-\d\d-\d\d', True),
    ('ambulatori_mese', 'ambulatori_mese', r'/ambulatori/mese/\d{4}-\d\d', True),
    ('ambulatori_riepilogo', 'ambulatori_riepilogo', r'/ambulatori/riepilogo', True),
    ('turni_mese', 'personale_turni', r'/personale/turni/mese/(\d{4}-\d\d)?', True),
)
DA_INDIRIZZO = {'personale_turni', 'ambulatori_riepilogo'}   # modelli di più pagine: conta anche l'indirizzo
CON_MENU = {n for n, _, _, menu in FOGLI if menu}
ASPETTA_PAGINE = 1200                                # millisecondi, solo per le pagine con il menu
PER_TIPO = 3
DPI = 100                                            # A4 orizzontale = 1170×827 pixel
LARGHEZZA_A4 = 1123                                  # 297 mm a 96 punti per pollice (solo senza pdftoppm)

# Per ESEGUI di confronta_rami.py: il modello che ha fatto la pagina, in un'intestazione. Il programma non
# cambia: è il segnale template_rendered di Flask, agganciato solo nel processo del lanciatore.
AGGANCIO_MODELLI = r'''
import flask
def _segna(mittente, template, context, **extra):
    if flask.has_request_context():
        flask.g.setdefault('_modelli', []).append(template.name)
flask.template_rendered.connect(_segna, A.app)
@A.app.after_request
def _intestazione(r):
    r.headers['X-Modelli'] = ' '.join(flask.g.get('_modelli', []))
    return r
'''

# Le cifre di data e ora di stampa diventano sempre le stesse: il resto della frase resta, così un formato
# cambiato si vede lo stesso. Solo nei nodi di testo. Torna quante frasi ha cambiato (si confronta anche quello).
NORMALIZZA_ORA = r"""() => {
  const regole = [
    [/(stampato il )\d\d\/\d\d\/\d{4}( alle )\d\d:\d\d/g, '$101/01/2000$200:00'],
    [/(aggiornata al )\d\d\/\d\d\/\d{4}/g, '$101/01/2000'],
    [/(Indicazioni date dalla segreteria[^\n]*? il )\d\d\/\d\d\/\d{4}/g, '$101/01/2000'],
  ];
  const giro = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n = 0;
  for (let t = giro.nextNode(); t; t = giro.nextNode()) {
    let v = t.nodeValue;
    for (const [rx, con] of regole) { v = v.replace(rx, con); }
    if (v !== t.nodeValue) { t.nodeValue = v; n++; }
  }
  return n;
}"""

PRONTA = "() => document.fonts.ready.then(() => Array.from(document.images).every(i => i.complete))"


def tipo_di(percorso, modelli=None):
    """Quale foglio è (o None): dall'intestazione X-Modelli se c'è, altrimenti dall'indirizzo. Il modello che fa più
    pagine (DA_INDIRIZZO) vale solo con il suo indirizzo."""
    strada = percorso.split('?')[0]
    if modelli is not None:
        nomi = {m[:-5] for m in modelli.split() if m.endswith('.html')}
        return next((n for n, modello, rx, _ in FOGLI if modello in nomi
                     and (modello not in DA_INDIRIZZO or re.fullmatch(rx, strada))), None)
    return next((n for n, _, rx, _ in FOGLI if re.fullmatch(rx, strada)), None)


def scegli_fogli(viste, per_tipo=PER_TIPO):
    """viste: [(percorso, X-Modelli o None, byte dell'HTML)] nell'ordine del giro, solo risposte 200.
    Di ogni foglio le per_tipo pagine più piene, una per variante (indirizzo con le cifre scritte N).
    Torna ([(modello, percorso)], [fogli mai incontrati])."""
    per_foglio = {}
    for percorso, modelli, byte in viste:
        t = tipo_di(percorso, modelli)
        if t:
            per_foglio.setdefault(t, []).append((percorso, byte))
    scelti = []
    for nome, _, _, _ in FOGLI:
        varianti, questi = set(), []
        pagine = sorted(per_foglio.get(nome, []), key=lambda x: -x[1])               # sorted è stabile
        for percorso, _ in pagine:
            v = re.sub(r'\d+', 'N', percorso)
            if v not in varianti and len(varianti) < per_tipo:
                varianti.add(v)
                questi.append(percorso)
        if pagine and pagine[-1][0] not in questi:        # e la più vuota («Nessun appuntamento»…)
            questi.append(pagine[-1][0])
        scelti += [(nome, p) for p in questi]
    return scelti, [n for n, _, _, _ in FOGLI if n not in per_foglio]


def stampa_pdf(pagina, base, percorso, file_pdf, aspetta=0):
    """Il PDF come Ctrl+P di Chrome. Torna (stato HTTP, quante date di stampa scritte uguali)."""
    r = pagina.goto(base + percorso, wait_until='load')
    pagina.evaluate(PRONTA)
    if aspetta:
        pagina.wait_for_timeout(aspetta)
    n = pagina.evaluate(NORMALIZZA_ORA)
    pagina.pdf(path=file_pdf, format='A4', prefer_css_page_size=True, print_background=False)
    return (r.status if r else 0), n


def foto_stampa(pagina, base, percorso, file_png, aspetta=0):
    """Senza pdftoppm: la pagina intera con i CSS di stampa, larga come un A4 orizzontale."""
    pagina.set_viewport_size({'width': LARGHEZZA_A4, 'height': 794})
    pagina.emulate_media(media='print')
    r = pagina.goto(base + percorso, wait_until='load')
    pagina.evaluate(PRONTA)
    if aspetta:
        pagina.wait_for_timeout(aspetta)
    n = pagina.evaluate(NORMALIZZA_ORA)
    pagina.screenshot(path=file_png, full_page=True, animations='disabled', caret='hide')
    return (r.status if r else 0), n


def in_immagini(file_pdf, dpi=DPI):
    """Le pagine del PDF in PNG con pdftoppm, accanto al PDF: elenco in ordine di pagina."""
    radice = file_pdf[:-4]
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', file_pdf, radice], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cartella, nome = os.path.split(radice)
    return sorted((os.path.join(cartella, f) for f in os.listdir(cartella)
                   if re.fullmatch(re.escape(nome) + r'-\d+\.png', f)),
                  key=lambda f: int(re.search(r'-(\d+)\.png$', f).group(1)))


def pixel_diversi(file_a, file_b, file_diff=None):
    """(pixel diversi, riquadro) fra due PNG; con file_diff salva la pagina A schiarita con i pixel diversi in rosso."""
    from PIL import Image, ImageChops
    a, b = Image.open(file_a).convert('RGB'), Image.open(file_b).convert('RGB')
    if a.size != b.size:
        return a.size[0] * a.size[1], (0, 0) + a.size
    d = ImageChops.difference(a, b).convert('L').point(lambda v: 255 if v else 0)
    quanti = d.histogram()[255]
    if quanti and file_diff:
        Image.composite(Image.new('RGB', a.size, (230, 0, 0)), a.point(lambda v: 160 + v * 95 // 255), d).save(file_diff)
    return quanti, d.getbbox()


def confronta_foglio(pagine, basi, percorso, cartella, tolleranza=0, aspetta=0):
    """Un foglio sui due programmi (pagine e basi: {'principale': …, 'qui': …}). [] se uguali."""
    os.makedirs(cartella, exist_ok=True)
    con_pdf = shutil.which('pdftoppm') is not None
    immagini, stati = {}, {}
    for lato in ('principale', 'qui'):
        if con_pdf:
            f = os.path.join(cartella, lato + '.pdf')
            stati[lato] = stampa_pdf(pagine[lato], basi[lato], percorso, f, aspetta)
            immagini[lato] = in_immagini(f)
        else:
            f = os.path.join(cartella, lato + '.png')
            stati[lato] = foto_stampa(pagine[lato], basi[lato], percorso, f, aspetta)
            immagini[lato] = [f]
    righe = []
    if stati['principale'] != stati['qui']:
        righe.append('risposta e frasi con la data di stampa: principale %r; qui %r' % (stati['principale'], stati['qui']))
    ia, ib = immagini['principale'], immagini['qui']
    if len(ia) != len(ib):
        righe.append('pagine: principale %d; qui %d' % (len(ia), len(ib)))
    for i, (a, b) in enumerate(zip(ia, ib), 1):
        diff = os.path.join(cartella, 'differenza-%d.png' % i)
        quanti, riquadro = pixel_diversi(a, b, diff)
        if quanti > tolleranza:
            righe.append('pagina %d: %d pixel diversi nel riquadro %s (in rosso: %s)' % (i, quanti, riquadro, diff))
    return righe


def confronta_fogli(porte, viste, uscita, per_tipo=PER_TIPO, tolleranza=0):
    """Dopo il giro delle pagine, con i due programmi ancora accesi. uscita: una cartella che resta (le
    immagini dei fogli diversi), non quella temporanea che confronta_rami.py cancella alla fine.
    Torna (righe del resoconto, fogli confrontati, fogli diversi, fogli mai incontrati)."""
    from playwright.sync_api import sync_playwright
    scelti, mancanti = scegli_fogli(viste, per_tipo)
    basi = {lato: 'http://127.0.0.1:%d' % porte[lato] for lato in porte}
    righe, diversi = [], 0
    if not shutil.which('pdftoppm'):
        righe.append('(senza pdftoppm: confrontate le foto in modo stampa, senza salti pagina né numeri di pagina)')
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
        ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT', timezone_id='Europe/Rome')
        ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); "
                            "localStorage.setItem('gestionale-tema','chiaro'); } catch (e) {}")
        pagine = {lato: ctx.new_page() for lato in basi}
        for k, (nome, percorso) in enumerate(scelti, 1):
            cartella = os.path.join(uscita, '%02d-%s' % (k, nome))
            aspetta = ASPETTA_PAGINE if nome in CON_MENU else 0
            differenze = confronta_foglio(pagine, basi, percorso, cartella, tolleranza, aspetta)
            if differenze:                                   # un caso a metà di qualcosa: una volta ancora
                shutil.rmtree(cartella, ignore_errors=True)
                differenze = confronta_foglio(pagine, basi, percorso, cartella, tolleranza, aspetta)
            if differenze:
                diversi += 1
                righe.append('FOGLIO DIVERSO %s (%s)\n  %s' % (percorso, nome, '\n  '.join(differenze)))
            else:
                shutil.rmtree(cartella, ignore_errors=True)  # restano solo le cartelle dei fogli diversi
        br.close()
    if mancanti:
        righe.append('FOGLI MAI INCONTRATI nel giro: %s' % ', '.join(mancanti))
    return righe, len(scelti), diversi, mancanti
