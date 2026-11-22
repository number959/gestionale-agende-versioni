# -*- coding: utf-8 -*-
"""Prove nel browser dell'accesso dagli altri PC (1.13, accessi.py), su un gestionale gia' avviato con i dati di
prova (strumenti/demo.py), tutto il giro come lo fa la segreteria:
    python prove_accessi_browser.py http://127.0.0.1:5001
- dal PC principale: Configura → Impostazioni → «Aree e accessi»; l'accesso dagli altri PC acceso su una porta libera
  (mai la 5080 della clinica), con l'indirizzo da scrivere sugli altri PC e il firewall spiegato; un utente nuovo con
  Agenda «guardare e modificare» e Cassa «solo guardare», scelte nello stesso modulo;
- da un'altra scheda, sull'indirizzo della rete (quello di questo PC fuori da 127.*, come un altro PC): la pagina di
  accesso, la password da cambiare al primo accesso, la barra «Entrato da un altro PC come…»; in Agenda la nota del
  giorno si salva, in Cassa la pagina si apre ma «Salva il listino» risponde «Solo guardare», Pazienti risponde con la
  pagina in italiano e «Torna alle pagine disponibili»; «Esci», e la pagina dopo chiede di nuovo l'accesso;
- di nuovo dal PC principale: la pagina di accesso non c'è, il registro dice chi è entrato, uscito e cosa ha salvato;
  «Togli» fa la domanda; l'accesso spento chiude davvero la porta.
Alla fine il gestionale di prova torna come prima: utente tolto, nota tolta, accesso spento.
La cornice (menu, messaggi, domande) si cerca per ruolo e nome con gli aiuti di aiuti_browser.py; ogni domanda passa
da rispondi(), e una domanda che nessuno aspettava fa cadere la prova."""
import os
import re
import socket
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aiuti_browser import (indirizzo_di_prova, messaggi, nome_voce, prepara_domande, principale, rispondi,  # noqa: E402
                           vai_dal_menu)

B = indirizzo_di_prova(sys.argv)   # mai la porta 5000, quella del programma vero
esiti = []
NOME = 'Sportello Esempietti'
PRIMA, NUOVA = 'pentola blu sul fuoco', 'barca verde nel lago'
NOTA = 'Nota scritta da un altro PC Fintini'


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


def porta_libera():
    """Una porta libera su tutte le schede, fuori dalle porte del programma vero e della prova (5000-5089)."""
    while True:
        with socket.socket() as x:
            x.bind(('0.0.0.0', 0))
            p = x.getsockname()[1]
        if not 5000 <= p < 5090:
            return p


def indirizzo_di_un_altro_pc():
    """Un indirizzo IPv4 di questo PC fuori da 127.* (la richiesta arriva come da un altro PC); se non c'e', 127.0.0.1
    (sulla porta della rete si e' comunque «dalla rete»). Come in prove_accessi.py."""
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            if not info[4][0].startswith(('127.', '169.254.')):
                return info[4][0]
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
            u.connect(('192.0.2.1', 9))            # UDP: nessun pacchetto parte, il sistema sceglie solo la scheda
            ip = u.getsockname()[0]
        if ip and not ip.startswith(('127.', '0.')):
            return ip
    except OSError:
        pass
    return '127.0.0.1'


def chiusa(host, porta):
    try:
        socket.create_connection((host, porta), timeout=5).close()
        return False
    except OSError:
        return True


PORTA = porta_libera()
IP = indirizzo_di_un_altro_pc()
RETE = 'http://%s:%d' % (IP, PORTA)

