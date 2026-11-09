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
Claude Code*), il 1° novembre 2026 alla versione **1.11** (l'autoriparazione e un giro di
correzioni: vedi *La 1.11*), l'8 novembre 2026 alla **1.12** (ambulatori, riepilogo live, stampe ed
Excel, certificati: vedi *La 1.12*), lo stesso giorno alla **1.12.1** (le cose aperte chiuse e le
prove su un Windows vero: vedi *La 1.12.1*), il 9 novembre alla **1.12.2** (il riepilogo live più
chiaro e il riepilogo del periodo: vedi *La 1.12.2*) e lo stesso giorno alla **1.12.3** (le esportazioni di
ambulatori e sala operatoria per giorno, settimana e mese: vedi *La 1.12.3*).

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

- **Versione 1.12.2, pubblicata il 9 novembre 2026**: la release `v1.12.2`, segnata come ultima, con
  i due Setup, i due file delle versioni e il PDF della guida (55 pagine). Il riepilogo live rifatto
  perché si legga a colpo d'occhio e il nuovo riepilogo del periodo, non in diretta (vedi *La
  1.12.2*). Il database non cambia. Alla clinica va messa una volta a mano (vedi *Cose aperte*).
- **Versione 1.12.1, pubblicata l'8 novembre 2026**: la release `v1.12.1`, segnata come ultima, con
  i due Setup, i due file delle versioni e, per la prima volta, il PDF della guida (53 pagine),
  costruiti dall'automazione di GitHub. Porta le ore vere nelle notti del cambio dell'ora, i codici
  dei turni scritti di seguito, lo svuotamento dei file rovinati messi da parte, e le prove su un
  Windows vero con GitHub Actions (verdi in tutte e due le cartelle, anche nel browser). Vedi *La
  1.12.1*. Dentro c'è la **1.12** (pubblicata la notte prima): il menu *Ambulatori* con la
  pianificazione della settimana, la matrice e la programmazione del mese in Excel, il *Riepilogo
  live*, il foglio del giorno rifatto, tutti gli Excel con lo stesso aspetto, e i certificati dei
  siti portati dentro il programma (la causa dell'errore degli aggiornamenti della 1.9 alla clinica).
- **Versione 1.11, pubblicata il 1° novembre 2026**: la release `v1.11` nel progetto delle versioni,
  segnata come ultima, con i quattro file costruiti dall'automazione di GitHub (vedi *La 1.11*).
  L'indirizzo pubblico risponde «1.11» e i Setup pubblicati sono stati provati sopra la 1.10 con i
  dati (46 controlli e i 10 dell'autoriparazione sull'eseguibile vero). È la **prima release** del
  progetto: contiene anche la 1.8, la 1.9, la 1.9.1 e la 1.10, mai pubblicate. Il programma in
  clinica la trova da solo (dalla 1.6; con la 1.5 il Setup si avvia a mano la prima volta). Il codice
  è sul ramo `ccr-07f8e160-7j5lup` dello stesso progetto pubblico (scelta di Giovanni del 1°
  novembre: non in un progetto privato). Porta **l'autoriparazione** e **40 difetti corretti** trovati con una
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
Su Windows le prove con i certificati (`prove_15.py`, `prove_16.py`, `prove_191.py`) cercano il
comando `openssl`, che c'è nella riga di comando di Git for Windows.

**Su un Windows vero, da GitHub (dalla 1.12.1).** Fino alla 1.12 le prove erano state lanciate
solo su Linux e nel Windows finto di Wine. Ora il workflow `.github/workflows/prove.yml` («Prove su
Windows», pagina *Actions* del progetto) le lancia su un Windows di GitHub (`windows-latest`, Python
3.13) nelle due cartelle, a ogni push di un ramo `ccr-*` o a mano (*Run workflow*): tutte le
raccolte senza browser, poi `strumenti/demo.py` in sottofondo e quelle nel browser (Chromium di
Playwright, `tutte_le_prove.py --solo-browser`); ci vogliono una ventina di minuti, e i registri di
ogni raccolta si scaricano dall'esecuzione (artefatti `registri-gestionale` e
`registri-gestionale-animata`). Al primo giro (8 novembre 2026) 24 raccolte su 26 erano verdi in
tutte e due le cartelle, 2550 casi di `campagna.py` compresi; le prove rotte (tre, più una nel
browser al giro dopo) erano differenze fra Linux e Windows nelle prove stesse, non difetti del
programma, e sono state sistemate (vedi *La 1.12.1*). Il workflow non pubblica niente: serve a vedere su Windows quello che qui si vede solo
su Linux.

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
«Guida Gestionale Agende <versione>.pdf» (alla 1.10, 48 pagine; alla 1.12.1, 53; alla 1.12.2, 55). Dalla 1.12.1
lo genera anche il workflow «Pubblica una versione» e lo mette nella release come quinto file
(`Guida-Gestionale-Agende-<versione>.pdf`): non va più rifatto a mano a ogni versione.

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

