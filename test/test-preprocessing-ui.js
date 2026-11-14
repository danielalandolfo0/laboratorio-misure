"use strict";

// Collaudo DOM senza librerie esterne: riproduce eventi, stati e risposte
// asincrone del motore. Non sostituisce un test con un browser reale.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((ok, ko) => { resolve = ok; reject = ko; });
  return { promise, resolve, reject };
}
async function flush() {
  for (let i = 0; i < 6; ++i) await new Promise(setImmediate);
}

function createHarness() {
  const dom = new Map();
  class Element {
    constructor(id) {
      this.id = id;
      this.listeners = new Map();
      this.innerHTML = "";
      this.textContent = "";
      this.hidden = true;
      this.disabled = false;
      this.value = "";
      this.style = {};
      this.dataset = {};
      this.classList = {
        add() {}, remove() {}, toggle() {}
      };
    }
    addEventListener(name, fn) {
      if (!this.listeners.has(name)) this.listeners.set(name, []);
      this.listeners.get(name).push(fn);
    }
    dispatch(name, target = this) {
      for (const fn of (this.listeners.get(name) || [])) {
        fn({ target, preventDefault() {}, dataTransfer: {files: []} });
      }
    }
    appendChild() {}
    append() {}
    click() {}
    remove() {}
    setAttribute() {}
    getAttribute() { return "false"; }
    querySelector() { return null; }
    querySelectorAll() { return []; }
    get outerHTML() { return '<div></div>'; }
  }
  const element = id => {
    if (!dom.has(id)) dom.set(id, new Element(id));
    return dom.get(id);
  };
  const document = {
    getElementById: element,
    createElement: name => new Element(name),
    createTextNode: text => ({textContent: text}),
    body: new Element("body")
  };
  element("load-example-csv").textContent = "Carica l'esempio";
  element("calculate-gower").textContent = "Calcola la matrice";
  element("prepare-comparison-plan").textContent = "Prepara il piano";

  const observations = {
    planCalls: [],
    matrixCalls: [],
    tableCalls: [],
    planIntercept: null,
    matrixIntercept: null,
    tableIntercept: null,
  };
  function makeTable(text, choices = []) {
    const lines = text.trim().split(/\r?\n/);
    const names = lines[0].split(",");
    const data = lines.slice(1).map(line => line.split(","));
    const numerical = n => n !== "categoria" && n !== "livello" &&
      n !== "codice" && n !== "etichette" && n !== "id" && n !== "gruppo" && n !== "presente";
    const colonne = names.map((nome, i) => {
      const tipo = /^flag[12]$/.test(nome) ? "binaria" :
        numerical(nome) ? "numerica" : "non_numerica";
      const valori = data.map(r => Number(r[i])).filter(Number.isFinite);
      const method = choices[i]?.metodo || "auto";
      return {
        nome, tipo, tipoRilevato: tipo,
        sceltaTipo: choices[i]?.tipo || "auto",
        sceltaMetodo: method,
        metodo: method === "auto" ? "zscore" : method,
        metodoAutomatico: "zscore",
        motivo: "Proposta preliminare",
        mancanti: 0,
        statistiche: {
          minimo: valori.length ? Math.min(...valori) : 0,
          massimo: valori.length ? Math.max(...valori) : 1,
          media: 0, deviazione: 1, mediana: 0, iqr: 1,
          massimoAssoluto: 1, estremi: 0, numeroOsservati: data.length
        }
      };
    });
    return {
      originale: {intestazioni: names, righe: data},
      trasformate: data,
      colonne,
      questionario: {
        colonne: names.map((nome, i) => ({
          nome, ruoloSuggerito: nome === "id" ? "identificativo" :
            /^flag[12]$/.test(nome) ? "presenza" :
            nome === "livello" ? "livello" :
            nome === "categoria" || nome === "gruppo" ? "categoria" :
            nome === "codice" ? "testo" :
            nome === "etichette" ? "categoria" : "quantita",
          usaNelConfronto: nome !== "id"
        }))
      },
      riepilogo: {istanze: data.length, feature: names.length}
    };
  }
  function makePlan() {
    return {
      completo: true,
      conteggioPercorsi: 1,
      diagnosi: null,
      avvisi: [],
      blocchi: [],
      percorsi: [{
        idPercorso: "percorso-1", tipo: "gower", titolo: "Categorie",
        colonne: ["categoria"], metodo: "Dissimilarità di Gower classica",
        motivo: "Confronto delle categorie", stato: "pronto",
        preelaborazione: {
          origine: "valori_originali", etichettaOrigine: "Originali",
          usaTabellaTrasformata: false, passi: [], descrizione: "Nessuna"
        },
        compatibilitaPreelaborazione: {},
        mancanti: {pronta: true, descrizione: "Nessun mancante", colonne: []},
        calcolo: {disponibile: true, descrizione: "Calcolabile"},
        pesoAggregazione: 1, normalizzazione: {
          metodo: "teorica", limiteTeorico: 1, descrizione: "Limite teorico"
        },
        avvisi: []
      }]
    };
  }
  function makeMatrix() {
    return {
      metodo: "Gower", colonne: ["categoria"],
      etichette: ["Riga 1", "Riga 2"], matrice: [[0, 1], [1, 0]],
      nota: "Confronto confermato", csv: "Riga;Riga 1;Riga 2\n",
      diagnosticaFinale: {avvisi: []}
    };
  }
  const preprocessing = {
    ready: Promise.resolve(),
    preparaTabella: (text, choices = []) => {
      observations.tableCalls.push({text, choices});
      return observations.tableIntercept?.(text, choices) ||
        Promise.resolve(makeTable(text, choices));
    },
    analizzaDiagnosi: async () => ({
      diagnosi: {
        colonneAsimmetriche: [], diagnosiMultivariata: {},
        dispersioniSimili: true, rapportoDispersioni: 1,
        relazioniCoppie: [], motivoCovarianza: ""
      },
      colonne: [], gruppiSuggeriti: []
    }),
    creaPiano: (text, choices, interpretazione) => {
      observations.planCalls.push({text, choices, interpretazione});
      return observations.planIntercept?.(text, choices, interpretazione) ||
        Promise.resolve(makePlan());
    },
    calcolaMatrice: (text, choices, interpretazione) => {
      observations.matrixCalls.push({text, choices, interpretazione});
      return observations.matrixIntercept?.(text, choices, interpretazione) ||
        Promise.resolve(makeMatrix());
    },
    creaCsv: async () => "csv"
  };

  const source = fs.readFileSync("js/preprocessing-ui.js", "utf8");
  vm.runInNewContext(source, {
    window: {Preprocessing: preprocessing},
    document, URL: {createObjectURL: () => "blob:mock", revokeObjectURL() {}},
    Blob, Intl, Number, Math, Set, JSON, console, Array, Promise
  }, {filename: "js/preprocessing-ui.js"});

  function fire(id, event, opts = {}) {
    let target = opts.target || element(id);
    if (opts.value !== undefined) target.value = opts.value;
    element(id).dispatch(event, target);
  }
  function customTarget(selector, dataset, value) {
    return {
      dataset, value,
      matches: s => s.split(",").map(x => x.trim()).includes(selector),
      closest: () => null
    };
  }
  return {fire, element, observations, makeTable, makePlan, makeMatrix, customTarget};
}

