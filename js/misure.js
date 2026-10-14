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
    euclidean: {
      nome: "Distanza euclidea",
      tipoDati: "numeric",
      q: 2,
      formula: String.raw`d_2(x,y)=\left(\sum_{j=1}^{p}|x_j-y_j|^2\right)^{1/2}`,
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|².",
      interpretazione: "È la lunghezza del segmento che congiunge i due punti. Differenze grandi incidono quadraticamente.",
      dominio: dominioNumerico,
      proprieta: "È una metrica: è non negativa, simmetrica e soddisfa la disuguaglianza triangolare."
    },
    manhattan: {
      nome: "Distanza di Manhattan",
      tipoDati: "numeric",
      q: 1,
      formula: String.raw`d_1(x,y)=\sum_{j=1}^{p}|x_j-y_j|`,
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|.",
      interpretazione: "Somma gli spostamenti lungo le coordinate, come un percorso composto da tratti paralleli agli assi.",
      dominio: dominioNumerico,
      proprieta: "È una metrica: è non negativa, simmetrica e soddisfa la disuguaglianza triangolare."
    },
    chebyshev: {
      nome: "Distanza di Chebyshev",
      tipoDati: "numeric",
      q: Infinity,
      formula: String.raw`d_{\infty}(x,y)=\max_{1\leq j\leq p}|x_j-y_j|`,
      contributo: "Le barre mostrano |xⱼ − yⱼ|; conta soltanto il valore massimo.",
      interpretazione: "È determinata dalla coordinata nella quale i due vettori differiscono maggiormente.",
      dominio: dominioNumerico,
      proprieta: "È una metrica: è non negativa, simmetrica e soddisfa la disuguaglianza triangolare."
    },
    minkowski: {
      nome: "Distanza di Minkowski",
      tipoDati: "numeric",
      q: 3,
      formula: String.raw`d_q(x,y)=\left(\sum_{j=1}^{p}|x_j-y_j|^q\right)^{1/q}`,
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|^q.",
      interpretazione: "Il parametro q controlla quanto le differenze più grandi dominano il risultato.",
      dominio: dominioNumerico,
      proprieta: "Per q ≥ 1 è una metrica; per 0 < q < 1 la disuguaglianza triangolare non vale in generale."
    },
    jaccard: {
      nome: "Distanza di Jaccard",
      tipoDati: "binary",
      formula: String.raw`d_J(x,y)=\frac{n_{10}+n_{01}}{n_{11}+n_{10}+n_{01}}`,
      interpretazione: "Confronta soltanto le presenze: le assenze comuni n₀₀ non modificano il risultato.",
      dominio: dominioBinario,
      proprieta: "È una metrica sui vettori binari identificati con insiemi e assume valori in [0,1]."
    },
    dice: {
      nome: "Distanza di Dice",
      tipoDati: "binary",
      formula: String.raw`d_D(x,y)=\frac{n_{10}+n_{01}}{2n_{11}+n_{10}+n_{01}}`,
      interpretazione: "Dà peso doppio alle presenze comuni e ignora le assenze comuni.",
      dominio: dominioBinario,
      proprieta: "È una dissimilarità simmetrica in [0,1], ma non è una metrica in generale."
    },
    ochiai: {
      nome: "Distanza di Ochiai",
      tipoDati: "binary",
      formula: String.raw`d_O(x,y)=1-\frac{n_{11}}{\sqrt{(n_{11}+n_{10})(n_{11}+n_{01})}}`,
      interpretazione: "Misura la sovrapposizione delle presenze rispetto alla loro numerosità nei due vettori.",
      dominio: dominioBinario,
      proprieta: "È una dissimilarità simmetrica in [0,1]; la trasformazione 1−Ochiai non è una metrica in generale."
    },
    hamming: {
      nome: "Distanza di Hamming normalizzata",
      tipoDati: "binary",
      formula: String.raw`d_H(x,y)=\frac{n_{10}+n_{01}}{p}`,
      interpretazione: "È la proporzione di coordinate nelle quali i due vettori hanno valori diversi.",
      dominio: dominioBinario,
      proprieta: "È una metrica. La divisione per p ne normalizza i valori nell’intervallo [0,1]."
    }
  };

  function leggiVettore(testo) {
    const normalizzato = String(testo).trim().replace(/;/g, " ");
    if (!normalizzato) throw new Error("Inserisci entrambi i vettori.");
    const parti = normalizzato.includes(",") ? normalizzato.split(",") : normalizzato.split(/\s+/);
    const valori = parti.filter(parte => parte.trim() !== "").map(parte => Number(parte.trim()));
    if (!valori.length || valori.some(valore => !Number.isFinite(valore))) {
      throw new Error("Usa soltanto numeri finiti separati da virgole, spazi o punti e virgola.");
    }
    return valori;
  }

  function validaVettori(x, y) {
    if (!Array.isArray(x) || !Array.isArray(y)) throw new TypeError("x e y devono essere vettori numerici.");
    if (x.length === 0 || y.length === 0) throw new Error("I vettori non possono essere vuoti.");
    if (x.length !== y.length) {
      throw new Error(`I vettori devono avere la stessa dimensione: x ne ha ${x.length}, y ne ha ${y.length}.`);
    }
    if ([...x, ...y].some(valore => !Number.isFinite(valore))) {
      throw new Error("Tutte le coordinate devono essere numeri finiti.");
    }
  }

  function validaBinari(x, y) {
    validaVettori(x, y);
    if ([...x, ...y].some(valore => valore !== 0 && valore !== 1)) {
      throw new Error("Per le misure binarie ogni coordinata deve essere uguale a 0 oppure 1.");
    }
  }

  function minkowski(x, y, q) {
    validaVettori(x, y);
    if (!Number.isFinite(q) || q < 1) {
      throw new Error("Per la distanza di Minkowski è necessario un parametro finito q ≥ 1.");
    }
    return Math.pow(x.reduce((somma, valore, j) => somma + Math.pow(Math.abs(valore - y[j]), q), 0), 1 / q);
  }

  function chebyshev(x, y) {
    validaVettori(x, y);
    return Math.max(...x.map((valore, j) => Math.abs(valore - y[j])));
  }

  function calcola(x, y, q) {
    validaVettori(x, y);
    if (q !== Infinity && (!Number.isFinite(q) || q < 1)) {
      throw new Error("Per la distanza di Minkowski è necessario q ≥ 1.");
    }
    const scarti = x.map((valore, j) => Math.abs(valore - y[j]));
    const contributi = q === Infinity ? scarti.slice() : scarti.map(scarto => Math.pow(scarto, q));
    const distanza = q === Infinity ? Math.max(...scarti) : Math.pow(contributi.reduce((a, b) => a + b, 0), 1 / q);
    return { scarti, contributi, distanza };
  }

  function conteggiBinari(x, y) {
    validaBinari(x, y);
    const conteggi = { n11: 0, n10: 0, n01: 0, n00: 0 };
    x.forEach((valore, j) => { conteggi[`n${valore}${y[j]}`] += 1; });
    return conteggi;
  }

  function calcolaBinaria(tipo, x, y) {
    if (!["jaccard", "dice", "ochiai", "hamming"].includes(tipo)) {
      throw new Error("Misura binaria non riconosciuta.");
    }
    const conteggi = conteggiBinari(x, y);
    const { n11, n10, n01 } = conteggi;
    let distanza;

    if (tipo === "jaccard") {
      const denominatore = n11 + n10 + n01;
      distanza = denominatore === 0 ? 0 : (n10 + n01) / denominatore;
    } else if (tipo === "dice") {
      const denominatore = 2 * n11 + n10 + n01;
      distanza = denominatore === 0 ? 0 : (n10 + n01) / denominatore;
    } else if (tipo === "ochiai") {
      const presenzeX = n11 + n10;
      const presenzeY = n11 + n01;
      if (presenzeX === 0 && presenzeY === 0) distanza = 0;
      else if (presenzeX === 0 || presenzeY === 0) distanza = 1;
      else distanza = 1 - n11 / Math.sqrt(presenzeX * presenzeY);
    } else {
      distanza = (n10 + n01) / x.length;
    }
    return { distanza, conteggi };
  }

  function formatta(numero) {
    if (Math.abs(numero) < 1e-12) return "0";
    return new Intl.NumberFormat("it-IT", { maximumFractionDigits: 6 }).format(numero);
  }

  return {
    definizioni, leggiVettore, validaVettori, validaBinari, minkowski,
    chebyshev, calcola, conteggiBinari, calcolaBinaria, formatta
  };
});
