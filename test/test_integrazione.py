"""Collaudo trasversale dell'intero contratto di confronto.

Scenari: Gower nominale/ordinale personalizzata, Hamming, Minkowski
pesata pairwise con trasformazioni miste e normalizzazione robusta,
Hellinger, pesi differenti, mancanti, permutazioni di righe e CSV finale.
Il confronto con formule indipendenti verifica la correttezza della
matrice, non solamente la sua forma.

Esecuzione: python3 test/test_integrazione.py
"""
from __future__ import annotations

import copy
import csv
import io
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import preprocessing as p  # noqa: E402


def vicino(a: float, b: float, eps: float = 1e-10) -> None:
    assert math.isclose(a, b, rel_tol=eps, abs_tol=eps), f"{a} != {b}"


CSV = ROOT / "examples" / "collaudo" / "test_integrato_gower_gruppi_mancanti.csv"
raw = CSV.read_text(encoding="utf-8")
colonne = raw.splitlines()[0].split(",")
assert colonne == [
    "livello", "categoria", "c1", "c2", "p1", "p2", "p3", "codice", "id"
]
scelte = [
    {"tipo": "auto", "metodo": (
        "nessuno" if nome == "c1" else "log1p" if nome == "c2" else "auto"
    )}
    for nome in colonne
]
tabella = p.prepara_tabella(p.leggi_csv(raw), scelte)
risposte = {
    "riga": "oggetto",
    "significatoEstremi": "reali",
    "significatoMancanti": "sconosciuto",
    "riscalamentoConfermato": True,
    "confrontoQuantitativo": "assoluto",
    "colonne": {
        **{
            nome: {"ruolo": "quantita", "usa": True}
            for nome in ("c1", "c2", "p1", "p2", "p3")
        },
        "livello": {"ruolo": "livello", "usa": True},
        "categoria": {"ruolo": "categoria", "usa": True},
        "codice": {"ruolo": "testo", "usa": True},
        "id": {"ruolo": "identificativo", "usa": False},
    },
    "ordineLivelli": "si",
    "ordiniLivelliGower": {"livello": "basso; medio; alto"},
    "modalitaIntervalliGower": {"livello": "personalizzati"},
    "passiOrdinaliGower": {"livello": "1; 3"},
    "modalitaCategorieGower": {"categoria": "personalizzata"},
    "dissimilaritaCategorieGower": {
        "categoria": {
            "livelli": ["blu", "rosso", "verde"],
            "coppie": {"0:1": "0.4", "0:2": "0.8", "1:2": "0.6"},
        }
    },
    "pesiGower": {"livello": "2", "categoria": "1"},
    "misureTestualiPerColonna": {"codice": "hamming"},
    "gruppi": [
        {"id": "coord", "nome": "Coordinate", "tipo": "coordinate"},
        {"id": "dist", "nome": "Istogramma", "tipo": "distribuzione"},
    ],
    "assegnazioni": {
        "c1": "coord", "c2": "coord",
        "p1": "dist", "p2": "dist", "p3": "dist",
    },
    "misureGruppi": {"coord": "weighted_minkowski"},
    "ordiniGruppi": {"coord": "2"},
    "pesiGruppi": {"coord": "1; 4"},
    "mancanti-gruppo-coord": "pairwise",
    "naturaDistribuzione-dist": "probabilita",
    "misuraDistribuzione-dist": "hellinger",
    "confermeRiscalamentiMistiGruppi": {"coord": "si"},
    "confermeValoriOriginaliGruppi": {"dist": "si"},
    "normalizzazioniPercorsi": {"percorso-3": "robusta"},
    "righeAnomaleNormalizzazione": {"percorso-3": "4; 5"},
    "pesiPercorsi": {
        "percorso-1": "2",
        "percorso-2": "1",
        "percorso-3": "3",
        "percorso-4": "4",
    },
}

