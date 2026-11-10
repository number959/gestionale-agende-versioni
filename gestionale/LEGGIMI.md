# Gestionale agende

Agenda delle stanze per l'accettazione. Nato per la Clinica Posillipo, è uguale per
ogni struttura: nome, logo, società e colori si impostano dal programma. Gira sul PC
della segreteria, con un solo utente; internet serve solo, in uscita, per le email e i
WhatsApp ai pazienti e per scaricare gli aggiornamenti. Il database è un file unico.

**Novità della 1.11.** **Il programma si ripara da solo.** Se il database si rovina (la
corrente saltata, un disco che sbaglia) il programma se ne accorge all'avvio e ogni mezz'ora: lo
ripara senza perdere niente quando si può (un indice rovinato si rifà dai dati), altrimenti rimette
l'ultima copia di sicurezza buona e dice da che ora ricontrollare; il file rovinato non si cancella
mai, resta in `backup\danneggiati` per l'assistenza. Se il programma si **blocca**, basta cliccare
di nuovo l'icona: quello bloccato si chiude e se ne apre uno nuovo; se una pagina resta ferma troppo
a lungo, o mancano i file del programma, si **riavvia da solo**. I lavori in sottofondo (copie,
email, aggiornamenti) se si fermano ripartono. Le copie di sicurezza sono **più frequenti** (una
ogni due ore se ci sono modifiche, oltre a quella del giorno) e si fanno anche quando la cartella
scelta non si raggiunge. Tutto si vede in *Impostazioni → Controllo del programma*, e la campanella
avvisa (vedi *Autoriparazione*). Corretti anche alcuni difetti trovati studiando i guasti: il
ripristino che si fermava proprio con il database rovinato, l'orologio del PC indietro che faceva
sparire le copie appena fatte, le copie della cartella accanto al database che non si vedevano.

**Novità della 1.10.** **Le fasce di ogni ambulatorio.** Ogni turno può avere la sua **durata
delle fasce** (*Configura → Anagrafiche*, il turno, *Durata delle fasce*): visite ogni 20 minuti
in un ambulatorio, esami ogni 15 nella sala endoscopia, mentre il resto della clinica resta con
le fasce della struttura. La prestazione occupa le **fasce intere** che le servono: una
colonscopia da 45 minuti con fasce da 15 ne occupa tre, una visita da 30 con fasce da 20 ne
occupa due (fino a 40 minuti), un esame più corto della fascia la occupa tutta, così non
restano buchi da 10 minuti prenotabili per sbaglio. La griglia lo mostra (in testa alla colonna
*fasce da 15'*, ogni fascia libera con la sua ora, righe alte in proporzione al tempo), e
**Prima disponibilità** e **Sposta** propongono le ore delle fasce. Un'ora scritta a mano a
metà fascia si salva con un avviso; nella stessa fascia il programma non mette un secondo
appuntamento. Gli appuntamenti già presi restano dove sono: salvando il turno il programma
dice quanti non stanno nelle fasce nuove, e si possono sempre modificare. Senza fasce
proprie nei turni tutto resta come prima (vedi *Fasce dei turni*).

**Novità della 1.9.1.** **L'email con qualsiasi casella, anche senza Gmail.** In *Configura →
Email e WhatsApp* si sceglie il tipo di casella: quella del **sito della clinica** (bastano
indirizzo e password, niente verifica in due passaggi), **Aruba**, **Gmail** o un **altro
server**; server, porta e sicurezza si compilano da soli e le istruzioni sono quelle del
tipo scelto. Per i fornitori che danno un nome utente diverso dall'indirizzo c'è il suo
campo, per un server della rete interna che non chiede la password una spunta. Se un'email
non parte, il messaggio dice cosa correggere (la password, porta e sicurezza che non vanno
insieme, il nome del server). La Gmail già collegata continua a funzionare com'è (vedi
*Email e WhatsApp ai pazienti*).

**Novità della 1.9.** **Dove si fa.** Nuovo menu *Dove si fa* (tasto D): si scrive la
prestazione come la dice il paziente («risonanza ginocchio», «tac torace», «holter») e si
vedono subito le **strutture del gruppo** dove si fa, con le sigle d'uso (RM, TC, RX, ECG,
MOC…), singolari e plurali e le parole scritte male corrette da sole. Un clic sulla struttura
apre la sua **scheda**: indirizzo con la mappa, telefoni, prenotazione online, orari, come si
prenota e il **messaggio già scritto per il paziente**, da copiare, mandare su WhatsApp o
per email, o stampare. Scelto il paziente (anche dalla sua scheda), il messaggio porta il
suo nome e parte verso i suoi recapiti. I pazienti indirizzati restano in un **registro**
(con Excel e nelle Statistiche). Il **database delle prestazioni** del gruppo, il file
Excel con una X per ogni struttura dove si fa una prestazione, si carica da *Configura →
Strutture del gruppo*, dove si scrivono anche i recapiti; per una versione nuova del file
basta caricarla, con l'anteprima di cosa cambia. La ricerca in alto (tasto /) trova anche
le prestazioni (vedi *Dove si fa*).

**Novità della 1.8.** **Turni del personale.** Nuovo menu *Turni*: medici, infermieri, OSS,
tecnici, accettazione e ausiliari, nel **mese** (il foglio dei turni con i codici M, P,
N…), nella **settimana** (con orari, aree e le ore di ciascuno contro quelle del contratto)
e nel **giorno a ore** (chi c'è ora per ora, con gli ambulatori dei medici dall'agenda). I
turni si mettono come in un foglio di calcolo: clic sulla cella oppure il codice scritto da
tastiera, più celle insieme trascinando o con Maiusc e le frecce; Ctrl+Z annulla e Ctrl+Y
rifà. Il programma rifiuta i turni sovrapposti (anche con la notte del giorno prima),
segnala i riposi sotto le 11 ore, conta ore, notti, festivi e assenze e, con le **coperture
minime**, colora i giorni in cui manca qualcuno. Lo **schema a rotazione** ripete una
sequenza (M M P P N SN R R) sfasata persona per persona, con l'anteprima; la settimana si
copia dalla precedente; il mese si stampa o si scarica in Excel; nella pagina *Oggi* c'è
*In servizio oggi* (vedi *Turni del personale*). In *Email e WhatsApp* il numero WhatsApp
**si registra dal programma** con il PIN, e gli errori di Meta si spiegano in parole
semplici. Le tendine del menu e *Stampa e scarica* della giornata restano sempre sopra la
pagina e le notifiche.