async function testGuida() {
  const h=createHarness();
  h.fire("load-example-csv","click");
  await flush();
  assert.match(h.element("comparison-guide-phase").textContent,/Indica che cosa rappresenta una riga/);
  h.fire("row-meaning","change",{value:"oggetto"});
  assert.doesNotMatch(h.element("comparison-guide-phase").textContent,/Indica che cosa rappresenta una riga/);
}

async function testStaleFiles() {
  const h = createHarness();
  const prima = deferred();
  h.observations.tableIntercept = text => (
    text.includes("PRIMA") ? prima.promise : null
  );
  const file = (name, data) => ({
    name, size: data.length, type: "text/csv",
    text: async () => data
  });
  h.fire("csv-file", "change", {target: {files: [
    file("prima.csv", "categoria,id\nPRIMA,1\nblu,2")
  ]}});
  await flush();
  h.fire("csv-file", "change", {target: {files: [
    file("seconda.csv", "categoria,id\nSECONDA,1\nverde,2")
  ]}});
  await flush();
  assert.equal(h.element("csv-file-name").textContent, "seconda.csv");
  prima.resolve(h.makeTable("categoria,id\nPRIMA,1\nblu,2"));
  await flush();
  assert.equal(h.element("csv-file-name").textContent, "seconda.csv",
    "Un caricamento obsoleto non deve ripristinare il CSV precedente.");
  assert.equal(h.element("csv-output").hidden, false);
}

async function testStaleFileRead() {
  const h = createHarness();
  const lettura = deferred();
  h.fire("csv-file", "change", {target: {files: [{
    name: "lento.csv", type: "text/csv", size: 50,
    text: () => lettura.promise
  }]}});
  h.fire("csv-file", "change", {target: {files: [{
    name: "veloce.csv", type: "text/csv", size: 50,
    text: async () => "categoria,id\nrapido,1\naltro,2"
  }]}});
  await flush();
  lettura.resolve("categoria,id\nritardo,1\naltro,2");
  await flush();
  assert.equal(h.element("csv-file-name").textContent, "veloce.csv",
    "La lettura lenta del file precedente non deve sovrascrivere quella nuova.");
}

async function testStalePlanAndMatrix() {
  const h = createHarness();
  h.fire("load-example-csv", "click");
  await flush();
  const richiestaPiano = deferred();
  h.observations.planIntercept = () => richiestaPiano.promise;
  h.fire("prepare-comparison-plan", "click");
  assert.equal(h.element("comparison-plan").hidden, true);
  h.fire("row-meaning", "change", {value: "persona"});
  assert.equal(h.element("prepare-comparison-plan").disabled, false,
    "Dopo la modifica deve essere possibile preparare un nuovo piano.");
  richiestaPiano.resolve(h.makePlan());
  await flush();
  assert.equal(h.element("comparison-plan").hidden, true,
    "Una risposta precedente non deve riaprire il piano dopo una modifica.");

  h.observations.planIntercept = null;
  h.fire("prepare-comparison-plan", "click");
  await flush();
  assert.equal(h.element("comparison-plan").hidden, false);
  const richiestaMatrice = deferred();
  h.observations.matrixIntercept = () => richiestaMatrice.promise;
  h.fire("calculate-gower", "click");
  h.fire("row-meaning", "change", {value: "evento"});
  assert.equal(h.element("calculate-gower").disabled, false,
    "Il pulsante di calcolo va ripristinato quando il piano viene invalidato.");
  richiestaMatrice.resolve(h.makeMatrix());
  await flush();
  assert.equal(h.element("gower-result").hidden, true,
    "Una matrice obsoleta non deve comparire dopo modifiche al piano.");
  assert.equal(h.element("comparison-plan").hidden, true);
}

