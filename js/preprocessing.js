/* Analisi e riscalamento di tabelle CSV, indipendenti dall'interfaccia. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.Preprocessing = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const MANCANTI = new Set(["", "na", "n/a", "null", "?"]);

  function rigaIniziale(testo) {
    let dentroVirgolette = false;
    let riga = "";
    for (let i = 0; i < testo.length; i += 1) {
      const c = testo[i];
      if (c === '"') {
        if (dentroVirgolette && testo[i + 1] === '"') { riga += '""'; i += 1; continue; }
        dentroVirgolette = !dentroVirgolette;
      }
      if (!dentroVirgolette && (c === "\n" || c === "\r")) break;
      riga += c;
    }
    return riga;
  }

  function contaSeparatore(riga, separatore) {
    let dentroVirgolette = false;
    let conteggio = 0;
    for (let i = 0; i < riga.length; i += 1) {
      if (riga[i] === '"') {
        if (dentroVirgolette && riga[i + 1] === '"') { i += 1; continue; }
        dentroVirgolette = !dentroVirgolette;
      } else if (!dentroVirgolette && riga[i] === separatore) conteggio += 1;
    }
    return conteggio;
  }

  function rilevaSeparatore(testo) {
    const prima = rigaIniziale(testo.replace(/^\uFEFF/, ""));
    const candidati = [",", ";", "\t"].map(separatore => ({ separatore, n: contaSeparatore(prima, separatore) }));
    candidati.sort((a, b) => b.n - a.n);
    if (candidati[0].n === 0) throw new Error("Non riesco a individuare il separatore del CSV. Usa virgola, punto e virgola oppure tabulazione.");
    return candidati[0].separatore;
  }

  function separaCsv(testo, separatore) {
    const righe = [];
    let riga = [], campo = "", dentroVirgolette = false;
    const chiudiCampo = () => { riga.push(campo.trim()); campo = ""; };
    const chiudiRiga = () => {
      chiudiCampo();
      if (riga.some(valore => valore !== "")) righe.push(riga);
      riga = [];
    };

    for (let i = 0; i < testo.length; i += 1) {
      const c = testo[i];
      if (c === '"') {
        if (dentroVirgolette && testo[i + 1] === '"') { campo += '"'; i += 1; }
        else dentroVirgolette = !dentroVirgolette;
      } else if (!dentroVirgolette && c === separatore) chiudiCampo();
      else if (!dentroVirgolette && (c === "\n" || c === "\r")) {
        if (c === "\r" && testo[i + 1] === "\n") i += 1;
        chiudiRiga();
      } else campo += c;
    }
    if (dentroVirgolette) throw new Error("Il CSV contiene un campo tra virgolette non chiuso.");
    if (campo !== "" || riga.length > 0) chiudiRiga();
    return righe;
  }

  function leggiCsv(testo) {
    if (typeof testo !== "string" || !testo.trim()) throw new Error("Il file CSV è vuoto.");
    const pulito = testo.replace(/^\uFEFF/, "");
    const separatore = rilevaSeparatore(pulito);
    const righe = separaCsv(pulito, separatore);
    if (righe.length < 2) throw new Error("Il CSV deve contenere un'intestazione e almeno una riga di dati.");
    const intestazioni = righe[0].map(x => x.trim());
    if (intestazioni.some(x => !x)) throw new Error("Tutte le colonne devono avere un titolo.");
    const normalizzate = intestazioni.map(x => x.toLocaleLowerCase("it-IT"));
    if (new Set(normalizzate).size !== normalizzate.length) throw new Error("I titoli delle colonne devono essere univoci.");
    const dati = righe.slice(1);
    dati.forEach((riga, i) => {
      if (riga.length !== intestazioni.length) {
        throw new Error(`La riga ${i + 2} contiene ${riga.length} campi anziché ${intestazioni.length}.`);
      }
    });
    if (dati.length * intestazioni.length > 2000000) throw new Error("La tabella supera il limite iniziale di 2.000.000 di celle.");
    return { intestazioni, righe: dati, separatore };
  }

  function mancante(valore) {
    return valore === null || valore === undefined || MANCANTI.has(String(valore).trim().toLocaleLowerCase("it-IT"));
  }

  function leggiNumero(valore, separatore = ",") {
    if (mancante(valore)) return null;
    let testo = String(valore).trim();
    const conPunto = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
    const conVirgola = /^[+-]?(?:\d+(?:,\d*)?|,\d+)(?:[eE][+-]?\d+)?$/;
    if (conPunto.test(testo)) return Number(testo);
    if (separatore !== "," && conVirgola.test(testo)) return Number(testo.replace(",", "."));
    return undefined;
  }

  function quantile(ordinati, p) {
    if (!ordinati.length) return null;
    const posizione = (ordinati.length - 1) * p;
    const sotto = Math.floor(posizione), sopra = Math.ceil(posizione);
    if (sotto === sopra) return ordinati[sotto];
    return ordinati[sotto] + (ordinati[sopra] - ordinati[sotto]) * (posizione - sotto);
  }

  function statistiche(valori) {
    const ordinati = valori.slice().sort((a, b) => a - b);
    const media = valori.reduce((a, b) => a + b, 0) / valori.length;
    const varianza = valori.reduce((somma, valore) => somma + (valore - media) ** 2, 0) / valori.length;
    const deviazione = Math.sqrt(varianza);
    const mediana = quantile(ordinati, .5);
    const q1 = quantile(ordinati, .25), q3 = quantile(ordinati, .75);
    const iqr = q3 - q1;
    const minimoTukey = q1 - 1.5 * iqr, massimoTukey = q3 + 1.5 * iqr;
    const estremi = valori.filter(v => v < minimoTukey || v > massimoTukey).length;
    const zeri = valori.filter(v => v === 0).length;
    const massimoAssoluto = Math.max(...valori.map(Math.abs));
    return {
      media, deviazione, mediana, q1, q3, iqr,
      minimo: ordinati[0], massimo: ordinati[ordinati.length - 1],
      massimoAssoluto, estremi, quotaEstremi: estremi / valori.length,
      zeri, quotaZeri: zeri / valori.length
    };
  }

  function descriviOutlier(stats) {
    if (stats.estremi === 1) return "È presente un solo outlier.";
    if (stats.quotaEstremi <= .1) return "Sono presenti pochi outlier.";
    return "Sono presenti molti outlier.";
  }

  function analizzaColonna(nome, valori, separatore) {
    const convertiti = valori.map(v => leggiNumero(v, separatore));
    const osservati = convertiti.filter(v => v !== null);
    const tuttiNumerici = osservati.length > 0 && osservati.every(v => v !== undefined && Number.isFinite(v));
    const mancanti = convertiti.filter(v => v === null).length;
    if (!tuttiNumerici) {
      return { nome, tipo: "non_numerica", metodo: "nessuno", mancanti, motivo: "Sono presenti valori non numerici." };
    }

    const numeri = osservati;
    const unici = [...new Set(numeri)];
    if (unici.every(v => v === 0 || v === 1)) {
      return { nome, tipo: "binaria", metodo: "nessuno", mancanti, motivo: "Sono presenti soltanto 0 e 1.", valoriNumerici: convertiti };
    }

    const stats = statistiche(numeri);
    if (stats.deviazione === 0) {
      return { nome, tipo: "numerica_costante", metodo: "costante", mancanti, motivo: "Tutti i valori sono uguali.", statistiche: stats, valoriNumerici: convertiti };
    }

    const robusto = stats.quotaEstremi > .01 && stats.iqr > 0;
    const maxabs = !robusto && stats.quotaZeri >= .8 && stats.massimoAssoluto > 0;
    const metodo = robusto ? "robusto" : maxabs ? "maxabs" : "zscore";
    const motivo = robusto
      ? descriviOutlier(stats)
      : maxabs
        ? "Molti valori sono uguali a zero."
      : stats.iqr === 0
        ? "I valori sono concentrati su pochi livelli."
        : "Non emergono outlier rilevanti.";
    return { nome, tipo: "numerica", metodo, mancanti, motivo, statistiche: stats, valoriNumerici: convertiti };
  }

  function personalizzaColonna(nome, valori, separatore, scelta = {}) {
    const automatica = analizzaColonna(nome, valori, separatore);
    const tipoScelto = scelta.tipo || "auto";
    const metodoScelto = scelta.metodo || "auto";
    if (tipoScelto === "auto" && metodoScelto === "auto") {
      return { ...automatica, tipoRilevato: automatica.tipo, metodoAutomatico: automatica.metodo, sceltaTipo: "auto", sceltaMetodo: "auto" };
    }

    const tipo = tipoScelto === "auto" ? automatica.tipo : tipoScelto;
    const convertiti = valori.map(v => leggiNumero(v, separatore));
    const osservati = convertiti.filter(v => v !== null);
    const mancanti = convertiti.filter(v => v === null).length;
    const numericiValidi = osservati.length > 0 && osservati.every(v => v !== undefined && Number.isFinite(v));
    let analisi;
    let metodoAutomaticoEffettivo = automatica.metodo;

    if (tipo === "non_numerica") {
      metodoAutomaticoEffettivo = "nessuno";
      analisi = { nome, tipo, metodo: "nessuno", mancanti, motivo: "I valori restano invariati." };
    } else {
      if (!numericiValidi) throw new Error(`La feature “${nome}” contiene valori non numerici e non può essere trattata come ${tipo === "binaria" ? "binaria" : "numerica"}.`);
      const numeri = osservati;
      if (tipo === "binaria") {
        if (!numeri.every(v => v === 0 || v === 1)) throw new Error(`La feature “${nome}” non è binaria: sono ammessi soltanto 0, 1 e valori mancanti.`);
        metodoAutomaticoEffettivo = "nessuno";
        analisi = { nome, tipo, metodo: "nessuno", mancanti, motivo: "Sono presenti soltanto 0 e 1.", valoriNumerici: convertiti };
      } else {
        const stats = statistiche(numeri);
        const haEstremi = stats.quotaEstremi > .01 && stats.iqr > 0;
        const sparsa = !haEstremi && stats.quotaZeri >= .8 && stats.massimoAssoluto > 0;
        const automatico = stats.deviazione === 0 ? "costante" : haEstremi ? "robusto" : sparsa ? "maxabs" : "zscore";
        metodoAutomaticoEffettivo = automatico;
        const metodo = metodoScelto === "auto" ? automatico : metodoScelto;
        if (metodo === "zscore" && stats.deviazione === 0) throw new Error(`La feature “${nome}” è costante: lo z-score richiede una deviazione standard positiva.`);
        if (metodo === "robusto" && stats.iqr === 0) throw new Error(`La feature “${nome}” ha IQR nullo: la scala robusta non è definita.`);
        if (metodo === "minmax" && stats.massimo === stats.minimo) throw new Error(`La feature “${nome}” è costante: min–max richiede massimo e minimo differenti.`);
        if (metodo === "maxabs" && stats.massimoAssoluto === 0) throw new Error(`La feature “${nome}” contiene soltanto zeri: max-abs richiede un massimo assoluto positivo.`);
        const motivi = {
          zscore: metodoScelto === "auto" ? "Non emergono outlier rilevanti." : "Le differenze vengono riportate su una scala comune.",
          robusto: metodoScelto === "auto" ? descriviOutlier(stats) : "Viene ridotto il peso degli outlier.",
          maxabs: metodoScelto === "auto" ? "Molti valori sono uguali a zero." : "Gli zeri restano invariati.",
          minmax: "I valori vengono riportati tra 0 e 1.",
          costante: "Tutti i valori sono uguali.",
          nessuno: "I valori restano invariati."
        };
        analisi = { nome, tipo: stats.deviazione === 0 && metodo === "costante" ? "numerica_costante" : "numerica", metodo, mancanti, motivo: motivi[metodo], statistiche: stats, valoriNumerici: convertiti };
      }
    }
    return { ...analisi, tipoRilevato: automatica.tipo, metodoAutomatico: metodoAutomaticoEffettivo, sceltaTipo: tipoScelto, sceltaMetodo: metodoScelto };
  }

  function trasformaValore(valore, analisi) {
    if (analisi.tipo === "non_numerica") return mancante(valore) ? null : valore;
    const numero = leggiNumero(valore, analisi.separatore);
    if (numero === null) return null;
    if (analisi.tipo === "binaria") return numero;
    if (analisi.metodo === "nessuno") return numero;
    if (analisi.metodo === "costante") return 0;
    if (analisi.metodo === "robusto") return (numero - analisi.statistiche.mediana) / analisi.statistiche.iqr;
    if (analisi.metodo === "minmax") return (numero - analisi.statistiche.minimo) / (analisi.statistiche.massimo - analisi.statistiche.minimo);
    if (analisi.metodo === "maxabs") return numero / analisi.statistiche.massimoAssoluto;
    return (numero - analisi.statistiche.media) / analisi.statistiche.deviazione;
  }

  function applicaConfrontoGlobale(colonne) {
    const numeriche = colonne.filter(c => c.tipo === "numerica" && c.statistiche && c.statistiche.deviazione > 0);
    if (!numeriche.length) return;

    const scale = numeriche.map(c => c.statistiche.iqr > 0 ? c.statistiche.iqr : c.statistiche.deviazione);
    const rapporto = numeriche.length === 1 ? 1 : Math.max(...scale) / Math.min(...scale);
    const confrontabili = rapporto <= 2;

    numeriche.forEach(colonna => {
      if (colonna.metodoAutomatico !== "zscore") return;
      colonna.metodoAutomatico = confrontabili ? "nessuno" : "zscore";
      if (colonna.sceltaMetodo !== "auto") return;
      colonna.metodo = colonna.metodoAutomatico;
      colonna.motivo = confrontabili
        ? numeriche.length === 1
          ? "Non ci sono altre feature numeriche con cui bilanciare la scala."
          : "Le feature numeriche hanno dispersioni simili."
        : "Le feature numeriche hanno dispersioni molto diverse.";
    });
  }

  function preparaTabella(tabella, scelte = []) {
    const colonne = tabella.intestazioni.map((nome, j) => {
      const analisi = personalizzaColonna(nome, tabella.righe.map(riga => riga[j]), tabella.separatore, scelte[j]);
      analisi.separatore = tabella.separatore;
      return analisi;
    });
    applicaConfrontoGlobale(colonne);
    const trasformate = tabella.righe.map(riga => riga.map((valore, j) => trasformaValore(valore, colonne[j])));
    const riepilogo = {
      istanze: tabella.righe.length,
      feature: tabella.intestazioni.length,
      numeriche: colonne.filter(c => c.tipo === "numerica" || c.tipo === "numerica_costante").length,
      binarie: colonne.filter(c => c.tipo === "binaria").length,
      nonNumeriche: colonne.filter(c => c.tipo === "non_numerica").length,
      mancanti: colonne.reduce((somma, c) => somma + c.mancanti, 0)
    };
    return { originale: tabella, colonne, trasformate, riepilogo };
  }

  function valoreCsv(valore) {
    if (valore === null || valore === undefined) return "";
    if (typeof valore === "number") {
      const pulito = Math.abs(valore) < 1e-14 ? 0 : valore;
      return Number(pulito.toPrecision(12)).toString();
    }
    const testo = String(valore);
    return /[",\r\n]/.test(testo) ? `"${testo.replaceAll('"', '""')}"` : testo;
  }

  function creaCsv(intestazioni, righe) {
    return [intestazioni, ...righe].map(riga => riga.map(valoreCsv).join(",")).join("\n");
  }

  return { rilevaSeparatore, leggiCsv, leggiNumero, quantile, statistiche, analizzaColonna, personalizzaColonna, applicaConfrontoGlobale, preparaTabella, creaCsv, mancante };
});
