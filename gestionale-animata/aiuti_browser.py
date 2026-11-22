# -*- coding: utf-8 -*-
"""Aiuti comuni delle prove nel browser (tappa 1 della base, 22/11/2026). Non è una raccolta di prove: non scrive la
riga finale e non sta nell'elenco di strumenti/tutte_le_prove.py; lo importano le raccolte prove_*_browser.py e
strumenti/equivalenza_selettori.py.

I pezzi della cornice (menu, tendine, ricerca rapida, messaggi, domande del browser) si cercano come li cerca un
lettore di schermo: per ruolo e nome («il pulsante Segreteria», «il collegamento Conferme»), non per classe. Così
una veste nuova può cambiare classi, colori e posti senza rompere le prove; se invece sparisce un nome, o due
pezzi prendono lo stesso nome, la prova lo dice. Il passaggio fra le pagine sta in un aiuto solo (vai_dal_menu), la
risposta alle domande del browser in un altro (rispondi): se la veste cambia il menu o le domande, si cambia qui.

    from aiuti_browser import prepara_domande, rispondi, vai_dal_menu

    pg = ctx.new_page()
    domande = prepara_domande(pg)           # subito: ogni domanda del browser passa da qui
    vai_dal_menu(pg, 'Segreteria', 'Conferme')
    with rispondi(pg, si=False) as d:
        pg.get_by_role('button', name='Elimina il tariffario').click()
    ok('fa la domanda', d.testo == 'Eliminare il tariffario «…»? …', d.testo)
    ok('nessuna domanda inattesa', not domande.inattese, domande.inattese)

Attenzione:
- per ruolo si vedono solo i pezzi visibili: una tendina chiusa non c'è (include_hidden=True per contarla);
- name= di Playwright cerca un pezzo del nome senza badare alle maiuscole: «Elimina» trova anche «Elimina il
  tariffario». Per le voci del menu nome_voce(), per i pulsanti exact=True;
- role="menu" lo conoscono solo questi aiuti (tendina_aperta, apri_comandi): la veste nuova può cambiarlo.
I selettori vecchi si tolgono dalle raccolte solo dopo che strumenti/equivalenza_selettori.py ha visto che il nuovo
trova lo stesso elemento."""
import re
import time
from contextlib import contextmanager

NOME_MENU = 'Pagine'            # aria-label di <nav class="menu"> in _menu.html
GRUPPI = ('Ambulatori', 'Segreteria', 'Aiuto', 'Configura')       # i gruppi del menu, con la loro tendina
ZONA = 'Messaggi'               # la zona dei messaggi del programma in base.html: role="status" aria-label="Messaggi"


def nome_voce(testo):
    """Il nome di una voce del menu comincia con le parole in grassetto e continua con la spiegazione in piccolo
    («Conferme telefonate per il prossimo giorno»), quello di un gruppo può avere il contatore («Segreteria 3»):
    si confronta l'inizio, fino a uno spazio o alla fine. «Conferme» non trova «Da confermare»."""
    return re.compile(r'^\s*' + re.escape(testo) + r'(?=\s|$)', re.IGNORECASE)


def _uno(loc, cosa):
    """Il locator deve trovare un elemento solo: zero vuol dire nome sparito, due nome ripetuto."""
    n = loc.count()
    if n != 1:
        raise AssertionError('%s: %s' % (cosa, 'non trovato' if n == 0 else 'trovato %d volte' % n))
    return loc


# --------------------------------------------------------------- il menu
def menu(pg):
    """La barra del menu (il landmark «navigation» di nome Pagine)."""
    return pg.get_by_role('navigation', name=NOME_MENU, exact=True)


def gruppo(pg, nome):
    """Il pulsante di un gruppo del menu: Ambulatori, Segreteria, Aiuto, Configura."""
    return menu(pg).get_by_role('button', name=nome_voce(nome))


def tendina_aperta(pg):
    """La tendina del menu aperta adesso (le chiuse non si vedono e non contano)."""
    return menu(pg).get_by_role('menu')


def apri_gruppo(pg, nome):
    """Apre un gruppo del menu con un clic, come una persona, e torna la sua tendina."""
    b = _uno(gruppo(pg, nome), 'il pulsante «%s» del menu' % nome)
    if b.get_attribute('aria-expanded') != 'true':
        b.click()
    t = tendina_aperta(pg)
    t.wait_for(state='visible', timeout=5000)
    return t


