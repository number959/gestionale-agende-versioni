# -*- coding: utf-8 -*-
"""Il catalogo dei pezzi della veste nuova (tappa 1-bis): una pagina con ogni pezzo di templates/_pezzi.html, i
gettoni di static/gettoni.css con i loro contrasti e le scale, in chiaro e in scuro. Per le foto da far approvare a
Giovanni e per chi fa le pagine.

    python strumenti/catalogo_pezzi.py                 # http://127.0.0.1:5141/catalogo-pezzi
    python strumenti/catalogo_pezzi.py --porta 5077

È un gestionale di prova a sé: database nuovo in una cartella temporanea, struttura e logo inventati, niente invii.
Il modello (strumenti/catalogo_pezzi.html) e questo file stanno in strumenti/: non entrano nell'eseguibile
(gestionale.spec porta solo templates/ e static/) e l'indirizzo /catalogo-pezzi non esiste nel programma vero, né nel
gestionale di prova di demo.py (così il confronto fra i rami non vede un indirizzo in più).

--bozze CARTELLA: prende prima da lì templates/ e static/ (per provare i mattoni prima di metterli nel programma)."""
import argparse
import io
import os
import re
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get('GESTIONALE_CARTELLA') or os.path.dirname(QUI)   # per provarlo fuori dal programma
sys.path.insert(0, SRC)
os.chdir(SRC)

# grandezze delle tavole Nefro che diventano ogni passo (misurate sulle 58 tavole con il blu del gruppo)
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
                   ('m', '13,5px', '13,5', False), ('n', '14px', '14, 14,5', False), ('l', '15px', '15, 15,5, 16', False),
                   ('t3', '18px', '17, 18', True), ('t2', '22px', '20, 22, 24', True), ('num', '30px', '26, 28, 30', True),
                   ('t1', '36px', '34, 36, 40, 44, 46', True)]
COPPIE = [('testo', 'fondo'), ('testo', 'superficie'), ('testo-medio', 'superficie'), ('testo-medio', 'incasso'),
          ('testo-tenue', 'superficie'), ('testo-tenue', 'fondo'), ('testo-tenue', 'incasso'), ('testo-tenue', 'chiuso'),
          ('verde-testo', 'occupato'), ('confermato-testo', 'confermato'), ('rosso', 'rosso-fondo'),
          ('rosso-forte', 'rosso-fondo'), ('avviso-testo', 'avviso-fondo'), ('avviso-testo', 'sabbia'),
          ('ok-testo', 'ok-fondo'), ('sala-testo', 'sala-fondo'), ('testo-su-pieno', 'verde-pieno'),
          ('testo-su-pieno', 'rosso-pieno')]


def leggi_gettoni(percorso):
    """I gettoni di gettoni.css: {nome: (chiaro, scuro)}; solo quelli con un colore scritto."""
    css = re.sub(r'/\*.*?\*/', '', open(percorso, encoding='utf-8').read(), flags=re.S)
    chiaro = dict(re.findall(r'--v-([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;', css[css.index(':root'):css.index('@media screen')]))
    scuro = dict(chiaro)
    scuro.update(re.findall(r'--v-([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;', css[css.index('html.scuro'):]))
    return {n: (chiaro[n], scuro[n]) for n in chiaro}


def logo_inventato():
    """Un logo che non è di nessuno: un quadrato blu con una A e la scritta «Poliambulatorio Esempio»."""
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (440, 80), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 8, 68, 72), radius=14, fill=(28, 65, 132, 255))
    d.text((26, 26), 'A', fill=(255, 255, 255, 255), font_size=30)
    d.text((86, 18), 'Poliambulatorio', fill=(18, 36, 74, 255), font_size=24)
    d.text((86, 46), 'Esempio', fill=(91, 104, 124, 255), font_size=20)
    uscita = io.BytesIO()
    im.save(uscita, 'PNG')
    return uscita.getvalue()


