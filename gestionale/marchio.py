# -*- coding: utf-8 -*-
"""Logo e colori di ogni struttura.

Il file caricato va trattato come ostile: si accetta solo cio' che Pillow
riesce davvero a decodificare come immagine raster, e se ne salva una copia
ricodificata in PNG. Cosi' nel database non finisce mai il file originale,
con i suoi metadati o con quello che ci e' stato nascosto dentro. L'SVG non
e' ammesso: puo' contenere script.
"""
import colorsys
import re
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MASSIMO_BYTE = 3 * 1024 * 1024          # file caricato
ALTEZZA_MAX = 160                       # a video il logo e' alto 27-40 px: 160 basta anche per gli schermi ad alta densita'
LARGHEZZA_MAX = 800
FORMATI = {'PNG', 'JPEG', 'GIF', 'WEBP', 'BMP'}
# oltre 40 milioni di pixel Pillow alza un errore invece di riempire la
# memoria: un PNG di pochi KB puo' dichiarare 100.000 x 100.000 pixel
Image.MAX_IMAGE_PIXELS = 40_000_000

COLORE = re.compile(r'#[0-9A-Fa-f]{6}')


class LogoNonValido(ValueError):
    """Il messaggio e' pensato per chi carica il file: va mostrato cosi' com'e'."""


def normalizza_logo(dati):
    """Da un file caricato a un PNG pulito, rifilato e di misura ragionevole."""
    if not dati:
        raise LogoNonValido('Il file è vuoto.')
    if len(dati) > MASSIMO_BYTE:
        raise LogoNonValido('Il file supera 3 MB: usare un logo più leggero.')
    try:
        with Image.open(BytesIO(dati)) as prova:
            formato = prova.format
            prova.verify()                  # struttura del file integra
        im = Image.open(BytesIO(dati))
        im.load()                           # decodifica vera: qui emergono i file troncati
    except Image.DecompressionBombError:
        raise LogoNonValido('L\'immagine è troppo grande: usare un logo più piccolo.')
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError):
        raise LogoNonValido('Il file non è un\'immagine leggibile: usare un PNG o un JPG.')
    if formato not in FORMATI:
        raise LogoNonValido('Formato %s non ammesso: usare un PNG o un JPG.' % formato)

    if getattr(im, 'n_frames', 1) > 1:
        im.seek(0)                          # GIF animata: vale il primo fotogramma
    im = ImageOps.exif_transpose(im)        # le foto da telefono arrivano ruotate
    im = im.convert('RGBA')
    im = rifila(im)
    if im.width < 8 or im.height < 8:
        raise LogoNonValido('Il logo è troppo piccolo: servono almeno 8 pixel per lato.')

    scala = min(1.0, ALTEZZA_MAX / im.height, LARGHEZZA_MAX / im.width)
    if scala < 1.0:
        im = im.resize((max(1, round(im.width * scala)), max(1, round(im.height * scala))),
                       Image.LANCZOS)
    im = togli_sfondo(im)          # dopo il ridimensionamento: meno pixel da visitare
    uscita = BytesIO()
    im.save(uscita, 'PNG', optimize=True)
    return uscita.getvalue()


def rifila(im):
    """Toglie i margini vuoti, trasparenti o bianchi: i loghi arrivano spesso
    con molto spazio attorno e a video risulterebbero minuscoli."""
    r, g, b, a = im.split()
    # contenuto = pixel non trasparente e non quasi bianco
    quasi_bianco = Image.merge('RGB', (r, g, b)).convert('L').point(lambda v: 255 if v > 245 else 0)
    visibile = a.point(lambda v: 255 if v > 16 else 0)
    contenuto = Image.composite(Image.new('L', im.size, 0), visibile, quasi_bianco)
    riquadro = contenuto.getbbox()
    if riquadro is None:
        raise LogoNonValido('Il logo risulta vuoto: è tutto bianco o trasparente.')
    return im.crop(riquadro)


def togli_sfondo(im):
    """I loghi in JPG arrivano con lo sfondo bianco, che sulle pagine a fondo
    grigio diventa un riquadro. Si rende trasparente solo il bianco collegato
    ai bordi: quello dentro il disegno (una lettera, un cerchio) resta."""
    from PIL import ImageDraw
    if im.getextrema()[3][0] < 255:
        return im                    # ha gia' la sua trasparenza: e' voluta
    im = im.copy()
    larghezza, altezza = im.size
    bordo = ([(x, 0) for x in range(larghezza)] + [(x, altezza - 1) for x in range(larghezza)] +
             [(0, y) for y in range(altezza)] + [(larghezza - 1, y) for y in range(altezza)])
    for xy in bordo:
        r, g, b, a = im.getpixel(xy)
        if a == 255 and min(r, g, b) > 235:
            # il riempimento cambia l'alfa: un pixel gia' tolto non viene rivisitato
            ImageDraw.floodfill(im, xy, (255, 255, 255, 0), thresh=40)
    return im


