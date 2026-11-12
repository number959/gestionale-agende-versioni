# -*- coding: utf-8 -*-
"""Il gestionale con i DATI DI PROVA intorno a oggi, su un server locale: per
le prove nel browser, le immagini e i video della guida, le dimostrazioni.
Mai con i dati veri: i nomi sono inventati (e scelti per non coincidere con
quelli dei file della clinica), le email sono @example.it.

    python strumenti/demo.py                      # dati in una cartella temporanea, porta 5001
    python strumenti/demo.py --dati C:\\prova --porta 5077

Ogni avvio ricomincia da capo (il database della prova si cancella e si rifa').
Dentro: medici, turni, appuntamenti della settimana in ogni stato, sala
operatoria e posti letto, cassa, lista d'attesa, cose da fare, documenti,
email e WhatsApp gia' partiti (finti, il thread degli invii non parte), le
schede per la guida del codice fiscale (valido, sbagliato, che non torna,
doppio, da calcolare) e un aggiornamento finto gia' scaricato, cosi' la
pagina Aggiornamenti mostra «Aggiorna adesso».

Le prove nel browser (prove_*_browser.py) cambiano i dati: per immagini e
video meglio un server appena avviato."""
import argparse
import json
import os
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
os.chdir(SRC)
parametri = argparse.ArgumentParser(description='Gestionale con i dati di prova.')
parametri.add_argument('--dati', default=os.path.join(tempfile.gettempdir(), 'gestionale-demo'),
                       help='cartella del database di prova (si svuota a ogni avvio)')
parametri.add_argument('--porta', type=int, default=5001)
ARG = parametri.parse_args()
os.makedirs(ARG.dati, exist_ok=True)
from datetime import date, datetime, time, timedelta  # noqa: E402
import seed  # noqa: E402
import app as A  # noqa: E402
from modelli import *  # noqa: E402,F401,F403
p = os.path.join(ARG.dati, 'demo.db')
for vecchio in (p, p + '-wal', p + '-shm'):
    if os.path.exists(vecchio):
        os.remove(vecchio)
S = seed.popola('sqlite:///' + p)
s = S()
oggi = date.today()
mar = oggi - timedelta(days=(oggi.weekday() - 1) % 7)          # martedi di questa settimana
gio = mar + timedelta(days=2)
ven = mar + timedelta(days=3)
med = {o.cognome: o for o in s.scalars(select(Operatore))}
amb = {r.nome: r for r in s.scalars(select(Risorsa))}
pr = {x.nome: x for x in s.scalars(select(Prestazione))}
# ---- 1.10: la seduta di endoscopia del martedi ha fasce sue, da 15 minuti: una colonscopia
# (45') ne occupa tre, una EGDS (30') due; il resto della struttura resta a 30'
if hasattr(Turno, 'passo'):
    for t_ in s.scalars(select(Turno).where(Turno.risorsa_id == amb['Sala endoscopia'].id,
                                            Turno.giorno_settimana == 1)):
        t_.passo = 15
nomi = [('Esposito', 'Anna', 'anna.esposito@example.it', '3331234500'), ('Russo', 'Giovanni', '', '3339876543'),
        ('Coppola', 'Maria', 'm.coppola@example.it', '3471112233'), ('Barbato', 'Luca', '', '3285556677'),
        ('Sorrentino', 'Teresa', 'teresa.s@example.it', '081 555 1234'), ('De Luca', 'Ciro', '', '3401234567'),
        ('Improta', 'Rosa', 'rosa.improta@example.it', '3669988776'), ('Palumbo', 'Salvatore', '', '3923344556'),
        ('Cutolo', 'Carmela', '', '3317788990'), ('Vitiello', 'Gennaro', 'g.vitiello@example.it', '3384455667'),
        ('Aiello', 'Francesca', '', '3207766554'), ('Ferrara', 'Antonio', 'antonio.ferrara@example.it', '3496655443')]
paz = []
for c, n, e, t in nomi:
    x = s.scalars(select(Paziente).where(Paziente.cognome == c)).first()
    x.nome, x.email, x.telefono = n, e, t
    paz.append(x)
x = paz[0]; x.data_nascita = date(1978, 3, 12); x.codice_fiscale = 'SPSNNA78C52F839X'
s.commit()
def app(g, stanza, medico, prest, h, m, pz, stato='PRENOTATO', tipo='', conv='', imp=None, extra=None, note=''):
    i = datetime.combine(g, time(h, m))
    a = Appuntamento(risorsa=amb[stanza], operatore=med[medico], prestazione=pr[prest], paziente=pz,
                     inizio=i, fine=i + timedelta(minutes=pr[prest].durata_min), stato=stato, tipo=tipo,
                     convenzione=conv, importo_cent=imp, extra=json.dumps(extra or {}, ensure_ascii=False) if extra else '',
                     note=note, arrivato_alle=(datetime.combine(g, time(h, m)) - timedelta(minutes=7)) if stato == 'ARRIVATO' else None)
    s.add(a)
