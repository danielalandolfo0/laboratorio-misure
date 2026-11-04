/* Interfaccia per il caricamento e il riscalamento automatico dei CSV. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const P = window.Preprocessing;
  let risultato = null;
  let tabellaOriginale = null;
  let testoOriginale = "";
  let scelte = [];
  let interpretazione = { colonne: {}, gruppi: [], assegnazioni: {}, prossimoGruppo: 1 };
  let vista = "lavoro";
  let pianoCorrente = null;
  let matriceCorrente = null;
  let versioneDiagnosi = 0;
  let riscalamentoConfermato = false;

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
    const selezionate = new Set(colonneNumericheSelezionate().map(c => c.nome));
    $("scaling-body").innerHTML = risultato.colonne
      .map((colonna, indice) => ({ colonna, indice }))
      .filter(({ colonna }) => selezionate.has(colonna.nome))
      .map(({ colonna, indice }) => {
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
          <option value="zscore"${metodo === "zscore" ? " selected" : ""}>Confronta gli scarti dalla media (z-score)</option>
          <option value="robusto"${metodo === "robusto" ? " selected" : ""}>Riduci l’effetto dei valori estremi sul riscalamento (robusto)</option>
          <option value="minmax"${metodo === "minmax" ? " selected" : ""}>Porta i valori tra 0 e 1 (min–max)</option>
          <option value="maxabs"${metodo === "maxabs" ? " selected" : ""}>Dividi per il valore massimo assoluto (max-abs)</option>
          <option value="nessuno"${metodo === "nessuno" ? " selected" : ""}>Mantieni i valori originali</option>
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
      riscalamentoConfermato = false;
      interpretazione.riscalamentoConfermato = false;
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
    const selezionate = vista === "lavoro"
      ? colonneNumericheSelezionate().map(c => c.nome)
      : risultato.originale.intestazioni;
    const indici = selezionate.map(nome => risultato.originale.intestazioni.indexOf(nome));
    const righe = vista === "lavoro" && pianoCorrente?.anteprimaNumerica
      ? pianoCorrente.anteprimaNumerica.righe
      : righeVista().map(riga => indici.map(indice => riga[indice]));
    const limiteRighe = Math.min(12, righe.length);
    const limiteColonne = Math.min(20, selezionate.length);
    const intestazioni = selezionate.slice(0, limiteColonne);
    $("preview-head").innerHTML = `<tr>${intestazioni.map(nome => `<th scope="col">${escapeHtml(nome)}</th>`).join("")}</tr>`;
    $("preview-body").innerHTML = righe.slice(0, limiteRighe).map(riga =>
      `<tr>${riga.slice(0, limiteColonne).map(valore => `<td>${escapeHtml(formatoNumero(valore))}</td>`).join("")}</tr>`
    ).join("");
    const origine = vista === "originale"
      ? "Valori originali."
      : "Valori trasformati secondo il riscalamento confermato nel piano di confronto.";
    const totaleRighe = risultato.originale.righe.length;
    $("preview-caption").textContent = `${origine} ${limiteRighe} di ${totaleRighe} righe${limiteColonne < selezionate.length ? ` e ${limiteColonne} di ${selezionate.length} colonne` : ""}.`;
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

  function domandaAdattiva(id, titolo, testo, opzioni, predefinito = "") {
    const selezionato = valoreRisposta(id) || predefinito;
    return `<div class="question-item">
      <label for="${id}">${titolo}</label>
      <p>${testo}</p>
      <select class="semantic-answer" id="${id}" data-answer="${id}">
        ${predefinito ? "" : '<option value="">Scegli una risposta</option>'}
        ${opzioni.map(([valore, etichetta]) => `<option value="${valore}"${selezionato === valore ? " selected" : ""}>${etichetta}</option>`).join("")}
      </select>
    </div>`;
  }

  function domandaInput(id, titolo, testo, placeholder, tipo = "text") {
    return `<div class="question-item">
      <label for="${id}">${titolo}</label>
      <p>${testo}</p>
      <input class="semantic-input" id="${id}" data-answer="${id}" type="${tipo}" value="${escapeHtml(valoreRisposta(id))}" placeholder="${escapeHtml(placeholder)}">
    </div>`;
  }

  function notaAutomatica(titolo, testo) {
    return `<div class="question-item automatic-note">
      <strong>${escapeHtml(titolo)}</strong>
      <p>${escapeHtml(testo)}</p>
    </div>`;
  }

  function nascondiPiano() {
    $("comparison-plan").hidden = true;
    $("gower-actions").hidden = true;
    $("gower-result").hidden = true;
    pianoCorrente = null;
    matriceCorrente = null;
    aggiornaVisibilitaTrasformazione();
  }

  function colonneNumericheSelezionate() {
    if (!risultato) return [];
    return risultato.colonne.filter(colonna => {
      const risposta = interpretazione.colonne[colonna.nome];
      return risposta?.usa && risposta.ruolo === "quantita"
        && !interpretazione.assegnazioni[colonna.nome]
        && ["numerica", "numerica_costante"].includes(colonna.tipo);
    });
  }
  function tabellaInteramenteNumerica() {
    if (!risultato) return false;
    const incluse = risultato.colonne.filter(c => interpretazione.colonne[c.nome]?.usa);
    return incluse.length > 0 && incluse.length === colonneNumericheSelezionate().length;
  }

  async function mostraDiagnosiPreliminare() {
    const contenitore = $("numeric-preliminary-diagnosis");
    const corpo = $("numeric-preliminary-content");
    const versione = ++versioneDiagnosi;
    const nomi = colonneNumericheSelezionate().map(c => c.nome);
    if (nomi.length < 2) {
      contenitore.hidden = true;
      corpo.innerHTML = "";
      return;
    }
    contenitore.hidden = false;
    $("numeric-preliminary-scope").textContent =
      `Analisi delle ${nomi.length} caratteristiche quantitative indipendenti: ${nomi.join(", ")}. ` +
      (tabellaInteramenteNumerica()
        ? "Questa diagnosi orienta la scelta della misura e del riscalamento; non modifica i dati."
        : "Le altre colonne e i gruppi non entrano in questa diagnosi. Nei percorsi misti Gower normalizza internamente i contributi quantitativi.");
    corpo.textContent = "Analisi preliminare delle colonne quantitative indipendenti…";
    try {
      const risposta = await P.analizzaDiagnosi(testoOriginale, scelte, nomi);
      if (versione !== versioneDiagnosi) return;
      const d = risposta.diagnosi;
      const estreme = risposta.colonne.filter(c => c.statistiche.estremi > 0);
      const range = risposta.colonne.map(c => ({
        nome: c.nome,
        ampiezza: c.statistiche.massimo - c.statistiche.minimo,
        iqr: c.statistiche.iqr
      }));
      const coppie = d.relazioniCoppie || [];
      const perfette = coppie.filter(c => c.intensita === "perfetta");
      const forti = coppie.filter(c => c.intensita === "forte");
      const outlier = estreme.length
        ? "Possibili valori insoliti in " + estreme.map(c => c.nome + " (" + c.statistiche.estremi + ")").join(", ") + ". Controlla se sono osservazioni corrette."
        : "Non risultano valori oltre i limiti della regola statistica utilizzata. Questo non garantisce che ogni valore sia corretto.";
      const scale = range.length < 2
        ? "È selezionata una sola colonna numerica."
        : "Intervalli osservati (massimo − minimo): " + range.map(c => c.nome + ": " + formatoNumero(c.ampiezza)).join("; ") + ". " +
          "Rapporto tra la dispersione maggiore e la minore: " + formatoNumero(d.rapportoDispersioni) + ". " +
          (d.dispersioniSimili
            ? "Secondo il criterio esplorativo adottato, le dispersioni non differiscono molto."
            : "Secondo il criterio esplorativo adottato, le dispersioni differiscono. La scelta della misura e delle scale richiede attenzione: il solo rapporto statistico non determina il riscalamento corretto.");
      let andamento = "Non sono state rilevate relazioni lineari forti tra le coppie di colonne controllabili.";
      if (perfette.length) {
        andamento = "Alcune coppie seguono un andamento lineare perfetto: " +
          perfette.map(c => c.colonne.join(" e ") + (c.correlazione > 0 ? " crescono insieme" : " si muovono in direzioni opposte")).join("; ") +
          ". Potrebbero riportare informazioni ripetute.";
      } else if (forti.length) {
        andamento = "Alcune coppie seguono un andamento lineare simile: " +
          forti.map(c => c.colonne.join(" e ")).join("; ") +
          ". Questo non significa che le colonne siano identiche.";
      }
      const riga = (titolo, descrizione) =>
        '<div class="question-item"><strong>' + escapeHtml(titolo) + '</strong><p>' + escapeHtml(descrizione) + '</p></div>';
      const spiegazioni = [
        riga("Ci sono valori molto diversi dagli altri?", outlier),
        riga("Le colonne hanno dispersioni simili?", scale),
        riga("Alcune colonne cambiano insieme?", andamento)
      ];
      if (d.covarianzaSingolare) {
        spiegazioni.push(riga("Alcune informazioni si ripetono?",
          "La matrice delle relazioni lineari non è invertibile: alcune colonne dipendono linearmente dalle altre. È opportuno verificare se mantenerle tutte."));
      }
      if (d.colonneMancanti.length) {
        spiegazioni.push(riga("Ci sono celle vuote?",
          "Sì, nelle colonne: " + d.colonneMancanti.join(", ") + ". Prima di calcolare una distanza bisogna decidere come gestirle."));
      }
      const dettaglio = '<details><summary>Dettagli statistici e criteri usati</summary>' +
        '<p>Valori insoliti: regola di Tukey, fuori da [Q1 − 1,5·IQR; Q3 + 1,5·IQR]. Con pochi dati il controllo è indicativo. ' +
        'Dispersioni: confronto degli IQR, oppure delle deviazioni standard se IQR è nullo; rapporto oltre 2 come soglia esplorativa, non universale. ' +
        'Andamenti: correlazione di Pearson calcolata sulle coppie di valori disponibili; relazione forte se |r| ≥ 0,8, perfetta entro una tolleranza di 10⁻¹⁰.</p>' +
        '<p>Correlazioni: ' + (coppie.length
          ? coppie.map(c => escapeHtml(c.colonne.join(" / ") + ": r = " + formatoNumero(c.correlazione) + " (" + c.coppieComplete + " coppie)")).join("; ")
          : "nessuna coppia confrontabile") + '.</p>' +
        '<p>' + escapeHtml(d.motivoCovarianza || "") + '</p></details>';
      corpo.innerHTML = spiegazioni.join("") + dettaglio;
    } catch (errore) {
      if (versione !== versioneDiagnosi) return;
      corpo.textContent = "Non è stato possibile completare la diagnosi: " + errore.message;
    }
  }

  function richiedeRiscalamentoConfermato() {
    return tabellaInteramenteNumerica() &&
      !["relativo", "abbondanza", "frequenze"].includes(valoreRisposta("confrontoQuantitativo"));
  }

  function aggiornaVisibilitaTrasformazione() {
    const numerico = richiedeRiscalamentoConfermato();
    $("scaling-wrap").hidden = !numerico;
    $("confirm-numeric-scaling").hidden = !numerico || riscalamentoConfermato;
    $("numeric-scaling-status").textContent = !numerico ? ""
      : riscalamentoConfermato
        ? "Riscalamento confermato: puoi consultare la matrice e scegliere la misura."
        : "Verifica i metodi proposti e conferma prima di visualizzare la matrice trasformata.";
    const confermata = numerico && riscalamentoConfermato;
    $("preview-view-switch").hidden = !confermata;
    $("download-work").hidden = !confermata;
    $("download-work").disabled = !confermata;
    if (!confermata) vista = "originale";
    if (risultato) disegnaTabella();
  }

  function aggiornaFaseNumerica() {
    const numerico = richiedeRiscalamentoConfermato();
    const pronto = !numerico || riscalamentoConfermato;
    // Le domande devono essere visibili prima della conferma del riscalamento.
    $("adaptive-questions").hidden = false;
    $("prepare-comparison-plan").hidden = !pronto;
    aggiornaVisibilitaTrasformazione();
  }

  function confermaRiscalamentoNumerico() {
    if (!tabellaInteramenteNumerica()) return;
    const colonne = colonneNumericheSelezionate();
    if (!colonne.length) return;
    riscalamentoConfermato = true;
    interpretazione.riscalamentoConfermato = true;
    vista = "lavoro";
    nascondiPiano();
    aggiornaFaseNumerica();
    nascondiErrore();
  }

  function disegnaDiagnosi(diagnosi, completo) {
    if (!diagnosi) {
      $("comparison-diagnosis").innerHTML = "";
      return;
    }
    const indicatori = diagnosi.indicatori || {};
    const proposta = diagnosi.proposta || {};
    const elementi = [];
    elementi.push(["Famiglia rilevata", diagnosi.famiglia]);
    if (diagnosi.famigliaId === "quantitativo") {
      elementi.push(["Valori estremi", indicatori.outlier
        ? `Rilevati in: ${(indicatori.colonneOutlier || []).join(", ")}`
        : "Nessun outlier rilevante"]);
      elementi.push(["Dispersioni", `Rapporto massimo/minimo ${formatoNumero(indicatori.rapportoDispersioni)} · ${indicatori.dispersioniSimili ? "simili" : "differenti"}`]);
      elementi.push(["Zeri", indicatori.matriceSparsa
        ? "Almeno l’80% dei valori è zero: proposta max-abs"
        : "Matrice non classificata come sparsa"]);
      elementi.push(["Relazioni tra colonne", indicatori.correlazioniForti
        ? `Correlazione massima |r| = ${formatoNumero(indicatori.correlazioneMassimaAssoluta)}${indicatori.coppiaCorrelata?.length ? ` (${indicatori.coppiaCorrelata.join(" e ")})` : ""}`
        : `Nessuna correlazione forte · massimo |r| = ${formatoNumero(indicatori.correlazioneMassimaAssoluta)}`]);
      elementi.push(["Relazione tra le colonne", indicatori.covarianzaSingolare
        ? `Alcune colonne ripetono informazioni già presenti: ${indicatori.motivoCovarianza}`
        : indicatori.covarianzaUtilizzabile
          ? `La covarianza è invertibile. ${indicatori.motivoCovarianza}`
          : `Mahalanobis classica non è utilizzabile in modo affidabile. ${indicatori.motivoCovarianza || "Verifica non superata."}`]);
    } else if (diagnosi.famigliaId === "misto") {
      elementi.push(["Valori utilizzati", "Originali: nessun riscalamento preliminare"]);
      elementi.push(["Valori estremi quantitativi", indicatori.outlier
        ? `Rilevati in: ${(indicatori.colonneOutlier || []).join(", ")}`
        : "Non rilevati"]);
      elementi.push(["Valori mancanti", (indicatori.colonneMancanti || []).length
        ? `Presenti in: ${indicatori.colonneMancanti.join(", ")}`
        : "Assenti"]);
    }
    $("comparison-diagnosis").innerHTML = `<div class="diagnosis-heading">
      <div><p>Diagnosi automatica</p><h5>${escapeHtml(proposta.misura || "Proposta da completare")}</h5></div>
      <span>${completo ? "Proposta pronta" : "Da confermare"}</span>
    </div>
    <div class="diagnosis-grid">${elementi.map(([etichetta, valore]) => `<div>
      <small>${escapeHtml(etichetta)}</small><strong>${escapeHtml(valore)}</strong>
    </div>`).join("")}</div>
    <p>${escapeHtml(proposta.motivo || "")}</p>
    ${diagnosi.conferma ? `<em>${escapeHtml(diagnosi.conferma)}</em>` : ""}`;
  }


  const guidaMisureNumeriche = {
  "euclidean": [
    "Riassume quanto due righe differiscono nel complesso. Gli scarti grandi incidono più di quelli piccoli.",
    "Uno scarto molto grande può influenzare sensibilmente il risultato.",
    "Se preferisci sommare semplicemente gli scarti, valuta Manhattan.",
    "d(x,y)=\\sqrt{\\sum_k(x_k-y_k)^2}"
  ],
  "standardized_euclidean": [
    "Confronta le differenze rispetto alla variabilità osservata delle colonne.",
    "La variabilità non coincide necessariamente con l'importanza della caratteristica.",
    "Se preferisci la somma degli scarti, valuta Manhattan dopo un riscalamento appropriato.",
    "d(x,y)=\\sqrt{\\sum_k(x_k-y_k)^2/s_k^2}"
  ],
  "manhattan": [
    "Somma tutte le differenze tra le colonne, senza elevarle al quadrato.",
    "Anche tante differenze moderate possono produrre un risultato elevato.",
    "Se vuoi dare più rilievo agli scarti grandi, valuta Euclidea.",
    "d(x,y)=\\sum_k|x_k-y_k|"
  ],
  "chebyshev": [
    "Considera soltanto la differenza più grande tra le colonne.",
    "Le altre differenze non modificano il risultato finché restano inferiori alla maggiore.",
    "Se vuoi considerare anche gli altri scarti, valuta Manhattan o Euclidea.",
    "d(x,y)=\\max_k|x_k-y_k|"
  ],
  "minkowski": [
    "Permette di regolare quanto le differenze più grandi incidono sul confronto.",
    "Il risultato dipende dall'esponente q; con q=1 coincide con Manhattan, con q=2 con Euclidea.",
    "Puoi scegliere direttamente Manhattan o Euclidea se non vuoi regolare q.",
    "d(x,y)=(\\sum_k|x_k-y_k|^q)^{1/q}"
  ],
  "weighted_minkowski": [
    "Permette di dare importanze diverse alle colonne e regolare l'effetto degli scarti grandi.",
    "I pesi esprimono una scelta sul significato delle caratteristiche, non una loro importanza oggettiva.",
    "Se tutte le colonne devono contare allo stesso modo, valuta Minkowski senza pesi.",
    "d(x,y)=(\\sum_k w_k|x_k-y_k|^q)^{1/q}"
  ],
  "weighted_chebyshev": [
    "Considera la differenza più grande dopo aver applicato l'importanza scelta per ciascuna colonna.",
    "Le altre differenze non influenzano il risultato finché non diventano la maggiore.",
    "Se non vuoi usare pesi diversi, valuta Chebyshev.",
    "d(x,y)=\\max_k w_k|x_k-y_k|"
  ],
  "mahalanobis": [
    "Considera come le colonne variano insieme, anziché trattarle come completamente indipendenti.",
    "Richiede una covarianza utilizzabile: la correlazione tra colonne non basta, da sola, a renderla preferibile.",
    "Se non vuoi tenere conto di queste relazioni, valuta Euclidea o Manhattan.",
    "d(x,y)=\\sqrt{(x-y)^\\top S^{-1}(x-y)}"
  ],
  "canberra": [
    "Confronta gli scarti in proporzione alla grandezza dei valori di ciascuna colonna.",
    "Valori vicini a zero possono fare incidere molto anche differenze assolute piccole.",
    "Se ti interessano quantità complessive non negative, valuta Bray–Curtis.",
    "d(x,y)=\\sum_k\\frac{|x_k-y_k|}{|x_k|+|y_k|}"
  ],
  "bray_curtis": [
    "Confronta le quantità complessive, rapportando la somma delle differenze al totale.",
    "Richiede valori non negativi e non è definita per due righe entrambe nulle; in generale non è una metrica.",
    "Se vuoi considerare gli scarti relativi per singola colonna, valuta Canberra.",
    "d(x,y)=\\frac{\\sum_k|x_k-y_k|}{\\sum_k(x_k+y_k)}"
  ],
  "chi_square": [
    "Dà più rilievo alle differenze nelle colonne che presentano valori complessivamente piccoli.",
    "Richiede valori non negativi; è importante che tale enfasi sia coerente con il significato dei dati.",
    "Se non vuoi questa enfasi, valuta Bray–Curtis.",
    "d(x,y)=\\sqrt{\\sum_k\\frac{(x_k-y_k)^2}{x_k+y_k}}"
  ]
};

  function spiegazioneMisuraNumerica(percorso) {
    const guida = guidaMisureNumeriche[percorso.idMisura];
    if (!guida) return "";
    const diagnosi = percorso.diagnosiAutomatica || {};
    const manuale = !["", "automatico"].includes(interpretazione.misuraNumericaManuale || "automatico");
    let motivo = manuale
      ? "Hai selezionato questa misura al posto della proposta automatica."
      : "La proposta deriva dalle tue risposte e dalle caratteristiche rilevate.";
    if (!manuale && percorso.idMisura === "manhattan" && diagnosi.outlier) {
      motivo = "Sono stati rilevati valori estremi: questo confronto non eleva al quadrato gli scarti.";
    }
    if (!manuale && percorso.idMisura === "mahalanobis" && diagnosi.correlazioniForti) {
      motivo = "Alcune colonne variano insieme e la covarianza ha superato i controlli numerici.";
    }
    const cautele = [guida[1]];
    if (diagnosi.covarianzaSingolare) {
      cautele.push("Alcune colonne contengono informazioni linearmente dipendenti: una distanza come l'Euclidea può contare più volte la stessa informazione. Valuta se mantenere tutte le colonne sia una scelta intenzionale.");
    }
    if (diagnosi.campioneLimitato && !diagnosi.covarianzaSingolare) {
      cautele.push("Il numero di righe è limitato rispetto alle colonne: le stime delle relazioni statistiche potrebbero essere poco stabili.");
    }
    if ((diagnosi.colonneCostanti || []).length) {
      cautele.push("Le colonne costanti non distinguono le righe: " + diagnosi.colonneCostanti.join(", ") + ".");
    }
    if ((diagnosi.colonneMancanti || []).length) {
      cautele.push("Sono presenti valori mancanti: occorre gestirli prima del calcolo.");
    }
    const contenitore = document.createElement("div");
    contenitore.className = "numeric-measure-explanation";
    const sezione = (titolo, testo) => {
      const p = document.createElement("p");
      const strong = document.createElement("strong");
      strong.textContent = titolo + " ";
      p.append(strong, document.createTextNode(testo));
      contenitore.appendChild(p);
    };
    sezione("Perché questa scelta?", motivo + " " + guida[0]);
    sezione("Quando fare attenzione?", cautele.join(" "));
    sezione("Che cosa cambierebbe?", guida[2]);
    const dettaglio = document.createElement("details");
    const sommario = document.createElement("summary");
    sommario.textContent = "Approfondimento matematico";
    const formula = document.createElement("p");
    formula.textContent = "Formula: " + guida[3];
    const proprieta = document.createElement("p");
    proprieta.textContent = "Proprietà: " + (percorso.proprieta || "");
    dettaglio.append(sommario, formula, proprieta);
    if (Object.keys(percorso.parametri || {}).length) {
      const parametri = document.createElement("p");
      parametri.textContent = "Parametri utilizzati: " + JSON.stringify(percorso.parametri);
      dettaglio.appendChild(parametri);
    }
    contenitore.appendChild(dettaglio);
    return contenitore.outerHTML;
  }

  function controlloDipendenzaLineare(percorso) {
    if (!percorso.diagnosiAutomatica?.covarianzaSingolare) return "";
    const scelta = interpretazione.gestioneDipendenzaLineare || "";
    return `<div class="question-item">
      <label for="numeric-dependency-choice"><strong>Alcune colonne riportano informazioni già contenute in altre. Come vuoi procedere?</strong></label>
      <p>Non è un errore del file. Se mantieni tutte le colonne, questa informazione ripetuta può influenzare più volte il risultato. Mahalanobis classica non può essere calcolata su queste colonne perché la covarianza è singolare.</p>
      <select id="numeric-dependency-choice">
        <option value=""${scelta === "" ? " selected" : ""}>Devo ancora decidere</option>
        <option value="mantieni"${scelta === "mantieni" ? " selected" : ""}>Voglio mantenere tutte le colonne e accetto questo effetto</option>
        <option value="rivedi"${scelta === "rivedi" ? " selected" : ""}>Preferisco rivedere le colonne da utilizzare</option>
      </select>
      <p>Se vuoi togliere le colonne ripetute, torna alla sezione «Usarla per confrontare le righe?» e deselezionale.</p>
    </div>`;
  }

  function editorMisuraNumerica(percorso) {
    const opzioni = [
      ["automatico", "Usa la misura proposta dal sito"],
      ["euclidean", "Vicinanza complessiva (euclidea)"], ["manhattan", "Somma le differenze (Manhattan)"],
      ["chebyshev", "Conta la maggiore differenza (Chebyshev)"], ["minkowski", "Regola l’importanza degli scarti (Minkowski)"],
      ["weighted_minkowski", "Dai importanza diversa alle colonne (Minkowski pesata)"],
      ["weighted_chebyshev", "Conta la maggiore differenza ponderata (Chebyshev pesata)"],
      ["mahalanobis", "Considera come le colonne variano insieme (Mahalanobis)"], ["canberra", "Confronta gli scarti relativi (Canberra)"],
      ["bray_curtis", "Confronta quantità complessive (Bray–Curtis)"], ["chi_square", "Dai rilievo alle componenti piccole (chi-quadrato)"]
    ];
    const scelta = interpretazione.misuraNumericaManuale || "automatico";
    const esponente = ["minkowski", "weighted_minkowski"].includes(scelta);
    const pesata = ["weighted_minkowski", "weighted_chebyshev"].includes(scelta);
    const colonne = percorso.colonne;
    return `<div class="numeric-measure-editor">
      <label for="numeric-measure-choice"><strong>Come vuoi confrontare le righe?</strong></label>
      <select id="numeric-measure-choice">
        ${opzioni.map(([id, nome]) => `<option value="${id}"${id === scelta ? " selected" : ""}>${escapeHtml(nome)}</option>`).join("")}
      </select>
      <p>Non serve conoscere il nome delle misure: scegli l’obiettivo che preferisci. Il sito verifica se è compatibile con i dati.</p>
      ${esponente ? `<label for="numeric-measure-q">Quanto vuoi dare rilievo alle differenze grandi? (q ≥ 1)</label><p>Con 1 sommi tutte le differenze; con 2 quelle grandi hanno maggiore influenza. Per altre scelte serve un valore almeno pari a 1.</p><input id="numeric-measure-q" type="number" min="1" step="0.5" value="${escapeHtml(interpretazione.ordineMisuraManuale || "2")}">` : ""}
      ${pesata ? `<label for="numeric-measure-weights">Quanto conta ogni colonna? ${colonne.map(escapeHtml).join(", ")}</label><input id="numeric-measure-weights" type="text" value="${escapeHtml(interpretazione.pesiMisuraManuale || colonne.map(() => "1").join("; "))}"><small>Inserisci un numero positivo per colonna, separando con punto e virgola. Usa 1 per tutte se devono avere la stessa importanza.</small>` : ""}
      <button class="secondary-action" id="apply-numeric-measure" type="button">Applica misura</button>
    </div>`;
  }

  function disegnaPiano(piano) {
    pianoCorrente = piano;
    matriceCorrente = null;
    $("gower-result").hidden = true;
    disegnaDiagnosi(piano.diagnosi, piano.completo);
    $("comparison-plan-paths").innerHTML = piano.percorsi.map((percorso, indice) => {
      const classe = percorso.stato === "da_completare" ? " incomplete" : "";
      const pre = percorso.preelaborazione;
      const mancanti = percorso.mancanti;
      const passi = pre.passi.length
        ? pre.passi.map(passo => `${escapeHtml(passo.colonna)}: ${escapeHtml(passo.etichetta)}`).join(" · ")
        : "Nessuna trasformazione colonna per colonna";
      const calcolo = percorso.calcolo.disponibile
        ? "Calcolo disponibile"
        : percorso.stato === "da_completare" ? "Completa la configurazione" : "Calcolo non ancora collegato";
      const pesiGower = Object.entries(percorso.pesiGower || {}).map(([nome, peso]) =>
        escapeHtml(nome) + ": " + formatoNumero(peso)
      ).join(" · ");
      const escluseGower = (percorso.colonneEscluseGower || []).map(escapeHtml).join(", ");
      const parametri = Object.entries(percorso.parametri || {}).map(([chiave, valore]) =>
        `${escapeHtml(chiave)} = ${escapeHtml(Array.isArray(valore) ? valore.join(", ") : valore)}`
      ).join(" · ");
      const editorNumerico = percorso.tipo === "numerico" ? editorMisuraNumerica(percorso) : "";
      const pesoAggregazione = piano.conteggioPercorsi > 1
        ? `<label class="path-weight-label">Quanto conta questo percorso nella matrice finale?
            <input class="path-weight" type="number" min="0.01" step="0.1"
              data-path-id="${escapeHtml(percorso.idPercorso)}"
              value="${escapeHtml(percorso.pesoAggregazione)}">
            <small>Il valore proposto è 1: tutti i percorsi hanno la stessa importanza.</small>
          </label>`
        : "";
      const alternative = (percorso.alternative || []).length
        ? `<div class="path-alternatives"><b>Alternative da valutare</b><ul>${percorso.alternative.map(alternativa =>
          `<li><strong>${escapeHtml(alternativa.nome)}</strong>: ${escapeHtml(alternativa.motivo)}</li>`
        ).join("")}</ul></div>`
        : "";
      return `<article class="plan-path${classe}">
        <p>Percorso ${indice + 1}</p>
        <h5>${escapeHtml(percorso.titolo)}</h5>
        <strong>${escapeHtml(percorso.metodo)}</strong>
        <small>Dati: ${percorso.colonne.map(escapeHtml).join(", ")}</small>
        <dl class="path-contract">
          <div><dt>Origine</dt><dd>${escapeHtml(pre.etichettaOrigine)}</dd></div>
          <div><dt>Trasformazioni</dt><dd>${passi}</dd></div>
          ${parametri ? `<div><dt>Parametri</dt><dd>${parametri}</dd></div>` : ""}
          ${pesiGower ? `<div><dt>Pesi Gower</dt><dd>${pesiGower}</dd></div>` : ""}
          ${escluseGower ? `<div><dt>Colonne senza variabilità</dt><dd>Escluse dal denominatore: ${escluseGower}</dd></div>` : ""}
          <div><dt>Mancanti</dt><dd>${escapeHtml(mancanti.descrizione)}</dd></div>
          ${percorso.proprieta ? `<div><dt>Proprietà</dt><dd>${escapeHtml(percorso.proprieta)}</dd></div>` : ""}
          <div><dt>Stato</dt><dd>${escapeHtml(calcolo)}</dd></div>
        </dl>
        <span>${escapeHtml(pre.descrizione)}</span>
        ${percorso.tipo === "numerico" ? spiegazioneMisuraNumerica(percorso) : `<p>${escapeHtml(percorso.motivo)}</p>`}
        ${percorso.tipo === "numerico" ? controlloDipendenzaLineare(percorso) : ""}
        ${percorso.notaPreelaborazione ? `<p><strong>Quali valori vengono usati:</strong> ${escapeHtml(percorso.notaPreelaborazione)}</p>` : ""}
        ${pesoAggregazione}
        ${editorNumerico}
        ${alternative}
      </article>`;
    }).join("");
    $("comparison-plan-body").innerHTML = piano.blocchi.length
      ? piano.blocchi.map(blocco => {
        const classe = blocco.stato === "da_completare"
          ? "plan-row-incomplete"
          : blocco.stato === "attenzione" ? "plan-row-warning" : "";
        const dati = blocco.colonne.length > 1
          ? `${escapeHtml(blocco.nome)}<small>${blocco.colonne.map(escapeHtml).join(", ")}</small>`
          : escapeHtml(blocco.nome);
        return `<tr class="${classe}">
          <th scope="row">${dati}</th>
          <td>${escapeHtml(blocco.interpretazione)}</td>
          <td>${escapeHtml(blocco.misura)}</td>
          <td>${escapeHtml(blocco.motivo)}</td>
        </tr>`;
      }).join("")
      : `<tr><td colspan="4">Non è ancora disponibile alcun blocco di confronto.</td></tr>`;

    const avvisiBlocchi = piano.blocchi.flatMap(blocco =>
      blocco.avvisi.map(avviso => `${blocco.nome}: ${avviso}`)
    );
    const avvisiPercorsi = piano.percorsi.flatMap(percorso =>
      (percorso.avvisi || []).map(avviso => `${percorso.titolo}: ${avviso}`)
    );
    const avvisi = [...piano.avvisi, ...avvisiBlocchi, ...avvisiPercorsi];
    $("comparison-plan-warnings").innerHTML = avvisi.length
      ? `<p><strong>Prima del calcolo:</strong></p><ul>${avvisi.map(avviso => `<li>${escapeHtml(avviso)}</li>`).join("")}</ul>`
      : "";
    $("comparison-plan-intro").textContent = !piano.completo
      ? "Il piano è stato preparato, ma alcune informazioni devono ancora essere completate."
      : piano.conteggioPercorsi === 1
        ? "È stato individuato un unico percorso di confronto."
        : `Sono stati individuati ${piano.conteggioPercorsi} percorsi. Il sito li renderà confrontabili e produrrà una sola matrice complessiva usando le importanze indicate.`;
    const percorsiCalcolabili = piano.percorsi.filter(percorso => percorso.calcolo.disponibile);
    $("gower-actions").hidden = !(
      piano.completo && piano.conteggioPercorsi > 0
      && percorsiCalcolabili.length === piano.conteggioPercorsi
    );
    if (percorsiCalcolabili.length) {
      $("calculate-gower").textContent = "Calcola la matrice finale";
    }
    $("comparison-plan").hidden = false;
    aggiornaVisibilitaTrasformazione();
  }

  function disegnaMatrice(risposta) {
    const limite = Math.min(12, risposta.etichette.length);
    const etichette = risposta.etichette.slice(0, limite);
    $("gower-matrix-head").innerHTML = `<tr><th>Riga</th>${etichette.map(etichetta => `<th>${escapeHtml(etichetta)}</th>`).join("")}</tr>`;
    $("gower-matrix-body").innerHTML = risposta.matrice.slice(0, limite).map((riga, indice) => `<tr>
      <th scope="row">${escapeHtml(etichette[indice])}</th>
      ${riga.slice(0, limite).map(valore => `<td>${valore === null ? "—" : escapeHtml(formatoNumero(valore))}</td>`).join("")}
    </tr>`).join("");
    $("gower-result-title").textContent = risposta.metodo;
    $("gower-result-caption").textContent = `${risposta.etichette.length} × ${risposta.etichette.length}. ${risposta.nota}${limite < risposta.etichette.length ? ` Anteprima delle prime ${limite} righe.` : ""}`;
    $("download-gower").disabled = false;
    $("gower-result").hidden = false;
  }

  async function calcolaMatrice() {
    if (!pianoCorrente) return;
    const pulsante = $("calculate-gower");
    const testo = pulsante.textContent;
    pulsante.disabled = true;
    pulsante.textContent = "Calcolo…";
    try {
      matriceCorrente = await P.calcolaMatrice(testoOriginale, scelte, interpretazione);
      nascondiErrore();
      disegnaMatrice(matriceCorrente);
    } catch (errore) {
      mostraErrore(errore.message);
    } finally {
      pulsante.disabled = false;
      pulsante.textContent = testo;
    }
  }

  function scaricaMatrice() {
    if (!matriceCorrente) return;
    const url = URL.createObjectURL(new Blob(["\uFEFF" + matriceCorrente.csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "matrice_distanze.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function preparaPiano() {
    const pulsante = $("prepare-comparison-plan");
    const testo = pulsante.textContent;
    pulsante.disabled = true;
    pulsante.textContent = "Preparazione…";
    try {
      const piano = await P.creaPiano(testoOriginale, scelte, interpretazione);
      nascondiErrore();
      disegnaPiano(piano);
    } catch (errore) {
      mostraErrore(errore.message);
    } finally {
      pulsante.disabled = false;
      pulsante.textContent = testo;
    }
  }

  function creaGruppo() {
    const numero = interpretazione.prossimoGruppo++;
    const gruppo = { id: `gruppo-${numero}`, nome: `Gruppo ${numero}`, tipo: "altro" };
    interpretazione.gruppi.push(gruppo);
    return gruppo;
  }

  function opzioniGruppo(selezionato) {
    const gruppi = interpretazione.gruppi.map(gruppo =>
      `<option value="${gruppo.id}"${selezionato === gruppo.id ? " selected" : ""}>${escapeHtml(gruppo.nome)}</option>`
    ).join("");
    return `<option value=""${!selezionato ? " selected" : ""}>Caratteristica indipendente</option>${gruppi}<option value="__nuovo__">+ Crea un nuovo gruppo</option>`;
  }

  function disegnaGruppi() {
    const profili = risultato.questionario.colonne;
    const incluse = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa);
    profili.filter(profilo => !interpretazione.colonne[profilo.nome]?.usa).forEach(profilo => {
      delete interpretazione.assegnazioni[profilo.nome];
    });
    const indipendenti = incluse.filter(profilo => !interpretazione.assegnazioni[profilo.nome]);
    const gruppiAttivi = interpretazione.gruppi.map(gruppo => ({
      gruppo,
      membri: incluse.filter(profilo => interpretazione.assegnazioni[profilo.nome] === gruppo.id)
    })).filter(elemento => elemento.membri.length);
    $("group-summary").innerHTML =
      `<p><strong>Caratteristiche indipendenti (${indipendenti.length}):</strong> ${indipendenti.length ? indipendenti.map(p => escapeHtml(p.nome)).join(", ") : "nessuna"}.</p>` +
      (gruppiAttivi.length
        ? `<p><strong>Gruppi strutturati (${gruppiAttivi.length}):</strong> ${gruppiAttivi.map(({ gruppo, membri }) => escapeHtml(gruppo.nome) + " (" + membri.map(p => escapeHtml(p.nome)).join(", ") + ")").join("; ")}.</p>`
        : "<p>Nessuna colonna assegnata a un gruppo. Puoi crearne più di uno, lasciando le altre colonne indipendenti.</p>");
    $("group-assignment-body").innerHTML = incluse.length ? incluse.map(profilo => `<tr>
      <th scope="row">${escapeHtml(profilo.nome)}</th>
      <td><select class="column-choice group-assignment" data-group-column="${escapeHtml(profilo.nome)}" aria-label="Gruppo della colonna ${escapeHtml(profilo.nome)}">${opzioniGruppo(interpretazione.assegnazioni[profilo.nome] || "")}</select></td>
    </tr>`).join("") : `<tr><td colspan="2">Non è stata inclusa alcuna colonna nel confronto.</td></tr>`;

    $("group-config-list").innerHTML = interpretazione.gruppi.map(gruppo => {
      const membri = incluse.filter(profilo => interpretazione.assegnazioni[profilo.nome] === gruppo.id).map(profilo => profilo.nome);
      const tipi = membri.map(nome => risultato.colonne.find(colonna => colonna.nome === nome)?.tipo);
      const tutteNumeriche = tipi.length >= 2 && tipi.every(tipo => tipo === "numerica" || tipo === "numerica_costante");
      const tutteQuantitative = tutteNumeriche && membri.every(nome => interpretazione.colonne[nome]?.ruolo === "quantita");
      const nota = membri.length < 2
        ? "Assegna almeno due colonne a questo gruppo."
        : !tutteQuantitative && gruppo.tipo !== "altro"
          ? "Per questa interpretazione servono quantità numeriche: verifica che non siano codici o livelli."
          : `Colonne: ${membri.join(", ")}.`;
      return `<div class="group-config" data-group-id="${gruppo.id}">
        <label>Nome del gruppo<input class="group-name" value="${escapeHtml(gruppo.nome)}" aria-label="Nome di ${escapeHtml(gruppo.nome)}"></label>
        <label>Che cosa formano insieme?<select class="group-type" aria-label="Tipo di ${escapeHtml(gruppo.nome)}">
          <option value="altro"${gruppo.tipo === "altro" ? " selected" : ""}>Da specificare</option>
          <option value="ripetute"${gruppo.tipo === "ripetute" ? " selected" : ""}>Misurazioni dello stesso profilo</option>
          <option value="tempo"${gruppo.tipo === "tempo" ? " selected" : ""}>Osservazioni successive nel tempo</option>
          <option value="parti"${gruppo.tipo === "parti" ? " selected" : ""}>Parti dello stesso totale</option>
        </select></label>
        <p>${escapeHtml(nota)}</p>
        <button class="remove-group" type="button">Rimuovi gruppo</button>
      </div>`;
    }).join("");
  }

  function domandeConfigurazioneGower(profili) {
    if (!profili.length) return "";
    const campi = [];
    const mancantiCSV = new Set(["", "na", "n/a", "null", "?"]);
    const rispostaMancanti = valoreRisposta("significatoMancanti");
    const rispostaZeri = valoreRisposta("zeriCondivisi");
    const rispostaOrdini = valoreRisposta("ordineLivelli");

    function menu(chiave, colonna, etichetta, opzioni, valore) {
      return '<label><strong>' + escapeHtml(etichetta) + '</strong>' +
        '<select class="gower-setting" data-gower-key="' + chiave + '" data-gower-column="' +
        escapeHtml(colonna) + '">' +
        opzioni.map(op => '<option value="' + escapeHtml(op[0]) + '"' +
          (String(valore || "") === op[0] ? " selected" : "") + '>' +
          escapeHtml(op[1]) + '</option>').join("") + '</select></label>';
    }

    campi.push('<div class="question-item"><strong>Configurazione delle caratteristiche in Gower</strong>' +
      '<p>Ogni caratteristica contribuisce secondo il suo tipo. Puoi assegnare un peso positivo a ciascuna ' +
      'colonna: 1 significa importanza uguale; 2 significa contributo doppio, a parità di disponibilità.</p></div>');
    for (const profilo of profili) {
      const nome = profilo.nome;
      const ruolo = interpretazione.colonne[nome]?.ruolo;
      const indice = risultato.originale.intestazioni.indexOf(nome);
      const osservati = risultato.originale.righe.map(r => String(r[indice]).trim()).filter(
        valore => !mancantiCSV.has(valore.toLocaleLowerCase())
      );
      const distinti = [...new Set(osservati)];
      const tipo = risultato.colonne.find(c => c.nome === nome)?.tipo;
      let elementi = '<div class="question-item"><strong>' + escapeHtml(nome) + '</strong>';
      const peso = interpretazione.pesiGower?.[nome] ?? "1";
      elementi += '<label>Importanza di questa caratteristica (peso positivo)' +
        '<input class="gower-setting" data-gower-key="pesiGower" data-gower-column="' +
        escapeHtml(nome) + '" type="text" value="' + escapeHtml(peso) +
        '" placeholder="1"></label>';

      if (risultato.colonne.find(c => c.nome === nome)?.mancanti > 0) {
        const opzioni = [["", "Segui la risposta generale sulle caselle vuote"],
          ["escludi", "Valore non disponibile: ignora questa colonna per la coppia"]];
        if (["categoria", "binaria", "presenza"].includes(ruolo))
          opzioni.push(["assenza", "Casella vuota = assenza (stato o categoria distinta)"]);
        if (ruolo === "quantita")
          opzioni.push(["zero", "Confermo esplicitamente che vuoto significa quantità zero"]);
        elementi += menu("mancantiPerColonna", nome, "Come trattare i valori vuoti di questa colonna?",
          opzioni, interpretazione.mancantiPerColonna?.[nome] || "");
        if (rispostaMancanti === "assenza" && !["categoria", "binaria", "presenza"].includes(ruolo))
          elementi += '<p>Per questa colonna, «assenza» non è uno zero automatico: scegli esplicitamente come trattarla.</p>';
      }

      if (ruolo === "presenza") {
        elementi += menu("zeriCondivisiPerColonna", nome, "Le assenze condivise contano?",
          [["", "Segui la risposta generale"],
            ["si", "Sì, contano"], ["no", "No, escludile dal confronto"]],
          interpretazione.zeriCondivisiPerColonna?.[nome] || "");
        const valoriPresenti = distinti.map(v => [v, "La presenza è indicata da: " + v]);
        elementi += menu("presenzaPositivaPerColonna", nome, "Quale valore indica la presenza?",
          [["", "Riconosci automaticamente 1/sì/vero, se possibile"], ...valoriPresenti],
          interpretazione.presenzaPositivaPerColonna?.[nome] || "");
        if (rispostaZeri === "dipende")
          elementi += '<p>Hai scelto «dipende»: specifica sopra se le assenze contano per questa colonna.</p>';
      }

      if (ruolo === "livello") {
        elementi += menu("ordinePerColonna", nome, "I livelli di questa colonna sono ordinati?",
          [["", "Segui la risposta generale"],
            ["si", "Sì, hanno un ordine"], ["no", "No, sono semplici categorie"]],
          interpretazione.ordinePerColonna?.[nome] || "");
        const ordinale = interpretazione.ordinePerColonna?.[nome] || rispostaOrdini;
        if (ordinale === "si" && tipo === "non_numerica") {
          elementi += '<label>Elenca i livelli dal più basso al più alto, separati da ;' +
            '<input class="gower-setting" data-gower-key="ordiniLivelliGower" data-gower-column="' +
            escapeHtml(nome) + '" type="text" value="' +
            escapeHtml(interpretazione.ordiniLivelliGower?.[nome] || "") +
            '" placeholder="es. basso; medio; alto"></label>';
          elementi += '<p>Livelli osservati (senza un ordine implicito): ' +
            escapeHtml(distinti.join(", ")) +
            '. Inseriscili tutti una sola volta nell’ordine corretto.</p>';
        }
      }
      elementi += '</div>';
      campi.push(elementi);
    }
    return campi.join("");
  }

  function domandeMancantiNumerici(colonne) {
    if (!colonne.length) return "";
    if (!interpretazione.mancantiNumericiPerColonna) {
      interpretazione.mancantiNumericiPerColonna = {};
    }
    const opzioni = [
      ["", "Scegli una strategia"],
      ["escludi_riga", "Non usare le righe in cui questo valore manca"],
      ["imputa_mediana", "Sostituisci con il valore centrale (mediana)"],
      ["imputa_media", "Sostituisci con il valore medio"],
      ["zero", "Confermo che la casella vuota significa davvero zero"]
    ];
    return '<div class="question-item"><strong>Come trattare le caselle vuote nelle quantità?</strong>' +
      '<p>La scelta è separata per colonna. Escludere una riga riduce i dati disponibili; ' +
      'sostituire un valore introduce un’ipotesi esplicita. Il sito userà la stessa scelta ' +
      'nell’anteprima e nella matrice finale.</p></div>' +
      colonne.map(colonna => {
        const valore = interpretazione.mancantiNumericiPerColonna[colonna.nome] || "";
        return '<div class="question-item"><label><strong>' + escapeHtml(colonna.nome) +
          ': che cosa facciamo quando il valore manca?</strong><select class="numeric-missing-setting" ' +
          'data-numeric-missing-column="' + escapeHtml(colonna.nome) + '">' +
          opzioni.map(([id, etichetta]) => '<option value="' + id + '"' +
            (valore === id ? ' selected' : '') + '>' + escapeHtml(etichetta) + '</option>')
            .join("") + '</select></label></div>';
      }).join("");
  }

  function disegnaQuestionario() {
    nascondiPiano();
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
      </tr>`;
    }).join("");
    disegnaGruppi();
    mostraDiagnosiPreliminare();
    disegnaMetodi();
    aggiornaFaseNumerica();

    const profiliInclusi = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa);
    const nomiInclusi = new Set(profiliInclusi.map(profilo => profilo.nome));
    const colonneIncluse = risultato.colonne.filter(colonna => nomiInclusi.has(colonna.nome));
    const ruoliInclusi = new Set(profiliInclusi.map(profilo => interpretazione.colonne[profilo.nome].ruolo));
    const domande = [];
    if (colonneIncluse.some(colonna => colonna.mancanti > 0)) domande.push(domandaAdattiva(
      "significatoMancanti", "Che cosa significa una casella vuota?",
      "Un valore sconosciuto viene escluso per la coppia; una vera assenza, se confermata per la colonna, viene trattata come uno stato osservato.",
      [["sconosciuto", "Il valore non è conosciuto"], ["non_applicabile", "La domanda non si applica"], ["assenza", "Indica assenza"], ["misto", "Dipende dalla colonna"], ["ignoto", "Non lo so"]]
    ));
    if (colonneIncluse.some(colonna => colonna.statistiche?.estremi > 0)) domande.push(domandaAdattiva(
      "significatoEstremi", "Alcuni valori sono molto lontani dagli altri: sono corretti?",
      "Il sito li ha individuati automaticamente. Indica se rappresentano situazioni reali o possibili errori.",
      [["reali", "Sì, confermo che sono casi reali"], ["errori", "No, probabilmente sono errori"], ["controllare", "Voglio controllarli prima del calcolo"], ["ignoto", "Non lo so"]]
    ));
    if (ruoliInclusi.has("presenza")) domande.push(domandaAdattiva(
      "zeriCondivisi", "Due assenze in comune rendono simili due righe?",
      "Nella Gower con presenze asimmetriche, due assenze condivise non forniscono un contributo. Puoi modificare questa scelta per ciascuna colonna.",
      [["si", "Sì, anche l’assenza in comune conta"], ["no", "No, contano soprattutto le presenze"], ["dipende", "Dipende dalla colonna"], ["ignoto", "Non lo so"]]
    ));
    if (ruoliInclusi.has("livello")) domande.push(domandaAdattiva(
      "ordineLivelli", "Nei livelli, l’ordine ha davvero significato?",
      "Per esempio, basso–medio–alto ha un ordine; rosso–verde–blu no.",
      [["si", "Sì, l’ordine è importante"], ["no", "No, sono soltanto etichette"], ["dipende", "Dipende dalla colonna"], ["ignoto", "Non lo so"]]
    ));
    if (ruoliInclusi.has("data")) domande.push(domandaAdattiva(
      "usoDate", "Come devono essere considerate le date?",
      "Una data può essere soltanto descrittiva oppure contribuire al confronto.",
      [["escludi", "Non devono influire sul confronto"], ["vicinanza", "Date vicine significano casi simili"], ["durata", "Conta il tempo trascorso"], ["ordine", "Conta soltanto quale viene prima"], ["ignoto", "Non lo so"]]
    ));

    const ruoliStandard = new Set(["quantita", "livello", "presenza", "binaria", "categoria", "data"]);
    const indipendentiStandard = profiliInclusi.filter(profilo =>
      !interpretazione.assegnazioni[profilo.nome] && ruoliStandard.has(interpretazione.colonne[profilo.nome].ruolo)
    );
    const quantitativeIndipendenti = colonneNumericheSelezionate();
    const percorsoNumerico = indipendentiStandard.length > 0 && indipendentiStandard.every(profilo => {
      const colonna = risultato.colonne.find(elemento => elemento.nome === profilo.nome);
      return interpretazione.colonne[profilo.nome].ruolo === "quantita"
        && ["numerica", "numerica_costante"].includes(colonna?.tipo);
    });
    if (percorsoNumerico) {
      const quantitativeConMancanti = quantitativeIndipendenti.filter(
        colonna => colonna.mancanti > 0
      );
      if (quantitativeConMancanti.length) {
        domande.push(domandeMancantiNumerici(quantitativeConMancanti));
      }
      domande.push(domandaAdattiva(
        "confrontoQuantitativo", "Che cosa rappresentano i numeri che vuoi confrontare?",
        "Scegli la risposta più vicina ai tuoi dati. Non occorre conoscere alcuna formula.",
        [["assoluto", "Misure di caratteristiche, per esempio età, altezza o temperatura"], ["abbondanza", "Quantità o conteggi, per esempio specie, prodotti o eventi"], ["frequenze", "Frequenze: voglio dare rilievo anche alle componenti rare"], ["relativo", "Misure per cui conta soprattutto la differenza percentuale o proporzionale"], ["ignoto", "Non lo so — usa la scelta consigliata"]]
      ));

      const confronto = valoreRisposta("confrontoQuantitativo");
      if (confronto === "ignoto") domande.push(notaAutomatica(
        "Scelta consigliata automatica",
        "Il sito proporrà una scelta motivata dalla diagnosi, da confermare. I valori estremi e le correlazioni sono indizi, non regole che determinano automaticamente la misura corretta."
      ));
      if (confronto === "assoluto") {
        if (quantitativeIndipendenti.length >= 2) domande.push(domandaAdattiva(
          "dipendenzaCoordinate", "Vuoi considerare anche il modo in cui queste caratteristiche variano insieme?",
          "Il sito ha già analizzato le correlazioni. Rispondere sì significa valutare Mahalanobis, se la covarianza è utilizzabile; rispondere no significa confrontare gli scarti senza correggere le dipendenze.",
          [["ignoto", "Non lo so: usa la scelta guidata"], ["no", "No, confronta le differenze tra le caratteristiche"], ["si", "Sì, considera le relazioni statistiche"]],
          "ignoto"
        ));
        domande.push(notaAutomatica(
          "Scelta automatica della misura",
          "Il sito ha analizzato valori estremi, dispersioni e correlazioni. La tua scelta determinerà la misura; i riscalamenti saranno usati soltanto dove pertinenti."
        ));
        if (valoreRisposta("dipendenzaCoordinate") !== "si") domande.push(domandaAdattiva(
          "aggregazioneScarti", "Quali differenze tra due righe ti interessano di più?",
          "Se non hai una preferenza, lascia che il sito scelga. Potrai cambiare la misura alla fine.",
          [["automatico", "Non ho preferenze: scegli il sito"], ["lineare", "Conta la somma delle differenze"], ["quadratica", "Dai più rilievo alle differenze grandi"], ["massimo", "Conta soprattutto la differenza più grande"], ["minkowski", "Voglio regolare io la sensibilità (avanzato)"]],
          "automatico"
        ));
        if (valoreRisposta("dipendenzaCoordinate") !== "si" && valoreRisposta("aggregazioneScarti") === "minkowski") domande.push(domandaInput(
          "ordineMinkowski", "Quanto devono pesare le differenze grandi? (avanzato)",
          "Questa è un'impostazione avanzata. Inserisci un numero almeno pari a 1; valori maggiori danno più peso alle differenze grandi.", "Per esempio 3", "number"
        ));
        if (quantitativeIndipendenti.length >= 2 && valoreRisposta("dipendenzaCoordinate") !== "si") {
          domande.push(domandaAdattiva(
            "importanzaCoordinate", "Alcune colonne sono più importanti di altre per il tuo confronto?",
            "Se non hai una preferenza, il sito assegna a tutte la stessa importanza.",
            [["uguale", "No, devono contare allo stesso modo"], ["diversa", "Sì, voglio assegnare importanze diverse"], ["ignoto", "Non lo so — assegna la stessa importanza"]]
          ));
          if (valoreRisposta("importanzaCoordinate") === "diversa") domande.push(domandaInput(
            "pesiQuantitativi", "Quanto deve contare ciascuna caratteristica?",
            `Inserisci un numero positivo per ogni colonna, nell'ordine: ${indipendentiStandard.map(profilo => escapeHtml(profilo.nome)).join(", ")}. Un valore doppio indica un'importanza doppia.`,
            "Per esempio 1; 2; 0,5"
          ));
        }
      }
      if (confronto === "relativo") domande.push(domandaAdattiva(
        "valoriVicinoZero", "Ci sono spesso valori uguali o molto vicini a zero?",
        "Quando si confrontano differenze in proporzione, valori molto piccoli possono avere un peso elevato.",
        [["no", "No, accade raramente"], ["si", "Sì, e questi valori sono significativi"], ["ignoto", "Non lo so — mostrami un avviso nel risultato"]]
      ));
    } else if (quantitativeIndipendenti.length >= 2 && indipendentiStandard.some(profilo =>
      interpretazione.colonne[profilo.nome]?.ruolo !== "quantita")) {
      domande.push(notaAutomatica(
        "Caratteristiche quantitative nel percorso misto",
        "Le colonne numeriche indipendenti sono analizzate insieme, ma la misura finale per le caratteristiche indipendenti di tipo diverso resta Gower: ogni quantità contribuisce con uno scarto normalizzato. Non viene applicata una distanza euclidea separata."
      ));
      domande.push(domandaAdattiva(
        "tipoGowerNumeriche", "Come vuoi normalizzare le differenze tra le quantità all'interno di Gower?",
        "La scelta riguarda solo i contributi quantitativi. Gower classica usa l'intervallo osservato; la variante robusta usa 7 volte l'IQR (se positivo) e limita ogni contributo a 1.",
        [["automatico", "Usa il criterio consigliato"], ["classica", "Usa l'intervallo osservato (Gower classica)"], ["robusta", "Limita l'influenza dei valori estremi sulla scala (Gower robusta)"]],
        "automatico"
      ));
    }
    if (!percorsoNumerico && indipendentiStandard.length) {
      domande.push(domandeConfigurazioneGower(indipendentiStandard));
    }
    interpretazione.gruppi.forEach(gruppo => {
      const membri = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa && interpretazione.assegnazioni[profilo.nome] === gruppo.id);
      const tipi = membri.map(profilo => risultato.colonne.find(colonna => colonna.nome === profilo.nome)?.tipo);
      const valido = membri.length >= 2 && membri.every((profilo, indice) =>
        ["numerica", "numerica_costante"].includes(tipi[indice]) && interpretazione.colonne[profilo.nome]?.ruolo === "quantita");
      if (!valido) return;
      if (gruppo.tipo === "ripetute") domande.push(domandaAdattiva(
        `somiglianza-${gruppo.id}`, `Nel gruppo “${escapeHtml(gruppo.nome)}”, quando due righe devono essere considerate simili?`,
        "Le colonne formano un unico profilo: scegli quale aspetto deve contare.",
        [["valori_vicini", "Quando hanno valori vicini"], ["proporzioni", "Quando mantengono proporzioni simili"], ["andamento", "Quando crescono e diminuiscono nello stesso modo"], ["ordine", "Quando ordinano le caratteristiche nello stesso modo"], ["ignoto", "Non lo so"]]
      ));
      if (gruppo.tipo === "tempo") domande.push(domandaAdattiva(
        `ritardo-${gruppo.id}`, `Nel gruppo “${escapeHtml(gruppo.nome)}”, un andamento simile può avvenire con un piccolo ritardo?`,
        "Per esempio, lo stesso picco può comparire in momenti leggermente diversi nelle due righe.",
        [["si", "Sì, il ritardo non deve renderle diverse"], ["no", "No, gli stessi eventi devono avvenire negli stessi momenti"], ["ignoto", "Non lo so"]]
      ));
      if (gruppo.tipo === "parti") domande.push(domandaAdattiva(
        `totale-${gruppo.id}`, `Le colonne del gruppo “${escapeHtml(gruppo.nome)}” sono parti di un unico totale?`,
        "Per esempio, percentuali, quote o quantità la cui somma ha un significato preciso.",
        [["si", "Sì, conta la composizione del totale"], ["no", "No, sono quantità indipendenti"], ["ignoto", "Non lo so"]]
      ));
    });
    $("adaptive-questions").innerHTML = domande.join("");
    aggiornaFaseNumerica();
  }

  function mostraRisultato(nomeFile) {
    $("csv-file-name").textContent = nomeFile;
    $("csv-dimensions").textContent = `Matrice ${risultato.riepilogo.istanze} × ${risultato.riepilogo.feature} (istanze × feature)`;
    $("csv-output").hidden = false;
    disegnaMetodi();
    vista = "originale";
    aggiornaVisibilitaTrasformazione(null);
    disegnaTabella();
    disegnaQuestionario();
  }

  async function elaboraTesto(testo, nomeFile) {
    nascondiErrore();
    try {
      interpretazione = { colonne: {}, gruppi: [], assegnazioni: {}, prossimoGruppo: 1 };
      riscalamentoConfermato = false;
      $("row-meaning").value = "";
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
      if (!riscalamentoConfermato || !tabellaInteramenteNumerica()) return;
      const colonne = colonneNumericheSelezionate().map(c => c.nome);
      const indici = colonne.map(nome => risultato.originale.intestazioni.indexOf(nome));
      const righe = risultato.trasformate.map(riga => indici.map(i => riga[i]));
      const csv = "\uFEFF" + await P.creaCsv(colonne, righe);
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
  $("confirm-numeric-scaling").addEventListener("click", confermaRiscalamentoNumerico);
  $("prepare-comparison-plan").addEventListener("click", preparaPiano);
  $("calculate-gower").addEventListener("click", calcolaMatrice);
  $("download-gower").addEventListener("click", scaricaMatrice);
  $("comparison-plan-paths").addEventListener("change", evento => {
    if (evento.target.matches(".path-weight")) {
      if (!interpretazione.pesiPercorsi) interpretazione.pesiPercorsi = {};
      interpretazione.pesiPercorsi[evento.target.dataset.pathId] = evento.target.value;
      preparaPiano();
      return;
    }
    if (evento.target.id !== "numeric-dependency-choice") return;
    interpretazione.gestioneDipendenzaLineare = evento.target.value;
    preparaPiano();
  });
  $("comparison-plan-paths").addEventListener("change", evento => {
    if (evento.target.id !== "numeric-measure-choice") return;
    interpretazione.misuraNumericaManuale = evento.target.value;
    const nomi = pianoCorrente?.percorsi.find(p => p.tipo === "numerico")?.colonne || [];
    if (["weighted_minkowski", "weighted_chebyshev"].includes(evento.target.value) && !interpretazione.pesiMisuraManuale) {
      interpretazione.pesiMisuraManuale = nomi.map(() => "1").join("; ");
    }
    preparaPiano();
  });
  $("comparison-plan-paths").addEventListener("click", evento => {
    if (evento.target.id !== "apply-numeric-measure") return;
    interpretazione.misuraNumericaManuale = $("numeric-measure-choice").value;
    const q = $("numeric-measure-q");
    const pesi = $("numeric-measure-weights");
    if (q) interpretazione.ordineMisuraManuale = q.value;
    if (pesi) interpretazione.pesiMisuraManuale = pesi.value;
    preparaPiano();
  });
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
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    disegnaQuestionario();
  });
  $("adaptive-questions").addEventListener("change", evento => {
    if (evento.target.matches(".numeric-missing-setting")) {
      if (!interpretazione.mancantiNumericiPerColonna) {
        interpretazione.mancantiNumericiPerColonna = {};
      }
      interpretazione.mancantiNumericiPerColonna[
        evento.target.dataset.numericMissingColumn
      ] = evento.target.value;
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".gower-setting")) {
      const chiave = evento.target.dataset.gowerKey;
      const colonna = evento.target.dataset.gowerColumn;
      if (!["pesiGower", "mancantiPerColonna", "zeriCondivisiPerColonna",
            "presenzaPositivaPerColonna", "ordinePerColonna", "ordiniLivelliGower"].includes(chiave)) return;
      if (!interpretazione[chiave]) interpretazione[chiave] = {};
      interpretazione[chiave][colonna] = evento.target.value;
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".semantic-answer, .semantic-input")) {
      interpretazione[evento.target.dataset.answer] = evento.target.value;
      if (evento.target.matches(".semantic-answer")) disegnaQuestionario();
      else nascondiPiano();
    }
  });
  $("row-meaning").addEventListener("change", evento => {
    interpretazione.riga = evento.target.value;
    nascondiPiano();
  });
  $("add-column-group").addEventListener("click", () => {
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    creaGruppo();
    disegnaQuestionario();
  });
  $("group-assignment-body").addEventListener("change", evento => {
    if (!evento.target.matches(".group-assignment")) return;
    const nome = evento.target.dataset.groupColumn;
    let gruppoId = evento.target.value;
    if (gruppoId === "__nuovo__") gruppoId = creaGruppo().id;
    if (gruppoId) interpretazione.assegnazioni[nome] = gruppoId;
    else delete interpretazione.assegnazioni[nome];
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    disegnaQuestionario();
  });
  $("group-config-list").addEventListener("change", evento => {
    const contenitore = evento.target.closest(".group-config");
    if (!contenitore) return;
    const gruppo = interpretazione.gruppi.find(elemento => elemento.id === contenitore.dataset.groupId);
    if (!gruppo) return;
    if (evento.target.matches(".group-name")) gruppo.nome = evento.target.value.trim() || gruppo.nome;
    if (evento.target.matches(".group-type")) gruppo.tipo = evento.target.value;
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    disegnaQuestionario();
  });
  $("group-config-list").addEventListener("input", evento => {
    if (!evento.target.matches(".group-name")) return;
    const contenitore = evento.target.closest(".group-config");
    const gruppo = interpretazione.gruppi.find(elemento => elemento.id === contenitore.dataset.groupId);
    if (gruppo && evento.target.value.trim()) gruppo.nome = evento.target.value.trim();
  });
  $("group-config-list").addEventListener("focusout", evento => {
    if (evento.target.matches(".group-name")) disegnaQuestionario();
  });
  $("group-config-list").addEventListener("click", evento => {
    const pulsante = evento.target.closest(".remove-group");
    if (!pulsante) return;
    const gruppoId = pulsante.closest(".group-config").dataset.groupId;
    interpretazione.gruppi = interpretazione.gruppi.filter(gruppo => gruppo.id !== gruppoId);
    Object.keys(interpretazione.assegnazioni).forEach(nome => {
      if (interpretazione.assegnazioni[nome] === gruppoId) delete interpretazione.assegnazioni[nome];
    });
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
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
