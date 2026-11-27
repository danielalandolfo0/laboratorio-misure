"use strict";

(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[character]);
  let rows = [], numeric = [], selected = new Set(), current = [], answers = [], step = 0;
  const IMAGE_BASE = "https://raw.githubusercontent.com/JuanitoOrtega/papila_db/main/DB_PAPILA/FundusImages/";
  let seed = 1937, used = new Set();
  let chosenGroups = [];

  function groupsFor(keys) {
    const groups = new Map();
    for (const key of keys) {
      const match = key.match(/^(.*)_(OD|OS)$/);
      const name = match ? match[1] : key;
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(key);
    }
    return [...groups].map(([name,columns]) => ({name,columns}));
  }
  function renderMeasureChoices() {
    const keys = [...$("papila-features").querySelectorAll(".papila-use:checked")].map(input => input.dataset.key);
    const previous = new Map([...$("papila-measures").querySelectorAll("select")].map(select => [select.dataset.group,select.value]));
    $("papila-measures").innerHTML = groupsFor(keys).map(({name,columns}) => {
      const binary = columns.every(key => rows.every(row => row[key] === "" || row[key] === "0" || row[key] === "1"));
      const choices = binary ? [["hamming","Stati uguali o diversi (Hamming)"]] : columns.length === 1
        ? [["manhattan","Scarto assoluto"]]
        : [["euclidean","Scarti combinati (Euclidea)"],["manhattan","Somma degli scarti (Manhattan)"],["chebyshev","Scarto maggiore (Chebyshev)"]];
      const selected = choices.some(([id]) => id === previous.get(name)) ? previous.get(name) : choices[0][0];
      return '<label><strong>' + escape(name) + '</strong><br><small>' + columns.map(escape).join(' · ') + '</small><br><select data-group="' + escape(name) + '">' + choices.map(([id,label]) => '<option value="' + id + '"' + (id === selected ? ' selected' : '') + '>' + label + '</option>').join('') + '</select></label>';
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
      $("papila-features").innerHTML = numeric.map(key => {
        const complete = rows.filter(row => row[key] !== "").length / rows.length;
        const suggested = complete >= .9 && !/^Gender_/.test(key) && !/^astigmatism_/.test(key);
        return '<label><strong>' + escape(key) + '</strong> · ' + Math.round(complete * 100) + '% presente<br><input type="checkbox" class="papila-use" data-key="' + escape(key) + '"' + (suggested ? ' checked' : '') + '> Usa nella distanza<br><input type="checkbox" class="papila-show" data-key="' + escape(key) + '"' + (suggested ? ' checked' : '') + '> Mostra nella scheda</label>';
      }).join("");
      $("papila-options").hidden = false;
      renderMeasureChoices();
      $("papila-count").textContent = rows.length + " pazienti, " + numeric.length + " colonne numeriche disponibili.";
      report("");
    }).catch(error => { rows = []; $("papila-options").hidden = true; $("papila-count").textContent = ""; report(error.message); });
  }
  $("papila-features").addEventListener("change", event => {
    if (event.target.matches(".papila-use")) renderMeasureChoices();
  });

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
    const pictures = $("papila-show-images").checked ? ["OD","OS"].map(eye => {
      const filename = row["image_" + eye];
      return '<figure><img loading="lazy" src="' + escape(IMAGE_BASE + encodeURIComponent(filename)) + '" alt="Fondo oculare ' + eye + '"><figcaption>Occhio ' + eye + '</figcaption></figure>';
    }).join("") : "";
    return '<button type="button" class="candidate-card papila-card" data-id="' + row._learningId + '" aria-pressed="false"><span class="candidate-content"><strong>' + escape(row.patient_id) + '</strong><span class="papila-images">' + pictures + '</span>' + shown.map(key => '<span class="measure-group"><strong>' + escape(key) + ':</strong> ' + escape(row[key] || "—") + '</span>').join("") + '</span></button>';
  }
  function render() {
    current = triple(); selected = new Set();
    $("papila-progress").textContent = "Confronto " + (step + 1) + " di 10";
    $("papila-candidates").innerHTML = current.map(card).join("");
    $("papila-next").disabled = true;
  }
  $("papila-start").addEventListener("click", () => {
    const keys = [...$("papila-features").querySelectorAll(".papila-use:checked")].map(input => input.dataset.key);
    if (!keys.length) return report("Seleziona almeno una misura per la distanza.");
    const complete = rows.filter(row => keys.every(key => row[key] !== "" && Number.isFinite(Number(row[key]))));
    if (complete.length < 3) return report("Con queste colonne restano meno di tre pazienti con dati completi.");
    rows = complete; rows.forEach((row,index) => { row._learningId = index + 1; });
    chosenGroups = groupsFor(keys).map(group => ({...group,measure:$("papila-measures").querySelectorAll("select").length
      ? [...$("papila-measures").querySelectorAll("select")].find(select => select.dataset.group === group.name)?.value : "manhattan"}));
    numeric = keys; answers = []; step = 0; used.clear(); report("");
    $("papila-setup").hidden = true; $("papila-completion").hidden = true;
    $("papila-comparison").hidden = false; render();
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
          const low = Math.min(...values), span = Math.max(...values) - low;
          return values.map(value => span ? (value - low) / span : 0);
        });
        return {id:group.name,label:group.name,candidateMeasures:[group.measure],vectors:rows.map((_,i) => columns.map(column => column[i]))};
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
