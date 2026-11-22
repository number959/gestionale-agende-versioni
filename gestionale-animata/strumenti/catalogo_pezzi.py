# -*- coding: utf-8 -*-
"""Il catalogo dei pezzi della veste nuova (tappa 1-bis, 22/11/2026): una pagina con ogni pezzo di templates/_pezzi.html
negli stati che ha davvero, i gettoni di static/gettoni.css con i loro contrasti e le scale, in chiaro e in scuro. Per le
foto da far approvare a Giovanni e per chi fa le pagine.

    python strumenti/catalogo_pezzi.py                     # http://127.0.0.1:5141/catalogo-pezzi
    python strumenti/catalogo_pezzi.py --porta 5077
    python strumenti/catalogo_pezzi.py --foto CARTELLA     # le foto a 1366, 1024 e 683 px, in chiaro e in scuro

È un gestionale di prova a sé: i dati inventati di strumenti/dati_prova.py con nomi_inventati (nome, indirizzo e logo
della clinica e i due medici veri diventano inventati; il colore resta quello della clinica), in una cartella
temporanea, niente invii. Il modello (strumenti/catalogo_pezzi.html) e questo file stanno in strumenti/: non entrano
nell'eseguibile (gestionale.spec porta solo templates/ e static/), e l'indirizzo /catalogo-pezzi non esiste nel
programma vero né nel gestionale di prova di demo.py (che dalla tappa 1 non cambia: il lanciatore lo usa).
?colore=1C4184 mostra il catalogo con un altro colore della struttura (quello delle tavole)."""
import argparse
import os
import re
import sys
import tempfile
import threading

QUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(QUI)
sys.path.insert(0, SRC)

# i valori delle tavole Nefro che diventano ogni passo delle scale (misurati sulle 58 tavole con il blu del gruppo)
SCALA_SPAZI = [('spazio-1', '2px', '1, 2, 3 px'), ('spazio-2', '4px', '4, 5 px'), ('spazio-3', '6px', '6, 7 px'),
               ('spazio-4', '8px', '8, 9, 10 px'), ('spazio-5', '12px', '11, 12, 13, 14 px'),
               ('spazio-6', '16px', '16, 18 px'), ('spazio-7', '20px', '20, 22 px'), ('spazio-8', '24px', '24, 26, 28 px'),
               ('spazio-9', '36px', '30, 32, 36, 40, 44, 48 px')]
SCALA_RAGGI = [('raggio-1', '4px', '1, 2, 3, 4, 5 px: segni, barrette, legenda'),
               ('raggio-2', '8px', '6, 7, 8, 9 px: linguette, contatori'),
               ('raggio-3', '12px', '10, 11, 12, 14 px: bottoni, campi, voci del menu'),
               ('raggio-4', '16px', '16, 18, 20 px: schede, barre, sezioni'),
               ('raggio-pieno', '999px', '999px, 100px, 50%: pillole e cerchi')]
SCALA_CARATTERI = [('xs', '12px', '9, 10,5, 11, 11,5, 12', False), ('s', '12,5px', '12,5, 13', False),
                   ('m', '13,5px', '13,5', False), ('n', '14px', '14, 14,5 (il corpo resta 14 come oggi)', False),
                   ('l', '15px', '15, 15,5, 16', False), ('t3', '18px', '17, 18', True), ('t2', '22px', '20, 22, 24', True),
                   ('num', '30px', '26, 28, 30', True), ('t1', '36px', '34, 36, 40, 44, 46', True)]
LARGHEZZE = (1366, 1024, 683)
ALTEZZA = 657


def prepara(cartella_dati):
    """Il database del catalogo: i dati di prova con i nomi inventati. Torna il modulo app pronto."""
    os.environ.setdefault('GESTIONALE_PROVE_RIGIDE', '1')
    os.chdir(SRC)
    import app as A
    import viste
    from strumenti import dati_prova
    S = dati_prova.fai_dati(os.path.join(cartella_dati, 'catalogo.db'))
    rimasti = dati_prova.nomi_inventati(S)
    if rimasti:
        raise SystemExit('nomi della clinica rimasti nei dati del catalogo: %s' % '; '.join(rimasti))
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return A


