> Nota del 22/11/2026: dopo questo resoconto il lavoro è stato portato nel ramo di lavoro `ccr-interfaccia` (fino al commit 9eb7800) e caricato su GitHub in quel ramo. Non è pubblicato e non è nel ramo principale: in clinica non cambia niente.

# Usare il programma dagli altri PC: stato finale

Per Giovanni, 22 novembre 2026, sera. Sulla tua richiesta dello stesso giorno: «dammi la possibilità di scegliere quale
modulo rendere disponibile sugli altri PC della rete in locale a quale utente e quale no».

**In breve.** È pronto, e l'ho verificato da capo un'altra volta, senza fidarmi dei resoconti di prima. È nel ramo di
lavoro `accessi`, in sei commit: 025e22e, 605b63f, 7e94a8a, e5e3d31, 4c1797a e 9eb7800, che è mio (vedi il punto 8).
**Non è pubblicato, non è unito al ramo principale e non ho fatto push.** In clinica non è cambiato niente.

Rispetto al resoconto di prima sono cambiate tre cose importanti:

1. **Un guasto grave trovato dalla seconda revisione, ora corretto.** Nel programma vero (l'eseguibile del Setup, e
   anche avviando `app.py` a mano) bastava aprire la pagina «Aree e accessi» per far rispondere **errore a tutte le
   pagine**, anche sul PC della segreteria, fino alla chiusura del programma. Succedeva anche con l'accesso dalla rete
   spento, se arrivava una richiesta della dashboard dal «portiere» (Caddy). Le prove non lo vedevano, perché avviavano
   il programma in un altro modo. Corretto alla causa, con le prove che avviano il programma come l'eseguibile. Io l'ho
   rifatto sull'eseguibile costruito apposta nel Windows finto: con quello di prima della correzione il guasto c'è,
   con quello di adesso no (punto 6).
2. **«Statistiche e report» non è più una domanda aperta**: ho applicato la regola che ti avevo proposto (punto 4). Se
   la vuoi diversa, si cambia.
3. **Altri 13 difetti più piccoli** trovati dalla seconda revisione sono corretti (punto 7).

---

## 1. Cosa puoi fare

Puoi scegliere, **persona per persona**, quali parti del programma può usare da un altro PC della rete della
clinica, e in che modo. Per ognuna delle 12 parti ci sono tre scelte:

- **non disponibile**: la parte non si apre. Esce una pagina che dice «… non è fra le parti disponibili per questo
  utente», con il nome della persona e dove si cambia (Configura → Impostazioni → Aree e accessi);
- **solo guardare**: si aprono le pagine e si scaricano i file di quella parte, ma non si salva niente. Da questo
  giro i bottoni per salvare sono **spenti**, con una riga in cima alla pagina che lo spiega: prima si poteva scrivere
  e poi, al clic, si perdeva tutto;
- **guardare e modificare**: come dal PC della segreteria.

Le 12 parti sono: Agenda, Pazienti, Segreteria, Cassa, Sala operatoria, Turni, Ambulatori e dashboard, Statistiche e
report, Dove si fa, Email e WhatsApp, Anagrafiche, Guida e aiuto.

Quello che è di un'altra parte resta di quella parte anche dentro le pagine. Esempi che ho visto succedere davvero:

- chi ha solo i Pazienti vede la scheda del paziente **senza** le cose da fare e la lista d'attesa (sono della
  Segreteria);
- chi ha solo l'Agenda vede il giorno **senza** gli appunti «Da confermare» della Segreteria;
- chi ha solo le Anagrafiche **non vede e non cambia** il prezzo di listino (è della Cassa);
- chi usa la ricerca dei pazienti da «Dove si fa» riceve solo nome, data di nascita e telefono, non codice fiscale e
  indirizzo;
- chi ha la Sala da guardare vede la checklist con le caselle spente.

Ogni persona ha il suo nome e la sua password, e al primo accesso se ne sceglie una sua. Le password troppo facili
sono rifiutate. Una frase di tre o quattro parole va bene.

## 2. Come si accende

1. Sul PC della segreteria apri **Configura → Impostazioni** e premi **«Aree e accessi»** (accanto a «Controllo del
   programma»).
