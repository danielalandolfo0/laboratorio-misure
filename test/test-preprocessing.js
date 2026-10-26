const assert = require("node:assert/strict");
const P = require("../js/preprocessing.js");

const quasiUguali = (a, b, tolleranza = 1e-10) => assert.ok(Math.abs(a - b) <= tolleranza, `${a} ≠ ${b}`);

const tabella = P.leggiCsv("a,b,flag,gruppo\n1,10,0,x\n2,20,1,y\n3,30,0,x");
assert.deepEqual(tabella.intestazioni, ["a", "b", "flag", "gruppo"]);
assert.equal(tabella.righe.length, 3);
assert.equal(tabella.separatore, ",");

const preparata = P.preparaTabella(tabella);
assert.equal(preparata.colonne[0].metodo, "zscore");
assert.equal(preparata.colonne[2].tipo, "binaria");
assert.equal(preparata.colonne[3].tipo, "non_numerica");
quasiUguali(preparata.trasformate[0][0], -Math.sqrt(1.5));
quasiUguali(preparata.trasformate[1][0], 0);
quasiUguali(preparata.trasformate[2][0], Math.sqrt(1.5));
assert.deepEqual(preparata.trasformate.map(r => r[2]), [0, 1, 0]);
assert.deepEqual(preparata.trasformate.map(r => r[3]), ["x", "y", "x"]);

const conEstremo = P.preparaTabella(P.leggiCsv("x;costante\n1;5\n2;5\n3;5\n4;5\n5;5\n6;5\n7;5\n8;5\n9;5\n100;5"));
assert.equal(conEstremo.colonne[0].metodo, "robusto");
assert.equal(conEstremo.colonne[0].motivo, "È presente un solo outlier.");
assert.equal(conEstremo.colonne[1].metodo, "costante");
assert.ok(conEstremo.trasformate.every(r => r[1] === 0));

const decimaliItaliani = P.preparaTabella(P.leggiCsv("x;y\n1,5;2,5\n2,5;3,5"));
assert.equal(decimaliItaliani.originale.separatore, ";");
assert.equal(decimaliItaliani.colonne[0].tipo, "numerica");

const mancanti = P.preparaTabella(P.leggiCsv("x,y\n1,NA\n2,3\n3,4"));
assert.equal(mancanti.riepilogo.mancanti, 1);
assert.equal(mancanti.trasformate[0][1], null);

assert.throws(() => P.leggiCsv("a,a\n1,2"), /univoci/);
assert.throws(() => P.leggiCsv("a,b\n1,2\n3"), /riga 3/);
assert.match(P.creaCsv(["a", "b"], [[1.25, "x,y"]]), /^a,b\n1.25,"x,y"$/);

const manuale = P.preparaTabella(tabella, [
  { tipo: "numerica", metodo: "nessuno" },
  { tipo: "numerica", metodo: "robusto" },
  { tipo: "numerica", metodo: "zscore" },
  { tipo: "non_numerica", metodo: "auto" }
]);
assert.deepEqual(manuale.trasformate.map(r => r[0]), [1, 2, 3]);
assert.equal(manuale.colonne[1].metodo, "robusto");
assert.equal(manuale.colonne[2].tipo, "numerica");

const binariaComeNumerica = P.preparaTabella(tabella, [{}, {}, { tipo: "numerica", metodo: "auto" }]);
assert.equal(binariaComeNumerica.colonne[2].tipo, "numerica");
assert.equal(binariaComeNumerica.colonne[2].metodo, "zscore");
assert.equal(binariaComeNumerica.colonne[2].metodoAutomatico, "zscore");
assert.notDeepEqual(binariaComeNumerica.trasformate.map(r => r[2]), [0, 1, 0]);
assert.throws(() => P.preparaTabella(tabella, [{ tipo: "auto", metodo: "auto" }, {}, {}, { tipo: "numerica", metodo: "zscore" }]), /valori non numerici/);
assert.throws(() => P.preparaTabella(tabella, [{}, { tipo: "binaria", metodo: "auto" }]), /non è binaria/);
assert.throws(() => P.preparaTabella(conEstremo.originale, [{}, { tipo: "numerica", metodo: "zscore" }]), /costante/);

const sparse = P.preparaTabella(P.leggiCsv("x,id\n0,a\n0,b\n0,c\n0,d\n0,e\n0,f\n0,g\n0,h\n2,i\n-1,j"));
assert.equal(sparse.colonne[0].metodo, "maxabs");
assert.equal(sparse.colonne[0].motivo, "Molti valori sono uguali a zero.");
assert.deepEqual(sparse.trasformate.map(r => r[0]), [0, 0, 0, 0, 0, 0, 0, 0, 1, -.5]);

const minmax = P.preparaTabella(tabella, [{ tipo: "numerica", metodo: "minmax" }]);
assert.deepEqual(minmax.trasformate.map(r => r[0]), [0, .5, 1]);
assert.throws(() => P.preparaTabella(conEstremo.originale, [{}, { tipo: "numerica", metodo: "minmax" }]), /costante/);

console.log("Tutti i test di preprocessing sono stati superati.");
