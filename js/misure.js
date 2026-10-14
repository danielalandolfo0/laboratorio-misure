/*
 * Nucleo matematico dell'applicazione.
 *
 * Questo file non dipende dall'interfaccia grafica: le funzioni qui definite
 * possono essere verificate separatamente mediante i test automatici.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.Misure = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const definizioni = {
    euclidean: {
      nome: "Distanza euclidea",
      q: 2,
      formula: "d₂(x,y) = (Σ |xⱼ − yⱼ|²)¹⁄²",
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|².",
      interpretazione: "È la lunghezza del segmento che congiunge i due punti. Differenze grandi incidono quadraticamente."
    },
    manhattan: {
      nome: "Distanza di Manhattan",
      q: 1,
      formula: "d₁(x,y) = Σ |xⱼ − yⱼ|",
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|.",
      interpretazione: "Somma gli spostamenti lungo le coordinate, come un percorso composto da tratti paralleli agli assi."
    },
    chebyshev: {
      nome: "Distanza di Chebyshev",
      q: Infinity,
      formula: "d∞(x,y) = maxⱼ |xⱼ − yⱼ|",
      contributo: "Le barre mostrano |xⱼ − yⱼ|; conta soltanto il valore massimo.",
      interpretazione: "È determinata dalla coordinata nella quale i due vettori differiscono maggiormente."
    },
    minkowski: {
      nome: "Distanza di Minkowski",
      q: 3,
      formula: "d_q(x,y) = (Σ |xⱼ − yⱼ|^q)^(1/q)",
      contributo: "Ogni barra rappresenta |xⱼ − yⱼ|^q.",
      interpretazione: "Il parametro q controlla quanto le differenze più grandi dominano il risultato."
    }
  };

  function leggiVettore(testo) {
    const normalizzato = String(testo).trim().replace(/;/g, " ");
    if (!normalizzato) throw new Error("Inserisci entrambi i vettori.");

    const parti = normalizzato.includes(",")
      ? normalizzato.split(",")
      : normalizzato.split(/\s+/);

    const valori = parti
      .filter(parte => parte.trim() !== "")
      .map(parte => Number(parte.trim()));

    if (!valori.length || valori.some(valore => !Number.isFinite(valore))) {
      throw new Error("Usa soltanto numeri finiti separati da virgole, spazi o punti e virgola.");
    }
    return valori;
  }

  function validaVettori(x, y) {
    if (!Array.isArray(x) || !Array.isArray(y)) {
      throw new TypeError("x e y devono essere vettori numerici.");
    }
    if (x.length === 0 || y.length === 0) {
      throw new Error("I vettori non possono essere vuoti.");
    }
    if (x.length !== y.length) {
      throw new Error(`I vettori devono avere la stessa dimensione: x ne ha ${x.length}, y ne ha ${y.length}.`);
    }
    if ([...x, ...y].some(valore => !Number.isFinite(valore))) {
      throw new Error("Tutte le coordinate devono essere numeri finiti.");
    }
  }

  function minkowski(x, y, q) {
    validaVettori(x, y);
    if (!Number.isFinite(q) || q < 1) {
      throw new Error("Per la distanza di Minkowski è necessario un parametro finito q ≥ 1.");
    }
    return Math.pow(
      x.reduce((somma, valore, j) => somma + Math.pow(Math.abs(valore - y[j]), q), 0),
      1 / q
    );
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
    const contributi = q === Infinity
      ? scarti.slice()
      : scarti.map(scarto => Math.pow(scarto, q));
    const distanza = q === Infinity
      ? Math.max(...scarti)
      : Math.pow(contributi.reduce((a, b) => a + b, 0), 1 / q);

    return { scarti, contributi, distanza };
  }

  function formatta(numero) {
    if (Math.abs(numero) < 1e-12) return "0";
    return new Intl.NumberFormat("it-IT", { maximumFractionDigits: 6 }).format(numero);
  }

  return {
    definizioni,
    leggiVettore,
    validaVettori,
    minkowski,
    chebyshev,
    calcola,
    formatta
  };
});
