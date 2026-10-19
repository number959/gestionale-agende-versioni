# -*- coding: utf-8 -*-
"""Modello dati del gestionale appuntamenti.

Una sola tabella regge tutto il calendario: Appuntamento.
Le altre descrivono il mondo in cui gli appuntamenti si collocano
(dove, con chi, per fare cosa) e le regole di apertura (Turno).
"""
import os
import sys
from datetime import datetime, date, time, timedelta

import logging
import re

from sqlalchemy import (create_engine, Column, Integer, String, Boolean, Date,
                        Time, DateTime, Text, ForeignKey, UniqueConstraint,
                        LargeBinary, Index, text, select)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, deferred
from sqlalchemy.schema import CreateTable

Base = declarative_base()

def cartella_risorse():
    """Dove stanno templates/ e static/.

    Dentro l'eseguibile PyInstaller scompatta tutto in una cartella
    temporanea il cui percorso sta in sys._MEIPASS: cercarle accanto
    all'eseguibile non funziona.
    """
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


# Dove vive il database sul PC dell'accettazione.
# Fuori dall'eseguibile, altrimenti un aggiornamento porta via i dati.
def percorso_db():
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    cartella = os.path.join(base, 'GestionaleAgende')
    os.makedirs(cartella, exist_ok=True)
    return os.path.join(cartella, 'agende.db')


COLORE_PREDEFINITO = '#154381'
APERTURA_PREDEFINITA = time(8, 0)
CHIUSURA_PREDEFINITA = time(20, 0)      # l'ultima fascia da 30' parte alle 19:30
PASSI_AMMESSI = (10, 15, 20, 30, 60)
GIORNI_PREDEFINITI = '1111110'          # da lunedi a sabato

# stato dell'appuntamento: solo quelli "attivi" occupano la stanza
STATI = [('PRENOTATO', 'Prenotato'), ('CONFERMATO', 'Confermato'),
         ('ARRIVATO', 'Arrivato'), ('NON_PRESENTATO', 'Non presentato'),
         ('DISDETTO', 'Disdetto')]
ETICHETTA_STATO = dict(STATI)
STATI_ATTIVI = ('PRENOTATO', 'CONFERMATO', 'ARRIVATO')
TIPI_VISITA = [('', '—'), ('PRIMA_VISITA', 'Prima visita'), ('CONTROLLO', 'Controllo'),
               ('PRESTAZIONE', 'Prestazione'), ('URGENZA', 'Urgenza')]
ETICHETTA_TIPO_VISITA = dict(TIPI_VISITA)
CANALI = [('WHATSAPP', 'WhatsApp'), ('SMS', 'SMS'), ('EMAIL', 'Email')]
# da dove arriva il paziente: per sapere cosa porta pazienti nuovi
PROVENIENZE = [('', '—'), ('MEDICO', 'Medico curante o specialista'), ('PASSAPAROLA', 'Passaparola'),
               ('INTERNET', 'Internet / Google'), ('SOCIAL', 'Social'),
               ('CONVENZIONE', 'Convenzione / assicurazione'), ('ALTRA_SEDE', 'Da un\'altra sede del gruppo'),
               ('ALTRO', 'Altro')]
ETICHETTA_PROVENIENZA = dict(PROVENIENZE)
METODI_PAGAMENTO = [('CONTANTI', 'Contanti'), ('POS', 'POS / carta'), ('BONIFICO', 'Bonifico'),
                    ('ASSEGNO', 'Assegno')]
ETICHETTA_PAGAMENTO = dict(METODI_PAGAMENTO)
FASCE_ATTESA = [('', 'Qualsiasi ora'), ('MATTINA', 'Solo mattina'), ('POMERIGGIO', 'Solo pomeriggio')]
# degenza di un intervento: quante notti occupa un letto
DEGENZE = [('', '—'), ('DH', 'Day hospital (senza notte)'), ('NOTTE', 'Una notte'),
           ('RICOVERO', 'Ricovero (più notti)')]
ETICHETTA_DEGENZA = {'': '', 'DH': 'DH', 'NOTTE': 'Notte', 'RICOVERO': 'Ricovero'}
MASSIMO_NOTTI = 60
# le voci della checklist pre-operatoria, se non cambiate in Impostazioni
CHECKLIST_PREDEFINITA = ['Esami pre-operatori', 'Consenso firmato', 'Anestesista confermato',
                         'Preparazione consegnata', 'Acconto versato']


def leggi_degenza(testo):
    """'DH', 'day hospital', 'NOTTE', '1 notte', 'RO', 'ricovero', '3 notti' ->
    (codice, notti). None se il testo non si capisce ('?', vuoto)."""
    t = ' '.join(re.sub(r'[^a-z0-9]+', ' ', (testo or '').lower()).split())
    if not t:
        return None
    m = re.fullmatch(r'(?:ricovero |ro )?(\d{1,2}) ?(?:notti|notte|n|gg|giorni)', t)
    if m:
        n = int(m.group(1))
        if n == 0:
            return 'DH', None
        return ('NOTTE', None) if n == 1 else ('RICOVERO', min(n, MASSIMO_NOTTI))
    if t in ('dh', 'd h', 'day hospital', 'day surgery', 'ds', 'd s', 'giornaliero', 'ambulatoriale'):
        return 'DH', None
    if t in ('notte', 'una notte', 'n', 'notturno', 'pernotto', 'pernottamento', 'overnight'):
        return 'NOTTE', None
    if t in ('ro', 'r o', 'ricovero', 'ricovero ordinario', 'ordinario', 'degenza'):
        return 'RICOVERO', None
    return None


# euro: il modulo di prenotazione, la cassa e l'importazione non vanno oltre.
# Un importo piu' alto e' quasi certamente un errore di battitura
MASSIMO_IMPORTO = 100000


def importo_in_testo(cent):
    """12345 -> '123,45'; 125050 -> '1.250,50'; None -> ''."""
    if cent is None:
        return ''
    euro, resto = divmod(abs(cent), 100)
    return '%s%s,%02d' % ('-' if cent < 0 else '', '{:,}'.format(euro).replace(',', '.'), resto)


class Struttura(Base):
    """Una sede: ha le sue stanze e il suo aspetto (logo, colore, societa')."""
    __tablename__ = 'strutture'
    id = Column(Integer, primary_key=True)
    nome = Column(String(80), nullable=False, unique=True)
    attiva = Column(Boolean, default=True, nullable=False)
    societa = Column(String(120), default='')             # ragione sociale
    colore = Column(String(7), default=COLORE_PREDEFINITO)  # colore dell'interfaccia
    # il logo sta nel database, gia' normalizzato in PNG: il backup resta un
    # file solo. "deferred": si legge solo quando serve davvero, non a ogni
    # pagina che nomina la struttura
    logo = deferred(Column(LargeBinary))
    logo_aggiornato = Column(DateTime)   # vuoto = nessun logo; serve anche da versione
    # recapiti: in testa alla stampa del giorno e nei messaggi ai pazienti
    indirizzo = Column(String(160), default='')
    telefono = Column(String(40), default='')
    email = Column(String(120), default='')
    # orario della griglia: dall'apertura alla chiusura, a fasce di "passo" minuti
    ora_apertura = Column(Time, default=APERTURA_PREDEFINITA)
    ora_chiusura = Column(Time, default=CHIUSURA_PREDEFINITA)
    passo = Column(Integer, default=30)
    giorni_apertura = Column(String(7), default=GIORNI_PREDEFINITI)   # lun..dom, 1 = aperta
    chiusa_festivi = Column(Boolean, default=False)   # False: i festivi sono solo segnalati
    patrono = Column(String(5), default='')           # 'gg/mm', festa locale
    posti_letto = Column(Integer)                     # vuoto = non si controllano i letti
    risorse = relationship('Risorsa', back_populates='struttura',
                           order_by='Risorsa.ordine')

    @property
    def ha_logo(self):
        return self.logo_aggiornato is not None

    @property
    def versione_logo(self):
        """Va nell'indirizzo del logo: cambia a ogni caricamento, cosi' il
        browser non mostra quello vecchio dalla sua cache. In millisecondi:
        due caricamenti nello stesso secondo darebbero lo stesso numero."""
        return int(self.logo_aggiornato.timestamp() * 1000) if self.logo_aggiornato else 0

    @property
    def colore_sicuro(self):
        """Il colore finisce in un foglio di stile: si accetta solo #rrggbb."""
        return (self.colore if re.fullmatch(r'#[0-9A-Fa-f]{6}', self.colore or '')
                else COLORE_PREDEFINITO)

    # letture sicure dell'orario: sui database aggiornati le colonne possono
    # essere vuote, e un valore storto non deve rompere la griglia
    @property
    def apertura(self):
        return self.ora_apertura or APERTURA_PREDEFINITA

    @property
    def chiusura(self):
        c = self.ora_chiusura or CHIUSURA_PREDEFINITA
        return c if c > self.apertura else CHIUSURA_PREDEFINITA

    @property
    def passo_min(self):
        return self.passo if self.passo in PASSI_AMMESSI else 30

    @property
    def giorni_aperti(self):
        """Insieme dei giorni della settimana aperti, 0 = lunedi."""
        g = self.giorni_apertura or ''
        if not re.fullmatch(r'[01]{7}', g):
            g = GIORNI_PREDEFINITI
        return {i for i, c in enumerate(g) if c == '1'}

    @property
    def patrono_giorno_mese(self):
        """(giorno, mese) della festa patronale, None se non indicata."""
        m = re.fullmatch(r'(\d{1,2})/(\d{1,2})', (self.patrono or '').strip())
        if not m:
            return None
        giorno, mese = int(m.group(1)), int(m.group(2))
        try:
            date(2024, mese, giorno)             # anno bisestile: il 29/02 vale
        except ValueError:
            return None
        return giorno, mese

    def __repr__(self):
        return self.nome