async function testNewestPlanAndFailures() {
  const h = createHarness();
  h.fire("load-example-csv", "click");
  await flush();
  const old = deferred();
  const next = deferred();
  let count = 0;
  h.observations.planIntercept = () => ++count === 1 ? old.promise : next.promise;
  h.fire("prepare-comparison-plan", "click");
  h.fire("prepare-comparison-plan", "click");
  next.resolve(h.makePlan());
  await flush();
  assert.equal(h.element("comparison-plan").hidden, false);
  old.reject(Error("Errore obsoleto"));
  await flush();
  assert.notEqual(h.element("csv-error").textContent, "Errore obsoleto",
    "L'errore di un calcolo superato non deve coprire la nuova risposta.");
  assert.equal(h.element("comparison-plan").hidden, false);
}

async function testLatestColumnChoice() {
  const h = createHarness();
  const file = {
    name: "quantita.csv", type: "text/csv", size: 60,
    text: async () => "x,y,id\n1,2,a\n2,3,b\n3,4,c"
  };
  h.fire("csv-file", "change", {target: {files: [file]}});
  await flush();
  const old = deferred();
  const next = deferred();
  let count = 0;
  h.observations.tableIntercept = (text, choices) => ++count === 1
    ? old.promise : next.promise;
  const select = (method) => h.customTarget(
    ".column-choice", {column: "0", choice: "metodo"}, method
  );
  h.fire("scaling-body", "change", {target: select("zscore")});
  h.fire("scaling-body", "change", {target: select("robusto")});
  next.resolve(h.makeTable("x,y,id\n1,2,a\n2,3,b\n3,4,c",
    [{tipo: "auto", metodo: "robusto"}]));
  await flush();
  old.resolve(h.makeTable("x,y,id\n1,2,a\n2,3,b\n3,4,c",
    [{tipo: "auto", metodo: "zscore"}]));
  await flush();
  assert.match(h.element("scaling-body").innerHTML, /value="robusto" selected/,
    "Una preparazione precedente non deve sovrascrivere la scelta più recente.");
}

async function testNominalSettingsPropagation() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "categorie.csv", type: "text/csv", size: 75,
    text: async () => "categoria,livello,id\nrosso,basso,a\nblu,medio,b\nverde,alto,c"
  }]}});
  await flush();
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-gower-key="modalitaCategorieGower"/);
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".gower-setting",
    {gowerKey: "modalitaCategorieGower", gowerColumn: "categoria"},
    "personalizzata"
  )});
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-gower-nominal-column="categoria"/);
  const livelli = ["blu", "rosso", "verde"];
  const inputs = [
    {dataset: {gowerPair: "0:1"}, value: "0,4"},
    {dataset: {gowerPair: "0:2"}, value: "0,8"},
    {dataset: {gowerPair: "1:2"}, value: "0,6"}
  ];
  const target = h.customTarget(".gower-nominal-pair", {
    gowerNominalColumn: "categoria",
    gowerLevels: JSON.stringify(livelli),
    gowerPair: "0:1"
  }, "0,4");
  target.closest = () => ({querySelectorAll: () => inputs});
  h.fire("adaptive-questions", "input", {target});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  const last = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(last.modalitaCategorieGower.categoria, "personalizzata");
  assert.equal(last.dissimilaritaCategorieGower.categoria.coppie["1:2"], "0,6");
  assert.deepEqual(Array.from(last.dissimilaritaCategorieGower.categoria.livelli), livelli);
}

async function testGruppoTemporaleConferme() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "tempo.csv", type: "text/csv", size: 100,
    text: async () => "t1,t2,t3,id\n1,2,3,A\n4,5,6,B\n2,3,4,C"
  }]}});
  await flush();
  h.fire("add-column-group", "click");
  for (const nome of ["t1", "t2", "t3"]) {
    h.fire("group-assignment-body", "change", {target: h.customTarget(
      ".group-assignment", {groupColumn: nome}, "gruppo-1"
    )});
  }
  const tipo = h.customTarget(".group-type", {}, "tempo");
  tipo.closest = () => ({dataset: {groupId: "gruppo-1"}});
  h.fire("group-config-list", "change", {target: tipo});
  assert.match(h.element("adaptive-questions").innerHTML,
    /class="temporal-order-input"/);
  assert.match(h.element("adaptive-questions").innerHTML,
    /class="temporal-spacing-select"/);

  h.fire("adaptive-questions", "input", {target: h.customTarget(
    ".temporal-order-input", {groupId: "gruppo-1"}, "t3; t2; t1"
  )});
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".temporal-spacing-select", {groupId: "gruppo-1"}, "regolare"
  )});
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "ritardo-gruppo-1"}, "si"
  )});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  const prima = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(prima.ordiniTemporaliGruppi["gruppo-1"], "t3; t2; t1");
  assert.equal(prima.campionamentiTemporaliGruppi["gruppo-1"], "regolare");
  assert.equal(prima["ritardo-gruppo-1"], "si");

  // La struttura cambia: la vecchia conferma dell'ordine non è riusabile.
  h.fire("group-assignment-body", "change", {target: h.customTarget(
    ".group-assignment", {groupColumn: "t3"}, ""
  )});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  const nuova = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(nuova.ordiniTemporaliGruppi?.["gruppo-1"], undefined);
  assert.equal(nuova.campionamentiTemporaliGruppi?.["gruppo-1"], undefined);
}