2. In «Nuovo utente» scrivi il nome e una password per il primo accesso (almeno 10 caratteri; la vedi mentre la
   scrivi, perché va detta alla persona), scegli parte per parte cosa può fare e premi «Aggiungi l'utente». Se la
   password non va bene, la pagina resta lì con nome e parti già scelti e ti dice il perché.
3. In alto spunta «Gli altri PC della rete possono aprire il programma, con nome e password» e premi **Salva**. La
   porta è la 5080: si cambia solo se un altro programma la usa già.
4. La prima volta Windows chiede il permesso per la rete: spunta **Reti private**, togli **Reti pubbliche** e premi
   «Consenti accesso» (serve la password di un amministratore). **Attenzione:** se si preme «Annulla», Windows blocca
   il programma, e il blocco vince su tutto. La pagina lo spiega e, nel riquadro chiuso «Per l'assistenza», dà i due
   comandi: uno toglie le regole del programma, l'altro lo lascia ricevere. Sotto «Acceso» la pagina dice anche
   l'ultima richiesta arrivata da un altro PC: se non ne arriva nessuna, quasi sempre è il firewall.
5. Sugli altri PC apri nel browser l'indirizzo che la pagina scrive nel riquadro «Acceso», per esempio
   `http://NOME-DEL-PC:5080/`. Poi nome e password e «Entra».

La stessa spiegazione è nella guida: **Aiuto → «Far usare il programma dagli altri PC»**, con immagine e video rifatti.

Dalla stessa pagina puoi: cambiare le parti di una persona, spegnerla (esce subito), darle una password nuova, farla
uscire, sbloccarla dopo troppe password sbagliate, vedere gli ultimi accessi. **Spegnere l'accesso dalla rete fa
uscire tutti**: riaccendendolo, ognuno rientra con la sua password.

## 3. Cosa resta solo sul PC della segreteria

- **Il PC della segreteria resta come oggi**: tutto da `http://127.0.0.1:5000`, senza password. Ho confrontato le sue
  pagine con quelle del programma di oggi (punto 6): uguali.
- **Il «Sistema» non si dà a nessuno**: aggiornamenti, copie e ripristino, controllo del programma, Impostazioni,
  configurazione di email e WhatsApp, la pagina «Aree e accessi».
- Il Modo schermo della dashboard senza password solo se lo spunti tu (spento di partenza). Con l'accesso dalla rete
  spento, Caddy funziona come oggi.

## 4. Due regole decise in questo giro (le puoi cambiare)

**Statistiche e report.** Dagli altri PC:

