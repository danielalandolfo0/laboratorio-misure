"""Test della logica Python usata nel browser tramite Pyodide."""

from __future__ import annotations

import math
import json
from pathlib import Path
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
        "gestioneDipendenzaLineare": "mantieni",
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
assert robusto_comune["colonne"][1]["metodo"] == "zscore"
assert robusto_comune["colonne"][1]["metodoAutomatico"] == "zscore"
assert robusto_comune["colonne"][1]["motivo"] == "Non emergono outlier rilevanti."
quasi_uguali(p.statistiche([riga[0] for riga in robusto_comune["trasformate"]])["iqr"], 1)
quasi_uguali(p.statistiche([riga[1] for riga in robusto_comune["trasformate"]])["deviazione"], 1)

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

piano_sparso_auto = p.crea_piano_confronto(
    sparse,
    {
        "riga": "oggetto",
        "confrontoQuantitativo": "assoluto",
        "colonne": {
            "x": {"ruolo": "quantita", "usa": True},
            "id": {"ruolo": "identificativo", "usa": False},
        },
    },
)
assert piano_sparso_auto["diagnosi"]["indicatori"]["matriceSparsa"] is True
assert piano_sparso_auto["diagnosi"]["proposta"]["politicaPreelaborazione"] == "maxabs_automatico"
assert piano_sparso_auto["percorsi"][0]["preelaborazione"]["passi"][0]["metodo"] == "maxabs"

scale_simili = p.prepara_tabella(p.leggi_csv("a,b\n1,10\n2,11\n3,12"))
assert [colonna["metodo"] for colonna in scale_simili["colonne"]] == ["zscore", "zscore"]
quasi_uguali(scale_simili["trasformate"][0][0], -math.sqrt(1.5))
quasi_uguali(scale_simili["trasformate"][0][1], -math.sqrt(1.5))

scale_diverse = p.prepara_tabella(p.leggi_csv("a,b\n1,100\n2,200\n3,300"))
assert [colonna["metodo"] for colonna in scale_diverse["colonne"]] == ["zscore", "zscore"]