**Novità della 1.7.** **Codice fiscale controllato e calcolato.** Nella scheda del paziente e
nella prenotazione il codice fiscale si controlla mentre lo si scrive: se è sbagliato il
programma dice cosa non va (la lunghezza, il carattere al posto sbagliato, una data che non
esiste, l'ultima lettera di controllo) e non lo salva; da un codice giusto si riempiono da
soli data, sesso e luogo di nascita. Senza codice, con cognome, nome, sesso, data e luogo di
nascita, il codice si calcola da solo. Il luogo si sceglie da un elenco con tutti i comuni,
anche quelli soppressi o rinominati, e gli stati esteri. Per i pazienti già in archivio:
aggiornando, sesso, luogo e data di nascita si ricavano dai codici validi, e la pagina
*Pazienti → Controllo dei codici fiscali* mostra quelli non validi, quelli che non
corrispondono ai dati, lo stesso codice su due schede e chi è senza (vedi *Codice fiscale*).
Gli aggiornamenti sono già impostati sulle versioni pubblicate su GitHub.

**Novità della 1.6.** **Videoguide**: ogni guida di *Aiuto → Come fare…* ha il suo video
(*Guarda il video*), la guida sullo schermo registrata sui dati di prova con un puntatore
che va dove si clicca; si apre grande sopra la pagina e parte subito. **Aggiorna adesso**:
il programma si accorge da solo delle versioni nuove (le cerca fra quelle pubblicate su
GitHub, all'indirizzo già impostato), scarica il Setup e lo controlla; compare la notifica
*Aggiornamento disponibile* e da *Configura → Aggiornamenti* un clic fa la copia di
sicurezza, installa e riapre il programma in circa un minuto (vedi *Aggiornamenti dal
programma*). Dopo ogni aggiornamento si apre la pagina delle **Novità**, con il video di
ogni novità; si ritrova in *Aiuto → Novità*.

**Novità della 1.5.** Email e WhatsApp ai pazienti (vedi *Email e WhatsApp ai pazienti*).
Prenotando un esame endoscopico del Dr. Galasso parte da sola la mail di preparazione
dell'accettazione, con le informative di gastroscopia e colonscopia allegate. **Ogni medico
può avere le sue email**, con testi e informative sue: per le sue prestazioni parte la sua
al posto di quella per tutti i medici, e un'email già fatta si duplica per un altro medico.
Dalla pagina dell'appuntamento ogni email si manda anche a comando. Il giorno prima, all'ora scelta, parte il **promemoria**:
su WhatsApp quando è configurata la piattaforma di Meta, altrimenti per email; la pagina
Conferme dice cosa è partito e chi resta da chiamare. Le email partono dalla Gmail della
clinica, medicinamigliorenapolisrl@gmail.com, che l'aggiornamento scrive anche nella
struttura: compare nelle stampe e nella firma delle email. Nel modulo di prenotazione ci
sono **data di nascita**, **codice fiscale** (la data si riempie da sola) e il nuovo
**indirizzo** del paziente, anche nella scheda e nell'importazione. Il **mese** mostra la
sala operatoria: interventi e chirurghi di ogni giorno, e chi opera di solito quel giorno
ed è ancora libero. Il **logo nuovo** della clinica, *Clinica Posillipo · Longevity
Institute*, prende il posto del precedente da solo con l'aggiornamento, e i caratteri sono
quelli del sito della clinica: **Manrope** per i titoli, **Inter** per il testo. **Per
aggiornare non si disinstalla**: si avvia il Setup nuovo, che dice quale versione c'è e
quale arriva; il numero della versione installata è in *Aiuto → Come fare…*.

**Novità della 1.4.6.** La seconda parte della stessa revisione (vedi *Dodicesimo giro*).
Il gestionale accetta moduli solo dalle sue pagine e risponde solo agli indirizzi del PC:
un sito aperto nello stesso browser non può più cambiare o leggere niente. Importando
un'agenda, fra due medici con lo stesso cognome vince quello attivo, e se ne restano due
attivi l'anteprima lo dice. Le email con l'agenda o il riepilogo del medico restano entro
il limite di Outlook e si fermano a una riga intera. I file Excel scaricati non lasciano
più copie nella cartella temporanea di Windows. Eliminando un turno il programma dice
quanti appuntamenti restano fuori turno. Nei testi di moduli e messaggi `{Paziente}`
vale come `{paziente}`.

**Novità della 1.4.5.** Correzioni, da una revisione esterna del codice verificata punto
per punto (vedi *Undicesimo giro*). Nell'importazione tre righe alla stessa ora nella
stessa stanza non passano più come nuove, una stanza occupata dopo l'anteprima diventa un
appunto da confermare, lo stesso medico scritto in due modi viene segnalato se è in due
stanze alla stessa ora, e si leggono i file "Testo Unicode" di Excel e i CSV del Mac. Le
serie copiano la degenza; una stanza con soli appuntamenti disdetti si disattiva; la
settimana del medico non mostra più "libero" dentro un intervento lungo; niente doppioni
del paziente per un accento, un apostrofo o il secondo telefono; un telefono di meno di
sei cifre si ferma già in prenotazione; un importo 0 non è "da incassare"; con più
strutture i pazienti nuovi sono quelli della struttura scelta.

**Novità della 1.4.4.** Più semplice da usare. Il **menu** mostra solo le pagine di tutti i
giorni; le altre stanno in tre gruppi che si aprono passandoci sopra: *Segreteria*
(conferme, da confermare, chiusura, da fare, lista d'attesa, prima disponibilità,
elenco), *Aiuto* e *Configura* (anagrafiche, importazione, impostazioni). Nella giornata
le stampe sono raccolte in *Stampa e scarica*. C'è una **guida**: in **Aiuto → Come
fare…** venti procedure passo per passo, ciascuna con un'immagine numerata, e
**Mostrami sullo schermo** apre la pagina giusta e indica dove cliccare, un fumetto per
volta. La guida si stampa o si salva in PDF.

**Novità della 1.4.3.** All'avvio si apre **Oggi**: chi aspettare adesso, interventi,
cose da fare, appunti, telefonate, cassa. Per la **sala operatoria**: la **checklist
pre-operatoria** di ogni intervento (con il contatore nella griglia e l'avviso il giorno
prima), la **lista operatoria** da stampare, la **degenza** (DH, una notte, ricovero) e i
**posti letto** con l'avviso quando non bastano, i **giorni di sala dei chirurghi** (chi
opera oggi e chi è ancora libero). Da Statistiche, il **riepilogo del mese per medico** da
stampare, scaricare in Excel o mandare per email.

**Novità della 1.4.2.** Il **tema scuro** per lo schermo (chiaro, scuro o come Windows) e
il **foglio del giorno** su misura: quali colonne stampare, A4 orizzontale o verticale,
una tabella per stanza o tutto in ordine di ora. Tutti e due da Impostazioni.

**Novità della 1.4.1.** Gli **appunti da confermare**: le prenotazioni che non si possono
ancora mettere in agenda (stanza da decidere, sala già occupata, paziente da richiamare)
hanno un posto loro, compaiono in cima alla giornata e con *Prenota* diventano
appuntamenti; le importazioni ci mettono le righe in conflitto o incomplete invece di
lasciarle fuori. L'importazione riconosce anche le agende vere dell'accettazione che non
seguono i modelli (vedi *Importare da Excel*).

**Novità della 1.4.** Importazione da Excel e CSV della rubrica e delle agende;
chiusura della giornata; lista d'attesa con chi chiamare quando si libera un posto;
spostare un appuntamento o tutti quelli di un medico; appuntamenti in serie; cassa con
listino, pagamenti e chiusura di cassa; agenda del giorno per ogni medico; moduli da
stampare con le date già calcolate; documenti allegati alla scheda; da dove arrivano i
pazienti; note del giorno; cose da fare con notifiche a scomparsa; ricerca rapida e
tasti rapidi.

**Novità della 1.3.** Schede paziente con cellulare, email, codice fiscale e storico;
stato degli appuntamenti (arrivato, disdetto, non presentato); vista settimanale e
mensile; assenze, ferie, chiusure, festivi e turni di un giorno solo; pagina delle
conferme con WhatsApp ed email già scritti; stampa A4 del giorno; prima disponibilità
di un medico; statistiche di saturazione; orari e fasce per struttura; backup
automatico con ripristino dal programma.

## Installare

Doppio clic su `GestionaleAgende-setup.exe`, poi **Avanti** e **Fine**. Non servono
Python né diritti di amministratore. L'installatore è lo stesso per tutte le sedi.

L'installatore mette il programma nel profilo di chi lo lancia
(`%LOCALAPPDATA%\Programs\Gestionale Agende`), crea l'icona *Agende* sul desktop e la
voce nel menu Start, e registra l'avvio automatico all'accesso a Windows. All'accesso
il gestionale parte in silenzio, senza aprire il browser: la pagina la apre l'icona
*Agende*. Cliccarla con il programma già attivo apre solo il browser.

Va lanciato **dall'utente che userà il programma**, non da un amministratore: con i
diritti di amministratore collegamenti e avvio automatico finirebbero nel profilo di chi
ha digitato la password.

Il file non è firmato digitalmente, quindi al primo avvio Windows può mostrare *"Windows
ha protetto il PC"*: si sceglie **Ulteriori informazioni** e poi **Esegui comunque**.

**Aggiornare a una versione nuova.** Non serve disinstallare la vecchia: si avvia il
Setup nuovo (`GestionaleAgende-setup.exe`) e basta. Se trova il gestionale già installato lo dice nella prima
pagina (*"È installata la versione 1.5: verrà aggiornata alla 1.6"*), lo chiude se è aperto, sostituisce il programma e alla fine lo riapre.
Appuntamenti, pazienti, documenti e impostazioni stanno in `%LOCALAPPDATA%\GestionaleAgende`,
fuori dalla cartella del programma: l'aggiornamento non li tocca. Se la versione nuova
cambia il database, al primo avvio ne fa prima una copia
(`backup\agende-…-prima-della-versione-7.db` accanto ai dati) e poi aggiunge solo le
colonne e le tabelle nuove. Il Setup di una versione più vecchia di quella installata
avvisa prima di tornare indietro. Dalla 1.6 la strada più corta è dentro il programma:
**Aggiorna adesso** (sotto).

Anche la **disinstallazione** lascia i dati al loro posto, e lo dice; reinstallando, il
Setup avvisa che ha trovato appuntamenti salvati e il programma li ritrova tutti. La
cartella dei dati va cancellata a mano, e solo dopo averne messo via una copia.

## Aggiornamenti dal programma

**Per la segreteria.** Quando esce una versione nuova compare la notifica *Aggiornamento
disponibile*. La pagina *Configura → Aggiornamenti* dice quale versione è installata,
quale è pronta e cosa porta di nuovo; **Aggiorna adesso** fa il resto:

1. copia di sicurezza del database, fra i backup come *prima di aggiornare*;
2. se in quel momento sta partendo un'email, la lascia finire;
3. avvia il Setup senza domande: per qualche secondo si vede la sua barra di avanzamento.
   Il Setup chiude il gestionale, lo sostituisce e lo riapre;
4. la pagina rimasta aperta nel browser aspetta che il programma torni e mostra le
   novità, con i loro video.

Circa un minuto, senza disinstallare e senza toccare appuntamenti, pazienti, documenti e
impostazioni. Se qualcosa va storto il programma resta alla versione di prima, con tutti i
dati, e al riavvio lo dice (notifica *Aggiornamento non riuscito*, con il registro del
Setup per l'assistenza). Il Setup si può sempre avviare anche a mano.

**I certificati dei siti (1.12).** Il controllo degli aggiornamenti e l'invio delle email si fidano
dei certificati che conosce Windows, più l'elenco delle autorità riconosciute da Mozilla portato
dentro il programma (il pacchetto `certifi`, `comune.contesto_tls`) e, se c'è, del file
`certificati.pem` accanto al database (per una rete con un proxy o un antivirus che riscrive i
certificati: ci si mette il suo). Perché: Windows parte con pochi certificati e aggiunge una
radice nuova al suo elenco solo la prima volta che la incontra con Edge o con un suo programma; il
gestionale usa l'elenco così com'è, e quando GitHub è passato a radici nuove (2025) la 1.9 sul PC
della clinica diceva *il certificato del sito degli aggiornamenti non è valido* mentre il browser
apriva il sito senza problemi. Dalla 1.12 non dipende più da cosa ha già visto Windows; se un
controllo non riesce lo stesso, la pagina dice il motivo in parole semplici (autorità sconosciuta,
scaduto o data del PC sbagliata, un altro sito in mezzo) e il collegamento alla pagina delle
versioni per scaricare il Setup dal browser. Per la versione installata che ha ancora il difetto:
aprire una volta `https://github.com` con Edge (Windows scarica la radice) e poi *Controlla
adesso*, oppure il Setup nuovo a mano.

**Da dove arrivano.** Dalle versioni pubblicate su GitHub, nel progetto
`https://github.com/number959/gestionale-agende-versioni`: è l'indirizzo predefinito, già
scritto nel programma, e alla clinica non c'è niente da impostare. Il programma prende
sempre l'ultima versione pubblicata (`…/releases/latest/download/`). In *Configura →
Aggiornamenti → Da dove arrivano* se ne può scrivere un altro:

- l'indirizzo di un altro progetto su GitHub, `https://github.com/<utente>/<progetto>`;
- un altro indirizzo https, o una cartella condivisa (`\\server\aggiornamenti`, la
  cartella di Google Drive sincronizzata sul PC).

Lì il programma cerca `aggiornamento.json` (nella versione animata
`aggiornamento-animata.json`), il file delle versioni che `CREA_SETUP.bat` scrive accanto
al Setup. Lasciato vuoto, gli aggiornamenti automatici sono spenti; *Rimetti l'indirizzo
predefinito* torna a quello di GitHub. Un indirizzo `http://` non si accetta: lungo la
strada qualcuno potrebbe cambiare il file. Finché nel progetto non c'è una versione
pubblicata la pagina lo dice: *"lì non è stata ancora pubblicata nessuna versione"*.

**Quando.** Due minuti dopo l'avvio, poi ogni sei ore, oppure con *Controlla adesso*. Se
c'è una versione più nuova il Setup si scarica in sottofondo, in
`%LOCALAPPDATA%\GestionaleAgende\aggiornamenti`, e si controlla prima di proporlo:
dimensione e impronta SHA-256 uguali a quelle del file delle versioni, intestazione di un
programma Windows. Un file diverso, troncato o non scaricabile non viene mai installato: la
pagina dice perché e il programma riprova al giro dopo. I rimandi del sito (GitHub manda i
file a un altro indirizzo) si seguono solo se restano https. I Setup già installati si
cancellano da soli al riavvio.

**Come funziona dentro.** Il Setup parte con `cmd /c start` e i parametri
`/SILENT /NOCANCEL /SUPPRESSMSGBOXES /NORESTART /LOG=…`: con `start` non è un processo
figlio del gestionale, così il `taskkill /T` con cui il Setup chiude il gestionale non
chiude anche lui. Alla fine il Setup riapre il programma con `--avvio-automatico` (la voce
`[Run]` con `Check: WizardSilent` in `installer.iss`), senza aprire un'altra pagina del
browser: quella rimasta aperta se ne accorge perché a ogni avvio cambia il valore
`avviato` di `/aggiornamenti/stato.json`. Un file `in-corso.json` nella cartella degli
aggiornamenti dice al primo avvio da quale versione si veniva e a quale si andava: così il
programma sa se l'aggiornamento è riuscito. La versione normale e l'animata leggono
ciascuna il suo file delle versioni e installano il loro Setup. Tutto è in
`aggiornamenti.py`.

## Pubblicare un aggiornamento

Per chi sviluppa. Le versioni si pubblicano nel progetto pubblico
`number959/gestionale-agende-versioni`, che contiene solo quelle ("Releases"): il programma
le scarica senza password, e il codice può stare altrove. Il suo indirizzo è
`INDIRIZZO_PREDEFINITO`, in `aggiornamenti.py`: se un giorno cambia, si cambia lì e vale
dalla versione costruita dopo (i PC su cui nessuno ha scritto un altro indirizzo seguono da
soli quello nuovo). GitHub non accetta versioni in un progetto vuoto: la prima volta serve
almeno un file, per esempio un `README.md` (nella pagina del progetto vuoto, *creating a
new file*).

A ogni versione:

1. il numero nuovo in `comune.py` (`VERSIONE`) e in `installer.iss` (`#define Versione`),
   in tutte e due le cartelle; in `novita.py` una voce per ogni novità, in parole semplici,
   con la guida che la spiega;
2. le prove; immagini e video delle guide se le pagine sono cambiate (*Aiuto e guida*);
3. in ciascuna cartella `CREA_EXE.bat` e `CREA_SETUP.bat`: in `Output` ci sono il Setup e
   il file delle versioni (`GestionaleAgende-setup.exe` e `aggiornamento.json`;
   nell'animata `GestionaleAgende-animata-setup.exe` e `aggiornamento-animata.json`);
4. la versione su GitHub con i quattro file: dalla pagina del progetto, *Releases → Create
   a new release* (tag `v1.10`, titolo *Gestionale Agende 1.10*, i quattro file trascinati
   nel riquadro dei file, *Set as the latest release* lasciato acceso, *Publish release*),
   oppure con la riga di comando `gh`:

   ```
   gh release create v1.10 --repo number959/gestionale-agende-versioni --latest ^
     --title "Gestionale Agende 1.10" --notes "Le fasce di ogni ambulatorio" ^
     gestionale\Output\GestionaleAgende-setup.exe gestionale\Output\aggiornamento.json ^
     gestionale-animata\Output\GestionaleAgende-animata-setup.exe gestionale-animata\Output\aggiornamento-animata.json
   ```

Entro sei ore il gestionale della clinica la trova da solo; con *Controlla adesso*,
subito. Il file delle versioni va pubblicato insieme al suo Setup: se il Setup non
corrisponde all'impronta scritta nel file, il programma non lo installa. Per controllare la
pubblicazione basta aprire nel browser
`https://github.com/number959/gestionale-agende-versioni/releases/latest/download/aggiornamento.json`:
deve dire la versione nuova.

## Primo avvio

Al primo avvio vengono create una struttura chiamata *La mia struttura*, sei stanze e
sei prestazioni. Medici e turni no: si inseriscono da **Anagrafiche** (stanze, medici e turni), e
finché mancano la griglia e il modulo di prenotazione lo dicono e rimandano lì.

L'ordine è: nome e logo della struttura, medici, poi turni. La guida in cima a
**Anagrafiche** segue questi passi e barra quelli fatti. Sono i turni a far
comparire libere le fasce nella griglia; si ripetono ogni settimana nel giorno scelto,
oppure valgono per una data sola (*Ripetizione: un giorno solo*), come il giorno non
fisso del dott. Galasso o una sostituzione. Aprendo una fascia libera, il modulo di
prenotazione propone il medico di turno in quella stanza a quell'ora.

Regole controllate dal programma:

- una stanza ha un medico alla volta: due turni sovrapposti nella stessa stanza sono
  rifiutati, lo stesso medico su due stanze insieme è ammesso (visite su due ambulatori);
- non si elimina un medico, una stanza o una prestazione che ha appuntamenti o turni: si
  disattiva, e resta visibile negli appuntamenti già presi;
- non si disattiva una stanza con prenotazioni da oggi in poi, perché sparirebbero dalla
  griglia.

## Fasce dei turni

Fino alla 1.9.1 le fasce erano una misura sola per tutta la struttura (*Configura →
Anagrafiche*, la struttura, *Fasce*: 10, 15, 20, 30 o 60 minuti). Dalla 1.10 ogni turno può
averne di sue: nel modulo del turno, **Durata delle fasce** (10, 15, 20, 30, 40, 45 o 60
minuti; *Come la struttura* lascia quelle di tutta la clinica). Le fasce di un turno
cominciano dall'ora di inizio del turno: un turno dalle 9 alle 12 con fasce da 20 ha le fasce
delle 9:00, 9:20, 9:40… fino a quella delle 11:40. È la "programmazione" dell'ambulatorio.

- **Fasce intere.** Un appuntamento occupa tutte le fasce che tocca, dall'inizio della prima
  alla fine dell'ultima: una visita da 30 minuti alle 9:00 con fasce da 20 occupa 9:00-9:40, un
  esame da 10 minuti alle 10:20 occupa 10:20-10:40. Nella stessa stanza un altro appuntamento
  non entra in una fascia occupata, anche se gli orari veri non si toccano: il programma lo
  dice («la fascia delle 09:20 è già occupata dall'appuntamento delle 09:00-09:30…») e non
  salva. Il medico invece conta con i suoi orari veri, come prima.
- **Griglia.** In testa alla colonna, *fasce da 15'*. Le righe diventano più fitte (la misura
  comune alle fasce della struttura e a quelle dei turni: con fasce da 30 e da 15, righe da 15
  minuti; con 30 e 20, righe da 10) e sono alte in proporzione al tempo, con l'ora scritta
  sulle fasce della struttura. Ogni fascia libera di un turno con fasce sue dice la sua ora
  («09:40»; *libero* compare passando con il mouse) e un clic apre il modulo a quell'ora, con
  il medico di turno. Le colonne senza fasce proprie restano a fasce della struttura. In una
  fascia corta medico e paziente stanno su una riga sola. Lo stesso nell'agenda della
  settimana del medico (che in testa al giorno dice anche le fasce del turno); nell'Excel del
  giorno le righe sono quelle fitte, con le celle unite.
- **Prima disponibilità e Sposta** propongono gli inizi delle fasce libere. Nei turni senza
  fasce proprie, come prima: il passo della struttura dall'inizio del turno.
- **Orario a mano.** Un'ora che non è l'inizio di una fascia si può scrivere (un paziente in
  ritardo, un esame infilato): si salva, con l'avviso «alle 09:30 non ne comincia una,
  l'appuntamento occupa la fascia intera (09:20-10:00)».
- **Appuntamenti già presi.** Cambiando le fasce di un turno, gli appuntamenti già prenotati
  restano dove sono, nella fascia in cui cominciano. Se qualcuno comincia a metà di una fascia
  o ne divide una con un altro, salvando il turno il programma lo dice («Ci sono 2
  appuntamenti già prenotati in questo turno che non stanno nelle fasce da 20 minuti…», con
  il primo), da controllare nella griglia. Si possono sempre modificare (nota, paziente,
  medico): contano solo le fasce nuove che un appuntamento prenderebbe, non quelle che
  divideva già. Rimettere attivo un disdetto, invece, controlla tutto. L'importazione da
  Excel guarda solo gli orari veri: le prenotazioni già decise nei fogli entrano come sono,
  come quelle prese prima delle fasce.
- Senza turni con fasce proprie tutto è come nella 1.9.1, griglia compresa: le prove lo
  confrontano con le funzioni della 1.9.1 su centinaia di giorni inventati.

Dentro: la colonna `turni.passo` (schema 11; vuota = come la struttura) e
`Turno.passo_proprio`; in `servizi.py` `base_righe` (le righe della tabella), `pezzi_colonna`
(la colonna divisa nelle sue fasce), `celle_colonna` (le celle della griglia e dell'agenda del
medico), `blocco` (le fasce intere di un appuntamento) e `turno_con_fasce`, usate da
`griglia`, `settimana_medico`, `conflitti`, `fuori_turno` e `disponibilita`; nei modelli
`griglia.html` e `settimana.html` la tabella a righe fitte (`tbody.fasce-miste`).

## Nome, logo e colori

Da **Anagrafiche**, tabella *Strutture*, voce **Nome, logo e colori**.

- **Logo**: PNG o JPG (anche GIF, WEBP, BMP), al massimo 3 MB. I margini vuoti vengono
  tolti e lo sfondo bianco attorno al disegno diventa trasparente, così sulle pagine
  grigie non resta un riquadro; il bianco dentro il disegno resta. Senza logo, al suo
  posto compare il nome della struttura. L'SVG non è ammesso: può contenere codice.
- **Colore dell'interfaccia**: caricando un logo, se il colore non è stato toccato, si
  propone quello del logo. Un colore troppo chiaro per il testo bianco di intestazioni e
  pulsanti viene scurito quanto basta (contrasto 4,5:1, il minimo WCAG per il testo) e
  il programma lo dice.
- **Società**: la ragione sociale, in fondo a ogni foglio esportato in Excel. Il foglio
  porta anche logo e nome della struttura nel titolo.

Il logo non viene salvato così com'è: il programma lo decodifica, lo rifila, lo riduce
a 160 pixel di altezza e lo salva come PNG nuovo dentro il database. Nel database non
finisce mai il file originale, con i suoi metadati, e il backup resta un file solo.

**Più strutture.** *Aggiungi struttura* ne crea un'altra, con logo e colore suoi. Le
stanze si assegnano alla struttura dal loro modulo; una struttura appena creata non ne
ha, e la sua griglia lo dice con il collegamento per aggiungerle. Il menu in alto nella
griglia passa da una struttura all'altra, e ogni pagina prende logo e colore di quella
che si sta guardando. Nel modulo di prenotazione le stanze sono raggruppate per
struttura, con quelle della struttura da cui si arriva per prime; dopo il salvataggio
si torna alla giornata della struttura in cui l'appuntamento sta. Non si elimina una
struttura che ha stanze, né l'unica rimasta.

**Recapiti e orari.** Nello stesso modulo: indirizzo, telefono ed email della
struttura (finiscono nei messaggi ai pazienti e sulla stampa), ora di apertura e
chiusura, durata delle fasce (10, 15, 20, 30 o 60 minuti), giorni di apertura, patrono
(gg/mm) e la scelta *Chiusa nei festivi*. Il predefinito è 08:00–20:00 a mezz'ora, dal
lunedì al sabato, come la 1.2.

**Aggiornamento dalla 1.1.** Al primo avvio il database riceve da solo le colonne
nuove, senza toccare i dati, e le strutture con *Posillipo* nel nome ricevono il logo
della clinica che la 1.1 aveva incorporato. Succede una volta sola: un logo tolto a mano
non torna al riavvio.

**Il logo nuovo (1.5).** Aggiornando alla 1.5, le strutture che mostrano ancora il logo
precedente della clinica (*Casa di Cura Clinica Posillipo · Gruppo NefroCenter*) ricevono
quello nuovo, *Clinica Posillipo · Longevity Institute*: a video, nelle stampe, nei fogli
Excel e nella firma delle email. Il programma riconosce il logo vecchio dal disegno, non
dal nome della struttura; un logo diverso caricato a mano resta com'è, una struttura senza
logo resta senza. Anche questo succede una volta sola.

## Pazienti

Menu **Pazienti**. La ricerca accetta cognome, nome, telefono (con o senza +39, spazi,
punti) o codice fiscale, e non bada ad accenti e maiuscole: *de rosa* trova *DE ROSA* e
*De Rosà*. La scheda ha due telefoni, email, sesso, data (con l'età) e luogo di nascita,
codice fiscale, indirizzo, note, il consenso ai promemoria e il canale preferito (WhatsApp, SMS o email),
più lo storico degli appuntamenti con i conteggi di presenze, disdette e mancate presenze.

- **Nel modulo di prenotazione**, in *Cerca in anagrafica*, si scrivono le prime
  lettere del cognome o il telefono e compaiono le schede che corrispondono (si sceglie
  con le frecce e Invio, o con il mouse): i campi si riempiono e l'appuntamento resta
  legato a quella scheda. Un paziente nuovo non va cercato: basta scrivere cognome e
  telefono e la scheda si crea da sola. Cambiando il cognome dopo la scelta il legame si
  scioglie, e il programma cerca o crea la scheda giusta.
- **Nascita, codice fiscale, indirizzo** anche nel modulo di prenotazione: finiscono
  nella scheda (un campo lasciato vuoto non cancella quello che la scheda ha già). Il
  codice fiscale si controlla e si calcola come nella scheda (vedi *Codice fiscale*). Un
  paziente con lo stesso cognome e codice fiscale è
  riconosciuto anche se chiama da un altro numero (che va nel secondo telefono); con lo
  stesso telefono ma un altro codice fiscale, per esempio un figlio, si crea una scheda
  nuova.
- **Controlli**: il codice fiscale (vedi *Codice fiscale*), l'email nella forma, il
  telefono nel numero di cifre (almeno 6). Un valore sbagliato rimanda la scheda con il
  messaggio e i dati già scritti.
- **Doppioni**: creando una scheda con lo stesso cognome e nome, lo stesso telefono, la
  stessa email o lo stesso codice fiscale di un'altra, il programma mostra le schede simili e chiede conferma.
  **Unisci** sposta tutti gli appuntamenti su una scheda sola, completa i campi vuoti con
  quelli dell'altra, accoda le note ed elimina il doppione.
- **Avvisi in prenotazione**: se il paziente ha già un appuntamento quel giorno, o due o
  più mancate presenze nell'ultimo anno, lo dice al salvataggio.
- **Come ci ha conosciuto** e **Inviato da** (il medico o la persona che lo manda): si
  scelgono nella scheda o, per un paziente nuovo, già nel modulo di prenotazione. Le
  statistiche contano i pazienti nuovi per provenienza e chi li manda.
- **Documenti**: in fondo alla scheda si allegano impegnative, referti, consensi
  firmati, in PDF, JPG o PNG fino a 10 MB. Il tipo si riconosce dal contenuto, non dal
  nome: un eseguibile rinominato ".pdf" viene rifiutato. I file stanno nel database,
  quindi finiscono nei backup (che crescono di conseguenza).
- Unendo due schede, appuntamenti, documenti, cose da fare, lista d'attesa e messaggi
  mandati passano alla scheda che resta.
- Una scheda si elimina solo se non ha appuntamenti né documenti.

## Codice fiscale

**Per la segreteria.** Nella scheda del paziente e nel modulo di prenotazione ci sono
*Sesso*, *Data di nascita*, *Luogo di nascita* e *Codice fiscale*.

- Il codice si scrive com'è sulla tessera sanitaria, anche minuscolo o con gli spazi.
  Mentre lo si scrive, sotto il campo compare *Codice fiscale corretto* oppure cosa non
  va: quanti caratteri mancano, quale posto ha una lettera al posto di una cifra, una
  data che non esiste (il 30 febbraio), o che il carattere di controllo, l'ultimo, non
  torna (con la lettera che ci andrebbe: di solito vuol dire un errore di battitura in un
  altro punto). Un codice sbagliato non si salva: il modulo torna con il messaggio e
  tutti i dati scritti.
- Da un codice giusto si riempiono da soli data, sesso e luogo di nascita lasciati vuoti
  (o riempiti prima dal codice: cambiando codice si aggiornano). Quelli scritti a mano
  restano; se non tornano con il codice, sotto il campo e al salvataggio compare un
  avviso (le lettere del cognome o del nome, la data, il sesso, il luogo), perché uno dei
  due è sbagliato. Fa fede la tessera sanitaria.
- **Senza codice**: con cognome, nome, sesso, data e luogo di nascita il codice si
  calcola da solo, e lo dice (*Calcolato dai dati: controllarlo sulla tessera
  sanitaria*): in rari casi, l'omocodia, l'Agenzia delle Entrate assegna un codice
  diverso. Un codice calcolato non prende mai il posto di quello già nella scheda.
- **Il luogo di nascita** si sceglie dall'elenco che compare scrivendo le prime lettere
  (*s giorgio cre* trova *San Giorgio a Cremano (NA)*): tutti i comuni italiani, anche
  quelli soppressi o rinominati con il periodo in cui sono esistiti (per chi è nato
  allora vale il comune di allora), e gli stati esteri, anche quelli che non esistono
  più (Jugoslavia, URSS). Due comuni con lo stesso nome si distinguono dalla provincia;
  un nome scritto per intero senza sceglierlo va bene se è uno solo.
- **Controllo dei codici fiscali** (pulsante nella pagina *Pazienti*): i codici già
  salvati che non sono validi, con il motivo; quelli validi che non corrispondono ai dati
  della scheda; lo stesso codice su più schede (di solito un doppione, con *Unisci*); le
  schede con tutti i dati ma senza codice (*Calcola e salva*, dopo una copia di
  sicurezza); e chi è senza codice e senza i dati per calcolarlo, a partire da chi ha un
  appuntamento in programma, così i dati si chiedono quando viene.
- Aggiornando alla 1.7, dai codici validi già in archivio si ricavano sesso, luogo e data
  di nascita dove mancano (una data già scritta non si tocca), dopo la solita copia di
  sicurezza del database.
- Nei moduli da stampare e nelle email ci sono anche `{luogo_nascita}` e `{sesso}`.

**Come funziona dentro.** Tutto il codice fiscale è in `codice_fiscale.py`, senza Flask e
senza database: controllo (forma, data esistente in uno dei due secoli possibili,
carattere di controllo, con il motivo), lettura (anche dei codici omocodici: le cifre
diventate lettere tornano cifre), calcolo, confronto con i dati, ricerca dei luoghi. La
scheda, la prenotazione, l'importazione, l'unione delle schede e l'aggiornamento dello
schema (versione 8) usano le stesse funzioni; la pagina chiede il controllo al programma
mentre si scrive (`/pazienti/codice-fiscale`, `/pazienti/luoghi`), così il controllo è uno
solo. I luoghi stanno in `dati/luoghi_nascita.json` (circa 15 mila righe: comuni con il
periodo in cui sono esistiti, stati esteri), scritto da
`strumenti/genera_luoghi_nascita.py` dai dati ISTAT e ANPR raccolti nel pacchetto
python-codicefiscale (licenza MIT, Fabio Caccamo); il programma non usa il pacchetto e
funziona senza internet. Per aggiornare l'elenco quando nascono comuni nuovi:
`pip install -U python-codicefiscale`, poi `python strumenti/genera_luoghi_nascita.py` e
le prove. Il calcolo e la lettura sono confrontati in `prove_17.py` con il pacchetto, su
migliaia di casi generati.

## Stato degli appuntamenti

Ogni appuntamento è *Prenotato*, *Confermato*, *Arrivato*, *Non presentato* o
*Disdetto*. I pulsanti sono nell'elenco del giorno e nel modulo; nella griglia un segno
distingue confermati e arrivati. *Arrivato* registra l'ora d'arrivo e l'elenco mostra
l'attesa. Disdetti e non presentati liberano la fascia: escono dalla griglia e restano
in una striscia sotto, da cui si possono riattivare se la fascia è ancora libera. Ogni
cambio di stato finisce nel registro delle modifiche dell'appuntamento.

Nel modulo ci sono anche **Tipo** (prima visita, controllo, prestazione, urgenza),
**Convenzione / assicurazione**, **Importo** (formato italiano, *80* o *1.250,50*) e i
**campi in più della prestazione**: in *Prestazioni* si scrivono separati da virgola,
per esempio `Sedazione?, Anestesista, Preparazione consegnata?`; quelli con il punto
interrogativo diventano un sì/no. Il testo *Preparazione* della prestazione finisce nel
promemoria al paziente.

## Viste e stampe

- **Elenco** (del giorno): gli appuntamenti in ordine d'ora, con telefono, stato e
  pulsanti. È la vista da tenere aperta in accettazione.
- **Settimana**: sette colonne con gli appuntamenti; con *Medico* si vede la settimana di
  un medico solo, fascia per fascia, come le agende Excel per medico (con le fasce dei suoi
  turni e un appuntamento alto quanto le fasce che occupa, come nella griglia).
- **Mese**: per ogni giorno il numero di appuntamenti, i medici, i festivi e la **sala
  operatoria**: quanti interventi e di quali chirurghi (*Sala 3: Borrelli (2), Lippi*) e,
  da oggi in poi, chi opera di solito quel giorno ed è ancora libero (*sala libera*). Con
  il filtro sul medico, solo i suoi. Un clic apre il giorno.
- **Stampa**: il giorno su A4, per ora o per stanza, con recapiti e note, pronto per
  *Ctrl+P*. In testa i recapiti della struttura, email compresa (anche nei moduli e nella
  lista operatoria). Dal modulo, *Promemoria* stampa il foglietto da dare al paziente, con
  indirizzo e preparazione.
- **Disponibilità** (la prima): medico, durata ed eventualmente fascia oraria o stanza;
  dà le prime fasce libere nei prossimi 60 giorni rispettando turni (con le loro fasce, se
  ne hanno di proprie), assenze, chiusure e festivi. Un clic apre il modulo già compilato.
- **Statistiche**: per un periodo, saturazione di ogni stanza (ore prenotate su ore di
  turno), appuntamenti per medico con il tasso di mancate presenze, per prestazione,
  tipo e giorno della settimana, pazienti nuovi. Si scaricano in Excel. L'export del
  giorno ora ha anche un secondo foglio *Elenco* con tutti i campi.


**Il foglio del giorno dalla 1.12.** La pagina di stampa è una tabella con testata (`thead`) e piede
(`tfoot`): il browser li ripete su ogni foglio stampato, e nel margine in basso a destra c'è
«Pagina X di Y» (`@page` con `counter(pages)`, Chrome ed Edge recenti). Ogni stanza dice quanti
appuntamenti ha, chi è di turno e chi è assente; le stanze con un medico di turno ma senza
appuntamenti compaiono lo stesso (non le sale operatorie); le colonne in più (sedazione, anestesista…)
compaiono solo nella tabella della stanza che le usa; sotto ogni tabella il totale degli importi
degli appuntamenti attivi, nel piede quello del giorno; con *anche disdetti e non presentati* la
colonna Stato (con l'ora di arrivo), i disdetti barrati in grigio, i non presentati in marrone e
una legenda. Due colonne in più a scelta: la data di nascita e una casella da spuntare a penna
(arrivato, pagato). In *Impostazioni → Foglio del giorno* si salva anche «anche disdetti e non
presentati» (`tutti`); nell'indirizzo `tutti=0` o `tutti=1` vince per quella stampa. Il pulsante
*Stampa* dell'elenco del giorno segue le preferenze salvate; l'elenco stampato con Ctrl+P perde
pulsanti e collegamenti rapidi, ripete le intestazioni e stampa la nota del giorno.


**Gli Excel dalla 1.12: un aspetto solo.** Tutti i file Excel (planning e elenco del giorno,
statistiche, incassi, riepilogo medici, turni del personale, registro di Dove si fa, matrice e
programmazione degli ambulatori) passano dagli aiuti di `comune.py`: `apri_foglio_excel` (titolo con
la struttura, sottotitolo con il periodo, «Esportato il … dal Gestionale Agende»), `tabella_excel`
(intestazione bianca su blu, bordi, formati di ore, euro e date, righe dei totali, filtri, riquadri
bloccati), `imposta_stampa_excel` (A4 adattato in larghezza, intestazioni ripetute su ogni pagina,
intestazione e piè di pagina con struttura, periodo e «Pagina X di Y»). Il planning del giorno mostra
anche i turni dei medici nell'intestazione di ogni stanza, le fasce libere nel turno in azzurro e
quelle fuori turno in grigio, con la legenda; l'elenco ha i disdetti barrati e la riga dei totali
dei soli attivi. La prova `prove_112_excel.py` riapre ogni file e controlla formato, intestazioni,
piè di pagina e totali.

## Ambulatori

Dalla 1.12. Menu *Ambulatori*: chi sta in quale stanza, calcolato dai turni dei medici (quelli
di *Configura → Anagrafiche*), in due pagine nate da fogli che in due strutture del gruppo si
compilavano a mano. Tutto in `ambulatori.py`; le sale operatorie si programmano in *Sala* e restano
fuori dai conti degli ambulatori, ma dalla 1.12.3 la settimana e il mese le mostrano in una parte loro
(vedi *La sala operatoria nella settimana e nel mese*).

- **Pianificazione della settimana** (`/ambulatori/settimana/<data>`): una riga per stanza attiva,
  una colonna per la mattina (dall'apertura alle 14) e una per il pomeriggio (dalle 14 alla
  chiusura) di ogni giorno di apertura. In ogni cella chi occupa la stanza con l'orario; una cella
  senza nessuno è **DISPONIBILE**, in verde; se dentro una mezza giornata occupata avanza almeno
  un'ora, la cella dice *libero* e da che ora a che ora. Un medico assente lascia la stanza libera
  solo in quella settimana (e lo si legge: *assente: ferie*); un giorno di chiusura, o un festivo
  in cui la struttura chiude, è grigio. È anche la pianificazione: il **+** in alto a destra di
  una cella (solo da oggi in poi) apre un modulo con il medico, le ore (proposte quelle libere) e
  la ripetizione, *ogni settimana da questa in poi* (un turno valido da quel giorno) oppure *quel
  giorno solo* (un turno di un giorno); le regole sono quelle della scheda del turno
  (`anagrafiche.stanza_gia_assegnata`: una stanza ospita un medico alla volta, con le eccezioni
  delle sostituzioni). Il nome apre la scheda del turno, che poi torna qui (`torna`); la **×** lo
  toglie da quella settimana in poi: un turno di un giorno, o che comincia in quella settimana o
  dopo, si elimina; uno che veniva da prima si chiude la domenica precedente (*Fino al*), così le
  settimane già fatte e le statistiche restano com'erano.
- **La matrice in Excel** (*Stampa e scarica → La matrice in Excel*,
  `/ambulatori/settimana/<lunedì>.xlsx`): il foglio *Matrice turni ambulatori e disponibilità
  integrative* chiesto dalla direzione sanitaria, già compilato: nome della struttura, titolo,
  settimana, destinatario e chi lo compila, la tabella stanze × mezze giornate con *DISPONIBILE*
  in verde pieno e le ore libere in verde chiaro, la legenda, la data del calcolo e le righe per
  le firme; una pagina A4 orizzontale. Con `?tipo=1` (*La settimana tipo in Excel*) solo i turni
  che si ripetono, senza assenze, chiusure e turni di un giorno.
- **Programmazione del mese** (`/ambulatori/mese/<aaaa-mm>` e `.xlsx`): il foglio *programmazione
  ambulatori* di un'altra struttura del gruppo, ma calcolato: una riga per turno, raggruppate per
  specialità del medico (dalla sua scheda; senza specialità in fondo), con il giorno della
  settimana, le **date del mese in cui il medico viene davvero** (tolte assenze, chiusure e festivi
  in cui si chiude), l'orario, la stanza e le note che si scrivono da sole: *un giorno solo*,
  *dal 15*, *fino al 20*, *non il 2 e il 9 (assente: ferie)*, *nessuna seduta nel mese*, *fasce
  da 20 minuti*. In fondo alla pagina il calendario del mese; nell'Excel è un secondo foglio.
  Perché così e non ricopiato: il foglio a mano andava riscritto ogni mese e si allontanava
  dall'agenda (le date saltate le scriveva una persona); qui non può dire una cosa diversa.
- **La sala operatoria nella settimana e nel mese** (dalla 1.12.3, richieste di Giovanni del 9 novembre
  2026: «accorpare le esportazioni della sala e quelle degli ambulatori», poi «esportazioni singole
  giornaliere, settimanali e mensili rispettivamente di ambulatori e sale operatorie, e un'esportazione
  unica che accorpi tutto per giorno, settimana e mese»). Le sale operatorie attive
  (`ambulatori.sale_della`) stanno in fondo alla pianificazione della settimana e alla programmazione del
  mese, in una parte loro e solo da guardare (niente + e ×: la sala si programma da *Sala*). Nella
  settimana una riga per sala con, per ogni mattina e pomeriggio, i chirurghi in turno, quanti
  interventi attivi (prenotati, confermati, arrivati: `interventi_attivi`; i disdetti e i non presentati
  no) e, per nome, chi ha interventi senza un turno in quella mezza giornata; «sala libera» solo senza
  turni e senza interventi; un intervento prima dell'apertura sta nella mattina, uno dopo la chiusura nel
  pomeriggio (`intervento_nella_meta`), e allo stesso modo un turno di sala fuori dall'orario della
  struttura si vede con le sue ore vere (in sala la prima mezza giornata comincia a mezzanotte e l'ultima
  finisce a mezzanotte); il testo di una cella è uno solo (`testo_cella_sala`), uguale in pagina e negli
  Excel. Nel mese, dopo le specialità, i turni dei chirurghi con le date e gli interventi
  nelle ore di ciascun turno (ogni intervento conta in un turno solo, il primo per ora di inizio, anche
  con due turni sovrapposti dello stesso chirurgo), una riga per chi ha operato fuori dai suoi turni e la
  frase con gli interventi del mese (`frase_sala_mese`); nel calendario le righe della sala con la colonna
  *Interventi* («fuori turno» per gli interventi fuori dalle ore dei turni) e, nei giorni senza medici
  nelle stanze, prima la riga grigia con il motivo (chiusura, festivo, «solo sala operatoria»). **I conti degli ambulatori non cambiano** (mezze giornate libere e con ore libere restano
  delle stanze); un giorno che c'è solo per la sala (turni o interventi in sala in un giorno in cui la
  struttura non apre) compare nella pagina e nei fogli della sala, con le stanze *chiusa: solo sala
  operatoria* (`GIORNO_SOLO_SALA`), ma non nella matrice per la direzione né nel riepilogo live, che
  restano quelli di prima.
- **Esportazioni in Excel** (dalla 1.12.3; `esportazioni.py`, menu *Ambulatori → Esportazioni in Excel*,
  `/esportazioni?data=` e `/esportazioni/<giorno|settimana|mese>/<ambulatori|sala|tutto>/<data>.xlsx`):
  nove file, una tabella con una riga per il giorno, la settimana e il mese della data scelta e una
  colonna per solo gli ambulatori, solo la sala operatoria o tutto insieme. Giorno: il planning delle
  stanze o delle sale (`servizi.esporta_giorno(..., parte=)`, lo stesso foglio di sempre limitato a
  quelle colonne) con l'elenco degli appuntamenti; tutto: due fogli di planning, *Ambulatori* e *Sala
  operatoria*, più l'elenco di tutto. Settimana: la matrice per la direzione sanitaria (solo ambulatori,
  `foglio_matrice`), oppure il foglio *Sala operatoria* (`foglio_sala_settimana`) e l'elenco degli
  *Interventi* (`foglio_interventi`); tutto: i tre fogli. Mese: la programmazione e il calendario degli
  ambulatori (`fogli_programmazione`), oppure la sala del mese giorno per giorno (`sala_del_mese` e
  `foglio_sala_mese`, fatta con le celle delle matrici delle settimane, così settimana e mese non possono
  dire cose diverse), i *Turni di sala* (`foglio_turni_sala`) e gli *Interventi*; tutto: la
  programmazione, il calendario con la sala e i fogli della sala. In «tutto insieme» ambulatori e sala
  stanno sempre in fogli separati. Gli elenchi degli interventi non hanno i dati dei pazienti (c'è la
  lista operatoria del giorno); il planning del giorno sì, come sempre. Gli Excel classici restano dov'erano
  e uguali: `/esporta/<data>` (il planning di tutte le stanze in un foglio), la matrice
  (`/ambulatori/settimana/<lunedì>.xlsx`) e la programmazione (`/ambulatori/mese/<aaaa-mm>.xlsx`), solo
  ambulatori; le esportazioni di solo ambulatori sono identiche a quelle, cella per cella. Ci si arriva
  anche da «Altre esportazioni» nel giorno, dal menu *Stampa e scarica* della settimana e da *Altre
  esportazioni* nel mese.


**Riepilogo live** (`live.py`, menu *Ambulatori → Riepilogo live*, `/riepilogo-live` e
`/riepilogo-live.json`): la giornata adesso. Dalla 1.12.2 la pagina è rifatta perché si legga a colpo
d'occhio (alla 1.12 era una fila di otto numeri che non tornavano, «in ritardo» contava solo le
ultime tre ore e chi era arrivato stamattina senza essere segnato non stava da nessuna parte).

- **Le esportazioni stampate** (1.12.4, dall'anteprima delle nove esportazioni stampate su A4 e guardate
  pagina per pagina): il planning del giorno con una tabella stretta (le due sale della sala operatoria, una
  stanza sola) va su un A4 verticale, le altre in orizzontale (`servizi._larghezza_pixel` contro
  `PIXEL_A4_VERTICALE`, contando solo la tabella); titolo e legenda vanno a capo e la riga cresce
  (`_righe_testo`; in una cella unita Excel non fa uscire il testo); oltre la tabella il titolo prende colonne
  vuote larghe 9 per stare in due righe. Il foglio della sala ha le righe delle fasce delle sale
  (`griglia(..., solo=di_sala)`; senza `solo` la griglia è quella di sempre), non quelle da 15 minuti di un
  ambulatorio, e le parole della sala (intervento, chirurgo, sala; nell'elenco le colonne SALA e CHIRURGO).
  Ogni fascia libera o chiusa più lunga di una riga è un blocco solo (celle unite, colorate tutte); il
  grigio «fuori turno» è D6DADF (prima ECEEF0, uguale all'azzurro su carta); sotto la legenda quanti
  appuntamenti sono disdetti o non presentati (la loro fascia resta libera). La testata di ogni pagina dice
  anche cosa c'è nel foglio (ambulatori o sala operatoria). In tutti gli Excel `imposta_stampa_excel` mette
  testata e piede a 0,25 pollici (con gli 0,5 di partenza di openpyxl restava un decimo di pollice e la testata
  copriva il titolo), e `una_pagina_se_manca_poco` fa stare in una pagina un foglio alto al massimo un quarto
  più di una pagina (il planning, la sala del mese). In `tabella_excel` date e orari al centro e l'etichetta
  dei totali unita alle celle vuote che la seguono (prima ne usciva sotto i bordi). Nei fogli di `ambulatori.py`
  ogni carattere ha il nome (`_carattere`, Calibri 11 come le celle senza stile); le settimane con gli articoli
  giusti (`servizi.dal_giorno`, `al_giorno`: dall'8, all'11); nel calendario del mese la data e il giorno in
  ogni riga (in grigio dalla seconda del giorno) e quando è stato calcolato; una data sola è testo; nella sala
  della settimana l'orario va sotto il nome quando non ci sta; la legenda della sala dice «arrivati».
- **In cima** una frase in parole semplici (`riassunto`): quante visite sono in corso, quante stanze
  hanno un medico adesso, quanti pazienti hanno l'orario passato senza l'arrivo segnato e il prossimo
  appuntamento. Sotto, una barra a quattro colori e i quattro numeri, che sommano agli appuntamenti
  attivi di oggi: **fatti** (arrivati, visita finita), **in corso** (l'orario è adesso), **da
  segnare** (orario passato, arrivo non segnato: si sistemano in *Oggi*) e **da fare** (più tardi).
  Ogni appuntamento sta in un gruppo solo (`live.stato_visita`). Una riga più piccola dice le stanze
  con un medico, i pazienti in struttura, disdetti e non presentati, e quanti sono da confermare per
  il prossimo giorno, con la data.
- **Le stanze adesso**: una riga per stanza (senza le sale operatorie). A sinistra la frase della
  stanza (*Visita in corso fino alle…*, *Libera, prossimo paziente alle…*, *Libera fino a fine turno
  (…)*, *Nessun medico fino alle…, poi …*, *Turni finiti per oggi*, *Nessun medico oggi*, *Chiusa
  oggi*), il medico di turno (una volta sola anche con due turni uguali) e i conti della stanza. A
  destra la linea del tempo dall'apertura alla chiusura (allargata se un turno o una visita escono):
  la fascia azzurra è il turno del medico, i rettangoli le visite colorate per gruppo, la linea rossa
  l'ora di adesso. Le posizioni le calcola `live.py` in percento (`linea`, `asse`); la pagina non
  ha bisogno di JavaScript per disegnarle. Nei rettangoli non c'è nessun nome: solo orario e stato.
- **Visite ora per ora**: il numero sopra ogni colonna, in scuro gli arrivati, le ore passate più
  chiare e quella di adesso bordata di rosso.
- **Mezze giornate libere**: una tabellina con una riga per giorno (i prossimi sette, senza i giorni
  in cui tutto è chiuso) e una colonna per stanza; M e P in verde sono mattina e pomeriggio senza
  nessun medico, dalla matrice degli ambulatori (`libere_tabella`; restano anche la lista `libere` e
  `libere_giorni` nel JSON).
- Su questa pagina le notifiche a comparsa non si chiedono nemmeno (`gestionale.js`): coprivano le
  stanze, e nascoste sarebbero risultate già viste nelle altre pagine; restano nelle altre pagine.
- Dopo una revisione indipendente (quattro revisori e due verificatori per segnalazione, 19 cose vere
  trovate e corrette prima di pubblicare): i conti sono solo delle stanze della pagina (gli interventi
  in sala operatoria si vedono in *Oggi* e in *Sala*), in un festivo con un turno di un giorno la sua
  stanza è aperta e la frase lo dice («chiusa, ma ci sono turni o appuntamenti»), una chiusura senza
  motivo dice solo «chiusa», con turni più tardi non dice «nessun turno», due turni attaccati sono uno
  solo per «libera fino a…», le visite fuori orario entrano nelle ore, dopo la mezzanotte la pagina si
  ricarica tutta, l'etichetta dell'ora non copre le tacche, l'ora di adesso resta bordata anche piena,
  in stampa le stanze non si spezzano e la legenda ha i suoi colori, nel tema scuro «in corso» e «da
  fare» si distinguono. Le prove ora guardano la pagina e il JSON a un'ora con turni e visite (prima la
  prova della riservatezza chiedeva il JSON di un giorno vuoto e non poteva fallire).

La pagina si rinnova da sola ogni minuto (ricarica il proprio contenuto con `fetch`, senza
sfarfallio); con `?schermo=1` («Modo schermo») niente menu e caratteri grandi, per il secondo
monitor. Il JSON ha gli stessi numeri: solo conteggi, orari, nomi di stanze e medici, mai un paziente
(una prova lo controlla con i nomi inventati) ed è il formato pensato per alimentare un giorno il
cruscotto su internet (vedi le proposte nel `PASSAGGIO_DI_CONSEGNE.md`). Per vedere la pagina com'è in
un giorno di lavoro mentre è domenica o sera, il riepilogo prende l'ora da `live.riepilogo(..., adesso=)`:
le prove la passano, e per le immagini della guida si è usato un gestionale di prova con
`live.datetime` fermo a un martedì alle 10:40.

**Riepilogo del periodo** (dalla 1.12.2; `ambulatori.riepilogo_periodo`, menu *Ambulatori → Riepilogo
del periodo*, `/ambulatori/riepilogo`, `.xlsx` e `.json`): il riepilogo «non live», com'è andato un
periodo. Si sceglie oggi, ieri, questa settimana, la settimana scorsa, questo mese, il mese scorso
(`?periodo=`) o due date (`?da=&a=`, girate se al contrario, al massimo `MASSIMO_GIORNI_RIEPILOGO` = 93
giorni); di partenza la settimana in corso; le frecce vanno alla settimana o al mese accanto, o allo
stesso numero di giorni prima e dopo. In cima una frase e i cinque gruppi che sommano al totale degli
appuntamenti delle stanze (fatti, non presentati, disdetti, da segnare, da fare: `gruppo_periodo`),
poi le ore di turno e quelle occupate. **Ore di turno**: i turni effettivi di ogni stanza giorno per
giorno (`servizi.Regole.turni_effettivi`: tolte assenze e chiusure), uniti, così due turni uguali non
contano doppio. **Ore occupate**: le ore dentro i turni coperte da un appuntamento che tiene il posto
(prenotato, confermato, arrivato e anche non presentato; il disdetto lo libera); le ore prenotate fuori
dai turni sono a parte. Tabelle: per stanza (medici, ore, occupazione, conti, mezze giornate senza
nessun medico dalla matrice degli ambulatori), per medico (giorni e ore di turno, occupazione nei suoi
turni, conti, percentuale dei non presentati su chi doveva venire) e giorno per giorno (i giorni chiusi
in grigio, il giorno apre la giornata). L'Excel ha i fogli Riepilogo, Stanze, Medici e, per più di un
giorno, Giorni, con gli aiuti di `comune.py`; «Stampa» stampa la pagina. Nel JSON e nell'Excel solo
conteggi, ore, stanze e medici.

Regole fissate dalla revisione della 1.12.2. **Medici**: le ore di un medico sono l'unione dei suoi
turni del giorno su tutte le stanze (con due stanze nello stesso momento non contano doppio) e le ore
occupate sono i suoi appuntamenti dentro quell'unione; per questo due medici nella stessa stanza
possono sommare più ore della stanza. **Mezzanotte**: una visita che passa la mezzanotte conta come
appuntamento nel giorno in cui comincia, ma i minuti dopo la mezzanotte vanno nel giorno dopo (anche se
il periodo comincia proprio quel giorno). **Festivi e domeniche**: un giorno con turni o appuntamenti
non è «chiuso» anche se la struttura chiude (la riga dice «Immacolata Concezione, ma con turni o
appuntamenti»), ma un giorno chiuso con soli appuntamenti disdetti resta chiuso; nei giorni che non sono
di apertura contano solo le mezze giornate con un medico, non tutte le stanze libere; una visita che
finisce alle 24:00 in punto non ha coda. **Stanze disattivate**: compaiono, con «(non più attiva)», nei
periodi in cui avevano appuntamenti (anche solo la coda dopo la mezzanotte di una visita della sera
prima). Disattivando una stanza i suoi turni non si chiudono e la data non resta scritta: per questo i
turni di una stanza disattivata contano solo fino al giorno del suo ultimo appuntamento non disdetto,
che viene per forza prima dello spegnimento (la scheda non lascia disattivare una stanza con
appuntamenti da oggi in poi). **Frecce**: uno o più mesi interi vanno allo stesso numero di mesi prima e dopo.
**Excel**: le ore non arrotondate (i totali tornano con il foglio Riepilogo), i «Giorni di turno» dei
medici senza totale, «giorno di chiusura» nei giorni in cui la struttura non apre, e nella colonna
«Chiusa» la stessa nota della pagina («Immacolata Concezione, ma con turni o appuntamenti»). **Parole**: «lo 0%»,
«45 minuti», «nessun appuntamento» invece di «0 appuntamenti, 0 fatti», «1 mezza giornata».

Le prove sono `prove_112.py` (le celle della matrice contro un calcolo minuto per minuto fatto a
parte, la programmazione, i due Excel riaperti, mettere e togliere, le protezioni, il foglio del
giorno, dalla 1.12.3 la sala operatoria nella settimana e nel mese contro un calcolo a parte (due sale e
una spenta, interventi prima dell'apertura e dopo la chiusura, nel festivo, disdetti e non presentati,
una domenica di sola sala e una di soli interventi, chi opera fuori dai turni, gli ambulatori con gli
stessi conti di prima) e le nove esportazioni (fogli e nomi dei file, solo ambulatori uguali cella per
cella agli Excel classici, la sala del mese uguale alle settimane, niente pazienti negli Excel di
settimana e mese, la pagina anche senza sale), il riepilogo del periodo contro gli insiemi di minuti di Python su tre periodi, con un non
presentato, una visita fuori turno e una a cavallo della fine del turno, e una settimana contata a mano
con i casi della revisione (stesso medico in due stanze, sovrapposizioni, mezzanotte, festivo e domenica
con un turno, stanza disattivata, frasi parola per parola, l'Excel uguale alla pagina) e due settimane
della seconda revisione (stanza spenta con i turni fino all'ultimo appuntamento e con la sola coda,
visita fino alle 24:00, chiusura con soli disdetti, ogni foglio dell'Excel confrontato cella per cella,
con ore non intere); ognuno dei difetti trovati, rimesso apposta nel codice, fa fallire almeno una
prova, il riepilogo live: dalla 1.12.2 i quattro gruppi che sommano al totale a dieci ore diverse,
anche stanza per stanza, le frasi, la linea del tempo, le ore e la tabella delle mezze giornate) e
`prove_112_browser.py` (anche la pagina del riepilogo, a qualsiasi ora giri: conti, righe, turni e
visite come nel JSON, linea di adesso, notifiche nascoste, telefono senza scorrimento laterale).

## Conferme

Menu **Segreteria → Conferme** (tasto C): gli appuntamenti del prossimo giorno che ne ha (o del giorno scelto),
ciascuno con i pulsanti **WhatsApp**, **Email** e **Chiama**. WhatsApp ed email si
aprono con il messaggio già scritto: nome, data, ora, struttura, indirizzo,
prestazione, medico, preparazione e numero da chiamare per disdire. Si invia con un
clic, poi *Confermato* sull'appuntamento. WhatsApp compare per i cellulari (e i numeri
esteri), non per i fissi; chi ha tolto il consenso ai promemoria è segnalato in riga.

Il testo si cambia in **Impostazioni** con i segnaposto fra graffe (`{paziente}`,
`{giorno}`, `{ora}`, `{struttura}`, `{indirizzo}`, `{prestazione}`, `{medico}`,
`{stanza}`, `{preparazione}`, `{recapito}`, `{data}`, `{telefono_struttura}`); *Rimetti il
testo predefinito* torna all'originale.

Con i promemoria automatici accesi (vedi *Email e WhatsApp ai pazienti*) la colonna
**Promemoria** dice cosa è partito da solo e quando; **Manda** lo manda adesso a chi non
l'ha ricevuto; *da chiamare* sono quelli senza cellulare né email, o che non vogliono
promemoria.

## Email e WhatsApp ai pazienti

Menu **Configura → Email e WhatsApp**. In alto quattro spie dicono cosa è pronto; sotto, le
email automatiche, l'account, il promemoria, WhatsApp e il registro.

**L'account email.** Le email partono da una casella della clinica e le risposte dei
pazienti arrivano lì. Dalla 1.9.1 va bene **qualsiasi casella** con un server di posta in
uscita (SMTP): si sceglie il **tipo di casella** e il programma propone server, porta e
sicurezza, con le istruzioni di quel tipo.

- **Casella del sito della clinica** (consigliata): una casella con il dominio del sito,
  per esempio *segreteria@* e il dominio, creata nel pannello di chi ospita il sito (in
  cPanel *Email → Account email → Crea*). Bastano indirizzo e password della casella,
  **senza verifica in due passaggi**. Il server proposto è *mail.* seguito dal dominio,
  porta 465 con SSL, come in quasi tutti gli hosting; se il pannello ne indica un altro (in
  cPanel *Connetti dispositivi*) lo si scrive in *Server e accesso*. Perché le email non
  finiscano nello spam, nel pannello SPF e DKIM devono risultare a posto (in cPanel *Email
  Deliverability*).
- **Aruba**: server smtps.aruba.it, porta 465 con SSL, l'indirizzo completo e la password
  della casella (la stessa della webmail). Non una casella PEC.
- **Gmail**: Gmail non accetta la password normale da un programma, vuole una *password per
  le app*, che Google dà solo con la verifica in due passaggi attiva.
  1. Accedere a Gmail con l'account della clinica (medicinamigliorenapolisrl@gmail.com).
  2. In **myaccount.google.com → Sicurezza** attivare la **Verifica in due passaggi**, se
     non c'è già (serve un cellulare).
  3. Aprire **myaccount.google.com/apppasswords**, scrivere un nome (*Gestionale*) e
     premere **Crea**: Google mostra 16 lettere.
  4. Nel gestionale, *Password per le app*: incollarle (gli spazi non contano) e salvare.

  Cambiando la password dell'account Google, la password per le app smette di funzionare:
  se ne crea un'altra. Gmail permette circa 500 email al giorno.
- **Altro server**: server, porta e sicurezza li indica il fornitore o chi gestisce la posta
  (di solito 465 con SSL, oppure 587 con STARTTLS). In *Server e accesso* ci sono anche il
  **nome utente**, da scrivere solo se il fornitore ne dà uno diverso dall'indirizzo (i
  servizi di invio come Brevo o Mailjet), e la spunta **Il server non chiede la password**,
  per un server della rete interna che manda senza accesso. Outlook.com e Hotmail non vanno
  (Microsoft non accetta più la password da un programma); con Microsoft 365 l'invio con
  password (SMTP AUTH) deve permetterlo l'amministratore, e Microsoft ha annunciato che lo
  spegne dalla fine del 2026.

L'indirizzo è già proposto, preso dalla struttura; il tipo si propone da solo (una casella
@gmail.com è Gmail, le altre la casella del sito). Poi **Manda la prova** al proprio
indirizzo: se arriva, le email ai pazienti partono. Se non parte, il messaggio dice cosa
correggere: password non accettata (con il consiglio giusto per Gmail e per Microsoft, e la
risposta del server), SSL scelto su una porta che vuole STARTTLS, certificato del server
fatto per un altro nome (va scritto il nome esatto del server), server che non si trova, che
rifiuta il collegamento o che non risponde (con la porta 465 la sicurezza è SSL), mittente
diverso dalla casella, invio a indirizzi di fuori non permesso senza accesso. Salvando, il
programma avvisa già delle combinazioni che di solito non vanno (porta 465 senza SSL, 587
con SSL, password senza sicurezza) e di una password di Gmail che non sembra una password
per le app. Gli errori da correggere fermano subito il messaggio (*non partito*, poi
*Riprova* quando è corretto); quelli di rete si riprovano da soli.

La password resta nel database cifrata con la protezione dati di Windows (DPAPI): la
legge solo lo stesso utente sullo stesso PC. Un backup portato su un altro computer non
la contiene in chiaro e lì va riscritta. La casella collegata con la 1.9 (Gmail) continua a
funzionare com'è: il tipo si ricava dal server salvato.

**Email automatiche.** Una *regola* dice per quale medico e quali prestazioni parte
un'email, con oggetto, testo e PDF allegati (fino a 10 MB ciascuno). Nella pagina le email
sono raggruppate per medico, in ordine di cognome, con per ultime quelle *per tutti i
medici*; sotto ogni gruppo **Nuova email per…** ne aggiunge una con il medico già scelto, e
in fondo si sceglie il medico (o tutti) e **Crea**. Per il Dr. Galasso
c'è **Crea la regola già pronta**: la mail di preparazione che l'accettazione manda oggi a
mano, con lo stesso oggetto e lo stesso testo, e le due informative (gastroscopia e
colonscopia) allegate; parte per le sue prestazioni con EGDS, gastroscopia o colonscopia
nel nome (non per le visite). In fondo all'email il programma aggiunge il logo e la firma
della struttura: società, indirizzo, telefono, email (da *Anagrafiche → Strutture*). Nel
testo di una regola si possono usare i dati dell'appuntamento (`{giorno}`, `{ora}`,
`{data-3}`, `{medico}`…, come nei moduli); *Prova* la manda al proprio indirizzo con un
appuntamento finto.

Quando si salva un appuntamento che corrisponde a una regola, il messaggio verde dice
"Email … in partenza per …" e l'email parte subito, senza far aspettare. Se il paziente
non ha l'email, o l'invio non è configurato, il messaggio è giallo e lo dice: si aggiunge
l'email e la si manda dalla pagina dell'appuntamento. Regole precise:

- una volta per appuntamento e paziente: modificare l'appuntamento non la rimanda;
  cambiare il paziente sì, al nuovo;
- gastroscopia e colonscopia dello stesso paziente lo stesso giorno, prenotate a parte:
  un'email sola (il testo parla già di tutte e due);
- una serie: un'email sola; un appuntamento già passato (chi ricopia l'agenda): nessuna;
- gli appuntamenti importati da Excel non mandano niente;
- un appuntamento disdetto o eliminato prima della partenza: l'email non parte; se
  valeva anche per un altro appuntamento del paziente quel giorno (l'email unica di
  gastroscopia e colonscopia), parte per quello.