Dalla 1.11 c'è la via senza PC: l'automazione `.github/workflows/pubblica.yml` dalla pagina
*Actions* del progetto (vedi *La 1.11*, «Pubblicare senza un PC con Python e Inno Setup»). I passi
qui sotto sono quelli a mano.

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

**Eseguibile e Setup alla 1.11**, costruiti in Wine dall'ultimo commit (`d832b27`) e provati: la
1.10 normale consegnata installata in un Windows finto pulito, i dati inventati di `demo.py` della
1.10 (46 appuntamenti, 30 pazienti), la 1.11 installata sopra con il Setup: le tabelle identiche
riga per riga dopo (la 1.11 non cambia lo schema), 46 controlli di `prove_installato.py` a posto,
e `strumenti/prova_autoriparazione_installato.py` (nuovo, con il Python di Windows) 10 controlli su
10 sull'eseguibile vero: il secondo avvio non apre un altro programma, il programma fermato con
`NtSuspendProcess` viene chiuso e riaperto da solo (104 secondi: prima aspetta chi potrebbe essere
solo occupato), un indice del database rovinato a programma chiuso viene riparato all'avvio senza
perdere una riga, il file rovinato messo da parte. Una cosa imparata: il Setup deve chiudere il
programma con `taskkill /F /T` (senza `/T` uno dei due processi dell'eseguibile a file unico
resta e tiene il file: l'installazione si fermava); e nel Windows finto lo schermo (`Xvfb`) dopo
molte ore smette di rispondere e il Setup muore con «Invalid window handle» senza avere
colpa: si riavvia lo schermo (per numero di processo, mai con `pkill -f`) e si riprova.

**Pubblicare senza un PC con Python e Inno Setup** (1° novembre 2026): dalla sessione nel cloud
non si possono creare release né tag (il collegamento a GitHub lo vieta: «Creating, editing, or
deleting releases is not permitted for this session type», e anche `git push` dei tag e l'API dei
riferimenti sono rifiutati), e Giovanni non ha Git né Python sul suo PC. Per questo nel ramo c'è
`.github/workflows/pubblica.yml`, un'automazione di GitHub («Actions») che fa tutto sui computer
di GitHub: un Windows vero con Python 3.13 e Inno Setup rifà i passi di `CREA_EXE.bat` e
`CREA_SETUP.bat` nelle due cartelle, controlla che l'impronta scritta in ogni `aggiornamento.json`
sia quella del suo Setup, crea la release `vX.Y` (la versione è quella di `comune.py`) segnata come
ultima, con le note prese da `NOTE-RELEASE-X.Y.md` se c'è, e alla fine scarica dall'indirizzo
pubblico come fa il programma e controlla che dica la versione nuova. Si avvia a mano dalla pagina
*Actions* del progetto: «Pubblica una versione» → *Run workflow* → scegliere il ramo → *Run
workflow*. Dura una decina di minuti. Se la release esiste già, i quattro file vengono sostituiti.
I Setup costruiti così sono diversi byte per byte da quelli costruiti in Wine o sul PC (li fa un
altro Python), ed è normale: vale la coppia Setup + file delle versioni.

**La 1.11 è stata pubblicata così**, il 1° novembre 2026: l'automazione avviata dalla sessione con
lo strumento GitHub della sessione (l'API diretta era vietata), esecuzione n. 1 riuscita; poi dalla
sessione il controllo dall'indirizzo pubblico (`latest` dice 1.11, le impronte dei due Setup
scaricati coincidono con i file delle versioni) e i Setup pubblicati, scaricati da GitHub,
installati in Wine sopra la 1.10 consegnata con i dati inventati: tabelle identiche, 46 controlli e
i 10 dell'autoriparazione a posto. Resta da rigenerare il **PDF della guida** (c'è una guida in più,
*Il programma si ripara da solo*): non blocca niente, le guide sono dentro il programma.

