# Esecuzione del piano completo (dal 22/11/2026, richiesta di Giovanni)

Richiesta (22/11, dopo la mezzanotte): «Completa tutto il software, attieniti al piano, dammi la possibilità di
scegliere quale modulo rendere disponibile sugli altri PC della rete in locale a quale utente e quale no».

Piano di riferimento: scratchpad/piano2/ (s0-s7) = piano_v3; tappe in piano_v3/tappe.json; dettagli in piano2/s4.md.
Tavole (anteprime): scratchpad/tela/project/*.dc.html (+ canvas.json), scratchpad/anteprime/SPEC-*.md.

## Decisioni prese (scritte nel resoconto finale per Giovanni)
- Si va avanti tappa dopo tappa senza aspettare il suo sguardo a ogni tappa (lui: «completa tutto»); per ogni
  tappa resoconto + foto salvati, da guardare alla fine.
- MAI: pubblicare, unire al principale, segnare «ultima», Setup fuori da Wine, toccare la clinica.
- Ramo: tutto su ccr-interfaccia (base e moduli). ccr-moduli resta fermo (push non autorizzato).
- I quattro cambiamenti di funzionamento (M3 mappa e logo del gruppo, M6 dashboard, M7 due agende, M8 finestra)
  si fanno: nel piano erano «sì» e lui ora dice «completa tutto».
- axe-core: no (il piano dice «se Giovanni dice sì»): prova nostra più piccola.
- Le 8 pagine che si stampano: confrontate in PDF anche loro dalla tappa 2 (più sicuro).
- Mese dei turni a 1366: celle strette per stare nei ~1046 px.
- Pagina dei moduli: nome «Aree e accessi» (Configura), con due parti: aree accese/spente e accesso dagli altri PC.
- Statistiche diventa «Statistiche e report» (M5): esportazioni lì, Excel e PDF con grafici (richiesta del 21/11).
- Accesso dagli altri PC (M2-bis, richiesta del 22/11):
  * spento per difetto; quando acceso il programma ascolta ANCHE su 0.0.0.0:<porta rete> (5080 di partenza),
    il PC principale resta su 127.0.0.1:5000 senza accesso, come oggi;
  * utenti (nome, password con hash di werkzeug, attivo) e per ogni utente, area per area:
    non disponibile / solo guardare / guardare e modificare; tenuti fra le impostazioni (schema 12);
  * dalla rete: accesso obbligatorio; un'area non permessa → 403 con pagina italiana; «solo guardare» → solo GET;
    sempre e solo sul PC principale: aggiornamenti, copie e ripristino, autoriparazione, chiudi programma, la pagina
    degli accessi stessa; il Modo schermo (/riepilogo-live*?schermo) resta senza accesso se la clinica lo vuole;
  * richieste con X-Forwarded-For/Forwarded (portiere Caddy) contano come «dalla rete»;
  * chiave della sessione casuale per installazione (oggi è fissa 'gestionale-locale': con la rete sarebbe una
    porta aperta); controllo dell'origine anche per gli indirizzi della rete; tentativi di accesso limitati;
  * HTTP in chiaro sulla rete locale: detto chiaramente nella pagina (HTTPS con Caddy come passo dopo).

## Ordine
T1 (in chiusura: #55 gemelli, #56 tre modelli+main+rigide, #57 guida data-guida+ruoli, #59 pacchetto) →
1-bis mattoni → 2 menu e barra → 3 campanella/messaggi/domande → 4 Pazienti e Statistiche → 5 Oggi/Agenda/Sala →
6 Segreteria e Cassa → 7 Turni → 8 Ambulatori e Dove si fa → 9 Configura/Aiuto/aggiornamenti → 10 prova finale
(1.13, guida, immagini, video, Wine) → [11 pubblicazione: NO, serve il via] → M1 fondamenta → M2 aree + accessi
dalla rete → M3 Dove si fa + mappa → M4 Comunicazioni → M5 Statistiche e report → M6 Ambulatori e dashboard →
M7 Sala e due agende → M8 finestra → M9 Segreteria → M10 nucleo ripulito.

## Accessi dalla rete: progetto pronto (22/11, notte)
Bozza provata: scratchpad/accessi-rete/copia/gestionale/accessi.py + templates/accessi.html + prove_accessi.py (14 prove,
15 mutanti), censimento aree.tsv (152 endpoint), bozza.diff. Revisione di sicurezza (journal wf_528eed0d-c25, attacchi in
accessi-rete/revisione/attacchi/): DA FARE quando si applica (M2):
1. waitress clear_untrusted_proxy_headers=False in crea_server (altrimenti X-Forwarded-For sparisce e il portiere = PC);
   meglio: i portieri puntano alla porta della rete.
2. max_request_body_size 13 MB, connection_limit ~20, channel_timeout 30 s (anche nel server principale).
3. Configurazione casella email e token WhatsApp (sezioni email/whatsapp di /invii) = Sistema; e la password salvata si
   cancella se cambiano server/porta/sicurezza/utente.
4. Sessioni con id casuale tenute sul server (Esci vero, «Fai uscire», password cambiata → fuori); file accanto alla chiave.
5. Scritture fra aree: appuntamento() aggiorna la scheda paziente solo con puo_cambiare('pazienti'), importo/convenzione
   solo con 'cassa', lista d'attesa solo con 'segreteria'.
6. Letture fra aree: appuntamento.html tariffe/pagamento dentro puo('cassa'), messaggi dentro puo('comunicazioni'),
   candidati attesa dentro puo('segreteria'); notifiche con 'area' dichiarata; /sposta/avvisi solo id dell'utente.
7. Endpoint di servizio con più aree (pazienti.cerca_json, luoghi_json, codice_fiscale_json: pazienti|agenda|segreteria|
   dove) + prova: ogni area apre le sue pagine e tutti i JSON che chiamano rispondono 200.
8. Chiave casuale già all'import (secrets.token_bytes(32)); AscoltoRete rifiuta di accendersi con chiave corta/fissa.
9. Blocco tentativi per (indirizzo, nome); per nome soglia 20 con attesa crescente; «Sblocca» nella pagina.
10. Sempre «Nome o password non giusti.»; utente con id casuale; registro senza caratteri di controllo, con le GET di
    schede/documenti/allegati/Excel, file per giorno; porta salvata solo dopo accendi riuscito; applica(cfg) dopo
    ripristino/riparazione; all_avvio riprova per qualche minuto; Modo schermo senza password SPENTO di partenza…
    ma attenzione: oggi la dashboard dietro Caddy funziona senza password → lasciare acceso se rete spenta? Deciso:
    con rete spenta il comportamento di Caddy resta quello di oggi (schermo libero), la casella vale per la rete accesa.
11. Password: lista di vietate, frase lunga consigliata, cambio al primo accesso.
Nucleo applicato (22/11, ramo `accessi`, gestionale/accessi.py + prove_accessi.py): correzioni 4-11 tutte; della 1 il
`clear_untrusted_proxy_headers=False` in crea_server (senza, il portiere di Caddy sembrerebbe il PC); della 2 i limiti
solo per l'ascolto della rete (13 MB, 20 collegamenti, 30 s).
Presa della rete e pagina (22/11, ramo `accessi`, secondo commit): correzioni 1-3 e il resto della 10 applicati. 1: i
portieri puntati alla porta della rete detto nella pagina, nella guida e nel LEGGIMI (con l'accesso acceso gli schermi
non hanno più bisogno di Caddy); 2: gli stessi limiti anche sul server principale (`accessi.LIMITI_SERVER`); 3:
`SISTEMA_DENTRO` (casella email e WhatsApp di /invii: 403 dalla rete e nascoste nella pagina) e la password salvata
tolta se cambiano server, porta, sicurezza o utente (`invii.casella_cambiata`). La pagina: firewall (reti private sì,
pubbliche no, comando netsh), indirizzi, in chiaro, utente nuovo con le aree nello stesso modulo, registro degli ultimi
7 giorni dai file; pagina di accesso con il nome della struttura; rifiuto che dice a chi chiedere. Indirizzi in numeri
sempre buoni sulla porta della rete; nomi del PC rifatti ogni minuto. La guida «Far usare il programma dagli altri PC»
(altri-pc, con immagine e video fatti solo per lei: le altre si rifanno nella tappa 10). Nella prova la porta della rete
è la 5085, mai la 5080. Prove: prove_accessi.py (25, con il programma vero in un processo a parte e richieste
dall'indirizzo non di loopback), prove_accessi_browser.py (nel browser), prove_prova.py. Resta: la pagina come settima
linguetta di Configura (dopo la tappa 2) e la metà «aree accese/spente» (con M1).
Scelte del nucleo: Modo schermo libero solo con ?schermo=1 (le pagine con il menu vogliono l'accesso); «Oggi» senza i
riquadri delle aree che l'utente non ha; menu (_menu.html) non toccato: le voci delle aree negate portano al 403.
Domande lasciate a Giovanni (decido io il predefinito e lo scrivo): Importa da Excel → Configura «modificare» (no Sistema);
Riepilogo medici → Statistiche e report; Oggi: spariscono i riquadri senza area; utenti personali consigliati;
firewall: il programma propone la regola con il consenso di Windows (UAC) + comando netsh nella guida.
Revisione dei tre revisori (22/11, dopo la presa della rete; ramo `accessi`): ogni problema riprodotto prima di correggerlo,
ognuno con la sua prova `z_…` in prove_accessi.py, il gemello e un mutante (38 mutanti, tutti presi). Corretti: assenze e
chiusure senza l'Agenda (solo il numero), ricerca dei pazienti senza i Pazienti solo a chi prenota (anche il paziente di
Dove si fa), importi e convenzioni solo con la Cassa (stampa, Excel ed elenco del giorno, esportazione, chiusura), lista
d'attesa e appunti con `aggiorna=`, Conferme della Segreteria (stato e promemoria, `ANCHE_PER`), incasso con la sola Cassa,
tentativi (limite per PC 30, tetto, `bloccati()` in un passaggio, `prenota`, risposta senza database, registro raggruppato e
letto dal fondo), Excel troppo compressi (`controlla_excel_compresso`, Importa in sola lettura), 12 collegamenti per PC sulla
rete, cookie legato al PC, 5 sessioni per utente, password più severe. Domanda per Giovanni (predefinito: come oggi, ma la
pagina lo dice accanto alla parte): Statistiche e report contiene nomi, telefoni, importi e incassi; togliere i pazienti a
chi non ha Pazienti o Agenda, e gli importi a chi non ha la Cassa? prenota_appunti resta della Segreteria (è il suo giro).
Secondo giro della revisione (22/11, sera; ramo `accessi`): i 14 problemi che al primo giro erano arrivati tagliati, ognuno
riprodotto prima, con la sua prova (`y_come_l_eseguibile`, `a_nessun_modulo_importa_app`, `z_nv_…` in prove_accessi.py), il
gemello e un mutante su una copia. Il grave: nell'eseguibile (e con «python app.py») app.py gira come «__main__» e il
primo «from app import» di accessi.py caricava una seconda copia del programma con Sessione=None: tutto 500, anche sul
PC. Corretto alla causa (`accessi.installa(app, ses, LUCCHETTO, fabbrica)`, nessun modulo importa app) e con la rete di
sicurezza in app.py (`sys.modules['app']`); regola in gestionale/CLAUDE.md.
Decisioni di questo giro (predefiniti decisi, Giovanni può cambiarli):
- *Copia rimessa*: gli accessi dagli altri PC (utenti, password, parti, accensione, porta, schermo, altri nomi) NON tornano
  indietro con una copia di sicurezza, né con il ripristino dalle Impostazioni né con una riparazione (custode, Controllo
  del programma, avvio): sono impostazioni di sicurezza, come la chiave dei cookie. Il ripristino lo dice nel messaggio,
  la riparazione nel diario e nella campanella. Restano quelle di prima del ripristino, o (riparazioni) quelle del file
  accessi-rete.json accanto al database, fuori dalle copie; se il file non c'è, la rete resta spenta finché la segreteria
  non controlla. Così chi è stato spento o ha cambiato password oggi non rientra con la copia di ieri. Con una copia di
  prima della 1.13 gli utenti non spariscono più.
- *Firewall*: dopo «Annulla»/«No» (o se chi usa il PC non è amministratore) Windows crea regole di BLOCCO per il programma,
  che vincono sulle regole che permettono (documentazione Microsoft «Windows Firewall rules»). La pagina lo spiega; in «Per
  l'assistenza» i due comandi: togliere tutte le regole del programma (`delete rule name=all program="…"`, il percorso
  vero da sys.executable) e mettere quella per programma, TCP e porta, reti private e di dominio. La pagina dice l'ultima
  richiesta arrivata da un altro PC, o che non ne è arrivata nessuna. Rimandato: il bottone con il consenso di Windows
  (UAC, ShellExecute «runas») e la lettura del tipo di rete e delle regole di blocco (PowerShell): non si possono provare
  senza un Windows vero (in Wine netsh e PowerShell non fanno niente).
- *Spegnere l'accesso* dalla pagina fa uscire tutti; le sessioni restano solo nei riavvii (per esempio «Aggiorna adesso»).
- *Solo guardare*: i moduli che l'utente non può salvare hanno campi e bottoni spenti, con la spiegazione e una riga in cima
  alla pagina (per tutte le pagine, dal programma: accessi.segna_moduli + gestionale.js); la guardia resta.
- *Statistiche e report*: predefinito deciso, Giovanni può cambiarlo. Dagli altri PC i nomi, telefoni ed email dei pazienti
  (e le note, dove si scrivono nomi) solo a chi ha anche Pazienti o Agenda; importi e incassi solo a chi ha anche la Cassa;
  nelle pagine e negli Excel (statistiche, riepilogo dei medici con la sua email già scritta, esportazione del giorno), con
  le colonne tolte, non vuote. Sul PC principale tutto identico. Tolto dalla pagina l'avviso provvisorio: la descrizione
  della parte dice la regola.
- *Ricerca dei pazienti*: l'anagrafica intera solo a chi ha Pazienti o Agenda; a chi la usa da Dove si fa o dalla Segreteria
  bastano nome, nascita e telefono.
- *Menu*: la voce «Ambulatori → Esportazioni in Excel» del menu porta ancora al 403 a chi non ha Statistiche e report (il menu
  non si tocca finché la tappa 2 non lo rifà, come deciso nel nucleo); le voci dentro le pagine degli Ambulatori sono tolte.
