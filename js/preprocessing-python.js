/* Collegamento sottile tra l'interfaccia e il preprocessing Python in Pyodide. */
(function () {
  "use strict";

  let analizzaCsvPython = null;
  let creaCsvPython = null;
  let creaPianoPython = null;
  let calcolaGowerPython = null;

  const ready = (async () => {
    if (typeof loadPyodide !== "function") {
      throw new Error("Non è stato possibile avviare Python nel browser.");
    }
    const pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.29.0/full/"
    });
    const risposta = await fetch("python/preprocessing.py?v=20261029-2", { cache: "no-cache" });
    if (!risposta.ok) throw new Error("Non è stato possibile caricare il modulo Python di preprocessing.");
    await pyodide.runPythonAsync(await risposta.text());
    analizzaCsvPython = pyodide.globals.get("analizza_csv_json");
    creaCsvPython = pyodide.globals.get("crea_csv_json");
    creaPianoPython = pyodide.globals.get("crea_piano_json");
    calcolaGowerPython = pyodide.globals.get("calcola_gower_json");
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

  async function creaPiano(testo, scelte, interpretazione) {
    await ready;
    const risposta = JSON.parse(creaPianoPython(
      testo,
      JSON.stringify(scelte),
      JSON.stringify(interpretazione)
    ));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.piano;
  }

  async function calcolaGower(testo, scelte, interpretazione) {
    await ready;
    const risposta = JSON.parse(calcolaGowerPython(
      testo,
      JSON.stringify(scelte),
      JSON.stringify(interpretazione)
    ));
    if (!risposta.ok) throw new Error(risposta.errore);
    return risposta.gower;
  }

  window.Preprocessing = { ready, preparaTabella, creaCsv, creaPiano, calcolaGower };
})();