## La 1.12

Fatta il 2 novembre 2026 nella stessa sessione di Claude Code nel cloud, sullo stesso ramo
`ccr-07f8e160-7j5lup`, dopo la richiesta di Giovanni con l'errore degli aggiornamenti e i due
fogli da digitalizzare (il PDF della programmazione ambulatori di un'altra struttura del gruppo e
la matrice chiesta dalla segreteria amministrativa per la direzione sanitaria: file veri, rimasti fuori dal progetto).

**L'errore «il certificato del sito degli aggiornamenti non è valido»** (la 1.9 animata installata
alla clinica, 2 novembre). La causa non è il sito né la rete: Windows parte con pochi certificati
radice e aggiunge gli altri solo la prima volta che li incontra con Edge o con un suo programma
(CryptoAPI); il Python dentro il gestionale usa l'elenco di Windows così com'è e non glieli fa
scaricare. Nel 2025 GitHub è passato a radici nuove di Sectigo, che quel PC non aveva ancora
incontrato: il browser apriva il sito, il programma no. Dalla 1.12 `comune.contesto_tls` si fida
anche dell'elenco Mozilla portato dentro l'eseguibile (`certifi`, in `requirements.txt` e nella
ricetta `gestionale.spec`) e di un eventuale `certificati.pem` accanto al database; lo usano gli
aggiornamenti e le email. Il messaggio dice il motivo in parole semplici e la pagina ha il
collegamento alla pagina delle versioni per il Setup a mano; una riga «per l'assistenza» dice di
quali certificati il programma si fida (così `prove_installato.py` controlla che certifi sia dentro
l'eseguibile). Prove in `prove_16.py` (il file `certificati.pem`, l'elenco Mozilla senza nessun
certificato di sistema, i motivi spiegati). **Per la clinica**: la 1.9 installata non può
aggiornarsi da sola finché Windows non conosce quella radice. Due strade: aprire una volta
`https://github.com` con **Edge** su quel PC (Windows scarica la radice) e poi *Configura →
Aggiornamenti → Controlla adesso*; oppure scaricare dal browser
`GestionaleAgende-animata-setup.exe` dalla pagina delle versioni
(`https://github.com/number959/gestionale-agende-versioni/releases/latest`) e avviarlo sopra la
1.9: i dati restano. Dalla 1.12 in poi non succede più.