for g in (mar, gio):
    app(g, 'Ambulatorio 1', 'Lippiello', 'Visita ginecologica', 8, 30, paz[0], 'ARRIVATO' if g == mar else 'CONFERMATO', 'CONTROLLO', 'Privato', 8000, note='riporta ecografia')
    app(g, 'Ambulatorio 1', 'Lippiello', 'Visita ginecologica', 9, 0, paz[1], 'CONFERMATO', 'PRIMA_VISITA', 'Unisalute', 10000)
    app(g, 'Ambulatorio 1', 'Lippiello', 'Visita ginecologica', 10, 0, paz[2], 'PRENOTATO', 'CONTROLLO', 'Privato', 8000)
    app(g, 'Ambulatorio 1', 'Lippiello', 'Visita ginecologica', 11, 30, paz[3], 'DISDETTO', 'CONTROLLO', 'Privato')
    app(g, 'Ambulatorio 2', 'Lippiello', 'Ecografia', 8, 30, paz[4], 'CONFERMATO', 'PRESTAZIONE', 'Generali', 6000)
    app(g, 'Ambulatorio 2', 'Lippiello', 'Ecografia', 9, 30, paz[5], 'PRENOTATO', 'PRESTAZIONE', 'Privato', 6000)
app(mar, 'Sala endoscopia', 'Galasso', 'Colonscopia', 8, 0, paz[6], 'ARRIVATO', 'PRESTAZIONE', 'Privato', 25077, {'Sedazione': 'Sì', 'Anestesista': 'Romano', 'Preparazione consegnata': 'Sì'})
app(mar, 'Sala endoscopia', 'Galasso', 'EGDS', 9, 0, paz[7], 'CONFERMATO', 'PRESTAZIONE', 'Privato', 18000, {'Sedazione': 'No', 'Preparazione consegnata': 'Sì'})
app(mar, 'Sala endoscopia', 'Galasso', 'EGDS', 10, 0, paz[8], 'NON_PRESENTATO', 'PRESTAZIONE', 'Privato')
app(mar, 'Ambulatorio 3', 'Esposito', 'Visita cardiologica', 15, 30, paz[9], 'PRENOTATO', 'PRIMA_VISITA', 'Allianz', 12000)
app(mar, 'Ambulatorio 4', 'Russo', 'Visita diabetologica', 9, 30, paz[10], 'CONFERMATO', 'CONTROLLO', 'Privato', 9000)
app(gio, 'Ambulatorio 2', 'Lippiello', 'Ecografia', 11, 0, paz[11], 'PRENOTATO', 'PRESTAZIONE', 'Privato', 6000)
# Galasso senza giorno fisso: il venerdi di questa settimana, turno di un giorno
s.add(Turno(operatore=med['Galasso'], risorsa=amb['Sala endoscopia'], giorno_settimana=ven.weekday(),
            ora_inizio=time(8, 0), ora_fine=time(13, 30), valido_da=ven, valido_a=ven))
app(ven, 'Sala endoscopia', 'Galasso', 'Colonscopia', 8, 30, paz[11], 'PRENOTATO', 'PRESTAZIONE', 'Privato', 25077, {'Sedazione': 'Sì', 'Anestesista': 'Romano'})
# Esposito in ferie la settimana prossima
s.add(Assenza(operatore=med['Esposito'], dal=mar + timedelta(days=7), al=mar + timedelta(days=11), motivo='Ferie'))
s.add(Chiusura(struttura_id=1, dal=date(oggi.year, 12, 24), al=date(oggi.year, 12, 24), motivo='Vigilia di Natale'))

# ---- 1.4
pr['Visita ginecologica'].tariffa_cent = 8000; pr['Ecografia'].tariffa_cent = 6000
pr['Colonscopia'].tariffa_cent = 25000; pr['EGDS'].tariffa_cent = 18000
s.add(Tariffa(prestazione_id=pr['Visita ginecologica'].id, convenzione='Unisalute', importo_cent=10000))
s.flush()
# ---- 1.12.6: un tariffario attivo (prezzi inventati) e uno spento, per il controllo dei medici (con i nomi che
# i medici hanno alla fine: Esposito diventa Gallo, Marino diventa Monti, vedi RINOMINA)
_t = Tariffario(nome='Dott. Gallo', note='Le tariffe valgono per la singola prestazione o per il pacchetto intero.',
                origine='tariffario-prova.xlsx')