def voce_del_menu(pg, gruppo_o_voce, voce=None):
    """Il collegamento di una pagina del menu: voce_del_menu(pg, 'Pazienti') o voce_del_menu(pg, 'Segreteria',
    'Conferme'). Per una voce dentro un gruppo il gruppo si apre."""
    if voce is None:
        link = menu(pg).get_by_role('link', name=nome_voce(gruppo_o_voce))
        return _uno(link, 'la voce «%s» del menu' % gruppo_o_voce)
    link = apri_gruppo(pg, gruppo_o_voce).get_by_role('link', name=nome_voce(voce))
    return _uno(link, 'la voce «%s» del gruppo «%s»' % (voce, gruppo_o_voce))


def vai_dal_menu(pg, gruppo_o_voce, voce=None, attesa=10000):
    """Va a una pagina dal menu, come una persona, e torna l'indirizzo della pagina nuova:
        vai_dal_menu(pg, 'Pazienti')                     # una voce sempre in vista
        vai_dal_menu(pg, 'Segreteria', 'Da confermare')  # una voce di un gruppo
    Prima il mouse in un punto neutro: lasciato in cima alla finestra apre da solo il gruppo che ci sta sotto
    (prove_112_browser.py, apri_stampa_e_scarica, 21/11/2026). Per le voci che non cambiano pagina («Tasti
    rapidi», «Guida di questa pagina») voce_del_menu(...).click()."""
    pg.mouse.move(2, 500)
    link = voce_del_menu(pg, gruppo_o_voce, voce)
    with pg.expect_navigation(timeout=attesa):
        link.click()
    return pg.url


def voce_attiva(pg):
    """La voce del menu della pagina aperta (aria-current="page"), anche dentro una tendina chiusa."""
    return menu(pg).locator('[aria-current="page"]')


def gruppo_attivo(pg):
    """Il nome del gruppo del menu che contiene la pagina aperta, None se la pagina non è in un gruppo: è quello con
    aria-current="true" sul pulsante, messo con la stessa condizione che lo colora (_menu.html). Se fossero più
    d'uno, i nomi separati da virgole (e la prova che ne aspetta uno cade)."""
    attivi = [g for g in GRUPPI if _uno(gruppo(pg, g), 'il pulsante «%s» del menu' % g).get_attribute('aria-current') == 'true']
    altri = menu(pg).locator('button[aria-current="true"]').count() - len(attivi)
    return ', '.join(attivi + ['%d altri' % altri] * bool(altri)) or None


# --------------------------------------------------------------- comandi e ricerca della pagina
def principale(pg):
    """Il contenuto della pagina, fuori dal menu (il <main> di base.html)."""
    return pg.get_by_role('main')


def apri_comandi(pg, nome):
    """Una tendina dei comandi della pagina («Stampa e scarica», «Altre esportazioni», «Strumenti») aperta con un
    clic, con il mouse prima in un punto neutro; torna la tendina. Si cerca dentro la pagina, fuori dal menu:
    «Programmazione del mese» c'è in tutti e due."""
    pg.mouse.move(2, 500)
    b = _uno(principale(pg).get_by_role('button', name=nome_voce(nome)), 'il pulsante «%s»' % nome)
    if b.get_attribute('aria-expanded') != 'true':
        b.click()
    t = principale(pg).get_by_role('menu')
    t.wait_for(state='visible', timeout=5000)
    return t


def cerca_rapido(pg, testo, attesa=5000):
    """Scrive nella ricerca rapida del menu, come una persona, e torna i risultati (i collegamenti sotto il campo;
    nessuno se il programma risponde «Nessun risultato.»)."""
    zona = menu(pg).get_by_role('search')
    campo = _uno(zona.get_by_role('searchbox'), 'il campo della ricerca rapida')
    campo.click()
    campo.fill('')
    pg.keyboard.type(testo, delay=40)
    risultati = zona.get_by_role('link')
    risultati.or_(zona.get_by_text('Nessun risultato.')).first.wait_for(timeout=attesa)
    return risultati