**Ambulatori** (`ambulatori.py`, menu *Ambulatori*, sezione *Ambulatori* del `LEGGIMI.md`, guide
*Chi sta in quale stanza* e *La programmazione ambulatori del mese* con immagini e video): la
pianificazione della settimana (stanze × mattina/pomeriggio, DISPONIBILE e ore libere, il «+» per
mettere un medico, la «×» per toglierlo da quella settimana in poi, il nome apre il turno e torna
indietro), la matrice in Excel per la direzione sanitaria (anche come settimana tipo), la
programmazione del mese per specialità con le date calcolate e le note automatiche, in pagina e in
Excel con il calendario. Le scelte: calcolato dai turni e mai ricopiato (il foglio a mano si
allontanava dall'agenda); mattina e pomeriggio divisi alle 14 (`ambulatori.META`), un'ora libera
(`MINIMO_LIBERO`) si segnala; sale operatorie fuori; destinatario e chi compila sono testi fissi
(`DESTINATARIO`, `COMPILATO_DA`), modificabili nell'Excel; la regola della stanza occupata è una
sola, `anagrafiche.stanza_gia_assegnata`, condivisa con la scheda del turno. Prove `prove_112.py` e
`prove_112_browser.py`.

**Richieste del 7–8 novembre** (Giovanni, dalla chat): «verifica tutto», stampe e report migliorati,
una dashboard animata da esporre su internet, un riepilogo live di agende e ambulatori.

- **Revisione della 1.12** con agenti indipendenti (correttezza dei calcoli, sicurezza delle pagine,
  Excel, equivalenza del refactor di `anagrafiche`): nessun difetto grave; sistemate le cose trovate
  (giorni della matrice solo con turni delle stanze mostrate, festivo che chiude la mezza giornata
  senza turno di un giorno, motivi di assenza e chiusura in parole semplici con l'articolo giusto
  davanti a 1, 8 e 11, specialità con maiuscole diverse in un gruppo solo, `testo_excel` su ogni
  testo degli Excel, altezza delle righe, «Togli» con data valida e mai su un turno già finito).
- **Foglio del giorno** rifatto e **Excel con un aspetto solo** (vedi *Viste e stampe* nel
  `LEGGIMI.md`): la pagina di stampa è una tabella con testata e piede ripetuti, numero di pagina nel
  margine, conteggi e turni per stanza, colonne in più solo dove servono, totali, colonne a scelta
  (data di nascita, casella da spuntare), preferenza «anche disdetti»; gli Excel passano dagli aiuti
  di `comune.py` (titolo con struttura e periodo, intestazione blu, A4 adattato, intestazioni
  ripetute, piede con il numero di pagina, totali).
- **Riepilogo live** (`live.py`, *Ambulatori → Riepilogo live*, con «Modo schermo» per il secondo
  monitor): la giornata adesso e ogni stanza; il JSON `/riepilogo-live.json` con soli conteggi è il
  formato pensato per il cruscotto su internet.
- **Dashboard su internet**: non ancora nel programma. Due pagine private pubblicate per Giovanni dalla
  sessione: il prototipo animato con quattro stili e il riepilogo live con dati finti
  (https://claude.ai/artifact/QBveCZQsB1AHyNigxoPNE9) e il documento delle proposte
  (https://claude.ai/artifact/V1HQkTgpQud35dL6MCwF2N): cosa si vede, il motion design, la
  riservatezza (il programma pubblicherebbe solo conteggi, cifrati; la chiave nel collegamento), le
  tre strade a confronto (file cifrato sullo spazio web del gruppo via FTPS o su GitHub Pages, senza
  server, consigliata; oppure un piccolo servizio su Cloudflare con accesso per persona, quando
  servirà per più strutture), costi, tempi (5–6 giorni per la prima strada, versione 1.13) e le
  decisioni che spettano a Giovanni. Il file del prototipo è anche in
  `strumenti/cruscotto_prototipo/` (vedi sotto).

**La 1.12 è stata pubblicata così**, l'8 novembre 2026: l'automazione «Pubblica una versione» avviata
dalla sessione (esecuzione n. 2, riuscita in due minuti), release `v1.12` segnata come ultima con i
quattro file (le impronte nei file delle versioni coincidono con quelle che GitHub calcola per i
Setup). Prima, nel Windows finto: le due cartelle costruite con `costruisci.sh`; **la simulazione
dell'aggiornamento** della clinica: installata la 1.11 pubblicata, poi «Aggiorna adesso» verso la
1.12 da una cartella (`prova_aggiorna_adesso.py`, 14 controlli a posto: copia di sicurezza, Setup
silenzioso, riavvio, novità, dati intatti, Setup installato tolto dopo due minuti), poi i 50
controlli di `prove_installato.py` sulla 1.12; infine il controllo degli aggiornamenti della 1.12
installata contro il vero indirizzo GitHub, attraverso il proxy della sessione con il suo
certificato in `certificati.pem`: «Il programma è aggiornato» (nella sessione il certificato del
proxy è anche in `SSL_CERT_FILE`, che Python legge: il caso «radice sconosciuta» è coperto dalle
prove di `prove_16.py`, non da quella simulazione). Tutte le raccolte senza browser verdi nelle due
cartelle (26 raccolte ciascuna, 2550 casi di `campagna.py`), prove nel browser verdi nella normale
e nell'animata (quelle dell'animata comprese).

## La 1.12.1

Fatta l'8 novembre 2026, nella stessa sessione, dopo la richiesta di Giovanni di chiudere le cose
aperte. Niente di nuovo nel database (schema 11). Cosa porta:

- **Le ore vere nelle notti del cambio dell'ora** (trovato dalla revisione della 1.11): una notte
  21–07 vale 9 ore nell'ultima domenica di marzo e 11 in quella di ottobre, nei conti del mese,
  nell'Excel (la riga «Esportato il…» lo dice nei mesi con il cambio) e nei riposi fra due turni.
  Decisione: la regola europea (ultima domenica di marzo e di ottobre, alle 3:00) è scritta a mano
  in `calendario.cambio_ora` e `calendario.minuti_veri`, invece di usare `zoneinfo`: su Windows il
  fuso di Roma vuole il pacchetto `tzdata`, e un eseguibile PyInstaller senza darebbe risultati
  sbagliati in silenzio; la regola è fissa dal 1996 e `prove_18.py` la confronta con `zoneinfo` dove
  c'è (ogni giorno dal 2024 al 2039, 41.000 coppie di orari). Un orario scritto nell'ora che non
  esiste o in quella ripetuta si legge come prima del cambio, la stessa convenzione di Python. Il
  tipo di turno senza data (`TipoTurno.minuti`) resta nominale (600 per N). Se Giovanni e Federica
  preferissero le ore dell'orologio (per le buste paga), basta far tornare `TurnoPersonale.minuti`
  a `fine - inizio`: è un punto solo.
- **Codici dei turni scritti di seguito**: «M» e subito «P» non sono più «codice sconosciuto MP»,
  ma M sul giorno e P su quello dopo, come scrivendoli con calma (`nuovoBuffer` in `turni.js`:
  vale il codice più lungo con cui comincia il testo, il resto ricomincia da capo). Provato in
  `prove_18_browser.py`.
- **`backup\danneggiati` si può svuotare**: *Controllo del programma* dice quanti file ci sono e
  quanto occupano, e con una conferma toglie quelli da più di 90 giorni
  (`autoripara.svuota_danneggiati`, `GIORNI_DANNEGGIATI`); i recenti restano sempre, il programma
  da solo non cancella mai niente. Nel diario resta la riga. Provato in `prove_autoriparazione.py`.
- **Le prove su un Windows vero**, con GitHub Actions (`prove.yml`, vedi *Prove*): ai primi giri
  quattro prove rotte, tutte nelle prove e non nel programma: `pid_vero` usava `wmic`, che Windows Server
  2025 (il `windows-latest` di GitHub) e i Windows 11 recenti non hanno più (ora legge i processi
  figli con Toolhelp, `ctypes`; il programma non ha mai usato `wmic`); `h_elenco_mozilla` voleva zero
  certificati di sistema, ma su Windows l'elenco delle radici è del PC e c'è sempre (ora controlla
  che il programma ne abbia di più grazie all'elenco Mozilla); `h_senza_risposta` con una porta
  chiusa su 127.0.0.1 riceveva «non risponde» invece di «non raggiungibile», perché Windows dice
  «rifiutata» solo dopo un paio di secondi di tentativi (ora aspetta 5 secondi); «Copia» di Dove si fa
  (`prove_19_browser.py`) confrontava gli appunti alla lettera, e su Windows gli a capo sono CRLF (ora
  li normalizza); e `prove_18_browser.py`, che sceglie un mese a caso nel futuro, in un marzo con il
  cambio dell'ora la notte 24→25 si aspettava 10 ore di riposo invece delle 9 vere (ora le calcola con
  `calendario.minuti_veri`; `PROVE_MESE=AAAA-MM` forza il mese). Al terzo giro tutte le raccolte senza
  browser erano verdi nelle due cartelle, al quarto anche quelle nel browser dell'animata.
- **Revisione avversaria** della 1.12.1 (quattro revisori e due verificatori per segnalazione, come per
  la 1.12): il limite orario della sessione ne ha fermata metà; delle segnalazioni arrivate due erano
  giuste e sono state corrette: «Svuota» diceva «niente da togliere» anche quando un file non si era
  potuto cancellare (ora lo dice, con il consiglio), e lo svuotamento finiva in campanella come «Riparato
  da solo» (ora il diario lo tiene, la campanella no). Il cambio dell'ora non ha avuto segnalazioni; i
  codici di seguito e le prove su Windows sono stati rivisti a mano e dal giro su GitHub.
- **Il PDF della guida nella release**: il workflow «Pubblica una versione» avvia il gestionale di
  prova, genera il PDF con Chromium e lo carica come quinto file (53 pagine alla 1.12.1). Se il
  passo non riesce la release si fa lo stesso, senza PDF.
- `tutte_le_prove.py --solo-browser` (solo le prove nel browser, per chi ha già fatto le altre).

**La 1.12.1 è stata pubblicata così**, l'8 novembre 2026: prima tutte le prove verdi qui (26
raccolte senza browser in ciascuna cartella, 2550 casi di `campagna.py`, 11 raccolte nel browser
nella normale e 13 nell'animata) e su GitHub, nel quinto giro di «Prove su Windows» (tutte e due le
cartelle verdi, anche nel browser); i due Setup costruiti in Wine, installati uno sopra l'altro e
provati (`prove_installato.py`, 50 controlli su 50 ciascuno). Poi l'automazione «Pubblica una
versione» (esecuzione n. 3, tre minuti): release `v1.12.1` segnata come ultima con cinque file, il
PDF della guida compreso. Dalla sessione il controllo dall'indirizzo pubblico (`latest` dice 1.12.1,
le impronte dei due Setup scaricati coincidono con i file delle versioni) e **la simulazione
dell'aggiornamento della clinica dall'indirizzo vero**: nel Windows finto installata la 1.12
pubblicata su GitHub, poi «Aggiorna adesso» ha trovato la 1.12.1 sull'ultima release, l'ha scaricata,
ha fatto la copia di sicurezza, ha avviato il Setup in silenzio e si è riaperto alla 1.12.1 con le
novità (`prova_aggiorna_adesso.py` con l'indirizzo `…/releases/latest/download/`, 14 controlli su 14,
dati intatti), quindi indirizzo predefinito rimesso e di nuovo `prove_installato.py` (50 su 50). Il
certificato del proxy della sessione era in `certificati.pem`, come documentato in *La 1.12*.

