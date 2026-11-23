"use strict";

(() => {
  const LINNERUD = [
    {id:1, exercise:[5,162,60], physiological:[191,36,50]},
    {id:2, exercise:[2,110,60], physiological:[189,37,52]},
    {id:3, exercise:[12,101,101], physiological:[193,38,58]},
    {id:4, exercise:[12,105,37], physiological:[162,35,62]},
    {id:5, exercise:[13,155,58], physiological:[189,35,46]},
    {id:6, exercise:[4,101,42], physiological:[182,36,56]},
    {id:7, exercise:[8,101,38], physiological:[211,38,56]},
    {id:8, exercise:[6,125,40], physiological:[167,34,60]},
    {id:9, exercise:[15,200,40], physiological:[176,31,74]},
    {id:10, exercise:[17,251,250], physiological:[154,33,56]},
    {id:11, exercise:[17,120,38], physiological:[169,34,50]},
    {id:12, exercise:[13,210,115], physiological:[166,33,52]},
    {id:13, exercise:[14,215,105], physiological:[154,34,64]},
    {id:14, exercise:[1,50,50], physiological:[247,46,50]},
    {id:15, exercise:[6,70,31], physiological:[193,36,46]},
    {id:16, exercise:[12,210,120], physiological:[202,37,62]},
    {id:17, exercise:[4,60,25], physiological:[176,37,54]},
    {id:18, exercise:[11,230,80], physiological:[157,32,52]},
    {id:19, exercise:[15,225,73], physiological:[156,33,54]},
    {id:20, exercise:[2,110,43], physiological:[138,33,68]}
  ];
  const BATCH_SIZE = 10;
  const FEATURES = [
    {key:"chins", label:"Trazioni", field:"exercise", index:0, unit:"", proposedGroup:"exercise"},
    {key:"situps", label:"Addominali", field:"exercise", index:1, unit:"", proposedGroup:"exercise"},
    {key:"jumps", label:"Salti", field:"exercise", index:2, unit:"", proposedGroup:"exercise"},
    {key:"weight", label:"Peso", field:"physiological", index:0, unit:"lb", proposedGroup:"physiological"},
    {key:"waist", label:"Circonferenza vita", field:"physiological", index:1, unit:"in", proposedGroup:"physiological"},
    {key:"pulse", label:"Frequenza cardiaca", field:"physiological", index:2, unit:"bpm", proposedGroup:"physiological"}
  ];
  const state = {step: 0, selected: new Set(), answers: [], current: [], usedTriples: new Set(), seed: 1947};
  state.assignments = Object.fromEntries(FEATURES.map(feature => [feature.key, feature.proposedGroup]));
  state.scaling = {exercise:"zscore", physiological:"zscore"};
  state.semanticAnswers = {};
  state.candidateMeasures = [];
  const MEASURE_CATALOG = window.LearningMeasureCatalog;
  const $ = id => document.getElementById(id);

  function random() {
    state.seed = (1664525 * state.seed + 1013904223) >>> 0;
    return state.seed / 4294967296;
  }

  function sampleTriple() {
    for (let attempt = 0; attempt < 1000; attempt++) {
      const ids = new Set();
      while (ids.size < 3) ids.add(Math.floor(random() * LINNERUD.length));
      const indices = [...ids];
      const key = [...indices].sort((a,b) => a-b).join("-");
      if (!state.usedTriples.has(key)) {
        state.usedTriples.add(key);
        return indices.map(i => LINNERUD[i]);
      }
    }
    return [...LINNERUD].sort(() => random() - .5).slice(0, 3);
  }

  function featureValues(feature) {
    return LINNERUD.map(row => row[feature.field][feature.index]);
  }

  function mean(values) {
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }

  function percentile(values, p) {
    const sorted = [...values].sort((a,b) => a-b);
    const position = (sorted.length - 1) * p;
    const lower = Math.floor(position);
    const fraction = position - lower;
    return sorted[lower] + (sorted[lower + 1] === undefined ? 0 : fraction * (sorted[lower + 1] - sorted[lower]));
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("it-IT", {maximumFractionDigits:2}).format(value);
  }

  function scalingParameters(feature, method) {
    const values = featureValues(feature);
    if (method === "zscore") {
      const average = mean(values);
      const deviation = Math.sqrt(values.reduce((sum, value) => sum + (value - average) ** 2, 0) / values.length);
      return "media " + formatNumber(average) + " · σ " + formatNumber(deviation);
    }
    if (method === "robust") {
      const q1 = percentile(values, .25);
      const q3 = percentile(values, .75);
      return "mediana " + formatNumber(percentile(values, .5)) + " · IQR " + formatNumber(q3 - q1);
    }
    if (method === "minmax") return "min " + Math.min(...values) + " · max " + Math.max(...values);
    if (method === "maxabs") return "max |x| " + Math.max(...values.map(Math.abs));
    return "—";
  }

  function scaledFeatureValues(feature, method) {
    const values = featureValues(feature);
    if (method === "zscore") {
      const average = mean(values);
      const deviation = Math.sqrt(values.reduce((total,value) => total + (value - average) ** 2, 0) / values.length);
      return values.map(value => deviation ? (value - average) / deviation : 0);
    }
    if (method === "robust") {
      const median = percentile(values,.5);
      const range = percentile(values,.75) - percentile(values,.25);
      return values.map(value => range ? (value - median) / range : 0);
    }
    if (method === "minmax") {
      const minimum = Math.min(...values), range = Math.max(...values) - minimum;
      return values.map(value => range ? (value - minimum) / range : 0);
    }
    if (method === "maxabs") {
      const maximum = Math.max(...values.map(Math.abs));
      return values.map(value => maximum ? value / maximum : 0);
    }
    return [...values];
  }

  function renderGroupAssignments() {
    $("learning-group-assignment-body").innerHTML = FEATURES.map(feature =>
      '<tr><th scope="row">' + feature.label + '</th><td><select class="column-choice learning-group-assignment" data-feature="' + feature.key + '" aria-label="Gruppo della colonna ' + feature.label + '">' +
      '<option value="independent"' + (state.assignments[feature.key] === "independent" ? " selected" : "") + '>Caratteristica indipendente</option>' +
      '<option value="exercise"' + (state.assignments[feature.key] === "exercise" ? " selected" : "") + '>Esercizi</option>' +
      '<option value="physiological"' + (state.assignments[feature.key] === "physiological" ? " selected" : "") + '>Misure fisiologiche</option>' +
      '</select></td></tr>'
    ).join("");
  }

  function renderScalingTable() {
    const groups = activeGroups();
    $("block-scaling-controls").innerHTML = groups.map(group =>
      '<label class="block-scaling-choice">' + group.label +
      '<select class="column-choice" data-group="' + group.key + '" aria-label="Riscalamento del blocco ' + group.label + '">' +
      '<option value="zscore"' + (state.scaling[group.key] === "zscore" ? " selected" : "") + '>Z-score (suggerito)</option>' +
      '<option value="robust"' + (state.scaling[group.key] === "robust" ? " selected" : "") + '>Robusto: mediana e IQR</option>' +
      '<option value="minmax"' + (state.scaling[group.key] === "minmax" ? " selected" : "") + '>Min–max</option>' +
      '<option value="maxabs"' + (state.scaling[group.key] === "maxabs" ? " selected" : "") + '>Max-abs</option>' +
      '<option value="none"' + (state.scaling[group.key] === "none" ? " selected" : "") + '>Valori originali</option>' +
      '</select></label>'
    ).join("");
    $("learning-scaling-body").innerHTML = FEATURES.map(feature => {
      const group = groups.find(candidate => candidate.features.includes(feature));
      const method = state.scaling[group.key];
      const names = {zscore:"Z-score", robust:"Robusto", minmax:"Min–max", maxabs:"Max-abs", none:"Originale"};
      return '<tr><td>' + group.label + '</td><th scope="row">' + feature.label + '</th><td>' + names[method] +
        '</td><td><span class="method-params">' + scalingParameters(feature, method) + '</span></td></tr>';
    }).join("");
  }

  function activeGroups() {
    const groups = [
      {key:"exercise", label:"Esercizi", features:FEATURES.filter(f => state.assignments[f.key] === "exercise")},
      {key:"physiological", label:"Misure fisiologiche", features:FEATURES.filter(f => state.assignments[f.key] === "physiological")}
    ].filter(group => group.features.length);
    for (const feature of FEATURES.filter(f => state.assignments[f.key] === "independent")) {
      groups.push({key:feature.key, label:feature.label + " (indipendente)", features:[feature]});
    }
    for (const group of groups) state.scaling[group.key] ??= "zscore";
    return groups;
  }

  function answerChoices(groupKey, questionKey, question, choices) {
    const selected = state.semanticAnswers[groupKey]?.[questionKey] || "";
    return '<fieldset class="meaning-question"><legend>' + question + '</legend><div class="meaning-options">' +
      choices.map(choice => '<label><input type="radio" name="' + groupKey + '-' + questionKey + '" data-group="' +
        groupKey + '" data-question="' + questionKey + '" value="' + choice.value + '"' +
        (selected === choice.value ? " checked" : "") + '><span>' + choice.label + '</span></label>').join("") +
      '</div></fieldset>';
  }

  const YES_NO_UNSURE = [
    {value:"yes", label:"Sì"},
    {value:"no", label:"No"},
    {value:"unsure", label:"Non sono sicuro"}
  ];

  function renderMeaningControls() {
    $("meaning-controls").innerHTML = activeGroups().map(group => {
      state.semanticAnswers[group.key] ??= {};
      const answers = state.semanticAnswers[group.key];
      let questions = "";
      if (group.features.length === 1) {
        questions = '<p class="single-column-note">Questo blocco contiene una sola colonna: non servono altre domande.</p>';
      } else {
        questions += answerChoices(group.key, "parts",
          "Queste colonne sono parti o percentuali di uno stesso totale?", YES_NO_UNSURE);
        if (answers.parts === "no" || answers.parts === "unsure") {
          questions += answerChoices(group.key, "temporal",
            "Sono la stessa misura osservata in momenti successivi?", YES_NO_UNSURE);
          if (answers.temporal === "yes" || answers.temporal === "unsure") {
            questions += answerChoices(group.key, "alignment",
              "Due andamenti possono essere simili anche se uno avviene un po’ prima o dopo?", [
                {value:"flexible", label:"Sì"},
                {value:"aligned", label:"No, contano gli stessi momenti"},
                {value:"unsure", label:"Non sono sicuro"}
              ]);
          }
          if (answers.temporal === "no" || answers.temporal === "unsure") {
            questions += answerChoices(group.key, "comparisonFocus",
              "Nel confrontare due persone, che cosa dovrebbe essere simile in questo gruppo di caratteristiche?", [
                {value:"values", label:"I valori delle singole caratteristiche"},
                {value:"ratio", label:"Le proporzioni tra le caratteristiche"},
                {value:"unsure", label:"Non sono sicuro"}
              ]);
            if (answers.comparisonFocus) questions += answerChoices(group.key, "abundance",
              "In queste colonne, lo zero significa che quella caratteristica è assente?", YES_NO_UNSURE);
          }
        }
      }
      return '<section class="meaning-item" data-meaning-group="' + group.key + '">' +
        '<h3>' + group.label + '</h3><p class="meaning-columns">' +
        group.features.map(feature => feature.label).join(", ") + '</p>' + questions + '</section>';
    }).join("");
    updateMeaningConfirm();
  }

  function hasFullRank(group) {
    const rows = LINNERUD.map(row => group.features.map(feature => row[feature.field][feature.index]));
    const averages = group.features.map((_, column) => mean(rows.map(row => row[column])));
    const matrix = group.features.map((_, i) => group.features.map((__, j) =>
      rows.reduce((sum, row) => sum + (row[i] - averages[i]) * (row[j] - averages[j]), 0)));
    let rank = 0;
    for (let col = 0; col < group.features.length; col++) {
      let pivot = rank;
      for (let row = rank + 1; row < group.features.length; row++)
        if (Math.abs(matrix[row][col]) > Math.abs(matrix[pivot][col])) pivot = row;
      if (Math.abs(matrix[pivot][col]) < 1e-8) continue;
      [matrix[rank], matrix[pivot]] = [matrix[pivot], matrix[rank]];
      const value = matrix[rank][col];
      for (let j = col; j < group.features.length; j++) matrix[rank][j] /= value;
      for (let row = rank + 1; row < group.features.length; row++) {
        const factor = matrix[row][col];
        for (let j = col; j < group.features.length; j++) matrix[row][j] -= factor * matrix[rank][j];
      }
      rank++;
    }
    return rank === group.features.length;
  }

  function addMeasures(target, catalogKey) {
    for (const measure of MEASURE_CATALOG[catalogKey].measures) target.add(measure);
  }

  function semanticCandidates(group, answers) {
    const measures = new Set();
    if (group.features.length === 1) {
      addMeasures(measures, "numeric");
      return measures;
    }
    if (answers.parts === "yes" || answers.parts === "unsure") addMeasures(measures, "parts");
    if (answers.parts === "yes") return measures;

    if (answers.temporal === "yes" || answers.temporal === "unsure") {
      if (answers.alignment === "aligned" || answers.alignment === "unsure") addMeasures(measures, "temporal_aligned");
      if (answers.alignment === "flexible" || answers.alignment === "unsure") addMeasures(measures, "temporal_flexible");
    }
    if (answers.temporal === "yes") return measures;

    addMeasures(measures, "profile_trend");
    if (answers.comparisonFocus === "values" || answers.comparisonFocus === "unsure") addMeasures(measures, "numeric");
    if (answers.comparisonFocus === "ratio" || answers.comparisonFocus === "unsure") addMeasures(measures, "profile_ratio");
    if (answers.abundance === "yes" || answers.abundance === "unsure") addMeasures(measures, "abundance");
    return measures;
  }

  function candidatesFor(group, answers) {
    const values = group.features.flatMap(featureValues);
    let measures = [...semanticCandidates(group, answers)];
    if (group.features.length === 1) measures = measures.filter(id => !["chebyshev","minkowski","mahalanobis"].includes(id));
    if (values.some(value => value < 0)) measures = measures.filter(id => !["canberra","braycurtis","hellinger","jensen_shannon","aitchison"].includes(id));
    if (values.some(value => value <= 0)) measures = measures.filter(id => id !== "aitchison");
    if (group.features.length > 1 && (LINNERUD.length <= group.features.length || !hasFullRank(group)))
      measures = measures.filter(id => id !== "mahalanobis");
    const rows = LINNERUD.map(row => group.features.map(feature => row[feature.field][feature.index]));
    if (rows.some(row => row.every(value => value === 0))) measures = measures.filter(id => id !== "cosine");
    if (rows.some(row => row.every(value => value === row[0]))) measures = measures.filter(id => id !== "correlation");
    return measures;
  }

  function missingAnswer(group, answers) {
    if (group.features.length === 1) return null;
    if (!answers.parts) return "la prima domanda";
    if (answers.parts === "yes") return null;
    if (!answers.temporal) return "la domanda sui momenti successivi";
    if (["yes","unsure"].includes(answers.temporal) && !answers.alignment) return "la domanda sullo spostamento nel tempo";
    if (answers.temporal === "yes") return null;
    if (!answers.comparisonFocus) return "la domanda su che cosa dovrebbe essere simile";
    if (!answers.abundance) return "la domanda sul significato dello zero";
    return null;
  }

  function updateMeaningConfirm() {
    $("confirm-meaning").disabled = activeGroups().some(group =>
      missingAnswer(group, state.semanticAnswers[group.key] || {}));
  }

  function confirmMeaning() {
    const entries = [];
    for (const group of activeGroups()) {
      const answers = state.semanticAnswers[group.key] || {};
      const missing = missingAnswer(group, answers);
      if (missing) return 'Completa ' + missing + ' nel blocco “' + group.label + '”.';
      const measures = candidatesFor(group, answers);
      if (!measures.length) return 'Nessuna misura candidata per il blocco “' + group.label + '”.';
      entries.push({id:group.key, label:group.label, columns:group.features.map(feature => feature.key),
        semanticAnswers:{...answers}, scaling:state.scaling[group.key], candidateMeasures:measures});
    }
    state.candidateMeasures = entries;
    try {
      sessionStorage.setItem("laboratorio-misure:apprendimento-config:v1", JSON.stringify({dataset:"linnerud", blocks:entries}));
    } catch (_) { /* La sessione può non consentire la memorizzazione. */ }
    return null;
  }

  function trainingBlocks() {
    const groups = activeGroups();
    return state.candidateMeasures.map(block => {
      const group = groups.find(candidate => candidate.key === block.id);
      const columns = group.features.map(feature => scaledFeatureValues(feature,block.scaling));
      return {
        id:block.id,
        label:block.label,
        candidateMeasures:block.candidateMeasures,
        vectors:LINNERUD.map((_,row) => columns.map(column => column[row]))
      };
    });
  }

  function renderLearningResult() {
    $("training-status").hidden = false;
    $("training-status").textContent = "Calcolo del risultato…";
    $("training-error").hidden = true;
    $("learning-result").hidden = true;
    try {
      const result = window.LearningTrainer.train({
        rowIds:LINNERUD.map(row => row.id),
        blocks:trainingBlocks(),
        answers:state.answers,
        gamma:.05,
        lambda:.01
      });
      $("result-rate").textContent = new Intl.NumberFormat("it-IT", {style:"percent",maximumFractionDigits:0}).format(result.rate);
      $("result-respected").textContent = result.respected + " su " + result.total + " scelte";
      $("result-measures-body").innerHTML = result.blocks.map(block =>
        '<tr><th scope="row">' + block.label + '</th><td>' + block.measureLabel + '</td><td>' +
        new Intl.NumberFormat("it-IT", {style:"percent",maximumFractionDigits:1}).format(block.weight) + '</td></tr>'
      ).join("");
      $("training-status").hidden = true;
      $("learning-result").hidden = false;
      try {
        sessionStorage.setItem("laboratorio-misure:apprendimento-result:v1", JSON.stringify(result));
      } catch (_) { /* La sessione può non consentire la memorizzazione. */ }
    } catch (error) {
      $("training-status").hidden = true;
      $("training-error").textContent = error.message || "Non è stato possibile calcolare il risultato.";
      $("training-error").hidden = false;
    }
  }

  function measureGroupHtml(title, features, item) {
    if (!features.length) return "";
    return '<span class="measure-group"><span class="measure-group-title">' + title + '</span><dl class="measure-list">' +
      features.map(feature => {
        const value = item[feature.field][feature.index];
        return '<div><dt>' + feature.label + '</dt><dd>' + value + (feature.unit ? ' ' + feature.unit : '') + '</dd></div>';
      }).join("") + '</dl></span>';
  }

  function cardHtml(item, position) {
    const exercises = FEATURES.filter(feature => state.assignments[feature.key] === "exercise");
    const physiological = FEATURES.filter(feature => state.assignments[feature.key] === "physiological");
    const independent = FEATURES.filter(feature => state.assignments[feature.key] === "independent");
    return '<button class="candidate-card" type="button" data-id="' + item.id +
      '" aria-pressed="false" aria-label="Persona ' + (position + 1) +
      ', seleziona come parte della coppia più simile">' +
      '<span class="selection-mark" aria-hidden="true">✓</span>' +
      '<span class="candidate-content">' +
      '<span class="candidate-title">Persona ' + (position + 1) + '</span>' +
      measureGroupHtml("Esercizi", exercises, item) +
      measureGroupHtml("Misure fisiologiche", physiological, item) +
      independent.map(feature => measureGroupHtml(feature.label + " · indipendente", [feature], item)).join("") +
      '</span></button>';
  }

  function showStage(id) {
    const stage = $(id);
    stage.hidden = false;
    stage.scrollIntoView({behavior: "smooth", block: "start"});
  }

  function updateSelection() {
    const count = state.selected.size;
    $("next-comparison").disabled = count !== 2;
    document.querySelectorAll(".candidate-card").forEach(card => {
      const selected = state.selected.has(Number(card.dataset.id));
      card.setAttribute("aria-pressed", selected ? "true" : "false");
      card.classList.toggle("selection-locked", count === 2 && !selected);
    });
  }

  function renderStep() {
    state.current = sampleTriple();
    state.selected.clear();
    $("candidate-grid").innerHTML = state.current.map(cardHtml).join("");
    const positionInBatch = (state.step % BATCH_SIZE) + 1;
    $("comparison-counter").textContent =
      "Confronto " + (state.step + 1) + " · " + positionInBatch + " di " + BATCH_SIZE;
    $("comparison-progress").style.width = ((positionInBatch / BATCH_SIZE) * 100) + "%";
    updateSelection();
  }

  $("confirm-blocks").addEventListener("click", () => {
    $("confirm-blocks").disabled = true;
    $("confirm-blocks").textContent = "Blocchi confermati";
    showStage("scaling-stage");
  });

  $("learning-group-assignment-body").addEventListener("change", event => {
    const select = event.target.closest(".learning-group-assignment");
    if (!select) return;
    state.assignments[select.dataset.feature] = select.value;
    renderScalingTable();
  });

  $("block-scaling-controls").addEventListener("change", event => {
    const select = event.target.closest("select[data-group]");
    if (!select) return;
    state.scaling[select.dataset.group] = select.value;
    renderScalingTable();
  });

  $("confirm-scaling").addEventListener("click", () => {
    $("confirm-scaling").disabled = true;
    $("confirm-scaling").textContent = "Riscalamento confermato";
    renderMeaningControls();
    showStage("meaning-stage");
  });

  $("meaning-controls").addEventListener("change", event => {
    const input = event.target.closest('input[type="radio"][data-question]');
    if (!input) return;
    state.semanticAnswers[input.dataset.group] ??= {};
    const answers = state.semanticAnswers[input.dataset.group];
    answers[input.dataset.question] = input.value;
    const dependants = {
      parts:["temporal","alignment","comparisonFocus","abundance"],
      temporal:["alignment","comparisonFocus","abundance"],
      comparisonFocus:["abundance"]
    };
    for (const key of dependants[input.dataset.question] || []) delete answers[key];
    renderMeaningControls();
    $("meaning-error").hidden = true;
  });

  $("confirm-meaning").addEventListener("click", () => {
    const error = confirmMeaning();
    if (error) {
      $("meaning-error").textContent = error;
      $("meaning-error").hidden = false;
      return;
    }
    $("confirm-meaning").disabled = true;
    $("confirm-meaning").textContent = "Significato confermato";
    renderStep();
    showStage("comparison-stage");
  });

  $("candidate-grid").addEventListener("click", event => {
    const card = event.target.closest(".candidate-card");
    if (!card) return;
    const id = Number(card.dataset.id);
    if (state.selected.has(id)) state.selected.delete(id);
    else if (state.selected.size < 2) state.selected.add(id);
    updateSelection();
  });

  $("next-comparison").addEventListener("click", () => {
    if (state.selected.size !== 2) return;
    const chosen = [...state.selected];
    const excluded = state.current.find(item => !state.selected.has(item.id)).id;
    state.answers.push({step: state.step + 1, candidates: state.current.map(item => item.id), chosen, excluded});
    state.step++;
    if (state.step % BATCH_SIZE === 0) {
      $("comparison-stage").hidden = true;
      $("batch-title").textContent = "Hai effettuato " + state.step + " scelte";
      showStage("batch-card");
      return;
    }
    renderStep();
    $("comparison-stage").scrollIntoView({behavior: "smooth", block: "start"});
  });

  $("skip-comparison").addEventListener("click", () => {
    renderStep();
    $("comparison-stage").scrollIntoView({behavior: "smooth", block: "start"});
  });

  $("continue-comparisons").addEventListener("click", () => {
    $("batch-card").hidden = true;
    renderStep();
    showStage("comparison-stage");
  });

  $("stop-comparisons").addEventListener("click", () => {
    $("batch-card").hidden = true;
    $("completion-title").textContent = "Risultato dopo " + state.step + " scelte";
    showStage("completion-card");
    renderLearningResult();
  });

  $("restart-comparisons").addEventListener("click", () => {
    state.step = 0;
    state.answers = [];
    state.usedTriples.clear();
    state.selected.clear();
    state.seed = 1947;
    $("completion-card").hidden = true;
    $("learning-result").hidden = true;
    $("training-error").hidden = true;
    renderStep();
    showStage("comparison-stage");
  });

  renderGroupAssignments();
  renderScalingTable();
})();
