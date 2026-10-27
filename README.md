# Laboratorio delle misure

Applicazione didattica per calcolare, confrontare e visualizzare distanze e dissimilarità.

## Funzionalità disponibili

- caricamento locale di tabelle CSV con intestazione;
- riconoscimento di feature numeriche, binarie e non numeriche;
- preprocessing Python eseguito localmente nel browser tramite Pyodide;
- scelta globale del riscalamento tra nessuno, z-score, scala robusta e max-abs;
- conservazione dei mancanti, segnalazione delle feature costanti e anteprima originale/trasformata;
- esportazione della tabella di lavoro riscalata;
- famiglia di Minkowski: forma generale, Manhattan, Euclidea, Chebyshev, versione pesata ed Euclidea standardizzata;
- Mahalanobis, Canberra, Bray–Curtis e χ² simmetrica;
- similarità coseno e correlazione di Pearson per confrontare i profili;
- correlazioni di Spearman e Kendall τb per i confronti basati sui ranghi;
- distanze, dissimilarità e similarità pesata per vettori binari;
- Hamming, Levenshtein e Damerau–Levenshtein per stringhe e sequenze simboliche;
- selezione del tipo di dato e delle sole misure compatibili;
- contributi delle singole coordinate;
- rappresentazione geometrica per vettori numerici in due dimensioni, inclusi i vettori direzionali e i profili centrati;
- confronto visuale degli ordinamenti, dei ranghi e dei conteggi di Kendall;
- conteggi \(n_{11}, n_{10}, n_{01}, n_{00}\) per vettori binari;
- confronto simbolo per simbolo e matrici di programmazione dinamica per le stringhe;
- controlli sulla validità degli input numerici e binari.

## Struttura del progetto

```text
laboratorio-misure/
├── index.html              pagina dell'applicazione
├── css/stile.css           aspetto grafico
├── python/preprocessing.py logica Python per CSV, diagnosi e riscalamento
├── js/preprocessing-python.js collegamento tra pagina e Python
├── js/preprocessing-ui.js  interfaccia della preparazione dei dati
├── js/misure.js            formule e controlli matematici
├── js/interfaccia.js       comportamento dell'interfaccia
├── test/test-misure.js     test automatici
├── test/test_preprocessing.py test del modulo Python per i CSV
└── package.json            comando per eseguire i test
```

La separazione principale è tra `js/misure.js`, che contiene la matematica, e
`js/interfaccia.js`, che si occupa soltanto della pagina. In questo modo le
formule possono essere controllate senza dipendere dalla grafica.

## Aprire l'applicazione

La versione pubblicata non richiede installazioni. Per eseguire una copia
locale, avvia un piccolo server HTTP dalla cartella del progetto, per esempio:

```bash
python3 -m http.server 8000
```

e apri `http://localhost:8000`. Al primo caricamento il browser scarica
l'ambiente Python di Pyodide; i CSV restano nel dispositivo dell'utente.

## Eseguire i test

Se sul computer sono installati Node.js e Python, dalla cartella del progetto
esegui:

```bash
npm test
```

## Come contribuire

1. Modifica i file direttamente su GitHub oppure sul tuo computer.
2. Prova l'applicazione aprendo `index.html`.
3. Per modifiche alle formule, aggiorna anche `test/test-misure.js`.
4. Descrivi chiaramente nel messaggio di commit cosa hai cambiato.

La tabella riscalata costituisce la base per i successivi moduli di scelta e
calcolo delle distanze tra le istanze.