async function testRiscalamentoNumericoInTabellaMista() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "misto.csv", type: "text/csv", size: 120,
    text: async () =>
      "categoria,c1,c2,id\nrosso,1,10,A\nblu,2,20,B\nverde,3,30,C"
  }]}});
  await flush();
  // La categoria resta inclusa: non tutte le colonne hanno ruolo
  // quantitativo, ma c1 e c2 costituiscono due variabili numeriche.
  assert.equal(h.element("scaling-wrap").hidden, false,
    "La presenza di categorie non deve nascondere il riscalamento numerico.");
  assert.equal(h.element("prepare-comparison-plan").hidden, true,
    "Prima del piano le due colonne richiedono una conferma.");
  assert.match(h.element("scaling-body").innerHTML, /c1/);
  assert.match(h.element("scaling-body").innerHTML, /c2/);
  assert.match(h.element("adaptive-questions").innerHTML, /id="gestioneQuantitativeMiste"/);
  assert.doesNotMatch(h.element("adaptive-questions").innerHTML, /id="confrontoQuantitativo"/);
  h.fire("confirm-numeric-scaling", "click");
  assert.equal(h.element("prepare-comparison-plan").hidden, false);
  assert.equal(h.element("view-work").disabled, false);
  assert.match(h.element("preview-head").innerHTML, /c1/);
  assert.doesNotMatch(h.element("preview-head").innerHTML, /categoria/);
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "gestioneQuantitativeMiste"}, "separato"
  )});
  assert.match(h.element("adaptive-questions").innerHTML, /id="confrontoQuantitativo"/);
  assert.match(h.element("adaptive-questions").innerHTML, /data-gower-key="modalitaCategorieGower"/);
  assert.doesNotMatch(h.element("adaptive-questions").innerHTML,
    /data-gower-key="pesiGower" data-gower-column="c1"/);
  h.fire("prepare-comparison-plan", "click");
  await flush();
  assert.equal(h.observations.planCalls.at(-1).interpretazione.gestioneQuantitativeMiste, "separato");
  assert.equal(h.observations.planCalls.at(-1).interpretazione.riscalamentoConfermato, true,
    "La conferma deve arrivare realmente al motore di confronto.");
}

async function testMahalanobisAvanzata() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "singolare.csv", type: "text/csv", size: 100,
    text: async () => "x,y,id\n0,0,A\n1,2,B\n2,4,C"
  }]}});
  await flush();
  const piano = h.makePlan();
  Object.assign(piano.percorsi[0], {
    tipo: "numerico", idMisura: "mahalanobis_ridge",
    metodo: "Mahalanobis con covarianza regolarizzata",
    proprieta: "Metrica per S + λI definita positiva",
    diagnosiAutomatica: {covarianzaSingolare: true, campioneLimitato: true},
    parametri: {}
  });
  h.observations.planIntercept = () => Promise.resolve(piano);
  h.fire("prepare-comparison-plan", "click");
  await flush();
  assert.match(h.element("comparison-plan-paths").innerHTML, /value="mahalanobis_ridge"/);
  assert.match(h.element("comparison-plan-paths").innerHTML, /value="mahalanobis_pinv"/);
  const selezione = {id:"numeric-measure-choice", value:"mahalanobis_ridge",
    matches:()=>false};
  h.fire("comparison-plan-paths", "change", {target: selezione});
  await flush();
  assert.match(h.element("comparison-plan-paths").innerHTML, /id="numeric-measure-lambda"/);
  h.element("numeric-measure-choice").value = "mahalanobis_ridge";
  h.element("numeric-measure-lambda").value = "0.5";
  h.fire("comparison-plan-paths", "click", {target: {id:"apply-numeric-measure"}});
  await flush();
  assert.equal(h.observations.planCalls.at(-1).interpretazione.lambdaMahalanobis, "0.5");
  const pinv = {id:"numeric-measure-choice", value:"mahalanobis_pinv",
    matches:()=>false};
  h.fire("comparison-plan-paths", "change", {target: pinv});
  await flush();
  assert.match(h.element("comparison-plan-paths").innerHTML, /id="numeric-measure-tolerance"/);
  h.element("numeric-measure-choice").value = "mahalanobis_pinv";
  h.element("numeric-measure-tolerance").value = "1e-10";
  h.fire("comparison-plan-paths", "click", {target: {id:"apply-numeric-measure"}});
  await flush();
  const scelta = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(scelta.misuraNumericaManuale, "mahalanobis_pinv");
  assert.equal(scelta.tolleranzaPseudoinversa, "1e-10");
}