piano = p.crea_piano_confronto(tabella, risposte)
assert piano["completo"], piano
# Gli spazi sono validi separatori nel campo dei numeri di riga: l'UI
# mostra esempi come "4; 5", quindi il parser deve accettarli davvero.
con_spazi = copy.deepcopy(risposte)
con_spazi["righeAnomaleNormalizzazione"]["percorso-3"] = "4 ;  5"
assert p.crea_piano_confronto(tabella, con_spazi)["completo"]
assert piano["conteggioPercorsi"] == 4, piano
assert [percorso["tipo"] for percorso in piano["percorsi"]] == [
    "gower", "separato", "gruppo", "gruppo"
]
assert [percorso["metodo"] for percorso in piano["percorsi"]] == [
    "Dissimilarità di Gower classica con contributi personalizzati",
    "Distanza di Hamming normalizzata",
    "Distanza di Minkowski pesata",
    "Distanza di Hellinger",
]
assert [percorso["colonne"] for percorso in piano["percorsi"]] == [
    ["livello", "categoria"], ["codice"], ["c1", "c2"], ["p1", "p2", "p3"]
]
assert len({nome for path in piano["percorsi"] for nome in path["colonne"]}) == 8
assert piano["percorsi"][2]["preelaborazione"]["usaTabellaTrasformata"]
assert not piano["percorsi"][3]["preelaborazione"]["usaTabellaTrasformata"]
assert [s["metodo"] for s in piano["percorsi"][2]["preelaborazione"]["passi"]] == [
    "nessuno", "log1p"
]
assert [path["pesoAggregazione"] for path in piano["percorsi"]] == [2, 1, 3, 4]
assert [path["normalizzazione"]["metodo"] for path in piano["percorsi"]] == [
    "teorica", "teorica", "robusta", "teorica"
]

local_gower = p.calcola_matrice_gower(tabella, risposte)["matrice"]
local_text = p._calcola_matrice_specializzata(
    tabella, risposte, piano["percorsi"][1]
)["matrice"]
local_coord_result = p._calcola_matrice_specializzata(
    tabella, risposte, piano["percorsi"][2]
)
local_coord = local_coord_result["matrice"]
local_dist = p._calcola_matrice_specializzata(
    tabella, risposte, piano["percorsi"][3]
)["matrice"]

# Formula di riferimento del confronto pesato con coordinate comuni:
# c1 originale, c2 trasformata con log(1+x). I pesi 1 e 4 vengono
# ristretti e rinormalizzati sulle coordinate osservate da entrambi.
coordinate = [
    (1., 10.), (2., 12.), (None, 15.),
    (10., None), (None, None), (3., 17.)
]
def distanza_coordinate_attesa(i, j):
    a, b = coordinate[i], coordinate[j]
    termini = []
    if a[0] is not None and b[0] is not None:
        termini.append((1, abs(a[0] - b[0]) ** 2))
    if a[1] is not None and b[1] is not None:
        termini.append((4, abs(math.log1p(a[1]) - math.log1p(b[1])) ** 2))
    if not termini:
        return None
    return math.sqrt(sum(w * d for w, d in termini) /
                     sum(w for w, _ in termini))

for i in range(6):
    for j in range(i + 1, 6):
        expected = distanza_coordinate_attesa(i, j)
        if expected is None:
            assert local_coord[i][j] is None, (i, j, local_coord[i][j])
        else:
            vicino(local_coord[i][j], expected)
assert local_coord[2][3] is None
assert all(local_coord[4][j] is None for j in range(6) if j != 4)

norm_coord, descr, diag = p._normalizza_per_aggregazione_con_diagnostica(
    local_coord_result, piano["percorsi"][2]["normalizzazione"]
)
regular = [0, 1, 2, 5]  # Escluse SOLO dalla stima le righe D ed E.
scala_attesa = max(
    distanza_coordinate_attesa(i, j)
    for pos, i in enumerate(regular)
    for j in regular[pos + 1:]
    if distanza_coordinate_attesa(i, j) is not None
)
vicino(diag["scala"], scala_attesa)
assert diag["metodo"] == "robusta"
assert diag["righeEscluseSoloDallaScala"] == [4, 5]
assert diag["coppieSaturate"] > 0
assert "massimo robusto" in descr

# La matrice unica deve mediare soltanto i percorsi disponibili.
finale = p.calcola_matrice(tabella, risposte)
assert finale["metodo"] == "Dissimilarità complessiva pesata"
assert finale["etichette"] == list("ABCDEF")
assert finale["diagnosticaFinale"]["coppieNonDisponibili"] == 0
assert finale["diagnosticaFinale"]["coppieTotali"] == 15
assert len(finale["contributi"]) == 4
assert [c["peso"] for c in finale["contributi"]] == [2, 1, 3, 4]
assert finale["contributi"][2]["diagnosticaNormalizzazione"]["coppieSaturate"] > 0
assert any("saturate" in s for s in finale["diagnosticaFinale"]["avvisi"])
for i in range(6):
    assert finale["matrice"][i][i] == 0
    for j in range(i + 1, 6):
        assert finale["matrice"][i][j] == finale["matrice"][j][i]
        numeratore = 2 * local_gower[i][j] + local_text[i][j] + 4 * local_dist[i][j]
        denominatore = 2 + 1 + 4
        if norm_coord[i][j] is not None:
            numeratore += 3 * norm_coord[i][j]
            denominatore += 3
        vicino(finale["matrice"][i][j], numeratore / denominatore)
        assert 0 <= finale["matrice"][i][j] <= 1

