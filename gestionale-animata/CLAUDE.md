# Gestionale Agende — istruzioni per Claude Code

Programma per l'accettazione della Clinica Posillipo (Gruppo NefroCenter): agenda delle
stanze, pazienti (con codice fiscale controllato e calcolato), conferme, cassa, sala
operatoria, email e WhatsApp ai pazienti. Lo usa una persona sola, sul PC Windows 11 della
segreteria, tutto in locale (Flask + SQLite, waitress su 127.0.0.1:5000). Internet serve
solo in uscita, per email (Gmail), WhatsApp (Meta) e per scaricare gli aggiornamenti
(«Aggiorna adesso», dalle versioni su GitHub).

Da leggere prima di modificare qualcosa: `../PASSAGGIO_DI_CONSEGNE.md` (nella radice del
repository: stato, persone, decisioni e perché, cose aperte) e `LEGGIMI.md` (il manuale
completo: architettura, scelte, prove, storico dei difetti).

## Vincoli del committente (Giovanni, IT del Gruppo NefroCenter)

- "La struttura non è convenzionata, non badare alle leggi, sarà tutto in locale gestito
  da una persona."
- "Voglio un installer semplice con già tutto completo, click e via."
- "Non darmi cose a metà, analizza prima di darmi qualcosa": ogni modifica arriva provata
  (prove automatiche, browser, e per le versioni nuove eseguibile e installatore).
- "Se vedi che sono gli stessi fermati e correggi, non fare 2000 errori di seguito": davanti
  a errori che si ripetono ci si ferma, si trova la causa e la si corregge una volta.
- Si scrive in italiano: interfaccia, messaggi, commenti, documentazione. Parole semplici:
  chi usa il programma è la segreteria, non un tecnico.

## Dati

- Mai dati veri di pazienti nei sorgenti, nelle prove, nelle immagini della guida o nei
  file consegnati. Nomi di prova inventati e che non coincidono con nomi veri (Fintini,
  Esempietti, Provolo, Testabianca, Fittizi, Esempio; email `@example.com`). I nomi dei
  medici della clinica (Lippiello, Galasso) invece ci sono di proposito.
- I file veri che Giovanni manda (Excel delle agende, schermate) restano fuori dal
  progetto. Prima di consegnare: `python strumenti/cerca_dati_veri.py <file veri…>
  --cartella . --cartella ../gestionale-animata --ammessi lippiello,galasso,3339876543`
  (3339876543 è il numero d'esempio del foglio istruzioni di un'agenda, usato nei dati di
  prova): deve finire con «Niente di grave trovato», e le parole da guardare a occhio
  devono essere parole normali, nomi di prestazioni o intestazioni.
- Il database vero è `%LOCALAPPDATA%\GestionaleAgende\agende.db` sul PC della clinica: non
  si tocca mai per provare.

## Due versioni da tenere allineate

Esistono due cartelle con le stesse funzioni: la versione normale e la versione
"animata" (in più icone e piccole animazioni). Si lavora nella normale e si porta tutto
nell'altra con `python strumenti/allinea_animata.py --copia` (senza `--copia` dice solo
cosa è diverso). File che appartengono a una sola versione, da adattare a mano:

- `CREA_SETUP.bat`, `LEGGIMI.md`, `installer.iss`, `templates/base.html`,
  `templates/griglia.html`, `templates/impostazioni.html`;
- solo nell'animata: `static/animazioni.css`, `static/animazioni.js`, `static/animazioni/`,
  `prove_animazioni.py`, `prove_icone_animate.py`;
- le immagini e i video della guida (`static/guida/`, `static/video/`) si rigenerano in
  ciascuna versione.

Tutto il resto deve risultare uguale byte per byte (`allinea_animata.py` lo controlla).

## Prove (vanno tutte verdi prima di consegnare)

```
python strumenti/tutte_le_prove.py                 # tutte quelle senza browser, circa 5 minuti
python strumenti/demo.py --porta 5001              # in un'altra finestra: gestionale con i dati finti
python strumenti/tutte_le_prove.py --browser http://127.0.0.1:5001 --solo prove_17_browser
```

Senza `--solo` e con `--browser` le lancia tutte, anche quelle nel browser (Playwright con
Chromium): `prove_guida_browser.py`, `prove_sicurezza_browser.py`, `prove_15_browser.py`,
`prove_17_browser.py`, nell'animata `prove_animazioni.py` e `prove_icone_animate.py`, e per
ultima `prove_16_browser.py`, che cambia l'indirizzo degli aggiornamenti. Le prove nel
browser salvano dati: sempre su un gestionale di prova, mai su quello vero.