async function testGruppoBinarioESceltaTestuale() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "flag.csv", type: "text/csv", size: 90,
    text: async () => "flag1,flag2,categoria,id\n1,1,x,A\n1,0,x,B\n0,1,y,C"
  }]}});
  await flush();
  h.fire("add-column-group", "click");
  for (const nome of ["flag1", "flag2"]) {
    h.fire("group-assignment-body", "change", {target: h.customTarget(
      ".group-assignment", {groupColumn: nome}, "gruppo-1"
    )});
  }
  assert.match(h.element("group-config-list").innerHTML, /value="vettore_binario"/);
  const tipo = h.customTarget(".group-type", {}, "vettore_binario");
  tipo.closest = () => ({dataset: {groupId: "gruppo-1"}});
  h.fire("group-config-list", "change", {target: tipo});
  const html = h.element("adaptive-questions").innerHTML;
  assert.match(html, /id="misuraBinaria-gruppo-1"/);
  assert.match(html, /value="rogers_tanimoto"/);
  assert.match(html, /value="dice"/);
  assert.match(html, /value="jaccard"/);
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "misuraBinaria-gruppo-1"}, "dice"
  )});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  assert.equal(h.observations.planCalls.at(-1).interpretazione["misuraBinaria-gruppo-1"], "dice");
  assert.equal(h.observations.planCalls.at(-1).interpretazione.assegnazioni.flag1, "gruppo-1");
  assert.equal(h.observations.planCalls.at(-1).interpretazione.assegnazioni.flag2, "gruppo-1");

  const t = createHarness();
  t.fire("csv-file", "change", {target: {files: [{
    name: "testo.csv", type: "text/csv", size: 80,
    text: async () => "codice,id\nCA,A\nABC,B\nAC,C"
  }]}});
  await flush();
  assert.match(t.element("adaptive-questions").innerHTML,
    /value="damerau_levenshtein"/);
  t.fire("adaptive-questions", "change", {target: t.customTarget(
    ".text-measure-setting", {textMeasureColumn: "codice"}, "damerau_levenshtein"
  )});
  t.fire("prepare-comparison-plan", "click");
  await flush();
  assert.equal(t.observations.planCalls.at(-1).interpretazione.misureTestualiPerColonna.codice,
    "damerau_levenshtein");
}

async function testInsiemiECicliQuestionario() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "insiemi.csv", type: "text/csv", size: 140,
    text: async () => "etichette,categoria,id\nrosso|blu,x,A\nrosso|verde,y,B\n[],x,C"
  }]}});
  await flush();
  assert.match(h.element("meaning-body").innerHTML, /value="insieme"/);
  const setRole = h.customTarget(".semantic-role", {semanticColumn: "0"}, "insieme");
  h.fire("meaning-body", "change", {target: setRole});
  assert.match(h.element("adaptive-questions").innerHTML, /class="set-setting"/);
  assert.match(h.element("adaptive-questions").innerHTML, /data-set-key="ripetizioni"/);
  for (const [key, value] of Object.entries({
    conferma: "si", separatore: "|", maiuscole: "ignora",
    ripetizioni: "deduplica", misura: "dice"
  })) {
    h.fire("adaptive-questions", "change", {target: h.customTarget(
      ".set-setting", {setColumn: "etichette", setKey: key}, value
    )});
  }
  h.fire("prepare-comparison-plan", "click");
  await flush();
  const a = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(a.colonne.etichette.ruolo, "insieme");
  assert.equal(a.configurazioniInsiemi.etichette.misura, "dice");
  assert.equal(a.configurazioniInsiemi.etichette.maiuscole, "ignora");
  assert.equal(a.configurazioniInsiemi.etichette.separatore, "|");

  const c = createHarness();
  c.fire("csv-file", "change", {target: {files: [{
    name: "ciclo.csv", type: "text/csv", size: 120,
    text: async () => "ora,categoria,id\n23,x,A\n0,x,B\n12,y,C"
  }]}});
  await flush();
  const cycleRole = c.customTarget(".semantic-role", {semanticColumn: "0"}, "ciclica");
  c.fire("meaning-body", "change", {target: cycleRole});
  assert.match(c.element("adaptive-questions").innerHTML, /class="cycle-period-setting"/);
  assert.match(c.element("adaptive-questions").innerHTML, /class="cycle-unit-setting"/);
  c.fire("adaptive-questions", "change", {target: c.customTarget(
    ".cycle-period-setting", {cycleColumn: "ora"}, "24"
  )});
  c.fire("adaptive-questions", "change", {target: c.customTarget(
    ".cycle-unit-setting", {cycleColumn: "ora"}, "ore"
  )});
  c.fire("prepare-comparison-plan", "click");
  await flush();
  const b = c.observations.planCalls.at(-1).interpretazione;
  assert.equal(b.colonne.ora.ruolo, "ciclica");
  assert.equal(b.configurazioniCicliche.ora.periodo, "24");
  assert.equal(b.configurazioniCicliche.ora.unita, "ore");
}

