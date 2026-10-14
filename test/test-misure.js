const assert = require("node:assert/strict");
const M = require("../js/misure.js");

const quasiUguali = (a, b, tolleranza = 1e-12) => {
  assert.ok(Math.abs(a - b) <= tolleranza, `${a} e ${b} non coincidono entro la tolleranza`);
};

const x = [1, 4];
const y = [3, 1];
quasiUguali(M.calcolaNumerica("minkowski", x, y, { q: 2 }).valore, Math.sqrt(13));
quasiUguali(M.calcolaNumerica("manhattan", x, y).valore, 5);
quasiUguali(M.calcolaNumerica("chebyshev", x, y).valore, 3);
quasiUguali(M.calcolaNumerica("weighted_minkowski", x, y, { q: 2, pesi: [2, 1] }).valore, Math.sqrt(17));
quasiUguali(M.calcolaNumerica("standardized_euclidean", x, y, { scale: [2, 3] }).valore, Math.sqrt(2));
quasiUguali(M.calcolaNumerica("mahalanobis", x, y, { matrice: [[2, 0], [0, 1]] }).valore, Math.sqrt(11));
quasiUguali(M.calcolaNumerica("canberra", x, y).valore, 1.1);
quasiUguali(M.calcolaNumerica("bray_curtis", x, y).valore, 5 / 9);
quasiUguali(M.calcolaNumerica("chi_square", x, y).valore, Math.sqrt(2.8));
assert.equal(M.calcolaNumerica("bray_curtis", [0, 0], [0, 0]).definita, false);
assert.throws(() => M.calcolaNumerica("bray_curtis", [-1], [1]), /non negative/);
assert.throws(() => M.calcolaNumerica("mahalanobis", x, y, { matrice: [[1, 2], [0, 1]] }), /simmetrica/);
assert.throws(() => M.calcolaNumerica("mahalanobis", x, y, { matrice: [[1, 0], [0, 0]] }), /definita positiva/);

assert.deepEqual(M.leggiVettore("1, 2, -3.5"), [1, 2, -3.5]);
assert.deepEqual(M.leggiMatrice("2, 0; 0, 1"), [[2, 0], [0, 1]]);
assert.throws(() => M.minkowski([1], [1, 2], 2), /stessa dimensione/);
assert.throws(() => M.minkowski([1], [2], .5), /q ≥ 1/);

const b1 = [1, 1, 0, 0];
const b2 = [1, 0, 1, 0];
assert.deepEqual(M.conteggiBinari(b1, b2), { n11: 1, n10: 1, n01: 1, n00: 1 });
const attesi = {
  hamming: .5,
  rogers_tanimoto: 2 / 3,
  sokal_sneath_sym: 1 / 3,
  jaccard: 2 / 3,
  sokal_sneath_asym: 4 / 5,
  dice: .5,
  ochiai: .5,
  russell_rao: 3 / 4,
  yule_q: 0,
  phi: 0
};
for (const [tipo, atteso] of Object.entries(attesi)) quasiUguali(M.calcolaBinaria(tipo, b1, b2).valore, atteso);
quasiUguali(M.calcolaBinaria("weighted_binary", b1, b2, { lambda: 1, mu: 1, nu: 1 }).valore, .5);

const nulli = [0, 0];
quasiUguali(M.calcolaBinaria("jaccard", nulli, nulli).valore, 0);
quasiUguali(M.calcolaBinaria("sokal_sneath_asym", nulli, nulli).valore, 0);
assert.equal(M.calcolaBinaria("dice", nulli, nulli).definita, false);
assert.equal(M.calcolaBinaria("ochiai", nulli, nulli).definita, false);
assert.equal(M.calcolaBinaria("ochiai", nulli, [1, 0]).definita, false);
assert.equal(M.calcolaBinaria("yule_q", [1, 1], [1, 1]).definita, false);
assert.equal(M.calcolaBinaria("phi", [1, 1], [1, 1]).definita, false);
assert.throws(() => M.calcolaBinaria("jaccard", [1, 2], [1, 0]), /0 oppure 1/);

console.log("Tutti i test matematici sono stati superati.");