_t.medici.append(TariffarioMedico(operatore_id=med['Esposito'].id))
for _i, (_sez, _nome, _mod, _cent, _det, _p) in enumerate([
        ('Visite', 'Visita cardiologica', '', 11000, '', pr['Visita cardiologica'].id),
        ('Visite', 'Visita di controllo', '', 7000, '', pr['Controllo'].id),
        ('Esami', 'Elettrocardiogramma', '', 4000, '', None),
        ('Esami', 'Holter cardiaco', 'Singola', 9000, '24 ore', None),
        ('Esami', 'Holter cardiaco', 'Pacchetto', 24000, '3 registrazioni in un anno', None)]):
    _t.voci.append(VoceTariffario(sezione=_sez, nome=_nome, modalita=_mod, importo_cent=_cent, dettagli=_det,
                                  prestazione_id=_p, ordine=_i))
s.add(_t)
_t2 = Tariffario(nome='Dott.ssa Monti', attivo=False)
_t2.medici.append(TariffarioMedico(operatore_id=med['Marino'].id))
_t2.voci.append(VoceTariffario(nome='Visita dermatologica', importo_cent=9000, prestazione_id=pr['Visita dermatologica'].id))
s.add(_t2)
s.flush()
for a_ in s.scalars(select(Appuntamento).where(Appuntamento.stato == 'ARRIVATO')):
    a_.pagato_cent, a_.pagamento, a_.pagato_il = a_.importo_cent, 'POS' if a_.importo_cent and a_.importo_cent < 20000 else 'CONTANTI', a_.inizio + timedelta(minutes=40)
paz[0].provenienza = 'MEDICO'; paz[0].inviato_da = 'Dott. Ferraro'
paz[2].provenienza = 'INTERNET'; paz[6].provenienza = 'PASSAPAROLA'
s.add(Attesa(paziente=paz[9], operatore=med['Lippiello'], prestazione=pr['Visita ginecologica'], note='anche con poco preavviso', creato_il=datetime.now() - timedelta(days=6)))
s.add(Attesa(paziente=paz[10], fascia='MATTINA', creato_il=datetime.now() - timedelta(days=2)))
s.add(Attivita(testo='Richiamare per il referto istologico', per_il=oggi, paziente=paz[2]))
s.add(Attivita(testo='Sollecitare l\'impegnativa', per_il=oggi - timedelta(days=1), paziente=paz[5]))
s.add(NotaGiorno(struttura_id=1, data=gio, testo='Lippiello arriva alle 10:30. Ambulatorio 3 chiuso per manutenzione.'))
s.add(ModuloStampa(nome='Istruzioni per la colonscopia (esempio)', prestazione=pr['Colonscopia'], firma=False,
                   testo=open(os.path.join(SRC, 'documenti.py'), encoding='utf-8').read().split('ESEMPIO = """')[1].split('"""')[0]))
s.add(Documento(paziente=paz[0], nome='impegnativa.pdf', descrizione='Impegnativa del medico curante', tipo='application/pdf',
                dati=b'%PDF-1.4\n%%EOF\n', dimensione=16))
st = s.get(Struttura, 1); st.email = 'accettazione@example.it'; st.patrono = '19/09'
# ---- 1.4.3: sala operatoria
st.posti_letto = 4
amb['Sala A'].struttura_id = amb['Sala B'].struttura_id = 1
amb['Sala A'].ordine, amb['Sala B'].ordine = 20, 21
ieri, domani = oggi - timedelta(days=1), oggi + timedelta(days=1)
amato = Operatore(cognome='Amato', nome='Paolo', specialita='chirurgia plastica', colore='#C2185B', email='p.amato@example.it', giorni_sala='0100100')
fiore = Operatore(cognome='Fiore', nome='Marta', specialita='chirurgia generale', colore='#0F7C8C', giorni_sala='1000100')
conte = Operatore(cognome='Conte', nome='Luigi', specialita='ortopedia', colore='#8A6D1F', giorni_sala=''.join('1' if i == oggi.weekday() else '0' for i in range(7)))
s.add_all([amato, fiore, conte])
rino = Prestazione(nome='Rinoplastica', durata_min=120, campi_extra='Anestesista', tariffa_cent=450000)
ernia = Prestazione(nome='Ernia inguinale', durata_min=90, campi_extra='Anestesista')
masto = Prestazione(nome='Mastoplastica additiva', durata_min=120, campi_extra='Anestesista, Protesi')
s.add_all([rino, ernia, masto]); s.flush()
med.update({'Amato': amato, 'Fiore': fiore, 'Conte': conte}); pr.update({'Rinoplastica': rino, 'Ernia inguinale': ernia, 'Mastoplastica additiva': masto})
extra_nomi = [('Capasso', 'Lucia', '3351112201'), ('Marra', 'Elena', '3351112202'), ('Longobardi', 'Pietro', '3351112203'),
              ('Scotti', 'Giulia', '3351112204'), ('Nappi', 'Sara', '3351112205'), ('Guida', 'Marco', '3351112206'),
              ('Bove', 'Chiara', '3351112207'), ('Riccio', 'Alba', '3351112208')]
