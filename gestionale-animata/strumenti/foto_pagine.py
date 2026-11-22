# -*- coding: utf-8 -*-
"""Le foto delle pagine di oggi prima e dopo (tappa 1-bis della veste nuova, 22/11/2026): lo stesso programma in due
versioni, sugli stessi dati e con l'ora ferma, fotografato pagina per pagina e confrontato pixel per pixel.

    python strumenti/foto_pagine.py                                  # principale = origin/ccr-07f8e160-7j5lup
    python strumenti/foto_pagine.py --principale 3b8d3f7 --uscita CARTELLA
    python strumenti/foto_pagine.py --solo /oggi,/pazienti --senza-extra

Serve a chi cambia l'aspetto senza voler cambiare le pagine di oggi (lo strato «vecchio» della tappa 1-bis): le pagine
devono restare IDENTICHE. confronta_rami.py guarda quello che le pagine fanno (moduli, collegamenti, testo, dati) e non
le foto; questo strumento guarda solo le foto.

Come: il database lo fa una volta strumenti/demo.py del principale (preso con git archive, senza toccare il
repository); poi, uno alla volta e sulla stessa cartella dei dati (così anche i percorsi scritti nelle pagine sono
uguali), parte il programma del principale e poi quello di questa cartella, ognuno su una copia fresca del database,
con l'orologio fermo (--giorno e --ora: nel programma date.today() e datetime.now(), nel browser Date) e lo stesso
browser (Chromium di Playwright, «riduci movimento», cursore del testo nascosto). Ogni pagina si fotografa a 1366×657
(quello che si vede) e intera, in chiaro e in scuro; in più (senza --senza-extra) la tendina «Stampa e scarica»
aperta, il fuoco della tastiera, i messaggi a scomparsa e le pagine stampate con i CSS di stampa. Le foto diverse si
rifanno sul principale ripartito da capo: il rumore (le differenze fra due foto dello stesso programma) si dice accanto.
Finisce con «N foto confrontate, K identiche, D diverse (R come il rumore)», esce con 1 se resta una differenza che il
rumore non spiega, e lascia nella cartella di uscita le foto, le differenze in rosso ed esito.json."""
import argparse
import datetime as DT
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RADICE = os.path.dirname(QUI)
NOME = os.path.basename(QUI)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from confronta_rami import aspetta, porta_libera  # noqa: E402

# il programma, con l'orologio fermo: date e datetime dei moduli del programma (anche quelli importati dopo, a ogni
# richiesta) diventano classi che rispondono sempre lo stesso momento; isinstance con le date vere resta valido
ESEGUI = r'''
import datetime as DT, os, sys
codice, db, porta, momento = sys.argv[1], sys.argv[2], int(sys.argv[3]), DT.datetime.fromisoformat(sys.argv[4])
sys.path.insert(0, codice); os.chdir(codice)
vd, vm = DT.date, DT.datetime
class MD(type):
    def __instancecheck__(c, o): return isinstance(o, vd)
    def __subclasscheck__(c, s): return issubclass(s, vd)
class MM(MD):
    def __instancecheck__(c, o): return isinstance(o, vm)
    def __subclasscheck__(c, s): return issubclass(s, vm)
class Data(vd, metaclass=MD):
    @classmethod
    def today(c): return vd(momento.year, momento.month, momento.day)
class Momento(vm, metaclass=MM):
    @classmethod
    def now(c, tz=None): return momento if tz is None else momento.replace(tzinfo=tz)
    @classmethod
    def today(c): return momento
import app as A
from modelli import crea_sessione
A.Sessione = crea_sessione('sqlite:///' + db); A._registro = None
def ferma():
    for m in list(sys.modules.values()):
        f = os.path.abspath(getattr(m, '__file__', None) or '')
        if f.startswith(codice + os.sep) and m is not sys.modules.get('__main__'):
            if getattr(m, 'datetime', None) is vm: m.datetime = Momento
            if getattr(m, 'date', None) is vd: m.date = Data
ferma()
A.app.before_request(ferma)
from waitress import serve
serve(A.app, host='127.0.0.1', port=porta, threads=4)
'''

NASCONDI = '* { caret-color: transparent !important; }'
NASCONDI_MESSAGGI = ' #notifiche, .notifiche, .notifica { visibility: hidden !important; }'


