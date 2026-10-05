# -*- coding: utf-8 -*-
"""Prima di consegnare: niente dei file veri della clinica (Excel o CSV con
pazienti, agende, interventi) deve essere finito nei sorgenti, nelle prove o
nella documentazione. Si passano i file veri, che restano dove sono (mai
copiarli nel progetto):

    python strumenti/cerca_dati_veri.py FILE_VERI... [--cartella DIR]... [--ammessi parola,parola]

Senza --cartella si guarda questa cartella del programma. Si leggono i file
di testo (.py .html .md .js .css .iss .bat .txt .spec .json .csv), tranne
dati/luoghi_nascita.json, l'elenco pubblico dei comuni. Per il PDF della
guida: pdftotext "Guida ... .pdf" in una cartella da passare con --cartella.

Cerca:
- numeri di 8 cifre o piu' (telefoni, codici; non le date) che ci sono nei
  file veri;
- email e codici fiscali che ci sono nei file veri;
- coppie di parole dei file veri (cognome e nome, in un ordine o nell'altro)
  scritte nel progetto con le iniziali maiuscole: gravi se una delle due e'
  un nome di battesimo, altrimenti da guardare (spesso intestazioni);
- parole dei file veri che nel progetto compaiono solo con l'iniziale
  maiuscola (possibili cognomi): queste si guardano a occhio, molte sono
  parole normali, nomi stranieri o nomi di prestazioni.

I nomi dei medici, nei dati di prova di proposito, e i numeri d'esempio si
passano con --ammessi. Esce con 1 se trova numeri, email, codici fiscali o
coppie con un nome di battesimo."""
import argparse
import csv
import io
import os
import re
import sys
import unicodedata

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTENSIONI = ('.py', '.html', '.md', '.js', '.css', '.iss', '.bat', '.txt', '.spec', '.json', '.csv')
SALTATI = {'luoghi_nascita.json'}
CARTELLE_SALTATE = {'__pycache__', '.venv', 'build', 'dist', 'Output', '.git', 'node_modules'}
PAROLA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")
CF = re.compile(r'[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]')
EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
NUMERO = re.compile(r'\d[\d .\-/]{6,}\d')


def norma(parola):
    p = unicodedata.normalize('NFKD', parola)
    return ''.join(c for c in p if not unicodedata.combining(c)).lower()


def data(n):
    """Una data (con l'ora), non un telefono: 20260915, 2026091508, 25092026."""
    def valida(a, m, g):
        return 1900 <= a <= 2100 and 1 <= m <= 12 and 1 <= g <= 31
    return valida(int(n[:4]), int(n[4:6]), int(n[6:8])) or (len(n) == 8 and valida(int(n[4:]), int(n[2:4]), int(n[:2])))


def numeri_in(testo):
    return {n for n in (re.sub(r'\D', '', x) for x in NUMERO.findall(testo)) if len(n) >= 8 and not data(n)}


def celle(percorso):
    if percorso.lower().endswith(('.xlsx', '.xlsm')):
        import openpyxl
        libro = openpyxl.load_workbook(percorso, data_only=True, read_only=True)
        for foglio in libro.worksheets:
            for riga in foglio.iter_rows(values_only=True):
                for v in riga:
                    if v is not None:
                        yield str(v)
        return
    testo = ''
    for codifica in ('utf-8-sig', 'cp1252'):
        try:
            with open(percorso, encoding=codifica, newline='') as f:
                testo = f.read()
            break
        except UnicodeDecodeError:
            continue
    prima = testo.split('\n', 1)[0]
    for riga in csv.reader(io.StringIO(testo), delimiter=';' if prima.count(';') > prima.count(',') else ','):
        for v in riga:
            if v.strip():
                yield v


def file_del_progetto(cartelle):
    for cartella in cartelle:
        for radice, sotto, nomi in os.walk(cartella):
            sotto[:] = [s for s in sotto if s not in CARTELLE_SALTATE and not s.endswith('_tmp')]
            for n in nomi:
                if n.endswith(ESTENSIONI) and n not in SALTATI:
                    yield os.path.join(radice, n)