def registra(A):
    """Aggiunge /catalogo-pezzi all'applicazione (solo in questo gestionale di prova)."""
    from flask import Blueprint, render_template, request
    import marchio
    from modelli import STATI, COLORE_PREDEFINITO
    from strumenti import leggi_gettoni as L
    bp = Blueprint('catalogo_pezzi', __name__, template_folder=QUI)

    @bp.route('/catalogo-pezzi')
    def pagina():
        richiesto = (request.args.get('colore') or '').lstrip('#')
        struttura = A.marchio_di(1)
        colore = ('#' + richiesto) if re.fullmatch(r'[0-9A-Fa-f]{6}', richiesto) else struttura['tema']['primario']
        tema = marchio.tema(colore)

        def marchio_di(sid=None):           # il colore scelto, per base.html
            return dict(A.marchio_di(sid), tema=tema)
        chiaro, scuro = L.Valori(colore, 'chiaro'), L.Valori(colore, 'scuro')
        gettoni = [dict(nome=n[2:], chiaro=chiaro.risolvi(n) or chiaro.v[n], scuro=scuro.risolvi(n) or scuro.v[n])
                   for n in L.gettoni_css(L.leggi(os.path.join('static', 'gettoni.css')))[0]
                   if chiaro.risolvi(n)]
        c_chiaro, c_scuro = L.contrasti(colore, 'chiaro'), L.contrasti(colore, 'scuro')
        coppie = [dict(testo=t, fondo=f, dove=d, chiaro=x, scuro=y[3]) for (t, f, d, x), y in zip(c_chiaro, c_scuro)]
        return render_template('catalogo_pezzi.html', sid=1, marchio_di=marchio_di, struttura=struttura['nome'],
                               colore=tema['primario'], colore_della_clinica=not richiesto and colore == struttura['tema']['primario'],
                               gettoni=gettoni, coppie=coppie, colori_provati=len(L.COLORI_DI_PROVA + L.griglia_di_colori()),
                               scala_spazi=SCALA_SPAZI, scala_raggi=SCALA_RAGGI, scala_caratteri=SCALA_CARATTERI, stati=STATI,
                               predefinito=COLORE_PREDEFINITO)
    A.app.register_blueprint(bp)
    return A


def avvia_in_un_filo(A, porta=0):
    """Il catalogo su 127.0.0.1 in un filo a parte (porta 0: una libera). Torna (server, porta)."""
    import logging
    from waitress import create_server
    logging.getLogger('waitress.queue').setLevel(logging.ERROR)      # «Task queue depth»: le foto chiedono molto insieme
    server = create_server(A.app, host='127.0.0.1', port=porta, threads=4)
    threading.Thread(target=server.run, daemon=True).start()
    return server, int(server.effective_port)


