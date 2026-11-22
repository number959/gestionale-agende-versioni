# -*- coding: utf-8 -*-
"""Prove nel browser della 1.12 (gli ambulatori), su un gestionale gia'
avviato con i dati di prova (strumenti/demo.py):
    python prove_112_browser.py http://127.0.0.1:5001
- la pianificazione della settimana prossima: la matrice con due righe di
  intestazione (giorni, mezze giornate), Lippiello in Ambulatorio 1 tutte le
  mattine, celle DISPONIBILI;
- dal «+» di una cella libera si mette Galasso: compare il suo nome; dalla
  «x» (con la conferma) si toglie: la cella torna DISPONIBILE, e i dati di
  prova restano come prima;
- «Stampa e scarica»: i quattro collegamenti, la matrice in Excel scaricata
  con il suo nome;
- la programmazione del mese: la tabella e l'Excel scaricato con il suo nome;
- il gruppo Ambulatori del menu e' segnato attivo in tutte e due le pagine;
- dalla 1.12.2 il riepilogo live: la frase, i quattro gruppi che sommano al
  totale, una riga per stanza con turni e visite come nel JSON, la linea di
  adesso, le notifiche nascoste, il telefono senza scorrimento laterale e il
  modo schermo; il riepilogo del periodo: i gruppi che sommano, i periodi
  pronti, la freccia, l'Excel; nessun errore JavaScript;
- dalla tappa 1 della base la dashboard rimasta aperta, con l'orologio della pagina mandato avanti: il rinnovo di
  ogni minuto ricarica la pagina solo se cambia data-giorno (giorno e versione), e ogni richiesta resta dentro
  /riepilogo-live, /static/ e /logo/.
La cornice (menu, tendine del menu e della pagina, messaggi, notifiche, la domanda della «×») si cerca per ruolo e
nome con gli aiuti di aiuti_browser.py, come un lettore di schermo (tappa 1 della base); la domanda del browser passa
da rispondi(), e una domanda che nessuno aspettava fa cadere la prova.
Mette e toglie un turno sui dati di prova: alla fine sono come prima."""
import os
import re
import sys
from datetime import date, timedelta

from playwright.sync_api import expect, sync_playwright

from aiuti_browser import (GRUPPI, NOME_MENU, apri_comandi, apri_gruppo, gruppo, gruppo_attivo, menu, messaggi, nome_voce,
                           prepara_domande, rispondi, tendina_aperta)

from aiuti_browser import indirizzo_di_prova  # noqa: E402
B = indirizzo_di_prova(sys.argv)   # mai la porta 5000, quella del programma vero
esiti = []
OGGI = date.today()
LUN = OGGI - timedelta(days=OGGI.weekday()) + timedelta(days=7)        # il lunedi della settimana prossima: tutta nel futuro
GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']


def tendine_aperte():
    """Per la diagnosi: le tendine del menu aperte adesso, con il loro nome, e se il mouse o il fuoco sono nel loro
    gruppo (quello che le tiene aperte)."""
    return tendina_aperta(pg).evaluate_all(
        "ts => ts.map(t => ({gruppo: t.getAttribute('aria-label'), mouse_sopra: t.parentElement.matches(':hover'),"
        " focus_dentro: t.parentElement.matches(':focus-within')}))")


def apri_stampa_e_scarica():
    """Apre «Stampa e scarica» come una persona e torna la sua tendina: il mouse prima in un punto neutro della pagina,
    poi nessuna tendina del menu deve essere aperta. 21/11/2026, nell'animata: la tendina «Stampa e scarica» entra con
    un'animazione, Playwright fa scorrere la pagina per cliccarne una voce e lascia il mouse in cima alla finestra; al
    clic dopo la pagina torna in cima, il gruppo «Ambulatori» del menu finisce sotto il mouse e apre la sua tendina sopra
    il pulsante (una volta in tutti i giri di quel giorno; la causa l'ha trovata la revisione della 1.12.7). Con il mouse
    in (2, 500) non succede."""
    pg.mouse.move(2, 500)
    try:
        expect(tendina_aperta(pg)).to_have_count(0, timeout=5000)
    except AssertionError:
        ok('nessuna tendina del menu resta aperta da sola', False, tendine_aperte())
        raise
    return apri_comandi(pg, 'Stampa e scarica')


def notifiche(anche_nascoste=False):
    """La zona delle notifiche (role="region", nome «Notifiche», in _menu.html). Per ruolo una zona nascosta non si
    vede: anche_nascoste=True la trova lo stesso, per dire che c'è ma è nascosta."""
    return pg.get_by_role('region', name='Notifiche', exact=True, include_hidden=anche_nascoste)