## La 1.12.2

L'8 novembre 2026 sera Giovanni ha scritto che la schermata dei turni live (*Ambulatori → Riepilogo
live*) era poco chiara. Guardata alle 10:40 di un martedì con i dati di prova, aveva ragione: otto
numeri della stessa grandezza che non sommavano al totale (9 appuntamenti, 2 fatti, 0 in corso, 1 da
fare e 6 «in ritardo», che erano pazienti di stamattina mai segnati arrivati; oltre tre ore non
contavano più da nessuna parte), il medico scritto due volte con due turni uguali, «libera fino alle
14:00» senza dire se arrivava un paziente o finiva il turno, nessuna idea di quando lavora chi, 66
mezze giornate libere in una lista e le notifiche sopra le stanze. Rifatta (vedi *Riepilogo live* nel
`LEGGIMI.md`): una frase in cima, quattro gruppi che sommano (fatti, in corso, da segnare, da fare),
una riga per stanza con la linea del tempo del turno e delle visite e la linea rossa di adesso, le ore
con i numeri, le mezze giornate in una tabellina M/P per giorno e stanza, niente notifiche su quella
pagina. Le stesse scelte nel riepilogo del prototipo del cruscotto. Decisione: le frasi e le posizioni
le calcola `live.py` (sono anche nel JSON per il futuro cruscotto), la pagina non ha JavaScript per
disegnare; nei rettangoli delle visite solo orario e stato, mai nomi, perché la pagina può stare su
uno schermo che vedono anche i pazienti.

