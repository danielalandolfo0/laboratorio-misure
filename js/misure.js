/* Nucleo matematico dell'applicazione, indipendente dall'interfaccia. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.Misure = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const dominioNumerico = "Vettori numerici della stessa dimensione, con coordinate commensurabili.";
  const dominioBinario = "Vettori della stessa dimensione con coordinate uguali a 0 o 1.";

  const definizioni = {
    minkowski: {
      nome: "Distanza di Minkowski", tipoDati: "numeric",
      formula: String.raw`d_q(x,y)=\left(\sum_{j=1}^{p}|x_j-y_j|^q\right)^{1/q}`,
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|^q.",
      interpretazione: "Il parametro q controlla quanto le differenze più grandi dominano il risultato.",
      dominio: dominioNumerico, proprieta: "Per q ≥ 1 è una metrica."
    },
    manhattan: {
      nome: "Distanza di Manhattan (Minkowski q=1)", tipoDati: "numeric",
      formula: String.raw`d_1(x,y)=\sum_{j=1}^{p}|x_j-y_j|`,
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|.",
      interpretazione: "Somma gli spostamenti lungo le coordinate, come un percorso composto da tratti paralleli agli assi.",
      dominio: dominioNumerico, proprieta: "È una metrica."
    },
    euclidean: {
      nome: "Distanza euclidea (Minkowski q=2)", tipoDati: "numeric",
      formula: String.raw`d_2(x,y)=\left(\sum_{j=1}^{p}|x_j-y_j|^2\right)^{1/2}`,
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|².",
      interpretazione: "È la lunghezza del segmento che congiunge i due punti. Differenze grandi incidono quadraticamente.",
      dominio: dominioNumerico, proprieta: "È una metrica."
    },
    chebyshev: {
      nome: "Distanza di Chebyshev (Minkowski q=∞)", tipoDati: "numeric",
      formula: String.raw`d_{\infty}(x,y)=\max_{1\leq j\leq p}|x_j-y_j|`,
      contributo: "Le barre mostrano |xⱼ − yⱼ|; conta soltanto il valore massimo.",
      interpretazione: "È determinata dalla coordinata nella quale i due vettori differiscono maggiormente.",
      dominio: dominioNumerico, proprieta: "È una metrica."
    },
    weighted_minkowski: {
      nome: "Distanza di Minkowski pesata", tipoDati: "numeric",
      formula: String.raw`d_{q,w}(x,y)=\left(\sum_{j=1}^{p}w_j|x_j-y_j|^q\right)^{1/q}`,
      contributo: "Ogni barra rappresenta wⱼ|xⱼ − yⱼ|^q.",
      interpretazione: "I pesi modificano l'importanza relativa delle coordinate.",
      dominio: "Vettori numerici della stessa dimensione e pesi wⱼ strettamente positivi.",
      proprieta: "Per q ≥ 1 e wⱼ>0 è una metrica."
    },
    standardized_euclidean: {
      nome: "Distanza euclidea standardizzata", tipoDati: "numeric",
      formula: String.raw`d_{\mathrm{std}}(x,y)=\left(\sum_{j=1}^{p}\frac{(x_j-y_j)^2}{s_j^2}\right)^{1/2}`,
      contributo: "Ogni barra rappresenta (xⱼ − yⱼ)²/sⱼ².",
      interpretazione: "Divide ogni differenza per la scala della corrispondente variabile.",
      dominio: "Vettori numerici della stessa dimensione e scale sⱼ strettamente positive.",
      proprieta: "È una distanza euclidea pesata e quindi una metrica."
    },
    mahalanobis: {
      nome: "Distanza di Mahalanobis", tipoDati: "numeric",
      formula: String.raw`d_M(x,y)=\sqrt{(x-y)^\top S^{-1}(x-y)}`,
      contributo: "Le barre rappresentano i contributi quadratici nelle coordinate trasformate.",
      interpretazione: "Tiene conto delle scale e delle correlazioni codificate dalla matrice S.",
      dominio: "Vettori numerici e matrice S simmetrica definita positiva di dimensione p×p.",
      proprieta: "È una metrica quando S è definita positiva."
    },
    canberra: {
      nome: "Distanza di Canberra", tipoDati: "numeric",
      formula: String.raw`d_C(x,y)=\sum_{j=1}^{p}\frac{|x_j-y_j|}{|x_j|+|y_j|}`,
      contributo: "Ogni barra mostra uno scarto relativo; il termine 0/0 è posto uguale a 0.",
      interpretazione: "Differenze vicine allo zero possono avere un peso elevato; le doppie assenze sono ignorate.",
      dominio: dominioNumerico, proprieta: "È una metrica."
    },
    bray_curtis: {
      nome: "Dissimilarità di Bray–Curtis", tipoDati: "numeric",
      formula: String.raw`d_{BC}(x,y)=\frac{\sum_j|x_j-y_j|}{\sum_j(x_j+y_j)}`,
      contributo: "Le barre mostrano |xⱼ − yⱼ|.",
      interpretazione: "Confronta le differenze assolute rispetto alla quantità complessiva e ignora le doppie assenze.",
      dominio: "Vettori non negativi della stessa dimensione, non entrambi nulli.",
      proprieta: "Assume valori in [0,1], ma non soddisfa in generale la disuguaglianza triangolare."
    },
    chi_square: {
      nome: "Distanza χ² simmetrica", tipoDati: "numeric",
      formula: String.raw`d_{\chi^2}(x,y)=\left(\sum_{j=1}^{p}\frac{(x_j-y_j)^2}{x_j+y_j}\right)^{1/2}`,
      contributo: "Ogni barra rappresenta (xⱼ − yⱼ)²/(xⱼ + yⱼ), ponendo 0/0=0.",
      interpretazione: "Uno stesso scarto pesa maggiormente quando riguarda valori complessivamente piccoli.",
      dominio: "Vettori non negativi della stessa dimensione.", proprieta: "È una metrica."
    },
    weighted_binary: {
      nome: "Similarità binaria pesata", tipoDati: "binary", risultato: "Similarità",
      formula: String.raw`S_{\lambda,\mu,\nu}(x,y)=\frac{\lambda n_{11}+\mu n_{00}}{\lambda n_{11}+\mu n_{00}+\nu(n_{10}+n_{01})}`,
      interpretazione: "I parametri stabiliscono il peso di co-presenze, co-assenze e disaccordi; valori maggiori indicano maggiore similarità.",
      dominio: dominioBinario + " I pesi λ, μ, ν sono non negativi e il denominatore deve essere positivo.",
      proprieta: "È una famiglia di coefficienti di similarità con valori in [0,1]; non è una distanza."
    },
    hamming: {
      nome: "Hamming normalizzata / Simple Matching", tipoDati: "binary", risultato: "Distanza",
      formula: String.raw`d_H(x,y)=\frac{n_{10}+n_{01}}{p}`,
      interpretazione: "È la proporzione di coordinate discordanti; presenza e assenza hanno lo stesso peso.",
      dominio: dominioBinario, proprieta: "È una metrica e coincide con la dissimilarità Simple Matching."
    },
    rogers_tanimoto: {
      nome: "Dissimilarità di Rogers–Tanimoto", tipoDati: "binary", risultato: "Dissimilarità",
      formula: String.raw`d_{RT}(x,y)=\frac{2(n_{10}+n_{01})}{n_{11}+n_{00}+2(n_{10}+n_{01})}`,
      interpretazione: "Attribuisce peso doppio ai disaccordi rispetto agli accordi.",
      dominio: dominioBinario, proprieta: "È una metrica."
    },
    sokal_sneath_sym: {
      nome: "Sokal–Sneath simmetrico", tipoDati: "binary", risultato: "Dissimilarità",
      formula: String.raw`d_{SS,s}(x,y)=\frac{n_{10}+n_{01}}{2(n_{11}+n_{00})+n_{10}+n_{01}}`,
      interpretazione: "Attribuisce peso doppio agli accordi, comprese le assenze comuni.",
      dominio: dominioBinario, proprieta: "Separa i vettori, ma può violare la disuguaglianza triangolare."
    },
    jaccard: {
      nome: "Dissimilarità di Jaccard", tipoDati: "binary", risultato: "Dissimilarità",
      formula: String.raw`d_J(x,y)=\frac{n_{10}+n_{01}}{n_{11}+n_{10}+n_{01}}`,
      interpretazione: "Confronta soltanto le presenze: le assenze comuni n₀₀ non modificano il risultato.",
      dominio: dominioBinario + " Per due vettori nulli si pone convenzionalmente dJ=0.",
      proprieta: "È una metrica e assume valori in [0,1]."
    },
    sokal_sneath_asym: {
      nome: "Sokal–Sneath asimmetrico", tipoDati: "binary", risultato: "Dissimilarità",
      formula: String.raw`d_{SS,a}(x,y)=\frac{2(n_{10}+n_{01})}{n_{11}+2(n_{10}+n_{01})}`,
      interpretazione: "Penalizza ogni disaccordo due volte rispetto a una co-presenza e ignora le doppie assenze.",
      dominio: dominioBinario + " Per due vettori nulli si pone convenzionalmente d=0.",
      proprieta: "Con la convenzione per i vettori nulli è una metrica."
    },
    dice: {
      nome: "Dissimilarità di Dice–Sørensen", tipoDati: "binary", risultato: "Dissimilarità",
      formula: String.raw`d_D(x,y)=\frac{n_{10}+n_{01}}{2n_{11}+n_{10}+n_{01}}`,
      interpretazione: "Pesa due volte le co-presenze e ignora le assenze comuni.",
      dominio: dominioBinario + " Non è definita quando entrambi i vettori sono nulli.",
      proprieta: "È una semimetrica: può violare la disuguaglianza triangolare."
    },
    ochiai: {
      nome: "Dissimilarità di Ochiai", tipoDati: "binary", risultato: "Dissimilarità",
      formula: String.raw`d_O(x,y)=1-\frac{n_{11}}{\sqrt{(n_{11}+n_{10})(n_{11}+n_{01})}}`,
      interpretazione: "Normalizza le presenze comuni rispetto al numero di presenze nei due vettori.",
      dominio: dominioBinario + " Non è definita se almeno uno dei vettori è nullo.",
      proprieta: "Il complemento del coefficiente di Ochiai non è una metrica in generale."
    },
    russell_rao: {
      nome: "Dissimilarità di Russell–Rao", tipoDati: "binary", risultato: "Dissimilarità",
      formula: String.raw`d_{RR}(x,y)=1-\frac{n_{11}}{p}`,
      interpretazione: "Confronta le co-presenze con tutte le coordinate, comprese le doppie assenze nel denominatore.",
      dominio: dominioBinario, proprieta: "Non deriva da una similarità normalizzata sulla diagonale e non è una metrica."
    },
    string_hamming: {
      nome: "Distanza di Hamming", tipoDati: "string", risultato: "Distanza",
      formula: String.raw`d_H(x,y)=\sum_{i=1}^{n}\mathbf 1_{\{x_i\neq y_i\}}`,
      interpretazione: "Conta le posizioni nelle quali i simboli sono differenti.",
      dominio: "Stringhe della stessa lunghezza, già allineate. Ogni carattere, spazi inclusi, è trattato come un simbolo.",
      proprieta: "È una metrica sullo spazio delle stringhe di lunghezza fissata."
    },
    string_hamming_normalized: {
      nome: "Distanza di Hamming normalizzata", tipoDati: "string", risultato: "Distanza",
      formula: String.raw`d_H^{\mathrm{norm}}(x,y)=\frac{d_H(x,y)}{n}`,
      interpretazione: "È la proporzione di posizioni discordanti e rende confrontabili risultati ottenuti su coppie di lunghezze differenti.",
      dominio: "Stringhe non vuote della stessa lunghezza, già allineate.",
      proprieta: "Assume valori in [0,1] ed è una metrica per ogni lunghezza fissata."
    },
    levenshtein: {
      nome: "Distanza di Levenshtein", tipoDati: "string", risultato: "Distanza",
      formula: String.raw`\begin{aligned}D_{0j}&=j,\quad D_{i0}=i,\\ D_{ij}&=\min\!\left\{\begin{array}{l}D_{i-1,j}+1\\ D_{i,j-1}+1\\ D_{i-1,j-1}+\mathbf 1_{\{x_i\neq y_j\}}\end{array}\right.,\\ d_L(x,y)&=D_{nm}\end{aligned}`,
      interpretazione: "È il numero minimo di inserimenti, cancellazioni e sostituzioni necessari per trasformare una stringa nell'altra.",
      dominio: "Stringhe finite, anche di lunghezza differente. Ogni operazione ha costo unitario.",
      proprieta: "Con costi unitari è una metrica."
    },
    levenshtein_normalized: {
      nome: "Levenshtein normalizzata", tipoDati: "string", risultato: "Dissimilarità",
      formula: String.raw`d_L^{\mathrm{norm}}(x,y)=\frac{d_L(x,y)}{\max\{n,m\}}`,
      interpretazione: "Rapporta il numero minimo di modifiche alla lunghezza della stringa più lunga.",
      dominio: "Stringhe finite non entrambe vuote, con costi unitari.",
      proprieta: "Assume valori in [0,1], ma la normalizzazione può modificare le proprietà metriche."
    },
    damerau_levenshtein: {
      nome: "Distanza di Damerau–Levenshtein", tipoDati: "string", risultato: "Distanza",
      formula: String.raw`d_{DL}(x,y)=\min\!\left\{k:\;x\xrightarrow{k\text{ operazioni ammesse}}y\right\}`,
      interpretazione: "È il numero minimo di operazioni necessarie per trasformare una stringa nell’altra: inserimenti, cancellazioni, sostituzioni e trasposizioni di simboli adiacenti.",
      dominio: "Stringhe finite; inserimenti, cancellazioni, sostituzioni e trasposizioni adiacenti hanno costo unitario.",
      proprieta: "La versione completa implementata qui è una metrica."
    }
  };

  function leggiVettore(testo) {
    const normalizzato = String(testo).trim().replace(/;/g, " ");
    if (!normalizzato) throw new Error("Inserisci entrambi i vettori.");
    const parti = normalizzato.includes(",") ? normalizzato.split(",") : normalizzato.split(/\s+/);
    const valori = parti.filter(parte => parte.trim() !== "").map(parte => Number(parte.trim()));
    if (!valori.length || valori.some(v => !Number.isFinite(v))) throw new Error("Usa soltanto numeri finiti separati da virgole, spazi o punti e virgola.");
    return valori;
  }

  function leggiMatrice(testo) {
    const righe = String(testo).trim().split(/;|\n/).map(r => r.trim()).filter(Boolean);
    if (!righe.length) throw new Error("Inserisci la matrice S.");
    const matrice = righe.map(r => r.includes(",") ? r.split(",").map(Number) : r.split(/\s+/).map(Number));
    if (matrice.some(r => r.length !== matrice.length || r.some(v => !Number.isFinite(v)))) throw new Error("La matrice S deve essere quadrata e contenere soltanto numeri finiti.");
    return matrice;
  }

  function leggiStringa(testo) {
    return Array.from(String(testo));
  }

  function validaStringhe(x, y) {
    if (!Array.isArray(x) || !Array.isArray(y)) throw new TypeError("Le stringhe devono essere sequenze di simboli.");
  }

  function validaVettori(x, y) {
    if (!Array.isArray(x) || !Array.isArray(y)) throw new TypeError("x e y devono essere vettori numerici.");
    if (x.length === 0 || y.length === 0) throw new Error("I vettori non possono essere vuoti.");
    if (x.length !== y.length) throw new Error(`I vettori devono avere la stessa dimensione: x ne ha ${x.length}, y ne ha ${y.length}.`);
    if ([...x, ...y].some(v => !Number.isFinite(v))) throw new Error("Tutte le coordinate devono essere numeri finiti.");
  }

  function validaBinari(x, y) {
    validaVettori(x, y);
    if ([...x, ...y].some(v => v !== 0 && v !== 1)) throw new Error("Per le misure binarie ogni coordinata deve essere uguale a 0 oppure 1.");
  }

  function validaPositivi(v, p, nome) {
    if (!Array.isArray(v) || v.length !== p) throw new Error(`${nome} deve contenere esattamente ${p} valori.`);
    if (v.some(a => !Number.isFinite(a) || a <= 0)) throw new Error(`${nome} deve contenere soltanto valori strettamente positivi.`);
  }

  function cholesky(S, p) {
    if (!Array.isArray(S) || S.length !== p || S.some(r => !Array.isArray(r) || r.length !== p)) throw new Error(`La matrice S deve avere dimensione ${p}×${p}.`);
    const scala = Math.max(1, ...S.flat().map(Math.abs));
    const tolleranza = 1e-10 * scala;
    for (let i = 0; i < p; i += 1) for (let j = i + 1; j < p; j += 1) {
      if (!Number.isFinite(S[i][j]) || !Number.isFinite(S[j][i]) || Math.abs(S[i][j] - S[j][i]) > tolleranza) throw new Error("La matrice S deve essere simmetrica.");
    }
    const L = Array.from({ length: p }, () => Array(p).fill(0));
    for (let i = 0; i < p; i += 1) for (let j = 0; j <= i; j += 1) {
      let somma = S[i][j];
      for (let k = 0; k < j; k += 1) somma -= L[i][k] * L[j][k];
      if (i === j) {
        if (!(somma > tolleranza)) throw new Error("La matrice S deve essere definita positiva.");
        L[i][j] = Math.sqrt(somma);
      } else L[i][j] = somma / L[j][j];
    }
    return L;
  }

  function minkowski(x, y, q) {
    validaVettori(x, y);
    if (!Number.isFinite(q) || q < 1) throw new Error("Per la distanza di Minkowski è necessario un parametro finito q ≥ 1.");
    return Math.pow(x.reduce((s, v, j) => s + Math.pow(Math.abs(v - y[j]), q), 0), 1 / q);
  }

  function chebyshev(x, y) {
    validaVettori(x, y);
    return Math.max(...x.map((v, j) => Math.abs(v - y[j])));
  }

  function calcola(x, y, q) {
    validaVettori(x, y);
    if (q !== Infinity && (!Number.isFinite(q) || q < 1)) throw new Error("Per la distanza di Minkowski è necessario q ≥ 1.");
    const scarti = x.map((v, j) => Math.abs(v - y[j]));
    const contributi = q === Infinity ? scarti.slice() : scarti.map(s => Math.pow(s, q));
    const distanza = q === Infinity ? Math.max(...scarti) : Math.pow(contributi.reduce((a, b) => a + b, 0), 1 / q);
    return { definita: true, valore: distanza, distanza, scarti, contributi };
  }

  function calcolaNumerica(tipo, x, y, parametri = {}) {
    validaVettori(x, y);
    const scarti = x.map((v, j) => Math.abs(v - y[j]));
    if (tipo === "manhattan") return calcola(x, y, 1);
    if (tipo === "euclidean") return calcola(x, y, 2);
    if (tipo === "chebyshev") return calcola(x, y, Infinity);
    if (tipo === "minkowski") return calcola(x, y, parametri.q);
    let contributi;
    let valore;
    if (tipo === "weighted_minkowski") {
      const q = parametri.q;
      if (!Number.isFinite(q) || q < 1) throw new Error("Per Minkowski pesata occorre q ≥ 1.");
      validaPositivi(parametri.pesi, x.length, "Il vettore dei pesi");
      contributi = scarti.map((s, j) => parametri.pesi[j] * Math.pow(s, q));
      valore = Math.pow(contributi.reduce((a, b) => a + b, 0), 1 / q);
    } else if (tipo === "standardized_euclidean") {
      validaPositivi(parametri.scale, x.length, "Il vettore delle scale");
      contributi = scarti.map((s, j) => Math.pow(s / parametri.scale[j], 2));
      valore = Math.sqrt(contributi.reduce((a, b) => a + b, 0));
    } else if (tipo === "mahalanobis") {
      const L = cholesky(parametri.matrice, x.length);
      const diff = x.map((v, j) => v - y[j]);
      const z = [];
      for (let i = 0; i < diff.length; i += 1) {
        let s = diff[i];
        for (let k = 0; k < i; k += 1) s -= L[i][k] * z[k];
        z[i] = s / L[i][i];
      }
      contributi = z.map(v => v * v);
      valore = Math.sqrt(contributi.reduce((a, b) => a + b, 0));
    } else if (tipo === "canberra") {
      contributi = x.map((v, j) => {
        const den = Math.abs(v) + Math.abs(y[j]);
        return den === 0 ? 0 : Math.abs(v - y[j]) / den;
      });
      valore = contributi.reduce((a, b) => a + b, 0);
    } else if (tipo === "bray_curtis") {
      if ([...x, ...y].some(v => v < 0)) throw new Error("Bray–Curtis richiede coordinate non negative.");
      const den = x.reduce((s, v, j) => s + v + y[j], 0);
      contributi = scarti;
      if (den === 0) return { definita: false, valore: null, contributi, messaggio: "Bray–Curtis non è definita per due vettori entrambi nulli." };
      valore = contributi.reduce((a, b) => a + b, 0) / den;
    } else if (tipo === "chi_square") {
      if ([...x, ...y].some(v => v < 0)) throw new Error("La distanza χ² simmetrica richiede coordinate non negative.");
      contributi = x.map((v, j) => v + y[j] === 0 ? 0 : Math.pow(v - y[j], 2) / (v + y[j]));
      valore = Math.sqrt(contributi.reduce((a, b) => a + b, 0));
    } else throw new Error("Misura numerica non riconosciuta.");
    return { definita: true, valore, distanza: valore, scarti, contributi };
  }

  function conteggiBinari(x, y) {
    validaBinari(x, y);
    const c = { n11: 0, n10: 0, n01: 0, n00: 0 };
    x.forEach((v, j) => { c[`n${v}${y[j]}`] += 1; });
    return c;
  }

  function nonDefinita(conteggi, messaggio) {
    return { definita: false, valore: null, distanza: null, conteggi, messaggio };
  }

  function calcolaBinaria(tipo, x, y, parametri = {}) {
    const c = conteggiBinari(x, y);
    const { n11, n10, n01, n00 } = c;
    const m = n10 + n01;
    const a = n11 + n00;
    const p = x.length;
    let valore;
    if (tipo === "weighted_binary") {
      const { lambda, mu, nu } = parametri;
      if (![lambda, mu, nu].every(v => Number.isFinite(v) && v >= 0)) throw new Error("I pesi λ, μ e ν devono essere non negativi.");
      const den = lambda * n11 + mu * n00 + nu * m;
      if (den === 0) return nonDefinita(c, "La similarità pesata non è definita perché il denominatore è nullo.");
      valore = (lambda * n11 + mu * n00) / den;
    } else if (tipo === "hamming") valore = m / p;
    else if (tipo === "rogers_tanimoto") valore = 2 * m / (a + 2 * m);
    else if (tipo === "sokal_sneath_sym") valore = m / (2 * a + m);
    else if (tipo === "jaccard") valore = n11 + m === 0 ? 0 : m / (n11 + m);
    else if (tipo === "sokal_sneath_asym") valore = n11 + 2 * m === 0 ? 0 : 2 * m / (n11 + 2 * m);
    else if (tipo === "dice") {
      const den = 2 * n11 + m;
      if (den === 0) return nonDefinita(c, "Dice–Sørensen non è definita per due vettori entrambi nulli.");
      valore = m / den;
    } else if (tipo === "ochiai") {
      const px = n11 + n10;
      const py = n11 + n01;
      if (px === 0 || py === 0) return nonDefinita(c, "Ochiai non è definita se almeno uno dei due vettori è nullo.");
      valore = 1 - n11 / Math.sqrt(px * py);
    } else if (tipo === "russell_rao") valore = 1 - n11 / p;
    else throw new Error("Misura binaria non riconosciuta.");
    return { definita: true, valore, distanza: valore, conteggi: c };
  }

  function matriceLevenshtein(x, y) {
    const D = Array.from({ length: x.length + 1 }, () => Array(y.length + 1).fill(0));
    for (let i = 0; i <= x.length; i += 1) D[i][0] = i;
    for (let j = 0; j <= y.length; j += 1) D[0][j] = j;
    for (let i = 1; i <= x.length; i += 1) {
      for (let j = 1; j <= y.length; j += 1) {
        D[i][j] = Math.min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + (x[i - 1] === y[j - 1] ? 0 : 1));
      }
    }
    return D;
  }

  function matriceDamerauLevenshtein(x, y) {
    const n = x.length, p = y.length, infinito = n + p;
    const H = Array.from({ length: n + 2 }, () => Array(p + 2).fill(0));
    H[0][0] = infinito;
    for (let i = 0; i <= n; i += 1) { H[i + 1][0] = infinito; H[i + 1][1] = i; }
    for (let j = 0; j <= p; j += 1) { H[0][j + 1] = infinito; H[1][j + 1] = j; }
    const ultimaRiga = new Map();
    for (let i = 1; i <= n; i += 1) {
      let ultimaColonna = 0;
      for (let j = 1; j <= p; j += 1) {
        const i1 = ultimaRiga.get(y[j - 1]) || 0, j1 = ultimaColonna;
        let costo = 1;
        if (x[i - 1] === y[j - 1]) { costo = 0; ultimaColonna = j; }
        H[i + 1][j + 1] = Math.min(
          H[i][j] + costo,
          H[i + 1][j] + 1,
          H[i][j + 1] + 1,
          H[i1][j1] + (i - i1 - 1) + 1 + (j - j1 - 1)
        );
      }
      ultimaRiga.set(x[i - 1], i);
    }
    return { valore: H[n + 1][p + 1], matrice: H.slice(1).map(riga => riga.slice(1)) };
  }

  function calcolaStringa(tipo, testoX, testoY) {
    const x = Array.isArray(testoX) ? testoX.slice() : leggiStringa(testoX);
    const y = Array.isArray(testoY) ? testoY.slice() : leggiStringa(testoY);
    validaStringhe(x, y);
    if (["string_hamming", "string_hamming_normalized"].includes(tipo)) {
      if (x.length !== y.length) throw new Error("La distanza di Hamming richiede stringhe della stessa lunghezza.");
      if (tipo === "string_hamming_normalized" && x.length === 0) throw new Error("La Hamming normalizzata non è definita per due stringhe vuote.");
      const confronti = x.map((simbolo, i) => ({ simboloX: simbolo, simboloY: y[i], diverso: simbolo !== y[i] }));
      const distanza = confronti.reduce((somma, confronto) => somma + Number(confronto.diverso), 0);
      const valore = tipo === "string_hamming_normalized" ? distanza / x.length : distanza;
      return { definita: true, valore, distanza: valore, simboliX: x, simboliY: y, confronti };
    }
    if (tipo === "levenshtein" || tipo === "levenshtein_normalized") {
      const matrice = matriceLevenshtein(x, y), distanza = matrice[x.length][y.length];
      if (tipo === "levenshtein_normalized" && Math.max(x.length, y.length) === 0) throw new Error("La Levenshtein normalizzata non è definita per due stringhe vuote.");
      const valore = tipo === "levenshtein_normalized" ? distanza / Math.max(x.length, y.length) : distanza;
      return { definita: true, valore, distanza: valore, simboliX: x, simboliY: y, matrice };
    }
    if (tipo === "damerau_levenshtein") {
      const risultato = matriceDamerauLevenshtein(x, y);
      return { definita: true, valore: risultato.valore, distanza: risultato.valore, simboliX: x, simboliY: y, matrice: risultato.matrice };
    }
    throw new Error("Misura per stringhe non riconosciuta.");
  }

  function formatta(numero) {
    if (numero === null || numero === undefined || !Number.isFinite(numero)) return "Non definita";
    if (Math.abs(numero) < 1e-12) return "0";
    return new Intl.NumberFormat("it-IT", { maximumFractionDigits: 6 }).format(numero);
  }

  return {
    definizioni, leggiVettore, leggiMatrice, leggiStringa, validaVettori, validaBinari, validaStringhe,
    minkowski, chebyshev, calcola, calcolaNumerica, conteggiBinari,
    calcolaBinaria, calcolaStringa, matriceLevenshtein, matriceDamerauLevenshtein, cholesky, formatta
  };
});