def pagine(giorno):
    """Le pagine da fotografare: quelle di ogni area, con i giorni dei dati di prova (il martedì della settimana)."""
    mar = giorno + DT.timedelta(days=(1 - giorno.weekday()) % 7)
    g, lun, m = mar.isoformat(), (mar - DT.timedelta(days=1)).isoformat(), mar.strftime('%Y%m')
    return ['/oggi', '/giorno/%s?struttura=1' % g, '/settimana/%s?struttura=1' % g, '/mese/%s?struttura=1' % m,
            '/giorno/%s/elenco?struttura=1' % g, '/sala/%s?struttura=1' % g, '/pazienti', '/pazienti/1', '/conferme',
            '/da-confermare', '/cose-da-fare', '/attesa', '/cassa/%s?struttura=1' % g, '/cassa/mese/%s?struttura=1' % m,
            '/cassa/listino', '/personale/turni?struttura=1', '/personale/turni/mese/', '/personale/turni/giorno/',
            '/dove-si-fa/', '/dove-si-fa/registro', '/statistiche', '/impostazioni', '/anagrafiche',
            '/ambulatori/settimana/%s?struttura=1' % lun, '/ambulatori/mese/%s?struttura=1' % m, '/ambulatori/riepilogo',
            '/appuntamento?data=%s&struttura=1' % g, '/aiuto', '/aiuto/prenotare', '/aggiornamenti', '/disponibilita',
            '/riepilogo-live', '/riepilogo-live?schermo=1', '/stampa/%s?struttura=1' % g, '/pagina-che-non-esiste']


def casi(elenco, extra, giorno):
    uscita = []
    for i, pg in enumerate(elenco):
        for tema in ('chiaro', 'scuro'):
            uscita.append(('%02d-%s-schermo' % (i, tema), pg, tema, {}))
            uscita.append(('%02d-%s-intera' % (i, tema), pg, tema, {'intera': True}))
    if extra:
        mar = giorno + DT.timedelta(days=(1 - giorno.weekday()) % 7)
        g, lun, m = mar.isoformat(), (mar - DT.timedelta(days=1)).isoformat(), mar.strftime('%Y%m')
        for i, pg in enumerate(['/giorno/%s?struttura=1' % g, '/ambulatori/settimana/%s?struttura=1' % lun,
                                '/ambulatori/mese/%s?struttura=1' % m, '/personale/turni?struttura=1']):
            for tema in ('chiaro', 'scuro'):
                uscita.append(('tendina%02d-%s' % (i, tema), pg, tema, {'azione': 'tendina'}))
        for i, pg in enumerate(elenco[:12]):
            uscita.append(('fuoco%02d-scuro' % i, pg, 'scuro', {'azione': 'fuoco'}))
        for i, pg in enumerate(['/settimana/%s?struttura=1' % g, '/mese/%s?struttura=1' % m, '/giorno/%s/elenco?struttura=1' % g,
                                '/ambulatori/mese/%s?struttura=1' % m, '/personale/turni?struttura=1',
                                '/cassa/mese/%s?struttura=1' % m, '/statistiche', '/ambulatori/riepilogo']):
            uscita.append(('stampa%02d' % i, pg, 'chiaro', {'stampa': True}))
        for i, pg in enumerate(['/oggi', '/giorno/%s?struttura=1' % g]):
            for tema in ('chiaro', 'scuro'):
                uscita.append(('messaggi%02d-%s' % (i, tema), pg, tema, {'azione': 'messaggi'}))
    return uscita


class Programma:
    """Uno dei due programmi, acceso sulla cartella comune dei dati con una copia fresca del database."""

    def __init__(self, codice, base, dati, momento, registro):
        for est in ('', '-wal', '-shm'):
            if os.path.exists(os.path.join(dati, 'demo.db' + est)):
                os.remove(os.path.join(dati, 'demo.db' + est))
            if os.path.exists(os.path.join(base, 'demo.db' + est)):
                shutil.copy2(os.path.join(base, 'demo.db' + est), os.path.join(dati, 'demo.db' + est))
        self.porta = porta_libera()
        self.registro = open(registro, 'a')
        self.processo = subprocess.Popen([sys.executable, '-c', ESEGUI, os.path.abspath(codice), os.path.join(dati, 'demo.db'),
                                          str(self.porta), momento.isoformat()],
                                         stdout=subprocess.DEVNULL, stderr=self.registro)
        if not aspetta(self.porta):
            self.ferma()
            raise SystemExit('il programma %s non parte: %s' % (codice, registro))

    def ferma(self):
        self.processo.terminate()
        try:
            self.processo.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.processo.kill()
        self.registro.close()


