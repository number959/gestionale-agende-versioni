# -*- coding: utf-8 -*-
"""Prove nel browser dell'accesso dagli altri PC (1.13, accessi.py), su un gestionale gia' avviato con i dati di
prova (strumenti/demo.py), tutto il giro come lo fa la segreteria:
    python prove_accessi_browser.py http://127.0.0.1:5001
- dal PC principale: Configura → Impostazioni → «Aree e accessi»; l'accesso dagli altri PC acceso su una porta libera
  (mai la 5080 della clinica), con l'indirizzo da scrivere sugli altri PC, «nessuna richiesta da un altro PC» e il
  firewall spiegato (i comandi in «Per l'assistenza»); un utente rifiutato (la password con il suo nome) torna con nome e
  parti scritti; poi l'utente nuovo con Agenda «guardare e modificare», Cassa e Sala «solo guardare», riquadro aperto;
- da un'altra scheda, sull'indirizzo della rete (quello di questo PC fuori da 127.*, come un altro PC): la pagina di
  accesso, la password da cambiare al primo accesso, la barra «Entrato da un altro PC come…» con il suo stile; in Agenda
  la nota del giorno si salva, in Cassa la pagina si apre con «Salva il listino» spento e la riga «Solo guardare», in
  Sala le caselle della checklist spente, Pazienti risponde con la pagina in italiano e «Torna alle pagine disponibili»;
  «Esci», e la pagina dopo chiede di nuovo l'accesso;
- di nuovo dal PC principale: la pagina di accesso non c'è, il registro dice chi è entrato, uscito e cosa ha salvato; il
  riquadro chiuso dell'utente con le parti in una riga; «Togli» fa la domanda; l'accesso spento chiude davvero la porta;
  la checklist con un rifiuto finto del programma dice il suo motivo (e senza risposta «il programma non risponde»).
Alla fine il gestionale di prova torna come prima: utente tolto, nota tolta, accesso spento.
La cornice (menu, messaggi, domande) si cerca per ruolo e nome con gli aiuti di aiuti_browser.py; ogni domanda passa
da rispondi(), e una domanda che nessuno aspettava fa cadere la prova."""
import json
import os
import re
import socket
import sys
from datetime import date, timedelta

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
    if pg.get_by_role('group', name='Utente %s' % NOME).count():
        # una prova di prima fermata a metà: si riparte da capo (il riquadro dell'utente si apre con un clic sul nome)
        riquadro = pg.get_by_role('group', name='Utente %s' % NOME)
        if riquadro.get_attribute('open') is None:
            riquadro.locator('summary').click()
        with pg.expect_navigation():
            with rispondi(pg, si=True):
                riquadro.get_by_role('button', name='Togli %s' % NOME).click()
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
    ok('il firewall spiegato (reti private sì, pubbliche no, le regole che bloccano) e il collegamento in chiaro; i '
       'comandi chiusi in «Per l\'assistenza»',
       all(x in testo_ for x in ('Reti private', 'Reti pubbliche', 'bloccano', 'senza protezione'))
       and 'netsh' not in testo_, testo_[:200])
    ok('l\'accesso acceso dice che dagli altri PC non è ancora arrivato niente',
       'Ancora nessuna richiesta da un altro PC' in stato, stato[:300])
    principale(pg).get_by_text('Per l\'assistenza: i comandi del firewall').click()
    comandi = principale(pg).locator('#firewall-assistenza').inner_text()
    ok('«Per l\'assistenza»: togliere tutte le regole del programma, poi quella per la porta (private e dominio)',
       'delete rule name=all program="' in comandi and 'localport=%d' % PORTA in comandi
       and 'profile=private,domain' in comandi, comandi[:300])

    # un utente rifiutato (la password con il suo nome): la pagina torna con quello che si era scritto
    nuovo = pg.get_by_role('form', name='Nuovo utente')
    nuovo.get_by_label('Nome', exact=True).fill(NOME)
    nuovo.get_by_label('Password per il primo accesso').fill('Sportello di mare blu')
    nuovo.get_by_role('row', name=nome_voce('Agenda')).get_by_role('radio', name='guardare e modificare',
                                                                    exact=True).check()
    nuovo.get_by_role('row', name=nome_voce('Cassa')).get_by_role('radio', name='solo guardare', exact=True).check()
    with pg.expect_navigation():
        nuovo.get_by_role('button', name='Aggiungi l\'utente', exact=True).click()
    nuovo = pg.get_by_role('form', name='Nuovo utente')
    # il motivo e il modulo davanti agli occhi (il browser va a #nuovo-utente; il campo della password ha il fuoco)
    alto = pg.evaluate("document.getElementById('errore-nuovo').getBoundingClientRect().top")
    ok('rifiutato: il motivo accanto al modulo, il nome e le parti come scritti, la password no, il modulo davanti',
       'nome dell\'utente' in nuovo.get_by_role('alert').inner_text()
       and nuovo.get_by_label('Nome', exact=True).input_value() == NOME
       and nuovo.get_by_label('Password per il primo accesso').input_value() == ''
       and nuovo.get_by_role('row', name=nome_voce('Agenda')).get_by_role('radio', name='guardare e modificare',
                                                                           exact=True).is_checked()
       and nuovo.get_by_role('row', name=nome_voce('Cassa')).get_by_role('radio', name='solo guardare',
                                                                         exact=True).is_checked()
       and 0 <= alto < 900, (alto, nuovo.inner_text()[:200]))

    nuovo.get_by_label('Password per il primo accesso').fill(PRIMA)
    nuovo.get_by_role('row', name=nome_voce('Sala operatoria')).get_by_role('radio', name='solo guardare',
                                                                             exact=True).check()
    with pg.expect_navigation():
        nuovo.get_by_role('button', name='Aggiungi l\'utente', exact=True).click()
    m = messaggi(pg)
    riquadro = pg.get_by_role('group', name='Utente %s' % NOME)
    ok('utente aggiunto, con il suo riquadro aperto', 'Utente %s aggiunto' % NOME in m and riquadro.count() == 1
       and riquadro.get_attribute('open') is not None, m)
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
    stile = barra.evaluate("e => { const s = getComputedStyle(e); return [s.display, s.paddingLeft]; }")
    ok('la barra «Entrato da un altro PC» ha il suo stile (in riga, allineata alla pagina)', stile == ['flex', '18px'], stile)

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

    ok('Agenda da modificare: nessuna riga «Solo guardare» e il «Salva» della nota acceso',
       altro.locator('[data-solo-guardare-riga]').count() == 0
       and altro.locator('[data-guida="giorno-nota"]').get_by_role('button', name='Salva', exact=True).is_enabled())

    # Cassa: solo guardare → la pagina si apre, ma «Salva il listino» è spento, con la riga che lo dice
    altro.goto(RETE + '/cassa/listino')
    salva = altro.get_by_role('button', name='Salva il listino')
    riga = altro.locator('[data-solo-guardare-riga]')
    ok('Cassa da guardare: il listino si apre, «Salva il listino» spento con la spiegazione, e la riga in cima',
       salva.count() == 1 and salva.is_disabled() and 'Solo guardare' in (salva.get_attribute('title') or '')
       and riga.count() == 1 and 'Solo guardare: per «Cassa»' in riga.inner_text(), altro.url)

    # Sala da guardare: le caselle della checklist spente (cercate nei prossimi giorni della prova)
    caselle = None
    for settimana in range(5):
        altro.goto(RETE + '/sala/%s?giorni=7' % (date.today() + timedelta(days=7 * settimana)).isoformat())
        if altro.locator('form.checklist input[type="checkbox"]').count():
            caselle = altro.locator('form.checklist input[type="checkbox"]')
            break
    ok('Sala da guardare: le caselle della checklist sono spente', caselle is not None and caselle.count()
       and all(caselle.nth(i).is_disabled() for i in range(caselle.count())), caselle.count() if caselle else 'nessuna')

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
    ok('il registro: entrato, password cambiata, nota salvata, Pazienti negata, uscito, dall\'indirizzo dell\'altro PC '
       '(la Cassa da salvare non c\'è più: il bottone è spento)',
       all(x in registro for x in ('entrato', 'password cambiata', 'POST /note-giorno', 'negato GET /pazienti',
                                   'uscito', NOME)) and 'negato (solo guardare)' not in registro
       and (IP in registro or IP == '127.0.0.1'), registro[:400])

    # pulizia: la nota tolta dal PC, l'utente tolto (con la domanda), l'accesso spento
    vai_dal_menu(pg, 'Giorno')
    nota = pg.locator('[data-guida="giorno-nota"]')
    if nota.get_attribute('open') is None:
        nota.locator('summary').click()
    nota.get_by_role('textbox').fill('')
    with pg.expect_navigation():
        nota.get_by_role('button', name='Salva', exact=True).click()
    pg.goto(B + '/configura/accessi')
    riquadro = pg.get_by_role('group', name='Utente %s' % NOME)
    ok('il riquadro dell\'utente, chiuso, dice le sue parti in una riga',
       riquadro.get_attribute('open') is None and 'Agenda, Cassa (solo guardare), Sala operatoria (solo guardare)'
       in riquadro.locator('summary').inner_text(), riquadro.locator('summary').inner_text())
    riquadro.locator('summary').click()
    with pg.expect_navigation():
        with rispondi(pg, si=True) as d:
            riquadro.get_by_role('button', name='Togli %s' % NOME).click()
    ok('«Togli» fa la domanda e toglie l\'utente', d.testo and NOME in d.testo and 'Utente %s tolto' % NOME in messaggi(pg)
       and pg.get_by_role('group', name='Utente %s' % NOME).count() == 0, (d.testo, messaggi(pg)))
    rete_ = pg.get_by_role('form', name='Accesso dagli altri PC')
    rete_.get_by_label('Gli altri PC della rete possono aprire il programma').uncheck()
    rete_.get_by_label('Porta', exact=True).fill(porta_di_prima)          # e la porta di prima
    with pg.expect_navigation():
        rete_.get_by_role('button', name='Salva', exact=True).click()
    ok('spento: il messaggio e la porta della rete chiusa davvero',
       'Accesso dagli altri PC spento' in messaggi(pg) and chiusa(IP, PORTA) and chiusa('127.0.0.1', PORTA),
       messaggi(pg))
    ok('il solo rifiuto è quello voluto (Pazienti): «Salva il listino» spento non manda niente', rifiuti == ['/pazienti'],
       rifiuti)
    ok('rimessa la porta di prima', pg.get_by_role('form', name='Accesso dagli altri PC').get_by_label(
        'Porta', exact=True).input_value() == porta_di_prima, porta_di_prima)
    # la checklist: se il programma rifiuta, il messaggio dice il suo motivo (prima: «il programma non risponde», falso)
    for settimana in range(5):
        pg.goto(B + '/sala/%s?giorni=7' % (date.today() + timedelta(days=7 * settimana)).isoformat())
        if pg.locator('form.checklist input[type="checkbox"]').count():
            break
    casella = pg.locator('form.checklist input[type="checkbox"]').first
    motivo = 'Per «Sala operatoria» questo utente può solo guardare: non si salva niente.'
    pg.route('**/checklist', lambda r: r.fulfill(status=403, content_type='application/json',
                                                  body=json.dumps({'errore': motivo})))
    prima = casella.is_checked()
    with rispondi(pg, si=True) as d:
        casella.click()
    pg.wait_for_timeout(300)
    ok('checklist rifiutata: il messaggio dice il motivo del programma, e la casella torna com\'era',
       d.testo == 'Checklist non salvata: ' + motivo and casella.is_checked() == prima, d.testo)
    pg.unroute('**/checklist')
    pg.route('**/checklist', lambda r: r.abort())
    with rispondi(pg, si=True) as d:
        casella.click()
    pg.wait_for_timeout(300)
    ok('gemello: senza risposta «il programma non risponde»', d.testo and 'il programma non risponde' in d.testo
       and casella.is_checked() == prima, d.testo)
    pg.unroute('**/checklist')
    err[:] = [e for e in err if '403' not in e and 'Failed to load resource' not in e]   # i due finti, voluti

    ok('nessun errore JavaScript', not err, err[:3])
    ok('nessuna domanda del browser inattesa', not domande.inattese and not domande_altro.inattese,
       domande.inattese + domande_altro.inattese)
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
