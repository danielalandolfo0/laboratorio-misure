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
- gestione esplicita dei mancanti nei percorsi specializzati: esclusione dal solo percorso, interpolazione interna delle serie, imputazione dei profili o testo vuoto confermato;
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

## Gruppi numerici con misure differenti

Una tabella anche interamente numerica puo' essere organizzata in blocchi
**disgiunti**: ogni colonna appartiene a un solo percorso di confronto.
Nella sezione dei gruppi, scegli il significato delle colonne:

- **Osservazioni successive nel tempo**: scelta guidata tra confronto
  punto per punto e DTW (costo medio minimo sul cammino);
- **Misurazioni dello stesso profilo**: scelta tra forma, direzione,
  ordinamento e differenze tra coordinate;
- **Coordinate quantitative da confrontare insieme**: per quel solo gruppo
  scegli euclidea, Manhattan, Chebyshev, Minkowski o Minkowski pesata,
  con esponente q >= 1 e pesi interni strettamente positivi.

Le colonne quantitative non assegnate a gruppi mantengono il proprio percorso
numerico e la propria scelta di misura. Le impostazioni del gruppo di coordinate
non si trasferiscono agli altri blocchi. Il riscalamento numerico confermato
e' utilizzato per i gruppi di coordinate (non per la forma Pearson e l'allineamento
temporale DTW, che mantengono i valori originali).