- nomi, telefoni ed email dei pazienti solo a chi ha anche **Pazienti** o **Agenda**;
- importi, convenzioni e incassi solo a chi ha anche la **Cassa**;
- vale nelle pagine e negli Excel (statistiche, riepilogo dei medici con l'email già scritta, esportazioni). Le
  colonne sono tolte, non lasciate vuote. Sul PC della segreteria tutto come prima.

L'ho provato con quattro persone, su 70 pagine e file Excel ciascuna, cercando i nomi, i telefoni e le email di tutti
i pazienti di prova e gli importi (il valore 250,77 €, il simbolo €, le convenzioni):

| Chi | Nomi, telefoni, email | Importi e convenzioni |
|---|---|---|
| solo Statistiche | nessuno | nessuno |
| Statistiche e Cassa | nessuno | ci sono |
| Statistiche e Agenda | ci sono | nessuno |
| Statistiche, Pazienti e Cassa | ci sono | ci sono |
| PC della segreteria | ci sono | ci sono |

Una cosa da sapere: la tabella «Chi li manda» delle statistiche (il campo «Inviato da» della scheda) resta visibile a
tutti quelli che hanno le Statistiche. Di solito ci sono nomi di medici. Se in clinica ci scrivete anche nomi di
persone, dimmelo e la tolgo a chi non ha i Pazienti.

**Copia di sicurezza rimessa.** Gli accessi dagli altri PC (utenti, password, parti, accensione) **non tornano
indietro** con una copia: così chi hai spento oggi, o chi ha cambiato password oggi, non rientra con quella di ieri.
Vale per il ripristino dalle Impostazioni (il messaggio lo dice) e per le riparazioni del programma (lo scrive il
diario). Per le riparazioni il programma tiene un file a parte accanto al database: se quel file manca o è rovinato,
l'accesso dalla rete resta spento finché non controlli tu.

## 5. Limiti da sapere

- **Collegamento senza protezione (http).** Nomi, password e dati passano in chiaro nella rete della clinica: solo
  nella rete interna del personale, mai in una Wi-Fi aperta ai pazienti, mai da fuori. La protezione https, con
  Caddy, è un passo successivo.
- **Firewall**: il bottone che apre la porta con il permesso di Windows, e il controllo automatico del tipo di rete
  («Pubblica» o «Privata»), sono **rimandati**: nel Windows finto non si possono provare. Per ora ci sono la
  spiegazione e i comandi nella pagina.
- **Una voce del menu** («Ambulatori → Esportazioni in Excel») porta ancora alla pagina «non disponibile» a chi non ha
  le Statistiche. Il menu lo sta rifacendo un altro lavoro (la tappa 2); dentro le pagine degli Ambulatori le voci
  sono già tolte.
- **Una sessione vale solo dal PC da cui si è entrati.** Dopo 4 ore senza usarlo, o comunque dopo 12, si rientra.
- **Provato solo su Linux e nel Windows finto.** Su un Windows vero vanno guardate la domanda del firewall e
  l'indirizzo con il nome del PC.

## 6. Cosa ho verificato io, in questo giro

Ho lavorato solo nella copia di lavoro del ramo `accessi` e in cartelle mie, sulle porte 5421-5435, con dati
inventati. Alla fine ho spento tutto e cancellato le mie cartelle (anche quelle nel Windows finto). I registri e i
miei programmi di controllo sono in `scratchpad/accessi-finale/verifica-2/`.

**Il guasto grave, rifatto da capo:**

- ho costruito l'eseguibile del ramo nel Windows finto, in una cartella mia, con i dati in una cartella mia;
- passi della revisione: Oggi, Pazienti, Cassa e Impostazioni; poi la pagina «Aree e accessi»; poi la richiesta della
  dashboard dal portiere con la rete spenta; poi rete accesa, richiesta da un altro indirizzo (192.0.2.2) e una con
  l'intestazione del portiere; poi accesso, password nuova, giro dall'altro PC. Dopo ognuno, dal PC: **sempre 200
  (tutto a posto), 23 controlli su 23**;
- il gemello: ho costruito anche l'eseguibile di **prima** della correzione. Con quello, dopo «Aree e accessi» e dopo
  il portiere, le quattro pagine danno **500 (errore)**. Quindi la prova vede davvero il guasto, e la correzione lo
  toglie;
- lo stesso con `python app.py`, nelle due versioni: 23 su 23 (e il gemello di prima: errore);
- le prove sul programma installato sull'eseguibile nuovo: 71 su 72. L'unica che non va chiede nove bottoni nella
  pagina delle esportazioni, ma il mio database nuovo non ha una sala operatoria e la pagina giustamente ne mostra
  sei: non è un difetto;
- la cartella dei dati comune del Windows finto non l'ho toccata (l'ho controllata prima e dopo).

**Gli altri 13 difetti, con i passi della revisione:** tutti corretti. Fra quelli che ho rifatto: scheda del paziente
senza Segreteria; ricerca dei pazienti da «Dove si fa»; prezzo di listino con le sole Anagrafiche (salva, ma il prezzo
resta 80,00); bottoni spenti in «solo guardare» (anche nel browser); appunti nella griglia; voci di «Scarica» degli
Ambulatori; checklist della Sala (anche nel browser); copia rimessa (Bruno spento oggi resta spento e non entra con la
password di ieri; la rete resta spenta); spegnere fa uscire; la porta occupata non lascia più il riquadro rosso;
utente rifiutato con il modulo ancora pieno; firewall; la pagina del rifiuto con il percorso giusto.

