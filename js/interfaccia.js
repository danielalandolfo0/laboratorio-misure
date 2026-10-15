/* Gestione dell'interfaccia: seleziona dati compatibili e rappresenta i risultati. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const M = window.Misure;
  let timerFormula;

  const configurazioni = {
    numeric: {
      gruppi: [
        ["Famiglia di Minkowski", ["minkowski", "manhattan", "euclidean", "chebyshev", "weighted_minkowski", "standardized_euclidean"]],
        ["Altre distanze basate sulle coordinate", ["mahalanobis", "canberra", "bray_curtis", "chi_square"]],
        ["Similarità di profilo e correlazioni", ["cosine", "pearson"]],
        ["Confronti basati sui ranghi", ["spearman", "kendall_tau_b"]]
      ],
      etichettaX: "Vettore x", etichettaY: "Vettore y",
      aiuto: "Separa le coordinate con virgole, spazi o punti e virgola.",
      esempio: { x: "1, 4", y: "3, 1", testo: "Esempio 2D" }
    },
    binary: {
      gruppi: [
        ["Famiglia pesata", ["weighted_binary"]],
        ["Distanze e dissimilarità simmetriche", ["hamming", "rogers_tanimoto", "sokal_sneath_sym"]],
        ["Distanze e dissimilarità asimmetriche", ["jaccard", "sokal_sneath_asym", "dice", "ochiai", "russell_rao"]]
      ],
      etichettaX: "Vettore binario x", etichettaY: "Vettore binario y",
      aiuto: "Inserisci soltanto 0 e 1, separati da virgole, spazi o punti e virgola.",
      esempio: { x: "1, 1, 0, 0", y: "1, 0, 1, 0", testo: "Esempio binario" }
    },
    string: {
      gruppi: [
        ["Posizioni allineate", ["string_hamming", "string_hamming_normalized"]],
        ["Distanze di edit", ["levenshtein", "levenshtein_normalized", "damerau_levenshtein"]]
      ],
      etichettaX: "Stringa x", etichettaY: "Stringa y",
      aiuto: "Ogni carattere, spazi inclusi, è un simbolo. Il confronto distingue maiuscole e minuscole.",
      esempio: { x: "CA", y: "AC", testo: "Esempio stringhe" }
    }
  };

  const tipoDatiCorrente = () => $("data-type").value;
  const misuraCorrente = () => $("measure").value;

  function scriviFormula(tex) {
    const elemento = $("formula");
    if (window.MathJax?.typesetClear) window.MathJax.typesetClear([elemento]);
    elemento.textContent = `\\[${tex}\\]`;
    clearTimeout(timerFormula);
    timerFormula = setTimeout(() => {
      if (window.MathJax?.typesetPromise) window.MathJax.typesetPromise([elemento]).catch(e => console.error("Errore MathJax:", e));
    }, 70);
  }

  function popolaMisure() {
    $("measure").innerHTML = configurazioni[tipoDatiCorrente()].gruppi.map(([etichetta, misure]) =>
      `<optgroup label="${etichetta}">${misure.map(chiave => `<option value="${chiave}">${M.definizioni[chiave].nome}</option>`).join("")}</optgroup>`
    ).join("");
  }

  function dimensioneCorrente() {
    try { return M.leggiVettore($("vector-x").value).length; } catch (_) { return 2; }
  }

  function identitaTestuale(p) {
    return Array.from({ length: p }, (_, i) => Array.from({ length: p }, (_, j) => i === j ? 1 : 0).join(", ")).join("; ");
  }

  function configuraParametri() {
    const tipo = misuraCorrente();
    const usaQ = ["minkowski", "weighted_minkowski"].includes(tipo);
    $("q-panel").hidden = !usaQ;
    if (usaQ) {
      $("q").min = "1";
      $("q").max = "10";
      $("q").step = "0.5";
      $("q").value = "3";
      $("q-value").textContent = $("q").value.replace(".", ",");
      $("q-help").textContent = "Per ottenere una metrica occorre q ≥ 1.";
    }

    const usaVettore = ["weighted_minkowski", "standardized_euclidean"].includes(tipo);
    $("vector-parameter-panel").hidden = !usaVettore;
    if (usaVettore) {
      const pesi = tipo === "weighted_minkowski";
      $("vector-parameter-label").textContent = pesi ? "Pesi w" : "Scale s";
      $("vector-parameter-help").textContent = pesi ? "Inserisci un peso positivo per ogni coordinata." : "Inserisci una scala positiva per ogni coordinata.";
      $("vector-parameter").value = Array(dimensioneCorrente()).fill("1").join(", ");
    }

    $("matrix-panel").hidden = tipo !== "mahalanobis";
    if (tipo === "mahalanobis") $("matrix-s").value = identitaTestuale(dimensioneCorrente());
    $("binary-weights-panel").hidden = tipo !== "weighted_binary";
  }

  function configuraTipoDati() {
    const c = configurazioni[tipoDatiCorrente()];
    $("vector-x-label").textContent = c.etichettaX;
    $("vector-y-label").textContent = c.etichettaY;
    $("vector-help").textContent = c.aiuto;
    $("vector-x").value = c.esempio.x;
    $("vector-y").value = c.esempio.y;
    const testuale = tipoDatiCorrente() === "string";
    $("vector-x").inputMode = testuale ? "text" : "decimal";
    $("vector-y").inputMode = testuale ? "text" : "decimal";
    $("example-button").textContent = c.esempio.testo;
    popolaMisure();
    configuraParametri();
  }

  function leggiParametri() {
    const tipo = misuraCorrente();
    const parametri = {};
    if (["minkowski", "weighted_minkowski"].includes(tipo)) parametri.q = Number($("q").value);
    if (tipo === "weighted_minkowski") parametri.pesi = M.leggiVettore($("vector-parameter").value);
    if (tipo === "standardized_euclidean") parametri.scale = M.leggiVettore($("vector-parameter").value);
    if (tipo === "mahalanobis") parametri.matrice = M.leggiMatrice($("matrix-s").value);
    if (tipo === "weighted_binary") {
      parametri.lambda = Number($("lambda").value);
      parametri.mu = Number($("mu").value);
      parametri.nu = Number($("nu").value);
    }
    return parametri;
  }

  function aggiornaTesti(parametri) {
    const tipo = misuraCorrente();
    const info = M.definizioni[tipo];
    $("measure-title").textContent = info.nome;
    let formula = info.formula;
    if (parametri.q !== undefined) formula += `,\\qquad q=${M.formatta(parametri.q)}`;
    scriviFormula(formula);
    if (info.contributo) $("bar-subtitle").textContent = info.contributo.replaceAll("^q", `^${M.formatta(parametri.q)}`);
    $("interpretation").textContent = info.interpretazione;
    $("domain").textContent = info.dominio;
    $("properties").textContent = info.proprieta;
    $("result-label").textContent = info.risultato || (tipo === "bray_curtis" ? "Dissimilarità" : "Distanza");
  }

  function disegnaContributi(contributi, tipo) {
    const massimo = Math.max(...contributi, 1e-15);
    const infinito = tipo === "chebyshev";
    $("bars").innerHTML = contributi.map((c, j) => {
      const evidenzia = infinito && Math.abs(c - massimo) < 1e-12;
      return `<div class="bar-row"><b>${tipo === "mahalanobis" ? "k" : "j"}=${j + 1}</b><div class="bar-track"><div class="bar-fill ${evidenzia ? "maximum" : ""}" style="width:${Math.max(1.5, 100 * c / massimo)}%"></div></div><span class="bar-value">${M.formatta(c)}</span></div>`;
    }).join("");
  }

  function disegnaBinari(x, y, c) {
    const statistiche = [["n₁₁", c.n11, "presenze comuni", "match-one"], ["n₁₀", c.n10, "presente solo in x", "mismatch"], ["n₀₁", c.n01, "presente solo in y", "mismatch"], ["n₀₀", c.n00, "assenze comuni", "match-zero"]];
    $("binary-counts").innerHTML = statistiche.map(([s, v, t, cl]) => `<div class="binary-stat ${cl}"><span>${s}</span><strong>${v}</strong><small>${t}</small></div>`).join("");
    $("binary-coordinates").innerHTML = x.map((v, j) => `<div class="binary-coordinate pair-${v}${y[j]}"><b>j=${j + 1}</b><span>${v}, ${y[j]}</span><small>${v === y[j] ? "concordanza" : "discordanza"}</small></div>`).join("");
  }

  function escapeHtml(valore) {
    return String(valore).replace(/[&<>"']/g, carattere => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[carattere]);
  }

  function simboloVisibile(simbolo) {
    return simbolo === " " ? "␠" : escapeHtml(simbolo);
  }

  function disegnaStringhe(risultato) {
    const contenuto = $("string-visualization");
    if (risultato.confronti) {
      $("string-panel-subtitle").textContent = "Verde: simboli uguali. Viola: sostituzioni necessarie.";
      contenuto.innerHTML = `<div class="string-pairs">${risultato.confronti.map((c, i) =>
        `<div class="string-pair ${c.diverso ? "different" : "equal"}"><b>i=${i + 1}</b><span>${simboloVisibile(c.simboloX)}</span><span>${simboloVisibile(c.simboloY)}</span><small>${c.diverso ? "diversi" : "uguali"}</small></div>`
      ).join("")}</div>`;
      return;
    }
    $("string-panel-subtitle").textContent = "La cella in basso a destra contiene la distanza finale.";
    const intestazione = ["∅", ...risultato.simboliY].map(s => `<th>${simboloVisibile(s)}</th>`).join("");
    const righe = risultato.matrice.map((riga, i) => {
      const etichetta = i === 0 ? "∅" : risultato.simboliX[i - 1];
      return `<tr><th>${simboloVisibile(etichetta)}</th>${riga.map((v, j) =>
        `<td class="${i === risultato.matrice.length - 1 && j === riga.length - 1 ? "final-cell" : ""}">${v}</td>`
      ).join("")}</tr>`;
    }).join("");
    contenuto.innerHTML = `<div class="string-matrix-wrap"><table class="string-matrix"><thead><tr><th></th>${intestazione}</tr></thead><tbody>${righe}</tbody></table></div>`;
  }

  function coloreCoordinata(indice, totale) {
    const tonalita = Math.round((indice * 320 / Math.max(totale, 1) + 205) % 360);
    return `hsl(${tonalita} 66% 47%)`;
  }

  function creaRigaOrdine(nome, valori, ranghi) {
    const elementi = valori.map((valore, indice) => ({ valore, indice, rango: ranghi[indice] }))
      .sort((a, b) => a.rango - b.rango || a.indice - b.indice);
    return `<div class="rank-order-row"><b>${nome}</b><div class="rank-items">${elementi.map(item =>
      `<span class="rank-item" style="--rank-color:${coloreCoordinata(item.indice, valori.length)}"><small>j=${item.indice + 1}</small><strong>${M.formatta(item.valore)}</strong><em>R=${M.formatta(item.rango)}</em></span>`
    ).join("")}</div></div>`;
  }

  function disegnaRanghi(x, y, risultato) {
    $("rank-panel-subtitle").textContent = misuraCorrente() === "spearman"
      ? "Lo stesso colore identifica la medesima coordinata nei due ordinamenti; i pari merito condividono il rango medio."
      : "Lo stesso colore identifica la medesima coordinata; Kendall confronta tutte le coppie e corregge i pari merito.";
    $("rank-orders").innerHTML = creaRigaOrdine("Ordine secondo x", x, risultato.ranghiX)
      + creaRigaOrdine("Ordine secondo y", y, risultato.ranghiY);
    if (misuraCorrente() === "spearman") {
      $("rank-details").innerHTML = `<div class="rank-differences">${risultato.ranghiX.map((rangoX, j) =>
        `<div class="rank-detail" style="--rank-color:${coloreCoordinata(j, x.length)}"><b>j=${j + 1}</b><span>Rₓ=${M.formatta(rangoX)}</span><span>Rᵧ=${M.formatta(risultato.ranghiY[j])}</span><small>|ΔR|=${M.formatta(Math.abs(rangoX - risultato.ranghiY[j]))}</small></div>`
      ).join("")}</div>`;
    } else {
      const q = risultato.conteggiRango;
      const statistiche = [["C", q.C, "concordanti"], ["D", q.D, "discordanti"], ["Tₓ", q.Tx, "legate solo in x"], ["Tᵧ", q.Ty, "legate solo in y"]];
      $("rank-details").innerHTML = `<div class="rank-counts">${statistiche.map(([simbolo, valore, testo]) =>
        `<div class="rank-stat"><span>${simbolo}</span><strong>${valore}</strong><small>${testo}</small></div>`
      ).join("")}</div>`;
    }
  }

  function disegnaDirezioni(x, y, tipo) {
    const svg = $("plot");
    const margine = 42, larghezza = 420, altezza = 320;
    const centra = vettore => {
      const media = vettore.reduce((a, b) => a + b, 0) / vettore.length;
      return vettore.map(v => v - media);
    };
    const Xv = tipo === "pearson" ? centra(x) : x.slice();
    const Yv = tipo === "pearson" ? centra(y) : y.slice();
    $("geometry-subtitle").textContent = tipo === "pearson"
      ? "I profili centrati sono applicati all'origine: Pearson è il coseno dell'angolo fra essi."
      : "I vettori sono applicati all'origine: il loro angolo determina la similarità coseno.";
    const massimoX = Math.max(1, Math.abs(Xv[0]), Math.abs(Yv[0])) * 1.25;
    const massimoY = Math.max(1, Math.abs(Xv[1]), Math.abs(Yv[1])) * 1.25;
    const sx = v => margine + (v + massimoX) / (2 * massimoX) * (larghezza - 2 * margine);
    const sy = v => altezza - margine - (v + massimoY) / (2 * massimoY) * (altezza - 2 * margine);
    const O = { x: sx(0), y: sy(0) };
    const X = { x: sx(Xv[0]), y: sy(Xv[1]) };
    const Y = { x: sx(Yv[0]), y: sy(Yv[1]) };
    const etichettaX = tipo === "pearson" ? "x centrato" : "x";
    const etichettaY = tipo === "pearson" ? "y centrato" : "y";
    svg.innerHTML = `<defs><marker id="arrow-x" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#087cff"/></marker><marker id="arrow-y" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#7657ff"/></marker></defs><line x1="${margine}" y1="${O.y}" x2="${larghezza - margine}" y2="${O.y}" stroke="#b8c5d9"/><line x1="${O.x}" y1="${margine}" x2="${O.x}" y2="${altezza - margine}" stroke="#b8c5d9"/><circle cx="${O.x}" cy="${O.y}" r="4" fill="#77839a"/><line x1="${O.x}" y1="${O.y}" x2="${X.x}" y2="${X.y}" stroke="#087cff" stroke-width="4" marker-end="url(#arrow-x)"/><line x1="${O.x}" y1="${O.y}" x2="${Y.x}" y2="${Y.y}" stroke="#7657ff" stroke-width="4" marker-end="url(#arrow-y)"/><text x="${X.x + 10}" y="${X.y - 9}" fill="#087cff" font-size="13" font-weight="700">${etichettaX}</text><text x="${Y.x + 10}" y="${Y.y + 18}" fill="#7657ff" font-size="13" font-weight="700">${etichettaY}</text>`;
  }

  function disegnaPiano(x, y, tipo) {
    const svg = $("plot");
    $("geometry-subtitle").textContent = "Rappresentazione dei vettori nel piano ℝ².";
    const margine = 42, larghezza = 420, altezza = 320;
    let minX = Math.min(x[0], y[0], 0), maxX = Math.max(x[0], y[0], 0);
    let minY = Math.min(x[1], y[1], 0), maxY = Math.max(x[1], y[1], 0);
    const dx = Math.max(maxX - minX, 1), dy = Math.max(maxY - minY, 1);
    minX -= .2 * dx; maxX += .2 * dx; minY -= .2 * dy; maxY += .2 * dy;
    const sx = v => margine + (v - minX) / (maxX - minX) * (larghezza - 2 * margine);
    const sy = v => altezza - margine - (v - minY) / (maxY - minY) * (altezza - 2 * margine);
    const X = { x: sx(x[0]), y: sy(x[1]) }, Y = { x: sx(y[0]), y: sy(y[1]) };
    const collegamento = tipo === "manhattan" ? `<polyline points="${X.x},${X.y} ${Y.x},${X.y} ${Y.x},${Y.y}" fill="none" stroke="#7657ff" stroke-width="3" stroke-dasharray="7 5"/>` : `<line x1="${X.x}" y1="${X.y}" x2="${Y.x}" y2="${Y.y}" stroke="#7657ff" stroke-width="3"/>`;
    svg.innerHTML = `<line x1="${margine}" y1="${sy(0)}" x2="${larghezza - margine}" y2="${sy(0)}" stroke="#b8c5d9"/><line x1="${sx(0)}" y1="${margine}" x2="${sx(0)}" y2="${altezza - margine}" stroke="#b8c5d9"/>${collegamento}<circle cx="${X.x}" cy="${X.y}" r="7" fill="#087cff"/><text x="${X.x + 10}" y="${X.y - 10}" fill="#172033" font-size="14" font-weight="700">x</text><circle cx="${Y.x}" cy="${Y.y}" r="7" fill="#7657ff"/><text x="${Y.x + 10}" y="${Y.y - 10}" fill="#172033" font-size="14" font-weight="700">y</text>`;
  }

  function aggiornaPannelli(x, y, risultato) {
    const tipoDati = tipoDatiCorrente();
    const numerico = tipoDati === "numeric";
    const binario = tipoDati === "binary";
    const stringa = tipoDati === "string";
    const direzionale = ["cosine", "pearson"].includes(misuraCorrente());
    const basataSuiRanghi = ["spearman", "kendall_tau_b"].includes(misuraCorrente());
    const soloCoefficiente = direzionale || basataSuiRanghi;
    const geometria = numerico && !basataSuiRanghi && x.length === 2;
    $("contribution-panel").hidden = !numerico || soloCoefficiente;
    $("geometry-panel").hidden = !geometria;
    $("rank-panel").hidden = !basataSuiRanghi;
    $("binary-panel").hidden = !binario;
    $("string-panel").hidden = !stringa;
    $("visual-panels").classList.toggle("single-panel", soloCoefficiente || !geometria);
    if (numerico) {
      if (basataSuiRanghi) {
        disegnaRanghi(x, y, risultato);
        $("plot").replaceChildren();
      } else {
        if (!soloCoefficiente) disegnaContributi(risultato.contributi, misuraCorrente());
        if (geometria) {
          if (direzionale) disegnaDirezioni(x, y, misuraCorrente());
          else disegnaPiano(x, y, misuraCorrente());
        } else $("plot").replaceChildren();
      }
    } else if (binario) disegnaBinari(x, y, risultato.conteggi);
    else disegnaStringhe(risultato);
  }

  function eseguiCalcolo() {
    const messaggio = $("error");
    try {
      const tipoDati = tipoDatiCorrente();
      const x = tipoDati === "string" ? M.leggiStringa($("vector-x").value) : M.leggiVettore($("vector-x").value);
      const y = tipoDati === "string" ? M.leggiStringa($("vector-y").value) : M.leggiVettore($("vector-y").value);
      const parametri = leggiParametri();
      const risultato = tipoDati === "numeric"
        ? M.calcolaNumerica(misuraCorrente(), x, y, parametri)
        : tipoDati === "binary"
          ? M.calcolaBinaria(misuraCorrente(), x, y, parametri)
          : M.calcolaStringa(misuraCorrente(), x, y);
      aggiornaTesti(parametri);
      $("result").textContent = M.formatta(risultato.valore);
      aggiornaPannelli(x, y, risultato);
      messaggio.classList.toggle("notice", !risultato.definita);
      messaggio.textContent = risultato.definita ? "" : risultato.messaggio;
      messaggio.style.display = risultato.definita ? "none" : "block";
    } catch (e) {
      messaggio.classList.remove("notice");
      messaggio.textContent = e.message;
      messaggio.style.display = "block";
    }
  }

  $("data-type").addEventListener("change", () => { configuraTipoDati(); eseguiCalcolo(); });
  $("measure").addEventListener("change", () => { configuraParametri(); eseguiCalcolo(); });
  $("q").addEventListener("input", () => { $("q-value").textContent = $("q").value.replace(".", ","); eseguiCalcolo(); });
  $("calculate").addEventListener("click", eseguiCalcolo);
  $("example-button").addEventListener("click", () => {
    const e = configurazioni[tipoDatiCorrente()].esempio;
    $("vector-x").value = e.x; $("vector-y").value = e.y;
    configuraParametri(); eseguiCalcolo();
  });
  [$("vector-x"), $("vector-y"), $("vector-parameter"), $("matrix-s"), $("lambda"), $("mu"), $("nu")].forEach(input => input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) eseguiCalcolo(); }));
  configuraTipoDati();
  eseguiCalcolo();
  window.addEventListener("load", () => aggiornaTesti(leggiParametri()));
})();