async function testScelteTemporaliAvanzate() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "irregolari.csv", type: "text/csv", size: 120,
    text: async () => "t1,t2,t3,id\n0,3,0,A\n0,5,0,B\n2,4,2,C"
  }]}});
  await flush();
  h.fire("add-column-group", "click");
  for (const nome of ["t1", "t2", "t3"]) {
    h.fire("group-assignment-body", "change", {target: h.customTarget(
      ".group-assignment", {groupColumn: nome}, "gruppo-1"
    )});
  }
  const tipo = h.customTarget(".group-type", {}, "tempo");
  tipo.closest = () => ({dataset: {groupId: "gruppo-1"}});
  h.fire("group-config-list", "change", {target: tipo});
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="tempiTemporaliGruppi"/);
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="unitaTemporaleGruppi"/);
  h.fire("adaptive-questions", "input", {target: h.customTarget(
    ".temporal-order-input", {groupId: "gruppo-1"}, "t1; t2; t3"
  )});
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".temporal-spacing-select", {groupId: "gruppo-1"}, "irregolare"
  )});
  for (const [key,value] of [
    ["tempiTemporaliGruppi", "0; 1; 4"],
    ["unitaTemporaleGruppi", "ore"],
  ]) {
    const cls = key === "tempiTemporaliGruppi" ? ".temporal-parameter" : ".temporal-option";
    h.fire("adaptive-questions", "change", {target: h.customTarget(
      cls, {groupId: "gruppo-1", temporalKey: key}, value
    )});
  }
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "ritardo-gruppo-1"}, "no"
  )});
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="misureTemporaliGruppi"/);
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".temporal-option", {groupId: "gruppo-1", temporalKey: "misureTemporaliGruppi"}, "pendenze"
  )});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  let last = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(last.misureTemporaliGruppi["gruppo-1"], "pendenze");
  assert.equal(last.tempiTemporaliGruppi["gruppo-1"], "0; 1; 4");

  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "ritardo-gruppo-1"}, "si"
  )});
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".temporal-option", {groupId: "gruppo-1", temporalKey: "metodiAllineamentoTemporaleGruppi"}, "dtw"
  )});
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="finestreDTWGruppi"/);
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="penalizzazioniDTWGruppi"/);
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".temporal-option", {groupId: "gruppo-1", temporalKey: "penalizzazioniDTWGruppi"}, "si"
  )});
  for (const [key, value] of [
    ["finestreDTWGruppi", "1"],
    ["pesiRitardoDTWGruppi", "0.5"],
    ["scaleRitardoDTWGruppi", "2"]
  ]) {
    h.fire("adaptive-questions", "input", {target: h.customTarget(
      ".temporal-parameter", {groupId: "gruppo-1", temporalKey: key}, value
    )});
  }
  h.fire("prepare-comparison-plan", "click");
  await flush();
  last = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(last.penalizzazioniDTWGruppi["gruppo-1"], "si");
  assert.equal(last.pesiRitardoDTWGruppi["gruppo-1"], "0.5");
  assert.equal(last.finestreDTWGruppi["gruppo-1"], "1");

  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".temporal-option", {groupId: "gruppo-1", temporalKey: "metodiAllineamentoTemporaleGruppi"}, "lcss"
  )});
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="tolleranzeValoreLCSSGruppi"/);
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="tolleranzeTempoLCSSGruppi"/);
  for(const [key,value] of [
    ["tolleranzeValoreLCSSGruppi", "0.5"],
    ["tolleranzeTempoLCSSGruppi", "3"]
  ]) {
    h.fire("adaptive-questions", "input", {target: h.customTarget(
      ".temporal-parameter", {groupId: "gruppo-1", temporalKey: key}, value
    )});
  }
  h.fire("prepare-comparison-plan", "click");
  await flush();
  last = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(last.metodiAllineamentoTemporaleGruppi["gruppo-1"], "lcss");
  assert.equal(last.tolleranzeTempoLCSSGruppi["gruppo-1"], "3");
  // Modifiche alla struttura invalidano timestamp e conferme precedenti.
  h.fire("group-assignment-body", "change", {target: h.customTarget(
    ".group-assignment", {groupColumn: "t3"}, ""
  )});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  last = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(last.tempiTemporaliGruppi?.["gruppo-1"], undefined);
  assert.equal(last.unitaTemporaleGruppi?.["gruppo-1"], undefined);
}