**Un attacco nuovo, mio:** ho rovinato apposta il file degli accessi accanto al database e poi ho fatto rimettere
una copia al programma all'avvio (database rovinato). Il programma regge: la rete resta spenta, le pagine del PC
rispondono, il file torna buono. **Ma nessuna prova del progetto controllava questo caso**: ho cambiato apposta il
programma, in una copia, perché sbagliasse (la copia di ieri vinceva e riaccendeva la rete) e tutte le prove restavano
verdi. Ho aggiunto la prova che mancava (quattro modi di rovinare il file, più il caso del file buono), nelle due
versioni; sui due programmi sbagliati apposta la prova cade, su quello vero passa.

**Tutte le prove:** vedi il punto 8.

## 7. I difetti della seconda revisione, in breve

| Difetto | Stato |
|---|---|
| Eseguibile: dopo «Aree e accessi», o una richiesta dalla rete o dal portiere, tutto in errore | corretto |
| Copia rimessa: tornavano utenti, password e rete di ieri, senza dirlo | corretto (regola al punto 4) |
| Firewall: dopo «Annulla» il comando della pagina non bastava | corretto in parte (bottone rimandato) |
| Cose da fare e lista d'attesa nella scheda di chi ha solo Pazienti | corretto |
| Anagrafica intera dalla ricerca a chi ha solo «Dove si fa» | corretto |
| Prezzo di listino e tariffario con le sole Anagrafiche | corretto |
| Checklist della Sala spuntabile in «solo guardare», con un messaggio falso | corretto |
| Voci di «Scarica» degli Ambulatori che portavano al rifiuto | corretto nelle pagine (resta la voce del menu) |
| Bottoni per salvare in «solo guardare» | corretto in tutte le pagine |
| Appunti della Segreteria nella griglia di chi ha solo Agenda | corretto |
| Spegnere l'accesso non faceva uscire chi era dentro | corretto |
| Riquadro rosso della porta occupata che restava per sempre | corretto |
| Utente rifiutato: pagina in cima e modulo vuoto; password nascosta | corretto |
| Rifiuto con un percorso sbagliato, pagina lunga e da tecnico | corretto |

## 8. Prove e commit

- **Prove senza browser** (sul ramo prima della mia aggiunta): normale 36 raccolte su 36, animata 36 su 36. Fra
  queste `prove_accessi.py` (53 su 53), `prove_autoriparazione.py`, `prove_canarino.py`, `prove_pagine.py`, la campagna.
- **`prove_accessi.py` con la prova nuova**: normale 54 su 54, animata 54 su 54.
- **Prove nel browser**, sul gestionale di prova appena avviato: normale 14 raccolte su 14, animata 16 su 16
  (con le due delle animazioni). Fra queste `prove_accessi_browser.py`, 37 su 37 in tutte e due.
- **Confronto con il programma di oggi** (`confronta_rami.py`), le pagine del PC della segreteria: normale 610 pagine,
  **0 diverse**, e 20 fogli da stampare in PDF, 0 diversi; animata lo stesso. L'unica differenza è quella già approvata:
  la guida da stampare ha 2 pagine in più, per la guida nuova.
- **Le due versioni uguali**: `allinea_animata.py` dice «254 file comuni, tutti uguali».

Commit del ramo `accessi`:

- 025e22e il nucleo; 605b63f la rete e la pagina; 7e94a8a le correzioni della prima revisione;
- e5e3d31 i 14 difetti della seconda revisione e Statistiche e report; 4c1797a la regola del confronto per la guida
  rifatta;
- 9eb7800 (mio) la prova del file degli accessi rovinato, nelle due versioni, e la nota nel piano.

**Da sapere, del lavoro di prima:** chi ha corretto i difetti, provando l'eseguibile nel Windows finto, per circa 20
secondi ha usato la cartella dati del programma installato **nel Windows finto** (non in clinica: lì non è cambiato
niente). Ha tolto i due file che aveva creato; restano piccole tracce innocue in quei dati di prova.

## 9. Cosa arriva dopo

- **La settima linguetta di Configura**, quando il menu della tappa 2 si unisce a questo lavoro (e con lei la voce del
  menu delle esportazioni).
- **Accendere e spegnere le parti per tutta la clinica** (moduli M1 e M2 del piano).
- **Il bottone del firewall** con il permesso di Windows, da provare su un Windows vero.
- **La protezione https con Caddy.**

Niente si pubblica e niente arriva al programma della clinica senza il tuo via.
