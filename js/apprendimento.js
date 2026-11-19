"use strict";

(() => {
  const IRIS = [{"id":1,"v":[5.1,3.5,1.4,0.2]},{"id":2,"v":[4.9,3.0,1.4,0.2]},{"id":3,"v":[4.7,3.2,1.3,0.2]},{"id":4,"v":[4.6,3.1,1.5,0.2]},{"id":5,"v":[5.0,3.6,1.4,0.2]},{"id":6,"v":[5.4,3.9,1.7,0.4]},{"id":7,"v":[4.6,3.4,1.4,0.3]},{"id":8,"v":[5.0,3.4,1.5,0.2]},{"id":9,"v":[4.4,2.9,1.4,0.2]},{"id":10,"v":[4.9,3.1,1.5,0.1]},{"id":11,"v":[5.4,3.7,1.5,0.2]},{"id":12,"v":[4.8,3.4,1.6,0.2]},{"id":13,"v":[4.8,3.0,1.4,0.1]},{"id":14,"v":[4.3,3.0,1.1,0.1]},{"id":15,"v":[5.8,4.0,1.2,0.2]},{"id":16,"v":[5.7,4.4,1.5,0.4]},{"id":17,"v":[5.4,3.9,1.3,0.4]},{"id":18,"v":[5.1,3.5,1.4,0.3]},{"id":19,"v":[5.7,3.8,1.7,0.3]},{"id":20,"v":[5.1,3.8,1.5,0.3]},{"id":21,"v":[5.4,3.4,1.7,0.2]},{"id":22,"v":[5.1,3.7,1.5,0.4]},{"id":23,"v":[4.6,3.6,1.0,0.2]},{"id":24,"v":[5.1,3.3,1.7,0.5]},{"id":25,"v":[4.8,3.4,1.9,0.2]},{"id":26,"v":[5.0,3.0,1.6,0.2]},{"id":27,"v":[5.0,3.4,1.6,0.4]},{"id":28,"v":[5.2,3.5,1.5,0.2]},{"id":29,"v":[5.2,3.4,1.4,0.2]},{"id":30,"v":[4.7,3.2,1.6,0.2]},{"id":31,"v":[4.8,3.1,1.6,0.2]},{"id":32,"v":[5.4,3.4,1.5,0.4]},{"id":33,"v":[5.2,4.1,1.5,0.1]},{"id":34,"v":[5.5,4.2,1.4,0.2]},{"id":35,"v":[4.9,3.1,1.5,0.2]},{"id":36,"v":[5.0,3.2,1.2,0.2]},{"id":37,"v":[5.5,3.5,1.3,0.2]},{"id":38,"v":[4.9,3.6,1.4,0.1]},{"id":39,"v":[4.4,3.0,1.3,0.2]},{"id":40,"v":[5.1,3.4,1.5,0.2]},{"id":41,"v":[5.0,3.5,1.3,0.3]},{"id":42,"v":[4.5,2.3,1.3,0.3]},{"id":43,"v":[4.4,3.2,1.3,0.2]},{"id":44,"v":[5.0,3.5,1.6,0.6]},{"id":45,"v":[5.1,3.8,1.9,0.4]},{"id":46,"v":[4.8,3.0,1.4,0.3]},{"id":47,"v":[5.1,3.8,1.6,0.2]},{"id":48,"v":[4.6,3.2,1.4,0.2]},{"id":49,"v":[5.3,3.7,1.5,0.2]},{"id":50,"v":[5.0,3.3,1.4,0.2]},{"id":51,"v":[7.0,3.2,4.7,1.4]},{"id":52,"v":[6.4,3.2,4.5,1.5]},{"id":53,"v":[6.9,3.1,4.9,1.5]},{"id":54,"v":[5.5,2.3,4.0,1.3]},{"id":55,"v":[6.5,2.8,4.6,1.5]},{"id":56,"v":[5.7,2.8,4.5,1.3]},{"id":57,"v":[6.3,3.3,4.7,1.6]},{"id":58,"v":[4.9,2.4,3.3,1.0]},{"id":59,"v":[6.6,2.9,4.6,1.3]},{"id":60,"v":[5.2,2.7,3.9,1.4]},{"id":61,"v":[5.0,2.0,3.5,1.0]},{"id":62,"v":[5.9,3.0,4.2,1.5]},{"id":63,"v":[6.0,2.2,4.0,1.0]},{"id":64,"v":[6.1,2.9,4.7,1.4]},{"id":65,"v":[5.6,2.9,3.6,1.3]},{"id":66,"v":[6.7,3.1,4.4,1.4]},{"id":67,"v":[5.6,3.0,4.5,1.5]},{"id":68,"v":[5.8,2.7,4.1,1.0]},{"id":69,"v":[6.2,2.2,4.5,1.5]},{"id":70,"v":[5.6,2.5,3.9,1.1]},{"id":71,"v":[5.9,3.2,4.8,1.8]},{"id":72,"v":[6.1,2.8,4.0,1.3]},{"id":73,"v":[6.3,2.5,4.9,1.5]},{"id":74,"v":[6.1,2.8,4.7,1.2]},{"id":75,"v":[6.4,2.9,4.3,1.3]},{"id":76,"v":[6.6,3.0,4.4,1.4]},{"id":77,"v":[6.8,2.8,4.8,1.4]},{"id":78,"v":[6.7,3.0,5.0,1.7]},{"id":79,"v":[6.0,2.9,4.5,1.5]},{"id":80,"v":[5.7,2.6,3.5,1.0]},{"id":81,"v":[5.5,2.4,3.8,1.1]},{"id":82,"v":[5.5,2.4,3.7,1.0]},{"id":83,"v":[5.8,2.7,3.9,1.2]},{"id":84,"v":[6.0,2.7,5.1,1.6]},{"id":85,"v":[5.4,3.0,4.5,1.5]},{"id":86,"v":[6.0,3.4,4.5,1.6]},{"id":87,"v":[6.7,3.1,4.7,1.5]},{"id":88,"v":[6.3,2.3,4.4,1.3]},{"id":89,"v":[5.6,3.0,4.1,1.3]},{"id":90,"v":[5.5,2.5,4.0,1.3]},{"id":91,"v":[5.5,2.6,4.4,1.2]},{"id":92,"v":[6.1,3.0,4.6,1.4]},{"id":93,"v":[5.8,2.6,4.0,1.2]},{"id":94,"v":[5.0,2.3,3.3,1.0]},{"id":95,"v":[5.6,2.7,4.2,1.3]},{"id":96,"v":[5.7,3.0,4.2,1.2]},{"id":97,"v":[5.7,2.9,4.2,1.3]},{"id":98,"v":[6.2,2.9,4.3,1.3]},{"id":99,"v":[5.1,2.5,3.0,1.1]},{"id":100,"v":[5.7,2.8,4.1,1.3]},{"id":101,"v":[6.3,3.3,6.0,2.5]},{"id":102,"v":[5.8,2.7,5.1,1.9]},{"id":103,"v":[7.1,3.0,5.9,2.1]},{"id":104,"v":[6.3,2.9,5.6,1.8]},{"id":105,"v":[6.5,3.0,5.8,2.2]},{"id":106,"v":[7.6,3.0,6.6,2.1]},{"id":107,"v":[4.9,2.5,4.5,1.7]},{"id":108,"v":[7.3,2.9,6.3,1.8]},{"id":109,"v":[6.7,2.5,5.8,1.8]},{"id":110,"v":[7.2,3.6,6.1,2.5]},{"id":111,"v":[6.5,3.2,5.1,2.0]},{"id":112,"v":[6.4,2.7,5.3,1.9]},{"id":113,"v":[6.8,3.0,5.5,2.1]},{"id":114,"v":[5.7,2.5,5.0,2.0]},{"id":115,"v":[5.8,2.8,5.1,2.4]},{"id":116,"v":[6.4,3.2,5.3,2.3]},{"id":117,"v":[6.5,3.0,5.5,1.8]},{"id":118,"v":[7.7,3.8,6.7,2.2]},{"id":119,"v":[7.7,2.6,6.9,2.3]},{"id":120,"v":[6.0,2.2,5.0,1.5]},{"id":121,"v":[6.9,3.2,5.7,2.3]},{"id":122,"v":[5.6,2.8,4.9,2.0]},{"id":123,"v":[7.7,2.8,6.7,2.0]},{"id":124,"v":[6.3,2.7,4.9,1.8]},{"id":125,"v":[6.7,3.3,5.7,2.1]},{"id":126,"v":[7.2,3.2,6.0,1.8]},{"id":127,"v":[6.2,2.8,4.8,1.8]},{"id":128,"v":[6.1,3.0,4.9,1.8]},{"id":129,"v":[6.4,2.8,5.6,2.1]},{"id":130,"v":[7.2,3.0,5.8,1.6]},{"id":131,"v":[7.4,2.8,6.1,1.9]},{"id":132,"v":[7.9,3.8,6.4,2.0]},{"id":133,"v":[6.4,2.8,5.6,2.2]},{"id":134,"v":[6.3,2.8,5.1,1.5]},{"id":135,"v":[6.1,2.6,5.6,1.4]},{"id":136,"v":[7.7,3.0,6.1,2.3]},{"id":137,"v":[6.3,3.4,5.6,2.4]},{"id":138,"v":[6.4,3.1,5.5,1.8]},{"id":139,"v":[6.0,3.0,4.8,1.8]},{"id":140,"v":[6.9,3.1,5.4,2.1]},{"id":141,"v":[6.7,3.1,5.6,2.4]},{"id":142,"v":[6.9,3.1,5.1,2.3]},{"id":143,"v":[5.8,2.7,5.1,1.9]},{"id":144,"v":[6.8,3.2,5.9,2.3]},{"id":145,"v":[6.7,3.3,5.7,2.5]},{"id":146,"v":[6.7,3.0,5.2,2.3]},{"id":147,"v":[6.3,2.5,5.0,1.9]},{"id":148,"v":[6.5,3.0,5.2,2.0]},{"id":149,"v":[6.2,3.4,5.4,2.3]},{"id":150,"v":[5.9,3.0,5.1,1.8]}];
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
      while (ids.size < 3) ids.add(Math.floor(random() * IRIS.length));
      const indices = [...ids];
      const key = [...indices].sort((a,b) => a-b).join("-");
      if (!state.usedTriples.has(key)) {
        state.usedTriples.add(key);
        return indices.map(i => IRIS[i]);
      }
    }
    return [...IRIS].sort(() => random() - .5).slice(0, 3);
  }

  function flowerSvg(values) {
    const [sepalLength, sepalWidth, petalLength, petalWidth] = values;
    const sepalRx = 18 + sepalLength * 3.2;
    const sepalRy = 8 + sepalWidth * 3.4;
    const petalRx = 11 + petalLength * 4.7;
    const petalRy = 5 + petalWidth * 9.2;
    const petals = [0, 60, 120, 180, 240, 300].map(angle =>
      '<ellipse class="petal" cx="90" cy="39" rx="' + petalRy.toFixed(1) +
      '" ry="' + petalRx.toFixed(1) + '" transform="rotate(' + angle + ' 90 90)"/>'
    ).join("");
    const sepals = [30, 150, 270].map(angle =>
      '<ellipse class="sepal" cx="90" cy="47" rx="' + sepalRy.toFixed(1) +
      '" ry="' + sepalRx.toFixed(1) + '" transform="rotate(' + angle + ' 90 90)"/>'
    ).join("");
    return '<svg viewBox="0 0 180 180" aria-hidden="true">' + sepals + petals +
      '<circle class="center" cx="90" cy="90" r="13"/></svg>';
  }

  function cardHtml(item, position) {
    const v = item.v;
    return '<button class="candidate-card" type="button" data-id="' + item.id +
      '" aria-pressed="false" aria-label="Candidato ' + (position + 1) +
      ', seleziona come parte della coppia più simile">' +
      '<span class="selection-mark" aria-hidden="true">✓</span>' +
      '<span class="flower-visual">' + flowerSvg(v) + '</span>' +
      '<span class="candidate-content">' +
      '<span class="candidate-title">Candidato ' + (position + 1) + '</span>' +
      '<dl class="measure-list">' +
      '<div><dt>Lunghezza sepalo</dt><dd>' + v[0].toFixed(1) + ' cm</dd></div>' +
      '<div><dt>Larghezza sepalo</dt><dd>' + v[1].toFixed(1) + ' cm</dd></div>' +
      '<div><dt>Lunghezza petalo</dt><dd>' + v[2].toFixed(1) + ' cm</dd></div>' +
      '<div><dt>Larghezza petalo</dt><dd>' + v[3].toFixed(1) + ' cm</dd></div>' +
      '</dl></span></button>';
  }

  function updateSelection() {
    const count = state.selected.size;
    $("selection-help").textContent = count === 2
      ? "Hai selezionato due schede. Ora puoi confermare e continuare."
      : "Hai selezionato " + count + " schede su 2.";
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
    document.querySelector(".candidate-card")?.focus({preventScroll: true});
  }

  function toggleCard(card) {
    const id = Number(card.dataset.id);
    if (state.selected.has(id)) state.selected.delete(id);
    else if (state.selected.size < 2) state.selected.add(id);
    updateSelection();
  }

  $("candidate-grid").addEventListener("click", event => {
    const card = event.target.closest(".candidate-card");
    if (card) toggleCard(card);
  });

  $("next-comparison").addEventListener("click", () => {
    if (state.selected.size !== 2) return;
    const chosen = [...state.selected];
    const excluded = state.current.find(item => !state.selected.has(item.id)).id;
    state.answers.push({
      step: state.step + 1,
      candidates: state.current.map(item => item.id),
      chosen,
      excluded
    });
    state.step++;
    if (state.step % BATCH_SIZE === 0) {
      $("comparison-stage").hidden = true;
      $("batch-title").textContent =
        "Hai effettuato " + state.step + (state.step === 1 ? " scelta" : " scelte");
      $("batch-card").hidden = false;
      return;
    }
    renderStep();
    $("comparison-stage").scrollIntoView({behavior: "smooth", block: "start"});
  });

  $("continue-comparisons").addEventListener("click", () => {
    $("batch-card").hidden = true;
    $("comparison-stage").hidden = false;
    renderStep();
    $("comparison-stage").scrollIntoView({behavior: "smooth", block: "start"});
  });

  $("stop-comparisons").addEventListener("click", () => {
    $("batch-card").hidden = true;
    $("completion-title").textContent =
      "Raccolta conclusa dopo " + state.step + (state.step === 1 ? " scelta" : " scelte");
    $("completion-card").hidden = false;
  });

  $("restart-comparisons").addEventListener("click", () => {
    state.step = 0;
    state.answers = [];
    state.usedTriples.clear();
    state.selected.clear();
    state.seed = 1947;
    $("completion-card").hidden = true;
    $("batch-card").hidden = true;
    $("comparison-stage").hidden = false;
    renderStep();
    $("comparison-stage").scrollIntoView({behavior: "smooth", block: "start"});
  });

  renderStep();
})();

