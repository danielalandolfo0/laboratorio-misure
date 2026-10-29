"""Test della logica Python usata nel browser tramite Pyodide."""

from __future__ import annotations

import math
import pathlib
import sys


RADICE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE / "python"))

import preprocessing as p  # noqa: E402


def quasi_uguali(a: float, b: float, tolleranza: float = 1e-10) -> None:
    assert math.isclose(a, b, abs_tol=tolleranza), f"{a} != {b}"


def risposte_quantitative(**modifiche):
    risposte = {
        "riga": "oggetto",
        "comparabilitaScale": "comparabili",
        "confrontoQuantitativo": "assoluto",
        "aggregazioneScarti": "quadratica",
        "dipendenzaCoordinate": "no",
        "importanzaCoordinate": "uguale",
        "colonne": {
            "a": {"ruolo": "quantita", "usa": True},
            "b": {"ruolo": "quantita", "usa": True},
        },
    }
    risposte.update(modifiche)
    return risposte


tabella = p.leggi_csv("a,b,flag,gruppo\n1,10,0,x\n2,20,1,y\n3,30,0,x")
assert tabella["intestazioni"] == ["a", "b", "flag", "gruppo"]
assert len(tabella["righe"]) == 3
assert tabella["separatore"] == ","

preparata = p.prepara_tabella(tabella)
assert preparata["colonne"][0]["metodo"] == "zscore"
assert preparata["colonne"][2]["tipo"] == "binaria"
assert preparata["colonne"][3]["tipo"] == "non_numerica"
quasi_uguali(preparata["trasformate"][0][0], -math.sqrt(1.5))
quasi_uguali(preparata["trasformate"][1][0], 0)
quasi_uguali(preparata["trasformate"][2][0], math.sqrt(1.5))
assert [riga[2] for riga in preparata["trasformate"]] == [0, 1, 0]
assert [riga[3] for riga in preparata["trasformate"]] == ["x", "y", "x"]

con_estremo = p.prepara_tabella(
    p.leggi_csv("x;costante\n1;5\n2;5\n3;5\n4;5\n5;5\n6;5\n7;5\n8;5\n9;5\n100;5")
)
assert con_estremo["colonne"][0]["metodo"] == "robusto"
assert con_estremo["colonne"][0]["motivo"] == "È presente un solo outlier."
assert con_estremo["colonne"][1]["metodo"] == "costante"
assert all(riga[1] == 0 for riga in con_estremo["trasformate"])

robusto_comune = p.prepara_tabella(
    p.leggi_csv("a,b\n10,100\n12,105\n11,98\n9,102\n13,101\n10,99\n12,104\n80,103")
)
assert robusto_comune["colonne"][0]["metodo"] == "robusto"
assert robusto_comune["colonne"][1]["metodo"] == "robusto"
assert robusto_comune["colonne"][1]["metodoAutomatico"] == "robusto"
assert "scala robusta comune" in robusto_comune["colonne"][1]["motivo"]
quasi_uguali(p.statistiche([riga[0] for riga in robusto_comune["trasformate"]])["iqr"], 1)
quasi_uguali(p.statistiche([riga[1] for riga in robusto_comune["trasformate"]])["iqr"], 1)

decimali = p.prepara_tabella(p.leggi_csv("x;y\n1,5;2,5\n2,5;3,5"))
assert decimali["originale"]["separatore"] == ";"
assert decimali["colonne"][0]["tipo"] == "numerica"

mancanti = p.prepara_tabella(p.leggi_csv("x,y\n1,NA\n2,3\n3,4"))
assert mancanti["riepilogo"]["mancanti"] == 1
assert mancanti["trasformate"][0][1] is None

for testo, frammento in (
    ("a,a\n1,2", "univoci"),
    ("a,b\n1,2\n3", "riga 3"),
):
    try:
        p.leggi_csv(testo)
        raise AssertionError("Era atteso un errore")
    except ValueError as errore:
        assert frammento in str(errore)

assert p.crea_csv(["a", "b"], [[1.25, "x;y"]]) == 'a;b\n1,25;"x;y"'

manuale = p.prepara_tabella(
    tabella,
    [
        {"tipo": "numerica", "metodo": "nessuno"},
        {"tipo": "numerica", "metodo": "robusto"},
        {"tipo": "numerica", "metodo": "zscore"},
        {"tipo": "non_numerica", "metodo": "auto"},
    ],
)
assert [riga[0] for riga in manuale["trasformate"]] == [1, 2, 3]
assert manuale["colonne"][1]["metodo"] == "robusto"
assert manuale["colonne"][2]["tipo"] == "numerica"