def stesso_logo(a, b, tolleranza=8.0):
    """Due loghi (PNG o altro formato leggibile) sono lo stesso disegno? Si
    confrontano le proporzioni e una miniatura in grigi sul bianco: regge a
    ridimensionamenti, ricodifiche e piccole differenze di bordo, non a un
    logo diverso. Serve per riconoscere un logo vecchio e sostituirlo."""
    def miniatura(dati):
        im = Image.open(BytesIO(dati)).convert('RGBA')
        fondo = Image.new('RGBA', im.size, (255, 255, 255, 255))
        grigi = Image.alpha_composite(fondo, im).convert('L')
        # il disegno vero, non gli aloni chiari di un JPG ai bordi
        riquadro = grigi.point(lambda v: 255 if v < 200 else 0).getbbox()
        if riquadro is None:
            raise ValueError('logo vuoto')
        grigi = grigi.crop(riquadro)
        return grigi.width / grigi.height, grigi.resize((96, 16), Image.BILINEAR)
    if not a or not b:
        return False
    try:
        (pa, ma), (pb, mb) = miniatura(a), miniatura(b)
    except (UnidentifiedImageError, OSError, ValueError, LogoNonValido, Image.DecompressionBombError):
        return False
    if abs(pa - pb) > 0.05 * max(pa, pb):
        return False
    da = ma.get_flattened_data() if hasattr(ma, 'get_flattened_data') else ma.getdata()
    db = mb.get_flattened_data() if hasattr(mb, 'get_flattened_data') else mb.getdata()
    diff = sum(abs(x - y) for x, y in zip(da, db)) / (96 * 16)
    return diff <= tolleranza


def colore_dominante(png):
    """Il colore che caratterizza il logo, da proporre come colore
    dell'interfaccia. None se il logo e' in bianco e nero."""
    im = Image.open(BytesIO(png)).convert('RGBA')
    im.thumbnail((160, 160))
    gruppi = {}
    # getdata e' deprecato da Pillow 12; i requisiti ammettono anche la 11.3,
    # che il metodo nuovo non ce l'ha
    pixel = im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()
    for r, g, b, a in pixel:
        if a < 200:
            continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        # grigi e bianchi hanno saturazione bassa, i neri luminosita' bassa: non
        # caratterizzano il marchio. La luminosita' alta invece non esclude
        # nulla: il giallo pieno ha luminosita' 1 ed e' un colore a tutti gli effetti
        if s < 0.30 or v < 0.18:
            continue
        chiave = (r >> 4, g >> 4, b >> 4)
        somma = gruppi.setdefault(chiave, [0, 0, 0, 0])
        somma[0] += r
        somma[1] += g
        somma[2] += b
        somma[3] += 1
    if not gruppi:
        return None
    r, g, b, n = max(gruppi.values(), key=lambda x: x[3])
    if n < 12:
        return None                           # pochi pixel sparsi: non e' il colore del marchio
    return '#%02x%02x%02x' % (r // n, g // n, b // n)


# ================================================================ colori
def _rgb(colore):
    return tuple(int(colore[i:i + 2], 16) for i in (1, 3, 5))


def _esadecimale(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, round(x))) for x in rgb)


def luminanza(colore):
    """Luminanza relativa secondo le WCAG."""
    def canale(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canale(x) for x in _rgb(colore))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrasto(a, b):
    la, lb = sorted((luminanza(a), luminanza(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def leggibile(colore, minimo=4.5):
    """Scurisce il colore finche' il testo bianco sopra si legge: le intestazioni
    e i pulsanti hanno testo bianco, e un giallo chiaro li renderebbe illeggibili.
    La tinta resta quella scelta."""
    if not COLORE.fullmatch(colore or ''):
        return None
    rgb = _rgb(colore)
    for _ in range(40):
        c = _esadecimale(rgb)
        if contrasto(c, '#ffffff') >= minimo:
            return c
        rgb = tuple(x * 0.92 for x in rgb)
    return _esadecimale(rgb)


def mescola(colore, altro, quota):
    """quota 0 = colore, 1 = altro."""
    a, b = _rgb(colore), _rgb(altro)
    return _esadecimale(tuple(x + (y - x) * quota for x, y in zip(a, b)))


def tema(colore):
    """Le varianti del colore principale usate dal foglio di stile."""
    base = leggibile(colore) or '#154381'
    return {
        'primario': base,
        'scuro': mescola(base, '#000000', 0.28),          # passaggio del mouse, collegamenti
        'tenue': mescola(base, '#ffffff', 0.92),          # fondo delle fasce libere al passaggio
        'chiaro': mescola(base, '#ffffff', 0.62),         # testo secondario sulle intestazioni
        'fuoco': mescola(base, '#ffffff', 0.25),          # contorno del campo attivo
    }
