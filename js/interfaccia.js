/* Gestione dell'interfaccia: legge gli input e rappresenta i risultati. */
(function () {
  "use strict";

  const $ = id => document.getElementById(id);
  const M = window.Misure;
  let timerFormula;

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
    return tipo === "minkowski" ? Number($("q").value) : M.definizioni[tipo].q;
  }

  function aggiornaTesti() {
    const tipo = $("measure").value;
    const q = parametroCorrente();
    const info = M.definizioni[tipo];

    $("q-panel").hidden = tipo !== "minkowski";
    $("measure-title").textContent = info.nome;
    const formula = tipo === "minkowski"
      ? `${info.formula},\\qquad q=${M.formatta(q)}`
      : info.formula;
    scriviFormula(formula);
    $("bar-subtitle").textContent = info.contributo.replace("^q", `^${M.formatta(q)}`);
    $("interpretation").textContent = info.interpretazione;
  }

  function disegnaContributi(contributi, q) {
    const massimo = Math.max(...contributi, 1e-15);
    $("bars").innerHTML = contributi.map((contributo, j) => {
      const evidenzia = q === Infinity && Math.abs(contributo - massimo) < 1e-12;
      const larghezza = Math.max(1.5, 100 * contributo / massimo);
      return `
        <div class="bar-row">
          <b>j=${j + 1}</b>
          <div class="bar-track">
            <div class="bar-fill ${evidenzia ? "maximum" : ""}" style="width:${larghezza}%"></div>
          </div>
          <span class="bar-value">${M.formatta(contributo)}</span>
        </div>`;
    }).join("");
  }

  function disegnaPiano(x, y, tipo) {
    const svg = $("plot");
    if (x.length !== 2) {
      svg.innerHTML = '<text x="210" y="150" text-anchor="middle" fill="#61706c" font-size="14">Vista disponibile soltanto in ℝ²</text>';
      return;
    }

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
      ? `<polyline points="${X.x},${X.y} ${Y.x},${X.y} ${Y.x},${Y.y}" fill="none" stroke="#dd6b35" stroke-width="3" stroke-dasharray="7 5"/>`
      : `<line x1="${X.x}" y1="${X.y}" x2="${Y.x}" y2="${Y.y}" stroke="#dd6b35" stroke-width="3"/>`;

    svg.innerHTML = `
      <line x1="${margine}" y1="${scalaY(0)}" x2="${larghezza - margine}" y2="${scalaY(0)}" stroke="#c9c5ba"/>
      <line x1="${scalaX(0)}" y1="${margine}" x2="${scalaX(0)}" y2="${altezza - margine}" stroke="#c9c5ba"/>
      ${collegamento}
      <circle cx="${X.x}" cy="${X.y}" r="7" fill="#176b67"/>
      <text x="${X.x + 10}" y="${X.y - 10}" fill="#17211f" font-size="14" font-weight="700">x</text>
      <circle cx="${Y.x}" cy="${Y.y}" r="7" fill="#dd6b35"/>
      <text x="${Y.x + 10}" y="${Y.y - 10}" fill="#17211f" font-size="14" font-weight="700">y</text>`;
  }

  function eseguiCalcolo() {
    const errore = $("error");
    try {
      const x = M.leggiVettore($("vector-x").value);
      const y = M.leggiVettore($("vector-y").value);
      const q = parametroCorrente();
      const risultato = M.calcola(x, y, q);

      aggiornaTesti();
      $("result").textContent = M.formatta(risultato.distanza);
      disegnaContributi(risultato.contributi, q);
      disegnaPiano(x, y, $("measure").value);
      errore.style.display = "none";
    } catch (e) {
      errore.textContent = e.message;
      errore.style.display = "block";
    }
  }

  $("measure").addEventListener("change", eseguiCalcolo);
  $("q").addEventListener("input", () => {
    $("q-value").textContent = M.formatta(parametroCorrente());
    eseguiCalcolo();
  });
  $("calculate").addEventListener("click", eseguiCalcolo);

  document.querySelectorAll(".chip").forEach(bottone => {
    bottone.addEventListener("click", () => {
      $("vector-x").value = bottone.dataset.x;
      $("vector-y").value = bottone.dataset.y;
      eseguiCalcolo();
    });
  });

  [$("vector-x"), $("vector-y")].forEach(input => {
    input.addEventListener("keydown", evento => {
      if (evento.key === "Enter") eseguiCalcolo();
    });
  });

  eseguiCalcolo();
  window.addEventListener("load", aggiornaTesti);
})();