binaria_numerica = p.prepara_tabella(
    tabella,
    [{}, {}, {"tipo": "numerica", "metodo": "auto"}],
)
assert binaria_numerica["colonne"][2]["tipo"] == "numerica"
assert binaria_numerica["colonne"][2]["metodo"] == "zscore"
assert binaria_numerica["colonne"][2]["metodoAutomatico"] == "zscore"
assert [riga[2] for riga in binaria_numerica["trasformate"]] != [0, 1, 0]

sparse = p.prepara_tabella(
    p.leggi_csv("x,id\n0,a\n0,b\n0,c\n0,d\n0,e\n0,f\n0,g\n0,h\n2,i\n-1,j")
)
assert sparse["colonne"][0]["metodo"] == "maxabs"
assert [riga[0] for riga in sparse["trasformate"]] == [0, 0, 0, 0, 0, 0, 0, 0, 1, -0.5]

scale_simili = p.prepara_tabella(p.leggi_csv("a,b\n1,10\n2,11\n3,12"))
assert [colonna["metodo"] for colonna in scale_simili["colonne"]] == ["nessuno", "nessuno"]
assert scale_simili["trasformate"] == [[1, 10], [2, 11], [3, 12]]

scale_diverse = p.prepara_tabella(p.leggi_csv("a,b\n1,100\n2,200\n3,300"))
assert [colonna["metodo"] for colonna in scale_diverse["colonne"]] == ["zscore", "zscore"]

una_numerica = p.prepara_tabella(p.leggi_csv("a,gruppo\n1,x\n2,y\n3,z"))
assert una_numerica["colonne"][0]["metodo"] == "nessuno"
assert "Non ci sono altre feature numeriche" in una_numerica["colonne"][0]["motivo"]

semantica = p.prepara_tabella(
    p.leggi_csv(
        "id,data,presente,livello,gruppo,descrizione\n"
        "A1,2026-01-01,1,1,rosso,nota alfa\n"
        "A2,2026-01-02,0,2,blu,nota beta\n"
        "A3,2026-01-03,1,3,rosso,nota gamma\n"
        "A4,2026-01-04,0,4,verde,nota delta\n"
        "A5,2026-01-05,1,5,blu,nota epsilon"
    )
)
ruoli = {c["nome"]: c["ruoloSuggerito"] for c in semantica["questionario"]["colonne"]}
assert ruoli["id"] == "identificativo"
assert ruoli["data"] == "data"
assert ruoli["presente"] == "presenza"
assert ruoli["livello"] == "livello"
assert ruoli["gruppo"] == "categoria"
assert ruoli["descrizione"] == "testo"
assert semantica["questionario"]["condizioni"]["binarie"] is True
assert semantica["questionario"]["condizioni"]["date"] is True
assert semantica["questionario"]["condizioni"]["livelli"] is True

misure_generiche = p.prepara_tabella(
    p.leggi_csv("misura_A,misura_B\n10,100\n12,105\n11,98\n9,102\n13,101\n80,103")
)
assert [c["ruoloSuggerito"] for c in misure_generiche["questionario"]["colonne"]] == [
    "quantita", "quantita"
]

piano_incompleto = p.crea_piano_confronto(preparata, {})
assert piano_incompleto["completo"] is False
assert "Indica che cosa rappresenta ogni riga." in piano_incompleto["avvisi"]