**Un'email per ogni medico.** Ogni medico può avere informative diverse, e quindi email
sue. Per lo stesso appuntamento vale questo:

- l'email di un medico per una prestazione prende il posto di quella *per tutti i medici*
  per la stessa prestazione: se la Dr.ssa Lippiello ha la sua *Preparazione colonscopia*,
  ai suoi pazienti parte la sua, con i suoi PDF, e agli altri quella per tutti;
- l'email di un medico senza prestazioni spuntate (vale per tutte le sue) si aggiunge alle
  altre e non toglie niente: un'email di benvenuto non fa sparire una preparazione;
- due email dello stesso medico per la stessa prestazione partono tutte e due: salvando, il
  programma lo dice (*"Attenzione: insieme a questa parte anche…"*); a volte è voluto,
  altrimenti se ne spegne una o si tolgono le prestazioni in comune.

Nella pagina di ogni email, il riquadro *Con le altre email* dice dove sostituisce quella
per tutti, dove è sostituita da quella di un medico e con quali altre parte; lo stesso,
in breve, sotto ogni email nella pagina generale. **Duplica per un altro medico**, in fondo
alla pagina di un'email, ne fa una copia per un altro medico (o per tutti), con oggetto,
testo, prestazioni e una copia dei PDF: nasce spenta, si mettono testo e informative di
quel medico, si spunta *Attiva* e si salva. Anche la scheda del medico (*Anagrafiche*) elenca
le sue email, con **Nuova email per questo medico**. Nella pagina dell'appuntamento,
l'elenco delle email da mandare a comando dice perché le altre non partono da sole (*per
questo medico c'è la sua*, *è di Lippiello*, *non è per questa prestazione*).

Se un appuntamento cambia medico o prestazione, l'email del medico nuovo parte al
salvataggio; quella del medico di prima, se non è ancora partita (per esempio mentre
manca la rete), non parte più: il registro la segna *non vale più per questo
appuntamento*. Lo stesso quando la segreteria passa gli appuntamenti di un medico in ferie
a un sostituto (*Sposta gli appuntamenti di un medico*, da Impostazioni o dall'assenza in
Anagrafiche): ai pazienti parte l'email del sostituto, se ne ha una.

**A comando.** Nella pagina dell'appuntamento, il riquadro **Email e WhatsApp al
paziente** elenca cosa è partito per quell'appuntamento e ha **Manda l'email** (qualunque
regola, anche di nuovo) e **Manda il promemoria adesso**. Partono subito e il risultato si
vede appena la pagina torna.

**Il promemoria del giorno prima.** Spuntato *Manda i promemoria da solo*, ogni giorno
dall'ora scelta (10:00 se non si cambia) il programma manda il promemoria agli
appuntamenti fino al prossimo giorno di lavoro di ogni struttura: il martedì quelli di
mercoledì; il venerdì, con il sabato chiuso, quelli di sabato, domenica e lunedì; prima di
un ponte o di un festivo in cui la struttura chiude, anche quelli del giorno dopo.
Prenotati e confermati sì, disdetti no. Il canale: **WhatsApp** al cellulare (il primo
fra i due telefoni, anche estero) se WhatsApp automatico è configurato e il paziente non
preferisce l'email; altrimenti **email**, se ce l'ha. Chi ha tolto il consenso ai
promemoria non riceve niente. Il testo dell'email è quello di *Impostazioni → Messaggi ai
pazienti*; quello di WhatsApp è il modello approvato da Meta. Il PC deve essere acceso: il
gestionale parte da solo all'accesso a Windows e manda anche con il browser chiuso; se
all'ora scelta il PC è spento, il giro parte appena si accende. Un promemoria non parte
due volte, nemmeno dopo un riavvio; se l'appuntamento viene spostato a un altro giorno
prima della partenza, non parte. La pagina mostra in anteprima quanti partiranno nel
prossimo giro, e con quale canale.

**WhatsApp automatico.** L'app WhatsApp del telefono non permette invii da un programma:
serve la **WhatsApp Business Platform** di Meta.

1. Un account **Meta Business** della società e un'app in developers.facebook.com con il
   caso d'uso WhatsApp (*Connect with customers through WhatsApp*).
2. Un **numero di telefono dedicato**, aggiunto in *WhatsApp → Configurazione API* e
   verificato con un SMS o una chiamata. Non può essere un numero in uso in quel momento con
   l'app WhatsApp o WhatsApp Business del telefono: se lo è, prima si cancella l'account
   WhatsApp da quel telefono. Il **nome visualizzato** (quello che vedono i pazienti) lo
   approva Meta.
3. Un **modello di messaggio** approvato da Meta, categoria *Utilità*, lingua *Italiano*,
   nome `promemoria_appuntamento`, con questo testo:

   `Gentile {{1}}, le ricordiamo l'appuntamento di {{2}} alle ore {{3}} presso {{4}}. Per disdire o spostare l'appuntamento {{5}}. Grazie.`

   Il programma riempie {{1}}…{{5}} con nome del paziente, giorno, ora, struttura e
   "chiami il …" (il telefono della struttura). Se il modello approvato è diverso, si
   cambiano nome e variabili nella pagina, nello stesso ordine.
4. Un **token permanente**: in *Impostazioni dell'azienda → Utenti di sistema* un utente di
   sistema con l'app e l'account WhatsApp assegnati, poi *Genera token* con i permessi
   *whatsapp_business_messaging* e *whatsapp_business_management* e scadenza «mai»; e
   l'**ID del numero di telefono** (WhatsApp → Configurazione API). Si copiano nella pagina;
   il token è cifrato come la password.
5. **Registra il numero** (dalla 1.8, nella pagina): una volta sola, con un PIN di 6 cifre.
   Se il numero ha già la verifica in due passaggi il PIN è quello; altrimenti questo
   diventa il suo PIN. Il programma manda a Meta `POST /{ID del numero}/register` e non
   salva il PIN; Meta accetta al massimo 10 registrazioni in 72 ore. Senza questo passaggio
   Meta rifiuta i messaggi (codice 133010). Se Meta dice di no, la pagina spiega perché in
   parole semplici (PIN sbagliato, troppi tentativi, numero da verificare di nuovo, token
   scaduto o senza permessi); un altro ID del numero va registrato di nuovo.
6. Un metodo di pagamento: in Italia un messaggio di utilità costa circa 2,5 centesimi
   (listino Meta da ottobre 2026), cioè circa 2,50 € ogni 100 promemoria.