Il file \`examples/collaudo/test_blocchi_eterogenei.csv\` offre cinque osservazioni
e otto colonne: le prime tre possono essere raggruppate come serie temporale,
le successive tre come profilo e le ultime due come coordinate quantitative.
La matrice finale combina tre dissimilarita' normalizzate nell'intervallo [0,1].

### Proposte guidate di raggruppamento

La diagnosi preliminare ora mostra **possibili gruppi di colonne quantitative**
ancora indipendenti. La proposta usa due indizi distinti:

- intestazioni con una radice comune e indici numerici differenti
  (ad esempio `t1, t2, t3`, senza assumere che `t` indichi il tempo);
- correlazioni elevate fra tutte le coppie del gruppo, con
  `|r di Pearson| >= 0,8` e almeno quattro osservazioni comuni per coppia.

La soglia e' soltanto esplorativa: una correlazione forte non dimostra che
le colonne siano coordinate dello stesso profilo o osservazioni temporali.
Nessuna proposta entra automaticamente nel piano. Per **creare** un gruppo
l'utente deve scegliere esplicitamente se le colonne sono coordinate quantitative,
un profilo, misurazioni temporali o parti di un totale. Le proposte sono
facoltative; gli assegnamenti possono essere modificati o rimossi manualmente.
Gli eventuali gruppi già confermati e le colonne escluse non vengono toccati.

### Mancanti quantitativi: confronto sulle coordinate comuni

Per le distanze di Minkowski, Manhattan ed euclidea, quando l'utente seleziona
**confronto pairwise**, per la coppia di righe \(i,j\) si considerano
soltanto gli indici \(O_{ij}\) osservati in entrambe. Ponendo
\(a_\ell>0\), e \(q\ge1\), il contributo locale (prima della
normalizzazione in \([0,1]\)) e':

\[
d(i,j)=\left(
\frac{\sum_{\ell\in O_{ij}}a_\ell
|z_{i\ell}-z_{j\ell}|^q}
{\sum_{\ell\in O_{ij}}a_\ell}
\right)^{1/q}.
\]

Le distanze non pesate impiegano \(a_\ell=1\); Chebyshev usa il massimo
scarto disponibile, nella variante pesata il massimo degli scarti
moltiplicati per i rispettivi pesi. Le coordinate mancanti sono
**omesse dalla coppia**, mai assimilate a zero. Se
\(O_{ij}=\varnothing\), il contributo del blocco e' non disponibile.
La normalizzazione e l'aggregazione Gower generalizzata sono eseguite
solo sulle distanze locali definite; la matrice finale deve comunque
essere completa. Una normalizzazione sul numero di coordinate
disponibili non garantisce in generale la disuguaglianza triangolare
quando i dati hanno pattern differenti di mancanti.

La modalita' e' selezionabile separatamente per colonna nei percorsi
quantitativi indipendenti e per intero blocco quando il significato
confermato e' quello di coordinate quantitative. Non e' estesa
automaticamente a Pearson, DTW, Mahalanobis o distanze relative:
il sito segnala la loro incompatibilita' e chiede una scelta.

### Compatibilita' dei riscalamenti con le misure locali

La conferma del preprocessing preliminare non implica che tutte le misure
debbano usarlo: il piano dichiara per ogni blocco l'origine effettiva.

- I confronti fra coordinate quantitative usano il riscalamento confermato
  quando il percorso lo prevede.
- DTW, Pearson, coseno, Spearman e Aitchison operano in questa versione sui
  valori originali. Se esistono trasformazioni preliminari confermate, il
  sito richiede una **seconda conferma specifica per quel gruppo** prima di
  calcolare la matrice: altrimenti il percorso rimane incompleto.
- Se in un blocco quantitativo con distanza sulle coordinate si applicano
  trasformazioni differenti, il sito chiede di confermare esplicitamente
  la combinazione. La distanza puo' essere ben definita pur rappresentando
  un confronto diverso da quello desiderato.
- Per misure numeriche che usano i valori originali, come Canberra,
  Bray-Curtis, chi-quadrato e Mahalanobis, la conferma generale del
  riscalamento non e' sufficiente: occorre confermare che il riscalamento
  venga ignorato dal relativo percorso.

Le incompatibilita' non producono sostituzioni silenziose di misura o di
preprocessing. Le conferme vengono invalidate quando cambia il metodo
di riscalamento, la composizione dei gruppi o il confronto richiesto.

### Asimmetria e possibili outlier multivariati

La diagnostica numerica preliminare distingue gli indicatori su singole
colonne dalla ricerca di osservazioni anomale considerando insieme piu'
coordinate:

- L'**asimmetria quartilica di Bowley** e'
  `(Q3 + Q1 - 2 mediana)/(Q3-Q1)`, disponibile solo se `IQR>0`.
  Il sito segnala valori con `|Bowley| >= 0,3` e almeno otto
  osservazioni, senza interpretare l'asimmetria come un errore ne'
  imporre una trasformazione logaritmica.
- Con almeno `max(12,5p)` righe complete per `p` coordinate
  quantitative non costanti e covarianza invertibile e numericamente
  ben condizionata, il sito calcola la **distanza di Mahalanobis quadrata**
  di ogni riga dalla media. Segnala come possibili anomalie le righe con
  punteggio maggiore di `Q3 + 1,5 IQR` dei punteggi. La soglia e'
  esplorativa e non corrisponde a un test statistico con livello
  controllato. La stima classica puo' essere distorta dagli stessi
  outlier che si cercano (mascheramento).
- Se le condizioni non sono soddisfatte, lo stato e' **non valutabile**,
  mai "nessuna anomalia". Le righe con mancanti non partecipano alla
  stima congiunta. I numeri di riga si riferiscono ai dati CSV, a
  partire da 1, senza contare l'intestazione.

Se esistono candidati multivariati, l'utente deve confermare che siano
osservazioni reali, oppure controllare il file. La conferma non elimina,
non modifica e non trascura automaticamente alcuna riga; i percorsi
di distanza restano quelli scelti separatamente.

### Scelta esplicita tra valori originali, scala robusta e log(1+x)

L'asimmetria e la presenza di valori estremi sono segnali diagnostici,
non condizioni che impongono da sole una trasformazione. Nella tabella
dei riscalamenti l'utente puo' confermare, per ogni colonna quantitativa:

- **Nessuna trasformazione**: conserva le differenze nella misura originale.
- **Scala robusta**: \(z=(x-\mathrm{mediana})/IQR\), se \(IQR>0\).
  Cambia centro e unita' di misura, ma **non** taglia, elimina o attenua
  necessariamente gli scarti dei valori estremi in una distanza.
- **Trasformazione logaritmica \(\log(1+x)\)**: disponibile **solo per
  dati osservati non negativi**. Preserva lo zero e comprime le
  differenze assolute ai valori alti. Non coincide con una
  standardizzazione: un incremento da 1 a 2 non ha lo stesso effetto
  di un incremento da 100 a 101. L'interpretazione va confermata
  dall'utente.

Le opzioni gia' presenti (z-score, min-max, max-abs) restano disponibili.
**Una trasformazione scelta manualmente prevale sulla politica automatica
di riscalamento per quel percorso**, anche se la politica predefinita
prevedeva z-score, scala robusta o min-max. Il piano elenca sempre la
trasformazione effettivamente usata nei calcoli e nella sua anteprima.
Le misure basate su valori originali, come Canberra, Bray-Curtis,
Mahalanobis e Gower classica, non ricevono automaticamente log(1+x).

### Normalizzazione dei contributi locali, anche robusta

La matrice globale combina distanze locali \(\delta_k\in[0,1]\). La
normalizzazione e' **successiva** al riscalamento delle singole colonne e
non modifica i dati di partenza. Il piano dichiara sempre, per ogni
percorso, la regola scelta.

- Per misure con massimo teorico noto (come Gower, confronti testuali
  normalizzati, Pearson/coseno e Bray--Curtis su quantità non negative),
  mantiene quel limite e non riscalibra sul campione. Canberra ha come
  limite teorico il numero delle coordinate.
- Senza un massimo teorico disponibile, il default e' il **massimo
  campionario delle distanze definite su coppie distinte**; se tutte le
  distanze valide sono zero, conserva il blocco a dissimilarità nulla.
- In alternativa, l'utente puo' selezionare la **scala robusta** e
  indicare quali **righe del CSV** considera anomale. Si ottiene
  \[
  M_k^{rob}=\max_{a<b,\ a,b\in A_k}d_k(a,b),\qquad
  \delta_k^{rob}(i,j)=\min\{d_k(i,j)/M_k^{rob},1\}.
  \]
  Qui \(A_k\) contiene le righe confermate *non anomale*; le altre
  rimangono nella matrice finale e vengono escluse solo dalla stima
  della scala. Se il massimo robusto e' zero mentre esistono distanze
  positive, oppure le righe non anomale non forniscono coppie valide,
  il sistema blocca il calcolo e chiede una revisione. Non ricorre
  automaticamente a un percentile o alla regola 7 IQR.

La diagnostica conclusiva indica quante coppie sono state saturate a 1
nel singolo blocco; la saturazione non e' un errore ma puo' ridurre
la capacita' discriminante dei confronti. In caso di scelta robusta,
la normalizzazione potrebbe non conservare la proprieta' triangolare
delle distanze originarie. La scelta non elimina osservazioni o blocchi.

### Kendall tau-b e Hamming sulle strutture appropriate

Nel gruppo di **misurazioni dello stesso profilo**, alla scelta
dell'ordinamento con Spearman si affianca quella per il confronto delle
coppie con **Kendall \(\tau_b\)**, che gestisce esplicitamente i pari merito:
\[
\tau_b=\frac{C-D}{\sqrt{(C+D+T_x)(C+D+T_y)}},
\qquad
\delta_{\mathrm K}(x,y)=\frac{1-\tau_b}{2}\in[0,1].
\]
\(C\) e \(D\) contano le coppie concordanti e discordanti;
\(T_x\), \(T_y\) contano quelle legate in una sola delle due serie.
Le coppie legate in entrambe non contribuiscono. Quando uno dei due
fattori al denominatore e' nullo, la dissimilarita' e' **non definita**,
non artificialmente zero. Non serve una scala campionaria: l'intervallo
teorico e' gia' \([0,1]\).

Nelle **colonne testuali** l'utente puo' scegliere Levenshtein, adatta
anche a inserimenti e cancellazioni, oppure **Hamming normalizzata**.
Per due sequenze della stessa lunghezza \(m>0\):
\[
d_{\mathrm H}(a,b)=\frac{1}{m}\sum_{i=1}^m
\mathbf{1}\{a_i\ne b_i\}.
\]
Per due sequenze vuote si pone \(d_{\mathrm H}=0\). Hamming e'
applicabile soltanto quando tutte le stringhe confrontabili hanno
la stessa lunghezza: il piano controlla il requisito prima del
calcolo e non passa automaticamente a Levenshtein quando non e'
rispettato. Le stringhe vengono trattate come sequenze di caratteri
Unicode; questo confronto non e' una distanza semantica fra parole.

La scelta di Kendall in un blocco di profili o di Hamming in una
colonna testuale non cambia le misure degli altri percorsi; la matrice
finale aggrega i contributi disponibili con i pesi confermati.

### Distribuzioni di probabilita' e istogrammi

Un gruppo di colonne puo' essere interpretato esplicitamente come **bin
di una distribuzione** (stesse categorie/intervalli per tutte le righe),
distinto dalle *parti di un totale* confrontate con Aitchison.

Il sito chiede due decisioni separate: il **significato dei valori**
e la **misura da applicare**. Quando le righe contengono probabilita',
la somma deve essere 1 (tolleranza numerica \`1e-6\` relativa); quando
contengono conteggi, percentuali, frequenze o masse non negative, il
sito calcola invece \(p_k=x_k/\sum_\ell x_\ell\) per ogni riga.
Sono ammessi zeri effettivi; non sono ammessi componenti negative
o totali di riga nulli. Gli eventuali mancanti si possono escludere
dal percorso, oppure sostituire con **zero soltanto se l'utente ne
conferma esplicitamente il significato**. Non si imputano media
o mediana per queste distribuzioni.

La **distanza di Hellinger**, in \([0,1]\), e'
\[
H(p,q)=\left(\frac12\sum_k(\sqrt{p_k}-\sqrt{q_k})^2\right)^{1/2}.
\]
La **distanza di Jensen--Shannon** (radice della divergenza
normalizzata, con logaritmi naturali) e'
\[
d_{JS}(p,q)=\sqrt{\frac{D_{KL}(p\|m)+D_{KL}(q\|m)}
{2\ln 2}},\qquad m=\frac{p+q}{2},
\]
dove i termini \(0\log(0/m)\) valgono zero per continuita',
senza pseudoconteggi. Per entrambe il massimo teorico e' \(1\);
non si impone una normalizzazione campionaria o robusta successiva.
Si tratta di misure fra distribuzioni, non della geometria dei
log-rapporti composizionali propria di Aitchison.

La verifica preventiva riguarda ciascuna riga utilizzata nel
percorso. Una riga invalida blocca il piano e indica il suo numero nel
CSV, senza correzioni automatiche. I gruppi con una colonna che assume
soltanto 0/1 restano utilizzabili quando l'utente ne conferma la
semantica di probabilita' o frequenza. Il resto della tabella puo'
essere confrontato mediante altri percorsi, poi aggregati con la
consueta media pesata delle dissimilarita' disponibili.

### Dissimilarità categoriali e ordinali personalizzate in Gower

Per le **categorie nominali** (o livelli che l'utente dichiara privi di
ordine) resta disponibile il confronto classico \(d(a,b)=\mathbf 1_{a\ne b}\).
In alternativa l'utente puo' confermare le dissimilarita' di tutte le
coppie di stati osservati, fra 0 e 1. L'editor mostra ogni coppia una
sola volta; **la simmetria e la diagonale nulla sono definite dalla
costruzione**, non inserite due volte. Se un valore mancante e' stato
esplicitamente interpretato come *assenza*, costituisce uno stato
distinto da confrontare anch'esso con tutte le categorie osservate.
La configurazione include l'elenco delle categorie: se cambia, viene
rifiutata anziche' riusare valori in un ordine differente. L'editor
gestisce fino a 16 stati per colonna; per cardinalita' superiori e'
disponibile la scelta classica o una revisione motivata delle categorie.

Per una variabile **ordinale** con livelli
\(\ell_1<\ldots<\ell_m\), l'utente puo' conservare intervalli
equidistanti oppure assegnare esplicitamente ampiezze positive
\(g_1,\ldots,g_{m-1}\). La coordinata del livello \(\ell_k\) e'
\[
u(\ell_k)=\frac{\sum_{h=1}^{k-1}g_h}{\sum_{h=1}^{m-1}g_h},
\qquad d(\ell_i,\ell_j)=|u(\ell_i)-u(\ell_j)|.
\]
La scala rimane in \([0,1]\) e non dipende dai valori dei codici
numerici originali. Se un livello e' l'unico osservato, il contributo
e' sempre zero. Per livelli testuali bisogna prima dichiararne l'ordine.

Queste scelte estendono i contributi interni di Gower, **non modificano
la definizione di Gower nominale classica**. Le dissimilarita' nominali
personalizzate sono simmetriche, non negative e limitate da 1, ma
potrebbero non soddisfare la disuguaglianza triangolare; non sono
pertanto automaticamente metriche. Gli intervalli ordinali positivi
inducono invece la distanza assoluta sulla coordinata cumulativa.
Le impostazioni incompatibili o incomplete bloccano il piano prima
della generazione della matrice finale.

### Test dell'interfaccia e risposte asincrone

Oltre ai test numerici Python e ai test JavaScript delle misure,
`npm test` esegue `test/test-preprocessing-ui.js`. Il collaudo
simula con un DOM minimale le interazioni tra CSV, questionario,
gruppi, piani e matrice: caricamenti concorrenti, modifiche al
riscalamento, risposte asincrone superate, conferme temporali,
dissimilarità nominali personalizzate e ripristino dei comandi.
Le risposte di calcolo obsolete non possono riaprire un piano
invalidato né mostrare una matrice riferita a scelte precedenti.

Il test DOM è intenzionalmente privo di dipendenze esterne e
**non equivale a un test end-to-end nel browser reale**. Resta
necessaria una verifica manuale di layout, accessibilità,
gestione della tastiera, esportazione e percorso completo su
GitHub Pages.

## Matrice complessiva con più percorsi

Ogni percorso produce prima la propria matrice. Gower, i confronti 0/1 e le
dissimilarità già limitate conservano la loro scala teorica; le distanze non
limitate vengono divise per il massimo campionario del percorso (se positivo).
La stessa regola vale anche quando e' presente un unico percorso: la matrice
finale contiene sempre dissimilarita' nell'intervallo [0,1].

La matrice complessiva usa, per ogni coppia di righe, la media pesata dei soli
contributi disponibili:

\[
D(i,j)=\frac{\sum_b w_b\,\delta_{ij}^{(b)}\,\widetilde D^{(b)}(i,j)}
{\sum_b w_b\,\delta_{ij}^{(b)}}.
\]

I pesi dei percorsi sono strettamente positivi e valgono 1 per impostazione
predefinita. Se un percorso non può confrontare una coppia, non partecipa né al
numeratore né al denominatore di quella coppia. Se nessun percorso è
disponibile, il calcolo finale viene bloccato e il sito indica le coppie di
righe prive di un contributo valido. Non viene mai esportata una matrice finale
contenente celle vuote o valori non numerici.

Nei gruppi temporali l'utente deve confermare esplicitamente
l'**ordine cronologico** (elencando tutte e sole le colonne del gruppo)
e dichiarare che gli intervalli temporali sono **regolari**. L'ordine
non viene dedotto dal CSV e, se viene cambiato, determina effettivamente
l'ordine delle coordinate usato dalla DTW e dal confronto punto per punto.
Se gli istanti non sono equidistanti, il percorso si interrompe e chiede
un ricampionamento o un allineamento esplicito (non ancora disponibile).
L'interpolazione lineare e' applicata soltanto ai vuoti interni in una
serie con campionamento regolare; una serie priva del primo o dell'ultimo
valore non viene estrapolata. Nei profili numerici, media e mediana sono stimate
separatamente per colonna. Nei percorsi testuali una casella vuota può essere
esclusa dal solo percorso oppure interpretata come stringa vuota, ma soltanto
dopo una conferma esplicita.

La distanza composizionale di Aitchison non accetta zeri. Se l’utente conferma
che rappresentano valori sotto soglia, il sito chiude ogni riga a somma 1,
usa una piccola proporzione positiva non superiore a metà della minima osservata
e limitata per conservare almeno metà della massa alle componenti positive.
Queste ultime vengono ridimensionate proporzionalmente. Il valore usato compare nella nota
della matrice. Se gli zeri sono assenze strutturali, Aitchison viene
dichiarata non adatta e il calcolo resta bloccato.


## Convenzioni esplicite di Gower per dati misti

La Gower classica usa per le quantitative la differenza assoluta divisa per
l'intervallo osservato; per le nominali il disaccordo 0/1; per le ordinali
i ranghi normalizzati. I pesi delle caratteristiche sono strettamente positivi
(valore predefinito 1) e partecipano sia al numeratore sia al denominatore.
I dati numerici vengono letti dai valori originali, non dall'anteprima riscalata.

- Le colonne osservate ma costanti restano nel denominatore con peso
  strettamente positivo e contributo zero; il piano le segnala. Se tutte le
  colonne sono costanti e osservate, la matrice di Gower e' interamente nulla.
  Una colonna interamente mancante, invece, non fornisce contributi.
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
- Per la **variante robusta** occorre scegliere esplicitamente, per ogni
  colonna quantitativa, quali righe anomale escludere **soltanto dalla stima
  della scala**. Si utilizza il massimo scarto fra i valori non anomali,
  saturando i contributi a 1. La regola 7 volte IQR non e' piu' utilizzata
  automaticamente. Le righe anomale restano nella matrice.
- Se nessun contributo e' disponibile per una coppia, quella dissimilarita'
  intermedia resta non definita. Il controllo finale, pero', blocca il
  risultato e indica le coppie da risolvere. Vengono inoltre verificati
  simmetria, diagonale nulla, finitezza e intervallo [0,1]. Le eventuali
  dissimilarita' nulle tra righe distinte sono segnalate senza bloccare il
  calcolo. Con mancanti e assenze asimmetriche non si richiede la proprieta'
  triangolare.

I percorsi distinti (numerici, misti, testuali e gruppi temporali) vengono
aggregati in una sola matrice quando le coppie risultano tutte confrontabili.