def fotografa(indirizzo, cartella, colore=None):
    """Le foto del catalogo a 1366, 1024 e 683 px (pagina intera), in chiaro e in scuro, più la tendina aperta.
    Torna le righe del resoconto: larghezza della pagina, scorrimento di lato, errori JavaScript."""
    from playwright.sync_api import sync_playwright
    os.makedirs(cartella, exist_ok=True)
    righe, problemi = [], []
    dove = indirizzo + '/catalogo-pezzi' + ('?colore=' + colore.lstrip('#') if colore else '')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
        for tema in ('chiaro', 'scuro'):
            for larghezza in LARGHEZZE:
                ctx = browser.new_context(viewport={'width': larghezza, 'height': ALTEZZA}, reduced_motion='reduce')
                ctx.add_init_script("try { localStorage.setItem('gestionale-tema', '%s'); } catch (e) {}" % tema)
                p = ctx.new_page()
                errori = []
                p.on('pageerror', lambda e: errori.append(str(e)))
                p.on('console', lambda m: errori.append(m.text) if m.type == 'error' else None)
                p.goto(dove, wait_until='load')
                p.evaluate('document.fonts.ready')
                misure = p.evaluate('({pagina: document.documentElement.scrollWidth, finestra: window.innerWidth, '
                                    'scuro: document.documentElement.classList.contains("scuro")})')
                nome = 'catalogo-%d-%s%s.png' % (larghezza, tema, '-' + colore.lstrip('#') if colore else '')
                p.screenshot(path=os.path.join(cartella, nome), full_page=True)
                if larghezza == LARGHEZZE[0]:
                    p.locator('.v-stampa .apri-gruppo').first.click()
                    p.wait_for_timeout(150)
                    aperta = p.locator('.v-stampa .tendina').first.is_visible()
                    barra = p.locator('.v-barra-comandi').first
                    barra.scroll_into_view_if_needed()
                    box = barra.bounding_box()
                    p.screenshot(path=os.path.join(cartella, 'tendina-aperta-%s%s.png' % (tema, '-' + colore.lstrip('#') if colore else '')),
                                 clip={'x': 0, 'y': max(0, box['y'] - 20), 'width': larghezza, 'height': 360})
                    if not aperta:
                        problemi.append('%s: la tendina «Stampa e scarica» non si apre' % tema)
                di_lato = misure['pagina'] > misure['finestra']
                if di_lato or errori or misure['scuro'] != (tema == 'scuro'):
                    problemi.append('%s %d: larga %d su %d, errori %s, scuro %s' % (tema, larghezza, misure['pagina'],
                                                                                    misure['finestra'], errori, misure['scuro']))
                righe.append('%-6s %4d px: pagina larga %d, %s, %d errori JavaScript -> %s' % (
                    tema, larghezza, misure['pagina'], 'SCORRE DI LATO' if di_lato else 'niente scorrimento di lato',
                    len(errori), nome))
                ctx.close()
        browser.close()
    return righe, problemi


def main():
    parametri = argparse.ArgumentParser(description='Il catalogo dei pezzi della veste nuova (gestionale di prova).')
    parametri.add_argument('--porta', type=int, default=5141)
    parametri.add_argument('--dati', default=os.path.join(tempfile.gettempdir(), 'gestionale-catalogo'))
    parametri.add_argument('--foto', metavar='CARTELLA', help='fa le foto e finisce')
    parametri.add_argument('--colore', help='con --foto: anche le foto con questo colore della struttura (es. 1C4184)')
    arg = parametri.parse_args()
    if arg.porta in (5000, 5001, 5002) and not arg.foto:
        raise SystemExit('le porte 5000, 5001 e 5002 sono del programma vero e del gestionale di prova: scegline un\'altra')
    os.makedirs(arg.dati, exist_ok=True)
    A = registra(prepara(arg.dati))
    if arg.foto:
        server, porta = avvia_in_un_filo(A)
        righe, problemi = fotografa('http://127.0.0.1:%d' % porta, arg.foto)
        if arg.colore:
            r2, p2 = fotografa('http://127.0.0.1:%d' % porta, arg.foto, arg.colore)
            righe, problemi = righe + r2, problemi + p2
        server.close()
        print('\n'.join(righe))
        print('Foto in %s: %s' % (arg.foto, 'tutto a posto' if not problemi else 'DA GUARDARE: ' + '; '.join(problemi)))
        return 1 if problemi else 0
    from waitress import serve
    print('Catalogo dei pezzi: http://127.0.0.1:%d/catalogo-pezzi' % arg.porta, flush=True)
    serve(A.app, host='127.0.0.1', port=arg.porta, threads=4)
    return 0


if __name__ == '__main__':
    sys.exit(main())