piano_semplice = p.crea_piano_confronto(
    preparata,
    {"riga": "persona", "zeriCondivisi": "no", "ordineLivelli": "si", "colonne": {}},
)
assert piano_semplice["completo"] is True
misure_piano = {blocco["nome"]: blocco["misura"] for blocco in piano_semplice["blocchi"]}
assert misure_piano["a"] == "Differenza tra ranghi normalizzata"
assert misure_piano["b"] == "Differenza numerica"
assert misure_piano["flag"] == "Confronto asimmetrico di Jaccard"
assert misure_piano["gruppo"] == "Uguale o diverso"
assert piano_semplice["conteggioPercorsi"] == 1
assert piano_semplice["percorsi"][0]["metodo"] == "Dissimilarità di Gower classica"
assert piano_semplice["versioneContratto"] == 1
assert piano_semplice["percorsi"][0]["preelaborazione"]["origine"] == "valori_originali"
assert piano_semplice["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is False
assert piano_semplice["percorsi"][0]["mancanti"]["strategia"] == "non_necessaria"
assert piano_semplice["percorsi"][0]["calcolo"]["disponibile"] is True

matrice_gower = p.calcola_matrice_gower(
    preparata,
    {"riga": "persona", "zeriCondivisi": "no", "ordineLivelli": "si", "colonne": {}},
)
assert matrice_gower["metodo"] == "Dissimilarità di Gower classica"
quasi_uguali(matrice_gower["matrice"][0][1], 0.75)
quasi_uguali(matrice_gower["matrice"][0][2], 2 / 3)
assert matrice_gower["matrice"][1][0] == matrice_gower["matrice"][0][1]
assert all(matrice_gower["matrice"][i][i] == 0 for i in range(3))
assert matrice_gower["csv"].splitlines()[0] == "Riga;Riga 1;Riga 2;Riga 3"
assert "0,75" in matrice_gower["csv"]

solo_presenze = p.prepara_tabella(p.leggi_csv("id,presente\na,0\nb,0\nc,1"))
matrice_presenze = p.calcola_matrice_gower(
    solo_presenze,
    {"riga": "evento", "zeriCondivisi": "no", "colonne": {}},
)
assert matrice_presenze["matrice"][0][1] is None
assert matrice_presenze["matrice"][0][2] == 1

dati_misti_estremi = p.prepara_tabella(
    p.leggi_csv("a,categoria\n10,x\n12,y\n11,x\n9,z\n13,y\n10,x\n12,z\n80,y")
)
matrice_robusta = p.calcola_matrice_gower(
    dati_misti_estremi,
    {"riga": "oggetto", "significatoEstremi": "reali", "colonne": {}},
)
assert matrice_robusta["metodo"] == "Dissimilarità di Gower robusta"
assert all(
    valore is None or 0 <= valore <= 1
    for riga in matrice_robusta["matrice"] for valore in riga
)

piano_numerico = p.crea_piano_confronto(
    scale_diverse,
    risposte_quantitative(comparabilitaScale="diverse", gestioneScale="trasforma"),
)
assert piano_numerico["completo"] is True
assert piano_numerico["percorsi"][0]["metodo"] == "Distanza euclidea"
assert piano_numerico["percorsi"][0]["origine"] == "Tabella trasformata per questo percorso"
assert piano_numerico["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is True
assert [
    passo["metodo"] for passo in piano_numerico["percorsi"][0]["preelaborazione"]["passi"]
] == ["zscore", "zscore"]
assert piano_numerico["percorsi"][0]["calcolo"]["disponibile"] is False

piano_numerico_estremi = p.crea_piano_confronto(
    robusto_comune,
    risposte_quantitative(
        significatoEstremi="reali",
        comparabilitaScale="diverse",
        gestioneScale="trasforma",
        aggregazioneScarti="lineare",
    ),
)
assert piano_numerico_estremi["completo"] is True
assert piano_numerico_estremi["percorsi"][0]["metodo"] == "Distanza di Manhattan"

piano_profilo = p.crea_piano_confronto(
    misure_generiche,
    {
        "riga": "oggetto",
        "significatoEstremi": "reali",
        "colonne": {
            "misura_A": {"ruolo": "quantita", "usa": True},
            "misura_B": {"ruolo": "quantita", "usa": True},
        },
        "gruppi": [{"id": "gruppo-1", "nome": "Profilo", "tipo": "ripetute"}],
        "assegnazioni": {"misura_A": "gruppo-1", "misura_B": "gruppo-1"},
        "somiglianza-gruppo-1": "andamento",
    },
)
assert piano_profilo["completo"] is True
assert piano_profilo["conteggioBlocchi"] == 1
assert piano_profilo["blocchi"][0]["misura"] == "Dissimilarità di Pearson"
assert piano_profilo["conteggioPercorsi"] == 1
assert piano_profilo["percorsi"][0]["metodo"] == "Dissimilarità di Pearson"
assert piano_profilo["percorsi"][0]["preelaborazione"]["origine"] == "valori_originali"
assert piano_profilo["percorsi"][0]["preelaborazione"]["passi"] == []

piano_numerico_con_mancanti = p.crea_piano_confronto(
    mancanti,
    {
        "riga": "oggetto",
        "significatoMancanti": "sconosciuto",
        "comparabilitaScale": "comparabili",
        "confrontoQuantitativo": "assoluto",
        "aggregazioneScarti": "quadratica",
        "dipendenzaCoordinate": "no",
        "importanzaCoordinate": "uguale",
        "colonne": {
            "x": {"ruolo": "quantita", "usa": True},
            "y": {"ruolo": "quantita", "usa": True},
        },
    },
)
assert piano_numerico_con_mancanti["completo"] is False
assert piano_numerico_con_mancanti["percorsi"][0]["mancanti"]["strategia"] == "da_definire"
assert piano_numerico_con_mancanti["percorsi"][0]["stato"] == "da_completare"
assert any("strategia operativa" in avviso for avviso in piano_numerico_con_mancanti["avvisi"])

misti_con_mancanti = p.prepara_tabella(p.leggi_csv("x,categoria\n1,a\nNA,b\n3,a"))
piano_gower_con_mancanti = p.crea_piano_confronto(
    misti_con_mancanti,
    {"riga": "oggetto", "significatoMancanti": "sconosciuto", "colonne": {}},
)
assert piano_gower_con_mancanti["completo"] is True
assert piano_gower_con_mancanti["percorsi"][0]["mancanti"]["strategia"] == "esclusione_pairwise"
assert piano_gower_con_mancanti["percorsi"][0]["calcolo"]["disponibile"] is True

# Ogni misura numerica del registro deve essere raggiungibile da almeno un profilo di risposte.
dati_decisionali = p.prepara_tabella(p.leggi_csv("a,b\n1,2\n2,5\n4,3\n7,9"))

def misura_da(**risposte):
    piano = p.crea_piano_confronto(dati_decisionali, risposte_quantitative(**risposte))
    assert piano["completo"] is True, piano
    return piano["percorsi"][0]


assert misura_da(aggregazioneScarti="lineare")["idMisura"] == "manhattan"
assert misura_da(aggregazioneScarti="quadratica")["idMisura"] == "euclidean"
assert misura_da(aggregazioneScarti="massimo")["idMisura"] == "chebyshev"
assert misura_da(aggregazioneScarti="minkowski", ordineMinkowski="3")["idMisura"] == "minkowski"

pesata = misura_da(
    aggregazioneScarti="quadratica",
    importanzaCoordinate="diversa",
    pesiQuantitativi="1, 2",
)
assert pesata["idMisura"] == "weighted_minkowski"
assert pesata["parametri"] == {"pesi": [1.0, 2.0], "q": 2}

standardizzata = misura_da(
    comparabilitaScale="diverse",
    gestioneScale="interna",
    aggregazioneScarti="quadratica",
)
assert standardizzata["idMisura"] == "standardized_euclidean"
assert standardizzata["preelaborazione"]["origine"] == "valori_originali"

mahalanobis = misura_da(dipendenzaCoordinate="si")
assert mahalanobis["idMisura"] == "mahalanobis"
assert mahalanobis["preelaborazione"]["usaTabellaTrasformata"] is False

canberra = misura_da(
    confrontoQuantitativo="relativo",
    valoriVicinoZero="no",
)
assert canberra["idMisura"] == "canberra"

assert misura_da(confrontoQuantitativo="abbondanza")["idMisura"] == "bray_curtis"
assert misura_da(confrontoQuantitativo="frequenze")["idMisura"] == "chi_square"

raggiunte = {
    misura_da(aggregazioneScarti="lineare")["idMisura"],
    misura_da(aggregazioneScarti="quadratica")["idMisura"],
    misura_da(aggregazioneScarti="massimo")["idMisura"],
    misura_da(aggregazioneScarti="minkowski", ordineMinkowski="3")["idMisura"],
    pesata["idMisura"], standardizzata["idMisura"], mahalanobis["idMisura"],
    canberra["idMisura"],
    misura_da(confrontoQuantitativo="abbondanza")["idMisura"],
    misura_da(confrontoQuantitativo="frequenze")["idMisura"],
}
assert raggiunte == set(p.REGISTRO_MISURE_NUMERICHE)

pesi_invalidi = p.crea_piano_confronto(
    dati_decisionali,
    risposte_quantitative(importanzaCoordinate="diversa", pesiQuantitativi="1, 0"),
)
assert pesi_invalidi["completo"] is False
assert any("strettamente positivi" in avviso for avviso in pesi_invalidi["percorsi"][0]["avvisi"])

dati_singolari = p.prepara_tabella(p.leggi_csv("a,b\n1,2\n2,4\n3,6\n4,8"))
piano_singolare = p.crea_piano_confronto(
    dati_singolari,
    risposte_quantitative(dipendenzaCoordinate="si"),
)
assert piano_singolare["completo"] is False
assert any("covarianza empirica non è invertibile" in avviso for avviso in piano_singolare["percorsi"][0]["avvisi"])

dati_con_negativi = p.prepara_tabella(p.leggi_csv("a,b\n-2,1\n-1,2\n1,4\n3,7"))
piano_bray_non_valido = p.crea_piano_confronto(
    dati_con_negativi,
    risposte_quantitative(confrontoQuantitativo="abbondanza"),
)
assert piano_bray_non_valido["completo"] is False
assert any("non negativi" in avviso for avviso in piano_bray_non_valido["percorsi"][0]["avvisi"])

print("Tutti i test Python di preprocessing sono stati superati.")