pz2 = []
for c, n, t in extra_nomi:
    x = Paziente(cognome=c, nome=n, telefono=t, data_nascita=date(1985, 5, 20)); s.add(x); pz2.append(x)
s.flush()
def intervento(g, sala, medico, prest, h, m, pz, degenza='', notti=None, anest='Romano', spunte=(), stato='PRENOTATO', altro=None):
    i = datetime.combine(g, time(h, m)); e = {'Anestesista': anest}; e.update(altro or {})
    a = Appuntamento(risorsa=amb[sala], operatore=med[medico], prestazione=pr[prest], paziente=pz, inizio=i,
                     fine=i + timedelta(minutes=pr[prest].durata_min), stato=stato, degenza=degenza, notti=notti,
                     extra=json.dumps(e, ensure_ascii=False), convenzione='Privato',
                     checklist=json.dumps({v: (g - timedelta(days=2)).isoformat() + ' 10:15' for v in spunte}, ensure_ascii=False) if spunte else '')
    s.add(a)
TUTTE = ['Esami pre-operatori', 'Consenso firmato', 'Anestesista confermato', 'Preparazione consegnata', 'Acconto versato']
intervento(ieri, 'Sala A', 'Amato', 'Rinoplastica', 8, 0, pz2[0], 'RICOVERO', 3, spunte=TUTTE, stato='ARRIVATO')
intervento(oggi, 'Sala A', 'Amato', 'Mastoplastica additiva', 8, 30, pz2[1], 'NOTTE', spunte=TUTTE, altro={'Protesi': '300 cc'})
intervento(oggi, 'Sala B', 'Fiore', 'Ernia inguinale', 9, 0, pz2[2], 'DH', anest='Greco', spunte=TUTTE[:4])
intervento(domani, 'Sala A', 'Amato', 'Rinoplastica', 8, 0, pz2[3], 'NOTTE', spunte=TUTTE[:3])
intervento(domani, 'Sala A', 'Amato', 'Rinoplastica', 11, 0, pz2[4], 'DH', spunte=TUTTE)
intervento(domani, 'Sala B', 'Fiore', 'Ernia inguinale', 9, 0, pz2[5], 'RICOVERO', 2, anest='Greco', spunte=TUTTE[:1])
for gs in range(6):
    s.add(Turno(operatore=amato, risorsa=amb['Sala A'], giorno_settimana=gs, ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=oggi - timedelta(days=60)))
    s.add(Turno(operatore=fiore, risorsa=amb['Sala B'], giorno_settimana=gs, ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=oggi - timedelta(days=60)))
    s.add(Turno(operatore=med['Lippiello'], risorsa=amb['Ambulatorio 1'], giorno_settimana=gs, ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=oggi - timedelta(days=60)))
s.add_all([Appunto(testo='Stanza da decidere: la dottoressa conferma giovedì', giorno=domani, ora=time(15, 0), durata_min=30, struttura_id=1,
                   operatore_id=med['Lippiello'].id, prestazione_id=pr['Visita ginecologica'].id, cognome='Ferraro', nome='Ilaria', telefono='3351112299'),
           Appunto(testo='Richiama per scegliere il giorno', struttura_id=1, operatore_id=amato.id, prestazione_id=rino.id,
                   cognome='Santoro', nome='Paola', telefono='3351112298'),
           Appunto(testo='Sala A occupata alla stessa ora: spostare di un’ora?', giorno=domani, ora=time(8, 0), durata_min=120, struttura_id=1,
                   risorsa_id=amb['Sala A'].id, operatore_id=amato.id, prestazione_id=rino.id, cognome='Esposito', nome='Chiara', telefono='3351112297')])