def prepara(cartella_dati):
    """Il database del catalogo: quello di seed.py, con struttura, colore e logo inventati (nessun nome vero a video)."""
    from datetime import datetime
    import seed
    import marchio
    import app as A
    from modelli import Struttura, select
    p = os.path.join(cartella_dati, 'catalogo.db')
    for vecchio in (p, p + '-wal', p + '-shm'):
        if os.path.exists(vecchio):
            os.remove(vecchio)
    S = seed.popola('sqlite:///' + p)
    s = S()
    for i, st in enumerate(s.scalars(select(Struttura).order_by(Struttura.id))):
        st.nome = ['Sede centrale', 'Sede nord', 'Poliambulatorio est'][i] if i < 3 else 'Sede %d' % (i + 1)
        st.societa = 'Esempio S.r.l.'
        st.colore = '#1C4184'           # il blu del gruppo, come nelle tavole
        st.logo = marchio.normalizza_logo(logo_inventato()) if i == 0 else None
        st.logo_aggiornato = datetime.now() if i == 0 else None
        st.indirizzo, st.telefono, st.email = 'Via Esempio 1', '081 000 0000', 'segreteria@example.it'
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    return A


def registra(app, cartella_bozze=None):
    """Aggiunge /catalogo-pezzi all'applicazione (solo nel gestionale di prova)."""
    from flask import Blueprint, render_template, send_from_directory, request
    import marchio
    from modelli import STATI
    cartelle = [QUI] + ([os.path.join(cartella_bozze, 'strumenti'), os.path.join(cartella_bozze, 'templates')]
                        if cartella_bozze else [])
    if cartella_bozze:
        from jinja2 import ChoiceLoader, FileSystemLoader
        app.jinja_loader = ChoiceLoader([FileSystemLoader(cartelle[1:]), app.jinja_loader])
        statici = os.path.join(cartella_bozze, 'static')

        @app.before_request
        def statici_delle_bozze():
            if request.path.startswith('/static/'):
                nome = request.path[len('/static/'):]
                if os.path.isfile(os.path.join(statici, nome)):
                    return send_from_directory(statici, nome, max_age=0)
    bp = Blueprint('catalogo_pezzi', __name__, template_folder=QUI)
    gettoni_css = os.path.join(cartella_bozze or SRC, 'static', 'gettoni.css')

    @bp.route('/catalogo-pezzi')
    def pagina():
        g = leggi_gettoni(gettoni_css)
        coppie = [dict(testo=t, fondo=f, chiaro=marchio.contrasto(g[t][0], g[f][0]), scuro=marchio.contrasto(g[t][1], g[f][1]))
                  for t, f in COPPIE]
        return render_template('catalogo_pezzi.html', sid=1,
                               gettoni=[dict(nome=n, chiaro=c, scuro=s) for n, (c, s) in g.items()], coppie=coppie,
                               scala_spazi=SCALA_SPAZI, scala_raggi=SCALA_RAGGI, scala_caratteri=SCALA_CARATTERI,
                               stati=STATI)
    app.register_blueprint(bp)


if __name__ == '__main__':
    parametri = argparse.ArgumentParser(description='Il catalogo dei pezzi della veste nuova (gestionale di prova).')
    parametri.add_argument('--porta', type=int, default=5141)
    parametri.add_argument('--dati', default=os.path.join(tempfile.gettempdir(), 'gestionale-catalogo'))
    parametri.add_argument('--bozze', default=None)
    ARG = parametri.parse_args()
    os.makedirs(ARG.dati, exist_ok=True)
    A = prepara(ARG.dati)
    registra(A.app, ARG.bozze)
    from waitress import serve
    print('Catalogo dei pezzi: http://127.0.0.1:%d/catalogo-pezzi' % ARG.porta, flush=True)
    serve(A.app, host='127.0.0.1', port=ARG.porta, threads=4)
