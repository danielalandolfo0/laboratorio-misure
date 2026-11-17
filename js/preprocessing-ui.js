/* Interfaccia per il caricamento e il riscalamento automatico dei CSV. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const P = window.Preprocessing;
  let risultato = null;
  let tabellaOriginale = null;
  let testoOriginale = "";
  let scelte = [];
  // Configurazione di importazione separata dalle scelte semantiche.
  // Viene riapplicata ad ogni richiesta Python sul CSV originale.
  let importazioneCSV = null;
  let anteprimaImportazione = null;
  let nomeFileImportazione = "";
  let versioneAnteprimaImportazione = 0;
  let interpretazione = { colonne: {}, gruppi: [], assegnazioni: {}, prossimoGruppo: 1 };
  let vista = "lavoro";
  let pianoCorrente = null;
  let matriceCorrente = null;
  let rapportoCoppieNonConfrontabili = null;
  let versioneDiagnosi = 0;
  let proposteGruppiCorrenti = [];
  let riscalamentoConfermato = false;
  // Tipi -> preprocessing -> selezione/gruppi -> misure: l'ordine
  // precede il piano, che resta la fonte di verifica matematica.
  const FASI_QUESTIONARIO = ["semantica", "preprocessing", "selezione", "misure"];
  let faseQuestionario = "semantica";
  let indiceDomandaFocalizzata = 0;
  let mostraTutteDomande = false;

  function mostraFaseQuestionario() {
    if (!risultato) return;
    const nodi = ["phase-semantics", "phase-preprocessing", "phase-selection", "phase-measures"];
    const indice = FASI_QUESTIONARIO.indexOf(faseQuestionario);
    nodi.forEach((nome, i) => { $(nome).hidden = i !== indice; });
    const titoli = ["Significato delle colonne", "Diagnosi e preprocessing",
      "Selezione delle colonne e dei gruppi", "Misure e parametri"];
    $("questionnaire-progress").textContent =
      "Fase " + (indice + 1) + " di 4 — " + titoli[indice];
  }

  function vaiAllaFase(fase) {
    if (!FASI_QUESTIONARIO.includes(fase)) throw new Error("Fase non riconosciuta.");
    faseQuestionario = fase;
    aggiornaFaseNumerica();
    aggiornaDomandeFocalizzate();
    const titolo = {
      semantica: "phase-semantics-title",
      preprocessing: "phase-preprocessing-title",
      selezione: "phase-selection-title",
      misure: "phase-measures-title"
    }[fase];
    $(titolo).focus?.({preventScroll: true});
  }
  // Revisione incrementata a ogni modifica che invalida il piano.
  // Le risposte asincrone obsolete non devono mostrare un piano o una
  // matrice riferiti a scelte non più correnti.
  let versioneDati = 0;
  let versionePreparazioneColonne = 0;
  let versionePiano = 0;
  let versioneMatrice = 0;

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
    return ({ zscore: "Z-score", robusto: "Scala robusta", minmax: "Min–max", maxabs: "Max-abs", log: "Log(x)", log1p: "Log(1+x)", costante: "Valore 0", nessuno: "Nessuno" })[metodo];
  }

  function mostraErrore(messaggio) {
    $("csv-error").textContent = messaggio;
    $("csv-error").style.display = "block";
  }

  function nascondiErrore() {
    $("csv-error").textContent = "";
    $("csv-error").style.display = "none";
  }

  function elencoProblemiHtml(problemi) {
    if (!problemi?.length) return "";
    return '<ul class="problem-report-list">' +
      problemi.map(problema =>
        '<li><strong>' + escapeHtml(problema.nome || "Configurazione") +
        '</strong>' +
        (problema.colonne?.length
          ? '<span class="problem-report-columns">Colonne: ' +
            escapeHtml(problema.colonne.join(", ")) + '</span>'
          : '') +
        '<p>' + escapeHtml(problema.messaggio || "") + '</p>' +
        (problema.decisioniPossibili?.length
          ? '<p><strong>Possibili decisioni:</strong> ' +
            problema.decisioniPossibili.map(escapeHtml).join(" ") + '</p>'
          : '') + '</li>'
      ).join("") + '</ul>';
  }

  function azzeraProblemiCalcolo() {
    rapportoCoppieNonConfrontabili = null;
    $("comparison-calculation-problems-body").innerHTML = "";
    $("comparison-calculation-problems").hidden = true;
    $("download-uncovered-pairs").hidden = true;
  }

  function disegnaProblemiCalcolo(rapporto) {
    azzeraProblemiCalcolo();
    if (!rapporto || !Array.isArray(rapporto.bloccanti)) return;
    const coppie = rapporto.coppieNonConfrontabili || [];
    const etichette = rapporto.etichette || [];
    const copertura = rapporto.analisiCopertura;
    const etichetteMotivi = {
      riga_assente: "almeno una riga assente dal blocco",
      locale_indefinita: "distanza locale non definita"
    };
    const sintesiCopertura = copertura?.perBlocco?.length
      ? '<h6>Perché nessun blocco copre queste coppie?</h6>' +
        '<p>Ogni coppia elencata è priva di contributi in tutti i blocchi. ' +
        'Per ciascuno è indicata la causa, senza attribuire zeri.</p>' +
        '<ul>' + copertura.perBlocco.map(blocco =>
          '<li><strong>' + escapeHtml(blocco.titolo) + '</strong> (' +
          escapeHtml((blocco.colonne || []).join(", ")) + '): ' +
          escapeHtml(String(blocco.coppieConRigaAssente)) +
          ' coppie con almeno una riga assente dal risultato locale; ' +
          escapeHtml(String(blocco.coppieLocalmenteIndefinite)) +
          ' con distanza locale non definita.</li>'
        ).join("") + '</ul>'
      : "";
    const esempioCoppie = coppie.slice(0, 12).map(([i, j], indice) => {
      const dettagli = copertura?.esempi?.[indice]?.blocchi || [];
      const cause = dettagli.length
        ? '<small>Blocchi: ' + dettagli.map(blocco =>
            escapeHtml(blocco.titolo) + ' — ' +
            escapeHtml(etichetteMotivi[blocco.motivo] || blocco.motivo)
          ).join('; ') + '</small>'
        : '';
      return '<li>Riga ' + escapeHtml(String(i)) + ' (' +
        escapeHtml(etichette[i - 1] ?? String(i)) + ') e riga ' +
        escapeHtml(String(j)) + ' (' +
        escapeHtml(etichette[j - 1] ?? String(j)) + ')' +
        cause + '</li>';
    }).join("");
    $("comparison-calculation-problems-body").innerHTML =
      '<h5>Rapporto dei problemi riscontrati durante il calcolo</h5>' +
      '<p><strong>' + escapeHtml(String(rapporto.numeroBloccanti || 0)) +
      ' problemi bloccanti.</strong> La matrice non è stata generata: ' +
      'il sito non sostituisce distanze non definite con numeri arbitrari.</p>' +
      elencoProblemiHtml(rapporto.bloccanti) +
      sintesiCopertura +
      (coppie.length
        ? '<p><strong>Tutte le coppie non confrontabili: ' +
          escapeHtml(String(coppie.length)) +
          '.</strong> Eccone fino a 12; il CSV contiene l’elenco completo ' +
          'con gli indici originali e le etichette.</p><ul>' +
          esempioCoppie + '</ul>'
        : '') +
      '<p>Per proseguire rivedi le scelte pertinenti e prepara nuovamente ' +
      'il piano. Nessuna correzione viene applicata automaticamente.</p>';
    if (coppie.length) {
      rapportoCoppieNonConfrontabili = {coppie, etichette};
      $("download-uncovered-pairs").hidden = false;
    }
    $("comparison-calculation-problems").hidden = false;
  }

  function scaricaCoppieNonConfrontabili() {
    if (!rapportoCoppieNonConfrontabili?.coppie?.length) return;
    const {coppie, etichette} = rapportoCoppieNonConfrontabili;
    const cellaCsv = valore => {
      // Le etichette importate non possono diventare formule nel foglio CSV.
      let testo = String(valore);
      if (/^[\s]*[=+@-]/.test(testo)) testo = "'" + testo;
      return '"' + testo.replace(/"/g, '""') + '"';
    };
    const righe = ['riga_1;riga_2;etichetta_1;etichetta_2'];
    for (const [i, j] of coppie) {
      righe.push([i, j, etichette[i - 1] ?? "", etichette[j - 1] ?? ""]
        .map(cellaCsv).join(";"));
    }
    const url = URL.createObjectURL(new Blob(
      ["\uFEFF" + righe.join("\r\n")],
      {type: "text/csv;charset=utf-8"}
    ));
    const link = document.createElement("a");
    link.href = url;
    link.download = "coppie_non_confrontabili.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function disegnaMetodi() {
    const selezionate = new Set(colonneNumericheDaRiscalare().map(c => c.nome));
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
          : colonna.metodo === "log"
            ? "log(x) · rapporti |log(x/y)| · non è una standardizzazione"
          : colonna.metodo === "log1p"
            ? "log(1+x) · non è una standardizzazione" 
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
          <option value="robusto"${metodo === "robusto" ? " selected" : ""}>Usa mediana e IQR (robusto: non elimina gli outlier)</option>
          <option value="minmax"${metodo === "minmax" ? " selected" : ""}>Porta i valori tra 0 e 1 (min–max)</option>
          <option value="maxabs"${metodo === "maxabs" ? " selected" : ""}>Dividi per il valore massimo assoluto (max-abs)</option>
          <option value="log"${metodo === "log" ? " selected" : ""}${s.minimo <= 0 ? " disabled" : ""}>Confronta rapporti: log(x), soltanto per valori strettamente positivi (x &gt; 0)</option>
          <option value="log1p"${metodo === "log1p" ? " selected" : ""}${s.minimo < 0 ? " disabled" : ""}>Comprimi le differenze grandi: log(1+x), per valori non negativi (x ≥ 0)</option>
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
    const versione = ++versionePreparazioneColonne;
    const versioneFile = versioneDati;
    scelte[indice][chiave] = elemento.value;
    if (chiave === "tipo" && (elemento.value === "binaria" || elemento.value === "non_numerica")) scelte[indice].metodo = "auto";
    // Il piano corrente diventa invalido appena l'utente cambia la scelta.
    nascondiPiano();
    annullaScelteNormalizzazione();
    annullaConfermeCompatibilita();
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    try {
      let nuoveScelte = scelte.map(scelta => ({ ...scelta }));
      let nuovaTabella = await P.preparaTabella(testoOriginale, nuoveScelte, importazioneCSV || {});
      if (versione !== versionePreparazioneColonne || versioneFile !== versioneDati) return;
      const tipoEffettivo = nuovaTabella.colonne[indice].tipo;
      if ((tipoEffettivo === "binaria" || tipoEffettivo === "non_numerica") && scelte[indice].metodo !== "auto") {
        scelte[indice].metodo = "auto";
        nuoveScelte = scelte.map(scelta => ({ ...scelta }));
        nuovaTabella = await P.preparaTabella(testoOriginale, nuoveScelte, importazioneCSV || {});
        if (versione !== versionePreparazioneColonne || versioneFile !== versioneDati) return;
      }
      risultato = nuovaTabella;
      nascondiErrore();
      disegnaMetodi();
      disegnaTabella();
      disegnaQuestionario();
    } catch (errore) {
      if (versione !== versionePreparazioneColonne || versioneFile !== versioneDati) return;
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
      ? (pianoCorrente?.anteprimaNumerica?.colonne ||
          colonneNumericheDaRiscalare().map(c => c.nome))
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
      : "Anteprima delle trasformazioni numeriche confermate. I blocchi di forma e DTW usano i valori originali; i blocchi di coordinate usano le trasformazioni quando previste nel piano.";
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
      insieme: "Un insieme di etichette nella stessa cella",
      ciclica: "Una quantità ciclica con periodo noto",
      risultato: "Un risultato da spiegare o prevedere",
      altro: "Qualcos’altro",
      ignoto: "Non lo so"
    })[ruolo] || ruolo;
  }

  function opzioniRuolo(selezionato) {
    const ruoli = ["quantita", "livello", "presenza", "binaria", "categoria", "insieme", "ciclica", "identificativo", "data", "testo", "risultato", "altro", "ignoto"];
    return ruoli.map(ruolo => `<option value="${ruolo}"${ruolo === selezionato ? " selected" : ""}>${etichettaRuolo(ruolo)}</option>`).join("");
  }

  function valoreRisposta(id) {
    return interpretazione[id] || "";
  }

  function domandaAdattiva(id, titolo, testo, opzioni, predefinito = "") {
    const selezionato = valoreRisposta(id) || predefinito;
    return `<div class="question-item">
      <label for="${id}">${titolo}</label>
      <select class="semantic-answer" id="${id}" data-answer="${id}">
        ${predefinito ? "" : '<option value="">Scegli una risposta</option>'}
        ${opzioni.map(([valore, etichetta]) => `<option value="${valore}"${selezionato === valore ? " selected" : ""}>${etichetta}</option>`).join("")}
      </select>
      <details class="question-help"><summary>Perché me lo chiedi?</summary><p>${testo}</p></details>
    </div>`;
  }

  function domandaInput(id, titolo, testo, placeholder, tipo = "text") {
    return `<div class="question-item">
      <label for="${id}">${titolo}</label>
      <input class="semantic-input" id="${id}" data-answer="${id}" type="${tipo}" value="${escapeHtml(valoreRisposta(id))}" placeholder="${escapeHtml(placeholder)}">
      <details class="question-help"><summary>Come rispondere</summary><p>${testo}</p></details>
    </div>`;
  }

  function notaAutomatica(titolo, testo) {
    return `<div class="question-item automatic-note">
      <strong>${escapeHtml(titolo)}</strong>
      <p>${escapeHtml(testo)}</p>
    </div>`;
  }


  // Il suggerimento non approva alcuna interpretazione e non sostituisce
  // la validazione del piano; porta soltanto alla prossima decisione.
  let prossimoCampoGuida = null;

  function campoCompilato(campo) {
    if (!campo || campo.disabled) return true;
    if (campo.type === "checkbox" || campo.type === "radio") return campo.checked;
    return String(campo.value || "").trim() !== "";
  }

  function domandeInterattive() {
    return Array.from($("adaptive-questions").querySelectorAll(".question-item"))
      .filter(card => card.querySelector("select:not([disabled]), input:not([disabled]), textarea:not([disabled])"));
  }

  function aggiornaDomandeFocalizzate(preferisciIncompleta = false) {
    const contenitore = $("adaptive-questions");
    const cards = domandeInterattive();
    const note = Array.from(contenitore.querySelectorAll(".question-item"))
      .filter(card => !cards.includes(card));
    note.forEach(card => { card.hidden = !mostraTutteDomande; });
    if (!cards.length) {
      $("question-focus").hidden = true;
      return;
    }
    const incompleta = card => Array.from(card.querySelectorAll("select, input, textarea"))
      .some(campo => !campoCompilato(campo));
    if (preferisciIncompleta) {
      const prima = cards.findIndex(incompleta);
      if (prima >= 0) indiceDomandaFocalizzata = prima;
    }
    indiceDomandaFocalizzata = Math.max(0, Math.min(indiceDomandaFocalizzata, cards.length - 1));
    cards.forEach((card, indice) => {
      const richiesta = incompleta(card);
      card.classList.toggle("required-decision", richiesta);
      card.hidden = !mostraTutteDomande && indice !== indiceDomandaFocalizzata;
      card.setAttribute("aria-current", indice === indiceDomandaFocalizzata ? "step" : "false");
      let badge = card.querySelector(".decision-badge");
      if (richiesta && !badge) {
        badge = document.createElement("span");
        badge.className = "decision-badge";
        badge.textContent = "Decisione necessaria";
        card.prepend(badge);
      } else if (!richiesta && badge) badge.remove();
    });
    const mancanti = cards.filter(incompleta).length;
    $("question-focus-status").textContent = mostraTutteDomande
      ? `${cards.length} decisioni mostrate · ${mancanti} da completare`
      : `Decisione ${indiceDomandaFocalizzata + 1} di ${cards.length} · ${mancanti} da completare`;
    $("question-focus-previous").disabled = indiceDomandaFocalizzata === 0 || mostraTutteDomande;
    $("question-focus-next").disabled = indiceDomandaFocalizzata === cards.length - 1 || mostraTutteDomande;
    $("question-focus-all").textContent = mostraTutteDomande
      ? "Mostra una domanda per volta" : "Mostra tutte le domande e i dettagli";
    $("question-focus-all").setAttribute("aria-pressed", String(mostraTutteDomande));
    $("question-focus").hidden = faseQuestionario !== "misure";
  }

  function focalizzaCampo(campo) {
    const card = campo?.closest?.(".question-item");
    if (card) {
      const cards = domandeInterattive();
      const indice = cards.indexOf(card);
      if (indice >= 0) {
        mostraTutteDomande = false;
        indiceDomandaFocalizzata = indice;
        aggiornaDomandeFocalizzate();
      }
    }
  }

  function aggiornaGuida() {
    if (!risultato) return;
    if (faseQuestionario !== "misure") {
      $("comparison-guide").hidden = true;
      prossimoCampoGuida = null;
      return;
    }
    const domande = $("adaptive-questions");
    const campoVuoto = selettore => Array.from(domande.querySelectorAll(selettore))
      .find(c => !c.disabled && !String(c.value || "").trim());
    let titolo, testo, campo;
    if (!$("row-meaning").value) {
      titolo = "1. Indica che cosa rappresenta una riga.";
      testo = "Ogni riga può descrivere una persona, un oggetto o un evento. La risposta definisce il significato delle osservazioni.";
      campo = $("row-meaning");
    } else {
      const indefinito = interpretazione.gruppi.find(gruppo =>
        gruppo.tipo === "altro" &&
        Object.values(interpretazione.assegnazioni).includes(gruppo.id));
      if (indefinito) {
        titolo = "2. Specifica il significato delle colonne riunite nel gruppo.";
        testo = "Scegli che cosa rappresentano insieme, oppure lascia le colonne indipendenti.";
        campo = Array.from($("group-config-list").querySelectorAll(".group-config"))
          .find(x => x.dataset.groupId === indefinito.id)?.querySelector(".group-type");
      }
      const risposta = !titolo && campoVuoto(
        "select.semantic-answer, select.group-measure-setting, " +
        "select.group-preprocessing-confirmation, select.specialized-missing-setting");
      if (risposta) {
        titolo = "3. Completa una domanda sul significato o sul confronto.";
        testo = "Scegli ciò che descrive davvero i dati. Quando è previsto, puoi rispondere «Non lo so»: il sito non inventa una scelta al tuo posto.";
        campo = risposta;
      }
      const dettaglio = !titolo && campoVuoto(
        "input.gower-nominal-pair, " +
        "input.gower-setting[data-gower-key='ordiniLivelliGower'], " +
        "input.gower-setting[data-gower-key='passiOrdinaliGower']");
      if (dettaglio) {
        titolo = "3. Completa la personalizzazione delle categorie o dei livelli.";
        testo = "Per categorie diverse indica valori fra 0 e 1; per livelli ordinali usa intervalli positivi. Puoi anche tornare alle impostazioni standard.";
        campo = dettaglio;
      }
      if (!titolo && richiedeRiscalamentoConfermato() && !riscalamentoConfermato) {
        titolo = "4. Controlla e conferma le trasformazioni numeriche.";
        testo = "Verifica i metodi proposti per le colonne quantitative. Il file originale non verrà modificato.";
        campo = $("confirm-numeric-scaling");
      }
      if (!titolo && !pianoCorrente) {
        titolo = "5. Prepara il piano per verificare le scelte.";
        testo = "Prima di calcolare, il piano mostrerà eventuali incompatibilità e le conferme ancora necessarie.";
        campo = $("prepare-comparison-plan");
      }
      if (!titolo && !pianoCorrente.completo) {
        titolo = "5. Consulta gli avvisi e completa la configurazione.";
        testo = "Il calcolo resta bloccato finché le scelte non sono coerenti. Leggi gli avvisi del piano.";
        campo = $("comparison-plan-warnings");
      }
      if (!titolo && !matriceCorrente) {
        titolo = "6. Il piano è completo: puoi calcolare la matrice unica.";
        testo = "Tutti i percorsi previsti sono calcolabili; verranno aggregati secondo le importanze confermate.";
        campo = $("calculate-gower");
      }
      if (!titolo) {
        titolo = "6. La matrice è pronta.";
        testo = "Puoi consultarla o scaricare l'intera matrice CSV. Se modifichi una scelta, sarà necessario ricalcolarla.";
        campo = $("download-gower");
      }
    }
    $("comparison-guide-phase").textContent = titolo;
    $("comparison-guide-explanation").textContent = testo;
    prossimoCampoGuida = campo || null;
    $("comparison-guide-next").hidden = !campo || campo.hidden;
    $("comparison-guide").hidden = false;
  }

  function annullaScelteNormalizzazione() {
    // Gli ID dei percorsi dipendono dalla struttura corrente: non riutilizzare
    // una vecchia scala robusta dopo cambi di colonne, gruppi o misure.
    delete interpretazione.normalizzazioniPercorsi;
    delete interpretazione.righeAnomaleNormalizzazione;
  }

  function invalidaPesiPerStruttura() {
    // Gli ID "percorso-1", ecc. si riferiscono ai blocchi attuali.
    // Dopo una modifica strutturale non possiamo riutilizzare i pesi
    // personalizzati per blocchi che potrebbero essere differenti.
    delete interpretazione.pesiPercorsi;
    if (interpretazione.modalitaPesiPercorsi === "personalizzati") {
      interpretazione.modalitaPesiPercorsi = "uguali";
    }
    // In modalità "dimensione" il backend ricalcola |B_k| per la nuova struttura.
  }

  function annullaConfermeCompatibilita() {
    delete interpretazione.confermeValoriOriginaliGruppi;
    delete interpretazione.confermeRiscalamentiMistiGruppi;
    delete interpretazione.confermaValoriOriginaliNumerici;
  }

  function nascondiPiano() {
    ++versionePiano;
    ++versioneMatrice;
    $("comparison-plan").hidden = true;
    $("gower-actions").hidden = true;
    $("gower-result").hidden = true;
    pianoCorrente = null;
    matriceCorrente = null;
    // Le promesse annullate possono terminare dopo questa invalidazione.
    // Ripristina qui i comandi, non soltanto nel finally della promessa
    // superata, che non deve più modificare l'interfaccia.
    $("prepare-comparison-plan").disabled = false;
    $("prepare-comparison-plan").textContent = "Conferma scelte e prepara il piano";
    $("calculate-gower").disabled = false;
    $("calculate-gower").textContent = "Calcola la matrice finale";
    $("download-gower").disabled = true;
    $("download-report").disabled = true;
    azzeraProblemiCalcolo();
    aggiornaVisibilitaTrasformazione();
    aggiornaGuida();
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
  function colonneNumericheDaRiscalare() {
    if (!risultato) return [];
    return risultato.colonne.filter(colonna => {
      const risposta = interpretazione.colonne[colonna.nome];
      return risposta?.ruolo === "quantita" &&
        ["numerica", "numerica_costante"].includes(colonna.tipo);
    });
  }
  function tabellaInteramenteNumerica() {
    if (!risultato) return false;
    const incluse = risultato.colonne.filter(c => interpretazione.colonne[c.nome]?.usa);
    return incluse.length > 0 && incluse.length === colonneNumericheDaRiscalare().length;
  }

  async function mostraDiagnosiPreliminare() {
    const contenitore = $("numeric-preliminary-diagnosis");
    const corpo = $("numeric-preliminary-content");
    const versione = ++versioneDiagnosi;
    proposteGruppiCorrenti = [];
    const nomi = colonneNumericheDaRiscalare().map(c => c.nome);
    if (nomi.length < 2) {
      contenitore.hidden = true;
      corpo.innerHTML = "";
      $("numeric-group-proposals").innerHTML = "";
      return;
    }
    contenitore.hidden = false;
    $("numeric-preliminary-scope").textContent =
      `Analisi preliminare delle ${nomi.length} colonne quantitative, prima della selezione: ${nomi.join(", ")}. ` +
      (tabellaInteramenteNumerica()
        ? "Questa diagnosi orienta la scelta della misura e del riscalamento; non modifica i dati."
        : "Le altre colonne e i gruppi non entrano in questa diagnosi. Nei percorsi misti Gower usa i valori originali e normalizza internamente i contributi quantitativi; i gruppi di coordinate possono invece usare il riscalamento confermato.");
    corpo.textContent = "Analisi preliminare delle colonne quantitative indipendenti…";
    try {
      const risposta = await P.analizzaDiagnosi(testoOriginale, scelte, nomi, importazioneCSV || {});
      if (versione !== versioneDiagnosi) return;
      const d = risposta.diagnosi;
      proposteGruppiCorrenti = (risposta.gruppiSuggeriti || []).filter(proposta =>
        Array.isArray(proposta.colonne) && proposta.colonne.length >= 2 &&
        proposta.colonne.every(nome =>
          !interpretazione.assegnazioni[nome] && interpretazione.colonne[nome]?.usa
        )
      );
      const estreme = risposta.colonne.filter(c => c.statistiche.estremi > 0);
      const asimmetriche = d.colonneAsimmetriche || [];
      const multivariata = d.diagnosiMultivariata || {};
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
      const asimmetria = asimmetriche.length
        ? "Possibile asimmetria quartilica in: " +
          asimmetriche.map(c => c.nome + " (Bowley = " +
            formatoNumero(c.asimmetriaBowley) + ")").join("; ") +
          ". Non indica necessariamente dati errati: valuta se conta la differenza " +
          "assoluta o quella relativa e se una trasformazione sarebbe coerente con il dominio."
        : "Non emergono asimmetrie quartiliche marcate secondo il criterio " +
          "esplorativo, oppure le colonne sono troppo piccole o hanno IQR nullo.";
      const multivariati = multivariata.stato !== "valutata"
        ? "Controllo multivariato non eseguibile: " + (multivariata.motivo || "dati insufficienti") +
          " Nessuna conclusione sull'assenza di anomalie."
        : multivariata.numeroCandidati
          ? "Possibili osservazioni insolite nella combinazione delle colonne: " +
            multivariata.candidati.map(c => "riga dati " + c.riga +
              " (punteggio " + formatoNumero(c.punteggio) + ")").join("; ") +
            (multivariata.numeroCandidati > multivariata.candidati.length
              ? "; altri " + (multivariata.numeroCandidati - multivariata.candidati.length) +
                " candidati non elencati" : "") +
            ". Controlla il significato delle righe: non sono state escluse."
          : "Non risultano candidati oltre la soglia multivariata esplorativa. " +
            "Non è una garanzia di assenza di anomalie.";
      const sceltePreprocessing = risposta.colonne.map(colonna => {
        const st = colonna.statistiche;
        const indiceBowley = st.asimmetriaBowley;
        const asimmetrica = st.numeroOsservati >= 8 && indiceBowley !== null &&
          Math.abs(indiceBowley) >= 0.3;
        const haEstremi = st.estremi > 0;
        if (!asimmetrica && !haEstremi) return "";
        return colonna.nome + ": " +
          "puoi mantenere i valori originali oppure mantenere gli scarti ma " +
          "riscalare con mediana e IQR" +
          (st.iqr > 0 ? "" : " (non disponibile: IQR nullo)") +
          (st.minimo > 0
            ? "; puoi valutare log(x) se contano i rapporti tra valori positivi, oppure log(1+x) se è coerente con la scala e lo zero"
            : st.minimo === 0
              ? "; log(x) non è definito in zero, ma puoi valutare log(1+x) se aggiungere 1 nel logaritmo è semanticamente motivato"
              : "; né log(x) né log(1+x) sono disponibili senza modificare i dati perché ci sono valori negativi") +
          ". Nessuna alternativa viene applicata sulla sola base di questi indicatori.";
      }).filter(Boolean);
      const spiegazioni = [
        riga("Ci sono valori molto diversi dagli altri?", outlier),
        riga("Le distribuzioni sono asimmetriche?", asimmetria),
        ...(sceltePreprocessing.length
          ? [riga("Quale trattamento può essere appropriato?",
              sceltePreprocessing.join(" ") +
              " La scala robusta (x−mediana)/IQR non cancella i valori estremi: " +
              "in distanze sensibili agli scarti grandi possono restare molto influenti. " +
              "Puoi scegliere il metodo di ogni colonna nella tabella dei riscalamenti e confermarlo.")]
          : []),
        riga("Ci sono osservazioni insolite considerando più colonne insieme?", multivariati),
        riga("Le colonne hanno dispersioni simili?", scale),
        riga("Alcune colonne cambiano insieme?", andamento)
      ];
      if (multivariata.numeroCandidati > 0 && !estreme.length) {
        const scelta = interpretazione.significatoEstremi || "";
        spiegazioni.push(
          '<div class="question-item"><label><strong>Le righe segnalate nel confronto ' +
          'multivariato rappresentano osservazioni reali?</strong>' +
          '<select class="multivariate-extremes-choice">' +
          '<option value=""' + (!scelta || scelta === "ignoto" ? " selected" : "") +
          '>Devo ancora verificarlo</option>' +
          '<option value="reali"' + (scelta === "reali" ? " selected" : "") +
          '>Sì, sono osservazioni reali: mantienile</option>' +
          '<option value="controllare"' + (scelta === "controllare" ? " selected" : "") +
          '>Le devo controllare prima del calcolo</option>' +
          '<option value="errori"' + (scelta === "errori" ? " selected" : "") +
          '>Potrebbero essere errori: fermati</option>' +
          '</select></label></div>'
        );
      }
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
        '<p>Asimmetria quartilica di Bowley = (Q3 + Q1 − 2·mediana)/IQR, ' +
        'non definita per IQR = 0. La soglia esplorativa |Bowley| ≥ 0,3 ' +
        'si applica con almeno 8 osservazioni.</p>' +
        '<p>Outlier multivariati: su almeno max(12, 5p) righe complete, ' +
        'se la covarianza delle p colonne non è singolare o mal condizionata, ' +
        'si calcola la distanza di Mahalanobis quadrata dalla media campionaria. ' +
        'Possibili anomalie oltre Q3 + 1,5·IQR dei punteggi. ' +
        'La covarianza stimata sui medesimi dati può mascherare anomalie. ' +
        'Non è un test statistico con probabilità di falso positivo controllata.</p>' +
        '<p>' + escapeHtml(d.motivoCovarianza || "") + '</p></details>';

      const proposteHtml = proposteGruppiCorrenti.length
        ? '<section class="group-proposals"><h5>Possibili gruppi da verificare</h5>' +
          '<p>Sono soltanto indizi esplorativi. Il sito non assegna automaticamente ' +
          'a una correlazione il significato di una serie temporale o di un profilo. ' +
          'Puoi ignorare ogni proposta, oppure confermarla e modificarla in seguito.</p>' +
          proposteGruppiCorrenti.map((proposta, indice) =>
            '<div class="question-item"><strong>' + escapeHtml(proposta.nome) + '</strong>' +
            '<p>Colonne: ' + proposta.colonne.map(escapeHtml).join(', ') + '</p>' +
            '<p>' + escapeHtml(proposta.motivazione) + '</p>' +
            '<label>Che cosa rappresentano insieme queste colonne?' +
            '<select class="group-proposal-type" data-proposal-index="' + indice + '">' +
              '<option value="">Scegli il significato prima di creare il gruppo</option>' +
              '<option value="tempo">Misurazioni successive nel tempo (nell’ordine del CSV)</option>' +
              '<option value="ripetute">Coordinate di un profilo da confrontare per forma o direzione</option>' +
              '<option value="coordinate">Coordinate quantitative da confrontare insieme</option>' +
              '<option value="parti">Parti dello stesso totale</option>' +
              '<option value="distribuzione">Bin di una distribuzione o di un istogramma</option>' +
            '</select></label>' +
            '<button type="button" class="secondary-action apply-group-proposal" ' +
            'data-proposal-index="' + indice + '">Crea questo gruppo</button></div>'
          ).join('') + '</section>'
        : '<div class="question-item"><strong>Nessun gruppo proposto automaticamente</strong>' +
          '<p>Puoi comunque creare gruppi manualmente: nessuna regola statistica ' +
          'puo sostituire il significato delle variabili.</p></div>';
      corpo.innerHTML = spiegazioni.join("") + dettaglio;
      $("numeric-group-proposals").innerHTML = proposteHtml;
    } catch (errore) {
      if (versione !== versioneDiagnosi) return;
      corpo.textContent = "Non è stato possibile completare la diagnosi: " + errore.message;
    }
  }

  function richiedeRiscalamentoConfermato() {
    // Il requisito riguarda le quantità selezionate, non il fatto che
    // tutte le altre colonne del CSV siano numeriche. In un dataset misto
    // possono esserci gruppi di coordinate che usano il riscalamento.
    const quantitativi = colonneNumericheDaRiscalare();
    // Il riscalamento viene confermato prima della scelta delle misure.
    return quantitativi.length >= 1;
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
    const ciSonoAnomalie = colonneNumericheDaRiscalare().some(
      colonna => colonna.statistiche?.estremi > 0
    );
    const outlierConfermati = !ciSonoAnomalie ||
      interpretazione.significatoEstremi === "reali";
    const pronto = (!numerico || riscalamentoConfermato) && outlierConfermati;
    $("adaptive-questions").hidden = faseQuestionario !== "misure";
    $("prepare-comparison-plan").hidden = !pronto || faseQuestionario !== "misure";
    $("confirm-preprocessing-phase").disabled = !pronto;
    $("phase-preprocessing-help").textContent = pronto
      ? "Puoi selezionare le colonne. Se una misura successiva risulta incompatibile, torna qui."
      : ciSonoAnomalie && !outlierConfermati
        ? "Prima di procedere, conferma che i valori estremi siano reali. " +
          "Se sono errori, sono da verificare oppure non ne conosci il significato, " +
          "il preprocessing resta sospeso."
        : "Conferma le trasformazioni quantitative proposte o modificate.";
    aggiornaVisibilitaTrasformazione();
    mostraFaseQuestionario();
    aggiornaGuida();
  }

  function confermaRiscalamentoNumerico() {
    if (!richiedeRiscalamentoConfermato()) return;
    const colonne = colonneNumericheDaRiscalare();
    if (colonne.length < 1) return;
    annullaConfermeCompatibilita();
    riscalamentoConfermato = true;
    interpretazione.riscalamentoConfermato = true;
    vista = "lavoro";
    // Le nuove domande sulla compatibilita' sono visibili solo DOPO
    // la conferma del riscalamento: rigenera subito il questionario.
    disegnaQuestionario();
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
        : "Nessun outlier univariato rilevante"]);
      elementi.push(["Asimmetria quartilica", (indicatori.colonneAsimmetriche || []).length
        ? indicatori.colonneAsimmetriche.map(v => v.nome + ": " +
          formatoNumero(v.asimmetriaBowley)).join("; ")
        : "Nessuna marcata, o diagnosi non disponibile"]);
      elementi.push(["Osservazioni multivariate", indicatori.diagnosiMultivariata?.stato === "valutata"
        ? indicatori.diagnosiMultivariata.numeroCandidati +
          " possibili anomalie su " + indicatori.diagnosiMultivariata.numeroValutate + " righe complete"
        : "Non valutabile: " + (indicatori.diagnosiMultivariata?.motivo || "dati insufficienti")]);
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
      elementi.push(["Valori utilizzati", proposta.idMisura === "blocchi_misti"
        ? "Quantità: preprocessing confermato se pertinente; Gower: valori originali"
        : "Gower sui valori originali: nessun riscalamento preliminare"]);
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
  "mahalanobis_ridge": [
    "Considera le relazioni fra le colonne aggiungendo una quantità positiva λ alla diagonale della covarianza.",
    "Il risultato dipende da λ e dalle unità dei valori originali: aumentare λ attenua l'effetto delle correlazioni.",
    "Se non vuoi modificare la covarianza, puoi rivedere le colonne; l'alternativa con pseudoinversa scarta le direzioni a varianza nulla.",
    "d(x,y)=\\sqrt{(x-y)^\\top(S+\\lambda I)^{-1}(x-y)}"
  ],
  "mahalanobis_pinv": [
    "Confronta le righe nelle direzioni della covarianza che superano la soglia relativa scelta.",
    "Le direzioni scartate non contribuiscono: la distanza può essere zero tra vettori diversi (pseudometrica).",
    "La regolarizzazione conserva invece tutte le direzioni, ma richiede λ positivo.",
    "d(x,y)=\\sqrt{(x-y)^\\top S^+(x-y)}"
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
      <p>Non è un errore del file. Se mantieni tutte le colonne, questa informazione ripetuta può influenzare più volte il risultato. Mahalanobis classica non può essere calcolata con covarianza singolare; nel menu della misura puoi scegliere esplicitamente la regolarizzazione (λ positivo) o la pseudoinversa (soglia relativa), senza che il sito decida per te.</p>
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
      ["automatico", "Confermo la misura proposta: " + percorso.metodo],
      ["euclidean", "Vicinanza complessiva (euclidea)"], ["manhattan", "Somma le differenze (Manhattan)"],
      ["chebyshev", "Conta la maggiore differenza (Chebyshev)"], ["minkowski", "Regola l’importanza degli scarti (Minkowski)"],
      ["weighted_minkowski", "Dai importanza diversa alle colonne (Minkowski pesata)"],
      ["weighted_chebyshev", "Conta la maggiore differenza ponderata (Chebyshev pesata)"],
      ["mahalanobis", "Mahalanobis classica (covarianza invertibile)"],
      ["mahalanobis_ridge", "Mahalanobis regolarizzata: mantieni tutte le direzioni (avanzato)"],
      ["mahalanobis_pinv", "Mahalanobis con pseudoinversa: ignora direzioni dipendenti (avanzato)"],
      ["canberra", "Confronta gli scarti relativi (Canberra)"],
      ["bray_curtis", "Confronta quantità complessive (Bray–Curtis)"], ["chi_square", "Dai rilievo alle componenti piccole (chi-quadrato)"]
    ];
    const scelta = interpretazione.misuraNumericaManuale || "automatico";
    const famiglie = [
      ["Differenze nelle coordinate", ["manhattan", "euclidean", "chebyshev",
        "minkowski", "weighted_minkowski", "weighted_chebyshev"]],
      ["Relazioni fra coordinate", ["mahalanobis", "mahalanobis_ridge", "mahalanobis_pinv"]],
      ["Quantità e frequenze", ["canberra", "bray_curtis", "chi_square"]]
    ];
    const opzioniPerId = new Map(opzioni);
    const menuMisure = '<option value="automatico"' +
      (scelta === "automatico" ? ' selected' : '') + '>' +
      escapeHtml(opzioniPerId.get("automatico")) + '</option>' +
      famiglie.map(([famiglia, ids]) =>
        '<optgroup label="' + escapeHtml(famiglia) + '">' +
        ids.map(id => '<option value="' + id + '"' +
          (id === scelta ? ' selected' : '') + '>' +
          escapeHtml(opzioniPerId.get(id)) + '</option>').join('') +
        '</optgroup>'
      ).join("");
    const esponente = ["minkowski", "weighted_minkowski"].includes(scelta);
    const pesata = ["weighted_minkowski", "weighted_chebyshev"].includes(scelta);
    const colonne = percorso.colonne;
    const sceltaDoppioZero = interpretazione.convenzioneBrayCurtisZero || "";
    const opzioniDoppioZero = [
      ["", "Scegli esplicitamente"],
      ["zero", "Considerale uguali: distanza zero, contributo valido"],
      ["indefinita", "Lascia il confronto non definito; servirà un altro blocco"]
    ];
    const brayInfo = percorso.idMisura === "bray_curtis" &&
      percorso.coppieBrayDoppioZero > 0
      ? '<label for="bray-zero-convention"><strong>Come confrontare due righe ' +
        'che contengono solo zeri?</strong></label>' +
        '<p>Bray–Curtis produce 0/0 in ' +
        escapeHtml(String(percorso.coppieBrayDoppioZero)) +
        ' coppie. La formula non definisce questa distanza; ' +
        'la scelta non viene applicata automaticamente.</p>' +
        '<select id="bray-zero-convention">' +
        opzioniDoppioZero.map(([valore, etichetta]) =>
          '<option value="' + valore + '"' +
          (sceltaDoppioZero === valore ? ' selected' : '') + '>' +
          escapeHtml(etichetta) + '</option>'
        ).join('') + '</select>'
      : "";
    return `<div class="numeric-measure-editor">
      <label for="numeric-measure-choice"><strong>Come vuoi confrontare le righe?</strong></label>
      <select id="numeric-measure-choice">
        ${menuMisure}
      </select>
      <p>Manhattan somma gli scarti; Euclidea dà più influenza a quelli grandi; Chebyshev guarda il massimo. Minkowski permette di scegliere esponente e pesi. Mahalanobis tiene conto delle relazioni fra colonne, quando la covarianza lo consente. Canberra confronta differenze relative; Bray–Curtis confronta abbondanze complessive; chi-quadrato accentua differenze nelle componenti piccole. La proposta del sito richiede una conferma esplicita.</p>
      ${brayInfo}
      ${esponente ? `<label for="numeric-measure-q">Quanto vuoi dare rilievo alle differenze grandi? (q ≥ 1)</label><p>Con 1 sommi tutte le differenze; con 2 quelle grandi hanno maggiore influenza. Per altre scelte serve un valore almeno pari a 1.</p><input id="numeric-measure-q" type="number" min="1" step="0.5" value="${escapeHtml(interpretazione.ordineMisuraManuale || "2")}">` : ""}
      ${pesata ? `<label for="numeric-measure-weights">Quanto conta ogni colonna? ${colonne.map(escapeHtml).join(", ")}</label><input id="numeric-measure-weights" type="text" value="${escapeHtml(interpretazione.pesiMisuraManuale || colonne.map(() => "1").join("; "))}"><small>Inserisci un numero positivo per colonna, separando con punto e virgola. Usa 1 per tutte se devono avere la stessa importanza.</small>` : ""}
      ${scelta === "mahalanobis_ridge" ? `<label for="numeric-measure-lambda">Regolarizzazione λ (numero strettamente positivo)</label><input id="numeric-measure-lambda" type="text" inputmode="decimal" value="${escapeHtml(interpretazione.lambdaMahalanobis ?? "")}" placeholder="es. 1"><small>Il sito calcola S + λI sulle coordinate originali. λ ha le unità al quadrato dei dati; non viene scelto automaticamente. Se λ è troppo piccolo, il calcolo resta bloccato.</small>` : ""}
      ${scelta === "mahalanobis_pinv" ? `<label for="numeric-measure-tolerance">Soglia relativa della pseudoinversa (tra 1e-12 e 0.1)</label><input id="numeric-measure-tolerance" type="text" inputmode="decimal" value="${escapeHtml(interpretazione.tolleranzaPseudoinversa ?? "")}" placeholder="es. 1e-10"><small>Gli autovalori non superiori a questa frazione del massimo sono scartati. La matrice può descrivere una pseudometrica: scarti in direzioni scartate contano zero.</small>` : ""}
      <button class="secondary-action" id="apply-numeric-measure" type="button">Conferma questa misura</button>
    </div>`;
  }

  function disegnaPiano(piano) {
    azzeraProblemiCalcolo();
    pianoCorrente = piano;
    matriceCorrente = null;
    $("gower-result").hidden = true;
    disegnaDiagnosi(piano.diagnosi, piano.completo);
    const pesiGlobali = piano.pesaturaGlobale || {};
    const modalitaPesiGlobali = pesiGlobali.modalita ||
      (Object.keys(interpretazione.pesiPercorsi || {}).length
        ? "personalizzati" : "uguali");
    const scegliPesiGlobali = piano.conteggioPercorsi > 1
      ? '<div class="question-item global-weights-configuration">' +
        '<label for="global-weights-mode"><strong>Come vuoi assegnare l’importanza ai blocchi?</strong></label>' +
        '<select id="global-weights-mode" class="global-weights-mode">' +
        [
          ["uguali", "Stesso peso per ogni blocco (1 ciascuno)"],
          ["dimensione", "Proposta: peso pari al numero di colonne di ogni blocco"],
          ["personalizzati", "Decido io il peso di ciascun blocco"]
        ].map(([id, nome]) =>
          '<option value="' + id + '"' +
          (modalitaPesiGlobali === id ? ' selected' : '') + '>' +
          escapeHtml(nome) + '</option>'
        ).join("") + '</select>' +
        '<p>' + escapeHtml(pesiGlobali.descrizione ||
          "La scelta cambia solo i pesi globali, non quelli interni alle misure.") +
        '</p><p>Un blocco può contenere molte colonne e rappresentare un solo ' +
        'oggetto composto. Pesare i blocchi in proporzione al numero di colonne ' +
        'non equivale, in generale, a pesare ogni informazione elementare allo stesso modo. ' +
        'Le colonne usate sono disgiunte; i pesi restano positivi.</p></div>'
      : "";
    $("comparison-plan-paths").innerHTML = scegliPesiGlobali +
      piano.percorsi.map((percorso, indice) => {
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
      const costantiGower = (percorso.colonneCostantiGower || []).map(escapeHtml).join(", ");
      const parametri = Object.entries(percorso.parametri || {}).map(([chiave, valore]) =>
        `${escapeHtml(chiave)} = ${escapeHtml(Array.isArray(valore) ? valore.join(", ") : valore)}`
      ).join(" · ");
      const editorNumerico = percorso.tipo === "numerico" ? editorMisuraNumerica(percorso) : "";
      const compat = percorso.compatibilitaPreelaborazione || {};
      const origineNonConfermata = compat.richiesta === "originali_numerico" && !compat.confermata
        ? '<label>Confermi di usare i valori originali per questa misura, ' +
          'senza applicare i riscalamenti preliminari già confermati?' +
          '<select class="numeric-origin-confirmation">' +
          '<option value="">Scegli una risposta</option>' +
          '<option value="si">Sì, confermo l’uso dei valori originali</option>' +
          '</select></label>'
        : "";

      const norma = percorso.normalizzazione || {};
      const valoreMetodo = String(norma.metodo || "campionaria");
      const nomeId = escapeHtml(percorso.idPercorso);
      const limitata = norma.limiteTeorico !== null && norma.limiteTeorico !== undefined;
      const opzioniNorma = limitata
        ? [['teorica', 'Conserva il limite teorico della misura']]
        : [
            ['campionaria', 'Massimo di tutte le distanze osservate'],
            ['robusta', 'Massimo delle distanze tra le righe non anomale che confermo']
          ];
      if (!opzioniNorma.some(([id]) => id === valoreMetodo)) {
        opzioniNorma.unshift([valoreMetodo, 'Scelta precedente incompatibile: modifica per proseguire']);
      }
      const menuNorma = opzioniNorma.map(([id, label]) =>
        '<option value="' + escapeHtml(id) + '"' +
        (id === valoreMetodo ? ' selected' : '') + '>' + escapeHtml(label) + '</option>'
      ).join('');
      const righeDaEscludere = interpretazione.righeAnomaleNormalizzazione?.[percorso.idPercorso] || '';
      const configNorma = '<div class="question-item"><label><strong>Come riportare ' +
        'la dissimilarità di questo percorso nell’intervallo [0,1]?</strong>' +
        '<select class="path-normalization-method" data-path-id="' + nomeId + '">' +
        menuNorma + '</select></label>' +
        (limitata
          ? '<p>Il limite è noto teoricamente: ' + formatoNumero(norma.limiteTeorico) +
            '. Non si modifica la scala in base alle osservazioni caricate.</p>'
          : '<p>In assenza di un massimo teorico, la scelta iniziale è il massimo ' +
            'campionario. Puoi scegliere invece una scala robusta quando confermi ' +
            'quali righe sono anomale; gli outlier restano nella matrice e alcune ' +
            'coppie potrebbero saturare a 1.</p>') +
        (!limitata && valoreMetodo === 'robusta'
          ? '<label>Righe anomale del CSV da escludere SOLO dalla stima della scala ' +
            '(prima riga dei dati = 1, separa con ;)' +
            '<input type="text" class="path-robust-rows" data-path-id="' + nomeId +
            '" value="' + escapeHtml(righeDaEscludere) +
            '" placeholder="es. 3; 8"></label>' +
            '<p>Servono almeno due righe non anomale confrontabili, con distanza ' +
            'massima positiva salvo il caso di tutte le distanze nulle. ' +
            'Nessuna riga viene esclusa dalla matrice finale.</p>'
          : '') +
        '<p>Regola applicata: ' + escapeHtml(norma.descrizione || '') + '</p></div>';
      const numeroCaratteristiche = percorso.numeroCaratteristiche ??
        percorso.colonne.length;
      const pesoAggregazione = piano.conteggioPercorsi > 1
        ? (modalitaPesiGlobali === "personalizzati"
          ? `<label class="path-weight-label"><strong>Peso personalizzato per questo blocco</strong>
            <input class="path-weight" type="number" min="0" step="any"
              data-path-id="${escapeHtml(percorso.idPercorso)}"
              value="${escapeHtml(percorso.pesoAggregazione)}">
            <small>Inserisci un valore strettamente positivo: 0 non esclude il blocco.
            Per escludere una colonna o un blocco modifica la selezione dei dati.</small>
          </label>`
          : `<p class="path-weight-summary"><strong>Peso globale: ${formatoNumero(percorso.pesoAggregazione)}</strong>
            ${modalitaPesiGlobali === "dimensione"
              ? "(numero delle " + numeroCaratteristiche + " colonne del blocco)"
              : "(stesso peso per ogni blocco)"}</p>`)
        : "";
      const numeroColonneBlocco = piano.conteggioPercorsi > 1
        ? `<div><dt>Colonne del blocco</dt><dd>${numeroCaratteristiche}</dd></div>`
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
          <div><dt>Compatibilità</dt><dd>${escapeHtml(compat.descrizione || "Nessuna incompatibilità rilevata.")}</dd></div>
          ${parametri ? `<div><dt>Parametri</dt><dd>${parametri}</dd></div>` : ""}
          ${pesiGower ? `<div><dt>Pesi Gower</dt><dd>${pesiGower}</dd></div>` : ""}
          ${costantiGower ? `<div><dt>Colonne costanti</dt><dd>Contributo zero, ma peso mantenuto: ${costantiGower}</dd></div>` : ""}
          <div><dt>Mancanti</dt><dd>${escapeHtml(mancanti.descrizione)}</dd></div>
          ${numeroColonneBlocco}
          ${percorso.proprieta ? `<div><dt>Proprietà</dt><dd>${escapeHtml(percorso.proprieta)}</dd></div>` : ""}
          <div><dt>Stato</dt><dd>${escapeHtml(calcolo)}</dd></div>
        </dl>
        <span>${escapeHtml(pre.descrizione)}</span>
        ${percorso.tipo === "numerico" ? spiegazioneMisuraNumerica(percorso) : `<p>${escapeHtml(percorso.motivo)}</p>`}
        ${percorso.tipo === "numerico" ? controlloDipendenzaLineare(percorso) : ""}
        ${percorso.notaPreelaborazione ? `<p><strong>Quali valori vengono usati:</strong> ${escapeHtml(percorso.notaPreelaborazione)}</p>` : ""}
        ${pesoAggregazione}
        ${configNorma}
        ${origineNonConfermata}
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
    const rapporto = piano.rapportoProblemi;
    if (rapporto) {
      $("comparison-plan-warnings").innerHTML =
        '<h5>Rapporto complessivo del piano</h5>' +
        '<p><strong>' + escapeHtml(String(rapporto.numeroBloccanti)) +
        ' problemi bloccanti</strong> e ' +
        escapeHtml(String(rapporto.numeroAvvisi)) + ' avvisi informativi. ' +
        (rapporto.calcoloConsentito
          ? 'Il piano può essere calcolato; gli avvisi non bloccano.'
          : 'Completa le decisioni richieste prima di calcolare.') + '</p>' +
        (rapporto.bloccanti.length
          ? '<h6>Da risolvere prima del calcolo</h6>' +
            elencoProblemiHtml(rapporto.bloccanti)
          : '') +
        (rapporto.nonBloccanti.length
          ? '<details><summary>Osservazioni che non impediscono il calcolo (' +
            escapeHtml(String(rapporto.numeroAvvisi)) + ')</summary>' +
            elencoProblemiHtml(rapporto.nonBloccanti) + '</details>'
          : '');
    } else {
      $("comparison-plan-warnings").innerHTML = avvisi.length
        ? '<p><strong>Che cosa controllare prima del calcolo:</strong></p><ul>' +
          avvisi.map(avviso => '<li>' + escapeHtml(avviso) + '</li>').join("") +
          '</ul>'
        : "";
    }
    const semantica = piano.diagnosticaMancantiSemantici;
    const totaliMancanti = semantica?.attiva
      ? (" Marcatori confermati: " +
        "sconosciuti " + (semantica.totali?.sconosciuto || 0) +
        ", non applicabili " + (semantica.totali?.non_applicabile || 0) +
        ", assenze reali " + (semantica.totali?.assenza || 0) +
        ". Gli ultimi sono osservati soltanto nei blocchi compatibili.")
      : "";
    $("comparison-plan-intro").textContent = (!piano.completo
      ? "Il piano è stato preparato, ma alcune informazioni devono ancora essere completate."
      : piano.conteggioPercorsi === 1
        ? "È stato individuato un unico percorso di confronto."
        : `Sono stati individuati ${piano.conteggioPercorsi} percorsi. Il sito li renderà confrontabili e produrrà una sola matrice complessiva usando le importanze indicate.`) + totaliMancanti;
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
    aggiornaGuida();
  }

  function disegnaDiagnosticaFinale(risposta) {
    const contenitore = $("gower-diagnostics");
    const analisi = risposta.diagnosticaFinale?.sensibilitaPesi;
    const distribuzione = risposta.diagnosticaFinale?.distribuzioneDissimilarita;
    const presentazioneDistribuzione = distribuzione?.numeroCoppie > 0
      ? '<section class="final-distribution" aria-label="Distribuzione delle dissimilarità">' +
        '<h6>Distribuzione delle dissimilarità finali</h6>' +
        '<p>Si considera una volta ogni coppia di righe distinte (' +
        escapeHtml(String(distribuzione.numeroCoppie)) +
        ' confronti), senza contare la diagonale né duplicare le coppie simmetriche. ' +
        'I valori sono descrittivi: non modificano la matrice.</p>' +
        '<p>Minimo: <strong>' + escapeHtml(formatoNumero(distribuzione.minimo)) +
        '</strong>; massimo: <strong>' + escapeHtml(formatoNumero(distribuzione.massimo)) +
        '</strong>; media: <strong>' + escapeHtml(formatoNumero(distribuzione.media)) +
        '</strong>; mediana: <strong>' + escapeHtml(formatoNumero(distribuzione.mediana)) +
        '</strong>; primo e terzo quartile: <strong>' +
        escapeHtml(formatoNumero(distribuzione.primoQuartile)) + '</strong> e <strong>' +
        escapeHtml(formatoNumero(distribuzione.terzoQuartile)) + '</strong>.</p>' +
        '<ul class="final-distribution-list">' +
        (distribuzione.intervalli || []).map(voce => {
          const percentuale = Math.max(0, Math.min(
            100, 100 * Number(voce.frazione)
          ));
          const intervallo = '[' + formatoNumero(voce.inizio) + '; ' +
            formatoNumero(voce.fine) + (voce.fineInclusa ? ']' : ')');
          return '<li><span class="final-distribution-range">' +
            escapeHtml(intervallo) + '</span>' +
            '<span class="final-distribution-track" aria-hidden="true">' +
            '<span style="width: ' + percentuale + '%"></span></span>' +
            '<span class="final-distribution-count">' +
            escapeHtml(String(voce.coppie)) + ' (' +
            escapeHtml(formatoNumero(percentuale)) + '%)</span></li>';
        }).join('') +
        '</ul>' +
        '<p>Coppie a distanza zero: ' +
        escapeHtml(String(distribuzione.coppieZero)) +
        '; coppie a distanza uno: ' + escapeHtml(String(distribuzione.coppieUno)) +
        ' (con tolleranza numerica 10⁻¹²). I quartili sono calcolati con ' +
        'interpolazione lineare sui confronti ordinati.</p></section>'
      : '';
    if (!analisi?.perBlocco?.length) {
      contenitore.innerHTML = presentazioneDistribuzione;
      contenitore.hidden = !presentazioneDistribuzione;
      return;
    }
    const nulle = analisi.blocchiSempreNulli || [];
    const presentazioneNulle = nulle.length
      ? '<p class="final-diagnostics-warning"><strong>Attenzione ai blocchi con distanza nulla.</strong> ' +
        nulle.map(voce =>
          '«' + escapeHtml(voce.titolo) + '» (peso ' +
          escapeHtml(formatoNumero(voce.peso)) + ', ' +
          escapeHtml(String(voce.coppieDefinite)) +
          ' coppie definite): distanza zero per tutte le coppie in cui contribuisce. ' +
          (voce.attenuazioneMassimaRimuovendolo === null
            ? 'La sua rimozione potrebbe lasciare alcune coppie senza confronto.'
            : 'Variazione massima ipotetica senza questo blocco, ' +
              'fra le coppie ancora confrontabili: ' +
              escapeHtml(formatoNumero(voce.attenuazioneMassimaRimuovendolo)) + '.')
        ).join(' ') +
        ' Questi zeri sono contributi validi e restano nel denominatore.</p>'
      : '<p>Nessun blocco ha distanza nulla su tutti i confronti locali disponibili.</p>';
    if (analisi.numeroBlocchi === 1) {
      contenitore.innerHTML = presentazioneDistribuzione +
        '<h6>Influenza dei pesi e dei blocchi</h6>' +
        '<p>È presente un unico blocco: moltiplicarne il peso per un ' +
        'fattore positivo non cambia la matrice. Non si può rimuoverlo ' +
        'senza perdere il confronto.</p>' + presentazioneNulle;
      contenitore.hidden = false;
      return;
    }
    const righe = analisi.perBlocco.map(voce => {
      const rim = voce.senzaBlocco;
      const maxRim = rim.variazioneMassimaAssoluta === null
        ? 'Non definibile' : formatoNumero(rim.variazioneMassimaAssoluta);
      return '<tr><th scope="row">' + escapeHtml(voce.titolo) +
        '</th><td>' + escapeHtml(formatoNumero(voce.pesoOriginale)) +
        '</td><td>' + escapeHtml(String(voce.coppieDefinite)) +
        ' / ' + escapeHtml(String(analisi.coppieTotali)) +
        '</td><td>' + escapeHtml(formatoNumero(
          voce.fattoreMezzo.variazioneMassimaAssoluta
        )) + '</td><td>' + escapeHtml(formatoNumero(
          voce.fattoreDoppio.variazioneMassimaAssoluta
        )) + '</td><td>' + escapeHtml(maxRim) +
        ' (' + escapeHtml(String(rim.coppieConfrontabili)) + ' coppie)</td><td>' +
        escapeHtml(String(rim.coppieSenzaAltroContributo)) + '</td></tr>';
    }).join("");
    contenitore.innerHTML = presentazioneDistribuzione +
      '<h6>Influenza dei pesi e dei blocchi</h6>' +
      '<p>Analisi non bloccante: si varia <strong>un solo peso globale per volta</strong> ' +
      'a metà o al doppio, mantenendo fisse le misure e le normalizzazioni locali. ' +
      'Le differenze indicate sono i massimi scarti assoluti dalla matrice attuale, ' +
      'nell’intervallo [0,1]. La rimozione è soltanto ipotetica.</p>' +
      presentazioneNulle +
      '<div class="data-table-wrap"><table class="data-table final-diagnostics-table">' +
      '<thead><tr><th scope="col">Blocco</th><th scope="col">Peso</th>' +
      '<th scope="col">Coppie locali disponibili</th>' +
      '<th scope="col">Variazione max, peso ×0,5</th>' +
      '<th scope="col">Variazione max, peso ×2</th>' +
      '<th scope="col">Variazione max senza blocco</th>' +
      '<th scope="col">Coppie non confrontabili senza blocco</th>' +
      '</tr></thead><tbody>' + righe + '</tbody></table></div>' +
      '<p>La rimozione di un blocco non è una nuova scelta applicata alla matrice: ' +
      'si confrontano soltanto le coppie che resterebbero definite. ' +
      'Le medie, i massimi e i conteggi completi sono registrati nel rapporto JSON. ' +
      'Una variazione elevata non indica da sola un errore.</p>';
    contenitore.hidden = false;
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
    const avvisiFinali = risposta.diagnosticaFinale?.avvisi || [];
    const stati = risposta.diagnosticaMancantiSemantici;
    const diagnosticaMista = stati?.attiva
      ? ` Marcatori nel CSV: ${stati.totali?.sconosciuto || 0} sconosciuti, ${stati.totali?.non_applicabile || 0} non applicabili, ${stati.totali?.assenza || 0} assenze realmente osservate confermate.`
      : "";
    $("gower-result-caption").textContent = `${risposta.etichette.length} × ${risposta.etichette.length}. ${risposta.nota}${limite < risposta.etichette.length ? ` Anteprima delle prime ${limite} righe.` : ""}${diagnosticaMista}${avvisiFinali.length ? " Diagnostica (non bloccante): " + avvisiFinali.join(" ") : ""}`;
    disegnaDiagnosticaFinale(risposta);
    $("download-gower").disabled = false;
    $("download-report").disabled = false;
    $("gower-result").hidden = false;
    aggiornaGuida();
  }

  async function calcolaMatrice() {
    if (!pianoCorrente) return;
    azzeraProblemiCalcolo();
    const versione = ++versioneMatrice;
    const versioneFile = versioneDati;
    const versioneConfigurazione = versionePiano;
    const pulsante = $("calculate-gower");
    $("download-report").disabled = true;
    const testo = pulsante.textContent;
    pulsante.disabled = true;
    pulsante.textContent = "Calcolo…";
    try {
      const risposta = await P.calcolaMatrice(
        testoOriginale, scelte.map(scelta => ({ ...scelta })),
        JSON.parse(JSON.stringify(interpretazione)),
        importazioneCSV || {}
      );
      if (versione !== versioneMatrice ||
          versioneConfigurazione !== versionePiano ||
          versioneFile !== versioneDati) return;
      matriceCorrente = risposta;
      azzeraProblemiCalcolo();
      nascondiErrore();
      disegnaMatrice(risposta);
    } catch (errore) {
      if (versione !== versioneMatrice ||
          versioneConfigurazione !== versionePiano ||
          versioneFile !== versioneDati) return;
      matriceCorrente = null;
      $("gower-result").hidden = true;
      $("download-gower").disabled = true;
      $("download-report").disabled = true;
      disegnaProblemiCalcolo(errore.rapportoProblemi);
      mostraErrore(errore.message);
    } finally {
      if (versione === versioneMatrice) {
        pulsante.disabled = false;
        pulsante.textContent = testo;
      }
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

  async function scaricaRapporto() {
    // Il rapporto incorpora la sorgente e l'intera matrice. Si calcola
    // nuovamente nello stesso motore, evitando di assemblare in JS un
    // "piano" e una matrice appartenenti a revisioni differenti.
    if (!matriceCorrente || !pianoCorrente?.completo) return;
    const versione = versioneMatrice;
    const versioneFile = versioneDati;
    const versioneConfigurazione = versionePiano;
    const matriceAttuale = matriceCorrente;
    const pulsante = $("download-report");
    const etichetta = pulsante.textContent;
    pulsante.disabled = true;
    pulsante.textContent = "Preparazione rapporto…";
    try {
      const rapporto = await P.creaRapporto(
        testoOriginale,
        scelte.map(scelta => ({...scelta})),
        JSON.parse(JSON.stringify(interpretazione)),
        $("csv-file-name").textContent,
        importazioneCSV || {}
      );
      if (versione !== versioneMatrice ||
          versioneFile !== versioneDati ||
          versioneConfigurazione !== versionePiano ||
          matriceCorrente !== matriceAttuale) return;
      if (rapporto.risultato.csvMatrice !== matriceAttuale.csv) {
        throw new Error(
          "La matrice del rapporto non coincide con quella visualizzata. " +
          "Ricalcola la matrice prima di esportare il rapporto."
        );
      }
      const json = JSON.stringify(rapporto, null, 2) + "\n";
      const url = URL.createObjectURL(new Blob([json], {
        type: "application/json;charset=utf-8"
      }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "rapporto_calcolo.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      nascondiErrore();
    } catch (errore) {
      if (versione !== versioneMatrice ||
          versioneFile !== versioneDati ||
          versioneConfigurazione !== versionePiano) return;
      mostraErrore(errore.message);
    } finally {
      if (versione === versioneMatrice &&
          versioneFile === versioneDati &&
          versioneConfigurazione === versionePiano) {
        pulsante.disabled = false;
        pulsante.textContent = etichetta;
      }
    }
  }

  async function preparaPiano() {
    nascondiPiano();
    const versione = ++versionePiano;
    const versioneFile = versioneDati;
    const pulsante = $("prepare-comparison-plan");
    const testo = pulsante.textContent;
    pulsante.disabled = true;
    pulsante.textContent = "Preparazione…";
    try {
      const piano = await P.creaPiano(
        testoOriginale, scelte.map(scelta => ({ ...scelta })),
        JSON.parse(JSON.stringify(interpretazione)),
        importazioneCSV || {}
      );
      if (versione !== versionePiano || versioneFile !== versioneDati) return;
      nascondiErrore();
      disegnaPiano(piano);
    } catch (errore) {
      if (versione !== versionePiano || versioneFile !== versioneDati) return;
      mostraErrore(errore.message);
    } finally {
      if (versione === versionePiano) {
        pulsante.disabled = false;
        pulsante.textContent = testo;
      }
    }
  }

  function creaGruppo() {
    const numero = interpretazione.prossimoGruppo++;
    const gruppo = { id: `gruppo-${numero}`, nome: `Gruppo ${numero}`, tipo: "altro" };
    interpretazione.gruppi.push(gruppo);
    return gruppo;
  }

  function opzioniGruppo(selezionato) {
    const assegnazioneObsoleta = selezionato &&
      !interpretazione.gruppi.some(gruppo => gruppo.id === selezionato);
    const opzioneObsoleta = assegnazioneObsoleta
      ? '<option value="' + escapeHtml(selezionato) + '" selected disabled>' +
        'Assegnazione non valida: gruppo “' + escapeHtml(selezionato) +
        '” non trovato. Scegli nuovamente.</option>'
      : "";
    const gruppi = interpretazione.gruppi.map(gruppo =>
      `<option value="${escapeHtml(gruppo.id)}"${selezionato === gruppo.id ? " selected" : ""}>${escapeHtml(gruppo.nome)}</option>`
    ).join("");
    return opzioneObsoleta +
      `<option value=""${!selezionato ? " selected" : ""}>Caratteristica indipendente</option>${gruppi}<option value="__nuovo__">+ Crea un nuovo gruppo</option>`;
  }

  function disegnaGruppi() {
    const profili = risultato.questionario.colonne;
    const incluse = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa);
    profili.filter(profilo => !interpretazione.colonne[profilo.nome]?.usa).forEach(profilo => {
      delete interpretazione.assegnazioni[profilo.nome];
    });
    const indipendenti = incluse.filter(profilo => !interpretazione.assegnazioni[profilo.nome]);
    const idGruppiEsistenti = new Set(interpretazione.gruppi.map(gruppo => gruppo.id));
    const assegnazioniDaCorreggere = incluse.filter(profilo =>
      interpretazione.assegnazioni[profilo.nome] &&
      !idGruppiEsistenti.has(interpretazione.assegnazioni[profilo.nome])
    );
    const gruppiAttivi = interpretazione.gruppi.map(gruppo => ({
      gruppo,
      membri: incluse.filter(profilo => interpretazione.assegnazioni[profilo.nome] === gruppo.id)
    })).filter(elemento => elemento.membri.length);
    $("group-summary").innerHTML =
      `<p><strong>Caratteristiche indipendenti (${indipendenti.length}):</strong> ${indipendenti.length ? indipendenti.map(p => escapeHtml(p.nome)).join(", ") : "nessuna"}.</p>` +
      (gruppiAttivi.length
        ? `<p><strong>Gruppi strutturati (${gruppiAttivi.length}):</strong> ${gruppiAttivi.map(({ gruppo, membri }) => escapeHtml(gruppo.nome) + " (" + membri.map(p => escapeHtml(p.nome)).join(", ") + ")").join("; ")}.</p>`
        : "<p>Nessuna colonna assegnata a un gruppo valido. Puoi crearne più di uno, lasciando le altre colonne indipendenti.</p>") +
      (assegnazioniDaCorreggere.length
        ? '<p><strong>Assegnazioni da correggere prima del calcolo:</strong> ' +
          assegnazioniDaCorreggere.map(profilo =>
            escapeHtml(profilo.nome) + ' → ' +
            escapeHtml(interpretazione.assegnazioni[profilo.nome])
          ).join("; ") +
          '. Per ciascuna scegli un gruppo esistente o conferma la caratteristica indipendente.</p>'
        : "");
    $("group-assignment-body").innerHTML = incluse.length ? incluse.map(profilo => `<tr>
      <th scope="row">${escapeHtml(profilo.nome)}</th>
      <td><select class="column-choice group-assignment" data-group-column="${escapeHtml(profilo.nome)}" aria-label="Gruppo della colonna ${escapeHtml(profilo.nome)}">${opzioniGruppo(interpretazione.assegnazioni[profilo.nome] || "")}</select></td>
    </tr>`).join("") : `<tr><td colspan="2">Non è stata inclusa alcuna colonna nel confronto.</td></tr>`;

    $("group-config-list").innerHTML = interpretazione.gruppi.map(gruppo => {
      const membri = incluse.filter(profilo => interpretazione.assegnazioni[profilo.nome] === gruppo.id).map(profilo => profilo.nome);
      const tipi = membri.map(nome => risultato.colonne.find(colonna => colonna.nome === nome)?.tipo);
      const tutteNumeriche = tipi.length >= 2 && tipi.every(tipo =>
        tipo === "numerica" || tipo === "numerica_costante" ||
        (["distribuzione", "tempo_coppie"].includes(gruppo.tipo) && tipo === "binaria")
      );
      const tutteQuantitative = tutteNumeriche && membri.every(nome => interpretazione.colonne[nome]?.ruolo === "quantita");
      const tutteBinarie = membri.length >= 2 && membri.every((nome, indice) =>
        ["binaria", "non_numerica", "numerica_costante"].includes(tipi[indice]) &&
        ["binaria", "presenza"].includes(interpretazione.colonne[nome]?.ruolo)
      );
      const nota = membri.length < (gruppo.tipo === "tempo_coppie" ? 4 : 2)
        ? (gruppo.tipo === "tempo_coppie"
          ? "Assegna almeno quattro colonne (due coppie tempo-valore)."
          : "Assegna almeno due colonne a questo gruppo.")
        : gruppo.tipo === "vettore_binario" && !tutteBinarie
          ? "Per questo gruppo servono risposte binarie o presenze, con stati 0/1 oppure sì/no."
          : !tutteQuantitative && !["altro", "vettore_binario"].includes(gruppo.tipo)
            ? "Per questa interpretazione servono quantità numeriche: verifica che non siano codici o livelli."
            : `Colonne: ${membri.join(", ")}.`;
      return `<div class="group-config" data-group-id="${gruppo.id}">
        <label>Nome del gruppo<input class="group-name" value="${escapeHtml(gruppo.nome)}" aria-label="Nome di ${escapeHtml(gruppo.nome)}"></label>
        <label>Che cosa formano insieme?<select class="group-type" aria-label="Tipo di ${escapeHtml(gruppo.nome)}">
          <option value="altro"${gruppo.tipo === "altro" ? " selected" : ""}>Da specificare</option>
          <option value="ripetute"${gruppo.tipo === "ripetute" ? " selected" : ""}>Misurazioni dello stesso profilo</option>
          <option value="coordinate"${gruppo.tipo === "coordinate" ? " selected" : ""}>Coordinate quantitative da confrontare insieme</option>
          <option value="tempo"${gruppo.tipo === "tempo" ? " selected" : ""}>Serie con gli stessi istanti per tutte le righe</option>
          <option value="tempo_coppie"${gruppo.tipo === "tempo_coppie" ? " selected" : ""}>Serie con istanti diversi per ogni riga (coppie tempo-valore)</option>
          <option value="parti"${gruppo.tipo === "parti" ? " selected" : ""}>Parti dello stesso totale (Aitchison)</option>
          <option value="distribuzione"${gruppo.tipo === "distribuzione" ? " selected" : ""}>Distribuzione di probabilità o istogramma</option>
          <option value="vettore_binario"${gruppo.tipo === "vettore_binario" ? " selected" : ""}>Insieme di presenze/assenze da confrontare come vettore binario</option>
        </select></label>
        <p>${escapeHtml(nota)}</p>
        <button class="remove-group" type="button">Rimuovi gruppo</button>
      </div>`;
    }).join("");
  }

  function domandeConfigurazioneGower(profili) {
    if (!profili.length) return "";
    const campi = [];
    const mancantiCSV = new Set(importazioneCSV?.marcatoriMancanti || ["", "na", "n/a", "null", "?"]);
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


    function configuraNominali(nome, livelli) {
      const scelta = interpretazione.modalitaCategorieGower?.[nome] || "semplice";
      let html = menu(
        "modalitaCategorieGower", nome,
        "Quanto devono essere differenti due categorie diverse?",
        [
          ["semplice", "Uguale o diverso: tutte le categorie distinte valgono 1"],
          ["personalizzata", "Imposto una dissimilarità diversa per ciascuna coppia"]
        ],
        scelta
      );
      if (scelta !== "personalizzata") return html;
      if (livelli.length > 16) {
        return html + '<p>Le categorie distinte sono ' + livelli.length +
          '. L’editor personalizzato supporta al massimo 16 stati: ' +
          'raggruppa le categorie in modo motivato o torna al confronto uguale/diverso.</p>';
      }
      const configurata = interpretazione.dissimilaritaCategorieGower?.[nome];
      const valida = configurata && JSON.stringify(configurata.livelli) === JSON.stringify(livelli);
      const coppie = valida ? (configurata.coppie || {}) : {};
      const etichetta = livello => livello === null ? "Assenza confermata" : String(livello);
      const righe = [];
      for (let i = 0; i < livelli.length; i++) {
        for (let j = i + 1; j < livelli.length; j++) {
          const chiave = i + ":" + j;
          righe.push(
            '<label>' + escapeHtml(etichetta(livelli[i])) + ' ↔ ' +
            escapeHtml(etichetta(livelli[j])) + ': dissimilarità tra 0 e 1' +
            '<input type="text" class="gower-nominal-pair" data-gower-nominal-column="' +
            escapeHtml(nome) + '" data-gower-pair="' + chiave +
            '" data-gower-levels="' + escapeHtml(JSON.stringify(livelli)) +
            '" value="' + escapeHtml(coppie[chiave] ?? "") +
            '" placeholder="es. 0,4"></label>'
          );
        }
      }
      return html + (
        righe.length
          ? '<p>Indica tutte le coppie, senza assumere che categorie distinte abbiano distanza 1. ' +
            'Valore 0 = nessuna differenza; valore 1 = massima differenza. ' +
            'La matrice sarà simmetrica e con diagonale nulla. ' +
            'Questi valori non devono necessariamente soddisfare la disuguaglianza triangolare.</p>' +
            righe.join('')
          : '<p>La colonna contiene un solo stato: il contributo è sempre zero.</p>'
      );
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

      if (risultato.colonne.find(c => c.nome === nome)?.mancanti > 0
          && rispostaMancanti !== "misto") {
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

      if (ruolo === "quantita" && valoreRisposta("tipoGowerNumeriche") === "robusta") {
        elementi += '<label>Quali righe del CSV consideri anomale in questa colonna? (numeri di riga dei dati, da 1)' +
          '<input class="gower-setting" data-gower-key="righeOutlierGower" data-gower-column="' +
          escapeHtml(nome) + '" type="text" value="' +
          escapeHtml(interpretazione.righeOutlierGower?.[nome] || "") +
          '" placeholder="es. 3; 8"></label>' +
          '<p>Queste righe saranno escluse soltanto dalla stima della scala robusta, ' +
          'non dal confronto finale. Lascia vuoto se questa colonna non ha valori anomali. ' +
          'Per definire la scala servono almeno due valori distinti non anomali.</p>';
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

      if (ruolo === "categoria") {
        const politica = interpretazione.mancantiPerColonna?.[nome] || "";
        const comeAssenza = (risultato.colonne.find(c => c.nome === nome)?.mancanti > 0) &&
          (rispostaMancanti === "misto"
              ? Object.values(interpretazione.statiMancantiPerColonna?.[nome] || {}).includes("assenza")
              : politica === "assenza" || (!politica && rispostaMancanti === "assenza"));
        const livelli = [...distinti].sort();
        if (comeAssenza) livelli.push(null);
        elementi += configuraNominali(nome, livelli);
      }
      if (ruolo === "livello") {
        elementi += menu("ordinePerColonna", nome, "I livelli di questa colonna sono ordinati?",
          [["", "Segui la risposta generale"],
            ["si", "Sì, hanno un ordine"], ["no", "No, sono semplici categorie"]],
          interpretazione.ordinePerColonna?.[nome] || "");
        const ordinale = interpretazione.ordinePerColonna?.[nome] || rispostaOrdini;
        if (ordinale === "no") {
          const politica = interpretazione.mancantiPerColonna?.[nome] || "";
          const comeAssenza = (risultato.colonne.find(c => c.nome === nome)?.mancanti > 0) &&
            (rispostaMancanti === "misto"
              ? Object.values(interpretazione.statiMancantiPerColonna?.[nome] || {}).includes("assenza")
              : politica === "assenza" || (!politica && rispostaMancanti === "assenza"));
          const livelliNominali = [...distinti].sort();
          if (comeAssenza) livelliNominali.push(null);
          elementi += configuraNominali(nome, livelliNominali);
        }
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
        if (ordinale === "si") {
          const numerici = tipo !== "non_numerica";
          const livelli = numerici
            ? [...new Set(distinti.map(v => Number(v.replace(",", "."))))].sort((a,b) => a-b)
            : (interpretazione.ordiniLivelliGower?.[nome] || "").split(";")
                .map(v => v.trim()).filter(Boolean);
          const modo = interpretazione.modalitaIntervalliGower?.[nome] || "equidistanti";
          elementi += menu(
            "modalitaIntervalliGower", nome,
            "Quanto sono distanti due livelli consecutivi?",
            [
              ["equidistanti", "Tutti gli intervalli contano allo stesso modo"],
              ["personalizzati", "Indico l’ampiezza di ciascun intervallo (avanzato)"]
            ],
            modo
          );
          if (modo === "personalizzati" && livelli.length >= 2) {
            const intervalli = livelli.slice(1).map((v,i) =>
              escapeHtml(String(livelli[i])) + " → " + escapeHtml(String(v))
            );
            elementi += '<label>Ampiezze positive degli intervalli, nell’ordine indicato (' +
              intervalli.length + ' valori, separati da ;)' +
              '<input class="gower-setting" data-gower-key="passiOrdinaliGower" ' +
              'data-gower-column="' + escapeHtml(nome) +
              '" type="text" value="' +
              escapeHtml(interpretazione.passiOrdinaliGower?.[nome] || "") +
              '" placeholder="es. 1; 3"></label>' +
              '<p>Intervalli: ' + intervalli.join("; ") +
              '. I valori sono riportati su una scala da 0 a 1 dividendo ' +
              'le distanze cumulative per la somma delle ampiezze. ' +
              'Tutte le ampiezze devono essere positive.</p>';
          } else if (modo === "personalizzati") {
            elementi += '<p>Definisci prima l’ordine completo dei livelli; ' +
              'serve almeno una coppia di livelli diversi.</p>';
          }
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
      ["pairwise", "Confronta solo le coordinate osservate da entrambe le righe"],
      ["imputa_mediana", "Sostituisci con il valore centrale (mediana)"],
      ["imputa_media", "Sostituisci con il valore medio"],
      ["zero", "Confermo che la casella vuota significa davvero zero"]
    ];
    return '<div class="question-item"><strong>Come trattare le caselle vuote nelle quantità?</strong>' +
      '<p>La scelta è separata per colonna. Escludere una riga riduce i dati disponibili; ' +
      'sostituire un valore introduce un’ipotesi esplicita. La scelta pairwise conserva ' +
      'le righe e ignora la coordinata soltanto nelle coppie in cui manca. ' +
      'È applicabile a Minkowski, euclidea, Manhattan e Chebyshev; con nessuna ' +
      'coordinata comune il confronto di quel percorso non è definito.</p></div>' +
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
      </tr>`;
    }).join("");
    $("selection-body").innerHTML = profili.map((profilo, indice) => {
      const risposta = interpretazione.colonne[profilo.nome];
      return `<tr>
        <th scope="row">${escapeHtml(profilo.nome)}</th>
        <td>${escapeHtml(etichettaRuolo(risposta.ruolo))}</td>
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
    if (valoreRisposta("significatoMancanti") === "misto") {
      domande.push('<div class="question-item"><strong>Significato dei simboli mancanti</strong>' +
        '<p>Per ogni colonna conferma che cosa rappresentano i simboli effettivamente presenti. ' +
        'Per esempio ? può indicare sconosciuto, N/A non applicabile e NA assenza, ' +
        'ma non assumiamo mai questi significati automaticamente. ' +
        'Lo stesso simbolo nella stessa colonna può avere un solo significato: ' +
        'se ne servono due, correggi prima la codifica nel CSV.</p>' +
        '<p>L’assenza confermata è uno stato osservato per categorie e variabili binarie. ' +
        'Non è automaticamente uno zero per quantità e timestamp.</p></div>');
      const marcatoriAmmessi = new Set(importazioneCSV?.marcatoriMancanti || ["", "na", "n/a", "null", "?"]);
      for (const profilo of profiliInclusi) {
        const nome = profilo.nome;
        const indice = risultato.originale.intestazioni.indexOf(nome);
        const conteggi = new Map();
        for (const riga of risultato.originale.righe) {
          const simbolo = String(riga[indice] ?? "").trim().toLocaleLowerCase();
          if (marcatoriAmmessi.has(simbolo)) {
            conteggi.set(simbolo, (conteggi.get(simbolo) || 0) + 1);
          }
        }
        if (!conteggi.size) continue;
        const righe = [...conteggi].map(([marcatore, numero]) => {
          const scelta = interpretazione.statiMancantiPerColonna?.[nome]?.[marcatore] || "";
          const nomeSimbolo = marcatore === "" ? "Cella vuota" : marcatore.toUpperCase();
          const opzioni = [
            ["", "Scegli il significato"],
            ["sconosciuto", "Valore non conosciuto: non osservato"],
            ["non_applicabile", "Non applicabile: non osservato"],
            ["assenza", "Assenza reale: stato osservato (categorie/binarie)"]
          ];
          return '<label>' + escapeHtml(nomeSimbolo) + ' — ' + numero +
            ' occorrenz' + (numero === 1 ? 'a' : 'e') +
            '<select class="missing-marker-setting" data-missing-column="' +
            escapeHtml(nome) + '" data-missing-marker="' + escapeHtml(marcatore) + '">' +
            opzioni.map(([id, txt]) =>
              '<option value="' + id + '"' + (scelta === id ? ' selected' : '') +
              '>' + escapeHtml(txt) + '</option>').join("") +
            '</select></label>';
        });
        domande.push('<div class="question-item"><strong>Colonna “' +
          escapeHtml(nome) + '”</strong>' + righe.join("") + '</div>');
      }
    }
    const anomalieQuantitative = colonneNumericheDaRiscalare().some(
      colonna => colonna.statistiche?.estremi > 0
    );
    $("preprocessing-questions").innerHTML = anomalieQuantitative
      ? domandaAdattiva(
          "significatoEstremi", "Alcuni valori sono molto lontani dagli altri: sono corretti?",
          "Rispondi prima di confermare il preprocessing. Un valore reale non viene eliminato; " +
            "un possibile errore richiede la verifica del CSV. " +
            "Questa è una segnalazione statistica, non una prova di errore.",
          [["reali", "Sì, confermo che sono casi reali"],
           ["errori", "No, probabilmente sono errori"],
           ["controllare", "Voglio controllarli prima del calcolo"],
           ["ignoto", "Non lo so: sospendi la decisione"]]
        )
      : "";
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
    const nomiQuantitativi = new Set(quantitativeIndipendenti.map(colonna => colonna.nome));
    const altreIndipendentiStandard = indipendentiStandard.filter(
      profilo => !nomiQuantitativi.has(profilo.nome)
    );
    const mistoConQuantitative = quantitativeIndipendenti.length >= 2 &&
      altreIndipendentiStandard.length > 0;
    if (mistoConQuantitative) domande.push(domandaAdattiva(
      "gestioneQuantitativeMiste",
      "Come vuoi confrontare le quantità numeriche insieme alle altre caratteristiche?",
      "Puoi usare Gower classica, che confronta ogni quantità separatamente con "
        + "scarti normalizzati, oppure un blocco numerico unico con una misura "
        + "scelta da te, da aggregare al blocco delle altre caratteristiche. "
        + "In entrambi i casi il risultato è una sola matrice.",
      [
        ["gower", "Gower su tutte: ogni quantità dà un contributo separato"],
        ["separato", "Blocco numerico distinto: scelgo come confrontare insieme le quantità"]
      ]
    ));
    const separaQuantitative = mistoConQuantitative &&
      valoreRisposta("gestioneQuantitativeMiste") === "separato";
    const percorsoNumerico = separaQuantitative ||
      (indipendentiStandard.length > 0 && indipendentiStandard.every(profilo => {
      const colonna = risultato.colonne.find(elemento => elemento.nome === profilo.nome);
      return interpretazione.colonne[profilo.nome].ruolo === "quantita"
        && ["numerica", "numerica_costante"].includes(colonna?.tipo);
    }));
    if (percorsoNumerico) {
      const quantitativeConMancanti = quantitativeIndipendenti.filter(
        colonna => colonna.mancanti > 0
      );
      if (quantitativeConMancanti.length) {
        domande.push(domandeMancantiNumerici(quantitativeConMancanti));
      }
      domande.push(domandaAdattiva(
        "confrontoQuantitativo", "Quale differenza tra le righe vuoi misurare?",
        "Scegli prima lo scopo, poi conferma la misura proposta nel piano. Per confrontare direzione, forma o ranghi, crea nella fase precedente un gruppo «Misurazioni dello stesso profilo».",
        [["assoluto", "Quanto differiscono i valori delle caratteristiche"], ["abbondanza", "Quanto differiscono le quantità complessive (Bray–Curtis)"], ["frequenze", "Quanto differiscono le componenti, dando rilievo a quelle piccole (χ²)"], ["relativo", "Quanto differiscono i valori in proporzione alle loro grandezze (Canberra)"], ["ignoto", "Non so ancora: mostrami una proposta da confermare"]]
      ));

      const confronto = valoreRisposta("confrontoQuantitativo");
      if (confronto === "ignoto") domande.push(notaAutomatica(
        "Proposta da confermare",
        "I dati forniscono indizi per una proposta, non determinano il significato della dissimilarità. La misura dovrà essere confermata nell’editor del piano."
      ));
      if (confronto === "assoluto") {
        if (quantitativeIndipendenti.length >= 2) domande.push(domandaAdattiva(
          "dipendenzaCoordinate", "Vuoi considerare anche il modo in cui queste caratteristiche variano insieme?",
          "Il sito ha già analizzato le correlazioni. Rispondere sì significa valutare Mahalanobis, se la covarianza è utilizzabile; rispondere no significa confrontare gli scarti senza correggere le dipendenze.",
          [["ignoto", "Non lo so: usa la scelta guidata"], ["no", "No, confronta le differenze tra le caratteristiche"], ["si", "Sì, considera le relazioni statistiche"]],
          "ignoto"
        ));
        domande.push(notaAutomatica(
          "Proposta del sito (non ancora approvata)",
          "Il sito propone una misura sulla base di ciò che hai dichiarato. Potrai approvarla o sostituirla nel piano. La distribuzione dei dati, da sola, non rende una formula obbligatoria."
        ));
        if (valoreRisposta("dipendenzaCoordinate") !== "si") domande.push(domandaAdattiva(
          "aggregazioneScarti", "Quali differenze tra due righe ti interessano di più?",
          "Scegli la sensibilità agli scarti oppure chiedi una proposta che dovrai confermare nel piano.",
          [["automatico", "Mostrami una proposta da valutare e approvare"], ["lineare", "Conta la somma delle differenze"], ["quadratica", "Dai più rilievo alle differenze grandi"], ["massimo", "Conta soprattutto la differenza più grande"], ["minkowski", "Voglio regolare io la sensibilità (avanzato)"]],
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
    } else if (quantitativeIndipendenti.length >= 1 && indipendentiStandard.some(profilo =>
      interpretazione.colonne[profilo.nome]?.ruolo !== "quantita") &&
      (!mistoConQuantitative || valoreRisposta("gestioneQuantitativeMiste") === "gower")) {
      domande.push(notaAutomatica(
        "Caratteristiche quantitative nel percorso misto",
        "Le colonne numeriche indipendenti sono analizzate insieme, ma la misura finale per le caratteristiche indipendenti di tipo diverso resta Gower: ogni quantità contribuisce con uno scarto normalizzato. Non viene applicata una distanza euclidea separata."
      ));
      domande.push(domandaAdattiva(
        "tipoGowerNumeriche", "Come vuoi normalizzare le differenze tra le quantità all'interno di Gower?",
        "Per impostazione predefinita si usa il massimo scarto osservato. Se scegli la variante robusta, devi indicare quali righe NON usare per stimare la scala di ogni colonna quantitativa: restano comunque presenti nella matrice finale.",
        [["classica", "Usa il massimo scarto osservato (predefinito)"], ["robusta", "Scala robusta: scelgo quali osservazioni sono anomale"]],
        "classica"
      ));
    }
    const profiliGower = separaQuantitative
      ? altreIndipendentiStandard : indipendentiStandard;
    if (profiliGower.length && (!percorsoNumerico || separaQuantitative)) {
      domande.push(domandeConfigurazioneGower(profiliGower));
    }
    profiliInclusi.filter(profilo =>
      !interpretazione.assegnazioni[profilo.nome] &&
      interpretazione.colonne[profilo.nome]?.ruolo === "insieme"
    ).forEach(profilo => {
      const nome = profilo.nome;
      const conf = interpretazione.configurazioniInsiemi?.[nome] || {};
      domande.push('<div class="question-item"><strong>Insiemi nella colonna “' +
        escapeHtml(nome) + '”</strong><p>Ogni cella contiene più etichette, ' +
        'senza ordine: esempio rosso|blu. Usa [] per un insieme vuoto osservato. ' +
        'Una cella realmente vuota, NA o ?, invece, indica un dato mancante. ' +
        'Gli spazi esterni a ciascuna etichetta sono ignorati.</p>' +
        '<label>Confermi che ogni cella rappresenta un insieme?' +
        '<select class="set-setting" data-set-column="' + escapeHtml(nome) + '" data-set-key="conferma">' +
        '<option value="">Scegli una risposta</option>' +
        '<option value="si"' + (conf.conferma === "si" ? " selected" : "") + '>Sì, sono insiemi</option>' +
        '<option value="no"' + (conf.conferma === "no" ? " selected" : "") + '>No, devo cambiare il ruolo della colonna</option>' +
        '</select></label>' +
        '<label>Quale separatore distingue le etichette?' +
        '<select class="set-setting" data-set-column="' + escapeHtml(nome) + '" data-set-key="separatore">' +
        '<option value="">Scegli un separatore</option>' +
        [["|", "Barra verticale |"], [";", "Punto e virgola ;"], [",", "Virgola , (celle CSV tra virgolette)"]].map(([v, t]) =>
          '<option value="' + escapeHtml(v) + '"' + (conf.separatore === v ? " selected" : "") + '>' + escapeHtml(t) + '</option>'
        ).join("") +
        '</select></label>' +
        '<label>Le maiuscole distinguono due etichette?' +
        '<select class="set-setting" data-set-column="' + escapeHtml(nome) + '" data-set-key="maiuscole">' +
        '<option value="">Scegli una risposta</option>' +
        '<option value="distingui"' + (conf.maiuscole === "distingui" ? " selected" : "") + '>Sì: Roma e roma sono diverse</option>' +
        '<option value="ignora"' + (conf.maiuscole === "ignora" ? " selected" : "") + '>No: Roma e roma sono uguali</option>' +
        '</select></label>' +
        '<label>Se un’etichetta si ripete, conta una volta sola?' +
        '<select class="set-setting" data-set-column="' + escapeHtml(nome) + '" data-set-key="ripetizioni">' +
        '<option value="">Scegli una risposta</option>' +
        '<option value="deduplica"' + (conf.ripetizioni === "deduplica" ? " selected" : "") + '>Sì, ripetizioni ignorate: è un insieme</option>' +
        '<option value="no"' + (conf.ripetizioni === "no" ? " selected" : "") + '>No, contano le ripetizioni: questa struttura non è adatta</option>' +
        '</select></label>' +
        '<label>Come confrontare gli insiemi?' +
        '<select class="set-setting" data-set-column="' + escapeHtml(nome) + '" data-set-key="misura">' +
        '<option value="">Scegli una misura</option>' +
        '<option value="jaccard"' + (conf.misura === "jaccard" ? " selected" : "") + '>Jaccard: quota di etichette non condivise sull’unione</option>' +
        '<option value="dice"' + (conf.misura === "dice" ? " selected" : "") + '>Dice: doppio peso alle etichette condivise</option>' +
        '</select></label><p>Per due insiemi entrambi vuoti e osservati ' +
        'entrambe le misure valgono zero. L’assenza di informazione non vale zero.</p></div>');
    });
    profiliInclusi.filter(profilo =>
      !interpretazione.assegnazioni[profilo.nome] &&
      interpretazione.colonne[profilo.nome]?.ruolo === "ciclica"
    ).forEach(profilo => {
      const nome = profilo.nome;
      const conf = interpretazione.configurazioniCicliche?.[nome] || {};
      domande.push('<div class="question-item"><strong>Ciclo della colonna “' +
        escapeHtml(nome) + '”</strong><p>Un valore descrive una posizione ' +
        'su un ciclo, come un’ora nel giorno o una direzione. ' +
        'Inserisci il periodo positivo P e verifica che tutti i valori siano ' +
        'nell’intervallo [0,P): 0 e P rappresentano lo stesso punto, ' +
        'ma i valori P non vengono corretti automaticamente.</p>' +
        '<label>Qual è il periodo completo P?' +
        '<input type="text" inputmode="decimal" class="cycle-period-setting" data-cycle-column="' +
        escapeHtml(nome) + '" value="' + escapeHtml(conf.periodo ?? "") +
        '" placeholder="es. 24 o 360"></label>' +
        '<label>In quali unità è espresso il periodo?' +
        '<select class="cycle-unit-setting" data-cycle-column="' + escapeHtml(nome) + '">' +
        '<option value="">Scegli un’unità</option>' +
        [["ore", "Ore"], ["giorni", "Giorni"], ["gradi", "Gradi"], ["radianti", "Radianti"], ["altre", "Altre unità della colonna"]].map(([v,t]) =>
          '<option value="' + v + '"' + (conf.unita === v ? " selected" : "") + '>' + t + '</option>'
        ).join("") + '</select></label><p>Il sito usa il percorso più corto sul ciclo: ' +
        '(2/P) × min(|u−v|, P−|u−v|), con valori in [0,1]. ' +
        'Il riscalamento preliminare non viene applicato a questa colonna.</p></div>');
    });
    profiliInclusi.filter(profilo =>
      !interpretazione.assegnazioni[profilo.nome] &&
      interpretazione.colonne[profilo.nome]?.ruolo === "testo"
    ).forEach(profilo => {
      const scelta = interpretazione.misureTestualiPerColonna?.[profilo.nome] || "";
      domande.push('<div class="question-item"><label><strong>Come confrontare i testi nella colonna “' +
        escapeHtml(profilo.nome) + '”?</strong><select class="text-measure-setting" ' +
        'data-text-measure-column="' + escapeHtml(profilo.nome) + '">' +
        '<option value=""' + (!scelta ? " selected" : "") +
        '>Scegli che tipo di differenza conta per questi testi</option>' +
        '<option value="esatta"' + (scelta === "esatta" ? " selected" : "") +
        '>Coincidenza delle etichette: uguale o diverso (0/1)</option>' +
        '<option value="levenshtein"' + (scelta === "levenshtein" ? " selected" : "") +
        '>Levenshtein: consenti inserimenti, cancellazioni e sostituzioni</option>' +
        '<option value="hamming"' + (scelta === "hamming" ? " selected" : "") +
        '>Hamming: conta le posizioni diverse nelle sequenze allineate</option>' +
        '<option value="damerau_levenshtein"' + (scelta === "damerau_levenshtein" ? " selected" : "") +
        '>Damerau–Levenshtein: consenti anche lo scambio di caratteri vicini</option>' +
        '</select></label><p>Se contano solo le etichette, scegli coincidenza esatta ' +
        '(dopo la rimozione degli spazi esterni). Se ogni posizione ha lo stesso ' +
        'significato, scegli Hamming. Se sono ammesse aggiunte o cancellazioni, ' +
        'scegli Levenshtein; Damerau considera anche caratteri adiacenti scambiati. ' +
        'Hamming richiede che tutte le sequenze confrontate abbiano ' +
        'la stessa lunghezza. Levenshtein e Damerau–Levenshtein ammettono lunghezze diverse. ' +
        'La versione CSV di Damerau–Levenshtein usa la distanza completa con trasposizioni ' +
        'adiacenti e la divide per la lunghezza maggiore per ottenere valori in [0,1].</p></div>');
    });
    profiliInclusi.filter(profilo => {
      const ruolo = interpretazione.colonne[profilo.nome]?.ruolo;
      const colonna = risultato.colonne.find(elemento => elemento.nome === profilo.nome);
      return !interpretazione.assegnazioni[profilo.nome]
        && !ruoliStandard.has(ruolo)
        && ["testo", "identificativo", "insieme", "ciclica"].includes(ruolo)
        && colonna?.mancanti > 0;
    }).forEach(profilo => {
      if (!interpretazione.mancantiSpecializzatiPerColonna) {
        interpretazione.mancantiSpecializzatiPerColonna = {};
      }
      const valore = interpretazione.mancantiSpecializzatiPerColonna[profilo.nome] || "";
      const alternativa = ruolo === "insieme"
        ? `<option value="insieme_vuoto"${valore === "insieme_vuoto" ? " selected" : ""}>Confermo che ogni vuoto è un insieme vuoto osservato</option>`
        : ruolo === "ciclica" ? "" :
          `<option value="stringa_vuota"${valore === "stringa_vuota" ? " selected" : ""}>Confermo che significa un testo di lunghezza zero</option>`;
      domande.push(`<div class="question-item">
        <label><strong>Nella colonna “${escapeHtml(profilo.nome)}”, che cosa significa una casella mancante?</strong>
          <select class="specialized-missing-setting" data-specialized-missing-column="${escapeHtml(profilo.nome)}">
            <option value="">Scegli una risposta</option>
            <option value="escludi_percorso"${valore === "escludi_percorso" ? " selected" : ""}>Non usare questa colonna per le coppie coinvolte</option>
            ${alternativa}
          </select>
        </label>
        <p>Non attribuiamo automaticamente dissimilarità zero a dati mancanti. ${ruolo === "insieme" ? "Puoi usare [] nelle celle del CSV per un insieme vuoto realmente osservato." : ""}</p>
      </div>`);
    });
    interpretazione.gruppi.forEach(gruppo => {
      const membri = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa && interpretazione.assegnazioni[profilo.nome] === gruppo.id);
      const tipi = membri.map(profilo => risultato.colonne.find(colonna => colonna.nome === profilo.nome)?.tipo);
      const valido = membri.length >= 2 && membri.every((profilo, indice) =>
        (["numerica", "numerica_costante"].includes(tipi[indice]) ||
          (["distribuzione", "tempo_coppie"].includes(gruppo.tipo) && tipi[indice] === "binaria")) &&
          interpretazione.colonne[profilo.nome]?.ruolo === "quantita");
      if (gruppo.tipo === "vettore_binario") {
        const binarie = membri.length >= 2 && membri.every((profilo, indice) =>
          ["binaria", "non_numerica", "numerica_costante"].includes(tipi[indice]) &&
          ["binaria", "presenza"].includes(interpretazione.colonne[profilo.nome]?.ruolo));
        if (!binarie) return;
        domande.push(domandaAdattiva(
          `misuraBinaria-${gruppo.id}`,
          `Nel gruppo “${escapeHtml(gruppo.nome)}”, come confrontiamo le presenze e le assenze?`,
          "Le colonne sono confrontate insieme come vettori 0/1, senza usare Gower "
          + "sulle stesse colonne. Rogers–Tanimoto raddoppia i disaccordi; Dice "
          + "dà più peso alle presenze condivise. Jaccard considera uguali due "
          + "vettori di assenze osservate; Dice non è definita quando il "
          + "denominatore è nullo. Un dato non osservato non è un'assenza.",
          [
            ["hamming", "Hamming binaria: quota di disaccordi, comprese le assenze comuni"],
            ["rogers_tanimoto", "Rogers–Tanimoto: penalizza maggiormente i disaccordi"],
            ["jaccard", "Jaccard: ignora le assenze comuni; due vettori nulli valgono 0"],
            ["dice", "Dice: pesa maggiormente le presenze comuni; vietati i vettori nulli"]
          ]
        ));
        if (membri.some(profilo =>
          (risultato.colonne.find(colonna => colonna.nome === profilo.nome)?.mancanti || 0) > 0)) {
          domande.push(domandaAdattiva(
            `mancanti-gruppo-${gruppo.id}`,
            `Nel gruppo “${escapeHtml(gruppo.nome)}”, come trattiamo i valori mancanti?`,
            "Se scegli le coordinate osservate in entrambe le righe, una doppia "
            + "assenza realmente osservata conta come informazione, mentre "
            + "un valore mancante viene ignorato. Senza coordinate comuni "
            + "il contributo non è disponibile; Dice è indefinita quando "
            + "rimangono soltanto assenze comuni. Altri blocchi possono "
            + "ancora confrontare la stessa coppia di righe.",
            [["escludi_percorso", "Ignora il blocco se una delle due righe contiene vuoti"],
             ["pairwise", "Confronta soltanto le caratteristiche osservate in entrambe le righe"],
             ["zero", "Confermo che ogni vuoto rappresenta davvero assenza (zero)"]]
          ));
        }
        return;
      }

      if (gruppo.tipo === "tempo_coppie") {
        const corrette = membri.length >= 4 && membri.length % 2 === 0 &&
          membri.every((profilo, i) =>
            ["numerica", "numerica_costante", "binaria"].includes(tipi[i]) &&
            interpretazione.colonne[profilo.nome]?.ruolo === "quantita"
          );
        if (!corrette) {
          domande.push(notaAutomatica("Serie temporale per riga non configurabile",
            "Assegna almeno quattro colonne numeriche al gruppo, "
            + "con ruolo «quantità numerica» anche per i tempi 0/1."));
          return;
        }
        const id = gruppo.id;
        const impostato = chiave => interpretazione[chiave]?.[id] ?? "";
        const campo = (chiave, titolo, esempio) =>
          '<label>' + escapeHtml(titolo) + '<input type="text" ' +
          'class="temporal-parameter" data-temporal-key="' + chiave +
          '" data-group-id="' + escapeHtml(id) + '" value="' +
          escapeHtml(impostato(chiave)) + '" placeholder="' +
          escapeHtml(esempio) + '"></label>';
        const menu = (chiave, titolo, opzioni) =>
          '<label>' + escapeHtml(titolo) +
          '<select class="temporal-option" data-temporal-key="' + chiave +
          '" data-group-id="' + escapeHtml(id) + '">' +
          opzioni.map(([value, label]) =>
            '<option value="' + value + '"' +
            (impostato(chiave) === value ? " selected" : "") + '>' +
            escapeHtml(label) + '</option>').join("") + '</select></label>';
        const nomi = membri.map(profilo => profilo.nome);
        const esempio = [];
        for (let i = 0; i < nomi.length; i += 2) {
          esempio.push(nomi[i] + ":" + nomi[i + 1]);
        }
        domande.push('<div class="question-item"><strong>Serie a tempi per riga — ' +
          escapeHtml(gruppo.nome) + '</strong><p>Ogni riga rappresenta una serie ' +
          'di coppie (tempo, valore) con timestamp propri, non una griglia comune. ' +
          'Conferma l’ordine delle coppie e assegna ciascuna colonna una volta sola. ' +
          'I timestamp di ciascuna riga devono essere strettamente crescenti. ' +
          'Non vengono ricampionate le serie.</p>' +
          '<p>Colonne disponibili: ' + nomi.map(escapeHtml).join(", ") + '</p>' +
          campo("coppieTemporaliGruppi", "Coppie cronologiche tempo:valore separate da ;",
            esempio.join("; ")) +
          menu("unitaTemporaleGruppi", "Unità fisica di tutti i timestamp",
            [["", "Scegli unità"], ["secondi", "Secondi"], ["minuti", "Minuti"],
             ["ore", "Ore"], ["giorni", "Giorni"], ["altre", "Altre unità"]]) +
          '</div>');
        const metodo = impostato("metodiAllineamentoTemporaleGruppi");
        domande.push('<div class="question-item">' +
          menu("metodiAllineamentoTemporaleGruppi", "Come confrontare le serie?",
            [["", "Scegli la misura"], ["dtw", "DTW a costo medio minimo esatto"],
             ["lcss", "LCSS su sottosequenze con tolleranze"]]) +
          '<p>Il punto-a-punto e le pendenze richiedono istanti comparabili; ' +
          'in questo formato sono disponibili DTW e LCSS.</p></div>');
        if (metodo === "dtw") {
          domande.push('<div class="question-item"><strong>Scelte DTW</strong>' +
            menu("costiDTWGruppi", "Costo locale",
              [["", "Scegli"], ["assoluto", "Scarto assoluto"],
               ["quadratico", "Scarto quadratico"]]) +
            campo("finestreDTWGruppi", "Finestra |indice i−indice j|",
              "vuoto = nessun vincolo") +
            menu("penalizzazioniDTWGruppi",
              "Vuoi penalizzare lo sfasamento fisico tra i timestamp?",
              [["", "Scegli"], ["si", "Sì, aggiungi λ·|t−s|/τ"],
               ["no", "No, confronta solo valori e ordine degli eventi"]]) +
            (impostato("penalizzazioniDTWGruppi") === "si"
              ? campo("pesiRitardoDTWGruppi", "Peso della penalità λ > 0", "es. 1") +
                campo("scaleRitardoDTWGruppi", "Scala temporale τ > 0", "es. 2")
              : "") +
            '<p>La finestra è simmetrica e non viene allargata automaticamente. ' +
            'Il sito verifica che esistano cammini per tutte le coppie.</p></div>');
        } else if (metodo === "lcss") {
          domande.push('<div class="question-item"><strong>Scelte LCSS</strong>' +
            campo("tolleranzeValoreLCSSGruppi", "Tolleranza valori εv ≥ 0", "es. 0.5") +
            campo("tolleranzeTempoLCSSGruppi", "Tolleranza tempi εt ≥ 0", "es. 2") +
            '<p>Due eventi possono coincidere solo entro entrambe le tolleranze; ' +
            'la dissimilarità è 1−LCSS/min(lunghezze).</p></div>');
        }
        if (membri.some(profilo =>
          (risultato.colonne.find(c => c.nome === profilo.nome)?.mancanti || 0) > 0
        )) {
          domande.push(domandaAdattiva(
            'mancanti-gruppo-' + id,
            'Come trattare le coppie con celle vuote nel gruppo “' +
              escapeHtml(gruppo.nome) + '”?',
            "Solo una coppia completamente vuota può essere ignorata. " +
            "Un tempo senza valore (o viceversa) resta un errore; " +
            "non vengono creati campioni fittizi.",
            [["salta_slot", "Ometti le coppie con entrambi i campi vuoti"],
             ["escludi_percorso", "Escludi l’intera serie della riga se manca un campo"]]
          ));
        }
        const riscalamenti = riscalamentoConfermato && membri.some(profilo => {
          const c = risultato.colonne.find(col => col.nome === profilo.nome);
          return c?.metodo && !["nessuno", "costante"].includes(c.metodo);
        });
        if (riscalamenti) {
          const conferma = interpretazione.confermeValoriOriginaliGruppi?.[id] || "";
          domande.push('<div class="question-item"><label><strong>' +
            'Confermi che tempi e valori di questo gruppo restino originali?</strong>' +
            '<p>Il riscalamento preliminare non verrà applicato al confronto temporale.</p>' +
            '<select class="group-preprocessing-confirmation" data-group-id="' +
            escapeHtml(id) + '" data-kind="originali"><option value="">Conferma necessaria</option>' +
            '<option value="si"' + (conferma === "si" ? " selected" : "") +
            '>Confermo i valori originali</option></select></label></div>');
        }
        return;
      }
      if (!valido) return;
      if (gruppo.tipo === "ripetute") domande.push(domandaAdattiva(
        `somiglianza-${gruppo.id}`, `Nel gruppo “${escapeHtml(gruppo.nome)}”, quando due righe devono essere considerate simili?`,
        "Prima decidi la proprietà da preservare. Coseno e corda ignorano un fattore di scala comune; Pearson ignora anche una traslazione comune; " +
        "Spearman e Kendall usano gli ordini, non gli scarti numerici. Profili nulli e alcuni profili costanti possono rendere il confronto non definito.",
        [
          ["valori_vicini", "Conta quanto differiscono i singoli valori (Manhattan, Euclidea, Chebyshev…)"],
          ["proporzioni", "Conta solo la direzione del profilo (coseno)"],
          ["corda", "Conta la distanza tra profili portati a lunghezza unitaria (corda)"],
          ["andamento", "Conta la forma rispetto alla media, non il livello assoluto (Pearson)"],
          ["ordine", "Conta la graduatoria delle caratteristiche, anche con pari merito (Spearman)"],
          ["ordine_coppie", "Conta se le coppie di caratteristiche mantengono lo stesso ordine (Kendall τ-b)"],
          ["ignoto", "Non so quale proprietà voglio confrontare: guida necessaria"]
        ]
      ));
      if (gruppo.tipo === "tempo") {
        const ordine = interpretazione.ordiniTemporaliGruppi?.[gruppo.id] || "";
        const campionamento = interpretazione.campionamentiTemporaliGruppi?.[gruppo.id] || "";
        domande.push('<div class="question-item"><strong>Conferma la successione temporale del gruppo “' +
          escapeHtml(gruppo.nome) + '”</strong>' +
          '<p>Le colonne devono essere elencate dalla misurazione più antica alla più recente. ' +
          'Il sito non presume che l’ordine del file sia quello cronologico.</p>' +
          '<p>Colonne del gruppo: ' + membri.map(profilo => escapeHtml(profilo.nome)).join(', ') + '</p>' +
          '<label>Ordine temporale (separa i nomi con ;)' +
          '<input type="text" class="temporal-order-input" data-group-id="' + escapeHtml(gruppo.id) +
          '" value="' + escapeHtml(ordine) + '" placeholder="' +
          escapeHtml(membri.map(profilo => profilo.nome).join('; ')) +
          '"></label>' +
          '<button type="button" class="secondary-action temporal-order-from-csv" data-group-id="' +
          escapeHtml(gruppo.id) + '">Confermo che l’ordine nel file è cronologico</button>' +
          '<label>Gli intervalli di tempo tra queste misurazioni sono uguali?' +
          '<select class="temporal-spacing-select" data-group-id="' + escapeHtml(gruppo.id) + '">' +
          '<option value=""' + (!campionamento ? ' selected' : '') + '>Devo ancora confermarlo</option>' +
          '<option value="regolare"' + (campionamento === 'regolare' ? ' selected' : '') +
          '>Sì, le misurazioni sono equidistanti nel tempo</option>' +
          '<option value="irregolare"' + (campionamento === 'irregolare' ? ' selected' : '') +
          '>No, gli intervalli sono differenti</option>' +
          '</select></label>' +
          '<p>Le colonne rappresentano una griglia comune a tutte le righe. ' +
          'Per tempi irregolari servono i timestamp effettivi. ' +
          'Il sito non effettua ricampionamenti impliciti e non accetta ' +
          'timestamp differenti da riga a riga in questo formato.</p></div>');
        domande.push(domandaAdattiva(
          `ritardo-${gruppo.id}`, `Nel gruppo “${escapeHtml(gruppo.nome)}”, un andamento simile può avvenire con un piccolo ritardo?`,
          "Per esempio, lo stesso picco può comparire in momenti leggermente diversi nelle due righe.",
          [["si", "Sì, il ritardo non deve renderle diverse"], ["no", "No, gli stessi eventi devono avvenire negli stessi momenti"], ["ignoto", "Non lo so"]]
        ));
        const id = gruppo.id;
        const ritardo = valoreRisposta(`ritardo-${id}`);
        const misuraTempo = interpretazione.misureTemporaliGruppi?.[id] || "";
        const allineamento = interpretazione.metodiAllineamentoTemporaleGruppi?.[id] || "";
        const penale = interpretazione.penalizzazioniDTWGruppi?.[id] || "no";
        const valoreTempo = (chiave, fallback = "") => escapeHtml(
          interpretazione[chiave]?.[id] ?? fallback
        );
        const selezioneTempo = (chiave, scelte, scelto) =>
          '<select class="temporal-option" data-temporal-key="' + chiave +
          '" data-group-id="' + escapeHtml(id) + '">' +
          scelte.map(([v, label]) =>
            '<option value="' + v + '"' + (scelto === v ? ' selected' : '') +
            '>' + escapeHtml(label) + '</option>'
          ).join('') + '</select>';
        const inputTempo = (chiave, etichetta, suggerimento) =>
          '<label>' + escapeHtml(etichetta) + '<input type="text" class="temporal-parameter" ' +
          'data-temporal-key="' + chiave + '" data-group-id="' +
          escapeHtml(id) + '" value="' + valoreTempo(chiave) +
          '" placeholder="' + escapeHtml(suggerimento) + '"></label>';
        domande.push('<div class="question-item"><strong>Tempi fisici del gruppo “' +
          escapeHtml(gruppo.nome) + '”</strong><p>Se noti, indica i timestamp numerici ' +
          'nell’ordine cronologico confermato, separati da ;. ' +
          'Tutti i casi devono riferirsi agli stessi istanti. Per dati irregolari ' +
          'e per le pendenze i timestamp sono obbligatori. ' +
          'Per dati regolari senza tempi il confronto non penalizzato ' +
          'usa gli indici 0, 1, 2, ... come passi, non come tempi reali.</p>' +
          inputTempo("tempiTemporaliGruppi",
            "Timestamp, uno per colonna", "es. 0; 1; 3; 8") +
          '<label>Unità dei timestamp, se indicati' +
          selezioneTempo("unitaTemporaleGruppi",
            [["", "Scegli le unità"], ["secondi", "Secondi"], ["minuti", "Minuti"],
             ["ore", "Ore"], ["giorni", "Giorni"], ["altre", "Altre unità coerenti"]],
            interpretazione.unitaTemporaleGruppi?.[id] || "") + '</label></div>');
        if (ritardo === "no") {
          domande.push('<div class="question-item"><label><strong>Come confrontare ' +
            'le variazioni senza consentire ritardi?</strong>' +
            selezioneTempo("misureTemporaliGruppi",
              [["", "Scegli che cosa conta nella sincronia"],
               ["punto", "Livello agli stessi istanti: scarti punto per punto (poi scegli la misura)"],
               ["pendenze", "Velocità di cambiamento: confronta le pendenze (STS)"]],
              misuraTempo) + '</label><p>Le pendenze richiedono i timestamp ' +
            'reali e non distinguono serie che differiscono soltanto ' +
            'per una costante additiva.</p></div>');
        }
        if (ritardo === "si") {
          domande.push('<div class="question-item"><label><strong>Quale ' +
            'allineamento vuoi usare?</strong>' +
            selezioneTempo("metodiAllineamentoTemporaleGruppi",
              [["", "Scegli come tollerare ritardi ed eventi non allineati"],
               ["dtw", "DTW: riallinea gli eventi, minimizzando il costo medio"],
               ["lcss", "LCSS: trova una sottosequenza che coincide entro tolleranze"]],
              allineamento) + '</label></div>');
          if (allineamento === "dtw") {
            domande.push('<div class="question-item"><strong>Parametri DTW</strong>' +
              '<label>Costo locale tra due valori' +
              selezioneTempo("costiDTWGruppi",
                [["assoluto", "Scarto assoluto |u−v|"],
                 ["quadratico", "Scarto quadratico |u−v|²"]],
                interpretazione.costiDTWGruppi?.[id] || "assoluto") + '</label>' +
              inputTempo("finestreDTWGruppi",
                "Finestra massima |indice i−indice j| (vuoto = nessun vincolo)",
                "es. 1") +
              '<p>La finestra è simmetrica e deve permettere almeno un cammino. ' +
              'Un valore 0 consente solo la diagonale.</p>' +
              '<label>Penalizzare anche lo sfasamento nei tempi reali?' +
              selezioneTempo("penalizzazioniDTWGruppi",
                [["no", "No: costo soltanto sui valori"],
                 ["si", "Sì: aggiungo λ·|t−s|/τ"]],
                penale) + '</label>' +
              (penale === "si"
                ? inputTempo("pesiRitardoDTWGruppi",
                    "Peso dello sfasamento λ (≥0; >0 se irregolare)", "es. 2") +
                  inputTempo("scaleRitardoDTWGruppi",
                    "Scala temporale τ (>0; stessa unità dei timestamp)", "es. 1")
                : "") +
              '<p>Se i tempi sono irregolari, la penalità è necessaria: ' +
              'un allineamento per soli indici ignorerebbe le durate effettive. ' +
              'Nessun peso o scala viene impostato automaticamente.</p></div>');
          } else if (allineamento === "lcss") {
            domande.push('<div class="question-item"><strong>Parametri LCSS</strong>' +
              inputTempo("tolleranzeValoreLCSSGruppi",
                "Tolleranza sui valori εv (≥0)", "es. 0.5") +
              inputTempo("tolleranzeTempoLCSSGruppi",
                "Tolleranza sugli istanti εt (≥0)", "es. 2") +
              '<p>Due osservazioni possono coincidere soltanto se ' +
              'rientrano in entrambe le tolleranze. ' +
              'Con tempi regolari non specificati, εt è misurata in passi; ' +
              'in caso contrario, nell’unità dichiarata.</p></div>');
          }
        }
      }
      if (gruppo.tipo === "distribuzione") {
        domande.push(domandaAdattiva(
          `naturaDistribuzione-${gruppo.id}`,
          `Che cosa rappresentano i valori del gruppo “${escapeHtml(gruppo.nome)}”?`,
          "Ogni colonna rappresenta la stessa categoria o intervallo (bin) " +
          "in tutte le righe. Sono ammessi zeri reali; non sono ammessi valori negativi " +
          "o righe con totale zero. A differenza di Aitchison, le due misure " +
          "non richiedono componenti strettamente positive.",
          [
            ["probabilita", "Probabilità: ogni riga deve già sommare a 1"],
            ["masse", "Conteggi, percentuali o frequenze: normalizza ogni riga per il suo totale"]
          ]
        ));
        domande.push(domandaAdattiva(
          `misuraDistribuzione-${gruppo.id}`,
          `Come confrontare le distribuzioni del gruppo “${escapeHtml(gruppo.nome)}”?`,
          "Hellinger confronta le radici quadrate delle probabilità. " +
          "Jensen–Shannon confronta le informazioni contenute nelle due " +
          "distribuzioni e usa la radice della divergenza normalizzata. " +
          "Entrambe sono distanze tra 0 e 1 e ammettono probabilità nulle.",
          [
            ["hellinger", "Hellinger: scarti fra radici delle probabilità"],
            ["jensen_shannon", "Jensen–Shannon: informazione distribuita diversamente"]
          ]
        ));
      }
      if (gruppo.tipo === "parti") domande.push(domandaAdattiva(
        `totale-${gruppo.id}`, `Le colonne del gruppo “${escapeHtml(gruppo.nome)}” sono parti di un unico totale?`,
        "Per esempio, percentuali, quote o quantità la cui somma ha un significato preciso.",
        [["si", "Sì, conta la composizione del totale"], ["no", "No, sono quantità indipendenti"], ["ignoto", "Non lo so"]]
      ));
      // Ogni gruppo quantitativo confrontato per coordinate puo' usare
      // una misura locale differente. La semantica viene confermata prima.
      const misuraPerCoordinate = gruppo.tipo === "coordinate"
        || (gruppo.tipo === "ripetute" && valoreRisposta(`somiglianza-${gruppo.id}`) === "valori_vicini")
        || (gruppo.tipo === "tempo" && valoreRisposta(`ritardo-${gruppo.id}`) === "no" &&
            (interpretazione.misureTemporaliGruppi?.[gruppo.id] || "") === "punto")
        || (gruppo.tipo === "parti" && valoreRisposta(`totale-${gruppo.id}`) === "no");
      const metodiPreliminari = membri.map(profilo =>
        risultato.colonne.find(colonna => colonna.nome === profilo.nome)
      ).filter(colonna => colonna?.metodo && colonna.metodo !== "costante");
      const riscalamentiEffettivi = riscalamentoConfermato &&
        metodiPreliminari.some(colonna => colonna.metodo !== "nessuno");
      const applicaRiscalamento = misuraPerCoordinate && gruppo.tipo !== "tempo";
      const metodiDifferenti = new Set(metodiPreliminari.map(colonna => colonna.metodo)).size > 1;
      if (riscalamentiEffettivi && !applicaRiscalamento && gruppo.tipo !== "altro") {
        const conferma = interpretazione.confermeValoriOriginaliGruppi?.[gruppo.id] || "";
        domande.push('<div class="question-item"><label><strong>Per il gruppo “' +
          escapeHtml(gruppo.nome) + '”, confermi l’uso dei valori originali?</strong>' +
          '<p>I riscalamenti preliminari NON saranno applicati a questo gruppo: ' +
          'potrebbero alterare forma, andamento o significato della composizione.</p>' +
          '<select class="group-preprocessing-confirmation" data-group-id="' +
          escapeHtml(gruppo.id) + '" data-kind="originali">' +
          '<option value=""' + (!conferma ? ' selected' : '') +
          '>Conferma necessaria</option>' +
          '<option value="si"' + (conferma === 'si' ? ' selected' : '') +
          '>Confermo: usa i valori originali per questa misura</option>' +
          '</select></label></div>');
      } else if (riscalamentiEffettivi && applicaRiscalamento && metodiDifferenti) {
        const conferma = interpretazione.confermeRiscalamentiMistiGruppi?.[gruppo.id] || "";
        domande.push('<div class="question-item"><label><strong>Per il gruppo “' +
          escapeHtml(gruppo.nome) + '”, confermi i metodi di riscalamento differenti?</strong>' +
          '<p>Le colonne del gruppo ricevono trasformazioni differenti: ' +
          metodiPreliminari.map(colonna =>
            escapeHtml(colonna.nome) + ': ' + escapeHtml(etichettaMetodo(colonna.metodo))
          ).join('; ') +
          '. La distanza è calcolabile, ma la scelta modifica i pesi relativi delle coordinate.</p>' +
          '<select class="group-preprocessing-confirmation" data-group-id="' +
          escapeHtml(gruppo.id) + '" data-kind="misti">' +
          '<option value=""' + (!conferma ? ' selected' : '') +
          '>Conferma necessaria</option>' +
          '<option value="si"' + (conferma === 'si' ? ' selected' : '') +
          '>Confermo questi diversi riscalamenti</option>' +
          '</select></label></div>');
      }
      if (misuraPerCoordinate) {
        const idMisura = interpretazione.misureGruppi?.[gruppo.id] || "";
        const opzioniGruppo = [
          ["euclidean", "Euclidea: combina gli scarti dando maggior rilievo a quelli grandi"],
          ["manhattan", "Manhattan: somma le differenze assolute"],
          ["chebyshev", "Chebyshev: conta soltanto la differenza più grande"],
          ["minkowski", "Minkowski: scegli quanto pesano le differenze grandi"],
          ["weighted_minkowski", "Minkowski pesata: scegli anche quanto conta ciascuna colonna"],
        ];
        const menuMisure = '<option value=""' + (idMisura === "" ? " selected" : "") +
          '>Scegli una misura per questo gruppo</option>' +
          opzioniGruppo.map(([id, label]) => '<option value="' + id + '"' +
            (id === idMisura ? " selected" : "") + '>' + escapeHtml(label) + '</option>').join("");
        let parametriMisura = "";
        if (["minkowski", "weighted_minkowski"].includes(idMisura)) {
          parametriMisura += '<label>Esponente q (almeno 1)' +
            '<input type="text" class="group-measure-parameter" data-group-id="' +
            escapeHtml(gruppo.id) + '" data-parameter="q" value="' +
            escapeHtml(interpretazione.ordiniGruppi?.[gruppo.id] || "2") +
            '" placeholder="2"></label>';
        }
        if (idMisura === "weighted_minkowski") {
          parametriMisura += '<label>Pesi delle colonne, nell\'ordine: ' +
            membri.map(profilo => escapeHtml(profilo.nome)).join(", ") +
            '<input type="text" class="group-measure-parameter" data-group-id="' +
            escapeHtml(gruppo.id) + '" data-parameter="pesi" value="' +
            escapeHtml(interpretazione.pesiGruppi?.[gruppo.id] || membri.map(() => "1").join("; ")) +
            '" placeholder="es. 1; 2; 0,5"></label>' +
            '<p>Ogni peso deve essere strettamente positivo. Il numero dei pesi deve coincidere con quello delle colonne del gruppo.</p>';
        }
        domande.push('<div class="question-item"><label><strong>Quale regola combina gli scarti nel gruppo “' +
          escapeHtml(gruppo.nome) + '”?</strong><select class="group-measure-setting" data-group-id="' +
          escapeHtml(gruppo.id) + '">' + menuMisure +
          '</select></label><p>Prima hai deciso che cosa rappresenta il gruppo. ' +
          'Ora scegli come riassumere gli scarti: Manhattan li somma linearmente; ' +
          'Euclidea combina i quadrati; Chebyshev considera soltanto il massimo; ' +
          'Minkowski regola l’effetto degli scarti grandi (q ≥ 1); la versione pesata ' +
          'permette importanze interne diverse. La scelta non si applica agli altri blocchi.</p>' +
          parametriMisura + '</div>');
      }

      const colonneGruppo = membri.map(profilo =>
        risultato.colonne.find(colonna => colonna.nome === profilo.nome)
      );
      if (colonneGruppo.some(colonna => colonna?.mancanti > 0)) {
        const opzioni = gruppo.tipo === "distribuzione"
          ? [
              ["escludi_percorso", "Non usare questo gruppo per le righe che hanno valori mancanti"],
              ["zero", "Confermo che ogni vuoto corrisponde esattamente a massa zero"]
            ]
          : gruppo.tipo === "tempo"
          ? [
              ["escludi_percorso", "Non usare questo gruppo per le righe con vuoti"],
              ["interpola_lineare", "Ricostruisci soltanto i vuoti interni con una linea retta"],
              ["zero", "Confermo che i vuoti significano davvero zero"]
            ]
          : [
              ["escludi_percorso", "Non usare questo gruppo per le righe con vuoti"],
              ...(misuraPerCoordinate && gruppo.tipo !== "tempo"
                ? [["pairwise", "Confronta solo le coordinate osservate da entrambe le righe"]]
                : []),
              ["imputa_mediana", "Sostituisci con il valore centrale della colonna"],
              ["imputa_media", "Sostituisci con il valore medio della colonna"],
              ["zero", "Confermo che i vuoti significano davvero zero"]
            ];
        domande.push(domandaAdattiva(
          `mancanti-gruppo-${gruppo.id}`,
          `Nel gruppo “${escapeHtml(gruppo.nome)}”, come trattiamo le caselle vuote?`,
          gruppo.tipo === "tempo"
            ? "L’interpolazione usa soltanto valori osservati prima e dopo il vuoto; non inventa gli estremi della serie."
            : gruppo.tipo === "distribuzione"
              ? "Non si imputano media o mediana nelle distribuzioni. Puoi omettere il blocco per le righe con vuoti, oppure dichiarare che i vuoti sono autentiche frequenze nulle; ogni riga usata deve mantenere massa totale positiva."
            : "La scelta vale soltanto per questo gruppo e viene dichiarata nel risultato. " +
              "Se scegli il confronto pairwise, le distanze di Minkowski sono medie pesate " +
              "degli scarti sulle coordinate comuni, senza sostituire i vuoti.",
          opzioni
        ));
      }
      const contieneZeri = colonneGruppo.some(
        colonna => (colonna?.statistiche?.zeri || 0) > 0
      ) || valoreRisposta(`mancanti-gruppo-${gruppo.id}`) === "zero";
      if (gruppo.tipo === "parti" && contieneZeri && valoreRisposta(`totale-${gruppo.id}`) === "si") {
        domande.push(domandaAdattiva(
          `zeri-aitchison-${gruppo.id}`,
          `Nel gruppo “${escapeHtml(gruppo.nome)}”, che cosa significano gli zeri osservati?`,
          "Aitchison usa logaritmi e non è definita in presenza di zeri. Dopo aver riportato ogni riga a somma 1, il sito usa una piccola proporzione positiva, limitata per lasciare almeno metà della massa alle componenti osservate, e le ridimensiona proporzionalmente.",
          [
            ["sostituisci", "Sono valori sotto soglia: applica la sostituzione dichiarata"],
            ["strutturali", "Sono assenze reali: Aitchison non è adatta"],
            ["ignoto", "Non lo so: non calcolare ancora"]
          ]
        ));
      }
    });
    $("adaptive-questions").innerHTML = domande.join("");
    aggiornaDomandeFocalizzate(true);
    aggiornaFaseNumerica();
  }

  const MARCATORI_CSV_STANDARD = [
    ["na", "NA"], ["n/a", "N/A"], ["null", "NULL"],
    ["?", "?"], ["nan", "NaN"]
  ];

  function disegnaAnteprimaImportazione() {
    const config = importazioneCSV || {};
    const anteprima = anteprimaImportazione || {};
    $("csv-import-stage").hidden = false;
    $("import-separator").value = config.separatore || anteprima.separatore || ",";
    const attivi = new Set(config.marcatoriMancanti || []);
    $("import-marker-options").innerHTML = MARCATORI_CSV_STANDARD.map(([chiave, nome]) =>
      '<label><input class="import-marker-choice" type="checkbox" value="' +
      escapeHtml(chiave) + '"' + (attivi.has(chiave) ? " checked" : "") +
      '> ' + escapeHtml(nome) +
      ' (' + escapeHtml(String(anteprima.conteggiMarcatori?.[chiave] || 0)) +
      ' occorrenze)</label>'
    ).join("");
    if (anteprima.erroreAnteprima) {
      $("import-preview-error").textContent =
        "Con questo separatore il file non può essere letto: " + anteprima.erroreAnteprima;
    } else {
      $("import-preview-error").textContent = "";
    }
    const intestazioni = anteprima.intestazioni || [];
    const righe = anteprima.righe || [];
    const maxColonne = Math.min(20, intestazioni.length);
    $("import-preview-head").innerHTML = '<tr>' + intestazioni.slice(0, maxColonne)
      .map(nome => '<th scope="col">' + escapeHtml(nome) + '</th>').join("") + '</tr>';
    $("import-preview-body").innerHTML = righe.map(riga =>
      '<tr>' + riga.slice(0, maxColonne)
        .map(valore => '<td>' + escapeHtml(valore) + '</td>').join("") + '</tr>'
    ).join("");
    $("import-preview-caption").textContent = anteprima.erroreAnteprima
      ? "Scegli un altro separatore; nessuna colonna è stata ancora interpretata."
      : "Il file “" + nomeFileImportazione + "” contiene " + anteprima.numeroRighe +
        " righe di dati e " + intestazioni.length + " colonne. Anteprima di " +
        righe.length + " righe; i valori sono ancora quelli del CSV originale.";
    $("confirm-csv-import").disabled = !!anteprima.erroreAnteprima;
  }

  async function cambiaSeparatoreImportazione(separatore) {
    if (!testoOriginale || typeof P.anteprimaImportazione !== "function") return;
    if (!importazioneCSV) return;
    importazioneCSV.separatore = separatore;
    const versione = ++versioneAnteprimaImportazione;
    const versioneFile = versioneDati;
    $("import-preview-caption").textContent = "Rilettura dell'anteprima…";
    $("confirm-csv-import").disabled = true;
    try {
      const letta = await P.anteprimaImportazione(testoOriginale, {separatore});
      if (versione !== versioneAnteprimaImportazione || versioneFile !== versioneDati) return;
      anteprimaImportazione = letta;
      disegnaAnteprimaImportazione();
    } catch (errore) {
      if (versione !== versioneAnteprimaImportazione || versioneFile !== versioneDati) return;
      $("import-preview-error").textContent = errore.message;
      $("confirm-csv-import").disabled = true;
    }
  }

  function opzioniImportazioneConfermate() {
    const selezionati = [""]; // Le celle vuote restano sempre mancanti.
    const standard = MARCATORI_CSV_STANDARD.map(([nome]) => nome);
    const custom = $("import-custom-markers").value.split(";")
      .map(x => x.trim().toLocaleLowerCase()).filter(Boolean);
    const attivi = new Set(importazioneCSV?.marcatoriMancanti || []);
    return {
      separatore: $("import-separator").value,
      marcatoriMancanti: [...new Set([
        ...selezionati, ...standard.filter(nome => attivi.has(nome)), ...custom
      ])]
    };
  }

  async function confermaImportazione() {
    if (!testoOriginale || !importazioneCSV || anteprimaImportazione?.erroreAnteprima) return;
    const versione = ++versioneDati;
    ++versionePreparazioneColonne;
    ++versioneAnteprimaImportazione;
    const pulsante = $("confirm-csv-import");
    const testoPulsante = pulsante.textContent;
    pulsante.disabled = true;
    pulsante.textContent = "Analisi delle colonne…";
    nascondiErrore();
    try {
      const config = opzioniImportazioneConfermate();
      const nuovaTabella = await P.preparaTabella(testoOriginale, [], config);
      if (versione !== versioneDati) return;
      importazioneCSV = config;
      interpretazione = {colonne: {}, gruppi: [], assegnazioni: {}, prossimoGruppo: 1};
      faseQuestionario = "semantica";
      riscalamentoConfermato = false;
      $("row-meaning").value = "";
      risultato = nuovaTabella;
      tabellaOriginale = nuovaTabella.originale;
      scelte = tabellaOriginale.intestazioni.map(() => ({tipo: "auto", metodo: "auto"}));
      $("csv-import-stage").hidden = true;
      mostraRisultato(nomeFileImportazione);
    } catch (errore) {
      if (versione !== versioneDati) return;
      $("import-preview-error").textContent = errore.message;
    } finally {
      if (versione === versioneDati) {
        pulsante.disabled = false;
        pulsante.textContent = testoPulsante;
      }
    }
  }

  function modificaImportazione() {
    if (!testoOriginale || !importazioneCSV) return;
    ++versioneDati;
    ++versionePreparazioneColonne;
    ++versioneAnteprimaImportazione;
    nascondiPiano();
    nascondiErrore();
    risultato = null;
    $("csv-output").hidden = true;
    disegnaAnteprimaImportazione();
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
    const versione = ++versioneDati;
    ++versionePreparazioneColonne;
    nascondiPiano();
    nascondiErrore();
    $("csv-output").hidden = true;
    $("csv-import-stage").hidden = true;
    try {
      // La prima lettura identifica le colonne, ma non tipizza i dati.
      // L'analisi definitiva aspetta una conferma esplicita del CSV.
      if (typeof P.anteprimaImportazione === "function") {
        const preview = await P.anteprimaImportazione(testo, {});
        if (versione !== versioneDati) return;
        testoOriginale = testo;
        nomeFileImportazione = nomeFile;
        anteprimaImportazione = preview;
        importazioneCSV = {
          separatore: preview.separatore,
          marcatoriMancanti: ["", "na", "n/a", "null", "?"]
        };
        $("import-custom-markers").value = "";
        disegnaAnteprimaImportazione();
        return;
      }
      // Compatibilità con il motore simulato nei test DOM storici.
      const nuovaTabella = await P.preparaTabella(testo, []);
      if (versione !== versioneDati) return;
      interpretazione = { colonne: {}, gruppi: [], assegnazioni: {}, prossimoGruppo: 1 };
      faseQuestionario = "semantica";
      riscalamentoConfermato = false;
      $("row-meaning").value = "";
      testoOriginale = testo;
      risultato = nuovaTabella;
      tabellaOriginale = nuovaTabella.originale;
      scelte = tabellaOriginale.intestazioni.map(() => ({ tipo: "auto", metodo: "auto" }));
      mostraRisultato(nomeFile);
    } catch (errore) {
      if (versione !== versioneDati) return;
      risultato = null;
      $("csv-output").hidden = true;
      mostraErrore(errore.message);
    }
  }

  async function elaboraFile(file) {
    if (!file) return;
    // La lettura del file può finire dopo un secondo caricamento.
    const versione = ++versioneDati;
    ++versionePreparazioneColonne;
    nascondiPiano();
    $("csv-output").hidden = true;
    $("csv-import-stage").hidden = true;
    if (file.size > 15 * 1024 * 1024) { mostraErrore("Il file supera il limite iniziale di 15 MB."); return; }
    if (!/\.csv$/i.test(file.name) && file.type !== "text/csv" && file.type !== "text/plain") {
      mostraErrore("Seleziona un file CSV."); return;
    }
    try {
      const testo = await file.text();
      if (versione !== versioneDati) return;
      await elaboraTesto(testo, file.name);
    } catch (_) {
      if (versione !== versioneDati) return;
      mostraErrore("Non è stato possibile leggere il file selezionato.");
    }
  }

  async function scaricaTabella() {
    if (!risultato) return;
    try {
      if (!riscalamentoConfermato || !richiedeRiscalamentoConfermato()) return;
      const colonne = colonneNumericheDaRiscalare().map(c => c.nome);
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
  $("confirm-csv-import").addEventListener("click", confermaImportazione);
  $("edit-csv-import").addEventListener("click", modificaImportazione);
  $("import-separator").addEventListener("change", evento =>
    cambiaSeparatoreImportazione(evento.target.value)
  );
  $("import-marker-options").addEventListener("change", evento => {
    if (!evento.target.matches?.(".import-marker-choice") || !importazioneCSV) return;
    const nome = evento.target.value;
    const attivi = new Set(importazioneCSV.marcatoriMancanti);
    if (evento.target.checked) attivi.add(nome); else attivi.delete(nome);
    importazioneCSV.marcatoriMancanti = [...attivi];
  });
  $("view-original").addEventListener("click", () => { vista = "originale"; disegnaTabella(); });
  $("view-work").addEventListener("click", () => { vista = "lavoro"; disegnaTabella(); });
  $("comparison-guide-next").addEventListener("click", () => {
    const campo = prossimoCampoGuida;
    if (!campo) return;
    focalizzaCampo(campo);
    campo.scrollIntoView?.({block:"center"});
    campo.focus?.({preventScroll:true});
  });
  $("question-focus-previous").addEventListener("click", () => {
    indiceDomandaFocalizzata--;
    aggiornaDomandeFocalizzate();
    domandeInterattive()[indiceDomandaFocalizzata]?.querySelector("select, input, textarea")?.focus?.();
  });
  $("question-focus-next").addEventListener("click", () => {
    indiceDomandaFocalizzata++;
    aggiornaDomandeFocalizzate();
    domandeInterattive()[indiceDomandaFocalizzata]?.querySelector("select, input, textarea")?.focus?.();
  });
  $("question-focus-all").addEventListener("click", () => {
    mostraTutteDomande = !mostraTutteDomande;
    aggiornaDomandeFocalizzate();
  });
  $("download-work").addEventListener("click", scaricaTabella);
  $("preprocessing-questions").addEventListener("change", evento => {
    if (!evento.target.matches(".semantic-answer") ||
        evento.target.dataset.answer !== "significatoEstremi") return;
    interpretazione.significatoEstremi = evento.target.value;
    annullaScelteNormalizzazione();
    annullaConfermeCompatibilita();
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    disegnaQuestionario();
  });
  $("confirm-semantic-types").addEventListener("click", () => {
    if (!$("row-meaning").value) {
      mostraErrore("Indica che cosa rappresenta ogni riga prima di confermare le colonne.");
      $("row-meaning").focus?.();
      return;
    }
    nascondiErrore();
    vaiAllaFase("preprocessing");
  });
  $("back-to-semantics").addEventListener("click", () => vaiAllaFase("semantica"));
  $("confirm-preprocessing-phase").addEventListener("click", () => {
    if (colonneNumericheDaRiscalare().some(colonna => colonna.statistiche?.estremi > 0)
        && interpretazione.significatoEstremi !== "reali") {
      mostraErrore("Verifica prima i valori estremi; se sono errori o non sei sicuro, " +
        "la selezione delle colonne resta sospesa.");
      return;
    }
    if (richiedeRiscalamentoConfermato() && !riscalamentoConfermato) {
      mostraErrore("Conferma il preprocessing numerico prima di selezionare le colonne.");
      return;
    }
    nascondiErrore();
    vaiAllaFase("selezione");
  });
  $("back-to-preprocessing").addEventListener("click", () => vaiAllaFase("preprocessing"));
  $("confirm-selection-phase").addEventListener("click", () => {
    if (!Object.values(interpretazione.colonne).some(colonna => colonna.usa)) {
      mostraErrore("Seleziona almeno una colonna per il confronto.");
      return;
    }
    const incompleto = interpretazione.gruppi.find(gruppo =>
      gruppo.tipo === "altro" &&
      Object.values(interpretazione.assegnazioni).includes(gruppo.id));
    if (incompleto) {
      mostraErrore("Indica il significato del gruppo “" + incompleto.nome +
        "” oppure lascia le sue colonne indipendenti.");
      return;
    }
    nascondiErrore();
    interpretazione.questionarioGuidatoV2 = true;
    vaiAllaFase("misure");
  });
  $("back-to-selection").addEventListener("click", () => vaiAllaFase("selezione"));
  $("confirm-numeric-scaling").addEventListener("click", confermaRiscalamentoNumerico);
  $("prepare-comparison-plan").addEventListener("click", preparaPiano);
  $("calculate-gower").addEventListener("click", calcolaMatrice);
  $("download-uncovered-pairs").addEventListener("click", scaricaCoppieNonConfrontabili);
  $("download-gower").addEventListener("click", scaricaMatrice);
  $("download-report").addEventListener("click", scaricaRapporto);
  $("comparison-plan-paths").addEventListener("change", evento => {
    if (evento.target.matches(".global-weights-mode")) {
      interpretazione.modalitaPesiPercorsi = evento.target.value;
      preparaPiano();
      return;
    }
    if (evento.target.matches(".path-normalization-method")) {
      if (!interpretazione.normalizzazioniPercorsi) interpretazione.normalizzazioniPercorsi = {};
      interpretazione.normalizzazioniPercorsi[evento.target.dataset.pathId] = evento.target.value;
      preparaPiano();
      return;
    }
    if (evento.target.matches(".path-robust-rows")) {
      if (!interpretazione.righeAnomaleNormalizzazione) {
        interpretazione.righeAnomaleNormalizzazione = {};
      }
      interpretazione.righeAnomaleNormalizzazione[evento.target.dataset.pathId] =
        evento.target.value;
      preparaPiano();
      return;
    }
    if (evento.target.matches(".path-weight")) {
      if (interpretazione.modalitaPesiPercorsi !== "personalizzati"
          && Object.keys(interpretazione.pesiPercorsi || {}).length === 0) {
        // Compatibilità con controlli preesistenti al selettore globale.
        interpretazione.modalitaPesiPercorsi = "personalizzati";
      }
      if (interpretazione.modalitaPesiPercorsi !== "personalizzati") return;
      if (!interpretazione.pesiPercorsi) interpretazione.pesiPercorsi = {};
      interpretazione.pesiPercorsi[evento.target.dataset.pathId] = evento.target.value;
      preparaPiano();
      return;
    }
    if (evento.target.matches(".numeric-origin-confirmation")) {
      interpretazione.confermaValoriOriginaliNumerici = evento.target.value;
      preparaPiano();
      return;
    }
    if (evento.target.id !== "numeric-dependency-choice") return;
    interpretazione.gestioneDipendenzaLineare = evento.target.value;
    preparaPiano();
  });
  $("comparison-plan-paths").addEventListener("change", evento => {
    if (evento.target.id === "bray-zero-convention") {
      interpretazione.convenzioneBrayCurtisZero = evento.target.value;
      preparaPiano();
      return;
    }
    if (evento.target.id !== "numeric-measure-choice") return;
    interpretazione.misuraNumericaManuale = evento.target.value;
    delete interpretazione.confermaMisuraNumericaProposta;
    annullaScelteNormalizzazione();
    delete interpretazione.confermaValoriOriginaliNumerici;
    const nomi = pianoCorrente?.percorsi.find(p => p.tipo === "numerico")?.colonne || [];
    if (["weighted_minkowski", "weighted_chebyshev"].includes(evento.target.value) && !interpretazione.pesiMisuraManuale) {
      interpretazione.pesiMisuraManuale = nomi.map(() => "1").join("; ");
    }
    preparaPiano();
  });
  $("comparison-plan-paths").addEventListener("click", evento => {
    if (evento.target.id !== "apply-numeric-measure") return;
    interpretazione.misuraNumericaManuale = $("numeric-measure-choice").value;
    interpretazione.confermaMisuraNumericaProposta =
      interpretazione.misuraNumericaManuale === "automatico" ? "si" : undefined;
    annullaScelteNormalizzazione();
    delete interpretazione.confermaValoriOriginaliNumerici;
    const q = $("numeric-measure-q");
    const pesi = $("numeric-measure-weights");
    const lambda = $("numeric-measure-lambda");
    const tolleranza = $("numeric-measure-tolerance");
    if (pianoCorrente?.percorsi.some(
      p => p.idMisura === "bray_curtis" && p.coppieBrayDoppioZero > 0
    )) {
      interpretazione.convenzioneBrayCurtisZero = $("bray-zero-convention").value;
    }
    if (q) interpretazione.ordineMisuraManuale = q.value;
    if (pesi) interpretazione.pesiMisuraManuale = pesi.value;
    if (interpretazione.misuraNumericaManuale === "mahalanobis_ridge") {
      interpretazione.lambdaMahalanobis = lambda.value;
    }
    if (interpretazione.misuraNumericaManuale === "mahalanobis_pinv") {
      interpretazione.tolleranzaPseudoinversa = tolleranza.value;
    }
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
    if (!evento.target.matches(".semantic-role")) return;
    const indice = Number(evento.target.dataset.semanticColumn);
    if (!Number.isInteger(indice) || !risultato?.questionario?.colonne[indice]) return;
    const profilo = risultato.questionario.colonne[indice];
    interpretazione.colonne[profilo.nome].ruolo = evento.target.value;
    if (["identificativo", "data", "testo", "risultato"].includes(evento.target.value)) {
      interpretazione.colonne[profilo.nome].usa = false;
    }
    annullaScelteNormalizzazione();
    annullaConfermeCompatibilita();
    invalidaPesiPerStruttura();
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    faseQuestionario = "semantica";
    disegnaQuestionario();
  });
  $("selection-body").addEventListener("change", evento => {
    if (!evento.target.matches(".semantic-use")) return;
    const indice = Number(evento.target.dataset.semanticColumn);
    if (!Number.isInteger(indice) || !risultato?.questionario?.colonne[indice]) return;
    const profilo = risultato.questionario.colonne[indice];
    interpretazione.colonne[profilo.nome].usa = evento.target.checked;
    annullaScelteNormalizzazione();
    annullaConfermeCompatibilita();
    invalidaPesiPerStruttura();
    // La selezione successiva non annulla le trasformazioni confermate.
    disegnaQuestionario();
  });
  $("adaptive-questions").addEventListener("input", evento => {
    if (evento.target.matches(".gower-nominal-pair")) {
      const campo = evento.target;
      const nome = campo.dataset.gowerNominalColumn;
      const livelli = JSON.parse(campo.dataset.gowerLevels);
      const contenitore = campo.closest(".question-item");
      const coppie = {};
      contenitore.querySelectorAll(".gower-nominal-pair").forEach(input => {
        coppie[input.dataset.gowerPair] = input.value;
      });
      if (!interpretazione.dissimilaritaCategorieGower) {
        interpretazione.dissimilaritaCategorieGower = {};
      }
      interpretazione.dissimilaritaCategorieGower[nome] = {livelli, coppie};
      nascondiPiano();
      return;
    }
    if (evento.target.matches(".temporal-parameter")) {
      const key = evento.target.dataset.temporalKey;
      const id = evento.target.dataset.groupId;
      if (!interpretazione[key]) interpretazione[key] = {};
      interpretazione[key][id] = evento.target.value;
      annullaScelteNormalizzazione();
      nascondiPiano();
      return;
    }
    if (!evento.target.matches(".temporal-order-input")) return;
    if (!interpretazione.ordiniTemporaliGruppi) interpretazione.ordiniTemporaliGruppi = {};
    const id = evento.target.dataset.groupId;
    if (interpretazione.ordiniTemporaliGruppi[id] !== evento.target.value) {
      if (interpretazione.tempiTemporaliGruppi) delete interpretazione.tempiTemporaliGruppi[id];
    }
    interpretazione.ordiniTemporaliGruppi[id] = evento.target.value;
    annullaScelteNormalizzazione();
    nascondiPiano();
  });
  $("adaptive-questions").addEventListener("click", evento => {
    const pulsante = evento.target.closest(".temporal-order-from-csv");
    if (!pulsante) return;
    const id = pulsante.dataset.groupId;
    const nomi = risultato.originale.intestazioni.filter(nome =>
      interpretazione.colonne[nome]?.usa && interpretazione.assegnazioni[nome] === id
    );
    if (nomi.length < 2) return;
    if (!interpretazione.ordiniTemporaliGruppi) interpretazione.ordiniTemporaliGruppi = {};
    if (interpretazione.ordiniTemporaliGruppi[id] !== nomi.join("; ")) {
      if (interpretazione.tempiTemporaliGruppi) delete interpretazione.tempiTemporaliGruppi[id];
    }
    interpretazione.ordiniTemporaliGruppi[id] = nomi.join("; ");
    annullaScelteNormalizzazione();
    disegnaQuestionario();
  });
  $("adaptive-questions").addEventListener("change", evento => {
    if (evento.target.matches(".missing-marker-setting")) {
      if (!interpretazione.statiMancantiPerColonna) {
        interpretazione.statiMancantiPerColonna = {};
      }
      const nome = evento.target.dataset.missingColumn;
      const marcatore = evento.target.dataset.missingMarker;
      if (!interpretazione.statiMancantiPerColonna[nome]) {
        interpretazione.statiMancantiPerColonna[nome] = {};
      }
      interpretazione.statiMancantiPerColonna[nome][marcatore] =
        evento.target.value;
      annullaScelteNormalizzazione();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".temporal-parameter")) {
      const key = evento.target.dataset.temporalKey;
      const id = evento.target.dataset.groupId;
      if (!interpretazione[key]) interpretazione[key] = {};
      interpretazione[key][id] = evento.target.value;
      annullaScelteNormalizzazione();
      nascondiPiano();
      return;
    }
    if (evento.target.matches(".temporal-option")) {
      const key = evento.target.dataset.temporalKey;
      const id = evento.target.dataset.groupId;
      if (!interpretazione[key]) interpretazione[key] = {};
      interpretazione[key][id] = evento.target.value;
      if (key === "misureTemporaliGruppi" && evento.target.value === "pendenze"
          && interpretazione.misureGruppi) delete interpretazione.misureGruppi[id];
      annullaScelteNormalizzazione();
      annullaConfermeCompatibilita();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".set-setting")) {
      if (!interpretazione.configurazioniInsiemi) interpretazione.configurazioniInsiemi = {};
      const nome = evento.target.dataset.setColumn;
      if (!interpretazione.configurazioniInsiemi[nome]) interpretazione.configurazioniInsiemi[nome] = {};
      interpretazione.configurazioniInsiemi[nome][evento.target.dataset.setKey] = evento.target.value;
      annullaScelteNormalizzazione();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".cycle-period-setting, .cycle-unit-setting")) {
      if (!interpretazione.configurazioniCicliche) interpretazione.configurazioniCicliche = {};
      const nome = evento.target.dataset.cycleColumn;
      if (!interpretazione.configurazioniCicliche[nome]) interpretazione.configurazioniCicliche[nome] = {};
      interpretazione.configurazioniCicliche[nome][evento.target.matches(".cycle-period-setting") ? "periodo" : "unita"] = evento.target.value;
      annullaScelteNormalizzazione();
      if (evento.target.matches(".cycle-unit-setting")) disegnaQuestionario();
      else nascondiPiano();
      return;
    }
    if (evento.target.matches(".text-measure-setting")) {
      if (!interpretazione.misureTestualiPerColonna) interpretazione.misureTestualiPerColonna = {};
      interpretazione.misureTestualiPerColonna[evento.target.dataset.textMeasureColumn] =
        evento.target.value;
      annullaScelteNormalizzazione();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".specialized-missing-setting")) {
      if (!interpretazione.mancantiSpecializzatiPerColonna) {
        interpretazione.mancantiSpecializzatiPerColonna = {};
      }
      interpretazione.mancantiSpecializzatiPerColonna[
        evento.target.dataset.specializedMissingColumn
      ] = evento.target.value;
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".temporal-spacing-select")) {
      if (!interpretazione.campionamentiTemporaliGruppi) interpretazione.campionamentiTemporaliGruppi = {};
      interpretazione.campionamentiTemporaliGruppi[evento.target.dataset.groupId] = evento.target.value;
      annullaScelteNormalizzazione();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".group-preprocessing-confirmation")) {
      const id = evento.target.dataset.groupId;
      const campo = evento.target.dataset.kind === "originali"
        ? "confermeValoriOriginaliGruppi" : "confermeRiscalamentiMistiGruppi";
      if (!interpretazione[campo]) interpretazione[campo] = {};
      interpretazione[campo][id] = evento.target.value;
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".group-measure-setting")) {
      if (!interpretazione.misureGruppi) interpretazione.misureGruppi = {};
      interpretazione.misureGruppi[evento.target.dataset.groupId] = evento.target.value;
      annullaScelteNormalizzazione();
      annullaConfermeCompatibilita();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".group-measure-parameter")) {
      const id = evento.target.dataset.groupId;
      const chiave = evento.target.dataset.parameter === "q" ? "ordiniGruppi" : "pesiGruppi";
      if (!interpretazione[chiave]) interpretazione[chiave] = {};
      interpretazione[chiave][id] = evento.target.value;
      annullaScelteNormalizzazione();
      nascondiPiano();
      return;
    }
    if (evento.target.matches(".numeric-missing-setting")) {
      if (!interpretazione.mancantiNumericiPerColonna) {
        interpretazione.mancantiNumericiPerColonna = {};
      }
      interpretazione.mancantiNumericiPerColonna[
        evento.target.dataset.numericMissingColumn
      ] = evento.target.value;
      annullaScelteNormalizzazione();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".gower-setting")) {
      const chiave = evento.target.dataset.gowerKey;
      const colonna = evento.target.dataset.gowerColumn;
      if (!["pesiGower", "mancantiPerColonna", "zeriCondivisiPerColonna",
            "presenzaPositivaPerColonna", "ordinePerColonna", "ordiniLivelliGower",
            "righeOutlierGower", "modalitaCategorieGower",
            "modalitaIntervalliGower", "passiOrdinaliGower"].includes(chiave)) return;
      if (!interpretazione[chiave]) interpretazione[chiave] = {};
      interpretazione[chiave][colonna] = evento.target.value;
      annullaScelteNormalizzazione();
      disegnaQuestionario();
      return;
    }
    if (evento.target.matches(".semantic-answer, .semantic-input")) {
      interpretazione[evento.target.dataset.answer] = evento.target.value;
      if (evento.target.matches(".semantic-answer")) {
        const chiave = evento.target.dataset.answer || "";
        if (/^(gestioneQuantitativeMiste|confrontoQuantitativo|aggregazioneScarti|dipendenzaCoordinate|importanzaCoordinate|somiglianza-|ritardo-|totale-|mancanti-gruppo-|misuraBinaria-|naturaDistribuzione-|misuraDistribuzione-)/.test(chiave)) {
          annullaScelteNormalizzazione();
        }
        if (/^(somiglianza|ritardo|totale|naturaDistribuzione|misuraDistribuzione)-/.test(chiave)) {
          const idGruppo = chiave.replace(/^(somiglianza|ritardo|totale|naturaDistribuzione|misuraDistribuzione)-/, "");
          if (interpretazione.misureGruppi) delete interpretazione.misureGruppi[idGruppo];
          annullaConfermeCompatibilita();
        }
        if (chiave === "gestioneQuantitativeMiste") {
          // Cambiando la struttura cambiano anche gli ID dei percorsi.
          delete interpretazione.pesiPercorsi;
          interpretazione.modalitaPesiPercorsi = "uguali";
          delete interpretazione.misuraNumericaManuale;
          delete interpretazione.pesiMisuraManuale;
          annullaConfermeCompatibilita();
        }
        if (chiave === "confrontoQuantitativo") delete interpretazione.confermaValoriOriginaliNumerici;
        disegnaQuestionario();
      }
      else nascondiPiano();
    }
  });
  $("row-meaning").addEventListener("change", evento => {
    interpretazione.riga = evento.target.value;
    nascondiPiano();
  });
  $("numeric-preliminary-content").addEventListener("change", evento => {
    if (!evento.target.matches(".multivariate-extremes-choice")) return;
    interpretazione.significatoEstremi = evento.target.value;
    riscalamentoConfermato = false;
    interpretazione.riscalamentoConfermato = false;
    disegnaQuestionario();
  });
  $("numeric-group-proposals").addEventListener("click", evento => {
    const pulsante = evento.target.closest(".apply-group-proposal");
    if (!pulsante) return;
    const indice = Number(pulsante.dataset.proposalIndex);
    const proposta = proposteGruppiCorrenti[indice];
    if (!proposta) {
      mostraErrore("La proposta non è più disponibile. Riesamina le colonne selezionate.");
      return;
    }
    const selezione = pulsante.closest(".question-item").querySelector(".group-proposal-type");
    const tipo = selezione?.value || "";
    if (!["tempo", "ripetute", "coordinate", "parti", "distribuzione"].includes(tipo)) {
      mostraErrore("Prima di creare il gruppo, conferma che cosa rappresentano le sue colonne.");
      return;
    }
    const disponibili = new Set(colonneNumericheSelezionate().map(colonna => colonna.nome));
    if (!proposta.colonne.every(nome => disponibili.has(nome))) {
      mostraErrore("Alcune colonne sono state già assegnate o escluse. Controlla la nuova proposta.");
      disegnaQuestionario();
      return;
    }
    annullaScelteNormalizzazione();
    invalidaPesiPerStruttura();
    const gruppo = creaGruppo();
    gruppo.nome = proposta.nome;
    gruppo.tipo = tipo;
    proposta.colonne.forEach(nome => {
      interpretazione.assegnazioni[nome] = gruppo.id;
    });
    nascondiErrore();
    disegnaQuestionario();
  });

  $("add-column-group").addEventListener("click", () => {
    annullaScelteNormalizzazione();
    annullaConfermeCompatibilita();
    invalidaPesiPerStruttura();
    creaGruppo();
    disegnaQuestionario();
  });
  function invalidaConfermaTemporale(idGruppo) {
    if (!idGruppo) return;
    for (const chiave of [
      "ordiniTemporaliGruppi", "campionamentiTemporaliGruppi",
      "tempiTemporaliGruppi", "unitaTemporaleGruppi",
      "misureTemporaliGruppi", "metodiAllineamentoTemporaleGruppi",
      "costiDTWGruppi", "finestreDTWGruppi",
      "penalizzazioniDTWGruppi", "pesiRitardoDTWGruppi",
      "scaleRitardoDTWGruppi", "tolleranzeValoreLCSSGruppi",
      "tolleranzeTempoLCSSGruppi", "coppieTemporaliGruppi"
    ]) {
      if (interpretazione[chiave]) delete interpretazione[chiave][idGruppo];
    }
  }
  $("group-assignment-body").addEventListener("change", evento => {
    if (!evento.target.matches(".group-assignment")) return;
    const nome = evento.target.dataset.groupColumn;
    const precedenteGruppo = interpretazione.assegnazioni[nome];
    let gruppoId = evento.target.value;
    if (gruppoId === "__nuovo__") gruppoId = creaGruppo().id;
    if (gruppoId !== precedenteGruppo) {
      invalidaConfermaTemporale(precedenteGruppo);
      invalidaConfermaTemporale(gruppoId);
      delete interpretazione[`misuraBinaria-${precedenteGruppo}`];
      delete interpretazione[`misuraBinaria-${gruppoId}`];
    }
    if (gruppoId) interpretazione.assegnazioni[nome] = gruppoId;
    else delete interpretazione.assegnazioni[nome];
    if (gruppoId !== precedenteGruppo) invalidaPesiPerStruttura();
    annullaScelteNormalizzazione();
    annullaConfermeCompatibilita();
    disegnaQuestionario();
  });
  $("group-config-list").addEventListener("change", evento => {
    const contenitore = evento.target.closest(".group-config");
    if (!contenitore) return;
    const gruppo = interpretazione.gruppi.find(elemento => elemento.id === contenitore.dataset.groupId);
    if (!gruppo) return;
    if (evento.target.matches(".group-name")) gruppo.nome = evento.target.value.trim() || gruppo.nome;
    if (evento.target.matches(".group-type")) {
      if (gruppo.tipo !== evento.target.value) {
        invalidaConfermaTemporale(gruppo.id);
        delete interpretazione[`misuraBinaria-${gruppo.id}`];
      }
      gruppo.tipo = evento.target.value;
      invalidaPesiPerStruttura();
      if (interpretazione.misureGruppi) delete interpretazione.misureGruppi[gruppo.id];
      annullaScelteNormalizzazione();
      annullaConfermeCompatibilita();
    }
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
    invalidaConfermaTemporale(gruppoId);
    delete interpretazione[`misuraBinaria-${gruppoId}`];
    interpretazione.gruppi = interpretazione.gruppi.filter(gruppo => gruppo.id !== gruppoId);
    invalidaPesiPerStruttura();
    annullaScelteNormalizzazione();
    annullaConfermeCompatibilita();
    Object.keys(interpretazione.assegnazioni).forEach(nome => {
      if (interpretazione.assegnazioni[nome] === gruppoId) delete interpretazione.assegnazioni[nome];
    });
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
