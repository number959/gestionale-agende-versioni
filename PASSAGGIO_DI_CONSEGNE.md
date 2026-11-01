# Passaggio di consegne — Gestionale Agende

Questo file serve a chi riprende il progetto senza aver visto le conversazioni in cui è
nato, cioè un altro Claude o una persona. Contiene lo stato, le decisioni e il loro
perché, i vincoli, come si costruisce, si prova e si pubblica, i problemi già risolti e le
cose aperte. Si legge una volta per intero. Poi servono `CLAUDE.md` (le regole, in ognuna
delle due cartelle) e `LEGGIMI.md` (il manuale completo, con le prove e lo storico dei
difetti).

Scritto il 5 ottobre 2026 alla versione 1.7, aggiornato il 12 ottobre 2026 alla versione 1.9
(il 19 ottobre: come una sessione di Claude può pubblicare su GitHub), il 25 ottobre 2026 alla
versione 1.9.1 (l'email con qualsiasi casella, senza bisogno della verifica in due passaggi
di Gmail), il 31 ottobre 2026 alla versione **1.10** (le fasce di ogni ambulatorio), quando
Giovanni ha chiesto di continuare il lavoro con **Claude Code** sul suo PC (vedi *Passare a
Claude Code*), e il 1° novembre 2026 alla versione **1.11** (l'autoriparazione e un giro di
correzioni: vedi *La 1.11*).

## In breve

Gestionale degli appuntamenti per l'accettazione della **Clinica Posillipo** di Napoli
(Gruppo NefroCenter). Prende il posto dei file Excel con cui si gestivano le agende: stanze,
medici e turni, prenotazioni, pazienti, conferme, cassa, sala operatoria con posti letto,
email e WhatsApp ai pazienti, guide con videoguide, aggiornamenti dal programma, codice
fiscale, turni del personale (medici, infermieri, OSS e gli altri), *Dove si fa* (in quale
struttura del gruppo si fa una prestazione, per indirizzarci il paziente) e le fasce di ogni
ambulatorio (ogni turno con la sua durata delle fasce; la prestazione occupa fasce intere).

- Python, Flask e SQLite, con il server waitress su `127.0.0.1:5000`. Un solo utente, sul PC
  Windows 11 della segreteria, tutto in locale. Internet serve solo in uscita: la casella
  email della clinica (qualsiasi server SMTP), WhatsApp di Meta e gli aggiornamenti da GitHub.
- Arriva alla clinica come **un solo Setup** (Inno Setup), che contiene l'eseguibile
  PyInstaller con Python dentro. "Click e via".
- Ci sono **due varianti con le stesse funzioni**: `gestionale/` (normale) e
  `gestionale-animata/` (con icone e piccole animazioni in più). Hanno lo stesso AppId, quindi
  una si installa sopra l'altra e i dati restano.

## Le persone

- **Giovanni Silvestro**, IT del Gruppo NefroCenter, è il committente. Scrive in italiano.
  Vuole lavoro finito e verificato prima della consegna; le sue frasi, da prendere alla
  lettera:
  - "La struttura non è convenzionata, non badare alle leggi, sarà tutto in locale gestito
    da una persona."
  - "No solo la segreteria lo vede girerà su Windows 11, verrà mantenuto tutto in locale."
  - "Voglio un installer semplice con già tutto completo, click e via."
  - "Se vedi che sono gli stessi fermati e correggi, non fare 2000 errori di seguito."
  - "Non darmi cose a metà, analizza prima di darmi qualcosa."
- **Federica Corso** è all'accettazione della Clinica Posillipo ed è l'unica utente del
  programma. Le sue richieste arrivano tramite Giovanni: liste di cose da sistemare, a volte
  da WhatsApp. Il programma parla a lei: le parole devono essere semplici, mai da tecnico.
