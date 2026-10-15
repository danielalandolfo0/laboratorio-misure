# Laboratorio delle misure

Applicazione didattica per calcolare, confrontare e visualizzare distanze e dissimilarità.

## Funzionalità disponibili

- famiglia di Minkowski: forma generale, Manhattan, Euclidea, Chebyshev, versione pesata ed Euclidea standardizzata;
- Mahalanobis, Canberra, Bray–Curtis e χ² simmetrica;
- similarità coseno e correlazione di Pearson per confrontare i profili;
- correlazioni di Spearman e Kendall τb per i confronti basati sui ranghi;
- distanze, dissimilarità e similarità pesata per vettori binari;
- Hamming, Levenshtein e Damerau–Levenshtein per stringhe e sequenze simboliche;
- selezione del tipo di dato e delle sole misure compatibili;
- contributi delle singole coordinate;
- rappresentazione geometrica per vettori numerici in due dimensioni;
- conteggi \(n_{11}, n_{10}, n_{01}, n_{00}\) per vettori binari;
- confronto simbolo per simbolo e matrici di programmazione dinamica per le stringhe;
- controlli sulla validità degli input numerici e binari.

## Struttura del progetto

```text
laboratorio-misure/
├── index.html              pagina dell'applicazione
├── css/stile.css           aspetto grafico
├── js/misure.js            formule e controlli matematici
├── js/interfaccia.js       comportamento dell'interfaccia
├── test/test-misure.js     test automatici
└── package.json            comando per eseguire i test
```

La separazione principale è tra `js/misure.js`, che contiene la matematica, e
`js/interfaccia.js`, che si occupa soltanto della pagina. In questo modo le
formule possono essere controllate senza dipendere dalla grafica.

## Aprire l'applicazione

Scarica il repository e apri `index.html` con un browser. Non sono richieste
installazioni per usare l'applicazione.

## Eseguire i test

Se sul computer è installato Node.js, dalla cartella del progetto esegui:

```bash
npm test
```

## Come contribuire

1. Modifica i file direttamente su GitHub oppure sul tuo computer.
2. Prova l'applicazione aprendo `index.html`.
3. Per modifiche alle formule, aggiorna anche `test/test-misure.js`.
4. Descrivi chiaramente nel messaggio di commit cosa hai cambiato.

Il prossimo modulo ordinerà le osservazioni di un dataset rispetto a un nuovo
dato, dalla più vicina alla più lontana.