prossima = oggi + timedelta(days=6)
for k in range(5):
    intervento(prossima, 'Sala A' if k % 2 else 'Sala B', 'Amato' if k % 2 else 'Fiore', 'Rinoplastica' if k % 2 else 'Ernia inguinale', 8 + 2 * (k // 2), 0, pz2[(k + 6) % 8], 'NOTTE')

# nomi di prova che non coincidono con nessun nome dei file veri (le immagini della guida li mostrano)
RINOMINA = {'Esposito': 'Sepe', 'Russo': 'Rinaldi', 'Coppola': 'Cuomo', 'De Luca': 'Serino', 'Marino': 'Monti', 'Amato': 'Valente'}
NOMI = {'Rinaldi': 'Giorgio'}
for o in s.scalars(select(Operatore)):
    if o.cognome in RINOMINA:
        o.cognome = {'Esposito': 'Gallo', 'Russo': 'Guarino'}.get(o.cognome, RINOMINA[o.cognome])
        if o.email: o.email = o.email.split('@')[0].split('.')[0] + '.' + o.cognome.lower() + '@example.it'
for x in s.scalars(select(Paziente)):
    if x.cognome in RINOMINA:
        x.cognome = RINOMINA[x.cognome]
        x.nome = NOMI.get(x.cognome, x.nome)
        if x.email: x.email = (x.nome or 'paziente').lower() + '.' + x.cognome.lower().replace(' ', '') + '@example.it'
for x in s.scalars(select(Appunto)):
    if x.cognome == 'Esposito': x.cognome = 'Sartori'
s.commit()
# ---- 1.5: email e WhatsApp (dati finti; il thread degli invii qui non parte)
try:
    import invii
except ImportError:
    invii = None
if invii is not None:
    pz = s.scalars(select(Paziente).where(Paziente.cognome == 'Sepe')).first()
    if pz is not None:
        pz.indirizzo = 'Via Manzoni 12, 80123 Napoli'
    # la casella del sito (1.9.1): quella consigliata, senza Gmail
    for k, v in (('email_utente', 'accettazione@example.it'), ('email_password', invii.proteggi('Password-di-prova')),
                 ('email_tipo', 'dominio'), ('email_server', 'mail.example.it'), ('email_porta', '465'),
                 ('email_sicurezza', 'ssl'), ('promemoria_attivo', '1'), ('promemoria_ora', '10:00')):
        scrivi_impostazione(s, k, v)
    galasso = s.scalars(select(Operatore).where(Operatore.cognome == 'Galasso')).first()
    regola = invii.crea_regola_pronta(s, galasso)
    # email per medico (1.5): una per tutti i medici e una della Dr.ssa Lippiello, con PDF finti
    PDF = b'%PDF-1.4\n% esempio\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n'
    if hasattr(invii, 'duplica_regola'):
        colon = s.scalars(select(Prestazione).where(Prestazione.nome == 'Colonscopia')).first()
        eco = s.scalars(select(Prestazione).where(Prestazione.nome == 'Ecografia')).first()
        lip = s.scalars(select(Operatore).where(Operatore.cognome == 'Lippiello')).first()
        r1 = RegolaEmail(nome='Preparazione colonscopia', operatore_id=None, prestazioni=str(colon.id),
                         oggetto='Preparazione alla colonscopia del {giorno}',
                         testo='Gentile {paziente},\n\nin allegato le istruzioni per la preparazione alla colonscopia di {giorno} alle {ora}.\n\nCordiali saluti.')
        r1.allegati.append(AllegatoRegola(nome='Preparazione colonscopia.pdf', tipo='application/pdf', dimensione=len(PDF), dati=PDF))
        r2 = RegolaEmail(nome='Ecografia: come prepararsi', operatore_id=lip.id, prestazioni=str(eco.id),
                         oggetto='Ecografia del {giorno}: come prepararsi',
                         testo='Gentile {paziente},\n\nper l\'ecografia di {giorno} alle {ora} con {medico} in allegato le indicazioni.\n\nCordiali saluti.')
        r2.allegati.append(AllegatoRegola(nome='Indicazioni ecografia.pdf', tipo='application/pdf', dimensione=len(PDF), dati=PDF))
        s.add_all([r1, r2]); s.flush()
    adesso = datetime.now()
    for a_ in s.scalars(select(Appuntamento).where(Appuntamento.operatore_id == galasso.id).order_by(Appuntamento.inizio)):
        if a_.paziente is None:
            continue
        dest = a_.paziente.email or 'paziente@example.it'
        s.add(Invio(canale='EMAIL', motivo='PREPARAZIONE', destinatario=dest, appuntamento_id=a_.id,
                    paziente_id=a_.paziente_id, regola_id=regola.id, per_inizio=a_.inizio, stato='INVIATO',
                    oggetto=invii.PRONTA_OGGETTO, testo=invii.PRONTA_TESTO, tentativi=1,
                    creato_il=a_.inizio - timedelta(days=6), inviato_il=a_.inizio - timedelta(days=6, minutes=-1)))
    prossimi = s.scalars(select(Appuntamento).where(Appuntamento.inizio >= datetime.combine(oggi + timedelta(days=1), time(0, 0)),
                                                    Appuntamento.inizio < datetime.combine(oggi + timedelta(days=2), time(0, 0)),
                                                    Appuntamento.paziente_id != None).order_by(Appuntamento.inizio)).all()
    for k, a_ in enumerate(prossimi[:4]):
        if k == 2:
            s.add(Invio(canale='EMAIL', motivo='PROMEMORIA', destinatario='indirizzo.sbagliato@example.it', appuntamento_id=a_.id,
                        paziente_id=a_.paziente_id, per_inizio=a_.inizio, stato='ERRORE', tentativi=1,
                        errore='indirizzo del destinatario rifiutato: indirizzo.sbagliato@example.it',
                        creato_il=adesso.replace(hour=10, minute=0, second=0, microsecond=0)))
        else:
            s.add(Invio(canale='WHATSAPP', motivo='PROMEMORIA', destinatario='39' + (a_.paziente.telefono or '3330000000').replace(' ', ''),
                        appuntamento_id=a_.id, paziente_id=a_.paziente_id, per_inizio=a_.inizio, stato='INVIATO', tentativi=1,
                        oggetto='Modello promemoria_appuntamento · id wamid.ESEMPIO%d' % k,
                        creato_il=adesso.replace(hour=10, minute=0, second=0, microsecond=0),
                        inviato_il=adesso.replace(hour=10, minute=0, second=4, microsecond=0)))
    s.commit()
s.close()
A.Sessione = S; A._registro = None
import viste; viste._sessionmaker = lambda: S
# ---- 1.7: codici fiscali per la guida e per le prove (nomi inventati)
try:
    import codice_fiscale as CFm
except ImportError:
    CFm = None
if CFm is not None:
    s = S()
    def nuovo(c, n, **k):
        x = Paziente(cognome=c, nome=n, **k); s.add(x); return x
    pozzuoli = CFm.risolvi_luogo('Pozzuoli')[0]
    nuovo('Fintini', 'Prova', telefono='3330000101', sesso='M', data_nascita=date(1980, 1, 1), luogo_nascita='F839',
          codice_fiscale=CFm.calcola('Fintini', 'Prova', date(1980, 1, 1), 'M', 'F839'))
    nuovo('Esempietti', 'Maria Rosa', telefono='3330000102', sesso='F', data_nascita=date(1975, 3, 12),
          luogo_nascita=CFm.risolvi_luogo('San Giorgio a Cremano')[0])
    nuovo('Provolo', 'Hugo', telefono='3330000103', sesso='M', data_nascita=date(1969, 7, 4), luogo_nascita='F839',
          codice_fiscale=CFm.calcola('Provolo', 'Ugo', date(1969, 7, 4), 'M', 'F839'))
    lia = CFm.calcola('Testabianca', 'Lia', date(1990, 11, 23), 'F', pozzuoli)
    for tel in ('3330000104', '3330000105'):
        nuovo('Testabianca', 'Lia', telefono=tel, sesso='F', data_nascita=date(1990, 11, 23), luogo_nascita=pozzuoli,
              codice_fiscale=lia)
    s.commit(); s.close()
# ---- 1.8: il personale e i turni, dal mese scorso al mese prossimo (nomi inventati)
try:
    import personale as PE
except ImportError:
    PE = None
if PE is not None:
    s = S()
    T = {t.codice: t for t in s.scalars(select(TipoTurno))}
    def persona(c, n, ruolo, qualifica='', ore=36, **k):
        x = Persona(cognome=c, nome=n, ruolo=ruolo, qualifica=qualifica, minuti_settimana=ore * 60 if ore else None,
                    attiva=True, **k)
        s.add(x); return x
    medici = {o.cognome: persona(o.cognome, o.nome or '', 'MEDICO', o.specialita or '', None, operatore_id=o.id)
              for o in s.scalars(select(Operatore).where(Operatore.attivo == True).order_by(Operatore.cognome))}
    inf = [persona('Provanzi', 'Lucia', 'INFERMIERE', 'Coordinatrice'), persona('Campionelli', 'Marco', 'INFERMIERE'),
           persona('Esemplari', 'Anna', 'INFERMIERE'), persona('Fintoni', 'Paolo', 'INFERMIERE'),
           persona('Saggini', 'Teresa', 'INFERMIERE'), persona('Bozzolini', 'Rita', 'INFERMIERE'),
           persona('Pagellini', 'Ivo', 'INFERMIERE'), persona('Taccuini', 'Nora', 'INFERMIERE', 'Strumentista')]
    oss = [persona('Modellini', 'Carla', 'OSS'), persona('Prototti', 'Gino', 'OSS'), persona('Scheduzzi', 'Elsa', 'OSS'),
           persona('Moduletti', 'Bruno', 'OSS', ore=30)]
    tec = [persona('Righelli', 'Dario', 'TECNICO', 'Tecnico di radiologia'), persona('Matitelli', 'Nadia', 'TECNICO', 'Fisioterapista', 30)]
    amm = [persona('Cartolini', 'Giada', 'AMMINISTRATIVO', 'Accettazione'), persona('Fogliotti', 'Remo', 'AMMINISTRATIVO', 'Accettazione')]
    aus = [persona('Gessetti', 'Ugo', 'AUSILIARIO')]
    s.flush()
    primo = (oggi.replace(day=1) - timedelta(days=1)).replace(day=1)             # il primo del mese scorso
    dal_ = primo - timedelta(days=primo.weekday())                                # dal lunedi di quella settimana
    al_ = (oggi.replace(day=28) + timedelta(days=40)).replace(day=1) - timedelta(days=1)   # fine del mese prossimo
    def schema(persone, sequenza, sfasamento=0):
        PE.applica_schema(s, persone, dal_, al_, PE.leggi_sequenza(sequenza, T), sfasamento)
    schema(inf, 'M M P P N SN R R', 1)            # otto infermieri, otto giorni: ogni giorno due mattine, due pomeriggi, una notte
    schema(oss, 'M P R R', 1)
    schema(tec, 'G G G G G R R')
    schema(amm[:1], 'M M M M M R R'); schema(amm[1:], 'P P P P P R R')
    schema(aus, 'M M M M M M R')
    for cognome in ('Lippiello', 'Valente', 'Fiore'):
        if cognome in medici:
            schema([medici[cognome]], 'G G G G G R R')
    if 'Galasso' in medici:
        schema([medici['Galasso']], 'G - G - G R R')
    if 'Conte' in medici:
        schema([medici['Conte']], '- - - - - RE RE')
    s.flush()
    # le aree: degenza per gli infermieri (sala operatoria per la strumentista), ambulatori, accettazione
    for t in s.scalars(select(TurnoPersonale).where(TurnoPersonale.inizio != None)):
        p_ = t.persona
        if t.categoria != 'LAVORO':
            continue
        t.area = ('Sala operatoria' if p_ is inf[-1] else 'Degenza') if p_.ruolo in ('INFERMIERE', 'OSS') else \
            'Ambulatori' if p_.ruolo in ('TECNICO', 'MEDICO') else 'Accettazione' if p_.ruolo == 'AMMINISTRATIVO' else ''
    lun = oggi - timedelta(days=oggi.weekday())
    for d in range(5):                              # Esemplari in ferie la settimana prossima: lì manca qualcuno
        PE.assegna(s, inf[2], lun + timedelta(days=7 + d), T['F'])
    PE.assegna(s, oss[1], oggi, T['MA']); PE.assegna(s, oss[1], oggi + timedelta(days=1), T['MA'])
    PE.assegna(s, amm[1], lun + timedelta(days=2), T['PE'])
    # un cambio con poco riposo (pomeriggio e poi mattina), un orario diverso e uno scritto a mano
    for d in range(1, 7):
        g_ = lun + timedelta(days=d)
        prima_ = s.scalars(select(TurnoPersonale).where(TurnoPersonale.persona_id == inf[3].id,
                                                        TurnoPersonale.giorno == g_ - timedelta(days=1))).first()
        ora_ = s.scalars(select(TurnoPersonale).where(TurnoPersonale.persona_id == inf[3].id,
                                                      TurnoPersonale.giorno == g_)).first()
        if prima_ is not None and prima_.tipo is T['P'] and ora_ is not None and ora_.tipo is T['P']:
            PE.assegna(s, inf[3], g_, T['M'], area='Degenza', note='cambio con Saggini')
            break
    PE.assegna(s, amm[0], lun + timedelta(days=3), T['M'], time(7, 30), time(13, 30), 'Accettazione')
    PE.assegna(s, aus[0], lun + timedelta(days=4), None, time(8, 0), time(12, 0), note='solo mattina')
    s.add_all([CoperturaMinima(ruolo='INFERMIERE', tipo_id=T['M'].id, minimo=2),
               CoperturaMinima(ruolo='INFERMIERE', tipo_id=T['P'].id, minimo=2),
               CoperturaMinima(ruolo='INFERMIERE', tipo_id=T['N'].id, minimo=1),
               CoperturaMinima(ruolo='OSS', tipo_id=T['M'].id, minimo=1, giorni='1111110'),
               CoperturaMinima(ruolo='AMMINISTRATIVO', tipo_id=T['M'].id, minimo=1, giorni='1111100')])
    s.commit(); s.close()
# ---- 1.9: dove si fa, con un database delle prestazioni inventato (strutture e recapiti finti)
try:
    import dovesifa as DS
except ImportError:
    DS = None
if DS is not None:
    from strumenti.catalogo_prova import libro as libro_prova
    s = S()
    DS.importa_catalogo(s, DS.leggi_database(libro_prova(), 'Database delle prestazioni (prova).xlsx'))
    s.flush()
    voce_ = {v.nome: v for v in s.scalars(select(VoceCatalogo))}
    gr_ = {g.nome: g for g in s.scalars(select(StrutturaGruppo))}
    pz_ = {x.cognome: x for x in s.scalars(select(Paziente).where(Paziente.cognome.in_(['Cuomo', 'Palumbo', 'Sorrentino'])))}
    adesso_ = datetime.now().replace(second=0, microsecond=0)
    for ore_fa, cognome_, vn, gn, canale_ in [(3, 'Sorrentino', 'Ecografia renale', 'Centro Sud', 'stampa'),
                                              (26, 'Cuomo', 'Mammografia', 'Centro Nord', 'whatsapp'),
                                              (50, 'Palumbo', 'RM ginocchio', 'Diagnostica Lago', 'telefono')]:
        v_, g_, x_ = voce_[vn], gr_[gn], pz_[cognome_]
        s.add(Indirizzato(quando=adesso_ - timedelta(hours=ore_fa), struttura_id=1, gruppo_id=g_.id, gruppo_nome=g_.nome,
                          voce_id=v_.id, prestazione=v_.nome, branca=v_.branca, paziente_id=x_.id,
                          paziente=x_.etichetta, canale=canale_))
    s.commit(); s.close()
# ---- 1.6: un aggiornamento finto gia' scaricato, per la pagina Aggiornamenti (guida e video)
try:
    import aggiornamenti
except ImportError:
    aggiornamenti = None
if aggiornamenti is not None:
    import hashlib, random
    cart = os.path.join(ARG.dati, 'aggiornamenti-demo'); os.makedirs(cart, exist_ok=True)
    finto = b'MZ' + bytes(random.Random(16).getrandbits(8) for _ in range(1300000))
    open(os.path.join(cart, aggiornamenti.NOME_SETUP), 'wb').write(finto)
    prossima = aggiornamenti.VERSIONE + '.1'
    json.dump({'programma': 'Gestionale Agende', 'variante': aggiornamenti.VARIANTE, 'versione': prossima,
               'file': aggiornamenti.NOME_SETUP, 'byte': len(finto), 'sha256': hashlib.sha256(finto).hexdigest(),
               'pubblicata': date.today().isoformat(),
               'novita': [{'versione': prossima, 'voci': [{'titolo': 'Correzioni', 'testo': 'Piccole correzioni e miglioramenti, '
                                                           'dalle segnalazioni della segreteria.'}]}]},
              open(os.path.join(cart, aggiornamenti.MANIFESTO), 'w', encoding='utf-8'))
    s = S(); scrivi_impostazione(s, aggiornamenti.CHIAVE, cart); s.commit(); s.close()
    aggiornamenti._fabbrica = lambda: S()
    aggiornamenti.controlla(lambda: S())
    print('aggiornamento finto:', aggiornamenti.stato['pronto'], aggiornamenti.stato['errore'], flush=True)
    # nella pagina (e quindi nella guida) l'indirizzo vero: quello predefinito, senza riga nelle impostazioni
    from modelli import Impostazione
    s = S(); r = s.get(Impostazione, aggiornamenti.CHIAVE)
    if r is not None:
        s.delete(r)
    s.commit(); s.close()
from waitress import serve  # noqa: E402
with open(os.path.join(ARG.dati, 'demo.pid'), 'w') as f:
    f.write(str(os.getpid()))
print('Gestionale di prova: http://127.0.0.1:%d  (dati in %s)' % (ARG.porta, ARG.dati), flush=True)
serve(A.app, host='127.0.0.1', port=ARG.porta, threads=4)