async function testSerieTemporaliPerRiga() {
  const h = createHarness();
  h.observations.tableIntercept = (csv, scelte) => {
    const tabella = h.makeTable(csv, scelte);
    for (const colonna of tabella.colonne) {
      if (["t3", "v3"].includes(colonna.nome)) colonna.mancanti = 1;
    }
    return Promise.resolve(tabella);
  };
  h.fire("csv-file", "change", {target: {files: [{
    name: "serie-per-riga.csv", type: "text/csv", size: 150,
    text: async () =>
      "id,t1,v1,t2,v2,t3,v3,categoria\n" +
      "A,0,0,1,2,3,0,x\nB,0,0,2,2,4,0,x\nC,0,1,3,1,NA,NA,y"
  }]}});
  await flush();
  h.fire("add-column-group", "click");
  for (const nome of ["t1", "v1", "t2", "v2", "t3", "v3"]) {
    h.fire("group-assignment-body", "change", {target: h.customTarget(
      ".group-assignment", {groupColumn: nome}, "gruppo-1"
    )});
  }
  assert.match(h.element("group-config-list").innerHTML,
    /value="tempo_coppie"/);
  const tipo = h.customTarget(".group-type", {}, "tempo_coppie");
  tipo.closest = () => ({dataset: {groupId: "gruppo-1"}});
  h.fire("group-config-list", "change", {target: tipo});
  const html = h.element("adaptive-questions").innerHTML;
  assert.match(html, /data-temporal-key="coppieTemporaliGruppi"/);
  assert.match(html, /data-temporal-key="unitaTemporaleGruppi"/);
  assert.match(html, /data-temporal-key="metodiAllineamentoTemporaleGruppi"/);
  assert.match(html, /id="mancanti-gruppo-gruppo-1"/);
  const param = (key, value) => h.fire("adaptive-questions", "input", {
    target: h.customTarget(".temporal-parameter",
      {groupId: "gruppo-1", temporalKey: key}, value)
  });
  const sel = (key, value) => h.fire("adaptive-questions", "change", {
    target: h.customTarget(".temporal-option",
      {groupId: "gruppo-1", temporalKey: key}, value)
  });
  param("coppieTemporaliGruppi", "t1:v1; t2:v2; t3:v3");
  sel("unitaTemporaleGruppi", "ore");
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "mancanti-gruppo-gruppo-1"}, "salta_slot"
  )});
  sel("metodiAllineamentoTemporaleGruppi", "dtw");
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="penalizzazioniDTWGruppi"/);
  sel("costiDTWGruppi", "assoluto");
  sel("penalizzazioniDTWGruppi", "si");
  param("pesiRitardoDTWGruppi", "1");
  param("scaleRitardoDTWGruppi", "2");
  param("finestreDTWGruppi", "1");
  h.fire("prepare-comparison-plan", "click");
  await flush();
  let scelta = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(scelta.coppieTemporaliGruppi["gruppo-1"],
    "t1:v1; t2:v2; t3:v3");
  assert.equal(scelta.unitaTemporaleGruppi["gruppo-1"], "ore");
  assert.equal(scelta.metodiAllineamentoTemporaleGruppi["gruppo-1"], "dtw");
  assert.equal(scelta.pesiRitardoDTWGruppi["gruppo-1"], "1");
  assert.equal(scelta.finestreDTWGruppi["gruppo-1"], "1");
  assert.equal(scelta["mancanti-gruppo-gruppo-1"], "salta_slot");
  sel("metodiAllineamentoTemporaleGruppi", "lcss");
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="tolleranzeValoreLCSSGruppi"/);
  assert.match(h.element("adaptive-questions").innerHTML,
    /data-temporal-key="tolleranzeTempoLCSSGruppi"/);
  param("tolleranzeValoreLCSSGruppi", "0.5");
  param("tolleranzeTempoLCSSGruppi", "1");
  h.fire("prepare-comparison-plan", "click");
  await flush();
  scelta = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(scelta.metodiAllineamentoTemporaleGruppi["gruppo-1"], "lcss");
  assert.equal(scelta.tolleranzeTempoLCSSGruppi["gruppo-1"], "1");
  h.fire("group-assignment-body", "change", {target: h.customTarget(
    ".group-assignment", {groupColumn: "v3"}, ""
  )});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  scelta = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(scelta.coppieTemporaliGruppi?.["gruppo-1"], undefined);
  assert.equal(scelta.metodiAllineamentoTemporaleGruppi?.["gruppo-1"], undefined);
}


async function testMancantiBinariPairwise() {
  const h = createHarness();
  h.observations.tableIntercept = (csv, scelte) => {
    const data = h.makeTable(csv, scelte);
    for (const colonna of data.colonne) {
      if (colonna.nome === "flag1" || colonna.nome === "flag2") {
        colonna.mancanti = 1;
      }
    }
    return Promise.resolve(data);
  };
  h.fire("csv-file", "change", {target: {files: [{
    name: "binari-mancanti.csv", type: "text/csv", size: 100,
    text: async () =>
      "flag1,flag2,categoria,id\n1,NA,x,A\n1,0,x,B\n0,1,y,C"
  }]}});
  await flush();
  h.fire("add-column-group", "click");
  for (const nome of ["flag1", "flag2"]) {
    h.fire("group-assignment-body", "change", {target: h.customTarget(
      ".group-assignment", {groupColumn: nome}, "gruppo-1"
    )});
  }
  const tipo = h.customTarget(".group-type", {}, "vettore_binario");
  tipo.closest = () => ({dataset: {groupId: "gruppo-1"}});
  h.fire("group-config-list", "change", {target: tipo});
  const html = h.element("adaptive-questions").innerHTML;
  assert.match(html, /id="mancanti-gruppo-gruppo-1"/);
  assert.match(html, /value="pairwise"/);
  assert.match(html, /coordinate osservate/);
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "misuraBinaria-gruppo-1"}, "jaccard"
  )});
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "mancanti-gruppo-gruppo-1"}, "pairwise"
  )});
  h.fire("prepare-comparison-plan", "click");
  await flush();
  const dati = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(dati["misuraBinaria-gruppo-1"], "jaccard");
  assert.equal(dati["mancanti-gruppo-gruppo-1"], "pairwise");
  assert.equal(dati.assegnazioni.flag1, "gruppo-1");
  assert.equal(dati.assegnazioni.flag2, "gruppo-1");
}