def main():
    p = argparse.ArgumentParser(description='Cerca nel progetto i dati dei file veri della clinica.')
    p.add_argument('veri', nargs='+', help='file veri (.xlsx o .csv), letti e basta')
    p.add_argument('--cartella', action='append', help='cartella da guardare (anche piu\' volte)')
    p.add_argument('--ammessi', default='', help='parole, numeri o email da non segnalare, separati da virgole (i medici)')
    a = p.parse_args()
    ammessi = {norma(x.strip()) for x in a.ammessi.split(',') if x.strip()}
    cartelle = a.cartella or [QUI]

    numeri, email, codici, parole, coppie = set(), set(), set(), set(), set()
    for f in a.veri:
        for testo in celle(f):
            numeri |= {n for n in numeri_in(testo) | set(re.findall(r'\d{8,}', testo))
                       if not data(n) and n not in ammessi}
            email |= {m.lower() for m in EMAIL.findall(testo)} - ammessi
            codici |= set(CF.findall(testo.upper())) - {x.upper() for x in ammessi}
            w = [norma(x) for x in PAROLA.findall(testo)]
            parole |= {x for x in w if len(x) >= 4 and x not in ammessi}
            coppie |= {(x, y) for x, y in zip(w, w[1:]) if len(x) >= 3 and len(y) >= 3}

    trovati = {'numeri': {}, 'email': {}, 'codici fiscali': {}, 'coppie di nomi': {}}
    maiuscole, minuscole, dove = set(), set(), {}
    for f in file_del_progetto(cartelle):
        testo = open(f, encoding='utf-8', errors='ignore').read()
        breve = os.path.relpath(f, cartelle[0]) if f.startswith(cartelle[0]) else f
        for n in numeri_in(testo):
            for v in numeri:
                if n == v or (len(n) >= 8 and n in v) or (len(v) >= 8 and v in n):
                    trovati['numeri'].setdefault(v, set()).add(breve)
        basso = testo.lower()
        for m in email:
            if m in basso:
                trovati['email'].setdefault(m, set()).add(breve)
        alto = testo.upper()
        for c in codici:
            if c in alto:
                trovati['codici fiscali'].setdefault(c, set()).add(breve)
        gettoni = PAROLA.findall(testo)
        for g in gettoni:
            n = norma(g)
            (maiuscole if g[0].isupper() else minuscole).add(n)
            if g[0].isupper() and n in parole:
                dove.setdefault(n, set()).add(breve)
        for x, y in zip(gettoni, gettoni[1:]):
            if x[0].isupper() and y[0].isupper():
                cx, cy = norma(x), norma(y)
                if ((cx, cy) in coppie or (cy, cx) in coppie) and not (cx in ammessi or cy in ammessi):
                    trovati['coppie di nomi'].setdefault('%s %s' % (x, y), set()).add(breve)
    # una coppia di parole che nel progetto si usano anche minuscole e' testo normale ("Visita Ginecologica");
    # e' grave se una delle due e' un nome di battesimo, altrimenti si guarda a occhio ("Totale Slot")
    sys.path.insert(0, QUI)
    from importa import NOMI_PROPRI
    coppie_dubbie = {}
    for k, v in list(trovati['coppie di nomi'].items()):
        parole_k = [norma(w) for w in k.split()]
        if all(w in minuscole for w in parole_k):
            del trovati['coppie di nomi'][k]
        elif not any(w in NOMI_PROPRI for w in parole_k):
            coppie_dubbie[k] = trovati['coppie di nomi'].pop(k)
    da_guardare = sorted(w for w in dove if w not in minuscole)

    gravi = 0
    for tipo, cose in trovati.items():
        if cose:
            gravi += len(cose)
            print('%s dei file veri trovati nel progetto:' % tipo.capitalize())
            for cosa, files in sorted(cose.items()):
                print('  %s  ->  %s' % (cosa, ', '.join(sorted(files)[:4])))
    if coppie_dubbie:
        print('Coppie di parole dei file veri, senza nomi di battesimo (da guardare a occhio):')
        for cosa, files in sorted(coppie_dubbie.items()):
            print('  %s  ->  %s' % (cosa, ', '.join(sorted(files)[:3])))
    if da_guardare:
        print('Parole dei file veri che nel progetto compaiono solo con la maiuscola (da guardare a occhio):')
        for w in da_guardare:
            print('  %-20s %s' % (w, ', '.join(sorted(dove[w])[:3])))
    print('\n%d file veri letti: %d numeri, %d email, %d codici fiscali, %d parole. %s' % (
        len(a.veri), len(numeri), len(email), len(codici), len(parole),
        'Niente di grave trovato.' if not gravi else 'DA SISTEMARE: %d cose trovate.' % gravi))
    return 1 if gravi else 0


if __name__ == '__main__':
    sys.exit(main())