def fotografa(browser, porta, momento, casi_, cartella, lato):
    """Le foto di un programma: {caso: (file, errori JavaScript)}."""
    from fogli_pdf import PRONTA
    uscita = {}
    for nome, pg, tema, kw in casi_:
        ctx = browser.new_context(viewport={'width': 1366, 'height': 657}, reduced_motion='reduce', locale='it-IT')
        ctx.clock.set_fixed_time(momento.astimezone())
        if tema == 'scuro':
            ctx.add_init_script("try { localStorage.setItem('gestionale-tema', 'scuro'); } catch (e) {}")
        p = ctx.new_page()
        errori = []
        p.on('pageerror', lambda e: errori.append(str(e)))
        p.goto('http://127.0.0.1:%d%s' % (porta, pg), wait_until='load')
        try:
            p.wait_for_function(PRONTA, timeout=10000)
        except Exception:
            pass
        p.add_style_tag(content=NASCONDI + ('' if kw.get('azione') == 'messaggi' else NASCONDI_MESSAGGI))
        if kw.get('stampa'):
            p.emulate_media(media='print')
        azione = kw.get('azione')
        if azione == 'tendina' and p.locator('.gruppo-comandi .apri-gruppo').count():
            p.locator('.gruppo-comandi .apri-gruppo').first.click()
        elif azione == 'fuoco':
            for _ in range(3):
                p.keyboard.press('Tab')
        elif azione == 'messaggi':
            p.wait_for_timeout(2500)
        p.wait_for_timeout(250)
        f = os.path.join(cartella, '%s-%s.png' % (nome, lato))
        p.screenshot(path=f, full_page=bool(kw.get('intera') or kw.get('stampa')))
        uscita[nome] = (f, errori)
        ctx.close()
    return uscita