def menu_anche_nascosto():
    """Il menu anche se nascosto. «Senza menu» vuol dire che il menu non c'è nella pagina, come contava prima
    nav.menu: per ruolo un menu nascosto non si vede, ma i suoi collegamenti e i suoi tasti rapidi ci sarebbero."""
    return pg.get_by_role('navigation', name=NOME_MENU, exact=True, include_hidden=True)


# l'aspetto del pulsante di un gruppo del menu: quello che cambia fra il gruppo attivo e gli altri
ASPETTO = ("b => { const s = getComputedStyle(b); return [s.color, s.backgroundColor, s.opacity, s.fontWeight,"
           " s.borderBottomColor, s.boxShadow, s.textDecorationLine].join(' | '); }")


def gruppo_segnato():
    """Il gruppo attivo del menu (gruppo_attivo: aria-current, per chi usa un lettore di schermo), ma solo se si vede
    anche: il suo pulsante deve avere un aspetto diverso da quello di ogni altro gruppo. Prima la prova guardava la
    classe «attivo», che lo colora: aria-current da solo non vedrebbe un menu che non lo colora più."""
    nome = gruppo_attivo(pg)
    if nome not in GRUPPI:
        return nome
    pg.mouse.move(2, 500)                    # niente mouse sopra i gruppi: passandoci sopra cambiano aspetto
    pg.wait_for_timeout(300)                 # nell'animata il cambio dura .15 secondi
    aspetto = {g: gruppo(pg, g).evaluate(ASPETTO) for g in GRUPPI}
    come = [g for g in GRUPPI if g != nome and aspetto[g] == aspetto[nome]]
    return nome if not come else '%s, ma si vede come %s' % (nome, ', '.join(come))


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT', accept_downloads=True)
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                        "localStorage.setItem('gestionale-tema', 'chiaro'); } catch (e) {}")
    pg = ctx.new_page()
    domande = prepara_domande(pg)            # subito: ogni domanda del browser passa da qui
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)

    settimana = B + '/ambulatori/settimana/%s?struttura=1' % LUN.isoformat()
    pg.goto(settimana)
    pg.wait_for_selector('#matrice-ambulatori')
    testa = pg.locator('#matrice-ambulatori thead tr')
    ok('la matrice ha due righe di intestazione', testa.count() == 2, testa.count())
    giorni = [x.strip().split('\n')[0] for x in testa.nth(0).locator('th').all_inner_texts()][1:]
    ok('i giorni di apertura, da lunedì a sabato, con la data',
       len(giorni) == 6 and all(g.startswith('%s %d/%d' % (GIORNI[k], (LUN + timedelta(days=k)).day, (LUN + timedelta(days=k)).month))
                                for k, g in enumerate(giorni)), giorni)
    meta = testa.nth(1).locator('th').all_inner_texts()
    ok('sotto ogni giorno mattina e pomeriggio (08:00–14:00, 14:00–20:00)',
       len(meta) == 12 and meta[0] == '08:00–14:00' and meta[1] == '14:00–20:00' and len(set(meta)) == 2, meta[:4])
    ok('almeno una cella DISPONIBILE in verde', pg.locator('#matrice-ambulatori td.libera .disponibile').count() >= 1)
    riga = pg.locator('#matrice-ambulatori tbody tr', has=pg.locator('th.stanza-sett', has_text='Ambulatorio 1'))
    mattine = riga.locator('td').evaluate_all("tds => tds.filter((td, i) => i % 2 === 0).map(td => td.textContent.replace(/\\s+/g, ' ').trim())")
    ok('Lippiello in Ambulatorio 1 tutte le mattine (dati di prova)', len(mattine) == 6 and all('Lippiello' in x and '08:00–14:00' in x for x in mattine), mattine[:2])
    pomeriggi = riga.locator('td').evaluate_all("tds => tds.filter((td, i) => i % 2 === 1).map(td => td.className)")
    ok('i pomeriggi di Ambulatorio 1 liberi', len(pomeriggi) == 6 and all('libera' in x for x in pomeriggi), pomeriggi)
    attivo = gruppo_segnato()
    ok('il menu: il gruppo Ambulatori è segnato attivo', attivo == 'Ambulatori', attivo or 'nessun gruppo attivo')
    pg.mouse.move(2, 500)
    voci = apri_gruppo(pg, 'Ambulatori').get_by_role('link').all_inner_texts()
    ok('nel gruppo: Pianificazione della settimana, Programmazione del mese, Riepilogo live, Riepilogo del periodo, Esportazioni',
       len(voci) == 5 and 'Pianificazione' in voci[0] and 'Programmazione' in voci[1] and 'Riepilogo live' in voci[2] and
       'Riepilogo del periodo' in voci[3] and 'Esportazioni in Excel' in voci[4], voci)
    pg.keyboard.press('Escape')              # la tendina si chiude; il mouse via dal menu
    pg.mouse.move(2, 500)

    # Metti: una cella libera, il «+», Galasso, Metti
    cella = pg.locator('#matrice-ambulatori td.libera:has(details.metti)').first
    chiave = cella.get_attribute('data-cella')
    ok('una cella libera con il «+»', chiave, chiave)
    cella.locator('details.metti summary').click()
    modulo = cella.locator('details.metti form')
    modulo.wait_for(state='visible')
    ok('il modulo del «+» si apre con stanza e giorno', modulo.is_visible() and chiave.split('_')[1] == modulo.locator('input[name=data]').input_value(),
       modulo.locator('input[name=data]').input_value())
    ore = (modulo.locator('input[name=ora_inizio]').input_value(), modulo.locator('input[name=ora_fine]').input_value())
    ok('le ore proposte sono la mezza giornata intera', ore in (('08:00', '14:00'), ('14:00', '20:00')), ore)
    modulo.locator('select[name=operatore]').select_option(label='Galasso')
    with pg.expect_navigation():
        modulo.locator('button[type=submit]').click()
    avviso = messaggi(pg)
    ok('«Turno salvato» con medico, stanza e ore', 'Turno salvato: Galasso' in avviso and 'ogni %s' % GIORNI[date.fromisoformat(chiave.split('_')[1]).weekday()] in avviso, avviso[:200])
    cella = pg.locator('td[data-cella="%s"]' % chiave)
    nomi = cella.locator('.turno-sett a').all_inner_texts()
    ok('Galasso compare nella cella, che non è più libera', nomi == ['Galasso'] and 'occupata' in (cella.get_attribute('class') or ''), (nomi, cella.get_attribute('class')))
    ok('il nome apre il turno e torna qui', '/anagrafiche/turni/' in (cella.locator('.turno-sett a').first.get_attribute('href') or '')
       and 'torna=' in (cella.locator('.turno-sett a').first.get_attribute('href') or ''), cella.locator('.turno-sett a').first.get_attribute('href'))

    # Togli: la «x» chiede conferma; con Annulla il turno resta (la pagina non cambia), con OK la cella torna disponibile
    url_prima = pg.url
    with rispondi(pg, si=False) as d:
        cella.get_by_role('button', name=re.compile('^Togli ')).click()
    pg.wait_for_timeout(600)                 # un modulo partito lo stesso cambierebbe pagina in questo tempo
    pg.wait_for_load_state()
    cella = pg.locator('td[data-cella="%s"]' % chiave)
    ok('la «x» con Annulla: il turno resta', d.testo and 'Togliere Galasso' in d.testo and pg.url == url_prima
       and cella.locator('.turno-sett a').all_inner_texts() == ['Galasso'], (d.testo, pg.url))
    with pg.expect_navigation():
        with rispondi(pg) as d:
            cella.get_by_role('button', name=re.compile('^Togli ')).click()
    ok('la «x» chiede conferma', d.testo and 'Togliere Galasso' in d.testo and 'da questa settimana in poi' in d.testo, d.testo or 'nessuna conferma')
    avviso = messaggi(pg)
    ok('«Turno tolto»', 'Turno tolto: Galasso' in avviso, avviso[:200])
    cella = pg.locator('td[data-cella="%s"]' % chiave)
    ok('la cella è di nuovo DISPONIBILE (i dati di prova come prima)', cella.locator('.disponibile').count() == 1 and 'libera' in (cella.get_attribute('class') or '')
       and cella.locator('.turno-sett').count() == 0, cella.get_attribute('class'))

    # Stampa e scarica
    voci = apri_stampa_e_scarica().get_by_role('link').all_inner_texts()
    ok('«Stampa e scarica»: matrice, settimana tipo, sala, ambulatori e sala, programmazione, tutte le esportazioni, stampa',
       len(voci) == 7 and 'La matrice in Excel' in voci[0] and 'settimana tipo' in voci[1] and 'sala operatoria in Excel' in voci[2]
       and 'Ambulatori e sala' in voci[3] and 'Programmazione del mese' in voci[4] and 'Tutte le esportazioni' in voci[5]
       and 'Stampa' in voci[6], voci)
    tendina = apri_stampa_e_scarica()
    with pg.expect_download() as scaricato:
        tendina.get_by_role('link', name=nome_voce('Ambulatori e sala in Excel')).click()
    ok('ambulatori e sala della settimana in un file solo',
       scaricato.value.suggested_filename == 'ambulatori-e-sala-settimana-%s.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)
    tendina = apri_stampa_e_scarica()
    with pg.expect_download() as scaricato:
        tendina.get_by_role('link', name=nome_voce('La matrice in Excel')).click()
    ok('la matrice in Excel si scarica con il nome della settimana',
       scaricato.value.suggested_filename == 'matrice-ambulatori-%s.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)
    tendina = apri_stampa_e_scarica()
    with pg.expect_download() as scaricato:
        tendina.get_by_role('link', name=nome_voce('La settimana tipo in Excel')).click()
    ok('la settimana tipo in Excel', scaricato.value.suggested_filename == 'matrice-ambulatori-%s-settimana-tipo.xlsx' % LUN.isoformat(), scaricato.value.suggested_filename)

    # 1.12.3: la sala operatoria in fondo alla matrice, solo da guardare (la settimana di oggi ha interventi)
    pg.goto(B + '/ambulatori/settimana/%s?struttura=1' % OGGI.isoformat())
    pg.wait_for_selector('#matrice-ambulatori')
    parte = pg.locator('#matrice-ambulatori tbody.parte-sala')
    sale_viste = parte.locator('th.stanza-sett').all_inner_texts() if parte.count() else []
    ok('la sala operatoria in fondo alla matrice, con le due sale dei dati di prova',
       parte.count() == 1 and sale_viste == ['Sala A', 'Sala B'], sale_viste)
    ok('nella sala niente «+» e niente «×»: si programma dalla pagina Sala',
       parte.locator('details.metti').count() == 0 and parte.locator('form.togli-turno').count() == 0)
    link = parte.locator('a.interventi-sala')
    ok('gli interventi della settimana portano alla pagina Sala del giorno',
       link.count() >= 1 and '/sala/' in (link.first.get_attribute('href') or ''), link.count())
    ok('le sale non sono fra le stanze degli ambulatori',
       pg.locator('#matrice-ambulatori tbody:not(.parte-sala) th.stanza-sett', has_text='Sala A').count() == 0)
    larga = pg.evaluate("() => document.querySelector('tbody.parte-sala th.titolo-sala').colSpan")
    ok('il titolo della sala prende tutta la riga', larga == 1 + 2 * len(pg.locator('#matrice-ambulatori thead tr').nth(0).locator('th').all()) - 2,
       larga)

    # la programmazione del mese
    pg.goto(B + '/ambulatori/mese/%s?struttura=1' % LUN.strftime('%Y-%m'))
    pg.wait_for_selector('#programmazione-ambulatori')
    righe = pg.locator('#programmazione-ambulatori tr')
    corpo = pg.locator('#programmazione-ambulatori').inner_text()
    ok('la programmazione ha le sue righe, con Lippiello tutti i giorni in Ambulatorio 1',
       righe.count() > 6 and corpo.count('Lippiello') >= 6 and 'Ambulatorio 1' in corpo, (righe.count(), corpo.count('Lippiello')))
    ok('le date del mese sono numeri separati da virgole', any(',' in x for x in pg.locator('#programmazione-ambulatori tr td:nth-child(4)').all_inner_texts()))
    attivo = gruppo_segnato()
    ok('anche qui il gruppo Ambulatori è attivo', attivo == 'Ambulatori', attivo)
    with pg.expect_download() as scaricato:
        pg.locator('a.bottone.primario', has_text='Scarica in Excel').click()
    ok('la programmazione in Excel si scarica con il nome del mese',
       scaricato.value.suggested_filename == 'programmazione-ambulatori-%s.xlsx' % LUN.strftime('%Y-%m'), scaricato.value.suggested_filename)
    pg.locator('details.calendario-mese summary').click()
    ok('il calendario del mese si apre', pg.locator('details.calendario-mese[open] table tr').count() > 1)
    # 1.12.3: la sala dopo le specialità e nel calendario, con la colonna degli interventi
    sala_mese = pg.locator('#programmazione-ambulatori tr.riga-sala')
    ok('la programmazione ha la sala operatoria dopo le specialità', sala_mese.count() >= 2 and
       'Sala operatoria' in sala_mese.first.inner_text(), sala_mese.count())
    ok('il calendario ha la colonna degli interventi e le righe della sala',
       'Interventi' in pg.locator('details.calendario-mese table tr').first.inner_text()
       and pg.locator('details.calendario-mese tr.riga-sala').count() >= 1)
    tendina = apri_comandi(pg, 'Altre esportazioni')
    altre = tendina.get_by_role('link').all_inner_texts()
    ok('«Altre esportazioni» del mese: la sala, tutto insieme, la pagina delle esportazioni',
       len(altre) == 3 and 'sala operatoria del mese' in altre[0] and 'Ambulatori e sala' in altre[1] and 'Tutte le esportazioni' in altre[2], altre)
    with pg.expect_download() as scaricato:
        tendina.get_by_role('link', name=nome_voce('La sala operatoria del mese')).click()
    # sul telefono la tendina aperta resta dentro lo schermo (prima usciva a sinistra)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.reload()
    box = apri_comandi(pg, 'Altre esportazioni').bounding_box()
    ok('sul telefono la tendina «Altre esportazioni» resta dentro lo schermo',
       box and box['x'] >= 0 and box['x'] + box['width'] <= 390, box)
    pg.set_viewport_size({'width': 1366, 'height': 820})
    ok('la sala del mese in Excel', scaricato.value.suggested_filename == 'sala-operatoria-mese-%s.xlsx' % LUN.strftime('%Y-%m'),
       scaricato.value.suggested_filename)

    # 1.12.3: la pagina delle esportazioni: nove pulsanti, la data scelta, un file vero
    pg.goto(B + '/esportazioni?struttura=1&data=%s' % OGGI.isoformat())
    pg.wait_for_selector('#esportazioni')
    pulsanti = pg.locator('#esportazioni a.bottone')
    ok('esportazioni: nove pulsanti, giorno, settimana e mese per ambulatori, sala e tutto', pulsanti.count() == 9, pulsanti.count())
    righe_esp = pg.locator('#esportazioni tr[data-periodo]').evaluate_all("trs => trs.map(t => t.dataset.periodo)")
    ok('esportazioni: le righe sono giorno, settimana e mese', righe_esp == ['giorno', 'settimana', 'mese'], righe_esp)
    with pg.expect_download() as scaricato:
        pg.locator('#esportazioni tr[data-periodo="giorno"] a.bottone').nth(1).click()
    ok('esportazioni: la sala del giorno si scarica con il suo nome',
       scaricato.value.suggested_filename == 'sala-operatoria-giorno-%s.xlsx' % OGGI.isoformat(), scaricato.value.suggested_filename)
    pg.fill('form.scelta-data input[name="data"]', (OGGI + timedelta(days=40)).isoformat())
    pg.locator('form.scelta-data button').click()
    pg.wait_for_selector('#esportazioni')
    ok('esportazioni: cambiando la data cambiano i pulsanti',
       ((OGGI + timedelta(days=40)).isoformat() + '.xlsx') in (pulsanti.first.get_attribute('href') or ''), pulsanti.first.get_attribute('href'))
    attivo = gruppo_segnato()
    ok('esportazioni: il gruppo Ambulatori è attivo', attivo == 'Ambulatori', attivo)
    pg.set_viewport_size({'width': 390, 'height': 800})
    largo = pg.evaluate('document.documentElement.scrollWidth')
    ok('esportazioni: sul telefono niente scorrimento laterale', largo <= 392, largo)
    pg.set_viewport_size({'width': 1366, 'height': 820})

    # 1.12.2: il riepilogo live piu' chiaro, a qualsiasi ora la prova giri
    import json as _json
    import urllib.request as _url
    dati = _json.loads(_url.urlopen(B + '/riepilogo-live.json?struttura=1', timeout=30).read().decode('utf-8'))
    # le notifiche gia' viste nelle pagine di prima non contano: si azzera la memoria e si guardano le richieste
    pg.evaluate("sessionStorage.removeItem('notifiche-viste')")
    richieste_notifiche = []
    pg.on('request', lambda q: richieste_notifiche.append(q.url) if '/notifiche' in q.url else None)
    # gemello del «le notifiche non si chiedono» del riepilogo live (piu' sotto): in una pagina normale le stesse tre
    # cose ci sono (la richiesta a /notifiche, le notifiche nella loro zona, la memoria delle viste). I dati di prova
    # hanno sempre cose da fare di oggi e di ieri, quindi qualche notifica c'e'.
    pg.goto(B + '/ambulatori/riepilogo?struttura=1')
    try:
        notifiche().get_by_role('status').first.wait_for(timeout=8000)
    except Exception:
        pass
    viste = pg.evaluate("sessionStorage.getItem('notifiche-viste')")
    ok('notifiche (gemello): in una pagina normale si chiedono, compaiono e risultano viste',
       any('/notifiche' in u for u in richieste_notifiche) and notifiche().get_by_role('status').count() >= 1 and
       viste not in (None, '{}'), (richieste_notifiche, notifiche().get_by_role('status').count(), viste))
    del richieste_notifiche[:]                       # la stessa lista: la guarda ancora il pg.on di sopra
    pg.evaluate("sessionStorage.removeItem('notifiche-viste')")
    pg.goto(B + '/riepilogo-live?struttura=1')
    pg.wait_for_selector('#riepilogo-live .frase-live')
    ok('riepilogo live (gemello del modo schermo, piu\' sotto): nella pagina normale il menu c\'è',
       menu(pg).count() == 1, menu(pg).count())
    ok('riepilogo live: la frase in cima, in parole', len(pg.inner_text('.frase-live').strip()) > 20, pg.inner_text('.frase-live'))
    conti = pg.locator('.conti-oggi-live li b').all_inner_texts()
    ok('riepilogo live: fatti, in corso, da segnare e da fare sommano agli appuntamenti di oggi',
       len(conti) == 5 and sum(int(x) for x in conti[1:]) == int(conti[0]) == dati['oggi']['totale'], conti)
    righe = pg.locator('.linea-live .riga-live:not(.asse-live)')
    frasi = [x.strip() for x in pg.locator('.linea-live .riga-live .stato-live').all_inner_texts()]
    ok('riepilogo live: una riga per stanza, ognuna con la frase del JSON', righe.count() == len(dati['stanze']) and
       frasi == [x['frase'] for x in dati['stanze']], (frasi, [x['frase'] for x in dati['stanze']]))
    ok('riepilogo live: i turni sulla linea del tempo come nel JSON',
       pg.locator('.pista-live .turno-live').count() == sum(len(x['linea']['turni']) for x in dati['stanze']) and
       pg.locator('.pista-live .visita-live').count() == sum(len(x['linea']['visite']) for x in dati['stanze']))
    linee = pg.locator('.pista-live .adesso-live').count()
    ok('riepilogo live: la linea di adesso in ogni stanza, o in nessuna fuori orario',
       linee == (len(dati['stanze']) if dati['asse']['adesso'] is not None else 0), linee)
    ok('riepilogo live: le notifiche non coprono la pagina (la zona c\'è, ma nascosta)',
       notifiche(anche_nascoste=True).count() == 1 and notifiche().count() == 0 and not notifiche(anche_nascoste=True).is_visible(),
       (notifiche(anche_nascoste=True).count(), notifiche().count(), notifiche(anche_nascoste=True).is_visible()))
    pg.wait_for_timeout(1500)
    ok('riepilogo live: le notifiche non si chiedono nemmeno (non risultano viste nelle altre pagine)',
       not richieste_notifiche and pg.evaluate("sessionStorage.getItem('notifiche-viste')") in (None, '{}') and
       notifiche(anche_nascoste=True).get_by_role('status', include_hidden=True).count() == 0,
       (richieste_notifiche, pg.evaluate("sessionStorage.getItem('notifiche-viste')")))
    misura = pg.evaluate("(() => { const r = document.querySelector('.legenda-live .gr-turno').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })()")
    ok('riepilogo live: i quadratini della legenda sono tutti piccoli (nessuna classe di altre pagine)', misura[0] <= 16, misura)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(300)
    ok('riepilogo live: sul telefono la pagina non scorre di lato',
       pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), pg.evaluate('document.documentElement.scrollWidth'))
    pg.set_viewport_size({'width': 1366, 'height': 820})
    pg.goto(B + '/riepilogo-live?struttura=1&schermo=1')
    pg.wait_for_selector('#riepilogo-live .linea-live')
    ok('riepilogo live: il modo schermo senza menu, con la linea del tempo', menu_anche_nascosto().count() == 0 and
       pg.locator('.linea-live .riga-live').count() == len(dati['stanze']) + 1)

    # 1.12.2: il riepilogo del periodo
    pg.goto(B + '/ambulatori/riepilogo?struttura=1&periodo=settimana')
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: la frase e i cinque gruppi che sommano al totale',
       (lambda c: len(c) == 6 and sum(int(x) for x in c[1:]) == int(c[0]))(pg.locator('.conti-oggi-live li b').all_inner_texts()),
       pg.locator('.conti-oggi-live li b').all_inner_texts())
    ok('riepilogo del periodo: «Questa settimana» scelto, sette giorni nella tabella',
       pg.locator('.periodi-pronti .bottone.attivo').inner_text() == 'Questa settimana' and
       pg.locator('.giorni-periodo tbody tr').count() == 7, pg.locator('.giorni-periodo tbody tr').count())
    pg.locator('.periodi-pronti a', has_text='Oggi').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: «Oggi» un giorno solo, senza la tabella dei giorni',
       pg.locator('.giorni-periodo').count() == 0 and 'periodo=oggi' in pg.url, pg.url)
    pg.locator('a.passo[data-tasto="precedente"]').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: la freccia va al giorno prima', ('da=%s' % (OGGI - timedelta(days=1)).isoformat()) in pg.url, pg.url)
    with pg.expect_download() as scarico:
        pg.click('[data-guida="periodo-excel"]')
    ok('riepilogo del periodo: l\'Excel si scarica con il suo nome',
       scarico.value.suggested_filename == 'riepilogo-ambulatori-%s.xlsx' % (OGGI - timedelta(days=1)).isoformat(),
       scarico.value.suggested_filename)
    attivo = gruppo_segnato()
    ok('riepilogo del periodo: il gruppo Ambulatori è attivo', attivo == 'Ambulatori', attivo)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(300)
    ok('riepilogo del periodo: sul telefono la pagina non scorre di lato (scorrono le tabelle)',
       pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), pg.evaluate('document.documentElement.scrollWidth'))
    pg.set_viewport_size({'width': 1366, 'height': 820})
    # 1.12.6: la sala operatoria nel riepilogo del periodo e le statistiche dentro la dashboard
    pg.goto(B + '/ambulatori/riepilogo?struttura=1&periodo=settimana')
    pg.wait_for_selector('.pagina-periodo .frase-live')
    pg.locator('.parti-periodo a', has_text='Sala operatoria').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('riepilogo del periodo: la scheda Sala operatoria con sale e chirurghi',
       'parte=sala' in pg.url and 'Le sale' in pg.inner_text('.pagina-periodo') and 'I chirurghi' in pg.inner_text('.pagina-periodo'),
       pg.url)
    with pg.expect_download() as scarico:
        pg.click('[data-guida="periodo-excel"]')
    ok('riepilogo del periodo: l\'Excel della sala si scarica con il suo nome',
       scarico.value.suggested_filename.startswith('riepilogo-sala-operatoria-'), scarico.value.suggested_filename)
    # gemello di «apre il riepilogo senza menu, nel modo schermo» (piu' sotto): nella dashboard normale lo stesso pulsante
    # apre la stessa pagina (/riepilogo-live/statistiche senza schermo=1), e li' il menu c'è
    pg.goto(B + '/riepilogo-live?struttura=1')
    pg.wait_for_selector('#riepilogo-live .frase-live')
    pg.click('[data-guida="live-statistiche"]')
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('dashboard normale (gemello): «Riepilogo del periodo» apre il riepilogo con il menu',
       '/riepilogo-live/statistiche' in pg.url and 'schermo=1' not in pg.url and menu(pg).count() == 1,
       (pg.url, menu(pg).count()))
    pg.goto(B + '/riepilogo-live?struttura=1&schermo=1')
    pg.wait_for_selector('#riepilogo-live .frase-live')
    fuori = [h for h in pg.eval_on_selector_all('a[href], form[action]', 'els => els.map(e => e.getAttribute("href") || e.getAttribute("action"))')
             if not h.startswith(('/riepilogo-live', '/static/', '/logo/'))]
    ok('dashboard nel modo schermo: nessun collegamento fuori dalla dashboard', not fuori, fuori[:5])
    ok('dashboard: il pulsante si chiama «Riepilogo del periodo», non «Statistiche»',
       pg.inner_text('[data-guida="live-statistiche"]').strip() == 'Riepilogo del periodo', pg.inner_text('[data-guida="live-statistiche"]'))
    pg.click('[data-guida="live-statistiche"]')
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('dashboard: «Riepilogo del periodo» apre il riepilogo senza menu, nel modo schermo',
       '/riepilogo-live/statistiche' in pg.url and 'schermo=1' in pg.url and menu_anche_nascosto().count() == 0, pg.url)
    pg.locator('.parti-periodo a', has_text='Sala operatoria').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    pg.locator('.periodi-pronti a', has_text='Questo mese').click()
    pg.wait_for_selector('.pagina-periodo .frase-live')
    ok('dashboard: si sceglie la sala e il mese, restando nella dashboard',
       '/riepilogo-live/statistiche' in pg.url and 'parte=sala' in pg.url and 'periodo=mese' in pg.url and 'schermo=1' in pg.url, pg.url)
    fuori = [h for h in pg.eval_on_selector_all('a[href]', 'els => els.map(e => e.getAttribute("href"))')
             if not h.startswith('/riepilogo-live')]
    ok('dashboard: nel riepilogo del periodo nessun collegamento fuori dalla dashboard e niente Excel', not fuori, fuori[:5])
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.wait_for_timeout(300)
    ok('dashboard: il riepilogo del periodo sul telefono non scorre di lato',
       pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), pg.evaluate('document.documentElement.scrollWidth'))
    pg.set_viewport_size({'width': 1366, 'height': 820})
    pg.click('[data-guida="statistiche-torna"]')
    pg.wait_for_selector('#riepilogo-live .frase-live')
    ok('dashboard: «Torna al riepilogo live» resta nel modo schermo', '/riepilogo-live' in pg.url and 'schermo=1' in pg.url, pg.url)
    # tappa 1 della base: la dashboard rimasta aperta su un altro PC. Con l'orologio della pagina mandato avanti, il
    # rinnovo di ogni minuto ricarica tutta la pagina solo se cambia data-giorno, che dice giorno e versione: così dopo
    # la mezzanotte e dopo un aggiornamento la pagina passa da sola al giorno nuovo e alla versione nuova. E ogni
    # richiesta della pagina resta dentro quello che il portiere della rete lascia passare.
    sch = ctx.new_page()
    domande_sch = prepara_domande(sch)
    sch.on('pageerror', lambda e: err.append(str(e)))
    richieste = []
    sch.on('request', lambda r: richieste.append((r.resource_type, r.url)))
    sch.clock.install()
    sch.goto(B + '/riepilogo-live?struttura=1&schermo=1')
    sch.wait_for_selector('#riepilogo-live .frase-live')
    giorno = sch.get_attribute('#riepilogo-live', 'data-giorno') or ''
    ok('dashboard: data-giorno dice il giorno e la versione del programma',
       re.fullmatch(r'\d{4}-\d\d-\d\d \d+(\.\d+)+', giorno) is not None, giorno)
    giorno_solo, _, versione = giorno.partition(' ')
    cambia = {'come': None, 'cambiate': 0}

    def rinnovo(route):
        # solo il rinnovo di ogni minuto (fetch) si cambia; la pagina ricaricata arriva com'è
        if route.request.resource_type != 'fetch' or cambia['come'] is None:
            route.continue_()
            return
        r = route.fetch()
        corpo = cambia['come'](r.text())
        cambia['cambiate'] += 1
        route.fulfill(response=r, body=corpo)
    sch.route('**/riepilogo-live?*', rinnovo)

    def segna():
        # un segno nella finestra (sparisce se la pagina si ricarica) e uno dentro il riquadro (sparisce al rinnovo)
        sch.evaluate('window.__ancora_la_stessa = 1; document.getElementById("riepilogo-live")'
                     '.insertAdjacentHTML("beforeend", "<i id=\\"segno-dentro\\"></i>")')

    def un_minuto_senza_ricaricare():
        segna()
        with sch.expect_response(lambda r: r.request.resource_type == 'fetch' and '/riepilogo-live' in r.url):
            sch.clock.run_for(61000)
        sch.wait_for_timeout(800)
        return sch.evaluate('[window.__ancora_la_stessa === 1, !document.getElementById("segno-dentro")]')

    def un_minuto_ricaricando(come):
        segna()
        cambia['come'] = come
        try:
            with sch.expect_navigation(timeout=15000):
                sch.clock.run_for(61000)
        except Exception:
            return False
        finally:
            cambia['come'] = None
        sch.wait_for_selector('#riepilogo-live .frase-live')
        return sch.evaluate('window.__ancora_la_stessa === undefined')

    stessa, rinnovata = un_minuto_senza_ricaricare()
    ok('dashboard (gemello): con giorno e versione uguali il rinnovo cambia il contenuto senza ricaricare la pagina',
       stessa and rinnovata, (stessa, rinnovata))
    # un programma di un'altra versione: lo stesso numero di versione cambiato dovunque il programma lo scriva
    ok('dashboard: dopo un aggiornamento (il programma ha un\'altra versione) il rinnovo ricarica tutta la pagina',
       un_minuto_ricaricando(lambda c: c.replace(versione, '99.0.1')), cambia)
    ok('dashboard: dopo la mezzanotte (giorno diverso) il rinnovo ricarica tutta la pagina',
       un_minuto_ricaricando(lambda c: c.replace('data-giorno="%s' % giorno_solo, 'data-giorno="2000-01-01', 1)), cambia)
    ok('dashboard: il rinnovo dopo la ricarica è tornato quello di prima (niente ricariche di seguito)',
       un_minuto_senza_ricaricare()[0], cambia)
    sch.clock.run_for(5 * 60000)
    sch.wait_for_timeout(1500)
    fuori = sorted({u for _, u in richieste
                    if not re.sub(r'^https?://[^/]+', '', u).startswith(('/riepilogo-live', '/static/', '/logo/'))})
    rinnovi = sum(1 for tipo, u in richieste if tipo == 'fetch' and '/riepilogo-live?' in u)
    ok('dashboard nel modo schermo: con l\'orologio avanti di dieci minuti ogni richiesta resta in /riepilogo-live, /static/, /logo/',
       not fuori, fuori[:5])
    ok('dashboard (gemello): la registrazione vede davvero le richieste (rinnovi, file di /static/, la pagina)',
       rinnovi >= 8 and any('/static/' in u for _, u in richieste) and cambia['cambiate'] == 2,
       (rinnovi, cambia, len(richieste)))
    sch.close()
    ok('nessun errore JavaScript', not err, err[:3])
    ok('nessuna domanda del browser inattesa', not domande.inattese and not domande_sch.inattese, domande.inattese + domande_sch.inattese)
    br.close()

print('%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
