/* Collegamento sottile tra l'interfaccia e il preprocessing Python in Pyodide. */
(function () {
  "use strict";

  let anteprimaImportazionePython = null;
  let analizzaCsvPython = null;
  let creaCsvPython = null;
  let creaPianoPython = null;
  let calcolaMatricePython = null;
  let creaRapportoPython = null;
  let analizzaDiagnosiPython = null;

  const ready = (async () => {
    if (typeof loadPyodide !== "function") {
      throw new Error("Non è stato possibile avviare Python nel browser.");
    }
    const pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.29.0/full/"
    });
    const risposta = await fetch("python/preprocessing.py?v=20261115-stabilita-pesi1", { cache: "no-cache" });
    if (!risposta.ok) throw new Error("Non è stato possibile caricare il modulo Python di preprocessing.");
    await pyodide.runPythonAsync(await risposta.text());
    anteprimaImportazionePython = pyodide.globals.get("anteprima_importazione_json");
    analizzaCsvPython = pyodide.globals.get("analizza_csv_json");
    creaCsvPython = pyodide.globals.get("crea_csv_json");
    creaPianoPython = pyodide.globals.get("crea_piano_json");
    calcolaMatricePython = pyodide.globals.get("calcola_matrice_json");
    creaRapportoPython = pyodide.globals.get("crea_rapporto_json");
    analizzaDiagnosiPython = pyodide.globals.get("analizza_diagnosi_numerica_json");
  })();

  async function anteprimaImportazione(testo, opzioni = {}) {
    await ready;
    const risposta = JSON.parse(anteprimaImportazionePython(testo, JSON.stringify(opzioni)));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta;
  }

  async function preparaTabella(testo, scelte = [], importazione = {}) {
    await ready;
    const risposta = JSON.parse(analizzaCsvPython(
      testo, JSON.stringify(scelte), JSON.stringify(importazione)
    ));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.risultato;
  }

  async function creaCsv(intestazioni, righe) {
    await ready;
    const risposta = JSON.parse(creaCsvPython(JSON.stringify(intestazioni), JSON.stringify(righe)));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.csv;
  }

  async function creaPiano(testo, scelte, interpretazione, importazione = {}) {
    await ready;
    const risposta = JSON.parse(creaPianoPython(
      testo,
      JSON.stringify(scelte),
      JSON.stringify(interpretazione),
      JSON.stringify(importazione)
    ));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.piano;
  }

  async function calcolaMatrice(testo, scelte, interpretazione, importazione = {}) {
    await ready;
    const risposta = JSON.parse(calcolaMatricePython(
      testo,
      JSON.stringify(scelte),
      JSON.stringify(interpretazione),
      JSON.stringify(importazione)
    ));
    if (!risposta.ok) {
      const errore = new Error(risposta.errore);
      if (risposta.rapportoProblemi) {
        errore.rapportoProblemi = risposta.rapportoProblemi;
      }
      throw errore;
    }
    return risposta.matrice;
  }

  async function creaRapporto(testo, scelte, interpretazione, nomeFile, importazione = {}) {
    await ready;
    const risposta = JSON.parse(creaRapportoPython(
      testo,
      JSON.stringify(scelte),
      JSON.stringify(interpretazione),
      nomeFile,
      JSON.stringify(importazione)
    ));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.rapporto;
  }

  async function analizzaDiagnosi(testo, scelte, nomi, importazione = {}) {
    await ready;
    const risposta = JSON.parse(analizzaDiagnosiPython(
      testo, JSON.stringify(scelte), JSON.stringify(nomi),
      JSON.stringify(importazione)
    ));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta;
  }

  window.Preprocessing = { ready, anteprimaImportazione, preparaTabella, creaCsv, creaPiano, calcolaMatrice, creaRapporto, analizzaDiagnosi };
})();
