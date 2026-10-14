/* Gestione dell'interfaccia: seleziona dati compatibili e rappresenta i risultati. */
(function () {
  "use strict";

  const $ = id => document.getElementById(id);
  const M = window.Misure;
  let timerFormula;

  const configurazioni = {
    numeric: {
      misure: ["euclidean", "manhattan", "chebyshev", "minkowski"],
      etichettaX: "Vettore x",
      etichettaY: "Vettore y",
      aiuto: "Separa le coordinate con virgole, spazi o punti e virgola.",
      esempio: { x: "1, 4", y: "3, 1", testo: "Esempio 2D" }
    },
    binary: {
      misure: ["jaccard", "dice", "ochiai", "hamming"],
      etichettaX: "Vettore binario x",
      etichettaY: "Vettore binario y",
      aiuto: "Inserisci soltanto 0 e 1, separati da virgole, spazi o punti e virgola.",
      esempio: { x: "1, 1, 0, 0", y: "1, 0, 1, 0", testo: "Esempio binario" }
    }
  };

  function tipoDatiCorrente() {
    return $("data-type").value;
  }

  function scriviFormula(tex) {
    const elemento = $("formula");
    if (window.MathJax?.typesetClear) window.MathJax.typesetClear([elemento]);
    elemento.textContent = `\\[${tex}\\]`;
    clearTimeout(timerFormula);
    timerFormula = setTimeout(() => {
      if (window.MathJax?.typesetPromise) {
        window.MathJax.typesetPromise([elemento]).catch(errore => console.error("Errore MathJax:", errore));
      }
    }, 70);
  }

  function parametroCorrente() {
    const tipo = $("measure").value;
    if (tipo === "minkowski") return Number($("q").value);
    return M.definizioni[tipo]?.q;
  }

  function popolaMisure() {
    const configurazione = configurazioni[tipoDatiCorrente()];
    $("measure").innerHTML = configurazione.misure.map(chiave => {
      const info = M.definizioni[chiave];
      return `<option value="${chiave}">${info.nome}</option>`;
    }).join("");
  }

  function configuraTipoDati() {
    const configurazione = configurazioni[tipoDatiCorrente()];
    $("vector-x-label").textContent = configurazione.etichettaX;
    $("vector-y-label").textContent = configurazione.etichettaY;
    $("vector-help").textContent = configurazione.aiuto;
    $("vector-x").value = configurazione.esempio.x;
    $("vector-y").value = configurazione.esempio.y;
    const esempio = $("example-button");
    esempio.textContent = configurazione.esempio.testo;
    esempio.dataset.x = configurazione.esempio.x;
    esempio.dataset.y = configurazione.esempio.y;
    popolaMisure();
  }

  function aggiornaTesti() {
    const tipo = $("measure").value;
    const q = parametroCorrente();
    const info = M.definizioni[tipo];
    $("q-panel").hidden = tipo !== "minkowski";
    $("measure-title").textContent = info.nome;
    const formula = tipo === "minkowski" ? `${info.formula},\\qquad q=${M.formatta(q)}` : info.formula;
    scriviFormula(formula);
    if (info.contributo) {
      $("bar-subtitle").textContent = info.contributo.replace("^q", `^${M.formatta(q)}`);
    }
    $("interpretation").textContent = info.interpretazione;
    $("domain").textContent = info.dominio;
    $("properties").textContent = info.proprieta;
  }

  function disegnaContributi(contributi, q) {
    const massimo = Math.max(...contributi, 1e-15);
    $("bars").innerHTML = contributi.map((contributo, j) => {
      const evidenzia = q === Infinity && Math.abs(contributo - massimo) < 1e-12;
      const larghezza = Math.max(1.5, 100 * contributo / massimo);
      return `
        <div class="bar-row">
          <b>j=${j + 1}</b>
          <div class="bar-track"><div class="bar-fill ${evidenzia ? "maximum" : ""}" style="width:${larghezza}%"></div></div>
          <span class="bar-value">${M.formatta(contributo)}</span>
        </div>`;
    }).join("");
  }

  function disegnaBinari(x, y, conteggi) {
    const statistiche = [
      ["n₁₁", conteggi.n11, "presenze comuni", "match-one"],
      ["n₁₀", conteggi.n10, "presente solo in x", "mismatch"],
      ["n₀₁", conteggi.n01, "presente solo in y", "mismatch"],
      ["n₀₀", conteggi.n00, "assenze comuni", "match-zero"]
    ];
    $("binary-counts").innerHTML = statistiche.map(([simbolo, valore, testo, classe]) => `
      <div class="binary-stat ${classe}">
        <span>${simbolo}</span><strong>${valore}</strong><small>${testo}</small>
      </div>`).join("");

    $("binary-coordinates").innerHTML = x.map((valore, j) => {
      const coppia = `${valore}${y[j]}`;
      const stato = valore === y[j] ? "concordanza" : "discordanza";
      return `<div class="binary-coordinate pair-${coppia}"><b>j=${j + 1}</b><span>${valore}, ${y[j]}</span><small>${stato}</small></div>`;
    }).join("");
  }

  function disegnaPiano(x, y, tipo) {
    const svg = $("plot");
    const margine = 42;
    const larghezza = 420;
    const altezza = 320;
    const valoriX = [x[0], y[0], 0];
    const valoriY = [x[1], y[1], 0];
    let minX = Math.min(...valoriX);
    let maxX = Math.max(...valoriX);
    let minY = Math.min(...valoriY);
    let maxY = Math.max(...valoriY);
    const dx = Math.max(maxX - minX, 1);
    const dy = Math.max(maxY - minY, 1);
    minX -= 0.2 * dx; maxX += 0.2 * dx;
    minY -= 0.2 * dy; maxY += 0.2 * dy;
    const scalaX = valore => margine + (valore - minX) / (maxX - minX) * (larghezza - 2 * margine);
    const scalaY = valore => altezza - margine - (valore - minY) / (maxY - minY) * (altezza - 2 * margine);
    const X = { x: scalaX(x[0]), y: scalaY(x[1]) };
    const Y = { x: scalaX(y[0]), y: scalaY(y[1]) };
    const collegamento = tipo === "manhattan"
      ? `<polyline points="${X.x},${X.y} ${Y.x},${X.y} ${Y.x},${Y.y}" fill="none" stroke="#7657ff" stroke-width="3" stroke-dasharray="7 5"/>`
      : `<line x1="${X.x}" y1="${X.y}" x2="${Y.x}" y2="${Y.y}" stroke="#7657ff" stroke-width="3"/>`;
    svg.innerHTML = `
      <line x1="${margine}" y1="${scalaY(0)}" x2="${larghezza - margine}" y2="${scalaY(0)}" stroke="#b8c5d9"/>
      <line x1="${scalaX(0)}" y1="${margine}" x2="${scalaX(0)}" y2="${altezza - margine}" stroke="#b8c5d9"/>
      ${collegamento}
      <circle cx="${X.x}" cy="${X.y}" r="7" fill="#087cff"/>
      <text x="${X.x + 10}" y="${X.y - 10}" fill="#172033" font-size="14" font-weight="700">x</text>
      <circle cx="${Y.x}" cy="${Y.y}" r="7" fill="#7657ff"/>
      <text x="${Y.x + 10}" y="${Y.y - 10}" fill="#172033" font-size="14" font-weight="700">y</text>`;
  }

  function aggiornaPannelli(x, y, risultato, q) {
    const numerico = tipoDatiCorrente() === "numeric";
    const geometria = numerico && x.length === 2;
    $("contribution-panel").hidden = !numerico;
    $("geometry-panel").hidden = !geometria;
    $("binary-panel").hidden = numerico;
    $("visual-panels").classList.toggle("single-panel", !geometria);
    if (numerico) {
      disegnaContributi(risultato.contributi, q);
      if (geometria) disegnaPiano(x, y, $("measure").value);
      else $("plot").replaceChildren();
    } else {
      disegnaBinari(x, y, risultato.conteggi);
    }
  }

  function eseguiCalcolo() {
    const errore = $("error");
    try {
      const x = M.leggiVettore($("vector-x").value);
      const y = M.leggiVettore($("vector-y").value);
      const q = parametroCorrente();
      const risultato = tipoDatiCorrente() === "numeric"
        ? M.calcola(x, y, q)
        : M.calcolaBinaria($("measure").value, x, y);
      aggiornaTesti();
      $("result").textContent = M.formatta(risultato.distanza);
      aggiornaPannelli(x, y, risultato, q);
      errore.style.display = "none";
    } catch (e) {
      errore.textContent = e.message;
      errore.style.display = "block";
    }
  }

  $("data-type").addEventListener("change", () => { configuraTipoDati(); eseguiCalcolo(); });
  $("measure").addEventListener("change", eseguiCalcolo);
  $("q").addEventListener("input", () => {
    $("q-value").textContent = M.formatta(parametroCorrente());
    eseguiCalcolo();
  });
  $("calculate").addEventListener("click", eseguiCalcolo);
  $("example-button").addEventListener("click", () => {
    const esempio = configurazioni[tipoDatiCorrente()].esempio;
    $("vector-x").value = esempio.x;
    $("vector-y").value = esempio.y;
    eseguiCalcolo();
  });
  [$("vector-x"), $("vector-y")].forEach(input => {
    input.addEventListener("keydown", evento => { if (evento.key === "Enter") eseguiCalcolo(); });
  });

  configuraTipoDati();
  eseguiCalcolo();
  window.addEventListener("load", aggiornaTesti);
})();