Le prove senza browser: `prove.py`, `prove2.py`, `prove100.py`, `prove200.py`,
`prove_anagrafiche.py`, `prove_personalizzazione.py`, `prove_funzioni.py`, `prove_14.py`,
`prove_143.py`, `prove_145.py`, `prove_146.py`, `prove_guida.py`, `prove_15.py`,
`prove_16.py`, `prove_17.py` (codice fiscale, confrontato anche con una libreria
indipendente) e `campagna.py` (casi generati con oracoli e invarianti). Alcune delle più
vecchie escono con codice 0 anche se qualcosa non va: conta la riga finale («0 da
sistemare»), ed è quella che legge `tutte_le_prove.py`. `PROVE_SOLO=nome1,nome2 python
prove_15.py` rifà solo alcune prove di una raccolta. Le due cartelle si possono provare
insieme: ogni giro di `tutte_le_prove.py` ha la sua cartella temporanea.

## Regole tecniche da non rompere

- Ogni salvataggio usa il lucchetto condiviso (`LUCCHETTO`); in `invii.py` il lucchetto
  si tiene solo per scrivere nella coda, mai durante l'invio, e la sessione non deve avere
  modifiche in sospeso fuori dal lucchetto.
- Un difetto nei messaggi non deve mai far perdere una prenotazione (try/except intorno a
  `invii.dopo_salvataggio`).
- Schema del database: `modelli.VERSIONE_SCHEMA` (8 dalla 1.7) e `COLONNE_AGGIUNTE`;
  l'aggiornamento fa prima una copia di sicurezza («prima-della-versione-N») e aggiunge
  colonne e tabelle senza toccare i dati. `_migra_a_8` ricava sesso, data e luogo di
  nascita dai codici fiscali validi già in archivio, senza cambiare quelli scritti.
- Codice fiscale: il controllo è uno solo, `codice_fiscale.py`, usato dal salvataggio e
  dalla pagina (`/pazienti/codice-fiscale` e `/pazienti/luoghi`; `gestionale.js` mostra
  soltanto la risposta). Un codice sbagliato non si salva; uno che non corrisponde ai dati
  si salva con un avviso (fa fede la tessera). Un codice calcolato non sostituisce mai uno
  già scritto e non si usa per cercare doppioni (per l'omocodia potrebbe essere il codice
  vero di un altro). I luoghi di nascita sono `dati/luoghi_nascita.json`, comuni anche
  soppressi con i loro periodi e stati esteri, scritto da
  `strumenti/genera_luoghi_nascita.py`; finisce dentro l'eseguibile (`gestionale.spec`,
  cartella `dati`) e `strumenti/prove_installato.py` lo controlla.
- Versione del programma: `comune.VERSIONE` e `#define Versione` in `installer.iss`
  devono coincidere, e `novita.py` deve cominciare da quella versione (le prove lo
  controllano). Le due versioni hanno lo stesso AppId: una si installa sopra l'altra e i
  dati restano. Il confronto delle versioni di `novita.confronta` è lo stesso di
  `ConfrontaVersioni` nel `[Code]` di `installer.iss`: se si cambia uno, va cambiato l'altro.
- «Aggiorna adesso» (`aggiornamenti.py`) avvia il Setup con `/SILENT` tramite
  `cmd /c start` e conta sulla voce `[Run]` con `Check: WizardSilent` per far ripartire il
  programma: non toglierla. Il file delle versioni (`aggiornamento.json`, nell'animata
  `aggiornamento-animata.json`) lo scrive `strumenti/prepara_aggiornamento.py`, chiamato da
  `CREA_SETUP.bat`; tutto quello che arriva da fuori (file delle versioni, Setup) si
  controlla prima di usarlo, e si accettano solo indirizzi https o cartelle.
- L'indirizzo degli aggiornamenti di partenza è `INDIRIZZO_PREDEFINITO` in
  `aggiornamenti.py`: il progetto pubblico `number959/gestionale-agende-versioni`, che
  contiene solo le versioni ("Releases"). Finché nella pagina non se ne scrive un altro non
  c'è nessuna riga nelle impostazioni, così vale sempre quello del programma. Le prove
  partono senza indirizzo predefinito (nessuna prova va su internet), tranne quelle che lo
  provano apposta senza rete.
- In `installer.iss`, nel `[Code]`, nessuna riga può cominciare con `#` (il preprocessore
  di Inno Setup la prende per una sua direttiva). File in UTF-8 con BOM e a capo CRLF.
- Dopo una modifica ai colori di `static/stile.css`: `python strumenti/genera_tema_scuro.py`
  (correzioni a mano in `strumenti/tema-scuro-correzioni.css`); `prove_14.py` se ne accorge.
