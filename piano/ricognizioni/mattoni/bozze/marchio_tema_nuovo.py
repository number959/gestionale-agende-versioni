# Bozza per marchio.tema() (tappa 1-bis o 2): quattro varianti NUOVE del colore della struttura, per i gettoni della
# veste. Le cinque di oggi (primario, scuro, tenue, chiaro, fuoco) non cambiano: le pagine di oggi restano identiche.
# Con #1C4184 danno #E7EDF9, #BACCED, #112851 (tavola: #E7EEF8, #BCCCEC, #14294F); «testo» è il primario scurito
# finché si legge (4,5:1) anche sulla tinta: con #1C4184 resta #1C4184 (8,4:1), con #0087B4 diventa #007299 (4,8:1).
import colorsys


def _hls(colore):
    return colorsys.rgb_to_hls(*(int(colore[i:i + 2], 16) / 255 for i in (1, 3, 5)))


def _da_hls(h, l, s):
    return '#%02x%02x%02x' % tuple(round(x * 255) for x in colorsys.hls_to_rgb(h, l, s))


def varianti_nuove(base, contrasto):
    """base: il primario già leggibile (tema()['primario']); contrasto: marchio.contrasto."""
    h, l, s = _hls(base)
    tinta = _da_hls(h, .94, min(s, .59))     # voce e linguetta accese
    bordo = _da_hls(h, .83, min(s, .59))     # bordo delle cose scelte
    profondo = _da_hls(h, l * .61, s)        # bottone premuto
    testo = base
    for _ in range(40):                      # il primario come testo, anche sulla tinta
        if contrasto(testo, tinta) >= 4.5:
            break
        testo = '#%02x%02x%02x' % tuple(round(int(testo[i:i + 2], 16) * .92) for i in (1, 3, 5))
    return {'tinta': tinta, 'bordo': bordo, 'profondo': profondo, 'testo': testo}

# in tema():   return {..., **varianti_nuove(base, contrasto)}
# in base.html, nello stesso <style> dello strato:
#   --primario-tinta: {{ tema.tinta }}; --primario-bordo: {{ tema.bordo }};
#   --primario-profondo: {{ tema.profondo }}; --primario-testo: {{ tema.testo }};
