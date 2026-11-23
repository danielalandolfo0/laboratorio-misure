"use strict";

(() => {
  const LABELS = Object.freeze({
    manhattan:"Manhattan", euclidean:"Euclidea", chebyshev:"Chebyshev",
    minkowski:"Minkowski (p = 3)", mahalanobis:"Mahalanobis", canberra:"Canberra",
    braycurtis:"Bray–Curtis", hellinger:"Hellinger", jensen_shannon:"Jensen–Shannon",
    aitchison:"Aitchison", cosine:"Coseno", correlation:"Correlazione",
    pointwise:"Punto per punto", dtw:"DTW", lcss:"LCSS", hamming:"Hamming",
    jaccard:"Jaccard", matching:"Matching", ordinal_steps:"Livelli ordinati",
    exact:"Confronto esatto", hamming_string:"Hamming", levenshtein:"Levenshtein",
    damerau_levenshtein:"Damerau–Levenshtein", gower:"Gower"
  });

  const dot = (a,b) => a.reduce((sum,value,index) => sum + value * b[index], 0);
  const sum = values => values.reduce((total,value) => total + value, 0);

  function invert(matrix) {
    const n = matrix.length;
    const work = matrix.map((row,i) => row.concat(Array.from({length:n},(_,j) => i === j ? 1 : 0)));
    for (let column = 0; column < n; column++) {
      let pivot = column;
      for (let row = column + 1; row < n; row++)
        if (Math.abs(work[row][column]) > Math.abs(work[pivot][column])) pivot = row;
      if (Math.abs(work[pivot][column]) < 1e-10) return null;
      [work[column],work[pivot]] = [work[pivot],work[column]];
      const divisor = work[column][column];
      for (let j = 0; j < 2 * n; j++) work[column][j] /= divisor;
      for (let row = 0; row < n; row++) {
        if (row === column) continue;
        const factor = work[row][column];
        for (let j = 0; j < 2 * n; j++) work[row][j] -= factor * work[column][j];
      }
    }
    return work.map(row => row.slice(n));
  }

  function covarianceInverse(vectors) {
    const dimensions = vectors[0].length;
    if (vectors.length <= dimensions) return null;
    const averages = Array.from({length:dimensions},(_,j) =>
      sum(vectors.map(row => row[j])) / vectors.length);
    const covariance = Array.from({length:dimensions},(_,i) =>
      Array.from({length:dimensions},(_,j) =>
        sum(vectors.map(row => (row[i] - averages[i]) * (row[j] - averages[j]))) / vectors.length));
    return invert(covariance);
  }

  function closure(vector) {
    if (vector.some(value => value < 0)) return null;
    const total = sum(vector);
    return total > 0 ? vector.map(value => value / total) : null;
  }

  function correlation(a,b) {
    const averageA = sum(a) / a.length;
    const averageB = sum(b) / b.length;
    const centeredA = a.map(value => value - averageA);
    const centeredB = b.map(value => value - averageB);
    const denominator = Math.sqrt(dot(centeredA,centeredA) * dot(centeredB,centeredB));
    return denominator > 1e-12 ? dot(centeredA,centeredB) / denominator : null;
  }

  function dtwDistance(a,b) {
    const rows = a.length + 1;
    const columns = b.length + 1;
    const table = Array.from({length:rows},() => Array(columns).fill(Infinity));
    table[0][0] = 0;
    for (let i = 1; i < rows; i++) for (let j = 1; j < columns; j++)
      table[i][j] = Math.abs(a[i - 1] - b[j - 1]) +
        Math.min(table[i - 1][j],table[i][j - 1],table[i - 1][j - 1]);
    return table[a.length][b.length] / (a.length + b.length);
  }

  function lcssDistance(a,b) {
    const epsilon = .5;
    const table = Array.from({length:a.length + 1},() => Array(b.length + 1).fill(0));
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
      table[i][j] = Math.abs(a[i - 1] - b[j - 1]) <= epsilon
        ? table[i - 1][j - 1] + 1
        : Math.max(table[i - 1][j],table[i][j - 1]);
    return 1 - table[a.length][b.length] / Math.min(a.length,b.length);
  }

  function distanceFunction(id,vectors) {
    const inverse = id === "mahalanobis" ? covarianceInverse(vectors) : null;
    if (id === "mahalanobis" && !inverse) return null;
    return (a,b) => {
      if (id === "manhattan") return sum(a.map((value,i) => Math.abs(value - b[i])));
      if (id === "euclidean" || id === "pointwise")
        return Math.sqrt(sum(a.map((value,i) => (value - b[i]) ** 2)));
      if (id === "chebyshev") return Math.max(...a.map((value,i) => Math.abs(value - b[i])));
      if (id === "minkowski") return sum(a.map((value,i) => Math.abs(value - b[i]) ** 3)) ** (1 / 3);
      if (id === "mahalanobis") {
        const difference = a.map((value,i) => value - b[i]);
        const transformed = inverse.map(row => dot(row,difference));
        return Math.sqrt(Math.max(0,dot(difference,transformed)));
      }
      if (id === "canberra") return sum(a.map((value,i) => {
        const denominator = Math.abs(value) + Math.abs(b[i]);
        return denominator ? Math.abs(value - b[i]) / denominator : 0;
      }));
      if (id === "braycurtis") {
        if (a.some(value => value < 0) || b.some(value => value < 0)) return null;
        const denominator = sum(a) + sum(b);
        return denominator ? sum(a.map((value,i) => Math.abs(value - b[i]))) / denominator : 0;
      }
      if (id === "hellinger") {
        const p = closure(a), q = closure(b);
        return p && q ? Math.sqrt(sum(p.map((value,i) => (Math.sqrt(value) - Math.sqrt(q[i])) ** 2))) / Math.sqrt(2) : null;
      }
      if (id === "jensen_shannon") {
        const p = closure(a), q = closure(b);
        if (!p || !q) return null;
        const middle = p.map((value,i) => (value + q[i]) / 2);
        const kl = (x,y) => sum(x.map((value,i) => value > 0 ? value * Math.log(value / y[i]) : 0));
        return Math.sqrt(Math.max(0,(kl(p,middle) + kl(q,middle)) / 2));
      }
      if (id === "aitchison") {
        if (a.some(value => value <= 0) || b.some(value => value <= 0)) return null;
        const clr = vector => {
          const logs = vector.map(Math.log);
          const average = sum(logs) / logs.length;
          return logs.map(value => value - average);
        };
        const x = clr(a), y = clr(b);
        return Math.sqrt(sum(x.map((value,i) => (value - y[i]) ** 2)));
      }
      if (id === "cosine") {
        const denominator = Math.sqrt(dot(a,a) * dot(b,b));
        return denominator > 1e-12 ? 1 - Math.max(-1,Math.min(1,dot(a,b) / denominator)) : null;
      }
      if (id === "correlation") {
        const value = correlation(a,b);
        return value === null ? null : 1 - Math.max(-1,Math.min(1,value));
      }
      if (id === "dtw") return dtwDistance(a,b);
      if (id === "lcss") return lcssDistance(a,b);
      if (id === "hamming") return sum(a.map((value,i) => value === b[i] ? 0 : 1)) / a.length;
      if (id === "jaccard") {
        let intersection = 0, union = 0;
        for (let i = 0; i < a.length; i++) {
          if (a[i] || b[i]) union++;
          if (a[i] && b[i]) intersection++;
        }
        return union ? 1 - intersection / union : 0;
      }
      return null;
    };
  }

  function normalizedMatrix(vectors,measure) {
    const distance = distanceFunction(measure,vectors);
    if (!distance) return null;
    const n = vectors.length;
    const matrix = Array.from({length:n},() => Array(n).fill(0));
    let maximum = 0;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const value = distance(vectors[i],vectors[j]);
      if (value === null || !Number.isFinite(value)) return null;
      matrix[i][j] = matrix[j][i] = value;
      maximum = Math.max(maximum,value);
    }
    if (maximum > 0) for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) matrix[i][j] /= maximum;
    return matrix;
  }

  function projectSimplex(values) {
    const sorted = [...values].sort((a,b) => b - a);
    let running = 0, rho = 0;
    for (let i = 0; i < sorted.length; i++) {
      running += sorted[i];
      if (sorted[i] - (running - 1) / (i + 1) > 0) rho = i + 1;
    }
    const threshold = (sum(sorted.slice(0,rho)) - 1) / rho;
    return values.map(value => Math.max(0,value - threshold));
  }

  function objective(weights,deltas,gamma,lambda) {
    const hinge = deltas.length ? sum(deltas.map(delta => Math.max(0,gamma + dot(weights,delta)))) / deltas.length : 0;
    const uniform = 1 / weights.length;
    return hinge + lambda * sum(weights.map(weight => (weight - uniform) ** 2));
  }

  function optimizeWeights(deltas,dimensions,gamma,lambda) {
    let weights = Array(dimensions).fill(1 / dimensions);
    let best = [...weights], bestValue = objective(weights,deltas,gamma,lambda);
    for (let iteration = 0; iteration < 1800; iteration++) {
      const gradient = Array(dimensions).fill(0);
      for (const delta of deltas) if (gamma + dot(weights,delta) > 0)
        for (let r = 0; r < dimensions; r++) gradient[r] += delta[r] / deltas.length;
      const uniform = 1 / dimensions;
      for (let r = 0; r < dimensions; r++) gradient[r] += 2 * lambda * (weights[r] - uniform);
      const rate = .18 / Math.sqrt(iteration + 1);
      weights = projectSimplex(weights.map((weight,r) => weight - rate * gradient[r]));
      const value = objective(weights,deltas,gamma,lambda);
      if (value < bestValue) { bestValue = value; best = [...weights]; }
    }
    return {weights:best,objective:bestValue};
  }

  function configurations(options,index=0,current=[],result=[]) {
    if (index === options.length) { result.push([...current]); return result; }
    for (const option of options[index]) {
      current.push(option);
      configurations(options,index + 1,current,result);
      current.pop();
    }
    return result;
  }

  function pairKey(first,second) {
    return first < second ? first + ":" + second : second + ":" + first;
  }

  function consistentConstraints(answers) {
    const constraints = [];
    const directions = new Set();
    for (const answer of answers) {
      const [a,b] = answer.chosen;
      const selected = pairKey(a,b);
      for (const alternative of [pairKey(a,answer.excluded), pairKey(b,answer.excluded)]) {
        const key = selected + "<" + alternative;
        constraints.push({left:selected,right:alternative,answer});
        directions.add(key);
      }
    }
    const contradictory = new Set();
    for (const constraint of constraints) {
      const key = constraint.left + "<" + constraint.right;
      const reverse = constraint.right + "<" + constraint.left;
      if (directions.has(reverse)) {
        contradictory.add(key);
        contradictory.add(reverse);
      }
    }
    return {
      retained:constraints.filter(constraint => !contradictory.has(constraint.left + "<" + constraint.right)),
      removed:constraints.filter(constraint => contradictory.has(constraint.left + "<" + constraint.right)).length
    };
  }

  function pairIndices(key,indexById) {
    const [first,second] = key.split(":").map(Number);
    return [indexById.get(first),indexById.get(second)];
  }

  function train({rowIds,blocks,answers,gamma=.05,lambda=.01}) {
    if (!answers.length) throw new Error("Non ci sono scelte da utilizzare.");
    const indexById = new Map(rowIds.map((id,index) => [id,index]));
    const constraints = consistentConstraints(answers);
    if (!constraints.retained.length)
      throw new Error("Le scelte producono soltanto disuguaglianze contraddittorie.");
    const prepared = blocks.map(block => {
      const options = block.candidateMeasures.map(measure => ({
        measure,
        matrix:normalizedMatrix(block.vectors,measure)
      })).filter(option => option.matrix);
      if (!options.length) throw new Error('Nessuna misura calcolabile per il blocco “' + block.label + '”.');
      return {...block,options};
    });
    const choices = configurations(prepared.map(block => block.options));
    let best = null;
    for (const choice of choices) {
      const deltas = [];
      for (const constraint of constraints.retained) {
        const [a,b] = pairIndices(constraint.left,indexById);
        const [c,d] = pairIndices(constraint.right,indexById);
        deltas.push(choice.map(option => option.matrix[a][b] - option.matrix[c][d]));
      }
      const fitted = optimizeWeights(deltas,prepared.length,gamma,lambda);
      if (!best || fitted.objective < best.objective - 1e-12)
        best = {choice,weights:fitted.weights,objective:fitted.objective};
    }
    let respected = 0;
    const combined = (i,j) => sum(best.choice.map((option,r) => best.weights[r] * option.matrix[i][j]));
    for (const answer of answers) {
      const a = indexById.get(answer.chosen[0]);
      const b = indexById.get(answer.chosen[1]);
      const c = indexById.get(answer.excluded);
      const selected = combined(a,b);
      if (selected <= combined(a,c) + 1e-12 && selected <= combined(b,c) + 1e-12) respected++;
    }
    const rankMatrix = rowIds.map((_,i) => {
      const ordered = rowIds.map((id,j) => ({id,j,distance:combined(i,j)})).sort((first,second) => {
        const difference = first.distance - second.distance;
        if (Math.abs(difference) > 1e-12) return difference;
        return String(first.id).localeCompare(String(second.id),undefined,{numeric:true});
      });
      const ranks = Array(rowIds.length);
      ordered.forEach((item,position) => { ranks[item.j] = position + 1; });
      return ranks;
    });
    return {
      blocks:prepared.map((block,r) => ({
        id:block.id,
        label:block.label,
        measure:best.choice[r].measure,
        measureLabel:LABELS[best.choice[r].measure] || best.choice[r].measure,
        weight:best.weights[r]
      })),
      respected,
      total:answers.length,
      rate:respected / answers.length,
      objective:best.objective,
      configurations:choices.length,
      constraintsUsed:constraints.retained.length,
      contradictoryConstraintsRemoved:constraints.removed,
      rowIds:[...rowIds],
      rankMatrix
    };
  }

  window.LearningTrainer = Object.freeze({train,labels:LABELS,consistentConstraints});
})();
