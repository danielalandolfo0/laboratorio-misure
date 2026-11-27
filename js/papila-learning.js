"use strict";

(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[character]);
  let rows = [], numeric = [], selected = new Set(), current = [], answers = [], step = 0;
  const IMAGE_BASE = "https://raw.githubusercontent.com/JuanitoOrtega/papila_db/main/DB_PAPILA/FundusImages/";
  let seed = 1937, used = new Set();
  let chosenGroups = [];
  const assigned = new Map(), scalings = new Map();
  let selectedKeys = [];

  function stage(id) {
    for (const name of ["papila-setup","papila-block-stage","papila-scaling-stage","papila-meaning-stage","papila-comparison","papila-completion"])
      $(name).hidden = name !== id;
    $(id).scrollIntoView({behavior:"smooth",block:"start"});
  }
  document.querySelectorAll("[data-back]").forEach(button => button.addEventListener("click", () => stage(button.dataset.back)));

  function groupsFor(keys) {
    const groups = new Map();
    for (const key of keys) {
      const match = key.match(/^(.*)_(OD|OS)$/);
      const name = assigned.get(key) || (match ? match[1] : key);
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(key);
    }
    return [...groups].map(([name,columns]) => ({name,columns}));
  }
  function isBinary(columns) {
    return columns.every(key => rows.every(row => row[key] === "" || row[key] === "0" || row[key] === "1"));
  }
  function renderMeaning() {
    $("papila-measures").innerHTML = groupsFor(selectedKeys).map(({name,columns}) => {
      const binary = isBinary(columns);
      if (columns.length === 1 && !binary) return '<div class="meaning-item"><h3>' + escape(name) + '</h3><p>Una sola quantità: conta lo scarto assoluto. Non servono altre domande.</p></div>';
      const question = binary ? "Due assenze contemporanee devono contare come somiglianza?" : "Quali differenze devono contare di più?";
      const choices = binary ? [["hamming","Sì: confronto uguale/diverso"],["jaccard","No: contano soprattutto le presenze"],["unsure","Non sono sicuro"]]
        : [["manhattan","La somma degli scarti"],["euclidean","Gli scarti grandi pesano di più"],["chebyshev","Conta lo scarto più grande"],["unsure","Non sono sicuro"]];
      return '<div class="meaning-item"><h3>' + escape(name) + '</h3><p>' + columns.map(escape).join(' · ') + '</p><label>' + question + '<select class="papila-answer" data-group="' + escape(name) + '"><option value="">Scegli una risposta</option>' + choices.map(([id,label]) => '<option value="' + id + '">' + label + '</option>').join('') + '</select></label></div>';
    }).join("");
  }

  function parseCsv(text) {
    const records = [], row = []; let cell = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const character = text[i];
      if (quoted && character === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (character === '"') quoted = !quoted;
      else if (!quoted && (character === "," || character === "\n" || character === "\r")) {
        if (character !== "\r" || text[i + 1] !== "\n") { row.push(cell); cell = ""; }
        if (character !== ",") {
          if (character === "\r" && text[i + 1] === "\n") { row.push(cell); cell = ""; i++; }
          if (row.some(value => value !== "")) records.push(row.splice(0));
        }
      } else cell += character;
    }
    if (quoted) throw new Error("Il CSV contiene virgolette non chiuse.");
    if (cell || row.length) { row.push(cell); records.push(row); }
    const header = records.shift()?.map((name,i) => i === 0 ? name.replace(/^\uFEFF/, "") : name);
    if (!header || new Set(header).size !== header.length || records.some(record => record.length !== header.length))
      throw new Error("Il CSV ha intestazioni ripetute o righe con un numero di colonne diverso.");
    return records.map(record => Object.fromEntries(header.map((name,i) => [name,record[i]])));
  }

  function report(error) { $("papila-error").textContent = error || ""; $("papila-error").hidden = !error; }
  function setup() {
    $("papila-count").textContent = "Caricamento dei dati PAPILA…";
    fetch("examples/papila.csv").then(response => {
      if (!response.ok) throw new Error("Il dataset PAPILA non è disponibile sul sito.");
      return response.text();
    }).then(text => {
      const parsed = parseCsv(text);
      const required = ["patient_id","Diagnosis_OD","Diagnosis_OS","image_OD","image_OS"];
      if (!parsed.length || required.some(key => !(key in parsed[0]))) throw new Error("Usa il CSV paziente creato dall'importatore PAPILA.");
      if (new Set(parsed.map(row => row.patient_id)).size !== parsed.length) throw new Error("Gli ID dei pazienti devono essere univoci.");
      rows = parsed;
      numeric = Object.keys(rows[0]).filter(key => !required.includes(key) && rows.every(row =>
        row[key] === "" || (Number.isFinite(Number(row[key])) && row[key].trim() !== "")) &&
        rows.some(row => row[key] !== ""));
      $("papila-features").innerHTML = Object.keys(rows[0]).map(key => {
        const complete = rows.filter(row => row[key] !== "").length / rows.length;
        const output = /^Diagnosis_(OD|OS)$/.test(key), image = /^image_(OD|OS)$/.test(key), id = key === "patient_id";
        const available = numeric.includes(key);
        const suggested = available && complete >= .9 && !/^Gender_/.test(key) && !/^astigmatism_/.test(key);
        const label = output ? "Diagnosi · output riservato" : image ? "Fotografia · solo visualizzazione" : id ? "Identificativo" : Math.round(complete * 100) + "% presente";
        return '<tr><th scope="row">' + escape(key) + '</th><td><small>' + label + '</small></td><td><input type="checkbox" class="papila-use" data-key="' + escape(key) + '" aria-label="Usa ' + escape(key) + ' nella distanza"' + (suggested ? ' checked' : '') + (available ? '' : ' disabled') + '></td><td><input type="checkbox" class="papila-show" data-key="' + escape(key) + '" aria-label="Mostra ' + escape(key) + ' nella scheda"' + (suggested || image || id ? ' checked' : '') + (output ? ' disabled' : '') + '></td></tr>';
      }).join("");
      $("papila-options").hidden = false;
      $("papila-count").textContent = rows.length + " pazienti, " + numeric.length + " colonne numeriche disponibili.";
      report("");
    }).catch(error => { rows = []; $("papila-options").hidden = true; $("papila-count").textContent = ""; report(error.message); });
  }
  $("papila-confirm-selection").addEventListener("click", () => {
    selectedKeys = [...$("papila-features").querySelectorAll(".papila-use:checked")].map(input => input.dataset.key);
    if (!selectedKeys.length) return report("Seleziona almeno una caratteristica per calcolare la distanza.");
    const complete = rows.filter(row => selectedKeys.every(key => row[key] !== ""));
    if (complete.length < 3) return report("Con queste caratteristiche restano meno di tre pazienti con dati completi.");
    report("");
    const names = [...new Set(selectedKeys.map(key => key.replace(/_(OD|OS)$/,"")))];
    $("papila-blocks").innerHTML = selectedKeys.map(key => {
      const proposal = key.replace(/_(OD|OS)$/ ,"");
      const current = assigned.get(key) || proposal;
      return '<tr><th scope="row">' + escape(key) + '</th><td><select class="papila-assignment" data-key="' + escape(key) + '"><option value="' + escape(key) + '"' + (current === key ? ' selected' : '') + '>Indipendente</option>' + names.map(name => '<option value="' + escape(name) + '"' + (current === name ? ' selected' : '') + '>Blocco ' + escape(name) + '</option>').join('') + '</select></td></tr>';
    }).join("");
    stage("papila-block-stage");
  });
  $("papila-blocks").addEventListener("change", event => {
    if (event.target.matches(".papila-assignment")) assigned.set(event.target.dataset.key,event.target.value);
  });
  $("papila-confirm-blocks").addEventListener("click", () => {
    $("papila-scaling").innerHTML = groupsFor(selectedKeys).map(({name,columns}) => {
      const binary = isBinary(columns);
      const value = binary ? "none" : scalings.get(name) || "minmax";
      return '<label class="meaning-item"><strong>' + escape(name) + '</strong> · ' + columns.map(escape).join(' · ') + '<br><select class="papila-scale" data-group="' + escape(name) + '"' + (binary ? ' disabled' : '') + '><option value="minmax"' + (value === 'minmax' ? ' selected' : '') + '>Min–max (suggerito)</option><option value="zscore"' + (value === 'zscore' ? ' selected' : '') + '>Z-score</option><option value="robust"' + (value === 'robust' ? ' selected' : '') + '>Mediana e IQR</option><option value="none"' + (value === 'none' ? ' selected' : '') + '>Valori originali' + (binary ? ' · dati binari' : '') + '</option></select></label>';
    }).join("");
    stage("papila-scaling-stage");
  });
  $("papila-scaling").addEventListener("change", event => {
    if (event.target.matches(".papila-scale")) scalings.set(event.target.dataset.group,event.target.value);
  });
  $("papila-confirm-scaling").addEventListener("click", () => { renderMeaning(); stage("papila-meaning-stage"); });

  function random() { seed = (1664525 * seed + 1013904223) >>> 0; return seed / 4294967296; }
  function triple() {
    if (rows.length < 3) throw new Error("Servono almeno tre pazienti con dati completi.");
    for (let tries = 0; tries < 1000; tries++) {
      const indices = new Set(); while (indices.size < 3) indices.add(Math.floor(random() * rows.length));
      const key = [...indices].sort((a,b) => a-b).join("-");
      if (!used.has(key)) { used.add(key); return [...indices].map(index => rows[index]); }
    }
    used.clear(); return triple();
  }
  function card(row) {
    const shown = [...$("papila-features").querySelectorAll(".papila-show:checked")].map(input => input.dataset.key);
    const pictures = ["OD","OS"].filter(eye => shown.includes("image_" + eye)).map(eye => {
      const filename = row["image_" + eye];
      return '<figure><img loading="lazy" src="' + escape(IMAGE_BASE + encodeURIComponent(filename)) + '" alt="Fondo oculare ' + eye + '"><figcaption>Occhio ' + eye + '</figcaption></figure>';
    }).join("");
    return '<button type="button" class="candidate-card papila-card" data-id="' + row._learningId + '" aria-pressed="false"><span class="candidate-content"><strong>' + escape(row.patient_id) + '</strong><span class="papila-images">' + pictures + '</span>' + shown.filter(key => key !== "patient_id" && !key.startsWith("image_")).map(key => '<span class="measure-group"><strong>' + escape(key) + ':</strong> ' + escape(row[key] || "—") + '</span>').join("") + '</span></button>';
  }
  function render() {
    current = triple(); selected = new Set();
    $("papila-progress").textContent = "Confronto " + (step + 1) + " di 10";
    $("papila-candidates").innerHTML = current.map(card).join("");
    $("papila-next").disabled = true;
  }
  $("papila-start").addEventListener("click", () => {
    const groups = groupsFor(selectedKeys);
    const controls = [...$("papila-measures").querySelectorAll(".papila-answer")];
    if (controls.some(control => !control.value)) {
      $("papila-meaning-error").textContent = "Rispondi a tutte le domande, oppure scegli «Non sono sicuro».";
      $("papila-meaning-error").hidden = false;
      return;
    }
    const answersByGroup = new Map(controls.map(control => [control.dataset.group,control.value]));
    let combinations = 1;
    chosenGroups = groups.map(group => {
      const binary = isBinary(group.columns);
      const answer = answersByGroup.get(group.name);
      const candidates = group.columns.length === 1 && !binary ? ["manhattan"]
        : answer === "unsure" ? (binary ? ["hamming","jaccard"] : ["manhattan","euclidean","chebyshev"]) : [answer];
      combinations *= candidates.length;
      return {...group,candidates,scaling:binary ? "none" : scalings.get(group.name) || "minmax"};
    });
    if (combinations > 64) {
      $("papila-meaning-error").textContent = "Le risposte lasciano " + combinations + " combinazioni di misure. Specifica alcune risposte per ridurle a 64 o meno.";
      $("papila-meaning-error").hidden = false;
      return;
    }
    $("papila-meaning-error").hidden = true;
    const complete = rows.filter(row => selectedKeys.every(key => row[key] !== "" && Number.isFinite(Number(row[key]))));
    if (complete.length < 3) return report("Con queste colonne restano meno di tre pazienti con dati completi.");
    rows = complete; rows.forEach((row,index) => { row._learningId = index + 1; });
    answers = []; step = 0; used.clear(); report("");
    stage("papila-comparison"); render();
  });
  $("papila-candidates").addEventListener("click", event => {
    const button = event.target.closest(".candidate-card"); if (!button) return;
    const id = button.dataset.id;
    if (selected.has(id)) selected.delete(id); else if (selected.size < 2) selected.add(id);
    for (const card of $("papila-candidates").querySelectorAll(".candidate-card")) card.setAttribute("aria-pressed",String(selected.has(card.dataset.id)));
    $("papila-next").disabled = selected.size !== 2;
  });
  $("papila-skip").addEventListener("click", render);
  $("papila-next").addEventListener("click", () => {
    if (selected.size !== 2) return;
    answers.push({step:step+1,candidates:current.map(row => row._learningId),chosen:[...selected].map(Number),excluded:current.find(row => !selected.has(String(row._learningId)))._learningId});
    step++;
    if (step < 10) return render();
    $("papila-comparison").hidden = true; $("papila-completion").hidden = false;
    try {
      const blocks = chosenGroups.map(group => {
        const columns = group.columns.map(key => {
          const values = rows.map(row => Number(row[key]));
          if (group.scaling === "none") return values;
          if (group.scaling === "zscore") {
            const mean = values.reduce((a,b) => a+b,0) / values.length;
            const sd = Math.sqrt(values.reduce((sum,value) => sum + (value-mean)**2,0) / values.length);
            return values.map(value => sd ? (value-mean)/sd : 0);
          }
          const sorted = [...values].sort((a,b) => a-b);
          const quantile = p => { const k=(sorted.length-1)*p, lo=Math.floor(k); return sorted[lo]+(sorted[Math.ceil(k)]-sorted[lo])*(k-lo); };
          const low = group.scaling === "robust" ? quantile(.5) : sorted[0];
          const span = group.scaling === "robust" ? quantile(.75)-quantile(.25) : sorted.at(-1)-sorted[0];
          return values.map(value => span ? (value-low) / span : 0);
        });
        return {id:group.name,label:group.name,candidateMeasures:group.candidates,vectors:rows.map((_,i) => columns.map(column => column[i]))};
      });
      const result = window.LearningTrainer.train({rowIds:rows.map(row => row._learningId),blocks,answers});
      $("papila-result").textContent = "La distanza rispetta " + result.respected + " delle " + result.total + " scelte.";
      $("papila-weights").innerHTML = result.blocks.map(block => '<tr><th scope="row">' + escape(block.label) + ' · ' + escape(block.measureLabel) + '</th><td>' + (100 * block.weight).toFixed(1) + '%</td></tr>').join("");
      $("papila-reference").innerHTML = rows.map((row,index) => '<option value="' + index + '">' + escape(row.patient_id) + '</option>').join("");
      const showRanking = () => {
        const index = Number($("papila-reference").value);
        const ordered = rows.map((row,j) => ({row,rank:result.rankMatrix[index][j]}))
          .filter(item => item.row !== rows[index]).sort((a,b) => a.rank - b.rank).slice(0,10);
        $("papila-nearest").innerHTML = ordered.map(({row,rank}) => '<li><button type="button" data-patient-index="' + rows.indexOf(row) + '">' + escape(row.patient_id) + '</button> · rango ' + rank + '</li>').join("");
        $("papila-nearest-card").innerHTML = "";
      };
      $("papila-reference").onchange = showRanking;
      $("papila-ranking").hidden = false;
      showRanking();
    } catch (error) { $("papila-result").textContent = error.message; $("papila-weights").innerHTML = ""; $("papila-ranking").hidden = true; }
  });
  $("papila-restart").addEventListener("click", () => { $("papila-setup").hidden = false; $("papila-completion").hidden = true; setup(); });
  $("papila-nearest").addEventListener("click", event => {
    const button = event.target.closest("button[data-patient-index]");
    if (button) $("papila-nearest-card").innerHTML = card(rows[Number(button.dataset.patientIndex)]);
  });
  setup();
})();
