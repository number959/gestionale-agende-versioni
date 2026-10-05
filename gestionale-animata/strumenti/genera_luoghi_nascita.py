# -*- coding: utf-8 -*-
"""Scrive dati/luoghi_nascita.json: i luoghi di nascita del codice fiscale,
cioe' i comuni italiani (anche quelli soppressi o rinominati, con il periodo
in cui sono esistiti) e gli stati esteri, ognuno con il suo codice (il
"codice catastale" o "Belfiore": F839 = Napoli, Z112 = Germania).

I dati vengono dal pacchetto python-codicefiscale (licenza MIT, Fabio
Caccamo), che li ricava dagli archivi ufficiali ISTAT e ANPR e li aggiorna
quando nascono o si fondono comuni. Per aggiornarli:

    pip install -U python-codicefiscale
    python strumenti/genera_luoghi_nascita.py

e poi le prove (prove_17.py controlla il file). Il programma non usa il
pacchetto: legge solo il file scritto qui, cosi' resta senza dipendenze in
piu' e funziona senza internet."""
import json
import os
import re
import sys
from datetime import date, timedelta

import codicefiscale

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USCITA = os.path.join(QUI, 'dati', 'luoghi_nascita.json')
DATI = os.path.join(os.path.dirname(codicefiscale.__file__), 'data')


def leggi(nome):
    with open(os.path.join(DATI, nome), encoding='utf-8') as f:
        return json.load(f)


def giorno(testo):
    return (testo or '')[:10]


# nei dati ogni parola comincia con la maiuscola ("San Giorgio A Cremano"):
# le preposizioni e gli articoli tornano minuscoli, come nei nomi ufficiali
MINUSCOLE = {'a', 'ad', 'al', 'all', 'alla', 'alle', 'allo', 'agli', 'ai', 'con', 'da', 'dal', 'dalla', 'dalle',
             'de', 'dei', 'degli', 'del', 'dell', 'della', 'delle', 'dello', 'di', 'e', 'ed', 'in', 'nel', 'nell',
             'nella', 'nelle', 'nello', 'sul', 'sull', 'sulla', 'sulle', 'sullo', 'su', 'd', 'l', 'il', 'la', 'le',
             'lo', 'gli', 'i', 'li', 'of', 'the', 'and'}


def nome_ufficiale(nome):
    """'San Giorgio A Cremano' -> 'San Giorgio a Cremano', 'Cassano D'Adda' ->
    'Cassano d'Adda', 'Sant'Agata De' Goti' -> 'Sant'Agata de' Goti'."""
    pezzi = re.split(r"(\s+|-|'|’)", nome)
    uscita, prima = [], True
    for i, p in enumerate(pezzi):
        if not p or re.fullmatch(r"\s+|-|'|’", p):
            uscita.append(p)
            continue
        dopo = pezzi[i + 1] if i + 1 < len(pezzi) else ''
        if not prima and p.lower() in MINUSCOLE and (dopo in ("'", '’') or p.lower() not in ('d', 'l')):
            uscita.append(p.lower())
        elif re.fullmatch(r'[IVXivx]{2,}', p):
            uscita.append(p.upper())          # numeri romani: Giovanni XXIII
        else:
            uscita.append(p)
        prima = False
    return ''.join(uscita)


def unisci_periodi(righe):
    """Le righe dello stesso luogo (codice, nome e provincia uguali) con
    periodi contigui o sovrapposti diventano una riga sola."""
    righe = sorted(righe, key=lambda r: r['dal'] or '0000')
    uscita = []
    for r in righe:
        if uscita:
            u = uscita[-1]
            fine = u['al']
            if not fine:
                continue                      # il precedente esiste ancora: copre tutto
            if r['dal'] and date.fromisoformat(r['dal']) <= date.fromisoformat(fine) + timedelta(days=1):
                if not r['al'] or r['al'] > fine:
                    u['al'] = r['al']
                continue
        uscita.append(dict(r))
    return uscita


def main():
    gruppi = {}
    for x in leggi('municipalities.json'):
        if not re.fullmatch(r'[A-Z][0-9]{3}', x['code']):
            continue                          # 'ND': qualche comune dell'Ottocento senza codice, inutile qui
        chiave = (x['code'], nome_ufficiale(x['name']), x['province'])
        gruppi.setdefault(chiave, []).append({'dal': giorno(x['date_created']), 'al': giorno(x['date_deleted']),
                                              'alt': x.get('name_alt') or ''})
    stati = leggi('deleted-countries.json') + leggi('countries.json')
    for x in stati:
        chiave = (x['code'], nome_ufficiale(x['name']), 'EE')
        alt = x.get('name_alt_en') or x.get('name_alt') or ''
        gruppi.setdefault(chiave, []).append({'dal': '', 'al': giorno(x['date_deleted']),
                                              'alt': alt if alt.lower() != x['name'].lower() else ''})
    luoghi = []
    for (codice, nome, provincia), righe in gruppi.items():
        alt = next((r['alt'] for r in righe if r['alt']), '')
        for r in unisci_periodi(righe):
            riga = [codice, nome, provincia, r['dal'], r['al']]
            if alt:
                riga.append(alt)
            luoghi.append(riga)
    luoghi.sort(key=lambda r: (r[0], r[3] or '0000', r[1]))
    versione = getattr(codicefiscale, '__version__', '') or ''
    if not versione:
        try:
            from importlib.metadata import version
            versione = version('python-codicefiscale')
        except Exception:
            versione = '?'
    dati = {
        'fonte': 'Comuni italiani (anche soppressi o rinominati) e stati esteri con il codice usato nel codice '
                 'fiscale. Dati ISTAT e ANPR, dal pacchetto python-codicefiscale %s (licenza MIT, Fabio Caccamo).'
                 % versione,
        'generato_il': date.today().isoformat(),
        'colonne': ['codice', 'nome', 'provincia (EE = stato estero)', 'dal', 'al (vuoto: esiste ancora)',
                    'altro nome (bilingue o in inglese)'],
        'luoghi': luoghi,
    }
    os.makedirs(os.path.dirname(USCITA), exist_ok=True)
    with open(USCITA, 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    attivi = sum(1 for r in luoghi if not r[4] and r[2] != 'EE')
    print('%s: %d righe, %d comuni esistenti, %d stati esteri, %.0f KB' % (
        USCITA, len(luoghi), attivi, sum(1 for r in luoghi if r[2] == 'EE'), os.path.getsize(USCITA) / 1024))


if __name__ == '__main__':
    sys.exit(main())
