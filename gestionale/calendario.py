# -*- coding: utf-8 -*-
"""Festivita' italiane e piccoli calcoli sulle date.

Le festivita' nazionali sono fisse tranne Pasquetta, che dipende dalla
Pasqua: si calcola con l'algoritmo gregoriano "anonimo" (Meeus/Jones/Butcher),
valido per qualunque anno del calendario gregoriano.
"""
from datetime import date, timedelta

# (mese, giorno, nome, primo anno di validita')
FESTE_FISSE = [
    (1, 1, 'Capodanno', 1949),
    (1, 6, 'Epifania', 1949),
    (4, 25, 'Festa della Liberazione', 1949),
    (5, 1, 'Festa del Lavoro', 1949),
    (6, 2, 'Festa della Repubblica', 1949),
    (8, 15, 'Ferragosto', 1949),
    # reintrodotta come festa nazionale dal 2026 (legge promulgata nell'ottobre 2025)
    (10, 4, "San Francesco d'Assisi", 2026),
    (11, 1, 'Ognissanti', 1949),
    (12, 8, 'Immacolata Concezione', 1949),
    (12, 25, 'Natale', 1949),
    (12, 26, 'Santo Stefano', 1949),
]


def pasqua(anno):
    """Data della domenica di Pasqua nel calendario gregoriano."""
    a = anno % 19
    b, c = divmod(anno, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = (h + l - 7 * m + 114) % 31 + 1
    return date(anno, mese, giorno)


def festivita(anno, patrono=None):
    """{data: nome} delle festivita' dell'anno. patrono = (giorno, mese)."""
    feste = {}
    for mese, giorno, nome, dal in FESTE_FISSE:
        if anno >= dal:
            feste[date(anno, mese, giorno)] = nome
    p = pasqua(anno)
    feste[p] = 'Pasqua'
    feste[p + timedelta(days=1)] = "Lunedì dell'Angelo"
    if patrono:
        giorno, mese = patrono
        try:
            d = date(anno, mese, giorno)
        except ValueError:          # 29/02 in un anno non bisestile
            d = None
        if d is not None and d not in feste:
            feste[d] = 'Festa del patrono'
    return feste


_memoria = {}


def festivo(g, patrono=None):
    """Nome della festivita' se il giorno g e' festivo, altrimenti None.
    La domenica non conta: e' un giorno di chiusura, non una festa."""
    chiave = (g.year, patrono)
    if chiave not in _memoria:
        _memoria[chiave] = festivita(g.year, patrono)
    return _memoria[chiave].get(g)


def lunedi_di(g):
    return g - timedelta(days=g.weekday())


def giorni_del_mese(anno, mese):
    primo = date(anno, mese, 1)
    dopo = date(anno + (mese == 12), mese % 12 + 1, 1)
    return [primo + timedelta(days=i) for i in range((dopo - primo).days)]


def settimane_del_mese(anno, mese):
    """Le settimane (liste di 7 date, da lunedi) che coprono il mese."""
    giorni = giorni_del_mese(anno, mese)
    inizio = lunedi_di(giorni[0])
    fine = giorni[-1] + timedelta(days=6 - giorni[-1].weekday())
    settimane, g = [], inizio
    while g <= fine:
        settimane.append([g + timedelta(days=i) for i in range(7)])
        g += timedelta(days=7)
    return settimane