vicino(local_gower[0][1], (2 * .25 + .4) / 3)
vicino(local_text[0][1], 1 / 3)
vicino(local_dist[0][1], 1)
vicino(finale["matrice"][0][4], (2 * (2 / 3) + 1 + 4) / 7)

# La rappresentazione scaricabile è una matrice intera: intestazione,
# etichette stabili e nessuna coppia indefinita (non solo anteprima 12x12).
csv_lines = list(csv.reader(io.StringIO(finale["csv"]), delimiter=";"))
assert len(csv_lines) == 7
assert csv_lines[0] == ["Riga", *list("ABCDEF")]
assert [row[0] for row in csv_lines[1:]] == list("ABCDEF")
assert all(len(row) == 7 for row in csv_lines)
assert all(row[j+1] for row in csv_lines[1:] for j in range(6))

# Invarianza rispetto a una permutazione del CSV. Le righe escluse
# SOLO dalla scala robusta devono essere rinumerate.
permutazione = [4, 2, 0, 5, 1, 3]  # Indici di riga del file originale
righe_raw = raw.strip().splitlines()
permutato = "\n".join([
    righe_raw[0], *[righe_raw[i + 1] for i in permutazione]
]) + "\n"
tabella_perm = p.prepara_tabella(p.leggi_csv(permutato), scelte)
conf_perm = copy.deepcopy(risposte)
conf_perm["righeAnomaleNormalizzazione"]["percorso-3"] = "1; 6"
piano_perm = p.crea_piano_confronto(tabella_perm, conf_perm)
assert piano_perm["completo"], piano_perm
finale_perm = p.calcola_matrice(tabella_perm, conf_perm)
for a, i in enumerate(permutazione):
    for b, j in enumerate(permutazione):
        vicino(finale_perm["matrice"][a][b], finale["matrice"][i][j])
assert finale_perm["etichette"] == [finale["etichette"][i] for i in permutazione]

# Variando una sola scelta semantica, le altre misure locali non mutano.
nominali_diversi = copy.deepcopy(risposte)
nominali_diversi["dissimilaritaCategorieGower"]["categoria"]["coppie"]["0:1"] = ".9"
piano_nominali = p.crea_piano_confronto(tabella, nominali_diversi)
assert piano_nominali["completo"], piano_nominali
assert p.calcola_matrice_gower(tabella, nominali_diversi)["matrice"] != local_gower
assert p._calcola_matrice_specializzata(
    tabella, nominali_diversi, piano_nominali["percorsi"][2]
)["matrice"] == local_coord
assert p._calcola_matrice_specializzata(
    tabella, nominali_diversi, piano_nominali["percorsi"][3]
)["matrice"] == local_dist

# Mancanza di conferme e valori impossibili bloccano il piano, senza
# scegliere silenziosamente una misura di riserva.
for cambia in (
    {"confermeRiscalamentiMistiGruppi": {}},
    {"confermeValoriOriginaliGruppi": {}},
    {"ordiniGruppi": {"coord": "0.5"}},
    {"pesiPercorsi": {"percorso-3": "0"}},
    {"righeAnomaleNormalizzazione": {"percorso-3": "7"}},
    {"misuraDistribuzione-dist": ""},
    {"passiOrdinaliGower": {"livello": "0; 0"}},
):
    proposta = {**risposte, **cambia}
    provvisorio = p.crea_piano_confronto(tabella, proposta)
    assert not provvisorio["completo"], (cambia, provvisorio)

# La conferma dei riscalamenti non deve forzarli sulle distribuzioni;
# quando viene negata, le coordinate devono tornare ai valori originali.
senza_scale = copy.deepcopy(risposte)
senza_scale["riscalamentoConfermato"] = False
piano_originale = p.crea_piano_confronto(tabella, senza_scale)
assert piano_originale["completo"], piano_originale
assert not piano_originale["percorsi"][2]["preelaborazione"]["usaTabellaTrasformata"]
assert p.calcola_matrice(tabella, senza_scale)["matrice"] != finale["matrice"]

print("Collaudo di integrazione a quattro percorsi superato.")
