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
  let gowerCorrente = null;

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
    const origine = vista === "originale"
      ? "Valori originali: sono la base dei percorsi che non richiedono trasformazioni."
      : "Anteprima diagnostica: non viene usata automaticamente da tutti i percorsi.";
    $("preview-caption").textContent = `${origine} ${limiteRighe} di ${righe.length} righe${limiteColonne < risultato.originale.intestazioni.length ? ` e ${limiteColonne} di ${risultato.originale.intestazioni.length} colonne` : ""}.`;
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

  function haCorrelazioniForti(profili) {
    const colonne = profili.map(profilo => risultato.colonne.find(colonna => colonna.nome === profilo.nome));
    for (let i = 0; i < colonne.length; i += 1) {
      for (let j = i + 1; j < colonne.length; j += 1) {
        const coppie = (colonne[i]?.valoriNumerici || []).map((x, indice) => [x, colonne[j]?.valoriNumerici?.[indice]])
          .filter(([x, y]) => typeof x === "number" && typeof y === "number");
        if (coppie.length < 4) continue;
        const mediaX = coppie.reduce((somma, [x]) => somma + x, 0) / coppie.length;
        const mediaY = coppie.reduce((somma, [, y]) => somma + y, 0) / coppie.length;
        const numeratore = coppie.reduce((somma, [x, y]) => somma + (x - mediaX) * (y - mediaY), 0);
        const scalaX = Math.sqrt(coppie.reduce((somma, [x]) => somma + (x - mediaX) ** 2, 0));
        const scalaY = Math.sqrt(coppie.reduce((somma, [, y]) => somma + (y - mediaY) ** 2, 0));
        if (scalaX > 0 && scalaY > 0 && Math.abs(numeratore / (scalaX * scalaY)) >= 0.8) return true;
      }
    }
    return false;
  }

  function nascondiPiano() {
    $("comparison-plan").hidden = true;
    $("gower-actions").hidden = true;
    $("gower-result").hidden = true;
    pianoCorrente = null;
    gowerCorrente = null;
  }

  function disegnaPiano(piano) {
    pianoCorrente = piano;
    gowerCorrente = null;
    $("gower-result").hidden = true;
    $("comparison-plan-paths").innerHTML = piano.percorsi.map((percorso, indice) => {
      const classe = percorso.stato === "da_completare" ? " incomplete" : "";
      const pre = percorso.preelaborazione;
      const mancanti = percorso.mancanti;
      const passi = pre.passi.length
        ? pre.passi.map(passo => `${escapeHtml(passo.colonna)}: ${escapeHtml(passo.etichetta)}`).join(" · ")
        : "Nessuna trasformazione colonna per colonna";
      const calcolo = percorso.calcolo.disponibile ? "Calcolo disponibile" : "Calcolo non ancora collegato";
      const parametri = Object.entries(percorso.parametri || {}).map(([chiave, valore]) =>
        `${escapeHtml(chiave)} = ${escapeHtml(Array.isArray(valore) ? valore.join(", ") : valore)}`
      ).join(" · ");
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
          <div><dt>Mancanti</dt><dd>${escapeHtml(mancanti.descrizione)}</dd></div>
          ${percorso.proprieta ? `<div><dt>Proprietà</dt><dd>${escapeHtml(percorso.proprieta)}</dd></div>` : ""}
          <div><dt>Stato</dt><dd>${escapeHtml(calcolo)}</dd></div>
        </dl>
        <span>${escapeHtml(pre.descrizione)}</span>
        <p>${escapeHtml(percorso.motivo)}</p>
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
        : `${piano.conteggioPercorsi} percorsi verranno calcolati separatamente, senza combinarli automaticamente.`;
    $("gower-actions").hidden = !(piano.completo && piano.percorsi.some(percorso => percorso.tipo === "gower" && percorso.calcolo.disponibile));
    $("comparison-plan").hidden = false;
  }

  function disegnaMatriceGower(gower) {
    const limite = Math.min(12, gower.etichette.length);
    const etichette = gower.etichette.slice(0, limite);
    $("gower-matrix-head").innerHTML = `<tr><th>Riga</th>${etichette.map(etichetta => `<th>${escapeHtml(etichetta)}</th>`).join("")}</tr>`;
    $("gower-matrix-body").innerHTML = gower.matrice.slice(0, limite).map((riga, indice) => `<tr>
      <th scope="row">${escapeHtml(etichette[indice])}</th>
      ${riga.slice(0, limite).map(valore => `<td>${valore === null ? "—" : escapeHtml(formatoNumero(valore))}</td>`).join("")}
    </tr>`).join("");
    $("gower-result-title").textContent = gower.metodo;
    $("gower-result-caption").textContent = `${gower.etichette.length} × ${gower.etichette.length}. ${gower.nota}${limite < gower.etichette.length ? ` Anteprima delle prime ${limite} righe.` : ""}`;
    $("download-gower").disabled = false;
    $("gower-result").hidden = false;
  }

  async function calcolaGower() {
    if (!pianoCorrente) return;
    const pulsante = $("calculate-gower");
    const testo = pulsante.textContent;
    pulsante.disabled = true;
    pulsante.textContent = "Calcolo…";
    try {
      gowerCorrente = await P.calcolaGower(testoOriginale, scelte, interpretazione);
      nascondiErrore();
      disegnaMatriceGower(gowerCorrente);
    } catch (errore) {
      mostraErrore(errore.message);
    } finally {
      pulsante.disabled = false;
      pulsante.textContent = testo;
    }
  }

  function scaricaGower() {
    if (!gowerCorrente) return;
    const url = URL.createObjectURL(new Blob(["\uFEFF" + gowerCorrente.csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "matrice_gower.csv";
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
    const gruppo = { id: `gruppo-${numero}`, nome: `Gruppo ${numero}`, tipo: "ripetute" };
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
    $("group-assignment-body").innerHTML = incluse.length ? incluse.map(profilo => `<tr>
      <th scope="row">${escapeHtml(profilo.nome)}</th>
      <td><select class="column-choice group-assignment" data-group-column="${escapeHtml(profilo.nome)}" aria-label="Gruppo della colonna ${escapeHtml(profilo.nome)}">${opzioniGruppo(interpretazione.assegnazioni[profilo.nome] || "")}</select></td>
    </tr>`).join("") : `<tr><td colspan="2">Non è stata inclusa alcuna colonna nel confronto.</td></tr>`;

    $("group-config-list").innerHTML = interpretazione.gruppi.map(gruppo => {
      const membri = incluse.filter(profilo => interpretazione.assegnazioni[profilo.nome] === gruppo.id).map(profilo => profilo.nome);
      const tipi = membri.map(nome => risultato.colonne.find(colonna => colonna.nome === nome)?.tipo);
      const tutteNumeriche = tipi.length >= 2 && tipi.every(tipo => tipo === "numerica" || tipo === "numerica_costante");
      const nota = membri.length < 2
        ? "Assegna almeno due colonne a questo gruppo."
        : !tutteNumeriche && gruppo.tipo !== "altro"
          ? "Per questa interpretazione servono almeno due colonne numeriche."
          : `Colonne: ${membri.join(", ")}.`;
      return `<div class="group-config" data-group-id="${gruppo.id}">
        <label>Nome del gruppo<input class="group-name" value="${escapeHtml(gruppo.nome)}" aria-label="Nome di ${escapeHtml(gruppo.nome)}"></label>
        <label>Che cosa formano insieme?<select class="group-type" aria-label="Tipo di ${escapeHtml(gruppo.nome)}">
          <option value="ripetute"${gruppo.tipo === "ripetute" ? " selected" : ""}>Misurazioni dello stesso profilo</option>
          <option value="tempo"${gruppo.tipo === "tempo" ? " selected" : ""}>Osservazioni successive nel tempo</option>
          <option value="parti"${gruppo.tipo === "parti" ? " selected" : ""}>Parti dello stesso totale</option>
          <option value="altro"${gruppo.tipo === "altro" ? " selected" : ""}>Un altro insieme di caratteristiche</option>
        </select></label>
        <p>${escapeHtml(nota)}</p>
        <button class="remove-group" type="button">Rimuovi gruppo</button>
      </div>`;
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

    const profiliInclusi = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa);
    const nomiInclusi = new Set(profiliInclusi.map(profilo => profilo.nome));
    const colonneIncluse = risultato.colonne.filter(colonna => nomiInclusi.has(colonna.nome));
    const ruoliInclusi = new Set(profiliInclusi.map(profilo => interpretazione.colonne[profilo.nome].ruolo));
    const domande = [];
    if (colonneIncluse.some(colonna => colonna.mancanti > 0)) domande.push(domandaAdattiva(
      "significatoMancanti", "Che cosa significa una casella vuota?",
      "La risposta cambia il modo in cui due righe possono essere confrontate.",
      [["sconosciuto", "Il valore non è conosciuto"], ["non_applicabile", "La domanda non si applica"], ["assenza", "Indica assenza"], ["misto", "Dipende dalla colonna"], ["ignoto", "Non lo so"]]
    ));
    if (colonneIncluse.some(colonna => colonna.statistiche?.estremi > 0)) domande.push(domandaAdattiva(
      "significatoEstremi", "I valori molto lontani dagli altri sono plausibili?",
      "Sono stati osservati alcuni valori eccezionalmente alti o bassi.",
      [["reali", "Sì, sono casi reali"], ["errori", "Probabilmente sono errori"], ["controllare", "Vanno controllati uno per uno"], ["ignoto", "Non lo so"]]
    ));
    if (ruoliInclusi.has("presenza")) domande.push(domandaAdattiva(
      "zeriCondivisi", "Due assenze in comune rendono simili due righe?",
      "Pensa alle colonne di presenza/assenza: avere entrambi 0 può essere informativo oppure irrilevante.",
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
    const percorsoNumerico = indipendentiStandard.length > 0 && indipendentiStandard.every(profilo => {
      const colonna = risultato.colonne.find(elemento => elemento.nome === profilo.nome);
      return interpretazione.colonne[profilo.nome].ruolo === "quantita"
        && ["numerica", "numerica_costante"].includes(colonna?.tipo);
    });
    if (percorsoNumerico) {
      domande.push(domandaAdattiva(
        "confrontoQuantitativo", "Che cosa rappresentano insieme questi numeri?",
        "Questa informazione serve a distinguere misure ordinarie, abbondanze e frequenze. Non occorre conoscere i nomi delle distanze.",
        [["assoluto", "Caratteristiche misurate per ogni riga"], ["abbondanza", "Abbondanze o conteggi, come specie o eventi"], ["frequenze", "Frequenze, dove anche le componenti rare sono importanti"], ["relativo", "Valori per cui conta soprattutto la differenza in proporzione"], ["ignoto", "Non lo so — usa la scelta consigliata"]]
      ));

      const confronto = valoreRisposta("confrontoQuantitativo");
      if (confronto === "ignoto") domande.push(notaAutomatica(
        "Scelta consigliata automatica",
        "Il sito riequilibrerà le colonne per prudenza, assegnerà loro la stessa importanza e sceglierà una misura poco sensibile ai valori estremi quando necessario."
      ));
      if (confronto === "assoluto") {
        const riscalamentoAutomatico = indipendentiStandard.some(profilo => {
          const colonna = risultato.colonne.find(elemento => elemento.nome === profilo.nome);
          return ["zscore", "robusto", "maxabs", "minmax"].includes(colonna?.metodo);
        });
        if (riscalamentoAutomatico) {
          domande.push(notaAutomatica(
            "Riequilibrio automatico delle colonne",
            "Il sito ha rilevato scale, dispersioni o valori estremi che renderebbero dominante almeno una colonna. Applicherà automaticamente il riscalamento più adatto e userà quei valori nel confronto finale."
          ));
        } else {
          domande.push(domandaAdattiva(
            "tipoQuantita", "Le colonne misurano lo stesso tipo di quantità?",
            "Per esempio, più misure espresse tutte in centimetri sono dello stesso tipo; età, reddito e pressione sono quantità diverse.",
            [["stesso", "Sì, misurano lo stesso tipo di quantità"], ["diverse", "No, misurano quantità diverse"], ["ignoto", "Non lo so — riequilibrale per prudenza"]]
          ));
        }
        domande.push(domandaAdattiva(
          "aggregazioneScarti", "Quando due righe devono essere considerate molto diverse?",
          "Scegli l'effetto che vuoi ottenere; il sito tradurrà la risposta nella misura matematica adatta.",
          [["lineare", "Quando differiscono in molte caratteristiche, anche di poco"], ["quadratica", "Quando presentano alcune differenze grandi"], ["massimo", "Quando basta una sola differenza molto grande"], ["minkowski", "Voglio impostare manualmente la sensibilità (avanzato)"], ["ignoto", "Non lo so — usa la scelta consigliata"]]
        ));
        if (valoreRisposta("aggregazioneScarti") === "minkowski") domande.push(domandaInput(
          "ordineMinkowski", "Sensibilità personalizzata q",
          "Questa è un'impostazione avanzata. Inserisci un numero almeno pari a 1; valori maggiori danno più peso alle differenze grandi.", "Per esempio 3", "number"
        ));
        if (indipendentiStandard.length >= 2 && haCorrelazioniForti(indipendentiStandard)) domande.push(domandaAdattiva(
          "dipendenzaCoordinate", "Alcune colonne tendono a variare insieme. Vuoi evitare che informazioni simili contino più volte?",
          "Il sito ha rilevato una forte relazione numerica tra almeno due colonne. L'opzione sì usa un confronto che tiene conto di queste relazioni.",
          [["si", "Sì, evita di contare più volte la stessa informazione"], ["no", "No, considera ogni colonna separatamente"], ["ignoto", "Non lo so — considera le colonne separatamente"]]
        ));
        if (indipendentiStandard.length >= 2) {
          domande.push(domandaAdattiva(
            "importanzaCoordinate", "Alcune caratteristiche devono contare più delle altre?",
            "Se non hai indicazioni specifiche, il sito assegna la stessa importanza a tutte.",
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
    }
    interpretazione.gruppi.forEach(gruppo => {
      const membri = profili.filter(profilo => interpretazione.colonne[profilo.nome]?.usa && interpretazione.assegnazioni[profilo.nome] === gruppo.id);
      const tipi = membri.map(profilo => risultato.colonne.find(colonna => colonna.nome === profilo.nome)?.tipo);
      const valido = membri.length >= 2 && tipi.every(tipo => tipo === "numerica" || tipo === "numerica_costante");
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
      interpretazione = { colonne: {}, gruppi: [], assegnazioni: {}, prossimoGruppo: 1 };
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
  $("prepare-comparison-plan").addEventListener("click", preparaPiano);
  $("calculate-gower").addEventListener("click", calcolaGower);
  $("download-gower").addEventListener("click", scaricaGower);
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
    disegnaQuestionario();
  });
  $("adaptive-questions").addEventListener("change", evento => {
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
    disegnaQuestionario();
  });
  $("group-config-list").addEventListener("change", evento => {
    const contenitore = evento.target.closest(".group-config");
    if (!contenitore) return;
    const gruppo = interpretazione.gruppi.find(elemento => elemento.id === contenitore.dataset.groupId);
    if (!gruppo) return;
    if (evento.target.matches(".group-name")) gruppo.nome = evento.target.value.trim() || gruppo.nome;
    if (evento.target.matches(".group-type")) gruppo.tipo = evento.target.value;
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