- Nei dati di partenza (`seed.py`) e in alcuni testi ci sono medici veri della clinica: il
  Dr. Galasso (endoscopia, con l'email di preparazione già pronta) e la Dr.ssa Lippiello. Le
  email sono partite finora dalla Gmail della clinica, medicinamigliorenapolisrl@gmail.com
  (`servizi.EMAIL_POSILLIPO`, che è anche l'email della struttura); dalla 1.9.1 va bene
  qualsiasi casella, e per non dipendere dalla verifica in due passaggi di Gmail è consigliata
  una casella del sito (vedi *Cose aperte*).

## Dove sta ogni cosa

| Cosa | Dove |
|---|---|
| Il codice, le prove, la documentazione | Questo repository (privato): `gestionale/`, `gestionale-animata/` |
| Le versioni pubblicate | GitHub, progetto **pubblico** `number959/gestionale-agende-versioni`: contiene solo le "Releases". Il programma legge `…/releases/latest/download/aggiornamento.json` |
| Il programma installato | Sul PC della segreteria, in `%LOCALAPPDATA%\Programs\Gestionale Agende` |
| I dati veri | Solo sul PC della clinica: `%LOCALAPPDATA%\GestionaleAgende\agende.db`, il registro `gestionale.log` e le copie in `backup\` |
| Il database delle prestazioni del gruppo | Un file Excel di Giovanni (alla 1.9 la versione 8, sei strutture, 729 prestazioni): non nel repository; si carica dal programma, *Configura → Strutture del gruppo* |

I dati veri non entrano **mai** nel repository, nelle prove, nelle immagini o nei video
della guida, né nei file consegnati. Le prove usano nomi inventati (Fintini, Esempietti,
Provolo, Testabianca, Fittizi, Esempio; email `@example.com` o `@example.it`). Se Giovanni
manda file veri (agende Excel, schermate) per capire un problema, si usano solo per capire,
fuori dal repository. Prima di ogni consegna, con i file veri a portata di mano (fuori dal
repository):

```
python gestionale/strumenti/cerca_dati_veri.py <file veri .xlsx/.csv…> --cartella gestionale \
  --cartella gestionale-animata --cartella . --ammessi lippiello,galasso,3339876543,3331234567
```

Deve finire con «Niente di grave trovato»; le parole «da guardare a occhio» devono essere
intestazioni, prestazioni o parole normali. 3339876543 e 3331234567 sono i numeri
d'esempio dei fogli istruzioni di due agende, usati anche nei dati di prova. Con questo
controllo, alla 1.7, sono venuti fuori tre frammenti delle agende vere rimasti dalla 1.4.1
negli esempi dell'importazione (un nome di battesimo raro, uno scritto male e un cognome,
già con i cognomi cambiati): sostituiti con nomi inventati. Alla 1.8, con un'agenda vera
arrivata dopo, uno di quei nomi inventati (l'esempio di cognome con «De») è risultato
uguale a un nome vero: cambiato di nuovo, senza scrivere quello vero da nessuna parte.
Anche i database dei Windows finti delle prove (sotto) vanno trattati come dati veri. Alla
1.9 va passato al controllo anche il database delle prestazioni del gruppo: i nomi delle
sue strutture non si scrivono nei file del progetto (prove, prova, immagini e video usano le
strutture inventate di `strumenti/catalogo_prova.py`).

## Stato alla consegna

- **Versione 1.11**, in lavorazione sul ramo `ccr-07f8e160-7j5lup` del progetto pubblico
  `number959/gestionale-agende-versioni` (scelta di Giovanni del 1° novembre: il codice sta lì,
  non in un progetto privato). Porta **l'autoriparazione** e **40 difetti corretti** trovati con una
  revisione del codice per parti, ciascuno riprodotto da un controllo indipendente prima di
  correggerlo e con una prova che fallisce sul codice della 1.10. Tutte le prove sono verdi nelle
  due cartelle (vedi *La 1.11* per i numeri e per cosa resta da fare prima di pubblicarla).
- **Versione 1.10**, pubblicabile: **le fasce di ogni ambulatorio**. Ogni turno può avere la sua
  durata delle fasce (*Configura → Anagrafiche*, il turno, *Durata delle fasce*); la prestazione
  occupa le fasce intere che tocca, la griglia e l'agenda del medico le mostrano a righe fitte
  con l'ora in ogni fascia libera, prima disponibilità e Sposta le seguono, un orario a metà
  fascia si salva con un avviso, gli appuntamenti già presi restano (e salvando il turno il
  programma dice quanti non stanno nelle fasce nuove). Senza fasce proprie tutto come nella
  1.9.1. Il database passa allo schema 11 (una colonna nuova nei turni, vuota). Tutte le prove
  sono verdi (973 prove, 2550 casi generati, 382 controlli nel browser nella normale e 449
  nell'animata); eseguibile e due Setup costruiti e provati in Wine: «Aggiorna adesso» dalla
  1.9.1 installata alla 1.10 (14 controlli su 14, dati identici), la 1.10 animata sopra la 1.9.1
  animata, le fasce provate sull'eseguibile dal modulo del turno alla griglia, primo avvio senza
  dati con un turno a fasce da 20 e una prenotazione rifiutata a metà fascia.
- La **1.9.1** (dentro la 1.10): **l'email con qualsiasi casella**. In *Configura → Email e
  WhatsApp* si sceglie il tipo di casella (quella del sito della clinica, consigliata; Aruba;
  Gmail; un altro server) e il programma propone server, porta e sicurezza, con le istruzioni
  di quel tipo; c'è il campo del nome utente per i fornitori che ne danno uno diverso
  dall'indirizzo e la spunta per un server della rete interna senza password; se un'email non
  parte, il messaggio dice cosa correggere, e salvando il programma avvisa già delle scelte che
  di solito non vanno. La Gmail già collegata continua a funzionare com'è. Provata alla sua
  consegna (25 ottobre) anche sull'eseguibile: «Aggiorna adesso» dalla 1.9 vera, l'invio delle
  email con finti server di posta (SSL, STARTTLS, senza password, errori spiegati).
- La **1.9** (dentro la 1.10): **Dove si fa** (menu Dove si fa, tasto D): si scrive la
  prestazione come la dice il paziente e si vedono le strutture del gruppo dove si fa; la
  scheda della struttura ha recapiti, mappa, orari e il messaggio già scritto per il paziente
  (copia, WhatsApp, email, stampa); il paziente si sceglie dalla pagina o dalla sua scheda; i
  pazienti indirizzati vanno in un registro (Excel, Statistiche). Il database delle
  prestazioni del gruppo (l'Excel con una X per struttura) si carica da *Configura →
  Strutture del gruppo* con l'anteprima di cosa cambia: **va caricato dalla clinica**, il
  file vero non è nel Setup; i recapiti delle strutture si scrivono lì. Tutte le prove sono
  verdi; eseguibile e due Setup costruiti e provati in Wine: aggiornamento dalla 1.8.1 con 81
  appuntamenti, primo avvio senza dati, il database delle prestazioni caricato
  sull'eseguibile, «Aggiorna adesso» dalla 1.9 a una 1.9.1 di prova.
- La **1.8** (dentro la 1.9): i **turni del personale** (menu Turni: medici, infermieri, OSS,
  tecnici, accettazione e ausiliari nel mese, nella settimana e nel giorno a ore; turni
  scritti con un clic o con il codice da tastiera come in un foglio di calcolo, Ctrl+Z e
  Ctrl+Y; schema che si ripete, copia della settimana, coperture minime, controllo delle
  sovrapposizioni e dei riposi, ore contro il contratto, notti, festivi, assenze; stampa ed
  Excel), «In servizio oggi» nella pagina Oggi, la **registrazione del numero WhatsApp** dal
  programma (PIN a sei cifre, mai salvato) e gli errori di Meta spiegati in parole semplici,
  le tendine sempre sopra la pagina (la finestra «Stampa e scarica» coperta che aveva
  segnalato Federica: era stata corretta come 1.7.1, mai pubblicata, ed è dentro la 1.8).
- **Pubblicazione su GitHub**: da fare a mano, da Giovanni o da una sessione che abbia
  accesso in scrittura al progetto delle versioni. Nemmeno le sessioni della 1.8 e della 1.9
  l'avevano ("GitHub access to this repository is not enabled for this session"): l'account
  GitHub collegato era `number959`, ma alla sessione non era collegato nessun progetto e
  la sessione non aveva modo di collegarne. Perché una sessione pubblichi da sola servono
  l'app Claude installata su GitHub sui due progetti
  (https://github.com/apps/claude/installations/new, *Only select repositories*:
  `gestionale-agende` e `gestionale-agende-versioni`) e la sessione aperta con i due
  progetti scelti, per esempio da
  https://claude.ai/code?repositories=number959/gestionale-agende,number959/gestionale-agende-versioni
  (come si fa la release da lì: *Pubblicare una versione*). Una sessione nuova parte da
  zero: il codice lo prende dal progetto privato, che quindi deve esserci. L'11 ottobre 2026
  il progetto delle versioni era ancora **vuoto** (né file né release) e il 19 ottobre
  l'indirizzo pubblico del file delle versioni rispondeva ancora 404: serve prima un file,
  per esempio un README, poi la release `v1.10` con i quattro file (vedi *Pubblicare una
  versione*); se la 1.8, la 1.9 e la 1.9.1 non sono state pubblicate nel frattempo, si saltano:
  la 1.10 le contiene. Dal PC di Giovanni, con Claude Code, il `gh` vero dopo `gh auth login`
  basta (vedi *Passare a Claude Code*).
  Appena pubblicata si controlla che l'indirizzo pubblico risponda.
- **Alla clinica** potrebbe esserci ancora la 1.5, che non ha «Aggiorna adesso». La prima
  volta il Setup della 1.10 si avvia a mano sopra il vecchio: non si disinstalla e i dati
  restano. Dalla 1.6 in poi gli aggiornamenti arrivano dal programma, ogni sei ore o con
  «Controlla adesso».
- La 1.6 e la 1.7 non sono mai state pubblicate: la prima release su GitHub sarà la 1.10
  (o una precedente, se nel frattempo pubblicata).
- Il **codice** (questo repository) è nel pacchetto `gestionale-agende.bundle` consegnato
  con la 1.10 dentro lo zip per Claude Code (storia: un commit per versione dalla 1.7 alla
  1.10, con i tag `v1.7`, `v1.8`, `v1.9`, `v1.9.1` e `v1.10`): va messo in un progetto
  **privato** su GitHub (vedi *Consegnare file a Giovanni* e *Passare a Claude Code*).

## Storia in breve

Il dettaglio di ogni versione è in `LEGGIMI.md` (paragrafi *Novità della …* in cima e
*Difetti trovati e corretti* in fondo, giro per giro).

| Versione | Cosa ha portato |
|---|---|
| 1.0 – 1.2 | Griglia del giorno per stanza, medici e turni ricorrenti, prenotazioni, export Excel del planning, nome, logo e colori della struttura |
| 1.3 | Schede paziente con storico, stati dell'appuntamento, conferme, aggiornamento del database con copia di sicurezza |
| 1.4 – 1.4.2 | Importazione da Excel e CSV, cassa e listino, lista d'attesa, cose da fare, documenti, moduli da stampare, appunti da confermare, tema scuro |
| 1.4.3 – 1.4.4 | Pagina Oggi, sala operatoria (checklist, lista operatoria, posti letto, giorni di sala dei chirurghi), menu a gruppi e guida sullo schermo |
| 1.4.5 – 1.4.6 | Correzioni da una revisione esterna del codice: le pagine accettano moduli solo da sé stesse, il server risponde solo a 127.0.0.1 |
| 1.5 | Email e WhatsApp ai pazienti (email automatiche per medico, promemoria del giorno prima), nascita, codice fiscale e indirizzo, logo nuovo *Longevity Institute*, caratteri Manrope e Inter |
| 1.6 | Videoguide per ogni guida, «Aggiorna adesso» (Setup scaricato, controllato e installato dal programma), pagina delle Novità |
| 1.7 | Codice fiscale controllato e calcolato, luoghi di nascita, controllo dell'archivio, indirizzo GitHub predefinito |
| 1.8 | Turni del personale (mese, settimana, giorno a ore, schema, coperture, controlli dei riposi, Excel), «In servizio oggi», registrazione del numero WhatsApp dal programma, tendine sempre sopra la pagina (la 1.7.1 mai pubblicata) |
| 1.9 | Dove si fa: ricerca delle prestazioni nelle strutture del gruppo (sigle, plurali, correzioni), scheda della struttura con recapiti e messaggio per il paziente (copia, WhatsApp, email, stampa), registro dei pazienti indirizzati, database delle prestazioni importato dall'Excel del gruppo con l'anteprima |
| 1.9.1 | L'email con qualsiasi casella: tipo di casella con server, porta e sicurezza proposti (sito della clinica, Aruba, Gmail, altro server), nome utente diverso dall'indirizzo, server senza password, errori che dicono cosa correggere |
| 1.10 | Le fasce di ogni ambulatorio: ogni turno con la sua durata delle fasce, la prestazione occupa fasce intere (blocco), griglia a righe fitte con l'ora in ogni fascia libera, prima disponibilità e Sposta sulle fasce, avviso per un orario a metà fascia e per gli appuntamenti già presi che non stanno nelle fasce nuove |
| 1.11 | L'autoriparazione (il database controllato e riparato da solo senza perdere dati, un gestionale solo, il programma bloccato che si chiude e si riapre, i lavori in sottofondo che ripartono, le copie ogni due ore, la pagina Controllo del programma) e 40 difetti corretti nei messaggi, nell'agenda, nelle schede, nell'importazione, nei turni del personale, nelle copie di sicurezza e nelle pagine |

Idee messe da parte da Giovanni: un **PIN** per aprire il programma ("ignora il PIN": non
fatto, non richiesto per ora).

## Le decisioni e il loro perché

- **Solo locale, solo 127.0.0.1, una persona sola.** Niente account, niente rete. La
  sicurezza contro i siti aperti nello stesso browser è nella 1.4.6: Origin, Referer e
  Sec-Fetch-Site sono controllati, e il server risponde solo se il nome è `127.0.0.1` o
  `localhost`.
- **SQLite con il giornale classico, non il WAL.** Così `BACKUP.bat`, che copia un file solo,
  non perde niente. Il database non va mai su una cartella condivisa: SQLite su SMB lo
  corrompe.
- **Un lucchetto per tutti i salvataggi** (`LUCCHETTO`). Con waitress le richieste sono
  concorrenti. In `invii.py` il lucchetto si tiene solo per scrivere nella coda, mai mentre
  un'email parte.
- **Un difetto nei messaggi non fa mai perdere una prenotazione**: c'è un try/except intorno
  a `invii.dopo_salvataggio`.
- **Il database si aggiorna da solo** (`modelli.aggiorna_database`). Prima viene la copia di
  sicurezza (`backup\agende-…-prima-della-versione-N.db`), poi le colonne e le tabelle nuove
  in una transazione; i dati esistenti non si toccano. Lo schema è alla versione 10 (dalla
  1.8 la 9: le tabelle dei turni e, una volta sola, i dieci tipi di turno di partenza; dalla
  1.9 la 10: le quattro tabelle di Dove si fa).
- **Aggiorna adesso.** Il Setup parte con `cmd /c start`, così non è figlio del programma,
  con `/SILENT` e con l'**ambiente pulito**: senza le variabili `_PYI_*` dell'eseguibile, il
  programma riaperto si fermerebbe con "Security validation failure". La voce `[Run]` con
  `Check: WizardSilent` in `installer.iss` riapre il programma. Tutto quello che arriva da
  fuori si controlla (dimensione, impronta SHA-256, "MZ"), e si accettano solo https o
  cartelle.
- **Il codice fiscale ha un solo controllo**: quello del programma (`codice_fiscale.py`),
  chiesto dalla pagina mentre si scrive. Non c'è una seconda copia in JavaScript che può
  divergere. Un codice sbagliato non si salva; uno che non corrisponde ai dati si salva con
  un avviso, perché fa fede la tessera. Un codice calcolato non sostituisce mai quello già
  nella scheda e non si usa per cercare doppioni: per l'omocodia il codice vero di una
  persona può essere diverso da quello calcolato, e quello calcolato può essere di un'altra.
- **I turni del personale hanno le regole in un posto solo**, `personale.py`: due turni della
  stessa persona che si sovrappongono (anche con la notte del giorno prima) non si salvano,
  riposi e assenze occupano tutto il giorno, meno di 11 ore di riposo si segnalano soltanto
  (decide la segreteria). La pagina (`static/turni.js`) manda una modifica alla volta e
  ridisegna quello che il programma risponde; la risposta porta lo stato di prima delle
  celle cambiate, ed è così che funzionano Ctrl+Z e Ctrl+Y (*ripristina* è tutto o niente).
  Il disegno della cella esiste due volte, nel modello `_personale_cella.html` e in
  `chipCella()` di `turni.js`: si cambiano insieme, e le prove nel browser lo controllano.
  Le leggi sul lavoro non si controllano (vincolo di Giovanni): solo buon senso.
- **Dove si fa legge l'Excel del gruppo così com'è** (Branca, Prestazione, Sinonimi, una
  colonna per struttura con le X, Note con le sigle delle strutture), senza chiedere a
  nessuno di cambiarlo: il foglio giusto, le colonne di struttura e le note «da confermare»
  li riconosce il programma, e l'anteprima mostra cosa cambia prima di importare. Una
  versione nuova del file si carica sopra la vecchia: le prestazioni tengono il loro id per
  nome, i recapiti scritti nel programma restano (il foglio facoltativo *Strutture* riempie
  solo quelli che mancano), il registro copia i nomi e resta leggibile. La ricerca è fatta
  per come si parla allo sportello (RM, TAC, eco, «lastra», plurali, parole scritte male)
  e si prova contro un oracolo scritto a parte. I risultati e la scheda sono un solo
  disegno (modelli Jinja usati sia dalla pagina sia dai pezzi chiesti mentre si scrive),
  per non avere due copie che divergono come succedeva con le celle dei turni. Il registro
  si riempie da solo con WhatsApp, email e stampa (con Annulla): è per i conti del gruppo,
  non deve costare lavoro in più.
- **WhatsApp: il PIN non si salva mai.** «Registra il numero» lo manda a Meta
  (`POST /{id del numero}/register`) e lo dimentica, anche nel registro; Meta accetta al
  massimo 10 registrazioni in 72 ore per numero.
- **L'email va con qualsiasi casella SMTP, senza OAuth** (1.9.1). Gmail accetta i programmi
  esterni solo con la password per le app, che vuole la verifica in due passaggi, o con
  l'accesso con Google (OAuth). OAuth con un account Gmail personale vorrebbe un'app
  «External» registrata da Google: in prova l'accesso scade ogni 7 giorni, pubblicata senza
  verifica mostra gli avvisi di Google e ha un tetto di 100 utenti; Outlook.com non accetta più
  la password e Microsoft ha annunciato che la spegne anche per Microsoft 365 dalla fine del
  2026. Per questo la casella consigliata è quella del sito della clinica (cPanel e simili),
  che vuole solo indirizzo e password. I tipi di casella (`invii.CASELLE`) servono solo a
  proporre server, porta e sicurezza e a scegliere istruzioni e consigli: si salva quello che
  c'è nei campi, quindi le impostazioni della 1.9 valgono senza migrazione (il tipo si ricava
  dal server). Gli errori da correggere (password, SSL sulla porta sbagliata, certificato di
  un altro nome) fermano subito il messaggio; quelli di rete si riprovano.
- **Risorse di terze parti: poche e dentro il programma**, che gira senza internet: le icone
  Lucide (licenza ISC, quelle derivate da Feather MIT) scritte in `templates/_icone.html`, i
  colori dei turni presi dalle scale di Radix Colors (MIT), i caratteri Inter e Manrope
  (OFL) e, nell'animata, lottie-web (MIT) per le animazioni degli stati vuoti. I testi delle
  licenze sono in `static/icone/LICENZE.txt` e accanto ai caratteri. Niente librerie di
  animazione: bastano le animazioni CSS, che si spengono con «riduci movimento».
- **Le fasce sono del turno, non della clinica né della prestazione** (1.10). Federica aveva
  segnalato, tramite Giovanni, l'«incompatibilità tra durata prestazione e programmazione
  ambulatorio scadenzata con blocco e unica per tutta la clinica»: fino alla 1.9.1 c'era una
  sola misura di fascia per struttura (30 minuti), mentre ogni ambulatorio ha la sua
  programmazione (visite ogni 20, endoscopie ogni 15) e una prestazione deve bloccare le fasce
  intere. Fra le soluzioni proposte Giovanni ha scelto le **fasce per turno**: ogni turno
  (medico, stanza, giorno, orario) può avere la sua durata, dall'ora di inizio del turno; gli
  altri turni restano con quella della struttura. Un appuntamento occupa tutte le fasce che
  tocca: una prestazione più corta della fascia la blocca intera («mai buchi da 10 minuti
  prenotabili per sbaglio»), una più lunga ne prende più d'una. Il blocco vale per la stanza;
  il medico conta con gli orari veri. Un orario a metà fascia si accetta con un avviso (i
  ritardi e gli esami infilati esistono): rifiutarlo avrebbe obbligato a cambiare le fasce per
  un caso solo. Gli appuntamenti presi prima delle fasce non si spostano da soli (sarebbe
  cambiare l'orario detto al paziente): restano, salvando il turno il programma dice quanti non
  stanno nelle fasce nuove, e modificandoli contano solo le fasce nuove che prenderebbero, così
  una nota o un cambio di medico non vengono mai rifiutati. La griglia ha una sola colonna delle
  ore per tutte le stanze: le righe diventano il massimo comun divisore delle fasce (con 30 e
  15, righe da 15; con 30 e 20, da 10), alte in proporzione al tempo. Senza turni a fasce
  proprie il programma deve restare identico alla 1.9.1, e `prove_110.py` lo controlla con le
  funzioni della 1.9.1 copiate e ferme dentro la prova.
- **Le prove servono quanto il codice.** Ogni difetto trovato diventa una prova che lo
  riproduce. Le prove nuove si verificano introducendo apposta un errore nel codice (un
  "mutante") e controllando che la prova lo segnali.

## Come si lavora

1. Si modifica la versione **normale** (`gestionale/`).
2. Si portano i file comuni nell'animata: `python strumenti/allinea_animata.py --copia`.
   Senza `--copia` dice solo cosa è diverso. I file propri di ogni versione si adattano a
   mano: `CREA_SETUP.bat`, `LEGGIMI.md`, `installer.iss`, `templates/base.html`,
   `templates/griglia.html`, `templates/impostazioni.html`. Solo l'animata ha `static/animazioni*`,
   `prove_animazioni.py` e `prove_icone_animate.py`.
3. Prove in tutte e due le cartelle (vedi *Prove*).
4. Se cambia l'aspetto di una pagina con una guida: immagini e video rigenerati in tutte e due
   le versioni, sul server di prova (vedi *Guide*).
5. Documentazione: `LEGGIMI.md` in tutte e due le cartelle (sono diversi solo nelle parti
   sull'animazione), `CLAUDE.md` e questo file se cambia qualcosa di grosso.

Nel lavorare con Giovanni:

- Prima di consegnare si prova tutto, anche l'eseguibile e il Setup quando cambia la
  versione.
- Se un errore si ripete, ci si ferma e si corregge la causa, invece di insistere.
- Si dice chiaramente cosa non si è potuto fare e perché; per esempio "da qui non posso
  scrivere su GitHub".

## Prove

In ciascuna cartella:

```
python strumenti/tutte_le_prove.py                              # tutte quelle senza browser, circa 5 minuti
python strumenti/demo.py --porta 5001                           # in un'altra finestra: dati di prova
python strumenti/tutte_le_prove.py --browser http://127.0.0.1:5001   # tutte, anche nel browser
python strumenti/tutte_le_prove.py --solo prove_17,campagna     # solo alcune
```

In totale alla 1.11: 1121 prove e 2550 casi generati (`campagna.py`), più i controlli nel browser
nella normale e nell'animata (alla 1.10: 382 e 449; alla 1.11 nove in più in `prove_18_browser.py`) (che ha anche `prove_animazioni.py` e
`prove_icone_animate.py`). Le prove nel browser (Playwright con Chromium) salvano dati:
sempre sul server di prova, mai su quello vero; `prove_16_browser.py` cambia l'indirizzo
degli aggiornamenti e per questo il giro la lancia per ultima. Ogni prova si può anche
lanciare da sola (`python prove_17.py`, `python prove_17_browser.py http://127.0.0.1:5001`).

Alcune delle prove più vecchie escono con codice 0 anche quando una prova non va: conta la
riga finale («0 da sistemare»), ed è quella che legge `tutte_le_prove.py`. Ogni giro ha la
sua cartella temporanea, quindi le due cartelle si possono provare insieme. `prove_17.py`
confronta il codice fiscale con il pacchetto indipendente python-codicefiscale
(`pip install python-codicefiscale`); senza il pacchetto quelle prove si saltano e lo
dicono. Tutto verde alla 1.10 e alla 1.9.1 su Python 3.13 (alla 1.9 su 3.11 e 3.14). `prove_191.py` prova
l'email con lo stesso finto server di posta di `prove_15.py` (STARTTLS, SSL e accesso veri su
127.0.0.1) e con un finto `smtplib` per gli errori che un server locale non sa fare.
`prove_19.py` confronta la ricerca di Dove si fa con un oracolo scritto a parte su 1200
prestazioni inventate (ogni risultato contiene tutte le parole cercate, ogni prestazione si
trova con l'inizio delle sue parole). `prove_110.py` prova le fasce dei turni in tre modi: senza
fasce proprie griglia, agenda del medico, controlli, avvisi e prima disponibilità devono essere
identici a quelli della 1.9.1 (le cinque funzioni della 1.9.1 sono copiate nella prova e non si
toccano più; una prova controlla con git che la copia sia fedele e che le funzioni che usano
non siano cambiate); con le fasce proprie colonne e celle si confrontano con un calcolo minuto
per minuto e riga per riga, i controlli con le fasce toccate calcolate a parte, la prima
disponibilità con il controllo vero ora per ora; e poi i casi scritti a mano. Con
`PROVE_GIRI=500` usa più giorni inventati (predefinito 120); su Linux è passata anche così.
Finora tutte le prove sono state lanciate solo su Linux: su Windows le prove con i certificati
(`prove_15.py`, `prove_16.py`, `prove_191.py`) cercano il comando `openssl`, che c'è nella
riga di comando di Git for Windows.

## Guide: immagini e video

Le guide sono scritte una volta in `guida.py` e diventano quattro cose: la pagina Aiuto,
la guida sullo schermo, il PDF da stampare e la videoguida. Quando una pagina cambia
aspetto, sul server di prova appena avviato:

```
python strumenti/genera_immagini_guida.py http://127.0.0.1:5001 [cartella]
python strumenti/genera_video_guida.py http://127.0.0.1:5001 slug1 slug2 ...    # serve ffmpeg con libvpx-vp9
```

Tutte e due devono finire senza "non trovati". Si fa in tutte e due le versioni: le immagini
dell'animata hanno le sue icone. `prove_guida.py` controlla che ogni guida abbia immagine e
video. Il PDF della guida (`/aiuto/stampa` in A4, circa 43 pagine):
`python strumenti/genera_pdf_guida.py http://127.0.0.1:5001`, che scrive
«Guida Gestionale Agende <versione>.pdf» (alla 1.10, 48 pagine).

Le pagine fotografate usano i segnaposto `{martedi}` (il martedì di questa settimana),
`{domani}` e `{oggi}`, come i dati di `strumenti/demo.py`, che sono costruiti attorno a oggi.
Attenzione al giorno in cui si rigenera: la guida *Leggere la griglia del giorno* fotografa
`{domani}`, e di sabato domani è domenica, senza turni (i passi non trovano le fasce libere).
Alla 1.10, rigenerate di sabato, sono state rifatte solo le guide delle pagine cambiate
(*Le fasce di ogni ambulatorio*, nuova, *Stampare la giornata* e *Aggiungere un medico e i
suoi turni*). Il martedì della prova la sala endoscopia ha le fasce da 15 minuti: è il giorno
che mostra le fasce dei turni. «Mostrami sullo schermo» della guida sulle fasce apre il primo
giorno, da oggi, con un turno a fasce proprie (segnaposto `FASCE` in `guida.py`).

## Costruire e provare l'installatore

**Su Windows** (Python 3.10–3.14 e Inno Setup 6), in ciascuna cartella: `CREA_EXE.bat`,
poi `CREA_SETUP.bat`. In `Output` ci sono il Setup e il file delle versioni.

**Su Linux, con Wine** (per esempio in una sessione nel cloud), è il modo con cui sono
state provate tutte le versioni:

```
bash strumenti/wine/prepara.sh                 # una volta: Wine a 64 e 32 bit, Python per Windows, Inno Setup
bash strumenti/wine/costruisci.sh [cartella]   # CREA_EXE.bat e CREA_SETUP.bat dentro Wine; il risultato in Output/
bash strumenti/wine/installa.sh Output/GestionaleAgende-setup.exe    # installa senza domande e riapre su :5000
python strumenti/prove_installato.py           # versione, guide e video, aggiornamenti, codice fiscale, turni, WhatsApp
bash strumenti/wine/ferma.sh
```

«Aggiorna adesso» per intero si prova così:

1. Si costruisce la stessa versione con un altro numero: in una copia della cartella si
   cambiano `comune.py` e `installer.iss` e si aggiunge una voce in `novita.py`.
2. Si mettono il suo Setup e il file delle versioni in `C:\aggiornamenti-prova` del
   Windows finto.
3. Si lancia:

```
python strumenti/prova_aggiorna_adesso.py 'C:\aggiornamenti-prova' 1.9.2 "$WINEPREFIX/drive_c/users/$(id -un)/AppData/Local/GestionaleAgende"
```

L'email sul programma installato (dalla 1.9.1), con finti server di posta su 127.0.0.1:

```
python strumenti/prova_email_installato.py --certificato DIR --database "$CARTELLA_DATI/agende.db"
```

Cambia le impostazioni email del programma installato: solo nel Windows finto. Per gli invii
con SSL e STARTTLS riusciti il programma va avviato con `SSL_CERT_FILE` che punta al
certificato scritto in `DIR` (visto da Windows, con `Z:` davanti); senza, quelle due prove lo
dicono e le altre valgono lo stesso.

Alla 1.7 così, partendo da un Windows finto nuovo: `prepara.sh`, le due versioni costruite,
la 1.7 installata sopra la 1.6 con 81 appuntamenti (copia di sicurezza, schema da 7 a 8,
dati identici), 16 controlli di `prove_installato.py` a posto sulla normale e
sull'animata, «Aggiorna adesso» dalla 1.7 a una 1.7.1 di prova con 14 controlli su 14.

Alla 1.8 così: le due versioni costruite nello stesso Windows finto; la 1.8 installata sopra
la 1.7.1 con 81 appuntamenti (copia di sicurezza identica al database di prima, schema da 8
a 9, dieci tipi di turno, tutte le tabelle di prima identiche riga per riga); la 1.8 animata
sopra la 1.7 animata; 25 controlli di `prove_installato.py` a posto su tutte e due e su un
database nuovo; sull'eseguibile, nel browser, un turno scritto da tastiera, annullato e
rifatto; «Aggiorna adesso» dalla 1.8 a una 1.8.1 di prova con 14 controlli su 14.

Alla 1.9 così: le due versioni costruite nello stesso Windows finto; la 1.9 installata sopra
la 1.8.1 con 81 appuntamenti (copia di sicurezza identica al database di prima, schema da 9 a
10, le quattro tabelle di Dove si fa, tutte le tabelle di prima identiche riga per riga); la
1.9 animata sopra la 1.8 animata; 31 controlli di `prove_installato.py` a posto su tutte e
due e su un database nuovo; sull'eseguibile, il database delle prestazioni inventato
caricato dalla pagina e provato (anteprima, importazione con la copia di sicurezza, ricerca,
scheda, registro); «Aggiorna adesso» dalla 1.9 a una 1.9.1 di prova con 14 controlli su 14,
con il database delle prestazioni ancora lì dopo.

Alla 1.9.1 così: le due versioni costruite nello stesso Windows finto; in un Windows finto nuovo
la 1.9 normale installata con il Setup consegnato, con il database inventato di
`strumenti/demo.py` della 1.9 (46 appuntamenti, 30 pazienti, 8 medici, turni, regole) e la
casella collegata con il modulo della 1.9 a un finto server di posta; «Aggiorna adesso» dalla
1.9 alla 1.9.1 con 14 controlli su 14, le 28 tabelle identiche riga per riga dopo, la prova
dell'email partita con la password salvata dalla 1.9; la 1.9.1 animata installata con il Setup
sopra la 1.9 animata, stessi risultati; 34 controlli di `prove_installato.py` a posto su
tutte e due e su un database nuovo; `prova_email_installato.py` con 12 controlli su 12 su
tutte e due.

Alla 1.10 così: le due versioni costruite nello stesso Windows finto; la 1.9.1 normale installata
nelle prove della 1.9.1 (con i suoi 46 appuntamenti inventati e 27 turni) aggiornata con
«Aggiorna adesso» alla 1.10: 14 controlli su 14, copia *prima della versione 11* identica al
database di prima, le 28 tabelle identiche riga per riga dopo (i turni con la colonna nuova
vuota); la 1.10 animata installata con il Setup sopra la 1.9.1 animata, stessi risultati; 40
controlli di `prove_installato.py` a posto su tutte e due e su un database nuovo; sull'eseguibile,
nel browser, un turno passato a fasce da 20 e la sua griglia (7 controlli), e sul database nuovo
il primo giorno con un turno a fasce da 20, una visita da 30 minuti su due fasce e una
prenotazione alle 9:30 rifiutata (7 controlli). Gli script delle due prove sull'eseguibile non
sono nel repository (erano nella cartella di lavoro della sessione): le stesse cose le fanno
`prove_110_browser.py` e `prove_110.py` sul programma di prova.

Il programma installato nel Windows finto ha i suoi dati in
`$WINEPREFIX/drive_c/users/<utente>/AppData/Local/GestionaleAgende`. Sono dati delle prove,
in parte importati dalle agende vere: mai nelle immagini né nei file consegnati.

Cose imparate con Wine, da non riscoprire:

- **ISCC di Inno Setup è a 32 bit.** Il Windows finto va creato dopo aver installato
  `wine32`, altrimenti non ha i 32 bit; `prepara.sh` lo fa nell'ordine giusto.
- **Il Python dentro Wine vuole un terminale**, altrimenti si ferma con "can't initialize sys
  standard streams". Per questo gli script lanciano tutto dentro `script -qec "…" /dev/null`.
- I `.bat` finiscono con `pause`: gli script gli passano qualche Invio.
- Dietro un proxy che controlla i certificati, pip dentro Wine vuole il certificato visto da
  Windows (`PIP_CERT=Z:\percorso\del\file`): lo fa `ambiente.sh`.
- Per chiudere i processi si usa il nome del processo (`ferma.sh`), mai
  `pkill -f` con un testo che c'è anche nella propria riga di comando: chiuderebbe la shell
  stessa.
- **Wine 9 non ha `CopyFile2`**, una funzione di Windows che Python 3.14.8 usa in
  `shutil.copy2`: senza rimedio `CREA_EXE.bat` si ferma già creando l'ambiente isolato
  ("unimplemented function KERNEL32.dll.CopyFile2"). `prepara.sh` mette nel Python del
  Windows finto un `sitecustomize.py` che la toglie, e alla fine prova una copia. Il
  programma non usa `shutil.copy2`, e sul PC vero la funzione c'è.
- L'ora dentro Wine può differire di un'ora da quella di Linux: è il fuso, non un difetto.

## Pubblicare una versione

1. Il numero nuovo va in `comune.py` (`VERSIONE`) e in `installer.iss` (`#define Versione`)
   di tutte e due le cartelle. In `novita.py` va una voce per ogni novità, con la guida
   che la spiega.
2. Prove, guide, documentazione.
3. Eseguibile e Setup di tutte e due le versioni, provati.
4. La release nel progetto delle versioni, con il tag `vX.Y`, contiene i quattro file
   `GestionaleAgende-setup.exe`, `aggiornamento.json`,
   `GestionaleAgende-animata-setup.exe` e `aggiornamento-animata.json`. Si fa dalla pagina
   *Releases → Create a new release* (lasciando acceso *Set as the latest release*) oppure
   con
   `gh release create vX.Y --repo number959/gestionale-agende-versioni --latest …`.
   I nomi dei file devono essere proprio questi.

   In una sessione nel cloud di Claude il `gh` è un altro (fa solo `gh api`) e il
   collegamento a GitHub rifiuta sia il push dei tag con git sia le richieste GraphQL. La
   release si crea con l'API REST, che crea anche il tag:

   ```
   gh api repos/number959/gestionale-agende-versioni/releases -f tag_name=vX.Y \
     -f name="Gestionale Agende X.Y" -f body="…" -f make_latest=true     # risponde con "id"
   curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" -H "Content-Type: application/octet-stream" \
     --data-binary @Output/GestionaleAgende-setup.exe \
     "https://uploads.github.com/repos/number959/gestionale-agende-versioni/releases/ID/assets?name=GestionaleAgende-setup.exe"
   ```

   e lo stesso per gli altri tre file. Nella sessione `$GITHUB_TOKEN` vale `proxy-injected`:
   la credenziale vera la mette il collegamento. Il 19 ottobre 2026 uploads.github.com
   risultava gestito dal collegamento, ma il caricamento non era ancora stato provato. Nel
   progetto del codice i tag si creano allo stesso modo:
   `gh api repos/number959/gestionale-agende/git/refs -f ref=refs/tags/vX.Y -f sha=$(git rev-parse HEAD)`.
5. Controllo:
   `curl -sL https://github.com/number959/gestionale-agende-versioni/releases/latest/download/aggiornamento.json`
   deve dire la versione nuova, e l'impronta del Setup scaricato da lì deve essere quella
   scritta nel file.

Il programma della clinica la trova entro sei ore, o subito con «Controlla adesso».

## Consegnare file a Giovanni

In chat i file grossi non passano (circa 30 MB al massimo). Si usa
`python strumenti/consegna.py <cartella dei file> <cartella dei pezzi>`: divide i file
grossi in pezzi e scrive `RICOMPONI.bat`, che su Windows li rimette insieme e controlla
dimensione e impronta. Su GitHub invece i Setup vanno interi.

Il codice viaggia come `gestionale-agende.bundle`: un solo file di git con tutta la storia
(ramo `main`, tag `v1.7`, `v1.8`, `v1.9`, `v1.9.1` e `v1.10`). Per metterlo in un progetto **privato** su GitHub (per
esempio `number959/gestionale-agende`, creato vuoto e privato dalla pagina di GitHub, senza
README):

```
git clone gestionale-agende.bundle gestionale-agende
cd gestionale-agende
git remote set-url origin https://github.com/number959/gestionale-agende.git
git push -u origin main --tags
```

Con un bundle nuovo, nella stessa cartella: `git pull ../gestionale-agende.bundle main`,
poi `git push origin main --tags`. Il progetto delle versioni resta un altro, pubblico, con
le sole release: lì il codice non va.

## Passare a Claude Code

Il 31 ottobre 2026 Giovanni ha chiesto di continuare il lavoro con Claude Code, sul suo PC
Windows, invece che nella sessione di Claude nel cloud dove il progetto è nato. Gli è stato
consegnato lo zip **GestionaleAgende-1.10-per-Claude-Code** (a pezzi, con `RICOMPONI.bat`), che
contiene: `LEGGIMI PRIMA - Passare a Claude Code.txt` (cosa installare: Git for Windows, Python
3.13 o 3.14, Claude Code con `irm https://claude.ai/install.ps1 | iex`, Inno Setup 6 per i
Setup; come aprire il progetto; GitHub; come pubblicare la 1.10), `PROMPT per Claude Code.txt`
(il primo messaggio da incollare), `gestionale-agende.bundle` (questo repository con la storia e
i tag fino a `v1.10`), la cartella `Setup` con i quattro file della release 1.10 e la guida PDF.

Il prompt chiede a Claude Code, nell'ordine: clonare il bundle in `gestionale-agende`, leggere
questo file e `gestionale/CLAUDE.md`, preparare Python (`python -m pip install -r
gestionale/requirements.txt playwright python-codicefiscale`, `python -m playwright install
chromium`), lanciare `python strumenti/tutte_le_prove.py` nelle due cartelle e fermarsi a
spiegare se su Windows qualcosa non va, poi riassumere lo stato e proporre i passi; niente
pubblicazioni né push senza il via di Giovanni. Claude Code legge da solo `CLAUDE.md` della
cartella in cui parte e delle cartelle sopra; quello di `gestionale/` lo carica quando lavora
lì dentro.

Su Windows non serve Wine: `CREA_EXE.bat` e `CREA_SETUP.bat` dentro ciascuna cartella. La
riga di comando di Claude Code su Windows è quella di Git for Windows (bash): gli script di
`strumenti/wine/` non servono, i `.bat` si lanciano con `cmd //c CREA_EXE.bat` o da Esplora
risorse. Per GitHub c'è il vero `gh` (`winget install GitHub.cli`, poi `gh auth login`): la
release si fa con `gh release create` come in *Pubblicare una versione*.

## La 1.11

Fatta il 1° novembre 2026 in una sessione di Claude Code nel cloud, con il bundle della 1.10. Il
lavoro è su `ccr-07f8e160-7j5lup` (un commit per blocco: autoriparazione, messaggi, agenda e
schede, importazione, turni, revisione), tutto allineato nelle due cartelle.

**L'autoriparazione** (`autoripara.py`, con la sezione *Autoriparazione* del `LEGGIMI.md` e la
regola in `CLAUDE.md`): il database controllato all'avvio e ogni mezz'ora e riparato senza perdere
niente quando i guasti sono solo negli indici, altrimenti l'ultima copia buona (il file rovinato
resta sempre in `backup\danneggiati`); un gestionale solo (lucchetto, `gestionale.pid` con il
battito del custode, `/salute`): il secondo clic sull'icona apre la pagina, un gestionale bloccato
si chiude e si riparte, uno occupato si aspetta, un programma che non è il gestionale non si
chiude mai; il programma si riavvia da solo se perde i suoi file o resta bloccato, al massimo tre
volte in un'ora; i lavori in sottofondo ripartono; le copie ogni due ore se ci sono modifiche e
accanto al database se la cartella scelta non si raggiunge; la pagina *Impostazioni → Controllo del
programma* con il diario e la guida *Il programma si ripara da solo* (con immagine e video). Una
revisione indipendente del codice nuovo ha trovato undici difetti, corretti (il più grave: una
pagina rimasta fuori dall'albero dopo una corrente saltata si riparava dicendo «senza perdere
niente»). `prove_autoriparazione.py`: 60 prove, verdi su Linux e con il Python di Windows in Wine;
25 mutanti su 25 presi.