Subito dopo Giovanni ha chiesto anche un riepilogo «non live ma riassuntivo»: è *Ambulatori → Riepilogo
del periodo* (vedi il `LEGGIMI.md`), per un giorno, una settimana, un mese o due date: ore di turno
delle stanze e quanto sono state occupate, visite fatte, non presentati, disdetti, da segnare, mezze
giornate senza nessun medico, per stanza, per medico e giorno per giorno, in Excel e da stampare.
Decisione: le ore occupate contano anche i non presentati (il posto era preso) e non i disdetti; le
visite fuori dai turni si dicono a parte invece di gonfiare l'occupazione. Non sostituisce
*Statistiche* (prestazioni, provenienza, incassi) né il *Riepilogo del mese per medico* (la cassa):
guarda le stanze e i turni.

Prima di pubblicare, una revisione indipendente con un'automazione di revisori (quattro dimensioni,
due verificatori per segnalazione, solo letture e foto sui gestionali di prova) ha confermato 19 cose,
nessuna che perdesse dati: sono tutte corrette e provate (elenco nel `LEGGIMI.md`, *Riepilogo live*).
La più seria era nelle prove: quella della riservatezza del JSON chiedeva il riepilogo di un giorno
senza appuntamenti e non avrebbe mai visto un nome di paziente; ora usa l'orologio fermo
(`_OraFerma` in `prove_112.py`) su un'ora con turni e visite.

