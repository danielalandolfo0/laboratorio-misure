# Laboratorio delle misure

Applicazione didattica per calcolare, confrontare e visualizzare distanze e dissimilarità.

## Funzionalità disponibili

- caricamento locale di tabelle CSV con intestazione;
- riconoscimento di feature numeriche, binarie e non numeriche;
- preprocessing Python eseguito localmente nel browser tramite Pyodide;
- motore decisionale che distingue quantità numeriche indipendenti, dati misti e percorsi specializzati;
- diagnosi automatica di outlier, rapporto tra dispersioni, sparsità, correlazioni, numerosità completa e condizionamento della covarianza;
- riscalamento automatico dei percorsi quantitativi tramite z-score, scala robusta o max-abs; le colonne costanti ricevono contributo nullo;
- uso diretto dei valori originali nei percorsi misti di Gower, senza riscalamento preliminare; contributi pesabili e configurazione semantica di ciascuna variabile;
- conservazione dei mancanti, segnalazione delle feature costanti e anteprima originale/trasformata;
- gestione operativa dei mancanti nei percorsi numerici, separata per colonna: esclusione delle righe, imputazione con mediana o media, oppure zero esplicitamente confermato;
- anteprima ed esportazione della tabella trasformata, con uso esplicito nel percorso che la richiede;
- piano di confronto che dichiara, per ogni percorso, origine dei dati, trasformazioni, politica sui mancanti e disponibilità del calcolo;
- calcolo dei percorsi specializzati per profili, serie temporali, composizioni e testo, con aggregazione finale pesata quando sono presenti più percorsi;
- proposta automatica di Euclidea, Manhattan o Mahalanobis per le quantità, modificabile dall’utente senza domande tecniche obbligatorie;
- scelta consigliata disponibile quando l’utente non conosce la risposta, senza bloccare il piano;
- registro decisionale verificato per Manhattan, Euclidea, Chebyshev, Minkowski, Minkowski pesata, euclidea standardizzata, Mahalanobis, Canberra, Bray–Curtis e χ² simmetrica;
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
├── examples/collaudo/      CSV controllati per i rami decisionali principali
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

I sei file in `examples/collaudo/` verificano rispettivamente il percorso
euclideo ordinario, la combinazione scala robusta–Manhattan, Mahalanobis,
il ripiego euclideo per covarianza singolare, max-abs per dati sparsi e Gower
per dati misti. Gli stessi casi sono inclusi nei test automatici.

## Come contribuire

1. Modifica i file direttamente su GitHub oppure sul tuo computer.
2. Prova l'applicazione aprendo `index.html`.
3. Per modifiche alle formule, aggiorna anche `test/test-misure.js`.
4. Descrivi chiaramente nel messaggio di commit cosa hai cambiato.

La tabella trasformata compare soltanto dopo la conferma di un piano interamente
numerico. Nei percorsi misti rimane visibile soltanto la tabella originale:
Gower applica internamente il proprio riscalamento ai valori originali.

Nei percorsi numerici, centro e scala sono stimati sui valori osservati. Le
eventuali sostituzioni dei mancanti vengono poi sottoposte alla trasformazione
dichiarata nel piano; se si escludono righe, anche le etichette e la matrice
finale contengono soltanto le righe effettivamente utilizzate. Mahalanobis con
imputazione non viene abilitata automaticamente, perché richiede una nuova
verifica della covarianza dopo il completamento dei dati.

## Matrice complessiva con più percorsi

Ogni percorso produce prima la propria matrice. Gower, i confronti 0/1 e le
dissimilarità già limitate conservano la loro scala teorica; le distanze non
limitate vengono divise per il 95º percentile delle distanze positive del
percorso e troncate a 1. In questo modo un percorso non prevale soltanto perché
la sua misura usa valori numericamente più grandi.

La matrice complessiva usa, per ogni coppia di righe, la media pesata dei soli
contributi disponibili:

\[
D(i,j)=\frac{\sum_b w_b\,\delta_{ij}^{(b)}\,\widetilde D^{(b)}(i,j)}
{\sum_b w_b\,\delta_{ij}^{(b)}}.
\]

I pesi dei percorsi sono strettamente positivi e valgono 1 per impostazione
predefinita. Se un percorso non può confrontare una coppia, non partecipa né al
numeratore né al denominatore di quella coppia. Se nessun percorso è
disponibile, la dissimilarità resta non definita.


## Convenzioni esplicite di Gower per dati misti

La Gower classica usa per le quantitative la differenza assoluta divisa per
l'intervallo osservato; per le nominali il disaccordo 0/1; per le ordinali
i ranghi normalizzati. I pesi delle caratteristiche sono strettamente positivi
(valore predefinito 1) e partecipano sia al numeratore sia al denominatore.
I dati numerici vengono letti dai valori originali, non dall'anteprima riscalata.

- Le colonne che non variano fra i valori interpretati non entrano nel
  denominatore; il piano le elenca. Se tutte le colonne sono prive di
  variabilità, il confronto viene segnalato come non disponibile.
- Un valore **sconosciuto** o **non applicabile** viene omesso nel confronto
  a coppie. Se un mancante indica **assenza**, l'utente lo conferma per
  colonne binarie o nominali; per quantità numeriche lo zero deve essere
  scelto esplicitamente per colonna.
- Nei binari asimmetrici le assenze condivise non entrano nel denominatore.
  Il sistema riconosce convenzioni come 0/1 e sì/no; per codici senza un
  significato evidente chiede quale stato rappresenti la presenza. La
  scelta può differire fra le colonne binarie.
- I livelli ordinali testuali richiedono l'ordine esplicito delle etichette,
  con livelli separati da punto e virgola. I livelli numerici, dopo conferma
  del significato ordinale, vengono ordinati numericamente.
- Se nessun contributo è disponibile per una coppia, la dissimilarità è
  **non definita** e viene indicata come cella vuota nel CSV; sulla diagonale
  compare 0 per convenzione. Con valori mancanti e assenze asimmetriche
  non si garantiscono le proprietà di una metrica.

Queste regole valgono nel percorso Gower; non trasformano automaticamente i
percorsi specializzati in un'unica matrice globale.