**I difetti corretti** (40, tutti nello storico del `LEGGIMI.md`, con la prova in `prove_111*.py`):
sette nei messaggi ai pazienti (il più grave: un messaggio in attesa di riprovare arrivava
all'indirizzo del paziente di prima con il testo del paziente nuovo), cinque nell'agenda (una stanza
disattivata proposta e usata, l'anno a due cifre, la sostituzione che bloccava il turno del
sostituito, due nelle fasce intere), tre nelle schede dei pazienti (unione, omocodia, scheda
sovrascritta), dieci nell'importazione da Excel, tre nei turni del personale, sei nelle copie e
nel ripristino, sei nelle pagine e nella sicurezza (una pagina del gestionale non si mostra più dentro
la cornice di un altro sito: un sito ostile avrebbe potuto far cliccare «Disdetto»). Le prove nuove sono state lanciate anche sul codice della 1.10: falliscono.

**Le prove alla 1.11**: 25 raccolte senza browser nelle due cartelle, tutte verdi (1121 prove e
2550 casi generati), più le prove nel browser (10 raccolte nella normale, 12 nell'animata, tutte
verdi; `prove_18_browser.py` è passato da 46 a 55 controlli).

**Da fare prima di pubblicare la 1.11** (il codice è pronto, i Setup vanno rifatti dall'ultimo
commit e riprovati: il Setup della 1.11 provato in Wine sulla 1.10 consegnata era di un commit
precedente, vedi *Costruire e provare l'installatore*):

1. costruire eseguibile e Setup delle due cartelle e provarli sulla 1.10 installata
   (`prove_installato.py`, 46 controlli, e `strumenti/prova_autoriparazione_installato.py`: il
   programma bloccato sostituito e il database rovinato riparato sull'eseguibile vero);
2. rigenerare il PDF della guida (c'è una guida in più);
3. la release `v1.11` nel progetto delle versioni, con i quattro file.

## Cose aperte

- **Le notti del cambio dell'ora** (trovato dalla revisione della 1.11, non cambiato): un turno di
  notte nelle due notti in cui cambia l'ora conta 10 ore, mentre le ore vere sono 11 a ottobre e 9
  a marzo (`TurnoPersonale.minuti`, anche nell'Excel). Se contare le ore vere o quelle
  dell'orologio lo decide Giovanni con Federica (sono ore che possono finire in busta paga); per le
  ore vere serve `tzdata` dentro l'eseguibile o la regola europea scritta a mano.
- **Codici dei turni scritti di seguito** («M» poi «P» entro un attimo diventa «MP», codice
  sconosciuto): funziona come documentato (le lettere scritte durante l'attesa formano un codice
  solo, così si scrivono MA, PE e RE), ma se Federica ci inciampa si può cambiare.
- `backup\danneggiati` cresce senza limite (i file rovinati non si cancellano mai, apposta): se un
  giorno occupa troppo, si svuota a mano.

- In Claude Code, per prima cosa: le prove su Windows vero, mai lanciate finora (vedi *Passare a
  Claude Code*); alla 1.11 le raccolte senza browser sono state lanciate con il Python di Windows
  in Wine e quattro prove che non andavano su Windows sono state sistemate (la password protetta
  con DPAPI, una cartella non scrivibile, il pid di un venv, la prova delle icone animate di
  domenica); `prove_15.py`, `prove_16.py` e `prove_191.py` vogliono `openssl` sul PATH (c'è nella
  riga di comando di Git for Windows, non in PowerShell).
- Pubblicare la 1.10 su GitHub (contiene la 1.8, la 1.9 e la 1.9.1) e controllare l'indirizzo
  pubblico (vedi *Stato alla consegna*); mettere il codice (`gestionale-agende.bundle`) in un
  progetto privato.
- Installare la 1.10 alla clinica la prima volta a mano, se c'è ancora la 1.5.
- **Fasce dei turni**: con Federica, scegliere la durata delle fasce dei turni che ne hanno
  bisogno (per esempio le sedute di endoscopia e gli ambulatori con le visite ogni 20 minuti),
  da *Configura → Anagrafiche*, il turno, *Durata delle fasce*. Salvando ogni turno il programma
  dice quanti appuntamenti già presi non stanno nelle fasce nuove: vanno guardati nella griglia
  (restano dove sono finché non si spostano). Federica non ha ancora visto la 1.10; se chiede
  fasce diverse nello stesso turno (per esempio la prima visita più lunga), è una funzione
  nuova: oggi la durata è una per turno.
- WhatsApp: quando Giovanni avrà numero, ID del numero e token di Meta, registrare il
  numero una volta dal programma (Configura → Email e WhatsApp → «Registra il numero», con
  il PIN a sei cifre della verifica in due passaggi) e mandare un messaggio di prova.
- **Email senza la verifica in due passaggi di Gmail** (richiesta di Giovanni del 25 ottobre
  2026): fatta nella 1.9.1, la pagina accetta qualsiasi casella. Da fare alla clinica: creare
  una casella dedicata sul dominio del gruppo (nefrocenter.it, cPanel di Netsons; server e porta
  in «Connetti dispositivi», sezione SSL/TLS), sceglierla come *Casella del sito della
  clinica* (il programma propone mail. e il dominio, 465 con SSL; se il pannello indica un
  altro server, si scrive quello, e se il certificato non corrisponde il messaggio della prova
  lo dice), mandare la prova e controllare il recapito con mail-tester.com, sistemando se serve
  SPF e DKIM da *Email Deliverability* di cPanel. Le risposte dei pazienti arrivano alla
  casella che manda, o all'email della struttura se è diversa (il programma la mette come
  Reply-To). Finché resta la Gmail, funziona com'è. OAuth resta sconsigliato (vedi *Le
  decisioni*).
- Dove si fa: caricare il database delle prestazioni vero dal programma (*Configura →
  Strutture del gruppo*) e scrivere i recapiti delle sei strutture (indirizzo, telefono per
  prenotare, prenotazione online, orari): finché mancano, la scheda della struttura lo dice
  e il messaggio per il paziente ha solo il nome. Quando arrivano le altre quattro strutture
  annunciate nel file (foglio REGOLE), si carica la versione nuova allo stesso modo. Se la
  Clinica Posillipo entra nel file con lo stesso nome della struttura del gestionale, prende
  il segno «qui» da sola. Federica non l'ha ancora vista.
- Turni: Federica non li ha ancora visti. Le prime impressioni (codici e orari dei turni
  della clinica, ruoli, coperture minime) vanno nei tipi di turno e nelle persone, non nel
  codice; se chiede altro (per esempio mandare i turni al personale), è una funzione nuova.
- Restano da vedere su un Windows vero: l'avviso SmartScreen al primo avvio del Setup (non è
  firmato), l'antivirus della clinica, l'apertura del browser predefinito.
- L'elenco dei comuni (`dati/luoghi_nascita.json`) va aggiornato quando nascono comuni
  nuovi, di solito a gennaio:
  `pip install -U python-codicefiscale && python strumenti/genera_luoghi_nascita.py`,
  poi le prove.
- Nei dati ufficiali dei comuni c'è una stranezza nota e accettata: il codice D588 è stato
  usato fino al 1928 sia per Filago sia per Marne (`prove_17.py` la conosce).

## Prima di cominciare, in una sessione nuova

1. Leggi questo file, poi `gestionale/CLAUDE.md` e le parti di `gestionale/LEGGIMI.md` che
   riguardano il lavoro da fare.
2. `python -m pip install -r gestionale/requirements.txt playwright python-codicefiscale`, poi
   `python -m playwright install chromium` (se non c'è già un Chromium). Su Windows servono
   anche Git for Windows (la riga di comando bash e `openssl`, che usano alcune prove) e, per
   i Setup, Inno Setup 6.
3. Lancia le prove di tutte e due le cartelle (`python strumenti/tutte_le_prove.py` dentro
   ciascuna): devono essere tutte verdi prima di toccare qualcosa.
4. Per vedere il programma: `python strumenti/demo.py` dentro `gestionale/`, poi
   http://127.0.0.1:5001.