# --------------------------------------------------------------- messaggi del programma («Impostazioni salvate»)
def zona_messaggi(pg):
    """La zona dei messaggi del programma in cima alla pagina (in base.html, dentro <main>)."""
    return pg.get_by_role('status', name=ZONA, exact=True)


def messaggi(pg):
    """Il testo dei messaggi del programma in cima alla pagina («Impostazioni salvate», «Persona eliminata»), ''
    se non ce ne sono."""
    zona = zona_messaggi(pg)
    return zona.inner_text() if zona.count() else ''


def nella_zona(pg, testo, errore):
    """(va bene, dettaglio): il messaggio con quel testo c'è una volta sola nella pagina, dentro la zona dei
    messaggi, visibile, e rosso solo se è un errore."""
    trovati = pg.get_by_text(testo)
    zona = zona_messaggi(pg)
    if trovati.count() != 1:
        return False, '%r trovato %d volte; zone dei messaggi: %d' % (testo, trovati.count(), zona.count())
    m = trovati.first
    dentro = zona.count() == 1 and zona.evaluate('(z, e) => z !== e && z.contains(e)', m.element_handle())
    rosso = 'errore' in (m.get_attribute('class') or '').split()      # l'aspetto: per ora solo la classe lo dice
    return dentro and m.is_visible() and rosso == errore, {'dentro': dentro, 'visibile': m.is_visible(), 'errore': rosso}


# --------------------------------------------------------------- domande del browser («Eliminare…?»)
class Risposta:
    """La risposta preparata per una domanda: si (OK) o no (Annulla); testo è la domanda, se è arrivata."""

    def __init__(self, si):
        self.si = si
        self.testo = None


class Domande:
    """Tutte le domande del browser (confirm, alert) di una pagina passano da qui. Ognuna prende la risposta
    preparata da rispondi(); una domanda senza risposta preparata si segna fra le inattese e si risponde Annulla,
    come farebbe Playwright da solo senza nessun gestore."""

    def __init__(self, pg):
        self.pg = pg
        self.pronte = []           # le risposte preparate, in ordine
        self.viste = []            # tutti i testi arrivati
        self.inattese = []         # quelli arrivati senza rispondi()
        pg.on('dialog', self._arrivata)

    def _arrivata(self, d):
        self.viste.append(d.message)
        if self.pronte:
            r = self.pronte.pop(0)
            r.testo = d.message
            if r.si:
                d.accept()
            else:
                d.dismiss()
        else:
            self.inattese.append(d.message)
            d.dismiss()


_DOMANDE = []                      # una Domande per pagina


def prepara_domande(pg):
    """Da chiamare appena aperta la pagina, prima di qualsiasi clic: dopo, una domanda inattesa non passa
    inosservata (finisce in .inattese invece di essere chiusa in silenzio). Una volta per pagina: chiamata di
    nuovo torna la stessa. Mai insieme a un pg.on('dialog') della raccolta: due gestori sulla stessa domanda
    danno «dialog already handled»."""
    for d in _DOMANDE:
        if d.pg is pg:
            return d
    d = Domande(pg)
    _DOMANDE.append(d)
    return d


@contextmanager
def rispondi(pg, si=True, attesa=3000):
    """Risponde alla domanda che fa il clic dentro il blocco: OK con si=True, Annulla con si=False.
        with rispondi(pg, si=False) as d:
            pg.get_by_role('button', name='Elimina', exact=True).click()
        ok('... fa la domanda', d.testo == "Eliminare D'Esempio Anna?", d.testo)
    Se la pagina cambia con OK: «with pg.expect_navigation():» fuori, «with rispondi(pg) as d:» dentro.
    Non lancia eccezioni: se la domanda non arriva entro attesa millisecondi d.testo resta None e la prova che
    lo controlla cade (è il difetto dell'apostrofo della 1.12.7: niente domanda e il modulo partiva lo stesso)."""
    domande = prepara_domande(pg)
    r = Risposta(si)
    domande.pronte.append(r)
    try:
        yield r
        fine = time.monotonic() + attesa / 1000
        while r.testo is None and time.monotonic() < fine:
            pg.wait_for_timeout(50)
    finally:
        if r in domande.pronte:            # non usata: non deve rispondere alla domanda di un altro clic
            domande.pronte.remove(r)
