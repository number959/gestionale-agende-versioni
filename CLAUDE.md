# Gestionale Agende — il repository

Due cartelle con lo stesso programma: `gestionale/`, la versione normale, e
`gestionale-animata/`, con icone e piccole animazioni in più. Si lavora nella normale; i
file comuni si portano nell'altra con `python strumenti/allinea_animata.py --copia`
(lanciato dentro `gestionale/`). I pochi file propri di ogni versione si adattano a mano.

Da leggere prima di toccare qualcosa:

1. `PASSAGGIO_DI_CONSEGNE.md`: stato, persone, decisioni e perché, come si costruisce, si
   prova e si pubblica, cose aperte;
2. `gestionale/CLAUDE.md`: le regole del progetto;
3. `gestionale/LEGGIMI.md`: il manuale completo, con le prove e lo storico dei difetti.

Sempre:

- Italiano in interfaccia, messaggi, commenti e documentazione, con parole semplici: chi usa
  il programma è la segreteria.
- Mai dati veri di pazienti nel repository, nelle prove, nelle immagini o nei video. Solo
  nomi inventati.
- Ogni modifica si prova in tutte e due le cartelle: `python strumenti/tutte_le_prove.py`
  dentro ciascuna (con `--browser http://127.0.0.1:5001` e `python strumenti/demo.py
  --porta 5001` anche le prove nel browser). Per una versione nuova si provano anche
  l'eseguibile e il Setup (su Windows con `CREA_EXE.bat` e `CREA_SETUP.bat`, su Linux con
  `strumenti/wine/`).
- Prima di consegnare, se ci sono file veri della clinica: `strumenti/cerca_dati_veri.py`
  (vedi `PASSAGGIO_DI_CONSEGNE.md`).
- Le versioni si pubblicano nel progetto pubblico `number959/gestionale-agende-versioni`,
  da cui il programma della clinica le scarica da solo.