def differenza(a, b, segna=None):
    """Quanti pixel sono diversi fra due foto (o 'misure AxB / CxD'); con segna, salva le differenze in rosso."""
    from PIL import Image, ImageChops
    with Image.open(a) as x, Image.open(b) as y:
        x, y = x.convert('RGB'), y.convert('RGB')
        if x.size != y.size:
            return 'misure %dx%d / %dx%d' % (x.size + y.size)
        d = ImageChops.difference(x, y).convert('L').point(lambda v: 255 if v else 0)
        n = d.histogram()[255]
        if n and segna:
            rosso = Image.new('RGB', x.size, (230, 0, 0))
            Image.composite(rosso, x.point(lambda v: v // 3 + 170), d).save(segna)
        return n


def main():
    par = argparse.ArgumentParser(description='Foto delle pagine di oggi: il principale contro questa cartella.')
    par.add_argument('--principale', default='origin/ccr-07f8e160-7j5lup', help='il programma di partenza (un ramo o un commit)')
    par.add_argument('--qui', default=QUI, help='la cartella da confrontare (di solito questa)')
    par.add_argument('--uscita', default=None, help='dove lasciare foto ed esito (predefinito: una cartella temporanea)')
    par.add_argument('--giorno', default=DT.date.today().isoformat(), help='il giorno fermo (predefinito: oggi)')
    par.add_argument('--ora', default='10:20', help="l'ora ferma (predefinito: 10:20)")
    par.add_argument('--solo', default=None, help='solo queste pagine, separate da virgole')
    par.add_argument('--senza-extra', action='store_true', help='niente tendine, fuoco, messaggi e stampa')
    arg = par.parse_args()
    giorno = DT.date.fromisoformat(arg.giorno)
    momento = DT.datetime.combine(giorno, DT.time.fromisoformat(arg.ora))
    uscita = arg.uscita or tempfile.mkdtemp(prefix='foto-pagine-%s-' % NOME)
    os.makedirs(uscita, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='foto-pagine-')
    inizio = time.monotonic()
    try:
        archivio = subprocess.run(['git', '-C', RADICE, 'archive', '--format=tar', arg.principale, NOME],
                                  capture_output=True, check=True)
        principale = os.path.join(tmp, 'principale')
        with tarfile.open(fileobj=io.BytesIO(archivio.stdout)) as tf:
            if hasattr(tarfile, 'data_filter'):
                tf.extractall(principale, filter='data')
            else:
                tf.extractall(principale)
        codice_a = os.path.join(principale, NOME)
        # il database una volta sola, con il gestionale di prova del principale (si ferma appena pronto)
        base = os.path.join(tmp, 'dati-base')
        porta = porta_libera()
        demo = subprocess.Popen([sys.executable, os.path.join(codice_a, 'strumenti', 'demo.py'), '--dati', base,
                                 '--porta', str(porta)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not aspetta(porta):
            demo.kill()
            sys.exit('il gestionale di prova del principale non parte')
        demo.terminate()
        demo.wait(timeout=30)
        dati = os.path.join(tmp, 'dati')
        os.makedirs(dati)
        elenco = pagine(giorno)
        if arg.solo:
            elenco = [p for p in elenco if p in set(arg.solo.split(','))] or arg.solo.split(',')
        tutti = casi(elenco, not arg.senza_extra, giorno)
        from playwright.sync_api import sync_playwright
        registro = os.path.join(uscita, 'programmi.log')
        foto = {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
            for lato, codice in (('principale', codice_a), ('qui', os.path.abspath(arg.qui))):
                prog = Programma(codice, base, dati, momento, registro)
                try:
                    foto[lato] = fotografa(browser, prog.porta, momento, tutti, uscita, lato)
                finally:
                    prog.ferma()
            esiti, da_rifare = [], []
            for nome, pg, tema, kw in tutti:
                (a, ea), (b, eb) = foto['principale'][nome], foto['qui'][nome]
                n = differenza(a, b, os.path.join(uscita, '%s-differenza.png' % nome))
                esiti.append(dict(caso=nome, pagina=pg, tema=tema, diversi=n, rumore=None, errori=ea + eb))
                if n:
                    da_rifare.append((nome, pg, tema, kw))
            if da_rifare:                    # il rumore: le stesse foto del principale, ripartito da capo
                prog = Programma(codice_a, base, dati, momento, registro)
                try:
                    di_nuovo = fotografa(browser, prog.porta, momento, da_rifare, uscita, 'principale2')
                finally:
                    prog.ferma()
                for e in esiti:
                    if e['caso'] in di_nuovo:
                        e['rumore'] = differenza(foto['principale'][e['caso']][0], di_nuovo[e['caso']][0])
            browser.close()
        with open(os.path.join(uscita, 'esito.json'), 'w', encoding='utf-8') as f:
            json.dump(esiti, f, indent=1, ensure_ascii=False)
        uguali = sum(1 for e in esiti if e['diversi'] == 0)
        rumore = [e for e in esiti if e['diversi'] and e['rumore'] is not None and e['rumore'] == e['diversi']]
        restano = [e for e in esiti if e['diversi'] and e not in rumore]
        errori = [e for e in esiti if e['errori']]
        for e in restano:
            print('DIVERSA %s %s (%s): %s pixel, rumore %s -> %s' % (e['caso'], e['pagina'], e['tema'], e['diversi'], e['rumore'],
                                                                   os.path.join(uscita, e['caso'] + '-differenza.png')))
        for e in rumore:
            print('rumore  %s %s (%s): %s pixel, uguali a quelli fra due foto del principale' % (e['caso'], e['pagina'], e['tema'],
                                                                                                e['diversi']))
        for e in errori:
            print('errori JavaScript %s %s: %s' % (e['caso'], e['pagina'], e['errori'][:2]))
        n_pagine = len(elenco)
        print('%s: %d pagine, %d foto confrontate (principale %s, ora ferma %s), %d identiche, %d diverse (%d come il rumore), '
              '%d con errori JavaScript, in %.0f s. Foto in %s' % (
                  NOME, n_pagine, len(esiti), arg.principale, momento.strftime('%d/%m/%Y %H:%M'), uguali,
                  len(esiti) - uguali, len(rumore), len(errori), time.monotonic() - inizio, uscita))
        return 1 if restano or errori else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