Meta conferma di aver preso in carico il messaggio (il registro ne tiene l'identificativo),
non che il paziente l'abbia letto: le spunte blu e le risposte restano sul telefono di quel
numero. Leggerle dal gestionale richiederebbe un indirizzo pubblico raggiungibile da Meta,
contro la scelta del tutto in locale. Finché WhatsApp automatico non è configurato, i
promemoria vanno per email e i pulsanti WhatsApp delle Conferme funzionano come prima.

**Il registro.** In fondo alla pagina gli ultimi 80 messaggi: quando, cosa, a chi, per
quale appuntamento, com'è andata. Se manca la rete o il server è occupato, il messaggio
riprova da solo dopo 2, 10, 30 minuti, 2 e 6 ore, poi si ferma. Per un errore da
correggere (password, indirizzo del paziente sbagliato) non riprova: lo dice con parole
chiare, si corregge e si preme **Riprova**. I messaggi non partiti degli ultimi sette
giorni fanno anche una notifica rossa. Un messaggio in coda si può **annullare**.

## Assenze, chiusure e festivi

Da **Anagrafiche**:

- **Assenze** di un medico (ferie, malattia, congresso), dal giorno al giorno: i suoi
  turni spariscono dalla griglia in quei giorni e la prima disponibilità li salta. Un
  turno di un giorno solo può coprire la stanza di un medico assente: è la
  sostituzione.
- **Chiusure** della struttura (ponti, lavori, ferie d'agosto): la griglia di quei
  giorni lo dice e non offre fasce.
- In entrambi i casi, se nel periodo ci sono già appuntamenti, il programma li elenca
  con il telefono, da spostare: non li cancella.
- **Festivi**: calcolati dal programma, Pasqua e Pasquetta comprese, e San Francesco il
  4 ottobre dal 2026, più il patrono della struttura se indicato. Di norma sono solo
  segnalati in griglia e al salvataggio; con *Chiusa nei festivi* restano aperti
  solo i turni di un giorno solo.

Prenotare in un giorno di assenza, chiusura o festivo resta possibile (serve per le
eccezioni), ma il modulo lo segnala.

## La giornata

- **Chiusura** (menu): gli appuntamenti già finiti e ancora *prenotati* o *confermati*.
  Tutti spuntati: un clic per segnarli arrivati, oppure si tolgono le spunte a chi non è
  venuto e lo si segna non presentato. Per un giorno passato l'ora di arrivo resta vuota
  (quella vera non si sa). Sotto, gli arrivati con un importo non ancora incassato e gli
  altri giorni degli ultimi 30 rimasti aperti. Senza questo passaggio le mancate
  presenze nelle statistiche non tornano.
- **Lista d'attesa**: il paziente che vuole un posto prima, con medico, prestazione,
  struttura, "disponibile dal", "entro il" e mattina o pomeriggio, tutti facoltativi.
  Quando un appuntamento futuro viene disdetto, il programma dice quanti in lista vanno
  bene per quella fascia e apre l'elenco di chi chiamare, dal primo arrivato, con
  WhatsApp già scritto ("si è liberato un posto…") e il pulsante *Prenota*. Prenotato
  così, il paziente esce dalla lista da solo.
- **Sposta** (dal modulo dell'appuntamento): i primi posti liberi dello stesso medico,
  un clic per spostare; oppure data, ora e stanza a mano. Durata e dati restano, un
  confermato torna prenotato (la data nuova va confermata), lo spostamento resta nello
  storico.
- **Sposta gli appuntamenti di un medico** (Impostazioni, o dalla pagina dell'assenza):
  per un periodo di ferie o malattia. Due modi: stesso medico, primo posto libero dopo il
  periodo; oppure stesso giorno e ora con un sostituto. Il programma propone una
  collocazione per ciascuno, senza metterne due nella stessa fascia; si conferma solo
  quello che si spunta, poi si apre l'elenco dei pazienti da avvisare con il messaggio
  pronto.
- **Ripeti** (modulo di un appuntamento nuovo): ogni N giorni, settimane o mesi, da 2 a
  52 volte in tutto. Le date in conflitto non si prenotano e vengono elencate; per i
  mesi, il 31 diventa l'ultimo giorno dei mesi più corti. Dall'appuntamento si apre la
  serie intera e si disdice "da qui in poi".
- **Nota del giorno**: in cima alla griglia e all'elenco, e sulla stampa ("Lippiello
  arriva alle 10", "ambulatorio 3 chiuso"). Una per struttura e giorno; svuotandola si
  toglie.
- **Agenda dei medici** (dalla griglia): un foglio per medico con i suoi appuntamenti
  del giorno in tutte le strutture, da stampare; con l'email del medico scritta in
  *Anagrafiche*, il pulsante la manda già compilata.

## Cassa e listino

- **Listino** (dalla Cassa o da Impostazioni): il prezzo di ciascuna prestazione e, se
  diverso, quello per convenzione o assicurazione. Nel modulo di prenotazione il prezzo
  si propone da solo scegliendo prestazione e convenzione; un importo scritto a mano non
  viene toccato.
- **Incasso** (in fondo all'appuntamento): importo, metodo (contanti, POS, bonifico,
  assegno) e ora. Si annulla se sbagliato. Pagato senza un prezzo scritto, il prezzo
  diventa quello pagato.
- **Cassa** (menu): gli incassi del giorno per metodo, da confrontare con cassetto e POS,
  e gli appuntamenti del giorno ancora da incassare, con i pulsanti *Contanti* e *POS*.
  Si stampa come chiusura di cassa. **Mese**: totali per giorno e metodo, scaricabili in
  Excel con l'elenco dei pagamenti. La cassa somma per data di pagamento, non di
  appuntamento.
- Il gestionale non emette fatture né ricevute: registra gli incassi.

## Moduli da stampare

Impostazioni → **Moduli da stampare**. Un modulo è un testo con i segnaposto
(`{paziente}`, `{codice_fiscale}`, `{data_nascita}`, `{giorno}`, `{ora}`, `{medico}`,
`{prestazione}`, `{struttura}`, `{indirizzo}`, `{telefono_struttura}`, `{oggi}`…) e le
date relative all'appuntamento: `{data-3}` è la data tre giorni prima ("03/10/2026"),
`{giorno-1}` il giorno prima per esteso ("lunedì 5 ottobre"), `{data+7}` una settimana
dopo. Può valere per una prestazione o per tutte, con o senza righe per le firme.
Dall'appuntamento si stampa già compilato. *Crea un modulo di esempio* ne fa uno da
adattare; i testi clinici vanno fatti verificare dal medico.

## Importare da Excel

Impostazioni → **Importa pazienti o agende da Excel**. File .xlsx o .csv (il vecchio
.xls va risalvato come .xlsx da Excel), fino a 10 MB. Vanno bene anche il .txt salvato da
Excel come "Testo Unicode" e i CSV del Mac.

**Dalla 1.11**: si leggono al massimo 20.030 righe per foglio; se il file ne ha di più
(contate solo quelle scritte) l'anteprima e la pagina finale lo dicono, e il file va diviso.
Un orario scritto come numero in una cella normale (9,30 diventa il numero 9,3) si legge
9:30: le cifre dopo la virgola sono i minuti, quindi 9,5 è 9:50 e non le nove e mezza. La
data di nascita con l'anno a due cifre («12/03/65») vale la data più recente non nel futuro
(1965), e dal 2000 in poi la riga si segnala da controllare. Nella colonna del medico «Dott.»,
«Dott.ssa», «D.ssa», «Dr.», «Prof.» non fanno un medico nuovo. La durata si legge anche
come orario (0:45, 1:30); quella che non si legge, o fuori misura, si segnala. La stessa
sala scritta con maiuscole diverse è una sala sola. Una riga disdetta non occupa la stanza.
Reimportando lo stesso file, i da confermare non si aggiungono di nuovo, e quelli delle
righe che ora entrano in agenda si chiudono.

Il programma riconosce da solo:

1. **la riga dei nomi delle colonne**, anche se sopra c'è un titolo o una riga "SALA A";
2. **le colonne**, dal nome (Tel., Cellulare, Recapito, Nominativo, Operatore,
   Intervento, Assicurazione…, confrontati senza accenti né punteggiatura) e dal
   contenuto (date, orari, telefoni, email, codici fiscali verificati, nomi di persona).
   Il contenuto può smentire il nome: una colonna TELEFONO con sempre lo stesso numero per
   lo stesso medico, accanto a pazienti diversi, è **il telefono del medico** e non
   finisce sui pazienti (va sulla scheda del medico, se vuota);
3. **le agende a blocchi**, con più sale affiancate e le stesse colonne ripetute: la sala
   è il nome scritto sopra il blocco; giorno e data scritti una volta per blocco, anche in
   celle unite, valgono per le righe sotto;
4. **cognome e nome insieme** ("DE FITTIZI TERESA", "ANNA VITALE", "DE LUCA CIRO"), con
   un elenco di nomi propri e le particelle (De, Di, Della…) attaccate al cognome. Se non
   si capisce ("MARIA ROSA"), la riga è segnata da controllare;
5. **la durata**, se non scritta: quella della prestazione se esiste, altrimenti il passo
   più frequente fra una riga e l'altra dell'agenda (un'ora per riga, un'ora di
   intervento), mai oltre l'appuntamento successivo della stessa sala;
6. **il medico e la stanza scritti nel titolo**, per le agende di un medico solo senza
   colonna del medico ("AGENDA AMBULATORI DOTT.SSA LIPPIELLO"): il medico del titolo vale
   per tutto il file (si cambia dal menu *Medico di tutto il file*); se non è ancora fra i
   medici, come appena installato, si crea dal nome scritto dopo "Dott.", "Dott.ssa", "Dr."
   o "Prof.". Così anche la stanza
   ("ENDOSCOPIA" → Sala endoscopia) se non c'è una colonna o un blocco a dirla. La riga
   delle etichette sopra le colonne ("STANZA 1", "STANZA 2"…) non viene scambiata per
   quella delle intestazioni.
7. **il foglio giusto**: il foglio ISTRUZIONI in testa (anche con una tabella d'esempio) e
   il RIEPILOGO in fondo si saltano, si parte dal primo mese. Dopo l'importazione, un
   pulsante porta all'anteprima del mese dopo, con le colonne già impostate; se un foglio
   non ha appuntamenti, l'anteprima lo dice;
8. **i file che non seguono i modelli**, provati sulle agende vere dell'accettazione:
   - sale affiancate con una colonna diversa (RECAPITO PZ in una, ASSICURAZIONE MEDICO
     nell'altra): la colonna vale solo per la sua sala;
   - TELEFONO accanto all'OPERATORE e RECAPITO PZ più avanti: il primo è del medico anche
     quando i numeri sono troppo pochi per capirlo dal contenuto;
   - il registro di una giornata sola: la data scritta sopra la tabella ("Data: 25/09/2026",
     "Venerdì 25 Settembre 2026"), la tabellina di riepilogo accanto ignorata, i posti vuoti
     con il solo tipo di visita saltati, "Nome e Cognome" nell'intestazione usato nei casi
     dubbi;
   - al posto del paziente una nota ("?D.SSA LIPPIELLO BLOCCA", "IL DOTTORE ANNULLA A
     D.D.D."): appuntamento senza paziente con la nota; "annulla" e "DISDICE" nelle note
     lo fanno disdetto;
   - un nome con il punto interrogativo ("SERAFINI?") è una prenotazione da confermare:
     va fra i da confermare, non in agenda;
   - fra parentesi ("LINA(BIANCHI)", "3470000000(FIGLIO)"): nelle note, non nel nome;
   - "DI NARDO" è un cognome, "ANTONYO D'ANDREA" ha il cognome in fondo, "JENNYFER
     SERAFINI" il nome straniero davanti (segnato da controllare);
   - "ROSSETTI" e "MARCO ROSSETTI" nello stesso file sono un medico solo; "BIANCARDI X
     ROSSETTI" è il dott. Biancardi, con la nota "per conto di Rossetti";
   - "Sost, protesi +pessi", "SOST. PROTESI CON PESSI" e "Sostituzione protesi con pessi"
     sono la stessa prestazione.

Un **planning** senza pazienti (solo medici per stanza e fascia) si riconosce: l'anteprima
avverte che diventerebbero appuntamenti senza paziente, e per i turni dei medici conviene
inserirli dalle anagrafiche.

L'**anteprima** mostra per ogni colonna cosa diventa (si cambia dal menu), le sale e a
quale stanza vanno, i medici, le prestazioni e le stanze da creare, i nomi quasi uguali
riuniti ("MASTOPALSTICA ADDITIVA" → Mastoplastica additiva, scegliendo la grafia con le
parole mediche riconoscibili), e le righe: prima quelle da controllare, con il motivo.
Le scelte fatte restano: un file con le stesse colonne, il mese dopo, è già impostato.

All'importazione:

- prima si fa un **backup** (*prima dell'importazione*, fra le copie in Impostazioni);
- un paziente già in anagrafica (stesso codice fiscale, o stesso nome con lo stesso
  telefono) si **completa** senza sovrascrivere; due righe della stessa persona fanno una
  scheda sola;
- un appuntamento già in agenda non si duplica: il file si può reimportare;
- una sala occupata alla stessa ora è un **conflitto**: la riga non entra in agenda ma va
  fra i **da confermare**, con il paziente, il medico e il motivo; così anche le righe con
  giorno e ora a cui manca la stanza o il medico (casella nell'anteprima);
- lo stesso medico in due sale alla stessa ora si importa com'è nel file, ma si segnala;
- "?" al posto del paziente dà un appuntamento senza paziente, con la nota "paziente da
  definire"; il punto interrogativo dopo la prestazione è un "da confermare";
- le colonne in più (anestesista, degenza…) diventano campi in più della prestazione,
  così restano visibili e modificabili nel modulo;
- una cella di solo testo in un blocco vuoto ("NESSUNA SECONDA SALA…") diventa la **nota
  del giorno**;
- gli appuntamenti già passati si importano come avvenuti (scelta modificabile: come
  prenotati, o non importarli);
- alla fine, il numero di righe importate e, per quelle rimaste fuori, un Excel con riga
  e motivo.

Anche l'Excel scaricato dal gestionale (foglio *Elenco*) si reimporta: la data la prende
dal nome del primo foglio.

## Aspetto e foglio del giorno

**Impostazioni → Aspetto**: tema dello schermo *chiaro*, *scuro* o *come Windows* (segue
Impostazioni → Personalizzazione → Colori → Modalità, anche mentre il programma è
aperto). La scelta vale per il PC. I fogli da stampare (giornata, promemoria, agenda
dei medici, moduli) restano chiari anche a schermo, perché sono l'anteprima della carta,
e in stampa tutto esce chiaro.

Il tema scuro è in `static/tema-scuro.css`, **generato** da `stile.css` con
`python strumenti/genera_tema_scuro.py`: ogni colore di stile.css viene girato per il
fondo scuro tenendo la tinta (il verde degli arrivati resta verde), con le correzioni a
mano in `strumenti/tema-scuro-correzioni.css`. Dopo una modifica ai colori di
`stile.css` va rilanciato; la prova `prove_14.py` se ne accorge se non lo si fa.

**Caratteri.** Gli stessi del sito della clinica (casadicuraposillipo.it): **Manrope** per
titoli, date, stanze e numeri grandi, **Inter** per tutto il resto, anche nelle stampe.
Sono dentro il programma (`static/fonts`, licenza libera SIL OFL 1.1, testo della licenza
nella stessa cartella): non servono internet né installazioni, e sono uguali su ogni PC.
Se per qualche motivo non si caricassero, il browser usa Segoe UI di Windows. Nelle email
ai pazienti si chiede Inter e, se il PC del paziente non ce l'ha, il carattere di sistema.

**Impostazioni → Foglio del giorno**: cosa esce con *Stampa* dalla giornata.

- Colonne: telefono, prestazione, medico, tipo di visita e convenzione, importo, campi in
  più della prestazione (sedazione, anestesista…), note. Ora e paziente ci sono sempre, la
  stanza quando il foglio è in ordine di ora.
- Foglio A4 orizzontale o verticale; in verticale la data va sotto il logo.
- Una tabella per stanza o tutto in ordine di ora.

Sulla pagina di stampa i pulsanti cambiano ordine e orientamento al volo, solo per quella
stampa; *Colonne…* porta alle impostazioni.

## Da confermare

Menu **Segreteria → Da confermare** (il numero di quelli aperti è anche accanto a *Segreteria*). Un appunto è una prenotazione non
ancora in agenda: giorno e ora se si sanno, medico, stanza (o "da assegnare"),
prestazione, paziente (in anagrafica, o solo cognome e telefono) e cosa c'è da
confermare.

- Si scrivono a mano dal riquadro *Nuovo appunto*, o li crea l'importazione con le righe
  che non entrano: in conflitto con un'altra alla stessa ora, senza stanza, senza medico.
  Di quelli importati si vede il file e la riga.
- Compaiono in cima alla giornata, sotto la nota del giorno, e fra le notifiche quando
  sono di oggi o di domani.
- **Prenota** apre il modulo dell'appuntamento già compilato; salvando, l'appunto si
  chiude e resta collegato all'appuntamento.
- **Prenota i selezionati**: più appunti in agenda insieme, nella stanza scelta. È il caso
  della giornata della dott.ssa arrivata senza stanza: appena si sa quale, un clic. Quelli
  che trovano la stanza occupata restano aperti e il programma dice perché.
- *Chiudi* quando non serve più (resta fra i chiusi, si riapre); *Elimina* lo cancella.

## Aiuto e guida

- **Aiuto → Come fare…**: le guide, divise in *Primi passi*, *Tutti i giorni*, *Dove si fa*,
  *Turni del personale*, *Sala operatoria*, *Cassa e fogli*, *Email e WhatsApp*,
  *Configurazione*, con una casella per
  cercare ("spostare", "backup", "WhatsApp"). Ogni guida ha i passi numerati e un'immagine con gli stessi
  numeri (fatta con dati di prova inventati).
- **Guarda il video**, in ogni guida: la stessa guida in un video di un minuto o due,
  registrato sui dati di prova, con un puntatore rosso che va sul punto illuminato e preme
  *Avanti*. Si apre grande sopra la pagina e parte subito; *Esc*, *Chiudi* o un clic fuori
  lo chiudono. Nell'indice ogni guida dice quanto dura il suo video.
- **Mostrami sullo schermo**, in ogni guida, apre la pagina e la percorre: la pagina si
  oscura, il punto da usare resta illuminato, un fumetto spiega. *Avanti*, *Indietro*
  (anche con le frecce o Invio), *Esc* o la × per chiudere. Durante la guida le frecce non
  cambiano giorno.
- **Aiuto → Guida di questa pagina** fa lo stesso sulla pagina che si ha davanti; dove le
  guide sono più d'una si sceglie quale.
- La prima volta che si apre il programma, in basso a sinistra compare l'invito a un
  giro di un minuto; la prima volta su una pagina che ha una guida, l'invito "Mostrami come
  funziona". Chiuso una volta, non torna (vale per quel PC).
- **Stampa la guida** (dalla pagina Come fare…) dà tutte le guide di seguito, su A4
  verticale, da stampare o salvare in PDF.
- **Aiuto → Novità**: cosa c'è di nuovo in questa versione, ogni novità con il suo
  video e la sua guida; le versioni precedenti sotto. Dopo un aggiornamento si apre da
  sola, e per due settimane una notifica la ricorda finché non la si apre. Le novità sono
  scritte in `novita.py`.
- In fondo a **Come fare…** c'è il numero della versione installata (*Gestionale Agende,
  versione 1.9*), con i collegamenti a *Configura → Aggiornamenti* e alla guida
  *Aggiornare a una versione nuova*.

Le guide sono scritte una volta sola in `guida.py`: gli stessi passi fanno la pagina, la
guida sullo schermo e la stampa. Le immagini si rifanno con
`python strumenti/genera_immagini_guida.py http://127.0.0.1:5000` sul programma avviato
con i dati di prova (mai con quelli veri): fotografa le pagine, contorna i punti dei passi e
ci scrive il numero; se un punto non si trova più lo dice. I video si rifanno con
`python strumenti/genera_video_guida.py http://127.0.0.1:5000` (serve anche ffmpeg), sempre
sui dati di prova: per ogni guida apre la pagina con la guida sullo schermo, fotografa ogni
passo e monta il video (cartello con il titolo, puntatore, tempo per leggere ogni fumetto,
cartello finale), in WebM VP9 da 1366×768, senza audio, meno di un megabyte al minuto;
scrive anche `static/video/durate.json`. Anche lui dice se un passo non si trova più.

## Oggi

È la pagina che si apre all'avvio (menu **Oggi**). Per la struttura scelta:

- **Adesso e nelle prossime due ore**: chi è in ritardo (cominciato da poco, non ancora
  arrivato) e chi arriva, con i pulsanti *Arrivato*, *Confermato*, *Non presentato*; sotto,
  chi è in struttura in quel momento.
- **Sala operatoria**: gli interventi di oggi con la checklist, il prossimo giorno di sala
  e quanti hanno la checklist da completare, i chirurghi liberi, i letti di stanotte.
- **Da fare** (con *Fatto*), **Da confermare** di oggi e domani, **Telefonate** (conferme
  del prossimo giorno di lavoro, giornate da chiudere), **Cassa di oggi**.

*Apri la giornata* porta alla griglia di sempre.

## Turni del personale

Menu **Turni** (dalla 1.8). Tre viste dello stesso planning, con le schede *Giorno*,
*Settimana* e *Mese* in alto a sinistra:

- **Mese**: il foglio dei turni, una riga per persona (divise per ruolo: medici,
  infermieri, OSS, tecnici, accettazione e amministrazione, ausiliari, altro) e una colonna
  per giorno, con il codice del turno nella cella. A 1366 pixel entra tutto il mese, con i
  totali; sugli schermi più larghi le colonne si allargano.
- **Settimana**: le stesse celle più larghe, con orario e area; la colonna *Ore* confronta
  le ore lavorate con quelle del contratto (sotto, sopra o ✓).
- **Giorno**: a ore, una riga per chi ha un turno quel giorno; per ogni ruolo quante persone
  sono al lavoro ora per ora, e per i medici collegati all'agenda i loro ambulatori,
  tratteggiati (in una striscia sotto il turno, se c'è anche quello).

**Mettere i turni.** Come in un foglio di calcolo. Un clic sulla cella apre la scelta del
turno: i tipi divisi per categoria, *Orario diverso, area, nota* (un orario scritto a mano,
l'area, una nota, un secondo turno nello stesso giorno) e *Togli*. Con una cella scelta
basta scrivere il codice: il turno si mette e si passa al giorno dopo; un codice che può
continuare (M e MA) aspetta un attimo, oppure Invio. Dalla 1.12.1 i codici scritti uno dopo
l'altro senza aspettare (M e subito P) si separano come farebbe una persona: vale il codice più
lungo con cui comincia quello che si è scritto (MA, PE e RE restano un codice solo), le lettere
dopo ricominciano da capo sul giorno seguente. Le frecce si spostano; Maiusc+frecce
o trascinando si scelgono più celle, anche di più persone, Ctrl+clic ne aggiunge una; Canc
toglie; Invio apre la scelta, Esc la chiude. **Ctrl+Z** annulla l'ultima modifica e
**Ctrl+Y** la rifà, anche con *Annulla* nell'avviso in basso: le celle tornano esattamente
com'erano, con orari, aree e note. Sostituire o svuotare 8 o più celle già piene chiede
conferma. Cambiando turno dalla tastiera, o su più celle, l'area che c'era resta. Nella
vista del giorno: clic (o Invio) sulla riga della persona, e *Turno a…* per chi quel
giorno non ha ancora un turno.

**Regole**, controllate dal programma e non dalla pagina:

- due turni della stessa persona non si sovrappongono, nemmeno con la notte del giorno
  prima (una notte 21–7 conta nel giorno in cui comincia); due turni che si toccano (la
  notte finisce alle 7, la mattina comincia alle 7) vanno bene;
- riposi e assenze (R, SN, F, MA, PE) valgono tutto il giorno e non stanno insieme ad altri
  turni dello stesso giorno; due turni con orario nello stesso giorno (spezzato) sì;
- meno di 11 ore di riposo fra due turni si possono tenere, ma il salvataggio lo dice e la
  cella ha un triangolino arancione;
- chi non è più in servizio non riceve turni nuovi, ma resta in quelli passati.

**Conti.** In fondo alla riga: ore di lavoro (la durata meno la pausa del tipo; la
reperibilità a parte), notti (turni che finiscono il giorno dopo), festivi (domeniche,
festività del calendario e patrono della struttura) e giorni di assenza, con il dettaglio
passandoci sopra. Le ore del contratto del periodo sono le ore a settimana × giorni ÷ 7.
Nelle due notti del cambio dell'ora (dalla 1.12.1) le ore di un turno sono quelle passate
davvero, non quelle che dice l'orologio: la notte dell'ultima domenica di marzo dura un'ora in
meno (alle 2:00 si passa alle 3:00), quella dell'ultima domenica di ottobre un'ora in più (alle
3:00 si torna alle 2:00). Così una notte 21–07 vale 9 ore a marzo e 11 a ottobre, e anche il
riposo fra due turni si misura con le ore vere. L'Excel del mese lo ricorda nella riga
«Esportato il…» quando il mese contiene il cambio. La regola europea (dal 1996) è scritta nel
programma, `calendario.cambio_ora` e `calendario.minuti_veri`, senza dipendere dal fuso orario
di Windows; `prove_18.py` la confronta con il fuso di Roma di Python.
Sotto ogni ruolo la riga **Copertura** dice quanti per turno quel giorno (M2 P2 N1), in
rosso dove una copertura minima non è raggiunta.

**Persone** (*Turni → Persone*): cognome, nome, ruolo, qualifica, ore a settimana (36,
37:30 o 37,5), telefono, email, struttura (o tutte), note e *In servizio*. **Aggiungi i
medici dell'agenda** crea una persona per ogni medico attivo che non ce l'ha, già
collegata all'agenda. Una persona con turni non si elimina: si toglie *In servizio*.

**Tipi di turno** (*Turni → Tipi di turno*): codice (da una a quattro lettere o cifre),
nome, categoria (lavoro, reperibilità, riposo, assenza), orario, pausa e colore; il colore
del testo, blu scuro o bianco, lo sceglie il programma per il contrasto. Si comincia con
M 7–14, P 14–21, N 21–7, G 8–17 con un'ora di pausa, RE 20–8, SN, R, F, MA e PE. Cambiando
l'orario di un tipo i turni già messi tengono il loro; un tipo già usato non si elimina,
smette di comparire fra quelli da mettere. **Coperture minime**: per ruolo, tipo di turno,
giorni della settimana ed eventualmente area, quante persone servono almeno.

**Strumenti**, in alto a destra:

- *Schema a rotazione…*: una sequenza come M M P P N SN R R (un trattino è un giorno vuoto)
  ripetuta nel periodo per le persone scelte, ognuna sfasata di qualche giorno; l'anteprima
  mostra i primi 14 giorni delle prime sei persone; le celle già piene restano, a meno di
  *Sostituisci*; al massimo 120 giorni alla volta. Scelto prima un gruppo di celle nella
  griglia, lo schema si apre con quelle persone e quei giorni.
- *Copia la settimana prima*: gli stessi turni, nelle celle ancora vuote.
- *Stampa*: A4 orizzontale, con la legenda dei codici.
- *Scarica in Excel*: il mese con i colori e i totali, e un foglio *Elenco* con un turno
  per riga, per le paghe.

I filtri *ruolo* e *area* valgono per le tre viste e per l'Excel (riposi e assenze restano
sempre). Con più strutture, una persona di una struttura compare solo lì; senza struttura,
in tutte.

**Oggi.** Se il personale è stato inserito, la pagina Oggi ha **In servizio oggi**: per
ruolo chi lavora oggi, anche chi fa la notte cominciata ieri (*da ieri*), con un punto
verde per chi è al lavoro in quel momento.

Dentro: `personale.py` (regole, conti, pagine, Excel), le tabelle `personale`,
`tipi_turno`, `turni_personale` e `coperture_minime` (schema 9), le pagine
`templates/personale_*.html` e `static/turni.js`. Ogni modifica dalla pagina è una
richiesta `POST /personale/turni/cambia` in JSON (*metti*, *aggiungi*, *togli*,
*ripristina*) che risponde con le celle, i totali e la copertura da ridisegnare e con lo
stato di prima delle celle cambiate: è quello che *Annulla* rimanda indietro (*ripristina*
è tutto o niente: se un turno di prima non sta più, non cambia niente e lo dice). Le
richieste della pagina passano da una coda, una alla volta, così le risposte arrivano in
ordine. Le icone delle pagine dei turni sono di Lucide (licenza ISC), scritte dentro la
pagina, senza niente da internet (`templates/_icone.html`, licenze in
`static/icone/LICENZE.txt`).

## Dove si fa

Menu **Dove si fa** (tasto **D**, dalla 1.9): in quale struttura del gruppo si fa una
prestazione, per indirizzarci il paziente quando qui non si fa (o non c'è posto).

**La ricerca.** Si scrive la prestazione come la dice il paziente: «risonanza ginocchio»,
«tac torace», «eco addome», «holter», «cardiologo». I risultati arrivano mentre si scrive,
senza ricaricare la pagina. Ogni parola scritta deve trovarsi all'inizio di una parola del
nome, dei sinonimi del database o della branca, senza badare a maiuscole e accenti; le
parole come «di», «con», «la» non contano. Valgono anche:

- le sigle d'uso: RM o RMN e risonanza, TC e TAC, RX, lastra e radiografia, eco ed
  ecografia, ECG, EEG, EMG, MOC e densitometria, EGDS e gastroscopia, mdc e contrasto,
  doppler; colonna e schiena (rachide), lombare (lombo-sacrale), testa (cranio, encefalo);
- singolare e plurale: «ginocchio» e «ginocchia», «mano» e «mani», «rene» e «reni»;
- le parole con il trattino anche unite: «lombo-sacrale» e «lombosacrale»;
- gli specialisti: «dentista», «oculista», «nutrizionista», «otorino»; chi scrive il nome
  di uno specialista («cardiologo», «ortopedico») trova per prima la visita;
- una parola scritta male si corregge da sola: *Nessuna prestazione con «ecocardiogrma»:
  ecco quelle con «ecocardiogramma»*.

*Tutte le branche* restringe la ricerca a una branca. Senza ricerca la pagina mostra
l'elenco delle branche (un clic per vederne le prestazioni), le strutture con città e
numero di prestazioni, e gli ultimi pazienti indirizzati. Le frecce passano dal campo alle
strutture dei risultati e da una struttura all'altra; Esc nel campo lo svuota.

**I risultati.** Per ogni prestazione: nome, branca, sinonimi e le strutture dove si fa,
ognuna con il suo colore e la città. *qui* è questa struttura; *da confermare* (bordo
tratteggiato) vuol dire che il database non ne è sicuro (nella nota di quella struttura c'è
«da confermare» o «da verificare»): passandoci sopra si legge la nota. Se la prestazione è
anche nel listino di questo gestionale, sopra i risultati c'è **Si fa anche qui**, con il
collegamento per prenotarla (con il paziente, se è stato scelto). Al massimo 60 risultati:
una parola in più restringe la ricerca.

**La scheda della struttura.** Un clic (o Invio) sulla struttura apre la sua scheda, a
destra; la pagina si stringe per lasciarle posto, Esc o la × la chiudono e si torna al
risultato. Dentro: la prestazione (con l'avviso se è da confermare o se lì non si fa),
indirizzo con *mappa* (Google Maps: serve internet), telefoni ed email con *copia*,
prenotazione online, orari, come si prenota, le note per la segreteria; se mancano i
recapiti, il collegamento per scriverli. Sotto, il **messaggio per il paziente**, già
scritto con la prestazione e i recapiti e firmato con il nome della struttura, che si può
cambiare: *Copia* (negli appunti, si incolla con Ctrl+V), *WhatsApp* (WhatsApp Web o
l'app, con il testo già scritto), *Email* (il programma della posta, con oggetto e testo),
*Stampa* (un foglio A4 da dare allo sportello). WhatsApp ed email mandano il testo com'è
nella casella in quel momento. L'indirizzo della pagina segue la ricerca e la scheda
aperta: ricaricando si ritrova tutto.

**Per un paziente.** Scegliendo il paziente nella pagina (*Per un paziente in
anagrafica?*) o arrivando dalla sua scheda (*Dove si fa una prestazione*), il messaggio
comincia con il suo nome, WhatsApp va al suo cellulare (anche se è il secondo numero) e
l'email al suo indirizzo. Senza cellulare o senza email si sceglie a chi mandarlo.

**Il registro dei pazienti indirizzati.** *Segna come indirizzato* (al telefono o a voce,
allo sportello) lo scrive nel registro; WhatsApp, Email e Stampa si segnano da sole, una
volta per scheda aperta, e l'avviso in basso ha *Annulla* se non serviva. *Pazienti
indirizzati* (in alto nella pagina) mostra un mese per volta, con i conti per struttura,
*Togli* e lo scaricamento in Excel; le **Statistiche** hanno *Indirizzati alle altre
strutture*, anche nel loro Excel. Nel registro nomi del paziente, della prestazione e della
struttura sono copiati: resta leggibile anche dopo una versione nuova del database o una
scheda eliminata; unendo due schede dello stesso paziente le righe passano a quella che
resta.

**Il database delle prestazioni** (*Configura → Strutture del gruppo*) è il file Excel del
gruppo. Un foglio con l'intestazione **Branca** e **Prestazione** e, se ci sono,
**Sinonimi** (le altre parole con cui si chiede, separate da virgole) e **Note**; poi una
colonna per ogni struttura, con il suo nome in intestazione e una **X** dove la prestazione
si fa (valgono anche x, Sì, 1, ✓). L'intestazione può stare sotto qualche riga di titolo.
Se i fogli sono più d'uno vale quello con «database» nel nome, altrimenti il primo con
Branca e Prestazione: gli altri (riepiloghi, fogli per struttura, regole) si saltano. Una
colonna con altro oltre alle X si salta con un avviso (Codice, Tariffa e simili senza
avviso); le righe vuote o senza nome si saltano, una prestazione scritta due volte diventa
una. Nelle **note**, un pezzo che comincia con il nome o la sigla di una struttura (le
iniziali: «CN: …» per *Centro Nord*) va a quella struttura, se la prestazione lì si fa; più
pezzi si separano con il punto e virgola; con «da confermare» o «da verificare» la
prestazione in quella struttura è *da confermare*. Il resto della nota resta sulla
prestazione e si vede nei risultati. Facoltativo: un foglio **Strutture** con la colonna
**Struttura** (lo stesso nome delle colonne) e i recapiti (Indirizzo, Città, Telefono,
Altro telefono, Email, Prenotazione online, Orari, Come si prenota, Note), che riempie i
recapiti che nel programma mancano.

Caricando il file si vede prima **cosa cambia**: quante prestazioni, branche e strutture,
le prestazioni nuove, quelle tolte e quelle cambiate di branca, le strutture nuove o
sparite, gli avvisi. *Importa* fa una copia di sicurezza (*prima del database
prestazioni*) e porta tutto nel programma; se la copia non riesce, non cambia niente. Per
una **versione nuova** del database si carica il file nuovo allo stesso modo: le
prestazioni con lo stesso nome restano le stesse (anche per il registro), quelle tolte
spariscono dalla ricerca, i recapiti scritti nel programma restano. Una struttura che non
c'è più nel file resta, con i suoi recapiti ma senza prestazioni, finché non torna. Se nel
file una struttura cambia nome, per il programma è una struttura nuova: i recapiti si
riscrivono.

**Recapiti** di ogni struttura: indirizzo e città, telefono (quello per prenotare) e altro
telefono, email, prenotazione online (un indirizzo web completo, https://…), orari, come
si prenota (va nel messaggio al paziente), note per la segreteria (non vanno nel messaggio)
e un nome breve per le etichette. *È una struttura di questo gestionale?*: una struttura
del database con lo stesso nome di una del gestionale lo è da sola alla prima importazione;
altrimenti si sceglie qui, e nei risultati porta il segno *qui*. Togliendo *Compare nelle
ricerche di Dove si fa* la struttura non viene più proposta, senza cancellare niente.

Il file vero del gruppo non è dentro il programma: si carica dalla pagina, una volta, e di
nuovo a ogni versione.

Dentro: `dovesifa.py` (lettura del file, importazione, ricerca con il suo indice, scheda
della struttura e messaggio, registro, pagine), le tabelle `strutture_gruppo`, `catalogo`,
`catalogo_sedi` e `indirizzati` (schema 10), le pagine `templates/dove*.html`,
`templates/_dove_risultati.html` e `templates/_dove_scheda.html` e `static/dove.js`. I
risultati e la scheda sono gli stessi modelli per la pagina intera e per i pezzi che la
pagina chiede mentre si scrive (`/dove-si-fa/risultati` e `/dove-si-fa/scheda/<id>`): il
disegno è uno solo, e i dati vi arrivano già codificati. La ricerca prepara una volta
l'indice delle prestazioni e lo rifà solo quando il catalogo cambia (importazione o
recapiti: impostazione `catalogo_versione`); su 1200 prestazioni risponde in pochi
millesimi di secondo. `strumenti/catalogo_prova.py` scrive un database inventato, fatto
come quello vero, per la prova (`strumenti/demo.py`) e per le prove automatiche.

## Sala operatoria

Un **intervento** è un appuntamento in una stanza di tipo *Sala operatoria* (il tipo si
sceglie nella scheda della stanza). Il menu **Sala** compare quando ce n'è almeno una.

- **Degenza**: nel modulo dell'appuntamento, per le sale, *Day hospital*, *Una notte* o
  *Ricovero* con il numero di notti. L'importazione legge la colonna DEGENZA (DH, NOTTE,
  RO, "2 notti"); un valore che non si capisce, come "?", va nelle note.
- **Checklist pre-operatoria**: nell'appuntamento e nella pagina *Sala*, caselle che si
  salvano da sole con data e ora. Voci predefinite: esami pre-operatori, consenso firmato,
  anestesista confermato, preparazione consegnata, acconto versato; si cambiano in
  *Impostazioni → Checklist pre-operatoria* (al massimo dieci, vuoto = nessuna). Nella
  griglia ogni intervento mostra quante ne mancano (passandoci sopra, quali); il giorno
  prima arriva la notifica degli interventi con la checklist da completare.
- **Pagina Sala**: gli interventi del giorno o dei prossimi sette, con sala, paziente,
  chirurgo, anestesista (dal campo in più *Anestesista* della prestazione), degenza e
  checklist; in testa chi è in sala, chi opera di solito quel giorno ed è libero, chi è
  assente.
- **Lista operatoria**: il foglio da stampare, una tabella per sala, con età e telefono
  del paziente, chirurgo, anestesista, degenza, note e cosa manca della checklist. Anche
  dalla riga *Sala operatoria* in cima alla giornata.
- **Posti letto**: nella scheda della struttura (*Nome, logo e colori*) si scrive quanti
  sono. La pagina conta, notte per notte per quattro settimane, gli interventi con una
  notte o un ricovero (la notte del 10 è quella fra il 10 e l'11), disdetti esclusi.
  Salvando un intervento che non trova letto compare un avviso; nelle due settimane
  seguenti una notte senza letti fa una notifica rossa.
- **Giorni dei chirurghi** (dalla pagina Sala): per ogni chirurgo i giorni della
  settimana in cui opera di solito, con accanto quante volte ha operato in quel giorno
  nelle ultime dodici settimane e nelle prossime otto. *Proponi dagli interventi* spunta
  i giorni con almeno due interventi; si controlla e si salva. Salvando un intervento in
  un altro giorno, il programma lo fa notare.

## Riepilogo del mese per medico

Da **Statistiche → Riepilogo del mese per medico**: un foglio per medico con gli
appuntamenti del mese, quanti arrivati, prenotati, non presentati e disdetti, per
prestazione, importi previsti e incassati. Si stampa (un medico per pagina), si scarica
in Excel (un foglio di riepilogo e uno per medico) o, se il medico ha l'email, si manda
con il messaggio già scritto. Si può scegliere un medico solo e, con più sedi, la
struttura.

## Cose da fare, notifiche e tasti

- **Da fare** (menu, e "Ricordami di…" nella scheda paziente e nell'appuntamento):
  richiamare, sollecitare, ordinare, con il giorno.
- **Notifiche a scomparsa**, in basso a destra: le cose da fare di oggi e quelle rimaste
  indietro (con *Fatto* e *Domani*), le conferme del prossimo giorno di lavoro, le
  giornate da chiudere, dopo le 18 la giornata di oggi, un backup che non va. Spariscono
  da sole dopo 15 secondi (restano se ci si passa sopra); chiuse con la ×, non tornano
  finché non cambia qualcosa; sparite da sole, tornano dopo due ore. Dalla 1.5 anche i
  messaggi ai pazienti non partiti. Le notifiche sono per la segreteria: ai pazienti
  scrivono solo le email e i promemoria di *Email e WhatsApp ai pazienti*, se accesi.
- **Ricerca rapida** nel menu: un paziente per cognome o telefono, un medico (apre la sua
  settimana), un giorno ("oggi", "domani", "lunedì", "24/9", "24 settembre") o, dalla 1.9,
  una prestazione con le strutture dove si fa (apre *Dove si fa*).
- **Tasti** (fuori dai campi di testo): `/` cerca, `←` `→` giorno prima e dopo, `T`
  oggi, `N` nuovo appuntamento, `G` `E` `C` griglia, elenco e conferme, `D` Dove si fa, `?`
  l'elenco dei tasti. In un modulo, **Ctrl+Invio** salva.

## Autoriparazione

Dalla 1.11 il programma si accorge da solo dei guasti più comuni e li ripara, senza perdere dati e
dicendo cosa ha fatto. Chi lo usa non è un tecnico: quando qualcosa si blocca può solo cliccare di
nuovo l'icona, e quel clic deve bastare. Tutto sta in `autoripara.py` (senza Flask: lo usa l'avvio,
prima che il server esista); le prove sono `prove_autoriparazione.py`.

**Un gestionale solo.** Il primo che parte tiene un lucchetto sul file `gestionale.lock` (lo toglie
Windows quando il programma si chiude, anche se si chiude male) e scrive in `gestionale.pid` il suo
processo, la porta e la fase (`avvio`, poi `in servizio`). Il secondo clic chiede a `/salute` del
primo se risponde (due tentativi da 15 secondi): se sì apre solo la pagina; se il primo sta ancora
partendo (fase `avvio`) o riparando (fase `riparazione`), da meno di 10 minuti, aspetta e apre la
pagina. Il custode scrive un battito in `gestionale.pid` a ogni giro (30 secondi): un gestionale che
non risponde alle pagine ma batte è occupato (salvataggi in coda, una riparazione lunga), non
bloccato, e il secondo clic lo aspetta fino a due minuti e mezzo; uno che non batte da 90 secondi, o
che risponde ma ha tutti i fili fermi su una pagina da più di due minuti, si chiude (`taskkill /F`,
senza `/T`: il browser aperto dal gestionale è un suo «figlio» e si chiuderebbe anche lui) e il
nuovo parte al suo posto. Un processo si chiude solo se è lo stesso eseguibile, con il percorso intero, ed è
partito prima che il file fosse scritto (un numero di processo riusato da un programma nato dopo
non è il gestionale): un programma che non è il gestionale non si chiude mai. Se la porta 5000 è presa da un altro programma, o Windows non la
lascia usare (Hyper-V e WSL si riservano intere fasce di porte), il gestionale si apre su una delle
porte 5001-5009 e lo scrive nel diario. Il server lega da sé la porta, senza `SO_REUSEADDR` su
Windows: con quell'opzione (che waitress mette sempre) Windows lascia legare una porta già usata da
un altro programma, e la porta occupata non darebbe errore. Prima di aprire il browser il server è
già in ascolto. Se il programma non parte proprio, apre nel browser la pagina
`avvio-non-riuscito.html` (accanto al database) che lo dice in parole semplici.

**Il database, all'avvio.** Prima di aprirlo si controlla (`PRAGMA quick_check`, il file che
comincia con «SQLite format 3»):
- integro, o con il giornale di un salvataggio interrotto: niente da fare (il giornale lo rimette
  SQLite aprendolo, anche con la testa del file scritta a metà);
- occupato da un altro programma (`BACKUP.bat`, un antivirus): non è un guasto, non si tocca;
- mancante o vuoto (zero byte) ma con copie di sicurezza: si rimette la più recente che passa il
  controllo completo (le «prima del ripristino» per ultime: sono lo stato che qualcuno ha scelto di
  lasciare), e si dice da che ora ricontrollare. Senza copie è il primo avvio: database nuovo;
- danneggiato: il file (con il suo giornale) si copia così com'è in `backup\danneggiati`, poi si
  prova a rifarlo senza perdere niente: `VACUUM INTO`, poi `REINDEX` su una copia, poi la copia
  tabella per tabella con gli indici rifatti dai dati. «Senza perdere niente» si dice solo se il
  controllo di SQLite trovava guasti solo negli indici: una pagina «mai usata» che contiene delle
  righe (una scrittura persa quando è saltata la corrente: la pagina interna torna com'era e le
  righe più recenti restano fuori dall'albero) sono righe perse, anche se la ricostruzione riesce.
  Allora si rimette l'ultima copia buona (il recupero parziale resta da parte) e si dice da che ora
  ricontrollare; senza copie si tiene il recupero parziale (avviso rosso: chiamare l'assistenza).
  `VACUUM INTO` da solo non basta per un indice rovinato: copia gli indici così come sono
  (l'ottimizzazione «xfer» di SQLite) e si ferma anche lui. Le copie si aprono in sola lettura e si
  controllano prima di rimetterle: una copia sparita nel frattempo non si crea vuota.

Le copie si cercano nella cartella scelta nelle impostazioni e in quella accanto al database; la
cartella scelta è scritta anche nel diario, per trovarla quando il database non si legge. Dopo una
riparazione `aggiorna_database` porta la copia alla versione del programma, come dopo un
ripristino. All'avvio si tolgono anche gli avanzi di lavori interrotti (copie `.parziale`, cartelle
`riparazione-…`).

**Il custode**, un thread che si sveglia ogni minuto:
- i lavori in sottofondo (copie di sicurezza, email e WhatsApp, controllo degli aggiornamenti), se
  si sono fermati, li fa ripartire;
- ogni mezz'ora, e subito dopo un errore «malformed» in una pagina (allora con il controllo
  completo: quello veloce non vede un indice che non corrisponde più ai dati), controlla il
  database; se è danneggiato lo ripara con i salvataggi fermi (`LUCCHETTO`): la copia buona si scrive dentro il
  file aperto con l'API di backup di SQLite (su Windows un file aperto non si sostituisce), e solo se
  il file è troppo rovinato per riceverla si sostituisce il file;
- controlla lo spazio sul disco: sotto i 300 MB lo dice;
- **riavvia il programma** se mancano i suoi file (l'eseguibile si apre in una cartella temporanea
  di Windows, che la pulizia del disco può cancellare) o se è bloccato (tre pagine ferme da più di
  cinque minuti, o una da mezz'ora): lascia il lucchetto, fa ripartire l'eseguibile fra due secondi
  con l'ambiente pulito (come per il Setup di «Aggiorna adesso») e si chiude. Mai durante un
  aggiornamento e mai più di tre volte in un'ora: alla quarta lo dice e lascia fare a chi c'è.

**Le copie di sicurezza** (in `backup.py`): oltre a quella del giorno, una copia «recente» ogni
due ore se il database è cambiato (se ne tengono le ultime tre): rimettendo una copia si perdono al
massimo due ore. Se la cartella scelta non si raggiunge (la chiavetta tolta, il NAS spento) la copia
del giorno si fa nella cartella accanto al database, e si riprova la cartella scelta a ogni giro. La
pagina delle impostazioni mostra e rimette le copie di tutte e due le cartelle. Una copia che non si
scrive non lascia il suo `.parziale`. Con l'orologio del PC indietro la copia appena fatta non si
cancella più (prima la rotazione la toglieva subito, ogni ora) e la pagina lo dice, insieme agli
altri avvisi; una copia con la data nel futuro non conta come l'ultima e si rimette per ultima. Il
ripristino dalle impostazioni funziona anche quando il database attuale è rovinato: la sua copia di
sicurezza non passerebbe il controllo, quindi si copia così com'è fra i danneggiati e si va avanti.
Il ripristino e «Aggiorna adesso» fanno la loro copia accanto al database se la cartella scelta non
si raggiunge. All'avvio si guarda solo la cartella accanto al database: una cartella di rete spenta
farebbe aspettare.

**La versione dello schema.** Se la riga `versione_schema` manca (un recupero che l'ha persa), la
versione si ricava da tabelle e colonne (la colonna `turni.passo` → 11, le tabelle di Dove si fa →
10, i tipi di turno → 9…) e la riga si riscrive. Prima diceva 1 o 2 guardando solo il logo, e
`_migra_a_3` avrebbe cambiato ogni «Confermato» in «Prenotato».

**Il registro** `gestionale.log` oltre i 5 MB diventa `gestionale.log.1` (fino al `.3`).

**Il diario** `autoriparazione.json`, accanto al database e non dentro (il database è proprio la
cosa che si ripara): le ultime 100 riparazioni, con quando, cosa e il dettaglio per l'assistenza.
Lo mostra *Impostazioni → Controllo del programma* (`/autoriparazione`: com'è adesso il database, le
copie, i lavori in sottofondo, lo spazio, la porta; *Controlla adesso* fa il controllo completo,
`integrity_check`), e la campanella avvisa per tre giorni (*Riparato da solo*, o in rosso se serve
l'assistenza).

**I file rovinati messi da parte** (dalla 1.12.1). La pagina dice quanti file ci sono in
`backup\danneggiati` e quanto occupano, e quanti sono da più di 90 giorni. Il bottone *Svuota i
file rovinati più vecchi di 90 giorni* (solo se ce ne sono, con una conferma) cancella quelli,
`autoripara.svuota_danneggiati`, e lo annota nel diario (senza campanella: l'ha chiesto chi usa il
programma, non è una riparazione); quelli più recenti restano sempre, perché possono servire
all'assistenza. Se un file non si lascia cancellare (aperto da un altro programma) la pagina lo dice,
invece di «niente da togliere». Il programma da solo non cancella mai niente lì dentro: la cartella
cresce finché qualcuno non la svuota da qui. La data di un file è quella nel suo nome
(`danneggiato-AAAA-MM-GG_HHMMSS.db`), per un file con un altro nome quella del file. Una pagina che si rompe mostra una spiegazione in parole semplici al posto
dell'errore del server (il disco pieno e il database occupato con il loro messaggio).

Per le prove: `GESTIONALE_PORTA` cambia la porta del programma (al PC della clinica non c'è: le
prove non toccano mai la 5000).

## Dove stanno i dati

`%LOCALAPPDATA%\GestionaleAgende\agende.db`, insieme a `gestionale.log`. Il programma
gira senza finestra, quindi il registro è l'unico posto in cui compaiono gli errori.

**Backup automatico.** Il gestionale copia da solo il database una volta al giorno
(il primo controllo un minuto e mezzo dopo l'avvio, poi ogni ora), nella cartella
`backup` accanto al database oppure in quella scritta in **Impostazioni**, per esempio
il NAS o la cartella di Drive. La copia si fa con il programma aperto, senza fermarlo, e
viene verificata (`integrity_check`) prima di prendere il nome definitivo: una copia a
metà non sostituisce mai una buona. Si tengono le ultime 30 copie giornaliere più una
per ciascuno degli ultimi 12 mesi. Se una copia fallisce, o l'ultima riuscita ha più di
tre giorni, la griglia lo dice in cima.

Da **Impostazioni**: *Fai un backup adesso*, l'elenco delle copie con data e dimensione, lo
scaricamento di ciascuna e il **ripristino**. Prima di ripristinare, il database attuale
viene salvato fra le copie come *prima del ripristino*, quindi anche un ripristino
sbagliato si annulla. `BACKUP.bat` resta installato per chi preferisce l'Utilità di
pianificazione, ma non serve più.

In più il pulsante *Scarica in Excel* rigenera il planning del giorno nel formato che
l'accettazione usa già.

**Accanto al database (dalla 1.11)**: `autoriparazione.json` (il diario delle riparazioni),
`gestionale.lock` e `gestionale.pid` (il gestionale aperto), `gestionale.log.1`… (i registri
vecchi), `backup\danneggiati` (i file rovinati messi da parte, che si tolgono solo da *Controllo del
programma*, quelli da più di 90 giorni) e, solo se il
programma non è partito, `avvio-non-riuscito.html`. Vedi *Autoriparazione*.

**Aggiornamento alla 1.11.** Il database non cambia (resta allo schema 11): niente copia di
sicurezza in più e nessuna tabella nuova.

**Aggiornamento alla 1.10.** Al primo avvio della 1.10 il programma copia il database in
`backup\agende-…-prima-della-versione-11.db`, poi aggiunge ai turni la colonna della durata
delle fasce, vuota: tutti i turni restano con le fasce della struttura finché non se ne sceglie
una. Niente di quello che c'era viene toccato.

**Aggiornamento alla 1.9.1.** Il database non cambia (resta allo schema 10): niente copia di
sicurezza in più e nessuna tabella nuova. Le impostazioni dell'email salvate con la 1.9
valgono come prima (il tipo di casella si ricava dal server salvato, Gmail resta Gmail); le
tre impostazioni nuove (tipo, nome utente, server senza password) si scrivono la prima
volta che si salva la casella.

**Aggiornamento alla 1.9.** Al primo avvio della 1.9 il programma copia il database in
`backup\agende-…-prima-della-versione-10.db`, poi aggiunge le quattro tabelle di *Dove si
fa* (strutture del gruppo, prestazioni del database, dove si fanno, pazienti indirizzati),
vuote finché non si carica il database delle prestazioni. Niente di quello che c'era viene
toccato.

**Aggiornamento alla 1.8.** Al primo avvio della 1.8 il programma copia il database in
`backup\agende-…-prima-della-versione-9.db`, poi aggiunge le quattro tabelle dei turni del
personale e i dieci tipi di turno di partenza (una volta sola: se poi si tolgono tutti, non
tornano). Niente di quello che c'era viene toccato.

**Aggiornamento alla 1.7.** Al primo avvio della 1.7 il programma copia il database in
`backup\agende-…-prima-della-versione-8.db`, poi aggiunge alla scheda dei pazienti sesso e
luogo di nascita e li ricava, con la data di nascita dove manca, dai codici fiscali validi
già salvati. I codici fiscali non vengono cambiati: quelli che non vanno si vedono in
*Pazienti → Controllo dei codici fiscali*.

**Aggiornamento dalla 1.4.x.** Al primo avvio della 1.5 il programma copia il database
in `backup\agende-…-prima-della-versione-7.db`, poi aggiunge le tabelle delle regole, degli
allegati e dei messaggi e la colonna dell'indirizzo del paziente. Nelle strutture che si
chiamano *Posillipo* e non hanno ancora un'email scrive medicinamigliorenapolisrl@gmail.com,
una volta sola: se poi la si cambia o la si toglie, resta così. Niente di quello che c'era
viene toccato, e niente parte verso i pazienti finché non si configura l'account email.

**Aggiornamento dalla 1.3.** Al primo avvio della 1.4 il programma copia il database
in `backup\agende-…-prima-della-versione-4.db`, poi aggiunge le tabelle nuove (lista
d'attesa, cose da fare, note del giorno, documenti, moduli, tariffe) e le colonne nuove
(pagamenti, serie, provenienza, email e telefono dei medici, prezzo di listino). Niente
di quello che c'era viene toccato. Da una 1.1 o 1.2 si passa direttamente alla 1.4: il
programma fa anche i passaggi della 1.3 descritti sotto.

**Aggiornamento dalla 1.2.** Al primo avvio della 1.3, prima di toccare qualunque cosa,
il programma copia il database in `backup\agende-…-prima-della-versione-3.db`. Poi, in
una transazione sola: aggiunge le colonne nuove, ricostruisce la tabella degli
appuntamenti per sostituire il vecchio vincolo "una stanza, un orario" con uno che vale
solo per gli appuntamenti attivi (altrimenti un disdetto bloccherebbe la fascia per
sempre), e porta tutti gli appuntamenti esistenti a *Prenotato*. Se qualcosa va storto
la transazione si annulla e il database resta com'era. Il registro riporta ogni passo.

## Cosa c'è dentro

| File | A cosa serve |
|---|---|
| `app.py` | Avvio, griglia del giorno, modulo di prenotazione, export, logo |
| `anagrafiche.py` | Medici, turni, stanze, prestazioni e strutture, assenze e chiusure |
| `pazienti.py` | Ricerca, scheda, doppioni, unione, controlli su telefono, email e codice fiscale, pagina Controllo dei codici fiscali |
| `codice_fiscale.py` | Il codice fiscale: controllo con il motivo, lettura, calcolo, omocodia, confronto con i dati, luoghi di nascita |
| `dati/luoghi_nascita.json` | Comuni (anche soppressi, con il loro periodo) e stati esteri con il codice del codice fiscale |
| `viste.py` | Elenco, settimana, mese, conferme, stampa, prima disponibilità, statistiche, impostazioni |
| `backup.py` | Backup automatico, rotazione delle copie, ripristino |
| `calendario.py` | Festivi, Pasqua, settimane del mese |
| `segreteria.py` | Chiusura della giornata, lista d'attesa, sposta, serie, note del giorno, cose da fare, notifiche, ricerca rapida, agenda dei medici |
| `cassa.py` | Listino, tariffe per convenzione, pagamenti, cassa del giorno e del mese |
| `documenti.py` | Documenti allegati alla scheda, moduli da stampare |
| `invii.py` | Email e WhatsApp ai pazienti: regole, coda con i nuovi tentativi, promemoria del giorno prima, la casella della struttura (tipi di casella, invio SMTP, errori spiegati), WhatsApp Business Platform, registro |
| `modelli_email/` | Le due informative della regola già pronta (gastroscopia e colonscopia) |
| `guida.py` | Le guide: testi, passi, pagine Aiuto, versione da stampare, videoguide |
| `static/guida.js`, `static/guida/` | La guida sullo schermo, la finestra dei video, le immagini delle guide |
| `static/video/` | Le videoguide (una per guida) e la loro durata |
| `aggiornamenti.py` | Aggiorna adesso: controllo delle versioni, scaricamento e controllo del Setup, installazione, esito al riavvio, pagina Aggiornamenti e Novità |
| `novita.py` | Le novità di ogni versione (pagina Novità, notifica, file delle versioni) |
| `sala.py` | Checklist pre-operatoria, pagina Sala, lista operatoria, posti letto, giorni di sala dei chirurghi |
| `cruscotto.py` | La pagina Oggi e il riepilogo del mese per medico |
| `personale.py` | Turni del personale: regole (sovrapposizioni, riposi), conti, coperture, schema a rotazione, copia della settimana, pagine, Excel del mese |
| `static/turni.js` | La griglia dei turni come un foglio di calcolo, la scelta del turno, annulla e rifai, la vista del giorno, lo schema a rotazione |
| `dovesifa.py` | Dove si fa: lettura del database delle prestazioni (Excel), importazione con l'anteprima, ricerca, scheda della struttura con il messaggio per il paziente, registro dei pazienti indirizzati, recapiti |
| `static/dove.js` | La ricerca mentre si scrive, la scheda della struttura, copia, WhatsApp, email e stampa, il registro con Annulla, il paziente scelto |
| `strumenti/catalogo_prova.py` | Un database delle prestazioni inventato, fatto come quello vero, per la prova e per le prove |
| `templates/_icone.html`, `static/icone/LICENZE.txt` | Le icone (Lucide, licenza ISC) scritte dentro le pagine, con le licenze (anche Radix Colors, MIT, per i colori dei turni) |
| `importa.py` | Importazione da Excel e CSV: riconoscimento, anteprima, esecuzione |
| `marchio.py` | Controllo e pulizia del logo, colore proposto, contrasto |
| `servizi.py` | Griglia (con le fasce dei turni), turni effettivi (assenze, chiusure, festivi), conflitti (fasce intere), disponibilità, statistiche, export in Excel |
| `modelli.py` | Le tabelle del database e il suo aggiornamento da una versione all'altra |
| `comune.py` | Le funzioni di servizio di tutte le pagine: numeri e date dall'indirizzo, ritorno sicuro, struttura scelta, JSON, Excel da scaricare, collegamenti email |
| `templates/`, `static/` | Interfaccia; `static/tema-scuro.css` è generato |
| `static/fonts/` | I caratteri del sito della clinica (Manrope, Inter) con la loro licenza |
| `static/logo-posillipo.png` | Il logo della clinica (*Longevity Institute*); `logo-posillipo-precedente.png` serve a riconoscere e sostituire quello di prima |
| `strumenti/` | Il generatore del tema scuro e le sue correzioni a mano; i generatori delle immagini, dei video e del PDF della guida; `prepara_aggiornamento.py` (il file delle versioni accanto al Setup); `genera_luoghi_nascita.py` (l'elenco dei luoghi di nascita); `genera_icone.py` (le icone di Lucide nella macro delle pagine) |
| `strumenti/demo.py` | Il gestionale con i dati di prova intorno a oggi: per le prove nel browser, le immagini e i video della guida, le dimostrazioni |
| `strumenti/tutte_le_prove.py` | Tutte le prove in fila con il riepilogo, anche quelle nel browser (`--browser`) |
| `strumenti/allinea_animata.py` | Porta i file comuni nella versione animata e controlla che siano uguali |
| `strumenti/cerca_dati_veri.py` | Prima di consegnare: niente dei file veri della clinica deve essere finito nel progetto |
| `strumenti/wine/` | Costruire, installare e provare eseguibile e Setup su Linux, in un Windows finto (Wine) |
| `strumenti/prove_installato.py`, `strumenti/prova_aggiorna_adesso.py` | Prove sul programma installato e su «Aggiorna adesso» per intero |
| `strumenti/consegna.py` | Divide i file grandi in pezzi da mandare in una chat, con `RICOMPONI.bat` |
| `seed.py` | Dati finti per le prove e le dimostrazioni |
| `gestionale.spec` | Ricetta PyInstaller per l'eseguibile |
| `installer.iss`, `installatore/` | Ricetta Inno Setup per l'installatore e le sue immagini |
| `requirements.txt` | Librerie del programma |
| `requirements-build.txt` | Librerie in più per costruire l'eseguibile |
| `CLAUDE.md` | Le regole del progetto per chi continua il lavoro con Claude Code; lo stato, le decisioni e le cose aperte sono in `PASSAGGIO_DI_CONSEGNE.md`, nella cartella sopra (la radice del repository) |

## Ricostruire l'installatore

Serve un PC Windows con Python dalla 3.10 alla 3.14, e Inno Setup 6
(gratuito, jrsoftware.org/isdl.php).

1. `CREA_EXE.bat` produce `dist\Gestionale.exe` (circa 40 MB, con le videoguide: dentro
   c'è tutto, Python compreso).
2. `CREA_SETUP.bat` produce `Output\GestionaleAgende-setup.exe` e, accanto,
   `Output\aggiornamento.json`, il file delle versioni per *Aggiorna adesso* (vedi
   *Pubblicare un aggiornamento*).

Le librerie sono indicate con intervalli e non con versioni fisse, e gli script le
installano con `--only-binary`: pip sceglie la versione più recente che esiste già
compilata per il Python presente e non prova mai a compilare da sorgente. Con versioni
fisse un Python più nuovo del previsto faceva fallire tutto: è successo con Pillow 11.1.0
su Python 3.14. Se manca un pacchetto pronto l'errore arriva subito, con un messaggio che
spiega cosa fare.

Se l'ambiente isolato `.venv` è stato creato con un Python diverso da quello attuale,
gli script lo rifanno da soli.

PyInstaller non compila per un sistema diverso da quello su cui gira: l'eseguibile
Windows si costruisce su Windows, oppure su Linux in un Windows finto (Wine), con gli
stessi due file .bat:

```
bash strumenti/wine/prepara.sh          # una volta sola: Wine, Python e Inno Setup
bash strumenti/wine/costruisci.sh .     # Setup e file delle versioni in Output
bash strumenti/wine/installa.sh Output/GestionaleAgende-setup.exe
python strumenti/prove_installato.py    # prove sul programma installato
bash strumenti/wine/ferma.sh
```

Così sono state costruite e provate le versioni consegnate (sotto).

La strada senza eseguibile resta `INSTALLA.bat`, che richiede Python sul PC di
destinazione.

## Come è stato verificato

Eseguibile e installatore sono stati costruiti e collaudati con Wine 9, con
Python 3.14.7 per Windows e Inno Setup 6.7.3, partendo dagli stessi file del pacchetto.

- `CREA_EXE.bat` eseguito per intero dal `cmd.exe` di Wine, in una cartella con le
  parentesi nel nome come `Download\gestionale-appuntamenti (2)\gestionale`.
- Installazione senza diritti di amministratore: file, tre collegamenti, parametro di
  avvio silenzioso sul collegamento di avvio automatico.
- Avvio all'accesso: il gestionale risponde e non apre il browser. Clic sull'icona con il
  programma attivo: si apre il browser, la seconda copia esce senza errori.
- Primo giorno dall'interfaccia sull'eseguibile installato: guida iniziale, medico,
  turno, medico proposto nella fascia libera, prenotazione, Excel con logo.
- Aggiornamento con il programma aperto: processi chiusi, file sostituito, medico,
  turno e appuntamento conservati, struttura non duplicata.
- Disinstallazione con il programma aperto: processi chiusi, cartella e collegamenti
  rimossi, database e registro conservati.
- Le due schermate dell'installatore, in italiano.

Versione 1.2, con lo stesso metodo:

- Aggiornamento dalla 1.1 installata e aperta, con due medici, due turni e due
  appuntamenti, passando per le schermate dell'installatore: la 1.1 viene chiusa, al
  riavvio il registro riporta le quattro colonne aggiunte e il logo copiato; dati,
  griglia ed Excel sono intatti.
- Seconda struttura creata caricando un logo JPG: colore preso dal logo, griglia vuota
  con il collegamento alle stanze, stanza e turno inseriti, prenotazione dalla sua
  griglia con le sue stanze proposte per prime.
- Installazione nuova: struttura *La mia struttura* senza logo, colori neutri; un logo
  giallo porta a un colore scurito e all'avviso.

Versione 1.3, con lo stesso metodo:

- Aggiornamento dalla 1.2 installata e aperta, passando per le schermate
  dell'installatore: la 1.2 viene chiusa; al riavvio il registro riporta la copia di
  sicurezza, le 23 colonne aggiunte, la tabella degli appuntamenti ricostruita e i tre
  appuntamenti portati a *Prenotato*. La copia *prima della versione 3* è identica al
  database di partenza, con il vecchio vincolo; il database aggiornato passa
  `integrity_check` e `foreign_key_check` e ha il vincolo nuovo sui soli attivi.
- Backup automatico fatto 90 secondi dopo l'avvio, *Fai un backup adesso* dalle
  Impostazioni.
- Sull'eseguibile installato, da browser: scheda paziente con secondo numero, email e
  codice fiscale; prenotazione scegliendo il paziente dai suggerimenti con la tastiera,
  con tipo e importo; Conferme con WhatsApp ed email già scritti; *Disdetto* dall'elenco,
  stessa fascia riprenotata a un altro paziente senza doppione della scheda,
  riattivazione del disdetto rifiutata perché la fascia è occupata; settimana, settimana
  del medico, mese, stampa, statistiche, prima disponibilità, impostazioni; nessun
  errore JavaScript.
- Reinstallazione della stessa versione con il programma aperto: nessun aggiornamento
  ripetuto, dati intatti.

Versione 1.4, con lo stesso metodo:

- Aggiornamento dalla 1.3 installata e aperta, dalle schermate dell'installatore: la 1.3
  viene chiusa; al riavvio il registro riporta la copia di sicurezza, le colonne
  aggiunte e il passaggio dello schema da 3 a 4. Appuntamenti, pazienti, medici, stanze,
  prestazioni, turni e strutture sono identici a prima, riga per riga; il database passa
  `integrity_check`; la copia *prima della versione 4* è la 1.3.
- Sull'eseguibile installato, da browser: tutte le pagine nuove; importazione dell'agenda
  di prova (10 appuntamenti) e dell'agenda vera degli interventi di settembre (34
  appuntamenti, 2 sale, telefono del chirurgo riconosciuto, "Mastopalstica" riunita),
  ciascuna preceduta dal suo backup; documento allegato; pagamento registrato; notifiche.
- Nel browser, sul programma: notifiche a scomparsa (comparsa, chiusura, *Fatto*),
  tasti rapidi, ricerca rapida con la tastiera, prezzo proposto dal listino e dalla
  convenzione, ripetizione, Ctrl+Invio, chiusura della giornata, importazione con
  caricamento del file; nessun errore JavaScript (37 controlli).

Versione 1.5, con lo stesso metodo (Wine 9, Python 3.14.7, PyInstaller 6.22, Inno Setup 6.7.3):

- Aggiornamento dalla 1.4.6 installata e aperta, passando per le schermate del Setup: la
  prima pagina dice *"È installata la versione 1.4.6 animata: verrà aggiornata alla 1.5"*,
  la 1.4.6 viene chiusa, l'ultima pagina dice che appuntamenti, pazienti e impostazioni
  sono rimasti dove erano, e il gestionale riparte. Al riavvio il registro riporta la copia
  di sicurezza *prima della versione 7*, la colonna aggiunta, lo schema da 6 a 7, l'email
  della clinica e il **logo nuovo** nella struttura Clinica Posillipo (identico, pixel per
  pixel, a quello del programma). Tutte le tabelle sono identiche a prima sulle colonne di
  prima; `integrity_check` a posto.
- Sull'eseguibile installato, con un finto Gmail (STARTTLS con certificato controllato) e
  una finta Meta: 31 controlli sulle funzioni della 1.5 (email automatica con le due
  informative intere, password e token cifrati con DPAPI, WhatsApp con il token giusto),
  24 sulla 1.4.6 e 21 sulle novità: versione in Aiuto, guide e immagini nuove, caratteri
  serviti dal programma, email per medico (parte quella del medico al posto di quella per
  tutti, all'altro medico quella per tutti, ciascuna con il suo oggetto), duplica, scheda
  del medico, motivo nella pagina dell'appuntamento.
- Versione animata installata sopra la normale (*"verrà sostituita dalla 1.5 animata"*):
  dati identici, nessun aggiornamento ripetuto, stessi controlli tutti a posto.
- Disinstallazione: programma, collegamenti e voce di Windows tolti, database intatto.
  Reinstallando, la prima pagina dice *"Su questo PC ci sono già appuntamenti salvati"* e
  il programma li ritrova tutti (81 appuntamenti su 81).
- Setup di una versione più vecchia di quella installata: la prima pagina avvisa prima di
  tornare indietro; annullando, il gestionale aperto non viene toccato.

Versione 1.6, con lo stesso metodo (Wine 9, Python 3.14.7, PyInstaller 6.22, Inno Setup 6.7.3):

- `CREA_EXE.bat` e `CREA_SETUP.bat` eseguiti per intero, per le due versioni: in `Output` il
  Setup e il suo file delle versioni, con dimensione e impronta giuste, accettato dal
  programma.
- Aggiornamento dalla 1.5 installata e aperta, dalle schermate del Setup (*"È installata la
  versione 1.5: verrà aggiornata alla 1.6"*): alla fine si riapre un solo gestionale (la
  voce per il Setup silenzioso non parte quando il Setup ha le sue schermate), al primo
  avvio c'è la notifica *Novità della versione 1.6*, che sparisce aperta la pagina, e i
  dati sono quelli di prima (81 appuntamenti su 81).
- Sull'eseguibile installato, normale e animato: 14 controlli sulle novità (versione,
  pagina Novità, i 27 video serviti come `video/webm` e scorribili, pagina Aggiornamenti
  con la sua variante, tipi dei file).
- **Aggiorna adesso per intero.** Una 1.6.1 di prova (lo stesso programma con un altro
  numero) pubblicata in una cartella con il suo file delle versioni: indirizzo scritto nella
  pagina, controllo e scaricamento in 2 secondi, notifica *Aggiornamento disponibile*, clic
  su *Aggiorna adesso* nel browser. Copia di sicurezza, Setup silenzioso con la sua barra di
  avanzamento, gestionale chiuso, sostituito e riaperto; la pagina rimasta aperta è passata
  da sola alle *Novità della versione 1.6.1* in una decina di secondi. Registro: *"aggiornamento dalla
  1.6 alla 1.6.1 riuscito"*; dati identici; il Setup installato tolto dalla cartella al primo
  giro del controllo; un Setup rimasto da una versione precedente, con un'impronta diversa,
  riscaricato.
- La stessa cosa su https, come da GitHub, con il programma animato: il file delle versioni
  e il Setup da 42 MB seguiti attraverso il rimando a un altro indirizzo e controllati in 2
  secondi; con un certificato non fidato, *"il certificato del sito degli aggiornamenti non è
  valido"* e niente scaricato.
- Il primo giro di questa prova ha trovato il difetto del gestionale riaperto dal Setup
  (vedi *Tredicesimo giro*) e ha mostrato sull'eseguibile anche il caso *non riuscito*: al
  riavvio con la versione di prima, riga nel registro e notifica *Aggiornamento non
  riuscito*.
- Versione animata installata sopra la normale 1.6.1, senza domande: *"1.6 animata"* in
  Windows, stessi 14 controlli a posto.
- L'indirizzo predefinito contro il progetto vero su GitHub, quando era ancora vuoto: il
  programma lo raggiunge, e la pagina dice *"lì non è stata ancora pubblicata nessuna
  versione"*; *Rimetti l'indirizzo predefinito* provato nel browser.

Versione 1.7, con gli script di `strumenti/wine` (Wine 9, Python 3.14.8, PyInstaller 6.22,
Inno Setup 6.7.3), partendo da un Windows finto nuovo:

- `prepara.sh` su un Windows finto vuoto: Python e Inno Setup scaricati e pronti. Il primo
  `CREA_EXE.bat` si fermava creando l'ambiente isolato (vedi *Quattordicesimo giro*):
  corretto `prepara.sh`, che ora alla fine prova anche una copia di file.
- `costruisci.sh` per le due versioni: `CREA_EXE.bat` e `CREA_SETUP.bat` per intero, Setup e
  file delle versioni in `Output`.
- Aggiornamento dalla 1.6 animata installata, con 81 appuntamenti: copia di sicurezza
  *prima della versione 8*, schema da 7 a 8, sesso e luogo di nascita aggiunti, dati
  identici (81 appuntamenti, 81 pazienti, 14 medici), *"versione 1.7 avviata la prima volta
  (prima c'era la 1.6)"*.
- Sull'eseguibile installato, normale e animato, `prove_installato.py`: 16 controlli a posto
  (versione, Novità, i 29 video, pagina Aggiornamenti con l'indirizzo predefinito, tipi dei
  file, codice fiscale controllato, letto e calcolato dall'eseguibile con il file dei luoghi
  al suo interno, pagina Controllo dei codici fiscali). L'eseguibile raggiunge il progetto
  vero su GitHub, ancora senza versioni: *"lì non è stata ancora pubblicata nessuna
  versione"*.
- **Aggiorna adesso per intero** (`prova_aggiorna_adesso.py`), dalla 1.7 a una 1.7.1 di prova
  in una cartella: pronta in 2 secondi, notifica, clic nel browser, Setup silenzioso,
  gestionale riaperto e pagina passata da sola alle *Novità della versione 1.7.1* in 9
  secondi, registro *"aggiornamento dalla 1.7 alla 1.7.1 riuscito"*, copia di sicurezza,
  Setup installato tolto al primo giro del controllo, dati identici: 14 controlli su 14.
- Installazione nuova della 1.7 normale (database nuovo, già allo schema 8), una scheda con
  il codice fiscale scritto (data, sesso e luogo riempiti dal codice), poi la 1.7 animata
  sopra: scheda intatta, stessi 16 controlli a posto.

Versione 1.8, con gli stessi script (Wine 9, Python 3.14.8, PyInstaller 6.22.3, Inno Setup 6.7.3):

- `costruisci.sh` per le due versioni: `CREA_EXE.bat` e `CREA_SETUP.bat` per intero, Setup
  (circa 54 MB, con i 35 video) e file delle versioni in `Output`.
- Aggiornamento dalla 1.7.1 installata, con 81 appuntamenti, 81 pazienti e 14 medici: copia
  di sicurezza *prima della versione 9* identica al database di partenza, schema da 8 a 9, le
  quattro tabelle dei turni e i dieci tipi di turno di partenza, *"versione 1.8 avviata la
  prima volta (prima c'era la 1.7.1)"*. Tutte le tabelle di prima sono identiche riga per
  riga; nelle impostazioni cambiano solo le voci della versione; `integrity_check` e
  `foreign_key_check` a posto.
- Sull'eseguibile installato, normale e animato, `prove_installato.py`: 25 controlli a posto
  (in più rispetto alla 1.7: le pagine dei turni, i dieci tipi di partenza, il mese in Excel,
  `turni.js`, le licenze delle icone, «Registra il numero» di WhatsApp).
- **Aggiorna adesso per intero** dalla 1.8 a una 1.8.1 di prova in una cartella: pronta in 2
  secondi, notifica, clic nel browser, Setup silenzioso, gestionale riaperto e pagina passata
  da sola alle *Novità della versione 1.8.1* in 11 secondi, registro *"aggiornamento dalla
  1.8 alla 1.8.1 riuscito"*, copia di sicurezza, Setup installato tolto al primo giro del
  controllo, dati identici: 14 controlli su 14.
- La 1.8 animata installata sopra la 1.7 animata (con una scheda): stessa copia di sicurezza
  e stesso aggiornamento dello schema, dati identici, 25 controlli a posto.
- Primo avvio senza dati, come dopo un'installazione nuova: database creato già allo schema
  9 con i dieci tipi di turno, 25 controlli a posto; sull'eseguibile, nel browser, due
  persone aggiunte, un turno scritto con il tasto M nella griglia del mese, Ctrl+Z e Ctrl+Y,
  il turno ancora lì dopo aver ricaricato la pagina, nessun errore JavaScript.

Versione 1.9, con gli stessi script (Wine 9, Python 3.14.8, PyInstaller 6.22.3, Inno Setup 6.7.3):

- `costruisci.sh` per le due versioni: Setup di circa 56 MB (con i 37 video) e file delle
  versioni in `Output`.
- Aggiornamento dalla 1.8.1 installata, con 81 appuntamenti, 81 pazienti e 14 medici: copia di
  sicurezza *prima della versione 10* identica al database di partenza, schema da 9 a 10, le
  quattro tabelle di Dove si fa (vuote), *"versione 1.9 avviata la prima volta (prima c'era la
  1.8.1)"*; tutte le tabelle di prima identiche riga per riga, `integrity_check` e
  `foreign_key_check` a posto.
- Sull'eseguibile installato, normale e animato, `prove_installato.py`: 31 controlli a posto
  (in più rispetto alla 1.8: le pagine di Dove si fa, il tasto D nel menu, `dove.js`, la
  ricerca rapida con le prestazioni). Poi, sull'eseguibile, il database delle prestazioni
  inventato caricato dalla pagina, con l'anteprima, l'importazione (56 prestazioni in 6
  strutture) e la sua copia di sicurezza, la ricerca, una parola scritta male, la scheda
  della struttura, un paziente segnato e tolto dal registro, la ricerca rapida: 11 controlli
  su 11; nel browser la ricerca mentre si scrive, la scheda, Esc, nessun errore JavaScript.
- **Aggiorna adesso per intero** dalla 1.9 a una 1.9.1 di prova in una cartella: pronta in 2
  secondi, notifica, clic nel browser, Setup silenzioso, gestionale riaperto e pagina passata
  da sola alle *Novità della versione 1.9.1*, registro *"aggiornamento dalla 1.9 alla 1.9.1
  riuscito"*, copia di sicurezza, Setup installato tolto al primo giro del controllo, dati
  identici e il database delle prestazioni ancora lì: 14 controlli su 14.
- La 1.9 animata installata sopra la 1.8 animata: stessa copia di sicurezza e stesso
  aggiornamento dello schema, dati identici, gli stessi 31, 11 e 5 controlli a posto.
- Primo avvio senza dati, come dopo un'installazione nuova: database creato già allo schema
  10, gli stessi controlli a posto.

Versione 1.9.1, con gli stessi script (Wine 9, Python 3.14.8, PyInstaller 6.22.3, Inno Setup 6.7.3):

- `costruisci.sh` per le due versioni: Setup di circa 57 MB e file delle versioni in `Output`.
- **Aggiorna adesso per intero dalla 1.9 vera alla 1.9.1.** La 1.9 normale installata con il
  Setup consegnato il 12 ottobre, con dati inventati (46 appuntamenti, 30 pazienti, 8 medici,
  turni, email automatiche e messaggi) e la casella collegata con il modulo della 1.9; la
  1.9.1 in una cartella: pronta in 2 secondi, notifica, clic nel browser, Setup silenzioso,
  programma riaperto e pagina passata da sola alle *Novità della versione 1.9.1* in 9 secondi,
  registro *"aggiornamento dalla 1.9 alla 1.9.1 riuscito"*, copia di sicurezza *prima di
  aggiornare*, Setup installato tolto al primo giro del controllo: 14 controlli su 14. Dopo,
  le 28 tabelle identiche riga per riga e cambiate solo le impostazioni della versione
  (nessuna copia *prima della versione*: lo schema resta 10), `integrity_check` e
  `foreign_key_check` a posto; la prova dell'email parte subito con la casella e la password
  salvate dalla 1.9 (cifrate con DPAPI), senza toccare niente.
- La 1.9.1 animata installata con il Setup sopra la 1.9 animata, con gli stessi dati: tabelle
  identiche, cambiate solo le impostazioni della versione, la casella della 1.9 che manda.
- Sull'eseguibile installato, normale e animato, `prove_installato.py`: 34 controlli a posto
  (in più rispetto alla 1.9: la pagina dell'email con i tipi di casella, `gestionale.js`, il
  vecchio indirizzo della guida che porta al nuovo). `prova_email_installato.py`, con finti
  server di posta: 12 controlli su 12 su tutte e due (modulo e avvisi, password cifrata con
  DPAPI, prova arrivata con il nome utente e il mittente giusti, password sbagliata spiegata
  con la risposta del server, nome utente diverso dall'indirizzo, server senza password, SSL
  sulla porta che non lo usa, certificato sconosciuto, invii riusciti con SSL diretto e con
  STARTTLS).
- Primo avvio senza dati: 34 controlli a posto; nella pagina dell'email il tipo proposto è la
  casella del sito, con il server che arriva appena si scrive l'indirizzo.
- Le stesse prove hanno mostrato dal vero il difetto della 1.9 sulle password con gli spazi:
  salvata con il modulo della 1.9, una password con uno spazio non entrava (la 1.9 toglieva
  gli spazi); salvata con la 1.9.1, entra.

Versione 1.10, con gli stessi script (Wine 9, Python 3.14.8, PyInstaller 6.22.3, Inno Setup 6.7.3):

- `costruisci.sh` per le due versioni: Setup di circa 57 MB e file delle versioni in `Output`.
- **Aggiorna adesso per intero dalla 1.9.1 alla 1.10.** La 1.9.1 normale installata nelle prove
  della 1.9.1, con i dati inventati (46 appuntamenti, 30 pazienti, 8 medici, 27 turni); la 1.10
  in una cartella: pronta in 2 secondi, notifica, clic nel browser, Setup silenzioso, programma
  riaperto e pagina passata da sola alle *Novità della versione 1.10* in 16 secondi, registro
  *"aggiornamento dalla 1.9.1 alla 1.10 riuscito"*, Setup installato tolto al primo giro del
  controllo: 14 controlli su 14. Nel registro del programma: *"colonne aggiunte: turni.passo"*,
  *"versione dello schema: da 10 a 11"*. La copia *prima della versione 11* è identica al
  database di prima; dopo, le 28 tabelle identiche riga per riga (i turni con la colonna nuova,
  vuota), cambiate solo le impostazioni della versione, `integrity_check` e
  `foreign_key_check` a posto.
- Sull'eseguibile aggiornato, nel browser: un turno passato a fasce da 20 dal modulo, la sua
  griglia a righe fitte con *fasce da 20'* in testa e l'ora in ogni fascia libera, il clic che
  apre il modulo a quell'ora, il turno rimesso come la struttura e la griglia di sempre: 7
  controlli su 7.
- La 1.10 animata installata con il Setup sopra la 1.9.1 animata, con i suoi dati: tabelle
  identiche, cambiate solo le impostazioni della versione, la colonna nuova; le stesse 7 prove
  delle fasce.
- Sull'eseguibile installato, normale e animato, `prove_installato.py`: 40 controlli a posto (in
  più rispetto alla 1.9.1: giorno, settimana e mese con il database allo schema 11, la durata
  delle fasce nel modulo del turno, lo stile della griglia a righe fitte, la guida).
- Primo avvio senza dati: database creato già allo schema 11, 40 controlli a posto; poi
  dall'interfaccia un medico, un turno con fasce da 20 (fasce libere 9:00, 9:20, 9:40…), una
  visita da 30 minuti alle 9 che occupa due fasce (la prima libera diventa 9:40) e una seconda
  prenotazione alle 9:30 rifiutata con *«la fascia delle 09:20 è già occupata»*: 7 controlli su 7.
- L'invio delle email non è cambiato dalla 1.9.1: `prova_email_installato.py` non è stata
  rilanciata.

Restano fuori, perché si vedono solo su un Windows vero: l'avviso SmartScreen, il
comportamento dell'antivirus del PC e l'apertura del browser predefinito; per gli
aggiornamenti, una versione più nuova pubblicata davvero su GitHub (il percorso è lo stesso provato su
https, con l'indirizzo vero al posto di quello di prova).

**Su un Windows vero (dalla 1.12.1).** Il workflow `.github/workflows/prove.yml` («Prove su
Windows», nella pagina *Actions* del progetto) lancia `tutte_le_prove.py` nelle due cartelle su un
Windows di GitHub (`windows-latest`, Python 3.13, Chromium di Playwright, `openssl` di Git for
Windows), prima le raccolte senza browser e poi quelle nel browser contro `strumenti/demo.py`
(`--solo-browser`), a ogni push del ramo di lavoro o a mano; i registri delle prove si scaricano
dall'esecuzione. Ai primi giri erano rotte quattro prove, tutte per differenze fra Linux e Windows,
mai per il programma: `pid_vero` di `prove_autoriparazione.py` usava `wmic`, che i Windows recenti non
hanno più (ora legge i processi con Toolhelp, `ctypes`); una prova di `prove_16.py` voleva zero
certificati di sistema, ma su Windows l'elenco delle radici è del PC e c'è sempre (ora conta che il
programma ne abbia di più, con l'elenco Mozilla); e una porta chiusa su 127.0.0.1 su Windows viene
detta «rifiutata» solo dopo un paio di secondi di tentativi, con un solo secondo di attesa sembrava
un sito che non risponde (ora la prova aspetta 5 secondi); e negli appunti di Windows gli a capo
diventano CRLF, per cui il confronto di «Copia» in `prove_19_browser.py` ora li normalizza. Un
quinto caso non era Windows ma il caso: `prove_18_browser.py` sceglie un mese a caso nel futuro, e
in un marzo in cui il 25 è l'ultima domenica il riposo fra il pomeriggio del 24 e la mattina del 25
vale 9 ore vere, non 10 (dalla 1.12.1): ora la prova calcola le ore attese con `calendario.minuti_veri`
(`PROVE_MESE=AAAA-MM` sceglie il mese, per rifare il caso).

## Email e WhatsApp: come funzionano dentro

Ogni messaggio passa da una **coda** nel database (tabella `invii`), che è anche il
registro. La prenotazione mette l'email in coda nella stessa transazione
dell'appuntamento e risponde subito; un thread del programma la manda e scrive l'esito. Se
la prenotazione non si salva (fascia presa), non resta nemmeno l'email.

- Il lucchetto dei salvataggi si tiene solo per scrivere nella coda, mai durante l'invio,
  e mentre si spedisce il database non resta bloccato: un server lento non ferma le
  prenotazioni (una prova lo misura con un invio di 2 secondi).
- Un messaggio "in partenza" quando il programma si chiude torna in coda al riavvio
  (meglio un doppione che una preparazione mai arrivata); uno fermo da più di 15 minuti
  anche senza riavvio.
- Testo e allegati si compongono al momento dell'invio: se l'appuntamento è stato
  spostato nello stesso giorno, l'email ha l'ora giusta.
- Si controlla il certificato del server (posta, Meta) con i certificati di Windows. Un
  certificato fatto per un altro nome è un errore da correggere (il nome del server); uno
  scaduto o sconosciuto si riprova, perché può sistemarlo il fornitore.
- Gli errori si dividono in due: da correggere (password, indirizzo rifiutato, SSL sulla
  porta che vuole STARTTLS, modello WhatsApp sbagliato: niente nuovi tentativi) e
  momentanei (rete, server che non si trova o non risponde, server occupato, 4xx SMTP, 429
  e 5xx di Meta: nuovi tentativi). Il testo dice cosa correggere e, per chi ne sa, riporta
  la risposta del server (`spiega_accesso_rifiutato`, `manda_email`).
- Il tipo di casella (`CASELLE`, `tipo_casella`, `server_proposto`) serve solo a proporre
  server, porta e sicurezza e a scegliere le istruzioni e i consigli: si salva quello che
  c'è nei campi. Le impostazioni salvate con la 1.9, senza tipo, valgono come prima: il
  tipo si ricava dal server. Nessun server di partenza (prima era quello di Gmail). Il
  nome utente per l'accesso (`email_accesso`) vuoto vuol dire l'indirizzo;
  `email_senza_password` fa mandare senza accesso.
- Un messaggio mandato a comando non riprova da solo: chi l'ha mandato vede subito
  l'esito.
- Le email hanno testo semplice e HTML, il logo della struttura come immagine interna
  (nessun collegamento esterno da caricare) e `Reply-To` sull'email della struttura se è
  diversa dall'account che manda.

Non c'è: la lettura delle risposte (vedi sopra), gli SMS (servirebbe un fornitore con API,
circa 5–7 centesimi a messaggio), l'invio da una seconda postazione (c'è un solo
programma che manda, quello sul PC dell'accettazione).

## Tre scelte volute

**Solo 127.0.0.1.** Il gestionale non è raggiungibile dalla rete, nemmeno dalle altre
postazioni. Con un utente solo è la scelta giusta, e Windows Firewall non chiede
autorizzazioni al primo avvio. Dalla 1.4.6 risponde solo se l'indirizzo è `127.0.0.1` o
`localhost` (contro il "DNS rebinding", un nome di un altro sito che punta al PC) e
accetta un modulo solo se arriva da una sua pagina: `Origin`, `Referer` e
`Sec-Fetch-Site` devono dirlo, e "null" non basta. Un programma che manda richieste senza
queste intestazioni (le prove, `curl`) passa: un browser le mette sempre. Le email e i
WhatsApp della 1.5 sono collegamenti in uscita verso il server di posta e Meta: il gestionale non apre
porte e nessuno lo raggiunge da fuori.

**Il giornale classico di SQLite, non il WAL.** Con il WAL le ultime modifiche restano in
un file a parte (`agende.db-wal`) finché SQLite non le riversa nel database: `BACKUP.bat`,
che copia il solo `agende.db`, le perderebbe senza dire niente. Il WAL serve quando molte
persone scrivono insieme; qui scrive una persona, e l'attesa di 5 secondi di SQLite (quella
di Python) basta.

**Niente `.db` su cartella condivisa.** SQLite su SMB ha il locking rotto: non dà errore,
corrompe il file. Se un domani servono due postazioni, il server resta su una macchina
sola e le altre ci arrivano via browser, oppure si passa a MySQL cambiando la sola
stringa di connessione (per questo si usa SQLAlchemy e non SQL scritto a mano).

## Prove

Tutte insieme, con il riepilogo: `python strumenti/tutte_le_prove.py`; con `--browser
http://127.0.0.1:5001` anche quelle nel browser, su un gestionale di prova avviato con
`python strumenti/demo.py --porta 5001` (mai su quello vero: salvano dati). Una per una:

```
python prove.py              # casi limite: orari, durate, conflitti
python prove2.py             # modifica, eliminazione, celle impilate, concorrenza
python prove100.py           # 139 prove su dieci aree
python prove200.py           # 281 prove, comprese quelle a matrice e i giri casuali
python prove_anagrafiche.py  # 78 prove su medici, turni, stanze, prestazioni
python prove_personalizzazione.py  # 51 prove su logo, colori, strutture, aggiornamento
python prove_funzioni.py     # 68 prove sulle funzioni della 1.3
python prove_14.py           # 38 prove (con centinaia di controlli) sulle funzioni della 1.4, 1.4.1 e 1.4.2
python prove_143.py          # 19 prove sulle funzioni della 1.4.3
python prove_145.py          # 21 prove: le segnalazioni della revisione esterna, confermate e respinte
python prove_146.py          # 11 prove: la seconda parte della revisione
python prove_guida.py        # 3 prove (con centinaia di controlli) sulla guida e sul menu a gruppi
python prove_15.py           # 69 prove sulla 1.5: campi del paziente, email automatiche e per medico, invio con un
                             # finto Gmail (STARTTLS vero), WhatsApp con una finta Meta, promemoria, logo nuovo, versione
python prove_17.py           # 33 prove sulla 1.7: codice fiscale (controllo, omocodia, calcolo e lettura confrontati
                             # con python-codicefiscale su migliaia di casi), luoghi, scheda, prenotazione,
                             # aggiornamento dello schema, Controllo dei codici fiscali, importazione, unione
python prove_18.py           # 34 prove sulla 1.8: turni del personale (regole contro oracoli scritti a parte, conti,
                             # schema, copia, annulla e rifai, protezioni, 260 modifiche a caso con invarianti,
                             # aggiornamento dalla 8), registrazione del numero WhatsApp con una finta Meta e, dalla
                             # 1.12.1, le notti del cambio dell'ora (le date e i minuti veri confrontati con il fuso
                             # di Roma di Python su ogni giorno dal 2024 al 2039 e su 41.000 coppie di orari)
python prove_19.py           # 27 prove sulla 1.9: Dove si fa (lettura del file in tanti modi e con i suoi errori,
                             # importazione e versioni nuove, ricerca contro un oracolo su 1200 prestazioni
                             # inventate, pagine, registro, statistiche, protezioni, aggiornamento dalla 9)
python prove_191.py          # 21 prove sulla 1.9.1: l'email con qualsiasi casella (tipi, server proposti, modulo con
                             # errori e avvisi, anche quello della 1.9 senza tipo, pagina, nome utente diverso, server
                             # senza password, password con spazi, ogni errore con il suo consiglio e se riprovare,
                             # certificati, impostazioni della 1.9 che restano), con lo stesso finto server di prove_15
python prove_110.py          # 22 prove sulla 1.10: le fasce dei turni. Senza fasce proprie griglia, agenda del medico,
                             # controlli, avvisi e prima disponibilità identici alle funzioni della 1.9.1 (copiate e
                             # ferme) su centinaia di giorni inventati; con le fasce proprie colonne e celle contro un
                             # calcolo minuto per minuto e riga per riga, controlli contro le fasce toccate calcolate a
                             # parte, prima disponibilità contro il controllo vero ora per ora; casi scritti a mano,
                             # appuntamenti presi prima delle fasce, pagine, modulo, Excel, aggiornamento dalla 10
python prove_autoriparazione.py  # 61 prove sulla 1.11: l'autoriparazione. Ogni guasto creato apposta: database
                             # mancante, vuoto, con la testa rovinata, un indice o una pagina dei dati rovinati, il
                             # giornale di un salvataggio interrotto, occupato; riparazione all'avvio e a programma
                             # aperto; un gestionale bloccato (finti gestionali in processi a parte), uno che sta
                             # partendo, un programma che non è il nostro (mai chiuso), la porta occupata; lavori
                             # fermi, poco spazio, copie con la cartella irraggiungibile, l'orologio indietro, il
                             # ripristino sopra un database rovinato; e il programma vero (app.principale) avviato,
                             # bloccato, sostituito, riparato e riavviato da solo; dalla 1.12.1 i file rovinati messi
                             # da parte (quanto occupano, «Svuota» quelli da più di 90 giorni, i recenti restano)
python prove_111.py          # le correzioni della 1.11, una prova per difetto (messaggi, agenda, schede,
                             # importazione), ognuna fallisce con il codice della 1.10
python prove_16.py           # 47 prove sulla 1.6: Aggiorna adesso da una cartella e da un finto GitHub su https
                             # (rimandi, errori del sito, certificati anche con certificati.pem e senza quelli di
                             # sistema, file delle versioni storpiati, Setup rovinati),
                             # installazione, esito al riavvio, novità, videoguide, installer e file delle versioni,
                             # indirizzo predefinito su GitHub e Rimetti (senza rete)
python prove_15_browser.py http://127.0.0.1:5000   # 14 controlli nel browser sulle pagine della 1.5 e sui caratteri
python prove_16_browser.py http://127.0.0.1:5001   # 19 controlli: finestra dei video, pagina Aggiornamenti che si
                             # ricarica da sola, pagina d'attesa, notifica, Rimetti l'indirizzo predefinito (cambia
                             # l'indirizzo degli aggiornamenti: su un gestionale di prova a parte)
python prove_17_browser.py http://127.0.0.1:5001   # 16 controlli: codice fiscale mentre si scrive, calcolo,
                             # suggerimenti del luogo, prenotazione, pagina di controllo (salva pazienti di prova)
python prove_tendine_browser.py http://127.0.0.1:5001   # 150 controlli: le tendine sopra la pagina e le notifiche, a 1366x657
python prove_18_browser.py http://127.0.0.1:5001   # 56 controlli sui turni: griglia, tastiera (anche due codici scritti
                             # di seguito senza aspettare), annulla e rifai, scelta del turno (dove si apre, mai
                             # coperta), schema, giorno a ore, schermo stretto, movimento ridotto
python prove_19_browser.py http://127.0.0.1:5001   # 37 controlli su Dove si fa: ricerca mentre si scrive, frecce, scheda della
                             # struttura, messaggio cambiato, Copia, WhatsApp e Stampa, registro con Annulla, paziente,
                             # ricerca rapida, schermo stretto, tema scuro (segna pazienti indirizzati di prova)
python prove_191_browser.py http://127.0.0.1:5001   # 22 controlli sull'email della 1.9.1: tipo di casella con server,
                             # porta, sicurezza e istruzioni proposti, server che segue l'indirizzo, @gmail.com che passa
                             # a Gmail, tendina del tipo salvata con il modulo, schermo stretto (salva le impostazioni
                             # email della prova e poi rimette quelle di partenza)
python prove_110_browser.py http://127.0.0.1:5001   # 20 controlli sulle fasce dei turni (il martedi della prova):
                             # righe e celle alte quanto le loro fasce, ore nelle fasce libere, clic che apre il modulo
                             # a quell'ora, guida sullo schermo, agenda del medico, modulo del turno, tema scuro
python prove_guida_browser.py http://127.0.0.1:5000   # 53 controlli nel browser, sui dati di prova
python prove_sicurezza_browser.py http://127.0.0.1:5000   # 5 controlli: moduli mandati da un altro sito
python campagna.py           # 2550 casi generati, anche sulle pagine della 1.4, circa due minuti
```

In tutto 973 prove più 2550 casi generati e 382 controlli nel browser, tutte verdi su Python 3.13 (alla 1.9 anche su 3.11 e 3.14).
Vanno rilanciate dopo ogni modifica; ognuna crea un database usa e getta. Alcune delle più
vecchie escono con codice 0 anche se una prova non va: conta la riga finale («0 da
sistemare»), che è quella che legge `tutte_le_prove.py`.

`prove_14.py` parte, per l'aggiornamento, dallo schema esatto della 1.3. Per
l'importazione usa un'agenda costruita come quella degli interventi dell'accettazione
(sale affiancate, celle unite, telefono del chirurgo, errori di battitura, punti
interrogativi), senza dati di pazienti veri, e una rubrica CSV in codifica Windows con
titolo, due telefoni, doppioni e valori sbagliati; poi esporta un planning e lo
reimporta in un database vuoto, confrontando appuntamento per appuntamento. Le altre
aree: chiusura della giornata, lista d'attesa (300 combinazioni contro una regola scritta
a parte), spostamenti singoli e in blocco (proposte mai sovrapposte, fuori dal periodo,
nei turni), serie, cassa (pagamenti casuali contro una somma fatta a parte, Excel del
mese), documenti (tipi riconosciuti dal contenuto), moduli (date relative calcolate a
parte), provenienza, note del giorno, notifiche, ricerca rapida, agenda dei medici, e
400 moduli a caso sulle pagine nuove senza mai un errore del server.

`prove_funzioni.py` copre dodici aree: aggiornamento dallo schema esatto della 1.2
(anche con doppioni e con transazione interrotta), stati e fascia liberata, controlli e
ricerca dei pazienti, prenotazione con i campi nuovi, festivi (Pasqua confrontata con 33
date note, dal 2000 al 2285), assenze, chiusure e turni di un giorno, settimana, mese e
prima disponibilità, statistiche (ricalcolate a parte sugli stessi dati), elenco,
conferme e messaggi, orari della struttura, backup e ripristino, robustezza. La
campagna ora comprende anche le pagine nuove, con 600 indirizzi sporchi.

`prove_anagrafiche.py` è diversa dalle altre: ogni scenario parte dal database vuoto del
primo avvio, lo stesso che trova la segreteria dopo l'installazione. Le altre partono da
`seed.py`, che inserisce i medici direttamente nel database, ed è per questo che non si
erano accorte che dall'interfaccia medici e turni non si potevano inserire.

`campagna.py` genera i casi e li confronta con un oracolo indipendente o con un
invariante; raggruppa i guasti per causa e riporta la semenza che li riproduce.

`prove_personalizzazione.py` parte, per l'aggiornamento, dallo schema esatto della
tabella *strutture* della 1.1, preso dal database che quella versione creava. Con
`DETTAGLIO=1` stampa anche le note delle prove superate, e la campagna i motivi dei
moduli rifiutati.

## Difetti trovati e corretti

Primo giro:

| Difetto | Effetto | Correzione |
|---|---|---|
| Sessione condivisa fra i thread | SQLite in errore con più richieste insieme | `scoped_session`, una per thread |
| Orari non multipli di 30' | Appuntamento salvato ma invisibile | La fascia accoglie l'orario contenuto, con l'ora esatta a video |
| Appuntamenti fuori 08:00–19:30 | Stessa sparizione | La tabella si allarga da sola quanto serve |
| Appuntamento oltre l'ultima fascia | Tabella e merge Excel sballati | Estensione limitata alle fasce disponibili |
| Durata zero o non numerica | Appuntamento di durata nulla accettato | Minimo 5 minuti, controllato sul server |
| Conflitto in salvataggio | Il modulo si riapriva vuoto | Torna compilato con quanto già scritto |
| Due omonimi | Fusi in una sola scheda paziente | Si riusa la scheda solo se coincide anche il telefono |
| Colore del medico | Finiva grezzo dentro `style` | Accettato solo `#rrggbb` |
| Due appuntamenti brevi nella stessa fascia | Uno spariva | Impilati nella stessa cella |

Secondo giro:

| Difetto | Effetto | Correzione |
|---|---|---|
| `?struttura=abc` nella barra indirizzi | Errore 500 | Conversione dei parametri con valore di ripiego |
| `?risorsa=abc` sul modulo | Errore 500 | Stessa cosa |
| Ora `25:99` inviata dal modulo | Errore 500 | Data e ora convalidate, messaggio all'utente |
| Data `32/13/2026` inviata dal modulo | Errore 500 | Stessa cosa |
| Id di stanza inesistente | Appuntamento orfano, poi griglia in errore | Stanza, medico e prestazione verificati prima di salvare |
| Due salvataggi contemporanei | Doppia prenotazione sulla stessa fascia | Lucchetto sul salvataggio più vincolo di unicità su stanza e orario |

Terzo giro, dalla campagna generativa:

| Difetto | Effetto | Correzione |
|---|---|---|
| `/esporta/` con byte nullo nell'indirizzo | Errore 500 | Il nome del file nasce dalla data convalidata |
| `/esporta/` con 500 caratteri | Errore 500, nome file troppo lungo | Stessa correzione |
| Durata enorme nel modulo | Errore 500 per straripamento sulla data | Durata ammessa fra 5 minuti e 24 ore |

Quarto giro, installazione e primo avvio:

| Difetto | Effetto | Correzione |
|---|---|---|
| Pillow bloccato a 11.1.0 | `CREA_EXE.bat` falliva su Python 3.14 | Intervalli di versione e `--only-binary` |
| `.bat` con fine riga Unix | Salti alle etichette a rischio in `cmd.exe` | Fine riga Windows |
| `if errorlevel 1` | Un crash ha codice negativo: lo script proseguiva | Controllo del risultato, non del codice |
| Avvisi di PyInstaller su driver non usati | La compilazione sembrava fallita | Driver esclusi nello `spec` |
| Anagrafiche di sola lettura | Appena installato non si potevano inserire medici e turni | Pagine di inserimento e modifica, guida al primo avvio |
| Modifica di un appuntamento con medico disattivato | Salvando passava al primo medico dell'elenco | Medico e stanza correnti restano in elenco |
| Campi affiancati nei moduli | Dal terzo in poi sfalsati | Griglia a due colonne |
| Fascia libera | Proponeva il primo medico in ordine alfabetico | Propone il medico di turno |
| Installatore con diritti di amministratore | Collegamenti nel profilo sbagliato | Installazione per utente |
| Controllo "programma aperto" su un segnale mai creato | Aggiornamento con file in uso | Chiusura esplicita del processo |

Quinto giro, personalizzazione e più strutture:

| Difetto | Effetto | Correzione |
|---|---|---|
| Versione del logo al secondo | Due caricamenti nello stesso secondo: il browser mostrava il logo vecchio | Versione in millisecondi |
| "Nuovo appuntamento" dalla seconda struttura | Proponeva la prima stanza della prima sede: prenotazione nella sede sbagliata | Stanze raggruppate, quelle della struttura corrente per prime |
| Salvataggio da una stanza di un'altra sede | Si tornava alla griglia della sede di partenza | Si torna alla struttura della stanza |
| Struttura senza stanze | Griglia vuota senza spiegazione | Messaggio e collegamento, struttura già scelta nel modulo |
| Numero di 25 cifre nell'indirizzo | Errore 500 su dodici pagine | Oltre il limite di SQLite l'indirizzo non esiste (404) |
| Modulo struttura senza il campo colore | Rifiutato come colore non valido | Colore non inviato: resta com'era |
| Colore non valido rimandato al modulo | Il browser lo avrebbe mostrato nero | Si ripropone il colore precedente |

Sesto giro, funzioni della 1.3:

| Difetto | Effetto | Correzione |
|---|---|---|
| Prima disponibilità con due turni nello stesso giorno | Proponeva le fasce del turno trovato per primo, non le più presto | Si raccoglie il giorno intero, si ordina, poi si taglia |
| Cellulare scritto `3931234567` | Il "39" iniziale scambiato per il prefisso e tolto: WhatsApp al numero sbagliato | Prefisso tolto solo con `+39`, `0039` o da 11 cifre in su |
| Importo `1e3`, `nan`, `inf` | Accettati come numeri | Solo cifre, con al massimo due decimali, fra 0 e 100.000 |
| Ricerca pazienti in JSON | Un cognome con `<script>` tornava così com'era | Caratteri `< > &` codificati, `nosniff` |
| Mancate presenze nelle statistiche | Il totale e la tabella per medico contavano in modo diverso | Stesso conteggio, controllato dall'oracolo |
| Fasce con apertura non allineata | Un `max` di troppo spostava le fasce all'ora piena | Fasce allineate all'apertura |
| Pulsante *Disdetto* | Compariva barrato come gli appuntamenti disdetti | Barrato solo sulle righe |
| Arrivo registrato in anticipo | Attesa negativa a video | Attesa mostrata solo da quando è passata l'ora d'arrivo |
| Giorni passati | Fasce libere offerte anche ieri | Nascoste |
| Modulo del testo dei messaggi | Due campi `azione`: il pulsante non contava | Il valore lo porta il pulsante |
| Fisso come primo numero, cellulare come secondo | Niente WhatsApp per quel paziente (trovato provando l'eseguibile installato) | WhatsApp va al primo cellulare dei due; conferme, elenco e stampa mostrano entrambi i numeri |
| Intestazione dell'elenco del giorno | "2 appuntamenti · 1 disdetto" con un solo appuntamento in piedi | Si contano gli attivi; disdetti e non presentati a parte |
| Ore nelle statistiche | 75 minuti mostrati come 1,2 (arrotondamento all'estremo pari) | Arrotondamento a metà per eccesso: 1,3; l'Excel riporta le ore con due decimali |

Anche qui metà dei rossi era della prova: avvisi già consumati dalla pagina mostrata,
date della 1.2 senza microsecondi, due prove che si passavano il database, la rotazione
calcolata su un insieme di copie sbagliato, un controllo di `prove200.py` che cercava
"49" nell'HTML e ogni tanto lo trovava nella versione in millisecondi del logo.

Settimo giro, funzioni della 1.4 (quasi tutti trovati provando l'importazione
sull'agenda vera degli interventi):

| Difetto | Effetto | Correzione |
|---|---|---|
| Cella unita "SALA A" su otto colonne | Contata come otto intestazioni: la riga dei nomi delle colonne diventava quella della sala | Si contano i testi distinti |
| Colonna vuota fra una sala e l'altra | Blocchi non riconosciuti: le due sale diventavano una | I blocchi si confrontano senza le colonne vuote in fondo |
| Qualche riga alle 8:30 in un'agenda a righe di un'ora | Interventi importati da mezz'ora | Durata dal passo più frequente fra le righe, non dal più piccolo |
| Errore di battitura più frequente della grafia giusta | "Mastopalstica additiva" diventava il nome della prestazione | Vince la grafia con le parole mediche riconoscibili |
| Telefono del chirurgo in un file piccolo | Non riconosciuto: il numero del medico finiva su tutti i suoi pazienti | Criterio: stesso numero accanto a pazienti diversi |
| Colonne "Tel." e "Cell" | La seconda veniva scartata | Diventa l'altro telefono |
| Due righe della stessa persona nel file | L'anteprima diceva due pazienti nuovi, l'importazione ne faceva uno | Anche l'anteprima le riconosce |
| "DE LUCA CIRO" | Segnato come dubbio, perché Luca è anche un nome | Con una particella la testa è un cognome |
| Colonne senza nome (Colonna1, Colonna2) | Riga delle intestazioni non trovata | Conta anche una riga di testi con i dati sotto |
| Casella con il campo nascosto "0" davanti | Le opzioni dell'anteprima risultavano sempre spente | Si leggono tutti i valori |
| Scelta della stanza per ogni sala | Il menu segnava la stanza sbagliata | Indice del blocco, non della stanza |
| Riga scartata con l'ora ma senza fine | Anteprima in errore | Fine mostrata solo se c'è |
| Reimportando un'agenda, gli interventi senza paziente | "In conflitto" con se stessi invece che "già in agenda" (trovato sull'eseguibile, con il file vero) | Stessa ora e stesso medico, entrambi senza paziente: è lo stesso appuntamento |
| Agenda di un medico solo, senza colonna del medico (modelli Lippiello, Galasso) | Righe scartate: medico mancante | Medico e stanza dal titolo del foglio, modificabili nell'anteprima |
| Modello con il foglio ISTRUZIONI in testa | L'anteprima partiva dalle istruzioni: nessun appuntamento, righe "manca il cognome" | Si parte dal primo foglio con una tabella, istruzioni e riepilogo per ultimi; dopo l'importazione, il mese dopo |
| Medico del titolo non ancora inserito (appena installato) | Tutte le righe scartate: "manca il medico" | Il nome dopo Dott./Dr./Prof. diventa un medico nuovo |
| Nome del file letto in minuscolo | Medico del titolo proposto come "ferrante" | Il nome del file resta com'è; minuscole solo per l'estensione |
| Data in una colonna senza intestazione, accanto a GIORNO non unita | Colonna ignorata: "manca la data" su ogni riga | Conta anche una colonna senza nome, se è piena |
| Riga "STANZA 1, STANZA 2…" sopra le intestazioni del planning | Presa per la riga dei nomi delle colonne | Una riga di etichette numerate conta meno |
| Pazienti senza provenienza | Nelle statistiche come "—" | "Non indicata" |
| Ricerca rapida da una pagina senza struttura | Indirizzo sbagliato, nessun risultato | Separatore giusto nell'indirizzo |
| Scheda con documenti eliminata o unita | Documenti, cose da fare e lista d'attesa orfani | L'unione li sposta; con documenti la scheda non si elimina |
| Limite del server a 4 MB | Un documento da 10 MB non sarebbe arrivato | 12 MB; il logo resta a 3 |
| Nota del giorno | Uno spazio vuoto sopra il testo | Tolto il `pre-line` dal riquadro |
| Menu a 1366 pixel | Andava a capo | Spaziature ridotte |

Ottavo giro, 1.4.1, dalle agende vere di settembre e ottobre (interventi, endoscopia,
registro di una giornata):

| Difetto | Effetto | Correzione |
|---|---|---|
| Sale con una colonna diversa (RECAPITO PZ / ASSICURAZIONE MEDICO) | Sale non riconosciute: 0 interventi importati su 21 | Blocchi quasi uguali: la colonna diversa vale per la sua sala |
| Telefono del chirurgo con pochi numeri | Finiva sui pazienti | TELEFONO accanto all'OPERATORE, con RECAPITO PZ più avanti, è del medico |
| Titolo "DR. GALASSO/VISITE OGNI ORA…" | Medico "Galasso Visite Ogni" | Il nome finisce al primo separatore |
| "…A PARTIRE DALLE 9" nel titolo | La "a" faceva trovare anche la Sala A: stanza non scelta | Vince la parola che distingue la stanza |
| Registro di una giornata | Data non letta; il riepilogo accanto preso per dati | Data sopra la tabella; tabellina oltre una colonna vuota ignorata |
| "?D.SSA … BLOCCA", "IL DOTTORE ANNULLA" | Diventavano pazienti | Note al posto del paziente; "annulla", "disdice" fanno disdetto |
| "DI NARDO", nomi fra parentesi, email con uno spazio | Cognome "Di", nome "Nardo"; parentesi nel nome; email tolta | Particella con il cognome; parentesi nelle note; spazio tolto |
| "ROSSETTI" e "MARCO ROSSETTI" | Due medici | Stesso cognome, un nome solo: un medico |
| "Sost, protesi +pessi" e "Sostituzione protesi con pessi" | Due prestazioni | Abbreviazioni sciolte prima del confronto |
| Sala occupata alla stessa ora, stanza non indicata | La riga restava fuori, solo nell'Excel degli scarti | Va fra i da confermare, con i suoi dati |
| Nome del file e riepilogo nel titolo uniti | "Lippiello Data" preso per un medico | Le celle del titolo restano separate |
| Menu con la voce nuova | Andava a capo a 1366 pixel | Spaziature e ricerca più strette |

Diciottesimo giro, 1.10, le fasce di ogni turno (trovati provando con i calcoli a parte e
guardando la griglia nel browser):

| Difetto | Effetto | Correzione |
|---|---|---|
| Durata delle fasce come elenco obbligatorio con la prima scelta vuota | Il browser non avrebbe lasciato salvare il turno con *Come la struttura* | La prima scelta vale «0» |
| Righe fitte solo quando la misura delle righe cambia | Con un turno a fasce da 60 in una struttura da 30 le celle libere non coprivano le loro righe e la tabella si sfasava | La griglia a righe fitte vale per ogni turno con fasce proprie; ogni cella libera copre le sue righe |
| Appuntamenti presi prima delle fasce | Cambiare una nota a una visita che divideva una fascia con un'altra veniva rifiutato («fascia già occupata») | Modificando contano solo le fasce nuove; salvando il turno arriva l'avviso con quanti non stanno nelle fasce |
| Avviso dell'orario a metà fascia | Mancava se il medico scelto era assente quel giorno | Le fasce sono della stanza: l'avviso c'è sempre |
| Nome della prestazione nelle celle alte due righe | Con righe da 15 minuti ogni visita da 30 lo mostrava e allungava le righe: la griglia non era più in proporzione | Il nome compare solo dove c'è spazio (come prima); in una fascia corta medico e paziente su una riga |

Delle prove, non del programma: i giorni inventati mettevano due appuntamenti attivi alla
stessa ora nella stessa stanza, che il database non accetta (ora si saltano); nell'agenda del
medico della 1.9.1 «copre» poteva valere anche in una fascia dove comincia un altro
appuntamento, e lì la pagina mostrava comunque l'appuntamento (il confronto lo guarda solo
dove non comincia niente); la guida sullo schermo si leggeva dalla prima riga del fumetto,
che è il pulsante per chiudere (ora dal titolo).

Diciassettesimo giro, 1.9.1, l'email con qualsiasi casella (trovati rileggendo l'invio
della 1.9 per le caselle che non sono Gmail):

| Difetto | Effetto | Correzione |
|---|---|---|
| Spazi tolti da tutte le password | Gli spazi contano solo nella password per le app di Gmail: una password di casella con uno spazio dentro non sarebbe mai stata accettata | Spazi tolti solo per Gmail; per le altre solo quelli copiati prima e dopo |
| Server vuoto | Diventava da solo smtp.gmail.com, anche per una casella di un altro fornitore | Il server si propone secondo il tipo di casella; per un altro server senza nome, errore che lo chiede |
| Password non accettata | Il messaggio parlava sempre della password per le app di Gmail | Il consiglio giusto per Gmail, Microsoft e le altre caselle, con la risposta del server |
| SSL sulla porta 587, porta 465 senza SSL, certificato di un altro nome | Errori tecnici («WRONG_VERSION_NUMBER», «timed out»), riprovati per ore | Il messaggio dice cosa scegliere; quelli da correggere si fermano subito; salvando, un avviso |
| Server della rete interna senza password | «Email: da configurare» e la prova spenta finché non si scriveva una password | La spunta *Il server non chiede la password* |
| Nome utente diverso dall'indirizzo (servizi di invio) | Non si poteva entrare: si usava sempre l'indirizzo | Il campo *Nome utente per entrare nel server* |

Delle prove, non del programma: `prove_icone_animate.py` nella versione animata può non
trovare le icone se gira mentre la stessa macchina fa anche le prove nel browser dell'altra
versione (il lettore delle animazioni non fa in tempo a partire): da sola, o dopo le altre,
passa.

Sedicesimo giro, 1.9, Dove si fa (trovati provando la ricerca sul database vero, letto senza
copiarlo, e sulla pagina nel browser):

| Difetto | Effetto | Correzione |
|---|---|---|
| «nei» (le macchie della pelle) è anche una preposizione | La ricerca «nei» non trovava la mappatura dei nei | Se restano solo parole vuote, si cercano quelle |
| Parole di quattro lettere al plurale | «rx mani» non trovava *Radiografia mano*, «eco reni» non trovava *Ecografia renale* | Per le parole di quattro lettere vale anche il singolare o il plurale; reni e rene anche come renale |
| Nomi con il trattino nel database | «rm lombare» e «lombosacrale» non trovavano *RM rachide lombo-sacrale* | Le parole con il trattino valgono anche unite; lombare vale anche lombo |
| «cardiologo» | Prima *Riabilitazione cardiologica*, poi la visita | Chi scrive uno specialista trova per prima la visita |
| Recapiti nel foglio *Strutture* di una versione nuova del file | Avrebbero preso il posto di quelli corretti a mano nel programma | Il foglio riempie solo i recapiti che mancano |
| Tema scuro generato da `stile.css` | La riga colorata a sinistra delle strutture e il bordo tratteggiato di «da confermare» sparivano (il tema scuro riscrive il bordo intero) | Il colore della struttura è un'ombra interna, il bordo si scrive per parti |
| Avviso «Segnato…» al centro dello schermo | Con la scheda aperta finiva sotto la scheda | Al centro della parte libera della pagina |
| Testo con il paziente scelto | «WhatsApp ed email vanno a lui» anche per una paziente | «partono verso i suoi recapiti» |
| Guida sullo schermo della pagina | Sul gestionale vero la scheda della struttura non è aperta: i passi della scheda finivano al centro | La guida apre da sola la scheda della prima struttura |
| «Cosa si fa qui» nella scheda di una struttura | Un clic su una branca mostrava le prestazioni di tutte le strutture | Le prestazioni di quella struttura (filtro *Solo le prestazioni di…*, che si toglie) |

Delle prove, non del programma: una cercava il testo della correzione dove il programma
mette in grassetto la parola corretta; un'altra leggeva come una riga sola il testo di un
riquadro a colonne flessibili (il browser lo dà a righe); nella versione animata una misura
della scheda veniva presa mentre la scheda stava ancora entrando da destra (ora si aspetta
la fine del movimento).

Quindicesimo giro, 1.8, turni del personale e tendine (trovati provando, nel browser e con
le prove nuove):

| Difetto | Effetto | Correzione |
|---|---|---|
| Nella versione animata le animazioni con `fill-mode: both` creano contesti di sovrapposizione | La tendina *Stampa e scarica* restava in parte sotto la nota del giorno e la griglia | La barra ha il suo piano (`z-index` 40), le notifiche scendono a 30; una prova controlla con `elementFromPoint` |
| Il periodo della richiesta letto con `data_da(x, None)` | Senza periodo valeva *oggi*: la risposta ridisegnava le celle del giorno sbagliato | Lettura propria, che senza data dà «nessun periodo» |
| Classi degli avvisi dei turni con nomi già usati (`avviso`, `testo-avviso`) | Testo degli avvisi color ambra su fondo scuro | Nomi propri (`livello-…`, `parole-avviso`) |
| Il punto «al lavoro adesso» chiamato `adesso` | Nell'animata prendeva lo stile della linea rossa dell'agenda | `al-lavoro` |
| Ore del contratto «37,5» | Lette come 37 ore e 5 minuti | Decimali e ore:minuti distinti |
| Tutto il mese a 1366 pixel | Le colonne si allargavano sul contenuto e i totali uscivano a destra | Larghezze fisse delle colonne; lo spazio in più va diviso solo sugli schermi larghi |
| Copertura del mese «M2 N1 P2» su una riga | Tagliata nelle colonne strette, e in ordine alfabetico | Una riga per turno, nell'ordine dei tipi (M, P, N) |
| Orario scritto a mano nella cella stretta del mese | «8–12:30» usciva dalla cella | Su due righe, inizio e fine |
| Riposi e assenze nella vista del giorno sopra la riga delle ore | Coprivano la notte cominciata il giorno prima | Accanto al nome |
| Medico con turno e ambulatorio alla stessa ora | La barra del turno nascondeva l'ambulatorio | Ambulatorio in una striscia sotto il turno |
| L'esempio di cognome con «De» dell'importazione, scritto alla 1.7 al posto dei frammenti veri | Coincideva con un nome di un'agenda vera arrivata dopo | «DE FITTIZI TERESA»; il controllo dei dati veri prima della consegna legge anche quell'agenda |

Due rossi erano delle prove: una nuova prova dei festivi non sapeva che San Francesco
(4 ottobre) è di nuovo festa nazionale dal 2026, e un'altra cercava `<b>` in una pagina
dove `<b>` c'è per davvero (i codici della legenda).

Altri due, sempre delle prove e non del programma: `prove2.py` usava una porta fissa (5099),
e con le due cartelle provate insieme ogni tanto una trovava la porta già presa (ora la
sceglie il sistema); `prove_guida_browser.py`, nell'animata, quando Playwright rifaceva un
clic su un pulsante che entrava muovendosi lo portava in cima alla finestra e lasciava lì
il mouse, sopra il menu: dalla 1.8 in quel punto c'è *Segreteria*, la tendina si apriva e
copriva il pulsante della guida successiva (ora il mouse si sposta lontano dal menu prima
di ogni guida).

Quattordicesimo giro, 1.7, codice fiscale e passaggio di consegne:

| Difetto | Effetto | Correzione |
|---|---|---|
| Risposta del controllo del codice fiscale arrivata dopo un'altra modifica | Cancellato il codice e scritta subito la data, la risposta ancora in viaggio la riscriveva con quella del codice | Vale solo la risposta all'ultima modifica; data, sesso e luogo messi dal codice si aggiornano solo se nessuno li ha cambiati |
| Suggerimenti del luogo per «nap» | Anche Arena Po: le lettere si cercavano anche a cavallo di due parole | Si cerca l'inizio delle parole del nome; la provincia solo se il nome non dà niente |
| Nomi dei comuni dall'elenco ufficiale | «San Giorgio A Cremano», numeri romani minuscoli | Articoli e preposizioni minuscoli, numeri romani maiuscoli, come nei documenti |
| Prova d'invio di un'email automatica | Con il paziente finto della prova si fermava: gli mancavano sesso e luogo di nascita | Il paziente finto ha tutti i campi, e i segnaposto li leggono con prudenza |
| Esempi presi dalle agende vere nei commenti e nelle prove dell'importazione (dalla 1.4.1) | Un nome di battesimo raro, uno scritto male e un cognome dei file veri, anche se con i cognomi cambiati | Nomi inventati al loro posto; `strumenti/cerca_dati_veri.py` confronta i file veri con tutto il progetto prima di consegnare |
| Costruzione in un Windows finto nuovo | Con Python 3.14.8 `CREA_EXE.bat` si fermava creando l'ambiente isolato: Wine 9 non ha la funzione `CopyFile2`, che Python usa per copiare i file | `strumenti/wine/prepara.sh` la toglie al Python del Windows finto (sul PC della clinica non cambia niente) |

Della prova, non del programma: `prove_funzioni.py` generava codici fiscali con giorni
che non esistono, che ora giustamente non passano; `prove_15.py` voleva lo schema 7; le
prove nel browser, dopo un clic su *Salva*, leggevano la pagina senza aspettare quella
nuova (a volte trovavano la vecchia: ora aspettano la navigazione); le prove più vecchie
scrivevano in `/tmp`, che su Windows non c'è (ora nella cartella temporanea del sistema,
diversa per ogni giro di `tutte_le_prove.py`: le due versioni si provano anche insieme).

Tredicesimo giro, 1.6, provando «Aggiorna adesso» per intero sull'eseguibile:

| Difetto | Effetto | Correzione |
|---|---|---|
| Gestionale riaperto dal Setup di «Aggiorna adesso» | Ereditava le variabili interne dell'eseguibile a file unico (PyInstaller) e si fermava con *"Security validation failure: invalid originating onefile parent process"*: aggiornato, ma da riaprire a mano. Le prove senza eseguibile non potevano vederlo | Il Setup parte con l'ambiente pulito (`ambiente_pulito`), come da un doppio clic sull'icona; prova in `prove_16.py` e aggiornamento rifatto per intero |
| Setup appena installato | All'avvio della versione nuova era ancora aperto e non si poteva cancellare: restava nella cartella degli aggiornamenti | Si riprova a ogni giro del controllo |
| Indirizzo cambiato mentre un controllo è in corso | Il controllo del nuovo indirizzo non partiva: restava il risultato del vecchio | Il controllo chiesto dalla pagina aspetta quello in corso e poi parte |
| Pagina Aggiornamenti composta proprio mentre il controllo finisce | Visto una volta nel browser: la versione nuova risultava «non ancora scaricata» quando era già pronta, e la pagina non si aggiornava più | La pagina, la notifica e `stato.json` leggono lo stato una volta sola; una prova riproduce il momento esatto |
| Indirizzo `https://github.com/../x` | Accettato, diventava un indirizzo senza senso | Utente e progetto devono cominciare con una lettera o una cifra |
| *Controlla adesso*, o un indirizzo nuovo, mentre gira il controllo delle sei ore (con l'indirizzo predefinito succede davvero) | Fra i due controlli la pagina vedeva per un attimo «finito»: si ricaricava con il risultato del primo e non seguiva più il secondo | *Controllo in corso* resta acceso finché un controllo aspetta il suo turno; una prova ferma il secondo proprio in quel momento |
| Progetto GitHub senza versioni pubblicate | La pagina diceva solo «pubblicata senza quel file, oppure l'indirizzo è sbagliato» | Dice anche che lì non è stata ancora pubblicata nessuna versione |

Della prova, non del programma: lo script che allinea le due cartelle, rilanciato, aveva
scritto due volte la riga `[Run]` nuova nell'`installer.iss` dell'animata (il gestionale
sarebbe ripartito due volte: ora una prova conta le righe), e il Setup finto delle prove,
generato un byte alla volta, rendeva la prova lunga minuti.

Dodicesimo giro, 1.4.6, la seconda parte della stessa revisione: sette segnalazioni, il
modulo comune e il WAL. Anche qui ognuna riprodotta prima di toccare il codice, in
`prove_146.py`.

| Difetto | Effetto | Correzione |
|---|---|---|
| Moduli mandati da un'altra pagina aperta nello stesso browser | Un sito qualsiasi poteva cambiare le impostazioni o eliminare appuntamenti (gli indirizzi sono numeri in fila); provato in Chromium con un modulo, con `fetch` e con una cornice isolata. Con il DNS rebinding poteva anche leggere le pagine | Solo indirizzi `127.0.0.1` e `localhost`; moduli solo dalle pagine del gestionale. La correzione proposta lasciava passare "Origin: null" e ogni porta del PC |
| Importazione, medici con lo stesso cognome | Un medico non più attivo si prendeva gli appuntamenti dell'omonimo attivo; con due attivi se ne sceglieva uno in silenzio | Prima il nome intero, poi cognome e iniziale, poi il cognome; gli attivi prima; due attivi: si sceglie il primo e l'anteprima lo dice. La correzione proposta, con due attivi, creava un terzo medico |
| Email dell'agenda e del riepilogo del medico | Il limite di 1800 caratteri era sul testo prima della codifica: l'indirizzo arrivava a 3000 caratteri, oltre quello che Outlook apre; l'agenda si tagliava a metà riga | Limite sull'indirizzo codificato (`MASSIMO_MAILTO`), taglio all'ultima riga intera, una funzione sola per le due email |
| File Excel scaricati | Planning, incassi e riepiloghi, con nomi e telefoni, restavano nella cartella temporanea di Windows | Nascono in memoria |
| Suggerimenti dei pazienti mentre si scrive | Senza "no-store": nomi e telefoni restavano nella cache del browser. Le funzioni di servizio erano copiate in dieci file e questa copia si era allontanata dalle altre | `comune.py`, una copia sola |
| Chirurghi assenti | In ordine di inserimento, e compariva anche chi non è più attivo | In ordine di cognome, solo gli attivi |
| Eliminazione di un turno | Nessun avviso degli appuntamenti già presi in quel turno, che restano fuori turno; eliminare invece di chiudere cambia le ore di turno dei mesi passati | Avviso con il numero; la pagina del turno e la guida indicano "Fino al" |
| `{Paziente}` o `{DATA}` nei moduli e nei messaggi | Restavano scritti così (Word mette la maiuscola a inizio frase) | Maiuscole o minuscole, vale lo stesso segnaposto |

Non vere: la data di un modulo non può uscire dal calendario (le date degli appuntamenti
stanno fra il 1900 e il 2100); i nomi nelle istruzioni di aggiornamento del database sono
costanti del programma; il tempo d'attesa di SQLite non è basso ma di 5 secondi, e il WAL
avrebbe tolto le ultime modifiche alle copie di `BACKUP.bat` (vedi *Tre scelte volute*).
`{recapito}` e il nome in maiuscolo nei moduli erano già stati valutati al giro prima.

Undicesimo giro, 1.4.5, da una revisione esterna del codice (27/09/2026). Venti
segnalazioni, ognuna riprodotta con una prova prima di toccare il codice: dodici vere, tre
vere in parte, cinque non vere; della sesta è vera solo la seconda metà (un limite a 26
colonne nell'Excel delle statistiche, che ne ha al massimo sette: sistemato comunque).
`prove_145.py` le contiene tutte.

| Difetto | Effetto | Correzione |
|---|---|---|
| Importazione, tre righe alla stessa ora nella stessa stanza | La terza risultava nuova in anteprima e al momento di scrivere finiva fra gli scartati, senza diventare un appunto | Ogni riga si confronta con l'ultima entrata, non con la riga prima |
| Importazione, stanza occupata fra anteprima e importazione | La riga finiva fra gli scartati anche con "le righe in conflitto diventano appunti" | Diventa un appunto, come i conflitti visti in anteprima |
| Importazione, "ROSSETTI" e "MARCO ROSSETTI" | Un medico solo, ma se era in due stanze alla stessa ora l'avviso non compariva | Le righe dei nomi riuniti puntano al medico che resta |
| Importazione, importi | Accettati fino a un milione, il modulo fino a centomila: l'appuntamento importato non si salvava più | Un limite solo per tutti (`MASSIMO_IMPORTO`) |
| Importazione, "Testo Unicode" di Excel e CSV del Mac | Errore 500 al caricamento | UTF-16 riconosciuto dal BOM; gli a capo li legge il modulo csv; un file illeggibile dà un messaggio |
| Serie di appuntamenti | Degenza e notti non copiate (dalla 1.4.3 non stanno più fra i campi in più): letti contati solo per il primo | Copiate; la checklist no, ogni intervento ha la sua |
| Stanza con appuntamenti futuri tutti disdetti | Non si poteva disattivare | Contano solo gli attivi |
| Assenza o chiusura da oggi | L'elenco da spostare contava anche gli appuntamenti di stamattina già passati, lo spostamento in blocco no | Tutti e due da adesso in poi; quelli passati restano nella chiusura della giornata |
| Settimana del medico | Le mezz'ore dentro un intervento lungo comparivano "libero", con il link per prenotare | Occupate, come nella griglia del giorno |
| Prenotazione senza scegliere dall'elenco | Accenti, apostrofo curvo del telefonino o il secondo telefono creavano un doppione del paziente; un "telefono" senza cifre ("non ha") agganciava la scheda di un altro paziente con lo stesso cognome e senza telefono | Stesso confronto della ricerca, su tutti e due i telefoni; conta solo un numero di almeno sei cifre |
| Telefono di due cifre in prenotazione e in lista d'attesa | Accettato, poi la scheda del paziente non si salvava più | Almeno sei cifre, come nella scheda |
| Importo 0 (gratuito) | "Da incassare" in Oggi e in Cassa | Escluso; senza importo resta, finché non si sa |
| Statistiche con più strutture | Pazienti nuovi e provenienza erano di tutte le strutture | Quelli con un appuntamento nelle stanze della struttura; con una sola, tutti |
| Eliminazione di un appuntamento, impostazioni | Scrivevano senza il lucchetto dei salvataggi | Sotto il lucchetto, come il resto |
| Più appunti messi in agenda insieme | Se scattava il vincolo del database, errore 500 | Messaggio, e nessun appuntamento a metà |

Quelle non vere sono fissate da prove, perché nessuno le "corregga": il ritorno dopo un
paziente nuovo è già sempre interno; nel testo dei messaggi la sostituzione "a vuoto"
segnalata non esiste, e la lista proposta al suo posto lascerebbe " ." e ".." nei testi
personalizzati; la degenza fuori dalle sale operatorie è voluta (endoscopia, e il letto è
della struttura, non della stanza): toglierla perderebbe un dato visibile e farebbe
risultare liberi dei letti occupati; `{recapito}` non fa parte dei segnaposto dei moduli
e, come ogni segnaposto sconosciuto, resta visibile; un orario rovinato il modulo non lo
accetta e la griglia lo regge; l'ultima fascia finisce entro mezzanotte, e la modifica
proposta ne aggiungerebbe una che la supera. Le correzioni proposte per messaggi, degenza
e ultima fascia, applicate a una copia, fanno fallire tre prove su sei.

Decimo giro, 1.4.4, menu e guida:

| Difetto | Effetto | Correzione |
|---|---|---|
| La guida "stampa" aveva lo stesso indirizzo della guida da stampare | L'articolo non si apriva | Rinominata; una prova impedisce che ricapiti |
| Tendina chiusa con Esc | Spostando il mouse si riapriva | Resta chiusa finché mouse e tastiera non escono dal gruppo |
| Durante la guida | Le notifiche restavano sopra l'ombra | Nascoste finché la guida è aperta |
| Pagine della guida | Prendevano il bordo giallo di un riquadro con lo stesso nome | Nome proprio |

Nono giro, 1.4.3, sala operatoria e pagina Oggi:

| Difetto | Effetto | Correzione |
|---|---|---|
| Degenza fra i campi in più della prestazione | Non si potevano contare i letti | Campo vero dell'appuntamento; l'aggiornamento sposta i valori già importati |
| Notifiche: si guardavano solo le prime quattro | Chiuse quelle, le altre non comparivano più | Prima si tolgono le già chiuse, poi le quattro, errori per primi |
| Opzioni della stanza con un attributo in più | La prova sulla stanza disattivata non la trovava più (era la prova) | Confronto che ammette altri attributi |
| Menu con Oggi e Sala | Andava a capo a 1366 pixel | "Lista d'attesa" diventa *Attesa*, "Stanze, medici e turni" *Anagrafiche* (il nome intero resta passandoci sopra) |
| Incasso di oggi nel tema scuro | Cifra blu su fondo scuro, poco leggibile | Aggiunta alle correzioni del tema |

Anche qui una parte dei rossi era della prova: un conteggio atteso sbagliato (un
pagamento annullato torna da incassare), la parola "arriva" cercata nella pagina dove
compare nel testo d'esempio del campo, un conflitto messo su un appuntamento già
spostato, nel browser l'attesa di una pagina che non aveva ancora cominciato a caricarsi,
il database dimostrativo con lo stato del giro precedente, e nella campagna un'invariante
"nessuna sovrapposizione" violata apposta da un'altra parte della campagna stessa.

In una campagna generativa, e in generale nelle prove, una parte dei rossi è della prova e
non del programma: in questi giri è successo più volte, e va sempre isolato prima di
toccare il codice. Nel quinto giro tre rossi su cinque erano della prova: un apostrofo
cercato nell'HTML dove compare come `&#39;`, la misura del logo letta dall'immagine invece
che dall'ancoraggio nel foglio, i bordi sfumati del JPG.

Giro della 1.11 (novembre 2026, con Claude Code): una revisione del codice per parti
(agenda, pazienti, importazione, messaggi, turni del personale), uno studio dei guasti per
l'autoriparazione e, per ogni difetto, una riproduzione fatta da un controllo indipendente
prima di correggerlo. Ogni correzione ha la sua prova in `prove_111.py` (o in
`prove_autoriparazione.py`), e le prove sono state lanciate anche sul codice della 1.10:
falliscono, cioè il difetto c'era davvero.

| Difetto | Effetto | Correzione |
|---|---|---|
| Ripristino dalle impostazioni con il database rovinato | Si fermava: la copia di sicurezza del database attuale non passava il controllo, proprio quando serviva ripristinare | Il database rovinato si copia così com'è fra i danneggiati e il ripristino va avanti |
| Riga `versione_schema` mancante | Le migrazioni vecchie si rifacevano e ogni *Confermato* tornava *Prenotato* | La versione si ricava da tabelle e colonne, e la riga si riscrive |
| Orologio del PC indietro | La copia appena fatta era la più vecchia e la rotazione la cancellava subito, ogni ora, senza dire niente | La copia appena fatta non si cancella mai; la pagina dice che l'orologio è indietro |
| Copia che non si scrive (disco pieno, chiavetta tolta) | Restava il suo `.parziale`, uno in più a ogni tentativo | Il `.parziale` si toglie sempre; all'avvio si tolgono quelli rimasti |
| Copie della cartella accanto al database | Con un'altra cartella scelta non si vedevano (le *prima della versione*, per esempio) | La pagina mostra e rimette le copie di tutte e due le cartelle |
| Porta 5000 occupata, o riservata da Windows | Il browser si apriva su una pagina morta; due copie del programma potevano servire la stessa porta | Un gestionale solo (lucchetto), il server lega la porta prima di aprire il browser, porta di riserva |
| Messaggio in attesa di riprovare, paziente cambiato | L'indirizzo di prima riceveva la preparazione con il nome e la prestazione del paziente nuovo | Il messaggio si annulla e si rimette in coda per il paziente e il recapito di adesso (anche i promemoria) |
| Promemoria per il giorno di prima | Spostato l'appuntamento, Conferme diceva «inviato» e toglieva *Manda* | Conta solo il promemoria del giorno dell'appuntamento |
| Disdetto rimesso in agenda con un clic | L'email annullata quando era disdetto non ripartiva più | Rimesso attivo, riprende le sue email automatiche |
| Password della casella con lettere accentate o € | Ogni email si fermava con «errore inatteso: ascii codec» | Accesso in UTF-8 (AUTH PLAIN); se il server non lo offre, l'errore dice cosa correggere |
| Email di un appuntamento poi eliminato | Non contava più: la stessa email partiva una seconda volta | Conta anche senza appuntamento |
| Modifica di un appuntamento di una serie | Ripartiva l'email automatica, che per la serie deve essere una | Una per regola e paziente in tutta la serie |
| Indirizzo del paziente con una lettera accentata | La colpa andava alle impostazioni dell'accesso | L'errore dice che l'indirizzo va corretto nella scheda del paziente |
| Stanza disattivata con i suoi turni | Prima disponibilità, Sposta, spostamento in blocco e agenda del medico la proponevano: l'appuntamento spariva dalla griglia | Non si propone e non si sceglie; i turni restano per le statistiche |
| Anno fuori calendario nel modulo | 0026 (anno a due cifre) si salvava invisibile; 31/12/9999 dava un errore del server | Accettati solo dal 2000 al 2100, anche nel campo della data |
| Sostituzione di un giorno | Il turno del medico sostituito non si salvava più (fasce, *Fino al*) | La sovrapposizione con la sostituzione nel giorno della sua assenza non conta |
| Fasce intere, modificando | Si perdonavano tutte le fasce dell'altro appuntamento, non solo quelle già divise | Solo le fasce già divise |
| Fasce intere, prima del turno | Un appuntamento iniziato prima del turno e finito in una fascia occupata passava o no secondo l'ordine | Conta il turno a fasce che l'appuntamento tocca |
| Unione di due schede | Il cellulare dell'altra scheda si perdeva | I numeri in ordine, senza doppioni; quelli in più nelle note |
| Codice fiscale calcolato e omocodia | La scheda giusta veniva scartata e nasceva un doppione | Confronto senza le lettere dell'omocodia |
| Paziente scelto e poi cambiato | Con nome e data di nascita di un altro, la scheda scelta veniva sovrascritta | È un'altra persona: la scheda scelta resta |
| Importazione: orari scritti come numeri (9,30 = 9,3) | Righe scartate per «manca l'ora»; un'agenda ogni 20 minuti non si importava | Le cifre dopo la virgola sono i minuti |
| Importazione: anno di nascita a due cifre | Nati dal 1927 al 1969 diventavano del 2065 e la data si toglieva | La data più recente non nel futuro, con un avviso dal 2000 |
| Importazione: stanza nuova con il nome lungo | Dalla seconda importazione, errore e niente importato | Il nome tagliato a 60 caratteri si ritrova; nessuna stanza doppia |
| Importazione: la stessa sala con maiuscole diverse | Due stanze, e due appuntamenti alla stessa ora entravano tutti e due | Una stanza sola, con il conflitto |
| Importazione: una riga disdetta | Occupava la stanza: la prenotazione vera alla stessa ora finiva fra i da confermare | Le righe disdette non occupano e non si duplicano reimportando |
| Importazione: oltre 20.030 righe | Il file si troncava senza dirlo | L'anteprima e la pagina finale lo dicono |
| Importazione: «Dott. Galasso» nella colonna del medico | Nasceva un medico nuovo «Galasso Dott.» | Il titolo si toglie (anche «D.SSA») |
| Importazione: durata come orario, o «INF» | 0:45 non si leggeva; «INF» dava un errore del server | Si legge come ore e minuti; quello che non si legge si segnala |
| Importazione rifatta | Le stesse righe in conflitto diventavano ogni volta un da confermare nuovo | Non si aggiungono di nuovo; quelle entrate in agenda chiudono il loro |
| Importazione della rubrica: la stessa persona su due righe | I dati della seconda riga si perdevano | La seconda riga completa la scheda |
| Turni: Annulla dopo aver tolto i turni di chi non è più in servizio | Annulla si rifiutava, e in un blocco misto non tornava niente (anche i turni dei colleghi in servizio) | Annulla rimette i turni com'erano; le sovrapposizioni restano rifiutate |
| Turni: filtro per area | Una cella che sembrava vuota sostituiva il turno nascosto di un'altra area (con la sua nota); il turno nuovo restava invisibile | Si cambia solo quello che si vede; il turno nuovo prende l'area del filtro |
| Turni: Ctrl+Z mentre si scrive un codice, o mentre si salva | Annullava la modifica di prima e il codice scritto si salvava lo stesso | Ctrl+Z lascia perdere il codice in scrittura; la modifica da annullare si sceglie in coda |
| Autoriparazione: pagina di una tabella rimasta fuori dall'albero (corrente saltata) | Si riparava dicendo «senza perdere niente», e le righe più recenti sparivano | Una pagina «mai usata» con delle righe sono righe perse: si rimette la copia e si dice da che ora ricontrollare |
| Autoriparazione: copia da rimettere sparita nel frattempo | Si creava vuota e andava al posto del database | Le copie si aprono in sola lettura e si controllano prima; una copia che non c'è ferma tutto |
| Autoriparazione: errore «malformed» di un indice che non corrisponde ai dati | Il controllo veloce diceva «integro» e non si riparava | Dopo un errore «malformed» il custode fa il controllo completo |
| Autoriparazione: programma occupato (salvataggi in coda, riparazione lunga) | Il secondo clic lo chiudeva dopo mezzo minuto come se fosse bloccato | Il custode batte in gestionale.pid: chi batte si aspetta (2 minuti e mezzo), chi non batte da 90 secondi si chiude |
| Autoriparazione: chiusura con taskkill /T | Avrebbe chiuso anche il browser aperto dal gestionale (suo figlio) | Si chiude solo il processo (anche nel Setup e in FERMA.bat) |
| FERMA.bat chiudeva chi ascolta sulla porta 5000 | Con il gestionale su una porta di riserva chiudeva un altro programma | Chiude Gestionale.exe per nome |
| Copia di sicurezza con la data nel futuro (orologio avanti) | Fermava le copie recenti, veniva rimessa al posto di una buona, l'avviso dell'orologio nascondeva «Backup non riuscito» | Per ultima nella scelta, non conta come l'ultima, gli avvisi si sommano |
| Ripristino con la cartella scelta irraggiungibile | Rifiutato, anche delle copie accanto al database | La copia di prima del ripristino va accanto al database |
| Avvio con la cartella delle copie su un NAS spento | L'avvio aspettava la risposta della rete | All'avvio si guarda solo la cartella accanto al database |
| Riavvio da solo non riuscito | Il programma restava aperto senza il lucchetto: un secondo clic apriva un altro gestionale sullo stesso database | Il lucchetto torna al programma |
| Processo riconosciuto dal solo nome | «Gestionale.exe» può essere un altro programma; un numero di processo riusato | Percorso intero e ora di avvio del processo |
| Pagine dentro la cornice di un altro sito | Un sito ostile con la cornice trasparente sopra un pulsante esca faceva cliccare «Disdetto» | Nessuna pagina si mostra in una cornice (`X-Frame-Options`, `frame-ancestors`) |
| Dove si fa con più strutture | Ogni paziente indirizzato finiva nel registro della prima struttura | La struttura della pagina va nella richiesta |
| Nota con un carattere di controllo (incollata da Word) | L'Excel del planning e il riepilogo del mese davano un errore del server finché nessuno trovava la nota | La nota si pulisce al salvataggio; le celle di tutti gli Excel ripuliscono anche le note vecchie |
| Documento oltre il massimo | Rispondeva «405 Method Not Allowed» invece del messaggio | Si torna alla scheda del paziente con il messaggio |
| Dove si fa: «ecografia dell'addome», «rx dell'anca» | Zero risultati: «dell'» non era fra le parole vuote | Aggiunte le parole con l'apostrofo |
| Richieste JSON di forma inattesa | Errore del server (solo a mano) | Un JSON che non è un dizionario non ha campi |
| Controllo degli aggiornamenti: «il certificato del sito degli aggiornamenti non è valido» (1.9 alla clinica) | Windows non aveva ancora la radice nuova di GitHub (la aggiunge solo quando la incontra con Edge); Python usa l'elenco di Windows così com'è | L'elenco Mozilla (certifi) dentro il programma, più il file `certificati.pem` accanto al database; il motivo spiegato e il collegamento per il Setup a mano |
| Turni di notte nelle notti del cambio dell'ora (trovato dalla revisione della 1.11) | Contavano 10 ore sia a marzo sia a ottobre, anche nell'Excel e nei riposi | Dalla 1.12.1 contano le ore passate davvero (9 e 11): `calendario.minuti_veri`, con la regola europea scritta nel programma |
| Due codici dei turni scritti di seguito senza aspettare («M» e subito «P») | «Nessun turno ha il codice MP» | Dalla 1.12.1 si separano: vale il codice più lungo con cui comincia il testo, le lettere dopo ricominciano sul giorno seguente |
| `backup\danneggiati` cresceva senza limite | I file rovinati messi da parte non si toglievano mai, nemmeno dopo anni | Dalla 1.12.1 *Controllo del programma* dice quanto occupano e li svuota su richiesta, solo quelli da più di 90 giorni |
| Prove sul Windows di GitHub (1.12.1) | `pid_vero` usava `wmic`, che non c'è più; una prova voleva zero certificati di sistema; una porta chiusa sembrava un sito che non risponde; gli appunti con a capo CRLF | Processi letti con Toolhelp (`ctypes`); la prova conta che il programma abbia più certificati del sistema; 5 secondi di attesa per la porta chiusa; a capo normalizzati nel confronto |
| Riepilogo live poco chiaro (segnalato da Giovanni l'8 novembre 2026) | Otto numeri che non sommavano al totale, «in ritardo» solo per tre ore, il medico scritto due volte, «libera fino alle» senza dire perché, sessanta mezze giornate in una lista, le notifiche sopra le stanze | Dalla 1.12.2: quattro gruppi che sommano, una frase in cima, la linea del tempo con turni e visite, le mezze giornate in una tabellina, niente notifiche su quella pagina |
| Nessun riepilogo «non live» (richiesta di Giovanni dell'8 novembre 2026) | Per sapere com'era andata una settimana o un mese bisognava mettere insieme statistiche, pianificazione e agende | Dalla 1.12.2 *Ambulatori → Riepilogo del periodo*: ore di turno e occupate, conti e mezze giornate libere per stanza, medico e giorno, in Excel e da stampare |
| Riepilogo del periodo, prima della pubblicazione (revisione della 1.12.2) | Un medico in due stanze nello stesso momento contava le ore doppie; le visite dopo la mezzanotte e le stanze disattivate sparivano; un festivo con un turno sembrava chiuso; due mesi interi con le frecce diventavano uno; «il 0%» | Ore del medico unite su tutte le stanze, la coda dopo la mezzanotte nel giorno dopo, le stanze disattivate con i loro appuntamenti, il festivo aperto se ha turni, le frecce sullo stesso numero di mesi, «lo 0%»; una prova contata a mano |
| Verifica indipendente della 1.12.3, prima della pubblicazione | Un turno di sala prima delle 8 o dopo le 20 spariva dalla settimana (il chirurgo «senza turno»); con due turni sovrapposti un intervento contava due volte; un giorno di sola sala aggiungeva una colonna alla matrice della direzione e una riga al riepilogo live; nella pagina del mese una chiusura con un intervento perdeva il motivo; altri testi e il telefono | Mezze giornate della sala da mezzanotte a mezzanotte; un intervento, un turno; la matrice e il live come prima; il motivo per primo; prova con tutti i casi limite, e ogni difetto rimesso apposta fa fallire una prova |
| Esportazioni della sala separate da quelle degli ambulatori (richieste di Giovanni, 9 novembre 2026) | La matrice della settimana e la programmazione del mese lasciavano fuori la sala operatoria, la sala non aveva un Excel e non c'era un file unico per giorno, settimana e mese | Dalla 1.12.3 la sala nella settimana e nel mese in pagina, e *Esportazioni in Excel*: giorno, settimana e mese per ambulatori, sala operatoria o tutto insieme in fogli separati; i conti e gli Excel classici degli ambulatori uguali a prima |
| Anteprima delle esportazioni della 1.12.3, stampate su A4 e guardate da nove revisori (10 novembre 2026) | Il planning della sala del giorno con titolo e legenda tagliati, su due pagine e con le righe da 15 minuti dell'endoscopia; fasce libere a strisce; grigio e azzurro uguali su carta; la testata di ogni pagina sopra il titolo (0,1 pollici di spazio); caratteri senza nome nei fogli di settimana e mese; «al 8» senza apostrofo; nel calendario righe senza data dopo un salto pagina; la sala del mese su due pagine; il totale tagliato dai bordi; orari attaccati al testo accanto; una data sola scritta come numero | 1.12.4: ognuna corretta con la sua prova in `prove_112.py` o `prove_112_excel.py`, che con il codice della 1.12.3 falliscono (dieci). Lasciati com'erano, da decidere: la stampa piccola dell'elenco del giorno e delle matrici (stanno in una pagina in larghezza) e il verde, che vuol dire appuntamento nel planning e libero nella matrice |
| Riepilogo del periodo, seconda revisione (1.12.2) | I turni di una stanza disattivata contavano anche dopo lo spegnimento; la sola coda dopo la mezzanotte non la faceva comparire; una visita fino alle 24:00 lasciava una riga del medico a zero; un giorno chiuso con soli disdetti sembrava aperto; le prove dell'Excel avevano solo ore intere | Turni della stanza spenta fino al suo ultimo appuntamento; la coda la fa comparire; niente coda alle 24:00; i disdetti non aprono il giorno; Excel provato cella per cella con un terzo d'ora |

Nota sullo schema: `create_all` crea le tabelle mancanti ma non modifica quelle già
esistenti. Le colonne nuove le aggiunge `aggiorna_database` con `ALTER TABLE`, al primo
avvio. I vincoli invece così non si cambiano: per questo la 1.3 ricostruisce la tabella
degli appuntamenti (vedi *Aggiornamento dalla 1.2*). Da questa versione il database porta
il numero di versione dello schema nella tabella `impostazioni`, e ogni passaggio parte
da quello. Se su un database vecchio ci fossero già due appuntamenti attivi sulla stessa
stanza e ora, il vincolo nuovo non si crea, il registro lo dice e resta il lucchetto
applicativo.
