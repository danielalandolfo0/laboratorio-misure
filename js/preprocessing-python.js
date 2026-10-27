/* Collegamento sottile tra l'interfaccia e il preprocessing Python in Pyodide. */
(function () {
  "use strict";

  let analizzaCsvPython = null;
  let creaCsvPython = null;

  const ready = (async () => {
    if (typeof loadPyodide !== "function") {
      throw new Error("Non è stato possibile avviare Python nel browser.");
    }
    const pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.29.0/full/"
    });
    const risposta = await fetch("python/preprocessing.py?v=20261027-1", { cache: "no-cache" });
    if (!risposta.ok) throw new Error("Non è stato possibile caricare il modulo Python di preprocessing.");
    await pyodide.runPythonAsync(await risposta.text());
    analizzaCsvPython = pyodide.globals.get("analizza_csv_json");
    creaCsvPython = pyodide.globals.get("crea_csv_json");
  })();

  async function preparaTabella(testo, scelte = []) {
    await ready;
    const risposta = JSON.parse(analizzaCsvPython(testo, JSON.stringify(scelte)));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.risultato;
  }

  async function creaCsv(intestazioni, righe) {
    await ready;
    const risposta = JSON.parse(creaCsvPython(JSON.stringify(intestazioni), JSON.stringify(righe)));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.csv;
  }

  window.Preprocessing = { ready, preparaTabella, creaCsv };
})();
