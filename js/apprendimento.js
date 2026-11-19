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
  const state = {step: 0, selected: new Set(), answers: [], current: [], usedTriples: new Set(), seed: 1947};
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

  function measures(labels, values, units) {
    return labels.map((label, index) =>
      '<div><dt>' + label + '</dt><dd>' + values[index] + (units[index] ? ' ' + units[index] : '') + '</dd></div>'
    ).join("");
  }

  function cardHtml(item, position) {
    return '<button class="candidate-card" type="button" data-id="' + item.id +
      '" aria-pressed="false" aria-label="Persona ' + (position + 1) +
      ', seleziona come parte della coppia più simile">' +
      '<span class="selection-mark" aria-hidden="true">✓</span>' +
      '<span class="candidate-content">' +
      '<span class="candidate-title">Persona ' + (position + 1) + '</span>' +
      '<span class="measure-group"><span class="measure-group-title">Esercizi</span><dl class="measure-list">' +
      measures(["Trazioni","Addominali","Salti"], item.exercise, ["","",""]) +
      '</dl></span>' +
      '<span class="measure-group"><span class="measure-group-title">Misure fisiologiche</span><dl class="measure-list">' +
      measures(["Peso","Vita","Frequenza cardiaca"], item.physiological, ["lb","in","bpm"]) +
      '</dl></span></span></button>';
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

  $("confirm-scaling").addEventListener("click", () => {
    $("confirm-scaling").disabled = true;
    $("confirm-scaling").textContent = "Riscalamento confermato";
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

  $("continue-comparisons").addEventListener("click", () => {
    $("batch-card").hidden = true;
    renderStep();
    showStage("comparison-stage");
  });

  $("stop-comparisons").addEventListener("click", () => {
    $("batch-card").hidden = true;
    $("completion-title").textContent = "Raccolta conclusa dopo " + state.step + " scelte";
    showStage("completion-card");
  });

  $("restart-comparisons").addEventListener("click", () => {
    state.step = 0;
    state.answers = [];
    state.usedTriples.clear();
    state.selected.clear();
    state.seed = 1947;
    $("completion-card").hidden = true;
    renderStep();
    showStage("comparison-stage");
  });
})();