# Nel nuovo flusso le differenze numeriche evidenti sono gestite senza chiedere
# all'utente di conoscere il concetto di scala statistica.
risposte_accessibili = {
    "riga": "oggetto",
    "confrontoQuantitativo": "assoluto",
    "aggregazioneScarti": "quadratica",
    "importanzaCoordinate": "ignoto",
    # In questo esempio b = 100a: manteniamo intenzionalmente entrambe le
    # colonne e accettiamo che l'informazione ripetuta incida sul confronto.
    "gestioneDipendenzaLineare": "mantieni",
    "colonne": {
        "a": {"ruolo": "quantita", "usa": True},
        "b": {"ruolo": "quantita", "usa": True},
    },
}
piano_scale_automatiche = p.crea_piano_confronto(scale_diverse, risposte_accessibili)
assert piano_scale_automatiche["completo"] is True
assert piano_scale_automatiche["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is True
assert [
    passo["metodo"]
    for passo in piano_scale_automatiche["percorsi"][0]["preelaborazione"]["passi"]
] == ["zscore", "zscore"]

# Se le dispersioni sembrano simili ma le colonne hanno significati diversi,
# la risposta semantica attiva comunque un riequilibrio prudenziale.
piano_quantita_diverse = p.crea_piano_confronto(
    scale_simili,
    {**risposte_accessibili, "tipoQuantita": "diverse"},
)
assert piano_quantita_diverse["completo"] is True
assert [
    passo["metodo"]
    for passo in piano_quantita_diverse["percorsi"][0]["preelaborazione"]["passi"]
] == ["zscore", "zscore"]

piano_scelta_consigliata = p.crea_piano_confronto(
    scale_simili,
    {
        **risposte_accessibili,
        "confrontoQuantitativo": "ignoto",
        "aggregazioneScarti": "ignoto",
    },
)
assert piano_scelta_consigliata["completo"] is True
assert piano_scelta_consigliata["percorsi"][0]["idMisura"] == "euclidean"
assert piano_scelta_consigliata["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is True

piano_abbondanze_accessibile = p.crea_piano_confronto(
    scale_simili,
    {**risposte_accessibili, "confrontoQuantitativo": "abbondanza"},
)
assert piano_abbondanze_accessibile["completo"] is True
assert piano_abbondanze_accessibile["percorsi"][0]["idMisura"] == "bray_curtis"
assert piano_abbondanze_accessibile["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is False

# Nuovo motore: per le quantità ordinarie la proposta è prodotta dai dati e può
# essere modificata esplicitamente, ma non richiede domande tecniche preliminari.
def risposte_automatiche(nomi):
    return {
        "riga": "oggetto",
        "confrontoQuantitativo": "assoluto",
        "colonne": {nome: {"ruolo": "quantita", "usa": True} for nome in nomi},
    }


def carica_fixture(nome):
    percorso = Path(__file__).resolve().parents[1] / "examples" / "collaudo" / nome
    return p.prepara_tabella(p.leggi_csv(percorso.read_text(encoding="utf-8")))


dati_debolmente_correlati = p.prepara_tabella(p.leggi_csv(
    "a,b\n1,8\n2,1\n3,6\n4,3\n5,9\n6,2\n7,7\n8,4\n9,5\n10,10"
))
piano_auto_euclideo = p.crea_piano_confronto(
    dati_debolmente_correlati, risposte_automatiche(["a", "b"])
)
assert piano_auto_euclideo["diagnosi"]["famigliaId"] == "quantitativo"
assert piano_auto_euclideo["diagnosi"]["proposta"]["idMisura"] == "euclidean"
assert piano_auto_euclideo["percorsi"][0]["idMisura"] == "euclidean"
assert [
    passo["metodo"] for passo in piano_auto_euclideo["percorsi"][0]["preelaborazione"]["passi"]
] == ["zscore", "zscore"]

dati_fortemente_correlati = p.prepara_tabella(p.leggi_csv(
    "a,b\n1,2.1\n2,3.8\n3,6.3\n4,7.7\n5,10.4\n6,11.6\n"
    "7,14.5\n8,15.7\n9,18.2\n10,20.4\n11,21.5\n12,24.3"
))
piano_auto_mahalanobis = p.crea_piano_confronto(
    dati_fortemente_correlati, risposte_automatiche(["a", "b"])
)
assert piano_auto_mahalanobis["diagnosi"]["indicatori"]["correlazioniForti"] is True
assert piano_auto_mahalanobis["diagnosi"]["indicatori"]["covarianzaUtilizzabile"] is True
assert piano_auto_mahalanobis["percorsi"][0]["idMisura"] == "mahalanobis"
assert piano_auto_mahalanobis["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is True

dati_correlati_campione_limitato = p.prepara_tabella(p.leggi_csv(
    "a,b\n1,2.1\n2,3.8\n3,6.3\n4,7.7\n5,10.4\n6,11.6\n7,14.5\n8,15.7"
))
piano_campione_limitato = p.crea_piano_confronto(
    dati_correlati_campione_limitato, risposte_automatiche(["a", "b"])
)
indicatori_limitati = piano_campione_limitato["diagnosi"]["indicatori"]
assert indicatori_limitati["correlazioniForti"] is True
assert indicatori_limitati["covarianzaUtilizzabile"] is True
assert indicatori_limitati["campioneLimitato"] is True
assert piano_campione_limitato["diagnosi"]["proposta"]["idMisura"] == "euclidean"
assert piano_campione_limitato["percorsi"][0]["idMisura"] == "euclidean"
assert "Per prudenza" in piano_campione_limitato["diagnosi"]["proposta"]["motivo"]

piano_campione_limitato_manuale = p.crea_piano_confronto(
    dati_correlati_campione_limitato,
    {**risposte_automatiche(["a", "b"]), "misuraNumericaManuale": "mahalanobis"},
)
assert piano_campione_limitato_manuale["percorsi"][0]["idMisura"] == "mahalanobis"
assert piano_campione_limitato_manuale["percorsi"][0]["stato"] == "pronto"

diagnosi_json = json.loads(p.analizza_diagnosi_numerica_json(
    "a,b\n1,2.1\n2,3.8\n3,6.3\n4,7.7\n5,10.4\n6,11.6\n7,14.5\n8,15.7",
    "[]", '["a","b"]',
))
assert diagnosi_json["ok"] is True
assert diagnosi_json["diagnosi"]["campioneLimitato"] is True
assert diagnosi_json["diagnosi"]["proposta"]["idMisura"] == "euclidean"

dati_correlati_singolari = p.prepara_tabella(p.leggi_csv(
    "a,b\n1,2\n2,4\n3,6\n4,8\n5,10\n6,12\n7,14\n8,16\n9,18\n10,20\n11,22\n12,24"
))
piano_auto_singolare = p.crea_piano_confronto(
    dati_correlati_singolari, risposte_automatiche(["a", "b"])
)
assert piano_auto_singolare["diagnosi"]["indicatori"]["correlazioniForti"] is True
assert piano_auto_singolare["diagnosi"]["indicatori"]["covarianzaUtilizzabile"] is False
assert piano_auto_singolare["percorsi"][0]["idMisura"] == "euclidean"

piano_auto_robusto = p.crea_piano_confronto(
    robusto_comune,
    {**risposte_automatiche(["a", "b"]), "significatoEstremi": "reali"},
)
assert piano_auto_robusto["diagnosi"]["proposta"]["idMisura"] == "manhattan"
assert piano_auto_robusto["percorsi"][0]["idMisura"] == "manhattan"
assert [
    passo["metodo"] for passo in piano_auto_robusto["percorsi"][0]["preelaborazione"]["passi"]
] == ["robusto", "robusto"]

# Un IQR nullo in una colonna non deve cancellare gli outlier rilevati in
# un'altra colonna; impedisce soltanto di forzare la scala robusta su tutte.
dati_iqr_misto = p.prepara_tabella(p.leggi_csv(
    "a,b\n1,0\n2,0\n3,0\n4,0\n5,0\n6,0\n7,0\n8,2\n100,0"
))
analisi_iqr_misto = {c["nome"]: c for c in dati_iqr_misto["colonne"]}
diagnosi_iqr_misto = p._diagnosi_numerica(["a", "b"], analisi_iqr_misto)
assert diagnosi_iqr_misto["outlier"] is True
assert diagnosi_iqr_misto["colonneOutlier"] == ["a"]
assert diagnosi_iqr_misto["colonneEstremeNonRobuste"] == ["b"]
assert diagnosi_iqr_misto["robustoApplicabile"] is False
assert diagnosi_iqr_misto["proposta"]["idMisura"] == "manhattan"
assert diagnosi_iqr_misto["proposta"]["politicaPreelaborazione"] == "zscore_automatico"

dati_misti_auto = p.prepara_tabella(p.leggi_csv("a,categoria\n1,x\n2,y\n3,x\n4,z"))
piano_misto_auto = p.crea_piano_confronto(
    dati_misti_auto, {"riga": "oggetto", "colonne": {}}
)
assert piano_misto_auto["diagnosi"]["famigliaId"] == "misto"
assert piano_misto_auto["diagnosi"]["proposta"]["idMisura"] == "gower_classica"
assert piano_misto_auto["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is False

# I CSV distribuiti con il sito coprono stabilmente i sei rami principali.
fixture_ordinaria = carica_fixture("01_numerici_ordinari.csv")
fixture_outlier = carica_fixture("02_numerici_outlier.csv")
fixture_correlata = carica_fixture("03_numerici_correlati.csv")
fixture_singolare = carica_fixture("04_numerici_covarianza_singolare.csv")
fixture_sparsa = carica_fixture("05_numerici_sparsi.csv")
fixture_mista = carica_fixture("06_dati_misti.csv")

assert p.crea_piano_confronto(
    fixture_ordinaria, risposte_automatiche(["a", "b"])
)["diagnosi"]["proposta"]["idMisura"] == "euclidean"

piano_fixture_outlier = p.crea_piano_confronto(
    fixture_outlier,
    {**risposte_automatiche(["a", "b"]), "significatoEstremi": "reali"},
)
assert piano_fixture_outlier["diagnosi"]["proposta"]["idMisura"] == "manhattan"
assert {
    passo["metodo"] for passo in piano_fixture_outlier["percorsi"][0]["preelaborazione"]["passi"]
} == {"robusto"}

assert p.crea_piano_confronto(
    fixture_correlata, risposte_automatiche(["a", "b"])
)["diagnosi"]["proposta"]["idMisura"] == "mahalanobis"

piano_fixture_singolare = p.crea_piano_confronto(
    fixture_singolare, risposte_automatiche(["a", "b"])
)
assert piano_fixture_singolare["diagnosi"]["indicatori"]["covarianzaUtilizzabile"] is False
assert piano_fixture_singolare["diagnosi"]["proposta"]["idMisura"] == "euclidean"
assert piano_fixture_singolare["completo"] is False

risposte_singolari_confermate = {
    **risposte_automatiche(["a", "b"]),
    "gestioneDipendenzaLineare": "mantieni",
}
assert p.crea_piano_confronto(
    fixture_singolare, risposte_singolari_confermate
)["completo"] is True

piano_fixture_sparsa = p.crea_piano_confronto(
    fixture_sparsa,
    {**risposte_automatiche(["x", "y"]), "significatoEstremi": "reali"},
)
assert piano_fixture_sparsa["diagnosi"]["indicatori"]["matriceSparsa"] is True
assert piano_fixture_sparsa["diagnosi"]["proposta"]["politicaPreelaborazione"] == "maxabs_automatico"

piano_fixture_mista = p.crea_piano_confronto(
    fixture_mista, {"riga": "persona", "zeriCondivisi": "si", "colonne": {}}
)
assert piano_fixture_mista["diagnosi"]["famigliaId"] == "misto"
assert piano_fixture_mista["diagnosi"]["proposta"]["idMisura"] == "gower_classica"
assert piano_fixture_mista["percorsi"][0]["preelaborazione"]["usaTabellaTrasformata"] is False

def verifica_matrice_finale(risultato_matrice, dimensione):
    matrice = risultato_matrice["matrice"]
    assert len(matrice) == dimensione
    assert all(len(riga) == dimensione for riga in matrice)
    assert all(matrice[i][i] == 0 for i in range(dimensione))
    for i in range(dimensione):
        for j in range(dimensione):
            assert matrice[i][j] == matrice[j][i]
            assert matrice[i][j] is None or math.isfinite(matrice[i][j])


matrici_fixture = [
    p.calcola_matrice_numerica(fixture_ordinaria, risposte_automatiche(["a", "b"])),
    p.calcola_matrice_numerica(
        fixture_outlier,
        {**risposte_automatiche(["a", "b"]), "significatoEstremi": "reali"},
    ),
    p.calcola_matrice_numerica(fixture_correlata, risposte_automatiche(["a", "b"])),
    p.calcola_matrice_numerica(fixture_singolare, risposte_singolari_confermate),
    p.calcola_matrice_numerica(
        fixture_sparsa,
        {**risposte_automatiche(["x", "y"]), "significatoEstremi": "reali"},
    ),
    p.calcola_matrice_gower(
        fixture_mista,
        {"riga": "persona", "zeriCondivisi": "si", "colonne": {}},
    ),
]
metodi_fixture = [
    "Distanza euclidea",
    "Distanza di Manhattan",
    "Distanza di Mahalanobis",
    "Distanza euclidea",
    "Distanza euclidea",
    "Dissimilarità di Gower classica",
]
dimensioni_fixture = [10, 8, 12, 12, 10, 8]
for risultato_matrice, metodo, dimensione in zip(
    matrici_fixture, metodi_fixture, dimensioni_fixture
):
    assert risultato_matrice["metodo"] == metodo
    verifica_matrice_finale(risultato_matrice, dimensione)

una_numerica = p.prepara_tabella(p.leggi_csv("a,gruppo\n1,x\n2,y\n3,z"))
assert una_numerica["colonne"][0]["metodo"] == "zscore"
assert una_numerica["colonne"][0]["motivo"] == "Non emergono outlier rilevanti."

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
assert misure_piano["a"] == "Differenza numerica"
assert misure_piano["b"] == "Differenza numerica"
assert misure_piano["flag"] == "Confronto asimmetrico di Jaccard"
assert misure_piano["gruppo"] == "Uguale o diverso"
assert piano_semplice["conteggioPercorsi"] == 1
assert piano_semplice["percorsi"][0]["metodo"] == "Dissimilarità di Gower classica"
assert piano_semplice["versioneContratto"] == 4
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
assert piano_numerico["percorsi"][0]["calcolo"]["disponibile"] is True

matrice_numerica = p.calcola_matrice_numerica(scale_diverse, risposte_accessibili)
assert matrice_numerica["metodo"] == "Distanza euclidea"
assert matrice_numerica["matrice"][0][0] == 0
quasi_uguali(matrice_numerica["matrice"][0][1], math.sqrt(3))
assert matrice_numerica["matrice"][1][0] == matrice_numerica["matrice"][0][1]
assert matrice_numerica["csv"].splitlines()[0] == "Riga;Riga 1;Riga 2;Riga 3"

matrice_bray = p.calcola_matrice_numerica(
    scale_simili,
    {**risposte_accessibili, "confrontoQuantitativo": "abbondanza"},
)
quasi_uguali(matrice_bray["matrice"][0][1], 2 / 24)

quasi_uguali(p._distanza_numerica([1, 2], [4, 6], "manhattan", {}), 7)
quasi_uguali(p._distanza_numerica([1, 2], [4, 6], "euclidean", {}), 5)
quasi_uguali(p._distanza_numerica([1, 2], [4, 6], "chebyshev", {}), 4)
quasi_uguali(p._distanza_numerica([1, 2], [4, 6], "minkowski", {"q": 3}), 91 ** (1 / 3))
quasi_uguali(
    p._distanza_numerica([1, 2], [4, 6], "weighted_minkowski", {"q": 2, "pesi": [2, 0.5]}),
    math.sqrt(26),
)
quasi_uguali(p._distanza_numerica([0, 2], [0, 6], "canberra", {}), 0.5)
quasi_uguali(p._distanza_numerica([1, 2], [3, 4], "chi_square", {}), math.sqrt(1 + 2 / 3))

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

# I mancanti numerici diventano operativi per colonna e la stessa politica
# governa piano, anteprima, matrice ed etichette delle righe.
dati_numerici_mancanti = p.prepara_tabella(p.leggi_csv(
    "x,y,id\n1,10,A\n2,NA,B\nNA,30,C\n4,40,D"
))
risposte_mancanti_numerici = {
    "riga": "oggetto",
    "significatoMancanti": "sconosciuto",
    "confrontoQuantitativo": "assoluto",
    "aggregazioneScarti": "quadratica",
    "importanzaCoordinate": "uguale",
    "gestioneDipendenzaLineare": "mantieni",
    "riscalamentoConfermato": True,
    "mancantiNumericiPerColonna": {
        "x": "imputa_mediana",
        "y": "imputa_media",
    },
    "colonne": {
        "x": {"ruolo": "quantita", "usa": True},
        "y": {"ruolo": "quantita", "usa": True},
        "id": {"ruolo": "identificativo", "usa": False},
    },
}
piano_imputazione = p.crea_piano_confronto(
    dati_numerici_mancanti, risposte_mancanti_numerici
)
assert piano_imputazione["completo"] is True, piano_imputazione
assert piano_imputazione["percorsi"][0]["mancanti"]["pronta"] is True
assert "mediana osservata" in piano_imputazione["percorsi"][0]["mancanti"]["descrizione"]
assert "media osservata" in piano_imputazione["percorsi"][0]["mancanti"]["descrizione"]
matrice_imputata = p.calcola_matrice_numerica(
    dati_numerici_mancanti, risposte_mancanti_numerici
)
verifica_matrice_finale(matrice_imputata, 4)
assert matrice_imputata["etichette"] == ["A", "B", "C", "D"]

risposte_esclusione = {
    **risposte_mancanti_numerici,
    "mancantiNumericiPerColonna": {
        "x": "escludi_riga",
        "y": "escludi_riga",
    },
}
matrice_esclusione = p.calcola_matrice_numerica(
    dati_numerici_mancanti, risposte_esclusione
)
verifica_matrice_finale(matrice_esclusione, 2)
assert matrice_esclusione["etichette"] == ["A", "D"]
assert "Righe escluse: 2" in matrice_esclusione["nota"]

risposte_zero = {
    **risposte_mancanti_numerici,
    "significatoMancanti": "assenza",
    "mancantiNumericiPerColonna": {"x": "zero", "y": "zero"},
}
assert p.crea_piano_confronto(
    dati_numerici_mancanti, risposte_zero
)["completo"] is True

dati_senza_righe_complete = p.prepara_tabella(p.leggi_csv(
    "x,y\n1,NA\nNA,2\nNA,3"
))
risposte_senza_righe = {
    "riga": "oggetto",
    "significatoMancanti": "sconosciuto",
    "confrontoQuantitativo": "assoluto",
    "aggregazioneScarti": "quadratica",
    "importanzaCoordinate": "uguale",
    "gestioneDipendenzaLineare": "mantieni",
    "mancantiNumericiPerColonna": {"x": "escludi_riga", "y": "escludi_riga"},
    "colonne": {
        "x": {"ruolo": "quantita", "usa": True},
        "y": {"ruolo": "quantita", "usa": True},
    },
}
assert p.crea_piano_confronto(
    dati_senza_righe_complete, risposte_senza_righe
)["completo"] is False

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

pesata_decimali_italiani = misura_da(
    aggregazioneScarti="quadratica",
    importanzaCoordinate="diversa",
    pesiQuantitativi="1; 2,5",
)
assert pesata_decimali_italiani["parametri"] == {"pesi": [1.0, 2.5], "q": 2}

chebyshev_pesata = misura_da(
    misuraNumericaManuale="weighted_chebyshev",
    pesiMisuraManuale="1; 2",
)
assert chebyshev_pesata["idMisura"] == "weighted_chebyshev"
assert chebyshev_pesata["parametri"] == {"pesi": [1.0, 2.0]}

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
    pesata["idMisura"], chebyshev_pesata["idMisura"],
    standardizzata["idMisura"], mahalanobis["idMisura"],
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


# Un CSV può contenere una serie temporale e colonne indipendenti.
dati_con_gruppo = p.prepara_tabella(p.leggi_csv("a,b,c\\n1,2,10\\n2,3,12\\n4,5,15\\n8,9,20".replace("\\n", "\n")))
risposte_con_gruppo = {
    "riga": "oggetto",
    "confrontoQuantitativo": "assoluto",
    "aggregazioneScarti": "quadratica",
    "importanzaCoordinate": "uguale",
    "gestioneDipendenzaLineare": "mantieni",
    "riscalamentoConfermato": True,
    "colonne": {
        "a": {"ruolo": "quantita", "usa": True},
        "b": {"ruolo": "quantita", "usa": True},
        "c": {"ruolo": "quantita", "usa": True},
    },
    "gruppi": [{"id": "gruppo-1", "nome": "Serie", "tipo": "tempo"}],
    "assegnazioni": {"a": "gruppo-1", "b": "gruppo-1"},
    "ritardo-gruppo-1": "si",
}
piano_con_gruppo = p.crea_piano_confronto(dati_con_gruppo, risposte_con_gruppo)
assert piano_con_gruppo["conteggioPercorsi"] == 2
assert piano_con_gruppo["completo"] is True
assert all(percorso["calcolo"]["disponibile"] for percorso in piano_con_gruppo["percorsi"])
matrice_con_gruppo = p.calcola_matrice(dati_con_gruppo, risposte_con_gruppo)
verifica_matrice_finale(matrice_con_gruppo, 4)
assert matrice_con_gruppo["metodo"] == "Dissimilarità complessiva pesata"
assert len(matrice_con_gruppo["contributi"]) == 2
assert all(0 <= valore <= 1 for riga in matrice_con_gruppo["matrice"] for valore in riga)
risposte_gruppo_pesato = {
    **risposte_con_gruppo,
    "pesiPercorsi": {"percorso-1": "4", "percorso-2": "1"},
}
matrice_gruppo_pesato = p.calcola_matrice(dati_con_gruppo, risposte_gruppo_pesato)
assert matrice_gruppo_pesato["matrice"] != matrice_con_gruppo["matrice"]
assert [contributo["peso"] for contributo in matrice_gruppo_pesato["contributi"]] == [4.0, 1.0]
assert p.crea_piano_confronto(
    dati_con_gruppo,
    {**risposte_con_gruppo, "pesiPercorsi": {"percorso-1": "0"}},
)["completo"] is False
assert {tuple(percorso["colonne"]) for percorso in piano_con_gruppo["percorsi"]} == {
    ("c",), ("a", "b")
}
assert next(percorso for percorso in piano_con_gruppo["percorsi"] if percorso["tipo"] == "gruppo")["metodo"] == "Dynamic Time Warping"

# I percorsi specializzati pronti producono davvero una matrice, non soltanto
# un'etichetta nel piano.
for risposta_profilo in ("valori_vicini", "proporzioni", "andamento", "ordine"):
    risposte_profilo = {
        "riga": "oggetto",
        "colonne": {
            "a": {"ruolo": "quantita", "usa": True},
            "b": {"ruolo": "quantita", "usa": True},
            "c": {"ruolo": "quantita", "usa": True},
        },
        "gruppi": [{"id": "profilo", "nome": "Profilo", "tipo": "ripetute"}],
        "assegnazioni": {"a": "profilo", "b": "profilo", "c": "profilo"},
        "somiglianza-profilo": risposta_profilo,
    }
    verifica_matrice_finale(p.calcola_matrice(dati_con_gruppo, risposte_profilo), 4)

risposte_tempo_puntuale = {
    **risposte_con_gruppo,
    "ritardo-gruppo-1": "no",
}
verifica_matrice_finale(p.calcola_matrice(dati_con_gruppo, risposte_tempo_puntuale), 4)

dati_composizionali = p.prepara_tabella(p.leggi_csv("a,b,c\n1,2,7\n2,2,6\n4,3,3"))
risposte_composizionali = {
    "riga": "oggetto",
    "colonne": {
        nome: {"ruolo": "quantita", "usa": True} for nome in ("a", "b", "c")
    },
    "gruppi": [{"id": "parti", "nome": "Composizione", "tipo": "parti"}],
    "assegnazioni": {nome: "parti" for nome in ("a", "b", "c")},
    "totale-parti": "si",
}
matrice_aitchison = p.calcola_matrice(dati_composizionali, risposte_composizionali)
verifica_matrice_finale(matrice_aitchison, 3)
assert matrice_aitchison["metodo"] == "Distanza composizionale di Aitchison"

dati_testo = p.prepara_tabella(p.leggi_csv("testo,id\ncasa,A\ncassa,B\ncane,C"))
risposte_testo = {
    "riga": "oggetto",
    "colonne": {
        "testo": {"ruolo": "testo", "usa": True},
        "id": {"ruolo": "identificativo", "usa": False},
    },
}
matrice_testo = p.calcola_matrice(dati_testo, risposte_testo)
verifica_matrice_finale(matrice_testo, 3)
assert matrice_testo["matrice"][0][1] == 0.2

# Se un percorso numerico esclude una riga, gli altri percorsi possono ancora
# contribuire alle coppie che la contengono; gli indici restano allineati.
dati_multipercorso_mancanti = p.prepara_tabella(p.leggi_csv(
    "x,testo,id\n1,casa,A\nNA,cassa,B\n3,cane,C"
))
risposte_multipercorso_mancanti = {
    "riga": "oggetto",
    "significatoMancanti": "sconosciuto",
    "confrontoQuantitativo": "assoluto",
    "aggregazioneScarti": "quadratica",
    "importanzaCoordinate": "uguale",
    "gestioneDipendenzaLineare": "mantieni",
    "riscalamentoConfermato": True,
    "mancantiNumericiPerColonna": {"x": "escludi_riga"},
    "colonne": {
        "x": {"ruolo": "quantita", "usa": True},
        "testo": {"ruolo": "testo", "usa": True},
        "id": {"ruolo": "identificativo", "usa": False},
    },
}
matrice_multipercorso_mancanti = p.calcola_matrice(
    dati_multipercorso_mancanti, risposte_multipercorso_mancanti
)
verifica_matrice_finale(matrice_multipercorso_mancanti, 3)
assert matrice_multipercorso_mancanti["etichette"] == ["A", "B", "C"]
assert matrice_multipercorso_mancanti["matrice"][0][1] is not None

# I mancanti nei percorsi specializzati hanno una politica operativa esplicita.
dati_tempo_mancanti = p.prepara_tabella(p.leggi_csv(
    "t0,t1,t2,id\n1,NA,3,A\n2,3,4,B\n1,2,3,C\nNA,2,3,D"
))
risposte_tempo_mancanti = {
    "riga": "oggetto",
    "significatoMancanti": "sconosciuto",
    "significatoEstremi": "reali",
    "colonne": {
        "t0": {"ruolo": "quantita", "usa": True},
        "t1": {"ruolo": "quantita", "usa": True},
        "t2": {"ruolo": "quantita", "usa": True},
        "id": {"ruolo": "identificativo", "usa": False},
    },
    "gruppi": [{"id": "tempo", "nome": "Serie", "tipo": "tempo"}],
    "assegnazioni": {nome: "tempo" for nome in ("t0", "t1", "t2")},
    "ritardo-tempo": "si",
}
assert p.crea_piano_confronto(
    dati_tempo_mancanti, risposte_tempo_mancanti
)["completo"] is False
risposte_tempo_interpolate = {
    **risposte_tempo_mancanti,
    "mancanti-gruppo-tempo": "interpola_lineare",
}
piano_tempo_interpolato = p.crea_piano_confronto(
    dati_tempo_mancanti, risposte_tempo_interpolate
)
assert piano_tempo_interpolato["completo"] is True, piano_tempo_interpolato
matrice_tempo_interpolata = p.calcola_matrice(
    dati_tempo_mancanti, risposte_tempo_interpolate
)
assert matrice_tempo_interpolata["matrice"][0][1] is not None
assert matrice_tempo_interpolata["matrice"][0][3] is None
assert "interpolati linearmente" in matrice_tempo_interpolata["nota"]

risposte_tempo_esclusione = {
    **risposte_tempo_mancanti,
    "mancanti-gruppo-tempo": "escludi_percorso",
}
matrice_tempo_esclusione = p.calcola_matrice(
    dati_tempo_mancanti, risposte_tempo_esclusione
)
assert matrice_tempo_esclusione["matrice"][1][2] is not None
assert matrice_tempo_esclusione["matrice"][0][1] is None

risposte_profilo_mancanti = {
    **risposte_tempo_mancanti,
    "gruppi": [{"id": "profilo", "nome": "Profilo", "tipo": "ripetute"}],
    "assegnazioni": {nome: "profilo" for nome in ("t0", "t1", "t2")},
    "somiglianza-profilo": "valori_vicini",
    "mancanti-gruppo-profilo": "imputa_mediana",
}
matrice_profilo_imputata = p.calcola_matrice(
    dati_tempo_mancanti, risposte_profilo_mancanti
)
verifica_matrice_finale(matrice_profilo_imputata, 4)
assert "mediana osservata" in matrice_profilo_imputata["nota"]

dati_testo_mancante = p.prepara_tabella(p.leggi_csv(
    "testo,id\ncasa,A\nNA,B\ncane,C"
))
risposte_testo_mancante = {
    "riga": "oggetto",
    "significatoMancanti": "sconosciuto",
    "colonne": {
        "testo": {"ruolo": "testo", "usa": True},
        "id": {"ruolo": "identificativo", "usa": False},
    },
}
assert p.crea_piano_confronto(
    dati_testo_mancante, risposte_testo_mancante
)["completo"] is False
matrice_testo_esclusione = p.calcola_matrice(
    dati_testo_mancante,
    {**risposte_testo_mancante, "mancantiSpecializzatiPerColonna": {"testo": "escludi_percorso"}},
)
assert matrice_testo_esclusione["matrice"][0][1] is None
matrice_testo_vuoto = p.calcola_matrice(
    dati_testo_mancante,
    {**risposte_testo_mancante, "mancantiSpecializzatiPerColonna": {"testo": "stringa_vuota"}},
)
assert matrice_testo_vuoto["matrice"][0][1] == 1.0

# Gli zeri di una composizione non vengono mai corretti implicitamente.
dati_aitchison_zero = p.prepara_tabella(p.leggi_csv(
    "a,b,c\n1,0,9\n2,2,6\n4,3,3"
))
risposte_aitchison_zero = {
    "riga": "oggetto",
    "colonne": {
        nome: {"ruolo": "quantita", "usa": True} for nome in ("a", "b", "c")
    },
    "gruppi": [{"id": "parti-zero", "nome": "Composizione", "tipo": "parti"}],
    "assegnazioni": {nome: "parti-zero" for nome in ("a", "b", "c")},
    "totale-parti-zero": "si",
}
assert p.crea_piano_confronto(
    dati_aitchison_zero, risposte_aitchison_zero
)["completo"] is False
risposte_aitchison_sostituzione = {
    **risposte_aitchison_zero,
    "zeri-aitchison-parti-zero": "sostituisci",
}
matrice_aitchison_zero = p.calcola_matrice(
    dati_aitchison_zero, risposte_aitchison_sostituzione
)
verifica_matrice_finale(matrice_aitchison_zero, 3)
assert "sostituiti con 0.05" in matrice_aitchison_zero["nota"]
assert p.crea_piano_confronto(
    dati_aitchison_zero,
    {**risposte_aitchison_zero, "zeri-aitchison-parti-zero": "strutturali"},
)["completo"] is False

# Anche una composizione con molti zeri conserva una massa positiva residua.
dati_aitchison_molti_zeri = p.prepara_tabella(p.leggi_csv(
    "a,b,c,d,e\n10,0,0,0,0\n2,2,2,2,2\n3,3,3,3,3"
))
risposte_aitchison_molti_zeri = {
    "riga": "oggetto",
    "colonne": {
        nome: {"ruolo": "quantita", "usa": True} for nome in ("a", "b", "c", "d", "e")
    },
    "gruppi": [{"id": "parti-estreme", "nome": "Composizione", "tipo": "parti"}],
    "assegnazioni": {
        nome: "parti-estreme" for nome in ("a", "b", "c", "d", "e")
    },
    "totale-parti-estreme": "si",
    "zeri-aitchison-parti-estreme": "sostituisci",
}
matrice_aitchison_molti_zeri = p.calcola_matrice(
    dati_aitchison_molti_zeri, risposte_aitchison_molti_zeri
)
verifica_matrice_finale(matrice_aitchison_molti_zeri, 3)
assert "sostituiti con 0.1" in matrice_aitchison_molti_zeri["nota"]

# Un codice numerico o un livello ordinale non diventa una serie solo perché contiene numeri.
risposte_gruppo_incoerente = {
    **risposte_con_gruppo,
    "colonne": {
        **risposte_con_gruppo["colonne"],
        "a": {"ruolo": "livello", "usa": True},
    },
}
piano_gruppo_incoerente = p.crea_piano_confronto(dati_con_gruppo, risposte_gruppo_incoerente)
blocco_gruppo_incoerente = next(
    blocco for blocco in piano_gruppo_incoerente["blocchi"] if blocco["nome"] == "Serie"
)
assert blocco_gruppo_incoerente["stato"] == "da_completare"
assert "non codici o livelli" in blocco_gruppo_incoerente["motivo"]

# Aitchison non può essere proposta come pronta con componenti negative.
composizione_negativa = p.prepara_tabella(p.leggi_csv("a,b\\n1,2\\n-1,3\\n2,4".replace("\\n", "\n")))
piano_composizione_negativa = p.crea_piano_confronto(
    composizione_negativa,
    {
        "riga": "oggetto",
        "colonne": {
            "a": {"ruolo": "quantita", "usa": True},
            "b": {"ruolo": "quantita", "usa": True},
        },
        "gruppi": [{"id": "gruppo-1", "nome": "Composizione", "tipo": "parti"}],
        "assegnazioni": {"a": "gruppo-1", "b": "gruppo-1"},
        "totale-gruppo-1": "si",
    },
)
blocco_composizione_negativa = piano_composizione_negativa["blocchi"][0]
assert blocco_composizione_negativa["stato"] == "da_completare"
assert any("valori negativi" in avviso for avviso in blocco_composizione_negativa["avvisi"])


# Una scelta esplicita di non compensare le dipendenze non deve suggerire Mahalanobis.
risposte_no_mahalanobis = risposte_automatiche(["a", "b"])
risposte_no_mahalanobis.update({"dipendenzaCoordinate": "no", "aggregazioneScarti": "automatico"})
piano_senza_correzione = p.crea_piano_confronto(fixture_correlata, risposte_no_mahalanobis)
assert piano_senza_correzione["percorsi"][0]["idMisura"] == "euclidean"

# Nei misti con due quantitative indipendenti il percorso resta Gower,
# ma la scelta sulla normalizzazione quantitativa deve essere rispettata.
misti_con_due_quantita = p.prepara_tabella(p.leggi_csv(
    "a,b,categoria\\n1,2,rosso\\n2,5,blu\\n4,3,rosso\\n7,9,verde".replace("\\n", "\n")
))
base_misto_due = {
    "riga": "oggetto",
    "colonne": {
        "a": {"ruolo": "quantita", "usa": True},
        "b": {"ruolo": "quantita", "usa": True},
        "categoria": {"ruolo": "categoria", "usa": True},
    },
}
piano_misto_classico = p.crea_piano_confronto(
    misti_con_due_quantita, {**base_misto_due, "tipoGowerNumeriche": "classica"}
)
piano_misto_robusto = p.crea_piano_confronto(
    misti_con_due_quantita, {**base_misto_due, "tipoGowerNumeriche": "robusta"}
)
assert piano_misto_classico["percorsi"][0]["metodo"] == "Dissimilarità di Gower classica"
assert piano_misto_robusto["percorsi"][0]["metodo"] == "Dissimilarità di Gower robusta"
assert piano_misto_robusto["percorsi"][0]["calcolo"]["disponibile"] is True


# Sono riconosciute anche le colonne sì/no, senza imporre un codice 0/1.
rilevata_testuale = p.prepara_tabella(p.leggi_csv("presente,classe\\nsì,A\\nno,B".replace("\\n", "\n")))
assert rilevata_testuale["questionario"]["colonne"][0]["ruoloSuggerito"] == "presenza"

# --- Gower: regressioni sulle scelte semantiche e sui pesi. ---
def piano_gower_per(csv_testo, **config):
    preparato = p.prepara_tabella(p.leggi_csv(csv_testo))
    interpretazione = {"riga": "oggetto", **config}
    return preparato, p.crea_piano_confronto(preparato, interpretazione), interpretazione


dati_pesati, piano_pesato, risposte_pesate = piano_gower_per(
    "a,classe\n0,A\n10,B\n10,A",
    colonne={"a": {"ruolo": "quantita", "usa": True},
             "classe": {"ruolo": "categoria", "usa": True}},
    pesiGower={"a": "2", "classe": "1"},
)
assert piano_pesato["completo"], piano_pesato
matrice_pesata = p.calcola_matrice_gower(dati_pesati, risposte_pesate)
quasi_uguali(matrice_pesata["matrice"][0][2], 2 / 3)
assert piano_pesato["percorsi"][0]["pesiGower"] == {"a": 2.0, "classe": 1.0}
piano_peso_nullo = p.crea_piano_confronto(
    dati_pesati, {**risposte_pesate, "pesiGower": {"a": "0"}}
)
assert piano_peso_nullo["completo"] is False
assert any("strettamente positivo" in testo
           for testo in piano_peso_nullo["percorsi"][0]["avvisi"])

# Le colonne costanti non riducono le distanze delle caratteristiche informative.
dati_costanti, piano_costanti, risposte_costanti = piano_gower_per(
    "classe,costante\nrosso,5\nblu,5\nrosso,5",
    colonne={"classe": {"ruolo": "categoria", "usa": True},
             "costante": {"ruolo": "quantita", "usa": True}},
)
assert piano_costanti["completo"], piano_costanti
assert piano_costanti["percorsi"][0]["colonneEscluseGower"] == ["costante"]
quasi_uguali(p.calcola_matrice_gower(dati_costanti, risposte_costanti)["matrice"][0][1], 1)
tutti_costanti, piano_tutti_costanti, _ = piano_gower_per(
    "classe,costante\nrosso,5\nrosso,5\nrosso,5",
    colonne={"classe": {"ruolo": "categoria", "usa": True},
             "costante": {"ruolo": "quantita", "usa": True}},
)
assert not piano_tutti_costanti["completo"]
assert any("costanti" in testo for testo in piano_tutti_costanti["percorsi"][0]["avvisi"])

# "Sconosciuto" omette i valori vuoti, "assenza" diventa un valore vero e proprio.
dati_assenze, piano_sconosciuto, risposte_sconosciuto = piano_gower_per(
    "presente,classe\n1,A\n,A\n0,B",
    colonne={"presente": {"ruolo": "presenza", "usa": True},
             "classe": {"ruolo": "categoria", "usa": True}},
    zeriCondivisi="si", significatoMancanti="sconosciuto",
)
assert piano_sconosciuto["completo"], piano_sconosciuto
quasi_uguali(p.calcola_matrice_gower(dati_assenze, risposte_sconosciuto)["matrice"][0][1], 0)
risposte_assenza = {**risposte_sconosciuto, "significatoMancanti": "assenza"}
assert p.crea_piano_confronto(dati_assenze, risposte_assenza)["completo"]
quasi_uguali(p.calcola_matrice_gower(dati_assenze, risposte_assenza)["matrice"][0][1], .5)

dati_zero, piano_zero_non_confermato, risposte_zero = piano_gower_per(
    "numero,classe\n1,A\n,B\n3,A",
    colonne={"numero": {"ruolo": "quantita", "usa": True},
             "classe": {"ruolo": "categoria", "usa": True}},
    significatoMancanti="assenza",
)
assert not piano_zero_non_confermato["completo"]
risposte_zero["mancantiPerColonna"] = {"numero": "zero"}
assert p.crea_piano_confronto(dati_zero, risposte_zero)["completo"]
quasi_uguali(p.calcola_matrice_gower(dati_zero, risposte_zero)["matrice"][0][1], 2 / 3)

# Positività binaria: "sì/no" è interpretato; etichette arbitrarie richiedono conferma.
dati_si_no, piano_si_no, risposte_si_no = piano_gower_per(
    "presente,classe\nsì,A\nno,A\nno,B",
    colonne={"presente": {"ruolo": "presenza", "usa": True},
             "classe": {"ruolo": "categoria", "usa": True}},
    zeriCondivisi="no",
)
assert piano_si_no["completo"], piano_si_no
matrice_si_no = p.calcola_matrice_gower(dati_si_no, risposte_si_no)["matrice"]
quasi_uguali(matrice_si_no[0][1], .5)
quasi_uguali(matrice_si_no[1][2], 1)
dati_ab, piano_ab, risposte_ab = piano_gower_per(
    "presente,classe\nA,x\nB,x\nB,y",
    colonne={"presente": {"ruolo": "presenza", "usa": True},
             "classe": {"ruolo": "categoria", "usa": True}},
    zeriCondivisi="no",
)
assert not piano_ab["completo"]
risposte_ab["presenzaPositivaPerColonna"] = {"presente": "A"}
assert p.crea_piano_confronto(dati_ab, risposte_ab)["completo"]

# La scelta sulle assenze può variare tra due caratteristiche binarie.
dati_binari, piano_binari, risposte_binari = piano_gower_per(
    "primo,secondo,classe\n1,0,x\n0,0,x\n0,1,y",
    colonne={"primo": {"ruolo": "presenza", "usa": True},
             "secondo": {"ruolo": "presenza", "usa": True},
             "classe": {"ruolo": "categoria", "usa": True}},
    zeriCondivisi="si",
    zeriCondivisiPerColonna={"primo": "no", "secondo": "si"},
)
assert piano_binari["completo"], piano_binari
quasi_uguali(p.calcola_matrice_gower(dati_binari, risposte_binari)["matrice"][1][2], 1)

# I livelli testuali devono essere esplicitamente ordinati.
dati_ordinali, piano_ordinali, risposte_ordinali = piano_gower_per(
    "livello,classe\nbasso,x\nmedio,x\nalto,y",
    colonne={"livello": {"ruolo": "livello", "usa": True},
             "classe": {"ruolo": "categoria", "usa": True}},
    ordineLivelli="si",
)
assert not piano_ordinali["completo"]
risposte_ordinali["ordiniLivelliGower"] = {"livello": "basso; medio; alto"}
assert p.crea_piano_confronto(dati_ordinali, risposte_ordinali)["completo"]
matrice_ordinali = p.calcola_matrice_gower(dati_ordinali, risposte_ordinali)["matrice"]
quasi_uguali(matrice_ordinali[0][1], .25)
quasi_uguali(matrice_ordinali[0][2], 1)

print("Tutti i test Python di preprocessing sono stati superati.")