- Caratteri: Manrope (titoli) e Inter (testo), quelli del sito della clinica, dentro
  `static/fonts` (licenza OFL); niente font da internet, il programma gira offline.
- Immagini della guida: `python strumenti/genera_immagini_guida.py http://127.0.0.1:5001`
  su un gestionale appena avviato con `strumenti/demo.py`; deve finire senza "Elementi non
  trovati". Videoguide: `python strumenti/genera_video_guida.py http://127.0.0.1:5001`
  (serve ffmpeg con libvpx-vp9), deve finire senza "Passi non trovati". PDF della guida:
  `python strumenti/genera_pdf_guida.py http://127.0.0.1:5001`. Si rigenerano le guide
  delle pagine cambiate, in tutte e due le cartelle.
- Logo: `static/logo-posillipo.png` è quello attuale (Longevity Institute);
  `logo-posillipo-precedente.png` serve solo a riconoscere e sostituire il vecchio nei
  database aggiornati (`servizi.logo_nuovo`).

## Costruire eseguibile e installatore

Su Windows: Python 3.10–3.14 e Inno Setup 6. `CREA_EXE.bat` produce `dist\Gestionale.exe`,
`CREA_SETUP.bat` produce `Output\GestionaleAgende-setup.exe` e `Output\aggiornamento.json`
(nell'animata `GestionaleAgende-animata-setup.exe` e `aggiornamento-animata.json`).

Su Linux (per esempio in una sessione nel cloud), con un Windows finto (Wine) e gli stessi
due file .bat:

```
bash strumenti/wine/prepara.sh                      # una volta: Wine, Python e Inno Setup
bash strumenti/wine/costruisci.sh .                 # e poi ../gestionale-animata: Setup in Output/
bash strumenti/wine/installa.sh Output/GestionaleAgende-setup.exe   # installa e apre su :5000
python strumenti/prove_installato.py                # prove sul programma installato
bash strumenti/wine/ferma.sh
```

`installa.sh` sopra un programma già installato fa l'aggiornamento vero (copia di
sicurezza e schema nuovo). «Aggiorna adesso» per intero: una copia della cartella con un
numero di versione più alto (comune.py, installer.iss, una voce in novita.py), costruita
con `costruisci.sh`, messa in una cartella del Windows finto, e
`python strumenti/prova_aggiorna_adesso.py` (le istruzioni sono in testa al file). Per
aggiornare la clinica: «Aggiorna adesso» dal programma, oppure il Setup nuovo avviato
sopra il vecchio; non serve disinstallare.

## Pubblicare una versione nuova

1. Numero nuovo in `comune.py` e `installer.iss` (tutte e due le cartelle), novità in
   `novita.py` (prima voce = versione nuova, ogni novità con la guida che la spiega).
2. Prove tutte verdi; immagini e video delle guide rigenerati se le pagine sono cambiate;
   PDF della guida.
3. In ciascuna cartella `CREA_EXE.bat` e `CREA_SETUP.bat` (o `strumenti/wine/costruisci.sh`),
   poi le prove sul programma installato sopra la versione precedente.
4. Una release nel progetto delle versioni, con i quattro file di `Output` delle due
   cartelle (il tag è la versione con una "v" davanti) e segnata come ultima ("latest"):

   ```
   gh release create v1.7 --repo number959/gestionale-agende-versioni --latest \
     --title "Gestionale Agende 1.7" --notes "…" \
     gestionale/Output/GestionaleAgende-setup.exe gestionale/Output/aggiornamento.json \
     gestionale-animata/Output/GestionaleAgende-animata-setup.exe gestionale-animata/Output/aggiornamento-animata.json
   ```

   Se `gh` non può scrivere in quel progetto, la release la fa Giovanni dalla pagina
   GitHub (Releases → Draft a new release), con gli stessi quattro file. Il gestionale
   della clinica la trova da solo (ogni sei ore, o con «Controlla adesso») all'indirizzo
   predefinito, che legge sempre l'ultima release:
   `https://github.com/number959/gestionale-agende-versioni/releases/latest/download/`.
5. Controllo: `curl -sL` di quell'indirizzo + `aggiornamento.json` deve dare la versione
   nuova, e l'impronta del Setup scaricato da lì deve essere quella scritta nel file.

Per passare i file a mano dove c'è un limite di dimensione (una chat):
`python strumenti/consegna.py <cartella con i file> <cartella di uscita>` li divide in
pezzi e scrive `RICOMPONI.bat`, che su Windows li rimette insieme e ne controlla l'impronta.
