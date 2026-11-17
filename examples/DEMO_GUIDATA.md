# Dimostrazione guidata del laboratorio

Questa traccia mostra il funzionamento del sito attraverso decisioni
interpretabili e termina sempre con una sola matrice finale.

## Prima della dimostrazione

```bash
npm test
python3 examples/demo_flussi.py
```

Il primo comando verifica il motore; il secondo stampa una sintesi leggibile
dei principali percorsi. Nell'interfaccia si possono poi usare gli stessi CSV.

## 1. Quantità ordinarie

File: `collaudo/01_numerici_ordinari.csv`.

1. Confermare che ogni riga rappresenta un oggetto e che `a`, `b` sono quantità.
2. Osservare la diagnosi congiunta e confermare il preprocessing proposto.
3. Mantenere entrambe le colonne indipendenti.
4. Indicare che interessano gli scarti quantitativi e approvare l'euclidea.

Da mostrare: la misura è una proposta motivata e confermata; la matrice finale
è normalizzata in `[0,1]`, simmetrica e con diagonale nulla.

## 2. Dipendenza lineare esatta

File: `collaudo/04_numerici_covarianza_singolare.csv`.

Le colonne soddisfano `b=2a`. Il sito deve segnalarlo prima del calcolo.
Provare Mahalanobis classica per mostrare che viene bloccata perché la
covarianza è singolare. Le decisioni disponibili sono modificare le colonne,
usare una regolarizzazione o pseudoinversa esplicita, oppure mantenere le
coordinate e scegliere una misura compatibile, accettando la ridondanza.

Da mostrare: nessun ripiego modifica tacitamente la richiesta dell'utente.

## 3. Dati misti con Gower

File: `collaudo/06_dati_misti.csv`.

1. Confermare `eta` e `reddito` come quantità, `presente` come variabile
   binaria o di presenza e `gruppo` come categoria nominale.
2. Scegliere di trattare insieme tutte le caratteristiche con Gower.
3. Per la variabile di presenza dichiarare se le assenze condivise contano.
4. Conservare pesi unitari o modificarli per mostrare il loro effetto.

Da mostrare: Gower usa i valori originali e costruisce contributi locali già
confrontabili; il preprocessing numerico preliminare non viene applicato di
nascosto al percorso misto.

## 4. Quattro percorsi simultanei

File: `collaudo/test_integrato_gower_gruppi_mancanti.csv`.

| Percorso | Colonne | Misura |
|---|---|---|
| Categorie | `livello`, `categoria` | Gower con contributi personalizzati |
| Codice | `codice` | Hamming normalizzata |
| Coordinate | `c1`, `c2` | Minkowski pesata con mancanti pairwise |
| Istogramma | `p1`, `p2`, `p3` | Hellinger |

Il collaudo assegna pesi globali `2, 1, 3, 4`, usa una scala robusta per
le coordinate ed esclude le righe 4 e 5 soltanto dalla stima di tale scala.
Le righe restano nella matrice. Se per una coppia le coordinate non sono
disponibili, gli altri contributi vengono mediati sui soli pesi disponibili.

```bash
python3 test/test_integrazione.py
```

Il test confronta il risultato con formule indipendenti, non soltanto con la
forma attesa della matrice.

## Materiale da consegnare

- matrice finale in CSV;
- rapporto completo JSON;
- eventuale CSV delle coppie non confrontabili.

Il rapporto documenta sorgente, interpretazioni, trasformazioni, misure,
parametri, normalizzazioni, pesi e diagnostica finale.
