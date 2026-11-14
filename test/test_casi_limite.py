"""Collaudo trasversale dei casi limite nel contratto del motore.

Test di riferimento indipendenti, con risultati analitici e un oracolo
esaustivo dei cammini DTW. Nessun dato mancante diventa zero senza scelta.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
import preprocessing as p  # noqa: E402


def vicino(a, b, tol=1e-10):
    assert a is not None and math.isfinite(a)
    assert math.isclose(a, b, abs_tol=tol, rel_tol=tol), (a, b)


def deve_fallire(func, frammento):
    try:
        func()
    except ValueError as errore:
        assert frammento.lower() in str(errore).lower(), str(errore)
    else:
        raise AssertionError("La configurazione incompatibile è stata accettata.")


# 1. Coordinate numeriche, pesi, denominatori nulli e disponibilità.
vicino(p._distanza_numerica([0, 0], [3, 4], "euclidean", {}), 5)
vicino(p._distanza_numerica([0, 0], [3, 4], "manhattan", {}), 7)
vicino(p._distanza_numerica([0, 0], [3, 4], "chebyshev", {}), 4)
vicino(p._distanza_numerica([0, 0], [3, 4], "weighted_minkowski",
                          {"q": 2, "pesi": [2, 1]}), math.sqrt(34))
vicino(p._distanza_numerica([0, 0], [0, 0], "canberra", {}), 0)
vicino(p._distanza_numerica([1, 0], [0, 1], "bray_curtis", {}), 1)
assert p._distanza_numerica([0, 0], [0, 0], "bray_curtis", {}) is None
vicino(p._distanza_numerica([0, 0], [0, 0], "bray_curtis",
                           {"doppioZero": "zero"}), 0)
assert p._distanza_numerica([0, 0], [0, 0], "bray_curtis",
                           {"doppioZero": "indefinita"}) is None
vicino(p._distanza_numerica([1, 0], [0, 1], "chi_square", {}), math.sqrt(2))
vicino(p._distanza_coordinate_comuni(
    [0, None, 4], [3, 5, 0], "euclidean", {}
), math.sqrt((9 + 16) / 2))
assert p._distanza_coordinate_comuni(
    [0, None], [None, 4], "euclidean", {}
) is None
deve_fallire(
    lambda: p._distanza_coordinate_comuni(
        [1, 2], [2, 3], "weighted_minkowski", {"q": 2, "pesi": [1, 0]}
    ), "strettamente positivo"
)

# 2. Binarie simmetriche/asimmetriche: zero osservato != mancante.
vicino(p._distanza_vettori_binari([0, 0], [0, 0], "jaccard"), 0)
vicino(p._distanza_vettori_binari([0, 1], [1, 1], "hamming"), .5)
vicino(p._distanza_vettori_binari([0, 1], [1, 1], "jaccard"), .5)
vicino(p._distanza_vettori_binari([0, 1], [1, 1], "dice"), 1 / 3)
vicino(p._distanza_vettori_binari([0, 1], [1, 1], "rogers_tanimoto"), 2 / 3)
assert p._distanza_vettori_binari([None, 0], [1, None], "jaccard") is None
assert p._distanza_vettori_binari(
    [0, 0], [0, 0], "dice", consenti_indefiniti=True
) is None
deve_fallire(
    lambda: p._distanza_vettori_binari([0, 0], [0, 0], "dice"),
    "non è definita",
)

# 3. Stringhe, insiemi, variabili cicliche.
for fn in (p._levenshtein_normalizzata, p._damerau_levenshtein_normalizzata):
    vicino(fn("", ""), 0)
    vicino(fn("abc", "abc"), 0)
    vicino(fn("abc", ""), 1)
    vicino(fn("abc", "axc"), 1 / 3)
    for a, b in (("ab", "ba"), ("ac", "bb"), ("abc", "acbd")):
        vicino(fn(a, b), fn(b, a))
        assert 0 <= fn(a, b) <= 1
vicino(p._damerau_levenshtein_normalizzata("ab", "ba"), .5)
vicino(p._hamming_normalizzata("", ""), 0)
vicino(p._hamming_normalizzata("abc", "abd"), 1 / 3)
deve_fallire(lambda: p._hamming_normalizzata("a", "ab"), "uguale")
empty = frozenset()
full = frozenset({"a", "b"})
for metodo in ("jaccard", "dice"):
    vicino(p._distanza_insiemi(empty, empty, metodo), 0)
    vicino(p._distanza_insiemi(empty, full, metodo), 1)
vicino(p._distanza_ciclica(23, 1, 24), 1 / 6)
deve_fallire(lambda: p._distanza_ciclica(24, 0, 24), "[0,P)")

# 4. Distribuzioni e profili: non si sanano masse nulle o norme nulle.
for misura in ("hellinger", "jensen_shannon"):
    vicino(p._distanza_distribuzioni([1, 0], [0, 1], misura, "probabilita"), 1)
    vicino(p._distanza_distribuzioni([2, 0], [4, 0], misura, "masse"), 0)
    deve_fallire(
        lambda m=misura: p._distanza_distribuzioni(
            [0, 0], [1, 0], m, "masse"
        ), "positiva"
    )
assert p._distanza_specializzata(
    [0, 0], [1, 0], "Dissimilarità coseno"
) is None
assert p._distanza_specializzata(
    [1, 1, 1], [2, 2, 2], "Dissimilarità di Pearson"
) is None
vicino(p._distanza_specializzata(
    [1, 2, 3], [3, 2, 1], "Dissimilarità di Pearson"
), 2)
assert p._kendall_tau_b([1, 1, 1], [2, 3, 4]) is None

# 5. Serie temporali: confronto fra la DTW esatta e tutti i cammini.
def dtw_bruteforce(x, y, quadratico=False, finestra=None):
    n, m = len(x), len(y)
    risultati = []

    def cammino(i, j, costo, lunghezza):
        if finestra is not None and abs(i - j) > finestra:
            return
        d = abs(x[i] - y[j])
        costo += d * d if quadratico else d
        lunghezza += 1
        if i == n - 1 and j == m - 1:
            risultati.append(costo / lunghezza)
        else:
            for di, dj in ((1, 0), (0, 1), (1, 1)):
                if i + di < n and j + dj < m:
                    cammino(i + di, j + dj, costo, lunghezza)

    cammino(0, 0, 0, 0)
    return min(risultati)


for x in ([0], [0, 1], [0, 2, 0]):
    for y in ([0], [1, 0], [0, 1, 2]):
        for metodo in ("assoluto", "quadratico"):
            q = metodo == "quadratico"
            valore = p._distanza_dtw(x, y, {"costoLocale": metodo})
            vicino(valore, dtw_bruteforce(x, y, q))
            vicino(valore, p._distanza_dtw(y, x, {"costoLocale": metodo}))
            if len(x) == len(y):
                vicino(
                    p._distanza_dtw(x, y, {"costoLocale": metodo, "finestra": 0}),
                    dtw_bruteforce(x, y, q, finestra=0)
                )
deve_fallire(
    lambda: p._distanza_dtw([1], [1, 2], {"finestra": 0}),
    "consentire un cammino"
)
vicino(p._distanza_lcss([1, 2], [1, 2], [0, 1], [0, 1], 0, 0), 0)
vicino(p._distanza_lcss([1], [3], [0], [0], 0, 0), 1)

# 6. Invarianti globali e compatibilità semantica dichiarata.
dati_bray = "x,y\n0,0\n0,0\n3,2"
base = {
    "riga": "oggetto",
    "confrontoQuantitativo": "abbondanza",
    "gestioneDipendenzaLineare": "mantieni",
    "colonne": {
        "x": {"usa": True, "ruolo": "quantita"},
        "y": {"usa": True, "ruolo": "quantita"},
    }
}
preparati = p.prepara_tabella(p.leggi_csv(dati_bray))
piano_senza = p.crea_piano_confronto(preparati, base)
assert not piano_senza["completo"], piano_senza
bray = piano_senza["percorsi"][0]
assert bray["idMisura"] == "bray_curtis"
assert bray["coppieBrayDoppioZero"] == 1
assert bray["righeNulleBrayCurtis"] == [1, 2]
assert any("0/0" in avviso for avviso in bray["avvisi"])
assert piano_senza["rapportoProblemi"]["numeroBloccanti"] > 0
deve_fallire(lambda: p.calcola_matrice(preparati, base), "Completa")

con_zero = {**base, "convenzioneBrayCurtisZero": "zero"}
piano_zero = p.crea_piano_confronto(preparati, con_zero)
assert piano_zero["completo"], piano_zero
assert piano_zero["percorsi"][0]["parametri"]["doppioZero"] == "zero"
matrice_zero = p.calcola_matrice(preparati, con_zero)
assert len(matrice_zero["matrice"]) == 3
vicino(matrice_zero["matrice"][0][1], 0)
vicino(matrice_zero["matrice"][0][2], 1)
vicino(matrice_zero["matrice"][1][2], 1)
assert matrice_zero["diagnosticaFinale"]["coppieZeroDistinte"] == 1
assert "Convenzione per due vettori nulli" in matrice_zero["nota"]

indefinita = {**base, "convenzioneBrayCurtisZero": "indefinita"}
piano_indefinito = p.crea_piano_confronto(preparati, indefinita)
assert piano_indefinito["completo"]
try:
    p.calcola_matrice(preparati, indefinita)
    raise AssertionError("Non si deve inventare la distanza 0/0.")
except p.IncompatibilitaCalcolo as errore:
    assert errore.rapportoProblemi["coppieNonConfrontabili"] == [[1, 2]]

# Il bridge browser deve mantenere la decisione nell'API JSON.
output = json.loads(p.calcola_matrice_json(
    dati_bray, "[]", json.dumps(con_zero)
))
assert output["ok"]
vicino(output["matrice"]["matrice"][0][1], 0)
assert output["matrice"]["diagnosticaFinale"]["coppieZeroDistinte"] == 1

# Non si può convertire in numeri finiti una matrice non valida.
for matrice, messaggio in (
    ([[0, math.nan], [math.nan, 0]], "non finito"),
    ([[0, math.inf], [math.inf, 0]], "non finito"),
    ([[0, -0.1], [-0.1, 0]], "intervallo"),
    ([[0, 0.3], [0.8, 0]], "simmetrica"),
):
    deve_fallire(
        lambda m=matrice: p._valida_matrice_finale(m, ["A", "B"]), messaggio
    )

print("Collaudo trasversale dei casi limite superato.")