Una seconda revisione, sul riepilogo del periodo, ha confermato 22 segnalazioni (15 cose distinte),
anche qui nessuna che perdesse dati, tutte corrette e provate. Le più serie: un medico in due stanze
nello stesso momento (un turno di un giorno messo sopra quello di ogni settimana) contava le ore due
volte e dimezzava la sua occupazione; le visite che passano la mezzanotte e le stanze disattivate poi
sparivano dai conti; un festivo con un turno di un giorno sembrava chiuso; le frecce su due mesi interi
andavano di un mese solo. Decisione: le ore di un medico sono l'unione dei suoi turni del giorno su tutte
le stanze, quindi due medici nella stessa stanza possono sommare più ore della stanza (giusto: erano in
due). La prova nuova (`p_periodo_revisione` in `prove_112.py`) è una settimana con i numeri contati a mano.

Una verifica indipendente di queste correzioni (45 agenti, due scettici per segnalazione) ha confermato
altri quattro casi, tutti rari e senza dati persi, più tre su cui i verificatori erano divisi e che ho
corretto lo stesso: i turni di una stanza disattivata contavano anche dopo lo spegnimento (la scheda non
chiude i turni e la data non resta scritta: ora contano fino all'ultimo appuntamento non disdetto della
stanza), la sola coda dopo la mezzanotte non faceva comparire una stanza spenta, una visita fino alle
24:00 lasciava una riga del medico a zero, un giorno chiuso con soli disdetti sembrava aperto, e le prove
dell'Excel avevano solo ore intere (ora un terzo d'ora, ogni foglio cella per cella). Ogni difetto,
rimesso apposta nel codice, fa fallire almeno una prova (`p_periodo_seconda_revisione`). Se un giorno
servisse la data vera dello spegnimento, la scheda della stanza potrebbe scriverla nel registro.

**La 1.12.2 è stata pubblicata così**, il 9 novembre 2026: prima tutte le prove verdi qui sul codice
finale (26 raccolte senza browser in ciascuna cartella, 11 nel browser nella normale e 13
nell'animata) e su GitHub («Prove su Windows» n. 14, tutte e due le cartelle verdi); i due Setup
costruiti in Wine, installati uno sopra l'altro e provati (`prove_installato.py`, ora 53 controlli:
dalla 1.12.2 anche pagina, Excel e JSON del riepilogo del periodo). Poi «Pubblica una versione»
(esecuzione n. 4, dal commit `b7e0320`): release `v1.12.2` segnata come ultima con cinque file.
Dall'indirizzo pubblico `latest` dice 1.12.2 e le impronte dei Setup scaricati coincidono con i file
delle versioni (normale `817e1621…c759`, animata `284b51c7…0cef`). Simulazione dell'aggiornamento
della clinica dall'indirizzo vero, come per la 1.12.1: installata nel Windows finto la 1.12.1
pubblicata, «Aggiorna adesso» ha trovato la 1.12.2, l'ha scaricata e installata e si è riaperto alla
1.12.2 (14 controlli su 14, dati intatti), poi di nuovo `prove_installato.py` (53 su 53).
Provato anche il passaggio della clinica: la 1.9 animata ricostruita dal tag `v1.9`, installata su un
database fatto dalla 1.9 stessa (dati di prova, schema 10), e sopra il Setup animata 1.12.2 scaricato da
GitHub: dati intatti (46 appuntamenti, 30 pazienti, 27 turni), schema portato da 10 a 11 dopo la copia
«prima-della-versione-11», `prove_installato.py` 53 su 53.

Per vedere la pagina come in un giorno di lavoro di domenica o la sera, un gestionale di prova con
l'ora del riepilogo ferma: `strumenti/demo.py` lanciato con `live.datetime` sostituito da una classe
con `now()` fisso (lo script usato è nella cartella provvisoria della sessione, poche righe: importa
`live`, cambia `live.datetime`, poi `runpy.run_path('strumenti/demo.py')`). Immagini e video della
guida *Il riepilogo live* sono fatti così, alle 10:40 di martedì 3 novembre.

## La 1.12.3

