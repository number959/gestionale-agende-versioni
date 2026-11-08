# Prototipo del cruscotto su internet (novembre 2026)

Due pagine HTML, non parte del programma installato: il prototipo animato del cruscotto
(`cruscotto.html`: quattro stili, riepilogo live, dati di esempio generati sul momento, nessun
paziente) e il documento delle proposte (`proposte.html`: cosa si vede, motion design,
riservatezza, tre strade a confronto, piano per la 1.13). Sono scritte per essere pubblicate come
pagine singole: dentro un `<html>` con `<head>` e `<body>` si aprono in qualsiasi browser. I
caratteri Manrope e Inter li prendono da Google Fonts; senza internet usano quelli del sistema.

Il programma espone già i numeri con cui il cruscotto vero si alimenterà: `/riepilogo-live.json`
(`live.py`), solo conteggi e orari. Le scelte e le decisioni aperte sono nel
`PASSAGGIO_DI_CONSEGNE.md`, sezione «La 1.12».