class Risorsa(Base):
    """Una stanza: ambulatorio, sala operatoria, sala endoscopica."""
    __tablename__ = 'risorse'
    id = Column(Integer, primary_key=True)
    nome = Column(String(60), nullable=False)
    tipo = Column(String(30), nullable=False, default='AMBULATORIO')
    struttura_id = Column(Integer, ForeignKey('strutture.id'), nullable=False)
    ordine = Column(Integer, default=0, nullable=False)
    attiva = Column(Boolean, default=True, nullable=False)
    struttura = relationship('Struttura', back_populates='risorse')
    __table_args__ = (UniqueConstraint('struttura_id', 'nome'),)

    def __repr__(self):
        return self.nome


class Operatore(Base):
    __tablename__ = 'operatori'
    id = Column(Integer, primary_key=True)
    cognome = Column(String(60), nullable=False)
    nome = Column(String(60), default='')
    specialita = Column(String(60), default='')
    colore = Column(String(7), default='#0087B4')   # usato nella griglia
    attivo = Column(Boolean, default=True, nullable=False)
    # per mandargli la sua agenda del giorno
    email = Column(String(120), default='')
    telefono = Column(String(30), default='')
    # i giorni in cui di solito opera, lun..dom, 1 = in sala: per sapere chi c'e'
    giorni_sala = Column(String(7), default='')

    @property
    def etichetta(self):
        return ('%s %s' % (self.cognome or '', self.nome or '')).strip()

    @property
    def giorni_di_sala(self):
        """Insieme dei giorni in cui opera, 0 = lunedi; vuoto se non indicati."""
        g = self.giorni_sala or ''
        return {i for i, c in enumerate(g) if c == '1'} if re.fullmatch(r'[01]{7}', g) else set()

    @property
    def colore_sicuro(self):
        """Il colore finisce dentro un attributo style: si accetta solo #rrggbb."""
        # fullmatch e non match: con '$' un '#0087b4\n' passerebbe
        return (self.colore if re.fullmatch(r'#[0-9A-Fa-f]{6}', self.colore or '')
                else '#154381')

    def __repr__(self):
        return self.etichetta


class Prestazione(Base):
    __tablename__ = 'prestazioni'
    id = Column(Integer, primary_key=True)
    nome = Column(String(80), nullable=False, unique=True)
    durata_min = Column(Integer, nullable=False, default=30)
    # campi extra richiesti dal tipo di prestazione, separati da virgole:
    # "Sedazione?, Anestesista, Preparazione consegnata?". Il punto
    # interrogativo finale fa del campo una casella si'/no.
    campi_extra = Column(String(200), default='')
    # indicazioni per il paziente: finiscono sul promemoria e nei messaggi
    preparazione = Column(Text, default='')
    tariffa_cent = Column(Integer)          # prezzo di listino; vuoto = non indicato

    @property
    def tariffa_testo(self):
        return importo_in_testo(self.tariffa_cent)

    @property
    def elenco_campi_extra(self):
        """[(etichetta, si_no)], senza doppioni e senza voci vuote."""
        visti, uscita = set(), []
        for pezzo in (self.campi_extra or '').split(','):
            pezzo = ' '.join(pezzo.split())
            si_no = pezzo.endswith('?')
            etichetta = pezzo.rstrip('?').strip()[:40]
            if etichetta and etichetta.lower() not in visti:
                visti.add(etichetta.lower())
                uscita.append((etichetta, si_no))
        return uscita[:8]

    def __repr__(self):
        return self.nome


class Paziente(Base):
    __tablename__ = 'pazienti'
    id = Column(Integer, primary_key=True)
    cognome = Column(String(60), nullable=False)
    nome = Column(String(60), default='')
    telefono = Column(String(30), default='')      # il numero principale, di solito il cellulare
    note = Column(Text, default='')
    telefono2 = Column(String(30), default='')
    email = Column(String(120), default='')
    data_nascita = Column(Date)
    codice_fiscale = Column(String(16), default='')
    promemoria = Column(Boolean, default=True)     # accetta i promemoria degli appuntamenti
    canale = Column(String(10), default='WHATSAPP')
    creato_il = Column(DateTime, default=datetime.now)
    provenienza = Column(String(20), default='')
    inviato_da = Column(String(80), default='')     # il medico che lo manda, per esempio
    indirizzo = Column(String(200), default='')     # via, numero, CAP e citta' in una riga
    sesso = Column(String(1), default='')           # 'M', 'F' o vuoto
    luogo_nascita = Column(String(4), default='')   # codice del comune o dello stato estero (F839 = Napoli)

    @property
    def etichetta_provenienza(self):
        # vuota se non indicata: l'etichetta '—' serve solo al menu a tendina
        return ETICHETTA_PROVENIENZA.get(self.provenienza, '') if self.provenienza else ''

    @property
    def etichetta(self):
        return ('%s %s' % (self.cognome or '', self.nome or '')).strip()

    @property
    def eta(self):
        if not self.data_nascita:
            return None
        oggi = date.today()
        return oggi.year - self.data_nascita.year - (
            (oggi.month, oggi.day) < (self.data_nascita.month, self.data_nascita.day))

    def __repr__(self):
        return self.etichetta


class Turno(Base):
    """Regola ricorrente di apertura: chi sta dove, in che giorno e fascia.

    E' questa tabella che rende inutile precompilare a mano tutti i giorni
    del mese come facciamo nei fogli Excel.
    """
    __tablename__ = 'turni'
    id = Column(Integer, primary_key=True)
    operatore_id = Column(Integer, ForeignKey('operatori.id'), nullable=False)
    risorsa_id = Column(Integer, ForeignKey('risorse.id'), nullable=False)
    giorno_settimana = Column(Integer, nullable=False)   # 0 = lunedi
    ora_inizio = Column(Time, nullable=False)
    ora_fine = Column(Time, nullable=False)
    valido_da = Column(Date, nullable=False, default=date.today)
    valido_a = Column(Date)                              # None = a tempo indeterminato
    operatore = relationship('Operatore')
    risorsa = relationship('Risorsa')

    def vale_il(self, g):
        if self.giorno_settimana != g.weekday():
            return False
        if self.valido_da and g < self.valido_da:
            return False
        if self.valido_a and g > self.valido_a:
            return False
        return True


