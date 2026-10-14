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

console.log("Tutti i test matematici sono stati superati.");
