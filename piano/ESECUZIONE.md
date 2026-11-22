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
solo per l'ascolto della rete (13 MB, 20 collegamenti, 30 s). Restano da fare: 1 (i portieri puntati alla porta della
rete, nella guida), 2 nel server principale, 3 (email e WhatsApp nel Sistema, password salvata cancellata), la pagina
come settima linguetta di Configura (dopo la tappa 2), la guida e il LEGGIMI, le prove nel browser della pagina.
Scelte del nucleo: Modo schermo libero solo con ?schermo=1 (le pagine con il menu vogliono l'accesso); «Oggi» senza i
riquadri delle aree che l'utente non ha; menu (_menu.html) non toccato: le voci delle aree negate portano al 403.
Domande lasciate a Giovanni (decido io il predefinito e lo scrivo): Importa da Excel → Configura «modificare» (no Sistema);
Riepilogo medici → Statistiche e report; Oggi: spariscono i riquadri senza area; utenti personali consigliati;
firewall: il programma propone la regola con il consenso di Windows (UAC) + comando netsh nella guida.
