const assert = require("node:assert/strict");
const M = require("../js/misure.js");

const quasiUguali = (a, b, tolleranza = 1e-12) => {
  assert.ok(Math.abs(a - b) <= tolleranza, `${a} e ${b} non coincidono entro la tolleranza`);
};

const x = [1, 4];
const y = [3, 1];

quasiUguali(M.minkowski(x, y, 2), Math.sqrt(13));
quasiUguali(M.minkowski(x, y, 1), 5);
quasiUguali(M.chebyshev(x, y), 3);
quasiUguali(M.minkowski(x, x, 3), 0);
quasiUguali(M.minkowski(x, y, 3), M.minkowski(y, x, 3));

assert.deepEqual(M.leggiVettore("1, 2, -3.5"), [1, 2, -3.5]);
assert.throws(() => M.minkowski([1], [1, 2], 2), /stessa dimensione/);
assert.throws(() => M.minkowski([1], [2], 0.5), /q ≥ 1/);

const b1 = [1, 1, 0, 0];
const b2 = [1, 0, 1, 0];
assert.deepEqual(M.conteggiBinari(b1, b2), { n11: 1, n10: 1, n01: 1, n00: 1 });
quasiUguali(M.calcolaBinaria("jaccard", b1, b2).distanza, 2 / 3);
quasiUguali(M.calcolaBinaria("dice", b1, b2).distanza, 1 / 2);
quasiUguali(M.calcolaBinaria("ochiai", b1, b2).distanza, 1 / 2);
quasiUguali(M.calcolaBinaria("hamming", b1, b2).distanza, 1 / 2);
quasiUguali(M.calcolaBinaria("jaccard", b1, b2).distanza, M.calcolaBinaria("jaccard", b2, b1).distanza);

for (const tipo of ["jaccard", "dice", "ochiai", "hamming"]) {
  quasiUguali(M.calcolaBinaria(tipo, [0, 0], [0, 0]).distanza, 0);
}
quasiUguali(M.calcolaBinaria("ochiai", [0, 0], [1, 0]).distanza, 1);
assert.throws(() => M.calcolaBinaria("jaccard", [1, 2], [1, 0]), /0 oppure 1/);
assert.throws(() => M.calcolaBinaria("jaccard", [1], [1, 0]), /stessa dimensione/);

console.log("Tutti i test matematici sono stati superati.");