Il 9 novembre 2026 Giovanni ha chiesto di «accorpare le esportazioni della sala e quelle degli
ambulatori», per settimana e per mese, e subito dopo, alla domanda su cosa intendesse: «esportazioni singole
giornaliere, settimanali e mensili rispettivamente di ambulatori e sale operatorie, e un'esportazione unica che
accorpi tutto per giorno, settimana e mese»; per la sala del mese ha scelto l'Excel con la sala giorno per
giorno, i turni dei chirurghi e l'elenco degli interventi. Fatto così (vedi *Ambulatori* nel `LEGGIMI.md`):
la pagina *Ambulatori → Esportazioni in Excel* con nove file (giorno, settimana e mese × ambulatori, sala
operatoria, tutto insieme), e la sala in fondo alla pianificazione della settimana e alla programmazione del
mese, in pagina. Decisioni: gli Excel classici restano dov'erano e uguali, solo ambulatori (molte prove e
l'abitudine della clinica li usano; la matrice è il modulo della direzione sanitaria); in «tutto insieme»
ambulatori e sala stanno in fogli separati («occorre distinguere sala e ambulatori»); i conti degli
ambulatori non contano la sala; negli elenchi degli interventi niente dati dei pazienti (c'è la lista
operatoria del giorno). La sala in questa clinica si organizza anche senza turni (i «giorni di sala» dei
chirurghi e gli interventi prenotati): per questo chi opera senza un turno è detto per nome nella settimana e
ha una riga sua nel mese, e un giorno con soli interventi in sala compare. Il menu *Settimana* (l'agenda di
tutte le stanze) non è cambiato: si stampa come prima.

Prima di pubblicare, una verifica indipendente (quattro revisori, due verificatori per segnalazione; metà
dei verificatori si è fermata per il limite d'uso e quelle segnalazioni le ho guardate io) ha trovato: un
turno di sala fuori dall'orario della struttura che spariva dalla settimana, un intervento contato due
volte con due turni sovrapposti, la matrice della direzione e il riepilogo live cambiati dai giorni di sola
sala, la chiusura persa nel calendario della pagina del mese con un intervento, il titolo dell'Excel della
sala sotto un logo largo, la tendina «Altre esportazioni» tagliata sul telefono (ora ogni tendina aperta
resta dentro lo schermo, `gestionale.js`), e testi da sistemare. Tutto corretto, con la prova
`b_sala_casi_limite`; ogni difetto, rimesso apposta, fa fallire una prova.

## Cose aperte

- **Ore del cambio dell'ora**: dalla 1.12.1 contano le ore vere (vedi *La 1.12.1*). Se per le
  buste paga Giovanni e Federica vogliono quelle dell'orologio, è un punto solo da cambiare.
- Alla clinica c'è la 1.9 animata e il suo controllo degli aggiornamenti non riesce (il certificato,
  vedi *La 1.12*): l'ultima versione va messa una volta a mano, dal Setup scaricato nel browser dalla pagina
  delle versioni (dove c'è anche il PDF della guida), oppure dopo aver aperto github.com con Edge.
  Da lì in poi «Aggiorna adesso» torna a funzionare da solo.
- In Claude Code sul PC di Giovanni le prove si lanciano come qui; su un Windows vero le ha già
  fatte GitHub (`prove.yml`): se una prova non va sul suo PC e va su GitHub, è il PC (antivirus,
  `openssl` non sul PATH: c'è nella riga di comando di Git for Windows, non in PowerShell).
  Due volte una prova nel browser è fallita sul Windows di GitHub per `net::ERR_NO_BUFFER_SPACE` nella
  console del browser (Windows senza risorse per una connessione in quel momento): l'8 novembre 2026,
  esecuzione 11, `prove_icone_animate.py` 13 su 14 nell'animata; il 9 novembre, esecuzione 22, nella
  normale `prove_guida_browser.py` 57 su 59 (una pagina non caricata: «codice-fiscale: giro completo (0
  passi)») e `prove_15_browser.py` 13 su 14. Tutte e due le volte lo stesso codice è passato rifacendo la
  prova (nella 22, «Re-run failed jobs»: tutto verde), e su Linux e in Wine non è mai successo. La prova
  non lo ignora apposta. Da allora `prove.yml`, quando qualcosa fallisce, scrive nel suo registro le
  connessioni TCP per stato, le porte dinamiche e la memoria libera: se succede ancora, lì si vede se
  erano finite le porte (molte connessioni `TIME_WAIT`) o la memoria, e si corregge la causa.
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