class Appuntamento(Base):
    __tablename__ = 'appuntamenti'
    id = Column(Integer, primary_key=True)
    risorsa_id = Column(Integer, ForeignKey('risorse.id'), nullable=False)
    operatore_id = Column(Integer, ForeignKey('operatori.id'), nullable=False)
    paziente_id = Column(Integer, ForeignKey('pazienti.id'))
    prestazione_id = Column(Integer, ForeignKey('prestazioni.id'))
    inizio = Column(DateTime, nullable=False, index=True)
    fine = Column(DateTime, nullable=False)
    stato = Column(String(20), default='PRENOTATO', nullable=False)
    note = Column(Text, default='')
    creato_il = Column(DateTime, default=datetime.now)
    modificato_il = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    # come nelle agende Excel dell'accettazione
    tipo = Column(String(20), default='')           # prima visita, controllo...
    convenzione = Column(String(80), default='')    # privato o nome dell'assicurazione
    importo_cent = Column(Integer)                  # in centesimi; vuoto = non indicato
    extra = Column(Text, default='')                # campi extra della prestazione, in JSON
    arrivato_alle = Column(DateTime)
    stato_il = Column(DateTime)                     # ultimo cambio di stato
    # incasso: quanto, come e quando (la cassa del giorno somma per data di pagamento)
    pagato_cent = Column(Integer)
    pagamento = Column(String(12), default='')
    pagato_il = Column(DateTime)
    serie = Column(String(12), default='')          # appuntamenti ripetuti: stesso codice
    # interventi: degenza, notti di ricovero, checklist pre-operatoria {voce: quando}
    degenza = Column(String(12), default='')
    notti = Column(Integer)
    checklist = Column(Text, default='')

    risorsa = relationship('Risorsa')
    operatore = relationship('Operatore')
    paziente = relationship('Paziente')
    prestazione = relationship('Prestazione')

    # rete di sicurezza sotto al lucchetto applicativo: la stessa stanza non
    # puo' avere due appuntamenti attivi che iniziano nello stesso istante.
    # Parziale: un appuntamento disdetto non deve impedire di riprenotare l'ora
    __table_args__ = (Index('appuntamento_attivo_unico', 'risorsa_id', 'inizio', unique=True,
                            sqlite_where=text("stato IN ('PRENOTATO', 'CONFERMATO', 'ARRIVATO')")),)

    @property
    def durata_min(self):
        return int((self.fine - self.inizio).total_seconds() // 60)

    @property
    def attivo(self):
        return self.stato in STATI_ATTIVI

    @property
    def etichetta_stato(self):
        return ETICHETTA_STATO.get(self.stato, self.stato or '')

    @property
    def etichetta_tipo(self):
        return ETICHETTA_TIPO_VISITA.get(self.tipo or '', '')

    @property
    def importo_testo(self):
        return importo_in_testo(self.importo_cent)

    @property
    def pagato_testo(self):
        return importo_in_testo(self.pagato_cent)

    @property
    def pagato(self):
        return self.pagato_il is not None

    @property
    def etichetta_pagamento(self):
        return ETICHETTA_PAGAMENTO.get(self.pagamento or '', '')

    @property
    def notti_letto(self):
        """Quante notti occupa un letto: DH nessuna, NOTTE una, RICOVERO
        quelle indicate (almeno una)."""
        if self.degenza == 'NOTTE':
            return 1
        if self.degenza == 'RICOVERO':
            return min(max(self.notti or 1, 1), MASSIMO_NOTTI)
        return 0

    @property
    def etichetta_degenza(self):
        if self.degenza == 'RICOVERO' and (self.notti or 0) > 1:
            return 'Ricovero, %d notti' % self.notti
        return ETICHETTA_DEGENZA.get(self.degenza or '', self.degenza or '')

    @property
    def spunte(self):
        """La checklist salvata: {voce: 'aaaa-mm-gg hh:mm'}. Rovinata vale vuota."""
        import json
        try:
            v = json.loads(self.checklist or '{}')
        except ValueError:
            return {}
        return {str(k): str(x) for k, x in v.items()} if isinstance(v, dict) else {}

    @property
    def valori_extra(self):
        """I campi extra salvati, come dizionario. Un JSON rovinato vale vuoto."""
        import json
        try:
            v = json.loads(self.extra or '{}')
        except ValueError:
            return {}
        return {str(k): str(x) for k, x in v.items()} if isinstance(v, dict) else {}


class Assenza(Base):
    """Un medico non c'e': ferie, malattia, congresso. Nei giorni indicati i
    suoi turni non aprono fasce."""
    __tablename__ = 'assenze'
    id = Column(Integer, primary_key=True)
    operatore_id = Column(Integer, ForeignKey('operatori.id'), nullable=False)
    dal = Column(Date, nullable=False)
    al = Column(Date, nullable=False)
    motivo = Column(String(60), default='')
    operatore = relationship('Operatore')

    def copre(self, g):
        return self.dal <= g <= self.al


class Chiusura(Base):
    """La struttura e' chiusa: festivita', chiusura estiva, lavori."""
    __tablename__ = 'chiusure'
    id = Column(Integer, primary_key=True)
    struttura_id = Column(Integer, ForeignKey('strutture.id'), nullable=False)
    dal = Column(Date, nullable=False)
    al = Column(Date, nullable=False)
    motivo = Column(String(80), default='')
    struttura = relationship('Struttura')

    def copre(self, g):
        return self.dal <= g <= self.al


class Tariffa(Base):
    """Prezzo di una prestazione con una convenzione o assicurazione, se
    diverso dal listino."""
    __tablename__ = 'tariffe'
    id = Column(Integer, primary_key=True)
    prestazione_id = Column(Integer, ForeignKey('prestazioni.id'), nullable=False)
    convenzione = Column(String(80), nullable=False)
    importo_cent = Column(Integer, nullable=False)
    prestazione = relationship('Prestazione')
    __table_args__ = (UniqueConstraint('prestazione_id', 'convenzione'),)

    @property
    def importo_testo(self):
        return importo_in_testo(self.importo_cent)


class Attesa(Base):
    """Lista d'attesa: il paziente vuole un posto prima di quello che c'era,
    o non ce n'era proprio. Quando si libera una fascia adatta, il programma
    propone chi chiamare, dal piu' vecchio in lista."""
    __tablename__ = 'lista_attesa'
    id = Column(Integer, primary_key=True)
    paziente_id = Column(Integer, ForeignKey('pazienti.id'), nullable=False)
    operatore_id = Column(Integer, ForeignKey('operatori.id'))       # vuoto = qualsiasi medico
    prestazione_id = Column(Integer, ForeignKey('prestazioni.id'))
    struttura_id = Column(Integer, ForeignKey('strutture.id'))
    dal = Column(Date)                   # disponibile da
    entro = Column(Date)                 # il posto serve entro
    fascia = Column(String(12), default='')
    note = Column(Text, default='')
    creato_il = Column(DateTime, default=datetime.now)
    chiusa_il = Column(DateTime)
    esito = Column(String(12), default='')        # PRENOTATO, RINUNCIA
    appuntamento_id = Column(Integer, ForeignKey('appuntamenti.id'))
    paziente = relationship('Paziente')
    operatore = relationship('Operatore')
    prestazione = relationship('Prestazione')
    struttura = relationship('Struttura')

    @property
    def aperta(self):
        return self.chiusa_il is None

    def adatta_a(self, a):
        """La fascia dell'appuntamento a va bene per questa richiesta?"""
        g = a.inizio.date()
        if not self.aperta or self.paziente_id == a.paziente_id:
            return False
        if self.operatore_id and self.operatore_id != a.operatore_id:
            return False
        if self.prestazione_id and self.prestazione_id != a.prestazione_id:
            return False
        if self.struttura_id and a.risorsa is not None and self.struttura_id != a.risorsa.struttura_id:
            return False
        if self.dal and g < self.dal:
            return False
        if self.entro and g > self.entro:
            return False
        if self.fascia == 'MATTINA' and a.inizio.time() >= time(13, 0):
            return False
        if self.fascia == 'POMERIGGIO' and a.inizio.time() < time(13, 0):
            return False
        return True


class Attivita(Base):
    """Cose da fare della segreteria: richiamare un paziente, sollecitare un
    referto. Nel giorno indicato compaiono come notifica."""
    __tablename__ = 'attivita'
    id = Column(Integer, primary_key=True)
    testo = Column(String(300), nullable=False)
    per_il = Column(Date, nullable=False, default=date.today)
    paziente_id = Column(Integer, ForeignKey('pazienti.id'))
    appuntamento_id = Column(Integer, ForeignKey('appuntamenti.id'))
    creato_il = Column(DateTime, default=datetime.now)
    fatto_il = Column(DateTime)
    paziente = relationship('Paziente')


class NotaGiorno(Base):
    """Una nota per il giorno di una struttura: 'Lippiello arriva alle 10'."""
    __tablename__ = 'note_giorno'
    id = Column(Integer, primary_key=True)
    struttura_id = Column(Integer, ForeignKey('strutture.id'), nullable=False)
    data = Column(Date, nullable=False)
    testo = Column(Text, default='')
    __table_args__ = (UniqueConstraint('struttura_id', 'data'),)


class Documento(Base):
    """Un file allegato alla scheda del paziente: impegnativa, referto,
    consenso firmato. Sta nel database, cosi' finisce nei backup."""
    __tablename__ = 'documenti'
    id = Column(Integer, primary_key=True)
    paziente_id = Column(Integer, ForeignKey('pazienti.id'), nullable=False)
    appuntamento_id = Column(Integer, ForeignKey('appuntamenti.id'))
    nome = Column(String(120), nullable=False)
    descrizione = Column(String(200), default='')
    tipo = Column(String(40), nullable=False)       # application/pdf, image/jpeg, image/png
    dimensione = Column(Integer, default=0)
    dati = deferred(Column(LargeBinary))
    caricato_il = Column(DateTime, default=datetime.now)
    paziente = relationship('Paziente')


class ModuloStampa(Base):
    """Testo da stampare con i dati dell'appuntamento: consenso, istruzioni
    di preparazione con le date gia' calcolate."""
    __tablename__ = 'moduli'
    id = Column(Integer, primary_key=True)
    nome = Column(String(80), nullable=False, unique=True)
    testo = Column(Text, default='')
    prestazione_id = Column(Integer, ForeignKey('prestazioni.id'))    # vuoto = per tutte
    firma = Column(Boolean, default=True)           # righe per le firme in fondo
    prestazione = relationship('Prestazione')


class Appunto(Base):
    """Un appunto da confermare: una prenotazione che non si puo' ancora
    mettere in agenda (manca la stanza, la sala e' gia' occupata, il paziente
    deve richiamare). Si vede nella giornata e fra i "Da confermare"; con
    Prenota diventa un appuntamento. Le importazioni ci mettono le righe in
    conflitto o incomplete, invece di lasciarle fuori."""
    __tablename__ = 'appunti'
    id = Column(Integer, primary_key=True)
    testo = Column(Text, nullable=False, default='')         # cosa c'e' da confermare
    giorno = Column(Date)
    ora = Column(Time)
    durata_min = Column(Integer)
    struttura_id = Column(Integer, ForeignKey('strutture.id'))
    risorsa_id = Column(Integer, ForeignKey('risorse.id'))
    operatore_id = Column(Integer, ForeignKey('operatori.id'))
    prestazione_id = Column(Integer, ForeignKey('prestazioni.id'))
    paziente_id = Column(Integer, ForeignKey('pazienti.id'))
    # per chi non e' ancora in anagrafica
    cognome = Column(String(60), default='')
    nome = Column(String(60), default='')
    telefono = Column(String(30), default='')
    note = Column(Text, default='')                  # le note della riga d'origine
    origine = Column(String(200), default='')        # "Importazione AGENDA.xlsx, riga 77"
    creato_il = Column(DateTime, default=datetime.now)
    chiuso_il = Column(DateTime)
    esito = Column(String(12), default='')           # PRENOTATO, SCARTATO
    appuntamento_id = Column(Integer, ForeignKey('appuntamenti.id'))
    risorsa = relationship('Risorsa')
    operatore = relationship('Operatore')
    prestazione = relationship('Prestazione')
    paziente = relationship('Paziente')

    @property
    def aperto(self):
        return self.chiuso_il is None

    @property
    def chi(self):
        if self.paziente is not None:
            return self.paziente.etichetta
        return ' '.join(x for x in (self.cognome, self.nome) if x)

    @property
    def recapito(self):
        return (self.paziente.telefono if self.paziente is not None else '') or self.telefono or ''


class RegolaEmail(Base):
    """Un'email che parte da sola quando si prenota un appuntamento di quel
    medico (o di tutti) per una di quelle prestazioni, con testo e allegati.
    Esempio: la preparazione agli esami endoscopici, con le due informative."""
    __tablename__ = 'regole_email'
    id = Column(Integer, primary_key=True)
    nome = Column(String(80), nullable=False)
    attiva = Column(Boolean, default=True)
    operatore_id = Column(Integer, ForeignKey('operatori.id'))     # vuoto = tutti i medici
    prestazioni = Column(String(400), default='')                  # id separati da virgole
    oggetto = Column(String(200), nullable=False, default='')
    testo = Column(Text, nullable=False, default='')
    creata_il = Column(DateTime, default=datetime.now)
    operatore = relationship('Operatore')
    allegati = relationship('AllegatoRegola', cascade='all, delete-orphan', order_by='AllegatoRegola.id')

    @property
    def id_prestazioni(self):
        return {int(x) for x in (self.prestazioni or '').split(',') if x.strip().isdigit()}


class AllegatoRegola(Base):
    """Un file che parte con l'email di una regola: sta nel database, cosi'
    finisce nei backup e non dipende da una cartella del PC."""
    __tablename__ = 'allegati_regole'
    id = Column(Integer, primary_key=True)
    regola_id = Column(Integer, ForeignKey('regole_email.id'), nullable=False)
    nome = Column(String(120), nullable=False)
    tipo = Column(String(60), nullable=False, default='application/pdf')
    dimensione = Column(Integer, default=0)
    dati = deferred(Column(LargeBinary))


class Invio(Base):
    """Un messaggio a un paziente, mandato o da mandare: e' insieme la coda
    (stato DA_INVIARE, con l'ora del prossimo tentativo) e il registro."""
    __tablename__ = 'invii'
    id = Column(Integer, primary_key=True)
    canale = Column(String(10), nullable=False)          # EMAIL, WHATSAPP
    motivo = Column(String(14), nullable=False)          # PREPARAZIONE, PROMEMORIA, PROVA
    appuntamento_id = Column(Integer, ForeignKey('appuntamenti.id'), index=True)
    paziente_id = Column(Integer, ForeignKey('pazienti.id'), index=True)
    regola_id = Column(Integer, ForeignKey('regole_email.id'))
    per_inizio = Column(DateTime)       # l'ora dell'appuntamento quando e' entrato in coda
    destinatario = Column(String(120), nullable=False, default='')
    oggetto = Column(String(200), default='')
    testo = Column(Text, default='')
    stato = Column(String(12), nullable=False, default='DA_INVIARE', index=True)   # DA_INVIARE, IN_CORSO, INVIATO, ERRORE, ANNULLATO
    tentativi = Column(Integer, default=0)
    errore = Column(String(300), default='')
    prossimo = Column(DateTime)                          # quando provarci (o riprovarci)
    a_mano = Column(Boolean, default=False)              # con il pulsante, non da solo
    creato_il = Column(DateTime, default=datetime.now)
    inviato_il = Column(DateTime)
    appuntamento = relationship('Appuntamento')
    paziente = relationship('Paziente')
    regola = relationship('RegolaEmail')


class Impostazione(Base):
    """Coppie chiave-valore: versione dello schema, cartella dei backup,
    testo dei promemoria."""
    __tablename__ = 'impostazioni'
    chiave = Column(String(60), primary_key=True)
    valore = Column(Text, default='')


class Modifica(Base):
    """Storico: chi ha toccato cosa. Con un solo utente serve a ricostruire
    gli spostamenti, non ad attribuire responsabilita."""
    __tablename__ = 'modifiche'
    id = Column(Integer, primary_key=True)
    quando = Column(DateTime, default=datetime.now, nullable=False)
    entita = Column(String(40), nullable=False)
    entita_id = Column(Integer)
    azione = Column(String(20), nullable=False)
    dettaglio = Column(Text, default='')


# ============================================================ turni del personale (1.8)
# Il personale della struttura e i suoi turni: medici, infermieri, OSS, accettazione...
# Sono un'altra cosa dai "turni" dell'agenda (tabella turni): quelli dicono quando un
# medico riceve in una stanza e aprono le fasce prenotabili; questi dicono chi lavora,
# quando e dove, per tutto il personale. Un medico del personale puo' essere collegato
# al suo medico dell'agenda: nella vista del giorno compaiono anche i suoi ambulatori.
RUOLI = [
    # codice, nome del gruppo, nome di una persona, icona (static: templates/_icone.html)
    ('MEDICO', 'Medici', 'Medico', 'stethoscope'),
    ('INFERMIERE', 'Infermieri', 'Infermiere', 'heart-pulse'),
    ('OSS', 'OSS', 'OSS', 'hand-heart'),
    ('TECNICO', 'Tecnici', 'Tecnico', 'microscope'),
    ('AMMINISTRATIVO', 'Accettazione e amministrazione', 'Amministrativo', 'clipboard-list'),
    ('AUSILIARIO', 'Ausiliari', 'Ausiliario', 'spray-can'),
    ('ALTRO', 'Altro personale', 'Altro', 'users'),
]
ETICHETTA_RUOLO = {r[0]: r[1] for r in RUOLI}
ORDINE_RUOLO = {r[0]: i for i, r in enumerate(RUOLI)}

# Le categorie dei tipi di turno: un turno di LAVORO conta nelle ore e nella copertura;
# la REPERIBILITA ha un orario ma le sue ore si contano a parte; ASSENZA e RIPOSO
# valgono tutto il giorno, senza orario (ferie, malattia, riposo, smonto notte).
CATEGORIE_TURNO = [('LAVORO', 'Lavoro'), ('REPERIBILITA', 'Reperibilità'), ('ASSENZA', 'Assenza'),
                   ('RIPOSO', 'Riposo')]
ETICHETTA_CATEGORIA = dict(CATEGORIE_TURNO)

# I tipi di turno con cui comincia ogni gestionale (si cambiano in Turni → Tipi di turno).
# I colori sono delle scale Radix Colors (MIT, vedi static/icone/LICENZE.txt): sfondo
# chiaro e codice scuro, o sfondo pieno e codice bianco per la notte.
TIPI_TURNO_INIZIALI = [
    # codice, nome, categoria, inizio, fine, pausa (minuti), colore
    ('M', 'Mattina', 'LAVORO', time(7, 0), time(14, 0), 0, '#FBE577'),
    ('P', 'Pomeriggio', 'LAVORO', time(14, 0), time(21, 0), 0, '#FFD19A'),
    ('N', 'Notte', 'LAVORO', time(21, 0), time(7, 0), 0, '#3E63DD'),
    ('G', 'Giornata', 'LAVORO', time(8, 0), time(17, 0), 60, '#B8EAE0'),
    ('RE', 'Reperibilità', 'REPERIBILITA', time(20, 0), time(8, 0), 0, '#F7DEF8'),
    ('SN', 'Smonto notte', 'RIPOSO', None, None, 0, '#EBE4FF'),
    ('R', 'Riposo', 'RIPOSO', None, None, 0, '#E8E8EC'),
    ('F', 'Ferie', 'ASSENZA', None, None, 0, '#C9E8CA'),
    ('MA', 'Malattia', 'ASSENZA', None, None, 0, '#FFCDC2'),
    ('PE', 'Permesso', 'ASSENZA', None, None, 0, '#B5E9F0'),
]


def _colore_sicuro(colore, ripiego='#E8E8EC'):
    return colore if re.fullmatch(r'#[0-9A-Fa-f]{6}', colore or '') else ripiego


def _luminanza(colore):
    """Luminanza relativa WCAG di un #rrggbb."""
    def canale(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(colore[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canale(r) + 0.7152 * canale(g) + 0.0722 * canale(b)


def testo_su(colore):
    """Il colore del testo che si legge meglio su quello sfondo: il blu scuro del
    programma o il bianco, scegliendo il contrasto piu' alto (WCAG)."""
    L = _luminanza(_colore_sicuro(colore))
    scuro = (L + 0.05) / (_luminanza('#16263F') + 0.05)
    bianco = 1.05 / (L + 0.05)
    return '#16263F' if scuro >= bianco else '#FFFFFF'


class Persona(Base):
    """Una persona del personale: medico, infermiere, OSS, accettazione..."""
    __tablename__ = 'personale'
    id = Column(Integer, primary_key=True)
    cognome = Column(String(60), nullable=False)
    nome = Column(String(60), default='')
    ruolo = Column(String(20), nullable=False, default='INFERMIERE')
    qualifica = Column(String(60), default='')          # "Coordinatrice", "Anestesista", "Strumentista"
    telefono = Column(String(30), default='')
    email = Column(String(120), default='')
    minuti_settimana = Column(Integer)                  # ore del contratto, in minuti (36 ore = 2160)
    operatore_id = Column(Integer, ForeignKey('operatori.id'))   # il suo medico dell'agenda, se c'e'
    struttura_id = Column(Integer, ForeignKey('strutture.id'))   # vuoto = tutte le strutture
    ordine = Column(Integer, default=0, nullable=False)
    attiva = Column(Boolean, default=True, nullable=False)
    note = Column(String(300), default='')
    creato_il = Column(DateTime, default=datetime.now)
    operatore = relationship('Operatore')
    struttura = relationship('Struttura')

    @property
    def etichetta(self):
        return ('%s %s' % (self.cognome or '', self.nome or '')).strip()

    @property
    def ruolo_etichetta(self):
        return next((r[2] for r in RUOLI if r[0] == self.ruolo), self.ruolo or '')

    @property
    def ore_settimana(self):
        """'36' o '37:30', vuoto se non indicate."""
        if not self.minuti_settimana:
            return ''
        h, m = divmod(self.minuti_settimana, 60)
        return '%d' % h if not m else '%d:%02d' % (h, m)

    def __repr__(self):
        return self.etichetta


class TipoTurno(Base):
    """Mattina, pomeriggio, notte, riposo, ferie...: codice, orario e colore."""
    __tablename__ = 'tipi_turno'
    id = Column(Integer, primary_key=True)
    codice = Column(String(4), nullable=False, unique=True)
    nome = Column(String(40), nullable=False)
    categoria = Column(String(12), nullable=False, default='LAVORO')
    ora_inizio = Column(Time)                           # vuoti per riposi e assenze
    ora_fine = Column(Time)                             # prima dell'inizio: finisce il giorno dopo
    pausa_min = Column(Integer, default=0, nullable=False)
    colore = Column(String(7), default='#E8E8EC')
    ordine = Column(Integer, default=0, nullable=False)
    attivo = Column(Boolean, default=True, nullable=False)

    @property
    def con_orario(self):
        return self.categoria in ('LAVORO', 'REPERIBILITA') and self.ora_inizio is not None \
            and self.ora_fine is not None

    @property
    def tutto_il_giorno(self):
        return not self.con_orario

    @property
    def colore_sicuro(self):
        return _colore_sicuro(self.colore)

    @property
    def colore_testo(self):
        return testo_su(self.colore_sicuro)

    @property
    def minuti(self):
        """Durata del turno meno la pausa (0 per riposi e assenze)."""
        if not self.con_orario:
            return 0
        a = self.ora_inizio.hour * 60 + self.ora_inizio.minute
        b = self.ora_fine.hour * 60 + self.ora_fine.minute
        durata = (b - a) % 1440 or 1440
        return max(durata - (self.pausa_min or 0), 0)

    @property
    def orario(self):
        if not self.con_orario:
            return ''
        return '%s–%s' % (self.ora_inizio.strftime('%H:%M'), self.ora_fine.strftime('%H:%M'))

    def __repr__(self):
        return self.codice


class TurnoPersonale(Base):
    """Un turno di una persona in un giorno. 'giorno' e' il giorno in cui il
    turno comincia: la notte del 12 e' del 12 anche se finisce il 13 mattina.
    Riposi e assenze non hanno orario (inizio e fine vuoti)."""
    __tablename__ = 'turni_personale'
    id = Column(Integer, primary_key=True)
    persona_id = Column(Integer, ForeignKey('personale.id'), nullable=False)
    giorno = Column(Date, nullable=False)
    tipo_id = Column(Integer, ForeignKey('tipi_turno.id'))   # vuoto: orario scritto a mano
    inizio = Column(DateTime)
    fine = Column(DateTime)
    area = Column(String(60), default='')               # reparto o servizio: "Degenza", "Sala operatoria"
    note = Column(String(200), default='')
    creato_il = Column(DateTime, default=datetime.now)
    modificato_il = Column(DateTime, default=datetime.now)
    persona = relationship('Persona')
    tipo = relationship('TipoTurno')
    __table_args__ = (Index('ix_turni_personale_giorno', 'giorno'),
                      Index('ix_turni_personale_persona_giorno', 'persona_id', 'giorno'))

    @property
    def categoria(self):
        return self.tipo.categoria if self.tipo is not None else 'LAVORO'

    @property
    def con_orario(self):
        return self.inizio is not None and self.fine is not None

    @property
    def codice(self):
        return self.tipo.codice if self.tipo is not None else 'O'

    @property
    def minuti(self):
        """Minuti del turno, pausa tolta; 0 per riposi e assenze."""
        if not self.con_orario:
            return 0
        pausa = (self.tipo.pausa_min or 0) if self.tipo is not None else 0
        return max(int((self.fine - self.inizio).total_seconds() // 60) - pausa, 0)

    @property
    def di_notte(self):
        """Finisce il giorno dopo: una notte (o una reperibilita' notturna)."""
        return self.con_orario and self.fine.date() > self.inizio.date()

    @property
    def orario(self):
        if not self.con_orario:
            return ''
        return '%s–%s' % (self.inizio.strftime('%H:%M'), self.fine.strftime('%H:%M'))


class CoperturaMinima(Base):
    """Quante persone di un ruolo servono almeno in un tipo di turno (e area),
    nei giorni indicati: '2 infermieri di notte in degenza, tutti i giorni'."""
    __tablename__ = 'coperture_minime'
    id = Column(Integer, primary_key=True)
    ruolo = Column(String(20), nullable=False)
    tipo_id = Column(Integer, ForeignKey('tipi_turno.id'), nullable=False)
    area = Column(String(60), default='')               # vuota: qualunque area
    giorni = Column(String(7), default='1111111', nullable=False)   # lun..dom
    minimo = Column(Integer, nullable=False, default=1)
    tipo = relationship('TipoTurno')

    def vale_il(self, g):
        return re.fullmatch(r'[01]{7}', self.giorni or '') is not None and self.giorni[g.weekday()] == '1'


# ===================================================== strutture del gruppo
# "Dove si fa": le prestazioni delle altre strutture del gruppo, dal database
# delle prestazioni (un file Excel: una riga per prestazione, una colonna per
# struttura con una X dove si fa), per indirizzare un paziente dove serve.
class StrutturaGruppo(Base):
    """Un'altra struttura del gruppo, con i recapiti da dare al paziente. Il nome
    e' quello della colonna del database delle prestazioni."""
    __tablename__ = 'strutture_gruppo'
    id = Column(Integer, primary_key=True)
    nome = Column(String(80), nullable=False)
    nome_breve = Column(String(30), default='')        # per le etichette; vuoto = il nome
    indirizzo = Column(String(160), default='')
    citta = Column(String(80), default='')
    telefono = Column(String(40), default='')
    telefono2 = Column(String(40), default='')
    email = Column(String(120), default='')
    sito = Column(String(300), default='')             # prenotazione online
    orari = Column(String(200), default='')
    prenotazione = Column(String(400), default='')     # come si prenota: "solo per telefono, al mattino"
    note = Column(String(400), default='')
    struttura_id = Column(Integer, ForeignKey('strutture.id'))   # e' una struttura di questo gestionale
    colore = Column(String(7), default='')
    ordine = Column(Integer, default=0, nullable=False)
    attiva = Column(Boolean, default=True, nullable=False)       # spenta: non compare nelle ricerche
    nel_database = Column(Boolean, default=True, nullable=False)  # c'era nell'ultima importazione
    creato_il = Column(DateTime, default=datetime.now)
    modificato_il = Column(DateTime, default=datetime.now)
    struttura = relationship('Struttura')

    @property
    def etichetta(self):
        return (self.nome_breve or '').strip() or self.nome

    @property
    def con_recapiti(self):
        return bool((self.telefono or '').strip() or (self.indirizzo or '').strip() or (self.sito or '').strip())

    def __repr__(self):
        return self.nome


class VoceCatalogo(Base):
    """Una prestazione del database delle prestazioni del gruppo."""
    __tablename__ = 'catalogo'
    id = Column(Integer, primary_key=True)
    branca = Column(String(80), default='')
    nome = Column(String(160), nullable=False)
    sinonimi = Column(String(1000), default='')
    note = Column(String(1000), default='')
    ordine = Column(Integer, default=0, nullable=False)
    sedi = relationship('SedeVoce', cascade='all, delete-orphan', back_populates='voce')

    def __repr__(self):
        return self.nome


class SedeVoce(Base):
    """Dove si fa una prestazione: una X nel database. 'da_confermare' viene
    dalle note del database ("RAH: ... da confermare")."""
    __tablename__ = 'catalogo_sedi'
    voce_id = Column(Integer, ForeignKey('catalogo.id'), primary_key=True)
    struttura_id = Column(Integer, ForeignKey('strutture_gruppo.id'), primary_key=True)
    da_confermare = Column(Boolean, default=False, nullable=False)
    nota = Column(String(400), default='')
    voce = relationship('VoceCatalogo', back_populates='sedi')
    struttura = relationship('StrutturaGruppo')


class Indirizzato(Base):
    """Un paziente indirizzato a un'altra struttura del gruppo: il registro.
    Nomi di prestazione, struttura e paziente sono copiati: il registro resta
    leggibile anche dopo un database nuovo o una scheda cancellata."""
    __tablename__ = 'indirizzati'
    id = Column(Integer, primary_key=True)
    quando = Column(DateTime, default=datetime.now, nullable=False)
    struttura_id = Column(Integer, ForeignKey('strutture.id'))          # da quale struttura del gestionale
    gruppo_id = Column(Integer, ForeignKey('strutture_gruppo.id'))      # verso quale struttura del gruppo
    gruppo_nome = Column(String(80), default='')
    voce_id = Column(Integer, ForeignKey('catalogo.id'))
    prestazione = Column(String(160), default='')
    branca = Column(String(80), default='')
    paziente_id = Column(Integer, ForeignKey('pazienti.id'))
    paziente = Column(String(120), default='')
    canale = Column(String(12), default='voce')        # voce, telefono, whatsapp, email, stampa
    note = Column(String(200), default='')
    gruppo = relationship('StrutturaGruppo')
    scheda = relationship('Paziente')
    __table_args__ = (Index('ix_indirizzati_quando', 'quando'),)


CANALI_INDIRIZZO = [('voce', 'a voce'), ('telefono', 'al telefono'), ('whatsapp', 'WhatsApp'),
                    ('email', 'email'), ('stampa', 'foglio stampato')]


# ============================================================ aggiornamenti
# Versione dello schema, scritta in "impostazioni". 1-2 = gestionale 1.1-1.2
# (senza la tabella impostazioni), 3 = 1.3, 4 = 1.4, 5 = 1.4.1 (appunti da confermare),
# 6 = 1.4.3 (degenza, checklist, posti letto, giorni di sala dei chirurghi),
# 7 = 1.5 (indirizzo del paziente, email automatiche, promemoria, registro degli invii),
# 8 = 1.7 (sesso e luogo di nascita del paziente, per controllare e calcolare il codice fiscale),
# 9 = 1.8 (turni del personale: persone, tipi di turno, turni, coperture minime),
# 10 = 1.9 (Dove si fa: strutture del gruppo, prestazioni e dove si fanno, pazienti indirizzati).
VERSIONE_SCHEMA = 10

# Colonne aggiunte dopo la prima versione. create_all crea le tabelle nuove
# ma non tocca quelle esistenti: su un PC dove il gestionale e' gia'
# installato le colonne vanno aggiunte a mano, senza toccare i dati. Il
# DEFAULT serve alle righe gia' presenti, che altrimenti resterebbero vuote.
COLONNE_AGGIUNTE = {
    'strutture': [
        # 1.2
        ('societa', "VARCHAR(120) DEFAULT ''"),
        ('colore', "VARCHAR(7) DEFAULT '%s'" % COLORE_PREDEFINITO),
        ('logo', 'BLOB'),
        ('logo_aggiornato', 'DATETIME'),
        # 1.3
        ('indirizzo', "VARCHAR(160) DEFAULT ''"),
        ('telefono', "VARCHAR(40) DEFAULT ''"),
        ('email', "VARCHAR(120) DEFAULT ''"),
        ('ora_apertura', "TIME DEFAULT '08:00:00.000000'"),
        ('ora_chiusura', "TIME DEFAULT '20:00:00.000000'"),
        ('passo', 'INTEGER DEFAULT 30'),
        ('giorni_apertura', "VARCHAR(7) DEFAULT '%s'" % GIORNI_PREDEFINITI),
        ('chiusa_festivi', 'BOOLEAN DEFAULT 0'),
        ('patrono', "VARCHAR(5) DEFAULT ''"),
        # 1.4.3
        ('posti_letto', 'INTEGER'),
    ],
    'operatori': [
        # 1.4
        ('email', "VARCHAR(120) DEFAULT ''"),
        ('telefono', "VARCHAR(30) DEFAULT ''"),
        # 1.4.3
        ('giorni_sala', "VARCHAR(7) DEFAULT ''"),
    ],
    'pazienti': [
        ('telefono2', "VARCHAR(30) DEFAULT ''"),
        ('email', "VARCHAR(120) DEFAULT ''"),
        ('data_nascita', 'DATE'),
        ('codice_fiscale', "VARCHAR(16) DEFAULT ''"),
        ('promemoria', 'BOOLEAN DEFAULT 1'),
        ('canale', "VARCHAR(10) DEFAULT 'WHATSAPP'"),
        ('creato_il', 'DATETIME'),
        # 1.4
        ('provenienza', "VARCHAR(20) DEFAULT ''"),
        ('inviato_da', "VARCHAR(80) DEFAULT ''"),
        # 1.5
        ('indirizzo', "VARCHAR(200) DEFAULT ''"),
        # 1.7
        ('sesso', "VARCHAR(1) DEFAULT ''"),
        ('luogo_nascita', "VARCHAR(4) DEFAULT ''"),
    ],
    'prestazioni': [
        ('preparazione', "TEXT DEFAULT ''"),
        ('tariffa_cent', 'INTEGER'),
    ],
    'appuntamenti': [
        ('tipo', "VARCHAR(20) DEFAULT ''"),
        ('convenzione', "VARCHAR(80) DEFAULT ''"),
        ('importo_cent', 'INTEGER'),
        ('extra', "TEXT DEFAULT ''"),
        ('arrivato_alle', 'DATETIME'),
        ('stato_il', 'DATETIME'),
        # 1.4
        ('pagato_cent', 'INTEGER'),
        ('pagamento', "VARCHAR(12) DEFAULT ''"),
        ('pagato_il', 'DATETIME'),
        ('serie', "VARCHAR(12) DEFAULT ''"),
        # 1.4.3
        ('degenza', "VARCHAR(12) DEFAULT ''"),
        ('notti', 'INTEGER'),
        ('checklist', "TEXT DEFAULT ''"),
    ],
}


def aggiorna_schema(motore):
    """Aggiunge le colonne mancanti. Restituisce l'elenco di quelle aggiunte
    in questo avvio, come 'tabella.colonna'."""
    if motore.dialect.name != 'sqlite':
        return []            # con un altro database servono migrazioni vere
    aggiunte = []
    with motore.begin() as c:
        for tabella, colonne in COLONNE_AGGIUNTE.items():
            presenti = {r[1] for r in c.exec_driver_sql('PRAGMA table_info(%s)' % tabella)}
            for nome, tipo in colonne:
                if nome not in presenti:
                    c.exec_driver_sql('ALTER TABLE %s ADD COLUMN %s %s' % (tabella, nome, tipo))
                    aggiunte.append('%s.%s' % (tabella, nome))
    return aggiunte


def versione_trovata(motore):
    """La versione dello schema del database, prima di toccarlo. None se il
    database e' nuovo (nessuna tabella del gestionale)."""
    with motore.connect() as c:
        tabelle = {r[0] for r in c.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not tabelle & {'strutture', 'risorse', 'appuntamenti'}:
            return None
        if 'impostazioni' in tabelle:
            r = c.exec_driver_sql(
                "SELECT valore FROM impostazioni WHERE chiave = 'versione_schema'").fetchone()
            if r and str(r[0]).strip().isdigit():
                return int(r[0])
        colonne = {r[1] for r in c.exec_driver_sql('PRAGMA table_info(strutture)')}
        return 2 if 'logo' in colonne else 1


def in_transazione(motore, lavoro):
    """Esegue lavoro(cursore) in una transazione vera, BEGIN ... COMMIT.

    Il driver sqlite3 di Python apre da solo la transazione solo prima di
    INSERT e UPDATE: un CREATE TABLE andrebbe in automatico per conto suo e
    una ricostruzione interrotta a meta' lascerebbe tabelle a pezzi. Qui la
    transazione la apre il codice, e o passa tutto o non cambia niente."""
    grezza = motore.raw_connection()
    try:
        dbapi = grezza.driver_connection
        prima = dbapi.isolation_level
        dbapi.isolation_level = None
        cursore = dbapi.cursor()
        try:
            cursore.execute('BEGIN IMMEDIATE')
            risultato = lavoro(cursore)
            cursore.execute('COMMIT')
            return risultato
        except BaseException:
            cursore.execute('ROLLBACK')
            raise
        finally:
            dbapi.isolation_level = prima
    finally:
        grezza.close()


def _migra_a_3(motore):
    """Dalla 1.1-1.2 alla 1.3. Due cambiamenti oltre alle colonne nuove:

    1. il vincolo di unicita' su stanza e orario valeva per tutti gli
       appuntamenti: un appuntamento disdetto avrebbe impedito di riprenotare
       la stessa ora. Diventa un indice unico sui soli appuntamenti attivi.
       SQLite non sa togliere un vincolo: la tabella va ricostruita, dati
       compresi, dentro una transazione.
    2. fino alla 1.2 lo stato non si vedeva e valeva sempre CONFERMATO. Ora
       CONFERMATO vuol dire "il paziente ha confermato": quelli di prima
       diventano PRENOTATO."""
    from sqlalchemy.schema import CreateIndex
    dialetto = motore.dialect
    tabella = Appuntamento.__table__
    note = []

    def lavoro(cur):
        riga = cur.execute("SELECT sql FROM sqlite_master WHERE type = 'table' "
                           "AND name = 'appuntamenti'").fetchone()
        ddl_vecchio = riga[0] if riga else ''
        vecchio_vincolo = ('una_stanza_un_orario' in ddl_vecchio or
                           re.search(r'UNIQUE\s*\(\s*risorsa_id\s*,\s*inizio\s*\)', ddl_vecchio))
        if vecchio_vincolo:
            ddl = str(CreateTable(tabella).compile(dialect=dialetto)).strip()
            ddl = ddl.replace('CREATE TABLE appuntamenti', 'CREATE TABLE appuntamenti_nuova', 1)
            cur.execute('DROP TABLE IF EXISTS appuntamenti_nuova')
            cur.execute(ddl)
            vecchie = [r[1] for r in cur.execute('PRAGMA table_info(appuntamenti)')]
            comuni = ', '.join(c for c in vecchie if c in tabella.c)
            cur.execute('INSERT INTO appuntamenti_nuova (%s) SELECT %s FROM appuntamenti'
                        % (comuni, comuni))
            n = cur.execute('SELECT COUNT(*) FROM appuntamenti').fetchone()[0]
            m = cur.execute('SELECT COUNT(*) FROM appuntamenti_nuova').fetchone()[0]
            if n != m:
                raise RuntimeError('ricostruzione degli appuntamenti: %d righe invece di %d' % (m, n))
            cur.execute('DROP TABLE appuntamenti')
            cur.execute('ALTER TABLE appuntamenti_nuova RENAME TO appuntamenti')
            note.append('tabella appuntamenti ricostruita (%d righe) senza il vecchio vincolo' % n)
        n = cur.execute("UPDATE appuntamenti SET stato = 'PRENOTATO' "
                        "WHERE stato = 'CONFERMATO' OR stato IS NULL").rowcount
        if n:
            note.append('%d appuntamenti da CONFERMATO a PRENOTATO' % n)
        for indice in tabella.indexes:
            istruzione = str(CreateIndex(indice, if_not_exists=True).compile(dialect=dialetto))
            try:
                cur.execute('SAVEPOINT indice')
                cur.execute(istruzione)
                cur.execute('RELEASE indice')
            except Exception as e:
                # su database molto vecchi, senza vincolo, possono esserci
                # doppioni: resta il lucchetto applicativo, non si blocca l'avvio
                cur.execute('ROLLBACK TO indice')
                cur.execute('RELEASE indice')
                note.append('indice %s non creato: %s' % (indice.name, e))
        cur.execute("INSERT OR REPLACE INTO impostazioni (chiave, valore) VALUES "
                    "('versione_schema', '3')")
    in_transazione(motore, lavoro)
    return note


def e_campo_degenza(etichetta):
    t = (etichetta or '').lower()
    return 'degenza' in t or 'ricovero' in t or t.strip() == 'regime'


def _migra_a_6(motore):
    """Alla 1.4.3: la degenza, che le importazioni mettevano fra i campi in
    piu' della prestazione, diventa un campo vero dell'appuntamento (serve a
    contare i letti). Un valore che non si capisce ('?') passa nelle note."""
    import json
    note = []

    def lavoro(cur):
        spostati, in_nota = 0, 0
        for aid, extra, nota in cur.execute(
                "SELECT id, extra, note FROM appuntamenti WHERE extra LIKE '%egenz%' "
                "OR extra LIKE '%icover%' OR extra LIKE '%egime%'").fetchall():
            try:
                valori = json.loads(extra or '{}')
            except ValueError:
                continue
            if not isinstance(valori, dict):
                continue
            chiavi = [k for k in valori if e_campo_degenza(k)]
            if not chiavi:
                continue
            degenza, notti, aggiunta = '', None, []
            for k in chiavi:
                grezzo = str(valori.pop(k))
                letto = leggi_degenza(grezzo)
                if letto and not degenza:
                    degenza, notti = letto
                elif not letto and grezzo.strip():
                    aggiunta.append('%s: %s' % (k, grezzo.strip()))
            nota = ((nota or '') + (' ' if nota and aggiunta else '') + ' '.join(aggiunta)).strip()
            cur.execute('UPDATE appuntamenti SET degenza = ?, notti = ?, extra = ?, note = ? WHERE id = ?',
                        (degenza, notti, json.dumps(valori, ensure_ascii=False) if valori else '',
                         nota[:4000], aid))
            spostati += 1
            in_nota += bool(aggiunta)
        for pid, campi in cur.execute("SELECT id, campi_extra FROM prestazioni").fetchall():
            pezzi = [x for x in (campi or '').split(',') if x.strip()]
            restano = [x.strip() for x in pezzi if not e_campo_degenza(x.strip().rstrip('?'))]
            if len(restano) != len(pezzi):
                cur.execute('UPDATE prestazioni SET campi_extra = ? WHERE id = ?', (', '.join(restano), pid))
        if spostati:
            note.append('degenza: %d appuntamenti aggiornati%s' % (
                spostati, (', %d con un valore non chiaro passato nelle note' % in_nota) if in_nota else ''))
    in_transazione(motore, lavoro)
    return note


def _migra_a_8(motore):
    """Alla 1.7: dai codici fiscali gia' in archivio si ricavano sesso, luogo e
    data di nascita, dove mancano (un dato scritto non si tocca). Il codice
    si riscrive maiuscolo e senza spazi; uno non valido resta com'e': lo
    mostra la pagina Controllo dei codici fiscali."""
    import codice_fiscale as CF
    note = []

    def lavoro(cur):
        completati, riscritti = 0, 0
        for pid, cf, nascita, sesso, luogo in cur.execute(
                "SELECT id, codice_fiscale, data_nascita, sesso, luogo_nascita FROM pazienti "
                "WHERE codice_fiscale IS NOT NULL AND codice_fiscale != ''").fetchall():
            pulito = CF.pulisci(cf)
            if not CF.valido(pulito):
                continue
            dati = CF.leggi(pulito)
            nuovi = {}
            if pulito != cf:
                nuovi['codice_fiscale'] = pulito
                riscritti += 1
            if not nascita and dati['data_nascita']:
                nuovi['data_nascita'] = dati['data_nascita'].isoformat()
            if not sesso:
                nuovi['sesso'] = dati['sesso']
            if not luogo:
                nuovi['luogo_nascita'] = dati['luogo']
            if set(nuovi) - {'codice_fiscale'}:
                completati += 1
            if nuovi:
                cur.execute('UPDATE pazienti SET %s WHERE id = ?' % ', '.join('%s = ?' % k for k in nuovi),
                            list(nuovi.values()) + [pid])
        if completati:
            note.append('codice fiscale: %d pazienti completati con sesso, luogo e data di nascita' % completati)
        if riscritti:
            note.append('codice fiscale: %d riscritti maiuscoli e senza spazi' % riscritti)
    in_transazione(motore, lavoro)
    return note


def _prepara_tipi_turno(motore):
    """I tipi di turno con cui si comincia (mattina, pomeriggio, notte...), se la
    tabella e' vuota: in un database nuovo e alla prima apertura con la 1.8.
    Una volta sola: chi poi li cancella tutti non se li ritrova."""
    note = []

    def lavoro(cur):
        fatto = cur.execute("SELECT valore FROM impostazioni WHERE chiave = 'tipi_turno_iniziali'").fetchone()
        if fatto or cur.execute('SELECT COUNT(*) FROM tipi_turno').fetchone()[0]:
            return
        for i, (codice, nome, categoria, inizio, fine, pausa, colore) in enumerate(TIPI_TURNO_INIZIALI):
            cur.execute('INSERT INTO tipi_turno (codice, nome, categoria, ora_inizio, ora_fine, pausa_min, colore, '
                        'ordine, attivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)',
                        (codice, nome, categoria, inizio.strftime('%H:%M:%S.000000') if inizio else None,
                         fine.strftime('%H:%M:%S.000000') if fine else None, pausa, colore, i))
        cur.execute("INSERT OR REPLACE INTO impostazioni (chiave, valore) VALUES ('tipi_turno_iniziali', '1')")
        note.append('turni del personale: %d tipi di turno iniziali' % len(TIPI_TURNO_INIZIALI))
    in_transazione(motore, lavoro)
    return note


def copia_di_sicurezza(motore, motivo):
    """Copia del database prima di un aggiornamento dello schema, nella
    cartella backup accanto al database. None se il database non e' un file."""
    import sqlite3
    percorso = motore.url.database
    if motore.dialect.name != 'sqlite' or not percorso or percorso == ':memory:' \
            or not os.path.exists(percorso):
        return None
    cartella = os.path.join(os.path.dirname(os.path.abspath(percorso)), 'backup')
    os.makedirs(cartella, exist_ok=True)
    destinazione = os.path.join(cartella, 'agende-%s-%s.db' % (
        datetime.now().strftime('%Y-%m-%d_%H%M%S'), motivo))
    sorgente = sqlite3.connect(percorso)
    copia = sqlite3.connect(destinazione)
    try:
        sorgente.backup(copia)
    finally:
        copia.close()
        sorgente.close()
    return destinazione


def aggiorna_database(motore):
    """Porta il database alla versione del programma. Restituisce
    (versione trovata, colonne aggiunte, note sulle migrazioni). Si usa
    all'avvio e dopo il ripristino di un backup, che puo' essere vecchio."""
    trovata = versione_trovata(motore) if motore.dialect.name == 'sqlite' else VERSIONE_SCHEMA
    migrazioni = []
    if trovata is not None and trovata < VERSIONE_SCHEMA:
        try:
            copia = copia_di_sicurezza(motore, 'prima-della-versione-%d' % VERSIONE_SCHEMA)
            if copia:
                migrazioni.append('copia di sicurezza: %s' % copia)
        except Exception as e:
            # senza spazio o senza permessi si aggiorna lo stesso: la migrazione
            # e' in una transazione, non lascia il database a meta'
            migrazioni.append('copia di sicurezza non riuscita: %s' % e)
    Base.metadata.create_all(motore)
    aggiunte = aggiorna_schema(motore)
    if motore.dialect.name == 'sqlite':
        if trovata is None:
            with motore.begin() as c:
                c.exec_driver_sql("INSERT OR REPLACE INTO impostazioni (chiave, valore) "
                                  "VALUES ('versione_schema', '%d')" % VERSIONE_SCHEMA)
            _prepara_tipi_turno(motore)
        elif trovata < VERSIONE_SCHEMA:
            if trovata < 3:
                migrazioni += _migra_a_3(motore)
            if trovata < 6:
                migrazioni += _migra_a_6(motore)
            if trovata < 8:
                migrazioni += _migra_a_8(motore)
            if trovata < 9:
                migrazioni += _prepara_tipi_turno(motore)
            # dalla 3 alla 4 bastano tabelle e colonne nuove, gia' aggiunte sopra
            with motore.begin() as c:
                c.exec_driver_sql("INSERT OR REPLACE INTO impostazioni (chiave, valore) "
                                  "VALUES ('versione_schema', '%d')" % VERSIONE_SCHEMA)
            migrazioni.append('versione dello schema: da %d a %d' % (trovata, VERSIONE_SCHEMA))
        elif trovata > VERSIONE_SCHEMA:
            logging.warning('database della versione %d, piu nuova del programma (%d)',
                            trovata, VERSIONE_SCHEMA)
    return trovata, aggiunte, migrazioni


def crea_sessione(url=None, echo=False):
    url = url or 'sqlite:///%s' % percorso_db()
    motore = create_engine(url, echo=echo, future=True)
    trovata, aggiunte, migrazioni = aggiorna_database(motore)
    Sessione = sessionmaker(bind=motore, future=True)
    Sessione.colonne_aggiunte = aggiunte     # chi avvia sa se il database e' stato aggiornato
    Sessione.versione_precedente = trovata
    Sessione.migrazioni = migrazioni
    Sessione.motore = motore
    return Sessione


def leggi_impostazione(ses, chiave, difetto=''):
    riga = ses.get(Impostazione, chiave)
    return riga.valore if riga is not None and riga.valore is not None else difetto


def scrivi_impostazione(ses, chiave, valore):
    riga = ses.get(Impostazione, chiave)
    if riga is None:
        ses.add(Impostazione(chiave=chiave, valore=valore))
    else:
        riga.valore = valore