async function testMarcatoriMancantiMisti() {
  const h = createHarness();
  h.observations.tableIntercept = (csv, scelte) => {
    const tabella = h.makeTable(csv, scelte);
    for (const colonna of tabella.colonne) {
      if (colonna.nome === "flag1") colonna.mancanti = 2;
      if (colonna.nome === "categoria") colonna.mancanti = 2;
    }
    return Promise.resolve(tabella);
  };
  h.fire("csv-file", "change", {target: {files: [{
    name: "marcatori.csv", type: "text/csv", size: 95,
    text: async () => "flag1,categoria,id\n1,rosso,A\n?,N/A,B\nNA,NA,C\n0,blu,D"
  }]}});
  await flush();
  h.fire("adaptive-questions", "change", {target: h.customTarget(
    ".semantic-answer", {answer: "significatoMancanti"}, "misto"
  )});
  const html = h.element("adaptive-questions").innerHTML;
  assert.match(html, /class="missing-marker-setting"/);
  assert.match(html, /data-missing-column="flag1" data-missing-marker="\?"/);
  assert.match(html, /data-missing-column="flag1" data-missing-marker="na"/);
  assert.match(html, /data-missing-column="categoria" data-missing-marker="n\/a"/);
  const set = (colonna, marcatore, stato) => {
    h.fire("adaptive-questions", "change", {target: h.customTarget(
      ".missing-marker-setting",
      {missingColumn: colonna, missingMarker: marcatore}, stato
    )});
  };
  set("flag1", "?", "sconosciuto");
  set("flag1", "na", "assenza");
  set("categoria", "n/a", "non_applicabile");
  set("categoria", "na", "assenza");
  h.fire("prepare-comparison-plan", "click");
  await flush();
  const scelte = h.observations.planCalls.at(-1).interpretazione;
  assert.equal(scelte.significatoMancanti, "misto");
  assert.equal(scelte.statiMancantiPerColonna.flag1["?"], "sconosciuto");
  assert.equal(scelte.statiMancantiPerColonna.flag1.na, "assenza");
  assert.equal(scelte.statiMancantiPerColonna.categoria["n/a"],
    "non_applicabile");
  assert.equal(scelte.statiMancantiPerColonna.categoria.na, "assenza");
  assert.doesNotMatch(h.element("adaptive-questions").innerHTML,
    /data-gower-key="mancantiPerColonna"/);
}

async function testLogaritmoStrettamentePositivo() {
  const h = createHarness();
  h.fire("csv-file", "change", {target: {files: [{
    name: "logaritmo-positivo.csv", type: "text/csv", size: 91,
    text: async () =>
      "a,b,id\n0.5,3,A\n1,8,B\n2,6,C\n4,4,D"
  }]}});
  await flush();
  assert.match(h.element("scaling-body").innerHTML,
    /value="log"[^>]*>Confronta rapporti: log\(x\)/);
  assert.match(h.element("scaling-body").innerHTML,
    /value="log1p"[^>]*>Comprimi le differenze grandi: log\(1\+x\)/);
  assert.doesNotMatch(h.element("scaling-body").innerHTML,
    /value="log"[^>]* disabled/);
  h.fire("scaling-body", "change", {target: h.customTarget(
    ".column-choice", {column: "0", choice: "metodo"}, "log"
  )});
  await flush();
  assert.match(h.element("scaling-body").innerHTML, /value="log" selected/);
  assert.match(h.element("scaling-body").innerHTML, /rapporti \|log\(x\/y\)\|/);
  h.fire("confirm-numeric-scaling", "click");
  h.fire("prepare-comparison-plan", "click");
  await flush();
  const ultimoPiano = h.observations.planCalls.at(-1);
  assert.equal(ultimoPiano.choices[0].metodo, "log");
  assert.equal(ultimoPiano.interpretazione.riscalamentoConfermato, true);

  const h0 = createHarness();
  h0.fire("csv-file", "change", {target: {files: [{
    name: "zero.csv", type: "text/csv", size: 80,
    text: async () => "a,b,id\n0,3,A\n1,8,B\n2,6,C\n4,4,D"
  }]}});
  await flush();
  assert.match(h0.element("scaling-body").innerHTML,
    /value="log" disabled/);
  assert.doesNotMatch(h0.element("scaling-body").innerHTML,
    /value="log1p" disabled/);

  const hn = createHarness();
  hn.fire("csv-file", "change", {target: {files: [{
    name: "negativi.csv", type: "text/csv", size: 80,
    text: async () => "a,b,id\n-1,3,A\n1,8,B\n2,6,C\n4,4,D"
  }]}});
  await flush();
  assert.match(hn.element("scaling-body").innerHTML, /value="log" disabled/);
  assert.match(hn.element("scaling-body").innerHTML, /value="log1p" disabled/);
}

(async () => {
  await testLogaritmoStrettamentePositivo();
  await testMarcatoriMancantiMisti();
  await testMancantiBinariPairwise();
  await testSerieTemporaliPerRiga();
  await testScelteTemporaliAvanzate();
  await testInsiemiECicliQuestionario();
  await testGruppoBinarioESceltaTestuale();
  await testMahalanobisAvanzata();
  await testRiscalamentoNumericoInTabellaMista();
  await testGuida();
  await testStaleFiles();
  await testStaleFileRead();
  await testStalePlanAndMatrix();
  await testNewestPlanAndFailures();
  await testLatestColumnChoice();
  await testNominalSettingsPropagation();
  await testGruppoTemporaleConferme();
  console.log("Collaudo DOM e concorrenza dell'interfaccia superato.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
