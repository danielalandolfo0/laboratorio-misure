/* Interfaccia per il caricamento e il riscalamento automatico dei CSV. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const P = window.Preprocessing;
  let risultato = null;
  let tabellaOriginale = null;
  let testoOriginale = "";
  let scelte = [];
  let interpretazione = { colonne: {}, pesi: {} };
  let vista = "lavoro";

  function escapeHtml(valore) {
    return String(valore).replace(/[&<>"']/g, carattere => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[carattere]);
  }

  function formatoNumero(valore) {
    if (valore === null || valore === undefined) return "—";
    if (typeof valore !== "number") return valore;
    if (Math.abs(valore) < 1e-12) return "0";
    return new Intl.NumberFormat("it-IT", { maximumFractionDigits: 5 }).format(valore);
  }

  function etichettaTipo(tipo) {
    return ({ numerica: "Numerica", numerica_costante: "Numerica costante", binaria: "Binaria", non_numerica: "Non numerica" })[tipo];
  }

  function etichettaMetodo(metodo) {
    return ({ zscore: "Z-score", robusto: "Scala robusta", minmax: "Min–max", maxabs: "Max-abs", costante: "Valore 0", nessuno: "Nessuno" })[metodo];
  }

  function mostraErrore(messaggio) {
    $("csv-error").textContent = messaggio;
    $("csv-error").style.display = "block";
  }

  function nascondiErrore() {
    $("csv-error").textContent = "";
    $("csv-error").style.display = "none";
  }

  function disegnaMetodi() {
    $("scaling-body").innerHTML = risultato.colonne.map((colonna, indice) => {
      const s = colonna.statistiche;
      const parametri = colonna.metodo === "zscore"
        ? `media ${formatoNumero(s.media)} · σ ${formatoNumero(s.deviazione)}`
        : colonna.metodo === "robusto"
          ? `mediana ${formatoNumero(s.mediana)} · IQR ${formatoNumero(s.iqr)}`
          : colonna.metodo === "minmax"
            ? `min ${formatoNumero(s.minimo)} · max ${formatoNumero(s.massimo)}`
            : colonna.metodo === "maxabs"
              ? `max |x| ${formatoNumero(s.massimoAssoluto)}`
          : colonna.metodo === "costante" ? "deviazione 0" : "—";
      const tipo = colonna.sceltaTipo || "auto";
      const metodo = colonna.sceltaMetodo || "auto";
      return `<tr>
        <th scope="row">${escapeHtml(colonna.nome)}</th>
        <td><select class="column-choice" data-choice="tipo" data-column="${indice}" aria-label="Tipo della feature ${escapeHtml(colonna.nome)}">
          <option value="auto"${tipo === "auto" ? " selected" : ""}>${etichettaTipo(colonna.tipoRilevato)} (suggerito)</option>
          <option value="numerica"${tipo === "numerica" ? " selected" : ""}>Numerica</option>
          <option value="binaria"${tipo === "binaria" ? " selected" : ""}>Binaria 0/1</option>
          <option value="non_numerica"${tipo === "non_numerica" ? " selected" : ""}>Non numerica</option>
        </select></td>
        <td><div class="method-choice-wrap"><div class="method-choice-line"><select class="column-choice" data-choice="metodo" data-column="${indice}" aria-label="Metodo per la feature ${escapeHtml(colonna.nome)}"${colonna.tipo === "binaria" || colonna.tipo === "non_numerica" ? " disabled" : ""}>
          <option value="auto"${metodo === "auto" ? " selected" : ""}>${etichettaMetodo(colonna.metodoAutomatico)} (suggerito)</option>
          <option value="zscore"${metodo === "zscore" ? " selected" : ""}>Z-score</option>
          <option value="robusto"${metodo === "robusto" ? " selected" : ""}>Scala robusta</option>
          <option value="minmax"${metodo === "minmax" ? " selected" : ""}>Min–max [0,1]</option>
          <option value="maxabs"${metodo === "maxabs" ? " selected" : ""}>Max-abs</option>
          <option value="nessuno"${metodo === "nessuno" ? " selected" : ""}>Nessuno</option>
        </select><button class="method-info-button" data-info-column="${indice}" type="button" aria-label="Informazioni sulla scelta per ${escapeHtml(colonna.nome)}" aria-controls="method-reason-${indice}" aria-expanded="false">i</button></div><p class="method-reason" id="method-reason-${indice}" hidden>${escapeHtml(colonna.motivo)}</p></div></td>
        <td><span class="method-params">${parametri}</span></td>
        <td>${colonna.mancanti}</td></tr>`;
    }).join("");
  }

  async function aggiornaScelta(elemento) {
    const indice = Number(elemento.dataset.column);
    const chiave = elemento.dataset.choice;
    const precedente = { ...scelte[indice] };
    scelte[indice][chiave] = elemento.value;
    if (chiave === "tipo" && (elemento.value === "binaria" || elemento.value === "non_numerica")) scelte[indice].metodo = "auto";
    try {
      risultato = await P.preparaTabella(testoOriginale, scelte);
      const tipoEffettivo = risultato.colonne[indice].tipo;
      if ((tipoEffettivo === "binaria" || tipoEffettivo === "non_numerica") && scelte[indice].metodo !== "auto") {
        scelte[indice].metodo = "auto";
        risultato = await P.preparaTabella(testoOriginale, scelte);
      }
      nascondiErrore();
      disegnaMetodi();
      disegnaTabella();
      disegnaQuestionario();
    } catch (errore) {
      scelte[indice] = precedente;
      mostraErrore(errore.message);
      disegnaMetodi();
    }
  }

  function righeVista() {
    return vista === "originale" ? risultato.originale.righe : risultato.trasformate;
  }

  function disegnaTabella() {
    const righe = righeVista();
    const limiteRighe = Math.min(12, righe.length);
    const limiteColonne = Math.min(20, risultato.originale.intestazioni.length);
    const intestazioni = risultato.originale.intestazioni.slice(0, limiteColonne);
    $("preview-head").innerHTML = `<tr>${intestazioni.map(nome => `<th scope="col">${escapeHtml(nome)}</th>`).join("")}</tr>`;
    $("preview-body").innerHTML = righe.slice(0, limiteRighe).map(riga =>
      `<tr>${riga.slice(0, limiteColonne).map(valore => `<td>${escapeHtml(formatoNumero(valore))}</td>`).join("")}</tr>`
    ).join("");
    $("preview-caption").textContent = `Anteprima: ${limiteRighe} di ${righe.length} righe${limiteColonne < risultato.originale.intestazioni.length ? ` e ${limiteColonne} di ${risultato.originale.intestazioni.length} colonne` : ""}.`;
    $("view-original").classList.toggle("active", vista === "originale");
    $("view-work").classList.toggle("active", vista === "lavoro");
  }

  function etichettaRuolo(ruolo) {
    return ({
      quantita: "Una quantità misurata",
      livello: "Un livello con un ordine",
      presenza: "Presenza o assenza",
      binaria: "Una risposta con due possibilità",
      categoria: "Un gruppo o una categoria",
      identificativo: "Un codice identificativo",
      data: "Una data o un orario",
      testo: "Un testo o una sequenza",
      risultato: "Un risultato da spiegare o prevedere",
      altro: "Qualcos’altro",
      ignoto: "Non lo so"
    })[ruolo] || ruolo;
  }

  function opzioniRuolo(selezionato) {
    const ruoli = ["quantita", "livello", "presenza", "binaria", "categoria", "identificativo", "data", "testo", "risultato", "altro", "ignoto"];
    return ruoli.map(ruolo => `<option value="${ruolo}"${ruolo === selezionato ? " selected" : ""}>${etichettaRuolo(ruolo)}</option>`).join("");
  }

  function valoreRisposta(id) {
    return interpretazione[id] || "";
  }

  function domandaAdattiva(id, titolo, testo, opzioni) {
    return `<div class="question-item">
      <label for="${id}">${titolo}</label>
      <p>${testo}</p>
      <select class="semantic-answer" id="${id}" data-answer="${id}">
        <option value="">Scegli una risposta</option>
        ${opzioni.map(([valore, etichetta]) => `<option value="${valore}"${valoreRisposta(id) === valore ? " selected" : ""}>${etichetta}</option>`).join("")}
      </select>
    </div>`;
  }

  function dettaglioImportanza(profili) {
    const incluse = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa);
    if (!incluse.length) return `<div class="question-item importance-detail">
      <strong>Quali colonne sono più importanti?</strong>
      <p>Prima seleziona almeno una colonna da usare nel confronto.</p>
    </div>`;
    interpretazione.pesi ||= {};
    return `<div class="question-item importance-detail">
      <strong>Quanto deve contare ogni colonna?</strong>
      <p>Il peso è relativo: “più” significa che una differenza in quella colonna influirà maggiormente sul confronto.</p>
      <div class="importance-list">${incluse.map(profilo => {
        const peso = interpretazione.pesi[profilo.nome] || "1";
        return `<label><span>${escapeHtml(profilo.nome)}</span><select class="importance-weight" data-weight-column="${escapeHtml(profilo.nome)}" aria-label="Importanza della colonna ${escapeHtml(profilo.nome)}">
          <option value="0.5"${peso === "0.5" ? " selected" : ""}>Meno delle altre</option>
          <option value="1"${peso === "1" ? " selected" : ""}>Come le altre</option>
          <option value="2"${peso === "2" ? " selected" : ""}>Più delle altre</option>
          <option value="3"${peso === "3" ? " selected" : ""}>Molto più delle altre</option>
        </select></label>`;
      }).join("")}</div>
    </div>`;
  }

  function disegnaQuestionario() {
    const profili = risultato.questionario.colonne;
    profili.forEach(profilo => {
      if (!interpretazione.colonne[profilo.nome]) {
        interpretazione.colonne[profilo.nome] = {
          ruolo: profilo.ruoloSuggerito,
          usa: profilo.usaNelConfronto
        };
      }
    });
    $("meaning-body").innerHTML = profili.map((profilo, indice) => {
      const risposta = interpretazione.colonne[profilo.nome];
      return `<tr>
        <th scope="row">${escapeHtml(profilo.nome)}</th>
        <td><select class="column-choice semantic-role" data-semantic-column="${indice}" aria-label="Significato della colonna ${escapeHtml(profilo.nome)}">${opzioniRuolo(risposta.ruolo)}</select></td>
        <td><label class="comparison-toggle"><input class="semantic-use" type="checkbox" data-semantic-column="${indice}"${risposta.usa ? " checked" : ""}><span>${risposta.usa ? "Sì" : "No"}</span></label></td>
        <td>${escapeHtml(profilo.motivo)}</td>
      </tr>`;
    }).join("");

    const c = risultato.questionario.condizioni;
    const domande = [];
    if (c.mancanti) domande.push(domandaAdattiva(
      "significatoMancanti", "Che cosa significa una casella vuota?",
      "La risposta cambia il modo in cui due righe possono essere confrontate.",
      [["sconosciuto", "Il valore non è conosciuto"], ["non_applicabile", "La domanda non si applica"], ["assenza", "Indica assenza"], ["misto", "Dipende dalla colonna"], ["ignoto", "Non lo so"]]
    ));
    if (c.estremi) domande.push(domandaAdattiva(
      "significatoEstremi", "I valori molto lontani dagli altri sono plausibili?",
      "Sono stati osservati alcuni valori eccezionalmente alti o bassi.",
      [["reali", "Sì, sono casi reali"], ["errori", "Probabilmente sono errori"], ["controllare", "Vanno controllati uno per uno"], ["ignoto", "Non lo so"]]
    ));
    if (c.binarie) domande.push(domandaAdattiva(
      "zeriCondivisi", "Due assenze in comune rendono simili due righe?",
      "Pensa alle colonne di presenza/assenza: avere entrambi 0 può essere informativo oppure irrilevante.",
      [["si", "Sì, anche l’assenza in comune conta"], ["no", "No, contano soprattutto le presenze"], ["dipende", "Dipende dalla colonna"], ["ignoto", "Non lo so"]]
    ));
    if (c.livelli) domande.push(domandaAdattiva(
      "ordineLivelli", "Nei livelli, l’ordine ha davvero significato?",
      "Per esempio, basso–medio–alto ha un ordine; rosso–verde–blu no.",
      [["si", "Sì, l’ordine è importante"], ["no", "No, sono soltanto etichette"], ["dipende", "Dipende dalla colonna"], ["ignoto", "Non lo so"]]
    ));
    if (c.date) domande.push(domandaAdattiva(
      "usoDate", "Come devono essere considerate le date?",
      "Una data può essere soltanto descrittiva oppure contribuire al confronto.",
      [["escludi", "Non devono influire sul confronto"], ["vicinanza", "Date vicine significano casi simili"], ["durata", "Conta il tempo trascorso"], ["ordine", "Conta soltanto quale viene prima"], ["ignoto", "Non lo so"]]
    ));
    if (c.numeriche && interpretazione.organizzazione === "ripetute") domande.push(domandaAdattiva(
      "somiglianzaNumerica", "In base a che cosa due righe devono essere considerate simili?",
      "Le colonne misurano più volte lo stesso fenomeno. Scegli quale aspetto del profilo deve contare.",
      [["valori_vicini", "Quando hanno valori vicini"], ["proporzioni", "Quando mantengono proporzioni simili"], ["andamento", "Quando crescono e diminuiscono nello stesso modo"], ["ordine", "Quando ordinano le caratteristiche nello stesso modo"], ["ignoto", "Non lo so"]]
    ));
    if (c.numeriche && interpretazione.organizzazione === "tempo") domande.push(domandaAdattiva(
      "allineamentoTemporale", "Un andamento simile può avvenire con un piccolo ritardo?",
      "Per esempio, lo stesso picco può comparire in momenti leggermente diversi nelle due righe.",
      [["si", "Sì, il ritardo non deve renderle diverse"], ["no", "No, gli stessi eventi devono avvenire negli stessi momenti"], ["ignoto", "Non lo so"]]
    ));
    if (c.numeriche && interpretazione.organizzazione === "parti") domande.push(domandaAdattiva(
      "totaleComposizione", "I valori di ogni riga rappresentano parti di un unico totale?",
      "Per esempio, percentuali, quote o quantità la cui somma ha un significato preciso.",
      [["si", "Sì, conta la composizione del totale"], ["no", "No, sono quantità indipendenti"], ["ignoto", "Non lo so"]]
    ));
    domande.push(domandaAdattiva(
      "importanza", "Le colonne hanno tutte la stessa importanza?",
      "Una caratteristica molto importante potrebbe ricevere più peso delle altre.",
      [["uguale", "Sì, tutte uguali"], ["diversa", "No, alcune sono più importanti"], ["ignoto", "Non lo so"]]
    ));
    if (interpretazione.importanza === "diversa") domande.push(dettaglioImportanza(profili));
    $("adaptive-questions").innerHTML = domande.join("");
  }

  function mostraRisultato(nomeFile) {
    $("csv-file-name").textContent = nomeFile;
    $("csv-dimensions").textContent = `Matrice ${risultato.riepilogo.istanze} × ${risultato.riepilogo.feature} (istanze × feature)`;
    $("csv-output").hidden = false;
    $("download-work").disabled = false;
    disegnaMetodi();
    vista = "lavoro";
    disegnaTabella();
    disegnaQuestionario();
  }

  async function elaboraTesto(testo, nomeFile) {
    nascondiErrore();
    try {
      interpretazione = { colonne: {}, pesi: {} };
      $("row-meaning").value = "";
      $("column-organization").value = "";
      testoOriginale = testo;
      risultato = await P.preparaTabella(testo, []);
      tabellaOriginale = risultato.originale;
      scelte = tabellaOriginale.intestazioni.map(() => ({ tipo: "auto", metodo: "auto" }));
      mostraRisultato(nomeFile);
    } catch (errore) {
      risultato = null;
      $("csv-output").hidden = true;
      mostraErrore(errore.message);
    }
  }

  async function elaboraFile(file) {
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) { mostraErrore("Il file supera il limite iniziale di 15 MB."); return; }
    if (!/\.csv$/i.test(file.name) && file.type !== "text/csv" && file.type !== "text/plain") {
      mostraErrore("Seleziona un file CSV."); return;
    }
    try { await elaboraTesto(await file.text(), file.name); }
    catch (_) { mostraErrore("Non è stato possibile leggere il file selezionato."); }
  }

  async function scaricaTabella() {
    if (!risultato) return;
    try {
      const csv = "\uFEFF" + await P.creaCsv(risultato.originale.intestazioni, risultato.trasformate);
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "tabella_riscalata.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (errore) {
      mostraErrore(errore.message);
    }
  }

  const esempio = `misura_A,misura_B,presente,gruppo
10,100,1,alfa
12,105,0,beta
11,98,1,alfa
9,102,0,gamma
13,101,1,beta
10,99,0,alfa
12,104,1,gamma
80,103,0,beta`;

  $("csv-file").addEventListener("change", evento => elaboraFile(evento.target.files[0]));
  $("load-example-csv").addEventListener("click", () => elaboraTesto(esempio, "esempio.csv"));
  $("view-original").addEventListener("click", () => { vista = "originale"; disegnaTabella(); });
  $("view-work").addEventListener("click", () => { vista = "lavoro"; disegnaTabella(); });
  $("download-work").addEventListener("click", scaricaTabella);
  $("scaling-body").addEventListener("change", evento => {
    if (evento.target.matches(".column-choice")) aggiornaScelta(evento.target);
  });
  $("scaling-body").addEventListener("click", evento => {
    const pulsante = evento.target.closest(".method-info-button");
    if (!pulsante) return;
    const spiegazione = document.getElementById(pulsante.getAttribute("aria-controls"));
    const apri = pulsante.getAttribute("aria-expanded") !== "true";
    pulsante.setAttribute("aria-expanded", String(apri));
    spiegazione.hidden = !apri;
  });
  $("meaning-body").addEventListener("change", evento => {
    const indice = Number(evento.target.dataset.semanticColumn);
    if (!Number.isInteger(indice)) return;
    const profilo = risultato.questionario.colonne[indice];
    if (evento.target.matches(".semantic-role")) {
      interpretazione.colonne[profilo.nome].ruolo = evento.target.value;
      if (["identificativo", "data", "testo", "risultato"].includes(evento.target.value)) {
        interpretazione.colonne[profilo.nome].usa = false;
        const riga = evento.target.closest("tr");
        const casella = riga.querySelector(".semantic-use");
        casella.checked = false;
        casella.nextElementSibling.textContent = "No";
      }
    }
    if (evento.target.matches(".semantic-use")) {
      interpretazione.colonne[profilo.nome].usa = evento.target.checked;
      evento.target.nextElementSibling.textContent = evento.target.checked ? "Sì" : "No";
    }
    if (interpretazione.importanza === "diversa") disegnaQuestionario();
  });
  $("adaptive-questions").addEventListener("change", evento => {
    if (evento.target.matches(".semantic-answer")) {
      interpretazione[evento.target.dataset.answer] = evento.target.value;
      if (evento.target.dataset.answer === "importanza") disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".importance-weight")) {
      interpretazione.pesi[evento.target.dataset.weightColumn] = evento.target.value;
    }
  });
  $("row-meaning").addEventListener("change", evento => { interpretazione.riga = evento.target.value; });
  $("column-organization").addEventListener("change", evento => {
    interpretazione.organizzazione = evento.target.value;
    delete interpretazione.somiglianzaNumerica;
    delete interpretazione.allineamentoTemporale;
    delete interpretazione.totaleComposizione;
    disegnaQuestionario();
  });

  const zona = $("csv-drop-zone");
  ["dragenter", "dragover"].forEach(tipo => zona.addEventListener(tipo, evento => { evento.preventDefault(); zona.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach(tipo => zona.addEventListener(tipo, evento => { evento.preventDefault(); zona.classList.remove("dragging"); }));
  zona.addEventListener("drop", evento => elaboraFile(evento.dataTransfer.files[0]));

  const testoPulsanteEsempio = $("load-example-csv").textContent;
  $("csv-file").disabled = true;
  $("load-example-csv").disabled = true;
  $("load-example-csv").textContent = "Preparazione…";
  P.ready.then(() => {
    $("csv-file").disabled = false;
    $("load-example-csv").disabled = false;
    $("load-example-csv").textContent = testoPulsanteEsempio;
  }).catch(errore => {
    $("load-example-csv").textContent = testoPulsanteEsempio;
    mostraErrore(errore.message);
  });
})();