with sync_playwright() as p:
    # le pagine sono tutte su questo PC: nessun proxy, anche per l'indirizzo della rete
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None, args=['--no-proxy-server'])
    ctx = br.new_context(viewport={'width': 1366, 'height': 900}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                        "localStorage.setItem('gestionale-tema', 'chiaro'); } catch (e) {}")
    pg = ctx.new_page()
    domande = prepara_domande(pg)            # subito: ogni domanda del browser passa da qui
    err = []
    pg.on('pageerror', lambda e: err.append('PC: %s' % e))
    pg.on('console', lambda m: err.append('PC: %s' % m.text) if m.type == 'error' else None)

    # ------------------------------------------------------------------ dal PC principale
    pg.goto(B + '/oggi')
    vai_dal_menu(pg, 'Configura', 'Impostazioni')
    with pg.expect_navigation():
        principale(pg).get_by_role('link', name='Aree e accessi', exact=True).click()
    ok('da Impostazioni si arriva ad «Aree e accessi»', pg.url.endswith('/configura/accessi')
       and pg.get_by_role('heading', name='Aree e accessi', exact=True).count() == 1, pg.url)
    if pg.get_by_role('region', name='Utente %s' % NOME).count():
        # una prova di prima fermata a metà: si riparte da capo
        with pg.expect_navigation():
            with rispondi(pg, si=True):
                pg.get_by_role('region', name='Utente %s' % NOME).get_by_role('button', name='Togli %s' % NOME).click()
    rete_ = pg.get_by_role('form', name='Accesso dagli altri PC')
    if rete_.get_by_label('Gli altri PC della rete possono aprire il programma').is_checked():
        rete_.get_by_label('Gli altri PC della rete possono aprire il programma').uncheck()
        with pg.expect_navigation():
            rete_.get_by_role('button', name='Salva', exact=True).click()
    rete_ = pg.get_by_role('form', name='Accesso dagli altri PC')
    porta_di_prima = rete_.get_by_label('Porta', exact=True).input_value()
    ok('il modulo dell\'accesso dagli altri PC, spento di partenza',
       rete_.count() == 1 and not rete_.get_by_label('Gli altri PC della rete possono aprire il programma').is_checked())
    for _ in range(3):                           # una porta libera adesso può prenderla un altro programma subito dopo
        rete_ = pg.get_by_role('form', name='Accesso dagli altri PC')
        rete_.get_by_label('Porta', exact=True).fill(str(PORTA))
        rete_.get_by_label('Gli altri PC della rete possono aprire il programma').check()
        with pg.expect_navigation():
            rete_.get_by_role('button', name='Salva', exact=True).click()
        m = messaggi(pg)
        if 'già usata' not in m:
            break
        PORTA = porta_libera()
        RETE = 'http://%s:%d' % (IP, PORTA)
    ok('acceso: il messaggio dice quale indirizzo aprire sugli altri PC',
       'Accesso dagli altri PC acceso' in m and ':%d/' % PORTA in m, m)
    ok('acceso: il messaggio avverte che non c\'è ancora nessun utente', 'Nessun utente ancora' in m, m)
    stato = principale(pg).locator('#stato-rete').inner_text()
    ok('lo stato dice «Acceso» con la porta e gli indirizzi', ('Acceso, sulla porta %d' % PORTA) in stato
       and ('http://' in stato), stato[:200])
    testo_ = principale(pg).inner_text()
    ok('il firewall spiegato (reti private sì, pubbliche no, il comando a mano) e il collegamento in chiaro',
       all(x in testo_ for x in ('Reti private', 'Reti pubbliche', 'netsh advfirewall', 'localport=%d' % PORTA,
                                 'senza protezione')), testo_[:200])

    nuovo = pg.get_by_role('form', name='Nuovo utente')
    nuovo.get_by_label('Nome', exact=True).fill(NOME)
    nuovo.get_by_label('Password per il primo accesso').fill(PRIMA)
    nuovo.get_by_role('row', name=nome_voce('Agenda')).get_by_role('radio', name='guardare e modificare',
                                                                    exact=True).check()
    nuovo.get_by_role('row', name=nome_voce('Cassa')).get_by_role('radio', name='solo guardare', exact=True).check()
    with pg.expect_navigation():
        nuovo.get_by_role('button', name='Aggiungi l\'utente', exact=True).click()
    m = messaggi(pg)
    riquadro = pg.get_by_role('region', name='Utente %s' % NOME)
    ok('utente aggiunto, con il suo riquadro', 'Utente %s aggiunto' % NOME in m and riquadro.count() == 1, m)
    ok('nel riquadro le aree scelte: Agenda da modificare, Cassa da guardare, Pazienti no',
       riquadro.get_by_role('row', name=nome_voce('Agenda')).get_by_role('radio', name='guardare e modificare',
                                                                          exact=True).is_checked()
       and riquadro.get_by_role('row', name=nome_voce('Cassa')).get_by_role('radio', name='solo guardare',
                                                                            exact=True).is_checked()
       and riquadro.get_by_role('row', name=nome_voce('Pazienti')).get_by_role('radio', name='non disponibile',
                                                                               exact=True).is_checked())

    # ------------------------------------------------------------------ da un'altra scheda, sull'indirizzo della rete
    altro = ctx.new_page()
    domande_altro = prepara_domande(altro)
    altro.on('pageerror', lambda e: err.append('rete: %s' % e))
    # i due rifiuti voluti (Cassa da salvare, Pazienti) sono pagine 403: il browser lo scrive fra gli errori, e qui si
    # contano a parte; ogni altro errore, anche un file che manca, fa cadere la prova
    rifiuti, contati = [], []

    def errore_altro(m):
        if m.type != 'error':
            return
        if '403 (FORBIDDEN)' in m.text and len(contati) < len(rifiuti):
            contati.append(m.text)
        else:
            err.append('rete: %s' % m.text)
    altro.on('response', lambda r: rifiuti.append(r.url.split(str(PORTA), 1)[-1]) if r.status == 403 else None)
    altro.on('console', errore_altro)
    altro.goto(RETE + '/oggi')
    ok('dall\'altro PC: la pagina di accesso, con il nome della struttura e senza menu',
       '/accesso' in altro.url and altro.get_by_role('button', name='Entra', exact=True).count() == 1
       and altro.get_by_role('navigation', name='Pagine').count() == 0, altro.url)
    altro.get_by_label('Nome', exact=True).fill(NOME)
    altro.get_by_label('Password', exact=True).fill('password sbagliata ma lunga')
    with altro.expect_navigation():
        altro.get_by_role('button', name='Entra', exact=True).click()
    ok('password sbagliata: «Nome o password non giusti.»',
       altro.get_by_role('alert').inner_text().strip() == 'Nome o password non giusti.', altro.url)
    altro.get_by_label('Nome', exact=True).fill(NOME)
    altro.get_by_label('Password', exact=True).fill(PRIMA)
    with altro.expect_navigation():
        altro.get_by_role('button', name='Entra', exact=True).click()
    ok('primo accesso: prima si sceglie una password propria', altro.url.endswith('/accesso/password'), altro.url)
    altro.get_by_label('Password di adesso').fill(PRIMA)
    altro.get_by_label('Password nuova', exact=False).first.fill(NUOVA)
    altro.get_by_label('Password nuova, di nuovo').fill(NUOVA)
    with altro.expect_navigation():
        altro.get_by_role('button', name='Cambia la password', exact=True).click()
    barra = altro.get_by_role('region', name='Utente', exact=True)
    ok('dentro: Oggi, con la barra «Entrato da un altro PC come…» e Esci',
       altro.url.endswith('/oggi') and barra.count() == 1 and NOME in barra.inner_text()
       and barra.get_by_role('button', name='Esci', exact=True).count() == 1, altro.url)
    ok('il messaggio «Password cambiata.»', 'Password cambiata.' in messaggi(altro), messaggi(altro))

    # Agenda: guardare e modificare → la nota del giorno si salva
    vai_dal_menu(altro, 'Giorno')
    nota = altro.locator('[data-guida="giorno-nota"]')
    if nota.get_attribute('open') is None:
        nota.locator('summary').click()
    nota.get_by_role('textbox').fill(NOTA)
    with altro.expect_navigation():
        nota.get_by_role('button', name='Salva', exact=True).click()
    ok('Agenda da modificare: la nota del giorno si salva dall\'altro PC',
       altro.locator('[data-guida="giorno-nota"]').get_by_role('textbox').input_value() == NOTA, altro.url)

    # Cassa: solo guardare → la pagina si apre, il salvataggio risponde «Solo guardare»
    altro.goto(RETE + '/cassa/listino')
    ok('Cassa da guardare: il listino si apre', altro.get_by_role('button', name='Salva il listino').count() == 1,
       altro.url)
    with altro.expect_navigation():
        altro.get_by_role('button', name='Salva il listino').click()
    titolo = altro.get_by_role('heading', level=1).inner_text()
    ok('Cassa da guardare: «Salva il listino» risponde «Solo guardare», in italiano',
       titolo == 'Solo guardare' and 'non si salva niente' in altro.content(), titolo)

    with altro.expect_navigation():
        altro.get_by_role('link', name='Torna alle pagine disponibili').click()
    ok('dal rifiuto, «Torna alle pagine disponibili» porta a Oggi', altro.url.endswith('/oggi'), altro.url)

    # Pazienti: non disponibile → la pagina in italiano, con il ritorno e chi chiedere
    vai_dal_menu(altro, 'Pazienti')
    corpo = altro.locator('main').inner_text()
    ok('Pazienti non data: «non è fra le parti disponibili», chi chiedere',
       'non è fra le parti disponibili per questo utente' in corpo and 'Aree e accessi' in corpo, corpo[:200])
    with altro.expect_navigation():
        altro.get_by_role('link', name='Torna alle pagine disponibili').click()
    ok('di nuovo «Torna alle pagine disponibili»: Oggi', altro.url.endswith('/oggi'), altro.url)

    # Esci: fuori davvero, anche per chi si fosse tenuto il cookie di prima (la sessione si chiude sul programma)
    cookie_di_prima = [c for c in ctx.cookies(RETE) if c['name'] == 'gestionale_rete']
    with altro.expect_navigation():
        altro.get_by_role('region', name='Utente', exact=True).get_by_role('button', name='Esci', exact=True).click()
    ok('Esci: di nuovo la pagina di accesso', '/accesso' in altro.url, altro.url)
    altro.goto(RETE + '/oggi')
    ok('dopo Esci, Oggi chiede di nuovo l\'accesso', '/accesso' in altro.url, altro.url)
    ctx.add_cookies(cookie_di_prima)
    altro.goto(RETE + '/oggi')
    ok('dopo Esci, nemmeno il cookie di prima fa rientrare', len(cookie_di_prima) == 1 and '/accesso' in altro.url,
       (len(cookie_di_prima), altro.url))

    # ------------------------------------------------------------------ di nuovo dal PC principale
    pg.goto(B + '/accesso')
    ok('il PC principale non vede mai la pagina di accesso', pg.url.rstrip('/').endswith(('/oggi', B.split('//')[1]))
       and pg.get_by_role('button', name='Entra', exact=True).count() == 0, pg.url)
    pg.goto(B + '/configura/accessi')
    registro = pg.locator('[data-guida="accessi-registro"]').inner_text()
    ok('il registro: entrato, password cambiata, nota salvata, Cassa negata, uscito, dall\'indirizzo dell\'altro PC',
       all(x in registro for x in ('entrato', 'password cambiata', 'POST /note-giorno', 'negato (solo guardare)',
                                   'uscito', NOME)) and (IP in registro or IP == '127.0.0.1'), registro[:400])

    # pulizia: la nota tolta dal PC, l'utente tolto (con la domanda), l'accesso spento
    vai_dal_menu(pg, 'Giorno')
    nota = pg.locator('[data-guida="giorno-nota"]')
    if nota.get_attribute('open') is None:
        nota.locator('summary').click()
    nota.get_by_role('textbox').fill('')
    with pg.expect_navigation():
        nota.get_by_role('button', name='Salva', exact=True).click()
    pg.goto(B + '/configura/accessi')
    with pg.expect_navigation():
        with rispondi(pg, si=True) as d:
            pg.get_by_role('region', name='Utente %s' % NOME).get_by_role('button', name='Togli %s' % NOME).click()
    ok('«Togli» fa la domanda e toglie l\'utente', d.testo and NOME in d.testo and 'Utente %s tolto' % NOME in messaggi(pg)
       and pg.get_by_role('region', name='Utente %s' % NOME).count() == 0, (d.testo, messaggi(pg)))
    rete_ = pg.get_by_role('form', name='Accesso dagli altri PC')
    rete_.get_by_label('Gli altri PC della rete possono aprire il programma').uncheck()
    rete_.get_by_label('Porta', exact=True).fill(porta_di_prima)          # e la porta di prima
    with pg.expect_navigation():
        rete_.get_by_role('button', name='Salva', exact=True).click()
    ok('spento: il messaggio e la porta della rete chiusa davvero',
       'Accesso dagli altri PC spento' in messaggi(pg) and chiusa(IP, PORTA) and chiusa('127.0.0.1', PORTA),
       messaggi(pg))
    ok('i soli rifiuti sono i due voluti (Cassa da salvare, Pazienti)', rifiuti == ['/cassa/listino', '/pazienti'],
       rifiuti)
    ok('rimessa la porta di prima', pg.get_by_role('form', name='Accesso dagli altri PC').get_by_label(
        'Porta', exact=True).input_value() == porta_di_prima, porta_di_prima)
    ok('nessun errore JavaScript', not err, err[:3])
    ok('nessuna domanda del browser inattesa', not domande.inattese and not domande_altro.inattese,
       domande.inattese + domande_altro.inattese)
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
